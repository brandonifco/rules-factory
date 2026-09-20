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
| 3 | [Part 107, two dates](faa-part-107-temporal/) — 2020-01-01 and 2026-01-01 | The temporal axis, across a real amendment | 23 → 24 as first mapped; 39 → 47 now | 4 → 5; 7 → 10 now | maps must stamp their baseline; clarity belongs to a version; re-mapping guidance |
| 7 | [SRD 5.2.1, Combat](srd-52-combat/) — Wizards of the Coast, CC-BY-4.0, pp. 13–16 | A PDF: an adapter over extracted text, page locators; turn structure; GM judgement; pointers into the Rules Glossary | 86 (68 in scope) → 91 (70) after the [blind second mapping](srd-52-combat/blind-mapping/README.md) | 17 → 19 (27% of in scope) | Blind-mapped (#106 step 3): 259 flags, 21 blind-right and 11 corpus-does-not-settle, corrected. Numbered 7 because trials 5 and 6 are the injection and blind-mapping trials (0014, 0015); #106 first called it 5. Nothing changed in the method yet. Findings recorded, not decided: a quote is verbatim of the extraction, not the page; a page extent cannot end mid-page; no field for a term defined in the same corpus outside the slice; the cross-reference phrase list detects none of the SRD's pointers; assertion attribution has no field; whether a draw happens can be ambiguous |
| 8 | [SRD 5.2.1, the fifteen conditions](srd-52-conditions/) — Wizards of the Coast, CC-BY-4.0, Rules Glossary pp. 177–191 | A dense **internal** graph: conditions that impose, deny and end each other (#8) | 100 (66 in scope) | 12 (18% of in scope) | Answers #8, partly. `dependsOn` survives density unchanged (142 edges, no cycle, longest chain 5, a clean five-layer backlog) — but the dense part of the graph is not the part it carries: the thirteen rules that *impose* or *end* a condition run the other way and are `crossReferences`. Findings recorded, not decided: `extent` has no list unit for a page grammar, so a slice of sixteen scattered glossary entries has to claim fifteen whole pages; a rule the corpus prints verbatim five times cannot be cited on its own, and *Round Down*, printed twice identically, cannot be cited without annexing the next glossary entry; a second slice of one corpus must restate its manifest and nothing compares the copies; a conflict can straddle the slice boundary. And the sharpest one: **0026's `pointerPhrases` detect 0 of the 51 condition-to-condition references**, and no regex can, because this corpus points by naming the term and the same words make a self-reference |
| 9 | [26 CFR § 1.121-1](tax-121-principal-residence/) — exclusion of gain on a principal residence, 2026-01-01 | A corpus that references **structurally** — `paragraph (e) of this section` — which is the only thing that tests #8's remaining question | 37 (31 in scope) → 38 (32) after the [blind second mapping](tax-121-principal-residence/blind-mapping/README.md) | 8 → 8 (25% of in scope) | Blind-mapped and adjudicated: 36 partnerships aligned by quoted text, **0 disagreements about scope**, 3 about clarity, and one rule the first map did not have at all — § 1.121-1(b)(4) Example 4 nets a $25,000 loss against $270,000 of gain and no operative sentence says a loss does that, which no mechanical check could see because the paragraph *is* cited, by an entry that declines it. Largest correction: a gate recorded with none of its reach (30 missing `enabledBy` edges on § 1.121-1(f)). Two challenged ambiguities upheld ("adjacent to", "incapable of self-care") and one overturned (`allocation-required` is not ambiguous — the separateness test is in (e)(1)'s third sentence, which **both** mappers read past). `<EXAMPLE>` elements are now indexed by the eCFR locator checker, so a worked example can be cited. #216 is decided by [0031](../docs/decisions/0031-an-example-that-bounds-a-term-is-recorded-as-a-bound.md): Map C does not adopt the blind map's shape, and the two (c)(4) bounds are `short-temporary-absences.ambiguity.bounds`, where an owner's ruling is compared against them. **Closes #8.** A citation *can* address a cross-reference: 16 of the map's 26 resolved `crossReferences` are anchored on a structural pointer and every one of the 26 resolves to an entry whose locator is a constituent — `§ 1.121-1(d)` ↔ `§ 1.121-1(e)`, a mutual qualification, proved by the locator checker. No schema change: the field was `crossReferences` all along, and #8's phrasing put the question on the wrong field. Also: deriving `dependsOn` from the corpus's own pointers would be wrong in 12 of 16 places; the `section-designation` grammar cannot have #207's duplicate-passage problem at all (every one of 37 spans occurs exactly once, against 20 of 48 SRD entries forced to extend); the first publishable trial map. Findings recorded, not decided: the eCFR XML runs `(e)(1)` into `(e)`'s element, so 18 of 37 citations are one level shallower than the regulation's own numbering; `<EXAMPLE>` is not indexed, and holds 12 of the section's 21 structural pointers; a Treasury regulation's examples are *worked answers that constrain a rule*, and the method has no category for them between "advice" and "rule"; `definedElsewhere` and `ambiguity` are mutually exclusive and one entry needs both; `definedElsewhere` can only name one corpus and "local law" is a class of them; `check-locators-section.py` has no `absence` check |
| 10 | [49 CFR § 172.101–§ 172.102](hazmat-172-table/) — the Hazardous Materials Table and the special provisions, 2026-01-01 | Rules stated as a grid, pointers that are codes rather than words, applicability encoded in the shape of an identifier, and a specific provision governing a general one | 135 (129 in scope) as first mapped | 7 (5% of in scope) | Admitted first, with the slice, both protocols and [the hypotheses H1–H6 written down before any entry existed](hazmat-172-table/README.md#the-hypotheses-before-anything-is-mapped) — which is what [#262](https://github.com/brandonifco/rules-factory/issues/262) is for. Phase 1 filed [#284](https://github.com/brandonifco/rules-factory/issues/284) (no `pointerMechanisms` value for a column 7 code, no `adapterReach` modality for an equation) and [#285](https://github.com/brandonifco/rules-factory/issues/285) (12 of the 20 provisions sit inside an `<EXTRACT>`), and both are now answered — by [0041](../docs/decisions/0041-a-coded-pointer-is-made-by-the-column-it-sits-in.md), [0045](../docs/decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md), [0046](../docs/decisions/0046-an-additional-rule-can-continue-a-definition.md) and [0036](../docs/decisions/0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md). **Step 2, the first mapping**: 135 entries over the seven settled rows, § 172.101(a)–(j), § 172.102(a) and (b)(1)–(9) and the 20 invoked provisions. **H1 holds, and the citation is what holds it** — `IB2, T4, TP1` states no rule as four tokens, and what makes it one is `row [column 2 = "Acetal"], column 7`, so the evidence model survives a grid *once the grid is addressable* (0035). Two strains, both recorded. The row stating IB2's additional requirement leaves column 1 blank, so read alone it states half a rule, and because it does not print the code it still cannot declare direct `defines`. That gap forced [#321](https://github.com/brandonifco/rules-factory/issues/321) and 0046: an explicit, structurally witnessed `continuesDefinition` now joins that passage to IB2 without weakening 0045, and 0044 therefore obliges every IB2 pointer to name both defining entries. A contiguous span can cover **several cells**, which H1 did not predict: `3 | UN1088 | II` is one span and one classification. H3 is recorded (23 gated entries, modal reach in `enabledBy` on every provision) and untested until the mutation run. **H4 found a representational limit**: version 1 of `mapping-inventory.json` named one corpus while `mapper inventory` walks every corpus a map cites (0042), so this two-corpus map could record no rejection and its 615 unaccounted units could not be told from unread ([#319](https://github.com/brandonifco/rules-factory/issues/319)). Version 2 now gives every rejection its corpus `sourceId` and partitions accounting by it; the approximate first-mapper record is not reconstructed into exact verdicts after the fact. Also filed: [#318](https://github.com/brandonifco/rules-factory/issues/318), `mapper pointers` never runs the coded-pointer detector (40 codes detected when `report()` is called by hand, 0 by the gate); [#320](https://github.com/brandonifco/rules-factory/issues/320), a quote under four words reaches no unit, so every single-cell entry is *not located*; [#322](https://github.com/brandonifco/rules-factory/issues/322), one quote marks two byte-identical rows reached; [#323](https://github.com/brandonifco/rules-factory/issues/323), resolved by [0047](../docs/decisions/0047-a-mapping-discovered-corpus-boundary-amends-admission-without-rewriting-it.md) and the complete section-designation grammar, the manifest's `references` are short of six sections the mapped spans point at. All 10 sweeps fire on both corpora, so neither protocol owes a `sweepCuesReason`. Numbered for its issue; the validator-attack run below also calls itself trial 10, which is [#286](https://github.com/brandonifco/rules-factory/issues/286) |

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
  inspectable rather than inferred. Both Part 107 manifests now list 49 CFR 171.8 and the
  Air Almanac as referenced and not admitted; they had the field specified and unused until
  the schema work for #5 and #7 went looking.
- **Two temporal things** — `asOf` pins which text is in force; a rule may carry dates of
  its own. The method mentioned only the first.

**After trial 2**

- **Reachability is a property of the adapter** — the starting position of a backgammon
  board is fully determined in the corpus, as an illustration. Not another corpus, another
  *modality* of the same one, which `references` does not describe. Now `beyondAdapter`, an
  entry field naming the reader that failed and the modality that defeated it
  ([0004](../docs/decisions/0004-adapter-reach-is-a-property-of-the-entry.md)).
- **`dependsOn` conflates implementation order with runtime precondition** — invisible in a
  stateless corpus, immediate in one with turn structure. Now `gatedBy`, which holds entry
  ids and refuses to hold a condition
  ([0003](../docs/decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md)), since split
  by direction into `enabledBy` and `suspendedBy`
  ([0011](../docs/decisions/0011-a-gate-has-a-direction.md)). Ten backgammon entries carry a
  gate; no Part 107 entry does, which is the correct outcome for a corpus with no phases.
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
  internal cross-reference graph. **Now fully answered**, across two trials and two corpora that
  point in opposite styles. [Trial 8](srd-52-conditions/), the SRD 5.2.1 conditions, answered
  three of the four questions and could not test the fourth, because the SRD points at a *term by
  name* and never at a constituent. [Trial 9](tax-121-principal-residence/), 26 CFR § 1.121-1,
  is the corpus that issue named — a tax regulation — and it points structurally twenty-one
  times. **Can a citation address a cross-reference? Yes**, and without a schema change: sixteen
  of the map's resolved `crossReferences` items are anchored on a pointer such as *"paragraph (e)
  of this section"*, and every resolved item names an entry whose own locator is a constituent —
  including the mutual `§ 1.121-1(d)` ↔ `§ 1.121-1(e)` qualification, with the locator checker
  proving both. The correction #8 needs is that the question was on the wrong field: a locator
  says where *this* rule sits and never points, and what points is `crossReferences`, whose
  `resolvedBy` has always resolved to an entry of whatever granularity the mapper chose. The
  bound on the answer is the adapter's, not the schema's — a citation can address a
  cross-reference to the depth the markup exposes, and the eCFR XML exposes one level less than
  the CFR's own numbering. Trial 9 also sharpens *does the map become unreadable?*: the trigger
  is repetition, not size.
- [#9](https://github.com/brandonifco/rules-factory/issues/9) — whether a **wrong** map is
  caught downstream. Every finding so far surfaced during mapping, which is the cheap place,
  and that is encouraging rather than evidence. [Trial 10](validator-attack/) supplies the
  validator's half of the answer and it is not encouraging: fourteen kinds of deliberate damage
  over five committed maps, **18 of 62 refused and 44 passed** (16 and 46 when first measured;
  the two rows that moved are 0034's epistemic checks). Four `enforcement` issues came out of it,
  and five of the misses are now measured limits rather than argued ones.

## The collapse trial — what the validator sees when a superposition is collapsed

[`collapse-trial/`](collapse-trial/README.md) takes every recorded ambiguity in every committed
map, collapses it one at a time into `clarity: clear`, and counts what fails. It is the shape
[0014](../docs/decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md)'s injection trial
had, applied to the one error
[0034](../docs/decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md) is about.

**12 of 64 caught, against 4 before.** Every catch comes from a record a *second* reader left:
8 from the adjudication of a blind second mapping, 4 from a conflict the corpus creates by
stating a rule twice. None comes from the entry itself, which is why 0034 adds no field to it.
On the three maps with a readable adjudication record the rate is 8 of 36; on the three without
it is 0 of 28, and the ceiling is how much of each corpus was read twice.

## The build of trial 9 — seven entries of § 1.121-1

The second run downstream of a map, and the first with the rails in place:
[`tax-121-build/`](tax-121-build/), seven of 24 entries of `tax-121-principal-residence` taken
from `factory backlog --create` to merged `main` on 2026-09-17.

Trial 4 asked whether a map survives being built from. This one asked **what an entry costs, and
what the rails get wrong**, because the case for the platform rested on estimates.

Measured: ~17 minutes and ~230k tokens per merged entry, about two thirds of it process rather
than rules. Zero map defects found downstream, zero escalations, zero blocking review findings —
which says the blind second mapping worked, and says nothing about whether the map's boundary is
the right boundary for a product.

Four defects in the rails, one a real bypass of the evidence rule
([#239](https://github.com/brandonifco/rules-factory/issues/239), fixed), one a structural limit on
throughput ([#242](https://github.com/brandonifco/rules-factory/issues/242): any two entry pull
requests always conflict, because 19 of the 24 derived files in one are a backlog rendering nothing
reads). Full account, including the two findings left unfiled and the reasoning behind the
superposition idea the run produced: [EVIDENCE.md](tax-121-build/EVIDENCE.md).

## Trial 4 — building from a map

The first run that goes *downstream* of a map rather than producing one:
`hoyle-backgammon`, an engine built from trial 2's map, on the kernel packages.

157 tests, `validate.sh full` green, nine source mutations each turning the suite red. It
produced **16 findings against the map**, 11 of them the map being wrong.

Logged here because it is a different kind of trial and answers a different question. Mapping
trials ask *can this corpus be decomposed*. A build asks *was the decomposition right*, and
it finds a class of defect mapping cannot: relations that are only missed once something
needs them, entries whose `clarity: clear` survives until a case reaches it, and — the
sharpest one — a missing gate whose absence is invisible to every legality test and changes
every subsequent dice throw.

What it did **not** establish is a miss rate. These were unknown errors found in earnest, not
injected ones, so nothing says how many were missed. That is [#9](https://github.com/brandonifco/rules-factory/issues/9),
now much cheaper to run because a real engine exists to run it against.

Findings: [#12](https://github.com/brandonifco/rules-factory/issues/12) ·
[#13](https://github.com/brandonifco/rules-factory/issues/13) ·
[#14](https://github.com/brandonifco/rules-factory/issues/14) ·
[#15](https://github.com/brandonifco/rules-factory/issues/15) ·
[#16](https://github.com/brandonifco/rules-factory/issues/16)

### Trial 4, reviewed: two independent passes, and what they caught

The build's own 16 findings were then checked by two reviewers who had not written anything —
one verifying the findings against the corpus, one running 66 source mutations against the
engine.

**The verification reversed the trial's headline.** Trial 2's best finding — *a rule can live
in an image* — rested on a sentence quoted from the wrong paragraph. The starting arrangement
is stated in prose, completely, and over-determined three further ways; a mapper had written
*"Cannot be evidenced from this corpus"* about it, and a decision record, a trial report and an
engine's architecture were all built on top. The finding survives on a different entry —
`inner-table-handedness`, which really is stated only in Fig. 1 — so `beyondAdapter` keeps one
instance, and that instance is one no engine ever consumes.

It also found **13 wrong page citations out of 24**, which had passed a mapping trial, a build
and a review. They were invisible because `evidence` holds a summary of what the evidence shows
rather than the corpus's words, so no citation was checkable at all
([#18](https://github.com/brandonifco/rules-factory/issues/18), which ships the checker), and
four unmapped rules including the only statement in the corpus of how many faces a die has
([#20](https://github.com/brandonifco/rules-factory/issues/20)).

**The mutation pass killed 47 of 66 and left two rule holes.** Entering from the bar with two
or more men up, and bearing off from the highest point when a forward move is blocked — the
one case in this corpus where Hoyle's rule and the modern rule disagree. Both could be
replaced with the wrong rule and all 157 tests stayed green. The determinism was real but
largely unasserted: the replay identity's ruleset id, version, schema version, hash derivation
and generator could each be changed without a single test noticing, and the list a replay
indexes into is pinned by nothing at all
([#22](https://github.com/brandonifco/rules-factory/issues/22)).

All five merge blockers are closed; the engine is rebased onto the corrected map and the gate
is green at 334 results.

**What the two passes say about the method.** Every finding of consequence came from something
*executing* — a build, a mutation, a page-marker comparison. None came from reading. Three of
the four biggest are the same failure in different clothes: a human stopped reading, and no
field on a map can detect that. The one countermeasure that worked is the cheap mechanical one
— compare what an entry claims against the corpus itself — which is why
[#18](https://github.com/brandonifco/rules-factory/issues/18) matters more than its size
suggests.

Further findings: [#17](https://github.com/brandonifco/rules-factory/issues/17) ·
[#18](https://github.com/brandonifco/rules-factory/issues/18) ·
[#19](https://github.com/brandonifco/rules-factory/issues/19) ·
[#20](https://github.com/brandonifco/rules-factory/issues/20) ·
[#21](https://github.com/brandonifco/rules-factory/issues/21) ·
[#22](https://github.com/brandonifco/rules-factory/issues/22) ·
[#23](https://github.com/brandonifco/rules-factory/issues/23)
