# 0063 — No new map concept without a corpus that forces it

## Status

Accepted — 2026-09-21. Closes the first half of
[#265](https://github.com/brandonifco/rules-factory/issues/265); the queue behind trials 10 and
11 is the issue's second half, and stays there, because a plan is not a rule. **Extends
[0005](0005-a-field-earns-its-place-by-being-checkable.md)**, which says a field earns its place
by being checkable: this says who may propose one at all. Adds no field, no vocabulary value and
no check.

## Context

Nine trials in, the map contract has enough theory and not enough adversaries. The standing risk
is the one that archived the predecessor repository: an ontology designed in a vacuum, elegant,
internally consistent, and answering questions no corpus ever asked. That failure does not
announce itself. Every step of it is locally reasonable — a distinction is real, a field would
capture it, the field is cheap — and the sum is a schema nobody can map against.

[examples/README.md](../../examples/README.md) already half states the rule: *"Each trial exists
to change the method. A run that confirms everything has told us nothing."* That is the pressure
in one direction. This is the pressure in the other, and the two together are the whole
constraint: go looking for corpora that break the model, and change the model only where one
actually did.

The trials have been run that way in practice. Trial 10's `continuesDefinition`
([0046](0046-an-additional-rule-can-continue-a-definition.md)) exists because § 172.102's
additional-requirement row states half a rule read alone and cannot declare `defines`; the
coded-pointer mechanism ([0041](0041-a-coded-pointer-is-made-by-the-column-it-sits-in.md)) exists
because column 7 holds `IB2, T4, TP1` and no phrase list can see it. Both were exhibited before
they were built. What has been missing is the rule itself, written down — so that declining a
plausible schema idea is a rule being followed rather than an argument being lost, and so that
the next person to have a good idea has something to test it against rather than a taste to
argue with.

## Decision

**A new map concept is admitted only when a real corpus produced something the contract cannot
faithfully represent.**

A *map concept* is anything that changes what a map can say: an entry field, a kind, a relation,
a unit, a value in a closed vocabulary, a pointer mechanism, an adapter-reach modality, a
manifest key.

The corpus that forces it must be admitted under
[0028](0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md), and the
failure must be established in this order, before the change is designed:

1. **Decomposition under the existing model is attempted, and the attempt is written down.** What
   entries were tried, and what each one had to claim.
2. **The failed representation is exhibited.** The passage, the attempted entries, and the
   sentence the map would have to assert that is *false about the corpus* — not merely awkward,
   verbose or inelegant. Inconvenience is not impossibility, and the difference is the whole
   decision.
3. **A second reading sees the same failure.** The blind second mapping and its adjudication
   ([0014](0014-a-map-is-checked-by-a-blind-second-mapping.md),
   [0017](0017-a-map-change-carries-a-review-of-its-bytes.md)) are what separate a limit of the
   contract from one reader's preference.
4. **The check is named.** 0005: what would a checker look at to know this concept is used
   correctly? A concept nothing can check is a note, not a field.

A proposal that stops at step 1 or 2 is filed as an issue and left there. It is not wrong; it is
unforced, and an unforced concept is how the predecessor was lost.

## What this does not say

- **It does not forbid repairs.** A defect in a field that exists, a vocabulary value a committed
  map already needs, a check that reads the wrong thing — none of these is a new concept.
- **It does not forbid the changes a trial forces.** 0041, 0045, 0046 and 0036 were all admitted
  this way, during trial 10, and a trial that forces one is the trial working.
- **It does not require a *new* corpus.** A corpus already admitted can exhibit the failure; what
  it may not be is a hypothetical corpus, a corpus somebody expects to admit, or a genre.
- **It says nothing about the factory or the rails.** It governs the map contract — the interface
  ([0001](0001-the-corpus-map-is-the-interface.md)) every other subsystem is built against, and
  the one where a wrong addition is wrong everywhere at once.

## Two it already governs

- **A generalised evidence graph.** Wait for a corpus where decomposition into the entries and
  relations that exist actually fails; trial 10 was the candidate and its strains were repaired
  locally instead.
- **Superposition**, from the trial 9 build
  ([examples/tax-121-build/EVIDENCE.md](../../examples/tax-121-build/EVIDENCE.md)). Wait for a
  corpus whose ambiguity the existing `ambiguity` block cannot hold.

Both are plausible. Neither has a corpus behind it, and under this record that is the end of the
matter until one does.

## Alternatives

**Admit a concept when two corpora would plausibly use it.** Rejected: "plausibly" is the word
the predecessor's ontology was built on. Every concept in a vacuum is plausible for two corpora,
because the corpora are imagined together with the concept.

**Admit nothing new before 1.0.** Rejected, and it is the more tempting error now. A corpus that
genuinely forces a change would then be mapped *falsely* — the map would assert something untrue
about the corpus, which is worse than a schema change, and worse in the one way this project
cannot afford. The freeze is on unforced additions, not on the truth of a map.

**Leave it as prose in `examples/README.md`.** Rejected by #265 on the ground that a rule nobody
can cite is an argument: a record can be pointed at in a review, and a paragraph in a trial index
cannot.
