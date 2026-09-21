# Rules Factory

The production apparatus for deterministic rules engines built from plain-language rulesets:
a mapper that reads a ruleset, validation that certifies what it produced, and a factory that
turns a certified map into an engine. It admits only
rulesets that are public domain or openly licensed, because the corpus and its map are committed
and published
([0028](docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md));
a commercial rulebook is outside it.

The engine is the product. This is the factory: it takes a published corpus-map package, the
corpus that map was made of, and an engine name, and writes a .NET solution on
[`rules-kernel`](https://github.com/brandonifco/rules-kernel) whose code is tied to the map, with
the gate that judges it, and a record of what it was built from. The backlog derived from the map
is filed as GitHub issues and rendered on demand, not committed into the engine.
Making the map is not the factory's job, and this repository is not only the factory
([0032](docs/decisions/0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md)).

It is **not** a template you copy and diverge from. A factory keeps a relationship with what
it produced, and every file it writes has one owner
([decision 0018](docs/decisions/0018-every-file-the-factory-writes-has-one-owner.md)).
*Generated* files, such as the code tied to the map, the pins and the gate, are
rewritten on every run. *Managed* files (`global.json`, `NuGet.config`,
`Directory.Build.props`) hold the factory's build policy at a recipe version. A re-run updates
them, and refuses to overwrite a hand edit until the engine adopts the file or resets it.
*Engine-owned* files, such as the overlay, the solution and the projects, are written once and
then belong to the engine. Output carries provenance saying which factory commit built it from
what, and which class each file is in. Unless told not to, the factory builds and tests its
output before committing it.

## Three subsystems over one contract

```text
                              map contract
                        what a map's fields mean
                       /          |             \
                      v           v              v
                  mapper    map validation     factory
             corpus -> map   map -> verdict   map -> engine
```

| Subsystem | Where | What it takes | What it produces |
|---|---|---|---|
| **Mapper** | [`tools/mapper/`](tools/mapper/__init__.py) and [docs/mapper.md](docs/mapper.md); the map itself is still made by hand, by [the method](docs/method.md) | a pinned corpus, its manifest, an adapter, a mapping protocol | a candidate map, and the record of how it was made |
| **Validator** | [`tools/mapvalidator/`](tools/mapvalidator/__init__.py) and [docs/validator.md](docs/validator.md), built into `tools/check-map.py`, with the locator checkers, [`tools/check-map-review.py`](tools/check-map-review.py), [`tools/pack-map.py`](tools/pack-map.py) and [`tools/mutate-map.py`](tools/mutate-map.py), which measures what all of that misses | a map and its manifest | a verdict, and a map that may become a version |
| **Factory** | [`tools/factory/`](tools/factory/__main__.py) | a published map package and the corpus it was made of | a deterministic engine on `rules-kernel` |
| **Map contract** | [`tools/mapcontract/`](tools/mapcontract/__init__.py) | — | the map's closed vocabularies and the readers that get a field out of an entry |

Each asks a different question — the mapper *what does this corpus say, and where does its
certainty end?*, the validator *has the mapper justified those claims, and is this map safe
to rely on?*, the factory *given an acceptable map, what follows mechanically?* The mapper is
the interpreter and may not certify itself; the validator is the adversary, and what it
validates includes the uncertainty, because a map that collapsed a genuine ambiguity into one
confident reading passes every check there is
([0033](docs/decisions/0033-the-validator-is-the-adversary-and-validates-the-uncertainty-too.md)).
The three are siblings over the contract:
**none imports another**, and the contract imports none of them. The
factory therefore knows nothing about how a map was made — give it a valid, appropriately
certified map and it produces an engine — and producer and verifier stay apart for the reason
production code is not its own only test oracle.
[`tools/check-boundaries.py`](tools/check-boundaries.py), run by `validate.sh`, holds that
direction; its docstring says what it cannot see. The mapper is drawn as though it were already
a separate repository, and is not one yet: the map schema and the mapping method are still
co-evolving, and 0032 records what would justify the split.

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
| M1 intake | `intake.py` | merged. The package is read as data and never run ([0016](docs/decisions/0016-a-map-package-is-data-not-code.md)); every cited corpus is re-hashed, and [0048](docs/decisions/0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md) binds those resolved bytes to the exact map, manifest and packaged checker that passed the publish gate |
| M2 scaffold and generation | `generate.py` over `semantics.py`, `csharp.py`, `entries.py`, `registry.py`, `contracts.py`, `correspondence.py`, `pins.py`, `scaffold.py`, `agentrails.py`; `ownership.py` | merged. The registry, map entries and correspondence tests as `*.g.cs`; one ownership class per file ([0018](docs/decisions/0018-every-file-the-factory-writes-has-one-owner.md)). `generate.py` was one 88 KB module until [#171](https://github.com/brandonifco/rules-factory/issues/171) split it by what it emits; it is now the composition, and the name a produced engine imports |
| M3 gate recipe | `gate.py`, `recipe/` | merged. Every engine carries `scripts/validate.sh` and a CI workflow that runs it |
| M4 provenance | `provenance.py` | merged. `provenance.json` (format 3), and a command that recomputes it |
| M5 backlog | `backlog.py` | merged. GitHub issues, one per entry still to build, matched by an entry marker and never by title; one state label and one risk label from the engine's own `.github/agent-policy.json`. Rendered from the map and the overlay on demand and never committed into the engine ([#243](https://github.com/brandonifco/rules-factory/issues/243)) |
| Verify and write out | `verify.py`, `transaction.py` | merged. `produce` verifies in a staging copy and writes only what passed into `--out`. It writes files and makes no commit: the changes are left in the engine's working tree to review and commit |
| Acceptance test | | met; [#3](https://github.com/brandonifco/rules-factory/issues/3) closed 2026-09-16. A blind rebuild of `hoyle-backgammon` passes its tests ([evidence](examples/hoyle-blind-rebuild/EVIDENCE.md)); a board game ([`hoyle-backgammon`](https://github.com/brandonifco/hoyle-backgammon)), a regulation ([`faa-part-107`](https://github.com/brandonifco/faa-part-107)) and an SRD rulebook ([`srd-52-combat`](https://github.com/brandonifco/srd-52-combat)) are produced, carry provenance that `factory provenance` matches, and pass `factory verify` ([evidence](examples/acceptance-4-5/EVIDENCE.md)). The SR6 rebuild the test first named was dropped with licensed corpora ([0028](docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)) |

Factory versions are tagged `factory/vX.Y.Z`. Provenance records the tag's version for a tagged
commit (`0.2.1` at `factory/v0.2.1`), and `0.0.0-dev+<commit>` for any other commit.

What the CLI accepts is the table below. [`tools/check-readme-status.py`](tools/check-readme-status.py),
run by `validate.sh`, checks it against the parser `tools/factory/__main__.py` builds: a
subcommand or argument without a row fails, and so does a row the parser does not have, or one
marked `not implemented` that the parser does have. The prose cannot be checked that way, but one claim in it
can: [`tools/check-status-issues.py`](tools/check-status-issues.py) fails when a sentence or row
says something is "not yet", "not done" or "not passed", or "is open", and cites a closed issue.
Everything else in the prose is checked by a person on every pull request: its `## Documentation`
section accounts for every living document, and the `documentation` check holds that section to
the diff ([AGENTS.md](AGENTS.md) §3).

<!-- factory-cli-status:begin -->
| Command | Argument | Status | Notes |
|---|---|---|---|
| `produce` | — | implemented | intake, generation, gate, provenance, verify, write out. It writes no backlog, and removes one an earlier produce committed ([#243](https://github.com/brandonifco/rules-factory/issues/243)) |
| `produce` | `--package` | implemented | a `.nupkg` path, or `Id@Version` |
| `produce` | `--corpus` | implemented | one file per cited corpus: `committed-copy`, public domain or openly licensed ([0028](docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)), hashing to its manifest identity and to the same identity bound into the package by [0048](docs/decisions/0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md) |
| `produce` | `--name` | implemented | the engine's PascalCase name |
| `produce` | `--out` | implemented | the engine directory: created when absent, updated when it exists |
| `produce` | `--allow-dirty` | implemented | produce from a factory with uncommitted changes, recorded as `dirty: true` |
| `produce` | `--no-verify` | implemented | write without building or testing; the output says so, and the run ends **NOT VERIFIED (exit 3)**, never 0 |
| `produce` | `--adopt` | implemented | make a managed file engine-owned, keeping its edits |
| `produce` | `--reset` | implemented | overwrite a managed or adopted file with the current recipe |
| `produce` | `--produce-report` | implemented | a JSON report of the run: what moved and from what to what, every path written with its ownership class, and the provenance diff. A factory update's pull request is filled in from it ([#193](https://github.com/brandonifco/rules-factory/issues/193)) |
| `produce` | domain pack | not implemented | no pack exists; provenance records `"packs": []` |
| `produce` | agent rails | not implemented | not an input — the rails are output, and no flag turns them on or off ([0029](docs/decisions/0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)). Emitted: the contract, the roles, the charters, the guard, the engine-owned policy, the packets, dispatch, the pull request contract, the verdict gates, the rails doctor and the kernel's determinism analyzers. `factory rails --apply` is what makes the checks required on GitHub. Proven on a produced engine and on a real rule: `faa-part-107` was re-produced onto the rails, and `control-links-working` (§ 107.49(c)) went issue to merge through them ([#157](https://github.com/brandonifco/rules-factory/issues/157) closed 2026-09-16, [evidence](https://github.com/brandonifco/faa-part-107/pull/47)) |
| `backlog` | — | implemented | render an engine's backlog from its map package and its `overlay/`, and either file it as GitHub issues through `gh` or print it. `--create` labels each issue: state from the item's dependencies, `normal` risk on an issue with none. A `needs-decision` state and a promoted risk are a person's, and a sync never undoes either ([0029](docs/decisions/0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)) |
| `backlog` | `--create` | implemented | create missing issues and update changed ones; never closes or deletes an issue |
| `backlog` | `--render` | implemented | print the rendering as one Markdown document and send nothing; the replacement for the `backlog/` the factory no longer commits ([#243](https://github.com/brandonifco/rules-factory/issues/243)) |
| `backlog` | `--repo` | implemented | `owner/name` |
| `backlog` | `--dir` | implemented | the engine directory |
| `backlog` | `--to` | implemented | with `--render`, write the item files to this directory instead of printing them. A directory inside the engine is refused unless `git check-ignore` agrees the engine ignores it |
| `backlog` | `--package` | implemented | the map package the backlog is rendered from and the bodies checked against: each carries the attribution the corpus licence requires (0023) |
| `rails` | — | implemented | report, or put in place, the rails GitHub itself enforces: the labels, the factory's own branch ruleset, and the three required checks |
| `rails` | `--repo` | implemented | `owner/name` |
| `rails` | `--dir` | implemented | the engine directory, for the policy and the rail files |
| `rails` | `--check` | implemented | read-only: one row per rail, and what is not in place. The rail files are compared byte for byte with the recipe, the policy is judged by the rule the engine gate uses, and the rules in force on the default branch are read at every level, an organization's included, or reported NOT VERIFIED ([#211](https://github.com/brandonifco/rules-factory/issues/211)) |
| `rails` | `--apply` | implemented | creates the labels and a ruleset named `rules-factory-agent-rails`, and restricts merging to merge commits; idempotent, and it never writes another ruleset |
| `provenance` | — | implemented | re-produce in a scratch copy and name every field that does not match |
| `provenance` | `--engine` | implemented | the engine directory |
| `provenance` | `--package` | implemented | default: `Id@Version` from `provenance.json` |
| `verify` | — | implemented | provenance, then restore if the engine has no lock files, then the engine's own gate |
| `verify` | `--engine` | implemented | the engine directory |
| `verify` | `--package` | implemented | default: `Id@Version` from `provenance.json` |
<!-- factory-cli-status:end -->

### What the factory exits with

A caller that reads only `$?` must be able to tell what happened. There are four outcomes, and
they are four codes:

| Exit | Meaning |
|---|---|
| `0` | every step passed. For `produce`, that means the engine was verified: built and tested |
| `1` | a step refused or failed. Nothing was produced, and `--out` is as it was |
| `2` | a usage error |
| `3` | **NOT VERIFIED**: the command wrote its output but proved nothing about it. Today that is exactly `produce --no-verify` |

3 is not a pass and not a failure, and it is not new here: `engine-gate.py posture` already exits
3 when a corpus cannot be verified under its declared posture
([0013](docs/decisions/0013-verification-posture-belongs-to-the-corpus.md)), and so do
`examples/hoyle-blind-rebuild/check-rebuild.py` and `check-target.py`. `--no-verify` remains a
legitimate, documented mode — a machine without the SDK the engine pins, or the first produce of
an overlay whose tests cannot exist yet — so a caller that means to skip verification accepts
exactly 3 and lets every other code through, the way `scripts/validate.sh` accepts 3 from
`posture`:

```sh
status=0
python3 tools/factory produce … --no-verify || status=$?
[ "$status" -eq 3 ] || exit "$status"      # 3 is the intended outcome here; 0 and 1 are not
```

What never happens again is `NOT VERIFIED` on stdout and `0` in `$?`.

### What a verified `produce` proves

- **The inputs.** The package is a map package with its checker and deterministic verification
  record inside. The record's map, manifest and checker digests match those actual package members,
  and every cited corpus supplied to intake re-derives to the same sourceId/hashDerivation/contentHash
  identity the package says its publish gate verified ([0048](docs/decisions/0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md)).
  The map is in a schema version this factory reads. Every cited corpus is public domain or openly
  licensed ([0028](docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)).
  The factory's own `check-map.py --phase consumer` then passes on the packaged map.
- **The build.** `verify` recomputes provenance, restores (writing the lock files the first
  time, and re-locking them when the run changed the generated pins, as a map version bump
  does), then runs the engine's own gate, `scripts/validate.sh full`: the SDK pin, a locked
  restore, the overlay merge and the packaged consumer checker, the corpus hash under its
  posture, every `*.g.cs` equal to a fresh regeneration, format, and a `-warnaserror` build and
  tests in Debug and Release, with evidence that the tests ran: the result files are counted by
  *executed* outcomes, never by tests discovered, and every test project must have executed a test
  in every target framework, so a skipped suite or a framework that stopped running is a failure
  and not a number ([#337](https://github.com/brandonifco/rules-factory/issues/337)). A refusal or failure at any step
  leaves `--out` as it was.
- **Which SDK it proves.** For local runs only, `FACTORY_DOTNET_SDK_OVERRIDE` runs restore and the
  gate on another installed SDK, by re-pinning `global.json` for exactly as long as each takes —
  otherwise a machine without the pinned SDK could run neither. `global.json` is a managed file the
  gate hashes against the record, so that substitution is *declared* to the gate and proved there:
  the bytes it was re-pinned from must hash to what `provenance.json` records, and the file on disk
  must be those bytes with the SDK version replaced and nothing else. The run then says which SDK it
  actually verified on, in the gate's own steps and in the line that ends it, and never reads as a
  proof of the pinned toolchain. CI refuses the override, where a green run must mean the pinned SDK
  ([0054](docs/decisions/0054-a-verification-context-is-declared-and-proved-never-exempted.md)).
- **The tree it is a proof of.** The gate runs on a staging copy of `--out`, so what it proves is
  that copy, and a verified commit is held to both halves of that handoff. The copy must still be
  the tree the gate built and tested: `verify` notes every input of it immediately before the gate
  runs, and a commit whose copy no longer holds them is refused — so a test that writes into the
  engine it is testing, or leaves a writer running, refuses the run instead of being committed as
  verified ([#370](https://github.com/brandonifco/rules-factory/issues/370)). And `--out` must
  still hold the source and build inputs the copy was made from: a verified commit compares them
  all, not only the paths the run writes, and is refused before anything is written when one has
  moved, naming each path ([#335](https://github.com/brandonifco/rules-factory/issues/335)). An
  edit made in `--out` while `produce` ran is kept — nothing is written over it — and `produce` is
  run again to verify the engine with it. A source in `--out` that is, or lies under, a symlink is
  refused as well: a link's bytes can change between the check and the commit, and can be outside
  `--out` altogether, so no comparison of them supports the claim. Build output is not an input and
  refuses nothing — `bin` and `obj` at any depth, and `artifacts` and `TestResults` at the root of
  the engine, where the SDK writes them rather than wherever the name appears. `--no-verify` builds
  nothing and claims nothing about a build, so it is held only to the paths it writes.
- **The record.** `provenance.json` names the factory commit, the package and corpus hashes, the
  kernel version, the hash of every recipe file and generated file, the managed files at their
  recipe versions, and the bytes of every file the build reads as configuration. The recipe
  hashes are of bytes the named commit holds, or the run is refused: a symlink under
  `tools/factory`, or a git-ignored file there, would be hashed from a
  file no commit contains while `git status` — all `dirty` is — called the factory clean.
  Ignored bytecode is refused with the rest, because a `.pyc` whose header matches its source is
  what Python runs; the factory writes none of its own, so a second run in the same checkout is
  not refused for the first one's leavings.
  `factory provenance` re-produces the engine and names every field that no longer matches.
  The engine's own gate holds a narrower claim without the factory: `scripts/engine-gate.py
  provenance` hashes the recorded generated and managed files and every file of the overlay they
  were generated from, so an overlay edit never followed by a re-produce — leaving a record that
  hashes the overlay as it was before the edit — fails the gate, naming `tools/re-produce.sh`. An
  edit followed by a regeneration moves the generated hashes too; an edit followed by nothing moves
  only `buildInputs[overlay/<entry id>.json]`, so that comparison is the one that catches every
  form of it — the overlay's recorded paths and the directory's are compared as a **set**, so an
  entry's evidence added or removed is caught like one edited, and a record written before the
  split is refused rather than compared against nothing
  ([0018](docs/decisions/0018-every-file-the-factory-writes-has-one-owner.md)). It compares and
  never writes: only `produce` authors that record.

CI proves this on every pull request. The steps are
[`tools/validate-repo.py`](tools/validate-repo.py)'s, and
[`scripts/validate.sh`](scripts/validate.sh) is the wrapper that asks for all of them
(`--full`). The `validate` job asks a pull request's own diff what it owes
(`--changed --base <sha>`); a push to `main` and a weekly schedule ask for `--full`, and the
schedule is what reaches the one check no diff ever owes — the README's prose against the state
of the issues it cites, which needs the network. A tag asks `--release <map>`: every structural
check over every map, and only the map being published is packed. Every rule that narrows a run
is a row in a path table a test covers, and anything the table cannot place widens back to
`--full`
([0049](docs/decisions/0049-the-gate-can-say-which-of-its-checks-a-change-owes.md),
[0050](docs/decisions/0050-a-pull-request-is-gated-on-what-its-own-diff-owes.md)). The `engine`
job runs [`scripts/validate-engine.sh`](scripts/validate-engine.sh), which produces an engine
from the `hoyle-backgammon` package on the pinned SDK and verifies it.

Every artifact under `examples/` is named in
[`tools/evidence-lock.json`](tools/evidence-lock.json) with its SHA-256 and the parts of CI that
read it, and the gate holds the tree to that list in both directions on every run. The roles are
measured rather than declared — an audit hook records what each checker opens — and what they
found is in [docs/evidence-inventory.md](docs/evidence-inventory.md): 12.1 MB read by the checks,
2.5 MB packed into published packages, and 892 KB read by nothing at all
([0051](docs/decisions/0051-every-evidence-artifact-says-which-check-reads-it.md)).

### What it does not prove

- **That the map is right.** The checks a map passes read its shape and where its citations
  point, not whether an entry says what the corpus says. Mechanical checks caught 1 of 15
  injected comprehension errors, and the engine's tests caught none
  ([0014](docs/decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md)). A blind second
  mapping catches most of them, and every map in this repository must carry a review of its exact
  bytes ([0017](docs/decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)). The
  `hoyle-backgammon` map, which the `engine` job builds from, carries a legacy exemption rather
  than a review. What the second mapper was *given* is now staged by `tools/mapper stage` and
  recorded by digest, so an unredacted input is visible
  ([#223](https://github.com/brandonifco/rules-factory/issues/223)); paraphrase in a staged
  document is still nobody's check.
- **That a rule is implemented.** A produced engine answers each entry that is not
  `implemented` with a decline citing its locator. The rules themselves are hand-written
  handlers, and the backlog — the GitHub issues, and `factory backlog --render` — lists the ones
  still to write.
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
- **Anything, under `--no-verify`.** The engine is written without being built or tested, and the
  run says so twice and exits 3, NOT VERIFIED, so no caller can read it as a verified produce.
  Lock files the generated pins have moved past, in the version they resolve or the range they
  record as requested, are re-locked by `dotnet restore` alone, or the run is refused; they are
  never committed stale.

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
| Corpus maps — schema, checker, packages | this | maps of six corpus slices; `hoyle-backgammon`, `faa-part-107` and `srd-52-combat` published as packages; `tax-121-principal-residence` declares a package and has no `map/` tag, so it is unpublished |
| Corpus toolkit — adapters, locators, boundary policy | none | locator checkers for three citation grammars live here (page markers, eCFR sections, PDF-extracted text); no adapters |
| Domain packs — tabletop, legal | none | not implemented |
| Agent rails for produced engines | this | decided ([0029](docs/decisions/0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)), and they stay copied into each engine rather than being externalised — 204 KB of an engine that is 801 KB to 1378 KB, against losing offline verification, per-file provenance and per-file adoption ([0052](docs/decisions/0052-the-rails-stay-in-the-engine-that-runs-on-them.md)); emitted and enforced: the contract, the roles, the charters, the guard, the packets, dispatch, the PR contract, the recorded verdicts, `.github/agent-policy.json`, and `factory rails --apply`, which makes the three checks required. Proven on a real rule: `faa-part-107`'s `control-links-working` went issue to merge through them ([#157](https://github.com/brandonifco/rules-factory/issues/157)) |
| **Factory — intake, generation, gate, backlog, provenance, verify** | **this** | implemented; acceptance test ([#3](https://github.com/brandonifco/rules-factory/issues/3)) met 2026-09-16 |
| Produced engines | [`hoyle-backgammon`](https://github.com/brandonifco/hoyle-backgammon), [`faa-part-107`](https://github.com/brandonifco/faa-part-107), [`srd-52-combat`](https://github.com/brandonifco/srd-52-combat) | produced by the factory, with hand-written rule handlers; each engine's `provenance.json` names the factory and map versions it was built from ([evidence](examples/acceptance-4-5/EVIDENCE.md)) |
| Hand-built engines | `deckard`, `SRD_Combat` | built by hand, before the factory |

`hoyle-backgammon` was built by hand first and is now produced by the factory. Its generated
files, managed files and provenance are the factory's output. Its rules code, tests and extra
projects are engine-owned. `deckard` and `SRD_Combat` are still built by hand. They are what the
method was derived from. `deckard`'s corpus is commercial, so it stays hand-built and outside the
factory ([0028](docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)).

## The shape of a run

```
map package   a corpus map published as a .nupkg (0015, 0048): map, manifest, checker,\n              deterministic verification record binding those bytes to every cited corpus
corpus        each corpus the map cites, committed-copy, hashing to its manifest baseline
              (--corpus once per cited corpus; one map may cite several, decision 0039)
name          the engine's PascalCase name
        |
        v
    factory produce    intake, generation, gate, provenance,
                       verify (in a staging copy), write to --out (no commit)
        |
        v
engine        a .NET solution on RulesKernel: managed build policy, the kernel's
              determinism analyzers, engine-owned projects and overlay, generated
              *.g.cs tied to the map, the corpus
gate          scripts/validate.sh and the CI workflow that runs it
backlog       not a file in the engine: GitHub issues, one per entry still to
              build, in dependency order (factory backlog --create), rendered from
              the map and the overlay on demand (factory backlog --render)
provenance    factory commit, map package, corpus, kernel, recipe hashes, and the
              generated, managed, engine-owned and build-input files; "packs": []
rails         AGENTS.md, the roles, the three charters, the primary-checkout guard,
              dispatch, the entry and review packets, the pull request template and
              its policy check, the recorded verdict and its conformance gate, and
              .github/agent-policy.json, which the engine owns

not implemented: a domain pack as input
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
[docs/backlog.md](docs/backlog.md) for the scheme and the reasoning behind the ordering. How a
change to this repository is made, checked, finished and released is [AGENTS.md](AGENTS.md).
