# The collapse trial — how many premature collapses the validator sees

[0014](../../docs/decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md) measured the
mechanical checks against 15 injected comprehension errors and caught 1. This measures one error,
the one [0034](../../docs/decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md)
is about: a **premature collapse**, a mapper choosing between two readings the corpus does not
settle and recording the choice as `clarity: clear`.

```bash
python3 examples/collapse-trial/collapse.py                    # the table below
python3 examples/collapse-trial/collapse.py --json results.json
```

## The method

Every committed map has known unresolved entries — the ones it records as ambiguous. Each is
collapsed in turn, one per run, on a copy:

```python
entry["clarity"] = "clear"      # the corpus determines exactly one answer
del entry["ambiguity"]          # so there is no question, no fate and no reason
```

Nothing else is touched, because the map that results is the map the mapper would have written
had they never noticed the second reading. A committed map's bytes are never written: the example
tree is mirrored as symbolic links in a temporary directory and only the map under measurement is
replaced by a real file, since a map change invalidates its review
([0017](../../docs/decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)).

A collapse is **caught** when some check fails that did not fail on the clean map. Every clean
map passes every check, so the baseline is zero and nothing is credited to collateral damage.

## The result, 2026-09-17

| map | collapses | caught | missed |
|---|---:|---:|---:|
| `faa-part-107-temporal/corpus-map-2020-01-01.json` | 7 | 0 | 7 |
| `faa-part-107/corpus-map.json` | 10 | 3 | 7 |
| `hoyle-backgammon/corpus-map.json` | 7 | 2 | 5 |
| `srd-52-combat/corpus-map.json` | 19 | 5 | 14 |
| `srd-52-conditions/corpus-map.json` | 13 | 2 | 11 |
| `tax-121-principal-residence/corpus-map.json` | 8 | 0 | 8 |
| **total** | **64** | **12** | **52 (81%)** |

| | caught | missed |
|---|---:|---:|
| before 0034 | 4 of 64 | 60 (94%) |
| after 0034 | 12 of 64 | 52 (81%) |

Which check fires, and it is only ever two:

- **`superposition`, 8.** The blind second mapping read the passage as ambiguous, the adjudication
  answered *the corpus does not settle it*, and the collapsed map records one reading.
- **`conflicts`, 4.** The collapsed entry was a member of an `ambiguity.conflict`
  ([0007](../../docs/decisions/0007-a-conflict-is-a-question-not-a-pair.md)) and removing it left
  the group with a single member. This is the whole of what the validator caught before 0034, and
  it catches nothing except where the corpus contradicts *itself*.

## What the numbers say

**Every catch comes from a second reader.** Eight from a mapper who had not seen the first map;
four from the corpus stating the rule twice and the mapper recording both. Not one comes from the
entry itself, and that is the argument of 0034 §2 in one line: an entry cannot corroborate its own
doubt, so no field on it could have caught any of these 64.

**The ceiling is how much of each corpus was read twice.** Split by whether the map has an
adjudication record this can read:

| | collapses | caught by `superposition` |
|---|---:|---:|
| the three with a readable record (`faa-part-107`, `hoyle-backgammon`, `srd-52-combat`) | 36 | 8 (22%) |
| the three without (`faa-part-107-temporal`, `srd-52-conditions`, `tax-121-principal-residence`) | 28 | 0 |

`tax-121-principal-residence` has a record and three adjudicated disagreements about certainty,
none of them unsettled — two were ruled for the first map and one for the blind map — so there is
nothing for a collapse there to contradict. The other two maps were never mapped twice, and
`superposition` reports NOT VERIFIED on them rather than passing.

**22% is the rate where the machinery applies at all.** It is not a rate for collapses in general
and it is not a rate for any other corpus: it is 64 collapses in six maps of four corpora, where
the second reading exists for 36 of them.

## How this relates to trial 10

[`validator-attack/`](../validator-attack/README.md) measures a different thing and the two numbers
are not versions of each other.

| | that table | this one |
|---|---|---|
| asks | what does the whole validator catch, across fourteen kinds of damage | what fraction of premature collapses does it catch |
| damages | one entry per map, once per mutation | **every** recorded ambiguity, one at a time |
| denominator for a collapse | 5 (`ambiguous-to-clear`, one per map) | 64 |
| result | 1 of 5 refused, where it was 0 of 5 before 0034 | 12 of 64, where it was 4 of 64 |

Trial 10 asks whether the validator notices a *kind* of error at all; this asks how often it
notices *that* error. The 1 of 5 there is one of the 12 here, and the disagreement between "1 of 5"
and "12 of 64" is arithmetic about different subjects, not two answers to one question.

## Limits

- **A collapse of an ambiguity nobody recorded is not in the denominator.** This collapses
  ambiguities the map *has*. The map that never recorded one is exactly the map 0014's natural
  case found, and nothing here measures it.
- **One collapse at a time.** Two collapses in one map might interact; that is not tested.
- **The collapse is the maximal one.** It removes the `ambiguity` block entirely. A mapper who
  kept the block and changed `fate` to `decision`, or narrowed the `question`, leaves a different
  trace, and the rate for those is not measured here.
- **The numbers move when a map is mapped twice**, not when a check is improved, and re-running
  this after the next blind mapping is the point of committing it.
