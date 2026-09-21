#!/usr/bin/env python3
"""Every check in check-map.py, proved able to fail.

The pattern is one test per check: build a map the spec says is valid, assert the named
check reports `ok`, mutate exactly the thing that check exists to catch, and assert the
same check reports `fail`. A check with no failing test here is a check nobody has shown
can fail, which is the class of gate this repository most distrusts.

The fixture is written from `docs/corpus-map.md` and `docs/decisions/0005`, not from the
example maps -- an expectation drawn from the thing under test proves nothing, and the
example maps are mid-migration.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import glob
import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "check-map.py")

_spec = importlib.util.spec_from_file_location("check_map", TOOL)
check_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_map)


# --- the fixture, written from the spec ------------------------------------------------

MANIFEST = {
    "schemaVersion": 1,
    "corpora": [
        {
            "sourceId": "demo-corpus",
            "title": "A Demonstration Corpus",
            "adapter": "plain-text",
            "locatorGrammar": "printed-page",
            "contentHash": "a" * 64,
            "hashDerivation": "demo-plain-text",
            # 0024: the committed text is derived from a published file, and quotes are of it.
            "quotedText": {"derivation": "demo-plain-text", "extractedFrom": "demo.pdf"},
            "boundaryPolicy": "pin-in-repo",
            "licence": "public-domain",
            # 0013: how the baseline is verified, and whether a map may quote the corpus.
            "verification": "committed-copy",
            "committedPath": "demo.txt",
            "quotation": "verbatim",
            # 0019: whether an engine for the corpus may draw random values.
            "randomness": "none",
            "references": [{"sourceId": "other-corpus", "citation": "s 1", "admitted": False}],
        }
    ],
}

# A second corpus nobody may commit or quote, for the rules that only a licence triggers.
COMMERCIAL = {
    "sourceId": "core-rules",
    "title": "Core Rulebook",
    "adapter": "pdf",
    "locatorGrammar": "printed-page",
    "contentHash": "c" * 64,
    "hashDerivation": "pdf-bytes",
    "boundaryPolicy": "never-commit",
    "licence": "commercial",
    "verification": "local-copy",
    "envVar": "CORE_RULES_PDF",
    "quotation": "withheld",
    "randomness": "seeded",
}


def entry(entry_id, **overrides):
    base = {
        "id": entry_id,
        "name": f"The rule called {entry_id}",
        "locator": {"sourceId": "demo-corpus", "citation": f"Part One / p. 1 ({entry_id})"},
        "kind": "value",
        "scope": "in",
        "clarity": "clear",
        "dependsOn": [],
        "evidence": f"The sentence stating {entry_id}.",
        "status": "mapped",
    }
    base.update(overrides)
    return base


def proof(*names):
    """#2: the tests an implemented entry names, each with the mutation recorded turning it red."""
    return [{"test": name, "mutation": f"Inverted the comparison {name} asserts; it went red."}
            for name in names]


def bounds(**overrides):
    """0031: what two authored examples fix about a term an operative rule leaves open."""
    base = {
        "term": "short interruption",
        "dimension": "duration",
        "examples": [
            {"locator": {"sourceId": "demo-corpus", "citation": "Part One / p. 1 (the long pause)"},
             "text": "A pause of one year is not a short interruption.",
             "verdict": "doesNotApply", "value": "P1Y"},
            {"locator": {"sourceId": "demo-corpus", "citation": "Part One / p. 1 (the short pause)"},
             "text": "A pause of two months is a short interruption.",
             "verdict": "applies", "value": "P2M"},
        ],
    }
    base.update(overrides)
    return base


def valid_map():
    """A map exercising every shape the spec describes, and nothing the spec forbids."""
    return {
        "schemaVersion": 1,
        "corpus": "demo-corpus",
        "baseline": {"contentHash": "a" * 64, "hashDerivation": "demo-plain-text"},
        "extent": {"unit": "page", "from": 1, "to": 1},
        "entries": [
            entry("speed-limit", kind="value", status="implemented",
                  implementedIn={"ruleset": "demo", "version": 1},
                  tests=proof("SpeedLimitTests.The_limit_is_87_knots")),
            entry("speed-within-limit", kind="operation", dependsOn=["speed-limit"],
                  status="implemented", implementedIn={"ruleset": "demo", "version": 1},
                  tests=proof("SpeedTests.At_the_limit_is_permitted", "SpeedTests.Above_the_limit_is_refused")),
            # 0025: an assertion names who asserts it, in the corpus's words.
            entry("well-clear", kind="assertion", status="mapped", assertedBy=["remote pilot"],
                  evidence="The remote pilot must keep the aircraft well clear of other aircraft."),
            # 0045: the entry defines a term of a named vocabulary, anchored in its own
            # evidence -- "The sentence stating yield-right-of-way." prints the term.
            entry("yield-right-of-way", kind="operation", dependsOn=["well-clear"],
                  defines=[{"vocabulary": "demo-codes", "term": "yield-right-of-way"}],
                  enabledBy=["speed-limit"], suspendedBy=["speed-within-limit"],
                  status="implemented",
                  implementedIn={"ruleset": "demo", "version": 1},
                  tests=proof("RightOfWayTests.Passing_over_is_refused")),
            entry("hazardous-material", kind="value", status="declined",
                  definedElsewhere={"reference": "other-corpus"}),
            entry("inner-table-handedness", kind="value", status="declined",
                  beyondAdapter={"adapter": "plain-text", "modality": "illustration"}),
            entry("subpart-d-categories", scope="out", status="declined"),
            # 0031: the corpus leaves "a short interruption" open and bounds it by two authored
            # examples, on opposite sides, in a dimension a later ruling can be compared against.
            entry("must-play-whole-throw", kind="operation", clarity="ambiguous",
                  status="implemented", implementedIn={"ruleset": "demo", "version": 1},
                  tests=proof("WholeThrowTests.Either_die_alone_but_not_both_declines"),
                  evidence="The player must play the whole throw, and a short interruption does "
                           "not end his turn.",
                  ambiguity={
                      "question": "The text does not say what happens when only one die is playable, "
                                  "nor how long a short interruption may be.",
                      "fate": "unresolved",
                      "unresolvedReason": "RequiresInterpretation",
                      "bounds": bounds(),
                  }),
            # 0009: read, and the corpus does not state the rule at all. `scope: out` like
            # subpart-d-categories above and a different verdict, which is the distinction
            # the field exists to make. The claim itself is falsified by check-locators.py,
            # which searches the text; nothing in check-map.py reads a corpus.
            entry("doubling-cube", kind="operation", scope="out", status="declined",
                  absentFrom={"searched": ["doubling", "redouble"]}),
            # 0009: the corpus points somewhere, so the mapper answers the pointer.
            entry("next-game-opening", kind="operation", dependsOn=["speed-limit"],
                  evidence="After a gammon the players throw again for the right to begin, "
                           "as at starting.",
                  crossReferences=[{"cites": "as at starting", "resolvedBy": "speed-limit"}],
                  # 0024: the extraction garbles the passage, and the page reads otherwise.
                  extraction={"defect": "split-by-sidebar",
                              "renderedReading": "After a gammon the players throw again for the "
                                                 "right to begin, as at starting, whoever won."}),
            derived_entry("hit-pays-single-stake", ["speed-limit", "speed-within-limit"]),
        ],
    }


def derived_entry(entry_id, sources, **overrides):
    """0012: a fact the corpus entails and never states. It cites nothing."""
    base = entry(entry_id, derivedFrom=list(sources), **overrides)
    base.pop("locator")
    base.pop("evidence")
    return base


def decided_entry():
    """An entry whose ambiguity is settled by a record, for the two checks that need one."""
    return entry("opposed-test-tie", kind="operation", clarity="ambiguous", status="mapped",
                 evidence="On equal hits the opposed test is decided by the sentence stating "
                          "opposed-test-tie.",
                 ambiguity={
                     # #271: the question quotes the words the two readings turn on.
                     "question": "On equal hits the text does not say which side prevails.",
                     "fate": "decision",
                     "decision": "docs/decisions/0007-opposed-test-tie-break.md",
                 })


def section_cited_map():
    """valid_map, re-cited in the section-designation grammar with an extent of two sections."""
    document = valid_map()
    document["extent"] = {"unit": "section-designation", "sections": ["§ 1.10", "§ 1.11"]}
    for position, item in enumerate(document["entries"]):
        if "locator" in item:
            item["locator"]["citation"] = ("§ 1.10(a)", "§ 1.11 introductory text")[position % 2]
    return document


def table_map():
    """0035: the same map, with one rule read out of a row of a table the extent slices.

    Two tables in § 1.10: one sliced to two rows, one excluded with a reason. Every table of a
    cited section is named, which is what keeps an extent from shrinking to whatever the walk
    happened to read.
    """
    document = section_cited_map()
    document["extent"]["tables"] = [
        {"section": "§ 1.10", "table": 1,
         "rows": [{"column": 2, "is": "Acetal"},
                  [{"column": 2, "is": "Ammonia, anhydrous"}, {"column": 1, "is": "G"}]]},
        {"section": "§ 1.10", "table": 2,
         "excluded": "code meanings; no mapped row invokes one"},
    ]
    document["entries"][0]["locator"]["citation"] = \
        '§ 1.10 table 1, row [column 2 = "Acetal"], column 4A'
    return document


def applicability_map():
    """valid_map, plus a rule whose own words gate the whole unit and one entry it gates (#225).

    § 1.121-1(f) is the committed shape -- *"This section is applicable for sales and exchanges
    on or after December 24, 2002"* -- and `speed-within-limit` stands for the thirty entries
    Map C had to name it on.
    """
    document = valid_map()
    document["entries"].append(entry(
        "first-day", kind="operation",
        evidence="This section is applicable to throws made on or after the first day."))
    document["entries"][1]["enabledBy"] = ["first-day"]
    return document


# --- harness ---------------------------------------------------------------------------


class MapCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "docs", "decisions"))
        with open(os.path.join(self.root, "docs", "decisions",
                               "0007-opposed-test-tie-break.md"), "w") as handle:
            handle.write("# 0007\n")
        self.example = os.path.join(self.root, "examples", "demo")
        os.makedirs(self.example)
        with open(os.path.join(self.example, "demo.txt"), "w") as handle:
            handle.write("The committed copy of the demonstration corpus.\n")
        self.write_manifest(MANIFEST)

    def write_manifest(self, manifest):
        self.manifest_path = os.path.join(self.example, "corpus-manifest.json")
        with open(self.manifest_path, "w") as handle:
            json.dump(manifest, handle)

    def run_tool(self, document, argv=()):
        path = os.path.join(self.example, "corpus-map.json")
        with open(path, "w") as handle:
            json.dump(document, handle)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_map.main([path, "--repo-root", self.root, *argv])
        return code, out.getvalue() + err.getvalue()

    def status_of(self, output, check):
        found = re.search(rf"^\[(ok|fail|skip)\] {re.escape(check)}:", output, re.M)
        self.assertIsNotNone(found, f"check {check!r} did not report at all:\n{output}")
        return found.group(1)

    def assert_catches(self, check, mutate, expect="fail", *, message=None):
        """The valid map passes this check; the mutation makes this check say `message`.

        `message` is **required** and is a fragment of the refusal the mutation must produce
        ([#283](https://github.com/brandonifco/rules-factory/issues/283)). Asserting only the
        check's verdict was not enough: a mutation that damages the map in a way *another rule
        of the same check* also catches still showed red, and the test passed while proving
        nothing about the rule it was written for. Four of #280's eighteen extent tests did
        exactly that, and nothing said how many others do.

        It is keyword-only with no usable default, so the next test cannot be written without
        one -- which is the part of #283 a one-time audit could not deliver.
        """
        if not message:
            raise AssertionError(
                f"assert_catches({check!r}, ...) names no expected refusal. Assert the message, "
                f"not only the verdict: a neighbouring rule of the same check can satisfy the "
                f"verdict while the rule this test is about goes unexercised (#283)")
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, check), "ok", output)
        self.assertEqual(code, 0, output)
        document = valid_map()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, check), expect, output)
        self.assertEqual(code, 1, output)
        self.assertIn(message, output,
                      f"the {check!r} check refused the map, but not with the refusal this test "
                      f"names -- another rule of the same check may be doing the work:\n{output}")


# --- one test per check ------------------------------------------------------------------


class TestTheHelperCannotBeUsedWithoutNamingARefusal(MapCase):
    """#283: the verdict alone was never enough, and nothing stopped a test asserting only it.

    `assert_catches` asserted that a named check said `fail`. A mutation caught by a *different
    rule of the same check* satisfied that, and the test passed while the rule it was written for
    went unexercised -- measured on #280, where four of eighteen new extent tests stayed green
    under the mutation that removed the very rule they name.

    An audit fixes the call sites that exist. This fixes the ones that do not exist yet, which is
    why the argument is required rather than merely present everywhere today.

    Mutation: give `message` a default of `""`, or drop the guard. Both tests here go green while
    a test asserting nothing about the refusal becomes writable again.
    """

    def test_assert_catches_refuses_a_call_that_names_no_refusal(self):
        with self.assertRaises(AssertionError) as caught:
            self.assert_catches("schema", lambda d: d.pop("baseline"))
        self.assertIn("names no expected refusal", str(caught.exception))

    def test_the_refusal_must_be_the_one_the_check_actually_gave(self):
        # A message from a neighbouring rule of the same check does not satisfy it: this is the
        # shape of the four #280 tests, written out so the guard is demonstrated and not assumed.
        with self.assertRaises(AssertionError) as caught:
            self.assert_catches("schema", lambda d: d.pop("baseline"),
                                message="a schema version this checker does not read")
        self.assertIn("not with the refusal this test names", str(caught.exception))


class TestFixtureIsValid(MapCase):
    def test_the_valid_map_passes_every_check(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(code, 0, output)
        self.assertNotIn("[fail]", output, output)
        # `applicability-reach`, `conflicts`, `decision-records`, `definition-continuations`,
        # `inherited-reason` and `superposition` skip without subject matter -- the fixture
        # records no conflict, no decision, no continued definition, no blind second mapping
        # beside it, no rule whose own words gate a whole section (`applicability_map()` is the
        # fixture for that shape, because a page-marked rulebook slice does not talk about itself
        # that way), and no open question depending on an entry that defers to an unadmitted
        # corpus -- that last one is `TestTheReasonIsInheritedAcrossAnEdge`'s subject, built there
        # by pointing the fixture's one open question at `hazardous-material`. Nothing else may.
        skipped = re.findall(r"^\[skip\] (\S+):", output, re.M)
        self.assertEqual(sorted(skipped),
                         ["applicability-reach", "conflicts", "decision-records",
                          "definition-continuations", "inherited-reason", "superposition"], output)


class TestSchema(MapCase):
    def test_a_map_without_its_baseline_stamp_fails(self):
        self.assert_catches("schema", lambda d: d.pop("baseline"), message='map is missing `baseline`')

    def test_a_baseline_without_its_derivation_fails(self):
        self.assert_catches("schema", lambda d: d["baseline"].pop("hashDerivation"), message='baseline is missing `hashDerivation`: a digest without its')

    def test_a_schema_version_this_checker_does_not_read_fails(self):
        self.assert_catches("schema", lambda d: d.update(schemaVersion=2), message='schemaVersion 2 is not one this checker reads (1)')


    def test_an_inline_manifest_is_refused_rather_than_ignored(self):
        # #60: the blind Part 107 map carried `manifest` inline, and the checker reported "no
        # manifest" and skipped every resolution while the key sat there unread.
        self.assert_catches("schema", lambda d: d.update(manifest=MANIFEST), message='map carries `manifest` inline')

    def test_an_unknown_top_level_field_is_refused(self):
        self.assert_catches("schema", lambda d: d.update(coverage="twelve sections"), message='map has top-level `coverage`')

    def test_every_example_map_uses_only_known_top_level_fields(self):
        # The closed envelope must not break a map the repository already ships.
        repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        maps = sorted(os.path.join(repo, "examples", d, n)
                      for d in os.listdir(os.path.join(repo, "examples"))
                      if os.path.isdir(os.path.join(repo, "examples", d))
                      for n in os.listdir(os.path.join(repo, "examples", d))
                      if n.startswith("corpus-map") and n.endswith(".json"))
        self.assertTrue(maps)
        for path in maps:
            with self.subTest(map=path), open(path, encoding="utf-8") as handle:
                self.assertLessEqual(set(json.load(handle)), set(check_map.MAP_FIELDS))


class TestExtent(MapCase):
    """0020: the shape of `extent` in each unit, and a section-designation map cites inside it."""

    def section_map(self):
        return section_cited_map()

    def assert_section_catches(self, mutate, *, message=None):
        """As `assert_catches`, for the `extent` check. `message` is required for the
        same reason: a neighbouring rule of one check can satisfy its verdict (#283)."""
        if not message:
            raise AssertionError(
                "assert_section_catches(...) names no expected refusal. Assert the message, not only "
                "the verdict: a neighbouring rule of `extent` can satisfy it while the "
                "rule this test is about goes unexercised (#283)")
        code, output = self.run_tool(self.section_map())
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertEqual(code, 0, output)
        document = self.section_map()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "fail", output)
        self.assertEqual(code, 1, output)
        self.assertIn(message, output,
                      f"`extent` refused the map, but not with the refusal this test names -- "
                      f"another rule of the same check may be doing the work:\n{output}")
        return output

    def test_a_page_extent_may_end_before_a_heading(self):
        # 0024: the SRD combat chapter ends halfway down p. 16, where "Damage and Healing" begins.
        document = valid_map()
        document["extent"]["endsBefore"] = "Damage and Healing"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertIn("ending before the heading 'Damage and Healing' on p. 1", output)
        self.assertEqual(code, 0, output)

    def test_an_empty_ends_before_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update(endsBefore=""), message="endsBefore is ''; it names one heading on page `to`, as a")

    def test_an_ends_before_that_is_not_one_line_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update(endsBefore="Damage\nand Healing"), message="endsBefore is 'Damage\\nand Healing'")

    def test_an_ends_before_that_is_not_text_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update(endsBefore=16), message='endsBefore is 16; it names one heading on page `to`, as a')

    def test_starts_after_is_not_a_field_of_a_page_extent(self):
        # No real case needs it (0024), so it is refused like any other unknown field.
        self.assert_catches("extent", lambda d: d["extent"].update(startsAfter="Combat"), message='`startsAfter` is not a field of a page extent (unit, from')

    def test_a_page_extent_that_is_not_a_range_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update({"from": 4, "to": 1}), message='`to` 1 is before `from` 4')

    def test_a_page_extent_with_a_non_integer_bound_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update({"to": "280"}), message='a page extent names integer `from` and `to`')

    def test_a_page_extent_may_declare_the_fraction_of_it_the_map_quotes(self):
        # #270, 0054: the floor a map can be held to by the locator checkers, which have the
        # corpus. Only its shape is checked here.
        document = valid_map()
        document["extent"]["quoted"] = 0.8
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertIn("declaring at least 80% of it quoted", output)
        self.assertEqual(code, 0, output)

    def test_a_section_extent_may_declare_one_too(self):
        document = self.section_map()
        document["extent"]["quoted"] = 0.5
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertIn("declaring at least 50% of it quoted", output)
        self.assertEqual(code, 0, output)

    def test_a_quoted_fraction_above_one_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update(quoted=1.4),
            message="`quoted` is 1.4; it is the fraction of the extent this map claims its "
                    "verified evidence quotes, above 0 and at most 1")

    def test_a_quoted_fraction_of_zero_fails(self):
        # A map claiming it can show none of its extent quoted claims nothing, and says it in a
        # field: the omission already means "not held to a floor", and saying so twice, in two
        # ways, is a distinction nothing could act on.
        self.assert_catches("extent", lambda d: d["extent"].update(quoted=0),
            message="`quoted` is 0; it is the fraction of the extent this map claims")

    def test_a_quoted_fraction_that_is_not_a_number_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update(quoted="80%"),
            message="`quoted` is '80%'; it is the fraction of the extent this map claims")

    def test_an_in_scope_entry_citing_a_page_outside_the_extent_fails(self):
        # #269: the page unit's half of what this check already did for sections. Narrowing
        # `hoyle-backgammon`'s extent from 271-280 to 271-279 left every citation in place and
        # was missed by every check the validator has; `coverage` cannot see it, because
        # narrowing makes coverage easier to satisfy.
        self.assert_catches("extent", lambda d: d["entries"][0]["locator"].update(
            citation="Part One / p. 2"),
            message='cites p. 2, outside the declared extent (pages 1-1), and is not `scope: out`')

    def test_an_out_of_scope_entry_may_cite_a_page_beyond_the_extent_and_is_reported(self):
        # The same exemption 0020 gives a section citation: recording what lies beyond the slice
        # is what an out-of-scope entry is for. The SRD combat map cites p. 5 through p. 10 and
        # the Rules Glossary at pp. 178-189 that way, all outside its 13-16.
        document = valid_map()
        document["entries"][6]["locator"]["citation"] = "Part Two / p. 9"   # subpart-d-categories
        document["entries"][8]["locator"]["citation"] = "Part Two / p. 17"  # doubling-cube
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertIn("2 out-of-scope citations beyond the extent, neither passed nor failed: "
                      "subpart-d-categories (Part Two / p. 9), doubling-cube (Part Two / p. 17)",
                      output)
        self.assertEqual(code, 0, output)

    def test_an_in_scope_citation_naming_no_page_fails(self):
        # The page counterpart of "names no section or subpart": a citation with no page cannot
        # be placed, and the placement is the whole of what this rule buys.
        self.assert_catches("extent", lambda d: d["entries"][0]["locator"].update(
            citation="Part One"),
            message="citation 'Part One' names no page, so it cannot be placed inside the extent")

    def test_a_derived_entry_is_not_placed_in_a_page_extent(self):
        # 0012: a derived entry cites nothing, so there is nothing to place. It is exempt in the
        # page unit exactly as it is in the section unit.
        document = valid_map()
        document["extent"].update({"from": 271, "to": 280})
        for item in document["entries"]:
            if "locator" in item:
                item["locator"]["citation"] = "Part One / p. 271"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_an_extent_in_an_unknown_unit_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update({"unit": "paragraph"}), message="unit is 'paragraph', outside {page, section-designation}")

    def test_an_extent_mixing_the_two_shapes_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update({"sections": ["§ 1.10"]}), message='`sections` is not a field of a page extent (unit, from, to')

    def test_a_citation_outside_the_declared_sections_fails(self):
        output = self.assert_section_catches(
            lambda d: d["entries"][0]["locator"].update(citation="§ 1.12(b)"), message='cites § 1.12, outside the declared extent (2 sections), and')
        self.assertIn("§ 1.12", output)

    def test_a_section_list_holding_a_paragraph_fails(self):
        self.assert_section_catches(lambda d: d["extent"]["sections"].append("§ 1.12(a)"), message="sections holds '§ 1.12(a)'")

    def test_a_section_listed_twice_fails(self):
        self.assert_section_catches(lambda d: d["extent"]["sections"].append("§ 1.10"), message='§ 1.10 is listed twice')

    def test_an_empty_section_list_fails(self):
        self.assert_section_catches(lambda d: d["extent"].update(sections=[]), message='a section-designation extent names a non-empty `sections`')

    def test_a_citation_in_no_section_grammar_fails(self):
        self.assert_section_catches(
            lambda d: d["entries"][0]["locator"].update(citation="Part One / p. 1"), message="citation 'Part One / p. 1' names no section or subpart")

    def test_an_in_scope_entry_citing_a_subpart_outside_the_extent_fails(self):
        # speed-limit is scope: in.
        self.assert_section_catches(
            lambda d: d["entries"][0]["locator"].update(citation="subpart D"), message='cites subpart D, outside the declared extent (2 sections)')

    def test_an_out_of_scope_entry_may_cite_beyond_the_extent_and_is_reported(self):
        # Part 107's subpart-d-categories cites "subpart D", and #61's waiver entries cite
        # §§ 107.200 and 107.205: recording what lies beyond the slice is what scope: out is for.
        document = self.section_map()
        document["entries"][6]["locator"]["citation"] = "subpart D"   # subpart-d-categories
        document["entries"][8]["locator"]["citation"] = "§ 1.200"     # doubling-cube
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertIn("2 out-of-scope citations beyond the extent, neither passed nor failed: "
                      "subpart-d-categories (subpart D), doubling-cube (§ 1.200)", output)
        self.assertEqual(code, 0, output)

    def test_the_same_citation_fails_once_the_entry_is_in_scope(self):
        def mutate(document):
            document["entries"][6]["locator"]["citation"] = "§ 1.200"
            document["entries"][6]["scope"] = "in"
        self.assert_section_catches(mutate, message='cites § 1.200, outside the declared extent (2 sections)')

    def test_a_table_slice_is_a_shape_the_extent_may_carry(self):
        # 0035: the rows it takes, and the tables it does not, both named.
        code, output = self.run_tool(table_map())
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertIn("2 table(s) accounted for, 1 locator(s) naming a row the extent takes",
                      output)
        self.assertEqual(code, 0, output)

    def test_a_map_declaring_no_extent_is_not_refused_here(self):
        # The omission is refused by the locator checkers' `coverage`, which have the corpus.
        document = valid_map()
        document.pop("extent")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_the_section_is_read_as_the_locator_checker_reads_it(self):
        # The two grammars are one grammar, kept in two files; they agree on every citation
        # the Part 107 maps make, and on the forms 0020 adds.
        repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        spec = importlib.util.spec_from_file_location(
            "check_locators_section",
            os.path.join(repo, "examples", "faa-part-107", "check-locators-section.py"))
        section_tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(section_tool)
        citations = ["§ 107.51 introductory text", "§ 107.33 introductory text, (a)", "subpart D"]
        for name in ("faa-part-107/corpus-map.json",
                     "faa-part-107-temporal/corpus-map-2020-01-01.json"):
            with open(os.path.join(repo, "examples", name), encoding="utf-8") as handle:
                citations += [e["locator"]["citation"] for e in json.load(handle)["entries"]
                              if "locator" in e]
        for citation in citations:
            with self.subTest(citation=citation):
                prefixes = section_tool.cited_paths(citation)
                self.assertIsNotNone(prefixes)
                if prefixes[0][0] is None:
                    expected = ("section", prefixes[0][1])
                else:
                    expected = ("subpart", prefixes[0][0])
                self.assertEqual(check_map.cited_section(citation), expected)

    def test_the_page_is_read_as_the_two_page_locator_checkers_read_it(self):
        # #269, the page counterpart of the test above. `check-locators.py`'s `--page-re` default
        # and the PDF-text checker's `PAGE` are one grammar in three files now, so they are held
        # to each other over every citation the three committed page maps make.
        #
        # Mutation: give `CITE_PAGE` the anchored form the PDF-text checker uses, `\s*$` after
        # it. Both equalities go red, which is the drift this test exists to stop -- and the
        # reason `extent` reads the looser of the two is that placing a citation is a weaker
        # question than resolving it, so the strictness belongs to the grammar's own checker.
        repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        page_tool = _load(repo, "tools", "check-locators.py")
        pdf_tool = _load(repo, "examples", "srd-52-combat", "check-locators-pdf-text.py")
        self.assertEqual(page_tool.DEFAULT_PAGE, check_map.CITE_PAGE.pattern)
        self.assertEqual(pdf_tool.PAGE.pattern, check_map.CITE_PAGE.pattern + r"\s*$")
        citations = []
        for name in ("hoyle-backgammon/corpus-map.json", "srd-52-combat/corpus-map.json",
                     "srd-52-conditions/corpus-map.json"):
            with open(os.path.join(repo, "examples", name), encoding="utf-8") as handle:
                citations += [e["locator"]["citation"] for e in json.load(handle)["entries"]
                              if "locator" in e]
        self.assertTrue(citations)
        for citation in citations:
            with self.subTest(citation=citation):
                read = re.search(page_tool.DEFAULT_PAGE, citation)
                self.assertIsNotNone(read, "the page checker reads a page out of every citation")
                self.assertEqual(check_map.cited_page(citation), int(read.group(1)))


def _load(repo, *parts):
    spec = importlib.util.spec_from_file_location("_" + parts[-1], os.path.join(repo, *parts))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTableSlice(MapCase):
    """0035: an extent that slices a table names the rows it takes and accounts for the rest.

    What is checkable without the corpus is the shape of the list, and that an in-scope entry
    citing a row cites a row the slice took. That *every* table printed inside a cited section
    appears in the list needs the corpus, and the `ecfr-xml` adapter refuses one the extent
    passes over in silence (`tools/tests/mapper/test_mapper_table_rows.py`).
    """

    def assert_table_catches(self, mutate, *, message=None):
        """As `assert_catches`, for the `extent` check. `message` is required for the
        same reason: a neighbouring rule of one check can satisfy its verdict (#283)."""
        if not message:
            raise AssertionError(
                "assert_table_catches(...) names no expected refusal. Assert the message, not only "
                "the verdict: a neighbouring rule of `extent` can satisfy it while the "
                "rule this test is about goes unexercised (#283)")
        code, output = self.run_tool(table_map())
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertEqual(code, 0, output)
        document = table_map()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "fail", output)
        self.assertEqual(code, 1, output)
        self.assertIn(message, output,
                      f"`extent` refused the map, but not with the refusal this test names -- "
                      f"another rule of the same check may be doing the work:\n{output}")
        return output

    def test_a_row_the_slice_does_not_take_is_outside_the_extent(self):
        output = self.assert_table_catches(
            lambda d: d["entries"][0]["locator"].update(
                citation='§ 1.10 table 1, row [column 2 = "Acetaldehyde"]'), message='cites § 1.10 table 1, row [column 2 = "Acetaldehyde"], and')
        self.assertIn("does not take that row", output)

    def test_the_order_of_a_keys_pairs_is_not_part_of_what_it_names(self):
        # The pairs are a conjunction; a citation writing them the other way round names the
        # same row, and an extent that took it took it.
        document = table_map()
        document["entries"][0]["locator"]["citation"] = (
            '§ 1.10 table 1, row [column 1 = "G"; column 2 = "Ammonia, anhydrous"]')
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_row_of_an_excluded_table_fails(self):
        output = self.assert_table_catches(
            lambda d: d["entries"][0]["locator"].update(
                citation='§ 1.10 table 2, row [column 1 = "A3"]'), message='cites § 1.10 table 2, row [column 1 = "A3"], and the extent')
        self.assertIn("excludes § 1.10 table 2", output)

    def test_a_row_of_a_table_the_extent_does_not_name_fails(self):
        output = self.assert_table_catches(
            lambda d: d["entries"][0]["locator"].update(
                citation='§ 1.10 table 4, row [column 2 = "Acetal"]'), message='cites § 1.10 table 4, row [column 2 = "Acetal"], and the')
        self.assertIn("declares no slice of § 1.10 table 4", output)

    def test_a_row_of_a_section_outside_the_extent_fails(self):
        output = self.assert_table_catches(
            lambda d: d["entries"][0]["locator"].update(
                citation='§ 1.99 table 1, row [column 2 = "Acetal"]'), message='cites § 1.99, outside the declared extent (2 sections), and')
        self.assertIn("§ 1.99", output)

    def test_a_slice_of_a_section_the_extent_does_not_cite_fails(self):
        output = self.assert_table_catches(
            lambda d: d["extent"]["tables"].append({"section": "§ 1.99", "table": 1,
                                                    "rows": "all"}), message='§ 1.99 is not in the declared extent')
        self.assertIn("§ 1.99 is not in the declared extent", output)

    def test_the_same_table_sliced_twice_fails(self):
        output = self.assert_table_catches(
            lambda d: d["extent"]["tables"].append({"section": "§ 1.10", "table": 1,
                                                    "rows": "all"}), message='§ 1.10 table 1 is declared twice')
        self.assertIn("declared twice", output)

    def test_a_slice_that_both_takes_and_excludes_fails(self):
        # The message is asserted, not only the verdict: a slice that says both fails the
        # placement below too, and "it declares both" is the finding.
        output = self.assert_table_catches(
            lambda d: d["extent"]["tables"][0].update(excluded="and also excluded"), message='§ 1.10 table 1 is sliced (`rows`), taken whole (`rows')
        self.assertIn("declares both", output)

    def test_a_slice_that_neither_takes_nor_excludes_fails(self):
        output = self.assert_table_catches(lambda d: d["extent"]["tables"][0].pop("rows"), message='§ 1.10 table 1 is sliced (`rows`), taken whole (`rows')
        self.assertIn("declares neither", output)

    def test_an_exclusion_with_no_reason_fails(self):
        output = self.assert_table_catches(
            lambda d: d["extent"]["tables"][1].update(excluded="  "), message='`excluded` is why this table is outside the slice, in words')
        self.assertIn("in words", output)

    def test_an_empty_row_list_fails(self):
        output = self.assert_table_catches(lambda d: d["extent"]["tables"][0].update(rows=[]), message='`rows` is "all" or a non-empty list of row keys')
        self.assertIn("non-empty list of row keys", output)

    def test_a_rows_value_that_is_neither_all_nor_a_list_fails(self):
        output = self.assert_table_catches(lambda d: d["extent"]["tables"][0].update(rows="some"), message='`rows` is "all" or a non-empty list of row keys')
        self.assertIn("non-empty list of row keys", output)

    def test_a_row_key_that_is_not_a_column_and_a_value_fails(self):
        self.assert_table_catches(
            lambda d: d["extent"]["tables"][0]["rows"].append({"row": 4}), message='rows[2] is not a row key')

    def test_a_table_named_by_something_other_than_its_position_fails(self):
        output = self.assert_table_catches(
            lambda d: d["extent"]["tables"][0].update(table="Hazardous Materials Table"), message="`table` is 'Hazardous Materials Table'")
        self.assertIn("named by its position in the section", output)

    def test_a_table_slice_naming_a_paragraph_rather_than_a_section_fails(self):
        self.assert_table_catches(
            lambda d: d["extent"]["tables"][0].update(section="§ 1.10(a)"), message="`section` is '§ 1.10(a)', and a table is named inside one")

    def test_an_unknown_field_in_a_slice_fails(self):
        self.assert_table_catches(
            lambda d: d["extent"]["tables"][0].update(caption="Widget table"), message='`caption` is not a field of a table slice (section, table')

    def test_an_empty_tables_list_fails(self):
        output = self.assert_table_catches(lambda d: d["extent"].update(tables=[]), message='`tables` is present and names no table')
        self.assertIn("present and names no table", output)

    def test_tables_on_a_page_extent_is_not_a_field_of_one(self):
        self.assert_catches("extent", lambda d: d["extent"].update(
            tables=[{"section": "§ 1.10", "table": 1, "rows": "all"}]), message='`tables` is not a field of a page extent (unit, from, to')

    def test_an_out_of_scope_entry_may_cite_a_row_beyond_the_slice(self):
        # Recording what lies beyond the slice is what scope: out is for (0020), and a row is
        # not an exception to it.
        document = table_map()
        document["entries"][6]["locator"]["citation"] = (
            '§ 1.10 table 2, row [column 1 = "A3"]')       # subpart-d-categories, scope: out
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_the_row_is_read_as_the_locator_checker_reads_it(self):
        # One grammar in two files, as CITE_SECTION already is: the checker resolves the
        # citation against the corpus and this places it inside the extent, and the two must
        # read the same table and the same key out of it.
        repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        spec = importlib.util.spec_from_file_location(
            "check_locators_section",
            os.path.join(repo, "examples", "faa-part-107", "check-locators-section.py"))
        section_tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(section_tool)
        citations = ['§ 1.10 table 1, row [column 2 = "Acetal"]',
                     '§ 1.10 table 1, row [column 2 = "Acetal"], column 4A',
                     '§ 1.10 table 1, row [column 2 = "Ammonia, anhydrous"; column 1 = "G"]']
        for citation in citations:
            with self.subTest(citation=citation):
                section, table, selector, _ = section_tool.table_citation(citation)
                self.assertEqual(selector[0], "key")
                self.assertEqual(check_map.cited_row(citation),
                                 (section, table, frozenset(selector[1])))
        # A row named below the row above it (0043) is read by both, and this file keeps only the
        # table: no declared row key names such a row, so there is no key to compare.
        below = '§ 1.10 table 1, row blank in column 2 below row [column 2 = "Acetal"]'
        section, table, selector, _ = section_tool.table_citation(below)
        self.assertEqual(selector, ("below", "2", [("2", "Acetal")], []))
        self.assertEqual(check_map.cited_row(below), (section, table, None))
        for outside in ["§ 1.10(a)", "subpart D", "Part One / p. 1",
                        '§ 1.10 table 1, row [the second one]']:
            with self.subTest(citation=outside):
                self.assertIsNone(section_tool.table_citation(outside))
                self.assertIsNone(check_map.cited_row(outside))


class TestRequiredFields(MapCase):
    def test_an_entry_without_a_locator_is_not_an_entry(self):
        self.assert_catches("required-fields", lambda d: d["entries"][0].pop("locator"), message='missing required field `locator`')

    def test_a_locator_without_a_citation_fails(self):
        self.assert_catches("required-fields", lambda d: d["entries"][0]["locator"].pop("citation"), message='locator is missing `citation`')

    def test_a_missing_status_fails(self):
        self.assert_catches("required-fields", lambda d: d["entries"][2].pop("status"), message='missing required field `status`')


class TestVocabulary(MapCase):
    def test_kind_outside_the_closed_vocabulary_fails(self):
        # The live instance: `direction-of-travel` shipped as kind "rule" in both copies
        # of the backgammon map because nothing consumed `kind`.
        self.assert_catches("vocabulary", lambda d: d["entries"][0].update(kind="rule"), message="kind is 'rule', outside {assertion, operation, value}")

    def test_scope_outside_the_closed_vocabulary_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][0].update(scope="partial"), message="scope is 'partial', outside {in, out}")

    def test_clarity_outside_the_closed_vocabulary_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][0].update(clarity="murky"), message="clarity is 'murky', outside {ambiguous, clear}")

    def test_status_outside_the_closed_vocabulary_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][0].update(status="in-progress"), message="status is 'in-progress', outside {blocked, declined")

    def test_fate_outside_the_closed_vocabulary_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][7]["ambiguity"].update(fate="deferred"), message="ambiguity.fate is 'deferred', outside {decision, unresolved}")

    def test_an_unresolved_reason_outside_the_kernel_enum_fails(self):
        self.assert_catches(
            "vocabulary",
            lambda d: d["entries"][7]["ambiguity"].update(unresolvedReason="CorpusDisagreesWithItself"), message="unresolvedReason is 'CorpusDisagreesWithItself', outside",
        )

    def test_beyond_adapter_without_a_modality_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][5]["beyondAdapter"].pop("modality"), message='beyondAdapter is missing `modality`')


class TestUniqueIds(MapCase):
    def test_a_duplicated_id_fails(self):
        self.assert_catches("unique-ids", lambda d: d["entries"][1].update(id="speed-limit"), message='id used by entry[0] as well')


class TestReferences(MapCase):
    def test_a_dangling_depends_on_fails(self):
        self.assert_catches("references", lambda d: d["entries"][1].update(dependsOn=["no-such-entry"]), message="dependsOn names 'no-such-entry'")

    def test_a_dangling_enabled_by_fails(self):
        # 0003: a gate with no entry means the map is missing an entry.
        self.assert_catches("references", lambda d: d["entries"][3].update(enabledBy=["all-men-home"]), message="enabledBy names 'all-men-home'")

    def test_a_dangling_suspended_by_fails(self):
        self.assert_catches("references", lambda d: d["entries"][3].update(suspendedBy=["man-on-bar"]), message="suspendedBy names 'man-on-bar'")

    def test_a_gate_holding_a_condition_rather_than_an_id_fails(self):
        self.assert_catches("references", lambda d: d["entries"][3].update(suspendedBy=[{"onBar": True}]), message="suspendedBy holds {'onBar': True}")

    def test_a_map_with_no_edges_does_not_report_ok(self):
        document = valid_map()
        for item in document["entries"]:
            item["dependsOn"] = []
            item.pop("enabledBy", None)
            item.pop("suspendedBy", None)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "references"), "skip", output)
        self.assertEqual(self.status_of(output, "no-cycles"), "skip", output)
        self.assertEqual(self.status_of(output, "gates"), "skip", output)
        self.assertEqual(code, 0, output)


class TestGates(MapCase):
    """0011: a gate is filed by direction -- what makes a rule reachable, what suspends it."""

    GATED = 3  # yield-right-of-way, in valid_map()'s order

    def test_an_undirected_gated_by_is_refused(self):
        # The field 0011 split. Left unchecked, an unmigrated map's gates would simply vanish.
        def mutate(document):
            gated = document["entries"][self.GATED]
            gated["gatedBy"] = gated.pop("enabledBy") + gated.pop("suspendedBy")
        self.assert_catches("gates", mutate, message='carries `gatedBy`, which 0011 split by direction')

    def test_one_rule_both_enabling_and_suspending_an_entry_fails(self):
        self.assert_catches(
            "gates", lambda d: d["entries"][self.GATED]["suspendedBy"].append("speed-limit"), message="names 'speed-limit' in both `enabledBy` and `suspendedBy`")

    def test_a_map_with_no_gates_does_not_report_ok(self):
        # A map with no gates, like the Part 107 temporal map: nothing was checked, and it proves nothing.
        document = valid_map()
        document["entries"][self.GATED].pop("enabledBy")
        document["entries"][self.GATED].pop("suspendedBy")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "gates"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)


class TestApplicabilityReach(MapCase):
    """#225: a rule whose own words gate a whole section, and no entry says it is gated.

    § 1.121-1(f) -- *"This section is applicable for sales and exchanges on or after December 24,
    2002"* -- gates everything § 1.121-1 states. Map A recorded the entry and no entry pointed at
    it, so every rule it gates was recorded as applying unconditionally; Map C added 30
    `enabledBy` edges. Every check passed Map A.
    """

    GATE = -1  # effective-date, appended by applicability_map()

    def assert_reach(self, document, expect, message=None):
        """`applicability-reach` reaches `expect` on this map, saying `message` when it refuses.

        The standing helper cannot be used: it starts from `valid_map()`, whose words gate no
        whole unit, so this check reports NOT VERIFIED there rather than `ok`. The obligation
        #283 puts on it is kept by hand -- a refusal is asserted by its words, never only by
        its verdict.
        """
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "applicability-reach"), expect, output)
        self.assertEqual(code, 1 if expect == "fail" else 0, output)
        if message:
            self.assertIn(message, output)
        return output

    def test_the_gated_map_passes_and_the_same_map_without_the_edge_fails(self):
        self.assert_reach(applicability_map(), "ok")
        document = applicability_map()
        document["entries"][1].pop("enabledBy")
        self.assert_reach(document, "fail",
                          "gate the whole section, and no entry names it in `enabledBy`")

    def test_a_gate_the_map_reaches_by_suspension_passes(self):
        # `suspendedBy` is a reach too: a rule that switches a section off gates it.
        document = applicability_map()
        document["entries"][1].pop("enabledBy")
        document["entries"][1]["suspendedBy"] = ["first-day"]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "applicability-reach"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_citation_that_merely_mentions_the_unit_is_not_a_gate(self):
        # § 172.102(c)(7)(ii): "§ 178.275(g)(3) of this subchapter does not apply" gates one
        # cited paragraph, not the subchapter, and the committed hazmat map carries it.
        document = valid_map()
        document["entries"][0]["evidence"] = (
            "Column 4 specifies the applicability of the pressure rule. When the word "
            "\"Normal\" is indicated, that rule of this subchapter does not apply.")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "applicability-reach"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_an_out_of_scope_gate_is_not_flagged(self):
        document = applicability_map()
        document["entries"][1].pop("enabledBy")
        document["entries"][self.GATE]["scope"] = "out"
        document["entries"][self.GATE]["status"] = "declined"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "applicability-reach"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_a_map_whose_words_gate_nothing_does_not_report_ok(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "applicability-reach"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)

    def test_the_first_tax_map_is_flagged_and_the_committed_map_is_not(self):
        # #225's own acceptance, run against the two maps it names. Map A is trial 9's blind
        # first mapping and is committed evidence; nothing else in this repository checks it.
        repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        first = os.path.join(repo, "examples", "tax-121-principal-residence",
                             "blind-mapping", "first-map.json")
        committed = os.path.join(repo, "examples", "tax-121-principal-residence",
                                 "corpus-map.json")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_map.main([first, "--only", "applicability-reach"])
        output = out.getvalue() + err.getvalue()
        self.assertEqual(code, 1, output)
        self.assertIn("effective-date", output)
        self.assertIn("gate the whole section", output)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_map.main([committed, "--only", "applicability-reach"])
        output = out.getvalue() + err.getvalue()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.status_of(output, "applicability-reach"), "ok", output)

    def test_every_committed_map_states_the_reach_of_the_gates_it_records(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        for path in sorted(glob.glob(os.path.join(repo, "examples", "*", "corpus-map*.json"))):
            with self.subTest(map=os.path.relpath(path, repo)):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = check_map.main([path, "--only", "applicability-reach"])
                output = out.getvalue() + err.getvalue()
                self.assertNotEqual(self.status_of(output, "applicability-reach"), "fail", output)


class TestNoCycles(MapCase):
    def test_a_depends_on_cycle_fails(self):
        def mutate(document):
            document["entries"][0]["dependsOn"] = ["speed-within-limit"]
        self.assert_catches("no-cycles", mutate, message='dependsOn cycle: speed-limit -> speed-within-limit ->')

    def test_mutual_gates_are_not_a_cycle(self):
        # A gate orders nothing, so a mutual gate is legitimate and must still pass.
        document = valid_map()
        document["entries"][0]["suspendedBy"] = ["speed-within-limit"]
        document["entries"][1]["suspendedBy"] = ["speed-limit"]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "no-cycles"), "ok", output)
        self.assertEqual(code, 0, output)


class TestDerived(MapCase):
    """0012: `derivedFrom` -- this fact is entailed by those facts, and no sentence states it."""

    DERIVED = 10  # hit-pays-single-stake, in valid_map()'s order

    def test_a_derived_entry_needs_no_locator_or_evidence(self):
        # The fixture's derived entry carries neither, and required-fields must not demand them.
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "required-fields"), "ok", output)
        self.assertEqual(self.status_of(output, "derived"), "ok", output)

    def test_an_entry_without_derived_from_still_needs_its_locator(self):
        # The exemption is keyed on the field, so removing it makes the entry an ordinary one.
        self.assert_catches("required-fields", lambda d: d["entries"][self.DERIVED].pop("derivedFrom"), message='missing required field `locator`')

    def test_a_derived_entry_that_quotes_a_span_fails(self):
        # `evidence` keeps one meaning: a verbatim span. A derived fact has none to quote.
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED].update(evidence="A gammon pays double."), message='is derived and carries `evidence`')

    def test_a_derived_entry_that_cites_a_passage_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED].update(
                locator={"sourceId": "demo-corpus", "citation": "Part One / p. 1"}), message='is derived and carries `locator`')

    def test_a_derived_entry_carrying_a_cross_reference_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED].update(
                crossReferences=[{"cites": "as at starting", "resolvedBy": "speed-limit"}]), message='is derived and carries `crossReferences`')

    def test_a_source_that_is_not_an_entry_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED]["derivedFrom"].append("no-such-entry"), message="derivedFrom names 'no-such-entry'")

    def test_a_source_out_of_scope_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED]["derivedFrom"].append("subpart-d-categories"), message="derivedFrom names 'subpart-d-categories'")

    def test_deriving_from_an_absent_rule_fails(self):
        # An absence is scope: out, so the scope rule is what refuses it.
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED]["derivedFrom"].append("doubling-cube"), message="derivedFrom names 'doubling-cube'")

    def test_a_derivation_from_one_source_fails(self):
        # A consequence of one entry is that entry's, discharged as a test it names.
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED].update(derivedFrom=["speed-limit"]), message='`derivedFrom` names 1 source(s)')

    def test_a_derivation_naming_itself_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED]["derivedFrom"].append("hit-pays-single-stake"), message='derivedFrom names itself')

    def test_a_circular_derivation_fails(self):
        def mutate(document):
            document["entries"].append(
                derived_entry("gammon-pays-double", ["hit-pays-single-stake", "speed-limit"]))
            document["entries"][self.DERIVED]["derivedFrom"] = ["gammon-pays-double", "speed-limit"]
        self.assert_catches("derived", mutate, message='derivedFrom cycle: hit-pays-single-stake ->')

    def test_a_map_with_no_derived_entries_does_not_report_ok(self):
        document = valid_map()
        document["entries"].pop(self.DERIVED)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "derived"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)


class TestManifest(MapCase):
    def test_a_locator_source_not_in_the_manifest_fails(self):
        self.assert_catches("manifest", lambda d: d["entries"][0]["locator"].update(sourceId="unknown-corpus"), message="locator.sourceId 'unknown-corpus' is not declared in the")

    def test_a_beyond_adapter_naming_the_wrong_adapter_fails(self):
        # 0004: the adapter must match the one declared for the entry's source.
        self.assert_catches("manifest", lambda d: d["entries"][5]["beyondAdapter"].update(adapter="pdf"), message="beyondAdapter.adapter is 'pdf', but demo-corpus declares")

    def test_a_defined_elsewhere_reference_not_in_references_fails(self):
        # 0005: an elsewhere-defined *input* has no corpus to name and would not validate.
        self.assert_catches("manifest", lambda d: d["entries"][4]["definedElsewhere"].update(reference="airspace"), message="definedElsewhere.reference 'airspace' is not in")

    def test_a_baseline_disagreeing_with_the_manifest_fails(self):
        self.assert_catches("manifest", lambda d: d["baseline"].update(contentHash="b" * 64), message="baseline contentHash 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    def test_a_defined_elsewhere_naming_the_maps_own_corpus_fails(self):
        # 0026, #115: the SRD's Rules Glossary is the same corpus as its combat chapter. A term
        # defined there is a `scope: out` entry, not a reference to a corpus that was not admitted.
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0]["references"].append({"sourceId": "demo-corpus", "admitted": False})
        self.write_manifest(manifest)
        document = valid_map()
        document["entries"][4]["definedElsewhere"] = {"reference": "demo-corpus"}
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "manifest"), "fail", output)
        self.assertIn("a corpus that was admitted", output)
        self.assertIn("`scope: out` entry", output)
        self.assertEqual(code, 1, output)

    def test_a_defined_elsewhere_naming_a_reference_marked_admitted_fails(self):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0]["references"][0]["admitted"] = True
        self.write_manifest(manifest)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "manifest"), "fail", output)
        self.assertIn("a corpus that was admitted", output)
        self.assertEqual(code, 1, output)

    def test_a_defined_elsewhere_naming_a_reference_not_admitted_passes(self):
        # The other way: the fixture's hazardous-material names `other-corpus`, admitted: false.
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "manifest"), "ok", output)
        self.assertNotIn("a corpus that was admitted", output)
        self.assertEqual(code, 0, output)

    def test_without_a_manifest_the_check_skips_and_fails_the_run(self):
        os.remove(self.manifest_path)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "manifest"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 1, output)


class TestExtraction(MapCase):
    """0024: quotes of an extraction are declared so, and a garbled one declares its defect."""

    GARBLED = 9  # next-game-opening, in valid_map()'s order

    def manifest_without(self, mutate):
        manifest = json.loads(json.dumps(MANIFEST))
        mutate(manifest["corpora"][0])
        self.write_manifest(manifest)

    def test_the_fixture_declaration_and_defect_pass(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "extraction"), "ok", output)
        self.assertIn("1 renderedReading not verified here", output)

    def test_a_defect_outside_the_closed_list_fails(self):
        self.assert_catches("extraction", lambda d: d["entries"][self.GARBLED]["extraction"]
                            .update(defect="joined-hyphenation"), message="extraction.defect is 'joined-hyphenation', outside")

    def test_a_defect_without_a_rendered_reading_fails(self):
        self.assert_catches("extraction", lambda d: d["entries"][self.GARBLED]["extraction"]
                            .pop("renderedReading"), message='extraction names no `renderedReading`, the passage as read')

    def test_a_rendered_reading_that_is_the_evidence_fails(self):
        def mutate(document):
            garbled = document["entries"][self.GARBLED]
            garbled["extraction"]["renderedReading"] = "  " + garbled["evidence"].replace(" ", "\n")
        self.assert_catches("extraction", mutate, message='renderedReading is the evidence itself')

    def test_an_unknown_field_of_extraction_fails(self):
        self.assert_catches("extraction", lambda d: d["entries"][self.GARBLED]["extraction"]
                            .update(checkedBy="a person"), message='`checkedBy` is not a field of extraction (defect')

    def test_an_extraction_that_is_not_an_object_fails(self):
        self.assert_catches("extraction", lambda d: d["entries"][self.GARBLED]
                            .update(extraction="interleaved-table"), message='extraction is not an object {defect, renderedReading}')

    def test_extraction_beside_beyond_adapter_fails(self):
        self.assert_catches("extraction", lambda d: d["entries"][self.GARBLED].update(
            beyondAdapter={"adapter": "plain-text", "modality": "table"}), message='carries both extraction and beyondAdapter')

    def test_a_defect_on_a_corpus_not_declaring_quoted_text_fails(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(code, 0, output)
        self.manifest_without(lambda corpus: corpus.pop("quotedText"))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "extraction"), "fail", output)
        self.assertIn("declares no `quotedText`", output)

    def test_quoted_text_naming_another_derivation_fails(self):
        self.manifest_without(lambda corpus: corpus["quotedText"].update(derivation="pdf-bytes"))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "extraction"), "fail", output)
        self.assertIn("not the corpus's hashDerivation", output)

    def test_quoted_text_naming_nothing_extracted_fails(self):
        self.manifest_without(lambda corpus: corpus["quotedText"].pop("extractedFrom"))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "extraction"), "fail", output)
        self.assertIn("names no `extractedFrom`", output)

    def test_quoted_text_that_is_not_an_object_fails(self):
        self.manifest_without(lambda corpus: corpus.update(quotedText="the pdftotext output"))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "extraction"), "fail", output)

    def test_an_unknown_field_of_quoted_text_fails(self):
        self.manifest_without(lambda corpus: corpus["quotedText"].update(normalised=True))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "extraction"), "fail", output)

    def test_a_derived_entry_carrying_extraction_fails(self):
        self.assert_catches("derived", lambda d: d["entries"][10].update(
            extraction={"defect": "interleaved-table", "renderedReading": "Half | +2"}), message='is derived and carries `extraction`')

    def test_nothing_declared_skips_without_failing_the_run(self):
        document = valid_map()
        document["entries"][self.GARBLED].pop("extraction")
        self.manifest_without(lambda corpus: corpus.pop("quotedText"))
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extraction"), "skip", output)


class TestPostures(MapCase):
    """0013: each corpus declares how it is verified and whether a map may quote it."""

    def assert_manifest_catches(self, mutate, document=None):
        """The fixture manifest passes `postures`; the mutated one makes it fail."""
        code, output = self.run_tool(document or valid_map())
        self.assertEqual(self.status_of(output, "postures"), "ok", output)
        manifest = json.loads(json.dumps(MANIFEST))
        mutate(manifest)
        self.write_manifest(manifest)
        code, output = self.run_tool(document or valid_map())
        self.assertEqual(self.status_of(output, "postures"), "fail", output)
        self.assertEqual(code, 1, output)
        return output

    def test_a_corpus_with_no_verification_posture_fails(self):
        self.assert_manifest_catches(lambda m: m["corpora"][0].pop("verification"))

    def test_a_posture_outside_the_vocabulary_fails(self):
        self.assert_manifest_catches(lambda m: m["corpora"][0].update(verification="trust-me"))

    def test_a_corpus_with_no_quotation_policy_fails(self):
        self.assert_manifest_catches(lambda m: m["corpora"][0].pop("quotation"))

    def test_a_corpus_with_no_randomness_declared_fails(self):
        output = self.assert_manifest_catches(lambda m: m["corpora"][0].pop("randomness"))
        self.assertIn("randomness is None", output)

    def test_randomness_outside_the_vocabulary_fails(self):
        # `true` is not a declaration of how: 0019 names the source, seeded and replayable.
        for value in ("dice", True, "unseeded"):
            with self.subTest(value=value):
                self.write_manifest(MANIFEST)
                self.assert_manifest_catches(lambda m: m["corpora"][0].update(randomness=value))

    def test_both_randomness_declarations_pass_and_are_reported(self):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"].append(COMMERCIAL)
        self.write_manifest(manifest)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "postures"), "ok", output)
        self.assertIn("core-rules: local-copy, withheld, randomness seeded", output)
        self.assertIn("demo-corpus: committed-copy, verbatim, randomness none", output)

    def test_a_committed_copy_that_is_not_committed_fails(self):
        self.assert_manifest_catches(lambda m: m["corpora"][0].update(committedPath="missing.txt"))

    def test_a_committed_copy_naming_no_path_fails(self):
        self.assert_manifest_catches(lambda m: m["corpora"][0].pop("committedPath"))

    def test_a_never_commit_corpus_claiming_a_committed_copy_fails(self):
        def mutate(manifest):
            manifest["corpora"].append(dict(COMMERCIAL, verification="committed-copy",
                                            committedPath="demo.txt"))
        output = self.assert_manifest_catches(mutate)
        self.assertIn("cannot be verified from it", output)

    def test_a_local_copy_naming_no_env_var_fails(self):
        def mutate(manifest):
            commercial = dict(COMMERCIAL)
            commercial.pop("envVar")
            manifest["corpora"].append(commercial)
        self.assert_manifest_catches(mutate)

    def test_a_licensed_corpus_declared_properly_passes(self):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"].append(COMMERCIAL)
        self.write_manifest(manifest)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "postures"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_quoting_a_corpus_whose_quotation_is_withheld_fails(self):
        # For a never-commit corpus the map itself is the redistribution question.
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"].append(COMMERCIAL)
        self.write_manifest(manifest)
        document = _without_evidence_on_last(valid_map())
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "postures"), "ok", output)
        self.assertEqual(code, 0, output)
        document["entries"][-1]["evidence"] = "Compare the hits scored by each side."
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "postures"), "fail", output)
        self.assertIn("quotes `evidence`", output)
        self.assertEqual(code, 1, output)

    def test_an_entry_of_a_withheld_corpus_needs_no_evidence(self):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"].append(COMMERCIAL)
        self.write_manifest(manifest)
        document = _without_evidence_on_last(valid_map())
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "required-fields"), "ok", output)
        self.assertEqual(self.status_of(output, "postures"), "ok", output)
        # Without the withheld policy the same entry is simply missing its evidence.
        self.write_manifest(MANIFEST)
        document["entries"][-1]["locator"] = {"sourceId": "demo-corpus", "citation": "p. 36"}
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "required-fields"), "fail", output)

    def test_without_a_manifest_the_postures_are_not_verified(self):
        os.remove(self.manifest_path)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "postures"), "skip", output)
        self.assertEqual(code, 1, output)


def _without_evidence_on_last(document):
    """Append an entry citing the withheld corpus, carrying no span -- as 0013 requires.

    The page it cites is inside the map's declared extent, because #269 places a page citation
    the way this check has always placed a section one and the extent is one range for the whole
    map (0042). What this helper is about is an entry with no `evidence`, not an entry outside
    the slice, and p. 36 would now be both.
    """
    document["entries"].append(entry("opposed-test-tie", locator={
        "sourceId": "core-rules", "citation": "Game Concepts / p. 1"}))
    document["entries"][-1].pop("evidence")
    return document


class TestAnEntryMayBeDefinedElsewhereAndAmbiguousHere(MapCase):
    """0059 dropped the exclusion, and these are the two halves of what replaced it.

    Until 0059 `exclusions` refused `definedElsewhere` or `beyondAdapter` beside an `ambiguity`
    block, "to keep two rows of the correspondence table from firing with different answers".
    The table gained an order after that was written, so the pair has one answer -- row 3 or 4,
    `MissingRulesData` -- and the exclusion was costing a true fact: `method-of-allocation`
    defers a term to an unadmitted statute *and* leaves a gap of its own.
    """

    def _both(self, document, index):
        """Give entry `index` an ambiguity block anchored in its own evidence (#271)."""
        entry_id = document["entries"][index]["id"]
        document["entries"][index]["clarity"] = "ambiguous"
        document["entries"][index]["ambiguity"] = {
            "question": (f"\"The sentence stating {entry_id}.\" states the rule and the term it "
                         f"turns on is fixed in a corpus that was not admitted, and where that "
                         f"corpus does not reach the sentence settles nothing."),
            "fate": "unresolved",
            "unresolvedReason": "MissingRulesData",
        }

    def test_defined_elsewhere_beside_an_ambiguity_block_is_accepted(self):
        """Watched failing with the `definedElsewhere` arm of `check_exclusions` restored."""
        document = valid_map()
        self._both(document, 4)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "exclusions"), "ok", output)
        self.assertEqual(self.status_of(output, "unresolved-reason"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_beyond_adapter_beside_an_ambiguity_block_is_accepted(self):
        """Watched failing with the `beyondAdapter` arm of `check_exclusions` restored."""
        document = valid_map()
        self._both(document, 5)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "exclusions"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_such_an_entry_may_not_claim_an_interpretation_is_what_is_missing(self):
        """Row 3 wins, so `RequiresInterpretation` is a reason no row gives this entry.

        Watched failing by restoring `allowed = {OPEN_QUESTION_REASON}` unconditionally in
        `check_unresolved_reason`.
        """
        def mutate(document):
            self._both(document, 4)
            document["entries"][4]["ambiguity"]["unresolvedReason"] = "RequiresInterpretation"
        self.assert_catches("unresolved-reason", mutate,
                            message="sent to interpret what a definition they can go and get would settle")

    def test_an_entry_with_no_such_field_still_may_not_claim_missing_data(self):
        """The other direction, unchanged by 0059: row 6 is what an ordinary open question gets."""
        def mutate(document):
            document["entries"][7]["ambiguity"]["unresolvedReason"] = "MissingRulesData"
        self.assert_catches("unresolved-reason", mutate,
                            message="what is missing is an interpretation nobody has made")


class TestTheReasonIsInheritedAcrossAnEdge(MapCase):
    """#226: a missing definition dominates an open question one `dependsOn` edge away.

    Trial 9's two mappers got this wrong from opposite sides, and the adjudication stated the
    rule: `definedElsewhere` relocates the reason an entry declines, and never converts a decline
    into an answer. An entry that cannot be resolved without a corpus nobody admitted returns
    `MissingRulesData`, whatever its own question says.
    """

    def _run(self, depends_on, reason=None):
        """The fixture's one open question, pointed at `depends_on`.

        Not `assert_catches`: this check reports NOT VERIFIED on a map with no open question
        depending on a deferring entry, which the valid fixture is, and that helper asserts `ok`
        on the valid map first. A check that skips where it has no subject is the repository's
        own rule, so the helper is the wrong shape here rather than the check.
        """
        document = valid_map()
        document["entries"][7]["dependsOn"] = list(depends_on)
        if reason is not None:
            document["entries"][7]["ambiguity"]["unresolvedReason"] = reason
        return self.run_tool(document)

    def test_the_valid_fixture_has_no_subject_and_says_so(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "inherited-reason"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_an_open_question_depending_on_a_deferring_entry_fails(self):
        """Watched failing by pointing `dependsOn` at `subpart-d-categories`, which defers to
        nothing: the check goes back to NOT VERIFIED and this assertion fails."""
        code, output = self._run(["hazardous-material"])
        self.assertEqual(self.status_of(output, "inherited-reason"), "fail", output)
        self.assertEqual(code, 1, output)
        self.assertIn("The reason is inherited", output)
        self.assertIn("hazardous-material", output)

    def test_the_same_edge_to_an_entry_that_defers_to_nothing_is_fine(self):
        code, output = self._run(["subpart-d-categories"])
        self.assertNotEqual(self.status_of(output, "inherited-reason"), "fail", output)
        self.assertEqual(code, 0, output)

    def test_an_edge_to_a_beyond_adapter_entry_is_the_same_rule(self):
        """Row 4 inherits exactly as row 3 does. Watched failing by dropping `beyondAdapter`
        from the fields `deferring` is built from."""
        code, output = self._run(["inner-table-handedness"])
        self.assertEqual(self.status_of(output, "inherited-reason"), "fail", output)
        self.assertIn("which defer(s) to a corpus that was not admitted", output)

    def test_an_inheriting_entry_that_names_the_inherited_reason_is_accepted(self):
        """The fix the refusal asks for, proved accepted rather than merely described."""
        code, output = self._run(["hazardous-material"], reason="MissingRulesData")
        self.assertNotEqual(self.status_of(output, "inherited-reason"), "fail", output)
        self.assertEqual(code, 0, output)


class TestAReferenceMayNameAClass(MapCase):
    """0059: a class of corpora says so, because an absent `citation` cannot say it.

    Two manifests declare `air-almanac` with no citation and the Air Almanac is one publication,
    cited by name. So the marker is explicit and the absence means nothing.
    """

    def _manifest_with(self, reference):
        import copy
        manifest = copy.deepcopy(MANIFEST)
        manifest["corpora"][0].setdefault("references", []).append(reference)
        return manifest

    def test_a_class_with_a_citation_fails(self):
        """Watched failing by dropping the `citation is not None` arm."""
        self.write_manifest(self._manifest_with(
            {"sourceId": "local-law", "admitted": False, "class": True,
             "citation": "§ 1", "note": "The property law of the jurisdiction."}))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "manifest"), "fail", output)
        self.assertIn("a class of corpora has no one publication to cite", output)

    def test_a_class_with_no_note_fails(self):
        """Watched failing by dropping the `note` arm."""
        self.write_manifest(self._manifest_with(
            {"sourceId": "local-law", "admitted": False, "class": True}))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "manifest"), "fail", output)
        self.assertIn("says in no `note` what the class is", output)

    def test_a_well_formed_class_is_accepted(self):
        self.write_manifest(self._manifest_with(
            {"sourceId": "local-law", "admitted": False, "class": True,
             "note": "The property law of whichever jurisdiction the residence sits in."}))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "manifest"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_reference_cited_by_name_needs_no_marker(self):
        """The Air Almanac's shape: no citation, no class, and nothing owed."""
        self.write_manifest(self._manifest_with({"sourceId": "air-almanac", "admitted": False}))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "manifest"), "ok", output)
        self.assertEqual(code, 0, output)


class TestExclusions(MapCase):
    def test_an_ambiguity_block_on_a_clear_entry_fails(self):
        def mutate(document):
            document["entries"][7]["clarity"] = "clear"
        self.assert_catches("exclusions", mutate, message='clarity is `clear` but an `ambiguity` block is present')

    def test_an_ambiguous_entry_without_an_ambiguity_block_fails(self):
        def mutate(document):
            document["entries"][7].pop("ambiguity")
        self.assert_catches("exclusions", mutate, message='clarity is `ambiguous` but no `ambiguity` block states the')

    def test_a_decision_fate_naming_no_record_fails(self):
        def mutate(document):
            document["entries"][7]["ambiguity"] = {
                "question": "Two readings.",
                "fate": "decision",
            }
        self.assert_catches("exclusions", mutate, message='fate is `decision` but no record is named')

    def test_an_unresolved_fate_without_its_reason_fails(self):
        self.assert_catches("exclusions", lambda d: d["entries"][7]["ambiguity"].pop("unresolvedReason"), message='fate is `unresolved` but no `unresolvedReason` ties it to')


class TestStatus(MapCase):
    def test_implemented_without_implemented_in_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0].pop("implementedIn"), message='status is `implemented` but no `implementedIn` names the')

    def test_implemented_in_on_an_unbuilt_entry_fails(self):
        self.assert_catches("status", lambda d: d["entries"][2].update(implementedIn={"ruleset": "demo", "version": 1}), message="carries `implementedIn` while status is 'mapped'")

    def test_implemented_naming_no_tests_fails(self):
        # #2: `implemented` stops being a word someone typed. Without tests it is `mapped`.
        self.assert_catches("status", lambda d: d["entries"][0].pop("tests"), message='status is `implemented` but `tests` names no test that')

    def test_implemented_with_an_empty_tests_list_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0].update(tests=[]), message='status is `implemented` but `tests` names no test that')

    def test_a_test_with_no_recorded_mutation_fails(self):
        # A test nobody has seen go red is the class of test this repository keeps finding.
        self.assert_catches("status", lambda d: d["entries"][1]["tests"][1].pop("mutation"), message="tests[1] ('SpeedTests.Above_the_limit_is_refused') records")

    def test_a_blank_mutation_fails(self):
        self.assert_catches("status", lambda d: d["entries"][1]["tests"][0].update(mutation="  "), message="tests[0] ('SpeedTests.At_the_limit_is_permitted') records")

    def test_a_tests_item_naming_no_test_fails(self):
        self.assert_catches("status", lambda d: d["entries"][1]["tests"][0].pop("test"), message='tests[0] names no `test`')

    def test_a_test_named_twice_fails(self):
        def mutate(document):
            tests = document["entries"][1]["tests"]
            tests[1]["test"] = tests[0]["test"]
        self.assert_catches("status", mutate, message="names test 'SpeedTests.At_the_limit_is_permitted' twice")

    def test_a_bare_test_name_without_its_mutation_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0].update(tests=["SpeedLimitTests.The_limit_is_87_knots"]), message='tests[0] is not an object naming a test and its mutation')

    def test_malformed_tests_on_an_unbuilt_entry_still_fail(self):
        # The shape holds wherever the field appears, not only where it is required.
        self.assert_catches("status", lambda d: d["entries"][2].update(tests=[{"test": "WellClearTests.X"}]), message="tests[0] ('WellClearTests.X') records no `mutation`")

    # #240: a placeholder is not a mutation, and the checker a published map package carries
    # refuses one before any engine merges the map. Every test below names the exact refusal
    # rather than only the verdict, because `tests_problems` holds four other rules that also
    # turn `status` red -- no `mutation`, a `tests` item that is not an object, a missing `test`,
    # a test named twice -- and any of them would satisfy a verdict-only assertion while the
    # placeholder rule went unexercised (#283). The reason is asserted too, not just the
    # refusal: "is a placeholder" means normalisation read the word, where "too short" would
    # mean only the floor caught it.
    def test_a_placeholder_mutation_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0]["tests"][0].update(mutation="PENDING"),
                            message="records 'PENDING', which is a placeholder, not a mutation")

    def test_a_mutation_of_placeholder_words_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0]["tests"][0].update(mutation="todo -- pending, tbd"),
                            message="which is a placeholder, not a mutation")

    def test_a_placeholder_spelled_in_unicode_fails(self):
        # Fullwidth TODO. It is the normalisation that reads this as the word; without NFKD it
        # is three distinct-looking characters and the placeholder rule never sees a placeholder.
        self.assert_catches("status", lambda d: d["entries"][0]["tests"][0].update(mutation="ＴＯＤＯ"),
                            message="which is a placeholder, not a mutation")

    def test_one_word_repeated_fails(self):
        # A Cyrillic capital O where the Latin O belongs, repeated three times. No confusable
        # mapping is done, so this is refused for being one word repeated and never read as
        # `TODO` -- which is the claim the rule makes and the size of claim it keeps.
        self.assert_catches("status", lambda d: d["entries"][0]["tests"][0].update(mutation="TОDO TОDO TОDO"),
                            message="which is one word repeated, not a mutation")

    def test_a_mutation_under_the_word_floor_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0]["tests"][0].update(mutation="comparison inverted"),
                            message="which is too short to be a mutation: at least 3 words and 12 characters")

    def test_a_mutation_under_the_character_floor_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0]["tests"][0].update(mutation="abc def gh"),
                            message="which is too short to be a mutation: at least 3 words and 12 characters")

    def test_the_refusal_says_what_it_cannot_tell(self):
        # The floor refuses an unfilled placeholder and nothing else. A reader who is told only
        # "that is not a mutation" will read the passing case as "the test was watched failing",
        # which this check has never been able to say.
        self.assert_catches("status", lambda d: d["entries"][0]["tests"][0].update(mutation="TBD"),
                            message="it cannot tell whether the edit was made or the test went red")

    def test_a_real_mutation_at_the_floor_passes(self):
        # The floor is set far below any real mutation on purpose: refusing honest work blocks
        # it and teaches people to pad. Exactly three words and exactly twelve characters pass.
        document = valid_map()
        document["entries"][0]["tests"][0]["mutation"] = "abc def ghij"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "status"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_placeholder_word_inside_a_real_mutation_passes(self):
        document = valid_map()
        document["entries"][0]["tests"][0]["mutation"] = (
            "Handlers.SpeedLimit answered none where the map says pending review is unknown "
            "to it; this test went red.")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "status"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_placeholder_on_an_unbuilt_entry_still_fails(self):
        # The shape of `tests` holds wherever the field appears, not only where it is required,
        # and so does what a mutation must be.
        self.assert_catches("status", lambda d: d["entries"][2].update(
            tests=[{"test": "WellClearTests.X", "mutation": "TODO"}]),
            message="which is a placeholder, not a mutation")

    def test_a_map_with_nothing_built_does_not_report_ok(self):
        # All three example maps are in this state. Reporting `ok` would be a gate
        # trusted for proving something it never looked at.
        document = valid_map()
        for item in document["entries"]:
            item.pop("implementedIn", None)
            item.pop("tests", None)
            if item["status"] == "implemented":
                item["status"] = "mapped"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "status"), "skip", output)
        self.assertEqual(code, 0, output)


class TestDecisionRecords(MapCase):
    def _map_with_decision(self):
        document = valid_map()
        document["entries"].append(decided_entry())
        return document

    def test_a_named_record_that_exists_passes_this_check(self):
        # The run still fails, on `conflicts` -- see TestConflicts. This asserts on the
        # check's own line, which is the claim under test.
        code, output = self.run_tool(self._map_with_decision())
        self.assertEqual(self.status_of(output, "decision-records"), "ok", output)

    def test_a_named_record_that_does_not_exist_fails(self):
        document = self._map_with_decision()
        document["entries"][-1]["ambiguity"]["decision"] = "docs/decisions/0099-never-written.md"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "decision-records"), "fail", output)
        self.assertEqual(code, 1, output)

    def test_without_a_repository_root_the_check_skips_rather_than_passing(self):
        path = os.path.join(self.example, "corpus-map.json")
        with open(path, "w") as handle:
            json.dump(self._map_with_decision(), handle)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = check_map.main([path, "--repo-root", os.path.join(self.root, "nowhere")])
        self.assertEqual(self.status_of(out.getvalue(), "decision-records"), "skip", out.getvalue())
        self.assertEqual(code, 1, out.getvalue())

    def test_with_no_decision_fates_the_check_skips_without_failing_the_run(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "decision-records"), "skip", output)
        self.assertEqual(code, 0, output)


class TestConflicts(MapCase):
    """0007: a conflict is a question, named by a slug, not a list of pairwise ids."""

    def _map_with_conflict(self, **second):
        """Two entries answering one contradicted question, both settled by one record."""
        document = valid_map()
        first = decided_entry()
        first["ambiguity"]["conflict"] = "points-open-to-an-entering-man"
        other = decided_entry()
        other["id"] = "enter-from-bar"
        other["ambiguity"] = dict(first["ambiguity"])
        other["ambiguity"].update(second)
        document["entries"] += [first, other]
        return document

    def test_a_well_formed_conflict_passes(self):
        code, output = self.run_tool(self._map_with_conflict())
        self.assertEqual(self.status_of(output, "conflicts"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_member_naming_a_different_record_fails(self):
        # 0005 B's rule, and the whole reason 0007 exists.
        document = self._map_with_conflict(decision="docs/decisions/0099-a-different-record.md")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "conflicts"), "fail", output)
        self.assertIn("name different", output)
        self.assertEqual(code, 1, output)

    def test_members_disagreeing_on_fate_fail(self):
        # One side settled and the other declined: the failure the rule is named for.
        document = self._map_with_conflict(fate="unresolved",
                                           unresolvedReason="RequiresInterpretation")
        document["entries"][-1]["ambiguity"].pop("decision")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "conflicts"), "fail", output)
        self.assertIn("disagree on `fate`", output)
        self.assertEqual(code, 1, output)

    def test_a_conflict_of_one_member_fails(self):
        # What a typo in the slug looks like, and what deleting the other side looks like.
        document = self._map_with_conflict()
        document["entries"][-1]["ambiguity"]["conflict"] = "points-open-to-an-entring-man"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "conflicts"), "fail", output)
        self.assertIn("only entry in conflict", output)
        self.assertEqual(code, 1, output)

    def test_a_slug_that_is_not_a_slug_fails(self):
        document = self._map_with_conflict()
        document["entries"][-1]["ambiguity"]["conflict"] = ["legal-destination"]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "conflicts"), "fail", output)
        self.assertEqual(code, 1, output)

    def test_a_conflict_declared_outside_the_ambiguity_block_fails(self):
        # Only an ambiguous entry can be in a conflict; a `clear` entry declaring one
        # would otherwise escape `exclusions` entirely.
        document = self._map_with_conflict()
        document["entries"][0]["conflict"] = "points-open-to-an-entering-man"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "conflicts"), "fail", output)
        self.assertIn("belongs in the `ambiguity` block", output)
        self.assertEqual(code, 1, output)

    def test_a_decision_fate_that_is_not_a_conflict_needs_no_slug(self):
        # A gap settled by a decision is not a contradiction. The old check fired on every
        # `fate: decision`, which was over-broad and failed the run on this map.
        document = valid_map()
        document["entries"].append(decided_entry())
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "conflicts"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_a_map_with_no_conflicts_does_not_report_ok(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "conflicts"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)


class TestBounds(MapCase):
    """0031: an example that bounds a term an operative rule leaves open, in a dimension a later
    ruling can be compared against -- and nothing else."""

    BOUNDED = 7  # must-play-whole-throw, in valid_map()'s order

    def bounded(self, document):
        return document["entries"][self.BOUNDED]["ambiguity"]["bounds"]

    def test_the_valid_map_is_bounded_where_this_expects(self):
        self.assertEqual(valid_map()["entries"][self.BOUNDED]["id"], "must-play-whole-throw")

    def test_a_dimension_the_checker_cannot_compare_is_refused(self):
        # The restriction the decision turns on: "adjacent", bounded by a fact pattern about a
        # road and a corner, is comparable to no threshold any ruling would state, and a field
        # that accepted it would be recorded rather than checked (0005).
        def mutate(document):
            self.bounded(document).update(dimension="adjacency")
            for example in self.bounded(document)["examples"]:
                example["value"] = "across a public road"
        self.assert_catches("bounds", mutate, message="bounds.dimension is 'adjacency'")
        document = valid_map()
        mutate(document)
        _, output = self.run_tool(document)
        self.assertIn("not a dimension this checker can compare", output)
        self.assertIn("stays prose in `ambiguity.question`", output)

    def test_bounds_that_contradict_each_other_are_refused(self):
        # An 18-month pause that is short, beside the one-year pause that is not: a threshold
        # separates two months from a year, and nothing separates these three. No reading of the
        # term satisfies all of them, so the defect is in the map and not in the corpus.
        def mutate(document):
            self.bounded(document)["examples"].append(
                {"locator": {"sourceId": "demo-corpus", "citation": "Part One / p. 1 (the longest pause)"},
                 "text": "A pause of eighteen months is a short interruption.",
                 "verdict": "applies", "value": "P18M"})
        self.assert_catches("bounds", mutate, message='the bounds contradict each other in duration. The term')
        document = valid_map()
        mutate(document)
        _, output = self.run_tool(document)
        self.assertIn("contradict each other in duration", output)

    def test_one_value_with_both_verdicts_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d)["examples"][0].update(value="P2M"), message='the bounds contradict each other in duration. The term')

    def test_one_sided_bounds_pass(self):
        # An example on one side only bounds the term from that side, and contradicts nothing.
        document = valid_map()
        self.bounded(document)["examples"] = self.bounded(document)["examples"][:1]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "bounds"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_value_that_is_not_a_duration_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d)["examples"][0].update(value="a year"), message="bounds.examples[1]: value 'a year' is not a duration this")

    def test_a_verdict_outside_the_vocabulary_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d)["examples"][0].update(verdict="maybe"), message="bounds.examples[1]: verdict is 'maybe', outside {applies")

    def test_a_bound_without_a_locator_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d)["examples"][0].pop("locator"), message='bounds.examples[1] carries exactly locator, text, verdict')

    def test_a_bound_citing_another_corpus_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d)["examples"][0]["locator"].update(
            sourceId="core-rules"), message="bounds.examples[1]: cites corpus 'core-rules' and the entry")

    def test_a_bound_whose_text_elides_its_middle_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d)["examples"][0].update(
            text="A pause of one year ... is not a short interruption."), message='bounds.examples[1]: `text` elides its middle. One')

    def test_a_term_the_evidence_does_not_use_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d).update(term="brief interruption"), message="bounds names term 'brief interruption'")

    def test_a_field_the_block_does_not_have_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d).update(note="why these two"), message='`ambiguity.bounds` carries exactly term, dimension, examples')

    def test_a_field_an_example_does_not_have_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d)["examples"][0].update(
            note="the mapper's reading"), message='bounds.examples[1] carries exactly locator, text, verdict')

    def test_no_examples_is_refused(self):
        self.assert_catches("bounds", lambda d: self.bounded(d).update(examples=[]), message='bounds.examples is not a non-empty list')

    def test_bounds_at_entry_level_are_refused(self):
        document = valid_map()
        document["entries"][0]["bounds"] = bounds()
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "bounds"), "fail", output)
        self.assertIn("belongs in the `ambiguity` block", output)
        self.assertEqual(code, 1, output)

    def test_bounds_on_a_settled_ambiguity_are_refused(self):
        # A `fate: decision` has no ruling for a bound to be compared against, and this checker
        # cannot read the decision record, so the bound would be recorded and never read.
        def mutate(document):
            ambiguity = document["entries"][self.BOUNDED]["ambiguity"]
            ambiguity.pop("unresolvedReason")
            ambiguity["fate"] = "decision"
            ambiguity["decision"] = "docs/decisions/0007-opposed-test-tie-break.md"
        self.assert_catches("bounds", mutate, message='carries `ambiguity.bounds` and `fate: decision`. A bound is')

    def test_a_map_with_no_bounds_does_not_report_ok(self):
        document = valid_map()
        document["entries"][self.BOUNDED]["ambiguity"].pop("bounds")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "bounds"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)

    def test_a_duration_is_the_same_length_the_factory_compares(self):
        # tools/factory/rulings.py carries the same parser, because it is vendored into every
        # engine and imports nothing of this checker. The two are held to one table here, as the
        # section-designation expression already is above: a scale that drifted would let a
        # ruling clear a bound in the factory that the map's own checker read differently.
        repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        spec = importlib.util.spec_from_file_location(
            "factory_rulings_for_bounds", os.path.join(repo, "tools", "factory", "rulings.py"))
        vendored = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vendored)
        for value in ("P1Y", "P12M", "P18M", "P2M", "P730D", "P52W", "P1Y6M", "P0D",
                      "a year", "P", "", "PT48H", "1Y", "P1.5Y", None):
            with self.subTest(value=value):
                self.assertEqual(check_map.duration_in_days(value), vendored.duration_in_days(value))
        # And the convention itself, so neither file can quietly change it: 12 months is a year.
        self.assertEqual(check_map.duration_in_days("P1Y"), check_map.duration_in_days("P12M"))
        self.assertEqual(check_map.duration_in_days("P1W"), 7)


class TestAbsent(MapCase):
    """0009: `absentFrom` separates 'the corpus does not state it' from 'we declined it'."""

    ABSENT = 8  # doubling-cube, in valid_map()'s order

    def test_an_absent_rule_the_map_still_claims_to_cover_fails(self):
        # scope: out is not decoration here -- row 1 must dominate, and 0008's procedure
        # has scope: in as its precondition, so an absent rule must never reach the gates.
        self.assert_catches("absent", lambda d: d["entries"][self.ABSENT].update(scope="in"), message="carries `absentFrom` while scope is 'in'")

    def test_an_absent_rule_recorded_as_unbuilt_rather_than_declined_fails(self):
        self.assert_catches("absent", lambda d: d["entries"][self.ABSENT].update(status="mapped"), message="carries `absentFrom` while status is 'mapped'")

    def test_absent_beside_beyond_adapter_fails(self):
        # Nowhere in the corpus and somewhere in it we cannot reach are different claims.
        self.assert_catches(
            "absent",
            lambda d: d["entries"][self.ABSENT].update(
                beyondAdapter={"adapter": "plain-text", "modality": "illustration"}), message='carries `absentFrom` and `beyondAdapter`',
        )

    def test_absent_beside_defined_elsewhere_fails(self):
        self.assert_catches(
            "absent",
            lambda d: d["entries"][self.ABSENT].update(definedElsewhere={"reference": "other-corpus"}), message='carries `absentFrom` and `definedElsewhere`',
        )

    def test_absent_beside_an_ambiguity_block_fails(self):
        # An absent rule has no words to be ambiguous about.
        def mutate(document):
            document["entries"][self.ABSENT]["clarity"] = "ambiguous"
            document["entries"][self.ABSENT]["ambiguity"] = {
                "question": "The corpus does not say.",
                "fate": "unresolved",
                "unresolvedReason": "OutsideCurrentScope",
            }
        self.assert_catches("absent", mutate, message='carries `absentFrom` and an `ambiguity` block')

    def test_an_absent_rule_that_depends_on_something_fails(self):
        self.assert_catches(
            "absent", lambda d: d["entries"][self.ABSENT].update(dependsOn=["speed-limit"]), message='carries `absentFrom` and a non-empty `dependsOn`')

    def test_depending_on_an_absent_rule_fails(self):
        # The edge can never be satisfied: `blocked` that will never clear.
        self.assert_catches(
            "absent", lambda d: d["entries"][1].update(dependsOn=["doubling-cube"]), message="dependsOn names 'doubling-cube'")

    def test_enabling_on_an_absent_rule_fails(self):
        self.assert_catches(
            "absent", lambda d: d["entries"][3].update(enabledBy=["doubling-cube"]), message="enabledBy names 'doubling-cube'")

    def test_suspending_on_an_absent_rule_fails(self):
        self.assert_catches(
            "absent", lambda d: d["entries"][3].update(suspendedBy=["doubling-cube"]), message="suspendedBy names 'doubling-cube'")

    def test_an_absence_nobody_searched_for_fails_the_vocabulary(self):
        # An empty `searched` is the "(absent)" locator in a new spelling: a claim with
        # nothing behind it. It is caught where the field's shape is checked.
        self.assert_catches(
            "vocabulary", lambda d: d["entries"][self.ABSENT]["absentFrom"].update(searched=[]), message='absentFrom is missing a non-empty `searched` list')

    def test_a_map_with_no_absent_rules_does_not_report_ok(self):
        document = valid_map()
        document["entries"].pop(self.ABSENT)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "absent"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)


class TestAssertedBy(MapCase):
    """0025 (#117): an assertion says who the corpus lets assert it, in the corpus's words."""

    ASSERTION = 2  # well-clear, in valid_map()'s order

    def test_an_assertion_that_names_nobody_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].pop("assertedBy"), message='is `kind: assertion` and has no `assertedBy`')

    def test_asserted_by_on_an_entry_that_is_not_an_assertion_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][1].update(assertedBy=["remote pilot"]), message="carries `assertedBy` while kind is 'operation'")

    def test_an_empty_or_malformed_list_fails(self):
        # Two rules of one check, and the expected refusal is paired with the value rather than
        # shared across the loop: `[]` and a bare string are not a list of parties, while `[""]`
        # and `[3]` are a list holding something that is not a name. Asserting one message for
        # all four would be the very thing #283 is about -- a neighbouring rule satisfying the
        # verdict while the rule the case is about goes unexercised.
        for value, refusal in (
            ([], "`assertedBy` is not a non-empty list of who asserts it"),
            ("remote pilot", "`assertedBy` is not a non-empty list of who asserts it"),
            ([""], "`assertedBy` holds something that is not a name"),
            ([3], "`assertedBy` holds something that is not a name"),
        ):
            with self.subTest(value=value):
                self.assert_catches("asserted-by",
                                    lambda d, v=value: d["entries"][self.ASSERTION].update(assertedBy=v),
                                    message=refusal)

    def test_a_party_named_twice_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(
            assertedBy=["remote pilot", "Remote  Pilot"]), message='`assertedBy` names one party twice')

    def test_a_party_the_evidence_does_not_name_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(
            assertedBy=["visual observer"]), message="`assertedBy` names 'visual observer'")

    def test_a_party_matches_as_a_whole_word_only(self):
        # "pilot" inside "autopilot" is not the pilot.
        def mutate(document):
            document["entries"][self.ASSERTION].update(
                assertedBy=["pilot"], evidence="The autopilot must keep the aircraft well clear.")
        self.assert_catches("asserted-by", mutate, message="`assertedBy` names 'pilot'")

    def test_a_party_matches_ignoring_case_and_spacing(self):
        document = valid_map()
        document["entries"][self.ASSERTION].update(
            assertedBy=["Remote Pilot"], evidence="The remote\n pilot must keep the aircraft well clear.")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "asserted-by"), "ok", output)

    def test_a_party_named_in_a_span_the_note_quotes_passes(self):
        # The bearer is in a lead-in the evidence does not reach; the note quotes it.
        def named_in_note(document):
            document["entries"][self.ASSERTION].update(
                assertedBy=["remote pilot in command"],
                evidence="Keep the aircraft well clear of other aircraft.",
                note="The bearer is the lead-in's, “Prior to flight, the remote pilot in command must:”.")
        document = valid_map()
        named_in_note(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "asserted-by"), "ok", output)
        self.assertEqual(code, 0, output)
        # The same words in the note, unquoted, are the mapper's and anchor nothing.
        document["entries"][self.ASSERTION]["note"] = "The bearer is the remote pilot in command."
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "asserted-by"), "fail", output)

    def test_the_caller_passes_alone_and_with_a_reason(self):
        document = valid_map()
        document["entries"][self.ASSERTION].update(
            assertedBy=["caller"], evidence="No person may operate so close as to create a hazard.",
            note="The sentence names nobody who judges the hazard, so the caller asserts it.")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "asserted-by"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_the_caller_with_no_reason_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(assertedBy=["caller"]), message='`assertedBy` is `caller` and no `note` says why the corpus')
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(
            assertedBy=["caller"], note="Asserted, never inferred."), message='`assertedBy` is `caller` and no `note` says why the corpus')

    def test_the_caller_beside_a_named_party_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(
            assertedBy=["caller", "remote pilot"], note="The caller, or the remote pilot."), message='`assertedBy` names `caller` beside other parties')

    def test_a_map_with_no_assertions_does_not_report_ok(self):
        document = valid_map()
        document["entries"].pop(self.ASSERTION)
        document["entries"][1]["dependsOn"] = ["speed-limit"]
        for item in document["entries"]:
            item["dependsOn"] = [d for d in item.get("dependsOn", []) if d != "well-clear"]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "asserted-by"), "skip", output)


SEEDED = json.loads(json.dumps(MANIFEST))
SEEDED["corpora"][0]["randomness"] = "seeded"


def seeded_map():
    """valid_map, plus operations that draw and one whose unsettled point is how many draws."""
    document = valid_map()
    document["entries"].extend([
        entry("opening-throw", kind="operation", draws={"dice": "die", "count": "one per player"},
              evidence="The game begins with each player throwing a single die."),
        entry("group-roll", kind="operation", clarity="ambiguous",
              draws={"dice": "d20", "count": "one per group; how many groups is the question"},
              ambiguity={"question": "What is a group? The GM makes a single roll for one, and "
                                     "the corpus does not say how many there are.",
                         "fate": "unresolved",
                         "unresolvedReason": "RequiresInterpretation", "affectsDraws": True},
              evidence="The GM makes a single roll for a group.",
              note="The roll is a test, and “the game uses a d20 roll to determine success”."),
        entry("attack", kind="operation",
              draws=[{"dice": "d20", "count": 1}, {"dice": "damage dice", "count": "on a hit only"}],
              evidence="Roll a d20 to hit; on a hit, roll the damage dice."),
    ])
    return document


class TestDraws(MapCase):
    """0025 (#118): an operation of a seeded corpus that draws says how many draws of what."""

    THROW, GROUP, ATTACK = -3, -2, -1

    def setUp(self):
        super().setUp()
        self.write_manifest(SEEDED)

    def assert_draws_catch(self, mutate):
        code, output = self.run_tool(seeded_map())
        self.assertEqual(self.status_of(output, "draws"), "ok", output)
        self.assertEqual(code, 0, output)
        document = seeded_map()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "draws"), "fail", output)
        self.assertEqual(code, 1, output)
        return output

    def test_draws_under_randomness_none_fail(self):
        self.write_manifest(MANIFEST)
        code, output = self.run_tool(seeded_map())
        self.assertEqual(self.status_of(output, "draws"), "fail", output)
        self.assertIn("randomness: none", output)

    def test_a_map_of_a_none_corpus_that_draws_nothing_passes(self):
        self.write_manifest(MANIFEST)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "draws"), "ok", output)

    def test_a_seeded_map_that_declares_no_draws_does_not_report_ok(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "draws"), "skip", output)

    def test_draws_without_a_manifest_are_not_verified(self):
        os.remove(self.manifest_path)
        code, output = self.run_tool(seeded_map())
        self.assertEqual(self.status_of(output, "draws"), "skip", output)
        self.assertEqual(code, 1, output)

    def test_draws_on_an_entry_that_is_not_an_operation_fail(self):
        self.assert_draws_catch(lambda d: d["entries"][self.THROW].update(kind="value"))

    def test_draws_on_an_out_of_scope_entry_fail(self):
        self.assert_draws_catch(lambda d: d["entries"][self.THROW].update(scope="out", status="declined"))

    def test_a_malformed_draw_fails(self):
        for value in ({"dice": "die"}, {"count": 1}, {"dice": "", "count": 1}, {"dice": "die", "count": 0},
                      {"dice": "die", "count": True}, {"dice": "die", "count": " "}, [],
                      {"dice": "die", "count": 1, "faces": 6}, "one die", [{"dice": "die"}]):
            with self.subTest(value=value):
                self.assert_draws_catch(lambda d, v=value: d["entries"][self.THROW].update(draws=v))

    def test_dice_the_evidence_does_not_name_fail(self):
        output = self.assert_draws_catch(
            lambda d: d["entries"][self.THROW].update(draws={"dice": "d6", "count": "one per player"}))
        self.assertIn("'d6'", output)

    def test_each_draw_of_a_list_is_anchored(self):
        self.assert_draws_catch(lambda d: d["entries"][self.ATTACK]["draws"][1].update(dice="hit dice"))

    def test_dice_named_in_a_span_the_note_quotes_pass_and_unquoted_fail(self):
        self.assert_draws_catch(
            lambda d: d["entries"][self.GROUP].update(note="The roll is a test on a d20."))

    def test_an_ambiguity_affecting_draws_with_no_draws_fails(self):
        output = self.assert_draws_catch(lambda d: d["entries"][self.GROUP].pop("draws"))
        self.assertIn("affectsDraws is true", output)

    def test_an_ambiguity_not_affecting_draws_needs_none(self):
        document = seeded_map()
        document["entries"][self.GROUP].pop("draws")
        document["entries"][self.GROUP]["ambiguity"]["affectsDraws"] = False
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "draws"), "ok", output)

    def test_affects_draws_that_is_not_a_boolean_fails(self):
        self.assert_draws_catch(lambda d: d["entries"][self.GROUP]["ambiguity"].update(affectsDraws="yes"))

    def test_affects_draws_outside_the_ambiguity_block_fails(self):
        self.assert_draws_catch(lambda d: d["entries"][self.THROW].update(affectsDraws=True))


class TestCrossReferences(MapCase):
    """0009: a reference the corpus makes is an entry, or a recorded reason there is none."""

    POINTER = 9  # next-game-opening, in valid_map()'s order

    def test_a_pointer_with_no_declaration_fails(self):
        # The live instance: § 107.29(a) opens "Except as provided in paragraph (d)" and
        # (d) has no entry in either Part 107 map.
        self.assert_catches(
            "cross-references", lambda d: d["entries"][self.POINTER].pop("crossReferences"), message="`evidence` says 'as at starting' and no `crossReferences`")

    def test_a_pointer_phrased_as_an_exception_is_one_pointer_not_two(self):
        # "except as provided in" contains "as provided in"; demanding two declarations for
        # one pointer would teach mappers to pad the list.
        self.assertEqual(
            check_map.pointers_in("Except as provided in paragraph (d) of this section, no "
                                  "person may operate at night."),
            ["Except as provided in"],
        )

    def test_matches_only_whitespace_separates_are_one_pointer(self):
        # A corpus's own "paragraph (d) of this section" follows the built-in "except as provided
        # in"; one pointer, one declaration.
        patterns = check_map.BUILT_IN_PATTERNS + [re.compile(r"paragraph \([a-z]\) of this section", re.I)]
        self.assertEqual(
            check_map.pointers_in("Except as provided in paragraph (d) of this section, no person "
                                  "may operate; see paragraph (b) of this section.", patterns),
            ["Except as provided in paragraph (d) of this section", "paragraph (b) of this section"],
        )

    def test_a_declaration_not_anchored_in_the_evidence_fails(self):
        self.assert_catches(
            "cross-references",
            lambda d: d["entries"][self.POINTER]["crossReferences"][0].update(
                cites="as provided in paragraph (d)"), message="crossReferences cites 'as provided in paragraph (d)'",
        )

    def test_a_declaration_resolving_to_no_entry_fails(self):
        self.assert_catches(
            "cross-references",
            lambda d: d["entries"][self.POINTER]["crossReferences"][0].update(
                resolvedBy="no-such-entry"), message="crossReferences 'as at starting' resolves to 'no-such-entry'",
        )

    def test_a_declaration_resolving_to_itself_fails(self):
        self.assert_catches(
            "cross-references",
            lambda d: d["entries"][self.POINTER]["crossReferences"][0].update(
                resolvedBy="next-game-opening"), message="crossReferences 'as at starting' resolves to itself",
        )

    def test_a_declaration_resolving_to_nothing_at_all_fails(self):
        self.assert_catches(
            "cross-references",
            lambda d: d["entries"][self.POINTER]["crossReferences"][0].pop("resolvedBy"), message="crossReferences 'as at starting' resolves to nothing",
        )

    def test_a_declaration_claiming_both_arms_fails(self):
        # A reference is an entry or a recorded reason there is none, not both.
        self.assert_catches(
            "cross-references",
            lambda d: d["entries"][self.POINTER]["crossReferences"][0].update(
                unmapped="The figure is not a passage."), message="crossReferences 'as at starting' names both `resolvedBy`",
        )

    def test_a_recorded_reason_there_is_no_entry_is_accepted(self):
        # inner-table-handedness cites Fig. 1, which is an illustration and not a passage.
        document = valid_map()
        document["entries"][self.POINTER]["crossReferences"] = [
            {"cites": "as at starting", "unmapped": "Nothing in this map states it."}
        ]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "ok", output)
        self.assertEqual(code, 0, output)

    DEFINED_ELSEWHERE = 4  # hazardous-material, which names the unadmitted other-corpus

    def with_pointer_elsewhere(self, document, evidence, cites, reason):
        item = document["entries"][self.DEFINED_ELSEWHERE]
        item["evidence"] = evidence
        item["crossReferences"] = [{"cites": cites, "unmapped": reason}]
        return document

    def test_a_pointer_definedElsewhere_answers_is_not_declared_again_by_source_id(self):
        # #62: the blind Part 107 map declared "as defined in the Air Almanac" both in
        # definedElsewhere and as an unmapped crossReferences item.
        document = self.with_pointer_elsewhere(
            valid_map(), "Its meaning is as defined in the Other Corpus.",
            "as defined in the Other Corpus", "Not admitted; see definedElsewhere.")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("definedElsewhere` already answers", output)
        self.assertEqual(code, 1, output)

    def test_a_pointer_definedElsewhere_answers_is_not_declared_again_by_citation(self):
        # The other #62 instance: "defined in 49 CFR 171.8", whose manifest reference is
        # `cfr-49-171` citing "§ 171.8".
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0]["references"] = [
            {"sourceId": "cfr-49-171", "citation": "§ 171.8", "admitted": False}]
        self.write_manifest(manifest)
        document = self.with_pointer_elsewhere(
            valid_map(), "The term hazardous material is defined in 49 CFR 171.8.",
            "49 CFR 171.8", "Not admitted; see definedElsewhere.")
        document["entries"][self.DEFINED_ELSEWHERE]["definedElsewhere"] = {"reference": "cfr-49-171"}
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertEqual(code, 1, output)

    def test_another_pointer_on_an_entry_defined_elsewhere_is_still_declared(self):
        # Part 107's night-waiver-bar routes "at night" to § 1.1 and still answers its pointer
        # to § 107.200, which is a different corpus passage.
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0]["references"] = [
            {"sourceId": "cfr-14-1", "citation": "§ 1.1", "admitted": False}]
        self.write_manifest(manifest)
        document = self.with_pointer_elsewhere(
            valid_map(), "No person may operate at night under a waiver issued under § 107.200.",
            "under § 107.200", "§ 107.200 is outside this map's extent.")
        document["entries"][self.DEFINED_ELSEWHERE]["definedElsewhere"] = {"reference": "cfr-14-1"}
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_corpus_with_no_phrases_on_which_the_built_in_list_finds_nothing_fails(self):
        # #116: the SRD's 22 cross-references were never checked, because the built-in list
        # found no pointer in its text and said nothing about it. A silent zero is the defect.
        document = valid_map()
        document["entries"].pop(self.POINTER)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("manifest demo-corpus: the built-in pointer phrases detect no pointer", output)
        self.assertEqual(code, 1, output)

    def test_a_corpus_declaring_no_pointers_with_a_reason_is_not_verified_rather_than_failed(self):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0].update(pointerPhrases=[],
                                      pointerPhrasesReason="A list of rules that never refers to another.")
        self.write_manifest(manifest)
        document = valid_map()
        document["entries"].pop(self.POINTER)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)

    def test_an_empty_phrase_list_without_a_reason_fails(self):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0]["pointerPhrases"] = []
        self.write_manifest(manifest)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("`pointerPhrasesReason` does not say why", output)
        self.assertEqual(code, 1, output)

    def test_a_reason_beside_a_non_empty_phrase_list_fails(self):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0].update(pointerPhrases=["as at starting"], pointerPhrasesReason="Unread.")
        self.write_manifest(manifest)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("beside a non-empty `pointerPhrases`", output)
        self.assertEqual(code, 1, output)

    def test_a_reason_with_no_phrase_list_fails(self):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0]["pointerPhrasesReason"] = "Nothing points anywhere."
        self.write_manifest(manifest)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertEqual(code, 1, output)

    def test_a_malformed_phrase_is_refused(self):
        for bad, expect in (({"regex": "(unclosed"}, "does not compile"),
                            ({"regex": "x*"}, "matches the empty string"),
                            ({"pattern": "see"}, "an item is a literal phrase"),
                            (7, "an item is a literal phrase"),
                            ("   ", "an item is a literal phrase")):
            with self.subTest(phrase=bad):
                manifest = json.loads(json.dumps(MANIFEST))
                manifest["corpora"][0]["pointerPhrases"] = [bad]
                self.write_manifest(manifest)
                code, output = self.run_tool(valid_map())
                self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
                self.assertIn(expect, output)
                self.assertEqual(code, 1, output)

    def with_declared_phrases(self, phrases, evidence, references=None):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0]["pointerPhrases"] = phrases
        self.write_manifest(manifest)
        document = valid_map()
        item = document["entries"][0]
        item["evidence"] = evidence
        if references is not None:
            item["crossReferences"] = references
        return self.run_tool(document)

    def test_a_declared_literal_phrase_makes_a_pointer_that_must_be_answered(self):
        evidence = "Each square represents 5 feet (see the next section)."
        code, output = self.with_declared_phrases(["see the next section"], evidence)
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("'see the next section' and no `crossReferences` item claims it", output)
        code, output = self.with_declared_phrases(
            ["see the next section"], evidence,
            [{"cites": "(see the next section)", "resolvedBy": "speed-within-limit"}])
        self.assertEqual(self.status_of(output, "cross-references"), "ok", output)
        self.assertIn("demo-corpus: 2 pointers in 10 quoted spans (built-in and 1 declared phrase)", output)
        self.assertEqual(code, 0, output)

    def test_a_declared_regex_finds_what_the_built_in_list_cannot(self):
        # The built-in list's limit, `starting-position`'s "as shown in {273} Fig. 1", where a page
        # marker falls inside the phrase: still a limit of the list, and a corpus's own phrase
        # reaches it.
        self.assertEqual(check_map.pointers_in("The men are arranged as shown in {273} Fig. 1"), [])
        self.assertEqual(check_map.pointers_in("The men are arranged as shown in Fig. 1"),
                         ["shown in Fig."])
        evidence = "The men are arranged as shown in {273} Fig. 1"
        phrases = [{"regex": r"\bshown in (?:\{\d+\}\s*)?Fig\."}]
        code, output = self.with_declared_phrases(phrases, evidence)
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("'shown in {273} Fig.'", output)
        code, output = self.with_declared_phrases(
            phrases, evidence, [{"cites": "as shown in {273} Fig. 1", "unmapped": "An illustration."}])
        self.assertEqual(self.status_of(output, "cross-references"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_phrase_one_corpus_declares_does_not_apply_to_another(self):
        # Pointer phrases are per corpus: the SRD's "(see ...)" is not a CFR pointer.
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"].append(dict(MANIFEST["corpora"][0], sourceId="second-corpus",
                                        pointerPhrases=["see the next section"], references=[]))
        self.write_manifest(manifest)
        document = valid_map()
        document["entries"][0]["evidence"] = "Each square represents 5 feet (see the next section)."
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "ok", output)
        document["entries"][0]["locator"]["sourceId"] = "second-corpus"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("speed-limit: `evidence` says 'see the next section'", output)
        self.assertEqual(code, 1, output)

    def test_a_declaration_that_only_partly_covers_a_pointer_does_not_claim_it(self):
        code, output = self.with_declared_phrases(
            [{"regex": r"paragraph \([a-z]\) of this section"}],
            "Except as provided in paragraph (d) of this section, no person may operate.",
            [{"cites": "Except as provided in", "resolvedBy": "speed-within-limit"}])
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("'Except as provided in paragraph (d) of this section'", output)
        self.assertEqual(code, 1, output)

    def test_a_pointer_naming_the_entrys_defined_elsewhere_reference_is_answered_by_it(self):
        # hazardous-material's "defined in 49 CFR 171.8": definedElsewhere answers it (#62), so a
        # detected pointer naming that reference needs no crossReferences item.
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["corpora"][0]["references"] = [
            {"sourceId": "cfr-49-171", "citation": "§ 171.8", "admitted": False}]
        manifest["corpora"][0]["pointerPhrases"] = [{"regex": r"\b\d+ CFR \d+(?:\.\d+)?"}]
        self.write_manifest(manifest)
        document = valid_map()
        item = document["entries"][self.DEFINED_ELSEWHERE]
        item["definedElsewhere"] = {"reference": "cfr-49-171"}
        item["evidence"] = "The term hazardous material is defined in 49 CFR 171.8."
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "ok", output)
        self.assertEqual(code, 0, output)
        # The other way: a pointer to a different designation is not the reference's to answer.
        item["evidence"] = "The term hazardous material is defined in 49 CFR 172.101."
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("'49 CFR 172.101'", output)
        self.assertEqual(code, 1, output)

    def test_without_a_manifest_the_zero_is_not_judged(self):
        os.remove(self.manifest_path)
        document = valid_map()
        document["entries"].pop(self.POINTER)
        code, output = self.run_tool(document, ["--only", "cross-references"])
        self.assertEqual(self.status_of(output, "cross-references"), "skip", output)
        self.assertNotIn("detect no pointer", output)

    def test_every_example_corpus_reports_the_pointers_it_detected(self):
        # #116 on the committed maps: every corpus declares its phrases, and the SRD's declared
        # cross-references are now on pointers the check detects.
        root = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        for path in sorted(glob.glob(os.path.join(root, "examples", "*", "corpus-map*.json"))):
            with self.subTest(map=os.path.relpath(path, root)):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = check_map.main([path, "--only", "cross-references"])
                output = out.getvalue() + err.getvalue()
                self.assertEqual(code, 0, output)
                self.assertRegex(output, r"\[ok\] cross-references: [\w.-]+: [1-9]\d* pointers? in ")
                self.assertIn("declared phrase", output)


class TestDefines(MapCase):
    """0045: a term an entry defines is declared by that entry, anchored in its own evidence.

    `crossReferences` records a pointer the passage **makes**; `defines` records a term the
    passage **gives a meaning to**. One rule governs both, and it is 0026's: the declaration
    appears verbatim in the evidence of the entry that makes it. #314 refused to buy
    `coded-pointer` a vocabulary by exempting anything from that rule.
    """

    DEFINING = 3   # yield-right-of-way, which the fixture already has define a term
    SECOND = 1     # speed-within-limit, whose evidence prints its own id too

    @staticmethod
    def defining_map():
        return valid_map()

    def assert_catches_defines(self, mutate, message):
        """The defining map passes `defines`; the mutation makes it say `message`."""
        code, output = self.run_tool(self.defining_map())
        self.assertEqual(self.status_of(output, "defines"), "ok", output)
        self.assertEqual(code, 0, output)
        document = self.defining_map()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "defines"), "fail", output)
        self.assertEqual(code, 1, output)
        self.assertIn(message, output)

    def test_a_map_declaring_nothing_is_not_verified_rather_than_ok(self):
        # The field is optional, and a check with no subject has not passed. Every map
        # committed before 0045 is this case.
        document = valid_map()
        document["entries"][self.DEFINING].pop("defines")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "defines"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_a_term_absent_from_the_entrys_own_evidence_fails(self):
        # The live instance: `special-provision-codes` quoting "The following tables list ..."
        # and declaring twenty codes it does not print.
        self.assert_catches_defines(
            lambda d: d["entries"][self.DEFINING]["defines"][0].update(term="IB3"),
            "defines 'IB3', which does not appear in this entry's `evidence`")

    def test_two_entries_defining_one_term_are_both_accepted(self):
        # 0044's cardinality, as the ordinary result of two entries declaring the same term.
        document = self.defining_map()
        document["entries"][self.SECOND]["defines"] = [
            {"vocabulary": "demo-codes", "term": "speed-within-limit"}]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "defines"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_the_same_declaration_twice_on_one_entry_fails(self):
        self.assert_catches_defines(
            lambda d: d["entries"][self.DEFINING]["defines"].append(
                {"vocabulary": "demo-codes", "term": "yield-right-of-way"}),
            "declares 'yield-right-of-way' in vocabulary 'demo-codes' more than once")

    def test_the_same_term_in_two_vocabularies_on_one_entry_is_accepted(self):
        document = self.defining_map()
        document["entries"][self.DEFINING]["defines"].append(
            {"vocabulary": "other-codes", "term": "yield-right-of-way"})
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "defines"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_an_empty_list_fails(self):
        self.assert_catches_defines(
            lambda d: d["entries"][self.DEFINING].update(defines=[]),
            "`defines` is []")

    def test_a_list_that_is_not_a_list_fails(self):
        self.assert_catches_defines(
            lambda d: d["entries"][self.DEFINING].update(defines={"term": "yield-right-of-way"}),
            "it is a non-empty list of the terms this passage defines")

    def test_an_item_with_a_third_key_fails(self):
        # An unread key looks like it is doing work, which is #60's shape.
        self.assert_catches_defines(
            lambda d: d["entries"][self.DEFINING]["defines"][0].update(resolvedBy="speed-limit"),
            "an item is exactly `vocabulary` and `term`")

    def test_an_item_missing_the_vocabulary_fails(self):
        self.assert_catches_defines(
            lambda d: d["entries"][self.DEFINING]["defines"][0].pop("vocabulary"),
            "an item is exactly `vocabulary` and `term`")

    def test_an_empty_term_fails(self):
        self.assert_catches_defines(
            lambda d: d["entries"][self.DEFINING]["defines"][0].update(term="   "),
            "that is not a non-empty string")

    def test_a_derived_entry_carrying_defines_is_refused(self):
        # By `derived`, which refuses every passage field on one: no sentence states a derived
        # fact, so there is no evidence for a definition to be anchored in.
        document = valid_map()
        derived = next(e for e in document["entries"] if "derivedFrom" in e)
        derived["defines"] = [{"vocabulary": "demo-codes", "term": "speed-limit"}]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "derived"), "fail", output)
        self.assertIn("is derived and carries `defines`", output)
        self.assertEqual(code, 1, output)


class TestCorrespondence(MapCase):
    def test_a_declined_entry_with_no_row_fails(self):
        # `declined` claims no implemented path at all, so some row owes an answer.
        def mutate(document):
            document["entries"][4].pop("definedElsewhere")
        self.assert_catches("correspondence", mutate, message='status is `declined` -- no implemented path at all -- and')

    def test_defined_elsewhere_and_beyond_adapter_together_fail(self):
        def mutate(document):
            document["entries"][4]["beyondAdapter"] = {"adapter": "plain-text", "modality": "illustration"}
        self.assert_catches("correspondence", mutate, message='carries both `definedElsewhere` and `beyondAdapter`')

    def test_an_assertion_that_also_declines_fails(self):
        # Row 8: an assertion is a parameter, not a failure to resolve.
        def mutate(document):
            document["entries"][2]["beyondAdapter"] = {"adapter": "plain-text", "modality": "illustration"}
        self.assert_catches("correspondence", mutate, message='is `kind: assertion` and also matches row(s) [4]')

    def test_mapped_with_unresolved_fate_matching_two_rows_is_not_an_error(self):
        # 0005: eleven entries across the three maps do this; precedence is what it is for.
        document = valid_map()
        document["entries"][7]["status"] = "mapped"
        document["entries"][7].pop("implementedIn", None)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "correspondence"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_row_precedence_is_the_documented_order(self):
        # Derived from the table in docs/corpus-map.md, not from the tool.
        out_of_scope_and_unbuilt = entry("x", scope="out", status="mapped")
        self.assertEqual(check_map.matched_rows(out_of_scope_and_unbuilt, {})[0], 1)
        unbuilt_and_unresolved = entry("y", status="mapped", clarity="ambiguous",
                                       ambiguity={"question": "q", "fate": "unresolved",
                                                  "unresolvedReason": "RequiresInterpretation"})
        self.assertEqual(check_map.matched_rows(unbuilt_and_unresolved, {})[0], 2)

    def test_row_five_reads_the_dependency_graph(self):
        unimplemented_value = entry("limit", kind="value", status="mapped")
        operation = entry("compare", kind="operation", status="implemented", dependsOn=["limit"])
        rows = check_map.matched_rows(operation, {"limit": unimplemented_value})
        self.assertEqual(rows, [5])
        unimplemented_value["status"] = "implemented"
        self.assertEqual(check_map.matched_rows(operation, {"limit": unimplemented_value}), [])


class TestUnresolvedReason(MapCase):
    """0034: an open question returns the reason a caller can act on, not merely a reason in the
    kernel's vocabulary."""

    OPEN = 7  # must-play-whole-throw, in valid_map()'s order

    def test_missing_rules_data_on_an_open_question_fails(self):
        # In the vocabulary, so `schema` passes it, and produced by no row this entry matches:
        # the caller is sent after data that does not exist when what is missing is a reading.
        def mutate(document):
            document["entries"][self.OPEN]["ambiguity"]["unresolvedReason"] = "MissingRulesData"
        self.assert_catches("unresolved-reason", mutate, message='fate is `unresolved` and unresolvedReason is')

    def test_unsupported_rule_on_an_open_question_fails(self):
        def mutate(document):
            document["entries"][self.OPEN]["ambiguity"]["unresolvedReason"] = "UnsupportedRule"
        self.assert_catches("unresolved-reason", mutate, message='fate is `unresolved` and unresolvedReason is')

    def test_an_out_of_scope_open_question_may_return_outside_current_scope(self):
        # Row 1 wins before row 6, so both reasons are producible for this entry, and
        # srd-52-conditions' `malnutrition-hazard` is the committed instance of the shape.
        document = valid_map()
        document["entries"][self.OPEN]["scope"] = "out"
        document["entries"][self.OPEN]["ambiguity"]["unresolvedReason"] = "OutsideCurrentScope"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "unresolved-reason"), "ok", output)

    def test_status_does_not_turn_the_verdict(self):
        # Rows 2 and 5 are status-dependent and this check reads neither, which is why it is
        # outside STATUS_DEPENDENT.
        document = valid_map()
        document["entries"][self.OPEN]["status"] = "mapped"
        document["entries"][self.OPEN].pop("implementedIn", None)
        document["entries"][self.OPEN].pop("tests", None)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "unresolved-reason"), "ok", output)

    def test_a_map_leaving_nothing_open_does_not_report_ok(self):
        document = valid_map()
        document["entries"].pop(self.OPEN)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "unresolved-reason"), "skip", output)
        self.assertIn("NOT VERIFIED", output)


class TestBoundTermOpen(MapCase):
    """0031 and 0034: a bound narrows a term the map records as open, and the question is where
    the map records it."""

    BOUNDED = 7  # must-play-whole-throw, in valid_map()'s order

    def test_a_term_the_question_never_states_fails(self):
        # `bounds` already holds the term to the entry's `evidence`, so the corpus says the
        # words; nothing held them to the doubt the entry records.
        def mutate(document):
            ambiguity = document["entries"][self.BOUNDED]["ambiguity"]
            ambiguity["question"] = "The text does not say what happens when only one die is playable."
        self.assert_catches("bound-term-open", mutate, message="bounds the term 'short interruption'")

    def test_the_term_is_matched_without_regard_to_case(self):
        # § 1.121-1(c)(2)'s question opens with the term: "Short temporary absences" fixes no
        # length, and the bound's `term` is the lower-case words of the passage.
        document = valid_map()
        ambiguity = document["entries"][self.BOUNDED]["ambiguity"]
        ambiguity["question"] = "Short interruption is fixed at no length by this text."
        ambiguity["bounds"]["term"] = "short interruption"
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "bound-term-open"), "ok", output)

    def test_a_map_with_no_bound_does_not_report_ok(self):
        document = valid_map()
        document["entries"][self.BOUNDED]["ambiguity"].pop("bounds")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "bound-term-open"), "skip", output)
        self.assertIn("NOT VERIFIED", output)


class TestQuestionAnchor(MapCase):
    """#271: an `ambiguity.question` quotes the passage its two readings turn on.

    `crossReferences.cites` must appear verbatim in the entry's own evidence -- a reference is
    anchored to the passage that makes it. An `ambiguity` had no such rule, so a mapper who
    invented doubt the corpus settles passed on 5 committed maps of 5.
    """

    OPEN = 7  # must-play-whole-throw, in valid_map()'s order

    INVENTED = ("The passage can be read as stating a requirement and as stating a permission, "
                "and nothing in the corpus resolves between the two.")

    def test_a_question_that_quotes_no_passage_the_map_quotes_fails(self):
        # Verbatim the block `tools/mutate-map.py --only clear-to-ambiguous` writes: a complete,
        # plausible ambiguity about no sentence of the corpus.
        def mutate(document):
            document["entries"][self.OPEN]["ambiguity"]["question"] = self.INVENTED
        self.assert_catches("question-anchor", mutate,
                            message="quotes no passage this map quotes")

    def test_a_run_of_words_the_corpus_does_not_own_does_not_anchor(self):
        # hoyle-backgammon is the reason the run has to carry a word of the corpus: the invented
        # question and that map's evidence share "between the two", and not one of those three
        # words is the corpus's.
        def mutate(document):
            document["entries"].append(entry(
                "stake-division",
                evidence="The stake is divided between the two players."))
            document["entries"][self.OPEN]["ambiguity"]["question"] = self.INVENTED
        self.assert_catches("question-anchor", mutate,
                            message="quotes no passage this map quotes")

    def test_the_anchor_may_be_in_the_evidence_of_another_entry(self):
        # § 172.102(c)(7): the hazmat map's IB3 row is ambiguous because of what (b)(4) says,
        # which is a different entry's evidence. The anchor is the corpus as this map quotes it.
        document = valid_map()
        ambiguity = document["entries"][self.OPEN]["ambiguity"]
        ambiguity.pop("bounds")
        ambiguity["question"] = ("The sentence stating speed-within-limit could govern this "
                                 "throw as well, and the corpus chooses neither reading.")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "question-anchor"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_the_anchor_is_read_through_case_and_spacing(self):
        document = valid_map()
        document["entries"][self.OPEN]["ambiguity"]["question"] = (
            "A  SHORT\nINTERRUPTION is fixed at no length by this text, and a short "
            "interruption of a year may be one.")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "question-anchor"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_a_map_recording_no_ambiguity_does_not_report_ok(self):
        document = valid_map()
        document["entries"].pop(self.OPEN)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "question-anchor"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)

    def test_every_recorded_ambiguity_in_every_committed_map_is_anchored(self):
        # #271's acceptance: the rule holds for every committed map, or the maps are corrected
        # and the correction is the finding. 64 recorded ambiguities across the committed maps.
        repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        for path in sorted(glob.glob(os.path.join(repo, "examples", "*", "corpus-map*.json"))):
            with self.subTest(map=os.path.relpath(path, repo)):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = check_map.main([path, "--only", "question-anchor"])
                output = out.getvalue() + err.getvalue()
                self.assertEqual(code, 0, output)


class TestSuperposition(MapCase):
    """0034: a disagreement about certainty that the corpus did not settle is recorded in the
    map as unresolved, or it is a premature collapse with a paper trail.

    0060: the record is one shape, `blind-mapping/resolutions.json`, and it declares the
    vocabulary its verdicts are written in.
    """

    OPEN = 7  # must-play-whole-throw, the fixture's one ambiguous entry

    LEGEND = {"R": "the reference is right", "B": "the blind map is right",
              "U": "the corpus does not settle it",
              "N": "not a disagreement about the corpus"}

    def write_record(self, document, name="resolutions.json"):
        directory = os.path.join(self.example, "blind-mapping")
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, name), "w") as handle:
            json.dump(document, handle)

    def record(self, legend=None, unsettled="U", **row):
        """The one shape: a declared legend, the term that means unsettled, and rows."""
        base = {"id": "must-play-whole-throw|clarity|whole-throw|differs", "field": "clarity",
                "entries": ["must-play-whole-throw", "whole-throw"], "verdict": "U",
                "reason": "The corpus states the pause twice and differently."}
        base.update(row)
        return {"verdicts": self.LEGEND if legend is None else legend,
                "unsettledVerdict": unsettled, "adjudications": [base]}

    def other_words(self, unsettled="open", **row):
        """A record whose vocabulary is another one entirely -- trial 9's, as it happens.

        Nothing in the checker knows these terms; it reads them out of the file.
        """
        legend = {"A": "the first map is right", "B": "the blind map is right",
                  "open": "the corpus does not settle it"}
        base = {"id": "the-short-interruption", "field": "clarity",
                "entries": ["must-play-whole-throw", "whole-throw"], "verdict": "open",
                "reason": "Neither reading is eliminated by the text."}
        base.update(row)
        return {"verdicts": legend, "unsettledVerdict": unsettled, "adjudications": [base]}

    def test_an_unsettled_verdict_carried_into_the_map_passes(self):
        self.write_record(self.record())
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "superposition"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_an_unsettled_verdict_the_map_records_as_clear_fails(self):
        # The premature collapse itself: two mappers read the passage differently, the corpus
        # was asked and did not answer, and the map states one reading.
        self.write_record(self.record())
        document = valid_map()
        document["entries"][self.OPEN]["clarity"] = "clear"
        document["entries"][self.OPEN].pop("ambiguity")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "superposition"), "fail", output)
        self.assertIn("premature collapse", output)
        self.assertEqual(code, 1, output)

    def test_the_doubt_may_be_recorded_on_an_entry_the_adjudication_names(self):
        # `die-faces` was adjudicated unsettled and the question went to a new `rubber-scoring`
        # entry, because the doubt was about a sentence inside its span. The rule is that the
        # doubt is somewhere, not that it is here.
        self.write_record(self.record(
            reason="Fixed: the question is recorded on opposed-test-tie, not here."))
        document = valid_map()
        document["entries"][self.OPEN]["clarity"] = "clear"
        document["entries"][self.OPEN].pop("ambiguity")
        document["entries"].append(decided_entry())
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "superposition"), "ok", output)
        self.assertEqual(code, 0, output)

    def test_the_two_rows_of_one_disagreement_are_read_together(self):
        # `compare.py` emits a `clarity` row and an `ambiguity` row from one reading, and the
        # committed records write the second as "Same as the clarity row." Read apart, the
        # terser row is a doubt that landed nowhere.
        record = self.record(reason="Fixed: recorded on opposed-test-tie.")
        record["adjudications"].append(
            {"id": "must-play-whole-throw|ambiguity|whole-throw|present", "field": "ambiguity",
             "entries": ["must-play-whole-throw", "whole-throw"], "verdict": "U",
             "reason": "Same as the clarity row."})
        self.write_record(record)
        document = valid_map()
        document["entries"][self.OPEN]["clarity"] = "clear"
        document["entries"][self.OPEN].pop("ambiguity")
        document["entries"].append(decided_entry())
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "superposition"), "ok", output)

    def test_a_disagreement_about_certainty_with_no_verdict_fails(self):
        # 0014: every disagreement is dispositioned before the map is used.
        record = self.record()
        record["adjudications"][0].pop("verdict")
        self.write_record(record)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "superposition"), "fail", output)
        self.assertIn("no verdict", output)
        self.assertEqual(code, 1, output)

    def test_a_verdict_the_records_own_legend_does_not_define_fails(self):
        # #273: the verdict is a term of the vocabulary the file declares, and nothing else.
        # A row answered in some other word is a disposition nobody can be shown to have made,
        # exactly as a missing one is.
        self.write_record(self.record(verdict="probably"))
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "superposition"), "fail", output)
        self.assertIn("no verdict", output)
        self.assertEqual(code, 1, output)

    def test_a_settled_verdict_does_not_demand_an_ambiguity(self):
        # R: the reference is right, so there is nothing to carry.
        self.write_record(self.record(verdict="R", reason="The reference is right."))
        document = valid_map()
        document["entries"][self.OPEN]["clarity"] = "clear"
        document["entries"][self.OPEN].pop("ambiguity")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "superposition"), "ok", output)

    def test_a_record_in_another_vocabulary_is_read_by_its_own_legend(self):
        self.write_record(self.other_words())
        document = valid_map()
        document["entries"][self.OPEN]["clarity"] = "clear"
        document["entries"][self.OPEN].pop("ambiguity")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "superposition"), "fail", output)
        self.assertIn("premature collapse", output)

    def test_a_settled_verdict_in_another_vocabulary_carries_nothing(self):
        self.write_record(self.other_words(verdict="A"))
        document = valid_map()
        document["entries"][self.OPEN]["clarity"] = "clear"
        document["entries"][self.OPEN].pop("ambiguity")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "superposition"), "ok", output)

    def test_a_legend_that_names_no_unsettled_term_is_not_verified(self):
        # #273: a record that declares a vocabulary and does not say which of its terms means
        # *the corpus does not settle it* is one this check would pass in silence -- every row
        # readable, nothing compared -- and silence is what it exists to refuse.
        record = self.record()
        record.pop("unsettledVerdict")
        self.write_record(record)
        document = valid_map()
        document["entries"][self.OPEN]["clarity"] = "clear"
        document["entries"][self.OPEN].pop("ambiguity")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "superposition"), "skip", output)
        self.assertIn("no shape this knows", output)
        self.assertEqual(code, 1, output)  # it had subject matter and could not look

    def test_the_comparators_own_output_is_not_read_as_the_record(self):
        # #273: `results.json` is the comparison -- the alignment and the flags -- and it sits
        # beside the record in three of the four trials. It carried the verdicts too, which is
        # how one artefact came to have two shapes. One file is read now, and it is the one
        # `review.json` names as `resolutions`.
        self.write_record({"flags": [{"entry": "must-play-whole-throw", "field": "clarity",
                                      "resolution": {"verdict": "U", "reason": "Unsettled."}}]},
                          name="results.json")
        document = valid_map()
        document["entries"][self.OPEN]["clarity"] = "clear"
        document["entries"][self.OPEN].pop("ambiguity")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "superposition"), "skip", output)
        self.assertIn("no blind second mapping's adjudication record", output)
        self.assertEqual(code, 0, output)

    def test_the_legacy_per_flag_shape_is_no_longer_a_shape_this_knows(self):
        # #273: the flat per-flag record migrated, so the second parser went. A record still
        # written that way is NOT VERIFIED, which is what any other unknown shape gets.
        self.write_record({"flags": [{"entry": "must-play-whole-throw", "field": "clarity",
                                      "resolution": {"verdict": "U", "reason": "Unsettled."}}]})
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "superposition"), "skip", output)
        self.assertIn("no shape this knows", output)
        self.assertEqual(code, 1, output)

    def test_a_record_of_no_known_shape_is_not_verified(self):
        self.write_record({"about": "a comparison written some other way"})
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "superposition"), "skip", output)
        self.assertIn("no shape this knows", output)
        self.assertEqual(code, 1, output)  # it had subject matter and could not look

    def test_comparison_takes_the_directory_the_record_lives_in(self):
        # The mutation laboratory writes the map under test into a temporary directory, where
        # nothing sits beside it, and names the record's home instead.
        # The record's home is named on the command line, so it need not be called
        # `blind-mapping` and need not be beside anything.
        home = os.path.join(self.root, "adjudication")
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, "resolutions.json"), "w") as handle:
            json.dump(self.other_words(), handle)
        elsewhere = os.path.join(self.root, "moved")
        os.makedirs(elsewhere, exist_ok=True)
        document = valid_map()
        document["entries"][self.OPEN]["clarity"] = "clear"
        document["entries"][self.OPEN].pop("ambiguity")
        path = os.path.join(elsewhere, "corpus-map.json")
        with open(path, "w") as handle:
            json.dump(document, handle)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_map.main([path, "--repo-root", self.root, "--manifest", self.manifest_path,
                                   "--comparison", home])
        output = out.getvalue() + err.getvalue()
        self.assertEqual(self.status_of(output, "superposition"), "fail", output)
        self.assertIn("premature collapse", output)
        self.assertEqual(code, 1, output)

    def test_a_map_nobody_mapped_twice_does_not_report_ok(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "superposition"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)

    def test_every_committed_adjudication_record_is_of_the_one_shape(self):
        # #273's acceptance: four committed records, one shape, and each declares the
        # vocabulary its own verdicts are written in.
        repo = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        records = sorted(glob.glob(os.path.join(repo, "examples", "*", "blind-mapping",
                                                "resolutions.json")))
        self.assertEqual(len(records), 4, records)
        for path in records:
            with self.subTest(record=os.path.relpath(path, repo)):
                with open(path, encoding="utf-8") as handle:
                    record = json.load(handle)
                self.assertIsNotNone(check_map._adjudications(record), "not the one shape")
                legend = record["verdicts"]
                self.assertIn(record["unsettledVerdict"], legend)
                for row in record["adjudications"]:
                    self.assertIn(row.get("verdict"), legend, row.get("id"))

    def test_the_census_counts_ambiguities_nothing_corroborates(self):
        # 0034 adds no field for competing readings, so the number of ambiguities resting on
        # `ambiguity.question` alone is printed rather than argued about.
        self.write_record(self.record())
        document = valid_map()
        document["entries"].append(decided_entry())
        # A third ambiguity with no conflict, no bound, no decision record and no adjudication:
        # the shape 31 of the 64 ambiguities in the committed maps have.
        document["entries"].append(entry(
            "sparsely-populated-area", kind="operation", clarity="ambiguous", status="mapped",
            ambiguity={"question": "The corpus never defines a sparsely populated area.",
                       "fate": "unresolved", "unresolvedReason": "RequiresInterpretation"}))
        code, output = self.run_tool(document)
        self.assertIn("2 of 3 recorded ambiguities carry a second reading something can read, "
                      "and 1 rest on `ambiguity.question` alone", output)


class TestDriver(MapCase):
    def test_an_unknown_check_name_is_a_usage_error(self):
        code, output = self.run_tool(valid_map(), argv=["--only", "spelling"])
        self.assertEqual(code, 2, output)

    def test_only_runs_one_check(self):
        code, output = self.run_tool(valid_map(), argv=["--only", "vocabulary"])
        self.assertEqual(code, 0, output)
        self.assertEqual(len(re.findall(r"^\[(ok|fail|skip)\]", output, re.M)), 1, output)

    def test_a_run_in_which_nothing_passed_is_not_a_pass(self):
        code, output = self.run_tool(valid_map(), argv=["--only", "conflicts"])
        self.assertEqual(code, 1, output)
        self.assertIn("nothing was actually checked", output)

    def test_an_unreadable_map_is_a_usage_error(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = check_map.main([os.path.join(self.example, "absent.json")])
        self.assertEqual(code, 2, out.getvalue())


class TestPreviousVersion(MapCase):
    """#268: a check whose subject matter the damage removed said NOT VERIFIED and passed the run.

    That is the right outcome for a corpus that genuinely has no assertions and no gates. It is
    the wrong one when the damage is what removed them, and the map a published version replaces
    is where the validator can tell the two apart.
    """

    ASSERTION = 2  # well-clear, the fixture's only `kind: assertion`

    def previous(self, document):
        """`--previous PATH` for a map written outside the directory the checks read."""
        path = os.path.join(self.root, "previous-corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        return ["--previous", path]

    def silenced(self):
        """valid_map with its only assertion re-recorded as something the engine computes.

        `tools/mutate-map.py --only assertion-to-operation`, exactly: `asserted-by` is left with
        nothing to look at, says so, and declares it had no subject.
        """
        document = valid_map()
        document["entries"][self.ASSERTION]["kind"] = "operation"
        document["entries"][self.ASSERTION].pop("assertedBy")
        return document

    def test_without_a_predecessor_the_silenced_check_still_passes_the_run(self):
        # The measured defect, written down so the fix is visible as a change of verdict.
        code, output = self.run_tool(self.silenced())
        self.assertEqual(self.status_of(output, "asserted-by"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_a_check_that_had_subject_matter_in_the_version_it_replaces_fails(self):
        code, output = self.run_tool(self.silenced(), argv=self.previous(valid_map()))
        self.assertEqual(self.status_of(output, "asserted-by"), "fail", output)
        self.assertIn("had subject matter for it", output)
        self.assertEqual(code, 1, output)

    def test_a_check_with_no_subject_matter_in_either_version_still_only_skips(self):
        # `conflicts` has nothing to look at in valid_map and nothing here: no claim is made
        # about the corpus by a rule that was vacuous before and is vacuous now.
        code, output = self.run_tool(valid_map(), argv=self.previous(valid_map()))
        self.assertEqual(self.status_of(output, "conflicts"), "skip", output)
        self.assertEqual(code, 0, output)

    def test_the_map_replacing_itself_changes_no_verdict(self):
        document = valid_map()
        code, output = self.run_tool(document, argv=self.previous(document))
        self.assertEqual(code, 0, output)

    def test_an_unreadable_previous_map_is_a_usage_error(self):
        code, output = self.run_tool(
            valid_map(), argv=["--previous", os.path.join(self.root, "absent.json")])
        self.assertEqual(code, 2, output)

    def test_the_run_says_which_version_it_read(self):
        code, output = self.run_tool(valid_map(), argv=self.previous(valid_map()))
        self.assertIn("previous-corpus-map.json", output)


class TestPhaseSplit(MapCase):
    """0015: the split between publish-time and consumer-side checks is read from the tool.

    An overlay sets `status`, `implementedIn` and `tests` on the entries it names. A check
    marked structural must give the same verdict whatever those hold, or the engine is
    trusting a publish-time verdict its own overlay could have overturned. A check marked
    status-dependent must be turnable by them, or the engine re-runs it for nothing and the
    marking has drifted from the code.
    """

    def subject(self):
        """valid_map plus the shapes that make the skipping checks do work."""
        document = valid_map()
        document["entries"].append(decided_entry())
        for side in ("left", "right"):
            document["entries"].append(entry(
                f"tie-{side}", kind="operation", clarity="ambiguous",
                ambiguity={"question": "Which side wins a tie?", "fate": "unresolved",
                           "unresolvedReason": "RequiresInterpretation", "conflict": "tie"}))
        return document

    def overlays(self):
        """Every way an overlay can set the three fields, applied across the whole map."""
        def each(apply):
            document = self.subject()
            for position, item in enumerate(document["entries"]):
                apply(position, item)
            return document

        def set_status(value):
            return lambda _, item: item.__setitem__("status", value)

        def strip(_, item):
            item.pop("implementedIn", None)
            item.pop("tests", None)

        def garbage(_, item):
            item["implementedIn"] = {"ruleset": "elsewhere", "version": 99}
            item["tests"] = "not a list"

        def implemented_bare(_, item):
            item["status"] = "implemented"
            item.pop("implementedIn", None)
            item["tests"] = []

        def alternate(position, item):
            item["status"] = ("implemented", "declined", "blocked", "mapped")[position % 4]
            if position % 2:
                strip(position, item)

        variants = [each(set_status(s)) for s in sorted(check_map.STATUSES) + ["bogus"]]
        return variants + [each(strip), each(garbage), each(implemented_bare), each(alternate)]

    def verdict_of(self, check, document):
        with open(self.manifest_path) as handle:
            manifest = json.load(handle)
        ctx = {"map": document, "manifest": manifest, "manifest_path": self.manifest_path,
               "repo_root": self.root, "verbose": False}
        result = check(ctx)
        return result.status, sorted(result.details)

    def test_the_overlay_fields_are_the_ones_0015_names(self):
        self.assertEqual(check_map.OVERLAY_FIELDS, ("status", "implementedIn", "tests"))

    def test_every_marked_check_exists(self):
        self.assertLessEqual(check_map.STATUS_DEPENDENT, {name for name, _ in check_map.CHECKS})

    def test_a_structural_check_cannot_be_turned_by_an_overlay(self):
        for name, check in check_map.CHECKS:
            if name in check_map.STATUS_DEPENDENT:
                continue
            with self.subTest(check=name):
                baseline = self.verdict_of(check, self.subject())
                for variant in self.overlays():
                    self.assertEqual(self.verdict_of(check, variant), baseline,
                                     f"{name} reads an overlay field but is not in STATUS_DEPENDENT")

    def test_a_status_dependent_check_can_be_turned_by_an_overlay(self):
        for name, check in check_map.CHECKS:
            if name not in check_map.STATUS_DEPENDENT:
                continue
            with self.subTest(check=name):
                baseline = self.verdict_of(check, self.subject())
                turned = [v for v in self.overlays() if self.verdict_of(check, v) != baseline]
                self.assertTrue(turned, f"{name} is in STATUS_DEPENDENT but no overlay changes it")

    def test_the_consumer_phase_runs_only_the_status_dependent_checks(self):
        code, output = self.run_tool(valid_map(), argv=["--phase", "consumer"])
        self.assertEqual(code, 0, output)
        ran = set(re.findall(r"^\[(?:ok|fail|skip)\] (\S+):", output, re.M))
        self.assertEqual(ran, check_map.STATUS_DEPENDENT, output)

    def test_the_consumer_phase_fails_implemented_without_implemented_in(self):
        # #39's acceptance case, on the consumer side: an overlay that says `implemented`
        # and names no revision.
        document = valid_map()
        document["entries"][0].pop("implementedIn")
        code, output = self.run_tool(document, argv=["--phase", "consumer"])
        self.assertEqual(code, 1, output)
        self.assertEqual(self.status_of(output, "status"), "fail", output)

    def test_the_publish_phase_is_the_default_and_runs_every_check(self):
        code, output = self.run_tool(valid_map(), argv=["--phase", "publish"])
        ran = set(re.findall(r"^\[(?:ok|fail|skip)\] (\S+):", output, re.M))
        self.assertEqual(ran, {name for name, _ in check_map.CHECKS}, output)


if __name__ == "__main__":
    unittest.main()
