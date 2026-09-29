#!/usr/bin/env python3
"""The review-evidence model a produced engine's rails compute with (#532, decision 0071).

Each scenario is one the assignment names, run against `tools/factory/reviewscope.py`:

  A. a small isolated repair invalidates the repaired entry, what depends on it and the invariant
     anchored to it, and nothing else; the changed head alone requires no full review;
  B. a shared primitive invalidates every claim that reaches it, and nothing else;
  C. a changed corpus forces a full review; a changed entry of the map is bounded;
  D. a changed charter forces a full review, and says so;
  E. a tampered or stale attestation is refused;
  F. full FAIL, delta FAIL, delta PASS, final PASS: evidence is reused through the repairs, and the
     final review covers the whole slice;
  G. a delta packet is assembled from the state and the attestation alone;
  H. legacy evidence is never reused, and one full review establishes a reusable baseline.

`test_review_scope_mutations.py` breaks the module in the ways that would let a reviewer skip
something, and holds this file to catching each one. So the scenarios reach the module through
`MODULE`, which that file replaces.

Run: python3 -m pytest tools/tests/factory/test_review_scope.py
"""
import copy
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.join(os.path.dirname(os.path.dirname(HERE)), "factory")


def load(path=os.path.join(FACTORY, "reviewscope.py"), name="reviewscope_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load()
HEAD_1, HEAD_2, HEAD_3, HEAD_4 = ("1" * 40, "2" * 40, "3" * 40, "4" * 40)
BASE = "0" * 40
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def rule_file(letter, uses=()):
    """A hand-written rule for entry `letter`, calling the rules and primitives in `uses`."""
    name = letter.upper() + "Rule"
    calls = "\n".join(f"        {other}.Apply(request);" for other in uses)
    return (f"namespace Engine.Rules;\n\ninternal static class {name}\n{{\n"
            f"    internal static int Apply(int request)\n    {{\n{calls}\n        return request;\n    }}\n}}\n").encode()


def spec_for(letter):
    name = letter.upper() + "Rule"
    return (f"namespace Engine.Tests;\n\npublic class {name}Tests\n{{\n    [Fact]\n"
            f"    public void {name}_holds() => Assert.Equal(1, {name}.Apply(1));\n}}\n").encode()


class Engine:
    """A small engine of 26 entries, a..z, one rule file and one test file each.

    `d` depends on `c` in the map; `f`, `g` and `h` call the shared primitive `Dice`; invariant
    `X` is anchored to `c`'s rule file. Everything else is independent.
    """

    def __init__(self):
        self.entries = {}
        for letter in LETTERS:
            entry = {"id": letter, "name": f"Rule {letter}", "kind": "rule",
                     "locator": {"sourceId": "corpus-one", "citation": f"§ {letter}"},
                     "evidence": f"The rule {letter} holds.",
                     "dependsOn": ["c"] if letter == "d" else []}
            overlay = {"status": "implemented", "implementedIn": f"Rules/{letter.upper()}Rule.cs",
                       "tests": [{"name": f"{letter.upper()}Rule_holds", "mutation": f"return zero from rule {letter}"}]}
            self.entries[letter] = {"entry": entry, "overlay": overlay}
        self.files = {}
        for letter in LETTERS:
            uses = ("Dice",) if letter in "fgh" else ()
            self.files[f"src/Engine/Rules/{letter.upper()}Rule.cs"] = rule_file(letter, uses)
            self.files[f"tests/Engine.Tests/{letter.upper()}RuleTests.cs"] = spec_for(letter)
        self.files["src/Engine/Rules/Dice.cs"] = (b"namespace Engine.Rules;\n\ninternal static class Dice\n{\n"
                                                  b"    internal static int Apply(int faces) => faces;\n}\n")
        self.files["src/Engine/Generated/Registry.g.cs"] = b"// generated\n"
        self.files["src/Engine/Engine.csproj"] = b"<Project />\n"
        self.corpora = {"corpus-one": "a" * 64}
        self.charter = "c" * 64
        self.policy = "p" * 64
        self.factory = "f" * 40
        self.frame = {"schemaVersion": 1, "corpus": "corpus-one"}
        self.invariants = [{"id": "X", "statement": "a resolution never mutates its request",
                            "anchors": ["src/Engine/Rules/CRule.cs"]}]

    def copy(self):
        return copy.deepcopy(self)

    def snapshot(self, module=None):
        module = module or MODULE
        return module.Snapshot(
            entries=self.entries, slice=list(LETTERS), files=self.files,
            maps=[{"packageId": "Maps.One", "version": "1.0.0", "sha256": "m" * 64, "frame": self.frame}],
            corpora=self.corpora, charter=self.charter, policy_review=self.policy, factory=self.factory,
            generated_recorded={"src/Engine/Generated/Registry.g.cs": MODULE.sha256(self.files["src/Engine/Generated/Registry.g.cs"])},
            invariants=self.invariants)

    def state(self, module=None):
        return (module or MODULE).state(self.snapshot(module))


def attest(state, *, head, review_type, result, parent=None, impact=None, blocking=(), module=None):
    module = module or MODULE
    return module.build_attestation(
        project={"engine": "Engine", "repository": "example/engine", "enginePath": ""},
        reviewed_commit=head, base_commit=BASE, review_type=review_type,
        reviewer={"id": "semantic", "family": "test"},
        charter={"path": module.CHARTER, "sha256": state["units"]["charter"]},
        packet={"kind": "test", "sha256": "e" * 64},
        maps=[{"packageId": "Maps.One", "version": "1.0.0", "sha256": "m" * 64}],
        corpora=[{"sourceId": "corpus-one", "contentHash": "a" * 64}],
        current=state, result=result, blocking=blocking, parent=parent, impact_record=impact)


class Scenario(unittest.TestCase):
    module = None

    @property
    def m(self):
        return self.module or MODULE

    def baseline(self, engine=None):
        engine = engine or Engine()
        current = self.m.state(engine.snapshot(self.m))
        return engine, current, attest(current, head=HEAD_1, review_type="full", result="PASS",
                                       impact=self.m.impact(None, current), module=self.m)


class TestAnIsolatedRepair(Scenario):
    """A. The repair of one entry invalidates that entry, what depends on it, and its invariant."""

    def test_only_the_repaired_closure_is_invalidated(self):
        engine, _, prior = self.baseline()
        engine.files["src/Engine/Rules/CRule.cs"] = rule_file("c") + b"// clamp the lower bound\n"
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual(result["mode"], "delta", result["reasons"])
        self.assertEqual(result["review"], ["entry:c", "entry:d", "invariant:X"])
        self.assertEqual(len(result["retained"]), 24, "every unrelated entry keeps its evidence")
        self.assertIn("unit-changed: file:src/Engine/Rules/CRule.cs", result["invalidated"]["entry:d"],
                      "d depends on c in the map, so c's implementation is part of what d was reviewed on")

    def test_a_changed_head_alone_requires_nothing(self):
        engine, current, prior = self.baseline()
        # A new commit that changed no unit: a README edit, the attestation committed, a rebase.
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual((result["mode"], result["reasons"], result["review"]), ("none", [], []))
        self.assertTrue(self.m.may_carry(prior, result))

    def test_the_head_changing_is_not_a_reason_an_attestation_may_give(self):
        _, current, prior = self.baseline()
        document = attest(current, head=HEAD_2, review_type="full", result="PASS", parent=prior,
                          impact={"reasons": [{"code": "head-changed", "detail": "a new commit"}]}, module=self.m)
        problems = self.m.validate_attestation(document)
        self.assertTrue(any("head-changed" in p and "not a reason" in p for p in problems), problems)

    def test_a_full_review_after_a_prior_must_say_why(self):
        _, current, prior = self.baseline()
        document = attest(current, head=HEAD_2, review_type="full", result="PASS", parent=prior, impact={},
                          module=self.m)
        self.assertIn("a full review with a prior attestation names no reason for not being a delta",
                      self.m.validate_attestation(document))

    def test_a_new_file_the_repair_calls_is_a_dependency_added(self):
        engine, _, prior = self.baseline()
        engine.files["src/Engine/Rules/Clamp.cs"] = b"internal static class Clamp { }\n"
        engine.files["src/Engine/Rules/KRule.cs"] = rule_file("k", ("Clamp",))
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertIn("dependency-added: file:src/Engine/Rules/Clamp.cs", result["invalidated"]["entry:k"])

    def test_a_changed_file_no_claim_rests_on_is_reviewed_as_a_change(self):
        engine, _, prior = self.baseline()
        engine.files["src/Engine/Rules/Unused.cs"] = b"internal static class Unused { }\n"
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual(result["review"], ["change:src/Engine/Rules/Unused.cs"])

    def test_an_implementation_nobody_can_find_depends_on_every_source_file(self):
        engine = Engine()
        engine.entries["q"]["overlay"]["implementedIn"] = "Rules/Nowhere.cs"
        engine, _, prior = self.baseline(engine)
        engine.files["src/Engine/Rules/ZRule.cs"] = rule_file("z") + b"// z moves\n"
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertIn("entry:q", result["review"], "an unanchored claim is conservatively anchored to everything")


class TestASharedPrimitive(Scenario):
    """B. A primitive many entries use invalidates exactly those entries."""

    def test_every_claim_that_reaches_the_primitive_is_invalidated_and_no_other(self):
        engine, _, prior = self.baseline()
        engine.files["src/Engine/Rules/Dice.cs"] += b"// a d20 rolls 1..20, not 0..19\n"
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual(result["mode"], "delta", result["reasons"])
        self.assertEqual(result["review"], ["entry:f", "entry:g", "entry:h"])
        self.assertEqual(len(result["retained"]), 24)

    def test_a_primitive_everything_uses_is_too_broad_for_a_delta(self):
        engine = Engine()
        for letter in LETTERS:
            engine.files[f"src/Engine/Rules/{letter.upper()}Rule.cs"] = rule_file(letter, ("Dice",))
        engine, _, prior = self.baseline(engine)
        engine.files["src/Engine/Rules/Dice.cs"] += b"// changed\n"
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual(result["mode"], "full")
        self.assertEqual([r["code"] for r in result["reasons"]], ["repair-too-broad"])

    def test_a_global_using_is_foundational(self):
        engine = Engine()
        engine.files["src/Engine/Usings.cs"] = b"global using static Engine.Rules.Dice;\n"
        engine, _, prior = self.baseline(engine)
        engine.files["src/Engine/Usings.cs"] += b"global using System.Linq;\n"
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertIn("foundational-file-changed", [r["code"] for r in result["reasons"]])


class TestACorpusChange(Scenario):
    """C. The corpus moving cannot be bounded; the map moving one entry can."""

    def test_a_changed_corpus_forces_a_full_review(self):
        engine, _, prior = self.baseline()
        engine.corpora["corpus-one"] = "b" * 64
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual(result["mode"], "full")
        self.assertEqual([r["code"] for r in result["reasons"]], ["governing-corpus-changed"])
        self.assertIn("corpus:corpus-one", result["reasons"][0]["detail"])

    def test_one_entry_changed_in_the_map_is_bounded(self):
        engine, _, prior = self.baseline()
        engine.entries["m"]["entry"]["evidence"] = "The rule m holds, except on Sundays."
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual((result["mode"], result["review"]), ("delta", ["entry:m"]))

    def test_the_map_moving_broadly_is_a_full_review(self):
        engine, _, prior = self.baseline()
        for letter in LETTERS[:20]:
            engine.entries[letter]["entry"]["evidence"] += " (revised)"
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertIn("map-changed-broadly", [r["code"] for r in result["reasons"]])

    def test_the_map_frame_moving_is_a_full_review(self):
        engine, _, prior = self.baseline()
        engine.frame["baseline"] = "another"
        self.assertEqual([r["code"] for r in self.m.impact(prior, self.m.state(engine.snapshot(self.m)))["reasons"]],
                         ["map-frame-changed"])


class TestACharterChange(Scenario):
    """D. A new charter means the prior reviews answered a different question."""

    def test_the_charter_changing_forces_a_full_review_and_says_so(self):
        engine, _, prior = self.baseline()
        engine.charter = "d" * 64
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual(result["mode"], "full")
        (reason,) = result["reasons"]
        self.assertEqual(reason["code"], "charter-changed")
        self.assertIn("charter", reason["detail"])
        self.assertIn("formed under", self.m.FULL_REASONS["charter-changed"])
        document = attest(self.m.state(engine.snapshot(self.m)), head=HEAD_2, review_type="full", result="PASS",
                          parent=prior, impact=result, module=self.m)
        self.assertEqual(self.m.validate_attestation(document), [])
        self.assertEqual({r for i in document["invalidated"] for r in i["reasons"]}, {"full-review: charter-changed"})
        self.assertEqual(len(document["invalidated"]), 27, "re-baselining invalidates every prior claim, by name")

    def test_the_review_policy_changing_forces_a_full_review(self):
        engine, _, prior = self.baseline()
        engine.policy = "q" * 64
        self.assertEqual([r["code"] for r in self.m.impact(prior, self.m.state(engine.snapshot(self.m)))["reasons"]],
                         ["review-policy-changed"])


class TestATamperedOrStaleAttestation(Scenario):
    """E. What was recorded is the attestation; anything else is refused."""

    def binding(self, document, **overrides):
        values = {"recorded_digest": self.m.attestation_digest(self.recorded), "reviewed_commit": HEAD_1,
                  "maps": [{"packageId": "Maps.One", "sha256": "m" * 64}], "project": "Engine"}
        values.update(overrides)
        return self.m.check_binding(document, **values)

    def setUp(self):
        _, self.current, self.recorded = self.baseline()

    def test_the_recorded_attestation_is_accepted(self):
        self.assertEqual(self.binding(self.recorded), [])

    def test_a_fail_rewritten_as_a_pass_is_refused(self):
        failed = attest(self.current, head=HEAD_1, review_type="full", result="FAIL",
                        blocking=[{"claim": "entry:c", "summary": "c accepts zero"}],
                        impact=self.m.impact(None, self.current), module=self.m)
        forged = copy.deepcopy(failed)
        forged["result"], forged["findings"]["blocking"] = "PASS", []
        problems = self.m.check_binding(forged, recorded_digest=self.m.attestation_digest(failed),
                                        reviewed_commit=HEAD_1, maps=[{"packageId": "Maps.One", "sha256": "m" * 64}],
                                        project="Engine")
        self.assertTrue(any("edited after it was recorded" in p for p in problems), problems)

    def test_an_attestation_of_another_head_is_refused(self):
        problems = self.binding(self.recorded, reviewed_commit=HEAD_2)
        self.assertTrue(any("not 2222" in p for p in problems), problems)

    def test_an_attestation_of_another_map_is_refused(self):
        problems = self.binding(self.recorded, maps=[{"packageId": "Maps.One", "sha256": "n" * 64}])
        self.assertTrue(any("declares" in p for p in problems), problems)

    def test_an_attestation_of_another_engine_is_refused(self):
        self.assertTrue(self.binding(self.recorded, project="Another"))

    def test_an_unprovable_prior_is_never_reused(self):
        result = self.m.impact(self.recorded, self.current, reusable=False)
        self.assertEqual([r["code"] for r in result["reasons"]], ["prior-attestation-unusable"])

    def test_a_stale_pass_is_not_carried_to_another_semantic_state(self):
        engine, _, prior = self.baseline()
        engine.files["src/Engine/Rules/ARule.cs"] += b"// moved\n"
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertFalse(self.m.may_carry(prior, result))

    def test_a_retained_claim_at_other_fingerprints_breaks_the_chain(self):
        engine, _, prior = self.baseline()
        engine.files["src/Engine/Rules/CRule.cs"] += b"// moved\n"
        current = self.m.state(engine.snapshot(self.m))
        result = self.m.impact(prior, current)
        delta = attest(current, head=HEAD_2, review_type="delta", result="PASS", parent=prior, impact=result,
                       module=self.m)
        self.assertEqual(self.m.check_chain(delta, prior), [])
        forged = copy.deepcopy(delta)
        claim = next(c for c in forged["claims"] if c["id"] == "entry:a")
        claim["dependencies"]["entry:a"] = "0" * 64
        self.assertTrue(any("entry:a is retained at fingerprints" in p for p in self.m.check_chain(forged, prior)))


class TestAMultiRoundRepair(Scenario):
    """F. full FAIL -> repair -> delta FAIL -> repair -> delta PASS -> final PASS."""

    def test_the_chain_reuses_what_the_repairs_did_not_touch_and_the_final_rereads_everything(self):
        m = self.m
        engine = Engine()
        state_1 = m.state(engine.snapshot(m))
        round_1 = attest(state_1, head=HEAD_1, review_type="full", result="FAIL", impact=m.impact(None, state_1),
                         blocking=[{"claim": "entry:c", "summary": "c accepts a negative count", "category": "exact-min-max"}],
                         module=m)
        self.assertEqual(m.validate_attestation(round_1), [])

        engine.files["src/Engine/Rules/CRule.cs"] += b"// refuse a negative count\n"
        state_2 = m.state(engine.snapshot(m))
        impact_2 = m.impact(round_1, state_2)
        self.assertEqual(impact_2["review"], ["entry:c", "entry:d", "invariant:X"])
        round_2 = attest(state_2, head=HEAD_2, review_type="delta", result="FAIL", parent=round_1, impact=impact_2,
                         blocking=[{"claim": "entry:d", "summary": "d still reads c's old bound", "category": "exact-min-max"}],
                         module=m)
        self.assertEqual(m.validate_attestation(round_2), [])
        self.assertEqual(m.check_chain(round_2, round_1), [])

        engine.files["src/Engine/Rules/DRule.cs"] += b"// read the new bound\n"
        state_3 = m.state(engine.snapshot(m))
        impact_3 = m.impact(round_2, state_3)
        self.assertEqual(impact_3["review"], ["entry:d"], "c and X are retained: nothing they rest on moved since round 2")
        self.assertEqual(impact_3["carriedFindings"], ["entry:d"])
        round_3 = attest(state_3, head=HEAD_3, review_type="delta", result="PASS", parent=round_2, impact=impact_3,
                         module=m)
        self.assertEqual(m.validate_attestation(round_3), [])
        self.assertEqual(m.check_chain(round_3, round_2), [])
        self.assertEqual(m.status_for(round_3, "rules-verdict/semantic"), ("rules-verdict/semantic/delta", "success"),
                         "a delta PASS does not post the context the merge gate requires")

        round_4 = attest(state_3, head=HEAD_3, review_type="final", result="PASS", parent=round_3,
                         impact={"reasons": []}, module=m)
        self.assertEqual(m.validate_attestation(round_4), [])
        self.assertEqual(round_4["retained"], [])
        self.assertEqual(set(round_4["reviewed"]["entries"]), set(LETTERS), "the final review covers the whole slice")
        self.assertEqual(m.status_for(round_4, "rules-verdict/semantic"), ("rules-verdict/semantic", "success"))

        measured = m.telemetry([round_3, round_1, round_4, round_2])
        self.assertEqual((measured["fullReviews"], measured["deltaReviews"], measured["finalReviews"]), (1, 2, 1))
        self.assertEqual([r["claimsReviewed"] for r in measured["rounds"]], [27, 3, 1, 27])
        self.assertEqual(measured["claimsReused"], 24 + 26)
        self.assertEqual(measured["repairsBeforePass"], 2)
        self.assertEqual(measured["repeatedFindingCategories"], {"exact-min-max": 2})

    def test_a_delta_pass_that_skips_an_invalidated_claim_is_invalid(self):
        engine, _, prior = self.baseline()
        engine.files["src/Engine/Rules/CRule.cs"] += b"// moved\n"
        current = self.m.state(engine.snapshot(self.m))
        result = self.m.impact(prior, current)
        skipping = dict(result, review=["entry:c"])
        document = attest(current, head=HEAD_2, review_type="delta", result="PASS", parent=prior, impact=skipping,
                          module=self.m)
        self.assertTrue(any("was invalidated and not reviewed" in p for p in self.m.validate_attestation(document)))

    def test_a_finding_the_repair_did_not_touch_is_reviewed_again(self):
        engine = Engine()
        state_1 = self.m.state(engine.snapshot(self.m))
        failed = attest(state_1, head=HEAD_1, review_type="full", result="FAIL", impact=self.m.impact(None, state_1),
                        blocking=[{"claim": "entry:q", "summary": "q is wrong"}], module=self.m)
        engine.files["src/Engine/Rules/ARule.cs"] += b"// an unrelated edit\n"
        result = self.m.impact(failed, self.m.state(engine.snapshot(self.m)))
        self.assertIn("entry:q", result["review"], "a finding is answered by review, not by a fingerprint")

    def test_a_final_review_must_follow_a_chain(self):
        _, current, _ = self.baseline()
        document = attest(current, head=HEAD_1, review_type="final", result="PASS", impact={}, module=self.m)
        self.assertTrue(any("a final review has no parent" in p for p in self.m.validate_attestation(document)))

    def test_a_final_review_that_retains_anything_is_invalid(self):
        engine, _, prior = self.baseline()
        engine.files["src/Engine/Rules/CRule.cs"] += b"// moved\n"
        current = self.m.state(engine.snapshot(self.m))
        document = attest(current, head=HEAD_2, review_type="delta", result="PASS", parent=prior,
                          impact=self.m.impact(prior, current), module=self.m)
        document["reviewType"] = "final"
        self.assertTrue(any("must review every claim" in p for p in self.m.validate_attestation(document)))

    def test_the_attestation_is_deterministic(self):
        _, current, first = self.baseline()
        _, again, second = self.baseline()
        self.assertEqual(self.m.canonical(first), self.m.canonical(second))
        audited = dict(first, audit={"recordedAt": "2026-09-29T00:00:00Z"})
        self.assertEqual(self.m.attestation_digest(audited), self.m.attestation_digest(first),
                         "the wall-clock time is audit metadata and never part of the identity")


class TestConversationIndependence(Scenario):
    """G. The delta packet is made of the repository's state and the committed attestation alone."""

    def test_the_packet_carries_everything_the_review_set_needs(self):
        m = self.m
        engine = Engine()
        state_1 = m.state(engine.snapshot(m))
        failed = attest(state_1, head=HEAD_1, review_type="full", result="FAIL", impact=m.impact(None, state_1),
                        blocking=[{"claim": "entry:c", "summary": "c accepts a negative count"}], module=m)
        engine.files["src/Engine/Rules/CRule.cs"] += b"// refuse a negative count\n"
        state_2 = m.state(engine.snapshot(m))
        result = m.impact(failed, state_2)
        closure = sorted({u[len("file:"):] for claim in result["review"] for u in state_2["claims"][claim]
                          if u.startswith("file:")})
        text = m.render_delta_packet(
            prior=failed, prior_digest=m.attestation_digest(failed), head=HEAD_2, base=BASE, current=state_2,
            impact_record=result,
            entry_packets=[(e, f"entry-{e}.md", "9" * 64) for e in ("c", "d")],
            diff="```diff\n+// refuse a negative count\n```",
            closure_files={p: state_2["units"][f"file:{p}"] for p in closure},
            locators={e: engine.entries[e]["entry"]["locator"] for e in ("c", "d")},
            tests={e: engine.entries[e]["overlay"]["tests"] for e in ("c", "d")})
        for needed in ("c accepts a negative count", "`entry:c`", "`entry:d`", "`invariant:X`", "entry-c.md",
                       "entry-d.md", "+// refuse a negative count", "src/Engine/Rules/CRule.cs",
                       "CRule_holds", "return zero from rule c", "§ c", "Evidence retained", "no implementation "
                       "conversation"):
            self.assertIn(needed, text)
        self.assertNotIn("entry:m`", text.split("## 9.")[0], "a retained claim is not in the review set")
        measured = m.measure(text)
        self.assertGreater(measured["bytes"], 0)


class TestLegacyEvidence(Scenario):
    """H. An engine with no reusable attestation is re-baselined once, and then reuses it."""

    def test_an_older_review_identity_is_never_reused(self):
        _, current, _ = self.baseline()
        identity = {"reviewPacketFormat": 2, "reviewRole": "semantic", "pullRequest": 5,
                    "reviewedCommit": HEAD_1, "baseCommit": BASE}
        result = self.m.impact(identity, current)
        self.assertEqual(result["mode"], "full")
        self.assertEqual([r["code"] for r in result["reasons"]], ["prior-attestation-unusable"])

    def test_an_unscoped_attestation_is_never_reused_and_one_full_review_is_the_baseline(self):
        engine = Engine()
        current = self.m.state(engine.snapshot(self.m))
        unscoped = self.m.build_attestation(
            project={"engine": "Engine"}, reviewed_commit=HEAD_1, base_commit=BASE, review_type="full",
            reviewer={"id": "semantic"}, charter={}, packet={}, maps=[], corpora=[], current={"units": {}, "claims": {}},
            result="PASS", scoped=False)
        self.assertEqual(self.m.validate_attestation(unscoped), [])
        result = self.m.impact(unscoped, current)
        self.assertEqual([r["code"] for r in result["reasons"]], ["legacy-evidence-unscoped"])

        baseline = attest(current, head=HEAD_2, review_type="full", result="PASS", parent=unscoped, impact=result,
                          module=self.m)
        self.assertEqual(self.m.validate_attestation(baseline), [])
        engine.files["src/Engine/Rules/BRule.cs"] += b"// moved\n"
        after = self.m.impact(baseline, self.m.state(engine.snapshot(self.m)))
        self.assertEqual((after["mode"], after["review"]), ("delta", ["entry:b"]))

    def test_no_attestation_at_all_is_a_baseline(self):
        _, current, _ = self.baseline()
        self.assertEqual([r["code"] for r in self.m.impact(None, current)["reasons"]], ["no-prior-attestation"])


def handler(member, body="return Resolution.Allowed;", extra=""):
    """One entry's handler as the generator's convention writes it: a member of the one partial
    class every handler shares, in a file of its own."""
    return (f"namespace Engine;\n\ninternal static partial class Handlers\n{{\n"
            f"    internal static partial Resolution<bool> {member}({member}Request request)\n    {{\n"
            f"        {body}\n    }}\n{extra}}}\n").encode()


class TestTheGeneratorsConventions(Scenario):
    """What a produced engine's code actually looks like: every handler a member of one partial
    class, and one entry reaching another through the generated request types and registry."""

    def engine(self):
        engine = Engine()
        for letter in LETTERS:
            member = letter.upper()
            engine.files.pop(f"src/Engine/Rules/{member}Rule.cs")
            engine.files[f"src/Engine/Handlers/{member}.cs"] = handler(member)
            engine.entries[letter]["overlay"]["implementedIn"] = f"Handlers/{member}.cs"
        engine.invariants[0]["anchors"] = ["src/Engine/Handlers/C.cs"]
        return engine

    def test_one_partial_class_does_not_make_every_handler_depend_on_every_other(self):
        engine = self.engine()
        engine, _, prior = self.baseline(engine)
        engine.files["src/Engine/Handlers/K.cs"] = handler("K", "return Resolution.Refused(\"k\");")
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual((result["mode"], result["review"]), ("delta", ["entry:k"]))

    def test_a_helper_declared_in_another_file_of_the_partial_class_is_a_dependency(self):
        engine = self.engine()
        engine.files["src/Engine/Handlers/Shared.cs"] = (
            b"namespace Engine;\n\ninternal static partial class Handlers\n{\n"
            b"    private static bool Within(int value) => value is >= 0 and <= 400;\n}\n")
        engine.files["src/Engine/Handlers/K.cs"] = handler("K", "return Within(request.Value) ? Resolution.Allowed : "
                                                                "Resolution.Refused(\"k\");")
        engine, _, prior = self.baseline(engine)
        engine.files["src/Engine/Handlers/Shared.cs"] = engine.files["src/Engine/Handlers/Shared.cs"].replace(b"400", b"399")
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual(result["review"], ["entry:k"],
                         "k calls a private member another file of the same partial class declares")

    def test_an_entry_reached_through_its_generated_request_type_is_a_dependency(self):
        engine = self.engine()
        engine.files["src/Engine/Handlers/K.cs"] = handler(
            "K", "return Registry.Resolve(new QRequest(request.Value)).IsAllowed ? Resolution.Allowed : "
                 "Resolution.Refused(\"k\");")
        engine, _, prior = self.baseline(engine)
        engine.files["src/Engine/Handlers/Q.cs"] = handler("Q", "return Resolution.Refused(\"q\");")
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertEqual(result["review"], ["entry:k", "entry:q"],
                         "the map says nothing of it, and k's answer turns on q's handler all the same")

    def test_an_entry_reached_by_its_id_as_a_string_is_a_dependency(self):
        engine = self.engine()
        engine.files["src/Engine/Handlers/K.cs"] = handler(
            "K", "return Registry.Resolve(\"q\", request).IsAllowed ? Resolution.Allowed : Resolution.Refused(\"k\");")
        engine, _, prior = self.baseline(engine)
        engine.files["src/Engine/Handlers/Q.cs"] = handler("Q", "return Resolution.Refused(\"q\");")
        result = self.m.impact(prior, self.m.state(engine.snapshot(self.m)))
        self.assertIn("entry:k", result["review"])

    def test_a_brace_in_a_string_or_a_comment_is_not_structure(self):
        text = ('internal static partial class Handlers\n{\n    // a stray { in a comment\n'
                '    static string Label(int v) => $"{v} }} {{";\n    static int Clamp(int v) { var s = "}"; return v; }\n}\n')
        self.assertEqual(self.m.partial_members(text), ({"Handlers"}, {"Label", "Clamp"}))


class TestTheSelfReview(Scenario):
    """The adversarial pre-review an implementer owes before a semantic packet can be written."""

    def complete(self, digest):
        record = self.m.self_review_skeleton("c", digest)
        for identifier in self.m.SELF_REVIEW_IDS:
            record["classes"][identifier] = {"outcome": "tested", "tests": ["CRule_holds"]}
        record["classes"]["exclusive-or"] = {"outcome": "not-applicable",
                                             "reason": "rule c has no disjunction anywhere in its evidence"}
        return record

    def test_a_complete_current_record_passes(self):
        current = Engine().state(self.m)
        digest = self.m.claim_digest(current, "entry:c")
        self.assertEqual(self.m.self_review_problems(self.complete(digest), "c", digest, {"CRule_holds"}), [])

    def test_a_record_made_before_the_repair_is_stale(self):
        engine = Engine()
        before = self.m.claim_digest(engine.state(self.m), "entry:c")
        engine.files["src/Engine/Rules/CRule.cs"] += b"// repaired\n"
        after = self.m.claim_digest(engine.state(self.m), "entry:c")
        problems = self.m.self_review_problems(self.complete(before), "c", after, {"CRule_holds"})
        self.assertTrue(any("attack it again" in p for p in problems), problems)

    def test_an_unanswered_class_a_missing_test_and_a_placeholder_are_each_refused(self):
        digest = self.m.claim_digest(Engine().state(self.m), "entry:c")
        record = self.complete(digest)
        del record["classes"]["idempotence"]
        record["classes"]["immutability"] = {"outcome": "tested", "tests": ["NoSuchTest"]}
        record["classes"]["sentinel-wraparound"] = {"outcome": "not-applicable", "reason": "n/a"}
        problems = self.m.self_review_problems(record, "c", digest, {"CRule_holds"})
        self.assertEqual(len(problems), 3, problems)

    def test_the_twenty_classes_are_the_ones_the_assignment_names(self):
        self.assertEqual(len(self.m.SELF_REVIEW_IDS), 20)
        self.assertEqual(len(set(self.m.SELF_REVIEW_IDS)), 20)


if __name__ == "__main__":
    unittest.main()
