# A blind rebuild of hoyle-backgammon

rules-factory#3, criterion 1, as Brandon redefined it on 2026-09-15. It replaces rebuilding deckard
from the licensed SR6 corpus, which was dropped (closed PR #143).

> An implementer who has never seen `brandonifco/hoyle-backgammon`'s code or tests produces that
> engine from the factory, the published map, and the owner's rulings and decisions. It must pass
> hoyle-backgammon's own tests, pinned at a frozen commit.

This directory is step one: the frozen target, the blind brief, and the pass condition. Nothing here
implements the engine. **An implementer may not read this directory**: `TARGET.json` names every test.

| File | What it is |
|---|---|
| [TARGET.json](TARGET.json) | The frozen target, and Brandon's decisions of 2026-09-15 |
| [check-target.py](check-target.py) | Re-derives every pin in TARGET.json from git objects, and optionally runs the tests |
| [build-brief.py](build-brief.py) | Builds the API contract, assembles the brief from pinned inputs, and scans it for leaks |
| [api-surface/](api-surface/Program.cs) | Prints a compiled assembly's public surface and XML documentation; reads metadata, never IL |
| [brief-source/](brief-source/README.md) | The brief's hand-written parts: its front page and [conventions.md](brief-source/conventions.md) |
| [brief/](brief/MANIFEST.json) | The assembled brief's engine-derived part and its manifest (the map, corpus and factory docs are rebuilt from pins, not committed) |
| [EQUIVALENCE.md](EQUIVALENCE.md) | The pass condition, and what counts as cheating |
| [check-rebuild.py](check-rebuild.py) | Runs the pass condition's scripted part against a rebuild, with the pass count and the label |
| [REDACTIONS.md](REDACTIONS.md) | Every redaction in the brief with its reason, findings and removed text, for Brandon's review (H9) |
| [RUNBOOK.md](RUNBOOK.md) | The rebuild session: workspace, network allowlist and its enforcement, questions, transcript search, CI judgement |
| [sandbox/](sandbox/run-isolated.sh) | bubblewrap isolation with a logging HTTPS allowlist proxy, no sudo needed, and its probe |
| [search-transcript.py](search-transcript.py) | Searches the session's transcript and network log for signs it was not blind |
| [judge-rebuild.yml](../../.github/workflows/judge-rebuild.yml) | The final judgement in CI on SDK 10.0.112, dispatched by hand |

## The target

hoyle-backgammon `712e8cae8f5e13fae5666441f3bb1ddd9f4c3832`, main on 2026-09-15. That is `dab64e0`
(factory 0.6.0, the owner's rulings, ruleset 6, replay schema 4) plus hoyle-backgammon#19, which
re-produced the engine with factory 0.7.0 for RulesKernel 0.3.0 and changed no rule and no test.

| Pin | Value |
|---|---|
| `tests/` tree | `73b6952b0025d533541e38c8bfdf3d338b17a9d3` |
| Test methods | 189: 141 hand-written and 38 factory-generated in `HoyleBackgammon.Tests`, 10 in `Tabletop.Dice.Tests` |
| Test cases | 560: 262 and 18 per project, on each of net8.0 and net10.0; all pass |
| Map | `RulesFactory.Maps.HoyleBackgammon` 6.0.0, nupkg sha256 `50f03817…` |
| Factory | `factory/v0.7.0` = `0697808`, recipes digest `1ddbbfea…` (recomputed from the tag's blobs) |
| Kernel | `RulesKernel` and `RulesKernel.Randomness` 0.3.0 |
| Identity | ruleset `hoyle-1909-backgammon` 6, replay schema 4, `pcg_setseq_64_xsh_rr_32` |
| Replay | seed 20260914, canonical JSON sha256 `24af54b1…`, asserted in `EntryPointTests.cs` |
| Generated and managed files | 20 and 3, each with its sha256 |
| Owner's rulings | 6, on `must-play-whole-throw`, `bearing-off-eligible` and `game-value`, all fully ruled |

```
python3 examples/hoyle-blind-rebuild/check-target.py HOYLE_CLONE --factory . --nupkg MAP.nupkg \
    [--run-tests [--sdk-override 10.0.111]]
python3 examples/hoyle-blind-rebuild/check-target.py --self-check
```

Run locally on 2026-09-15: every pin matches, and `--run-tests --sdk-override 10.0.111` passes all 560
cases (NOT VERIFIED only because 10.0.112 is not installed here). `tools/tests/test_hoyle_blind_rebuild.py`
runs the self-check, mutates each pin against a synthetic engine repository, plants each kind of leak
in a synthetic brief, and refuses a synthetic rebuild with other provenance, edited generated files or
copied source, offline.

## The brief

`build-brief.py api` then `assemble` build it; `scan` re-checks one. What it holds:

**Given**
- the map package, byte for byte, and the corpus;
- the factory, pre-staged at `inputs/factory/rules-factory/` so the session needs no github.com access
  (H8): a shallow, blobless, sparse clone of `factory/v0.7.0` from the local rules-factory clone, holding
  only `tools/factory/`, `tools/check-map.py` and `.gitignore`, with no remote. `factory produce` needs a
  clean git checkout of the tag to record provenance, and a full clone would include this directory.
  `scan` re-checks the stage (commit, tag, clean, no remote, the tag's blobs, nothing else present).
  Tested: it stays clean after running the factory, and produces with the tag's provenance;
- rules-factory's `README.md` and `docs/` at the tag, redacted (4 blocks name the target's tests);
- `api-contract.md`: every public type and member of `HoyleBackgammon` and `Tabletop.Dice` with
  signature, nullability, default and constant values, and public XML documentation, from the compiled
  assemblies (2,220 lines; one documentation line redacted for naming a test class);
- `conventions.md`: what the tests observe that nothing else states (decision H2);
- `overlay-skeleton.json`: each entry's `status` and `implementedIn`, and the six rulings as data
  (id, span, answer, ruledBy, ruledOn, record) with `declines: []`;
- the solution, `Directory.Packages.props` and both `src` project files, verbatim;
- decision records 0001 to 0010, redacted (21 blocks: test names, and seeds and hashes the tests pin).

**Named and withheld**: the engine's code and tests, `corpus-map.overlay.json`'s `tests` and `mutation`
text, `MAP-FINDINGS.md`, the engine's `README.md`, rules-factory's `examples/` and `tools/tests/`, and
issue #3.

**Checked** (any finding fails the build, unless TARGET pins it as a disclosure with its count):
test method and class names; long integers and hex strings from the tests that no allowed source has;
eight consecutive words from a test file, a statement or comment of engine source, or the overlay's
mutation text, that no allowed source has. The map package and the factory's tools are scanned too,
because the implementer sees them. Redactions are logged in `MANIFEST.json` with the sha256 of what
was removed, and listed with their reasons and removed text in [REDACTIONS.md](REDACTIONS.md), outside
the brief.

**Disclosed and counted**: the published map package names 3 test methods and 5 test classes in entry
notes (10 occurrences), a comment in the engine project file names one test class, and
`conventions.md` is a disclosure as a whole. `MANIFEST.json` lists the disclosures by hash, not by
name.

Checked: `factory produce` from the brief alone, with the skeleton overlay and placeholder tests and
records, gives all 20 generated and 3 managed files byte-identical to the target's.

## The pass condition

[EQUIVALENCE.md](EQUIVALENCE.md). In short: the target's `tests/` tree replaces the rebuild's, with no
shims, and every one of the 560 cases passes on the pinned SDK with locked restore; provenance names the
same factory, map, kernel, corpus and rulings; every generated and managed file is identical; no file
is a copy; the rebuild's own gate is green; and the blindness rules were kept, enforced by the sandbox
of [RUNBOOK.md](RUNBOOK.md) where the agent runs inside it and searched in the transcript in every
case. The judgement runs in CI on SDK 10.0.112, reports the pass count either way, and labels the
result "with a written interface", and "blind" or "assisted". `check-rebuild.py` run against the
target as its own "rebuild" passes the tests and provenance and fails the copy check, as it should.

## Decisions (Brandon, 2026-09-15)

All eleven were decided by Brandon on 2026-09-15 and are recorded in TARGET.json `decisions`. None is
open. The goal they serve: proving the factory can rebuild an engine without copying it.

| # | Question | Decision |
|---|---|---|
| H1 | Does the API contract carry the engine's public documentation, or signatures only? | Keep `api-contract.md` with its documentation. The result is labelled "with a written interface". |
| H2 | Is `conventions.md`, written from the tests, allowed? | Keep it. It counts as help received, under the same label. |
| H3 | May the implementer ask questions? | Yes, in writing. Every question and answer is published with the result; more than 10 answers labels it "assisted". |
| H4 | Does a partial pass count? | No. All 560 cases pass or it fails, and the pass count is reported either way. |
| H5 | The published map 6.0.0 names 3 test methods and 5 test classes. | Accepted as a pinned disclosure. Future maps must not name an engine's tests. |
| H6 | Five tests read the engine's source text. | Accepted: the tests stay unmodified and the convention is disclosed in `conventions.md`. |
| H7 | Freeze `712e8ca` with `factory/v0.7.0` rather than `dab64e0` with `v0.6.0`? | Accepted. |
| H8 | How is blindness enforced? | A fresh agent, network restricted to NuGet, the .NET SDK, docs and the factory, and its transcript searched afterwards. The factory is pre-staged in the brief, so no github.com access is needed. [RUNBOOK.md](RUNBOOK.md) says how, and what is and is not enforced on this machine. |
| H9 | Mechanical, logged redaction. | Brandon reviews the 26 redactions himself, from [REDACTIONS.md](REDACTIONS.md). |
| H10 | `recordSha256`, `buildInputs` and `engineOwned` may differ; the copy check has no threshold. | Accepted. |
| H11 | Where does the final judgement run? | In CI on the pinned SDK 10.0.112: [judge-rebuild.yml](../../.github/workflows/judge-rebuild.yml). |

What the decisions changed here:

- **The label.** `check-rebuild.py --questions` prints "with a written interface", and "blind" or
  "assisted".
- **The pass count.** It prints the count either way.
- **Answers.** Each answer passes `build-brief.py check-text` before it is handed over.
- **The factory.** It is pre-staged in the brief, and `GET-FACTORY.sh` is gone.
- **The review.** `build-brief.py assemble --review` writes REDACTIONS.md.
- **The session.** RUNBOOK.md, `sandbox/` and `search-transcript.py` are new.
- **The judgement.** `judge-rebuild.yml` runs it in CI.

**Enforcement finding (RUNBOOK.md section 2).** On this machine, without sudo, bubblewrap confines a
process to the workspace, with network only through the logging allowlist proxy. Tested: NuGet and the
docs are reachable, github.com and every other host are refused, a bypass of the proxy reaches nothing,
`/home` is invisible, and a real `dotnet restore` succeeds inside. The mechanism does not confine an
agent that runs outside it. This session's host, the desktop app, cannot be started inside it, and no
Claude Code CLI is installed here, so an agent running inside was not tested. To enforce it for the
agent too, Brandon must install the CLI, start it through `run-isolated.sh` and log in inside; the
exact steps are in RUNBOOK.md. Otherwise the transcript search is the check, and the evidence says so.
