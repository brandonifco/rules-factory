# Trial 8: a dense internal cross-reference graph — the SRD 5.2.1 conditions

A run of [the method](../../docs/method.md), phases 1–3, over the fifteen conditions the SRD
5.2.1 Rules Glossary defines, pp. 177–191. It exists to close
[#8](https://github.com/brandonifco/rules-factory/issues/8): the three corpora mapped before it
had **outward** references only — to another title of the CFR, to the Air Almanac, to an
illustration — and none had a dense **internal** graph where the corpus's own sections
routinely qualify each other. Here they do: Paralyzed, Petrified and Stunned each impose
Incapacitated, Unconscious imposes Incapacitated *and* Prone, and Petrified denies Poisoned.

**Status: a mapping trial, not a produced engine.** It follows
[faa-part-107-temporal](../faa-part-107-temporal/)'s precedent: a map, a manifest, a report and a
review record, and no `map-package.json`. #8's acceptance criteria ask for a trial with its own
report and the log updated, and nothing downstream consumes this map.

**The corpus is not duplicated.** `srd-5.2.1.txt` and the 6 MB PDF it is derived from stay where
[trial 7](../srd-52-combat/) committed them. This trial's manifest points `committedPath` at that
one copy and `scripts/validate.sh` points trial 7's locator checker at this map and at that text.

> This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of
> the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the
> Creative Commons Attribution 4.0 International License, available at
> https://creativecommons.org/licenses/by/4.0/legalcode.

That is the attribution statement the SRD's own Legal Information page (p. 1) requires, word for
word, and [CORPUS-LICENCE.txt](CORPUS-LICENCE.txt) carries it beside this map as it does beside
trial 7's.

## Admission

Nothing in Phase 1 is re-answered. The corpus is `srd-5.2.1` at
`contentHash c55926cb…`, `hashDerivation srd-5.2.1-pdftotext-24.02.0-page-marked`, adapter
`pdftotext-page-marked`, locator grammar `heading-path-and-printed-page`, `pin-in-repo`,
`committed-copy`, `quotation: verbatim`, `randomness: seeded`, with the same `pointerPhrases`
trial 7 derived from the text. Only two fields differ, and both are the "one corpus, two slices"
question:

**The manifest is restated, not referenced, and `committedPath` is relative.** There is no
include: `check-map.py` reads `corpus-manifest*.json` **beside the map** or from `--manifest`, and
an inline manifest inside the map is refused by name
([#60](https://github.com/brandonifco/rules-factory/issues/60)). So a second slice of one corpus
needs a second manifest file, and the only question is what its `committedPath` points at.
`check-postures` resolves it with `os.path.isfile(os.path.join(dirname(manifest), path))`, so
`"../srd-52-combat/srd-5.2.1.txt"` resolves and passes, and the repository holds one copy of the
text and one of the PDF. That is what this trial does. **The cost is that the duplication moves
rather than disappearing**: the digest, the derivation, the licence statement and the seven
pointer-phrase regexes are now written down twice, and nothing checks that the two copies agree.
A `contentHash` edited in one manifest and not the other would leave two maps claiming different
baselines for the same `sourceId`, and every checker in the repository would pass. That is a
finding, recorded below and not fixed here.

**`extent`: pages 177–191**, the glossary from *Blinded* to *Unconscious*. That range is not the
slice; see finding 1.

## The map

**100 entries**: 66 in scope, 34 out.

| | in scope | out of scope |
|---|---:|---:|
| operation | 64 | 32 |
| value | 2 | 2 |
| assertion | 0 | 0 |
| clear | 54 | 33 |
| ambiguous | **12 (18%)** | 1 |
| status | 66 `mapped` | 34 `declined` |

**The shape.** Three entries for the glossary's own *Condition* entry (p. 179) — what a condition
is, the list of fifteen, and the non-stacking rule with its Exhaustion exception. Then, for each
of the fifteen conditions, **one hub entry and one entry per named effect**: 15 hubs and 48
effects. The hub quotes the lead sentence — *"While you have the Blinded condition, you experience
the following effects."* — and `dependsOn` its effects. Then 34 `scope: out` entries for the rules
the slice leans on: the terms it is written in (ability check, attack roll, Advantage,
Disadvantage, D20 Test, saving throw, Critical Hit, Concentration, action, Bonus Action, Reaction,
Initiative, Speed, size, crawling, Round Down, Resistance, Immunity), and the rules elsewhere in
the same glossary that **impose** a condition or **end** one (Heavily Obscured, Grappling, Falling,
Flying, Hide, Knocking Out a Creature, Long Rest, Malnutrition, Suffocation, Dead, Unarmed Strike,
Blindsight, Truesight, Surprise).

**Why an effect is an entry.** Petrified states seven effects: a transformation, Incapacitated,
Speed 0, Advantage against you, automatic save failures, Resistance to all damage, and Immunity to
Poisoned. A single entry for Petrified would need "and" six times, which Phase 3 says is six
entries, and it would hide that one of the seven is undetermined and six are not. Per-effect
entries also show what one condition has and another lacks: Stunned turns out to be Paralyzed
minus the Speed clause and minus the automatic Critical Hits, and the map says so by having three
entries under one name that have no counterpart under the other.

**Why a hub.** The corpus points at *"the Incapacitated condition"* and never at one of its
effects. `dependsOn` holds entry ids, so the pointer needs an entry to name, and the lead sentence
is the one sentence that states the binding — these effects apply while you hold this condition.
Without hubs, `paralyzed-incapacitated` would have to name Incapacitated's four effects
separately, turning one reference the corpus makes into four edges it does not. **Whether the hub
is a rule or a mapper's scaffolding is the first thing a blind second mapping should attack**; it
is recorded in `review.json` as one of three things owed.

**12 ambiguous, and ten of them are one shape.** An effect states a determinate consequence over a
category the corpus never enumerates and delegates to nobody:

- *"any ability check that requires sight"* (`blinded-cant-see`) and *"that requires hearing"*
  (`deafened-cant-hear`) — the corpus never marks which checks require a sense;
- *"damaging abilities or magical effects"* and *"target the charmer"* (`charmed-cant-harm`);
- *"any ability check to interact with you socially"* (`charmed-social-advantage`);
- *"the source of fear"* (`frightened-checks-attacks`, `frightened-cant-approach`) — undefined,
  and no rule says the Frightened condition records what its source is;
- *"unless the effect's creator can somehow see you"* (`invisible-concealed`), and the same words
  plus *"this benefit"*, singular, where two benefits were stated (`invisible-attacks`);
- *"usually stone"*, the magical objects the transformation excludes, and *"you cease aging"*
  (`petrified-turned`);
- *"You're unaware of your surroundings"* (`unconscious-unaware`) — an effect that attaches to no
  rule anywhere in the corpus, so an engine that implements it and one that omits it answer every
  question identically.

The eleventh is `condition-definition`, and it is the slice's largest hole: the corpus calls a
condition *“a temporary game state”* and says *“various rules define how to end a
condition”*, and for nine of the fifteen — Blinded, Charmed, Deafened, Frightened, Invisible,
Paralyzed, Petrified, Poisoned and Stunned — no rule in the glossary says how the condition ends
at all. Prone and Exhaustion are the only two of the fifteen that state their own
ending; the other four that end at all are ended by a rule outside the slice.

The twelfth is the slice's **one conflict**, `can-a-long-rest-remove-exhaustion-from-malnutrition`:
Exhaustion (p. 181) says finishing a Long Rest removes 1 level, without qualification, and
Malnutrition (p. 185) says Exhaustion it caused *"can't be removed until the creature eats the full
amount of food required for a day"*. A starving creature that finishes a Long Rest is reached by
both. Both members are `unresolved`; the specific-governs reading is a Phase 4 decision and is not
taken here. The other member, `malnutrition-hazard`, is `scope: out` — which is what a conflict
between an in-scope rule and an out-of-scope one has to look like, since a conflict needs two
members and `check-map.py --only conflicts` does not require them to share a scope.

**18% against trial 7's 27%, and the difference is not smoothing.** The combat chapter is narrative
prose that stops to say *"the GM determines"*; the conditions glossary is written as an operative
list, and it shows: every one of the 48 effects states its consequence exactly, and the openings
are all in *what the consequence applies to*. Two verdicts were the closest calls, and both went to
`clear` deliberately. `incapacitated-surprised`'s effect is headed *"Surprised."* and gives the same
Initiative penalty the Surprise entry (p. 189) gives for being caught unawares — a shared label for
two triggers, which costs nothing because nothing in the corpus keys off the word, so the entry is
clear with the observation in its note. And `grappled-movable`'s *"two or more sizes smaller"* is
total once `creature-size` (p. 188) supplies the order, unlike trial 7's *"two sizes larger or
smaller"*, which left exactly-two open. The honest summary is that a glossary of conditions is the
most machine-followable prose the SRD has, and the residue is concentrated in one place.

**No assertions, and that is the right outcome.** Trial 7 found three, all *"the GM decides"*
constructions. The conditions glossary delegates nothing: it never says "at the GM's option" (the
neighbouring Climbing and Swimming entries do, two pages away), and gate 3 needs the caller's own
determination to be operative *and* a measure or a fixed set stated in the same constituent.
*"Somehow see you"*, *"the source of fear"* and *"requires sight"* each fail the second half, and
nobody is named to decide any of them, so all three are gaps
([0010](../../docs/decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md): being the only
possible source is not a reason to reclassify).

**No derived entries.** One candidate was found and rejected: a Paralyzed, Petrified or Stunned
creature cannot escape a grapple, because escaping costs an action (`grappling-ends`) and
`incapacitated-inactive` forbids actions. No sentence states it and two rules entail it — but
`derivedFrom` requires `scope: in` sources and both of those are outside the slice, so the
consequence is recorded in `grappling-ends`' note instead. It should be a test when anything builds
this.

**107 `crossReferences` items**, of which 5 sit on a pointer the check detects. See finding 3.

## The dependency graph, and its actual shape

The graph is real and it is **shallow and wide**, not deep:

```
action ─► incapacitated-inactive ─► incapacitated ─► paralyzed-incapacitated ─► paralyzed
```

That is the longest `dependsOn` chain in the map, and it is five entries. 142 edges over 100
entries; 22 entries name three or more dependencies; layered by depth the backlog is
41 / 35 / 14 / 6 / 4.

**Six edges, over five entries, are condition-to-condition**, and they are the reason the trial
exists:

| entry | depends on | the corpus's words |
|---|---|---|
| `paralyzed-incapacitated` | `incapacitated` | "You have the Incapacitated condition." |
| `petrified-incapacitated` | `incapacitated` | "You have the Incapacitated condition." |
| `stunned-incapacitated` | `incapacitated` | "You have the Incapacitated condition." |
| `unconscious-inert` | `incapacitated`, `prone` | "You have the Incapacitated and Prone conditions" |
| `petrified-poison-immunity` | `poisoned` | "You have Immunity to the Poisoned condition." |

`petrified-poison-immunity` is the one that runs the other way: it is the only edge in the slice
where one condition **denies** another, and it does it through a third rule, Immunity (p. 183).
`unconscious-inert` is the only place where one noun phrase makes two edges, and the
`crossReferences` items have to repeat the same `cites` twice to say so.

**The graph's real density is outward, not between the conditions.** `condition-definition` has 18
dependents; `attack-roll` has 13, `advantage` 10, `disadvantage` 9, `speed` 7. Twenty of the
thirty-four out-of-scope entries are named in some entry's `dependsOn`, which is to say they exist
only because an in-scope rule cannot be resolved without them. The corpus's internal web turns out to be mostly **condition → vocabulary**, with a thin
layer of **condition → condition** on top of it, and a second thin layer running the other way that
`dependsOn` never sees at all: seven out-of-slice rules *impose* a condition (Heavily Obscured
gives Blinded, Falling gives Prone, Hide gives Invisible, Long Rest gives Unconscious to every
creature that sleeps, Knocking Out gives Unconscious, and Unarmed Strike and Grappling give
Grappled) and six more say how one *ends* or a level of it is removed (Grappling's escape check,
Hide's list of ways to stop being hidden, Knocking Out's first aid, and the Long Rest, suffocation
and revival routes out of Exhaustion). Those are recorded as `crossReferences` and not as `dependsOn`, because the imposing
rule is not something a condition has to be built after — it is the condition that has to be built
first. The map has no field for "imposes", and did not need one: the edge is already the
`crossReferences` item, pointing the way the corpus points.

`flying-fall` is the sharpest single instance of the web: *"While flying, you fall if you have the
Incapacitated or Prone condition"*. Four conditions impose Incapacitated and one of them also imposes Prone,
so all four drop a flying creature out of the air through a rule none of them mentions — and then
`falling-hazard` imposes Prone on landing, which Unconscious had already imposed.

## Direct answers to #8's four questions

**Does `dependsOn` survive a corpus where most entries depend on several others?** Yes, without
strain, and it survives for a reason worth naming: **the dense part of the graph is not the part
`dependsOn` carries.** 142 edges, no cycle, a longest chain of five and a clean five-layer
topological order. What `dependsOn` never had to express is the seven rules that impose a
condition and the six that end one, which run in the opposite direction from implementation order,
and `crossReferences` already holds them. The field the density pressed on hardest was not `dependsOn`
at all; it was `evidence` (finding 2).

**Can a citation address a cross-reference — one entry's locator pointing at the constituent of
another?** It did not have to, because **the SRD never points at a constituent.** Every one of the
51 condition-name references in the slice names a condition *as a whole*: "the Incapacitated
condition", never "Incapacitated's Inactive effect". The question #8 asked — can `§ 107.29(a)` name
`§ 107.65` — has an answer here only in the sense that `resolvedBy` names an entry id and an entry
id can be any granularity the mapper chose. What the corpus's own habit forced instead was the
opposite move: a hub entry per condition, so that the *whole* is nameable at all. If a corpus did
point at a constituent, this map shows the machinery would work — `petrified-poison-immunity`
points at `poisoned` through a third rule and resolves fine — but this corpus does not, and the
trial cannot claim to have tested it.

**Does the map become unreadable at that density?** **The entries do not; the file does.** Each
entry is still one rule, one span, one verdict, and reads in fifteen seconds. What stopped being
readable is the whole: 100 entries, 142 `dependsOn` edges and 107 `crossReferences` items in one
2,325-line JSON file, in which the fact that five entries quote a word-for-word identical sentence
is invisible, and the fact that `incapacitated` has 4 dependents while `condition-definition` has
18 can only be got by running a script. **What that implies for automation is narrow and specific:
nothing here needs a new field, and everything here needs a view.** The three facts this report
states about the graph — longest chain, in-degree, the condition-to-condition edge list — were each
produced by ten lines of Python over the committed map, and none of them is stated in the map. A
map at this density wants a *derived* rendering (a graph, a layered backlog, a duplicate-span
report) that is regenerated and never committed, exactly as `check-locators` derives coverage
rather than the map declaring it. Adding a field for any of it would fail
[0005](../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md)'s test: it would be
a second copy of something the data already determines.

**Is the backlog ordering the dependency graph produces actually workable?** Yes, and it is better
than the corpus's own order, which is what Phase 5 claims. The five layers are:

1. **41 entries** — all 34 `scope: out` entries (the vocabulary, and the rules elsewhere that
   impose or end a condition), plus the seven in-scope entries that depend on nothing:
   `condition-definition`, `charmed-cant-harm`, `frightened-cant-approach`,
   `incapacitated-speechless`, `invisible-concealed`, `petrified-turned` and `unconscious-unaware`;
2. **35 entries** — the effects that consume the vocabulary, and `condition-list`;
3. **14** — the ten hubs whose effects are all in layers 1–2 (Blinded, Charmed, Deafened,
   Frightened, Grappled, Incapacitated, Invisible, Poisoned, Prone, Restrained),
   `condition-no-stacking`, and the three Exhaustion effects that depend on `exhaustion-levels`;
4. **6** — the `exhaustion` hub, and the five condition-to-condition effects:
   `paralyzed-incapacitated`, `petrified-incapacitated`, `stunned-incapacitated`,
   `unconscious-inert`, `petrified-poison-immunity`;
5. **4** — Paralyzed, Petrified, Stunned, Unconscious.

The four conditions that impose others come **last**, which is right and is the opposite of the
glossary's alphabetical order, where Paralyzed (p. 186) precedes Stunned (p. 189) and Incapacitated
(p. 184) precedes both by accident. It also confirms trial 7's batching finding from the other
side: a batch cut by subject — "the conditions that stop you acting", say — would have had to build
`action`, `bonus-action` and `reaction` from layer 1, which nobody would have assigned it. Cut by
layer, nothing crosses.

## Findings: where the method and schema did not fit

### 1. `extent` cannot describe a slice that is a set of definitions scattered through a glossary

The slice is sixteen glossary entries. They sit on ten of the fifteen pages from 177 to 191, and
the five pages between them (180, 183, 185, 188, 190) carry nothing about conditions except in
passing. `extent` has two units: a **page range** and a **list of section designations**
([0020](../../docs/decisions/0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)),
and the section list is for the section-designation grammar, which this corpus does not use. So the
extent is `{"unit": "page", "from": 177, "to": 191}` — a claim to have read fifteen pages of a
364-page glossary in order to map sixteen of its entries.

0020 gave the section unit a **list** precisely because "what a mapper reads of a CFR part is not
contiguous". The same is true here and the page unit has no list. `endsBefore` (0024) solves the
mirror-image problem — a slice that stops in the middle of its last page — and nothing solves this
one.

**What it cost, and it was not nothing.** `coverage` names every page in the extent no entry
reaches, so the map had to reach five pages that are not in the slice. That turned out well and
should not be read as harmless: the entries that cover them are `d20-test` and
`dead-revival-conditions` (p. 180), `hide-action` and `immunity` (p. 183), `long-rest`,
`long-rest-exhaustion` and `malnutrition-hazard` (p. 185), `speed` and `creature-size` (p. 188),
`truesight` and `unarmed-strike-grapple` (p. 190), and every one of them is a rule the slice
genuinely needed. But that is luck. A slice whose scattered definitions happened to skip a page of
spell descriptions would have had to either over-claim the extent or invent an entry, and the
method offers no third answer. Recorded, not decided.

### 2. `evidence` is where density actually broke, and it broke twice — since fixed

**Fixed by [#207](https://github.com/brandonifco/rules-factory/issues/207) and
[0030](../../docs/decisions/0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md).**
What follows is the finding as this trial made it, and the state it describes is the state before
that decision. The citation's **heading path** now identifies which printing of a repeated passage
an entry means, so all twenty entries quote their own sentence and `round-down` quotes *Round Down*
and nothing else. What could not be reached is recorded at the end of this finding.

**A rule the corpus states word for word five times cannot be cited on its own.** `evidence` is one
contiguous verbatim span, and `check-locators-pdf-text.py` requires **every** occurrence of it to
touch the cited page — correctly, because a quote that resolves on five pages resolves on none.
*"Speed 0. Your Speed is 0 and can't increase."* occurs five times (Grappled, Paralyzed, Petrified,
Restrained, Unconscious). *"Saving Throws Affected. You automatically fail Strength and Dexterity
saving throws."* occurs four. *"Attacks Affected. Attack rolls against you have Advantage."* occurs
five, three as itself and twice as a prefix of the longer Blinded and Restrained sentences.
*"Incapacitated. You have the Incapacitated condition."* occurs three. So **twenty of the 48
effect entries cannot quote their own rule**: each has to begin its span at the condition's lead
sentence and run forward through every effect between, and the last effect of Unconscious quotes
the whole condition. The quotes are honest and verbatim and the checker verifies all 100. They are
also nested, repetitive, and much longer than the rule they carry, and a reader comparing
`paralyzed-speed-0` with `petrified-speed-0` is comparing two spans that differ only in a word of
their preamble.

This is not a defect in the rule that `evidence` be one contiguous verbatim span — that rule is
what makes the citation checkable at all, and #18 is the evidence for it. It is the first case
where **the corpus's own repetition, not the mapper's laziness, is what makes a span ambiguous**,
and there is nowhere to say so. `extraction` says the text garbles a passage; nothing says the text
states a passage more than once and the entry means this one.

**And one rule cannot be cited at all without annexing its neighbour.** *Round Down* is printed
twice, identically, in Playing the Game (p. 5) and in the Rules Glossary (p. 187) — heading
included, so even quoting the heading does not separate them. `prone-restricted-movement` depends
on it (*"half your Speed (round down)"*), so it needs an entry, and no span of the rule itself can
be located. The map cites p. 187 and its span runs on into the whole of the next glossary entry:
*"…tell you to round up. Save Save is another name for a saving throw."* That passes every check
and it is a span whose last sentence is a different rule. Recorded as the sharpest thing this trial
found, and at the time not fixed: a `occurrence` discriminator on the locator, or an `evidence` that
may name which occurrence it means, is a schema change that one instance does not justify
([0005](../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md)), and two more
instances would.

**What #207 did, and what it did not reach.** No field was added and no schema changed: the
citations were already `Rules Glossary / <heading> / p. N`, and the checker was discarding the only
part of them capable of telling two printings apart. Twenty-one spans are now the rule the entry is
about — the twenty effects, and `round-down`, which is why the map now carries twenty-one quotes
the corpus prints more than once and verifies all of them. Two limits stand. A citation whose last
heading is itself repeated is separated only by a heading above it that is not, so `Playing the
Game / Round Down / p. 5` could not be written: the extraction does not record where a chapter ends,
and the checker refuses rather than choosing. And the whole mechanism rests on pdftotext emitting a
heading as a line of its own; a corpus whose headings run into their text would be back where this
finding started.

### 3. The pointer-phrase regexes detect **none** of the internal graph, and cannot

This is trial 7's finding 4 asked again after
[0026](../../docs/decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)
fixed it, and the answer is worse than trial 7's, not better.

Run against the sixteen glossary definitions that are this slice, the SRD's seven declared
`pointerPhrases` detect **0 pointers**, and so does the built-in list. The same sixteen passages
contain **51 bare condition-name references**. Over the whole map — including the 34 out-of-slice
entries — the check reports **5 pointers in 100 quoted spans**, and all five are `See also "…"`
sentences in glossary entries *outside* the slice (Crawling, Heavily Obscured, Grappling, Flying,
Malnutrition). Of the 107 `crossReferences` items the map declares, **5 sit on a detected pointer
and 102 are obliged by nothing.**

The reason is structural and not a gap in the list. **This corpus points at another of its passages
by using the term**, and the same words make a self-reference: *"You have the Incapacitated
condition"* in Paralyzed is a pointer, and *"While you have the Incapacitated condition"* in
Incapacitated's own lead sentence is not. A regex over the fifteen names — which is the only regex
that would catch the graph — fires on both, and `check-map.py` refuses a `crossReferences` item
whose `resolvedBy` is the entry itself. The built-in list's own comment already rules this out:
*"a check that fires on a self-reference teaches mappers to work around it."* So the honest
declaration for this corpus is the one trial 7 wrote, and it will keep reporting a near-zero on
exactly the corpus #8 was opened about.

**What would work is not a phrase and not a regex.** Every one of the 51 references names an entry
this same map defines, and the map already knows the fifteen names, because `condition-list` is a
`kind: value` entry holding them. A check that read a *declared vocabulary* out of the map and
required each occurrence of a term to be claimed — excluding the entry that defines it — would
oblige all 51. That is a real proposal and it is not made here: it is a checker change, it needs
the "excluding the definition" rule to be written down before it can be trusted, and one corpus is
not enough to write a vocabulary mechanism from. 0026's `pointerPhrases` stays as it is, and the
finding is that **a phrase list is the wrong instrument for a corpus whose pointer is a proper
noun** — which is the single most important thing this trial has to say about automation.

The half of 0026 that does work, works well: the **term-anchored `crossReferences` item**
(`{"cites": "the Incapacitated condition", "resolvedBy": "incapacitated"}`) carried all 102
undetected references without strain, and the anchor rule — `cites` must appear verbatim in the
same evidence — caught one real error during this mapping, a `"the grappler"` written where the
corpus says `"The grappler"`.

### 4. A second slice of one corpus duplicates its manifest, and nothing compares the copies

Answered under Admission above, and repeated here because it is a finding and not a decision.
`check-map.py` reads the manifest beside the map, refuses an inline one (#60), and has no include.
So `contentHash`, `hashDerivation`, the licence statement and seven regexes are now written twice
in this repository, and `corpus-manifest.json` in `srd-52-conditions/` could drift from
`srd-52-combat/`'s without any checker noticing. The relative `committedPath` at least means the
*bytes* cannot drift. A check that two manifests declaring the same `sourceId` declare the same
baseline is cheap and is not written here.

### 5. A conflict can cross the slice boundary, and `scope` does not stop it

`check-map.py --only conflicts` requires two or more members, one `fate`, and one decision record
where the fate is `decision`. It says nothing about `scope`, and this trial needed that: the
Exhaustion/Malnutrition contradiction has one member in scope and one out. Trial 7's conflict had
both members in scope and a page apart; this one is fifteen pages apart and across the boundary of
the slice. It worked as written, and it is worth recording that it worked, because an
out-of-scope entry carrying an `ambiguity` block reads oddly — row 1 of the correspondence table
dominates, so the engine returns `OutsideCurrentScope` for it and the recorded question is for the
mapper and the reviewer, not for the runtime.

### 6. A condition presupposes state that no rule says a condition carries

Not a schema finding — a finding about the corpus that the map can only record in `note` and
`ambiguity.question`. Four of the fifteen are defined against a party: *the charmer*, *the source
of fear*, *the grappler*, and Invisible's *the effect's creator*. Nothing in the SRD says that a
condition records anything at all; `condition-definition` says only that it is "a temporary game
state". An engine has to carry a referent with three of the fifteen conditions on the strength of
sentences that presuppose one and never grant it. `charmed-cant-harm` and both Frightened entries
are `ambiguous` partly for this reason; `grappled-attacks` and `grappled-movable` are not, because
`grappling-imposes` names the grappler and `dependsOn` reaches it.

## What a blind second mapping is owed

`review.json` records this map as an `exemption` of kind `legacy` naming #8 — the same misfit trial
7 recorded in its finding 8, and used for the same reason: it is the only kind that names a
tracking issue, and `non-semantic` needs a reviewed map to depart from. Nothing downstream consumes
this map, and a blind second mapping (0014) is owed before anything does. Three things it should
attack first: whether the fifteen hub entries are rules or scaffolding; whether the twelve
ambiguity verdicts are the right twelve, since 18% is below trial 7's 27% and this report argues
genre rather than rigour; and whether the 107 `crossReferences` are complete, since finding 3 means
nothing obliged 102 of them.

## How the evidence spans were produced

The classification, the granularity, the verdicts and the notes are the mapper's. The `evidence`
bytes are not typed: each span was asserted to occur exactly once in the committed
`srd-5.2.1.txt`, and on the page its locator cites, and the characters the map carries are the
corpus's own. That is a precaution against the failure #18 names — thirteen wrong citations that
survived a build because `evidence` held a summary — applied at the point where 100 spans have to
be right rather than 24.
