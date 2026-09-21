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
| [`tools/check-locators.py`](../tools/check-locators.py) and the two per-grammar checkers under `examples/` | the evidentiary half: does the cited text exist where the map says, does no in-scope quote lie outside the declared extent (`extent-bounds`, [#269](https://github.com/brandonifco/rules-factory/issues/269)), and how much of that extent can the map show it quoted ([0055](decisions/0055-coverage-reports-how-much-of-the-extent-is-quoted-and-a-map-declares-the-floor.md)) |
| [`tools/check-map-review.py`](../tools/check-map-review.py) | every map carries a review of its exact bytes ([0017](decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)), and a `blind-second-mapping` review names the staging record of what its mapper was given, or says out loud that it has none ([#223](https://github.com/brandonifco/rules-factory/issues/223)) |
| [`tools/pack-map.py`](../tools/pack-map.py) | a map that passed becomes a version; [0048](decisions/0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md) makes it hash every cited corpus, run the structural and locator checks on immutable snapshots of those exact bytes, and bind the resulting corpus identities to the packaged map, manifest and checker |
| [`tools/mutate-map.py`](../tools/mutate-map.py) | the adversary turned on itself: it damages a committed map one named way at a time and measures what is refused ([the validator attack](../examples/validator-attack/README.md)). Outside the package on purpose, because `build-check-map.py` would ship it inside every map |
| `tools/tests/mapvalidator/` | its tests |

`check-map.py` keeps its name because a map package's checker is a published artefact. Renaming
it is a decision about a version of the package, not about a directory here.

## The six kinds of truth

0033 §2 names them, and the point of naming them is that four are mostly unbuilt. This is the map
of the territory, not the territory.

| Kind | The question | Today |
|---|---|---|
| **structural** | does the object obey the map contract? | most of what exists: `schema`, `vocabulary`, `required-fields`, `unique-ids`, `gates`, `references`, `derived`, `exclusions`, `conflicts`, `defines`, `definition-continuations` |
| **evidentiary** | does the cited text exist where the map says it does? | the three locator checkers and `test_map_anchors.py` — outside the package, and belonging inside it; the section checker also proves 0046 structural continuation anchors |
| **completeness** | did the mapper skip definitions, gates, pointers, tables, examples, applicability clauses, or part of the declared extent? | the producer's half runs — [`mapper sweeps`](mapper.md#the-sweeps) asks each declared sweep of the units the walk left unaccounted ([#250](https://github.com/brandonifco/rules-factory/issues/250)) — and the adversarial half has its first measure. `extent` claims coverage and [`mapper inventory`](mapper.md#the-inventory) measures it — 408 of 806 units across the six maps are reached by no quote and recorded by no rejection ([#255](https://github.com/brandonifco/rules-factory/issues/255), [#267](https://github.com/brandonifco/rules-factory/issues/267)) — but it is the producer measuring its own walk. What the adversary now reads is `coverage`'s **quoted fraction**: the union of the verified quotes' spans over the extent's own length, reported on every run and 19%–100% across the committed maps ([0055](decisions/0055-coverage-reports-how-much-of-the-extent-is-quoted-and-a-map-declares-the-floor.md), [#270](https://github.com/brandonifco/rules-factory/issues/270)). It fails a map only against the floor the map declares in `extent.quoted`, and no committed map declares one yet |
| **interpretive** | does the evidence actually support the classification? | nothing mechanical, by nature. It is what the blind second mapping exists for ([0014](decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md)), which caught 14 of 15 injected comprehension errors the mechanical checks missed |
| **relational** | does this gate govern everything the map says it governs — and more than the map noticed? | shape, plus one reach. `full-table-suspension` reached the throw and everything a throw leads to, recorded none of it, and survived a trial, a build and a review. `applicability-reach` ([#225](https://github.com/brandonifco/rules-factory/issues/225)) refuses a `scope: in` entry whose own words gate a whole section, part or table and whose id no entry names in `enabledBy` or `suspendedBy` — § 1.121-1(f), which trial 9's first mapping recorded with no reach at all. It cannot tell whether the reach recorded is *complete*: one edge satisfies it where thirty were owed |
| **epistemic** | was ambiguity preserved where the corpus supports two readings, or collapsed into one? | `superposition`, `unresolved-reason`, `bound-term-open` ([0034](decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md)), each reading a record made outside the entry, and `question-anchor` ([#271](https://github.com/brandonifco/rules-factory/issues/271)), which reads the corpus the map quotes. Measured: 12 of 64 collapses caught, against 4 before ([`examples/collapse-trial/`](../examples/collapse-trial/README.md)); invented doubt 5 of 5 |

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
adjudication of a blind second mapping (0014), which is one file and one shape,
`blind-mapping/resolutions.json`, declaring the vocabulary its verdicts are written in
([0060](decisions/0060-one-adjudication-record-one-shape-and-the-vocabulary-is-declared-in-the-file.md)):

| check | the trace it reads |
|---|---|
| `superposition` | a disagreement about certainty adjudicated *the corpus does not settle it*, and no entry the adjudication names is `clarity: ambiguous` |
| `unresolved-reason` | an open question returning a reason no correspondence row gives that entry |
| `bound-term-open` | a `bounds` whose `term` the entry's own `ambiguity.question` never states |
| `question-anchor` | an `ambiguity.question` quoting no passage this map quotes |

`question-anchor` is the one of the four that reads the corpus rather than a record made beside
it, and it is the answer to the other direction of the same flip.
[0033](decisions/0033-the-validator-is-the-adversary-and-validates-the-uncertainty-too.md) named
them asymmetric and this keeps them so. A false *certainty* — premature collapse — leaves no field
to check. A false *ambiguity* has a `question`, and a question is prose the mapper wrote about a
passage; the words of that passage are in the map. So the question must quote them: a run of at
least three consecutive words appearing verbatim in quoted `evidence` and carrying at least one
word outside the closed function classes, which the invented block `tools/mutate-map.py` writes
does on none of the five committed maps. The anchor is the corpus as the map quotes it, not the
entry's own evidence alone, because two readings can turn on a passage another entry holds.

What it does not reach, and this is the larger half: a mapper who invents doubt about a **real**
sentence. Nothing structural does. It catches the ambiguity that is about nothing in the passage,
and it makes an invented one have to be invented against words the corpus prints.

## The version a map replaces

A check with no subject matter reports NOT VERIFIED and **passes the run**, because such a check
declares it had nothing to look at. That is right for a corpus that genuinely has no gates and no
assertions. It is wrong when the subject matter was there a moment ago and the damage is what
removed it, and both halves of that were measured: turning a map's only assertion into an
operation silenced `asserted-by`, removing the rule every other entry was suspended by silenced
`gates`, and the gate stayed green through both
([#268](https://github.com/brandonifco/rules-factory/issues/268)).

The validator cannot know from one map whether a corpus has assertions. It can know that *this*
map had them: a published map package is a version, and its predecessor is a fact
([0015](decisions/0015-a-map-is-published-as-a-versioned-package.md)). `check-map.py --previous
PATH` takes the map this one replaces, re-runs any check that reports no subject matter against
it, and fails where that check had subject matter there. A corpus that lost its assertions, its
gates or its definitions between two versions is a change the map's diff states, not a check that
goes quiet.

It compares verdicts, not corpora, and says nothing at all without a predecessor — a first map has
none, and a caller who does not pass `--previous` gets exactly the behaviour #268 describes. Nor
does it see a check that lost only *half* its subject matter: an assertion removed from a map that
has five leaves `asserted-by` looking at four and saying `ok`.

`tools/mutate-map.py` passes it, because the harness holds both versions and that is what makes
the two silent skips measurable. [`tools/pack-map.py`](../tools/pack-map.py) now passes it too
([0062](decisions/0062-the-publish-gate-reads-the-version-it-replaces-from-a-tag-in-this-repository.md)),
and the predecessor's bytes come from the highest `map/<name>/vX.Y.Z` tag below the version being
packed — not from nuget.org, because a network read would make the gate's verdict depend on a
remote service, and not from a path the publisher names, because that proves whatever it was
handed. A first publish passes no `--previous` and is not refused for it; a tag that exists and
does not contain the map is a refusal rather than a silent skip; and which version was compared,
or that none was, is printed on every run.

Three of the four packable maps compare against a predecessor today. The fourth,
`tax-121-principal-residence`, is at v2.0.0 with no v1 tag, so it has no reachable predecessor —
which the gate reports as that, rather than as a first publish, because the two wear the same
shape and only one of them is harmless.

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
validator was watched not noticing ([the validator attack](../examples/validator-attack/README.md)) — or
**reasoned**, argued from the code and not yet attacked. The distinction used to be invisible from
reading them.

- **Its own miss rate is 55%.** Fourteen mutations over five committed maps and three locator
  grammars: 62 landed, 28 are refused, 34 pass
  ([#259](https://github.com/brandonifco/rules-factory/issues/259); 16 and 46 when first measured
  at `69167d8`). Twelve rows have moved: two are the epistemic checks 0034 added, two are
  `narrow-extent` on `hoyle-backgammon` and `srd-52-conditions`, which #269 closed, and eight are
  `question-anchor` (#271, five), `--previous` (#268, two) and `applicability-reach` (#225, one).
  Seven of the twenty-nine checks `check-map.py` now holds ever turned; twenty-two never did, and
  `definition-continuations` ([0046](decisions/0046-an-additional-rule-can-continue-a-definition.md))
  is among them. Every remaining miss is dispositioned, below or as an issue:
  [#270](https://github.com/brandonifco/rules-factory/issues/270),
  [#208](https://github.com/brandonifco/rules-factory/issues/208).
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
- **A rule nobody mapped leaves no trace.** An omitted definition passes. *Measured: 0 of 4.* An
  applicability rule removed with the edges that named it is refused on 3 of 4 now — by
  `applicability-reach` where it was the map's last whole-unit gate, by `gates` where it was the
  map's last gate at all, and by `superposition` where the deleted entry was where an adjudicated
  doubt was recorded. Where the map still has other gates it is missed, and that is the next item.
- **A check that loses only *half* its subject matter still says `ok`.** `--previous` compares
  verdicts, not corpora: an assertion removed from a map with five leaves `asserted-by` looking at
  four. *Measured: 2 of 4 for `assertion-to-operation`.*
- **A whole-unit gate is recognised by a phrase list,** `WHOLE_UNIT_GATES`, written from the CFR
  corpora, with the same limit `POINTER_PHRASES` has: a corpus that gates itself in other words is
  unseen. And one edge satisfies the reach, so a gate recorded with one edge where thirty are owed
  passes. *Reasoned.*
- **A false ambiguity about a real sentence passes.** `question-anchor` refuses a question about
  nothing in the passage. A question invented about words the corpus does print is prose about a
  real sentence, and no structural check separates it from a question somebody meant.
  *Measured from the other side: 5 of 5 for the invented block.*
- **A recorded `mutation` is still only a string.** Since
  [#240](https://github.com/brandonifco/rules-factory/issues/240) `status` refuses an unfilled
  placeholder — the set, one word repeated, or anything under three words and twelve characters,
  all read after Unicode normalisation
  ([`tools/mapvalidator/mutation.py`](../tools/mapvalidator/mutation.py), the rule the engine gate
  already applied to the merge it builds). That is where it stops: nothing here runs a test or
  sees an engine, so it cannot tell whether the edit was made, whether the test went red, or
  whether the sentence was copied from the entry above. `not yet recorded` passes, and every
  refusal says as much rather than letting the passing case read as proof. *Reasoned.*
- **An absence is claimed here and proved elsewhere.** Nothing in `check-map.py` reads a corpus;
  `absentFrom` is checked for shape, and falsified by the locator checkers. *Reasoned.*
- **A cross-reference nobody noticed is invisible** to the phrase list — measured at 0 detected in
  passages holding 51 references ([#208](https://github.com/brandonifco/rules-factory/issues/208)),
  and measured again from the other end by the validator attack, where hiding a recorded cross-reference is
  refused on all three phrase-pointing corpora and missed on both SRD maps. The mapper's
  `defined-term-use` detector answers that corpus; a corpus that points in a third way is still
  unseen.
- **Nothing checks that an entry is the right decomposition,** that a gate list is complete, or
  that `evidence` is sufficient. Those are review.


### Definition-continuation fate

`definition-continuations` treats the relation as an operative semantic assertion, not only
metadata. In this contract version it therefore refuses an entry that carries
`continuesDefinition` while its `ambiguity.fate` is `unresolved`. A source may remain
`clarity: ambiguous`; if the map adopts the continuation reading, the ambiguity is settled by a
named `fate: decision`. This is the invariant exposed by the independent review of PR #329.


### Manifest boundary corrections

The manifest check reads the current external boundary as the Phase-1 `references` plus any
0047 `referenceAmendments`. An amendment is additive and mapping-time only: it may add only
referenced-but-not-admitted targets and provenance naming the decision. Its reference source and
citation must name one coherent boundary, it may not duplicate an existing boundary, and it may
not target a corpus already admitted by the manifest. It cannot change corpus pinning or admission
facts. This preserves the distinction between what admission declared and
what mapping later discovered while keeping the operational boundary machine-readable. Broad
part references cover their child sections; exact section references do not act as prefix
wildcards.
