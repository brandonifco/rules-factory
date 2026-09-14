"""The map's closed vocabularies and the helpers every check uses to read an entry.

Nothing here judges anything. The helpers tolerate a malformed map -- a missing block reads as
empty, a non-list `entries` as no entries -- so that each check reports the malformation it
owns and no check crashes on one another check owns.
"""


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
