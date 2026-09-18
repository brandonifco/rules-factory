#!/usr/bin/env python3
"""A coded pointer is a pointer its structural context makes, not its text (0041).

[#307](https://github.com/brandonifco/rules-factory/issues/307), the measured outcome of trial
10's **H2** ([#262](https://github.com/brandonifco/rules-factory/issues/262)), recorded in advance
as [#284](https://github.com/brandonifco/rules-factory/issues/284).

49 CFR § 172.101 column 7 holds `IB2, T4, TP1` and nothing else — each a pointer into § 172.102,
with no English pointer phrase and no defined term named anywhere near it. Run against the seven
settled rows, `defined-term-use` detected all 33 column 7 occurrences and **missed none** — and
produced false references for the numeric code `148`:

  * `Alkali metal amalgam, solid` prints `13, 52, 148` in **column 14**, vessel stowage
    provisions under § 176.84, which are not § 172.102's;
  * § 172.101's prose prints *"46 CFR parts 30 to 40, 70, 98, 148, 151, 153 and 154"*, where
    `148` is a **part number**.

Firing is not the same as being right. A column 7 code is a pointer *because of the column it
sits in*, and `defined-term-use` reads text, which column membership is not.

Watched here, on the corpus's own strings:

  * all three of `Acetal`'s column 7 codes are detected, and the whole seven-row set's 33;
  * the stowage `148` in column 14 is **not** a pointer, though the text is `148`;
  * the 46 CFR part `148` in a prose paragraph is **not** a pointer, though the text is `148`;
  * moving the *same* `148` from column 7 to any other column stops it being a pointer, which is
    the whole proposition: the context makes the pointer, not the token;
  * a token in the pointer-bearing column that the vocabulary does not declare is reported, not
    silently dropped;
  * `defined-term-use` behaves exactly as before, and a protocol may declare both.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))

sys.path.insert(0, TOOLS)
try:
    from mapper import pointers, protocol
finally:
    sys.path.remove(TOOLS)

SECTION = "cfr-49-172.101"
PROVISIONS = "148 A10 A3 A7 B16 B2 IB2 IB3 IB4 IP1 N40 T11 T4 T7 T9 TP1 TP2 TP33 TP7 W31".split()

# The corpus's own column 7 cells, for the seven rows the trial settled. 33 codes in all.
COLUMN_7 = {
    "Acetal": "IB2, T4, TP1",
    "Acetaldehyde": "B16, T11, TP2, TP7",
    "Acetic acid, glacial or Acetic acid solution, with more than 80 percent acid, by mass":
        "A3, A7, A10, B2, IB2, T7, TP2",
    "Acetic acid solution, not less than 50 percent but not more than 80 percent acid, by mass":
        "148, A3, A7, A10, B2, IB2, T7, TP2",
    "Acetic acid solution, with more than 10 percent and less than 50 percent acid, by mass":
        "148, IB3, T4, TP1",
    "Acetyl acetone peroxide with more than 9 percent by mass active oxygen": "",
    "Alkali metal amalgam, solid": "IB4, IP1, N40, T9, TP7, TP33, W31",
}
GROUND_TRUTH = sum(len([c for c in cell.split(",") if c.strip()]) for cell in COLUMN_7.values())

# The two false positives the experiment measured, as the corpus prints them.
STOWAGE_CELL = "13, 52, 148"
PROSE = ("(For bulk transportation by vessel, see 46 CFR parts 30 to 40, 70, 98, 148, 151, 153 "
         "and 154.)")


def cell_entry(eid, row_name, column, text):
    return {"id": eid, "name": f"{row_name} column {column}",
            "locator": {"sourceId": SECTION,
                        "citation": f'§ 172.101 table 3, row [column 2 = "{row_name}"], '
                                    f'column {column}'},
            "evidence": text}


def vocabulary_entry():
    return {"id": "column-7-codes", "name": "The column 7 special provision codes",
            "locator": {"sourceId": SECTION, "citation": "§ 172.101(h)"},
            "evidence": "Column 7 lists the special provisions that apply to the material.",
            "crossReferences": [{"cites": code, "resolvedBy": f"provision-{code.lower()}"}
                                for code in sorted(PROVISIONS)]}


def provision_entries():
    return [{"id": f"provision-{code.lower()}", "name": f"Special provision {code}",
             "locator": {"sourceId": "cfr-49-172.102",
                         "citation": f"§ 172.102(c) [{code}]"},
             "evidence": f"{code} states a special provision."}
            for code in PROVISIONS]


def a_map(extra=()):
    entries = provision_entries() + [vocabulary_entry()]
    for i, (row_name, cell) in enumerate(COLUMN_7.items(), 1):
        entries.append(cell_entry(f"row-{i}-col7", row_name, 7, cell))
    entries.extend(extra)
    return {"schemaVersion": 1, "corpus": SECTION,
            "extent": {"unit": "section-designation", "sections": ["§ 172.101", "§ 172.102"]},
            "entries": entries}


def a_protocol(mechanisms):
    return {"protocolVersion": 1, "corpus": SECTION,
            "units": ["table", "table-row", "paragraph", "heading"],
            "pointerMechanisms": mechanisms,
            "requiredSweeps": ["cross-references"],
            "adapterReach": {"text": "readable", "tables": "readable",
                             "illustrations": "unsupported"}}


CODED = {"mechanism": "coded-pointer", "column": 7, "vocabularyFrom": "column-7-codes"}


def found(document, mechanisms=(CODED,)):
    """{(entry id, code)} the protocol's coded-pointer mechanisms detect."""
    _, _, _ = None, None, None
    namings = []
    for mechanism in protocol.mechanisms_of(a_protocol(list(mechanisms)), "coded-pointer"):
        namings += pointers.detect_coded(document, mechanism)
    return {(n.entry_id, n.term) for n in namings}


class TheColumnMakesThePointer(unittest.TestCase):
    def test_the_vocabulary_admits_the_mechanism(self):
        self.assertIn("coded-pointer", protocol.POINTER_MECHANISMS)

    def test_a_protocol_declaring_it_is_not_refused(self):
        problems = protocol.check(a_protocol([CODED]), a_map(), None)
        self.assertEqual([p for p in problems if "coded-pointer" in p], [], problems)

    def test_every_column_7_code_of_one_row_is_detected(self):
        detected = found(a_map())
        self.assertEqual({code for entry, code in detected if entry == "row-1-col7"},
                         {"IB2", "T4", "TP1"})

    def test_all_thirty_three_selected_occurrences_are_detected(self):
        self.assertEqual(len(found(a_map())), GROUND_TRUTH)
        self.assertEqual(GROUND_TRUTH, 33)

    # --- the two false positives the experiment measured ---------------------------------

    def test_the_stowage_148_in_column_14_is_not_a_pointer(self):
        document = a_map([cell_entry("row-7-col14", "Alkali metal amalgam, solid", 14,
                                     STOWAGE_CELL)])
        self.assertEqual([c for entry, c in found(document) if entry == "row-7-col14"], [])
        self.assertIn("148", STOWAGE_CELL)  # the text really is there

    def test_the_46_cfr_part_148_in_prose_is_not_a_pointer(self):
        prose = {"id": "vessel-stowage-reference",
                 "locator": {"sourceId": SECTION, "citation": "§ 172.101(k)"},
                 "evidence": PROSE}
        self.assertEqual([c for entry, c in found(a_map([prose]))
                          if entry == "vessel-stowage-reference"], [])
        self.assertIn("148", PROSE)

    def test_the_same_code_moved_out_of_column_7_stops_being_a_pointer(self):
        """The proposition itself: identical text, different column, no pointer."""
        for column in (6, 8, 14):
            with self.subTest(column=column):
                document = a_map([cell_entry(f"moved-{column}", "Acetal", column, "148, IB2")])
                detected = {c for entry, c in found(document) if entry == f"moved-{column}"}
                self.assertEqual(detected, set())
        moved_back = a_map([cell_entry("moved-7", "Acetaldehyde", 7, "148, IB2")])
        self.assertEqual({c for entry, c in found(moved_back) if entry == "moved-7"},
                         {"148", "IB2"})

    # --- what it owes the reader ----------------------------------------------------------

    def test_a_token_the_vocabulary_does_not_declare_is_reported(self):
        document = a_map([cell_entry("row-8-col7", "Ammonia, anhydrous", 7, "IB2, ZZ9")])
        lines, detected, undeclared = pointers.report(a_protocol([CODED]), document)
        self.assertTrue(any("ZZ9" in line for line in lines), lines)

    def test_defined_term_use_is_unchanged_beside_it(self):
        both = [CODED, {"mechanism": "defined-term-use", "vocabularyFrom": "column-7-codes"}]
        problems = protocol.check(a_protocol(both), a_map(), None)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
