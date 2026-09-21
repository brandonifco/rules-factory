#!/usr/bin/env python3
"""A pull request says what it did to every living document, and what it says matches its diff.

`validate.sh` holds the documents to the code where a machine can compare them: links resolve, the
decision index is complete, the README's CLI table matches the parser, no absence claim cites a
closed issue. Everything else a change makes untrue -- a paragraph in method.md, a row in the
backlog guide, a rail's own instructions -- is found only by a person reading, and #170 is what
happens when nobody is asked to. So every pull request carries a `## Documentation` section with
one line per living document:

    - [x] `docs/method.md` — updated: phase 3 names the bound category
    - [x] `README.md` — checked, no change: the status table does not describe map checks

This check cannot tell whether anyone read a file. What it does hold, mechanically:

  * every living document is listed, ticked, and carries a note after the colon;
  * a document the diff changes, adds or deletes -- living or frozen -- is listed as `updated`;
  * a document listed as `updated` is one the diff changes;
  * a listed path that is not a living document or in the diff is a typo, and fails.

Living means every tracked `*.md` except the two kinds that are frozen by design: numbered
decision records (`docs/decisions/NNNN-*.md`, superseded by a new record, never rewritten) and
trial evidence under `examples/<trial>/` (a record of what happened). `examples/README.md` and
`docs/decisions/README.md` are indexes, and living. A new document is living the moment it is
committed; nothing has to register it.

`--skeleton` prints the section for the current diff, unticked, for the author to complete.

Usage: check-pr-docs.py --event FILE            (CI: the pull_request event payload)
       check-pr-docs.py --pr N                  (a pull request, read with gh)
       check-pr-docs.py --body FILE [--base REF] [--head REF]
       check-pr-docs.py --skeleton [--base REF] [--head REF]
Exit 0 when the section holds; 1 when it does not; 2 when the inputs cannot be read.
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
HEADING = "## Documentation"
FROZEN = (re.compile(r"^docs/decisions/\d{4}-[^/]+\.md$"), re.compile(r"^examples/[^/]+/.+\.md$"))
LINE = re.compile(
    r"^[-*]\s*\[(?P<tick>[ xX])\]\s*`?(?P<path>[^`\s]+\.md)`?\s*[—–-]+\s*"
    r"(?P<verdict>updated|checked, no change)\s*:\s*(?P<note>.*?)\s*$")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


class Unreadable(Exception):
    pass


def git(*args, root):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        raise Unreadable(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def is_frozen(path):
    return any(pattern.match(path) for pattern in FROZEN)


def living_documents(root, head):
    listing = git("ls-tree", "-r", "--name-only", head, root=root)
    return sorted(p for p in listing.splitlines() if p.endswith(".md") and not is_frozen(p))


def changed_documents(root, base, head):
    listing = git("diff", "--name-only", "--no-renames", f"{base}...{head}", root=root)
    return sorted(p for p in listing.splitlines() if p.endswith(".md"))


def section(body):
    """The lines under `## Documentation`, comments removed, or None when there is no section."""
    lines = COMMENT.sub("", (body or "").replace("\r\n", "\n")).split("\n")
    for start, line in enumerate(lines):
        if line.strip() == HEADING:
            rest = lines[start + 1:]
            end = next((i for i, l in enumerate(rest) if l.startswith("## ")), len(rest))
            return [l.strip() for l in rest[:end] if l.strip()]
    return None


def problems(body, living, changed):
    lines = section(body)
    if lines is None:
        return [f"the description has no `{HEADING}` section; check-pr-docs.py --skeleton prints one"]
    found, listed = [], {}
    for line in lines:
        match = LINE.match(line)
        if not match:
            if line.startswith(("-", "*")):
                found.append(f"cannot read: {line!r} (expected: - [x] `path.md` — updated: note)")
            continue
        path = match["path"]
        if path in listed:
            found.append(f"`{path}` is listed twice")
        listed[path] = match
        if match["tick"] == " ":
            found.append(f"`{path}` is not ticked")
        if not match["note"]:
            found.append(f"`{path}` has no note after `{match['verdict']}:`")
    # Abbreviated paths first, and what they resolve to is not reported missing as well: one
    # clear message beats a clear one under a redundant one.
    real = set(living) | set(changed)
    covered = set()
    for path in list(listed):
        if not ELLIPSIS.search(path):
            continue
        meant = resolves_to(path, real)
        if len(meant) == 1:
            found.append(f"`{path}` is abbreviated -- it has an ellipsis in it. Write the path "
                         f"in full: `{meant[0]}`")
            covered.add(meant[0])
        elif meant:
            found.append(f"`{path}` is abbreviated -- it has an ellipsis in it, and could be any "
                         f"of: {', '.join(f'`{m}`' for m in meant)}. Write one in full")
        else:
            found.append(f"`{path}` is abbreviated -- it has an ellipsis in it, and no document "
                         f"here matches what is either side of it")
    for path in living:
        if path in covered:
            continue
        if path not in listed:
            found.append(f"`{path}` is a living document and is not listed")
    for path in changed:
        if path in covered:
            continue
        if path not in listed:
            found.append(f"`{path}` is changed by this pull request and is not listed")
        elif listed[path]["verdict"] != "updated":
            found.append(f"`{path}` is changed by this pull request but listed as checked, no change")
    for path, match in listed.items():
        if ELLIPSIS.search(path):
            continue  # already reported above, with what it should have said
        if path not in living and path not in changed:
            found.append(f"`{path}` is neither a living document nor changed here")
        elif match["verdict"] == "updated" and path not in changed:
            found.append(f"`{path}` is listed as updated but this pull request does not change it")
    return found


# An abbreviated path, written the way a person abbreviates one when the real name is long: a
# Unicode ellipsis, or three full stops, standing for the middle of it. No document is named this
# way, so the path matches nothing -- and before this the check said so twice and unhelpfully, once
# as "neither a living document nor changed here" for what was written, and once as "is a living
# document and is not listed" for what was meant. Neither named the ellipsis. That is the failure
# #365 merged through, and this check is a required one now, so its diagnostics have to say what
# is actually wrong.
ELLIPSIS = re.compile(r"\u2026|\.\.\.")


def resolves_to(path, candidates):
    """The real documents an abbreviated `path` could mean: same head and same tail."""
    head, _, tail = ELLIPSIS.split(path, 1)[0], None, ELLIPSIS.split(path, 1)[-1]
    return sorted(c for c in candidates if c.startswith(head) and c.endswith(tail))


def skeleton(living, changed):
    lines = [HEADING, ""]
    for path in sorted(set(living) | set(changed)):
        verdict = "updated" if path in changed else "checked, no change"
        lines.append(f"- [ ] `{path}` — {verdict}: ")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--event", help="a GitHub pull_request event payload")
    source.add_argument("--pr", type=int, help="a pull request number, read with gh")
    source.add_argument("--body", help="a file holding the pull request description")
    source.add_argument("--skeleton", action="store_true", help="print the section to fill in")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    base, head, body = args.base, args.head, ""
    try:
        if args.event:
            with open(args.event, encoding="utf-8") as handle:
                pull = json.load(handle)["pull_request"]
            base, head, body = pull["base"]["sha"], pull["head"]["sha"], pull.get("body") or ""
        elif args.pr:
            result = subprocess.run(
                ["gh", "pr", "view", str(args.pr), "--json", "body,baseRefName,headRefOid"],
                cwd=args.root, capture_output=True, text=True)
            if result.returncode != 0:
                raise Unreadable(f"gh pr view {args.pr}: {result.stderr.strip()}")
            pull = json.loads(result.stdout)
            base, head, body = f"origin/{pull['baseRefName']}", pull["headRefOid"], pull["body"]
        elif args.body:
            with open(args.body, encoding="utf-8") as handle:
                body = handle.read()
        living = living_documents(args.root, head)
        changed = changed_documents(args.root, base, head)
    except (OSError, KeyError, ValueError, Unreadable) as error:
        print(f"check-pr-docs: cannot read the inputs: {error}", file=sys.stderr)
        return 2

    if args.skeleton:
        print(skeleton(living, changed))
        return 0
    if not living:
        print("check-pr-docs: no living documents found -- this check proved nothing", file=sys.stderr)
        return 2
    found = problems(body, living, changed)
    for problem in found:
        print(f"  X  {problem}")
    if found:
        print(f"\n{len(found)} problem(s) in the Documentation section")
        return 1
    print(f"{len(living)} living document(s) accounted for, {len(changed)} changed, all listed as updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
