# srd-52-conditions: the blind inputs, staged

**There is no second mapping here yet.** What is here is what a second mapper will be given, and
the proof that it was redacted — the half of the exercise
[#223](https://github.com/brandonifco/rules-factory/issues/223) found nothing enforcing.

## What happened

Staging a second mapping of this slice by hand copied `docs/method.md` and `docs/corpus-map.md`
verbatim. Both leaked. `docs/corpus-map.md` named `incapacitated-condition` — an entry id of the
slice under mapping — and stated part of what its glossary text says; `docs/method.md` carried
eight references to the neighbouring SRD slice's entries. The mapper read the leak and disclosed
it unprompted. The staging did not, and could not: the comparison tooling compares two maps and
never sees what the second mapper was given. That run is **partially contaminated and is not
recorded as a blind second mapping**; the map's review stays the `legacy` exemption in
[`../review.json`](../review.json) until the exercise is redone from these inputs.

## What is here

| file | what it is |
|---|---|
| [`staging.json`](staging.json) | the staging spec: every substitution, each saying why, each required to match its document exactly once |
| [`method.md`](method.md), [`corpus-map.md`](corpus-map.md) | the two documents as redacted |
| [`REDACTIONS.md`](REDACTIONS.md) | what was removed, what was named and left in, and what the tool did not look for |
| [`staged-inputs.json`](staged-inputs.json) | the digests, the maps the scan's vocabulary came from, and the vocabulary itself |

```bash
python3 tools/mapper stage examples/srd-52-conditions/blind-mapping/staging.json           # re-stage
python3 tools/mapper stage --verify examples/srd-52-conditions/blind-mapping/staged-inputs.json
```

`scripts/validate.sh` runs the second on every record: it re-hashes every file the record names
and re-runs the leak scan over the staged documents, so neither a swapped input nor a record
claiming a redaction it did not make passes.

## What the re-staging removed

Fifty declared edits, and both leaks #223 names are gone. Beyond them the documents had drifted a
long way toward this corpus since trial 7 staged its own run: the corpus id and its name, the
page-extent and `endsBefore` examples (which are this corpus's own slice), the `quotedText`
derivation string and PDF file name, the `draws`, `assertedBy` and `renderedReading` JSON
examples, the six questions building the neighbouring slice could not answer, the three worked
declines, the batch closure example and the four-page engine's counts. A heading-path example
cited `Rules Glossary / Round Down / p. 187` — a citation *into the slice under mapping*, naming
one of its entries and the page it is on.

Fifteen occurrences were **named and left in**: `reach`, `action`, `invisible` and `speed` are
one-word entry ids or entry names of this corpus and are also ordinary English, and each is
recorded with the reason it is not a leak.

## What this does not prove

The scan sees names, not meaning. An example that paraphrases a rule of this corpus without
naming an entry, an id or the corpus is invisible to it, and the declared edits are what covers
that — by judgement, not by proof. The backgammon examples in both documents are left in: they
are another corpus, and unlike trial 7's combat slice, a game of dice and turns is not this
glossary's shape. Anything the second mapper is given that is not these two documents and the
pinned extract — a prompt, a brief, a review thread — is outside what this stages.
