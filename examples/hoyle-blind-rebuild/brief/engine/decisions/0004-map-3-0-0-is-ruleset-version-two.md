# 0004: Map 3.0.0 is ruleset version two

**Status:** accepted.

## Context

> [redacted by build-brief.py: test-name]

Consuming `RulesFactory.Maps.HoyleBackgammon` 3.0.0 changed what the rules return. The row
numbers below are rows of rules-factory
`examples/hoyle-backgammon/blind-mapping/resolutions.json`.

- `LegalPlays.For` declines a throw once a player who has begun to bear off has a hit man
  re-entered and men still at home. Rows 12 and 13 made `bearing-off-eligible` unresolved.
- `Outcome.ValueOf` declines a loser with a man up who has borne off nothing, where it used to
  return a backgammon. Row 52 put that overlap into `game-value`'s question.
- `Outcome.RubberWinner` is new. Rows 114 and 115 added `rubber-scoring`.

A game recorded under the earlier rules can pass through either declined case. Replayed now
with the same seed and the same decisions, it stops with `RequiresInterpretation` where it used
to finish. Nothing in the record says so. Under the old identity it would still claim to be
comparable with games played today, and it is not.

## Decision

**The ruleset is `hoyle-1909-backgammon` version 2.** Version 1 covers every build up to and
including the `hand-built-v1` tag (33a8154), on map 2.0.0. Version 2 starts with map 3.0.0.

- **`implementedIn` moves to 2 on every implemented entry.** The claim is "this entry is
  implemented, and these tests prove it, in this revision". That is true of 2, the only
  revision this code is. Many entries behave exactly as they did under 1. The map field names
  the revision the claim was checked against, not the first revision the behaviour appeared in.
- **The replay schema stays at 1.** `GameRecord` has the same fields with the same meanings. A
  version 1 record can still be read. It just cannot be replayed against version 2 and
  expected to agree.
- **The corpus baseline and the generator do not change.**

## Consequences

- A tool that compares recorded games has to refuse to compare a version 1 record with a
  version 2 one. That is what the identity is for.
- The next map version that changes what a rule returns bumps the ruleset again. A map version
  that changes only notes, edges or citations does not. Finding 17 (`game-value`'s overlap for a
  man in the winner's home table, expected upstream as 4.0.0) will change a return value, so
  consuming it will be version 3.

## Alternatives rejected

- **Keep version 1, since the new declines are rare.** Rare is still observable. A record whose
  identity matches and whose replay disagrees is exactly the failure the identity exists to
  prevent.
- **Bump the replay schema instead.** The record's shape did not change. Bumping the schema
  would make every old record unreadable, which is a different and false claim.
