# 0064 — A page extent can start after a heading on its first page, and that heading joins two maps

## Status

Accepted — 2026-09-22. Records the decision on
[#434](https://github.com/brandonifco/rules-factory/issues/434). **Extends
[0024](0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md) § 3**, whose
last sentence — "There is no `startsAfter`. The SRD combat chapter starts at the top of p. 13, and
no map needs it" — is superseded: one does now. Adds one field to the page extent and the two
checks that read it. The specification is [corpus-map.md](../corpus-map.md).

## Context

*Playing the Game* runs pp. 5–18 of SRD 5.2.1, and three maps read it. Trial 7 mapped the combat
half, pp. 13–16, and stopped where the chapter does — halfway down p. 16, at the *Damage and
Healing* heading — which is the case 0024 § 3 was written for:

```json
"extent": { "unit": "page", "from": 13, "to": 16, "endsBefore": "Damage and Healing" }
```

Trial 12 mapped pp. 5–12, which is contiguous whole pages and needs nothing. What is left is
*Damage and Healing* through *Temporary Hit Points*, pp. 16–18, and it begins where trial 7's
extent ends: halfway down p. 16, under the same heading.

## The failed representation

Decomposition under the contract as it stands is one line, and it was attempted
([#434](https://github.com/brandonifco/rules-factory/issues/434)):

```json
"extent": { "unit": "page", "from": 16, "to": 18 }
```

The sentence that map asserts is **`this map read p. 16`**, and it is false about the corpus. It
did not read the top half of p. 16; trial 7 did. Nothing catches the overclaim, and each checker
is quiet in a different way:

- `coverage` passes. A quote anywhere on p. 16 reaches the page, and the map has many.
- `extent-bounds` passes. Every in-scope quote is on a page in the range.
- `mapper inventory` reports the combat half's units — some thirty blocks — **unaccounted**,
  which is 0009's word for *nobody looked*, when somebody did.

The only way to close that inventory is to record a rejection against every one of those blocks,
and the honest `ground` for each would be *another map read this*, which is in no closed set and
should not be: a rejection is a reading the mapper performed
([0009](0009-absence-is-a-verdict-with-evidence.md)), and thirty rejections that mean "this is
somebody else's slice" would turn a limit of `extent` into a record of work nobody did — the same
mistake `srd-52-conditions`' 407 unaccounted units were *not* made into.

Neither alternative is inconvenient. Both are false, in the one register this contract exists to
keep true.

## Decision

**A page extent may start after a heading on its first page.**

```json
"extent": { "unit": "page", "from": 16, "to": 18, "startsAfter": "Damage and Healing" }
```

The field is the mirror of `endsBefore`, in every part:

| | `startsAfter` | `endsBefore` |
|---|---|---|
| page it names a line on | `from` | `to` |
| shape, checked by `check-map.py --only extent` | one line of text, no surrounding whitespace | the same |
| the corpus must print it | exactly once as a line of its own on that page | the same |
| what the slice excludes | everything before it on that page, and the line itself | the line itself, and everything after it on that page |
| in-scope quote outside it | `extent-start` fails the map | `extent-end` fails the map |
| out-of-scope quote outside it | named in the summary, neither passed nor failed (0020) | the same |
| `absence` | searches only after it | searches only up to it |
| `coverage` | a quote ending at or before it does not reach page `from` | a quote starting at or after it does not reach page `to` |
| `mapper inventory` | enumerates only the blocks after it | enumerates only the blocks before it |
| `tools/check-locators.py` | cannot find a line, reports NOT VERIFIED, fails the run | the same |

"After" is in the extraction's reading order, as everything in this grammar is, and on p. 16 the
order and the eye agree.

### The heading belongs to neither map

The slice begins at the **end** of the heading's line. Trial 7's extent ends at the **start** of
the same line. So `Damage and Healing` is inside no map's extent, and the two slices of p. 16 are
complementary with exactly one line between them.

That is deliberate and it is the cost. It is small because of what the line is: a heading states
no rule, and every committed inventory that meets one records it as `ground: heading` — 54 of
trial 12's 74 rejections are exactly this. The line in the gap is the one unit both maps would
have declined.

The alternative, `startsAt`, including the heading in the later map, would tile p. 16 with no gap.
It was rejected below.

### Both cuts may be declared, and they can contradict each other once

An extent may carry both. Where `from` and `to` are different pages, the order is a fact of the
page numbers. Where they are the same page, an extent can start after a heading printed at or
after the one it ends before — it ends where it has not begun, and selects nothing. `check-map.py`
refuses the one case it can see without the corpus (both fields naming the same string);
`extent-start` and `mapper inventory` refuse the rest, each in the reader that has the lines.

## Against 0063

[0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md) governs this: an extent field
is a map concept. Its four steps, honestly:

1. **Decomposition attempted, written down.** Above, and in #434 before this record existed.
2. **The failed representation exhibited.** Above: the map asserts it read p. 16, which is false,
   and the only repair inside the contract is thirty rejections whose ground would be a lie.
3. **A second reading sees the same failure.** *This step has no analogue here, and saying so is
   part of the record.* A blind second mapping separates a limit of the contract from one
   reader's preference about a **passage**; this failure is in the extent, before any entry
   exists, and a second mapper handed pp. 16–18 would be handed the same undeclarable slice. What
   stands in for it is that the identical failure at the other end was established independently,
   by a different trial, a week earlier, and accepted as 0024 § 3 — and that the two are one
   mechanism, which the mirror table above is.
4. **The check is named.** `extent-start` in `check-locators-pdf-text.py`, `extent` in
   `check-map.py`, and the enumeration in `mapper inventory`. Three readers, each failing
   independently.

0063 also exempts repairs, and there is a reading on which this is one: `endsBefore` already
decided that a page extent may be cut at a heading, and this is that decision applied to the end
it was not applied to. This record does not lean on that reading. The corpus forced it either
way.

## Alternatives considered

**`startsAt`, naming the heading and including it.** Rejected, though it is the better of the two
on coverage: p. 16 would tile exactly, and the heading would be some map's unit. Two things
against. It is not the mirror of `endsBefore` — "starts at X" and "ends before Y" cut on opposite
sides of the line they name, so one page cut at both would have to be read in two directions, and
the pair of fields would stop being one idea. And it makes the *same string* mean two different
offsets depending on which field it appears in, which is exactly the "two shapes under one name"
0024 rejected when it declined a heading-bounded `to`. The gap is one heading line, and a heading
is the one thing every map already declines.

**Let the later map declare `from: 17` and quote p. 16 out of scope.** Rejected. It is false in
the other direction: *Damage and Healing*, *Healing*, *Dropping to 0 Hit Points* and
*Death Saving Throws* are printed on p. 16, are in scope, and an in-scope quote outside the extent
is what `extent-bounds` exists to refuse.

**A list of page ranges with offsets.** Rejected as unforced (0063). One corpus needs one cut at
one end; a general geometry is the vacuum ontology this repository archived a predecessor over.

**Keep the overclaim and add a `sharedWith` naming the other map.** Rejected. It makes a map's
extent depend on another map, which nothing in the contract does, and it answers the inventory
question ("who read this?") with an assertion no checker of this map can verify — the other map's
bytes are not here.

## Consequences

**The rest of *Playing the Game* becomes mappable**, which is the point, and is the next trial.

**A heading line on a split page is in no map's extent.** Stated above. Anyone unioning two maps
of one corpus to ask what has been read should expect exactly one such line per split, and it is
a heading.

**`tools/check-locators.py` gains a second refusal it cannot satisfy.** It reads
whitespace-collapsed text with no lines and cannot find either heading; it now reports
`extent-start` NOT VERIFIED beside `extent-end`, and fails the run rather than passing over a cut
it did not check.

**No injection measures the new check, and `mutate-map.py` says so rather than pretending.**
`extent-start` was added to `narrow-extent`'s expected family and taken out again: that mutation
moves `to`, and the start cut is on page `from`, which it never touches. Under
[0061](0061-an-injection-names-the-refusal-it-expects-and-a-catch-by-another-rule-is-a-different-outcome.md)
an `expect` naming a rule the mutation cannot reach would read every catch as a neighbour's and
say the opposite of the truth, so the field is left at three and a comment says why. An injection
that damages a start cut is a different one, and it waits for a map that declares one — the next
trial. The measured catch rate is unchanged at 28 of 62.
