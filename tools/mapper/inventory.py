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
  **rejected**      the mapper examined it and produced no entry, and recorded why. Its identity
                    is (`sourceId`, `unit`): unit keys are stable only inside the corpus whose
                    adapter enumerated them. `method.md`
                    says to drop advice and note in the entry that you dropped it -- and a
                    passage that produced no entry at all has no entry to note it in, which is
                    exactly the passage a reader most needs to know was seen. That note lives in
                    `mapping-inventory.json`, beside the map.
  **unaccounted**   neither. Not a failure of the map and not a pass: nobody can tell from the
                    map whether it was read and dismissed or never opened, and that is the state
                    -- "nobody looked" -- a map exists to distinguish from a recorded verdict.

A fourth thing cuts across those three. A unit may be text the corpus prints that **no citation
can resolve into** (0036): an appendix the section's designation grammar does not reach, a
wrapper whose contents state designations of their own. The enumeration counts it, because
dropping it would shrink the denominator to what happened to be citable. But a quote of it is
**not coverage of it** -- the locator run would report that entry unchecked and fail -- so a map
that claims to have reached one is a `problem` here, and a run that merely contains one is NOT
VERIFIED with the count said out loud. Accounting for such a unit means recording a rejection
against it, which is the one verdict that does not require an address.

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
INVENTORY_VERSIONS = (1, 2)
INVENTORY_FIELDS = {
    1: ("inventoryVersion", "corpus", "rejected"),
    2: ("inventoryVersion", "rejected"),
}

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

    @property
    def unaddressable(self):
        """Units no citation can resolve into (0036), whatever else is true of them."""
        return [u for u in self.units if u.unaddressable]

    def by_kind(self):
        counts = {}
        for unit in self.units:
            counts[unit.kind] = counts.get(unit.kind, 0) + 1
        return counts


def path_beside(map_path):
    return os.path.join(os.path.dirname(os.path.abspath(map_path)) or ".", INVENTORY_FILENAME)


def load_rejections(path, corpora):
    """The examined-and-rejected verdicts, partitioned by every corpus the map cites.

    Version 1 bound the whole document to one corpus. It remains readable for a single-corpus
    map with exactly that meaning, and is refused for a multi-corpus map rather than silently
    supplying one corpus's accounting to a walk of several. Version 2 puts `sourceId` on each
    rejection, because a rejection is a verdict about one unit and a unit key has meaning only
    inside the corpus whose adapter enumerated it (0009, 0039, 0042).
    """
    cited = tuple(sorted(set(corpora)))
    if not os.path.exists(path):
        return {corpus: {} for corpus in cited}
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"cannot read {path}: {error}")
    if not isinstance(document, dict):
        raise Refused(f"{path} is not a JSON object")
    version = document.get("inventoryVersion")
    if version not in INVENTORY_VERSIONS:
        raise Refused(f"{os.path.basename(path)} is version "
                      f"{version!r}, which this reader does not read")
    fields = INVENTORY_FIELDS[version]
    for extra in sorted(set(document) - set(fields)):
        raise Refused(f"`{extra}` is not an inventory version {version} field; the fields are "
                      + ", ".join(fields))
    listed = document.get("rejected")
    if not isinstance(listed, list) or not listed:
        raise Refused(f"{os.path.basename(path)} records no rejection; a file that rejects "
                      f"nothing says less than no file at all")

    if version == 1:
        corpus = document.get("corpus")
        if len(cited) != 1:
            raise Refused(f"{os.path.basename(path)} version 1 records rejections in one corpus "
                          f"({corpus!r}), but the map cites {len(cited)} corpora; version 2 puts "
                          f"`sourceId` on each rejection")
        if not cited or corpus != cited[0]:
            expected = cited[0] if cited else None
            raise Refused(f"{os.path.basename(path)} records rejections in corpus {corpus!r}; "
                          f"the map's corpus is {expected!r}")

    rejected = {corpus: {} for corpus in cited}
    for position, item in enumerate(listed):
        where = f"rejected[{position}]"
        if not isinstance(item, dict):
            raise Refused(f"{where} is not an object")
        source = document.get("corpus") if version == 1 else item.get("sourceId")
        if not isinstance(source, str) or not source:
            raise Refused(f"{where} names no `sourceId`; a unit has identity only inside the "
                          f"corpus whose adapter enumerated it")
        if source not in rejected:
            raise Refused(f"{where}: sourceId {source!r} names a corpus the map does not cite")
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
        if key in rejected[source]:
            raise Refused(f"{where}: unit {key!r} in corpus {source!r} is rejected twice")
        rejected[source][key] = {"ground": ground, "note": note}
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
    for unit in units:
        if unit.unaddressable and unit.key in reached:
            # The contradiction 0036 makes visible: no citation resolves into this unit, so the
            # locator run reports the entry that quotes it unchecked and fails. Counting it as
            # reached here would have the two tools disagree about the same passage, with the
            # inventory the more forgiving of the two -- which is the direction this repository
            # must never be wrong in.
            problems.append(f"  X  {unit.key!r} is quoted by "
                            f"{', '.join(sorted(reached[unit.key]))} and no citation can resolve "
                            f"into it -- {unit.unaddressable}. A quote of a passage with no "
                            f"address is not coverage of it: record a rejection against it, or "
                            f"give it an address")
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
    if inventory.unaddressable:
        out.append(f"  no address:  {len(inventory.unaddressable)} unit(s) no citation can "
                   f"resolve into (0036), so a quote of one is not coverage of it")
        for unit in inventory.unaddressable[:5] if not show_all else inventory.unaddressable:
            out.append(f"  -  {unit.key} [{unit.kind}]: {unit.unaddressable}")
        if not show_all and len(inventory.unaddressable) > 5:
            out.append(f"  -  ... and {len(inventory.unaddressable) - 5} more; --list prints "
                       f"every one")
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
