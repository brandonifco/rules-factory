#!/usr/bin/env python3
"""Whether this pull request has the review verdicts it needs, at the commit being merged.

    tools/conformance-gate.py <pr-number>

Emitted by rules-factory as a managed file (decision 0029), and run by
`.github/workflows/conformance-gate.yml` as a required check.

**What it asks.** For the pull request's current head commit:

  1. does the change touch the semantic surface (`review.semanticPaths`)? Then the semantic
     verdict must be recorded, and successful, at that commit.
  2. is the linked issue classified as needing independent review? Then one of the configured
     independent contexts must also be recorded, and successful, at that commit.
  3. is any configured context recorded as a failure at that commit? Then this blocks, whatever
     else is green.

**Why the head commit, and not "the pull request".** A verdict is formed on bytes somebody read.
A commit after it means nobody has read the bytes being merged. Because the status lives on the
commit rather than on the pull request, that invalidation is automatic: nothing has to notice.

**Why a recorded failure blocks outright.** The independent chain exists to catch the plausible,
fluent, wrong implementation -- the failure a second reviewer from the same family reproduces
rather than catches. A chain that could be walked until one link agrees would produce exactly the
outcome it exists to prevent, at more expense. So the chain advances only when a provider was
unavailable, and a fail anywhere in it stands until the code, the map or an owner's ruling changes.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`).
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


class Undecidable(Exception):
    """The gate cannot tell. It says so and fails: silence is not a pass."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT, timeout=120)
    if done.returncode != 0:
        raise Undecidable(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def is_semantic(path, patterns):
    for pattern in patterns:
        regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(regex, path):
            return True
    return False


def statuses(repository, sha):
    """context -> state, the most recent status per context at `sha`."""
    document = json.loads(gh("api", f"repos/{repository}/commits/{sha}/status", "--paginate"))
    found = {}
    for status in document.get("statuses") or []:
        found.setdefault(status["context"], status["state"])
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(prog="conformance-gate.py", description=__doc__.split("\n")[0])
    parser.add_argument("pr", type=int)
    args = parser.parse_args(argv)

    try:
        with open(ROOT / POLICY, encoding="utf-8") as handle:
            review = (json.load(handle).get("review") or {})
        semantic_context = review.get("semanticContext")
        chain = review.get("independentFallback") or []
        if not semantic_context:
            raise Undecidable(f"{POLICY} sets no review.semanticContext")

        pull = json.loads(gh("pr", "view", str(args.pr), "--json",
                             "number,headRefOid,files,closingIssuesReferences"))
        sha = pull.get("headRefOid")
        if not sha:
            raise Undecidable(f"PR #{args.pr} has no head commit")
        changed = [f["path"] for f in pull.get("files") or []]
        touched = sorted(path for path in changed if is_semantic(path, review.get("semanticPaths") or []))

        issues = pull.get("closingIssuesReferences") or []
        if len(issues) != 1:
            raise Undecidable(f"PR #{args.pr} closes {len(issues)} issues; exactly one is required "
                              f"(pr-policy.py says the same, and says it first)")
        issue = json.loads(gh("issue", "view", str(issues[0]["number"]), "--json", "number,labels"))
        names = {label["name"] for label in issue.get("labels") or []}

        with open(ROOT / POLICY, encoding="utf-8") as handle:
            labels = json.load(handle).get("labels") or {}
        independent_required = labels.get("independentRisk") in names

        repository = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
        recorded = statuses(repository, sha)
    except (Undecidable, OSError, ValueError, KeyError) as error:
        print(f"conformance-gate: cannot decide PR #{args.pr} -- {error}", file=sys.stderr)
        print("An undecidable gate fails. A check that cannot examine what it is for is not a pass.", file=sys.stderr)
        return 2

    print(f"conformance-gate: PR #{args.pr}, head {sha[:12]}")
    print(f"  semantic surface: {len(touched)} changed file(s)" + (f" ({', '.join(touched[:4])})" if touched else ""))
    print(f"  recorded at this commit: {', '.join(f'{c}={s}' for c, s in sorted(recorded.items())) or 'nothing'}")

    problems = []
    configured = [semantic_context] + [link.get("context") for link in chain]
    for context in configured:
        if recorded.get(context) in ("failure", "error"):
            problems.append(f"{context} is recorded as a failure at {sha[:12]}. A recorded failure blocks outright: "
                            f"fix the code, fix the map, or get an owner's ruling. Recording a pass at another "
                            f"context does not clear it.")

    if touched and recorded.get(semantic_context) != "success":
        problems.append(f"{semantic_context} is not recorded as a success at {sha[:12]}, and this change touches the "
                        f"semantic surface. Review the head commit and record the verdict "
                        f"(`tools/record-verdict.py --pr {args.pr} --reviewer semantic --verdict pass`). "
                        f"A verdict on an earlier commit is a verdict on bytes nobody is merging.")

    if independent_required:
        passed = [link.get("context") for link in chain if recorded.get(link.get("context")) == "success"]
        if not passed:
            names = " or ".join(link.get("context", "?") for link in chain)
            problems.append(f"issue #{issue['number']} is {labels.get('independentRisk')}, so one of {names} must "
                            f"also be recorded as a success at {sha[:12]}. The chain is tried in order, and it "
                            f"advances only when a provider is unavailable.")
        else:
            print(f"  independent verdict: {passed[0]}")

    if problems:
        print(f"\nconformance-gate: BLOCKED ({len(problems)}):")
        for problem in problems:
            print(f"  X  {problem}")
        return 1
    if not touched:
        print("  nothing on the semantic surface: no rules verdict required for this change")
    print("\nconformance-gate: the verdicts this change needs are recorded at the commit being merged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
