#!/usr/bin/env python3
"""Reference-boundary amendment contract regressions (#323, 0047)."""
import copy
import unittest

from mapcontract.entry import reference_covers, references_of
from mapvalidator.manifest import check_manifest


BASE_CORPUS = {
    "sourceId": "cfr-49-172.102",
    "adapter": "ecfr-xml",
    "contentHash": "a" * 64,
    "hashDerivation": "ecfr-versioner-xml",
    "asOf": "2026-01-01",
    "licence": "public-domain-us-government",
    "references": [
        {"sourceId": "cfr-49-173", "citation": "part 173", "admitted": False},
        {"sourceId": "cfr-49-178", "citation": "part 178", "admitted": False},
    ],
}


def context(corpus):
    return {
        "manifest": {"schemaVersion": 1, "corpora": [corpus]},
        "map": {
            "corpus": corpus["sourceId"],
            "baseline": {
                "contentHash": corpus["contentHash"],
                "hashDerivation": corpus["hashDerivation"],
            },
            "entries": [],
        },
        "manifest_path": None,
    }


class TestReferenceBoundaryAmendments(unittest.TestCase):
    def test_broad_part_reference_covers_child_sections(self):
        self.assertTrue(reference_covers(BASE_CORPUS, "cfr-49-173.150"))
        self.assertTrue(reference_covers(BASE_CORPUS, "cfr-49-173.308"))
        self.assertTrue(reference_covers(BASE_CORPUS, "cfr-49-178.702"))

    def test_a_section_reference_is_not_a_prefix_wildcard(self):
        corpus = copy.deepcopy(BASE_CORPUS)
        corpus["references"] = [
            {"sourceId": "cfr-49-173.2", "citation": "§ 173.2", "admitted": False}
        ]
        self.assertFalse(reference_covers(corpus, "cfr-49-173.2a"))

    def test_an_undeclared_part_is_missing_until_an_amendment_adds_it(self):
        self.assertFalse(reference_covers(BASE_CORPUS, "cfr-49-180.605"))
        corpus = copy.deepcopy(BASE_CORPUS)
        corpus["referenceAmendments"] = [{
            "discoveredDuring": "mapping",
            "decision": "0047",
            "references": [
                {"sourceId": "cfr-49-180", "citation": "part 180", "admitted": False}
            ],
        }]
        self.assertTrue(reference_covers(corpus, "cfr-49-180.605"))
        self.assertEqual(BASE_CORPUS["references"], corpus["references"])
        self.assertIn("cfr-49-180", {r["sourceId"] for r in references_of(corpus)})

    def test_a_correction_cannot_admit_the_new_corpus(self):
        corpus = copy.deepcopy(BASE_CORPUS)
        corpus["referenceAmendments"] = [{
            "discoveredDuring": "mapping",
            "decision": "0047",
            "references": [
                {"sourceId": "cfr-49-180", "citation": "part 180", "admitted": True}
            ],
        }]
        result = check_manifest(context(corpus))
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("referenced-but-not-admitted" in line for line in result.details))

    def test_a_correction_cannot_carry_baseline_or_licensing_changes(self):
        for forbidden in ("contentHash", "asOf", "licence"):
            with self.subTest(forbidden=forbidden):
                corpus = copy.deepcopy(BASE_CORPUS)
                corpus["referenceAmendments"] = [{
                    "discoveredDuring": "mapping",
                    "decision": "0047",
                    "references": [
                        {"sourceId": "cfr-49-180", "citation": "part 180", "admitted": False}
                    ],
                    forbidden: "changed",
                }]
                result = check_manifest(context(corpus))
                self.assertEqual(result.status, "fail")
                self.assertTrue(any("may only record" in line for line in result.details))


if __name__ == "__main__":
    unittest.main()
