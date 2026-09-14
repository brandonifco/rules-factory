"""A pointer the corpus makes in an entry's evidence is answered by a `crossReferences` item:
an entry, or a recorded reason there is none (0009).
"""
from .diagnostics import skip, verdict
from .model import entries_of, index, label


# The corpus's own pointers, in the words it uses to make them. Each phrase points at
# another designated passage and at nothing else: "subject to a certain qualification--viz."
# points forward inside its own sentence and is deliberately not here, because a check that
# fires on a self-reference teaches mappers to work around it.
POINTER_PHRASES = [
    "except as provided in",
    "as provided in",
    "in accordance with §",
    "pursuant to §",
    "as in Fig.",
    "shown in Fig.",
    "see Fig.",
    "to be hereafter stated",
    "as at starting",
]


def pointers_in(evidence):
    """The pointer phrases this evidence makes, longest first, without their prefixes.

    "Except as provided in" contains "as provided in"; reporting both would demand two
    declarations for one pointer.
    """
    text = " ".join(str(evidence or "").split()).lower()
    found = [phrase for phrase in POINTER_PHRASES if phrase.lower() in text]
    return [p for p in found if not any(p != q and p.lower() in q.lower() for q in found)]


def check_cross_references(ctx):
    """A reference the corpus makes is an entry, or a recorded reason there is none (0009).

    § 107.29(a) opens *"Except as provided in paragraph (d) of this section"* and (d) has no
    entry in either Part 107 map. Nothing detected that, because a cross-reference was a
    sentence in an `evidence` span and no field made a mapper answer it.

    Each pointer phrase the evidence contains must be claimed by a `crossReferences` entry
    whose `cites` appears verbatim in that same evidence -- so the declaration is anchored
    to the corpus's words rather than asserted beside them -- and resolved exactly one way:
    `resolvedBy`, an entry id in this map, or `unmapped`, a reason there is no entry.

    Two limits, stated where the claim is. The phrase list is closed and short, so a corpus
    that points somewhere in other words passes silently -- `starting-position` quotes
    *"as shown in {273} Fig. 1"* and the page marker falling inside the phrase is enough to
    hide it. And `unmapped` is prose, which 0003 and 0004 both rejected as a carrier: what
    is checked is that a mapper was made to write one, not that what they wrote is true.
    """
    by_id, bad, pointers, declared = index(ctx["map"]), [], 0, 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        evidence = " ".join(str(entry.get("evidence") or "").split())
        made = pointers_in(evidence)
        pointers += len(made)
        references = entry.get("crossReferences")
        if references is None:
            references = []
        elif not isinstance(references, list):
            bad.append(f"  X  {name}: `crossReferences` is not a list")
            references = []
        claimed = []
        for item in references:
            declared += 1
            if not isinstance(item, dict):
                bad.append(f"  X  {name}: crossReferences holds {item!r}, which is not an object")
                continue
            cites = item.get("cites")
            if not isinstance(cites, str) or not cites.strip():
                bad.append(f"  X  {name}: a crossReferences item has no `cites` naming the "
                           f"corpus's own words")
                continue
            if " ".join(cites.split()) not in evidence:
                bad.append(f"  X  {name}: crossReferences cites {cites!r}, which does not appear "
                           f"in this entry's `evidence`; a reference is anchored to the passage "
                           f"that makes it")
                continue
            claimed.append(cites)
            has_resolution = isinstance(item.get("resolvedBy"), str) and item["resolvedBy"].strip()
            has_reason = isinstance(item.get("unmapped"), str) and item["unmapped"].strip()
            if has_resolution and has_reason:
                bad.append(f"  X  {name}: crossReferences {cites!r} names both `resolvedBy` and "
                           f"`unmapped`; a reference is an entry or a recorded reason there is "
                           f"none, not both")
            elif not has_resolution and not has_reason:
                bad.append(f"  X  {name}: crossReferences {cites!r} resolves to nothing; name the "
                           f"entry in `resolvedBy` or the reason there is none in `unmapped`")
            elif has_resolution:
                target = item["resolvedBy"]
                if target not in by_id:
                    bad.append(f"  X  {name}: crossReferences {cites!r} resolves to {target!r}, "
                               f"which is not an entry in this map; the reference is the finding")
                elif target == entry.get("id"):
                    bad.append(f"  X  {name}: crossReferences {cites!r} resolves to itself")
        for phrase in made:
            if not any(phrase.lower() in " ".join(c.split()).lower() for c in claimed):
                bad.append(f"  X  {name}: `evidence` says {phrase!r} and no `crossReferences` "
                           f"item claims it; a reference is an entry or a recorded reason "
                           f"there is none")
    if not pointers and not declared:
        return skip("no entry's evidence makes a pointer this check knows and none declares a "
                    "crossReferences item, so the obligation is vacuous over this map",
                    had_subject=False)
    return verdict(bad, f"{pointers} pointer{'' if pointers == 1 else 's'} in evidence, "
                        f"{declared} declared: each is anchored in the passage that makes it and "
                        f"names an entry or a reason there is none",
                   "a cross-reference the corpus makes is unanswered")
