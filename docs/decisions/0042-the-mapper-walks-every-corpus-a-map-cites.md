# 0042 — The mapper walks every corpus a map cites, each with its own share of the extent, its own adapter and its own protocol

## Status

Accepted — 2026-09-18. Records the decision on
[#305](https://github.com/brandonifco/rules-factory/issues/305), found while making the protocol
per cited corpus and forced by trial 10 ([#262](https://github.com/brandonifco/rules-factory/issues/262)).
**Extends [0039](0039-the-manifest-pins-every-corpus-a-map-cites.md)**, which established that a
map may cite several corpora, and **[0040](0040-a-protocol-is-about-one-corpus-and-a-map-has-one-per-corpus-it-cites.md)**,
which gave each of them a protocol. **Carries out [0009](0009-absence-is-a-verdict-with-evidence.md)**,
whose point is that what was not read must be visible. The specification is
[mapper.md](../mapper.md).

## Context

`tools/mapper/cli.py`'s `_walk` opened **the map's principal corpus** and nothing else:

```python
source = document.get("corpus")
adapter = corpus_step.open_corpus(manifest, source, ...)
units = adapter.units(extent)
```

`units` was then the whole candidate set for both `mapper inventory` and `mapper sweeps`. A map
citing two corpora has two failure modes, and both were measured on trial 10's admitted corpora:

| the map | on the old walk |
|---|---|
| extent names **both** § 172.101 and § 172.102 | **refused outright** — *"the extent names § 172.102, which the corpus does not contain"* |
| extent names **only** § 172.101, entries cite both | **runs**: 104 units enumerated, coverage reported over them, and § 172.102's **612** units never enumerated at all |

The first blocks the honest map shape from being measured. The second is worse: it is formally
green, and it is a completeness claim over **15%** of what the map claims to have read. No sweep
could find anything in the other 85%, because a sweep runs over the units the walk left
unaccounted and those units were never enumerated to be left.

That is [#270](https://github.com/brandonifco/rules-factory/issues/270)'s failure one level up —
a measurement reporting coverage over a smaller universe than the map claims — and it would have
invalidated trial 10's **H4**, whose whole question is whether coverage can be evidenced.

## Decision

**One walk per corpus the map cites.** Each walk has:

- **its own adapter**, opened from the manifest, which is already the one place saying which
  adapter read a corpus and where the pinned bytes are;
- **its own share of the extent** — the sections that corpus contains, with their table slices.
  The map declares one extent across all its corpora, and handing the whole of it to one corpus's
  adapter either refuses the run or claims coverage of a section that corpus does not hold;
- **its own protocol** (0040). A corpus with no protocol is **refused**, not swept under another
  corpus's: a corpus swept by the wrong interrogation is #208's failure with the mechanism known;
- **only the entries that cite it.** An entry of § 172.102 quotes nothing in § 172.101, and
  counting it unlocated there would report every multi-corpus map as full of quotes the mapper
  cannot find.

### The invariant that must survive the split

A section the extent names that **no** cited corpus contains is still refused. `units` held that
for one corpus — *an extent over a section that is not there claims coverage of nothing* — and
splitting the extent would quietly lose it, because each corpus would simply decline the sections
that are not its own. So it is asked of the **union** instead, after every walk and before any is
trusted.

### The verdict is the worst of them

A corpus nobody measured is not measured by another corpus being clean. `mapper inventory` and
`mapper sweeps` each report per corpus and return the worst verdict across them, and the inventory
prints a total besides: units, unaccounted, unaddressable, and entries located.

### How a corpus's share is found

`Adapter.portion_of(extent)` returns the part of the extent this corpus contains and the extent
items it accounts for. The default is the whole extent and no claim — a grammar whose corpus is
one document has nothing to divide — and `EcfrXml` overrides it by intersecting the section list
with the sections the corpus actually holds, carrying each section's table slices with it.

The corpus is the authority for what it contains, which is the same principle 0039 applied to
pinning: the thing itself says, rather than a second declaration that can drift.

## Consequences

- **No committed map moves.** `mapper inventory` and `mapper sweeps` produce **byte-identical**
  output for all five committed maps — measured, not assumed.
- **Trial 10's inventory sees 716 units across two corpora**, 612 of them in § 172.102, where the
  old walk saw 104 and reported them as the extent's coverage.
- **A single-corpus caller is refused rather than silently served.** `_walk` remains for callers
  that read one corpus and now refuses a map citing more, so no future caller can inherit the
  defect by accident.
- **H4 can be asked honestly.** Whether coverage *can* be evidenced is trial 10's question; until
  this, the measurement would have answered it over the wrong universe.
