# The validator

The subsystem that challenges a map's claims, and the only one positioned to say that neither
the mapper nor the factory may claim authority it does not possess.

It is a sibling of the mapper and of the factory, over the map contract they share
([0032](decisions/0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md),
[0033](decisions/0033-the-validator-is-the-adversary-and-validates-the-uncertainty-too.md)). Its
attitude is *I don't care that the mapper thinks this is right; show me.* It imports
`tools/mapcontract/` and nothing else, so a map written by hand is validated exactly as one the
mapper produced — which is the test of whether the boundary is real.

It is not the mapper's checker. Producer and verifier stay apart for the reason production code
is not its own only test oracle.

## Where it lives

| | |
|---|---|
| [`tools/mapvalidator/`](../tools/mapvalidator/__init__.py) | the checks, as modules |
| [`tools/check-map.py`](../tools/check-map.py) | what `tools/build-check-map.py` joins them into: one standard-library file, because a map package ships it ([0015](decisions/0015-a-map-is-published-as-a-versioned-package.md)) and the factory imports it ([0016](decisions/0016-a-map-package-is-data-not-code.md)) |
| [`tools/check-locators.py`](../tools/check-locators.py) and the two per-grammar checkers under `examples/` | the evidentiary half: does the cited text exist where the map says |
| [`tools/check-map-review.py`](../tools/check-map-review.py) | every map carries a review of its exact bytes ([0017](decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)), and a `blind-second-mapping` review names the staging record of what its mapper was given, or says out loud that it has none ([#223](https://github.com/brandonifco/rules-factory/issues/223)) |
| [`tools/pack-map.py`](../tools/pack-map.py) | a map that passed becomes a version |
| [`tools/mutate-map.py`](../tools/mutate-map.py) | the adversary turned on itself: it damages a committed map one named way at a time and measures what is refused ([trial 10](../examples/validator-attack/README.md)). Outside the package on purpose, because `build-check-map.py` would ship it inside every map |
| `tools/tests/mapvalidator/` | its tests |

`check-map.py` keeps its name because a map package's checker is a published artefact. Renaming
it is a decision about a version of the package, not about a directory here.

## The six kinds of truth

0033 §2 names them, and the point of naming them is that four are mostly unbuilt. This is the map
of the territory, not the territory.

| Kind | The question | Today |
|---|---|---|
| **structural** | does the object obey the map contract? | most of what exists: `schema`, `vocabulary`, `required-fields`, `unique-ids`, `gates`, `references`, `derived`, `exclusions`, `conflicts`, `defines` |
| **evidentiary** | does the cited text exist where the map says it does? | the three locator checkers and `test_map_anchors.py` — outside the package, and belonging inside it |
| **completeness** | did the mapper skip definitions, gates, pointers, tables, examples, applicability clauses, or part of the declared extent? | the producer's half now runs — [`mapper sweeps`](mapper.md#the-sweeps) asks each declared sweep of the units the walk left unaccounted ([#250](https://github.com/brandonifco/rules-factory/issues/250)) — and the adversarial half is owed. `extent` claims coverage and [`mapper inventory`](mapper.md#the-inventory) now measures it — 540 of 806 units across the six maps are reached by no quote ([#255](https://github.com/brandonifco/rules-factory/issues/255), [#267](https://github.com/brandonifco/rules-factory/issues/267)) — but it is the producer measuring its own walk, and nothing adversarial reads that count |
| **interpretive** | does the evidence actually support the classification? | nothing mechanical, by nature. It is what the blind second mapping exists for ([0014](decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md)), which caught 14 of 15 injected comprehension errors the mechanical checks missed |
| **relational** | does this gate govern everything the map says it governs — and more than the map noticed? | shape only. `full-table-suspension` reached the throw and everything a throw leads to, recorded none of it, and survived a trial, a build and a review |
| **epistemic** | was ambiguity preserved where the corpus supports two readings, or collapsed into one? | `superposition`, `unresolved-reason` and `bound-term-open` ([0034](decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md)), each reading a record made outside the entry. Measured: 12 of 64 collapses caught, against 4 before ([`examples/collapse-trial/`](../examples/collapse-trial/README.md)) |

## Validating the uncertainty

Every check today asks *is this value valid?* The validator also has to ask **is this uncertainty
valid?**

When the mapper says reading A is defensible, reading B is defensible, and the corpus does not
resolve between them, the job is not to choose:

```text
  ✓ evidence supports A
  ✓ evidence supports B
  ✓ no admitted authority resolves A against B
  ✓ C is contradicted by the corpus

  VALID UNRESOLVED STATE
```

That is a success. A **premature collapse** — a `clear` entry whose evidence supports two
readings — passes every check that exists, produces a confident engine, and records no doubt for
anyone to find. It is worse than a wrong answer, because a wrong answer can be disputed.

0034 builds what can be built around a judgement that cannot be mechanical. It adds **no field**:
a field inside the `ambiguity` block can only be carried by an entry that already admits its
doubt, and is absent exactly where a collapse happens. What it reads instead is the record a
second reader left — an `ambiguity.conflict` (0007), an `ambiguity.bounds` example (0031), or the
adjudication of a blind second mapping (0014):

| check | the trace it reads |
|---|---|
| `superposition` | a disagreement about certainty adjudicated *the corpus does not settle it*, and no entry the adjudication names is `clarity: ambiguous` |
| `unresolved-reason` | an open question returning a reason no correspondence row gives that entry |
| `bound-term-open` | a `bounds` whose `term` the entry's own `ambiguity.question` never states |

A ruling that resolves a question the map never recorded as open is the fourth trace, and it is
already refused — by `tools/factory/rulings.py` (0027), because a ruling lives in the engine's
overlay and the validator's publish phase has no overlay to read.

What still passes: `check-map.py` admits the oldest form of the gap in its own docstring — *two
`clarity: clear` entries stating incompatible rules pass every check here* — and 0034's own
measurement puts the collapse miss rate at 52 of 64.

## The blind second mapping, across the boundary

```text
                  corpus
                 /      \
                v        v
           Mapper A    Mapper B          producing a mapping is mapping
                \        /
                 v      v
                Validator                comparing mappings is challenging them
                    |
             disagreement set
                    |
                    v
               adjudication              a judgement; the validator owns the machinery, not the call
                    |
                    v
              certified map
```

The mapper produces both mappings from independently staged inputs — staging is what makes
independence a property of the run rather than a hope about it
([#223](https://github.com/brandonifco/rules-factory/issues/223)). The validator owns the
machinery that says *these disagreements exist, every one must be dispositioned, and no map
passes until they are*, and that the adjudication record corresponds exactly to these map bytes
and these comparison inputs (0017).

## What it cannot do

Stated here and in the checker's own docstring, which is the longer version and the one a reader
of the code meets.

Each line says whether it is **measured** — a committed map was damaged that exact way and the
validator was watched not noticing ([trial 10](../examples/validator-attack/README.md)) — or
**reasoned**, argued from the code and not yet attacked. The distinction used to be invisible from
reading them.

- **Its own miss rate is 71%.** Fourteen mutations over five committed maps and three locator
  grammars: 62 landed, 18 are refused, 44 pass
  ([#259](https://github.com/brandonifco/rules-factory/issues/259); 16 and 46 when first measured
  at `69167d8`, and the two rows that moved are the epistemic checks 0034 added). Five of the
  twenty-five checks `check-map.py` held when it was measured ever turned; there are twenty-six
  now, `defines` ([0045](decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md))
  being the newest and unmeasured. Every miss is dispositioned, below or as an
  issue: [#268](https://github.com/brandonifco/rules-factory/issues/268),
  [#269](https://github.com/brandonifco/rules-factory/issues/269),
  [#270](https://github.com/brandonifco/rules-factory/issues/270),
  [#271](https://github.com/brandonifco/rules-factory/issues/271).
- **A conflict nobody recorded is invisible.** Two `clarity: clear` entries stating incompatible
  rules pass. *Reasoned.* Its neighbour is measured, and the measurement moved: deleting a
  recorded ambiguity and asserting one reading — premature collapse — passed on 5 maps of 5
  before `superposition` existed and is refused on 1 of 5 now. That check reaches the case where a
  *second mapper* recorded the doubt and the map did not, which is not a property of the map at
  all; where both readers made the same silent choice there is no record and no trace. Over every
  recorded ambiguity rather than one per map, 12 of 64
  ([`examples/collapse-trial/`](../examples/collapse-trial/README.md), 0034).
- **A gate is not checked against the corpus at all.** A missing `enabledBy` edge, a missing
  `suspendedBy` edge and an invented `dependsOn` edge leave the map internally consistent, and
  every one passed. *Measured: 0 of 13.*
- **An entry can quote the wrong sentence of the right passage.** The locator resolves, the quote
  is verbatim of the extraction, and only reading the corpus against the entry says it is the
  wrong sentence. *Measured: 1 of 5, and that one by bookkeeping rather than by reading.* Where the
  swap crosses into a neighbouring passage, whether it is caught is a property of the grammar — a
  section citation names a paragraph and refuses it; a page citation names a page and does not.
- **A rule nobody mapped leaves no trace.** An omitted definition, and an applicability rule
  removed with the edges that named it, both pass. *Measured: 0 of 4 and 0 of 4.*
- **An absence is claimed here and proved elsewhere.** Nothing in `check-map.py` reads a corpus;
  `absentFrom` is checked for shape, and falsified by the locator checkers. *Reasoned.*
- **A cross-reference nobody noticed is invisible** to the phrase list — measured at 0 detected in
  passages holding 51 references ([#208](https://github.com/brandonifco/rules-factory/issues/208)),
  and measured again from the other end in trial 10, where hiding a recorded cross-reference is
  refused on all three phrase-pointing corpora and missed on both SRD maps. The mapper's
  `defined-term-use` detector answers that corpus; a corpus that points in a third way is still
  unseen.
- **Nothing checks that an entry is the right decomposition,** that a gate list is complete, or
  that `evidence` is sufficient. Those are review.
