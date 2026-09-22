"""The USLM adapter's walk and the USLM locator checker's index are the same walk (trial 11).

`tools/mapper/corpus.py` enumerates a corpus's units so the inventory can say which the map
reached; `examples/frcp-6-12-81/check-locators-uslm.py` indexes the same corpus so a citation can
be resolved against it. The two files cannot import one another -- 0032 puts them in different
subsystems -- so nothing else would notice them drifting apart, and the drift has a name: a unit
the checker can cite and the adapter cannot see is a denominator that shrinks to fit what was
read, and a unit the adapter counts and no citation can reach is a coverage gap nothing can close.

`test_mapper_top_level.py` and `test_mapper_nested_paragraphs.py` hold the eCFR pair to each
other by comparing the closed sets each one walks, because that pair *does* differ in one
decidable respect. This pair differs in none: USLM carries the designation path in an attribute,
both walks read it, and the comparison is therefore the strongest available -- same units, same
order, same text.
"""
import importlib.util
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
TRIAL = os.path.join(REPO, "examples", "frcp-6-12-81")

sys.path.insert(0, TOOLS)
try:
    from mapper.corpus import ADAPTERS, Refused, UslmXml
finally:
    sys.path.remove(TOOLS)


def _checker():
    spec = importlib.util.spec_from_file_location(
        "check_locators_uslm", os.path.join(TRIAL, "check-locators-uslm.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheTwoWalksAgree(unittest.TestCase):
    def setUp(self):
        self.corpus = os.path.join(TRIAL, "frcp-6-12-81.xml")
        with open(os.path.join(TRIAL, "corpus-map.json"), encoding="utf-8") as handle:
            self.extent = json.load(handle)["extent"]
        self.checker = _checker()

    def test_the_adapter_is_registered_under_its_manifest_name(self):
        self.assertIs(ADAPTERS.get("uslm-xml"), UslmXml)

    def test_the_same_passages_in_the_same_order_with_the_same_text(self):
        units = UslmXml(self.corpus).units(self.extent)
        text, spans = self.checker.corpus_index(self.corpus)
        self.assertTrue(units, "the adapter enumerated nothing -- this test proved nothing")
        self.assertEqual(len(units), len(spans))
        for unit, (start, end, path) in zip(units, spans):
            designation = self.checker.designation(path)
            with self.subTest(unit=unit.key):
                # The rule element prints twice -- its heading, then its source credit -- so the
                # adapter's key carries which run it is and the checker's path does not.
                self.assertTrue(unit.key == designation
                                or unit.key.startswith(designation + " "), unit.key)
                self.assertEqual(unit.text, text[start:end])

    def test_an_extent_naming_a_rule_the_corpus_does_not_hold_is_refused(self):
        """An extent over a rule that is not there claims coverage of nothing."""
        extent = dict(self.extent, sections=["Rule 6", "Rule 9999"])
        with self.assertRaises(Refused) as caught:
            UslmXml(self.corpus).units(extent)
        self.assertIn("Rule 9999", str(caught.exception))

    def test_an_extent_in_another_unit_is_refused_rather_than_enumerated(self):
        with self.assertRaises(Refused):
            UslmXml(self.corpus).units({"unit": "page", "from": 1, "to": 2})


if __name__ == "__main__":
    unittest.main()
