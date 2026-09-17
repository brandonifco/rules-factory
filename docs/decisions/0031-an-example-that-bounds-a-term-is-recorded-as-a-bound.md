# 0031 — An example that bounds a term an operative rule leaves open is a bound on that rule, admitted only where the dimension is comparable

## Status

Accepted — 2026-09-17. Decided by Brandon, the owner. Closes
[#216](https://github.com/brandonifco/rules-factory/issues/216). **Extends
[0005](0005-a-field-earns-its-place-by-being-checkable.md)** by adding one field under its own
test, and **extends [0027](0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md)**:
a ruling on a bounded question carries a `boundary`, and § 5's list of what the factory refuses
gains the contradiction of a bound. Changes no `fate`, no `clarity` and no correspondence row.

## Context

A corpus illustrates its own rules, and the method had two places to put an illustration: an
entry, or nothing. The blind second mapping of 26 CFR § 1.121-1
([examples/tax-121-principal-residence/blind-mapping](../../examples/tax-121-principal-residence/blind-mapping/README.md))
put both to the test on one section and produced the line this record implements:

> An example that is the corpus's **only authority for a rule no operative sentence states** is an
> entry. An example that **bounds a term an operative rule leaves open** is an interpretation
> constraint on that rule, and the schema has no shape for one.

The first half is already applied. § 1.121-1(b)(4) Example 4 nets a $25,000 loss on the dwelling
unit against $270,000 of gain on the vacant land; no operative sentence says a loss does that, and
no entry of the first map could produce $245,000. Map C carries it as an ordinary in-scope entry
(`combined-sale-nets-dwelling-loss`).

The second half had nowhere to go. § 1.121-1(c)(2) counts "short temporary absences" as use and
fixes no length; § 1.121-1(c)(4) Example 4 states that a 1-year sabbatical leave *"is not
considered to be a short temporary absence under paragraph (c)(2) of this section"*, and Example 5
that *"the 2-month vacations are short temporary absences"*. The blind mapper made each an
ordinary in-scope entry **and still recorded `short-temporary-absences` ambiguous** — which is the
finding: the entries and the ambiguity they bound did not interact. Map C quoted both inside
`ambiguity.question` instead, and the row stayed `open`.

**The failure that decides it.** Under 0027 an engine's owner may rule on part of an unresolved
question. An owner could set "short temporary absence" at eighteen months, and **no check would
notice that § 1.121-1(c)(4) Example 4 forbids it**. The corpus's own authority, in the same
regulation, published by the same authority as the rule, was invisible to every check the factory
runs. That is what this record closes, and it is the obligation the blind mapping named as the
price of admitting the field at all under 0005.

## Decision

### 1. A bound is a field on the ambiguity, not an entry

**`ambiguity.bounds` records the authored examples that fix what an open term does and does not
reach.** It sits on the entry whose term is open, never as an entry of its own, because such an
example answers no caller's request and states no rule: it constrains the permissible readings of
another rule. The shape is in
[corpus-map.md](../corpus-map.md#ambiguitybounds--what-an-authored-example-fixes-about-the-open-term):
a `term` that must occur in the entry's own `evidence`, a `dimension`, and `examples`, each with
its own `locator`, one contiguous verbatim `text`, a `verdict` of `applies` or `doesNotApply`, and
the `value` where its fact pattern sits in the dimension.

Only on `fate: unresolved`. A bound's force is that a ruling is compared against it, and a settled
ambiguity has no ruling — its record is prose no checker reads, so a bound there would be recorded
and never read, which is precisely what 0005 refuses.

### 2. A bound is admitted only where the dimension is comparable

**This is the restriction the decision turns on.** 0005 says a field earns its place by being
checkable. A bound is mechanically checkable only where it and a later ruling are values on one
scale: *"a 1-year sabbatical is not short"* against a ruling setting *"short ≤ 18 months"* is a
catchable contradiction, because both are durations. *"Adjacent"*, bounded by a fact pattern about
a public road and a corner, is comparable to no threshold any ruling would state. **A field that
is checkable sometimes and merely recorded the rest of the time does not satisfy 0005**: it would
read as structure and behave as prose, and the reader could not tell which entries were which.

So `dimension` is a closed vocabulary holding only what a checker compares — today `duration`, in
ISO 8601, on a scale of 30-day months and 12-month years so that `P1Y` and `P12M` are one value
and a ruling cannot clear a bound by restating the length. A dimension is admitted when a corpus
states a bound in it **and a parser and its tests arrive with it**, never before; that is 0004's
rule about `modality` applied to a second field. `check-map.py --only bounds` **refuses** a bound
in any other dimension, naming why and saying where the reading belongs instead: prose in
`ambiguity.question`, unchecked and admittedly so. A field that silently accepted the thing it was
scoped to exclude would be the defect this record exists to avoid.

### 3. An owner's ruling on a bounded question is compared against the bounds

Extending 0027 § 2 and § 5. Where the entry's ambiguity carries bounds, a ruling on it carries
**`boundary`**: `{dimension, operator, value}` — the line it draws, `operator` one of `<=`, `<`,
`>=`, `>` — or `null`, declaring that the ruling draws no line in that dimension and answers some
other part of the question. `boundary` is refused on a ruling whose entry has no bounds, because
nothing would compare it.

`tools/factory/rulings.py` evaluates a stated line at every bound's value and refuses the ruling
where the verdict it implies is not the verdict the example states, **naming the example, its
citation and its words**. That module is vendored into every engine as `scripts/factory/rulings.py`
and is run by `generate.merge` on every `produce` and by the gate's `map-overlay.py merge`, so the
check lands in both places at once: **the engine fails its own gate rather than answering.** An
eighteen-month ruling on `short-temporary-absences` fails it, naming § 1.121-1(c)(4) Example 4.

### 4. A bound is located like `evidence`

A bound quotes the corpus and cites it, so the three locator checkers hold it to the citation it
names, by the same code that checks `evidence` — `check-locators.py` (printed page),
`examples/faa-part-107/check-locators-section.py` (section designation) and
`examples/srd-52-combat/check-locators-pdf-text.py` (page-marked extraction). A bound whose words
are not at its citation fails the run: a gate decided on a quotation of nothing is the failure a
summary in `evidence` already was ([#18](https://github.com/brandonifco/rules-factory/issues/18)).

**A bound does not reach a section or a page for `coverage`.** Coverage asks which parts of the
declared extent an entry's own evidence reached; an example quoted to bound someone else's term is
not a verdict on the paragraph it sits in.

### 5. The bounds of one term must be mutually consistent

A bounded term is one-sided — short, long, near, far — so the fact patterns it applies to sit
wholly on one side of the ones it does not. `check-map.py --only bounds` refuses a set of examples
no single threshold separates, in either direction, and nothing declares a direction: which side
the term applies on is the corpus's to say and the examples' to show. Two bounds that cannot both
hold are a defect in the map, not an ambiguity in the corpus.

## Alternatives considered

**Amend 0005 to allow a partially checkable field** — admit bounds in any dimension, check the
comparable ones and record the rest. Rejected. It weakens the one test this schema is held
together by. Every field then arrives with "it is checkable where it can be", and the answer to
"what does this field buy" becomes "sometimes, something". The uncomparable bounds also lose
nothing by staying prose: `ambiguity.question` already carries them, and a reader reads them
there.

**Add nothing; leave the examples quoted in `ambiguity.question`,** which is what Map C did while
#216 was open. Rejected, because it accepts the failure in Context: a ruling can silently
contradict an example the same corpus authored, and the factory's whole claim is that an engine
never presents an owner's answer as the corpus's. This is the alternative that was in force, and
it is the one the failure indicts.

**An interpretation constraint as its own entry** (the blind mapper's shape). Rejected on the
evidence it produced: the entries answer no caller request, `dependsOn` runs backwards (an example
does not depend on the rule, it constrains it), `kind: value` does not fit an example, and nothing
ties the constraint to what it constrains — which is the one thing that mattered.

**A `boundary` the ruling may omit.** Rejected. An omission is invisible, and the hole this record
closes would reopen entry by entry. `boundary` is required on a ruling whose entry is bounded, and
`null` is the declaration — printed by `produce` and by the gate, so a reader sees it.

**Generate the boundary into `Rulings.g.cs` and provenance.** Not done. 0027 § 4 leaves to the
engine which results rely on which ruling; the boundary is what the factory checks the ruling
against, not something the engine surfaces, and generating it would change every engine's public
`OwnerRuling` for no checked claim.

## Consequences

- **§ 1.121-1's map carries the first bounds**, on `short-temporary-absences`, from (c)(4)
  Examples 4 and 5. `blind-mapping/build-map-c.py` applies them from the adjudication record's
  `worked-examples-as-entries` row, which is no longer `open`, and the map's `review.json` records
  the new bytes.
- **No other committed map gains bounds.** A survey of all 83 unresolved ambiguities across the
  committed maps found no second instance: Part 107 contains no worked example at all, the SRD
  conditions slice has none touching a mapped term, and every other candidate either illustrates
  the settled side of its rule or turns on a categorical fact — hidden and unaware, whose men hold
  a point, a road and a corner — that no threshold is comparable to. That is one corpus's evidence
  for the shape, which is less than the blind mapping asked for; the restriction in § 2 is what
  keeps the field from being stretched over the cases that do not fit while a second corpus is
  found.
- **An engine with no bounded entry is unchanged.** No new overlay key, no new generated file, no
  new provenance field, and nothing new in its gate's output.

## What this does not close

- **The uncomparable bounds are still unchecked.** "Adjacent to", "incapable of self-care", "all
  the facts and circumstances" are bounded or illustrated by the corpus in ways no ruling can be
  compared against. They stay prose in `ambiguity.question`, and an owner's ruling that
  contradicts one of those readings is refused by nothing here. That is deliberate, and it is the
  price of § 2.
- **An example bounding a term in a dimension no ruling will state remains prose**, even where the
  dimension is comparable in principle: if no owner ever draws a line in it, the bound is recorded
  and never read. Nothing detects that state.
- **An example the mapper never read is invisible**, exactly as an unrecorded conflict is (0007).
  The map says which examples bound the term; nothing says which it missed.
- **A bound's `value` is a mapper's reading.** That Taxpayer D's sabbatical was a year is in the
  quoted words; that its length is the feature the example turns on is a judgement, and no check
  makes it.
- **Nothing holds a ruling's `boundary` to the `answer` beside it**, or a `boundary: null` to the
  truth. An owner who draws a line and declares none passes, and review is what reads that — the
  same residue 0027 § 7 already records for `answer` and for `ruledBy`.
- **One term, one dimension per ambiguity.** An ambiguity bounded on two terms, or in two
  dimensions, has no shape here. No corpus has produced one, and inventing the shape from zero
  instances is the mistake 0004 avoided.
