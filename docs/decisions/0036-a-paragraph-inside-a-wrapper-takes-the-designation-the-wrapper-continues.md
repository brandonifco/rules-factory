# 0036 — A paragraph the corpus prints inside a wrapper takes the designation the wrapper continues, and a wrapper that continues nothing is unplaced

## Status

Accepted — 2026-09-18. Records the decision on
[#285](https://github.com/brandonifco/rules-factory/issues/285), found while admitting trial 10's
corpus ([#262](https://github.com/brandonifco/rules-factory/issues/262)) and blocking its mapping.
**Extends [0020](0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)**,
which fixed what a section citation names, and is the sibling of
**[0035](0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)**, which gave a table cell an
address: 0035 answered the pointer's *source*, and this answers its *target*. The specification is
[corpus-map.md](../corpus-map.md) and [mapper.md](../mapper.md).

## Context

`examples/faa-part-107/check-locators-section.py` built the designation tree from the **direct
children** of a `DIV8`, and `tools/mapper/corpus.py`'s `ecfr-xml` adapter enumerated the same
children. § 172.102 does not state its rules there. Its special provisions — the targets of every
column 7 code in the Hazardous Materials Table — are ordinary paragraphs inside an `<EXTRACT>`, a
block set off from the running text and printed beside the designated paragraph that introduces
the run:

```xml
<P>(2) “A” codes. These provisions apply only to transportation by aircraft:</P>
<EXTRACT><HD2>Code/Special Provisions</HD2>
  <FP-1>A1 Single packagings are not permitted on passenger aircraft.</FP-1>
  <FP-1>A3 For combination packagings, if glass inner packagings … </FP-1>
```

Measured on the admitted corpus: of the 20 provisions trial 10's seven rows invoke, 8 are rows of
§ 172.102's own tables and citable since 0035, and **12 were in neither the paragraph index nor a
table** — `148, A3, A7, A10, B2, B16, N40, TP1, TP2, TP7, TP33, W31`. § 172.102 indexed 9,115 of
159,251 characters, 5.7%. A map of this corpus could hold the pointer and not its target.

Three further measurements bound what an answer may be, and each of the last two came out of a
review that ran the first answer against the real corpus rather than against the fixture:

- **A wrapper is printed *after* a paragraph, and the markup does not say it is *inside* it.**
  § 172.101 prints two `EXTRACT`s of its own, and each opens an **appendix**. They follow
  `(l)(3)`, a rule about choosing a proper shipping name. Attributing a wrapper to the paragraph
  before it made `§ 172.101(l)(3)` accept a quote of Appendix B paragraph 2.
- **The sub-items of one provision are designated in the CFR's own forms.** Inside § 172.102's
  runs the corpus prints `(1)` ten times, `(i)` three times and one each of `(a)` to `(d)` — the
  same forms its own paragraphs use. Letting them into the designator stack puts the "B", "N" and
  "W" provision runs at `§ 172.102(d)(3)`, `(d)(5)` and `(d)(9)`, three paragraphs of the
  used-battery exception.
- **One level of descent is not enough, and the shortfall is silent.** A wrapper inside a wrapper
  vanishes, and a sentence with a copy in each of two wrappers is then found once — so the
  every-occurrence rule, which exists precisely to stop a quote being verified against the wrong
  one of two copies, reports success on the copy that survived.

## Decision

**A paragraph the corpus prints inside a wrapper takes the designation of the paragraph the
wrapper continues; a wrapper that continues nothing is unplaced, not attributed; and the descent
goes to any depth.** Four parts.

### 1. The wrappers are a closed set, and the descent is to any depth

`EXTRACT` and `NOTE`. A `DIV` is not one: its text is a table, a table is addressed by its rows
(0035), and flattening one into the paragraph index is the reading that decision refused. The set
is written once in each of the two files that walk it, with the reason for each member beside it,
and a test holds the two equal — they cannot import one another (0032), and a tag one walk indexes
and the other does not is a passage one half can cite and the other cannot count.

Descent is through wrappers and nothing else, **at any depth**. A wrapper inside a wrapper is a
wrapper.

### 2. Where the wrapper continues the run, its paragraphs take the run's designation

`§ 172.102(c)(2)` names every "A" code, `(c)(1)` every numeric provision, `(c)(8)(ii)` every
portable-tank provision. **Nothing is added to the citation grammar.** What distinguishes one
provision of a run from another is the quote, and a quote is already held to its citation at
*every* occurrence — which is 0030's rule, that a repeated passage is identified by the container
its citation names, applied where the container is the run.

A wrapped paragraph **never opens a designator level**. The eCFR's formatted-paragraph tags
(`FP`, `FP-1`, `FP-2`, `FP1-2`) are block markup rather than section paragraphs, and the
parenthesised tokens they print belong to the block's own numbering.

### 3. Two things say a wrapper continues nothing, and each leaves it unplaced

An **unplaced** paragraph has no path: it is in no index, so no quote of it is ever found and no
citation ever resolves into it, and the run prints it with its reason and its first words. This is
the same posture 0035 took towards a table whose geometry the markup does not carry — *an address
that is confidently wrong is worse than none* — applied to a designation.

- **The wrapper opens a division of the section**: it holds a heading at the section's outermost
  heading level (`HD1`). § 172.101's two appendices are exactly this, and a division is not inside
  the paragraph it is printed after.
- **An ordinary `<P>` inside it states its own designation.** A `<P>` opening `(b)` after an
  enclosing `(a)` is a *sibling* of the enclosing paragraph, not something under it; inheriting
  files it beneath its own predecessor and throws its designator away.

The second rule rests on a distinction the corpus itself draws, and it was measured before it was
adopted: **every** designator-printing element inside a wrapper of either admitted section is an
`FP1-2` (54 of them), and **no `<P>` inside any wrapper of either section prints a designator**.

### 4. A note takes the paragraph it names

A `NOTE` names its own paragraph in its heading — § 172.101 prints `Note to paragraph (c)(11):` —
and that is the address it takes, where it is the paragraph the note is printed in or one the note
sits inside. The note in question is printed after `(c)(11)(iii)(C)`, so inheriting would file it
under the deepest designator that happens to be open, which is narrower than the corpus's own word
about where it belongs. A note naming a paragraph it is not printed in is unplaced: the two
statements disagree and neither is guessed at. A note whose heading names nothing takes the
enclosing designation like any other wrapper.

### Where each half is held

| Held by | What it holds |
|---|---|
| `examples/faa-part-107/check-locators-section.py` | the descent, the attribution, and the two refusals. `wrapper_reach` decides; `wrapped_elements` walks |
| `tools/mapper/corpus.py` (`ecfr-xml`) | the enumeration, over the same wrappers and the same table of tags |
| `tools/tests/mapper/test_mapper_nested_paragraphs.py` | that the two sets and the two tables are equal, and that the two reach the same paragraphs out of the same corpus |

**The two walks part company on exactly one thing.** The checker asserts *containment* — that is
its whole job — so it leaves a wrapper unplaced. A unit key asserts nothing of the kind:
`§ 172.101 ¶94` says where a paragraph sits in the section's reading order and no more. So the
adapter enumerates what the checker leaves unplaced, and the inventory reports it **unaccounted**
until something accounts for it. That is the honest state of a passage that has no address yet,
and the opposite of dropping it out of the denominator.

## Alternatives considered

**Attribute every wrapper to the paragraph before it.** This was the first answer on #285 and it
is what the review caught. It is not a reading of the markup but an assertion about it, and on the
one corpus that has both shapes it is wrong twice.

**Refuse every wrapper.** Consistent, and it leaves the 12 provisions exactly where #285 found
them. The whole point of the change is that § 172.102(c)'s runs *are* continuations of the
paragraphs that introduce them, and the corpus says so structurally.

**A new citation form for a wrapped paragraph** — `§ 172.102(c)(2) extract 1 paragraph 3`, or an
address built from the provision code, `§ 172.102(c)(2) "A3"`. Rejected: the quote already
discriminates, at every occurrence, and 0030 settled that this is how a repeated passage is
identified. A new form would also have to be invented for a corpus that has not asked for one, and
#265's standard is that a concept is added once a corpus forces it under mapping.

**Read the prose instead of the markup** — treat a wrapper as a continuation where the paragraph
before it ends in a colon. Rejected: it is a reading of English where a reading of structure is
available, and a run whose introduction ends in a full stop would silently change address.

**Decide the note's address from where it sits.** Rejected: the corpus states the address in the
note's own heading, and preferring position over the corpus's own word is the ordinal that 0035
rejected for a table row.

## Consequences

**Every FAA and tax path is unchanged, and § 172.102's unit keys move.** Four of the six committed
eCFR corpora print no wrapper at all — `part107.xml`, `part107-2020-01-01.xml`,
`part107/blind-mapping/part107-slice.xml` and `section-1.121-1.xml` — so every locator run,
inventory and sweep over every committed map is byte-identical before and after, which was
recorded before the change and compared after it. The two hazmat files do print wrappers, and
their enumeration moves: § 172.102 goes from 38 units to 612 and `§ 172.102 ¶16 (2)` becomes
`§ 172.102 ¶333 (2)`; § 172.101 goes from 87 to 103. That corpus has no map, so no citation and no
recorded rejection names any of those keys. An earlier version of this record claimed no committed
corpus contained a wrapper at all; that was true the day before trial 10's corpus was admitted and
false afterwards, and the narrower claim above is the one that holds.

**§ 172.102 now indexes 150,985 of 159,251 characters in 611 units — 94.8%**, against 5.7%, and
all 20 of trial 10's invoked provisions are citable: eight by their rows (0035) and twelve at the
designation their run continues.

**§ 172.101 has 15 unplaced paragraphs**, and a locator run over it says so and fails. Fourteen are
its two appendices, which are out of trial 10's slice; the fifteenth is the ambiguous designator
(*"(i) Such a change does not apply …"*) that #261 already recorded. Failing is the behaviour a
refusal already had, and it is left alone here: what this changes is that an unaddressable passage
is now *reported* rather than quietly attributed to the paragraph above it.

**It was reviewed against the real corpus, by a second model, before it was merged** (AGENTS.md
§6). The first answer passed every fixture test and was wrong on § 172.101 in two ways and on
nesting in a third; each is a rule above and each is watched failing under a named mutation. A
decision whose code is wrong about its own corpus is the defect this repository exists to catch.

**What this is not.** Not a new citation form, not a new unit kind, and not an answer to any of
#262's six hypotheses. `paragraph`, `heading` and `worked-example` were already units. It is the
address a wrapped paragraph did not have, and the refusal where it has none.
