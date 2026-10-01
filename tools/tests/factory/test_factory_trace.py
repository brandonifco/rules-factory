#!/usr/bin/env python3
"""`factory trace` reports what an engine's records say about each entry, and labels how it knows (#576).

Every fixture is an engine `factory produce` wrote, so the trace reads the same records and the
same merge a real engine has. The two-corpus fixture (test_two_corpus_map.py) is small and cites two
corpora, which is what keeps them distinct is asserted on. The srd-52 composition is two published
maps of one corpus, which is what makes an entry id a derived fact rather than a recorded one.

Asserted:

  * every relationship is exactly one of recorded, derived, inferred, unknown; a recorded or derived
    one names its basis, an inferred one its mechanism, and an unknown one says why and is a gap;
  * named tests and mutations are the overlay's bytes, attributed to the overlay field that holds
    them, and a test with no mutation is unknown rather than assumed;
  * entry -> implementation is inferred from the handler declaration and never recorded, build
    output is not read, and an implemented entry nothing implements is unknown;
  * each corpus an entry cites is kept distinct, and a locator naming a corpus provenance does not
    record is unknown;
  * the topology is read from the record and from git and never corrected: standalone, embedded, a
    moved engine, no repository, and a record from before format 9;
  * no corpus text reaches the trace, the same engine gives the same bytes, and no absolute path is
    printed;
  * what is not a produced engine is refused, exit 1, and a non-directory is a usage error, exit 2.

Run: python3 -m pytest tools/tests/factory/test_factory_trace.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
PACK = os.path.join(TOOLS, "pack-map.py")

sys.path.insert(0, TOOLS)
try:
    from factory import __main__ as factory
finally:
    sys.path.remove(TOOLS)

# The module, not its TestCase: a class bound here would be collected and run a second time.
from tests.factory import test_two_corpus_map as two  # noqa: E402

CLASSES = ("recorded", "derived", "inferred", "unknown")
HANDLER = """namespace TwoSection;

internal static partial class Handlers
{
    internal static partial Resolution<object> ListedInTheTable(Requests.ListedInTheTableRequest request) =>
        Resolution<object>.FromValue(true);
}
"""
MUTATION = ("Handlers.ListedInTheTable returned false (`FromValue(false)` for `FromValue(true)`); "
            "this test went red.")


def feed(directory, nupkgs):
    """A NuGet global packages folder holding `nupkgs`, laid out where intake looks for Id@Version."""
    for nupkg in nupkgs:
        # The id is every dot-separated part before the version, which is the last three numbers.
        parts = os.path.basename(nupkg)[:-len(".nupkg")].lower().split(".")
        package_id, version = ".".join(parts[:-3]), ".".join(parts[-3:])
        target = os.path.join(directory, package_id, version)
        os.makedirs(target, exist_ok=True)
        shutil.copy(nupkg, os.path.join(target, f"{package_id}.{version}.nupkg"))
    return directory


def run(argv, packages):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"NUGET_PACKAGES": packages}), redirect_stdout(out), redirect_stderr(err):
        code = factory.main(argv)
    return code, out.getvalue(), err.getvalue()


def produce(nupkgs, corpora, name, out, *extra):
    argv = ["produce"]
    for nupkg in nupkgs:
        argv += ["--package", nupkg]
    for corpus in corpora:
        argv += ["--corpus", corpus]
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = factory.main(argv + ["--name", name, "--out", out, "--allow-dirty", "--no-verify", *extra])
    assert code == factory.NOT_VERIFIED, buffer.getvalue()


def git_init(directory):
    subprocess.run(["git", "init", "-q", directory], check=True)


def facts(node):
    """Every relationship in the trace: each dict that carries an evidence class and a value."""
    if isinstance(node, dict):
        if "evidence" in node and "value" in node:
            yield node
            return
        for value in node.values():
            yield from facts(value)
    elif isinstance(node, list):
        for value in node:
            yield from facts(value)


def entry(trace, entry_id):
    (found,) = [e for e in trace["entries"] if e["id"]["value"] == entry_id]
    return found


class TraceOfATwoCorpusEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp(prefix="trace-")
        cls.map_dir = two.TwoCorpusMap.write_map(os.path.join(cls.shared, "two-section-fixture"))
        cls.nupkg = two.TwoCorpusMap.pack(cls.map_dir, os.path.join(cls.shared, "feed"))
        cls.packages = feed(os.path.join(cls.shared, "packages"), [cls.nupkg])
        cls.corpora = [os.path.join(cls.map_dir, name) for _, name, _ in two.SECTIONS]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="trace-case-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.engine = os.path.join(self.tmp, "engine")
        produce([self.nupkg], self.corpora, "TwoSection", self.engine)

    def trace(self, engine=None, packages=None):
        code, out, err = run(["trace", "--engine", engine or self.engine, "--json"], packages or self.packages)
        self.assertEqual(code, 0, err)
        return json.loads(out), out

    def overlay(self, entry_id, item):
        path = os.path.join(self.engine, "overlay", f"{entry_id}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(item, handle, indent=2)

    def source(self, relative, text):
        path = os.path.join(self.engine, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def record(self, change):
        path = os.path.join(self.engine, "provenance.json")
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        change(document)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)

    def implemented(self, tests):
        self.overlay("listed-in-the-table", {"status": "implemented",
                                             "implementedIn": {"ruleset": "fixture", "version": 1}, "tests": tests})

    # --- the evidence classes -----------------------------------------------------------------

    def test_every_relationship_has_one_evidence_class_and_says_how_it_knows(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}, {"test": "ListedTests.Bare"}])
        self.source("src/TwoSection/Handlers/ListedInTheTable.cs", HANDLER)
        trace, _ = self.trace()
        seen = set()
        for fact in facts(trace):
            seen.add(fact["evidence"])
            self.assertIn(fact["evidence"], CLASSES, fact)
            if fact["evidence"] in ("recorded", "derived"):
                self.assertTrue(fact.get("basis"), fact)
            elif fact["evidence"] == "inferred":
                self.assertTrue(fact.get("mechanism"), fact)
            else:
                self.assertIsNone(fact["value"], fact)
                self.assertTrue(fact.get("why"), fact)
        self.assertEqual(seen, set(CLASSES))

    def test_every_unknown_is_also_a_gap(self):
        trace, _ = self.trace()
        unknowns = [f["why"] for f in facts(trace) if f["evidence"] == "unknown"]
        self.assertTrue(unknowns)
        gaps = [g["why"] for g in trace["gaps"]]
        for why in unknowns:
            self.assertIn(why, gaps)
        self.assertEqual(sum(trace["summary"]["gaps"].values()), len(trace["gaps"]))
        self.assertEqual(trace["summary"]["evidence"]["unknown"], len(unknowns))

    # --- tests and mutations ------------------------------------------------------------------

    def test_named_tests_and_their_mutations_are_the_overlays_bytes_and_say_which_field(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        listed = entry(self.trace()[0], "listed-in-the-table")
        (test,) = listed["tests"]
        self.assertEqual(test["name"], {"value": "ListedTests.Holds", "evidence": "recorded",
                                        "basis": "overlay/listed-in-the-table.json tests[0].test"})
        self.assertEqual(test["mutation"], {"value": MUTATION, "evidence": "recorded",
                                            "basis": "overlay/listed-in-the-table.json tests[0].mutation"})
        self.assertEqual(listed["status"]["basis"], "overlay/listed-in-the-table.json status")
        self.assertEqual(listed["implementedIn"]["value"], {"ruleset": "fixture", "version": 1})

    def test_a_test_with_no_mutation_is_unknown_and_a_gap(self):
        self.implemented([{"test": "ListedTests.Bare"}])
        trace, _ = self.trace()
        (test,) = entry(trace, "listed-in-the-table")["tests"]
        self.assertEqual(test["mutation"]["evidence"], "unknown")
        self.assertIn({"subject": "entry:listed-in-the-table", "relationship": "test -> mutation",
                       "why": test["mutation"]["why"]}, trace["gaps"])

    def test_an_implemented_entry_that_names_no_test_is_a_gap(self):
        self.implemented([])
        trace, _ = self.trace()
        self.assertIn({"subject": "entry:listed-in-the-table", "relationship": "entry -> test",
                       "why": "the entry is implemented and names no test"}, trace["gaps"])

    def test_an_entry_with_no_overlay_file_takes_its_status_from_the_map_and_says_so(self):
        water = entry(self.trace()[0], "w-is-water-only")
        self.assertEqual(water["status"]["value"], "mapped")
        self.assertIn("map/corpus-map.json", water["status"]["basis"])
        self.assertIn("no overlay/w-is-water-only.json", water["status"]["basis"])
        self.assertNotIn("implementedIn", water)

    # --- implementation -----------------------------------------------------------------------

    def test_implementation_is_inferred_from_the_handler_and_never_recorded(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        self.source("src/TwoSection/Handlers/ListedInTheTable.cs", HANDLER)
        self.source("src/TwoSection/Rules/Table.cs",
                    "namespace TwoSection;\n\ninternal static class Table\n{\n"
                    "    internal const string Entry = \"listed-in-the-table\";\n}\n")
        # Build output names the entry too, and is not the engine's code.
        self.source("src/TwoSection/obj/Debug/Stale.cs", HANDLER)
        trace, _ = self.trace()
        candidates = entry(trace, "listed-in-the-table")["implementation"]
        self.assertEqual([c["value"] for c in candidates],
                         [{"path": "src/TwoSection/Handlers/ListedInTheTable.cs", "symbol": "Handlers.ListedInTheTable"},
                          {"path": "src/TwoSection/Rules/Table.cs", "symbol": None}])
        self.assertEqual({c["evidence"] for c in candidates}, {"inferred"})
        self.assertIn("reviewscope.partial_members", candidates[0]["mechanism"])
        self.assertIn("reviewscope.entry_references", candidates[1]["mechanism"])
        for listed in trace["entries"]:
            for fact in listed["implementation"]:
                self.assertIn(fact["evidence"], ("inferred", "unknown"))

    def test_an_implemented_entry_nothing_implements_is_unknown_and_a_gap(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        trace, _ = self.trace()
        (fact,) = entry(trace, "listed-in-the-table")["implementation"]
        self.assertEqual(fact["evidence"], "unknown")
        self.assertIn({"subject": "entry:listed-in-the-table", "relationship": "entry -> implementation",
                       "why": fact["why"]}, trace["gaps"])

    # --- corpora and locators -----------------------------------------------------------------

    def test_each_corpus_an_entry_cites_is_kept_distinct(self):
        trace, _ = self.trace()
        self.assertEqual([c["sourceId"]["value"] for c in trace["corpora"]], ["cfr-9-9.101", "cfr-9-9.102"])
        (package,) = trace["maps"]
        self.assertEqual(package["corpora"]["value"], ["cfr-9-9.101", "cfr-9-9.102"])
        self.assertEqual(package["principalCorpus"]["value"], "cfr-9-9.101")
        for entry_id, source in (("listed-in-the-table", "cfr-9-9.101"), ("w-is-water-only", "cfr-9-9.102")):
            listed = entry(trace, entry_id)
            self.assertEqual(listed["locator"]["value"]["sourceId"], source)
            self.assertEqual(listed["corpus"], {"value": source, "evidence": "derived",
                                                "basis": "the locator's sourceId is a sourceId provenance.json "
                                                         "corpora[] records"})
            self.assertEqual(listed["segment"]["evidence"], "unknown")

    def test_a_locator_naming_a_corpus_provenance_does_not_record_is_unknown(self):
        self.record(lambda r: r.update(corpora=[c for c in r["corpora"] if c["sourceId"] != "cfr-9-9.102"]))
        trace, _ = self.trace()
        water = entry(trace, "w-is-water-only")
        self.assertEqual(water["corpus"]["evidence"], "unknown")
        self.assertIn("cfr-9-9.102", water["corpus"]["why"])
        self.assertIn({"subject": "entry:w-is-water-only", "relationship": "locator -> corpus",
                       "why": water["corpus"]["why"]}, trace["gaps"])

    def test_no_corpus_text_reaches_the_trace(self):
        _, text = self.trace()
        for row in two.ENTRIES:
            self.assertNotIn(row["evidence"], text)
        for _, _, corpus in two.SECTIONS:
            for line in corpus.splitlines():
                if "(a)" in line or "(b)" in line:
                    self.assertNotIn(line.split(")", 1)[1].split("<")[0].strip(), text)

    def test_the_same_engine_gives_the_same_bytes_and_no_absolute_path(self):
        _, first = self.trace()
        _, second = self.trace()
        self.assertEqual(first, second)
        self.assertNotIn(self.tmp, first)
        self.assertNotIn(os.path.realpath(self.tmp), first)

    # --- topology -----------------------------------------------------------------------------

    def test_a_standalone_engine_agrees_with_its_record(self):
        git_init(self.engine)
        topology = self.trace()[0]["topology"]
        self.assertEqual(topology["recordedEnginePath"]["value"], None)
        self.assertEqual(topology["recordedEnginePath"]["evidence"], "recorded")
        self.assertEqual(topology["observedEnginePath"]["value"], None)
        self.assertTrue(topology["agrees"])

    def test_an_engine_in_no_repository_is_unknown_and_not_assumed(self):
        trace, _ = self.trace()
        topology = trace["topology"]
        self.assertEqual(topology["observedEnginePath"]["evidence"], "unknown")
        self.assertIsNone(topology["agrees"])
        self.assertIn("engine -> repository root", [g["relationship"] for g in trace["gaps"]])

    def test_an_embedded_engine_is_traced_from_the_path_its_record_names(self):
        host = os.path.join(self.tmp, "host")
        git_init(host)
        produce([self.nupkg], self.corpora, "TwoSection", os.path.join(host, "engine"), "--repo-root", host)
        topology = self.trace(os.path.join(host, "engine"))[0]["topology"]
        self.assertEqual(topology["recordedEnginePath"]["value"], "engine")
        self.assertEqual(topology["observedEnginePath"]["value"], "engine")
        self.assertTrue(topology["agrees"])

    def test_a_moved_engine_is_reported_and_not_corrected(self):
        host = os.path.join(self.tmp, "host")
        git_init(host)
        produce([self.nupkg], self.corpora, "TwoSection", os.path.join(host, "engine"), "--repo-root", host)
        os.makedirs(os.path.join(host, "elsewhere"))
        os.rename(os.path.join(host, "engine"), os.path.join(host, "elsewhere", "engine"))
        trace, _ = self.trace(os.path.join(host, "elsewhere", "engine"))
        topology = trace["topology"]
        self.assertEqual(topology["recordedEnginePath"]["value"], "engine")
        self.assertEqual(topology["observedEnginePath"]["value"], "elsewhere/engine")
        self.assertFalse(topology["agrees"])
        (gap,) = [g for g in trace["gaps"] if g["relationship"] == "engine -> repository root"]
        self.assertIn("'engine'", gap["why"])
        self.assertIn("'elsewhere/engine'", gap["why"])

    def test_a_record_before_format_9_is_read_as_a_repository_root_and_says_it_was_derived(self):
        self.record(lambda r: r.pop("repository"))
        said = self.trace()[0]["topology"]["recordedEnginePath"]
        self.assertEqual(said["value"], None)
        self.assertEqual(said["evidence"], "derived")
        self.assertIn("repository.from_record", said["basis"])

    def test_a_fact_an_older_record_does_not_carry_is_unknown(self):
        self.record(lambda r: r.pop("kernel"))
        trace, _ = self.trace()
        self.assertEqual(trace["engine"]["kernel"]["version"]["evidence"], "unknown")
        self.assertIn("engine -> kernel.version", [g["relationship"] for g in trace["gaps"]])

    # --- refusals -----------------------------------------------------------------------------

    def test_a_directory_with_no_record_is_refused(self):
        code, out, err = run(["trace", "--engine", self.tmp, "--json"], self.packages)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("has no provenance.json", err)

    def test_a_record_that_is_not_json_is_refused(self):
        with open(os.path.join(self.engine, "provenance.json"), "w", encoding="utf-8") as handle:
            handle.write("{")
        code, out, err = run(["trace", "--engine", self.engine, "--json"], self.packages)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("cannot read provenance.json", err)

    def test_a_package_that_is_not_here_is_refused(self):
        code, out, err = run(["trace", "--engine", self.engine, "--json"], os.path.join(self.tmp, "empty"))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("the entries cannot be traced", err)

    def test_an_overlay_that_does_not_merge_is_refused(self):
        self.overlay("no-such-entry", {"status": "implemented"})
        code, out, err = run(["trace", "--engine", self.engine, "--json"], self.packages)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("do not merge", err)

    def test_an_engine_that_is_not_a_directory_is_a_usage_error(self):
        code, _, err = run(["trace", "--engine", os.path.join(self.tmp, "absent"), "--json"], self.packages)
        self.assertEqual(code, 2, err)


class TraceOfAComposedEngine(unittest.TestCase):
    """Two published maps of one corpus (0067): an entry id is the factory's composition of it."""

    COMPOSED = ("srd-52-combat", "srd-52-conditions")

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp(prefix="trace-composed-")
        out = os.path.join(cls.shared, "feed")
        for slug in cls.COMPOSED:
            subprocess.run([sys.executable, PACK, os.path.join(REPO, "examples", slug), "--out", out], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        nupkgs = sorted(os.path.join(out, n) for n in os.listdir(out) if n.endswith(".nupkg"))
        cls.packages = feed(os.path.join(cls.shared, "packages"), nupkgs)
        cls.engine = os.path.join(cls.shared, "engine")
        produce(nupkgs, [os.path.join(REPO, "examples", "srd-52-combat", "srd-5.2.1.txt")], "Srd52", cls.engine)
        code, out, err = run(["trace", "--engine", cls.engine, "--json"], cls.packages)
        assert code == 0, err
        cls.trace = json.loads(out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def test_both_packages_are_traced_and_each_entry_names_the_one_it_came_from(self):
        self.assertEqual([m["packageId"]["value"] for m in self.trace["maps"]],
                         ["RulesFactory.Maps.Srd52Combat", "RulesFactory.Maps.Srd52Conditions"])
        prone = entry(self.trace, "Srd52Conditions.prone")
        self.assertEqual(prone["package"]["value"], "RulesFactory.Maps.Srd52Conditions")
        self.assertEqual(prone["package"]["evidence"], "derived")
        self.assertEqual(prone["id"]["evidence"], "derived")
        self.assertIn("compose.union", prone["id"]["basis"])
        for listed in self.trace["entries"]:
            self.assertEqual(listed["id"]["evidence"], "derived")
            self.assertTrue(listed["id"]["value"].startswith(("Srd52Combat.", "Srd52Conditions.")))


if __name__ == "__main__":
    unittest.main()
