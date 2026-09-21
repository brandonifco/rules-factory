# 26 CFR § 1.121-1: the blind second mapping, adjudicated

The procedure in [method.md](../../../docs/method.md) ("Before the map is used — a blind second
mapping", [0014](../../../docs/decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md)),
applied to [trial 9's map](first-map.json). A second mapper who had not seen that map mapped
the same section; the two were compared field by field; every disagreement was answered from the
corpus and recorded before any reconciled map existed.

Three maps, and only one of them is used:

| | file | entries | in scope | ambiguous | status |
|---|---|---:|---:|---:|---|
| **A** | [`first-map.json`](first-map.json) | 37 | 31 | 8 | the first mapping. **Frozen evidence, not edited.** It was `../corpus-map.json` until Map C was promoted to that name (#8), and moved here rather than into git alone because `build-map-c.py` reads it. |
| **B** | [`blind-map.json`](blind-map.json) | 44 | 34 | 6 | the blind second mapping, copied verbatim from the mapper's bundle with its [`blind-map-manifest.json`](blind-map-manifest.json). **Frozen evidence, not edited.** |
| **C** | [`../corpus-map.json`](../corpus-map.json) | 38 | 32 | 8 | A corrected to every ruling in [`resolutions.json`](resolutions.json). This is the map the example publishes and anything is built from. |

The corpus is [`../section-1.121-1.xml`](../section-1.121-1.xml), sha256
`faf3e310a81b1d00729fd69fb422342bcff8049a98a0ae80955be3287e30bab2`. Every quote in the record is
of those bytes; 26 U.S.C. 121, 280A, 1250 and 6511 are named by the section and are not admitted,
and nothing outside the extract was consulted for any ruling.

## What is here

- [`blind-map.json`](blind-map.json) + [`blind-map-manifest.json`](blind-map-manifest.json) — Map B as
  the mapper left it.
- [`compare.py`](compare.py) → [`results.json`](results.json) — the field-by-field comparison.
  Entries are aligned **by the text they quote**, not by id: the two mappers chose ids
  independently, so a shared id would be a coincidence rather than a claim. `python3 compare.py`
  rewrites `results.json`; `--table` prints the difference table.
- [`resolutions.json`](resolutions.json) — **the adjudication record.** One `adjudications` list:
  four rows `group: disagreement`, each about a rule and each with the six fields 0014's review
  needs, and ten rows `group: family` covering every remaining flag. A disagreement with no row
  would leave the map unusable. Its shape is the one every trial's record has
  ([0060](../../../docs/decisions/0060-one-adjudication-record-one-shape-and-the-vocabulary-is-declared-in-the-file.md)):
  the verdict is a `verdict` field rather than the opening clause of the prose, the prose beside
  it is `reason`, and the `verdicts` legend — which this record always carried — is what says what
  each term means, with `unsettledVerdict: "open"` naming the one that means the corpus does not
  settle it. `graph-shape` is the one row answered two ways, which is what the legend's `mixed`
  says; its reason says which went which way.
- [`first-map.json`](first-map.json) — Map A as the first mapping left it.
- [`build-map-c.py`](build-map-c.py) → [`../corpus-map.json`](../corpus-map.json)
  — Map C, built from Map A by applying exactly the changes the record rules, keyed to row ids.
  `--check` fails if the published map is not what the script builds, and `scripts/validate.sh`
  runs it, so a correction nobody ruled on cannot be slipped into the map that is used — and
  neither can a change to Map A, which nothing else checks now that it is not a map.
- Map C's `blind-second-mapping` review of its bytes (0017) is [`../review.json`](../review.json),
  beside the map it reviews, where the checker's glob looks for it.

## Counts

Aligned by quoted text: **36 partnerships**, covering 36 of Map A's 37 entries and 36 of Map B's
44. One entry is A's alone, eight are B's alone, and none is unalignable for want of a quote.

| compared field | pairs agreeing | pairs differing |
|---|---:|---:|
| `scope` | 36 | 0 |
| `clarity` and whether `ambiguity` is present | 33 | 3 |
| `kind` | 29 | 7 |
| `locator.citation` (same passage, different depth) | 18 | 18 |
| whether `definedElsewhere` is present | 30 | 6 |
| `enabledBy` | 6 | 30 |
| `dependsOn` | 28 | 8 |
| `suspendedBy` | 35 | 1 |

**The two maps never once disagreed about whether a rule is in the engine's scope.** They
disagreed about clarity three times, and those three plus one entry only B has are the four
adjudicated in full.

## The four disagreements

Each is recorded in [`resolutions.json`](resolutions.json) with all six fields — what A said
verbatim, what B said verbatim, the corpus's own words, why they differed, the ruling (the
`verdict` field and the `reason` beside it), and what it teaches beyond this entry. Summarised:

| # | entry | A | B | ruling |
|---|---|---|---|---|
| 1 | `vacant-land-sale`, § 1.121-1(b)(3)(i) — "adjacent to" | ambiguous | clear | **A** |
| 2 | `out-of-residence-care`, § 1.121-1(c)(2)(ii) — "incapable of self-care" | ambiguous | clear | **A** |
| 3 | `allocation-required`, § 1.121-1(e)(1) — "separate from the dwelling unit" | ambiguous | clear | **B's verdict, neither's reasoning** |
| 4 | `combined-sale-nets-dwelling-loss`, § 1.121-1(b)(4) Example 4 | no entry | ambiguous | **B** — a coverage miss |

### 1. Is the ambiguity in the word, or in the decomposition?

**In the word. The granularity hypothesis was testable and is refuted.** The premise this
adjudication was given — that Map A carried § 1.121-1(b)(3) in one coarse entry whose vague term
contaminated several rules, against six fine clear entries in Map B — is not what the maps say.
Each decomposes (b)(3) into **seven** entries; all seven partner one-to-one by quoted text; six
of the seven pairs agree the rule is clear. The only verdict difference is on the one entry that
contains the word "adjacent". Nothing was contaminated, because nothing was merged.

The ruling for A rests on evidence neither map used: inside the same four-item list, (C) states a
window, its length and its direction — *"within 2 years before or 2 years after the date of the
sale or exchange of the vacant land"* — and (A) states no measure of adjacency at all. A list
that fixes a measure for one condition and none for another has a blank in it.

### 2. Does the "unresolved decision boundary" principle survive?

**No, and this was the most productive failure of the exercise.** B's formulation — *undefined
language is not automatically an ambiguity; it becomes one when resolving the rule requires
choosing a boundary the corpus does not supply* — was tested against the five ambiguities both
maps agreed on. It keeps two of them (`short-temporary-absences`, a boundary on duration;
`principal-residence-majority-of-time`, where "ordinarily" leaves the displacing case unfixed).
It fails on three. The two *"all the facts and circumstances"* entries supply no dimension for a
boundary to be drawn on at all, so read strictly nothing is left unsupplied and both would be
clear — and B called both ambiguous, on the ground that the corpus *"names nobody whose
determination is operative"*, which is A's ground, not B's own. `method-of-allocation`'s *"if
applicable"* leaves a **case** unfixed, not a boundary. Read loosely enough to keep all five,
"boundary" means "anything the corpus did not fix", and the formulation is corpus-map.md's gate 1
restated, which both maps already share.

So it is either too narrow to hold the agreed ambiguities or too broad to do any work, and B did
not apply it consistently inside its own map. What replaces it is already in the docs and was
quoted by neither map:
[0010](../../../docs/decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md)'s *whose fact it
is decides nothing*, plus the comparative test above. Gate 1's escape — a fact the rule tests, a
caller-supplied parameter with no entry — is available for a predicate with a determinate
extension the caller can simply report (an authorization granted, a licence held, a closing date,
a sum of money). It is not available for a predicate whose application is the contested
classification, however plainly the caller is the only person who could answer.

§ 1.121-1(c)(2)(ii) makes that concrete in one sentence: it fixes a quantity (*"periods
aggregating at least 1 year"*), a window, an ownership condition and an institutional test for
the facility (*"licensed by a State or political subdivision to care for an individual in the
taxpayer's condition"*) — and states no degree, no dimension and no determiner for the
incapacity, in the same sentence where it assigns an institutional determination to the element
beside it.

### 3. Does the § 280A point change how `definedElsewhere` works?

**It does not change what the field means, and it sharpens what it can do.** § 280A(f)(1) is
outside the frozen corpus and its content cannot be checked here at all — but a `definedElsewhere`
attribution never asserts what the other corpus says. It asserts that *this* corpus defers, and
that claim is checkable from the admitted text alone: *"the term dwelling unit has the same
meaning as in section 280A(f)(1)"* is in the extract, and both maps quote it. So this
plausible-looking attribution is falsifiable after all, on the narrow question it actually makes.

What it can never do is settle an ambiguity, and that is the general rule:
**`definedElsewhere` relocates the reason an entry declines; it never converts a decline into an
answer.** corpus-map.md already forbids one entry carrying both `definedElsewhere` and an
`ambiguity` block; this is that exclusion arriving one edge away. An entry whose `dependsOn`
reaches a `definedElsewhere` entry inherits `MissingRulesData`, not `RequiresInterpretation`, and
must not be recorded `clear` on the strength of the pointer either. Both maps failed it from
opposite sides, and B's own map contradicts B two entries away, where `dwelling-unit-definition`
says it declines with `MissingRulesData`.

The ruling itself went to neither reading. The corpus **does** state the separateness test, in
(e)(1)'s third sentence — *"No allocation is required if both the residential and non-residential
portions of the property are within the same dwelling unit"* — with (e)(2) closing the partition
from the other side by subtracting *"appurtenant structures or other property"*. A stable is
separate (Example 1); a law office inside the house is not (Example 5); a basement with its own
entrance is settled by counting dwelling units (Example 3). Both mappers stopped before the third
sentence.

### 4. A coverage miss, verified against the corpus

Example 4 excludes **$245,000** where the dwelling unit sold at a **$25,000 loss** and the vacant
land realized **$270,000** of gain. $270,000 − $25,000 = $245,000, and the maximum limitation
amount is $250,000, so the cap is not what produces the figure: the loss is netted against the
gain. The merger the operative text states is expressly bounded — *"For purposes of section
121(b)(1) and (2) (relating to the maximum limitation amount of the section 121 exclusion), the
sale or exchange of the dwelling unit and the vacant land are treated as one sale or exchange"* —
and no sentence of (b)(3)(ii) says a loss on one transaction reduces the gain excludable on the
other. **No entry of Map A can produce $245,000.** An engine built from Map A would answer
$250,000 for the regulation's own worked facts, in the regulation's voice.

This is the finding that could not have come from a tool. Map A's every locator resolves, its
declared extent is reached, it passes `check-map.py` at publish phase and packs byte-identically.
The rule is missing from a paragraph the map **does** cite, by an entry that declines it — and
`extent` coverage is satisfied by one verified quote per section, so it cannot see inside a
declined paragraph. A blanket `scope: out` verdict on a paragraph is where a rule is lost with
every check green, which is method.md's own rule (*"`scope` is decided per rule, never per
section"*) and the way the backgammon map lost the number of faces on a die.

A tooling reason was in the way and is fixed here. § 1.121-1's examples sit in `<EXAMPLE>`
elements that the eCFR locator checker did not index, so **no entry could cite one at all** —
trial 9's own finding 3, and part of why it declined them wholesale.
`examples/faa-part-107/check-locators-section.py` now indexes an `<EXAMPLE>` under the paragraph
that introduces it and reads `§ 1.121-1(b)(4) Example 4` as a citation, with eight tests in
`tools/tests/mapvalidator/test_check_locators.py`. **A grammar that cannot cite a passage quietly decides the
passage holds no rules.**

## The worked-examples question — [#216](https://github.com/brandonifco/rules-factory/issues/216)

*(Written while the question was open, and kept as written; the decision is at the end of this
section.)*

**Not solved, and Map C does not adopt B's shape.** B mapped two of the (c)(4) examples as
ordinary in-scope entries — `sabbatical-not-short-absence` and `two-month-vacation-short-absence`,
`kind: value`, `clarity: clear`, opposite verdicts on the same paragraph — while **still**
recording `short-temporary-absences` ambiguous. That B could do all three at once is itself the
finding: the entries and the ambiguity they bound do not interact.

**What B's representation preserves.** The corpus's only authority on "short" stops being a
sentence in a note and becomes a located, quoted, checkable entry. Both bounds survive a
`scope: out` verdict on the paragraph around them. The relation is visible in the graph at all,
as a `dependsOn` edge. And it is decided per rule rather than per paragraph, which is what
method.md asks for.

**What it loses.** Four things. The entries answer no caller request — nobody asks an engine
whether Taxpayer D's sabbatical was short — so they are `scope: in` entries with no reachable
operation, and the map's vocabulary is meant to be the engine's runtime vocabulary. The edge runs
the wrong way: `dependsOn` is implementation order, and an example does not depend on the rule,
it **constrains** it. `kind: value` is a poor fit — an example is not a table the engine
consumes. And nothing ties the constraint to the thing it constrains: an owner's `ruling` on
`short-temporary-absences` under
[0027](../../../docs/decisions/0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md)
could set the line at eighteen months and no check would notice that Example 4 forbids it. That
last one is the whole point of an interpretation constraint, and B's shape does not carry it.

**A candidate shape**, recorded and not adopted:

    rule → interpretation constraint (example) → fact pattern + authoritative result

**What it would take to decide.** Three things, none of them settled by this corpus. (1) A second
corpus that constrains its rules by worked example in the same way, so the shape is not designed
from one regulation — Treasury regulations do this everywhere, so the evidence is cheap. (2) A
checkable obligation, without which the field is unearned under
[0005](../../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md): the obvious
one is that an engine ruling on an entry must be tested against every constraint attached to it,
which makes the constraint carry a fact pattern and an expected result, not prose. (3) A decision
on whether a constraint is an entry at all or a field on the entry it constrains — B's evidence
bears on this and does not settle it.

**A line worth proposing meanwhile**, because it is what separates #216 from ruling 4 above:

> An example that is the corpus's **only authority for a rule no operative sentence states** is an
> entry. An example that **bounds a term an operative rule leaves open** is an interpretation
> constraint on that rule, and the schema has no shape for one.

**Decided 2026-09-17 by [0031](../../../docs/decisions/0031-an-example-that-bounds-a-term-is-recorded-as-a-bound.md),
and the paragraphs above are left as they were written.** The proposed line is the decision's, and
the schema now has the shape it says was missing. `combined-sale-nets-dwelling-loss` is an entry,
as it already was; the two "short" bounds are `short-temporary-absences.ambiguity.bounds` — each
with its citation, its verbatim text, its verdict and its value in the dimension that makes it
comparable (duration: the sabbatical at `P1Y`, `doesNotApply`; the vacations at `P2M`, `applies`)
— rather than a quotation inside the question. What that buys is the fourth thing B's shape lost:
an owner's ruling under 0027 states the line it draws in the same dimension, and one setting
"short temporary absence" at eighteen months fails the engine's gate naming Example 4.

Of the three things this record said it would take to decide, (2) and (3) are answered — the
checkable obligation is the ruling comparison, and a constraint is a field on the entry it
constrains, not an entry. (1) is **not**: a survey of every unresolved ambiguity in this
repository's maps found no second corpus instance, because Part 107 contains no worked example at
all and every other candidate either illustrates the settled side or turns on a categorical fact.
0031's answer to designing from one regulation is the restriction rather than the delay: bounds
are admitted only where the dimension is comparable, which is what keeps the field off the cases
that do not fit.

## What Map C changes, and what it does not

Six rulings land in Map C, every one keyed to a row of the record and applied by
[`build-map-c.py`](build-map-c.py):

- `allocation-required` becomes `clear`, loses its `ambiguity` block, and gains
  `suspendedBy: [no-allocation-within-dwelling-unit]` (rows `separate-from-the-dwelling-unit`,
  `graph-shape`).
- `combined-sale-nets-dwelling-loss` is added, ambiguous and unresolved (row
  `combined-sale-nets-dwelling-loss`), and `examples-b`'s note stops declining the paragraph whole.
- `short-temporary-absences` carries both example bounds as `ambiguity.bounds`, and its question
  states that they bound the term rather than re-quoting them (row `worked-examples-as-entries`,
  ruled later by 0031; the bounds' own text is held to the corpus by the locator checker).
- `ownership-and-use-aggregation` and `residence-excludes-personal-property` become `value`
  (rows `kind-two-year-equivalents`, `kind-residence-exclusion`). The second was caught by Map A's
  own neighbouring verdict: it records *"may include"* as a value and *"does not include"*, one
  sentence later, as an operation.
- **`enabledBy: [effective-date]` on all 30 remaining in-scope entries** (row
  `effective-date-gate`). This is the largest correction. § 1.121-1(f) says *"This section is
  applicable for sales and exchanges on or after Decmeber 24, 2002"* — it names the whole section,
  which makes it a rule that makes every rule of the section reachable, and 0011 puts that in
  `enabledBy`. Map A recorded the gate and **none** of its reach, which is exactly the
  `full-table-suspension` omission method.md warns about, and it passed every check in this
  repository.

**One disagreement was recorded open and is now ruled elsewhere:** #216's shape, row
`worked-examples-as-entries`. Under 0014 leaving it open was a legitimate outcome — the corpus
settles what a rule says, not what a schema should be — and it was recorded rather than guessed
until 0031 decided the schema question. The row keeps its original ruling and carries the later
one beside it.

What Map C keeps from A, over B's objection, with reasons in the record: the eighteen
citations one level shallower than the regulation's own numbering (tested — written at the
regulation's depth, eighteen of thirty-seven fail the locator checker, because the eCFR XML runs
a first sub-paragraph into its parent's `<P>`); `definedElsewhere` rather than
`crossReferences[].unmapped` for six unadmitted references, which is a schema question and not a
corpus one; `kind` on four declined signposts, where the field has no subject; and the five
entries B has for pointer targets and the source credit, where both maps record the same reading.

## What this run does not establish

It is one section, two mappers and a comparison scoped by hand. The three clarity disagreements
are 3 of 36 partnerships, which is not a rate for anything. The largest correction — 30 missing
gate edges — is one omission repeated, not thirty findings. And the silent failure 0014
names is untouched: where both mappers made the same mistake there is no flag, and this record
contains one instance where they nearly did, since **both** maps stopped before the third
sentence of § 1.121-1(e)(1) and only their opposite verdicts made anyone read it.
