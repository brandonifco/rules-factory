"""The mapping protocol: how one corpus communicates rules.

docs/method.md phase 2 says *walk the corpus*. Different corpora require different walks, and
the method had no way to say so, so each trial decided by hand what to look at and nothing
recorded what it decided. The cost is measured in
[#208](https://github.com/brandonifco/rules-factory/issues/208): the cross-reference detector
reads a phrase list, and against the SRD's conditions -- which point by naming a defined term --
it found 0 pointers in passages holding 51 references, leaving 102 of 107 declarations obliged
by nothing. The phrase list was not a gap in a list; it was the wrong interrogation mechanism
for that corpus, and nothing could say which was right.

So the generic mapper knows how mapping works, and a protocol says how *this* corpus
communicates rules: the units it states them in, the mechanisms it points with, the sweeps a
mapping of it owes, and how far the adapter reaches into each modality. It is a JSON document
beside the map: `mapping-protocol.json` for a map citing one corpus, and
`mapping-protocol-<sourceId>.json` once it cites several (0039, 0040). **One protocol is about
one corpus**, because two corpora that state rules differently cannot share one account of how
they are read, and a protocol stretched over both would read as coverage of the one it is not
about.

Every vocabulary below is closed, for the reason every vocabulary in the map is closed: a value
nothing holds to a set is a value that means whatever the last writer thought. A protocol that
names a mechanism no detector owns is refused rather than quietly skipped, because a declared
interrogation nobody performs is worse than none -- it reads as coverage.
"""
import json
import os

from mapcontract.entry import (block, canonical_vocabulary, defined_vocabulary,
                               entries_of, index)

PROTOCOL_VERSIONS = (1,)
PROTOCOL_FILENAME = "mapping-protocol.json"
PROTOCOL_FIELDS = ("protocolVersion", "corpus", "units", "pointerMechanisms", "requiredSweeps",
                   "adapterReach")
# Optional, because a corpus on which every sweep's built-in cues fire declares neither. They
# take the shape `pointerPhrases` takes (0026): `sweepCues` maps a sweep to the corpus's own cues,
# read *in addition to* the built-in list, and `sweepCuesReason` says why a sweep this corpus
# requires is expected to find nothing -- the one thing that distinguishes wrong cues from
# nothing to say. A reason beside a sweep that fired is refused, as 0026 refuses one beside a
# non-empty phrase list.
OPTIONAL_FIELDS = ("sweepCues", "sweepCuesReason")

# The shapes a corpus states a rule in. A unit is what a mapper reads one at a time: the walk is
# bounded, and this says by what.
# `table-row` is a unit of its own beside `table` (0035): a corpus that states one rule per row
# of a 3,687-row table states them in rows, and a unit the inventory counts as reached when one
# quote lands in it would report such a table read on a single citation.
UNITS = ("section", "paragraph", "sentence", "list-item", "table", "table-row",
         "glossary-definition", "worked-example", "heading", "figure")

# How a corpus points at a meaning it gives elsewhere (0026). Each is either detected here or
# detected somewhere named: a mechanism in neither map is refused.
#
# `phrase` and `section-designation` are detected outside this subsystem and are declared here
# anyway, so that a protocol is the whole account of how a corpus points rather than the part
# this package happens to implement.
#: `coded-pointer` is the mechanism a token gets from **where it is printed**, not from what it
#: spells (0041). 49 CFR § 172.101 column 7 holds `IB2, T4, TP1` and nothing else; each is a
#: pointer into § 172.102, with no pointer phrase and no defined term named anywhere near it.
#: Measured on trial 10's seven rows, `defined-term-use` detects all 33 of them and misses none --
#: and reads the numeric code `148` as a pointer twice more where it is not one: in column 14's
#: vessel stowage provisions, which are § 176.84's, and in "46 CFR parts ... 98, 148, 151 ...",
#: where it is a part number (#307). Firing is not the same as being right, and no lexical
#: mechanism can be, because column membership is not text.
DETECTED_HERE = ("defined-term-use", "coded-pointer")
DETECTED_ELSEWHERE = {
    "phrase": "check-map.py --only cross-references, over the corpus's `pointerPhrases` (0026)",
    "section-designation": "the corpus's own locator checker, which resolves the designation",
}
POINTER_MECHANISMS = DETECTED_HERE + tuple(DETECTED_ELSEWHERE)

# The completeness challenge of docs/method.md, as a closed set of named sweeps. Each is code the
# mapper runs over the units the walk left unaccounted (`mapper sweeps`, #250). A name this
# checker holds to the vocabulary but the registry does not implement is reported by name and
# exits NOT VERIFIED, never skipped: a declared interrogation nobody performs reads as coverage.
SWEEPS = ("definitions", "vocabulary", "applicability", "exceptions", "permissions",
          "prohibitions", "undefined-terms", "examples", "tables", "cross-references",
          "extent-coverage")

# How far the adapter reaches into a modality (0004, 0024). `readable` means the extraction
# carries it; `rendered-page-required` means an entry that depends on it owes a rendered reading;
# `unsupported` means the mapper cannot inspect it at all and an entry that needs it is
# `beyondAdapter`.
MODALITIES = ("text", "tables", "columns", "formatting", "illustrations")
REACH = ("readable", "rendered-page-required", "unsupported")


class Refused(Exception):
    """The protocol is not one this mapper can act on."""


def path_beside(map_path):
    """Where a single-corpus map's protocol lives: beside it, named for what it is."""
    return os.path.join(os.path.dirname(os.path.abspath(map_path)) or ".", PROTOCOL_FILENAME)


def per_corpus_filename(source_id):
    return f"mapping-protocol-{source_id}.json"


def cited_corpora(document):
    """Every corpus the map reads: its envelope's, and every entry locator's (0039)."""
    cited = {document.get("corpus")} if isinstance(document, dict) else set()
    for item in document.get("entries") or []:
        locator = item.get("locator") if isinstance(item, dict) else None
        if isinstance(locator, dict) and locator.get("sourceId"):
            cited.add(locator["sourceId"])
    return {c for c in cited if isinstance(c, str)}


def paths_beside(map_path, document):
    """`{sourceId: path}`, one protocol per corpus the map cites (0040).

    A protocol is about **one** corpus -- that is the whole concept, and it is why 49 CFR
    § 172.101, which states rules in table rows and points with bare codes, cannot share one with
    § 172.102, which states them as prose and points with section designations. A map may cite
    several corpora (0039), so it may have several protocols, and each is true of its own.

    `mapping-protocol.json` still serves a map citing one corpus, which is every map committed
    before trial 10 and none of whose files move. Beyond one, each is
    `mapping-protocol-<sourceId>.json`.

    Raises Refused when a cited corpus has no protocol, or when a per-corpus protocol sits beside
    the map for a corpus the map does not cite: a leftover claiming to govern a corpus nobody
    reads is the state the file exists to make impossible.
    """
    directory = os.path.dirname(os.path.abspath(map_path)) or "."
    cited = cited_corpora(document)
    if not cited:
        raise Refused(f"{map_path} cites no corpus, so no protocol could be about it")
    found, missing = {}, []
    for source_id in sorted(cited):
        per_corpus = os.path.join(directory, per_corpus_filename(source_id))
        if os.path.exists(per_corpus):
            found[source_id] = per_corpus
            continue
        plain = os.path.join(directory, PROTOCOL_FILENAME)
        if len(cited) == 1 and os.path.exists(plain):
            found[source_id] = plain
            continue
        missing.append(source_id)
    stray = sorted(name for name in os.listdir(directory)
                   if name.startswith("mapping-protocol-") and name.endswith(".json")
                   and name not in {per_corpus_filename(c) for c in cited})
    if stray:
        raise Refused(f"{', '.join(stray)} beside {os.path.basename(map_path)} name(s) a corpus "
                      f"this map does not cite; a protocol is about a corpus that was read")
    if missing:
        raise Refused(f"no protocol beside {os.path.basename(map_path)} for "
                      f"{', '.join(missing)}: expected "
                      + ", ".join(per_corpus_filename(c) for c in missing)
                      + (f" (or {PROTOCOL_FILENAME})" if len(cited) == 1 else "")
                      + ". A corpus with no protocol is one nothing says how it was read (0032)")
    return found


def load(path):
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"cannot read {path}: {error}")
    if not isinstance(document, dict):
        raise Refused(f"{path} is not a JSON object")
    return document


def check(protocol, document, manifest=None):
    """Every problem with the protocol, as lines. Empty means it is one the mapper can act on.

    `document` is the map it governs, and `manifest` the corpus manifest when there is one:
    a protocol is about a corpus, so it is checked against the corpus's own declarations rather
    than read as a standalone wish.
    """
    problems = []
    version = protocol.get("protocolVersion")
    if version not in PROTOCOL_VERSIONS:
        problems.append(f"protocolVersion {version!r} is not one this mapper reads "
                        f"({', '.join(str(v) for v in PROTOCOL_VERSIONS)})")
    for field in PROTOCOL_FIELDS:
        if field not in protocol:
            problems.append(f"`{field}` is missing, and every protocol field is required")
    for extra in sorted(set(protocol) - set(PROTOCOL_FIELDS) - set(OPTIONAL_FIELDS)):
        problems.append(f"`{extra}` is not a protocol field; the five are "
                        + ", ".join(PROTOCOL_FIELDS[1:]) + ", and the optional two are "
                        + ", ".join(OPTIONAL_FIELDS))

    corpus = protocol.get("corpus")
    if manifest is not None:
        declared = [c.get("sourceId") for c in manifest.get("corpora") or [] if isinstance(c, dict)]
        if corpus not in declared:
            problems.append(f"corpus {corpus!r} is not a sourceId the manifest declares "
                            f"({', '.join(repr(d) for d in declared) or 'none'})")
    # Declared is not read. A protocol about a corpus no entry cites describes a walk this map
    # never took, and would report as coverage of it (0040).
    cited = cited_corpora(document)
    if corpus is not None and cited and corpus not in cited:
        problems.append(f"corpus {corpus!r} is not cited by this map "
                        f"({', '.join(sorted(cited))}); a protocol says how a corpus that was "
                        f"read was read")

    units = protocol.get("units")
    if not isinstance(units, list) or not units:
        problems.append("`units` is empty; a protocol that names no unit says nothing about how "
                        "the corpus is read")
    else:
        for unit in units:
            if unit not in UNITS:
                problems.append(f"unit {unit!r} is outside the closed set: " + ", ".join(UNITS))

    problems += _check_mechanisms(protocol, document)

    sweeps = protocol.get("requiredSweeps")
    if not isinstance(sweeps, list) or not sweeps:
        problems.append("`requiredSweeps` is empty; a mapping that owes no completeness challenge "
                        "is one nothing holds to its extent")
    else:
        for sweep in sweeps:
            if sweep not in SWEEPS:
                problems.append(f"sweep {sweep!r} is outside the closed set: " + ", ".join(SWEEPS))
    problems += _check_sweep_cues(protocol, sweeps if isinstance(sweeps, list) else [])

    reach = protocol.get("adapterReach")
    if not isinstance(reach, dict) or not reach:
        problems.append("`adapterReach` is empty; how far the adapter reads is a fact about the "
                        "mapping, not a detail (0004)")
    else:
        for modality, verdict in sorted(reach.items()):
            if modality not in MODALITIES:
                problems.append(f"modality {modality!r} is outside the closed set: "
                                + ", ".join(MODALITIES))
            if verdict not in REACH:
                problems.append(f"adapterReach[{modality!r}] is {verdict!r}, outside: "
                                + ", ".join(REACH))
    return problems


def _check_sweep_cues(protocol, required):
    """`sweepCues` and `sweepCuesReason` are about sweeps this protocol requires, and about cues
    that compile.

    A cue for a sweep the protocol does not require is read by nothing, which is the shape #60
    refused for `pointerPhrasesReason`: a declaration nobody reads is worse than none, because it
    looks like it is doing work.
    """
    # Imported here rather than at the top: `sweeps` reads `Refused` and `SWEEPS` from this
    # module, and the cue grammar belongs beside the sweeps that use it, not in the protocol.
    from mapper.sweeps import compile_cue

    problems = []
    for field in OPTIONAL_FIELDS:
        declared = protocol.get(field)
        if declared is None:
            continue
        if not isinstance(declared, dict) or not declared:
            problems.append(f"`{field}` is {declared!r}; it maps a sweep name to "
                            + ("its cues" if field == "sweepCues" else "why it finds nothing")
                            + ", and an empty one says nothing")
            continue
        for name in sorted(declared):
            where = f"{field}[{name!r}]"
            if name not in SWEEPS:
                problems.append(f"{where}: {name!r} is outside the closed set of sweeps: "
                                + ", ".join(SWEEPS))
                continue
            if name not in required:
                problems.append(f"{where}: this protocol does not require the {name!r} sweep, so "
                                f"nothing reads this")
                continue
            value = declared[name]
            if field == "sweepCuesReason":
                if not isinstance(value, str) or not value.strip():
                    problems.append(f"{where}: a reason is why this corpus states nothing of that "
                                    f"kind, in words; {value!r} is not one")
                continue
            if not isinstance(value, list) or not value:
                problems.append(f"{where}: cues are a non-empty list of phrases or "
                                f"{{'regex': ...}} objects (0026); {value!r} is not one")
                continue
            for position, item in enumerate(value):
                try:
                    compile_cue(item, f"{where}[{position}]")
                except Refused as error:
                    problems.append(str(error))
    return problems


def _check_mechanisms(protocol, document):
    problems = []
    mechanisms = protocol.get("pointerMechanisms")
    if not isinstance(mechanisms, list) or not mechanisms:
        problems.append("`pointerMechanisms` is empty; a corpus that points in no way at all is a "
                        "claim, and 0026 already refuses a silent zero")
        return problems
    for position, declared in enumerate(mechanisms):
        where = f"pointerMechanisms[{position}]"
        if not isinstance(declared, dict):
            problems.append(f"{where} is not an object")
            continue
        name = declared.get("mechanism")
        if name not in POINTER_MECHANISMS:
            problems.append(f"{where}: mechanism {name!r} is outside the closed set: "
                            + ", ".join(POINTER_MECHANISMS))
            continue
        if name == "defined-term-use":
            problems += _check_vocabulary(where, declared, document)
        elif "vocabularyFrom" in declared:
            problems.append(f"{where}: `vocabularyFrom` names the one entry that prints a "
                            f"corpus's terms, which is defined-term-use's vocabulary; "
                            f"{name!r} does not read one"
                            + (". coded-pointer's vocabulary is distributed over the entries "
                               "that define its codes, and it names that vocabulary in "
                               "`vocabulary` (0045)" if name == "coded-pointer" else ""))
        if name == "coded-pointer":
            problems += _check_coded_pointer(where, declared)
            problems += _check_defined_vocabulary(where, declared, document)
        else:
            if "column" in declared:
                problems.append(f"{where}: `column` belongs to coded-pointer, whose pointers are "
                                f"made by the column they sit in; {name!r} reads no column")
            if "vocabulary" in declared:
                problems.append(f"{where}: `vocabulary` names a vocabulary the map's entries "
                                f"declare with `defines` (0045), which is coded-pointer's; "
                                f"{name!r} reads no such vocabulary")
    return problems


def _check_coded_pointer(where, declared):
    """`coded-pointer` says which column bears the pointers, because that is what makes them.

    A mechanism parameter, exactly as `vocabularyFrom` is for `defined-term-use`: the protocol's
    shape is a list of mechanism objects each carrying its own, and no protocol field is added
    (0041). Without it the mechanism would be a regex over prose, which is the thing the
    measurement refused.
    """
    column = declared.get("column")
    if isinstance(column, bool) or not isinstance(column, (str, int)) or not str(column).strip():
        return [f"{where}: coded-pointer names no `column`; a pointer made by the column it sits "
                f"in has to say which column, or it is a scan of the corpus's words"]
    return []


def _check_defined_vocabulary(where, declared, document):
    """`coded-pointer` names a vocabulary, and the entries that define its terms make it (0045).

    `defined-term-use` reads its vocabulary out of **one** entry, because the corpus that forced
    it prints one: the SRD's glossary list names all fifteen conditions in a sentence. 49 CFR
    § 172.101 prints no such passage -- its codes are one per table row -- and the nearest
    candidate, § 172.102(c), says only *"The following tables list … the special provisions
    referred to in column 7"*. An entry indexing twenty codes it does not print would be a
    registry disguised as a passage, which 0026's anchoring rule exists to refuse (#314).

    So the vocabulary is a **name**, and it is distributed: every entry declaring
    `defines: [{"vocabulary": name, "term": code}]` states one of its terms, anchored in its own
    evidence. A name no entry defines is refused rather than read as an empty vocabulary, for the
    reason a declared sweep nobody runs is refused: it reads as coverage.
    """
    name = declared.get("vocabulary")
    if not canonical_vocabulary(name):
        return [f"{where}: coded-pointer names no `vocabulary`; a mechanism that reads a cell's "
                f"codes as pointers must say which vocabulary they are codes of"]
    terms = defined_vocabulary(document, name)
    if not terms:
        return [f"{where}: no entry in this map establishes vocabulary {name!r}; a "
                f"vocabulary is what the entries that define its terms add up to (0045), and one "
                f"nothing defines would report every code in the column as undeclared"]
    return []


def _check_vocabulary(where, declared, document):
    """`defined-term-use` points by naming a term, so it has to say where the terms are.

    They are read out of the map, not out of a list in the protocol: the corpus already states
    its vocabulary somewhere, that statement is an entry, and a second copy in the protocol would
    be a second definition to keep in step.
    """
    source = declared.get("vocabularyFrom")
    if not isinstance(source, str) or not source:
        return [f"{where}: defined-term-use names no `vocabularyFrom`; a mechanism that points by "
                f"naming a term must say which entry states the terms"]
    entry = index(document).get(source)
    if entry is None:
        return [f"{where}: vocabularyFrom {source!r} is not an entry in this map"]
    terms = vocabulary_of(entry)
    if not terms:
        return [f"{where}: entry {source!r} states no vocabulary -- defined-term-use reads its "
                f"`crossReferences` as term -> defining entries, and it has none"]
    known = index(document)
    problems = [f"{where}: term {term!r} in {source!r} resolves to {target!r}, which is not an "
                f"entry"
                for term in sorted(terms) for target in terms[term] if target not in known]
    return problems + _repeated_targets(where, source, entry)


def _repeated_targets(where, source, entry):
    """A `crossReferences` pair the entry declares twice, reported rather than collapsed (0044).

    A term may name several entries, so two declarations of one term are ordinary. Two
    declarations of the *same* term and the *same* entry are not: they add nothing, and the
    likeliest reason one is there is that a second target was meant. Silence would make the two
    cases indistinguishable, which is the failure #311 is about, one step along.
    """
    seen, repeated = set(), []
    for reference in entry.get("crossReferences") or []:
        if not isinstance(reference, dict):
            continue
        pair = (reference.get("cites"), reference.get("resolvedBy"))
        if not all(isinstance(half, str) for half in pair):
            continue
        if pair in seen and pair not in repeated:
            repeated.append(pair)
        seen.add(pair)
    return [f"{where}: {source!r} declares term {cites!r} -> {target!r} more than once; a term "
            f"may name several entries, and naming one of them twice says nothing the first "
            f"declaration does not"
            for cites, target in repeated]


def vocabulary_of(entry):
    """The terms an entry states, as term -> **the ids of every entry that defines it** (0044).

    A vocabulary entry is one whose `crossReferences` are term-anchored (0026): each names the
    term as the corpus prints it and the entry that gives its meaning. That is already how a
    list-of-defined-things entry is written, so the vocabulary needs no new field.

    **One printed code can name more than one rule**, and this returns all of them in the order
    the entry declares them. 49 CFR § 172.102(c)(4) says so outright -- *"Large Packagings are
    authorized for the Packing Group III entries of specific proper shipping names when either
    special provision IB3 or IB8 is assigned to that entry"* -- so `IB3` in column 7 of the
    § 172.101 table authorises IBCs unconditionally and Large Packagings for PG III only, two
    rules the corpus states in two of its tables. Keeping a `dict` of one target each discarded
    the first silently, and every check passed: both targets were real entries, so nothing could
    see that a declaration had been dropped (#311).

    A target declared twice for one term is **not** collapsed here either -- it is returned once,
    and `_check_vocabulary` reports the repetition, because a second identical declaration is
    either a mistake or a second target someone meant to write.
    """
    terms = {}
    for reference in entry.get("crossReferences") or []:
        if isinstance(reference, dict):
            cites, resolved = reference.get("cites"), reference.get("resolvedBy")
            if isinstance(cites, str) and isinstance(resolved, str):
                if resolved not in terms.setdefault(cites, []):
                    terms[cites].append(resolved)
    return terms


def mechanisms_of(protocol, name=None):
    """The declared mechanisms, optionally just the ones with this name."""
    declared = protocol.get("pointerMechanisms")
    if not isinstance(declared, list):
        return []
    return [m for m in declared if isinstance(m, dict)
            and (name is None or m.get("mechanism") == name)]


def entry_count(document):
    """How many entries the protocol's map holds -- so a run can say what it examined."""
    return len(entries_of(document))


def citation_of(entry):
    """An entry's citation, which is how a passage is identified (0030)."""
    return block(entry, "locator").get("citation")
