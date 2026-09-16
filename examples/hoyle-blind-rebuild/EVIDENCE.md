# Evidence: the blind rebuild of HoyleBackgammon

The result of rules-factory [#3](https://github.com/brandonifco/rules-factory/issues/3) criterion 1,
run on 2026-09-15 under [RUNBOOK.md](RUNBOOK.md) and judged by the conditions
[EQUIVALENCE.md](EQUIVALENCE.md) sets. This file is A3: the published evidence criterion 1 is ticked
from.

Criterion 1 is the one Brandon redefined on 2026-09-15 (TARGET.json `criterion`): a blind rebuild of
`hoyle-backgammon`, replacing "rebuild deckard from the licensed SR6 corpus", which was dropped when
PR #143 was closed. Issue #3's checkbox still carries the old wording.

**Result: PASS, "blind, with a written interface". 560 of 560 cases. P1 to P5 all met.**

| | |
|---|---|
| The rebuild | [brandonifco/hoyle-blind-rebuild](https://github.com/brandonifco/hoyle-blind-rebuild) |
| The judged commit | `baba6287f1ca71cb1afae35ed4980d5a0a0c928b` |
| The target | `brandonifco/hoyle-backgammon` at `712e8cae8f5e13fae5666441f3bb1ddd9f4c3832` |
| The judge run | [rules-factory run 35046509202](https://github.com/brandonifco/rules-factory/actions/runs/35046509202) (`judge-rebuild.yml` on `main`) |
| SDK | 10.0.112, the version the target's `global.json` pins, roll-forward disabled |
| Label | blind, with a written interface |
| Questions asked | none |

The rebuild's repository holds the implementer's five commits exactly as it left them. One further
commit (`2b29dc5`) was added afterwards **by the operator**, and adds a section to the top of
`README.md` saying what the repository is. It is not part of the judged commit and sits above it.

---

## What was frozen

[TARGET.json](TARGET.json), on 2026-09-15, before the brief was built:

| | |
|---|---|
| Engine | `brandonifco/hoyle-backgammon` `712e8ca`, branch `main` |
| Its `tests/` tree | `73b6952b0025d533541e38c8bfdf3d338b17a9d3` |
| Its `provenance.json` sha256 | `c171e5d35de4f1ebb935569fcbce2ee6b8005af18d313e2aeecf6dbb7538be4b` |
| Factory | tag `factory/v0.7.0`, commit `0697808`, not dirty, recipes digest `1ddbbfea…7ed0a` |
| Map | `RulesFactory.Maps.HoyleBackgammon` 6.0.0, nupkg sha256 `50f03817…e053a8` |
| Kernel | `RulesKernel` 0.3.0 |
| Corpus | `hoyle-1909`, content hash `5d505fa9…40645e`, Gutenberg plain text including boilerplate |
| Allowed shims | none (the list is empty) |
| Cases required | all |
| Judged on | SDK 10.0.112, in `.github/workflows/judge-rebuild.yml` |

`check-target.py` passed on the target before the brief was built, and was re-run while writing this
file: every pin matches (`check-target: pins match; tests not run: NOT VERIFIED` — it does not run the
suite itself; the judge run below does).

## What the brief held

70 files, assembled by [build-brief.py](build-brief.py). `MANIFEST.json`'s sha256 is
`da6726e61c3cbb3d8c179eccde0930c61aca082d5ac6a4388789a3dc19de8dcc`, which equals TARGET
`brief.manifestSha256` — **A2 holds**; re-checked against the handed-over copy while writing this
file.

- `inputs/map/` — the published map package, byte for byte as nuget.org serves it.
- `inputs/corpus/hoyle.txt` — Project Gutenberg's plain text of *Hoyle's Games Modernized* (1909),
  public domain.
- `inputs/factory/rules-factory/` — the factory pre-staged at the tag: a clean, shallow, blobless,
  sparse, remote-less checkout holding only the tools, so the session needed no github.com access.
- `inputs/factory-docs/` — rules-factory's `README.md` and `docs/` at the tag, redacted where they
  name the target's tests.
- `engine/api-contract.md` — every public type and member with its signature and documentation, and
  no code. Redacted where the documentation names a test.
- `engine/conventions.md` — what the tests observe that nothing else in the brief states.
- `engine/overlay-skeleton.json` — every entry's `status` and `implementedIn`, and the owner's
  rulings and declines.
- `engine/build-files/` — the solution and the engine-owned build files, verbatim.
- `engine/decisions/` — the owner's decision records 0001 to 0010, redacted where they name tests or
  quote test data.

Named but withheld: the target's `MAP-FINDINGS.md` and `README.md`, and rules-factory's `examples/`,
`tools/tests/` and everything outside the tools and docs the brief carries.

`api-contract.md` and `conventions.md` are why the label is **"with a written interface"** (H1, H2).
Every pass or fail from this brief carries it.

## The result: P1 to P5

All five are met. P1 to P4 and the provenance half of P5 come from the judge run; the CI half of P5
comes from the rebuild repository's own `validate`.

### P1 — the target's tests pass, unmodified

The rebuild is exported at the judged commit, its `tests/` deleted and replaced wholesale by the
target's `tests/` tree from git objects at `712e8ca`. No shims: the allowed list is empty. Then, with
`CI=true` on SDK 10.0.112: `dotnet restore --locked-mode`, `dotnet build -c Release -warnaserror`,
`dotnet test -c Release`.

```
ok   P1 the engine clone's tests tree is TARGET's
ok   P1 allowed shims (none are allowed)
ok   P1 the solution is HoyleBackgammon.slnx
ok   P1 dotnet restore
ok   P1 dotnet build
ok   P1 dotnet test
info P1 560 of 560 case(s) passed
ok   run: HoyleBackgammon.Tests cases per framework
ok   run: HoyleBackgammon.Tests every case passed
ok   run: HoyleBackgammon.Tests methods that ran are the methods in source
ok   run: Tabletop.Dice.Tests cases per framework
ok   run: Tabletop.Dice.Tests every case passed
ok   run: Tabletop.Dice.Tests methods that ran are the methods in source
ok   run: no test project TARGET does not name
```

**560 of 560.** The cases per project and target framework equal TARGET's (262 and 18, on net8.0 and
net10.0), and the methods that ran are exactly the 189 names TARGET records.

### P2 — factory provenance matches

```
ok   P2 factory version          ok   P2 corpus
ok   P2 factory commit           ok   P2 randomness
ok   P2 factory not dirty        ok   P2 packs
ok   P2 recipes digest           ok   P2 owner's rulings
ok   P2 map                      ok   P2 kernel
```

All six owner's rulings match on id, entry, span, answer, ruledBy, ruledOn and record path.

### P3 — generated and managed files are identical

```
ok   P3 generated files: paths
ok   P3 generated files: sha256 equal TARGET's
ok   P3 generated files at the commit hash to provenance.json
ok   P3 managed files: paths
ok   P3 managed files: sha256 equal TARGET's
ok   P3 managed files at the commit hash to provenance.json
```

20 generated files and 3 managed files, path for path and sha256 for sha256. Because `Registry.g.cs`,
`Rulings.g.cs` and `CorrespondenceTests.g.cs` are generated from the overlay, this also holds the
rebuild's overlay to the target's statuses and rulings.

### P4 — nothing is copied

```
ok   P4 no rebuild file is byte-identical to a hand-written target file
info P4 404 of 1018 hand-written source line(s) also occur in the target's hand-written
     source (39.7%); for review, not a pass mark
```

**The reviewer's statement.** The listed lines are not copying. All 200 flagged distinct lines were
read. They fall into four groups:

- **Public signatures the brief dictates (55).** Every long line on the list is a declaration whose
  exact text `engine/api-contract.md` supplies — `public static ImmutableArray<Move>
  MovesForDie(Position position, Player player, int die)`, `public readonly record struct Move(int
  From, int To, int Die, MoveKind Kind, bool TakesUpBlot)`, `public sealed record AssertedAnswer<T>(T
  Value, AssertedPosition Position)`, `public static bool HasReEnteredMidBearOff(...)`,
  `WhichCompartmentIsTheInnerTable`. Each was spot-checked and found in the contract. An engine that
  satisfies a written interface must reproduce that interface verbatim; this is exactly the help the
  "with a written interface" label declares, not evidence of copying.
- **Guard clauses (13).** `ArgumentNullException.ThrowIfNull(position);` and its siblings, which
  `conventions.md` requires and the analyzers enforce.
- **Trivial returns and control lines (41).** `return false;`, `return true;`, `break;`,
  `if (position.Men(player, pip) > 0)`, `var moves = ImmutableArray.CreateBuilder<Move>();`.
- **Short idiomatic fragments (91).** Single expressions and fragments of C# that coincide by chance
  in any two implementations of the same interface over the same data types.

No method body of any length coincides. The share is high because the interface is large relative to
the logic and the interface was given; it is a measure of how much the contract fixes, not of what
was taken.

### P5 — the rebuild's own gate

**`factory provenance`, with the factory at the tag.** In the judge run, the factory checked out at
`factory/v0.7.0` (`0697808`) against the rebuild at the judged commit:

```
provenance of /home/runner/work/_temp/rebuild-at-commit: every field matches
```

Re-run independently by the operator against a fresh clone of the published repository at
`baba6287`, with the factory at the same tag:

```
provenance of .: every field matches
```

**The rebuild's CI `validate` run.** Green for the judged commit:
[hoyle-blind-rebuild run 35046436767](https://github.com/brandonifco/hoyle-blind-rebuild/actions/runs/35046436767),
`validate` on `baba6287f1ca71cb1afae35ed4980d5a0a0c928b`. That workflow runs `./scripts/validate.sh
full`, which is the engine's own definition of acceptable. The operator's later README commit also
validates green.

The rebuild's first commit, `89ecf94`, is exactly what `factory produce` wrote.

## The questions

**None.** The implementer asked no question; `workspace/questions/` is empty. The threshold for
"assisted" is more than 10 answers, so the label stays **blind**. There is nothing to publish here
because nothing was asked or answered.

## The transcript search

The implementer ran outside the sandbox (see "Operator decisions" below), so its transcript is the
agent's own session log rather than one written inside the workspace. `search-transcript.py` was run
over it by the operator:

```
$ python3 examples/hoyle-blind-rebuild/search-transcript.py <the implementer's transcript>
search-transcript: FAIL (13 failure(s), 38 to review; 1 transcript(s))
```

**It reports FAIL, and every one of the 13 failures is benign.** Each was opened and read. They are
the search finding the implementer's *own output*, not anything it took in. Full list:

| # | Flag | What it actually is |
|---|---|---|
| 1-4, 7-8 | the target's test method `A_hit_pays_the_single_stake` (×4) | The implementer writing its own `tests/HoyleBackgammon.Tests/StakeTests.cs`, and the same name going into its own `corpus-map.overlay.json`. |
| 5-6, 9-10 | the target's test method `The_winner_of_a_hit_throws_first_in_the_game_next_following` (×4) | The implementer writing its own `tests/HoyleBackgammon.Tests/OutcomeTests.cs`, and one `Read` of that file straight back. |
| 11 | an action names `github.com` | The implementer writing its own `README.md`, which links `https://github.com/brandonifco/rules-factory` as the factory that produced the engine. A link written into a file, not a request. |
| 12 | an action names `hoyle-backgammon` | The implementer writing its own `READING-LOG.md`, whose "what was deliberately not read" section names the target in order to say it was not read. |
| 13 | an action names `hoyle-backgammon` | The implementer writing its own `STATEMENT.md`, whose rule 1 names the target in order to say it was not looked at. |

The 38 REVIEW lines are the same phenomenon: the class names `StakeTests`, `GeometryTests`,
`PositionTests` and `DieFacesTests` appearing in `Write` calls creating the implementer's own test
files of those names.

**Why the names converged.** The brief's `overlay-skeleton.json` gives every map entry's `status` and
`implementedIn`, and `conventions.md` fixes the naming convention: a test class named for the concept
and a method named as a sentence asserting what the corpus says. Two implementers following that
convention over the same map entries land on the same names. Two method names out of the target's 189
converged, and four class names out of its hand-written classes. Nothing in the transcript shows the
implementer reading a name; every occurrence is it writing one.

They are also **not** among the brief's nine pinned disclosures (H5) — the three method names and six
class names the published map package and the verbatim engine project file carry, which could not be
redacted because those files are pinned by hash. Those nine are
`A_blocked_forward_move_bears_off_from_the_highest_point_men_still_above_it`,
`A_point_held_by_the_entering_players_own_men_does_not_make_the_table_full`,
`Entry_is_permitted_on_a_point_the_entering_players_own_men_hold`, `BearingOffDetailTests`,
`EnterFromBarTests`, `FullTableSuspensionTests`, `GameValueTests`, `WholeThrowTests` and
`CitationTests`. None of them overlaps the six the search flagged, and none of them is flagged, so the
convergence is genuine convergence and not a disclosure being echoed back.

**Independent checks by the operator, beyond the script.** The implementer's transcript was audited
directly:

- Tool calls in the whole session: `Bash` 83, `Write` 55, `Read` 17, `Edit` 5, and two chapter
  markers. **`WebFetch`: 0. `WebSearch`: 0.** The implementer had no other network tool.
- No `Bash` command contains `curl`, `wget`, `gh`, `git clone`, `git fetch`, `nc` or `ping`. **Zero
  network-capable commands of any kind.**
- No `Read`, `Write` or `Edit` touched a path outside `/home/brandon/blind-rebuild/workspace`, the
  pinned SDK at `/home/brandon/blind-rebuild/dotnet`, and the session's own scratchpad. **Zero file
  operations elsewhere.**
- No `Bash` command names `target-clone`, `factory-clone`, `/home/brandon/hoyle-backgammon`,
  `/home/brandon/rules-factory` or `.claude/projects`. **Zero commands touching a forbidden path.**

This corroborates `READING-LOG.md`, which lists no URLs, and `STATEMENT.md` rule 4, which says no
network request was made. The only files read outside the brief are the four `RulesKernel` /
`RulesKernel.Randomness` 0.3.0 package files and the pinned SDK, all of which the brief's "also
allowed" clause permits, and all of which the reading log declares.

## The network log

`~/blind-rebuild/network-logs/` holds only `network.operator-test.jsonl` and
`proxy.operator-test.out`, from the operator's own sandbox probe on 2026-09-15. **There is no session
network log, because the allowlist proxy was not in the implementer's path — it ran outside the
sandbox.** No refused request is recorded for the session, and none could be. What stands in its
place is the tool-call audit above: the implementer made no network request that any log could have
recorded, because it invoked nothing that can make one.

## Operator decisions

Stated plainly, because they weaken what RUNBOOK.md section 2 describes and the reader should judge
the result knowing them.

1. **The rebuild ran outside the bubblewrap sandbox.** This is the material one. RUNBOOK.md section 2
   says: "the implementer is only confined if the agent runs inside too… For such a session,
   blindness is attested and searched, not enforced." That is this session. The implementer ran as an
   agent on the host, with its own file and shell tools, and was bound by its instructions rather
   than by a namespace. **Blindness here is attested and searched, not enforced.** The attestation is
   `STATEMENT.md` and `READING-LOG.md`; the search is `search-transcript.py` plus the four
   independent audits above. That is a weaker guarantee than the runbook's enforced arrangement, and
   nothing in this document should be read as claiming otherwise.
2. **The Claude Code CLI was installed by the operator** at
   `~/blind-rebuild/tools/.local/bin/claude`, per RUNBOOK.md section 2's step 1, so that an enforced
   run would be possible. It was not used to launch the implementer: the session ran in the desktop
   app, which cannot be started inside bubblewrap.
3. **The .NET 8 runtime was added alongside the pinned SDK** at `~/blind-rebuild/dotnet` (SDK
   10.0.112, runtimes 10.0.12 and 8.0.31). The tests target net8.0 as well as net10.0, and the
   10.0.112 SDK on its own cannot run the net8.0 cases. This affects
   the local run only; the judgement in CI installs the SDK from `global.json` and gets its runtimes
   from the runner image.
4. **The judgement was run in CI on SDK 10.0.112** (H11), which is the decision the runbook records.
   The local pre-check ran on 10.0.111 and is, by EQUIVALENCE.md's own rule, NOT VERIFIED rather than
   a pass. The CI run is the one that counts, and it is the one above.
5. **The rebuild repository was published** at `brandonifco/hoyle-blind-rebuild`, public, with the
   implementer's history intact, and given the same `protect-main` ruleset the other engines carry
   (deletion, non-fast-forward, pull request, required check `validate`), byte-identical to
   `brandonifco/faa-part-107`'s.

## What this does and does not show

It shows that the factory, the published map, the corpus, the owner's recorded rulings and a written
interface are together enough to rebuild the engine so that the original's own tests pass, without
the rebuilder seeing the original — subject to the attestation in decision 1.

It does not show that the map alone is enough. `api-contract.md` and `conventions.md` were given, and
P4's 39.7% is mostly their doing. A rebuild without a written interface is a different, harder
exercise, and is not what this is.
