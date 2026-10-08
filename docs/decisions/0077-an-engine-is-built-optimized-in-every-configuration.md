# 0077 — An engine is built optimized in every configuration

## Status

Accepted — 2026-10-08. Records the decision on
[#626](https://github.com/brandonifco/rules-factory/issues/626). Changes the managed
`Directory.Build.props` (recipe 2 → 3, decision
[0018](0018-every-file-the-factory-writes-has-one-owner.md)). Changes no engine-owned file, no gate
step, no test an engine runs, and not the CI timeout.

## Context

The factory renders every engine's CI workflow with `timeout-minutes: 20`. A factory-produced
engine whose suite drives whole runs of its own surface (brandonifco/reykholt#123) outgrew it. Its
`validate` job ran 11 to 17 minutes and was then cancelled at 20 on its main branch
(brandonifco/reykholt#132). The gate runs every test project in Debug and then in Release
(`scripts/validate.sh`), and the Debug pass on a 2-vCPU runner was the longer half.

The first proposal there was to sample the work the suite does, which would have weakened the
invariant the suite exists to hold. Profiling showed that most of the cost was unoptimized engine code. The
fix that shipped (brandonifco/reykholt#133, PR #134) set `<Optimize>true</Optimize>` on the engine
assembly in every configuration and changed no test. The whole suite went from 150.79 s to 81.93 s
on 2 cores, and `validate` from cancelled at 20 minutes to 7 m 10 s.

That engine put the property in its own `.csproj`, which is engine-owned: the factory never writes
it, so no other engine benefits, and the next engine finds the same limit the same way.

A survey of the recipe found nothing that depends on Debug being unoptimized:

- no emitted C# uses `#if DEBUG`, `Debug.Assert` or `[Conditional("DEBUG")]`;
- no test reads stack-trace line numbers or depends on inlining;
- `mutate.py`, `engine-gate.py` and the rendered workflow parse only test verdicts and compiler
  errors, which optimization does not change;
- the gate already runs every test against optimized code in its Release pass.

`DEBUG` stays defined in Debug, because `<Optimize>` does not change the defined constants.

## Decision

1. **`Directory.Build.props`, which the recipe owns, sets `<Optimize>true</Optimize>`
   unconditionally**, so the engine assembly and its tests are optimized in every configuration. It
   is the one file the recipe owns that every project of an engine imports. Putting the property in
   an engine-owned `.csproj` would make it one engine's choice, which is what this record replaces.
2. **The Debug pass stays.** It still builds with `DEBUG` defined and still runs every test, so a
   difference between configurations is still caught. What it no longer covers is the unoptimized
   JIT, which no check reads.
3. **Cost is reduced by making the engine faster, not by doing less of the check.** The timeout
   stays at 20 minutes, as a hang detector.

## Measured

The example engine CI's `engine` job produces is `HoyleBackgammon`, from `examples/hoyle-backgammon`
(`scripts/validate-engine.sh`). It was produced and verified (`factory produce`, then the verifying
re-produce `validate-engine.py` runs) from a detached worktree of `origin/main` (`ce364c9`, recipe 2)
and from the branch head (`dc89f90`, recipe 3), each twice, on a 24-core machine with SDK 10.0.112,
and each engine's gate (`./scripts/validate.sh full`) was timed per step. Seconds, as run 1 / run 2:

| Gate step | before (recipe 2) | after (recipe 3) |
|---|---|---|
| Restore (locked) | 0.7 / 0.7 | 0.7 / 0.7 |
| Format | 2.4 / 2.5 | 2.4 / 2.4 |
| Build + test (Debug) | 2.1 / 2.1 | 2.1 / 2.1 |
| Build + test (Release) | 2.1 / 2.1 | 2.1 / 2.1 |
| whole gate | 8.8 / 8.8 | 8.8 / 8.8 |
| test duration reported, Debug, net10.0 / net8.0 | 36 and 36 ms / 35 and 41 ms | 39 and 35 ms / 35 and 35 ms |

The example engine implements no entry; its 39 tests per target framework run in about 40 ms, so
there is nothing for the optimizer to save and the table shows it: no step moved by more than the
noise of 0.1 s, and the produced engines' build policy differs in `Directory.Build.props` (the property
is there in one and absent in the other). The measurement is therefore evidence of cost and of safety, not of benefit: the gate costs
the same, the same 78 tests ran in both passes, and none changed its verdict. The benefit is the one
measured by the engine that outgrew the limit (150.79 s to 81.93 s on 2 cores, above), where the suite
drives whole runs of the engine and the unoptimized JIT dominated.

For comparison, the factory's own `engine` job (which produces this engine in CI) has a median of
445 s and a maximum of 535 s over its last 30 successful runs; the example engine's own gate is 9 s of
that here, so this change is not expected to move the job's median.

## Compatibility

`Directory.Build.props` is managed, so an engine that has not adopted it takes recipe 3 at its next
`produce`. An engine that adopted it keeps its own. An engine that already sets `<Optimize>` in its
own `.csproj` is unaffected, because the two say the same thing. No test changes its verdict.
