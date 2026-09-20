#!/usr/bin/env python3
"""Reference-boundary amendment contract regressions (#323, 0047)."""
import copy
import json
import os
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


def add_amendment(corpus, *references):
    corpus["referenceAmendments"] = [{
        "discoveredDuring": "mapping",
        "decision": "0047",
        "references": list(references),
    }]


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
        add_amendment(
            corpus,
            {"sourceId": "cfr-49-180", "citation": "part 180", "admitted": False},
        )
        self.assertTrue(reference_covers(corpus, "cfr-49-180.605"))
        self.assertEqual(BASE_CORPUS["references"], corpus["references"])
        self.assertIn("cfr-49-180", {r["sourceId"] for r in references_of(corpus)})

    def test_a_correction_cannot_admit_the_new_corpus(self):
        corpus = copy.deepcopy(BASE_CORPUS)
        add_amendment(
            corpus,
            {"sourceId": "cfr-49-180", "citation": "part 180", "admitted": True},
        )
        result = check_manifest(context(corpus))
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("referenced-but-not-admitted" in line for line in result.details))

    def test_a_correction_cannot_carry_baseline_or_licensing_changes(self):
        for forbidden in ("contentHash", "asOf", "licence"):
            with self.subTest(forbidden=forbidden):
                corpus = copy.deepcopy(BASE_CORPUS)
                add_amendment(
                    corpus,
                    {"sourceId": "cfr-49-180", "citation": "part 180", "admitted": False},
                )
                corpus["referenceAmendments"][0][forbidden] = "changed"
                result = check_manifest(context(corpus))
                self.assertEqual(result.status, "fail")
                self.assertTrue(any("may only record" in line for line in result.details))

    def test_a_correction_reference_requires_a_nonempty_citation(self):
        for bad in (None, "", 180):
            with self.subTest(citation=bad):
                corpus = copy.deepcopy(BASE_CORPUS)
                add_amendment(
                    corpus,
                    {"sourceId": "cfr-49-180", "citation": bad, "admitted": False},
                )
                result = check_manifest(context(corpus))
                self.assertEqual(result.status, "fail")
                self.assertTrue(any("citation" in line for line in result.details))

    def test_a_part_boundary_citation_must_match_its_source_id(self):
        corpus = copy.deepcopy(BASE_CORPUS)
        add_amendment(
            corpus,
            {"sourceId": "cfr-49-180", "citation": "part 181", "admitted": False},
        )
        result = check_manifest(context(corpus))
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("does not match" in line for line in result.details))

    def test_an_existing_or_duplicate_boundary_cannot_be_amended_again(self):
        corpus = copy.deepcopy(BASE_CORPUS)
        add_amendment(
            corpus,
            {"sourceId": "cfr-49-173", "citation": "part 173", "admitted": False},
        )
        result = check_manifest(context(corpus))
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("already declared" in line for line in result.details))

        corpus = copy.deepcopy(BASE_CORPUS)
        add_amendment(
            corpus,
            {"sourceId": "cfr-49-180", "citation": "part 180", "admitted": False},
            {"sourceId": "cfr-49-180", "citation": "part 181", "admitted": False},
        )
        result = check_manifest(context(corpus))
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("already declared" in line for line in result.details))

    def test_an_already_admitted_boundary_cannot_be_amended(self):
        corpus = copy.deepcopy(BASE_CORPUS)
        corpus["references"].append(
            {"sourceId": "cfr-49-180", "citation": "part 180", "admitted": True}
        )
        add_amendment(
            corpus,
            {"sourceId": "cfr-49-180", "citation": "part 180", "admitted": False},
        )
        result = check_manifest(context(corpus))
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("already declared" in line for line in result.details))

    def test_trial_10_operational_boundary_covers_every_newly_observed_external_section(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        with open(os.path.join(repo, "examples", "hazmat-172-table", "corpus-manifest.json"),
                  encoding="utf-8") as handle:
            manifest = json.load(handle)
        corpora = {item["sourceId"]: item for item in manifest["corpora"]}
        observed = {
            "cfr-49-172.101": [
                "cfr-49-173.150", "cfr-49-173.308", "cfr-49-173.24a",
            ],
            "cfr-49-172.102": [
                "cfr-49-173.185", "cfr-49-173.225",
                "cfr-49-178.702", "cfr-49-180.605",
            ],
        }
        for source, targets in observed.items():
            for target in targets:
                with self.subTest(source=source, target=target):
                    self.assertTrue(reference_covers(corpora[source], target))


if __name__ == "__main__":
    unittest.main()
