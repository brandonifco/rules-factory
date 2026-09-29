# 0070 — A page-marked map may cite several corpora, each entry checked against its own, and only the principal corpus carries the map's extent

## Status

Accepted — 2026-09-29. Records the decision on
[#529](https://github.com/brandonifco/rules-factory/issues/529), forced by a private project that
admits a printed game board as a second page-marked corpus beside its rulebook. **Extends
[0039](0039-the-manifest-pins-every-corpus-a-map-cites.md)**, which let a map cite several corpora
and named `MULTI_CORPUS_ADAPTERS` for the adapters whose locator checker reads several, and
**[0042](0042-the-mapper-walks-every-corpus-a-map-cites.md)**. **Adds no map concept** — no field, no
kind, no relation, no manifest key — so
[0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md) does not govern it.

## Context

0039 said the set "today is `ecfr-xml` alone", and #298 gave `check-locators-section.py` the ability
to read several corpora in one run, each entry against the corpus its own `locator.sourceId` names.
`check-locators-pdf-text.py`, which serves both page-marked adapters, read one. A map citing two
page-marked corpora therefore could not be packed: `pack-map.py` refused it as NOT VERIFIED, which
was accurate. Everything else it needs was already there — the manifest pins each corpus (0039),
the mapper walks each (0042), and `pack-map` already passes `sourceId=path` for every cited corpus.

## Decision

**The page-marked checker takes `<sourceId>=<corpus.txt>` for each corpus, checks each entry
against the corpus its own `locator.sourceId` names, and both page-marked adapter names join
`MULTI_CORPUS_ADAPTERS`.**

- An entry citing a corpus the run was **not given** fails, naming the corpus and the entries. A
  corpus given twice, or an argument that is not `<sourceId>=<path>`, is a usage error.
- The one-bare-path form is unchanged for a map whose entries cite one corpus, and refused for a
  map citing more, where it would check every entry against whichever file it was handed.
- **The map's page `extent` describes its principal corpus** (`corpus`), as it always has. A second
  corpus is read for its locators, quotes and extraction, and **makes no extent claim**: the run
  prints that as NOT VERIFIED, and never passes it silently. So absence, coverage and the extent
  checks are the principal corpus's alone.

## What this does not do

It does not gate the *completeness* of a secondary corpus: nothing here says every page or cell of it
was read. A project that needs that holds it itself — the project that forced this does so
mechanically, in the derivation that writes its second corpus. A per-corpus extent would be a new
map concept, and this corpus does not force it; it needs its own decision if one ever does.

`plain-text`'s checker still reads one corpus per run, and a map citing two of those stays refused.
