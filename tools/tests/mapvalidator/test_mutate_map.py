#!/usr/bin/env python3
"""The mutation harness, proved able to report a miss and unable to damage a committed map.

A harness that reports "detected" for everything is exactly as useless as a checker that
reports ok while examining nothing, and it is the easier of the two mistakes to make: the
scoring code sees a non-zero exit and a turned check on nearly every run. So the tests below
are mostly about the negative verdicts -- a run where nothing turned must read as a **miss**,
and a check that goes NOT VERIFIED without failing the run must read as `signalled`, which
is counted as a miss too.

The other half is the constraint #259 puts on the tool: a committed map is never mutated in
place. That is asserted against the real `examples/hoyle-backgammon/corpus-map.json` by
running a real measurement over it and comparing the bytes, because the property is about
the file on disk and a synthetic fixture cannot witness it.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import copy
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(TOOLS)
TOOL = os.path.join(TOOLS, "mutate-map.py")

_spec = importlib.util.spec_from_file_location("mutate_map", TOOL)
mutate_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mutate_map)


def entry(entry_id, page, evidence, **fields):
    record = {
        "id": entry_id,
        "name": entry_id.replace("-", " "),
        "locator": {"sourceId": "s", "citation": f"PART / {entry_id} / p. {page}"},
        "kind": "value",
        "scope": "in",
        "clarity": "clear",
        "dependsOn": [],
        "evidence": evidence,
        "status": "mapped",
        "note": "a fixture",
    }
    record.update(fields)
    return record


# A map with somewhere for every mutation to land: a gate in each direction, an ambiguity, an
# assertion, a cross-reference, a definition, two entries on one page and two on different ones.
MAP = {
    "schemaVersion": 1,
    "corpus": "s",
    "extent": {"unit": "page", "from": 1, "to": 3},
    "entries": [
        entry("player-count", 1, "A widget is played by two persons."),
        entry("token-count", 1, "Each person has three tokens of one colour."),
        entry("turn-order", 2, "The person with the higher number moves first.",
              enabledBy=["start-of-play"]),
        entry("start-of-play", 2, "Play starts when both persons have placed their tokens.",
              suspendedBy=["abandoned"]),
        entry("abandoned", 2, "A game abandoned before the first move is no game."),
        entry("token", 3, "A token means a piece of the colour a person has chosen.",
              crossReferences=[{"cites": "as provided in", "resolvedBy": "player-count"}],
              evidence_note=None),
        entry("who-decides", 3, "The umpire decides a disputed number.", kind="assertion",
              assertedBy=["umpire"]),
        entry("open-question", 3, "The number shown may be read two ways.",
              clarity="ambiguous",
              ambiguity={"question": "Which reading governs?", "fate": "unresolved",
                         "unresolvedReason": "RequiresInterpretation"}),
    ],
}
# `as provided in` is a built-in pointer phrase, so the cross-reference above is anchored in
# words the checker recognises -- which is what makes hiding it a mutation rather than an edit.
MAP["entries"][5]["evidence"] = "A token means a piece, as provided in the first rule."
MAP["entries"][5].pop("evidence_note")


def result(exit_code, checks):
    return {"exit": exit_code, "checks": checks, "output": ""}


GREEN = {"tool": result(0, {"schema": ("ok", "fine"), "gates": ("ok", "fine")})}


class ScoringReportsAMiss(unittest.TestCase):
    """The verdicts, and above all the ones that are not detections."""

    def test_nothing_turned_is_a_miss(self):
        turned, refused, unexplained = mutate_map.score(GREEN, copy.deepcopy(GREEN))
        self.assertEqual(turned, [])
        self.assertEqual(refused, [])
        self.assertEqual(unexplained, [])

    def test_a_check_that_turns_and_fails_the_run_is_a_detection(self):
        after = {"tool": result(1, {"schema": ("fail", "bad"), "gates": ("ok", "fine")})}
        turned, refused, _ = mutate_map.score(GREEN, after)
        self.assertEqual([t["check"] for t in turned], ["schema"])
        self.assertEqual(refused, ["tool"])

    def test_a_check_that_turns_without_failing_the_run_is_not_a_detection(self):
        """`asserted-by` goes NOT VERIFIED when the last assertion is turned into an operation,
        and `check-map.py` still exits 0. A map that passes is a map that ships."""
        after = {"tool": result(0, {"schema": ("ok", "fine"),
                                    "gates": ("skip", "NOT VERIFIED -- no entry carries a gate")})}
        turned, refused, _ = mutate_map.score(GREEN, after)
        self.assertEqual([t["check"] for t in turned], ["gates"])
        self.assertEqual(refused, [], "a run that stayed green has not detected anything")

    def test_a_check_already_red_on_the_control_proves_nothing(self):
        control = {"tool": result(1, {"schema": ("fail", "bad")})}
        after = {"tool": result(1, {"schema": ("fail", "bad")})}
        turned, _, _ = mutate_map.score(control, after)
        self.assertEqual(turned, [])

    def test_a_non_zero_exit_no_named_check_explains_is_reported(self):
        after = {"tool": result(1, {"schema": ("ok", "fine"), "gates": ("ok", "fine")})}
        _, refused, unexplained = mutate_map.score(GREEN, after)
        self.assertEqual(refused, ["tool"])
        self.assertEqual(unexplained, ["tool"],
                         "a refusal no check accounts for is a verdict this tool did not read")


class ReadingTheSectionChecker(unittest.TestCase):
    """check-locators-section.py prints findings rather than verdicts, so they are read out."""

    def test_a_citation_finding_and_a_coverage_finding_are_told_apart(self):
        verdicts = mutate_map.parse_section(
            "  X  speed-limit: cited § 107.51(a), evidence also sits in 107.51/b\n"
            "  X  § 107.29: inside the declared extent and reached by no entry\n")
        self.assertEqual(verdicts["locators"][0], "fail")
        self.assertEqual(verdicts["coverage"][0], "fail")

    def test_a_clean_run_is_two_passes(self):
        verdicts = mutate_map.parse_section("locators ok (all 47 checked); coverage ok\n")
        self.assertEqual(verdicts["locators"][0], "ok")
        self.assertEqual(verdicts["coverage"][0], "ok")

    def test_an_entry_it_could_not_check_is_not_a_pass(self):
        verdicts = mutate_map.parse_section("  ?  fog: evidence is not a quote\n")
        self.assertEqual(verdicts["locators"][0], "skip")


class TheAdjudicationRecordIsStaged(unittest.TestCase):
    """The map under test is written into a temporary directory, so a check that reads a file
    beside the committed map finds nothing unless it is told where to look (0034).

    A detector the harness never ran would be recorded as a detector that noticed nothing, which
    is this tool's worst failure mode and the reason `superposition` is named a comparison
    directory on every run of a subject that was mapped twice.
    """

    def test_a_subject_mapped_twice_names_its_record(self):
        home = mutate_map.comparison_record(
            os.path.join(ROOT, "examples", "hoyle-backgammon"))
        self.assertEqual(home, os.path.join(ROOT, "examples", "hoyle-backgammon", "blind-mapping"))

    def test_a_subject_never_mapped_twice_names_none(self):
        self.assertIsNone(mutate_map.comparison_record(
            os.path.join(ROOT, "examples", "faa-part-107-temporal")))

    def test_superposition_has_subject_matter_where_the_harness_puts_the_map(self):
        # The proof that the wiring works, taken where it matters: the map copied into a
        # temporary directory, as every run of this tool copies it. Without the record's home on
        # the command line the check says NOT VERIFIED here and says it on every mutation too.
        subject = next(s for s in mutate_map.SUBJECTS if s["name"] == "hoyle-backgammon")
        workspace = tempfile.mkdtemp(prefix="mutate-map-test-")
        try:
            copied = os.path.join(workspace, "corpus-map.json")
            shutil.copy(os.path.join(ROOT, subject["dir"], "corpus-map.json"), copied)
            control = mutate_map.detectors(subject, copied, ROOT)
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
        status, said = control["check-map.py"]["checks"]["superposition"]
        self.assertEqual(status, "ok", said)


class EveryMutationDamagesOrSaysWhy(unittest.TestCase):
    """A patch that silently did nothing would be scored as an undetected error."""

    def test_no_mutation_is_a_silent_no_op(self):
        for mutation in mutate_map.MUTATIONS:
            with self.subTest(mutation=mutation["name"]):
                document = copy.deepcopy(MAP)
                try:
                    if mutation["apply"] is mutate_map.m_omit_definition:
                        what = mutation["apply"](document, None)
                    else:
                        what = mutation["apply"](document)
                except mutate_map.NotApplicable:
                    continue
                self.assertNotEqual(document, MAP,
                                    f"{mutation['name']} reported {what!r} and changed nothing")

    def test_a_mutation_with_no_target_raises_rather_than_passing(self):
        bare = {"schemaVersion": 1, "extent": {"unit": "page", "from": 1, "to": 2},
                "entries": [entry("only", 1, "One rule.")]}
        with self.assertRaises(mutate_map.NotApplicable):
            mutate_map.m_drop_enabled_by(copy.deepcopy(bare))
        with self.assertRaises(mutate_map.NotApplicable):
            mutate_map.m_hide_cross_reference(copy.deepcopy(bare))

    def test_an_omission_takes_its_inbound_edges_with_it(self):
        document = copy.deepcopy(MAP)
        mutate_map.m_remove_applicability(document)
        ids = {e["id"] for e in document["entries"]}
        for record in document["entries"]:
            for field in mutate_map.CITING_LIST_FIELDS:
                for target in record.get(field) or []:
                    self.assertIn(target, ids, "a dangling edge would be caught for the wrong reason")

    def test_the_evidence_swap_leaves_the_locator_alone(self):
        document = copy.deepcopy(MAP)
        mutate_map.m_neighbour_evidence(document)
        before = {e["id"]: e["locator"]["citation"] for e in MAP["entries"]}
        after = {e["id"]: e["locator"]["citation"] for e in document["entries"]}
        self.assertEqual(before, after)
        self.assertNotEqual([e["evidence"] for e in MAP["entries"]],
                            [e["evidence"] for e in document["entries"]])


class TheCommittedMeasurement(unittest.TestCase):
    """What the gate runs, and the constraint the whole tool is written under."""

    def test_a_row_that_moved_is_reported(self):
        committed = {"subjects": [{"name": "m", "runs": [
            {"mutation": "drop-entry", "applicable": True, "detected": False, "signalled": False,
             "by": []}]}]}
        fresh = copy.deepcopy(committed)
        fresh["subjects"][0]["runs"][0]["detected"] = True
        differences = mutate_map.compare(committed, fresh)
        self.assertEqual(len(differences), 1)
        self.assertIn("drop-entry", differences[0])

    def test_the_same_measurement_twice_is_no_difference(self):
        committed = {"subjects": [{"name": "m", "runs": [
            {"mutation": "drop-entry", "applicable": True, "detected": False, "signalled": False,
             "by": []}]}]}
        self.assertEqual(mutate_map.compare(committed, copy.deepcopy(committed)), [])

    def test_a_measurement_run_does_not_touch_the_committed_map(self):
        subject = next(s for s in mutate_map.SUBJECTS if s["name"] == "hoyle-backgammon")
        path = os.path.join(ROOT, subject["dir"], "corpus-map.json")
        with open(path, "rb") as handle:
            before = handle.read()
        with redirect_stdout(io.StringIO()):
            runs, problems = mutate_map.measure(subject, ROOT, only={"drop-entry", "move-locator"})
        with open(path, "rb") as handle:
            self.assertEqual(before, handle.read(), "a committed map was mutated in place")
        self.assertEqual(problems, [])
        self.assertTrue(any(r["applicable"] for r in runs))

    def test_the_committed_table_names_every_mutation_for_every_subject(self):
        with open(os.path.join(ROOT, "examples", "validator-attack", "results.json"),
                  encoding="utf-8") as handle:
            measurement = json.load(handle)
        self.assertEqual([s["name"] for s in measurement["subjects"]],
                         [s["name"] for s in mutate_map.SUBJECTS])
        for subject in measurement["subjects"]:
            self.assertEqual(sorted(r["mutation"] for r in subject["runs"]),
                             sorted(m["name"] for m in mutate_map.MUTATIONS),
                             f"{subject['name']} has a mutation the catalogue does not")


class EveryInjectionNamesTheRefusalItExpects(unittest.TestCase):
    """#362, 0061: an injection declared what it damaged and not which rule should object, so a
    mutation refused by a different rule counted as caught. A catch rate can be right about the
    number and wrong about which rules are load-bearing, and a rule that never catches anything
    on its own is invisible in it."""

    def test_every_mutation_declares_one(self):
        """`None` is a declaration too -- no rule is written to catch this -- and the difference
        between declaring it and forgetting the field is the whole of the check."""
        for mutation in mutate_map.MUTATIONS:
            with self.subTest(mutation=mutation["name"]):
                self.assertIn("expect", mutation,
                              f"{mutation['name']} names no expected refusal (#362)")
                expect = mutation["expect"]
                self.assertTrue(expect is None or isinstance(expect, (str, tuple)),
                                f"{mutation['name']}: expect is {expect!r}")
                if isinstance(expect, tuple):
                    self.assertGreater(len(expect), 1, "a family of one is a string")

    def test_the_four_that_measure_a_gap_are_the_four_named(self):
        """Named, so a mutation that quietly loses its rule fails here rather than being counted
        as measuring a gap it was never written to measure."""
        self.assertEqual(sorted(m["name"] for m in mutate_map.MUTATIONS if m["expect"] is None),
                         ["drop-enabled-by", "drop-suspended-by", "invent-depends-on",
                          "omit-definition", "same-passage-evidence"])

    def test_the_expected_rule_must_be_one_the_validator_can_report(self):
        """An `expect` naming a rule nothing emits would never match, so every catch would read
        as a neighbour's and the measurement would say the opposite of the truth.

        The vocabulary is the validator's own -- every rule check-map.py names on a real map,
        plus every rule a measured run has seen the locator checkers report -- and not the set
        that happens to have fired. A rule written to catch an error it has never yet caught is
        exactly what 0061 wants visible, so requiring `expect` to have fired would demand the
        opposite of the decision.
        """
        emitted = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "check-map.py"),
             os.path.join(ROOT, "examples", "hoyle-backgammon", "corpus-map.json"),
             "--manifest", os.path.join(ROOT, "examples", "hoyle-backgammon", "corpus-manifest.json"),
             "--repo-root", ROOT],
            capture_output=True, text=True, cwd=ROOT)
        known = set(re.findall(r"^\[[a-z-]+\] ([a-z][a-z-]+):", emitted.stdout, re.M))
        self.assertTrue(known, f"check-map.py named no rule; the vocabulary is unknown\n{emitted.stdout[:500]}")
        known |= {rule for subject in json.load(
            open(os.path.join(ROOT, "examples", "validator-attack", "results.json"),
                 encoding="utf-8"))["subjects"]
            for run_of in subject["runs"] for rule in
            {x["check"] for x in (run_of.get("by") or [])}}
        for mutation in mutate_map.MUTATIONS:
            expect = mutation["expect"]
            if expect is None:
                continue
            for rule in ((expect,) if isinstance(expect, str) else expect):
                with self.subTest(mutation=mutation["name"], rule=rule):
                    self.assertIn(rule, known,
                                  f"{mutation['name']} expects {rule!r}, which no measured run "
                                  f"has ever reported; it could never count as an intended catch")


class ACatchByAnotherRuleIsADifferentOutcome(unittest.TestCase):
    """The committed measurement, read for what the headline cannot say."""

    def setUp(self):
        with open(os.path.join(ROOT, "examples", "validator-attack", "results.json"),
                  encoding="utf-8") as handle:
            self.measured = json.load(handle)

    def runs(self):
        return [r for s in self.measured["subjects"] for r in s["runs"] if r.get("applicable")]

    def test_the_totals_separate_the_two(self):
        totals = self.measured["totals"]
        for key in ("byIntendedRule", "byNeighbourOnly"):
            self.assertIn(key, totals, f"the measurement does not report {key} (#362)")
        self.assertEqual(totals["detected"], totals["byIntendedRule"] + totals["byNeighbourOnly"],
                         "every catch is by the intended rule or by another; there is no third")

    def test_a_neighbour_catch_is_recorded_as_one_and_not_as_a_catch_of_its_own(self):
        neighbours = [r for r in self.runs() if r.get("byNeighbourOnly")]
        self.assertTrue(neighbours, "no neighbour catch is recorded, so this proves nothing about "
                                    "a harness that can tell them apart")
        for run_of in neighbours:
            with self.subTest(mutation=run_of["mutation"]):
                self.assertTrue(run_of["detected"], "a neighbour catch is still a catch of something")
                self.assertFalse(run_of["byIntendedRule"])

    def test_a_mutation_with_no_rule_can_only_ever_be_caught_by_a_neighbour(self):
        """0061's sharpest case: `same-passage-evidence` leaves the quote inside the passage the
        entry cites, so nothing structural can see it. Its one refusal is another rule's."""
        without = {m["name"] for m in mutate_map.MUTATIONS if m["expect"] is None}
        for run_of in self.runs():
            if run_of["mutation"] in without and run_of["detected"]:
                with self.subTest(mutation=run_of["mutation"]):
                    self.assertFalse(run_of["byIntendedRule"],
                                     f"{run_of['mutation']} has no intended rule and is recorded "
                                     f"as caught by one")
                    self.assertTrue(run_of["byNeighbourOnly"])

    def test_the_gate_holds_the_committed_record_to_it(self):
        """A mutation that stops being caught by its own rule, and starts being caught only by a
        neighbour, is a row nobody chose to move."""
        committed = {"subjects": [{"name": "m", "runs": [
            {"mutation": "remove-applicability", "applicable": True, "detected": True,
             "signalled": False, "byIntendedRule": True, "by": []}]}]}
        fresh = copy.deepcopy(committed)
        fresh["subjects"][0]["runs"][0]["byIntendedRule"] = False
        differences = mutate_map.compare(committed, fresh)
        self.assertEqual(len(differences), 1, differences)
        self.assertIn("remove-applicability", differences[0])

    def test_the_table_says_neighbour_only(self):
        rendered = mutate_map.table(self.measured)
        self.assertIn("neighbour only:", rendered,
                      "the table reports a neighbour catch as though the intended rule fired")


if __name__ == "__main__":
    unittest.main()
