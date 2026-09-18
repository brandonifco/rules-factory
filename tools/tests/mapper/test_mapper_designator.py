#!/usr/bin/env python3
"""A paragraph that states a compound or unspaced designation opens one, in both walks.

[#289](https://github.com/brandonifco/rules-factory/issues/289). The section locator checker's
`DESIGNATOR` required whitespace after the parenthesised token:

    DESIGNATOR = re.compile(r"^\\(([A-Za-z0-9]{1,4})\\)\\s")

so `(b)(1) Text` and `(b)Text` -- designations a reader sees at once -- opened no designator, and
the paragraph **silently took the designation of the paragraph before it**. `tools/mapper/
corpus.py`'s `EcfrXml.DESIGNATOR` has no `\\s` and never did, so the two halves of one grammar
read the same paragraph differently: one designated, one not.

#288 declined to widen it, on the stated ground that doing so "would move the designation of
paragraphs in corpora this change is not about". **Measured, that ground is empty**: across every
committed eCFR corpus, 850 paragraphs, 696 of them designated, **zero** match the broad
expression and not the narrow one. No committed path moves.

What is watched here:

  * the two expressions are the **same expression** -- the disagreement is the defect, and a test
    is the only thing that can keep them equal, since the two files cannot import one another
    (0032);
  * a compound `(b)(1)` and an unspaced `(b)Text` each **open** a designator rather than
    inheriting the one before them;
  * a compound designation opens only its **first** group, so the paragraph is indexed at an
    *ancestor* of its true address rather than at a wrong sibling. Withholding precision is safe;
    inheriting a neighbour's address is not. Reading `(b)(1)` as two levels would be a new
    mechanism, and no admitted corpus prints the shape -- #265's standard says wait for one that
    forces it;
  * nothing in any committed corpus moves, asserted over the corpora themselves.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import os
import re
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

#: A section printing the two shapes the issue names, each directly after a designated paragraph
#: whose address it would otherwise inherit.
COMPOUND = """<ROOT><DIV6 N="B" TYPE="SUBPART">
<DIV8 N="3.10" TYPE="SECTION"><HEAD>§ 3.10 Compound designations.</HEAD>
<P>(a) An ordinary paragraph, so that a run is open.</P>
<P>(a)(1) A compound designation, printed with no space after the first group.</P>
<P>(b)Text with no space at all after the designator.</P>
<P>(c) A third ordinary paragraph.</P>
</DIV8></DIV6></ROOT>"""

COMMITTED = [
    os.path.join(REPO, "examples", "faa-part-107", "part107.xml"),
    os.path.join(REPO, "examples", "faa-part-107-temporal", "part107-2020-01-01.xml"),
    os.path.join(REPO, "examples", "tax-121-principal-residence", "section-1.121-1.xml"),
    os.path.join(REPO, "examples", "hazmat-172-table", "section-172.101.xml"),
    os.path.join(REPO, "examples", "hazmat-172-table", "section-172.102.xml"),
]


def indexed(fixture):
    return {text: path for path, text, why in checker.paragraphs(ET.fromstring(fixture))
            if why is None}


class TestTheTwoExpressionsAgree(unittest.TestCase):
    """One grammar, one expression for what opens a designator.

    Mutation: put the `\\s` back on either side. `test_the_expressions_are_the_same` fails, and so
    does every placement test below it on the checker's side.
    """

    def test_the_expressions_are_the_same(self):
        self.assertEqual(checker.DESIGNATOR.pattern, corpus.EcfrXml.DESIGNATOR.pattern)

    def test_neither_requires_whitespace_after_the_token(self):
        for name, expression in (("checker", checker.DESIGNATOR),
                                 ("adapter", corpus.EcfrXml.DESIGNATOR)):
            self.assertIsNotNone(expression.match("(b)(1) Text"), f"{name}: compound not matched")
            self.assertIsNotNone(expression.match("(b)Text"), f"{name}: unspaced not matched")
            self.assertIsNotNone(expression.match("(b) Text"), f"{name}: ordinary not matched")

    def test_the_refusal_expression_is_no_broader_than_the_designator(self):
        # `STATES_A_DESIGNATION` was deliberately broader than `DESIGNATOR` only because
        # `DESIGNATOR` was too narrow. With that fixed they agree on what states a designation.
        for probe in ("(b)(1) Text", "(b)Text", "(b) Text"):
            self.assertEqual(bool(checker.STATES_A_DESIGNATION.match(probe)),
                             bool(checker.DESIGNATOR.match(probe)), probe)


class TestACompoundDesignationOpensOne(unittest.TestCase):
    """The defect itself: such a paragraph inherited the address of the one before it.

    Mutation: restore the `\\s`. `(a)(1)` then takes `(a)`'s path by inheritance rather than by
    opening its own, and `(b)Text` takes it too -- so all three of these fail.
    """

    def test_a_compound_designation_is_not_inherited_from_the_paragraph_before(self):
        paths = indexed(COMPOUND)
        compound = paths["(a)(1) A compound designation, printed with no space after the first "
                         "group."]
        self.assertEqual(compound, ("B", "3.10", "a"),
                         "a compound designation should open its first group")

    def test_an_unspaced_designation_opens_its_own_designator(self):
        paths = indexed(COMPOUND)
        self.assertEqual(paths["(b)Text with no space at all after the designator."],
                         ("B", "3.10", "b"))

    def test_the_run_after_them_is_not_displaced(self):
        paths = indexed(COMPOUND)
        self.assertEqual(paths["(c) A third ordinary paragraph."], ("B", "3.10", "c"))

    def test_a_compound_opens_only_its_first_group(self):
        # An ancestor of the true address, never a wrong sibling. Reading `(b)(1)` as two levels
        # is a mechanism no admitted corpus forces (#265).
        paths = indexed(COMPOUND)
        compound = paths["(a)(1) A compound designation, printed with no space after the first "
                         "group."]
        self.assertEqual(len(compound), 3, "only the first group opens a level")


class TestNoCommittedPathMoves(unittest.TestCase):
    """The compatibility claim #288 could not make, now measured rather than assumed.

    Mutation: none needed -- this is the evidence for the change, and it fails if any committed
    corpus turns out to print a shape the two expressions read differently.
    """

    NARROW = re.compile(r"^\(([A-Za-z0-9]{1,4})\)\s")

    def test_no_committed_paragraph_is_read_differently_by_the_two_expressions(self):
        seen = 0
        for path in COMMITTED:
            if not os.path.exists(path):
                self.skipTest(f"{path} is not in this checkout")
            root = ET.parse(path).getroot()
            for section in root.iter("DIV8"):
                for p in section.iter("P"):
                    text = checker.normalise("".join(p.itertext()))
                    if not text:
                        continue
                    seen += 1
                    if checker.DESIGNATOR.match(text) and not self.NARROW.match(text):
                        self.fail(f"{os.path.basename(path)} § {section.get('N')}: widening "
                                  f"moves this paragraph -- {text[:70]!r}")
        self.assertGreater(seen, 600, "the corpora were not actually walked")


if __name__ == "__main__":
    unittest.main()
