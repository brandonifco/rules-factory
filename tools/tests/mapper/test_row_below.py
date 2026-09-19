#!/usr/bin/env python3
"""A row the corpus leaves blank in the column that names the row above it has an address (0043).

Trial 10 ([#262](https://github.com/brandonifco/rules-factory/issues/262)) could not finalise its
extent without this. § 172.102 table 2 states `IB2` in two rows -- the authorised IBCs, then an
`Additional Requirement` whose code cell the corpus leaves blank -- and that second row is
**byte-identical** to `IB1`'s, so no `column = value` key names either and `rows: "all"` was
refused outright ([#310](https://github.com/brandonifco/rules-factory/issues/310)). One of the
seven selected § 172.101 rows invokes `IB2`, so dropping the row from the extent would make the
declared universe smaller than the rule requires.

Watched here, on a synthetic fixture and on nothing admitted:

  * the **one** blank-key row below an anchor resolves with no discriminator;
  * **two** of them require one, exactly as an ambiguous row key does;
  * deleting the target, inserting a second match, and renaming the anchor each **refuse** --
    the address stops resolving rather than resolving to something else, which is the property
    0035 demanded of a row key and an ordinal does not have;
  * the column taken is the one whose anchor is **nearest above**, because a column blank on most
    of a table anchors to a row far away and produces an address that is unique, stable and
    confidently wrong;
  * ordinary 0035 row citations are **unchanged**;
  * and the adapter and the section locator checker resolve the same selector to the same row,
    the way `test_mapper_table_rows.py` already holds their row-key grammars to each other.

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
    sys.path.remove(TOOLS)

SECTION_TOOL = os.path.join(REPO, "examples", "faa-part-107", "check-locators-section.py")
_spec = importlib.util.spec_from_file_location("check_locators_section", SECTION_TOOL)
check_locators_section = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_locators_section)

_map_spec = importlib.util.spec_from_file_location(
    "check_map", os.path.join(TOOLS, "check-map.py"))
check_map = importlib.util.module_from_spec(_map_spec)
_map_spec.loader.exec_module(check_map)


def table_of(rows, headings=("(1) Code", "(2) Requirement"), module=corpus):
    """One table of `rows`, as the named module's own `Table` reads it."""
    element = ET.Element("TABLE")
    head = ET.SubElement(ET.SubElement(element, "THEAD"), "TR")
    for text in headings:
        ET.SubElement(head, "TH").text = text
    body = ET.SubElement(element, "TBODY")
    for cells in rows:
        row = ET.SubElement(body, "TR")
        for text in cells:
            ET.SubElement(row, "TD").text = text
    return module.Table("1.10", 1, element)


#: The shape § 172.102 table 2 prints: a code row, then a requirement row whose code cell is
#: blank -- and IB1's and IB2's requirement rows are the same sentence, so neither is nameable.
SAME_REQUIREMENT = "Additional Requirement: Only liquids with a vapor pressure of 110 kPa."
IB_ROWS = [
    ["IB1", "Authorized IBCs: Metal (31A)."],
    [" ", SAME_REQUIREMENT],
    ["IB2", "Authorized IBCs: Metal (31A); Rigid plastics (31H1)."],
    [" ", SAME_REQUIREMENT],
    ["IB3", "Authorized IBCs: Metal (31A); Composite (31HZ1)."],
]


class OneBlankRowBelowAnAnchor(unittest.TestCase):
    """Proof 1: IB2's single blank-key row resolves, with no discriminator."""

    def setUp(self):
        self.table = table_of(IB_ROWS)

    def test_the_row_has_no_row_key_of_its_own(self):
        self.assertIsNone(self.table.key_for(4),
                          "IB2's requirement row is byte-identical to IB1's, so no key names it")

    def test_it_is_named_below_its_anchor(self):
        self.assertEqual(self.table.key_below(4), ("1", [("1", "IB2")], []))

    def test_the_citation_the_adapter_writes(self):
        self.assertEqual(
            corpus.row_below_citation("172.102", 2, *self.table.key_below(4)),
            '§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]')

    def test_it_resolves_to_that_row_and_not_IB1s(self):
        at, why = self.table.resolve_below("1", [("1", "IB2")])
        self.assertIsNone(why)
        self.assertEqual(at, 4)
        other, why = self.table.resolve_below("1", [("1", "IB1")])
        self.assertIsNone(why)
        self.assertEqual(other, 2)

    def test_a_table_holding_it_is_enumerated_whole(self):
        """`rows: "all"` was refused before this; every row now carries an address."""
        keys = [self.table.key_for(position) or self.table.key_below(position)
                for position in range(len(self.table.rows))]
        self.assertTrue(all(key is not None for key in keys), keys)


class TwoBlankRowsNeedADiscriminator(unittest.TestCase):
    """Proof 2: the Adhesives shape -- one anchor, two blank rows, told apart by a column."""

    #: § 172.101 table 3 states a multi-packing-group material this way: the named row, then one
    #: row per packing group with columns 1-4 blank. Both of Adhesives' are byte-identical to
    #: Resin Solution's, so neither has a key.
    ROWS = [
        [" ", "Adhesives", "I", "T11"],
        [" ", " ", "II", "IB2"],
        [" ", " ", "III", "IB3"],
        [" ", "Resin Solution", "I", "T11"],
        [" ", " ", "II", "IB2"],
        [" ", " ", "III", "IB3"],
    ]
    HEADINGS = ("(1) Symbol", "(2) Name", "(5) Packing group", "(7) Provisions")

    def setUp(self):
        self.table = table_of(self.ROWS, self.HEADINGS)

    def test_neither_row_has_a_key(self):
        # The heading row is row 0, so Adhesives is row 1 and its two packing groups rows 2 and 3.
        self.assertIsNone(self.table.key_for(2))
        self.assertIsNone(self.table.key_for(3))

    def test_each_is_named_below_the_material_with_a_discriminator(self):
        self.assertEqual(self.table.key_below(2), ("2", [("2", "Adhesives")], [("5", "II")]))
        self.assertEqual(self.table.key_below(3), ("2", [("2", "Adhesives")], [("5", "III")]))

    def test_the_two_materials_runs_do_not_collide(self):
        self.assertEqual(self.table.key_below(5),
                         ("2", [("2", "Resin Solution")], [("5", "II")]))
        at, why = self.table.resolve_below("2", [("2", "Resin Solution")], [("5", "II")])
        self.assertIsNone(why)
        self.assertEqual(at, 5)

    def test_without_a_discriminator_the_run_of_two_refuses(self):
        at, why = self.table.resolve_below("2", [("2", "Adhesives")])
        self.assertIsNone(at)
        self.assertIn("2 of the 2 row(s)", why)

    def test_the_column_taken_is_the_one_whose_anchor_is_nearest(self):
        """Column 1 is blank on both rows too, and its nearest filled row is another material.

        Read in the table's column order the address would be
        `blank in column 1 below row [column 2 = "Adhesives"]` for row 4 -- unique, stable and
        naming the wrong material. Nearest-first is what stops that.
        """
        column, anchor, _ = self.table.key_below(5)
        self.assertEqual(column, "2")
        self.assertEqual(anchor, [("2", "Resin Solution")])


class AnAmendmentMakesItStopResolving(unittest.TestCase):
    """Proofs 3, 4 and 5: every way the corpus can move under the address is a refusal."""

    def test_deleting_the_target_refuses(self):
        table = table_of([row for position, row in enumerate(IB_ROWS) if position != 3])
        at, why = table.resolve_below("1", [("1", "IB2")])
        self.assertIsNone(at)
        self.assertIn("leaves column 1 blank", why)

    def test_inserting_a_second_match_refuses(self):
        rows = IB_ROWS[:4] + [[" ", "Additional Requirement: And also this."]] + IB_ROWS[4:]
        table = table_of(rows)
        at, why = table.resolve_below("1", [("1", "IB2")])
        self.assertIsNone(at)
        self.assertIn("2 of the 2 row(s)", why)

    def test_renaming_the_anchor_refuses(self):
        rows = [["IB2A" if cell == "IB2" else cell for cell in row] for row in IB_ROWS]
        at, why = table_of(rows).resolve_below("1", [("1", "IB2")])
        self.assertIsNone(at)
        self.assertIn("names 0 rows", why)

    def test_duplicating_the_anchor_refuses(self):
        rows = IB_ROWS + [["IB2", "Authorized IBCs: Metal (31A); Rigid plastics (31H1)."]]
        at, why = table_of(rows).resolve_below("1", [("1", "IB2")])
        self.assertIsNone(at)
        self.assertIn("names 2 rows", why)

    def test_a_column_the_table_does_not_print_refuses(self):
        at, why = table_of(IB_ROWS).resolve_below("9", [("1", "IB2")])
        self.assertIsNone(at)
        self.assertIn("prints no column 9", why)


class OrdinaryRowCitationsAreUnchanged(unittest.TestCase):
    """Proof 6: nothing about a plain 0035 row key moves."""

    def test_a_nameable_row_keeps_its_plain_key(self):
        table = table_of(IB_ROWS)          # row 0 is the heading, so IB2's own row is row 3
        self.assertEqual(table.key_for(3), [("1", "IB2")])
        self.assertEqual(corpus.row_citation("172.102", 2, table.key_for(3)),
                         '§ 172.102 table 2, row [column 1 = "IB2"]')

    def test_the_checker_still_reads_a_plain_citation(self):
        read = check_locators_section.table_citation(
            '§ 172.101 table 3, row [column 2 = "Acetal"], column 7')
        self.assertEqual(read, ("172.101", 3, ("key", [("2", "Acetal")]), "7"))

    def test_check_map_still_reads_a_plain_citation(self):
        self.assertEqual(
            check_map.cited_row('§ 172.101 table 3, row [column 2 = "Acetal"]'),
            ("172.101", 3, frozenset({("2", "Acetal")})))

    def test_a_citation_outside_both_grammars_is_still_none(self):
        self.assertIsNone(check_locators_section.table_citation("§ 107.51(a)"))
        self.assertIsNone(check_map.cited_row("§ 107.51(a)"))


class TheTwoWalksReadTheSameSelector(unittest.TestCase):
    """What the adapter writes, the section locator checker resolves to the same row."""

    CITATION = '§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]'

    def test_the_checker_parses_what_the_adapter_writes(self):
        self.assertEqual(
            check_locators_section.table_citation(self.CITATION),
            ("172.102", 2, ("below", "1", [("1", "IB2")], []), None))

    def test_a_discriminated_selector_round_trips(self):
        citation = ('§ 172.101 table 3, row blank in column 2 [column 5 = "II"] '
                    'below row [column 2 = "Adhesives"]')
        self.assertEqual(
            check_locators_section.table_citation(citation),
            ("172.101", 3, ("below", "2", [("2", "Adhesives")], [("5", "II")]), None))

    def test_a_cell_suffix_still_reads(self):
        self.assertEqual(
            check_locators_section.table_citation(self.CITATION + ", column 2")[3], "2")

    def test_both_tables_resolve_it_to_the_same_row(self):
        here = table_of(IB_ROWS)
        there = table_of(IB_ROWS, module=check_locators_section)
        at, why = here.resolve_below("1", [("1", "IB2")])
        other, other_why = there.resolve_below("1", [("1", "IB2")])
        self.assertEqual((at, why), (other, other_why))
        self.assertEqual(here.rows[at], there.rows[other])

    def test_the_run_is_the_same_on_both_sides(self):
        here = table_of(IB_ROWS)
        there = table_of(IB_ROWS, module=check_locators_section)
        self.assertEqual(here.run_below(2, "1"), there.run_below(2, "1"))

    def test_check_map_reads_it_as_a_row_no_slice_can_name(self):
        self.assertEqual(check_map.cited_row(self.CITATION), ("172.102", 2, None))

    def test_such_a_row_is_inside_the_extent_only_where_the_table_is_whole(self):
        row = check_map.cited_row(self.CITATION)
        self.assertEqual(check_map._place_row("e", self.CITATION, row, {"172.102"},
                                              {("172.102", 2): "all"}), [])
        refused = check_map._place_row("e", self.CITATION, row, {"172.102"},
                                       {("172.102", 2): {frozenset({("1", "IB2")})}})
        self.assertEqual(len(refused), 1)
        self.assertIn("no key names a row below the row above it", refused[0])


if __name__ == "__main__":
    unittest.main()
