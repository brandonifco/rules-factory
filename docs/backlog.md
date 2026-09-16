# How the backlog is organised

Two labels on every issue: **what kind of thing it is**, and **what it blocks**.

## Category — the project's own decomposition

| Label | What belongs in it |
|---|---|
| `schema` | The corpus map's shape. [0001](decisions/0001-the-corpus-map-is-the-interface.md) says the map is the interface, so a wrong schema is wrong everywhere downstream at once. |
| `method` | The written procedure a mapper or builder follows. Distinct from the schema: a correct schema with a method that contradicts it produces wrong maps, which is exactly how the delegated-standard entries got misclassified. |
| `enforcement` | A check that turns a stated rule into a fact. "A rule worth stating is worth a check" is the kernel's second governing principle and it applies here. |
| `rails` | What a produced engine ships with for the team that maintains it. |
| `evidence` | Measures whether the method works — trials, miss rates, the acceptance test. |
| `map-data` | An error in a specific map rather than in the schema. Cheap to fix, and worth keeping separate so a pile of them is not mistaken for a design problem. |
| `factory` | The factory's own implementation: intake, generation, the gate recipe, provenance, backlog, verify. Distinct from `enforcement`, which holds this repository's documents to their word; a `factory` defect is in what `tools/factory/` does to a produced engine. |

`documentation` (GitHub's default label) is used for text that is wrong about the code, such as
[#75](https://github.com/brandonifco/rules-factory/issues/75).

## Priority — distance from the next engine

The spine of this project is [#3](https://github.com/brandonifco/rules-factory/issues/3), the
acceptance test. Priority is not urgency; it is **what happens if you build the next engine
without doing this**.

### `p1-next-engine` — settle first, or the next engine inherits the defect

A schema defect costs once per engine, and migrating two engines costs more than deciding once.
Everything here is either a schema question, the enforcement that makes a schema answer real, or
data an engine would be built from.

The evidence for putting these first is concrete: the first engine was built from a map with
eleven errors in it, and the correction to `starting-position` invalidated an architectural
commitment the engine had already shipped.

### `p2-acceptance` — needed for the acceptance test, not blocking the next build

Measurement and the builds themselves. These are the work, not the preconditions for it.

### `p3-needs-two-engines` — cannot be generalised from one

Rails especially. Deciding what every produced engine ships with, from a sample of one board
game, is how the predecessor repository ended up encoding one team's operating model as a
framework. Wait for a corpus that is not a game.

**The hold is lifted for the rails, 2026-09-15.** `faa-part-107` is a regulation and
`srd-52-combat` is not backgammon, so the sample is no longer one board game. What the factory
emits, and where the line falls between it and one team's operating model, is
[0029](decisions/0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md).

### `review-p0`, `review-p1`, `review-p2` — findings of the September 2026 external review

The factory's code was reviewed from outside in September 2026, and each finding became an
issue. These labels carry the review's own priority, which answers a different question from the
`p1`–`p3` scheme: not what the next engine inherits, but **how badly the factory breaks its own
promises today**.

| Label | Meaning |
|---|---|
| `review-p0` | Breaks the factory's trust, correspondence or refusal promise: a package that runs code, pins that disagree with provenance, a refusal that leaves output half-written. |
| `review-p1` | The factory cannot yet prove its product or keep its relationship with it: an engine never built in CI, backlog issues matched by title, provenance blind to build inputs. |
| `review-p2` | Policy, provenance depth, maintainability and accuracy, including this README's status. |

A review issue carries a review label *instead of* a `p1`–`p3` label, and one or more category
labels as usual (#65 is `enforcement` and `factory`). The thirteen findings are one ordered list
(#65 to #77), P0 before P1 before P2, and each issue's first line gives its place in it:
"Review priority P2 (11 of 13)". Findings that were not in the review's priority table are
ordered after those that were, and the issue says so.

The two schemes answer different questions, and no decision orders one against the other. What
the labels do say: a `review-p0` or `review-p1` issue is a defect in the factory as merged, where
`p1-next-engine` is a question to settle before the next map or engine. The acceptance test
([#3](https://github.com/brandonifco/rules-factory/issues/3), `p2-acceptance`) runs through the
factory, so it measures a factory with whatever review findings are still open. The review labels
belong to that one review; work found later is labelled under the scheme above.

### `review2-p1`, `review2-p2`, `review2-p3` — findings of the 2026-09-16 review

A second review, of `factory/v0.8.1`, labelled the same way: a review label instead of a
`p1`–`p3` label, category labels as usual, and a first line giving the issue's place in the
review's one ordered list of twelve ("Review priority P2 (6 of 12)"). Two of the twelve were
already open, #157 and #8, and carry the label beside their own.

| Label | What belongs in it |
|---|---|
| `review2-p1` | Prove what exists before building more: the rails' live acceptance (#157), the dense cross-reference trial (#8), a second independent review, and status text that is true about `main`. |
| `review2-p2` | Maintainability and reproducibility of the factory as merged: refactors that change no output byte, floating CI tooling, the rails as their own bounded context. |
| `review2-p3` | Deeper trust that does not block 1.0: signed release tags, an expected package digest, an engine-owned domain-type contract, build attestation. |

The review's other recommendation is not an issue: hold new factory features until the P1 items
are done, and let real engine work, not anticipated needs, propose the next abstraction.

## The hub

[#24](https://github.com/brandonifco/rules-factory/issues/24) is not one issue among the
`p1-next-engine` set — it subsumes five of them. #6, #10, #11, #15, #19 and #23 are one question
asked six times, answered in
[0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md). Work #24 and most of the
`schema` label closes with it.

## What this ordering is betting on

That the vocabulary has converged. Trials 3 and 4 produced new *instances* of the six situations
and no new *kinds*, which is the signal that a decision can be derived rather than guessed. If a
regulation engine produces a seventh kind, this ordering was wrong and the schema work should
have waited. That is the bet, and it is recorded here so it can be judged later rather than
rationalised.
