#!/usr/bin/env python3
"""Where the work on this engine stands, read from the repository. Small enough to restart from.

    tools/orchestrator-status.py [--json] [--local] [--limit N]

Emitted by rules-factory as a managed file (decision 0029). `AGENTS.md` is the contract, and
`docs/agent-team.md` says which role reads this.

**Why.** The orchestrator's job is the *current scheduling decision*. Everything it needs to make
one is durable and none of it is in a conversation: the issues are the backlog, the branches and
worktrees are the work in flight, the pull requests carry their own heads, the commit statuses
carry the verdicts, and the checks say what is green. A conversation is the one part of the
arrangement that is lost on a usage limit, a process restart, a new session, a context that
filled, or a deliberate rotation -- and re-reading it is what an orchestrator does when nothing
tells it what else to do.

In the measured session of 2026-09-23/24, carrying and re-reading orchestration history cost
51.1M effective tokens -- over 18% of the whole session -- against 4.3M for every scheduling
decision that orchestrator actually wrote. This is the command that makes the second number the
whole cost. Read `AGENTS.md`, run this, continue.

**What it is not.** Not a second backlog, and not a state database: it stores nothing and writes
nothing, so there is no copy of the truth here to go stale. GitHub and git remain authoritative,
and every line below is something one of them said a moment ago.

**Bounded on purpose.** No issue body, no pull request body, no diff, no log, no history. Those
are one `gh issue view` away when a decision turns on them, and the whole point of this output is
that it can be read in full, every time, for the price of reading it once.

**Read-only, and it says what it could not read.** It runs no command that writes -- not even a
fetch, which moves refs, and not an ordinary `git status`, which refreshes and rewrites the index
by default and takes its lock to do it (`--no-optional-locks`, #479) -- and a GitHub it could not
reach is `NOT CHECKED`, never a clean repository. It exits 0 when everything was readable, 1 when the repository is not in the steady
state or something needs a decision, and 3 when a part of the answer is missing.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`) and `git`.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

# An import of the vendored factory would otherwise leave scripts/factory/__pycache__ behind, and
# a checkout that ran a read-only report would go dirty (#194).
sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
NOT_CHECKED = "NOT CHECKED"
# How many of each list is printed before it is summarised. A backlog longer than this is a
# backlog, not a scheduling decision: the next ready issue is at the top either way.
DEFAULT_LIMIT = 15
# The width a title is cut to. A title is an identifier here, not a description.
TITLE = 72


class Unreadable(Exception):
    """A read that could not be made. It is reported, never treated as an answer."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    try:
        done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              cwd=ROOT, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise Unreadable(f"cannot run {command[0]} ({error})")
    if done.returncode != 0:
        raise Unreadable(done.stderr.strip() or done.stdout.strip() or f"{' '.join(command)} failed")
    try:
        return json.loads(done.stdout or "null")
    except ValueError as error:
        raise Unreadable(f"{' '.join(command[:3])} did not answer with JSON ({error})")


#: What makes `git status` read-only. Git's own documentation, under BACKGROUND REFRESH: "By
#: default, `git status` will automatically refresh the index, updating the cached stat information
#: from the working tree and writing out the result." That write takes `.git/index`'s lock, in a
#: checkout another agent may be committing in, from a command whose whole claim is that it changes
#: nothing. `--no-optional-locks` is how git is told not to (#479).
READ_ONLY = ("--no-optional-locks",)


def git(*args):
    done = subprocess.run(["git", *READ_ONLY, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, cwd=ROOT)
    return done.stdout.strip() if done.returncode == 0 else None


def policy():
    try:
        with open(ROOT / POLICY, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def required_checks():
    """The checks the factory's ruleset requires, from the copy `produce` vendored, or `None`.

    Read rather than restated, for the reason `tools/agent-doctor.py` reads it: two lists of
    required checks disagree eventually, and the disagreement is invisible until a merge. An
    engine produced before the factory vendored that list answers `None`, and the report then says
    the required set was not checked rather than inventing one.
    """
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    for module in ("agentrails", "generate"):
        try:
            names = getattr(__import__(module), "REQUIRED_CHECKS", None)
        except ImportError:
            continue
        if names:
            return tuple(names)
    return None


def short(text, width=TITLE):
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: width - 1] + "…"


def issue_of(branch):
    """The issue number a branch name carries, or None. `tools/dispatch-agent.sh` names them
    `issue-<n>-<slug>`, and a branch that does not is a branch nobody dispatched."""
    if not branch.startswith("issue-"):
        return None
    rest = branch[len("issue-"):].split("-", 1)[0]
    return int(rest) if rest.isdigit() else None


def worktrees():
    """Every registered worktree but the primary one: path, branch, dirty, and commits ahead.

    Sorted by path, so two runs against one repository print the same bytes.
    """
    listing = git("worktree", "list", "--porcelain") or ""
    found, path, branch = [], None, None
    for line in listing.splitlines() + [""]:
        if line.startswith("worktree "):
            if path is not None:
                found.append((path, branch))
            path, branch = line[len("worktree "):], None
        elif line.startswith("branch "):
            branch = line[len("branch "):].replace("refs/heads/", "", 1)
        elif line == "" and path is not None:
            found.append((path, branch))
            path, branch = None, None
    out = []
    for path, branch in found:
        if pathlib.Path(path).resolve() == ROOT:
            continue
        dirty = subprocess.run(["git", *READ_ONLY, "status", "--porcelain"], cwd=path,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        ahead = subprocess.run(["git", *READ_ONLY, "rev-list", "--count", "main.." + (branch or "HEAD")],
                               cwd=path, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        out.append({
            "path": path,
            "branch": branch,
            "issue": issue_of(branch or ""),
            "dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
            "commits": int(ahead.stdout.strip() or 0) if ahead.returncode == 0 and ahead.stdout.strip() else None,
        })
    return sorted(out, key=lambda row: row["path"])


def rollup(pull):
    """One pull request's checks and recorded statuses, as `{name: state}`, lower-cased states.

    GitHub returns two shapes in one list -- a check run has a `name` and a `conclusion`, a commit
    status has a `context` and a `state` -- and a verdict is the second kind, which is why both
    are read here rather than only the first.
    """
    out = {}
    for item in pull.get("statusCheckRollup") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("context")
        if not name:
            continue
        state = item.get("conclusion") or item.get("state") or item.get("status") or "?"
        out[name] = str(state).lower()
    return out


def pull_requests(limit):
    pulls = gh("pr", "list", "--state", "open", "--limit", str(max(limit, 1) * 4), "--json",
               "number,title,isDraft,headRefOid,headRefName,closingIssuesReferences,statusCheckRollup")
    out = []
    for pull in pulls or []:
        closes = [issue.get("number") for issue in pull.get("closingIssuesReferences") or []]
        out.append({
            "number": pull.get("number"),
            "title": pull.get("title") or "",
            "draft": bool(pull.get("isDraft")),
            "head": pull.get("headRefOid") or "",
            "branch": pull.get("headRefName") or "",
            "closes": closes,
            "checks": rollup(pull),
        })
    return sorted(out, key=lambda row: row["number"] or 0)


def issues(labels, limit):
    """Open issues grouped by the state label the policy names, plus the ones carrying none.

    The vocabulary is the engine's: a repository that renamed `state:ready` is read correctly
    here, because the names come from `.github/agent-policy.json` and not from this file.
    """
    rows = gh("issue", "list", "--state", "open", "--limit", str(max(limit, 1) * 8),
              "--json", "number,title,labels")
    groups = {key: [] for key in ("ready", "blocked", "needsDecision")}
    groups["unlabelled"] = []
    for issue in rows or []:
        names = {label.get("name") for label in issue.get("labels") or []}
        item = {"number": issue.get("number"), "title": issue.get("title") or ""}
        for key in ("needsDecision", "blocked", "ready"):
            if labels.get(key) in names:
                groups[key].append(item)
                break
        else:
            groups["unlabelled"].append(item)
    return {key: sorted(items, key=lambda row: row["number"] or 0) for key, items in groups.items()}


def collect(limit, local):
    """Everything the report is made of, and every read it could not make."""
    settings = policy()
    labels = settings.get("labels") or {}
    review = settings.get("review") or {}
    contexts = [review.get("semanticContext")] + [link.get("context")
                                                  for link in review.get("independentFallback") or []]
    state = {
        "repository": None,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": git("rev-parse", "HEAD"),
        "clean": (git("status", "--porcelain") == ""),
        "remoteHead": None,
        "worktrees": worktrees(),
        # None until read. An unread list that printed as "0 open" would be the exact substitution
        # of a claim for a fact every other rail refuses (`--sweep`, the doctor).
        "pullRequests": None,
        "issues": None,
        "reviewContexts": [context for context in contexts if context],
        "requiredChecks": required_checks(),
        "notChecked": [],
    }
    if not settings:
        state["notChecked"].append(f"{POLICY} could not be read, so the label vocabulary and the review "
                                   f"contexts below are this engine's defaults and may not be its own")
    if local:
        state["notChecked"].append("--local: the pull requests, the issues and the default branch's head "
                                   "were not read, so this says nothing about what is open")
        return state
    try:
        state["repository"] = (gh("repo", "view", "--json", "nameWithOwner,defaultBranchRef") or {})
    except Unreadable as why:
        state["notChecked"].append(f"which repository this is, and its default branch: {why}")
    default = ((state["repository"] or {}).get("defaultBranchRef") or {}).get("name") or "main"
    if state["repository"]:
        try:
            state["remoteHead"] = (gh("api", f"repos/{{owner}}/{{repo}}/commits/{default}",
                                      "--jq", "{sha: .sha}") or {}).get("sha")
        except Unreadable as why:
            state["notChecked"].append(f"the head of `{default}` on GitHub, so whether this checkout is "
                                       f"current is unknown: {why}")
    try:
        state["pullRequests"] = pull_requests(limit)
    except Unreadable as why:
        state["notChecked"].append(f"the open pull requests: {why}")
    try:
        state["issues"] = issues(labels, limit)
    except Unreadable as why:
        state["notChecked"].append(f"the open issues, which are the backlog: {why}")
    return state


def listing(items, limit, render):
    """At most `limit` rendered rows, and a line saying how many were not printed."""
    shown = [render(item) for item in items[:limit]]
    if len(items) > limit:
        shown.append(f"  … and {len(items) - limit} more")
    return shown


def report(state, limit, labels):
    lines = []
    name = (state["repository"] or {}).get("nameWithOwner") or "(unknown repository)"
    checkout = f"{name}  {state['branch']} {(state['head'] or '')[:12]}"
    if state["remoteHead"] is None:
        currency = "current: NOT CHECKED"
    elif state["remoteHead"] == state["head"]:
        currency = "level with the default branch"
    else:
        # Which way round is a question only a fetch could answer, and a fetch writes refs.
        currency = f"NOT level with the default branch, which is at {state['remoteHead'][:12]}"
    lines.append(f"checkout      {checkout}  [{'clean' if state['clean'] else 'DIRTY'}; {currency}]")

    trees = state["worktrees"]
    lines.append(f"worktrees     {len(trees)}")
    for tree in trees:
        issue = f"#{tree['issue']}" if tree["issue"] else "no issue in its name"
        dirty = "DIRTY" if tree["dirty"] else "clean" if tree["dirty"] is False else NOT_CHECKED
        commits = "?" if tree["commits"] is None else tree["commits"]
        lines.append(f"  {tree['branch'] or '(detached)'}")
        lines.append(f"      {issue}  {dirty}  {commits} commit(s) not on main  {tree['path']}")

    pulls = state["pullRequests"]
    if pulls is None:
        lines.append(f"pull requests {NOT_CHECKED}")
        pulls = []
    else:
        lines.append(f"pull requests {len(pulls)} open")
    for pull in pulls[:limit]:
        closes = ", ".join(f"#{number}" for number in pull["closes"]) or "CLOSES NO ISSUE"
        lines.append(f"  #{pull['number']}  {'draft' if pull['draft'] else 'ready'}  "
                     f"{pull['head'][:12]}  closes {closes}  {short(pull['title'])}")
        checks = pull["checks"]
        required = state["requiredChecks"]
        if required is None:
            lines.append(f"      required checks: {NOT_CHECKED} (scripts/factory/agentrails.py could not be read)")
        else:
            lines.append("      " + "  ".join(
                f"{check}={checks.get(check, 'not reported')}" for check in sorted(required)))
        verdicts = [f"{context}={checks[context]}" for context in sorted(state["reviewContexts"])
                    if context in checks]
        lines.append("      verdicts: " + ("  ".join(verdicts) if verdicts else "none recorded at this head"))
    if len(pulls) > limit:
        lines.append(f"  … and {len(pulls) - limit} more")

    grouped = state["issues"]
    if grouped is not None:
        counts = "  ".join(f"{key}={len(grouped.get(key) or [])}"
                           for key in ("ready", "blocked", "needsDecision", "unlabelled"))
        lines.append(f"issues        {counts}")
        for key, heading in (("needsDecision", labels.get("needsDecision", "needs-decision")),
                             ("ready", labels.get("ready", "ready")),
                             ("blocked", labels.get("blocked", "blocked")),
                             ("unlabelled", "no state label — not dispatchable until one is set")):
            items = grouped.get(key) or []
            if not items:
                continue
            lines.append(f"  {heading}")
            lines += listing(items, limit, lambda item: f"      #{item['number']}  {short(item['title'])}")
    else:
        lines.append(f"issues        {NOT_CHECKED}")

    if state["notChecked"]:
        lines.append("")
        for why in state["notChecked"]:
            lines.append(f"  {NOT_CHECKED}  {why}")
        lines.append("  A report that could not read part of the repository is a partial report, and this "
                     "is which part.")
    return "\n".join(lines)


def verdict(state):
    """0 when this is the steady state and everything was readable, 1 when something wants a
    person, 3 when part of the answer is missing. The three are distinguished because "I could
    not look" and "there is nothing to do" leave the same repository behind."""
    if state["notChecked"]:
        return 3
    wants_attention = (not state["clean"]
                       or any(tree["dirty"] for tree in state["worktrees"])
                       or any(not pull["closes"] for pull in state["pullRequests"])
                       or ((state["issues"] or {}).get("needsDecision") or [])
                       or ((state["issues"] or {}).get("unlabelled") or []))
    return 1 if wants_attention else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="orchestrator-status.py", description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="the same state, machine-readable, for a caller that acts on it")
    parser.add_argument("--local", action="store_true",
                        help="this checkout only, and say GitHub was not read")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"how many of each list to print before summarising (default {DEFAULT_LIMIT})")
    args = parser.parse_args(argv)
    if args.limit < 1:
        print("orchestrator-status: --limit must be at least 1", file=sys.stderr)
        return 2

    state = collect(args.limit, args.local)
    if args.as_json:
        print(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(report(state, args.limit, (policy().get("labels") or {})))
    return verdict(state)


if __name__ == "__main__":
    sys.exit(main())
