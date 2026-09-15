# 0028 — A licensed-copy map is restored from the operator's own feed, and its engine's CI says NOT VERIFIED

## Status

Proposed — 2026-09-15, on [#142](https://github.com/brandonifco/rules-factory/issues/142). Accepted
when the pull request that closes #142 merges. **Extends
[0022](0022-a-licensed-copy-is-used-locally-by-a-named-operator-and-never-published.md)**: where a
licensed map package comes from on the operator's machine, and what an engine of one runs in CI.
**Keeps [0018](0018-every-file-the-factory-writes-has-one-owner.md)**: no ownership row, managed
recipe or recipe version changes. Blocks criterion 1 of
[#3](https://github.com/brandonifco/rules-factory/issues/3).

## Context

0022 lets one named operator pack a map of a licensed `local-copy` corpus into a local `.nupkg`, and
produce and verify an engine from it. It never said how that engine restores the package. An engine
takes its map as a NuGet package (0015). The managed `NuGet.config` names nuget.org and nothing else,
and a licensed map is never on nuget.org. So `produce` and `verify` under the exception both failed at
restore with `NU1101`.

0022 also said the engine's CI "cannot verify its corpus", and that posture is NOT VERIFIED there. It
is worse than that. The emitted workflow runs `./scripts/validate.sh full`, whose locked restore can
never find the package on a runner, so every push goes red. A workflow that is always red is neither
a gate nor a NOT VERIFIED.

A spike on the synthetic licensed fixture, with the real dotnet (#142), tried each way in:

- **Seeding the NuGet global packages folder, with the managed `NuGet.config` untouched.** The whole
  gate passed: locked restore, merge, the consumer checker, posture verified from `envVar`,
  regeneration, format, and build and tests in Debug and Release. Both lock files pinned the packed
  `.nupkg`'s hash. Nothing was committed.
- **`RestoreAdditionalProjectSources` from the environment.** Refused by package source mapping.
- **A `%VAR%` local source in `NuGet.config`.** It restores, but only by adopting the managed file.
  That puts a second source into the engine's committed supply-chain policy, and it fails with
  `NU1301` wherever the variable is unset.
- **A gitignored `NuGet.config.local` imported by the managed one.** NuGet has no import, and the
  managed file's `<clear />` drops sources from user and machine configs.
- **CI without the package.** Whitespace formatting runs with no restore. Nothing restores: the test
  project references the engine project, and the engine project references the map.

## Decision

### 1. The operator names a feed directory, and the factory seeds the global packages folder from it

**`RULES_FACTORY_LOCAL_MAP_FEED`** names a directory on the operator's machine that holds the `.nupkg`
files `pack-map.py --licensed-copy-exception --out` wrote. It must be an absolute path to a directory,
**outside every git work tree**. The package is never committed, so it must not sit where a `git add`
would pick it up. The operator sets it once, in the shell profile, beside the corpus's `envVar`.

Under `--licensed-copy-exception`, and only for an engine whose corpus is `local-copy`
([`tools/factory/local_map.py`](../../tools/factory/local_map.py)):

- **Which package.** A `--package` file is itself. For `Id@Version`, given or read from
  `provenance.json`, the factory uses the global packages folder's copy if it has one, and otherwise
  `<feed>/<Id>.<Version>.nupkg`. So `verify` and `provenance` with no `--package` never go to
  nuget.org for a package that is not there. If neither place has it, `verify` and `provenance` are
  refused, naming the variable and the pack command. `produce` cannot know the corpus is `local-copy`
  before intake, so it only looks in the feed and never refuses for its absence.
- **Seeding, before anything restores.** `produce` seeds before its verify or relock. `verify` seeds
  before its stages. The package's SHA-256 must be what provenance records (`nupkgSha256`). If the
  global packages folder already holds that id and version, its `.nupkg.sha512` must match: then
  nothing runs. If it holds a different package under the same id and version, the run is refused,
  naming the directory to delete. Otherwise a throwaway restore runs in a temporary directory outside
  the engine: one project referencing `Id` at `[Version]`, and a `NuGet.config` whose only source is a
  temporary folder holding a copy of that one file. NuGet extracts it, so the layout is NuGet's own.
- **Recorded as before.** `provenance.json` still records the package id, version, `nupkgSha256` and
  the hash of each part. The lock files pin its sha512, and the gate's locked restore holds the engine
  to them.

**The engine's `NuGet.config` does not change.** It stays the managed recipe: nuget.org, and nothing
else. The local package never becomes a source of the engine. It reaches restore only through the
global packages folder, where the lock file's content hash decides whether it is the right one.

### 2. A local-copy engine's CI runs what needs no licensed input, and says NOT VERIFIED

For an engine whose corpus is `local-copy`, `produce` writes
[`recipe/validate-local-copy.yml`](../../tools/factory/recipe/validate-local-copy.yml) at
`.github/workflows/validate.yml`, in place of `recipe/validate.yml`. It has the same path, the same
ownership row (generated), the same triggers and permissions, and the same action pins. It has two jobs:

- **`checks that need no licensed input`**, which fails on a real defect:
  - the SDK pin, with roll-forward disabled;
  - every project has a `packages.lock.json` (`engine-gate.py lock-files`);
  - nothing under `corpus/`, and no `.nupkg`, is committed;
  - `dotnet format whitespace --folder --verify-no-changes`;
  - every project whose `ProjectReference` closure does not reach the engine project: a locked
    restore, a Release build with `-warnaserror`, and a test run for test projects. A fresh engine has
    none, and the step says so. An engine-owned project such as a dice library over the kernel is
    built here.

  The job writes `NOT VERIFIED: licensed map not available in CI` to the run summary, naming what did
  not run.
- **`NOT VERIFIED: licensed map not available in CI`**, a job that always passes. It carries the
  status in its name, where a pull request's checks list shows it, and raises a warning annotation.

No step runs `validate.sh`, and nothing uses `continue-on-error`. A step that can fail is never
dressed as passing, and a green run never claims the engine was verified.

### 3. The full verify happens only on the operator's machine

0022's rule stands, and this makes it explicit. **`./scripts/validate.sh full`, and so `factory
verify`, is the one definition of acceptable for a local-copy engine, and it runs only on the
operator's machine**, under the exception, with the corpus at `envVar` and the map from the feed.
CI's checks are a subset that needs no licensed input. They are never a substitute for the full gate,
and the workflow says so in its header, its job name and its summary.

## Alternatives considered

**Put the feed into the engine's `NuGet.config`** (a `%VAR%` source, or an adopted file). Rejected:
it changes the engine's committed supply-chain policy for a package that is never published. It
needs `--adopt` on every licensed engine, and it breaks restore wherever the variable is unset.

**A gitignored `NuGet.config.local`.** Not possible, as the spike found: NuGet has no include, and
the managed file clears lower configs.

**Document seeding and leave it to the operator.** Rejected. Seeding by hand means a throwaway project
every time the packages folder is cleared. Nothing would check that the seeded package is the one
provenance records. A stale package under the same id and version fails the locked restore with a
message that does not say why.

**Write the global packages folder's layout directly**, without dotnet. Rejected: the layout
(`.nupkg.metadata`, `.sha512`, the extracted parts) is NuGet's to define, and a restore gets it right
by construction.

**Run the full gate in CI and let it fail, or mark it `continue-on-error`.** Rejected: a permanently
red check teaches everyone to ignore the check. A failing step shown as passing hides the defects the
checks that can run would have caught.

**No CI at all for a licensed engine.** Rejected: the SDK pin, lock files, formatting, a committed
corpus and the map-free projects are real defects a runner can catch.

**An emitted script for the CI checks.** Not chosen: it needs a new ownership row. `ownership.py` is
vendored into every engine, so the row would change every public engine's bytes. The steps live in
the one generated workflow file instead.

## Consequences

**Every committed-copy engine is byte-identical.** Its workflow is `recipe/validate.yml` as before. No
vendored module (`generate.py`, `intake.py`, `ownership.py`, `provenance.py`, `rulings.py`) and no
recipe script changed. For hoyle-backgammon, faa-part-107 and srd-52-combat, a produce before and after
this change gives the same bytes in every file but `provenance.json`'s factory commit and recipe
digest.

**The operator's setup** for a licensed corpus is two variables, both outside every repository:

```sh
export SR6_CORE_TEXT="$HOME/sr6-local/sr6-core.txt"                 # the corpus's envVar (0013, 0022)
export RULES_FACTORY_LOCAL_MAP_FEED="$HOME/sr6-local/feed"          # this record
python3 tools/pack-map.py <map dir> --out "$RULES_FACTORY_LOCAL_MAP_FEED" --licensed-copy-exception
python3 tools/factory produce --package RulesFactory.Maps.<Name>@<version> --corpus "$SR6_CORE_TEXT" \
  --name <Engine> --out <engine> --licensed-copy-exception
```

The engine's own `./scripts/validate.sh full` then works by hand too, for as long as the global
packages folder holds the package. After `dotnet nuget locals all --clear`, `factory verify
--licensed-copy-exception` seeds it again.

**It is proven with the real dotnet** in
[`scripts/validate-engine.sh`](../../scripts/validate-engine.sh), on the synthetic fixture:

- a pack into a feed, and a produce from `Id@Version` that seeds, verifies and pins the packed hash;
- a verify after the packages folder is cleared;
- the full gate failing at restore on a simulated runner, and every step of the emitted `checks` job
  passing there.

The fixture borrows the one raw-bytes `hashDerivation` the vendored gate already knows, because the
gate's own process cannot have a test derivation patched in. Its text is still invented, and its
licence field says the name is borrowed.

**Limits.** The feed check looks for a git work tree, not for every place a file could be shared from.
Like 0022, this is a guardrail against accident, not a security boundary. A package seeded into a
shared machine's global packages folder is readable by whoever can read that folder.
