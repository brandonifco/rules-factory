#!/usr/bin/env python3
"""Ask the conformance gate to report again when something outside the pull request changed
what it would answer.

    VERDICT_SHA=<sha> VERDICT_CONTEXT=<context> VERDICT_STATE=<state> tools/requeue-gate.py
    ISSUE_NUMBER=<n> ISSUE_LABEL=<name> tools/requeue-gate.py

Emitted by rules-factory as a managed file (decision 0029), and run by
`.github/workflows/verdict-requeue.yml` on GitHub's `status` and `issues` events.

**Two occasions, one gap.** The gate reads two things that are not the pull request's own commits:
the verdicts recorded at its head, and the risk label on the issue it closes. Neither is a
`pull_request` event, so neither re-runs the required check, which keeps the answer it reached
before. The verdict half was rules-factory #191. The risk half is #230: the gate decides whether
an independent verdict is required from the labels on the *linked issue*, while the workflow runs
on `labeled`/`unlabeled` of the *pull request*, so adding the risk label to the issue after the
gate passed leaves a green required check that no longer reflects the issue's risk -- and the
pull request merges without the independent verdict it now needs. 0029 keeps risk the
orchestrator's call, a label anyone who can write labels may set at any time; this is what makes
the gate follow it.

**The gap this closes.** `tools/record-verdict.py` writes a commit status on a pull request's head.
The required `conformance-gate` check had already concluded, on an earlier run, that the verdict
was missing -- and a commit status is not a check run, so recording one re-runs nothing. The pull
request stays blocked on a check whose answer has changed, until somebody notices and re-runs it by
hand. This re-requests that run instead, so the recorded verdict is the whole of the step.

**Why it writes no commit status and no check run, ever.** Both obvious shortcuts are worse than
the defect. A commit status named `conformance-gate` does not replace the failed check run of that
name: GitHub requires both when a status and a check share a required check's name, so the red
check run survives beside the green status and the pull request can never merge. A second check
run of that name is ambiguous by GitHub's own account -- there is then no one answer to "is
`conformance-gate` green". The gate reports its own result, once, from its own workflow run; this
tool's only effect is to cause one of those runs to happen again.

**Why this cannot loop.** It acts only on a status whose context is one the engine's review policy
configures, and the only thing that writes those is `tools/record-verdict.py`. Re-requesting a
workflow run produces check runs, not commit statuses, so nothing this tool causes can deliver
another `status` event. The context filter is the argument, not a precaution on top of it.

**What it cannot do.** Re-request a run that does not exist: there must already be a
`pull_request` run of the gate at that head, which there is as soon as the pull request was opened
or pushed. And GitHub only allows re-running a workflow run for 30 days, after which the branch
must be pushed to produce a new one. Both are reported as failures naming themselves rather than
passed over in silence.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`).
"""
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
GATE_WORKFLOW = "conformance-gate.yml"
SHA = re.compile(r"^[0-9a-f]{40}$")
# A run in one of these has not concluded, so it will report at this commit without being asked.
UNFINISHED = ("queued", "in_progress", "requested", "waiting", "pending")


class Refused(Exception):
    """Nothing to do, or nothing this tool may do. Nothing is re-requested."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT, timeout=120)
    if done.returncode != 0:
        raise Refused(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def verdict_contexts():
    """Every status context a verdict is recorded under, from the engine's own policy."""
    with open(ROOT / POLICY, encoding="utf-8") as handle:
        review = json.load(handle).get("review") or {}
    semantic = review.get("semanticContext")
    if not semantic:
        raise Refused(f"{POLICY} sets no review.semanticContext, so no status can be told to be a verdict")
    return [semantic] + [link.get("context") for link in review.get("independentFallback") or [] if link.get("context")]


def newest_gate_run(repository, sha):
    """The most recent `pull_request` run of the gate at `sha`, or None."""
    document = json.loads(gh("api", f"repos/{repository}/actions/workflows/{GATE_WORKFLOW}/runs"
                             f"?head_sha={sha}&event=pull_request&per_page=50"))
    runs = document.get("workflow_runs") or []
    # GitHub lists newest first; sorting on the run number rather than trusting that is cheap, and
    # the wrong run here would re-run the gate against bytes nobody is merging.
    return max(runs, key=lambda run: run.get("run_number") or run.get("id") or 0) if runs else None


def requeue_at(repository, sha, numbers):
    """Re-request the newest `pull_request` gate run at `sha`. Returns (done, waiting, blocked)."""
    requeued, waiting, unavailable = [], [], []
    run = newest_gate_run(repository, sha)
    if run is None:
        unavailable.append(f"no {GATE_WORKFLOW} run on the `pull_request` event at {sha[:12]} to re-request. "
                           f"There is one as soon as the pull request is opened or pushed to")
    elif (run.get("status") or "") in UNFINISHED:
        waiting.append(f"run {run['id']} is {run['status']}; it will report at {sha[:12]} without being asked")
    else:
        try:
            gh("api", f"repos/{repository}/actions/runs/{run['id']}/rerun", "-X", "POST")
            requeued.append(f"re-requested {GATE_WORKFLOW} run {run['id']} at {sha[:12]} for {numbers}")
        except Refused as error:
            # The 30-day limit lands here, and it is the one failure a re-run cannot work around.
            unavailable.append(f"run {run['id']} could not be re-requested ({error}). GitHub allows "
                               f"re-running a run for 30 days; after that the branch must be pushed to "
                               f"produce a new one")
    return requeued, waiting, unavailable


def risk_label():
    """The label the engine's own policy calls independent risk, and nothing else."""
    with open(ROOT / POLICY, encoding="utf-8") as handle:
        labels = json.load(handle).get("labels") or {}
    name = labels.get("independentRisk")
    if not name:
        raise Refused(f"{POLICY} names no labels.independentRisk, so no label can be told to be a risk label")
    return name


def for_issue():
    """The `issues` half: an issue was labelled or unlabelled, so every open pull request that
    closes it may now need a different answer from the gate.

    The link is `closingIssuesReferences`, which is the same link conformance-gate.py reads to
    find the issue in the first place -- so the two agree about which pull request an issue
    governs by construction rather than by two similar queries.
    """
    number = (os.environ.get("ISSUE_NUMBER") or "").strip()
    label = (os.environ.get("ISSUE_LABEL") or "").strip()
    if not number.isdigit():
        raise Refused(f"ISSUE_NUMBER is {number!r}, which is not an issue number")
    configured = risk_label()
    if label != configured:
        print(f"requeue-gate: {label!r} is not the risk label ({configured}); the gate does not read it, "
              f"so nothing to do")
        return 0

    repository = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
    pulls = json.loads(gh("pr", "list", "--state", "open", "--json",
                          "number,headRefOid,closingIssuesReferences"))
    closing = [pull for pull in pulls
               if any(str(issue.get("number")) == number
                      for issue in pull.get("closingIssuesReferences") or [])]
    if not closing:
        # Not a failure. Labelling an issue no open pull request closes is the ordinary case:
        # risk is set when the issue is triaged, usually before anything is opened against it.
        print(f"requeue-gate: no open pull request closes #{number}; nothing to re-run")
        return 0

    requeued, waiting, unavailable = [], [], []
    # Per pull request, not per commit: two pull requests closing one issue head different
    # commits, and each has its own gate run to re-request.
    for pull in closing:
        head = (pull.get("headRefOid") or "").strip()
        if not SHA.fullmatch(head):
            unavailable.append(f"PR #{pull.get('number')} has no readable head commit")
            continue
        done, later, blocked = requeue_at(repository, head, f"#{pull.get('number')}")
        requeued += done
        waiting += later
        unavailable += blocked

    numbers = ", ".join(f"#{pull.get('number')}" for pull in closing)
    print(f"requeue-gate: {label} {os.environ.get('ISSUE_ACTION', 'changed')} on #{number}, "
          f"closed by {numbers}")
    for line in requeued + waiting:
        print(f"  {line}")
    if not requeued and not waiting:
        for line in unavailable:
            print(f"  X  {line}", file=sys.stderr)
        print(f"requeue-gate: the risk label on #{number} re-ran nothing, so the required check still holds "
              f"its previous answer.", file=sys.stderr)
        return 1
    return 0


def main():
    if os.environ.get("ISSUE_NUMBER"):
        try:
            return for_issue()
        except (Refused, OSError, ValueError, KeyError) as error:
            print(f"requeue-gate: {error}", file=sys.stderr)
            return 1
    sha = (os.environ.get("VERDICT_SHA") or "").strip()
    context = (os.environ.get("VERDICT_CONTEXT") or "").strip()
    state = (os.environ.get("VERDICT_STATE") or "").strip()
    try:
        if not SHA.fullmatch(sha):
            raise Refused(f"VERDICT_SHA is {sha!r}, which is not a 40-character commit SHA")
        configured = verdict_contexts()
        if context not in configured:
            print(f"requeue-gate: {context!r} is not a verdict context ({', '.join(configured)}); nothing to do")
            return 0
        if state == "pending":
            print(f"requeue-gate: {context} is pending at {sha[:12]}; a verdict that has not concluded changes "
                  f"nothing the gate would read")
            return 0

        repository = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
        pulls = json.loads(gh("pr", "list", "--state", "open", "--json", "number,headRefOid"))
        heading = [pull for pull in pulls if pull.get("headRefOid") == sha]
        if not heading:
            # Not a failure, and deliberately not reported anywhere but here. A verdict can be
            # recorded on a commit no open pull request heads -- an older commit, a merged branch --
            # and a failing check on such a commit would be a red mark on a commit nobody can clear
            # (rules-factory #191, acceptance criterion 2).
            print(f"requeue-gate: no open pull request heads {sha}; nothing to re-run")
            return 0

        # One run, however many pull requests head this commit: a workflow run is keyed by the
        # commit it ran on, and the gate reads the pull request out of that run's own event. So
        # re-requesting it once is the whole of the work, and doing it per pull request would
        # re-request the same run twice.
        numbers = ", ".join(f"#{pull.get('number')}" for pull in heading)
        requeued, waiting, unavailable = requeue_at(repository, sha, numbers)
    except (Refused, OSError, ValueError, KeyError) as error:
        print(f"requeue-gate: {error}", file=sys.stderr)
        return 1

    print(f"requeue-gate: {context}={state} at {sha[:12]}, headed by {numbers}")
    for line in requeued + waiting:
        print(f"  {line}")
    if not requeued and not waiting:
        for line in unavailable:
            print(f"  X  {line}", file=sys.stderr)
        print(f"requeue-gate: the verdict at {sha[:12]} re-ran nothing, so the required check still holds its "
              f"previous answer.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
