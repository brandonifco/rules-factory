# 0018 — Every file the factory writes has one owner: generated, managed or engine-owned

## Status

Accepted — 2026-09-14. Records the fix for
[#72](https://github.com/brandonifco/rules-factory/issues/72), finding 5 of the September 2026
external review.

**Amended 2026-09-14** for [#94](https://github.com/brandonifco/rules-factory/issues/94): a
`produce` that changes the generated pins re-locks the engine's lock files. See
*Amendment — changed pins re-lock* below. The lock-file rows of the table changed; nothing else
did.

## Amendment — changed pins re-lock

The lock files are engine-owned, and the table said no `produce` rewrites them. That made a map
version bump impossible to commit. `produce` rewrites `RulesFactory.Packages.g.props` with the new
map version, lock files resolved against the old version fail the gate's locked restore, and
`verify` commits nothing that fails its gate.

So there is one exception. When a `produce` run changes the resolved pin set of
`RulesFactory.Packages.g.props` (every `PackageVersion` id and version, compared with what the
engine had before the run), `verify` re-locks the existing lock files in the staging copy with
`dotnet restore --force-evaluate`. Then `produce`'s after-restore hook records the new lock files
in `provenance.json`, and the gate's locked restore proves them. The re-locked files are committed
only when the gate passes, and `produce` names them as changed, for the engine to review.

- **Why this doesn't break ownership.** The lock files follow the pins, and the pins are a
  generated fact about the factory's inputs. Keeping lock files that no longer match the pins
  isn't the engine's choice to protect. It is a build that can't restore.
- **What still holds.** When the pin set is unchanged, including when only the props' comments or
  layout changed, nothing is re-locked, and the gate holds the engine to its committed lock files.
  Lock files of projects the engine added are re-locked with the rest, since one restore covers
  the solution. No other engine-owned file is touched.
- **Standalone `factory verify` never re-locks.** It has no earlier pin set to compare with, and it
  runs on the engine in place, outside a transaction, so a relock there would rewrite engine-owned
  files silently and leave them unrecorded. An engine whose pins moved some other way fails the
  gate's locked restore. It re-locks with `scripts/validate.sh lock`, or runs `produce` again.

## Context

The README said the factory is not a template you copy and diverge from. The code said
otherwise. `factory produce` wrote two kinds of file and nothing named the difference:

- **generated** files (`*.g.cs`, `RulesFactory.Packages.g.props`, the backlog, the gate recipe,
  the corpus copy, `provenance.json`), rewritten on every run; and
- a **write-once scaffold** (`global.json`, `NuGet.config`, `Directory.Build.props`,
  `Directory.Packages.props`, the solution, both projects and the overlay), written when absent
  and never again.

The scaffold mixed two different things. The overlay, the solution and the projects are the
engine's: it adds projects, references and files, and it records its own build facts in the
overlay (0015). But `global.json`, `NuGet.config` and `Directory.Build.props` hold the
factory's build policy: the SDK the kernel pins and its roll-forward rule, the package sources
and source mapping restore may use, and the target frameworks, analyzers, warnings-as-errors,
determinism and lock-file settings. Once the first `produce` had run, a factory change to any of
these never reached that engine. An engine produced last month and one produced today were
built under different policies, and neither the engine nor its provenance said so.

Making those files generated would fix the drift, but it would silently overwrite an engine
that had a real reason to change them, such as a private feed, or an SDK the kernel does not
pin yet. Leaving them write-once keeps the drift.

## Decision

**Every path `produce` writes belongs to exactly one of three classes, decided in one table in
code, `TABLE` in [`tools/factory/ownership.py`](../../tools/factory/ownership.py).** The table
below is that table. A test holds them equal, and another walks a produced engine and fails on
any file that matches no row or more than one. `produce` also refuses, before committing, any
written path the table does not classify.

- **generated**: rewritten on every run from the factory's inputs. A hand edit is overwritten.
  `provenance.json` hashes each one in `generated`.
- **managed**: factory policy with a **recipe version**. The factory keeps, for every managed
  file, the SHA-256 of the bytes each version of its recipe wrote (`RECIPE_SHA256`). On each
  run, a managed file that is absent, or whose bytes match any recorded version, is rewritten
  with the current recipe. That is the migration. A managed file whose bytes match no recorded
  version was edited by hand. `produce` refuses and names it. The refusal is transactional
  (#67), so nothing changes. Two flags settle it:
  - `--adopt PATH` moves the file to engine-owned and keeps the edit. The adoption is recorded in
    `provenance.json` (`engineOwned[].adopted`), and later runs read it back, so it is given once.
  - `--reset PATH` overwrites the file with the current recipe and makes it managed again. This
    is also how an adopted file comes back under the factory.

  `provenance.json` hashes each managed file once, in `managed`, together with its
  `recipeVersion`. The two XML files also say in a comment that they are managed and name their
  recipe version. `global.json` cannot carry a comment.
- **engine-owned**: written once, when absent, and never touched again. `provenance.json`
  lists these files in `engineOwned`. They are all build inputs, so each is hashed once, in
  `buildInputs` (#69).

| Path | Class | Recipe | Why this class |
|---|---|---|---|
| `provenance.json` | generated |  | The record of this run, written last, from the run itself. |
| `RulesFactory.Packages.g.props` | generated |  | The kernel and map pins and the map reference are facts about the inputs (#66). |
| `src/{name}/Generated/*.g.cs` | generated |  | The map, registry, typed contracts and embedded provenance, from merge(package, overlay). |
| `tests/{name}.Tests/Generated/*.g.cs` | generated |  | The correspondence and provenance tests, from the same merge. |
| `corpus/*` | generated |  | The corpus copy intake proved against the map's baseline. |
| `backlog/*.md` | generated |  | The entries still to build, from the merge. GitHub issues are synced from it, not the reverse. |
| `scripts/validate.sh` | generated |  | The gate recipe (M3): the factory's definition of acceptable, which an engine must not weaken by editing. |
| `scripts/map-overlay.py` | generated |  | Gate recipe: 0015's merge. |
| `scripts/engine-gate.py` | generated |  | Gate recipe: the non-dotnet checks. |
| `scripts/factory/*.py` | generated |  | The factory's generator, vendored so the gate can regenerate without the factory. |
| `.github/workflows/validate.yml` | generated |  | Gate recipe: CI runs `validate.sh full`. |
| `global.json` | managed | 1 | The SDK the kernel pins and `rollForward: disable`. This is policy every engine should follow as the kernel moves. An engine that must move ahead of the kernel adopts the file. |
| `NuGet.config` | managed | 2 | Package sources and source mapping: supply-chain policy (restore talks to nuget.org only, lock files pin content). An extra feed is a deliberate departure, so it is an explicit adoption. |
| `Directory.Build.props` | managed | 2 | Target frameworks, analyzers, warnings-as-errors, determinism and lock-file mode. The review named exactly these as changes that never reached existing engines. |
| `Directory.Packages.props` | engine-owned |  | Central package management and the test package versions, which an engine bumps itself. It imports the generated pins, and `produce` refuses an engine whose copy does not import them or pins the kernel or map again, so the part that must track the factory is already generated. |
| `{name}.slnx` | engine-owned |  | The engine adds projects to its solution. |
| `src/{name}/{name}.csproj` | engine-owned |  | The engine adds references and files. The map reference lives in the generated props. |
| `tests/{name}.Tests/{name}.Tests.csproj` | engine-owned |  | The engine adds test references. |
| `corpus-map.overlay.json` | engine-owned |  | The engine's three fields per entry (0015). The factory must never overwrite it. |
| `src/{name}/packages.lock.json` | engine-owned |  | Written by `verify`'s first restore (#70) in the staging copy, only when there is no lock file yet, and committed with the engine. After that, the engine relocks (`scripts/validate.sh lock`), reviews and commits it. A `produce` rewrites it only when that run changed the generated pins: it re-locks before the gate (#94, *Amendment* above). |
| `tests/{name}.Tests/packages.lock.json` | engine-owned |  | The same, for the test project. |

`{name}` is the engine name, and `*` matches within one path segment. Files the engine adds
itself, such as hand-written code or the lock files of a project it adds, match no row.
Engine-owned files are listed in `engineOwned` only once they exist. The lock files appear there,
and in `buildInputs`, when `produce`'s after-restore hook rewrites `provenance.json`, which it
builds in the same format 3 as the first record. They are not the factory's to
classify.

**Detection compares against the recipe history in code, not against the hash the last run
recorded in `provenance.json`.** Three reasons:

- It does not trust a file inside the engine. An edited `provenance.json` cannot make a hand
  edit look like the factory's.
- It works for an engine produced before this decision. Its scaffold bytes are version 1 of each
  recipe, so it migrates without a flag.
- It makes a recipe version mean fixed bytes. A test fails when a recipe's bytes change without a
  new version and hash.

Adoption is the one fact read back from `provenance.json`. If that record is missing or
unreadable, nothing counts as adopted. An edited adopted file is then refused, naming
`--adopt`, rather than overwritten. That is the safe direction.

**The gate stays consistent with the classes.** The engine's gate regenerates the generated
`*.g.*` files and fails on a difference (M3). Its vendored generator now includes
`scripts/factory/ownership.py`, itself a generated file. `verify` runs the gate with
`PYTHONDONTWRITEBYTECODE=1`, so importing it leaves no `__pycache__` for a verified `produce` to
commit unclassified. The gate does not judge managed or
engine-owned files. A hand edit to a managed file is caught by the next `produce` and by
`factory provenance` (`managed[<path>]`).

## Alternatives considered

**Make the three policy files generated.** Rejected. Every engine that legitimately moved its
SDK or added a feed would lose that change on the next run without being told. That is the same
defect as drift, pointed the other way.

**Keep them write-once and document it.** Rejected. That is what the review found. The
factory's policy would be a template after all, and "not a template" would stay untrue.

**Detect edits by the hash in `provenance.json` alone.** Workable, and it is what the issue
suggested. It was rejected as the only mechanism, for the reasons above: it trusts engine bytes,
it cannot recognise an engine produced before `managed` existed, and it lets a recipe change
without a version bump go unnoticed.

**A marker comment carrying the version in every managed file, read back to decide.** Rejected
as the mechanism. `global.json` cannot hold one, and a marker is part of the bytes an editor can
change. The XML files carry it for people to read. The decision uses the hash.

**Three-way merge of a hand edit with a new recipe.** Rejected. It needs a base the factory
would have to store, and a merge tool the standard library lacks. It would also decide on the
engine's behalf which change wins in a build-policy file.

**Put the solution and project files under management too.** Rejected for now. Engines edit
them as a matter of course, so every engine would adopt them on day one, and the class would
mean nothing. The parts of them that must follow the inputs already live in generated files.

## Consequences

**A factory change to build policy now reaches existing engines**, through a new recipe version
and its hash in `RECIPE_SHA256`. Changing a managed recipe without doing that fails the tests.
A recipe version must never be removed from the history: an engine still on those bytes would be
refused as hand-edited.

**An engine that edited a managed file must say so once.** Its next `produce` is refused until it
passes `--adopt` or `--reset`. From then on, an adopted file receives no policy changes, and
`provenance.json` shows the adoption to anyone reading the record.

**A managed recipe cannot depend on the engine's name or the map.** None does. If one ever must,
detection needs the recorded hash as well, and this record should be amended.

**`provenance.json` is format 3.** It adds `managed` and `engineOwned`. `buildInputs` no longer
lists managed files, because they are hashed in `managed`. Format-2 records recompute as
mismatches until the engine is produced again.

**`scripts/validate-engine.sh` adopts what it edits.** It points the scratch engine's
`NuGet.config` at a local feed, and, under `FACTORY_DOTNET_SDK_OVERRIDE`, `global.json` at another
SDK. Those are hand edits to managed files. Its re-produce step passes `--adopt` for exactly the
files it edited, which is what a real engine with a private feed would do.
