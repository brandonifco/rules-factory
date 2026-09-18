# 0034 — A valid unresolved state is established, not asserted, and the map records no competing readings of its own

## Status

Accepted — 2026-09-17. Carries out
[0033](0033-the-validator-is-the-adversary-and-validates-the-uncertainty-too.md) §3, which placed
the responsibility and built none of it. Closes
[#258](https://github.com/brandonifco/rules-factory/issues/258). **Extends
[0014](0014-a-map-is-checked-by-a-blind-second-mapping.md)**: the adjudication record a blind
second mapping produces is read by the validator, not only by the person who wrote it.
**Adds no entry field and no manifest key**, and that refusal is half of what is decided here.
Changes no check's verdict on any committed map.

## Context

Every check the validator has ever run asks *is this value valid?* 0033 named a sixth kind of
truth that nothing asked at all:

> **epistemic** — was ambiguity preserved where the corpus supports two readings, or collapsed
> into one?

The failure is not a map that records doubt badly. It is a map that records no doubt: a
**premature collapse**, a `clarity: clear` entry whose evidence supports two readings. It passes
every check, produces a confident engine, and leaves nothing for anyone to dispute. A wrong
answer can be argued with. A collapse cannot, because there is nothing on the page to argue with.
The built checker has said so about itself since it was written: *two `clarity: clear` entries
stating incompatible rules pass every check here.*

And it is measurable. Collapsing every recorded ambiguity in every committed map, one at a time
— [`examples/collapse-trial/`](../../examples/collapse-trial/README.md) — the validator as it
stood caught **4 of 64**, all four because the collapsed entry was a member of an
`ambiguity.conflict` and removing it left the group with one member. The other 60 produced a map
that passed every check in the gate.

**The honest difficulty, first.** Whether a passage supports two readings is not mechanical, and
0033 §4 asks for the points where validation necessarily invokes another interpretation to be
named rather than blurred into the rest. So the question this record answers is not *how do we
detect ambiguity*. It is **what can be made mechanical around a judgement that cannot be**.

## Decision

### 1. What a valid unresolved state is, and which part of it is mechanical

0033 §3 states the success condition in four lines. Each line is a claim about a different kind
of truth, and they are not equally checkable:

| The claim | What establishes it | Mechanical? |
|---|---|---|
| evidence supports reading A | the entry's `locator` and `evidence`, held to the corpus by the locator checkers | the span, yes; that it *supports* A, no |
| evidence supports reading B | a second entry in the same `ambiguity.conflict` (0007), an `ambiguity.bounds` example (0031), or a second mapper's entry in the adjudication record (0014) | the record, yes; the reading, no |
| no admitted authority resolves A against B | `fate: unresolved`, with `exclusions` refusing `definedElsewhere` and `beyondAdapter` beside an `ambiguity` block, and `decision-records` proving that a `fate: decision` names a record that exists | yes |
| reading C is contradicted by the corpus | a `bounds` example whose `verdict` is `doesNotApply`, held consistent with the others by `bounds`; or an adjudication that ruled for one map against the other | yes |

**A valid unresolved state is one where each of those four has a record behind it that is not the
mapper's own prose.** The judgement stays a judgement. What this record makes mechanical is
whether the *records* exist and agree — and the one place where a second reading is established
rather than asserted is the blind second mapping, because a second mapper who has not seen the
first map is not the first mapper saying *I considered the alternative*.

### 2. The map records no competing readings of its own. No `readings` field

The obvious move is an `ambiguity.readings` list: two or more readings, each with the span that
supports it. It is refused, and the argument is not that it is hard.

- **It is absent exactly where the failure happens.** A field inside the `ambiguity` block can
  only be carried by an entry that already says `clarity: ambiguous`. The dangerous case is the
  entry that says `clear` and has no block at all. A field that can only be filled in by a mapper
  who noticed the second reading cannot detect the mapper who did not, which is the whole of
  what #258 is about.
- **There is nothing to read it against.** 0005 admits a field when a check can read it and say
  what it is read *against*. A reading's text is prose; the only checkable part is the span that
  supports it, and the span is `evidence`, already required and already falsified by the locator
  checkers. 0031 settled the general form of this: *a field that is checkable sometimes and
  merely recorded the rest of the time reads as structure and behaves as prose*, and the reader
  cannot tell which entries are which.
- **The second reading is already recorded, in a better place.** 0014's blind mapping produces a
  whole second map, made from independently staged inputs, and an adjudication answering every
  disagreement from the corpus. That is a second reading with a corpus behind it and a mapper who
  could not see the first. Restating it inside the entry would be a claim; carrying it forward
  from there is a check.

**What is lost, stated rather than waved at.** The map alone cannot show a reader that two
readings were weighed. `ambiguity.question` is prose: it usually states both readings, nothing
holds it to doing so, and nothing ever will without a field. Across the six committed maps, **31
of 64 recorded ambiguities have no corroboration any check can read** — no `conflict`, no
`bounds`, no decision record, no adjudicated disagreement — and rest on the mapper's word that a
second reading exists. The `superposition` check prints that count on every run so that the
number is on the page rather than in an argument. This record does not close that gap; it says
where it is.

### 3. Three checks, for three traces a collapse leaves

Each reads records that already exist. None reads a corpus, and none guesses at prose.

**`superposition`** — an adjudicated *the corpus does not settle it* is recorded in the map as
unresolved. 0014's comparison already contains the second reading and its verdict; nothing
carried it forward. Two rules: every disagreement about `clarity` or the presence of an
`ambiguity` block carries a verdict the check can read, because 0014 requires every disagreement
to be dispositioned and one nothing can read is one nobody can be shown to have made; and every
unsettled verdict lands on an entry the map records as `clarity: ambiguous` — the flagged entry,
or one the adjudication names by id, because the doubt often belongs on a neighbour. `die-faces`
was adjudicated unsettled and the question went to a new `rubber-scoring` entry; `night-operation`
to `night-training-completed`. The rule is that the doubt is somewhere, not that it is here.

**`unresolved-reason`** — an open question returns a reason a caller can act on. `schema` holds
`unresolvedReason` to the kernel's five values; the correspondence table produces exactly one of
them for a question the corpus leaves open. `RequiresInterpretation` tells a caller to interpret,
or to rule under 0027. `MissingRulesData` sends them after data that does not exist and
`UnsupportedRule` tells them to wait for an implementation that would not settle it either. So
the reason must be one the entry's own rows can produce: `RequiresInterpretation`, or
`OutsideCurrentScope` where the entry is `scope: out` and row 1 wins first — the shape
`srd-52-conditions`' `malnutrition-hazard` has, as the out-of-scope member of a conflict.

**`bound-term-open`** — a bound narrows a term the map records as open. `bounds` already holds
the `term` to the entry's `evidence`, which proves the corpus says the words. Nothing held them
to the doubt: the term must also occur in `ambiguity.question`, matched without regard to case,
because the question is where the map records the term as open and an owner's ruling quotes a
span of that question (0027). A term the question omits is one no ruling could be compared
against, which is the whole of what a bound earns its place by.

### 4. The fifth trace is already caught, in the factory, and stays there

#258 also names *a ruling that resolves a question the map never recorded as open*.
`tools/factory/rulings.py` already refuses a ruling or a decline on an entry the map does not
record as `fate: unresolved`, and a `span` that is not in the current `ambiguity.question`
exactly once. It stays there rather than being duplicated here: a ruling lives in the engine's
overlay (0027), the validator's publish phase has no overlay, and the validator may not import
the factory (0032). The trace is named in [`docs/validator.md`](../validator.md) with where it is
held, so a reader does not have to find that out by searching.

## Consequences

- The validator reads one artefact it did not read before: the blind second mapping's
  adjudication record, found under `blind-mapping/` beside the map, or named by `--comparison`.
  A map package does not ship it, so a consuming engine finds nothing and the check reports NOT
  VERIFIED rather than ok. That is correct: the package's bytes are what passed (0015).
- **The record has two committed shapes and two verdict vocabularies**, which is a finding rather
  than a design. `compare.py` writes per-flag resolutions carrying a one-letter verdict (`U` is
  "the corpus does not settle it"); trial 9's is hand-written, with its own `verdicts` legend and
  the verdict as the leading clause of a prose `ruling` (`open`). Both are read, neither is
  guessed at, and a record of any third shape is NOT VERIFIED.
  [#273](https://github.com/brandonifco/rules-factory/issues/273) is where that becomes one shape.
- None of the three checks is status-dependent (0015). An overlay must not be able to turn a
  verdict about whether the corpus settles a question, because the corpus is the same either way,
  and rows 2 and 5 of the correspondence table are deliberately not read for that reason.
- The measured miss rate moves from **60 of 64** collapses to **52 of 64**. That is the honest
  headline and it is in [`examples/collapse-trial/`](../../examples/collapse-trial/README.md)
  with the method, not only in a pull request.

### Limits

- **Four in five collapses are still missed.** Every catch comes from a record made by a second
  reader: 8 from an adjudication, 4 from a conflict the corpus itself creates. On the three maps
  with a readable adjudication record the checks catch 8 of 36; on the three without, 0 of 28.
  The ceiling is not the check — it is how much of each corpus was read twice.
- **`superposition` reads verdicts, never reasoning.** An adjudication that says unsettled and
  means something else passes. So does one whose prose names an ambiguous entry for an unrelated
  reason: the carry-forward is established by an id appearing in the adjudication's own words,
  which is weaker than a field would be and is the price of not adding one.
- **It sees `clarity` and `ambiguity` disagreements only.** An unsettled verdict about coverage or
  `kind` is invisible to it — trial 9's `worked-examples-as-entries` was adjudicated `open` and
  became `ambiguity.bounds` under 0031, and nothing here would have noticed either way.
- **Nothing detects the collapse both readers share.** Where two mappers make the same silent
  choice there is no disagreement, no flag, and no trace at all. That is 0014's own limit
  restated one level up, and no field and no check in this record reaches it.
- **Two committed maps have no second mapping** (`faa-part-107-temporal`, `srd-52-conditions`),
  and on those `superposition` proves nothing. It says so rather than passing.
