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
| 3 | [Part 107, two dates](faa-part-107-temporal/) — 2020-01-01 and 2026-01-01 | The temporal axis, across a real amendment | 23 → 24 | 4 → 5 | maps must stamp their baseline; clarity belongs to a version; re-mapping guidance |

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

**After trial 3**

- **A map must stamp the baseline it describes** — `contentHash`, `hashDerivation`, `asOf`.
  The differ printed `2020-01-01 -> ?` because a map is true of one corpus state and carried
  no reference to which.
- **Clarity belongs to a version, and does not only improve** — a flat prohibition on night
  flight was amended into a conditional permission turning on an unstated flash rate. More
  permissive and less determinate at once.
- **Re-mapping guidance** — diff entry content, never the entry list, because a stable id can
  hide a reversal; expect an amendment to reach into sections it did not add; and expect a
  text diff and a map diff to disagree, with both correct.

## What the trials confirmed

Worth recording because a confirmation across genres is evidence, where one is a
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
- **One corpus, one baseline per run.** `ReplayCompatibilityIdentity` refuses two baselines
  for the same corpus at two dates — a constraint added on reasoning and first *tested* in
  trial 3. It holds: a locator naming a corpus by id alone would be genuinely ambiguous, and
  § 107.29 is a section where the two versions say opposite things. Comparing dates is two
  runs, not one run with two baselines.
- **Bounded extraction is the right size.** Roughly 8,000 characters each, readable in one
  sitting, enough to find real structure.

## Calibration

Numbers worth having before estimating a real intake.

| | Part 107 | Backgammon | Part 107 re-map |
|---|---|---|---|
| Sections or headings mapped | 12 | 3 | 12 |
| Entries | 24 | 24 | 23 |
| Entries per section | ~2 | ~8 | ~2 |
| Ambiguous | 21% | 8% | 17% |
| Declined | 3 | 3 | 3 |
| Slice as share of corpus | 11% | 1.1% | 20% |
| Time, by hand | under an hour | under an hour | under an hour |

Re-mapping a revised corpus is markedly cheaper than mapping it, because the question is
"what moved" rather than "what is here". A maintained map costs far less to keep current
than to create — which is an argument for mapping early rather than at the point of need.

Ambiguity rate looks like a property of **genre**, not of mapping quality: a regulator writes
standards deliberately, a games author is trying to settle every case at the table. A high
rate is not evidence of a bad map.

Entries per heading varies by a factor of four, so "sections" is a poor unit for estimating.
Characters of slice is better: both trials produced ~24 entries from ~8,000 characters.

## What has not been tried

Tracked as issues, not listed here — a markdown backlog outside the tracker is a second
queue, and this project archived its predecessor partly for having one.

- [#8](https://github.com/brandonifco/rules-factory/issues/8) — a corpus with a dense
  internal cross-reference graph. All three trials had outward references only.
- [#9](https://github.com/brandonifco/rules-factory/issues/9) — whether a **wrong** map is
  caught downstream. Every finding so far surfaced during mapping, which is the cheap place,
  and that is encouraging rather than evidence.
