# 0028 — A PDF text is derived for the printed pages the manifest declares, and marked with their printed numbers

## Status

Accepted — 2026-09-15. Records the fix for
[#139](https://github.com/brandonifco/rules-factory/issues/139), which blocks criterion 1 of
[#3](https://github.com/brandonifco/rules-factory/issues/3). **Extends
[0022](0022-a-licensed-copy-is-used-locally-by-a-named-operator-and-never-published.md)**, which let
an operator use a licensed copy locally and said nothing about what that copy is, and
**[0024](0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)**, which held
quotes to a derived text for a book whose printed pages are its PDF pages. The specification is
[corpus-map.md](../corpus-map.md), "The corpus manifest".

## Context

deckard's corpus is the SR6 core rulebook, a PDF the operator holds under 0022. Three things stood
between it and a packable map.

- **Its pages are numbered differently.** It prints page N-1 on PDF page N. deckard cites printed
  pages, and a reader turns to printed pages. The SRD's `extract.py` refuses exactly this, and the
  PDF text checker read `{N}` markers as PDF pages running 1, 2, 3, ….
- **The hash has to cover the text, not the PDF.** 0024 holds quotes to the bytes `contentHash`
  covers. deckard pins the PDF's digest. A `contentHash` over the PDF would leave the quotes held to
  bytes nobody hashed, and `check-map.py` already refuses that (`quotedText.derivation` must be the
  `hashDerivation`).
- **The text is licensed.** Deriving the whole book makes 300-odd pages of text exist where one
  map needs three. 0022 keeps a licensed copy on one machine, and it did not ask how much of it.

## Decision

### 1. One derivation, parameterised by the manifest

`pdftotext-24.02.0-printed-page-marked`, written by `tools/extract-pdf-pages.py`. The manifest
declares its parameters:

```json
"sourcePdf": { "sha256": "…", "bytes": 12216214, "envVar": "CORE_RULES_PDF" },
"derivedText": { "extractor": "pdftotext", "extractorVersion": "24.02.0", "pdfPageOffset": 1,
                 "printedPages": [ { "from": 35, "to": 36 }, { "from": 44, "to": 44 } ] }
```

For each printed page P, the tool runs `pdftotext -enc UTF-8 -f Q -l Q` for Q = P + offset, and
writes `{P}` and that page's text. The first line names the derivation, the pages and the offset.
`contentHash` is SHA-256 over the result, and intake's `HASH_DERIVATIONS` has it. `sourcePdf.sha256`
is the PDF's, and `check-map.py` refuses it equal to `contentHash`, since they are different facts.

### 2. Markers are printed pages, and the text holds only the declared ones

A citation's `p. 35` is the printed page, the same as for the SRD. The two derivations agree on the
grammar and differ only in which numbers exist. `check-locators-pdf-text.py` reads the header and
requires the markers to be exactly its pages. Without a header they must still run from 1. An
`extent` claiming a page the text does not hold is a usage error, not an unreached page.

**Each page proves its own offset.** The tool refuses a page with no line that is its printed page
number. A wrong offset is caught at the first page, not in a citation that happens to land.

### 3. The extractor is pinned and the text stays out of repositories

pdftotext 24.02.0 is part of the derivation's name, as the SRD's is, and `derivedText` repeats it
so `check-map.py` can refuse a mismatch. The tool refuses another version, a PDF with another size
or digest, and an output path inside a git work tree (a `.git` directory or file above it). Beside
the text it writes `<text>.derivation.json`: the extractor, version, argv template, the PDF's
digest, the PDF pages read, and `bodySha256`, with no corpus text.

## Alternatives considered

**Mark PDF pages, and cite `printed p. 35 / PDF p. 36`.** deckard's form. Rejected. It has two
numbers that can disagree in one citation, and nothing reads the printed one. An offset declared
once and proved on every page leaves one number, the one on the page.

**Derive the whole PDF, and bound only what the map claims.** Simpler. Rejected for a licensed
copy: the text would exist in full wherever the operator derived it, and the map needs a few pages.
A committed-copy corpus may still declare every page.

**`contentHash` over the PDF, with the text's digest recorded beside it.** Rejected by 0024's rule.
Quotes are held to the bytes the baseline covers, and a baseline over the PDF would need a second
check to say the text follows from it, run by every consumer. With the hash over the text, only
`--check` needs the PDF.

**Generalise `examples/srd-52-combat/extract.py`.** Rejected. Its text is committed and its digest
published, so it has to stay byte-stable. It stays as it is, and the new tool is the general one.

## Consequences

**No existing map, text or hash changes.** The SRD text has no header, and its markers are read as
before.

**`--check` is NOT VERIFIED without the PDF and pdftotext 24.02.0**, and says so. Without them
it holds the text to `contentHash` and its header to the manifest, and nothing more. Factory CI
never holds a licensed PDF, so its tests use a synthetic PDF and a stand-in pdftotext.

**A page without a printed folio cannot be derived.** Chapter openers sometimes omit one. A map
that needs such a page needs another way to prove its offset, and a decision to add it.

**Contiguous ranges only, per span.** `printedPages` lists spans, and a map's `extent` names the
pages inside them. Whether a map's extent can list more than one span is
[#140](https://github.com/brandonifco/rules-factory/issues/140).
