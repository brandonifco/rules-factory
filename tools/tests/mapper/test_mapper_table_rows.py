#!/usr/bin/env python3
"""A table row is a unit, and the extent says which rows it takes (0035).

Before this, the `ecfr-xml` adapter enumerated a section's `<P>` and `<EXAMPLE>` children and
nothing else, so a table was invisible to every measurement the mapper makes: of § 172.101 --
450,000 characters, 3,687 rows -- the enumeration and the locator checker could see 6.6%
([#261](https://github.com/brandonifco/rules-factory/issues/261)). Watched here:

  * a row of a sliced table is a **unit**, keyed by the citation that names it, so the inventory
    counts a 3,687-row table as 3,687 things to account for and not as one;
  * a row is named by a **cell that identifies it**, and a key matching two rows is **refused**,
    never resolved to the first of them -- 59 of that table's rows are not distinguishable by
    their flattened text;
  * the row's text keeps its **columns**, empty cells included, because 1,112 rows have exactly
    one empty cell and joined into prose a missing symbol and a missing packing group are the
    same absence;
  * **every table of a cited section is accounted for** -- sliced, taken whole, or excluded with
    a reason -- and one the extent passes over in silence is refused, which is 0020's rule that
    a map may not quietly shrink its extent, one unit down;
  * and every way the geometry can fail to say which column a cell is in is a **refusal**: a
    spanned cell, headings that do not number the cells, a section designation printed twice.
    The alternative is an address that is confidently wrong, which is worse than none.

The corpus is a synthetic eCFR-shaped fixture written here. No real corpus is admitted by this
test: that is trial 10's work (#262), not this one's.

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

# The section checker, loaded by path: it is an example's tool and not an importable package,
# and this test holds the two grammars to each other the way test_check_map.py already holds
# CITE_SECTION to the checker's own expression.
SECTION_TOOL = os.path.join(REPO, "examples", "faa-part-107", "check-locators-section.py")
_spec = importlib.util.spec_from_file_location("check_locators_section", SECTION_TOOL)
check_locators_section = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_locators_section)

# Two tables in one section. The first prints a (4) heading split into (4A) and (4B), so its
# columns are the leaves and not the six labels; its first row has an empty column 1, and its
# last two rows are told apart only by column 3. The second is the shape that forces a composite
# key: every value of its first row is printed in another row too, so no one cell and no two
# cells name it.
FIXTURE = """<ROOT><DIV6 N="B" TYPE="SUBPART">
<DIV8 N="1.10" TYPE="SECTION"><HEAD>§ 1.10 Widget table.</HEAD>
<P>Each widget is listed in the widget table with the class and the packing it requires.</P>
<P>(a) Column 1 states the symbol, column 2 the widget name and column 3 the class.</P>
<DIV><TABLE>
<THEAD><TR><TD>(1) Symbols</TD><TD>(2) Widget name</TD><TD>(3) Class</TD><TD>(4) Packing</TD>
<TD>(4A) Exceptions</TD><TD>(4B) Non-bulk</TD></TR></THEAD>
<TBODY>
<TR><TD/><TD>Acetal</TD><TD>3</TD><TD>150</TD><TD>202</TD></TR>
<TR><TD>G</TD><TD>Ammonia, anhydrous</TD><TD>2.2</TD><TD/><TD>306</TD></TR>
<TR><TD>G</TD><TD>Ammonia, anhydrous</TD><TD>2.3</TD><TD>T4</TD><TD>314</TD></TR>
</TBODY></TABLE></DIV>
<TABLE><THEAD><TR><TD>(1) Code</TD><TD>(2) Mode</TD><TD>(3) Limit</TD></TR></THEAD>
<TBODY>
<TR><TD>A3</TD><TD>Aircraft</TD><TD>5 L</TD></TR>
<TR><TD>A3</TD><TD>Aircraft</TD><TD>60 L</TD></TR>
<TR><TD>A3</TD><TD>Vessel</TD><TD>5 L</TD></TR>
<TR><TD>N34</TD><TD>Aircraft</TD><TD>5 L</TD></TR>
</TBODY></TABLE>
</DIV8>
</DIV6></ROOT>"""

# Ten numbered columns with the last split, which is the shape of the table this decision was
# written for: `10A` is a sub-column of `10`, and `1` is a sub-column of nothing. Read as a
# string prefix, `1` is swallowed by `10A` and the table loses its own numbering.
WIDE_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Symbols</TD><TD>(2) Name</TD><TD>(3) Class</TD><TD>(4) ID</TD><TD>(5) PG</TD>
<TD>(6) Label</TD><TD>(7) Provisions</TD><TD>(8) Packaging</TD><TD>(9) Quantity</TD>
<TD>(10) Vessel</TD><TD>(10A) Location</TD><TD>(10B) Other</TD></TR></THEAD>
<TBODY><TR><TD/><TD>Acetal</TD><TD>3</TD><TD>UN1088</TD><TD>II</TD><TD>3</TD><TD>IB2</TD>
<TD>202</TD><TD>5 L</TD><TD>E</TD><TD>D</TD></TR></TBODY></TABLE>"""

SPANNED_TABLE = """<TABLE>
<THEAD><TR><TD COLSPAN="2">(8) Packaging</TD><TD>(9) Quantity</TD></TR></THEAD>
<TBODY><TR><TD>202</TD><TD>242</TD><TD>5 L</TD></TR></TBODY></TABLE>"""

DUPLICATE_LABEL_TABLE = """<TABLE>
<THEAD><TR><TD>(2) Left</TD><TD>(2) Right</TD></TR></THEAD>
<TBODY><TR><TD>near</TD><TD>far</TD></TR></TBODY></TABLE>"""

MISCOUNTED_TABLE = """<TABLE>
<THEAD><TR><TD>(1) One</TD><TD>(2) Two</TD><TD>(3) Three</TD></TR></THEAD>
<TBODY><TR><TD>near</TD><TD>far</TD></TR></TBODY></TABLE>"""

UNLABELLED_TABLE = """<TABLE>
<THEAD><TR><TD>Widget</TD><TD>Limit</TD></TR></THEAD>
<TBODY><TR><TD>Acetal</TD><TD>5 L</TD></TR></TBODY></TABLE>"""

# One table inside another. The inner table's rows are the inner table's.
NESTED_TABLES = """<TABLE>
<THEAD><TR><TD>(1) Code</TD><TD>(2) Meaning</TD></TR></THEAD>
<TBODY><TR><TD>A3</TD><TD>Aircraft only</TD></TR>
<TR><TD>N34</TD><TD><TABLE><THEAD><TR><TD>(1) Mode</TD><TD>(2) Limit</TD></TR></THEAD>
<TBODY><TR><TD>Vessel</TD><TD>60 L</TD></TR></TBODY></TABLE></TD></TR>
</TBODY></TABLE>"""

# Rows told apart by an empty cell, and a row whose only unique cell cannot be written into a
# key. Both are cells a key may name or must pass over, and neither is "identical in every
# column".
EMPTY_CELL_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Widget</TD><TD>(2) Class</TD><TD>(3) Exception</TD></TR></THEAD>
<TBODY><TR><TD>Acetal</TD><TD>3</TD><TD/></TR>
<TR><TD>Acetal</TD><TD>3</TD><TD>T4</TD></TR></TBODY></TABLE>"""

QUOTED_CELL_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Words</TD><TD>(2) Limit</TD></TR></THEAD>
<TBODY><TR><TD>He said "yes"</TD><TD>5 L</TD></TR>
<TR><TD>He said no</TD><TD>60 L</TD></TR></TBODY></TABLE>"""

IDENTICAL_ROWS_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Widget</TD><TD>(2) Class</TD></TR></THEAD>
<TBODY><TR><TD>Acetal</TD><TD>3</TD></TR>
<TR><TD>Acetal</TD><TD>3</TD></TR></TBODY></TABLE>"""

# A section whose only table holds another inside a cell. The inner table is a table of the
# section in its own right: its rows are its own, and the extent has to account for it.
NESTED_FIXTURE = """<ROOT><DIV8 N="1.12" TYPE="SECTION"><HEAD>§ 1.12 Codes.</HEAD>
<P>Each code has the meaning given in the table.</P>
""" + NESTED_TABLES + """
</DIV8></ROOT>"""

ACETAL = {"column": 2, "is": "Acetal"}
AMMONIA_23 = [{"column": 2, "is": "Ammonia, anhydrous"}, {"column": 3, "is": "2.3"}]
ACETAL_ROW = "| Acetal | 3 | 150 | 202"
ACETAL_KEY = '§ 1.10 table 1, row [column 2 = "Acetal"]'
HEADING_KEY = '§ 1.10 table 1, row [column 1 = "(1) Symbols"]'
SECOND_TABLE_EXCLUDED = {"section": "§ 1.10", "table": 2,
                         "excluded": "code meanings; no mapped row invokes one"}


def extent(tables):
    return {"unit": "section-designation", "sections": ["§ 1.10"], "tables": tables}


def table_of(markup):
    """A `Table` over one table's markup, for the geometry cases an extent cannot reach."""
    return corpus.Table("1.10", 1, ET.fromstring(markup))


class AdapterCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="table-rows-test-")
        self.addCleanup(shutil.rmtree, self.directory)
        self.corpus_path = self.write_corpus(FIXTURE)
        self.adapter = corpus.EcfrXml(self.corpus_path)

    def write_corpus(self, text, name="corpus.xml"):
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def units(self, tables):
        return self.adapter.units(extent(tables))

    def rows(self, tables):
        return [u for u in self.units(tables) if u.kind == "table-row"]

    def refusal(self, tables):
        with self.assertRaises(protocol.Refused) as caught:
            self.units(tables)
        return str(caught.exception)


class TestARowIsAUnit(AdapterCase):
    def test_a_sliced_row_is_a_unit_keyed_by_the_citation_that_names_it(self):
        rows = self.rows([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                          SECOND_TABLE_EXCLUDED])
        self.assertEqual([u.key for u in rows], [ACETAL_KEY])
        self.assertEqual(rows[0].kind, "table-row")
        self.assertEqual(rows[0].text, ACETAL_ROW)

    def test_the_rest_of_the_section_is_enumerated_as_it_always_was(self):
        units = self.units([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                            SECOND_TABLE_EXCLUDED])
        self.assertEqual([u.key for u in units if u.kind != "table-row"],
                         ["§ 1.10 heading", "§ 1.10 ¶1", "§ 1.10 ¶2 (a)"])

    def test_a_rows_text_keeps_its_columns_and_its_empty_cells(self):
        key = [{"column": 2, "is": "Ammonia, anhydrous"}, {"column": 3, "is": "2.2"}]
        rows = self.rows([{"section": "§ 1.10", "table": 1, "rows": [key]},
                          SECOND_TABLE_EXCLUDED])
        self.assertEqual(rows[0].text, "G | Ammonia, anhydrous | 2.2 | | 306")

    def test_a_heading_row_is_a_unit_like_any_other_and_is_citable(self):
        # 0035: the column semantics of this corpus live in its headings, and it prints them
        # once for 3,687 rows -- which is exactly the passage a map most needs to cite. A table
        # of nothing but headings would otherwise pass every check by holding no unit at all.
        rows = self.rows([{"section": "§ 1.10", "table": 1,
                           "rows": [{"column": 1, "is": "(1) Symbols"}]},
                          SECOND_TABLE_EXCLUDED])
        self.assertEqual([u.key for u in rows], [HEADING_KEY])
        self.assertEqual(rows[0].text, "(1) Symbols | (2) Widget name | (3) Class | (4) Packing "
                                       "| (4A) Exceptions | (4B) Non-bulk")

    def test_a_whole_table_keys_every_row_by_a_cell_that_identifies_it(self):
        # One column where one will do, taken in the corpus's own column order: the two ammonia
        # rows are told apart by column 3, and the empty column 1 of the Acetal row names
        # nothing, so column 2 does. A key is what identifies the row, never where it sits.
        rows = self.rows([{"section": "§ 1.10", "table": 1, "rows": "all"},
                          SECOND_TABLE_EXCLUDED])
        self.assertEqual([u.key for u in rows], [
            HEADING_KEY,
            ACETAL_KEY,
            '§ 1.10 table 1, row [column 3 = "2.2"]',
            '§ 1.10 table 1, row [column 3 = "2.3"]',
        ])

    def test_a_row_no_two_cells_name_is_keyed_by_three(self):
        # Every value of the first row of table 2 is printed in another row too, and so is every
        # pair of them. A key widens until it names one row; it does not give up at two.
        rows = self.rows([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                          {"section": "§ 1.10", "table": 2, "rows": "all"}])
        self.assertIn('§ 1.10 table 2, row [column 1 = "A3"; column 2 = "Aircraft"; '
                      'column 3 = "5 L"]', [u.key for u in rows])
        for unit in rows:
            with self.subTest(key=unit.key):
                self.assertIsNotNone(check_locators_section.table_citation(unit.key))

    def test_a_key_that_names_two_rows_is_refused(self):
        message = self.refusal([{"section": "§ 1.10", "table": 1,
                                 "rows": [{"column": 2, "is": "Ammonia, anhydrous"}]},
                                SECOND_TABLE_EXCLUDED])
        self.assertIn("names 2 rows", message)

    def test_a_discriminating_column_settles_it(self):
        rows = self.rows([{"section": "§ 1.10", "table": 1, "rows": [AMMONIA_23]},
                          SECOND_TABLE_EXCLUDED])
        self.assertEqual([u.key for u in rows],
                         ['§ 1.10 table 1, row [column 2 = "Ammonia, anhydrous"; '
                          'column 3 = "2.3"]'])

    def test_a_key_that_names_no_row_is_refused(self):
        message = self.refusal([{"section": "§ 1.10", "table": 1,
                                 "rows": [{"column": 2, "is": "Acetaldehyde"}]},
                                SECOND_TABLE_EXCLUDED])
        self.assertIn("names 0 rows", message)


class TestAKeyIsChosenFromCellsThatCanName(unittest.TestCase):
    """`key_for` over the cases a citation has to survive: an empty cell, a quotation mark, and
    two rows nothing tells apart."""

    def test_an_empty_cell_is_a_value_a_key_may_name(self):
        # The whole reason the extraction keeps the columns: a blank cell is a fact about the
        # row, and two rows that differ only in one are not "identical in every column".
        table = table_of(EMPTY_CELL_TABLE)
        self.assertEqual(table.key_for(1), [("3", "")])
        self.assertEqual(table.key_for(2), [("3", "T4")])

    def test_a_cell_holding_a_quotation_mark_is_passed_over(self):
        # A key delimits its values with `"` and defines no escape, so such a cell names
        # nothing -- and another column does.
        table = table_of(QUOTED_CELL_TABLE)
        key = table.key_for(1)
        self.assertEqual(key, [("2", "5 L")])
        self.assertIsNotNone(check_locators_section.table_citation(
            corpus.row_citation("1.10", 1, key)))

    def test_two_rows_alike_in_every_column_have_no_key(self):
        table = table_of(IDENTICAL_ROWS_TABLE)
        self.assertIsNone(table.key_for(1))
        self.assertIsNone(table.key_for(2))


class TestTheGeometryIsReadOrRefused(unittest.TestCase):
    """A column is the corpus's own numbering, and where the markup does not carry it the table
    addresses nothing. An address that is confidently wrong is worse than no address."""

    def test_a_two_digit_column_is_not_a_sub_column_of_column_one(self):
        # The defect this test exists for: read as a string prefix, `1` is a parent of `10A`,
        # 11 leaves come out against a width of 12, the table falls back to positional numbering
        # and `column 9` addresses column 8's cell. Containment is a label plus letters.
        self.assertTrue(corpus.sub_column_of("10", "10A"))
        self.assertFalse(corpus.sub_column_of("1", "10A"))
        table = table_of(WIDE_TABLE)
        self.assertEqual(table.numbering, "printed")
        self.assertEqual(table.columns,
                         ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10A", "10B"])
        self.assertEqual(table.index_of("10B"), 10)
        self.assertEqual(table.matching([("9", "5 L")])[0][1][8], "5 L")

    def test_a_spanned_cell_leaves_the_geometry_unreadable(self):
        table = table_of(SPANNED_TABLE)
        self.assertIn("spans rows or columns", table.unresolved or "")
        self.assertEqual(table.columns, [])

    def test_headings_that_do_not_number_the_cells_are_refused(self):
        table = table_of(MISCOUNTED_TABLE)
        self.assertIn("no heading can be matched to a cell", table.unresolved or "")

    def test_a_label_printed_twice_numbers_the_table_by_position(self):
        table = table_of(DUPLICATE_LABEL_TABLE)
        self.assertIsNone(table.unresolved)
        self.assertEqual(table.numbering, "positional")
        self.assertEqual(table.columns, ["1", "2"])

    def test_a_table_that_prints_no_numbering_is_numbered_by_position(self):
        table = table_of(UNLABELLED_TABLE)
        self.assertEqual(table.numbering, "positional")
        self.assertEqual(table.columns, ["1", "2"])

    def test_a_nested_tables_rows_belong_to_the_nested_table(self):
        outer = table_of(NESTED_TABLES)
        self.assertEqual([cells[0] for cells in outer.rows], ["(1) Code", "A3", "N34"])
        inner = corpus.Table("1.10", 2, ET.fromstring(NESTED_TABLES).iter("TABLE").__next__()
                             .findall(".//TABLE")[0])
        self.assertEqual([cells[0] for cells in inner.rows], ["(1) Mode", "Vessel"])


class TestEveryTableIsAccountedFor(AdapterCase):
    def test_a_table_the_extent_passes_over_in_silence_is_refused(self):
        message = self.refusal([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]}])
        self.assertIn("§ 1.10 table 2 is inside the declared extent", message)

    def test_an_excluded_table_enumerates_nothing_and_accounts_for_itself(self):
        rows = self.rows([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                          SECOND_TABLE_EXCLUDED])
        self.assertEqual([u.key for u in rows], [ACETAL_KEY])

    def test_an_extent_that_names_no_tables_at_all_is_refused(self):
        message = self.refusal(None)
        self.assertIn("§ 1.10 table 1 is inside the declared extent", message)

    def test_a_slice_of_a_section_outside_the_extent_is_refused(self):
        message = self.refusal([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                                SECOND_TABLE_EXCLUDED,
                                {"section": "§ 1.99", "table": 1, "rows": "all"}])
        self.assertIn("which the extent does not cite", message)

    def test_a_slice_of_a_table_the_section_does_not_print_is_refused(self):
        message = self.refusal([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                                SECOND_TABLE_EXCLUDED,
                                {"section": "§ 1.10", "table": 3, "rows": "all"}])
        self.assertIn("prints 2 table(s)", message)

    def test_a_slice_that_both_takes_and_excludes_is_refused(self):
        message = self.refusal([{"section": "§ 1.10", "table": 1, "rows": [ACETAL],
                                 "excluded": "and also excluded"},
                                SECOND_TABLE_EXCLUDED])
        self.assertIn("declares both", message)

    def test_a_nested_table_is_accounted_for_in_its_own_right(self):
        # Its rows are not admitted to the table that encloses it, so taking the outer table
        # whole cannot dispose of it: an inner table is a table of the section, numbered like
        # any other, and the extent has to say what it did with it.
        corpus_path = self.write_corpus(NESTED_FIXTURE, "nested.xml")
        adapter = corpus.EcfrXml(corpus_path)
        with self.assertRaises(protocol.Refused) as caught:
            adapter.units({"unit": "section-designation", "sections": ["§ 1.12"],
                           "tables": [{"section": "§ 1.12", "table": 1, "rows": "all"}]})
        self.assertIn("§ 1.12 table 2 is inside the declared extent", str(caught.exception))

    def test_the_outer_tables_rows_are_only_its_own(self):
        corpus_path = self.write_corpus(NESTED_FIXTURE, "nested-rows.xml")
        adapter = corpus.EcfrXml(corpus_path)
        units = adapter.units({"unit": "section-designation", "sections": ["§ 1.12"],
                               "tables": [{"section": "§ 1.12", "table": 1, "rows": "all"},
                                          {"section": "§ 1.12", "table": 2, "rows": "all"}]})
        rows = [u for u in units if u.kind == "table-row"]
        self.assertEqual([u.key for u in rows], [
            '§ 1.12 table 1, row [column 1 = "(1) Code"]',
            '§ 1.12 table 1, row [column 1 = "A3"]',
            '§ 1.12 table 1, row [column 1 = "N34"]',
            '§ 1.12 table 2, row [column 1 = "(1) Mode"]',
            '§ 1.12 table 2, row [column 1 = "Vessel"]',
        ])

    def test_a_table_whose_geometry_is_unreadable_is_refused_rather_than_addressed(self):
        corpus_path = self.write_corpus(
            FIXTURE.replace("<TABLE><THEAD><TR><TD>(1) Code</TD><TD>(2) Mode</TD>"
                            "<TD>(3) Limit</TD></TR></THEAD>",
                            '<TABLE><THEAD><TR><TD COLSPAN="2">(1) Code</TD><TD>(3) Limit</TD>'
                            '</TR></THEAD>'), "spanned.xml")
        adapter = corpus.EcfrXml(corpus_path)
        with self.assertRaises(protocol.Refused) as caught:
            adapter.units(extent([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                                  {"section": "§ 1.10", "table": 2, "rows": "all"}]))
        self.assertIn("spans rows or columns", str(caught.exception))

    def test_the_same_table_excluded_with_a_reason_needs_no_geometry(self):
        corpus_path = self.write_corpus(
            FIXTURE.replace("<TABLE><THEAD><TR><TD>(1) Code</TD><TD>(2) Mode</TD>"
                            "<TD>(3) Limit</TD></TR></THEAD>",
                            '<TABLE><THEAD><TR><TD COLSPAN="2">(1) Code</TD><TD>(3) Limit</TD>'
                            '</TR></THEAD>'), "spanned-excluded.xml")
        adapter = corpus.EcfrXml(corpus_path)
        rows = adapter.units(extent([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                                     SECOND_TABLE_EXCLUDED]))
        self.assertEqual([u.key for u in rows if u.kind == "table-row"], [ACETAL_KEY])

    def test_a_corpus_that_prints_a_section_twice_is_refused(self):
        # Keeping the last of two is what a dictionary does by itself, and it is silent: the
        # first section's tables leave the corpus, and the accounting passes over them.
        twice = FIXTURE.replace("</DIV6></ROOT>",
                                '<DIV8 N="1.10" TYPE="SECTION"><HEAD>§ 1.10 Again.</HEAD>'
                                "<P>A second printing of the same designation.</P>"
                                "</DIV8></DIV6></ROOT>")
        corpus_path = self.write_corpus(twice, "twice.xml")
        adapter = corpus.EcfrXml(corpus_path)
        with self.assertRaises(protocol.Refused) as caught:
            adapter.units(extent([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                                  SECOND_TABLE_EXCLUDED]))
        self.assertIn("prints § 1.10 twice", str(caught.exception))


class TestTheTwoGrammarsAreOneGrammar(AdapterCase):
    """The adapter writes the citation; the section locator checker reads it. Two files, one
    form -- as CITE_SECTION already is, and for the same reason: they cannot drift silently."""

    def test_every_key_the_adapter_writes_the_checker_reads_back(self):
        rows = self.rows([{"section": "§ 1.10", "table": 1, "rows": "all"},
                          {"section": "§ 1.10", "table": 2, "rows": "all"}])
        self.assertEqual(len(rows), 9)
        for unit in rows:
            with self.subTest(key=unit.key):
                read = check_locators_section.table_citation(unit.key)
                self.assertIsNotNone(read, unit.key)
                section, table, pairs, column = read
                self.assertEqual(section, "1.10")
                self.assertIsNone(column)
                indexed = check_locators_section.table_index(self.corpus_path)[(section, table)]
                self.assertEqual(len(indexed.matching(pairs)), 1)
                self.assertEqual(
                    check_locators_section.row_text(indexed.matching(pairs)[0]), unit.text)

    def test_the_two_read_the_same_columns_out_of_the_same_table(self):
        indexed = check_locators_section.table_index(self.corpus_path)[("1.10", 1)]
        table = corpus.Table("1.10", 1, self.adapter.root.iter("TABLE").__next__())
        self.assertEqual(indexed.columns, table.columns)
        self.assertEqual(indexed.columns, ["1", "2", "3", "4A", "4B"])

    def test_the_two_refuse_the_same_geometry(self):
        for markup in (SPANNED_TABLE, MISCOUNTED_TABLE):
            with self.subTest(markup=markup.split("\n")[0]):
                theirs = check_locators_section.Table("1.10", 1, ET.fromstring(markup))
                self.assertEqual(bool(theirs.unresolved), bool(table_of(markup).unresolved))
                self.assertEqual(theirs.unresolved, table_of(markup).unresolved)


class TestTheProtocolNamesTheUnit(unittest.TestCase):
    def test_table_row_is_a_unit_a_protocol_may_declare(self):
        self.assertIn("table-row", protocol.UNITS)

    def test_table_row_is_a_kind_an_enumeration_may_produce(self):
        self.assertIn("table-row", corpus.KINDS)


class TestAQuoteInARowReachesIt(unittest.TestCase):
    """End to end, through `mapper inventory`: the measurement the units exist for."""

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="table-rows-inventory-")
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
            "extent": extent([{"section": "§ 1.10", "table": 1, "rows": "all"},
                              SECOND_TABLE_EXCLUDED]),
            "entries": [{"id": "acetal-packing", "evidence": evidence}],
        })
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["inventory", self.map_path])
        return code, out.getvalue() + err.getvalue()

    def test_a_quote_of_a_row_reaches_that_row_and_the_others_are_unaccounted(self):
        code, output = self.inventory(ACETAL_ROW)
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("4 table-row", output)
        self.assertIn("reached:     1", output)
        self.assertIn("unaccounted: 6", output)

    def test_a_quote_of_one_cell_still_reaches_its_row(self):
        code, output = self.inventory("| Acetal | 3 |")
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("reached:     1", output)


if __name__ == "__main__":
    unittest.main()
