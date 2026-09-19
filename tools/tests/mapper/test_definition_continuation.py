#!/usr/bin/env python3
"""A passage can continue one direct definition without repeating its term (0046, #321).

The first two tests were committed red at e9557dce before production code. On main,
`defined_vocabulary` read only direct `defines`, so the additional IB2 rule never joined the
vocabulary and deleting its `resolvedBy` edge was clean.

0046 keeps 0045 intact instead of making a locator into evidence. A continuation names one entry
that directly defines one term and carries a structural locator witness. The map validator holds
the relation's shape and target; the section locator checker proves that the witness resolves to
this passage under the target's row.
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
import io

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(TOOLS)
TRIAL = os.path.join(ROOT, "examples", "hazmat-172-table")
sys.path.insert(0, TOOLS)
try:
    from mapcontract.entry import defined_vocabulary
    from mapvalidator.definition_continuations import check_definition_continuations
    from mapper import pointers
finally:
    sys.path.remove(TOOLS)

_spec = importlib.util.spec_from_file_location(
    "check_locators_for_definition_continuation",
    os.path.join(ROOT, "examples", "faa-part-107", "check-locators-section.py"))
check_locators = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_locators)

_map_spec = importlib.util.spec_from_file_location("check_map_for_definition_continuation",
                                                   os.path.join(TOOLS, "check-map.py"))
check_map = importlib.util.module_from_spec(_map_spec)
_map_spec.loader.exec_module(check_map)

CODES = "special-provision-codes"
OTHER = "other-codes"
PROVISIONS = "cfr-49-172.102"
TABLE = "cfr-49-172.101"
DIRECT = "ib2-authorized-ibcs"
CONTINUATION = "ib2-vapour-pressure-limit"
IB2 = '§ 172.102 table 2, row [column 1 = "IB2"]'
IB2_BELOW = '§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]'
IB3 = '§ 172.102 table 2, row [column 1 = "IB3"]'
IB3_BELOW = '§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB3"]'


def rule(entry_id, citation, evidence, **extra):
    value = {
        "id": entry_id,
        "name": entry_id,
        "locator": {"sourceId": PROVISIONS, "citation": citation},
        "kind": "value",
        "scope": "in",
        "clarity": "clear",
        "evidence": evidence,
        "status": "mapped",
    }
    value.update(extra)
    return value


def continuation(entry_id=CONTINUATION, target=DIRECT, citation=IB2_BELOW,
                 anchor=IB2_BELOW, source=PROVISIONS):
    return rule(
        entry_id, citation,
        "| Additional Requirement: Only liquids with a vapor pressure of 110 kPa are authorized.",
        continuesDefinition={
            "definedBy": target,
            "anchor": {"sourceId": source, "citation": anchor},
        })


def pointer(*targets):
    return {
        "id": "acetal-special-provisions",
        "name": "acetal special provisions",
        "locator": {
            "sourceId": TABLE,
            "citation": '§ 172.101 table 3, row [column 2 = "Acetal"], column 7',
        },
        "kind": "value",
        "scope": "in",
        "clarity": "clear",
        "evidence": "IB2",
        "status": "mapped",
        "crossReferences": [{"cites": "IB2", "resolvedBy": target} for target in targets],
    }


def document(*, pointer_targets=(DIRECT, CONTINUATION)):
    return {
        "entries": [
            rule(DIRECT, IB2, "IB2 | Authorized IBCs: Metal (31A).",
                 defines=[{"vocabulary": CODES, "term": "IB2"}]),
            continuation(),
            pointer(*pointer_targets),
        ]
    }


def table_of(rows):
    element = ET.Element("TABLE")
    head = ET.SubElement(ET.SubElement(element, "THEAD"), "TR")
    ET.SubElement(head, "TH").text = "(1) Code"
    ET.SubElement(head, "TH").text = "(2) Requirement"
    body = ET.SubElement(element, "TBODY")
    for cells in rows:
        row = ET.SubElement(body, "TR")
        for text in cells:
            ET.SubElement(row, "TD").text = text
    return check_locators.Table("172.102", 2, element)


class TheWatchedFailureNowTurns(unittest.TestCase):
    """The exact #321 mutation: the second edge is now owed by the vocabulary."""

    def test_the_additional_rule_joins_the_defining_set(self):
        self.assertEqual(defined_vocabulary(document(), CODES)["IB2"],
                         [DIRECT, CONTINUATION])

    def test_removing_the_second_resolved_by_is_not_clean(self):
        naming = pointers.detect_coded(
            document(pointer_targets=(DIRECT,)),
            {"mechanism": "coded-pointer", "column": 7, "vocabulary": CODES})[0]
        self.assertEqual(naming.missing, [CONTINUATION])
        lines, _, findings = pointers.report(
            {"pointerMechanisms": [
                {"mechanism": "coded-pointer", "column": 7, "vocabulary": CODES}]},
            document(pointer_targets=(DIRECT,)))
        self.assertTrue(any(CONTINUATION in line for line in lines), lines)
        self.assertEqual([finding.term for finding in findings], ["IB2"])

    def test_resolving_both_is_complete(self):
        naming = pointers.detect_coded(
            document(),
            {"mechanism": "coded-pointer", "column": 7, "vocabulary": CODES})[0]
        self.assertEqual(naming.missing, [])


class TheSemanticRelationIsNarrow(unittest.TestCase):
    def result(self, doc):
        return check_definition_continuations({"map": doc})

    def test_one_direct_target_and_same_corpus_pass(self):
        result = self.result(document())
        self.assertEqual(result.status, "ok", result.details)

    def test_unknown_relation_metadata_is_refused(self):
        doc = document()
        doc["entries"][1]["continuesDefinition"]["term"] = "IB2"
        result = self.result(doc)
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("unknown key" in line for line in result.details), result.details)

    def test_unknown_anchor_metadata_is_refused(self):
        doc = document()
        doc["entries"][1]["continuesDefinition"]["anchor"]["row"] = "IB2"
        result = self.result(doc)
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("anchor holds" in line for line in result.details), result.details)

    def test_an_unrelated_corpus_is_refused(self):
        doc = document()
        doc["entries"][1]["continuesDefinition"]["anchor"]["sourceId"] = "other-corpus"
        result = self.result(doc)
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("anchor names corpus" in line for line in result.details), result.details)

    def test_a_continuation_does_not_also_directly_define(self):
        doc = document()
        doc["entries"][1]["defines"] = [{"vocabulary": CODES, "term": "IB2"}]
        result = self.result(doc)
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("both `defines` and `continuesDefinition`" in line
                            for line in result.details), result.details)

    def test_a_semantic_continuation_cannot_leave_its_relationship_unresolved(self):
        doc = document()
        doc["entries"][1]["clarity"] = "ambiguous"
        doc["entries"][1]["ambiguity"] = {
            "question": "Does this blank-code row continue IB2?",
            "fate": "unresolved",
            "unresolvedReason": "RequiresInterpretation",
        }
        result = self.result(doc)
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("semantic choice" in line and "named decision" in line
                            for line in result.details), result.details)

    def test_a_chain_is_refused(self):
        doc = document()
        second = continuation("second-additional-rule", target=CONTINUATION)
        doc["entries"].append(second)
        result = self.result(doc)
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("continuation chains are not supported" in line
                            for line in result.details), result.details)

    def test_a_target_defining_two_terms_is_refused(self):
        doc = document()
        doc["entries"][0]["defines"].append({"vocabulary": CODES, "term": "IBX"})
        doc["entries"][0]["evidence"] += " IBX"
        result = self.result(doc)
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("2 direct definition(s)" in line for line in result.details),
                        result.details)

    def test_several_additional_rules_may_join_one_term(self):
        doc = document()
        doc["entries"].insert(2, continuation("ib2-second-additional-rule"))
        self.assertEqual(defined_vocabulary(doc, CODES)["IB2"],
                         [DIRECT, CONTINUATION, "ib2-second-additional-rule"])

    def test_same_text_in_another_vocabulary_does_not_capture_the_continuation(self):
        doc = document()
        doc["entries"].insert(
            1, rule("other-ib2", IB3, "IB2 in another vocabulary",
                    defines=[{"vocabulary": OTHER, "term": "IB2"}]))
        self.assertEqual(defined_vocabulary(doc, CODES)["IB2"], [DIRECT, CONTINUATION])
        self.assertEqual(defined_vocabulary(doc, OTHER)["IB2"], ["other-ib2"])


class TheStructuralWitnessIsIndependent(unittest.TestCase):
    ROWS = [
        ["IB2", "Authorized IBCs"],
        [" ", "Additional Requirement: IB2 limit"],
        ["IB3", "Authorized IBCs"],
        [" ", "Additional Requirement: IB3 limit"],
    ]

    def setUp(self):
        self.tables = {("172.102", 2): table_of(self.ROWS)}
        self.ib2 = rule(DIRECT, IB2, "IB2 Authorized IBCs",
                        defines=[{"vocabulary": CODES, "term": "IB2"}])
        self.ib3 = rule("ib3-authorized-ibcs", IB3, "IB3 Authorized IBCs",
                        defines=[{"vocabulary": CODES, "term": "IB3"}])

    def check(self, entry, target):
        return check_locators.check_definition_continuation_anchor(entry, target, self.tables)

    def test_the_witness_resolves_to_this_row_under_its_target(self):
        verdict, message = self.check(continuation(), self.ib2)
        self.assertEqual(verdict, "ok", message)

    def test_wrong_anchor_is_refused(self):
        verdict, message = self.check(continuation(anchor=IB3_BELOW), self.ib2)
        self.assertEqual(verdict, "bad")
        self.assertIn("different row than the continuation", message)

    def test_unrelated_entry_cannot_attach_itself_with_metadata(self):
        unrelated = continuation(citation=IB3_BELOW)
        verdict, message = self.check(unrelated, self.ib2)
        self.assertEqual(verdict, "bad")
        self.assertIn("different row than the continuation", message)

    def test_term_mismatch_through_the_wrong_defining_entry_is_refused(self):
        verdict, message = self.check(continuation(), self.ib3)
        self.assertEqual(verdict, "bad")
        self.assertIn("different row than continuesDefinition.definedBy", message)

    def test_an_ordinary_row_locator_may_keep_the_structural_witness(self):
        ib3_additional = continuation("ib3-vapour-pressure-limit",
                                      target="ib3-authorized-ibcs",
                                      citation='§ 172.102 table 2, row '
                                               '[column 2 = "Additional Requirement: IB3 limit"]',
                                      anchor=IB3_BELOW)
        verdict, message = self.check(ib3_additional, self.ib3)
        self.assertEqual(verdict, "ok", message)


class DirectDefinesStillMeansWhat0045Says(unittest.TestCase):
    def run_defines(self, doc):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        try:
            with handle:
                json.dump(doc, handle)
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = check_map.main([handle.name, "--only", "defines"])
            return code, out.getvalue() + err.getvalue()
        finally:
            os.unlink(handle.name)

    def test_locator_text_still_cannot_anchor_direct_defines(self):
        doc = document()
        doc["entries"][1]["defines"] = [{"vocabulary": CODES, "term": "IB2"}]
        code, output = self.run_defines(doc)
        self.assertEqual(code, 1, output)
        self.assertIn("defines 'IB2', which does not appear in this entry's `evidence`", output)


class Trial10UsesTheWitnessOnBothRows(unittest.TestCase):
    def test_ib2_and_ib3_structural_anchors_resolve_in_the_pinned_corpus(self):
        with open(os.path.join(TRIAL, "corpus-map.json"), encoding="utf-8") as handle:
            doc = json.load(handle)
        by_id = {entry["id"]: entry for entry in doc["entries"]}
        tables = check_locators.table_index(os.path.join(TRIAL, "section-172.102.xml"))
        for entry_id, target_id in (
                ("ib2-vapour-pressure-limit", "ib2-authorized-ibcs"),
                ("ib3-vapour-pressure-limit", "ib3-authorized-ibcs")):
            with self.subTest(entry=entry_id):
                entry = by_id[entry_id]
                self.assertEqual(entry["continuesDefinition"]["definedBy"], target_id)
                self.assertEqual(entry["clarity"], "ambiguous")
                self.assertEqual(entry["ambiguity"]["fate"], "decision")
                self.assertEqual(
                    entry["ambiguity"]["decision"],
                    "docs/decisions/0046-an-additional-rule-can-continue-a-definition.md")
                self.assertNotIn("unresolvedReason", entry["ambiguity"])
                verdict, message = check_locators.check_definition_continuation_anchor(
                    entry, by_id[target_id], tables)
                self.assertEqual(verdict, "ok", message)


if __name__ == "__main__":
    unittest.main()
