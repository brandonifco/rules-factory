# Run 2: blind mapping with backgammon removed from the docs

Run 1 (`../README.md`) was contaminated: the mapper's copies of `docs/corpus-map.md` and
`docs/method.md` named about 17 backgammon entries and several of their verdicts. This run
repeats it with those references removed.

## What changed from run 1

- **Inputs.** `inputs/corpus-map.md` and `inputs/method.md` are the docs at `170daa6` with every
  backgammon reference replaced by an SR6, Part 107 or invented example. `REDACTIONS.md` lists
  the 50 edits. A final grep found no entry ids and no backgammon vocabulary.
- **Mapper.** A fresh agent that read only those two files and the chapter text.
- **Everything else is unchanged.** Same reference (`ecc53b8`), same `../compare.py` and the same
  injections as run 1. The comparator was run with this `blind-map.json` in place of run 1's.

## Results

| | run 1 | run 2 |
|---|---:|---:|
| blind entries | 41 | 34 |
| comprehension injections caught | 11 of 15 | 10 of 15 |
| flags on the clean map | 71 | 78 |

Caught in run 2: evidence-truncated, depends-spurious, gate-dropped, gate-spurious,
kind-operation-to-value, kind-assertion-to-value, clarity-ambiguous-to-clear, scope-in-to-out,
entry-fabricated-real-quote, absence-stated-in-other-words.

Missed in run 2: evidence-adjacent-sentence, depends-dropped, clarity-clear-to-ambiguous,
beyond-adapter-false, name-contradicts-corpus.

The sensitivity sweep in `results.json` moves the count by at most one (9 at `PAGE_SLACK=0`).

## Limits

- **The redaction was incomplete.** The mapper reported that some replacement examples closely
  paraphrase the chapter: a stake "as may have been agreed", a whole-or-partial play split, an
  uncovered scoring case. So this run is less contaminated than run 1, not clean.
- **The `by_leak` split in `results.json` does not apply to this run.** It is computed from run
  1's list of leaked entries.
- **The 78 flags have not been adjudicated.** Run 1's hand verdicts do not transfer.
- **One corpus, two mappers, 15 injections.** The two runs agree (11 and 10), which says the
  catch rate is not a fluke of one mapper. It does not give a rate for other corpora.

## Reading it

Across two runs, a blind second mapping caught 10–11 of the 15 comprehension errors that every
mechanical check missed. It costs about 70–80 flags per map to review, and roughly half of run 1's
were noise from splits and merges. The review cost, not the catch rate, is what to work on
next.
