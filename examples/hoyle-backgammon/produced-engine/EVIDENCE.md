# hoyle-backgammon is the factory's output

Evidence for criterion 2 of [#3](https://github.com/brandonifco/rules-factory/issues/3): that
[`hoyle-backgammon`](https://github.com/brandonifco/hoyle-backgammon) is what the factory
produces, plus the engine's own files, and not factory files added to a hand-built repository.
This records a run. It does not tick the criterion.

| Input | Value |
|---|---|
| engine | `brandonifco/hoyle-backgammon` at `dab64e080fab5b7c11f6aeaa7d48cd208abc43d5` (merge of hoyle-backgammon#18, re-produced with rules-factory 0.6.0; map 6.0.0, ruleset 6, replay schema 4, six owner's rulings in its overlay) |
| factory | `factory/v0.6.0`, commit `ec6294a008a4983fc8b3c406e29657b9bb88c06d`, the commit the engine's `provenance.json` records |
| map package | `RulesFactory.Maps.HoyleBackgammon@6.0.0`, as published |
| corpus | the engine's `corpus/hoyle.txt`, sha256 `5d505fa9…645e` |
| produce flags | `--no-verify` (the local SDK was 10.0.111; the kernel pins 10.0.112) |

Reproduce with

```
examples/hoyle-backgammon/produced-engine/equivalence.sh dab64e080fab5b7c11f6aeaa7d48cd208abc43d5 factory/v0.6.0
```

The full output of that command is [equivalence.out](equivalence.out). **Result: PASS.** No
generated or managed file differs. Every difference is engine-owned, and
`factory provenance --engine` reports every field matching.

## What the script does

[equivalence.sh](equivalence.sh) clones the engine at the sha and checks the factory out at the
tag in a scratch worktree. It refuses a tag that is not the factory commit the engine's
provenance names. Then it produces twice, each time into an empty directory:

- **bare**: truly empty.
- **seeded**: empty except for the engine's `corpus-map.overlay.json`, and the decision records
  its owner's rulings name. Generation reads that one engine-owned file, because the generated code
  and the backlog are merge(package map, overlay). Since 0.6.0 the merge also refuses a ruling whose
  `record` is not a file in the output, and provenance hashes each record
  ([decision 0027](../../../docs/decisions/0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md)).
  So the script copies exactly the records the overlay's rulings name, here
  `docs/decisions/0009-…` and `0010-…`. Without them the seeded produce was refused, naming each
  ruling.

[classify.py](classify.py) classifies every path with the factory checkout's own
[`ownership.py`](../../../tools/factory/ownership.py)
([decision 0018](../../../docs/decisions/0018-every-file-the-factory-writes-has-one-owner.md)).
It does not restate the table. Then the script runs `factory provenance --engine` on the clone.

This is not wired into `scripts/validate.sh` or CI. It needs the network (GitHub, and nuget.org
unless the package is already cached) and a published package. It does not build the engine
either: whether the engine builds and its tests pass is the job of hoyle-backgammon's own CI.

## Classification: seeded produce against the engine (120 paths)

| Class | State | Count | Paths |
|---|---|---:|---|
| generated | identical | 20 | every `*.g.cs` (`Rulings.g.cs` among them), `RulesFactory.Packages.g.props`, `corpus/hoyle.txt`, `backlog/README.md`, the gate scripts, `scripts/factory/*.py` (`rulings.py` among them), `.github/workflows/validate.yml` |
| generated | differs | 1 | `provenance.json`, explained field by field below |
| managed | identical | 3 | `global.json`, `NuGet.config`, `Directory.Build.props` |
| engine-owned | identical | 1 | `corpus-map.overlay.json` (the seed) |
| engine-owned | differs | 4 | `Directory.Packages.props`, `HoyleBackgammon.slnx`, `src/HoyleBackgammon/HoyleBackgammon.csproj`, `tests/HoyleBackgammon.Tests/HoyleBackgammon.Tests.csproj` |
| engine-owned | only in engine | 2 | `src/HoyleBackgammon/packages.lock.json`, `tests/HoyleBackgammon.Tests/packages.lock.json` |
| no row (the engine's own) | identical | 2 | `docs/decisions/0009-owner-rulings-are-ruleset-version-five.md`, `docs/decisions/0010-owner-rulings-are-ruleset-version-six.md` (seeded) |
| no row (the engine's own) | only in engine | 87 | 46 `src/HoyleBackgammon` (rules code, handlers, adapter types), 5 `src/Tabletop.Dice`, 21 `tests/HoyleBackgammon.Tests`, 3 `tests/Tabletop.Dice.Tests`, 8 other `docs/decisions`, `README.md`, `MAP-FINDINGS.md`, `LICENSE`, `.gitignore` |
| any | only in produce | 0 | |

The four engine-owned files that differ are the engine's own additions:

- `HoyleBackgammon.slnx` adds the `Tabletop.Dice` projects.
- `HoyleBackgammon.csproj` references `RulesKernel.Randomness` and `Tabletop.Dice`, and adds a
  `RulesFactoryMapItem` target.
- The test project copies the restored map beside the test assembly for `CitationTests`.
- `Directory.Packages.props` has a longer comment.

## provenance.json

Of its 14 top-level fields, 12 are identical: `provenanceFormat`, `engine`, `factory` (including
`dirty: false`), `map`, `corpus`, `kernel`, `packs`, `recipes`, `generated`, `managed`,
`randomness` and `rulings` (new in 0.6.0: the six rulings, each with its record's `recordSha256`). The two that differ are the two the ownership table lets differ:

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

The bare produce, with no overlay, differs from the engine in 34 generated files:

- 29 `backlog/NNN-*.md` items exist only in the bare produce.
- `backlog/README.md`, `Contracts.g.cs`, `Registry.g.cs` and `CorrespondenceTests.g.cs` differ.
- `Rulings.g.cs` exists only in the engine. With no overlay there is no ruling, and 0.6.0 writes no
  such file.

Every one of the 34 is identical to the engine, or absent, once the overlay is seeded. The
overlay alone explains them.

## factory provenance

Run from the `factory/v0.6.0` checkout against the clone:

```
provenance of $WORK/engine: every field matches
```
