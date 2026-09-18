# 0035 — A rule stated in a table row is cited by its row, a row is named by a cell that identifies it, and the extraction of a row keeps its columns

## Status

Accepted — 2026-09-17. Records the decision on
[#280](https://github.com/brandonifco/rules-factory/issues/280), forced by the spike on
[#261](https://github.com/brandonifco/rules-factory/issues/261), which blocks trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)).
**Extends [0020](0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)**,
which fixed what a section citation may name and what a section extent lists,
**[0024](0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)**, whose
rule about what a quote is verbatim *of* is applied here to a row, and
**[0030](0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md)**, which
identified a repeated passage by the container its citation names and could name no container for
a table row. The specification is [corpus-map.md](../corpus-map.md) and
[mapper.md](../mapper.md).

## Context

The eCFR serves the Hazardous Materials Table as ordinary table markup, and the geometry survives
it intact: 3,687 body rows, **14 `TD` per row with no exceptions**, empty cells present as empty
`TD`, and the 17 `THEAD` cells printed once at the top. What does not survive is the indexer.
`examples/faa-part-107/check-locators-section.py` walks the direct `P` and `EXAMPLE` children of a
`DIV8` and nothing else, and #261 measured what that sees:

| Section | Text in the section | Indexed | Share |
|---|---:|---:|---:|
| § 1.121-1 (trial 9) | 23,178 | 23,016 | **99.3%** |
| § 172.101 | 449,986 | 29,584 | **6.6%** |
| § 172.102 | 159,251 | 9,079 | **5.7%** |

The 420,000 characters it cannot see are the table. A column 7 pointer runs **from a table cell to
a table row** — `IB2` and `T4` are stated in rows of § 172.102's own tables — and a mapper could
cite neither end of it. That is a level below #208's "the phrase list detects nothing": the
passage the pointer resolves to is not in the index at all.

Three further measurements bound what an answer may be:

- **A row has no designation, and 59 rows are not unique.** Flattened, 3,687 rows produce 3,488
  distinct strings, and one string appears five times. 0030 settles a repeated passage by naming
  the container its citation names, and a table row had no container to name.
- **Flattening destroys which cell is blank.** 1,112 rows have exactly one empty cell, 419 have
  thirteen (the `Forbidden` entries), and one row is empty end to end. Joined into a sentence, a
  blank column 1 symbol and a blank column 5 packing group are the same absence.
- **A unit the inventory counts as reached when one quote lands in it** would report a 3,687-row
  table as read on a single citation. That is the defect
  [#270](https://github.com/brandonifco/rules-factory/issues/270) is open about, at a scale that
  makes it unusable.

## Decision

**A rule stated in a table is cited by its row; a row is named by a cell that identifies it, not
by where it sits; and the extraction of a row keeps its columns.** Four parts.

### 1. The extraction of a row is its cells in column order

A row's text is its cells joined by ` | `, **empty cells kept as empty**, normalised like every
other passage the checkers index:

```
| Acetal | 3 | UN1088 | II | 3 | IB2, T4, TP1 | 150 | 202 | 242 | 5 L | 60 L | E |
```

`evidence` is then one contiguous verbatim span of *that*, which is 0024's rule applied where it
has never been applied. This makes a blank cell quotable: an empty cell reads as the two
separators around it, and a missing symbol and a missing packing group are no longer the same
absence.

### 2. A row is cited by `column = value` pairs, and an ambiguous citation is refused

```
§ 172.101 table 3, row [column 2 = "Acetal"]
§ 172.101 table 3, row [column 2 = "Acetal"], column 7
§ 172.101 table 3, row [column 2 = "Ammonia, anhydrous"; column 1 = "I"]
```

- The **table** is named by its position in the section, counted from 1 in document order, which
  is mechanical and never absent. Its caption, where it has one, is what the reader sees in the
  map's `note`.
- The **row** is named by `column = value` pairs in the corpus's own column numbering — the
  numbering § 172.101(b)–(l) uses to explain itself and the numbering printed in the table's own
  headings. The pairs are a conjunction and their order is not part of what they name. The checker
  resolves them against the table and requires **exactly one** row: two matches is a refusal and
  never a first hit, answered by a discriminating column.
- A **cell** is named by its column, `9A` and `10B` included, because the corpus splits and names
  them. Where a citation names a column, the quote is held to that cell and not to the whole row.
- **The columns are the labels the table's own headings print, and a heading split into
  sub-columns names no column of its own**: where the headings print `(8)`, `(8A)`, `(8B)` and
  `(8C)`, the columns are the three leaves. **Split means the parent's label plus letters**, never
  a string prefix: `10A` is a sub-column of `10`, and `1` is a sub-column of nothing. Read as a
  prefix, `1` is swallowed by `10A`, the Hazardous Materials Table's 14 columns come out as 13,
  and the table silently falls back to position — the one corpus this decision was written for,
  addressed wrongly, with `column 9` naming column 8B.
- **Where the markup does not carry the geometry, the table addresses nothing.** A cell that
  spans rows or columns, or headings whose leaf labels do not number the cells one for one, leave
  no honest way to say which column a cell is in: the table is **refused** — by the adapter, which
  will not enumerate it, and by the checker, which will not resolve a citation into it — and a map
  that does not read it excludes it with a reason. A label printed twice names no column either,
  and such a table is numbered **positionally**, which is what the markup does say; so is a table
  that prints no numbering at all. Each table says which of the two numberings it got.

Ordinals were the obvious alternative and are the wrong answer; see below.

**A heading row is a row.** The column semantics of a regulation live in its headings —
§ 172.102(b)(1)–(8) explains what a code shape means, and the HMT prints its 17 heading cells once
for 3,687 rows — so the passage a map most needs to cite must be citable:
`row [column 1 = "(1) Symbols"]` names the heading row of table 1. It is also what keeps a
heading-only table from passing every check by holding no unit at all.

**A row quote carries no ellipsis.** `evidence` is one contiguous verbatim span
([corpus-map.md](../corpus-map.md)), and a row is short: an ellipsis inside one elides a column,
and the check then passes over the very cell the entry is about. The row path refuses it. (The
prose path's ellipsis handling is older than this decision and is proposed rather than settled —
[#18](https://github.com/brandonifco/rules-factory/issues/18),
[#282](https://github.com/brandonifco/rules-factory/issues/282).)

### 3. `table-row` is a unit

Added to `protocol.UNITS` and `corpus.KINDS`, and enumerated by the `ecfr-xml` adapter with the
key above — a row's unit key *is* the citation that names it, so a rejection, an inventory line
and a locator all say the same words. The whole-table `table` unit stays, for a table cited as one
thing.

Where an extent takes a table whole, the adapter keys each row itself: the cell that narrows the
table furthest first, then the cell that narrows what is left the most, until one row is named —
as many cells as it takes, and not a cell more. An empty cell is a value a key may name, because a
blank column 1 symbol is a fact about the row and two rows differing only in one are not alike; it
is taken only where it narrows further than a cell that says something, since a row named by what
is absent from it is the weaker name. A cell holding a `"` is passed over altogether, because no
key written from it could be read back. What remains is a **refusal**: a row another row matches in
every nameable cell — the same refusal the citation gets, made where the citation is written.

### 4. An extent that slices a table names the rows it takes, and accounts for every table it does not

```json
"extent": {
  "unit": "section-designation",
  "sections": ["§ 172.101", "§ 172.102"],
  "tables": [
    { "section": "§ 172.101", "table": 3,
      "rows": [ { "column": 2, "is": "Acetal" } ] },
    { "section": "§ 172.101", "table": 1,
      "excluded": "label substitution; no mapped row invokes it" }
  ]
}
```

**Every table in every cited section appears, with `rows` (a list of keys, or `"all"`) or with
`excluded` and a reason.** A table left out fails. That is 0020's own principle — a map may not
quietly shrink its extent to match what it happened to read — applied to the unit that now exists.
An in-scope entry citing a row the slice does not take is cited outside what the map claims to
have read, exactly as an entry citing an unlisted section is.

### Where each half is held

The rule spans a boundary, and each half is checked where its evidence is:

| Held by | What it holds |
|---|---|
| `examples/faa-part-107/check-locators-section.py` | the table geometry, the row a citation resolves to, and the quote against the row or the cell. A key that names 0 or 2 rows, a table or a column the section does not print, a table whose geometry the markup does not carry, a quote that is not a span of the row, a quote that elides its middle, and a corpus printing one section designation twice, each fail |
| `tools/mapper/corpus.py` (`ecfr-xml`) | the enumeration: a sliced table's rows as `table-row` units, and the **refusal** of a table the extent passes over in silence, a table whose geometry is unreadable, a slice of an uncited section or an absent table, a key that resolves to 0 or 2 rows, and a corpus printing one section designation twice |
| `tools/check-map.py --only extent` | the shape of `tables`, and that every in-scope row citation names a row the slice took. It has no corpus, so *which* tables a section prints is not its question |

## Alternatives considered

**An ordinal — `row 412`.** Rejected. A row's position is not stable across an amendment and this
corpus amends constantly, so an ordinal silently re-points at a different material, where a key
that stops resolving is a check going red for the right reason. It also asks the mapper for a
number nobody can verify by reading the page, which is the ground 0030 rejected an `occurrence`
selector on.

**Extending the flattened text until it is unique**, which is what 0030 replaced for a page-marked
corpus. Rejected for the same reason and one more: 59 of the 3,687 rows are not distinguishable by
their flattened text at all, so for those there is no span to extend to.

**A flattened sentence per row** — "Acetal, class 3, UN1088, packing group II…". Rejected on the
measurement: 1,112 rows have exactly one empty cell and 419 have thirteen, and a sentence cannot
say which column is blank. It would also make `evidence` the mapper's words rather than the
corpus's, which is the defect `evidence` became a span to fix.

**A `table` unit only, cited as one thing.** Rejected: the inventory would count 3,687 rows as one
unit reached by one quote, which is #270's defect at a scale that makes the measurement useless.
The whole-table unit survives for a table a map genuinely cites as one thing.

**Deriving the extent's tables from the citations.** Rejected by 0020's own argument, which this
extends: a map may not shrink its extent to whatever it happened to read, and a table nobody cited
is exactly the one a reader needs told about.

**Naming a table by its caption.** Rejected: a caption is optional and editorial, a position is
mechanical and always there. The caption belongs in the map's `note`, where a reader wants it.

## Consequences

**No existing path moves, and nothing in any committed map changes.** No eCFR corpus committed to
this repository prints a table, so the enumeration and the locator runs for Part 107, the 2020
temporal map and § 1.121-1 are byte-identical before and after — which was recorded before the
change and compared after it, and again after every correction.

**It was reviewed against the real corpus, and against a second model, before it was merged**
(AGENTS.md §6). Both passes confirmed that no path moved and that a seven-row slice of the real
§ 172.101 enumerates; both found the column-containment defect above, and between them the spanned
cells, the nested table, the heading rows, the duplicated designation and the elided row quote. A
decision whose code is wrong about its own corpus is the defect this repository exists to catch,
and the record says so here rather than in a commit message.

**The punctuation is the issue's, with one adjustment, stated here.** The design comment writes a
row's rendering with its leading and trailing spaces intact (` | Acetal | … | E | `). Every quote
in this repository is compared after whitespace normalisation, so those spaces cannot survive to
be quoted; the rendering is normalised, an empty cell reads as `| |`, and a leading empty cell
reads as a leading `|`. The citation form itself is unchanged.

**A nested table is a table of its section in its own right.** Its rows are its own — the table
that encloses it does not admit them — and the extent accounts for it separately. Taking or
excluding the outer table says nothing about the inner one.

**A section designation the corpus prints twice is refused.** Indexing it keeps one of the two and
drops the other's paragraphs and tables out of the corpus, so every check over them passes by
having nothing to look at — and the accounting this decision adds would rest on that silence.

**A value containing a double quote cannot be written as a row key.** The key's values are
delimited by `"`, and no escape is defined, because no corpus has needed one. A row whose
identifying cell holds a quotation mark is answered by a different column, or by a form a later
decision adds.

**The two grammars stay two files and one grammar.** The section checker reads the citation and
the adapter writes it; `tools/tests/mapper/test_mapper_table_rows.py` holds the adapter's keys to
the checker's parser and both to the same columns, as `test_check_map.py` already holds
`CITE_SECTION` to the checker's own expression. `tools/mapvalidator/extent.py` was 312 lines and
the build holds a module to 300, so the section-designation grammar and the row grammar now live
in `tools/mapvalidator/locators.py`; nothing about what either reads changed.

**What this is not.** Not a new relation, not a new evidence model, and not an answer to any of
#262's six hypotheses. It is the address a table cell did not have. Whether an entry can be
supported by one row's span, or needs the column heading and the referenced provision too, is what
the trial is for, and this deliberately does not prejudge it: a heading row is quotable as a row
of the `THEAD` where the corpus prints one, and nothing here requires or forbids citing it.

**The ambiguous designator this does not touch.** `level_of` raises `Ambiguous` on exactly one
paragraph of § 172.101 — *"(i) Such a change does not apply to the shipment of any package filled
prior to …"*, the amendment transition rule. It is out of scope here and gets its own issue if the
trial needs that paragraph.
