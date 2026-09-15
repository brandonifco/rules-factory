# 0020 — A section citation can name its lead-in, and a section-designation map lists its extent

## Status

Accepted — 2026-09-14. Records the decisions on
[#58](https://github.com/brandonifco/rules-factory/issues/58),
[#59](https://github.com/brandonifco/rules-factory/issues/59),
[#60](https://github.com/brandonifco/rules-factory/issues/60) and
[#62](https://github.com/brandonifco/rules-factory/issues/62), four schema points the Part 107
blind second mapping ([0014](0014-a-map-is-checked-by-a-blind-second-mapping.md),
[`blind-mapping/`](../../examples/faa-part-107/blind-mapping/README.md)) reported as unclear.
**Extends [0009](0009-absence-is-a-verdict-with-evidence.md)**: `extent` gets its second unit.
The specification is [corpus-map.md](../corpus-map.md); this record says what was chosen and why.

## Context

The blind mapper read the same documents as every mapper and had to invent four answers:

- **`extent`** was specified only as a page range. A `section-designation` corpus "needs the
  paragraph-path equivalent and does not have one", so the Part 107 map declared no extent and
  "outside this map's slice" in its `unmapped` reasons was prose. The blind map invented
  `{unit: section-designation, sections: [...]}`.
- **A section's lead-in** had no citation. The reference map cited § 107.51's undesignated
  opening sentence as `§ 107.51`, which the checker verified as "somewhere in § 107.51". The
  blind map wrote `§ 107.51 introductory text`, which the checker did not read: 5 of its 54
  entries went unchecked.
- **The manifest** was described as part of the map ("a list of entries … plus the manifest").
  The blind map put it inline; `check-map.py` reported "no manifest" and skipped every
  resolution against it, silently.
- **A pointer to an unadmitted corpus** — "defined in 49 CFR 171.8", "as defined in the Air
  Almanac" — was answered by `definedElsewhere` in the reference map, and by `definedElsewhere`
  *and* an `unmapped` `crossReferences` item in the blind map. Both passed. The resolution
  record left the two flags pending this.

## Decision

1. **A `section-designation` extent is a list of sections.**
   `{ "unit": "section-designation", "sections": ["§ 107.25", ...] }`, each item a bare section.
   `check-map.py --only extent` checks the shape of both units and refuses a `scope: in` entry
   whose locator cites outside the list (a section not listed, or a whole subpart), reading the
   citation with the locator checker's own expressions. A `scope: out` entry may cite beyond
   the extent, because recording what lies beyond the slice is what an out-of-scope entry is
   for; the check names it in its summary and neither passes nor fails it.
   `check-locators-section.py` gains `coverage`: every listed section is reached by a verified
   quote, and a map with no extent fails, as `check-locators.py` already does for pages. The
   Part 107 map and the 2020 temporal map declare the twelve subpart B sections they read.
2. **"Introductory text" is part of the locator grammar.** `§ 107.51 introductory text` names the
   section's undesignated lead-in and nothing else, alone or as a list item
   (`§ 107.33 introductory text, (a)`). The checker requires every occurrence of the quote to lie
   before the section's first designated paragraph. A section with no designated paragraph has
   none. The bare section stays valid. Only an entry quoting the lead-in alone switches to the
   explicit form; in the Part 107 maps that is `operating-limitations`.
3. **The manifest is a separate file.** The map's top-level fields are `schemaVersion`, `corpus`,
   `baseline`, `extent` and `entries`, and `check-map.py --only schema` refuses any other,
   `manifest` by name.
4. **`definedElsewhere` answers a pointer to a corpus that was not admitted.** A
   `crossReferences` item naming the same reference is refused by
   `check-map.py --only cross-references`.

## Alternatives considered

**A range of sections, `{from: "§ 107.25", to: "§ 107.51"}`.** Rejected. The slice skips
§§ 107.27, .43 and .47, so a range claims three sections nobody read, which is the understated
claim `extent` exists to prevent — in the other direction.

**A subpart, `{subpart: "B"}`.** Rejected for the same reason: subpart B has more sections than
the twelve.

**Derive the extent from the citations.** Rejected by 0009 already: a map could then shrink its
extent to what it happened to quote.

**Leave the lead-in to the bare section.** Rejected. A bare citation is true of a lead-in quote
and of any other quote in the section, so it says less than the mapper knows, and a map cannot be
held to a distinction it cannot write. The alternative spelling, `§ 107.51 (lead-in)`, is not the
CFR's; "introductory text" is what the Federal Register uses when it amends one.

**Allow an inline manifest.** Rejected. Every map ships its manifest as a file, the package
carries the two separately (0015), and a second place to declare corpora is a second place for
them to disagree.

**Require `crossReferences` to repeat the `definedElsewhere` pointer.** Rejected. The item could
only be `unmapped`, its reason could only restate the field, and 0005 ruled that a field earns its
place by being checkable; a prose restatement of a checked field is not.

## Consequences

**The Part 107 map's bytes change, and its review is an exemption.** The extent is added and one
citation names the same paragraph more precisely; no entry's meaning moves. `review.json` records
`non-semantic` against the blind-mapped digest and keeps that review as `previousReview`. The 2020
map keeps its `legacy` exemption with the new digest: `non-semantic` names a reviewed map it
departs from, and that map has none. The 0017 table describes the maps as they were then.

**An out-of-scope entry is how a map records what lies beyond its extent.**
`subpart-d-categories` cites `subpart D` and quotes § 107.100, outside the twelve sections; it is
`scope: out`, so it is reported and passes. #61's waiver entries citing §§ 107.200 and 107.205
will be too. The cost: an out-of-scope entry's citation is not bounded by the extent, so a typo
in one (`§ 107.52` for `§ 107.51`) is reported rather than refused, and the locator checker is
what catches it.

**The grammar lives in two files.** `check-map.py` is standard-library and ships alone (0015), so
it cannot import the section checker. It copies the two expressions it needs, and
`test_check_map.py` requires both to read every Part 107 citation the same way.

**The duplicate check recognises a reference by its name, not its meaning.** It matches the
designation in the manifest reference's `citation` or the `sourceId` read as words. A reference
declared with neither, or an item naming it in other words, passes.
