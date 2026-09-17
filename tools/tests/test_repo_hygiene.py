#!/usr/bin/env python3
"""repo-hygiene.py, proved able to fail -- and proved unable to remove work that is not finished.

Every case builds a real origin and clone in a temporary directory, and puts a fake `gh` first on
PATH that answers from JSON the case writes. Nothing reads the network.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(ROOT, "tools", "repo-hygiene.py")

_spec = importlib.util.spec_from_file_location("repo_hygiene", TOOL)
hygiene = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hygiene)

FAKE_GH = """#!{python}
import json, os, sys
state = json.load(open(os.environ["FAKE_GH_STATE"]))
if state.get("fail"):
    sys.stderr.write("gh: not logged in\\n"); sys.exit(1)
key = " ".join(sys.argv[1:3])
print(json.dumps(state.get(key, [])))
"""

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class Hygiene(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = os.path.realpath(self._tmp.name)
        self.origin = os.path.join(self.tmp, "origin.git")
        self.clone = os.path.join(self.tmp, "clone")
        self.state = {"pr list": [], "issue list": []}
        bin_dir = os.path.join(self.tmp, "bin")
        os.mkdir(bin_dir)
        gh = os.path.join(bin_dir, "gh")
        with open(gh, "w", encoding="utf-8") as handle:
            handle.write(FAKE_GH.format(python=sys.executable))
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IEXEC)
        self.env = mock.patch.dict(os.environ, dict(
            ENV, PATH=bin_dir + os.pathsep + os.environ["PATH"],
            FAKE_GH_STATE=os.path.join(self.tmp, "gh.json")))
        self.env.start()

        self.git(self.tmp, "init", "-q", "--bare", "-b", "main", self.origin)
        self.git(self.tmp, "clone", "-q", self.origin, self.clone)
        self.commit(self.clone, "README.md", "base")
        self.git(self.clone, "push", "-q", "origin", "main")

    def tearDown(self):
        self.env.stop()
        self._tmp.cleanup()

    # -- helpers ------------------------------------------------------------------------------

    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                              text=True).stdout.strip()

    def commit(self, cwd, path, text):
        full = os.path.join(cwd, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
        self.git(cwd, "add", "-A")
        self.git(cwd, "commit", "-q", "-m", text)
        return self.git(cwd, "rev-parse", "HEAD")

    def merge_on_origin(self, branch):
        """Merge a branch into origin's main the way a pull request would, from a scratch clone."""
        scratch = os.path.join(self.tmp, f"merge-{branch}")
        self.git(self.tmp, "clone", "-q", self.origin, scratch)
        self.git(scratch, "merge", "-q", "--no-ff", "-m", f"merge {branch}", f"origin/{branch}")
        self.git(scratch, "push", "-q", "origin", "main")

    def merged_pr(self, branch, sha):
        self.state["pr list"].append({"headRefName": branch, "headRefOid": sha})

    def run_tool(self, *args, cwd=None):
        with open(os.environ["FAKE_GH_STATE"], "w", encoding="utf-8") as handle:
            json.dump(self.state, handle)
        out = io.StringIO()
        previous = os.getcwd()
        os.chdir(cwd or self.clone)
        try:
            with redirect_stdout(out), redirect_stderr(out):
                code = hygiene.main(list(args))
        finally:
            os.chdir(previous)
        return code, out.getvalue()

    def branches(self):
        return self.git(self.clone, "branch", "--format=%(refname:short)").split()

    def worktree_paths(self):
        out = self.git(self.clone, "worktree", "list", "--porcelain")
        return [l.split(" ", 1)[1] for l in out.splitlines() if l.startswith("worktree ")][1:]

    def pushed_branch(self, name):
        """A branch with one commit, pushed, merged on origin, with its merged pull request."""
        self.git(self.clone, "switch", "-q", "-c", name)
        sha = self.commit(self.clone, f"{name}.txt", name)
        self.git(self.clone, "push", "-q", "origin", name)
        self.git(self.clone, "switch", "-q", "main")
        self.merge_on_origin(name)
        self.merged_pr(name, sha)
        return sha

    def finished_worktree(self, name):
        """A worktree on a branch whose pull request merged at its tip, like an isolated agent's."""
        self.pushed_branch(name)
        self.git(self.clone, "branch", "-D", name)
        tree = os.path.join(self.tmp, f"wt-{name}")
        self.git(self.clone, "worktree", "add", "-q", tree, name)
        return tree

    # -- cases --------------------------------------------------------------------------------

    def test_a_clean_repository_is_clean(self):
        code, output = self.run_tool()
        self.assertEqual(code, 0, output)
        self.assertIn("repo-hygiene: CLEAN", output)

    def test_a_merged_branch_is_a_leftover_and_fix_deletes_it(self):
        self.pushed_branch("done-work")
        code, output = self.run_tool()
        self.assertEqual(code, 1, output)
        self.assertIn("branch    done-work", output)
        self.assertIn("done-work", self.branches())
        code, output = self.run_tool("--fix")
        self.assertNotIn("done-work", self.branches())
        self.assertIn("fixed     branch    done-work", output)

    def test_an_unmerged_branch_is_kept_and_named(self):
        self.git(self.clone, "switch", "-q", "-c", "abandoned")
        self.commit(self.clone, "x.txt", "not in main")
        self.git(self.clone, "switch", "-q", "main")
        code, output = self.run_tool("--fix")
        self.assertEqual(code, 0, output)
        self.assertIn("abandoned", self.branches())
        self.assertIn("kept because their commits are not in main: abandoned", output)

    def test_the_primary_checkout_behind_origin_is_fast_forwarded(self):
        self.pushed_branch("ahead")
        code, output = self.run_tool("--fix")
        self.assertIn("fast-forwarded main by 2 commit(s)", output)
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD"),
                         self.git(self.clone, "rev-parse", "origin/main"))

    def test_a_dirty_primary_checkout_is_not_fast_forwarded(self):
        self.pushed_branch("ahead")
        with open(os.path.join(self.clone, "README.md"), "a", encoding="utf-8") as handle:
            handle.write("uncommitted\n")
        code, output = self.run_tool("--fix")
        self.assertEqual(code, 1, output)
        self.assertIn("LEFTOVER  behind", output)

    def test_a_locked_worktree_whose_pull_request_merged_is_removed(self):
        tree = self.finished_worktree("agent-work")
        self.git(self.clone, "worktree", "lock", tree)
        code, output = self.run_tool("--fix", "--remote")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.worktree_paths(), [])
        self.assertNotIn("agent-work", self.branches())

    def test_a_fresh_worktree_with_no_commits_is_not_finished_though_it_is_in_main(self):
        # The case the merged-pull-request proof exists for: an agent that has not committed yet.
        tree = os.path.join(self.tmp, "wt-fresh")
        self.git(self.clone, "worktree", "add", "-q", "-b", "just-started", tree)
        code, output = self.run_tool("--fix")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.worktree_paths(), [tree])
        self.assertIn("just-started", self.branches())

    def test_a_worktree_merged_at_an_older_tip_is_not_finished(self):
        tree = self.finished_worktree("more-to-come")
        self.commit(tree, "later.txt", "a commit after the merge")
        self.run_tool("--fix")
        self.assertEqual(self.worktree_paths(), [tree])

    def test_a_finished_worktree_with_untracked_files_is_reported_not_removed(self):
        tree = self.finished_worktree("messy")
        with open(os.path.join(tree, "notes.txt"), "w", encoding="utf-8") as handle:
            handle.write("not committed\n")
        code, output = self.run_tool("--fix")
        self.assertEqual(code, 1, output)
        self.assertIn("uncommitted or untracked files", output)
        self.assertEqual(self.worktree_paths(), [tree])

    def test_the_worktree_the_command_runs_in_is_left_alone(self):
        tree = self.finished_worktree("here")
        code, output = self.run_tool("--fix", cwd=tree)
        self.assertEqual(code, 1, output)
        self.assertIn("this command is running inside it", output)
        self.assertEqual(self.worktree_paths(), [tree])

    def test_a_detached_review_worktree_is_removed_only_when_a_day_old(self):
        tree = os.path.join(self.tmp, "review-tree")
        self.git(self.clone, "worktree", "add", "-q", "--detach", tree, "origin/main")
        self.run_tool("--fix")
        self.assertEqual(self.worktree_paths(), [tree], "a review started today may still be running")
        admin = os.path.join(self.clone, ".git", "worktrees", "review-tree")
        old = time.time() - 2 * 24 * 60 * 60
        os.utime(admin, (old, old))
        code, output = self.run_tool("--fix")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.worktree_paths(), [])

    def test_a_worktree_whose_directory_is_gone_is_pruned(self):
        tree = os.path.join(self.tmp, "wt-gone")
        self.git(self.clone, "worktree", "add", "-q", "-b", "gone", tree)
        shutil.rmtree(tree)
        code, output = self.run_tool()
        self.assertEqual(code, 1, output)
        self.assertIn("LEFTOVER  prunable", output)
        self.run_tool("--fix")
        self.assertEqual(self.worktree_paths(), [])

    def test_a_merged_remote_branch_is_deleted_only_with_remote(self):
        self.pushed_branch("on-github")
        code, output = self.run_tool("--fix")
        self.assertEqual(code, 1, output)
        self.assertIn("remote    origin/on-github", output)
        self.assertIn("on-github", self.git(self.origin, "branch", "--format=%(refname:short)"))
        code, output = self.run_tool("--fix", "--remote")
        self.assertEqual(code, 0, output)
        self.assertNotIn("on-github", self.git(self.origin, "branch", "--format=%(refname:short)"))

    def test_a_remote_branch_pushed_to_after_its_merge_is_kept(self):
        self.pushed_branch("reused")
        self.git(self.clone, "switch", "-q", "reused")
        self.commit(self.clone, "again.txt", "new work on an old branch")
        self.git(self.clone, "push", "-q", "origin", "reused")
        self.git(self.clone, "switch", "-q", "main")
        self.run_tool("--fix", "--remote")
        self.assertIn("reused", self.git(self.origin, "branch", "--format=%(refname:short)"))

    def test_caches_are_leftovers_and_fix_removes_them(self):
        os.makedirs(os.path.join(self.clone, "tools", "__pycache__"))
        os.makedirs(os.path.join(self.clone, ".pytest_cache"))
        code, output = self.run_tool()
        self.assertEqual(code, 1, output)
        self.run_tool("--fix")
        self.assertFalse(os.path.exists(os.path.join(self.clone, "tools", "__pycache__")))
        self.assertFalse(os.path.exists(os.path.join(self.clone, ".pytest_cache")))

    def test_a_declared_map_version_with_no_tag_is_a_leftover_until_tagged(self):
        self.commit(self.clone, "examples/some-map/map-package.json", '{"version": "2.0.0"}')
        self.git(self.clone, "push", "-q", "origin", "main")
        code, output = self.run_tool("--fix")
        self.assertEqual(code, 1, output)
        self.assertIn("examples/some-map declares 2.0.0, and map/some-map/v2.0.0 is not tagged", output)
        self.git(self.clone, "tag", "map/some-map/v2.0.0")
        self.assertEqual(self.run_tool("--fix")[0], 0)

    def release_setup(self, product_change):
        self.git(self.clone, "tag", "-a", "factory/v0.1.0", "-m", "v0.1.0")
        self.git(self.clone, "push", "-q", "origin", "factory/v0.1.0")
        time.sleep(1.1)  # the tag's date and the closing date are compared to the second
        path = "tools/factory/intake.py" if product_change else "examples/trial/REPORT.md"
        self.commit(self.clone, path, "after the tag")
        self.git(self.clone, "push", "-q", "origin", "main")
        closed = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 60))
        self.state["issue list"] = [
            {"number": 7, "closedAt": closed, "labels": [{"name": "review3-p0"}]},
            {"number": 8, "closedAt": closed, "labels": [{"name": "schema"}]}]

    def test_a_p0_fixed_in_the_factory_after_the_last_tag_makes_a_release_due(self):
        self.release_setup(product_change=True)
        code, output = self.run_tool("--fix")
        self.assertEqual(code, 1, output)
        self.assertIn("release   #7 closed after factory/v0.1.0, with 1 factory commit(s) untagged", output)
        self.assertNotIn("#8", output)

    def test_no_release_is_due_when_the_factory_has_not_changed(self):
        self.release_setup(product_change=False)
        code, output = self.run_tool()
        self.assertEqual(code, 0, output)
        self.assertIn("none in the factory", output)

    def test_offline_is_not_verified_rather_than_clean(self):
        code, output = self.run_tool("--offline")
        self.assertEqual(code, 3, output)
        self.assertIn("NOT VERIFIED", output)

    def test_gh_unavailable_is_not_verified_rather_than_clean(self):
        self.state["fail"] = True
        code, output = self.run_tool()
        self.assertEqual(code, 3, output)
        self.assertIn("NOT CHECKED merged pull requests (gh pr list: gh: not logged in)", output)


if __name__ == "__main__":
    unittest.main()
