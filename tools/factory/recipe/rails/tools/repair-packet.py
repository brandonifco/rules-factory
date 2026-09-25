#!/usr/bin/env python3
"""The bounded brief for one repair attempt on one pull request.

    tools/repair-packet.py <pr number> --finding "..." [--finding "..."]
    tools/repair-packet.py <pr number> --findings <path>        # or `-` for stdin

Emitted by rules-factory as a managed file (decision 0029). `AGENTS.md` is the contract, and
`docs/agent-team.md` says why this exists at all.

**Why.** A review finding does not end the work, and until this file existed nothing said it ended
the *agent*. So the implementer that wrote the code received the finding, repaired, was reviewed
again, repaired again -- one conversation across every round, growing monotonically, with every
later turn paying for the whole of it. In the measured session of 2026-09-23/24 the implementer
that went eight rounds cost about 45M effective tokens on its own, and what it was buying with
most of them was its own transcript.

None of that transcript was authoritative. The issue, the branch, the worktree, the commits, the
pull request and its head, the entry as the map has it, the overlay's mutation records and the
gate are all durable, and between them they say everything a repair needs. **One subagent
instance is one attempt**, and the next attempt is a new one, reading this.

**What this deliberately does not carry**: the previous implementer's transcript, earlier review
conversations, orchestration discussion, or a summary of a superseded head. A repair attempt that
is handed the argument it is repairing is anchored by it, and paying for the anchor.

**What the caller supplies, and why only that.** The findings. Which findings block is the
orchestrator's judgement (`docs/agent-team.md`), and it is the one thing here that is not derived.
Everything else -- the head, the branch, the worktree, the issue's acceptance criteria, the
entries, the verdicts standing at this head, what must be green -- is read from the repository.

**Read-only, and ephemeral.** It writes nothing, anywhere: the brief goes to stdout, so there is
no packet file to clean up and nothing that can go stale beside the state it was derived from.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`) and `git`.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
# The marker `factory backlog --create` puts under an item's title: what ties a pull request back
# to an entry, and the same one `tools/review-packet.py` reads.
ENTRY_MARKER = "<!-- rules-factory-entry:"
# The two sections of an issue a repair attempt is held to. `tools/new-issue.sh` writes both, and
# the rest of the body is the case for the work -- which a repair attempt does not need to be
# persuaded of, because the work is already merged into a branch.
ISSUE_SECTIONS = ("Acceptance criteria", "Required evidence")
DEFAULT_WORKTREE_VARIABLE = "RULES_ENGINE_WORKTREE_ROOT"


class Refused(Exception):
    """Something the brief cannot honestly assemble. Nothing is printed."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    try:
        done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              cwd=ROOT, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise Refused(f"cannot run {command[0]} ({error}); it is how a brief reads the issue and the PR")
    if done.returncode != 0:
        raise Refused(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def gh_maybe(*args):
    """A read that may legitimately be unavailable: `(text, None)` or `(None, why)`.

    Used where an unreachable GitHub must be reported as NOT CHECKED rather than as an answer --
    the rule `tools/dispatch-agent.sh --sweep` and `tools/agent-doctor.py` already hold.
    """
    try:
        return gh(*args), None
    except Refused as error:
        return None, str(error)


def git(*args):
    done = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
    if done.returncode != 0:
        raise Refused(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def git_maybe(*args):
    done = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
    return done.stdout if done.returncode == 0 else None


def policy():
    try:
        with open(ROOT / POLICY, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"{POLICY} cannot be read ({error}); it holds the review contexts and the worktree root")


def entry_ids(*texts):
    """Every entry id named by a marker in `texts`, in first-seen order."""
    found = []
    for text in texts:
        for part in (text or "").split(ENTRY_MARKER)[1:]:
            entry_id = part.split("-->")[0].strip()
            if entry_id and entry_id not in found:
                found.append(entry_id)
    return found


def named_sections(body, wanted):
    """`## <heading>` -> text, for the headings in `wanted` that the body actually has.

    A section the issue does not carry is absent from the result rather than empty: the brief then
    says the issue states none, which is a finding about the issue and not a blank heading.

    **A section ends at the next heading of the same or shallower depth, and nothing sooner**
    (#484). It used to end at the next `##` *or `###`*, so a `### Boundary cases` written under
    `## Acceptance criteria` -- ordinary Markdown, and exactly where a boundary belongs -- silently
    took every criterion under it out of the packet. The whole-body fallback did not rescue them
    either: it fires only when no wanted section was found at all, and one had been.
    """
    out, current, depth = {}, None, 0
    for line in (body or "").splitlines():
        heading = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if heading:
            level, title = len(heading.group(1)), heading.group(2)
            if current is not None and level > depth:
                # Nested under the section being kept: it belongs to it, heading and all.
                out[current].append(line)
                continue
            current = title if title in wanted else None
            depth = level
            if current:
                out[current] = []
            continue
        if current:
            out[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in out.items() if "\n".join(lines).strip()}


def worktree_for(branch):
    """Where `branch` is checked out, and what to do when it is nowhere: `(path, how)`.

    A repair attempt works the branch the pull request is already on -- one issue, one branch, one
    worktree, one pull request is unchanged by a second attempt at it (`AGENTS.md` section 4). The
    worktree usually still exists, because the pull request has not merged and `--sweep` removes
    only what merged at exactly its tip. When a previous session's machine is gone it does not,
    and the command that puts it back is a fact this can compute rather than one the next agent
    has to invent.
    """
    listing = git_maybe("worktree", "list", "--porcelain") or ""
    path = head = None
    for line in listing.splitlines():
        if line.startswith("worktree "):
            path, head = line[len("worktree "):], None
        elif line.startswith("branch ") and line[len("branch "):] == f"refs/heads/{branch}":
            head = path
            break
    if head:
        return head, None

    document = policy()
    variable = ((document.get("worktrees") or {}).get("rootEnvironmentVariable")
                or DEFAULT_WORKTREE_VARIABLE)
    root = os.environ.get(variable) or os.path.join(
        os.path.expanduser("~"), "rules-engine-worktrees", ROOT.name)
    target = os.path.join(root, branch)
    local = git_maybe("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    if local:
        return None, f"git worktree add {target} {branch}"
    return None, f"git fetch origin {branch} && git worktree add {target} -b {branch} origin/{branch}"


def verdicts_at(head, settings):
    """What is recorded at `head` under this engine's review contexts: `(rows, note)`.

    A repair attempt is answering something, and a recorded failure is the most precise statement
    of what. It is also the thing the next commit ends: the verdict is bound to this SHA, so the
    repair invalidates it by existing, which is the mechanism working rather than a cost.
    """
    review = settings.get("review") or {}
    contexts = [review.get("semanticContext")]
    contexts += [link.get("context") for link in review.get("independentFallback") or []]
    contexts = [context for context in contexts if context]
    document, why = gh_maybe("api", f"repos/{{owner}}/{{repo}}/commits/{head}/status",
                             "--jq", "[.statuses[] | {context, state, description}]")
    if document is None:
        return [], f"NOT CHECKED -- the commit statuses could not be read ({why})"
    try:
        statuses = json.loads(document or "[]")
    except ValueError as error:
        return [], f"NOT CHECKED -- the commit statuses could not be parsed ({error})"
    rows = [status for status in statuses if status.get("context") in contexts]
    rows.sort(key=lambda status: status.get("context") or "")
    return rows, None


def readings(paths):
    """Every finding the caller gave, in the order given. Empty is refused by `main`."""
    out = []
    for path in paths:
        if path == "-":
            out.append(sys.stdin.read())
        else:
            try:
                out.append(pathlib.Path(path).expanduser().read_text(encoding="utf-8"))
            except OSError as error:
                raise Refused(f"cannot read the findings from {path} ({error})")
    return out


def is_semantic(path, patterns):
    """Whether `path` is on the semantic surface, by the policy's glob patterns.

    `**` spans directories and `*` does not, which is what the patterns in `agent-policy.json`
    mean; fnmatch alone would treat `src/*` as matching `src/a/b.cs`. The same reading
    `tools/review-packet.py` and `tools/conformance-gate.py` use, so a brief cannot say a change
    owes something the gate will not ask for (#483).
    """
    for pattern in patterns:
        regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(regex, path):
            return True
    return False


def section(title, body):
    return f"## {title}\n\n{body.rstrip()}\n"


def build(number, findings):
    pull = json.loads(gh("pr", "view", str(number), "--json",
                         "number,title,state,isDraft,headRefOid,headRefName,baseRefName,"
                         "body,files,changedFiles,closingIssuesReferences"))
    state = (pull.get("state") or "").upper()
    if state != "OPEN":
        raise Refused(f"PR #{number} is {state or 'in an unknown state'}. A repair attempt works an open "
                      f"pull request; a merged or closed one is finished or abandoned, and either way the "
                      f"next change is a new issue (`AGENTS.md` section 4).")
    head = pull.get("headRefOid") or ""
    if not head:
        raise Refused(f"PR #{number} has no head commit")
    branch = pull.get("headRefName") or ""
    if not branch:
        raise Refused(f"PR #{number} names no head branch, so there is no branch to repair on")

    issues = pull.get("closingIssuesReferences") or []
    if len(issues) != 1:
        raise Refused(f"PR #{number} closes {len(issues)} issues; the rails allow exactly one "
                      f"(`AGENTS.md`). Fix the PR body before repairing against it.")
    issue_number = issues[0]["number"]
    issue = json.loads(gh("issue", "view", str(issue_number), "--json", "number,title,body,labels,state"))
    labels = [label["name"] for label in issue.get("labels") or []]

    settings = policy()
    review = settings.get("review") or {}
    names = settings.get("labels") or {}
    independent = names.get("independentRisk") in labels

    # The readiness refusal `tools/dispatch-agent.sh` makes, made here for the same reason (#483).
    # A repair attempt is an implementation attempt -- the contract says so -- so an issue that
    # stopped being workable while its pull request was open stops being workable for the repair
    # too. This brief read the labels, printed them, and implemented regardless, which is the one
    # way the change that introduced it weakened a protection the rails already had.
    issue_state = (issue.get("state") or "").upper()
    if issue_state and issue_state != "OPEN":
        raise Refused(f"issue #{issue_number} is {issue_state}, and PR #{number} claims to close it. A repair "
                      f"attempt implements an open issue; reopen it, or close the pull request.")
    for key, why in (("needsDecision",
                      "An implementation agent may not resolve the open question itself (`AGENTS.md` section 6). "
                      "The answer is the owner's, recorded as a ruling or a decision record; then the label moves "
                      "and the repair can be briefed."),
                     ("blocked",
                      "Something it depends on is not built yet. Work that dependency first, or move the label if "
                      "it is already done.")):
        label = names.get(key)
        if label and label in labels:
            raise Refused(f"issue #{issue_number} is {label}, and is not implementable. {why}")

    changed = [f["path"] for f in pull.get("files") or []]
    # `gh pr view --json files` caps at 100, silently, and `changedFiles` says how many there are.
    # The semantic line below is decided from these paths, and the conformance gate refuses the
    # same truncation for the same reason (#193).
    count = pull.get("changedFiles")
    if isinstance(count, int) and len(changed) != count:
        raise Refused(f"GitHub listed {len(changed)} of PR #{number}'s {count} changed files, so the file list is "
                      f"truncated and what this change owes cannot be decided from it. Read the pull request's "
                      f"files directly: `git diff origin/main...{head}`.")

    path, how = worktree_for(branch)
    entries = entry_ids(issue.get("body"), pull.get("body"))
    standing, note = verdicts_at(head, settings)

    parts = [f"# Repair attempt: PR #{number} — {pull.get('title', '')}\n",
             f"Issue #{issue_number}. Branch `{branch}`. Head commit `{head}`"
             + (" (draft)" if pull.get("isDraft") else "") + ".\n",
             "**You are a fresh attempt, not a continuation.** The previous attempt's conversation is "
             "gone on purpose and none of it was authoritative: the worktree holds the implementation, the "
             "map holds the rule, the overlay holds the mutations, and this brief holds what is wrong with "
             "the result. If something you need is in none of those, say so rather than reconstructing it "
             "from memory.\n"]

    parts.append(section("1. Where you work",
                         (f"The branch is checked out at:\n\n```\n{path}\n```\n\n"
                          f"Work there and nowhere else. Confirm it before your first write — "
                          f"`git rev-parse --git-common-dir` and `git rev-parse --git-dir` must differ."
                          if path else
                          f"**No worktree holds `{branch}` on this machine.** Put one back, and work there:\n\n"
                          f"```bash\n{how}\n```\n\n"
                          f"One issue, one branch, one worktree, one pull request: this is the same branch the "
                          f"pull request is already on, not a new one.")))

    parts.append(section("2. What is wrong",
                         "\n\n".join(f"### Finding {index}\n\n{text.strip()}"
                                     for index, text in enumerate(findings, 1)) +
                         "\n\nRepair exactly these. A defect you notice that is not one of them is a new "
                         "issue, not a second commit on this branch (`AGENTS.md` section 4)."))

    wanted = named_sections(issue.get("body"), ISSUE_SECTIONS)
    parts.append(section(f"3. What issue #{issue_number} asks for",
                         f"**{issue.get('title', '')}** ({issue.get('state', '')}) — "
                         f"labels: {', '.join(labels) or 'none'}\n\n"
                         + ("\n\n".join(f"### {name}\n\n{wanted[name]}" for name in ISSUE_SECTIONS if name in wanted)
                            if wanted else
                            "The issue states neither acceptance criteria nor required evidence. That is itself "
                            "a finding: say so rather than inferring what it wanted.")
                         + "\n\nThe rest of the issue is the case for the work, and the work is already on the "
                           "branch. Read the issue in full only if a finding turns on something this leaves out."))

    parts.append(section("4. The rule, as the map has it",
                         ("\n".join(f"- `{entry_id}` — `tools/entry-packet.py {entry_id}`" for entry_id in entries)
                          + "\n\nRead the entry packet before you change anything the finding calls a misreading. "
                            "The map is the interface and you do not remap it (`AGENTS.md` section 5)."
                          if entries else
                          "The issue and the pull request name no entry (no `rules-factory-entry` marker). "
                          "If a finding is about how a rule is read, that is missing context: say so.")))

    if note:
        recorded = note
    elif standing:
        recorded = "\n".join(f"- `{row.get('context')}` — **{row.get('state')}**"
                             + (f": {row.get('description')}" if row.get("description") else "")
                             for row in standing)
    else:
        recorded = f"No verdict is recorded at `{head[:12]}` under this engine's review contexts."
    parts.append(section("5. What is recorded at this head",
                         recorded +
                         f"\n\nYour repair commit moves the head, so every verdict above stops applying to it. "
                         f"That is the mechanism working: the next review reads the new bytes, from a new "
                         f"packet (`tools/review-packet.py {number}`)."))

    # What this change actually owes, decided the way `tools/review-packet.py` and
    # `tools/conformance-gate.py` decide it: from the changed paths against the policy's declared
    # semantic surface. It used to be asserted unconditionally, so a repair that fixed a README was
    # told it owed a verdict neither of them would ask for -- and a rail that overstates what is
    # owed is a rail agents learn to read past (#483).
    semantic = [path for path in changed if is_semantic(path, review.get("semanticPaths") or [])]
    gates = ["- `validate` — `./scripts/validate.sh full`, whole, and paste what it printed",
             f"- `{review.get('semanticContext', '(unset)')}` — a semantic verdict at the new head"
             if semantic else
             f"- `{review.get('semanticContext', '(unset)')}` — **not required as this pull request stands**: "
             f"nothing in it touches the semantic surface. Your repair can change that, and then it is."]
    if independent:
        chain = " → ".join(link.get("context", "?") for link in review.get("independentFallback") or [])
        gates.append(f"- one of: {chain} — required, because issue #{issue_number} is "
                     f"{names.get('independentRisk')}")
    parts.append(section("6. What you must satisfy before you finish",
                         "\n".join(gates) +
                         "\n\nAn overlay change is finished by `tools/re-produce.sh`, before the gate. Commit as "
                         "you go, stage explicit paths, and push to `" + branch + "` — the pull request is "
                         "already open and already says `Closes #" + str(issue_number) + "`; do not open a "
                         "second one. Then stop. You are one attempt."))

    parts.append(section("7. What you may not do",
                         "- Resolve a genuine ambiguity. Escalate it (`AGENTS.md` section 6) and stop; you may "
                         "not answer your own escalation.\n"
                         "- Argue a finding down. If a finding is wrong, say why, with the map's bytes — the "
                         "packet and the map decide, not the previous attempt's reasoning and not yours.\n"
                         "- Widen the change, remap the corpus, edit a generated file, a baseline or the gate.\n"
                         "- Assume anything about what the previous attempt tried. It is not recorded here "
                         "because it is not evidence."))

    after = json.loads(gh("pr", "view", str(number), "--json", "headRefOid"))
    if (after.get("headRefOid") or "") != head:
        raise Refused(f"PR #{number} moved while this brief was being assembled "
                      f"({head[:12]} -> {(after.get('headRefOid') or '')[:12]}); regenerate from the new head")
    return "\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="repair-packet.py", description=__doc__.split("\n")[0])
    parser.add_argument("pr", type=int, help="the pull request to repair")
    parser.add_argument("--finding", action="append", default=[], metavar="TEXT",
                        help="one blocking finding, verbatim; repeat for each")
    parser.add_argument("--findings", action="append", default=[], metavar="PATH",
                        help="a file of findings, or `-` for standard input; repeat for each")
    args = parser.parse_args(argv)

    try:
        findings = [text for text in args.finding] + readings(args.findings)
        findings = [text for text in findings if text.strip()]
        if not findings:
            raise Refused("no findings were given, and a repair attempt with nothing to repair is a fresh "
                          "implementation attempt: dispatch one, or say what blocks. Use --finding or --findings.")
        sys.stdout.write(build(args.pr, findings))
    except Refused as error:
        print(f"repair-packet: REFUSED -- {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
