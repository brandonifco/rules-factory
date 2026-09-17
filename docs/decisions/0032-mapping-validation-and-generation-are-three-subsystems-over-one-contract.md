# 0032 — Mapping, validation and generation are three subsystems, and the map contract is all they share

## Status

Accepted — 2026-09-17. Records the decision behind
[#248](https://github.com/brandonifco/rules-factory/issues/248). **Extends
[0001](0001-the-corpus-map-is-the-interface.md)** (the map is the interface) by saying who is on
each side of it, and **[0016](0016-a-map-package-is-data-not-code.md)** (the factory checks a
package with its own checker) by naming what "its own checker" is a part of. Adds no entry field
and no manifest key. Changes no check's verdict on any committed map.

## Context

This repository does three jobs:

| Capability | Input | Output |
|---|---|---|
| **Mapper** | a pinned corpus, its manifest, an adapter, a mapping protocol | a candidate map and the record of how it was made |
| **Map validation** | a map and its manifest | a verdict, and a map that may become a version |
| **Factory** | a published map package and the corpus it was made of | a deterministic engine on `rules-kernel` |

Only the third had an address. `tools/factory/` is a subsystem with modules, tests, a CLI, a
provenance record and a release tag. The second is `tools/checkmap/` and the file it builds. The
first — the part that turns natural-language rules into a structured, provenance-backed,
independently challenged representation, and the part that is hardest to do and hardest to trust
— was spread across [`docs/method.md`](../method.md),
[`docs/corpus-map.md`](../corpus-map.md), thirty-one decision records, per-trial scripts under
`examples/<trial>/` and the behaviour of `tools/check-map.py`. Nothing in the tree said *this is
the mapper*.

Two consequences, both already visible:

- **A mapping discovery lands wherever it fits.**
  [#208](https://github.com/brandonifco/rules-factory/issues/208) — the cross-reference detector
  is structurally blind to a corpus that points by naming its defined terms, measured at 0
  detected pointers in passages holding 51 references — is filed against `schema` and `method`
  because there was no subsystem to file it against. So is
  [#223](https://github.com/brandonifco/rules-factory/issues/223): the redaction a blind second
  mapping requires is enforced by nothing, and the one tool that does it lives inside the trial
  that needed it.
- **The factory looked like the thing that also sort of knows how to map.** It does not and
  should not. It should be able to say: *give me a valid, appropriately certified map, and I will
  produce an engine.*

The question this record answers is not whether to separate them. It is **where the boundary
goes, and whether it is a repository boundary**.

## Decision

### 1. Three subsystems, siblings, over one contract

```text
                         map contract
                     (what a map's fields mean)
                    /          |            \
                   v           v             v
               mapper    map validation    factory
            corpus -> map   map -> verdict   map -> engine
```

`tools/mapcontract/` holds the map's closed vocabularies and the readers that get a field out of
an entry. It depends on nothing else in the repository. It is not a utility library that happened
to be shared; it is the interface 0001 names, written down once, so that a consumer cannot keep a
second definition of it and drift.

The other three are siblings and **none may import another**.

- The **mapper** is not a module of the factory. The factory consumes the mapper's product; an
  `import` in that direction would say the opposite. A mapper inside `tools/factory/` would also
  undersell it: the corpus → audited map problem is the harder of the two, and it is the one with
  uses — regulation, compliance, policy, contracts, procedure, tax, eligibility, standards — well
  beyond generating these engines.
- **Producer and verifier stay apart** for the reason production code is not its own only test
  oracle. The mapper says *this is my reading of the corpus*; validation says *prove you satisfied
  the contract*; the factory says *I do not care how you got here, give me an acceptable map*.
  Absorbing `checkmap` into the mapper would make the map its own only judge.
- **Where the blind second mapping falls.** Producing both mappings belongs to the mapper —
  including staging the second mapper's inputs, which is what makes independence a property of
  the run rather than a hope about it. Comparing them, adjudicating and certifying belong to
  validation. The second mapping is therefore the same machinery run again over independently
  staged inputs, not a review of the first map (0014).

### 2. The direction is checked, not intended

[`tools/check-boundaries.py`](../../tools/check-boundaries.py), run by `validate.sh`, holds every
subsystem to the direction declared in its `SUBSYSTEMS` table: the contract imports no subsystem,
no subsystem imports another, an import inside a function counts, and a relative import may not
climb out of its own package. The checker fails when it examined no subsystem, like every other
step in the gate.

An architecture is an architecture only while something enforces it. An `import` is one line, and
the reason to keep the boundary is invisible at the moment someone crosses it — which is how the
mapper became a chapter of a document in the first place.

What the checker cannot see is stated in its docstring, not here: chiefly that `tools/factory/`
reads map field names directly (`entry["id"]`, `entry.get("kind")`) rather than through the
contract. That is a real dependency on the contract's vocabulary that no import expresses, and
putting those reads behind the contract is its own change.

### 3. Not a separate repository — yet

`rules-mapper` is the right eventual shape and the wrong move today, because the map schema and
the mapping method are still co-evolving. Assertions, assertion attribution, gate directionality,
`definedElsewhere`, adapter limits, extraction corruption, derived facts, example bounds and
pointer mechanisms all arrived *from mapping trials*, each as a change to the method, the schema,
the checker and the examples at once. Behind a repository boundary each such discovery costs a
mapper pull request, a factory pull request, a schema version, a checker update, example
migrations and a compatibility question. That is a coordination tax paid precisely while the
abstraction is still being found, and it is how a premature separation freezes the wrong one.

So the boundary is drawn **as though it were already another repository**, and the repository
stays one.

### 4. What would justify the split

Not a date and not a feeling. Most of these, true at once:

- the map contract has held through several structurally different corpora, not four slices of
  one kind of ruleset;
- mapping runs and is tested without the factory present;
- the mapper has a CLI worth using on its own;
- a consumer other than this factory could plausibly use its maps;
- mapper releases would make sense on their own cadence;
- the mapper has its own substantial trial suite;
- its dependency on factory internals is zero and has been for a while;
- most changes to the mapper no longer require a simultaneous factory change.

The evidence to judge that is another two to four *genuinely different* mapping trials — not four
more RPG slices, but a structurally different ruleset each time. Until then the extraction is
deliberately deferred, and what makes it cheap when it comes is §2: a package move, not an
architectural rewrite.

## Consequences

- `tools/checkmap/model.py` is gone. Its vocabularies are `tools/mapcontract/vocabulary.py` and
  its readers `tools/mapcontract/entry.py`. `quotes_withheld` takes the manifest rather than a
  check's context, because the contract does not know what a check is.
- `tools/build-check-map.py` joins two packages instead of one, under the same rules, into the
  same single standard-library file a map package ships (0015) and the factory imports (0016).
  The boundary is in the sources and not in the artefact — which is the reason the join has
  rules at all.
- `mapper` is a category label in [the backlog](../backlog.md), so a mapping finding has
  somewhere to go.
- The factory's provenance is unchanged: it hashes `tools/factory/` and the built
  `tools/check-map.py`, and the contract reaches it inside that file.

### Limits

- The boundary is checked at the level of imports. The factory's direct reads of map field names
  are coupling the checker cannot see, and this record does not fix them.
- Three of the four subsystems exist. `tools/mapper/` is
  [#249](https://github.com/brandonifco/rules-factory/issues/249) and
  [#250](https://github.com/brandonifco/rules-factory/issues/250); until it does, the mapper's
  identity is a decision and a label rather than code, and this record is a promissory note to
  that extent.
- Nothing here makes the mapping method better. It gives the method a place to live, which is a
  precondition for the work that does — #208 and #223 both name defects that have no owner
  today.
