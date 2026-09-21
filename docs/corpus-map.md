# The corpus map

The interface between reading a corpus and building an engine from it. Everything in
[method.md](method.md) phases 1–4 produces it; everything in phases 5–8 consumes it.

A map is a list of entries, one per rule the corpus states, plus a stamp naming the baseline it
was built against and the extent it claims to have read. The corpora its entries cite are
declared in a **separate file**, the [corpus manifest](#the-corpus-manifest)
(`corpus-manifest*.json` beside the map, or `check-map.py --manifest`), never inside the map:

```json
{ "schemaVersion": 1, "corpus": "cfr-14-107",
  "baseline": { "contentHash": "80f6bc4b…", "hashDerivation": "ecfr-versioner-xml",
                "asOf": "2026-01-01" },
  "extent": { "unit": "section-designation", "sections": ["§ 107.25", "§ 107.29", "…"] },
  "entries": [ … ] }
```

**Those five are the map's top-level fields, and there are no others.** `check-map.py --only
schema` refuses any other key, and names an inline `manifest` in particular: the Part 107 blind
mapper put one there, and the checker, which reads the manifest from its own file, reported
"no manifest" and skipped every resolution against it while the key sat unread
([#60](https://github.com/brandonifco/rules-factory/issues/60)). A field a checker ignores is a
claim nothing checks.

The stamp is not decoration. It fixes **one state of the corpus it names**. Without it, two
maps cannot be compared, a map cannot be checked against the text it claims to describe, and
it silently outlives that text. The third trial's differ printed `2020-01-01 -> ?` for
exactly this reason.

**The stamp covers the principal corpus, and a map may depend on more than one.** `corpus` and
`baseline` name the map's **principal** corpus and pin its bytes. An entry's `locator.sourceId`
need only be declared in the manifest, so a map whose rules cross two served documents — trial
10's, where a code printed in § 172.101's table is stated in § 172.102 — cites both, and the
manifest pins both. A served-document boundary is a delivery artifact, and
[0039](decisions/0039-the-manifest-pins-every-corpus-a-map-cites.md) declines to let it split one
mapping problem into two maps. Packaging and factory intake independently re-hash **every** cited
corpus under the one canonical hashDerivation implementation. Packaging runs citation checks on an
immutable snapshot of those exact bytes and records their identities in map/verification.json;
intake requires its resolved corpus bytes to re-derive to those same identities before accepting
the package ([0048](decisions/0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md)).
The engine carries them all and records them all in provenance; nothing else turns on which corpus
occupies the envelope's field.

## `extent` — how much of the corpus this map claims to have read

The baseline says *which text*. `extent` says *how much of it*, in the corpus's own units.
Added in [0009](decisions/0009-absence-is-a-verdict-with-evidence.md).

It is the field that makes "no entry anywhere cites this section" a **fact** rather than a
hope: `check-locators.py`'s `coverage` check names every page inside the extent that no
entry's located evidence reaches. A page nobody quoted is a page nobody demonstrably read, and that is
the state — *nobody looked* — a map exists to distinguish from a recorded verdict. It also
bounds an absence claim: see `absentFrom` below.

`coverage` asks that at the grain of a whole page or a whole section, which a map satisfies by
reaching one sentence. [`mapper inventory`](mapper.md#the-inventory) asks it at the grain the
corpus states rules in: it enumerates the units inside the extent and reports the ones no quote
reaches and no recorded rejection accounts for
([#255](https://github.com/brandonifco/rules-factory/issues/255)).

`coverage` also reports **how much of the extent the map can show it quoted** — the union of its
verified quotes' spans over the extent's own length, printed on every run
([0055](decisions/0055-coverage-reports-how-much-of-the-extent-is-quoted-and-a-map-declares-the-floor.md),
[#270](https://github.com/brandonifco/rules-factory/issues/270)). Because one quote reaches a
page, counting units reached could not see an entry deleted from a map whose other entries still
reach its page; the fraction can. A map may name the floor it claims, `"quoted": 0.8`, and
`coverage` fails a map that quotes less than it declared. A map that declares none is measured,
printed and not failed: across the committed maps the fraction runs from 19% to 100%, so no
single threshold could be honest about all of them.

It is a property of the **map**, not of the corpus, and so it does not belong in the manifest.
`contentHash` and `licence` are true of the text whoever reads it; how far a mapper got is
true of one mapping.

**What it does not buy.** Nothing sizes it. A map declaring one page of a four-hundred-page
book covers that page and passes, and `quoted` above is a floor the map chooses for itself. The
field buys that the claim is written down and can be
argued with — and that a map cannot quietly shrink its own extent to match what it happened to
read, which deriving the extent from the citations would have allowed: the backgammon
citations run 271–277, and the throw enumeration that #20 is about is on 278–280.

**Two units, one per locator grammar.** Decided in
[0020](decisions/0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)
([#58](https://github.com/brandonifco/rules-factory/issues/58)).

```json
"extent": { "unit": "page", "from": 271, "to": 280 }
"extent": { "unit": "page", "from": 13, "to": 16, "endsBefore": "Damage and Healing" }
"extent": { "unit": "section-designation", "sections": ["§ 107.25", "§ 107.29", "§ 107.31"] }
```

- **`page`** — a range of printed pages, `from` ≤ `to`, for a corpus with page markers in its
  text. `check-locators.py`'s `coverage` names every page in it no verified quote reaches.
  `check-map.py --only extent` refuses **any `scope: in` entry whose locator cites a page
  outside the range** ([#269](https://github.com/brandonifco/rules-factory/issues/269)), exactly
  as it does for a section designation below, and `extent-bounds` in both page checkers refuses
  an in-scope *quote* that lies outside it — a map may cite fewer pages than it declares, and
  then only the quote notices a narrowing.
  **It may end before a heading on its last page**, `"endsBefore": "Damage and Healing"`
  ([0024](decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md),
  [#114](https://github.com/brandonifco/rules-factory/issues/114)): the SRD combat chapter ends
  halfway down p. 16, and a whole-page range claims the section after it. `check-map.py` checks
  that it is one line of text. `check-locators-pdf-text.py`'s `extent-end` requires the heading
  to occur exactly once as a line on page `to` and fails any `scope: in` quote on that page at or
  after it, or running across it. `absence` searches only up to the heading, and a quote after it
  does not reach the page for `coverage`. "After" is in the extraction's reading order.
  `check-locators.py` collapses lines, cannot find the heading, and reports such an extent NOT
  VERIFIED. There is no `startsAfter`; no map has needed one.
- **`section-designation`** — a **list** of sections, each a bare designation (`§ 107.25`, never
  `§ 107.25(a)`), for a corpus cited by section. A list and not a range, because what a mapper
  reads of a CFR part is not contiguous: the Part 107 slice is twelve sections of subpart B and
  skips § 107.27, .43 and .47 between them, and a range would claim them. Not a subpart, for the
  same reason. `check-map.py --only extent` refuses a malformed list and **any `scope: in`
  entry whose locator cites outside it**, a section not listed or a whole subpart; the citation
  is parsed by the locator grammar below. `check-locators-section.py`'s `coverage` names every
  listed section no verified quote reaches.

**A section-designation extent that reads a table says which rows it took.** Decided in
[0035](decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)
([#280](https://github.com/brandonifco/rules-factory/issues/280)).

```json
"extent": {
  "unit": "section-designation",
  "sections": ["§ 172.101", "§ 172.102"],
  "tables": [
    { "section": "§ 172.101", "table": 3, "rows": [ { "column": 2, "is": "Acetal" } ] },
    { "section": "§ 172.101", "table": 1,
      "excluded": "label substitution; no mapped row invokes it" }
  ]
}
```

Each item names a table by its position in the section, counted from 1, and carries either `rows`
— a list of row keys, or `"all"` — or `excluded` with a reason, never both and never neither. A
row key is one `{"column": 2, "is": "Acetal"}` object, or a list of them read as a conjunction,
and it is the same key the row's citation names (below). A nested table is a table of its section
in its own right, listed separately: its rows are its own. **Every table printed inside a cited
section appears in the list**: a map may not quietly shrink its extent to whatever it happened to
read, which is the rule the section list itself already carries, one unit down. `check-map.py
--only extent` checks the shape and refuses an in-scope entry citing a row the slice did not take;
which tables a section prints needs the corpus, and the `ecfr-xml` adapter refuses one the extent
passes over in silence ([mapper.md](mapper.md#the-adapter-interface)).

`check-map.py` checks each unit's shape and refuses a unit outside the two. A map with no extent
passes `check-map.py` and fails both locator checkers, which are where what was read can be
compared with the text.

**A section-designation extent declares the passages its grammar cannot address.** Decided in
[0038](decisions/0038-a-map-declares-the-passages-its-grammar-cannot-address.md)
([#299](https://github.com/brandonifco/rules-factory/issues/299)).

```json
"extent": {
  "unit": "section-designation",
  "sections": ["§ 172.101", "§ 172.102"],
  "unreachable": [
    { "sourceId": "cfr-49-172.101",
      "opensWith": "Appendix A to § 172.101—List of Hazardous Substances and Rep",
      "reason": "division-wrapper",
      "requires": "a citation grammar for a section's appendices; 0036 refuses a wrapper holding an HD1" }
  ]
}
```

This is a **positive statement, not an exclusion**. The extent still names § 172.101 whole and
every in-scope entry is still held to it; `unreachable` says that a passage of the corpus exists
which *nothing could cite*, and what addressing it would take. An exclusion would delete the
uncertainty; a declaration carries it where a reader can see it, which is what 0009 does for an
absence and 0034 for an unsettled reading. Optional, and a list with nothing in it is refused:
an empty list says nothing a missing field does not.

- **`sourceId`** names the corpus, because a map may cite several and reachability is a property
  of one document under one grammar.
- **`opensWith`** is the passage's opening as the walk reports it — the first 60 characters of its
  normalised text — an identity rather than a quotation, stable because the corpus is pinned by
  `contentHash`. A prefix the walk refuses twice is refused, never matched to the first
  declaration, the rule a duplicate row key already gets (0035).
- **`reason`** is closed to what the walk emits: `ambiguous-designator`,
  `captioned-after-undesignated`, `division-wrapper`, `example-head-unreadable`,
  `no-unit-for-element`, `note-heading-elsewhere`, `note-heading-unreadable`,
  `states-own-designation`. The authority is `check-locators-section.py`'s `UNREACHABLE_REASONS`,
  and the vocabulary is of **reasons, not of tests**: `division-wrapper` is given by each of the
  three things that say a wrapper opens a division (0036, 0056), because what a map declares is
  that no citation reaches the passage and what reaching it would take, and those are the same
  whichever signal saw it. `test_unreachable_declaration.py` holds `check-map.py`'s copy equal to
  it, so a map cannot declare a reason no run can give.
- **`requires`** is a sentence saying what reaching the passage would take, and may not be empty.

`check-map.py --only extent` checks the shape. **That the declaration is true of the corpus is the
locator run's**, in both directions: a passage with no address the map does not declare fails, as
it always did, and a passage the map declares which the walk *reaches* fails too — a declaration
the corpus no longer supports is not a bound on the map. Only a run of the walk knows what it
refused, which is 0034's rule that such a state is established rather than asserted.

Only the `section-designation` grammar has the field. The page grammars refuse no passage today,
and nothing is added to them before a corpus forces it
([#265](https://github.com/brandonifco/rules-factory/issues/265)).

**A `scope: out` entry may cite beyond the extent.** Recording what lies beyond the slice is what
an out-of-scope entry is for: Part 107's `subpart-d-categories` cites `subpart D` and quotes
§ 107.100 to decline the subpart an in-scope rule defers to. `check-map.py` names each such entry
in its summary as an out-of-scope citation beyond the extent, and neither passes nor fails it. An
in-scope rule is cited inside what the map claims to have read, or the check fails.

**What the section list does not buy.** Nothing sizes it, exactly as nothing sizes a page range.

### Citing a section in the `section-designation` grammar

A citation names a section and, optionally, what inside it the quote sits in:

| citation | names |
|---|---|
| `§ 107.35` | the whole section |
| `§ 107.51 introductory text` | the section's undesignated lead-in, **and nothing under it** |
| `§ 107.51(a)` | a paragraph and everything under it |
| `§ 107.29(c)(1)-(2)`, `§ 107.51(c)-(d)` | a range at one level |
| `§ 107.29(a)(2), (b)`, `§ 107.33 introductory text, (a)` | a list, each item read against the section |
| `subpart D` | every section of a subpart |
| `§ 172.101 table 3, row [column 2 = "Acetal"]` | one row of one table of the section |
| `§ 172.101 table 3, row [column 2 = "Acetal"], column 7` | one cell of that row |
| `§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]` | a row the corpus leaves blank in the column that names the row above it |

**"Introductory text" is part of the grammar**
([#59](https://github.com/brandonifco/rules-factory/issues/59), 0020). A CFR section often opens
with an undesignated sentence before paragraph (a) — § 107.51's *"A remote pilot in command and
the person manipulating the flight controls … must comply with all of the following operating
limitations"*. The bare section covers that sentence, and covers everything else in the section
too; `§ 107.51 introductory text` says the quote is the lead-in, and
`check-locators-section.py` holds it to that: **every occurrence of the quote lies before the
section's first designated paragraph**, or the entry fails. The phrase is the CFR's own. A
section with no designated paragraph has no introductory text, and citing one fails: cite the
section. A paragraph's own introductory text (`§ 107.29(a) introductory text`) is not in the
grammar and is reported unchecked.

**A row of a table has an address, and it is a cell that identifies it**
([#280](https://github.com/brandonifco/rules-factory/issues/280),
[0035](decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)). Until then the
checker indexed a section's `<P>` and `<EXAMPLE>` children and nothing else, which is **6.6%** of
§ 172.101 — the other 420,000 characters are one table
([#261](https://github.com/brandonifco/rules-factory/issues/261)).

- The **table** is named by its position in the section, counted from 1 in document order. Its
  caption, where it has one, goes in the entry's `note`.
- The **row** is named by `column = value` pairs, separated by `;` inside the brackets, in the
  corpus's own column numbering — the numbering the table's headings print, `9A` and `10B`
  included, and read wherever the heading prints them — the corpus writes a parent as a prefix,
  `(8)Packaging(§ 173.***)`, and its children as suffixes, `Exceptions(8A)`. A two-level heading
  is expanded into a grid (`colspan` widens a cell, `rowspan` carries it down) and a column's
  label is the bottom-most heading cell covering it; a heading split into sub-columns names no
  column of its own, and split means the label plus letters, so `10A` is a sub-column of `10` and
  `1` is a sub-column of nothing. Two things are **refused**, because they leave a body cell's
  column undetermined: a cell of a body row carried into the row below, and leaf labels that do
  not number the body's cells one for one. Such a table addresses nothing, and a map that does not
  read it excludes it in `extent.tables` with a reason. A row that spans *part* of its width is
  unaddressable on its own — no key names it — while a row that is one cell across the whole
  width, the footnote row a regulation ends a table with, is a row like any other. Every other way
  a printed numbering can fail — a heading naming two columns, a table numbered only in part, a
  numbering that does not begin at `(1)`, a label printed twice — falls back to numbering **by
  position**, and the run says which numbering it used and why. The pairs are a conjunction and their order does not matter. **Exactly one row must
  match**: two is a refusal, not a first hit, and the answer is a discriminating column —
  `row [column 2 = "Ammonia, anhydrous"; column 1 = "I"]`. A row's position is never part of the
  key, because an amendment moves it and a key that stops resolving is better than one that
  silently names a different material.
- A **cell** is named by `, column 7` after the row. The quote is then held to that cell; without
  it, to the row.
- **The row is the extraction, and `evidence` is one contiguous verbatim span of it**: the cells
  in column order joined by ` | `, with the empty cells kept as empty, so a blank cell is
  quotable. 1,112 rows of § 172.101 have exactly one empty cell and 419 have thirteen; flattened
  into prose, a missing column 1 symbol and a missing column 5 packing group are the same
  absence. **Contiguous is held strictly here**: an ellipsis inside a row quote elides a column,
  and the checker refuses it rather than checking the halves.
- **A heading row is a row**, and citable like any other: `row [column 1 = "(1)Symbols"]`. The
  column semantics of a regulation live in its headings, and this corpus prints them once for
  3,687 rows.

**A row the corpus leaves blank in a column an earlier row fills is addressed relative to that
earlier row** ([#310](https://github.com/brandonifco/rules-factory/issues/310),
[0043](decisions/0043-a-row-blank-in-the-column-that-names-the-row-above-is-named-below-it.md)).
§ 172.102 table 2 states `IB2` in two rows — the authorised IBCs, then an `Additional Requirement`
whose code cell is blank — and that second row is **byte-identical** to `IB1`'s, so no
`column = value` key names either and the table could not be taken whole at all. 258 rows of
§ 172.101's Hazardous Materials Table are in the same position.

```
§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]
§ 172.101 table 3, row blank in column 2 [column 5 = "II"] below row [column 2 = "Adhesives, containing a flammable liquid"]
```

- The **anchor** is named by an ordinary row key and must resolve to **exactly one row**, as any
  row key must. Both halves of the address are the grammar above; **no ordinal and no occurrence
  selector**, because an amendment repoints one silently and 0035 refused it for that reason.
- The **run** is the rows immediately after the anchor whose cell in the named column is blank. It
  ends at the first row that fills it, and at the first row of another width or one spanning part
  of it — such a row has no cell in that column to be blank.
- **Exactly one row must resolve.** An empty run is refused, and two matches are answered with an
  ordinary `column = value` **discriminator** written before `below`, never with the first hit. So
  a deleted target, a second blank row inserted under the same anchor, a renamed anchor and an
  anchor printed twice each make the citation stop resolving rather than resolve to something else.
- Where a row leaves several columns blank, the column is the one whose anchor is **nearest above**,
  then the one whose **run is shortest**, then the table's own order. § 172.101's Symbols column is
  blank on 3,139 of 3,689 rows, and column order alone addresses *Adhesives* PG II as
  `blank in column 1 below row [column 2 = "Acetaldehyde ammonia"]` — unique, stable, and naming a
  material twenty rows away.
- **The locator claims nothing about meaning.** It says the row leaves a column blank and sits
  below the anchor; whether it *continues* the anchor is a reading, and readings live in entries.
  That is why the grammar says `blank in column` and not `continuation of`.
- An ordinary row key is tried first and is the better address where there is one. Such a row is
  inside an extent that takes its table **whole**: no declared row key names it, so
  `extent.tables[].rows` cannot list it, and `check-map.py --only extent` says so.

**A paragraph the corpus prints inside a wrapper is named by the designation the wrapper
continues, or by nothing at all**
([#285](https://github.com/brandonifco/rules-factory/issues/285),
[0036](decisions/0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md)).
§ 172.102 states its special provisions as ordinary paragraphs inside an `<EXTRACT>` — a block set
off from the running text, beside the designated paragraph that introduces the run — and the
checker walked only a section's direct children, so `A3`, `B2`, `N40`, `TP1` and `148` were in no
index at all. They are now at `§ 172.102(c)(2)`, `(c)(3)`, `(c)(5)`, `(c)(8)(ii)` and `(c)(1)`,
with every other provision of their run.

- **Nothing was added to the grammar above.** What distinguishes one provision of a run from
  another is the quote, which is held to its citation at every occurrence, exactly as it already
  was for two paragraphs that print the same sentence
  ([0030](decisions/0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md)).
- The wrappers are a **closed set** — `EXTRACT` and `NOTE` — descended into to **any depth**, and
  the descent **loses nothing**: every text-bearing element it reaches is either indexed or
  reported unplaced with a reason. A table's wrapper is the one exception, because a table is
  cited by its rows, above.
- A wrapper is printed *after* a paragraph, and the markup does not say it is *inside* it. Three
  things say it is not, asked of **every** wrapper at every depth, and each leaves that wrapper
  **unplaced** — in no index, named by no citation, and reported by the run with its reason:
  it **opens a division of the section** (it holds a heading at the level directly below the
  section, it is captioned and follows no designated paragraph, or **its heading names a division
  of the corpus** — § 172.101's two appendices answer all three); an ordinary `<P>` inside it
  **states its own designation**, which the designation it is printed under is not; or it is a
  note whose heading does not name one paragraph it sits in. An address that is confidently wrong
  is worse than none — 0035's posture towards an unreadable table, applied to a designation.
- The third division signal reads the heading's **words**, which the other two deliberately do
  not, and [0056](decisions/0056-a-wrapper-whose-heading-names-a-division-continues-nothing.md)
  records why: an appendix titled `HD2` and printed directly after a designated paragraph defeats
  both structural tests at once and is otherwise indistinguishable from the captioned provision
  runs the rule exists to reach ([#291](https://github.com/brandonifco/rules-factory/issues/291)).
  What is read is an address the corpus states about itself — `Appendix A to § 172.101—…`,
  `Subpart B—…` — which is the reading a note's heading already gets, and not a reading of prose.
- A **note takes the one paragraph it names in its own heading**: § 172.101 prints
  `Note to paragraph (c)(11):` after `(c)(11)(iii)(C)`, and `§ 172.101(c)(11)` is where it is
  cited from. A heading naming several paragraphs, none, or one the note is not printed in is
  refused, exactly as a row key naming two rows is — and so is any heading opening `Note to …`
  that this grammar cannot parse whole, because a note that states an address and is filed where
  it happens to be printed is the reading this rule exists to refuse
  ([#293](https://github.com/brandonifco/rules-factory/issues/293), 0056).
- **A passage with no address is never coverage of itself.** `mapper inventory` counts such a
  unit, reports it on a `no address` line, and fails a map whose entry quotes one: the locator
  run would report that entry unchecked, and the two tools may not disagree about one passage.

**Use it where the quote is the lead-in alone.** Part 107's `operating-limitations` cites
`§ 107.51 introductory text`. Entries that quote the lead-in *together with* designated paragraphs
— `over-human-beings`, `preflight-actions`, `visual-observer-conditions`, both § 107.25 entries —
keep the bare section, which is true of them. So do sections that are one undesignated passage,
§ 107.35, .36, .41 and .45.

## Why it exists

Without it, "drop in a ruleset and let agents build the engine" has no interface. An agent
dispatched against a corpus has to decide what a unit of work is, re-read to find it, and
re-derive where it sits in the dependency order — every time, inconsistently. An agent
dispatched against a map entry has one concern, a citation, its dependencies, and a
statement of what evidence would settle it.

It also makes the decomposition *reviewable before any code exists*. A wrong map produces a
wrong engine efficiently; the cheapest moment to catch "this is two rules, not one" is
before either has been implemented.

## An entry

```json
{
  "id": "opposed-test-tie",
  "name": "Resolving a tie in an opposed test",
  "locator": { "sourceId": "core-rules", "citation": "Game Concepts / Tests / printed p. 36" },
  "kind": "operation",
  "scope": "in",
  "clarity": "ambiguous",
  "ambiguity": {
    "question": "The text does not say which side prevails when both achieve equal hits.",
    "fate": "decision",
    "decision": "docs/decisions/0099-opposed-test-tie-break.md"
  },
  "dependsOn": ["simple-test", "dice-pool-assembly"],
  "evidence": "Compare the hits scored by each side. The side with more hits prevails, and the difference is the margin.",
  "status": "implemented",
  "implementedIn": { "ruleset": "sr6", "version": 4 },
  "tests": [
    { "test": "OpposedTestTieTests.A_tie_goes_to_the_defender",
      "mutation": "Awarded ties to the attacker; this test went red." }
  ],
  "note": "Demonstrate both tie directions, and the boundary where one side has one more hit."
}
```

### Fields

| Field | Meaning |
|---|---|
| `id` | Stable slug. Referenced by `dependsOn`, by issues, and by the engine's own citations. Never reused. |
| `name` | What the rule is called, in the corpus's language where it has one. |
| `locator` | Corpus id plus a citation in that corpus's grammar. **Required**, except on a derived entry, which must not carry one. An entry without one is not an entry. |
| `kind` | `value`, `operation` or `assertion` — a fact the corpus states, a procedure it describes, or a condition only the caller can supply. See below. |
| `assertedBy` | On every `kind: assertion` entry, and only there. Who the corpus says supplies or decides the fact, in its words, or `["caller"]` with the reason in `note` where it names nobody. See below. |
| `draws` | Present only on an in-scope `operation` of a `randomness: seeded` corpus whose own resolution draws: `{dice, count}` or a list of them. See below. |
| `scope` | `in` or `out`. Out is a recorded verdict with a reason, not an omission. **Decided per rule. A section has no scope of its own.** See below. |
| `clarity` | `clear` or `ambiguous`. `clear` asserts the corpus determines exactly one answer for every valid input — so a corpus that states the rule twice, differently, is `ambiguous`. |
| `ambiguity` | Absent when clear. Otherwise the question, its `fate`, where the corpus contradicts itself the `conflict` the question belongs to, and `affectsDraws: true` where the unsettled point changes the entry's draw count. Never a carrier for a decline that is not an ambiguity. |
| `dependsOn` | Entry ids. Determines backlog order — the sequence entries must be *implemented* in. **Not** a runtime precondition; see the gate fields. |
| `enabledBy` | Entry ids. The rules that make this one reachable at runtime; it does not apply until one holds. Absent on an entry no rule opens. Orders nothing. See below. |
| `suspendedBy` | Entry ids. The rules that make this one unreachable while they hold. Absent on an entry no rule closes. Orders nothing. See below. |
| `beyondAdapter` | Present only when the declared adapter cannot read the rule the locator cites. Names the adapter and the modality. See below. |
| `extraction` | Present only when the corpus text is an extraction (`quotedText` in the manifest) and it garbles this entry's passage. Names the defect and the passage as read from the rendered page. See below. |
| `definedElsewhere` | Present only when the rule's meaning is fixed in a corpus that was not admitted. Names the manifest `references` entry. Never the map's own corpus: a meaning given elsewhere in it is a `scope: out` entry (0026). See below. |
| `absentFrom` | Present only when the corpus does **not** state the rule at all. Names the terms searched for. See below. |
| `derivedFrom` | Present only when no sentence states the fact and two or more in-scope entries entail it. Entry ids. The entry then carries no `locator` and no `evidence`. See below. |
| `crossReferences` | The pointers this entry's `evidence` makes, each resolved to an entry or to a recorded reason there is none. See below. |
| `defines` | The terms this entry's `evidence` defines, each in a named vocabulary. Optional, and the opposite direction to `crossReferences`. See below. |
| `continuesDefinition` | This passage states an additional defining rule for the one term directly defined by another entry. Names that entry and a structural locator witness; it carries no vocabulary or term of its own (0046). See below. |
| `evidence` | One contiguous verbatim span of the corpus: the passage that *states* this rule. Not a summary of it. Absent on a derived entry, and only there. See below. |
| `status` | Whether the engine has built this entry. Independent of `ambiguity.fate`. See below. |
| `implementedIn` | The ruleset revision that implemented it. Set when status becomes `implemented`. |
| `tests` | The tests that prove the entry, each `{ "test", "mutation" }`: the test's name, and the recorded change to the engine that turned it red. **Required, non-empty, when status is `implemented`**, and the mutation may not be a placeholder. See `status`. |
| `note` | Prose explanation: why the entry is shaped this way, and what a test must demonstrate. **Never a claim a test could carry** — a consequence the mapper proved is a test the entry names. See below. |

### `kind: assertion`

Added after the first trial against a real corpus, where eight of twenty-four entries were
neither a value nor an operation.

An assertion is a condition the engine cannot evaluate: that a person could see the
aircraft, that communication was maintained, that a preflight check was performed, that a
pilot judged an action safe. These are real, binding rules — and no computation settles
them.

An engine owes an assertion four things: **demand it, attribute it, record it alongside the
outcome, and never infer it.** Defaulting an unasserted condition to true substitutes the
engine's judgement for a person's, silently, which is the failure the unresolved-result
contract exists to prevent in the other direction.

Judgement the corpus *deliberately* delegates ("if the pilot determines it would be in the
interest of safety") looks ambiguous and is not — the corpus is entirely clear about who
decides.

**Whose fact it is does not decide the kind. The measure the corpus states does.** An
assertion is a property of an **open term the corpus delegated with a stated measure or a
fixed set**, never of the fact's source. § 107.39 settles it in one sentence: (a)'s
*"directly participating"* and (b)'s *"reasonable protection **from a falling small unmanned
aircraft**"* are both facts about a third party that only a person could report, and (a) is a
gap while (b) is an assertion, because only (b) says what the term is measured against.
§ 107.49 settles it the other way — (a)'s *"assess … considering risks to …"* and
(c)'s *"working properly"* are two obligations on the same person, both of them things only
that person could report, and only the first states a measure. This is the half of
[#11](https://github.com/brandonifco/rules-factory/issues/11) 0005 left open, and it is
decided in [0010](decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md): ten of the
twenty measured instances are assertions, six are gaps, two split inside one paragraph, and
two turned out not to be open terms at all.

**A fact the rule merely tests is a parameter, gets no entry, and is not an assertion.** The
airspace class, the groundspeed, whether a visual observer was used, whether the aircraft is
powered — the engine demands all of them and none of them is a rule. Gate 1 below is what
stops them. Until 0010 this section also said *"facts about the physical world are consumed,
not derived"* and filed them under `kind: assertion`, which contradicted gate 1 and
contradicted this document's own ruling on `airspace-authorized`; the sentence is withdrawn
rather than deleted, because it is how four entries were nearly reclassified in 0005's
Consequences.

**A delegated judgement is an assertion, and it is an entry of its own.** `kind` is
entry-level, so classifying a whole entry by one of its clauses destroys the rest of it.
`night-operation` states a computable rule about training and lighting *and* defers the flash
rate to the operator; `over-human-beings` defers a judgement *and* defers to a subpart the map
does not cover, which is a different runtime reason entirely. Split them the way
`speed-limit` (value) and `speed-within-limit` (operation, `dependsOn: [speed-limit]`) are
split: the standard becomes its own assertion entry — `well-clear`, `reasonable-protection`,
`flash-rate-sufficient` — and the rule that consumes it depends on it. Every entry then has
exactly one runtime reason, which is what makes the correspondence table below checkable.
Decided in [0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md).

**There is no test. Recognising one is a procedure, and it is three gates in order.** Five
one-sentence tests have failed — names-a-decider, standard-of-conduct, has-a-bearer, and the two
successors proposed to replace it, each of which agreed with the corpus it was derived from and
was refuted on the other. Decided in
[0008](decisions/0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md), which
carries the counts.

**It runs only on an entry that is `scope: in` and normative.** Advice is not a rule —
`strategy-advice`'s "make points whenever you **fairly** can" is an undefined degree that demands
nothing of anybody — and an absent rule has no words to read. Row 1 of the correspondence table
disposes of both, before the gates. The procedure is not self-standing, and that is a real limit.

1. **A blank in the rule, or a fact the rule tests?** Does applying the corpus's words require
   fixing a threshold, degree, value **or case** the corpus did not fix? If not, the entry is an
   ordinary `value` or `operation` and the fact is a caller-supplied parameter that **gets no
   entry of its own**. Applying *"either thrice or four times"* requires fixing the multiplier;
   applying *"either wholly by moving men forward … or partly by the one method and partly by the
   other"* requires fixing nothing, because the corpus states every branch. Whether ATC authorized
   is a fact the rule tests, not a blank. **"Or case" is load-bearing and is there for two
   instances**: `game-value`'s three named results do not cover a reachable finish and
   `must-play-whole-throw` does not say which die is lost when only one is playable. Neither is an
   open degree, both are gaps, and a gate written only for undefined terms cannot see either.
2. **Unsupplied by the corpus, or only to us?** Readable but not by this adapter →
   `beyondAdapter`. Fixed in a corpus that was not admitted → `definedElsewhere`. Supplied twice,
   differently → a conflict under [0007](decisions/0007-a-conflict-is-a-question-not-a-pair.md).
3. **Whose hands?** The caller's own determination or agreement is operative **and the corpus
   states, in the same constituent as the open term, either what the term is measured against or
   the set of values it may take** → `kind: assertion`. A third party whose determination is a
   separate act → not a caller assertion; `definedElsewhere` where that party's output is itself a
   corpus. Nobody → gap, `clarity: ambiguous`, `fate: unresolved`.

**Gate 3 is checkable, and that is why it is worded this way.** An entry claiming
`kind: assertion` must quote, from its own `evidence`, either the measure — "sufficient **to avoid
a collision**", "reasonable protection **from a falling small unmanned aircraft**", "so close **as
to create a collision hazard**" — or the fixed set: "**either thrice or four times**". An
assertion entry that can quote neither is a gap. The disjunction is the two arms, delegated
standard and delegated choice, and the second has no measure and must not need one. Parties need
not be **named**: *"(as may have been agreed)"* is an agentless passive and names nobody, which is
what refuted two of the five tests.

**What gate 3 cannot decide, stated here because this is where the claim is made.** An open degree
in the `unless` clause of a prohibition, with no measure stated in its own constituent, no set of
values fixed and no third party named. § 107.37(a)'s *"unless well clear"* is that shape —
"well clear" occurs once in the corpus, § 107.3 does not define it, and "must give way" is a
coordinate obligation rather than a measure — and so is § 107.25(b)'s *"sparsely populated
area"*. The procedure returns a gap for both. The map recorded `right-of-way` as an assertion and
`moving-vehicle-operation` as a gap, and **nothing in the corpus draws that line**; what separated
them is aviation practice, which is in neither text. Where the project believes such a term is
determinate, that belief is `fate: decision` with a record, or `definedElsewhere` if the practice
is a corpus that can be admitted — never a `kind`, because a claim the corpus cannot falsify is
the ground `surprising: true` was rejected on. Both maps now agree with the procedure:
`right-of-way` keeps its two computable enumerations and `well-clear` is a gap beside
`moving-vehicle-operation`.

**Four more terms sit in that residue**, and they are where the operator is plainly the only
person who could answer: `effective-communication`, `control-links-working`,
`direct-participation`, `attached-object-secure`.
[0010](decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md) rules that being the only
possible source is not a reason to reclassify. An operator asserting a conclusion the engine
cannot check, where the corpus gave no warrant to delegate, is the substitution of judgement
`never infer it` exists to prevent, arriving from the other side.

**A stated measure may itself be open, and gate 3 does not ask.** § 107.49(a) states what the
assessment is measured against and that measure carries *"immediate vicinity"*; § 107.49(b)
fixes five briefing topics, each open-textured. Gate 3 asks whether a measure is *stated*, not
whether it is *determinate*, so both fire and both are assertions. Named by 0010 with two
instances per map, and filed rather than decided.

### `assertedBy` — who asserts it

**An assertion names who the corpus lets assert it, in the corpus's words.** Decided in
[0025](decisions/0025-an-assertion-names-who-asserts-it-and-an-operation-names-what-it-draws.md)
([#117](https://github.com/brandonifco/rules-factory/issues/117)). *Attribute it* is the second
thing an engine owes an assertion, and until 0025 the map did not say to whom, so the SRD engine
checked `initiative-ties`' deciders against its own reading.

```json
"kind": "assertion",
"assertedBy": ["GM", "players"]
```

A non-empty list, on every `kind: assertion` entry and on no other. **Each value is anchored**: it
appears, ignoring case and spacing, as a whole word or phrase in the entry's `evidence`, or inside a
span the entry's `note` quotes from the corpus. The second route is for a party named outside the
span, such as § 107.49's lead-in, *"Prior to flight, the remote pilot in command must:"*, which governs
four assertion entries. **Where the corpus names nobody**, the value is `["caller"]`, alone, and `note`
says why. *"(as may have been agreed)"* names nobody, and neither does § 107.37(b)'s *"No person may
operate"*, which names only the subject of a prohibition. `check-map.py --only asserted-by`
enforces all of it. The generated `MapEntry` and `RegisteredEntry` carry the list as `AssertedBy`, so
an engine checks an attribution against the map.

**What it does not buy.** `check-map.py` reads no corpus, so it cannot tell a quote in `note` from a
sentence in quotation marks. `tools/tests/mapvalidator/test_map_anchors.py` holds the example maps' quotes to their
committed corpora. An anchor proves the word is there, not that it names the right party. And a list
of who must *be able to see* (§ 107.31(a)) does not say that § 107.31(b) lets some of them do it
instead of others.

### `draws` — what an operation draws

**An operation whose own resolution draws random values says how many draws of what.** Decided in
[0025](decisions/0025-an-assertion-names-who-asserts-it-and-an-operation-names-what-it-draws.md)
([#118](https://github.com/brandonifco/rules-factory/issues/118)). Under `randomness: seeded`, one
extra or missing draw changes every later one, so the count is part of what a replay means.

```json
"draws": { "dice": "d20", "count": "one per participant not in a group of identical creatures, …" }
"draws": [ { "dice": "d20", "count": "one attack roll; …" },
           { "dice": "damage dice", "count": "the attack's own damage dice, on a hit only, …" } ]
```

- `dice` names what is rolled, anchored as `assertedBy` is. The SRD's Initiative evidence says only "a Dexterity check", so the note quotes p. 6's *"the game uses a d20 roll"*. Hoyle has no notation, and its dice are `die` and `dice`.
- `count` is a positive number, or a short statement.
- Only an in-scope `operation` carries it. It is refused under `randomness: none`.
- **A draw belongs to the entry whose own resolution makes it.** A gate, a dependency or a cross-reference that leads to a roll does not declare it: `full-table-suspension` suspends `throw-two-dice`, `attack-structure` depends on `attack-resolution`, and `next-game-opening`'s *"as at starting"* is `opening-roll`'s throw. Otherwise one d20 is declared three times. The count may name the other entry, so a draw is counted once.

**`ambiguity.affectsDraws: true`** marks an ambiguity whose unsettled point changes how many draws
*this entry* makes. `group-initiative` does not say what a group is, and so does not say how many
rolls there are. Such an entry must declare `draws`, and its `count` may name the alternatives.
`check-map.py --only draws` enforces the shape, the anchor, the kind, the corpus's randomness and
this requirement.

**What it does not buy.** An operation that rolls and omits `draws` passes. The field is required only
where a mapper has recorded that the count is unsettled, which is the same blind spot as an
unrecorded conflict. `count` is prose that nothing reads.

### `evidence` is the corpus's words, not the mapper's

**`evidence` holds one contiguous verbatim span of the corpus: the passage that states the rule
the entry maps.** Not a description of it, not a list of the cases a test should cover.

This is the field that makes `locator` checkable. `tools/check-locators.py` finds the span in
the corpus, walks back to the nearest page marker and compares it against the citation. Where
`evidence` held a summary — "Both figures.", "Both elections." — nothing was findable, so
nothing was checkable, and **thirteen of the backgammon map's citations were wrong by a page or
two through a mapping trial, a build and a review**
([#18](https://github.com/brandonifco/rules-factory/issues/18)). The wrong pages are not the
point. They are the measurable symptom of a mapper who stopped reading, and quoting is the only
part of that a check can reach.

**An ellipsis skips whole paragraphs and never words inside one**
([0037](decisions/0037-an-ellipsis-skips-whole-paragraphs-and-never-words-inside-one.md),
[#282](https://github.com/brandonifco/rules-factory/issues/282)). Truncating a span at either end
is fine; eliding its middle is not, and the line between the two is the corpus's own paragraph
boundary. At every `...` in a prose `evidence`, the text before it must end where a paragraph
ends and the text after it must begin where one begins — so a quote may pass over a paragraph the
citation names, and may never drop a qualifying clause from inside the sentence an entry rests
on. The words an ellipsis skips this way are visible in the citation, which must name every
paragraph the quote touches; words dropped from inside a paragraph are visible nowhere.

A **table row** carries no ellipsis at all
([0035](decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)): a row is short, has
no paragraphs inside it to skip, and an ellipsis in the middle of one elides a column.

Where the intervening text is not itself the rule, include it — a shorter honest span beats a
longer edited one. **If the rule genuinely needs two passages the same citation cannot name, that
is evidence the entry is two entries**, which is the granularity finding the map already rests
on; whether that holds for a corpus built to break it is trial 10's first hypothesis
([#262](https://github.com/brandonifco/rules-factory/issues/262)).

A separate weakness, and **not** what the rule above describes: the page-marked checker
(`check-locators.py`) matches the longest contiguous *prefix* of a span and reports coverage,
because it was retrofitted onto evidence that was never a quote. `point-designations` was exactly
that — a 118-word `evidence` of which 11 words were ever checked. That is
[#18](https://github.com/brandonifco/rules-factory/issues/18)'s unfinished business and is
recorded as such, rather than being described here as though it were the ellipsis rule.

**A span may straddle a page marker, and carries it verbatim.** The arrangement sentence begins
on p. 272 and the `{273}` marker falls mid-sentence. Citing either page is honest and the
checker accepts both; dropping the marker to make the quote read cleanly would break the match.

**A span the corpus prints more than once is identified by the container the citation names, and
never by extending the span until it is unique.** Decided in
[0030](decisions/0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md)
([#207](https://github.com/brandonifco/rules-factory/issues/207)). A corpus repeats itself — a
regulation restates a proviso, a glossary gives five conditions the same effect — and a quote that
resolves in five places resolves in none. What settles it is what the citation *names*:

- **`section-designation`** names a container, so `check-locators-section.py` asks whether every
  occurrence lies inside it. The anti-collision sentence is printed in `§ 107.29(a)(2)` and again
  in `(b)`, and each is cited by naming its paragraph. Nothing more is needed, at any depth.
  **A row of a table is a container too**, once it has a name:
  `§ 172.101 table 3, row [column 2 = "Acetal"]`, below.
- **`heading-path-and-printed-page`** names a page, which is positional and contains nothing, so
  the **heading path** is the container. Where a quote also occurs off the cited page,
  `check-locators-pdf-text.py` reads the path: each line matching the citation's last heading
  selects the first occurrence after it, counted only where the earlier headings occur as lines
  before it, and **exactly one occurrence must be selected**. `Rules Glossary / Round Down / p. 187`
  resolves and `Playing the Game / Round Down / p. 5` does not, because `Playing the Game` precedes
  both printings; a citation the path does not narrow to one passage **fails**, and the checker
  never picks a printing for the mapper.

Extending a span until it is unique is what this replaces, and it is not a fallback: it produced a
`round-down` whose span carried the whole of the next glossary entry and passed every check.

**What must be demonstrated is a mapper's reading, and it goes in `note`.** "Both figures",
"the worked distribution, for both the quatre and the trois", "a throw fully playable, partly
playable, and unplayable" — these are genuinely useful and no check can read them. They are
prose, and `note` is where prose lives, the same ruling 0004 made for `beyondAdapter`'s
explanation. A field for them would fail the test 0005 sets: it would name a distinction
without becoming checkable. The whole-table rule survives the move intact — **where the corpus
prints a finite table, the note requires the whole table and never a sample** — and so does the
rule that a span must cover every case the entry claims, not one of them.

**`note` is explanation, never a claim a test could carry.** It says why an entry is shaped the
way it is, what a test must demonstrate, where a span was corrected — reading aids for the next
mapper and the implementer. It is not where a mapper records something they *proved* about the
rule. *"The adopted opening throw can never be doublets"* is a claim about the engine's answers
that a test can assert and that will silently become false if the opening rule changes; written
in `note` it rots, and nothing notices. Such a consequence is discharged as a test named for what
it proves, and the entry names the test — the rule 0005's rail E already set for a surprising
reading, extended to every derived consequence
([#16](https://github.com/brandonifco/rules-factory/issues/16),
[method.md Phase 6](method.md#phase-6--implement)). The test for whether a sentence belongs in
`note`: if a test could fail because the sentence became false, the sentence is the test's, not
the note's. What cannot be reduced to a test is lost, and that cost is accepted.

**A `scope: out` entry quotes too, and so does an absent one.** An out-of-scope verdict is a
verdict about a passage, and a passage nobody can locate is a verdict about nothing:
`strategy-advice` quotes the opening sentence of the advice it declines, and demands nothing
of the engine. A rule the corpus does not state at all — `doubling-cube`, which this 1909 text
predates — quotes **the passage the rule would be in**, and carries `absentFrom` to say that is
what the span is. There is no exception and no entry without a span. Until
[0009](decisions/0009-absence-is-a-verdict-with-evidence.md) there was: the citation read
`(absent)`, the checker special-cased it, and the gate's line "all 29 checked" meant
twenty-eight.

**An `evidence` a licence forbids quoting is recorded as absent, never as a summary.** Phase 2
of [method.md](method.md) says *cite, do not copy*, and for a licensed corpus a span in the map
may be a licence problem rather than a discipline one. The corpus's manifest entry then declares
`quotation: withheld` ([0013](decisions/0013-verification-posture-belongs-to-the-corpus.md)),
its entries carry no `evidence`, and `check-map.py --only postures` fails any that do. The
citation is unverifiable — which `check-locators.py` reports, because an unlocatable entry
fails the run and is never counted as ok. What is not acceptable is a summary occupying the field
and looking like evidence. No trial has produced this case; every mapped corpus is public domain
and declares `quotation: verbatim`. The factory admits no corpus whose licence forbids the
quote ([0028](decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)), so this case
describes a manifest the checker reads, never a map the factory packs.

**What a verified span does not prove.** Only that the page cited is the page the quoted words
sit on. It says nothing about whether that is the *right* passage for the entry, whether the
entry is the right decomposition, or whether the mapper read the three sentences after it.

### `ambiguity.fate`

`decision` — the project rules on what the passage means, records it, and implements as
though the corpus had said so. `decision` names the record.

`unresolved` — the engine declines at runtime and returns `RequiresInterpretation`. Correct
when no reading is defensible enough to bake in, or when the choice belongs to the caller.

There is no third value. An implementer choosing a reading silently is the failure this
field exists to prevent.

**An owner's ruling is not a fate, and it is not in the map.** The owner of one engine may answer
part of an `unresolved` question for that engine. The answer lives in the entry's own overlay file
as a `ruling` that quotes the part it answers from `question`, and the map still says `unresolved`,
because the corpus still does not settle it. The engine names the ruling on every result that
relies on it. See [0027](decisions/0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md)
and `status` below.

`ambiguity.unresolvedReason` names the `UnresolvedReason` the engine will return, and is
present when the fate is `unresolved`. It is the field that ties an entry to the
correspondence table below — and it must be a reason that table actually produces for this
entry: `RequiresInterpretation` (row 6), or `OutsideCurrentScope` where the entry is
`scope: out` and row 1 wins first. `check-map.py --only unresolved-reason` refuses the rest
([0034](decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md)). Being in the
kernel's vocabulary is not enough: a caller told `MissingRulesData` is sent after data that does
not exist, when what is missing is an interpretation nobody has made.

**The block is never a general decline carrier.** A rule defined in an unadmitted corpus
takes `definedElsewhere`; a rule the adapter cannot read takes `beyondAdapter`. No entry
carries either of those *and* an `ambiguity` block — that is a checkable exclusion, and it is
what keeps two rows of the correspondence table from firing with different answers on the
same entry.

**A corpus that contradicts itself is ambiguous.** `clear` asserts the corpus determines
exactly one answer, and a corpus stating a rule twice in incompatible terms does not.
`enter-from-bar` names two legal destinations where `legal-destination`, three sentences
earlier, names three. The `question` states both readings; `fate` records which governs, or
declines.

### `ambiguity.conflict`

A slug naming the question the corpus answers twice. Entries carrying the same slug are the
members of one conflict. Absent on an ambiguity that is a gap rather than a contradiction,
which is most of them. Decided in
[0007](decisions/0007-a-conflict-is-a-question-not-a-pair.md).

```json
"ambiguity": {
  "question": "…",
  "conflict": "points-open-to-an-entering-man",
  "fate": "decision",
  "decision": "docs/decisions/0006-the-general-rule-governs-entry-and-full-means-adversely-full.md"
}
```

**A conflict is a question, not a pair.** The three backgammon entries carrying this slug do
not each contradict each other — `enter-from-bar` and `full-table-suspension` fit together
exactly, and both disagree with `legal-destination`. What makes them one conflict is that they
are three answers to *which points are open to a man entering from the bar*. A list of pairwise
ids would record edges, from which the set could be recovered only by a closure the data does
not license.

Four rules, and `tools/check-map.py --only conflicts` enforces all four:

- The slug lives **inside the `ambiguity` block**, so only an `ambiguous` entry can be in a
  conflict. A corpus that says it twice, differently, is ambiguous — that is what puts it here.
- **A conflict has at least two members.** A slug on one entry records a contradiction with
  nothing, and is what both a typo and a deleted counterpart look like.
- **Every member shares a `fate`.** One question cannot be both settled and declined.
- **Where that fate is `decision`, every entry in the conflict names the same decision
  record** — otherwise one side can be decided and the other left open with nothing noticing.

Nothing detects a conflict the mapper never noticed: two `clarity: clear` entries stating
incompatible rules produce a map that validates, which is the same blind spot as an incomplete
gate list. What these rules buy is that a *recorded* conflict cannot be half-settled.

A conflict a **second mapper** noticed is reached, though, and by the adjudication rather than by
the map: where a blind second mapping read an entry as ambiguous and the adjudication answered
*the corpus does not settle it*, `check-map.py --only superposition` requires the map to record
that doubt — on the flagged entry or on one the adjudication names
([0034](decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md),
[0014](decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md)). **The map has no field for
competing readings, and 0034 decides it will not gain one**: a field inside the `ambiguity` block
can only be carried by an entry that already admits its doubt, so it would be absent exactly where
a collapse happens. What is lost by that is stated there, with the count.

### `ambiguity.bounds` — what an authored example fixes about the open term

An operative rule can leave a term open while the same corpus, in the same authority's words,
states that a particular fact pattern is or is not within it. § 1.121-1(c)(2) counts "short
temporary absences" as use and fixes no length; § 1.121-1(c)(4) Example 4 states that a 1-year
sabbatical is not one and Example 5 that a 2-month vacation is. Those two are not entries — they
answer no caller's request and state no rule — and they are not prose either: they decide what an
owner's `ruling` (0027) may say. Decided in
[0031](decisions/0031-an-example-that-bounds-a-term-is-recorded-as-a-bound.md)
([#216](https://github.com/brandonifco/rules-factory/issues/216)).

```json
"ambiguity": {
  "question": "\"Short temporary absences\" fixes no length and no test. …",
  "fate": "unresolved",
  "unresolvedReason": "RequiresInterpretation",
  "bounds": {
    "term": "short temporary absences",
    "dimension": "duration",
    "examples": [
      { "locator": { "sourceId": "cfr-26-1.121-1", "citation": "§ 1.121-1(c)(4) Example 4" },
        "text": "… Because his leave is not considered to be a short temporary absence under paragraph (c)(2) of this section, …",
        "verdict": "doesNotApply", "value": "P1Y" },
      { "locator": { "sourceId": "cfr-26-1.121-1", "citation": "§ 1.121-1(c)(4) Example 5" },
        "text": "… the 2-month vacations are short temporary absences and are counted as periods of use …",
        "verdict": "applies", "value": "P2M" }
    ]
  }
}
```

- **`term`** is the open term in the corpus's words, and it must occur verbatim in the entry's
  own `evidence`. A term the cited passage does not use is the mapper's, not the corpus's. It
  must also occur in the entry's own `ambiguity.question`, matched without regard to case, because
  the question is where the map records the term as **open** and an owner's ruling quotes a span
  of that question (0027): a term the question omits is one no ruling could be compared against.
  `check-map.py --only bound-term-open` holds it
  ([0034](decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md)).
- **`dimension`** is the scale the example's fact pattern and a later ruling's line are both
  values on. **It is a closed vocabulary, and it holds only what a checker compares**: today
  `duration`, in ISO 8601 (`P1Y`, `P18M`, `P730D`), compared in 30-day months and 12-month years
  so that `P1Y` and `P12M` are one value. A dimension is added when a corpus states a bound in it
  and a parser and its tests arrive with it.
- **`examples[].locator` and `.text`** are the example's own citation and one contiguous verbatim
  span of it, on the same terms as `locator` and `evidence`: the locator checkers find the words
  and hold them to the citation, and a bound whose words are not there fails the run.
- **`examples[].verdict`** is `applies` or `doesNotApply` — the term reaches that fact pattern, or
  it does not. **`.value`** is where the fact pattern sits in the dimension.
- Only on `fate: unresolved`, and only inside the `ambiguity` block. `check-map.py --only bounds`
  refuses the block elsewhere, a dimension it cannot compare, a value it cannot place, and
  **examples no single threshold separates** — two bounds that cannot both hold are a defect in
  the map, not an ambiguity in the corpus.

**What a bound buys, and it is one thing: an owner's ruling is compared against it.** Under 0027
an engine's owner may answer part of an open question. Where the entry carries bounds, that ruling
states the line it draws — `"boundary": {"dimension", "operator", "value"}` — or `null` to declare
that it draws no line in that dimension, and `tools/factory/rulings.py` evaluates it at every
example's value. A ruling that "short temporary absence" means eighteen months or less makes a
1-year sabbatical short, Example 4 says it is not, and the engine fails its gate naming the
example rather than answering. That comparison is the whole of what the field earns its place by
under [0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md), which is why the
dimension must be comparable.

**A bound is admitted only where the dimension is comparable, and the rest stays prose.**
§ 1.121-1(b)(3)(i)'s "adjacent to" is bounded by fact patterns about a public road and a corner;
no threshold any ruling would state is comparable to them, so they stay in `ambiguity.question`,
unchecked and admittedly so. Recording them as bounds would put in a structured field exactly what
the field was scoped to exclude.

**What it does not buy.** Nothing detects an authored example the mapper never read — the blind
spot an unrecorded conflict already has. Nothing holds a ruling's `boundary` to the `answer` in
prose beside it, or a `boundary: null` to the truth; both are what review reads. And a bound's
`value` is the mapper's reading of the example's fact pattern: that Taxpayer D's sabbatical was
a year is in the quoted text, and that it is the feature the example turns on is a judgement no
check makes.

### `dependsOn` orders work; `enabledBy` and `suspendedBy` do not

`dependsOn` orders *implementation*. A rule that applies only in a phase — bearing off
begins once every man is home; entry from the bar suspends every other move — has a
**runtime precondition**, which is a different fact. The gate fields are where it lives.
Decided in [0003](decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md), and split by
direction in [0011](decisions/0011-a-gate-has-a-direction.md).

The two relations coincide often enough to be confused, and they are not derivable from each
other. In the backgammon map, `bearing-off-doublets` has six `dependsOn` ancestors and
exactly one of them is its gate; `move-by-pip` is suspended by `enter-from-bar`, which is not
among its ancestors, and nor is `move-by-pip` among `enter-from-bar`'s. A stateless corpus
has no phase for a rule to be scoped to, but it can still have gates. A waiver is one: while a
certificate of waiver authorizing deviation from § 107.41 is held, § 107.41 does not apply. See
*A gate outside the slice* below.

**A gate has a direction, and the field says which.** `enabledBy` names the rules that make
this one reachable; `suspendedBy` the rules that make it unreachable while they hold.
Direction belongs to the edge, not to the gating rule: `bearing-off-eligible` is in
`bearing-off-highest`'s `enabledBy` and in `move-by-pip`'s `suspendedBy`, because once every
man is home bearing off governs every forward move. Until 0011 both were one undirected
`gatedBy` list, and a reader had to follow each id to learn whether it opened a phase or closed
one. `check-map.py --only gates` refuses `gatedBy` by name, and refuses an id named in both
fields of one entry.

**Both hold entry ids and nothing else.** No predicate, no state name, no threshold,
no sentence. A gate is itself a rule the corpus states, so it already has an entry with a
locator; if a gate you want to record has no entry, the map is missing an entry. The
condition is the engine's to implement — the map says which rule governs reachability, in
which direction, and points at where to read it.

They are **not transitive and not inherited through `dependsOn`.** Every entry a gate reaches
names it, even where a `dependsOn` ancestor names the same gate — the two relations are
independent, so inheriting along one of them would be a guess. Expect repetition:
`full-table-suspension` is named by seven entries, each with the judgement in its `note`.

They order nothing. `dependsOn` remains the only input to backlog order.

**A gate outside the slice is a `scope: out` entry, and whether it holds is the caller's to
state.** Decided in [0021](decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md). A gate
field can name an out-of-scope entry the way `dependsOn` names `subpart-d-categories`. In Part 107,
27 entries name `waivable-regulations` (§ 107.205, subpart E) in `suspendedBy`. The corpus states
the rule and does not say whether a waiver is held. That is the Administrator's determination, a
third party's separate act (§ 107.200(a)), and its output reaches the engine as a fact the gate
tests. By gate 1 below, such a fact is a parameter. It is not `kind: assertion`, and it gets no entry.
What the engine owes it is borrowed from row 8. **It demands the fact, attributes it, records it with
the outcome, and never infers it in either direction**: defaulting to "not held" convicts a holder,
and defaulting to "held" excuses everyone. Where the caller states the gate holds, the suspended entry
answers `OutsideCurrentScope` and cites the gate, which is row 1 reached through the edge. Where the
caller states it does not hold, the entry is evaluated as if it had no gate. An absent rule can never
hold, so `absent` still refuses an edge to one.

**What the split does not buy.** Nothing checks that a gate is complete, or that it is in the
right field: a permitting rule filed under `suspendedBy` resolves and passes. The direction is
written down where a reviewer reads it, which is all.

### `beyondAdapter`

The rule is in the corpus, stated in a modality the declared adapter cannot read. Decided in
[0004](decisions/0004-adapter-reach-is-a-property-of-the-entry.md).

```json
"beyondAdapter": { "adapter": "plain-text", "modality": "illustration" }
```

`adapter` must match the `adapter` declared in the manifest for the entry's
`locator.sourceId`. The fact is adapter-relative, not absolute: a reader that can see
figures reaches the entry, and naming the reader that could not makes "what did the old
adapter miss" a query rather than a re-read.

`modality` is a short noun phrase naming what holds the rule — `illustration` in the one
observed case. Deliberately not a closed vocabulary: one instance is not enough to write
one from, and it can be closed later from evidence. Explanation goes in `note`, not here.

`locator` is still required and still cites the passage that *states* the rule — the
sentence saying the men are placed as in Fig. 1. The entry is unreadable, not uncitable.

This is a different fact from the manifest's `references`, and telling them apart is the
whole point. `references` says the rule is defined in a corpus that was not admitted;
`beyondAdapter` says the rule is here and our reader cannot see it. Both decline as
`MissingRulesData` at runtime, and before this field they were indistinguishable without
reading a prose reason.

The general case is worse than the one illustration: a PDF rulebook read as extracted text
loses exactly the tables a rules engine most needs. No trial has produced that — both
corpora were text end to end — and the field does not detect it. It records a limit a human
recognised. An adapter that silently drops a table produces an entry nobody writes, and no
field can help with an entry that does not exist.

### `extraction`

The rule is readable, and the extraction the corpus is quoted from reads it wrongly. Decided in
[0024](decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)
([#113](https://github.com/brandonifco/rules-factory/issues/113)).

```json
"extraction": { "defect": "interrupted-by-page-furniture",
                "renderedReading": "The GM decides the order if the tie is between a monster and a player character." }
```

**`evidence` stays verbatim of the extraction**, because that is what a checker can hold it to,
and the manifest says so with `quotedText` (below). Where the extraction differs from the page in
a way that changes what the passage says, the entry declares it. `defect` is closed, with the
three values trial 7's SRD map gave:

- `interrupted-by-page-furniture` — a folio or running header sits inside the quote
  (`initiative-ties`);
- `split-by-sidebar` — a sidebar lies between a sentence's halves, so the quote begins or ends
  mid-sentence (`attack-structure`);
- `interleaved-table` — a table's cells come out out of order (`cover-bonuses`).

`renderedReading` is the passage as read from the rendered page, and must differ from `evidence`.
`check-map.py --only extraction` refuses the field on a corpus with no `quotedText`, beside
`beyondAdapter`, under `quotation: withheld`, and on a derived entry.
`check-locators-pdf-text.py`'s `extraction` tests each declared defect at every occurrence of the
quote: a folio line inside it, a fragment, three or more blank-line-separated blocks. It fails a
quote that runs across a folio line and does not declare the furniture. **It prints every
`renderedReading` NOT VERIFIED.** Nothing reads the page. A reviewer does, and a map change that
adds or alters a rendered reading carries a review of it (0017).

**What it does not buy.** The tests show that a declared defect has its shape. They cannot show
that cells are out of order or that the text between two halves is a sidebar. An undeclared
interleaved table passes. A joined line-end hyphen or a space after a line-end dash changes no
word of a rule, so neither is a defect. Both are covered by `quotedText`.

### `definedElsewhere`

The rule is stated here and its *meaning* is fixed in a corpus that was not admitted. Added
in [0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md).

```json
"definedElsewhere": { "reference": "cfr-49-171" }
```

`reference` must resolve to an entry in the manifest's `references`, exactly as
`beyondAdapter`'s `adapter` must resolve in the manifest. Part 107's `hazardous-material`
defers to 49 CFR 171.8 and `civil-twilight-alaska` to the Air Almanac; both previously
carried the reason in an `ambiguity` block, on entries that are not ambiguous.

It shares a runtime reason with `beyondAdapter` and shares nothing else, which is why they
are two fields rather than one with a discriminator: each has required contents that resolve
against a different part of the manifest, and a merged field would be half-empty in every
instance and checkable only after reading its own discriminator.

**It answers the pointer, once.** *"The term hazardous material is defined in 49 CFR 171.8"* is
a reference the corpus makes, and `definedElsewhere` is its answer: it names the manifest
reference and gives the entry its runtime row. A `crossReferences` item for the same pointer
answers it a second time, as prose, and `check-map.py --only cross-references` refuses it
([#62](https://github.com/brandonifco/rules-factory/issues/62)). The entry may still declare its
*other* pointers: `night-waiver-bar` routes "at night" to § 1.1 and answers "under § 107.200" as
a cross-reference, because § 107.200 is a different passage.

**It never names the corpus the map was made of.** Decided in
[0026](decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)
([#115](https://github.com/brandonifco/rules-factory/issues/115)). The SRD's Rules Glossary is the
same admitted corpus as its combat chapter, and it says when a creature is surprised. A meaning the
same corpus gives outside the slice is a **`scope: out` entry** citing and quoting that passage,
checked by the locator checker like any entry. The in-scope entry names it in `crossReferences`
(see below). Where the passage **modifies** the rule, meaning the engine cannot resolve the rule
in some case without it, the entry names it in `dependsOn` too: `initiative-roll` depends on
`incapacitated-condition`, whose glossary text gives Disadvantage on Initiative. Where the slice
already decides every case the passage does, the
cross-reference is enough. `check-map.py --only manifest` refuses a `definedElsewhere` naming a
corpus the manifest declares, or a reference marked `admitted: true`.

**An elsewhere-defined *input* is neither an elsewhere-defined rule nor an assertion.**
`airspace-authorized` is fully implementable: § 107.41 requires authorization iff the class is
B, C, D or the lateral surface area of E, and the entry's `evidence` is that matrix. What comes
from outside is the airspace class — an ordinary caller-supplied parameter, like groundspeed or
altitude. `definedElsewhere` is wrong (there is no airspace corpus to name) and so is
`kind: assertion` (it would destroy the computable rule and make the evidence unevidenceable).
**A parameter is not a rule, so it gets no entry at all**; the entry stays an `operation` with a
`note` saying the input comes from outside.

### `absentFrom`

The corpus does **not** state the rule. Added in
[0009](decisions/0009-absence-is-a-verdict-with-evidence.md).

```json
"absentFrom": { "searched": ["doubling", "doubling cube", "redouble", "offer to double"] }
```

Three states exist and two of them are `scope: out`: *read and declined*, *read and not
there*, and *nobody looked*. `absentFrom` is what separates the first two; the third is a
missing entry, which `extent` and `crossReferences` are what narrow.

`searched` is the words the corpus would use if it stated the rule. Non-empty, and
**`check-locators.py` searches the declared `extent` for every one of them — an entry whose
terms turn up fails.** It is the only check here that goes red by *finding* something. The
search is bounded by `extent` and must be: "doubling" does not occur in Hoyle's backgammon
chapter and does occur elsewhere in the same volume, so a whole-volume search would refuse a
true absence and teach mappers to write vaguer terms.

`locator` and `evidence` are required exactly as on any other entry. They cite and quote **the
passage the rule would be in** — for `doubling-cube`, the sentence that enumerates the
apparatus and closes the list. So an absence costs a mapper *more* reading than a scope
verdict, not less, which is the right price for the failure it exists to catch.

`scope: out` and `status: declined`; `beyondAdapter`, `definedElsewhere` and an `ambiguity`
block are excluded — a rule is not both nowhere in this corpus and somewhere in it we cannot
reach, and a rule with no words cannot be ambiguous about them. Nothing may name an absent
entry in `dependsOn`, `enabledBy` or `suspendedBy`: that edge can never be satisfied.

**What it does not buy.** A term absent is not a rule absent. The corpus could state the rule
in words nobody searched for. What the check catches is a mapper who declared an absence
without looking — which is what [#29](https://github.com/brandonifco/rules-factory/issues/29)
was.

### `derivedFrom`

A fact the corpus entails and never states. Added in
[0012](decisions/0012-a-fact-the-corpus-implies-is-a-derived-entry.md).

```json
{ "id": "hit-pays-single-stake", "kind": "value", "scope": "in", "clarity": "clear",
  "derivedFrom": ["stake-multiplier", "agreed-backgammon-multiple"], "dependsOn": ["game-value"],
  "status": "mapped", "note": "…" }
```

Hoyle says a gammon pays *"double the agreed stake"* and a backgammon *"thrice or four times …
the amount of the single stake"*, and never says what a hit pays. That it pays the single stake
is one step of arithmetic over two stated rules. It used to sit inside `stake-multiplier`,
`clear`, with nothing to quote.

It is the fourth relation between entries and none of the other three: `dependsOn` orders
implementation, the gate fields govern reachability, `crossReferences` records a pointer the
corpus makes. `derivedFrom` says **this fact is entailed by those facts**, and orders nothing.

**A derived entry cites nothing.** No sentence contains its fact, so it has no `locator` and no
`evidence`, and its sources' located spans are its citation. That is what keeps `evidence` one
thing — a verbatim span — everywhere it appears. `kind` keeps its ordinary value; there is no
`kind: derived`, because the field already says it.

`check-map.py --only derived` enforces the shape: at least two sources, each an entry in this
map, not the entry itself, `scope: in`, no circular derivation, and none of `locator`,
`evidence`, `crossReferences`, `absentFrom`, `beyondAdapter` or `definedElsewhere` on the derived
entry. `check-locators.py` names derived entries and does not locate them.

**One source is not a derivation.** A fact that follows from a single entry is that entry's
consequence, and it is discharged as a test the entry names (see
[method.md](method.md#phase-6--implement)), not as an entry.

**What it does not buy.** Nothing checks that the sources entail the fact. The check proves the
reading names what it rests on and that those are rules the map covers; the entailment is in
`note`, and is review.

### `scope` is decided per rule. A section has no scope of its own

A section is a unit of the corpus's **layout**; `scope` is a judgement about a **rule**. There
is no field for excluding a section and there will not be one.

The instance: the backgammon map excluded *Hints for Play* wholesale as advice, and inside it
sits the only authority in the corpus for a die having six faces — *"all the possible throws"*,
followed by twenty-one of them, and *n(n+1)/2 = 21* has one positive solution.
`strategy-advice` declines **the advice**; `die-faces` is `scope: in` and cites the same
section. Two entries citing one section, with opposite verdicts, is correct.

Excluding a section requires reading it first, and what records that reading is `extent`
coverage: every page inside the declared extent is reached by some entry's located evidence, or
`check-locators.py` names it.

### `crossReferences`

A reference the corpus makes is an entry, or a recorded reason there is none. Added in
[0009](decisions/0009-absence-is-a-verdict-with-evidence.md).

```json
"crossReferences": [
  { "cites": "as at starting", "resolvedBy": "opening-roll" },
  { "cites": "as in Fig. 1", "unmapped": "Fig. 1 is an illustration, not a passage." }
]
```

§ 107.29(a) opens *"Except as provided in paragraph (d) of this section"* and (d) has no entry
in either Part 107 map ([#28](https://github.com/brandonifco/rules-factory/issues/28)). Nothing
detected it, because a cross-reference was a sentence inside an `evidence` span and no field
made a mapper answer it.

`check-map.py --only cross-references` reads pointer phrases out of each entry's `evidence` and
requires each pointer to lie inside a declaration whose `cites` appears **verbatim in that same
evidence** — the answer is anchored in the corpus's words rather than asserted beside them — and
resolved by exactly one of `resolvedBy` (an entry id in this map) or `unmapped` (a reason there is
none).

**The phrases are per corpus.** Decided in
[0026](decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)
([#116](https://github.com/brandonifco/rules-factory/issues/116)). A short built-in list, written
from CFR and Hoyle wording, is read for every corpus. Each manifest corpus adds the words its own
text points with, as `pointerPhrases` (see [the manifest](#the-corpus-manifest)). Matches that
overlap, or that only whitespace separates, are one pointer. A pointer naming the entry's own
`definedElsewhere` reference is answered by that field. The check prints, for each corpus, how many
pointers it detected in the spans the map quotes and how many declarations sit on one, and it
**fails a corpus that declares no `pointerPhrases` and on which the built-in list detects nothing**.
That silent zero is how the SRD map's 22 declared cross-references went unchecked.

**A term defined elsewhere in the same corpus is declared here, anchored on the term.** Where the
chapter uses a word the corpus defines outside the slice and no words point at the definition,
`cites` quotes the term as the evidence uses it, and `resolvedBy` names the `scope: out` entry
that quotes the definition: `{ "cites": "surprised", "resolvedBy": "surprise-glossary" }`. See
`definedElsewhere` above for when `dependsOn` names it too.

What an *"except as provided in"* clause obliges a mapper to do is therefore: **follow it, and
produce either an entry or a sentence saying why there is none.** Not a judgement about whether
the target matters.

**A pointer into a corpus that was not admitted is `definedElsewhere`'s, not this field's.** An
item naming the entry's own `definedElsewhere` reference is refused
([#62](https://github.com/brandonifco/rules-factory/issues/62), see above). The check recognises
the reference by the designation in the manifest reference's `citation` (`§ 171.8` in
"49 CFR 171.8") or by its `sourceId` read as words (`air-almanac` in "the Air Almanac"), and by
nothing else, so an item naming it some other way passes.

**Three limits.** Detection is still a list, now the corpus's own. A corpus that points in words
its phrases do not cover passes. The built-in list alone missed *"as shown in {273} Fig. 1"*
because the page marker fell inside the phrase, and Hoyle's own regex reaches it. `unmapped` is
prose, the carrier 0003 and 0004 both rejected. What is checked is that a mapper was made to write
one and anchored it, not that it is true. And a term-anchored item is checked for its anchor and
its target, not for whether the target defines the term.

### `defines`

A term an entry defines is declared by that entry, and anchored in that entry's own evidence.
Added in [0045](decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md).

```json
"defines": [
  { "vocabulary": "special-provision-codes", "term": "IB3" }
]
```

**It is the opposite direction to `crossReferences`, and neither implies the other.**
`crossReferences` records a pointer the passage *makes*; `defines` records a term the passage
*gives a meaning to*. 49 CFR § 172.101's column 7 cell prints `IB3` and points at the § 172.102
entries that define it; those entries point at nothing merely by defining it. Deriving one from
the other would make a defining entry assert a reference its passage does not make.

**Why it exists.** A mechanism that reads a corpus's codes as pointers has to know what the codes
are ([`coded-pointer`](mapper.md#coded-pointer--a-pointer-its-column-makes)). `defined-term-use`
reads them out of one entry, because the SRD prints its glossary list in a sentence. § 172.102
prints no such passage — its codes are one per table row, and § 172.102(c) says only *"The
following tables list … the special provisions referred to in column 7"* — so an entry carrying
that list would be indexing twenty codes it does not print, which the anchoring rule refuses
([#314](https://github.com/brandonifco/rules-factory/issues/314)). The vocabulary is therefore distributed. A passage that prints its term declares it directly;
where a second passage states an additional rule without repeating that term, 0046 may attach it
through an independently anchored `continuesDefinition`. `(vocabulary, term)` resolves to **every**
direct and continued defining entry. That is where
[0044](decisions/0044-one-printed-code-can-name-more-than-one-rule.md)'s cardinality comes from:
trial 10's `IB3` now reaches its table-2 IBC rule, the additional-requirement row beneath it, and
the separate table-4 Large Packagings rule.

`check-map.py --only defines` holds the declaration, and only what can be held mechanically: a
non-empty list; each item exactly `vocabulary` and `term`, both non-empty strings; the `term`
**verbatim in this entry's own `evidence`**; and the same `(vocabulary, term)` once per entry. A
derived entry may not carry it, for the reason it may not carry `crossReferences` — it quotes no
passage. Several entries **may** define the same term; that is the case the field exists for.

**One canonical form, read by everyone.** A `vocabulary` is the map's own word and is taken
stripped of surrounding whitespace; a `term` is a quotation and is whitespace-normalised, as a
`cites` is and as the evidence it is matched against is. That canonical form is the contract's,
in `mapcontract.entry.definition_of`, and the check, the protocol and the pointer detector all
read it rather than normalising their own — because a declaration proved under one
`(vocabulary, term)` and consumed under another is a code the map declared and the detector reads
as undeclared, with nothing able to say so.

**Three limits.** That the passage really *defines* the term rather than printing it is
interpretive, as `unmapped` is, and is not checked. That some protocol reads the vocabulary is
not checked here either — the protocol belongs to the mapper
([0032](decisions/0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md)),
and `mapper protocol` is what refuses a `coded-pointer` naming a vocabulary no entry defines. And
a vocabulary name is free text: two entries that meant the same vocabulary and spelled it
differently make two vocabularies, and what says so is the pointer report listing the codes
neither declares.


### `continuesDefinition`

A passage can state an additional defining rule under a term that another passage prints without
repeating that term. [0046](decisions/0046-an-additional-rule-can-continue-a-definition.md) gives
that relationship its own field instead of weakening `defines`:

```json
"continuesDefinition": {
  "definedBy": "ib2-authorized-ibcs",
  "anchor": {
    "sourceId": "cfr-49-172.102",
    "citation": "§ 172.102 table 2, row blank in column 1 below row [column 1 = \"IB2\"]"
  }
}
```

It means **this passage adds one defining rule to the one direct vocabulary term
`definedBy` defines**. The continuation carries neither `vocabulary` nor `term`; the canonical
reader inherits both from that target. The target must exist in the same corpus, have exactly one
direct `defines` declaration, and not itself be a continuation. The continuation may not also
carry `defines`. Several entries may continue one direct definition, but chains, multi-term
targets, and one continuation joining several terms are deliberately unsupported until a corpus
forces them.

**The `anchor` is a structural witness, not evidence.** It must resolve to the continuation's
own passage in a way that also identifies the directly defining passage. For the case that forced
0046, the section locator checker requires a `row blank ... below row [...]` locator: that
locator must resolve to the same table row as this entry's ordinary `locator`, and its
`below row [...]` anchor must resolve to the same row as `definedBy`. This lets IB3 retain its
better ordinary column-2 row key while separately proving that its additional-requirement row is
the one below the IB3 row.

0043 remains structural only: a blank-row locator does not imply continuation merely by existing.
0045 also remains literal: `check-map.py --only defines` still requires a direct
`defines.term` verbatim in **that entry's own evidence**.

**The relation is a semantic choice, not an unresolved hypothesis.** In this contract version an
entry carrying `continuesDefinition` may not also carry `ambiguity.fate: unresolved`. Where the
source is still ambiguous about the association — Trial 10's blank code cells are the forcing
case — the entry stays `clarity: ambiguous` but uses `fate: decision` and names the record that
made the reading. That distinction says both things honestly: the corpus leaves the convention
implicit, and the map has chosen one interpretation strongly enough to make it operative.

The `definition-continuations` check validates the relation's map-level shape, target, and this
cross-field fate rule; the corpus locator checker validates its structural witness. A grammar with
no implemented structural witness cannot use the relation yet.

The field is optional in schema version 1. Existing maps that omit it keep exactly their prior
meaning; this is the same additive versioning treatment used for `defines`.

### `status`

```
mapped       enumerated and classified; not yet worked
blocked      a dependency is unmet
implemented  in the engine, naming the tests that prove it, each shown to fail
declined     no implemented path at all: scope is out, the rule is unreadable,
             or nothing about it was built
```

`status` answers **has the engine built this entry**. `ambiguity.fate` answers **what happens
at runtime when the declining case is reached**. They were coupled and are not
([0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md)):
`implemented` with `fate: unresolved` is legal and means *built, and declines the stated
case*. `must-play-whole-throw` is the instance — the engine implements the compulsion and
declines only where two maximal plays are incomparable, which is neither `declined` nor a
clean `implemented` under the old coupling.

`implemented` requires the verdict, and the verdict is **the tests the entry names**. An
`implemented` entry carries `tests`, non-empty, and every item names a test and records the
`mutation` that turned it red — what was changed in the engine, for that test to fail. Code
without them is `mapped`, whatever the repository contains — otherwise the map records intent
rather than fact, and its whole value is that it records fact.

**A `mapped` entry declines, even when its code exists.** Built but unproven is still `mapped`,
and row 2 of the correspondence table holds for it as written: the engine returns
`UnsupportedRule` for that entry until a test that has been seen to fail exists and the entry
is `implemented`. The code stays behind the decline; it does not answer. `mapped` keeps one
runtime meaning, so the table stays true without a list of exceptions to it. Decided on
[#47](https://github.com/brandonifco/rules-factory/issues/47): refuse until proven.
`check-map.py` cannot enforce this. The map records no code, so an entry that is built and
unproven looks exactly like one that was never built. Whether the engine actually declines is
checked in the engine, against its own runtime.

**Where `fate: unresolved`
accompanies it, the verdict covers every case except the one `ambiguity.question` names, and the
declining case ships a test** — which is one of the tests named. **Or the engine's owner has ruled
on part or all of that case** ([0027](decisions/0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md)).
Then the engine's overlay file for that entry (`overlay/<entry id>.json`) carries `rulings` and
`declines` beside its `tests`. Each ruling
quotes the part of `question` it answers and names the tests that show it. Each decline quotes a
part the engine still declines and names the test that shows the decline. Between them, the quoted
spans cover the whole question. `declines: []` declares the question fully ruled, and then no
declining test is owed. Neither key is merged into the map. The factory checks both against the
map on every `produce` and in the engine's gate.

```json
"tests": [
  { "test": "WholeThrowTests.Where_either_die_alone_can_be_played_but_not_both_the_throw_declines",
    "mutation": "Let the engine play the higher die when only one of two is playable; this test went red." }
]
```

Decided on [#2](https://github.com/brandonifco/rules-factory/issues/2). Until then `implemented`
was a word someone typed: 26 backgammon entries claimed it in the engine's copy with nothing
behind any of them. Every real defect this project has found in its own checks was found by
mutation — five tests that could not fail, a checker counting an entry it had not checked — and
none by reading. This makes that practice the schema. The same answer as rail E below and as a
derived consequence (#16): **the artifact is the test.**

**A placeholder is not a mutation.** Two checkers refuse an `implemented` entry whose test records
one: an engine's gate (`scripts/map-overlay.py`, the recipe at
`tools/factory/recipe/map-overlay.py`), on the map the engine merges; and the checker a published
map package carries (`tools/mapvalidator/mutation.py`, and the `check-map.py` built from it),
before any engine merges the map at all. They refuse a test that records
`PENDING`, `TBD`, `TODO`, `none`, `n/a`, `scratch`, `placeholder`, `xxx`, `unknown`, `later`,
`fixme`, `wip`, `?` or `-` — or **one word repeated** — or anything shorter than **three words and
twelve characters**. All three are applied to the mutation after it is normalised: NFKD, combining
marks and format characters removed, whitespace collapsed, punctuation and symbols stripped from
both ends by Unicode category, and casefolded. So `Pending.`, `--`, `""`, `“TODO”`, `ＴＯＤＯ`, `TÓDO`
and a `TODO` with a zero-width space inside it are all the same word. The gate's refusal names the
entry, the test, the string, where the record lives and `tools/re-produce.sh`; the published map's
names the entry, the position in `tests`, the test and the string.

Words are counted **with repeats**, because a word may legitimately appear twice: ``Increment
`increment`; fails.`` is honest evidence about a variable named `increment`. Distinctness is only
the placeholder rule's business — the whole mutation is a placeholder, or every distinct word in
it is — and the separate "one word repeated" refusal is what catches `TODO TODO TODO` when the
copies are spelled in a script the set does not contain, such as with a Cyrillic `О` for a Latin
`O`. **No confusable mapping is done and none is claimed**, so the claim is exactly this: repeating
one spelling is refused whatever script the spelling is in, and mixing spellings to evade
(`TODO TОDO TODО`, three different ones) is not something this floor stops.

**The rule is written twice, on purpose, and held to itself by a test.** The recipe is vendored
into a produced engine, where it is a standard-library script with none of this repository on the
path, so it may import nothing of the factory's; and [0032](decisions/0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md)
forbids the reverse — the map's verifier does not import the factory's consumer code. Moving the
rule into `tools/mapcontract/` would not help either: the contract states what a field means and
judges nothing, and this judges. So there are two copies, and
`tools/tests/test_placeholder_mutation_is_one_rule.py` loads both and asserts that every constant
is equal, that the five functions are the same code (compared as syntax trees with docstrings
removed, so the prose may differ and the behaviour may not), and that both return the same verdict
over one table of strings. Changing either copy alone turns that test red and names the constant,
the function or the string that diverged. Filed as
[#240](https://github.com/brandonifco/rules-factory/issues/240).

**The gate reads the merge, not the overlay.** `tests` is a field of the merged entry, and a package map
may carry one, so checking only the overlay would leave an implemented entry whose evidence came
from upstream unexamined — the same shape of hole. Filed as
[#239](https://github.com/brandonifco/rules-factory/issues/239): the first implementer of
`tax-121-principal-residence` had to produce twice, because a handler cannot compile until a
re-produce marks the entry `implemented`, so it wrote `PENDING`, produced, ran the real mutations
and produced again — and `validate.sh full` passed on the intermediate run. The threshold is set
an order of magnitude below the shortest real mutation either of the factory's engines records
(20 words, 159 characters), because refusing an honest mutation blocks work and invites padding,
which is worse than a placeholder slipping through.

**It is read after the merge is built,** which is after rules 1 and 2 and the owner's rulings have
held. An overlay that breaks one of those is refused there and its mutations are never looked at,
so a refusal that names no mutation is not a report that the mutations are fine — it is a merge
that could not be read yet. Fix what is named and run it again.

**What it refuses is an unfilled placeholder, and nothing more.** It cannot tell whether the edit
was made, whether the test went red, whether the mutation was a good one, or whether the sentence
was copied from another entry; `not yet recorded` passes it, and so does a real mutation typed by
someone who ran nothing. That part rests on the implementer's word, as it did before — see
immediately below. Both refusals say so in as many words: *it cannot tell whether the edit was
made or the test went red.*

`check-map.py --only status` enforces what a map alone can show: `tests` is present and
non-empty on every `implemented` entry, and wherever it appears each item has a non-blank `test`,
a `mutation` that is not an unfilled placeholder, and no test is named twice. **What it cannot
show:** that a named test exists or ran. That is the engine gate's check, against the engine's own suite. And a recorded
mutation proves *one* way of breaking the rule is caught — an entry can name one weak test with
one easy mutation and pass. What is removed is the state of claiming conformance with nothing
behind it. The mutation is recorded, not re-run; whether a gate ever re-runs them is a separate
decision.

The cost of decoupling, stated where the claim is: after it, `fate: unresolved` means the
engine declines for *at least one* input, not for every input, and nothing distinguishes an
entry that declines one shape of throw from one that declines everything. The totality claim
is weaker than it was. An engine whose overlay carries `rulings` or `declines` for the entry
(0027) now says which parts of the question it declines and which its owner answered. Every
other engine says neither, and what the factory can check stops at the quoted words, not at
whether the engine's split matches the question's real parts.

**An entry whose correct reading is surprising names the test that proves it.** Not a field —
a flag saying "this is surprising" is unfalsifiable. `bearing-off-highest` is clear, correct,
and the opposite of what a modern player expects, and the useful artifact is the one test in
the suite that fails under the reading a reasonable person would have implemented. The entry
names it in `note` while it is `mapped`, and among its `tests` once it is `implemented`.

## The map and the engine agree, or the map is wrong

The map's classifications correspond exactly to the kernel's closed `UnresolvedReason`
vocabulary. This is the property that makes the map load-bearing rather than documentation:

**Rows are checked in order and the first match wins.** Not-in-scope and not-built dominate;
the rest describe what a *built* entry returns. Without an order, every `status: mapped` entry
carrying `fate: unresolved` matches two rows — eleven entries across the three maps today —
and the invariant is unwritable in either direction.

| # | A map entry that is… | At runtime the engine returns… |
|---|---|---|
| 1 | `scope: out` | `OutsideCurrentScope` |
| 2 | `status: mapped` or `blocked` — read, not built | `UnsupportedRule` |
| 3 | carries `definedElsewhere` | `MissingRulesData` |
| 4 | carries `beyondAdapter` | `MissingRulesData` |
| 5 | an `operation` whose `value` dependency is unimplemented | `MissingRulesData` |
| 6 | `ambiguity.fate: unresolved` | `RequiresInterpretation` |
| 7 | two implemented entries with no entry for their combination | `UnsupportedInteraction` |
| 8 | `kind: assertion` | **nothing — the engine demands the value and proceeds** |

`absentFrom` adds no row. An engine asked about a rule the corpus does not state answers
`OutsideCurrentScope`, the same as one it read and declined — which is why 0009 records the
difference in a field only the map reads rather than in a third `scope` value the engine would
have to share. The distinction the map preserves is the mapper's, not the runtime's.

A gate that is `scope: out` adds no row either. The table classifies an entry by its own fields.
An entry suspended by an out-of-scope gate answers by its own row while the caller states that the
gate does not hold, and `OutsideCurrentScope`, citing the gate, while the caller states that it holds
([0021](decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md)).

Row 8 is the one that is easy to get wrong. An assertion is not a failure to resolve; it is a
parameter. An engine returning `RequiresInterpretation` where the corpus named a decider is
declining a job the corpus gave it the means to do — and it discards whatever bounds the
corpus *did* state, which is what reading `stake-multiplier` as an ambiguity costs.

So an engine's honest answer about what it cannot do should be derivable from its map, and
an unresolved result that does not correspond to a map entry means something was implemented
without being mapped. That is a checkable invariant, and it is the first thing the factory
should enforce once it exists.

**The map declares no types, and the engine's typed contract says only what the map does.** No
field names an entry's inputs, outputs, units or value type: a parameter is not a rule and gets
no entry, and `dependsOn` is not a runtime input. So the factory's generated contract
([#76](https://github.com/brandonifco/rules-factory/issues/76), `tools/factory/semantics.py` and
`tools/factory/contracts.py`) types
what the map fixes and nothing more. Each entry has a request type of its own, so a request for
one entry cannot be handed to another. An assertion's request carries the caller's value, which
is what row 8 resolves to, and its generated entry carries `AssertedBy`, who may assert it (0025). The request type is partial, so what the map leaves unnamed, an
operation's inputs, the engine declares on it in its own code
([#93](https://github.com/brandonifco/rules-factory/issues/93)), and the typed entry point passes
that request, inputs included, to the handler. Each entry's handler is a declared method, so an `implemented` entry
that needs one (any not on row 8) and lacks it does not build. The value itself, and every output, is `object` until a field
declares otherwise.

## The corpus manifest

Beside the entries, the corpora they cite:

```json
{
  "schemaVersion": 1,
  "corpora": [
    {
      "sourceId": "cfr-26",
      "title": "Title 26, Code of Federal Regulations",
      "adapter": "ecfr-xml",
      "locatorGrammar": "section-designation",
      "contentHash": "…64 hex…",
      "hashDerivation": "ecfr-xml",
      "asOf": "2019-03-14",
      "boundaryPolicy": "pin-in-repo",
      "licence": "public-domain",
      "verification": "committed-copy",
      "committedPath": "title26.xml",
      "quotation": "verbatim",
      "randomness": "none"
    },
    {
      "sourceId": "core-rules",
      "title": "Core Rulebook",
      "edition": "First printing",
      "adapter": "pdf",
      "locatorGrammar": "printed-page",
      "contentHash": "…64 hex…",
      "hashDerivation": "pdf-bytes",
      "boundaryPolicy": "never-commit",
      "licence": "commercial",
      "verification": "local-copy",
      "envVar": "CORE_RULES_PDF",
      "quotation": "withheld",
      "randomness": "seeded"
    }
  ]
}
```

`hashDerivation` and `boundaryPolicy` are the two fields most likely to be thought
redundant, and both are load-bearing. A digest without its derivation does not say what it
covers. A boundary policy is a property of the licence, and the two engines this method was
derived from answer it in opposite directions — one commits its extracted corpus because the
SRD is CC-BY, the other commits nothing because its rulebook is commercial.

`verification` and `quotation` are the same question asked of a map's *consumers*, and are
answered per corpus for the same reason ([0013](decisions/0013-verification-posture-belongs-to-the-corpus.md)):

- **`verification`** — how anyone checks the baseline hash. `committed-copy`: the bytes are at
  `committedPath` beside the manifest, and CI can verify them. `local-copy`: they are not
  committed; a holder of a legal copy points `envVar` at it, and everyone else — every CI run
  included — is told `NOT VERIFIED` with the reason, never `ok`. A `never-commit` corpus is
  always `local-copy`; a `pin-in-repo` corpus that commits only a derivation may be too.
  The factory refuses a `local-copy` corpus at every step: `pack-map.py` will not pack its map,
  and intake will not produce from it.
- **`quotation`** — whether a map may carry verbatim spans of the corpus. `verbatim`, or
  `withheld` where the licence forbids it: since `evidence` became a span, a map carries a few
  hundred sentences of its corpus, and for a licensed corpus **the map is itself the
  redistribution question**. A person declares it; nothing infers it from `licence` or
  `boundaryPolicy`.

**`randomness`** is the same kind of fact about the engine
([0019](decisions/0019-randomness-is-declared-by-the-corpus.md)): whether the rules call for
chance. `none`: a conforming engine draws no random value, and its gate refuses
`RulesKernel.Randomness`. `seeded`: it may draw, only through the kernel's seeded, replayable
source; the factory pins that package at the kernel's version and references nothing. A person
declares it from the rules. Nothing infers it, and a missing value is a failure, never `none`. Which
entries draw, and how many of what, is the map's `draws` field, which is refused under `none`
([0025](decisions/0025-an-assertion-names-who-asserts-it-and-an-operation-names-what-it-draws.md)).

**`licence` decides whether the factory uses the corpus at all**
([0028](decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)).
The factory admits only a corpus whose licence permits committing and publishing its text and its
map. The class is read from the licence's leading
identifier: `public-domain` or `public-domain-<whose>` is public domain, and `CC-BY-4.0` or `CC0-1.0`
is open. Any other licence, or none, is refused by intake (`produce`, `verify`, `provenance`) and by
`pack-map.py`, naming 0028. `core-rules` in the example above is such a corpus: the schema can
describe it and `check-map.py` checks its declarations, but the factory neither packs its map nor
produces from it. The same holds for `never-commit`, `local-copy` and `withheld`, which no corpus the
factory admits uses today.

`check-map.py --only postures` requires all three on every admitted corpus, refuses a `never-commit`
`committed-copy`, a `local-copy` with no `envVar`, a `committedPath` that is not a file, and any
`evidence` on an entry whose corpus is `withheld`. It hashes nothing; verifying the bytes and
reporting the posture in force is an engine gate's job.

**`quotedText`** says what a quote is verbatim of when the committed text is derived from what
was published
([0024](decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)):

```json
"quotedText": { "derivation": "srd-5.2.1-pdftotext-24.02.0-page-marked", "extractedFrom": "SRD_CC_v5.2.1.pdf" }
```

`derivation` must be the corpus's `hashDerivation`, since quotes are held to the bytes
`contentHash` covers and to no others. `extractedFrom` names the published file. It need not be
beside the manifest, since a map package does not carry it; the derivation's own check holds the
text to it. A corpus without it is quoted as published, and
none of its entries may carry `extraction`.

`references` lists corpora this one defers to — a regulation citing another title, a
rulebook citing a supplement — each marked admitted or not. Those references are the
boundary of any engine built from the corpus, and naming them makes that boundary
inspectable rather than inferred from whichever entries happen to be declined. A broad
part-level reference is a boundary declaration for its child sections; it is not necessary to
duplicate every section pointer beneath it. A section-level reference remains exact.

The Phase-1 list is historical evidence. If Phase 2 discovers an external corpus boundary it
omitted, 0047 adds `referenceAmendments`: an additive, mapping-time correction whose references
must remain `admitted: false`. Consumers read the operational union of `references` and those
amendments. An amended reference must have exactly one coherent source/citation identity, cannot
repeat an existing boundary, and cannot target a corpus the manifest already admits. The correction
cannot carry baseline, date, licence, adapter or verification fields, so correcting a boundary
cannot silently rewrite what was admitted or which bytes were pinned.
In the first trial, three of twelve sections deferred their meaning to a corpus that had not been
admitted.

```json
"references": [
  { "sourceId": "cfr-49-171", "citation": "§ 171.8", "admitted": false },
  { "sourceId": "air-almanac", "admitted": false }
]
```

`pointerPhrases` lists the words this corpus points at another of its passages with
([0026](decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)).
An item is a literal phrase or `{"regex": "..."}`. Both match case-insensitively, and a literal
matches across any run of whitespace. `check-map.py --only cross-references` reads them, in addition
to its built-in list, for entries citing this corpus and no other. Derive them from the corpus's
text rather than from memory. Two of the SRD's, which came from searching its 364 pages for "see",
"explained in" and "later in", and one of Hoyle's:

```json
"pointerPhrases": [
  { "regex": "\\(see [^)]+\\)" },
  { "regex": "“[^”]+” (?:earlier|later) in “[^”]+”" },
  "as in the earlier stage of the game"
]
```

Omitting it is allowed only while the built-in list detects at least one pointer in the spans the
map quotes. A corpus on which it detects none fails. A corpus that really points at nothing
declares `"pointerPhrases": []` with `pointerPhrasesReason`, a sentence saying why. The reason is
refused anywhere else, and so are a regex that does not compile and a regex that matches the empty
string.

`asOf` is present only for a corpus that is revised over time. Absent means timeless, never
unknown. It pins which text is in force and nothing more — a rule may carry dates of its
own, which are ordinary operations over a date the caller supplies.

## Where the map lives

**In the factory, published as a versioned package; never copied into an engine**
([0015](decisions/0015-a-map-is-published-as-a-versioned-package.md)). Each map is a NuGet
package, `RulesFactory.Maps.<MapName>`, carrying `corpus-map.json`, the manifest entries of
the corpora it cites, the `tools/check-map.py` its consumer runs, and `map/verification.json`.
The verification record binds the SHA-256 of those three package artifacts to every cited corpus's
sourceId, hashDerivation and verified contentHash; intake compares the record to the actual package
members and to the corpus bytes it resolves ([0048](decisions/0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md)).
A version therefore asserts one `schemaVersion`, one principal corpus baseline, and the
manifest-pinned baseline of every other corpus the map cites ([0039](decisions/0039-the-manifest-pins-every-corpus-a-map-cites.md)).

**What a consumer owns** is an overlay of three fields per entry, `status`, `implementedIn` and
`tests`, because those are build facts only the engine can know, and they are only true of a
particular engine commit. It is one file per entry, `overlay/<entry id>.json`, read in the package
map's entry order ([#247](https://github.com/brandonifco/rules-factory/issues/247)): an entry's
evidence is its own file, so two entry branches never write the same one. The factory is canonical
for everything else. The engine's gate checks
that the overlay names only entries the package has and sets only those three fields, and runs
the package's own `tools/check-map.py --phase consumer` on the merge, never a copy
([#51](https://github.com/brandonifco/rules-factory/issues/51)). Any other difference is drift.

## Open questions

Recorded rather than decided. The first trial —
[examples/faa-part-107](../examples/faa-part-107/README.md) — answered some and sharpened
the rest.

**Granularity.** Partly answered. Twelve sections of regulation produced twenty-four
entries, close to 2:1, and the split that mattered was separating a stated figure from the
comparison against it: one paragraph of § 107.51 holds three distinct figures, and a single
entry would have lost two of them. The dependency graph remains the arbiter for the harder
cases.

Open questions are tracked as issues so they are worked rather than admired:

- [#5](https://github.com/brandonifco/rules-factory/issues/5) — `dependsOn` conflates
  implementation order with runtime precondition. Decided:
  [0003](decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md) adds `gatedBy`.
- [#32](https://github.com/brandonifco/rules-factory/issues/32) — a gate that suspends seven
  entries was named by none of them, and the one field could not say which way a gate points.
  Decided: [0011](decisions/0011-a-gate-has-a-direction.md) splits `gatedBy` into `enabledBy`
  and `suspendedBy`.
- [#61](https://github.com/brandonifco/rules-factory/issues/61) — a waiver suspends rules from a
  section outside the map's slice, and `suspendedBy` could not name it. Decided:
  [0021](decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md). The gate is a `scope: out`
  entry, and whether it holds is a fact the caller states and the engine never infers.
- [#31](https://github.com/brandonifco/rules-factory/issues/31) — an entry claimed a rate the
  corpus implies and never states. Decided:
  [0012](decisions/0012-a-fact-the-corpus-implies-is-a-derived-entry.md) adds `derivedFrom`; a
  derived entry cites nothing.
- [#15](https://github.com/brandonifco/rules-factory/issues/15) — where a corpus lives when a
  map moves into an engine. Decided:
  [0013](decisions/0013-verification-posture-belongs-to-the-corpus.md) extends 0002 — each
  corpus declares its `verification` posture and its `quotation` policy.
- [#6](https://github.com/brandonifco/rules-factory/issues/6) — a standard is not a gap.
  Decided: [0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md) — a delegated
  standard is `kind: assertion`, and it is an entry of its own.
- [#24](https://github.com/brandonifco/rules-factory/issues/24) — six reasons an entry is not
  a plain rule, and three fields carrying them. Decided:
  [0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md).
- [#7](https://github.com/brandonifco/rules-factory/issues/7) — an entry beyond the
  adapter's reach has no field to say so. Decided:
  [0004](decisions/0004-adapter-reach-is-a-property-of-the-entry.md) adds `beyondAdapter`.
- [#25](https://github.com/brandonifco/rules-factory/issues/25) — a conflict is a relation
  between entries and nothing records it. Decided:
  [0007](decisions/0007-a-conflict-is-a-question-not-a-pair.md) adds `ambiguity.conflict`, and
  rules that the relation is a grouping rather than a pair.
- [#18](https://github.com/brandonifco/rules-factory/issues/18) — `evidence` held a summary, so
  no citation was checkable and thirteen wrong ones survived a build. Decided above: `evidence`
  is a contiguous verbatim span and the summary moves to `note`.
- [#29](https://github.com/brandonifco/rules-factory/issues/29) — three states, two words for
  them. Decided: [0009](decisions/0009-absence-is-a-verdict-with-evidence.md) adds `absentFrom`,
  and rules that an absence is an entry rather than a manifest record because `references` is
  bounded by the corpus and absence is not.
- [#20](https://github.com/brandonifco/rules-factory/issues/20) — `scope: out` applied to a
  section cost the map the number of faces on a die. Decided:
  [0009](decisions/0009-absence-is-a-verdict-with-evidence.md) — `scope` is per rule, and
  `extent` coverage is what records that a section was read.
- [#28](https://github.com/brandonifco/rules-factory/issues/28) — a carve-out with no entry in
  either direction. Decided: [0009](decisions/0009-absence-is-a-verdict-with-evidence.md) adds
  `crossReferences`; the Part 107 data fix is
  [0010](decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md) § 3 —
  `night-waiver-termination`, `scope: in`, because a rule whose condition can no longer be met
  is not a rule that is no longer in force.
- [#11](https://github.com/brandonifco/rules-factory/issues/11) — nothing used
  `kind: assertion`, and the half about facts a *person* asserts outlived 0005 and 0008.
  Decided: [0010](decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md) — whose fact
  it is does not decide the kind, so the family dissolves into assertions and gaps under the
  gate that already exists, and no new `kind` or field is added.

- [#58](https://github.com/brandonifco/rules-factory/issues/58),
  [#59](https://github.com/brandonifco/rules-factory/issues/59),
  [#60](https://github.com/brandonifco/rules-factory/issues/60),
  [#62](https://github.com/brandonifco/rules-factory/issues/62) — four schema points the Part 107
  blind second mapping found unclear. Decided:
  [0020](decisions/0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)
  — a `section-designation` extent is a list of sections and every locator cites inside it;
  "introductory text" is in the grammar and means the lead-in only; the manifest is never inline;
  and `definedElsewhere` alone answers a pointer to an unadmitted corpus.
- [#113](https://github.com/brandonifco/rules-factory/issues/113),
  [#114](https://github.com/brandonifco/rules-factory/issues/114) — in the first PDF, a quote is
  verbatim of the extraction and not of the page, and a page extent could not end mid-page.
  Decided:
  [0024](decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)
  — the manifest declares `quotedText`, an entry the extraction garbles declares `extraction`
  with its rendered reading (printed as not verified), and a page extent may name `endsBefore`.
- [#115](https://github.com/brandonifco/rules-factory/issues/115),
  [#116](https://github.com/brandonifco/rules-factory/issues/116) — trial 7 found no field for a
  term the same corpus defines outside the slice, and a pointer phrase list that detected none of
  the SRD's pointers. Decided:
  [0026](decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)
  — a `scope: out` entry named by `crossReferences`, and by `dependsOn` where it modifies the rule;
  `definedElsewhere` never names an admitted corpus; each corpus declares its `pointerPhrases`, and
  a corpus on which nothing is detected and nothing is declared fails.

- [#117](https://github.com/brandonifco/rules-factory/issues/117),
  [#118](https://github.com/brandonifco/rules-factory/issues/118) — an assertion named nobody who
  may make it, and an ambiguous draw count changes a replay. Decided:
  [0025](decisions/0025-an-assertion-names-who-asserts-it-and-an-operation-names-what-it-draws.md)
  adds `assertedBy`, `draws` and `ambiguity.affectsDraws`, each anchored in the corpus's words.

**Where a decline's runtime reason lives.** Opened by 0004, answered by 0005: an entry whose
meaning is fixed in an unadmitted corpus takes `definedElsewhere`, parallel to
`beyondAdapter`, and the `ambiguity` block is no longer a general decline carrier.

**`kind: assertion` is fully adopted.** 0005 settled that the maps were behind the schema,
not that the category was too wide, and reclassified the delegated standards.
[0010](decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md) closes the other half of
[#11](https://github.com/brandonifco/rules-factory/issues/11) — facts a *person* asserts,
in `visual-line-of-sight`, `preflight-actions`, `visual-observer-conditions` and
`over-human-beings` — and the answer is that the family is not a category. It is a mixture
of the two answers gate 3 already gives, and the four entries were mis-split: ten assertion
instances, six gaps, two paragraphs that split inside themselves, and two terms that are part
of another entry's measure. Both Part 107 maps are migrated.

**How the maps got this way is worth recording**, because it was not carelessness.
[method.md](method.md) contradicted itself: Phase 3 said a delegated judgement is an
assertion and Phase 4 said its fate is "almost always a runtime unresolved", naming three of
the four entries. A mapper following Phase 4 produced exactly what the maps contained. A
schema is only as good as the procedure that cites it.

**Who writes it.** The ambition is that an agent produces a first draft from the corpus and
a human reviews the decomposition. Whether the first draft is good enough to be worth
reviewing is unknown, and is the main thing the first real run will test.

**Drift.** The map claims things about the engine (`status`, `implementedIn`) that the engine
could contradict. The correspondence table above is checkable and should become a check.
