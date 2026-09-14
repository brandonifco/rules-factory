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
            "boundaryPolicy": "pin-in-repo",
            "licence": "public-domain",
            "references": [{"sourceId": "other-corpus", "citation": "s 1", "admitted": False}],
        }
    ],
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


def valid_map():
    """A map exercising every shape the spec describes, and nothing the spec forbids."""
    return {
        "schemaVersion": 1,
        "corpus": "demo-corpus",
        "baseline": {"contentHash": "a" * 64, "hashDerivation": "demo-plain-text"},
        "entries": [
            entry("speed-limit", kind="value", status="implemented",
                  implementedIn={"ruleset": "demo", "version": 1}),
            entry("speed-within-limit", kind="operation", dependsOn=["speed-limit"],
                  status="implemented", implementedIn={"ruleset": "demo", "version": 1}),
            entry("well-clear", kind="assertion", status="mapped"),
            entry("yield-right-of-way", kind="operation", dependsOn=["well-clear"],
                  gatedBy=["speed-limit"], status="implemented",
                  implementedIn={"ruleset": "demo", "version": 1}),
            entry("hazardous-material", kind="value", status="declined",
                  definedElsewhere={"reference": "other-corpus"}),
            entry("inner-table-handedness", kind="value", status="declined",
                  beyondAdapter={"adapter": "plain-text", "modality": "illustration"}),
            entry("subpart-d-categories", scope="out", status="declined"),
            entry("must-play-whole-throw", kind="operation", clarity="ambiguous",
                  status="implemented", implementedIn={"ruleset": "demo", "version": 1},
                  ambiguity={
                      "question": "The text does not say what happens when only one die is playable.",
                      "fate": "unresolved",
                      "unresolvedReason": "RequiresInterpretation",
                  }),
        ],
    }


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

    def test_a_dangling_gated_by_fails(self):
        # 0003: a gate with no entry means the map is missing an entry.
        self.assert_catches("references", lambda d: d["entries"][3].update(gatedBy=["all-men-home"]))

    def test_a_gated_by_holding_a_condition_rather_than_an_id_fails(self):
        self.assert_catches("references", lambda d: d["entries"][3].update(gatedBy=[{"allMenHome": True}]))

    def test_a_map_with_no_edges_does_not_report_ok(self):
        document = valid_map()
        for item in document["entries"]:
            item["dependsOn"] = []
            item.pop("gatedBy", None)
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "references"), "skip", output)
        self.assertEqual(self.status_of(output, "no-cycles"), "skip", output)
        self.assertEqual(code, 0, output)


class TestNoCycles(MapCase):
    def test_a_depends_on_cycle_fails(self):
        def mutate(document):
            document["entries"][0]["dependsOn"] = ["speed-within-limit"]
        self.assert_catches("no-cycles", mutate)

    def test_mutual_gates_are_not_a_cycle(self):
        # gatedBy orders nothing, so a mutual gate is legitimate and must still pass.
        document = valid_map()
        document["entries"][0]["gatedBy"] = ["speed-within-limit"]
        document["entries"][1]["gatedBy"] = ["speed-limit"]
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "no-cycles"), "ok", output)
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

    def test_without_a_manifest_the_check_skips_and_fails_the_run(self):
        os.remove(self.manifest_path)
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "manifest"), "skip", output)
        self.assertIn("NOT VERIFIED", output)
        self.assertEqual(code, 1, output)


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

    def test_a_map_with_nothing_built_does_not_report_ok(self):
        # All three example maps are in this state. Reporting `ok` would be a gate
        # trusted for proving something it never looked at.
        document = valid_map()
        for item in document["entries"]:
            item.pop("implementedIn", None)
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
    def test_a_decision_fate_makes_the_unenforceable_rule_fail_the_run(self):
        # 0005 B requires conflicting entries to name the same record and records that
        # nothing links them. The check never reports ok; it reports NOT VERIFIED and
        # becomes fatal exactly when an entry could be breaking the rule.
        code, output = self.run_tool(valid_map())
        self.assertEqual(self.status_of(output, "conflicts"), "skip", output)
        self.assertEqual(code, 0, output)

        document = valid_map()
        document["entries"].append(decided_entry())
        code, output = self.run_tool(document)
        self.assertEqual(self.status_of(output, "conflicts"), "skip", output)
        self.assertIn("no field identifies", output)
        self.assertEqual(code, 1, output)

    def test_the_check_never_reports_ok(self):
        for document in (valid_map(), {**valid_map(), "entries": valid_map()["entries"] + [decided_entry()]}):
            _, output = self.run_tool(document, argv=["--only", "conflicts"])
            self.assertNotIn("[ok] conflicts", output, output)


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


if __name__ == "__main__":
    unittest.main()
