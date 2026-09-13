# Trials

Runs of [the method](../docs/method.md) against real corpora, by hand, before building
anything to automate it.

Each trial exists to **change the method**. A run that confirms everything has told us
nothing, and should be read as a failure to pick a hard enough corpus.

## The log

| # | Corpus | Chosen to stress | Entries | Ambiguous | Changed as a result |
|---|---|---|---|---:|---:|---|
| 1 | [14 CFR Part 107](faa-part-107/) — FAA small-drone operating rules, 2026-01-01 | No dice, no pages, citations by designation, dates inside rules | 24 | 5 (21%) | `kind: assertion`; standards vs gaps; manifest `references`; two temporal things |
| 2 | [Hoyle's Backgammon](hoyle-backgammon/) — *Hoyle's Games Modernized*, 1909 | Dice, turn order, a corpus written to be complete | 24 | 2 (8%) | adapter reachability; `dependsOn` conflates two orderings; advice inside rules; corpus bounds the engine |

## What has actually changed

Every item below came from a trial and is now in the method or the map schema. This section
is the answer to "are we learning anything, or just producing artefacts."

**After trial 1**

- **`kind: assertion`** — `value` and `operation` were not exhaustive. Eight of 24 entries
  were facts only a caller can supply. An engine owes them demand, attribution, recording,
  and never inference.
- **A standard is not a gap** — "well clear", "reasonable protection". A regulator writing
  these was not vague by accident, and resolving one to a number substitutes the engine's
  rule for the corpus's. Recorded as an open question rather than forced into a fate.
- **Manifest `references`** — a quarter of the sections deferred their meaning to a corpus
  that had not been admitted. Those references are the engine's boundary and should be
  inspectable rather than inferred.
- **Two temporal things** — `asOf` pins which text is in force; a rule may carry dates of
  its own. The method mentioned only the first.

**After trial 2**

- **Reachability is a property of the adapter** — the starting position of a backgammon
  board is fully determined in the corpus, as an illustration. Not another corpus, another
  *modality* of the same one, which `references` does not describe.
- **`dependsOn` conflates implementation order with runtime precondition** — invisible in a
  stateless corpus, immediate in one with turn structure.
- **Advice inside normative sections** — `scope` excludes an entry, not a sentence.
- **The corpus bounds the engine, not the subject** — a 1909 text has no doubling cube, and
  "absent from the corpus" must not look like "nobody looked."

## What both trials confirmed

Worth recording because a confirmation across two genres is evidence, where one is a
coincidence.

- **Opaque, adapter-defined citations.** Two grammars — `§ 107.51(b)(2)` and
  `Playing / p. 273` — through one pipeline with no special-casing.
- **Optional randomness, from both directions.** One corpus draws nothing; the other cannot
  be modelled without dice.
- **`hashDerivation` is load-bearing.** eCFR XML is not the rendered HTML; Gutenberg plain
  text carries 20 KB of boilerplate that is not the work. Two independent confirmations that
  a digest does not say what it covers.
- **Delegation to a person is a category.** A federal regulator and a Victorian games author
  reached the same construction — "if the pilot determines", "as may have been agreed".
- **The kernel needed no changes.** The five `UnresolvedReason` values absorbed both corpora
  without strain, on material neither was designed against.
- **Bounded extraction is the right size.** Roughly 8,000 characters each, readable in one
  sitting, enough to find real structure.

## Calibration

Numbers worth having before estimating a real intake.

| | Part 107 | Backgammon |
|---|---|---|
| Sections or headings mapped | 12 | 3 |
| Entries | 24 | 24 |
| Entries per section | ~2 | ~8 |
| Ambiguous | 21% | 8% |
| Declined | 3 | 3 |
| Slice as share of corpus | 11% | 1.1% |
| Time, by hand | under an hour | under an hour |

Ambiguity rate looks like a property of **genre**, not of mapping quality: a regulator writes
standards deliberately, a games author is trying to settle every case at the table. A high
rate is not evidence of a bad map.

Entries per heading varies by a factor of four, so "sections" is a poor unit for estimating.
Characters of slice is better: both trials produced ~24 entries from ~8,000 characters.

## What has not been tried

- A corpus with **cross-references inside itself** — "except as provided in § 107.200".
  Both trials had outward references; neither had a dense internal graph.
- A **revised** corpus: re-running an intake at a later `asOf` and diffing the map. The
  temporal axis has never actually been exercised across two versions.
- A corpus where **the map is wrong** and the error is caught downstream. Every finding so
  far surfaced during mapping, which is the cheap place. Nothing has yet tested whether a
  bad map is caught at all.
