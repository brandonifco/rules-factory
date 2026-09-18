# 0038 — A map declares the passages its citation grammar cannot address, and what reaching each would require

## Status

Accepted — 2026-09-18. Records the decision on
[#299](https://github.com/brandonifco/rules-factory/issues/299), found by probing trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)) before its map was written.
**Extends [0009](0009-absence-is-a-verdict-with-evidence.md)**, which made an absence a verdict
the map states rather than a silence, and
**[0020](0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)**, which
fixed what a section extent lists. **Bounded by
[0036](0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md)**, whose
refusal is the thing being declared, and which is **not** reversed here. The specification is
[corpus-map.md](../corpus-map.md).

## Context

`examples/faa-part-107/check-locators-section.py` fails a run when **any** paragraph of the corpus
has no address:

```python
if refused:
    print(f"\n{len(refused)} paragraph(s) could not be placed in the section tree")
    return 1
```

That invariant is correct and worth keeping: a passage no citation can name is one a quote could
silently be verified against. It is asked of the whole document, and the extent is not consulted.
Measured across every committed eCFR corpus:

| corpus | unplaced | locator run |
|---|---:|---|
| `faa-part-107` | 0 | can pass |
| `faa-part-107-temporal` | 0 | can pass |
| `tax-121-principal-residence` | 0 | can pass |
| § 172.102 | 0 | can pass |
| **§ 172.101** | **15** | **fails, always** |

The fifteen are **Appendix A** (*List of Hazardous Substances and Reportable Quantities*, its
heading and 7 paragraphs), **Appendix B** (*List of Marine Pollutants*, its heading and 5), and one
paragraph whose designator `(i)` is genuinely ambiguous. The appendices are refused *correctly*:
each is an `EXTRACT` opening with an `HD1`, and 0036 is explicit that such a wrapper opens a
division of the section, so nothing in it is indexed and no citation can resolve into it.

So § 172.101 could never pass the locator run, whatever its map said — **including a map quoting
none of the refused text.** This is the first admitted corpus with an appendix, which is why it
had not come up.

**The extent cannot scope it out.** A `section-designation` extent's fields are `unit`, `sections`
and `tables`. `tables[].excluded` excludes a *table* with a reason (0035); `endsBefore` is a
**page** extent's field. Nothing excludes a run of prose.

**No entry-level field reaches it either.** `beyondAdapter` (0004) is the nearest thing in the
contract — *the rule is here and our reader cannot see it* — and its own specification names this
hole and declines it:

> An adapter that silently drops a table produces an entry nobody writes, and no field can help
> with an entry that does not exist.

0004 made adapter reach a property of **the entry**, which presumes an entry exists. An
unaddressable appendix produces none: there is nothing to hang the fact on.

## Decision

**A map declares, per corpus, each passage its citation grammar has no address for, naming why
the grammar refused it and what reaching it would require. The locator run holds that declaration
to the corpus in both directions.**

This is a *positive* statement, not an exclusion. The map does not say "this prose is out of
scope"; it says "this passage exists, nothing could cite it, and here is what addressing it would
take". The difference is the whole point: an exclusion deletes the uncertainty, and a declaration
carries it forward where a reader and a reviewer can see it. That is the same move 0009 made for
an absence and [0034](0034-a-valid-unresolved-state-is-established-not-asserted.md) made for an
unsettled reading.

### 1. The shape

`extent.unreachable`, a non-empty list when present, each item:

```json
{
  "sourceId": "cfr-49-172.101",
  "opensWith": "Appendix A to § 172.101—List of Hazardous Substances and Rep",
  "reason": "division-wrapper",
  "requires": "a citation grammar for a section's appendices; 0036 refuses a wrapper holding an HD1 because the markup does not say it is inside the paragraph it follows"
}
```

- **`sourceId`** names the corpus, because a map may cite several
  ([#298](https://github.com/brandonifco/rules-factory/issues/298)) and reachability is a property
  of one document under one grammar.
- **`opensWith`** is the passage's opening as the walk reports it — the first 60 characters of its
  normalised text. It is an identity, not a quotation, and it is stable because the corpus is
  pinned by `contentHash`. A prefix the walk refuses **twice** is refused rather than matched to
  the first declaration, which is the rule a duplicate row key already gets (0035).
- **`reason`** is closed, and its authority is the walk: each value is produced at exactly one
  place in `check-locators-section.py`, and `check-map.py` enforces the same set. A vocabulary
  copied and left to drift would let a map declare a reason no run can give.
- **`requires`** is a sentence saying what addressing the passage would take, and may not be
  empty. "I could not reach it" without "and this is what it would take" is the silence the field
  exists to break.

### 2. The run holds it in both directions

- A passage with no address that the map does **not** declare fails. The invariant is unmoved.
- A passage the map declares and the walk **reaches** fails. A declaration that has gone stale is
  a claim about the corpus that is no longer true, and a corpus whose grammar improved is exactly
  when a map must be re-read — not when a leftover line may keep standing.
- A declaration naming a `reason` the walk did not give fails, so a map cannot mislabel why it
  could not look.

Shape is `check-map.py --only extent`'s. That the declaration is *true of the corpus* is the
locator run's, because only a run of the walk knows what it refused. This is 0034's rule applied
to a different fact: the state is **established**, not asserted.

### 3. What this is not

It is **not** a way to scope prose out of the extent. The extent still names § 172.101 whole, and
every entry is still held to it. The declaration says what the *grammar* cannot address, which is
a fact about the corpus and the walk, not about the mapper's ambition.

It is **not** a reversal of 0036. The appendices remain unindexed and uncitable. What changes is
that a map must now say so, in writing, with the cost of reaching them named.

It is **not** a general place to record difficulty. `reason` is closed to what the walk emits, so
a mapper cannot declare a passage unreachable because reading it was hard.

## Consequences

- **The five committed maps do not move.** Four have no unplaced passage, so each reports `every
  passage has an address` and passes exactly as before; `srd-52-*` use a different grammar and a
  different checker, untouched. Measured, not assumed.
- **Trial 10's corpus passes the locator run**, with fifteen passages declared and § 172.102
  clean.
- **The refusal record gained a code.** `corpus_index` now reports `(text, reason, prose)` rather
  than `(text, prose)`, so the declaration and the refusal have one source of truth instead of two
  prose strings compared to each other.
- **Only the `section-designation` grammar has this.** The page grammars refuse no passage today
  and nothing is added to them speculatively
  ([#265](https://github.com/brandonifco/rules-factory/issues/265)).
- **It does not prove the map read the passage's neighbourhood.** A declared appendix is a
  declared hole, and a hole a reviewer can see is not a hole that has been filled. What the map
  owes about material it could not reach beyond saying so is
  [#300](https://github.com/brandonifco/rules-factory/issues/300)'s question, not this one's.
