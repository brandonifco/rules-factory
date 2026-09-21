#!/usr/bin/env python3
"""The workflows ask for the scope they claim to, and the publish gate still double-packs (#347).

A scope is only as good as what asks for it. These read the two workflows the way
check-workflow-pins.py does -- as lines, because the standard library has no YAML parser and
these files write each value on one line -- and hold them to four things:

  * a pull request asks what its own diff owes, and can read the diff to do it;
  * anything that is not a pull request runs the full gate;
  * a schedule exists at all, because the check it is for is the one no diff ever owes;
  * the tagged map is packed twice, in two jobs that share no filesystem, and the digests are
    compared before anything is pushed -- the one thing no scope may narrow.

The last is why this file exists rather than a line in a review checklist. Publishing cannot be
undone, and the comparison that makes it safe was previously held by nothing but its own comment.

Run: python3 -m pytest tools/tests/test_ci_scope.py
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")


def _uncommented(text):
    """The lines of a job body that are not comments.

    A comment explaining that only `publish` holds `id-token: write` must not be what satisfies
    the test that only `publish` holds it.
    """
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def read(name):
    with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as handle:
        return handle.read()


class TestValidateAsksWhatTheDiffOwes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read("validate.yml")

    def test_a_pull_request_asks_for_the_scope_of_its_own_diff(self):
        self.assertIn("--changed --base", self.text)
        self.assertIn("github.event.pull_request.base.sha", self.text)

    def test_anything_that_is_not_a_pull_request_runs_the_full_gate(self):
        # A push to main and the schedule both land in the else branch, which is the script.
        self.assertRegex(self.text, r"else\s*\n\s*\./scripts/validate\.sh")

    def test_the_base_commit_is_in_the_checkout(self):
        # `git diff <base>...HEAD` needs it. Without this the diff is unreadable, which widens
        # to --full -- correct, but silently, and a scope nobody can compute does not exist.
        self.assertIn("fetch-depth: 0", self.text)

    def test_there_is_a_scheduled_run(self):
        # Anchored, so that a key merely ending in "schedule:" does not satisfy this.
        self.assertRegex(self.text, r"(?m)^\s*schedule:\s*$")
        self.assertRegex(self.text, r"(?m)^\s*- cron:\s*'[^']+'\s*$")

    def test_the_scope_is_not_decided_twice(self):
        # The rule that widens for core tooling lives in tools/validate-repo.py, covered by
        # tests. A second copy in YAML is the drift this repository keeps finding in itself.
        for word in ("mapcontract", "mapvalidator", "tools/mapper", "pack-map"):
            with self.subTest(word=word):
                self.assertNotIn(word, self.text)

    def test_the_engine_job_still_runs_unconditionally(self):
        # Scope.engine says whether an engine is owed, and nothing consumes it yet: the engine
        # job is not the critical path, and skipping it would trade a real check for no wall
        # clock. When something does consume it, this test is what has to change first.
        self.assertIn("engine:", self.text)
        self.assertNotIn("needs: scope", self.text)


class TestThePublishGateIsNarrowedInExactlyOnePlace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read("publish-map.yml")
        # The two job bodies, without the file header and without comment lines.
        body = cls.text[cls.text.index("\n  gate:"):]
        gate, _, publish = body.partition("\n  publish:")
        cls.gate, cls.publish = _uncommented(gate), _uncommented(publish)

    def test_the_gate_validates_at_the_release_scope(self):
        self.assertIn("tools/validate-repo.py --release", self.gate)

    def test_the_gate_no_longer_packs_every_map(self):
        self.assertNotIn("./scripts/validate.sh", self.text)

    def test_the_tagged_map_is_packed_in_both_jobs(self):
        self.assertIn("tools/pack-map.py", self.gate)
        self.assertIn("tools/pack-map.py", self.publish)

    def test_the_two_packs_are_compared_before_anything_is_pushed(self):
        # The acceptance condition: a tagged map cannot publish unless its own two
        # independently built packages match.
        self.assertIn('"$actual" != "$EXPECTED"', self.publish)
        self.assertIn("refusing to push bytes the gate did not see", self.publish)
        compare = self.publish.index("$EXPECTED")
        push = self.publish.index("dotnet nuget push")
        self.assertLess(compare, push, "the comparison must come before the push")

    def test_an_absent_digest_is_refused_rather_than_treated_as_a_match(self):
        self.assertIn('-z "$EXPECTED"', self.publish)

    def test_the_jobs_do_not_share_a_checkout(self):
        # Two packs in one job would prove pack-map.py is deterministic and nothing else.
        self.assertEqual(2, self.text.count("uses: actions/checkout@"))

    def test_only_the_publishing_job_can_mint_a_token(self):
        self.assertIn("id-token: write", self.publish)
        self.assertNotIn("id-token: write", self.gate)

    def test_a_refused_pack_cannot_pass_through_tee(self):
        self.assertEqual(2, len(re.findall(r"set -o pipefail", self.text)))


class ThePublishJobsCanReadTheVersionTheyReplace(unittest.TestCase):
    """0062, #378: `pack-map.py` reads the predecessor out of a `map/<name>/vX.Y.Z` tag, and a
    shallow checkout has no tags.

    The tool does not refuse a checkout without them -- packing a map from outside this
    repository is legitimate and says so -- which is exactly why the workflow has to ask. Without
    this, the comparison would silently not happen in the one job that actually publishes, and
    #378 would be closed by relocating its defect rather than by fixing it.

    Read from the uncommented text, like everything else here: the comment beside `fetch-depth`
    explaining why it is there must not be what satisfies the test that it is there.
    """

    def test_every_checkout_that_packs_takes_the_whole_history(self):
        body = _uncommented(read("publish-map.yml"))
        checkouts = body.count("actions/checkout@")
        self.assertGreater(checkouts, 0, "publish-map.yml checks nothing out")
        self.assertEqual(checkouts, body.count("fetch-depth: 0"),
                         f"publish-map.yml has {checkouts} checkout(s) and "
                         f"{body.count('fetch-depth: 0')} asking for the whole history; a shallow "
                         f"one has no map tags, so pack-map.py would compare against nothing (0062)")

    def test_the_validate_workflow_still_takes_it_too(self):
        """The engine job packs a map as part of producing an engine rather than to publish one,
        and says on every run which version it compared against or that it compared none. What
        must not regress is `validate`, whose scope is read from a diff against a base commit."""
        self.assertIn("fetch-depth: 0", _uncommented(read("validate.yml")))


if __name__ == "__main__":
    unittest.main()
