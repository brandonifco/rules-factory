# Slice

- corpus: `hoyle-1909` (see `corpus-manifest.json`); the text is `hoyle.txt`, the committed copy.
- baseline: `contentHash` `5d505fa9f6202340eb55313b8ef607b816087a860d3d51b1bf92b5f65240645e`,
  `hashDerivation` `gutenberg-plain-text-including-boilerplate`. Verify with `sha256sum hoyle.txt`.
- asOf: none (a fixed printing).
- extent: `{ "unit": "page", "from": 271, "to": 280 }` — the BACKGAMMON chapter, from the `{271}`
  page marker to the end of the chapter (the `* * *` rule before `{281}` BAGATELLE). Every page in
  the extent must be reached by some entry's `evidence`.
- Footnote markers such as `[65]` inside the chapter point at the notes near the end of
  `hoyle.txt`. You may read those notes to understand the chapter.
- Locator grammar `chapter-section-and-page-marker`: `locator.citation` is
  `"<CHAPTER> / <section heading> / p. <N>"`, where `<N>` is the number of the last `{N}` page marker
  before the start of the quoted `evidence` (or after it, if the quote straddles a marker). Only the
  `p. <N>` part is checked mechanically; `locator.sourceId` is `hoyle-1909`.
- Map top level: `schemaVersion` 1, `corpus` `hoyle-1909`, `baseline` as above, `extent` as above,
  `entries`. No inline manifest; the manifest is `corpus-manifest.json` beside the map.
