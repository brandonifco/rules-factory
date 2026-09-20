"""The map's closed vocabularies, and the field names whose meaning the spec fixes.

Closed is the point: `kind: "rule"` shipped in both copies of the backgammon map because
nothing held a value to a set. A value absent from a set here is not a value of the map.
"""


# The `schemaVersion`s this contract describes. A map in any other version is not one these
# names describe, so validation fails it rather than checking fields whose meaning may have
# moved; and the factory refuses to intake it (0016), reading this set rather than keeping
# its own.
SCHEMA_VERSIONS = (1,)

# The map's top-level fields, and all of them (#60). The manifest is not among them: it is a
# separate file. `extent` is optional; `schema` requires the other four.
MAP_FIELDS = ("schemaVersion", "corpus", "baseline", "extent", "entries")

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
# What only a passage can carry, and so what a derived entry may not. `defines` is among them
# for the reason `crossReferences` is: a definition is anchored in the passage that makes it
# (0045), and a derived entry quotes no passage. `continuesDefinition` is anchored twice: by
# this passage and by its structural witness to the directly defining passage (0046).
PASSAGE_FIELDS = CITING_FIELDS + ("crossReferences", "defines", "continuesDefinition",
                                  "absentFrom", "beyondAdapter", "definedElsewhere", "extraction")
# The two halves of one `defines` item, and both of them: the vocabulary the term belongs to, and
# the term as the corpus prints it (0045). Exactly these, because an item with a third key is one
# whose author expected something to read it.
DEFINES_FIELDS = ("vocabulary", "term")
# A continuation writes neither vocabulary nor term. It names the directly defining entry and a
# second locator that mechanically witnesses the structural relationship (0046). Unknown keys are
# refused rather than ignored, so metadata cannot look operative while no reader consumes it.
CONTINUES_DEFINITION_FIELDS = ("definedBy", "anchor")
DEFINITION_ANCHOR_FIELDS = ("sourceId", "citation")
# The relations that hold entry ids and nothing else. `gatedBy` is not among them: 0011 split
# it into the two gate fields, and `gates` refuses it by name.
GATE_FIELDS = ("enabledBy", "suspendedBy")
ID_LIST_FIELDS = ("dependsOn",) + GATE_FIELDS
