#!/usr/bin/env python3
"""One printed code can name more than one rule, and the vocabulary keeps all of them (0044).

[#311](https://github.com/brandonifco/rules-factory/issues/311), found by trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)). 49 CFR § 172.102(c)(4) states
it outright:

> Table 1 authorizes IBCs for specific proper shipping names through the use of IB Codes assigned
> in the § 172.101 table … Large Packagings are authorized for the Packing Group III entries of
> specific proper shipping names when either special provision **IB3** or **IB8** is assigned to
> that entry in the § 172.101 Table.

So `IB3` in column 7 authorises IBCs unconditionally (§ 172.102 table 2) *and* Large Packagings
for PG III only (§ 172.102 table 4). The original reader built a `dict` of one target per term, so
the **last** declaration won and the first was discarded with no diagnostic anywhere.

**The vocabulary is now distributed** ([0045](../../../docs/decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md),
[#314](https://github.com/brandonifco/rules-factory/issues/314)): § 172.102 prints no passage
listing its codes, so each defining entry declares the term its own evidence prints, and two
entries declaring `IB3` is what a two-rule code *is*. 0044's cardinality stops being a special
case of one entry's `crossReferences` and becomes the ordinary sum of two declarations.

Watched here:

  * `IB3` resolves to **both** entries, and `IB8` expresses the same shape;
  * **the order the map states the defining entries in changes nothing**, which is the whole of
    what was wrong;
  * a code with two targets is accounted for only when the pointing cell points at **both**, so
    deleting either target's `crossReference` is reported;
  * one entry declaring the *same* term twice is **refused**, by `check-map.py --only defines`;
  * a one-target code behaves exactly as it did, and `defined-term-use`'s single-entry vocabulary
    -- repeated-pair check included -- is untouched beside it.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))

sys.path.insert(0, TOOLS)
try:
    from mapcontract.entry import defined_vocabulary
    from mapper import pointers, protocol
finally:
    sys.path.remove(TOOLS)

ROW = '§ 172.101 table 3, row [column 2 = "Acetic acid solution, with more than 10 percent and less than 50 percent acid, by mass"], column 7'

#: The name the two mechanisms read, and the two rules § 172.102 states under `IB3` and `IB8`.
VOCABULARY = "special-provision-codes"
IB3_IBCS = "ib3-authorized-ibcs"
IB3_LARGE = "ib3-authorized-large-packagings"
IB8_IBCS = "ib8-authorized-ibcs"
IB8_LARGE = "ib8-authorized-large-packagings"

#: Which entry defines which code, as the corpus states them: two tables under `IB3`, two under
#: `IB8`, one under `T4`.
CITATIONS = {
    IB3_IBCS: '§ 172.102 table 2, row [column 1 = "IB3"]',
    IB3_LARGE: '§ 172.102 table 4, row [column 1 = "IB3"]',
    IB8_IBCS: '§ 172.102 table 2, row [column 1 = "IB8"]',
    IB8_LARGE: '§ 172.102 table 5, row [column 1 = "IB8"]',
    "t4-portable-tank": '§ 172.102 table 6, row [column 1 = "T4"]',
}


def defining(entry_id, term):
    """One § 172.102 row, declaring the one code its own evidence prints."""
    return {"id": entry_id,
            "locator": {"sourceId": "cfr-49-172.102", "citation": CITATIONS[entry_id]},
            "evidence": f"{term} Authorized packagings, as this row states them.",
            "defines": [{"vocabulary": VOCABULARY, "term": term}]}


BOTH_IB3 = [(IB3_IBCS, "IB3"), (IB3_LARGE, "IB3")]


def document(definitions, row_references=()):
    """A map whose one column 7 cell points with `IB3`, over the given defining entries."""
    entries = [defining(entry_id, term) for entry_id, term in definitions]
    entries.append({"id": "band-3-provisions",
                    "locator": {"sourceId": "cfr-49-172.101", "citation": ROW},
                    "evidence": "148, IB3, T4, TP1",
                    "crossReferences": [{"cites": cites, "resolvedBy": target}
                                        for cites, target in row_references]})
    return {"schemaVersion": 1, "corpus": "cfr-49-172.101", "entries": entries}


MECHANISM = {"mechanism": "coded-pointer", "column": 7, "vocabulary": VOCABULARY}
DECLARE_BOTH = [("IB3", IB3_IBCS), ("IB3", IB3_LARGE)]


class OneCodeNamesTwoRules(unittest.TestCase):
    """Proofs 1 and 2: IB3 keeps both targets, and IB8 expresses the same shape."""

    def test_ib3_resolves_to_both_the_table_2_and_the_table_4_entry(self):
        terms = defined_vocabulary(document(BOTH_IB3), VOCABULARY)
        self.assertEqual(terms, {"IB3": [IB3_IBCS, IB3_LARGE]})

    def test_ib8_expresses_the_same_shape(self):
        terms = defined_vocabulary(
            document(BOTH_IB3 + [(IB8_IBCS, "IB8"), (IB8_LARGE, "IB8")]), VOCABULARY)
        self.assertEqual(terms["IB8"], [IB8_IBCS, IB8_LARGE])
        self.assertEqual(terms["IB3"], [IB3_IBCS, IB3_LARGE])

    def test_a_vocabulary_no_entry_defines_is_refused(self):
        """The check that replaces "vocabularyFrom names no entry": a name nothing defines."""
        problems = protocol._check_defined_vocabulary(
            "pointerMechanisms[0]", {"mechanism": "coded-pointer", "column": 7,
                                     "vocabulary": "codes-nobody-defines"},
            document(BOTH_IB3))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("codes-nobody-defines", problems[0])

    def test_a_term_of_another_vocabulary_does_not_join_this_one(self):
        """Column 6's `3` is a hazard label; column 7's numeric codes are provisions."""
        doc = document(BOTH_IB3)
        doc["entries"].append({"id": "class-3-flammable-liquid",
                               "locator": {"sourceId": "cfr-49-172.101",
                                           "citation": '§ 172.101 table 1, row [column 1 = "3"]'},
                               "evidence": "3 Flammable liquid",
                               "defines": [{"vocabulary": "hazard-label-codes", "term": "3"}]})
        self.assertEqual(sorted(defined_vocabulary(doc, VOCABULARY)), ["IB3"])
        self.assertEqual(sorted(defined_vocabulary(doc, "hazard-label-codes")), ["3"])


class DeclarationOrderDoesNotDecide(unittest.TestCase):
    """Proof 3: the defect was that the last declaration won. Neither wins now."""

    def test_the_two_orders_give_the_same_vocabulary(self):
        forwards = defined_vocabulary(document(BOTH_IB3), VOCABULARY)
        backwards = defined_vocabulary(document(list(reversed(BOTH_IB3))), VOCABULARY)
        self.assertEqual(set(forwards["IB3"]), set(backwards["IB3"]))
        self.assertEqual(len(forwards["IB3"]), 2)

    def test_the_two_orders_report_the_same_missing_targets(self):
        for order in (BOTH_IB3, list(reversed(BOTH_IB3))):
            with self.subTest(order=[entry_id for entry_id, _ in order]):
                naming = self.ib3(document(order))
                self.assertEqual(set(naming.missing), {IB3_IBCS, IB3_LARGE})

    def test_neither_target_alone_satisfies_the_pointer(self):
        for kept in (IB3_IBCS, IB3_LARGE):
            with self.subTest(declared=kept):
                naming = self.ib3(document(BOTH_IB3, [("IB3", kept)]))
                self.assertEqual(naming.missing,
                                 [t for t in (IB3_IBCS, IB3_LARGE) if t != kept])

    def test_declaring_both_satisfies_it(self):
        naming = self.ib3(document(BOTH_IB3, DECLARE_BOTH))
        self.assertEqual(naming.missing, [])

    @staticmethod
    def ib3(doc):
        return [n for n in pointers.detect_coded(doc, MECHANISM) if n.term == "IB3"][0]


class DeletingEitherTargetIsVisible(unittest.TestCase):
    """Proof 4: a rule that loses its pointer is reported, whichever of the two it is."""

    def report(self, row_references, definitions=BOTH_IB3):
        doc = document(definitions, row_references)
        return pointers.report({"pointerMechanisms": [MECHANISM]}, doc)

    def test_declaring_both_leaves_ib3_out_of_the_findings(self):
        lines, detected, undeclared = self.report(DECLARE_BOTH)
        self.assertTrue(detected)
        self.assertEqual([n.term for n in undeclared if n.term == "IB3"], [])

    def test_deleting_the_ibc_target_is_reported_by_name(self):
        lines, _, undeclared = self.report([("IB3", IB3_LARGE)])
        said = [line for line in lines if IB3_IBCS in line]
        self.assertEqual(len(said), 1, lines)
        self.assertIn("2 entries state it", said[0])
        self.assertIn("IB3", [n.term for n in undeclared])

    def test_deleting_the_large_packaging_target_is_reported_by_name(self):
        lines, _, undeclared = self.report([("IB3", IB3_IBCS)])
        said = [line for line in lines if IB3_LARGE in line]
        self.assertEqual(len(said), 1, lines)
        self.assertIn("2 entries state it", said[0])

    def test_deleting_a_definition_altogether_is_visible(self):
        """One defining entry removed: the pointer is satisfied and the rule is gone.

        `--only references` cannot see it -- the cell declares one target and that target
        exists -- so what says it is that the code now names one rule where it named two.
        """
        lines, _, _ = self.report([("IB3", IB3_IBCS)], definitions=[(IB3_IBCS, "IB3")])
        self.assertEqual([line for line in lines if IB3_LARGE in line], [])
        self.assertIn("1 term(s) defined by 1 entr(ies) (0045-0046)", lines[0])

    def test_a_one_target_code_says_nothing_about_a_count(self):
        """The count is printed only where it tells the reader something."""
        lines, _, _ = self.report([], definitions=BOTH_IB3 + [("t4-portable-tank", "T4")])
        said = [line for line in lines if "t4-portable-tank" in line]
        self.assertEqual(len(said), 1, lines)
        self.assertNotIn("entries state it", said[0])


class ADuplicateDeclarationIsReported(unittest.TestCase):
    """Proof 5: the same term twice says nothing, and is not swallowed.

    Where 0044 refused a repeated `crossReferences` pair on a vocabulary entry, 0045 refuses a
    repeated `defines` item on a defining entry -- `check-map.py --only defines`, watched in
    `tests/mapvalidator/test_check_map.py`. The reader still returns it once, so the vocabulary
    a duplicate produces is the vocabulary without it.
    """

    def test_the_vocabulary_holds_it_once(self):
        doc = document([(IB3_IBCS, "IB3")])
        doc["entries"][0]["defines"].append({"vocabulary": VOCABULARY, "term": "IB3"})
        self.assertEqual(defined_vocabulary(doc, VOCABULARY), {"IB3": [IB3_IBCS]})

    def test_a_duplicate_does_not_change_what_the_pointer_needs(self):
        doc = document([(IB3_IBCS, "IB3")], [("IB3", IB3_IBCS)])
        doc["entries"][0]["defines"].append({"vocabulary": VOCABULARY, "term": "IB3"})
        one = [n for n in pointers.detect_coded(doc, MECHANISM) if n.term == "IB3"][0]
        self.assertEqual(one.missing, [])


class DefinedTermUseIsUntouched(unittest.TestCase):
    """0044's single-entry vocabulary still reads as it did, repeated pair included.

    The SRD's `condition-list` really does print all fifteen terms, so its `vocabularyFrom`
    representation is valid and 0045 does not migrate it.
    """

    @staticmethod
    def listing(pairs):
        return {"id": "condition-list",
                "locator": {"sourceId": "srd-5.2.1", "citation": "Conditions"},
                "evidence": "This glossary defines these conditions: Blinded Charmed.",
                "crossReferences": [{"cites": cites, "resolvedBy": target}
                                    for cites, target in pairs]}

    def a_map(self, pairs):
        return {"schemaVersion": 1, "corpus": "srd-5.2.1", "entries": [
            self.listing(pairs),
            {"id": "blinded", "locator": {"sourceId": "srd-5.2.1", "citation": "Blinded"},
             "evidence": "While you have the Blinded condition, you cannot see."},
            {"id": "charmed", "locator": {"sourceId": "srd-5.2.1", "citation": "Charmed"},
             "evidence": "While you have the Charmed condition, you cannot attack."}]}

    def test_a_term_still_reads_out_of_one_entrys_cross_references(self):
        self.assertEqual(protocol.vocabulary_of(self.listing([("Blinded", "blinded")])),
                         {"Blinded": ["blinded"]})

    def test_a_repeated_pair_is_still_reported(self):
        pairs = [("Blinded", "blinded"), ("Blinded", "blinded")]
        problems = protocol._check_vocabulary(
            "pointerMechanisms[0]",
            {"mechanism": "defined-term-use", "vocabularyFrom": "condition-list"},
            self.a_map(pairs))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("more than once", problems[0])

    def test_two_different_targets_are_not_reported_as_a_duplicate(self):
        problems = protocol._check_vocabulary(
            "pointerMechanisms[0]",
            {"mechanism": "defined-term-use", "vocabularyFrom": "condition-list"},
            self.a_map([("Blinded", "blinded"), ("Blinded", "charmed")]))
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
