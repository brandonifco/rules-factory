#!/usr/bin/env python3
"""Hold the three subsystems to the one direction of dependency they are allowed (0032).

This repository does three jobs, and for most of its life they were one pile: a mapper that
turns a corpus into a map, validation that certifies a map, and a factory that turns a
certified map into an engine. 0032 makes them siblings over one shared contract, so that the
factory knows nothing about how a map was made and the mapper nothing about what is built from
it. That is an architecture only while something enforces it -- an `import` is one line, and
the reason to keep the boundary is invisible at the moment someone crosses it.

So the direction is declared in SUBSYSTEMS below and checked here:

  * every declared subsystem exists, and the file SUBSYSTEMS names for it opens with a
    docstring saying what it owns -- a directory with no statement of its job is not a
    subsystem;
  * no subsystem imports one it is not permitted to, at the top of a module or inside a
    function, because a deferred import is a dependency too;
  * the contract imports no subsystem at all: it is the root, and a contract that reached back
    into a consumer would make the graph a cycle and the extraction of any part impossible;
  * no relative import climbs out of its own package.

What it cannot see, stated here rather than in a commit message:

  * **Coupling that is not an import.** `tools/factory/` reads map field names directly --
    `entry["id"]`, `entry.get("kind")`, `entry.get("dependsOn")` -- rather than through
    `mapcontract`. That is a real dependency on the contract's vocabulary that no import
    expresses, and this checker reports it as nothing. Moving those reads behind the contract
    is its own change.
  * **The bytes an engine receives.** `tools/factory/recipe/` is excluded. Those files are not
    this repository's code but the files a produced engine carries, and they import their
    vendored copies by bare name (`import generate`) inside the engine, where the rule that
    governs them is ownership (0018) and the checker is
    `tools/tests/test_factory_rails.py`. Judging them here would compare them against the
    wrong tree.
  * **Whether the boundary is the right one.** It checks the declaration, not the design.

Usage: check-boundaries.py [--root PATH]
Exit 0 when every subsystem holds the direction; 1 when one does not, or when the check
examined no subsystem or no file; 2 on a usage error.
"""
import argparse
import ast
import os
import sys

# Each subsystem, and the subsystems it may import. The order is the dependency order: a
# subsystem may only name one above it, and the first names nothing.
#
# `mapcontract` is first and depends on nothing, which is what makes it a contract rather than
# a utility library shared by whoever reached for it. `mapper`, `checkmap` and `factory` are
# siblings: producer, verifier and consumer of the same map, and none of the three may know
# another. Producer and verifier stay apart for the reason production code is not its own only
# test oracle; the factory stays out of both so that it consumes a certified map and asks
# nothing about how it was made. A map could be written by hand and still be validated and
# built, which is the test of whether the boundary is real.
# The middle element is the file that states what the subsystem owns. It is `__init__.py` for
# an importable package, and `__main__.py` for `tools/factory/`, which is a directory run as a
# script (`python3 tools/factory`) whose modules import each other by bare name -- so it has no
# `__init__.py` to state anything in, and the statement lives where the command starts.
SUBSYSTEMS = (
    ("mapcontract", "__init__.py", ()),
    ("mapper", "__init__.py", ("mapcontract",)),
    ("checkmap", "__init__.py", ("mapcontract",)),
    ("factory", "__main__.py", ("mapcontract",)),
)

# Excluded, and why, per the docstring: these are the bytes a produced engine receives.
EXCLUDED = ("factory/recipe",)


def _subsystem_names():
    return tuple(name for name, _, _ in SUBSYSTEMS)


def _sources(tools, name):
    """Every .py file in a subsystem, as (path relative to tools/, absolute path)."""
    found = []
    root = os.path.join(tools, name)
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = sorted(d for d in subdirs if d != "__pycache__")
        relative_dir = os.path.relpath(directory, tools).replace(os.sep, "/")
        if any(relative_dir == e or relative_dir.startswith(e + "/") for e in EXCLUDED):
            subdirs[:] = []
            continue
        for filename in sorted(files):
            if filename.endswith(".py"):
                path = os.path.join(directory, filename)
                found.append((os.path.relpath(path, tools).replace(os.sep, "/"), path))
    return found


def _imports(tree):
    """Every import anywhere in the module, as (lineno, root package, written form, level)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0], f"import {alias.name}", 0
        elif isinstance(node, ast.ImportFrom):
            written = "." * node.level + (node.module or "")
            root = (node.module or "").split(".")[0] if not node.level else None
            yield node.lineno, root, f"from {written} import ...", node.level


def check(tools):
    """One line per finding, and the two counts that say the check did something."""
    problems, files = [], 0
    names = _subsystem_names()
    for name, states_it, allowed in SUBSYSTEMS:
        directory = os.path.join(tools, name)
        if not os.path.isdir(directory):
            problems.append(f"  X  tools/{name}/ is declared a subsystem and does not exist")
            continue
        statement = os.path.join(directory, states_it)
        try:
            with open(statement, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=statement)
        except (OSError, SyntaxError) as error:
            problems.append(f"  X  tools/{name}/{states_it} cannot be read: {error}")
            tree = None
        if tree is not None and not ast.get_docstring(tree):
            problems.append(f"  X  tools/{name}/{states_it} has no docstring; a subsystem with no "
                            f"statement of what it owns is not one")
        for relative, path in _sources(tools, name):
            files += 1
            try:
                with open(path, encoding="utf-8") as handle:
                    module = ast.parse(handle.read(), filename=path)
            except (OSError, SyntaxError) as error:
                problems.append(f"  X  tools/{relative} cannot be read: {error}")
                continue
            depth = relative.count("/")  # how far a relative import may climb and stay inside
            for lineno, root, written, level in _imports(module):
                if level > depth:
                    problems.append(f"  X  tools/{relative}:{lineno}: `{written}` climbs out of "
                                    f"tools/{name}/; a subsystem is imported by name, not by "
                                    f"reaching above it")
                elif root in names and root != name and root not in allowed:
                    why = (f"tools/{name}/ is the contract and imports no subsystem" if not allowed
                           else f"tools/{name}/ may import {', '.join(allowed)}, and {root} is a "
                                f"subsystem beside it: the two meet at the contract or not at all")
                    problems.append(f"  X  tools/{relative}:{lineno}: `{written}` -- {why}")
    return problems, files


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the subsystem dependency direction (0032).")
    parser.add_argument("--root", help="the repository root (default: the one this file is in)")
    args = parser.parse_args(argv)

    here = os.path.dirname(os.path.abspath(__file__))
    tools = os.path.join(args.root, "tools") if args.root else here
    if not os.path.isdir(tools):
        print(f"no tools directory at {tools}", file=sys.stderr)
        return 2

    problems, files = check(tools)
    if not SUBSYSTEMS or not files:
        print("no subsystem source was examined -- this check proved nothing", file=sys.stderr)
        return 1
    for line in problems:
        print(line)
    declared = ", ".join(f"{name} -> " + (" ".join(allowed) if allowed else "nothing")
                         for name, _, allowed in SUBSYSTEMS)
    if problems:
        print(f"\n{len(problems)} boundary violation(s) over {files} file(s) in "
              f"{len(SUBSYSTEMS)} subsystem(s)")
        return 1
    print(f"{files} file(s) in {len(SUBSYSTEMS)} subsystem(s) hold the direction: {declared}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
