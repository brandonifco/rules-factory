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
        self.assertEqual(len(unplaced()), 4)
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
    """Mutation: descend into every child of a `DIV8` that holds children of its own.

    The set is a decision, and a set that is "whatever has children" is not one. A `DIV` holds a
    table, whose rows are units of their own (0035).
    """

    def test_a_table_inside_a_wrapper_is_not_flattened_into_the_paragraph_index(self):
        stated = " ".join(text for _, text in indexed())
        self.assertNotIn("(1) Code", stated)
        self.assertNotIn("5 L", stated)

    def test_the_table_is_still_a_table_of_the_section(self):
        # `table_index` reaches it by `.iter`, so descending into the DIV would index its words
        # twice, once as prose with a designation and once as a row.
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
                         ["§ 1.20 ¶24 (d)"])

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
