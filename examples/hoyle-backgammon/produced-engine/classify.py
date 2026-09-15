#!/usr/bin/env python3
"""Classify every difference between a from-scratch produce and a committed engine (#3).

  classify.py --factory <factory checkout> --engine <engine clone> --name <Name>
              --bare <produce into an empty dir> --seeded <produce into a dir holding only the overlay>

Ownership is read from the factory checkout's own tools/factory/ownership.py (decision 0018), the
table the engine was produced under, never restated here. Two produces are compared with the
engine, because the generated files are a function of merge(package map, engine overlay):

  * **seeded** -- an empty directory holding only the engine's corpus-map.overlay.json, the one
    engine-owned file generation reads (generate.py). Against the engine, every generated file
    must be byte-identical, every managed file identical, and provenance.json may differ only in
    `buildInputs` and `engineOwned`, each differing item explained below. Every other difference
    must be an engine-owned row of the table, or a file that matches no row (the engine's own
    code, tests, docs, extra projects and lock files).
  * **bare** -- a truly empty directory. Its generated files may differ from the engine's only
    where the seeded produce agrees with the engine: that is, only because of the overlay.

A generated or managed file that differs, is missing on one side, or a provenance field that
differs for any other reason, is a FINDING. Exit 0 when there are none; 1 when there are; 2 on a
usage error. Standard library only.
"""
import argparse
import collections
import hashlib
import importlib.util
import json
import os
import sys

ALLOWED_PROVENANCE_FIELDS = ("buildInputs", "engineOwned")


def load_ownership(factory):
    path = os.path.join(factory, "tools", "factory", "ownership.py")
    spec = importlib.util.spec_from_file_location("ownership", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tree(root):
    """Every file under `root` as a POSIX relative path, .git excluded."""
    found = set()
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d != ".git"]
        for name in files:
            found.add(os.path.relpath(os.path.join(directory, name), root).replace(os.sep, "/"))
    return found


def read(root, relative):
    with open(os.path.join(root, *relative.split("/")), "rb") as handle:
        return handle.read()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cls_of(ownership, relative, name):
    row = ownership.classify(relative, name)
    return row.cls if row else "unlisted"


def explain_provenance(ownership, name, engine, seeded, findings):
    produced = json.loads(read(seeded, ownership.PROVENANCE))
    committed = json.loads(read(engine, ownership.PROVENANCE))
    lines = []
    for field in sorted(set(produced) | set(committed)):
        if produced.get(field) == committed.get(field):
            lines.append(f"  field {field}: identical")
            continue
        if field not in ALLOWED_PROVENANCE_FIELDS:
            findings.append(f"provenance.json field {field} differs, and only {ALLOWED_PROVENANCE_FIELDS} may")
            lines.append(f"  field {field}: DIFFERS (finding)")
            continue
        lines.append(f"  field {field}: differs, explained item by item:")
        mine = {item["path"]: item for item in produced.get(field) or []}
        theirs = {item["path"]: item for item in committed.get(field) or []}
        engine_files = tree(engine)
        for path in sorted(set(mine) | set(theirs)):
            a, b = mine.get(path), theirs.get(path)
            if a == b:
                continue
            owner = cls_of(ownership, path, name)
            if owner not in (ownership.ENGINE_OWNED, "unlisted"):
                findings.append(f"provenance.json {field} item {path} differs, and it is {owner}")
                lines.append(f"    {path}: DIFFERS and is {owner} (finding)")
            elif a is None and path not in engine_files:
                findings.append(f"provenance.json {field} lists {path}, which the engine does not have")
                lines.append(f"    {path}: recorded but absent from the engine (finding)")
            elif a is not None and b is None:
                findings.append(f"provenance.json {field} item {path} is in the produce and not the engine")
                lines.append(f"    {path}: only in the produce (finding)")
            elif field == "buildInputs" and b["sha256"] != sha(read(engine, path)):
                findings.append(f"provenance.json buildInputs {path} does not hash to the engine's bytes")
                lines.append(f"    {path}: recorded hash is not the engine's bytes (finding)")
            elif field == "engineOwned" and a is not None and a.get("adopted") != b.get("adopted"):
                findings.append(f"provenance.json engineOwned {path} differs in `adopted`")
                lines.append(f"    {path}: `adopted` differs (finding)")
            elif a is None and field == "engineOwned":
                lines.append(f"    {path}: engine-owned lock file, written by verify's restore; "
                             f"the evidence produce ran --no-verify, so it has none")
            elif a is None:
                lines.append(f"    {path}: {owner}, added by the engine (sha256 {b['sha256'][:12]} = its bytes)")
            else:
                lines.append(f"    {path}: {owner}, the engine changed it from what produce writes first "
                             f"({a['sha256'][:12]} -> {b['sha256'][:12]} = its bytes)")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for flag in ("--factory", "--engine", "--name", "--bare", "--seeded"):
        parser.add_argument(flag, required=True)
    args = parser.parse_args()
    for directory in (args.factory, args.engine, args.bare, args.seeded):
        if not os.path.isdir(directory):
            parser.error(f"{directory} is not a directory")
    ownership = load_ownership(args.factory)
    name = args.name
    findings = []
    engine, seeded, bare = tree(args.engine), tree(args.seeded), tree(args.bare)
    if not seeded or not engine:
        print("an empty tree was compared -- this proved nothing", file=sys.stderr)
        return 1

    counts = collections.Counter()
    details = collections.defaultdict(list)
    for path in sorted(engine | seeded):
        owner = cls_of(ownership, path, name)
        if path in engine and path in seeded:
            same = read(args.engine, path) == read(args.seeded, path)
            state = "identical" if same else "differs"
        else:
            state = "only-engine" if path in engine else "only-produced"
        key = f"{owner} {state}"
        counts[key] += 1
        details[key].append(path)
        if owner in (ownership.GENERATED, ownership.MANAGED) and state != "identical":
            if path != ownership.PROVENANCE or state != "differs":
                findings.append(f"{owner} file {path}: {state}")
        if owner in (ownership.ENGINE_OWNED, "unlisted") and state == "only-produced":
            findings.append(f"{owner} file {path} was produced and the engine does not have it")

    print(f"seeded produce vs engine: {len(engine | seeded)} path(s)")
    for key in sorted(counts):
        print(f"  {counts[key]:4d}  {key}")
        if (not key.endswith("identical") or key.startswith("engine-owned")) and key != "unlisted only-engine":
            for path in details[key]:
                print(f"          {path}")
    print("  unlisted only-engine, by top directory:")
    tops = collections.Counter(p.split("/")[0] if p.count("/") == 0 else "/".join(p.split("/")[:2])
                               for p in details["unlisted only-engine"])
    for top in sorted(tops):
        print(f"        {tops[top]:4d}  {top}")

    print("provenance.json (generated), seeded produce vs engine:")
    for line in explain_provenance(ownership, name, args.engine, args.seeded, findings):
        print(line)

    print("bare produce vs engine: generated files that differ, and whether the overlay alone explains them")
    explained = 0
    for path in sorted(bare | engine):
        if cls_of(ownership, path, name) != ownership.GENERATED or path == ownership.PROVENANCE:
            continue
        in_bare, in_engine = path in bare, path in engine
        if in_bare and in_engine and read(args.bare, path) == read(args.engine, path):
            continue
        state = "differs" if in_bare and in_engine else ("only-bare" if in_bare else "only-engine")
        if path in seeded and path in engine and read(args.seeded, path) == read(args.engine, path):
            explained += 1
            print(f"  {state:11s} {path}: identical once seeded with the overlay")
        elif not in_engine and path not in seeded:
            explained += 1
            print(f"  {state:11s} {path}: absent once seeded with the overlay: not a backlog item")
        else:
            findings.append(f"bare produce generated file {path} {state}, not explained by the overlay")
            print(f"  {state:11s} {path}: NOT explained by the overlay (finding)")
    print(f"  {explained} generated file(s) differ in the bare produce, all explained by the overlay"
          if not any(f.startswith("bare") for f in findings) else "  some are not explained")

    if findings:
        print(f"\nFINDINGS ({len(findings)}):")
        for finding in findings:
            print(f"  X  {finding}")
        return 1
    print("\nno generated or managed difference: every difference is engine-owned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
