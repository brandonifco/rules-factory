"""An applicability rule whose own words gate a whole section, and what the map says it gates
(#225).
"""
import re

from .diagnostics import skip, verdict
from mapcontract.vocabulary import GATE_FIELDS
from mapcontract.entry import entries_of, label

# The units a passage can gate all of. A paragraph is not among them: "this paragraph (e)" is a
# scope a definition states about itself, and every definition in the tax map would be a gate.
WHOLE_UNITS = (r"section|part|subpart|chapter|subchapter|title|table|appendix|schedule|glossary"
               r"|book|rules")
# The words a corpus gates a whole unit in. A list, exactly as `POINTER_PHRASES` is a list, and
# with the same limit stated where the claim is: a corpus that says it in other words is unseen.
# Group 1 is the word before the phrase and group 2 is the unit, both read by `gates_a_whole_unit`.
WHOLE_UNIT_GATES = (
    re.compile(r"(\w+\s+)?\bthis\s+(" + WHOLE_UNITS + r")\s+(?:is|are|shall be|will be)\s+"
               r"(?:applicable|effective|in effect)\b", re.I),
    re.compile(r"(\w+\s+)?\bthis\s+(" + WHOLE_UNITS + r")\s+"
               r"(?:applies|apply|shall apply|shall not apply|does not apply|do not apply)\b", re.I),
    re.compile(r"(\w+\s+)?\b(?:applies|applicable|apply)\s+(?:to|for)\s+"
               r"(?:all|every|the\s+whole\s+of|the\s+entirety\s+of)\s+(?:this\s+)?(" + WHOLE_UNITS
               + r")\b", re.I),
)
# A unit word behind one of these is the tail of a citation, not the subject of the sentence.
# § 172.102(c)(7)(ii) says "§ 178.275(g)(3) of this subchapter does not apply", which switches off
# one cited paragraph; reading it as the subchapter switching itself off flagged a committed map.
CITATION_TAILS = ("of", "in", "under", "to", "within", "for", "by", "from", "on", "throughout")


def gates_a_whole_unit(evidence):
    """`(the words, the unit)` by which this passage gates a whole unit of the corpus, or None."""
    text = " ".join(str(evidence or "").split())
    for pattern in WHOLE_UNIT_GATES:
        for match in pattern.finditer(text):
            if (match.group(1) or "").strip().lower() in CITATION_TAILS:
                continue
            return match.group(0).strip(), match.group(2).lower()
    return None


def gated_ids(document):
    """Every id named in `enabledBy` or `suspendedBy` anywhere in the map."""
    named = set()
    for entry in entries_of(document):
        if not isinstance(entry, dict):
            continue
        for field in GATE_FIELDS:
            for target in entry.get(field) or []:
                if isinstance(target, str):
                    named.add(target)
    return named


def check_applicability_reach(ctx):
    """A rule whose own words gate a whole unit is named by the entries it gates (#225).

    § 1.121-1(f) -- *"This section is applicable for sales and exchanges on or after December 24,
    2002"* -- gates everything § 1.121-1 states. Trial 9's blind first mapping recorded the entry
    and **no entry pointed at it**, so every rule it gates was recorded as applying
    unconditionally; the third mapping added 30 `enabledBy` edges to correct it. Every check
    passed the first map. This is `docs/method.md`'s own `full-table-suspension` warning arriving
    a third time.

    So: a `scope: in` entry whose `evidence` states an applicability over a whole section, part,
    table or chapter, and whose id no entry names in `enabledBy` or `suspendedBy`, is refused.
    `suspendedBy` counts as reach because a rule that switches a section off gates it as surely
    as one that switches it on.

    Deciding what "gates by its own words" means mechanically is the work, and the answer here is
    a phrase list with the same standing as `POINTER_PHRASES`: `WHOLE_UNIT_GATES` holds the forms
    the CFR corpora use, the unit words are `WHOLE_UNITS`, and a corpus that gates itself in other
    words is not seen. A paragraph is deliberately not a whole unit -- "for purposes of this
    paragraph (e)" is a definition stating its own scope, and admitting it would make a gate of
    every definition in the tax map.

    What it cannot do, and each is a place a mapper still has to read:

      * **It cannot tell how far the gate reaches.** One edge satisfies it. The first map had
        zero and the corrected map thirty; a map with one would pass here, and whether the list
        is complete is review -- the same limit `gates` states about direction.
      * **It has no way to record a gate with deliberately no reach.** Such a gate is possible,
        and the honest answer was not a `note`: the first tax map's `effective-date` already
        carries a note that names the section, so any rule satisfied by prose about the unit
        would have been satisfied by the very entry this check exists to flag. The answer is
        therefore the edge, or `scope: out` where the map does not reach the gate at all, and a
        corpus that truly holds a reachless gate is a finding to file rather than a flag to
        suppress.
      * **It reads the map, never the corpus.** A passage that gates a whole section in words
        outside the list is invisible here, exactly as a pointer in undeclared words is invisible
        to `cross-references`.
    """
    named, bad, gates = gated_ids(ctx["map"]), [], []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict) or entry.get("scope") != "in":
            continue
        found = gates_a_whole_unit(entry.get("evidence"))
        if found is None:
            continue
        words, unit = found
        name = label(entry, position)
        gates.append(name)
        if entry.get("id") in named:
            continue
        bad.append(f"  X  {name}: `evidence` says {words!r}, so its own words gate the whole "
                   f"{unit}, and no entry names it in `enabledBy` or `suspendedBy`. Every rule "
                   f"the {unit} states is recorded as applying unconditionally: name this rule "
                   f"in the gate lists of the entries it reaches, or put it out of scope (#225)")
    if not gates:
        return skip("no entry's own words gate a whole section, part or table, so this map "
                    "records no applicability rule whose reach could be missing", had_subject=False)
    return verdict(bad, f"{len(gates)} entr{'y gates' if len(gates) == 1 else 'ies gate'} a whole "
                        f"unit of the corpus, and the map says of each which rules it gates",
                   "an applicability rule gates a whole unit and no entry says it is gated")
