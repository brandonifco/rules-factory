# Redactions

What was removed from the documents a blind second mapping of `srd-5.2.1` is given, and why (docs/method.md, *Before the map is used*). Written by `python3 tools/mapper stage`; the digests are in [staged-inputs.json](staged-inputs.json).

## What was staged

- `corpus-map.md` from `../../../docs/corpus-map.md` (e269c3bcbfcf…) -> `dbf56226812d…`, 23 edit(s)
- `method.md` from `../../../docs/method.md` (a8e5d777d772…) -> `8cb5aaac4614…`, 27 edit(s)

## The vocabulary the scan used

Every map of this corpus, the neighbouring slices included: a sibling slice's entry id is this corpus's vocabulary.

- `../../srd-52-combat/corpus-map.json` (95 entries)
- `../corpus-map.json` (100 entries)

162 term(s) an occurrence of which fails a staging (a hyphenated entry id, or the corpus id), 224 that raise a question (a one-word id, an entry name, a word of the corpus id).

## Content edits

- `method.md` L33: corpus id example names this corpus
- `method.md` L54: boundary-policy example names a CC-BY SRD
- `method.md` L85: extraction example names the corpus and the table it garbled
- `method.md` L229: "the GM decides" example: five stated facts of this corpus, four of them entry ids
- `method.md` L423: executed-map defects: three entries of this corpus, with their draws and dependencies
- `method.md` L424: the same three entries, named again in what the blind second mapping missed
- `method.md` L548: affectsDraws instance names this corpus's group Initiative roll
- `method.md` L551: the six questions building this corpus's slice could not answer, quoted from it
- `method.md` L554: the four unresolved ambiguities, by entry id, with the corpus's words
- `method.md` L559: the conflict, by both entry ids and both pages of this corpus
- `method.md` L562: the clear-entry example: the slice's sentence, the Rules Glossary, two entry ids
- `method.md` L595: the engine of this corpus named as the carrier of an owner's decision
- `method.md` L599: the conflict's two entry ids again, in the per-entry ruling rule
- `method.md` L603: the open-term ruling names its entry id and this corpus's referee
- `method.md` L651: the batches of this corpus's build, with the nine entry ids they had to build across
- `method.md` L656: correspondence row 5's example uses this corpus's Speed and size order
- `method.md` L663: the third engine is named as this corpus's chapter and pages
- `method.md` L668: the scope: out count names the Rules Glossary, this corpus's chapters and two absences
- `method.md` L723: the parallel-agents finding names this corpus's slice
- `method.md` L838: the three worked declines are named as this corpus's engine
- `method.md` L840: decline example 1: the Cover table entry, its three answers and the corpus's words
- `method.md` L845: decline example 2: two entry ids and the corpus's Advantage and Disadvantage
- `method.md` L848: decline example 3: two entry ids, the corpus's saving throw, and what it determines
- `corpus-map.md` L319: assertedBy history names this corpus's engine and an entry id
- `corpus-map.md` L355: dice example quotes this corpus's Initiative evidence and its d20 sentence
- `corpus-map.md` L358: draw-ownership examples name four entry ids, two of them this corpus's
- `corpus-map.md` L361: affectsDraws instance names this corpus's group Initiative entry
- `corpus-map.md` L415: heading-path example names the glossary entry whose span ran on
- `corpus-map.md` L709: extraction defects are each illustrated by an entry id of this corpus
- `corpus-map.md` L759: definedElsewhere example is this corpus's Rules Glossary and its surprise rule
- `corpus-map.md` L763: the modifying-passage instance is two entry ids of this corpus and what one says
- `corpus-map.md` L897: the silent-zero instance names this corpus's map
- `corpus-map.md` L901: the defined-term JSON example is a term and an entry id of this corpus
- `corpus-map.md` L58: the page-extent example is this corpus's slice, pages and following heading
- `corpus-map.md` L64: endsBefore's worked value is the heading this corpus's slice stops at
- `corpus-map.md` L66: the extent-end example names this corpus's chapter and its last page
- `corpus-map.md` L409: the heading-path example is a citation into the slice under mapping, entry name and page
- `corpus-map.md` L1145: the boundary-policy history names this corpus's licence
- `corpus-map.md` L1221: the pointerPhrases example counts this corpus's pages and names it
- `corpus-map.md` L1345: the #116 summary names this corpus's pointers
- `corpus-map.md` L1193: the quotedText example is this corpus's own derivation string and PDF file name
- `method.md` L582: 0027's four awkwardnesses name the engine built from this corpus
- `method.md` L199: the value example is a list of conditions and a creature's statistics
- `method.md` L227: the caller-states heading is this corpus's word for its referee
- `method.md` L233: the mapper-guessing example prices a move in squares, cites a page and quotes the corpus
- `corpus-map.md` L322: the assertedBy JSON example is this corpus's deciders
- `corpus-map.md` L349: the draws JSON examples quote this corpus's dice and two of its rules
- `corpus-map.md` L357: the draw-ownership rule counts this corpus's die
- `corpus-map.md` L398: the repetition example is the slice under mapping: a glossary giving five rules one effect
- `corpus-map.md` L700: the renderedReading example is a sentence of this corpus, verbatim

## Links made plain text

A markdown link to anything but a staged document became its link text: the mapper has none of those files, and a target is prose too.

- ../examples/faa-part-107-temporal/README.md (1)
- ../examples/faa-part-107/README.md (1)
- decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md (3)
- decisions/0004-adapter-reach-is-a-property-of-the-entry.md (4)
- decisions/0005-a-field-earns-its-place-by-being-checkable.md (9)
- decisions/0007-a-conflict-is-a-question-not-a-pair.md (4)
- decisions/0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md (2)
- decisions/0009-absence-is-a-verdict-with-evidence.md (8)
- decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md (7)
- decisions/0011-a-gate-has-a-direction.md (3)
- decisions/0012-a-fact-the-corpus-implies-is-a-derived-entry.md (4)
- decisions/0013-verification-posture-belongs-to-the-corpus.md (4)
- decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md (1)
- decisions/0015-a-map-is-published-as-a-versioned-package.md (2)
- decisions/0017-a-map-change-carries-a-review-of-its-bytes.md (1)
- decisions/0019-randomness-is-declared-by-the-corpus.md (1)
- decisions/0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md (2)
- decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md (5)
- decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md (5)
- decisions/0025-an-assertion-names-who-asserts-it-and-an-operation-names-what-it-draws.md (8)
- decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md (5)
- decisions/0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md (5)
- decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md (3)
- decisions/0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md (1)
- decisions/0031-an-example-that-bounds-a-term-is-recorded-as-a-bound.md (3)
- https://github.com/brandonifco/rules-factory/issues/11 (4)
- https://github.com/brandonifco/rules-factory/issues/113 (2)
- https://github.com/brandonifco/rules-factory/issues/114 (2)
- https://github.com/brandonifco/rules-factory/issues/115 (2)
- https://github.com/brandonifco/rules-factory/issues/116 (2)
- https://github.com/brandonifco/rules-factory/issues/117 (2)
- https://github.com/brandonifco/rules-factory/issues/118 (2)
- https://github.com/brandonifco/rules-factory/issues/13 (1)
- https://github.com/brandonifco/rules-factory/issues/15 (1)
- https://github.com/brandonifco/rules-factory/issues/158 (1)
- https://github.com/brandonifco/rules-factory/issues/16 (2)
- https://github.com/brandonifco/rules-factory/issues/18 (2)
- https://github.com/brandonifco/rules-factory/issues/2 (2)
- https://github.com/brandonifco/rules-factory/issues/20 (2)
- https://github.com/brandonifco/rules-factory/issues/207 (1)
- https://github.com/brandonifco/rules-factory/issues/208 (1)
- https://github.com/brandonifco/rules-factory/issues/216 (2)
- https://github.com/brandonifco/rules-factory/issues/22 (1)
- https://github.com/brandonifco/rules-factory/issues/223 (1)
- https://github.com/brandonifco/rules-factory/issues/239 (2)
- https://github.com/brandonifco/rules-factory/issues/24 (1)
- https://github.com/brandonifco/rules-factory/issues/240 (1)
- https://github.com/brandonifco/rules-factory/issues/243 (2)
- https://github.com/brandonifco/rules-factory/issues/247 (1)
- https://github.com/brandonifco/rules-factory/issues/25 (1)
- https://github.com/brandonifco/rules-factory/issues/27 (1)
- https://github.com/brandonifco/rules-factory/issues/28 (2)
- https://github.com/brandonifco/rules-factory/issues/29 (2)
- https://github.com/brandonifco/rules-factory/issues/31 (1)
- https://github.com/brandonifco/rules-factory/issues/32 (1)
- https://github.com/brandonifco/rules-factory/issues/33 (1)
- https://github.com/brandonifco/rules-factory/issues/47 (2)
- https://github.com/brandonifco/rules-factory/issues/5 (1)
- https://github.com/brandonifco/rules-factory/issues/51 (2)
- https://github.com/brandonifco/rules-factory/issues/58 (2)
- https://github.com/brandonifco/rules-factory/issues/59 (2)
- https://github.com/brandonifco/rules-factory/issues/6 (1)
- https://github.com/brandonifco/rules-factory/issues/60 (2)
- https://github.com/brandonifco/rules-factory/issues/61 (1)
- https://github.com/brandonifco/rules-factory/issues/62 (3)
- https://github.com/brandonifco/rules-factory/issues/7 (1)
- https://github.com/brandonifco/rules-factory/issues/76 (1)
- https://github.com/brandonifco/rules-factory/issues/93 (1)
- mapper.md (1)

## Named and left in

Each of these is a word the document uses for its own reasons. The staging says so, by document and term, and counts the occurrences, so one more is a change:

- `corpus-map.md` — `action` ×1: "that a pilot judged an action safe", in the assertion example, which is drawn from the CFR corpus. The slice has an entry id `action`; this is the English noun.
- `corpus-map.md` — `reach` ×4: The ordinary verb, four times: a quote that does not reach a page, a rule somewhere we cannot reach, what a check can reach, an entry beyond the adapter's reach.
- `corpus-map.md` — `speed` ×3: The same hypothetical pair, three times on one line.
- `method.md` — `invisible` ×1: "invisible to a plain-text adapter", of an illustration in another corpus. The slice has an entry id `invisible`; this is the English adjective.
- `method.md` — `reach` ×4: The ordinary verb and the noun in "adapter reach", four times: what an adapter cannot reach, an entry beyond its reach, and an operation that can reach an out-of-scope entry. The slice under mapping has an entry id `reach`; none of these is it.
- `method.md` — `speed` ×2: `speed-limit` and `speed-within-limit`, the hypothetical pair the delegated-standard example uses. The corpus under mapping has an entry named `Speed`; these are not it.

## What this did not check

- Paraphrase: an example that describes a rule of the corpus under mapping without naming an entry, an id or the corpus is invisible to the scan. The declared edits are what covers it.
- Examples from another corpus that share this corpus's shapes -- dice, turns, a phase gate -- are not leaks of this corpus and are not detected. Whether to replace them anyway is a judgement the spec makes.
- Anything the second mapper is given that is not one of these documents: a prompt, a brief or a review thread that states the first mapper's reading is outside what this stages.
