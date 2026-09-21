#!/usr/bin/env python3
"""The rules factory (#3): produce a .NET engine from a published corpus-map package.

  python3 tools/factory produce --package <nupkg path | Id@Version> --corpus <file> [--corpus <file> ...]
                                --name <PascalName> --out <dir> [--no-verify]
  python3 tools/factory backlog --create --repo <owner/name> --dir <engine dir>
  python3 tools/factory backlog --render --dir <engine dir> [--to <directory>]

`produce` runs, in order, and stops at the first refusal. Every step writes into a staging copy
of `--out`, and the result is written to `--out` only after the last step passed, so a
refusal leaves `--out` byte-identical to how it started (transaction.py, #67). `produce` writes
files and never runs git in the engine: when `--out` is a git checkout the last line says the
changes are uncommitted, for whoever ran it to review and commit:

  * intake (intake.py) -- the package is a map package carrying its checker, the map's
    `schemaVersion` is one the factory reads, the corpus's licence is public domain or open
    (decision 0028), the corpus is `committed-copy` and hashes to the map's baseline, and the
    factory's own `tools/check-map.py --phase consumer` passes on the packaged map. Nothing from the package is ever run (0016): its checker is hashed, not
    executed;
  * scaffold and generation (generate.py) -- a .NET solution on RulesKernel and the map
    package, each file in one ownership class (ownership.py): managed build policy, updated
    with its recipe and refused when hand-edited unless `--adopt PATH` or `--reset PATH`;
    engine-owned files, written once; and the generated files, rewritten
    every run: the `*.g.cs` from the package map merged with the engine's overlay --
    `overlay/<entry id>.json`, one file per entry, read in map order (#247) -- and
    `RulesFactory.Packages.g.props`, which pins RulesKernel and
    the map package at the versions given and references the map;
  * the gate recipe (gate.py) -- scripts/validate.sh and the scripts and CI workflow it runs,
    rewritten every run;
  * backlog (backlog.py) -- nothing is written. The backlog is a projection of the map and the
    overlay, not a file in the engine (#243): `backlog --create` files it as GitHub issues and
    `backlog --render` prints it. A `backlog/` an earlier produce committed is removed, with the
    run, and the run says so;
  * provenance (provenance.py), last -- `provenance.json` in the engine root, embedded in the
    engine. Before anything else, a factory whose git working tree is dirty is refused unless
    `--allow-dirty`;
  * verify (verify.py), in the staging copy, before anything is written out -- the engine is
    proven, as below, so a failure leaves `--out` as it was and only a verified engine is ever
    written out. The lock files restore writes are written with it (bin/ and obj/ never are).
    When restore writes lock files there, provenance.json is rewritten before the gate builds
    to record them as build inputs (#69), so what is written out is what the gate tested.
    When the run changed the generated pins (a map version bump) and lock files exist, verify
    re-locks them first (#94); that is the one case produce rewrites engine-owned files.
    `--no-verify` skips it, for a machine without the SDK the engine pins. The output and the
    final line say the engine was written unverified, and the run **exits 3, NOT VERIFIED, never
    0**: nothing was built or tested, so no caller reading only the exit code may read it as a
    verified produce. 3 is what NOT VERIFIED exits with everywhere in this lineage (the gate's
    `posture` check, `check-rebuild.py`, `check-target.py`); a caller for which an unverified
    engine is the intended outcome accepts exactly that code, the way scripts/validate.sh accepts
    3 from `engine-gate.py posture`. A `--no-verify` run whose committed lock
    files resolve a pinned package (RulesKernel, RulesKernel.Randomness, the map) at another version
    than the generated pins re-locks them with `dotnet restore` alone, on the pinned SDK or
    `FACTORY_DOTNET_SDK_OVERRIDE`, and records them. When no SDK can run, restore fails, or the lock
    files still disagree, it is refused, naming each lock file, package and both versions, and the
    command that works. Lock files that agree are written out as they are;
  * `--produce-report FILE`, after the files are in place -- what this run did, as JSON: what moved
    (the map version, the kernel, the factory) and from what to what, every path written with its
    ownership class, and the provenance diff. A `factory produce` update to an engine is a pull
    request under that engine's rails, and this is where its template's fields come from, so they
    are read off the run rather than remembered (#193, decision 0029's amendment);
  * writing out (transaction.py) -- the files the steps added, changed or removed are put in place
    in `--out`, journaled and rolled back on failure (a fresh `--out` is one rename). No git commit
    is made, here or anywhere else in produce. A verified run is held to every source and build
    input verify built and tested it from, not only to the paths it writes: if one of them moved in
    `--out` while produce ran, the run is refused before anything is written, naming each path,
    because the tree that would be on disk is not the one that was built (#335). The edit is kept --
    nothing is written over it -- and produce is run again to verify the engine with it.

`backlog --create` renders the backlog from the map package provenance.json records (`--package`,
or Id@Version from the NuGet global packages folder) merged with the engine's `overlay/`, and
synchronises it with GitHub issues through `gh` (or `$FACTORY_GH`):
each item is matched to its issue by the entry marker in its body, never by title, and the
issue is created, updated, or left unchanged. It never closes or deletes an issue. Before any
call, when the corpus's licence requires attribution, a body without the statement is refused
(decision 0023).

`backlog --render` is the same rendering with nothing sent anywhere: one Markdown document on
stdout, or, with `--to <directory>`, the item files. `--to` is refused inside the engine unless
the engine's `.gitignore` covers it -- the point of #243 is that a rendering of the overlay is
not committed beside the overlay.

  python3 tools/factory provenance --engine <dir> [--package <nupkg path | Id@Version>]

re-produces the engine in a scratch copy and names every provenance field that does not match
(exit 1), or says it matches (exit 0). `recompute_provenance` is the same, as a function.

  python3 tools/factory verify --engine <dir> [--package <nupkg path | Id@Version>]

runs the stages that make an engine acceptable and names the first that fails: provenance
recomputes; `dotnet restore` writes the lock files if the engine has none (standalone verify
never re-locks existing ones; only produce does, when it changed the pins); and the engine's own
gate (`scripts/validate.sh full`: locked restore, -warnaserror build and tests in Debug and
Release, format, regeneration, posture, ...) passes. `dotnet` is `$FACTORY_DOTNET` when set.
Outside CI, `FACTORY_DOTNET_SDK_OVERRIDE=<version>` runs restore and the gate on that SDK instead of
global.json's pin, without changing global.json or what provenance checks, and verify and produce
say so in a WARNING and on their last line.
See verify.py.

Exit 0 when every step passed; 1 when a step refused; 2 on a usage error; 3 when a step could
prove nothing and said so -- today that is `produce --no-verify`, which writes an engine that was
never built or tested. 3 is NOT VERIFIED: not a pass, not a failure, and never silent (0013).
Standard library only.
"""
import argparse
import contextlib
import io
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backlog as backlog_step  # noqa: E402
import gate  # noqa: E402
import generate  # noqa: E402
import ownership  # noqa: E402
import intake as intake_step  # noqa: E402
import provenance  # noqa: E402
import rails as rails_step  # noqa: E402
import transaction  # noqa: E402
import verify as verify_step  # noqa: E402

PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]*$")

#: The exit code of a run that proved nothing and said so. Not a pass and not a failure: the same
#: outcome, and the same code, that `engine-gate.py posture`, `check-rebuild.py` and
#: `check-target.py` already use for NOT VERIFIED. `produce --no-verify` is the only run that ends
#: this way; a caller that wants an unverified engine accepts exactly 3, and 1 still means refused.
NOT_VERIFIED = 3


def produce(args):
    if not PASCAL.match(args.name):
        raise intake_step.Usage(f"--name {args.name!r} is not a PascalCase C# identifier")
    # Refused before anything is produced: a report directory that does not exist is a typo, and
    # finding out after a verified produce means running the whole thing again for one file.
    if getattr(args, "produce_report", None):
        directory = os.path.dirname(os.path.abspath(args.produce_report))
        if not os.path.isdir(directory):
            raise intake_step.Usage(f"--produce-report {args.produce_report}: {directory} is not a directory")
    state = provenance.factory_state()
    provenance.require_clean(state, args.allow_dirty)
    # The record this engine had before the run, for --produce-report. Read here because the
    # staging copy is about to be overwritten with the new one, and an absent file is the first
    # produce of this engine, which the report says rather than guesses at.
    before = read_record(args.out)
    # Every step writes into `out`, a staging copy of --out; --out itself is only touched by
    # commit(), after the last step passed -- which puts files in place and makes no git commit
    # (transaction.py).
    with transaction.Stage(args.out, log=sys.stdout) as stage:
        out = stage.root
        # The pins the engine had before this run: the staging copy is still --out as it was.
        pins_before = verify_step.read_pins(out)
        with provenance.Recorder(out) as recorder:
            result = intake_step.intake(args.package, args.corpus, log=sys.stdout)
            print(f"intake passed: {result.package_id} {result.version}, {len(result.map.get('entries') or [])} entries")
            model = generate.produce(result, args.name, out, log=sys.stdout,
                                     adopt=getattr(args, "adopt", None) or (), reset=getattr(args, "reset", None) or ())
            gate.emit(args.name, out, log=sys.stdout)
            # What the factory used to write and no longer does is removed here, by the retired
            # patterns of the ownership table, and the removal is committed with everything else
            # this run did, or not at all (transaction.py). Two things are retired: the `backlog/`
            # an earlier produce committed (#243 -- the backlog is a projection of the map and the
            # overlay, rendered on demand and filed as GitHub issues), and the one shared
            # `corpus-map.overlay.json` (#247), whose keys generate.produce has just written out as
            # `overlay/<entry id>.json`. Each is deleted only if the bytes say it may be.
            for line in remove_retired(args.name, out):
                print(line)
            provenance.emit(model, out)
        # Provenance is written last, outside the recorder: every step above is in `generated`.
        document = provenance.build(state, result, model, recorder)
        provenance.write(out, document)
        print(f"wrote {provenance.FILE_NAME}: factory {state['version']}{' (dirty)' if state['dirty'] else ''}, "
              f"{len(document['generated'])} generated files")
        overridden = None

        def record_lock_files():
            provenance.write(out, provenance.build(state, result, model, recorder))
            print(f"rewrote {provenance.FILE_NAME}: the lock files restore wrote are build inputs")
        if args.no_verify:
            # Nothing is built or tested, but lock files that resolve other versions than the pins just
            # generated are never committed: restore alone re-locks them, or the run is refused
            # (verify.py, `stale_locks`, `relock`).
            if getattr(args, "check_locks", True):
                overridden = relock_stale_locks(out, args, record_lock_files)
            print(f"verification SKIPPED (--no-verify): the engine was not built or tested, so this "
                  f"run ends NOT VERIFIED and exits {NOT_VERIFIED}, never 0")
        else:
            # #94: a run that moved the generated pins re-locks (verify.py). The lock files are
            # engine-owned, and this is the one case produce rewrites them (ownership.py, 0018).
            relock = verify_step.pins_changed(pins_before, verify_step.read_pins(out))
            overridden = verify_step.verify_staged(out, recompute_provenance, args.package, log=sys.stdout,
                                                   after_restore=record_lock_files, relock=relock)
        # The same expression decides the guard and the word on the last line, so the two can never
        # drift apart: a run that will say "verified" is held to every input verify built and tested
        # (transaction.Stage.drift, #335), and a --no-verify run, which claims nothing about a build,
        # is held only to the paths it writes, as before.
        added, changed, removed = stage.commit(verified=not args.no_verify)

    if getattr(args, "produce_report", None):
        write_produce_report(args.produce_report, before, document, added, changed, removed)
        print(f"wrote the produce report to {args.produce_report}: what moved, the changed paths by "
              f"ownership class, and the provenance diff")

    def is_lock(path):
        return path.endswith("/packages.lock.json") or path == "packages.lock.json"
    locks = [path for path in added if is_lock(path)]
    if locks:
        print(f"added {len(locks)} packages.lock.json file(s) written by restore: review and commit them")
    relocked = [path for path in changed if is_lock(path)]
    if relocked:
        print(f"re-locked {len(relocked)} packages.lock.json file(s) because the generated pins changed: "
              f"review and commit them")
    # The last line is what a caller reads, and it must agree with the exit code: a --no-verify run
    # names the code it ends with, so "NOT VERIFIED" and "exit 0" can never be read together.
    print(f"produced {args.name} in {args.out}, {'NOT VERIFIED' if args.no_verify else 'verified'}"
          f"{overridden_suffix(overridden, verify_step.pinned_sdk(args.out), 'lock files re-locked' if args.no_verify else '')}"
          f"{f' -- nothing was built or tested, so this run exits {NOT_VERIFIED}, not 0' if args.no_verify else ''}")
    # produce writes files and runs no git in the engine: say so where --out is a git checkout,
    # so nobody reads "wrote to <engine>" as a commit that was made for them (transaction.py).
    transaction.git_note(args.out, log=sys.stdout)
    return document


#: The produce report's shape (#193). 1 is the first.
REPORT_FORMAT = 1
#: The four values `.github/pull_request_template.md`'s `## Produced by the factory` section asks
#: for, under the labels it asks for them under, so a factory update's pull request is filled in
#: from the run rather than from memory -- and `tools/pr-policy.py` checks three of them against the
#: engine's own provenance.json, which is where a retyped version would be caught anyway.
DECLARATION_FIELDS = ("factory version", "map package and version", "kernel version", "what moved")


def read_record(engine_dir):
    """`engine_dir`'s provenance.json, or {} when there is none to read.

    {} for an unreadable record and not a refusal: produce is about to write a new one, and a
    report that says "this engine had no readable record before" is true and useful, where a run
    refused over the old record would be a produce blocked by the state it is replacing.
    """
    try:
        with open(os.path.join(engine_dir, provenance.FILE_NAME), encoding="utf-8") as handle:
            record = json.load(handle)
        return record if isinstance(record, dict) else {}
    except (OSError, ValueError):
        return {}


def moved(before, after):
    """One line per input that is not what it was: the map version, the kernel, the factory.

    Only what moved. A run that regenerates an engine from the same inputs (a recipe change, or a
    re-produce after an overlay edit) says so, rather than listing three facts that all stayed
    still and leaving a reader to compare them.
    """
    lines = []
    for what, path in (("the map", ("map", "version")), ("the kernel", ("kernel", "version")),
                       ("the factory", ("factory", "version"))):
        was, now = before, after
        for key in path:
            was, now = (was or {}).get(key), (now or {}).get(key)
        if was != now:
            lines.append(f"{what}, {was if was is not None else 'nothing recorded'} to {now}")
    return lines


def remove_retired(name, out):
    """Delete what the factory used to write and no longer does, in the staging copy; the lines to log.

    Silent when there is nothing to remove, which is every engine produced since the retirement.
    One line per retired pattern that matched something, naming the pattern, how many files went
    and why -- so the run says what it did, rather than leaving a reader to find nineteen deletions
    in the diff and work out who made them.

    **And every match this run would not delete is named, by path.** A file under a retired pattern
    that provenance.json never recorded, or whose bytes have moved since it did, is not the
    factory's to remove (ownership.remove_retired) -- but it is now under a pattern nothing
    maintains, which its owner cannot know unless they are told here.
    """
    removed, kept = ownership.remove_retired(out, name)
    lines = []
    for row in ownership.RETIRED:
        matched = [p for p in removed if ownership.retired(p, name) == row]
        if matched:
            lines.append(f"--- removed {len(matched)} file(s) matching the retired pattern {row.pattern}, which "
                         f"`produce` no longer writes: {row.reason}")
    for path, why in kept:
        lines.append(f"--- kept {path}: it matches the retired pattern "
                     f"{ownership.retired(path, name).pattern}, but {why}, so it is yours and not this "
                     f"run's to remove. Nothing writes or checks it any more")
    return lines


def classified_paths(name, added, changed, removed):
    """Every path this run put in place, with how it changed and which ownership class it is in.

    The class comes from ownership.py, the one table produce itself wrote these files by, so a
    reader of the report and `tools/pr-policy.py` reading the pull request are answering from the
    same rows. `class: "retired"` is a path the factory used to write and **this run deleted**
    (ownership.RETIRED): a class of change rather than of file, named so that a migration's
    deletions read as the factory's. It is only ever reported against `removed`, because a retired
    pattern is not something the factory writes -- a file appearing or changing under one is
    somebody's own, and calling it retired would say the opposite of what this section is for.
    `class: null` is a path the table does not classify at all: the lock files a restore wrote are
    engine-owned rows and do classify, so a null here is something to look at.
    """
    out = []
    for how, paths in (("added", added), ("changed", changed), ("removed", removed)):
        for path in paths:
            try:
                row = ownership.classify(path, name)
            except ownership.OwnershipError:
                row = None
            gone = how == "removed" and ownership.retired(path, name) is not None
            out.append({"path": path, "change": how,
                        "class": row.cls if row else ("retired" if gone else None)})
    return sorted(out, key=lambda item: item["path"].encode("utf-8"))


def write_produce_report(path, before, after, added, changed, removed):
    """The report `--produce-report` writes: what this run did, as JSON (#193).

    A `factory produce` update to an engine is a pull request under that engine's rails, and its
    template asks what moved, from what to what, and what the run wrote. Every one of those facts
    is known here, at the moment the run makes them, and nowhere else afterwards except by
    reconstruction from the diff. So the run writes them down.

    `provenanceDiff` is provenance.diff() over the two records, field by field and including
    `recipes[]`, which is the same comparison `factory provenance` reports mismatches with. It is
    reused rather than re-derived: two answers to "how does this record differ from that one" can
    disagree, and then a reader has to decide which to believe.
    """
    report = {
        "reportFormat": REPORT_FORMAT,
        "engine": after.get("engine") or {},
        "factory": after.get("factory") or {},
        "map": {"packageId": (after.get("map") or {}).get("packageId"),
                "from": (before.get("map") or {}).get("version"),
                "to": (after.get("map") or {}).get("version")},
        "kernel": {"packageId": (after.get("kernel") or {}).get("packageId"),
                   "from": (before.get("kernel") or {}).get("version"),
                   "to": (after.get("kernel") or {}).get("version")},
        "moved": moved(before, after),
        "paths": classified_paths((after.get("engine") or {}).get("name") or "", added, changed, removed),
        "provenanceDiff": provenance.diff(before, after) if before else [],
    }
    report["declaration"] = dict(zip(DECLARATION_FIELDS, (
        report["factory"].get("version"),
        f"{report['map']['packageId']} {report['map']['to']}",
        report["kernel"].get("to"),
        "; ".join(report["moved"]) or "nothing: this run reproduced the engine from the inputs it already had",
    )))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def overridden_suffix(overridden, pinned, what=""):
    """What the last line adds when dotnet ran on $FACTORY_DOTNET_SDK_OVERRIDE (verify.py); `what` names
    what ran, where the line does not already say (a --no-verify produce's relock)."""
    if not overridden:
        return ""
    return f"{', ' + what if what else ''} on SDK {overridden} by {verify_step.SDK_OVERRIDE}, not the pinned {pinned}"


def relock_stale_locks(out, args, record_lock_files):
    """A --no-verify produce's lock files, made to agree with the generated pins (verify.py).

    Nothing happens when they agree. Otherwise they are re-locked (`verify.relock`), compared again
    and recorded; a relock that cannot run, fails, or leaves them disagreeing is refused, naming the
    command that works. Returns the SDK override the relock ran on, or None."""
    pinned = verify_step.read_pins(out)
    stale = verify_step.stale_locks(out, pinned)
    if not stale:
        return None
    lines = describe_stale(stale)
    # Nothing is announced before the relock runs: a run with no SDK is refused before any restore,
    # and a line saying restore re-locks them would be false there. `relock` prints its own line once
    # an SDK runs, and this function prints what it re-locked once they agree.
    override, sdk = verify_step.sdk_override(), verify_step.pinned_sdk(out)
    overridden = override if override is not None and override != sdk else None
    if overridden:
        print(verify_step.override_warning(overridden, sdk))
    refused = (f"--no-verify must re-lock the lock files that disagree with the generated pins in "
               f"{verify_step.PACKAGES_PROPS} ({lines}), and ")
    try:
        verify_step.relock(out, sys.stdout)
    except verify_step.Failed as error:
        if not error.sdk_missing:
            raise intake_step.Refused(f"{refused}the re-lock failed: {error.message}. Fix what restore reports, "
                                      f"then run `{produce_command(args, override)}`")
        installed = [version for version in verify_step.installed_sdks() if version != override]
        if installed:
            how = (f"the SDK {override or sdk} that {verify_step.SDK_OVERRIDE if override else 'global.json'} "
                   f"selects is not installed ({error.message}); with one that is, run "
                   f"`{produce_command(args, installed[-1])}`")
        else:
            how = (f"no .NET SDK can run here ({error.message}); install the .NET SDK {sdk}, then run "
                   f"`{produce_command(args, None)}`")
        raise intake_step.Refused(refused + how)
    still = verify_step.stale_locks(out, pinned)
    if still:
        raise intake_step.Refused(f"{refused}after re-locking they still disagree ({describe_stale(still)}), so "
                                  f"nothing is written out")
    print(f"--no-verify: re-locked the lock files that disagreed with the generated pins in "
          f"{verify_step.PACKAGES_PROPS} ({lines})")
    record_lock_files()
    return overridden


def describe_stale(stale):
    return "; ".join(f"{path}: {package} locked at {locked}, pinned at {version}"
                     for path, package, locked, version in stale)


def produce_command(args, override):
    """The --no-verify produce command `args` describes, run under `override` when given."""
    corpora = args.corpus if isinstance(args.corpus, (list, tuple)) else [args.corpus]
    argv = ["python3", "tools/factory", "produce", "--package", args.package]
    for path in corpora:
        argv += ["--corpus", path]
    argv += ["--name", args.name, "--out", args.out]
    for flag, values in (("--adopt", getattr(args, "adopt", None)), ("--reset", getattr(args, "reset", None))):
        for value in values or ():
            argv += [flag, value]
    if getattr(args, "allow_dirty", False):
        argv.append("--allow-dirty")
    argv.append("--no-verify")
    return (f"{verify_step.SDK_OVERRIDE}={shlex.quote(override)} " if override else "") + shlex.join(argv)


def recompute_provenance(engine_dir, package=None):
    """Every provenance field of `engine_dir` that re-producing does not reproduce; [] when all match."""
    def produce_into(spec, corpora, name, out):
        with contextlib.redirect_stdout(io.StringIO()):
            return produce(argparse.Namespace(package=spec, corpus=corpora, name=name, out=out, allow_dirty=True,
                                              no_verify=True, check_locks=False))
    return provenance.recompute(engine_dir, produce_into, package)


def check_provenance(args):
    mismatches = recompute_provenance(args.engine, args.package)
    for line in mismatches:
        print(f"MISMATCH {line}")
    if mismatches:
        print(f"provenance of {args.engine}: {len(mismatches)} mismatch(es)")
        return 1
    print(f"provenance of {args.engine}: every field matches")
    return 0


def render_backlog(args):
    """`backlog --render`: the backlog of an engine, rendered now from its map package and overlay.

    Nothing is sent anywhere and nothing in the engine is written. Without `--to` the whole
    rendering goes to stdout as one Markdown document, index first, so it can be piped, paged or
    redirected. With `--to` the item files are written there, which is what a reader who wants the
    links between items to resolve needs -- and a `--to` inside the engine is refused unless the
    engine ignores every file it would write, is not the engine root, and passes through no symlink
    (backlog.refuse_unignored, #243).
    """
    rendered, _ = backlog_step.engine_backlog(args.dir, args.package)
    if args.to:
        # Every name the run would touch -- what it writes, and the stale items it would delete --
        # is known before anything happens, and the gate is asked about each: an ignored directory
        # can hold a tracked child, and a deletion is a change to the engine as much as a write
        # (backlog.refuse_unignored, #243).
        touched = list(rendered) + backlog_step.stale_names(args.to, rendered)
        backlog_step.refuse_unignored(args.dir, args.to, touched)
        written = backlog_step.write_rendered(rendered, args.to)
        print(f"--- backlog: {len(written) - 1} item(s) and an index written to {args.to}")
        return 0
    sys.stdout.write(backlog_step.document(rendered))
    return 0


def build_parser():
    """The CLI. README.md's status table is checked against this (tools/check-readme-status.py)."""
    parser = argparse.ArgumentParser(prog="factory", description="Produce a rules engine from a corpus-map package.")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("produce", help="intake a map package and produce an engine")
    p.add_argument("--package", required=True, help="a .nupkg path, or Id@Version")
    p.add_argument("--corpus", required=True, action="append", metavar="FILE",
                   help="a corpus file the map cites; repeat once per cited corpus (0039)")
    p.add_argument("--name", required=True, help="PascalCase engine name")
    p.add_argument("--out", required=True, help="directory the engine is written to")
    p.add_argument("--allow-dirty", action="store_true",
                   help="produce from a factory with uncommitted changes, recording dirty: true")
    p.add_argument("--no-verify", action="store_true",
                   help="write the engine without `verify` (no .NET SDK here); the output says it is not verified "
                        f"and the run exits {NOT_VERIFIED} (NOT VERIFIED), never 0")
    p.add_argument("--adopt", action="append", metavar="PATH",
                   help="make this managed file (global.json, NuGet.config, Directory.Build.props) engine-owned, "
                        "keeping its edits; repeatable (tools/factory/ownership.py)")
    p.add_argument("--reset", action="append", metavar="PATH",
                   help="overwrite this managed or adopted file with the current recipe and make it managed; repeatable")
    p.add_argument("--produce-report", metavar="FILE",
                   help="write a JSON report of this run: what moved (map, kernel, factory) from what to what, every "
                        "path written with its ownership class, and the provenance diff. A factory update's pull "
                        "request is filled in from it (#193)")
    b = commands.add_parser("backlog", help="file an engine's backlog as GitHub issues, or render it")
    action = b.add_mutually_exclusive_group(required=True)
    action.add_argument("--create", action="store_true",
                        help="create missing issues and update changed ones; needs --repo")
    action.add_argument("--render", action="store_true",
                        help="print the backlog as one Markdown document, or write its files to --to; sends nothing")
    b.add_argument("--repo", help="owner/name of the engine's repository (--create)")
    b.add_argument("--dir", required=True, help="the engine directory `produce` wrote")
    b.add_argument("--to", metavar="DIR",
                   help="with --render, write the item files here instead of printing them; a directory inside the "
                        "engine is refused unless the engine ignores it (#243)")
    b.add_argument("--package", help="the .nupkg whose manifest and map the backlog is rendered from and the bodies "
                                      "checked against: the corpus licence's attribution (decision 0023) (default: "
                                      "Id@Version from provenance.json, from the NuGet global packages folder)")
    l = commands.add_parser("rails", help="report, or put in place, the rails GitHub itself enforces")
    l.add_argument("--repo", required=True, help="owner/name of the engine's repository")
    l.add_argument("--dir", required=True, help="the engine directory `produce` wrote")
    mode = l.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report what is in place and change nothing")
    mode.add_argument("--apply", action="store_true",
                     help="create the labels and the factory's own branch ruleset, and restrict merging to merge "
                          "commits; idempotent, and it never writes another ruleset")
    r = commands.add_parser("provenance", help="recompute an engine's provenance.json and report mismatches")
    r.add_argument("--engine", required=True, help="the engine directory")
    r.add_argument("--package", help="the .nupkg or Id@Version (default: Id@Version from provenance.json)")
    v = commands.add_parser("verify", help="prove an engine: provenance, restore if unlocked, then its gate")
    v.add_argument("--engine", required=True, help="the engine directory")
    v.add_argument("--package", help="the .nupkg or Id@Version (default: Id@Version from provenance.json)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "backlog":
            if args.render:
                if args.repo:
                    raise intake_step.Usage("--repo is for --create; --render sends nothing anywhere")
                return render_backlog(args)
            if not args.repo:
                raise intake_step.Usage("--create needs --repo <owner/name>")
            if args.to:
                raise intake_step.Usage("--to is for --render; --create writes issues, not files")
            if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", args.repo):
                raise intake_step.Usage(f"--repo {args.repo!r} is not owner/name")
            backlog_step.create(args.repo, args.dir, log=sys.stdout, gh=os.environ.get("FACTORY_GH", "gh"),
                                package=args.package)
            return 0
        if args.command == "rails":
            return rails_step.run(args.repo, args.dir, os.environ.get("FACTORY_GH", "gh"), sys.stdout, args.apply)
        if args.command == "provenance":
            return check_provenance(args)
        if args.command == "verify":
            overridden = verify_step.verify(args.engine, recompute_provenance, args.package, log=sys.stdout)
            print(f"verify {args.engine}: PASS" + overridden_suffix(overridden, verify_step.pinned_sdk(args.engine)))
            return 0
        produce(args)
        # An engine that was written but never built or tested is not a success to a caller reading
        # the exit code, and `--no-verify` stays a usable, documented mode: it ends NOT VERIFIED (3),
        # which a caller that meant to skip verification accepts explicitly.
        return NOT_VERIFIED if args.no_verify else 0
    except intake_step.Usage as error:
        print(f"factory: {error}", file=sys.stderr)
        return 2
    except rails_step.RailsError as error:
        # Not "nothing was produced": `rails` produces nothing either way, and `--apply` may have
        # made some of its changes before the one that failed. Every change it makes is idempotent,
        # so the fix is to re-run it once the reason is gone.
        print(f"factory: rails REFUSED -- {error}", file=sys.stderr)
        return 1
    except (intake_step.Refused, generate.GenerationError, backlog_step.BacklogError) as error:
        print(f"factory: REFUSED -- {error}. Nothing was produced.", file=sys.stderr)
        return 1
    except verify_step.Failed as error:
        # In produce, verify runs in the staging copy, which is discarded: --out is untouched.
        nothing = " Nothing was produced." if args.command == "produce" else ""
        print(f"factory: verify FAILED at stage {error.stage} -- {error.message}.{nothing}", file=sys.stderr)
        return 1
    except transaction.CommitError as error:
        if error.rolled_back:
            print(f"factory: FAILED -- {error}; --out is as it was before this run.", file=sys.stderr)
        else:
            print(f"factory: FAILED -- {error}. --out is partly written.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
