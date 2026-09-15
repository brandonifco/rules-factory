# 0023 — A map package is licensed as its corpus and the factory are, in a licence file it carries

## Status

Proposed — 2026-09-15, on [#106](https://github.com/brandonifco/rules-factory/issues/106) (trial 7,
the SRD 5.2.1 combat map). **Amends [0015](0015-a-map-is-published-as-a-versioned-package.md)**:
the package gains `LICENCE.txt`, and its nuspec licence changes. Brandon should confirm it before
the SRD map is published.

## Context

`tools/pack-map.py` wrote `<license type="expression">Apache-2.0</license>` into every map package
(with the `licenseUrl` nuget.org demanded, #50). That is the factory's own licence, and it was
wrong for every map the factory has packed, because a map quotes its corpus verbatim
(`quotation: verbatim`, 0013):

- **SRD 5.2.1** is CC-BY-4.0. Its Legal Information page requires a stated attribution in any work
  that uses it, and asks for no other attribution to Wizards. A package carrying its quotes under
  Apache-2.0 with no attribution breaks those terms.
- **Hoyle** (Project Gutenberg eBook 39445) and **14 CFR Part 107** are public domain in the United
  States. Apache-2.0 on their quotes claims a licence nobody can grant, and there is no SPDX
  identifier for "public domain". `CC0-1.0` would be untrue: neither source is a CC0 dedication.

The package is not only quotes. `tools/check-map.py`, the props file, and everything in the map
that is not quoted corpus text (ids, names, notes, relations, questions) are this repository's
work, which is Apache-2.0 (`LICENSE`).

## Decision

**The package's licence is a file, `LICENCE.txt`, named by `<license type="file">`**, with
`<licenseUrl>https://aka.ms/deprecateLicenseUrl</licenseUrl>`, the companion nuget.org requires
for a licence file just as #50 found it requires `https://licenses.nuget.org/<expression>` for an
expression. The file has two parts, and says which contents each covers:

- **A. The corpus's terms**, for the quoted corpus text: the map's corpus terms file, verbatim.
- **B. Apache License 2.0**, for everything else: this repository's `LICENSE`, verbatim.

pack-map.py generates it deterministically from those two files, so packages stay byte-identical
across packs (0015). The description says the licence is in `LICENCE.txt` and that the quotations
are not Apache-2.0; it names no rights holder, so it adds no attribution the SRD asks us not to give.

**The corpus's terms have one source of truth: the manifest's `licence` field.** It is already a
reviewed fact of the corpus, and changing it is already major under 0015. But it is a short
token (`public-domain-us-government`) or a sentence, not text a package reader can act on. So each
map's `map-package.json` names a **corpus terms file** beside it:

```json
{ "version": "1.0.0", "licence": { "corpusTerms": "CORPUS-LICENCE.txt" } }
```

That file writes the terms out: for the SRD, the licence and the attribution statement word for
word; for a public-domain corpus, what "public domain" means for that text and where it stops
(United States law only, not a CC0 dedication, Gutenberg's trademark terms apply to its eBook
rather than to the excerpts). **The file must restate the manifest's `licence` for every corpus
the map cites, verbatim with whitespace normalised**, so it cannot drift from the manifest.
`pack-map.py` refuses, writing nothing, when `licence.corpusTerms` is absent, is not a plain
`.txt` name in the map directory, cannot be read as UTF-8, or does not restate the manifest, and
when a cited corpus has no `licence`. **Nothing defaults to Apache-2.0.**

| map | manifest `licence` | package licence |
|---|---|---|
| `srd-52-combat` | `CC-BY-4.0. Attribution required: …` (the statement) | A: CC-BY-4.0 and WotC's statement verbatim, noting the quotes are verbatim excerpts of the extracted text; B: Apache-2.0 |
| `hoyle-backgammon` | `public-domain-underlying-work; Project Gutenberg trademark terms apply to the edition` | A: US public domain, no licence granted, Gutenberg's terms govern its edition and trademark; B: Apache-2.0 |
| `faa-part-107` | `public-domain-us-government` | A: US public domain under 17 U.S.C. 105, no licence granted; B: Apache-2.0 |

### Versions

`LICENCE.txt` is a package file other than the map and manifest, and the nuspec's licence
changes, so under 0015's closed lists this is a **major** change to every map package, and so is
any later change to a terms file or to `LICENSE`. **The next published versions of
`hoyle-backgammon` and `faa-part-107` are major bumps** (from 4.0.0 and 2.0.0). This record bumps
neither: their `map-package.json` versions are unchanged, and the bump belongs to whichever change
publishes them next. `srd-52-combat` is 1.0.0 and unpublished, so its first version carries the
licence file.

## Alternatives considered

**An SPDX expression per map** (`Apache-2.0 AND CC-BY-4.0`, with attribution in the description or
a NOTICE file). Rejected. An expression cannot say which part of the package is under which terms,
cannot state a public-domain corpus at all, and would need a second mechanism for the attribution
anyway. Whether nuget.org accepts a compound expression with CC-BY-4.0, and which `licenseUrl` it
wants for one, was not tested. A licence file serves all three maps with one mechanism. The cost:
tools that read licences by SPDX id show these packages as having a file licence, not a known id.

**`CC0-1.0` for the public-domain corpora.** Rejected as untrue. Neither source dedicates its text
under CC0, and CC0 is a waiver by a rights holder that rules-factory is not.

**Derive the package licence from the manifest's `licence` field alone.** Rejected. The field is a
token or a sentence. Turning `public-domain-us-government` into text a reader can rely on would put
a table of legal prose in pack-map.py. That prose would change with the packer rather than with a
reviewed file beside the map, and a new corpus's token would have no text at all.

**Declare the licence only in `map-package.json`** (for example an expression and attribution
string there). Rejected as a second source of truth. The manifest already records the corpus's
terms, and a map-package field could say something else. The terms file is checked against the
manifest instead.

**Put the corpus text's licence in `<copyright>`.** Rejected. That is a copyright notice, not
terms, and the SRD asks for its statement and no other attribution.

## Consequences

- Every map directory with a `map-package.json` has a corpus terms file, and a new map cannot be
  packed until someone writes one. That is where a corpus's redistribution terms get read and
  written down for the package, not assumed.
- The check is textual. It proves the terms file carries the manifest's words. It cannot prove
  the explanation around them is legally right, or that the manifest's `licence` was read
  correctly at admission. Those stay a reviewed claim.
- The licence file includes the whole Apache text, about 11 KB, in every package.
- `publish-map.yml` assumed nothing about the licence: it gates, re-packs and compares digests. It
  is unchanged. The first push with a licence file is the real test of nuget.org's acceptance of
  `type="file"` with this `licenseUrl`, as #50's first publish was for the expression.
- A licensed `local-copy` map (0022) needs a terms file too. Such a package is never published, so
  its terms file only documents what the operator holds.
