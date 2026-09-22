# Trial 11 — Federal Rules of Civil Procedure 6, 12 and 81

Run of [the method](../../docs/method.md) against a corpus chosen for a different axis of
attack from every corpus before it. [#264](https://github.com/brandonifco/rules-factory/issues/264)
is the trial; [#265](https://github.com/brandonifco/rules-factory/issues/265) is why a trial is
run before a concept is admitted, and
[0063](../../docs/decisions/0063-no-new-map-concept-without-a-corpus-that-forces-it.md) is the
rule that governs what this trial is allowed to change.

**It is the last pre-1.0 architecture experiment.** What it is for is to find out whether the
map contract, exactly as it stands, can say what this corpus says. Not whether a nicer contract
could.

## Why this corpus

Where trial 10's Hazardous Materials Table attacks *where a rule lives*, the Federal Rules of
Civil Procedure attack **when a rule applies and who may change it**:

- **Rule 6** is exact calendar arithmetic — count forward, count backward, exclude the trigger
  day, roll off weekends and legal holidays, an inaccessible clerk's office — sitting directly
  beside `for good cause`, `excusable neglect` and a court's order, and with a short list of
  extensions a court **must not** grant. Computation an engine can do to the day, and delegation
  it cannot, in one rule.
- **Rule 12** hangs deadlines off **procedural state**: what was served, what was waived, what
  was joined, what is preserved. A deadline whose condition is history is a gate no mapped
  corpus has had.
- **Rule 81** makes **applicability itself conditional** across whole classes of proceeding, and
  then gives removed actions their own deadlines on top.

Nothing in the six committed maps has any of this. The nearest is § 1.121-1(f)'s flat effective
date, which gates a section and turns on nothing.

## The admission record

| | |
|---|---|
| `sourceId` | `frcp-6-12-81` |
| Title | Federal Rules of Civil Procedure, Rules 6, 12 and 81 |
| Adapter | `uslm-xml` |
| Locator grammar | `section-designation` — `Rule 6(a)(1)(A)` |
| `contentHash` | `d4e63d1f…` over [`frcp-6-12-81.xml`](frcp-6-12-81.xml) |
| `hashDerivation` | `uslm-courtrule-without-usc-notes` |
| `asOf` | 2025-12-03, the release point's own stamp |
| Licence | `public-domain-us-government` ([CORPUS-LICENCE.txt](CORPUS-LICENCE.txt)) |
| Posture | `pin-in-repo`, `committed-copy`, `quotation: verbatim`, `randomness: none` |
| Retrieved from | `https://uscode.house.gov/download/releasepoints/us/pl/119/110/xml_usc28A@119-110.zip` |

### Why the committed bytes are a derivation

The Office of Law Revision Counsel serves Title 28 Appendix as **one** 4.7 MB USLM document
holding the Appellate, Civil and Evidence rules together. Every other corpus this repository
admits arrives as its own served document — the eCFR versioner returns one section, Project
Gutenberg returns one book — so `retrievedFrom` alone has always said what the digest covers.
Here it cannot: a digest over the release would cover two other rulebooks, and no reader could
tell which bytes a quote is held to.

[`derive-corpus.py`](derive-corpus.py) is the derivation, and `hashDerivation` names it. It takes
the three `<courtRule>` elements **verbatim from the release's bytes** — by text scan, not by
parse and re-serialise, so nothing rewrites an entity reference or an attribute order — and drops
one child of each: `<notes type="uscNote">`, the Notes of the Advisory Committee on Rules and the
editorial amendment notes. `derive-corpus.py --from <release> --check frcp-6-12-81.xml` re-derives
and compares.

**Dropping the notes is an admission decision and it has a cost.** The Advisory Committee Notes
are transmitted with the rules and courts read them as an interpretive aid; they are not the
rule, which is what the Supreme Court prescribed under 28 U.S.C. 2072 and Congress let take
effect. A map built over them would quote a commentator's account of a rule as though it were
the rule. What it costs is stated rather than hidden: **no entry of this map may be supported by
an Advisory Committee Note, and a rule stated only in one is beyond this adapter's reach.** The
`<sourceCredit>` is kept, because it is the rule's own amendment history and is inside the
`<courtRule>` element the Code prints.

## The slice

All of Rule 6, all of Rule 12, all of Rule 81. Three whole rules and no part of a fourth:
15,549 characters of whitespace-normalised text — 4,569 in Rule 6, 6,250 in Rule 12, 4,730 in
Rule 81 — against the ~8,000 characters both of the first two trials took.

Whole rather than sliced, because every question this trial asks is about how the rules reach
each other. Rule 6(a) is what every period in Rule 12 and Rule 81(c) is counted by; Rule 6(b) is
what a court may do to any of them; Rule 81(a) is what decides whether any of it applies at all.
A slice that cut inside one of the three would produce a map whose gates point outside it, which
is the shape trial 9 already measured.

## The hypotheses, before anything is mapped

Written from a reading of the corpus and before a single entry exists, so that the map cannot be
read backwards into a confirmation. A run that confirms all seven is a failure to have picked a
hard enough corpus.

- **H1 — a computed deadline is one entry.** *"within 21 days after being served with the summons
  and complaint"* states a period, a trigger and an actor in one sentence. H1 says that is one
  `kind: operation` entry which `dependsOn` Rule 6(a)'s counting rules, and that no field is
  needed to hold the period, the unit or the triggering event: they are in the quote, and what
  computes them is the engine's code, which the map deliberately does not type
  ([corpus-map.md](../../docs/corpus-map.md), *the map declares no types*).
- **H2 — the two gate fields carry a court's power over time.** Rule 6(b)(1) lets a court extend
  any period for good cause; Rule 6(b)(2) forbids it for six named rules; Rule 6(c)(1)(C) lets a
  court order displace the 14-day notice period; Rule 12(a)(4) says a motion alters the Rule 12(a)
  periods. H2 says `enabledBy` and `suspendedBy`, holding entry ids and nothing else
  ([0003](../../docs/decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md),
  [0011](../../docs/decisions/0011-a-gate-has-a-direction.md)), express all four with no new
  relation, and that whether a gate holds is a fact the caller states
  ([0021](../../docs/decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md)).
- **H3 — delegated judgement is an assertion, not an ambiguity.** *"for good cause"*, *"excusable
  neglect"*, *"so vague or ambiguous that the party cannot reasonably prepare a response"*,
  *"early enough not to delay trial"*, *"to the extent applicable"*. H3 says these are open terms
  the corpus deliberately delegated with a measure, so they are `kind: assertion` with
  `assertedBy` naming the court
  ([0025](../../docs/decisions/0025-an-assertion-names-who-asserts-it-and-an-operation-names-what-it-draws.md)),
  and that `clarity: ambiguous` would report a deliberate delegation as a defect.
- **H4 — conditional applicability is a gate.** Rule 81(a) turns whole classes of proceeding on
  and off; Rule 81(c)(1) turns the rules on for a removed action. H4 says these are ordinary
  entries named in `enabledBy` / `suspendedBy`, and that
  [`applicability-reach`](../../docs/validator.md) sees them.
- **H5 — procedural history is a caller-supplied parameter and gets no entry.** What was served,
  waived, joined or omitted is a fact about a case, not a rule of the corpus, so phase 4's gate 1
  gives it no entry and the rules that turn on it are ordinary operations over facts the caller
  states. H5 says the map needs no state machine and no `state` field.
- **H6 — the existing checks can see a removed deadline.** Deleting a period, a trigger or a gate
  from one entry is caught by something other than a person's memory. Trial 10 falsified its own
  H6 on a tabular corpus; this asks the same question of prose.
- **H7 — the contract can read this corpus's designations.** `Rule 6(a)(1)(A)` is a structural
  designation, listed and not ranged, exactly as `§ 107.29(a)(2)` is, and
  `extent.unit: "section-designation"` is the unit for it. **Already known to be strained at
  admission** — see below — and stated anyway, because what is strained and what is broken are
  different findings.

### What would falsify each

| | Falsified if |
|---|---|
| H1 | the period, the unit or the triggering event has to go in a field the contract does not have, or splitting a deadline sentence produces two entries neither of which states a rule |
| H2 | a rule that *alters* a period rather than enabling or suspending one has to be recorded as a gate that is false about the corpus, or the relation ends up in a `note` |
| H3 | one of the delegated terms states no measure **and** names no party, so it is neither an assertion nor a clear rule, and `ambiguity` cannot hold it either |
| H4 | an applicability whose condition is a class of proceeding cannot be a gate because the class has no entry, or `applicability-reach` cannot see a gate whose reach is a corpus outside the slice |
| H5 | a waiver rule — Rule 12(g)(2), Rule 12(h)(1) — cannot be stated without the map recording what has already happened in the case |
| H6 | deleting a period from an entry's evidence, or a `dependsOn` edge to Rule 6(a), passes `check-map.py` and the locator run |
| H7 | the contract's reading of `section-designation` is CFR-specific, and a second designation-cited corpus needs a new `extent.unit` value — which under 0063 is a new map concept and needs the full four steps |

### H7 is strained at admission, and the strain is recorded here before it is repaired

`tools/mapvalidator/locators.py` reads a `section-designation` citation with two expressions
copied from `examples/faa-part-107/check-locators-section.py`:

```python
CITE_SECTION   = re.compile(r"§+\s*(\d+\.\d+(?:[A-Za-z]|-\d+)?)(?![A-Za-z0-9-])")
EXTENT_SECTION = re.compile(r"^§\s*(\d+\.\d+(?:[A-Za-z]|-\d+)?)$")
```

Both spell the Code of Federal Regulations and only it. `Rule 6` matches neither, so before a
single entry is written it is already certain that *something* must change for this corpus to be
citable at all. What the trial has to decide is **which** thing, and 0063 is what decides it: a
value in a closed vocabulary is a map concept and needs a corpus that forces it; a check that
reads the wrong thing is a repair and does not. The answer is recorded under
[the outcome](#the-outcome) with the reasoning, not here.

## The outcome

The bounded FRCP 6/12/81 slice is **faithfully represented by the architecture as it stood**,
with two repairs to shared code that the corpus forced and no new map concept. `#264`'s hard
stop is reached at B: concrete representational failures met while mapping, repaired with the
smallest forced changes, and the slice then maps.

### The map

| | |
|---|---|
| Entries | **83** — 29 in Rule 6, 33 in Rule 12, 21 in Rule 81 |
| Kinds | 66 operation, 9 value, 8 assertion |
| Scope | 83 `in`, 0 `out` — the slice is three whole rules, so nothing in it is beyond the engine the corpus bounds |
| Ambiguous | **1 of 83 (1.2%)**, against 5%–27% on the six maps before it |
| Gates | 42 `enabledBy` edges on 42 entries, 10 `suspendedBy` edges on 9 |
| `dependsOn` | 31 edges, acyclic |
| `crossReferences` | 89 items: 43 resolved to an entry, 46 recorded as unmapped |
| `defines` | 6 terms in 3 vocabularies |
| Units accounted | **111 of 111** — 96 reached by a quote, 15 recorded as examined and rejected, **0 unaccounted** |
| Quoted | 86% of the declared extent, against a declared floor of 85% — the first committed map to declare one |
| Pointers | 51 detected by phrase, 10 by defined-term use, every one declared |

Zero unaccounted units is the first time a committed map has managed it from its first mapping.
It is not a virtue of the mapper: it is what a slice of three whole rules buys, where
`srd-52-conditions` claims fifteen glossary pages to map sixteen scattered entries and reports
407 unaccounted. The lesson is about choosing an extent, not about care.

**The ambiguity rate is the number to be suspicious of.** One open question in 83 entries is far
below every previous map, and the honest reading is not that the Federal Rules are clearer than a
tax regulation. It is that this corpus delegates rather than leaves gaps: *"for good cause"*,
*"excusable neglect"*, *"early enough not to delay trial"* are eight assertions, and under the
method's own § 107.39 test — **the measure decides** — an assertion is not an ambiguity. A second
reader who thinks two or three of those eight state no measure would move the rate to 4%, which
is why `review.json` names it as the first thing a second reading should attack.

### The seven hypotheses, reported

| | Verdict |
|---|---|
| **H1 — a computed deadline is one entry** | **Held.** Sixteen computed deadlines, each one entry with the period, the trigger and the actor inside the quote, and `dependsOn` naming Rule 6(a). No field holds a period, a unit or a triggering event. The one place it strained is recorded below. |
| **H2 — the two gate fields carry a court's power over time** | **Held, and Rule 12(a)(4) is the case worth arguing about.** See below. |
| **H3 — delegated judgement is an assertion, not an ambiguity** | **Held.** Eight assertions: two attributed to the court, one to the party, one to the President or Congress, one to the state, three to `caller` where the sentence names no decider. Zero of the delegated terms became `clarity: ambiguous`. |
| **H4 — conditional applicability is a gate** | **Held in the map and falsified in the check.** The relation is expressible and recorded; `applicability-reach` sees none of it, for two independent reasons ([#420](https://github.com/brandonifco/rules-factory/issues/420)). |
| **H5 — procedural history is a caller-supplied parameter and gets no entry** | **Held.** Rule 12(g)(2) and Rule 12(h)(1) turn on *"available to the party but omitted from its earlier motion"* and are ordinary operations over a fact the caller states. No state machine, no `state` field, and nothing in the map describes a case's history. |
| **H6 — the existing checks can see a removed deadline** | **Half.** The committed mutation catalogue, run once over this map: **8 of 14 detected**, the best rate of any subject (against 8/13, 8/13, 5/12, 3/14 and 4/10). `move-locator`, `neighbour-evidence`, `narrow-extent` and both ambiguity mutations are caught. `drop-entry`, `drop-enabled-by`, `drop-suspended-by`, `invent-depends-on`, `omit-definition` and `assertion-to-operation` are missed — so **deleting a gate passes**, which is trial 10's finding on prose. |
| **H7 — the contract can read this corpus's designations** | **Falsified, as predicted at admission**, and repaired. |

### H2, and the one relation this trial had to argue about

Rule 12(a)(4) is the sharpest case in the slice:

> **(4) Effect of a Motion.** Unless the court sets a different time, serving a motion under this
> rule **alters these periods** as follows:

It does not switch a rule on, and it does not switch one off. It *replaces* six periods with two
others. `enabledBy` and `suspendedBy` are the only relations available, and H2's falsifier was
"a rule that alters a period rather than enabling or suspending one has to be recorded as a gate
that is false about the corpus."

The map records `suspendedBy: ["motion-alters-periods"]` on all six Rule 12(a) periods, and the
reading is this: while a motion under Rule 12 is before the court, **none of those six periods
determines the answer date**. That is what `suspendedBy` says — *the rules that make this one
unreachable while they hold* — and it is true of the corpus. What replaces them is stated by
Rule 12(a)(4)(A) and (B), which are entries of their own, `enabledBy` the same rule. Nothing is
recorded as an adjustment to a period, because the corpus does not state one.

So H2 holds, and the claim is narrow: the gate fields carry *displacement*, because displacement
is reachability plus a second rule. They would not carry an *arithmetic* change — "add three days
to whatever the period was" — and the slice has one of those too, Rule 6(d), which is an ordinary
operation and no gate at all.

The same shape holds for Rule 6(b)(1) (`suspendedBy: extension-forbidden`, six rules a court must
not extend) and Rule 6(c)(1) (`suspendedBy: ex-parte-application-for-a-different-time`).

### H7, and what the corpus forced

Two changes to shared code, both repairs under
[0063](../../docs/decisions/0063-no-new-map-concept-without-a-corpus-that-forces-it.md) —
*"a check that reads the wrong thing"* — and neither adding a field, a unit, a relation or a
value in a closed vocabulary.

**1. `section-designation` spelled the CFR and only it.** `CITE_SECTION` and `EXTENT_SECTION` in
`tools/mapvalidator/locators.py` read `§ 107.29(a)(2)`; `Rule 6` matched neither, so before a
single entry existed this corpus could declare no extent at all and every in-scope citation would
have been refused as outside it. The unit is the *structural address* — a top-level designation
plus a path of parenthesised designators, listed rather than ranged — and the sign in front is the
corpus's house style. The alternative was a third `extent.unit` value, which under 0063 is a map
concept and would have needed the full four steps to add a synonym.

**2. `defined-term-use` read its vocabulary out of one entry.** The SRD prints a Rules Glossary,
so `vocabularyFrom` names the entry that lists its fifteen conditions. The FRCP prints no index:
*"Last Day"*, *"Next Day"*, *"Legal holiday"*, *"State Law"* are defined in the paragraphs the
rules using them sit beside. The mechanism now also reads `vocabulary`, the distributed form
[0045](../../docs/decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md)
already defined for `coded-pointer`, and `_check_defined_vocabulary` is the check that owns it.

### The independent reading, and where it dissents

0063 step 3 requires a second reading before a change is admitted. One was run, read-only against
a detached worktree pinned at `fa12e78`, by a reviewer from a different model family given no
earlier conclusions.

**On change 1 it agrees**: a repair, and forced.

**On change 2 it agrees the change is a repair and disputes that it was forced.** Its argument,
in its words: *"vocabularyFrom requires no special index-entry kind, and the old protocol permits
multiple declarations. A concrete alternative using three existing entries passed the old protocol
checker and every old map check … The change is convenient, not forced."* The alternative it
built and ran declares three `defined-term-use` mechanisms whose `vocabularyFrom` names
`include-last-day`, `jury-demand-not-required-by-state-law` and `responsive-pleading-time` — three
*rule* entries whose `crossReferences` happen to be term-anchored — and detects 16 namings against
the committed map's 10.

**The dissent is recorded and not accepted, and the reason is what `vocabularyFrom` asserts.**
The field names *"the one entry that lists this corpus's terms"* (`tools/mapper/protocol.py`,
`docs/mapper.md`). Rule 6(a)(1)(C) is a rule about counting days; it lists nothing. Declaring it
as this corpus's vocabulary entry asserts that the Federal Rules of Civil Procedure print an index
where they print none, which is 0063 step 2's test — *a sentence the map would have to assert that
is false about the corpus* — met exactly. Two further things weigh the same way: the alternative
requires editing three quoted `cites` strings to shorten them purely so the detector matches, which
is authoring a map to fit a tool; and a vocabulary read from an arbitrary rule entry's
`crossReferences` is anchored to nothing, so deleting one of those items would silently shrink the
vocabulary, where `defines` is anchored in each defining passage's own evidence (0045).

The reviewer's narrower correction is accepted and this document now reflects it: the claim is not
that the mechanism *could not be declared*, which is false — it could be declared untruthfully.
The claim is that **no truthful `vocabularyFrom` exists in this corpus**.

**Round 1 also found four defects in the trial's own changes, all by mutation, all repaired:**

- `Rule 6A(a)(1)(A)` resolved to `Rule 6`, because the lookahead after the rule number refused a
  digit and a dot and admitted a letter. A typo that resolves to a real passage is the one outcome
  a citation checker exists to prevent.
- `Rule 6(a), Rule 12(b)` had its second item's rule number discarded and resolved under Rule 6.
- `vocabularyFrom: []` beside a good `vocabulary` passed as a single-answer declaration, because
  the new rule judged which key held a usable value rather than which key was present.
- Widening the designation grammar let a table slice be declared against `Rule 6`, where 0035's
  table machinery is the eCFR's and no other adapter reads a table.

Each has the test its mutation earned. The review is what found them; nothing in the gate did.

### Findings recorded, and not decided

Filed, and post-1.0 under the release directive. None of them makes this map untrue.

- [#420](https://github.com/brandonifco/rules-factory/issues/420) — `applicability-reach` sees
  none of Rule 81's seven applicability rules. Its phrase list spells the CFR, *and* six of the
  seven gate a body of rules outside the slice, which the check has no way to record. Widening
  the phrase list alone would turn a silent skip into six failures with no truthful fix.
- [#421](https://github.com/brandonifco/rules-factory/issues/421) — the term detector is
  case-sensitive, and Rule 6(a)(6) prints *"Legal holiday"* at the head of a sentence while six
  rules use *"legal holiday"*. `last day` and `next day` escape only because their defining
  paragraphs happen to print a lower-case form too.
- [#422](https://github.com/brandonifco/rules-factory/issues/422) — Rule 81(d)(2) defines
  *"state"*, and the same slice uses that word as an ordinary verb four times. The map puts the
  term in a vocabulary no mechanism interrogates; the *reason* has no carrier but a `note`.
- [#423](https://github.com/brandonifco/rules-factory/issues/423) — `resolvedBy` holds one id, and
  this corpus points at whole rules. 16 of 89 `crossReferences` items exist only to enumerate a
  set, and nothing can tell a complete enumeration from a short one.
- [#424](https://github.com/brandonifco/rules-factory/issues/424) — `references` names a document
  and this slice defers eleven times to a *class*: *"any statute"*, *"a local rule"*, *"a court
  order"*, *"the state where the district court is located"*. Trial 9 met the same thing on
  `definedElsewhere`; two genres now.

Two more, smaller, recorded here rather than filed:

- **The USLM markup puts Rule 12(b)'s three flush sentences inside Rule 12(b)(7).** The three
  sentences that close Rule 12(b) — *"A motion asserting any of these defenses must be made before
  pleading…"* — are a `<p>` inside the seventh listed paragraph's `<content>`. Containment
  therefore places them at `Rule 12(b)(7)`, and the map cites them at `Rule 12(b)`, which is both
  what a lawyer writes and an ancestor the checker accepts. Trial 9 met the mirror image: the eCFR
  XML runs `(e)(1)` into `(e)`'s element.
- **The flattener puts a space before punctuation that follows an inline element.** `<date>Dec. 27,
  1946</date>, eff.` flattens to `Dec. 27, 1946 , eff.`. Every instance is inside a
  `<sourceCredit>`, which states no rule and which the inventory records as rejected; no operative
  sentence of the three rules is affected.

### What this trial does not establish

- **No blind second mapping.** Step 3 of the trial protocol was not run, so every verdict above
  rests on one mapper's reading plus the independent reading of the two forced changes.
  `review.json` names the five things a second reading should attack first.
- **Nothing was built from this map.** Trial 4 and the trial 9 build both found defects that only
  appear downstream — a missing gate invisible to every legality test among them — and this map
  has had no such pass.
- **The mutation run is one run.** 8 of 14 on one map is a measurement, not a rate.
