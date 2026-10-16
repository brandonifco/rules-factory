#!/usr/bin/env python3
"""A pull request has a review budget: one independent review and one focused recheck (#678).

#677 went through eleven independent review rounds, each followed by a fresh repair, before the
owner stopped the cycle. Each round found real but ever narrower defects, and nothing bounded the
churn. AGENTS.md section 6 now does: a pull request gets one initial independent review and one
focused recheck. A third round means the change itself is the problem, and the way out is a
root-cause analysis and a redesign, not another repair-and-review pair.

Each round is recorded on the pull request as a comment whose body starts with
`Independent review (`. This counts those comments and fails when there are more than two, unless
the description has a non-empty `## Review budget exceeded` section naming the structural cause
and the redesign decided.

The budget limits process churn, not correctness: a genuine safety defect blocks the merge inside
the budget or outside it. This check cannot tell whether the section's reasoning is any good; it
holds that someone had to write it down.

Usage: check-review-budget.py --pr N        (a pull request, read with gh)
Exit 0 when the budget holds, printing the count; 1 when it is exceeded without the section;
2 when the pull request cannot be read -- a gh failure is a failure, never a pass.
Standard library only.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HEADER = "Independent review ("
BUDGET = 2
HEADING = "## Review budget exceeded"
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


class Unreadable(Exception):
    pass


def rounds(comments):
    """How many comments are an independent review round: the body starts with the header."""
    return sum(1 for c in comments if (c.get("body") or "").lstrip().startswith(HEADER))


def exceeded_section(body):
    """The text under `## Review budget exceeded`, comments removed; "" when absent or empty."""
    lines = COMMENT.sub("", (body or "").replace("\r\n", "\n")).split("\n")
    for start, line in enumerate(lines):
        if line.strip() == HEADING:
            rest = lines[start + 1:]
            end = next((i for i, l in enumerate(rest) if l.startswith("## ")), len(rest))
            return "\n".join(l.strip() for l in rest[:end] if l.strip())
    return ""


def verdict(body, comments):
    """(exit code, one line) for a pull request's description and comments."""
    count = rounds(comments)
    if count > BUDGET and not exceeded_section(body):
        return 1, (f"{count} independent review rounds exceed the budget of {BUDGET}, and the "
                   f"description has no non-empty `{HEADING}` section naming the cause and the "
                   f"redesign (AGENTS.md section 6)")
    if count > BUDGET:
        return 0, f"{count} independent review rounds, over the budget of {BUDGET}, and `{HEADING}` is filled"
    return 0, f"{count} independent review round(s), within the budget of {BUDGET}"


def read_pull(number, root):
    result = subprocess.run(["gh", "pr", "view", str(number), "--json", "body,comments"],
                            cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        raise Unreadable(f"gh pr view {number}: {result.stderr.strip()}")
    try:
        pull = json.loads(result.stdout)
        return pull["body"] or "", pull["comments"]
    except (ValueError, KeyError, TypeError) as error:
        raise Unreadable(f"gh pr view {number}: unexpected output: {error}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--pr", type=int, required=True, help="a pull request number, read with gh")
    parser.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        body, comments = read_pull(args.pr, args.root)
    except (OSError, Unreadable) as error:
        print(f"check-review-budget: cannot read the pull request: {error}", file=sys.stderr)
        return 2
    code, line = verdict(body, comments)
    print(line, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
