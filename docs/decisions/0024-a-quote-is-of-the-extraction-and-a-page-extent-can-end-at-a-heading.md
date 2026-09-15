# 0024 — A quote is verbatim of the extraction, a garbled one declares its defect, and a page extent can end before a heading

## Status

Accepted — 2026-09-15. Records the decisions on
[#113](https://github.com/brandonifco/rules-factory/issues/113) and
[#114](https://github.com/brandonifco/rules-factory/issues/114), findings 1 and 2 of trial 7
([`examples/srd-52-combat/README.md`](../../examples/srd-52-combat/README.md)), the first map of a
PDF. **Extends [0004](0004-adapter-reach-is-a-property-of-the-entry.md)**, which could say only
that an adapter cannot read a rule, and **[0020](0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)**,
which gave `extent` its second unit. The specification is [corpus-map.md](../corpus-map.md).

## Context

**#113.** The SRD map quotes `srd-5.2.1.txt`, which `extract.py` derives from the PDF with
pdftotext, because a checker can hold a quote to that text and to nothing else. The text is not the
page. In the entries the trial wrote:

- `initiative-ties` and `initiative-ties-uncovered` quote "The GM decides the 13 System Reference
  Document 5.2.1 order if…": the p. 13 folio and running header, which pdftotext emits between the
  page's columns, sit inside the sentence;
- `attack-structure` quotes from "or make an attack roll as part of a spell", because pdftotext puts
  the "Unseen Attackers and Targets" sidebar and the p. 15 marker between the sentence's halves;
- `cover-bonuses`, `cover-degree` and `total-cover` quote the Cover table as extracted: "Three+5
  bonus to AC Quarters and Dexterity saving throws", with the Total row's cells reversed. Their
  values were read from the rendered page, and a `note` said so.

Nothing checked any of it. `beyondAdapter` says the reader cannot see a rule, and has no way to
say it sees it garbled. The manifest said nowhere that quotes are of the extraction.

**#114.** "Combat" ends halfway down p. 16, where "Damage and Healing" begins. A page extent
covers whole pages, so `coverage` could be met on p. 16 by a Damage and Healing quote, and
`absence` searched that section too.

## Decision

### 1. The manifest says what a quote is verbatim of

A corpus whose committed text is derived from what was published declares

```json
"quotedText": { "derivation": "srd-5.2.1-pdftotext-24.02.0-page-marked", "extractedFrom": "SRD_CC_v5.2.1.pdf" }
```

**Quotes stay verbatim of the extraction.** `derivation` must equal the corpus's `hashDerivation`:
the text quotes are held to is the text `contentHash` covers, and naming any other would hold them
to bytes nobody hashed. `extractedFrom` names the published file. `check-map.py --only extraction`
checks both. It does not require `extractedFrom` to be a file: a map package carries the manifest
and the text and not the PDF, and holding the text to the PDF is the derivation's own check
(`extract.py --check`, against `sourcePdf`).

### 2. An entry the extraction garbles declares the defect and the rendered reading

```json
"extraction": { "defect": "interleaved-table", "renderedReading": "Degree | Benefit to Target | Offered By …\nHalf | +2 bonus …" }
```

`defect` is closed, and has the three values the real cases gave:

| defect | entries | the cheap test that it is there, at every occurrence of the quote |
|---|---|---|
| `interrupted-by-page-furniture` | `initiative-ties`, `initiative-ties-uncovered` | the quote runs across a line that is the folio of the page it is on |
| `split-by-sidebar` | `attack-structure` | the quote begins or ends mid-sentence |
| `interleaved-table` | `cover-bonuses`, `cover-degree`, `total-cover` | the quote runs across three or more blank-line-separated blocks, the shape pdftotext gives table cells |

`renderedReading` is the passage as read from the rendered page. `check-map.py` requires it, and
requires it to differ from `evidence`, since a passage the extraction reads as printed has no defect.
It refuses `extraction` on a corpus that declares no `quotedText`, beside `beyondAdapter` (the
adapter cannot read the rule, or reads it garbled, not both), under `quotation: withheld` (a
rendered reading is a quote of the page), and on a derived entry.

`check-locators-pdf-text.py`'s `extraction` check holds `evidence` to the extraction as before, runs
the test for the declared defect, and fails a quote that runs across a folio line without
declaring `interrupted-by-page-furniture`, so that defect cannot be silent. **It prints every
`renderedReading` as NOT VERIFIED.** 0005 asks a field to be checkable. The part of this one that
is checkable is checked, and the part that is not is reported, never passed. What stands behind a
rendered reading is a reviewer who read the page: the SRD's three readings have an independent
verdict (0017).

### 3. A page extent may end before a heading on its last page

```json
"extent": { "unit": "page", "from": 13, "to": 16, "endsBefore": "Damage and Healing" }
```

`check-map.py --only extent` checks its shape: one line of text. `check-locators-pdf-text.py`'s
`extent-end` requires the heading to occur exactly once as a line of its own on page `to`, and
fails any `scope: in` entry whose quote on that page lies at or after it, or runs across it. A
`scope: out` entry may quote beyond it, as 0020 allows, and is named. `absence` searches only up to
the heading, and a quote after it does not reach page `to` for `coverage`. `tools/check-locators.py`
reads whitespace-collapsed text with no lines, so it cannot find the heading, and reports an
extent with `endsBefore` NOT VERIFIED, failing the run.

There is no `startsAfter`. The SRD combat chapter starts at the top of p. 13, and no map needs it.

## Alternatives considered

**Declare a normalisation in the adapter, with its own `hashDerivation`, so quotes match the
page.** #113's other option. Rejected. The defects are not normalisations. No rule on the text
un-interleaves a table or moves a sidebar back out of a sentence, so a derivation that did would
be a hand transcription wearing a derivation's name, and the checker would hold quotes to that.
A rule for the whitespace cases only (join the hyphens back, drop the space after a line-end dash)
fixes the two cases that change no rule and leaves the three that do.

**Quote the page, with the extraction as a separate check.** Rejected. No check can hold a quote
to a rendered page, and `evidence` would stop being checkable at all.

**Leave `renderedReading` unchecked and silent.** Rejected: it is what #113 found. Printing it
NOT VERIFIED on every run is what makes an unchecked table value visible to whoever reviews.

**Close the defect list with the two other gaps trial 7 found.** A line-end hyphen joined
("hand-held" read as "handheld", p. 15) and a space after a line-end em dash (`grid-range`,
"objects— count"). Not added. No entry's quote contains the first, and the second changes no word
of the rule. Both are covered by the manifest's declaration that quotes are of the extraction. A
real case that turns on either can add a value, with a test.

**Give `gm-requires-action` and `free-object-interaction` the field.** The trial README names
them, because pdftotext places the "Playing on a Grid" sidebar between the two paragraphs. Not
done. Each quote reads on the page exactly as it is extracted, and the split falls between them,
not inside either quote. There is no rendered reading that differs from the evidence, so the field
would be refused, and `split-by-sidebar`'s test would fail on both, since each begins and ends on
a sentence boundary. Their notes still record the split.

**A heading-bounded `to`, `{from: 13, to: "Damage and Healing"}`.** Rejected. A page unit whose
`to` is sometimes a page and sometimes a heading is two shapes under one name. `endsBefore` keeps
`to` a page, which is what `coverage` counts.

## Consequences

**The SRD map's bytes change, and its review is an independent verdict.** The additions are
structure a check verifies, except `renderedReading`, which asserts what the page says, including
the Cover table's values. A reviewer in a separate context, given only renders of pp. 13–15 and the
three distinct readings, agreed with all three
([`independent-verdict-113-114.json`](../../examples/srd-52-combat/independent-verdict-113-114.json)).
`review.json` keeps the blind second mapping as `previousReview`.

**The tests are shapes, not proofs.** A quote running across three blocks may be a paragraph and
two headings, not a table. A fragment may be cut short for a reason other than a sidebar. The
tests show a declared defect has the shape it names, and they catch a defect declared on a quote
that plainly lacks it. An undeclared interleaved table, like the Creature Size table, whose cells
come out in row order, is not detected. Only page furniture is enforced both ways.

**"After the heading" is in extraction order.** On a two-column page pdftotext's order is the
checker's, not necessarily a reader's. On p. 16 the two agree.

**The page-furniture test reads folios, not running headers.** `extract.py` already requires every
page to print its folio as a line, so the folio is a fact of every page. A running header is one
string per corpus, and this checker is general over the PDF grammar's page markers.
