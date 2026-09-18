"""Detecting a pointer the corpus makes by naming a term it defines elsewhere (#208).

The built-in and declared `pointerPhrases` (0026) find a pointer by the words around it -- *see*,
*as described in*, *subject to*. Against a corpus that points by simply **naming a defined
term**, they find nothing, and no phrase can be added that would work: the words that constitute
a pointer in one entry are the words of the definition in another.

  * in `paralyzed-incapacitated`: "You have the **Incapacitated** condition" -- a pointer
  * in `incapacitated`'s own lead: "While you have the **Incapacitated** condition" -- the
    definition

A phrase list cannot separate those; the strings are identical. What separates them is **where
the sentence is**. A naming of a term inside the passage that defines the term is the definition;
a naming of it anywhere else is a pointer. The passage is the container the citation names
(0030), so two entries whose locators cite the same container are inside the same definition, and
a term named in one of them is not pointing anywhere.

That generalises past this corpus, which is the test of it: a regulation's defined terms, a
contract's capitalised definitions, a rulebook's keywords. The vocabulary is read out of the map
-- the corpus already states it somewhere and that statement is an entry -- so nothing here
carries a list of words, and no corpus is named in this file.

What it does not do. It reads `evidence`, which is the corpus's words for the rule and not the
whole passage, so a naming outside every entry's quoted span is invisible to it. It matches a
term exactly, so a corpus that inflects its defined terms needs a mechanism this is not.
"""
import re

from mapcontract.entry import entries_of, index

from mapper.protocol import citation_of, mechanisms_of, vocabulary_of


class Naming:
    """One occurrence of a defined term in an entry that does not define it."""

    def __init__(self, entry_id, term, defines, count, declared):
        self.entry_id = entry_id
        self.term = term
        self.defines = defines      # the entry the term's own definition is in
        self.count = count          # how many times the entry's evidence names it
        self.declared = declared    # whether a crossReferences item already names this term

    def __repr__(self):
        return (f"Naming({self.entry_id!r}, {self.term!r}, x{self.count}, "
                f"declared={self.declared})")


def _names(text, term):
    """How many times `text` names `term`, on word boundaries and exactly as printed."""
    if not isinstance(text, str) or not term:
        return 0
    edge = r"\b" if term[0].isalnum() else ""
    tail = r"\b" if term[-1].isalnum() else ""
    return len(re.findall(edge + re.escape(term) + tail, text))


def detect(document, vocabulary_entry):
    """Every naming of a defined term outside the passage that defines it."""
    entries = entries_of(document)
    by_id = index(document)
    terms = vocabulary_of(vocabulary_entry)
    # Where each term is defined, as a citation: every entry citing it is inside that definition.
    home = {}
    for term, defining in terms.items():
        entry = by_id.get(defining)
        if entry is not None:
            home[term] = citation_of(entry)

    found = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        citation = citation_of(entry)
        declared = {reference.get("cites") for reference in entry.get("crossReferences") or []
                    if isinstance(reference, dict)}
        for term in sorted(terms):
            if term not in home or citation == home[term]:
                continue
            count = _names(entry.get("evidence"), term)
            if count:
                found.append(Naming(entry.get("id"), term, terms[term], count,
                                    any(term in (cites or "") for cites in declared)))
    return found


#: The column a table-cell citation names, as 0035 writes it: `..., column 7`, after the row key
#: and outside it. Anchored on the key's closing bracket, so the `column 2 = "Acetal"` *inside* the
#: key can never be read as the cell's column.
CITED_COLUMN = re.compile(r"\]\s*,\s*column\s+([A-Za-z0-9]{1,4})\s*\.?\s*$")

#: What separates one code from the next in a cell that holds several: `IB2, T4, TP1`. Commas and
#: whitespace only. Nothing here reads the corpus's prose, which is the point of the mechanism.
CODE_SEPARATOR = re.compile(r"[,\s]+")


def cited_column(entry):
    """The column an entry's citation names, or None when it names no cell."""
    match = CITED_COLUMN.search(str((entry.get("locator") or {}).get("citation") or ""))
    return match.group(1) if match else None


def detect_coded(document, mechanism):
    """Every code in the pointer-bearing column, as pointers (0041).

    The mechanism's `column` says which column of the corpus's own numbering carries pointers.
    An entry is examined **only** when its citation names a cell in that column; everything else
    in the map -- another column of the same row, a paragraph of prose -- is not read at all.
    That is what makes this not a scan: the same token in another column is not a pointer, and
    the measurement that forced the mechanism is exactly a token that spells like one and is not
    (#307).

    Tokenising is by comma and whitespace, because that is how the corpus prints a cell holding
    several codes. A token the vocabulary does not declare is still returned, with `defines` None,
    so `report` can say so rather than drop it.
    """
    wanted = str(mechanism.get("column") or "").strip()
    if not wanted:
        return []
    terms = {}
    by_id = index(document)
    source = by_id.get(mechanism.get("vocabularyFrom"))
    if source is not None:
        terms = vocabulary_of(source)
    found = []
    for entry in entries_of(document):
        if not isinstance(entry, dict) or cited_column(entry) != wanted:
            continue
        declared = {reference.get("cites") for reference in entry.get("crossReferences") or []
                    if isinstance(reference, dict)}
        seen = {}
        for token in CODE_SEPARATOR.split(str(entry.get("evidence") or "")):
            token = token.strip()
            if token:
                seen[token] = seen.get(token, 0) + 1
        for token, count in sorted(seen.items()):
            found.append(Naming(entry.get("id"), token, terms.get(token), count,
                                token in declared))
    return found


def report(protocol, document):
    """Run every `defined-term-use` mechanism the protocol declares.

    Returns (lines, detected, undeclared). `detected` is what makes a silent zero visible: a
    corpus that declares this mechanism and on which nothing fires has either the wrong mechanism
    declared or a map whose evidence spans do not reach the pointers, and 0026 already refuses
    that shape for phrases.
    """
    lines, detected, undeclared = [], 0, []
    by_id = index(document)
    for mechanism in mechanisms_of(protocol, "coded-pointer"):
        column = mechanism.get("column")
        namings = detect_coded(document, mechanism)
        detected += sum(n.count for n in namings)
        cells = len({n.entry_id for n in namings})
        lines.append(f"  column {column}: {sum(n.count for n in namings)} code(s) in {cells} "
                     f"cell(s); a token in another column is not a pointer (0041)")
        for naming in namings:
            if naming.defines is None:
                # Not dropped. A code in the pointer-bearing column that the vocabulary does not
                # declare is either a pointer nobody recorded or a vocabulary that is short, and
                # both are findings.
                undeclared.append(naming)
                lines.append(f"  ?  {naming.entry_id}: column {column} holds {naming.term!r}, "
                             f"which the vocabulary does not declare")
            elif not naming.declared:
                undeclared.append(naming)
                lines.append(f"  ?  {naming.entry_id}: column {column} points with "
                             f"{naming.term!r} and the entry declares no crossReference to "
                             f"{naming.defines!r}")
    for mechanism in mechanisms_of(protocol, "defined-term-use"):
        source = mechanism.get("vocabularyFrom")
        entry = by_id.get(source)
        if entry is None:
            lines.append(f"  X  vocabularyFrom {source!r} is not an entry in this map")
            continue
        terms = vocabulary_of(entry)
        namings = detect(document, entry)
        detected += sum(n.count for n in namings)
        lines.append(f"  {len(terms)} term(s) declared by {source!r}; "
                     f"{sum(n.count for n in namings)} naming(s) of one outside its own passage, "
                     f"in {len({n.entry_id for n in namings})} entr(ies)")
        for naming in namings:
            if not naming.declared:
                undeclared.append(naming)
                lines.append(f"  ?  {naming.entry_id}: names {naming.term!r} "
                             f"x{naming.count} and declares no crossReference to "
                             f"{naming.defines!r}")
    return lines, detected, undeclared
