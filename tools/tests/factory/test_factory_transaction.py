#!/usr/bin/env python3
"""transaction.py never writes, deletes or restores outside --out (#183, #184, #228).

Both defects were found by an independent review and reproduced before they were fixed: a journal
committed into an engine made `recover()` delete a file beside the engine, and a symlinked
directory in an engine made a commit write one file and delete another in the directory it
pointed to. These cases drive `Stage` and `recover()` directly, on a scratch tree, so they are
fast and need no package; test_factory_produce.py covers the refusal through `produce`.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.join(os.path.dirname(os.path.dirname(HERE)), "factory")
sys.path.insert(0, FACTORY)
import transaction  # noqa: E402
import intake  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def listing(root):
    found = {}
    for directory, _, names in os.walk(root):
        for name in names:
            path = os.path.join(directory, name)
            with open(path, encoding="utf-8") as handle:
                found[os.path.relpath(path, root)] = handle.read()
    return found


class Scratch(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = os.path.realpath(self._tmp.name)
        self.out = os.path.join(self.tmp, "engine")
        write(os.path.join(self.out, "backlog", "001.md"), "one")
        self.victim = os.path.join(self.tmp, "victim.txt")
        write(self.victim, "precious")

    def tearDown(self):
        self._tmp.cleanup()

    def read(self, relative):
        with open(os.path.join(self.out, *relative.split("/")), encoding="utf-8") as handle:
            return handle.read()

    def assertNoStaging(self):
        self.assertEqual([n for n in os.listdir(self.tmp) if ".factory-produce-" in n], [])


class TestHostileJournal(Scratch):
    """#183: a journal that did not come from a dead run touches nothing."""

    def plant(self, make_work=True, **lists):
        work = os.path.join(self.tmp, ".engine.factory-produce-planted")
        if make_work:
            os.makedirs(os.path.join(work, "backup"), exist_ok=True)
        journal = {"format": transaction.JOURNAL_FORMAT, "out": self.out, "work": work,
                   "added": [], "changed": [], "removed": [], "directories": []}
        journal.update(lists)
        write(os.path.join(self.out, transaction.JOURNAL), json.dumps(journal))
        return work

    def assertRefusedAndUntouched(self, fragment):
        before = listing(self.tmp)
        with self.assertRaises(intake.Refused) as caught:
            transaction.recover(self.out)
        self.assertIn(fragment, str(caught.exception))
        self.assertIn("nothing in it was rolled back", str(caught.exception))
        self.assertEqual(before, listing(self.tmp))

    def test_a_path_leaving_out_is_refused_and_the_file_outside_survives(self):
        for bad in ("../victim.txt", "backlog/../../victim.txt", "/" + self.victim.lstrip("/"), "", "./x", "a//b"):
            with self.subTest(path=bad):
                self.plant(added=[bad])
                self.assertRefusedAndUntouched("not a relative path inside the engine")
                self.assertTrue(os.path.isfile(self.victim))

    def test_every_list_is_checked(self):
        for key in ("added", "changed", "removed", "directories"):
            with self.subTest(key=key):
                self.plant(**{key: ["../victim.txt"]})
                self.assertRefusedAndUntouched(f"its {key!r} list")

    def test_a_non_string_path_is_refused(self):
        self.plant(added=[7])
        self.assertRefusedAndUntouched("not a relative path")

    def test_a_working_directory_that_does_not_exist_is_refused(self):
        self.plant(make_work=False, added=["backlog/001.md"])
        self.assertRefusedAndUntouched("does not exist")
        self.assertTrue(os.path.isfile(os.path.join(self.out, "backlog", "001.md")))

    def test_a_path_through_a_symlink_is_refused(self):
        os.symlink(self.tmp, os.path.join(self.out, "escape"))
        self.plant(added=["escape/victim.txt"])
        self.assertRefusedAndUntouched("passes through the symlink escape")
        self.assertTrue(os.path.isfile(self.victim))

    def test_a_changed_path_with_no_backup_is_refused(self):
        self.plant(changed=["backlog/001.md"])
        self.assertRefusedAndUntouched("has no backed-up file")

    def test_a_genuine_journal_is_still_rolled_back(self):
        work = self.plant(added=["backlog/002.md"], changed=["backlog/001.md"], directories=[])
        write(os.path.join(work, "backup", "backlog", "001.md"), "one")
        write(os.path.join(self.out, "backlog", "002.md"), "added by the dead run")
        write(os.path.join(self.out, "backlog", "001.md"), "changed by the dead run")
        transaction.recover(self.out)
        self.assertEqual(listing(self.out), {os.path.join("backlog", "001.md"): "one"})
        self.assertFalse(os.path.exists(work))

    # #228: the rollback's own scratch paths, inside the working directory, are not trusted either.

    def planted_restore(self):
        """The reproduction from #228: a genuine-looking journal whose backup would be copied into
        `work/restoring`, which is a link to a file outside --out."""
        work = self.plant(changed=["backlog/001.md"])
        write(os.path.join(work, "backup", "backlog", "001.md"), "ATTACKER bytes")
        return work

    def test_a_restoring_symlink_is_refused_and_its_target_is_unchanged(self):
        work = self.planted_restore()
        os.symlink(self.victim, os.path.join(work, "restoring"))
        self.assertRefusedAndUntouched("is not a regular file")
        with open(self.victim, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "precious")
        self.assertFalse(os.path.islink(os.path.join(self.out, "backlog", "001.md")))

    def test_a_symlinked_backup_directory_is_refused(self):
        work = self.plant(changed=["backlog/001.md"])
        elsewhere = os.path.join(self.tmp, "elsewhere")
        write(os.path.join(elsewhere, "backlog", "001.md"), "ATTACKER bytes")
        os.rmdir(os.path.join(work, "backup"))
        os.symlink(elsewhere, os.path.join(work, "backup"))
        self.assertRefusedAndUntouched("is not a real directory")

    def test_a_backed_up_file_that_is_a_symlink_is_refused(self):
        work = self.plant(changed=["backlog/001.md"])
        os.makedirs(os.path.join(work, "backup", "backlog"))
        os.symlink(self.victim, os.path.join(work, "backup", "backlog", "001.md"))
        self.assertRefusedAndUntouched("has no backed-up file")

    def test_a_regular_restoring_file_left_by_a_crash_mid_restore_does_not_block_recovery(self):
        work = self.planted_restore()
        write(os.path.join(work, "restoring"), "half a copy")
        transaction.recover(self.out)
        self.assertEqual(listing(self.out), {os.path.join("backlog", "001.md"): "ATTACKER bytes"})
        self.assertFalse(os.path.exists(work))

    def test_a_link_planted_after_the_check_fails_the_copy_rather_than_being_written_through(self):
        source = os.path.join(self.tmp, "source.txt")
        write(source, "ATTACKER bytes")
        destination = os.path.join(self.tmp, "restoring")
        os.symlink(self.victim, destination)
        with self.assertRaises(OSError):
            transaction._copy_without_following(source, destination)
        with open(self.victim, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "precious")

    def test_rollback_itself_does_not_write_through_a_link_planted_after_the_check(self):
        # The journal check ran and passed; the link appears afterwards, before the restore.
        work = self.planted_restore()
        journal = {"out": self.out, "work": work, "added": [], "changed": ["backlog/001.md"],
                   "removed": [], "directories": []}
        os.symlink(self.victim, os.path.join(work, "restoring"))
        with self.assertRaises(OSError):
            transaction._rollback(journal)
        with open(self.victim, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "precious")

    def test_the_open_itself_refuses_a_link_that_appears_between_the_checks_and_the_open(self):
        source = os.path.join(self.tmp, "source.txt")
        write(source, "ATTACKER bytes")
        destination = os.path.join(self.tmp, "restoring")
        os.symlink(self.victim, destination)
        # Both name-based checks see nothing, as they would if the link arrived just after them.
        with mock.patch.object(transaction.os.path, "islink", return_value=False), \
                mock.patch.object(transaction.os.path, "lexists", return_value=False):
            with self.assertRaises(OSError):
                transaction._copy_without_following(source, destination)
        with open(self.victim, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "precious")

    def test_the_copy_keeps_bytes_and_mode(self):
        source = os.path.join(self.tmp, "tool.sh")
        write(source, "#!/bin/sh\n")
        os.chmod(source, 0o755)
        destination = os.path.join(self.tmp, "restoring")
        transaction._copy_without_following(source, destination)
        with open(destination, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "#!/bin/sh\n")
        self.assertEqual(os.stat(destination).st_mode & 0o777, 0o755)


class TestVerifiedCommitHoldsOutToWhatWasVerified(Scratch):
    """#335: a verified commit is refused when --out no longer holds the inputs that were verified.

    The mutation-set check that was already here (`--out changed while produce ran`) looks only at
    the paths the run writes or removes, so an engine-owned source file edited in --out while
    produce ran was preserved -- correctly -- and the run still called the result verified, though
    the gate had built and tested a tree that no longer existed anywhere.

    Every assertion below names the verified-commit refusal *and* the exact path and reason, never
    `Refused` alone: the older mutation-set refusal, the symlink refusal and a `CommitError` are
    all refusals of this same call, so a verdict-only assertion would pass on a different rule
    firing for a different reason (#283).
    """

    def setUp(self):
        super().setUp()
        # An engine's own source and build input: neither is in any mutation set below.
        write(os.path.join(self.out, "src", "Engine", "Rule.cs"), "class Rule { }")
        write(os.path.join(self.out, "src", "Engine", "Engine.csproj"), "<Project />")
        # Test output the gate writes and no build reads: not an input, so not guarded.
        write(os.path.join(self.out, "TestResults", "engine.trx"), "<TestRun />")

    def stage_generated_file(self, stage):
        """What the run itself produced: one added generated file, the whole of its mutation set."""
        write(os.path.join(stage.root, "src", "Engine", "Generated", "Entries.g.cs"), "// generated")

    def assertRefusedVerified(self, concurrent, *expected):
        """Run a verified commit with `concurrent(--out)` happening after the copy; assert the refusal."""
        with transaction.Stage(self.out) as stage:
            self.stage_generated_file(stage)
            stage.testing()  # what the gate built and tested: the staging copy, as it is here (#370)
            concurrent(self.out)
            after_the_edit = listing(self.out)
            with self.assertRaises(intake.Refused) as caught:
                stage.commit(verified=True)
        message = str(caught.exception)
        self.assertIn("--out changed after the engine was verified", message)
        for fragment in expected:
            self.assertIn(fragment, message)
        self.assertIn("run produce again", message)
        # The user's concurrent edit stands, and nothing this run staged was written over it.
        self.assertEqual(after_the_edit, listing(self.out))
        self.assertFalse(os.path.lexists(os.path.join(self.out, transaction.JOURNAL)))
        self.assertEqual([n for n in os.listdir(self.tmp) if ".factory-produce-" in n], [])
        return message

    def test_a_source_file_edited_after_verification_refuses_and_keeps_the_edit(self):
        self.assertRefusedVerified(lambda out: write(os.path.join(out, "src", "Engine", "Rule.cs"),
                                                     "class Rule { int mine; }"),
                                   "src/Engine/Rule.cs (changed)")
        self.assertEqual(self.read("src/Engine/Rule.cs"), "class Rule { int mine; }")

    def test_a_build_input_edited_after_verification_refuses(self):
        self.assertRefusedVerified(lambda out: write(os.path.join(out, "src", "Engine", "Engine.csproj"),
                                                     "<Project><ItemGroup /></Project>"),
                                   "src/Engine/Engine.csproj (changed)")

    def test_a_source_file_added_after_verification_refuses(self):
        # An added file is an input too: the gate compiled a tree without it.
        self.assertRefusedVerified(lambda out: write(os.path.join(out, "src", "Engine", "Extra.cs"), "class Extra { }"),
                                   "src/Engine/Extra.cs (added)")
        self.assertEqual(self.read("src/Engine/Extra.cs"), "class Extra { }")

    def test_a_source_file_removed_after_verification_refuses(self):
        self.assertRefusedVerified(lambda out: os.remove(os.path.join(out, "src", "Engine", "Rule.cs")),
                                   "src/Engine/Rule.cs (removed)")

    def test_a_rename_after_verification_names_both_halves(self):
        def rename(out):
            os.rename(os.path.join(out, "src", "Engine", "Rule.cs"), os.path.join(out, "src", "Engine", "Moved.cs"))
        self.assertRefusedVerified(rename, "src/Engine/Moved.cs (added)", "src/Engine/Rule.cs (removed)")

    def test_an_executable_bit_changed_after_verification_refuses(self):
        # The one mode bit git tracks, and the one the mutation set compares.
        def flip(out):
            os.chmod(os.path.join(out, "src", "Engine", "Rule.cs"), 0o755)
        self.assertRefusedVerified(flip, "src/Engine/Rule.cs (changed)")

    def test_build_output_changed_after_verification_is_not_an_input_and_commits(self):
        """The guard is no broader than necessary: TestResults/ and bin/ are written, never read."""
        with transaction.Stage(self.out) as stage:
            self.stage_generated_file(stage)
            stage.testing()
            write(os.path.join(self.out, "TestResults", "engine.trx"), "<TestRun result='later' />")
            write(os.path.join(self.out, "bin", "Engine.dll"), "built after the copy")
            added, changed, removed = stage.commit(verified=True)
        self.assertEqual((added, changed, removed), (["src/Engine/Generated/Entries.g.cs"], [], []))
        self.assertEqual(self.read("TestResults/engine.trx"), "<TestRun result='later' />")
        self.assertEqual(self.read("bin/Engine.dll"), "built after the copy")

    def test_an_unverified_commit_still_keeps_a_concurrent_edit_and_commits(self):
        """--no-verify claims nothing about a build, so it is not held to one (the old behaviour)."""
        with transaction.Stage(self.out) as stage:
            self.stage_generated_file(stage)
            write(os.path.join(self.out, "src", "Engine", "Rule.cs"), "class Rule { int mine; }")
            added, changed, removed = stage.commit(verified=False)
        self.assertEqual((added, changed, removed), (["src/Engine/Generated/Entries.g.cs"], [], []))
        self.assertEqual(self.read("src/Engine/Rule.cs"), "class Rule { int mine; }")

    def test_a_verified_commit_with_no_concurrent_change_still_commits_everything(self):
        with transaction.Stage(self.out) as stage:
            self.stage_generated_file(stage)
            write(os.path.join(stage.root, "src", "Engine", "Rule.cs"), "class Rule { int factory; }")
            os.remove(os.path.join(stage.root, "backlog", "001.md"))
            stage.testing()
            added, changed, removed = stage.commit(verified=True)
        self.assertEqual((added, changed, removed),
                         (["src/Engine/Generated/Entries.g.cs"], ["src/Engine/Rule.cs"], ["backlog/001.md"]))
        self.assertEqual(self.read("src/Engine/Rule.cs"), "class Rule { int factory; }")
        self.assertFalse(os.path.exists(os.path.join(self.out, "backlog")))

    def test_a_path_this_run_writes_that_moved_in_out_is_refused_as_verified_too(self):
        """A concurrent edit to a path the run also writes: refused, and the verified refusal is the one raised."""
        with transaction.Stage(self.out) as stage:
            write(os.path.join(stage.root, "src", "Engine", "Rule.cs"), "class Rule { int factory; }")
            stage.testing()
            write(os.path.join(self.out, "src", "Engine", "Rule.cs"), "class Rule { int mine; }")
            with self.assertRaises(intake.Refused) as caught:
                stage.commit(verified=True)
        self.assertIn("--out changed after the engine was verified", str(caught.exception))
        self.assertIn("src/Engine/Rule.cs (changed)", str(caught.exception))
        self.assertEqual(self.read("src/Engine/Rule.cs"), "class Rule { int mine; }")


class TestVerifiedCommitProvesTheTreeThatWasTested(Scratch):
    """#370: the staging copy committed is the staging copy the gate built and tested, not another one.

    #335 bound one side of the handoff -- `--out` did not move under the run. The other side was
    unbound: verification happens in the staging copy, the gate executes the engine's own test code
    there, and nothing compared the staging copy at commit time with the staging copy that was
    built and tested. A test that writes to a staged source after the build -- or leaves a delayed
    writer behind -- changed the bytes that were committed, and `provenance.json` said
    `"verification": {"verified": true}` over a tree nothing had built (#222).

    `Stage.testing()` is the name the proof gets: verify calls it immediately before the gate runs,
    and a verified commit is held to it. Each assertion names the refusal's own words and the exact
    path and reason, never `Refused` alone (#283).
    """

    def setUp(self):
        super().setUp()
        write(os.path.join(self.out, "src", "Engine", "Rule.cs"), "class Rule { }")
        write(os.path.join(self.out, "src", "Engine", "Engine.csproj"), "<Project />")

    def staged(self, stage, relative, text):
        write(os.path.join(stage.root, *relative.split("/")), text)

    def assertRefusedTested(self, after_the_gate, *expected):
        """A run whose gate step does `after_the_gate(staging copy)` after it has built and tested it."""
        before = listing(self.out)
        with transaction.Stage(self.out) as stage:
            self.staged(stage, "src/Engine/Entries.g.cs", "// generated")
            stage.testing()
            after_the_gate(stage.root)
            with self.assertRaises(intake.Refused) as caught:
                stage.commit(verified=True)
        message = str(caught.exception)
        self.assertIn("the engine changed after it was built and tested", message)
        for fragment in expected:
            self.assertIn(fragment, message)
        self.assertIn("run produce again", message)
        self.assertEqual(before, listing(self.out), "--out is byte-identical to how it started")
        self.assertFalse(os.path.lexists(os.path.join(self.out, transaction.JOURNAL)))
        self.assertNoStaging()
        return message

    def test_a_test_step_that_writes_to_a_staged_source_after_the_build_refuses(self):
        """The mutation: a test that writes into the engine it is testing."""
        def write_a_source(root):
            write(os.path.join(root, "src", "Engine", "Rule.cs"), "class Rule { int writtenByATest; }")
        self.assertRefusedTested(write_a_source, "src/Engine/Rule.cs (changed)")

    def test_a_source_a_test_step_adds_after_the_build_refuses(self):
        def add_a_source(root):
            write(os.path.join(root, "src", "Engine", "Slipped.cs"), "class Slipped { }")
        self.assertRefusedTested(add_a_source, "src/Engine/Slipped.cs (added)")

    def test_a_source_a_test_step_deletes_after_the_build_refuses(self):
        self.assertRefusedTested(lambda root: os.remove(os.path.join(root, "src", "Engine", "Rule.cs")),
                                 "src/Engine/Rule.cs (removed)")

    def test_a_delayed_writer_that_lands_on_a_generated_file_refuses(self):
        """The file the run itself wrote is an input of the proof too: the gate compiled it."""
        def rewrite(root):
            write(os.path.join(root, "src", "Engine", "Entries.g.cs"), "// not what the gate compiled")
        self.assertRefusedTested(rewrite, "src/Engine/Entries.g.cs (changed)")

    def test_the_build_output_the_gate_leaves_in_the_staging_copy_is_not_an_input(self):
        """No broader than necessary: the proof produced these, so they cannot be inputs of it."""
        with transaction.Stage(self.out) as stage:
            self.staged(stage, "src/Engine/Entries.g.cs", "// generated")
            stage.testing()
            self.staged(stage, "TestResults/run.trx", "<TestRun />")
            self.staged(stage, "artifacts/Engine.dll", "built")
            self.staged(stage, "src/Engine/obj/project.assets.json", "{}")
            self.staged(stage, "src/Engine/bin/Debug/Engine.dll", "built")
            added, changed, removed = stage.commit(verified=True)
        self.assertEqual((added, changed, removed),
                         (["TestResults/run.trx", "artifacts/Engine.dll", "src/Engine/Entries.g.cs"], [], []))

    def test_what_verify_writes_before_the_gate_is_part_of_what_was_tested_and_commits(self):
        """restore's lock files and after_restore's rewritten record: written before, so tested."""
        with transaction.Stage(self.out) as stage:
            self.staged(stage, "src/Engine/Entries.g.cs", "// generated")
            self.staged(stage, "src/Engine/packages.lock.json", '{"version": 1}')
            self.staged(stage, "provenance.json", '{"verification": {"verified": true}}')
            stage.testing()
            added, changed, removed = stage.commit(verified=True)
        self.assertEqual((added, changed, removed),
                         (["provenance.json", "src/Engine/Entries.g.cs", "src/Engine/packages.lock.json"], [], []))
        self.assertEqual(self.read("src/Engine/packages.lock.json"), '{"version": 1}')

    def test_a_fresh_out_is_held_to_the_tested_tree_too(self):
        """A fresh --out is committed by renaming the whole staging copy, so it carries the change along."""
        fresh = os.path.join(self.tmp, "new-engine")
        with transaction.Stage(fresh) as stage:
            write(os.path.join(stage.root, "src", "Engine", "Rule.cs"), "class Rule { }")
            stage.testing()
            write(os.path.join(stage.root, "src", "Engine", "Rule.cs"), "class Rule { int writtenByATest; }")
            with self.assertRaises(intake.Refused) as caught:
                stage.commit(verified=True)
        self.assertIn("the engine changed after it was built and tested", str(caught.exception))
        self.assertIn("src/Engine/Rule.cs (changed)", str(caught.exception))
        self.assertFalse(os.path.exists(fresh), "a refusal before the rename leaves no --out behind")

    def test_a_verified_commit_that_recorded_no_tested_tree_is_refused(self):
        """Fail closed: without the record there is nothing to compare, and `verified` would be a guess."""
        with transaction.Stage(self.out) as stage:
            self.staged(stage, "src/Engine/Entries.g.cs", "// generated")
            with self.assertRaises(intake.Refused) as caught:
                stage.commit(verified=True)
        self.assertIn("did not record the engine the gate built and tested", str(caught.exception))
        self.assertEqual(listing(self.out), listing(self.out))
        self.assertFalse(os.path.exists(os.path.join(self.out, "src", "Engine", "Entries.g.cs")))

    def test_an_unverified_commit_is_not_held_to_a_tree_nothing_tested(self):
        """--no-verify builds and tests nothing, so there is no proof for a commit to be held to."""
        with transaction.Stage(self.out) as stage:
            self.staged(stage, "src/Engine/Entries.g.cs", "// generated")
            added, changed, removed = stage.commit(verified=False)
        self.assertEqual((added, changed, removed), (["src/Engine/Entries.g.cs"], [], []))


class TestOutputIsExcludedWhereItIsProduced(Scratch):
    """#370: `artifacts` and `TestResults` are build output at the root of the engine, not at any depth.

    `_is_input` used to answer False when *any* directory component of a path was one of those two
    names, so `src/Engine/TestResults/override.targets` and `src/Engine/artifacts/Injected.cs` were
    classified as build output and left out of the verified commit's comparison -- though MSBuild
    imports the first and compiles the second. The exclusion is for the output a build writes at the
    root of the engine (`verify.verify_staged` deletes bin/ and obj/ there; the SDK's artifacts path
    and `dotnet test`'s TRX directory are the other two), not for every directory in the tree that
    shares a name with it.

    Each assertion names the verified-commit refusal *and* the exact path and reason: `commit`
    refuses in several other ways -- the mutation-set refusal, the symlink refusals, a CommitError --
    so asserting `Refused` alone would pass on the wrong rule firing (#283).
    """

    def setUp(self):
        super().setUp()
        write(os.path.join(self.out, "src", "Engine", "Engine.csproj"), "<Project />")
        # Hidden under a name the classification treated as build output, at a depth where it is not.
        write(os.path.join(self.out, "src", "Engine", "TestResults", "override.targets"), "<Project />")
        # The real build output, where a build actually writes it.
        write(os.path.join(self.out, "TestResults", "engine.trx"), "<TestRun />")
        write(os.path.join(self.out, "artifacts", "bin", "Engine.dll"), "built")

    def commit_with(self, concurrent):
        with transaction.Stage(self.out) as stage:
            write(os.path.join(stage.root, "src", "Engine", "Entries.g.cs"), "// generated")
            stage.testing()
            concurrent(self.out)
            with self.assertRaises(intake.Refused) as caught:
                stage.commit(verified=True)
        self.assertIn("--out changed after the engine was verified", str(caught.exception))
        self.assertNoStaging()
        return str(caught.exception)

    def test_a_targets_file_under_a_nested_TestResults_is_an_input(self):
        """MSBuild imports it, so the tree that was tested had the old bytes in it."""
        def edit(out):
            write(os.path.join(out, "src", "Engine", "TestResults", "override.targets"),
                  "<Project><Target Name='Inject' /></Project>")
        self.assertIn("src/Engine/TestResults/override.targets (changed)", self.commit_with(edit))

    def test_a_source_added_under_a_nested_artifacts_is_an_input(self):
        """The compiler globs **/*.cs, so a file put here after the gate ran was never compiled."""
        def add(out):
            write(os.path.join(out, "src", "Engine", "artifacts", "Injected.cs"), "class Injected { }")
        self.assertIn("src/Engine/artifacts/Injected.cs (added)", self.commit_with(add))

    def test_a_file_named_like_the_output_directories_is_an_input(self):
        """`artifacts` is a directory name; a *file* called that is a file like any other."""
        write(os.path.join(self.out, "artifacts.props"), "<Project />")
        self.assertIn("artifacts.props (changed)",
                      self.commit_with(lambda out: write(os.path.join(out, "artifacts.props"), "<Project>x</Project>")))

    def test_the_build_output_at_the_root_is_still_not_an_input(self):
        """No broader than necessary: a TRX file or an assembly landing in --out refuses nothing."""
        with transaction.Stage(self.out) as stage:
            write(os.path.join(stage.root, "src", "Engine", "Entries.g.cs"), "// generated")
            stage.testing()
            write(os.path.join(self.out, "TestResults", "engine.trx"), "<TestRun result='later' />")
            write(os.path.join(self.out, "artifacts", "bin", "Engine.dll"), "built again")
            write(os.path.join(self.out, "bin", "Engine.dll"), "and again")
            added, changed, removed = stage.commit(verified=True)
        self.assertEqual((added, changed, removed), (["src/Engine/Entries.g.cs"], [], []))
        self.assertEqual(self.read("TestResults/engine.trx"), "<TestRun result='later' />")


class TestASymlinkedInputIsRefusedByAVerifiedCommit(Scratch):
    """#370: a source in --out that is a symlink is refused, because the check and the write are not one instant.

    `drift()` reads through a link (`os.stat` and `open` both follow one), so a source replaced by a
    link to identical bytes compared equal -- and the bytes the commit then left in place were
    whatever the link pointed at when someone next read it, which is not what the gate built and
    tested and need not even be inside --out. #232's symlink guard covers `tools/factory`, and
    #184's covers only the paths the commit itself writes; an engine's own sources in --out had
    neither.

    Each assertion names the link refusal's own words and the path it names, never `Refused` alone
    (#283): the drift refusal, the mutation-set refusal and #184's write-through refusal are all
    refusals of this same call.
    """

    def setUp(self):
        super().setUp()
        write(os.path.join(self.out, "src", "Engine", "Rule.cs"), "class Rule { }")
        self.elsewhere = os.path.join(self.tmp, "elsewhere.cs")
        write(self.elsewhere, "class Rule { }")  # the same bytes, so drift() alone sees nothing

    def relink(self, relative, target):
        path = os.path.join(self.out, *relative.split("/"))
        os.remove(path)
        os.symlink(target, path)

    def assertRefusedLinked(self, plant, *expected):
        # What the run writes is at the root and passes through no link, so #184's write-through
        # refusal cannot fire and the link refusal is the only one that can (#283).
        with transaction.Stage(self.out) as stage:
            write(os.path.join(stage.root, "provenance.json"), "{}")
            stage.testing()
            plant()
            with self.assertRaises(intake.Refused) as caught:
                stage.commit(verified=True)
        message = str(caught.exception)
        self.assertIn("--out has a symlink where the verified engine has a source or build input", message)
        for fragment in expected:
            self.assertIn(fragment, message)
        self.assertFalse(os.path.lexists(os.path.join(self.out, transaction.JOURNAL)))
        self.assertNoStaging()
        return message

    def test_a_source_replaced_by_a_link_to_identical_bytes_is_refused(self):
        self.assertRefusedLinked(lambda: self.relink("src/Engine/Rule.cs", self.elsewhere),
                                 "src/Engine/Rule.cs")
        # Nothing was written, so the link is still the engine's to deal with.
        self.assertTrue(os.path.islink(os.path.join(self.out, "src", "Engine", "Rule.cs")))

    def test_the_bytes_behind_the_link_can_change_after_the_check_which_is_why_the_link_is_refused(self):
        """Check and use are not the same instant: comparing bytes through a link proves nothing.

        `drift()` is wrapped so the link's target changes the moment it has compared equal -- the
        race, made deterministic. The link is refused before the comparison is reached, so the
        wrapped comparison never runs and the substituted bytes are never committed.
        """
        self.relink("src/Engine/Rule.cs", self.elsewhere)
        compared = []
        real = transaction.Stage.drift

        def drift_then_repoint(stage):
            result = real(stage)
            compared.append(result)
            write(self.elsewhere, "class Rule { int attacker; }")
            return result
        with mock.patch.object(transaction.Stage, "drift", drift_then_repoint):
            self.assertRefusedLinked(lambda: None, "src/Engine/Rule.cs")
        self.assertEqual(compared, [], "the link is refused before its bytes are ever compared")
        self.assertEqual(self.read("src/Engine/Rule.cs"), "class Rule { }")

    def test_a_directory_on_an_input_path_that_is_a_link_is_refused(self):
        def plant():
            source = os.path.join(self.out, "src", "Engine")
            moved = os.path.join(self.tmp, "Engine")
            os.rename(source, moved)
            os.symlink(moved, source)
        self.assertRefusedLinked(plant, "src/Engine")

    def test_a_link_inside_the_build_output_is_not_an_input_and_commits(self):
        """No broader than necessary: nothing under the root TestResults/ is an input of the proof."""
        os.makedirs(os.path.join(self.out, "TestResults"))
        os.symlink(self.elsewhere, os.path.join(self.out, "TestResults", "linked.trx"))
        with transaction.Stage(self.out) as stage:
            write(os.path.join(stage.root, "provenance.json"), "{}")
            stage.testing()
            added, changed, removed = stage.commit(verified=True)
        self.assertEqual((added, changed, removed), (["provenance.json"], [], []))

    def test_an_unverified_commit_leaves_a_link_it_does_not_write_through_alone(self):
        """--no-verify claims nothing about a build, so it is held only to the paths it writes (#184)."""
        self.relink("src/Engine/Rule.cs", self.elsewhere)
        with transaction.Stage(self.out) as stage:
            write(os.path.join(stage.root, "provenance.json"), "{}")
            added, changed, removed = stage.commit(verified=False)
        self.assertEqual((added, changed, removed), (["provenance.json"], [], []))
        self.assertTrue(os.path.islink(os.path.join(self.out, "src", "Engine", "Rule.cs")))


class TestSymlinkInOut(Scratch):
    """#184: a commit never writes or removes through a symlink in --out."""

    def setUp(self):
        super().setUp()
        self.external = os.path.join(self.tmp, "external")
        write(os.path.join(self.external, "old.md"), "external old")

    def commit(self, change):
        before = listing(self.tmp)
        with transaction.Stage(self.out) as stage:
            change(stage.root)
            with self.assertRaises(intake.Refused) as caught:
                stage.commit()
        self.assertIn("symlink", str(caught.exception))
        self.assertIn("nothing was written", str(caught.exception))
        self.assertEqual(before, listing(self.tmp))
        self.assertEqual([n for n in os.listdir(self.tmp) if ".factory-produce-" in n], [])
        return str(caught.exception)

    def test_writing_and_removing_beneath_a_symlinked_directory_is_refused(self):
        os.symlink(self.external, os.path.join(self.out, "linked"))

        def change(root):
            write(os.path.join(root, "linked", "new.md"), "written by produce")
            os.remove(os.path.join(root, "linked", "old.md"))
        message = self.commit(change)
        self.assertIn("linked/new.md (through linked)", message)
        self.assertIn("linked/old.md (through linked)", message)
        self.assertEqual(sorted(os.listdir(self.external)), ["old.md"])

    def test_replacing_a_symlinked_file_is_refused(self):
        os.symlink(os.path.join(self.external, "old.md"), os.path.join(self.out, "backlog", "002.md"))
        self.commit(lambda root: write(os.path.join(root, "backlog", "002.md"), "replaced"))
        self.assertEqual(listing(self.external), {"old.md": "external old"})

    def test_a_symlink_the_commit_does_not_touch_is_left_alone(self):
        os.symlink(self.external, os.path.join(self.out, "linked"))
        with transaction.Stage(self.out) as stage:
            write(os.path.join(stage.root, "backlog", "002.md"), "two")
            added, changed, removed = stage.commit()
        self.assertEqual((added, changed, removed), (["backlog/002.md"], [], []))
        self.assertTrue(os.path.islink(os.path.join(self.out, "linked")))
        self.assertEqual(listing(self.external), {"old.md": "external old"})


if __name__ == "__main__":
    unittest.main()
