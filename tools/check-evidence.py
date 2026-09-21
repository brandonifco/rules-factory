#!/usr/bin/env python3
"""Every artifact under examples/ is in the lock, and the lock is what is on disk (#349).

`examples/` is this repository's evidence: four corpora, six maps, the transcripts of blind second
mappings, trial reports, independent verdicts, injection and collapse results. Some of it is read
on every gate run, some only when a package is built, and some by nothing at all -- and until this
file nothing said which was which.

Three things followed from that, and this fixes the third:

  * **Nothing could be retired.** A transcript may be what a decision record rests on, or a file
    nobody has opened since it was written. Telling them apart meant reading every checker.
  * **Nothing hashed the spare.** A corpus is pinned by its manifest's `contentHash`, a staged
    blind input by its record's digests, trial 9's first mapping by `build-map-c.py --check`. The
    artifacts no check reads were pinned by nothing: their bytes could change and no run noticed.
  * **No claim about coverage could be made.** "The evidence suite passed" says nothing without a
    list of what the suite is. tools/evidence-lock.json is that list.

The role each artifact plays is **measured, not declared**. `--measure` runs the gate and the
packer under a Python audit hook that records every file they open, so the classification is what
the checks actually read. A role somebody believed, written down by hand, is the kind of claim
this repository has twice found to be false about its own tools.

  active    read by an ordinary gate run
  release   read by tools/pack-map.py -- packed into, or gating, a published package
  archived  read by nothing

What this cannot see, stated here rather than in a commit message:

  * **Reads from outside Python.** The audit hook is installed in Python processes. `dotnet` and
    `pdftotext` read files this does not see. Every corpus they touch is reached by a Python
    reader too -- extract.py hashes the PDF before pdftotext is asked for it -- so no artifact is
    classified `archived` because a non-Python reader was missed. A new evidence file read *only*
    by a non-Python tool would be, and that is what `--measure`'s own report is for.
  * **Whether an `archived` artifact should exist.** It says nothing reads it. Whether that means
    it is spare, or that a check is missing, is a question for a person.
  * **Whether the bytes are right.** It holds them to what they were, not to what they should be.

Usage:
  check-evidence.py               verify the lock against the tree, and re-hash every artifact
  check-evidence.py --measure     re-run the readers under the audit hook and rewrite the lock
  check-evidence.py --roles       print the classification and its totals

Exit 0 when the lock and the tree agree; 1 when they do not, or when the lock is empty; 2 on a
usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCK = ROOT / "tools" / "evidence-lock.json"
# The document whose per-trial byte tables are derived from the lock, and which restates the
# commit they were measured at in prose. Two places holding one fact drift (#403, #404).
INVENTORY = ROOT / "docs" / "evidence-inventory.md"
MEASURED_AT_LABEL = re.compile(r"^Measured at `([0-9a-f]{7,40})`", re.M)
EVIDENCE = "examples"
ROLES = ("active", "release", "archived")
READERS = ("checks", "links", "package")


def tracked(root: pathlib.Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", EVIDENCE], cwd=root,
                         capture_output=True, text=True, check=True).stdout
    return sorted(line for line in out.splitlines() if line)


def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(lock: pathlib.Path = LOCK) -> dict:
    with open(lock, encoding="utf-8") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------------------------
# Measuring: what does each reader actually open?
# --------------------------------------------------------------------------------------------

# Installed into every Python process the measured commands start, through PYTHONPATH. An audit
# hook sees `open` before the file is read, in the interpreter, so it catches a path however it
# was spelled -- relative, absolute, or built by a checker that copied a map into a temporary
# directory and read the original to do it.
SITECUSTOMIZE = '''\
import os, sys
_out = os.environ.get("EVIDENCE_TRACE")
_root = os.environ.get("EVIDENCE_ROOT")
if _out and _root:
    _fh = open(_out, "a", buffering=1)
    _who = sys.argv[0] or "?"
    if _who.startswith(_root):
        _who = _who[len(_root):].lstrip("/")
    _self = "check-evidence.py"
    def _by_the_lock_itself():
        # The lock's own verifier hashes every artifact it names. A measurement that counted
        # those reads would find everything read and classify nothing `archived` -- the checker
        # standing in as the evidence that something uses the bytes. It reads from its own
        # process and, through the tests, from inside pytest's, so the stack is what says so
        # rather than the command.
        frame = sys._getframe()
        while frame is not None:
            if frame.f_code.co_filename.endswith(_self):
                return True
            frame = frame.f_back
        return False
    def _hook(event, args):
        if event != "open":
            return
        path = args[0]
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        try:
            resolved = os.path.realpath(os.fspath(path))
        except Exception:
            return
        if not resolved.startswith(_root):
            return
        if _by_the_lock_itself():
            return
        _fh.write(_who + "\\t" + resolved[len(_root):].lstrip("/") + "\\n")
    sys.addaudithook(_hook)
'''


def _trace(root: pathlib.Path, argv: list[str], home: pathlib.Path,
           name: str) -> tuple[set[str], list[str]]:
    """Run `argv` with the audit hook installed.

    Returns the evidence paths it opened, and the gate steps that failed during it. The second
    is not decoration: a role is "what the checks read", so a run in which a check did not get
    as far as reading is a different measurement, and #408 saw roles move between runs with
    nothing between them touching the files.
    """
    out = home / f"{name}.txt"
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{home}:{existing}" if existing else str(home)
    env["EVIDENCE_TRACE"] = str(out)
    env["EVIDENCE_ROOT"] = str(root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        # A measurement over a run that stopped early would classify by what it happened to
        # reach, and call everything after the failure `archived`. The gate is the exception
        # worth making: it runs every step whatever any one of them says, and reports at the
        # end -- and re-measuring after adding an artifact necessarily happens while the
        # evidence step is failing, because the lock does not mention it yet. So a complete
        # failing gate run is accepted, loudly, and anything else is refused.
        complete = proc.stdout.rstrip().endswith("validate-repo.py: FAIL")
        if not complete:
            sys.stdout.write(proc.stdout[-4000:])
            sys.stderr.write(proc.stderr[-4000:])
            raise SystemExit(f"check-evidence.py: {' '.join(argv)} stopped before it finished; "
                             f"a measurement over a partial run would classify by what it "
                             f"reached")
        failed = [line[5:] for line in proc.stdout.splitlines() if line.startswith("FAIL ")]
        print(f"  NOTE: the gate ran every step and failed {len(failed)} of them; "
              f"the roles below are measured over that run", file=sys.stderr)
        for line in failed:
            print(f"        FAIL {line}", file=sys.stderr)
    else:
        failed = []
    if not out.exists():
        raise SystemExit(f"check-evidence.py: {name} opened nothing -- the audit hook did not run")
    seen = set()
    with open(out, encoding="utf-8") as handle:
        for line in handle:
            reader, _, path = line.rstrip("\n").partition("\t")
            if path.startswith(EVIDENCE + "/"):
                seen.add((reader, path))
    return seen, failed


# Which part of CI a read belongs to, decided by the tool that made it.
#
# Two of these rows are the reason the attribution exists at all.
#
# `tools/check-evidence.py` is dropped. It hashes every artifact in the lock, so a measurement
# that counted its reads would find every artifact read by the gate and classify none of them
# `archived` -- the checker's own verification standing in for the evidence that something uses
# the bytes. That is exactly the shape of self-confirming check this repository keeps finding.
#
# `tools/validate-repo.py`'s own reads are the repository-wide markdown link check and the
# decision index: the two steps it runs in-process rather than as a subprocess. Both open a file
# for a reason having nothing to do with what is in it -- every tracked *.md is opened to resolve
# its links. Counting that as "a check reads this" without saying which check would overstate how
# load-bearing the evidence is: a trial report whose only reader is the link check is verified to
# have working links and nothing else.
IGNORED_READER = "tools/check-evidence.py"
DOCUMENT_READER = "tools/validate-repo.py"
PACKER = "tools/pack-map.py"


def _reader_class(reader: str) -> str | None:
    if IGNORED_READER in reader:
        return None
    if PACKER in reader:
        return "package"
    if DOCUMENT_READER in reader:
        return "links"
    return "checks"


# The evidence step is the one failure a measurement cannot avoid: re-measuring necessarily
# happens while the lock is stale, so that step is failing by construction. Any *other* failing
# step means a check did not get as far as reading, and "what the checks read" is then measured
# over a gate that did not finish its work -- which is how a role can move with nothing about
# the file having changed (#408).
EVIDENCE_STEP = "every evidence artifact is the bytes the lock names"
# The lock's own tests hold the committed lock to the tree, so while the lock is stale they fail
# for the same reason the evidence step does. Excused only in that company: a failing test step
# with the evidence step green is a real one, and it is the step whose absence moved a role.
TESTS_STEP = "the checkers' own tests"


def partial_steps(failed: list[str]) -> list[str]:
    """The failing steps that make a measurement partial -- those failing by construction while
    the lock is being rewritten removed."""
    excusable = {EVIDENCE_STEP}
    if EVIDENCE_STEP in failed:
        excusable.add(TESTS_STEP)
    return sorted(step for step in failed if step not in excusable)


def measure(root: pathlib.Path = ROOT) -> tuple[dict[str, list[str]], list[str]]:
    """What reads each tracked artifact, attributed to the tool that opened it.

    The role follows: an artifact the packer reads is `release`, because its bytes reach
    nuget.org and that is the strongest claim on it; one another part of the gate reads is
    `active`; one nothing reads is `archived`. An artifact whose only reader is the link check
    is `active` and says so, because what that check proves about it is that its links resolve.
    """
    files = tracked(root)
    with tempfile.TemporaryDirectory() as tmp:
        home = pathlib.Path(tmp)
        (home / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
        print("measuring: the gate ...", flush=True)
        seen, failed = _trace(root, ["./scripts/validate.sh"], home, "gate")
        print(f"  {len({p for _, p in seen})} artifact(s) opened by "
              f"{len({r for r, _ in seen})} reader(s)", flush=True)
        print("measuring: every map package ...", flush=True)
        out = home / "packages"
        for settings in sorted((root / EVIDENCE).glob("*/map-package.json")):
            directory = str(settings.parent.relative_to(root))
            packed, _ = _trace(root, [sys.executable, "tools/pack-map.py", directory,
                                      "--out", str(out)], home, "pack")
            seen |= packed
        print(f"  {len({p for _, p in seen})} artifact(s) opened in all", flush=True)
    readers: dict[str, list[str]] = {path: [] for path in files}
    for reader, path in seen:
        kind = _reader_class(reader)
        if kind and path in readers and kind not in readers[path]:
            readers[path].append(kind)
    return ({path: [r for r in READERS if r in who] for path, who in readers.items()}, failed)


def role_of(readers: list[str]) -> str:
    if "package" in readers:
        return "release"
    if readers:
        return "active"
    return "archived"


# --------------------------------------------------------------------------------------------
# The lock, and holding the tree to it
# --------------------------------------------------------------------------------------------

# What each role says about where an artifact may live. `archive` is null for everything today:
# nothing has been moved out of the repository, and the field exists so that a decision to move
# something is recorded per artifact rather than in a commit message. An `archived` artifact is
# the only one for which a non-null `archive` would be admissible -- the other two are read by a
# check, and a check that fetches its inputs over the network is not a check you can run offline.
MOVABLE = ("archived",)


def build(root: pathlib.Path, readers: dict[str, list[str]], previous: dict | None,
          failed: list[str] | None = None) -> dict:
    was = {a["path"]: a for a in (previous or {}).get("artifacts", [])}
    artifacts = []
    for path in tracked(root):
        full = root / path
        artifacts.append({
            "path": path,
            "sha256": digest(full),
            "bytes": full.stat().st_size,
            "role": role_of(readers[path]),
            # Which part of CI reads these bytes: "checks" the gate proper, "links" the
            # repository-wide markdown link check and nothing else, "package" tools/pack-map.py.
            "readBy": readers[path],
            # Where the bytes are. Null means "in this repository", which is every artifact
            # today; a content-addressed identifier would go here if one were ever moved.
            "archive": was.get(path, {}).get("archive"),
        })
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                            capture_output=True, text=True, check=True).stdout.strip()
    other = partial_steps(failed or [])
    return {
        "version": 1,
        "measuredAt": commit,
        "measuredBy": "tools/check-evidence.py --measure",
        # What the measurement was taken over, so that a figure derived from it can be read
        # against the run that produced it rather than assumed (#408). The evidence step is
        # failing by construction during a re-measure, so it is not counted here; any other
        # failing step means a check stopped before it read, and the roles below are what that
        # run happened to reach.
        "measuredOver": {
            "gateStepsFailed": sorted(other),
            "complete": not other,
        },
        "roles": {
            "active": "read by an ordinary gate run",
            "release": "read by tools/pack-map.py -- packed into, or gating, a published package",
            "archived": "read by nothing the measurement could see",
        },
        "readers": {
            "checks": "a gate step that reads this artifact for what is in it",
            "links": "the repository-wide markdown link check, which opens every tracked *.md",
            "package": "tools/pack-map.py",
        },
        "artifacts": artifacts,
    }


def measured_at_problems(root: pathlib.Path, lock: dict) -> list[str]:
    """Whether the commit the lock names is one this repository has, and whether the document
    derived from the lock agrees about it (#404).

    A measurement names `git rev-parse HEAD`, so any branch whose history is rewritten --
    amended, rebased, squashed -- leaves the lock pointing at a commit that no longer exists.
    Nothing noticed, and the failure is invisible until someone tries to reproduce the run.
    `docs/evidence-inventory.md` restates the same commit in prose, so the two can disagree
    silently; they were found disagreeing on main the day this check was written.
    """
    problems = []
    commit = lock.get("measuredAt")
    if not commit:
        return ["the lock does not say which commit it was measured at"]

    known = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=root,
                           capture_output=True, text=True).returncode == 0
    if not known:
        problems.append(f"measuredAt {commit} is not a commit this repository has, so the "
                        f"measurement cannot be reproduced; re-measure, or recover the commit")
    elif subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=root,
                        capture_output=True, text=True).returncode != 0:
        problems.append(f"measuredAt {commit} is not reachable from HEAD -- it is on a history "
                        f"this branch does not contain, so the lock describes another tree")

    if INVENTORY.exists():
        found = MEASURED_AT_LABEL.search(INVENTORY.read_text(encoding="utf-8"))
        if not found:
            problems.append(f"{INVENTORY.relative_to(root)} no longer says which commit its "
                            f"figures were measured at")
        elif not commit.startswith(found.group(1)):
            problems.append(f"{INVENTORY.relative_to(root)} says its figures were measured at "
                            f"{found.group(1)} and the lock was measured at {commit[:7]}; the "
                            f"tables are derived from the lock, so one of them is stale")
    return problems


def verify(root: pathlib.Path, lock: dict) -> list[str]:
    """Every problem between the lock and the tree. Empty means they agree."""
    artifacts = lock.get("artifacts") or []
    if not artifacts:
        # Sole message, deliberately: a lock that names nothing proved nothing, and what commit
        # it says it proved nothing at adds no information.
        return ["the lock names no artifact -- this check proved nothing"]
    problems = measured_at_problems(root, lock)

    locked = {a["path"]: a for a in artifacts}
    if len(locked) != len(artifacts):
        problems.append("the lock names a path more than once")
    on_disk = set(tracked(root))

    # Both directions. A lock that only checked what it already listed would pass forever while
    # the evidence it does not mention grew beside it -- which is the shape of every stale
    # declaration this repository has found in itself.
    for missing in sorted(on_disk - set(locked)):
        problems.append(f"{missing} is tracked evidence and is not in the lock")
    for phantom in sorted(set(locked) - on_disk):
        problems.append(f"the lock names {phantom}, which is not tracked in this checkout")

    for path in sorted(on_disk & set(locked)):
        entry = locked[path]
        if entry.get("role") not in ROLES:
            problems.append(f"{path}: role {entry.get('role')!r} is not one of {ROLES}")
        readers = entry.get("readBy")
        if not isinstance(readers, list) or any(r not in READERS for r in readers):
            problems.append(f"{path}: readBy {readers!r} is not a list drawn from {READERS}")
        elif entry.get("role") != role_of(readers):
            problems.append(f"{path}: readBy {readers} makes it {role_of(readers)}, "
                            f"and the lock says {entry.get('role')}")
        if entry.get("archive") is not None and entry.get("role") not in MOVABLE:
            problems.append(f"{path}: role {entry['role']} is read by a check, so its bytes "
                            f"cannot live outside this repository")
        full = root / path
        size = full.stat().st_size
        if entry.get("bytes") != size:
            problems.append(f"{path}: the lock says {entry.get('bytes')} bytes, on disk {size}")
        actual = digest(full)
        if entry.get("sha256") != actual:
            problems.append(f"{path}: the lock says sha256 {entry.get('sha256')}, "
                            f"on disk {actual}")
    return problems


def totals(lock: dict) -> list[tuple[str, int, int]]:
    rows = []
    for role in ROLES:
        entries = [a for a in lock["artifacts"] if a.get("role") == role]
        rows.append((role, len(entries), sum(a.get("bytes", 0) for a in entries)))
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="check-evidence.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--measure", action="store_true",
                        help="re-run the readers under the audit hook and rewrite the lock")
    parser.add_argument("--roles", action="store_true",
                        help="print the classification and its totals, and check nothing")
    parser.add_argument("--lock", default=str(LOCK))
    parser.add_argument("--allow-partial", action="store_true",
                        help="write the lock from a run in which a step other than the evidence "
                             "step failed, and record in it that the measurement was partial")
    args = parser.parse_args(argv)

    lock_path = pathlib.Path(args.lock)

    if args.measure:
        previous = load(lock_path) if lock_path.exists() else None
        readers, failed = measure(ROOT)
        other = partial_steps(failed)
        if other and not args.allow_partial:
            print("check-evidence.py: the gate failed a step other than the evidence step, so a "
                  "check did not get as far as reading and the roles below are what this run "
                  "happened to reach:", file=sys.stderr)
            for step in other:
                print(f"    FAIL {step}", file=sys.stderr)
            print("  a role measured over such a run is not reproducible (#408). Fix the step, "
                  "or pass --allow-partial to write the lock anyway and record that it was "
                  "measured over a partial run.", file=sys.stderr)
            return 1
        lock = build(ROOT, readers, previous, failed)
        lock_path.write_text(json.dumps(lock, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        print(f"\nwrote {lock_path.relative_to(ROOT)}")
        for role, count, size in totals(lock):
            print(f"  {role:9s} {count:4d} artifact(s)  {size / 1024:9.0f} KB")
        if previous:
            before = {a["path"]: a["role"] for a in previous["artifacts"]}
            moved = [(p, before[p], a["role"]) for a in lock["artifacts"]
                     if (p := a["path"]) in before and before[p] != a["role"]]
            for path, was, now in moved:
                print(f"  role changed: {path}: {was} -> {now}")
        return 0

    if not lock_path.exists():
        print(f"check-evidence.py: {lock_path} does not exist; run --measure to write it",
              file=sys.stderr)
        return 1
    lock = load(lock_path)

    if args.roles:
        for role, count, size in totals(lock):
            print(f"{role:9s} {count:4d} artifact(s)  {size / 1024:9.0f} KB")
        for artifact in lock["artifacts"]:
            if artifact["role"] == "archived":
                where = artifact["archive"] or "this repository"
                print(f"  archived  {artifact['bytes'] / 1024:8.1f} KB  {artifact['path']}"
                      f"  ({where})")
        return 0

    problems = verify(ROOT, lock)
    for line in problems:
        print(f"  X  {line}")
    if problems:
        print(f"\n{len(problems)} problem(s) between tools/evidence-lock.json and the tree")
        return 1
    counts = ", ".join(f"{count} {role}" for role, count, _ in totals(lock))
    total = sum(size for _, _, size in totals(lock))
    print(f"{len(lock['artifacts'])} evidence artifact(s) verified by sha256 "
          f"({counts}), {total / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
