#!/usr/bin/env python3
"""No workflow floats the Python it runs on or the packages it installs (#173).

Actions are pinned by commit and the runner by release, and the rest floated: `setup-python`
asked for `3.12`, which is whichever patch the runner cache holds that day, and `pip install
pytest` took whichever pytest PyPI served. Either can change what `validate.sh` concludes with no
commit in this repository.

For every `.github/workflows/*.yml` this fails when:

  * a `python-version:` is not an exact `X.Y.Z`;
  * a line runs `pip install` without `--require-hashes` and a `-r` requirements file;
  * no workflow was examined, or none set up Python -- the check proved nothing.

It reads lines, not YAML (the standard library has no YAML parser), so a value spread over
several lines is not seen; the workflows here write each on one line.

Usage: check-workflow-pins.py [--workflows DIR]
Exit 0 when every workflow pins both; 1 otherwise. Standard library only.
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PYTHON_VERSION = re.compile(r"^\s*python-version:\s*(.*?)\s*(?:#.*)?$")
EXACT = re.compile(r"""^(['"]?)\d+\.\d+\.\d+\1$""")
PIP_INSTALL = re.compile(r"\bpip3?\s+install\b")


def check(paths):
    """Problems as lines, and how many python-version lines were examined."""
    problems, pythons = [], 0
    for path in paths:
        name = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                match = PYTHON_VERSION.match(line)
                if match:
                    pythons += 1
                    if not EXACT.match(match.group(1)):
                        problems.append(f"{name}:{number}: python-version {match.group(1)} is not an exact X.Y.Z")
                if PIP_INSTALL.search(line) and not ("--require-hashes" in line and re.search(r"\s-r\s", line)):
                    problems.append(f"{name}:{number}: pip install without --require-hashes -r <file>")
    return problems, pythons


def main(argv=None):
    parser = argparse.ArgumentParser(prog="check-workflow-pins.py", description=__doc__.split("\n")[0])
    parser.add_argument("--workflows", default=os.path.join(ROOT, ".github", "workflows"))
    args = parser.parse_args(argv)
    paths = sorted(glob.glob(os.path.join(args.workflows, "*.yml")) + glob.glob(os.path.join(args.workflows, "*.yaml")))
    if not paths:
        print(f"check-workflow-pins: no workflows in {args.workflows} -- this check proved nothing", file=sys.stderr)
        return 1
    problems, pythons = check(paths)
    for line in problems:
        print(f"  X  {line}")
    if problems:
        return 1
    if pythons == 0:
        print("check-workflow-pins: no workflow sets up Python -- this check proved nothing", file=sys.stderr)
        return 1
    print(f"{len(paths)} workflow(s), {pythons} python-version pin(s), every one exact; every pip install hash-locked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
