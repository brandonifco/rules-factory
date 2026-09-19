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
        if not isinstance(item, dict):
            continue
        name, term = item.get("vocabulary"), item.get("term")
        if isinstance(name, str) and name and isinstance(term, str) and term:
            found.append((name, term))
    return found


def defined_vocabulary(doc, name):
    """One named vocabulary, as `{term: [the ids of every entry that defines it]}` (0045).

    **One printed code can name more than one rule** (0044), and here that cardinality is not a
    special case: `IB3` has two defining entries because two entries declare they define it, in
    § 172.102's table 2 and its table 4. The ids are in the order the map states them, and an id
    that declares one term twice appears once -- `check-map.py --only defines` reports the
    repetition, so the two cases stay distinguishable.

    A vocabulary no entry defines is `{}`, which is what makes a protocol naming one refusable.
    """
    terms = {}
    for entry in entries_of(doc):
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        for vocabulary, term in defines_of(entry):
            if vocabulary == name and entry["id"] not in terms.setdefault(term, []):
                terms[term].append(entry["id"])
    return terms
