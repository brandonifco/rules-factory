#!/usr/bin/env python3
"""The map this engine is built from: the factory's map package, plus this engine's overlay.

Emitted by rules-factory tools/factory (the gate recipe, #3). Rewritten by every `factory
produce`; do not edit it here.

rules-factory decision 0015 publishes a map as a NuGet package, which the engine references and
never copies. What the engine owns is corpus-map.overlay.json,
`{ "<entry id>": { "status", "implementedIn", "tests" } }`: the build facts only the engine can
know. Every other byte of meaning is the package's. Beside them an item may hold its owner's
`rulings` and the `declines` that go with them (rules-factory decision 0027): answers the owner,
not the corpus, gives to part of an unresolved question. They are checked against the package map
by scripts/factory/rulings.py, the factory's own, and never merged: the map says only what the
corpus says.

merge(package, overlay), as 0015 defines it -- each rule is also a failure below:

  1. every overlay key names an entry in the package map;
  2. every overlay item sets `status`, and holds no key outside the three and `rulings` and
     `declines`, which break none of 0027's rules (the decision record each ruling names is looked
     for beside the overlay, in the engine root);
  3. for a named entry, the three fields come from the overlay alone: they are removed from the
     upstream entry, then the ones the overlay item carries are set. Every other field is
     upstream's, and `rulings` and `declines` are not carried into the merge;
  4. an entry the overlay does not name is upstream's verbatim, and so are the entry order and
     the top-level fields;
  5. if the engine commits a materialised corpus-map.json, it equals the merge as parsed JSON
     (`check --map`; an engine produced by the factory commits none, and its gate merges into a
     scratch file instead).

(Rule 6, the consumer-phase checks on the merge, is the package's own tools/check-map.py
--phase consumer, which scripts/validate.sh runs.)

And one rule 0015 did not state, because until rules-factory #239 nothing checked it: an item
whose `status` is `implemented` records, for every test, a **mutation that is not an unfilled
placeholder**. AGENTS.md's "a test whose named mutation was never observed to fail is a test
nobody has watched fail" rested on `isinstance(mutation, str) and mutation.strip()`, so the gate
passed with `"mutation": "PENDING"` -- evidence for a test nobody had run. The rule, in full, is
`placeholder_problem()` below: a named set of placeholder words, matched case-insensitively after
whitespace and surrounding punctuation are stripped, and a floor of MINIMUM_WORDS words and
MINIMUM_CHARACTERS characters.

This is a floor against the unfilled placeholder, **not a grader of mutation quality**. It cannot
tell whether the edit was made, whether the test went red, or whether the mutation was a good one;
nothing a string can be read for can. What it removes is the state of recording evidence that was
never filled in. The threshold is set far below any real mutation on purpose: refusing an honest
mutation blocks honest work and teaches people to pad, which is worse than a placeholder slipping
through. The shortest mutation in either engine the factory has built (faa-part-107,
tax-121-principal-residence) is 20 words and 159 characters, an order of magnitude above the
floor.

Where the overlay's fields land inside an entry is serialisation, not meaning: they are placed,
in the order status, implementedIn, tests, where upstream's `status` was.

  map-overlay.py merge --package-map P --overlay O --out corpus-map.json
  map-overlay.py check --package-map P --overlay O [--map corpus-map.json]

Standard library only, and scripts/factory/rulings.py.
"""
import argparse
import json
import pathlib
import string
import sys

# rulings, imported just below, leaves its bytecode behind: scripts/factory/__pycache__/, a path
# no ownership row covers, so the checkout that ran this goes dirty and tools/dispatch-agent.sh
# refuses to open a worktree for the next issue (#194). scripts/validate.sh and `factory verify`
# export PYTHONDONTWRITEBYTECODE for the same reason, but nothing exports it in the shell an agent
# runs this from. The loader reads this flag when the import happens, so it must come first --
# here the import is at module level, so today even `--help` writes the bytecode.
sys.dont_write_bytecode = True

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "factory"))
import rulings  # noqa: E402  (vendored by `factory produce`, rules-factory decision 0027)

OWNED = ("status", "implementedIn", "tests")

# The placeholder set (#239). Each of these is a word someone types to get past a check they mean
# to come back to, and every one of them has been seen in a `mutation` field or is one keystroke
# from one. `scratch` is here deliberately: the factory's own tools/validate-engine.py wrote
# `"mutation": "scratch"` in its scratch-engine overlays, which is exactly the habit this refuses,
# so the fixtures were given real sentences rather than the rule being weakened for them.
PLACEHOLDERS = frozenset((
    "pending", "tbd", "todo", "none", "n/a", "na", "scratch", "placeholder", "xxx",
    "unknown", "later", "fixme", "wip", "",
))

# The floor. A mutation is a sentence: it names what was changed and says what the test then did,
# and neither fits in two words. Set an order of magnitude below any real mutation -- the shortest
# in faa-part-107 or tax-121-principal-residence is 20 words and 159 characters -- because refusing
# an honest mutation is worse than letting a placeholder through: it blocks work and invites
# padding. Not a quality bar; see the module docstring.
MINIMUM_WORDS = 3
MINIMUM_CHARACTERS = 12

# The punctuation a placeholder is decorated with: "TODO.", "-- pending --", "?", "n/a!". Stripped
# from both ends before matching, which is also how the empty-after-punctuation case ("...", "-")
# becomes the empty string and matches.
EDGES = string.punctuation + string.whitespace


def normalise(mutation):
    """The mutation as it is matched: lowercased, with whitespace and surrounding punctuation gone."""
    return " ".join(mutation.split()).strip(EDGES).casefold()


def words(normalised):
    """The tokens that carry meaning: whitespace-separated, at least one letter or digit each."""
    return [w for w in normalised.split() if any(c.isalnum() for c in w)]


def placeholder_problem(mutation):
    """Why this mutation is not evidence, or None. The whole rule, in one place (#239)."""
    normalised = normalise(mutation)
    tokens = words(normalised)
    if normalised in PLACEHOLDERS or (tokens and all(t.strip(EDGES) in PLACEHOLDERS for t in tokens)):
        return f"{mutation.strip()!r} is a placeholder, not a mutation"
    if len(tokens) < MINIMUM_WORDS or len(normalised) < MINIMUM_CHARACTERS:
        return (f"{mutation.strip()!r} is too short to be a mutation: at least {MINIMUM_WORDS} words "
                f"and {MINIMUM_CHARACTERS} characters are asked for, and this is "
                f"{len(tokens)} and {len(normalised)}")
    return None


def mutation_problems(entry_id, item):
    """Rule #239, for one overlay item: an `implemented` entry records a real mutation per test."""
    if not isinstance(item, dict) or item.get("status") != "implemented":
        return []
    tests = item.get("tests")
    if not isinstance(tests, list):
        return []
    problems = []
    for position, test in enumerate(tests, start=1):
        if not isinstance(test, dict):
            continue
        named = test.get("test") if isinstance(test.get("test"), str) else f"the test at position {position}"
        mutation = test.get("mutation")
        if not isinstance(mutation, str):
            why = "records no mutation" if mutation is None else f"records a {type(mutation).__name__}, not a mutation"
        else:
            why = placeholder_problem(mutation)
            if why is None:
                continue
            why = f"records {why}"
        problems.append(
            f"overlay item {entry_id!r} is implemented, and {named!r} {why}. A mutation is the edit "
            "you made to this engine that turned that test red, written down: what you changed, "
            "where, and what the test then did. Make the edit, watch the test fail, undo it, record "
            "it here, and re-produce with `tools/re-produce.sh`. This is a floor against an unfilled "
            "placeholder, not a judgement of the mutation.")
    return problems


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def serialise(document):
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def merge(package, overlay, root=None):
    """merge(package, overlay), every way the overlay breaks rules 1 and 2, and every placeholder
    mutation an implemented entry records (#239). `root` is the engine directory the owner's
    decision records are looked for in."""
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
            if key not in OWNED and key not in rulings.KEYS:
                problems.append(f"overlay item {entry_id!r} sets {key!r}; an engine owns only "
                                f"{', '.join(OWNED)} (and its owner's {' and '.join(rulings.KEYS)}), "
                                f"and every other field is the package's")
        problems += mutation_problems(entry_id, item)
    problems += [f"owner's rulings (rules-factory decision 0027): {p}"
                 for p in rulings.problems(package, overlay, root)]
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
    merged, problems = merge(package, overlay, root=str(pathlib.Path(args.overlay).resolve().parent))

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
    for line in rulings.describe(overlay):
        print(f"     {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
