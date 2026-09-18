#!/usr/bin/env python3
"""Staging a blind second mapping is a step something runs, and something checks (#223).

What has to be watched here is not that the tool edits text. It is the two ways a redaction
tool is worse than no redaction tool:

  * it passes over a leak, which manufactures the confidence a blind run is evidence *of*;
  * it passes over an occurrence it cannot judge, which does the same thing more quietly.

So the fixtures are small maps and small documents, and each test mutates one thing: an entry id
left in, an edit that stops matching, an acknowledgement that stops covering, a staged file
edited after the fact. The committed `srd-52-conditions` bundle is checked too, against the
leaks #223 actually names.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

sys.path.insert(0, TOOLS)
try:
    from mapper import cli, staging
finally:
    sys.path.remove(TOOLS)

BUNDLE = os.path.join(REPO, "examples", "srd-52-conditions", "blind-mapping")

# The two documents a second mapper gets, in miniature. `slice-rule` and `neighbour-rule` are
# entry ids of the two maps below; `cover` is a one-word id, and also a word.
METHOD = """# Method

A worked example: `slice-rule` is the entry that shows what a gate is.
Another: the neighbour map's `neighbour-rule` shows the same thing.
A rule may cover a case its neighbour does not.
See [0001](decisions/0001-something.md) for the argument.
"""
MAP_DOC = """# What a map is

`toybook-1909` is the source these examples come from.
Nothing else here names anything.
"""


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_json(path, value):
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


class Fixture(unittest.TestCase):
    """A corpus with two mapped slices, two documents that leak, and a spec that redacts them.

    Laid out the way the repository is -- `<root>/examples/<trial>/corpus-map.json` -- because
    the sibling maps of a corpus are found by walking that shape, and a test that hand-fed the
    neighbour would not watch the one thing that matters: a leak of the *other* slice.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.examples = os.path.join(self.tmp, "examples")
        for trial, entries in (
                ("slice", [{"id": "slice-rule", "name": "The slice's rule"},
                           {"id": "cover", "name": "Cover"}]),
                ("neighbour", [{"id": "neighbour-rule", "name": "The neighbour's rule"}]),
                ("elsewhere", [{"id": "other-rule", "name": "Another corpus's rule"}])):
            os.makedirs(os.path.join(self.examples, trial))
            write_json(os.path.join(self.examples, trial, "corpus-map.json"),
                       {"schemaVersion": 1,
                        "corpus": "otherbook-1950" if trial == "elsewhere" else "toybook-1909",
                        "entries": entries})
        self.docs = os.path.join(self.tmp, "docs")
        os.makedirs(self.docs)
        write(os.path.join(self.docs, "method.md"), METHOD)
        write(os.path.join(self.docs, "corpus-map.md"), MAP_DOC)
        self.out = os.path.join(self.examples, "slice", "blind-mapping")
        os.makedirs(self.out)
        self.spec_path = os.path.join(self.out, "staging.json")
        self.spec = {
            "stagingVersion": 1,
            "map": "../corpus-map.json",
            "documents": ["../../../docs/method.md", "../../../docs/corpus-map.md"],
            "edits": [
                {"document": "method.md", "why": "the slice's own entry",
                 "find": "A worked example: `slice-rule` is the entry that shows what a gate is.",
                 "replace": "A worked example shows what a gate is."},
                {"document": "method.md", "why": "the neighbouring slice's entry",
                 "find": "Another: the neighbour map's `neighbour-rule` shows the same thing.",
                 "replace": "Another shows the same thing."},
                {"document": "corpus-map.md", "why": "the corpus id",
                 "find": "`toybook-1909` is the source these examples come from.",
                 "replace": "One source is where these examples come from."},
            ],
            "acknowledged": [
                {"document": "method.md", "term": "cover",
                 "reason": "the English verb, in \"may cover a case\""},
            ],
        }
        self.write_spec()

    def write_spec(self):
        write_json(self.spec_path, self.spec)

    def stage(self, *extra):
        return run(["stage", self.spec_path, *extra])

    def verify(self):
        return run(["stage", "--verify",
                    os.path.join(self.out, staging.RECORD_FILENAME)])


class TestStagingTheBundle(Fixture):
    def test_the_spec_stages_both_documents_and_writes_the_record(self):
        code, out, err = self.stage()
        self.assertEqual(code, 0, out + err)
        for name in ("method.md", "corpus-map.md", staging.LOG_FILENAME,
                     staging.RECORD_FILENAME):
            self.assertTrue(os.path.isfile(os.path.join(self.out, name)), name)
        staged = io.open(os.path.join(self.out, "method.md"), encoding="utf-8").read()
        self.assertNotIn("slice-rule", staged)
        self.assertNotIn("neighbour-rule", staged)

    def test_a_link_the_mapper_cannot_follow_becomes_its_text(self):
        self.stage()
        staged = io.open(os.path.join(self.out, "method.md"), encoding="utf-8").read()
        self.assertIn("See 0001 for the argument.", staged)

    def test_the_record_names_every_map_of_the_corpus_and_no_other_corpus(self):
        self.stage()
        record = json.load(io.open(os.path.join(self.out, staging.RECORD_FILENAME),
                                   encoding="utf-8"))
        came_from = sorted(source["path"].replace(os.sep, "/")
                           for source in record["vocabularyFrom"])
        self.assertEqual(came_from, ["../../neighbour/corpus-map.json", "../corpus-map.json"])
        self.assertIn("neighbour-rule", record["terms"]["certain"])
        self.assertNotIn("other-rule", record["terms"]["certain"])


class TestWhatFailsAStaging(Fixture):
    def test_an_entry_id_of_the_slice_left_in_fails(self):
        self.spec["edits"] = self.spec["edits"][1:]
        self.write_spec()
        code, out, _ = self.stage()
        self.assertEqual(code, 1)
        self.assertIn("slice-rule", out)
        self.assertIn("not blind", out)

    def test_an_entry_id_of_the_neighbouring_slice_left_in_fails(self):
        """#223's actual leak: `method.md` named four entries of the *other* SRD slice."""
        del self.spec["edits"][1]
        self.write_spec()
        code, out, _ = self.stage()
        self.assertEqual(code, 1)
        self.assertIn("neighbour-rule", out)

    def test_the_corpus_id_left_in_fails(self):
        self.spec["edits"] = self.spec["edits"][:2]
        self.write_spec()
        code, out, _ = self.stage()
        self.assertEqual(code, 1)
        self.assertIn("toybook-1909", out)

    def test_a_compound_cannot_hide_a_leak(self):
        """The first real run reported clean while `srd-52-combat` was still in the text."""
        write(os.path.join(self.docs, "corpus-map.md"),
              MAP_DOC + "\nThe engine is `slice-rule-engine`, built from TOYBOOK_v1.pdf.\n")
        code, out, _ = self.stage()
        self.assertEqual(code, 1)
        self.assertIn("slice-rule", out)

    def test_an_edit_that_no_longer_matches_fails(self):
        self.spec["edits"][0]["find"] = "A worked example: `slice-rule` is the entry that moved."
        self.write_spec()
        code, out, _ = self.stage()
        self.assertEqual(code, 1)
        self.assertIn("matched 0 time(s)", out)

    def test_an_edit_that_matches_twice_fails(self):
        write(os.path.join(self.docs, "method.md"), METHOD + METHOD)
        code, out, _ = self.stage()
        self.assertEqual(code, 1)
        self.assertIn("matched 2 time(s)", out)

    def test_an_acknowledgement_that_covers_nothing_fails(self):
        self.spec["acknowledged"].append(
            {"document": "corpus-map.md", "term": "cover", "reason": "not there"})
        self.write_spec()
        code, out, _ = self.stage()
        self.assertEqual(code, 1)
        self.assertIn("does not occur", out)


class TestWhatItWillNotDecide(Fixture):
    def test_an_unacknowledged_one_word_id_is_not_verified_rather_than_passed(self):
        self.spec["acknowledged"] = []
        self.write_spec()
        code, out, _ = self.stage()
        self.assertEqual(code, cli.NOT_VERIFIED)
        self.assertIn("NOT VERIFIED", out)
        self.assertIn("cover", out)

    def test_acknowledging_it_with_a_reason_lets_the_run_pass_and_records_the_count(self):
        code, out, err = self.stage()
        self.assertEqual(code, 0, out + err)
        record = json.load(io.open(os.path.join(self.out, staging.RECORD_FILENAME),
                                   encoding="utf-8"))
        self.assertEqual(record["acknowledged"],
                         [{"document": "method.md", "term": "cover", "occurrences": 1,
                           "reason": "the English verb, in \"may cover a case\""}])

    def test_every_run_says_what_it_did_not_look_for(self):
        _, out, _ = self.stage()
        self.assertIn("what this did not look for", out)
        for limit in staging.LIMITS:
            self.assertIn(limit, out)


class TestVerifyingARecord(Fixture):
    def test_a_staged_bundle_verifies(self):
        self.stage()
        code, out, err = self.verify()
        self.assertEqual(code, 0, out + err)

    def test_a_staged_document_edited_after_the_fact_fails(self):
        self.stage()
        path = os.path.join(self.out, "method.md")
        write(path, io.open(path, encoding="utf-8").read() + "\nAnd `slice-rule` is back.\n")
        code, out, _ = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("is not the one this record covers", out)

    def test_a_record_claiming_a_redaction_it_did_not_make_fails(self):
        """The digests would still match: the record and the bytes are changed together."""
        self.stage()
        path = os.path.join(self.out, "method.md")
        write(path, io.open(path, encoding="utf-8").read() + "\nAnd `slice-rule` is back.\n")
        record_path = os.path.join(self.out, staging.RECORD_FILENAME)
        record = json.load(io.open(record_path, encoding="utf-8"))
        for document in record["documents"]:
            if document["name"] == "method.md":
                document["sha256"] = staging.sha256_file(path)
        write_json(record_path, record)
        code, out, _ = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("is not redacted", out)

    def test_a_record_with_no_vocabulary_proves_nothing_and_fails(self):
        self.stage()
        record_path = os.path.join(self.out, staging.RECORD_FILENAME)
        record = json.load(io.open(record_path, encoding="utf-8"))
        # Only the vocabulary is emptied: with the acknowledgements left in, their counts would
        # fail on their own and the test would pass for the wrong reason.
        record["terms"] = {"certain": [], "possible": []}
        record["acknowledged"] = []
        write_json(record_path, record)
        code, out, _ = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("examine nothing", out)


class TestTheCommittedBundle(unittest.TestCase):
    """The evidence run, held to the two leaks #223 names."""

    def test_the_srd_52_conditions_bundle_verifies(self):
        code, out, err = run(["stage", "--verify",
                              os.path.join(BUNDLE, staging.RECORD_FILENAME)])
        self.assertEqual(code, 0, out + err)

    def test_neither_leak_223_names_is_in_the_staged_documents(self):
        for name, leaked in (("corpus-map.md", ["incapacitated-condition"]),
                             ("method.md", ["cover-degree", "falling-off", "attack-resolution",
                                            "initiative-ties"])):
            text = io.open(os.path.join(BUNDLE, name), encoding="utf-8").read()
            for term in leaked:
                with self.subTest(document=name, term=term):
                    self.assertNotIn(term, text)

    def test_the_staged_documents_do_not_name_the_corpus(self):
        for name in ("method.md", "corpus-map.md"):
            text = io.open(os.path.join(BUNDLE, name), encoding="utf-8").read().lower()
            with self.subTest(document=name):
                self.assertNotIn("srd", text)


if __name__ == "__main__":
    unittest.main()
