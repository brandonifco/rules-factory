# 0049 — A review verdict is bound to one immutable review packet

## Status

Accepted — 2026-09-20. Implements
[#334](https://github.com/brandonifco/rules-factory/issues/334) under
[#338](https://github.com/brandonifco/rules-factory/issues/338). This amends
[0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)
§7's commit-binding mechanism. It does **not** change 0029's reviewer authentication boundary:
the operator still attests which reviewer produced the verdict.

## Context

0029 intended a verdict to be evidence about one exact commit, but the two commands on either side
of the review did not mechanically share that identity.

First, `tools/review-packet.py` asked GitHub for PR head B and printed B as the reviewed commit,
while reading `provenance.json`, policy, entry-packet tooling and entry/map context from whichever
checkout happened to run the command. A checkout at A could therefore emit a packet that claimed B
and described A.

Second, `tools/record-verdict.py` made `--sha` optional and otherwise selected the PR's current
head. A reviewer could read a packet for A, return PASS, the PR could advance to B, and the ordinary
recording command would post that PASS to B. The conformance gate correctly treated an *already
recorded* status on A as stale; the defect was that recording could move the evidence to B before
the gate saw it.

The missing object is the handoff between those commands: a machine-readable identity for the
actual review packet.

## Decision

### 1. A packet is assembled from one immutable reviewed tree

The PR head SHA is read once. The tool ensures that exact commit object exists locally without
switching the caller's branch, then creates a private detached temporary worktree pinned to that
SHA. All repository material used to assemble the packet is read from that worktree, including
provenance, policy, overlays and the reviewed commit's `tools/entry-packet.py`.

The caller's branch, index, uncommitted files and other agents' worktrees are not inputs. The
temporary worktree is removed on success and on failure.

If the PR head object is absent, the tool fetches the PR head without checking it out and then
verifies that the obtained object is exactly the SHA GitHub reported. Failure to obtain that exact
object is a refusal; the current checkout is never a fallback.

### 2. The diff has two immutable endpoints

The normal base is the PR's GitHub-reported base commit OID. A caller may name another base ref,
but it is resolved once to a commit before packet assembly. The manifest records the resolved base
commit and the reviewed head commit; the diff is produced only from those immutable identities.

A symbolic name such as `origin/main` is never the identity of the reviewed diff.

### 3. Every packet has review-packet format 1

Beside the Markdown packet, `review-packet.py` writes deterministic JSON whose
`reviewPacketFormat` is `1`. It records:

- the pull-request number;
- the exact reviewed commit;
- the exact resolved base commit;
- the deterministic Markdown packet filename and SHA-256;
- SHA-256 identities for the reviewed tree's `.github/agent-policy.json`,
  `provenance.json`, and `tools/entry-packet.py`;
- every generated entry packet independently, by entry id, deterministic filename and SHA-256;
- when an external restored package map is supplied to entry-packet generation, its content
  SHA-256 as an input identity.

The serialization is stable and contains no clock time, random value, hostname, temporary
directory or absolute worktree path. Artifact roles, entry ids and filenames are unique or the
packet is refused.

The Markdown packet refers to companion files by deterministic basename, not by the caller's
temporary output path, so moving the packet bundle does not change what it means.

### 4. Verdict recording consumes the packet identity

A verdict that can satisfy the review gate requires `--packet <manifest>`.
`record-verdict.py` does not infer the reviewed SHA from the current PR head.

Before posting anything it:

1. parses format 1 and refuses unknown or malformed shapes;
2. requires the manifest PR number to equal `--pr`;
3. re-hashes the actual Markdown packet and every bound entry packet;
4. resolves the manifest's reviewed commit locally and re-hashes each bound repository artifact
   from that immutable Git tree;
5. reads the review policy from that reviewed tree to map the reviewer id to the status context;
6. if `--sha` is supplied for compatibility, requires it to equal the manifest reviewed commit;
7. posts the verdict only to the manifest's reviewed commit.

A changed packet, changed entry packet, altered digest, substituted policy/provenance identity,
wrong PR or conflicting `--sha` is a refusal.

The manifest is an integrity relationship, not a signature. Coordinated malicious fabrication by
an actor who can rewrite all local evidence and post statuses remains inside 0029's explicitly
separate authentication boundary.

### 5. A moved PR makes the packet stale; it does not retarget it

If a packet names A and the PR now heads at B, recording is allowed **on A only** as historical
evidence and prints that it satisfies no current gate. This preserves 0029's existing useful
historical behavior while eliminating the dangerous default.

PASS and FAIL obey the same identity rule: both are facts about the bytes reviewed. The workflow
consequence remains separate. The conformance gate asks for required PASS contexts on the current
head, while a configured recorded failure retains the blocking semantics 0029 already defines.
Changing the evidence identity does not weaken failure policy.

### 6. Legacy packets are readable evidence, not format-1 authority

Old Markdown-only review packets remain human-readable historical records. They do not contain the
machine relationship needed to establish the new guarantee, so `record-verdict.py` does not turn
one into a new gating status. A new packet must be generated under format 1.

Produced engines receive this guarantee when they receive the new managed rail recipes through
`factory produce`; historical engine commits and historical review statuses are not rewritten.

## Rejected alternatives

**Require only `--sha`.** Rejected. It leaves packet contents free to come from another checkout
and relies on an operator to copy the right identity between two commands.

**Require local HEAD to equal the PR head.** Rejected. It couples review to the caller's mutable
worktree, excludes harmless concurrent work, and still admits dirty-working-tree material.

**Use the current PR head when recording.** Rejected. That is the reproduced failure.

**Put a SHA in Markdown and parse it.** Rejected. Human prose is not a machine contract and can be
edited independently after review.

**Hash only the diff.** Rejected. The reviewer also consumes issue/PR context, provenance, entry
packets and policy. The human packet itself must be bound.

**Sign the manifest or authenticate the model.** Deferred. Content identity and immutable Git
objects solve #334's question — what bytes were reviewed. Who cryptographically attests to the
verdict is 0029's separate trust boundary.

## Consequences

- A valid verdict now has a mechanical chain from PR to reviewed SHA to immutable snapshot to
  packet bytes to manifest to the exact commit status.
- Advancing a PR invalidates the old packet for the merge gate without erasing its historical
  status.
- Review-packet generation is safe from a dirty or differently checked-out caller tree.
- Packet generation may perform a fetch when the exact GitHub-reported PR head object is absent,
  but it never switches the active checkout.
- Review bundles gain one deterministic JSON manifest; no historical review artifact is mass
  migrated.
- 0029's statement that a verdict cannot be replayed onto unread bytes becomes mechanically true
  for format-1 packets. Its statement that provider identity is not authenticated remains true.
