"""A pointer the corpus makes in an entry's evidence is answered by a `crossReferences` item:
an entry, or a recorded reason there is none (0009). Which words count as a pointer is the
built-in list plus the phrases each corpus declares in the manifest (0026).
"""
import re

from .diagnostics import skip, verdict
from mapcontract.entry import block, corpora_of, entries_of, index, label


# The pointers the first corpora made, in the words they used to make them. Each phrase points
# at another designated passage and at nothing else: "subject to a certain qualification--viz."
# points forward inside its own sentence and is deliberately not here, because a check that
# fires on a self-reference teaches mappers to work around it. A corpus that points in other
# words declares them as `pointerPhrases` in its manifest entry (0026); this list is what every
# corpus gets in addition, not what any corpus is limited to.
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


def literal_pattern(phrase):
    """A literal phrase as a pattern: case-insensitive, any run of whitespace between words."""
    return re.compile(r"\s+".join(re.escape(word) for word in phrase.split()), re.I)


BUILT_IN_PATTERNS = [literal_pattern(phrase) for phrase in POINTER_PHRASES]


def declared_pointer_phrases(corpus):
    """The patterns one manifest corpus declares, and what is wrong with the declaration.

    `pointerPhrases` is a list. A string is a literal phrase; `{"regex": "..."}` is a regular
    expression. Both match case-insensitively. An empty list says the corpus makes no pointer
    the built-in list misses, and needs `pointerPhrasesReason` saying why; the reason is refused
    beside a non-empty list, where nothing would read it. Returns (patterns, problems, declared).
    """
    name = f"manifest {corpus.get('sourceId')}"
    if "pointerPhrases" not in corpus:
        if "pointerPhrasesReason" in corpus:
            return [], [f"  X  {name}: `pointerPhrasesReason` without `pointerPhrases`; the reason "
                        f"explains an empty list and there is no list"], False
        return [], [], False
    phrases, reason, patterns, problems = corpus["pointerPhrases"], corpus.get("pointerPhrasesReason"), [], []
    if not isinstance(phrases, list):
        return [], [f"  X  {name}: `pointerPhrases` is not a list"], True
    if not phrases and not (isinstance(reason, str) and reason.strip()):
        problems.append(f"  X  {name}: `pointerPhrases` is empty and `pointerPhrasesReason` does not say "
                        f"why; a corpus that points at nothing is a claim with a reason, never a default")
    if phrases and "pointerPhrasesReason" in corpus:
        problems.append(f"  X  {name}: `pointerPhrasesReason` beside a non-empty `pointerPhrases`; the "
                        f"reason explains an empty list, and nothing reads it here")
    for item in phrases:
        if isinstance(item, str) and item.strip():
            patterns.append(literal_pattern(item))
        elif isinstance(item, dict) and set(item) == {"regex"} and isinstance(item["regex"], str) \
                and item["regex"].strip():
            try:
                pattern = re.compile(item["regex"], re.I)
            except re.error as error:
                problems.append(f"  X  {name}: pointerPhrases regex {item['regex']!r} does not compile: {error}")
                continue
            if pattern.search(""):
                problems.append(f"  X  {name}: pointerPhrases regex {item['regex']!r} matches the empty "
                                f"string, so it would find a pointer everywhere")
                continue
            patterns.append(pattern)
        else:
            problems.append(f"  X  {name}: pointerPhrases holds {item!r}; an item is a literal phrase or "
                            f"{{\"regex\": \"...\"}}")
    return patterns, problems, True


def pointer_spans(text, patterns):
    """Where the pointers in `text` are, as (start, end), one span per pointer.

    Matches that overlap, or that only whitespace separates, are one pointer: "Except as provided
    in" contains "as provided in", and a corpus's "paragraph (d) of this section" follows it.
    Reporting them apart would demand two declarations for one pointer.
    """
    found = sorted(
        (m.start(), m.end())
        for p in patterns
        for m in p.finditer(text)
        if m.end() > m.start()
        # A corpus regex is a declaration, not permission to rename what the corpus printed.
        # If a match containing a section sign stops inside an alphanumeric token, it is a
        # prefix of a longer designation/word and is not a pointer at all (#323).
        and not ("§" in m.group(0) and m.end() < len(text) and text[m.end()].isalnum())
    )
    spans = []
    for start, end in found:
        if spans and (start <= spans[-1][1] or not text[spans[-1][1]:start].strip()):
            spans[-1][1] = max(spans[-1][1], end)
        else:
            spans.append([start, end])
    return [(start, end) for start, end in spans]


def pointers_in(evidence, patterns=None):
    """The pointers this evidence makes, as the words that make them, read with `patterns`
    (the built-in list when none are given)."""
    text = " ".join(str(evidence or "").split())
    return [text[start:end] for start, end in pointer_spans(text, BUILT_IN_PATTERNS if patterns is None else patterns)]


def reference_names(reference_id, manifest_reference):
    """The words a pointer to a non-admitted corpus would use to name it, as patterns.

    Two, both read from what the map and manifest already declare: the designation in the
    manifest reference's `citation` (`§ 171.8` gives `171.8`, which "49 CFR 171.8" contains),
    and the reference's `sourceId` read as words when every part of it is a word (`air-almanac`
    gives "air almanac"). A reference with neither -- a sourceId like `cfr-49-171` and no
    citation -- has no name this can recognise.
    """
    patterns = []
    citation = str((manifest_reference or {}).get("citation") or "").replace("§", "").strip()
    if citation:
        patterns.append(re.compile(r"(?<![\w.])" + re.escape(citation) + r"(?![\w]|\.\d)", re.I))
    words = str(reference_id or "").split("-")
    if words and all(word.isalpha() for word in words):
        patterns.append(re.compile(r"\b" + r"\s+".join(map(re.escape, words)) + r"\b", re.I))
    return patterns


def defined_elsewhere_names(ctx, entry):
    """The patterns naming this entry's `definedElsewhere` reference, or none."""
    reference_id = block(entry, "definedElsewhere").get("reference")
    if not reference_id:
        return []
    source = corpora_of(ctx.get("manifest")).get(block(entry, "locator").get("sourceId")) or {}
    declared = next((r for r in source.get("references") or []
                     if isinstance(r, dict) and r.get("sourceId") == reference_id), None)
    return reference_names(reference_id, declared)


def duplicates_defined_elsewhere(ctx, entry, item):
    """The `definedElsewhere` reference a crossReferences item names again, or None (#62).

    `definedElsewhere` is the answer to a pointer into a corpus that was not admitted: it names
    the manifest reference, and the correspondence table gives the entry its runtime reason. A
    crossReferences item for the same pointer answers it a second time, as prose.
    """
    cites = " ".join(str(item.get("cites") or "").split())
    if any(pattern.search(cites) for pattern in defined_elsewhere_names(ctx, entry)):
        return block(entry, "definedElsewhere").get("reference")
    return None


def occurrences(text, needle):
    """Every (start, end) at which `needle` occurs in `text`, overlapping ones included."""
    found, at = [], text.find(needle)
    while needle and at >= 0:
        found.append((at, at + len(needle)))
        at = text.find(needle, at + 1)
    return found


def check_cross_references(ctx):
    """A reference the corpus makes is an entry, or a recorded reason there is none (0009).

    § 107.29(a) opens *"Except as provided in paragraph (d) of this section"* and (d) has no
    entry in either Part 107 map. Nothing detected that, because a cross-reference was a
    sentence in an `evidence` span and no field made a mapper answer it.

    Each pointer the evidence makes must lie inside a `crossReferences` item's `cites`, and that
    `cites` must appear verbatim in the same evidence -- so the declaration is anchored to the
    corpus's words rather than asserted beside them -- and resolve exactly one way: `resolvedBy`,
    an entry id in this map, or `unmapped`, a reason there is none.

    What counts as a pointer is per corpus (0026, #116). The built-in `POINTER_PHRASES` were
    written from CFR and Hoyle wording, and detected none of the SRD's 22 declared pointers,
    which passed because nothing obliged them. So each corpus in the manifest declares the
    phrases its own text points with, `pointerPhrases`, read in addition to the built-in list;
    the check reports how many pointers it detected in each corpus's quoted evidence; and it
    **fails a corpus that declares no `pointerPhrases` and on which the built-in list detects
    nothing**, since a silent zero is the defect. A corpus that truly points at nothing declares
    `pointerPhrases: []` with `pointerPhrasesReason`. Without a manifest only the built-in list
    is read, and the zero is not judged.

    Two limits, stated where the claim is. Detection is still a list, now a corpus's own: a
    pointer in words nobody declared passes. And `unmapped` is prose, which 0003 and 0004 both
    rejected as a carrier: what is checked is that a mapper was made to write one, not that
    what they wrote is true.

    A pointer into a corpus that was not admitted is answered by `definedElsewhere`, and an item
    naming that same reference is refused (#62): the blind Part 107 map declared "49 CFR 171.8"
    and "as defined in the Air Almanac" in both places. A detected pointer whose words name the
    entry's `definedElsewhere` reference is answered by it. The reference is recognised by the
    words `reference_names` reads from the manifest and the sourceId, and by no others.
    """
    manifest_corpora = corpora_of(ctx.get("manifest"))
    by_id, bad = index(ctx["map"]), []
    patterns_of, declared_phrases, counts = {}, {}, {}
    for source_id, corpus in manifest_corpora.items():
        patterns, problems, declared = declared_pointer_phrases(corpus)
        patterns_of[source_id] = BUILT_IN_PATTERNS + patterns
        declared_phrases[source_id] = (declared, len(patterns))
        bad.extend(problems)

    declared_items = anchored_to_pointer = 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        evidence = " ".join(str(entry.get("evidence") or "").split())
        source_id = block(entry, "locator").get("sourceId")
        spans = []
        if evidence:
            spans = pointer_spans(evidence, patterns_of.get(source_id, BUILT_IN_PATTERNS))
            tally = counts.setdefault(source_id, [0, 0])
            tally[0] += 1
            tally[1] += len(spans)
        references = entry.get("crossReferences")
        if references is None:
            references = []
        elif not isinstance(references, list):
            bad.append(f"  X  {name}: `crossReferences` is not a list")
            references = []
        claimed = []
        for item in references:
            declared_items += 1
            if not isinstance(item, dict):
                bad.append(f"  X  {name}: crossReferences holds {item!r}, which is not an object")
                continue
            cites = item.get("cites")
            if not isinstance(cites, str) or not cites.strip():
                bad.append(f"  X  {name}: a crossReferences item has no `cites` naming the "
                           f"corpus's own words")
                continue
            cites = " ".join(cites.split())
            if cites not in evidence:
                bad.append(f"  X  {name}: crossReferences cites {cites!r}, which does not appear "
                           f"in this entry's `evidence`; a reference is anchored to the passage "
                           f"that makes it")
                continue
            places = occurrences(evidence, cites)
            claimed.extend(places)
            if any(s <= start and end <= e for start, end in spans for s, e in places):
                anchored_to_pointer += 1
            duplicated = duplicates_defined_elsewhere(ctx, entry, item)
            if duplicated:
                bad.append(f"  X  {name}: crossReferences {cites!r} names {duplicated!r}, which "
                           f"this entry's `definedElsewhere` already answers; a pointer to a "
                           f"corpus that was not admitted is answered there, once (#62)")
                continue
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
        elsewhere = [(m.start(), m.end()) for p in defined_elsewhere_names(ctx, entry) for m in p.finditer(evidence)]
        for start, end in spans:
            if any(s <= start and end <= e for s, e in claimed):
                continue
            if any(s < end and start < e for s, e in elsewhere):
                continue
            bad.append(f"  X  {name}: `evidence` says {evidence[start:end]!r} and no `crossReferences` "
                       f"item claims it; a reference is an entry or a recorded reason there is none")

    reports, pointers = [], 0
    for source_id in sorted(counts, key=str):
        quoted, found = counts[source_id]
        pointers += found
        corpus = manifest_corpora.get(source_id)
        declared, phrase_count = declared_phrases.get(source_id, (False, 0))
        phrases = (f"built-in and {phrase_count} declared phrase{'' if phrase_count == 1 else 's'}"
                   if declared else "built-in phrases only")
        reports.append(f"{source_id}: {found} pointer{'' if found == 1 else 's'} in {quoted} quoted "
                       f"span{'' if quoted == 1 else 's'} ({phrases})")
        if corpus is not None and not declared and not found:
            bad.append(f"  X  manifest {source_id}: the built-in pointer phrases detect no pointer in the "
                       f"{quoted} span{'' if quoted == 1 else 's'} this map quotes, and the corpus declares "
                       f"no `pointerPhrases`. A silent zero is how 22 SRD cross-references went unchecked "
                       f"(#116): declare the phrases this corpus points with, or `pointerPhrases: []` with "
                       f"`pointerPhrasesReason` (0026)")
    summary = (f"{'; '.join(reports) or 'no quoted evidence'}. {declared_items} declared, "
               f"{anchored_to_pointer} of them on a detected pointer: each is anchored in the passage "
               f"that makes it and names an entry or a reason there is none")
    if not pointers and not declared_items and not bad:
        return skip("no entry's evidence makes a pointer this check knows and none declares a "
                    "crossReferences item, so the obligation is vacuous over this map"
                    + (f" ({'; '.join(reports)})" if reports else ""),
                    had_subject=False)
    return verdict(bad, summary, "a cross-reference the corpus makes is unanswered, or a corpus's "
                                 "pointer phrases are missing or malformed")
