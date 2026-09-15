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
    the final line say the engine was committed unverified;
  * commit (transaction.py) -- the files the steps added, changed or removed are put in place
    in `--out`, journaled and rolled back on failure (a fresh `--out` is one rename).

`backlog --create` synchronises those files with GitHub issues through `gh` (or `$FACTORY_GH`):
each file is matched to its issue by the entry marker in its body, never by title, and the
issue is created, updated, or left unchanged. It never closes or deletes an issue.

  python3 tools/factory provenance --engine <dir> [--package <nupkg path | Id@Version>]

re-produces the engine in a scratch copy and names every provenance field that does not match
(exit 1), or says it matches (exit 0). `recompute_provenance` is the same, as a function.

  python3 tools/factory verify --engine <dir> [--package <nupkg path | Id@Version>]

runs the stages that make an engine acceptable and names the first that fails: provenance
recomputes; `dotnet restore` writes the lock files if the engine has none (standalone verify
never re-locks existing ones; only produce does, when it changed the pins); and the engine's own
gate (`scripts/validate.sh full`: locked restore, -warnaserror build and tests in Debug and
Release, format, regeneration, posture, ...) passes. `dotnet` is `$FACTORY_DOTNET` when set.
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
            written = backlog_step.emit([item["entry"] for item in model.entries], context, out)
            print(f"--- backlog: {len(written) - 1} item(s)")
            provenance.emit(model, out)
        # Provenance is written last, outside the recorder: every step above is in `generated`.
        document = provenance.build(state, result, model, recorder)
        provenance.write(out, document)
        print(f"wrote {provenance.FILE_NAME}: factory {state['version']}{' (dirty)' if state['dirty'] else ''}, "
              f"{len(document['generated'])} generated files")
        if args.no_verify:
            print("verification SKIPPED (--no-verify): the engine was not built or tested")
        else:
            def record_lock_files():
                provenance.write(out, provenance.build(state, result, model, recorder))
                print(f"rewrote {provenance.FILE_NAME}: the lock files restore wrote are build inputs")
            # #94: a run that moved the generated pins re-locks (verify.py). The lock files are
            # engine-owned, and this is the one case produce rewrites them (ownership.py, 0018).
            relock = verify_step.pins_changed(pins_before, verify_step.read_pins(out))
            verify_step.verify_staged(out, lambda engine, package: recompute_provenance(
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
    print(f"produced {args.name} in {args.out}, {'NOT VERIFIED' if args.no_verify else verified(document)}")
    return document


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
                                              no_verify=True, licensed_copy_operator=licensed_copy_operator))
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
    b.add_argument("--package", help="for an engine produced from a licensed local-copy corpus (decision 0022): the "
                                      ".nupkg whose map the bodies are checked against (default: Id@Version from "
                                      "provenance.json, from the NuGet global packages folder)")
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
            verify_step.verify(args.engine, lambda engine, package: recompute_provenance(
                engine, package, args.licensed_copy_operator), args.package, log=sys.stdout)
            document = recorded_provenance(args.engine)
            print(f"verify {args.engine}: PASS" + ("" if verified(document) == "verified"
                                                   else f", {verified(document)}"))
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
