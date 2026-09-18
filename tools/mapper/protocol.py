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
mapping of it owes, and how far the adapter reaches into each modality. It is a JSON document,
`mapping-protocol.json`, beside the map.

Every vocabulary below is closed, for the reason every vocabulary in the map is closed: a value
nothing holds to a set is a value that means whatever the last writer thought. A protocol that
names a mechanism no detector owns is refused rather than quietly skipped, because a declared
interrogation nobody performs is worse than none -- it reads as coverage.
"""
import json
import os

from mapcontract.entry import block, entries_of, index

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
DETECTED_HERE = ("defined-term-use",)
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
    """Where a map's protocol lives: beside it, named for what it is."""
    return os.path.join(os.path.dirname(os.path.abspath(map_path)) or ".", PROTOCOL_FILENAME)


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
            problems.append(f"{where}: `vocabularyFrom` belongs to defined-term-use, and "
                            f"{name!r} does not read a vocabulary")
    return problems


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
                f"`crossReferences` as term -> defining entry, and it has none"]
    unresolved = sorted(t for t, resolved in terms.items() if resolved not in index(document))
    return [f"{where}: term {t!r} in {source!r} resolves to {terms[t]!r}, which is not an entry"
            for t in unresolved]


def vocabulary_of(entry):
    """The terms an entry states, as term -> the id of the entry that defines it.

    A vocabulary entry is one whose `crossReferences` are term-anchored (0026): each names the
    term as the corpus prints it and the entry that gives its meaning. That is already how a
    list-of-defined-things entry is written, so the vocabulary needs no new field.
    """
    terms = {}
    for reference in entry.get("crossReferences") or []:
        if isinstance(reference, dict):
            cites, resolved = reference.get("cites"), reference.get("resolvedBy")
            if isinstance(cites, str) and isinstance(resolved, str):
                terms[cites] = resolved
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
