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
| [TARGET.json](TARGET.json) | The frozen target, and the decisions still open |
| [check-target.py](check-target.py) | Re-derives every pin in TARGET.json from git objects, and optionally runs the tests |
| [build-brief.py](build-brief.py) | Builds the API contract, assembles the brief from pinned inputs, and scans it for leaks |
| [api-surface/](api-surface/Program.cs) | Prints a compiled assembly's public surface and XML documentation; reads metadata, never IL |
| [brief-source/](brief-source/README.md) | The brief's hand-written parts: its front page, [conventions.md](brief-source/conventions.md) and GET-FACTORY.sh |
| [brief/](brief/MANIFEST.json) | The assembled brief's engine-derived part and its manifest (the map, corpus and factory docs are rebuilt from pins, not committed) |
| [EQUIVALENCE.md](EQUIVALENCE.md) | The pass condition, and what counts as cheating |
| [check-rebuild.py](check-rebuild.py) | Runs the pass condition's scripted part against a rebuild |

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
- `GET-FACTORY.sh`: a shallow, blobless, sparse clone of rules-factory at `factory/v0.7.0` holding only
  `tools/factory/`, `tools/check-map.py` and `.gitignore`, with its remote removed. `factory produce`
  needs a clean git checkout of the tag to record provenance, and a full clone would include this
  directory. Tested: the clone is clean after running the factory, and its recipes digest is the tag's;
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
was removed.

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
is a copy; the rebuild's own gate is green; and the blindness rules were kept, checked by transcript
search where the harness allows and attested where it does not. `check-rebuild.py` run against the
target as its own "rebuild" passes the tests and provenance and fails the copy check, as it should.

## Decisions for Brandon

Each is recorded in TARGET.json `openDecisions`. The goal they are judged against: proving the factory
can rebuild an engine without copying it.

**H1. The API contract includes the public documentation, not only signatures.** The engine's doc
comments state conventions its tests pin exactly: the order legal plays are listed in, whose die is
thrown first, the pip numbering, what each ruling marks. With signatures alone a blind rebuild would
almost certainly fail the replay hash, the play-enumeration tests and every scripted-game test,
through guesses that have nothing to do with the factory. The cost is that the implementer reads the
target's design reasoning, though never its code. *Recommendation: keep the documentation.* It is what
any consumer of the package sees, and without it the test measures luck, not the factory.

**H2. `conventions.md` is written from the tests.** About 40 facts nothing else states: exception
message fragments, `Move.ToString`'s format, point names, what each entry point returns, how
`Game.Play` spends draws and decisions, the canonical record's terms (whose paragraph in decision 0006
was redacted), a word list the dice pack's names must avoid, and the textual shape the tests require
of hand-written declines. Without it, some 30 test methods would turn on guessing a format or a
message, for reasons unrelated to the rules. With it, the rebuild is less than fully blind. *Recommendation: keep it, publish it
with the evidence, and report it as help received.* The alternative, pre-registering those tests as
expected failures, would make "passes the tests" untrue.

**H3. Questions during the rebuild.** The brief lets the implementer ask in writing; answers become
disclosures and are counted. *Recommendation: allow it, with every answer published.* A silent
implementer who guesses from outside sources is worse evidence than one whose questions are on record.
Consider stating in advance that more than about ten answers makes the result "assisted" rather than
"blind".

**H4. No partial pass.** A rebuild passing 95% of cases does not meet the criterion. The tests pin
exact bytes (the replay hash, record serialisation, play order); a 95% rebuild may be one that fails
exactly those, which are the engine's contract with its callers. *Recommendation: all 560 or fail, with
the passing count reported either way.* A near miss is still a useful finding about the factory, and
should be written up as one, not as a pass.

**H5. The published map names three test methods and five test classes.** They sit in entry notes of
`RulesFactory.Maps.HoyleBackgammon` 6.0.0, which the build restores by hash and the tests assert by
version, so they cannot be redacted without changing the target. *Recommendation: accept them as
disclosed.* Names without bodies say little, and they record decided readings the map states anyway.
Separately, future maps should not name an engine's tests (a small method change).

**H6. Some tests read the engine's source text.** `MapCorrespondenceTests` inspects hand-written
`src/` files for how declines are constructed, and reads `corpus-map.overlay.json`. That constrains how
the code is written, not what it does. *Recommendation: keep the tests unmodified (that is the
criterion) and disclose the convention in conventions.md, as done.* Excluding those five methods would
be the first crack in "unmodified".

**H7. Target at `712e8ca` and factory `v0.7.0`, not `dab64e0` and `v0.6.0`.** `712e8ca` is `dab64e0` plus
a re-produce for RulesKernel 0.3.0, with no rule or test change, and `v0.7.0` is the newest tag and the
one the engine records. *Recommendation: accept.* Freezing `dab64e0` would force the rebuild onto an
older factory than the current one.

**H8. Blindness is attested, not enforced, unless the harness restricts network access.** Both
hoyle-backgammon and this directory are public. *Recommendation: run the implementer as a fresh agent
context with egress limited to nuget.org, the .NET SDK, documentation hosts and the one factory fetch,
keep its transcript, and search it for the target's name and every test name.* If egress cannot be
limited, the result should say "attested blind". The context that froze this target (this one) has read
the tests and cannot be the implementer.

**H9. Redaction is mechanical.** A whole paragraph or list item goes if it names a test or quotes a
seed or hash the tests pin, including the per-seed statistics in decisions 0008 to 0010 and the
correspondence-test bullet in 0010. Some redacted paragraphs also held useful design text.
*Recommendation: accept, and review the 26 logged redactions once.* Hand editing would be less
lossy and would make the redaction itself something to trust.

**H10. What is not compared.** `recordSha256` for the rulings, and provenance's `buildInputs` and
`engineOwned`, are the rebuild's own files and may differ. The copy check fails byte-identical files
and lists shared source lines for a reviewer, with no percentage threshold. *Recommendation: accept.*
A threshold would either flag coincidental short lines or excuse copying below it.

**H11. The pins were measured on SDK 10.0.111.** The factory pins 10.0.112, which is not installed
here; test counts, the API contract and the dry run used an overridden `global.json`. *Recommendation:
run the final judgement in CI or on a machine with 10.0.112, and treat a local 10.0.111 result as NOT
VERIFIED, as the scripts already do.*
