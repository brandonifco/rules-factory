#!/usr/bin/env python3
"""A chapter of the United States Code is admitted as the release's own bytes (#653, 0082).

The OLRC serves a title as a zip holding one USLM member. `olrc-uslm-chapter-slice-verbatim` is
the name of the derivation that takes one chapter of it, and `tools/derive-uslm-chapter.py` is
the derivation. Watched here: the slice is exactly the bytes the derivation states, the
refusals are the ones it promises, and the closed set of admitted names has the new name in it
and still refuses a near miss.

The release is invented, small, and written here. Nothing in it is a real statute.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
FACTORY = os.path.join(TOOLS, "factory")

_spec = importlib.util.spec_from_file_location(
    "derive_uslm_chapter", os.path.join(TOOLS, "derive-uslm-chapter.py"))
derive = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(derive)

_spec = importlib.util.spec_from_file_location("intake_uslm_slice", os.path.join(FACTORY, "intake.py"))
intake = importlib.util.module_from_spec(_spec)
_bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
sys.path.insert(0, FACTORY)
try:
    _spec.loader.exec_module(intake)
finally:
    sys.dont_write_bytecode = _bytecode

NAME = "olrc-uslm-chapter-slice-verbatim"
ROOT = ('<uscDoc xsi:schemaLocation="http://xml.house.gov/schemas/uslm/1.0 USLM-1.0.15.xsd" '
        'xml:lang="en" identifier="/us/usc/t99" xmlns="http://xml.house.gov/schemas/uslm/1.0" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">')
META = "<meta>\n  <dc:title>Title 99</dc:title>\n  <property role=\"is-positive-law\">no</property>\n</meta>"
CHAPTER = ('<chapter id="c1" identifier="/us/usc/t99/ch5"><num value="5">CHAPTER 5&#8212;</num>'
           '<heading>Invented</heading>\n'
           '<section id="s1" identifier="/us/usc/t99/s501"><num value="501">&#167;501.</num>'
           '<subsection id="s1a" identifier="/us/usc/t99/s501/a"><content>A thing &amp; another.</content>'
           '</subsection></section>\n</chapter>')
OTHER = ('<chapter id="c2" identifier="/us/usc/t99/ch50"><num value="50">CHAPTER 50</num>'
         '<section id="s2" identifier="/us/usc/t99/s5001"><content>Elsewhere.</content></section></chapter>')


def member(chapter=CHAPTER, other=OTHER, head=None):
    head = head if head is not None else (
        '<?xml version="1.0" encoding="UTF-8"?>\r\n<?xml-stylesheet type="text/css" '
        'href="usctitle.css"?>\r\n')
    return (head + ROOT + "\n" + META + "\n<main>\n<title identifier=\"/us/usc/t99\">"
            + other + "\n" + chapter + "\n</title>\n</main>\n</uscDoc>\n").encode("utf-8")


class Release:
    """A temporary zip holding `members` ({name: bytes})."""

    def __init__(self, members):
        self.members = members

    def __enter__(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "xml_usc99.zip")
        with zipfile.ZipFile(self.path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in self.members.items():
                archive.writestr(name, data)
        return self

    def __exit__(self, *exc):
        self.directory.cleanup()


class TestTheSliceIsTheDerivationsBytes(unittest.TestCase):
    def test_the_slice_is_the_declaration_the_root_the_meta_and_the_chapter_verbatim(self):
        with Release({"usc99.xml": member()}) as release:
            got = derive.derive(release.path, "/us/usc/t99/ch5")
        want = ('<?xml version="1.0" encoding="UTF-8"?>\n' + ROOT + "\n" + META + "\n<main>\n"
                + CHAPTER + "\n</main>\n</uscDoc>\n").encode("utf-8")
        self.assertEqual(want, got)

    def test_a_chapter_whose_identifier_is_a_prefix_of_another_is_the_one_named(self):
        with Release({"usc99.xml": member()}) as release:
            self.assertIn(b'identifier="/us/usc/t99/ch50"',
                          derive.derive(release.path, "/us/usc/t99/ch50"))
            self.assertNotIn(b"ch50", derive.derive(release.path, "/us/usc/t99/ch5"))

    def test_the_members_carriage_returns_are_not_carried(self):
        with Release({"usc99.xml": member()}) as release:
            self.assertNotIn(b"\r", derive.derive(release.path, "/us/usc/t99/ch5"))

    def test_check_matches_the_derivation_and_names_a_difference(self):
        with Release({"usc99.xml": member()}) as release, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            held = os.path.join(release.directory.name, "slice.xml")
            self.assertEqual(0, derive.main(["x", "--from", release.path,
                                             "--chapter", "/us/usc/t99/ch5", "--into", held]))
            self.assertEqual(0, derive.main(["x", "--from", release.path,
                                             "--chapter", "/us/usc/t99/ch5", "--check", held]))
            with open(held, "ab") as handle:
                handle.write(b"\n")
            self.assertEqual(1, derive.main(["x", "--from", release.path,
                                             "--chapter", "/us/usc/t99/ch5", "--check", held]))


class TestWhatTheDerivationRefuses(unittest.TestCase):
    def refused(self, members, chapter="/us/usc/t99/ch5"):
        with Release(members) as release:
            with self.assertRaises(derive.Refused) as raised:
                derive.derive(release.path, chapter)
        return str(raised.exception)

    def test_a_member_not_named_for_the_chapters_title(self):
        self.assertIn("usc99.xml", self.refused({"usc15.xml": member()}))

    def test_a_zip_holding_more_than_the_one_member(self):
        self.refused({"usc99.xml": member(), "usc99.css": b"x"})

    def test_a_chapter_the_release_does_not_hold(self):
        self.assertIn("0 elements", self.refused({"usc99.xml": member()}, "/us/usc/t99/ch6"))

    def test_a_chapter_identified_twice(self):
        self.assertIn("2 elements", self.refused({"usc99.xml": member(other=CHAPTER)}))

    def test_a_chapter_that_nests_another(self):
        nested = CHAPTER.replace("</chapter>", OTHER.replace("ch50", "ch51") + "</chapter>")
        self.assertIn("another chapter", self.refused({"usc99.xml": member(chapter=nested)}))

    def test_a_carriage_return_inside_the_chapter(self):
        crlf = CHAPTER.replace("\n<section", "\r\n<section")
        self.assertIn("carriage return", self.refused({"usc99.xml": member(chapter=crlf)}))

    def test_an_identifier_that_is_not_a_chapter(self):
        self.assertIn("not a chapter identifier",
                      self.refused({"usc99.xml": member()}, "/us/usc/t99/s501"))

    def test_an_element_that_is_not_a_chapter_carrying_the_identifier(self):
        wrong = CHAPTER.replace("<chapter ", "<subchapter ").replace("</chapter>", "</subchapter>")
        self.refused({"usc99.xml": member(chapter=wrong)})


class TestTheNameIsAdmitted(unittest.TestCase):
    def test_the_derivation_is_registered(self):
        self.assertIn(NAME, intake.ADMITTED_HASH_DERIVATIONS)

    def test_the_set_is_still_closed(self):
        for near in ("olrc-uslm-xml-member", "olrc-uslm-chapter-slice", NAME.upper()):
            self.assertNotIn(near, intake.ADMITTED_HASH_DERIVATIONS)


if __name__ == "__main__":
    unittest.main()
