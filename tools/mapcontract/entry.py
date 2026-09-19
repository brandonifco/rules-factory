"""How a map, an entry and a corpus manifest are read.

Every reader takes what it was given and answers anyway: a caller that has not yet proved the
document well-formed can still ask these questions, and gets an empty answer rather than an
exception it would have to distinguish from a real verdict.
"""


def corpora_of(manifest):
    if not isinstance(manifest, dict):
        return {}
    return {c.get("sourceId"): c for c in manifest.get("corpora") or [] if isinstance(c, dict)}


def quotes_withheld(manifest, entry):
    """True when the entry's corpus declares `quotation: withheld` (0013)."""
    source = corpora_of(manifest).get(block(entry, "locator").get("sourceId"))
    return isinstance(source, dict) and source.get("quotation") == "withheld"


def entries_of(doc):
    value = doc.get("entries")
    return value if isinstance(value, list) else []


def index(doc):
    return {e.get("id"): e for e in entries_of(doc) if isinstance(e, dict) and isinstance(e.get("id"), str)}


def label(entry, position):
    got = entry.get("id") if isinstance(entry, dict) else None
    return got if isinstance(got, str) else f"entry[{position}]"


def block(entry, name):
    value = entry.get(name)
    return value if isinstance(value, dict) else {}


def fate_of(entry):
    return block(entry, "ambiguity").get("fate")


def canonical_vocabulary(name):
    """A vocabulary name as every reader of the map sees it: surrounding whitespace removed.

    One canonical interpretation, here, because two of them is the defect (#314 review): the
    checker normalised a declaration before judging it and the reader returned the raw strings,
    so `" special-provision-codes "` could be proved and `"special-provision-codes"` looked up,
    and a code the map declared was read as undeclared with nothing saying so. **What the
    validator accepts, every consumer must read the same way**, so the canonical form lives at
    the contract boundary and validation, the protocol and the detector all read it.

    Not a string is `""`, which no vocabulary is: the caller reports the malformation it owns.
    """
    return name.strip() if isinstance(name, str) else ""


def canonical_term(term):
    """A term as every reader sees it: whitespace-normalised, as `crossReferences.cites` is.

    A term is quoted from the corpus, and a quote's internal spacing is the extraction's rather
    than the corpus's -- which is why the anchoring checks compare against evidence read the same
    way. `canonical_vocabulary` only strips, because a vocabulary name is the map's own word and
    not a quotation.
    """
    return " ".join(term.split()) if isinstance(term, str) else ""


def definition_of(item):
    """One `defines` item as `(vocabulary, term)`, canonically, or None when it is not one."""
    if not isinstance(item, dict):
        return None
    vocabulary = canonical_vocabulary(item.get("vocabulary"))
    term = canonical_term(item.get("term"))
    return (vocabulary, term) if vocabulary and term else None


def defines_of(entry):
    """The `(vocabulary, term)` pairs an entry declares it defines, in declaration order (0045).

    A vocabulary is distributed over the entries that define its terms: the corpus that forced
    `coded-pointer` prints its codes one per table row and has no passage that lists them, so
    there is no entry a protocol could name as *the* vocabulary. Each defining entry declares
    the term it defines instead, and the vocabulary is what those declarations add up to.

    Malformed items are skipped rather than reported here -- `check-map.py --only defines` owns
    the judgement, and a reader that raised would make every other check depend on this one.
    """
    declared = entry.get("defines") if isinstance(entry, dict) else None
    found = []
    for item in declared if isinstance(declared, list) else []:
        canonical = definition_of(item)
        if canonical is not None:
            found.append(canonical)
    return found


def definition_continuation_of(entry):
    """One `continuesDefinition` as `(definedBy, sourceId, citation)`, or None (0046).

    A continuation writes no vocabulary or term of its own. It names the entry that directly
    defines the term and carries a structural locator witnessing that this passage sits under that
    defining passage. Shape errors are reported by the validator; every consumer reads this one
    tolerant canonical form.
    """
    if not isinstance(entry, dict):
        return None
    declared = entry.get("continuesDefinition")
    if not isinstance(declared, dict):
        return None
    target = declared.get("definedBy")
    anchor = declared.get("anchor")
    if not isinstance(target, str) or not target:
        return None
    if not isinstance(anchor, dict):
        return None
    source = anchor.get("sourceId")
    citation = anchor.get("citation")
    if not isinstance(source, str) or not source or not isinstance(citation, str) or not citation:
        return None
    return target, source, citation


def defined_vocabulary(doc, name):
    """One named vocabulary as `{term: [every entry that defines it]}` (0044-0046).

    Direct definitions come from evidence-anchored `defines` exactly as 0045 specifies.
    A `continuesDefinition` entry then joins the **one** direct definition made by its
    `definedBy` target. It copies neither vocabulary nor term: both are inherited from that
    target, which is why an additional rule whose own evidence omits the printed code can join
    the same defining set without weakening direct anchoring.

    Readers apply the map-level invariants here too: the continuation has no direct `defines`,
    its target exists, directly defines exactly one term, is not itself a continuation, and all
    three locators name the same corpus. The locator checker separately proves the structural
    anchor resolves to this passage under that target (0046).

    A vocabulary no entry defines is `{}`. Declaration order decides nothing semantically, but
    ids are returned in map order for stable diagnostics.
    """
    wanted, terms = canonical_vocabulary(name), {}
    if not wanted:
        return terms
    entries = entries_of(doc)
    by_id = index(doc)

    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        direct = defines_of(entry)
        if direct:
            for vocabulary, term in direct:
                if vocabulary == wanted and entry["id"] not in terms.setdefault(term, []):
                    terms[term].append(entry["id"])
            continue

        continuation = definition_continuation_of(entry)
        if continuation is None:
            continue
        target_id, anchor_source, _ = continuation
        target = by_id.get(target_id)
        if not isinstance(target, dict) or definition_continuation_of(target) is not None:
            continue
        target_definitions = defines_of(target)
        if len(target_definitions) != 1:
            continue
        entry_source = block(entry, "locator").get("sourceId")
        target_source = block(target, "locator").get("sourceId")
        if not entry_source or entry_source != target_source or entry_source != anchor_source:
            continue
        vocabulary, term = target_definitions[0]
        if vocabulary == wanted and entry["id"] not in terms.setdefault(term, []):
            terms[term].append(entry["id"])
    return terms
