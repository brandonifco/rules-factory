# 0049 — A review verdict is derived from one immutable review packet identity

## Status

Accepted — 2026-09-20. Decided while resolving
[#334](https://github.com/brandonifco/rules-factory/issues/334), the second remediation under
[#338](https://github.com/brandonifco/rules-factory/issues/338). Extends
[0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md).

## Context

The engine rails already intended a verdict to mean “somebody reviewed this exact commit,” and
the conformance gate correctly asks only for statuses on the pull request's current head. Two
handoffs did not mechanically establish that claim.

First, `tools/review-packet.py` asked GitHub for PR head **B** but read `provenance.json`,
policy, overlay and entry-packet inputs from whichever checkout happened to invoke it. A packet
could therefore print “head B” while carrying evidence from checkout **A**.

Second, `tools/record-verdict.py` made `--sha` optional and otherwise selected the PR's
*current* head. A reviewer could read packet A, the branch could advance to B, and the ordinary
recording command would attach PASS to B. The gate would then see exactly the status it required,
even though nobody reviewed B.

The two defects share one missing relationship: review evidence had plausible identities, but no
machine-readable object bound the evidence bytes to the immutable commit whose status was posted.

## Decision

### 1. A saved review packet has a machine-readable identity manifest

`tools/review-packet.py` emits the human Markdown packet, any generated entry packets, and a
deterministic `*.review.json` manifest. Format 1 names:

- pull request number;
- exact reviewed commit SHA;
- exact resolved base commit SHA used for the diff;
- SHA-256 of the human Markdown packet;
- the produced map package identity from reviewed `provenance.json`;
- SHA-256 identities of the reviewed tree's `provenance.json`, review policy, and
  `tools/entry-packet.py` when entry packets are generated;
- each generated entry packet independently by entry id, file name and SHA-256;
- any external package-map input by a staged file name and SHA-256;
- deterministic digests of the GitHub PR and issue context presented to the reviewer.

The manifest contains no clock, random identifier, host name, absolute temporary path or
unordered collection. A preview produced with `--stdout` has no manifest and cannot authorize a
verdict.

### 2. Repository evidence comes from one detached immutable tree

The PR head is read once from GitHub. The tool deliberately obtains that exact Git object without
switching the caller's branch, then creates a uniquely named detached temporary worktree pinned to
the SHA. Policy, provenance, overlay state, the entry-packet implementation and every other
repository read used to assemble the packet come from that worktree.

If the object is absent locally, the tool fetches the PR head/exact SHA without checking it out and
then verifies that the requested SHA exists as a commit. Failure to obtain the exact object is a
refusal; the live checkout is never a fallback.

The symbolic diff base is likewise resolved once to a commit SHA before assembly. Both base and
head are recorded in the manifest, so the diff the reviewer saw is reconstructable even after a
branch moves.

The worktree and staging directory are removed by their exact paths on success and failure. The
caller's branch, index and dirty files are never switched or consumed as review evidence.

### 3. External package-map bytes are staged and bound

When `--package-map` is supplied, its bytes are copied into the packet's private staging
directory before entry packets are generated. The reviewed commit's `entry-packet.py` reads that
staged copy, and the manifest binds the same copy by SHA-256. A later edit to the caller's external
path cannot change what the packet claims was reviewed.

When the normal restored package path is used, the reviewed tree's provenance continues to name
the package by its existing package id, version and nupkg digest. This decision does not redesign
NuGet restore or package provenance.

### 4. Verdict recording consumes the manifest, never mutable head identity

A newly recorded verdict requires `--packet <manifest>`. Before posting anything,
`tools/record-verdict.py`:

1. accepts only the known format-1 shape;
2. requires the manifest PR to equal `--pr`;
3. re-hashes the human Markdown packet;
4. re-hashes every bound entry packet and external input;
5. obtains the exact reviewed Git commit if necessary;
6. re-reads and hashes every bound repository source from that commit;
7. reads the reviewer/context policy from that reviewed commit; and
8. posts the status only to the manifest's `reviewedCommit`.

Self-reported digests are never enough. Duplicate source, entry-packet or external-input
identities are refused, as are unknown required shapes.

`--sha` remains only as a compatibility assertion. If supplied, it must equal
`reviewedCommit`; it cannot choose or override the target commit.

A Markdown-only legacy packet remains readable historical evidence, but it cannot be used to
record a new verdict under this guarantee.

### 5. A moved PR makes a packet stale; it does not rewrite history

If packet A is recorded after the PR advances to B, the status is posted to A and the command says
that it satisfies no current gate. This preserves useful historical evidence without ever
claiming B was reviewed.

PASS and FAIL are both evidence about exact bytes. A FAIL formed on A remains a failure of A.
Moving to B does not convert it into a PASS or attach it to B. Separately, the conformance gate's
existing head-specific policy means B still lacks the required successful review and remains
blocked until B is reviewed. **Evidence identity and workflow consequence are distinct.**

The fallback rule is unchanged: a provider failure is not a reason to ask later providers until
one agrees.

### 6. Provider authentication remains out of scope

This binds *what bytes were reviewed*. It does not cryptographically prove which model or person
formed the verdict, authenticate a provider, sign packets, or prove fallback-chain ordering.
0029's explicit operator trust boundary remains.

## Rejected alternatives

**Require `--sha`.** This still leaves packet contents free to come from another checkout and
asks an operator to copy identity correctly.

**Require local HEAD to equal PR head.** This couples review to the caller's checkout, rejects
useful dirty/parallel workflows, and does not establish that every read came from committed bytes.

**Parse the SHA from Markdown.** Human prose is not a machine contract and does not bind the prose
itself against later edits.

**Keep using current PR head when recording.** That is the reproduced defect.

**Hash only the diff.** Provenance, entry packets, policy and issue/PR context also informed the
review.

**Add signatures.** Signer identity is a different problem; exact Git identities plus content
digests close this artifact-substitution defect without inventing a signing infrastructure.

## Consequences

- Every newly recordable verdict is traceable to one immutable commit and one exact packet.
- A later PR head can determine whether a verdict satisfies the gate, never what commit the
  reviewer is said to have reviewed.
- Existing produced engines receive this contract when their managed rails are regenerated.
  Historical review records are not rewritten or retroactively upgraded.
- The manifest is review-packet identity only. It is not the general assurance manifest deferred
  by #338.
