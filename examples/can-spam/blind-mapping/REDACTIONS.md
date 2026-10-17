# Redactions

What was removed from the documents a blind second mapping of `usc-15-ch103` is given, and why (docs/method.md, *Before the map is used*). Written by `python3 tools/mapper stage`; the digests are in [staged-inputs.json](staged-inputs.json).

## What was staged

- `0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md` from `../../../docs/decisions/0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md` (8df79f8934cd…) -> `2652e7dd39ad…`, 5 edit(s)
- `corpus-map.md` from `../../../docs/corpus-map.md` (c05aad38d4c2…) -> `1497a86dd037…`, 1 edit(s)
- `mapper.md` from `../../../docs/mapper.md` (3af74e64bdd2…) -> `3caaeedf44da…`, 3 edit(s)
- `method.md` from `../../../docs/method.md` (f152d9ea32a8…) -> `3c5b7570c687…`, 0 edit(s)

## The vocabulary the scan used

Every map of this corpus, the neighbouring slices included: a sibling slice's entry id is this corpus's vocabulary.

- `../corpus-map.json` (141 entries)

141 term(s) an occurrence of which fails a staging (a hyphenated entry id, or the corpus id), 143 that raise a question (a one-word id, an entry name, a word of the corpus id).

## Content edits

- `0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md` L12: names the statute chapter that forced the decision, by its U.S.C. range
- `0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md` L17: names the title the chapter sits in, with its size
- `0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md` L34: repeats the size of that title
- `0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md` L45: example USLM identifier of a section and subdivision of the chapter
- `0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md` L47: example USLM identifier of a section of the chapter, as the extent item
- `corpus-map.md` L158: example USLM identifier of a section and subdivision of the chapter
- `mapper.md` L247: example USLM identifier of a section of the chapter
- `mapper.md` L366: extent-item example identifier of a section of the chapter, in the adapter table
- `mapper.md` L366: citation example identifier of a section and subdivision of the chapter, in the adapter table

## Links made plain text

A markdown link to anything but a staged document became its link text: the mapper has none of those files, and a target is prose too.

- ../../tools/derive-uslm-chapter.py (1)
- ../examples/faa-part-107-temporal/README.md (1)
- ../examples/faa-part-107/README.md (1)
- ../tools/mapper/corpus.py (1)
- ../tools/mapper/protocol.py (1)
- ../tools/mapvalidator/locators.py (1)
- 0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md (1)
- 0063-no-new-map-concept-without-a-corpus-that-forces-it.md (1)
- 0074-a-corpus-is-built-and-verified-by-rules-corpus-from-the-definition-committed-beside-it.md (1)
- decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md (3)
- decisions/0004-adapter-reach-is-a-property-of-the-entry.md (5)
- decisions/0005-a-field-earns-its-place-by-being-checkable.md (9)
- decisions/0007-a-conflict-is-a-question-not-a-pair.md (4)
- decisions/0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md (2)
- decisions/0009-absence-is-a-verdict-with-evidence.md (8)
- decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md (7)
- decisions/0011-a-gate-has-a-direction.md (3)
- decisions/0012-a-fact-the-corpus-implies-is-a-derived-entry.md (4)
- decisions/0013-verification-posture-belongs-to-the-corpus.md (4)
- decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md (2)
- decisions/0015-a-map-is-published-as-a-versioned-package.md (4)
- decisions/0017-a-map-change-carries-a-review-of-its-bytes.md (3)
- decisions/0019-randomness-is-declared-by-the-corpus.md (1)
- decisions/0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md (2)
- decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md (5)
- decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md (6)
- decisions/0025-an-assertion-names-who-asserts-it-and-an-operation-names-what-it-draws.md (8)
- decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md (8)
- decisions/0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md (5)
- decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md (3)
- decisions/0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md (3)
- decisions/0031-an-example-that-bounds-a-term-is-recorded-as-a-bound.md (3)
- decisions/0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md (4)
- decisions/0033-the-validator-is-the-adversary-and-validates-the-uncertainty-too.md (1)
- decisions/0034-a-valid-unresolved-state-is-established-not-asserted.md (4)
- decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md (5)
- decisions/0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md (2)
- decisions/0037-an-ellipsis-skips-whole-paragraphs-and-never-words-inside-one.md (1)
- decisions/0038-a-map-declares-the-passages-its-grammar-cannot-address.md (1)
- decisions/0039-the-manifest-pins-every-corpus-a-map-cites.md (4)
- decisions/0040-a-protocol-is-about-one-corpus-and-a-map-has-one-per-corpus-it-cites.md (2)
- decisions/0041-a-coded-pointer-is-made-by-the-column-it-sits-in.md (1)
- decisions/0042-the-mapper-walks-every-corpus-a-map-cites.md (1)
- decisions/0043-a-row-blank-in-the-column-that-names-the-row-above-is-named-below-it.md (2)
- decisions/0044-one-printed-code-can-name-more-than-one-rule.md (2)
- decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md (2)
- decisions/0046-an-additional-rule-can-continue-a-definition.md (2)
- decisions/0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md (3)
- decisions/0055-coverage-reports-how-much-of-the-extent-is-quoted-and-a-map-declares-the-floor.md (3)
- decisions/0056-a-wrapper-whose-heading-names-a-division-continues-nothing.md (2)
- decisions/0058-a-pointer-is-declared-by-the-passage-that-makes-it-whatever-the-engine-does-with-the-rule.md (2)
- decisions/0059-a-missing-definition-dominates-an-open-question-and-a-reference-may-name-a-class.md (2)
- decisions/0060-one-adjudication-record-one-shape-and-the-vocabulary-is-declared-in-the-file.md (1)
- decisions/0064-a-page-extent-can-start-after-a-heading-and-the-heading-joins-two-maps.md (1)
- decisions/0066-the-cited-page-chooses-among-the-printings-the-heading-path-selects.md (2)
- decisions/0068-a-licensed-corpus-may-be-produced-and-verified-inside-a-private-distribution-boundary.md (2)
- decisions/0070-a-page-marked-map-may-cite-several-corpora-each-entry-checked-against-its-own.md (1)
- decisions/0074-a-corpus-is-built-and-verified-by-rules-corpus-from-the-definition-committed-beside-it.md (2)
- decisions/0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md (1)
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
- https://github.com/brandonifco/rules-factory/issues/18 (3)
- https://github.com/brandonifco/rules-factory/issues/2 (2)
- https://github.com/brandonifco/rules-factory/issues/20 (2)
- https://github.com/brandonifco/rules-factory/issues/207 (1)
- https://github.com/brandonifco/rules-factory/issues/208 (3)
- https://github.com/brandonifco/rules-factory/issues/216 (2)
- https://github.com/brandonifco/rules-factory/issues/22 (1)
- https://github.com/brandonifco/rules-factory/issues/223 (2)
- https://github.com/brandonifco/rules-factory/issues/225 (1)
- https://github.com/brandonifco/rules-factory/issues/239 (2)
- https://github.com/brandonifco/rules-factory/issues/24 (1)
- https://github.com/brandonifco/rules-factory/issues/240 (2)
- https://github.com/brandonifco/rules-factory/issues/243 (2)
- https://github.com/brandonifco/rules-factory/issues/247 (1)
- https://github.com/brandonifco/rules-factory/issues/25 (1)
- https://github.com/brandonifco/rules-factory/issues/250 (3)
- https://github.com/brandonifco/rules-factory/issues/254 (1)
- https://github.com/brandonifco/rules-factory/issues/255 (2)
- https://github.com/brandonifco/rules-factory/issues/261 (1)
- https://github.com/brandonifco/rules-factory/issues/262 (1)
- https://github.com/brandonifco/rules-factory/issues/265 (2)
- https://github.com/brandonifco/rules-factory/issues/267 (3)
- https://github.com/brandonifco/rules-factory/issues/269 (2)
- https://github.com/brandonifco/rules-factory/issues/27 (1)
- https://github.com/brandonifco/rules-factory/issues/270 (1)
- https://github.com/brandonifco/rules-factory/issues/271 (1)
- https://github.com/brandonifco/rules-factory/issues/277 (1)
- https://github.com/brandonifco/rules-factory/issues/28 (2)
- https://github.com/brandonifco/rules-factory/issues/280 (3)
- https://github.com/brandonifco/rules-factory/issues/282 (1)
- https://github.com/brandonifco/rules-factory/issues/285 (2)
- https://github.com/brandonifco/rules-factory/issues/29 (2)
- https://github.com/brandonifco/rules-factory/issues/290 (1)
- https://github.com/brandonifco/rules-factory/issues/291 (2)
- https://github.com/brandonifco/rules-factory/issues/292 (1)
- https://github.com/brandonifco/rules-factory/issues/293 (2)
- https://github.com/brandonifco/rules-factory/issues/299 (1)
- https://github.com/brandonifco/rules-factory/issues/305 (1)
- https://github.com/brandonifco/rules-factory/issues/307 (1)
- https://github.com/brandonifco/rules-factory/issues/31 (1)
- https://github.com/brandonifco/rules-factory/issues/310 (1)
- https://github.com/brandonifco/rules-factory/issues/311 (1)
- https://github.com/brandonifco/rules-factory/issues/314 (2)
- https://github.com/brandonifco/rules-factory/issues/32 (1)
- https://github.com/brandonifco/rules-factory/issues/321 (1)
- https://github.com/brandonifco/rules-factory/issues/33 (1)
- https://github.com/brandonifco/rules-factory/issues/392 (1)
- https://github.com/brandonifco/rules-factory/issues/393 (2)
- https://github.com/brandonifco/rules-factory/issues/396 (2)
- https://github.com/brandonifco/rules-factory/issues/399 (2)
- https://github.com/brandonifco/rules-factory/issues/434 (1)
- https://github.com/brandonifco/rules-factory/issues/436 (1)
- https://github.com/brandonifco/rules-factory/issues/437 (1)
- https://github.com/brandonifco/rules-factory/issues/47 (2)
- https://github.com/brandonifco/rules-factory/issues/5 (1)
- https://github.com/brandonifco/rules-factory/issues/51 (2)
- https://github.com/brandonifco/rules-factory/issues/58 (2)
- https://github.com/brandonifco/rules-factory/issues/59 (2)
- https://github.com/brandonifco/rules-factory/issues/6 (1)
- https://github.com/brandonifco/rules-factory/issues/60 (2)
- https://github.com/brandonifco/rules-factory/issues/61 (1)
- https://github.com/brandonifco/rules-factory/issues/62 (3)
- https://github.com/brandonifco/rules-factory/issues/653 (2)
- https://github.com/brandonifco/rules-factory/issues/654 (1)
- https://github.com/brandonifco/rules-factory/issues/660 (1)
- https://github.com/brandonifco/rules-factory/issues/7 (1)
- https://github.com/brandonifco/rules-factory/issues/76 (1)
- https://github.com/brandonifco/rules-factory/issues/93 (1)
- validator.md (4)

## Named and left in

Each of these is a word the document uses for its own reasons. The staging says so, by document and term, and counts the occurrences, so one more is a change:

- `0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md` — `usc` ×4: The path prefix `/us/usc/` of a USLM identifier and the `usc<NN>.xml` member name: the grammar's own spelling, here in the identifier of a court rule (`/us/usc/t28a/courtRules/Civil/rule6/a/1`) that the edits substituted. It is a word of the corpus id only because the corpus is cut from the same Code.
- `corpus-map.md` — `character` ×1: "a player character" in the rendered-reading example drawn from the SRD corpus: the English noun for a role in a game, not a term of this corpus.
- `corpus-map.md` — `person` ×14: The ordinary English noun, and the regulated party of 14 CFR Part 107 (`No person may operate ...`) in the assertion examples drawn from that corpus: a person who could report a fact, a person's judgement, a reasonable person. Not a term of any map.
- `corpus-map.md` — `usc` ×2: The path prefix `/us/usc/` of a USLM identifier and the `usc<NN>.xml` member name: the grammar's own spelling, here in the identifier of a court rule (`/us/usc/t28a/courtRules/Civil/rule6/a/1`) that the edits substituted. It is a word of the corpus id only because the corpus is cut from the same Code.
- `mapper.md` — `usc` ×3: The path prefix `/us/usc/` of a USLM identifier and the `usc<NN>.xml` member name: the grammar's own spelling, here in the identifier of a court rule (`/us/usc/t28a/courtRules/Civil/rule6/a/1`) that the edits substituted. It is a word of the corpus id only because the corpus is cut from the same Code.
- `method.md` — `person` ×7: The ordinary English noun, and the regulated party of 14 CFR Part 107 (`No person may operate ...`) in the assertion examples drawn from that corpus: a person who could report a fact, a person's judgement, a reasonable person. Not a term of any map.

## What this did not check

- Paraphrase: an example that describes a rule of the corpus under mapping without naming an entry, an id or the corpus is invisible to the scan. The declared edits are what covers it.
- Examples from another corpus that share this corpus's shapes -- dice, turns, a phase gate -- are not leaks of this corpus and are not detected. Whether to replace them anyway is a judgement the spec makes.
- Anything the second mapper is given that is not one of these documents: a prompt, a brief or a review thread that states the first mapper's reading is outside what this stages.
