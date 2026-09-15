# hoyle-backgammon is the factory's output

Evidence for criterion 2 of [#3](https://github.com/brandonifco/rules-factory/issues/3): that
[`hoyle-backgammon`](https://github.com/brandonifco/hoyle-backgammon) is what the factory
produces, plus the engine's own files, and not factory files added to a hand-built repository.
This records a run. It does not tick the criterion.

| Input | Value |
|---|---|
| engine | `brandonifco/hoyle-backgammon` at `56685020cc7d976beb7b8b6ebdb70d2f15ed1161` (merge of hoyle-backgammon#17, re-produced with rules-factory 0.5.0; map 6.0.0, ruleset 5) |
| factory | `factory/v0.5.0`, commit `5bdd77f2b4b0a5e628c1f4b2dd5c476025785184`, the commit the engine's `provenance.json` records |
| map package | `RulesFactory.Maps.HoyleBackgammon@6.0.0`, as published |
| corpus | the engine's `corpus/hoyle.txt`, sha256 `5d505fa9…645e` |
| produce flags | `--no-verify` (the local SDK was 10.0.111; the kernel pins 10.0.112) |

Reproduce with

```
examples/hoyle-backgammon/produced-engine/equivalence.sh 56685020cc7d976beb7b8b6ebdb70d2f15ed1161 factory/v0.5.0
```

The full output of that command is [equivalence.out](equivalence.out). **Result: PASS.** No
generated or managed file differs. Every difference is engine-owned, and
`factory provenance --engine` reports every field matching.

## What the script does

[equivalence.sh](equivalence.sh) clones the engine at the sha and checks the factory out at the
tag in a scratch worktree. It refuses a tag that is not the factory commit the engine's
provenance names. Then it produces twice, each time into an empty directory:

- **bare**: truly empty.
- **seeded**: empty except for the engine's `corpus-map.overlay.json`. Generation reads that one
  engine-owned file, because the generated code and the backlog are merge(package map, overlay).

[classify.py](classify.py) classifies every path with the factory checkout's own
[`ownership.py`](../../../tools/factory/ownership.py)
([decision 0018](../../../docs/decisions/0018-every-file-the-factory-writes-has-one-owner.md)).
It does not restate the table. Then the script runs `factory provenance --engine` on the clone.

This is not wired into `scripts/validate.sh` or CI. It needs the network (GitHub, and nuget.org
unless the package is already cached) and a published package. It does not build the engine
either: whether the engine builds and its tests pass is the job of hoyle-backgammon's own CI.

## Classification: seeded produce against the engine (117 paths)

| Class | State | Count | Paths |
|---|---|---:|---|
| generated | identical | 18 | every `*.g.cs`, `RulesFactory.Packages.g.props`, `corpus/hoyle.txt`, `backlog/README.md`, the gate scripts, `scripts/factory/*.py`, `.github/workflows/validate.yml` |
| generated | differs | 1 | `provenance.json`, explained field by field below |
| managed | identical | 3 | `global.json`, `NuGet.config`, `Directory.Build.props` |
| engine-owned | identical | 1 | `corpus-map.overlay.json` (the seed) |
| engine-owned | differs | 4 | `Directory.Packages.props`, `HoyleBackgammon.slnx`, `src/HoyleBackgammon/HoyleBackgammon.csproj`, `tests/HoyleBackgammon.Tests/HoyleBackgammon.Tests.csproj` |
| engine-owned | only in engine | 2 | `src/HoyleBackgammon/packages.lock.json`, `tests/HoyleBackgammon.Tests/packages.lock.json` |
| no row (the engine's own) | only in engine | 88 | 46 `src/HoyleBackgammon` (rules code, handlers, adapter types), 5 `src/Tabletop.Dice`, 21 `tests/HoyleBackgammon.Tests`, 3 `tests/Tabletop.Dice.Tests`, 9 `docs/decisions`, `README.md`, `MAP-FINDINGS.md`, `LICENSE`, `.gitignore` |
| any | only in produce | 0 | |

The four engine-owned files that differ are the engine's own additions:

- `HoyleBackgammon.slnx` adds the `Tabletop.Dice` projects.
- `HoyleBackgammon.csproj` references `RulesKernel.Randomness` and `Tabletop.Dice`, and adds a
  `RulesFactoryMapItem` target.
- The test project copies the restored map beside the test assembly for `CitationTests`.
- `Directory.Packages.props` has a longer comment.

## provenance.json

Of its 13 top-level fields, 11 are identical: `provenanceFormat`, `engine`, `factory` (including
`dirty: false`), `map`, `corpus`, `kernel`, `packs`, `recipes`, `generated`, `managed` and
`randomness`. The two that differ are the two the ownership table lets differ:

- **`buildInputs`** hashes the engine-owned files the build reads, so it follows the engine's
  bytes. classify.py checks each recorded hash against the file in the clone:
  - 4 items differ from the first produce because the engine changed those engine-owned files:
    `Directory.Packages.props`, the `.slnx` and the two `.csproj`.
  - 6 items the engine added: the two `HoyleBackgammon` lock files, and the `Tabletop.Dice` and
    `Tabletop.Dice.Tests` project and lock files.
- **`engineOwned`** has two extra rows in the engine, the `HoyleBackgammon` src and test lock
  files. Verify's first restore writes them. The evidence produces ran `--no-verify`, so they
  have none. No row's `adopted` flag differs.

## Bare produce

The bare produce, with no overlay, differs from the engine in 33 generated files:

- 29 `backlog/NNN-*.md` items exist only in the bare produce.
- `backlog/README.md`, `Contracts.g.cs`, `Registry.g.cs` and `CorrespondenceTests.g.cs` differ.

Every one of the 33 is identical to the engine, or absent, once the overlay is seeded. The
overlay alone explains them.

## factory provenance

Run from the `factory/v0.5.0` checkout against the clone:

```
provenance of $WORK/engine: every field matches
```
