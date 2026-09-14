# 0003 — A phase gate names a rule, not a condition

## Status

Accepted — 2026-09-13. **Partly superseded 2026-09-14** by
[0011](0011-a-gate-has-a-direction.md): `gatedBy` is split into `enabledBy` and
`suspendedBy`, so the field now states direction. The polarity paragraphs below are kept as
they were written and marked where they stand; everything else here still applies to both new
fields.

## Context

`dependsOn` orders *implementation*: which entries must be built before which. The second
trial — [Hoyle's Backgammon](../../examples/hoyle-backgammon/README.md) — produced a corpus
with turn structure, and that surfaced a second ordering the map had no field for. Bearing
off applies only once every man is home. A man on the bar suspends every other move. Those
are **runtime preconditions**, and they are not what `dependsOn` records.

The first trial never asked. 14 CFR Part 107 evaluates one flight against a set of limits;
there is no phase for a rule to be scoped to. This is a property of genre, not of mapping
quality, and it is why a stateless corpus is a poor test of the schema.

The tempting answer is "the graph already tells you". It does not, and the backgammon map is
the counter-example. Taking the transitive closure of `dependsOn`:

- `bearing-off-doublets` has six implementation ancestors — `bearing-off-eligible`,
  `bearing-off-move-or-remove`, `doublets`, `move-by-pip`, `throw-two-dice`, `opening-roll`.
  Exactly one of them is the phase gate. Nothing in the graph distinguishes it from the other
  five.
- `move-by-pip` is gated by `enter-from-bar`, which is **not** among its ancestors
  (`opening-roll`, `throw-two-dice`) — nor is `move-by-pip` among `enter-from-bar`'s
  (`blot-hit`, `legal-destination`). On that pair the two relations are simply unrelated.

So the gate relation is neither a subset of the implementation relation nor derivable from
it. It is a second fact.

The live question is whether that second fact belongs to the map at all. The map
deliberately does not model engine state ([0001](0001-the-corpus-map-is-the-interface.md)
rejected a formal rule language on exactly that ground), and "all fifteen men are home" is a
statement about engine state if anything is. Against that: the map is the interface
everything downstream consumes, an implementer dispatched against `bearing-off-highest`
needs to know the rule is unreachable outside a phase, and the entry's `evidence` is wrong
if they do not — a test of a phase-scoped rule must set up the phase, and one that does not
is testing something the corpus never describes.

## Decision

The map gains **`gatedBy`**: an array of entry ids. Present on an entry that the corpus
states is reachable only in some circumstance; absent otherwise.

The condition belongs to the engine. The *fact that the entry is phase-scoped, and which
mapped rule states the scope*, belongs to the map. `gatedBy` records only the second.

What may go in it: **ids of other entries in the same map, and nothing else.** The value
type is the whole constraint — an array of ids cannot hold a predicate, a state name, a
boolean expression, a threshold, or a sentence. A gate in a well-mapped corpus is always
itself a rule the corpus states, so it always already has an entry, an id, and a locator.
If a proposed gate has no entry, the map is missing an entry; that is the finding, not a
reason to write prose here.

What may not: any expression of *when* the condition holds. `gatedBy` says which rule
governs reachability. It does not say in which direction — `bearing-off-eligible` permits
the entries it gates, `enter-from-bar` suspends them — and it is not meant to. The reader
follows the id to an entry with a locator and reads the corpus. That is the same move the
map makes everywhere else: point, do not restate.

`gatedBy` is **not transitive and not inherited through `dependsOn`.** An entry that a gate
reaches records it, even when one of its `dependsOn` ancestors records the same gate. The
two relations are independent, as above, so inheritance through one of them would be a
guess.

`gatedBy` does not affect backlog order. `dependsOn` remains the only ordering.

## Alternatives considered

**Nothing — phase conditions are the engine's business.** The strongest alternative, and
rejected on the evidence rather than on principle. It survives right up to the point where
someone writes the `evidence` field: `bearing-off-highest` requires "the six-throw example",
and that example is only constructible in a position the corpus reaches by a rule stated
three entries away. Under this option the implementer rediscovers that by re-reading the
corpus, which is the specific cost the map exists to remove.

**A `precondition` field holding the condition itself.** Rejected, and the reason is the
field's name: "precondition" is an invitation to write `allMenHome && !onBar`. That is a
second implementation of the rule, in a format nothing executes and no test checks, which
0001 already rejected when it rejected a formal rule language. It would also go stale
silently — the engine could change and the map's copy of the predicate would still parse.

**A free-text `phase` or `appliesWhen` string.** Rejected for the same reason as the
reason-string half of [0004](0004-adapter-reach-is-a-property-of-the-entry.md): prose is not
checkable, and two mappers would write "bearing off" and "all men home" for the same gate
with nothing to reconcile them. Ids are checkable — every id must resolve to an entry in the
same map.

**Reuse `dependsOn` with a flag per edge.** Rejected: it presumes every gate is also an
implementation dependency, and `move-by-pip`/`enter-from-bar` shows it is not. Encoding a
second relation on the edges of the first only works when the second is a subset of the
first, and it is not.

## Consequences

`gatedBy` does not make an engine correct. The engine still has to implement the check, and
nothing verifies that an entry's gate list is complete — a mapper who misses a gate produces
a map that validates. What it buys is that a *recorded* gate is inspectable and machine-
checkable for dangling ids, and that an implementer reading one entry learns the rule is
phase-scoped without re-reading the corpus.

**The field cannot express polarity, and that is a real cost.** "Gated by
`bearing-off-eligible`" and "gated by `enter-from-bar`" mean opposite things — permitted
once, suspended while — and only the referenced entry's text says which. A reader who does
not follow the id learns less than they may think they have.

> **Superseded by [0011](0011-a-gate-has-a-direction.md).** The cost stopped being theoretical
> when the build found two unrecorded gates and `move-by-pip` came to carry three, one of them
> opening the bearing-off entries and closing this one. The paragraph above, and the sentence
> in the Decision section saying `gatedBy` "is not meant to" state direction, no longer
> describe the schema.

**Deciding what to list required judgement the map does not record.** Filling the backgammon
map, `bearing-off-move-or-remove` is gated by `bearing-off-eligible` and arguably also by
`enter-from-bar`; it is not listed, because a man on the bar is not home and the first gate
subsumes the second. That subsumption is reasoning, done once, and invisible in the result.
Expect gate lists to be judged rather than enumerated, and expect two mappers to differ.

Non-transitivity means repetition: three backgammon entries each name `enter-from-bar`. That
is deliberate — the alternative is inferring a gate along an edge that does not carry it —
but it makes gate lists something a re-map has to maintain rather than derive.

Stateless corpora will carry the field on no entry at all. Both Part 107 maps do exactly
that, which is the correct outcome and not an incomplete one.
