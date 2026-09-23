# Trials

Runs of [the method](../docs/method.md) against real corpora, by hand, before building
anything to automate it.

Each trial exists to **change the method**. A run that confirms everything has told us
nothing, and should be read as a failure to pick a hard enough corpus.

## The log

A number belongs to the trial the issue that ran it names: 1–3 and 7–11 are rows below, 4 has
[its own section](#trial-4--building-from-a-map), and 5 and 6 are the
[injection](injection-trial/) and [blind-mapping](blind-mapping-trial/) trials (0014, 0015).
**A map is not always a trial.** `srd-52-damage-and-healing` has a row with no number: it completes the chapter trial 12 mapped half of, and a run chosen to finish something rather than to break something has told us nothing a number should claim. It is listed because every committed map is listed, and it is read here as evidence like any other.

**The validator attack is not a numbered trial.** It damages maps that are already committed
rather than admitting a corpus, it has never held a row here, and it called itself trial 10 until
[#286](https://github.com/brandonifco/rules-factory/issues/286) settled the collision in favour of
the run the rest of the repository already means by that number. Its own README still opens
*"Trial 10"*: it is trial evidence, superseded rather than rewritten
([AGENTS.md](../AGENTS.md) §3), and this line is what supersedes it.

| # | Corpus | Chosen to stress | Entries | Ambiguous | Changed as a result |
|---|---|---|---|---:|---:|---|
| 1 | [14 CFR Part 107](faa-part-107/) — FAA small-drone operating rules, 2026-01-01 | No dice, no pages, citations by designation, dates inside rules | 24 | 5 (21%) | `kind: assertion`; standards vs gaps; manifest `references`; two temporal things |
| 2 | [Hoyle's Backgammon](hoyle-backgammon/) — *Hoyle's Games Modernized*, 1909 | Dice, turn order, a corpus written to be complete | 24 | 2 (8%) | adapter reachability; `dependsOn` conflates two orderings; advice inside rules; corpus bounds the engine |
| 3 | [Part 107, two dates](faa-part-107-temporal/) — 2020-01-01 and 2026-01-01 | The temporal axis, across a real amendment | 23 → 24 as first mapped; 39 → 47 now | 4 → 5; 7 → 10 now | maps must stamp their baseline; clarity belongs to a version; re-mapping guidance |
| 7 | [SRD 5.2.1, Combat](srd-52-combat/) — Wizards of the Coast, CC-BY-4.0, pp. 13–16 | A PDF: an adapter over extracted text, page locators; turn structure; GM judgement; pointers into the Rules Glossary | 86 (68 in scope) → 91 (70) after the [blind second mapping](srd-52-combat/blind-mapping/README.md) | 17 → 19 (27% of in scope) | Blind-mapped (#106 step 3): 259 flags, 21 blind-right and 11 corpus-does-not-settle, corrected. Numbered 7 because trials 5 and 6 are the injection and blind-mapping trials (0014, 0015); #106 first called it 5. Nothing changed in the method yet. Findings recorded, not decided: a quote is verbatim of the extraction, not the page; a page extent cannot end mid-page; no field for a term defined in the same corpus outside the slice; the cross-reference phrase list detects none of the SRD's pointers; assertion attribution has no field; whether a draw happens can be ambiguous |
| 8 | [SRD 5.2.1, the fifteen conditions](srd-52-conditions/) — Wizards of the Coast, CC-BY-4.0, Rules Glossary pp. 177–191 | A dense **internal** graph: conditions that impose, deny and end each other (#8) | 100 (66 in scope) | 12 (18% of in scope) | Answers #8, partly. `dependsOn` survives density unchanged (142 edges, no cycle, longest chain 5, a clean five-layer backlog) — but the dense part of the graph is not the part it carries: the thirteen rules that *impose* or *end* a condition run the other way and are `crossReferences`. Findings recorded, not decided: `extent` has no list unit for a page grammar, so a slice of sixteen scattered glossary entries has to claim fifteen whole pages; a rule the corpus prints verbatim five times cannot be cited on its own, and *Round Down*, printed twice identically, cannot be cited without annexing the next glossary entry; a second slice of one corpus must restate its manifest and nothing compares the copies; a conflict can straddle the slice boundary. And the sharpest one: **0026's `pointerPhrases` detect 0 of the 51 condition-to-condition references**, and no regex can, because this corpus points by naming the term and the same words make a self-reference. That finding is answered: `defined-term-use` reads the vocabulary out of the map and separates the two by where the sentence is (#249), and against this map it finds 54 namings where the phrase list found 5. It also found the map's own gap — three `scope: out`, `status: declined` entries that name a condition and declare nothing — which [0058](../docs/decisions/0058-a-pointer-is-declared-by-the-passage-that-makes-it-whatever-the-engine-does-with-the-rule.md) settled and corrected, closing [#208](https://github.com/brandonifco/rules-factory/issues/208) and [#254](https://github.com/brandonifco/rules-factory/issues/254) |
| 9 | [26 CFR § 1.121-1](tax-121-principal-residence/) — exclusion of gain on a principal residence, 2026-01-01 | A corpus that references **structurally** — `paragraph (e) of this section` — which is the only thing that tests #8's remaining question | 37 (31 in scope) → 38 (32) after the [blind second mapping](tax-121-principal-residence/blind-mapping/README.md) | 8 → 8 (25% of in scope) | Blind-mapped and adjudicated: 36 partnerships aligned by quoted text, **0 disagreements about scope**, 3 about clarity, and one rule the first map did not have at all — § 1.121-1(b)(4) Example 4 nets a $25,000 loss against $270,000 of gain and no operative sentence says a loss does that, which no mechanical check could see because the paragraph *is* cited, by an entry that declines it. Largest correction: a gate recorded with none of its reach (30 missing `enabledBy` edges on § 1.121-1(f)). Two challenged ambiguities upheld ("adjacent to", "incapable of self-care") and one overturned (`allocation-required` is not ambiguous — the separateness test is in (e)(1)'s third sentence, which **both** mappers read past). `<EXAMPLE>` elements are now indexed by the eCFR locator checker, so a worked example can be cited. #216 is decided by [0031](../docs/decisions/0031-an-example-that-bounds-a-term-is-recorded-as-a-bound.md): Map C does not adopt the blind map's shape, and the two (c)(4) bounds are `short-temporary-absences.ambiguity.bounds`, where an owner's ruling is compared against them. **Closes #8.** A citation *can* address a cross-reference: 16 of the map's 26 resolved `crossReferences` are anchored on a structural pointer and every one of the 26 resolves to an entry whose locator is a constituent — `§ 1.121-1(d)` ↔ `§ 1.121-1(e)`, a mutual qualification, proved by the locator checker. No schema change: the field was `crossReferences` all along, and #8's phrasing put the question on the wrong field. Also: deriving `dependsOn` from the corpus's own pointers would be wrong in 12 of 16 places; the `section-designation` grammar cannot have #207's duplicate-passage problem at all (every one of 37 spans occurs exactly once, against 20 of 48 SRD entries forced to extend); the first publishable trial map. Findings recorded, not decided: the eCFR XML runs `(e)(1)` into `(e)`'s element, so 18 of 37 citations are one level shallower than the regulation's own numbering; `<EXAMPLE>` is not indexed, and holds 12 of the section's 21 structural pointers; a Treasury regulation's examples are *worked answers that constrain a rule*, and the method has no category for them between "advice" and "rule"; `definedElsewhere` and `ambiguity` are mutually exclusive and one entry needs both; `definedElsewhere` can only name one corpus and "local law" is a class of them; `check-locators-section.py` has no `absence` check |
| 10 | [49 CFR § 172.101–§ 172.102](hazmat-172-table/) — the Hazardous Materials Table and the special provisions, 2026-01-01 | Rules stated as a grid, pointers that are codes rather than words, applicability encoded in the shape of an identifier, and a specific provision governing a general one | 135 (129 in scope) as first mapped | 7 (5% of in scope) | Admitted first, with the slice, both protocols and [the hypotheses H1–H6 written down before any entry existed](hazmat-172-table/README.md#the-hypotheses-before-anything-is-mapped) — which is what [#262](https://github.com/brandonifco/rules-factory/issues/262) is for. Phase 1 filed [#284](https://github.com/brandonifco/rules-factory/issues/284) (no `pointerMechanisms` value for a column 7 code, no `adapterReach` modality for an equation) and [#285](https://github.com/brandonifco/rules-factory/issues/285) (12 of the 20 provisions sit inside an `<EXTRACT>`), and both are now answered — by [0041](../docs/decisions/0041-a-coded-pointer-is-made-by-the-column-it-sits-in.md), [0045](../docs/decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md), [0046](../docs/decisions/0046-an-additional-rule-can-continue-a-definition.md) and [0036](../docs/decisions/0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md). **Step 2, the first mapping**: 135 entries over the seven settled rows, § 172.101(a)–(j), § 172.102(a) and (b)(1)–(9) and the 20 invoked provisions. **H1 holds, and the citation is what holds it** — `IB2, T4, TP1` states no rule as four tokens, and what makes it one is `row [column 2 = "Acetal"], column 7`, so the evidence model survives a grid *once the grid is addressable* (0035). Two strains, both recorded. The row stating IB2's additional requirement leaves column 1 blank, so read alone it states half a rule, and because it does not print the code it still cannot declare direct `defines`. That gap forced [#321](https://github.com/brandonifco/rules-factory/issues/321) and 0046: an explicit, structurally witnessed `continuesDefinition` now joins that passage to IB2 without weakening 0045, and 0044 therefore obliges every IB2 pointer to name both defining entries. A contiguous span can cover **several cells**, which H1 did not predict: `3 | UN1088 | II` is one span and one classification. H3 is recorded (23 gated entries, modal reach in `enabledBy` on every provision) and is **expressible but unchecked**: the committed mutation catalogue, run once over this map, misses both `drop-enabled-by` and `remove-applicability`, which is H6 falsified for this corpus too. 5 of 13 mutations detected, against 8/13, 8/13, 5/12, 3/14 and 4/10 on the five gate subjects — a tabular map is not measurably less checkable than a prose one. **Step 3, the blind second mapping, was not run**, so H5 is untested and every verdict rests on one mapper's reading plus the independent verdict on this map's bytes. **H4 found a representational limit**: version 1 of `mapping-inventory.json` named one corpus while `mapper inventory` walks every corpus a map cites (0042), so this two-corpus map could record no rejection and its 615 unaccounted units could not be told from unread ([#319](https://github.com/brandonifco/rules-factory/issues/319)). Version 2 now gives every rejection its corpus `sourceId` and partitions accounting by it; the approximate first-mapper record is not reconstructed into exact verdicts after the fact. Also filed: [#318](https://github.com/brandonifco/rules-factory/issues/318), `mapper pointers` never runs the coded-pointer detector (40 codes detected when `report()` is called by hand, 0 by the gate); [#320](https://github.com/brandonifco/rules-factory/issues/320), a quote under four words reaches no unit, so every single-cell entry is *not located*; [#322](https://github.com/brandonifco/rules-factory/issues/322), one quote marks two byte-identical rows reached; [#323](https://github.com/brandonifco/rules-factory/issues/323), resolved by [0047](../docs/decisions/0047-a-mapping-discovered-corpus-boundary-amends-admission-without-rewriting-it.md) and the complete section-designation grammar, the manifest's `references` are short of six sections the mapped spans point at. All 10 sweeps fire on both corpora, so neither protocol owes a `sweepCuesReason`. Numbered for its issue, and the only trial 10: [#286](https://github.com/brandonifco/rules-factory/issues/286) retired the validator attack's claim on the number |
| 11 | [FRCP 6, 12 and 81](frcp-6-12-81/) — Federal Rules of Civil Procedure, release point 119-110 | Procedural state, deadlines computed from a triggering event, a court's power to extend or forbid an extension, and applicability that is itself conditional | 83 (83 in scope) as first mapped | 1 (1.2% of in scope) | The last pre-1.0 architecture experiment ([#264](https://github.com/brandonifco/rules-factory/issues/264)), and the second trial to write [its hypotheses down before any entry existed](frcp-6-12-81/README.md#the-hypotheses-before-anything-is-mapped). **The slice is faithfully represented by the contract as it stood, and forced two repairs to the code that reads it** — no field, no unit, no relation, no value in a closed vocabulary. **H7 was falsified at admission and said so**: `section-designation` was spelled `§ 107.29` and only that, so a second designation-cited corpus could declare no extent at all; the unit is the structural address and now reads `Rule 6(a)(1)(A)` too. **`defined-term-use` read its vocabulary out of one index entry**, and the FRCP prints no index — *“Last Day”*, *“Next Day”*, *“Legal holiday”* are defined in the paragraphs the rules using them sit beside — so the mechanism now also reads 0045's distributed form. **H1, H2, H3 and H5 held**: sixteen computed deadlines are sixteen entries with the period, the trigger and the actor inside the quote; `suspendedBy` carries Rule 12(a)(4)'s *alteration* of six periods, because displacement is reachability plus a second rule; eight delegated standards are assertions and none became an ambiguity; and procedural history is a caller-supplied parameter with no entry and no state machine. **H4 held in the map and was falsified in the check**: the gate edges are recorded and `applicability-reach` sees none of Rule 81's seven applicability rules ([#420](https://github.com/brandonifco/rules-factory/issues/420)), because its phrase list spells the CFR *and* six of the seven gate a body of rules outside the slice. **H6 half**: 8 of 14 mutations detected, the best of any subject (against 8/13, 8/13, 5/12, 3/14 and 4/10), and deleting a gate still passes. Fourth citation grammar and fourth adapter, `uslm-xml`, held to each other unit for unit. **111 of 111 units accounted for from the first mapping**, the first map to manage it, and the first to declare an `extent.quoted` floor (85%, against 86% quoted). The independent reading required by 0063 step 3 agreed the first change was forced, **dissented on the second** — recorded in full, with the argument against it — and found four defects in the trial's own changes by mutation, each repaired with the test it earned. Findings recorded, not decided: [#421](https://github.com/brandonifco/rules-factory/issues/421) the term detector is case-sensitive and the corpus capitalises a definiendum it uses in lower case; [#422](https://github.com/brandonifco/rules-factory/issues/422) a defined term the corpus also uses as a verb can only be declared by leaving its vocabulary uninterrogated; [#423](https://github.com/brandonifco/rules-factory/issues/423) a pointer at a whole rule costs one item per target; [#424](https://github.com/brandonifco/rules-factory/issues/424) `references` names a document and this slice defers eleven times to a class of them. **No blind second mapping**, and nothing was built from the map |
| 12 | [SRD 5.2.1, the rest of *Playing the Game*](srd-52-playing-the-game/) — Wizards of the Coast, CC-BY-4.0, pp. 5–12 | The rules a page-cited corpus states **in tables**, and a third slice of one corpus ([#433](https://github.com/brandonifco/rules-factory/issues/433)) | 91 (80 in scope) | 4 (5% of in scope) | Chosen because trials 7 and 8 both use *D20 Test*, *ability check*, *Advantage* and *Proficiency Bonus* and neither defines them; this is the chapter that does. Its five hypotheses were [written down before any entry existed](srd-52-playing-the-game/README.md#the-hypotheses-before-anything-was-mapped). **H1 held and cost more than predicted**: seven of the eleven tables in the slice state rules, the page grammar has no address for a row (0035 gave one to `section-designation` only, and [#265](https://github.com/brandonifco/rules-factory/issues/265) left the page grammars alone), so `skills-table`'s eighteen rows and `actions-table`'s twelve are one entry each — and a rule-bearing column shares its citation with an advisory one, three row-stated rules are told apart by their quotes alone, and `mapping-protocol.json` can declare the unit `table-row` that no citation can name. **H2 held and generalised**: the heading path selects both printings of *Round Down*, and the reason is that every heading above the p. 5 printing is also above the p. 187 one — **the path can name the later of two identical printings and never the earlier** ([#436](https://github.com/brandonifco/rules-factory/issues/436), which also found `srd-52-combat`'s `round-down` surviving only by extending its span with a `{6}` marker, the practice 0030 retired). Settled by [0066](../docs/decisions/0066-the-cited-page-chooses-among-the-printings-the-heading-path-selects.md): the cited page chooses among the printings the path selects, this map gains `round-down` in scope, and the `{6}` is gone. **H3 held**: `heavily-obscured` is incomplete without the Blinded condition, that condition *is* mapped by trial 8 over the same pinned bytes, and `resolvedBy` holds an id in this map, so fifteen pointers into the Rules Glossary can only be recorded as `unmapped`. **H4 falsified, interestingly**: 12% declined against trial 7's 26% and trial 8's 34% — the chapter separates its own guidance into whole named sections — and what the chapter actually cost was **eight assertions**, 9%, behind only trial 1's 21%, because the GM's say is a parameter and not a vagueness. **H5 held for the wrong reason, and then did not hold**: 28 of 374 units unaccounted, and not H1 — [#437](https://github.com/brandonifco/rules-factory/issues/437), a defect this trial found, where `mapper inventory` could not locate a quote that straddles a page turn because `unmarked()` reused a line-anchored marker on a flattened quote, so two readers of the same map disagreed about the same bytes. Fixed; the pile closes at 300 reached, 74 rejected, 0 unaccounted, with the map's bytes untouched and four rejections withdrawn because `actions-table` quotes the units they named. Not predicted at all: **an extraction can split one sentence into two entries** — a column, a sidebar or an eighteen-row table lands between a sentence's halves, 0037 forbids an ellipsis inside a paragraph, and nothing in the map says the halves are one sentence; and **a run-in heading gets no line of its own**, so the level the SRD states many of its rules at cannot be cited ([#435](https://github.com/brandonifco/rules-factory/issues/435)). [#422](https://github.com/brandonifco/rules-factory/issues/422) measured: *Attack*, *Dodge* and *Influence* are defined terms the corpus also uses as ordinary words, 5 false namings in 144 from three mechanisms, and the only move is to leave them out of the vocabulary, which loses one true naming. No blind second mapping, no independent verdict, and nothing was built from the map. The second half of the chapter, *Damage and Healing* pp. 16–18, could not be sliced at all: a page extent had no `startsAfter` ([#434](https://github.com/brandonifco/rules-factory/issues/434)). It has one now ([0064](../docs/decisions/0064-a-page-extent-can-start-after-a-heading-and-the-heading-joins-two-maps.md)) — the mirror of the `endsBefore` trial 7 forced, cutting page `from` where that one cuts page `to` |
| — | [SRD 5.2.1, *Damage and Healing*](srd-52-damage-and-healing/) — Wizards of the Coast, CC-BY-4.0, pp. 16–18 | Nothing. It completes a chapter rather than stressing the method ([#434](https://github.com/brandonifco/rules-factory/issues/434)) | 42 (40 in scope) | 1 (3% of in scope) | **Not a numbered trial**, and the row is here because every map is listed: trial 12 could not declare this slice at all, and it was mapped as soon as [0064](../docs/decisions/0064-a-page-extent-can-start-after-a-heading-and-the-heading-joins-two-maps.md) gave a page extent `startsAfter`. It is the first committed map to declare one, and `extent-start` passed on the first run: *Damage and Healing* is one line on p. 16, and the two maps of that page are complementary. *Playing the Game* is now mapped end to end across three maps. Four other things turned up, three of them trial 12's met again: an extraction put the **whole Resting section** inside a sentence, so `hit-point-maximum` quotes a span ending mid-sentence under `split-by-sidebar` — a value named after a cause that is not this one; a quote crosses the p. 16/17 turn carrying `{17}`, which [#437](https://github.com/brandonifco/rules-factory/issues/437) fixed in time for the units it reaches to be counted; *Duration* is a run-in heading again ([#435](https://github.com/brandonifco/rules-factory/issues/435)), and again not forced; and the map's one ambiguity was nearly hidden in a `note` — `bloodied`'s *"half your Hit Points"* is half of something the passage does not name, now recorded as a question and ruled on by [0065](../docs/decisions/0065-bloodied-is-measured-against-the-hit-point-maximum.md). Seven of its 22 cross-references are `unmapped` and six point into the Rules Glossary that trial 8 maps over the same pinned bytes, which is trial 12's H3 from the other side. No blind second mapping, no independent verdict, nothing built from the map |

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
  and that is encouraging rather than evidence. [The validator attack](validator-attack/) supplies the
  validator's half of the answer, and more than half of the damage still gets through: fourteen
  kinds of deliberate damage over five committed maps, **28 of 62 refused and 34 passed** — and of
  those 28, **25 were refused by the rule the damage exercises and 3 only by another**, which
  [0061](../docs/decisions/0061-an-injection-names-the-refusal-it-expects-and-a-catch-by-another-rule-is-a-different-outcome.md)
  made the measurement able to say (16 and
  46 when first measured; of the twelve rows that have moved, two are 0034's epistemic checks, two
  are the `narrow-extent` cells [#269](https://github.com/brandonifco/rules-factory/issues/269)
  closed, and eight are the checks
  [#271](https://github.com/brandonifco/rules-factory/issues/271),
  [#268](https://github.com/brandonifco/rules-factory/issues/268) and
  [#225](https://github.com/brandonifco/rules-factory/issues/225) added). Four `enforcement` issues
  came out of it, three are closed, and the misses that remain are measured limits rather than
  argued ones.

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
