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
    from mapper import cli, corpus, inventory, protocol
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

TWO_LEVEL_TABLE = """<TABLE>
<THEAD>
<TR><TH ROWSPAN="2">(1)Symbols</TH><TH ROWSPAN="2">(2)Hazardous materials descriptions and \
proper shipping names</TH><TH ROWSPAN="2">(3)Hazard class or Division</TH>
<TH ROWSPAN="2">(4)Identification Numbers</TH><TH ROWSPAN="2">(5)PG</TH>
<TH ROWSPAN="2">(6)Label codes</TH><TH ROWSPAN="2">(7)Special provisions(§ 172.102)</TH>
<TH COLSPAN="3">(8)Packaging(§ 173.***)</TH><TH COLSPAN="2">(9)Quantity limitations</TH>
<TH COLSPAN="2">(10)Vesselstowage</TH></TR>
<TR><TH>Exceptions(8A)</TH><TH>Non-bulk(8B)</TH><TH>Bulk(8C)</TH>
<TH>Passenger aircraft/rail(9A)</TH><TH>Cargo aircraft only(9B)</TH><TH>Location(10A)</TH>
<TH>Other(10B)</TH></TR>
</THEAD>
<TBODY>
<TR><TD/><TD>Acetal</TD><TD>3</TD><TD>UN1088</TD><TD>II</TD><TD>3</TD><TD>IB2, T4, TP1</TD>
<TD>150</TD><TD>202</TD><TD>242</TD><TD>5 L</TD><TD>60 L</TD><TD>E</TD><TD/></TR>
<TR><TD>D</TD><TD>Acetaldehyde</TD><TD>3</TD><TD>UN1089</TD><TD>I</TD><TD>3</TD><TD>A3, T11</TD>
<TD>None</TD><TD>201</TD><TD>243</TD><TD>Forbidden</TD><TD>30 L</TD><TD>E</TD><TD/></TR>
</TBODY></TABLE>"""

# A span in a *body* row: the markup then genuinely stops saying which column a later cell is in.
SPANNED_BODY_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Code</TD><TD>(2) Mode</TD><TD>(3) Limit</TD></TR></THEAD>
<TBODY><TR><TD COLSPAN="2">A3, aircraft</TD><TD>5 L</TD></TR></TBODY></TABLE>"""

# A colspan parent with no second heading row under it: the two columns it covers are both
# labelled `(8)`, which names neither, so the table is numbered by position.
SPANNED_TABLE = """<TABLE>
<THEAD><TR><TD COLSPAN="2">(8) Packaging</TD><TD>(9) Quantity</TD></TR></THEAD>
<TBODY><TR><TD>202</TD><TD>242</TD><TD>5 L</TD></TR></TBODY></TABLE>"""

# A heading that names two columns at once, and one that names none while its neighbours do.
CROWDED_HEADING_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Code and (2) Mode</TD><TD>(3) Limit</TD></TR></THEAD>
<TBODY><TR><TD>A3</TD><TD>5 L</TD></TR></TBODY></TABLE>"""

HALF_NUMBERED_TABLE = """<TABLE>
<THEAD><TR><TD>Widget</TD><TD>(2) Class</TD></TR></THEAD>
<TBODY><TR><TD>Acetal</TD><TD>3</TD></TR></TBODY></TABLE>"""

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

# A table that ends with a footnote row spanning its whole width, which is how every printed
# regulation ends one; a row that spans *part* of its width, which displaces every cell after it;
# a cell carried into the row below; and a heading whose parenthesised token is a footnote marker.
FOOTNOTE_ROW_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Widget</TD><TD>(2) Limit</TD></TR></THEAD>
<TBODY><TR><TD>Acetal</TD><TD>5 L</TD></TR>
<TR><TD COLSPAN="2">1 The RQ applies to the whole entry.</TD></TR></TBODY></TABLE>"""

# A heading where the colspan is load-bearing: the cell *after* the split parent starts where
# the parent's width says it does, so reading the span as one column puts column 5 in the middle
# of the packaging columns instead of after them.
SPLIT_PARENT_TABLE = """<TABLE>
<THEAD>
<TR><TD ROWSPAN="2">(1) Symbols</TD><TD COLSPAN="2">(2) Packaging</TD>
<TD ROWSPAN="2">(5) Stowage</TD></TR>
<TR><TD>Exceptions(2A)</TD><TD>Bulk(2B)</TD></TR>
</THEAD>
<TBODY><TR><TD>G</TD><TD>150</TD><TD>202</TD><TD>E</TD></TR></TBODY></TABLE>"""

MIXED_SPAN_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Code</TD><TD>(2) Mode</TD><TD>(3) Limit</TD></TR></THEAD>
<TBODY><TR><TD>A3</TD><TD>Aircraft</TD><TD>5 L</TD></TR>
<TR><TD COLSPAN="2">A3, aircraft</TD><TD>60 L</TD></TR></TBODY></TABLE>"""

CARRIED_ROW_TABLE = """<TABLE>
<THEAD><TR><TD>(1) Code</TD><TD>(2) Limit</TD></TR></THEAD>
<TBODY><TR><TD ROWSPAN="2">A3</TD><TD>5 L</TD></TR>
<TR><TD>60 L</TD></TR></TBODY></TABLE>"""

FOOTNOTE_MARKER_TABLE = """<TABLE>
<THEAD><TR><TD>Minimum test pressure (2)</TD><TD>Widget (3)</TD></TR></THEAD>
<TBODY><TR><TD>4 bar</TD><TD>Acetal</TD></TR></TBODY></TABLE>"""

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

    def test_a_two_level_heading_is_expanded_and_read(self):
        # The shape the Hazardous Materials Table prints: seven rowspan=2 cells and three colspan
        # parents over a second row of seven, which is 7 + 3 + 2 + 2 = 14 leaves over 14 body
        # cells. The alignment is stated by the markup, and refusing it refuses arithmetic.
        table = table_of(TWO_LEVEL_TABLE)
        self.assertIsNone(table.unresolved)
        self.assertEqual(table.numbering, "printed")
        self.assertEqual(table.columns, ["1", "2", "3", "4", "5", "6", "7",
                                         "8A", "8B", "8C", "9A", "9B", "10A", "10B"])

    def test_a_split_parent_widens_the_grid_for_the_cell_after_it(self):
        table = table_of(SPLIT_PARENT_TABLE)
        self.assertIsNone(table.unresolved)
        self.assertEqual(table.columns, ["1", "2A", "2B", "5"])
        row = table.matching([("1", "G")])[0][1]
        self.assertEqual(row[table.index_of("5")], "E")
        self.assertEqual(row[table.index_of("2B")], "202")

    def test_a_split_parent_names_no_column_of_its_own(self):
        table = table_of(TWO_LEVEL_TABLE)
        self.assertIsNone(table.index_of("9"))
        self.assertIsNone(table.index_of("8"))
        self.assertIsNone(table.index_of("10"))

    def test_each_column_of_the_two_level_heading_addresses_its_own_cell(self):
        table = table_of(TWO_LEVEL_TABLE)
        acetal = table.matching([("2", "Acetal")])[0][1]
        self.assertEqual(acetal[table.index_of("9A")], "5 L")
        self.assertEqual(acetal[table.index_of("9B")], "60 L")
        self.assertEqual(acetal[table.index_of("8B")], "202")
        self.assertEqual(acetal[table.index_of("10A")], "E")

    def test_a_label_is_read_wherever_the_heading_prints_it(self):
        # The parents are prefixes, `(8)Packaging(§ 173.***)`; the children are suffixes,
        # `Exceptions(8A)`. Anchoring the token at the start of the cell finds none of the
        # children, which is the other half of why this table never numbered correctly.
        self.assertEqual(corpus.COLUMN_LABEL.findall("Exceptions(8A)"), ["8A"])
        self.assertEqual(corpus.COLUMN_LABEL.findall("(8)Packaging(§ 173.***)"), ["8"])
        self.assertEqual(corpus.COLUMN_LABEL.findall("(7)Special provisions(§ 172.102)"), ["7"])

    def test_a_row_spanning_part_of_its_width_can_be_told_apart_by_no_column(self):
        # A COLSPAN in the middle of a row displaces every cell after it. The row is not
        # addressable; where a table has no other, the table addresses nothing.
        table = table_of(SPANNED_BODY_TABLE)
        self.assertEqual(table.addressable, [True, False])
        self.assertIn("told apart by column", table.unresolved or "")
        self.assertEqual(table.columns, [])

    def test_a_footnote_row_across_the_whole_width_is_a_row_like_any_other(self):
        # § 172.101's reportable-quantity table ends with four of these, and refusing a
        # 1,356-row table for its footnotes is refusing the table for its footnotes.
        table = table_of(FOOTNOTE_ROW_TABLE)
        self.assertIsNone(table.unresolved)
        self.assertEqual(table.numbering, "printed")
        self.assertEqual(table.columns, ["1", "2"])
        self.assertEqual(table.addressable, [True, True, True])
        self.assertEqual(len(table.matching([("1", "1 The RQ applies to the whole entry.")])), 1)

    def test_a_cell_carried_into_the_next_row_leaves_the_geometry_unreadable(self):
        # A ROWSPAN in a body row displaces the rows below it, and which column their cells are
        # in is then not in the markup at all.
        table = table_of(CARRIED_ROW_TABLE)
        self.assertIn("carrying it into the row below", table.unresolved or "")
        self.assertEqual(table.columns, [])

    def test_an_unaddressable_row_is_matched_by_no_key_and_keyed_by_none(self):
        table = table_of(MIXED_SPAN_TABLE)
        self.assertEqual(table.addressable, [True, True, False])
        self.assertEqual(len(table.matching([("1", "A3, aircraft")])), 0)
        self.assertIsNone(table.key_for(2))

    def test_a_colspan_parent_with_no_row_under_it_numbers_by_position(self):
        # Both columns it covers are labelled `(8)`, which names neither of them.
        table = table_of(SPANNED_TABLE)
        self.assertIsNone(table.unresolved)
        self.assertEqual(table.numbering, "positional")
        self.assertEqual(table.columns, ["1", "2", "3"])

    def test_a_heading_that_names_two_columns_falls_back_to_position(self):
        # Which cell is which column is still determined; only the printed numbering is not.
        # That is a fall back to what the markup does say, and never a refusal -- the table is
        # § 172.102's portable-tank table, whose heading prints a footnote marker.
        table = table_of(CROWDED_HEADING_TABLE)
        self.assertIsNone(table.unresolved)
        self.assertEqual(table.numbering, "positional")
        self.assertIn("names more than one column", table.numbering_note)

    def test_a_table_numbered_only_in_part_falls_back_to_position(self):
        table = table_of(HALF_NUMBERED_TABLE)
        self.assertIsNone(table.unresolved)
        self.assertEqual(table.numbering, "positional")
        self.assertIn("some do not", table.numbering_note)

    def test_a_numbering_that_does_not_start_at_one_is_a_footnote_marker(self):
        table = table_of(FOOTNOTE_MARKER_TABLE)
        self.assertEqual(table.numbering, "positional")
        self.assertIn("and not (1)", table.numbering_note)

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
            FIXTURE.replace("<TR><TD>A3</TD><TD>Aircraft</TD><TD>5 L</TD></TR>\n"
                            "<TR><TD>A3</TD><TD>Aircraft</TD><TD>60 L</TD></TR>\n"
                            "<TR><TD>A3</TD><TD>Vessel</TD><TD>5 L</TD></TR>\n"
                            "<TR><TD>N34</TD><TD>Aircraft</TD><TD>5 L</TD></TR>",
                            '<TR><TD COLSPAN="2">A3, aircraft</TD><TD>5 L</TD></TR>'),
            "spanned.xml")
        adapter = corpus.EcfrXml(corpus_path)
        with self.assertRaises(protocol.Refused) as caught:
            adapter.units(extent([{"section": "§ 1.10", "table": 1, "rows": [ACETAL]},
                                  {"section": "§ 1.10", "table": 2, "rows": "all"}]))
        self.assertIn("told apart by column", str(caught.exception))

    def test_the_same_table_excluded_with_a_reason_needs_no_geometry(self):
        corpus_path = self.write_corpus(
            FIXTURE.replace("<TR><TD>A3</TD><TD>Aircraft</TD><TD>5 L</TD></TR>\n"
                            "<TR><TD>A3</TD><TD>Aircraft</TD><TD>60 L</TD></TR>\n"
                            "<TR><TD>A3</TD><TD>Vessel</TD><TD>5 L</TD></TR>\n"
                            "<TR><TD>N34</TD><TD>Aircraft</TD><TD>5 L</TD></TR>",
                            '<TR><TD COLSPAN="2">A3, aircraft</TD><TD>5 L</TD></TR>'),
            "spanned-excluded.xml")
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
                section, table, selector, column = read
                self.assertEqual(section, "1.10")
                self.assertIsNone(column)
                indexed = check_locators_section.table_index(self.corpus_path)[(section, table)]
                # The selector is a row key, or the anchor-relative one 0043 added; the checker
                # resolves either to exactly the row the adapter enumerated.
                if selector[0] == "below":
                    at, why = indexed.resolve_below(selector[1], selector[2], selector[3])
                    self.assertIsNone(why, unit.key)
                    cells = indexed.rows[at]
                else:
                    self.assertEqual(len(indexed.matching(selector[1])), 1)
                    cells = indexed.matching(selector[1])[0]
                self.assertEqual(check_locators_section.row_text(cells), unit.text)

    def test_the_two_read_the_same_two_level_heading(self):
        for markup in (TWO_LEVEL_TABLE, SPLIT_PARENT_TABLE, FOOTNOTE_ROW_TABLE,
                       FOOTNOTE_MARKER_TABLE):
            with self.subTest(markup=markup.split("\n")[0]):
                mine = corpus.Table("1.10", 1, ET.fromstring(markup))
                theirs = check_locators_section.Table("1.10", 1, ET.fromstring(markup))
                self.assertEqual(mine.columns, theirs.columns)
                self.assertEqual(mine.numbering, theirs.numbering)
                self.assertEqual(mine.numbering_note, theirs.numbering_note)
                self.assertEqual(mine.addressable, theirs.addressable)

    def test_the_two_read_the_same_columns_out_of_the_same_table(self):
        indexed = check_locators_section.table_index(self.corpus_path)[("1.10", 1)]
        table = corpus.Table("1.10", 1, self.adapter.root.iter("TABLE").__next__())
        self.assertEqual(indexed.columns, table.columns)
        self.assertEqual(indexed.columns, ["1", "2", "3", "4A", "4B"])

    def test_the_two_refuse_the_same_geometry(self):
        for markup in (SPANNED_BODY_TABLE, MISCOUNTED_TABLE, CROWDED_HEADING_TABLE,
                       HALF_NUMBERED_TABLE):
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

    def inventory(self, evidence, citation=ACETAL_KEY):
        self.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": extent([{"section": "§ 1.10", "table": 1, "rows": "all"},
                              SECOND_TABLE_EXCLUDED]),
            "entries": [{"id": "acetal-packing",
                         "locator": {"sourceId": "fixture", "citation": citation},
                         "evidence": evidence}],
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

    def test_a_one_token_cell_reaches_only_the_row_its_citation_names(self):
        # The token occurs elsewhere in the table and headings too. Its citation bounds the
        # search to one structural row; merely lowering the global four-word floor would make
        # those other occurrences look reached.
        code, output = self.inventory("3")
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("reached:     1", output)
        self.assertNotIn("not located inside the extent", output)

    def test_a_one_token_cell_citation_reaches_its_row(self):
        citation = ACETAL_KEY + ", column 3"
        code, output = self.inventory("3", citation)
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("reached:     1", output)
        self.assertNotIn("not located inside the extent", output)

    def test_a_two_token_cell_does_not_reach_the_other_row_that_prints_it(self):
        citation = '§ 1.10 table 1, row [column 3 = "2.2"]'
        code, output = self.inventory("Ammonia, anhydrous", citation)
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("reached:     1", output)
        self.assertNotIn("not located inside the extent", output)

    def test_three_token_evidence_is_locatable_inside_its_cited_row(self):
        citation = '§ 1.10 table 1, row [column 3 = "2.3"]'
        code, output = self.inventory("Ammonia, anhydrous |", citation)
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("reached:     1", output)
        self.assertNotIn("not located inside the extent", output)

    def test_a_short_fragment_in_the_wrong_row_does_not_reach_the_cited_row(self):
        citation = '§ 1.10 table 1, row [column 3 = "2.2"]'
        code, output = self.inventory("T4", citation)
        self.assertEqual(code, 1, output)
        self.assertIn("not located inside the extent: 1 entry", output)

    def test_duplicate_long_row_text_reaches_only_the_row_its_citation_names(self):
        text = "the same long evidence appears in both structurally distinct rows"
        units = [
            corpus.Unit('§ 1.10 table 1, row [column 1 = "left"]', "table-row", text),
            corpus.Unit('§ 1.10 table 1, row [column 1 = "right"]', "table-row", text),
        ]
        measured = inventory.take(units, {"entries": [{
            "id": "right-only",
            "locator": {"sourceId": "fixture", "citation": units[1].key},
            "evidence": text,
        }]}, {})
        self.assertEqual(set(measured.reached), {units[1].key})
        self.assertEqual(measured.located, ["right-only"])

    def test_duplicate_long_row_text_is_not_biased_toward_the_first_or_last_row(self):
        text = "the same long evidence appears in both structurally distinct rows"
        units = [
            corpus.Unit('§ 1.10 table 1, row [column 1 = "left"]', "table-row", text),
            corpus.Unit('§ 1.10 table 1, row [column 1 = "right"]', "table-row", text),
        ]
        measured = inventory.take(units, {"entries": [{
            "id": "left-only",
            "locator": {"sourceId": "fixture", "citation": units[0].key},
            "evidence": text,
        }]}, {})
        self.assertEqual(set(measured.reached), {units[0].key})
        self.assertEqual(measured.located, ["left-only"])

    def test_a_long_quote_in_the_wrong_structurally_cited_row_reaches_neither_row(self):
        units = [
            corpus.Unit('§ 1.10 table 1, row [column 1 = "left"]', "table-row",
                        "the left row has its own sufficiently long evidence"),
            corpus.Unit('§ 1.10 table 1, row [column 1 = "right"]', "table-row",
                        "the right row has different sufficiently long evidence"),
        ]
        measured = inventory.take(units, {"entries": [{
            "id": "wrong-row",
            "locator": {"sourceId": "fixture", "citation": units[0].key},
            "evidence": units[1].text,
        }]}, {})
        self.assertEqual(measured.reached, {})
        self.assertEqual(measured.unlocated, ["wrong-row"])

    def test_duplicate_long_prose_without_structural_unit_identity_keeps_current_behavior(self):
        text = "the same sufficiently long prose evidence appears in both units"
        units = [
            corpus.Unit("p. 1 block 1", "paragraph", text),
            corpus.Unit("p. 1 block 2", "paragraph", text),
        ]
        measured = inventory.take(units, {"entries": [{
            "id": "prose",
            "locator": {"sourceId": "fixture", "citation": "p. 1"},
            "evidence": text,
        }]}, {})
        self.assertEqual(set(measured.reached), {units[0].key, units[1].key})


if __name__ == "__main__":
    unittest.main()
