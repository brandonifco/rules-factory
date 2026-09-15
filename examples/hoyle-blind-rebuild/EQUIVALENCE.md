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
There is no partial pass: 559 of 560 cases is a fail, and the number that passed is reported beside the
verdict either way (Brandon, 2026-09-15, H4 in [README.md](README.md)). The verdict runs in CI on the
pinned SDK 10.0.112 ([judge-rebuild.yml](../../.github/workflows/judge-rebuild.yml), H11;
[RUNBOOK.md](RUNBOOK.md) step 5).

**The result's label.** Every pass or fail from this brief is "with a written interface", because the
brief carries `api-contract.md` with the engine's documentation and `conventions.md`, which counts as
help received (H1, H2). It is also "blind", or "assisted" if more than 10 written questions were
answered (H3).

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
factory at the tag, and `overlay-skeleton.json` with placeholder tests and records) gives
all 20 generated and 3 managed files byte-identical to TARGET's. P3 is reachable without the target.

**P4. Nothing is copied.** No file of the rebuild is byte-identical to a hand-written file of the
target's `src/` or `tests/` (generated, managed and the brief's verbatim build files excepted). The
script also prints every hand-written source line of the rebuild that occurs in the target's
hand-written source, ignoring whitespace, braces, usings and documentation, and the share they make.
That share is for the reviewer: short lines (`return false;`) coincide by chance, so it is not a pass
mark. The reviewer states in the evidence that the listed lines are not copying.

Run against the target itself as its own rebuild, the script passes P1 to P3 and fails P4 on 73
identical files with 100% shared lines, which is what it is for.

**P5. The rebuild's own gate.** In the rebuild's checkout, with the factory at the tag (judge-rebuild.yml checks it out):
`factory provenance --engine .` reports every field matching, and the rebuild's CI `validate` run for
the commit is green. Its first commit is exactly what `factory produce` wrote.

## Conditions attested

These cannot be proven by a script, so they are made checkable where possible and attested where not.

**A1. The implementer was blind.** Cheating is any of:

| Cheating | How it is checked or attested |
|---|---|
| Reading hoyle-backgammon (code, tests, issues, PRs, commits, CI logs, forks, mirrors, caches) | The implementer is a fresh agent context that has never read it (H8). It runs in the workspace of [RUNBOOK.md](RUNBOOK.md): under bubblewrap, the network reaches only NuGet, the .NET SDK, documentation and the model's API, through a logging allowlist proxy, and the filesystem shows only the workspace. No github.com host is allowed, because the factory is pre-staged in the brief. Afterwards `search-transcript.py` searches the transcript and the network log. RUNBOOK.md section 2 states exactly what is enforced and what is only searched: an agent running outside the sandbox is searched, not confined. |
| Reading rules-factory beyond the brief: `examples/hoyle-blind-rebuild/` (this directory names every test), `examples/hoyle-backgammon/`, `tools/tests/`, issue #3 and its links | Invisible in the sandbox's filesystem, unreachable on its network, and searched for in the transcript. The staged factory is a shallow, blobless, sparse checkout with no remote, so it holds no other file's content and cannot fetch any. |
| Being told test names, test data or code by someone who has seen them | Every question and answer is written in `questions/`, and each answer passes `build-brief.py check-text` before it is handed over. All are published, and more than 10 answers labels the result assisted (H3). |
| Using a model or person with prior exposure to the target | The implementer is a context that did not take part in freezing the target or writing the brief. The target was created after the knowledge cutoff of the models in use (May 2026), and the implementer says whether it recognises the engine. |
| Copying the target's source | P4. |
| Editing the target's tests, or adding shims | P1 replaces `tests/` wholesale from git objects; `allowedShims` is empty. |

**A2. The brief handed over is the pinned one.** `build-brief.py scan` passes on it: every file
matches `MANIFEST.json`, the staged factory is a clean tools-only checkout of the tag, and the
manifest's sha256 equals TARGET `brief.manifestSha256`. Answers to questions are not added to the
brief; they are published with the result (A3).

**A3. The evidence is published.** A rules-factory pull request adds `EVIDENCE.md` to this directory:
the rebuild's repository and commit, the judge-rebuild run and its output (with the pass count and the
label), the transcript search results with every REVIEW line explained, the network log's refused
requests, whether the agent ran inside the sandbox, every question and answer, and the P4 reviewer's
statement. Criterion 1 is ticked on #3 only from that evidence.
