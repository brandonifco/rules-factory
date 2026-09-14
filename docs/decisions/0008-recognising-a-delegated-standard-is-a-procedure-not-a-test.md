# 0008 — Recognising a delegated standard is a procedure, not a test, and its residue is named

## Status

Accepted — 2026-09-14. Records a **failure**: there is no one-sentence test, the fourth and
fifth candidates were refuted by cross-application like the three before them, and the honest
landing is an ordered procedure whose last gate cannot fire on one shape of sentence. That shape
is named, and the entry sitting in it is named.

## Context

[0005](0005-a-field-earns-its-place-by-being-checkable.md)'s correction A — *a deliberately
delegated judgement is `kind: assertion`, and it is its own entry* — has now survived **five**
failed attempts to state the test that recognises one, without a single entry's `kind` turning
out wrong.

| # | test | refuted by |
|---|---|---|
| 1 | the corpus **names a decider** | "well clear" and "a flash rate sufficient" name nobody |
| 2 | a **standard of conduct** the subject must meet, versus a predicate vested in nobody | *"either thrice or four times (as may have been agreed)"* is neither |
| 3 | the missing fact has a **bearer** | 11 of 29 backgammon entries; 14 of 52 Part 107 entries |
| 4 | backgammon's four gates (G1–G4) | this record: 10 of 52 Part 107 entries on the reading most favourable to it, 30 of 52 on its own words |
| 5 | Part 107's two stages | this record: 3 of 29 backgammon entries, one of them the sole `kind: assertion` entry in that map |

Tests 1–3 are recorded in [#30](https://github.com/brandonifco/rules-factory/issues/30),
0005, and `corpus-map.md`'s `kind: assertion` section. Tests 4 and 5 are the successors proposed
by the two independent passes ordered by #30, written up in
`examples/hoyle-backgammon/ASSERTION-TEST.md` and `examples/faa-part-107/ASSERTION-TEST.md`.
Each was reported as agreeing with every entry in the corpus it was derived from. **That is the
property all of tests 1–3 had**, so agreement was worth nothing and #30 ordered the
cross-application this record carries out.

## The evidence

Every entry was re-derived from the corpus text at its `locator` — `hoyle.txt`,
`part107.xml`, and `part107-2020-01-01.xml` — not from either report's tables. Nothing below
rests on a map's own description of itself. Scoring is on what each test claims to decide:
**assertion, gap, or ordinary `value`/`operation`.** Silence where the entry is not an assertion
counts as agreement.

### Test 5 (Part 107's two stages) against the 29 backgammon entries

> **Stage 1.** Does applying the corpus's words require fixing a threshold, degree or value the
> corpus did not fix? If not, the entry is an ordinary `operation` or `value` with a
> caller-supplied input, and the input gets no entry of its own.
> **Stage 2, for a blank only.** To the answerable subject with the purpose stated at the
> locator → assertion. To named parties among values the corpus fixes → assertion. To nobody,
> no purpose and no fixed set → gap.

**23 agree, 3 disagree, 2 undecidable, 1 uncovered.**

| entry | test 5 says | entry says | |
|---|---|---|---|
| `agreed-backgammon-multiple` | **falls through all three branches of Stage 2** | assertion | **no** |
| `strategy-advice` | gap, `RequiresInterpretation` | `scope: out`, clear, declined | **no** |
| `inner-table-handedness` | ordinary value, caller-supplied input, no entry | `beyondAdapter`, declined | **no** |
| `game-value` | ordinary operation *or* gap, depending on the reading of "value" | gap, `fate: unresolved` | **undecidable** |
| `must-play-whole-throw` | ordinary operation *or* gap, same | gap, `fate: unresolved` | **undecidable** |
| `doubling-cube` | nothing — the corpus has no words to apply | `scope: out` | **uncovered** |
| the other 23 | agree | | yes |

**The disagreement that kills it is the first.** Stage 2's second branch requires *named*
parties. `hoyle.txt:8380-8381` reads "the loser pays {277} either thrice or four times **(as may
have been agreed)** the amount of the single stake" — an agentless passive, verified at the line,
naming who agrees exactly as much as § 107.37(a)'s "unless well clear" names who judges. Which is
what killed test 1. The third branch does not catch it either: it fires only where *both* no
purpose is stated **and** no set of values is fixed, and here the set {thrice, four times} is
fixed. So on the instance that motivated the whole correction, test 5 returns nothing at all —
or returns the right answer only if the mapper supplies the agent, which is test 1 one level in.

The two undecidable rows are the same defect in Stage 1's vocabulary. "Fixing a threshold, degree
or value" is written for an **undefined term**. `game-value`'s three named results do not cover a
reachable finish and `must-play-whole-throw` does not say which die is lost when only one is
playable; neither defect is an open degree, and whether Stage 1 sees them turns on how broadly
"value" is read. A test whose answer depends on which of two readings the mapper takes to a case
nobody has looked at is the failure mode #30 exists to avoid, and § 6.4 of
`examples/faa-part-107/ASSERTION-TEST.md` rejects the bearer test on precisely that ground.

`strategy-advice` and `inner-table-handedness` are gates test 5 does not have, not errors in what
it does have: normativity and scope, and *missing to whom*.

### Test 4 (backgammon's G1–G4) against the 52 Part 107 entries

> **G1** Is anything the rule needs actually unsupplied — a fact the rule requires that the
> engine cannot compute from what the corpus does supply?
> **G2** Unsupplied by the corpus, or only to us? → `beyondAdapter` / `definedElsewhere` /
> `scope: out` / conflict.
> **G3** Does the corpus site the choice at a step of the procedure it describes? → operation.
> **G4** Whose hands, and are they the caller's? → assertion / third party / gap.

Two counts, because G1's words and G1's evident intention are not the same test.

**On G1 as written: 30 disagreements of 52.** "A fact the rule requires, which the engine cannot
compute from what the corpus does supply" is satisfied by the groundspeed in § 107.51(a), the
airspace class in § 107.41, whether a visual observer was used in § 107.33 — by every runtime
input in the map. G2 clears `civil-twilight-alaska`, `hazardous-material` and
`subpart-d-categories`; G3 finds no choice sited at a step of a procedure, because a regulation
describes no procedure; and fifteen operations per map arrive at G4 and are called assertions.
Test 3 produced 14 disagreements. Test 4, read on its own words, produces 30.

**On the reading most favourable to it** — G1 restricted to facts the *rule's own terms* leave
open, which is Stage 1 of test 5 silently imported — **10 disagreements of 52, 5 per map.**

| entry (both maps) | test 4 says | entry says | |
|---|---|---|---|
| `moving-vehicle-operation` | assertion (G4, first branch) | gap, `ambiguous`, `fate: unresolved` | **no** |
| `visual-line-of-sight` | assertion | operation | **no** |
| `visual-observer-conditions` | assertion | operation | **no** |
| `preflight-actions` | assertion | operation | **no** |
| `weather-minimums-met` | assertion | operation, clear | **no** |

**`moving-vehicle-operation` is the named killer and test 4 does not survive it.** G4's first
branch is "a subject told a standard he is answerable for and the engine cannot check". § 107.25
is addressed to a person, that person may operate from a moving vehicle only if the area is
sparsely populated, and that person answers for it. G4 reaches the map's answer only by asserting
that "sparsely populated" is vested in nobody while "well clear" is vested in the operator — the
distinction test 2 was withdrawn for. **G4 dropped the purpose clause that was test 5's only
machinery here, and inherited test 3's failure with it.**

The other four are the same omission as test 3's third over-fire, and they matter for a second
reason: `visual-line-of-sight`, `visual-observer-conditions` and `preflight-actions` are the
three entries [#11](https://github.com/brandonifco/rules-factory/issues/11) is open over, and
0005 A rules explicitly that they are "facts-a-person-asserts, not delegated standards". Test 4
closes #11 in the affirmative as a side effect, six entry instances at a time. Whichever way #11
should go, a test that settles it by accident is not fit to adopt.

### Both tests against the constructed cases

Thirteen cases from tax code, contract, sports, chess, state statute and a metered fact, taken
from the two reports. **Both reports state that these are paraphrases from their authors'
knowledge of the instruments and are not in this repository; nothing here verifies the wording,
and the cases are used only to separate the two tests from each other.**

| case | test 4 | test 5 | a competent mapper |
|---|---|---|---|
| "best efforts to obtain the consent" | assertion ✓ | assertion ✓ | assertion |
| "at the referee's discretion" | assertion ✓ | assertion ✓ | assertion |
| "delivery dates as the parties may agree" (unbounded) | assertion ✓ | **gap ✗** | assertion |
| "players may agree any house rules" | assertion ✓ | **gap ✗** | assertion |
| "the Secretary shall by regulation prescribe" | third party, not a caller assertion ✓ | **gap ✗** | inoperative rule |
| § 162 "ordinary and necessary" | `definedElsewhere` ✓ (G2) | **gap ✗** | `definedElsewhere` |
| § 6664 "reasonable cause" | third party ✓ | gap — right behaviour, **wrong reason** | the Service determines |
| undefined "dangerous play" | **✗ unfalsifiable** | **gap ✗**, but for a stated textual reason | assertion |
| "as registered by the approved meter" | assertion ✓ | input, no entry ✓ | see below |
| OSHA general duty clause | assertion ✓ | assertion ✓ | assertion |
| force majeure "beyond the reasonable control" | gap ✓ | gap ✓ | gap |
| delivery date bounded, FIDE rate of play | assertion ✓ | assertion ✓ | assertion |
| "the rate established annually by the Commissioner" | `definedElsewhere` ✓ (G2) | **gap ✗** | `definedElsewhere` |

**12 of 13 for test 4; 6 of 13 for test 5.** The asymmetry is the result. Outside both corpora
the work is done by G2 (*missing to whom*) and by G4's third-party branch, which test 5 has
neither of. Inside Part 107 the work is done by Stage 1 and by Stage 2's purpose clause, which
test 4 has neither of.

`examples/faa-part-107/ASSERTION-TEST.md` § 6.4 claims Stage 1 disposes of the Commissioner case.
It does not: § 107.41 is disposed of by Stage 1 because *whether ATC authorized* is a fact the
rule tests, but *what the rate is* is a blank in the rule, so the case reaches Stage 2 and falls
out of it as a gap. That error was invisible until the case was run against the other test.

## Decision

### 1. There is no test. There is a procedure: a precondition and three gates, in order

Not a fourth sentence. Each gate is one of the two successors' contributions, kept because
cross-application showed the other test fails without it.

**Precondition, and it is not a gate.** The procedure applies only to an entry that is
`scope: in` and normative. `strategy-advice` — "A leading principle is to 'make points' whenever
you **fairly** can" (`hoyle.txt:8391`) — is an undefined degree addressed to the reader, and
tests 3, 4 and 5 all fire on it. Nothing is demanded of anybody, so there is nothing to be
answerable for. `doubling-cube` has no passage at all. 0005's correspondence table already
disposes of both at row 1, and that is where they are disposed of; the procedure is not asked to
re-derive it. **Stated as a limit rather than repaired: the procedure is not self-standing, and
#30 asked for one.**

**Gate 1 — a blank in the rule, or a fact the rule tests?** Does applying the corpus's words
require fixing a threshold, degree, value **or case** the corpus did not fix? If not, the entry is
an ordinary `value` or `operation`, and the fact is a caller-supplied parameter that **gets no
entry of its own**.

**"Or case" is added to test 5's wording, and the two instances that forced it are named.**
Stage 1 as proposed says "a threshold, degree or value", which is written for an *undefined term*
and is what made `game-value` and `must-play-whole-throw` undecidable in the cross-application
above. Neither is an open degree: `game-value`'s three named results do not cover a reachable
finish, and `must-play-whole-throw` does not say which die is lost when only one is playable. Both
are defective **enumerations**, both are recorded as gaps, and both are right. A gate whose answer
depends on how broadly a reader takes "value" is not a gate.

Otherwise this is test 5's Stage 1 and it is the clause both passes found independently — "the
engine cannot check it" and "a blank in the rule versus a fact the rule tests". It is what
silences the airspace class, whether a visual observer was used, whether the whole throw was
played, and every in-play election in the backgammon map. It also makes test 4's G3 redundant:
applying "may be played **either** wholly by moving men forward … **or** partly by the one method
and partly by the other, **as may be desirable**" (`hoyle.txt:8357-8359`) requires fixing
nothing, because the corpus states every branch; applying "either thrice or four times" requires
fixing the multiplier,
because the corpus states neither. Gate 1 draws that line from the sentence. G3 drew it by asking
whether the corpus "sites the choice at a step of its own procedure", which a regulation has none
of — G3 is dropped, and "if it needs *and*, it is two" is the reason.

**Gate 2 — unsupplied by the corpus, or only to us?** Readable but not by this adapter →
`beyondAdapter`. Fixed in a corpus that was not admitted → `definedElsewhere`. Supplied twice,
differently → a conflict under [0007](0007-a-conflict-is-a-question-not-a-pair.md).

This is test 4's G2. Test 5 has no such gate and loses `inner-table-handedness`, § 162 and the
Commissioner's rate to it — three of its seven constructed-case failures.

**Gate 3 — whose hands?** Of what survives:

- **The caller's own determination or agreement is operative**, and the corpus states, in the
  same constituent as the open term, **either what the term is measured against, or the set of
  values it may take** → `kind: assertion`, and it is an entry of its own under 0005 A. The
  disjunction is not decoration: the first arm is the delegated standard ("sufficient **to avoid a
  collision**") and the second is the delegated choice ("**either thrice or four times**"), which
  has no measure and must not need one. The bound survives into the signature where the corpus
  states one; parties need not be *named*, because Hoyle names none.
- **A third party whose determination is a separate act.** Not a caller assertion. Where that
  party's output is itself a corpus, this is `definedElsewhere` — row 3 of 0005's correspondence
  table, `MissingRulesData`. Where it is not, see § 3 below.
- **Nobody** → gap, `clarity: ambiguous`, `fate: unresolved`.

The purpose requirement in the first branch is test 5's, and it is the only thing either pass
produced that separates `well clear` from `sparsely populated area` — see § 2, where it is
attacked and does not hold. The *bounded-not-named* wording is test 4's, and it is what keeps
`agreed-backgammon-multiple` and the unbounded "as the parties may agree" on the same side.

**Gate 3 is checkable in 0005 rail E's sense.** An entry claiming `kind: assertion` must quote,
from its own `evidence`, either the words that state what the open term is measured against or the
words that fix the set of values it may take. An assertion entry that can quote neither is a gap.
That is a quotable obligation a reviewer can fail, which is the standard 0005 sets and the standard
tests 1–3 never met.

### 2. The purpose clause does not hold on § 107.37(a), and the line is not in the text

`examples/faa-part-107/ASSERTION-TEST.md` § 5 flagged this row of its own table as the weakest
and asked for it to be attacked. It does not survive.

The four uncontested assertions state the measure **inside the constituent that carries the open
term**, verified verbatim in `part107.xml`:

| open term | what fixes it, in the same constituent |
|---|---|
| "a flash rate **sufficient**" | "**to avoid a collision**" — an infinitival adjunct on *sufficient* |
| "**reasonable** protection" | "**from a falling small unmanned aircraft**" — the complement of *protection* |
| "**so close**" | "**as to create a collision hazard**" — a result clause fixing the degree |
| whether to reduce intensity | "**in the interest of safety**", decider named in the same clause |

§ 107.37(a) reads, in full and verbatim: *"Each small unmanned aircraft must yield the right of
way to all aircraft, airborne vehicles, and launch and reentry vehicles. Yielding the right of way
means that the small unmanned aircraft must give way to the aircraft or vehicle and may not pass
over, under, or ahead of it unless well clear."*

The proposed purpose was read off "must give way to the aircraft or vehicle". That is not a
purpose clause. The sentence is a **definition**, and "must give way" and "may not pass … unless
well clear" are two coordinate conjuncts of the definiens. "Give way" does not say what the
clearance is measured against; it states a second obligation, and "well clear" is the *exception*
to it, not its measure. Nothing anywhere fixes a margin. "Well clear" occurs exactly once in the
corpus, § 107.3 does not define it, and no other section does — all three checked against
`part107.xml`.

So gate 3's first branch does not fire on `well clear`, and it does not fire on "sparsely
populated area" either. **The procedure returns the same answer for both — gap — which is the
first time any formulation has been consistent about the two.** The map is not consistent about
them: `right-of-way` is `kind: assertion` and `moving-vehicle-operation` is a gap.

**Finding, and it is worth more than the test.** The line between § 107.37(a) and § 107.25(b) is
not derivable from the corpus. It was not derivable under test 1, test 2 or test 3; the two
successors were built to derive it and neither does. What separates them is that "well clear" is a
recognised operational standard in aviation practice which the regulator delegates to pilot
judgement — an institutional fact, in neither text. **A test whose answer turns on knowledge the
corpus does not contain is unfalsifiable from the corpus**, which is the ground 0005 rejected
`surprising: true` on.

### 3. The residue is named, and it is disposed of by machinery that already exists

**The residue:** *an open degree in the `unless` clause of a prohibition, with no measure stated
in its own constituent, no set of values fixed, and no third party named.* Gate 3's first branch
cannot fire on it, so the procedure returns a gap. Where the project believes the term is
nevertheless determinate — because practice outside the corpus fixes it — that belief is not a
`kind`. It is `clarity: ambiguous` with **`fate: decision`** and a record naming the reading, or
`definedElsewhere` if the practice is a corpus that can be admitted and cited. Both already exist;
both are checkable; neither lets a map claim to have derived from the text something it did not.

That is the Phase 4 question, asked where Phase 4 asks it, and it is the answer to *"then what
happens to `well clear`"*.

**No `kind` is changed by this record.** The procedure implies that `right-of-way`'s should move,
and the Part 107 pass argues separately that the entry should split. That is filed, not done —
see Consequences.

### 4. "The bearer is not the caller" is row 3 where the output is a corpus,
and otherwise out of scope

*"The Secretary shall by regulation prescribe"*; § 162 "ordinary and necessary"; § 6664
"reasonable cause"; force majeure's "beyond the reasonable control of the affected Party". Being
the party who will **claim** a standard was met is not being the party the instrument made
**answerable** for meeting it. 0005's correspondence table has no row that says so in terms, and
the regulation engine ([#3](https://github.com/brandonifco/rules-factory/issues/3)) meets the
family immediately.

**It is not a new `kind`.** `kind` is a property of what the entry's passage states — a fact, a
procedure, or a condition the caller supplies. *Whose determination is operative* is a property of
where the fact comes from, which is what `definedElsewhere` and `beyondAdapter` already carry.

**It is not a new row either, in the case that has an answer.** Where the third party's
determination is published — a regulation once made, a body of case law, a Commissioner's annual
order — it is a corpus that was not admitted, and that is **row 3, `definedElsewhere`,
`MissingRulesData`**. 0005 named this as "the nearest" and stopped; this record makes it the
ruling, because gate 2 reaches it mechanically and got § 162 and the Commissioner's rate right in
the cross-application, which is the only evidence either pass produced for it.

**What is left over is out of scope for this decision, and it is this:** where the determination
has not been made and is not a corpus — a regulation not yet prescribed, an arbitrator who has not
ruled — the rule is **inoperative**, and the map has no way to say so. It is not a gap (the corpus
did decide; it decided who would decide), not `definedElsewhere` (`reference` must resolve in the
manifest and there is nothing to name), and not an assertion (demanding it from the caller invites
an answer that is not theirs to give — the substitution of judgement that `never infer it` exists
to prevent, one level up).

**File it as: an inoperative rule has no carrier.** Zero instances in either mapped corpus; four
constructed cases, none of them verified against a source. Deciding a carrier from that is the
mistake 0004 avoided with `modality` and 0005 avoided with the second `ambiguity` citation, and
#3 is the case that will produce the instances.

## Alternatives considered

**Adopt test 4 (G1–G4).** Rejected on evidence: 30 disagreements of 52 Part 107 entries on its own
words, 10 on the reading most favourable to it, including `moving-vehicle-operation` — the entry
the exercise named as the killer — and six instances that close #11 as a side effect. It is the
better of the two outside both corpora (12 of 13) and that is why G2 and the third-party branch
survive into the procedure.

**Adopt test 5 (Stage 1 + Stage 2).** Rejected on evidence: it returns nothing on
`agreed-backgammon-multiple`, the sole `kind: assertion` entry in the backgammon map and the
instance 0005 A exists for, because Stage 2's "named parties" is test 1 restated and Hoyle names
none. 6 of 13 outside. Its Stage 1 survives into the procedure as gate 1, and is the single most
valuable thing either pass produced.

**A sixth one-sentence test.** Rejected. Five have now failed, three of them after surviving a
review, and the two most recent failed in *opposite* directions — test 4 too wide on Part 107,
test 5 too narrow on backgammon. The failures are not all of the same kind: separating *a
delegated standard from an undefined term* and separating *a blank in the rule from a fact the rule
tests* are two questions, and one sentence keeps answering one of them.

**Rule that `right-of-way` is an assertion by precedent and stop.** Rejected as the whole answer,
kept as the interim position. It is what the map does today and it is not derivable from the text;
leaving it undisturbed while claiming a test produces it is what made the maps wrong three times.
§ 3 gives it a carrier that says what it is resting on.

**Fold this into 0005 as a third amendment.** Rejected. 0005's ruling is that a delegated
judgement is an assertion and an entry; that ruling is untouched and has now survived five tests.
This record says something different — that recognising one is not a test — and burying a recorded
failure inside the decision it qualifies is how the qualification gets lost.

**A `surprising`-shaped flag for the residue** ("this term is fixed by practice"). Rejected on
0005 E's ground: unfalsifiable from the corpus. `fate: decision` with a record is the falsifiable
form of the same claim.

## Consequences

**`method.md` Phase 4 and `corpus-map.md`'s `kind: assertion` section are brought into line, in
the same change.** They disagreed with each other before, and 0005 records that the disagreement
is how the maps got wrong: a mapper following Phase 4 produced exactly what the maps contained.
Both now carry the procedure and both name the residue.

**Two `kind` questions this record implies and does not make.** Recorded here so they are filed
rather than done quietly:

- **`right-of-way`.** Under gate 3 its `well clear` clause is a gap, not an assertion. The Part
  107 pass argues separately, and on the corpus, that the entry should split — § 107.37(a)
  enumerates three protected classes and three prohibited relative positions, both computable, so
  the entry's note ("nothing here is computed") is contradicted by its own `evidence`. The two
  together give `right-of-way` (operation, retaining the enumerations) + `well-clear`, whose kind
  is the residue question in § 3. Two instances, one per map.
- **`weather-minimums-met`.** "Prominent" is undefined in Part 107, checked; it carries the whole
  visibility metric, and it sits inside a definition with no measure and no decider. Gate 3 returns
  a gap; the entry is `operation`, `clarity: clear`, in both maps. Two instances.

**Neither is changed here, and no map is touched by this record.**

**What this costs, stated where the claim is made.** The procedure is three gates and a
precondition where 0005 wanted one sentence; it needs the correspondence table's scope row applied
before it runs, so it is not self-standing; and its last gate has a named shape of sentence it
cannot decide. It agrees with all 29 backgammon entries, `agreed-backgammon-multiple` included,
and disagrees with **three Part 107 entries, six instances**: `right-of-way` and
`weather-minimums-met`, both listed below, and `night-operation`, where gate 2 routes the
undefined "night" to `definedElsewhere` against 14 CFR § 1.1 and the map records `clear` — which
is [#33](https://github.com/brandonifco/rules-factory/issues/33), already open, and the map is
wrong rather than the gate. Against test 3's 25 entries and test 4's 10. The argument for
it is not elegance and it is not that it never disagrees. It is that it is **the first formulation
that disagrees consistently**: § 107.37(a) and § 107.25(b) are the same sentence shape and it
returns the same answer for both, where every predecessor returned different answers for
sentences it could not tell apart.

**What this does not settle.** [#11](https://github.com/brandonifco/rules-factory/issues/11) stays
open, deliberately: gate 1 routes a caller-supplied fact to "no entry of its own", which is
`corpus-map.md`'s ruling on `airspace-authorized` and is in tension with the same document's "facts
about the physical world are consumed, not derived". That tension is #11 and it is a separate
argument, which is exactly what test 4 decided by accident. The residue in § 3 is unresolved by
construction. And nothing here reaches an entry whose author never noticed the term was open —
the same class 0004 and 0005 both stop at.

**The evidence base is two corpora, 81 entry instances and 13 unverified constructed cases.** The
constructed cases are the weakest part and they are where both tests differ most, which is an
argument for treating § 4's filing as provisional. #3 is the next thing likely to falsify this,
and it is being built next on purpose.
