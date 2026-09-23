#!/usr/bin/env python3
"""The map this engine is built from: the factory's map package, plus this engine's overlay.

Emitted by rules-factory tools/factory (the gate recipe, #3). Rewritten by every `factory
produce`; do not edit it here.

rules-factory decision 0015 publishes a map as a NuGet package, which the engine references and
never copies. What the engine owns is its overlay: one file per entry, `overlay/<entry id>.json`,
each holding `{ "status", "implementedIn", "tests" }` for that entry -- the build facts only the
engine can know. One entry, one file, so two entry branches never write the same one (#247); the
files are read **in the package map's order**, never in the directory's, so the merge is the same
bytes whatever a filesystem lists first. Every other byte of meaning is the package's. Beside them
an item may hold its owner's
`rulings` and the `declines` that go with them (rules-factory decision 0027): answers the owner,
not the corpus, gives to part of an unresolved question. They are checked against the package map
by scripts/factory/rulings.py, the factory's own, and never merged: the map says only what the
corpus says.

merge(package, overlay), as 0015 defines it -- each rule is also a failure below:

  1. every overlay file names an entry in the package map (its name is the entry id);
  2. every overlay file sets `status`, and holds no key outside the three and `rulings` and
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

And one rule 0015 did not state, because until rules-factory #239 nothing checked it: an entry
**of the merge** whose `status` is `implemented` records, for every test, a **mutation that is not
an unfilled placeholder**. AGENTS.md's "a test whose named mutation was never observed to fail is
a test nobody has watched fail" rested on `isinstance(mutation, str) and mutation.strip()`, so the
gate passed with `"mutation": "PENDING"` -- evidence for a test nobody had run.

Read on the merge, not on the overlay. The overlay is where an engine normally records its tests,
but `tests` is a field of the merged entry, and a package map may carry one: checking overlay
items would leave an implemented entry whose evidence came from upstream unexamined, which is the
same shape of hole as the one this rule closes. What the engine ships is the merge, so the merge
is what is read.

The rule, in full, is `placeholder_problem()` below. Three refusals, in order, all applied to the
mutation after `normalise()` -- NFKD, combining marks and format characters (Unicode Mn, Me, Cf)
removed, whitespace collapsed, punctuation, symbols and spaces stripped from both ends by Unicode
category, and casefolded, so `TODO`, `ＴＯＤＯ`, `"TODO"`, `TO<zero-width space>DO` and `TÓDO` are
one word:

  * a **placeholder**: the whole mutation is one of the set, or every distinct word in it is;
  * **one word repeated**: two or more words, all the same word;
  * **too short**: fewer than MINIMUM_WORDS words, counted with repeats, or fewer than
    MINIMUM_CHARACTERS characters.

Words are counted with repeats, and distinctness is only ever the placeholder rule's business.
They were one check and should not have been: ``Increment `increment`; fails.`` is honest evidence
about a variable named `increment`, and a floor counting distinct words refused it.

"One word repeated" is what refuses `TODO TODO TODO` when the copies are spelled in a script the
placeholder set does not contain -- a Cyrillic `О` for a Latin `O`, say. **Confusable (homoglyph)
mapping is deliberately not done**: it needs a versioned table of confusables kept current against
Unicode, which belongs to the whole factory and not to one check, and a homoglyph here is
deliberate evasion, which this floor does not claim to stop in any case. So the claim is exactly
this and no more: *repeating one spelling is refused whatever script the spelling is in; mixing
spellings to evade -- `TODO TОDO TODО`, three different ones -- is not something this floor
stops.*

Read after the merge is built, which means **after** rules 1 and 2 and 0027's rulings have held.
An overlay that breaks one of those is refused there and its mutations are never looked at, so a
refusal that names no mutation is not a report that the mutations are fine -- it is a merge that
could not be read yet. Fix what is named, run it again.

This refuses **unfilled placeholders**, and nothing more. It cannot tell whether the edit was
made, whether the test went red, whether the mutation was a good one, or whether the sentence was
copied from another entry; `not yet recorded` passes it. Nothing a string can be read for can do
otherwise. The threshold is set far below any real mutation on purpose: refusing an honest
mutation blocks honest work and teaches people to pad, which is worse than a placeholder slipping
through. The shortest mutation in either engine the factory has built (faa-part-107,
tax-121-principal-residence) is 20 words and 159 characters, an order of magnitude above the
floor.

Where the overlay's fields land inside an entry is serialisation, not meaning: they are placed,
in the order status, implementedIn, tests, where upstream's `status` was.

  map-overlay.py merge --package-map P --overlay overlay --out corpus-map.json
  map-overlay.py check --package-map P --overlay overlay [--map corpus-map.json]

`--overlay` is the engine's overlay **directory**.

Standard library only, and scripts/factory/{overlay,rulings}.py.
"""
import argparse
import json
import pathlib
import sys
import unicodedata

# rulings, imported just below, leaves its bytecode behind: scripts/factory/__pycache__/, a path
# no ownership row covers, so the checkout that ran this goes dirty and tools/dispatch-agent.sh
# refuses to open a worktree for the next issue (#194). scripts/validate.sh and `factory verify`
# export PYTHONDONTWRITEBYTECODE for the same reason, but nothing exports it in the shell an agent
# runs this from. The loader reads this flag when the import happens, so it must come first --
# here the import is at module level, so today even `--help` writes the bytecode.
sys.dont_write_bytecode = True

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "factory"))
import compose  # noqa: E402  (vendored by `factory produce`, rules-factory decision 0067)
import overlay as overlay_step  # noqa: E402  (vendored by `factory produce`; the layout, #247)
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
# and neither fits in two words. Counted with repeats -- a word may legitimately appear twice, as in
# ``Increment `increment`; fails.`` Set an order of magnitude below any real mutation -- the shortest in faa-part-107 or tax-121-principal-residence
# is 20 words and 159 characters -- because refusing an honest mutation is worse than letting a
# placeholder through: it blocks work and invites padding. Not a quality bar; see the docstring.
MINIMUM_WORDS = 3
MINIMUM_CHARACTERS = 12

# Combining marks and format characters. Removed outright, not stripped from the ends: a zero-width
# space inside `TO<zwsp>DO` hides the word, and seven of them pad `1 2 3` past a character floor.
INVISIBLE = ("Mn", "Me", "Cf")

# What a placeholder is decorated with -- "TODO.", "-- pending --", "?", "n/a!", curly quotes --
# taken by Unicode category rather than an ASCII set, so it is not only ASCII punctuation. This is
# also how the empty-after-punctuation case ("...", "-", "()") becomes the empty string.
EDGE_CATEGORIES = ("P", "S", "Z")


def an_edge(character):
    return unicodedata.category(character)[0] in EDGE_CATEGORIES or character.isspace()


def strip_edges(text):
    """`text` without leading and trailing punctuation, symbols and whitespace."""
    start, end = 0, len(text)
    while start < end and an_edge(text[start]):
        start += 1
    while end > start and an_edge(text[end - 1]):
        end -= 1
    return text[start:end]


def normalise(mutation):
    """The mutation as it is matched. See the docstring: NFKD, invisibles gone, whitespace
    collapsed, ends stripped by category, casefolded."""
    text = unicodedata.normalize("NFKD", mutation)
    text = "".join(c for c in text if unicodedata.category(c) not in INVISIBLE)
    text = unicodedata.normalize("NFC", text)
    return strip_edges(" ".join(text.split())).casefold()


def words(normalised):
    """The tokens that carry meaning: whitespace-separated, at least one letter or digit each,
    with their own punctuation off. In order, with repeats: the floor counts these."""
    return [strip_edges(w) for w in normalised.split() if any(c.isalnum() for c in w)]


def placeholder_problem(mutation):
    """Why this mutation is not evidence, or None. The whole rule, in one place (#239)."""
    normalised = normalise(mutation)
    tokens = words(normalised)
    distinct = set(tokens)
    if normalised in PLACEHOLDERS or (distinct and distinct <= PLACEHOLDERS):
        return f"{mutation.strip()!r}, which is a placeholder, not a mutation"
    if len(tokens) > 1 and len(distinct) == 1:
        return f"{mutation.strip()!r}, which is one word repeated, not a mutation"
    if len(tokens) < MINIMUM_WORDS or len(normalised) < MINIMUM_CHARACTERS:
        return (f"{mutation.strip()!r}, which is too short to be a mutation: at least "
                f"{MINIMUM_WORDS} words and {MINIMUM_CHARACTERS} characters are asked "
                f"for, and this is {len(tokens)} and {len(normalised)}")
    return None


def where_it_is(entry_id):
    """The overlay file an entry's item is in, for a refusal to name; its id when that is not a name."""
    return (f"`{overlay_step.path_for(entry_id)}`"
            if isinstance(entry_id, str) and overlay_step.NAME.match(entry_id) else f"overlay item {entry_id!r}")


def mutation_problems(entry_id, entry, from_overlay):
    """Rule #239, for one entry of the merge: an `implemented` entry records a real mutation per
    test. `from_overlay` says where the reader must go to fix it."""
    if not isinstance(entry, dict) or entry.get("status") != "implemented":
        return []
    tests = entry.get("tests")
    if not isinstance(tests, list):
        return []
    advice = (f"Make the edit, watch the test fail, undo it, record it in {where_it_is(entry_id)}, "
              "and re-produce with `tools/re-produce.sh`." if from_overlay else
              "This entry's `tests` come from the map package, not this engine's overlay, so the "
              "record to fix is upstream's and no re-produce here will change it: raise it against "
              f"the map, or set this engine's own `tests` for the entry in {where_it_is(entry_id)}.")
    problems = []
    for position, test in enumerate(tests, start=1):
        if not isinstance(test, dict):
            continue
        named = test.get("test") if isinstance(test.get("test"), str) else f"the test at position {position}"
        mutation = test.get("mutation")
        if not isinstance(mutation, str):
            why = ("records no mutation at all" if mutation is None else
                   f"records a {type(mutation).__name__}, which is not a mutation")
        else:
            why = placeholder_problem(mutation)
            if why is None:
                continue
            why = f"records {why}"
        problems.append(
            f"merged entry {entry_id!r} is implemented, and {named!r} {why}. A mutation is the edit "
            "you made to this engine that turned that test red, written down: what you changed, "
            f"where, and what the test then did. {advice} This refuses an unfilled "
            "placeholder; it cannot tell whether the edit was made or the test went red.")
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
        where = where_it_is(entry_id)
        if entry_id not in ids:
            problems.append(f"{where} names {entry_id!r}, which the package map has no entry for "
                            "(renamed or removed upstream?)")
        if not isinstance(item, dict):
            problems.append(f"{where} is not an object")
            continue
        if "status" not in item:
            problems.append(f"{where} does not set status")
        for key in item:
            if key not in OWNED and key not in rulings.KEYS:
                problems.append(f"{where} sets {key!r}; an engine owns only "
                                f"{', '.join(OWNED)} (and its owner's {' and '.join(rulings.KEYS)}), "
                                f"and every other field is the package's")
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

    # #239, and it reads the merge rather than the overlay: an implemented entry whose `tests` came
    # from the package map is checked too. The merge exists by here, and is returned only if it
    # holds; a refused merge writes nothing.
    for entry in merged_entries:
        entry_id = entry.get("id") if isinstance(entry, dict) else None
        problems += mutation_problems(entry_id, entry, from_overlay=entry_id in overlay)
    if problems:
        return None, problems

    return {key: (merged_entries if key == "entries" else value) for key, value in package.items()}, []


def canonical(document):
    return json.dumps(document, sort_keys=True, ensure_ascii=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description="merge(package map, the engine's overlay/) under 0015")
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("merge", help="write the merge; exit 1 when the overlay breaks a rule")
    m.add_argument("--package-map", required=True, action="append", metavar="PATH",
                   help="the restored package's map; repeat once per package for a composed "
                        "engine, with a --package-id each, in the same order (0067)")
    m.add_argument("--package-id", action="append", default=[], metavar="ID",
                   help="the package id of the --package-map at the same position")
    m.add_argument("--overlay", required=True, help="the engine's overlay directory")
    m.add_argument("--out", required=True)
    c = sub.add_parser("check", help="check the overlay, and a committed materialised map if given")
    c.add_argument("--package-map", required=True, action="append", metavar="PATH")
    c.add_argument("--package-id", action="append", default=[], metavar="ID")
    c.add_argument("--overlay", required=True, help="the engine's overlay directory")
    c.add_argument("--map")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.overlay).resolve().parent
    paths, ids = args.package_map, args.package_id
    if len(paths) > 1 and len(ids) != len(paths):
        print(f"error: {len(paths)} --package-map and {len(ids)} --package-id; a composed engine "
              f"names the package each map came from, because the entry ids it merges the overlay "
              f"on are qualified by it (rules-factory 0067)", file=sys.stderr)
        return 1
    try:
        package = compose.union(list(zip(ids or [None], (load(p) for p in paths)))
                                if len(paths) > 1 else [(None, load(paths[0]))])
        overlay = overlay_step.load(str(root), package)
    except (OSError, ValueError, compose.Refused, overlay_step.OverlayError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    merged, problems = merge(package, overlay, root=str(root))

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
    print(f"     merge(package, {overlay_step.DIRECTORY}/): {len(overlay)} of "
          f"{len(package.get('entries', []))} entries overlaid on {', '.join(OWNED)} only, in map order")
    for line in rulings.describe(overlay):
        print(f"     {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
