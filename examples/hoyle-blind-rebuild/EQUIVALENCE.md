# The pass condition for the blind rebuild

rules-factory#3, criterion 1, as Brandon redefined it on 2026-09-15: an implementer who has never seen
`brandonifco/hoyle-backgammon`'s code or tests produces that engine from the factory, the published
map, and the owner's rulings and decisions, and it passes hoyle-backgammon's own tests, pinned at a
frozen commit.

The target is frozen in [TARGET.json](TARGET.json): hoyle-backgammon `712e8ca`, its `tests/` tree
`73b6952`, 189 test methods and 560 cases (280 per target framework), map
`RulesFactory.Maps.HoyleBackgammon` 6.0.0, factory `factory/v0.7.0`, ruleset 6, replay schema 4, and
the seeded replay's canonical-JSON sha256. [check-target.py](check-target.py) re-derives every pin
from git objects.

The rebuild **passes** when every condition below holds for one commit of the rebuild's repository.
There is no partial pass: 559 of 560 cases is a fail (decision H4 in [README.md](README.md)), and the
number that passed is reported beside the verdict, not instead of it.

## Conditions checked by a script

[check-rebuild.py](check-rebuild.py) `REBUILD_CLONE ENGINE_CLONE --commit SHA` runs P1 to P4 and
prints P5's commands.

**P1. The target's tests pass, unmodified.**
- The rebuild's commit is exported. Its `tests/` directory is deleted and replaced by the target's
  `tests/` tree from git objects at `712e8ca`, whose tree hash is `73b6952`. Nothing else is added,
  removed or changed. The allowed adapter shims are listed in TARGET `equivalence.allowedShims`, and
  the list is empty.
- With `CI=true`, on the SDK the factory pins (10.0.112): `dotnet restore --locked-mode` (the target's
  test lock files against the rebuild's package graph), `dotnet build -c Release -warnaserror`, and
  `dotnet test -c Release`.
- Every case passes; the cases per project and target framework equal TARGET's (262 and 18, on net8.0
  and net10.0); the methods that ran are exactly the 189 TARGET names. A run on another SDK is NOT
  VERIFIED, not a pass.

**P2. Factory provenance matches.** The rebuild's `provenance.json` records:
- factory `0.7.0`, commit `0697808`, `dirty: false`, and the recipes digest TARGET pins (which
  check-target.py recomputes from the tag's blobs);
- map `RulesFactory.Maps.HoyleBackgammon` 6.0.0 with the pinned nupkg sha256; kernel `RulesKernel`
  0.3.0; corpus `hoyle-1909` with its content hash and derivation; `randomness: seeded`; no packs;
- the six owner's rulings with the same id, entry, span, answer, ruledBy, ruledOn and record path.

Not compared, because they are the rebuild's own files: `recordSha256` (the rebuild writes its own
decision records at the same paths), `buildInputs` and `engineOwned` (lock files and project files it
writes itself).

**P3. Generated and managed files are identical.** `provenance.json`'s `generated` list (20 files:
every `*.g.cs`, `RulesFactory.Packages.g.props`, `scripts/`, the workflow, `backlog/README.md` and the
corpus copy) and `managed` list (`Directory.Build.props`, `NuGet.config`, `global.json`) equal TARGET's
path for path and sha256 for sha256, and every one of those files at the commit hashes to what is
recorded. Because `Registry.g.cs`, `Rulings.g.cs` and `CorrespondenceTests.g.cs` are generated from
the overlay, this also holds the rebuild's overlay to the target's statuses and rulings.

Checked on 2026-09-15: running `factory produce` from the brief alone (the map package, the corpus, the
factory from `GET-FACTORY.sh`, and `overlay-skeleton.json` with placeholder tests and records) gives
all 20 generated and 3 managed files byte-identical to TARGET's. P3 is reachable without the target.

**P4. Nothing is copied.** No file of the rebuild is byte-identical to a hand-written file of the
target's `src/` or `tests/` (generated, managed and the brief's verbatim build files excepted). The
script also prints every hand-written source line of the rebuild that occurs in the target's
hand-written source, ignoring whitespace, braces, usings and documentation, and the share they make.
That share is for the reviewer: short lines (`return false;`) coincide by chance, so it is not a pass
mark. The reviewer states in the evidence that the listed lines are not copying.

Run against the target itself as its own rebuild, the script passes P1 to P3 and fails P4 on 73
identical files with 100% shared lines, which is what it is for.

**P5. The rebuild's own gate.** In the rebuild's checkout, with the factory from `GET-FACTORY.sh`:
`factory provenance --engine .` reports every field matching, and the rebuild's CI `validate` run for
the commit is green. Its first commit is exactly what `factory produce` wrote.

## Conditions attested

These cannot be proven by a script, so they are made checkable where possible and attested where not.

**A1. The implementer was blind.** Cheating is any of:

| Cheating | How it is checked or attested |
|---|---|
| Reading hoyle-backgammon (code, tests, issues, PRs, commits, CI logs, forks, mirrors, caches) | The implementer runs as a fresh agent context that has never read it, with network access limited to nuget.org, the .NET SDK and documentation hosts, and one fetch of rules-factory by `GET-FACTORY.sh`, where the harness can enforce an allowlist (decision H9). Its tool-call transcript is kept and searched for `hoyle-backgammon`, `github.com/brandonifco` other than the factory fetch, and every hand-written test name in TARGET. Where egress cannot be enforced, the implementer signs a statement and hands in a reading log. |
| Reading rules-factory beyond the brief: `examples/hoyle-blind-rebuild/` (this directory names every test), `examples/hoyle-backgammon/`, `tools/tests/`, issue #3 and its links | Same transcript search. `GET-FACTORY.sh` makes a shallow, blobless, sparse clone and removes its remote, so the checkout cannot fetch those files later. |
| Being told test names, test data or code by someone who has seen them | Every question and answer during the rebuild is written, added to the brief as a disclosure, and counted in the evidence (decision H3). |
| Using a model or person with prior exposure to the target | The implementer is a context that did not take part in freezing the target or writing the brief. The target was created after the knowledge cutoff of the models in use (May 2026), and the implementer says whether it recognises the engine. |
| Copying the target's source | P4. |
| Editing the target's tests, or adding shims | P1 replaces `tests/` wholesale from git objects; `allowedShims` is empty. |

**A2. The brief handed over is the pinned one.** `build-brief.py scan` passes on it, and its
`MANIFEST.json` sha256 equals TARGET `brief.manifestSha256`. Every disclosure made later is a new
manifest, pinned by a pull request before it is handed over.

**A3. The evidence is published.** A rules-factory pull request adds `EVIDENCE.md` to this directory:
the rebuild's repository and commit, `check-rebuild.py` output in full, P5's output and CI link, the
transcript search results, the reading log, every disclosure with its count, and the P4 reviewer's
statement. Criterion 1 is ticked on #3 only from that evidence.
