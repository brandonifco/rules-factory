#!/usr/bin/env python3
"""The map this engine is built from: the factory's map package, plus this engine's overlay.

Emitted by rules-factory tools/factory (the gate recipe, #3). Rewritten by every `factory
produce`; do not edit it here.

rules-factory decision 0015 publishes a map as a NuGet package, which the engine references and
never copies. What the engine owns is corpus-map.overlay.json,
`{ "<entry id>": { "status", "implementedIn", "tests" } }`: the build facts only the engine can
know. Every other byte of meaning is the package's.

merge(package, overlay), as 0015 defines it -- each rule is also a failure below:

  1. every overlay key names an entry in the package map;
  2. every overlay item sets `status`, and holds no key outside the three;
  3. for a named entry, the three fields come from the overlay alone: they are removed from the
     upstream entry, then the ones the overlay item carries are set. Every other field is
     upstream's;
  4. an entry the overlay does not name is upstream's verbatim, and so are the entry order and
     the top-level fields;
  5. if the engine commits a materialised corpus-map.json, it equals the merge as parsed JSON
     (`check --map`; an engine produced by the factory commits none, and its gate merges into a
     scratch file instead).

(Rule 6, the consumer-phase checks on the merge, is the package's own tools/check-map.py
--phase consumer, which scripts/validate.sh runs.)

Where the overlay's fields land inside an entry is serialisation, not meaning: they are placed,
in the order status, implementedIn, tests, where upstream's `status` was.

  map-overlay.py merge --package-map P --overlay O --out corpus-map.json
  map-overlay.py check --package-map P --overlay O [--map corpus-map.json]

Standard library only.
"""
import argparse
import json
import pathlib
import sys

OWNED = ("status", "implementedIn", "tests")


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def serialise(document):
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def merge(package, overlay):
    """merge(package, overlay), and every way the overlay breaks rules 1 and 2."""
    problems = []
    if not isinstance(overlay, dict):
        return None, ["the overlay is not an object of entry id -> owned fields"]
    ids = [e.get("id") for e in package.get("entries", []) if isinstance(e, dict)]
    for entry_id, item in overlay.items():
        if entry_id not in ids:
            problems.append(f"overlay names {entry_id!r}, which the package map has no entry for "
                            "(renamed or removed upstream?)")
        if not isinstance(item, dict):
            problems.append(f"overlay item {entry_id!r} is not an object")
            continue
        if "status" not in item:
            problems.append(f"overlay item {entry_id!r} does not set status")
        for key in item:
            if key not in OWNED:
                problems.append(f"overlay item {entry_id!r} sets {key!r}; an engine owns only "
                                f"{', '.join(OWNED)}, and every other field is the package's")
    if problems:
        return None, problems

    merged_entries = []
    for entry in package.get("entries", []):
        item = overlay.get(entry.get("id"))
        if item is None:
            merged_entries.append(entry)
            continue
        out, placed = {}, False
        for key, value in entry.items():
            if key in OWNED:
                if key == "status" and not placed:
                    out.update({k: item[k] for k in OWNED if k in item})
                    placed = True
                continue
            out[key] = value
        if not placed:
            out.update({k: item[k] for k in OWNED if k in item})
        merged_entries.append(out)
    return {key: (merged_entries if key == "entries" else value) for key, value in package.items()}, []


def canonical(document):
    return json.dumps(document, sort_keys=True, ensure_ascii=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description="merge(package map, corpus-map.overlay.json) under 0015")
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("merge", help="write the merge; exit 1 when the overlay breaks a rule")
    m.add_argument("--package-map", required=True)
    m.add_argument("--overlay", required=True)
    m.add_argument("--out", required=True)
    c = sub.add_parser("check", help="check the overlay, and a committed materialised map if given")
    c.add_argument("--package-map", required=True)
    c.add_argument("--overlay", required=True)
    c.add_argument("--map")
    args = parser.parse_args(argv)

    try:
        package = load(args.package_map)
        overlay = load(args.overlay)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    merged, problems = merge(package, overlay)

    if merged is not None and args.command == "check" and args.map:
        committed = load(args.map)
        if canonical(committed) != canonical(merged):
            differing = [e.get("id") for e, n in zip(committed.get("entries", []), merged["entries"])
                         if canonical(e) != canonical(n)]
            problems.append(f"{args.map} is not merge(package, overlay); differing entries: "
                            f"{', '.join(map(str, differing)) or 'none (top-level fields or entry count)'}. "
                            "Edit the overlay, not the map, and regenerate it with `map-overlay.py merge`.")

    for p in problems:
        print(f"error: {p}", file=sys.stderr)
    if problems:
        return 1
    if args.command == "merge":
        pathlib.Path(args.out).write_text(serialise(merged), encoding="utf-8")
    print(f"     merge(package, {pathlib.Path(args.overlay).name}): {len(overlay)} of "
          f"{len(package.get('entries', []))} entries overlaid on {', '.join(OWNED)} only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
