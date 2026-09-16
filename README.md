# Rules Factory

The production apparatus for deterministic rules engines built from plain-language rulesets: a
method for mapping a ruleset, and a factory that turns the map into an engine.

The engine is the product. This is the factory: it takes a published corpus-map package, the
corpus that map was made of, and an engine name, and writes a .NET solution on
[`rules-kernel`](https://github.com/brandonifco/rules-kernel) whose code is tied to the map, with
the gate that judges it, a backlog derived from the map, and a record of what it was built from.
Making the map is not the factory's job. That is [the method](docs/method.md), done by hand.

It is **not** a template you copy and diverge from. A factory keeps a relationship with what
it produced, and every file it writes has one owner
([decision 0018](docs/decisions/0018-every-file-the-factory-writes-has-one-owner.md)).
*Generated* files, such as the code tied to the map, the pins, the gate and the backlog, are
rewritten on every run. *Managed* files (`global.json`, `NuGet.config`,
`Directory.Build.props`) hold the factory's build policy at a recipe version. A re-run updates
them, and refuses to overwrite a hand edit until the engine adopts the file or resets it.
*Engine-owned* files, such as the overlay, the solution and the projects, are written once and
then belong to the engine. Output carries provenance saying which factory commit built it from
what, and which class each file is in. Unless told not to, the factory builds and tests its
output before committing it.

## Status

The manual came first, deliberately: [docs/method.md](docs/method.md) and
[docs/corpus-map.md](docs/corpus-map.md) settled the questions the code would otherwise have
guessed at. The method has been run by hand against real corpora, and
[examples/](examples/README.md) logs what each trial changed.

The factory is now code, in standard-library Python under
[`tools/factory/`](tools/factory/__main__.py). Its milestones, from
[#3](https://github.com/brandonifco/rules-factory/issues/3):

| Milestone | Modules | State on `main` |
|---|---|---|
| M1 intake | `intake.py` | merged. The package is read as data and never run ([0016](docs/decisions/0016-a-map-package-is-data-not-code.md)); the corpus must hash to the map's baseline |
| M2 scaffold and generation | `generate.py`, `ownership.py` | merged. The registry, map entries and correspondence tests as `*.g.cs`; one ownership class per file ([0018](docs/decisions/0018-every-file-the-factory-writes-has-one-owner.md)) |
| M3 gate recipe | `gate.py`, `recipe/` | merged. Every engine carries `scripts/validate.sh` and a CI workflow that runs it |
| M4 provenance | `provenance.py` | merged. `provenance.json` (format 3), and a command that recomputes it |
| M5 backlog | `backlog.py` | merged. `backlog/` files, and GitHub issues matched to them by an entry marker, never by title |
| Verify and commit | `verify.py`, `transaction.py` | merged. `produce` verifies in a staging copy and commits only what passed |
| Acceptance: an engine the factory produced | | [`hoyle-backgammon`](https://github.com/brandonifco/hoyle-backgammon) is produced by `factory/v0.2.1` from `RulesFactory.Maps.HoyleBackgammon` 4.0.0. A from-scratch produce differs from it only in engine-owned files, and `factory provenance` matches it ([evidence](examples/hoyle-backgammon/produced-engine/EVIDENCE.md)). Not yet ticked on [#3](https://github.com/brandonifco/rules-factory/issues/3) |
| Acceptance: rebuild an engine blind, and build something that is not a game | | not done ([#3](https://github.com/brandonifco/rules-factory/issues/3)); criterion 1 is a blind rebuild of `hoyle-backgammon`, since the factory admits no licensed corpus ([0028](docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)) |

Factory versions are tagged `factory/vX.Y.Z`. Provenance records the tag's version for a tagged
commit (`0.2.1` at `factory/v0.2.1`), and `0.0.0-dev+<commit>` for any other commit.

What the CLI accepts is the table below. [`tools/check-readme-status.py`](tools/check-readme-status.py),
run by `validate.sh`, checks it against the parser `tools/factory/__main__.py` builds: a
subcommand or argument without a row fails, and so does a row the parser does not have, or one
marked `not implemented` that the parser does have.

<!-- factory-cli-status:begin -->
| Command | Argument | Status | Notes |
|---|---|---|---|
| `produce` | — | implemented | intake, generation, gate, backlog, provenance, verify, commit |
| `produce` | `--package` | implemented | a `.nupkg` path, or `Id@Version` |
| `produce` | `--corpus` | implemented | the corpus file: `committed-copy`, public domain or openly licensed ([0028](docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)), hashing to the map's baseline |
| `produce` | `--name` | implemented | the engine's PascalCase name |
| `produce` | `--out` | implemented | the engine directory: created when absent, updated when it exists |
| `produce` | `--allow-dirty` | implemented | produce from a factory with uncommitted changes, recorded as `dirty: true` |
| `produce` | `--no-verify` | implemented | commit without building or testing; the output says so |
| `produce` | `--adopt` | implemented | make a managed file engine-owned, keeping its edits |
| `produce` | `--reset` | implemented | overwrite a managed or adopted file with the current recipe |
| `produce` | domain pack | not implemented | no pack exists; provenance records `"packs": []` |
| `produce` | agent rails | not implemented | not an input — the rails are output, and no flag turns them on or off ([0029](docs/decisions/0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)). Emitted: the contract, the roles, the charters, the guard and the engine-owned policy. Not yet: packets, dispatch, the PR policy and the verdict gates ([#152](https://github.com/brandonifco/rules-factory/issues/152)–[#155](https://github.com/brandonifco/rules-factory/issues/155)) |
| `backlog` | — | implemented | synchronise `backlog/` with GitHub issues through `gh` |
| `backlog` | `--create` | implemented | the only action; never closes or deletes an issue |
| `backlog` | `--repo` | implemented | `owner/name` |
| `backlog` | `--dir` | implemented | the engine directory |
| `backlog` | `--package` | implemented | the map package the bodies are checked against: each carries the attribution the corpus licence requires (0023) |
| `provenance` | — | implemented | re-produce in a scratch copy and name every field that does not match |
| `provenance` | `--engine` | implemented | the engine directory |
| `provenance` | `--package` | implemented | default: `Id@Version` from `provenance.json` |
| `verify` | — | implemented | provenance, then restore if the engine has no lock files, then the engine's own gate |
| `verify` | `--engine` | implemented | the engine directory |
| `verify` | `--package` | implemented | default: `Id@Version` from `provenance.json` |
<!-- factory-cli-status:end -->

### What a verified `produce` proves

- **The inputs.** The package is a map package with its checker inside. The map is in a schema
  version this factory reads. The corpus is public domain or openly licensed
  ([0028](docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)),
  and is the committed copy the map was made of. The factory's own `check-map.py --phase consumer`
  passes on the packaged map.
- **The build.** `verify` recomputes provenance, restores (writing the lock files the first
  time, and re-locking them when the run changed the generated pins, as a map version bump
  does), then runs the engine's own gate, `scripts/validate.sh full`: the SDK pin, a locked
  restore, the overlay merge and the packaged consumer checker, the corpus hash under its
  posture, every `*.g.cs` equal to a fresh regeneration, format, and a `-warnaserror` build and
  tests in Debug and Release, with evidence that the tests ran. A refusal or failure at any step
  leaves `--out` as it was.
- **The record.** `provenance.json` names the factory commit, the package and corpus hashes, the
  kernel version, the hash of every recipe file and generated file, the managed files at their
  recipe versions, and the bytes of every file the build reads as configuration.
  `factory provenance` re-produces the engine and names every field that no longer matches.

CI proves this on every pull request. The `validate` job runs
[`scripts/validate.sh`](scripts/validate.sh). The `engine` job runs
[`scripts/validate-engine.sh`](scripts/validate-engine.sh), which produces an engine from the
`hoyle-backgammon` package on the pinned SDK and verifies it.

### What it does not prove

- **That the map is right.** The checks a map passes read its shape and where its citations
  point, not whether an entry says what the corpus says. Mechanical checks caught 1 of 15
  injected comprehension errors, and the engine's tests caught none
  ([0014](docs/decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md)). A blind second
  mapping catches most of them, and every map in this repository must carry a review of its exact
  bytes ([0017](docs/decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)). The
  `hoyle-backgammon` map, which the `engine` job builds from, carries a legacy exemption rather
  than a review.
- **That a rule is implemented.** A produced engine answers each entry that is not
  `implemented` with a decline citing its locator. The rules themselves are hand-written
  handlers, and the backlog lists the ones still to write.
- **That an engine declines what its map leaves open.** An `implemented` entry whose question is
  `unresolved` must decline the question, unless the engine's owner has ruled on it
  ([0027](docs/decisions/0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md)).
  A ruling lives in the overlay, never in the map, beside `declines` for the parts still declined.
  The factory checks that the rulings and declines quote the map's current question and between
  them cover it, name tests the entry names, and name decision records the engine commits.
  `produce`, the gate and `provenance.json` report which answers are the owner's, and
  `Rulings.g.cs` carries them into the engine. What no check reads is whether the engine actually
  declines or rules as the overlay says. The named tests are held only to having run.
- **What the machine did.** Provenance says the engine's source tree is the recorded one. It
  does not record which SDK was installed, what restore fetched beyond the hashes the lock files
  pin, environment variables, MSBuild or NuGet files outside the engine directory, or that a
  given assembly was built from the tree. The limits are listed in
  [`provenance.py`](tools/factory/provenance.py).
- **Anything, under `--no-verify`.** The engine is committed without being built or tested. Lock
  files the generated pins have moved past, in the version they resolve or the range they record
  as requested, are re-locked by `dotnet restore` alone, or the run is refused; they are never
  committed stale.

The generated runtime is typed by entry, and no further than the map declares
([#76](https://github.com/brandonifco/rules-factory/issues/76)). Each entry has its own request
type and typed entry point, so a request for one entry does not compile against another. Each
entry's handler is a generated partial method, so an `implemented` entry whose handler is
missing or has the wrong signature fails the build. The map names no inputs, outputs or units,
though. An engine declares an entry's inputs itself, as properties on the entry's partial request
type, and the typed entry point hands that request to the handler
([#93](https://github.com/brandonifco/rules-factory/issues/93)). Assertion values and results
are still `object`. A wrong domain value inside them is
found at run time, not at compile time. The string-keyed `Registry` and reflection-discovered
`[Implements]` handlers remain, as the shared dispatch and a runtime cross-check.

## Where this sits

| Piece | Repository | Status |
|---|---|---|
| Kernel — identity, provenance, resolution | [`rules-kernel`](https://github.com/brandonifco/rules-kernel) | published; engines pin 0.3.0 |
| Corpus maps — schema, checker, packages | this | maps of two corpora; `hoyle-backgammon` and `faa-part-107` published as packages |
| Corpus toolkit — adapters, locators, boundary policy | none | locator checkers for two citation grammars live here; no adapters |
| Domain packs — tabletop, legal | none | not implemented |
| Agent rails for produced engines | this | decided ([0029](docs/decisions/0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)); `AGENTS.md`, the roles, the charters, the primary-checkout guard and `.github/agent-policy.json` are emitted. Packets, dispatch, PR policy and the verdict gates are open ([#1](https://github.com/brandonifco/rules-factory/issues/1), [#4](https://github.com/brandonifco/rules-factory/issues/4)) |
| **Factory — intake, generation, gate, backlog, provenance, verify** | **this** | implemented; acceptance test ([#3](https://github.com/brandonifco/rules-factory/issues/3)) not passed |
| Produced engines | [`hoyle-backgammon`](https://github.com/brandonifco/hoyle-backgammon) | produced by the factory (`factory/v0.2.1`, map 4.0.0), with hand-written rule handlers ([evidence](examples/hoyle-backgammon/produced-engine/EVIDENCE.md)) |
| Hand-built engines | `deckard`, `SRD_Combat` | built by hand, before the factory |

`hoyle-backgammon` was built by hand first and is now produced by the factory. Its generated
files, managed files and provenance are the factory's output. Its rules code, tests and extra
projects are engine-owned. `deckard` and `SRD_Combat` are still built by hand. They are what the
method was derived from. `deckard`'s corpus is commercial, so it stays hand-built and outside the
factory ([0028](docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)).

## The shape of a run

```
map package   a corpus map published as a .nupkg (0015): map, manifest, checker
corpus        the one corpus the map cites, committed-copy, hashing to its baseline
name          the engine's PascalCase name
        |
        v
    factory produce    intake, generation, gate, backlog, provenance,
                       verify (in a staging copy), commit to --out
        |
        v
engine        a .NET solution on RulesKernel: managed build policy, engine-owned
              projects and overlay, generated *.g.cs tied to the map, the corpus
gate          scripts/validate.sh and the CI workflow that runs it
backlog       backlog/NNN-<entry-id>.md, one per entry still to build, in
              dependency order
provenance    factory commit, map package, corpus, kernel, recipe hashes, and the
              generated, managed, engine-owned and build-input files; "packs": []
rails         AGENTS.md, the roles, the three charters, the primary-checkout guard,
              and .github/agent-policy.json, which the engine owns

not implemented: a domain pack as input; the rails' packets, dispatch, PR policy
and verdict gates
```

## Why a manual before code

The factory's real output is not a repository — it is a *decomposition*. Turning three
hundred pages of prose into a backlog an agent can work is the part that is hard, and it is
not made easier by writing a scaffolder first. [docs/method.md](docs/method.md) is the rules
for doing it; [docs/corpus-map.md](docs/corpus-map.md) is the artifact those rules produce
and everything downstream consumes.

A predecessor attempt shipped the enforcement machinery and deleted the documents it cited,
producing sixty-one references to files that did not exist — several inside runtime error
messages. The manual comes first here partly to avoid repeating that, and partly because
writing it down is what exposes the decisions.

The open work is labelled by what it is and by what it blocks; see
[docs/backlog.md](docs/backlog.md) for the scheme and the reasoning behind the ordering.
