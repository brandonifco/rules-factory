#!/usr/bin/env python3
"""Search a rebuild session's transcript and network log for signs it was not blind. RUNBOOK.md, step 6.

    python3 examples/hoyle-blind-rebuild/search-transcript.py --network-log network.jsonl TRANSCRIPT...

A TRANSCRIPT is a Claude Code session file (JSON lines) or any plain text log. In a JSON-lines file,
the inputs of `tool_use` blocks are the session's *actions* (commands run, files read, URLs fetched)
and every string is *text*. A line that is not JSON counts as both.

FAIL, exit 1:
  * a hand-written test method of the target (TARGET tests.projects.*.handWritten) anywhere in the text,
    unless it is a name the brief itself discloses (TARGET brief.disclosures): those long names cannot
    arise by chance, and the brief holds no others;
  * an action naming github.com or githubusercontent.com, hoyle-backgammon, hoyle-blind-rebuild, or
    rules-factory's examples/, tools/tests/, issues or pulls;
  * a network request the proxy refused to a github host or naming the target, and any request the
    proxy allowed to a host not in sandbox/allowlist.txt (which the proxy never does, so it means the
    log is not the proxy's).

REVIEW, reported without failing: a hand-written test class name of the target in the text (short
names such as `PositionTests` are ones an implementer may choose for his own tests), and every other
refused request (NuGet's certificate revocation checks over plain HTTP are refused routinely).

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"github\.com", r"githubusercontent\.com", r"hoyle-backgammon", r"hoyle-blind-rebuild",
        r"rules-factory/(?:blob/[^/\s]+/|tree/[^/\s]+/)?(?:examples|tools/tests)\b", r"rules-factory/(?:issues|pulls?)\b",
    )
]
GITHUB_HOST = re.compile(r"(?:^|\.)(?:github\.com|githubusercontent\.com|githubassets\.com)(?::\d+)?$", re.IGNORECASE)


def strings(value, in_action=False):
    """(string, is_action) for every string in a JSON value; a tool_use block's input is an action."""
    if isinstance(value, str):
        yield value, in_action
    elif isinstance(value, dict):
        action = in_action or value.get("type") == "tool_use"
        for key, item in value.items():
            yield from strings(item, action and (in_action or key == "input"))
    elif isinstance(value, list):
        for item in value:
            yield from strings(item, in_action)


def allowlist(path: Path) -> list[str]:
    rules = [line.split("#", 1)[0].strip().lower() for line in path.read_text(encoding="utf-8").splitlines()]
    return [r for r in rules if r]


def host_allowed(host: str, rules: list[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == r or (r.startswith(".") and (host.endswith(r) or host == r[1:])) for r in rules)


def search(target: dict, transcripts: list[Path], network_log: Path | None, allow: Path) -> tuple[list[str], list[str]]:
    disclosed = {d["name"] for d in target["brief"]["disclosures"]}
    methods = sorted({m.rsplit(".", 1)[1] for p in target["tests"]["projects"].values() for m in p["handWritten"]}
                     - disclosed, key=len, reverse=True)
    classes = sorted(set(target["tests"]["handWrittenClasses"]) - disclosed, key=len, reverse=True)
    method_re = re.compile(r"\b(" + "|".join(map(re.escape, methods)) + r")\b") if methods else None
    class_re = re.compile(r"\b(" + "|".join(map(re.escape, classes)) + r")\b") if classes else None
    fails, reviews = [], []
    for transcript in transcripts:
        for number, line in enumerate(transcript.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            try:
                items = list(strings(json.loads(line)))
            except ValueError:
                items = [(line, True)]
            where = f"{transcript.name}:{number}"
            for text, is_action in items:
                if method_re:
                    fails += [f"{where}: the target's test method {m.group(1)}" for m in method_re.finditer(text)]
                if class_re:
                    reviews += [f"{where}: the target's test class name {m.group(1)}" for m in class_re.finditer(text)]
                if is_action:
                    for pattern in ACTION_PATTERNS:
                        if match := pattern.search(text):
                            fails.append(f"{where}: an action names {match.group(0)!r}: {text[:160]!r}")
    if network_log is not None:
        rules = allowlist(allow)
        for number, line in enumerate(network_log.read_text(encoding="utf-8").splitlines(), 1):
            entry = json.loads(line)
            target_text = entry.get("target", "")
            host = target_text.rsplit(":", 1)[0] if entry.get("method") == "CONNECT" else \
                re.sub(r"^[a-z]+://([^/:]+).*$", r"\1", target_text)
            where = f"{network_log.name}:{number}"
            if entry.get("allowed"):
                if not host_allowed(host, rules):
                    fails.append(f"{where}: allowed {target_text}, which the allowlist does not hold")
            elif GITHUB_HOST.search(host) or "hoyle" in target_text.lower():
                fails.append(f"{where}: refused {entry.get('method')} {target_text}: the session tried to reach it")
            else:
                reviews.append(f"{where}: refused {entry.get('method')} {target_text}")
    return fails, reviews


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcripts", nargs="*", type=Path)
    parser.add_argument("--network-log", type=Path)
    parser.add_argument("--allowlist", type=Path, default=HERE / "sandbox" / "allowlist.txt")
    parser.add_argument("--target", type=Path, default=HERE / "TARGET.json")
    args = parser.parse_args(argv)
    if not args.transcripts and args.network_log is None:
        parser.print_usage(sys.stderr)
        return 2
    target = json.loads(args.target.read_text(encoding="utf-8"))
    fails, reviews = search(target, args.transcripts, args.network_log, args.allowlist)
    for line in fails:
        print(f"FAIL   {line}")
    for line in reviews:
        print(f"REVIEW {line}")
    print(f"search-transcript: {'FAIL' if fails else 'PASS'} ({len(fails)} failure(s), {len(reviews)} to review; "
          f"{len(args.transcripts)} transcript(s){', network log' if args.network_log else ''})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
