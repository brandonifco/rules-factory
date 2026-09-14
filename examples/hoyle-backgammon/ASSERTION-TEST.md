# The bearer test, applied to all 29 entries of the backgammon map

Exercise ordered by [#30](https://github.com/brandonifco/rules-factory/issues/30). The candidate
under test, as stated there and in `docs/corpus-map.md`'s `kind: assertion` section:

> **The corpus puts the missing fact in somebody's hands — it has a *bearer*.** Either the
> subject, by telling them a standard to meet and holding them answerable for having met it
> (arm a); or named parties, by fixing a set of permitted values and vesting the choice between
> them (arm b). A gap has no bearer: only a word the corpus uses and never defines.

Entries examined: **29 of 29.** Every quotation below was checked against
`examples/hoyle-backgammon/hoyle.txt` at the line given.

## Verdict: **fails**

Three independent reasons, in descending order of how hard they are to argue with.

**1. It fails on its own motivating case, on the text, for the same reason the first test did.**
Arm (b) requires *named* parties. Hoyle names none. The sentence is
`hoyle.txt:8380-8381`:

> "the loser pays {277} either thrice or four times (as may have been agreed) the amount of the
> single stake."

*As may have been agreed* is an agentless passive. It no more names who agrees than
§ 107.37's "unless well clear" names who judges — which is precisely what killed test 1. The
same page does it twice: "pays double **the agreed stake**" (`hoyle.txt:8376`) is also
agentless. That the agreeing parties are the two players is an inference from context, and a
safe one, but it is the mapper's inference and not the corpus's words. `agreed-backgammon-multiple`'s
own note asserts the corpus "vests the choice between them in the players, by agreement";
`corpus-map.md:112` says it "hands to named parties by agreement". Neither is what the sentence
says.

So arm (b) has two horns and both are fatal. Require naming, and the motivating instance fails
the test — test 1's error, one level in. Drop the naming requirement, and arm (b) reduces to
"the corpus fixes a set of values and somebody picks one", which is reason 2.

**2. Arm (b) is satisfied by every choice rule in the game, and by one sentence of nearly
identical grammar four pages away.** Six `kind: operation` entries state a fixed set of options
exercised by an identified party. The closest is `bearing-off-doublets` (`hoyle.txt:8357-8359`):

> "may be played **either** wholly by moving men forward, wholly by bearing off, or partly by the
> one method and partly by the other, **as may be desirable**."

against `agreed-backgammon-multiple`:

> "**either** thrice or four times (**as may have been agreed**)"

*Either X or Y … as may be Z*, in both. One is ruled an assertion, the other an operation, both
rulings are right, and the candidate cannot see any difference between them. It therefore does
not classify the motivating case correctly — it merely fails to classify it wrong, which is the
suspicion #30 raised about that entry and the answer is that the suspicion was justified.

**3. Arm (a) is satisfied by every duty-imposing sentence, because it has no uncheckability
requirement.** "Every player is compelled to play the whole of his throw if it is possible to do
so" (`hoyle.txt:8332-8334`) tells the subject a standard and holds him answerable for having met
it — arm (a) verbatim. It is not a delegation; it is a compulsion the engine computes.
`LegalPlays.For` decides whether it was met. What makes "well clear" an assertion is not that it
is a standard addressed to the subject but that **the engine cannot check whether it was met.**
The candidate omits that, and so swallows the rulebook.

The strongest case I could not break it with: a contract's **"best efforts"**, and a sports
rulebook's **"at the referee's discretion"**. Where the bearer is the subject, the subject is the
engine's caller, and the standard is uncheckable from the facts the engine holds, the candidate
is right and cheap. That is a narrow band, and it is the band both arms were fitted from.

## What the candidate is missing

It is a test with three unstated preconditions. Stated, they are gates, and the bearer idea
survives only as the last of them — narrowed. Section "A better test" below.

## The disagreement table

`—` in the *candidate* column means the candidate is silent because nothing the rule needs is
unsupplied. "Silent" is scored as agreement where the entry is not an assertion.

| # | entry | the corpus's words at the locator | candidate says | entry says | ? |
|---|---|---|---|---|---|
| 1 | `player-count` | "played by two persons" | — | value | agree |
| 2 | `men-count` | "fifteen white and fifteen black **(or red)**" | gap (set fixed, nobody named) | value / clear | **no** |
| 3 | `board-tables` | "known as 'tables' … 'outer' … 'inner' or 'home'" | — | value | agree |
| 4 | `point-designations` | "alternately of black and white, black and red, **or other distinctive colours**" | gap (unbounded set, nobody named) | value / clear | **no** |
| 5 | `inner-table-handedness` | "With the men placed as in Fig. 1, the right hand is the inner or home table" | gap | `beyondAdapter`, declined | **no** |
| 6 | `starting-position` | "two of White's men are placed on the ace point…" | — | value | agree |
| 7 | `opening-roll` | "the higher throw of the two giving the right to begin" | — | operation | agree |
| 8 | `opening-thrower-option` | "may **either** adopt the points shown by the two dice as his own throw, **or** throw again" | assertion (arm b) | operation | **no** |
| 9 | `throw-two-dice` | "All subsequent throws are with both dice." | — | operation | agree |
| 10 | `move-by-pip` | "move **one man** forward … then **the same or another man** three points onward" | assertion (arm b) | operation | **no** |
| 11 | `direction-of-travel` | "from the ace point in his opponent's home table towards the like point in his own" | — | operation | agree |
| 12 | `doublets` | "he may move **one or more men** forward to an aggregate extent of four points" | assertion (arm b) | operation | **no** |
| 13 | `legal-destination` | "a point which is either vacant or occupied by one or more men of the player, or by one man only of the adversary" | assertion (arm b: the mover picks the point) | operation, conflict, `fate: decision` | **no** |
| 14 | `made-point` | "A player getting two men on a given point is said to 'make' such point" | — | value | agree |
| 15 | `blot-hit` | "'taken up' (placed on the bar between the two tables)" | — | operation | agree |
| 16 | `enter-from-bar` | "a throw corresponding with a vacant point or blot in such table" | gap — *by a false reason* | operation, conflict | agree (wrong reason) |
| 17 | `full-table-suspension` | "completely full—_i.e._, each point occupied by two or more men" | gap — *by a false reason* | operation, conflict | agree (wrong reason) |
| 18 | `must-play-whole-throw` | "every player is **compelled** to play the whole of his throw if it is possible to do so" | assertion (arm a) | operation, gap, `fate: unresolved` | **no** |
| 19 | `bearing-off-eligible` | "all his men into his home table, he proceeds to 'bear them off'" | — | operation | agree |
| 20 | `bearing-off-move-or-remove` | "entitles the player **either** to move forward a man or men … **or** to remove men" | assertion (arm b) | operation | **no** |
| 21 | `bearing-off-highest` | "entitled to bear off a man from his highest occupied point" | — | operation | agree |
| 22 | `bearing-off-doublets` | "**either** wholly by moving men forward, wholly by bearing off, or partly by … , **as may be desirable**" | assertion (arm b) | operation | **no** |
| 23 | `win-condition` | "The player who first succeeds in removing all his men from the board wins the game" | — | operation | agree |
| 24 | `game-value` | "a 'hit' … a 'gammon' … a 'backgammon'" | **gap** | gap, `fate: unresolved` | **agree — substantively** |
| 25 | `agreed-backgammon-multiple` | "either thrice or four times (as may have been agreed)" | assertion (arm b) — or gap, if arm b's "named" is enforced | assertion | agree **vacuously** (see reasons 1–2) |
| 26 | `stake-multiplier` | "pays double the agreed stake" / "thrice or four times … the single stake" — **never states what a hit pays** | gap | value / clear | **no** |
| 27 | `next-game-opening` | "the winner of a 'hit' throws first in the game next following" | — | operation | agree |
| 28 | `doubling-cube` | *(absent — no passage)* | gap | `scope: out`, clear | **no** |
| 29 | `strategy-advice` | "make points whenever you **fairly** can" | assertion (arm a) | `scope: out`, declined | **no** |

**Score: 11 disagreements, 2 right-verdict-wrong-reason, 1 vacuous agreement, 1 substantive
agreement, 14 silent.** In every one of the 11 the map is right and the candidate is wrong.

## The disagreements that matter

### `opening-thrower-option`, `bearing-off-doublets` and the other four choice rules

These are reason 2 above, and they are the finding. Six entries nobody has questioned state a
closed set of options exercised by an identified party. `bearing-off-move-or-remove`:
"each throw entitles the player either to move forward a man or men … or to remove men"
(`hoyle.txt:8342-8344`). `opening-thrower-option`: "may either adopt the points shown by the two
dice as his own throw, or throw again" (`hoyle.txt:8293-8294`). Under arm (b) each is a bounded
set in a party's hands, and each is therefore an assertion the engine must demand before it can
proceed. That is wrong six times over, and it is wrong in the direction that matters: turning a
move into a required input makes the engine unable to play the game.

What would have to be true for the candidate to be right about them? That an in-play election
and a pre-play agreement are the same kind of missing fact. They are not, and the difference is
visible without leaving the text: **the corpus sites the election at a step of the procedure it
describes and sites the agreement nowhere.** There is no throw, no turn and no position at which
the multiple is agreed. An engine can reach every move choice from a state and offer the set; it
can reach the agreement from no state at all. That distinction does real work and the candidate
does not contain it.

### `must-play-whole-throw` — gap, and the candidate says delegation

Arm (a) fires cleanly: the player is told a standard ("play the whole of your throw if it is
possible") and is answerable for having met it. The entry records a gap. **The entry is right.**
For the candidate to be right, the corpus would have to leave the meeting of the standard
uncheckable — and it does not: whether a play used the whole throw is decidable from the
position, which is exactly why the rule is implemented and declines only the case where two
maximal plays are incomparable. Nor does the corpus delegate the tie-break: it says the
unplayable part "is lost to the thrower" (`hoyle.txt:8332`) and says nothing about who picks
which part. Reading silence as "then the player may choose" is the inference from silence that
`RequiresInterpretation` exists to prevent.

Verified, because the entry rests on it: the text contains no rule for playing the higher number
and no rule for choosing between dice. The only sentences on the subject are the two quoted.

### `game-value` — the one place the candidate does substantive work, and its reason is still false

Candidate and entry agree: gap. Nobody is named, no set is fixed, no standard of conduct is
stated, so the uncovered finish is vested in nobody. That is the right answer for the right
reason at the top level.

But the candidate's *characterisation* of a gap — "only a word the corpus uses and never
defines" — is false of this instance. Every word in the three definitions is defined. What is
defective is the **enumeration**: three named results that do not cover a reachable finish. Two
distinct gap shapes exist, undefined-term and incomplete-enumeration, and the candidate's
negative arm describes only the first, which is the one Part 107 supplied. Same defect on the
three conflict entries (13, 16, 17): the corpus there defines everything and says it twice
differently. The candidate returns "not an assertion" for all four by default, not by its
reason.

### `strategy-advice` and `doubling-cube` — the candidate has no scope gate, and should

The candidate applies to both, and gets both wrong.

`strategy-advice` quotes "A leading principle is to 'make points' whenever you **fairly** can"
(`hoyle.txt:8391`). *Fairly* is an undefined standard of conduct addressed to the subject — the
exact grammatical shape of "well clear". Arm (a) fires and nominates an out-of-scope entry as an
assertion. The only thing that stops it being one is that the sentence is advice: nothing is
demanded of anybody, so there is nothing to be answerable for. The candidate has no normativity
gate, and the corpus makes this non-theoretical — `made-point`'s own paragraph contains "it is
always an object to do this" (`hoyle.txt:8318`), advice inside a normative section, which the map
drops by hand.

`doubling-cube` has no passage at all. A rule wholly absent is the limiting case of "a fact the
corpus never supplies and vests in nobody", so the candidate calls it a gap — `clarity:
ambiguous`, `RequiresInterpretation`. That is the outcome `method.md` and 0002 exist to prevent:
a 1909 corpus has no doubling cube and an engine built from it is a 1909 engine, which is a
correct outcome and not an incomplete one.

Should the candidate apply to an out-of-scope entry? **No**, and it says nothing about that.
0005's correspondence table saves it operationally, because `scope: out` is row 1 and
`fate: unresolved` is row 6 — but a recognition test that needs the precedence table applied
first is not the self-standing test #30 asked for.

### `inner-table-handedness` — missing to us, not to the corpus

"With the men placed as in Fig. 1, the right hand is the inner or home table"
(`hoyle.txt:8260-8261`). The corpus determines the fact completely; our adapter cannot read the
figure that determines it. No bearer, so the candidate says gap. The right answer is
`beyondAdapter` → `MissingRulesData`, which is what the entry records. Same structural failure
as `doubling-cube`: the candidate never asks *whom* the fact is missing from.

### Two minor over-fires worth recording rather than fixing

- **`men-count` / `point-designations`.** "fifteen black **(or red)**" (`hoyle.txt:8248`) and
  "black and white, black and red, **or other distinctive colours**" (`hoyle.txt:8265-8266`) are
  sets of permitted values with no chooser named — the second unbounded. The candidate calls
  each a gap. They are not rules at all, and `point-designations`'s note already says so. The
  candidate has no materiality gate; the map applies one by hand.
- **`stake-multiplier`.** The quoted span states what a gammon and a backgammon pay and
  **never states what a hit pays**; the entry's own note concedes this is "an inference, not a
  sentence". The candidate calls it a gap. I would not change `kind`, and I would not change
  `clarity` on my own reading — but under `clarity`'s stated meaning ("the corpus determines
  exactly one answer for every valid input") a multiple supplied only by necessary implication is
  a live question, and it is the same shape as the `game-value` violation 0005 names. **Filed
  here rather than fixed**, as the only candidate finding this exercise produced that is not
  about the test.

## Half 2 — the test attacked from outside these two corpora

The candidate was derived from the two corpora that produced the two failed tests. These are the
cases that were not available to it.

| # | case | candidate's answer | what a competent mapper gives | ? |
|---|---|---|---|---|
| 1 | Contract: "Seller shall use **best efforts** to obtain the consent." | assertion (arm a) | assertion | ✓ |
| 2 | Sports: "**at the referee's discretion**, play may be restarted." | assertion (arm b: named bearer) | assertion | ✓ |
| 3 | Contract: "delivery dates **as the parties may agree**." | **gap** — arm (b) requires a *fixed set* and none is fixed | assertion; the paradigm delegation | ✗ |
| 4 | Boardgame: "players may agree **any house rules** before play." | **gap**, same reason | assertion, or an explicit variant mechanism | ✗ |
| 5 | Statute: "The Secretary **shall by regulation prescribe** the applicable rate." (regulation not yet made) | assertion — bearer named, squarely vested | **not** an assertion: the rule is inoperative. Demanding the rate from a caller invites a value nobody prescribed | ✗ |
| 6 | Tax: an expense must be "**ordinary and necessary**" (IRC § 162). | assertion (arm a) | `definedElsewhere` — a century of case law fixes it, in a corpus not admitted | ✗ |
| 7 | Tax: penalty abated for "**reasonable cause**" (§ 6664). | assertion (arm a) | not a caller assertion: the *determination* is the Service's. Demanding it lets the taxpayer self-certify relief | ✗ |
| 8 | Sports: undefined "**dangerous play**" shall be penalised. | assertion if the code mentions a referee; gap if it does not | assertion — every code refers it to the official, whether or not that clause says so | ✗ (unfalsifiable) |
| 9 | Metering: "quantity billed shall be **as registered by the approved meter**." | **gap** — a machine is not "somebody" | assertion: a fact about the world the engine consumes | ✗ |

Six wrong answers out of nine, and they fall into three families.

**Family A — arm (b) was fitted to a two-element set (cases 3, 4).** The motivating instance
happened to bound the choice; the candidate wrote the bound into the test. Remove the bound and
keep everything else, and the candidate reports a *gap* in a clause that is the clearest
delegation in the list. This is the cleanest kill: it is the motivating case with one incidental
feature deleted.

**Family B — the candidate never asks whether the bearer is the engine's caller (cases 5, 6,
7).** "Well clear" works because bearer = subject = caller: the operator's own in-the-moment
judgement is the operative fact, and an engine that demands it and records who asserted it has
done the honest thing. Where the corpus vests the fact in a **third party whose determination is
a separate act** — a Secretary who has not yet prescribed, a court construing § 162, a revenue
service finding reasonable cause — "demand it from the caller and proceed" is the same
substitution of judgement that `never infer it` exists to prevent, one level up: the caller is
invited to supply an answer that is not theirs to give. 0005 has no row for this. The nearest is
`definedElsewhere` where the third party's output is itself a corpus (case 6, and case 5 once
the regulation exists); case 5 before the regulation exists has no carrier at all, and naming
one would be its own decision, not a clause bolted on here. **This is the family the regulation
engine ([#3](https://github.com/brandonifco/rules-factory/issues/3)) hits on day one**, and it
is the reason I would not ship the candidate even amended.

**Family C — "bearer" smuggles in extratextual knowledge (cases 8, 9).** Case 9 is cheap to
fix: widen "somebody" to "some determiner", and note that `corpus-map.md` already covers it
under a *different* limb — "facts about the physical world are consumed, not derived" — which
is itself evidence that the bearer test is not the test for `kind: assertion` but at most the
test for one of its two sources. 0005's A says as much when it declines to close
[#11](https://github.com/brandonifco/rules-factory/issues/11).

Case 8 is not cheap. "Dangerous play" and "sparsely populated area" are the same sentence shape:
an undefined predicate in a condition, defined nowhere, addressed to nobody in particular. Every
reader's intuition is that the first is refereed and the second is a gap — and the thing that
differs is **not in either text**. Football has an on-field adjudicator; Part 107 has no
on-scene adjudicator of population density. The candidate reports that difference as "has a
bearer", which makes an institutional fact sound like a textual one. A test whose answer turns
on knowledge the corpus does not contain is unfalsifiable from the corpus, which is the ground
0005 rejected `surprising: true` on.

Note also that 0005 already files this residual as unsettled — "a world fact an operator could
perfectly well assert sits close to a gap". The candidate does not touch it, and the residual is
load-bearing for `moving-vehicle-operation`, the one entry 0005 rules on explicitly to stop a
migrator getting it wrong.

## A better test

Not one question. The bearer idea survives as the last of four, narrowed, and each earlier gate
is one the candidate silently assumed.

**G1 — Is anything the rule needs actually unsupplied?** A fact the rule requires, which the
engine cannot compute from what the corpus does supply. Silences the men's colours, the
fourteen fully-stated entries, and `stake-multiplier`'s implied single stake. *(Kills the
`must-play-whole-throw` over-fire too, in its second form: a standard the engine can check is
not a missing fact.)*

**G2 — Unsupplied by the corpus, or only to us?** Readable but not by this adapter →
`beyondAdapter`. Fixed in a corpus we did not admit → `definedElsewhere`. Wholly absent →
`scope: out`. Supplied twice, differently → conflict. Silences `inner-table-handedness`,
`doubling-cube`, and entries 13/16/17; catches outside case 6.

**G3 — Does the corpus site the choice at a step of the procedure it describes?** If yes, the
engine *offers* it: the caller picks from a set the engine computes from the state, and the
entry is an operation. Silences all six move-choice entries and "as may be desirable" — the
whole of reason 2.

**G4 — Of what survives: whose hands, and are they the caller's?** What reaches here is a fact
the engine must demand before it can compute anything.
- The corpus makes **the caller's own determination or agreement operative** — a subject told a
  standard he is answerable for and the engine cannot check, or parties handed the choice,
  bounded or not → **`kind: assertion`**.
- The corpus vests it in a **third party whose determination is a separate act** → not a caller
  assertion. `MissingRulesData` where that party's output is a corpus; otherwise the rule is
  inoperative and the map needs vocabulary it does not have.
- Vested in **nobody** → gap, `clarity: ambiguous`, `fate: unresolved`.

Applied to the 29: only `agreed-backgammon-multiple` reaches G4 and is an assertion — and it
reaches it without needing parties to be *named*, which is what makes G4 survive finding 1.
`game-value` reaches G4 and is vested in nobody → gap. `must-play-whole-throw` reaches G4 (the
tie-break is genuinely unsupplied and uncomputable) and is vested in nobody → gap. All three
match the map. The other 26 are silenced at G1–G3, all matching the map. **Zero disagreements
across 29.**

Applied to the outside cases: 1 ✓, 2 ✓, 3 ✓ (bound dropped), 4 ✓, 5 ✓ (third-party branch), 6 ✓
(G2), 7 ✓ (third-party branch), 9 ✓ (G4 "determiner"). **Case 8 still fails**, and G4 fails it
*visibly* — it forces the mapper to say who the third party is, and for "dangerous play" the
answer is not in the clause. That is progress from hiding the problem inside the word "bearer",
not a cure.

**What G1–G4 costs, stated where the claim is made.** It is four questions where 0005 wanted
one, and G4's middle branch names a runtime outcome the schema cannot carry. Neither is a reason
to keep a one-line test that is wrong eleven times in this map. But G4's middle branch is a
decision, not a clause: it should not be adopted by being written down here.

## Entries whose `kind` should change

**None.** All 29 `kind` values as recorded survive both the candidate and G1–G4. The candidate
disagrees with eleven of them and the map is right in every case.

One finding filed rather than fixed, and it is not about `kind`: **`stake-multiplier`'s
`clarity: clear`** rests on a multiple the quoted span never states. Its own note records the
inference honestly, which is why this is a question and not a defect — but it is the same shape
as the `game-value` violation 0005 named, and it should be decided rather than left in the note.

One pre-existing observation, already recorded in `doubling-cube`'s own note and repeated here
only because it bears on any count drawn from this map: `check-locators.py` skips the entry whose
citation names no page and still counts it, so its "all 29 checked" line verifies 28 citations.
That is a "check that proves nothing says so" case and it is already stated where the claim is.

## Confirmations for the record

- Entries examined: **29 of 29**, not the interesting ones.
- Every corpus quotation above was located in `hoyle.txt` and is reproduced verbatim, with the
  line number given for the load-bearing ones.
- Nothing in this file asserts a fact about Hoyle that was not read at the locator. The claims
  most likely to be wrong — that "as may have been agreed" names nobody, that the text contains
  no tie-break rule for a half-playable throw, and that the span behind `stake-multiplier` never
  states what a hit pays — were each checked by reading the surrounding paragraphs, not by
  searching for the phrase.
