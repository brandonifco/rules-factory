#!/usr/bin/env python3
"""Validate a corpus map against docs/corpus-map.md and docs/decisions/0005.

`schema/` is empty and nothing has ever validated these maps. That is how
`kind: "rule"` -- outside the closed vocabulary -- shipped in both copies of the
backgammon map, and it is the gap this tool closes for everything the spec states
*structurally*. It does not read the corpus: `check-locators.py` does that.

What it cannot do, stated here rather than in a commit message:

  * **A conflict nobody recorded is invisible.** `ambiguity.conflict` (0007) groups the
    entries that answer one contradicted question, and `conflicts` enforces that a group
    has two or more members, one fate, and one decision record. Nothing detects the
    conflict a mapper never noticed: two `clarity: clear` entries stating incompatible
    rules pass every check here.
  * **Correspondence row 7** ("two implemented entries with no entry for their
    combination") is a fact about pairs and about interactions the map does not enumerate.
    It is not evaluated. The `correspondence` check therefore proves that every entry is
    reachable by rows 1-6 and 8, not by all eight.
  * Rows 1-8 are not exhaustive by design: a built, clear, unambiguous rule matches no row
    because the engine simply answers. Unmatched entries are reported; an unmatched entry
    is a **failure** only when `status: declined`, which asserts no implemented path at all
    and therefore owes a runtime reason.
  * **An absence is claimed here and proved elsewhere.** `absentFrom` (0009) asserts the
    corpus does not contain the rule. Nothing in this file reads a corpus, so the `absent`
    check enforces only the shape of the claim -- that it is non-empty, that it excludes
    the fields it contradicts, and that nothing depends on a rule that does not exist. The
    claim itself is falsified by `check-locators.py`, which searches the text.
  * **A cross-reference nobody noticed is invisible.** `cross-references` reads the
    pointer phrases it knows about and no others; a corpus that points somewhere in words
    outside that list produces a map that passes. The list is stated in
    `POINTER_PHRASES` rather than inferred, so what the check does not cover is readable.
  * Nothing here checks that an entry is the *right* decomposition of the corpus, that a
    gate list (`enabledBy`, `suspendedBy`) is complete, or that `evidence` is sufficient.
    Those are review.

Where each check runs is stated in STATUS_DEPENDENT below (0015): every check runs before a
map is published; the status-dependent ones run again in the engine, on its merged map.

Usage: check-map.py <corpus-map.json> [--manifest PATH] [--repo-root PATH] [--only CHECK]
                    [--phase publish|consumer]
Exit 0 only if every check that ran passed and at least one check actually checked
something; 1 if any check failed or skipped with subject matter; 2 on a usage error.
"""
import argparse
import json
import os
import sys

# The `schemaVersion`s this checker reads. A map in any other version is not one these checks
# describe, so `schema` fails it rather than checking fields whose meaning may have moved; and
# the factory refuses to intake it (0016), reading this set rather than keeping its own.
SCHEMA_VERSIONS = (1,)

KINDS = {"value", "operation", "assertion"}
SCOPES = {"in", "out"}
CLARITIES = {"clear", "ambiguous"}
STATUSES = {"mapped", "blocked", "implemented", "declined"}
FATES = {"decision", "unresolved"}
# The kernel's closed UnresolvedReason vocabulary, as the correspondence table names it.
UNRESOLVED_REASONS = {
    "OutsideCurrentScope",
    "UnsupportedRule",
    "MissingRulesData",
    "RequiresInterpretation",
    "UnsupportedInteraction",
}
REQUIRED_ENTRY_FIELDS = ["id", "name", "locator", "kind", "scope", "clarity", "evidence", "status"]
# A derived entry (0012) cites nothing: no sentence contains its fact, so it has no passage
# to locate or quote. Its sources' locators and evidence are its citation.
CITING_FIELDS = ("locator", "evidence")
# What only a passage can carry, and so what a derived entry may not.
PASSAGE_FIELDS = CITING_FIELDS + ("crossReferences", "absentFrom", "beyondAdapter", "definedElsewhere")
# The relations that hold entry ids and nothing else. `gatedBy` is not among them: 0011 split
# it into the two gate fields, and `gates` refuses it by name.
GATE_FIELDS = ("enabledBy", "suspendedBy")
ID_LIST_FIELDS = ("dependsOn",) + GATE_FIELDS


class Result:
    """One check's verdict. `skip` never becomes `ok`; it fails the run if it had work."""

    def __init__(self, status, summary, details=None, had_subject=True):
        self.status = status  # "ok" | "fail" | "skip"
        self.summary = summary
        self.details = details or []
        self.had_subject = had_subject

    @property
    def fatal(self):
        return self.status == "fail" or (self.status == "skip" and self.had_subject)


def ok(summary, details=None):
    return Result("ok", summary, details)


def fail(details, summary):
    return Result("fail", summary, details)


def skip(summary, had_subject=True):
    return Result("skip", "NOT VERIFIED -- " + summary, had_subject=had_subject)


def verdict(details, ok_summary, fail_summary):
    return fail(details, fail_summary) if details else ok(ok_summary)


# --- helpers -------------------------------------------------------------------------


def corpora_of(manifest):
    if not isinstance(manifest, dict):
        return {}
    return {c.get("sourceId"): c for c in manifest.get("corpora") or [] if isinstance(c, dict)}


def quotes_withheld(ctx, entry):
    """True when the entry's corpus declares `quotation: withheld` (0013)."""
    source = corpora_of(ctx.get("manifest")).get(block(entry, "locator").get("sourceId"))
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


# --- checks --------------------------------------------------------------------------


def check_schema(ctx):
    """The map's own envelope: the stamp naming the baseline it was built against."""
    doc, bad = ctx["map"], []
    if not isinstance(doc, dict):
        return fail(["  X  top level is not an object"], "the map is not an object")
    for field in ("schemaVersion", "corpus", "baseline", "entries"):
        if field not in doc:
            bad.append(f"  X  map is missing `{field}`")
    version = doc.get("schemaVersion")
    if "schemaVersion" in doc and (isinstance(version, bool) or version not in SCHEMA_VERSIONS):
        bad.append(f"  X  schemaVersion {version!r} is not one this checker reads "
                   f"({', '.join(map(str, SCHEMA_VERSIONS))})")
    baseline = doc.get("baseline")
    if "baseline" in doc and not isinstance(baseline, dict):
        bad.append("  X  `baseline` is not an object")
    elif isinstance(baseline, dict):
        for field in ("contentHash", "hashDerivation"):
            if not baseline.get(field):
                bad.append(f"  X  baseline is missing `{field}`: a digest without its derivation does not say what it covers")
    if "entries" in doc and not isinstance(doc.get("entries"), list):
        bad.append("  X  `entries` is not a list")
    elif not entries_of(doc) and isinstance(doc.get("entries"), list):
        bad.append("  X  `entries` is empty: there is nothing to check")
    return verdict(bad, "map envelope and baseline stamp present", "the map envelope is incomplete")


def check_required_fields(ctx):
    """Every field the spec's table marks required, and `locator` above all.

    "An entry without one is not an entry" (corpus-map.md), so a missing or malformed
    locator is reported as its own line rather than folded into a field list.
    """
    bad = []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            bad.append(f"  X  entry[{position}] is not an object")
            continue
        name = label(entry, position)
        derived = "derivedFrom" in entry
        for field in REQUIRED_ENTRY_FIELDS:
            if derived and field in CITING_FIELDS:
                continue  # `derived` refuses them instead: a derived entry cites nothing
            if field == "evidence" and quotes_withheld(ctx, entry):
                continue  # `postures` refuses it instead: the licence forbids the span
            if field not in entry:
                bad.append(f"  X  {name}: missing required field `{field}`")
        if "locator" in entry and not derived:
            locator = entry.get("locator")
            if not isinstance(locator, dict):
                bad.append(f"  X  {name}: `locator` is not an object")
            else:
                for field in ("sourceId", "citation"):
                    if not locator.get(field):
                        bad.append(f"  X  {name}: locator is missing `{field}`")
        for field in ID_LIST_FIELDS:
            if field in entry and not isinstance(entry[field], list):
                bad.append(f"  X  {name}: `{field}` is not a list of ids")
    return verdict(bad, f"{len(entries_of(ctx['map']))} entries carry every required field", "required fields are missing")


def check_vocabulary(ctx):
    """The five closed vocabularies, plus the kernel's UnresolvedReason enum.

    `beyondAdapter.modality` is deliberately open (0004) and is only checked for presence.
    """
    bad = []
    closed = [("kind", KINDS), ("scope", SCOPES), ("clarity", CLARITIES), ("status", STATUSES)]
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        for field, allowed in closed:
            if field in entry and entry[field] not in allowed:
                bad.append(f"  X  {name}: {field} is {entry[field]!r}, outside {{{', '.join(sorted(allowed))}}}")
        ambiguity = block(entry, "ambiguity")
        if "fate" in ambiguity and ambiguity["fate"] not in FATES:
            bad.append(f"  X  {name}: ambiguity.fate is {ambiguity['fate']!r}, outside {{decision, unresolved}}")
        reason = ambiguity.get("unresolvedReason")
        if reason is not None and reason not in UNRESOLVED_REASONS:
            bad.append(f"  X  {name}: unresolvedReason is {reason!r}, outside the kernel's UnresolvedReason vocabulary")
        if "beyondAdapter" in entry:
            for field in ("adapter", "modality"):
                if not block(entry, "beyondAdapter").get(field):
                    bad.append(f"  X  {name}: beyondAdapter is missing `{field}`")
        if "definedElsewhere" in entry and not block(entry, "definedElsewhere").get("reference"):
            bad.append(f"  X  {name}: definedElsewhere is missing `reference`")
        if "absentFrom" in entry:
            searched = block(entry, "absentFrom").get("searched")
            if not isinstance(searched, list) or not searched:
                bad.append(f"  X  {name}: absentFrom is missing a non-empty `searched` list; an "
                           f"absence nobody searched for is the state 0009 exists to separate out")
            elif any(not isinstance(term, str) or not term.strip() for term in searched):
                bad.append(f"  X  {name}: absentFrom.searched holds something that is not a term")
    return verdict(bad, "every closed vocabulary holds only its stated values", "a field is outside its closed vocabulary")


def check_unique_ids(ctx):
    """Ids are referenced by dependsOn, by issues, and by the engine's own citations."""
    seen, bad = {}, []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str):
            bad.append(f"  X  entry[{position}]: `id` is not a string")
        elif entry_id in seen:
            bad.append(f"  X  {entry_id}: id used by entry[{seen[entry_id]}] as well")
        else:
            seen[entry_id] = position
    return verdict(bad, f"{len(seen)} ids, all distinct", "an id is duplicated or missing")


def check_references(ctx):
    """`dependsOn`, `enabledBy` and `suspendedBy` hold entry ids in the same map, and nothing else.

    0003: "If a proposed gate has no entry, the map is missing an entry; that is the
    finding, not a reason to write prose here."
    """
    by_id, bad, edges = index(ctx["map"]), [], 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        for field in ID_LIST_FIELDS:
            for ref in entry.get(field) or []:
                edges += 1
                if not isinstance(ref, str):
                    bad.append(f"  X  {name}: {field} holds {ref!r}, which is not an id")
                elif ref not in by_id:
                    bad.append(f"  X  {name}: {field} names {ref!r}, which is not an entry in this map")
                elif ref == entry.get("id"):
                    bad.append(f"  X  {name}: {field} names itself")
    if not edges:
        return skip("no entry names a dependsOn, enabledBy or suspendedBy, so no reference was resolved",
                    had_subject=False)
    return verdict(bad, f"{edges} dependsOn/enabledBy/suspendedBy references all resolve",
                   "a reference names no entry")


def check_no_cycles(ctx):
    """`dependsOn` determines backlog order, so a cycle means no order exists.

    The gate fields are deliberately not checked for cycles: they order nothing (0003), and a
    mutual gate is a legitimate shape -- entry from the bar suspends other moves while
    those moves' own gate names it back.
    """
    by_id = index(ctx["map"])
    colour, bad = {}, []

    def walk(node, trail):
        colour[node] = "open"
        for dep in by_id.get(node, {}).get("dependsOn") or []:
            if not isinstance(dep, str) or dep not in by_id:
                continue
            if colour.get(dep) == "open":
                cycle = trail[trail.index(dep):] if dep in trail else [dep]
                bad.append("  X  dependsOn cycle: " + " -> ".join(cycle + [dep]))
            elif dep not in colour:
                walk(dep, trail + [dep])
        colour[node] = "closed"

    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    for node in by_id:
        if node not in colour:
            walk(node, [node])
    if not any(by_id[node].get("dependsOn") for node in by_id):
        return skip("no entry depends on another, so acyclicity was not exercised", had_subject=False)
    return verdict(sorted(set(bad)), f"dependsOn over {len(by_id)} entries is acyclic", "dependsOn has a cycle")


def check_gates(ctx):
    """A gate has a direction, and the field it sits in states it (0011).

    0003 recorded a gate as one undirected list, `gatedBy`, and accepted as a cost that
    `bearing-off-eligible` (which opens a phase) and `enter-from-bar` (which closes one) looked
    identical on the entries they gate. 0011 splits the list: `enabledBy` names the rules that
    make this rule reachable, `suspendedBy` the rules that make it unreachable. Resolving the
    ids is `references`' job; what is checked here is what the split adds:

      * `gatedBy` is refused by name. A map still carrying it states gates with no direction,
        which is what 0011 removed, and ignoring the field would make every gate in an
        unmigrated map vanish from every other check without a word;
      * no entry names one rule in both fields, because one rule cannot both open and close
        the same entry's reachability.

    What it cannot do: tell whether a gate is in the right field. A permitting rule filed under
    `suspendedBy` resolves, is not duplicated, and passes. That is review -- what 0011 buys is
    that the direction is written where a reviewer reads it, rather than recovered by following
    the id.
    """
    bad, gated = [], 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        if "gatedBy" in entry:
            bad.append(f"  X  {name}: carries `gatedBy`, which 0011 split by direction; name each "
                       f"gate in `enabledBy` (makes this rule reachable) or `suspendedBy` (makes it "
                       f"unreachable)")
        lists = {field: entry.get(field) if isinstance(entry.get(field), list) else []
                 for field in GATE_FIELDS}
        if any(lists.values()):
            gated += 1
        both = {x for x in lists["enabledBy"] if isinstance(x, str)} & \
            {x for x in lists["suspendedBy"] if isinstance(x, str)}
        for ref in sorted(both):
            bad.append(f"  X  {name}: names {ref!r} in both `enabledBy` and `suspendedBy`; one rule "
                       f"cannot both open and close this one")
    if not gated and not bad:
        return skip("no entry carries `enabledBy` or `suspendedBy`, so no gate's direction was "
                    "checked -- the right outcome for a stateless corpus", had_subject=False)
    return verdict(bad, f"{gated} gated entr{'y' if gated == 1 else 'ies'}: every gate is filed by "
                        f"direction, and none in both directions",
                   "a gate does not state its direction")


def check_derived(ctx):
    """A derived entry is a fact the corpus entails and never states (0012).

    `stake-multiplier`'s span states what a gammon and a backgammon pay, both as multiples of
    a single stake, and never what a hit pays. That a hit pays the single stake is read off
    the other two. 0012 gives the fact its own entry and a fourth relation, `derivedFrom`: not
    implementation order (`dependsOn`), not reachability (the gate fields), not a pointer the
    corpus makes (`crossReferences`), but *this fact is entailed by those facts*.

      * `derivedFrom` is a list of at least two ids. A consequence of one entry is that
        entry's, and 0012 discharges it as a test the entry names, not as an entry;
      * every source resolves in this map, is not the entry itself, and is `scope: in` -- a
        fact cannot be derived from a rule the engine does not cover, or from an absence;
      * no derivation is circular, following `derivedFrom` through derived sources;
      * a derived entry cites nothing: no `locator`, no `evidence`, and nothing only a passage
        carries (`crossReferences`, `absentFrom`, `beyondAdapter`, `definedElsewhere`). No
        sentence contains its fact, so `evidence` keeps one meaning -- a verbatim span -- on
        every entry that has it, and the derived entry's citation is its sources'.

    What it cannot do: tell whether the sources actually entail the fact. That a hit pays one
    stake *follows* from the two payouts is the mapper's reading, written in `note`; this check
    proves only that the reading names what it rests on and that those are rules the map
    covers.
    """
    by_id, bad, carriers = index(ctx["map"]), [], []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict) or "derivedFrom" not in entry:
            continue
        name = label(entry, position)
        carriers.append(name)
        sources = entry.get("derivedFrom")
        if not isinstance(sources, list) or any(not isinstance(s, str) for s in sources):
            bad.append(f"  X  {name}: `derivedFrom` is not a list of entry ids")
            continue
        if len(set(sources)) < 2:
            bad.append(f"  X  {name}: `derivedFrom` names {len(set(sources))} source(s); a fact "
                       f"that follows from one entry is that entry's consequence, and is a test "
                       f"that entry names (0012), not an entry")
        for ref in sources:
            target = by_id.get(ref)
            if target is None:
                bad.append(f"  X  {name}: derivedFrom names {ref!r}, which is not an entry in this map")
            elif ref == entry.get("id"):
                bad.append(f"  X  {name}: derivedFrom names itself")
            elif target.get("scope") != "in":
                bad.append(f"  X  {name}: derivedFrom names {ref!r}, which is scope "
                           f"{target.get('scope')!r}; a fact is not derived from a rule the engine "
                           f"does not cover")
        for field in PASSAGE_FIELDS:
            if field in entry:
                bad.append(f"  X  {name}: is derived and carries `{field}`; no sentence states a "
                           f"derived fact, so it cites nothing and its sources are its citation")

    colour = {}

    def walk(node, trail):
        colour[node] = "open"
        sources = by_id.get(node, {}).get("derivedFrom")
        for ref in sources if isinstance(sources, list) else []:
            if not isinstance(ref, str) or ref not in by_id or ref == node:
                continue
            if colour.get(ref) == "open":
                bad.append("  X  derivedFrom cycle: " + " -> ".join(trail[trail.index(ref):] + [ref]))
            elif ref not in colour:
                walk(ref, trail + [ref])
        colour[node] = "closed"

    for node, entry in by_id.items():
        if "derivedFrom" in entry and node not in colour:
            walk(node, [node])

    if not carriers:
        return skip("no entry carries `derivedFrom`, so no derivation was checked", had_subject=False)
    return verdict(sorted(set(bad), key=bad.index),
                   f"{len(carriers)} derived entr{'y' if len(carriers) == 1 else 'ies'} "
                   f"({', '.join(sorted(carriers))}): each derives from two or more in-scope "
                   f"entries and cites nothing itself",
                   "a derived entry is not well-formed")


def check_manifest(ctx):
    """Everything that resolves against the manifest rather than against the map.

    The map's `corpus` and baseline stamp, every `locator.sourceId`, `beyondAdapter.adapter`
    against the adapter declared for that source (0004), and `definedElsewhere.reference`
    against that source's `references` (0005).
    """
    manifest = ctx["manifest"]
    if manifest is None:
        return skip(
            "no manifest was given or found beside the map, so no sourceId, adapter or "
            "reference was resolved. Pass --manifest."
        )
    corpora = {c.get("sourceId"): c for c in manifest.get("corpora") or [] if isinstance(c, dict)}
    if not corpora:
        return skip("the manifest declares no corpora, so nothing could be resolved against it")

    doc, bad, checked = ctx["map"], [], 0
    corpus_id = doc.get("corpus")
    declared = corpora.get(corpus_id)
    if declared is None:
        bad.append(f"  X  map: corpus {corpus_id!r} is not declared in the manifest")
    else:
        checked += 1
        baseline = doc.get("baseline") if isinstance(doc.get("baseline"), dict) else {}
        for field in ("contentHash", "hashDerivation"):
            if baseline.get(field) and declared.get(field) and baseline[field] != declared[field]:
                bad.append(
                    f"  X  map: baseline {field} {baseline[field]!r} does not match the manifest's "
                    f"{declared[field]!r} for {corpus_id}"
                )

    for position, entry in enumerate(entries_of(doc)):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        source_id = block(entry, "locator").get("sourceId")
        source = corpora.get(source_id)
        if source_id is not None:
            checked += 1
            if source is None:
                bad.append(f"  X  {name}: locator.sourceId {source_id!r} is not declared in the manifest")
        if "beyondAdapter" in entry:
            checked += 1
            adapter = block(entry, "beyondAdapter").get("adapter")
            if source is None:
                bad.append(f"  X  {name}: beyondAdapter names adapter {adapter!r}, but its source is not in the manifest")
            elif adapter != source.get("adapter"):
                bad.append(
                    f"  X  {name}: beyondAdapter.adapter is {adapter!r}, but {source_id} declares "
                    f"{source.get('adapter')!r}"
                )
        if "definedElsewhere" in entry:
            checked += 1
            reference = block(entry, "definedElsewhere").get("reference")
            known = {r.get("sourceId") for r in (source or {}).get("references") or [] if isinstance(r, dict)}
            if source is None:
                bad.append(f"  X  {name}: definedElsewhere names {reference!r}, but its source is not in the manifest")
            elif reference not in known:
                bad.append(
                    f"  X  {name}: definedElsewhere.reference {reference!r} is not in {source_id}'s "
                    f"`references`; an elsewhere-defined *input* is kind: assertion, not this field"
                )
    if not checked:
        return skip("no entry carried anything that resolves against the manifest")
    return verdict(bad, f"{checked} manifest resolutions all succeed", "something does not resolve in the manifest")


VERIFICATION_POSTURES = {"committed-copy", "local-copy"}
QUOTATION_POLICIES = {"verbatim", "withheld"}


def check_postures(ctx):
    """How each corpus is verified, and whether a map may quote it, are declared per corpus (0013).

    0002 made *where a corpus lives* a property of its licence. 0013 carries that one step on:
    *how a consumer verifies the baseline* is declared per corpus too, and so is *whether the
    map may carry verbatim spans of it* -- because since #18 a map quotes a few hundred sentences
    of its corpus, and for a corpus that may not be committed the map is itself the
    redistribution question.

    Every admitted corpus in the manifest declares both:

      * `verification`: `committed-copy` (the bytes are in this repository, at `committedPath`,
        so anyone -- CI included -- can verify the hash) or `local-copy` (they are not; a holder
        of a legal copy points `envVar` at it, and everyone else is told NOT VERIFIED, never ok);
      * `quotation`: `verbatim` (entries quote spans, as corpus-map.md requires) or `withheld`
        (the licence forbids it, so no entry citing the corpus carries `evidence`).

    And what follows from them:

      * `never-commit` is `local-copy`: bytes the repository may not hold cannot be verified
        from it;
      * `local-copy` names `envVar`, or nobody could ever verify it;
      * `committed-copy` names `committedPath`, and the file exists beside the manifest;
      * under `withheld`, an entry that quotes anyway fails.

    What it cannot do: hash anything. `hashDerivation` names what a digest covers and this file
    does not know how to recompute any derivation, so a committed file with the wrong bytes
    passes here. Reporting the posture and verifying the hash is the gate's job. Nor does it
    decide a licence: `quotation` is declared by a person, and 0013 is explicit that nothing
    infers it.
    """
    manifest = ctx["manifest"]
    corpora = corpora_of(manifest)
    if not corpora:
        return skip("no manifest, or a manifest declaring no corpora, so no corpus's verification "
                    "posture or quotation policy was read. Pass --manifest.")
    base = os.path.dirname(os.path.abspath(ctx["manifest_path"])) if ctx.get("manifest_path") else None
    bad = []
    for source_id, corpus in corpora.items():
        name = f"manifest {source_id}"
        posture, quotation = corpus.get("verification"), corpus.get("quotation")
        if posture not in VERIFICATION_POSTURES:
            bad.append(f"  X  {name}: verification is {posture!r}, outside "
                       f"{{{', '.join(sorted(VERIFICATION_POSTURES))}}}; a corpus with no declared "
                       f"posture is a failure, not a default (0002, 0013)")
        if quotation not in QUOTATION_POLICIES:
            bad.append(f"  X  {name}: quotation is {quotation!r}, outside "
                       f"{{{', '.join(sorted(QUOTATION_POLICIES))}}}; whether a map may quote its "
                       f"corpus is declared per corpus, never assumed")
        if corpus.get("boundaryPolicy") == "never-commit" and posture == "committed-copy":
            bad.append(f"  X  {name}: is `never-commit` but claims `committed-copy`; bytes the "
                       f"repository may not hold cannot be verified from it")
        if posture == "local-copy" and not (isinstance(corpus.get("envVar"), str) and corpus["envVar"].strip()):
            bad.append(f"  X  {name}: is `local-copy` and names no `envVar`, so nobody holding a "
                       f"legal copy has anywhere to point the verifier")
        if posture == "committed-copy":
            path = corpus.get("committedPath")
            if not isinstance(path, str) or not path.strip():
                bad.append(f"  X  {name}: is `committed-copy` and names no `committedPath`")
            elif base is None or not os.path.isfile(os.path.join(base, path)):
                bad.append(f"  X  {name}: committedPath {path!r} is not a file beside the manifest; "
                           f"a committed copy that is not committed is `local-copy`")

    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        if quotes_withheld(ctx, entry):
            if entry.get("evidence"):
                bad.append(f"  X  {label(entry, position)}: quotes `evidence` from "
                           f"{block(entry, 'locator').get('sourceId')}, whose quotation is `withheld`; "
                           f"the span is recorded as absent, never quoted and never summarised")
    postures = sorted(f"{s}: {c.get('verification')}, {c.get('quotation')}" for s, c in corpora.items())
    return verdict(bad, f"{len(corpora)} corpus postures declared ({'; '.join(postures)})",
                   "a corpus's verification posture or quotation policy is missing or contradicted")


def check_exclusions(ctx):
    """The `ambiguity` block is not a general decline carrier (0005 D).

    Three rules: no entry carries `definedElsewhere` or `beyondAdapter` alongside an
    `ambiguity` block; `ambiguity` is present exactly when `clarity: ambiguous`; and the
    block's own contents -- `question`, `fate`, `decision` when the fate is `decision`,
    `unresolvedReason` when it is `unresolved`.
    """
    bad = []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        has_ambiguity = "ambiguity" in entry
        for field in ("definedElsewhere", "beyondAdapter"):
            if field in entry and has_ambiguity:
                bad.append(f"  X  {name}: carries `{field}` and an `ambiguity` block; two correspondence rows would fire")
        if entry.get("clarity") == "clear" and has_ambiguity:
            bad.append(f"  X  {name}: clarity is `clear` but an `ambiguity` block is present")
        if entry.get("clarity") == "ambiguous" and not has_ambiguity:
            bad.append(f"  X  {name}: clarity is `ambiguous` but no `ambiguity` block states the question")
        if has_ambiguity:
            ambiguity = block(entry, "ambiguity")
            if not isinstance(entry.get("ambiguity"), dict):
                bad.append(f"  X  {name}: `ambiguity` is not an object")
                continue
            if not ambiguity.get("question"):
                bad.append(f"  X  {name}: ambiguity has no `question`")
            if not ambiguity.get("fate"):
                bad.append(f"  X  {name}: ambiguity has no `fate`; there is no third value and no absent one")
            if ambiguity.get("fate") == "decision" and not ambiguity.get("decision"):
                bad.append(f"  X  {name}: fate is `decision` but no record is named")
            if ambiguity.get("fate") == "unresolved" and not ambiguity.get("unresolvedReason"):
                bad.append(f"  X  {name}: fate is `unresolved` but no `unresolvedReason` ties it to the correspondence table")
            if ambiguity.get("fate") == "decision" and ambiguity.get("unresolvedReason"):
                bad.append(f"  X  {name}: fate is `decision`, so there is no runtime unresolved reason to name")
    return verdict(bad, "ambiguity blocks are present exactly where clarity says, and carry nothing else's job",
                   "an ambiguity block is misused")


def tests_problems(name, tests):
    """What is wrong with a `tests` list, as report lines. Empty when it is well-formed."""
    if not isinstance(tests, list):
        return [f"  X  {name}: `tests` is not a list"]
    bad, seen = [], set()
    for position, item in enumerate(tests):
        if not isinstance(item, dict):
            bad.append(f"  X  {name}: tests[{position}] is not an object naming a test and its mutation")
            continue
        test, mutation = item.get("test"), item.get("mutation")
        if not isinstance(test, str) or not test.strip():
            bad.append(f"  X  {name}: tests[{position}] names no `test`")
        elif test in seen:
            bad.append(f"  X  {name}: names test {test!r} twice")
        else:
            seen.add(test)
        if not isinstance(mutation, str) or not mutation.strip():
            bad.append(f"  X  {name}: tests[{position}] ({test!r}) records no `mutation`; a test "
                       f"nobody has seen go red is not evidence")
    return bad


def check_status(ctx):
    """`implemented` is a claim with its evidence attached (#2), not a word someone typed.

    Two rules:

      * `implementedIn` is set when status becomes `implemented`, and only then;
      * an `implemented` entry names the tests that prove it in `tests`, non-empty, and every
        test carries the `mutation` that was recorded turning it red. Without them the entry is
        `mapped`, whatever the repository contains. Wherever `tests` appears, its shape is held
        to the same rule.

    What it cannot do: this file never sees an engine, so a named test that does not exist, or
    exists and never ran, passes here. That is the engine gate's check. And a recorded mutation
    proves one way of breaking the rule is caught, not that the test is good.
    """
    bad, implemented = [], 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        if "tests" in entry:
            bad.extend(tests_problems(name, entry["tests"]))
        if entry.get("status") == "implemented":
            implemented += 1
            if not entry.get("implementedIn"):
                bad.append(f"  X  {name}: status is `implemented` but no `implementedIn` names the ruleset revision")
            if not entry.get("tests"):
                bad.append(f"  X  {name}: status is `implemented` but `tests` names no test that proves "
                           f"it; without one the entry is `mapped`")
        elif entry.get("implementedIn"):
            bad.append(f"  X  {name}: carries `implementedIn` while status is {entry.get('status')!r}")
    carriers = sum(1 for e in entries_of(ctx["map"])
                   if isinstance(e, dict) and (e.get("implementedIn") or "tests" in e))
    if not bad and not implemented and not carriers:
        return skip("no entry is `implemented` and none carries `implementedIn` or `tests`, so the "
                    "rules that accompany an implemented claim were not exercised", had_subject=False)
    return verdict(bad, f"{implemented} implemented entries all name their revision and the tests, "
                        f"each with a recorded mutation, that prove them",
                   "an implemented claim is missing its revision or its tests")


def check_decision_records(ctx):
    """A `fate: decision` that names a record means the record exists.

    "Never cite a document you have not written." Paths are resolved against the repository
    root; without one the check reports NOT VERIFIED rather than passing.
    """
    named = [
        (label(e, i), block(e, "ambiguity").get("decision"))
        for i, e in enumerate(entries_of(ctx["map"]))
        if isinstance(e, dict) and fate_of(e) == "decision"
    ]
    if not named:
        return skip("no entry carries `fate: decision`, so no record was named to resolve", had_subject=False)
    root = ctx["repo_root"]
    if root is None or not os.path.isdir(root):
        return skip(f"no repository root ({root!r}) to resolve a decision record path against")
    bad = []
    for name, path in named:
        if not path:
            continue  # reported by `exclusions`
        if not os.path.isfile(os.path.join(root, path)):
            bad.append(f"  X  {name}: names decision record {path!r}, which does not exist under {root}")
    return verdict(bad, f"{len(named)} named decision records all exist", "a decision record does not exist")


def check_conflicts(ctx):
    """`ambiguity.conflict` groups the entries that answer one contradicted question (0007).

    0005 section B required that entries in a conflict settled by decision name the same
    record, and conceded in the same section that nothing linked them. 0007 adds the slug
    and rules that a conflict is a question rather than a pair, so the four rules below are
    the whole of what it claims:

      * the slug lives inside an `ambiguity` block, so only an ambiguous entry is in a
        conflict -- `exclusions` already ties the block to `clarity: ambiguous`;
      * a conflict has at least two members, because a slug carried alone records a
        contradiction with nothing and is what a typo looks like;
      * every member shares a `fate`, because one question is not both settled and declined;
      * where that fate is `decision`, every member names the same record.

    What it cannot do: detect a conflict nobody recorded. Two `clarity: clear` entries
    stating incompatible rules pass every check in this file.
    """
    bad, groups = [], {}
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        slug = block(entry, "ambiguity").get("conflict")
        if slug is None:
            if "conflict" in entry:
                bad.append(f"  X  {name}: carries `conflict` at entry level; it belongs in the "
                           f"`ambiguity` block, because only an ambiguous entry is in a conflict")
            continue
        if not isinstance(slug, str) or not slug.strip():
            bad.append(f"  X  {name}: ambiguity.conflict is {slug!r}, which is not a slug naming a question")
            continue
        groups.setdefault(slug, []).append((name, entry))

    for slug, members in sorted(groups.items()):
        names = [name for name, _ in members]
        if len(members) < 2:
            bad.append(f"  X  {names[0]}: is the only entry in conflict {slug!r}; a conflict is a "
                       f"question the corpus answers twice, so it has at least two members")
            continue
        fates = {fate_of(entry) for _, entry in members}
        if len(fates) > 1:
            bad.append(f"  X  conflict {slug!r} ({', '.join(names)}): members disagree on `fate` "
                       f"({', '.join(sorted(str(f) for f in fates))}); one question is not both "
                       f"settled and declined")
            continue
        if fates == {"decision"}:
            records = {block(entry, "ambiguity").get("decision") for _, entry in members}
            if len(records) > 1:
                bad.append(f"  X  conflict {slug!r} ({', '.join(names)}): members name different "
                           f"decision records ({', '.join(sorted(str(r) for r in records))}); one "
                           f"side can be decided and the other left open")
    if not groups and not bad:
        return skip("no entry carries `ambiguity.conflict`, so no conflict was grouped and the "
                    "rule is vacuous over this map", had_subject=False)
    members = sum(len(m) for m in groups.values())
    return verdict(bad, f"{len(groups)} conflict{'' if len(groups) == 1 else 's'} over {members} "
                        f"entries: each has two or more members, one fate, and one record",
                   "a conflict is not well-formed")


def check_absent(ctx):
    """`absentFrom` says the corpus does not contain the rule at all (0009).

    Three states share one schema and two of them are `scope: out`: read-and-declined, and
    read-and-not-there. `absentFrom` is the discriminator, and everything here follows from
    what it asserts:

      * it is a verdict, so `scope: out` and `status: declined` -- row 1 of the
        correspondence table dominates, and 0008's procedure has `scope: in` as its
        precondition, so an absent rule must never reach the gates;
      * a rule cannot be both nowhere in the corpus and somewhere in it the reader cannot
        reach, so `beyondAdapter` and `definedElsewhere` are excluded;
      * an absent rule has no words, so it cannot be ambiguous about them;
      * nothing can be implemented after a rule that does not exist, so an absent entry
        neither depends on nor gates anything, and nothing names it in either relation.
        That edge would be unsatisfiable forever, which is what `blocked` looks like when
        it will never clear.

    What it cannot do: this file never reads a corpus, so the claim itself -- *the words
    are not there* -- is not tested here. `check-locators.py` searches the text for the
    terms `searched` names and fails when one of them turns up.
    """
    bad, carriers, absent_ids = [], [], set()
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        if "absentFrom" not in entry:
            continue
        carriers.append(name)
        if isinstance(entry.get("id"), str):
            absent_ids.add(entry["id"])
        if not isinstance(entry.get("absentFrom"), dict):
            bad.append(f"  X  {name}: `absentFrom` is not an object")
            continue
        if entry.get("scope") != "out":
            bad.append(f"  X  {name}: carries `absentFrom` while scope is "
                       f"{entry.get('scope')!r}; a rule the corpus does not state is not one "
                       f"the engine covers, and row 1 must dominate")
        if entry.get("status") != "declined":
            bad.append(f"  X  {name}: carries `absentFrom` while status is "
                       f"{entry.get('status')!r}; there is no rule to have built")
        for field in ("beyondAdapter", "definedElsewhere"):
            if field in entry:
                bad.append(f"  X  {name}: carries `absentFrom` and `{field}`; the rule is either "
                           f"nowhere in this corpus or somewhere in it we cannot reach, not both")
        if "ambiguity" in entry:
            bad.append(f"  X  {name}: carries `absentFrom` and an `ambiguity` block; an absent "
                       f"rule has no words to be ambiguous about")
        for field in ID_LIST_FIELDS:
            if entry.get(field):
                bad.append(f"  X  {name}: carries `absentFrom` and a non-empty `{field}`; a rule "
                           f"the corpus does not state orders nothing and gates nothing")

    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        for field in ID_LIST_FIELDS:
            for ref in entry.get(field) or []:
                if isinstance(ref, str) and ref in absent_ids:
                    bad.append(f"  X  {name}: {field} names {ref!r}, which carries `absentFrom`; "
                               f"that edge can never be satisfied")
    if not carriers:
        return skip("no entry carries `absentFrom`, so the rules about an absent rule are "
                    "vacuous over this map", had_subject=False)
    return verdict(bad, f"{len(carriers)} absent-rule entr{'y' if len(carriers) == 1 else 'ies'} "
                        f"({', '.join(sorted(carriers))}): out, declined, carrying nothing that "
                        f"contradicts an absence, and depended on by nothing",
                   "an absent-rule entry claims something else as well")


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


ROW_DESCRIPTIONS = {
    1: "scope: out -> OutsideCurrentScope",
    2: "status mapped/blocked -> UnsupportedRule",
    3: "definedElsewhere -> MissingRulesData",
    4: "beyondAdapter -> MissingRulesData",
    5: "operation with an unimplemented value dependency -> MissingRulesData",
    6: "fate: unresolved -> RequiresInterpretation",
    8: "kind: assertion -> nothing; the engine demands the value",
}


def matched_rows(entry, by_id):
    """Every correspondence row whose predicate holds, ignoring precedence.

    Row 7 is absent: "two implemented entries with no entry for their combination" is a
    fact about a pair and about an interaction the map does not enumerate.
    """
    rows = []
    if entry.get("scope") == "out":
        rows.append(1)
    if entry.get("status") in ("mapped", "blocked"):
        rows.append(2)
    if "definedElsewhere" in entry:
        rows.append(3)
    if "beyondAdapter" in entry:
        rows.append(4)
    if entry.get("kind") == "operation":
        for dep in entry.get("dependsOn") or []:
            target = by_id.get(dep) if isinstance(dep, str) else None
            if isinstance(target, dict) and target.get("kind") == "value" and target.get("status") != "implemented":
                rows.append(5)
                break
    if fate_of(entry) == "unresolved":
        rows.append(6)
    if entry.get("kind") == "assertion":
        rows.append(8)
    return rows


def check_correspondence(ctx):
    """Every entry is reachable by some correspondence row, or is a plain computable rule.

    Rows are checked in order and the first match wins, so matching two is not itself an
    error -- 0005 notes that `status: mapped` with `fate: unresolved` matches rows 2 and 6
    on eleven entries today and is exactly what precedence is for. What is reported:

      * an entry matching no row at all. A failure when `status: declined`, which claims no
        implemented path and therefore owes a runtime reason; informational otherwise,
        because a built clear rule matches no row by design.
      * two specific unordered overlaps that precedence hides but that are data errors:
        `definedElsewhere` together with `beyondAdapter` (rows 3 and 4 both fire with the
        same runtime reason from contradictory evidence), and a `kind: assertion` that also
        declines (row 8 says an assertion is a parameter, not a failure to resolve).
    """
    by_id, bad, notes, matched = index(ctx["map"]), [], [], 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        rows = matched_rows(entry, by_id)
        if rows:
            matched += 1
            first = rows[0]
            notes.append(f"  .  {name}: row {first} ({ROW_DESCRIPTIONS[first]})")
        elif entry.get("status") == "declined":
            bad.append(f"  X  {name}: status is `declined` -- no implemented path at all -- and no "
                       f"correspondence row says what the engine returns instead")
        else:
            notes.append(f"  .  {name}: matches no row; the engine answers it (status "
                         f"{entry.get('status')!r}, clarity {entry.get('clarity')!r})")
        if 3 in rows and 4 in rows:
            bad.append(f"  X  {name}: carries both `definedElsewhere` and `beyondAdapter`; the rule is "
                       f"either here and unreadable or defined in a corpus not admitted, not both")
        if 8 in rows and (3 in rows or 4 in rows or 6 in rows):
            others = [r for r in rows if r in (3, 4, 6)]
            bad.append(f"  X  {name}: is `kind: assertion` and also matches row(s) {others}; an assertion "
                       f"is a parameter the engine demands, not a decline")
    total = len([e for e in entries_of(ctx["map"]) if isinstance(e, dict)])
    if not total:
        return skip("there are no entries to place in the table")
    result = verdict(bad, f"{matched} of {total} entries match a row; the rest are plainly computable "
                          f"(row 7 is not evaluated)",
                     "an entry cannot be placed in the correspondence table")
    if ctx["verbose"]:
        result.details = result.details + notes
    return result


# --- where each check runs (0015) ------------------------------------------------------
#
# A map is published as a package, and a map that fails any check here never becomes a
# version (`--phase publish`, the default, runs every check). The engine consuming it does
# not re-run them: the package's bytes are what passed. What it does run is the subset whose
# verdict its own overlay can change. An overlay sets exactly OVERLAY_FIELDS on the entries it
# names and nothing else (0015, from #17), so a check that reads none of them is discharged at
# publish, and a check that reads any of them is re-run by the consumer against
# merge(package, overlay) with `--phase consumer`.
#
# The split is read from here, not maintained beside it. `test_check_map.py` holds it to its
# word both ways: every check outside STATUS_DEPENDENT gives the same verdict whatever the
# overlay fields hold, and every check inside it can be turned by them.

OVERLAY_FIELDS = ("status", "implementedIn", "tests")

STATUS_DEPENDENT = {
    "vocabulary",      # `status` is one of the closed vocabularies
    "status",          # implementedIn exactly when implemented; tests, each with its mutation
    "absent",          # an absentFrom entry is `status: declined`
    "correspondence",  # rows 2 and 5 branch on status; `declined` owes a runtime row
}

PHASES = ("publish", "consumer")


CHECKS = [
    ("schema", check_schema),
    ("required-fields", check_required_fields),
    ("vocabulary", check_vocabulary),
    ("unique-ids", check_unique_ids),
    ("references", check_references),
    ("no-cycles", check_no_cycles),
    ("gates", check_gates),
    ("derived", check_derived),
    ("manifest", check_manifest),
    ("postures", check_postures),
    ("exclusions", check_exclusions),
    ("status", check_status),
    ("decision-records", check_decision_records),
    ("conflicts", check_conflicts),
    ("absent", check_absent),
    ("cross-references", check_cross_references),
    ("correspondence", check_correspondence),
]


# --- driver --------------------------------------------------------------------------


def find_manifest(map_path):
    """The manifest beside the map, when there is exactly one candidate."""
    directory = os.path.dirname(os.path.abspath(map_path)) or "."
    candidates = sorted(
        os.path.join(directory, n)
        for n in os.listdir(directory)
        if n.startswith("corpus-manifest") and n.endswith(".json")
    )
    return candidates[0] if len(candidates) == 1 else None


def find_repo_root(start):
    directory = os.path.dirname(os.path.abspath(start))
    while True:
        if os.path.isdir(os.path.join(directory, "docs", "decisions")) or os.path.isdir(os.path.join(directory, ".git")):
            return directory
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a corpus map against docs/corpus-map.md.")
    parser.add_argument("map_path")
    parser.add_argument("--manifest", help="corpus manifest; found beside the map when unambiguous")
    parser.add_argument("--repo-root", help="root that decision-record paths are relative to")
    parser.add_argument("--only", help="run one check: " + ", ".join(name for name, _ in CHECKS))
    parser.add_argument("--verbose", action="store_true", help="also print the row each entry matches")
    parser.add_argument("--phase", choices=PHASES, default="publish",
                        help="publish (default): every check, before a map may become a version. "
                             "consumer: only the checks an overlay of " + ", ".join(OVERLAY_FIELDS)
                             + " can change, run by an engine on merge(package, overlay) (0015)")
    args = parser.parse_args(argv)

    selected = CHECKS
    if args.phase == "consumer":
        selected = [c for c in CHECKS if c[0] in STATUS_DEPENDENT]
    if args.only:
        selected = [c for c in CHECKS if c[0] == args.only]
        if not selected:
            print(f"unknown check {args.only!r}; known: {', '.join(n for n, _ in CHECKS)}", file=sys.stderr)
            return 2
    try:
        with open(args.map_path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        print(f"cannot read map {args.map_path}: {error}", file=sys.stderr)
        return 2

    manifest_path = args.manifest or find_manifest(args.map_path)
    manifest = None
    if manifest_path:
        try:
            with open(manifest_path, encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (OSError, ValueError) as error:
            print(f"cannot read manifest {manifest_path}: {error}", file=sys.stderr)
            return 2

    ctx = {
        "map": document,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "repo_root": args.repo_root or find_repo_root(args.map_path),
        "verbose": args.verbose,
    }

    print(f"{args.map_path} ({len(entries_of(document))} entries"
          + (f", manifest {os.path.basename(manifest_path)}" if manifest_path else ", no manifest") + ")")
    failed = skipped = passed = fatal = 0
    for name, check in selected:
        try:
            result = check(ctx)
        except Exception as error:  # a check that crashes has proved nothing
            result = skip(f"the check raised {type(error).__name__}: {error}")
        print(f"[{result.status}] {name}: {result.summary}")
        for line in result.details:
            print(line)
        if result.status == "fail":
            failed += 1
        elif result.status == "skip":
            skipped += 1
        else:
            passed += 1
        if result.fatal:
            fatal += 1

    print(f"\n{passed} ok, {failed} failed, {skipped} not verified")
    if fatal:
        return 1
    if not passed:
        # Nothing failed and nothing passed: every check declined to prove anything.
        print("nothing was actually checked; this is not a pass", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
