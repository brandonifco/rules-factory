# How the backlog is organised

Two labels on every issue: **what kind of thing it is**, and **what it blocks**.

## Category — the project's own decomposition

| Label | What belongs in it |
|---|---|
| `schema` | The corpus map's shape. [0001](decisions/0001-the-corpus-map-is-the-interface.md) says the map is the interface, so a wrong schema is wrong everywhere downstream at once. |
| `method` | The written procedure a mapper or builder follows. Distinct from the schema: a correct schema with a method that contradicts it produces wrong maps, which is exactly how the delegated-standard entries got misclassified. |
| `enforcement` | A check that turns a stated rule into a fact. "A rule worth stating is worth a check" is the kernel's second governing principle and it applies here. |
| `rails` | What a produced engine ships with for the team that maintains it. |
| `evidence` | Measures whether the method works — trials, miss rates, the acceptance test. |
| `map-data` | An error in a specific map rather than in the schema. Cheap to fix, and worth keeping separate so a pile of them is not mistaken for a design problem. |

## Priority — distance from the next engine

The spine of this project is [#3](https://github.com/brandonifco/rules-factory/issues/3), the
acceptance test. Priority is not urgency; it is **what happens if you build the next engine
without doing this**.

### `p1-next-engine` — settle first, or the next engine inherits the defect

A schema defect costs once per engine, and migrating two engines costs more than deciding once.
Everything here is either a schema question, the enforcement that makes a schema answer real, or
data an engine would be built from.

The evidence for putting these first is concrete: the first engine was built from a map with
eleven errors in it, and the correction to `starting-position` invalidated an architectural
commitment the engine had already shipped.

### `p2-acceptance` — needed for the acceptance test, not blocking the next build

Measurement and the builds themselves. These are the work, not the preconditions for it.

### `p3-needs-two-engines` — cannot be generalised from one

Rails especially. Deciding what every produced engine ships with, from a sample of one board
game, is how the predecessor repository ended up encoding one team's operating model as a
framework. Wait for a corpus that is not a game.

## The hub

[#24](https://github.com/brandonifco/rules-factory/issues/24) is not one issue among the
`p1-next-engine` set — it subsumes five of them. #6, #10, #11, #15, #19 and #23 are one question
asked six times, answered in
[0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md). Work #24 and most of the
`schema` label closes with it.

## What this ordering is betting on

That the vocabulary has converged. Trials 3 and 4 produced new *instances* of the six situations
and no new *kinds*, which is the signal that a decision can be derived rather than guessed. If a
regulation engine produces a seventh kind, this ordering was wrong and the schema work should
have waited. That is the bet, and it is recorded here so it can be judged later rather than
rationalised.
