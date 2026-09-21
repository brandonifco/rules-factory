#!/usr/bin/env python3
"""Attack the validator with a damaged map, and report what it noticed.

Every check in `check-map.py` has been watched failing on a unit fixture it was written
beside. That proves each check fires; it does not say what fraction of a *real* error
reaches the gate. Nobody had taken a committed, passing map, damaged it deliberately, and
counted the misses, so the validator's miss rate was unknown (#259). The equivalent number
exists for the method -- 0014 measured the mechanical checks at 1 of 15 injected
comprehension errors -- and for the factory (`test_map_overlay_mutation.py`). This supplies
it for the validator.

One run is: copy a committed map, apply one named mutation, run every detector the
validator has for that corpus, and compare each named check's verdict against the same
check's verdict on an unmutated control. A check that was already red proves nothing and is
excluded by construction rather than by judgement.

    control   the committed map, re-serialised the way a mutation is, and nothing else changed
    mutated   the same bytes with one mutation applied

    detected  some check that said `ok` on the control says `fail` or NOT VERIFIED here
    missed    every check gives the verdict it gave on the control

**Where it lives, and why not in the package.** `tools/build-check-map.py` joins
`tools/mapvalidator/` into the single `check-map.py` that every map package ships (0015), so
a module added there travels inside every published map. A harness that damages maps is the
validator's own instrument, not part of the artefact a consumer receives, so it sits beside
`check-locators.py` and `pack-map.py` -- tools of the validator subsystem that live outside
the shipped file. It imports nothing from this repository at all, which is the strongest
statement of the boundary available to it: it drives the built `check-map.py` as a
subprocess, exactly as `validate.sh` does, so what it measures is the shipped command rather
than the modules it was built from.

**What is deliberately not a detector.** `tools/check-map-review.py` holds a map's exact
bytes to a review of them (0017), so it goes red on *any* edit, including re-serialisation.
Counting it would report 100% detection by a check that has not read a word of the map --
the same trap the injection trial's manifest pin was (examples/injection-trial/README.md).
It is excluded, and named here so the exclusion is a decision rather than an omission.

**What a miss here does and does not mean.** A missed mutation is not automatically a bug.
Some of these are provably outside a structural checker's reach, which is *why* the blind
second mapping exists (0014). What this tool supplies is the denominator: a miss that is
dispositioned -- as an issue, or as a measured line in the validator's statement of its
limits -- is the point, and an undocumented one is the defect.

**Nothing is ever mutated in place.** The mutated map is written into a temporary directory
that is removed on the way out; the manifest, the corpus and the repository are read from
the checkout and never written.

Usage: mutate-map.py [--subject NAME] [--only MUTATION[,...]] [--list]
                     [--json PATH] [--markdown PATH] [--repo-root PATH]
Exit 0 when every run completed and its verdicts were read; 1 when a mutation could not be
applied or a detector could not be scored -- a mutation that silently did nothing would be
counted as an undetected error, which is the worst failure this tool has; 2 on a usage
error.
"""
import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


class NotApplicable(Exception):
    """This corpus has nothing for this mutation to damage. Recorded, never scored."""


# --- the subjects ----------------------------------------------------------------------
#
# Two structurally different genres, as #259 requires, and five maps so that every mutation
# has somewhere to land: a regulation's map carries `enabledBy` and no `assertedBy`, a
# rulebook's the reverse, and only one protocol in the repository declares a
# `defined-term-use` vocabulary. `genre` and `grammar` are what the results table groups by.

SUBJECTS = [
    {
        "name": "hoyle-backgammon",
        "genre": "rulebook",
        "grammar": "page-marker (Gutenberg plain text)",
        "dir": "examples/hoyle-backgammon",
        "locators": ["tools/check-locators.py", "{map}", "examples/hoyle-backgammon/hoyle.txt"],
        "locator_format": "named",
    },
    {
        "name": "faa-part-107",
        "genre": "regulation",
        "grammar": "section-designation (eCFR XML)",
        "dir": "examples/faa-part-107",
        "locators": ["examples/faa-part-107/check-locators-section.py", "{map}",
                     "examples/faa-part-107/part107.xml"],
        "locator_format": "section",
    },
    {
        "name": "tax-121-principal-residence",
        "genre": "regulation",
        "grammar": "section-designation (eCFR XML)",
        "dir": "examples/tax-121-principal-residence",
        "locators": ["examples/faa-part-107/check-locators-section.py", "{map}",
                     "examples/tax-121-principal-residence/section-1.121-1.xml"],
        "locator_format": "section",
    },
    {
        "name": "srd-52-combat",
        "genre": "rulebook",
        "grammar": "page-marker (PDF-extracted text)",
        "dir": "examples/srd-52-combat",
        "locators": ["examples/srd-52-combat/check-locators-pdf-text.py", "{map}",
                     "examples/srd-52-combat/srd-5.2.1.txt"],
        "locator_format": "named",
    },
    {
        "name": "srd-52-conditions",
        "genre": "rulebook",
        "grammar": "page-marker (PDF-extracted text)",
        "dir": "examples/srd-52-conditions",
        "locators": ["examples/srd-52-combat/check-locators-pdf-text.py", "{map}",
                     "examples/srd-52-combat/srd-5.2.1.txt"],
        "locator_format": "named",
    },
]


# --- reading a map ----------------------------------------------------------------------

CITING_LIST_FIELDS = ("dependsOn", "enabledBy", "suspendedBy")


def entries(document):
    return document.get("entries", [])


def by_id(document, entry_id):
    for entry in entries(document):
        if entry.get("id") == entry_id:
            return entry
    raise NotApplicable(f"no entry {entry_id!r}")


def first(document, predicate, what):
    """The first entry in document order the predicate admits, or NotApplicable."""
    for entry in entries(document):
        if predicate(entry):
            return entry
    raise NotApplicable(f"no entry {what}")


def inbound(document, entry_id):
    """Every (entry, field) that names `entry_id`: the edges an omission would leave dangling."""
    found = []
    for entry in entries(document):
        for field in CITING_LIST_FIELDS:
            if entry_id in (entry.get(field) or []):
                found.append((entry, field))
        for item in entry.get("crossReferences") or []:
            if isinstance(item, dict) and item.get("resolvedBy") == entry_id:
                found.append((entry, "crossReferences"))
        if entry_id in (entry.get("derivedFrom") or []):
            found.append((entry, "derivedFrom"))
    return found


def unreferenced(document, entry):
    return not inbound(document, entry.get("id"))


def drop_entry(document, entry):
    document["entries"] = [e for e in entries(document) if e is not entry]


def drop_inbound(document, entry_id):
    """Remove every edge naming `entry_id`, so the omission leaves no dangling reference.

    A `derivedFrom` entry is removed outright rather than shortened: a fact derived from a rule
    nobody mapped would not have been written either, and a one-source derivation is refused by
    `derived` for a reason that has nothing to do with the omission being measured.
    """
    document["entries"] = [e for e in entries(document)
                           if entry_id not in (e.get("derivedFrom") or [])]
    for entry in entries(document):
        for field in CITING_LIST_FIELDS:
            if entry_id in (entry.get(field) or []):
                entry[field] = [v for v in entry[field] if v != entry_id]
        if entry.get("crossReferences"):
            for item in entry["crossReferences"]:
                if isinstance(item, dict) and item.get("resolvedBy") == entry_id:
                    item.pop("resolvedBy")
                    item["unmapped"] = ("The corpus points here and this map has no entry for "
                                        "what it points at.")


def page_of(citation):
    match = re.search(r"\bp\.\s*(\d+)", str(citation or ""))
    return int(match.group(1)) if match else None


def cited(entry):
    return (entry.get("locator") or {}).get("citation")


def quoted(entry):
    return isinstance(entry.get("evidence"), str) and len(entry["evidence"].split()) > 3


def in_scope(entry):
    return entry.get("scope") == "in" and "derivedFrom" not in entry


# --- the mutations ----------------------------------------------------------------------
#
# Each is the damage a mapper does by mistake, not damage chosen to suit a checker. Every one
# states why the mutated map is FALSE about the corpus -- a mutation whose result happens to
# be true is not a mutation, it is an edit -- and every one raises rather than returning
# quietly when its target is absent. A patch that changed nothing would be scored as an
# undetected error, which is the failure mode this whole tool exists to guard against, so
# `apply` compares the document before and after and refuses a no-op.


def m_drop_entry(document):
    entry = first(document, lambda e: in_scope(e) and quoted(e) and unreferenced(document, e),
                  "is in scope, quotes the corpus and is named by no other entry")
    drop_entry(document, entry)
    return f"dropped {entry['id']} ({cited(entry)}), which no other entry names"


def m_drop_enabled_by(document):
    entry = first(document, lambda e: e.get("enabledBy"), "carries an `enabledBy` edge")
    gone = entry["enabledBy"][0]
    entry["enabledBy"] = entry["enabledBy"][1:]
    return f"dropped {entry['id']}.enabledBy -> {gone}"


def m_drop_suspended_by(document):
    entry = first(document, lambda e: e.get("suspendedBy"), "carries a `suspendedBy` edge")
    gone = entry["suspendedBy"][0]
    entry["suspendedBy"] = entry["suspendedBy"][1:]
    return f"dropped {entry['id']}.suspendedBy -> {gone}"


def m_clear_to_ambiguous(document):
    """A false ambiguity, recorded the way a mapper who believed it would record it.

    Recording only `clarity: ambiguous` and no `ambiguity` block is refused by
    `required-fields`, which measures field coupling rather than the validator's reach into
    the corpus. The mutation therefore records the complete, plausible claim.
    """
    entry = first(document, lambda e: e.get("clarity") == "clear" and "ambiguity" not in e
                  and in_scope(e) and quoted(e), "is `clarity: clear` with no ambiguity block")
    entry["clarity"] = "ambiguous"
    entry["ambiguity"] = {
        "question": "The passage can be read as stating a requirement and as stating a "
                    "permission, and nothing in the corpus resolves between the two.",
        "fate": "unresolved",
        "unresolvedReason": "RequiresInterpretation",
    }
    return f"{entry['id']}: clear -> ambiguous, with a full and false `ambiguity` block"


def m_ambiguous_to_clear(document):
    """Premature collapse: the doubt the corpus supports is deleted and one reading asserted."""
    entry = first(document, lambda e: e.get("clarity") == "ambiguous"
                  and isinstance(e.get("ambiguity"), dict)
                  and "conflict" not in e["ambiguity"] and "bounds" not in e["ambiguity"],
                  "is `clarity: ambiguous` with a plain ambiguity block")
    entry["clarity"] = "clear"
    entry.pop("ambiguity")
    return f"{entry['id']}: ambiguous -> clear, and its recorded question deleted"


def m_assertion_to_operation(document):
    """A fact only a caller can supply, re-recorded as something the engine computes."""
    entry = first(document, lambda e: e.get("kind") == "assertion", "is `kind: assertion`")
    entry["kind"] = "operation"
    entry.pop("assertedBy", None)
    return f"{entry['id']}: assertion -> operation, and `assertedBy` removed with it"


def m_invent_depends_on(document):
    """An order the corpus does not impose, of the kind trial 4 found six times (#13)."""
    source = first(document, lambda e: isinstance(e.get("dependsOn"), list) and in_scope(e),
                   "carries a `dependsOn` list")
    reachable = _reaching(document, source["id"])
    for candidate in reversed(entries(document)):
        target = candidate.get("id")
        if not target or target == source["id"] or target in (source.get("dependsOn") or []):
            continue
        if source["id"] in _reaching(document, target) or target in reachable:
            continue
        source["dependsOn"] = list(source["dependsOn"]) + [target]
        return f"invented {source['id']}.dependsOn -> {target}, an order the corpus does not state"
    raise NotApplicable("every other entry would close a cycle")


def _reaching(document, entry_id, seen=None):
    """Every id reachable from `entry_id` through dependsOn, so an invented edge is acyclic."""
    seen = seen if seen is not None else set()
    try:
        entry = by_id(document, entry_id)
    except NotApplicable:
        return seen
    for target in entry.get("dependsOn") or []:
        if target not in seen:
            seen.add(target)
            _reaching(document, target, seen)
    return seen


def _evidence_swap(document, same_citation):
    """Give one entry another entry's verbatim quote, leaving its own locator untouched.

    Both quotes are committed evidence of the same corpus, so both are still verbatim of the
    extraction and the locator still resolves to a real passage. The entry is simply about a
    different sentence than the one it cites -- the shape of error that survived a mapping
    trial, a build and a review thirteen times in the backgammon map.
    """
    candidates = [e for e in entries(document) if in_scope(e) and quoted(e) and cited(e)]
    # The recipient records no cross-reference and no `definedElsewhere`. Both anchor a claim
    # in the words of *this* entry's evidence, so replacing the evidence would break an
    # anchoring the mutation is not about, and `cross-references` would go red without anything
    # having compared the entry to the corpus. Excluding them isolates the evidence swap. It is
    # also a finding in its own right, and the trial README records it: where the recipient does
    # carry a `crossReferences` item, `cites` no longer appears in the evidence and the swap is
    # caught -- by bookkeeping, not by reading.
    unanchored = [e for e in candidates
                  if not e.get("crossReferences") and not e.get("definedElsewhere")]
    for pool in (unanchored, candidates):
        for position, entry in enumerate(pool):
            for other in candidates:
                if other is entry or other["evidence"] == entry["evidence"]:
                    continue
                if (cited(other) == cited(entry)) != same_citation:
                    continue
                entry["evidence"] = other["evidence"]
                anchored = "" if entry in unanchored else \
                    " (the recipient anchors a cross-reference; see the trial README)"
                return (f"{entry['id']} ({cited(entry)}) now quotes {other['id']}"
                        f" ({cited(other)})'s passage{anchored}")
    raise NotApplicable("no two entries quote "
                        + ("the same citation" if same_citation else "different citations"))


def m_neighbour_evidence(document):
    return _evidence_swap(document, same_citation=False)


def m_same_passage_evidence(document):
    return _evidence_swap(document, same_citation=True)


def m_move_locator(document):
    """The citation moves one unit; the quote stays where it was."""
    unit = (document.get("extent") or {}).get("unit")
    if unit == "page":
        extent = document["extent"]
        entry = first(document, lambda e: in_scope(e) and quoted(e)
                      and page_of(cited(e)) is not None
                      and page_of(cited(e)) + 1 <= extent.get("to", 0),
                      "cites a page with a next page inside the declared extent")
        was = page_of(cited(entry))
        entry["locator"]["citation"] = re.sub(r"\bp\.\s*%d\b" % was, f"p. {was + 1}",
                                              cited(entry))
        return f"{entry['id']}: p. {was} -> p. {was + 1}, evidence untouched"
    entry = first(document, lambda e: in_scope(e) and quoted(e)
                  and re.search(r"\(([a-z])\)\s*$", str(cited(e))),
                  "cites a section whose citation ends in a lettered paragraph")
    was = re.search(r"\(([a-z])\)\s*$", cited(entry)).group(1)
    now = chr(ord(was) + 1)
    entry["locator"]["citation"] = re.sub(r"\(%s\)\s*$" % was, f"({now})", cited(entry))
    return f"{entry['id']}: ({was}) -> ({now}), evidence untouched"


DEFINITION = re.compile(r"\bmeans\b|\bis defined\b|\bfor purposes of\b|\bthe term\b", re.I)


def m_omit_definition(document, protocol=None):
    """A term the corpus defines, and the map does not.

    Where the protocol declares a `defined-term-use` mechanism (0026), the vocabulary is the
    entry it names and the omission is one of the terms that entry lists. Everywhere else it
    is an entry whose evidence states a definition. The inbound edges go with it: a mapper
    who never saw the definition never wrote an edge to it, and leaving one dangling would be
    caught by `references` for the wrong reason.
    """
    vocabulary = None
    for mechanism in (protocol or {}).get("pointerMechanisms", []):
        if isinstance(mechanism, dict) and mechanism.get("mechanism") == "defined-term-use":
            vocabulary = mechanism.get("vocabularyFrom")
    if vocabulary:
        source = by_id(document, vocabulary)
        # The vocabulary entry quotes the corpus's own list. The terms in it are the
        # capitalised words after the sentence that introduces them -- "This glossary defines
        # these conditions: Blinded Charmed ..." -- which is how that corpus prints a list.
        tail = (source.get("evidence") or "").split(":", 1)
        terms = re.findall(r"\b[A-Z][A-Za-z][A-Za-z-]+", tail[-1])
        for term in terms:
            for entry in entries(document):
                if entry is source or not in_scope(entry):
                    continue
                if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)",
                             entry.get("name") or "", re.I):
                    drop_inbound(document, entry["id"])
                    drop_entry(document, entry)
                    return (f"dropped {entry['id']}, the entry for {term!r} -- a term the "
                            f"protocol's vocabulary ({vocabulary}) names")
        raise NotApplicable(f"no entry maps a term {vocabulary} names")
    entry = first(document, lambda e: in_scope(e) and quoted(e)
                  and DEFINITION.search(e.get("evidence") or ""),
                  "quotes a definition")
    drop_inbound(document, entry["id"])
    drop_entry(document, entry)
    return f"dropped {entry['id']} ({cited(entry)}), which quotes a definition, and its inbound edges"


def m_remove_applicability(document):
    """The rule that decides when the rest applies, with every edge that pointed at it.

    Chosen by reach rather than by name: the entry the most others name in `enabledBy`, and
    failing that in `suspendedBy`, is the applicability rule of a map whatever it is called --
    § 1.121-1's effective date, Part 107's waivable-regulations.
    """
    counts = {}
    for field in ("enabledBy", "suspendedBy"):
        for entry in entries(document):
            for target in entry.get(field) or []:
                counts.setdefault(field, {}).setdefault(target, 0)
                counts[field][target] += 1
    for field in ("enabledBy", "suspendedBy"):
        if counts.get(field):
            target = max(sorted(counts[field]), key=lambda t: counts[field][t])
            reach = counts[field][target]
            entry = by_id(document, target)
            drop_inbound(document, target)
            drop_entry(document, entry)
            return (f"dropped {target}, which {reach} entries named in `{field}`, and every "
                    f"edge that named it")
    raise NotApplicable("no entry gates another, so the map records no applicability rule")


def m_hide_cross_reference(document):
    entry = first(document, lambda e: e.get("crossReferences"), "records a cross-reference")
    gone = entry["crossReferences"][0]
    entry["crossReferences"] = entry["crossReferences"][1:]
    if not entry["crossReferences"]:
        entry.pop("crossReferences")
    cites = gone.get("cites") if isinstance(gone, dict) else gone
    return f"hid {entry['id']}'s cross-reference to {cites!r}"


def m_narrow_extent(document):
    extent = document.get("extent")
    if not isinstance(extent, dict):
        raise NotApplicable("the map declares no extent")
    if extent.get("unit") == "page":
        if extent.get("to", 0) <= extent.get("from", 0):
            raise NotApplicable("the page extent is one page and cannot be narrowed")
        was = extent["to"]
        extent["to"] = was - 1
        # `endsBefore` is left exactly as committed. Removing it would be a second mutation,
        # and the `extent-end` check going quiet would be this tool's doing rather than the
        # narrowing's.
        return f"extent narrowed from {extent['from']}-{was} to {extent['from']}-{was - 1}"
    sections = extent.get("sections")
    if not isinstance(sections, list) or len(sections) < 2:
        raise NotApplicable("the section extent names fewer than two sections")
    gone = sections[-1]
    extent["sections"] = sections[:-1]
    return f"extent narrowed by dropping {gone}, which the map still cites"


MUTATIONS = [
    {
        "name": "drop-entry",
        "models": "the mapper never reached this rule",
        "wrong": "the corpus states a rule the map now has no entry for",
        "apply": m_drop_entry,
    },
    {
        "name": "drop-enabled-by",
        "models": "a gate recorded with less reach than it has (trial 9: 30 missing edges)",
        "wrong": "the corpus conditions this rule on a rule the map no longer says it depends on",
        "apply": m_drop_enabled_by,
    },
    {
        "name": "drop-suspended-by",
        "models": "an exception the mapper saw once and not everywhere it applies",
        "wrong": "the corpus suspends this rule under a condition the map no longer records",
        "apply": m_drop_suspended_by,
    },
    {
        "name": "clear-to-ambiguous",
        "models": "a mapper who invents doubt the corpus settles",
        "wrong": "the corpus does resolve this question; the map records it as open",
        "apply": m_clear_to_ambiguous,
    },
    {
        "name": "ambiguous-to-clear",
        "models": "premature collapse (0033): two readings, one asserted, no doubt recorded",
        "wrong": "the corpus supports two readings and the map now states one as certain",
        "apply": m_ambiguous_to_clear,
    },
    {
        "name": "assertion-to-operation",
        "models": "trial 1's finding, in reverse: a caller's fact re-read as a computation",
        "wrong": "no passage lets the engine compute this; the corpus makes it an input",
        "apply": m_assertion_to_operation,
    },
    {
        "name": "invent-depends-on",
        "models": "#13: six wrong `dependsOn` edges in a map written in earnest",
        "wrong": "the corpus imposes no such order between these two rules",
        "apply": m_invent_depends_on,
    },
    {
        "name": "neighbour-evidence",
        "models": "the thirteen wrong citations that survived trial 4's build and review",
        "wrong": "the quote is verbatim of the corpus and is not the passage the entry cites",
        "apply": m_neighbour_evidence,
    },
    {
        "name": "same-passage-evidence",
        "models": "the same error inside one cited passage, where locator granularity cannot see it",
        "wrong": "the entry's rule is stated by a different sentence of the passage it cites",
        "apply": m_same_passage_evidence,
    },
    {
        "name": "move-locator",
        "models": "a citation off by one unit, the commonest transcription error",
        "wrong": "the evidence is not at the citation the entry now names",
        "apply": m_move_locator,
    },
    {
        "name": "omit-definition",
        "models": "a defined term the map uses and never maps",
        "wrong": "the corpus defines a term the map relies on and no entry records the definition",
        "apply": m_omit_definition,
    },
    {
        "name": "remove-applicability",
        "models": "the rule that says when the rest applies, never mapped",
        "wrong": "the corpus conditions the whole slice on a rule the map does not contain",
        "apply": m_remove_applicability,
    },
    {
        "name": "hide-cross-reference",
        "models": "#208: a pointer nobody noticed, measured at 0 of 51 in one corpus",
        "wrong": "the passage points somewhere and the map no longer says where",
        "apply": m_hide_cross_reference,
    },
    {
        "name": "narrow-extent",
        "models": "a map that claims less than it cites, so coverage becomes easy to satisfy",
        "wrong": "the map read more of the corpus than it now declares, and cites what it disclaims",
        "apply": m_narrow_extent,
    },
]

MUTATIONS_BY_NAME = {m["name"]: m for m in MUTATIONS}


# --- running the detectors ---------------------------------------------------------------

VERDICT = re.compile(r"^\[(ok|fail|skip)\] ([A-Za-z0-9][A-Za-z0-9 ./-]*?): (.*)$")
SECTION_COVERAGE = re.compile(r"^\s+X\s+§")


def parse_named(stdout):
    """`[ok] name: summary`, the format check-map.py and two of the three locator checkers use."""
    verdicts = {}
    for line in stdout.splitlines():
        match = VERDICT.match(line)
        if match:
            verdicts[match.group(2)] = (match.group(1), match.group(3))
    return verdicts


def parse_section(stdout):
    """check-locators-section.py prints findings, not verdicts, so its two checks are read out.

    `  X  <id>: ...` is a citation whose evidence is not where it says; `  X  § N: ...` is a
    section of the extent no verified quote reached; `  ?  <id>: ...` is an entry it could not
    check, which that tool fails the run for. Anything else it prints that begins a finding is
    reported under `locators`, so a new failure mode cannot be silently unscored.
    """
    verdicts = {"locators": ("ok", "every citation checked"),
                "coverage": ("ok", "every declared section reached")}
    for line in stdout.splitlines():
        if SECTION_COVERAGE.match(line):
            verdicts["coverage"] = ("fail", line.strip())
        elif line.startswith("  X  ") or line.startswith("  !  "):
            verdicts["locators"] = ("fail", line.strip())
        elif line.startswith("  ?  ") and verdicts["locators"][0] == "ok":
            verdicts["locators"] = ("skip", line.strip())
    return verdicts


def run(argv, root):
    proc = subprocess.run([sys.executable] + argv, cwd=root, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def comparison_record(directory):
    """Where the blind second mapping's adjudication record lives for a committed map, or None.

    The directory, not the file: which of the files in it is the readable record is the
    validator's to decide, and `--comparison` takes a directory for exactly that reason. A
    subject that was never mapped twice has no such directory.
    """
    home = os.path.join(directory, "blind-mapping")
    return home if os.path.isdir(home) else None


def detectors(subject, map_path, root, previous=None):
    """Every verdict the validator reaches about this map, by detector and by check name.

    `previous` is the committed map, passed as the version this one replaces (#268). That is
    what the run models: the committed map is the published version, the mutated map is the one
    proposed to replace it, and a check that had subject matter there and has none here is a
    claim that the corpus changed. The control gets it too, pointing at the same bytes, so the
    control's verdicts are unchanged by it and a detection is the mutation's doing.
    """
    directory = os.path.join(root, subject["dir"])
    manifest = os.path.join(directory, "corpus-manifest.json")
    results = {}

    argv = ["tools/check-map.py", map_path, "--manifest", manifest, "--repo-root", root]
    if previous:
        argv += ["--previous", previous]
    # The map is written into a bare temporary directory, so the checks that find a file beside
    # the map find nothing there. `superposition` reads the blind second mapping's adjudication
    # record (0034), and without this it says NOT VERIFIED on the control and on every mutation,
    # which would report a check this harness never ran as a check that noticed nothing.
    record = comparison_record(directory)
    if record:
        argv += ["--comparison", record]
    code, out = run(argv, root)
    results["check-map.py"] = {"exit": code, "checks": parse_named(out), "output": out}

    argv = [a.format(map=map_path) for a in subject["locators"]]
    code, out = run(argv, root)
    parse = parse_section if subject["locator_format"] == "section" else parse_named
    name = os.path.basename(argv[0])
    results[name] = {"exit": code, "checks": parse(out), "output": out}
    return results


def score(control, mutated):
    """What the validator said, and whether saying it would have stopped the map.

    A check that turns is not by itself a detection. `check-map.py` exits 0 on a NOT VERIFIED
    whose check had no subject matter -- turning an assertion into an operation leaves
    `asserted-by` with nothing to look at, and it says so and passes the run. A map that
    passes is a map that ships, so **detected means the run went red**: some detector that
    exited 0 on the control exits non-zero here. A check that turned without failing the run
    is recorded as `signalled`, counted as a miss, and reported, because a signal nobody is
    obliged to act on is the shape of this repository's two checkers that counted work they
    had not done.
    """
    turned, refused = [], []
    for detector, after in mutated.items():
        before = control[detector]
        for name, (status, summary) in sorted(after["checks"].items()):
            was = before["checks"].get(name)
            if was and was[0] == "ok" and status != "ok":
                turned.append({"detector": detector, "check": name, "status": status,
                               "said": summary[:300]})
        if before["exit"] == 0 and after["exit"] != 0:
            refused.append(detector)
    unexplained = [d for d in refused
                   if not any(t["detector"] == d for t in turned)]
    return turned, refused, unexplained


def measure(subject, root, only=None):
    """One control run and one run per mutation, in a temporary directory that does not survive."""
    directory = os.path.join(root, subject["dir"])
    with open(os.path.join(directory, "corpus-map.json"), encoding="utf-8") as handle:
        committed = json.load(handle)
    protocol = None
    protocol_path = os.path.join(directory, "mapping-protocol.json")
    if os.path.exists(protocol_path):
        with open(protocol_path, encoding="utf-8") as handle:
            protocol = json.load(handle)

    workspace = tempfile.mkdtemp(prefix="mutate-map-")
    runs, problems = [], []
    try:
        map_path = os.path.join(workspace, "corpus-map.json")
        # The published version every run is measured against (#268). Named so that
        # `find_manifest` and `pack-map.py`'s one-map rule do not see a second map beside it.
        previous_path = os.path.join(workspace, "published-map.json")
        write(previous_path, committed)
        write(map_path, committed)
        control = detectors(subject, map_path, root, previous_path)
        for detector, result in control.items():
            if result["exit"] != 0:
                problems.append(f"{subject['name']}: {detector} is already red on the committed "
                                f"map, so nothing it says about a mutation means anything")

        for mutation in MUTATIONS:
            if only and mutation["name"] not in only:
                continue
            document = copy.deepcopy(committed)
            try:
                if mutation["apply"] is m_omit_definition:
                    what = mutation["apply"](document, protocol)
                else:
                    what = mutation["apply"](document)
            except NotApplicable as why:
                runs.append({"mutation": mutation["name"], "applicable": False,
                             "why": str(why)})
                continue
            if document == committed:
                problems.append(f"{subject['name']}/{mutation['name']}: the mutation changed "
                                f"nothing, and would be scored as an undetected error")
                continue
            write(map_path, document)
            after = detectors(subject, map_path, root, previous_path)
            turned, refused, unexplained = score(control, after)
            for detector in unexplained:
                problems.append(f"{subject['name']}/{mutation['name']}: {detector} exited "
                                f"non-zero and no named check turned; the verdict was not read")
            runs.append({
                "mutation": mutation["name"], "applicable": True, "damage": what,
                "detected": bool(refused), "refusedBy": refused,
                "signalled": bool(turned) and not refused,
                "by": turned,
            })
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    return runs, problems


def write(path, document):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


# --- reporting ----------------------------------------------------------------------------

def commit(root):
    proc = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True)
    return proc.stdout.strip() or "unknown"


def table(measurement):
    """The results as markdown: one row per mutation, one column per corpus."""
    names = [s["name"] for s in measurement["subjects"]]
    lines = ["| mutation | " + " | ".join(names) + " |",
             "|---|" + "---|" * len(names)]
    for mutation in MUTATIONS:
        cells = []
        for subject in measurement["subjects"]:
            run_of = {r["mutation"]: r for r in subject["runs"]}.get(mutation["name"])
            if run_of is None:
                cells.append("not run")
            elif not run_of["applicable"]:
                cells.append("n/a")
            elif run_of["detected"]:
                cells.append(", ".join(sorted({t["check"] for t in run_of["by"]})))
            elif run_of["signalled"]:
                cells.append("signalled only: "
                             + ", ".join(sorted({t["check"] for t in run_of["by"]})))
            else:
                cells.append("**missed**")
        lines.append(f"| `{mutation['name']}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def shape(measurement):
    """The measurement without the commit it was taken at: what a re-run must reproduce."""
    return {
        subject["name"]: {
            run_of["mutation"]: {
                "applicable": run_of["applicable"],
                "detected": run_of.get("detected", False),
                "signalled": run_of.get("signalled", False),
                "by": sorted({f"{t['detector']}:{t['check']}" for t in run_of.get("by", [])}),
            }
            for run_of in subject["runs"]
        }
        for subject in measurement["subjects"]
    }


def compare(committed, fresh):
    """Every way the committed measurement no longer describes what the validator does.

    The gate runs this rather than a staleness date, because a date says when somebody last
    looked and this says whether what they wrote down is still true. A check added to the
    validator, a map corrected, a mutation retargeted: each shows up here as the row it
    changes, and the fix is to re-record the measurement rather than to bump a timestamp.
    """
    differences = []
    old, new = shape(committed), shape(fresh)
    for name in sorted(set(old) | set(new)):
        if name not in old:
            differences.append(f"  X  {name}: measured now and absent from the committed table")
            continue
        if name not in new:
            differences.append(f"  X  {name}: in the committed table and not measured now")
            continue
        for mutation in sorted(set(old[name]) | set(new[name])):
            was, is_now = old[name].get(mutation), new[name].get(mutation)
            if was != is_now:
                differences.append(f"  X  {name}/{mutation}: recorded {was}, measured {is_now}")
    return differences


def main(argv=None):
    parser = argparse.ArgumentParser(description="Damage a committed map and measure what the "
                                                 "validator notices.")
    parser.add_argument("--subject", action="append",
                        help="one map by name; repeatable. Default: every subject")
    parser.add_argument("--only", help="one mutation, or a comma-separated list")
    parser.add_argument("--list", action="store_true", help="print the catalogue and stop")
    parser.add_argument("--json", help="write the full measurement here")
    parser.add_argument("--markdown", help="write the results table here")
    parser.add_argument("--check", metavar="PATH",
                        help="re-measure and fail unless the committed measurement at PATH still "
                             "describes what the validator does. This is what the gate runs")
    parser.add_argument("--repo-root", default=ROOT)
    args = parser.parse_args(argv)

    if args.list:
        for mutation in MUTATIONS:
            print(f"{mutation['name']:<24} {mutation['models']}")
        for subject in SUBJECTS:
            print(f"subject {subject['name']:<32} {subject['genre']}, {subject['grammar']}")
        return 0

    only = set(args.only.split(",")) if args.only else None
    if only:
        unknown = sorted(only - set(MUTATIONS_BY_NAME))
        if unknown:
            print(f"unknown mutation(s): {', '.join(unknown)}", file=sys.stderr)
            return 2
    chosen = [s for s in SUBJECTS if not args.subject or s["name"] in args.subject]
    if not chosen:
        print("no subject matched; --list names them", file=sys.stderr)
        return 2

    root = os.path.abspath(args.repo_root)
    measurement = {"measuredAt": commit(root), "subjects": []}
    problems = []
    for subject in chosen:
        runs, trouble = measure(subject, root, only)
        problems.extend(trouble)
        measurement["subjects"].append({
            "name": subject["name"], "genre": subject["genre"], "grammar": subject["grammar"],
            "map": subject["dir"] + "/corpus-map.json", "runs": runs,
        })
        applied = [r for r in runs if r["applicable"]]
        missed = [r for r in applied if not r["detected"]]
        print(f"{subject['name']}: {len(applied) - len(missed)} of {len(applied)} detected, "
              f"{len(missed)} missed, {len(runs) - len(applied)} not applicable")
        for run_of in runs:
            if not run_of["applicable"]:
                print(f"  n/a  {run_of['mutation']}: {run_of['why']}")
            elif run_of["detected"]:
                print(f"  ok   {run_of['mutation']}: refused by "
                      + ", ".join(f"{t['detector']}:{t['check']}={t['status']}"
                                  for t in run_of["by"]))
            elif run_of["signalled"]:
                print(f"  SIG  {run_of['mutation']}: {run_of['damage']}\n"
                      f"       turned but did not fail the run: "
                      + ", ".join(f"{t['detector']}:{t['check']}={t['status']}"
                                  for t in run_of["by"]))
            else:
                print(f"  MISS {run_of['mutation']}: {run_of['damage']}")

    applied = [r for s in measurement["subjects"] for r in s["runs"] if r["applicable"]]
    detected = [r for r in applied if r["detected"]]
    measurement["totals"] = {"applied": len(applied), "detected": len(detected),
                             "missed": len(applied) - len(detected)}
    print(f"\n{len(detected)} of {len(applied)} mutations detected; "
          f"{len(applied) - len(detected)} missed")
    print(table(measurement))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(measurement, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as handle:
            handle.write(table(measurement) + "\n")

    if not applied:
        print("no mutation was applied -- this run measured nothing", file=sys.stderr)
        return 1
    for problem in problems:
        print(f"  X  {problem}", file=sys.stderr)
    if problems:
        return 1

    if args.check:
        if args.subject or only:
            print("--check re-measures everything; it cannot be narrowed", file=sys.stderr)
            return 2
        try:
            with open(args.check, encoding="utf-8") as handle:
                committed = json.load(handle)
        except (OSError, ValueError) as error:
            print(f"cannot read the committed measurement {args.check}: {error}", file=sys.stderr)
            return 2
        differences = compare(committed, measurement)
        if differences:
            print(f"\nthe committed measurement ({args.check}, taken at "
                  f"{committed.get('measuredAt', 'an unrecorded commit')}) no longer describes "
                  f"what the validator does:", file=sys.stderr)
            for line in differences:
                print(line, file=sys.stderr)
            print("re-run tools/mutate-map.py --json <that file> and read the table again: a row "
                  "that moved is either a check that grew or a check that stopped looking",
                  file=sys.stderr)
            return 1
        print(f"\nthe committed measurement at {args.check} still describes what the validator "
              f"does ({len(applied)} mutations re-measured)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
