#!/usr/bin/env python3
"""Every check in check-locators.py, proved able to fail.

Same pattern as test_check_map.py: build a map and a corpus the spec says agree, assert the
named check reports `ok`, mutate exactly the thing that check exists to catch, and assert
the same check reports `fail`. A check with no failing test here is a check nobody has
shown can fail.

The corpus is synthetic and written here rather than sliced out of `examples/`, because an
expectation drawn from the thing under test proves nothing -- and because the three checks
have to be exercised over a corpus small enough that "page 3 is reached by no entry" is
readable at a glance.

Run: python3 -m unittest discover -s tools/tests
"""
import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "check-locators.py")

_spec = importlib.util.spec_from_file_location("check_locators", TOOL)
check_locators = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_locators)


CORPUS = """
{1}
A widget is played by two persons with a pair of tokens.

{2}
The right to move a token is subject to the number shown.

{3}
Where several rounds are played in succession, the winner moves first.

{4}
A leading principle is to keep your tokens together where you fairly can.

{5}
This page belongs to the next chapter and is outside the extent.
"""


def entry(entry_id, citation, evidence, **overrides):
    base = {
        "id": entry_id,
        "name": f"The rule called {entry_id}",
        "locator": {"sourceId": "demo-corpus", "citation": citation},
        "kind": "value",
        "scope": "in",
        "clarity": "clear",
        "evidence": evidence,
        "status": "mapped",
    }
    base.update(overrides)
    return base


def valid_map():
    """A map whose citations, absence and reach all hold against CORPUS."""
    return {
        "schemaVersion": 1,
        "corpus": "demo-corpus",
        "baseline": {"contentHash": "a" * 64, "hashDerivation": "demo-plain-text"},
        "extent": {"unit": "page", "from": 1, "to": 4},
        "entries": [
            entry("player-count", "Part One / p. 1",
                  "A widget is played by two persons with a pair of tokens."),
            entry("legal-destination", "Part One / p. 2",
                  "The right to move a token is subject to the number shown."),
            entry("next-round-opening", "Part One / p. 3",
                  "Where several rounds are played in succession, the winner moves first."),
            entry("strategy-advice", "Part One / p. 4",
                  "A leading principle is to keep your tokens together where you fairly can.",
                  scope="out", status="declined"),
            # 0009: the corpus does not state this rule. It cites and quotes the passage the
            # rule would be in -- the apparatus sentence, which closes its list -- so the
            # entry is as locatable as any other and the absence is what is extra.
            entry("doubling", "Part One / p. 1",
                  "A widget is played by two persons with a pair of tokens.",
                  kind="operation", scope="out", status="declined",
                  absentFrom={"searched": ["doubling", "redouble", "raise the stake"]}),
        ],
    }


class LocatorCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.corpus_path = os.path.join(self.root, "corpus.txt")
        with open(self.corpus_path, "w", encoding="utf-8") as handle:
            handle.write(CORPUS)

    def run_tool(self, document, corpus_path=None):
        path = os.path.join(self.root, "corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_locators.main([path, corpus_path or self.corpus_path])
        return code, out.getvalue() + err.getvalue()

    def status_of(self, output, check):
        found = re.search(rf"^\[(ok|fail|skip)\] {re.escape(check)}:", output, re.M)
        self.assertIsNotNone(found, f"check {check!r} did not report at all:\n{output}")
        return found.group(1)

    def assert_catches(self, check, mutate, expect="fail"):
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, check), "ok", output)
        self.assertEqual(code, 0, output)
        document = valid_map()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, check), expect, output)
        self.assertEqual(code, 1, output)


class TestFixtureIsValid(LocatorCase):
    def test_the_valid_map_passes_every_check(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(code, 0, output)
        self.assertNotIn("[fail]", output, output)
        self.assertNotIn("[skip]", output, output)


class TestLocators(LocatorCase):
    def test_a_citation_naming_the_wrong_page_fails(self):
        self.assert_catches(
            "locators", lambda d: d["entries"][2]["locator"].update(citation="Part One / p. 2"))

    def test_evidence_that_is_a_summary_rather_than_a_quote_fails(self):
        # The defect that let thirteen wrong citations survive a build (#18).
        self.assert_catches(
            "locators", lambda d: d["entries"][1].update(evidence="Both elections."))

    def test_a_citation_naming_no_page_fails(self):
        # What `(absent)` was, before 0009 gave an absence a locator that cites a passage.
        self.assert_catches(
            "locators", lambda d: d["entries"][4]["locator"].update(citation="(absent)"))

    def test_a_map_whose_evidence_is_nowhere_in_the_corpus_does_not_report_ok(self):
        document = valid_map()
        for item in document["entries"]:
            item["evidence"] = "A summary of what this entry shows."
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "locators"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 1, output)


class TestAbsence(LocatorCase):
    def test_a_term_the_corpus_actually_contains_fails_the_absence(self):
        # The only check in the repository that goes red by *finding* something.
        self.assert_catches(
            "absence",
            lambda d: d["entries"][4]["absentFrom"]["searched"].append("pair of tokens"),
        )

    def test_the_search_is_bounded_by_the_declared_extent(self):
        # "doubling" is absent from pages 1-4 and present on page 5, which is outside the
        # extent. A whole-volume search would refuse a true absence, and a mapper would
        # learn to write vaguer terms -- which is the opposite of what the field is for.
        document = valid_map()
        with open(self.corpus_path, "a", encoding="utf-8") as handle:
            handle.write("\nA later chapter describes doubling at length.\n")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "absence"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_an_absence_claimed_over_no_extent_is_not_a_search(self):
        document = valid_map()
        document.pop("extent")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "absence"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 1, output)

    def test_an_empty_searched_list_proves_nothing_and_says_so(self):
        document = valid_map()
        document["entries"][4]["absentFrom"]["searched"] = []
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "absence"), "skip", output)
        self.assertEqual(code, 1, output)

    def test_a_map_claiming_no_absence_does_not_report_ok(self):
        document = valid_map()
        document["entries"].pop(4)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "absence"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)


class TestCoverage(LocatorCase):
    def test_a_page_inside_the_extent_that_no_entry_reaches_fails(self):
        # #20 in miniature: the entry covering a page is removed, and the page it was the
        # only reader of is named. Before this check, nothing distinguished that page from
        # one a mapper had read and found nothing in.
        def mutate(document):
            document["entries"].pop(2)
        self.assert_catches("coverage", mutate)

    def test_the_uncovered_page_is_named(self):
        document = valid_map()
        document["entries"].pop(2)
        code, output = self.run_tool(document)
        self.assertIn("p. 3", output)
        self.assertEqual(code, 1, output)

    def test_a_map_declaring_no_extent_does_not_report_ok(self):
        # What it claims to have read is unstated, so "no entry cites this section" cannot
        # be a fact. This is the state every map was in before 0009.
        document = valid_map()
        document.pop("extent")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "coverage"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 1, output)

    def test_an_extent_in_a_unit_this_checker_cannot_read_reports_not_verified(self):
        # A `section-designation` corpus has no page markers; this tool must decline rather
        # than pass over a claim it did not test.
        document = valid_map()
        document["extent"] = {"unit": "paragraph", "from": 1, "to": 4}
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "coverage"), "skip", output)
        self.assertEqual(code, 1, output)

    def test_an_extent_that_is_not_a_range_reports_not_verified(self):
        document = valid_map()
        document["extent"] = {"unit": "page", "from": 4, "to": 1}
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "coverage"), "skip", output)
        self.assertEqual(code, 1, output)

    def test_coverage_counts_only_pages_a_verified_quote_reached(self):
        # A citation naming a page is not a quote sitting on it. An entry whose evidence
        # cannot be found proves nothing about the page it claims, so `coverage` must not
        # credit it -- otherwise a summary would cover the corpus.
        def mutate(document):
            document["entries"][2]["evidence"] = "The rule about succession."
        self.assert_catches("coverage", mutate)


if __name__ == "__main__":
    unittest.main()
