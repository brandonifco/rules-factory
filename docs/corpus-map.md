# The corpus map

The interface between reading a corpus and building an engine from it. Everything in
[method.md](method.md) phases 1–4 produces it; everything in phases 5–8 consumes it.

A map is a list of entries, one per rule the corpus states, plus the manifest of the corpora
they cite, plus a stamp naming the baseline it was built against:

```json
{ "schemaVersion": 1, "corpus": "cfr-14-107",
  "baseline": { "contentHash": "80f6bc4b…", "hashDerivation": "ecfr-versioner-xml",
                "asOf": "2026-01-01" },
  "extent": { "unit": "page", "from": 271, "to": 280 },
  "entries": [ … ] }
```

The stamp is not decoration. A map is true of **one state of one corpus**. Without it, two
maps cannot be compared, a map cannot be checked against the text it claims to describe, and
it silently outlives that text. The third trial's differ printed `2020-01-01 -> ?` for
exactly this reason.

## `extent` — how much of the corpus this map claims to have read

The baseline says *which text*. `extent` says *how much of it*, in the corpus's own units.
Added in [0009](decisions/0009-absence-is-a-verdict-with-evidence.md).

It is the field that makes "no entry anywhere cites this section" a **fact** rather than a
hope: `check-locators.py`'s `coverage` check names every page inside the extent that no
entry's located evidence reaches. A page nobody quoted is a page nobody demonstrably read, and that is
the state — *nobody looked* — a map exists to distinguish from a recorded verdict. It also
bounds an absence claim: see `absentFrom` below.

It is a property of the **map**, not of the corpus, and so it does not belong in the manifest.
`contentHash` and `licence` are true of the text whoever reads it; how far a mapper got is
true of one mapping.

**What it does not buy.** Nothing sizes it. A map declaring one page of a four-hundred-page
book covers that page and passes. The field buys that the claim is written down and can be
argued with — and that a map cannot quietly shrink its own extent to match what it happened to
read, which deriving the extent from the citations would have allowed: the backgammon
citations run 271–277, and the throw enumeration that #20 is about is on 278–280.

**One grammar today.** `unit: "page"` is checkable because page markers are in the text. A
`section-designation` corpus needs the paragraph-path equivalent and does not have one, so
`coverage` reports NOT VERIFIED there rather than passing.

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
  "note": "Demonstrate both tie directions, and the boundary where one side has one more hit."
}
```

### Fields

| Field | Meaning |
|---|---|
| `id` | Stable slug. Referenced by `dependsOn`, by issues, and by the engine's own citations. Never reused. |
| `name` | What the rule is called, in the corpus's language where it has one. |
| `locator` | Corpus id plus a citation in that corpus's grammar. **Required.** An entry without one is not an entry. |
| `kind` | `value`, `operation` or `assertion` — a fact the corpus states, a procedure it describes, or a condition only the caller can supply. See below. |
| `scope` | `in` or `out`. Out is a recorded verdict with a reason, not an omission. **Decided per rule. A section has no scope of its own.** See below. |
| `clarity` | `clear` or `ambiguous`. `clear` asserts the corpus determines exactly one answer for every valid input — so a corpus that states the rule twice, differently, is `ambiguous`. |
| `ambiguity` | Absent when clear. Otherwise the question, its `fate`, and — where the corpus contradicts itself — the `conflict` the question belongs to. Never a carrier for a decline that is not an ambiguity. |
| `dependsOn` | Entry ids. Determines backlog order — the sequence entries must be *implemented* in. **Not** a runtime precondition; see the gate fields. |
| `enabledBy` | Entry ids. The rules that make this one reachable at runtime; it does not apply until one holds. Absent on an entry no rule opens. Orders nothing. See below. |
| `suspendedBy` | Entry ids. The rules that make this one unreachable while they hold. Absent on an entry no rule closes. Orders nothing. See below. |
| `beyondAdapter` | Present only when the declared adapter cannot read the rule the locator cites. Names the adapter and the modality. See below. |
| `definedElsewhere` | Present only when the rule's meaning is fixed in a corpus that was not admitted. Names the manifest `references` entry. See below. |
| `absentFrom` | Present only when the corpus does **not** state the rule at all. Names the terms searched for. See below. |
| `crossReferences` | The pointers this entry's `evidence` makes, each resolved to an entry or to a recorded reason there is none. See below. |
| `evidence` | One contiguous verbatim span of the corpus: the passage that *states* this rule. Not a summary of it. See below. |
| `status` | Whether the engine has built this entry. Independent of `ambiguity.fate`. See below. |
| `implementedIn` | The ruleset revision that implemented it. Set when status becomes `implemented`. |

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

**Contiguous, and no ellipsis.** The checker matches the longest contiguous *prefix* of the
span, so a `...` in the middle silently reduces what was verified to the words before it — a
check reporting a pass over a fraction of what it appears to have read. `point-designations`
was exactly this: a 118-word `evidence` of which 11 words were ever checked. Truncating a
sentence at either end is fine; eliding its middle is not. Where the intervening text is not
itself the rule, include it — a shorter honest span beats a longer edited one. **If the rule
genuinely needs two separated passages, that is evidence the entry is two entries**, which is
the granularity finding the map already rests on.

**A span may straddle a page marker, and carries it verbatim.** The arrangement sentence begins
on p. 272 and the `{273}` marker falls mid-sentence. Citing either page is honest and the
checker accepts both; dropping the marker to make the quote read cleanly would break the match.

**What must be demonstrated is a mapper's reading, and it goes in `note`.** "Both figures",
"the worked distribution, for both the quatre and the trois", "a throw fully playable, partly
playable, and unplayable" — these are genuinely useful and no check can read them. They are
prose, and `note` is where prose lives, the same ruling 0004 made for `beyondAdapter`'s
explanation. A field for them would fail the test 0005 sets: it would name a distinction
without becoming checkable. The whole-table rule survives the move intact — **where the corpus
prints a finite table, the note requires the whole table and never a sample** — and so does the
rule that a span must cover every case the entry claims, not one of them.

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
of [method.md](method.md) says *cite, do not copy*, and for a `never-commit` corpus a span in
the map may be a licence problem rather than a discipline one. Then the entry says so and the
citation is unverifiable — which the checker reports, because an unlocatable entry fails the
run and is never counted as ok. What is not acceptable is a summary occupying the field and
looking like evidence. No trial has produced this case; both mapped corpora are public domain.

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

`ambiguity.unresolvedReason` names the `UnresolvedReason` the engine will return, and is
present when the fate is `unresolved`. It is the field that ties an entry to the
correspondence table below.

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
never asks: a regulation evaluating one flight against a set of limits has no phase for a
rule to be scoped to, and both Part 107 maps carry neither gate field on any entry.

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

`check-map.py --only cross-references` reads a closed list of pointer phrases out of each
entry's `evidence` and requires each to be claimed by a declaration whose `cites` appears
**verbatim in that same evidence** — the answer is anchored in the corpus's words rather than
asserted beside them — and resolved by exactly one of `resolvedBy` (an entry id in this map) or
`unmapped` (a reason there is none).

What an *"except as provided in"* clause obliges a mapper to do is therefore: **follow it, and
produce either an entry or a sentence saying why there is none.** Not a judgement about whether
the target matters.

**Two limits.** The phrase list is closed and short: `starting-position` quotes *"as shown in
{273} Fig. 1"* and the page marker falling inside the phrase hides it, so a corpus that points
somewhere in other words passes. And `unmapped` is prose, the carrier 0003 and 0004 both
rejected — what is checked is that a mapper was made to write one and anchored it, not that it
is true.

### `status`

```
mapped       enumerated and classified; not yet worked
blocked      a dependency is unmet
implemented  in the engine, with a recorded conformance verdict
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

`implemented` requires the verdict. Code without one is `mapped`, whatever the repository
contains — otherwise the map records intent rather than fact, and its whole value is that it
records fact. **Where `fate: unresolved` accompanies it, the verdict covers every case except
the one `ambiguity.question` names, and the declining case ships a test.**

The cost of decoupling, stated where the claim is: after it, `fate: unresolved` means the
engine declines for *at least one* input, not for every input, and nothing distinguishes an
entry that declines one shape of throw from one that declines everything. The totality claim
is weaker than it was.

**An entry whose correct reading is surprising names the test that proves it.** Not a field —
a flag saying "this is surprising" is unfalsifiable. `bearing-off-highest` is clear, correct,
and the opposite of what a modern player expects, and the useful artifact is the one test in
the suite that fails under the reading a reasonable person would have implemented. The entry
names it in `note`.

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

Row 8 is the one that is easy to get wrong. An assertion is not a failure to resolve; it is a
parameter. An engine returning `RequiresInterpretation` where the corpus named a decider is
declining a job the corpus gave it the means to do — and it discards whatever bounds the
corpus *did* state, which is what reading `stake-multiplier` as an ambiguity costs.

So an engine's honest answer about what it cannot do should be derivable from its map, and
an unresolved result that does not correspond to a map entry means something was implemented
without being mapped. That is a checkable invariant, and it is the first thing the factory
should enforce once it exists.

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
      "licence": "public-domain"
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
      "envVar": "CORE_RULES_PDF"
    }
  ]
}
```

`hashDerivation` and `boundaryPolicy` are the two fields most likely to be thought
redundant, and both are load-bearing. A digest without its derivation does not say what it
covers. A boundary policy is a property of the licence, and the two engines this method was
derived from answer it in opposite directions — one commits its extracted corpus because the
SRD is CC-BY, the other commits nothing because its rulebook is commercial.

`references` lists corpora this one defers to — a regulation citing another title, a
rulebook citing a supplement — each marked admitted or not. Those references are the
boundary of any engine built from the corpus, and naming them makes that boundary
inspectable rather than inferred from whichever entries happen to be declined. In the first
trial, three of twelve sections deferred their meaning to a corpus that had not been
admitted.

```json
"references": [
  { "sourceId": "cfr-49-171", "citation": "§ 171.8", "admitted": false },
  { "sourceId": "air-almanac", "admitted": false }
]
```

`asOf` is present only for a corpus that is revised over time. Absent means timeless, never
unknown. It pins which text is in force and nothing more — a rule may carry dates of its
own, which are ordinary operations over a date the caller supplies.

## Where the map lives

In the engine's own repository, under version control, beside the code it describes. It is
not a factory artifact that gets discarded after a run: it changes as the engine grows, and
its `status` fields are only true of a particular commit.

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
