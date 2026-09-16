# Evidence: criteria 4 and 5 of the acceptance test

The last two acceptance criteria of [#3](https://github.com/brandonifco/rules-factory/issues/3):

> - All three outputs carry provenance naming the factory version, corpus identity, packs and
>   recipe hashes
> - The factory validates each output before declaring success

Run on 2026-09-16, from clean clones, on a machine with .NET SDK 10.0.111 and 8.0.130. The pinned
SDK is **10.0.112**, which is not installed here, so every step that builds ran under
`FACTORY_DOTNET_SDK_OVERRIDE=10.0.111` and says so in its own output. CI runs the same checks on
the pinned SDK (`validate-engine.sh` refuses the override when `CI=true`).

**Result: both criteria are met. Three limits are named below rather than papered over, and one
of them is a hole in what "success" proves.**

## The outputs

Shadowrun/`deckard` was dropped when licensed rules were ruled out
([0028](../../docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)), so the three
outputs of #3 are one board game, one federal regulation and one modern licensed-open rulebook.
`hoyle-blind-rebuild` is a fourth produced engine — criterion 1's blind rebuild — checked here
too, but it is a second engine over the *same* corpus and map as `hoyle-backgammon` and does not
stand in for one of the three.

| Output | Repository | Commit checked | Domain |
|---|---|---|---|
| Board game | [`hoyle-backgammon`](https://github.com/brandonifco/hoyle-backgammon) | `712e8ca` | *Hoyle's Games Modernized* (1909), backgammon |
| Federal regulation | [`faa-part-107`](https://github.com/brandonifco/faa-part-107) | `4f0ab29` | 14 CFR Part 107, as of 2026-01-01 |
| Third domain | [`srd-52-combat`](https://github.com/brandonifco/srd-52-combat) | `59904e2` | SRD 5.2.1 Combat, pp. 13–16, CC-BY-4.0 |
| (fourth, criterion 1) | [`hoyle-blind-rebuild`](https://github.com/brandonifco/hoyle-blind-rebuild) | `2b29dc5` | the blind rebuild of `hoyle-backgammon` |

All four were produced by the factory at tag **`factory/v0.7.0`**, commit
`069780809543a66d5556d713e337d850ef405b41`, **not dirty**.

---

# Criterion 4 — the record, and that it is true

## What each record names

Every field below is read out of the committed `provenance.json` of the commit in the table above.
`provenanceFormat` is 3 in all four (`2` added `buildInputs` (#69), `3` added `managed` and
`engineOwned` (#72)).

| | `hoyle-backgammon` | `faa-part-107` | `srd-52-combat` | `hoyle-blind-rebuild` |
|---|---|---|---|---|
| `factory.version` | 0.7.0 | 0.7.0 | 0.7.0 | 0.7.0 |
| `factory.commit` | `0697808…` | `0697808…` | `0697808…` | `0697808…` |
| `factory.dirty` | `false` | `false` | `false` | `false` |
| `map.packageId` | `RulesFactory.Maps.HoyleBackgammon` | `RulesFactory.Maps.FaaPart107` | `RulesFactory.Maps.Srd52Combat` | `RulesFactory.Maps.HoyleBackgammon` |
| `map.version` | 6.0.0 | 4.0.0 | 2.0.0 | 6.0.0 |
| `map.nupkgSha256` | `50f03817…e053a8` | `0cd6dc3c…78a378` | `b4d20a82…12f6cf` | `50f03817…e053a8` |
| `map.files` | map, manifest, checker (3 hashes) | 3 | 3 | 3 |
| `corpus.sourceId` | `hoyle-1909` | `cfr-14-107` | `srd-5.2.1` | `hoyle-1909` |
| `corpus.contentHash` | `5d505fa9…40645e` | `80f6bc4b…7ce35e` | `c55926cb…a075b100` | `5d505fa9…40645e` |
| `corpus.hashDerivation` | `gutenberg-plain-text-including-boilerplate` | `ecfr-versioner-xml` | `srd-5.2.1-pdftotext-24.02.0-page-marked` | `gutenberg-plain-text-including-boilerplate` |
| `corpus.asOf` | `null` (undated) | `2026-01-01` | `null` (undated) | `null` (undated) |
| `corpus.recomputed` | `true` | `true` | `true` | `true` |
| `kernel` | `RulesKernel` 0.3.0 | 0.3.0 | 0.3.0 | 0.3.0 |
| `randomness` | `seeded` | `none` | `seeded` | `seeded` |
| `packs` | `[]` | `[]` | `[]` | `[]` |
| `recipes.digest` | `1ddbbfea…7ed0a` | same | same | same |
| `recipes.files` | 17 | 17 | 17 | 17 |
| `generated` | 20 files, hashed | 56 | 36 | 20 |
| `managed` | 3, with `recipeVersion` and hash | 3 | 3 | 3 |
| `engineOwned` | 7 | 7 | 7 | 7 |
| `buildInputs` | 11, hashed | 7 | 7 | 11 |
| `rulings` | 6 | *absent* | 5 | 6 |

`corpus.recomputed: true` means intake derived the content hash from the corpus bytes under the
named derivation and it matched the map's baseline — it was not copied out of the map. The
`recipes.digest` is one value across all four because the factory commit is the same one, and the
digest is `sha256sum`-format over the 17 recipe files (`tools/factory/*` plus
`tools/check-map.py`).

**Three things the table says plainly, none of them papered over.**

1. **`packs: []` everywhere.** No rule packs exist yet, so the "packs" half of criterion 4 is
   satisfied by a field that truthfully says *none*, recorded rather than omitted
   (`provenance.py`: "`packs` — `[]`: no rule packs exist yet, and the empty list says so rather
   than omitting it"). Nothing here proves the field carries pack identity once packs exist,
   because nothing here has a pack.
2. **`faa-part-107` records no `rulings`, and that is correct.** `rulings` is present only when
   the engine's `corpus-map.overlay.json` carries an owner's ruling
   ([0027](../../docs/decisions/0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md)); Part 107's
   overlay carries two implemented entries and no ruling, so there is nothing to record. The field
   was introduced in `factory/v0.7.0` (`df6326c`), the version all four engines were produced by,
   so no engine here is missing it for being old.
3. **`corpus.asOf` is `null` for the two undated corpora** — a 1909 Gutenberg text and the SRD PDF
   have no effective date. The one corpus where it applies, the eCFR XML, records `2026-01-01`.

## That the record is true of the engine as it stands

`factory provenance --engine <dir>` re-produces the engine in a scratch copy from the same package
and the engine's committed corpus and names every field that does not match; it also hashes each
recorded generated and managed file on disk and re-applies the build-input rule, so a hand edit is
caught even where re-producing would undo or refuse it.

Run at the factory version each engine records (`factory/v0.7.0`, `0697808`), each engine a fresh
clone:

```
$ git clone https://github.com/brandonifco/rules-factory.git factory-v0.7.0
$ git -C factory-v0.7.0 checkout factory/v0.7.0      # 0697808, clean
$ git clone https://github.com/brandonifco/hoyle-backgammon.git
$ git clone https://github.com/brandonifco/faa-part-107.git
$ git clone https://github.com/brandonifco/srd-52-combat.git
$ git clone https://github.com/brandonifco/hoyle-blind-rebuild.git
$ cd factory-v0.7.0
$ python3 tools/factory provenance --engine ../hoyle-backgammon
provenance of ../hoyle-backgammon: every field matches            # exit 0
$ python3 tools/factory provenance --engine ../faa-part-107
provenance of ../faa-part-107: every field matches                # exit 0
$ python3 tools/factory provenance --engine ../srd-52-combat
provenance of ../srd-52-combat: every field matches               # exit 0
$ python3 tools/factory provenance --engine ../hoyle-blind-rebuild
provenance of ../hoyle-blind-rebuild: every field matches         # exit 0
```

No SDK is needed: nothing is built. [`check-provenance.sh`](check-provenance.sh) is the same run
in one command — it clones each engine, reads `factory.commit` out of its own record, checks the
factory out at that commit, and runs the check:

```
$ examples/acceptance-4-5/check-provenance.sh /tmp/crit4

==> hoyle-backgammon
     engine at 712e8cae8f5e13fae5666441f3bb1ddd9f4c3832; produced by factory 0.7.0 (069780809543a66d5556d713e337d850ef405b41), dirty: False
provenance of /tmp/crit4/hoyle-backgammon: every field matches

==> faa-part-107
     engine at 4f0ab29c438d834c13b867b33de631284283f185; produced by factory 0.7.0 (069780809543a66d5556d713e337d850ef405b41), dirty: False
provenance of /tmp/crit4/faa-part-107: every field matches

==> srd-52-combat
     engine at 59904e2af7f80887390098a987764727a14e8c77; produced by factory 0.7.0 (069780809543a66d5556d713e337d850ef405b41), dirty: False
provenance of /tmp/crit4/srd-52-combat: every field matches

==> hoyle-blind-rebuild
     engine at 2b29dc5a08f63bf4f54144c8fc62d4fb8f7255f5; produced by factory 0.7.0 (069780809543a66d5556d713e337d850ef405b41), dirty: False
provenance of /tmp/crit4/hoyle-blind-rebuild: every field matches

check-provenance.sh: PASS -- every engine's record is true of the engine     # exit 0
```

## That the check is capable of failing

A check that always passes proves nothing, so each negative control below was run against a
throwaway copy of a clone and the engine put back afterwards.

**A hand edit to a generated file** — one comment line appended to
`src/FaaPart107/Generated/MapEntries.g.cs` of a produced engine:

```
--- verify [1/3] provenance
MISMATCH generated[src/FaaPart107/Generated/MapEntries.g.cs].sha256: recorded b61a4d35…, on disk 9e725b30…
factory: verify FAILED at stage provenance -- 1 provenance field(s) do not match what re-producing gives.
```

**A hand edit to a managed file** — one comment appended to `Directory.Build.props`; `produce`
refuses before generating anything:

```
factory: REFUSED -- Directory.Build.props is a managed file edited by hand: the bytes are no
version of the factory's recipe, so produce will neither overwrite the edit nor leave a stale
policy unnoticed. Pass --adopt <path> to make it the engine's own from now on, or --reset <path>
to replace it with the current recipe. Nothing was produced.
```

**An owner's ruling whose decision record is missing** — deleting
`docs/decisions/0007-brandons-rulings-on-six-open-questions-are-ruleset-version-seven.md` from a
copy of `srd-52-combat`, which its five rulings name:

```
$ python3 tools/factory provenance --engine ../srd-missing-record
MISMATCH produce refused to re-produce the engine, so nothing else was compared:
corpus-map.overlay.json breaks decision 0027: moving-through-creatures: ruling
'moving-through-creatures/two-or-more': record 'docs/decisions/0007-…-version-seven.md' is not a
file in the engine; the ruling's decision record must be committed with it; …(all five)…
provenance of ../srd-missing-record: 1 mismatch(es)                # exit 1
```

**An owner's ruling whose record was edited since** — the record restored and one line appended.
`recordSha256` is live, so the whole `rulings` section is a named mismatch:

```
MISMATCH rulings: recorded [… "recordSha256": "0120ca2799855ba3…" …],
               recomputed [… "recordSha256": "5f5141030af3f3d1…" …]
provenance of ../srd-missing-record: 1 mismatch(es)                # exit 1
```

**Verdict on criterion 4: met.** All three outputs (and the fourth engine) carry a
`provenance.json` naming the factory version and commit and that it was not dirty, the corpus's
identity, hash and derivation with the hash recomputed from the bytes, the map package id, version
and `.nupkg` hash plus the hash of the map, manifest and checker inside it, the kernel version, the
randomness the corpus declares, `packs`, the recipes digest over the 17 factory recipe files, and
hashes for every generated, managed and build-input file — and the owner's rulings with the hash
of each ruling's decision record, where the engine has any. Every field of every record was
re-derived and matched, and the check demonstrably fails when it should.

---

# Criterion 5 — the factory validates each output before declaring success

This is about the factory's own behaviour, not CI. The claim has three parts, and all three were
run.

## 1. A verifying `produce` runs the generated gate in its staging copy, and refuses to write `--out` if it fails

Every step of `produce` writes into a staging copy of `--out`; `verify` runs there, after
provenance is written and before anything is put in place, and `--out` is only written when it
passes (`transaction.py` #67, `verify.py` #70). Proven by producing a scratch engine, breaking it,
and producing again into the same `--out`.

The factory used here is a clean clone of `main` at `574fa86` (four commits past `factory/v0.8.0`,
so it records `factory 0.0.0-dev+574fa869b3a8` — the honest version string for an untagged
commit). The map is `RulesFactory.Maps.FaaPart107@4.0.0`.

**The engine produces and verifies:**

```
$ FACTORY_DOTNET_SDK_OVERRIDE=10.0.111 python3 tools/factory produce \
    --package RulesFactory.Maps.FaaPart107@4.0.0 --corpus examples/faa-part-107/part107.xml \
    --name FaaPart107 --out ../scratch-engine
…
Passed!  - Failed: 0, Passed: 51, … FaaPart107.Tests.dll (net10.0)
validate.sh full: PASS
ok   gate: scripts/validate.sh full passed on SDK 10.0.111 (FACTORY_DOTNET_SDK_OVERRIDE), not the pinned 10.0.112
wrote to …/scratch-engine: 89 added, 0 changed, 0 removed
added 2 packages.lock.json file(s) written by restore: review and commit them
produced FaaPart107 in ../scratch-engine, verified on SDK 10.0.111 by FACTORY_DOTNET_SDK_OVERRIDE, not the pinned 10.0.112
                                                                        # exit 0
```

**A test that fails at run time.** One hand-written xUnit test added to the engine's own test
project, asserting `1 == 2`. `--out` was hashed file by file before the run (89 files + the broken
test, manifest sha256 `b5216383…`) and again after:

```
$ FACTORY_DOTNET_SDK_OVERRIDE=10.0.111 python3 tools/factory produce … --out ../scratch-engine
--- verify [3/3] gate -- scripts/validate.sh full …
[xUnit.net] FaaPart107.Tests.DeliberatelyBroken.ThisTestFailsOnPurpose [FAIL]
Failed!  - Failed: 1, Passed: 51, Skipped: 0, Total: 52 - FaaPart107.Tests.dll (net10.0)
FAIL test Debug
factory: verify FAILED at stage gate -- scripts/validate.sh full failed; its output above names
the step. Nothing was produced.                                          # exit 1

$ python3 manifest.py scratch-engine            # after
90 files, manifest sha256 b5216383f167f752ce770d08ba0cc734dcfe80fd2d01a4c25cbe1e70af83d966
$ diff before.manifest after.manifest && echo IDENTICAL
IDENTICAL                                       # --out untouched, byte for byte
```

**A build that fails.** The same experiment with `Assert.True(false, …)`, which the xUnit
analysers reject under `-warnaserror`, refuses at the same stage one step earlier (`error
xUnit2020` → `FAIL build Debug` → `validate.sh full: FAIL`), and `--out` was again byte-identical
before and after (manifest `fd214882…` both times).

**The control:** deleting the broken test and re-producing passes again, and writes nothing,
which is what a re-produce of an unchanged engine should do:

```
validate.sh full: PASS
wrote to …/scratch-engine: 0 added, 0 changed, 0 removed
produced FaaPart107 in ../scratch-engine, verified on SDK 10.0.111 …      # exit 0
```

## 2. `factory verify --engine` re-runs the gate against a produced engine

Run against each of the four clones, at the factory version each records (`factory/v0.7.0`):

| Engine | Result | Tests that ran (per configuration, per framework) |
|---|---|---|
| `hoyle-backgammon` | `verify ../hoyle-backgammon: PASS` (exit 0) | 262 + 18 (`Tabletop.Dice.Tests`) |
| `faa-part-107` | `verify ../faa-part-107: PASS` (exit 0) | 78 |
| `srd-52-combat` | `verify ../srd-52-combat: PASS` (exit 0) | 271 |
| `hoyle-blind-rebuild` | `verify ../hoyle-blind-rebuild: PASS` (exit 0) | 91 + 5 |

```
$ cd factory-v0.7.0
$ FACTORY_DOTNET_SDK_OVERRIDE=10.0.111 python3 tools/factory verify --engine ../srd-52-combat
--- verify [1/3] provenance
ok   provenance: every field matches
--- verify [2/3] restore -- skipped: 2 lock file(s) present; the gate's locked restore holds the engine to them
--- verify [3/3] gate -- scripts/validate.sh full (locked restore, build -warnaserror and tests in Debug and Release, and the engine's other checks)
ok   SDK 10.0.111 (rollForward=disable)
ok   dotnet restore --locked-mode
ok   merge(RulesFactory.Maps.Srd52Combat@2.0.0, corpus-map.overlay.json) obeys 0015
ok   packaged check-map.py --phase consumer passes on the merged map
ok   RulesKernel.Randomness is reachable only as the corpus declares
ok   every corpus verified under its declared posture
ok   every *.g.cs matches a fresh regeneration (no hand edits)
ok   dotnet format --verify-no-changes
ok   build Debug (0 warnings) / test Debug / build Release / test Release
ok   every test an implemented entry names exists and ran (Debug, Release)
ok   the rails hold: read-only reviewers, no dangling citation, a readable policy
validate.sh full: PASS
verify ../srd-52-combat: PASS on SDK 10.0.111 by FACTORY_DOTNET_SDK_OVERRIDE, not the pinned 10.0.112
```

Provenance is stage 1 on purpose: everything after it runs code the factory generated, so the gate
is only trusted once the generated files are proven to be the factory's, byte for byte, and not a
hand-weakened copy.

## 3. `validate-engine.sh` runs both in CI, for every example map

[`scripts/validate-engine.sh`](../../scripts/validate-engine.sh) produces an engine from scratch,
re-produces it verifying, re-produces after the engine adds projects of its own, re-produces at a
bumped map version (which re-locks), recomputes provenance on the committed engine each time —
and then, at its last step, produces and verifies an engine for **every other example map with a
`map-package.json`**, gate and all. It also proves refusals CI must keep proving, including "a
missing or mis-typed handler for an implemented entry is a build error". It refuses
`FACTORY_DOTNET_SDK_OVERRIDE` when `CI=true`, so a green CI run means the pinned SDK 10.0.112.

## The refusal paths, run

| Refusal | How it was provoked | What the factory did |
|---|---|---|
| A dirty factory | one line appended to `tools/factory/provenance.py` in the factory clone | `REFUSED -- the factory working tree … has uncommitted changes, so provenance could not name what produced the engine; commit them, or pass --allow-dirty …. Nothing was produced.` (exit 1, before anything ran) |
| A failing test | an xUnit test asserting `1 == 2` in the engine's test project | `verify FAILED at stage gate … Nothing was produced.` `--out` byte-identical (above) |
| A failing build | `Assert.True(false, …)`, rejected by the analysers under `-warnaserror` | `FAIL build Debug` → `verify FAILED at stage gate … Nothing was produced.` `--out` byte-identical |
| A missing named test | in a copy of `faa-part-107`, the test method the overlay's `speed-limit` entry names, renamed | see below |
| Stale lock files, `--no-verify`, no SDK | `resolved` for `RulesKernel` edited to `0.2.0` in a lock file, `FACTORY_DOTNET=/nonexistent/dotnet` | `REFUSED -- --no-verify must re-lock the lock files that disagree with the generated pins in RulesFactory.Packages.g.props (src/FaaPart107/packages.lock.json: RulesKernel locked at 0.2.0, pinned at 0.3.0), and no .NET SDK can run here …; install the .NET SDK 10.0.112, then run `python3 tools/factory produce … --no-verify`. Nothing was produced.` (exit 1) |
| Stale lock files, verifying | the same edited lock file, a verifying produce | refused at the gate — but see the finding below |
| A hand-edited generated file | one comment appended to a `*.g.cs` | `verify FAILED at stage provenance` (criterion 4, above) |
| A hand-edited managed file | one comment appended to `Directory.Build.props` | `REFUSED` before generation (criterion 4, above) |
| A ruling whose record is missing or edited | the decision record deleted, then edited | `provenance … 1 mismatch(es)` (criterion 4, above) |

**The missing named test is the sharpest of these.** All 78 tests still passed, in both
configurations and both frameworks, and the gate still refused:

```
Passed!  - Failed: 0, Passed: 78, Skipped: 0, Total: 78 - FaaPart107.Tests.dll (net10.0)
     156 test(s) across 2 result file(s) actually ran
ok   test Debug
error: speed-limit: names 'SpeedLimitEntryPointTests.The_limit_resolves_as_printed_87_knots_and_100_miles_per_hour_citing_107_51_a',
       which no result file shows running -- renamed, deleted, skipped, or never a test
FAIL every test an implemented entry names exists and ran (Debug)
factory: verify FAILED at stage gate -- scripts/validate.sh full failed; its output above names the step.
```

An engine cannot quietly drop the evidence for a rule it claims to implement and stay green.

## What "declaring success" means today

The factory says so in exactly these ways, and nowhere else:

| Command | Success | Failure |
|---|---|---|
| `produce` (default) | last line `produced <Name> in <out>, verified` (plus the SDK-override clause when one was used), exit 0 | a `REFUSED --` or `verify FAILED at stage <stage>` line on stderr, exit 1, and `--out` untouched |
| `produce --no-verify` | `verification SKIPPED (--no-verify): the engine was not built or tested`, then `produced <Name> in <out>, NOT VERIFIED`, **exit 0** | as above, exit 1 |
| `verify --engine` | `verify <dir>: PASS`, exit 0 | `verify FAILED at stage <stage> -- …`, exit 1 |
| `provenance --engine` | `provenance of <dir>: every field matches`, exit 0 | one `MISMATCH …` line per field, then a count, exit 1 |
| the engine's own gate | `validate.sh full: PASS` | `FAIL <step>` then `validate.sh full: FAIL` |

There is no step that prints success while something failed: the gate's steps are printed `ok` /
`FAIL` / `skip … (depends on a step that failed)` individually and a single `FAIL` ends the run,
and both `produce` and `verify` stop at the first stage that fails.

**What "verified" does not mean, and the one hole worth naming.**

1. **`--no-verify` exits 0.** It writes an engine that was never built or tested, and says so
   twice in its output — but a caller reading only the exit code cannot tell it from a verified
   produce. That is the hole. It is bounded: such a run still refuses to commit lock files that
   disagree with the generated pins (proven above), and CI never uses the flag.
2. **"verified" means the gate passed, not that the engine implements anything.** The fresh
   scratch engine above was declared `verified` with 51 generated tests, no entry implemented and
   no rule logic at all — the gate says so in its own words (`no entry is implemented, so no named
   test was required (nothing here to prove yet)`, and the packaged checker's `2 ok, 0 failed,
   2 not verified`). Rule logic is the engine's own work and its evidence is the named tests, which
   the gate then enforces once an entry claims to be implemented.
3. **`FACTORY_DOTNET_SDK_OVERRIDE` is loud.** A run under it prints a `WARNING` and repeats the
   override on its last line, and is refused under `CI=true`. Every run in this file except the
   provenance recomputations used it, at SDK 10.0.111 rather than the pinned 10.0.112.
4. **A finding about locked restore.** In the stale-lock experiment with a verifying produce, the
   gate's `dotnet restore --locked-mode` printed `ok` even though `resolved` for `RulesKernel` had
   been hand-edited from `0.3.0` to `0.2.0`; the run was refused a step later, when the build could
   not find the `RulesKernel` namespace (`error CS0246`) and `validate.sh full: FAIL`. So the gate
   does catch a tampered lock file and `--out` stayed untouched, but it is the build that catches
   it, not the locked restore. Worth knowing before anyone reads `ok dotnet restore --locked-mode`
   as proof the lock files are the ones the pins resolve.

**Verdict on criterion 5: met.** A verifying `produce` runs the engine's own gate — locked
restore, the packaged consumer checker on the merged map, declared randomness, corpus posture,
regeneration equality, format, `-warnaserror` build and tests in Debug and Release on two target
frameworks, the named-test check and the agent rails — inside a staging copy, and writes `--out`
only when it passes; a failure leaves `--out` byte-identical, which was measured, not assumed.
`factory verify --engine` re-runs the same gate against a produced engine, and passed on all four
outputs. `validate-engine.sh` runs both in CI for every example map, on the pinned SDK.

---

## Reproducing this

```
# criterion 4, no .NET SDK needed (~2 minutes)
examples/acceptance-4-5/check-provenance.sh /tmp/crit4

# criterion 5, needs a .NET SDK (10.0.112 pinned; anything else via the override)
git clone https://github.com/brandonifco/rules-factory.git factory && cd factory
FACTORY_DOTNET_SDK_OVERRIDE=<your SDK> python3 tools/factory produce \
  --package RulesFactory.Maps.FaaPart107@4.0.0 --corpus examples/faa-part-107/part107.xml \
  --name FaaPart107 --out ../scratch-engine
# then break something in ../scratch-engine and run the same command again
FACTORY_DOTNET_SDK_OVERRIDE=<your SDK> python3 tools/factory verify --engine ../scratch-engine
```

The map packages come from nuget.org when they are not already in the NuGet global packages
folder. Hashing `--out` before and after a refused run is how "untouched" was measured: sha256 of
every file with `bin/`, `obj/`, `.git/`, `artifacts/` and `TestResults/` pruned.
