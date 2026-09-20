# 0047 — A mapping-discovered corpus boundary amends admission without rewriting it

## Status

Accepted — 2026-09-19. Records the process decision forced by
[#323](https://github.com/brandonifco/rules-factory/issues/323) during trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)). Extends
[0009](0009-absence-is-a-verdict-with-evidence.md)'s rule that `references` is bounded by what
the corpus names, and preserves [docs/method.md](../method.md)'s Phase-1 requirement that admission
is recorded before mapping.

## Context

Trial 10's Phase-1 manifest was deliberately frozen before a map entry existed. Phase 2 then
quoted § 172.102(c)(7)(ii), which points to § 180.605. The original `references` list for that
corpus has no part-180 boundary. Editing the Phase-1 list in place would make the current boundary
more accurate by making the experiment's claim about what admission knew false.

The same mapping found section-level citations under parts 173 and 178. Those parts were already
declared as referenced-but-not-admitted. `references` names external **corpus boundaries**, not
an exact inventory of every pointer: a `part 173` declaration covers a child such as
§ 173.308(b)(2). Exact section references remain useful where a map field such as
`definedElsewhere.reference` names that exact source id, but they are not required merely because
a pointer names a child of an already-declared part.

## Decision

A corpus keeps its Phase-1 `references` list unchanged. If mapping discovers an external corpus
boundary that list did not declare, the corpus may add `referenceAmendments`:

```json
"referenceAmendments": [
  {
    "discoveredDuring": "mapping",
    "decision": "0047",
    "references": [
      { "sourceId": "cfr-49-180", "citation": "part 180", "admitted": false }
    ]
  }
]
```

The amendment is **additive only**. It can contain only the provenance above and new
referenced-but-not-admitted references. Each correction reference has exactly `sourceId`,
`citation` and `admitted: false`; a CFR part or section citation must name the same structural
identity as its source id. An amendment cannot repeat an existing boundary or target a corpus
already admitted by the manifest. It cannot change `contentHash`, `hashDerivation`, `asOf`,
`licence`, verification, quotation, adapter, locator grammar, or admission status. Admitting a
corpus remains a separate Phase-1 act.

Every consumer asking for the current boundary reads the original `references` plus all valid
`referenceAmendments`. The original list remains the mechanically inspectable statement of what
admission knew before mapping; the amendment says what mapping learned later.

A broad part-level reference is coverage of sections beneath that part. A section-level reference
is exact and does not become a prefix wildcard. This is boundary semantics, not pointer identity:
the pointer detector still has to preserve the complete designation the corpus printed.

## Alternatives considered

**Edit `references` in place and rely on git history.** Rejected for this trial. Git can recover
old bytes, but the current artifact would no longer distinguish admission knowledge from a later
correction, while the README explicitly uses that distinction as experimental evidence.

**Add every section mapping encountered.** Rejected. It turns a corpus boundary into a duplicate
pointer inventory. Trial 10 already declares parts 173 and 178, so adding § 173.185 or § 178.702
would add no boundary information.

**Put the omission only in the Trial README.** Rejected. The operational manifest would remain
knowingly incomplete, and consumers inspect the manifest rather than prose to learn the engine
boundary.

## Consequences

Trial 10 adds one operational boundary, part 180, as a mapping-time amendment to
`cfr-49-172.102`. Its original Phase-1 `references` arrays and corpus pinning facts remain
byte-for-byte unchanged. Parts 173 and 178 already cover the newly observed child-section
pointers, so no redundant section references are added.

A malformed amendment is refused. In particular it cannot admit a target, repeat an existing
reference, or carry unrelated corpus facts. `definedElsewhere` and other consumers resolve
against the operational union, so a correction is not documentation that tooling ignores.
