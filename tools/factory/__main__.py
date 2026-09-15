#!/usr/bin/env python3
"""The rules factory (#3): produce a .NET engine from a published corpus-map package.

  python3 tools/factory produce --package <nupkg path | Id@Version> --corpus <file>
                                --name <PascalName> --out <dir> [--no-verify]
  python3 tools/factory backlog --create --repo <owner/name> --dir <engine dir>

`produce` runs, in order, and stops at the first refusal. Every step writes into a staging copy
of `--out`, and the result is committed to `--out` only after the last step passed, so a
refusal leaves `--out` byte-identical to how it started (transaction.py, #67):

  * intake (intake.py) -- the package is a map package carrying its checker, the map's
    `schemaVersion` is one the factory reads, the corpus is `committed-copy` and hashes to the
    map's baseline, and the factory's own `tools/check-map.py --phase consumer` passes on the
    packaged map. Nothing from the package is ever run (0016): its checker is hashed, not
    executed;
  * scaffold and generation (generate.py) -- a .NET solution on RulesKernel and the map
    package, each file in one ownership class (ownership.py): managed build policy, updated
    with its recipe and refused when hand-edited unless `--adopt PATH` or `--reset PATH`;
    engine-owned files, written once; and the generated files, rewritten
    every run: the `*.g.cs` from the package map merged with the engine's
    `corpus-map.overlay.json`, and `RulesFactory.Packages.g.props`, which pins RulesKernel and
    the map package at the versions given and references the map;
  * the gate recipe (gate.py) -- scripts/validate.sh and the scripts and CI workflow it runs,
    rewritten every run;
  * backlog (backlog.py) -- `backlog/NNN-<entry-id>.md`, one per entry still to build, in
    dependsOn order, and `backlog/README.md`, rewritten every run;
  * provenance (provenance.py), last -- `provenance.json` in the engine root, embedded in the
    engine. Before anything else, a factory whose git working tree is dirty is refused unless
    `--allow-dirty`;
  * verify (verify.py), in the staging copy, before anything is committed -- the engine is
    proven, as below, so a failure leaves `--out` as it was and only a verified engine is ever
    committed. The lock files restore writes are committed with it (bin/ and obj/ never are).
    When restore writes lock files there, provenance.json is rewritten before the gate builds
    to record them as build inputs (#69), so what is committed is what the gate tested.
    When the run changed the generated pins (a map version bump) and lock files exist, verify
    re-locks them first (#94); that is the one case produce rewrites engine-owned files.
    `--no-verify` skips it, for a machine without the SDK the engine pins, and the output and
    the final line say the engine was committed unverified. A `--no-verify` run whose committed lock
    files resolve a pinned package (RulesKernel, RulesKernel.Randomness, the map) at another version
    than the generated pins re-locks them with `dotnet restore` alone, on the pinned SDK or
    `FACTORY_DOTNET_SDK_OVERRIDE`, and records them. When no SDK can run, restore fails, or the lock
    files still disagree, it is refused, naming each lock file, package and both versions, and the
    command that works. Lock files that agree are committed as they are;
  * commit (transaction.py) -- the files the steps added, changed or removed are put in place
    in `--out`, journaled and rolled back on failure (a fresh `--out` is one rename).

`backlog --create` synchronises those files with GitHub issues through `gh` (or `$FACTORY_GH`):
each file is matched to its issue by the entry marker in its body, never by title, and the
issue is created, updated, or left unchanged. It never closes or deletes an issue. Before any
call it reads the map package provenance.json records (`--package`, or Id@Version from the NuGet
global packages folder): when the corpus's licence requires attribution, a body without the
statement is refused (decision 0023); for a licensed local-copy corpus, a body quoting it (0022).

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

`produce`, `verify` and `provenance` take `--licensed-copy-exception` (decision 0022, #105):
outside CI, and only when `gh api user` (or `$FACTORY_GH`) is authenticated as a login in
tools/factory/licensed-copy-operators.json, intake admits a licensed `local-copy` corpus, hashing
the local file (`--corpus`, or for a re-produce the manifest's `envVar`) against the baseline. No
corpus bytes are copied into the engine, provenance records `licensedCopyException`, and every
line that would say verified says `verified locally under the licensed-copy exception by <login>`.
Without the flag nothing differs. See licensed_copy.py.

Exit 0 when every step passed; 1 when a step refused; 2 on a usage error.
Standard library only.
"""
import argparse
import contextlib
import io
import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backlog as backlog_step  # noqa: E402
import gate  # noqa: E402
import generate  # noqa: E402
import intake as intake_step  # noqa: E402
import licensed_copy  # noqa: E402
import provenance  # noqa: E402
import transaction  # noqa: E402
import verify as verify_step  # noqa: E402

PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def produce(args):
    if not PASCAL.match(args.name):
        raise intake_step.Usage(f"--name {args.name!r} is not a PascalCase C# identifier")
    state = provenance.factory_state()
    provenance.require_clean(state, args.allow_dirty)
    # Every step writes into `out`, a staging copy of --out; --out itself is only touched by
    # commit(), after the last step passed (transaction.py).
    with transaction.Stage(args.out, log=sys.stdout) as stage:
        out = stage.root
        # The pins the engine had before this run: the staging copy is still --out as it was.
        pins_before = verify_step.read_pins(out)
        with provenance.Recorder(out) as recorder:
            result = intake_step.intake(args.package, args.corpus, log=sys.stdout,
                                        licensed_copy_operator=getattr(args, "licensed_copy_operator", None))
            print(f"intake passed: {result.package_id} {result.version}, {len(result.map.get('entries') or [])} entries")
            model = generate.produce(result, args.name, out, log=sys.stdout,
                                     adopt=getattr(args, "adopt", None) or (), reset=getattr(args, "reset", None) or ())
            gate.emit(args.name, out, log=sys.stdout)
            context = {"name": args.name, "package": result.package_id, "version": result.version}
            if result.corpus.get("verification") == "local-copy":
                context["localCopy"] = True  # decision 0022: the backlog quotes nothing from the corpus
            else:
                credit = backlog_step.attribution(result.corpus)  # decision 0023: quotations carry their attribution
                if credit:
                    context["attribution"] = credit
            written = backlog_step.emit([item["entry"] for item in model.entries], context, out)
            print(f"--- backlog: {len(written) - 1} item(s)")
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
            print("verification SKIPPED (--no-verify): the engine was not built or tested")
        else:
            # #94: a run that moved the generated pins re-locks (verify.py). The lock files are
            # engine-owned, and this is the one case produce rewrites them (ownership.py, 0018).
            relock = verify_step.pins_changed(pins_before, verify_step.read_pins(out))
            overridden = verify_step.verify_staged(out, lambda engine, package: recompute_provenance(
                                          engine, package, getattr(args, "licensed_copy_operator", None)),
                                      args.package, log=sys.stdout, after_restore=record_lock_files, relock=relock)
        added, changed, _ = stage.commit()

    def is_lock(path):
        return path.endswith("/packages.lock.json") or path == "packages.lock.json"
    locks = [path for path in added if is_lock(path)]
    if locks:
        print(f"added {len(locks)} packages.lock.json file(s) written by restore: review and commit them")
    relocked = [path for path in changed if is_lock(path)]
    if relocked:
        print(f"re-locked {len(relocked)} packages.lock.json file(s) because the generated pins changed: "
              f"review and commit them")
    for line in ruling_record_notes(document, args.out):
        print(line)
    print(f"produced {args.name} in {args.out}, {'NOT VERIFIED' if args.no_verify else verified(document)}"
          f"{overridden_suffix(overridden, verify_step.pinned_sdk(args.out), 'lock files re-locked' if args.no_verify else '')}")
    return document


def ruling_record_notes(document, engine_dir):
    """One line per decision record a ruling names (0027): provenance.json has just hashed it, so an edit
    after this produce leaves `recordSha256` stale, and nothing says so until `factory verify`. A WARNING
    when git reports the record uncommitted in `engine_dir`, which is when such an edit usually follows."""
    lines, seen = [], set()
    for ruling in (document.get("rulings") if isinstance(document, dict) else None) or []:
        record = ruling.get("record")
        if record in seen:
            continue
        seen.add(record)
        ids = ", ".join(r.get("id") for r in document["rulings"] if r.get("record") == record)
        try:
            done = subprocess.run(["git", "status", "--porcelain", "--", record], cwd=engine_dir, capture_output=True,
                                  text=True, timeout=30)
            pending = done.returncode == 0 and bool(done.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pending = False
        lines.append(f"{'WARNING' if pending else 'note'}: provenance.json hashes the decision record {record} "
                     f"({ids}) as it stands now{', with changes git has not committed' if pending else ''}. Commit "
                     f"it exactly so: an edit after this produce leaves rulings[...].recordSha256 stale, and "
                     f"`factory verify` fails until `factory produce` runs again")
    return lines


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
                                  f"nothing is committed")
    print(f"--no-verify: re-locked the lock files that disagreed with the generated pins in "
          f"{verify_step.PACKAGES_PROPS} ({lines})")
    record_lock_files()
    return overridden


def describe_stale(stale):
    return "; ".join(f"{path}: {package} locked at {locked}, pinned at {version}"
                     for path, package, locked, version in stale)


def produce_command(args, override):
    """The --no-verify produce command `args` describes, run under `override` when given."""
    argv = ["python3", "tools/factory", "produce", "--package", args.package, "--corpus", args.corpus,
            "--name", args.name, "--out", args.out]
    for flag, values in (("--adopt", getattr(args, "adopt", None)), ("--reset", getattr(args, "reset", None))):
        for value in values or ():
            argv += [flag, value]
    if getattr(args, "allow_dirty", False):
        argv.append("--allow-dirty")
    if getattr(args, "licensed_copy_exception", False):
        argv.append(licensed_copy.FLAG)
    argv.append("--no-verify")
    return (f"{verify_step.SDK_OVERRIDE}={shlex.quote(override)} " if override else "") + shlex.join(argv)


def verified(document):
    """How a verified engine is described: plainly, or under the licensed-copy exception (0022)."""
    exception = document.get("licensedCopyException") if isinstance(document, dict) else None
    if isinstance(exception, dict) and exception.get("operator"):
        return licensed_copy.attestation(exception["operator"])
    return "verified"


def recorded_provenance(engine_dir):
    try:
        with open(os.path.join(engine_dir, provenance.FILE_NAME), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def recompute_provenance(engine_dir, package=None, licensed_copy_operator=None):
    """Every provenance field of `engine_dir` that re-producing does not reproduce; [] when all match.

    `licensed_copy_operator` is the login main() established for --licensed-copy-exception, or None.
    """
    def produce_into(spec, corpus, name, out):
        with contextlib.redirect_stdout(io.StringIO()):
            return produce(argparse.Namespace(package=spec, corpus=corpus, name=name, out=out, allow_dirty=True,
                                              no_verify=True, check_locks=False,
                                              licensed_copy_operator=licensed_copy_operator))
    return provenance.recompute(engine_dir, produce_into, package)


def check_provenance(args):
    mismatches = recompute_provenance(args.engine, args.package, args.licensed_copy_operator)
    for line in mismatches:
        print(f"MISMATCH {line}")
    if mismatches:
        print(f"provenance of {args.engine}: {len(mismatches)} mismatch(es)")
        return 1
    document = recorded_provenance(args.engine)
    suffix = "" if verified(document) == "verified" else f", {verified(document)}"
    print(f"provenance of {args.engine}: every field matches{suffix}")
    return 0


def build_parser():
    """The CLI. README.md's status table is checked against this (tools/check-readme-status.py)."""
    parser = argparse.ArgumentParser(prog="factory", description="Produce a rules engine from a corpus-map package.")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("produce", help="intake a map package and produce an engine")
    p.add_argument("--package", required=True, help="a .nupkg path, or Id@Version")
    p.add_argument("--corpus", required=True, help="the corpus file the map was made of")
    p.add_argument("--name", required=True, help="PascalCase engine name")
    p.add_argument("--out", required=True, help="directory the engine is written to")
    p.add_argument("--allow-dirty", action="store_true",
                   help="produce from a factory with uncommitted changes, recording dirty: true")
    p.add_argument("--no-verify", action="store_true",
                   help="commit the engine without `verify` (no .NET SDK here); the output says it is not verified")
    p.add_argument("--adopt", action="append", metavar="PATH",
                   help="make this managed file (global.json, NuGet.config, Directory.Build.props) engine-owned, "
                        "keeping its edits; repeatable (tools/factory/ownership.py)")
    p.add_argument("--reset", action="append", metavar="PATH",
                   help="overwrite this managed or adopted file with the current recipe and make it managed; repeatable")
    exception_help = ("an allowlisted operator (gh api user) uses a licensed local-copy corpus on their own machine; "
                      "refused in CI (decision 0022)")
    p.add_argument(licensed_copy.FLAG, dest="licensed_copy_exception", action="store_true", help=exception_help)
    b = commands.add_parser("backlog", help="create or update GitHub issues from an engine's backlog/ files")
    b.add_argument("--create", action="store_true", required=True, help="create missing issues and update changed ones (the only action)")
    b.add_argument("--repo", required=True, help="owner/name of the engine's repository")
    b.add_argument("--dir", required=True, help="the engine directory `produce` wrote")
    b.add_argument("--package", help="the .nupkg whose manifest and map the bodies are checked against: the corpus "
                                      "licence's attribution (decision 0023), and for a licensed local-copy corpus, "
                                      "no quoted text (0022) (default: Id@Version from provenance.json, from the "
                                      "NuGet global packages folder)")
    r = commands.add_parser("provenance", help="recompute an engine's provenance.json and report mismatches")
    r.add_argument("--engine", required=True, help="the engine directory")
    r.add_argument("--package", help="the .nupkg or Id@Version (default: Id@Version from provenance.json)")
    r.add_argument(licensed_copy.FLAG, dest="licensed_copy_exception", action="store_true", help=exception_help)
    v = commands.add_parser("verify", help="prove an engine: provenance, restore if unlocked, then its gate")
    v.add_argument("--engine", required=True, help="the engine directory")
    v.add_argument("--package", help="the .nupkg or Id@Version (default: Id@Version from provenance.json)")
    v.add_argument(licensed_copy.FLAG, dest="licensed_copy_exception", action="store_true", help=exception_help)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        # Decision 0022: the identity is established once, before anything is read, and only when asked.
        args.licensed_copy_operator = (licensed_copy.authorise() if getattr(args, "licensed_copy_exception", False)
                                       else None)
        if args.command == "backlog":
            if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", args.repo):
                raise intake_step.Usage(f"--repo {args.repo!r} is not owner/name")
            backlog_step.create(args.repo, args.dir, log=sys.stdout, gh=os.environ.get("FACTORY_GH", "gh"),
                                package=args.package)
            return 0
        if args.command == "provenance":
            return check_provenance(args)
        if args.command == "verify":
            overridden = verify_step.verify(args.engine, lambda engine, package: recompute_provenance(
                engine, package, args.licensed_copy_operator), args.package, log=sys.stdout)
            document = recorded_provenance(args.engine)
            print(f"verify {args.engine}: PASS" + ("" if verified(document) == "verified"
                                                   else f", {verified(document)}")
                  + overridden_suffix(overridden, verify_step.pinned_sdk(args.engine)))
            return 0
        produce(args)
        return 0
    except intake_step.Usage as error:
        print(f"factory: {error}", file=sys.stderr)
        return 2
    except (intake_step.Refused, generate.GenerationError, backlog_step.BacklogError, licensed_copy.Refused) as error:
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
