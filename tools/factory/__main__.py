#!/usr/bin/env python3
"""The rules factory (#3): produce a .NET engine from a published corpus-map package.

  python3 tools/factory produce --package <nupkg path | Id@Version> --corpus <file>
                                --name <PascalName> --out <dir>

`produce` runs, in order, and stops at the first refusal:

  * intake (intake.py) -- the package is a map package carrying its checker, the corpus is
    `committed-copy` and hashes to the map's baseline, and the package's own
    `check-map.py --phase consumer` passes.

Later milestones add scaffolding, generation, provenance, the backlog and `verify`.

Exit 0 when every step passed; 1 when a step refused; 2 on a usage error.
Standard library only.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import intake as intake_step  # noqa: E402

PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def produce(args):
    if not PASCAL.match(args.name):
        raise intake_step.Usage(f"--name {args.name!r} is not a PascalCase C# identifier")
    result = intake_step.intake(args.package, args.corpus, log=sys.stdout)
    print(f"intake passed: {result.package_id} {result.version}, {len(result.map.get('entries') or [])} entries")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="factory", description="Produce a rules engine from a corpus-map package.")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("produce", help="intake a map package and produce an engine")
    p.add_argument("--package", required=True, help="a .nupkg path, or Id@Version")
    p.add_argument("--corpus", required=True, help="the corpus file the map was made of")
    p.add_argument("--name", required=True, help="PascalCase engine name")
    p.add_argument("--out", required=True, help="directory the engine is written to")
    args = parser.parse_args(argv)
    try:
        return produce(args)
    except intake_step.Usage as error:
        print(f"factory: {error}", file=sys.stderr)
        return 2
    except intake_step.Refused as error:
        print(f"factory: REFUSED -- {error}. Nothing was produced.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
