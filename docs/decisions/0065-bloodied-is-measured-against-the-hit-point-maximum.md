# 0065 — Bloodied is measured against the Hit Point maximum

## Status

Accepted — 2026-09-22. Rules on the one `ambiguity` in the map of SRD 5.2.1 pp. 16–18
([`examples/srd-52-damage-and-healing/`](../../examples/srd-52-damage-and-healing/README.md),
[#434](https://github.com/brandonifco/rules-factory/issues/434)). A reading of one passage, under
[0005](0005-a-field-earns-its-place-by-being-checkable.md)'s `fate: decision`. **Adds no field, no
vocabulary value and no check**, so [0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md)
does not govern it.

## Context

SRD 5.2.1 p. 16, under *Hit Points*:

> If you have half your Hit Points or fewer, you’re Bloodied, which has no game effect on its own
> but which might trigger other game effects.

Half of what is not said. Two sentences of the same paragraph fix how this chapter uses the words:

> Your current Hit Points can be any number from that maximum down to 0 …
> Whenever you take damage, subtract it from your **Hit Points**.

So *your Hit Points*, in this slice, is the current total. Read that way the threshold is
`current ≤ current / 2`, which holds only at 0, and the corpus would have defined a word for
*dead or nearly so* while saying it triggers other effects. The other reading takes the half from
the Hit Point maximum, which the immediately preceding sentence of the same paragraph defines and
which every other threshold in the chapter measures against — `massive-damage` compares the
remainder to the maximum, `hit-point-maximum-of-zero-is-death` watches the maximum, and
`healing-cannot-exceed-maximum` caps at it.

The passage itself chooses neither.

## Decision

**Bloodied is `current Hit Points ≤ Hit Point maximum ÷ 2`.** The map records the question on
`bloodied` with `fate: decision` naming this record, and an engine implements the maximum
reading as though the corpus had said so.

Rounding is not decided here and is not needed: `≤ maximum ÷ 2` is the same predicate however the
half is rounded, because Hit Points are integers and the comparison is on the current total. A
creature with a maximum of 7 is Bloodied at 3 under *round down* and at 3.5 — so at 3 — under
exact division.

## Why the other reading is not left open

`fate: unresolved` is for a question where no reading is defensible enough to bake in. This is not
that. The current-total reading is not a rival reading of the rule; it is a reading on which the
rule says nothing the corpus could have wanted, and an engine returning `RequiresInterpretation`
for every Bloodied test would be declining a question the corpus has effectively answered by what
it does everywhere else. Recording it as `clear`, on the other hand, would have hidden the choice
in a `note` — which is what the first draft of this map did, and what this field exists to stop.

## Consequences

**One entry in one map moves**, from `clarity: clear` to `ambiguous` with a `decision`. Nothing
else in the map depends on the threshold: Bloodied has no game effect of its own in this slice,
and no other entry names it.

**An engine's test is named by the entry.** `bloodied`'s note asks for the predicate at exactly
half the maximum and at half plus one, which is where the two readings and the rounding would
diverge if either mattered.

**If a later slice of the SRD states the threshold**, this record is superseded by that passage
rather than reaffirmed: a decision is what the project does where the corpus is silent, and it
stops applying where the corpus speaks. The Rules Glossary (pp. 178–190, mapped in part by trial
8) is where such a statement would be, and no entry of that map quotes one today.
