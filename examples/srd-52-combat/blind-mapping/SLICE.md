# Slice

- corpus: `srd-5.2.1` (see `corpus-manifest.json`); the text is `srd-5.2.1.txt`, the committed copy.
- baseline: `contentHash` `c55926cb77bc7ea09096fc652db1411d763eae89d430c52221ed8709a075b100`,
  `hashDerivation` `srd-5.2.1-pdftotext-24.02.0-page-marked`. Verify with `sha256sum srd-5.2.1.txt`.
  The text is pdftotext's output for each page of the PDF, each page preceded by a line `{N}`,
  where physical page N is printed page N. Nothing in it is normalised.
- asOf: none (a fixed printing).
- extent: `{ "unit": "page", "from": 13, "to": 16 }` — the "Combat" section, from its heading at the
  `{13}` page marker to its end on p. 16, where the next section begins on the same page. That next
  section, and the rest of p. 16, are not in the slice. Every page in the extent must be reached by
  some entry's `evidence`.
- `pages/p-013.png` … `pages/p-016.png` are renders of the same four PDF pages. pdftotext reorders
  columns and sidebars, can place the page footer mid-sentence, and can interleave table cells; use
  the renders to read what the page says. `evidence` must still be quoted from `srd-5.2.1.txt`.
- The rest of `srd-5.2.1.txt` is the same document. You may read any of it to understand the slice
  (the slice points into other sections by name).
- Locator grammar `heading-path-and-printed-page`: `locator.citation` is
  `"<heading> / <heading> / … / p. <N>"`, a path of the document's own headings ending with the
  heading the quote sits under, then the page. `locator.sourceId` is `srd-5.2.1`. What is checked:
  - the whole `evidence` occurs in `srd-5.2.1.txt`, with runs of whitespace treated as equal (no
    other normalisation: quote the extracted characters, hyphens and dashes as they are);
  - every occurrence of that text touches page N (the page it starts on, or a `{N}` marker falls
    inside it);
  - the last heading in the path occurs as a line of its own somewhere between the start of page
    N−1 and the start of the quote.
- Map top level: `schemaVersion` 1, `corpus` `srd-5.2.1`, `baseline` as above (no `asOf`), `extent`
  as above, `entries`. No inline manifest; the manifest is `corpus-manifest.json` beside the map.
