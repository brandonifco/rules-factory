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
for PG III only (§ 172.102 table 4). `vocabulary_of` built a `dict` of one target per term, so the
**last** declaration won and the first was discarded — with no diagnostic anywhere, because both
targets were real entries and `_check_vocabulary` only asked that much.

Watched here:

  * `IB3` resolves to **both** entries, and `IB8` expresses the same shape;
  * **declaration order does not change the result**, which is the whole of what was wrong;
  * a code with two targets is accounted for only when the entry points at **both**, so deleting
    either target's `crossReference` is reported;
  * the *same* target declared twice is **reported**, not collapsed in silence;
  * a one-target vocabulary behaves exactly as it did, and so does `defined-term-use`.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import copy
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

ROW = '§ 172.101 table 3, row [column 2 = "Acetic acid solution, with more than 10 percent and less than 50 percent acid, by mass"], column 7'

#: The two rules § 172.102 states under `IB3`, and the two it states under `IB8`.
IB3_IBCS = "ib3-authorized-ibcs"
IB3_LARGE = "ib3-authorized-large-packagings"
IB8_IBCS = "ib8-authorized-ibcs"
IB8_LARGE = "ib8-authorized-large-packagings"


def stub(entry_id, citation="§ 172.102(c)"):
    return {"id": entry_id, "locator": {"sourceId": "cfr-49-172.102", "citation": citation},
            "evidence": f"{entry_id} states a rule."}


def vocabulary(pairs):
    return {"id": "special-provision-codes",
            "locator": {"sourceId": "cfr-49-172.102", "citation": "§ 172.102(c)"},
            "evidence": "The following tables list, and set forth the requirements of, the "
                        "special provisions referred to in column 7 of the § 172.101 table.",
            "crossReferences": [{"cites": cites, "resolvedBy": target}
                                for cites, target in pairs]}


def document(pairs, row_references=()):
    """A map whose one column 7 cell points with `IB3`, over a vocabulary of `pairs`."""
    return {"schemaVersion": 1, "corpus": "cfr-49-172.101", "entries": [
        vocabulary(pairs),
        stub(IB3_IBCS, '§ 172.102 table 2, row [column 1 = "IB3"]'),
        stub(IB3_LARGE, '§ 172.102 table 4, row [column 1 = "IB3"]'),
        stub(IB8_IBCS, '§ 172.102 table 2, row [column 1 = "IB8"]'),
        stub(IB8_LARGE, '§ 172.102 table 5, row [column 1 = "IB8"]'),
        {"id": "band-3-provisions",
         "locator": {"sourceId": "cfr-49-172.101", "citation": ROW},
         "evidence": "148, IB3, T4, TP1",
         "crossReferences": [{"cites": cites, "resolvedBy": target}
                             for cites, target in row_references]},
    ]}


MECHANISM = {"mechanism": "coded-pointer", "column": 7,
             "vocabularyFrom": "special-provision-codes"}
BOTH_IB3 = [("IB3", IB3_IBCS), ("IB3", IB3_LARGE)]


class OneCodeNamesTwoRules(unittest.TestCase):
    """Proofs 1 and 2: IB3 keeps both targets, and IB8 expresses the same shape."""

    def test_ib3_resolves_to_both_the_table_2_and_the_table_4_entry(self):
        terms = protocol.vocabulary_of(vocabulary(BOTH_IB3))
        self.assertEqual(terms, {"IB3": [IB3_IBCS, IB3_LARGE]})

    def test_ib8_expresses_the_same_shape(self):
        terms = protocol.vocabulary_of(vocabulary(BOTH_IB3 + [("IB8", IB8_IBCS),
                                                              ("IB8", IB8_LARGE)]))
        self.assertEqual(terms["IB8"], [IB8_IBCS, IB8_LARGE])
        self.assertEqual(terms["IB3"], [IB3_IBCS, IB3_LARGE])

    def test_both_targets_are_checked_against_the_map(self):
        """A second target that is not an entry is reported, as the first already was."""
        pairs = [("IB3", IB3_IBCS), ("IB3", "ib3-large-packagings-nobody-wrote")]
        problems = protocol._check_vocabulary("pointerMechanisms[0]", MECHANISM, document(pairs))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("ib3-large-packagings-nobody-wrote", problems[0])
        self.assertIn("which is not an entry", problems[0])


class DeclarationOrderDoesNotDecide(unittest.TestCase):
    """Proof 3: the defect was that the last declaration won. Neither wins now."""

    def test_the_two_orders_give_the_same_vocabulary(self):
        forwards = protocol.vocabulary_of(vocabulary(BOTH_IB3))
        backwards = protocol.vocabulary_of(vocabulary(list(reversed(BOTH_IB3))))
        self.assertEqual(set(forwards["IB3"]), set(backwards["IB3"]))
        self.assertEqual(len(forwards["IB3"]), 2)

    def test_the_two_orders_report_the_same_missing_targets(self):
        for pairs in (BOTH_IB3, list(reversed(BOTH_IB3))):
            with self.subTest(order=[t for _, t in pairs]):
                naming = self.ib3(document(pairs))
                self.assertEqual(set(naming.missing), {IB3_IBCS, IB3_LARGE})

    def test_neither_target_alone_satisfies_the_pointer(self):
        for kept in (IB3_IBCS, IB3_LARGE):
            with self.subTest(declared=kept):
                naming = self.ib3(document(BOTH_IB3, [("IB3", kept)]))
                self.assertEqual(naming.missing,
                                 [t for t in (IB3_IBCS, IB3_LARGE) if t != kept])

    def test_declaring_both_satisfies_it(self):
        naming = self.ib3(document(BOTH_IB3, BOTH_IB3))
        self.assertEqual(naming.missing, [])

    @staticmethod
    def ib3(doc):
        return [n for n in pointers.detect_coded(doc, MECHANISM) if n.term == "IB3"][0]


class DeletingEitherTargetIsVisible(unittest.TestCase):
    """Proof 4: a rule that loses its pointer is reported, whichever of the two it is."""

    def report(self, row_references):
        doc = document(BOTH_IB3, row_references)
        return pointers.report({"pointerMechanisms": [MECHANISM]}, doc)

    def test_declaring_both_leaves_ib3_out_of_the_findings(self):
        lines, detected, undeclared = self.report(BOTH_IB3)
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

    def test_a_one_target_code_says_nothing_about_a_count(self):
        """The count is printed only where it tells the reader something."""
        pairs = BOTH_IB3 + [("T4", "t4-portable-tank")]
        doc = document(pairs)
        doc["entries"].append(stub("t4-portable-tank",
                                   '§ 172.102 table 6, row [column 1 = "T4"]'))
        lines, _, _ = pointers.report({"pointerMechanisms": [MECHANISM]}, doc)
        said = [line for line in lines if "t4-portable-tank" in line]
        self.assertEqual(len(said), 1, lines)
        self.assertNotIn("entries state it", said[0])


class ADuplicateDeclarationIsReported(unittest.TestCase):
    """Proof 5: the same term and the same target twice says nothing, and is not swallowed."""

    PAIRS = [("IB3", IB3_IBCS), ("IB3", IB3_IBCS)]

    def test_the_vocabulary_holds_it_once(self):
        self.assertEqual(protocol.vocabulary_of(vocabulary(self.PAIRS)), {"IB3": [IB3_IBCS]})

    def test_and_the_check_says_it_was_declared_twice(self):
        problems = protocol._check_vocabulary("pointerMechanisms[0]", MECHANISM,
                                              document(self.PAIRS))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("more than once", problems[0])
        self.assertIn("IB3", problems[0])

    def test_two_different_targets_are_not_reported_as_a_duplicate(self):
        self.assertEqual(
            protocol._check_vocabulary("pointerMechanisms[0]", MECHANISM, document(BOTH_IB3)), [])

    def test_a_duplicate_does_not_change_what_the_pointer_needs(self):
        one = DeclarationOrderDoesNotDecide.ib3(document(self.PAIRS, [("IB3", IB3_IBCS)]))
        self.assertEqual(one.missing, [])


class AOneTargetVocabularyIsUnchanged(unittest.TestCase):
    """Proof 6: every vocabulary that names one entry per term behaves as it always did."""

    SINGLE = [("IB3", IB3_IBCS), ("IB8", IB8_IBCS)]

    def test_each_term_still_names_its_entry(self):
        self.assertEqual(protocol.vocabulary_of(vocabulary(self.SINGLE)),
                         {"IB3": [IB3_IBCS], "IB8": [IB8_IBCS]})

    def test_a_declared_pointer_is_satisfied(self):
        naming = DeclarationOrderDoesNotDecide.ib3(document(self.SINGLE, [("IB3", IB3_IBCS)]))
        self.assertEqual(naming.missing, [])

    def test_an_undeclared_pointer_is_reported(self):
        naming = DeclarationOrderDoesNotDecide.ib3(document(self.SINGLE))
        self.assertEqual(naming.missing, [IB3_IBCS])

    def test_a_token_the_vocabulary_does_not_declare_is_still_reported(self):
        lines, _, undeclared = pointers.report({"pointerMechanisms": [MECHANISM]},
                                               document(self.SINGLE))
        self.assertIn("TP1", [n.term for n in undeclared])
        self.assertTrue(any("which the vocabulary does not declare" in line and "TP1" in line
                            for line in lines), lines)

    def test_a_vocabulary_entry_with_no_crossReferences_is_still_refused(self):
        doc = document(self.SINGLE)
        doc["entries"][0] = {k: v for k, v in doc["entries"][0].items() if k != "crossReferences"}
        problems = protocol._check_vocabulary("pointerMechanisms[0]", MECHANISM, doc)
        self.assertEqual(len(problems), 1)
        self.assertIn("states no vocabulary", problems[0])


class DefinedTermUseIsUnchanged(unittest.TestCase):
    """The other mechanism reading a vocabulary keeps its own behaviour, including 0026's
    reading that a declaration whose `cites` *names* the term is about that term."""

    TERMS = {"id": "condition-list",
             "locator": {"sourceId": "srd", "citation": "Rules Glossary / Condition / p. 179"},
             "evidence": "This glossary defines these conditions: Blinded Grappled",
             "crossReferences": [{"cites": "Blinded", "resolvedBy": "blinded"},
                                 {"cites": "Grappled", "resolvedBy": "grappled"}]}

    def base(self):
        return {"schemaVersion": 1, "corpus": "srd", "entries": [
            copy.deepcopy(self.TERMS),
            {"id": "blinded", "locator": {"sourceId": "srd", "citation": "Blinded / p. 179"},
             "evidence": "While you have the Blinded condition you cannot see."},
            {"id": "grappled", "locator": {"sourceId": "srd", "citation": "Grappled / p. 180"},
             "evidence": "While you have the Grappled condition your speed is 0."},
            {"id": "a-rule", "locator": {"sourceId": "srd", "citation": "Attack / p. 181"},
             "evidence": "A creature with the Blinded condition has Disadvantage.",
             "crossReferences": []},
        ]}

    @staticmethod
    def naming(doc, entry_id="a-rule"):
        found = [n for n in pointers.detect(doc, doc["entries"][0]) if n.entry_id == entry_id]
        return found[0] if found else None

    def test_a_naming_outside_the_defining_passage_is_a_pointer(self):
        doc = self.base()
        self.assertEqual([(n.entry_id, n.term) for n in pointers.detect(doc, doc["entries"][0])
                          if n.entry_id == "a-rule"], [("a-rule", "Blinded")])
        self.assertEqual(self.naming(doc).missing, ["blinded"])

    def test_a_naming_inside_the_defining_passage_is_not(self):
        self.assertEqual([n for n in pointers.detect(self.base(), self.TERMS)
                          if n.entry_id == "blinded"], [])

    def test_a_declaration_whose_cites_names_the_term_satisfies_it(self):
        doc = self.base()
        doc["entries"][3]["crossReferences"] = [{"cites": "the Blinded condition",
                                                 "resolvedBy": "blinded"}]
        self.assertEqual(self.naming(doc).missing, [])

    def test_a_declaration_resolving_somewhere_else_does_not(self):
        doc = self.base()
        doc["entries"][3]["crossReferences"] = [{"cites": "Blinded", "resolvedBy": "grappled"}]
        self.assertEqual(self.naming(doc).missing, ["blinded"])


if __name__ == "__main__":
    unittest.main()
