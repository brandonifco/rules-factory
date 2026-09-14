#!/usr/bin/env python3
"""The rules factory (#3): produce a .NET engine from a published corpus-map package.

  python3 tools/factory produce --package <nupkg path | Id@Version> --corpus <file>
                                --name <PascalName> --out <dir>
  python3 tools/factory backlog --create --repo <owner/name> --dir <engine dir>

`produce` runs, in order, and stops at the first refusal:

  * intake (intake.py) -- the package is a map package carrying its checker, the corpus is
    `committed-copy` and hashes to the map's baseline, and the package's own
    `check-map.py --phase consumer` passes;
  * scaffold and generation (generate.py) -- a .NET solution on RulesKernel and the map
    package, written once, and the `*.g.cs` files, rewritten every run from the package map
    merged with the engine's `corpus-map.overlay.json`;
  * backlog (backlog.py) -- `backlog/NNN-<entry-id>.md`, one per entry still to build, in
    dependsOn order, and `backlog/README.md`, rewritten every run.

`backlog --create` turns those files into GitHub issues through `gh` (or `$FACTORY_GH`),
skipping any whose title the repository already has.

Later milestones add the gate recipe, provenance and `verify`.

Exit 0 when every step passed; 1 when a step refused; 2 on a usage error.
Standard library only.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backlog as backlog_step  # noqa: E402
import generate  # noqa: E402
import intake as intake_step  # noqa: E402

PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def produce(args):
    if not PASCAL.match(args.name):
        raise intake_step.Usage(f"--name {args.name!r} is not a PascalCase C# identifier")
    result = intake_step.intake(args.package, args.corpus, log=sys.stdout)
    print(f"intake passed: {result.package_id} {result.version}, {len(result.map.get('entries') or [])} entries")
    model = generate.produce(result, args.name, args.out, log=sys.stdout)
    context = {"name": args.name, "package": result.package_id, "version": result.version}
    written = backlog_step.emit([item["entry"] for item in model.entries], context, args.out)
    print(f"--- backlog: {len(written) - 1} item(s)")
    print(f"produced {args.name} in {args.out}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="factory", description="Produce a rules engine from a corpus-map package.")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("produce", help="intake a map package and produce an engine")
    p.add_argument("--package", required=True, help="a .nupkg path, or Id@Version")
    p.add_argument("--corpus", required=True, help="the corpus file the map was made of")
    p.add_argument("--name", required=True, help="PascalCase engine name")
    p.add_argument("--out", required=True, help="directory the engine is written to")
    b = commands.add_parser("backlog", help="create GitHub issues from an engine's backlog/ files")
    b.add_argument("--create", action="store_true", required=True, help="create the issues (the only action)")
    b.add_argument("--repo", required=True, help="owner/name of the engine's repository")
    b.add_argument("--dir", required=True, help="the engine directory `produce` wrote")
    args = parser.parse_args(argv)
    try:
        if args.command == "backlog":
            if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", args.repo):
                raise intake_step.Usage(f"--repo {args.repo!r} is not owner/name")
            backlog_step.create(args.repo, args.dir, log=sys.stdout, gh=os.environ.get("FACTORY_GH", "gh"))
            return 0
        return produce(args)
    except intake_step.Usage as error:
        print(f"factory: {error}", file=sys.stderr)
        return 2
    except (intake_step.Refused, generate.GenerationError, backlog_step.BacklogError) as error:
        print(f"factory: REFUSED -- {error}. Nothing was produced.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
