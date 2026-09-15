# 0008: Map 6.0.0 is ruleset version four

**Status:** accepted. Supersedes [decision 0007](0007-an-equivalent-order-is-offered-once-until-the-map-says-otherwise.md). Superseded in part by [decision 0009](0009-owner-rulings-are-ruleset-version-five.md): Brandon ruled on 2026-09-15 on the second parts of both questions below, and the engine no longer declines them (ruleset 5). The first parts still decline.

## Context

[Decision 0007](0007-an-equivalent-order-is-offered-once-until-the-map-says-otherwise.md) kept two
behaviours the corpus does not settle and sent the gap to the map as finding 18 in
`MAP-FINDINGS.md`:

- `LegalPlays.For` offered two orders of a throw once when they reach the same position with the
  same numbers used, in the first enumerated order and with that order's authorities;
- bearing off began as soon as every man was home, including partway through a throw.

`RulesFactory.Maps.HoyleBackgammon` 6.0.0 (rules-factory#125, PR #127) answers the finding. It
settles neither question. It records both, each as a second part of an existing entry's
`ambiguity.question`, with `fate: unresolved` and `unresolvedReason: RequiresInterpretation`:

- **`must-play-whole-throw`** (BACKGAMMON / Playing / p. 275): where two orders use the same numbers
  and reach the same position, the text does not say whether they are one play or two. That matters
  where the rule that permits a move differs between the orders. The map's example: with the last
  man outside on the eight point and deuce-ace thrown, 8/6 6/5 plays the ace after every man is
  home, and 8/7 7/5 does not.
- **`bearing-off-eligible`** (BACKGAMMON / Bearing off the Men / p. 275): if a man played with the
  first number of a throw is the last to come home, the text does not say whether the number left is
  played under the bearing-off stage or as an ordinary move. The map's example: last man on the nine
  point, six-trois thrown; 9/3 then off with the trois, or 9/6 then off with the six, is legal on
  the first reading and neither is on the second.

`move-by-pip` and `bearing-off-move-or-remove` changed only their notes, which now point at those
two questions. No `clarity`, `fate`, `evidence` or edge changed.

Both of the engine's behaviours above adopt one reading of a question the map now marks open.

## Decision

**The engine declines both cases, and the ruleset is `hoyle-1909-backgammon` version 4.**

`LegalPlays.For` (and so `EntryPoints.MustPlayWholeThrow` and `Game.Play`) returns
`RequiresInterpretation` in two new cases. Both are decided after the re-entry decline of map 3.0.0
and before any question of which plays are compelled, over every line the search explores, as the
re-entry decline is:

1. **Orders under different rules.** The memo that prunes an order reaching a state an earlier order
   reached (the enumeration contract, rule 4) now keeps, for each state, the multiset of authorities
   of the moves that reached it. If a later order reaches the state with a different multiset, the
   throw declines, citing `must-play-whole-throw`.
2. **A number left after the last man comes home.** If the player was not eligible to bear off at
   the start of the throw, and a line makes him eligible with a number still to play, the throw
   declines, citing `bearing-off-eligible`.

Where both hold, as in the deuce-ace example, the first is reported: the orders' authorities differ
only because the second question is open, and whether they are one play is what the list of plays
itself depends on.

What "a move is permitted by a different rule" means is read as the *multiset* of the moves'
authorities, not the authority of each number. So bar/22 22/16 and bar/19 19/16 (a man up,
six-trois), each an entry and a move-by-pip, are still offered once. In the first the trois enters;
in the second the six does. Both orders use the same rules, once each, and the first move of each is
an entry. The map's note on `move-by-pip` does say that with a man up "the rule that permits a move
depends on the moves before it in the same throw", but the example its open question gives is the
bearing-off one, where one order uses a rule the other never does. This is a reading of the
question's scope, and the narrower one: a per-number comparison would decline nearly every throw
that enters one man and plays on. If a later map version says the entry case is also one play or
two, this is the comparison to change.

- **`implementedIn` moves to 4 on every implemented entry**, for the reason 0004 gives.
- **The replay schema stays at 2.** The shape of a `GameRecord` and its canonical serialisation
  (0006) do not change; only which games finish does. The corpus baseline and the generator do not
  change.
- Neither alternative that 0007 rejected is adopted: offering every order, or recording that an
  equivalent order exists. Each is still a reading.

## Consequences

> [redacted by build-brief.py: test-literal]
> [redacted by build-brief.py: test-literal, test-name]
> [redacted by build-brief.py: test-name]
> [redacted by build-brief.py: test-name]
- `BearingOff.IsEligible`, and the `bearing-off-eligible` entry point that answers it, remain a
  predicate on a position. The new question is about a throw, and a position alone never raises it.
- Finding 18 is accepted. When a map version settles either question, the engine follows it, and if
  that changes what a rule returns it is a new ruleset version with its own record.
