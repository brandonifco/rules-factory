# 0053 — A review verdict binds the exact packet and reviewed commit

## Status

Accepted — 2026-09-20. Records the remediation for
[#334](https://github.com/brandonifco/rules-factory/issues/334), under the assurance-hardening
parent [#338](https://github.com/brandonifco/rules-factory/issues/338).
**Amends [0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)**
at its packet-to-verdict handoff. It does not authenticate a reviewer and does not change the
review-chain policy.

## Context

0029 intended a useful invariant: a verdict belongs to one exact commit, so a later pull-request
commit cannot inherit an earlier review. The emitted tools did not actually establish the first
half of that statement.

Two reproduced failures made the gap concrete.

First, `tools/review-packet.py` asked GitHub for PR head B but read `.github/agent-policy.json`,
`provenance.json`, overlay state and generated entry packets from the caller's current checkout.
Running it from checkout A could therefore produce a packet headed "B" whose review context came
from A.

Second, `tools/record-verdict.py` let `--sha` default to the pull request's current head. A
reviewer could read A, the pull request could advance to B, and the normal recording command would
then post PASS to B. The gate correctly required a status on the commit being merged; the recorder
had simply attached the human judgement to a commit the human had never reviewed.

Each component was locally plausible. The missing invariant was the relationship:

> the bytes shown to the reviewer, the commit identity carried by the review evidence, and the SHA
> receiving the verdict must be the same review event.

## Decision

### 1. Packet assembly has one immutable repository state

`tools/review-packet.py` resolves the PR's exact head SHA and base SHA before assembly. It creates
a private detached git worktree at the reviewed head and reads every commit-local review input from
that snapshot: policy, provenance, overlay-derived entry context and the emitted entry-packet
program itself.

The caller's dirty or differently checked-out tree is not an input to those facts. The diff is
computed between the resolved base SHA and reviewed head SHA, not between moving branch names.

The temporary worktree is removed in a `finally` path on success or refusal and the worktree
metadata is pruned.

The PR head is read again after assembly. If it moved during packet construction, the packet is
refused rather than handed out as current review material.

### 2. File output carries a deterministic machine-readable review identity

Alongside the human `pr-<n>-<sha>.md` packet and any entry packets, packet generation writes
`pr-<n>-<sha>.review.json`, format 1. It names at least:

- pull request number;
- exact reviewed head commit;
- exact base commit used for the diff;
- SHA-256 of the human review packet;
- every generated entry packet id, file name and SHA-256;
- the reviewed policy path and SHA-256, plus the semantic context and ordered independent chain
  the reviewer was operating under;
- the reviewed provenance path and SHA-256;
- the map package id, version and package hash named by that provenance.

The record contains no timestamp, UUID, absolute machine path or mutable branch name.

### 3. The packet identity selects the verdict target

`tools/record-verdict.py` requires `--packet <...review.json>` for every newly recorded verdict.

The recorder verifies the identity format and the SHA-256 of the human packet and every entry
packet it names. The packet's pull-request number must equal `--pr`. If `--sha` is supplied it
is only an assertion and must equal `reviewedCommit`; it never selects a different commit.

The recorder then asks GitHub for the pull request's current head. That head must still equal the
packet's `reviewedCommit`. If A was reviewed and the PR is now B, recording refuses with both
identities and posts no status. The remedy is to generate a new packet and review B.

The status is posted to `reviewedCommit`, never to a SHA inferred at recording time.

### 4. Review policy is part of what was reviewed

The status context is selected from the policy captured in the packet identity, not from the
recorder's current checkout. A later local or committed policy change cannot silently reinterpret
an old review as belonging to a different context or provider chain.

This is an integrity property, not an authentication property. A person with status-write access
can still lie, manufacture a self-consistent packet identity, or falsely claim a provider produced
a judgement. Provider signatures, attestation and authentication are separate problems and are
not added here.

### 5. Existing history remains history; legacy recording does not float

Existing commit statuses remain readable by the conformance gate and repository history. Nothing
retroactively claims they had format-1 packet identities.

The old recording form with no `--packet` is refused for new verdicts. Silently falling back to
"current PR head" would recreate the exact defect this decision closes.

## Rejected alternatives

**Hash only the head commit.** Rejected. The original packet already printed the head SHA; the
failure was that the material under that heading could come from another checkout.

**Keep `--sha` and require the reviewer to type it.** Rejected. A manually copied SHA does not
bind the human packet or entry context, and it leaves the critical relationship as operator
discipline.

**Read the current checkout and merely verify it is clean.** Rejected. A clean checkout of A is
still the wrong state when the packet claims B.

**Post the old verdict to A after the PR moves to B.** Rejected as the normal workflow. That status
would not satisfy B's gate, but accepting the command makes stale review look like a successful
current operation. The recorder instead refuses and says to re-review.

**Add provider signatures/authentication here.** Rejected as scope expansion. This decision binds
what was reviewed to where its verdict lands. Who actually formed the judgement remains the
explicitly documented trust boundary from 0029.

## Consequences

Review evidence is now relational rather than three locally valid claims. A packet can be
reconstructed from one immutable commit, its exact human/entry bytes are hashed, and the verdict
cannot move to a different head.

A review packet is intentionally ephemeral, but its digest is surfaced in the commit-status
description so the recorded verdict names which packet identity was consumed.

Generating a file-backed packet becomes a prerequisite for recording a verdict. `--stdout`
remains useful for inspection, but by itself produces no identity that can authorize recording.

This closes only #334. Source-tree transaction identity (#335), SDK override/provenance semantics
(#336), and executed-test accounting (#337) remain separate assurance boundaries.
