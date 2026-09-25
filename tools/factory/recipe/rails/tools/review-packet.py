#!/usr/bin/env python3
"""Everything a reviewer needs about one pull request, assembled once.

    tools/review-packet.py <pr-number> [--role ROLE] [--package-map PATH] [--out DIR] [--stdout]

Emitted by rules-factory as a managed file (decision 0029). `AGENTS.md` is the contract, and
`docs/agent-team.md` says which reviewer reads what.

**Why.** "Review this PR, figure out the context" makes every reviewer rediscover the same facts,
badly and differently: which entry this is, what the map says, what the issue asked for, what
changed, what the gate already proved. That is expensive where it is merely wasteful, and wrong
where a reviewer reconstructs the context from the diff -- which is the implementer's reading of
the rule, restated.

So the context is assembled mechanically, once, from the issue, the pull request, git and the
map. What a reviewer then adds is judgement, which is the part that cannot be assembled.

**A reviewer is given what its role judges, and not the other role's material.** `--role` cuts
the packet three ways, and the whole packet is still the default:

  * `structural` -- what the repository steward checks: scope, ownership, evidence, determinism,
    citation and documents. It carries the pull request's claim in full, because "the template is
    filled with actual output rather than a claim" is its check, and the changed paths **with the
    ownership class of each**, because "no generated or managed file was hand-edited" is the first
    one. It carries **no entry packet**: the steward is forbidden to judge whether the
    implementation reads the rule correctly (`docs/agent-team.md`), so the map's bytes are not its
    to weigh -- and without them this role needs no restored map package to read a packet at all.
  * `semantic` -- the entry packets first, then the acceptance criteria, then the semantic surface
    and its diff. It does **not** carry the pull request body. That body is the implementer's case
    for its own reading of the rule, and this reviewer's charter tells it not to accept that case
    as an answer; handing it over first, several pages of it, is the anchoring this role exists to
    resist.
  * `independent` -- the same assignment and the current bytes in full, with no prior reviewer's
    conclusion, no repair discussion and no pull request narrative, and a section saying so. The
    value of this verdict is independence, and independence is a property of what it was given.

**The role is part of the identity.** The `.review.json` names the role the packet was cut for and
hashes the bytes that role was handed, and `tools/record-verdict.py` refuses a verdict the role
cannot carry: a semantic verdict formed on a packet with no entry packets in it is exactly the
unbound entry evidence #372 refuses, arriving by another door. A structural packet carries no
verdict at all, because this engine's policy configures no context for one -- the steward reports
findings, and the orchestrator decides which of them block.

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
import re
import shutil
import subprocess
import sys
import tempfile

# The ownership class beside each changed path comes from the reviewed commit's vendored
# scripts/factory/ownership.py, and an imported module leaves its bytecode beside it. The loader
# reads this flag when the import happens, so it belongs here and not beside the import (#194).
sys.dont_write_bytecode = True

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
NOT_CHECKED = "NOT CHECKED"
#: The three cuts, and the whole packet. `ALL` is what a caller that names no role gets, and is
#: what every caller before `--role` existed got, byte for byte where the sections are the same.
STRUCTURAL, SEMANTIC, INDEPENDENT, ALL = "structural", "semantic", "independent", "all"
ROLES = (STRUCTURAL, SEMANTIC, INDEPENDENT)
#: Which roles read the entry packets -- and therefore which need the map held to the reviewed
#: commit's declared digest. The steward does not judge the rule, so it is given no reading of it.
READS_ENTRIES = frozenset({SEMANTIC, INDEPENDENT, ALL})
#: Which roles are given the pull request's own case for itself. The semantic and independent
#: reviewers are not: their charters say the map decides, never the implementer's explanation.
READS_THE_CLAIM = frozenset({STRUCTURAL, ALL})
#: The sections of an issue each role is given when the issue has them. The whole body is the
#: fallback, because starving a reviewer is worse than over-feeding one, and the packet says which
#: happened.
ISSUE_SECTIONS = {
    STRUCTURAL: ("Scope, and what it deliberately does not do", "Acceptance criteria",
                 "Required evidence"),
    SEMANTIC: ("The rule, if this is rules work", "Acceptance criteria", "Required evidence"),
    INDEPENDENT: ("The rule, if this is rules work", "Acceptance criteria", "Required evidence"),
}


class Refused(Exception):
    """Something the packet cannot honestly assemble. Nothing is written."""


#: Why a map that is not the one the reviewed commit declares is refused rather than used. One
#: sentence, shared by every shape of the refusal, so a composed engine and a single-map one give
#: a reader the same reason and it cannot be reworded in one place and not the other.
SUBSTITUTION = ("An entry packet built from it would be evidence the reviewed commit never carried, "
                "and section 3 tells the reviewer it is the commit's own bytes.")


def map_packages(record):
    """Every map package a record names, in the order it names them.

    A review packet carries the bytes of the maps its entries came from -- all of them. An engine
    composed of several (rules-factory 0067) has one per constituent, and the record names them in
    package id order, because a record of a composition is a function of its inputs and not of the
    order they were given in. One map is the ordinary case and is a list of one.
    """
    return [m for m in record.get("maps") or [] if isinstance(m, dict)]


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


def maps_read_once(package_maps, record, head, work_dir):
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

    **An engine composed of several packages is several maps, and every one of them is checked**
    (rules-factory 0067). The pairing is by digest, never by the order the paths were given in:
    `provenance.json` records the sha256 of each package's map, and a file that hashes to one *is*
    that package's. So a composed engine cannot become the way an unchecked map reaches a
    reviewer, which it would be if one of several were taken on trust or matched by position.

    Returns {package id: the digest read} and the paths of the copies holding exactly those bytes,
    one per package, in the record's own order.
    """
    packages = map_packages(record)
    if not packages:
        raise Refused(f"{PROVENANCE} at {head[:12]} names no map package, so the bytes an entry "
                      f"packet is built from cannot be checked against it")
    declared = {}
    for package in packages:
        digests = [part.get("sha256") for part in package.get("files") or []
                   if isinstance(part, dict) and part.get("role") == "map"]
        if len(digests) != 1 or not digests[0]:
            raise Refused(f"{PROVENANCE} at {head[:12]} does not record the digest of "
                          f"{package.get('packageId')}'s map (`maps[].files[role=\"map\"]`), so the "
                          f"bytes an entry packet is built from cannot be checked against it")
        declared[digests[0]] = package
    read, unknown = {}, []
    for index, package_map in enumerate(package_maps):
        try:
            with open(package_map, "rb") as handle:
                data = handle.read()
        except OSError as error:
            raise Refused(f"--package-map {package_map} cannot be read ({error})")
        digest = hashlib.sha256(data).hexdigest()
        if digest not in declared:
            unknown.append((package_map, digest))
            continue
        copy = work_dir / f"checked-corpus-map-{index}.json"
        copy.write_bytes(data)
        read[declared[digest]["packageId"]] = (digest, copy)
    missing = [p for p in packages if p["packageId"] not in read]
    if missing or unknown:
        # The single-package case is the ordinary one and reads as one sentence naming both
        # digests, which is what a reader compares. Several packages cannot be one sentence, so
        # each line says the same thing about one package: what it declares, and what was given.
        declared_for = {p["packageId"]: digest for digest, p in declared.items()}
        if len(packages) == 1 and len(unknown) == 1:
            path, digest = unknown[0]
            raise Refused(f"--package-map {path} is not the map commit {head[:12]} was produced "
                          f"from: it hashes to {digest[:12]} and {PROVENANCE} declares "
                          f"{declared_for[packages[0]['packageId']][:12]}. "
                          + SUBSTITUTION + " Restore the package the engine declares, or review "
                          "the commit that declares this map.")
        lines = [f"the --package-map file(s) given are not the map(s) commit {head[:12]} was produced from:"]
        for package in missing:
            lines.append(f"  - {package['packageId']} declares "
                         f"{declared_for[package['packageId']][:12]} and nothing given hashes to it")
        for path, digest in unknown:
            lines.append(f"  - {path} hashes to {digest[:12]}, which this engine's provenance does not record")
        raise Refused("\n".join(lines) + "\n" + SUBSTITUTION
                      + f" Restore the {len(packages)} package(s) this engine declares and pass one "
                        f"--package-map each, or review the commit that declares these maps.")
    return ({package_id: digest for package_id, (digest, _) in read.items()},
            [read[p["packageId"]][1] for p in packages])


def entry_packet(entry_id, work_dir, source_root, package_maps=()):
    """The entry packet for `entry_id`, generated from the exact reviewed tree.

    Built into this run's private directory and returned as bytes; `main()` writes it out only
    once the packet as a whole is assembled, so a later refusal leaves no half a packet behind.

    The digest is what makes "the reviewer read the same entry the implementer did" checkable: two
    packets of the same entry at the same reviewed commit have the same sha256.
    """
    target = work_dir / f"entry-{entry_id}.md"
    command = [sys.executable, str(source_root / ENTRY_PACKET), entry_id, "--out", str(work_dir)]
    for package_map in package_maps:
        command += ["--package-map", str(package_map)]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=source_root)
    if done.returncode != 0 or not target.is_file():
        return None, (done.stderr.strip() or "entry-packet.py produced nothing")
    data = target.read_bytes()
    return {"entryId": entry_id, "name": target.name, "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": data}, None


def packet_suffix(role):
    """What distinguishes one cut's files from another's in a directory that holds several.

    The whole packet keeps the name it always had -- a caller that names no role gets the file it
    got before `--role` existed -- and each cut adds its own, so three reviews of one head can sit
    side by side without one overwriting another.
    """
    return "" if role == ALL else f"-{role}"


def section(title, body):
    return f"## {title}\n\n{body.rstrip()}\n"


def ownership_of(snapshot, record):
    """`path -> ownership class`, from the reviewed commit's own vendored table, or `(None, why)`.

    The steward's first check is that no generated or managed file was hand-edited, and until this
    existed the packet handed it a list of paths and left it to recognise them. The table is the
    one `factory produce` wrote the files by, read from the **reviewed** tree, so the packet cannot
    classify by a newer table than the commit was written under.
    """
    name = (record.get("engine") or {}).get("name")
    if not isinstance(name, str) or not name:
        return None, f"{PROVENANCE} at the reviewed commit names no engine"
    sys.path.insert(0, str(snapshot / "scripts" / "factory"))
    try:
        import ownership  # noqa: E402  (the factory's ownership table, as this commit vendored it)
    except ImportError as error:
        return None, f"scripts/factory/ownership.py is not importable at the reviewed commit ({error})"

    def classify(path):
        try:
            if getattr(ownership, "retired", None) is not None and ownership.retired(path, name) is not None:
                return "retired"
            row = ownership.classify(path, name)
        except Exception as error:  # noqa: BLE001  (an unclassifiable path is reported, never guessed)
            return f"unclassifiable ({error})"
        return row.cls if row else "not in the table"

    return classify, None


def role_diff(base, head, paths):
    """The bounded diff of exactly `paths`. An empty list is an empty diff, never the whole one."""
    if not paths:
        return None
    text = git("diff", f"{base}...{head}", "--", *paths)
    lines = text.splitlines()
    if len(lines) <= DIFF_LINE_BUDGET:
        return "```diff\n" + text.rstrip() + "\n```"
    return ("```diff\n" + "\n".join(lines[:DIFF_LINE_BUDGET]) + "\n```\n\n"
            f"**This diff is {len(lines)} lines and was cut at {DIFF_LINE_BUDGET}.** A change this size "
            f"against one issue is itself a finding: say so rather than reviewing the visible part and "
            f"calling it a review. The whole of it: `git diff {base}...{head} -- <the paths above>`.")


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


def named_sections(body, wanted):
    """`## <heading>` -> text, for the headings in `wanted` the body actually has, in that order.

    A section the issue does not carry is absent rather than empty, so the packet can say the
    issue states none instead of printing a blank heading over it.
    """
    out, current = {}, None
    for line in (body or "").splitlines():
        heading = re.match(r"^#{2,3}\s+(.*?)\s*$", line)
        if heading:
            current = heading.group(1) if heading.group(1) in wanted else None
            if current:
                out[current] = []
            continue
        if current:
            out[current].append(line)
    kept = {name: "\n".join(lines).strip() for name, lines in out.items()}
    return {name: kept[name] for name in wanted if kept.get(name)}


def build(number, base, package_maps=(), recordable=True, role=ALL):
    pull = json.loads(gh("pr", "view", str(number), "--json",
                         "number,title,body,headRefOid,headRefName,baseRefName,baseRefOid,files,closingIssuesReferences"))
    head = pull.get("headRefOid") or ""
    if not head:
        raise Refused(f"PR #{number} has no head commit")
    base_oid = pull.get("baseRefOid")
    base_sha = base_oid or git("rev-parse", f"{base}^{{commit}}").strip()
    package_maps = [str(pathlib.Path(path).expanduser().resolve()) for path in package_maps or []]

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
        maps_read, checked_maps = (maps_read_once(package_maps, record, head, parent) if package_maps
                                   else ({}, []))
        recorded_maps = map_packages(record)
        if recordable and entries and role in READS_ENTRIES and not maps_read:
            raise Refused(f"this packet names {len(entries)} entr" + ("y" if len(entries) == 1 else "ies")
                          + f" ({', '.join(entries)}) and no --package-map was given, so the "
                          + ("map" if len(recorded_maps) < 2 else f"{len(recorded_maps)} maps")
                          + f" its entry packets would be built from cannot be held to the digest"
                          + ("" if len(recorded_maps) < 2 else "s")
                          + f" commit {head[:12]} declares. Entry evidence the reviewed commit is not "
                          f"bound to cannot carry a verdict (#372): supply "
                          + ("--package-map with the restored package's corpus-map.json"
                             if len(recorded_maps) < 2 else
                             f"one --package-map per package, with each restored package's corpus-map.json "
                             f"({', '.join(m['packageId'] for m in recorded_maps)})")
                          + ", or read this packet with --stdout, which writes no identity.")

        wanted = ISSUE_SECTIONS.get(role)
        cut = named_sections(issue.get("body"), wanted) if wanted else {}
        if wanted and cut:
            assignment = ("\n\n".join(f"### {name}\n\n{text}" for name, text in cut.items())
                          + f"\n\nThese are the sections of #{issue_number} your role is held to. The rest of "
                            f"the body is the case for the work; read the issue in full if a finding turns on "
                            f"something this leaves out.")
        elif wanted:
            assignment = (f"#{issue_number} carries none of the sections this role is given "
                          f"({', '.join(wanted)}), so its whole body is below. An issue with no acceptance "
                          f"criteria is itself a finding.\n\n---\n\n{issue.get('body') or '(empty)'}")
        else:
            assignment = f"---\n\n{issue.get('body') or '(empty)'}"

        parts = [f"# Review packet ({role}): PR #{number} — {pull.get('title', '')}\n",
                 f"Head commit `{head}`. Base commit `{base_sha}`. **Every verdict is recorded against this "
                 f"exact reviewed commit and this packet's identity.** If the pull request gains another commit, "
                 f"regenerate the packet and review the new bytes.\n",
                 section("1. The issue this closes",
                         f"**#{issue_number} — {issue.get('title', '')}** ({issue.get('state', '')})\n\n"
                         f"Labels: {', '.join(issue_labels) or 'none'}\n\n"
                         f"Risk: {', '.join(risk) if risk else 'no risk label — that is itself a finding'}"
                         + ("\n\n**Independent review is required for this issue.** A semantic verdict alone does not "
                            "satisfy the gate." if independent else "") +
                         f"\n\n{assignment}"),
                 ]
        if role in READS_THE_CLAIM:
            parts.append(section("2. What the pull request claims",
                                 (pull.get("body") or "(empty — the PR template is not optional)")))
        elif role == INDEPENDENT:
            parts.append(section("2. What you were not given",
                                 "No earlier reviewer's conclusion, no finding anybody else raised, no repair "
                                 "discussion, and not the pull request's own narrative. The value of an "
                                 "independent verdict is independence, and independence is a property of what "
                                 "the reviewer was handed, so this is a section rather than an omission: if you "
                                 "find yourself reasoning about what another reviewer thought, you are reasoning "
                                 "about something that is not here.\n\nWhat you have is the assignment — the map's "
                                 "own bytes and the issue's acceptance criteria — and the current bytes of the "
                                 "change, whole."))
        else:
            parts.append(section("2. What you were not given",
                                 "Not the pull request body. It is the implementer's case for its own reading of "
                                 "the rule, written to be persuasive about it, and your charter says the map and "
                                 "the entry's evidence decide — never the implementer's explanation. The claim "
                                 "that the pull request is properly filled in is the structural review's, and it "
                                 "runs before you.\n\nWhat the pull request says it closes is section 1; what it "
                                 "actually did is sections 5 to 7."))

        packets = []
        if role not in READS_ENTRIES:
            parts.append(section("3. The entries this names",
                                 ("\n".join(f"- `{entry_id}`" for entry_id in entries)
                                  + "\n\nThe ids only. Whether the change **cites** its entry and locator is "
                                    "yours to check; whether it reads the rule correctly is not, so the map's "
                                    "bytes are not here (`docs/agent-team.md`). That review runs after you, "
                                    "on a packet built for it."
                                  if entries else
                                  "The issue and the pull request name no entry (no `rules-factory-entry` "
                                  "marker). For a change to the rules surface that is a finding: the next "
                                  "reviewer cannot check an implementation against a rule nobody named.")))
        elif entries:
            rendered = []
            for entry_id in entries:
                packet, problem = entry_packet(entry_id, parent, snapshot, checked_maps)
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
            several = len(recorded_maps) > 1
            provenance_of_map = (
                "They are the reviewed commit's own map and overlay bytes: the overlay came out of the commit, "
                + ("and each of the " + str(len(recorded_maps)) + " maps this engine is composed of was checked"
                   if several else "and the map was checked")
                + " against the digest the commit's `provenance.json` declares, once, and "
                "the entry packets were built from those exact bytes."
                if maps_read else
                "The overlay came out of the reviewed commit. **The map did not: it was resolved by MSBuild "
                "inside the reviewed tree and its identity was NOT VERIFIED against the digest the commit's "
                "`provenance.json` declares** (#356). This packet is therefore for reading only: no identity "
                "was written for it and no verdict can be recorded from it (#372). Supply `--package-map` "
                + ("once per composed package, with each restored package's `corpus-map.json`, "
                   if several else "with the restored package's `corpus-map.json` ")
                + "to have the map checked.")
            body = ("Read these **before** the diff. " + provenance_of_map + " Your reading of the rule is formed "
                    "from them, not from the implementation.\n\n" + "\n".join(rendered))
            parts.append(section("3. The entries, as the map has them", body))
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

        classify, why = ownership_of(snapshot, record)
        def owned(path):
            return f"  [{NOT_CHECKED.lower()}]" if classify is None else f"  [{classify(path)}]"

        if role == SEMANTIC:
            listed = semantic
            rest = [path for path in changed if path not in semantic]
            # Named, not counted. A count is not something a reviewer can disagree with, and the
            # sentence under it invites exactly that disagreement -- so the file that decides what
            # this cut contains would have reached the reviewer as the number 1 (#475). Paths are
            # cheap; it is the diff this cut exists to withhold, and it still withholds it.
            withheld = ("\n\nChanged and **not** on that surface, by name, with their diff in the "
                        "structural cut and not here:\n\n"
                        + "\n".join(f"- `{path}`"
                                    + ("  ← **this file decides what is on the semantic surface**, and "
                                       "therefore what this packet contains" if path == POLICY else "")
                                    for path in rest)
                        + "\n\nA document, a workflow or a rail cannot make the engine answer a rule "
                          "differently, which is why their diff is the structural review's. If you believe "
                          "one of these can, that is a finding about `semanticPaths` in "
                          f"`{POLICY}` -- and if {POLICY} is in the list above, this packet was cut by "
                          "a rule the same pull request is changing."
                        if rest else
                        "\n\nEvery changed file is on that surface; nothing was withheld from this cut.")
            heading = ("6. What changed on the semantic surface",
                       ("\n".join(f"- `{path}`" for path in listed) + withheld
                        if listed else
                        "**Nothing here touches the semantic surface** this engine's policy declares, so no "
                        "semantic verdict is required for this change (section 9). If you think that is wrong, "
                        f"the finding is about `semanticPaths` in `{POLICY}`."
                        + withheld))
        else:
            listed = changed
            heading = ("6. What changed",
                       ("\n".join(f"- `{path}`{owned(path)}"
                                  + ("  ← semantic surface" if path in semantic else "")
                                  for path in changed)
                        + ("\n\nThe class in brackets beside each path is the reviewed commit's own vendored ownership "
                           "table — the one `factory produce` wrote the files by. A **generated** or **managed** "
                           "file changed without a produce is a hand edit, and the whole of this row is what says "
                           "so." if classify is not None else
                           f"\n\nOwnership {NOT_CHECKED}: {why}. Which files the factory writes could not be "
                           f"decided here, so decide it from `provenance.json` rather than assuming.")
                        if changed else "(no files)"))
        parts.append(section(*heading))
        diff = role_diff(base_sha, head, listed) if role == SEMANTIC else bounded_diff(base_sha, head)
        parts.append(section("7. The diff",
                             diff if diff is not None else
                             "Empty: nothing this role judges changed. See section 6."))

        if role == SEMANTIC:
            parts.append(section("8. Determinism",
                                 "The structural review checks this, and it runs before you: wall-clock time, "
                                 "ambient locale, environment-dependent ordering, unseeded randomness, hash "
                                 "codes or object identity in anything observable. Raise it if you see it — a "
                                 "reviewer who notices a defect outside its remit reports it — but it is not "
                                 "what your verdict is about, and the diff you were given is cut to the "
                                 "semantic surface, so it is not the whole of what that check reads."))
        else:
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

        manifest_name = f"pr-{number}-{head[:12]}{packet_suffix(role)}.review.json"
        if role == STRUCTURAL:
            recording = (f"**No verdict is recorded from a structural packet.** This engine's policy configures no "
                         f"review context for one: you report findings, and the orchestrator decides which of them "
                         f"block (`docs/agent-team.md`). The identity written beside this packet, "
                         f"`{manifest_name}`, records which bytes you were given; `tools/record-verdict.py` refuses "
                         f"it, by name, rather than letting a verdict be formed on a packet with no entry evidence "
                         f"in it.")
        else:
            recording = (f"When written to disk, the machine-readable identity for this packet is `{manifest_name}`. "
                         f"Record a verdict with `tools/record-verdict.py --pr {number} --packet <path-to-{manifest_name}> "
                         f"--reviewer <id> --verdict pass|fail`. The recorder verifies this packet and its entry "
                         f"packet digests, refuses if PR #{number} has moved, and refuses a reviewer this packet's "
                         f"role cannot carry — a `{role}` packet records a "
                         + ("semantic verdict." if role == SEMANTIC else
                            "verdict under one of the configured independent contexts."
                            if role == INDEPENDENT else "semantic or an independent verdict."))
        parts.append(section("10. Recording this review", recording))

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
            # Every map the engine was produced from, not one of them. An engine composed of
            # several (rules-factory 0067) is several sets of bytes an entry packet may have been
            # built from, and an identity naming one says nothing about the others -- the same
            # move `provenance.json` made from `map` to `maps` in format 7, one level out, and for
            # the same reason. One package is a list of one and reads as it did.
            "maps": [
                {
                    "packageId": package.get("packageId"),
                    "version": package.get("version"),
                    "nupkgSha256": package.get("nupkgSha256", ""),
                    # What the commit declares, and what was actually read. Recording only the first
                    # is what let two packets with different entry evidence carry one identity (#356).
                    "declaredSha256": next((part.get("sha256") for part in package.get("files") or []
                                            if part.get("role") == "map"), ""),
                    # Null, never the declared digest, when nothing was checked: writing the declared
                    # value here would be the very substitution of a claim for a fact this closes.
                    # A written identity carries a digest here whenever it names an entry packet, and
                    # `record-verdict.py` refuses one that does not (#372).
                    "readSha256": maps_read.get(package.get("packageId")),
                }
                for package in map_packages(record)
            ],
            "mapsReadFrom": ("--package-map, checked against the reviewed commit, and the entry packets "
                             "built from those exact bytes" if maps_read
                             else "MSBuild inside the reviewed tree -- NOT VERIFIED" if entries
                             else "not read: this packet names no entry, so no entry packet was built"),
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
    parser.add_argument("--package-map", action="append", default=[], metavar="PATH",
                        help="the restored map package's corpus-map.json, passed to entry-packet.py "
                             "(default: it asks MSBuild in the reviewed snapshot); repeat once per "
                             "package for a composed engine")
    parser.add_argument("--base", default="origin/main",
                        help="fallback local base ref when GitHub supplies no base SHA (default: origin/main)")
    parser.add_argument("--role", choices=ROLES,
                        help="cut the packet for one reviewer: structural (no entry packets, and no "
                             "restored map package needed), semantic (the entry packets first, and not "
                             "the pull request's own case), independent (the assignment and the current "
                             "bytes, with no other reviewer's conclusions). Default: the whole packet")
    parser.add_argument("--stdout", action="store_true",
                        help="display the human packet only; no review-packet identity file is written")
    args = parser.parse_args(argv)

    try:
        # Resolved and judged, but not created: a packet that is refused writes nothing, and a
        # directory is a write (#371). Everything below is built in the run's own private
        # directory first and lands here only once there is nothing left to refuse.
        out_dir = destination(args.out)
        packet_text, head, base_sha, packets, context = build(args.pr, args.base, args.package_map,
                                                              recordable=not args.stdout,
                                                              role=args.role or ALL)
        if args.stdout:
            sys.stdout.write(packet_text)
            return 0
        out_dir.mkdir(parents=True, exist_ok=True)
        role = args.role or ALL
        target = out_dir / f"pr-{args.pr}-{head[:12]}{packet_suffix(role)}.md"
        target.write_text(packet_text, encoding="utf-8")
        for packet in packets:
            (out_dir / packet["name"]).write_bytes(packet["bytes"])
        manifest = {
            # Format 2 carries the role. A verdict is evidence about the bytes a reviewer read, and
            # which bytes those were now depends on the cut as well as the commit, so a recorder
            # that could not see the role could not tell a semantic verdict formed on entry
            # evidence from one formed on a packet that never carried any.
            "reviewPacketFormat": 2,
            "reviewRole": args.role or ALL,
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
        manifest_target = out_dir / f"pr-{args.pr}-{head[:12]}{packet_suffix(role)}.review.json"
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
