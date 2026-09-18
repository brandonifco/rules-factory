#!/usr/bin/env python3
"""A paragraph the corpus prints inside a wrapper is indexed under the designation the wrapper
continues, or not at all.

Both halves of the eCFR grammar walked the **direct** children of a `DIV8`: the section locator
checker's `paragraphs()` and the `ecfr-xml` adapter's `_section_units()`. § 172.102 states its
special provisions as ordinary paragraphs inside an `<EXTRACT>`, which is a *sibling* of those
children, so 12 of the 20 provisions trial 10's seven rows invoke -- `148`, `A3`, `A7`, `A10`,
`B2`, `B16`, `N40`, `TP1`, `TP2`, `TP7`, `TP33`, `W31` -- were in neither the paragraph index nor
a table, and a map could hold the column 7 pointer and not its target
([#285](https://github.com/brandonifco/rules-factory/issues/285),
[#261](https://github.com/brandonifco/rules-factory/issues/261)). Watched here:

  * a paragraph inside a wrapper **is indexed**, under the designation of the paragraph the
    wrapper continues, so `§ 172.102(c)(2)` names every "A" code and no citation grammar is
    added -- which provision an entry means is settled by its quote, and the checker already
    holds a quote to its citation at *every* occurrence;
  * a wrapper that is **not** a continuation of the run it sits in is **unplaced**, not
    attributed ([0036](../../../docs/decisions/0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md)):
    one that opens a division of the section, and one whose ordinary paragraph states its own
    designation. Nothing in it is indexed, so no citation resolves into it;
  * a `NOTE` takes the paragraph **it names in its own heading**, where that is where the corpus
    prints it, and is unplaced where the two disagree;
  * the descent is to **any depth**, because one level was silently not enough: a second copy of
    a sentence inside a nested wrapper vanished, and the every-occurrence rule then verified the
    quote against the one copy that was left;
  * a nested paragraph **never opens a designator level**, because the eCFR writes the sub-items
    of one provision as `(a)`, `(b)`, `(1)`, `(2)` -- the same forms the section's own paragraphs
    use -- and letting them into the stack re-designates the rest of the section;
  * the wrapper set is **closed**, and a `DIV` holding a table is not in it, because a table is
    addressed by its rows (0035);
  * the **adapter walks the same wrappers with the same table of tags**, and parts company on
    exactly one thing: a unit key asserts no containment, so the adapter enumerates what the
    checker leaves unplaced and reports it unaccounted rather than dropping it from the
    denominator.

The corpus is a synthetic eCFR-shaped fixture written here, in the shapes § 172.101 and § 172.102
print. No real corpus is admitted by this test: that is trial 10's work (#262), not this one's.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

sys.path.insert(0, TOOLS)
try:
    from mapper import cli, corpus, protocol
finally:
    sys.path.remove(TOOLS)

NOT_VERIFIED = 3

# The section checker, loaded by path: it is an example's tool and not an importable package.
# This test holds the two walks to each other, the way test_mapper_table_rows.py holds the row
# grammar the adapter writes to the parser the checker reads it with.
SECTION_TOOL = os.path.join(REPO, "examples", "faa-part-107", "check-locators-section.py")
_spec = importlib.util.spec_from_file_location("check_locators_section", SECTION_TOOL)
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

# § 172.102's shape and § 172.101's, at a size a test can read.
#
# (c)(1) introduces the numeric provisions and the run is an EXTRACT beside it; (c)(2) introduces
# the "A" codes. Two provisions carry sub-items, printed as `(a)`, `(b)` and `(1)`, `(2)` -- the
# designator forms § 172.102's own runs print (10 x `(1)`, 3 x `(i)`, one each of `(a)` to `(d)`)
# and the ones that must not reach the designator stack. `Shared rule.` is printed twice, once in
# each of two runs under different designations, and the second copy is inside a wrapper nested
# in a wrapper. One run holds a table and a worked example, one holds a MATH with no text.
#
# Then the three shapes that are **not** continuations: a note naming a paragraph it is not
# printed in, a wrapper whose ordinary paragraph states its own designation, and an appendix.
FIXTURE = """<ROOT><DIV6 N="B" TYPE="SUBPART">
<DIV8 N="1.20" TYPE="SECTION"><HEAD>§ 1.20 Special provisions.</HEAD>
<P>A code in column 7 of the widget table is a pointer to the provision of that code here.</P>
<P>(a) A special provision applies to the widget it is assigned to and to no other.</P>
<P>(c) The following special provisions are assigned:</P>
<P>(1) Numeric provisions. These provisions apply to bulk and non-bulk packagings:</P>
<EXTRACT><HD2>Code/Special Provisions</HD2>
<FP-1>148 A widget bearing this code must be packed in a closed receptacle, unless:</FP-1>
<FP1-2>(a) The widget is offered in a cargo tank; or</FP1-2>
<FP1-2>(b) The widget is a solid.</FP1-2>
<FP-1>149 A widget bearing this code is forbidden on a passenger aircraft.</FP-1>
<FP-1>Shared rule.</FP-1>
<MATH/>
</EXTRACT>
<P>(2) "A" codes. These provisions apply only to transportation by aircraft:</P>
<EXTRACT><HD2>Code/Special Provisions</HD2>
<FP-1>A1 Single packagings are not permitted on passenger aircraft.</FP-1>
<FP-1>A3 Glass inner packagings must be packed with absorbent material, if:</FP-1>
<FP1-2>(1) Each inner packaging holds not more than 70 mL; and</FP1-2>
<FP1-2>(2) The vent is not immersed in liquid in any orientation.</FP1-2>
<EXTRACT><FP-1>A4 A run set off inside a run.</FP-1>
<FP-1>Shared rule.</FP-1></EXTRACT>
<EXAMPLE><HED>Example 1.</HED><P>A widget offered by air in a glass ampoule.</P></EXAMPLE>
<DIV><TABLE><THEAD><TR><TD>(1) Code</TD><TD>(2) Limit</TD></TR></THEAD>
<TBODY><TR><TD>A3</TD><TD>5 L</TD></TR></TBODY></TABLE></DIV>
</EXTRACT>
<P>(3) "B" codes. These provisions apply only to bulk packagings:</P>
<EXTRACT><HD2>Code/Special Provisions</HD2>
<FP-1>B2 A widget bearing this code must be offered in a cargo tank.</FP-1>
</EXTRACT>
<NOTE><HED>Note to paragraph (<E T="01">c</E>):</HED>
<P>For samples of a widget, see § 1.30 of this subchapter.</P></NOTE>
<P>(d) A special provision governs the packaging column of the widget table.</P>
<NOTE><HED>Note to paragraph (<E T="01">c</E>)(1):</HED>
<P>The numeric provisions were renumbered in 2019.</P></NOTE>
<EXTRACT><P>(e) A paragraph that designates itself.</P></EXTRACT>
<EXTRACT><HD1>Appendix A to § 1.20—List of widgets</HD1>
<P>1. This appendix lists widgets and the provisions assigned to them.</P></EXTRACT>
</DIV8>
</DIV6></ROOT>"""

# The shapes a review found by construction, none of which either admitted section prints. Each
# one used to vanish or to inherit an address that is not its own; each is now reported. They sit
# in a section of their own so that § 1.20's unit numbering stays readable above.
ODDITIES = """<ROOT>
<DIV8 N="1.21" TYPE="SECTION"><HEAD>§ 1.21 Odd shapes.</HEAD>
<P>(a) A paragraph that introduces a run:</P>
<EXTRACT><FP-1>Alpha rule.</FP-1>
<P>(b)(1) A compound designation, which DESIGNATOR does not match.</P></EXTRACT>
<P>(b) Another paragraph:</P>
<EXTRACT><FP-1>Beta rule.</FP-1>
<P>(c)An unspaced designation, which DESIGNATOR does not match either.</P></EXTRACT>
<P>(c) A third:</P>
<EXTRACT><FP-1>Gamma rule.</FP-1>
<EXAMPLE><HED>Illustration.</HED><P>A head that does not name an example.</P></EXAMPLE>
<FOOTNOTE>A tag this walk has no unit for.</FOOTNOTE></EXTRACT>
<P>(d) A fourth:</P>
<EXTRACT><FP-1>Delta rule.</FP-1>
<NOTE><HED>Note to paragraph (z):</HED>
<P>A note, inside a placed wrapper, naming a paragraph that does not exist.</P></NOTE></EXTRACT>
<P>(e) A fifth:</P>
<NOTE><HED>Note to paragraphs (a) and (1):</HED>
<P>A note naming two paragraphs at once.</P></NOTE>
<P>(f) A sixth:</P>
<NOTE><HED>Note to paragraph (a)(12345):</HED>
<P>A note naming a group this grammar cannot read.</P></NOTE>
<P>(g) A seventh:</P>
<DIV><TABLE><THEAD><TR><TD>(1) Code</TD><TD>(2) Limit</TD></TR></THEAD>
<TBODY><TR><TD>X1</TD><TD>5 L</TD></TR></TBODY></TABLE></DIV>
<EXTRACT><HD2>Appendix C to § 1.21—Odd widgets</HD2>
<P>1. An appendix titled at level two rather than level one.</P></EXTRACT>
</DIV8></ROOT>"""

#: The committed corpora, for the invariant below: a rule measured only on a fixture is a rule
#: measured on the shapes its author thought of.
COMMITTED = [
    os.path.join(REPO, "examples", "faa-part-107", "part107.xml"),
    os.path.join(REPO, "examples", "faa-part-107-temporal", "part107-2020-01-01.xml"),
    os.path.join(REPO, "examples", "tax-121-principal-residence", "section-1.121-1.xml"),
    os.path.join(REPO, "examples", "hazmat-172-table", "section-172.101.xml"),
    os.path.join(REPO, "examples", "hazmat-172-table", "section-172.102.xml"),
]

TABLE_TAKEN = {"section": "§ 1.20", "table": 1, "rows": "all"}


def extent(tables=(TABLE_TAKEN,)):
    return {"unit": "section-designation", "sections": ["§ 1.20"], "tables": list(tables)}


def walked(fixture=FIXTURE):
    """Everything `paragraphs()` returns, placed and unplaced alike."""
    return checker.paragraphs(ET.fromstring(fixture))


def indexed(fixture=FIXTURE):
    """(path, text) for every paragraph the checker gives an address."""
    return [(path, text) for path, text, why in walked(fixture) if why is None]


def unplaced(fixture=FIXTURE):
    """(text, reason) for every paragraph the checker refuses to place."""
    return [(text, why) for path, text, why in walked(fixture) if why is not None]


def reached_by_the_descent(root):
    """Every text-bearing element inside a wrapper, counted **independently of the walk**.

    Written here rather than imported, so that the invariant below is a claim about the corpus
    and not a restatement of the implementation: this traversal knows only which tags are
    wrappers and which hold a table, and it collects everything else that has words in it.
    """
    found = []

    def visit(node, inside):
        for child in node:
            if child.tag in checker.NESTED_CONTAINERS:
                visit(child, True)
            elif child.tag in checker.TABLE_WRAPPERS:
                continue
            elif inside:
                text = checker.normalise("".join(child.itertext()))
                if text:
                    found.append(text)

    for section in root.iter("DIV8"):
        visit(section, False)
    return found


def path_of(opening, fixture=FIXTURE):
    """The designation path of the one indexed paragraph that starts with `opening`."""
    found = [path for path, text in indexed(fixture) if text.startswith(opening)]
    assert len(found) == 1, f"{opening!r} opens {len(found)} indexed paragraphs"
    return found[0]


def written(directory, fixture=FIXTURE):
    path = os.path.join(directory, "corpus.xml")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(fixture)
    return path


class Fixture(unittest.TestCase):
    def corpus_file(self, fixture=FIXTURE, prefix="nested-paragraphs-"):
        directory = tempfile.mkdtemp(prefix=prefix)
        self.addCleanup(shutil.rmtree, directory)
        return written(directory, fixture)


class TestANestedParagraphIsIndexed(unittest.TestCase):
    """Mutation: drop the `NESTED_CONTAINERS` branch from `paragraphs()`.

    That is the code as it stood, and every test in this class fails on it -- each nested
    paragraph is simply absent from the index.
    """

    def test_a_paragraph_inside_a_container_is_in_the_index(self):
        stated = [text for _, text in indexed()]
        self.assertIn("148 A widget bearing this code must be packed in a closed receptacle, "
                      "unless:", stated)
        self.assertIn("B2 A widget bearing this code must be offered in a cargo tank.", stated)

    def test_it_takes_the_designation_of_the_paragraph_the_wrapper_continues(self):
        self.assertEqual(path_of("148 "), ("B", "1.20", "c", "1"))
        self.assertEqual(path_of("A1 "), ("B", "1.20", "c", "2"))
        self.assertEqual(path_of("A3 "), ("B", "1.20", "c", "2"))
        self.assertEqual(path_of("B2 "), ("B", "1.20", "c", "3"))

    def test_the_runs_own_heading_is_indexed_at_the_same_address(self):
        headings = [path for path, text in indexed() if text == "Code/Special Provisions"]
        self.assertEqual(headings, [("B", "1.20", "c", "1"), ("B", "1.20", "c", "2"),
                                    ("B", "1.20", "c", "3")])

    def test_a_sub_item_of_a_provision_is_indexed_at_the_provisions_address(self):
        # `FP1-2` is the sub-item of the provision above it, and it is text of the regulation
        # like any other. It is at the address of the run, because that is the address the
        # provision itself has and the sub-item states no rule of its own.
        self.assertEqual(path_of("(1) Each inner packaging"), ("B", "1.20", "c", "2"))
        self.assertEqual(path_of("(b) The widget is a solid"), ("B", "1.20", "c", "1"))

    def test_an_element_with_no_text_enumerates_nothing(self):
        # `MATH` carries no text in this markup -- the formula is an image -- and a unit with no
        # words is one no quote can ever reach.
        self.assertNotIn("", [text for _, text in indexed()])

    def test_a_worked_example_inside_a_wrapper_keeps_its_label(self):
        # "Already a unit of its own" covered an EXAMPLE that is a direct child of the section.
        # One inside a wrapper is the same rule one level down, and it was omitted.
        self.assertEqual(path_of("Example 1."), ("B", "1.20", "c", "2", "Example 1"))


class TestANestedParagraphOpensNoDesignatorLevel(unittest.TestCase):
    """Mutation: index a nested paragraph through the ordinary `<P>` branch, stack and all.

    The sub-items of a provision are designated `(a)`, `(b)`, `(1)`, `(2)`, `(i)` -- the same
    forms the section's own paragraphs use. Let them into the designator stack and `(b)` closes
    the lettered run that `(c)` opened, so every paragraph after it is read one branch across:
    on the real § 172.102 the mutation puts the "B", "N" and "W" runs at `§ 172.102(d)(3)`,
    `(d)(5)` and `(d)(9)`, which are three paragraphs of the used-battery exception. The first
    two tests here fail under it, and so does the sub-item's own address above; the third holds
    the case the mutation happens to get right, because a rule that is right by luck on one
    paragraph is the reason the other two are worth pinning.
    """

    def test_the_run_after_one_with_lettered_sub_items_keeps_its_designation(self):
        self.assertEqual(path_of('(2) "A" codes'), ("B", "1.20", "c", "2"))

    def test_and_so_does_every_run_after_that(self):
        self.assertEqual(path_of('(3) "B" codes'), ("B", "1.20", "c", "3"))
        self.assertEqual(path_of("B2 "), ("B", "1.20", "c", "3"))

    def test_and_the_paragraph_that_closes_the_section(self):
        self.assertEqual(path_of("(d) A special provision governs"), ("B", "1.20", "d"))


class TestAWrapperThatIsNotAContinuationIsUnplaced(unittest.TestCase):
    """Mutation: return `enclosing` from `wrapper_reach` unconditionally.

    That was this branch's first answer, and Codex reproduced what it costs on the real
    § 172.101: the two appendices are `EXTRACT`s printed after `(l)(3)`, a rule about choosing a
    shipping name, so `check()` accepted `§ 172.101(l)(3)` for evidence quoting Appendix B
    paragraph 2. A citation naming a shipping-name rule that resolves inside an appendix is the
    wrong-passage defect in a new costume. Every test in this class fails under the mutation.
    """

    def reason_for(self, opening):
        found = [why for text, why in unplaced() if text.startswith(opening)]
        self.assertTrue(found, f"{opening!r} was placed, or is not in the corpus at all")
        return found[0]

    def test_a_wrapper_that_opens_a_division_of_the_section_is_unplaced(self):
        self.assertIn("division of the section", self.reason_for("Appendix A to § 1.20"))
        self.assertIn("division of the section", self.reason_for("1. This appendix lists"))

    def test_a_wrapper_whose_paragraph_states_its_own_designation_is_unplaced(self):
        self.assertIn("states its own designation, (e)",
                      self.reason_for("(e) A paragraph that designates itself"))

    def test_an_unplaced_paragraph_is_in_no_index_so_no_citation_reaches_it(self):
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-unplaced-")
        self.addCleanup(shutil.rmtree, directory)
        text, spans, refused = checker.corpus_index(written(directory))
        self.assertNotIn("This appendix lists widgets", text)
        for citation in ("§ 1.20", "§ 1.20(d)", "§ 1.20(c)(3)"):
            verdict, message = checker.check(
                {"locator": {"citation": citation},
                 "evidence": "1. This appendix lists widgets"}, text, spans)
            self.assertEqual(verdict, "unchecked", f"{citation}: {message}")

    def test_every_unplaced_paragraph_is_reported_with_its_reason(self):
        # Not indexed is not the same as passed over: `corpus_index` hands each to `main`, which
        # prints it. A passage the tool cannot address must be visible as one.
        self.assertEqual(len(unplaced()), 5)
        for text, why in unplaced():
            self.assertTrue(why and text)


class TestANoteTakesTheParagraphItNames(unittest.TestCase):
    """Mutation: drop `note_reach` and let a NOTE inherit like any other wrapper.

    § 172.101's note is printed after `(c)(11)(iii)(C)` and its heading says
    `Note to paragraph (c)(11):`. Inheriting files it under the deepest designator that happens
    to be open, which is narrower than the corpus's own word about where it belongs.
    """

    def test_a_note_is_indexed_at_the_paragraph_its_heading_names(self):
        self.assertEqual(path_of("For samples of a widget"), ("B", "1.20", "c"))

    def test_a_note_naming_a_paragraph_it_is_not_printed_in_is_unplaced(self):
        found = [why for text, why in unplaced() if text.startswith("The numeric provisions")]
        self.assertTrue(found)
        self.assertIn("which is not where the corpus prints it", found[0])

    def test_the_note_was_not_merely_unaccounted_before_this_it_was_invisible(self):
        stated = [text for _, text in indexed()]
        self.assertIn("For samples of a widget, see § 1.30 of this subchapter.", stated)


class TestTheDescentGoesToAnyDepth(unittest.TestCase):
    """Mutation: walk `container`'s direct children instead of recursing in `wrapped_elements`.

    Codex's reproduction, and the sharpest of the findings: the second copy of a repeated
    sentence sat inside a wrapper nested in a wrapper, so it disappeared from the index, and the
    check that exists precisely to stop a quote being verified against the wrong one of two
    copies reported one occurrence and passed. Both tests here fail under it -- the second by
    returning `ok`.
    """

    def setUp(self):
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-depth-")
        self.addCleanup(shutil.rmtree, directory)
        self.corpus, self.spans, _ = checker.corpus_index(written(directory))

    def test_a_wrapper_inside_a_wrapper_is_indexed_at_the_outer_wrappers_address(self):
        self.assertEqual(path_of("A4 A run set off inside a run"), ("B", "1.20", "c", "2"))

    def test_both_copies_of_a_repeated_sentence_are_in_the_index(self):
        self.assertEqual([path for path, text in indexed() if text == "Shared rule."],
                         [("B", "1.20", "c", "1"), ("B", "1.20", "c", "2")])


class TestEveryOccurrenceIsHeldToTheCitation(unittest.TestCase):
    """Mutation: `occurrences(...)` -> `occurrences(...)[:1]` in `check`.

    The rule this file's header calls the second deliberate difference from the page checker. The
    tests above exercise it only where one occurrence exists, and Codex made that mutation with
    every end-to-end test still passing. These two fail under it, and under the one-level walk.
    """

    def setUp(self):
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-occurrences-")
        self.addCleanup(shutil.rmtree, directory)
        self.corpus, self.spans, _ = checker.corpus_index(written(directory))

    def check(self, citation, evidence):
        return checker.check({"locator": {"citation": citation}, "evidence": evidence},
                             self.corpus, self.spans)

    def test_a_sentence_printed_in_two_runs_is_refused_at_either_one(self):
        for citation in ("§ 1.20(c)(1)", "§ 1.20(c)(2)"):
            verdict, message = self.check(citation, "Shared rule.")
            self.assertEqual(verdict, "bad", f"{citation}: {message}")
            self.assertIn("occurrence", message)

    def test_and_accepted_at_the_paragraph_that_contains_both(self):
        verdict, message = self.check("§ 1.20(c)", "Shared rule.")
        self.assertEqual(verdict, "ok", message)
        self.assertIn("2 occurrence(s)", message)


class TestTheWrapperSetIsClosed(unittest.TestCase):
    """Mutation: name a table a run of paragraphs -- `DIV`/`TABLE`/`TR` as wrappers and `TD` as a
    paragraph, in both tables at once so they stay equal.

    That is the reading 0035 refused, and it is what an open set slides into: a table's rows are
    units of their own, and a cell flattened into the paragraph index is addressed twice and
    quotable as prose.
    """

    def test_a_table_inside_a_wrapper_is_not_flattened_into_the_paragraph_index(self):
        stated = " ".join(text for _, text in indexed())
        self.assertNotIn("(1) Code", stated)
        self.assertNotIn("5 L", stated)

    def test_the_table_is_still_a_table_of_the_section(self):
        # `table_index` reaches it by `.iter` whatever this walk does, so descending into the DIV
        # indexes its words twice: once as prose with a designation and once as a row.
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-table-")
        self.addCleanup(shutil.rmtree, directory)
        tables = checker.table_index(written(directory))
        self.assertEqual(sorted(tables), [("1.20", 1)])
        self.assertEqual(tables[("1.20", 1)].matching([("1", "A3")]), [["A3", "5 L"]])


class TestACitationOfTheEnclosingParagraphNamesIt(unittest.TestCase):
    """The point of the address, end to end through `check`.

    Mutation: drop the `NESTED_CONTAINERS` branch. The quote is then not in the corpus index at
    all and every entry here reports `unchecked` -- which is the state #285 measured: a pointer
    whose target no citation names.
    """

    def setUp(self):
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-check-")
        self.addCleanup(shutil.rmtree, directory)
        path = written(directory)
        self.corpus, self.spans, _ = checker.corpus_index(path)
        self.tables = checker.table_index(path)

    def check(self, citation, evidence):
        entry = {"locator": {"citation": citation}, "evidence": evidence}
        return checker.check(entry, self.corpus, self.spans, tables=self.tables)

    def test_the_enclosing_designation_names_a_nested_provision(self):
        verdict, message = self.check(
            "§ 1.20(c)(2)", "A3 Glass inner packagings must be packed with absorbent material")
        self.assertEqual(verdict, "ok", message)

    def test_it_names_every_provision_of_its_run(self):
        verdict, message = self.check("§ 1.20(c)(2)", "A1 Single packagings are not permitted")
        self.assertEqual(verdict, "ok", message)

    def test_the_wrong_run_is_refused(self):
        verdict, message = self.check("§ 1.20(c)(3)", "A1 Single packagings are not permitted")
        self.assertEqual(verdict, "bad", message)
        self.assertIn("1.20/c/2", message)

    def test_the_whole_section_names_it_too(self):
        verdict, message = self.check("§ 1.20", "B2 A widget bearing this code")
        self.assertEqual(verdict, "ok", message)

    def test_a_quote_that_runs_past_the_run_is_refused(self):
        # Two paragraphs of two different runs are two paragraphs: the index joins them with one
        # space, and a citation of one of them does not contain the other.
        verdict, message = self.check(
            "§ 1.20(c)(2)",
            'Code/Special Provisions B2 A widget bearing this code must be offered in a cargo '
            'tank.')
        self.assertEqual(verdict, "bad", message)


class TestTheAdapterSeesTheSameParagraphs(unittest.TestCase):
    """Mutation: drop the `NESTED_CONTAINERS` branch from `_section_units()`.

    The checker could then cite a passage the inventory does not count, so the denominator would
    shrink to what was read and a provision nobody looked at would never be reported unaccounted.
    """

    def setUp(self):
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-adapter-")
        self.addCleanup(shutil.rmtree, directory)
        self.units = corpus.EcfrXml(written(directory)).units(extent())

    def texts(self, kind):
        return [u.text for u in self.units if u.kind == kind]

    def test_a_nested_paragraph_is_a_unit(self):
        self.assertIn("148 A widget bearing this code must be packed in a closed receptacle, "
                      "unless:", self.texts("paragraph"))
        self.assertIn("B2 A widget bearing this code must be offered in a cargo tank.",
                      self.texts("paragraph"))

    def test_the_runs_own_heading_is_a_heading(self):
        self.assertEqual(self.texts("heading").count("Code/Special Provisions"), 3)

    def test_a_worked_example_inside_a_wrapper_is_a_worked_example(self):
        self.assertEqual(self.texts("worked-example"),
                         ["Example 1.A widget offered by air in a glass ampoule."])

    def test_what_the_checker_leaves_unplaced_is_still_counted_here(self):
        # The one place the two walks part company, and deliberately: a unit key asserts reading
        # order, not containment, so a passage with no address is enumerated and reported
        # unaccounted rather than dropped out of the denominator.
        self.assertIn("1. This appendix lists widgets and the provisions assigned to them.",
                      self.texts("paragraph"))
        self.assertIn("Appendix A to § 1.20—List of widgets", self.texts("heading"))

    def test_the_numbering_runs_on_through_the_wrappers_and_no_two_units_share_a_key(self):
        keys = [u.key for u in self.units]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual([u.key for u in self.units if u.text == "Code/Special Provisions"],
                         ["§ 1.20 ¶5 heading", "§ 1.20 ¶12 heading", "§ 1.20 ¶21 heading"])
        self.assertEqual([u.key for u in self.units if u.text.startswith("148 ")], ["§ 1.20 ¶6"])
        self.assertEqual([u.key for u in self.units if u.text.startswith("(d) ")],
                         ["§ 1.20 ¶25 (d)"])

    def test_the_table_inside_the_wrapper_is_still_enumerated_as_rows(self):
        self.assertEqual([u.key for u in self.units if u.kind == "table-row"],
                         ['§ 1.20 table 1, row [column 1 = "(1) Code"]',
                          '§ 1.20 table 1, row [column 1 = "A3"]'])

    def test_a_table_inside_a_wrapper_still_has_to_be_accounted_for(self):
        # 0035's accounting is unchanged by the descent: the table this section prints sits
        # inside an EXTRACT, and an extent that passes over it in silence is still refused.
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-silent-")
        self.addCleanup(shutil.rmtree, directory)
        with self.assertRaises(protocol.Refused) as caught:
            corpus.EcfrXml(written(directory)).units(extent(tables=()))
        self.assertIn("tables", str(caught.exception))


class TestTheTwoWalksAreOneWalk(unittest.TestCase):
    """The checker and the adapter descend into the same wrappers and name the same tags.

    Mutation: add a tag to one table and not the other, or a wrapper to one set and not the
    other. Nothing else in the repository would notice -- the two files cannot import one
    another (0032) -- and the result is a passage one half can cite and the other cannot count.
    """

    def test_the_wrapper_sets_are_the_same(self):
        self.assertEqual(tuple(checker.NESTED_CONTAINERS), tuple(corpus.NESTED_CONTAINERS))

    def test_the_tables_of_tags_are_the_same(self):
        self.assertEqual(checker.NESTED_UNITS, corpus.NESTED_KINDS)

    def test_every_kind_the_table_names_is_one_an_enumeration_may_produce(self):
        for kind in set(corpus.NESTED_KINDS.values()):
            self.assertIn(kind, corpus.KINDS)

    def test_the_two_reach_the_same_paragraphs_out_of_the_same_corpus(self):
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-both-")
        self.addCleanup(shutil.rmtree, directory)
        units = corpus.EcfrXml(written(directory)).units(extent())
        enumerated = [u.text for u in units if u.kind != "table-row"]
        # The section's own HEAD is a unit of the adapter and not of the checker's paragraph
        # tree, which is what it always was. Everything else is the same text in the same order,
        # placed and unplaced together: the checker reaches every passage the adapter counts, and
        # says of each either where it is or why it has no address.
        self.assertEqual([t for t in enumerated if t != "§ 1.20 Special provisions."],
                         [text for _, text, _ in walked()])


class TestTheWalkLosesNothing(unittest.TestCase):
    """The invariant, over the committed corpora and both fixtures.

    Every text-bearing element the descent reaches is **indexed or reported unplaced**. This is
    worth more than any of the individual shapes below it, because each of those was found by
    construction and the next one will be too: an element that vanishes is a second copy of a
    quote nobody counts, and the every-occurrence rule then verifies that quote against whichever
    copy survived -- the hole this branch closed once already.

    Mutation: `continue` instead of reporting, on any of the three branches of `wrapped` that
    have no unit to give -- an unrecognised tag, an example with no label, an element inside an
    unplaced wrapper. Each makes this fail on the fixture that carries the shape.

    Scope, said plainly: the claim is about what the **descent into a wrapper** reaches. A
    section's direct `CITA`, `EDNOTE` and `HD1` children are passed over as they always were,
    which is older than this change and is #290.
    """

    def assert_nothing_vanished(self, root, where):
        # Everything the descent reaches must come back from the walk, placed or unplaced. The
        # walk also carries the section's own top-level paragraphs, so this is containment with
        # multiplicity rather than equality.
        counted = {}
        for _, text, _ in checker.paragraphs(root):
            counted[text] = counted.get(text, 0) + 1
        for text in sorted(reached_by_the_descent(root)):
            self.assertIn(text, counted, f"{where}: vanished -- {text[:70]!r}")
            counted[text] -= 1
            self.assertGreaterEqual(counted[text], 0, f"{where}: counted too few -- {text[:70]!r}")

    def test_nothing_vanishes_from_either_fixture(self):
        for name, fixture in (("FIXTURE", FIXTURE), ("ODDITIES", ODDITIES)):
            self.assert_nothing_vanished(ET.fromstring(fixture), name)

    def test_nothing_vanishes_from_any_committed_corpus(self):
        for path in COMMITTED:
            self.assert_nothing_vanished(ET.parse(path).getroot(), os.path.basename(path))

    def test_the_committed_corpora_exercise_the_descent_at_all(self):
        # A containment test over corpora with no wrapper proves nothing, so this says which
        # ones carry the shape: only the two hazmat sections do, with 574 wrapped elements in
        # § 172.102 and 16 in § 172.101 -- the two appendices and the note.
        counts = {os.path.basename(p): len(reached_by_the_descent(ET.parse(p).getroot()))
                  for p in COMMITTED}
        self.assertEqual(counts["part107.xml"], 0)
        self.assertEqual(counts["section-1.121-1.xml"], 0)
        self.assertEqual(counts["section-172.102.xml"], 574)
        self.assertEqual(counts["section-172.101.xml"], 16)


class TestNothingSlipsThroughInheritance(unittest.TestCase):
    """The shapes a review found by construction; every one used to be attributed or to vanish.

    Mutation for the first two: use `DESIGNATOR` for the refusal test instead of
    `STATES_A_DESIGNATION`. `DESIGNATOR` requires whitespace after the first parenthesised token,
    so `(b)(1) Text` and `(b)Text` slip past it and inherit an address that is not their own.
    That expression drives the whole section's designator tree and is deliberately **not**
    widened here (#289); the refusal test is a separate, broader expression, because refusing too
    widely only withholds an address while inheriting too widely hands out a wrong one.
    """

    def reason_for(self, opening):
        found = [why for text, why in unplaced(ODDITIES) if text.startswith(opening)]
        self.assertTrue(found, f"{opening!r} was placed, or is not in the corpus at all")
        return found[0]

    def test_a_compound_designation_is_a_designation(self):
        self.assertIn("states its own designation, (b)", self.reason_for("Alpha rule."))

    def test_an_unspaced_designation_is_a_designation(self):
        self.assertIn("states its own designation, (c)", self.reason_for("Beta rule."))

    def test_an_example_whose_head_names_no_example_is_reported(self):
        # Mutation: `continue` instead of reporting. It then vanishes, and a second copy of any
        # sentence in it is invisible to the every-occurrence rule.
        self.assertIn("head does not name an example", self.reason_for("Illustration."))

    def test_an_element_this_walk_has_no_unit_for_is_reported(self):
        self.assertIn("no unit for a <FOOTNOTE>", self.reason_for("A tag this walk has no unit"))

    def test_the_wrapper_around_them_is_unplaced_whole(self):
        # The refusal is of the wrapper, not of the offending paragraph alone: a run one of whose
        # paragraphs designates itself is not a run the paragraph before it continues.
        self.assertIn("states its own designation", self.reason_for("Alpha rule."))
        self.assertEqual([p for p, t in indexed(ODDITIES) if t == "Alpha rule."], [])


class TestAttributionIsAskedAtEveryDepth(unittest.TestCase):
    """Mutation: evaluate `wrapper_reach` once, for the outermost wrapper, and let recursion
    carry that answer down unchecked.

    That is last round's descent defect in its other half: the walk reached every depth and the
    *check* did not, so a `NOTE` nested inside a placed `EXTRACT` whose heading names a paragraph
    that does not exist was attributed to the enclosing run.
    """

    def test_a_note_nested_in_a_placed_wrapper_is_judged_on_its_own(self):
        found = [why for text, why in unplaced(ODDITIES) if text.startswith("A note, inside")]
        self.assertTrue(found, "the nested note was attributed rather than judged")
        self.assertIn("which is not where the corpus prints it", found[0])

    def test_and_the_wrapper_around_it_is_still_placed(self):
        self.assertEqual(path_of("Delta rule.", ODDITIES), (None, "1.21", "d"))


class TestANoteHeadingNamesOneParagraphOrNone(unittest.TestCase):
    """Mutation: read the heading with `CITE_GROUP.findall` over the whole string.

    `findall` concatenates `Note to paragraphs (a) and (1):` into the single path `(a)(1)`, which
    names a paragraph nobody wrote, and silently drops the unreadable group from
    `Note to paragraph (a)(12345):`, attributing the note to `(a)`. The heading is now parsed as
    a whole address or refused, which is the rule a row key already has (0035): a key that
    resolves to two rows is never resolved to the first of them.
    """

    def reason_for(self, opening):
        found = [why for text, why in unplaced(ODDITIES) if text.startswith(opening)]
        self.assertTrue(found, f"{opening!r} was placed")
        return found[0]

    def test_a_heading_naming_two_paragraphs_is_refused(self):
        self.assertIn("names no single paragraph", self.reason_for("A note naming two"))

    def test_a_heading_naming_a_group_the_grammar_cannot_read_is_refused(self):
        self.assertIn("names no single paragraph", self.reason_for("A note naming a group"))

    def test_a_heading_that_does_name_one_paragraph_still_works(self):
        self.assertEqual(path_of("For samples of a widget"), ("B", "1.20", "c"))


class TestADivisionIsRecognisedWithoutReadingItsTag(unittest.TestCase):
    """Mutation: drop the captioned-and-continues-nothing test, leaving only the `HD1` one.

    The tag-literal test alone is true of every division the admitted corpora print and of no
    other, but it is a statement about a tag rather than about a shape, and a review titled an
    appendix with an `HD2` to show it. The second test is level-agnostic: a wrapper that carries
    a caption and is not printed after a designated paragraph continues nothing.

    Computing "the outermost heading level this section prints" instead, which is what the review
    proposed, would refuse all six of § 172.102's captioned provision runs -- that section prints
    no `HD1` at all, so its outermost level is 2 -- and 0036 records why that is not the rule.
    """

    def test_an_appendix_titled_at_level_two_is_still_a_division(self):
        found = [why for text, why in unplaced(ODDITIES)
                 if text.startswith("Appendix C to § 1.21")]
        self.assertTrue(found, "the HD2-titled appendix was attributed")
        self.assertIn("is not a designated paragraph", found[0])

    def test_and_a_captioned_run_after_its_own_paragraph_is_not(self):
        # All six of § 172.102's captioned runs are this shape, so the test above must not catch
        # them: `Code/Special Provisions` follows the paragraph that introduces the run.
        self.assertEqual(path_of("A1 "), ("B", "1.20", "c", "2"))
        self.assertEqual([t for t, _ in unplaced() if t == "Code/Special Provisions"], [])


class TestTheInventoryCarriesPlacement(unittest.TestCase):
    """Mutation: drop `Unit.unaddressable`, or stop setting it in `wrapped_elements`.

    Enumerated 3, reached 3, unaccounted 0, exit 0 -- for a section whose appendix the checker
    refuses to place. A unit no citation can resolve into must never be counted as accounted for
    by a quotation of it: the locator run would report that entry unchecked and fail, and the two
    tools would disagree about the same passage with the inventory the more forgiving of the two.
    """

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="nested-paragraphs-placement-")
        self.addCleanup(shutil.rmtree, self.directory)
        self.write("corpus.xml", ODDITIES, raw=True)
        self.write("corpus-manifest.json", {
            "schemaVersion": 1,
            "corpora": [{"sourceId": "fixture", "adapter": "ecfr-xml",
                         "committedPath": "corpus.xml", "verification": "committed-copy"}],
        })
        self.map_path = os.path.join(self.directory, "corpus-map.json")

    def write(self, name, content, raw=False):
        with open(os.path.join(self.directory, name), "w", encoding="utf-8") as handle:
            handle.write(content) if raw else json.dump(content, handle)

    def inventory(self, evidence):
        self.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": {"unit": "section-designation", "sections": ["§ 1.21"],
                       "tables": [{"section": "§ 1.21", "table": 1, "rows": "all"}]},
            "entries": [{"id": "an-entry", "evidence": evidence}],
        })
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["inventory", self.map_path, "--list"])
        return code, out.getvalue() + err.getvalue()

    def test_a_unit_with_no_address_is_enumerated_and_said_out_loud(self):
        code, output = self.inventory("(a) A paragraph that introduces a run:")
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("no address:", output)
        self.assertIn("no citation can resolve into", output)

    def test_quoting_one_is_a_failure_not_coverage(self):
        code, output = self.inventory("Appendix C to § 1.21—Odd widgets")
        self.assertEqual(code, 1, output)
        self.assertIn("not coverage of it", output)

    def test_what_the_adapter_calls_unaddressable_the_checker_leaves_unplaced(self):
        # The one place the two walks part company, pinned in the direction that is safe: the
        # adapter builds no designator tree, so it decides the three tests that need no path and
        # not the fourth. Everything it refuses, the checker refuses; not the reverse.
        for fixture in (FIXTURE, ODDITIES):
            path = os.path.join(self.directory, "one.xml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(fixture)
            adapter = corpus.EcfrXml(path)
            refused = set()
            for number, section in adapter._sections().items():
                for unit in adapter._section_units(number, section):
                    if unit.unaddressable:
                        refused.add(unit.text)
            unplaced_here = {text for text, _ in unplaced(fixture)}
            self.assertTrue(refused <= unplaced_here,
                            f"the adapter refuses more than the checker: "
                            f"{sorted(refused - unplaced_here)[:3]}")

    def test_and_every_committed_corpus_agrees_the_same_way(self):
        for path in COMMITTED:
            adapter = corpus.EcfrXml(path)
            refused = set()
            for number, section in adapter._sections().items():
                for unit in adapter._section_units(number, section):
                    if unit.unaddressable:
                        refused.add(unit.text)
            unplaced_here = {text for text, _ in
                             unplaced(open(path, encoding="utf-8").read())}
            self.assertTrue(refused <= unplaced_here, os.path.basename(path))


class TestAQuoteInANestedParagraphReachesIt(unittest.TestCase):
    """End to end, through `mapper inventory`: the measurement the units exist for."""

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="nested-paragraphs-inventory-")
        self.addCleanup(shutil.rmtree, self.directory)
        self.write("corpus.xml", FIXTURE, raw=True)
        self.write("corpus-manifest.json", {
            "schemaVersion": 1,
            "corpora": [{"sourceId": "fixture", "adapter": "ecfr-xml",
                         "committedPath": "corpus.xml", "verification": "committed-copy"}],
        })
        self.map_path = os.path.join(self.directory, "corpus-map.json")

    def write(self, name, content, raw=False):
        with open(os.path.join(self.directory, name), "w", encoding="utf-8") as handle:
            handle.write(content) if raw else json.dump(content, handle)

    def inventory(self, evidence):
        self.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": extent(),
            "entries": [{"id": "a3-absorbent", "evidence": evidence}],
        })
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["inventory", self.map_path])
        return code, out.getvalue() + err.getvalue()

    def test_a_quote_of_a_nested_provision_reaches_its_unit(self):
        code, output = self.inventory(
            "A3 Glass inner packagings must be packed with absorbent material, if:")
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("reached:     1", output)

    def test_the_provisions_nobody_quoted_are_reported_unaccounted(self):
        # The measurement #285 is about: before this, a special provision was in no denominator
        # at all, so a map that never looked at one was not reported as having missed it.
        code, output = self.inventory("B2 A widget bearing this code must be offered in a "
                                      "cargo tank.")
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("148 A widget bearing this code", output)


if __name__ == "__main__":
    unittest.main()
