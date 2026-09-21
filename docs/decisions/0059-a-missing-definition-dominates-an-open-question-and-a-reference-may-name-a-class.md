# 0059 — A missing definition dominates an open question, and a reference may name a class of corpora

## Status

Accepted — 2026-09-21. Records the decisions on
[#218](https://github.com/brandonifco/rules-factory/issues/218) and
[#226](https://github.com/brandonifco/rules-factory/issues/226), both found by trial 9's blind
second mapping of 26 CFR § 1.121-1 ([#8](https://github.com/brandonifco/rules-factory/issues/8)).

**Supersedes** the `definedElsewhere`/`ambiguity` exclusion in
[0005](0005-a-field-earns-its-place-by-being-checkable.md) D, and **extends**
[0020](0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md) § 4 and
[0026](0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)
§ 3, which say what `definedElsewhere` names. Adds no entry field. Adds one manifest rule.

## Part 1 — an entry may be defined elsewhere *and* ambiguous here

### Context

`check_exclusions` refuses an entry carrying `definedElsewhere` beside an `ambiguity` block, and
`corpus-map.md` gives the reason: *"it is what keeps two rows of the correspondence table from
firing with different answers on the same entry."*

`method-of-allocation` in `examples/tax-121-principal-residence/corpus-map.json` is genuinely
both. Its rule is § 1.121-1(e)(3): allocate *"using the same method of allocation that the
taxpayer used to determine depreciation adjustments (as defined in section 1250(b)(3)), if
applicable."*

- **Defined elsewhere.** *Depreciation adjustments* is fixed in 26 U.S.C. § 1250(b)(3), which
  this map's manifest declares as a reference, `admitted: false`.
- **Ambiguous here.** Where the *"if applicable"* condition fails — a portion separate from the
  dwelling unit on which no depreciation was taken — there is no such method, and the corpus
  states no other and names nobody to choose one, while still requiring the allocation.

  The entry's own question names *"(e)(4) Example 6"* as that case and **is wrong about it**:
  Example 6 is non-residential use *within* the dwelling unit, where (e)(1) requires no
  allocation at all and (e)(3) never fires. The independent verdict on this change found it, it
  is verified against the corpus, and it is
  [#407](https://github.com/brandonifco/rules-factory/issues/407) rather than a second commit
  here — the gap the question describes is real and the illustration it reaches for is not, which
  is a claim about the corpus needing its own reading and its own review. This record does not
  rest on the example, only on the condition.

Forced to pick one, the map picked the ambiguity and wrote the definition as a
`crossReferences[].unmapped` reason. **The entry says so itself**, in the map as committed:

> "It is answered here rather than by `definedElsewhere` because this entry already carries an
> `ambiguity` block and the schema excludes the two on one entry; the report records that as
> finding 4."

And the map is inconsistent as a result. `depreciation-not-excludable` quotes the **same statute
for the same term** and declares `definedElsewhere: {"reference": "usc-26-1250"}`. One corpus
reference, two entries, two representations, and what separates them is not the corpus — it is
whether the entry happened to carry an `ambiguity` block.

### Decision

**The exclusion is dropped. An entry may carry `definedElsewhere` (or `beyondAdapter`) and an
`ambiguity` block, and the correspondence table's row order says what the engine returns.**

The exclusion's stated reason has not been true since the table gained an order. The table now
opens *"Rows are checked in order and the first match wins"*, added because *"without an order,
every `status: mapped` entry carrying `fate: unresolved` matches two rows — eleven entries across
the three maps today — and the invariant is unwritable in either direction."* That is the same
problem the exclusion was written for, solved generally and one layer down. Row 3
(`definedElsewhere`) precedes row 6 (`ambiguity.fate: unresolved`), so two rows matching is no
longer two answers: it is one answer and a recorded second fact.

**The order is not arbitrary here, and it was established independently.** Trial 9's adjudication
reached it from the other direction, one edge away, and stated it as a general rule:

> **`definedElsewhere` relocates the reason an entry declines; it never converts a decline into an
> answer.**

A missing definition dominates an open question. A caller who does not have § 1250(b)(3) cannot
even determine whether *"if applicable"* applies, so the definition is the first wall and
`MissingRulesData` is the honest first answer. The question does not disappear: it stays in
`ambiguity.question`, where a person or an overlay ruling under
[0027](0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md) can reach it.

### What changes

- `check_exclusions` no longer refuses the pair. It still holds `clarity` and the block's own
  contents.
- `check_unresolved_reason` gains rows 3 and 4. Its docstring said *"Rows 3 and 4 cannot arise —
  `exclusions` already refuses `definedElsewhere` or `beyondAdapter` beside an `ambiguity`
  block"*; they can arise now, so an entry carrying either field may — and must —
  name `MissingRulesData`, which is what its first matching row produces.
- `method-of-allocation` declares `definedElsewhere: {"reference": "usc-26-1250"}`, drops the
  `crossReferences[].unmapped` item that stood in for it (0026 § 3 refuses a cross-reference
  answering the entry's own `definedElsewhere` pointer a second time), and its
  `unresolvedReason` becomes `MissingRulesData`. The deleted item asserted that *"the schema
  excludes the two on one entry"*, which **was true when it was written** — this record is what
  makes it false, and the entry's note says so, because a reader of the map alone would otherwise
  find a deleted claim and a live counter-example and no account of which governs. That item was
  also the entry's only reference to finding 4 of the trial report, carried forward into the note
  for the same reason.
- The map is **generated**, by `blind-mapping/build-map-c.py` from a frozen Map A and the
  adjudication record, under an invariant that every difference is keyed to a ruling. A schema
  migration is not a ruling and Map A is trial evidence that is not edited to follow the schema,
  so the builder gains a second, separately-labelled kind of step, named by its decision record
  and counted apart from the rulings.

### Part 1's limit, stated rather than argued away

`check_unresolved_reason`'s own prose is the case against this, and it is not wrong:

> "`MissingRulesData` tells them to go and find data that does not exist … An open question
> wearing either reason is an uncertainty misdescribed to the only party who could act on it."

For `method-of-allocation` the engine now answers `MissingRulesData` in **both** of its cases,
and in one of them — depreciation demonstrably never taken — the definition would not have
helped: what is missing there is an interpretation. The entry gives one reason because the table
gives one reason per entry, and it gives the first wall rather than the second.

Two fields do different jobs and this decision rests on the distinction: `unresolvedReason`
describes **the runtime**, and `question` describes **the uncertainty**. Before this, an entry in
this position had to drop one of the two facts to be representable at all. It now keeps both, and
what it loses is a reason that changes with the case — which no single-reason row ever carried.

**What would reopen it:** an entry whose two cases are *both* reachable by a caller who has the
unadmitted corpus. That is evidence the sentence states two rules and the answer is two entries,
which is the contract's existing answer to distributed meaning, not a third reason.

**Two costs the independent verdict named, which this record pays rather than hides:**

- **The interpretive gap stops being machine-readable.** Before, `unresolvedReason:
  RequiresInterpretation` was one field saying *an interpretation is missing here*. After, that
  field records the runtime row, and the only place the gap survives is the prose of
  `ambiguity.question`. Nothing a program reads now distinguishes an entry that defers *and* has a
  gap from one that only defers. That is the honest residue of the objection below, and a new
  field to carry it is what [0005](0005-a-field-earns-its-place-by-being-checkable.md) refuses
  until a check can read it.
- **The answer has a dated expiry.** `MissingRulesData` promises that supplying the data unblocks
  the caller, and in the no-depreciation branch it does not. Worse, if § 1250(b)(3) is ever
  admitted, row 3 stops firing and row 6 answers `RequiresInterpretation` for **both** branches —
  wrongly for the one the statute settles. **Admitting that corpus obliges splitting the entry in
  two**, and `method-of-allocation`'s note now says so, because nothing else would.

The independent verdict argued exactly that, and the argument is recorded rather than dismissed:
where depreciation was taken, `MissingRulesData` is honest and actionable — read § 1250(b)(3) and
proceed; where none was, the caller reads all of § 1250(b)(3) and still has nothing, because what
is missing is not in that statute. Two branches, two reasons, one row. What decides it for now is
that a caller cannot tell which branch they are in *without* § 1250(b)(3), so the first wall is
the first wall in both. If someone shows a branch reachable without it, the entry is two entries
and this record is the reason to split it rather than to add a reason.

## Part 2 — one rule for an unadmitted reference, and a reference may name a class

### Context

Trial 9's two mappers split nine times on the same kind of reference, and the adjudication ruled
it `not-a-corpus-disagreement` because the corpus says nothing about which:

> "A asked whether the rule's meaning is fixed outside and used `definedElsewhere`; B asked
> whether the outcome is a fact the caller reports and used `crossReferences[].unmapped` with a
> caller-supplied parameter."

Separately, § 1.121-1(b)(2) defers to **local law**, which is not a corpus — it is a category of
them, different in each jurisdiction and not knowable at map time. Every other use of
`definedElsewhere` names a publication.

### Decision

**One rule, in three lines, and the exclusion was the only thing that made it two:**

| what the unadmitted passage is to this rule | the field |
|---|---|
| it fixes the **meaning of a term this rule uses** | `definedElsewhere` |
| it is a **different rule** this passage points at — an election, an example, another section | `crossReferences[].unmapped` |
| it is a **fact the caller reports** — an airspace class, the method a taxpayer actually used | neither: no entry, a `note` |

The third line is already in `corpus-map.md` and is unchanged. The first two were one question
with two answers because an entry that was ambiguous could not take `definedElsewhere` at all;
with Part 1 that reason is gone.

**A manifest reference names a publication with a `citation`, or names a class of corpora by
omitting one and saying in a `note` what the class is.** The tax manifest already does the
first half of this — `{"sourceId": "local-law", "admitted": false}` is the one reference of the
eleven with no `citation` — and nothing said so and nothing checked it. `check-map.py --only
manifest` resolves a reference by `sourceId` alone, so a missing `citation` was invisible rather
than allowed.

Recording a single named corpus for local law would be false; leaving the deferral out would
suggest the regulation settles something it explicitly defers. The class is the true thing, and
a reference that is a class still gives its entries `MissingRulesData`: the runtime answer does
not depend on how many corpora the caller has to go and read.

### Limits

- **A class is recognised by an absence.** No `citation` means a class, which is a convention
  rather than a declaration, chosen because
  [0005](0005-a-field-earns-its-place-by-being-checkable.md) refuses a field that buys nothing a
  check can read. The `note` is what a reader gets, and no check can tell whether it describes
  the class truthfully.
- **Nothing checks that a `definedElsewhere` attribution is true of the unadmitted corpus.**
  Trial 9 established what it *can* check — that *this* corpus defers, which is readable in the
  admitted text — and that is unchanged here.
- **The three-line rule is a rule about reading, not a detector.** Nothing fires when a mapper
  writes a definition as a cross-reference; what changed is that there is now one answer to give
  when somebody asks which is right.
