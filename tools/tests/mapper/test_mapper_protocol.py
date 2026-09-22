#!/usr/bin/env python3
"""The mapping protocol is a checked document, and its detector finds what a phrase list cannot.

A protocol says how one corpus communicates rules. A declaration nothing holds to a vocabulary
is a comment, and a declared interrogation nobody performs is worse than none -- it reads as
coverage. So every closed set is watched refusing a value outside it, and the detector is
watched on the corpus #208 measured: `defined-term-use` finds namings where the phrase list
finds zero, and does not make a definition point at itself.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import copy
import glob
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

sys.path.insert(0, TOOLS)
try:
    from mapper import cli, pointers, protocol
finally:
    sys.path.remove(TOOLS)

CONDITIONS = os.path.join(REPO, "examples", "srd-52-conditions", "corpus-map.json")


def read(path):
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def maps():
    found = sorted(glob.glob(os.path.join(REPO, "examples", "*", "corpus-map*.json")))
    found += sorted(glob.glob(os.path.join(REPO, "examples", "*", "*", "corpus-map*.json")))
    return found


class TestEveryMapHasOne(unittest.TestCase):
    def test_every_map_is_governed_by_a_protocol_the_mapper_can_act_on(self):
        paths = maps()
        self.assertTrue(paths, "no example maps -- this test proved nothing")
        for path in paths:
            with self.subTest(map=os.path.relpath(path, REPO)):
                code, out, err = run(["protocol", path])
                self.assertEqual(code, 0, out + err)

    def test_a_map_with_no_protocol_beside_it_is_refused(self):
        code, _, err = run(["protocol", os.path.join(REPO, "README.md")])
        self.assertEqual(code, 2)
        self.assertIn("cannot read map", err)


class ProtocolCase(unittest.TestCase):
    """The conditions protocol, mutated one way per test."""

    def setUp(self):
        self.document = read(CONDITIONS)
        self.protocol = read(os.path.join(os.path.dirname(CONDITIONS),
                                          protocol.PROTOCOL_FILENAME))
        self.manifest = read(os.path.join(os.path.dirname(CONDITIONS), "corpus-manifest.json"))

    def problems(self):
        return protocol.check(self.protocol, self.document, self.manifest)

    def assert_clean(self):
        self.assertEqual(self.problems(), [])

    def assert_refused(self, fragment):
        found = self.problems()
        self.assertTrue(found, f"nothing refused; expected {fragment!r}")
        self.assertTrue(any(fragment in line for line in found), found)


class TestTheClosedSets(ProtocolCase):
    def test_the_committed_protocol_is_clean(self):
        self.assert_clean()

    def test_an_unknown_version(self):
        self.protocol["protocolVersion"] = 2
        self.assert_refused("is not one this mapper reads")

    def test_a_missing_field(self):
        del self.protocol["adapterReach"]
        self.assert_refused("`adapterReach` is missing")

    def test_a_field_that_is_not_one(self):
        self.protocol["mappedBy"] = "someone"
        self.assert_refused("`mappedBy` is not a protocol field")

    def test_a_corpus_the_manifest_does_not_declare(self):
        self.protocol["corpus"] = "srd-5.2.2"
        self.assert_refused("is not a sourceId the manifest declares")

    def test_a_unit_outside_the_set(self):
        self.protocol["units"] = ["stanza"]
        self.assert_refused("unit 'stanza' is outside the closed set")

    def test_no_units_at_all(self):
        self.protocol["units"] = []
        self.assert_refused("says nothing about how the corpus is read")

    def test_a_sweep_outside_the_set(self):
        self.protocol["requiredSweeps"] = ["vibes"]
        self.assert_refused("sweep 'vibes' is outside the closed set")

    def test_no_sweeps_at_all(self):
        self.protocol["requiredSweeps"] = []
        self.assert_refused("owes no completeness challenge")

    def test_a_modality_outside_the_set(self):
        self.protocol["adapterReach"] = {"smell": "readable"}
        self.assert_refused("modality 'smell' is outside the closed set")

    def test_a_reach_outside_the_set(self):
        self.protocol["adapterReach"] = {"tables": "probably fine"}
        self.assert_refused("outside: readable, rendered-page-required, unsupported")

    def test_a_mechanism_outside_the_set(self):
        self.protocol["pointerMechanisms"] = [{"mechanism": "vibes"}]
        self.assert_refused("mechanism 'vibes' is outside the closed set")

    def test_no_mechanism_at_all(self):
        self.protocol["pointerMechanisms"] = []
        self.assert_refused("0026 already refuses a silent zero")


class TestTheVocabularyMustExist(ProtocolCase):
    def mechanism(self, **changes):
        declared = {"mechanism": "defined-term-use", "vocabularyFrom": "condition-list"}
        declared.update(changes)
        self.protocol["pointerMechanisms"] = [declared]

    def test_defined_term_use_without_a_vocabulary(self):
        self.mechanism(vocabularyFrom=None)
        self.assert_refused("a mechanism that points by naming a term must say which terms")

    def test_a_vocabulary_entry_that_is_not_in_the_map(self):
        self.mechanism(vocabularyFrom="the-fifteen-conditions")
        self.assert_refused("is not an entry in this map")

    def test_an_entry_that_states_no_vocabulary(self):
        self.mechanism(vocabularyFrom="paralyzed")
        self.assert_refused("states no vocabulary")

    def test_a_term_that_resolves_to_nothing(self):
        for entry in self.document["entries"]:
            if entry["id"] == "condition-list":
                entry["crossReferences"][0] = {"cites": "Blinded", "resolvedBy": "blinded-oops"}
        self.mechanism()
        self.assert_refused("which is not an entry")

    def test_a_vocabulary_on_a_mechanism_that_reads_none(self):
        self.protocol["pointerMechanisms"] = [{"mechanism": "phrase",
                                               "vocabularyFrom": "condition-list"}]
        self.assert_refused("which is defined-term-use's vocabulary; 'phrase' does not read one")

    def test_coded_pointer_may_not_name_a_single_vocabulary_entry(self):
        """0045: its vocabulary is distributed, and `vocabularyFrom` names one entry."""
        self.protocol["pointerMechanisms"] = [{"mechanism": "coded-pointer", "column": 7,
                                               "vocabularyFrom": "condition-list"}]
        self.assert_refused("coded-pointer's vocabulary is distributed over the entries")

    def test_defined_term_use_may_not_name_a_vocabulary_two_ways(self):
        """Trial 11 gave this mechanism 0045's distributed form as well, and one or the other.

        The SRD prints a Rules Glossary, so `vocabularyFrom` names the entry that lists its terms;
        the Federal Rules of Civil Procedure print no index, so the vocabulary is what the
        entries defining each term add up to. Naming both is two vocabularies for one mechanism,
        and nothing says which the detector reads.
        """
        self.protocol["pointerMechanisms"] = [{"mechanism": "defined-term-use",
                                               "vocabularyFrom": "condition-list",
                                               "vocabulary": "condition-names"}]
        self.assert_refused("names both `vocabularyFrom` and `vocabulary`")

    def test_a_named_vocabulary_on_a_mechanism_that_reads_none(self):
        self.protocol["pointerMechanisms"] = [{"mechanism": "phrase",
                                               "vocabulary": "condition-names"}]
        self.assert_refused("'phrase' reads no such vocabulary")

    def test_defined_term_use_over_a_vocabulary_no_entry_defines(self):
        """The distributed form is held to 0045's own check, which is the one `coded-pointer`
        already gets: a name no entry defines is refused rather than read as an empty vocabulary.
        """
        self.mechanism(vocabularyFrom=None, vocabulary="nothing-defines-this")
        self.assert_refused("no entry in this map establishes vocabulary")


class TestTheDetector(unittest.TestCase):
    """#208's measurement, the other way round."""

    def setUp(self):
        self.document = read(CONDITIONS)
        self.index = {e["id"]: e for e in self.document["entries"]}

    def namings(self, document=None):
        document = document or self.document
        vocabulary = {e["id"]: e for e in document["entries"]}["condition-list"]
        return pointers.detect(document, vocabulary)

    def test_it_finds_what_the_phrase_list_cannot(self):
        found = self.namings()
        self.assertGreater(sum(n.count for n in found), 40,
                           "the detector found almost nothing on the corpus #208 measured")
        self.assertGreater(len({n.entry_id for n in found}), 15)

    def test_a_definition_never_points_at_itself(self):
        """`incapacitated` and every entry inside its passage name Incapacitated; none is a
        pointer, and a detector that made one would make every definition self-referential."""
        inside = [e["id"] for e in self.document["entries"]
                  if e["id"].startswith("incapacitated")]
        self.assertGreater(len(inside), 3)
        named = {n.entry_id for n in self.namings() if n.term == "Incapacitated"}
        self.assertFalse(named & set(inside), named & set(inside))

    def test_a_naming_outside_the_passage_is_a_pointer(self):
        found = {(n.entry_id, n.term) for n in self.namings()}
        self.assertIn(("paralyzed-incapacitated", "Incapacitated"), found)
        self.assertIn(("stunned-incapacitated", "Incapacitated"), found)

    def test_the_committed_map_leaves_no_naming_undeclared(self):
        """0058 corrected the three #254 found, and this is what holds the map to it.

        The gate now accepts only 0 on this map, so a naming that lost its declaration is a
        failure rather than a NOT VERIFIED. Watched failing by removing `suffocation-hazard`'s
        item: the set comes back as {"suffocation-hazard"}.
        """
        undeclared = {n.entry_id for n in self.namings() if not n.declared}
        self.assertEqual(undeclared, set(),
                         "a naming lost its declaration; the gate accepts only 0 here (0058)")

    def test_it_still_reports_a_naming_a_map_does_not_declare(self):
        """The detector's own behaviour, on a map mutated to have the defect.

        Pinned to the committed map's three undeclared namings until 0058 corrected them, which
        made this test a hostage to a defect: fixing the map broke the test that proved the
        detector worked. The mutation carries it instead, so the detector is watched reporting
        with no map obliged to stay wrong.
        """
        document = copy.deepcopy(self.document)
        for entry in document["entries"]:
            if entry["id"] == "suffocation-hazard":
                entry.pop("crossReferences", None)
        undeclared = {n.entry_id for n in self.namings(document) if not n.declared}
        self.assertEqual(undeclared, {"suffocation-hazard"})
        missing = [n.missing for n in self.namings(document)
                   if n.entry_id == "suffocation-hazard" and n.term == "Exhaustion"]
        self.assertEqual(missing, [["exhaustion"]], "it names the entry the pointer is owed to")

    def test_a_term_is_matched_on_word_boundaries(self):
        document = copy.deepcopy(self.document)
        for entry in document["entries"]:
            if entry["id"] == "paralyzed-incapacitated":
                entry["evidence"] = "You are Incapacitatedly unbothered."
        named = [n for n in self.namings(document)
                 if n.entry_id == "paralyzed-incapacitated" and n.term == "Incapacitated"]
        self.assertEqual(named, [], "a term inside a longer word is not a naming of it")


class TestTheCommandsExitCodes(unittest.TestCase):
    def pointer_case(self, mechanisms, *, coded=True, defined=True, declare_defined_use=True):
        """Run `mapper pointers` on a mechanism-neutral synthetic map.

        The two pointer kinds coexist in one map so these tests exercise command dispatch rather
        than either detector's corpus-specific details.
        """
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        entries = [
            {"id": "code-a", "locator": {"sourceId": "example", "citation": "section 1"},
             "evidence": "A defines one code.",
             "defines": [{"vocabulary": "codes", "term": "A"}]},
            {"id": "blue", "locator": {"sourceId": "example", "citation": "section 2"},
             "evidence": "Blue defines one term."},
            {"id": "terms", "locator": {"sourceId": "example", "citation": "section 3"},
             "evidence": "The terms include Blue.",
             "crossReferences": [{"cites": "Blue", "resolvedBy": "blue"}]},
        ]
        if coded:
            entries.append({
                "id": "coded-use",
                "locator": {"sourceId": "example",
                            "citation": 'table 1, row [column 1 = "thing"], column 7'},
                "evidence": "A",
                "crossReferences": [{"cites": "A", "resolvedBy": "code-a"}],
            })
        if defined:
            entries.append({
                "id": "defined-use",
                "locator": {"sourceId": "example", "citation": "section 4"},
                "evidence": "Blue applies.",
            })
            if declare_defined_use:
                entries[-1]["crossReferences"] = [{"cites": "Blue", "resolvedBy": "blue"}]
        document = {"schemaVersion": 1, "corpus": "example", "entries": entries}
        declared = {"protocolVersion": 1, "corpus": "example",
                    "units": ["paragraph"], "pointerMechanisms": mechanisms,
                    "requiredSweeps": ["cross-references"],
                    "adapterReach": {"text": "readable"}}
        map_path = os.path.join(tmp, "corpus-map.json")
        protocol_path = os.path.join(tmp, protocol.PROTOCOL_FILENAME)
        with io.open(map_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle)
        with io.open(protocol_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(declared, handle)
        return run(["pointers", map_path])

    def test_a_protocol_declaring_only_coded_pointer_runs_its_detector(self):
        mechanism = {"mechanism": "coded-pointer", "column": 7, "vocabulary": "codes"}
        code, out, err = self.pointer_case([mechanism])
        self.assertEqual(code, 0, out + err)
        self.assertIn("column 7: 1 code(s)", out)

    def test_a_protocol_declaring_only_defined_term_use_runs_its_detector(self):
        mechanism = {"mechanism": "defined-term-use", "vocabularyFrom": "terms"}
        code, out, err = self.pointer_case([mechanism])
        self.assertEqual(code, 0, out + err)
        self.assertIn("term(s) declared by 'terms'", out)

    def test_a_protocol_declaring_both_runs_both_detectors(self):
        mechanisms = [
            {"mechanism": "coded-pointer", "column": 7, "vocabulary": "codes"},
            {"mechanism": "defined-term-use", "vocabularyFrom": "terms"},
        ]
        code, out, err = self.pointer_case(mechanisms)
        self.assertEqual(code, 0, out + err)
        self.assertIn("column 7: 1 code(s)", out)
        self.assertIn("term(s) declared by 'terms'", out)

    def test_a_protocol_declaring_no_locally_detected_mechanism_says_so(self):
        code, out, err = self.pointer_case([{"mechanism": "phrase"}])
        self.assertEqual(code, 0, out + err)
        self.assertIn("declares no mechanism detected by `mapper pointers`", out)
        self.assertIn("phrase:", out)

    def test_a_pointer_mechanism_no_detector_owns_is_refused(self):
        code, _, err = self.pointer_case([{"mechanism": "vibes"}])
        self.assertEqual(code, 2)
        self.assertIn("no detector owns", err)

    def test_a_coded_pointer_silent_zero_fails(self):
        mechanism = {"mechanism": "coded-pointer", "column": 7, "vocabulary": "codes"}
        code, _, err = self.pointer_case([mechanism], coded=False)
        self.assertEqual(code, 1)
        self.assertIn("A silent zero is not a pass", err)

    def test_a_map_naming_an_undeclared_term_is_not_verified(self):
        """Exit 3 on a map with the defect, built for the purpose.

        This ran against `examples/srd-52-conditions/` while that map had three undeclared
        namings. 0058 corrected them and the map exits 0, so the case moved to a synthetic map:
        an exit code is the detector's behaviour and must not depend on a committed map keeping
        a defect. Watched failing by declaring `Blue` on `defined-use`, which returns 0.
        """
        mechanism = {"mechanism": "defined-term-use", "vocabularyFrom": "terms"}
        code, out, _ = self.pointer_case([mechanism], coded=False, declare_defined_use=False)
        self.assertEqual(code, 3, out)
        self.assertIn("NOT VERIFIED", out)
        self.assertIn("defined-use", out)

    def test_the_committed_map_exits_0(self):
        """The other half: the corpus #208 measured now has every naming declared (0058)."""
        code, out, _ = run(["pointers", CONDITIONS])
        self.assertEqual(code, 0, out)
        self.assertIn("54 naming(s), every one declared", out)

    def test_a_corpus_that_points_no_way_this_detects_says_so(self):
        backgammon = os.path.join(REPO, "examples", "hoyle-backgammon", "corpus-map.json")
        code, out, _ = run(["pointers", backgammon])
        self.assertEqual(code, 0, out)
        self.assertIn("declares no mechanism detected by `mapper pointers`", out)
        self.assertIn("phrase:", out)

    def test_a_silent_zero_fails(self):
        """The shape #208 measured: the mechanism is declared and nothing fires."""
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        document = read(CONDITIONS)
        for entry in document["entries"]:
            entry["evidence"] = "Nothing here names anything."
        map_path = os.path.join(tmp, "corpus-map.json")
        with io.open(map_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle)
        shutil.copy(os.path.join(os.path.dirname(CONDITIONS), protocol.PROTOCOL_FILENAME),
                    os.path.join(tmp, protocol.PROTOCOL_FILENAME))
        code, _, err = run(["pointers", map_path])
        self.assertEqual(code, 1)
        self.assertIn("A silent zero is not a pass", err)


if __name__ == "__main__":
    unittest.main()
