#!/usr/bin/env python3
"""The evidence lock, proved unable to pass while the tree disagrees with it (#349).

The lock's whole job is to notice. So every test here is a way the tree and the lock can come
apart -- a file added, a file gone, a byte changed, a size wrong, a role invented, an artifact
claimed to live somewhere a check could not read it -- and the assertion is always that the
checker refuses rather than reports a count.

The fetch half is tested through a `file:` archive, because the mechanism has to be known to work
before anything is moved, not after. Nothing is archived today; these build a lock that says
something is, point it at bytes in a temporary directory, and watch it verified, and watch it
refused when the bytes are wrong, missing, or named by a scheme the tool cannot resolve.

Run: python3 -m pytest tools/tests/test_check_evidence.py
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


evidence = _load("check_evidence", "check-evidence.py")
fetch = _load("fetch_evidence", "fetch-evidence.py")
LOCK = json.loads(open(os.path.join(ROOT, "tools", "evidence-lock.json"), encoding="utf-8").read())


class TestTheLockDescribesThisTree(unittest.TestCase):
    def test_the_committed_lock_verifies(self):
        self.assertEqual([], evidence.verify(pathlib.Path(ROOT), LOCK))

    def test_it_names_every_tracked_artifact_and_no_other(self):
        on_disk = set(evidence.tracked(pathlib.Path(ROOT)))
        named = {a["path"] for a in LOCK["artifacts"]}
        self.assertEqual(on_disk, named)

    def test_every_artifact_has_one_of_the_three_roles(self):
        for artifact in LOCK["artifacts"]:
            with self.subTest(path=artifact["path"]):
                self.assertIn(artifact["role"], evidence.ROLES)

    def test_every_reader_is_recorded_for_something(self):
        used = {r for a in LOCK["artifacts"] for r in a["readBy"]}
        self.assertEqual(set(evidence.READERS), used)

    def test_the_weakly_held_set_is_visible(self):
        # An artifact whose only reader is the link check is verified to have working links and
        # nothing else. That is a real distinction and the lock has to keep making it, because
        # `active` alone reads as "a check depends on these bytes".
        links_only = [a for a in LOCK["artifacts"] if a["readBy"] == ["links"]]
        self.assertTrue(links_only)
        for artifact in links_only:
            with self.subTest(path=artifact["path"]):
                self.assertEqual("active", artifact["role"])

    def test_every_role_is_used_by_something(self):
        # A role nothing carries is a classification nobody has tested.
        used = {a["role"] for a in LOCK["artifacts"]}
        self.assertEqual(set(evidence.ROLES), used)

    def test_nothing_a_check_reads_lives_outside_this_repository(self):
        for artifact in LOCK["artifacts"]:
            if artifact["role"] not in evidence.MOVABLE:
                with self.subTest(path=artifact["path"]):
                    self.assertIsNone(artifact["archive"])

    def test_the_lock_records_the_commit_it_was_measured_at(self):
        self.assertRegex(LOCK["measuredAt"], r"^[0-9a-f]{40}$")


class TestItRefusesADisagreement(unittest.TestCase):
    """Each way the lock and the tree can come apart, watched being refused."""

    def setUp(self):
        self.root = pathlib.Path(ROOT)
        self.lock = copy.deepcopy(LOCK)

    def problems(self, lock=None):
        return evidence.verify(self.root, lock if lock is not None else self.lock)

    def test_an_artifact_the_lock_does_not_name(self):
        dropped = self.lock["artifacts"].pop(0)
        self.assertTrue(any(dropped["path"] in p and "not in the lock" in p
                            for p in self.problems()))

    def test_a_lock_entry_naming_a_file_that_is_gone(self):
        self.lock["artifacts"].append(
            {"path": "examples/gone/results.json", "sha256": "0" * 64, "bytes": 1,
             "role": "archived", "archive": None})
        self.assertTrue(any("examples/gone/results.json" in p and "not tracked" in p
                            for p in self.problems()))

    def test_a_byte_that_changed(self):
        self.lock["artifacts"][0]["sha256"] = "f" * 64
        self.assertTrue(any("sha256" in p for p in self.problems()))

    def test_a_size_that_changed(self):
        self.lock["artifacts"][0]["bytes"] = 1
        self.assertTrue(any("bytes" in p for p in self.problems()))

    def test_a_role_that_is_not_one_of_the_three(self):
        self.lock["artifacts"][0]["role"] = "probably-fine"
        self.assertTrue(any("is not one of" in p for p in self.problems()))

    def test_a_reader_that_is_not_one_of_the_three(self):
        self.lock["artifacts"][0]["readBy"] = ["vibes"]
        self.assertTrue(any("is not a list drawn from" in p for p in self.problems()))

    def test_a_role_its_readers_do_not_support(self):
        # The lock cannot say `archived` about something it also says a check reads.
        for artifact in self.lock["artifacts"]:
            if artifact["role"] == "active":
                artifact["role"] = "archived"
                break
        self.assertTrue(any("makes it active" in p for p in self.problems()))

    def test_an_artifact_a_check_reads_claimed_to_live_elsewhere(self):
        # The rule that keeps the gate runnable offline: what a check reads stays in the tree.
        for artifact in self.lock["artifacts"]:
            if artifact["role"] == "active":
                artifact["archive"] = "https://example.invalid/x"
                break
        self.assertTrue(any("cannot live outside this repository" in p for p in self.problems()))

    def test_an_archived_artifact_may_be_claimed_to_live_elsewhere(self):
        # The other half of the same rule: the movable set is exactly the unread one. Its bytes
        # are still in the tree here, so only the archive field is exercised.
        for artifact in self.lock["artifacts"]:
            if artifact["role"] == "archived":
                artifact["archive"] = "https://example.invalid/x"
                break
        self.assertEqual([], [p for p in self.problems() if "outside this repository" in p])

    def test_an_empty_lock_proves_nothing(self):
        self.assertEqual(["the lock names no artifact -- this check proved nothing"],
                         self.problems({"artifacts": []}))

    def test_a_path_named_twice(self):
        self.lock["artifacts"].append(copy.deepcopy(self.lock["artifacts"][0]))
        self.assertTrue(any("more than once" in p for p in self.problems()))


class TestFetchingVerifiesWhereverTheBytesAre(unittest.TestCase):
    """The mechanism a move would rely on, exercised before anything is moved."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = pathlib.Path(self.tmp.name)
        # One real archived artifact, copied out of the tree to stand in for an archive.
        self.artifact = next(a for a in LOCK["artifacts"] if a["role"] == "archived")
        self.elsewhere = self.home / "archived-bytes"
        self.elsewhere.write_bytes((pathlib.Path(ROOT) / self.artifact["path"]).read_bytes())

    def lock_with(self, archive):
        lock = {"artifacts": [dict(self.artifact, archive=archive)]}
        return lock

    def run_verify(self, lock):
        cache = self.home / "cache"
        cache.mkdir(exist_ok=True)
        return fetch.verify(lock, pathlib.Path(ROOT), cache)

    def test_the_committed_lock_verifies_from_the_repository(self):
        problems, examined, fetched = self.run_verify(LOCK)
        self.assertEqual([], problems)
        self.assertEqual(len(LOCK["artifacts"]), examined)
        self.assertEqual([], fetched)

    def test_a_file_archive_is_fetched_and_verified(self):
        problems, examined, fetched = self.run_verify(self.lock_with(f"file:{self.elsewhere}"))
        self.assertEqual([], problems)
        self.assertEqual(1, examined)
        self.assertEqual([self.artifact["path"]], fetched)

    def test_fetched_bytes_that_do_not_match_the_lock_are_refused(self):
        self.elsewhere.write_bytes(b"not the evidence")
        problems, examined, _ = self.run_verify(self.lock_with(f"file:{self.elsewhere}"))
        self.assertEqual(0, examined)
        self.assertTrue(any("hash to" in p for p in problems))

    def test_an_archive_that_is_not_there_is_a_failure_and_not_a_skip(self):
        problems, examined, _ = self.run_verify(self.lock_with(f"file:{self.home}/absent"))
        self.assertEqual(0, examined)
        self.assertTrue(any("names no file" in p for p in problems))

    def test_a_scheme_the_tool_cannot_resolve_is_a_failure(self):
        problems, examined, _ = self.run_verify(self.lock_with("ftp://example.invalid/x"))
        self.assertEqual(0, examined)
        self.assertTrue(any("not an archive identifier" in p for p in problems))

    def test_an_empty_lock_proves_nothing(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            empty = self.home / "empty.json"
            empty.write_text(json.dumps({"artifacts": []}))
            code = fetch.main(["--verify", "--lock", str(empty)])
        self.assertEqual(1, code)
        self.assertIn("proved nothing", err.getvalue())

    def test_the_cache_does_not_survive_the_run(self):
        out = io.StringIO()
        before = set(os.listdir(tempfile.gettempdir()))
        with redirect_stdout(out):
            self.assertEqual(0, fetch.main(["--verify"]))
        left = {n for n in set(os.listdir(tempfile.gettempdir())) - before
                if n.startswith("evidence-")}
        self.assertEqual(set(), left)


class TestTheMeasurementCanSeeAnything(unittest.TestCase):
    """--measure classifies by what it observed, so an audit hook that does not fire would call
    every artifact `archived`. This watches the hook see one read."""

    def test_the_audit_hook_records_a_read_under_examples(self):
        root = pathlib.Path(ROOT)
        target = LOCK["artifacts"][0]["path"]
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            (home / "sitecustomize.py").write_text(evidence.SITECUSTOMIZE, encoding="utf-8")
            seen = evidence._trace(
                root,
                [sys.executable, "-c",
                 f"open({target!r}, 'rb').read(1)"],
                home, "probe")
        # (reader, path): the tool that opened it, and what it opened.
        self.assertIn(target, {path for _, path in seen})

    def test_the_lock_s_own_hashing_is_not_counted_as_a_read(self):
        # check-evidence.py hashes every artifact it names. Counting that would find everything
        # read and classify nothing `archived` -- the checker standing in as the evidence that
        # something uses the bytes. It happens in its own process and, through these tests,
        # inside pytest's, so the exclusion is by call stack rather than by command.
        root = pathlib.Path(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            (home / "sitecustomize.py").write_text(evidence.SITECUSTOMIZE, encoding="utf-8")
            # Two different artifacts, so that a set of (reader, path) cannot hide the
            # difference: one read only through the lock's own hashing, one read plainly.
            hashed = LOCK["artifacts"][0]["path"]
            plain = LOCK["artifacts"][1]["path"]
            probe = (
                "import importlib.util, sys, pathlib\n"
                "spec = importlib.util.spec_from_file_location('ce', 'tools/check-evidence.py')\n"
                "ce = importlib.util.module_from_spec(spec); sys.modules['ce'] = ce\n"
                "spec.loader.exec_module(ce)\n"
                f"ce.digest(pathlib.Path({hashed!r}))\n"
                f"open({plain!r}, 'rb').read(1)\n"
            )
            seen = evidence._trace(root, [sys.executable, "-c", probe], home, "self")
        opened = {path for _, path in seen}
        self.assertIn(plain, opened)
        self.assertNotIn(hashed, opened)

    def test_a_read_is_attributed_to_the_tool_that_made_it(self):
        for reader, expected in (("tools/pack-map.py", "package"),
                                 ("tools/validate-repo.py", "links"),
                                 ("tools/check-map.py", "checks"),
                                 ("/usr/bin/pytest", "checks")):
            with self.subTest(reader=reader):
                self.assertEqual(expected, evidence._reader_class(reader))
        self.assertIsNone(evidence._reader_class("tools/check-evidence.py"))

    def test_the_role_follows_from_who_reads_it(self):
        self.assertEqual("release", evidence.role_of(["checks", "package"]))
        self.assertEqual("release", evidence.role_of(["package"]))
        self.assertEqual("active", evidence.role_of(["checks"]))
        self.assertEqual("active", evidence.role_of(["links"]))
        self.assertEqual("archived", evidence.role_of([]))

    def test_a_command_that_stops_early_is_refused(self):
        root = pathlib.Path(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            (home / "sitecustomize.py").write_text(evidence.SITECUSTOMIZE, encoding="utf-8")
            with self.assertRaises(SystemExit):
                evidence._trace(root, [sys.executable, "-c", "raise SystemExit(3)"],
                                home, "broken")


class TestTheGateRunsIt(unittest.TestCase):
    def test_the_evidence_step_is_in_the_gate(self):
        text = open(os.path.join(ROOT, "tools", "validate-repo.py"), encoding="utf-8").read()
        self.assertIn("step_evidence", text)
        self.assertIn("tools/check-evidence.py", text)

    def test_with_evidence_asks_the_fetching_verifier(self):
        text = open(os.path.join(ROOT, "tools", "validate-repo.py"), encoding="utf-8").read()
        self.assertIn("--with-evidence", text)
        self.assertIn("tools/fetch-evidence.py", text)

    def test_verifying_the_whole_tree_is_cheap_enough_to_always_run(self):
        # 15.5 MB of sha256. If this ever stops being true the step needs a scope, not a skip.
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check-evidence.py")],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("verified by sha256", proc.stdout)


if __name__ == "__main__":
    unittest.main()


class TestTheCommitTheLockNamesIsOneThisRepositoryHas(unittest.TestCase):
    """#404: two stale commit references got through, and nothing stopped them drifting again.

    `--measure` records `git rev-parse HEAD`, so a branch whose history is rewritten -- amended,
    rebased, squashed -- leaves the lock naming an orphan. The verifier hashed every artifact the
    lock named and never asked whether the commit it named still existed. It does now, and the
    document derived from the lock is held to the same commit: the two were found disagreeing on
    main the day this was written.
    """

    def root(self):
        return pathlib.Path(ROOT)

    def test_the_committed_lock_names_a_commit_this_repository_has(self):
        self.assertEqual([], evidence.measured_at_problems(self.root(), LOCK))

    def test_a_commit_that_does_not_exist_is_refused(self):
        lock = copy.deepcopy(LOCK)
        lock["measuredAt"] = "0" * 40
        problems = evidence.measured_at_problems(self.root(), lock)
        self.assertTrue(any("not a commit this repository has" in p for p in problems), problems)

    def test_a_lock_that_says_nothing_about_its_commit_is_refused(self):
        lock = copy.deepcopy(LOCK)
        del lock["measuredAt"]
        self.assertEqual(["the lock does not say which commit it was measured at"],
                         evidence.measured_at_problems(self.root(), lock))

    def test_a_commit_off_this_history_is_refused(self):
        """Real, and the case #404 names: a commit that exists as an object but is not on the
        history this branch has. An empty commit made here and never merged is exactly that."""
        with tempfile.TemporaryDirectory() as tmp:
            side = os.path.join(tmp, "side")
            subprocess.run(["git", "init", "-q", side], check=True, capture_output=True)
            env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
            subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "elsewhere"],
                           cwd=side, check=True, env=env, capture_output=True)
            other = subprocess.run(["git", "rev-parse", "HEAD"], cwd=side, check=True,
                                   capture_output=True, text=True).stdout.strip()
        lock = copy.deepcopy(LOCK)
        lock["measuredAt"] = other
        problems = evidence.measured_at_problems(self.root(), lock)
        # Unknown here, because it was made in a repository this one has never fetched.
        self.assertTrue(any(other in p for p in problems), problems)

    def test_the_inventory_and_the_lock_must_name_the_same_commit(self):
        """The drift that was live on main: the document's label and the lock disagreeing, with
        the tables derived from the lock."""
        lock = copy.deepcopy(LOCK)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
        lock["measuredAt"] = head
        found = evidence.MEASURED_AT_LABEL.search(
            evidence.INVENTORY.read_text(encoding="utf-8"))
        self.assertIsNotNone(found, "the inventory no longer carries a label to check")
        if head.startswith(found.group(1)):
            self.skipTest("the inventory already names HEAD; the disagreement case is below")
        problems = evidence.measured_at_problems(self.root(), lock)
        self.assertTrue(any("one of them is stale" in p for p in problems), problems)


class TestAMeasurementSaysWhatItWasTakenOver(unittest.TestCase):
    """#408: `--measure` gave a different role for the same file on different runs.

    A role is "what the checks read", so a run in which a check did not get as far as reading is
    a different measurement. `_trace` deliberately accepts a failing gate -- re-measuring happens
    while the lock is stale by construction -- but it accepted *any* failing gate, so a role
    could follow an unrelated broken step. The lock now records what the measurement was taken
    over, and a run with any other failing step is refused unless the caller says otherwise.
    """

    def test_the_committed_lock_records_what_it_was_measured_over(self):
        self.assertIn("measuredOver", LOCK, "the lock does not say what run produced it (#408)")
        self.assertIn("complete", LOCK["measuredOver"])
        self.assertIn("gateStepsFailed", LOCK["measuredOver"])

    def test_a_clean_run_is_recorded_complete(self):
        lock = evidence.build(pathlib.Path(ROOT), {p: [] for p in evidence.tracked(pathlib.Path(ROOT))},
                              None, [])
        self.assertEqual({"gateStepsFailed": [], "complete": True}, lock["measuredOver"])

    def test_the_evidence_step_alone_does_not_make_a_run_partial(self):
        """It fails by construction while the lock is being rewritten, so counting it would
        refuse every measurement there is."""
        lock = evidence.build(pathlib.Path(ROOT), {p: [] for p in evidence.tracked(pathlib.Path(ROOT))},
                              None, [evidence.EVIDENCE_STEP])
        self.assertEqual({"gateStepsFailed": [], "complete": True}, lock["measuredOver"])

    def test_any_other_failing_step_makes_it_partial_and_is_recorded(self):
        lock = evidence.build(pathlib.Path(ROOT), {p: [] for p in evidence.tracked(pathlib.Path(ROOT))},
                              None, [evidence.EVIDENCE_STEP, "every citation resolves in its corpus"])
        self.assertEqual({"gateStepsFailed": ["every citation resolves in its corpus"],
                          "complete": False}, lock["measuredOver"])


class TestWhatIsFailingByConstructionWhileTheLockIsRewritten(unittest.TestCase):
    """The evidence step fails while the lock is stale, and so do the lock's own tests, which
    hold the committed lock to the tree. Excusing the second only in the first's company keeps
    the guard from excusing a real test failure -- which is the step whose absence moves a role,
    because a file read only by a test is read by nothing when the tests do not run."""

    def test_the_evidence_step_alone_is_excused(self):
        self.assertEqual([], evidence.partial_steps([evidence.EVIDENCE_STEP]))

    def test_the_tests_step_is_excused_only_beside_it(self):
        self.assertEqual([], evidence.partial_steps([evidence.EVIDENCE_STEP, evidence.TESTS_STEP]))
        self.assertEqual([evidence.TESTS_STEP], evidence.partial_steps([evidence.TESTS_STEP]))

    def test_any_other_step_makes_it_partial(self):
        self.assertEqual(["every citation resolves in its corpus"],
                         evidence.partial_steps([evidence.EVIDENCE_STEP,
                                                 "every citation resolves in its corpus"]))
