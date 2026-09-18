# 0040 — A mapping protocol is about one corpus, and a map has one protocol per corpus it cites

## Status

Accepted — 2026-09-18. Records the decision on
[#304](https://github.com/brandonifco/rules-factory/issues/304), recorded in advance as point 3
of [#284](https://github.com/brandonifco/rules-factory/issues/284) and forced by trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)).
**Extends [0039](0039-the-manifest-pins-every-corpus-a-map-cites.md)**, which established that a
map may cite several corpora, and **[0032](0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md)**,
which made the mapper a subsystem with a protocol of its own. The specification is
[mapper.md](../mapper.md).

## Context

The protocol exists because of [#208](https://github.com/brandonifco/rules-factory/issues/208).
The cross-reference detector read a phrase list against a corpus that points by naming a defined
term, found **0 pointers in passages holding 51 references**, and left 102 of 107 declarations
obliged by nothing. The phrase list was not a gap in a list; it was the wrong interrogation for
that corpus, and nothing recorded which interrogation was right. `tools/mapper/protocol.py` says
what that cost bought:

> A protocol that names a mechanism no detector owns is refused rather than quietly skipped,
> because a declared interrogation nobody performs is worse than none — it reads as coverage.

A map had exactly one protocol — `mapping-protocol.json` beside it — about exactly one corpus,
`protocol["corpus"]`, a single `sourceId` checked against the manifest.

0039 then established that a map may cite several corpora, because a served-document boundary is
a delivery artifact and must not split one mapping problem. Trial 10's map cites two, and they do
not communicate rules the same way:

| | § 172.101 | § 172.102 |
|---|---|---|
| a rule is stated in | a **table row** (0035) | a **prose paragraph inside an `EXTRACT`** (0036) |
| it points with | a bare code in column 7 — `IB2`, `T4`, `W31`, `N40`, `148` | an ordinary section designation |
| an English pointer phrase | none anywhere near the cell | present |

One protocol naming `cfr-49-172.101` would be a true account of the first and a false one of the
second. Nothing would refuse it. Every check downstream — `validate.sh` steps 4, 5 and 7 — would
report on a walk that is wrong for half the map, which is #208's failure repeated with the
mechanism known in advance.

## Decision

**A protocol is about one corpus. A map has one protocol per corpus it cites.**

### 1. Naming

- `mapping-protocol.json` — a map citing one corpus. Every map committed before trial 10, and
  none of their files move.
- `mapping-protocol-<sourceId>.json` — one per cited corpus, once a map cites several. A
  single-corpus map may use this name too.

### 2. Refusals

- **A cited corpus with no protocol** is refused, naming which. That is the state the file exists
  to make impossible: nothing says how this corpus was read.
- **A `mapping-protocol-<sourceId>.json` for a corpus the map does not cite** is refused. A
  leftover sitting beside a map, claiming to govern a corpus nobody reads, is a declared
  interrogation nobody performs.
- **A protocol whose `corpus` the map does not cite** is a problem even when the manifest declares
  it. Declared is not read, and the manifest declares corpora a given map may never touch.
- **`--protocol`**, which names one file, is refused for a map citing several, rather than letting
  one protocol stand for all of them.

### 3. Why not one protocol naming several corpora

Rejected. `units`, `pointerMechanisms`, `requiredSweeps` and `adapterReach` are each a statement
about *how a corpus communicates rules*. One list across a table-and-codes corpus and a prose
corpus would have to be the union, and a union says of each corpus things that are true only of
the other. The protocol's whole value is that it is specific enough to be wrong, and a union
cannot be wrong about either corpus in particular.

The concept does not change here. A protocol is still about one corpus; what changes is that a
map may have more than one of them, exactly as it may cite more than one corpus.

## Consequences

- **No committed map moves.** All six resolve their own `mapping-protocol.json`, held by a test
  that enumerates them.
- **The inventory and the sweeps still walk the principal corpus only.** That is a separate
  defect with the same root, filed as [#305](https://github.com/brandonifco/rules-factory/issues/305)
  and deliberately not fixed here: `mapper sweeps` chooses the principal corpus's protocol and
  says so where it does it. A protocol per corpus is the precondition for the walk per corpus,
  not a substitute for it.
- **Trial 10 can state how each of its corpora is read**, which is the last structural blocker
  between the admitted corpus and its map.
