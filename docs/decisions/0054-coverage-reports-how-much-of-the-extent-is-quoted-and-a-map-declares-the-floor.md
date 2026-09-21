# 0054 — `coverage` reports how much of the declared extent is quoted, and only a floor the map declares can fail it

## Status

Accepted — 2026-09-20. Records the decision
[#270](https://github.com/brandonifco/rules-factory/issues/270) asked for by name: *whether a
fraction can fail a map is decided here and written down — a threshold nobody argued for would
be worse than the number alone.*
**Extends [0009](0009-absence-is-a-verdict-with-evidence.md)**, whose bargain this repeats one
level down, and **sibling of
[0020](0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)**, whose
two units it measures in.

## Context

`coverage`, in all three locator checkers, asks whether every **unit** of the declared extent —
a page, or a section — is reached by some entry's verified evidence. One quote reaches a page.

Measured by the mutation harness ([trial 10](../../examples/validator-attack/README.md),
[#259](https://github.com/brandonifco/rules-factory/issues/259)): the `drop-entry` mutation
removes one `scope: in` entry that quotes the corpus and that no other entry names. It is caught
on `faa-part-107`, where the dropped entry was the only quote in its section, and **missed** on
`hoyle-backgammon`, `tax-121-principal-residence`, `srd-52-combat` and `srd-52-conditions`. 4 of
5. On a ten-page extent carrying 33 entries, deleting a rule is invisible.

The unit is doing the damage, and a section extent is not finer: `§ 1.121-1` is one section and
the whole tax-121 map lies inside it, so `coverage` there proves that somebody quoted the section
once.

## Decision

**1. Every `coverage` reports the fraction of the declared extent that verified evidence
quotes, and prints it on every run.** The measure is the union of the verified quotes' spans
over the extent's own length, in characters of the text the checker reads:

- a page extent is one span, from the marker for `from` to the end of `to` — or to `endsBefore`
  where the extent stops at a heading (0024), the same slice `absence` searches;
- a section extent is one span per paragraph of every section the extent names, summed across
  every corpus of the run (0042), because a section is read in whichever corpus the eCFR served
  it;
- a character quoted twice was read once, so the union and never the sum.

**2. A map may declare `extent.quoted`, the fraction it claims its verified evidence can show,
and `coverage` fails a map that quotes less than it declared.** Optional; above 0 and at most 1.
`check-map.py --only extent` checks its shape, and the locator checkers — which have the corpus
— measure the number and hold the map to it.

**3. No threshold is imposed on a map that declares none.** The fraction is reported and the run
stays green.

## Why not a threshold

Because the measurement says one could not be honest. Across the five committed maps, on the
commit this record was written at:

| map | extent | quoted |
|---|---|---:|
| `faa-part-107` | 12 sections | 100% |
| `faa-part-107-temporal` | 12 sections | 97% |
| `srd-52-combat` | pp. 13–16 | 84% |
| `hoyle-backgammon` | pp. 271–280 | 79% |
| `tax-121-principal-residence` | § 1.121-1 | 45% |
| `srd-52-conditions` | pp. 177–191 | 20% |
| `hazmat-172-table` | §§ 172.101, 172.102 | 19% |

The spread is not sloppiness. `srd-52-conditions` declares the whole of the SRD's Rules Glossary
as its extent and maps the conditions in it; `faa-part-107` maps twelve sections of a regulation
substantially whole. A floor that passed the second would refuse the first, and a floor that
passed the first would prove nothing about anything. A number picked to sit under 19% is a number
chosen to fail nothing, and it would read as a check.

So the fraction is a **claim the map makes**, exactly as `extent` itself is. 0009 already settled
that nothing sizes an extent and what the field buys is that the claim is written down and can be
argued with. `extent.quoted` is that bargain one level down: a map that says it can show 80% of
its extent quoted is held to 80%, and a map that says nothing is measured, printed, and not
failed.

## What this does not decide

- **Whether any committed map declares one.** None does, and adding the field to one changes its
  bytes, which invalidates the review of those bytes
  ([0017](0017-a-map-change-carries-a-review-of-its-bytes.md)). Each is a separate decision for
  the map's owner. Until one is made, `drop-entry` stays missed on the four maps where it is
  missed today, and the harness's table says so.
- **That a quoted fraction measures comprehension.** It measures how much of what the map claims
  to have read it can show it read. A map can quote a page whole and misread every sentence on
  it, which is what the blind second mapping exists for
  ([0014](0014-a-map-is-checked-by-a-blind-second-mapping.md)).
- **How a sliced table is measured.** A table row is not in the section tree's flat text, and
  `extent.tables` already accounts for a read table row by row
  ([0035](0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)) — a finer statement than a
  fraction, not a coarser one. The section fraction is therefore of the extent's *paragraph*
  text, and the summary says so.
- **The producer's half.** [`mapper inventory`](../mapper.md#the-inventory) counts the units
  inside the extent that no quote reaches
  ([#255](https://github.com/brandonifco/rules-factory/issues/255)). That is the mapper measuring
  its own walk; this is the adversary measuring the map, and the two numbers are not each other's.
