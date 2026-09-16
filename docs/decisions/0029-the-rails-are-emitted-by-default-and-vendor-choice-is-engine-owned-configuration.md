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
| `tools/agent-doctor.py` | managed | the audit of all of it |
| `.github/pull_request_template.md` | managed | the PR shape |
| `.github/workflows/pr-policy.yml`, `.github/workflows/conformance-gate.yml` | managed | the two new required checks |
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
determinism prompt, the expected gates and the risk classification. Packets are written outside
the repository and are never committed.

### 7. A verdict names a commit, and the chain advances only on unavailability

A review that exists only in a transcript is not a review anyone can check later. A verdict is a
commit status recorded against the exact PR head SHA (`tools/record-verdict.py`), and
`tools/conformance-gate.py` requires it at the head being merged. A further commit therefore
invalidates the review that preceded it, because the status is on the old SHA.

A change touching `review.semanticPaths` requires `review.semanticContext`. An issue carrying the
independent risk label additionally requires one of `review.independentFallback`'s contexts. The
independent reviewer receives the same entry packet and **not** the first reviewer's conclusions.

**The chain advances because a link is unavailable, never because its verdict was unwelcome.** A
recorded failure at any configured context blocks the gate outright, and a later pass at a
different context does not clear it. A fail is answered by fixing the code, fixing the map, or
getting an owner's ruling.

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
policy, the labels, the ruleset and each required check are present, and which review chain is
configured. `--apply` creates the labels and a branch ruleset the factory owns, named
`rules-factory-agent-rails`, requiring a pull request, resolved threads, no force-push, no
deletion, no bypass actor, and the checks `validate`, `pr-policy` and `conformance-gate`. Both are
idempotent.

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
