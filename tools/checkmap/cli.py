"""The command line: read the map and its manifest, run the selected checks, print each
verdict, and turn them into an exit code.
"""
import argparse
import json
import os
import sys

from .diagnostics import skip
from mapcontract.entry import entries_of
from .phases import CHECKS, OVERLAY_FIELDS, PHASES, STATUS_DEPENDENT


def find_manifest(map_path):
    """The manifest beside the map, when there is exactly one candidate."""
    directory = os.path.dirname(os.path.abspath(map_path)) or "."
    candidates = sorted(
        os.path.join(directory, n)
        for n in os.listdir(directory)
        if n.startswith("corpus-manifest") and n.endswith(".json")
    )
    return candidates[0] if len(candidates) == 1 else None


def find_repo_root(start):
    directory = os.path.dirname(os.path.abspath(start))
    while True:
        if os.path.isdir(os.path.join(directory, "docs", "decisions")) or os.path.isdir(os.path.join(directory, ".git")):
            return directory
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a corpus map against docs/corpus-map.md.")
    parser.add_argument("map_path")
    parser.add_argument("--manifest", help="corpus manifest; found beside the map when unambiguous")
    parser.add_argument("--repo-root", help="root that decision-record paths are relative to")
    parser.add_argument("--only", help="run one check: " + ", ".join(name for name, _ in CHECKS))
    parser.add_argument("--verbose", action="store_true", help="also print the row each entry matches")
    parser.add_argument("--phase", choices=PHASES, default="publish",
                        help="publish (default): every check, before a map may become a version. "
                             "consumer: only the checks an overlay of " + ", ".join(OVERLAY_FIELDS)
                             + " can change, run by an engine on merge(package, overlay) (0015)")
    args = parser.parse_args(argv)

    selected = CHECKS
    if args.phase == "consumer":
        selected = [c for c in CHECKS if c[0] in STATUS_DEPENDENT]
    if args.only:
        selected = [c for c in CHECKS if c[0] == args.only]
        if not selected:
            print(f"unknown check {args.only!r}; known: {', '.join(n for n, _ in CHECKS)}", file=sys.stderr)
            return 2
    try:
        with open(args.map_path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        print(f"cannot read map {args.map_path}: {error}", file=sys.stderr)
        return 2

    manifest_path = args.manifest or find_manifest(args.map_path)
    manifest = None
    if manifest_path:
        try:
            with open(manifest_path, encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (OSError, ValueError) as error:
            print(f"cannot read manifest {manifest_path}: {error}", file=sys.stderr)
            return 2

    ctx = {
        "map": document,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "repo_root": args.repo_root or find_repo_root(args.map_path),
        "verbose": args.verbose,
    }

    print(f"{args.map_path} ({len(entries_of(document))} entries"
          + (f", manifest {os.path.basename(manifest_path)}" if manifest_path else ", no manifest") + ")")
    failed = skipped = passed = fatal = 0
    for name, check in selected:
        try:
            result = check(ctx)
        except Exception as error:  # a check that crashes has proved nothing
            result = skip(f"the check raised {type(error).__name__}: {error}")
        print(f"[{result.status}] {name}: {result.summary}")
        for line in result.details:
            print(line)
        if result.status == "fail":
            failed += 1
        elif result.status == "skip":
            skipped += 1
        else:
            passed += 1
        if result.fatal:
            fatal += 1

    print(f"\n{passed} ok, {failed} failed, {skipped} not verified")
    if fatal:
        return 1
    if not passed:
        # Nothing failed and nothing passed: every check declined to prove anything.
        print("nothing was actually checked; this is not a pass", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
