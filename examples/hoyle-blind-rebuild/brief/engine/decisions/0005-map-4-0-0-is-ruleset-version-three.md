# 0005: Map 4.0.0 is ruleset version three

**Status:** accepted.

## Context

[Decision 0004](0004-map-3-0-0-is-ruleset-version-two.md) made map 3.0.0 ruleset version 2 and
said the next map version that changes what a rule returns bumps the ruleset again. It named the
one expected: finding 17 in `MAP-FINDINGS.md`, `game-value`'s overlap for a man in the winner's
home table.

`RulesFactory.Maps.HoyleBackgammon` 4.0.0 (rules-factory#102, #103) is that version. It changes
one entry. `game-value`'s `ambiguity.question` now names both overlap cases: a loser who has
borne off nothing and has a man up, **or a man in the winner's home table**. Both answer the
gammon condition and the backgammon condition, and the corpus does not say which result he
suffers.

The engine followed 3.0.0's question and declined only the man up. Under version 2,
`Outcome.ValueOf` valued a loser with nothing off, no man up and a man in the winner's home table
a backgammon. Under 4.0.0 it returns `RequiresInterpretation` for him, citing `game-value`.

A game recorded under version 2 that ends that way finished with a backgammon. Replayed now with
the same seed and the same decisions, it stops with `RequiresInterpretation`.

## Decision

**The ruleset is `hoyle-1909-backgammon` version 3.** Version 2 covers map 3.0.0. Version 3
starts with map 4.0.0.

- **`implementedIn` moves to 3 on every implemented entry**, for the reason 0004 gives: the field
  names the revision the claim was checked against.
- **The replay schema stays at 1**, the corpus baseline and the generator do not change.

This is also the first version produced by rules-factory rather than built by hand (factory
0.2.1). That is not why the ruleset moved. Producing the engine changed no rule's answer. The
tests that pinned the answers before the migration still pass unchanged, apart from the ones this
decision names.

## Consequences

- A tool comparing recorded games must refuse to compare a version 2 record with a version 3 one.
> [redacted by build-brief.py: test-name]
