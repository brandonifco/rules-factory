#!/usr/bin/env python3
"""Everything a reviewer needs about one pull request, assembled once.

    tools/review-packet.py <pr-number> [--out DIR] [--stdout] [--base main]

Emitted by rules-factory as a managed file (decision 0029). `AGENTS.md` is the contract, and
`docs/agent-team.md` says which reviewer reads what.

**Why.** "Review this PR, figure out the context" makes every reviewer rediscover the same facts,
badly and differently: which entry this is, what the map says, what the issue asked for, what
changed, what the gate already proved. That is expensive where it is merely wasteful, and wrong
where a reviewer reconstructs the context from the diff -- which is the implementer's reading of
the rule, restated.

So the context is assembled mechanically, once, from the issue, the pull request, git and the
map. What a reviewer then adds is judgement, which is the part that cannot be assembled.

**Order matters, and the packet is built to enforce it.** A semantic reviewer reads the entry
packet (`tools/entry-packet.py`, section 3 here) and forms its own reading of the rule BEFORE the
diff (section 5). Reading the implementation first destroys the review: the code was written to be
persuasive about its own interpretation. The sections are in the order they are meant to be read.

**One commit, and every byte from it (#334).** The packet used to take the head SHA from GitHub
and then read `provenance.json` and the entries from whatever the working tree happened to hold,
so a reviewer whose checkout was elsewhere got a packet that named commit B and described commit
A. Now the reviewed commit is extracted once, with `git archive`, and every byte the packet
reports is read from that tree. The working tree is not read at all, and a commit this repository
does not have is a refusal rather than a packet about something else.

Beside the packet it writes a **manifest** -- `pr-<n>-<sha12>.review.json` -- naming the reviewed
commit, the packet's own sha256, and the digests of what was reviewed. `tools/record-verdict.py`
takes the commit to record against from that file, so a verdict cannot drift onto a later head.

**Ephemeral**, for the reason an entry packet is: written outside the repository, never committed.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`) and `git`.
"""
import argparse
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
OVERLAY = "overlay"
PROVENANCE = "provenance.json"
ENTRY_PACKET = "tools/entry-packet.py"
PACKET_ROOT_VARIABLE = "RULES_ENGINE_PACKET_ROOT"
# The marker `factory backlog --create` puts under an item's title: the one thing about an item the
# map never changes, and therefore what ties a pull request back to an entry.
ENTRY_MARKER = "<!-- rules-factory-entry:"
# The manifest a verdict is recorded from. Bumping this is a change record-verdict.py must know.
MANIFEST_VERSION = 1
DIFF_LINE_BUDGET = 2000


class Refused(Exception):
    """Something the packet cannot honestly assemble. Nothing is written."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    try:
        done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              cwd=ROOT, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise Refused(f"cannot run {command[0]} ({error}); it is how a packet reads the issue and the PR")
    if done.returncode != 0:
        raise Refused(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def git(*args):
    done = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
    if done.returncode != 0:
        raise Refused(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def policy():
    try:
        with open(ROOT / POLICY, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"{POLICY} cannot be read ({error}); it holds the labels and the review contexts")


def entry_ids(*texts):
    """Every entry id named by a marker in `texts`, in first-seen order."""
    found = []
    for text in texts:
        for part in (text or "").split(ENTRY_MARKER)[1:]:
            entry_id = part.split("-->")[0].strip()
            if entry_id and entry_id not in found:
                found.append(entry_id)
    return found


def reviewed_tree(sha, into):
    """The reviewed commit's own bytes, extracted once, with nothing of the working tree in them.

    `git archive` writes the commit's tree and no git metadata, so the result cannot be a branch,
    cannot be dirty, and cannot move while a reviewer reads it. That is the property #334 is
    about: a packet describes one immutable tree or it is refused.
    """
    try:
        done = subprocess.run(["git", "archive", "--format=tar", sha], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.SubprocessError) as error:
        raise Refused(f"cannot run git to read {sha[:12]} ({error})")
    if done.returncode != 0:
        raise Refused(f"{sha[:12]} is not a commit this repository has "
                      f"({done.stderr.decode('utf-8', 'replace').strip()}). "
                      f"`git fetch origin` first: a packet is assembled from the reviewed commit's "
                      f"own bytes, never from the working tree.")
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
        archive.extractall(into, filter="data")
    return pathlib.Path(into)


def read_at(tree, relative):
    """One file, from the reviewed tree."""
    try:
        return (tree / relative).read_text(encoding="utf-8")
    except OSError as error:
        raise Refused(f"{relative} cannot be read from the reviewed commit ({error})")


def entry_packet(entry_id, out_dir, tree, package_map=None):
    """The entry packet for `entry_id`, and its digest, or the reason there is none.

    The digest is what makes "the reviewer read the same entry the implementer did" checkable: two
    packets of the same entry at the same map version have the same sha256.
    """
    target = out_dir / f"entry-{entry_id}.md"
    # The reviewed commit's own entry-packet.py, over the reviewed commit's own map and overlay.
    # `entry-packet.py` is a managed file, so the checkout's copy may not be the one this change
    # was written against either.
    command = [sys.executable, str(tree / ENTRY_PACKET), entry_id, "--out", str(out_dir)]
    if package_map:
        command += ["--package-map", package_map]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=tree)
    if done.returncode != 0 or not target.is_file():
        return None, None, (done.stderr.strip() or "entry-packet.py produced nothing")
    data = target.read_bytes()
    return target, hashlib.sha256(data).hexdigest(), None


def section(title, body):
    return f"## {title}\n\n{body.rstrip()}\n"


def bounded_diff(base, head):
    """The diff, with a line budget: a reviewer that skims a 6000-line diff reviewed nothing."""
    text = git("diff", f"{base}...{head}")
    lines = text.splitlines()
    if len(lines) <= DIFF_LINE_BUDGET:
        return "```diff\n" + text.rstrip() + "\n```"
    kept = "\n".join(lines[:DIFF_LINE_BUDGET])
    return ("```diff\n" + kept + "\n```\n\n"
            f"**The diff is {len(lines)} lines and was cut at {DIFF_LINE_BUDGET}.** A change this size against one "
            f"issue is itself a finding: say so rather than reviewing the visible part and calling it a review. "
            f"The whole diff: `git diff {base}...{head}`.")


def build(number, base, out_dir, tree_root, sha=None, package_map=None):
    settings = policy()
    labels = settings.get("labels") or {}
    review = settings.get("review") or {}

    pull = json.loads(gh("pr", "view", str(number), "--json",
                         "number,title,body,headRefOid,headRefName,baseRefName,files,closingIssuesReferences"))
    head = sha or pull.get("headRefOid") or ""
    if not head:
        raise Refused(f"PR #{number} has no head commit, and --sha named none")
    # Everything below reads this tree and nothing reads the checkout (#334).
    tree = reviewed_tree(head, tree_root)
    issues = pull.get("closingIssuesReferences") or []
    if len(issues) != 1:
        raise Refused(f"PR #{number} closes {len(issues)} issues; the rails allow exactly one "
                      f"(`AGENTS.md`). Fix the PR body before reviewing it.")
    issue_number = issues[0]["number"]
    issue = json.loads(gh("issue", "view", str(issue_number), "--json", "number,title,body,labels,state"))
    issue_labels = [label["name"] for label in issue.get("labels") or []]

    risk = [label for label in issue_labels
            if label in (labels.get("normalRisk"), labels.get("independentRisk"))]
    independent = labels.get("independentRisk") in issue_labels

    changed = [f["path"] for f in pull.get("files") or []]
    semantic = [path for path in changed if is_semantic(path, review.get("semanticPaths") or [])]

    provenance_raw = read_at(tree, PROVENANCE)
    try:
        record = json.loads(provenance_raw)
    except ValueError as error:
        raise Refused(f"{PROVENANCE} at {head[:12]} is not readable JSON ({error})")
    entries = entry_ids(issue.get("body"), pull.get("body"))

    parts = [f"# Review packet: PR #{number} — {pull.get('title', '')}\n",
             f"Reviewed commit `{head}`. **Every byte below is read from this commit** -- not from anyone's "
             f"working tree -- and every verdict is recorded against it. If the pull request gains another "
             f"commit, this packet and any verdict recorded from it no longer apply to it.\n",
             section("1. The issue this closes",
                     f"**#{issue_number} — {issue.get('title', '')}** ({issue.get('state', '')})\n\n"
                     f"Labels: {', '.join(issue_labels) or 'none'}\n\n"
                     f"Risk: {', '.join(risk) if risk else 'no risk label — that is itself a finding'}"
                     + ("\n\n**Independent review is required for this issue.** A semantic verdict alone does not "
                        "satisfy the gate." if independent else "") +
                     f"\n\n---\n\n{issue.get('body') or '(empty)'}"),
             section("2. What the pull request claims",
                     (pull.get("body") or "(empty — the PR template is not optional)")),
             ]

    packets = []
    entry_digests = []
    if entries:
        rendered = []
        for entry_id in entries:
            path, digest, problem = entry_packet(entry_id, out_dir, tree, package_map)
            if problem:
                rendered.append(f"- `{entry_id}`: **no packet** — {problem}")
                entry_digests.append({"entryId": entry_id, "problem": problem})
            else:
                packets.append(path)
                entry_digests.append({"entryId": entry_id, "path": str(path), "sha256": digest})
                rendered.append(f"- `{entry_id}`: `{path}` (sha256 `{digest}`)")
        body = ("Read these **before** the diff. They are the map's own bytes for the entries this change names; "
                "your reading of the rule is formed from them, not from the implementation.\n\n"
                + "\n".join(rendered))
    else:
        body = ("The issue and the pull request name no entry (no `rules-factory-entry` marker). For a change to "
                "the rules surface that is a finding: the reviewer cannot check an implementation against a rule "
                "nobody named.")
    parts.append(section("3. The entries, as the map has them", body))

    parts.append(section("4. What this engine was produced from",
                         f"- map `{record['map']['packageId']}` {record['map']['version']} "
                         f"(`sha256:{record['map'].get('nupkgSha256', '')}`)\n"
                         + "".join(
                             f"- corpus `{c.get('sourceId')}`"
                             + (" (principal)" if c.get("principal") else "")
                             + f", {c.get('hashDerivation', '')}, "
                             f"content hash `{c.get('contentHash', '')}`\n"
                             for c in record.get("corpora") or [])
                         + f"- randomness declared: `{record.get('randomness')}`\n"
                         + f"- factory `{record['factory'].get('commit', '')[:12]}`"))

    overlay_diff = git("diff", f"{base}...{head}", "--", OVERLAY).rstrip()
    # The whole directory: one file per entry (#247), so a diff of `overlay` is this pull request's
    # own entry file and, if it touched more than one entry, each of the others.
    parts.append(section("5. The overlay, before and after",
                         ("```diff\n" + overlay_diff + "\n```\n\nEvery test named here carries the mutation that "
                          "makes it fail. A mutation too vague to re-run is a finding.")
                         if overlay_diff else
                         f"`{OVERLAY}/` is unchanged. A change that adds a test without naming it here, or "
                         f"implements an entry without moving its status, is a finding."))

    parts.append(section("6. What changed",
                         "\n".join(f"- `{path}`" + ("  ← semantic surface" if path in semantic else "")
                                   for path in changed) or "(no files)"))
    parts.append(section("7. The diff", bounded_diff(base, head)))

    parts.append(section("8. Determinism",
                         "Check, in the diff above: wall-clock time; ambient locale, culture or encoding; "
                         "environment-dependent ordering (dictionary or set iteration, file-system order); unseeded "
                         "randomness; hash codes or object identity in anything observable; anything that reads the "
                         "machine rather than the request. The engine's declared randomness is in section 4: an "
                         "engine declaring `none` may not reference a randomness package at all."))

    gates = [f"- `validate` — `./scripts/validate.sh full`",
             f"- `{review.get('semanticContext', '(unset)')}` — required for this change"
             if semantic else f"- `{review.get('semanticContext', '(unset)')}` — not required: nothing here touches "
                              f"the semantic surface"]
    if independent:
        chain = " → ".join(link.get("context", "?") for link in review.get("independentFallback") or [])
        gates.append(f"- one of: {chain} — required, because the issue is {labels.get('independentRisk')}")
    parts.append(section("9. What must be green before this merges",
                         "\n".join(gates) +
                         "\n\nA verdict is recorded against the reviewed commit above, and a later commit "
                         "invalidates it. Record it with `tools/record-verdict.py` and its `--packet` option, "
                         "naming the `.review.json` written beside this packet: the commit then comes from what "
                         "you actually read, and never from the pull request's current head. The chain advances "
                         "only when a provider is unavailable — never because its verdict was unwelcome."))
    manifest = {
        "manifestVersion": MANIFEST_VERSION,
        "pullRequest": number,
        "reviewedSha": head,
        "base": base,
        "provenanceSha256": hashlib.sha256(provenance_raw.encode("utf-8")).hexdigest(),
        "map": {"packageId": record["map"]["packageId"], "version": record["map"]["version"],
                "nupkgSha256": record["map"].get("nupkgSha256", "")},
        "corpora": [{"sourceId": c.get("sourceId"), "contentHash": c.get("contentHash"),
                     "principal": bool(c.get("principal"))} for c in record.get("corpora") or []],
        "entryPackets": entry_digests,
    }
    return "\n".join(parts), head, packets, manifest


def is_semantic(path, patterns):
    """Whether `path` is on the semantic surface, by the policy's glob patterns.

    `**` spans directories and `*` does not, which is what the patterns in `agent-policy.json`
    mean; fnmatch alone would treat `src/*` as matching `src/a/b.cs`.
    """
    import re
    for pattern in patterns:
        regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(regex, path):
            return True
    return False


def destination(out):
    if out is None:
        root = os.environ.get(PACKET_ROOT_VARIABLE) or os.path.join(tempfile.gettempdir(), "rules-engine-packets")
        out = os.path.join(root, ROOT.name)
    resolved = pathlib.Path(out).expanduser().resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise Refused(f"a packet is never written inside the repository ({resolved}); use --out elsewhere, or "
                      f"${PACKET_ROOT_VARIABLE}")
    return resolved


def main(argv=None):
    parser = argparse.ArgumentParser(prog="review-packet.py", description=__doc__.split("\n")[0])
    parser.add_argument("pr", type=int, help="the pull request number")
    parser.add_argument("--out", help=f"directory to write into (default: ${PACKET_ROOT_VARIABLE}, else a "
                                      f"directory beside the system temporary one)")
    parser.add_argument("--package-map", help="the restored map package's corpus-map.json, passed to "
                                                  "entry-packet.py (default: it asks MSBuild)")
    parser.add_argument("--base", default="origin/main", help="what the change is diffed against (default: origin/main)")
    parser.add_argument("--sha", help="the commit to assemble the packet from (default: the pull request's head "
                                      "as GitHub reports it). Every byte of the packet comes from this commit.")
    parser.add_argument("--stdout", action="store_true", help="write the packet to stdout, and no packet file and "
                                                              "no manifest -- so no verdict can be recorded from it")
    args = parser.parse_args(argv)

    tree_root = None
    try:
        out_dir = destination(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        tree_root = tempfile.mkdtemp(prefix="review-packet-tree-")
        text, head, packets, manifest = build(args.pr, args.base, out_dir, tree_root, args.sha, args.package_map)
        if args.stdout:
            sys.stdout.write(text)
            return 0
        target = out_dir / f"pr-{args.pr}-{head[:12]}.md"
        target.write_text(text, encoding="utf-8")
        # The manifest names the packet's own bytes, so it is written after the packet and never
        # before: a manifest whose digest does not match the file beside it is what
        # record-verdict.py refuses.
        manifest["packetPath"] = str(target)
        manifest["packetSha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        record_path = out_dir / f"pr-{args.pr}-{head[:12]}.review.json"
        record_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Refused as error:
        print(f"review-packet: REFUSED -- {error}", file=sys.stderr)
        return 1
    finally:
        if tree_root:
            shutil.rmtree(tree_root, ignore_errors=True)
    print(target)
    print(record_path)
    for path in packets:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
