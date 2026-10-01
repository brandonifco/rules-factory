#!/usr/bin/env python3
"""`factory status` says what an engine's records establish now, and issues no verdict (#585).

Asserted:

  * every count comes from the trace of the same engine: replacing the trace changes the status;
  * provenance's `verification` is reported as recorded, scoped to the produce that wrote it;
  * the working tree is a git fact, clean or moved or unknown, and never a verification;
  * nothing anywhere is an overall verdict, a score or a severity, and verification is "not run";
  * a run writes nothing: every byte and every timestamp under the engine and its .git is unchanged;
  * the text and the JSON say the same things;
  * what is not an engine is refused, exit 1, and a non-directory is a usage error, exit 2.

Run: python3 -m pytest tools/tests/factory/test_factory_status.py
"""
import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

# The fixtures, by module: a TestCase bound here would be collected and run a second time.
from tests.factory import test_factory_trace as fixture  # noqa: E402
from tests.factory import test_two_corpus_map as two  # noqa: E402

factory = fixture.factory
status_step = factory.status_step
trace_step = factory.trace_step

VERDICTS = re.compile(r"\b(overall|verdict|score|severity|healthy|conformant|PASS|FAIL)\b", re.I)


def keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from keys(value)


def snapshot(root):
    """Every path under `root` with its bytes and its modification time: what 'wrote nothing' means."""
    found = {}
    for directory, dirs, names in os.walk(root):
        dirs.sort()
        for name in sorted(names + dirs):
            path = os.path.join(directory, name)
            info = os.lstat(path)
            data = None
            if os.path.isfile(path) and not os.path.islink(path):
                with open(path, "rb") as handle:
                    data = handle.read()
            found[os.path.relpath(path, root)] = (info.st_mtime_ns, data)
    return found


class StatusOfAnEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp(prefix="status-")
        cls.map_dir = two.TwoCorpusMap.write_map(os.path.join(cls.shared, "two-section-fixture"))
        cls.nupkg = two.TwoCorpusMap.pack(cls.map_dir, os.path.join(cls.shared, "feed"))
        cls.packages = fixture.feed(os.path.join(cls.shared, "packages"), [cls.nupkg])
        cls.corpora = [os.path.join(cls.map_dir, name) for _, name, _ in two.SECTIONS]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="status-case-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.engine = os.path.join(self.tmp, "engine")
        fixture.produce([self.nupkg], self.corpora, "TwoSection", self.engine)
        os.makedirs(os.path.join(self.engine, "overlay"), exist_ok=True)
        with open(os.path.join(self.engine, "overlay", "listed-in-the-table.json"), "w", encoding="utf-8") as handle:
            json.dump({"status": "implemented", "implementedIn": {"ruleset": "fixture", "version": 1},
                       "tests": [{"test": "ListedTests.Holds", "mutation": fixture.MUTATION},
                                 {"test": "ListedTests.Bare"}]}, handle)

    def status(self, *extra, engine=None):
        code, out, err = fixture.run(["status", "--engine", engine or self.engine, *extra], self.packages)
        return code, out, err

    def report(self):
        code, out, err = self.status("--json")
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def commit(self):
        fixture.git_init(self.engine)
        subprocess.run(["git", "-C", self.engine, "add", "-A"], check=True)
        subprocess.run(["git", "-C", self.engine, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "-m", "engine"], check=True)

    def test_every_count_is_the_traces(self):
        report = self.report()
        done = report["implementation"]
        self.assertEqual(done["entries"], 2)
        self.assertEqual(done["byStatus"], {"implemented": 1, "mapped": 1})
        self.assertEqual((done["namedTests"], done["mutationsRecorded"]), (2, 1))
        with mock.patch.dict(os.environ, {"NUGET_PACKAGES": self.packages}):
            traced = trace_step.build(self.engine)
        self.assertEqual(done["evidence"], traced["summary"]["evidence"])
        self.assertEqual(done["gaps"], traced["summary"]["gaps"])
        self.assertEqual(report["engine"]["topology"], traced["topology"])

    def test_a_different_trace_is_a_different_status(self):
        """No second reader: what `status` counts is what the trace says, whatever the overlay says."""
        with mock.patch.dict(os.environ, {"NUGET_PACKAGES": self.packages}):
            real = trace_step.build(self.engine)
        altered = copy.deepcopy(real)
        altered["entries"] = [e for e in altered["entries"] if e["id"]["value"] == "w-is-water-only"]
        altered["summary"]["evidence"] = {"recorded": 7, "derived": 0, "inferred": 0, "unknown": 0}
        with mock.patch.object(trace_step, "build", return_value=altered):
            report = self.report()
        # The overlay still holds an implemented entry with two tests; the trace handed in does not.
        self.assertEqual(report["implementation"]["entries"], 1)
        self.assertEqual(report["implementation"]["byStatus"], {"mapped": 1})
        self.assertEqual(report["implementation"]["namedTests"], 0)
        self.assertEqual(report["implementation"]["evidence"]["recorded"], 7)

    def test_provenance_verification_is_a_recorded_fact_about_the_produce_that_wrote_it(self):
        verification = self.report()["provenance"]["verification"]
        # The fixture is produced with --no-verify, and the record says so.
        self.assertEqual(verification["verified"], {"value": False, "evidence": "recorded",
                                                    "basis": "provenance.json verification.verified"})
        self.assertEqual(verification["scope"], status_step.HISTORICAL)
        self.assertIn("not about the tree as it stands", verification["scope"])

    def test_verification_is_not_run_and_says_so(self):
        report = self.report()
        self.assertEqual(report["verification"], {"ranNow": False, "says": status_step.NOT_RUN})
        _, text, _ = self.status()
        self.assertIn("not run by this invocation", text)

    def test_a_clean_tree_is_a_git_fact_and_not_a_verification(self):
        self.commit()
        tree = self.report()["currentTree"]
        self.assertEqual(tree["value"], {"clean": True, "changedPaths": 0})
        self.assertEqual(tree["evidence"], "derived")
        self.assertIn("is not a verification", tree["basis"])
        _, text, _ = self.status()
        self.assertIn("working tree  clean [git] -- not a verification", text)

    def test_a_moved_tree_is_counted(self):
        self.commit()
        with open(os.path.join(self.engine, "overlay", "listed-in-the-table.json"), "a", encoding="utf-8") as handle:
            handle.write("\n")
        self.assertEqual(self.report()["currentTree"]["value"], {"clean": False, "changedPaths": 1})

    def test_a_tree_in_no_repository_is_unknown(self):
        tree = self.report()["currentTree"]
        self.assertEqual(tree["evidence"], "unknown")
        self.assertIn("git could not read the engine's repository", tree["why"])

    def test_there_is_no_verdict_anywhere(self):
        self.commit()
        report = self.report()
        for key in keys(report):
            self.assertIsNone(VERDICTS.search(key), key)
        _, text, _ = self.status()
        # The fixture's own data says none of these words, so any in the text are the reporter's.
        self.assertIsNone(VERDICTS.search(fixture.MUTATION))
        self.assertIsNone(VERDICTS.search(text), VERDICTS.search(text))

    def test_a_run_writes_nothing_not_even_gits_index(self):
        self.commit()
        # Make the index stale, so that a git that may refresh it would write it.
        path = os.path.join(self.engine, "overlay", "listed-in-the-table.json")
        stamp = os.stat(path).st_mtime_ns + 5_000_000_000
        os.utime(path, ns=(stamp, stamp))
        before = snapshot(self.engine)
        for extra in ((), ("--json",)):
            code, _, err = self.status(*extra)
            self.assertEqual(code, 0, err)
        self.assertEqual(snapshot(self.engine), before)

    def test_every_value_in_the_json_is_on_the_text_page(self):
        self.commit()
        report = self.report()
        _, text, _ = self.status()
        for fact in fixture.facts(report):
            if fact["evidence"] == "unknown":
                self.assertIn(fact["why"], text)
            elif not isinstance(fact["value"], dict):
                # Beside its own evidence class, as the page prints every fact: a `True` elsewhere on
                # the page is not this one.
                self.assertIn(f"{fact['value']}  [{fact['evidence']}]", text, fact)

    def test_an_engine_git_does_not_track_is_unknown_not_clean(self):
        outer = os.path.join(self.tmp, "outer")
        os.makedirs(outer)
        fixture.git_init(outer)
        with open(os.path.join(outer, ".gitignore"), "w", encoding="utf-8") as handle:
            handle.write("eng/\n")
        shutil.copytree(self.engine, os.path.join(outer, "eng"))
        code, out, err = self.status("--json", engine=os.path.join(outer, "eng"))
        tree = json.loads(out)["currentTree"]
        self.assertEqual(tree["evidence"], "unknown")
        self.assertIn("git tracks no file under the engine", tree["why"])

    def test_the_text_and_the_json_say_the_same_things(self):
        self.commit()
        report = self.report()
        _, text, _ = self.status()
        done = report["implementation"]
        self.assertIn(f"entries       {done['entries']}: 1 implemented, 1 mapped", text)
        self.assertIn(f"named tests   {done['namedTests']}, {done['mutationsRecorded']} with a recorded mutation", text)
        for evidence, count in done["evidence"].items():
            self.assertIn(f"{count} {evidence}", text)
        for relationship, count in done["gaps"].items():
            self.assertIn(f"{count} {relationship}", text)
        for corpus in report["inputs"]["corpora"]:
            self.assertIn(corpus["contentHash"]["value"], text)
        self.assertIn(report["engine"]["name"]["value"], text)

    def test_what_is_not_an_engine_is_refused_and_a_non_directory_is_a_usage_error(self):
        code, out, err = self.status(engine=self.tmp)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("has no provenance.json", err)
        code, _, _ = self.status(engine=os.path.join(self.tmp, "absent"))
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
