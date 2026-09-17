# 0033 — The validator is the adversary, it is named for that, and what it validates includes the uncertainty

## Status

Accepted — 2026-09-17. Records the decision behind
[#257](https://github.com/brandonifco/rules-factory/issues/257). **Extends
[0032](0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md)**, which
made the three subsystems siblings over the map contract. Adds no entry field and no manifest
key. Changes no check's verdict on any committed map.

**Every earlier record that names `tools/checkmap/` means `tools/mapvalidator/`.** 0015 and 0032
are the two, and they are not rewritten past the path: a decision record says what was decided,
and this is the record that renamed the directory.

## Context

0032 named three subsystems and gave two of them their own identity. The third was still called
`checkmap` — the name of a script. That is what it began as, and it is not what it is.

The three ask three different questions, and they are three different trust boundaries:

| Subsystem | Its question |
|---|---|
| Mapper | What does this corpus say, and where does its certainty end? |
| **Validator** | Has the mapper justified those claims, and is this map safe to rely on? |
| Factory | Given an acceptable map, what follows mechanically? |

The mapper is an **interpreter**. It takes messy authoritative material and turns it into
structured claims, and it is allowed to say *I believe this passage produces this entry*. What it
is not allowed to do is certify itself.

The validator is the **adversary**. Its attitude is *I don't care that the mapper thinks this is
right; show me.* That is not a utility hanging off the mapper. It is the only subsystem
positioned to say that neither the mapper nor the factory may claim authority it does not
possess, and it is on its way to being much larger than `check-map.py`.

The factory should be **aggressively uninterested in interpretation**. By the time a map reaches
it, its answer is *this map satisfied the validation policy; I will build exactly what it says*.
A factory that re-read the corpus and decided a rule meant something else would destroy the
architecture, because the point of the map boundary is that semantic interpretation happened
upstream.

## Decision

### 1. `tools/checkmap/` is `tools/mapvalidator/`

Named for what it is rather than for its first implementation. `check-map.py` keeps its name and
its bytes: a map package's checker is a published artefact (0015), and renaming it is a separate,
breaking decision that would have to be made about a version of the package, not about a
directory here. The built file is byte-identical apart from the comments naming its sources.

Tests follow the subsystems: `tools/tests/mapper/`, `tools/tests/mapvalidator/`,
`tools/tests/factory/`, and, at the top level, the tests of the checkers that hold *this
repository* to its word rather than any subsystem.

### 2. Six kinds of truth

The validator's job is not one check list. It is six, and naming them is most of the design,
because it says what exists and what is still owed:

| Kind | The question | Today |
|---|---|---|
| **structural** | does the object obey the map contract? | `schema`, `vocabulary`, `required-fields`, `unique-ids`, `gates`, `references`, `derived` |
| **evidentiary** | does the cited text exist where the map says? | the three locator checkers, and `test_map_anchors.py`; they live outside the package and belong inside it |
| **completeness** | are there signs the mapper skipped definitions, gates, pointers, tables, examples, applicability clauses, or part of the declared extent? | almost nothing. The producer's half is [#250](https://github.com/brandonifco/rules-factory/issues/250); the adversarial half is owed |
| **interpretive** | does the evidence actually support the classification? | nothing mechanical. It is what the blind second mapping exists for (0014) |
| **relational** | does this gate govern everything the map says it governs — and perhaps more than the map noticed? | shape only. The backgammon map's `full-table-suspension` reached the throw and everything a throw leads to, and recorded none of it, through a trial, a build and a review |
| **epistemic** | was ambiguity preserved where the corpus supports more than one reading, or collapsed into one? | nothing. [#258](https://github.com/brandonifco/rules-factory/issues/258) |

### 3. Validating the uncertainty is validation

Every check today asks *is this value valid?* The validator also has to ask **is this
uncertainty valid?**

When the mapper records that reading A is defensible, reading B is defensible, and the corpus
does not resolve between them, the validator's job is not to choose. It is to establish that the
corpus really does support both, that neither has been eliminated, and that the map represents
the rule as unresolved:

```text
  ✓ evidence supports A
  ✓ evidence supports B
  ✓ no admitted authority resolves A against B
  ✓ C is contradicted by the corpus

  VALID UNRESOLVED STATE
```

That is a success. The validator has not failed to find the answer; it has established that the
absence of a unique answer is itself justified. A premature collapse — a `clear` entry whose
evidence supports two readings — passes every check that exists, produces a confident engine, and
leaves no doubt recorded for anyone to find. That is worse than a wrong answer, because a wrong
answer can be disputed and a collapse leaves nothing to dispute. The built checker already admits
the gap in its own words: *two `clarity: clear` entries stating incompatible rules pass every
check here.* Closing it is #258; this record is where the responsibility is placed.

### 4. Three forms of determinism

The subsystems differ in what determinism they can even claim, and the boundary is where the
claim changes:

- **The mapper is not necessarily deterministic.** Two legitimate mappers can disagree about the
  same passage. That is not a defect to engineer away; it is why 0014 requires an independent
  second mapping and an adjudication rather than a re-run.
- **The validator is deterministic wherever it is mechanical.** Given a map, a corpus, a protocol
  and its evidence, the same inputs give the same verdict. Where semantic validation necessarily
  invokes another interpretation — the interpretive and epistemic rows above — that point is
  named, not blurred into the rest.
- **The factory is fully deterministic.** Given the same certified map, configuration and
  rulings, the same engine. `factory provenance` exists to prove it.

### 5. Where the blind second mapping falls

0032 put staging and both mappings with the mapper and comparison with validation. This states it
sharply, because it is the boundary most easily got wrong:

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
               adjudication              may require a person or an authorised interpreter
                    |
                    v
              certified map
```

The mapper produces both mappings, from independently staged inputs — staging is what makes
independence a property of the run rather than a hope about it ([#223](https://github.com/brandonifco/rules-factory/issues/223)).
The validator owns the machinery that says *these disagreements exist, every one must be
dispositioned, and no map passes until they are*, and that the adjudication record corresponds
exactly to these map bytes and these comparison inputs (0017). Adjudication itself is a
judgement; owning the machinery is not the same as making it.

### 6. The contract stays small

`tools/mapcontract/` holds the map's closed vocabularies and the readers that get a field out of
an entry, and it will be tempting to widen it into a place for anything two subsystems both want.
It is not that. If a thing is not part of what a map *means*, it does not go there — and the test
of the boundary is that somebody could hand-author a map and still validate and build it.

## Consequences

- The validator imports `mapcontract` and nothing else, as before. Its dependency on
  mapper-produced artefacts runs through the contract, never through mapper internals.
- The eventual repository family is `rules-kernel`, `rules-mapper`, `rules-map-validator`,
  `rules-factory`. Architecturally yes; physically not yet, for the reason 0032 §3 gives, which
  now covers three subsystems rather than two.
- `docs/validator.md` is the validator's document, as `docs/mapper.md` is the mapper's.

### Limits

- Four of the six kinds of truth are named here and built nowhere. This record is the map of the
  territory, not the territory: #250, #258 and
  [#259](https://github.com/brandonifco/rules-factory/issues/259) are where three of them become
  code, and the interpretive row may never be fully mechanical.
- The validator's own miss rate is unknown. Nobody has taken a committed, passing map, damaged it
  deliberately, and measured how much of the damage is noticed (#259). Several lines in the
  checker's statement of what it cannot do are reasoned rather than measured, and this record
  does not change that.
- Nothing here improves a single check. It renames a directory, moves tests, and writes down
  whose job the unbuilt things are — which is worth doing before they are built, and worth
  nothing if they are not.
