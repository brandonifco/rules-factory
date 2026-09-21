# Trial 10 — attacking the validator with a damaged map

Every check in `check-map.py` has been watched failing on a unit fixture written beside it.
That proves each check *can* fire. It says nothing about how much of a real error reaches the
gate, and nobody had taken a committed, passing map, damaged it deliberately, and counted
([#259](https://github.com/brandonifco/rules-factory/issues/259)). The equivalent number exists
for the method — [0014](../../docs/decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md)
measured the mechanical checks at 1 of 15 injected comprehension errors, which is the number that
made the blind second mapping mandatory — and for the factory's overlay. It did not exist for the
validator.

**The number, first, and then the sentence that governs it.**

> **Fourteen named mutations were applied, one at a time, to five committed maps across three
> locator grammars. Sixty-two of the seventy combinations had somewhere to land. The validator
> refuses twenty of them and passes forty-two — a miss rate of 68%.**
>
> **First measured at 16 of 62 refused (74% missed), at commit `69167d8`.** Four rows have moved
> since: two are the epistemic checks
> [0034](../../docs/decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md) added,
> and two are the `narrow-extent` cells
> [#269](https://github.com/brandonifco/rules-factory/issues/269) closed. *What moved, and why*
> below says which and why. That the table moves when a check grows is
> the point of re-measuring it in the gate rather than dating it.
>
> **That is not a verdict on the validator. It is the denominator it did not have.** Several of
> these misses are provably outside a structural checker's reach, which is *why* the blind second
> mapping exists. What the trial changes is that each of them is now measured rather than argued,
> and each is dispositioned: an issue, or a line in the validator's own statement of its limits
> that says it was measured.

Re-measured on every pull request (`examples/validator-attack/results.json` carries the commit it
was recorded at, every run, and what each failing check actually said).

## The laboratory

`tools/mutate-map.py`. One run is: copy a committed map into a temporary directory, apply one
named mutation, and run every detector the validator has for that corpus —

| detector | what it reads |
|---|---|
| [`tools/check-map.py`](../../tools/check-map.py) | the map, its manifest and this repository. Never the corpus |
| [`tools/check-locators.py`](../../tools/check-locators.py) | page markers in a Gutenberg plain text |
| [`examples/faa-part-107/check-locators-section.py`](../faa-part-107/check-locators-section.py) | containment in an eCFR section tree |
| [`examples/srd-52-combat/check-locators-pdf-text.py`](../srd-52-combat/check-locators-pdf-text.py) | page markers in PDF-extracted text |

— comparing each named check's verdict against the same check's verdict on an unmutated control.
A check already red on the control proves nothing and is excluded by construction rather than by
judgement. No committed map is ever written to; a unit test asserts that against the real
`hoyle-backgammon` map's bytes.

**Detected means the run went red.** A check that turns without failing the run is recorded as
`signalled` and counted as a **miss**, because a map that passes is a map that ships. Two
mutations landed there, and they are [#268](https://github.com/brandonifco/rules-factory/issues/268).

**`check-map-review.py` is deliberately not a detector.** It holds a map's exact bytes to a review
of them (0017), so it goes red on *any* edit, including re-serialisation. Counting it would report
100% detection by a check that has not read a word of the map — the trap the injection trial's
manifest pin was ([../injection-trial/README.md](../injection-trial/README.md)).

## The subjects

Two structurally different genres, as #259 requires, and five maps because no single map carries
somewhere for all fourteen mutations to land: a regulation's map has `enabledBy` and no
`assertedBy`, a rulebook's the reverse, and exactly one protocol in the repository declares a
`defined-term-use` vocabulary.

| map | genre | locator grammar | applied | refused | missed |
|---|---|---|---:|---:|---:|
| [`hoyle-backgammon`](../hoyle-backgammon/) | rulebook, 1909 | page markers, Gutenberg text | 13 | 6 | 7 |
| [`faa-part-107`](../faa-part-107/) | regulation | section designation, eCFR XML | 13 | 6 | 7 |
| [`tax-121-principal-residence`](../tax-121-principal-residence/) | regulation | section designation, eCFR XML | 12 | 3 | 9 |
| [`srd-52-combat`](../srd-52-combat/) | rulebook | page markers, PDF-extracted text | 14 | 2 | 12 |
| [`srd-52-conditions`](../srd-52-conditions/) | rulebook, a glossary | page markers, PDF-extracted text | 10 | 3 | 7 |

## The table

`n/a` is a corpus with nothing for that mutation to damage — recorded, never scored. A cell naming
checks is a refusal, and names the checks that turned.

| mutation | hoyle-backgammon | faa-part-107 | tax-121-principal-residence | srd-52-combat | srd-52-conditions |
|---|---|---|---|---|---|
| `drop-entry` | **missed** | coverage | **missed** | **missed** | **missed** |
| `drop-enabled-by` | **missed** | n/a | **missed** | **missed** | n/a |
| `drop-suspended-by` | **missed** | **missed** | **missed** | **missed** | n/a |
| `clear-to-ambiguous` | **missed** | **missed** | **missed** | **missed** | **missed** |
| `ambiguous-to-clear` | **missed** | superposition | **missed** | **missed** | **missed** |
| `assertion-to-operation` | signalled only: asserted-by | **missed** | n/a | **missed** | n/a |
| `invent-depends-on` | **missed** | **missed** | **missed** | **missed** | **missed** |
| `neighbour-evidence` | cross-references, locators | locators | cross-references, locators | **missed** | locators |
| `same-passage-evidence` | cross-references | **missed** | **missed** | **missed** | **missed** |
| `move-locator` | locators | locators | locators | locators | locators |
| `omit-definition` | n/a | **missed** | **missed** | **missed** | **missed** |
| `remove-applicability` | superposition | signalled only: gates | **missed** | **missed** | n/a |
| `hide-cross-reference` | cross-references | cross-references | cross-references | **missed** | **missed** |
| `narrow-extent` | extent-bounds | extent | n/a | extent, extent-bounds, extent-end | extent, extent-bounds |

Twenty refusals, made up of twenty-five turned checks, and seven check names account for every
one: `locators` (9), `cross-references` (6), `extent` (3), `extent-bounds` (3), `superposition`
(2), and one each from `coverage` and `extent-end`. Counting the two signalled-only turns,
**five of the twenty-five checks in `check-map.py` ever turned; twenty never did.** They are not
idle — they hold shapes a hand-written map breaks and a mutation of an already correct map does
not — but a reader should not take twenty-five checks as twenty-five chances of being caught.

`extent-bounds` is new here, and is a locator checker's rather than `check-map.py`'s: it is the
half of #269 that placing a citation could not reach, and the paragraph on `narrow-extent` below
says why.

## What the table says

**One mutation is caught everywhere: `move-locator`.** A citation moved by one unit is the only
damage all three grammars refuse, and it is refused because the evidence stays put while the
citation moves. That is the whole of what a locator checker knows how to do, and it does it.

**`neighbour-evidence` is the one #259 called interesting, and it splits by grammar.** Replacing
an entry's evidence with the neighbouring passage's — the locator still resolves, the quote is
still verbatim of the extraction — is refused by both section-designation maps and by
`hoyle-backgammon`, and **missed** by `srd-52-combat`. The reason is granularity, not rigour: a
section citation names a paragraph, so a neighbour's sentence is *outside* it and containment
catches the swap; a page citation names a page, so a neighbour's sentence is usually on it.
`same-passage-evidence` — the same error committed inside one cited passage — is missed by four of
five, including both regulations. **This is the shape of error that survived a mapping trial, a
build and a review thirteen times in the backgammon map, and the measurement says the validator's
reach against it is a property of how finely the corpus is designated.**

Two of the refusals in those two rows came from `cross-references` rather than from a locator
checker, and they are worth naming rather than banking. `crossReferences.cites` must appear
verbatim in the entry's own evidence, so swapping the evidence out from under a recorded pointer
breaks the anchoring. That is bookkeeping catching a swap, not anything having read the corpus:
the harness therefore prefers a recipient entry that records no cross-reference, and the
refusals that remain are where the *donated* sentence carried a pointer phrase the recipient does
not answer. Either way the catch depends on what the donor sentence happened to contain.

**The gate graph is not checked at all.** `drop-enabled-by`, `drop-suspended-by` and
`invent-depends-on` were missed by every map that had one to damage — 0 of 13. The docstring
already said nothing checks that a gate list is complete; this says the same about an edge that is
present and wrong.

**The clarity flip is asymmetric, and one direction has moved.** At `69167d8` both directions were
0 of 10, and the trial's sharpest single finding was that they are not the same kind of miss:
premature collapse cannot be caught *structurally*, but an invented ambiguity could be, because
`ambiguity.question` is free prose where `crossReferences.cites` on the same entry must be verbatim
of the evidence. That second half is still true and still
[#271](https://github.com/brandonifco/rules-factory/issues/271): `clear-to-ambiguous` remains 0 of
5.

The first half is now **1 of 5**, and the way it is caught is the interesting part — not
structurally at all. `superposition`
([0034](../../docs/decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md)) reads
the adjudication record of the blind second mapping beside the map, and on `faa-part-107` the
collapsed entry is one a second mapper read as ambiguous and the adjudication answered *the corpus
does not settle it*. Nothing in the map betrays the collapse; the record of the second reading
does. On the other four maps the entry the harness happens to collapse first carries no such
adjudication — two of those maps were never mapped twice — and it stays missed.

**`narrow-extent` is closed, and needed two checks rather than one.** `extent` now places a page
citation inside the declared range exactly as it always placed a section designation, which
refuses the narrowing on both SRD maps. It does **not** refuse it on `hoyle-backgammon`, and the
reason is worth recording: that map cites pp. 271–278 inside a declared extent of 271–280, so
narrowing the declaration by a page moves no citation at all. What notices is the *quote* —
`die-faces`, cited at p. 277, quotes 3,292 characters running to p. 280 — and `extent-bounds`,
the check that places a quote inside the range, is what that needed. It is
[0024](../../docs/decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)'s
`extent-end` without a heading: that check already refused an in-scope quote past the boundary on
the extent's last page, and both ends of a range are the same fact.

**`hide-cross-reference` divides exactly where [#208](https://github.com/brandonifco/rules-factory/issues/208)
says it should.** Refused on all three corpora whose pointers are phrases; missed on both SRD maps,
whose corpus points by naming a defined term. #208 measured that at 0 of 51 references by argument
and by inspection; this is the same fact arrived at from the other end.

## Every miss, dispositioned

The two categories are kept apart, because that is the point of the exercise.

### A miss the validator could catch and does not — an issue

| mutation | what is missed | issue |
|---|---|---|
| `assertion-to-operation`, `remove-applicability` | a check whose subject matter the damage removed says NOT VERIFIED and the run stays green | [#268](https://github.com/brandonifco/rules-factory/issues/268) |
| `drop-entry` | `coverage` counts units touched, so deleting a rule is invisible in 4 of 5 maps. `coverage` now reports how much of the extent is quoted ([0055](../docs/decisions/0055-coverage-reports-how-much-of-the-extent-is-quoted-and-a-map-declares-the-floor.md)) and fails a map that quotes less than the `extent.quoted` floor it declares — **and no committed map declares one**, because adding the field changes the map's bytes and so its review ([0017](../../docs/decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)). Each is its owner's decision, and until one is made these four cells stay missed | [#270](https://github.com/brandonifco/rules-factory/issues/270) |
| `clear-to-ambiguous` | an ambiguity is anchored to nothing, where a cross-reference must quote the evidence | [#271](https://github.com/brandonifco/rules-factory/issues/271) |
| `hide-cross-reference`, and the SRD half of `neighbour-evidence` | a pointer made by naming a defined term is not a phrase, and no phrase list will find it | [#208](https://github.com/brandonifco/rules-factory/issues/208), already open |

### A miss no structural check can reach — a measured limit

Each of these is now a line in `check-map.py`'s docstring and in
[`docs/validator.md`](../../docs/validator.md), marked **measured** rather than reasoned. The
distinction was invisible to a reader before this trial, and several of those lines were argued
from first principles.

| mutation | why nothing structural reaches it | measured |
|---|---|---|
| `drop-enabled-by`, `drop-suspended-by`, `invent-depends-on` | whether the corpus imposes an order is a fact about the corpus; the map is internally consistent either way | 0 of 13 |
| `ambiguous-to-clear` | premature collapse: one reading asserted, the other deleted. No check *of the map* reaches it; where a second mapper's adjudication says the corpus does not settle it, `superposition` does | 1 of 5, and that one from the adjudication record rather than the map |
| `same-passage-evidence` | the entry quotes a real sentence of the passage it cites. Only reading the corpus against the entry says it is the wrong sentence | 1 of 5, and that one by bookkeeping |
| `omit-definition` | a definition nobody mapped leaves no trace in a map that never referred to it | 0 of 4 |
| `remove-applicability` | so does an applicability rule, once the edges that named it go with it | 1 of 4 refusals, and that one because the deleted entry was where an adjudicated doubt was recorded |

## What this trial changed

- The validator's miss rate is a number: **74%, 46 of 62**, at `69167d8`, with the table above
  saying which. It is **68%, 42 of 62** now, and every row that moved moved because a check
  grew — which is the thing this trial was built to be able to say.
- Four `enforcement` issues, each with the mutation that exposes it and the re-measurement that
  will close it. One of them, #269, is closed by the two `narrow-extent` cells above.
- Five lines in the validator's statement of its limits are now marked **measured**, with the
  count beside them, and the ones that remain reasoned are visibly reasoned.
- `scripts/validate.sh` re-runs the whole measurement on every pull request and fails when a row
  moves. The table is not a document that can go quietly out of date: a check that grows, a map
  that is corrected, or a mutation that is retargeted all show up as the row they change, and the
  fix is to re-record rather than to bump a date.

## Running it

```bash
python3 tools/mutate-map.py --list                       # the catalogue and the subjects
python3 tools/mutate-map.py --only neighbour-evidence     # one mutation, every map
python3 tools/mutate-map.py --subject hoyle-backgammon    # one map, every mutation
python3 tools/mutate-map.py --json results.json --markdown results.md   # re-record
python3 tools/mutate-map.py --check examples/validator-attack/results.json  # what the gate runs
```

The whole measurement takes about ten seconds, which is why it is a step in the gate rather than a
workflow of its own.

## What moved, and why

| row | was | is | why |
|---|---|---|---|
| `faa-part-107` / `ambiguous-to-clear` | missed | `superposition` | the collapsed entry was adjudicated *the corpus does not settle it* by the blind second mapping, and the collapsed map records one reading |
| `hoyle-backgammon` / `remove-applicability` | missed | `superposition` | the applicability rule the harness drops is `bearing-off-eligible`, which is where that map records an adjudicated unsettled reading; deleting the entry leaves the doubt with nowhere to land |
| `hoyle-backgammon` / `narrow-extent` | missed | `extent-bounds` | #269. The map cites pp. 271–278 of a declared 271–280, so narrowing moves no citation; `die-faces`'s quote runs to p. 280 and is now placed inside the range, not only counted |
| `srd-52-conditions` / `narrow-extent` | missed | `extent`, `extent-bounds` | #269. `extent` places a page citation inside the declared range as it always placed a section designation, and the entries on p. 191 are outside 177–190 |

`srd-52-combat` / `narrow-extent` did not move — it was already refused — but its cell now names
three checks rather than one. At `69167d8` the narrowing was caught only incidentally, by
`extent-end`, because the heading the extent ends before was no longer on its last page; the
narrowing itself was not seen. It is now seen twice, by the citation rule and by the quote rule.

The first two are `superposition` and both are second-order: what is caught is not a property of the
damaged map but a disagreement between the damaged map and a record made by a second reader. The
harness was changed in one way to make them visible — `detectors()` now passes `--comparison`, the
directory holding the adjudication record, because the map under test is written into a temporary
directory where nothing sits beside it. Without that the check reports NOT VERIFIED on the control
and on every mutation, and the table would have recorded a check this harness never ran as a check
that noticed nothing.

**This is a different measurement from [`examples/collapse-trial/`](../collapse-trial/README.md),
and the two do not overlap.** This table asks *what does the whole validator catch across fourteen
kinds of damage*, and collapses one entry per map. The collapse trial asks *what fraction of
premature collapses does the validator catch*, and collapses **every** recorded ambiguity in every
map, 64 of them, one at a time — 12 caught, against 4 before 0034. One row here, 64 there; the
denominators are not the same subject and neither number is the other's.
