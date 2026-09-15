# 0007: An equivalent order is offered once, until the map says otherwise

**Status:** superseded by [decision 0008](0008-map-6-0-0-is-ruleset-version-four.md). Map 6.0.0 records both questions below as unresolved, and the engine now declines both cases. This recorded a gap in the map (finding 18). It did not settle a reading. Its behaviour returned in ruleset 5 as the owner's rulings of [decision 0009](0009-owner-rulings-are-ruleset-version-five.md), named on every play that relies on them.

## Context

`LegalPlays.For`, and so `EntryPoints.MustPlayWholeThrow` and `Game.Play`, offers two orders of
moves once when they reach the same position with the same numbers used. The first enumerated
order survives (the enumeration contract, rule 4). PR #11's end-to-end test found this with a man
up and six-trois: bar/22 22/16 is not offered because bar/19 19/16 reaches the same place.

Two questions follow. Does the corpus treat a play as the position it reaches, or as the ordered
moves? And does a move's `Authority` depend on the order, so that offering one order hides
provenance?

### Whether authorities differ between orders

**Sometimes.** In PR #11's example they do not: both orders are `enter-from-bar` then
`move-by-pip`. They do differ when a throw brings the last man home partway through. Take White's
last man outside on his eight point, and deuce ace thrown:

| Order | Moves | Authorities |
|---|---|---|
| offered | 8/6(2) 6/5(1) | `move-by-pip`, then `bearing-off-move-or-remove` (every man is home after 8/6) |
| pruned | 8/7(1) 7/5(2) | `move-by-pip`, `move-by-pip` (the man is still outside, on the seven point) |

Both orders leave the same position with the same numbers used.

### What the corpus says

- **BACKGAMMON / Playing / pp. 273-274** (`move-by-pip`): "he is entitled to move one man six
  points onward, and then the same or another man three points onward". The moves come in
  sequence, but this is a worked example of what each number entitles. It neither requires that
  order nor calls another order a different play.
- **p. 274** (`enter-from-bar`): "Until he does this, the play of his other men is suspended". One
  move's authority depends on the moves before it in the same throw. Nothing is said about two
  sequences with the same result.
- **p. 275** (`must-play-whole-throw`): "every player is compelled to play the whole of his throw if
  it is possible to do so", and "any part of a throw which cannot be played is lost". The unit is
  the part of a throw, a number. The rule is about which numbers are used, not their order.
- **BACKGAMMON / Bearing off the Men / pp. 275-276** (`bearing-off-eligible`,
  `bearing-off-move-or-remove`): "When the game has reached this stage, each throw entitles the
  player ...". The stage is described per *throw*. The worked quatre-trois example weighs each
  number against the same distribution (Fig. 2), never one after the other. The chapter never
  shows a throw whose regime changes partway through, and never says whether it can.

None of these says whether a play is the arrangement or the ordered moves. The last one leaves a
second question: whether a stage reached with the first number of a throw governs the second. If
it does not, the offered order above is two `move-by-pip` moves too. A play such as 9/3 3/off
would then not be legal at all.

## Decision

**The corpus does not settle it, so the engine keeps its behaviour and the gap goes to the map.**

- Equivalent orders stay offered once, in the first enumerated order, each move with that order's
  authority. `LegalPlays.For`'s remarks now say what rule 4 hides.
- Bearing off stays available as soon as every man is home, including partway through a throw.
- Neither alternative is adopted: offering every order, or keeping one order and recording that an
  equivalent one exists. Offering every order changes the list a recorded decision indexes into,
  which is a ruleset change, and would be made on a reading the corpus does not give. Recording the
  equivalent order would claim that the two orders are one play with two provenances, which is
  also a reading.
- `MAP-FINDINGS.md` finding 18 asks the map for both questions: whether a play is the arrangement
  or the ordered moves (on `must-play-whole-throw`, or a new entry for a throw taken whole), and
  whether bearing off begins within the throw that brings the last man home (on
  `bearing-off-eligible`'s question).
> [redacted by build-brief.py: test-name]

## Consequences

- No rule's answer changes, so the ruleset stays at version 3 and the replay bytes of
  decision 0006 do not move.
- A reader of a `Play`, or of a recorded game's moves (whose serialisation writes each move's
  `authority`), sees the authorities of the order the engine enumerated. The same position may be
  reachable in an order with different authorities.
- When a map version answers finding 18, the engine follows it. If that changes the plays offered,
  or which moves are legal, it is a new ruleset version with its own record.
