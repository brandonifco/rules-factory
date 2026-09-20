# 0029 — The rails are emitted by default, `AGENTS.md` governs, and vendor choice is engine-owned configuration

## Status

Accepted — 2026-09-15. Decided by Brandon on 2026-09-15. Answers
[#1](https://github.com/brandonifco/rules-factory/issues/1) (which rails are general and which are
one team's operating model) and specifies
[#4](https://github.com/brandonifco/rules-factory/issues/4) (what a produced engine ships with).
Extends [0018](0018-every-file-the-factory-writes-has-one-owner.md), which classifies every file
the factory writes, and [0001](0001-the-corpus-map-is-the-interface.md), which makes the map the
interface an engine is built against.

Neither #1 nor #4 closes with this record. Both close on the acceptance run below.

**Amended 2026-09-16** for [#193](https://github.com/brandonifco/rules-factory/issues/193): a
`factory produce` update to an engine is work under these rails like any other, and §4's contract
could not be satisfied by one. See *Amendment — a factory update is work under the rails* below.
Nothing in §3's line, §7's verdicts or §10's ruleset changes; §5's table gains no row, and five
managed rails move a recipe version.

**Amended 2026-09-16** for [#186](https://github.com/brandonifco/rules-factory/issues/186): §7's
verdict gate says who can satisfy it, which is everyone with status-write access, and the required
checks are pinned to the app that posts them. See *Amendment — the verdict gate is an integrity
check, not an authentication* below. Nothing about the chain, the contexts or the commit binding
changes; §10's ruleset gains the pin, and `AGENTS.md` moves a recipe version.

**Amended 2026-09-20** by
[0049](0049-a-review-verdict-is-bound-to-one-immutable-review-packet.md) for
[#334](https://github.com/brandonifco/rules-factory/issues/334): the intended exact-commit binding
in §§6-7 is now carried by a deterministic review-packet manifest. Packet assembly reads one
detached immutable reviewed tree, and verdict recording consumes and verifies that packet identity
rather than selecting the mutable current PR head. The provider-authentication boundary above is
unchanged.

## Amendment — the verdict gate is an integrity check, not an authentication

A verdict is a commit status under a policy-named context, and **anyone who can write commit
statuses on the repository can post one**: any collaborator with write access, any workflow whose
token carries `statuses: write`, anyone holding a leaked token. Nothing attributes a verdict to the
reviewer it names. `tools/record-verdict.py` has always said it cannot check which model produced a
verdict; what was missing is that the trust boundary was not stated where the rails are decided —
here — nor where they are read, in the emitted `AGENTS.md` §7. A reader of either could reasonably
have concluded that a recorded verdict proves a review happened.

**So it is stated, and it is not overstated.** The commit binding is real and does the work claimed
for it in §7: a verdict names one SHA, so it cannot be replayed onto bytes nobody read, and a
further commit ends it. What the gate is, exactly, is an integrity check — against a review that
was skipped, forgotten, or formed on an earlier commit — and not an authentication of who reviewed.
An invented verdict is stopped by honesty and by the review of the pull request it sits on, not by
permissions.

**The verdict contexts cannot be pinned to a source, and this records why.** GitHub's ruleset
`required_status_checks` takes an optional `integration_id` beside each `context`: "the optional
integration ID that this status check must originate from". An integration is a **GitHub App**. A
verdict is posted by whoever ran `tools/record-verdict.py`, with that person's own token, so it has
no integration to name and no value of `integration_id` would ever match it. A verdict context is
therefore unpinnable **while a verdict is a commit status posted by a person**, and no arrangement
of the ruleset changes that. What would change it is changing who posts: a verdict recorded by a
GitHub App, or by a workflow using `GITHUB_TOKEN` (which posts as the GitHub Actions app), could be
pinned to that app. Both move the identity from the reviewer to the machine that carries it, which
is a different design and a larger one — an App to install and hold a key for, or a workflow that
must itself decide a verdict it did not form. It is not done here, and the gap is named rather than
papered over.

**Where a pin does apply, `--apply` now writes it.** The three required checks — `validate`,
`pr-policy` and `conformance-gate` — are GitHub Actions workflows this record emits, and a required
status check matches by context name alone: an unpinned `conformance-gate` was satisfied by a commit
status under that name, which is the same write access as above. Each is now pinned by
`integration_id` to the GitHub Actions app, read from the host at apply time rather than hard-coded,
because the id differs between github.com and each Enterprise Server. `rails --check` reports a
required check that is not pinned, and `--apply` refuses to write the ruleset at all when the app's
id cannot be read: a ruleset whose checks look required and are satisfiable by anyone is the defect,
not a degraded success.

**Two consequences worth stating.** A check satisfied from anywhere but GitHub Actions — another CI
posting a status named `validate` — stops counting, which is the point and is also a real change for
any engine doing that. And an engine whose rails were applied before this carries three unpinned
checks until the next `factory rails --apply`, which `--check` now reports.

## Amendment — a factory update is work under the rails

The live run of #157 found it: `faa-part-107#43` failed `pr-policy` and `conformance-gate`, and
merged only because neither was required yet. From then on every `factory produce` update to an
engine — a new map version, a new kernel pin, a new factory recipe — is a pull request under the
rails this record emits, and such a pull request closes no issue, names no single entry or locator,
and records no mutation, because it writes no test. The rails could not accept the change that
installs them.

**A factory update is opened from an issue like any other work** (`tools/new-issue.sh --produce`),
dispatched to a worktree, produced there, and merged through the same three checks. Nothing about
it is outside §4. `--produce` does not promote risk: what moved decides that, and risk stays the
orchestrator's judgement (§3).

**Produce mode in `tools/pr-policy.py` is a closed predicate, not an indicative one.** A pull
request is a factory update only when all three hold:

1. **it says so** — a `## Produced by the factory` section carrying the fixed marker
   `<!-- rules-factory-produce -->`, declaring the factory version, the map package and version,
   and the kernel version;
2. **those facts equal `provenance.json` in the checked-out tree**, and that record says
   `factory.dirty: false`. `pr-policy.yml` checks out on a `pull_request` event, so the workspace
   is the merge result. A produce from a dirty factory is not reproducible by anyone, so it is not
   an update;
3. **every changed path is one the factory writes**, classified through the engine's own vendored
   `scripts/factory/ownership.py` — generated, managed, or a `packages.lock.json` the #94 re-lock
   exception covers. The table is imported rather than restated, so the classification a pull
   request is judged by and the one `produce` wrote the files by cannot disagree. A hand-written
   `src/**/*.cs`, an overlay edit, a `.csproj` edit, an edit to `.github/agent-policy.json`, an
   unclassified path: any one of them voids the claim, and the pull request is judged as the
   ordinary pull request it then is.

A claim that fails any part produces a finding naming which part. There is no silent downgrade: an
author who wrote the section meant it, and being told "you named no mutation" without being told
why the claim was refused is the failure this record's §9 is about.

**Why this grants no new territory.** The file set produce mode can cover is *exactly* the set
nobody may hand-edit anyway: `AGENTS.md` §10 already forbids editing `corpus/`, `provenance.json`
and `Generated/` by hand, and `produce` refuses a hand-edited managed file by name (0018). Forging
the *content* of those bytes is caught by `validate.sh full`, a required check, which regenerates
every `*.g.cs` and compares byte for byte. Forging the *declaration* fails against
`provenance.json`, which is in the diff.

**It changes what a pull request must say, and never what it must prove.** It waives no verdict, no
`Closes #<n>`, no label rule, no `validate` run and no behavioural claim. It replaces two
obligations that do not apply with two that are harder to fake:

- instead of one entry id and one locator — the map package and version, and what moved. A map
  version bump regenerates every entry, so "all of them" is the honest answer and it names nothing;
- instead of a named mutation — the `factory produce` command and its output, the gate's output,
  and a `factory provenance --engine <dir>` recompute showing the committed record is the one a
  re-produce writes. All three are re-runnable by a reviewer.

`factory produce --produce-report FILE` writes those fields, so they are read off the run rather
than remembered. Agent provenance is unchanged: a factory update still says who ran the produce and
who reviewed it.

**No future amendment lets produce mode waive the semantic verdict.** This is refused here, in
advance, because it is the amendment that will be proposed the first time a map bump is urgent: the
whole value of the predicate is that it moves nothing from the review column into the paperwork
column. A produce update that cannot get its verdict is a produce update that waits.

**Which verdicts such a pull request needs is derived from the changed paths, by the rule already
in `tools/conformance-gate.py`, unchanged.** `review.semanticPaths` is `src/**`, `tests/**`,
`corpus-map.overlay.json`, `RulesFactory.Packages.g.props`, `corpus/**` and `docs/decisions/**`,
and that answers all four sub-cases without anyone declaring anything:

- **a map version bump** rewrites `RulesFactory.Packages.g.props`, every `src/**/Generated/*.g.cs`
  and `tests/**/Generated/*.g.cs`, and re-locks both `packages.lock.json`, which sit under `src/**`
  and `tests/**`. Semantic, by four independent paths;
- **a kernel pin bump** touches the props file and the lock files. Semantic, and it must stay so:
  the kernel is the runtime the rules execute on, and "only a pin" is exactly the change that
  alters behaviour without looking like it;
- **a generator recipe change** rewrites the `*.g.cs`. Semantic;
- **a rails or gate recipe change** touches managed files, `scripts/**` and `backlog/`, none of them
  on the semantic surface. No rules verdict, and the gate already prints "nothing on the semantic
  surface".

The gate therefore gets **no produce-aware branch**. It needs none, and it is precisely where an
exemption could later be written. Its one change for #193 is unrelated to produce mode and is
described below.

**A truncated file list is undecidable, in both checks.** `gh pr view --json files` returns at most
100 files, silently: `cli/cli#14354` has 150 changed files and returns 100, `kubernetes#142020` has
164 and returns 100, with no error and no warning. Both checks derive everything from that list,
and neither asked for `changedFiles`, so neither could tell. A pull request with more than a
hundred changed files whose rule-bearing files sort past the first hundred got "nothing on the
semantic surface" and merged unreviewed — and a map version bump regenerates hundreds of files, so
it is exactly the change that hits it. Both now ask for the count alongside the list and refuse to
decide when they disagree: an `Undecidable` in `conformance-gate.py`, a finding in `pr-policy.py`.
This is §7's "a check that examines nothing is a failure" applied to a check that examined *some*
things.

**What this does not close.** Two gaps, recorded rather than implied:

- **A map version bump is semantic work with no single entry, and `tools/review-packet.py` assembles
  a packet around one entry.** A reviewer of such a pull request is served a packet for whichever
  entry the issue happens to name, or none. The verdict is still required and is still a person's
  reading; what is missing is the bounded context this record's §6 promises them. A known gap.
- **The predicate cannot catch a pull request that edits the vendored generator and the files it
  generates together**, so that regeneration agrees with itself. Both are generated files, so the
  claim would stand. This hole exists for every pull request today and is not created here:
  `validate.sh` regenerates using the *vendored* generator, so it cannot see it, and only
  `factory provenance` against the real factory closes it (`recipes[]` hashes every factory module).
  What the predicate does add is that such a diff is loud — a produce that changed nothing else
  rewriting `scripts/factory/generate.py` is the first thing a reviewer sees.

## Context

Both rails issues were held at `p3-needs-two-engines`: deciding what every produced engine ships
with, from a sample of one board game, is how the predecessor repository ended up encoding one
team's operating model as a framework ([docs/backlog.md](../backlog.md)). That hold is now lifted.
`faa-part-107` is a regulation, not a game; `hoyle-backgammon` and `srd-52-combat` are the other
two. There are three produced engines and a fourth built blind from the map alone.

What those engines show, in two directions:

**The work item is already sufficient.** A `faa-part-107` backlog issue carries the merged map
entry, the locator and its `evidence` verbatim, dependencies, reachability, cross-references and
how each resolves, acceptance criteria, the generated handler contract, and the requirement that
every test record the mutation that makes it fail (`tools/factory/backlog.py`). The blind rebuild
(#3, criterion 1) is the evidence that this is enough: an agent with no access to the original
implementation reconstructed the engine from the map, the corpus and the owner's rulings, and
passed the target's own tests. The factory's technical specification is not the gap.

**Nothing around the work item is emitted.** `tools/factory/gate.py` writes `scripts/validate.sh`,
its three scripts, the vendored `scripts/factory/*.py` and `.github/workflows/validate.yml`. That
is the whole of it. `faa-part-107` and `hoyle-blind-rebuild` each have exactly one workflow, no
`AGENTS.md`, no charters, no dispatch, no PR policy and no recorded verdicts. `faa-part-107` has
37 open backlog issues and no rails to work them with.

`deckard` has the missing layer, hand-built: a governing contract, three agent charters, a
worktree discipline with a `PreToolUse` guard, bounded packets, a PR policy that runs as a check,
review verdicts recorded as commit statuses at an exact SHA, a conformance gate, and a branch
ruleset that requires all three. It is outside the factory (0028) and stays there, so what it
offers is a proven shape, not a component to import.

The question #1 asks is where the line falls between that shape and this author's choices inside
it. This record draws it.

## Decision

### 1. The rails are default output

A produced engine ships with its rails, as it ships with its gate. There is no flag to decline
them and no module to add later. An engine without rails is a scaffold, and scaffolds were
already tried.

### 2. `AGENTS.md` is the governing contract; `CLAUDE.md` points at it

`AGENTS.md` is the one governing document, and it is vendor-neutral. `CLAUDE.md` says that
`AGENTS.md` is authoritative, that it must be read first, and that Claude-specific role adapters
live under `.claude/`. It states no rule of its own.

`deckard` has this the other way round, because it was built in one vendor and grew the neutral
file second. The factory produces engines for whoever works them, so the neutral file is the
contract. Which file governs is settled once here so that no engine has to answer it, and neither
file restates the other: duplicate governing instructions drift, and a drifted contract is worse
than no contract.

### 3. Where the line falls

**The factory emits, fixed:** the governing contract and the role definitions; the charters; the
worktree discipline and its guard; one issue state machine and one risk axis; bounded packets
generated from the map rather than discovered; a PR shape demanding a behavioural claim and real
evidence; a review verdict pinned to an exact commit; the rule that a reviewer is read-only; the
rule that a fallback chain advances on unavailability and never on disagreement; and the
requirement that the enforcement and the documents it cites ship together.

**The engine chooses, in configuration:** which providers are in the independent chain and in
what order; the status contexts they record under; the label strings; the paths that count as a
semantic surface; and where worktrees are rooted.

**The factory does not decide at all:** whether a given issue is high risk (the orchestrator's
call), what the answer to an ambiguity is (the owner's, recorded as a ruling or an ADR), or
which review actually ran (recorded, not inferred).

No vendor name appears in any emitted script or document. The default chain shipped in the
configuration file names `codex`, `gemini` and `in-house-independent` because those are this
author's, and a file the engine owns is exactly where a default belongs.

### 4. `.github/agent-policy.json` is engine-owned

One file holds every choice above, read by every emitted script. It is engine-owned under 0018:
written once when absent, never touched again, so a factory change cannot undo a consumer's
provider chain or label vocabulary. Its `schemaVersion` is 1. The shape the factory writes:

```json
{
  "schemaVersion": 1,
  "labels": {
    "ready": "state:ready",
    "blocked": "state:blocked",
    "needsDecision": "state:needs-decision",
    "normalRisk": "risk:normal",
    "independentRisk": "risk:independent-review"
  },
  "review": {
    "semanticContext": "rules-verdict/semantic",
    "semanticPaths": ["src/**", "tests/**", "corpus-map.overlay.json",
                      "RulesFactory.Packages.g.props", "corpus/**", "docs/decisions/**"],
    "independentFallback": [
      { "id": "codex", "context": "rules-verdict/codex" },
      { "id": "gemini", "context": "rules-verdict/gemini" },
      { "id": "in-house-independent", "context": "rules-verdict/in-house-independent" }
    ]
  },
  "worktrees": {
    "rootEnvironmentVariable": "RULES_ENGINE_WORKTREE_ROOT",
    "primaryMutationEscapeHatch": "RULES_ENGINE_ALLOW_PRIMARY_MUTATION"
  }
}
```

**The five labels are three states and two risks, and no two of them may be the same string**
(#188). `backlog.py` computes a state set and a risk set from them, so two keys sharing one label
make an issue ready and blocked at once, or strip its risk when its state moves. The rule is
checked once, in the module that writes this file, and both `rails --check` and `backlog` refuse
through it rather than each stating it. The review section is held to the same arrangement (#211):
a semantic context, a non-empty chain, and an `id` and a `context` on every link, judged by one
function that `rails --check`, the engine gate and `tools/agent-doctor.py` all import.

Replacing the review chain is an edit to this file and nothing else. That is #1's second
acceptance criterion and #4's third, and it is what the emitted scripts are tested against.

Environment variables are `RULES_ENGINE_*`, never a vendor's or an engine's name.

### 5. Every emitted rail has an ownership row, and managed rails are name-free

0018 admits no unclassified output, and `provenance.build` refuses a written path that matches no
row. The classification:

| Path | Class | Why |
|---|---|---|
| `AGENTS.md`, `CLAUDE.md`, `docs/agent-team.md` | managed | factory policy the engine keeps receiving; adoptable |
| `.claude/agents/*.md`, `.claude/hooks/*.py`, `.claude/settings.json` | managed | the Claude adapter for the same policy |
| `tools/dispatch-agent.sh`, `tools/new-issue.sh` | managed | the worktree and issue discipline |
| `tools/entry-packet.py`, `tools/review-packet.py` | managed | bounded context, read from the merged map |
| `tools/pr-policy.py`, `tools/record-verdict.py`, `tools/conformance-gate.py` | managed | enforcement |
| `tools/requeue-gate.py` | managed | a recorded verdict asks the gate to report again (#191) |
| `tools/re-produce.sh` | managed | an overlay edit is finished by a re-produce, from the factory commit the record names (#192) |
| `tools/agent-doctor.py` | managed | the audit of all of it |
| `.github/pull_request_template.md` | managed | the PR shape |
| `.github/workflows/pr-policy.yml`, `.github/workflows/conformance-gate.yml` | managed | the two new required checks |
| `.github/workflows/verdict-requeue.yml` | managed | the `status` event's side of that, and deliberately not required |
| `.editorconfig` | managed | analyzer severities (§12) |
| `.github/agent-policy.json` | engine-owned | §4 |
| `docs/decisions/**` | engine-owned | the engine's own rulings |

**A managed rail may not interpolate the engine's name or anything about its map.** This is not a
style preference; it is what 0018 already requires. A managed file's bytes are detected against
`RECIPE_SHA256`, the fixed bytes every version of its recipe ever wrote, and that is how a hand
edit is told from a stale policy and refused rather than overwritten. A recipe that varied by
engine would have no such history.

So `AGENTS.md` and the charters say "this engine" and read the name from `provenance.json` where
they need it. The alternatives were to generate them with substitution, which would silently
overwrite a team's edits to its own governing contract on every `produce`, or to add a
managed-with-substitution class to 0018, which would weaken hand-edit detection for every managed
file to personalise a handful of documents. Neither is worth it: everything name- and map-specific
belongs in the packets, which are generated at the moment they are used.

### 6. The entry packet, not a source packet: the map is the interface

`deckard` extracts bounded rulebook excerpts because its corpus cannot enter the repository. The
factory admits only corpora it can commit and publish (0028), and the map — not the corpus — is
what an engine is built against (0001). Copying the source-packet mechanism would import a
constraint this factory does not have and point agents at the wrong interface.

`tools/entry-packet.py` takes an entry id and writes a bounded, ephemeral packet from the same
`merge(package, overlay)` the gate uses (0015, `scripts/map-overlay.py`): the merged entry; its
`SourceLocator` and `evidence` verbatim; `dependsOn`; `enabledBy` and `suspendedBy`;
`crossReferences` and how each resolves; the generated handler signature; the entry's current
overlay row; the owner's rulings and declines that apply to it (0027); the ADRs it names; the map
package id, version and hash; and its test and mutation obligations.

**An implementer does not remap the corpus.** Where the packet and the corpus appear to disagree,
it stops and reports an upstream map defect. It does not make the engine disagree with the
published map. A map is corrected where maps are corrected — a new map version, checked and
published (0015, 0017) — and the engine is re-produced from it. An implementation agent that can
quietly overrule the map makes the map stop being the interface.

`tools/review-packet.py` is separate and assembles what a reviewer needs: the issue and its
acceptance criteria, the PR body, changed files, a bounded diff, the entry ids and their packet
digest, the map version and provenance, the overlay before and after, the applicable ADRs, the
determinism prompt, the expected gates and the risk classification. Under 0049 it reads all
repository evidence from a detached worktree pinned to the exact reviewed head, and writes a
deterministic `*.review.json` manifest binding the Markdown packet, reviewed base/head,
provenance, policy, entry-packet tooling, generated entry packets and their package-map input.
Packets are written outside the repository and are never committed.

### 7. A verdict consumes one packet identity, and the chain advances only on unavailability

A review that exists only in a transcript is not a review anyone can check later. Under 0049 a
verdict requires the format-1 `*.review.json` emitted with the packet. `tools/record-verdict.py`
re-hashes the human packet and its bound companion artifacts and records the status only against
the manifest's exact reviewed SHA; the current PR head never supplies the identity of what was
reviewed. `tools/conformance-gate.py` still requires the verdict at the head being merged. A
further commit therefore makes the old packet and status stale for the gate while preserving them
as historical evidence on the old SHA.

A change touching `review.semanticPaths` requires `review.semanticContext`. An issue carrying the
independent risk label additionally requires one of `review.independentFallback`'s contexts. The
independent reviewer receives the same entry packet and **not** the first reviewer's conclusions.

**The chain advances because a link is unavailable, never because its verdict was unwelcome.** A
recorded failure at any configured context blocks the gate outright, and a later pass at a
different context does not clear it. A fail is answered by fixing the code, fixing the map, or
getting an owner's ruling.

**Who can satisfy this gate: everyone with status-write access on the repository.** The commit
binding above is an integrity check, not an authentication of the reviewer, and the verdict
contexts cannot be pinned to a source. See *Amendment — the verdict gate is an integrity check, not
an authentication* above (#186).

### 8. Read-only is checked, not claimed

The predecessor shipped a charter that described a reviewer as read-only while granting it
`Bash`. Every emitted reviewer charter grants read tools only, and the engine's own gate
(`scripts/engine-gate.py`) fails when a reviewer charter grants a mutation-capable tool. An
external reviewer is invoked in a read-only sandbox against the packet directory, not against the
implementation worktree.

### 9. No rail cites a document the factory does not emit

The predecessor shipped enforcement machinery beside documents it had deleted: 61 references to
files that did not exist, several inside runtime error messages, and a pre-armed hook whose escape
hatch was documented in a file that was gone. The engine gate checks that every path and document
an emitted rail names exists in the engine, and that the guard's escape hatch is documented where
the guard says it is. Rails and their manual ship together or neither ships.

### 10. `produce` writes files; `factory rails` changes GitHub

A workflow that exists is not a workflow that is required, and that gap is #4's largest loophole.
Closing it means changing repository settings, which `produce` must not do silently.

`factory rails --repo <owner/name> --check` reports, read-only, whether the agent files, the
policy, the labels, the ruleset, the rules in force on the default branch and each required check
are in place, and which review chain is configured. `--apply` creates the labels and a branch ruleset the factory owns, named
`rules-factory-agent-rails`, requiring a pull request, resolved threads, no force-push, no
deletion, no bypass actor, and the checks `validate`, `pr-policy` and `conformance-gate`. Both are
idempotent.

**A ruleset that carries the factory's name is compared in full, and `--check` says OK only when it
is the ruleset the factory writes** — its target, its enforcement, its conditions *including any
exclusion*, its bypass actors and every rule's parameters, with a condition the factory does not
model counted as a mismatch rather than skipped. Until #185 the comparison read `enforcement`, the
`include` list, the bypass actors and the rule parameters, so a ruleset excluding `~DEFAULT_BRANCH`
or targeting tags was reported as enforced and left alone: the default branch had no rails and the
doctor said OK. The checks are pinned to the app that posts them (#186, the amendment above).

**A row says OK only about what it examined (#211).** Four rows did not. The `Agent files` row
found files by name, so a truncated rail was OK; it now compares each rail's bytes with the recipe
history `produce` refuses a hand edit by (0018), and names a rail that is absent, from an earlier
recipe, edited by hand, or adopted by the engine. The `Policy` row was OK once the file parsed, so a
chain link with an `id` and no `context` — a reviewer who cannot record a verdict — was OK here
while the engine's gate rejected it; the policy is now judged by one function in `generate.py`,
which `rails --check` imports and the engine's `scripts/engine-gate.py rails` and
`tools/agent-doctor.py` import from the copy `produce` vendors, so the three cannot disagree about
one file. Only the repository's own rulesets were read, and an organization's rulesets govern its
repositories' branches too; the rules in force on the default branch are now read from GitHub at
every level and named by the ruleset they come from, a ruleset carrying the factory's name above the
repository is reported as not the factory's, and where the rules cannot be read the row says NOT
VERIFIED and `--check` fails rather than reporting nothing there. And the `Verdict gate` row, which
examines nothing, said OK beside a note saying the gate is unpinnable; its state is now NOT
AUTHENTICATED, and, since no `--apply` can change it, it does not fail the check.

**The factory owns one ruleset and never edits another.** A ruleset update replaces its whole
rules array, so writing into an existing ruleset would silently drop rules the factory did not
author. GitHub evaluates rulesets together, so a separate one composes with whatever else the
repository has.

**Merge commits only.** The verdict is pinned to the head SHA. A squash merge manufactures a
commit that no reviewer ever saw; a merge commit keeps the reviewed SHA in the history as a
parent.

### 11. One state label, one risk label, and no phase labels

The map already knows build order through `dependsOn`, and `backlog.py` already emits items in
topological order. Recreating that as phase labels in GitHub is a second ordering that can
disagree with the first. There are none.

`backlog --create` sets `blocked` while an unimplemented `dependsOn` remains and `ready`
otherwise, and `normalRisk` on creation. Synchronisation **never** overwrites `needsDecision` and
**never** lowers risk: both are human judgements the factory has no basis to revise. An
implementation agent cannot resolve its own ambiguity and return its issue to ready.

Dispatch refuses an issue that is closed, blocked, awaiting a decision, already has a worktree, or
whose primary checkout is dirty.

### 12. Analyzers from day one, not a copied blacklist

`RulesKernel.Analyzers` is pinned at the kernel's version with the other pins, and `.editorconfig`
sets its diagnostics to warning in `src/` and off in `tests/`. Produced engines already build
warnings-as-errors, so a determinism defect breaks the build.

The alternative — copying a textual nondeterminism blacklist into every engine — is precisely the
copy-and-diverge the kernel exists to end. Review still owns what the analyzer cannot see.

### 13. One gate, unchanged

`scripts/validate.sh` stays the single definition of acceptable and is not duplicated or replaced.
The new mechanical checks are subcommands of `scripts/engine-gate.py`, which it already runs.
`validate.yml` still runs `./scripts/validate.sh full` and nothing else. The required checks are
`validate`, `pr-policy` and `conformance-gate`.

### 14. The agent team is three roles and an orchestrator

**Orchestrator** — the main session: grooming, risk classification, dispatch, collecting reviews,
escalation to the owner, merge. It does not implement ordinary issues in the primary checkout.
**Engine developer** — one ready issue, one worktree, one branch, one PR closing exactly that
issue; may edit code, may not resolve a genuine ambiguity. **Repository steward** — cheap
read-only review on every PR, run before semantic review so a scope or evidence defect does not
consume reasoning tokens. **Rules conformance reviewer** — read-only semantic review that reads
the entry packet before the implementation, so it is not anchored to the implementer's reading,
and tries to falsify it.

A role is added when a failure mode demands one, not in anticipation. Architect, testing,
documentation, GitHub and security agents are not emitted: each mostly adds a handoff.

### 15. What closes #1 and #4

Not the existence of these files. The acceptance run is a produced engine on GitHub where the
labels exist, the ruleset genuinely requires all three checks, a mutation in the primary checkout
is blocked, a ready issue dispatches, a malformed PR is rejected, a new commit invalidates a
recorded verdict, an independent-risk issue cannot merge on one verdict, and changing the provider
chain touches only `agent-policy.json` — followed by one real `faa-part-107` backlog entry taken
from issue to merge through nothing but the emitted rails.

## Alternatives considered

**Rails as an opt-in module.** Rejected before this record, in #1 and #4: the rails are the
product, and an engine that has to add them later is a scaffold.

**`CLAUDE.md` as the governing contract, as in `deckard`.** Rejected. The factory is
vendor-neutral by construction; making one vendor's file authoritative would make every other
agent a second-class reader of a mirror, and mirrors drift.

**Copy `source-slice.py`.** Rejected. It solves a licensing constraint 0028 removed, and it points
agents at the corpus when 0001 makes the map the interface.

**Let an implementer correct the map when it disagrees with the corpus.** Rejected. It makes every
implementation agent an unreviewed mapper and lets the engine diverge from the published map
without a version. Stopping costs one round trip; a silent divergence costs the interface.

**Hard-code the provider chain, as `deckard` does.** Rejected by #1's acceptance criterion. It is
the clearest example of one team's operating model becoming something every consumer must undo.

**Phase labels.** Rejected: a second ordering beside `dependsOn` that can disagree with it.

**A generic verdict context.** Rejected, for `deckard`'s reason: a reader of a merged commit must
be able to tell a cross-vendor verdict from a same-vendor fallback without opening a transcript.

**Squash merges.** Rejected here, though normal elsewhere: the reviewed SHA must survive in the
history.

**Managed-with-substitution ownership, so rails can name their engine.** Rejected. It weakens
hand-edit detection for every managed file, in exchange for personalising documents whose
specifics belong in the packets.

**A `factory:produce` label, instead of the body marker and the predicate.** Rejected. A label is
not in the reviewed bytes and not in the merge commit, so a reader six months later cannot tell why
the checks asked less of that pull request. Worse, nothing invalidates it: a commit status is
pinned to a SHA and dies when the head moves (§7), but a label applied *after* a reviewer read the
change alters what the gate demands without altering a byte.

**A body marker that relaxes the contract by its presence.** Rejected, and this is the distinction
the amendment turns on. `pr-policy.yml` treats the pull request body as attacker-controlled text and
refuses `pull_request_target` for exactly that reason; a marker that buys relaxations is a
self-issued exemption written in the one field anybody can edit. It survives only as the
human-readable statement of a claim that is decided elsewhere — against `provenance.json` and the
ownership table, both of which are in the diff.

**Let the author declare whether the update is semantic.** Rejected. The gate would have to check
the declaration against the changed paths anyway, since a declaration is worth what it can be
checked against — and once it does that, the declaration can only ever agree with the paths or
disagree with the truth.

**`produce` applies the GitHub settings itself.** Rejected. Producing files into a directory and
mutating a remote repository's protection settings are different acts with different blast radii,
and the second needs to be asked for.

## Consequences

- Every engine produced after this carries the rails, and every engine produced before it
  receives them on its next `produce` as managed files, unless it adopts them.
- A consumer who wants a different review chain, label vocabulary or worktree root edits one
  engine-owned JSON file. A consumer who wants different *rules* edits a managed file and either
  adopts it or has the next `produce` refuse, naming it — which is the intended conversation.
- `provenance.json` records `agent-policy.json` among the engine's build inputs, so what the rails
  were configured to do at a given commit is recoverable.
- The factory gains a command that talks to GitHub. `scripts/validate-engine.sh` proves the rails
  mechanically on a produced engine; the parts that need a real remote are proven once, in the
  acceptance run, and recorded there.
- This repository does not adopt its own rails yet. Deciding what engines receive and changing how
  this repository is worked are separate, and doing both at once doubles the review surface of
  every step.
- `deckard` keeps its hand-built rails and does not converge on these. It is outside the factory
  (0028), and its `CLAUDE.md`-first arrangement stays as it is.
