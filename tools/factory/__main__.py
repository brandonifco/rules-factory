#!/usr/bin/env python3
"""The rules factory (#3): produce a .NET engine from a published corpus-map package.

  python3 tools/factory produce --package <nupkg path | Id@Version> --corpus <file>
                                --name <PascalName> --out <dir>
  python3 tools/factory backlog --create --repo <owner/name> --dir <engine dir>

`produce` runs, in order, and stops at the first refusal:

  * intake (intake.py) -- the package is a map package carrying its checker, the map's
    `schemaVersion` is one the factory reads, the corpus is `committed-copy` and hashes to the
    map's baseline, and the factory's own `tools/check-map.py --phase consumer` passes on the
    packaged map. Nothing from the package is ever run (0016): its checker is hashed, not
    executed;
  * scaffold and generation (generate.py) -- a .NET solution on RulesKernel and the map
    package, written once, and the `*.g.cs` files, rewritten every run from the package map
    merged with the engine's `corpus-map.overlay.json`;
  * backlog (backlog.py) -- `backlog/NNN-<entry-id>.md`, one per entry still to build, in
    dependsOn order, and `backlog/README.md`, rewritten every run;
  * provenance (provenance.py), last -- `provenance.json` in the engine root, embedded in the
    engine. Before anything else, a factory whose git working tree is dirty is refused unless
    `--allow-dirty`.

`backlog --create` turns those files into GitHub issues through `gh` (or `$FACTORY_GH`),
skipping any whose title the repository already has.

  python3 tools/factory provenance --engine <dir> [--package <nupkg path | Id@Version>]

re-produces the engine in a scratch copy and names every provenance field that does not match
(exit 1), or says it matches (exit 0). `recompute_provenance` is the same, as a function.

Later milestones add the gate recipe and `verify`.

Exit 0 when every step passed; 1 when a step refused; 2 on a usage error.
Standard library only.
"""
import argparse
import contextlib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backlog as backlog_step  # noqa: E402
import generate  # noqa: E402
import intake as intake_step  # noqa: E402
import provenance  # noqa: E402

PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def produce(args):
    if not PASCAL.match(args.name):
        raise intake_step.Usage(f"--name {args.name!r} is not a PascalCase C# identifier")
    state = provenance.factory_state()
    provenance.require_clean(state, args.allow_dirty)
    with provenance.Recorder(args.out) as recorder:
        result = intake_step.intake(args.package, args.corpus, log=sys.stdout)
        print(f"intake passed: {result.package_id} {result.version}, {len(result.map.get('entries') or [])} entries")
        model = generate.produce(result, args.name, args.out, log=sys.stdout)
        context = {"name": args.name, "package": result.package_id, "version": result.version}
        written = backlog_step.emit([item["entry"] for item in model.entries], context, args.out)
        print(f"--- backlog: {len(written) - 1} item(s)")
        provenance.emit(model, args.out)
    # Provenance is written last, outside the recorder: every step above is in `generated`.
    document = provenance.build(state, result, model, recorder)
    provenance.write(args.out, document)
    print(f"wrote {provenance.FILE_NAME}: factory {state['version']}{' (dirty)' if state['dirty'] else ''}, "
          f"{len(document['generated'])} generated files")
    print(f"produced {args.name} in {args.out}")
    return document


def recompute_provenance(engine_dir, package=None):
    """Every provenance field of `engine_dir` that re-producing does not reproduce; [] when all match."""
    def produce_into(spec, corpus, name, out):
        with contextlib.redirect_stdout(io.StringIO()):
            return produce(argparse.Namespace(package=spec, corpus=corpus, name=name, out=out, allow_dirty=True))
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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="factory", description="Produce a rules engine from a corpus-map package.")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("produce", help="intake a map package and produce an engine")
    p.add_argument("--package", required=True, help="a .nupkg path, or Id@Version")
    p.add_argument("--corpus", required=True, help="the corpus file the map was made of")
    p.add_argument("--name", required=True, help="PascalCase engine name")
    p.add_argument("--out", required=True, help="directory the engine is written to")
    p.add_argument("--allow-dirty", action="store_true",
                   help="produce from a factory with uncommitted changes, recording dirty: true")
    b = commands.add_parser("backlog", help="create GitHub issues from an engine's backlog/ files")
    b.add_argument("--create", action="store_true", required=True, help="create the issues (the only action)")
    b.add_argument("--repo", required=True, help="owner/name of the engine's repository")
    b.add_argument("--dir", required=True, help="the engine directory `produce` wrote")
    r = commands.add_parser("provenance", help="recompute an engine's provenance.json and report mismatches")
    r.add_argument("--engine", required=True, help="the engine directory")
    r.add_argument("--package", help="the .nupkg or Id@Version (default: Id@Version from provenance.json)")
    args = parser.parse_args(argv)
    try:
        if args.command == "backlog":
            if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", args.repo):
                raise intake_step.Usage(f"--repo {args.repo!r} is not owner/name")
            backlog_step.create(args.repo, args.dir, log=sys.stdout, gh=os.environ.get("FACTORY_GH", "gh"))
            return 0
        if args.command == "provenance":
            return check_provenance(args)
        produce(args)
        return 0
    except intake_step.Usage as error:
        print(f"factory: {error}", file=sys.stderr)
        return 2
    except (intake_step.Refused, generate.GenerationError, backlog_step.BacklogError) as error:
        print(f"factory: REFUSED -- {error}. Nothing was produced.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
