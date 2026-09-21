# 0057 — A verdict rests on entry evidence read once and bound to the reviewed commit

## Status

Accepted — 2026-09-21. Records the remediation for
[#371](https://github.com/brandonifco/rules-factory/issues/371) and
[#372](https://github.com/brandonifco/rules-factory/issues/372), the two residuals of
[#356](https://github.com/brandonifco/rules-factory/issues/356) filed by round six
([#375](https://github.com/brandonifco/rules-factory/issues/375)).
**Extends [0053](0053-a-review-verdict-binds-the-exact-packet-and-reviewed-commit.md)** at the one
input it left unbound, and adds the consequence #372 asked 0053 to gain. It does not authenticate
a reviewer, and the trust boundary 0053 §3 records is unchanged.

## Context

0053 bound a verdict to one immutable reviewed commit: the packet is assembled from a detached
snapshot of that head, its bytes are hashed into a `*.review.json` identity, and the recorder
refuses to post a status anywhere else. #356 then found the hole in the middle of it. The entry
packets — the one artifact a semantic reviewer is told to read **before** the diff — are built
from a map, and the map is not in the reviewed tree: it is a package (0015), named by
`--package-map` or resolved through MSBuild. #357 closed the `--package-map` half by hashing those
bytes and holding them to `map.files[role="map"]` in the reviewed commit's `provenance.json`, and
recorded the other half honestly rather than claiming otherwise: `"readSha256": null`,
`"readFrom": "MSBuild inside the reviewed tree -- NOT VERIFIED"`.

An independent review of that remediation (AGENTS.md §6) found that both halves were still open,
in different ways.

**The check and the use were two opens of one pathname.** `map_read_from()` opened
`--package-map`, hashed it and compared; `entry_packet()` then started a subprocess which opened
the same name again. Anything that replaced the file between them produced entry packets built
from map B carrying the checked digest of map A. A packet is assembled outside the repository, by
whoever is reviewing, so the window is real on a shared machine.

It is also reproducible without a race. The substitution below is performed by the subprocess's
own interpreter at startup — after the hash, before the map is read — and the altered evidence
reaches the reviewer under a passing check:

```
AssertionError: 'THE REVIEWER IS READING BYTES NOBODY COMMITTED' unexpectedly found in
'# Entry packet: `altitude-limit` … "evidence": "THE REVIEWER IS READING BYTES NOBODY COMMITTED"'
: the digest was checked on one read of --package-map and the entry packet was built from another
```

That is #356's finding exactly, moved from "never checked" to "checked, then not used".

**Nothing acted on the honest `null`.** `record-verdict.py` accepted such an identity and posted a
passing status, so a semantic `pass` could stand for entry bytes nobody proved the reviewed commit
carried, indistinguishable in the record from one formed on checked evidence.

**And a refusal was not free.** `main()` created the output directory before `build()` could
refuse, so a mismatched `--package-map` left a newly created empty packet directory behind,
including under `--stdout`.

### What the unbound path actually produces

#372 set out three options and asked for a decision rather than a split. The measurement that
decides it is what the unbound path produces today, run against a produced engine:

```
## 3. The entries, as the map has them

Read these **before** the diff. The overlay came out of the reviewed commit. **The map did not: it
was resolved by MSBuild inside the reviewed tree and its identity was NOT VERIFIED …**

- `altitude-limit`: **no packet** — entry-packet: REFUSED -- MSBuild returned no single
  RulesFactoryMap item; restore first, or pass --package-map
```

The exit code was 0, and the packet, its `*.review.json` identity and a recordable `pass` followed.
The reason is structural, not incidental: `RulesFactoryMap` comes from the restored package's
`build/<id>.props`, and the reviewed snapshot is a **freshly created detached worktree** with no
`obj/` and no restore — which is why `scripts/validate.sh` asks MSBuild the same question only
after its own locked restore, under `if [[ "$RESTORED" -eq 1 ]]`.

So the unbound path does not merely produce unverified entry evidence. It produces **no entry
evidence at all**, and a verdict recordable on it.

## Decision

**A review packet identity is written only when the entry evidence it names exists and was built
from map bytes bound to the reviewed commit; a verdict is recorded only from such an identity; and
a refusal leaves nothing.** Four parts.

### 1. The map is read once, and the entry packets are built from those bytes

`review-packet.py` reads `--package-map` once, hashes what it read, holds that digest to
`map.files[role="map"]`, and writes those exact bytes into this run's own private directory. The
`entry-packet.py` subprocess is handed that copy. There is no second open of the caller's path, so
there is nothing to substitute between the check and the use.

The copy is deliberately **not** put under the packet's `--out`, which #371 suggested. `--out` is a
shared, predictable location — `$RULES_ENGINE_PACKET_ROOT`, or a directory beside the system
temporary one — and a copy there is open to the same substitution the fix exists to stop. The
directory `mkdtemp` already made for the reviewed snapshot is private to the process, and the
`finally` that removes the snapshot removes it.

### 2. A refusal leaves nothing

Nothing reaches `--out` until every refusal has passed. The human packet, the entry packets and the
identity are assembled in the private directory and written in one place at the end, so a refused
packet creates no directory and writes no file — the map-mismatch refusal, the moved-pull-request
refusal, and every other one alike. `--stdout` now genuinely writes nothing at all: it previously
left the entry packets on disk while describing itself as display-only.

### 3. A packet that cannot carry its evidence is not written as an identity

For file output, a packet that names an entry is refused unless every named entry has a packet and
the map those packets were built from was checked. Both refusals name the entry and the remedy.

`--stdout` keeps the unbound path: it assembles the packet, says in section 3 that the map's
identity was **NOT VERIFIED**, and writes no identity, so nothing can be recorded from it. The line
is 0053's own: a packet is either evidence a verdict can be recorded from, or it is for reading.

The identity's `reviewContext.map` therefore carries `readSha256` whenever it names an entry
packet; a packet naming no entry never reads a map at all, and says so in `readFrom` rather than
claiming an MSBuild resolution that never happened.

### 4. The recorder checks the relationship, rather than trusting the producer's summary

`record-verdict.py` refuses an identity that names entry packets and carries
`reviewContext.map.readSha256: null`, naming the remedy. Where a digest is present it must equal
`declaredSha256`, the digest the reviewed commit declares, so an identity that claims a bound read
of some other map is refused as well. An identity naming no entry packet never read a map and is
unaffected.

## Alternatives considered

**#372's option 2 — verify the MSBuild-resolved path too.** Rejected on the measurement above, and
it was the option the issue thought most likely right. Resolving the map inside the reviewed
snapshot requires a full `dotnet restore` of a throwaway detached worktree, per packet: the SDK,
the network and minutes, to obtain a path the caller already has. That is not a cost worth paying
for a convenience, and until the restore is added the option delivers nothing at all, because the
resolution it would verify cannot succeed in an unrestored snapshot. If the reviewer's own restore
is later made available to the snapshot cheaply, this decision does not stand in the way: the
binding rule is about the bytes, not about where they came from.

**#372's option 3 — record the weaker verdict under its own status context.** Rejected. It adds a
context to `.github/agent-policy.json`, a rule to `conformance-gate.py`, and a configuration
decision each engine has to get right, in order to keep recordable a verdict formed on evidence
that — measured — does not exist. It also keeps a passing status in the record for a review with no
entry packet in it, which is the state this round was filed about.

**#372's option 1, unscoped: refuse every identity whose `readSha256` is null.** Rejected as
untrue, not as too strong. A pull request that names no entry never causes a map to be read, so
refusing it would refuse for a reason that is not the case, and would put a map package in the way
of reviewing a change to a document. The rule is stated about entry evidence, which is what is
actually at stake.

**Refuse at the recorder only, and let the packet be written.** Rejected. The reviewer would find
out after the review, which is the expensive moment. The producer refuses first, and the recorder
holds the same rule independently so that an identity from an older producer, or one edited by
hand, cannot be recorded either.

**Bump `reviewPacketFormat` to 2.** Rejected. Nothing in the identity changes shape: `readSha256`
and `declaredSha256` are format-1 members #357 already wrote, and what changes is that one of them
must be a digest when entry packets are named. A format-1 identity written by the previous producer
for an unbound entry-bearing packet is exactly what must now be refused, and refusing it by content
says why; refusing it by version number would say only that it is old.

**Keep the checked copy under the packet's `--out`,** as #371 suggests. Rejected for the reason in
part 1: it is a shared location, and the private directory costs nothing and is already removed.

## Consequences

An entry packet's bytes now have a digest in the record that is a fact about them rather than a
claim beside them, and a verdict that cites entry evidence cites evidence that was produced and
bound. A `pass` in the record means the same thing every time it appears.

**`--package-map` becomes required for any reviewed change that names an entry**, which is #372's
stated cost for this option. Measured, it is not a new requirement: without it there was no entry
packet to read. The rails say so where the command is given (`AGENTS.md`), and the refusal names
the flag rather than the reviewer's mistake.

**A packet with an unbound map is still readable**, on `--stdout`, and still says so in its own
section 3. What it cannot do is authorize anything.

A reviewer whose engine cannot produce an entry packet — an overlay that does not merge, an entry
id nobody has — is refused a recordable packet and told which entry and why. That is a finding
about the change, surfaced before the review rather than after it.

This closes #371 and #372. The forgeable-manifest limit (#375's second unfiled finding) is
untouched and remains 0053 §3's: a person with status-write access can still manufacture a
self-consistent identity. What is closed here is the gap between what the packet said and what it
had done.
