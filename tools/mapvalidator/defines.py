"""A term an entry defines is declared by that entry, and anchored in its own evidence (0045).

`crossReferences` records a pointer the entry's passage *makes*. `defines` records a term the
entry's passage *gives a meaning to*. They are opposite directions, and neither implies the
other: the § 172.101 row cell that prints `IB3` points at the two § 172.102 rows that define it,
and those two rows point at nothing.

The two share one rule, which is 0026's and is why `defines` is a field and not a list in the
protocol: **the declaration is anchored in the corpus's words.** A `cites` appears verbatim in
the evidence of the entry that makes the reference; a `term` appears verbatim in the evidence of
the entry that defines it. An entry whose evidence reads *"The following tables list … the
special provisions referred to in column 7"* and whose declarations name twenty codes it does not
print is a registry someone wrote, not a passage of the corpus, and that is the shape #314
refused to create.
"""
from .diagnostics import skip, verdict
from mapcontract.vocabulary import DEFINES_FIELDS
from mapcontract.entry import entries_of, label


def check_defines(ctx):
    """Every `defines` declaration: its shape, and its anchor in the entry's own evidence.

    Optional, and checked entirely where it appears. What it must be, and why each half of it:

      * a **non-empty list** -- an empty one declares nothing and reads as a vocabulary the entry
        belongs to;
      * each item **exactly** `vocabulary` and `term`, both non-empty strings. A third key is
        refused rather than ignored, for the reason the map's envelope refuses one (#60): an
        unread key looks like it is doing work;
      * the `term` **verbatim in this entry's `evidence`**, whitespace-normalised as
        `crossReferences` normalises a `cites`. An entry defines a term by printing it;
      * the same `(vocabulary, term)` **once** per entry. A second identical declaration adds
        nothing, and the likeliest reason it is there is that another term or another vocabulary
        was meant -- the reasoning 0044 already applied to a repeated `crossReferences` pair.

    Two things it deliberately does not check. That the vocabulary is one some protocol reads:
    the protocol is the mapper's and this subsystem does not read it (0032), and
    `tools/mapper/protocol.py` refuses a `coded-pointer` naming a vocabulary no entry defines.
    And that the passage really does define the term rather than merely printing it -- that is
    interpretive, and the anchor is what can be held mechanically.

    A derived entry carrying `defines` is refused by `--only derived`, which refuses every
    passage field on one, so nothing here reads a derived entry.
    """
    bad, entries, declaring, declarations = [], entries_of(ctx["map"]), 0, 0
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict) or "defines" not in entry or "derivedFrom" in entry:
            continue
        name = label(entry, position)
        declaring += 1
        declared = entry["defines"]
        if not isinstance(declared, list) or not declared:
            bad.append(f"  X  {name}: `defines` is {declared!r}; it is a non-empty list of the "
                       f"terms this passage defines, and an empty one declares nothing")
            continue
        evidence = " ".join(str(entry.get("evidence") or "").split())
        seen = set()
        for item in declared:
            declarations += 1
            if not isinstance(item, dict):
                bad.append(f"  X  {name}: defines holds {item!r}, which is not an object")
                continue
            if set(item) != set(DEFINES_FIELDS):
                held = ", ".join(f"`{field}`" for field in sorted(item)) or "nothing"
                bad.append(f"  X  {name}: a defines item holds {held}; an item is exactly "
                           f"`vocabulary` and `term`, and a key nothing reads is refused rather "
                           f"than ignored")
                continue
            vocabulary, term = item["vocabulary"], item["term"]
            if not isinstance(vocabulary, str) or not vocabulary.strip() \
                    or not isinstance(term, str) or not term.strip():
                bad.append(f"  X  {name}: defines item {item!r} has a `vocabulary` or `term` "
                           f"that is not a non-empty string")
                continue
            vocabulary, term = vocabulary.strip(), " ".join(term.split())
            if term not in evidence:
                bad.append(f"  X  {name}: defines {term!r}, which does not appear in this "
                           f"entry's `evidence`; a definition is anchored in the passage that "
                           f"makes it, as a reference is (0026, 0045)")
                continue
            if (vocabulary, term) in seen:
                bad.append(f"  X  {name}: declares {term!r} in vocabulary {vocabulary!r} more "
                           f"than once; a term may be defined by several entries, and one entry "
                           f"declaring it twice says nothing the first declaration does not")
                continue
            seen.add((vocabulary, term))
    if not declaring:
        return skip("no entry declares `defines`, so there is no definition to anchor",
                    had_subject=False)
    return verdict(bad, f"{declarations} definition(s) declared by {declaring} entr(ies), each "
                        f"naming one vocabulary and a term its own evidence prints",
                   "a `defines` declaration is malformed or unanchored")
