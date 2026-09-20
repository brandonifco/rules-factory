#!/usr/bin/env python3
"""Watched regressions for complete CFR section designation identity (#323)."""
import importlib.util
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

from mapvalidator import crossrefs, locators


def section_checker():
    path = os.path.join(REPO, "examples", "faa-part-107", "check-locators-section.py")
    spec = importlib.util.spec_from_file_location("check_locators_section_323", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSectionDesignationIdentity(unittest.TestCase):
    def test_bare_letter_suffixes_are_whole_designations(self):
        for text, wanted in (
            ("§ 173.2a", "173.2a"),
            ("§ 173.4a", "173.4a"),
            ("§ 173.24b", "173.24b"),
        ):
            with self.subTest(text=text):
                match = locators.CITE_SECTION.search(text)
                self.assertIsNotNone(match)
                self.assertEqual(match.group(1), wanted)

    def test_existing_hyphenated_and_paragraph_forms_stay_whole(self):
        checker = section_checker()
        for text, wanted in (
            ("§ 173.2(a)", "173.2"),
            ("§ 1.121-1", "1.121-1"),
            ("§ 1.121-1(b)(4)", "1.121-1"),
        ):
            with self.subTest(text=text):
                self.assertEqual(locators.CITE_SECTION.search(text).group(1), wanted)
                self.assertEqual(checker.CITE_SECTION.search(text).group(1), wanted)

    def test_checker_and_validator_read_bare_letter_suffixes_the_same_way(self):
        checker = section_checker()
        for text in ("§ 173.2a", "§ 173.4a", "§ 173.24b"):
            with self.subTest(text=text):
                self.assertEqual(
                    locators.CITE_SECTION.search(text).group(1),
                    checker.CITE_SECTION.search(text).group(1),
                )
                self.assertEqual(locators.CITE_SECTION.search(text).group(1), text.split()[-1])

    def test_longer_invalid_suffix_is_not_returned_as_a_shorter_valid_section(self):
        for text in ("§ 173.2abc", "§ 173.2aXYZ"):
            with self.subTest(text=text):
                self.assertIsNone(locators.CITE_SECTION.search(text))

    def test_designation_terminates_before_neighboring_prose_and_punctuation(self):
        for text, wanted in (
            ("See § 173.2a.", "173.2a"),
            ("See § 173.4a, then continue.", "173.4a"),
            ("See § 1.121-1(b)(4).", "1.121-1"),
        ):
            with self.subTest(text=text):
                self.assertEqual(locators.CITE_SECTION.search(text).group(1), wanted)

    def test_corpus_regex_cannot_report_a_section_prefix_as_the_pointer(self):
        incomplete = re.compile(r"§+\\s?\\d+\\.\\d+(?:\\([A-Za-z0-9]+\\))*", re.I)
        self.assertEqual(crossrefs.pointers_in("See § 173.2a.", [incomplete]), [])


if __name__ == "__main__":
    unittest.main()
