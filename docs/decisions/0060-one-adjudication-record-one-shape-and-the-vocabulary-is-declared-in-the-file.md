# 0060 — The blind second mapping's adjudication record is one shape, and each record declares the vocabulary its verdicts are written in

## Status

Accepted — 2026-09-21. Closes
[#273](https://github.com/brandonifco/rules-factory/issues/273), found while building the
`superposition` check for [#258](https://github.com/brandonifco/rules-factory/issues/258).
**Carries out [0034](0034-a-valid-unresolved-state-is-established-not-asserted.md)** and closes
the limit its *Consequences* recorded: *"the record has two committed shapes and two verdict
vocabularies, which is a finding rather than a design."* **Extends
[0014](0014-a-map-is-checked-by-a-blind-second-mapping.md)**, whose procedure is unchanged.
Adds no entry field and no manifest key. Changes no check's verdict on any committed map.

## Context

0014 makes a map be read a second time by a mapper who has not seen the first, compares the two
field by field, and answers every disagreement from the corpus. 0034 made the validator read that
answer: where a disagreement about certainty was adjudicated *the corpus does not settle it*, the
map must record the doubt somewhere, or it is a premature collapse with a paper trail.

Four mappings have been adjudicated. They produced two artefacts:

| map | where the verdicts were | vocabulary | where the vocabulary was defined |
|---|---|---|---|
| `faa-part-107`, `hoyle-backgammon`, `srd-52-combat` | `blind-mapping/results.json`, `flags[].resolution.verdict`, copied there by `compare.py` from a flat `resolutions.json` keyed by flag | `R` / `B` / `U` / `N` | each trial's `blind-mapping/README.md`, in prose |
| `tax-121-principal-residence` | `blind-mapping/resolutions.json`, `disagreements[]` and `families[]`, each with a prose `ruling` | `A` / `B` / `neither` / `not-a-corpus-disagreement` / `open` | the file, under `verdicts` |

So `tools/mapvalidator/epistemic.py` carried two parsers for one artefact. The first read a
verdict out of a field and compared it against a four-term vocabulary **hardcoded in the
checker**, which is where `U` means *the corpus does not settle it* — a README says so, and no
program could read the README. The second read the verdict as the leading clause of a prose
sentence, longest term first so that `not-a-corpus-disagreement` was not read as something
shorter, and a verdict stated anywhere later in the prose was not read at all. A record of any
third shape reported NOT VERIFIED.

Two parsers is the visible cost. The invisible one is that the vocabulary of three of the four
records lived nowhere the code could check it against the record, so the checker and the record
could disagree about what a letter meant and nothing would say so.

## Decision

**There is one adjudication record, `blind-mapping/resolutions.json`, it is one shape, and it
declares the vocabulary its own verdicts are written in.**

### 1. The record is `resolutions.json`, and `results.json` is the comparison

`review.json` already names the two separately (0017): `comparison` is the comparator's output,
`resolutions` is the record. That division is the right one and it is now honoured. `results.json`
holds the alignment, the flags and the parameters — what the comparator found. `resolutions.json`
holds what a person decided about it. The validator reads the second and not the first.

### 2. The shape

```json
{
  "about": "...",
  "verdicts": { "<term>": "<what it meant here>" },
  "unsettledVerdict": "<one of those terms>",
  "adjudications": [
    { "id": "...", "field": "clarity", "entries": ["..."],
      "verdict": "<one of those terms>", "reason": "..." }
  ]
}
```

- **`verdicts`** is the legend, as trial 9's already was: every term the record uses, and what it
  meant to the people who used it.
- **`unsettledVerdict`** names the one term that means *the corpus does not settle it*. It is the
  term `superposition` turns on, and it is the piece that was hardcoded.
- **`adjudications`** is one list. Each row carries its verdict in a field, the `field` the
  disagreement was about, and `entries`, the ids it is about in either map.
- A record may carry whatever else its trial needed. Trial 9's rows keep `group`
  (`disagreement` or `family`), `citation`, `count`, `aSaid`, `bSaid`, `corpusEvidence`,
  `whyTheyDiffered` and `methodConsequence`; the other three keep `locator` and `quote`. Nothing
  reads those and nothing refuses them.

`ruling` becomes `reason`, the name the other three records already used. It also stops colliding
with an owner's ruling under [0027](0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md),
which is a different thing held in a different place.

### 3. The vocabulary is per record, and declared

The terms themselves are **not** unified. `R`/`B`/`U`/`N` and `A`/`B`/`neither`/
`not-a-corpus-disagreement`/`open` both stay, each in the record that used them, with the meaning
that record's trial gave them — for the three trials that had no legend, copied word for word from
the README that did define it. A verdict is a fact about an adjudication somebody performed; a
letter rewritten afterwards is a record of something that did not happen.

What is unified is that the meaning is **in the file**. The checker knows no terms at all: it
reads the legend, reads `unsettledVerdict`, and refuses a verdict the legend does not define
exactly as it refuses a missing one.

### 4. `compare.py` maintains the shape

A comparator cannot write the verdicts — it does not make them, a person does, and the three
trials' `compare.py` already exits 1 when a flag has no row. What it can write is everything
about a row that is the comparison's: on each run it rewrites each row's `id`, `field` and
`entries` from the flags it raised, so the record cannot drift from the comparison it answers,
and leaves the verdict and the prose exactly as the adjudicator wrote them, in the order that row
already had them in. It refuses to write anything at all when the record does not declare a
legend, an `unsettledVerdict` the legend defines, and a verdict the legend defines on every row.
A row matching no flag is kept where it is and reported, never dropped.

### 5. One parser

`epistemic.py` reads one file and one shape. The per-flag reader, the leading-clause reader and
both hardcoded vocabularies are deleted, because every committed record was migrated and none is
left to read. A record that does not declare an `unsettledVerdict` is NOT VERIFIED rather than
passing: a legend that does not say which of its terms means *the corpus does not settle it* is
one this check would pass in silence, and silence is what it exists to refuse.

## What the migration cost

**No `review.json` was touched, and no re-review is owed.** 0017 binds a review to the bytes of
the **map**. `tools/check-map-review.py` hashes `corpus-map.json` and nothing else: it checks that
`comparison` and `resolutions` *exist*, and that the comparison's `reference.commit` equals
`compared.commit`. No map's bytes change here, and neither does any comparison's
`reference.commit`.

**No `results.json` byte changed.** All three comparators were re-run after the change and
reproduce their committed output exactly, because what `compare.py` copies into a flag is still
the row's verdict and prose in the row's own key order.

**No verdict moved.** The seven `superposition` lines — three `ok` with their counts, four NOT
VERIFIED — are identical before and after, including the census of how many ambiguities carry a
second reading.

What changed is four `resolutions.json`, three `compare.py`, `epistemic.py`, and
`tools/evidence-lock.json`, which pins the digest of every file under `examples/` (0051).

## Alternatives considered

**Extend `results.json` instead.** Rejected. Trial 9's `results.json` is a differently scoped
comparator's output that carries no verdicts at all, so making it the record means writing
verdicts into a frozen artefact that never had them. It also puts the human adjudication inside a
generated file, where re-running the comparator owns it.

**A new file name.** Rejected. `review.json` already names `resolutions` as the record and
`comparison` as the output, in every blind-second-mapping review committed; a third name orphans
that field and buys nothing the existing one does not.

**One vocabulary across all four records.** Rejected, and this is the substantive refusal.
`R`→`A` and `U`→`open` are mechanical, but `neither` — *both misread the corpus; Map C carries a
third answer* — has no counterpart in `R`/`B`/`U`/`N`, so a merged vocabulary is a fifth term
three adjudications never had available. And a verdict is evidence: rewriting the letters in
three committed records makes them say something nobody wrote. Declaring the vocabulary in the
file gets what a program needs without that.

**Leave the legacy parser in place for records not yet migrated.** Rejected, because there are
none. Every committed record is of the one shape, and a parser with no input is a claim the tests
cannot hold to anything.

**Split `graph-shape` into one row per verdict.** Rejected. See *Limits*.

## Consequences

- **The checker knows no verdict vocabulary.** Two hardcoded dictionaries are gone from
  `epistemic.py`. A new corpus may adjudicate in whatever terms it likes and the check works,
  provided the record says which term means unsettled.
- **A record may now be wrong in a way the checker catches.** A verdict the record's own legend
  does not define fails, where before a term outside the hardcoded four failed only if it was one
  of the first shape's and a term outside trial 9's legend was simply unreadable prose.
- **`compare.py` is the shape's maintainer.** The structural fields cannot drift from the
  comparison, because they are rewritten from it on every run, and the run refuses when the
  record's envelope is not the one shape.
- **`results.json` stops being an adjudication record.** It is the comparison. A future reader
  looking for verdicts has one place to look, and `review.json` already names it.
- **One more file is rewritten by a `compare.py` run.** Re-running a trial's comparator now
  touches `resolutions.json` as well as `results.json`. Both are idempotent, and both are pinned
  in the evidence lock, so a run that changes either shows up in the gate.

## Limits

- **`graph-shape` cannot carry one verdict, and the legend says so rather than the shape hiding
  it.** Trial 9's `graph-shape` family covers nine flags and its ruling opens *"Six
  not-a-corpus-disagreement; the seventh B"*. Splitting it into two rows would need counts the
  prose does not give — it says `count: 9`, six, and a seventh — so the split would be invented.
  The legend declares `mixed` for exactly this shape, and the reason says which went which way.
  Nothing turns on it: `superposition` reads `clarity` and `ambiguity` rows only, and
  `graph-shape`'s field is `dependsOn, suspendedBy`. A `mixed` verdict on a row about certainty
  would pass this check while answering nothing, and that is a hole. It is not reachable from any
  committed record, and the right closing of it is an adjudication that answers a family one way
  or splits it, not a checker rule written for one historical row.
- **The legend is the record's own word.** Nothing compares a term's declared meaning against how
  the rows use it, and nothing could. `unsettledVerdict` pointing at the wrong term silently
  redirects the whole check, exactly as the hardcoded value could have been wrong — the
  difference is that it is now a line in the diff of the record it governs.
- **0034's limits are untouched.** `superposition` still reads verdicts and never reasoning; it
  still sees `clarity` and `ambiguity` disagreements only; and it is still worth nothing on a map
  nobody mapped twice. Three of the seven committed maps have no adjudication record, and this
  record changes none of that.
- **`entries` is the ids in either map.** For the three migrated records it is the reference
  entry and the blind entry the flag paired; for trial 9 it is Map A's id and Map B's. A blind
  map's id is a different map's namespace, and a doubt is counted as landing when such an id
  matches an ambiguous entry in this map — which happens when the map adopted that blind entry,
  as `rubber-scoring` was, and would also happen on a coincidence of naming. No committed map's
  verdict depends on it: every `superposition` line is unchanged.
- **Nothing holds a record to the shape except the code that reads it.** `compare.py` refuses a
  malformed envelope for the three trials that have one; trial 9's record is hand-written and has
  no comparator, so for it the shape rests on `epistemic.py` reporting NOT VERIFIED and on the
  test that walks every committed record.
