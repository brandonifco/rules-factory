#!/usr/bin/env python3
"""A paragraph the corpus prints inside a wrapper is indexed under its enclosing designation.

Both halves of the eCFR grammar walked the **direct** children of a `DIV8`: the section locator
checker's `paragraphs()` and the `ecfr-xml` adapter's `_section_units()`. § 172.102 states its
special provisions as ordinary paragraphs inside an `<EXTRACT>`, which is a *sibling* of those
children, so 12 of the 20 provisions trial 10's seven rows invoke -- `148`, `A3`, `A7`, `A10`,
`B2`, `B16`, `N40`, `TP1`, `TP2`, `TP7`, `TP33`, `W31` -- were in neither the paragraph index nor
a table, and a map could hold the column 7 pointer and not its target
([#285](https://github.com/brandonifco/rules-factory/issues/285),
[#261](https://github.com/brandonifco/rules-factory/issues/261)). Watched here:

  * a paragraph inside a container **is indexed**, under the designation of the paragraph the
    container sits under, so `§ 172.102(c)(2)` names every "A" code and no citation grammar is
    added -- which provision an entry means is settled by its quote, and the checker already
    holds a quote to its citation at *every* occurrence;
  * a nested paragraph **never opens a designator level**, because the eCFR writes the sub-items
    of one provision as `(1)`, `(2)`, `(3)` and letting those into the stack re-designates every
    paragraph of the section after the run;
  * the container set is **closed**: a wrapper not in it is passed over as it always was, and a
    `DIV` holding a table is passed over because a table is addressed by its rows (0035) and
    flattening one into the paragraph index is the reading that decision refused;
  * the **adapter descends into the same set**, so the inventory's denominator holds the units
    the checker can cite. A unit one can reach and the other cannot see is a denominator that
    shrinks to fit what was read, which is the mismatch 0035 was careful to avoid.

The corpus is a synthetic eCFR-shaped fixture written here, in the shape § 172.102 prints. No
real corpus is admitted by this test: that is trial 10's work (#262), not this one's.

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
    from mapper import cli, corpus
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

# § 172.102's shape, at a size a test can read. (c)(1) introduces the numeric provisions and the
# run is an EXTRACT beside it; (c)(2) introduces the "A" codes. Two provisions carry sub-items,
# printed as `(a)`, `(b)` and as `(1)`, `(2)` -- the designator forms § 172.102's own runs print
# (10 × `(1)`, 3 × `(i)`, one each of `(a)` to `(d)`), and the ones that must not reach the
# designator stack. One run holds a table, one holds a MATH with no text of its own, and the
# section ends with a NOTE, which is a wrapper the set deliberately does not name.
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
<MATH/>
</EXTRACT>
<P>(2) "A" codes. These provisions apply only to transportation by aircraft:</P>
<EXTRACT><HD2>Code/Special Provisions</HD2>
<FP-1>A1 Single packagings are not permitted on passenger aircraft.</FP-1>
<FP-1>A3 Glass inner packagings must be packed with absorbent material, if:</FP-1>
<FP1-2>(1) Each inner packaging holds not more than 70 mL; and</FP1-2>
<FP1-2>(2) The vent is not immersed in liquid in any orientation.</FP1-2>
<DIV><TABLE><THEAD><TR><TD>(1) Code</TD><TD>(2) Limit</TD></TR></THEAD>
<TBODY><TR><TD>A3</TD><TD>5 L</TD></TR></TBODY></TABLE></DIV>
</EXTRACT>
<P>(3) "B" codes. These provisions apply only to bulk packagings:</P>
<EXTRACT><HD2>Code/Special Provisions</HD2>
<FP-1>B2 A widget bearing this code must be offered in a cargo tank.</FP-1>
</EXTRACT>
<P>(d) A special provision governs the packaging column of the widget table.</P>
<NOTE><HED>Note to paragraph (d):</HED><P>See § 1.30 for the widget table itself.</P></NOTE>
</DIV8>
</DIV6></ROOT>"""

TABLE_TAKEN = {"section": "§ 1.20", "table": 1, "rows": "all"}


def extent(tables=(TABLE_TAKEN,)):
    return {"unit": "section-designation", "sections": ["§ 1.20"], "tables": list(tables)}


def indexed(fixture=FIXTURE):
    """(path, text) for every paragraph the checker indexes, refusals dropped."""
    return [(path, text) for path, text, bad in
            checker.paragraphs(ET.fromstring(fixture)) if bad is None]


def path_of(opening, fixture=FIXTURE):
    """The designation path of the one indexed paragraph that starts with `opening`."""
    found = [path for path, text in indexed(fixture) if text.startswith(opening)]
    assert len(found) == 1, f"{opening!r} opens {len(found)} indexed paragraphs"
    return found[0]


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

    def test_it_takes_the_designation_of_the_paragraph_the_container_sits_under(self):
        self.assertEqual(path_of("148 "), ("B", "1.20", "c", "1"))
        self.assertEqual(path_of("A1 "), ("B", "1.20", "c", "2"))
        self.assertEqual(path_of("A3 "), ("B", "1.20", "c", "2"))
        self.assertEqual(path_of("B2 "), ("B", "1.20", "c", "3"))

    def test_the_runs_own_heading_is_indexed_at_the_same_address(self):
        headings = [path for path, text in indexed() if text == "Code/Special Provisions"]
        self.assertEqual(headings, [("B", "1.20", "c", "1"), ("B", "1.20", "c", "2"),
                                    ("B", "1.20", "c", "3")])

    def test_a_sub_item_of_a_provision_is_indexed_at_the_provision_s_address(self):
        # `FP1-2` is the sub-item of the provision above it, and it is text of the regulation
        # like any other. It is at the address of the run, because that is the address the
        # provision itself has and the sub-item states no rule of its own.
        self.assertEqual(path_of("(1) Each inner packaging"), ("B", "1.20", "c", "2"))
        self.assertEqual(path_of("(2) The vent"), ("B", "1.20", "c", "2"))

    def test_an_element_with_no_text_enumerates_nothing(self):
        # `MATH` carries no text in this markup -- the formula is an image -- and a unit with no
        # words is one no quote can ever reach.
        self.assertNotIn("", [text for _, text in indexed()])


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


class TestTheContainerSetIsClosed(unittest.TestCase):
    """Mutation: descend into every child of a `DIV8` that holds children of its own.

    The set is a decision, and a set that is "whatever has children" is not one. A `DIV` holds a
    table, whose rows are units of their own (0035); a `NOTE` is a wrapper nothing has been
    measured to need (#265). Both tests fail under the mutation.
    """

    def test_a_table_inside_a_container_is_not_flattened_into_the_paragraph_index(self):
        stated = " ".join(text for _, text in indexed())
        self.assertNotIn("(1) Code", stated)
        self.assertNotIn("5 L", stated)

    def test_the_table_is_still_a_table_of_the_section(self):
        # `table_index` reaches it by `.iter`, so descending into the DIV would index its words
        # twice, once as prose with a designation and once as a row.
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-table-")
        self.addCleanup(shutil.rmtree, directory)
        path = os.path.join(directory, "corpus.xml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(FIXTURE)
        tables = checker.table_index(path)
        self.assertEqual(sorted(tables), [("1.20", 1)])
        self.assertEqual(tables[("1.20", 1)].matching([("1", "A3")]), [["A3", "5 L"]])

    def test_a_wrapper_the_set_does_not_name_is_passed_over_as_it_always_was(self):
        stated = " ".join(text for _, text in indexed())
        self.assertNotIn("See § 1.30 for the widget table itself.", stated)


class TestACitationOfTheEnclosingParagraphNamesIt(unittest.TestCase):
    """The point of the address, end to end through `check`.

    Mutation: drop the `NESTED_CONTAINERS` branch. The quote is then not in the corpus index at
    all and every entry here reports `unchecked` -- which is the state #285 measured: a pointer
    whose target no citation names.
    """

    def setUp(self):
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-check-")
        self.addCleanup(shutil.rmtree, directory)
        self.path = os.path.join(directory, "corpus.xml")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(FIXTURE)
        self.corpus, self.spans, _ = checker.corpus_index(self.path)
        self.tables = checker.table_index(self.path)

    def check(self, citation, evidence):
        entry = {"locator": {"citation": citation}, "evidence": evidence}
        return checker.check(entry, self.corpus, self.spans, tables=self.tables)

    def test_the_enclosing_designation_names_a_nested_provision(self):
        verdict, message = self.check(
            "§ 1.20(c)(2)", "A3 Glass inner packagings must be packed with absorbent material")
        self.assertEqual(verdict, "ok", message)

    def test_it_names_every_provision_of_its_run(self):
        verdict, message = self.check("§ 1.20(c)(2)",
                                      "A1 Single packagings are not permitted")
        self.assertEqual(verdict, "ok", message)

    def test_the_wrong_run_is_refused(self):
        verdict, message = self.check("§ 1.20(c)(3)",
                                      "A1 Single packagings are not permitted")
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
            "(2) The vent is not immersed in liquid in any orientation. "
            '(3) "B" codes. These provisions apply only to bulk packagings:')
        self.assertEqual(verdict, "bad", message)


class TestTheAdapterSeesTheSameParagraphs(unittest.TestCase):
    """Mutation: drop the `NESTED_CONTAINERS` branch from `_section_units()`.

    The checker could then cite a passage the inventory does not count, so the denominator would
    shrink to what was read and a provision nobody looked at would never be reported unaccounted.
    """

    def setUp(self):
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-adapter-")
        self.addCleanup(shutil.rmtree, directory)
        path = os.path.join(directory, "corpus.xml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(FIXTURE)
        self.units = corpus.EcfrXml(path).units(extent())

    def texts(self, kind):
        return [u.text for u in self.units if u.kind == kind]

    def test_a_nested_paragraph_is_a_unit(self):
        self.assertIn("148 A widget bearing this code must be packed in a closed receptacle, "
                      "unless:", self.texts("paragraph"))
        self.assertIn("B2 A widget bearing this code must be offered in a cargo tank.",
                      self.texts("paragraph"))

    def test_the_runs_own_heading_is_a_heading(self):
        self.assertEqual(self.texts("heading").count("Code/Special Provisions"), 3)

    def test_the_numbering_runs_on_through_the_run_and_no_two_units_share_a_key(self):
        keys = [u.key for u in self.units]
        self.assertEqual(len(keys), len(set(keys)))
        # The first run's heading is ¶5 and its four paragraphs ¶6 to ¶9, so the paragraph
        # introducing the next run is ¶10: the section's reading order, with nothing skipped.
        self.assertEqual([u.key for u in self.units if u.text == "Code/Special Provisions"],
                         ["§ 1.20 ¶5 heading", "§ 1.20 ¶11 heading", "§ 1.20 ¶17 heading"])
        self.assertEqual([u.key for u in self.units if u.text.startswith("148 ")],
                         ["§ 1.20 ¶6"])
        self.assertEqual([u.key for u in self.units if u.text.startswith("(d) ")],
                         ["§ 1.20 ¶19 (d)"])

    def test_the_table_inside_the_run_is_still_enumerated_as_rows(self):
        self.assertEqual([u.key for u in self.units if u.kind == "table-row"],
                         ['§ 1.20 table 1, row [column 1 = "(1) Code"]',
                          '§ 1.20 table 1, row [column 1 = "A3"]'])

    def test_a_table_inside_a_run_still_has_to_be_accounted_for(self):
        # 0035's accounting is unchanged by the descent: the table this section prints sits
        # inside an EXTRACT, and an extent that passes over it in silence is still refused.
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-silent-")
        self.addCleanup(shutil.rmtree, directory)
        path = os.path.join(directory, "corpus.xml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(FIXTURE)
        with self.assertRaises(Exception) as caught:
            corpus.EcfrXml(path).units(extent(tables=()))
        self.assertIn("tables", str(caught.exception))


class TestTheTwoWalksAreOneWalk(unittest.TestCase):
    """The checker and the adapter descend into the same wrappers and index the same tags.

    Mutation: add a tag to one set and not the other. Nothing else in the repository would
    notice -- the two files cannot import one another (0032) -- and the result is a unit one
    half can reach and the other cannot see.
    """

    def test_the_container_sets_are_the_same(self):
        self.assertEqual(tuple(checker.NESTED_CONTAINERS), tuple(corpus.NESTED_CONTAINERS))

    def test_the_indexed_tags_are_the_same(self):
        self.assertEqual(set(checker.NESTED_PARAGRAPHS), set(corpus.NESTED_KINDS))

    def test_every_kind_the_adapter_writes_is_a_kind_an_enumeration_may_produce(self):
        for kind in set(corpus.NESTED_KINDS.values()):
            self.assertIn(kind, corpus.KINDS)

    def test_the_two_index_the_same_paragraphs_out_of_the_same_corpus(self):
        directory = tempfile.mkdtemp(prefix="nested-paragraphs-both-")
        self.addCleanup(shutil.rmtree, directory)
        path = os.path.join(directory, "corpus.xml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(FIXTURE)
        units = corpus.EcfrXml(path).units(extent())
        enumerated = [u.text for u in units if u.kind in ("paragraph", "heading")]
        # The section's own HEAD is a unit of the adapter and not of the checker's paragraph
        # tree, which is what it always was; everything else is the same text in the same order.
        self.assertEqual([t for t in enumerated if t != "§ 1.20 Special provisions."],
                         [text for _, text in indexed()])


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
