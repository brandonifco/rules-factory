# 0044 — A term in a corpus's vocabulary names one **or more** defining entries, and a pointer is accounted for only when it names them all

## Status

Accepted — 2026-09-18. Records the decision on
[#311](https://github.com/brandonifco/rules-factory/issues/311), predicted by trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)) and then measured.
**Extends [0026](0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)**,
which made the vocabulary a map's own term-anchored `crossReferences`, and
**[0041](0041-a-coded-pointer-is-made-by-the-column-it-sits-in.md)**, which gave `coded-pointer`
the same `vocabularyFrom`. Sibling of
**[0043](0043-a-row-blank-in-the-column-that-names-the-row-above-is-named-below-it.md)**: the same
decomposition problem from the other side — there one rule is spread over two rows, here two rules
share one printed code. The specification is [mapper.md](../mapper.md#coded-pointer--a-pointer-its-column-makes).

## Context

§ 172.102(c)(4) states it outright:

> Table 1 authorizes IBCs for specific proper shipping names through the use of IB Codes assigned
> in the § 172.101 table of this subchapter. … Table 3 authorizes Large Packagings for specific
> proper shipping names through the use of IB Codes assigned in the § 172.101 table. **Large
> Packagings are authorized for the Packing Group III entries of specific proper shipping names
> when either special provision IB3 or IB8 is assigned to that entry in the § 172.101 Table.**

So `IB3` in column 7 carries **two** authorisations — IBCs unconditionally, and Large Packagings
for PG III only — stated in two different tables of § 172.102. `IB8` is the same. They are not one
concept, and the corpus is the authority for that, not the mapper.

`vocabulary_of` built `{term: resolvedBy}`. Measured with four declarations, two of them `IB3`:

```
crossReferences declared: 4
vocabulary_of() returns  : 3 term(s)
{"IB2": "ib2-authorized-ibcs",
 "IB3": "ib3-authorized-large-packagings",     <- the LAST declaration; the first was discarded
 "T4":  "t4-portable-tank"}

protocol._check_vocabulary problems: []
```

**The last declaration won, and nothing said so.** `_check_vocabulary` asks only that each
`resolvedBy` names an entry; both did, so the collapse was invisible to it. `detect_coded` then
resolved `IB3` against whichever target survived and reported the pointer satisfied.

A map could therefore declare both rules honestly, in exactly the shape 0026 and 0041 require, and
lose one of them with **zero diagnostics anywhere**. That is trial 9's failure repeated — a gate
recorded with none of its reach, and no check able to see the rest — with the difference that here
the mapper did the work and the tool threw it away.

## Decision

**A term names one or more defining entries, and a pointer to a term with several is accounted for
only when the entry names every one of them.**

### 1. No new field. The existing `crossReferences` already say it

```json
{ "cites": "IB3", "resolvedBy": "ib3-authorized-ibcs" },
{ "cites": "IB3", "resolvedBy": "ib3-authorized-large-packagings" }
```

Two term-anchored references, which 0026's shape has always permitted and only the reader
collapsed. `vocabulary_of` returns `{term: [id, ...]}` in declaration order. **Nothing is added to
the map, the protocol or the manifest** — the defect was in the reading, not the representation,
and #265's standard is that a concept is added only once a corpus forces one. This corpus forced
none.

### 2. Declaration order decides nothing

That it did was the whole defect. Both targets are kept, both are checked against the map, and the
two orders produce the same vocabulary and the same findings.

### 3. All of them, or the pointer is not accounted for

`Naming.missing` is the defining entries an entry points at none of, and a finding is reported per
missing target, by name. A pointer satisfied by one of two targets leaves the other obliged by
nothing, which is the state 0026 exists to make visible.

The count is printed **only where it tells the reader something** — `(2 entries state it)` beside a
term with two, and nothing beside a term with one.

### 4. A target declared twice is reported, not collapsed

A term may name several entries, so two declarations of one term are ordinary. Two declarations of
the *same* term and the *same* entry are not: they add nothing, and the likeliest reason one is
there is that a second target was meant. `vocabulary_of` returns it once and `_check_vocabulary`
reports the repetition — because silence would make "someone wrote it twice" and "someone meant two
rules" indistinguishable, which is the failure this decision is about, one step along.

### 5. `defined-term-use` keeps 0026's reading of what a declaration is about

A declaration is about a term when its `cites` **names** the term — a corpus writes *the Exhaustion
condition* as readily as *Exhaustion*, and 0026 already read it that way. What changed is only what
then satisfies it: the declaration must resolve to the defining entry, not merely mention the term.

## What was rejected

**A `definedBy` list, or any second place to write the targets.** The vocabulary is read out of the
map precisely so there is one definition to keep in step (0026), and a list in the protocol would be
the second copy that decision refused.

**Collapsing `IB3`'s two rules into one entry.** They are different packaging families under
different conditions, and § 172.102(c)(4) says so in terms. A map that merged them would be the
mapper deciding something the corpus settled.

## Consequences

- **All six committed maps produce byte-identical `mapper pointers` output** — measured against a
  baseline captured before the change, not assumed. Every committed vocabulary names one entry per
  term, and a one-target vocabulary behaves exactly as it did.
- **A repeated `cites` → `resolvedBy` pair now fails `mapper protocol`.** No committed map has one.
- **Trial 10 can state what § 172.102 states.** Whether the eventual decomposition needs anything
  further is **H2** and **H3**, still open.
- **The table-numbering hazard is recorded and not acted on**: § 172.102's prose numbers its tables
  1, 2 and 3 (IB codes, IP codes, Large Packagings) where the adapter numbers them 2, 3 and 4 by
  document order, because document-order table 1 is the ASTM volatility table inside numeric
  provision 14. 0035 already puts a caption in the entry's `note`; this is the first corpus where
  the two numberings disagree, and trial 10's entries say so in their notes.
