#!/usr/bin/env python3
"""Trial 10's real case, through the complete validator (0045).

[#314](https://github.com/brandonifco/rules-factory/issues/314). 0041 gave `coded-pointer` the
`vocabularyFrom` `defined-term-use` has -- one entry whose `crossReferences` list the corpus's
terms -- and was measured with a proposition test over synthetic documents and with
`protocol.check`. Neither runs `check-map.py --only cross-references`, whose anchoring rule
(0026) requires every `cites` to appear **verbatim in that entry's own `evidence`**. 49 CFR
§ 172.102 prints no passage listing its codes, so no entry of a map of it can carry that list
without inventing it, and the mechanism could not be declared by a map of the corpus that forced
it.

This file is the integration regression 0041 lacked: **the real corpus's own strings**, both
pointer-bearing columns, both vocabularies, run through **every check in `check-map.py`** and
through `mapper protocol` and `mapper pointers` -- not through one of them.

Watched here:

  * the old synthetic `special-provision-codes` entry still **fails**, exactly as it did, when
    its `crossReferences.cites` are absent from its evidence. Nothing here exempts anything;
  * the map that replaces it -- one `defines` declaration per defining entry -- passes the
    complete validator, and `mapper protocol` accepts its two protocols;
  * `IB2`'s additional requirement and `IB3`'s analogous row join their direct definitions
    through `continuesDefinition` (0046); all defining entries are required and deleting any
    pointer edge is visible;
  * reversing the order the map states the defining entries in changes nothing;
  * column 6 and column 7 read two different vocabularies, and a token of one does not satisfy
    the other because the text matches;
  * a `defines.term` absent from its entry's evidence is refused, a derived entry carrying
    `defines` is refused, and a duplicate declaration is refused;
  * a `coded-pointer` naming a vocabulary no entry defines is refused.

The corpus is `examples/hazmat-172-table/`, pinned at the 2026-01-01 baseline, and its own
`corpus-manifest.json` is the manifest this map is checked against. Every quoted span below is
the corpus's text, and every table number is the adapter's document order, checked against the
committed XML: § 172.101 table 1 is the Label Substitution Table and table 3 the Hazardous
Materials Table; § 172.102 table 2 is the IB Codes table, table 4 the Large Packagings table and
table 6 the portable tank T codes.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(TOOLS)
TRIAL = os.path.join(ROOT, "examples", "hazmat-172-table")
MANIFEST = os.path.join(TRIAL, "corpus-manifest.json")

sys.path.insert(0, TOOLS)
try:
    from mapcontract.entry import defined_vocabulary, defines_of
    from mapper import pointers, protocol
finally:
    sys.path.remove(TOOLS)

_spec = importlib.util.spec_from_file_location("check_map_for_defines",
                                               os.path.join(TOOLS, "check-map.py"))
check_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_map)

TABLE = "cfr-49-172.101"
PROVISIONS = "cfr-49-172.102"
CODES = "special-provision-codes"
LABELS = "hazard-label-codes"

ACETAL = ('§ 172.101 table 3, row [column 2 = "Acetal"]')
ACETIC = ('§ 172.101 table 3, row [column 2 = "Acetic acid solution, with more than 10 percent '
          'and less than 50 percent acid, by mass"]')


def entry(entry_id, source, citation, evidence, **overrides):
    base = {"id": entry_id, "name": f"The rule at {citation}",
            "locator": {"sourceId": source, "citation": citation},
            "kind": "value", "scope": "in", "clarity": "clear",
            "evidence": evidence, "status": "mapped"}
    base.update(overrides)
    return base


def defines(vocabulary, *terms):
    return [{"vocabulary": vocabulary, "term": term} for term in terms]


def cites(*pairs):
    return [{"cites": token, "resolvedBy": target} for token, target in pairs]


# --- the defining entries: one per code, each anchored in its own row or paragraph ----------

def defining_entries():
    return [
        entry("ib2-authorized-ibcs", PROVISIONS,
              '§ 172.102 table 2, row [column 1 = "IB2"]',
              "IB2 Authorized IBCs: Metal (31A, 31B and 31N); Rigid plastics (31H1 and 31H2); "
              "Composite (31HZ1).",
              defines=defines(CODES, "IB2")),
        entry("ib2-vapour-pressure-limit", PROVISIONS,
              '§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]',
              "| Additional Requirement: Only liquids with a vapor pressure less than or equal "
              "to 110 kPa at 50 °C (1.1 bar at 122 °F), or 130 kPa at 55 °C "
              "(1.3 bar at 131 °F) are authorized.",
              continuesDefinition={
                  "definedBy": "ib2-authorized-ibcs",
                  "anchor": {
                      "sourceId": PROVISIONS,
                      "citation": '§ 172.102 table 2, row blank in column 1 below row '
                                  '[column 1 = "IB2"]',
                  },
              }),
        entry("ib3-authorized-ibcs", PROVISIONS,
              '§ 172.102 table 2, row [column 1 = "IB3"]',
              "IB3 Authorized IBCs: Metal (31A, 31B and 31N); Rigid plastics (31H1 and 31H2); "
              "Composite (31HZ1 and 31HA2, 31HB2, 31HN2, 31HD2 and 31HH2).",
              defines=defines(CODES, "IB3")),
        entry("ib3-vapour-pressure-limit", PROVISIONS,
              '§ 172.102 table 2, row [column 2 = "Additional Requirement: Only liquids with a '
              'vapor pressure less than or equal to 110 kPa at 50 °C (1.1 bar at 122 °F), or '
              '130 kPa at 55 °C (1.3 bar at 131 °F) are authorized, except for UN2672 (also see '
              'special provision IP8 in Table 2 for UN2672)."]',
              "| Additional Requirement: Only liquids with a vapor pressure less than or equal "
              "to 110 kPa at 50 °C (1.1 bar at 122 °F), or 130 kPa at 55 °C "
              "(1.3 bar at 131 °F) are authorized, except for UN2672 (also see special provision "
              "IP8 in Table 2 for UN2672).",
              continuesDefinition={
                  "definedBy": "ib3-authorized-ibcs",
                  "anchor": {
                      "sourceId": PROVISIONS,
                      "citation": '§ 172.102 table 2, row blank in column 1 below row '
                                  '[column 1 = "IB3"]',
                  },
              }),
        # 0044: the same printed code, a second rule, a second table. Three entries, one term.
        entry("ib3-authorized-large-packagings", PROVISIONS,
              '§ 172.102 table 4, row [column 1 = "IB3"]',
              "IB3 Authorized Large Packagings (LIQUIDS) (PG III materials only)",
              defines=defines(CODES, "IB3")),
        entry("t4-portable-tank", PROVISIONS,
              '§ 172.102 table 6, row [column 1 = "T4"]',
              "T4 2.65 § 178.274(d)(2) Normal § 178.275(d)(3)",
              defines=defines(CODES, "T4"),
              crossReferences=[
                  {"cites": "§ 178.274(d)(2)",
                   "unmapped": "Part 178 is not admitted; the manifest names it as a reference."},
                  {"cites": "§ 178.275(d)(3)",
                   "unmapped": "Part 178 is not admitted; the manifest names it as a reference."}]),
        entry("tp1-degree-of-filling", PROVISIONS, "§ 172.102(c)(7) [TP1]",
              "TP1 The maximum degree of filling must not exceed the degree of filling determined "
              "by the following:",
              defines=defines(CODES, "TP1")),
        entry("provision-148-bulk-blasting", PROVISIONS, "§ 172.102(c)(1) [148]",
              "148 For domestic transportation, this entry directs to § 173.66 of this subchapter "
              "for:",
              defines=defines(CODES, "148"),
              crossReferences=[{"cites": "§ 173.66 of this subchapter",
                                "unmapped": "§ 173.66 is outside this map's extent."}]),
        # The second vocabulary, in the other section and the other table.
        entry("class-3-flammable-liquid", TABLE, '§ 172.101 table 1, row [column 1 = "3"]',
              "3 Flammable Liquid", defines=defines(LABELS, "3")),
        entry("class-8-corrosive", TABLE, '§ 172.101 table 1, row [column 1 = "8"]',
              "8 Corrosive", defines=defines(LABELS, "8")),
    ]


# --- the pointing cells: the corpus's own column 6 and column 7 cells ------------------------

def pointing_entries():
    return [
        entry("acetal-column-7", TABLE, f"{ACETAL}, column 7", "IB2, T4, TP1",
              crossReferences=cites(("IB2", "ib2-authorized-ibcs"),
                                    ("IB2", "ib2-vapour-pressure-limit"),
                                    ("T4", "t4-portable-tank"),
                                    ("TP1", "tp1-degree-of-filling"))),
        entry("acetal-column-6", TABLE, f"{ACETAL}, column 6", "3",
              crossReferences=cites(("3", "class-3-flammable-liquid"))),
        entry("acetic-acid-10-50-column-7", TABLE, f"{ACETIC}, column 7", "148, IB3, T4, TP1",
              crossReferences=cites(("148", "provision-148-bulk-blasting"),
                                    ("IB3", "ib3-authorized-ibcs"),
                                    ("IB3", "ib3-authorized-large-packagings"),
                                    ("IB3", "ib3-vapour-pressure-limit"),
                                    ("T4", "t4-portable-tank"),
                                    ("TP1", "tp1-degree-of-filling"))),
        entry("acetic-acid-10-50-column-6", TABLE, f"{ACETIC}, column 6", "8",
              crossReferences=cites(("8", "class-8-corrosive"))),
    ]


def trial_map():
    """The map, as trial 10 writes this slice under 0045-0046."""
    return {
        "schemaVersion": 1,
        "corpus": TABLE,
        "baseline": {"contentHash": "979bfc51b90b56ce337662ff6cb39d159c460e79a61f9b716a97be3c"
                                    "d0ee8227",
                     "hashDerivation": "ecfr-versioner-xml"},
        "extent": {
            "unit": "section-designation",
            "sections": ["§ 172.101", "§ 172.102"],
            "tables": [
                {"section": "§ 172.101", "table": 1,
                 "rows": [{"column": 1, "is": "3"}, {"column": 1, "is": "8"}]},
                {"section": "§ 172.101", "table": 2,
                 "excluded": "packaging section reference for solid materials; no mapped row "
                             "invokes it"},
                {"section": "§ 172.101", "table": 3,
                 "rows": [{"column": 2, "is": "Acetal"},
                          {"column": 2, "is": "Acetic acid solution, with more than 10 percent "
                                              "and less than 50 percent acid, by mass"}]},
                {"section": "§ 172.101", "table": 4,
                 "excluded": "appendix A hazardous substances; outside the slice"},
                {"section": "§ 172.101", "table": 5,
                 "excluded": "appendix A radionuclides; outside the slice"},
                {"section": "§ 172.101", "table": 6,
                 "excluded": "appendix B marine pollutants; outside the slice"},
                {"section": "§ 172.102", "table": 1,
                 "excluded": "the ASTM maximum ambient temperature table inside numeric "
                             "provision 14; no mapped row invokes it"},
                {"section": "§ 172.102", "table": 2, "rows": "all"},
                {"section": "§ 172.102", "table": 3,
                 "excluded": "IP codes; no mapped row carries one"},
                {"section": "§ 172.102", "table": 4, "rows": [{"column": 1, "is": "IB3"}]},
                {"section": "§ 172.102", "table": 5,
                 "excluded": "the IB8 large packaging table; no mapped row carries IB8"},
                {"section": "§ 172.102", "table": 6, "rows": [{"column": 1, "is": "T4"}]},
                {"section": "§ 172.102", "table": 7,
                 "excluded": "the organic peroxide concentration table; no mapped row invokes it"},
            ],
        },
        "entries": defining_entries() + pointing_entries(),
    }


def a_protocol(corpus, mechanisms):
    return {"protocolVersion": 1, "corpus": corpus,
            "units": ["section", "paragraph", "table", "table-row"],
            "pointerMechanisms": mechanisms,
            "requiredSweeps": ["cross-references", "tables", "extent-coverage"],
            "adapterReach": {"text": "readable", "tables": "readable", "columns": "readable",
                             "illustrations": "unsupported"}}


COLUMN_7 = {"mechanism": "coded-pointer", "column": 7, "vocabulary": CODES}
COLUMN_6 = {"mechanism": "coded-pointer", "column": 6, "vocabulary": LABELS}


def table_protocol(mechanisms=None):
    return a_protocol(TABLE, mechanisms if mechanisms is not None
                      else [COLUMN_7, COLUMN_6, {"mechanism": "section-designation"}])


def provisions_protocol():
    return a_protocol(PROVISIONS, [{"mechanism": "phrase"},
                                   {"mechanism": "section-designation"}])


# --- the synthetic vocabulary entry #314 refused to make legal --------------------------------

def synthetic_vocabulary_entry():
    """What 0041 asked for, and what 0026 refuses: an index of codes the passage does not print.

    § 172.102(c) is the nearest thing the corpus has to a list of its own codes, and this is its
    whole text.
    """
    return entry("special-provision-codes", PROVISIONS, "§ 172.102(c)",
                 "Tables of special provisions. The following tables list, and set forth the "
                 "requirements of, the special provisions referred to in column 7 of the "
                 "§ 172.101 table.",
                 crossReferences=cites(("IB2", "ib2-authorized-ibcs"),
                                       ("IB3", "ib3-authorized-ibcs"),
                                       ("T4", "t4-portable-tank")))


class ValidatorCase(unittest.TestCase):
    """Runs the built `check-map.py` over a map, against the trial's own manifest."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()

    def run_checks(self, document, argv=()):
        path = os.path.join(self.directory, "corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_map.main([path, "--manifest", MANIFEST, "--repo-root", ROOT, *argv])
        return code, out.getvalue() + err.getvalue()

    def status_of(self, output, check):
        found = re.search(rf"^\[(ok|fail|skip)\] {re.escape(check)}:", output, re.M)
        self.assertIsNotNone(found, f"check {check!r} did not report at all:\n{output}")
        return found.group(1)

    def tearDown(self):
        for name in os.listdir(self.directory):
            os.remove(os.path.join(self.directory, name))
        os.rmdir(self.directory)


class TheRealCasePassesTheCompleteValidator(ValidatorCase):
    """The regression 0041 lacked: not `protocol.check`, but every check there is."""

    def test_the_map_passes_every_check(self):
        code, output = self.run_checks(trial_map())
        self.assertEqual(code, 0, output)
        self.assertNotIn("[fail]", output)

    def test_the_defines_check_examined_it(self):
        # A skip would mean the declarations were never read -- a step proving nothing.
        code, output = self.run_checks(trial_map())
        self.assertEqual(self.status_of(output, "defines"), "ok", output)
        self.assertIn("8 definition(s) declared by 8 entr(ies)", output)
        self.assertEqual(self.status_of(output, "definition-continuations"), "ok", output)

    def test_the_cross_references_of_the_pointing_cells_are_anchored(self):
        code, output = self.run_checks(trial_map())
        self.assertEqual(self.status_of(output, "cross-references"), "ok", output)

    def test_both_protocols_are_ones_this_mapper_can_act_on(self):
        document = trial_map()
        self.assertEqual(protocol.check(table_protocol(), document, self.manifest()), [])
        self.assertEqual(protocol.check(provisions_protocol(), document, self.manifest()), [])

    @staticmethod
    def manifest():
        with open(MANIFEST, encoding="utf-8") as handle:
            return json.load(handle)


class TheSyntheticVocabularyEntryStillFails(ValidatorCase):
    """No exemption was created. The shape #314 refused is refused exactly as it was."""

    def test_an_entry_indexing_codes_its_evidence_does_not_print_is_refused(self):
        document = trial_map()
        document["entries"].append(synthetic_vocabulary_entry())
        code, output = self.run_checks(document)
        self.assertEqual(self.status_of(output, "cross-references"), "fail", output)
        self.assertIn("special-provision-codes: crossReferences cites 'IB2', which does not "
                      "appear in this entry's `evidence`", output)
        self.assertEqual(code, 1, output)

    def test_and_naming_it_as_a_coded_pointers_vocabulary_is_refused_too(self):
        problems = protocol.check(
            table_protocol([{"mechanism": "coded-pointer", "column": 7,
                             "vocabularyFrom": "special-provision-codes"}]),
            trial_map(), None)
        self.assertTrue(any("distributed over the entries" in line for line in problems), problems)


class TheVocabularyIsWhatTheDefiningEntriesAddUpTo(ValidatorCase):
    """0044 through 0046: direct definitions plus continuations, and the cell owes all."""

    @staticmethod
    def column_7(document):
        return {n.term: n for n in pointers.detect_coded(document, COLUMN_7)
                if n.entry_id == "acetic-acid-10-50-column-7"}

    def test_ib3_defines_three_rules(self):
        found = self.column_7(trial_map())
        self.assertEqual(found["IB3"].defines,
                         ["ib3-authorized-ibcs", "ib3-vapour-pressure-limit",
                          "ib3-authorized-large-packagings"])
        self.assertEqual(found["IB3"].missing, [])

    def test_ib2_defines_the_direct_and_additional_rules(self):
        found = {n.term: n for n in pointers.detect_coded(trial_map(), COLUMN_7)
                 if n.entry_id == "acetal-column-7"}
        self.assertEqual(found["IB2"].defines,
                         ["ib2-authorized-ibcs", "ib2-vapour-pressure-limit"])
        self.assertEqual(found["IB2"].missing, [])

    def test_deleting_either_ib3_declaration_is_visible(self):
        for dropped in ("ib3-authorized-ibcs", "ib3-vapour-pressure-limit",
                        "ib3-authorized-large-packagings"):
            with self.subTest(dropped=dropped):
                document = trial_map()
                for item in document["entries"]:
                    if item["id"] == "acetic-acid-10-50-column-7":
                        item["crossReferences"] = [c for c in item["crossReferences"]
                                                   if c["resolvedBy"] != dropped]
                naming = self.column_7(document)["IB3"]
                self.assertEqual(naming.missing, [dropped])
                lines, _, undeclared = pointers.report(table_protocol(), document)
                self.assertTrue(any(dropped in line for line in lines), lines)
                self.assertIn("IB3", [n.term for n in undeclared])

    def test_deleting_a_defining_entry_is_visible(self):
        """The rule, not the pointer: deleting table 4 leaves IB3's table-2 pair."""
        document = trial_map()
        document["entries"] = [e for e in document["entries"]
                               if e["id"] != "ib3-authorized-large-packagings"]
        for item in document["entries"]:
            if item["id"] == "acetic-acid-10-50-column-7":
                item["crossReferences"] = [c for c in item["crossReferences"]
                                           if c["resolvedBy"] != "ib3-authorized-large-packagings"]
        document["extent"]["tables"] = [t for t in document["extent"]["tables"]
                                        if not (t["section"] == "§ 172.102" and t["table"] == 4)]
        document["extent"]["tables"].append(
            {"section": "§ 172.102", "table": 4, "excluded": "dropped, for this measurement"})
        lines, _, _ = pointers.report(table_protocol(), document)
        self.assertEqual(self.column_7(document)["IB3"].defines,
                         ["ib3-authorized-ibcs", "ib3-vapour-pressure-limit"])
        self.assertTrue(any("5 term(s) defined by 7 entr(ies)" in line for line in lines), lines)

    def test_the_order_the_map_states_the_defining_entries_in_changes_nothing(self):
        forwards = trial_map()
        backwards = trial_map()
        backwards["entries"] = list(reversed(backwards["entries"]))
        self.assertEqual(set(self.column_7(forwards)["IB3"].defines),
                         set(self.column_7(backwards)["IB3"].defines))
        self.assertEqual(self.column_7(backwards)["IB3"].missing, [])
        code, output = self.run_checks(backwards)
        self.assertEqual(code, 0, output)


class TwoColumnsReadTwoVocabularies(ValidatorCase):
    """Column 6 is hazard labels and column 7 special provisions, and neither answers the other."""

    def test_each_column_reads_only_its_own(self):
        document = trial_map()
        labels = {n.term for n in pointers.detect_coded(document, COLUMN_6)}
        codes = {n.term for n in pointers.detect_coded(document, COLUMN_7)}
        self.assertEqual(labels, {"3", "8"})
        self.assertEqual(codes, {"148", "IB2", "IB3", "T4", "TP1"})

    def test_a_token_of_one_vocabulary_does_not_satisfy_the_other(self):
        """`3` is defined -- as a hazard label. In column 7 it is an undeclared code."""
        document = trial_map()
        for item in document["entries"]:
            if item["id"] == "acetal-column-7":
                item["evidence"] = "3, IB2"
                item["crossReferences"] = cites(("IB2", "ib2-authorized-ibcs"))
        found = {n.term: n for n in pointers.detect_coded(document, COLUMN_7)
                 if n.entry_id == "acetal-column-7"}
        self.assertEqual(found["3"].defines, [])
        lines, _, undeclared = pointers.report(table_protocol([COLUMN_7]), document)
        self.assertTrue(any("no entry declares it defines in vocabulary "
                            f"{CODES!r}" in line for line in lines), lines)
        self.assertIn("3", [n.term for n in undeclared])

    def test_a_vocabulary_no_entry_defines_is_refused(self):
        problems = protocol.check(
            table_protocol([{"mechanism": "coded-pointer", "column": 9,
                             "vocabulary": "column-9-codes"}]),
            trial_map(), None)
        self.assertTrue(any("no entry in this map establishes vocabulary "
                            "'column-9-codes'" in line for line in problems), problems)


class TheValidatorAndTheReadersAgree(ValidatorCase):
    """What `check-map.py --only defines` accepts is what every contract reader sees.

    The validator normalised a declaration before judging it and the contract reader returned
    the raw strings, so a map could pass the check under one `(vocabulary, term)` and be read
    under another -- `" special-provision-codes "` proved, `"special-provision-codes"` looked up,
    and the code silently undeclared. One canonical interpretation now lives at the contract
    boundary (`mapcontract.entry.definition_of`) and both sides read it.

    Each case walks the whole chain: accepted by check-map -> `defined_vocabulary` returns
    exactly that vocabulary and term -> the coded pointer resolves against it.
    """

    TERMS = "provision-terms"

    def declaring(self, entry_id, items, also=None):
        document = trial_map()
        for item in document["entries"]:
            if item["id"] == entry_id:
                item["defines"] = items
            if also is not None and item["id"] == also[0]:
                item["defines"] = also[1]
        return document

    def assert_chain(self, document, vocabulary, term, defined_by):
        """Accepted, read as exactly this, and resolved as exactly this."""
        code, output = self.run_checks(document)
        self.assertEqual(self.status_of(output, "defines"), "ok", output)
        self.assertEqual(code, 0, output)
        self.assertIn(defined_by, defined_vocabulary(document, vocabulary).get(term, []))

    def test_whitespace_around_a_vocabulary_name_is_canonicalised(self):
        document = self.declaring("ib3-authorized-large-packagings",
                                  [{"vocabulary": f"  {CODES}  ", "term": "IB3"}])
        self.assert_chain(document, CODES, "IB3", "ib3-authorized-large-packagings")
        naming = {n.term: n for n in pointers.detect_coded(document, COLUMN_7)
                  if n.entry_id == "acetic-acid-10-50-column-7"}["IB3"]
        self.assertEqual(naming.defines,
                         ["ib3-authorized-ibcs", "ib3-vapour-pressure-limit",
                          "ib3-authorized-large-packagings"])
        self.assertEqual(naming.missing, [])

    def test_whitespace_around_a_term_is_canonicalised(self):
        document = self.declaring("ib2-authorized-ibcs",
                                  [{"vocabulary": CODES, "term": "  IB2\n"}])
        self.assert_chain(document, CODES, "IB2", "ib2-authorized-ibcs")
        naming = {n.term: n for n in pointers.detect_coded(document, COLUMN_7)
                  if n.entry_id == "acetal-column-7"}["IB2"]
        self.assertEqual(naming.missing, [])

    def test_repeated_whitespace_inside_a_term_is_canonicalised(self):
        """A multi-word term, as the evidence prints it once the map's own spacing is read."""
        document = self.declaring(
            "ib3-authorized-large-packagings",
            [{"vocabulary": CODES, "term": "IB3"},
             {"vocabulary": self.TERMS, "term": "Large   Packagings"}])
        self.assert_chain(document, self.TERMS, "Large Packagings",
                          "ib3-authorized-large-packagings")
        self.assertEqual(sorted(defined_vocabulary(document, self.TERMS)), ["Large Packagings"])

    def test_a_declaration_the_check_accepts_is_one_the_reader_returns(self):
        """The invariant itself, over every declaration in the map."""
        document = trial_map()
        code, output = self.run_checks(document)
        self.assertEqual(self.status_of(output, "defines"), "ok", output)
        for item in document["entries"]:
            if "defines" not in item:
                continue
            with self.subTest(entry=item["id"]):
                self.assertEqual(len(defines_of(item)), len(item["defines"]))
                for vocabulary, term in defines_of(item):
                    self.assertIn(item["id"],
                                  defined_vocabulary(document, vocabulary).get(term, []))

    def test_two_declarations_differing_only_by_whitespace_are_a_duplicate(self):
        document = self.declaring("ib3-authorized-ibcs",
                                  [{"vocabulary": CODES, "term": "IB3"},
                                   {"vocabulary": f" {CODES}", "term": " IB3 "}])
        code, output = self.run_checks(document)
        self.assertEqual(self.status_of(output, "defines"), "fail", output)
        self.assertIn("more than once", output)
        self.assertEqual(code, 1, output)

    def test_a_term_that_is_only_whitespace_is_refused_and_read_by_nobody(self):
        document = self.declaring("ib2-authorized-ibcs",
                                  [{"vocabulary": CODES, "term": "   "}])
        code, output = self.run_checks(document)
        self.assertEqual(self.status_of(output, "defines"), "fail", output)
        self.assertEqual(defined_vocabulary(document, CODES).get("IB2"), None)


class TheDeclarationIsAnchoredOrItIsRefused(ValidatorCase):
    """0026's rule, applied to a definition: an entry defines a term by printing it."""

    def mutate(self, entry_id, change):
        document = trial_map()
        for item in document["entries"]:
            if item["id"] == entry_id:
                change(item)
        return self.run_checks(document)

    def test_a_term_the_entrys_evidence_does_not_print_is_refused(self):
        code, output = self.mutate("ib2-authorized-ibcs",
                                   lambda e: e["defines"].__setitem__(
                                       0, {"vocabulary": CODES, "term": "IB9"}))
        self.assertEqual(self.status_of(output, "defines"), "fail", output)
        self.assertIn("defines 'IB9', which does not appear in this entry's `evidence`", output)
        self.assertEqual(code, 1, output)

    def test_the_same_declaration_twice_is_refused(self):
        code, output = self.mutate("ib3-authorized-ibcs",
                                   lambda e: e["defines"].append(
                                       {"vocabulary": CODES, "term": "IB3"}))
        self.assertEqual(self.status_of(output, "defines"), "fail", output)
        self.assertIn("more than once", output)

    def test_a_derived_entry_carrying_defines_is_refused(self):
        document = trial_map()
        document["entries"].append({
            "id": "acetal-is-an-ibc-liquid", "name": "Acetal travels in an IBC",
            "kind": "value", "scope": "in", "clarity": "clear", "status": "mapped",
            "derivedFrom": ["acetal-column-7", "ib2-authorized-ibcs"],
            "defines": defines(CODES, "IB2")})
        code, output = self.run_checks(document)
        self.assertEqual(self.status_of(output, "derived"), "fail", output)
        self.assertIn("is derived and carries `defines`", output)
        self.assertEqual(code, 1, output)

    #: The committed maps that declare `defines`: trial 10's, whose corpus forced 0045; trial
    #: 11's, whose corpus prints no index for `vocabularyFrom` to name; and trial 12's, which is
    #: the first to declare one for a corpus that *does* print an index -- the SRD's Rules
    #: Glossary is on pp. 176-191, outside its slice, so the terms this chapter defines are
    #: distributed over the entries that define them exactly as a corpus with no index would be
    #: (#433). Every other map predates the field, so its verdict is `NOT VERIFIED -- no entry
    #: declares `defines``, a skip with no subject that fails nothing.
    DECLARING = {os.path.join("examples", "hazmat-172-table", "corpus-map.json"),
             os.path.join("examples", "frcp-6-12-81", "corpus-map.json"),
             os.path.join("examples", "srd-52-playing-the-game", "corpus-map.json")}

    def test_only_the_map_that_forced_the_field_carries_defines(self):
        """A map gaining `defines` is a change to how a vocabulary is read, and it is named here.

        This asserted that **no** committed map carried the field, which was true while 0045 had
        no corpus mapped against it and stopped being true the day one was. The guard it was
        written for -- that adopting the field is deliberate rather than incidental -- is kept by
        naming which maps declare it; `check-map.py --only defines` is what holds each
        declaration to its own evidence.
        """
        root = os.path.join(ROOT, "examples")
        maps = [os.path.join(directory, name)
                for directory, _, names in os.walk(root) for name in names
                if name.startswith("corpus-map") and name.endswith(".json")]
        self.assertTrue(maps, "no committed map was examined -- this test proves nothing")
        declaring = set()
        for path in maps:
            with self.subTest(map=os.path.relpath(path, ROOT)):
                with open(path, encoding="utf-8") as handle:
                    document = json.load(handle)
                declared = [e.get("id") for e in document.get("entries") or []
                            if isinstance(e, dict) and "defines" in e]
                if os.path.relpath(path, ROOT) in self.DECLARING:
                    self.assertTrue(declared, "the map 0045 was decided on declares no `defines`")
                    declaring.add(os.path.relpath(path, ROOT))
                else:
                    self.assertEqual(declared, [])
        self.assertEqual(declaring, self.DECLARING)


if __name__ == "__main__":
    unittest.main()
