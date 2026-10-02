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

**What a review covered is recorded, so the next one can be bounded** (rules-factory 0071). A file
packet that carries entry evidence also writes a `*.scope.json` beside its identity: the claims of
the slice -- each entry, each invariant `reviews/invariants.json` declares -- and the fingerprint of
every unit each rests on. `tools/record-verdict.py` turns it into the review's attestation. After a
repair, `tools/review-scope.py`'s `delta` compares that attestation with the new head and writes the
bounded packet; this one is for the reviews that read everything: the first (`--review full`), one
whose delta was refused for a stated reason (`--review full --prior <attestation>`), and the final
acceptance review at the merge boundary (`--review final --prior <attestation>`).

**A reviewer is paid only after the implementer has attacked its own work.** A semantic,
independent or whole packet for a `semantic-implementation` that names an entry is refused until
every entry has a committed `reviews/self-review/<entry id>.json` answering all twenty classes of
`docs/adversarial-self-review.md`, made against the entry's claim digest at the reviewed head.

**What a change owes is its review class's to say** (rules-factory 0076): `scripts/factory/
reviewclass.py` computes it from the diff, and the first section of every packet states it. A
`semantic-ruling` is owed a decision-scoped record, `reviews/rulings/<decision>.json`
(`docs/adversarial-self-review.md`), in place of the self-review it has no code to attack with. A
change whose class owes no semantic review -- a new decision record that overrules nothing, a
regeneration with the rules unmoved, a document -- is refused a **semantic** packet outright:
a packet and a self-review written only to satisfy a policy are the ceremony this class exists to
remove. The structural cut, which is the review such a change gets, is unaffected, and so is
`--stdout`, which writes nothing a verdict could be recorded from.

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


# GitHub's REST statuses, spelled as `gh pr view --json files` spells a `changeType`, so a path read
# either way compares the same.
_CHANGE_TYPES = {"added": "ADDED", "removed": "DELETED", "modified": "MODIFIED", "renamed": "RENAMED",
                 "copied": "COPIED", "changed": "CHANGED"}


def listed_files(pull, number):
    """Every changed file of the pull request, as `{"path", "changeType"}` (#562).

    `gh pr view --json files` stops at 100 files without a word, and `changedFiles` says how many
    there are. Where the two disagree, the list is read again from the REST endpoint, which pages
    to 3,000 files; what that returns is still held to `changedFiles` by the caller, so a list
    GitHub will not give whole is refused as it always was, and never judged in part.
    """
    files = [{"path": f["path"], "changeType": f.get("changeType") or ""} for f in pull.get("files") or []]
    count = pull.get("changedFiles")
    # A rename is named by its new path alone in `gh pr view --json files`, and the REST endpoint says
    # where it came from (0076): the old path is a deletion, and a handler moved off the surface is one.
    renamed = any(f["changeType"] in ("RENAMED", "COPIED") for f in files)
    if isinstance(count, int) and len(files) == count and not renamed:
        return files
    if not isinstance(count, int) and not renamed:
        return files
    listing = gh("api", f"repos/{{owner}}/{{repo}}/pulls/{number}/files?per_page=100", "--paginate",
                 "--jq", '.[] | [.filename, .status, (.previous_filename // "")] | @tsv')
    whole = []
    for line in listing.splitlines():
        path, _, rest = line.partition("\t")
        status, _, previous = rest.partition("\t")
        if path:
            whole.append({"path": path, "changeType": _CHANGE_TYPES.get(status, status.upper()), "previous": previous})
    return whole


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


def engine_path():
    """This engine's path under its repository root, or "" when the engine **is** that root.

    Read from `provenance.json` (`repository.enginePath`, provenanceFormat 9, rules-factory decision
    0069). A worktree holds the **repository**, so for an engine embedded under one the engine inside
    a reviewed snapshot is this much deeper -- and every read of the snapshot here is a read of the
    engine: the policy, the record, the overlay, the vendored ownership table.
    """
    try:
        record = json.loads((ROOT / PROVENANCE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    section = record.get("repository") if isinstance(record, dict) else None
    return str((section or {}).get("enginePath") or "") if isinstance(section, dict) else ""


def reviewed_snapshot(head):
    """The reviewed commit's **engine**, plus the private directory that owns the worktree.

    A detached worktree containing exactly `head` is made first; what is returned is the engine
    inside it, which is the worktree itself for an engine that is its own repository root and
    `<worktree>/<enginePath>` for one embedded under a repository root (0069). Everything the
    assembly reads is engine-relative, so returning the engine is what makes the rest of this file
    read the same for either topology.

    The parent is this run's own scratch space, and everything the assembly produces is built
    there first: the map copy the entry packets are read from, and the entry packets themselves.
    Nothing reaches the caller's `--out` until every refusal has passed, so a refused packet
    leaves nothing behind (#371).
    """
    parent = pathlib.Path(tempfile.mkdtemp(prefix="rules-engine-review-"))
    worktree = parent / "reviewed"
    try:
        git("worktree", "add", "--detach", "--quiet", str(worktree), head)
    except Exception:
        shutil.rmtree(parent, ignore_errors=True)
        raise
    inside = engine_path()
    snapshot = worktree / inside if inside else worktree
    if not (snapshot / PROVENANCE).is_file():
        remove_reviewed_snapshot(parent, snapshot)
        raise Refused(f"the reviewed commit {head[:12]} holds no {PROVENANCE} at "
                      f"{inside or '.'}, where this engine's own record says the engine is; the "
                      f"packet is cut from the engine inside the reviewed tree and there is none "
                      f"there (rules-factory decision 0069)")
    return parent, snapshot


def remove_reviewed_snapshot(parent, snapshot):
    """Remove the temporary worktree on both success and failure.

    `snapshot` may be the engine inside the worktree rather than the worktree itself (0069), and
    git removes a worktree by its own root, so the root is taken from `parent` and not from it.
    """
    subprocess.run(["git", "worktree", "remove", "--force", str(parent / "reviewed")], cwd=ROOT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(parent, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=ROOT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def policy_tool():
    """`tools/pr-policy.py`, loaded by path: the one reading of what a pull request says it implements.

    `pr-policy.py` requires the pull request body's `## Map and rules conformance` bullet to name the
    entry, and reads it. A packet that read only the HTML marker told a reviewer that a pull request
    policy had accepted named no entry (#464), so the bullet is read by the same functions and the two
    cannot come to disagree about what counts as naming one.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("pr_policy_tool", pathlib.Path(__file__).resolve().parent
                                                  / "pr-policy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def entry_ids(*texts):
    """Every entry id named by a marker in `texts`, in first-seen order."""
    found = []
    for text in texts:
        for part in (text or "").split(ENTRY_MARKER)[1:]:
            entry_id = part.split("-->")[0].strip()
            if entry_id and entry_id not in found:
                found.append(entry_id)
    return found


def entries_named(issue_body, pull_body):
    """`(ids, unreadable)`: every entry the issue or the pull request names, and what is not an id.

    The issue's marker, the pull request's marker, and the ids on the `entry id(s):` line of the pull
    request's `## Map and rules conformance` section -- which is where `tools/pr-policy.py` requires
    them, and where an issue that legitimately carries several finds room for them (#464, #526). In
    first-seen order, each once. `unreadable` is the parts of that line no entry id can be: they are
    reported in section 3 and never silently dropped.
    """
    tool = policy_tool()
    listed, unreadable = tool.named_entries(tool.sections(pull_body).get("Map and rules conformance"))
    ids = entry_ids(issue_body, pull_body)
    for entry_id in listed:
        if entry_id not in unreadable and entry_id not in ids:
            ids.append(entry_id)
    return ids, unreadable


def naming_note(unreadable):
    """A sentence for section 3 about the parts of the conformance bullet that name no entry, or ""."""
    if not unreadable:
        return ""
    return ("\n\nThe pull request's `## Map and rules conformance` `entry id(s):` line also holds "
            + ", ".join(f"`{part}`" for part in unreadable)
            + ", which is not an entry id and was not read as one. `tools/pr-policy.py` reads the same line "
              "and reports it too.")


NAMES_NO_ENTRY = ("The issue and the pull request name no entry: there is no `rules-factory-entry` marker in "
                  "either body, and the `entry id(s):` line of the pull request's `## Map and rules conformance` "
                  "section names none.")


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


def factory_module(name):
    """One of this engine's own vendored `scripts/factory` modules, or a refusal that says to produce again."""
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        return __import__(name)
    except ImportError as error:
        raise Refused(f"scripts/factory/{name}.py is not importable ({error}); run `factory produce` again")
    finally:
        sys.path.pop(0)


def git_show(commit, path):
    """The bytes of an engine-relative `path` as `commit` commits it, or None."""
    prefix = (engine_path() + "/") if engine_path() else ""
    done = subprocess.run(["git", "show", f"{commit}:{prefix}{path}"], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    return done.stdout if done.returncode == 0 else None


def review_class(snapshot, record, files, patterns, body, base_sha):
    """`(result, effective, problems, hints, declared, module)`: what the reviewed diff owes (0076).

    `files` is GitHub's list, a rename carrying the path it came from, judged against the surface the base
    and the head policies both list (0076). The head's bytes are the reviewed
    snapshot's and the base's are the base commit's, so neither is the caller's checkout. The
    ownership table is the reviewed commit's own, as for the changed-path classes below: a path is
    the factory's by the rows that wrote it. Where that table cannot be loaded nothing is the
    factory's, and nothing is exempt.
    """
    module = factory_module("reviewclass")
    prefix = engine_path()
    inside = {}
    try:
        base_policy = json.loads((git_show(base_sha, POLICY) or b"").decode("utf-8")).get("review") or {}
        base_listed = base_policy.get("semanticPaths") if isinstance(base_policy, dict) else None
    except (UnicodeDecodeError, ValueError, AttributeError):
        base_listed = None
    patterns = module.surface_patterns(patterns, base_listed if isinstance(base_listed, list) else None)
    for path, change in module.changes_of(files).items():
        relative = engine_relative(path, prefix)
        if relative is not None:
            inside[relative] = change
    name = (record.get("engine") or {}).get("name")
    fclass = lambda _path: None  # noqa: E731
    if isinstance(name, str) and name:
        sys.path.insert(0, str(snapshot / "scripts" / "factory"))
        try:
            import ownership  # noqa: E402  (the reviewed commit's own table)
            fclass = module.factory_class(ownership, name)
        except ImportError:
            pass

    def read(path, side):
        if side == "head":
            try:
                return (snapshot / path).read_bytes()
            except OSError:
                return None
        return git_show(base_sha, path)

    result = module.classify(inside, patterns, read=read, fclass=fclass)
    declared = module.declared_class(body)
    effective, problems, hints = module.judge(result, declared)
    return result, effective, problems, hints, declared, module


def ruling_review_problems(snapshot, result, base_sha):
    """Every way the decision records this change rules on lack the review record they owe (0076).

    One `reviews/rulings/<decision>.json` per decision record, made against that record's bytes at
    the reviewed head, so an edit to the ruling after it was reviewed makes the record stale.
    """
    model = factory_module("reviewscope")
    out = []
    for path in result["decisionRecords"]:
        try:
            data = (snapshot / path).read_bytes()
        except OSError:
            data = b""          # a deleted record: the ruling withdrawn is reviewed against nothing
        record_path = snapshot / model.RULING_REVIEWS / f"{model.ruling_review_stem(path)}.json"
        try:
            record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else None
        except (OSError, ValueError) as error:
            record = {"unreadable": str(error)}
        out += model.ruling_review_problems(record, path, hashlib.sha256(data).hexdigest())
    return out


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
    """The bounded diff of exactly `paths`. An empty list is an empty diff, never the whole one.

    `paths` are as GitHub reports them, **repository**-relative, and git runs in the engine, which for
    an engine embedded under a repository root (0069) is a directory below the repository's. A pathspec
    is relative to where git runs, so `engine/src/X.cs` matched nothing and section 7 of every such
    packet was an empty fence (#522, #526). `:(top)` anchors each at the repository's root, and
    `literal` keeps a file name with a glob character in it a file name.

    **A listed path that yields no diff is a refusal, not an empty section.** Every path here is one
    GitHub reported as changed between exactly these two commits, so nothing but a wrong pathspec can
    make git say otherwise -- and a reviewer handed an empty diff over a listed surface would form a
    verdict on bytes it was never shown.
    """
    if not paths:
        return None
    specs = [f":(top,literal){path}" for path in paths]
    shown = set(git("diff", "--name-only", "-z", f"{base}...{head}", "--", *specs).split("\0"))
    missing = [path for path in paths if path not in shown]
    if missing:
        raise Refused(f"git shows no change to {len(missing)} of the {len(paths)} path(s) GitHub lists as changed "
                      f"between {base[:12]} and {head[:12]}: {', '.join(missing[:5])}"
                      + (", ..." if len(missing) > 5 else "")
                      + ". A diff that examined nothing is not an empty diff, and a semantic reviewer given one "
                        "would judge a surface it was never shown; the pathspec or the commits are wrong.")
    text = git("diff", f"{base}...{head}", "--", *specs)
    lines = text.splitlines()
    if len(lines) <= DIFF_LINE_BUDGET:
        return "```diff\n" + text.rstrip() + "\n```"
    return ("```diff\n" + "\n".join(lines[:DIFF_LINE_BUDGET]) + "\n```\n\n"
            f"**This diff is {len(lines)} lines and was cut at {DIFF_LINE_BUDGET}.** A change this size "
            f"against one issue is itself a finding: say so rather than reviewing the visible part and "
            f"calling it a review. The whole of it: `git diff {base}...{head} -- <the paths above>`.")


def bounded_diff(base, head, changed=()):
    """The diff, with a line budget: a reviewer that skims a 6000-line diff reviewed nothing.

    `changed` is the files GitHub says the pull request changes. A diff that comes back empty over a
    non-empty list is refused for the reason `role_diff` refuses one (#522).
    """
    text = git("diff", f"{base}...{head}")
    if changed and not text.strip():
        raise Refused(f"git shows no diff between {base[:12]} and {head[:12]}, but GitHub lists {len(changed)} "
                      f"changed file(s). A diff that examined nothing is not an empty diff.")
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
    kept = {name: "\n".join(lines).strip() for name, lines in out.items()}
    return {name: kept[name] for name in wanted if kept.get(name)}


REVIEWS = ("full", "final")


def scope_tool():
    """`tools/review-scope.py`, loaded by path: the one reading of the engine's review state."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("review_scope_tool", pathlib.Path(__file__).resolve().parent
                                                  / "review-scope.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def review_scope(snapshot, checked_maps, entries, head, review, prior, base=None, self_review=True):
    """The scope record a comprehensive review is formed on, after the self-review gate (0071).

    Refuses when an entry has no current adversarial self-review, when `--review final` has no
    prior to follow, and when `--review full --prior` names a prior this change is only a delta of:
    a full review after a prior needs a reason, and "the head changed" is not one.
    """
    tool = scope_tool()
    try:
        model, current, facts = tool.engine_state(snapshot, checked_maps, entries)
        problems = []
        for entry_id in (entries if self_review else ()):
            record_path = snapshot / model.SELF_REVIEWS / f"{entry_id}.json"
            try:
                record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else None
            except (OSError, ValueError) as error:
                record = {"unreadable": str(error)}
            problems += model.self_review_problems(record, entry_id, model.claim_digest(current, f"entry:{entry_id}"),
                                                   facts["declaredTests"])
        if problems:
            raise Refused("the implementer's adversarial self-review is not complete at this head, so no reviewer is "
                          "paid yet:\n" + "\n".join(f"  - {p}" for p in problems)
                          + "\nWrite each record from `tools/review-scope.py self-review <entry id> --package-map "
                            "<path>` and commit it under reviews/self-review/ (docs/adversarial-self-review.md).")
        prior_document = None
        if prior:
            prior_document, reusable, why = tool.load_prior(snapshot, prior, head)
            if review == "final":
                if not reusable:
                    raise Refused(f"a final review follows the chain it accepts, and {prior} cannot be proved to be "
                                  f"the attestation recorded ({why})")
                if (prior_document.get("reviewType"), prior_document.get("result")) != ("delta", "PASS"):
                    raise Refused(f"a final review follows a delta PASS, and {prior} is a "
                                  f"{prior_document.get('reviewType')} {prior_document.get('result')}: answer its "
                                  f"findings with a repair and a delta review first. A full PASS needs no final review.")
                result = {"mode": "full", "reasons": [], "review": sorted(current["claims"]), "retained": [],
                          "invalidated": {}, "new": [], "changes": [], "carriedFindings": [], "changedUnits": []}
            else:
                result = model.impact(prior_document if prior_document is not None else {}, current,
                                      reusable=reusable)
                if result["mode"] != "full":
                    raise Refused(f"this change is a {result['mode']} of {prior}, not a full review: nothing it "
                                  f"changed forces one, and the head changing is not a reason. Write the bounded "
                                  f"packet with `tools/review-scope.py delta <pr> --prior {prior} --package-map "
                                  f"<path>`" + (", or carry the verdict: nothing it rested on moved"
                                                if result["mode"] == "none" else "") + ".")
        else:
            if review == "final":
                raise Refused("a final acceptance review follows a chain of reviews: name its last attestation with "
                              "--prior. The first review of a change is --review full.")
            earlier = tool.committed_on_branch(snapshot, base) if base else []
            if earlier:
                # A baseline taken while this branch already has reviews would drop their findings
                # and call itself the first. The latest is the prior; its impact says what is owed.
                raise Refused(f"this branch already carries {len(earlier)} review attestation(s) "
                              f"({', '.join(earlier)}): name the latest with --prior. A full review of a change "
                              f"that has been reviewed before answers its findings, and needs a reason.")
            result = model.impact(None, current)
    except tool.Refused as error:
        raise Refused(str(error))
    return {"scopeFormat": 1, "project": facts["project"],
            "state": {"units": current["units"], "claims": current["claims"]}, "impact": result,
            "maps": facts["maps"], "corpora": facts["corpora"], "charter": facts["charter"],
            "locators": {e: facts["locators"].get(e) for e in entries},
            "telemetry": {"closureSize": len({u for c in current["claims"].values() for u in c if u.startswith("file:")}),
                          "entriesPresented": len(entries)}}, prior_document


def build(number, base, package_maps=(), recordable=True, role=ALL, review_type="full", prior=None):
    pull = json.loads(gh("pr", "view", str(number), "--json",
                         "number,title,body,headRefOid,headRefName,baseRefName,baseRefOid,files,changedFiles,"
                         "closingIssuesReferences"))
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

        files = listed_files(pull, number)
        changed = [f["path"] for f in files]
        # `gh pr view --json files` caps at 100 files, silently: no error, no warning, and
        # `changedFiles` says how many there really are; `listed_files` reads the rest from the
        # REST endpoint (#562), and what is still short is refused here. `tools/conformance-gate.py` has refused a
        # truncated list since #193, because the semantic surface cannot be decided from half the
        # files -- and since the cuts of #467 these paths decide what the diff *contains*, not only
        # what it is labelled. On a truncated list a semantic packet can drop a changed source file
        # from the diff and then say "nothing was withheld" (#478). A packet that cannot see the
        # whole change cannot honestly say what it left out of it.
        count = pull.get("changedFiles")
        if isinstance(count, int) and len(changed) != count:
            raise Refused(f"GitHub listed {len(changed)} of PR #{number}'s {count} changed files, so the file list "
                          f"is truncated. This packet cuts its diff and its withheld-file list from those paths, so "
                          f"on a partial list it would drop a change and say nothing was dropped. Review this pull "
                          f"request in pieces it can list, or read the whole diff directly: "
                          f"`git diff {base_sha}...{head}`.")
        # In the engine's own terms. `semanticPaths` are engine-relative (`src/**`, `overlay/**`), and
        # GitHub reports a changed path relative to the **repository** -- for an engine embedded under
        # a repository root (rules-factory decision 0069) those are not the same string, and matching
        # the wrong one told a semantic reviewer that twenty new handlers and their tests were not its
        # business, with the entry packets withheld because the surface looked empty (#515). A path
        # outside the engine is not this engine's surface and is listed among what was withheld.
        try:
            provenance_bytes = (snapshot / PROVENANCE).read_bytes()
            record = json.loads(provenance_bytes.decode("utf-8"))
            policy_bytes = (snapshot / POLICY).read_bytes()
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise Refused(f"reviewed commit {head[:12]} does not carry readable review context ({error})")

        # What this change owes is its review class's to say (0076), and the surface a semantic
        # reviewer is handed is what that class says is semantic: not every path the policy lists.
        result, effective, class_problems, class_hints, declared, classes = review_class(
            snapshot, record, files, review.get("semanticPaths") or [], pull.get("body") or "", base_sha)
        prefix = engine_path()
        semantic = [f"{prefix}/{path}" if prefix else path for path in classes.semantic_files(result, effective)]
        owed = classes.owes(effective)
        if recordable and role == SEMANTIC and not owed["verdict"]:
            raise Refused(f"this change is `{effective}`, which owes no semantic review: "
                          + "; ".join(result["reasons"][:3] or [effective])
                          + ". A semantic packet, and the entries and self-review it would require, written only to "
                            "satisfy a policy are the ceremony the review classes remove. The review it gets is "
                            "structural (`--role structural`) and the pull request policy's. If this change is "
                            "more than that, say so on the `review class:` line of its conformance section; if "
                            "you want to read this packet anyway, `--stdout` writes nothing a verdict can be "
                            "recorded from.")

        entries, unreadable = entries_named(issue.get("body"), pull.get("body"))

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
                 f"`tools/review-scope.py`'s `delta` says what of this review it invalidates.\n",
                 "This packet is the whole of your assignment. It is built from the repository and the map; there is "
                 "no conversation behind it, and you need none. Start from a clean session.\n",
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
                                  NAMES_NO_ENTRY + (" For a change to the rules surface that is a finding: the "
                                  "next reviewer cannot check an implementation against a rule nobody named."
                                                    if effective == classes.SEMANTIC_IMPLEMENTATION else
                                                    f" A `{effective}` change owes no entry."))
                                 + naming_note(unreadable)))
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
                    "from them, not from the implementation.\n\n" + "\n".join(rendered) + naming_note(unreadable))
            parts.append(section("3. The entries, as the map has them", body))
        else:
            body = (NAMES_NO_ENTRY + (" For a change to the rules surface that is a finding: the reviewer cannot "
                    "check an implementation against a rule nobody named."
                                      if effective == classes.SEMANTIC_IMPLEMENTATION else
                                      f" A `{effective}` change owes no entry.") + naming_note(unreadable))
            parts.append(section("3. The entries, as the map has them", body))

        # What a comprehensive review is formed on, and the gate in front of it: only for a packet a
        # verdict can be recorded from, and only where there is entry evidence to scope (0071). After
        # the entry packets, so an entry nobody can build a packet for is refused for that first.
        if recordable and effective == classes.SEMANTIC_RULING and role in READS_ENTRIES:
            problems = ruling_review_problems(snapshot, result, base_sha)
            if problems:
                raise Refused("the implementer's review of the ruling is not complete at this head, so no reviewer "
                              "is paid yet:\n" + "\n".join(f"  - {p}" for p in problems)
                              + "\nWrite each record from `tools/review-scope.py ruling-review <decision record>` and "
                                "commit it under reviews/rulings/ (docs/adversarial-self-review.md).")
        scope, prior_document = ((review_scope(snapshot, checked_maps, entries, head, review_type, prior, base_sha,
                                               self_review=owed["self_review"]))
                                 if recordable and entries and role in READS_ENTRIES and maps_read
                                 else (None, None))
        if prior and scope is None and recordable:
            raise Refused("--prior applies to a packet that carries entry evidence: a semantic, independent or whole "
                          "packet that names an entry, with --package-map")
        parts.insert(3, section("0. What this change owes",
                                "\n".join(classes.describe(result, effective, declared))
                                + "".join(f"\n- note: {line}" for line in class_hints + class_problems)
                                + ("".join(f"\n- ruling: `{path}`, reviewed by `reviews/rulings/"
                                           f"{factory_module('reviewscope').ruling_review_stem(path)}.json`"
                                           for path in result["decisionRecords"])
                                   if effective == classes.SEMANTIC_RULING else "")
                                + "\n\nThis is computed from the diff, not taken from the pull request: its "
                                  "`review class:` line can claim an exemption the diff shows or ask for more, and "
                                  "cannot lower what the diff computes (rules-factory 0076)."))
        if review_type == "final":
            parts.insert(3, section("0. Final acceptance review",
                                    "This is the **final acceptance review**: the complete claimed slice, reread once, from "
                                    "a clean snapshot of the head being merged. It exists to catch what a chain of bounded "
                                    "reviews cannot -- an invalidation computed wrongly, an interaction between two repairs, "
                                    "a blind spot of an earlier reviewer, a reading that drifted. You are not given the "
                                    "earlier reviews' conclusions, on purpose. Review every entry below as if nothing had "
                                    "been reviewed before."))
        elif scope and scope["impact"]["reasons"]:
            parts.insert(3, section("0. Why this review is a full one",
                                    "\n".join(f"- `{r['code']}`: {r['detail']}" for r in scope["impact"]["reasons"])
                                    + "\n\nA full review needs a reason, and these are this one's (rules-factory 0071)."))
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
        diff = role_diff(base_sha, head, listed) if role == SEMANTIC else bounded_diff(base_sha, head, changed)
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
                 f"- `{review.get('semanticContext', '(unset)')}` — required for this change (`{effective}`)"
                 if semantic or owed["verdict"] else
                 f"- `{review.get('semanticContext', '(unset)')}` — not required: this change is `{effective}`"]
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
            # What this change was computed to be, and what it was judged as once the pull request's
            # claim was weighed (0076): the recorder refuses a semantic verdict on a class that owes none.
            "reviewClass": {"computed": result["class"], "effective": effective, "declared": declared},
            "mapsReadFrom": ("--package-map, checked against the reviewed commit, and the entry packets "
                             "built from those exact bytes" if maps_read
                             else "MSBuild inside the reviewed tree -- NOT VERIFIED" if entries
                             else "not read: this packet names no entry, so no entry packet was built"),
        }
        return "\n".join(parts), head, base_sha, packets, context, scope
    finally:
        remove_reviewed_snapshot(parent, snapshot)


def engine_relative(path, prefix):
    """`path`, as GitHub reports it, in the engine's own terms -- or None when it is not the engine's.

    None is a file of the repository the engine is embedded in: its README, its own workflows, the
    corpus and tooling a host product keeps beside the engine. Those are not on this engine's semantic
    surface, and a verdict about this engine is not about them (0069, #515).
    """
    if not prefix:
        return path
    return path[len(prefix) + 1:] if path.startswith(prefix + "/") else None


def semantic_surface(changed, patterns, prefix):
    """The changed paths on the engine's semantic surface, in the order they were given.

    One function rather than a comprehension at the call site, so a test can reach it: the defect this
    closes (#515) was invisible because nothing but `main` computed the surface, and `main` needs a
    pull request to run.
    """
    found = []
    for path in changed:
        relative = engine_relative(path, prefix)
        if relative is not None and is_semantic(relative, patterns):
            found.append(path)
    return found


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


def _committed(head, path):
    """The bytes of `path` as `head` commits them, engine-relative."""
    prefix = (engine_path() + "/") if engine_path() else ""
    done = subprocess.run(["git", "show", f"{head}:{prefix}{path}"], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    if done.returncode != 0:
        raise Refused(f"{path} is not committed at {head[:12]}")
    return done.stdout


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
    parser.add_argument("--review", choices=REVIEWS, default="full",
                        help="full (the first review, or one a delta was refused for) or final (the acceptance "
                             "review at the merge boundary, which rereads the whole slice). Default: full")
    parser.add_argument("--prior", metavar="PATH",
                        help="the prior attestation, as committed under reviews/attestations/: required for "
                             "--review final, and for a full review that follows one")
    parser.add_argument("--stdout", action="store_true",
                        help="display the human packet only; no review-packet identity file is written")
    args = parser.parse_args(argv)

    try:
        # Resolved and judged, but not created: a packet that is refused writes nothing, and a
        # directory is a write (#371). Everything below is built in the run's own private
        # directory first and lands here only once there is nothing left to refuse.
        out_dir = destination(args.out)
        packet_text, head, base_sha, packets, context, scope = build(args.pr, args.base, args.package_map,
                                                                     recordable=not args.stdout,
                                                                     role=args.role or ALL, review_type=args.review,
                                                                     prior=args.prior)
        if args.stdout:
            sys.stdout.write(packet_text)
            return 0
        out_dir.mkdir(parents=True, exist_ok=True)
        role = args.role or ALL
        stem = f"pr-{args.pr}-{head[:12]}{packet_suffix(role)}" + ("-final" if args.review == "final" else "")
        target = out_dir / f"{stem}.md"
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
            # What kind of review this packet is for, and -- where it carries entry evidence -- the
            # scope a verdict on it attests (0071). A packet with no scope still records a verdict,
            # and its attestation says it is unscoped, so it can never be a delta's parent.
            "reviewType": args.review,
        }
        if scope is not None:
            measured = scope_tool().scope_model().measure(packet_text, [p["bytes"] for p in packets])
            scope["telemetry"].update({"packetBytes": measured["bytes"], "packetCharacters": measured["characters"],
                                       "packetFiles": measured["files"]})
            scope_bytes = (json.dumps(scope, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            (out_dir / f"{stem}.scope.json").write_bytes(scope_bytes)
            manifest["scope"] = {"path": f"{stem}.scope.json", "sha256": hashlib.sha256(scope_bytes).hexdigest()}
            if args.prior:
                prior_bytes = _committed(head, args.prior)
                (out_dir / f"{stem}.prior.attestation.json").write_bytes(prior_bytes)
                manifest["prior"] = {"path": f"{stem}.prior.attestation.json", "source": args.prior,
                                     "sha256": hashlib.sha256(prior_bytes).hexdigest()}
        manifest_target = out_dir / f"{stem}.review.json"
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
