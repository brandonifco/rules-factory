#!/usr/bin/env python3
"""Several map packages read as one (0067, #446).

Three things are watched, because each is a way a composition could be wrong in silence:

  * **identity.** An entry id is unique in a map and never was across maps -- `round-down` names
    three entries over the four SRD maps -- so a composition qualifies every id by its package,
    and every reference to one inside that package moves with it. A single package is not
    qualified, so an engine produced from one map does not churn.
  * **compatibility.** Packages that are not readings of one ruleset over one corpus are refused,
    each by its own rule and with its own message.
  * **supersession.** What says two entries are one passage is the span their evidence occupies in
    the corpus. Text alone merges the two printings of *Round Down*; the citation alone misses one
    passage two mappers gave different heading paths. A quote the corpus repeats has no span, and
    the composition reports it and merges nothing.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.join(os.path.dirname(os.path.dirname(HERE)), "factory")
sys.path.insert(0, FACTORY)
try:
    import compose
    import overlay
    import semantics
finally:
    sys.path.remove(FACTORY)

CORPUS = ("A player rolls a die. The winner moves first. Round down if you end up with a "
          "fraction. A token moves once. Round down if you end up with a fraction.")


class FakeIntake:
    """What `compose` reads of an `intake.Intake`, and nothing else."""

    def __init__(self, package_id, entries, version="1.0.0", corpus="demo",
                 content_hash="a" * 64, derivation="demo-1", randomness="none"):
        self.package_id = package_id
        self.version = version
        self.randomness = randomness
        self.map = {"schemaVersion": 1, "corpus": corpus,
                    "baseline": {"contentHash": content_hash, "hashDerivation": derivation},
                    "entries": entries}
        self.corpora = [{"sourceId": corpus, "path": f"{corpus}.txt",
                         "corpus": {"contentHash": content_hash, "hashDerivation": derivation,
                                    "committedPath": f"{corpus}.txt"}}]


def entry(entry_id, evidence, scope="in", status="mapped", **rest):
    made = {"id": entry_id, "kind": "value", "scope": scope, "clarity": "clear",
            "locator": {"sourceId": "demo", "citation": f"Rules / {entry_id}"},
            "evidence": evidence, "status": status, "note": "."}
    made.update(rest)
    return made


class TheIdentityIsThePackageAndTheId(unittest.TestCase):
    def test_one_package_is_not_qualified(self):
        only = FakeIntake("RulesFactory.Maps.Demo", [entry("a", "A player rolls a die.")])
        composed = compose.compose([only])
        self.assertFalse(composed.composed)
        self.assertEqual(["a"], [e["id"] for e in composed.map["entries"]])
        self.assertIn("one package: entry ids are unqualified", composed.lines()[0])

    def test_several_packages_qualify_every_id(self):
        composed = compose.compose([
            FakeIntake("RulesFactory.Maps.One", [entry("a", "A player rolls a die.")]),
            FakeIntake("RulesFactory.Maps.Two", [entry("a", "A token moves once.")]),
        ])
        self.assertTrue(composed.composed)
        self.assertEqual(["One.a", "Two.a"], [e["id"] for e in composed.map["entries"]])

    def test_a_qualified_id_can_name_an_overlay_file_and_a_csharp_member(self):
        qualified = compose.qualified("RulesFactory.Maps.Srd52Combat", "round-down")
        self.assertEqual("overlay/Srd52Combat.round-down.json", overlay.path_for(qualified))
        self.assertEqual("Srd52CombatRoundDown", semantics.pascal(qualified))

    def test_every_reference_inside_the_package_moves_with_the_id(self):
        composed = compose.compose([
            FakeIntake("RulesFactory.Maps.One", [
                entry("a", "A player rolls a die."),
                entry("b", "The winner moves first.", dependsOn=["a"], enabledBy=["a"],
                      suspendedBy=["a"], crossReferences=[{"cites": "die", "resolvedBy": "a"}],
                      continuesDefinition={"definedBy": "a",
                                           "anchor": {"sourceId": "demo", "citation": "Rules / a"}}),
                entry("c", "A token moves once.", derivedFrom=["a", "b"]),
            ]),
            FakeIntake("RulesFactory.Maps.Two", [entry("a", "Round down if you end up with a fraction.")]),
        ])
        b = next(e for e in composed.map["entries"] if e["id"] == "One.b")
        for field in ("dependsOn", "enabledBy", "suspendedBy"):
            self.assertEqual(["One.a"], b[field], field)
        self.assertEqual("One.a", b["crossReferences"][0]["resolvedBy"])
        self.assertEqual("One.a", b["continuesDefinition"]["definedBy"])
        c = next(e for e in composed.map["entries"] if e["id"] == "One.c")
        self.assertEqual(["One.a", "One.b"], c["derivedFrom"])

    def test_a_reference_to_no_entry_of_the_package_is_left_alone(self):
        """A dangling reference is check-map.py's to refuse; renaming it would hide it."""
        composed = compose.compose([
            FakeIntake("RulesFactory.Maps.One", [entry("a", "A player rolls a die.",
                                                       dependsOn=["nowhere"])]),
            FakeIntake("RulesFactory.Maps.Two", [entry("b", "A token moves once.")]),
        ])
        self.assertEqual(["nowhere"], composed.map["entries"][0]["dependsOn"])


class PackagesThatAreNotOneReading(unittest.TestCase):
    def refusal(self, intakes):
        with self.assertRaises(compose.Refused) as caught:
            compose.compose(intakes)
        return str(caught.exception)

    def test_no_package_at_all(self):
        self.assertIn("composes nothing", self.refusal([]))

    def test_the_same_package_twice(self):
        one = FakeIntake("RulesFactory.Maps.One", [entry("a", "A player rolls a die.")])
        self.assertIn("composed twice", self.refusal([one, one]))

    def test_two_principal_corpora(self):
        self.assertIn("principal corpora", self.refusal([
            FakeIntake("RulesFactory.Maps.One", [entry("a", "x")], corpus="demo"),
            FakeIntake("RulesFactory.Maps.Two", [entry("b", "y")], corpus="other"),
        ]))

    def test_one_corpus_read_from_different_bytes(self):
        self.assertIn("different bytes", self.refusal([
            FakeIntake("RulesFactory.Maps.One", [entry("a", "x")], content_hash="a" * 64),
            FakeIntake("RulesFactory.Maps.Two", [entry("b", "y")], content_hash="b" * 64),
        ]))

    def test_two_baselines(self):
        one = FakeIntake("RulesFactory.Maps.One", [entry("a", "x")])
        two = FakeIntake("RulesFactory.Maps.Two", [entry("b", "y")])
        two.map["baseline"] = {"contentHash": "c" * 64, "hashDerivation": "demo-1"}
        two.corpora = one.corpora
        self.assertIn("different baselines", self.refusal([one, two]))

    def test_two_randomness_postures(self):
        self.assertIn("randomness", self.refusal([
            FakeIntake("RulesFactory.Maps.One", [entry("a", "x")], randomness="none"),
            FakeIntake("RulesFactory.Maps.Two", [entry("b", "y")], randomness="seeded"),
        ]))


class SupersessionIsTheSpanInTheCorpus(unittest.TestCase):
    def compose_two(self, declined, mapped):
        return compose.compose([
            FakeIntake("RulesFactory.Maps.One", [declined]),
            FakeIntake("RulesFactory.Maps.Two", [mapped]),
        ], {"demo": CORPUS})

    def test_a_declined_stub_inside_a_mapped_passage_is_superseded(self):
        composed = self.compose_two(
            entry("stub", "The winner moves first.", scope="out", status="declined"),
            entry("rule", "A player rolls a die. The winner moves first."))
        self.assertEqual({"One.stub": "Two.rule"}, composed.superseded)

    def test_a_passage_the_corpus_prints_twice_supersedes_nothing_and_is_reported(self):
        composed = self.compose_two(
            entry("stub", "Round down if you end up with a fraction.", scope="out",
                  status="declined"),
            entry("rule", "Round down if you end up with a fraction."))
        self.assertEqual({}, composed.superseded)
        self.assertEqual([("One.stub", 2)], composed.repeated)
        self.assertIn("prints this evidence 2 times", "\n".join(composed.lines()))

    def test_an_in_scope_entry_with_a_repeated_quote_is_not_reported(self):
        """0030's ordinary case, and never a supersession question: naming it would bury the ones
        that are."""
        composed = self.compose_two(
            entry("stub", "The winner moves first.", scope="out", status="declined"),
            entry("rule", "Round down if you end up with a fraction."))
        self.assertEqual([], composed.repeated)

    def test_a_mapped_entry_is_never_superseded(self):
        composed = self.compose_two(
            entry("kept", "The winner moves first."),
            entry("rule", "A player rolls a die. The winner moves first."))
        self.assertEqual({}, composed.superseded)

    def test_a_stub_is_not_superseded_by_its_own_package(self):
        composed = compose.compose([
            FakeIntake("RulesFactory.Maps.One", [
                entry("stub", "The winner moves first.", scope="out", status="declined"),
                entry("rule", "A player rolls a die. The winner moves first."),
            ]),
            FakeIntake("RulesFactory.Maps.Two", [entry("other", "A token moves once.")]),
        ], {"demo": CORPUS})
        self.assertEqual({}, composed.superseded)

    def test_a_stub_wider_than_the_mapped_passage_is_not_superseded(self):
        """The stub declined more than the entry holds, so the entry does not answer all of it."""
        composed = self.compose_two(
            entry("stub", "A player rolls a die. The winner moves first.", scope="out",
                  status="declined"),
            entry("rule", "The winner moves first."))
        self.assertEqual({}, composed.superseded)

    def test_without_the_corpus_nothing_is_superseded(self):
        composed = compose.compose([
            FakeIntake("RulesFactory.Maps.One", [entry("stub", "The winner moves first.",
                                                       scope="out", status="declined")]),
            FakeIntake("RulesFactory.Maps.Two",
                       [entry("rule", "A player rolls a die. The winner moves first.")]),
        ])
        self.assertEqual({}, composed.superseded)
        self.assertIn("no entry of one package names a passage another holds in scope",
                      "\n".join(composed.lines()))


class TheComposedDocument(unittest.TestCase):
    def test_it_carries_the_shared_corpus_baseline_and_every_entry(self):
        composed = compose.compose([
            FakeIntake("RulesFactory.Maps.One", [entry("a", "A player rolls a die.")]),
            FakeIntake("RulesFactory.Maps.Two", [entry("b", "A token moves once.")]),
        ])
        self.assertEqual(1, composed.map["schemaVersion"])
        self.assertEqual("demo", composed.map["corpus"])
        self.assertEqual("a" * 64, composed.map["baseline"]["contentHash"])
        self.assertEqual(2, len(composed.map["entries"]))

    def test_it_declares_no_extent(self):
        """Two page ranges are not one page range, and `--phase consumer` reads no extent: the
        composed document says nothing about coverage rather than something false."""
        composed = compose.compose([
            FakeIntake("RulesFactory.Maps.One", [entry("a", "A player rolls a die.")]),
            FakeIntake("RulesFactory.Maps.Two", [entry("b", "A token moves once.")]),
        ])
        self.assertNotIn("extent", composed.map)

    def test_one_corpus_is_carried_once_however_many_packages_cite_it(self):
        composed = compose.compose([
            FakeIntake("RulesFactory.Maps.One", [entry("a", "A player rolls a die.")]),
            FakeIntake("RulesFactory.Maps.Two", [entry("b", "A token moves once.")]),
        ])
        self.assertEqual(["demo"], [v["sourceId"] for v in composed.corpora])


if __name__ == "__main__":
    unittest.main()
