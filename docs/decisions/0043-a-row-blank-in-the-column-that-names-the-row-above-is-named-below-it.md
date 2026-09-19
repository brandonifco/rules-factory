# 0043 — A row the corpus leaves blank in the column that names the row above it is named below that row

## Status

Accepted — 2026-09-18. Records the decision on
[#310](https://github.com/brandonifco/rules-factory/issues/310), forced by trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)) while settling its extent, before
any entry was written.
**Extends [0035](0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)**, whose row key this
reuses for both halves of the address and whose refusal of an ordinal it keeps. The specification
is [corpus-map.md](../corpus-map.md#citing-a-section-in-the-section-designation-grammar).

## Context

§ 172.102 table 2 states `IB2` in two rows:

```
IB2 | Authorized IBCs: Metal (31A, 31B and 31N); Rigid plastics (31H1 and 31H2); Composite (31HZ1).
    | Additional Requirement: Only liquids with a vapor pressure less than or equal to 110 kPa
      at 50 °C (1.1 bar at 122 °F), or 130 kPa at 55 °C (1.3 bar at 131 °F) are authorized.
```

The second row is **byte-identical** to `IB1`'s, so no `column = value` key names either, and
`rows: "all"` was refused outright:

> § 172.102 table 2 holds a row no combination of its cells names: another row holds the same
> value in every column that can be written into a key.

`IB3`'s equivalent survives only by ending with an extra *"except for UN2672"* clause.

**The row is in scope.** One of trial 10's seven selected § 172.101 rows invokes `IB2` in column 7,
and this row states a restriction on what `IB2` authorises. Dropping it from `extent.tables` would
make the declared universe smaller than the rule requires — 0020's rule that a map may not quietly
shrink its extent, one unit down, which is the rule 0035 itself applied to tables.

### The shape is not rare, and one reading of it is confidently wrong

| table | rows | named by no key |
|---|---:|---:|
| § 172.101 table 3, the Hazardous Materials Table | 3,689 | **258** (59 distinct texts) |
| § 172.101 table 4 | 1,356 | 4 |
| § 172.102 table 2 | 15 | **2** |

The Hazardous Materials Table states a multi-packing-group material the same way — the named row,
then one row per packing group with columns 1 to 4 blank — and *Adhesives, containing a flammable
liquid* PG II and III are byte-identical to *Resin Solution, flammable*'s.

### What the markup carries, measured before anything was designed

| candidate | measured |
|---|---|
| `rowspan` / `colspan` | **no.** § 172.102 has 0 `rowspan`; § 172.101's 7 are all in table 3's two-level heading |
| XML grouping | **no.** One `<TBODY>` per table, no grouping per code |
| CSS classes | **no.** The keyed row and the blank one both carry `class="left border-right-single"` |
| the corpus's own prose | **no.** Neither section states the convention anywhere |
| the blank cell | **yes** — `<TD class="left border-right-single"> </TD>`. The corpus writes the column and leaves it empty |

**This is recorded rather than argued away: the corpus never states the convention.** What the
bytes carry is an empty cell the corpus chose to print, and the reading that a row leaving the key
column blank belongs with the row above is the mapper's.

## Decision

**A row the corpus leaves blank in a column an earlier row fills is addressed relative to that
earlier row, which is named by an ordinary row key.**

```
§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]
§ 172.101 table 3, row blank in column 2 [column 5 = "II"] below row [column 2 = "Adhesives, containing a flammable liquid"]
```

### 1. It is mechanical, and it says nothing about meaning

The locator identifies a passage and makes no claim that the row **continues** the anchor. That
reading is the map's, and it belongs in an entry — which is why the grammar says *blank in column*
and *below*, and not *continuation of*. A map may decompose the two rows into two entries, or read
them as one rule it cannot represent; the address is the same either way.

Resolution, in order:

1. the anchor key resolves against the table exactly as 0035 says — **exactly one row**, or refuse;
2. the **run** is the rows immediately after the anchor whose cell in the named column is blank,
   ending at the first row that fills it — and at the first row of another width or one spanning
   part of it, which has no cell in that column to be blank;
3. an empty run **refuses**;
4. the discriminators, where given, are ordinary `column = value` pairs read against the run;
5. **exactly one** candidate resolves. Zero or two **refuse**, and a second match is answered with
   a discriminating column, never with the first hit.

### 2. No ordinal, and no occurrence selector

0035 refused `row 412` because an amendment repoints it silently. That refusal stands, and this is
why the address is anchored to a row a reader can recognise. Every way the corpus can move under it
**fails loudly**, which is the property the ordinal did not have:

| the amendment | the citation |
|---|---|
| deletes the target row | refuses — nothing below the anchor leaves the column blank |
| adds a second blank row under the same anchor | refuses — two match where one must |
| renames the anchor | refuses — the anchor names 0 rows |
| prints the anchor twice | refuses — the anchor names 2 rows |

### 3. The column is the nearest one, then the narrowest

Where a row leaves several columns blank, the column taken is the one whose anchor is **nearest
above**; among those, the one whose **run is shortest**; and among those, the table's own column
order. Both orderings exist because a measurement demanded them, not for elegance.

§ 172.101's Symbols column is blank on **3,139** of its 3,689 rows. Read in the table's column
order, *Adhesives* PG II addresses as `blank in column 1 below row [column 2 = "Acetaldehyde
ammonia"]` — unique, stable, and naming a material twenty rows away. That is the address 0035
refuses, arrived at by a rule that looked reasonable. Nearest-first gives
`blank in column 2 below row [column 2 = "Adhesives, containing a flammable liquid"]`. Shortest-run
is the same guard one step further on: where the material row does carry a symbol, column 1 and
column 2 share an anchor and column 1's run swallows every following material whose symbol column
is also blank.

### 4. An ordinary key is still the better address

`key_for` is tried first and nothing about it moves. § 172.102 table 2's other three blank-code
rows keep the plain keys they have, because their text is unique. This selector is reached only
where no combination of a row's own cells names it.

### 5. Such a row is inside an extent that takes its table **whole**

No declared row key names it, so `extent.tables[].rows` cannot list it, and `check-map.py --only
extent` says so rather than passing it: the extent takes that table whole, or does not reach the
row. **Nothing is added to the extent's shape.** A map wanting one such row out of a sliced table
has no way to say so, and that is left unbuilt until a corpus forces it
([#265](https://github.com/brandonifco/rules-factory/issues/265)).

## What was rejected

**A generic row-group concept**, and **multi-span evidence**. Neither was reached: this is an
addressability failure, and whether one contiguous span per entry survives the decomposition it
unblocks is trial 10's **H1**, still open and now testable.

**Extending it to the Hazardous Materials Table's other 258 unnameable rows in this change.** They
are outside trial 10's seven-row slice. The selector reaches them and the measurement is recorded
here, but no map takes that table whole and none is edited to.

## Consequences

- **`mapper inventory` enumerates § 172.102 table 2 whole**, 15 rows, where it refused the table
  before. Trial 10's declared universe keeps the row its rule needs.
- **The adapter and the section locator checker resolve the same selector to the same row**, held
  by `tools/tests/mapper/test_row_below.py` the way `test_mapper_table_rows.py` already holds their
  row-key grammars to each other. A row one half can cite and the other cannot enumerate is a
  denominator that shrinks to fit what was read.
- **No committed map moves.** None cites such a row, and every ordinary row citation reads exactly
  as it did.
- **A table is refused only where a row has neither address**, and the refusal now says both were
  tried.
