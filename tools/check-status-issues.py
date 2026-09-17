#!/usr/bin/env python3
"""README.md says nothing is "not yet" or "not done" on the strength of a closed issue (#170).

#75 tied the README's CLI table to the parser, and the prose beside it drifted anyway: three days
later the README said the acceptance test was "not done (#3)" after #3 closed with every criterion
ticked, and "Not yet: the PR policy and the verdict gates (#152-#155)" after all four merged. A
parser cannot tell whether a sentence is true, but one claim shape can be checked: a statement
that something is missing, citing the issue that tracks it. When that issue is closed, the
statement is stale, or the issue was closed wrongly; either way a person has to look.

A claim is one table row, or one paragraph (text between blank lines). It is an absence claim when
it contains "not yet", "not done" or "not passed", or says something "is open", "are open",
"remains open" or "still open" (any case). The last four were added after the README's own "Where
this sits" table said "acceptance test (#3) not passed" and "the acceptance run is open (#1, #4)"
for a day after all three closed, which the first two phrases did not catch. Every issue of this repository it cites, as a
link to `github.com/<repo>/issues/N` or as a bare `#N`, must be open. An absence claim that cites
no issue is not checked; `check-readme-status.py` holds the `not implemented` rows to the CLI.

Issue state comes from the GitHub REST API, authenticated with GH_TOKEN or GITHUB_TOKEN when set.
A state that cannot be read is a failure, not a pass: set RULES_FACTORY_OFFLINE=1 to run without
the network, and the check says NOT CHECKED instead of claiming anything.

Consequence to know about: closing an issue can turn the next validate run red, with no commit,
until the README stops citing it as missing. That is the point.

Usage: check-status-issues.py [--readme FILE] [--repo OWNER/NAME]
Exit 0 when every cited issue is open (or RULES_FACTORY_OFFLINE=1); 1 otherwise. Standard library only.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = "brandonifco/rules-factory"
ABSENCE = re.compile(r"\bnot (?:yet|done|passed)\b|\b(?:is|are|remains|still) open\b", re.IGNORECASE)


class Problem(Exception):
    pass


def claims(text):
    """[(first line number, claim text)]: each table row alone, each paragraph otherwise."""
    result, paragraph, start = [], [], None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("|"):
            if paragraph:
                result.append((start, "\n".join(paragraph)))
                paragraph = []
            result.append((number, stripped))
        elif not stripped:
            if paragraph:
                result.append((start, "\n".join(paragraph)))
                paragraph = []
        else:
            if not paragraph:
                start = number
            paragraph.append(stripped)
    if paragraph:
        result.append((start, "\n".join(paragraph)))
    return result


def cited_issues(claim, repo):
    """The issue numbers of `repo` that `claim` cites, in order of first mention."""
    link = re.compile(r"github\.com/" + re.escape(repo) + r"/(?:issues|pull)/(\d+)")
    numbers = [int(n) for n in link.findall(claim)]
    # A bare #N, not owner/repo#N (another repository) and not part of a URL fragment or word.
    bare = link.sub("", claim)
    numbers += [int(n) for n in re.findall(r"(?<![\w/#])#(\d+)\b", bare)]
    return list(dict.fromkeys(numbers))


def github_state(repo, number):
    """'open' or 'closed', from the GitHub REST API."""
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues/{number}",
                                     headers={"Accept": "application/vnd.github+json",
                                              "User-Agent": "rules-factory-check-status-issues"})
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)["state"]
    except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
        raise Problem(f"could not read the state of #{number}: {error}") from error


def check(text, repo, state_of):
    """Problems as lines, and how many issue citations in absence claims were examined."""
    problems, examined, states = [], 0, {}
    for number, claim in claims(text):
        if not ABSENCE.search(claim):
            continue
        for issue in cited_issues(claim, repo):
            examined += 1
            if issue not in states:
                states[issue] = state_of(repo, issue)
            if states[issue] != "open":
                phrase = ABSENCE.search(claim).group(0)
                problems.append(f"README line {number}: says {phrase!r} citing #{issue}, which is "
                                f"{states[issue]}")
    return problems, examined


def main(argv=None, state_of=github_state):
    parser = argparse.ArgumentParser(prog="check-status-issues.py", description=__doc__.split("\n")[0])
    parser.add_argument("--readme", default=os.path.join(ROOT, "README.md"))
    parser.add_argument("--repo", default=REPO)
    args = parser.parse_args(argv)
    if os.environ.get("RULES_FACTORY_OFFLINE") == "1":
        print("NOT CHECKED: RULES_FACTORY_OFFLINE=1, so no issue state was read")
        return 0
    try:
        with open(args.readme, encoding="utf-8") as handle:
            text = handle.read()
        problems, examined = check(text, args.repo, state_of)
    except (OSError, Problem) as error:
        print(f"check-status-issues: {error}", file=sys.stderr)
        return 1
    for line in problems:
        print(f"  X  {line}")
    if problems:
        print(f"\n{len(problems)} closed issue citation(s) in README.md absence claims")
        return 1
    print(f"{examined} issue citation(s) in absence claims, every one open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
