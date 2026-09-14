# 0006 — The general rule governs entry, and "full" means adversely full

## Status

Accepted — 2026-09-14. Settles
[#19](https://github.com/brandonifco/rules-factory/issues/19), which
[0005](0005-a-field-earns-its-place-by-being-checkable.md) classified but deliberately did not
close.

## Context

Hoyle's backgammon states the rule for where a man may be played twice, three sentences
apart, and the two statements do not agree. Both are in `BACKGAMMON / Playing / p. 273`.

**The general rule names three cases** (`legal-destination`):

> The right to move is subject to a certain qualification--viz., that a man can only be played
> to a point which is either vacant, or occupied by one or more men of the player, or by one
> man only of the adversary.

**The entry sentence names two** (`enter-from-bar`):

> Nor can such man again start on its journey until its owner is fortunate enough to make a
> throw corresponding with a vacant point or blot in such table.

It omits exactly the case the general rule's second arm supplies: a point the entering
player's own men already hold.

**And "full" is stated by occupancy, not by adverse occupancy** (`full-table-suspension`):

> If the adverse player's home table is completely full--*i.e.*, each point occupied by two or
> more men, his play is altogether suspended, the adversary continuing to throw and move until
> the course of play again throws open one or more points in his table.

"Each point occupied by two or more men" is unqualified. Two of the *entering* player's own
men satisfy it.

**The two readings are each internally coherent**, which is what makes this a conflict rather
than a slip. Read strictly, `enter-from-bar` and `full-table-suspension` are exact negations
of one another: entry needs a vacant point or a blot, and "full" is precisely the absence of
both, whosever the men are. Read broadly, the general rule governs entry and "full" must mean
*adversely* full, or the two halves contradict each other. Both are consistent; the corpus
does not choose.

The engine chose, and chose silently. `Movement.MovesForDie` routes entry through
`IsPermittedDestination` (`AdversaryMen <= 1`), applying the general rule and overriding the
entry sentence; `Movement.IsWhollySuspended` tests `HasMadePoint(adversary, pip)`, narrowing
"full" to adverse men. Both entries were mapped `clarity: clear` with no `ambiguity` block, so
nothing in the map recorded that a choice had been made — the precise failure `ambiguity.fate`
exists to prevent.

## Decision

**The general rule governs entry, and "completely full" means full of the adversary's men.**

Both halves are the reading the engine already implements. What changes is that it is now
recorded, argued, and cited from the three entries it settles.

`legal-destination`, `enter-from-bar` and `full-table-suspension` each become
`clarity: ambiguous` with `ambiguity.fate: decision` naming **this record** — all three the
same record, which is `corpus-map.md`'s rule for a conflict settled by decision, and the only
thing that keeps one side of a conflict from being settled while the other is left open.

### Why the general rule governs entry

**1. The qualification is stated as governing all moving, and is never withdrawn.** "The right
to move is subject to a certain qualification" introduces a rule about the right to move as
such. Entry is a move — the corpus calls it starting the journey anew — so the qualification
reaches it unless something takes it back. The entry sentence does not take it back: it is not
phrased as an exception, a proviso, or a narrowing. It is a sentence about being *fortunate*,
describing what the thrower hopes for.

**2. The strict reading makes the corpus's own starting arrangement illegal to enter on.**
`starting-position` puts two of each player's men on the ace point in the adversary's inner
table — pip 24, which is exactly where a die of one enters. From the first move of every game
the corpus describes, each player holds a made point inside the table he would re-enter in.
Under the strict reading an ace could not enter there, and Hoyle never remarks on it. A rule
that forbade entry on the most familiar point on the board, from the opening position, would
not pass without a word.

**3. Hoyle's own recommended play would be self-harming, silently.** *Hints for Play* is
`scope: out` and non-normative — advice, not rules, and this argument is worth exactly what
that makes it. But it is the same author describing the same game, and he recommends making
points inside the adversary's inner table: "DOUBLE QUATRE.--Play two men from the ace to the
cinque point in the adversary's inner table"; "DEUCES.--... play the other two from the ace to
the trois point in your opponent's inner table." Under the strict reading each of those plays
destroys one of the player's own entry squares, and under the literal reading of "full" it
moves him toward suspending *himself*. He also writes that it is "sometimes even desirable to
be 'hit,' inasmuch as it enables you to make a fresh start from your adversary's home table" —
advice that assumes re-entry is ordinarily available, not that a good player has been closing
it off all game.

**4. The general rule is the one stated with care.** It is introduced, set off by "viz.", and
enumerates its three cases exhaustively. The entry sentence is an aside in the middle of the
paragraph about blots, summarising in passing. Where a corpus states a rule once carefully and
once in passing, the careful statement is the rule and the aside is shorthand for it. That is a
judgement about this text, not a canon of construction, and it is the weakest of the four.

### Why "full" means adversely full

**5. The sentence is about the adverse player's table.** "If the adverse player's home table is
completely full" describes a table by whose it is; the gloss "--i.e., each point occupied by
two or more men" answers *how many men make a point*, which is `made-point`, and not *whose
men*. Reading the gloss as silently admitting the entering player's own men makes the
possessive in the clause it glosses do no work.

**6. The stated remedy only describes adverse men leaving.** Suspension lasts "until the course
of play again throws open one or more points in his table" — the adversary's play opening his
own points. A point held by the *suspended* player's own men is not something his adversary's
throws can open; he could not open it either, since he may not move. Under the literal reading
the suspension it describes could be permanent, with the corpus's stated remedy inapplicable,
and the corpus would not have said "until".

**7. The two halves are one decision.** If the general rule governs entry, a point held by the
entering player's own men is a point he may enter on, so the table is not closed against him
and calling it "full" contradicts the reading just adopted. This is why one record governs all
three entries rather than two records governing two conflicts. It also means the halves cannot
be split: adopting the general rule for entry and the literal reading of "full" produces an
engine that lets a man enter on a point while holding that the table containing it is shut.

## Alternatives considered

**The strict reading: entry needs a vacant point or a blot, and "full" is the absence of
both.** The serious alternative, and it has one real merit the chosen reading does not — it is
the reading on which the two sentences are exact negations of one another, which is a kind of
evidence that the author wrote them as a pair. Rejected on arguments 2 and 3: it makes the
opening position's own made point unenterable and Hoyle's own recommended plays quietly
self-destructive, neither of which the corpus notices. It would also be the more conservative
choice in one respect worth naming: it takes the entry sentence at its word, and the chosen
reading does not.

**`fate: unresolved` — decline entry from the bar and let the caller settle it.** Rejected.
Entry from the bar is reached on most turns of most games; declining it declines the game. The
fate exists for a case no reading settles well enough to bake in, and here one reading is well
enough supported to bake in and say so. It would also be a strictly worse record than this one:
a caller handed the question gets no argument with it.

**Two decision records, one per conflict.** Rejected under argument 7 — they are not two
conflicts. Splitting them also re-creates exactly the hole `corpus-map.md` closes by requiring
one record across a conflict: two records can drift apart, and a reader of one would not learn
that the other half was decided the same way for the same reason.

**Leave the entries `clarity: clear` and record the reading in the code's remarks.** The status
quo, and rejected for the reason 0003 and 0004 both gave: prose no check can read is a
convention nobody can be shown to have broken. `Movement`'s remarks did already quote both
sentences; what they did not say is that the two disagree and that one was chosen.

## Consequences

**`Game.Play`'s `UnsupportedInteraction` branch is live code, and only reachable from an
asserted position.** This is what #19 said the decision decides, and it decides it in a shape
neither of #19's two answers anticipated.

Under the strict reading the both-suspended deadlock arises in ordinary play: enter one man
onto your own blot in the adversary's table, that point now holds two men, the table is
"full", and you still have a man up. Under this decision it cannot. A player's own move never
puts his own man on the bar; a move never adds *adversary* men to the adversary's home table;
and a player who is already suspended does not move at all. So no sequence of legal play
reaches a position where both players are suspended that did not start in one.

It is nonetheless reachable, because `Game.Play` demands an `AssertedPosition` and a caller
may assert one — a mid-game study, a replayed log, a position from another engine. Fifteen men
a side permits it: a man up and twelve men making all six points of one's own home table, for
each player. `DeterminismTests.Two_players_suspended_against_each_other_is_an_interaction_no_entry_covers`
constructs exactly that and reaches the branch. So the branch is not dead, and the honest
statement of what it is — unreachable by play under this decision, reachable by assertion — now
sits next to it in `Game.Play` instead of the bare "which fifteen men a side does permit" that
said neither half.

**It resolves the third bullet of [#13](https://github.com/brandonifco/rules-factory/issues/13)
from this decision rather than independently**, which is what #19 asked for. There is no map
entry for two players suspended at once because the corpus describes no such case, and under
this reading play never produces one. `UnsupportedInteraction` — row 7 of the correspondence
table, two implemented entries with no entry for their combination — is the right answer, and
it is an answer about what a caller may assert, not about what the rules generate.

**Three entries move from `clear` to `ambiguous`, and none of them becomes less implemented.**
`fate: decision` means the project ruled and implemented as though the corpus had said so, so
the runtime is unchanged and no row of the correspondence table fires for these three. What
changes is that a reader of the map can now see that a choice was made, follow it here, and
disagree with it.

**The decision is falsifiable and the map now says where.** Two tests make the reading
observable — one entering on a point the player's own men hold in the adversary's home table,
one against a home table whose six points are all occupied but one of them by the entering
player's own men, which suspends nobody. Under the strict reading both fail. Before this,
`EnterFromBarTests` and `FullTableSuspensionTests` both avoided the case, which is why the
choice was invisible: every test in the repository passed under either reading.

**What this does not settle.** The corpus is still self-contradictory and no decision makes it
otherwise. A reader who thinks argument 4 is the weak link is right that it is, and arguments 2
and 3 are what the decision actually rests on — both of which are inferences from what Hoyle
*did not* say, which is the weakest kind of textual evidence there is. It is better than a
silent choice by exactly the amount that being written down is worth.
