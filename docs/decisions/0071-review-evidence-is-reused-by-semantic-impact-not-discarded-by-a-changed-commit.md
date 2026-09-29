# 0071 — Review evidence is reused by semantic impact, not discarded by a changed commit

## Status

Accepted — 2026-09-29. Records the remediation for
[#532](https://github.com/brandonifco/rules-factory/issues/532).
**Extends [0053](0053-a-review-verdict-binds-the-exact-packet-and-reviewed-commit.md) and
[0057](0057-a-verdict-rests-on-entry-evidence-read-once-and-bound-to-the-reviewed-commit.md)**: a
verdict still binds the exact packet and the exact reviewed commit, and a merge still needs a
comprehensive verdict at the commit being merged. What changes is that a verdict now leaves a
durable record of *what it covered*, so the review after a repair can be bounded by what the repair
could have changed.

## Context

0053 bound a verdict to one immutable reviewed head, and the gate requires that verdict at the head
being merged. Nothing recorded which claims a review had covered, or which bytes each claim rested
on. So a verdict was all-or-nothing about a commit, and the only honest response to a new commit
was to review everything again.

On a produced engine that is ruinous in exactly the case review is for. A semantic FAIL is answered
by a repair commit; the repair moves the head; the next review rereads the governing entries, the
whole implementation slice, the full diff and the evidence. One produced engine spent roughly half
of a ~29M-token session on those rereads, and the reviewers were right each time. The cost curve
was

    review cost ≈ rounds × size of the accumulated slice

where it should be

    review cost ≈ first full review + semantic impact of each repair + one final acceptance review

The reviews were not the waste. Discarding what they had established, because a SHA changed, was.

## Decision

**Verification scales with the semantic impact of a change, not with the accumulated size of the
engine or of the conversation. A changed SHA alone never invalidates semantic review evidence.**

Eight parts. The machinery is one module of the generator, `tools/factory/reviewscope.py`,
vendored into every engine as `scripts/factory/reviewscope.py` so that the engine's tools compute
with the factory's code and cannot drift from it, and one new rail, `tools/review-scope.py`, beside
the changed `review-packet.py` and `record-verdict.py`.

### 1. A review leaves a deterministic attestation

`record-verdict.py` writes an **attestation** (`attestationFormat` 1) beside the packet it consumed
and puts the attestation's SHA-256 in the commit status it posts. It names the project, the
reviewed and base commits, the review type (`full`, `delta` or `final`), the reviewer, the charter
and its digest, the packet identity and digest, every map and corpus by digest, the **claims**
reviewed — each entry of the slice and each declared invariant — with the dependency units and
fingerprints each rested on, the implementation files and corpus locators examined, the result, the
blocking findings and the non-blocking observations, the evidence used, the parent attestation,
which prior claims it retained, which it invalidated and why, the reasons a full review was
required, and telemetry. Its bytes are canonical JSON; the only wall-clock value is under `audit`,
which the digest excludes, so the same review recorded twice is the same attestation.

`reviewscope.validate_attestation` is the one statement of what a well-formed attestation is: a
PASS carries no blocking finding and a FAIL carries at least one; a full or final review reviewed
every claim and retained none; a delta has a parent and reviewed every claim it invalidated; a full
review that has a parent names a reason, and every reason is one of the codes in part 3.

### 2. What a repair invalidates is computed, never declared

A claim's dependencies are **units**, each with a fingerprint: the merged map entry and its overlay
row, every entry it depends on through `dependsOn`, `enabledBy`, `suspendedBy`,
`crossReferences[].resolvedBy` and `derivedFrom` (transitively), the corpus each cites, and the
implementation and test files each is anchored to — `implementedIn` and the files declaring the
tests the overlay names — **closed over a lexical reference graph** of the engine's C#: a file
depends on every file that declares a type or extension method whose name it mentions. The graph
over-approximates on purpose; a name that is also a word adds an edge, never loses one.

A prior claim is **retained** only when every unit it recorded still has the same fingerprint *and*
its dependency set at the new head adds no unit it did not record. Everything else is invalidated,
with a reason per unit: `unit-changed`, `unit-removed`, `dependency-added`. A changed file on the
semantic surface that no claim depends on becomes a claim of its own, `change:<path>`, so nothing
that changed escapes review. And a claim that carried a blocking finding in the parent is reviewed
again whether or not its units moved: a finding is answered by review, not by a fingerprint.

Where the dependency cannot be bounded, the expansion is conservative. An entry whose
`implementedIn` names no file depends on every source file; a test the overlay names that no file
declares makes its entry depend on every test file; a file the lexical graph cannot read — any
non-C# file on the implementation surface — forces a full review (part 3). Generated files are not
units: they are a function of map and overlay, which are, and `provenance.json` must hash them
exactly or the full review is forced.

The implementer's word that a change "only touches C" is not an input to any of this.

### 3. A full review needs a reason, and the head changing is not one

A delta turns back into a full review only for a named reason, and `reviewscope.FULL_REASONS` is
the closed list:

| Code | When |
|---|---|
| `no-prior-attestation` | nothing has been reviewed yet; this review is the baseline |
| `prior-attestation-unusable` | the prior is not a valid format-1 attestation of this project, or its integrity cannot be proved |
| `legacy-evidence-unscoped` | the prior records no per-claim dependency fingerprints (an older verdict or packet) |
| `charter-changed` | the semantic reviewer's charter differs from the one the prior was formed under |
| `review-policy-changed` | the `review` section of `.github/agent-policy.json` differs |
| `governing-corpus-changed` | a corpus a claim cites has a new content hash: new rules may exist that no entry covers |
| `map-frame-changed` | anything in a map outside its entries differs (corpus binding, extent, schema) |
| `map-changed-broadly` | more than half of the slice's entries changed in the map |
| `factory-recipe-changed` | the engine was re-produced from another factory commit |
| `foundational-file-changed` | a project, props, lock, SDK or package-source file changed |
| `engine-decision-changed` | a record under `docs/decisions/` changed: it is authority over every entry |
| `dependency-graph-unbounded` | a changed file is one the graph cannot read |
| `generated-provenance-inconsistent` | a generated file's bytes are not the ones `provenance.json` records |
| `repair-too-broad` | the repair invalidated more of the prior claims than `review.deltaCeiling` (default one half) allows |

"The head changed" is not on it, and an attestation carrying any code not on it is invalid. When
the computation finds nothing invalidated and no reason, the impact is `none`: the prior evidence
stands whole, and a comprehensive PASS may be **carried** to the new head (part 6).

### 4. A delta review is given a delta packet

`tools/review-scope.py delta <pr> --prior <attestation>` computes the impact and writes a **delta
packet** and its identity. It carries the prior attestation's identity and result, the prior head
and the new head, the blocking findings being repaired, the claims to review with the reason each
was invalidated, their entry packets, the diff from the prior head restricted to their closure, the
closure's unchanged files by path and digest, their corpus locators, their tests and mutations, the
retained evidence and the invalidated evidence. It carries no conversation. When the impact is
`full` it refuses and prints the reasons instead, so a delta is never made of a change it cannot
bound.

The prior attestation must be **committed** at the new head, under `reviews/attestations/`, and its
digest must equal the digest the recorder put in the status at the prior reviewed commit. An
attestation edited after it was recorded — PASS written over FAIL, a claim's fingerprints changed —
therefore fails to match and is refused, not reused. It is the same integrity boundary 0053 draws: a
person with status-write access can still forge a self-consistent record, and that is out of scope
here as it was there.

### 5. A final acceptance review rereads the whole slice once

A delta PASS is recorded at `<semanticContext>/delta`, which no gate requires. The semantic context
the merge gate requires is posted only by a comprehensive review: a `full` PASS, or a `final` PASS —
`tools/review-packet.py <pr> --review final`, the whole semantic packet read from a clean snapshot,
which must be preceded by at least one delta and must cover every claim of the slice. So a chain of
deltas cannot reach `main` without one complete reread, and that reread is what catches an
invalidation the graph got wrong, an interaction between two repairs, and a reviewer's blind spot.

### 6. Evidence may cross a commit that changed nothing it rests on

When the impact to the current head is `none`, `tools/review-scope.py delta` writes a **carry**
identity instead of a packet, and `record-verdict.py` posts the semantic context at the current head
from it only when the prior attestation is a comprehensive PASS (`reviewscope.may_carry`). This is how
the attestation-only commit that stores the last verdict, or a README fix after acceptance, keeps
the verdict: not because the commit is unimportant, but because every byte the verdict rested on is
proved unchanged. 0053's invariant — a verdict applies only to bytes somebody read — is preserved,
and stated more exactly than a SHA states it.

### 7. A semantic packet needs the implementer's adversarial self-review

Before a semantic, independent or final packet can be written, every entry it names needs a
committed `reviews/self-review/<entry id>.json` that answers each of the twenty classes in
`reviewscope.SELF_REVIEW_CLASSES` — integer extremes, overflow, empty collections, crafted public
input, invalid construction, phase boundaries, order dependence, partial mutation before refusal,
exception leakage, refusal classification, missing content masking a refusal, sentinels, idempotence,
immutability, caller-controlled sizes, exact bounds, exclusive-or, count semantics, action
interactions, invalid intermediate states — with the tests that attack it or a reason it does not
apply, and whose `claimSha256` is the entry's claim digest at that head. A repair that touches the
claim's closure changes that digest, so the attack is redone before the next reviewer is paid. The
engine's `docs/adversarial-self-review.md` holds a test template per class.

### 8. The packet is the interface, and review is measured

A reviewer starts from a clean session with a packet; the charters, `AGENTS.md` and
`docs/agent-team.md` say so, and the delta packet is built from git, the map and committed
attestations alone. `tools/review-scope.py telemetry` reads the committed attestations and reports
full, delta and final counts, claims reviewed and invalidated per round, packet bytes, changed files
and entries, closure size, findings and repeated finding categories, repairs before PASS, the reasons
a full review was required, and the evidence reused. No token count is reported unless the caller
supplies one; byte, file and entry counts are the proxies.

## Measured

**What a reviewer is handed.** `tools/review-cost-benchmark.py` replays a repair chain over three
real maps — FAA part 107 (regulatory), 49 CFR 172.101 (hazardous materials), SRD 5.2 combat (a
game) — with a 24-entry slice implemented one handler per entry, coupled exactly as each map's
`dependsOn`, `enabledBy` and `suspendedBy` declare, a shared primitive under a third of them, and a
test file each. The old model hands over a complete packet at every head; the new one a full packet,
a delta per repair, and a final packet when the chain ended on a delta. No token count is invented:
bytes, entries, implementation bytes and corpus-evidence bytes are what is measured, and every run
prints the same table.

| map | findings | repairs | comprehensive reviews, old → new | bytes presented, new / old | claims reused |
|---|---|---|---|---|---|
| faa-part-107 | local | 7 | 8 → 2 | 162,322 / 445,312 (36%) | 160 |
| hazmat-172-table | local | 7 | 8 → 2 | 182,085 / 508,928 (36%) | 160 |
| srd-52-combat | local | 7 | 8 → 2 | 159,476 / 444,600 (36%) | 160 |
| each of the three | local | 2 | 3 → 2 | 76–79% | 45 |
| srd-52-combat | hub | 7 | 8 → 2 | 183,725 / 444,600 (41%) | 154 |
| hazmat-172-table | hub | 7 | 8 → 3 | 234,677 / 508,928 (46%) | 138 |
| faa-part-107 | hub | 7 | 8 → 8 | 445,312 / 445,312 (100%), every repair `repair-too-broad` | 0 |

"Local" findings land on the entries of the slice fewest others rest on; "hub" findings on the two
most rested on. The last row is the model being right, not the model failing: in part 107,
`waivable-regulations` cross-references nearly every operating rule, and a rule that suspends by
reference to it rests on all of them, so a repair there *is* a change to most of the slice and is
reviewed as one, for a stated reason, at no more than the old cost. The worst any chain does is one
extra comprehensive review — the final one after a delta — and `tools/tests/test_review_cost_benchmark.py`
holds both bounds.

**What the rails were watched catching.** `tools/tests/factory/test_review_scope_mutations.py`
applies twenty mutations to `reviewscope.py` and runs the scenarios against each; all twenty are
killed. Among them: a changed entry or file marked unaffected, a map dependent or a shared
primitive's caller dropped from the closure, a grown dependency set not invalidating, the wrong
prior head, map digest or corpus digest accepted, an edited attestation accepted, a changed charter
accepted, a delta PASS that skipped an invalidated claim, a failed claim not reviewed again, a delta
PASS posting the merge gate's context, a final review retaining evidence, a changed head treated as
a reason, legacy unscoped evidence reused, a retained claim at unrecorded fingerprints, a stale
self-review accepted, and a carry across a changed state.

## A stronger invariant, kept

The assignment asks that a changed SHA never invalidate review evidence. 0053's invariant is that a
verdict applies only to bytes somebody read, and it is kept in its strong form: a **commit status**
still ends at the next commit, the gate still requires one at the head being merged, and nothing
here makes a status inherit across commits. What survives a commit is the *evidence* — the
attestation's per-claim fingerprints — which bounds the next review. The one place a status is
posted without a new review is a carry, and only when every unit the comprehensive PASS rested on
is proved byte-identical at the new head: the bytes somebody read are the bytes being merged,
which is 0053's own condition, checked unit by unit rather than by commit.

## Alternatives considered

**Carry a verdict across any commit that does not touch the semantic paths.** Rejected. It is the
cheap half of this decision without the other: a repair *on* the semantic surface is the common
case, and a path filter says nothing about which claims it touched.

**Let the implementer or reviewer declare the change's scope.** Rejected. The assignment asks for
structural evidence because a declaration is exactly what a plausible, wrong change produces.

**A precise C# dependency analysis.** Rejected for now. A Roslyn pass would need the SDK and a
restore inside every packet run, which 0057 already measured as too costly for the snapshot; the
lexical graph over-approximates, is standard library, and fails towards reviewing more. The unit
model does not care how the edges are found, so a precise analyser can replace it later.

**Drop the final review when every delta passed.** Rejected. The final review is what protects
against an invalidation the graph got wrong and against interactions between repairs; it is paid
once, at the boundary, not per round.

**Keep attestations outside the repository.** Rejected. A reviewer is to need nothing but the
repository and its committed review artifacts; an attestation that lives only in a scratch
directory is a conversation by another name.

## Consequences

A repair is reviewed at the size of what it could have changed. A PASS at the merge head still
means somebody read every claim of the slice at that head's semantic state, and now the record says
which claims those were.

Existing engines receive this through `factory produce`: the rails are managed files and the module
is vendored. Their old verdicts stay readable and are never reused: with no attestation, the first
review after the update is a full one (`no-prior-attestation`), and it establishes the baseline.
A format-2 review identity can still be recorded, and its attestation says it is unscoped, so it
cannot become a delta's parent.

The self-review record is new work for every entry reviewed after the update. That is the point:
it moves the cheap attacks to before the expensive reviewer.

The charter changing invalidates every prior attestation, so this very change forces one full
review of any engine mid-chain when it is produced into it. That is the rule working.
