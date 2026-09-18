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
  one of two copies, reports success on the copy that survived. The same hole opens for any
  element the walk drops rather than reports, which is why part 1 below is an invariant and not a
  list of tags.

## Decision

**A paragraph the corpus prints inside a wrapper takes the designation of the paragraph the
wrapper continues; a wrapper that continues nothing is unplaced, not attributed; the descent goes
to any depth and loses nothing; and a passage with no address is never coverage.** Five parts.

### 1. The wrappers are a closed set, the descent is to any depth, and it loses nothing

`EXTRACT` and `NOTE`. Descent is through wrappers and nothing else, **at any depth**: a wrapper
inside a wrapper is a wrapper, and it is judged on its own children.

**Every text-bearing element the descent reaches is either indexed under a designation or
reported unplaced with a reason.** Nothing is dropped for being unrecognised — not an element
whose tag the walk has no unit for, not a worked example whose head does not name an example, not
a paragraph inside a wrapper that was itself refused. This is the invariant, and it matters more
than any individual shape: an element that vanishes is a second copy of a quote that nobody
counts, and the every-occurrence rule then verifies that quote against whichever copy survived —
the defect this record's own first draft shipped. It is asserted over the committed corpora and
every fixture by a traversal written independently of the walk.

`DIV` and `TABLE` are the one exception, and they are an exception because that text is addressed
**elsewhere**: a table is cited by its rows (0035), and flattening one into the paragraph index is
the reading that decision refused. They are named in a constant of their own, so that passing them
over is a decision and not an omission.

The wrapper set and the table of tags are written once in each of the two files that walk them,
with the reason for each member beside it, and a test holds the two equal — they cannot import one
another (0032), and a tag one walk indexes and the other does not is a passage one half can cite
and the other cannot count.

### 2. Where the wrapper continues the run, its paragraphs take the run's designation

`§ 172.102(c)(2)` names every "A" code, `(c)(1)` every numeric provision, `(c)(8)(ii)` every
portable-tank provision. **Nothing is added to the citation grammar.** What distinguishes one
provision of a run from another is the quote, and a quote is already held to its citation at
*every* occurrence — which is 0030's rule, that a repeated passage is identified by the container
its citation names, applied where the container is the run.

A wrapped paragraph **never opens a designator level**. The eCFR's formatted-paragraph tags
(`FP`, `FP-1`, `FP-2`, `FP1-2`) are block markup rather than section paragraphs, and the
parenthesised tokens they print belong to the block's own numbering.

### 3. Three things say a wrapper continues nothing, and each leaves it unplaced

An **unplaced** paragraph has no path: it is in no index, so no quote of it is ever found and no
citation ever resolves into it, and the run prints it with its reason and its first words. This is
the same posture 0035 took towards a table whose geometry the markup does not carry — *an address
that is confidently wrong is worse than none* — applied to a designation. The question is asked of
**every wrapper the descent reaches**, at every depth: a wrapper inside a placed wrapper is judged
on its own, and one inside an unplaced wrapper stays unplaced.

- **It opens a division of the section**, and two independent tests say so.
  - It holds a heading at the level **directly below the section itself** (`HD1`). That level is a
    sibling of the section's paragraphs, not something printed inside one. The level is read from
    the tag because the eCFR states it there **absolutely** — `HD2` means "one level further in",
    not "the outermost heading this particular section happens to print".
  - Or it holds a heading of **any** level and the element printed before it is not a designated
    paragraph: a captioned block continuing nothing. This test reads no tag digit at all.

  § 172.101's two appendices answer both — each is captioned and each follows a table. All six of
  § 172.102's captioned provision runs follow the designated paragraph that introduces them, and
  its seventh wrapper, the continuation of the portable-tank run, carries no caption at all.
- **An ordinary `<P>` inside it states its own designation.** A `<P>` opening `(b)` after an
  enclosing `(a)` is a *sibling* of the enclosing paragraph, not something under it; inheriting
  files it beneath its own predecessor and throws its designator away.
- **A note's heading does not name exactly one paragraph it sits in** — part 4.

The second rule rests on a distinction the corpus itself draws, and it was measured before it was
adopted: **every** designator-printing element inside a wrapper of either admitted section is an
`FP1-2` (54 of them), and **no `<P>` inside any wrapper of either section prints a designator**.
Its test is deliberately broader than the expression that builds the designator tree, which
requires whitespace after the token and so reads neither `(b)(1) Text` nor `(b)Text` as a
designation ([#289](https://github.com/brandonifco/rules-factory/issues/289)). Refusing too widely
only withholds an address; inheriting too widely hands out a wrong one, so the refusal takes the
broad reading and the tree is left alone.

### 4. A note takes the one paragraph it names, or none

A `NOTE` names its own paragraph in its heading — § 172.101 prints `Note to paragraph (c)(11):` —
and that is the address it takes, where it is a paragraph the note is printed in. The note in
question is printed after `(c)(11)(iii)(C)`, so inheriting would file it under the deepest
designator that happens to be open, which is narrower than the corpus's own word about where it
belongs.

**The heading is parsed as a whole address or refused.** Where it says it names a paragraph and
names several (`Note to paragraphs (a) and (1):`), names none, or names a group this grammar
cannot read (`Note to paragraph (a)(12345):`), the note is unplaced. That is the rule a row key
already has: a key matching two rows is refused and never resolved to the first of them (0035).
Collecting whatever tokens a `findall` happened to catch would invent `(a)(1)` out of the first
and `(a)` out of the second — an address nobody wrote, on a passage nobody could check.

A note naming a paragraph it is not printed in is likewise unplaced: the two statements disagree
and neither is guessed at. A note whose heading does not claim to name a paragraph takes the
enclosing designation like any other wrapper.

### 5. A unit no citation can resolve into is counted, reported, and never coverage

The enumeration counts an unplaced passage — dropping it would shrink the denominator to what
happened to be citable, which is the opposite of what an inventory is for. But a quote of it is
**not coverage of it**: the locator run reports that entry unchecked and fails. So `mapper
inventory` carries placement on the unit, reports `no address: N` on a line of its own, exits NOT
VERIFIED while any exist, and **fails** a map whose entry quotes one. Accounting for such a unit
means recording a rejection against it, which is the one verdict that needs no address.

### Where each half is held

| Held by | What it holds |
|---|---|
| `examples/faa-part-107/check-locators-section.py` | the descent, the attribution, and the two refusals. `wrapper_reach` decides; `wrapped_elements` walks |
| `tools/mapper/corpus.py` (`ecfr-xml`) | the enumeration, over the same wrappers and the same table of tags, and `Unit.unaddressable` |
| `tools/mapper/inventory.py`, `cli.py` | the `no address` count, and the failure when an entry quotes such a unit |
| `tools/tests/mapper/test_mapper_nested_paragraphs.py` | that the two sets and the two tables are equal, and that the two reach the same paragraphs out of the same corpus |

**The two walks part company on exactly one thing, and the direction is asserted.** The checker
builds the designator tree; the adapter does not, because a unit key says where a paragraph sits
in the section's reading order and asserts no containment. So the adapter decides the three tests
that need no designation and the checker decides those three and a fourth — whether the paragraph
a note's heading names is one the note is printed in. **Everything the adapter calls unaddressable
the checker leaves unplaced; the reverse does not hold**, and a test asserts that containment over
the committed corpora and every fixture, so it cannot drift into disagreement unnoticed. The gap
is one unit per malformed note heading, in the direction where the tool that gates a citation is
the stricter of the two ([#290](https://github.com/brandonifco/rules-factory/issues/290)).

## Alternatives considered

**Attribute every wrapper to the paragraph before it.** This was the first answer on #285 and it
is what the review caught. It is not a reading of the markup but an assertion about it, and on the
one corpus that has both shapes it is wrong twice.

**Read the division test from the outermost heading level each section happens to print.** The
obvious repair for a tag-literal test, proposed in review, and it is wrong on the corpus this
record is about: § 172.102 prints no `HD1` at all, so its outermost level is 2, and the rule would
refuse all six of its captioned provision runs — every "A", "B", "N" and "W" code, which is what
the change exists to reach. The eCFR's heading levels are absolute, and the level-agnostic part of
the answer is the second test above, which asks what the wrapper follows rather than what its
heading is called.

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
designation their run continues. Each of the twelve quotes occurs exactly once in the index, so
the discrimination is the every-occurrence rule and not luck.

**§ 172.101 indexes 88 paragraphs and leaves 15 unplaced**, and a locator run over it says so and
fails. Fourteen are its two appendices, which are out of trial 10's slice; the fifteenth is the
ambiguous designator (*"(i) Such a change does not apply …"*) that #261 already recorded. Failing
is the behaviour a refusal already had, and it is left alone here: what this changes is that an
unaddressable passage is now *reported* rather than quietly attributed to the paragraph above it.
Its note is the one passage that gained an address, at `§ 172.101(c)(11)`.

**What this does not reach, recorded rather than left to be rediscovered**
([#290](https://github.com/brandonifco/rules-factory/issues/290)). The invariant holds *inside* a
wrapper; a section's direct `CITA`, `EDNOTE` and `HD1` children are still passed over without a
word, which is older than this record. A wrapper that opens a division, carries an `HD2` and
follows a designated paragraph passes both division tests. `NOTE_HEAD` and `example_label` each
read one heading form. Of those, only the first reports nothing at all; the rest report unplaced,
which withholds an address rather than inventing one.

**It was reviewed against the real corpus, by a second model, twice, before it was merged**
(AGENTS.md §6). The first answer passed every fixture test and was wrong on § 172.101 in two ways
and on nesting in a third. The second answer fixed those and was still tag-literal where this
record claimed to be level-agnostic, checked attribution only at the outermost wrapper, read a
note heading with `findall`, and let three kinds of element vanish. Each is a rule above and each
is watched failing under a named mutation. A decision whose code is wrong about its own corpus is
the defect this repository exists to catch, and a record that overstates its own mechanism is the
same defect written down.

**What this is not.** Not a new citation form, not a new unit kind, and not an answer to any of
#262's six hypotheses. `paragraph`, `heading` and `worked-example` were already units. It is the
address a wrapped paragraph did not have, and the refusal where it has none.
