#!/usr/bin/env python3
"""transaction.py never writes, deletes or restores outside --out (#183, #184, #228).

Both defects were found by an independent review and reproduced before they were fixed: a journal
committed into an engine made `recover()` delete a file beside the engine, and a symlinked
directory in an engine made a commit write one file and delete another in the directory it
pointed to. These cases drive `Stage` and `recover()` directly, on a scratch tree, so they are
fast and need no package; test_factory_produce.py covers the refusal through `produce`.

Run: python3 -m unittest discover -s tools/tests
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.join(os.path.dirname(HERE), "factory")
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
