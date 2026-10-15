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
import re
import sys
import tempfile
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


STATUTE = os.path.join(REPO, "examples", "can-spam", "usc15-ch103.xml")


class TestAStatuteChapterIsInventoried(unittest.TestCase):
    """A chapter of the Code is the same grammar under another identifier prefix (0082, #654)."""

    def setUp(self):
        self.checker = _checker()
        self.adapter = UslmXml(STATUTE)
        self.sections = ["/us/usc/" + number for number in self.adapter._rules()]
        self.extent = {"unit": "section-designation", "sections": self.sections}

    def test_the_chapter_has_its_thirteen_sections_and_all_are_enumerated(self):
        self.assertEqual(len(self.sections), 13)
        units = self.adapter.units(self.extent)
        self.assertEqual({u.key.split("/")[4].split(" ")[0] for u in units},
                         {f"s{n}" for n in range(7701, 7714)})

    def test_the_same_passages_in_the_same_order_with_the_same_text(self):
        units = self.adapter.units(self.extent)
        text, spans = self.checker.corpus_index(STATUTE)
        self.assertEqual(len(units), len(spans))
        for unit, (start, end, path) in zip(units, spans):
            designation = self.checker.designation(path)
            with self.subTest(unit=unit.key):
                # Exactly the designation, or the designation and one of the run names the
                # adapter gives (#661 review, finding 7): a suffix of any other spelling is a
                # key nothing documents.
                self.assertRegex(unit.key, "^" + re.escape(designation)
                                 + r"(?: (?:heading|closing|continuation)(?: [0-9]+)?)?$")
                self.assertEqual(unit.text, text[start:end])

    def test_no_two_units_share_a_key(self):
        """15 U.S.C. 7702(17)(A) prints a `<continuation>` after its clauses: two runs."""
        keys = [u.key for u in self.adapter.units(self.extent)]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("/us/usc/t15/s7702/17/A continuation", keys)

    def test_an_extent_may_name_one_section(self):
        units = self.adapter.units({"unit": "section-designation",
                                    "sections": ["/us/usc/t15/s7713"]})
        self.assertEqual([u.key for u in units], ["/us/usc/t15/s7713"])

    def test_an_extent_naming_a_section_the_chapter_does_not_hold_is_refused(self):
        with self.assertRaises(Refused) as caught:
            self.adapter.units({"unit": "section-designation",
                                "sections": ["/us/usc/t15/s7701", "/us/usc/t15/s9999"]})
        self.assertIn("/us/usc/t15/s9999", str(caught.exception))

    def test_a_section_of_another_title_is_not_this_one(self):
        with self.assertRaises(Refused):
            self.adapter.units({"unit": "section-designation",
                                "sections": ["/us/usc/t26/s7701"]})


NS = "http://xml.house.gov/schemas/uslm/1.0"
S = "/us/usc/t99/s501"


def invented(body):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<uscDoc xmlns="{NS}" identifier="/us/usc/t99">'
            f'<main><chapter identifier="/us/usc/t99/ch5">{body}</chapter></main></uscDoc>')


class TestAnInventedChapter(unittest.TestCase):
    """A chapter small enough to read, for what the real one cannot be made to print."""

    def units(self, body, sections=(S,)):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "slice.xml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(invented(body))
            extent = {"unit": "section-designation", "sections": list(sections)}
            walked = UslmXml(path).units(extent)
            indexed = _checker().corpus_index(path)
        return walked, indexed

    def test_every_run_of_text_after_the_first_is_keyed_apart(self):
        """#661 review, finding 5: three runs under one identifier were keyed as two."""
        walked, _ = self.units(
            f'<section identifier="{S}"><heading>H</heading>'
            f'<subsection identifier="{S}/a"><chapeau>Start</chapeau>'
            f'<paragraph identifier="{S}/a/1">One</paragraph><continuation>Middle</continuation>'
            f'<paragraph identifier="{S}/a/2">Two</paragraph><continuation>End</continuation>'
            f'</subsection><sourceCredit>Credit</sourceCredit>'
            f'<paragraph identifier="{S}/z">Zed</paragraph><notes>Note one</notes>'
            f'<paragraph identifier="{S}/y">Why</paragraph><notes>Note two</notes></section>')
        self.assertEqual(
            [(u.key, u.text) for u in walked],
            [(f"{S} heading", "H"), (f"{S}/a", "Start"), (f"{S}/a/1", "One"),
             (f"{S}/a continuation", "Middle"), (f"{S}/a/2", "Two"),
             (f"{S}/a continuation 2", "End"), (f"{S} closing", "Credit"),
             (f"{S}/z", "Zed"), (f"{S} closing 2", "Note one"), (f"{S}/y", "Why"),
             (f"{S} closing 3", "Note two")])
        self.assertEqual(len({u.key for u in walked}), len(walked))

    def test_a_foreign_element_carrying_an_identifier_is_not_a_unit(self):
        """#661 review, finding 6: ownership came from the attribute and never the namespace."""
        walked, (text, spans) = self.units(
            f'<section identifier="{S}"><heading>H</heading></section>'
            f'<x:section xmlns:x="urn:other" identifier="/us/usc/t99/s502">Foreign words'
            f'</x:section>', sections=(S,))
        self.assertEqual([u.key for u in walked], [S])
        with self.assertRaises(Refused):
            self.units(f'<x:section xmlns:x="urn:other" identifier="{S}">Foreign words</x:section>')
        # the checker's index is the same walk: the foreign words belong to no span
        self.assertEqual([text[start:end] for start, end, _ in spans], ["H"])

    def test_the_two_walks_agree_over_the_invented_chapter(self):
        walked, (text, spans) = self.units(
            f'<section identifier="{S}"><heading>H</heading>'
            f'<subsection identifier="{S}/a"><chapeau>Start</chapeau>'
            f'<paragraph identifier="{S}/a/1">One</paragraph><continuation>Middle</continuation>'
            f'<x:aside xmlns:x="urn:other" identifier="{S}/q">Aside</x:aside>'
            f'<paragraph identifier="{S}/a/2">Two</paragraph><continuation>End</continuation>'
            f'</subsection><sourceCredit>Credit</sourceCredit></section>')
        self.assertEqual(len(walked), len(spans))
        for unit, (start, end, _) in zip(walked, spans):
            self.assertEqual(unit.text, text[start:end])


if __name__ == "__main__":
    unittest.main()
