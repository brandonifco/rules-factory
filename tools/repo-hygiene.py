#!/usr/bin/env python3
"""Nothing a finished piece of work leaves behind outlives it.

On 2026-09-17 this repository had 84 local branches (79 merged), 59 merged branches on GitHub, 9
worktrees from agents and a review that had all finished, a primary checkout 41 commits behind, and
54 commits on `main` since the last tag, two of them P0 fixes. None of it was wrong on the day it
was made. Each operation that made it simply stopped before cleaning up, and nothing noticed.

This reports every such leftover, and with `--fix` removes the ones that are provably finished:

  * behind     the primary checkout is on `main`, clean, and behind `origin/main`: fast-forwarded
  * branch     a local branch no worktree has checked out, whose tip is already in `origin/main`:
               deleted. Its commits are in `main`, so nothing is lost, even for a branch that
               never had a commit of its own
  * worktree   a clean worktree on a branch whose pull request merged at exactly that tip, or a
               clean detached worktree at a commit in `origin/main`, unlocked and more than a day
               old: removed. A fresh worktree on a new branch is also "in main", so a branch
               worktree needs the merged pull request as proof -- an agent that has not yet
               committed is not finished
  * prunable   a registered worktree whose directory is gone: pruned
  * cache      `__pycache__` and `.pytest_cache` in the primary checkout: removed
  * remote     a branch on GitHub whose pull request merged at exactly that tip: deleted only with
               `--remote`, because it is a write to GitHub
  * map        a map under `examples/` whose `map-package.json` declares a version with no
               `map/<name>/v<version>` tag: never fixed here, because the tag publishes to nuget.org
  * release    an issue labelled `review*-p0` or `review*-p1` closed after the last `factory/v*`
               tag, while `tools/factory/` has changed since it: never fixed here. A tag is a
               decision; this says it is due until one is made

Nothing is ever forced. A worktree with uncommitted or untracked files, a locked detached one, the
one this command runs in, and a branch with commits outside `main` are reported and left alone.

What cannot be read is not called clean: offline, or with `gh` unavailable, the parts that need
GitHub print NOT CHECKED and the run exits 3 rather than 0.

Usage: repo-hygiene.py [--fix] [--remote] [--offline]
Exit 0 clean; 1 leftovers remain; 3 no leftovers found, but part of the check could not run.
Standard library only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

REPO = "brandonifco/rules-factory"
MAIN = "main"
UPSTREAM = "origin/main"
TAG_PATTERN = "factory/v*"
RELEASE_LABEL = re.compile(r"^review\d*-p[01]$")
DETACHED_MIN_AGE_SECONDS = 24 * 60 * 60
CACHE_NAMES = ("__pycache__", ".pytest_cache")
# The released product: provenance records these files' commit, so a change here is what a tag names.
PRODUCT_PATHS = ("tools/factory", ":(exclude)tools/tests")
GROUPED_REMEDY = {"remote": "repo-hygiene.py --fix --remote", "worktree": "run without --fix to see each"}


class Unavailable(Exception):
    """A source of facts could not be read. The caller says NOT CHECKED, never OK."""


def git(*args, cwd, check=True):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result


def gh_json(*args):
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise Unavailable("gh is not installed")
    if result.returncode != 0:
        raise Unavailable(f"gh {' '.join(args[:2])}: {result.stderr.strip() or 'failed'}")
    return json.loads(result.stdout or "null")


def primary_root(cwd):
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd).stdout.strip()
    return os.path.dirname(common)


def worktrees(root):
    """Every registered worktree after the primary, as dicts of git's porcelain fields."""
    out = git("worktree", "list", "--porcelain", cwd=root).stdout
    found, current = [], {}
    for line in out.splitlines() + [""]:
        if not line:
            if current:
                found.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value if value else True
    return found[1:]


def is_ancestor(root, commit, of=UPSTREAM):
    return git("merge-base", "--is-ancestor", commit, of, cwd=root, check=False).returncode == 0


def is_clean(path):
    status = git("status", "--porcelain", "--untracked-files=all", cwd=path, check=False)
    return status.returncode == 0 and not status.stdout.strip()


def is_within(path, directory):
    path, directory = os.path.realpath(path), os.path.realpath(directory)
    return path == directory or path.startswith(directory + os.sep)


class Report:
    def __init__(self):
        self.leftovers, self.fixed, self.unchecked, self.notes = [], [], [], []

    def leftover(self, kind, what, remedy):
        self.leftovers.append((kind, what, remedy))

    def done(self, kind, what):
        self.fixed.append((kind, what))

    def print(self):
        for kind, what in self.fixed:
            print(f"fixed     {kind:<9} {what}")
        # A long run of one kind is one finding with many instances; listed whole it buries the rest.
        by_kind = {}
        for kind, what, remedy in self.leftovers:
            by_kind.setdefault(kind, []).append((what, remedy))
        for kind, items in by_kind.items():
            if len(items) > 3:
                shown = ", ".join(what.split(" ")[0] for what, _ in items[:3])
                remedy = GROUPED_REMEDY.get(kind, "repo-hygiene.py --fix")
                print(f"LEFTOVER  {kind:<9} {len(items)} of them: {shown}, ...\n          -> {remedy}")
                continue
            for what, remedy in items:
                print(f"LEFTOVER  {kind:<9} {what}\n          -> {remedy}")
        for what in self.unchecked:
            print(f"NOT CHECKED {what}")
        for what in self.notes:
            print(f"note      {what}")
        if self.leftovers:
            print(f"repo-hygiene: {len(self.leftovers)} leftover(s)")
            return 1
        if self.unchecked:
            print("repo-hygiene: NOT VERIFIED -- no leftovers found in what could be read")
            return 3
        print("repo-hygiene: CLEAN")
        return 0


def merged_pulls():
    """{head branch name: set of head commits} for merged pull requests of this repository."""
    rows = gh_json("pr", "list", "--repo", REPO, "--state", "merged", "--limit", "1000",
                   "--json", "headRefName,headRefOid")
    heads = {}
    for row in rows or []:
        heads.setdefault(row["headRefName"], set()).add(row["headRefOid"])
    return heads


def check_primary(root, fix, report):
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root).stdout.strip()
    behind = int(git("rev-list", "--count", f"HEAD..{UPSTREAM}", cwd=root).stdout.strip() or 0)
    if not behind:
        return
    what = f"the primary checkout is {behind} commit(s) behind {UPSTREAM}"
    if branch != MAIN:
        report.notes.append(f"{what}, but it is on {branch}, which is a person's choice")
    elif not is_clean(root):
        report.leftover("behind", what, "commit, stash or discard, then git merge --ff-only origin/main")
    elif fix and git("merge", "--ff-only", "-q", UPSTREAM, cwd=root, check=False).returncode == 0:
        report.done("behind", f"fast-forwarded {MAIN} by {behind} commit(s)")
    else:
        report.leftover("behind", what, "git merge --ff-only origin/main")


def check_worktrees(root, here, pulls, fix, report):
    for tree in worktrees(root):
        path = tree["worktree"]
        if tree.get("prunable"):
            if fix:
                git("worktree", "prune", cwd=root)
                report.done("prunable", path)
            else:
                report.leftover("prunable", path, "git worktree prune")
            continue
        head = tree.get("HEAD", "")
        branch = tree.get("branch", "").removeprefix("refs/heads/")
        if branch:
            if pulls is None:
                continue  # unchecked; said once by the caller
            finished = head in pulls.get(branch, set()) and is_ancestor(root, head)
            why = f"{path} ({branch}, its pull request merged)"
        else:
            admin = os.path.join(root, ".git", "worktrees", os.path.basename(path))
            age = time.time() - os.path.getmtime(admin) if os.path.exists(admin) else 0
            finished = is_ancestor(root, head) and age > DETACHED_MIN_AGE_SECONDS
            why = f"{path} (detached at {head[:7]}, in {UPSTREAM}, {int(age // 3600)}h old)"
        if not finished:
            continue
        blocked = None
        if is_within(here, path):
            blocked = "this command is running inside it; run it from the primary checkout"
        elif not is_clean(path):
            blocked = "it has uncommitted or untracked files; look at them before removing it"
        elif "locked" in tree and not branch:
            blocked = "it is locked, so something said it is still in use: git worktree unlock"
        if blocked:
            report.leftover("worktree", why, blocked)
            continue
        if not fix:
            report.leftover("worktree", why, f"git worktree remove {path}")
            continue
        if "locked" in tree:
            # Claude Code locks an isolated agent's worktree and never unlocks it. For a branch
            # worktree the merged pull request at this exact tip is the proof the lock is stale.
            git("worktree", "unlock", path, cwd=root, check=False)
        removed = git("worktree", "remove", path, cwd=root, check=False)
        if removed.returncode == 0:
            report.done("worktree", why)
        else:
            report.leftover("worktree", why, removed.stderr.strip())


def check_branches(root, fix, report):
    checked_out = {t.get("branch", "").removeprefix("refs/heads/") for t in worktrees(root)}
    checked_out.add(git("rev-parse", "--abbrev-ref", "HEAD", cwd=root).stdout.strip())
    listing = git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads", cwd=root)
    for line in listing.stdout.splitlines():
        name, sha = line.split()
        if name == MAIN or name in checked_out or not is_ancestor(root, sha):
            continue
        if fix:
            # update-ref with the expected old value, not `branch -d`: -d judges "merged" against
            # the local HEAD, which may be behind origin/main, and the ancestry was checked above.
            git("update-ref", "-d", f"refs/heads/{name}", sha, cwd=root)
            report.done("branch", f"{name} (in {UPSTREAM})")
        else:
            report.leftover("branch", f"{name} (in {UPSTREAM})", f"git branch -d {name}")
    unmerged = [n for n in git("branch", "--format=%(refname:short)", "--no-merged", UPSTREAM,
                               cwd=root).stdout.split() if n not in checked_out]
    if unmerged:
        report.notes.append(
            "unmerged local branch(es) with no worktree, kept because their commits are not in "
            f"{MAIN}: {', '.join(unmerged)}. Delete one deliberately with git branch -D")


def check_remote(root, pulls, fix, remote, report):
    listing = git("for-each-ref", "--format=%(refname:lstrip=3) %(objectname)",
                  "refs/remotes/origin", cwd=root)
    for line in listing.stdout.splitlines():
        name, sha = line.split()
        if name in (MAIN, "HEAD") or sha not in pulls.get(name, set()):
            continue
        what = f"origin/{name} (its pull request merged)"
        if fix and remote:
            pushed = git("push", "-q", "origin", "--delete", name, cwd=root, check=False)
            if pushed.returncode == 0:
                report.done("remote", what)
                continue
            report.leftover("remote", what, pushed.stderr.strip())
        else:
            report.leftover("remote", what, f"repo-hygiene.py --fix --remote, or git push origin --delete {name}")


def check_release(root, report):
    tags = git("tag", "--list", TAG_PATTERN, "--sort=-v:refname", cwd=root).stdout.split()
    if not tags:
        report.notes.append(f"no {TAG_PATTERN} tag exists")
        return
    tag = tags[0]
    since = git("log", "-1", "--format=%cI", tag, cwd=root).stdout.strip()
    untagged = int(git("rev-list", "--count", f"{tag}..{UPSTREAM}", cwd=root).stdout.strip() or 0)
    # What is released is the factory. An evidence issue closing with no factory change since the
    # tag has nothing to release, so only commits that touch the product count.
    product = git("rev-list", "--count", f"{tag}..{UPSTREAM}", "--", *PRODUCT_PATHS, cwd=root)
    product = int(product.stdout.strip() or 0)
    if not product:
        if untagged:
            report.notes.append(f"{untagged} commit(s) on {UPSTREAM} since {tag}, none in the factory")
        return
    rows = gh_json("issue", "list", "--repo", REPO, "--state", "closed", "--limit", "200",
                   "--search", f"closed:>{since[:19]}", "--json", "number,labels,closedAt")
    due = sorted(
        row["number"] for row in rows or []
        if row["closedAt"] > since and any(RELEASE_LABEL.match(l["name"]) for l in row["labels"]))
    if due:
        report.leftover(
            "release",
            f"{', '.join(f'#{n}' for n in due)} closed after {tag}, with {product} factory commit(s) untagged",
            "tag the next factory/vX.Y.Z on origin/main once its CI is green (AGENTS.md, releases)")
    else:
        report.notes.append(f"{product} factory commit(s) on {UPSTREAM} since {tag}; no release is due")


def check_map_releases(root, report):
    listing = git("ls-tree", "--name-only", f"{UPSTREAM}:examples", cwd=root, check=False)
    tags = set(git("tag", "--list", "map/*", cwd=root).stdout.split())
    for name in listing.stdout.split():
        shown = git("show", f"{UPSTREAM}:examples/{name}/map-package.json", cwd=root, check=False)
        if shown.returncode != 0:
            continue
        try:
            version = json.loads(shown.stdout)["version"]
        except (ValueError, KeyError, TypeError):
            report.leftover("map", f"examples/{name}/map-package.json has no readable version",
                            "fix the file; tools/pack-map.py says what it needs")
            continue
        if f"map/{name}/v{version}" not in tags:
            report.leftover(
                "map", f"examples/{name} declares {version}, and map/{name}/v{version} is not tagged",
                f"publish it (git tag map/{name}/v{version} on origin/main; publish-map.yml runs on the "
                "tag), or say in the map's README why it is held")


def remove_caches(root, fix, report):
    found = []
    for directory, subdirs, _ in os.walk(root):
        # Another worktree nested in this one (.claude/worktrees/) is its own checkout.
        subdirs[:] = [d for d in subdirs if d != ".git" and not
                      os.path.exists(os.path.join(directory, d, ".git"))]
        for name in CACHE_NAMES:
            if name in subdirs:
                found.append(os.path.join(directory, name))
                subdirs.remove(name)
    for path in found:
        relative = os.path.relpath(path, root)
        if fix:
            shutil.rmtree(path, ignore_errors=True)
            report.done("cache", relative)
        else:
            report.leftover("cache", relative, "repo-hygiene.py --fix")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fix", action="store_true", help="remove what is provably finished")
    parser.add_argument("--remote", action="store_true",
                        help="with --fix, also delete merged branches on GitHub")
    parser.add_argument("--offline", action="store_true",
                        help="read nothing from the network; GitHub-backed parts are NOT CHECKED")
    args = parser.parse_args(argv)

    here = os.getcwd()
    root = primary_root(here)
    report = Report()

    if args.offline:
        report.unchecked.append(f"{UPSTREAM} was not fetched (--offline)")
    elif git("fetch", "-q", "--prune", "origin", cwd=root, check=False).returncode != 0:
        report.unchecked.append(f"git fetch failed; {UPSTREAM} may be stale")

    pulls = None
    if args.offline:
        report.unchecked.append("merged pull requests, so branch worktrees, remote branches and "
                                "the release are not judged")
    else:
        try:
            pulls = merged_pulls()
        except Unavailable as error:
            report.unchecked.append(f"merged pull requests ({error}); branch worktrees and "
                                    "remote branches are not judged")

    check_primary(root, args.fix, report)
    check_worktrees(root, here, pulls, args.fix, report)
    if args.fix:
        git("worktree", "prune", cwd=root)
    check_branches(root, args.fix, report)
    if pulls is not None:
        check_remote(root, pulls, args.fix, args.remote, report)
    if not args.offline:
        try:
            check_release(root, report)
        except Unavailable as error:
            report.unchecked.append(f"whether a release is due ({error})")
    check_map_releases(root, report)
    remove_caches(root, args.fix, report)
    return report.print()


if __name__ == "__main__":
    sys.exit(main())
