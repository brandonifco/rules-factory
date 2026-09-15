# 0019 — Whether an engine may draw random values is declared by the corpus

## Status

Accepted — 2026-09-14. Decided on
[#92](https://github.com/brandonifco/rules-factory/issues/92). **Extends
[0002](0002-boundary-policy-belongs-to-the-corpus.md) and
[0013](0013-verification-posture-belongs-to-the-corpus.md)**; adds no new principle.

## Context

The engine gate the factory emits (`tools/factory/recipe/engine-gate.py`) refused
`RulesKernel.Randomness` unconditionally, and `provenance.py` recorded `"randomness": "none"` as a
constant. That was true of Part 107, which must never draw a random value, and it was the
factory's default rather than anything a corpus said. Backgammon is played with dice. The
hand-built `hoyle-backgammon` engine draws through the kernel's randomness package in
`Tabletop.Dice`, `Opening` and `Game.Play`, so a factory-produced backgammon engine could never
pass `verify`. And if the gate had simply been loosened, provenance would have said `none` about
an engine that throws dice.

Two things are already settled elsewhere. rules-kernel makes randomness an optional package
(its decision 0002). Every draw goes through one primitive, `IRandomSource`. The implementation
is PCG32, seeded with `Pcg32.FromSeed` and resumable from a captured `Pcg32State` (its decision
0005), so a game's draws replay exactly from the seed. The kernel therefore answers *how* an
engine draws. It cannot answer *whether* a particular ruleset does. That answer is in the rules.

## Decision

**Per corpus, recorded in the manifest, as `randomness`.** No factory default. 0002 decided where
a corpus may live and 0013 decided how it is verified and whether a map may quote it; this is
the same answer for the same kind of question.

### Two values

- **`none`**: the rules call for no chance. A conforming engine draws no random value, so
  `RulesKernel.Randomness` must not be reachable from it, directly or transitively.
- **`seeded`**: the rules call for chance (dice, a shuffle, a draw). A conforming engine may draw,
  and only through the kernel's seeded source: `IRandomSource` over `Pcg32`, with the seed in
  the caller's hands so that a game replays. It is not permission to use `System.Random`, the
  clock or the OS entropy pool. The gate cannot see calls, so that part is not checked; see
  Consequences.

The name says what the value controls, and `seeded` says how the engine draws. A boolean
(`randomness: true`) would say only whether. Adding a second way to draw later means adding a
value to this field, and a new value is a decision, not a quiet change in what `true` means.

### Why it is the corpus's property

Whether chance is part of a ruleset is a fact of the text, true whoever builds the engine.
Backgammon's rules throw dice. Part 107's never draw a value. An engine that disagreed with its
corpus would be wrong either way: one that drew random values for Part 107 would give answers the
regulation does not, and a backgammon engine that could not draw could not play the game. So it
is declared beside `boundaryPolicy`, `verification` and `quotation`, by a person, per corpus, and
nothing infers it: not from `licence`, not from the map's entries (a map records rules, and no
field says "this rule throws a die"), and not from the factory.

| corpus | randomness |
|---|---|
| `hoyle-1909` | `seeded` |
| `cfr-14-107` (2026-01-01) | `none` |
| `cfr-14-107` (2020-01-01) | `none` |

### What is checked, and where

- **`check-map.py --only postures`** (publish phase): every admitted corpus declares `randomness`
  as `none` or `seeded`. Missing is a failure, not a default (0002's rule for `boundaryPolicy`).
- **Intake**: the corpus an engine is produced from declares one of the two values. A package
  whose manifest predates the field is refused. It is not read as `none`.
- **Generation**: under `seeded`, `RulesFactory.Packages.g.props` pins `RulesKernel.Randomness`
  at the kernel's version, the one the factory pins for `RulesKernel`, and references nothing.
  Whether and where to draw is the engine's own code; the pin means only that when the engine
  references the package, the version is not the engine's to choose. Under `none` there is no
  pin. `produce` refuses a seeded engine whose own MSBuild files pin the package again.
- **The engine gate**, in both directions. Under `none`, a lock file resolving the package, or any
  project or props file naming it, fails, as before. Under `seeded`, the engine may reference it,
  and a pin or version for it anywhere but the generated props fails.
- **Provenance** records the declared value, and recompute compares it like any other field.

### Where the gate reads the declaration

From the **restored map package's manifest**, the `Manifest` path of the package's
`RulesFactoryMap` item, and not from any file the engine commits.

The alternative was `provenance.json`, which carries the same value. It is a file in the engine's
tree, though. The gate does not recompute provenance (only `factory provenance` does), so an engine
could edit `"none"` to `"seeded"` and pass. The packaged manifest cannot be edited that way. The
package's version is pinned in `RulesFactory.Packages.g.props`, which the gate's regeneration
step holds byte for byte. Its bytes are pinned by the content hash in the lock files, which a
locked restore enforces. To change the declaration, an engine has to be built from a different
package, and that shows in the pins, the lock files and provenance.

The cost is ordering. The check needs a restored package, so it runs after the map is located.
When restore fails, it is skipped, and the gate has already failed.

## Alternatives considered

**Keep refusing, and let a dice engine adopt the gate.** Rejected. The gate is generated so that
it cannot be weakened by hand (0018). A board-game engine that has to own its gate has no gate
the factory stands behind.

**A repository-wide or factory-wide setting.** Rejected, for 0002's reason. The two example
corpora answer it in opposite directions, and both are right.

**Infer it from the engine.** "It references the package, so it is seeded." Rejected. The
direction of trust would be backwards: the check exists to hold the engine to the corpus, so the
engine cannot be the source of the answer.

**A boolean.** Rejected above. It names no mechanism, and the one mechanism the kernel offers is
the point.

**Reference the package from the generated props under `seeded`.** Rejected. It would make
every seeded engine, and its test project, restore the package whether it draws or not. An
engine that implements no chance rule yet would still carry a dependency its code does not use.

## Consequences

**The field is a major change to a map package** under 0015's list, like `quotation`. It is
added before `RulesFactory.Maps.HoyleBackgammon` 3.0.0 and `RulesFactory.Maps.FaaPart107` 2.0.0
are published, so no version was cut without it. Earlier published versions (backgammon 2.x,
Part 107 1.x) do not declare it, and the factory refuses to produce from them.

**The manifest is not under the review gate.** 0017 reviews a map's bytes (`corpus-map.json`,
recorded in `review.json`), and the manifest is not the map. Adding the field changes no map's
bytes and no review, and `check-map-review.py` passes unchanged. The declaration is reviewed
the way the other manifest fields are: in the pull request that adds it. Whether manifests
should carry a digest of their own is a question for 0017, not this record.

**`seeded` is not proof that every draw is seeded.** The gate sees packages, not calls. An engine
could reference nothing and still call `System.Random`, under either value. The gate
never caught that, and it still does not. What changed is that the package-level check now
matches the corpus, and provenance states the corpus's answer instead of a constant. Detecting
unseeded sources in engine code would be an analyser, and nothing here attempts one.
