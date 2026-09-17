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
        self.assert_refused("must say which entry states the terms")

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
        self.assert_refused("`vocabularyFrom` belongs to defined-term-use")


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

    def test_it_reports_which_namings_the_map_does_not_declare(self):
        undeclared = {n.entry_id for n in self.namings() if not n.declared}
        self.assertEqual(undeclared, {"suffocation-hazard", "dead-revival-conditions",
                                      "grappling-ends"},
                         "the three of #254; a change here is a map change or a detector change")

    def test_a_term_is_matched_on_word_boundaries(self):
        document = copy.deepcopy(self.document)
        for entry in document["entries"]:
            if entry["id"] == "paralyzed-incapacitated":
                entry["evidence"] = "You are Incapacitatedly unbothered."
        named = [n for n in self.namings(document)
                 if n.entry_id == "paralyzed-incapacitated" and n.term == "Incapacitated"]
        self.assertEqual(named, [], "a term inside a longer word is not a naming of it")


class TestTheCommandsExitCodes(unittest.TestCase):
    def test_a_map_naming_an_undeclared_term_is_not_verified(self):
        code, out, _ = run(["pointers", CONDITIONS])
        self.assertEqual(code, 3, out)
        self.assertIn("NOT VERIFIED", out)

    def test_a_corpus_that_points_no_way_this_detects_says_so(self):
        backgammon = os.path.join(REPO, "examples", "hoyle-backgammon", "corpus-map.json")
        code, out, _ = run(["pointers", backgammon])
        self.assertEqual(code, 0, out)
        self.assertIn("declares no defined-term-use", out)
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
