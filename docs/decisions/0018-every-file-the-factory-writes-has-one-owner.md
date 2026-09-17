# 0018 — Every file the factory writes has one owner: generated, managed or engine-owned

## Status

Accepted — 2026-09-14. Records the fix for
[#72](https://github.com/brandonifco/rules-factory/issues/72), finding 5 of the September 2026
external review.

**Amended 2026-09-14** for [#94](https://github.com/brandonifco/rules-factory/issues/94): a
`produce` that changes the generated pins re-locks the engine's lock files. See
*Amendment — changed pins re-lock* below. The lock-file rows of the table changed; nothing else
did.

**Amended 2026-09-16** for the hole criterion 5 of
[#3](https://github.com/brandonifco/rules-factory/issues/3) named in
[`examples/acceptance-4-5/EVIDENCE.md`](../../examples/acceptance-4-5/EVIDENCE.md): a
`produce --no-verify` exits 3, NOT VERIFIED, never 0. See *Amendment — `--no-verify` is not a
success* below. Nothing about the three classes, the detection or the re-lock changed.

**Amended 2026-09-16** for [#151](https://github.com/brandonifco/rules-factory/issues/151): the
agent rails of [0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)
are rows in the table below — twenty managed, one engine-owned. Nothing about the three classes or
the detection changed. 0029 §5 records the one constraint the managed class puts on them: a
managed recipe's bytes are fixed per version, so a rail may not interpolate the engine's name or
its map.

**Amended 2026-09-16** for [#192](https://github.com/brandonifco/rules-factory/issues/192): an
engine that edits an engine-owned *input* must re-produce, and the gate now enforces it. See
*Amendment — an overlay edit is finished by a re-produce* below. No row of the table changes class,
and one managed row is added (`tools/re-produce.sh`).

**Amended 2026-09-17** for [#243](https://github.com/brandonifco/rules-factory/issues/243): the
backlog is no longer a file the factory writes, so `backlog/*.md` leaves the table. See
*Amendment — the backlog is a projection, not an output* below. No remaining row changes class.

**Amended 2026-09-17** for [#247](https://github.com/brandonifco/rules-factory/issues/247): the
engine's overlay is a directory, one file per entry, so the `corpus-map.overlay.json` row becomes
`overlay/*.json`. See *Amendment — the overlay is one file per entry* below. It stays
engine-owned; no row changes class.

## Amendment — an overlay edit is finished by a re-produce

`provenance.json` and `backlog/*.md` are **generated**, which by this decision means `factory
produce` is their only author. Implementing a backlog entry edits `corpus-map.overlay.json`, which
is engine-owned — and every one of those generated files is derived from it. Nothing in a produced
engine refreshes them: `scripts/engine-gate.py regenerate --write` rewrites the generated C# and
nothing else. So an implementation pull request carried a record hashing bytes that no longer
existed and a backlog still listing the entry as one to build, and `validate.sh full` passed
anyway. The live run of [#157](https://github.com/brandonifco/rules-factory/issues/157) on
`brandonifco/faa-part-107` merged at four stale hashes; steward review caught it, and it took an
owner's ruling and a second commit.

**So an engine that changes an engine-owned input re-produces, and `scripts/engine-gate.py
provenance` fails until it has.** The step is in `scripts/validate.sh` after the regeneration step,
and it is not guarded on the restore or the map: it reads only files in the repository, so it can
never legitimately degrade to a skip. Its failure names one command, `tools/re-produce.sh`, which
is a managed rail (0029) rather than a paragraph telling an operator to clone rules-factory and
assemble four arguments — a procedure with a trap in it, since cloning the factory's `main` instead
of the recorded commit silently rewrites the gate, the rails and the vendored generator into an
implementation pull request.

- **What the check compares, and why not more.** Every `generated` entry, every `managed` entry,
  and the overlay entirely — `buildInputs[overlay/*.json]`, as a set since #247, so a file added or
  removed is a mismatch as loudly as one edited — and no other build input. Adding a
  `PackageReference`, a project to the `.slnx`, or a version to `Directory.Packages.props` are
  legitimate engine-owned acts under this decision; making each of them require a re-produce
  before the gate goes green produces a gate people route around. Holding the whole of
  `buildInputs` is `factory provenance`'s job, where a real re-produce can tell a legitimate
  addition from drift. The overlay is different in kind: it is the *input to generation*, and it
  appears in `buildInputs` only because it happens to be engine-owned. This scoping is recorded
  here so it is a decision and not an omission.
- **The overlay comparison is the load-bearing one.** Hashing the recorded backlog files does not
  catch a stale backlog: the item file for an entry that has since been implemented is recorded
  and unchanged, so its hash matches. What catches it is that the overlay moved, which makes
  everything derived from the overlay older than the overlay.
- **The record is also checked for the factory's canonical serialisation** (`provenance.serialize`),
  so a hand edit that kept every hash true is still named.
- **A check that examines nothing is a failure.** A record listing no generated file, no managed
  file and no overlay fails, saying it examined nothing.

**Rejected: let the engine rewrite the record itself.** This is the issue's first option, and it
cannot be done. Four independent blockers, all in `tools/factory/provenance.py`:

1. `factory_state()` resolves the factory directory from `__file__`. In an engine that is
   `<engine>/scripts/factory`, so the engine's own HEAD would be written into `factory.commit` — a
   false value indistinguishable from a true one.
2. `recipes()` walks all of `tools/factory/` plus `tools/check-map.py`. An engine has only the five
   modules `gate.FILES` vendors.
3. `generated` is built by `provenance.Recorder`, which watches `open`, `replace` and `rename`
   while `produce` runs. Engine-side there is no run to observe.
4. Decisively, an engine can re-derive its `*.g.cs` but not `scripts/validate.sh`,
   `scripts/engine-gate.py`, `scripts/map-overlay.py`, `scripts/factory/*.py` or
   `.github/workflows/validate.yml` — all class generated, all hashed in the record. An engine-side
   rewrite would hash whatever is on disk and hand a fresh, matching SHA-256 to a hand-edited gate.
   A gate that re-blesses its own bytes proves nothing.

So the engine compares and never writes, and `tools/factory/backlog.py` is deliberately not
vendored into an engine and stays that way.

## Amendment — the overlay is one file per entry

`corpus-map.overlay.json` was **engine-owned**: one shared JSON object, keyed by entry id, holding
the three fields 0015 gives an engine. It is now `overlay/<entry id>.json`, one file per entry
([#247](https://github.com/brandonifco/rules-factory/issues/247), part B of the design decision on
[#242](https://github.com/brandonifco/rules-factory/issues/242)), and the row changes with it. The
class does not: an overlay file is the engine's, written once by whoever implements the entry and
never touched by a `produce` — except the one `produce` that migrates an engine to this layout.

**Why.** Every implemented entry appended to the one object, so two entry branches cut from the
same commit were *guaranteed* to collide in it, whatever else they touched. It was the last such
file after #243. What 0015 says an engine owns is unchanged; only where the bytes sit moved.

**Two things follow for this record.**

*The scaffold.* Nothing writes an empty overlay any more. `produce` used to write
`corpus-map.overlay.json` as `{}` when an engine had none; a directory has no equivalent, and an
engine that has implemented nothing has nothing to say. So `overlay/*.json` is the one engine-owned
row with no scaffold, and `provenance.json`'s `engineOwned` lists the files that are there rather
than the pattern. The gate's "a check that examines nothing is a failure" is then carried by
`provenanceFormat`, which is 4 from #247 on: a record written before the split describes a layout
the engine does not have, and is refused rather than compared against nothing.

*The retirement.* `corpus-map.overlay.json` joins `RETIRED`, and the migrating `produce` deletes it
— but the rule #243 wrote cannot authorise that deletion. That rule is "the engine's own record
hashed these bytes in `generated` or `managed`", and the overlay is in neither: the factory never
wrote the engine's evidence and cannot claim to have. What authorises this one is different in kind
and no weaker. The run **moved** the content, so before deleting anything it parses the bytes it is
about to delete and requires the `overlay/*.json` files beside them to hold every key and every
value (`ownership.WITNESSES`, `overlay.superseded_by_split`). An overlay those files do not account
for is kept where it is and named in the run's output, exactly as a hand-edited `backlog/notes.md`
is. Both answers are reached by reading the bytes; neither is reached from the pathname. The
engine's `tools/pr-policy.py` asks the same function the same question about the base commit's
bytes, so the run and the policy cannot disagree about who owned a file.

## Amendment — the backlog is a projection, not an output

`backlog/*.md` and `backlog/README.md` were **generated**: `factory produce` wrote them on every
run and `provenance.json` hashed each one. They are gone
([#243](https://github.com/brandonifco/rules-factory/issues/243), part A of the design decision on
[#242](https://github.com/brandonifco/rules-factory/issues/242)), and the row leaves the table.

**Why.** Nineteen of the twenty-seven files in a one-entry pull request were backlog files, and
each item states its position out of the total, so finishing any entry renumbered and rewrote
nearly all of them. Two entry branches therefore collided, with rename/rename conflicts, on twenty
files neither of them was about. Nothing read them: `factory backlog --create` files GitHub issues,
`tools/dispatch-agent.sh` dispatches from issues, `tools/entry-packet.py` assembles an assignment
from the map. The committed markdown was a rendering of what the issues already held.

**What replaces it.** `factory backlog --create` renders the items in memory from the map package
the record names, merged with `corpus-map.overlay.json`, and files them as issues exactly as
before — every body is byte-identical. `factory backlog --render --dir <engine>` prints the same
rendering as one Markdown document, or writes the files with `--to <directory>`. A rendering of the
overlay committed beside the overlay is the state this amendment removes, and the command must not
be the way it comes back, so a `--to` inside the engine is refused unless all three hold: it is not
the engine root; `git check-ignore` agrees the engine ignores **every file the run would touch** —
what it writes *and* the stale items it would delete, asked per file because an ignored directory
can hold a tracked child, and a deletion is a change to the engine as much as a write; and no
component of the path is a symlink, because git answers about the name and the write follows the
link. Each file is then opened `O_NOFOLLOW`, so a planted `README.md ->` anywhere fails the write
instead of going through it, and a platform whose `os` has no `O_NOFOLLOW` is refused rather than
quietly given the following write back. `O_NOFOLLOW` covers the final component; a parent directory
swapped for a link between the check and the write is not caught, which would take
descriptor-relative I/O the standard library does not offer portably.

**Migration.** The next `produce` removes a committed `backlog/` inside the staging copy, so the
removal is committed with the rest of the run or not at all (`transaction.py`), and the run prints
what it removed. No one-off migration command: an engine is already brought into step by
`tools/re-produce.sh` after every overlay edit, and a command that had to be remembered once per
engine would leave any engine that forgot it holding a `backlog/` its record no longer mentions.

**A retired pattern is not a licence to delete.** Two independent guards, because this is the only
part of `produce` that removes a file it did not just write:

- **By evidence.** A match is deleted only when the engine's own `provenance.json`, as it stood
  before the run, hashed that exact path in `generated` or `managed` *and* the bytes on disk are
  still that hash. The bytes are re-hashed rather than trusted from the record, for the same reason
  `recipe_versions` does not trust it. A hand-written `backlog/notes.md`, and an item somebody
  edited after the last produce, are left where they are — and **named in the run's output**, since
  a file under a pattern nothing maintains any more is something its owner has to be told about.
  Deleting by pathname alone was the first implementation of this and was wrong.
- **By structure.** `retired_conflicts()` refuses, before any deletion and in the tests, any RETIRED
  pattern that could match a path any row of the table can match. A retirement therefore cannot
  reach a generated, managed, adopted or engine-owned file however it is spelled — not merely
  unlikely, impossible. An adopted file fails the evidence guard too: `engineOwned` carries no hash.

  Overlap is decided **exactly**, which takes a **constrained grammar**: a retired segment is a
  literal, or `*`, or `*` and a literal suffix, and `check_retired_grammar` refuses anything else
  before any deletion. Inside it, `{name}` on the table's side reduces to `*` (an engine name is one
  segment's worth of text), so a retirement of `obsolete.md` does not collide with `{name}.slnx` —
  and `*.g.cs` against `*.cs` is a collision, which it is. The alternative, matching two globs
  against each other with `fnmatch` both ways, is wrong in both directions: it calls `{name}.slnx` a
  conflict with every root-level retirement, and it calls `a*.md` and `*b.md` disjoint when `ab.md`
  matches both. The grammar excludes the interior `*` that makes the second possible.

A file kept once is kept for good: the next `produce` writes a record that does not mention it, so
no later run can attribute it to the factory either. That is the trade, taken deliberately —
preserving a file somebody wrote costs an engine one path nothing maintains, named on every run;
deleting it costs somebody their work.

`tools/pr-policy.py` admits a retired path just as narrowly, and draws **the same line the remover
draws**: only as a **deletion**, and only when the bytes at that path in the base commit hash to
what the base commit's `provenance.json` recorded. The path's presence in the record is not enough
— a file generated once and hand-edited since is listed under its old hash, and the remover keeps
it, so a policy that went by name would have called somebody's deletion of somebody's work a
produce. Adding to, editing, or deleting an unattributed file under a retired pattern voids a claim
like any other hand-written change, and a base record that cannot be read admits nothing.

**What still catches a stale derived state.** `buildInputs[corpus-map.overlay.json]`. Hashing the
backlog never could catch a stale backlog, because an item file listing an entry someone has since
implemented is *unchanged*. The `generated` hashes do catch one form of an unfinished overlay edit
— one followed by `regenerate --write`, which leaves the `*.g.cs` differing from what the record
holds — but an overlay edited and nothing else run moves no generated byte, and the overlay
comparison is the only thing that sees it. Now that nothing else even appears to carry the case, it
is no longer conditional: a record with no overlay entry and an engine with no overlay on disk fails
`scripts/engine-gate.py provenance`, rather than passing on the strength of the generated hashes it
did compare — and printing that the overlay was among what it examined. A check that examined
nothing is a failure, including when what it failed to examine is the one input it exists for.

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
- **`produce --no-verify` never commits stale lock files.** Before committing, it checks whether
  any committed lock file resolves a pinned package at a version other than the generated pins,
  or records a `requested` range other than the one the pin requests (a pin that changes form but
  not version, `0.5.0` to `[0.5.0]`, moves only the range, and a locked restore refuses that too).
  When one does, it re-locks them in the staging copy with `dotnet restore --force-evaluate`
  alone, on the pinned SDK or `FACTORY_DOTNET_SDK_OVERRIDE`, checks again, and records them; nothing
  is built or tested. It refuses, naming each file, package and both versions (or ranges), when
  no SDK can run, restore fails, or they still disagree, and the refusal names the command that
  works: the same produce under the override at an installed SDK, or, with none, after installing
  the pinned one. Lock files that already agree are committed as they are. Those refusals exit 1,
  like every other refusal; a `--no-verify` run that writes its engine exits 3, below.

## Amendment — `--no-verify` is not a success

The bullet above is about what a `--no-verify` run must not *commit*. This is about what it must
not *claim*. It printed `verification SKIPPED (--no-verify)` and `produced <Name> in <out>, NOT
VERIFIED`, and then exited 0. A script or CI job that checks only the exit code — which is what a
script checks — could not tell an engine that was never built or tested from a verified one. It
was found proving criterion 5 of [#3](https://github.com/brandonifco/rules-factory/issues/3) ("the
factory validates each output before declaring success") and recorded there as the one real hole
([`examples/acceptance-4-5/EVIDENCE.md`](../../examples/acceptance-4-5/EVIDENCE.md)).

**So `produce --no-verify` exits 3, NOT VERIFIED, and never 0.** 0 means verified, 1 means refused,
2 means a usage error, and 3 means the output was written and nothing about it was proven.

- **3 is not a new invention.** It is the code this lineage already gives that outcome:
  `scripts/engine-gate.py posture` exits 3 when a corpus cannot be verified under its declared
  posture — "neither ok nor FAIL, and never silent" — and `examples/hoyle-blind-rebuild`'s
  `check-rebuild.py` and `check-target.py` both document "3 NOT VERIFIED", the latter adding
  "without `--run-tests` the check exits 3, NOT VERIFIED: never 0".
  [0013](0013-verification-posture-belongs-to-the-corpus.md) is where the rule comes from: a run
  that could not verify reports `NOT VERIFIED` with the reason, never `ok`. An exit code is part of
  the report.
- **`--no-verify` stays usable, and unflagged.** No option makes it exit 0. That is deliberate, and
  it follows `check-target.py`'s "never 0": a flag whose only effect is to turn NOT VERIFIED into
  success would put the hole back behind one more argument. A caller for which an unverified engine
  is the intended outcome accepts exactly 3 and passes every other code through — the idiom
  `scripts/validate.sh` already uses for `posture`. `scripts/validate-engine.sh` does this in one
  wrapper (`unverified_produce`), which also fails if produce ever exits 0 under `--no-verify`.
- **Only `produce --no-verify` exits 3 today.** `verify`, `provenance`, `rails` and `backlog` each
  either prove their claim (0) or refuse (1); none of them writes an unproven output. If a future
  command acquires that outcome, it takes this code.
- **The last line names the code.** `produced <Name> in <out>, NOT VERIFIED -- nothing was built or
  tested, so this run exits 3, not 0`. The line and the code cannot be read apart.

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
| `scripts/validate.sh` | generated |  | The gate recipe (M3): the factory's definition of acceptable, which an engine must not weaken by editing. |
| `scripts/map-overlay.py` | generated |  | Gate recipe: 0015's merge. |
| `scripts/engine-gate.py` | generated |  | Gate recipe: the non-dotnet checks. |
| `scripts/factory/*.py` | generated |  | The factory's generator, vendored so the gate can regenerate without the factory. |
| `.github/workflows/validate.yml` | generated |  | Gate recipe: CI runs `validate.sh full`. |
| `AGENTS.md` | managed | 10 | The governing contract every agent works the engine under (0029). Managed, not generated: a team may amend its own contract, and the factory must then either carry the amendment or refuse and say so, never silently overwrite it. |
| `CLAUDE.md` | managed | 1 | A pointer to `AGENTS.md` and an index of the Claude adapters. It states no rule of its own, so it cannot drift from the contract. |
| `docs/agent-team.md` | managed | 4 | The four roles and what each may not do (0029). |
| `.claude/agents/engine-dev.md` | managed | 8 | The implementer's charter. |
| `.claude/agents/repo-steward.md` | managed | 1 | The structural reviewer's charter, read-only. |
| `.claude/agents/rules-conformance.md` | managed | 3 | The semantic reviewer's charter, read-only. |
| `.claude/hooks/primary-checkout-guard.py` | managed | 1 | The `PreToolUse` guard keeping implementation work out of the primary checkout. Policy, and the engine that must change it adopts it. |
| `.claude/settings.json` | managed | 1 | Which tools the guard runs before. |
| `tools/dispatch-agent.sh` | managed | 3 | One issue, one worktree, one branch; it refuses what is not ready to work (0029). |
| `tools/new-issue.sh` | managed | 2 | An issue with the shape the rails expect, at the ready state and normal risk. `--produce` swaps in the body for a `factory produce` update, and promotes nothing (#193). |
| `tools/entry-packet.py` | managed | 5 | The bounded assignment for one entry, assembled from merge(package, overlay) so it cannot carry a reading of its own. |
| `tools/re-produce.sh` | managed | 4 | Re-runs `factory produce` on the engine from the factory commit `provenance.json` names. The record is generated, so an overlay edit is only finished by a produce, and prose describing that clone is a procedure an operator can get wrong (#192). |
| `tools/review-packet.py` | managed | 2 | Everything a reviewer needs about one pull request, in the order it is meant to be read. |
| `tools/pr-policy.py` | managed | 5 | The pull request contract, checked mechanically: one linked issue, every section filled, output rather than a claim. A `factory produce` update's claim is checked against `provenance.json` and this table, never taken (#193). A retired path counts only as a deletion the base commit's record attributes to the factory (#243). |
| `tools/record-verdict.py` | managed | 1 | A review verdict as a commit status on the exact commit reviewed, so a later commit invalidates it by itself. |
| `tools/conformance-gate.py` | managed | 2 | Whether the verdicts this change needs are recorded at the commit being merged. A truncated file list is undecidable rather than a small change (#193). |
| `tools/requeue-gate.py` | managed | 1 | Asks the gate to report again at the commit a recorded verdict names, so recording the verdict is the whole of the step (#191). It writes no status and no check run of its own. |
| `.github/pull_request_template.md` | managed | 2 | The pull request shape `pr-policy.py` checks. Template and checker are emitted together, so neither can drift from the other. |
| `.github/workflows/pr-policy.yml` | managed | 1 | The required check that runs `pr-policy.py`. |
| `.github/workflows/conformance-gate.yml` | managed | 2 | The required check that runs `conformance-gate.py`, on the `pull_request` event alone: a `status` run belongs to the default branch's commit, so the check has one producer and one commit it lands on (#191). |
| `.github/workflows/verdict-requeue.yml` | managed | 1 | Runs `requeue-gate.py` on the `status` event. Deliberately not a required check: it runs on the default branch's commit, where a required check governs nothing. |
| `tools/agent-doctor.py` | managed | 3 | Whether the rails are active or only present: the rails byte for byte as the recipe wrote them, the hook wired, the policy one a verdict can be recorded under, the labels created, the checks required (#211). |
| `.editorconfig` | managed | 1 | The kernel determinism analyzers' severities: warning (so, with warnings as errors, a build error) under `src/`, off under `tests/`. |
| `global.json` | managed | 1 | The SDK the kernel pins and `rollForward: disable`. This is policy every engine should follow as the kernel moves. An engine that must move ahead of the kernel adopts the file. |
| `NuGet.config` | managed | 2 | Package sources and source mapping: supply-chain policy (restore talks to nuget.org only, lock files pin content). An extra feed is a deliberate departure, so it is an explicit adoption. |
| `Directory.Build.props` | managed | 2 | Target frameworks, analyzers, warnings-as-errors, determinism and lock-file mode. The review named exactly these as changes that never reached existing engines. |
| `Directory.Packages.props` | engine-owned |  | Central package management and the test package versions, which an engine bumps itself. It imports the generated pins, and `produce` refuses an engine whose copy does not import them or pins the kernel or map again, so the part that must track the factory is already generated. |
| `{name}.slnx` | engine-owned |  | The engine adds projects to its solution. |
| `src/{name}/{name}.csproj` | engine-owned |  | The engine adds references and files. The map reference lives in the generated props. |
| `tests/{name}.Tests/{name}.Tests.csproj` | engine-owned |  | The engine adds test references. |
| `overlay/*.json` | engine-owned |  | The engine's three fields for **one** entry, `overlay/<entry id>.json` (0015, #247). One file per entry, so two entry branches never write the same one. Scaffolded by nothing: a file appears when an entry is implemented, and `produce` writes one only to migrate an engine produced before the split. The factory must never overwrite one. |
| `.github/agent-policy.json` | engine-owned |  | The engine's own rails configuration: label strings, review contexts, the ordered independent-review chain, the worktree variables (0029). Written once; a factory change must never undo a consumer's provider chain. |
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
