"""The shape of the map itself: its envelope, each entry's required fields, the closed
vocabularies, and distinct ids. What the spec states field by field, before any relation.
"""
from .diagnostics import fail, verdict
from .model import (CITING_FIELDS, CLARITIES, FATES, ID_LIST_FIELDS, KINDS, MAP_FIELDS,
                    REQUIRED_ENTRY_FIELDS, SCHEMA_VERSIONS, SCOPES, STATUSES, UNRESOLVED_REASONS, block,
                    entries_of, label, quotes_withheld)


def check_schema(ctx):
    """The map's own envelope: the stamp naming the baseline it was built against.

    The envelope is closed. A top-level key outside MAP_FIELDS is refused rather than ignored:
    the Part 107 blind mapper put its manifest inline as `manifest`, and this checker, which
    reads the manifest from a separate file, reported "no manifest" and skipped every
    resolution against it while the key sat there unread (#60).
    """
    doc, bad = ctx["map"], []
    if not isinstance(doc, dict):
        return fail(["  X  top level is not an object"], "the map is not an object")
    for field in doc:
        if field == "manifest":
            bad.append("  X  map carries `manifest` inline; the manifest is a separate file, "
                       "corpus-manifest*.json beside the map or --manifest, and an inline one is "
                       "never read")
        elif field not in MAP_FIELDS:
            bad.append(f"  X  map has top-level `{field}`, which is not a field of a map "
                       f"({', '.join(MAP_FIELDS)}); an unknown field is refused, never ignored")
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
