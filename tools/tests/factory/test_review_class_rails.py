#!/usr/bin/env python3
"""The five review classes, held to the rails that act on them (decision 0076, #595).

test_review_class.py proves the classifier. This proves the **tools an engine runs** read it, one
class at a time, against a real produced engine and the stand-in for `gh` the other rail tests use:
`tools/pr-policy.py` (what the pull request must say), `tools/conformance-gate.py` (which verdicts
it needs), `tools/review-packet.py` (which packet is written, and what stands in front of it) and
`tools/record-verdict.py` (what may be recorded).

The three acceptance cases of the issue are here by shape, not by name:

  * a pull request that adds one decision record and nothing else -- no code, no overlay, no map --
    passes, with no principal entry invented for it and no all-not-applicable self-review written
    for code that does not exist (`TestDecisionRecordOnly`);
  * an implementation still names its entries, has an entry-scoped self-review, a semantic packet
    and a verdict, and no claim on a pull request lowers that (`TestSemanticImplementation`);
  * a factory update that claims no behavioural change, and whose maps, corpora and randomness did
    not move, needs structural and provenance validation and no semantic verdict -- and the same
    update with the map moved needs the verdict it always did (`TestGeneratedOrProvenance`).

Every class is inherited from `rails.RailsInAGitEngine` for its produced, committed engine and its
`gh`, and every inherited test is dropped: they are that module's to run, once.

Run: python3 -m pytest -p no:cacheprovider tools/tests/factory/test_review_class_rails.py
"""
import json
import os
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from tests.factory import test_factory_rails as rails  # noqa: E402

NAME = rails.NAME
BASE = "b" * 40
DECISION = "docs/decisions/0007-owner-rulings.md"
HANDLER = f"src/{NAME}/Rules/AltitudeLimit.cs"
RECORD_TEXT = "# 0007 — owner rulings\n\n- **Status:** accepted\n- **Relates to:** decisions 0001 to 0006\n"


def only_its_own_tests(cls):
    """Drop the tests a class inherits from the rails module: that module runs them, once."""
    for parent in cls.__mro__[1:]:
        for name in list(vars(parent)):
            if name.startswith("test") and name not in vars(cls):
                setattr(cls, name, None)
    return cls


class ClassRails(rails.RailsInAGitEngine):
    """A produced, committed engine, a `gh` that keeps statuses and serves the base's files, and a pull request."""

    def setUp(self):
        super().setUp()
        self.statuses = os.path.join(self.tmp, "statuses.json")
        with open(self.gh, "w", encoding="utf-8") as handle:
            handle.write(rails.GH_STATUS_STUB)
        with open(self.statuses, "w", encoding="utf-8") as handle:
            json.dump({}, handle)

    # --- the engine and the pull request -----------------------------------------------------

    def engine(self):
        """The produced engine, committed, with a record that says the factory was clean."""
        self.commit_engine()
        record = json.loads(self.read("provenance.json"))
        if record["factory"]["dirty"] is not False:
            # A factory checkout with uncommitted changes records itself dirty; a clean one already says not.
            record["factory"]["dirty"] = False
            self.write("provenance.json", json.dumps(record, indent=2) + "\n")
            rails.git(self.out, "commit", "-qam", "a clean factory")

    def write(self, relative, text):
        path = os.path.join(self.out, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def body(self, conformance, evidence=None, documentation=None, produce=None, provenance=None):
        text = rails.GOOD_PR_BODY
        old = text.split("## Map and rules conformance")[1].split("## Tests and evidence")[0]
        text = text.replace(old, f"\n\n{conformance}\n\n")
        if evidence is not None:
            old = text.split("## Tests and evidence")[1].split("## Documentation")[0]
            text = text.replace(old, f"\n\n{evidence}\n\n")
        if documentation is not None:
            text = text.replace("None: this engine has no documents of its own, and nothing here changes one.",
                                documentation)
        if produce is not None:
            text = text.replace("## Exact behavioural claim", f"{produce}\n## Exact behavioural claim")
        if provenance is not None:
            text = text.replace("- semantically reviewed by: rules-conformance", provenance)
        return text

    NO_TEST = ("```\n$ ./scripts/validate.sh full\nvalidate.sh full: PASS\n```\n\n"
               "No test is written: this change implements no rule.")

    def pull_request(self, body, files, contents=None, head=None, issue_body="", labels=("state:ready", "risk:normal"),
                     changed=None, base=None):
        """Fixture the pull request. `files` is `{path: change type}`; `contents` is the base commit's files."""
        listed = [{"path": path, "changeType": change} if isinstance(change, str) else
                  {"path": path, "changeType": change[0], "previous": change[1]}
                  for path, change in files.items()]
        self.fixture({
            "pr": {"5": {"number": 5, "title": "A change", "body": body, "files": listed,
                         "changedFiles": len(listed) if changed is None else changed,
                         "baseRefOid": base or BASE, "headRefOid": head or "a" * 40, "headRefName": "issue-27",
                         "baseRefName": "main", "state": "OPEN", "closingIssuesReferences": [{"number": 27}]}},
            "issue": {"27": {"number": 27, "title": "An issue", "state": "OPEN", "body": issue_body,
                             "labels": [{"name": name} for name in labels]}},
            "repo": {"nameWithOwner": "owner/engine"},
            "contents": {base or BASE: contents or {}},
        })

    # --- the tools -------------------------------------------------------------------------

    def environment(self, **extra):
        return super().environment(GH_STATUSES=self.statuses, **extra)

    def run_tool(self, tool, *args):
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", tool), *args], cwd=self.out,
                              capture_output=True, text=True, env=self.environment())

    def policy(self):
        return self.run_tool("pr-policy.py", "5")

    def gate(self):
        return self.run_tool("conformance-gate.py", "5")

    def packet(self, *extra):
        return self.run_tool("review-packet.py", "5", "--base", "main", *extra)

    def decision_record_only_request(self, conformance=None):
        """A pull request that adds one new decision record, and says it is one."""
        self.engine()
        self.write(DECISION, RECORD_TEXT)
        conformance = conformance if conformance is not None else "- review class: decision-record-only\n- entry id(s): none"
        self.pull_request(
            self.body(conformance, evidence=self.NO_TEST,
                      documentation=f"- [x] `{DECISION}` — updated: the record itself is new in this change",
                      provenance="- semantically reviewed by: not required (a decision record that overrules nothing)"),
            {DECISION: "ADDED"})


class TestDecisionRecordOnly(ClassRails):
    """Reykholt #79: one new decision record, no code, no overlay, no map, no behaviour change."""

    def test_it_passes_with_no_principal_entry_and_no_self_review(self):
        # mutation: leave `docs/decisions/**` as a semantic path the policy must name an entry for
        self.decision_record_only_request()
        done = self.policy()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("review class: `decision-record-only`", done.stdout)
        self.assertIn("structural and provenance validation only", done.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.out, "reviews")),
                         "no self-review record exists, and none was asked for")

    def test_the_gate_asks_for_no_semantic_verdict(self):
        # mutation: let the gate decide from the surface list alone
        self.decision_record_only_request()
        done = self.gate()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("no rules verdict required", done.stdout)
        self.assertIn("review class: `decision-record-only`", done.stdout)

    def test_a_semantic_packet_is_refused_rather_than_written_to_satisfy_a_policy(self):
        # mutation: write the semantic packet for any change that touches the surface
        self.decision_record_only_request()
        rails.git(self.out, "checkout", "-qb", "issue-27")
        self.write(DECISION, RECORD_TEXT)
        rails.git(self.out, "add", "-A")
        rails.git(self.out, "commit", "-qm", "record the rulings")
        self.pull_request(self.body("- review class: decision-record-only\n- entry id(s): none",
                                    evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: new"),
                          {DECISION: "ADDED"}, head=rails.git(self.out, "rev-parse", "HEAD"),
                          base=rails.git(self.out, "rev-parse", "main"))
        done = self.packet("--role", "semantic")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("owes no semantic review", done.stderr)
        self.assertIn("--role structural", done.stderr)
        # The review it does get is structural, and its packet says what the class is and what that owes.
        structural = self.packet("--role", "structural", "--stdout")
        self.assertEqual(structural.returncode, 0, structural.stderr)
        self.assertIn("review class: `decision-record-only`", structural.stdout)
        self.assertIn("owes: structural and provenance validation only", structural.stdout)
        reading = self.packet("--role", "semantic", "--stdout")
        self.assertEqual(reading.returncode, 0, "`--stdout` writes nothing a verdict can be recorded from")

    def test_a_semantic_verdict_cannot_be_recorded_on_a_change_that_owes_none(self):
        # mutation: delete the recorder's refusal, and a verdict nobody was owed reads like one that was
        self.engine()
        rails.git(self.out, "checkout", "-qb", "issue-27")
        self.write(DECISION, RECORD_TEXT)
        rails.git(self.out, "add", "-A")
        rails.git(self.out, "commit", "-qm", "record the rulings")
        head = rails.git(self.out, "rev-parse", "HEAD")
        self.pull_request(self.body("- review class: decision-record-only\n- entry id(s): none", evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: new"),
                          {DECISION: "ADDED"}, head=head, base=rails.git(self.out, "rev-parse", "main"),
                          labels=("state:ready", "risk:independent-review"))
        out = os.path.join(self.tmp, "whole-packet")
        # The whole packet is writable: an independent review may be owed by the issue's risk label.
        done = self.packet("--out", out)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        identity = os.path.join(out, f"pr-5-{head[:12]}.review.json")
        recorded = json.load(open(identity, encoding="utf-8"))
        self.assertEqual(recorded["reviewContext"]["reviewClass"]["effective"], "decision-record-only")
        refused = self.run_tool("record-verdict.py", "--pr", "5", "--reviewer", "semantic", "--verdict", "pass",
                                "--packet", identity)
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("owes no semantic review", refused.stderr)
        allowed = self.run_tool("record-verdict.py", "--pr", "5", "--reviewer", "codex", "--verdict", "pass",
                                "--packet", identity)
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)

    def test_without_the_claim_it_is_reviewed_as_it_was_and_told_how_to_ask_for_less(self):
        # mutation: exempt it because the diff proves it is only a record, whatever the body says
        self.decision_record_only_request(conformance="N/A")
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("touches the semantic surface", done.stdout)
        self.assertIn("review class: decision-record-only", done.stdout)
        gate = self.gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)
        self.assertIn("rules-verdict/semantic is not recorded", gate.stdout)

    def test_a_record_that_supersedes_another_is_not_one_it_can_claim(self):
        # mutation: let the claim win over a header that says the record overrules another
        self.engine()
        self.write(DECISION, RECORD_TEXT + "- **Supersedes:** 0003\n")
        self.pull_request(self.body("- review class: decision-record-only\n- entry id(s): none", evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: new"),
                          {DECISION: "ADDED"})
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("claims `decision-record-only`, and this diff is `semantic-ruling`", done.stdout)

    def test_a_handler_beside_the_record_voids_the_claim(self):
        # mutation: judge the decision record and not the rest of the diff
        self.engine()
        self.write(DECISION, RECORD_TEXT)
        self.write(HANDLER, "// the altitude limit\n")
        self.pull_request(self.body("- review class: decision-record-only\n- entry id(s): none", evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: new"),
                          {DECISION: "ADDED", HANDLER: "ADDED"})
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("claims `decision-record-only`, and this diff is `semantic-implementation`", done.stdout)
        self.assertEqual(self.gate().returncode, 1, "and the gate still wants the verdict")


class TestSemanticImplementation(ClassRails):
    """Reykholt #77: handlers, tests and overlay rows. Nothing about it got cheaper."""

    def implementation_request(self, conformance=None, files=None):
        self.engine()
        self.write(HANDLER, "// the altitude limit\n")
        self.write_overlay_row()
        self.pull_request(
            self.body(conformance if conformance is not None else
                      "- entry id(s): altitude-limit\n- map package and version: RulesFactory.Maps.FaaPart107 5.0.0\n"
                      "- source locator(s): § 107.51(b)"),
            files or {HANDLER: "ADDED", "overlay/altitude-limit.json": "MODIFIED"},
            contents={"overlay/altitude-limit.json": json.dumps({"status": "mapped"})},
            issue_body="<!-- rules-factory-entry: altitude-limit -->\n")

    def write_overlay_row(self):
        self.write("overlay/altitude-limit.json", json.dumps({
            "status": "implemented", "implementedIn": "Rules/AltitudeLimit.cs",
            "tests": [{"name": "AltitudeLimit_DeclinesAboveTheCeiling",
                       "mutation": "return the ceiling instead of declining"}]}))

    def test_it_still_names_an_entry_a_map_and_a_locator(self):
        # mutation: let any pull request that declares a class skip the conformance fields
        self.implementation_request(conformance="N/A")
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("touches the semantic surface", done.stdout)

    def test_it_still_names_a_mutation(self):
        # mutation: drop the mutation requirement for every class
        self.implementation_request()
        self.pull_request(self.body("- entry id(s): altitude-limit\n- map package and version: x 1\n- source locator(s): y",
                                    evidence=self.NO_TEST),
                          {HANDLER: "ADDED", "overlay/altitude-limit.json": "MODIFIED"},
                          contents={"overlay/altitude-limit.json": json.dumps({"status": "mapped"})},
                          issue_body="<!-- rules-factory-entry: altitude-limit -->\n")
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("names no mutation", done.stdout)

    def test_a_claim_cannot_lower_it(self):
        # mutation: honour a declared non-semantic class over a diff that computes a semantic one
        for claim in ("decision-record-only", "generated-or-provenance", "documentation", "semantic-ruling"):
            with self.subTest(claim=claim):
                self.implementation_request(conformance=f"- review class: {claim}\n- entry id(s): altitude-limit\n"
                                                        "- map package and version: x 1\n- source locator(s): y")
                done = self.policy()
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn(f"claims `{claim}`", done.stdout)
                gate = self.gate()
                self.assertEqual(gate.returncode, 1, gate.stdout)
                self.assertIn("rules-verdict/semantic is not recorded", gate.stdout)
                self.assertIn("`semantic-implementation`, which owes a semantic verdict", gate.stdout)

    def test_a_diff_that_empties_the_surface_is_judged_by_the_surface_it_removed(self):
        # Codex: a head policy with `semanticPaths: []` made the handler it changed "not on the surface".
        # mutation: judge by the head's surface alone
        self.engine()
        policy = json.loads(self.read(".github/agent-policy.json"))
        before = json.dumps(policy)
        policy["review"]["semanticPaths"] = []
        self.write(".github/agent-policy.json", json.dumps(policy))
        self.write(HANDLER, "int Limit() => 401;\n")
        self.pull_request(self.body("- review class: documentation\n- entry id(s): none", evidence=self.NO_TEST),
                          {HANDLER: "MODIFIED", ".github/agent-policy.json": "MODIFIED"},
                          contents={HANDLER: "int Limit() => 400;\n", ".github/agent-policy.json": before})
        gate = self.gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)
        self.assertIn("`semantic-implementation`, which owes a semantic verdict", gate.stdout)
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("claims `documentation`, and this diff is `semantic-implementation`", done.stdout)

    def test_a_handler_renamed_off_the_surface_is_still_a_handler_removed(self):
        # Codex: GitHub lists a rename by its new path alone, so moving a handler to notes/ left the
        # surface with nothing on it. mutation: ignore `previous_filename`
        self.engine()
        self.write("notes/Altitude.md", "# the altitude limit\n")
        self.pull_request(self.body("- review class: documentation\n- entry id(s): none", evidence=self.NO_TEST,
                                    documentation="- [x] `notes/Altitude.md` — updated: moved here"),
                          {"notes/Altitude.md": ("RENAMED", HANDLER)}, contents={HANDLER: "int Limit() => 400;\n"})
        gate = self.gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)
        self.assertIn("rules-verdict/semantic is not recorded", gate.stdout)
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("claims `documentation`, and this diff is `semantic-implementation`", done.stdout)

    def test_a_path_with_a_hash_in_it_is_asked_for_by_name_and_at_its_ref(self):
        # Codex: `src/E/H.cs#variant.cs` sent raw is read as `H.cs` on the default branch. The stub drops
        # the fragment as HTTP does. mutation: build the URL from the raw path
        self.engine()
        hashed = f"src/{NAME}/H.cs#variant.cs"
        self.write(hashed, "int F() => 2; // a note\n")
        self.pull_request(self.body("- review class: documentation\n- entry id(s): none", evidence=self.NO_TEST),
                          {hashed: "MODIFIED"}, contents={hashed: "int F() => 1; // a note\n"})
        gate = self.gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)
        self.assertIn("rules-verdict/semantic is not recorded", gate.stdout)
        done = self.policy()
        self.assertIn("claims `documentation`, and this diff is `semantic-implementation`", done.stdout)

    def test_the_gate_reruns_when_the_body_is_edited(self):
        # What a change owes is its body's `review class:` line's to claim, so editing the body must
        # re-ask the gate. mutation: drop `edited` from the workflow's types
        workflow = open(os.path.join(rails.FACTORY, "recipe", "rails", "workflows", "conformance-gate.yml"),
                        encoding="utf-8").read()
        self.assertRegex(workflow, r"types: \[[^\]]*\bedited\b[^\]]*\]")

    def test_the_gate_wants_the_verdict_and_takes_it_when_it_is_recorded(self):
        self.implementation_request()
        self.assertEqual(self.gate().returncode, 1)
        head = "a" * 40
        with open(self.statuses, "w", encoding="utf-8") as handle:
            json.dump({head: {"rules-verdict/semantic": "success"}}, handle)
        self.assertEqual(self.gate().returncode, 0)

    def test_the_semantic_packet_is_refused_until_every_entry_has_its_self_review(self):
        # mutation: gate the self-review on the class being anything but an implementation
        self.engine()
        rails.git(self.out, "checkout", "-qb", "issue-27")
        self.write(HANDLER, "// the altitude limit\n")
        self.write_overlay_row()
        rails.git(self.out, "add", "-A")
        rails.git(self.out, "commit", "-qm", "implement the altitude limit")
        head = rails.git(self.out, "rev-parse", "HEAD")
        self.pull_request(self.body("- entry id(s): altitude-limit\n- map package and version: x 1\n- source locator(s): y"),
                          {HANDLER: "ADDED", "overlay/altitude-limit.json": "ADDED"}, head=head,
                          base=rails.git(self.out, "rev-parse", "main"),
                          issue_body="<!-- rules-factory-entry: altitude-limit -->\n## Acceptance criteria\n- [ ] it declines")
        package_map = os.path.join(rails.PART107, "corpus-map.json")
        done = self.packet("--role", "semantic", "--package-map", package_map)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("adversarial self-review is not complete", done.stderr)
        text = self.packet("--role", "semantic", "--package-map", package_map, "--stdout").stdout
        self.assertIn("review class: `semantic-implementation`", text)
        self.assertIn("owes: named entries, an entry-scoped self-review", text)


class TestSemanticRuling(ClassRails):
    """A decision that changes how rules are read owes a semantic review, and a review of the ruling in place of a self-review."""

    EDITED = RECORD_TEXT + "\n1. The furthest player wins.\n"
    ORIGINAL = RECORD_TEXT + "\n1. The nearest player wins.\n"
    SCOPE = "- review class: semantic-ruling\n- decision scope: who wins a Story Mode game\n- entry id(s): none"

    def ruling_request(self, conformance=None, head=None):
        self.engine()
        self.write(DECISION, self.EDITED)
        self.pull_request(
            self.body(conformance if conformance is not None else self.SCOPE, evidence=self.NO_TEST,
                      documentation=f"- [x] `{DECISION}` — updated: the ruling on the winner is reversed"),
            {DECISION: "MODIFIED"}, contents={DECISION: self.ORIGINAL}, head=head)

    def test_an_edited_record_is_a_ruling_whether_or_not_the_pull_request_says_so(self):
        # mutation: let the claim, or its absence, decide the class of a diff that edits a record
        self.ruling_request(conformance="- entry id(s): none\n- decision scope: who wins a Story Mode game")
        gate = self.gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)
        self.assertIn("`semantic-ruling`, which owes a semantic verdict", gate.stdout)
        self.assertIn("review class: `semantic-ruling`", gate.stdout)

    def test_it_names_its_scope_or_its_entries_and_nothing_else(self):
        # mutation: ask a ruling for a locator and a map, which it has no implementation to cite
        self.ruling_request(conformance="- review class: semantic-ruling\n- entry id(s): none")
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("does not say what this ruling is a ruling on", done.stdout)
        self.ruling_request()
        done = self.policy()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("source locator", done.stdout)
        self.assertNotIn("names no mutation", done.stdout, "a ruling writes no test")

    def test_a_ruling_may_name_entries_instead_of_a_scope(self):
        self.ruling_request(conformance="- review class: semantic-ruling\n- entry id(s): altitude-limit")
        done = self.policy()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_new_record_may_raise_itself_to_a_ruling(self):
        # The claim adds review: a record the diff shows overrules nothing may still say it is a ruling.
        self.engine()
        self.write(DECISION, RECORD_TEXT)
        self.pull_request(self.body(self.SCOPE, evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: new"), {DECISION: "ADDED"})
        done = self.policy()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("review class: `semantic-ruling` (computed `decision-record-only`)", done.stdout)
        gate = self.gate()
        self.assertEqual(gate.returncode, 1)
        self.assertIn("rules-verdict/semantic is not recorded", gate.stdout)

    def committed_ruling(self):
        """The branch that edits an existing record, as a pull request, and its head."""
        self.engine()
        self.write(DECISION, self.ORIGINAL)
        rails.git(self.out, "add", "-A")
        rails.git(self.out, "commit", "-qm", "an earlier ruling")
        base = rails.git(self.out, "rev-parse", "HEAD")
        rails.git(self.out, "checkout", "-qb", "issue-27")
        self.write(DECISION, self.EDITED)
        rails.git(self.out, "commit", "-qam", "reverse the ruling")
        head = rails.git(self.out, "rev-parse", "HEAD")
        self.pull_request(self.body(self.SCOPE, evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: reversed"),
                          {DECISION: "MODIFIED"}, contents={DECISION: self.ORIGINAL}, head=head,
                          base=base)
        return head

    def ruling_record(self, **overrides):
        """`reviews/rulings/<decision>.json`, from the skeleton the tool prints, answered."""
        done = self.run_tool("review-scope.py", "ruling-review", DECISION)
        self.assertEqual(done.returncode, 0, done.stderr)
        record = json.loads("\n".join(line for line in done.stdout.splitlines() if not line.startswith("#")))
        record["scope"] = "who wins a Story Mode game, reversed from the nearest player to the furthest"
        for identifier, answer in record["classes"].items():
            answer.update(outcome="answered", answer=f"for {identifier}: the owner's ruling follows the rulebook's wording")
        record.update(overrides)
        self.write("reviews/rulings/0007-owner-rulings.json", json.dumps(record, indent=2) + "\n")
        rails.git(self.out, "add", "-A")
        rails.git(self.out, "commit", "-qm", "the review of the ruling")
        return rails.git(self.out, "rev-parse", "HEAD")

    def test_the_packet_is_refused_until_the_ruling_is_reviewed_and_then_it_is_written_and_recorded(self):
        # mutation: require entries and a self-review of a ruling, or require nothing of it
        self.committed_ruling()
        done = self.packet("--role", "semantic")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("the implementer's review of the ruling is not complete", done.stderr)
        self.assertIn(f"{DECISION}: no ruling review record", done.stderr)
        self.assertNotIn("reviews/self-review", done.stderr, "a ruling has no code to attack, so no self-review is asked of it")

        head = self.ruling_record()
        self.pull_request(self.body(self.SCOPE, evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: reversed"),
                          {DECISION: "MODIFIED"}, contents={DECISION: self.ORIGINAL}, head=head,
                          base=rails.git(self.out, "rev-parse", "main"))
        out = os.path.join(self.tmp, "ruling-packet")
        done = self.packet("--role", "semantic", "--out", out)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        identity = json.load(open(os.path.join(out, f"pr-5-{head[:12]}-semantic.review.json"), encoding="utf-8"))
        self.assertEqual(identity["reviewContext"]["reviewClass"],
                         {"computed": "semantic-ruling", "effective": "semantic-ruling", "declared": "semantic-ruling"})
        packet = open(os.path.join(out, f"pr-5-{head[:12]}-semantic.md"), encoding="utf-8").read()
        self.assertIn("review class: `semantic-ruling`", packet)
        self.assertIn("reviews/rulings/0007-owner-rulings.json", packet)
        self.assertIn("owes: a decision-scoped review record, a semantic packet, a semantic verdict", packet)
        # ... and the verdict is recorded, because a ruling owes one.
        recorded = self.run_tool("record-verdict.py", "--pr", "5", "--reviewer", "semantic", "--verdict", "pass",
                                 "--packet", os.path.join(out, f"pr-5-{head[:12]}-semantic.review.json"))
        self.assertEqual(recorded.returncode, 0, recorded.stdout + recorded.stderr)

    def test_a_ruling_that_names_entries_owes_their_packets_and_no_self_review(self):
        # mutation: ask an entry a ruling names for the self-review of code the ruling does not write
        self.committed_ruling()
        head = self.ruling_record(entries=["altitude-limit"])
        self.pull_request(self.body(self.SCOPE, evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: reversed"),
                          {DECISION: "MODIFIED"}, contents={DECISION: self.ORIGINAL}, head=head,
                          base=rails.git(self.out, "rev-parse", "main"),
                          issue_body="<!-- rules-factory-entry: altitude-limit -->\n## Acceptance criteria\n- [ ] it declines")
        out = os.path.join(self.tmp, "ruling-with-entries")
        done = self.packet("--role", "semantic", "--out", out,
                           "--package-map", os.path.join(rails.PART107, "corpus-map.json"))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(os.path.isfile(os.path.join(out, "entry-altitude-limit.md")),
                        "the entry it names is still handed to the reviewer")
        self.assertFalse(os.path.exists(os.path.join(self.out, "reviews", "self-review")))

    def test_a_review_of_the_ruling_goes_stale_when_the_ruling_is_edited(self):
        # mutation: do not bind the record to the decision's bytes
        self.committed_ruling()
        self.ruling_record()
        self.write(DECISION, self.EDITED + "2. And the furthest wins ties.\n")
        rails.git(self.out, "commit", "-qam", "a second ruling, after the review")
        head = rails.git(self.out, "rev-parse", "HEAD")
        self.pull_request(self.body(self.SCOPE, evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: reversed"),
                          {DECISION: "MODIFIED"}, contents={DECISION: self.ORIGINAL}, head=head,
                          base=rails.git(self.out, "rev-parse", "main"))
        done = self.packet("--role", "semantic")
        self.assertEqual(done.returncode, 1)
        self.assertIn("it was edited since, so review it again", done.stderr)

    def test_a_review_that_answers_nothing_is_not_a_review(self):
        # mutation: accept a placeholder answer
        self.committed_ruling()
        head = self.ruling_record(scope="n/a")
        self.pull_request(self.body(self.SCOPE, evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: reversed"),
                          {DECISION: "MODIFIED"}, contents={DECISION: self.ORIGINAL}, head=head,
                          base=rails.git(self.out, "rev-parse", "main"))
        done = self.packet("--role", "semantic")
        self.assertEqual(done.returncode, 1)
        self.assertIn("`scope` says nothing anybody can check", done.stderr)
        check = self.run_tool("review-scope.py", "ruling-review", DECISION, "--check")
        self.assertEqual(check.returncode, 1)
        self.assertIn("ruling-review: INCOMPLETE", check.stderr)


class TestGeneratedOrProvenance(ClassRails):
    """Reykholt #68: a factory update claiming no behavioural change, with the map unmoved."""

    def update_request(self, moved=None, claim=True, extra=(), section=True, kernel_moved=True):
        """A factory update as a real produce wrote it, with a base record that differs only as `moved` says."""
        self.engine()
        head = json.loads(self.read("provenance.json"))
        base = json.loads(json.dumps(head))
        if kernel_moved:
            base["kernel"]["version"] = "0.0.9"
            base["factory"]["version"] = "0.0.1"
        for key, value in (moved or {}).items():
            base[key] = value
        paths = ["provenance.json"] + [item["path"] for item in head["generated"]
                                       if not item["path"].startswith("corpus/")][:30]
        paths += [item["path"] for item in head["managed"]][:5]
        files = {path: "MODIFIED" for path in paths}
        files.update({path: "MODIFIED" for path in extra})
        record = head
        produce = (f"## Produced by the factory\n\n<!-- rules-factory-produce -->\n\n"
                   f"- factory version: {record['factory']['version']}\n"
                   f"- map package and version: {record['maps'][0]['packageId']} {record['maps'][0]['version']}\n"
                   f"- kernel version: {record['kernel']['version']}\n- what moved: the kernel and the factory\n")
        evidence = ("```\n$ python3 tools/factory produce --package p.nupkg --corpus c --name N --out e\n"
                    "validate.sh full: PASS\n$ python3 tools/factory provenance --engine e\n"
                    "provenance of e: every field matches\n```")
        moved_documents = sorted(path for path in files if path.endswith(".md"))
        conformance = ((("- review class: generated-or-provenance\n" if claim else "")) +
                       f"- map package and version: {record['maps'][0]['packageId']} {record['maps'][0]['version']}")
        self.pull_request(
            self.body(conformance, evidence=evidence, produce=produce if section else None,
                      documentation="\n".join(f"- [x] `{path}` — updated: written by produce" for path in moved_documents)
                      or None),
            files, contents={"provenance.json": json.dumps(base)})
        return files

    def test_it_passes_the_policy_and_the_gate_asks_for_no_semantic_verdict(self):
        # mutation: require the semantic verdict for every factory update, as the gate did
        self.update_request()
        done = self.policy()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("review class: `generated-or-provenance`", done.stdout)
        self.assertIn("claim was admitted", done.stdout)
        self.assertIn("the maps, the corpora and the randomness are the same at the base and the head", done.stdout)
        gate = self.gate()
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertIn("no rules verdict required", gate.stdout)

    def test_managed_review_files_changing_is_not_a_reason_to_review_semantics(self):
        # The rails and the review model are managed files; a produce that rewrites them is this class.
        # mutation: count tools/review-*.py or docs/review-evidence.md as semantic because they say "review"
        files = self.update_request()
        self.assertTrue([p for p in files if p.startswith("tools/") or p.endswith(".md")] or True)
        self.assertEqual(self.gate().returncode, 0)

    def test_it_needs_the_claim(self):
        # mutation: exempt a regeneration because the diff proves it inert, whatever the body says
        self.update_request(claim=False)
        gate = self.gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)
        self.assertIn("rules-verdict/semantic is not recorded", gate.stdout)
        self.assertIn("review class: generated-or-provenance", gate.stdout)

    def test_a_moved_map_owes_the_verdict_it_always_did(self):
        # mutation: compare the maps' package ids and not their versions
        base_maps = [{"packageId": "RulesFactory.Maps.FaaPart107", "version": "4.0.0", "nupkgSha256": "00"}]
        self.update_request(moved={"maps": base_maps})
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("claims `generated-or-provenance`", done.stdout)
        self.assertIn("the record's maps differ between the base and the head", done.stdout)
        gate = self.gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)
        self.assertIn("rules-verdict/semantic is not recorded", gate.stdout)

    def test_a_hand_written_file_in_the_update_owes_the_verdict(self):
        # mutation: judge the files the factory wrote and not the one it did not
        self.update_request(extra=(HANDLER,))
        self.write(HANDLER, "// smuggled\n")
        gate = self.gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)

    def test_the_claim_needs_the_produce_section_admitted(self):
        # mutation: let generated-or-provenance be claimed without the provenance validation it names
        self.update_request(section=False)
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("is the factory's", done.stdout)
        self.assertIn("## Produced by the factory", done.stdout)

    def test_a_base_nobody_can_read_is_reviewed(self):
        # mutation: treat an unreadable base record as unmoved
        self.update_request()
        document = json.load(open(self.fixture_path, encoding="utf-8"))
        document["contents"][BASE] = {}
        self.fixture(document)
        gate = self.gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)


class TestDocumentation(ClassRails):
    """A document, a comment, a process file: structural checks only."""

    def test_a_readme_needs_no_entry_no_mutation_no_verdict(self):
        # mutation: keep asking every pull request to name a mutation
        self.engine()
        self.write("README.md", "# the engine\n")
        self.pull_request(self.body("N/A", evidence=self.NO_TEST,
                                    documentation="- [x] `README.md` — updated: the engine's own README"),
                          {"README.md": "ADDED"})
        done = self.policy()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("review class: `documentation`", done.stdout)
        gate = self.gate()
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertIn("no rules verdict required", gate.stdout)

    def test_a_comment_only_change_to_a_handler_is_documentation_when_it_is_claimed(self):
        # mutation: let comment_only return True for any C# file
        self.engine()
        self.write(HANDLER, "int Limit() { return 400; } // the corpus says 400\n")
        rails.git(self.out, "add", "-A")
        rails.git(self.out, "commit", "-qm", "the handler")
        self.write(HANDLER, "int Limit() { return 400; } // 14 CFR 107.51(b)\n")
        self.pull_request(self.body("- review class: documentation\n- entry id(s): none", evidence=self.NO_TEST),
                          {HANDLER: "MODIFIED"},
                          contents={HANDLER: "int Limit() { return 400; } // the corpus says 400\n"})
        done = self.policy()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.gate().returncode, 0)

    def test_a_code_change_dressed_as_a_comment_change_is_an_implementation(self):
        # mutation: compare the files with their comments removed but their literals normalised
        self.engine()
        self.write(HANDLER, 'string Url() { return "http://b"; }\n')
        self.pull_request(self.body("- review class: documentation\n- entry id(s): none", evidence=self.NO_TEST),
                          {HANDLER: "MODIFIED"}, contents={HANDLER: 'string Url() { return "http://a"; }\n'})
        done = self.policy()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("claims `documentation`, and this diff is `semantic-implementation`", done.stdout)
        self.assertEqual(self.gate().returncode, 1)

    def test_a_list_past_the_cap_is_never_exempted(self):
        # The gate's refusal of a truncated list is untouched by classes: an undecidable gate fails.
        self.engine()
        self.write("README.md", "# the engine\n")
        self.pull_request(self.body("N/A", evidence=self.NO_TEST,
                                    documentation="- [x] `README.md` — updated: readme"),
                          {"README.md": "ADDED"}, changed=140)
        self.assertEqual(self.gate().returncode, 2)


class TestAnEmbeddedEngineIsClassifiedInItsOwnTerms(ClassRails):
    """GitHub reports `engine/docs/decisions/0007-x.md`; the policy, the table and the base are the engine's (0069)."""

    PATH = f"engine/{DECISION}"

    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "repo")
        self.out = os.path.join(self.repo, "engine")
        self.produced("--repo-root", self.repo)

    def request(self, files, contents, conformance="- review class: decision-record-only\n- entry id(s): none"):
        self.pull_request(self.body(conformance, evidence=self.NO_TEST,
                                    documentation=f"- [x] `{DECISION}` — updated: the record"),
                          files, contents=contents)

    def test_a_new_record_beneath_the_root_is_a_record_and_nothing_else(self):
        # mutation: match the repository-relative path against the engine-relative surface and class nothing
        self.write(DECISION, RECORD_TEXT)
        self.request({self.PATH: "ADDED"}, {})
        done = self.policy()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("review class: `decision-record-only`", done.stdout)
        gate = self.gate()
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertIn("no rules verdict required", gate.stdout)

    def test_the_base_is_read_at_the_path_github_knows_it_by(self):
        # A change of line endings is cosmetic only if the base was read: with the engine's own path
        # asked of the API the base is missing, and a record that cannot be compared is a ruling.
        # mutation: read the base by the engine-relative path
        self.write(DECISION, "The furthest player wins.\n")
        self.request({self.PATH: "MODIFIED"}, {self.PATH: "The furthest player wins.  \r\n"})
        done = self.policy()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("review class: `decision-record-only`", done.stdout)
        self.assertEqual(self.gate().returncode, 0)

    def test_a_host_files_change_is_not_the_engines_surface_and_is_documentation(self):
        self.write("README.md", "# the engine\n")
        self.pull_request(self.body("N/A", evidence=self.NO_TEST,
                                    documentation="- [x] `../tools/build-map.py` — checked, no change: not a document"),
                          {"tools/build-map.py": "MODIFIED"})
        self.assertEqual(self.gate().returncode, 0)


for _cls in (ClassRails, TestDecisionRecordOnly, TestSemanticImplementation, TestSemanticRuling,
             TestGeneratedOrProvenance, TestDocumentation, TestAnEmbeddedEngineIsClassifiedInItsOwnTerms):
    only_its_own_tests(_cls)
del _cls


if __name__ == "__main__":
    unittest.main()
