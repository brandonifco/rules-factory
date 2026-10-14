#!/usr/bin/env python3
"""A statute passage is cited by its USLM identifier, and the quote is held to it (#653, 0082).

`/us/usc/t15/s7704/a/1` is the address the OLRC's markup already carries, so the third spelling of
a `section-designation` is the identifier itself. Watched here, over an invented chapter small
enough to read: a quote inside the cited element passes; a quote that is also somewhere the
citation does not name fails; a citation this spelling cannot read is unchecked and fails the
run; the validator's two expressions read the citation as the checker does; and pack-map has a
checker for the adapter.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
CHECKER = os.path.join(REPO, "examples", "frcp-6-12-81", "check-locators-uslm.py")

_spec = importlib.util.spec_from_file_location("check_locators_uslm_653", CHECKER)
uslm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uslm)

from mapvalidator import locators  # noqa: E402

NS = "http://xml.house.gov/schemas/uslm/1.0"
SLICE = f'''<?xml version="1.0" encoding="UTF-8"?>
<uscDoc xmlns="{NS}" identifier="/us/usc/t99">
<meta><title>Title 99</title></meta>
<main>
<chapter identifier="/us/usc/t99/ch5"><num>CHAPTER 5</num><heading>Invented matters</heading>
<section identifier="/us/usc/t99/s501"><num>&#167;501.</num><heading>Widgets</heading>
<subsection identifier="/us/usc/t99/s501/a"><num>(a)</num><heading>Rule</heading>
<paragraph identifier="/us/usc/t99/s501/a/1"><num>(1)</num><content>A widget shall be red.</content></paragraph>
<paragraph identifier="/us/usc/t99/s501/a/2"><num>(2)</num><content>A gadget shall be blue.</content></paragraph>
</subsection>
<subsection identifier="/us/usc/t99/s501/b"><num>(b)</num><content>A widget shall be red.</content></subsection>
</section>
<section identifier="/us/usc/t99/s502"><num>&#167;502.</num><heading>Gadgets</heading>
<content>No gadget is a widget.</content>
</section>
</chapter>
</main>
</uscDoc>
'''


def entry(identifier, citation, evidence, source="usc-99-ch5"):
    return {"id": identifier, "evidence": evidence,
            "locator": {"sourceId": source, "citation": citation}}


def document(entries, sections=("/us/usc/t99/s501", "/us/usc/t99/s502")):
    return {"entries": entries, "extent": {"unit": "section-designation", "sections": list(sections)}}


class RunChecker(unittest.TestCase):
    def run_checker(self, map_document):
        with tempfile.TemporaryDirectory() as directory:
            corpus = os.path.join(directory, "slice.xml")
            with open(corpus, "w", encoding="utf-8") as handle:
                handle.write(SLICE)
            path = os.path.join(directory, "corpus-map.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(map_document, handle)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = uslm.main(["check-locators-uslm.py", path, corpus])
        return code, out.getvalue() + err.getvalue()


class TestAnIdentifierCitationIsHeldToItsElement(RunChecker):
    def test_a_quote_inside_the_cited_element_passes(self):
        code, output = self.run_checker(document([
            entry("e1", "/us/usc/t99/s501/a/2", "A gadget shall be blue."),
            entry("e2", "/us/usc/t99/s501/a/1, /us/usc/t99/s501/b", "A widget shall be red."),
            entry("e3", "/us/usc/t99/s502", "No gadget is a widget."),
        ]))
        self.assertEqual(0, code, output)
        self.assertIn("locators ok (all 3 checked", output)

    def test_a_quote_the_citation_does_not_contain_fails(self):
        code, output = self.run_checker(document([
            entry("e1", "/us/usc/t99/s501/a/1", "A gadget shall be blue."),
            entry("e3", "/us/usc/t99/s502", "No gadget is a widget."),
        ]))
        self.assertEqual(1, code, output)
        self.assertIn("evidence also sits in /us/usc/t99/s501/a/2", output)

    def test_a_sentence_printed_twice_must_be_inside_the_citation_both_times(self):
        code, output = self.run_checker(document([
            entry("e1", "/us/usc/t99/s501/a/1", "A widget shall be red."),
            entry("e2", "/us/usc/t99/s501/a/2", "A gadget shall be blue."),
            entry("e3", "/us/usc/t99/s502", "No gadget is a widget."),
        ]))
        self.assertEqual(1, code, output)
        self.assertIn("2 occurrence(s)", output)

    def test_a_citation_in_a_title_the_corpus_does_not_hold_is_not_resolved(self):
        code, output = self.run_checker(document([
            entry("e1", "/us/usc/t98/s501/a/1", "A gadget shall be blue."),
        ]))
        self.assertEqual(1, code, output)

    def test_a_citation_this_spelling_cannot_read_is_unchecked_and_fails_the_run(self):
        for citation in ("/us/usc/t99/s501/a/1-2", "15 U.S.C. 501(a)", "/us/usc/t99/s501/a/1 and b",
                         "/us/usc/t99/ch5"):
            with self.subTest(citation=citation):
                code, output = self.run_checker(document([
                    entry("e1", citation, "A gadget shall be blue.")]))
                self.assertEqual(1, code, output)
                self.assertIn("outside the grammar", output)

    def test_text_a_chapter_prints_outside_its_sections_is_refused(self):
        code, output = self.run_checker(document([
            entry("e1", "/us/usc/t99/s501", "Invented matters"),
        ]))
        self.assertEqual(1, code, output)
        self.assertIn("sits in no identified element", output)

    def test_an_extent_section_no_verified_quote_reaches_fails_coverage(self):
        code, output = self.run_checker(document([
            entry("e1", "/us/usc/t99/s501/a/2", "A gadget shall be blue."),
        ]))
        self.assertEqual(1, code, output)
        self.assertIn("/us/usc/t99/s502: inside the declared extent and reached by no entry", output)

    def test_an_ellipsis_may_skip_whole_units_and_never_words_inside_one(self):
        code, output = self.run_checker(document([
            entry("e1", "/us/usc/t99/s501", "(a) Rule ... A gadget shall be blue."),
            entry("e3", "/us/usc/t99/s502", "No gadget is a widget."),
        ]))
        self.assertEqual(1, code, output)
        self.assertIn("ellipsis", output)


class TestTheValidatorReadsTheSpellingAsTheCheckerDoes(unittest.TestCase):
    def test_the_citation_names_its_section(self):
        for citation in ("/us/usc/t99/s501/a/1", "/us/usc/t99/s501", "/us/usc/t99/s501/a, /us/usc/t99/s501/b"):
            with self.subTest(citation=citation):
                self.assertEqual(("section", "/us/usc/t99/s501"), locators.cited_section(citation))
                self.assertEqual((uslm.cited_paths(citation)[0][0], "section"),
                                 ("t99/s501", locators.cited_section(citation)[0]))

    def test_an_identifier_that_is_only_the_tail_of_a_longer_path_is_not_renamed(self):
        self.assertIsNone(locators.cited_section("see/us/usc/t99/s501/a"))
        self.assertIsNone(uslm.cited_paths("/us/usc/t99/s501/a/"))
        # a section token is read whole, so `s501x` is a section of its own and not `s501`
        self.assertEqual(("section", "/us/usc/t99/s501x"),
                         locators.cited_section("/us/usc/t99/s501x/a"))

    def test_an_extent_item_is_a_section_and_nothing_below_it(self):
        self.assertEqual("/us/usc/t99/s501", locators.extent_designation("/us/usc/t99/s501"))
        self.assertIsNone(locators.extent_designation("/us/usc/t99/s501/a"))
        self.assertIsNone(uslm.EXTENT_STATUTE.match("/us/usc/t99/s501/a"))

    def test_it_is_printed_as_written(self):
        self.assertEqual("/us/usc/t99/s501", locators.printed_designation("/us/usc/t99/s501"))
        self.assertEqual("§ 107.29", locators.printed_designation("107.29"))

    def test_the_checker_and_the_validator_hold_the_same_expressions(self):
        self.assertEqual(uslm.EXTENT_STATUTE.pattern.replace("(t", "(/us/usc/t", 1)
                         .replace("^/us/usc/(/us/usc/", "^(/us/usc/"),
                         locators.EXTENT_STATUTE.pattern)


class TestTheTwoValidatorCopiesAreOne(unittest.TestCase):
    def test_check_map_holds_the_expressions_mapvalidator_holds(self):
        spec = importlib.util.spec_from_file_location("check_map_653", os.path.join(TOOLS, "check-map.py"))
        check_map = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check_map)
        for name in ("CITE_STATUTE", "EXTENT_STATUTE"):
            self.assertEqual(getattr(locators, name).pattern, getattr(check_map, name).pattern)
        for citation in ("/us/usc/t99/s501/a/1", "see/us/usc/t99/s501", "/us/usc/t99/s501x"):
            self.assertEqual(locators.cited_section(citation), check_map.cited_section(citation))
        self.assertEqual("/us/usc/t99/s501", check_map.printed_designation("/us/usc/t99/s501"))


class TestPackMapHasAChecker(unittest.TestCase):
    def test_uslm_xml_has_a_locator_checker_that_exists(self):
        spec = importlib.util.spec_from_file_location("pack_map_653", os.path.join(TOOLS, "pack-map.py"))
        module = importlib.util.module_from_spec(spec)
        import sys
        before, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = before
        self.assertEqual(CHECKER, module.LOCATOR_CHECKERS["uslm-xml"])
        self.assertTrue(os.path.isfile(module.LOCATOR_CHECKERS["uslm-xml"]))


if __name__ == "__main__":
    unittest.main()
