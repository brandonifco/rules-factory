#!/usr/bin/env python3
"""At the top level of a section, nothing with words in it is passed over without a word.

[#288](https://github.com/brandonifco/rules-factory/pull/288) made that true of the **descent
into a wrapper** and asserted it in `test_mapper_nested_paragraphs.py`. The top level of a
section was older and unchanged: a direct child of a `DIV8` that is not `P`, `EXAMPLE` or a
wrapper was dropped by both walks, with no record that anything had been there
([#290](https://github.com/brandonifco/rules-factory/issues/290)).

Measured on the committed corpora, that is `HEAD` (120), `CITA` (30), `DIV` (12), `EDNOTE` (2)
and `HD1` (1). Nothing normative is *known* to be lost -- `CITA` is the authority citation,
`EDNOTE` an editorial note, `DIV` a table addressed by its rows (0035) -- but nothing checked it,
and a corpus introducing a new block tag at the top level would lose it in silence. That is
exactly what #285 was, one level down.

What is watched here:

  * every text-bearing direct child of a section is **indexed or reported**, in both walks, with
    `TOP_LEVEL_PASSED_OVER` the one named exception -- a closed set, with the reason each member
    is in it written beside it, so that passing text over is a decision and not an omission;
  * the two walks name the **same** set, the way `NESTED_UNITS` and `NESTED_KINDS` are already
    held equal -- the two files cannot import one another (0032), so nothing else would notice
    them drifting apart;
  * `HEAD` is in the set on a stated basis and not by accident: the adapter enumerates a
    section's heading as its own `§ N heading` unit, and the checker's citation grammar has no
    designation path that could name one;
  * the invariant holds over the **committed corpora**, not only the fixture, because a rule
    measured on a fixture is a rule measured on the shapes its author thought of.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import os
import sys
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

sys.path.insert(0, TOOLS)
try:
    from mapper import corpus
finally:
    sys.path.pop(0)

_spec = importlib.util.spec_from_file_location(
    "check_locators_section",
    os.path.join(REPO, "examples", "faa-part-107", "check-locators-section.py"))
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

#: A section printing, at its top level, each tag the committed corpora print there -- plus one
#: this walk has never seen, which is the shape #285 was and the shape the next corpus will be.
TOP_LEVEL = """<ROOT><DIV6 N="B" TYPE="SUBPART">
<DIV8 N="2.10" TYPE="SECTION"><HEAD>§ 2.10 Top-level shapes.</HEAD>
<P>(a) An ordinary designated paragraph.</P>
<CITA>Authority: 49 U.S.C. 5101 et seq.</CITA>
<EDNOTE><HED>Editorial Note:</HED><P>At 84 FR 1, this section was redesignated.</P></EDNOTE>
<HD1>Appendix B to § 2.10—A division heading at the top level</HD1>
<DIV><TABLE><THEAD><TR><TD>(1) Code</TD><TD>(2) Limit</TD></TR></THEAD>
<TBODY><TR><TD>Z9</TD><TD>1 L</TD></TR></TBODY></TABLE></DIV>
<SOMETHINGNEW>A block tag neither walk has ever seen.</SOMETHINGNEW>
<P>(b) A second designated paragraph, after all of that.</P>
</DIV8></DIV6></ROOT>"""

COMMITTED = [
    os.path.join(REPO, "examples", "faa-part-107", "part107.xml"),
    os.path.join(REPO, "examples", "faa-part-107-temporal", "part107-2020-01-01.xml"),
    os.path.join(REPO, "examples", "tax-121-principal-residence", "section-1.121-1.xml"),
    os.path.join(REPO, "examples", "hazmat-172-table", "section-172.101.xml"),
    os.path.join(REPO, "examples", "hazmat-172-table", "section-172.102.xml"),
]


def top_level_text(root, passed_over):
    """Every text-bearing direct child of a section, counted independently of either walk.

    Knows only which tags are wrappers (their contents are the other test's subject) and which
    are deliberately passed over. Everything else with words in it must come back from the walk.
    """
    found = []
    for section in root.iter("DIV8"):
        for child in section:
            if child.tag in checker.NESTED_CONTAINERS or child.tag in passed_over:
                continue
            text = checker.normalise("".join(child.itertext()))
            if text:
                found.append(text)
    return found


class TestTheSetIsNamed(unittest.TestCase):
    """What is passed over at the top level is a closed, named set -- in both walks, the same one.

    Mutation: add a tag to one file's set and not the other's, or delete the constant and go back
    to `continue`. The first fails `test_the_two_walks_name_the_same_set`; the second fails every
    test below it.
    """

    def test_both_walks_name_a_top_level_set(self):
        self.assertTrue(hasattr(checker, "TOP_LEVEL_PASSED_OVER"))
        self.assertTrue(hasattr(corpus, "TOP_LEVEL_PASSED_OVER"))

    def test_the_two_walks_name_the_same_set(self):
        self.assertEqual(tuple(checker.TOP_LEVEL_PASSED_OVER),
                         tuple(corpus.TOP_LEVEL_PASSED_OVER))

    def test_a_table_at_the_top_level_is_passed_over_because_its_rows_address_it(self):
        for tag in checker.TABLE_WRAPPERS:
            self.assertIn(tag, checker.TOP_LEVEL_PASSED_OVER)

    def test_a_sections_heading_is_passed_over_because_the_adapter_enumerates_it(self):
        self.assertIn("HEAD", checker.TOP_LEVEL_PASSED_OVER)

    def test_the_editorial_tags_are_stepped_over_on_a_stated_reading(self):
        # CITA, EDNOTE and HD1 rest on a reading of what the eCFR prints -- authority citation,
        # editorial annotation, division title -- and not on a check. They are in the set, and
        # the tally below is what keeps that reading challengeable rather than invisible.
        for tag in ("CITA", "EDNOTE", "HD1"):
            self.assertIn(tag, checker.TOP_LEVEL_PASSED_OVER)

    def test_the_set_is_closed_and_no_larger_than_its_stated_members(self):
        self.assertEqual(set(checker.TOP_LEVEL_PASSED_OVER),
                         {"HEAD", "DIV", "TABLE", "CITA", "EDNOTE", "HD1"})


class TestTheCheckerReportsWhatItCannotPlace(unittest.TestCase):
    """The section locator checker gives every top-level passage an address or a reason.

    Mutation: `continue` instead of appending, on the top-level branch of `paragraphs` that has
    no unit to give. Every test here fails on the fixture.
    """

    def walked(self):
        return checker.paragraphs(ET.fromstring(TOP_LEVEL))

    def test_an_unknown_top_level_tag_is_reported_rather_than_dropped(self):
        unplaced = [(text, why[1]) for _, text, why in self.walked() if why is not None]
        texts = [text for text, _ in unplaced]
        self.assertIn("A block tag neither walk has ever seen.", texts)

    def test_the_reason_names_the_tag(self):
        for text, why in [(t, w[1]) for _, t, w in self.walked() if w is not None]:
            if text.startswith("A block tag"):
                self.assertIn("SOMETHINGNEW", why)
                return
        self.fail("the unknown tag was not reported at all")

    def test_the_authority_citation_and_the_editorial_note_are_counted_not_dropped(self):
        # The distinction this change turns on. They are stepped over -- being unplaced fails
        # the run, and an authority citation is not a defect -- but they are counted, and the
        # tally is printed on every run, so nothing goes past in silence (#290).
        tally = []
        checker.paragraphs(ET.fromstring(TOP_LEVEL), tally)
        by_tag = {tag: text for tag, text in tally}
        self.assertIn("CITA", by_tag)
        self.assertTrue(by_tag["CITA"].startswith("Authority:"))
        self.assertIn("EDNOTE", by_tag)
        self.assertIn("redesignated", by_tag["EDNOTE"])
        self.assertIn("HD1", by_tag)
        self.assertIn("HEAD", by_tag)

    def test_a_stepped_over_element_never_fails_the_run_as_unplaced(self):
        unplaced_texts = [text for _, text, why in self.walked() if why is not None]
        self.assertFalse([t for t in unplaced_texts if t.startswith("Authority:")],
                         "an authority citation was reported unplaced, which fails the run")

    def test_the_tally_is_empty_when_a_caller_does_not_ask_for_it(self):
        # `paragraphs(root)` keeps the signature every other call site uses.
        self.assertTrue(checker.paragraphs(ET.fromstring(TOP_LEVEL)))

    def test_the_ordinary_paragraphs_still_have_their_addresses(self):
        indexed = {text: path for path, text, why in self.walked() if why is None}
        self.assertEqual(indexed["(a) An ordinary designated paragraph."],
                         ("B", "2.10", "a"))
        self.assertEqual(indexed["(b) A second designated paragraph, after all of that."],
                         ("B", "2.10", "b"))

    def test_nothing_at_the_top_level_vanishes(self):
        counted = {}
        for _, text, _ in self.walked():
            counted[text] = counted.get(text, 0) + 1
        for text in top_level_text(ET.fromstring(TOP_LEVEL), checker.TOP_LEVEL_PASSED_OVER):
            self.assertIn(text, counted, f"vanished -- {text[:70]!r}")


class TestTheAdapterEnumeratesWhatItCannotAddress(unittest.TestCase):
    """The adapter counts every top-level passage, with a reason where it has no address.

    A unit nothing counts is a unit no sweep can ever report, and a denominator that shrinks to
    what could be read is the opposite of what an inventory is for.

    Mutation: drop the `why` and skip, as before. Both tests fail.
    """

    def units(self):
        return corpus.EcfrXml.__new__(corpus.EcfrXml), ET.fromstring(TOP_LEVEL)

    def enumerated(self):
        adapter, root = self.units()
        adapter.root = root
        section = next(root.iter("DIV8"))
        return adapter._section_units("2.10", section)

    def test_an_unknown_top_level_tag_becomes_a_unit_with_a_reason(self):
        found = [u for u in self.enumerated()
                 if u.text == "A block tag neither walk has ever seen."]
        self.assertEqual(len(found), 1, "the unknown tag was not enumerated")
        self.assertIsNotNone(found[0].unaddressable,
                             "it was enumerated with no reason for having no address")
        self.assertIn("SOMETHINGNEW", found[0].unaddressable)

    def test_the_heading_is_still_its_own_unit(self):
        headings = [u for u in self.enumerated() if u.kind == "heading"]
        self.assertEqual([u.text for u in headings], ["§ 2.10 Top-level shapes."])

    def test_nothing_at_the_top_level_vanishes(self):
        texts = [u.text for u in self.enumerated()]
        for text in top_level_text(ET.fromstring(TOP_LEVEL), corpus.TOP_LEVEL_PASSED_OVER):
            self.assertIn(text, texts, f"vanished -- {text[:70]!r}")


class TestTheInvariantHoldsOnTheCommittedCorpora(unittest.TestCase):
    """Over real corpora, not only the shapes this file's author thought of.

    Mutation: any of the above. `CITA` alone appears 30 times across the committed corpora, so
    this fails loudly on the first of them.
    """

    def test_nothing_vanishes_from_any_committed_corpus(self):
        for path in COMMITTED:
            if not os.path.exists(path):
                self.skipTest(f"{path} is not in this checkout")
            root = ET.parse(path).getroot()
            counted = {}
            for _, text, _ in checker.paragraphs(root):
                counted[text] = counted.get(text, 0) + 1
            for text in top_level_text(root, checker.TOP_LEVEL_PASSED_OVER):
                self.assertIn(text, counted,
                              f"{os.path.basename(path)}: vanished -- {text[:70]!r}")


if __name__ == "__main__":
    unittest.main()
