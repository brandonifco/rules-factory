"""The mapping inventory: what the extent claims, against what the walk reached (#255).

`extent` is a map's claim about how much of a corpus it read, and until now nothing evidenced
it. The locator checkers' `coverage` comes closest and asks a much coarser question -- is every
*page*, or every *section*, of the extent touched by some quote -- which a map satisfies by
reaching one sentence on a page and says nothing about the rest of it.

This asks it at the grain the corpus states rules in. `corpus.py` enumerates the units the
extent selects; here each unit is marked by one of three verdicts, and the three are exhaustive
by construction:

  **reached**       some entry's quoted evidence sits in it. The strongest of the three: a quote
                    found in the unit's own text, not a citation naming it.
  **rejected**      the mapper examined it and produced no entry, and recorded why. `method.md`
                    says to drop advice and note in the entry that you dropped it -- and a
                    passage that produced no entry at all has no entry to note it in, which is
                    exactly the passage a reader most needs to know was seen. That note lives in
                    `mapping-inventory.json`, beside the map.
  **unaccounted**   neither. Not a failure of the map and not a pass: nobody can tell from the
                    map whether it was read and dismissed or never opened, and that is the state
                    -- "nobody looked" -- a map exists to distinguish from a recorded verdict.

Unaccounted units are reported as **NOT VERIFIED** (exit 3), never as a failure. Whether a
passage owed an entry is decided by reading the corpus, and this tool does not read it.

## Why it is derived and not authored

Writing an inventory by hand for a map whose walk happened months ago would be fabricating a
record of that walk. Everything above except the rejections is measured on the spot from the
corpus and the map's own quotes; the rejections are the one part only the mapper can state, and
a rejection naming a unit the enumeration does not contain, or one an entry's quote reaches, is
a problem rather than a note -- the first is a claim about nothing, the second a contradiction.
"""
import json
import os

from mapcontract.entry import block, entries_of, label

from mapper.corpus import normalise
from mapper.protocol import Refused

#: Beside the map, like the protocol. Optional: a map that rejected nothing has no file, and
#: every unit is then reached or unaccounted.
INVENTORY_FILENAME = "mapping-inventory.json"
INVENTORY_VERSIONS = (1,)
INVENTORY_FIELDS = ("inventoryVersion", "corpus", "rejected")

# Why a passage examined in the extent produced no entry. Closed, for the reason every
# vocabulary here is closed: a ground nothing holds to a set means whatever the last writer
# thought, and "not a rule" would absorb all five of these.
GROUNDS = (
    "advice",            # guidance, not obligation (method.md, phase 2)
    "preamble",          # a lead-in that states nothing of its own
    "heading",           # the corpus's own structure, not a passage
    "page-furniture",    # a folio or a running head the extraction placed in the reading order
    "restatement",       # the same rule already mapped from the passage that states it
    "out-of-extent",     # printed inside the extent, about something outside it
    "beyond-adapter",    # the extraction cannot carry it (0004), so it was not examined as text
)
# An ellipsis in a quote, which is where a mapper elided the middle of a passage. Each fragment
# is looked for separately, and each one that is found reaches whatever units it touches.
ELLIPSIS = ("...", "…")


class Inventory:
    """One map's walk, measured against one extent."""

    def __init__(self, units, reached, rejected, problems, located, unlocated):
        self.units = units
        self.reached = reached        # unit key -> the entry ids whose evidence sits in it
        self.rejected = rejected      # unit key -> {"ground", "note"}
        self.problems = problems      # lines; each one fails the run
        self.located = located        # entry ids whose evidence was found inside the extent
        self.unlocated = unlocated    # entry ids whose evidence was not

    @property
    def unaccounted(self):
        return [u for u in self.units if u.key not in self.reached and u.key not in self.rejected]

    def by_kind(self):
        counts = {}
        for unit in self.units:
            counts[unit.kind] = counts.get(unit.kind, 0) + 1
        return counts


def path_beside(map_path):
    return os.path.join(os.path.dirname(os.path.abspath(map_path)) or ".", INVENTORY_FILENAME)


def load_rejections(path, corpus):
    """The examined-and-rejected verdicts recorded beside a map; `{}` when there is no file."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"cannot read {path}: {error}")
    if not isinstance(document, dict):
        raise Refused(f"{path} is not a JSON object")
    if document.get("inventoryVersion") not in INVENTORY_VERSIONS:
        raise Refused(f"{os.path.basename(path)} is version "
                      f"{document.get('inventoryVersion')!r}, which this reader does not read")
    for extra in sorted(set(document) - set(INVENTORY_FIELDS)):
        raise Refused(f"`{extra}` is not an inventory field; the three are "
                      + ", ".join(INVENTORY_FIELDS))
    if document.get("corpus") != corpus:
        raise Refused(f"{os.path.basename(path)} records rejections in corpus "
                      f"{document.get('corpus')!r}; the map's corpus is {corpus!r}")
    listed = document.get("rejected")
    if not isinstance(listed, list) or not listed:
        raise Refused(f"{os.path.basename(path)} records no rejection; a file that rejects "
                      f"nothing says less than no file at all")
    rejected = {}
    for position, item in enumerate(listed):
        where = f"rejected[{position}]"
        if not isinstance(item, dict):
            raise Refused(f"{where} is not an object")
        key, ground = item.get("unit"), item.get("ground")
        if not isinstance(key, str) or not key:
            raise Refused(f"{where} names no `unit`")
        if ground not in GROUNDS:
            raise Refused(f"{where}: ground {ground!r} is outside the closed set: "
                          + ", ".join(GROUNDS))
        note = item.get("note")
        if not isinstance(note, str) or not note.strip():
            raise Refused(f"{where}: a rejection carries a `note` saying what was examined and "
                          f"why it produced no entry; {ground!r} alone is a label, not a reading")
        if key in rejected:
            raise Refused(f"{where}: unit {key!r} is rejected twice")
        rejected[key] = {"ground": ground, "note": note}
    return rejected


def _fragments(evidence):
    """A quote's fragments: the whole of it, or the pieces an ellipsis divides it into."""
    text = normalise(evidence) if isinstance(evidence, str) else ""
    pieces = [text]
    for mark in ELLIPSIS:
        pieces = [p for piece in pieces for p in piece.split(mark)]
    return [normalise(p) for p in pieces if len(normalise(p).split()) >= 4]


def _joined(units):
    """The extent's units as one string, with the span each one occupies.

    The same join the section locator checker makes over its paragraphs, and for the same
    reason: a quote may run from one unit into the next, and a per-unit `in` test would find
    neither half.
    """
    pieces, spans, cursor = [], [], 0
    for unit in units:
        spans.append((cursor, cursor + len(unit.text), unit))
        pieces.append(unit.text)
        cursor += len(unit.text) + 1
    return " ".join(pieces), spans


def _occurrences(fragment, corpus):
    at, found = corpus.find(fragment), []
    while at != -1:
        found.append((at, at + len(fragment)))
        at = corpus.find(fragment, at + 1)
    return found


def take(units, document, rejected):
    """Measure the walk: which units its quotes reach, and which its rejections account for."""
    corpus, spans = _joined(units)
    known = {unit.key for unit in units}
    reached, located, unlocated = {}, [], []
    for position, entry in enumerate(entries_of(document)):
        if not isinstance(entry, dict) or "derivedFrom" in entry:
            # A derived entry (0012) cites nothing and quotes nothing: no sentence states its
            # fact. It reaches no unit, and counting it unlocated would report every map as
            # having quotes it cannot find.
            continue
        name = label(entry, position)
        hit = False
        for fragment in _fragments(entry.get("evidence")):
            for start, end in _occurrences(fragment, corpus):
                for lo, hi, unit in spans:
                    if lo < end and start < hi:
                        reached.setdefault(unit.key, set()).add(name)
                        hit = True
        (located if hit else unlocated).append(name)

    problems = []
    for key in sorted(rejected):
        if key not in known:
            problems.append(f"  X  {key!r} is recorded as examined and rejected, and the extent "
                            f"enumerates no such unit; a rejection of nothing accounts for "
                            f"nothing")
        elif key in reached:
            problems.append(f"  X  {key!r} is recorded as examined and rejected, and "
                            f"{', '.join(sorted(reached[key]))} quotes it; a passage cannot have "
                            f"produced no entry and be the evidence for one")
    return Inventory(units, reached, rejected, problems, located, unlocated)


def lines(inventory, map_name, corpus_name, adapter, extent, show_all=False):
    """The report, as lines. Counts first, because the counts are the measurement."""
    kinds = ", ".join(f"{count} {kind}" for kind, count in sorted(inventory.by_kind().items()))
    unaccounted = inventory.unaccounted
    out = [
        f"{map_name} against corpus {corpus_name!r} [{adapter}], extent "
        f"{json.dumps(extent, sort_keys=True)}",
        f"  enumerated:  {len(inventory.units)} unit(s) -- {kinds}",
        f"  reached:     {len(inventory.reached)} by the quoted evidence of "
        f"{len(inventory.located)} entr{'y' if len(inventory.located) == 1 else 'ies'}",
        f"  rejected:    {len(inventory.rejected)} examined and recorded as producing no entry",
        f"  unaccounted: {len(unaccounted)}",
    ]
    if inventory.unlocated:
        # Not an inventory failure: a `scope: out` entry quotes beyond the extent by design
        # (0020), and an entry whose evidence is a summary rather than a quote is unlocatable
        # anywhere. It is said out loud because it is the other way this measurement can be
        # wrong -- a quote nothing finds reaches nothing, and inflates the unaccounted count.
        out.append(f"  not located inside the extent: {len(inventory.unlocated)} entr"
                   f"{'y' if len(inventory.unlocated) == 1 else 'ies'} -- "
                   + ", ".join(inventory.unlocated))
    shown = unaccounted if show_all else unaccounted[:10]
    for unit in shown:
        out.append(f"  ?  {unit.key} [{unit.kind}]: {unit.text[:90]}"
                   + ("..." if len(unit.text) > 90 else ""))
    if len(shown) < len(unaccounted):
        out.append(f"  ?  ... and {len(unaccounted) - len(shown)} more; --list prints every one")
    out += inventory.problems
    return out
