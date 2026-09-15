#!/usr/bin/env python3
"""Every check in check-map.py, proved able to fail.

The pattern is one test per check: build a map the spec says is valid, assert the named
check reports `ok`, mutate exactly the thing that check exists to catch, and assert the
same check reports `fail`. A check with no failing test here is a check nobody has shown
can fail, which is the class of gate this repository most distrusts.

The fixture is written from `docs/corpus-map.md` and `docs/decisions/0005`, not from the
example maps -- an expectation drawn from the thing under test proves nothing, and the
example maps are mid-migration.

Run: python3 -m unittest discover -s tools/tests
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
TOOL = os.path.join(os.path.dirname(HERE), "check-map.py")

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
            entry("yield-right-of-way", kind="operation", dependsOn=["well-clear"],
                  enabledBy=["speed-limit"], suspendedBy=["speed-within-limit"],
                  status="implemented",
                  implementedIn={"ruleset": "demo", "version": 1},
                  tests=proof("RightOfWayTests.Passing_over_is_refused")),
            entry("hazardous-material", kind="value", status="declined",
                  definedElsewhere={"reference": "other-corpus"}),
            entry("inner-table-handedness", kind="value", status="declined",
                  beyondAdapter={"adapter": "plain-text", "modality": "illustration"}),
            entry("subpart-d-categories", scope="out", status="declined"),
            entry("must-play-whole-throw", kind="operation", clarity="ambiguous",
                  status="implemented", implementedIn={"ruleset": "demo", "version": 1},
                  tests=proof("WholeThrowTests.Either_die_alone_but_not_both_declines"),
                  ambiguity={
                      "question": "The text does not say what happens when only one die is playable.",
                      "fate": "unresolved",
                      "unresolvedReason": "RequiresInterpretation",
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
                 ambiguity={
                     "question": "The text does not say which side prevails on equal hits.",
                     "fate": "decision",
                     "decision": "docs/decisions/0007-opposed-test-tie-break.md",
                 })


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

    def assert_catches(self, check, mutate, expect="fail"):
        """The valid map passes this check; the mutation makes this check report `expect`."""
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, check), "ok", output)
        self.assertEqual(code, 0, output)
        document = valid_map()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, check), expect, output)
        self.assertEqual(code, 1, output)


# --- one test per check ------------------------------------------------------------------


class TestFixtureIsValid(MapCase):
    def test_the_valid_map_passes_every_check(self):
        code, output = self.run_tool(valid_map())
        self.assertEqual(code, 0, output)
        self.assertNotIn("[fail]", output, output)
        # `conflicts` and `decision-records` skip without subject matter; nothing else may.
        skipped = re.findall(r"^\[skip\] (\S+):", output, re.M)
        self.assertEqual(sorted(skipped), ["conflicts", "decision-records"], output)


class TestSchema(MapCase):
    def test_a_map_without_its_baseline_stamp_fails(self):
        self.assert_catches("schema", lambda d: d.pop("baseline"))

    def test_a_baseline_without_its_derivation_fails(self):
        self.assert_catches("schema", lambda d: d["baseline"].pop("hashDerivation"))

    def test_a_schema_version_this_checker_does_not_read_fails(self):
        self.assert_catches("schema", lambda d: d.update(schemaVersion=2))


    def test_an_inline_manifest_is_refused_rather_than_ignored(self):
        # #60: the blind Part 107 map carried `manifest` inline, and the checker reported "no
        # manifest" and skipped every resolution while the key sat there unread.
        self.assert_catches("schema", lambda d: d.update(manifest=MANIFEST))

    def test_an_unknown_top_level_field_is_refused(self):
        self.assert_catches("schema", lambda d: d.update(coverage="twelve sections"))

    def test_every_example_map_uses_only_known_top_level_fields(self):
        # The closed envelope must not break a map the repository already ships.
        repo = os.path.dirname(os.path.dirname(HERE))
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
        """valid_map, re-cited in the section-designation grammar with an extent of two sections."""
        document = valid_map()
        document["extent"] = {"unit": "section-designation", "sections": ["§ 1.10", "§ 1.11"]}
        for position, item in enumerate(document["entries"]):
            if "locator" in item:
                item["locator"]["citation"] = ("§ 1.10(a)", "§ 1.11 introductory text")[position % 2]
        return document

    def assert_section_catches(self, mutate):
        code, output = self.run_tool(self.section_map())
        self.assertEqual(self.status_of(output, "extent"), "ok", output)
        self.assertEqual(code, 0, output)
        document = self.section_map()
        mutate(document)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "extent"), "fail", output)
        self.assertEqual(code, 1, output)
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
        self.assert_catches("extent", lambda d: d["extent"].update(endsBefore=""))

    def test_an_ends_before_that_is_not_one_line_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update(endsBefore="Damage\nand Healing"))

    def test_an_ends_before_that_is_not_text_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update(endsBefore=16))

    def test_starts_after_is_not_a_field_of_a_page_extent(self):
        # No real case needs it (0024), so it is refused like any other unknown field.
        self.assert_catches("extent", lambda d: d["extent"].update(startsAfter="Combat"))

    def test_a_page_extent_that_is_not_a_range_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update({"from": 4, "to": 1}))

    def test_a_page_extent_with_a_non_integer_bound_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update({"to": "280"}))

    def test_an_extent_in_an_unknown_unit_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update({"unit": "paragraph"}))

    def test_an_extent_mixing_the_two_shapes_fails(self):
        self.assert_catches("extent", lambda d: d["extent"].update({"sections": ["§ 1.10"]}))

    def test_a_citation_outside_the_declared_sections_fails(self):
        output = self.assert_section_catches(
            lambda d: d["entries"][0]["locator"].update(citation="§ 1.12(b)"))
        self.assertIn("§ 1.12", output)

    def test_a_section_list_holding_a_paragraph_fails(self):
        self.assert_section_catches(lambda d: d["extent"]["sections"].append("§ 1.12(a)"))

    def test_a_section_listed_twice_fails(self):
        self.assert_section_catches(lambda d: d["extent"]["sections"].append("§ 1.10"))

    def test_an_empty_section_list_fails(self):
        self.assert_section_catches(lambda d: d["extent"].update(sections=[]))

    def test_a_citation_in_no_section_grammar_fails(self):
        self.assert_section_catches(
            lambda d: d["entries"][0]["locator"].update(citation="Part One / p. 1"))

    def test_an_in_scope_entry_citing_a_subpart_outside_the_extent_fails(self):
        # speed-limit is scope: in.
        self.assert_section_catches(
            lambda d: d["entries"][0]["locator"].update(citation="subpart D"))

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
        self.assert_section_catches(mutate)

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
        repo = os.path.dirname(os.path.dirname(HERE))
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


class TestRequiredFields(MapCase):
    def test_an_entry_without_a_locator_is_not_an_entry(self):
        self.assert_catches("required-fields", lambda d: d["entries"][0].pop("locator"))

    def test_a_locator_without_a_citation_fails(self):
        self.assert_catches("required-fields", lambda d: d["entries"][0]["locator"].pop("citation"))

    def test_a_missing_status_fails(self):
        self.assert_catches("required-fields", lambda d: d["entries"][2].pop("status"))


class TestVocabulary(MapCase):
    def test_kind_outside_the_closed_vocabulary_fails(self):
        # The live instance: `direction-of-travel` shipped as kind "rule" in both copies
        # of the backgammon map because nothing consumed `kind`.
        self.assert_catches("vocabulary", lambda d: d["entries"][0].update(kind="rule"))

    def test_scope_outside_the_closed_vocabulary_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][0].update(scope="partial"))

    def test_clarity_outside_the_closed_vocabulary_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][0].update(clarity="murky"))

    def test_status_outside_the_closed_vocabulary_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][0].update(status="in-progress"))

    def test_fate_outside_the_closed_vocabulary_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][7]["ambiguity"].update(fate="deferred"))

    def test_an_unresolved_reason_outside_the_kernel_enum_fails(self):
        self.assert_catches(
            "vocabulary",
            lambda d: d["entries"][7]["ambiguity"].update(unresolvedReason="CorpusDisagreesWithItself"),
        )

    def test_beyond_adapter_without_a_modality_fails(self):
        self.assert_catches("vocabulary", lambda d: d["entries"][5]["beyondAdapter"].pop("modality"))


class TestUniqueIds(MapCase):
    def test_a_duplicated_id_fails(self):
        self.assert_catches("unique-ids", lambda d: d["entries"][1].update(id="speed-limit"))


class TestReferences(MapCase):
    def test_a_dangling_depends_on_fails(self):
        self.assert_catches("references", lambda d: d["entries"][1].update(dependsOn=["no-such-entry"]))

    def test_a_dangling_enabled_by_fails(self):
        # 0003: a gate with no entry means the map is missing an entry.
        self.assert_catches("references", lambda d: d["entries"][3].update(enabledBy=["all-men-home"]))

    def test_a_dangling_suspended_by_fails(self):
        self.assert_catches("references", lambda d: d["entries"][3].update(suspendedBy=["man-on-bar"]))

    def test_a_gate_holding_a_condition_rather_than_an_id_fails(self):
        self.assert_catches("references", lambda d: d["entries"][3].update(suspendedBy=[{"onBar": True}]))

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
        self.assert_catches("gates", mutate)

    def test_one_rule_both_enabling_and_suspending_an_entry_fails(self):
        self.assert_catches(
            "gates", lambda d: d["entries"][self.GATED]["suspendedBy"].append("speed-limit"))

    def test_a_map_with_no_gates_does_not_report_ok(self):
        # A map with no gates, like the Part 107 temporal map: nothing was checked, and it proves nothing.
        document = valid_map()
        document["entries"][self.GATED].pop("enabledBy")
        document["entries"][self.GATED].pop("suspendedBy")
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "gates"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)


class TestNoCycles(MapCase):
    def test_a_depends_on_cycle_fails(self):
        def mutate(document):
            document["entries"][0]["dependsOn"] = ["speed-within-limit"]
        self.assert_catches("no-cycles", mutate)

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
        self.assert_catches("required-fields", lambda d: d["entries"][self.DERIVED].pop("derivedFrom"))

    def test_a_derived_entry_that_quotes_a_span_fails(self):
        # `evidence` keeps one meaning: a verbatim span. A derived fact has none to quote.
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED].update(evidence="A gammon pays double."))

    def test_a_derived_entry_that_cites_a_passage_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED].update(
                locator={"sourceId": "demo-corpus", "citation": "Part One / p. 1"}))

    def test_a_derived_entry_carrying_a_cross_reference_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED].update(
                crossReferences=[{"cites": "as at starting", "resolvedBy": "speed-limit"}]))

    def test_a_source_that_is_not_an_entry_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED]["derivedFrom"].append("no-such-entry"))

    def test_a_source_out_of_scope_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED]["derivedFrom"].append("subpart-d-categories"))

    def test_deriving_from_an_absent_rule_fails(self):
        # An absence is scope: out, so the scope rule is what refuses it.
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED]["derivedFrom"].append("doubling-cube"))

    def test_a_derivation_from_one_source_fails(self):
        # A consequence of one entry is that entry's, discharged as a test it names.
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED].update(derivedFrom=["speed-limit"]))

    def test_a_derivation_naming_itself_fails(self):
        self.assert_catches(
            "derived", lambda d: d["entries"][self.DERIVED]["derivedFrom"].append("hit-pays-single-stake"))

    def test_a_circular_derivation_fails(self):
        def mutate(document):
            document["entries"].append(
                derived_entry("gammon-pays-double", ["hit-pays-single-stake", "speed-limit"]))
            document["entries"][self.DERIVED]["derivedFrom"] = ["gammon-pays-double", "speed-limit"]
        self.assert_catches("derived", mutate)

    def test_a_map_with_no_derived_entries_does_not_report_ok(self):
        document = valid_map()
        document["entries"].pop(self.DERIVED)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "derived"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 0, output)


class TestManifest(MapCase):
    def test_a_locator_source_not_in_the_manifest_fails(self):
        self.assert_catches("manifest", lambda d: d["entries"][0]["locator"].update(sourceId="unknown-corpus"))

    def test_a_beyond_adapter_naming_the_wrong_adapter_fails(self):
        # 0004: the adapter must match the one declared for the entry's source.
        self.assert_catches("manifest", lambda d: d["entries"][5]["beyondAdapter"].update(adapter="pdf"))

    def test_a_defined_elsewhere_reference_not_in_references_fails(self):
        # 0005: an elsewhere-defined *input* has no corpus to name and would not validate.
        self.assert_catches("manifest", lambda d: d["entries"][4]["definedElsewhere"].update(reference="airspace"))

    def test_a_baseline_disagreeing_with_the_manifest_fails(self):
        self.assert_catches("manifest", lambda d: d["baseline"].update(contentHash="b" * 64))

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
                            .update(defect="joined-hyphenation"))

    def test_a_defect_without_a_rendered_reading_fails(self):
        self.assert_catches("extraction", lambda d: d["entries"][self.GARBLED]["extraction"]
                            .pop("renderedReading"))

    def test_a_rendered_reading_that_is_the_evidence_fails(self):
        def mutate(document):
            garbled = document["entries"][self.GARBLED]
            garbled["extraction"]["renderedReading"] = "  " + garbled["evidence"].replace(" ", "\n")
        self.assert_catches("extraction", mutate)

    def test_an_unknown_field_of_extraction_fails(self):
        self.assert_catches("extraction", lambda d: d["entries"][self.GARBLED]["extraction"]
                            .update(checkedBy="a person"))

    def test_an_extraction_that_is_not_an_object_fails(self):
        self.assert_catches("extraction", lambda d: d["entries"][self.GARBLED]
                            .update(extraction="interleaved-table"))

    def test_extraction_beside_beyond_adapter_fails(self):
        self.assert_catches("extraction", lambda d: d["entries"][self.GARBLED].update(
            beyondAdapter={"adapter": "plain-text", "modality": "table"}))

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

    # 0028: a text derived for the printed pages the manifest declares names its derivation whole.
    def printed_page_derivation(self, corpus):
        corpus.update(hashDerivation="pdftotext-24.02.0-printed-page-marked",
                      sourcePdf={"sha256": "b" * 64, "bytes": 1024, "envVar": "DEMO_PDF"},
                      derivedText={"extractor": "pdftotext", "extractorVersion": "24.02.0",
                                   "pdfPageOffset": 1,
                                   "printedPages": [{"from": 35, "to": 36}, {"from": 44, "to": 44}]})
        corpus["quotedText"]["derivation"] = "pdftotext-24.02.0-printed-page-marked"

    def assert_derivation_catches(self, mutate, expected):
        self.manifest_without(self.printed_page_derivation)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "extraction"), "ok", output)
        self.assertIn("1 printed-page derivation well formed", output)

        def both(corpus):
            self.printed_page_derivation(corpus)
            mutate(corpus)
        self.manifest_without(both)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "extraction"), "fail", output)
        self.assertIn(expected, output)

    def test_a_printed_page_derivation_without_derived_text_fails(self):
        self.assert_derivation_catches(lambda c: c.pop("derivedText"), "declares no `derivedText`")

    def test_derived_text_under_another_derivation_fails(self):
        def mutate(corpus):
            corpus["hashDerivation"] = corpus["quotedText"]["derivation"] = "demo-plain-text"
        self.assert_derivation_catches(mutate, "the derivation that field describes")

    def test_derived_text_without_quoted_text_fails(self):
        self.assert_derivation_catches(lambda c: c.pop("quotedText"), "and no `quotedText`")

    def test_another_extractor_version_fails(self):
        self.assert_derivation_catches(lambda c: c["derivedText"].update(extractorVersion="25.01.0"),
                                       "is pinned to pdftotext 24.02.0")

    def test_an_offset_that_is_not_an_integer_fails(self):
        self.assert_derivation_catches(lambda c: c["derivedText"].update(pdfPageOffset="+1"),
                                       "pdfPageOffset is '+1'")

    def test_overlapping_page_ranges_fail(self):
        self.assert_derivation_catches(lambda c: c["derivedText"]["printedPages"].append({"from": 44, "to": 45}),
                                       "list them ascending and disjoint")

    def test_a_page_before_the_pdf_starts_fails(self):
        def mutate(corpus):
            corpus["derivedText"]["pdfPageOffset"] = -40
        self.assert_derivation_catches(mutate, "on pages the PDF has")

    def test_an_unknown_field_of_derived_text_fails(self):
        self.assert_derivation_catches(lambda c: c["derivedText"].update(wholeBook=True),
                                       "`wholeBook` is not a field of derivedText")

    def test_a_source_pdf_digest_that_is_the_content_hash_fails(self):
        self.assert_derivation_catches(lambda c: c["sourcePdf"].update(sha256=c["contentHash"]),
                                       "the PDF's digest is a different fact")

    def test_derived_text_without_a_source_pdf_fails(self):
        self.assert_derivation_catches(lambda c: c.pop("sourcePdf"), "and no `sourcePdf` object")

    def test_a_derived_entry_carrying_extraction_fails(self):
        self.assert_catches("derived", lambda d: d["entries"][10].update(
            extraction={"defect": "interleaved-table", "renderedReading": "Half | +2"}))

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
    """Append an entry citing the withheld corpus, carrying no span -- as 0013 requires."""
    document["entries"].append(entry("opposed-test-tie", locator={
        "sourceId": "core-rules", "citation": "Game Concepts / p. 36"}))
    document["entries"][-1].pop("evidence")
    return document


class TestExclusions(MapCase):
    def test_an_ambiguity_block_beside_defined_elsewhere_fails(self):
        def mutate(document):
            document["entries"][4]["ambiguity"] = {
                "question": "Defined by reference to a corpus not admitted.",
                "fate": "unresolved",
                "unresolvedReason": "MissingRulesData",
            }
            document["entries"][4]["clarity"] = "ambiguous"
        self.assert_catches("exclusions", mutate)

    def test_an_ambiguity_block_beside_beyond_adapter_fails(self):
        def mutate(document):
            document["entries"][5]["clarity"] = "ambiguous"
            document["entries"][5]["ambiguity"] = {
                "question": "The rule is in a figure.",
                "fate": "unresolved",
                "unresolvedReason": "MissingRulesData",
            }
        self.assert_catches("exclusions", mutate)

    def test_an_ambiguity_block_on_a_clear_entry_fails(self):
        def mutate(document):
            document["entries"][7]["clarity"] = "clear"
        self.assert_catches("exclusions", mutate)

    def test_an_ambiguous_entry_without_an_ambiguity_block_fails(self):
        def mutate(document):
            document["entries"][7].pop("ambiguity")
        self.assert_catches("exclusions", mutate)

    def test_a_decision_fate_naming_no_record_fails(self):
        def mutate(document):
            document["entries"][7]["ambiguity"] = {
                "question": "Two readings.",
                "fate": "decision",
            }
        self.assert_catches("exclusions", mutate)

    def test_an_unresolved_fate_without_its_reason_fails(self):
        self.assert_catches("exclusions", lambda d: d["entries"][7]["ambiguity"].pop("unresolvedReason"))


class TestStatus(MapCase):
    def test_implemented_without_implemented_in_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0].pop("implementedIn"))

    def test_implemented_in_on_an_unbuilt_entry_fails(self):
        self.assert_catches("status", lambda d: d["entries"][2].update(implementedIn={"ruleset": "demo", "version": 1}))

    def test_implemented_naming_no_tests_fails(self):
        # #2: `implemented` stops being a word someone typed. Without tests it is `mapped`.
        self.assert_catches("status", lambda d: d["entries"][0].pop("tests"))

    def test_implemented_with_an_empty_tests_list_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0].update(tests=[]))

    def test_a_test_with_no_recorded_mutation_fails(self):
        # A test nobody has seen go red is the class of test this repository keeps finding.
        self.assert_catches("status", lambda d: d["entries"][1]["tests"][1].pop("mutation"))

    def test_a_blank_mutation_fails(self):
        self.assert_catches("status", lambda d: d["entries"][1]["tests"][0].update(mutation="  "))

    def test_a_tests_item_naming_no_test_fails(self):
        self.assert_catches("status", lambda d: d["entries"][1]["tests"][0].pop("test"))

    def test_a_test_named_twice_fails(self):
        def mutate(document):
            tests = document["entries"][1]["tests"]
            tests[1]["test"] = tests[0]["test"]
        self.assert_catches("status", mutate)

    def test_a_bare_test_name_without_its_mutation_fails(self):
        self.assert_catches("status", lambda d: d["entries"][0].update(tests=["SpeedLimitTests.The_limit_is_87_knots"]))

    def test_malformed_tests_on_an_unbuilt_entry_still_fail(self):
        # The shape holds wherever the field appears, not only where it is required.
        self.assert_catches("status", lambda d: d["entries"][2].update(tests=[{"test": "WellClearTests.X"}]))

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


class TestAbsent(MapCase):
    """0009: `absentFrom` separates 'the corpus does not state it' from 'we declined it'."""

    ABSENT = 8  # doubling-cube, in valid_map()'s order

    def test_an_absent_rule_the_map_still_claims_to_cover_fails(self):
        # scope: out is not decoration here -- row 1 must dominate, and 0008's procedure
        # has scope: in as its precondition, so an absent rule must never reach the gates.
        self.assert_catches("absent", lambda d: d["entries"][self.ABSENT].update(scope="in"))

    def test_an_absent_rule_recorded_as_unbuilt_rather_than_declined_fails(self):
        self.assert_catches("absent", lambda d: d["entries"][self.ABSENT].update(status="mapped"))

    def test_absent_beside_beyond_adapter_fails(self):
        # Nowhere in the corpus and somewhere in it we cannot reach are different claims.
        self.assert_catches(
            "absent",
            lambda d: d["entries"][self.ABSENT].update(
                beyondAdapter={"adapter": "plain-text", "modality": "illustration"}),
        )

    def test_absent_beside_defined_elsewhere_fails(self):
        self.assert_catches(
            "absent",
            lambda d: d["entries"][self.ABSENT].update(definedElsewhere={"reference": "other-corpus"}),
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
        self.assert_catches("absent", mutate)

    def test_an_absent_rule_that_depends_on_something_fails(self):
        self.assert_catches(
            "absent", lambda d: d["entries"][self.ABSENT].update(dependsOn=["speed-limit"]))

    def test_depending_on_an_absent_rule_fails(self):
        # The edge can never be satisfied: `blocked` that will never clear.
        self.assert_catches(
            "absent", lambda d: d["entries"][1].update(dependsOn=["doubling-cube"]))

    def test_enabling_on_an_absent_rule_fails(self):
        self.assert_catches(
            "absent", lambda d: d["entries"][3].update(enabledBy=["doubling-cube"]))

    def test_suspending_on_an_absent_rule_fails(self):
        self.assert_catches(
            "absent", lambda d: d["entries"][3].update(suspendedBy=["doubling-cube"]))

    def test_an_absence_nobody_searched_for_fails_the_vocabulary(self):
        # An empty `searched` is the "(absent)" locator in a new spelling: a claim with
        # nothing behind it. It is caught where the field's shape is checked.
        self.assert_catches(
            "vocabulary", lambda d: d["entries"][self.ABSENT]["absentFrom"].update(searched=[]))

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
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].pop("assertedBy"))

    def test_asserted_by_on_an_entry_that_is_not_an_assertion_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][1].update(assertedBy=["remote pilot"]))

    def test_an_empty_or_malformed_list_fails(self):
        for value in ([], "remote pilot", [""], [3]):
            with self.subTest(value=value):
                self.assert_catches("asserted-by",
                                    lambda d, v=value: d["entries"][self.ASSERTION].update(assertedBy=v))

    def test_a_party_named_twice_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(
            assertedBy=["remote pilot", "Remote  Pilot"]))

    def test_a_party_the_evidence_does_not_name_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(
            assertedBy=["visual observer"]))

    def test_a_party_matches_as_a_whole_word_only(self):
        # "pilot" inside "autopilot" is not the pilot.
        def mutate(document):
            document["entries"][self.ASSERTION].update(
                assertedBy=["pilot"], evidence="The autopilot must keep the aircraft well clear.")
        self.assert_catches("asserted-by", mutate)

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
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(assertedBy=["caller"]))
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(
            assertedBy=["caller"], note="Asserted, never inferred."))

    def test_the_caller_beside_a_named_party_fails(self):
        self.assert_catches("asserted-by", lambda d: d["entries"][self.ASSERTION].update(
            assertedBy=["caller", "remote pilot"], note="The caller, or the remote pilot."))

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
              ambiguity={"question": "What is a group?", "fate": "unresolved",
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
            "cross-references", lambda d: d["entries"][self.POINTER].pop("crossReferences"))

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
                cites="as provided in paragraph (d)"),
        )

    def test_a_declaration_resolving_to_no_entry_fails(self):
        self.assert_catches(
            "cross-references",
            lambda d: d["entries"][self.POINTER]["crossReferences"][0].update(
                resolvedBy="no-such-entry"),
        )

    def test_a_declaration_resolving_to_itself_fails(self):
        self.assert_catches(
            "cross-references",
            lambda d: d["entries"][self.POINTER]["crossReferences"][0].update(
                resolvedBy="next-game-opening"),
        )

    def test_a_declaration_resolving_to_nothing_at_all_fails(self):
        self.assert_catches(
            "cross-references",
            lambda d: d["entries"][self.POINTER]["crossReferences"][0].pop("resolvedBy"),
        )

    def test_a_declaration_claiming_both_arms_fails(self):
        # A reference is an entry or a recorded reason there is none, not both.
        self.assert_catches(
            "cross-references",
            lambda d: d["entries"][self.POINTER]["crossReferences"][0].update(
                unmapped="The figure is not a passage."),
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
        root = os.path.dirname(os.path.dirname(HERE))
        for path in sorted(glob.glob(os.path.join(root, "examples", "*", "corpus-map*.json"))):
            with self.subTest(map=os.path.relpath(path, root)):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = check_map.main([path, "--only", "cross-references"])
                output = out.getvalue() + err.getvalue()
                self.assertEqual(code, 0, output)
                self.assertRegex(output, r"\[ok\] cross-references: [\w.-]+: [1-9]\d* pointers? in ")
                self.assertIn("declared phrase", output)


class TestCorrespondence(MapCase):
    def test_a_declined_entry_with_no_row_fails(self):
        # `declined` claims no implemented path at all, so some row owes an answer.
        def mutate(document):
            document["entries"][4].pop("definedElsewhere")
        self.assert_catches("correspondence", mutate)

    def test_defined_elsewhere_and_beyond_adapter_together_fail(self):
        def mutate(document):
            document["entries"][4]["beyondAdapter"] = {"adapter": "plain-text", "modality": "illustration"}
        self.assert_catches("correspondence", mutate)

    def test_an_assertion_that_also_declines_fails(self):
        # Row 8: an assertion is a parameter, not a failure to resolve.
        def mutate(document):
            document["entries"][2]["beyondAdapter"] = {"adapter": "plain-text", "modality": "illustration"}
        self.assert_catches("correspondence", mutate)

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
