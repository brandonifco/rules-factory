#!/usr/bin/env python3
"""Collapse every recorded ambiguity in every committed map, and count what the validator sees.

0014 measured the mechanical checks against 15 injected comprehension errors and caught 1.
This measures the one error 0034 is about: a **premature collapse**, a mapper choosing a reading
the corpus does not settle and recording it as `clarity: clear`. One collapse per recorded
ambiguity, applied to a copy in a temporary directory -- a committed map's bytes are never
written, because a map change invalidates its review (0017).

The collapse is minimal and is what a mapper who chose silently would actually produce:

    entry["clarity"] = "clear"          # the corpus determines exactly one answer
    del entry["ambiguity"]              # so there is no question, no fate and no reason

Nothing else is touched. The map that results is the map the mapper would have written had they
never noticed the second reading, which is the point: every check still has its inputs, and a
check that fires fires on the collapse rather than on collateral damage.

Usage: collapse.py [--repo-root DIR] [--json PATH]
Exit 0 when the measurement ran, 1 when it found no map to collapse.
"""
import argparse
import glob
import io
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr

# Imports another of this repository's files by path, and the loader writes that file's
# bytecode beside it. No caller's environment is relied on to stop it (#384): module level
# and above the import, because the loader reads the flag when the import happens.
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


# The checks 0034 added. What fires without them is what the validator caught before,
# and the difference between the two numbers is what this measurement is of.
EPISTEMIC = {"superposition", "unresolved-reason", "bound-term-open"}


def load_checker(repo_root):
    """The built checker, imported as the factory imports it (0016)."""
    import importlib.util
    path = os.path.join(repo_root, "tools", "check-map.py")
    spec = importlib.util.spec_from_file_location("check_map_under_measurement", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(checker, map_path, repo_root):
    """Every check's verdict on one map, as {check: status}."""
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        checker.main([map_path, "--repo-root", repo_root])
    return dict((name, status) for status, name in
                re.findall(r"^\[(ok|fail|skip)\] (\S+):", out.getvalue(), re.M))


def mirror(examples, into):
    """Every example directory, as directories of symbolic links to the committed files.

    Links rather than copies, because a corpus text is megabytes and this reads them all; and the
    whole tree rather than one map's directory, because `postures` resolves a manifest's
    `committedPath` beside the manifest and one slice's manifest names another slice's text. The
    map under measurement is then overwritten with a real file, so no committed byte is ever
    written through a link.
    """
    for directory, _, names in os.walk(examples):
        staged = os.path.join(into, os.path.relpath(directory, examples))
        os.makedirs(staged, exist_ok=True)
        for name in names:
            link = os.path.join(staged, name)
            if not os.path.lexists(link):
                os.symlink(os.path.join(directory, name), link)


def measure(repo_root):
    checker = load_checker(repo_root)
    examples = os.path.join(repo_root, "examples")
    maps = sorted(glob.glob(os.path.join(examples, "*", "corpus-map*.json")))
    report = {"maps": [], "collapses": 0, "caught": 0, "only_epistemic": 0}
    workspace = tempfile.mkdtemp(prefix="collapse-trial-")
    try:
        mirror(examples, workspace)
        for committed in maps:
            staged = os.path.join(workspace, os.path.relpath(committed, examples))
            os.remove(staged)  # the link to the committed map; a real file replaces it
            original = json.load(open(committed, encoding="utf-8"))
            clean = run(checker, staged, repo_root)
            row = {"map": os.path.relpath(committed, repo_root),
                   "clean": sorted(c for c, s in clean.items() if s == "fail"),
                   "ambiguities": 0, "caught": 0, "missed": [], "by_check": {},
                   "fired": {}, "only_epistemic": 0}
            for position, entry in enumerate(original.get("entries") or []):
                if not isinstance(entry, dict) or entry.get("clarity") != "ambiguous":
                    continue
                row["ambiguities"] += 1
                collapsed = json.loads(json.dumps(original))
                collapsed["entries"][position]["clarity"] = "clear"
                collapsed["entries"][position].pop("ambiguity", None)
                with open(staged, "w", encoding="utf-8") as handle:
                    json.dump(collapsed, handle)
                after = run(checker, staged, repo_root)
                fired = sorted(check for check, status in after.items()
                               if status == "fail" and clean.get(check) != "fail")
                if fired:
                    row["caught"] += 1
                    row["fired"][entry.get("id")] = fired
                    for check in fired:
                        row["by_check"][check] = row["by_check"].get(check, 0) + 1
                    if not set(fired) - EPISTEMIC:
                        row["only_epistemic"] += 1
                else:
                    row["missed"].append(entry.get("id"))
            os.remove(staged)
            os.symlink(committed, staged)
            report["maps"].append(row)
            report["collapses"] += row["ambiguities"]
            report["caught"] += row["caught"]
            report["only_epistemic"] += row["only_epistemic"]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=ROOT)
    parser.add_argument("--json", help="write the whole report here")
    args = parser.parse_args(argv)

    report = measure(os.path.abspath(args.repo_root))
    if not report["collapses"]:
        print("no recorded ambiguity to collapse -- this measured nothing", file=sys.stderr)
        return 1
    print(f"{'map':45} {'collapses':>9} {'caught':>7} {'missed':>7}")
    for row in report["maps"]:
        print(f"{row['map']:45} {row['ambiguities']:>9} {row['caught']:>7} "
              f"{row['ambiguities'] - row['caught']:>7}")
    missed = report["collapses"] - report["caught"]
    print(f"\n{report['caught']} of {report['collapses']} collapses caught; "
          f"{missed} missed ({missed / report['collapses']:.0%})")
    fired = {}
    for row in report["maps"]:
        for check, count in row["by_check"].items():
            fired[check] = fired.get(check, 0) + count
    for check, count in sorted(fired.items(), key=lambda pair: -pair[1]):
        print(f"  {check}: fired on {count}")
    before = report["caught"] - report["only_epistemic"]
    print(f"without the checks 0034 added: {before} of {report['collapses']} caught, "
          f"{report['collapses'] - before} missed "
          f"({(report['collapses'] - before) / report['collapses']:.0%})")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, sort_keys=True)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
