# Review evidence: what a review covered, and what a repair invalidates of it

This document is managed by rules-factory (decision 0071). [`AGENTS.md`](../AGENTS.md) §7 is the
contract; this says how the parts fit and how to read what they write.

## Why evidence is reused at all

A semantic review is the most expensive thing this team does, and it is expensive in the right
place: it is where a fluent, well-tested implementation of the wrong rule is caught. What was
wasteful was rereading everything after every repair. A verdict is bound to one commit, so a
one-line repair ended it, and the next review reread every entry, the whole implementation and
the full diff — most of it bytes the repair never touched. A chain of eight repairs paid for eight
complete rereads.

So a review now records **what it covered**, and the review after a repair rereads only what the
repair could have changed. The rule is:

> Verification scales with the semantic impact of a change, not with the size of the engine or of
> the conversation. A changed commit alone invalidates nothing.

## The lifecycle

1. Implement, run the gate (`./scripts/validate.sh full`), record the mutations.
2. **Attack your own work** before anyone is paid to: [`docs/adversarial-self-review.md`](adversarial-self-review.md),
   one committed record per entry under `reviews/self-review/`.
3. **Full semantic review** — `tools/review-packet.py <pr> --role semantic --package-map <map>`.
4. On FAIL: repair the blocking findings, and commit the attestation the recorder wrote under
   `reviews/attestations/` in the same repair.
5. **Delta review** — `tools/review-scope.py delta <pr> --prior reviews/attestations/<file> --package-map <map>`.
   It writes a packet of only the invalidated claims, or refuses and says why a full review is
   owed.
6. Repeat 4 and 5 until a delta passes.
7. **Final acceptance review** — `tools/review-packet.py <pr> --role semantic --review final --prior <last attestation> --package-map <map>`.
   The whole slice, once, from a clean snapshot. Only a full or final PASS posts the verdict the
   merge gate requires.

A full review that passes first time needs no final review: it already read everything at the
head being merged.

## What can be reused, and what cannot

A review's attestation lists **claims** — one per entry of the pull request's slice, and one per
invariant `reviews/invariants.json` declares — and, for each, every **unit** it rests on with a
fingerprint:

| Unit | What it is |
|---|---|
| `entry:<id>` | the map's entry merged with its overlay row |
| `file:<path>` | a hand-written C# file under `src/` or `tests/` |
| `corpus:<sourceId>` | the corpus's content hash |
| `map-frame:<package>`, `charter`, `policy:review`, `factory` | what every claim rests on at once |
| `foundational:<path>`, `decision:<path>`, `unreadable:<path>` | files that can change every rule |

A claim's units are computed, never declared: the entry, every entry it depends on through
`dependsOn`, `enabledBy`, `suspendedBy`, `crossReferences[].resolvedBy` and `derivedFrom`, the
corpora they cite, and the files `implementedIn` and the overlay's tests name, **closed over the
lexical reference graph** — a file depends on every file declaring a type or extension method whose
name it mentions. The graph over-approximates on purpose.

A prior claim is **retained** only when every unit it recorded is unchanged and its dependency set
has not grown. A changed file no claim rests on is reviewed as a claim of its own. A claim the prior
review failed is reviewed again whether or not anything moved. Everything else is invalidated, with
a reason per unit.

## When a full review is mandatory

`tools/review-scope.py delta` refuses, naming the reason, when:

- there is no prior attestation, it cannot be proved to be the one recorded, or it has no scope;
- the charter, the review policy, the factory commit, a map's frame or a cited corpus changed;
- a foundational file (project, props, lock, SDK, package source, `global using`) or a decision
  record changed;
- a changed file under `src/` or `tests/` is not C#, so no edge into it can be computed;
- a generated file does not hash to what `provenance.json` records;
- more than half of the slice's entries changed in the map, or the repair invalidated more of the
  prior claims than `review.deltaCeiling` in `.github/agent-policy.json` (default one half) allows.

"The head changed" is never a reason, and an attestation that gives it is refused.

## Why a reviewer starts from a clean session

The packet is the interface; the conversation is not. A delta packet is built from git, the map and
the committed attestation, and carries no implementation transcript, no earlier reviewer's
reasoning, and no summary of the pull request. A reviewer launched fresh, with nothing but the
repository and the packet, has everything the review needs — and a reviewer handed the
conversation is anchored by it and pays for every token of it on every turn.

## Reading what the tools write

```bash
tools/review-scope.py impact --prior <attestation> --package-map <map>   # what this head invalidates, and why
tools/review-scope.py state --package-map <map> --entry <id>              # the claims and units at a commit
tools/review-scope.py verify <attestation>                                # is this the attestation that was recorded?
tools/review-scope.py telemetry                                           # review cost and reuse, from reviews/attestations/
```

Every packet is written with a `*.review.json` identity beside it, and a packet that carries entry
evidence with a `*.scope.json`: the state the verdict will attest. The recorder writes the
attestation beside them and puts its SHA-256 in the commit status. An attestation is plain,
sorted JSON; its `claims` say what was reviewed and what retained, `invalidated` says why each prior
claim was not retained, `fullReviewReasons` says why a review was full, and `telemetry` holds the
packet's size in bytes, files and entries. Token counts appear only when the environment reported
them.

## Integrity

A committed attestation is reused only when its SHA-256 is the one the recorder put in a status at
its reviewed commit, that commit is an ancestor of the head, and the maps and engine it names are
the ones that commit declared. An attestation edited afterwards, of another commit, or of another
map is not reused: the next review is a full one and says why. This is an integrity check, not
authentication — anyone who can write a commit status can forge a self-consistent record, exactly
as §7 says of verdicts.

## Migrating an engine produced before this

A `factory produce` update brings the tools, the model (`scripts/factory/reviewscope.py`) and these
documents. Nothing already recorded is reused: a commit status with no attestation says nothing
about what was covered. The first review after the update is therefore a full one
(`no-prior-attestation`), and its attestation is the baseline every later delta is bounded by. An
attestation written by a packet with no entry evidence says it is unscoped, and is never a delta's
parent either (`legacy-evidence-unscoped`).
