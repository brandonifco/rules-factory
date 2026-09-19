#!/usr/bin/env python3
"""Watched reproduction for #321: an anchored definition continuation must join its term.

The second IB2 row in trial 10 states an additional rule but does not repeat `IB2`. Direct
`defines` correctly refuses it under 0045, so the missing contract concept is represented here
as an explicit `continuesDefinition` claim. These tests are committed red before production code:
on main, `defined_vocabulary` reads only direct `defines`, and deleting the pointer's second
`resolvedBy` is therefore clean.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, TOOLS)
try:
    from mapcontract.entry import defined_vocabulary
    from mapper import pointers
finally:
    sys.path.remove(TOOLS)

CODES = "special-provision-codes"
PROVISIONS = "cfr-49-172.102"
TABLE = "cfr-49-172.101"
DIRECT = "ib2-authorized-ibcs"
CONTINUATION = "ib2-vapour-pressure-limit"


def document():
    return {
        "entries": [
            {
                "id": DIRECT,
                "locator": {
                    "sourceId": PROVISIONS,
                    "citation": '§ 172.102 table 2, row [column 1 = "IB2"]',
                },
                "evidence": "IB2 | Authorized IBCs: Metal (31A).",
                "defines": [{"vocabulary": CODES, "term": "IB2"}],
            },
            {
                "id": CONTINUATION,
                "locator": {
                    "sourceId": PROVISIONS,
                    "citation": '§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]',
                },
                "evidence": "| Additional Requirement: Only liquids with a vapor pressure "
                            "less than or equal to 110 kPa are authorized.",
                "continuesDefinition": {
                    "definedBy": DIRECT,
                    "anchor": {
                        "sourceId": PROVISIONS,
                        "citation": '§ 172.102 table 2, row blank in column 1 below row '
                                    '[column 1 = "IB2"]',
                    },
                },
            },
            {
                "id": "acetal-special-provisions",
                "locator": {
                    "sourceId": TABLE,
                    "citation": '§ 172.101 table 3, row [column 2 = "Acetal"], column 7',
                },
                "evidence": "IB2",
                "crossReferences": [{"cites": "IB2", "resolvedBy": DIRECT}],
            },
        ]
    }


class TheGapOnMain(unittest.TestCase):
    def test_the_additional_rule_joins_the_defining_set(self):
        self.assertEqual(
            defined_vocabulary(document(), CODES)["IB2"],
            [DIRECT, CONTINUATION],
        )

    def test_removing_the_second_resolved_by_is_not_clean(self):
        naming = pointers.detect_coded(
            document(), {"mechanism": "coded-pointer", "column": 7, "vocabulary": CODES}
        )[0]
        self.assertEqual(naming.missing, [CONTINUATION])


if __name__ == "__main__":
    unittest.main()
