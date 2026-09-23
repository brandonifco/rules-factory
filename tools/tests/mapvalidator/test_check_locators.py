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

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "check-locators.py")

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

    def assert_catches(self, check, mutate, expect="fail", *, message=None, base=None):
        """The valid map passes this check; the mutation makes this check say `message`.

        `message` is **required** and is a fragment of the refusal the mutation must produce
        ([#283](https://github.com/brandonifco/rules-factory/issues/283)). Asserting only the
        check's verdict was not enough: a check has several rules, and a mutation caught by a
        neighbouring one still shows red, so the test passes while the rule it was written for
        goes unexercised. `extraction`'s "a defect this checker has no test for" mutation does
        exactly that here -- it trips the folio rule as well -- and nothing said so.

        It is keyword-only with no usable default, so the next test cannot be written without one.
        """
        if not message:
            raise AssertionError(
                f"assert_catches({check!r}, ...) names no expected refusal. Assert the message, "
                f"not only the verdict: a neighbouring rule of the same check can satisfy the "
                f"verdict while the rule this test is about goes unexercised (#283)")
        base = base or valid_map
        code, output = self.run_tool(base())
        self.assertEqual(self.status_of(output, check), "ok", output)
        self.assertEqual(code, 0, output)
        document = base()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, check), expect, output)
        self.assertEqual(code, 1, output)
        self.assertIn(message, output,
                      f"the {check!r} check refused the map, but not with the refusal this test "
                      f"names -- another rule of the same check may be doing the work:\n{output}")


class TestTheHelperNamesTheRefusal(LocatorCase):
    """The guard itself, so #283 cannot be undone by writing the next test the old way.

    Mutation: give `message` a default of `""`, or drop the guard. This goes green while a test
    that asserts nothing about the refusal becomes writable again.
    """

    def test_assert_catches_refuses_a_call_that_names_no_refusal(self):
        with self.assertRaises(AssertionError) as caught:
            self.assert_catches("locators", lambda d: d["entries"][2]["locator"].update(
                citation="Part One / p. 2"))
        self.assertIn("names no expected refusal", str(caught.exception))

    def test_a_refusal_from_a_neighbouring_rule_does_not_satisfy_the_test(self):
        """The whole point: the verdict is red, and it is red for the wrong reason."""
        with self.assertRaises(AssertionError) as caught:
            self.assert_catches("locators", lambda d: d["entries"][2]["locator"].update(
                citation="Part One / p. 2"), message="a refusal this mutation does not produce")
        self.assertIn("another rule of the same check may be doing the work", str(caught.exception))


class TestFixtureIsValid(LocatorCase):
    def test_the_valid_map_passes_every_check(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(code, 0, output)
        self.assertNotIn("[fail]", output, output)
        self.assertNotIn("[skip]", output, output)


class TestLocators(LocatorCase):
    def test_a_citation_naming_the_wrong_page_fails(self):
        self.assert_catches(
            "locators", lambda d: d["entries"][2]["locator"].update(citation="Part One / p. 2"),
            message="cited p. 2, evidence is on p. 3")

    def test_evidence_that_is_a_summary_rather_than_a_quote_fails(self):
        # The defect that let thirteen wrong citations survive a build (#18).
        self.assert_catches(
            "locators", lambda d: d["entries"][1].update(evidence="Both elections."),
            message="evidence not found verbatim; cannot check")

    def test_a_citation_naming_no_page_fails(self):
        # What `(absent)` was, before 0009 gave an absence a locator that cites a passage.
        self.assert_catches(
            "locators", lambda d: d["entries"][4]["locator"].update(citation="(absent)"),
            message="names no page, so nothing can be compared")

    def test_a_map_whose_evidence_is_nowhere_in_the_corpus_does_not_report_ok(self):
        document = valid_map()
        for item in document["entries"]:
            item["evidence"] = "A summary of what this entry shows."
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "locators"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 1, output)


class TestDerived(LocatorCase):
    """0012: a derived entry cites nothing, so it is left out of locating -- by name."""

    def _with_derived(self):
        document = valid_map()
        derived = entry("hit-pays-single-stake", "", "",
                        derivedFrom=["player-count", "legal-destination"])
        derived.pop("locator")
        derived.pop("evidence")
        document["entries"].append(derived)
        return document

    def test_a_derived_entry_is_not_located_and_is_named(self):
        code, output = self.run_tool(self._with_derived())
        self.assertEqual(self.status_of(output, "locators"), "ok", output)
        self.assertIn("1 derived entry (hit-pays-single-stake) not located", output)
        self.assertEqual(code, 0, output)

    def test_the_exemption_is_the_field_and_nothing_else(self):
        # Without `derivedFrom` the same entry is an uncited one, and fails like any other.
        document = self._with_derived()
        document["entries"][-1].pop("derivedFrom")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "locators"), "fail", output)
        self.assertEqual(code, 1, output)


class TestAbsence(LocatorCase):
    def test_a_term_the_corpus_actually_contains_fails_the_absence(self):
        # The only check in the repository that goes red by *finding* something.
        self.assert_catches(
            "absence",
            lambda d: d["entries"][4]["absentFrom"]["searched"].append("pair of tokens"),
            message="and the extent contains it")

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
        self.assert_catches("coverage", mutate,
            message="p. 3: inside the declared extent and reached by no entry's verified evidence")

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
        self.assert_catches("coverage", mutate,
            message="p. 3: inside the declared extent and reached by no entry's verified evidence")


# #270: a corpus whose pages hold more than the map quotes, so that "every page is reached" and
# "how much of the extent is quoted" are visibly different numbers. Each page carries one mapped
# sentence and a paragraph of prose nobody quotes; page 1 carries two mapped sentences, so an
# entry can be deleted without leaving its page unreached -- which is exactly the damage
# `drop-entry` does to four of the five committed maps.
QUOTING_CORPUS = """
{1}
A widget is played by two persons with a pair of tokens.
The tokens are made of bone or of boxwood, and the older sets are the heavier ones, which
some players prefer and others do not; the matter has never been settled and is not settled
here, and nothing in this paragraph states a rule about any of it.
Each token is entered at the near end of the board.

{2}
The right to move a token is subject to the number shown.
The number is shown on the upper face, which is the face a player reads, and the lower face
is read by nobody at all; the custom is old and the reason for it is not recorded anywhere
in this volume, so it is repeated here without one and states no rule either.
"""


def quoting_map(**extent):
    """A map reaching both pages of QUOTING_CORPUS and quoting part of each."""
    document = {
        "schemaVersion": 1,
        "corpus": "demo-corpus",
        "baseline": {"contentHash": "a" * 64, "hashDerivation": "demo-plain-text"},
        "extent": {"unit": "page", "from": 1, "to": 2},
        "entries": [
            entry("player-count", "Part One / p. 1",
                  "A widget is played by two persons with a pair of tokens."),
            entry("entry-point", "Part One / p. 1",
                  "Each token is entered at the near end of the board."),
            entry("legal-destination", "Part One / p. 2",
                  "The right to move a token is subject to the number shown."),
        ],
    }
    document["extent"].update(extent)
    return document


class TestQuotedFraction(LocatorCase):
    """#270: `coverage` says how much of the extent the map can show it read, not how many
    pages something touched.

    One quote reaches a page, so an entry can be deleted from a map of 33 entries over ten pages
    and nothing notices. Measured with `drop-entry`: caught on `faa-part-107`, where the dropped
    entry was the only quote in its section, and missed on the other four.

    The fraction is reported on every run. It **fails** a map only against a floor the map
    itself declares, `extent.quoted` -- 0054, and the reason is in this class's last test.
    """

    def setUp(self):
        super().setUp()
        self.quoting_path = os.path.join(self.root, "quoting.txt")
        with open(self.quoting_path, "w", encoding="utf-8") as handle:
            handle.write(QUOTING_CORPUS)

    def run_tool(self, document, corpus_path=None):
        return super().run_tool(document, corpus_path or self.quoting_path)

    def test_the_fraction_is_reported_whether_or_not_the_map_declares_one(self):
        code, output = self.run_tool(quoting_map())
        self.assertEqual(self.status_of(output, "coverage"), "ok", output)
        self.assertIn("verified evidence quotes 24% of it; the map declares no floor", output)
        self.assertEqual(code, 0, output)

    def test_a_map_quoting_less_than_it_declares_fails(self):
        # The harness's `drop-entry`, on a fixture: `entry-point` is deleted, p. 1 is still
        # reached by `player-count`, and `coverage`'s unit rule stays green.
        self.assert_catches("coverage", lambda d: d["entries"].pop(1),
            base=lambda: quoting_map(quoted=0.2),
            message="the map declares its verified evidence quotes at least 20% of the declared "
                    "extent, and it quotes 17%")

    def test_a_map_quoting_at_least_what_it_declares_passes_and_says_so(self):
        code, output = self.run_tool(quoting_map(quoted=0.2))
        self.assertEqual(self.status_of(output, "coverage"), "ok", output)
        self.assertIn("verified evidence quotes 24% of it, above the 20% the map declares", output)
        self.assertEqual(code, 0, output)

    def test_no_threshold_is_imposed_on_a_map_that_declares_none(self):
        # 0054, and the measurement that decided it: across the five committed maps the quoted
        # fraction runs from 20% (`srd-52-conditions`, whose extent is the whole Rules Glossary
        # and whose map is the conditions in it) to 99.9% (`faa-part-107`). No single floor could
        # be right for both, and a threshold nobody argued for would be worse than the number
        # alone -- so the number is reported and the map says what it can be held to.
        code, output = self.run_tool(quoting_map())
        self.assertEqual(code, 0, output)
        self.assertNotIn("[fail]", output)


class TestExtentBounds(LocatorCase):
    """#269: no `scope: in` quote lies outside the declared page range.

    `extent` (check-map.py) places the *citation*; this places the *quote*, which is the other
    thing a page extent bounds and the half a citation cannot carry. 0024 already made exactly
    this statement about the one end a heading can stop: an in-scope quote at or after
    `endsBefore` does not belong to the slice. Both ends of the range are the same fact.

    It is what the harness's `narrow-extent` needs on `hoyle-backgammon`, whose citations run
    271-278 inside a declared 271-280: narrowing the extent by a page moves no citation, and the
    one quote that reaches p. 280 is the only thing that notices.
    """

    def test_an_in_scope_quote_outside_the_declared_range_fails(self):
        # The harness's `narrow-extent`, on this fixture: the map keeps every entry and claims
        # to have read two pages fewer than it quotes.
        self.assert_catches("extent-bounds", lambda d: d["extent"].update(to=2),
            message="next-round-opening: evidence lies on p. 3, outside the declared extent "
                    "(pages 1-2)")

    def test_an_out_of_scope_quote_beyond_the_range_is_named_and_neither_passes_nor_fails(self):
        # 0020's exemption, in the unit a quote is measured in: `strategy-advice` is the
        # fixture's `scope: out` entry and sits on p. 4.
        document = valid_map()
        document["extent"]["to"] = 3
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent-bounds"), "ok", output)
        self.assertIn("1 out-of-scope quote beyond the extent, neither passed nor failed: "
                      "strategy-advice (p. 4)", output)
        self.assertEqual(code, 0, output)

    def test_a_map_declaring_no_page_range_reports_not_verified_and_had_no_subject(self):
        document = valid_map()
        document.pop("extent")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent-bounds"), "skip", output)


# --- examples/faa-part-107/check-locators-section.py: the section-designation grammar -------

SECTION_TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))),
                            "examples", "faa-part-107", "check-locators-section.py")
_section_spec = importlib.util.spec_from_file_location("check_locators_section", SECTION_TOOL)
check_locators_section = importlib.util.module_from_spec(_section_spec)
_section_spec.loader.exec_module(check_locators_section)

# Two sections in the eCFR shape: one with an undesignated lead-in before its paragraphs, and
# one with no designated paragraph at all.
SECTION_CORPUS = """<ROOT><DIV6 N="B" TYPE="SUBPART">
<DIV8 N="1.10" TYPE="SECTION"><HEAD>§ 1.10 Widgets.</HEAD>
<P>Every operator of a widget must comply with all of the following:</P>
<P>(a) The widget may not exceed ten tokens.</P>
<P>(b) The widget may not be operated at night.</P>
</DIV8>
<DIV8 N="1.11" TYPE="SECTION"><HEAD>§ 1.11 Tokens.</HEAD>
<P>No person may carry a token into a restricted area.</P>
</DIV8>
</DIV6></ROOT>"""

LEAD_IN_TEXT = "Every operator of a widget must comply with all of the following:"


def section_map():
    """A map whose citations and extent hold against SECTION_CORPUS."""
    return {
        "schemaVersion": 1,
        "corpus": "demo-cfr",
        "baseline": {"contentHash": "b" * 64, "hashDerivation": "demo-xml"},
        "extent": {"unit": "section-designation", "sections": ["§ 1.10", "§ 1.11"]},
        "entries": [
            entry("widget-compliance", "§ 1.10 introductory text", LEAD_IN_TEXT),
            entry("token-limit", "§ 1.10(a)", "(a) The widget may not exceed ten tokens."),
            entry("token-area", "§ 1.11", "No person may carry a token into a restricted area."),
        ],
    }


class SectionCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.corpus_path = os.path.join(self.root, "corpus.xml")
        with open(self.corpus_path, "w", encoding="utf-8") as handle:
            handle.write(SECTION_CORPUS)
        self.corpus, self.spans, _, _ = check_locators_section.corpus_index(self.corpus_path)

    def verdict(self, citation, evidence):
        return check_locators_section.check(entry("x", citation, evidence), self.corpus, self.spans)[0]

    def run_tool(self, document):
        path = os.path.join(self.root, "corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = check_locators_section.main(["check-locators-section.py", path, self.corpus_path])
        return code, out.getvalue()


class TestIntroductoryText(SectionCase):
    """0020: "introductory text" names a section's undesignated lead-in, and only that."""

    def test_a_lead_in_cited_as_introductory_text_is_verified(self):
        self.assertEqual(self.verdict("§ 1.10 introductory text", LEAD_IN_TEXT), "ok")

    def test_the_bare_section_still_covers_its_lead_in(self):
        self.assertEqual(self.verdict("§ 1.10", LEAD_IN_TEXT), "ok")

    def test_a_designated_paragraph_cited_as_introductory_text_fails(self):
        self.assertEqual(
            self.verdict("§ 1.10 introductory text", "(a) The widget may not exceed ten tokens."), "bad")

    def test_a_quote_running_past_the_lead_in_fails_as_introductory_text_alone(self):
        evidence = LEAD_IN_TEXT + " (a) The widget may not exceed ten tokens."
        self.assertEqual(self.verdict("§ 1.10 introductory text", evidence), "bad")
        self.assertEqual(self.verdict("§ 1.10 introductory text, (a)", evidence), "ok")

    def test_a_section_with_no_designated_paragraph_has_no_introductory_text(self):
        self.assertEqual(self.verdict(
            "§ 1.11 introductory text", "No person may carry a token into a restricted area."), "bad")

    def test_a_paragraphs_own_introductory_text_is_outside_the_grammar(self):
        self.assertIsNone(check_locators_section.cited_paths("§ 1.10(a) introductory text"))
        self.assertEqual(self.verdict(
            "§ 1.10(a) introductory text", "(a) The widget may not exceed ten tokens."), "unchecked")


class TestSectionCoverage(SectionCase):
    """0020: every section of a section-designation extent is reached by a verified quote."""

    def test_the_valid_map_passes(self):
        code, output = self.run_tool(section_map())
        self.assertEqual(code, 0, output)
        self.assertIn("coverage ok (all 2 sections", output)

    def test_a_section_no_entry_reaches_fails_and_is_named(self):
        document = section_map()
        document["entries"].pop(2)
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("§ 1.11: inside the declared extent", output)

    def test_a_citation_naming_a_section_is_not_a_quote_reaching_it(self):
        document = section_map()
        document["entries"][2]["evidence"] = "A summary of the token rule."
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("§ 1.11: inside the declared extent", output)

    def test_a_map_declaring_no_extent_fails(self):
        document = section_map()
        document.pop("extent")
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("declares no `extent`", output)

    def test_an_extent_in_pages_fails(self):
        document = section_map()
        document["extent"] = {"unit": "page", "from": 1, "to": 2}
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)

    def test_the_quoted_fraction_of_the_sections_is_reported(self):
        # #270: a section extent is not finer than a page one -- `§ 1.121-1` is one section and
        # the whole tax-121 map lies inside it -- so the same measure is owed here. The unit is
        # the section; the fraction is of its text.
        code, output = self.run_tool(section_map())
        self.assertEqual(code, 0, output)
        self.assertIn("verified evidence quotes 78% of their text", output)

    def test_a_map_quoting_less_of_its_sections_than_it_declares_fails(self):
        # The harness's `drop-entry`: `token-limit` goes, § 1.10 is still reached by the lead-in
        # entry, and `coverage`'s section rule stays green while a rule has gone missing.
        document = section_map()
        document["extent"]["quoted"] = 0.7
        code, output = self.run_tool(document)
        self.assertEqual(code, 0, output)
        document["entries"].pop(1)
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("extent.quoted: the map declares its verified evidence quotes at least "
                      "70% of the declared extent, and it quotes 58%", output)
        self.assertNotIn("§ 1.10: inside the declared extent", output)


# --- a rule stated in a table row (0035) ----------------------------------------------------
# The same eCFR shape with two tables in one section. The first prints its columns the way the
# corpus that forced this prints them -- a (4) heading split into (4A) and (4B), so the columns
# are the leaves and not the six labels -- has an empty cell in column 1 of its first row, and
# two rows a column 2 key alone cannot tell apart. The second is the shape that needs a key of
# three cells: every value of its first row is printed in another row too, and so is every pair
# of them. Synthetic, like every fixture here -- and identical to the one
# `tools/tests/mapper/test_mapper_table_rows.py` writes, which is how the two implementations are
# held to the same reading. The real corpus is trial 10's to admit, not this test's.
TABLE_CORPUS = """<ROOT><DIV6 N="B" TYPE="SUBPART">
<DIV8 N="1.10" TYPE="SECTION"><HEAD>§ 1.10 Widget table.</HEAD>
<P>Each widget is listed in the widget table with the class and the packing it requires.</P>
<P>(a) Column 1 states the symbol, column 2 the widget name and column 3 the class.</P>
<DIV><TABLE>
<THEAD><TR><TD>(1) Symbols</TD><TD>(2) Widget name</TD><TD>(3) Class</TD><TD>(4) Packing</TD>
<TD>(4A) Exceptions</TD><TD>(4B) Non-bulk</TD></TR></THEAD>
<TBODY>
<TR><TD/><TD>Acetal</TD><TD>3</TD><TD>150</TD><TD>202</TD></TR>
<TR><TD>G</TD><TD>Ammonia, anhydrous</TD><TD>2.2</TD><TD/><TD>306</TD></TR>
<TR><TD>G</TD><TD>Ammonia, anhydrous</TD><TD>2.3</TD><TD>T4</TD><TD>314</TD></TR>
</TBODY></TABLE></DIV>
<TABLE><THEAD><TR><TD>(1) Code</TD><TD>(2) Mode</TD><TD>(3) Limit</TD></TR></THEAD>
<TBODY>
<TR><TD>A3</TD><TD>Aircraft</TD><TD>5 L</TD></TR>
<TR><TD>A3</TD><TD>Aircraft</TD><TD>60 L</TD></TR>
<TR><TD>A3</TD><TD>Vessel</TD><TD>5 L</TD></TR>
<TR><TD>N34</TD><TD>Aircraft</TD><TD>5 L</TD></TR>
</TBODY></TABLE>
</DIV8>
<DIV8 N="1.11" TYPE="SECTION"><HEAD>§ 1.11 Tokens.</HEAD>
<P>No person may carry a token into a restricted area.</P>
</DIV8>
</DIV6></ROOT>"""

ACETAL_ROW = "| Acetal | 3 | 150 | 202"
AMMONIA_22_ROW = "G | Ammonia, anhydrous | 2.2 | | 306"

# Ten numbered columns with the last split -- the § 172.101 shape, where `10A` is a sub-column
# of `10` and `1` is a sub-column of nothing -- and a table whose cells span, which carries no
# column geometry at all.
WIDE_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Symbols</TD><TD>(2) Name</TD><TD>(3) Class</TD><TD>(4) ID</TD><TD>(5) PG</TD>
<TD>(6) Label</TD><TD>(7) Provisions</TD><TD>(8) Packaging</TD><TD>(9) Quantity</TD>
<TD>(10) Vessel</TD><TD>(10A) Location</TD><TD>(10B) Other</TD></TR></THEAD>
<TBODY><TR><TD/><TD>Acetal</TD><TD>3</TD><TD>UN1088</TD><TD>II</TD><TD>3</TD><TD>IB2</TD>
<TD>202</TD><TD>5 L</TD><TD>E</TD><TD>D</TD></TR></TBODY></TABLE>"""

TWO_LEVEL_TABLE = """<TABLE>
<THEAD>
<TR><TH ROWSPAN="2">(1)Symbols</TH><TH ROWSPAN="2">(2)Hazardous materials descriptions and \
proper shipping names</TH><TH ROWSPAN="2">(3)Hazard class or Division</TH>
<TH ROWSPAN="2">(4)Identification Numbers</TH><TH ROWSPAN="2">(5)PG</TH>
<TH ROWSPAN="2">(6)Label codes</TH><TH ROWSPAN="2">(7)Special provisions(§ 172.102)</TH>
<TH COLSPAN="3">(8)Packaging(§ 173.***)</TH><TH COLSPAN="2">(9)Quantity limitations</TH>
<TH COLSPAN="2">(10)Vesselstowage</TH></TR>
<TR><TH>Exceptions(8A)</TH><TH>Non-bulk(8B)</TH><TH>Bulk(8C)</TH>
<TH>Passenger aircraft/rail(9A)</TH><TH>Cargo aircraft only(9B)</TH><TH>Location(10A)</TH>
<TH>Other(10B)</TH></TR>
</THEAD>
<TBODY>
<TR><TD/><TD>Acetal</TD><TD>3</TD><TD>UN1088</TD><TD>II</TD><TD>3</TD><TD>IB2, T4, TP1</TD>
<TD>150</TD><TD>202</TD><TD>242</TD><TD>5 L</TD><TD>60 L</TD><TD>E</TD><TD/></TR>
<TR><TD>D</TD><TD>Acetaldehyde</TD><TD>3</TD><TD>UN1089</TD><TD>I</TD><TD>3</TD><TD>A3, T11</TD>
<TD>None</TD><TD>201</TD><TD>243</TD><TD>Forbidden</TD><TD>30 L</TD><TD>E</TD><TD/></TR>
</TBODY></TABLE>"""

# A span in a *body* row: the markup then genuinely stops saying which column a later cell is in.
FOOTNOTE_MARKER_TABLE = """<TABLE>
<THEAD><TR><TD>Minimum test pressure (2)</TD><TD>Widget (3)</TD></TR></THEAD>
<TBODY><TR><TD>4 bar</TD><TD>Acetal</TD></TR></TBODY></TABLE>"""

SPANNED_BODY_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Code</TD><TD>(2) Mode</TD><TD>(3) Limit</TD></TR></THEAD>
<TBODY><TR><TD COLSPAN="2">A3, aircraft</TD><TD>5 L</TD></TR></TBODY></TABLE>"""

# A colspan parent with no second heading row under it: the two columns it covers are both
# labelled `(8)`, which names neither, so the table is numbered by position.
SPANNED_TABLE = """<TABLE>
<THEAD><TR><TD COLSPAN="2">(8) Packaging</TD><TD>(9) Quantity</TD></TR></THEAD>
<TBODY><TR><TD>202</TD><TD>242</TD><TD>5 L</TD></TR></TBODY></TABLE>"""

# A heading that names two columns at once, and one that names none while its neighbours do.
CROWDED_HEADING_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Code and (2) Mode</TD><TD>(3) Limit</TD></TR></THEAD>
<TBODY><TR><TD>A3</TD><TD>5 L</TD></TR></TBODY></TABLE>"""

HALF_NUMBERED_TABLE = """<TABLE>
<THEAD><TR><TD>Widget</TD><TD>(2) Class</TD></TR></THEAD>
<TBODY><TR><TD>Acetal</TD><TD>3</TD></TR></TBODY></TABLE>"""


class TestTableRows(unittest.TestCase):
    """0035: a citation reaches a row, a row is named by a cell, and two matches is a refusal."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.corpus_path = os.path.join(self.root, "corpus.xml")
        with open(self.corpus_path, "w", encoding="utf-8") as handle:
            handle.write(TABLE_CORPUS)
        self.corpus, self.spans, _, _ = check_locators_section.corpus_index(self.corpus_path)
        self.tables = check_locators_section.table_index(self.corpus_path)

    def verdict(self, citation, evidence):
        return check_locators_section.check(
            entry("x", citation, evidence), self.corpus, self.spans, None, self.tables)[0]

    def test_the_columns_are_the_ones_the_headings_print(self):
        # (4) is split into (4A) and (4B), so it names no column of its own.
        self.assertEqual(self.tables[("1.10", 1)].columns, ["1", "2", "3", "4A", "4B"])

    def test_a_row_is_reached_by_a_cell_that_identifies_it(self):
        self.assertEqual(
            self.verdict('§ 1.10 table 1, row [column 2 = "Acetal"]', ACETAL_ROW), "ok")

    def test_an_empty_cell_is_in_the_row_and_can_be_quoted(self):
        self.assertEqual(self.verdict(
            '§ 1.10 table 1, row [column 2 = "Ammonia, anhydrous"; column 3 = "2.2"]',
            AMMONIA_22_ROW), "ok")

    def test_a_key_that_names_two_rows_is_refused_and_not_resolved_to_the_first(self):
        result, message = check_locators_section.check(
            entry("x", '§ 1.10 table 1, row [column 2 = "Ammonia, anhydrous"]', AMMONIA_22_ROW),
            self.corpus, self.spans, None, self.tables)
        self.assertEqual(result, "bad", message)
        self.assertIn("names 2 rows", message)

    def test_a_discriminating_column_settles_it(self):
        self.assertEqual(self.verdict(
            '§ 1.10 table 1, row [column 2 = "Ammonia, anhydrous"; column 3 = "2.3"]',
            "G | Ammonia, anhydrous | 2.3 | T4 | 314"), "ok")

    def test_a_quote_from_another_row_fails(self):
        self.assertEqual(self.verdict(
            '§ 1.10 table 1, row [column 2 = "Acetal"]', AMMONIA_22_ROW), "bad")

    def test_a_cell_is_named_by_its_column(self):
        self.assertEqual(
            self.verdict('§ 1.10 table 1, row [column 2 = "Acetal"], column 4A', "150"), "ok")

    def test_a_quote_from_a_different_column_of_the_same_row_fails(self):
        self.assertEqual(
            self.verdict('§ 1.10 table 1, row [column 2 = "Acetal"], column 4A', "202"), "bad")

    def test_a_column_the_table_does_not_print_is_named_as_the_defect(self):
        # It fails either way -- no row holds a column that is not there -- and "no such column"
        # and "no such row" are different findings, so the run has to say which it is.
        result, message = check_locators_section.check(
            entry("x", '§ 1.10 table 1, row [column 9 = "Acetal"]', ACETAL_ROW),
            self.corpus, self.spans, None, self.tables)
        self.assertEqual(result, "bad", message)
        self.assertIn("prints no column 9", message)

    def test_a_table_the_section_does_not_print_fails(self):
        result, message = check_locators_section.check(
            entry("x", '§ 1.10 table 3, row [column 2 = "Acetal"]', ACETAL_ROW),
            self.corpus, self.spans, None, self.tables)
        self.assertEqual(result, "bad", message)
        self.assertIn("prints no table 3", message)

    def test_the_second_table_is_numbered_by_its_position_in_the_section(self):
        self.assertEqual(self.verdict(
            '§ 1.10 table 2, row [column 1 = "N34"]', "N34 | Aircraft | 5 L"), "ok")

    def test_a_row_of_the_second_table_needs_all_three_of_its_cells(self):
        # Every single value of this row, and every pair, is printed in another row too. Two
        # matches is a refusal; three predicates name the row.
        self.assertEqual(self.verdict(
            '§ 1.10 table 2, row [column 1 = "A3"; column 2 = "Aircraft"]',
            "A3 | Aircraft | 5 L"), "bad")
        self.assertEqual(self.verdict(
            '§ 1.10 table 2, row [column 1 = "A3"; column 2 = "Aircraft"; column 3 = "5 L"]',
            "A3 | Aircraft | 5 L"), "ok")

    def test_a_heading_row_is_citable(self):
        # 0035: the column semantics of a regulation live in its headings, printed once for
        # every row of the table, and a map has to be able to cite them.
        self.assertEqual(self.verdict(
            '§ 1.10 table 1, row [column 1 = "(1) Symbols"]',
            "(1) Symbols | (2) Widget name | (3) Class"), "ok")

    def test_a_row_quote_that_elides_its_middle_is_refused(self):
        # corpus-map.md: `evidence` is one contiguous span. A row is short and its point is
        # which cell holds what, so an ellipsis inside one drops a column nothing then checks.
        result, message = check_locators_section.check(
            entry("x", '§ 1.10 table 1, row [column 2 = "Acetal"]', "| Acetal ... 202"),
            self.corpus, self.spans, None, self.tables)
        self.assertEqual(result, "bad", message)
        self.assertIn("elides its middle", message)

    def test_a_label_is_read_wherever_the_heading_prints_it(self):
        # The parents are prefixes, the children suffixes: `Exceptions(8A)`. Anchoring the token
        # at the start of the cell finds none of the children.
        self.assertEqual(check_locators_section.COLUMN_LABEL.findall("Exceptions(8A)"), ["8A"])
        self.assertEqual(check_locators_section.COLUMN_LABEL.findall(
            "(7)Special provisions(§ 172.102)"), ["7"])

    def test_a_column_of_a_ten_way_table_is_not_swallowed_by_column_one(self):
        # Read as a string prefix, `1` is a parent of `10A`: the labels stop numbering the cells,
        # the table silently falls back to positional numbering, and `column 9` addresses another
        # column's cell. This is the § 172.101 shape.
        table = check_locators_section.Table("1.10", 1, ET.fromstring(WIDE_TABLE))
        self.assertEqual(table.numbering, "printed")
        self.assertEqual(table.index_of("10B"), 10)
        self.assertEqual(table.columns[8], "9")

    def test_a_table_whose_geometry_the_markup_does_not_carry_addresses_nothing(self):
        tables = {("1.10", 1): check_locators_section.Table(
            "1.10", 1, ET.fromstring(SPANNED_BODY_TABLE))}
        result, message = check_locators_section.check(
            entry("x", '§ 1.10 table 1, row [column 3 = "5 L"]', "A3, aircraft | 5 L"),
            self.corpus, self.spans, None, tables)
        self.assertEqual(result, "bad", message)
        self.assertIn("told apart by column", message)

    def test_a_citation_into_a_table_numbered_by_position_says_so(self):
        # A table that prints a footnote marker where a column number would be is numbered by
        # position, and the run says which numbering it used and why, rather than leaving a
        # reader to assume the corpus's own.
        tables = {("1.10", 1): check_locators_section.Table(
            "1.10", 1, ET.fromstring(FOOTNOTE_MARKER_TABLE))}
        result, message = check_locators_section.check(
            entry("x", '§ 1.10 table 1, row [column 9 = "4 bar"]', "4 bar"),
            self.corpus, self.spans, None, tables)
        self.assertEqual(result, "bad", message)
        self.assertIn("numbered positional", message)
        self.assertIn("and not (1)", message)

    def test_a_two_level_heading_resolves_a_citation_into_its_own_column(self):
        # The Hazardous Materials Table's heading, and the reason this decision exists: a
        # citation naming column 9A must reach the passenger-aircraft cell and nothing else.
        tables = {("1.10", 1): check_locators_section.Table(
            "1.10", 1, ET.fromstring(TWO_LEVEL_TABLE))}

        def verdict(citation, evidence):
            return check_locators_section.check(
                entry("x", citation, evidence), self.corpus, self.spans, None, tables)

        self.assertEqual(verdict(
            '§ 1.10 table 1, row [column 2 = "Acetal"], column 9A', "5 L")[0], "ok")
        self.assertEqual(verdict(
            '§ 1.10 table 1, row [column 2 = "Acetal"], column 9B', "60 L")[0], "ok")
        self.assertEqual(verdict(
            '§ 1.10 table 1, row [column 2 = "Acetal"], column 8B', "202")[0], "ok")
        # 9A is not 9B, and the quote is held to the cell the citation names.
        self.assertEqual(verdict(
            '§ 1.10 table 1, row [column 2 = "Acetal"], column 9A', "60 L")[0], "bad")
        # `9` is a split parent: it names no column at all.
        result, message = verdict(
            '§ 1.10 table 1, row [column 2 = "Acetal"], column 9', "5 L")
        self.assertEqual(result, "bad", message)
        self.assertIn("prints no column 9", message)

    def test_a_corpus_that_prints_a_section_twice_is_refused(self):
        path = os.path.join(self.root, "twice.xml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(TABLE_CORPUS.replace(
                "</DIV6></ROOT>",
                '<DIV8 N="1.11" TYPE="SECTION"><HEAD>§ 1.11 Again.</HEAD>'
                "<P>A second printing of the same designation.</P></DIV8></DIV6></ROOT>"))
        with self.assertRaises(check_locators_section.Duplicated) as caught:
            check_locators_section.table_index(path)
        self.assertIn("prints § 1.11 twice", str(caught.exception))

    def test_a_run_that_indexed_no_table_does_not_report_ok(self):
        result, message = check_locators_section.check(
            entry("x", '§ 1.10 table 1, row [column 2 = "Acetal"]', ACETAL_ROW),
            self.corpus, self.spans)
        self.assertEqual(result, "unchecked", message)

    def test_a_row_citation_reaches_its_section_for_coverage(self):
        document = {
            "schemaVersion": 1, "corpus": "demo-cfr",
            "baseline": {"contentHash": "d" * 64, "hashDerivation": "demo-xml"},
            "extent": {"unit": "section-designation", "sections": ["§ 1.10", "§ 1.11"]},
            "entries": [
                entry("acetal-packing", '§ 1.10 table 1, row [column 2 = "Acetal"]', ACETAL_ROW),
                entry("token-area", "§ 1.11",
                      "No person may carry a token into a restricted area."),
            ],
        }
        path = os.path.join(self.root, "corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = check_locators_section.main(
                ["check-locators-section.py", path, self.corpus_path])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("coverage ok (all 2 sections", out.getvalue())


# --- examples/srd-52-combat/check-locators-pdf-text.py: page-marked PDF text ----------------

PDF_TEXT_TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))),
                             "examples", "srd-52-combat", "check-locators-pdf-text.py")
_pdf_text_spec = importlib.util.spec_from_file_location("check_locators_pdf_text", PDF_TEXT_TOOL)
check_locators_pdf_text = importlib.util.module_from_spec(_pdf_text_spec)
_pdf_text_spec.loader.exec_module(check_locators_pdf_text)

# The shape pdftotext gives: a {N} marker line per physical page, headings as lines of their own,
# a folio and running header left mid-page, and one sentence repeated on a later page.
PDF_TEXT_CORPUS = """{1}
Widgets
A widget is played by two persons.
Tokens
Each token moves once per round,
1

Demo Reference Document

and never twice.
{2}
Rounds
The winner of a round moves first.

Scoring

A game is scored when it ends.
{3}
Glossary
Each token moves once per round,

Score

Win

One point

Gammon

Two points
"""


def pdf_text_map():
    return {
        "schemaVersion": 1,
        "corpus": "demo-pdf",
        "baseline": {"contentHash": "c" * 64, "hashDerivation": "demo-pdftotext"},
        "extent": {"unit": "page", "from": 1, "to": 2},
        "entries": [
            entry("players", "Widgets / p. 1", "A widget is played by two persons."),
            entry("token-moves", "Widgets / Tokens / p. 1",
                  "Each token moves once per round, 1 Demo Reference Document and never twice.",
                  # 0024: the folio and running header sit mid-sentence, and the entry says so.
                  extraction={"defect": "interrupted-by-page-furniture",
                              "renderedReading": "Each token moves once per round, and never twice."}),
            entry("winner-first", "Widgets / Rounds / p. 2", "The winner of a round moves first."),
        ],
    }


class TestPdfTextLocators(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.corpus_path = os.path.join(self.root, "corpus.txt")
        self.write_corpus(PDF_TEXT_CORPUS)

    def write_corpus(self, text):
        with open(self.corpus_path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def run_tool(self, document):
        path = os.path.join(self.root, "corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = check_locators_pdf_text.main([path, self.corpus_path])
        return code, out.getvalue()

    def test_a_map_that_agrees_passes(self):
        code, output = self.run_tool(pdf_text_map())
        self.assertEqual(code, 0, output)
        self.assertIn("[ok] locators", output)
        self.assertIn("[ok] coverage", output)

    def test_a_wrong_page_fails(self):
        document = pdf_text_map()
        document["entries"][2]["locator"]["citation"] = "Widgets / Rounds / p. 1"
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("winner-first: cited p. 1, evidence is on p. 2", output)

    def test_a_quote_matching_only_as_a_prefix_fails(self):
        # tools/check-locators.py would accept the first five words; this checker requires all.
        document = pdf_text_map()
        document["entries"][0]["evidence"] = "A widget is played by two persons and a referee."
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("players: evidence does not occur", output)

    def test_a_repeated_quote_is_identified_by_its_heading_path(self):
        # 0030, #207: the sentence is printed again on p. 3, under a different heading. The
        # citation names the heading the p. 1 printing sits under, and that is what identifies it.
        document = pdf_text_map()
        document["entries"].append(entry("token-moves-once", "Widgets / Tokens / p. 1",
                                         "Each token moves once per round,"))
        code, output = self.run_tool(document)
        self.assertEqual(code, 0, output)
        self.assertIn("1 of them printed off the cited page too and identified by the heading path",
                      output)

    def test_a_repeated_quote_whose_path_selects_another_printing_fails(self):
        # The heading resolves, and to the wrong page: a refusal, not a pass on the other copy.
        document = pdf_text_map()
        document["entries"].append(entry("token-moves-once", "Glossary / p. 1",
                                         "Each token moves once per round,"))
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("token-moves-once: cited p. 1, evidence is on p. 3", output)

    def test_a_heading_not_near_the_quote_fails(self):
        document = pdf_text_map()
        document["entries"][0]["locator"]["citation"] = "Glossary / p. 1"
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("heading 'Glossary' does not occur", output)

    def test_a_page_the_extent_claims_and_no_quote_reaches_fails(self):
        document = pdf_text_map()
        document["entries"].pop(2)
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("p. 2: inside the declared extent", output)

    def test_an_in_scope_quote_outside_the_declared_range_fails(self):
        # #269, in the second page grammar: the same `narrow-extent` damage, and `coverage` goes
        # green on the narrower range rather than red.
        output = self.assert_catches("extent-bounds", lambda d: d["extent"].update(to=1),
            message="winner-first: evidence lies on p. 2, outside the declared extent (pages 1-1)")
        self.assertEqual(self.status_of(output, "coverage"), "ok", output)

    def test_a_quote_past_the_ends_before_heading_is_extent_ends_alone(self):
        # #283: `extent-end` (0024) already refuses a quote past the heading, and the pages
        # `extent-bounds` is given are the pages `coverage` was given, so it does not refuse the
        # same quote a second time under a second name.
        document = ending_map()
        document["entries"].append(scoring())
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertEqual(self.status_of(output, "extent-end"), "fail", output)
        self.assertEqual(self.status_of(output, "extent-bounds"), "ok", output)

    def test_markers_out_of_sequence_are_a_usage_error(self):
        self.write_corpus(PDF_TEXT_CORPUS.replace("{2}", "{4}"))
        code, output = self.run_tool(pdf_text_map())
        self.assertEqual(code, 2, output)
        self.assertIn("page marker 4 where 2 was expected", output)

    def status_of(self, output, check):
        found = re.search(rf"^\[(ok|fail|skip)\] {re.escape(check)}:", output, re.M)
        self.assertIsNotNone(found, f"check {check!r} did not report at all:\n{output}")
        return found.group(1)

    def assert_catches(self, check, mutate, base=pdf_text_map, *, message=None):
        """The valid map passes this check; the mutation makes this check say `message`.

        `message` is **required** and is a fragment of the refusal the mutation must produce
        ([#283](https://github.com/brandonifco/rules-factory/issues/283)). Asserting only the
        check's verdict was not enough: a check has several rules, and a mutation caught by a
        neighbouring one still shows red, so the test passes while the rule it was written for
        goes unexercised. `extraction`'s "a defect this checker has no test for" mutation does
        exactly that here -- it trips the folio rule as well -- and nothing said so.

        It is keyword-only with no usable default, so the next test cannot be written without one.
        """
        if not message:
            raise AssertionError(
                f"assert_catches({check!r}, ...) names no expected refusal. Assert the message, "
                f"not only the verdict: a neighbouring rule of the same check can satisfy the "
                f"verdict while the rule this test is about goes unexercised (#283)")
        code, output = self.run_tool(base())
        self.assertEqual(self.status_of(output, check), "ok", output)
        self.assertEqual(code, 0, output)
        document = base()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, check), "fail", output)
        self.assertEqual(code, 1, output)
        self.assertIn(message, output,
                      f"the {check!r} check refused the map, but not with the refusal this test "
                      f"names -- another rule of the same check may be doing the work:\n{output}")
        return output


def ending_map():
    """pdf_text_map with an extent that stops at the "Scoring" heading on its last page (0024)."""
    document = pdf_text_map()
    document["extent"]["endsBefore"] = "Scoring"
    return document


def scoring(**overrides):
    return entry("scoring", "Scoring / p. 2", "A game is scored when it ends.", **overrides)


class TestPdfTextExtentEnd(TestPdfTextLocators):
    """0024: a page extent ending before a heading on its last page."""

    def test_an_extent_ending_before_a_heading_passes(self):
        code, output = self.run_tool(ending_map())
        self.assertEqual(code, 0, output)
        self.assertIn("[ok] extent-end: the extent ends before 'Scoring', a line on p. 2", output)

    def test_without_ends_before_the_check_has_nothing_to_hold(self):
        code, output = self.run_tool(pdf_text_map())
        self.assertEqual(self.status_of(output, "extent-end"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_an_in_scope_quote_after_the_heading_fails(self):
        output = self.assert_catches("extent-end", lambda d: d["entries"].append(scoring()),
                                     base=ending_map,
            message="its quote lies after the heading")
        self.assertIn("scoring: is scope: in, and its quote lies after the heading 'Scoring'", output)

    def test_an_in_scope_quote_running_across_the_heading_fails(self):
        output = self.assert_catches("extent-end", lambda d: d["entries"].append(entry(
            "rounds-and-scoring", "Widgets / Rounds / p. 2",
            "The winner of a round moves first. Scoring A game is scored when it ends.")),
            base=ending_map,
            message="its quote runs across the heading")
        self.assertIn("its quote runs across the heading", output)

    def test_an_out_of_scope_quote_after_the_heading_is_named_and_passes(self):
        document = ending_map()
        document["entries"].append(scoring(scope="out", status="declined"))
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent-end"), "ok", output)
        self.assertIn("1 out-of-scope quote beyond it, neither passed nor failed: scoring", output)
        self.assertEqual(code, 0, output)

    def test_a_heading_not_on_the_last_page_fails(self):
        output = self.assert_catches("extent-end", lambda d: d["extent"].update(endsBefore="Glossary"),
                                     base=ending_map,
            message="does not occur as a line of its own")
        self.assertIn("does not occur as a line of its own on p. 2", output)

    def test_a_heading_only_inside_a_sentence_fails(self):
        self.assert_catches("extent-end", lambda d: d["extent"].update(endsBefore="a round"),
                            base=ending_map,
            message="does not occur as a line of its own")

    def test_a_heading_twice_on_the_last_page_fails(self):
        code, output = self.run_tool(ending_map())
        self.assertEqual(code, 0, output)
        self.write_corpus(PDF_TEXT_CORPUS.replace("Rounds\n", "Scoring\nRounds\n"))
        code, output = self.run_tool(ending_map())
        self.assertEqual(self.status_of(output, "extent-end"), "fail", output)
        self.assertIn("occurs 2 times as a line on p. 2", output)

    def test_a_quote_after_the_heading_does_not_cover_the_last_page(self):
        def only_scoring_on_the_last_page(document):
            document["entries"].pop(2)
            document["entries"].append(scoring(scope="out", status="declined"))
        document = pdf_text_map()
        only_scoring_on_the_last_page(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "coverage"), "ok", output)
        document = ending_map()
        only_scoring_on_the_last_page(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "coverage"), "fail", output)
        self.assertIn("p. 2: inside the declared extent", output)

    def test_absence_is_searched_only_up_to_the_heading(self):
        def absent(document):
            document["entries"].append(entry("scoring-rule", "Widgets / Rounds / p. 2",
                                             "The winner of a round moves first.", scope="out",
                                             status="declined", absentFrom={"searched": ["scored"]}))
        document = ending_map()
        absent(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "absence"), "ok", output)
        document = pdf_text_map()
        absent(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "absence"), "fail", output)

    def test_the_page_checker_refuses_an_extent_it_cannot_end(self):
        # tools/check-locators.py collapses lines, so it cannot find the heading; it says so.
        path = os.path.join(self.root, "hoyle-like.json")
        document = valid_map()
        document["extent"]["endsBefore"] = "Scoring"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        corpus = os.path.join(self.root, "hoyle-like.txt")
        with open(corpus, "w", encoding="utf-8") as handle:
            handle.write(CORPUS)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = check_locators.main([path, corpus])
        self.assertIn("[skip] extent-end: NOT VERIFIED", out.getvalue())
        self.assertEqual(code, 1, out.getvalue())


def starting_map():
    """pdf_text_map with an extent that begins after the "Tokens" heading on p. 1 (0064).

    `players` goes with it: its quote is printed above that heading, so a map declaring this
    extent and keeping that entry is the thing `extent-start` exists to refuse, and a base fixture
    that already fails the check it is the base for proves nothing.
    """
    document = pdf_text_map()
    document["extent"]["startsAfter"] = "Tokens"
    document["entries"] = [e for e in document["entries"] if e["id"] != "players"]
    return document


def players(**overrides):
    return entry("players", "Widgets / p. 1", "A widget is played by two persons.", **overrides)


class TestPdfTextExtentStart(TestPdfTextLocators):
    """0064: a page extent starting after a heading on its first page -- `extent-end` mirrored.

    The mirror is what makes two maps of one page complementary: trial 7's combat map ends before
    `Damage and Healing` on p. 16, and the map of the rest of the chapter starts after the same
    line. The heading belongs to neither, which is the one thing about this that is not a mirror
    and is said out loud in 0064.
    """

    def test_an_extent_starting_after_a_heading_passes(self):
        code, output = self.run_tool(starting_map())
        self.assertEqual(code, 0, output)
        self.assertIn("[ok] extent-start: the extent starts after 'Tokens', a line on p. 1", output)

    def test_without_starts_after_the_check_has_nothing_to_hold(self):
        code, output = self.run_tool(pdf_text_map())
        self.assertEqual(self.status_of(output, "extent-start"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_an_in_scope_quote_before_the_heading_fails(self):
        output = self.assert_catches("extent-start", lambda d: d["entries"].append(players()),
                                     base=starting_map,
            message="its quote lies before the heading")
        self.assertIn("players: is scope: in, and its quote lies before the heading 'Tokens'", output)

    def test_an_in_scope_quote_running_across_the_heading_fails(self):
        output = self.assert_catches("extent-start", lambda d: d["entries"].append(entry(
            "players-and-tokens", "Widgets / p. 1",
            "A widget is played by two persons. Tokens Each token moves once per round,")),
            base=starting_map,
            message="its quote runs across the heading")
        self.assertIn("its quote runs across the heading", output)

    def test_an_out_of_scope_quote_before_the_heading_is_named_and_passes(self):
        document = starting_map()
        document["entries"].append(players(scope="out", status="declined"))
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent-start"), "ok", output)
        self.assertIn("1 out-of-scope quote before it, neither passed nor failed: players", output)
        self.assertEqual(code, 0, output)

    def test_a_heading_not_on_the_first_page_fails(self):
        output = self.assert_catches("extent-start",
                                     lambda d: d["extent"].update(startsAfter="Scoring"),
                                     base=starting_map,
            message="does not occur as a line of its own")
        self.assertIn("does not occur as a line of its own on p. 1", output)

    def test_a_heading_only_inside_a_sentence_fails(self):
        self.assert_catches("extent-start",
                            lambda d: d["extent"].update(startsAfter="two persons"),
                            base=starting_map,
            message="does not occur as a line of its own")

    def test_a_heading_twice_on_the_first_page_fails(self):
        code, output = self.run_tool(starting_map())
        self.assertEqual(code, 0, output)
        self.write_corpus(PDF_TEXT_CORPUS.replace("Widgets\n", "Tokens\nWidgets\n", 1))
        code, output = self.run_tool(starting_map())
        self.assertEqual(self.status_of(output, "extent-start"), "fail", output)
        self.assertIn("occurs 2 times as a line on p. 1", output)

    def test_a_quote_before_the_heading_does_not_cover_the_first_page(self):
        def only_players_on_the_first_page(document):
            document["entries"] = [e for e in document["entries"] if e["id"] != "token-moves"]
            document["entries"].append(players(scope="out", status="declined"))
        document = pdf_text_map()
        only_players_on_the_first_page(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "coverage"), "ok", output)
        document = starting_map()
        only_players_on_the_first_page(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "coverage"), "fail", output)
        self.assertIn("p. 1: inside the declared extent", output)

    def test_absence_is_searched_only_after_the_heading(self):
        def absent(document):
            document["entries"].append(entry("no-persons", "Widgets / Rounds / p. 2",
                                             "The winner of a round moves first.", scope="out",
                                             status="declined", absentFrom={"searched": ["persons"]}))
        document = starting_map()
        absent(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "absence"), "ok", output)
        document = pdf_text_map()
        absent(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "absence"), "fail", output)

    def test_an_extent_that_ends_where_it_has_not_begun_fails(self):
        """The one case the two cuts can contradict: both on the same page, in the wrong order."""
        document = starting_map()
        document["extent"] = {"unit": "page", "from": 1, "to": 1,
                              "startsAfter": "Tokens", "endsBefore": "Widgets"}
        document["entries"] = [e for e in document["entries"] if e["id"] == "token-moves"]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent-start"), "fail", output)
        self.assertIn("the second is printed at or before the first", output)

    def test_the_page_checker_refuses_an_extent_it_cannot_start(self):
        # tools/check-locators.py collapses lines, so it cannot find the heading; it says so.
        path = os.path.join(self.root, "hoyle-like.json")
        document = valid_map()
        document["extent"]["startsAfter"] = "Tokens"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        corpus = os.path.join(self.root, "hoyle-like.txt")
        with open(corpus, "w", encoding="utf-8") as handle:
            handle.write(CORPUS)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = check_locators.main([path, corpus])
        self.assertIn("[skip] extent-start: NOT VERIFIED", out.getvalue())
        self.assertEqual(code, 1, out.getvalue())


# 0030, #207: the two shapes a corpus's own repetition takes, in miniature. One sentence printed
# under two different headings (the SRD's "Speed 0." under five conditions), and one printed twice
# under the *same* heading, in two chapters, with a different rule immediately after it (the SRD's
# Round Down on pp. 5 and 187, and the Save entry that a unique span had to annex).
REPEATED_CORPUS = """{1}
Playing the Game
Rounding
Round down if you end up with a fraction.

Turn Order
The player to the left moves next.
{2}
Conditions
Grappled
Speed 0. Your Speed is 0.
{3}
Restrained
Speed 0. Your Speed is 0.
{4}
Glossary
Rounding
Round down if you end up with a fraction.

Save
A save is another name for a saving throw.
"""


# 0066: the boundary the cited page cannot cross. One page printing the same rule twice under two
# lines of the same heading, and a third printing elsewhere, so the path selects three and two of
# them are on the cited page. The page narrows and does not decide, and the citation is refused.
TWICE_ON_ONE_PAGE = """{1}
Playing the Game
Rounding
Round down if you end up with a fraction.

Rounding
Round down if you end up with a fraction.
{2}
Glossary
Rounding
Round down if you end up with a fraction.
"""


def repeated_map():
    return {
        "schemaVersion": 1,
        "corpus": "demo-pdf",
        "baseline": {"contentHash": "d" * 64, "hashDerivation": "demo-pdftotext"},
        "extent": {"unit": "page", "from": 1, "to": 4},
        "entries": [
            entry("turn-order", "Playing the Game / Turn Order / p. 1",
                  "The player to the left moves next."),
            entry("grappled-speed", "Conditions / Grappled / p. 2", "Speed 0. Your Speed is 0."),
            entry("restrained-speed", "Conditions / Restrained / p. 3", "Speed 0. Your Speed is 0."),
            entry("rounding", "Glossary / Rounding / p. 4",
                  "Round down if you end up with a fraction."),
        ],
    }


class TestPdfTextRepeatedPassages(TestPdfTextLocators):
    """0030: which printing of a repeated passage a citation means, and when it means none."""

    def run_repeated(self, document):
        """The repetition corpus, written per test so the inherited cases keep their own."""
        self.write_corpus(REPEATED_CORPUS)
        return self.run_tool(document)

    def test_the_same_sentence_under_two_headings_is_cited_by_each(self):
        code, output = self.run_repeated(repeated_map())
        self.assertEqual(code, 0, output)
        self.assertIn("3 quoted texts occur more than once, 3 of them printed off the cited page "
                      "too and identified by the heading path", output)

    def test_a_rule_printed_twice_is_cited_without_annexing_the_rule_after_it(self):
        # The round-down shape: no span of this rule alone is unique anywhere, and the only unique
        # span runs into the Save entry. The heading above it is what separates the two printings.
        document = repeated_map()
        quote = document["entries"][3]["evidence"]
        self.assertEqual(len(check_locators_pdf_text.occurrences(quote, REPEATED_CORPUS)), 2,
                         "the fixture must print this rule twice, or it is not the round-down shape")
        self.assertNotIn("A save", quote)
        code, output = self.run_repeated(document)
        self.assertEqual(code, 0, output)

    def test_the_old_workaround_is_not_the_only_option_and_still_passes(self):
        document = repeated_map()
        document["entries"][3]["evidence"] = ("Round down if you end up with a fraction. Save A "
                                              "save is another name for a saving throw.")
        code, output = self.run_repeated(document)
        self.assertEqual(code, 0, output)

    def test_the_earlier_of_two_identical_printings_is_named_by_its_page(self):
        """0066: the case the heading path structurally cannot narrow, resolved by the page.

        "Playing the Game" precedes both printings of "Rounding", and always will: p. 1 comes
        first, so every heading above the earlier printing is above the later one too. The path
        selects two, and the citation's own page holds one of them.
        """
        document = repeated_map()
        document["entries"][3]["locator"]["citation"] = "Playing the Game / Rounding / p. 1"
        code, output = self.run_repeated(document)
        # `coverage` then reports p. 4 unreached, which is true and is not what this is about.
        self.assertEqual(self.status_of(output, "locators"), "ok", output)
        self.assertIn("1 of those needing the cited page to choose among the printings the path "
                      "selected", output)

    def test_the_page_chooses_only_among_what_the_path_selected(self):
        """A path that selects nothing is still a refusal, page or no page.

        `Glossary / Save` is a heading with no printing of the quote after it. The quote *is* on
        p. 4, and that is not enough: the page narrows a selection, it does not make one.
        """
        document = repeated_map()
        document["entries"][3]["locator"]["citation"] = "Glossary / Save / p. 4"
        code, output = self.run_repeated(document)
        self.assertEqual(code, 1, output)
        self.assertIn("heading path 'Glossary / Save' selects none of them", output)
        self.assertIn("does not guess", output)

    def test_two_of_the_selected_printings_on_the_cited_page_is_still_a_refusal(self):
        self.write_corpus(TWICE_ON_ONE_PAGE)
        document = repeated_map()
        document["extent"] = {"unit": "page", "from": 1, "to": 2}
        document["entries"] = [entry("rounding", "Playing the Game / Rounding / p. 1",
                                     "Round down if you end up with a fraction.")]
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("selects 3 of them, 2 of those on the cited p. 1", output)
        self.assertIn("does not guess", output)

    def test_a_quote_that_occurs_nowhere_is_still_refused(self):
        document = repeated_map()
        document["entries"][3]["evidence"] = "Round up if you end up with a fraction."
        code, output = self.run_repeated(document)
        self.assertEqual(code, 1, output)
        self.assertIn("rounding: evidence does not occur in the extracted text", output)

    def test_a_repeated_quote_cited_to_a_page_neither_printing_is_on_fails(self):
        document = repeated_map()
        document["entries"][1]["locator"]["citation"] = "Conditions / Grappled / p. 3"
        code, output = self.run_repeated(document)
        self.assertEqual(code, 1, output)
        self.assertIn("grappled-speed: cited p. 3, evidence is on p. 2", output)


def table_entry(**overrides):
    return entry("score-table", "Glossary / p. 3", "Score Win One point Gammon Two points",
                 scope="out", status="declined",
                 extraction={"defect": "interleaved-table",
                             "renderedReading": "Score | Win: One point | Gammon: Two points"},
                 **overrides)


class TestPdfTextExtraction(TestPdfTextLocators):
    """0024: a declared extraction defect has its shape, and a folio in a quote is declared."""

    def test_declared_defects_pass_and_their_readings_are_printed_unverified(self):
        document = pdf_text_map()
        document["entries"].append(table_entry())
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extraction"), "ok", output)
        self.assertIn("token-moves: interrupted-by-page-furniture; renderedReading NOT VERIFIED", output)
        self.assertIn("'Each token moves once per round, and never twice.'", output)
        self.assertIn("score-table: interleaved-table; renderedReading NOT VERIFIED", output)
        self.assertEqual(code, 0, output)

    def test_a_folio_inside_an_undeclared_quote_fails(self):
        output = self.assert_catches("extraction", lambda d: d["entries"][1].pop("extraction"),
            message="runs across the folio line")
        self.assertIn("token-moves: its quote runs across the folio line '1'", output)

    def test_a_folio_inside_a_quote_declaring_another_defect_fails(self):
        output = self.assert_catches("extraction", lambda d: d["entries"][1]["extraction"]
                                     .update(defect="interleaved-table"),
            message="runs across the folio line")
        self.assertIn("does not declare extraction.defect interrupted-by-page-furniture", output)

    def test_page_furniture_declared_where_there_is_none_fails(self):
        output = self.assert_catches("extraction", lambda d: d["entries"][0].update(extraction={
            "defect": "interrupted-by-page-furniture", "renderedReading": "A widget is played by two."}),
            message="so no page furniture interrupts it")
        self.assertIn("runs across no folio line", output)

    def test_an_interleaved_table_declared_on_one_block_fails(self):
        output = self.assert_catches("extraction", lambda d: d["entries"][2].update(extraction={
            "defect": "interleaved-table", "renderedReading": "The winner moves first."}),
            message="blank-line-separated block")
        self.assertIn("fewer than the 3 a table's cells give", output)

    def test_a_split_sentence_declared_on_a_whole_sentence_fails(self):
        output = self.assert_catches("extraction", lambda d: d["entries"][2].update(extraction={
            "defect": "split-by-sidebar", "renderedReading": "The winner of each round moves first."}),
            message="so no sentence in it is split")
        self.assertIn("begins and ends on a sentence boundary", output)

    def test_a_split_sentence_declared_on_a_fragment_passes(self):
        document = pdf_text_map()
        document["entries"].append(entry("never-twice", "Widgets / Tokens / p. 1", "and never twice.",
                                         extraction={"defect": "split-by-sidebar",
                                                     "renderedReading": "Each token moves once per "
                                                                        "round, and never twice."}))
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extraction"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_defect_this_checker_has_no_test_for_fails(self):
        output = self.assert_catches("extraction", lambda d: d["entries"][1]["extraction"]
                                     .update(defect="joined-hyphenation"),
            message="is not a defect this checker has a test for")
        self.assertIn("is not a defect this checker has a test for", output)


# --- worked examples: an <EXAMPLE> is citable, and only under the paragraph it sits in -----

EXAMPLE_CORPUS = """<ROOT><DIV8 N="2.20" TYPE="SECTION"><HEAD>§ 2.20 Widgets.</HEAD>
<P>(a) <I>In general.</I> A widget adjacent to a token is a widget of the token.</P>
<P>(b) <I>Examples.</I> The provisions of this paragraph are illustrated by the following:</P>
<EXAMPLE><HED>Example 1.</HED><PSPACE>A owns a widget and a token. A may keep six.</PSPACE></EXAMPLE>
<EXAMPLE><HED>Example 2 Widget across a road.</HED><PSPACE>B owns a widget across a road from a \
token. B may keep none.</PSPACE></EXAMPLE>
<P>(c) <I>Tokens.</I> A token is counted once.</P>
<P>(d) <I>Example.</I> The provisions of this paragraph are illustrated by the following:</P>
<EXAMPLE><HED>Example.</HED><PSPACE>C owns one token and counts it once.</PSPACE></EXAMPLE>
</DIV8></ROOT>"""


class ExampleCase(unittest.TestCase):
    """A worked example is promulgated text and can be the corpus's only authority for a rule.

    § 1.121-1(b)(4) Example 4 is: it nets a loss on one of two combined transactions against the
    gain on the other, and no operative sentence of the section says a loss does that. Until the
    blind second mapping (examples/tax-121-principal-residence/blind-mapping/) the eCFR grammar
    could not cite one at all, so the first mapping declined all four Examples paragraphs and
    recorded the cost as its finding 3.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.corpus_path = os.path.join(self.root, "corpus.xml")
        with open(self.corpus_path, "w", encoding="utf-8") as handle:
            handle.write(EXAMPLE_CORPUS)
        self.corpus, self.spans, _, _ = check_locators_section.corpus_index(self.corpus_path)

    def verdict(self, citation, evidence):
        return check_locators_section.check(
            entry("x", citation, evidence), self.corpus, self.spans)[0]

    def test_an_example_is_indexed_under_the_paragraph_that_introduces_it(self):
        paths = [path for path, _, _ in
                 check_locators_section.paragraphs(ET.parse(self.corpus_path).getroot())]
        self.assertIn((None, "2.20", "b", "Example 1"), paths)
        self.assertIn((None, "2.20", "b", "Example 2"), paths)
        self.assertIn((None, "2.20", "d", "Example"), paths)

    def test_a_quote_from_an_example_verifies_against_its_own_citation(self):
        self.assertEqual(self.verdict("§ 2.20(b) Example 1", "A may keep six."), "ok")
        self.assertEqual(self.verdict("§ 2.20(b), Example 1", "A may keep six."), "ok")

    def test_the_paragraph_above_still_covers_its_examples(self):
        self.assertEqual(self.verdict("§ 2.20(b)", "A may keep six."), "ok")

    def test_a_quote_from_one_example_cited_to_another_fails(self):
        self.assertEqual(self.verdict("§ 2.20(b) Example 2", "A may keep six."), "bad")

    def test_an_example_cited_to_the_wrong_paragraph_fails(self):
        self.assertEqual(self.verdict("§ 2.20(d) Example 1", "A may keep six."), "bad")

    def test_a_numbered_example_is_not_reached_by_the_unnumbered_label(self):
        self.assertEqual(self.verdict("§ 2.20(b) Example", "A may keep six."), "bad")
        self.assertEqual(self.verdict("§ 2.20(d) Example", "C owns one token"), "ok")

    def test_a_descriptive_heading_is_indexed_with_the_example_and_citable(self):
        self.assertEqual(self.verdict("§ 2.20(b) Example 2", "Example 2 Widget across a road."),
                         "ok")

    def test_an_example_without_a_paragraph_is_outside_the_grammar(self):
        self.assertIsNone(check_locators_section.cited_paths("Example 4"))
        self.assertIsNone(check_locators_section.cited_paths("§ 2.20(b)-(c) Example 1"))

    def test_the_operative_paragraph_is_unchanged_by_the_examples_beside_it(self):
        self.assertEqual(
            self.verdict("§ 2.20(a)", "A widget adjacent to a token is a widget of the token."),
            "ok")


def bounded_map():
    """A map whose open term is bounded by the two worked examples of § 2.20(b) (0031)."""
    bounded = entry("widget-adjacency", "§ 2.20(a)",
                    "A widget adjacent to a token is a widget of the token.")
    bounded["clarity"] = "ambiguous"
    bounded["ambiguity"] = {
        "question": "The corpus fixes no distance for `adjacent`.",
        "fate": "unresolved",
        "unresolvedReason": "RequiresInterpretation",
        "bounds": {
            "term": "adjacent",
            "dimension": "duration",  # the shape, not the reading: what is checked here is the quote
            "examples": [
                {"locator": {"sourceId": "demo-cfr", "citation": "§ 2.20(b) Example 1"},
                 "text": "A owns a widget and a token. A may keep six.",
                 "verdict": "applies", "value": "P2M"},
                {"locator": {"sourceId": "demo-cfr", "citation": "§ 2.20(b) Example 2"},
                 "text": "B owns a widget across a road from a token. B may keep none.",
                 "verdict": "doesNotApply", "value": "P1Y"},
            ],
        },
    }
    return {
        "schemaVersion": 1,
        "corpus": "demo-cfr",
        "baseline": {"contentHash": "b" * 64, "hashDerivation": "demo-xml"},
        "extent": {"unit": "section-designation", "sections": ["§ 2.20"]},
        "entries": [bounded],
    }


class TestBoundsAreLocated(ExampleCase):
    """0031: a bound quotes the corpus and cites it, so it is held to `evidence`'s standard.

    A ruling is admitted or refused by comparing it against the bound's words, so a bound whose
    words are not at the citation it names would decide an engine's gate on a quotation of
    nothing -- which is the failure `evidence` being a summary already was (#18).
    """

    def run_tool(self, document):
        path = os.path.join(self.root, "corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = check_locators_section.main(["check-locators-section.py", path, self.corpus_path])
        return code, out.getvalue()

    def test_a_map_whose_bounds_quote_their_examples_passes(self):
        code, output = self.run_tool(bounded_map())
        self.assertEqual(code, 0, output)
        self.assertIn("2 authored example(s) bounding a term", output)

    def test_a_bound_whose_text_is_not_in_the_corpus_fails(self):
        document = bounded_map()
        document["entries"][0]["ambiguity"]["bounds"]["examples"][0]["text"] = (
            "A owns a widget and a token. A may keep seven.")
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("widget-adjacency: bounds.examples[1]", output)
        self.assertIn("do not quote the corpus at the citation they name", output)

    def test_a_bound_cited_to_the_wrong_example_fails(self):
        document = bounded_map()
        document["entries"][0]["ambiguity"]["bounds"]["examples"][0]["locator"]["citation"] = (
            "§ 2.20(b) Example 2")
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("widget-adjacency: bounds.examples[1]", output)

    def test_a_bound_does_not_reach_a_section_for_coverage(self):
        # An example quoted to bound someone else's term is not a verdict on the paragraph it
        # sits in. With the entry's own evidence unfindable, § 2.20 is reached by nothing, and
        # the two verified bounds inside it must not cover the section.
        document = bounded_map()
        document["entries"][0]["evidence"] = "A summary of the adjacency rule."
        code, output = self.run_tool(document)
        self.assertEqual(code, 1, output)
        self.assertIn("§ 2.20: inside the declared extent and reached by no entry's verified", output)


class TestPageBoundsAreLocated(LocatorCase):
    """The same rule in the printed-page grammar: a bound is located as `evidence` is (0031)."""

    def bounded(self):
        document = valid_map()
        document["entries"][1]["clarity"] = "ambiguous"
        document["entries"][1]["ambiguity"] = {
            "question": "The corpus does not say which number governs.",
            "fate": "unresolved",
            "unresolvedReason": "RequiresInterpretation",
            "bounds": {
                "term": "the number shown",
                "dimension": "duration",
                "examples": [
                    {"locator": {"sourceId": "demo-corpus", "citation": "Part One / p. 3"},
                     "text": "Where several rounds are played in succession, the winner moves first.",
                     "verdict": "applies", "value": "P2M"},
                ],
            },
        }
        return document

    def test_a_bound_quoting_its_cited_page_passes(self):
        code, output = self.run_tool(self.bounded())
        self.assertEqual(self.status_of(output, "locators"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_bound_cited_to_the_wrong_page_fails(self):
        document = self.bounded()
        document["entries"][1]["ambiguity"]["bounds"]["examples"][0]["locator"]["citation"] = \
            "Part One / p. 2"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "locators"), "fail", output)
        self.assertIn("legal-destination: bounds.examples[1]", output)
        self.assertEqual(code, 1, output)

    def test_a_bound_whose_text_is_not_in_the_corpus_fails(self):
        document = self.bounded()
        document["entries"][1]["ambiguity"]["bounds"]["examples"][0]["text"] = "The winner moves last."
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "locators"), "fail", output)
        self.assertIn("is not in the corpus verbatim", output)
        self.assertEqual(code, 1, output)


if __name__ == "__main__":
    unittest.main()
