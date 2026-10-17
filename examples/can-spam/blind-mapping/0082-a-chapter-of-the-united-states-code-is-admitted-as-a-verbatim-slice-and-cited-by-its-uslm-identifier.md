# 0082 — A chapter of the United States Code is admitted as a verbatim slice and cited by its USLM identifier

## Status

Accepted — 2026-10-13. Records the change on
#653. **Extends
0074**
(a derivation rules-corpus cannot run is declared `external`) and
**0035's** account of a
`section-designation` as one unit with several spellings. **Adds no map concept**, so
0063 is met by the corpus that forced
it: the Federal Rules of Civil Procedure slice (Rule 6).

## Context

The codified statute is published by the Office of the Law Revision Counsel as USLM XML, in a
release-point zip holding one member, `usc<NN>.xml`, a whole title's text. Since 0074 the factory
admits a corpus only under a `hashDerivation` name it has read, and the only XML name left was the
eCFR's. Two things were missing:

- a name for *which bytes* a corpus of one chapter holds: the member, the zip, or a cut of it;
- a way to cite a statute passage. The USLM locator checker read one prefix,
  `/us/usc/t28a/courtRules/Civil/rule`, and cited as `Rule 6(a)(1)`.

rules-corpus at the pin has an `xml` adapter that segments by one element name and reads one
attribute, and no step that opens a zip or cuts an element.

## Decision

1. **The name is `olrc-uslm-chapter-slice-verbatim`**, and the bytes are those
   `tools/derive-uslm-chapter.py` writes: an XML declaration,
   the member's root tag verbatim, its `<meta>` verbatim, `<main>`, the one `<chapter>` element
   named by its identifier verbatim, `</main>`, `</uscDoc>`, LF-ended. Not the zip, and not the
   member: a whole-title corpus cannot say which bytes a quote was held to, and the title's other
   chapters are not what a map of this one read. The scan is textual, because a re-serialisation
   is not what the OLRC published.
2. **The slice is an `external` derivation of the release zip.** The build definition declares the
   zip unstored (length and digest) and the slice produced from it by this tool. `verify --rebuild`
   reports the zip and the extraction not verified and the consumer's expectation names both, as
   the SRD's pdftotext step is named. What holds the slice to its release is the tool's `--check`,
   which cuts the chapter again from the zip and compares.
3. **The slice is segmented by `subsection`, with `id` as the segment id.** rules-corpus segment
   ids may not begin with `/`, so the USLM `identifier` cannot be one; the element's `id`
   attribute can, and the identifier is in the same start tag.
4. **A statute is cited by its USLM identifier**, `/us/usc/t28a/courtRules/Civil/rule6/a/1`, or a list of them. It is
   a third spelling of the `section-designation` unit: a top-level designation
   (`/us/usc/t28a/courtRules/Civil/rule6`, the extent item) and a path below it. `extent.unit` is still
   `section-designation`; no field and no vocabulary value is added. A range is not read in this
   spelling, and a citation the spelling cannot read is unchecked and fails the run. Text a chapter
   prints outside its sections, its heading and table of contents, has no address and a quote there
   is refused.
5. **pack-map has a locator checker for the adapter `uslm-xml`.**

## Not decided here

- Whether a map may rest on the OLRC's editorial notes. The slice is verbatim and keeps them; they
  sit inside a section element and outside its subsections, and a map's protocol says whether it
  reads them.
- A mapper adapter for statutes. `tools/mapper`'s `uslm-xml` reads the court-rule prefix only
  (filed separately).
- Having rules-corpus unzip and slice, which would turn the `external` step into one it verifies.
