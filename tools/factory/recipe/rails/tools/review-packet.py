#!/usr/bin/env python3
"""Everything a reviewer needs about one pull request, assembled once.

    tools/review-packet.py <pr-number> [--package-map PATH] [--out DIR] [--stdout] [--base main]

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

**What a written packet is worth.** File output is what a verdict is recorded from, so a packet
that names an entry is written only when its entry packets exist and were built from map bytes
checked against the digest the reviewed commit declares -- which is what `--package-map` supplies.
Otherwise it is refused, and `--stdout` remains for reading a packet whose evidence is unbound: it
writes nothing, so nothing can be recorded from it (#372).

**A refusal leaves nothing.** Every file, the output directory included, is written after the last
thing that can refuse; until then the packet is assembled in this run's own private directory.

**Ephemeral**, for the reason an entry packet is: written outside the repository, never committed.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`) and `git`.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
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
DIFF_LINE_BUDGET = 2000


class Refused(Exception):
    """Something the packet cannot honestly assemble. Nothing is written."""


def one_map(record):
    """The one map package a record names, or {} when it names none.

    A review packet carries the bytes of the map its entries came from. An engine composed of
    several (rules-factory 0067) is refused where the packet is assembled, above; this is the
    reader for the ordinary case and it never guesses which of several.
    """
    maps = [m for m in record.get("maps") or [] if isinstance(m, dict)]
    return maps[0] if len(maps) == 1 else {}


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


def policy(root):
    try:
        with open(root / POLICY, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"{POLICY} cannot be read at reviewed commit ({error}); it holds the labels and the review contexts")


def reviewed_snapshot(head):
    """A detached worktree containing exactly `head`, plus the private directory that owns it.

    The parent is this run's own scratch space, and everything the assembly produces is built
    there first: the map copy the entry packets are read from, and the entry packets themselves.
    Nothing reaches the caller's `--out` until every refusal has passed, so a refused packet
    leaves nothing behind (#371).
    """
    parent = pathlib.Path(tempfile.mkdtemp(prefix="rules-engine-review-"))
    snapshot = parent / "reviewed"
    try:
        git("worktree", "add", "--detach", "--quiet", str(snapshot), head)
    except Exception:
        shutil.rmtree(parent, ignore_errors=True)
        raise
    return parent, snapshot


def remove_reviewed_snapshot(parent, snapshot):
    """Remove the temporary worktree on both success and failure."""
    subprocess.run(["git", "worktree", "remove", "--force", str(snapshot)], cwd=ROOT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(parent, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=ROOT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def entry_ids(*texts):
    """Every entry id named by a marker in `texts`, in first-seen order."""
    found = []
    for text in texts:
        for part in (text or "").split(ENTRY_MARKER)[1:]:
            entry_id = part.split("-->")[0].strip()
            if entry_id and entry_id not in found:
                found.append(entry_id)
    return found


def map_read_once(package_map, record, head, work_dir):
    """The map bytes the entry packets will be built from: read once, checked, and kept (#356, #371).

    The overlay comes from the reviewed tree. The map does not: `--package-map` is a host path, and
    without this the packet's section 3 would say "the reviewed commit's own map/overlay bytes"
    while the map was whatever the caller pointed at. `provenance.json` records the sha256 of the
    exact `corpus-map.json` the engine was produced from, under `map.files[role="map"]`, so there
    is something precise to be held to rather than a version label.

    **One read, not two opens of a path.** The digest check and the `entry-packet.py` subprocess
    used to open `--package-map` separately, so a file replaced between them gave entry packets
    built from map B under the checked digest of map A -- the substitution #356 exists to stop,
    moved from "never checked" to "checked, then not used" (#371). The bytes that were hashed are
    therefore written into this run's own private directory and the subprocess is handed that copy.
    The copy is not put under the packet's `--out`: that is a shared, predictable location
    (`$RULES_ENGINE_PACKET_ROOT`, or a directory beside the system temporary one), and a copy there
    would be open to the same substitution. `mkdtemp`'s directory is private to this process, and
    the same `finally` that removes the reviewed snapshot removes it.

    Returns the digest of the bytes that were read and the path of the copy holding exactly them.
    """
    maps = [m for m in record.get("maps") or [] if isinstance(m, dict)]
    if len(maps) > 1:
        raise Refused(f"{PROVENANCE} at {head[:12]} names {len(maps)} map packages; a review packet "
                      f"carries the bytes of the one map its entries came from, and this tool "
                      f"cannot yet say which of several that is (rules-factory 0067)")
    declared = [part.get("sha256") for part in (maps[0] if maps else {}).get("files") or []
                if part.get("role") == "map"]
    if len(declared) != 1 or not declared[0]:
        raise Refused(f"{PROVENANCE} at {head[:12]} does not record the digest of the map it was "
                      f"produced from (`map.files[role=\"map\"]`), so the bytes an entry packet is "
                      f"built from cannot be checked against it")
    try:
        with open(package_map, "rb") as handle:
            data = handle.read()
    except OSError as error:
        raise Refused(f"--package-map {package_map} cannot be read ({error})")
    read = hashlib.sha256(data).hexdigest()
    if read != declared[0]:
        raise Refused(f"--package-map {package_map} is not the map commit {head[:12]} was produced "
                      f"from: it hashes to {read[:12]} and {PROVENANCE} declares {declared[0][:12]}. "
                      f"An entry packet built from it would be evidence the reviewed commit never "
                      f"carried, and section 3 tells the reviewer it is the commit's own bytes. "
                      f"Restore the package the engine declares, or review the commit that declares "
                      f"this map.")
    copy = work_dir / "checked-corpus-map.json"
    copy.write_bytes(data)
    return read, copy


def entry_packet(entry_id, work_dir, source_root, package_map=None):
    """The entry packet for `entry_id`, generated from the exact reviewed tree.

    Built into this run's private directory and returned as bytes; `main()` writes it out only
    once the packet as a whole is assembled, so a later refusal leaves no half a packet behind.

    The digest is what makes "the reviewer read the same entry the implementer did" checkable: two
    packets of the same entry at the same reviewed commit have the same sha256.
    """
    target = work_dir / f"entry-{entry_id}.md"
    command = [sys.executable, str(source_root / ENTRY_PACKET), entry_id, "--out", str(work_dir)]
    if package_map:
        command += ["--package-map", str(package_map)]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=source_root)
    if done.returncode != 0 or not target.is_file():
        return None, (done.stderr.strip() or "entry-packet.py produced nothing")
    data = target.read_bytes()
    return {"entryId": entry_id, "name": target.name, "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": data}, None


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


def build(number, base, package_map=None, recordable=True):
    pull = json.loads(gh("pr", "view", str(number), "--json",
                         "number,title,body,headRefOid,headRefName,baseRefName,baseRefOid,files,closingIssuesReferences"))
    head = pull.get("headRefOid") or ""
    if not head:
        raise Refused(f"PR #{number} has no head commit")
    base_oid = pull.get("baseRefOid")
    base_sha = base_oid or git("rev-parse", f"{base}^{{commit}}").strip()
    if package_map:
        package_map = str(pathlib.Path(package_map).expanduser().resolve())

    issues = pull.get("closingIssuesReferences") or []
    if len(issues) != 1:
        raise Refused(f"PR #{number} closes {len(issues)} issues; the rails allow exactly one "
                      f"(`AGENTS.md`). Fix the PR body before reviewing it.")
    issue_number = issues[0]["number"]
    issue = json.loads(gh("issue", "view", str(issue_number), "--json", "number,title,body,labels,state"))
    issue_labels = [label["name"] for label in issue.get("labels") or []]

    parent, snapshot = reviewed_snapshot(head)
    try:
        settings = policy(snapshot)
        labels = settings.get("labels") or {}
        review = settings.get("review") or {}
        risk = [label for label in issue_labels
                if label in (labels.get("normalRisk"), labels.get("independentRisk"))]
        independent = labels.get("independentRisk") in issue_labels

        changed = [f["path"] for f in pull.get("files") or []]
        semantic = [path for path in changed if is_semantic(path, review.get("semanticPaths") or [])]

        try:
            provenance_bytes = (snapshot / PROVENANCE).read_bytes()
            record = json.loads(provenance_bytes.decode("utf-8"))
            policy_bytes = (snapshot / POLICY).read_bytes()
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise Refused(f"reviewed commit {head[:12]} does not carry readable review context ({error})")

        entries = entry_ids(issue.get("body"), pull.get("body"))

        # Before any entry packet is built, and before anything is written: an entry packet made
        # from the wrong map is the one artifact a semantic reviewer is told to read first.
        map_read, checked_map = (map_read_once(package_map, record, head, parent) if package_map
                                 else (None, None))
        if recordable and entries and not map_read:
            raise Refused(f"this packet names {len(entries)} entr" + ("y" if len(entries) == 1 else "ies")
                          + f" ({', '.join(entries)}) and no --package-map was given, so the map its entry "
                          f"packets would be built from cannot be held to the digest commit {head[:12]} "
                          f"declares. Entry evidence the reviewed commit is not bound to cannot carry a "
                          f"verdict (#372): supply --package-map with the restored package's "
                          f"corpus-map.json, or read this packet with --stdout, which writes no identity.")

        parts = [f"# Review packet: PR #{number} — {pull.get('title', '')}\n",
                 f"Head commit `{head}`. Base commit `{base_sha}`. **Every verdict is recorded against this "
                 f"exact reviewed commit and this packet's identity.** If the pull request gains another commit, "
                 f"regenerate the packet and review the new bytes.\n",
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
        if entries:
            rendered = []
            for entry_id in entries:
                packet, problem = entry_packet(entry_id, parent, snapshot, checked_map)
                if problem:
                    if recordable:
                        raise Refused(f"no entry packet for `{entry_id}`: {problem}. A semantic reviewer is "
                                      f"told to read the entry packets before the diff, so a packet missing "
                                      f"one cannot carry a verdict (#372). Fix what the message names, or "
                                      f"read this packet with --stdout, which writes no identity.")
                    rendered.append(f"- `{entry_id}`: **no packet** — {problem}")
                else:
                    packets.append(packet)
                    rendered.append(f"- `{entry_id}`: `{packet['name']}` (sha256 `{packet['sha256']}`)")
            provenance_of_map = (
                "They are the reviewed commit's own map and overlay bytes: the overlay came out of the commit, "
                "and the map was checked against the digest the commit's `provenance.json` declares, once, and "
                "the entry packets were built from those exact bytes."
                if map_read else
                "The overlay came out of the reviewed commit. **The map did not: it was resolved by MSBuild "
                "inside the reviewed tree and its identity was NOT VERIFIED against the digest the commit's "
                "`provenance.json` declares** (#356). This packet is therefore for reading only: no identity "
                "was written for it and no verdict can be recorded from it (#372). Supply `--package-map` "
                "with the restored package's `corpus-map.json` to have the map checked.")
            body = ("Read these **before** the diff. " + provenance_of_map + " Your reading of the rule is formed "
                    "from them, not from the implementation.\n\n" + "\n".join(rendered))
        else:
            body = ("The issue and the pull request name no entry (no `rules-factory-entry` marker). For a change to "
                    "the rules surface that is a finding: the reviewer cannot check an implementation against a rule "
                    "nobody named.")
        parts.append(section("3. The entries, as the map has them", body))

        parts.append(section("4. What this engine was produced from",
                             "".join(
                                 f"- map `{m.get('packageId')}` {m.get('version')} "
                                 f"(`sha256:{m.get('nupkgSha256', '')}`)\n"
                                 for m in record.get("maps") or [])
                             + "".join(
                                 f"- corpus `{corpus.get('sourceId')}`"
                                 + (" (principal)" if corpus.get("principal") else "")
                                 + f", {corpus.get('hashDerivation', '')}, "
                                 f"content hash `{corpus.get('contentHash', '')}`\n"
                                 for corpus in record.get("corpora") or [])
                             + f"- randomness declared: `{record.get('randomness')}`\n"
                             + f"- factory `{record['factory'].get('commit', '')[:12]}`"))

        overlay_diff = git("diff", f"{base_sha}...{head}", "--", OVERLAY).rstrip()
        parts.append(section("5. The overlay, before and after",
                             ("```diff\n" + overlay_diff + "\n```\n\nEvery test named here carries the mutation that "
                              "makes it fail. A mutation too vague to re-run is a finding.")
                             if overlay_diff else
                             f"`{OVERLAY}/` is unchanged. A change that adds a test without naming it here, or "
                             f"implements an entry without moving its status, is a finding."))

        parts.append(section("6. What changed",
                             "\n".join(f"- `{path}`" + ("  ← semantic surface" if path in semantic else "")
                                       for path in changed) or "(no files)"))
        parts.append(section("7. The diff", bounded_diff(base_sha, head)))

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
                             "\n\nA verdict is recorded from this packet's machine-readable identity. A later commit invalidates "
                             "it. The chain advances only when a provider is unavailable — never because its verdict "
                             "was unwelcome."))

        manifest_name = f"pr-{number}-{head[:12]}.review.json"
        parts.append(section("10. Recording this review",
                             f"When written to disk, the machine-readable identity for this packet is `{manifest_name}`. "
                             f"Record a verdict with `tools/record-verdict.py --pr {number} --packet <path-to-{manifest_name}> "
                             f"--reviewer <id> --verdict pass|fail`. The recorder verifies this packet and its entry "
                             f"packet digests and refuses if PR #{number} has moved."))

        # A PR can move while the packet is being assembled. A packet for the earlier immutable commit is
        # internally honest, but handing it to a reviewer after the branch already moved invites a stale review.
        after = json.loads(gh("pr", "view", str(number), "--json", "headRefOid,baseRefOid"))
        after_head = after.get("headRefOid") or ""
        if after_head != head:
            raise Refused(f"PR #{number} moved while its packet was being assembled "
                          f"({head[:12]} -> {after_head[:12]}); regenerate from the new head")
        after_base = after.get("baseRefOid")
        if base_oid and after_base and after_base != base_oid:
            raise Refused(f"PR #{number}'s base moved while its packet was being assembled "
                          f"({base_oid[:12]} -> {after_base[:12]}); regenerate")

        context = {
            "policy": {
                "path": POLICY,
                "sha256": hashlib.sha256(policy_bytes).hexdigest(),
                "semanticContext": review.get("semanticContext"),
                "independentFallback": review.get("independentFallback") or [],
            },
            "provenance": {
                "path": PROVENANCE,
                "sha256": hashlib.sha256(provenance_bytes).hexdigest(),
            },
            "map": {
                "packageId": one_map(record).get("packageId"),
                "version": one_map(record).get("version"),
                "nupkgSha256": one_map(record).get("nupkgSha256", ""),
                # What the commit declares, and what was actually read. Recording only the first
                # is what let two packets with different entry evidence carry one identity (#356).
                "declaredSha256": next((part.get("sha256") for part in one_map(record).get("files") or []
                                        if part.get("role") == "map"), ""),
                # Null, never the declared digest, when nothing was checked: writing the declared
                # value here would be the very substitution of a claim for a fact this closes.
                # A written identity carries a digest here whenever it names an entry packet, and
                # `record-verdict.py` refuses one that does not (#372).
                "readSha256": map_read,
                "readFrom": ("--package-map, checked against the reviewed commit, and the entry packets "
                             "built from those exact bytes" if map_read
                             else "MSBuild inside the reviewed tree -- NOT VERIFIED" if entries
                             else "not read: this packet names no entry, so no entry packet was built"),
            },
        }
        return "\n".join(parts), head, base_sha, packets, context
    finally:
        remove_reviewed_snapshot(parent, snapshot)


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
                                                  "entry-packet.py (default: it asks MSBuild in the reviewed snapshot)")
    parser.add_argument("--base", default="origin/main",
                        help="fallback local base ref when GitHub supplies no base SHA (default: origin/main)")
    parser.add_argument("--stdout", action="store_true",
                        help="display the human packet only; no review-packet identity file is written")
    args = parser.parse_args(argv)

    try:
        # Resolved and judged, but not created: a packet that is refused writes nothing, and a
        # directory is a write (#371). Everything below is built in the run's own private
        # directory first and lands here only once there is nothing left to refuse.
        out_dir = destination(args.out)
        packet_text, head, base_sha, packets, context = build(args.pr, args.base, args.package_map,
                                                              recordable=not args.stdout)
        if args.stdout:
            sys.stdout.write(packet_text)
            return 0
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"pr-{args.pr}-{head[:12]}.md"
        target.write_text(packet_text, encoding="utf-8")
        for packet in packets:
            (out_dir / packet["name"]).write_bytes(packet["bytes"])
        manifest = {
            "reviewPacketFormat": 1,
            "pullRequest": args.pr,
            "reviewedCommit": head,
            "baseCommit": base_sha,
            "reviewPacket": {
                "path": target.name,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            },
            "reviewContext": context,
            "entryPackets": [
                {"entryId": packet["entryId"], "path": packet["name"], "sha256": packet["sha256"]}
                for packet in packets
            ],
        }
        manifest_target = out_dir / f"pr-{args.pr}-{head[:12]}.review.json"
        manifest_target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Refused as error:
        print(f"review-packet: REFUSED -- {error}", file=sys.stderr)
        return 1
    print(target)
    for packet in packets:
        print(out_dir / packet["name"])
    print(manifest_target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
