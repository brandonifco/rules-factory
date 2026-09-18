#!/usr/bin/env python3
"""A table row is a unit, and the extent says which rows it takes (0035).

Before this, the `ecfr-xml` adapter enumerated a section's `<P>` and `<EXAMPLE>` children and
nothing else, so a table was invisible to every measurement the mapper makes: of § 172.101 --
450,000 characters, 3,687 rows -- the enumeration and the locator checker could see 6.6%
([#261](https://github.com/brandonifco/rules-factory/issues/261)). Four things are watched here,
each one a way this could report coverage it did not measure:

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
    a map may not quietly shrink its extent, one unit down.

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
# last two rows are told apart only by column 3.
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
<TABLE><THEAD><TR><TD>(1) Code</TD><TD>(2) Meaning</TD></TR></THEAD>
<TBODY><TR><TD>A3</TD><TD>Aircraft only</TD></TR></TBODY></TABLE>
</DIV8>
</DIV6></ROOT>"""

ACETAL = {"column": 2, "is": "Acetal"}
AMMONIA_23 = [{"column": 2, "is": "Ammonia, anhydrous"}, {"column": 3, "is": "2.3"}]
ACETAL_ROW = "| Acetal | 3 | 150 | 202"
ACETAL_KEY = '§ 1.10 table 1, row [column 2 = "Acetal"]'
SECOND_TABLE_EXCLUDED = {"section": "§ 1.10", "table": 2,
                         "excluded": "code meanings; no mapped row invokes one"}


def extent(tables):
    return {"unit": "section-designation", "sections": ["§ 1.10"], "tables": tables}


class AdapterCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="table-rows-test-")
        self.addCleanup(shutil.rmtree, self.directory)
        self.corpus_path = os.path.join(self.directory, "corpus.xml")
        with open(self.corpus_path, "w", encoding="utf-8") as handle:
            handle.write(FIXTURE)
        self.adapter = corpus.EcfrXml(self.corpus_path)

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

    def test_a_whole_table_keys_every_row_by_a_cell_that_identifies_it(self):
        # One column where one will do, taken in the corpus's own column order: the two ammonia
        # rows are told apart by column 3, and the empty column 1 of the Acetal row names
        # nothing, so column 2 does. A key is what identifies the row, never where it sits.
        rows = self.rows([{"section": "§ 1.10", "table": 1, "rows": "all"},
                          SECOND_TABLE_EXCLUDED])
        self.assertEqual([u.key for u in rows], [
            ACETAL_KEY,
            '§ 1.10 table 1, row [column 3 = "2.2"]',
            '§ 1.10 table 1, row [column 3 = "2.3"]',
        ])

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


class TestTheTwoGrammarsAreOneGrammar(AdapterCase):
    """The adapter writes the citation; the section locator checker reads it. Two files, one
    form -- as CITE_SECTION already is, and for the same reason: they cannot drift silently."""

    def test_every_key_the_adapter_writes_the_checker_reads_back(self):
        rows = self.rows([{"section": "§ 1.10", "table": 1, "rows": "all"},
                          {"section": "§ 1.10", "table": 2, "rows": "all"}])
        self.assertEqual(len(rows), 4)
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
        self.assertIn("3 table-row", output)
        self.assertIn("reached:     1", output)
        self.assertIn("unaccounted: 5", output)

    def test_a_quote_of_one_cell_still_reaches_its_row(self):
        code, output = self.inventory("| Acetal | 3 |")
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn("reached:     1", output)


if __name__ == "__main__":
    unittest.main()
