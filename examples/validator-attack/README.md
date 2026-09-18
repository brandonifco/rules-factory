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
> refused sixteen of them and passed forty-six — a miss rate of 74%.**
>
> **That is not a verdict on the validator. It is the denominator it did not have.** Several of
> these misses are provably outside a structural checker's reach, which is *why* the blind second
> mapping exists. What the trial changes is that each of them is now measured rather than argued,
> and each is dispositioned: an issue, or a line in the validator's own statement of its limits
> that says it was measured.

Measured at commit `69167d8` (`examples/validator-attack/results.json` carries the commit, every
run, and what each failing check actually said).

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
| [`hoyle-backgammon`](../hoyle-backgammon/) | rulebook, 1909 | page markers, Gutenberg text | 13 | 4 | 9 |
| [`faa-part-107`](../faa-part-107/) | regulation | section designation, eCFR XML | 13 | 5 | 8 |
| [`tax-121-principal-residence`](../tax-121-principal-residence/) | regulation | section designation, eCFR XML | 12 | 3 | 9 |
| [`srd-52-combat`](../srd-52-combat/) | rulebook | page markers, PDF-extracted text | 14 | 2 | 12 |
| [`srd-52-conditions`](../srd-52-conditions/) | rulebook, a glossary | page markers, PDF-extracted text | 10 | 2 | 8 |

## The table

`n/a` is a corpus with nothing for that mutation to damage — recorded, never scored. A cell naming
checks is a refusal, and names the checks that turned.

| mutation | hoyle-backgammon | faa-part-107 | tax-121-principal-residence | srd-52-combat | srd-52-conditions |
|---|---|---|---|---|---|
| `drop-entry` | **missed** | coverage | **missed** | **missed** | **missed** |
| `drop-enabled-by` | **missed** | n/a | **missed** | **missed** | n/a |
| `drop-suspended-by` | **missed** | **missed** | **missed** | **missed** | n/a |
| `clear-to-ambiguous` | **missed** | **missed** | **missed** | **missed** | **missed** |
| `ambiguous-to-clear` | **missed** | **missed** | **missed** | **missed** | **missed** |
| `assertion-to-operation` | signalled only: asserted-by | **missed** | n/a | **missed** | n/a |
| `invent-depends-on` | **missed** | **missed** | **missed** | **missed** | **missed** |
| `neighbour-evidence` | cross-references, locators | locators | cross-references, locators | **missed** | locators |
| `same-passage-evidence` | cross-references | **missed** | **missed** | **missed** | **missed** |
| `move-locator` | locators | locators | locators | locators | locators |
| `omit-definition` | n/a | **missed** | **missed** | **missed** | **missed** |
| `remove-applicability` | **missed** | signalled only: gates | **missed** | **missed** | n/a |
| `hide-cross-reference` | cross-references | cross-references | cross-references | **missed** | **missed** |
| `narrow-extent` | **missed** | extent | n/a | extent-end | **missed** |

Sixteen refusals, made up of eighteen turned checks, and five check names account for every one:
`locators` (9), `cross-references` (6), and one each from `coverage`, `extent` and `extent-end`.
Counting the two signalled-only turns, **four of the twenty-two checks in `check-map.py` ever
turned; eighteen never did.** They are not idle — they hold shapes a hand-written map breaks and a
mutation of an already correct map does not — but a reader should not take twenty-two checks as
twenty-two chances of being caught.

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

**Neither direction of the clarity flip is seen.** `clear-to-ambiguous` and `ambiguous-to-clear`
are 0 of 10. They are not the same kind of miss, and the trial's sharpest single finding is that
they are asymmetric: premature collapse cannot be caught structurally, but an *invented* ambiguity
could be, because `ambiguity.question` is free prose where `crossReferences.cites` on the same
entry must be verbatim of the evidence. That is
[#271](https://github.com/brandonifco/rules-factory/issues/271).

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
| `narrow-extent` (page extents) | `extent` places a section citation inside the declared extent and a page citation nowhere | [#269](https://github.com/brandonifco/rules-factory/issues/269) |
| `drop-entry` | `coverage` counts units touched, so deleting a rule is invisible in 4 of 5 maps | [#270](https://github.com/brandonifco/rules-factory/issues/270) |
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
| `ambiguous-to-clear` | premature collapse: one reading asserted, the other deleted. Every check passes and the engine is confident | 0 of 5 |
| `same-passage-evidence` | the entry quotes a real sentence of the passage it cites. Only reading the corpus against the entry says it is the wrong sentence | 1 of 5, and that one by bookkeeping |
| `omit-definition` | a definition nobody mapped leaves no trace in a map that never referred to it | 0 of 4 |
| `remove-applicability` | so does an applicability rule, once the edges that named it go with it | 0 of 4 refusals |

## What this trial changed

- The validator's miss rate is a number: **74%, 46 of 62**, at `69167d8`, with the table above
  saying which 46.
- Four `enforcement` issues, each with the mutation that exposes it and the re-measurement that
  will close it.
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
