# Trial 9: a structural cross-reference graph — 26 CFR § 1.121-1

A run of [the method](../../docs/method.md), phases 1–3, over one Treasury regulation: § 1.121-1,
the exclusion of gain on the sale of a principal residence, as the eCFR serves it at 2026-01-01.

It exists to close the one question [#8](https://github.com/brandonifco/rules-factory/issues/8)
still had open after [trial 8](../srd-52-conditions/):

> **Can a citation address a cross-reference** — one entry's locator pointing at a constituent of
> another?

Trial 8 could not test it, and said so: the SRD points at a **term by name** — *"the Incapacitated
condition"* — and never at a constituent of another rule, so all 51 of its internal references
name a condition as a whole. A tax regulation points **structurally**: *"paragraph (e) of this
section"*, *"this paragraph (b)(3)"*, *"paragraph (d) of this section"*. That is the shape the
question is about, and this corpus makes it twenty-one times.

**The answer is yes, without a schema change, and the section below says exactly how.**

**Status: a mapping trial, and its map is publishable** — unlike trial 8's. It declares
[map-package.json](map-package.json) and passes `tools/pack-map.py`'s publish gate, which is
`scripts/validate.sh` step 5. The published map is the reconciled one (below), at version 2.0.0;
1.0.0 was the first mapping and was never pushed to nuget.org. An engine has been produced from
the map locally, from the package in a local feed, and it lives outside this repository.

## Why this slice

§ 1.121-1 was chosen over § 1.132-1, which nests deeper, because § 1.132-1 is largely a router to
sibling sections: its cross-references point at rules that are not there. § 1.121-1's
cross-references qualify **operative** rules that are in the same section — (d) carves itself back
for what (e) has already removed, and (e) subjects what it keeps to (d) — and it computes real
outcomes: a two-of-five-year ownership and use test computable to the day, a two-year window on a
vacant-land sale, a $250,000/$500,000 maximum limitation amount over a combined sale, an ordering
rule across taxable years, an allocation between residential and non-residential portions. A map
of it could produce an engine that answers rather than declines, which the conditions glossary
could not.

The slice is the whole section and nothing else. It was not widened.

## Admission

| | |
|---|---|
| `sourceId` | `cfr-26-1.121-1` |
| adapter | `ecfr-xml` — **reused, not written**; it is Part 107's |
| locator grammar | `section-designation` — **reused**; it is Part 107's |
| `contentHash` | `faf3e310a81b1d00729fd69fb422342bcff8049a98a0ae80955be3287e30bab2` |
| `hashDerivation` | `ecfr-versioner-xml` |
| `asOf` | **2026-01-01** |
| `boundaryPolicy` / `verification` / `quotation` | `pin-in-repo` / `committed-copy` / `verbatim` |
| `randomness` | `none` |
| `licence` | `public-domain-us-government` ([0028](../../docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md), [CORPUS-LICENCE.txt](CORPUS-LICENCE.txt)) |
| `extent` | `{"unit": "section-designation", "sections": ["§ 1.121-1"]}` |

**The baseline date is deliberate and it is 2026-01-01**, the same date both Part 107 maps are
pinned to, so that the three CFR maps in this repository state one instant of the CFR between
them. § 1.121-1 has not been amended since T.D. 9030 (2002), so the date buys nothing about this
text and buys comparability across the maps; trials 3 and 7 established that a map stamps its
baseline whether or not the text moves.

The bytes were fetched twice, an hour apart, and hashed identically:

```
curl --compressed "https://www.ecfr.gov/api/versioner/v1/full/2026-01-01/title-26.xml?part=1&section=1.121-1"
```

Without `--compressed` the endpoint answers `This endpoint requires response compression` and no
XML at all.

**The corpus is the section, not the part.** `sourceId` is `cfr-26-1.121-1` rather than `cfr-26-1`
because the committed bytes are one section, and `contentHash` has to cover what is committed. The
consequence runs through the whole map: **§ 1.121-2, § 1.121-3, § 1.121-4 and § 301.7701-3 are
other corpora**, listed in the manifest's `references` and not admitted, and a rule whose meaning
they fix carries `definedElsewhere`. Had the corpus been the whole of part 1, they would have been
`scope: out` entries quoting their own text ([0026](../../docs/decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md))
— and the map would then be asserting a `contentHash` over 9 MB of regulation it did not read.
Both are defensible; the map says which one it did.

## The map

Every count in this report is of **the first mapping**, which is what phases 1–3 produced and what
the blind second mapping below was run against. That map is no longer the file this example
publishes: since #8's promotion, [`corpus-map.json`](corpus-map.json) is the reconciled map (38
entries, 32 in scope, and the netting rule the first mapping did not have), and the first mapping
is frozen evidence at [`blind-mapping/first-map.json`](blind-mapping/first-map.json). The
differences are listed in [blind-mapping/README.md](blind-mapping/README.md), under *What Map C
changes*; nothing below is restated there, and nothing below is edited to match, because a trial
report that quietly acquired its own corrections would be a report of a run that never happened.

**37 entries**: 31 in scope, 6 out.

| | in scope | out of scope |
|---|---:|---:|
| operation | 26 | 6 |
| value | 5 | 0 |
| assertion | 0 | 0 |
| clear | 23 | 6 |
| ambiguous | **8 (26%)** | 0 |
| `definedElsewhere` | 8 | 0 |
| status | 31 `mapped` | 6 `declined` |

Thirty paragraphs of operative text, 10,246 characters as the checker indexes them, against
10,578 characters of `evidence`. The map quotes its corpus almost exactly once over.

**The six out-of-scope verdicts** are the four *Examples* paragraphs — (b)(4), (c)(4), (d)(2),
(e)(4) — the (f) signpost to § 1.121-4(j), and one `absentFrom` entry. There is no vocabulary
layer: unlike trial 8, where 34 of 100 entries existed only because an in-scope rule needed a term
the slice did not define, this corpus's terms are either defined in the section (`dwelling unit`,
`principal residence`, `residence`) or in the statute, which is a manifest reference rather than
an entry.

**8 ambiguous, and 26% is the point, not an accident.** Trial 1 found 21%, trial 7 27%, trial 8
18%. This sits with the regulations rather than the glossary, which is what genre predicts. All
eight are gaps under Phase 4's gate 3 — an open term with no measure stated in its own constituent
and nobody named to decide — and not one is a delegated standard:

| entry | the words |
|---|---|
| `residence-facts-and-circumstances` | *"depends upon all the facts and circumstances"*, with no factor listed at all |
| `principal-residence-facts-and-circumstances` | the same phrase, with six factors *"not limited to"* and no weighting |
| `principal-residence-majority-of-time` | *"**ordinarily** will be considered"* — a default with no stated displacement |
| `vacant-land-not-principal-residence` | *"**adjacent** to land containing the dwelling unit"* |
| `short-temporary-absences` | *"**short** temporary absences, **such as** for vacation"* |
| `out-of-residence-care` | *"physically or mentally **incapable of self-care**"* |
| `allocation-required` | *"any portion (**separate from** the dwelling unit)"* |
| `method-of-allocation` | *"the same method … **if applicable**"* — and no method where it is not |

Two of those verdicts were the closest calls and both are recorded rather than smoothed.
*"Adjacent"* is an ordinary English word and a second reader may well call it clear; it is marked
ambiguous because land across a public road, land touching at a corner and land separated by a
strip the taxpayer does not own are each inside or outside a rule the corpus does not draw, and
the litigation over § 1.121-1(b)(3)(i)(A) is about exactly that. *"Ordinarily"* is marked
ambiguous because a default whose displacement is unstated is not a rule that determines one
answer for every input, which is what `clear` asserts.

**No assertions, and that is the second corpus in a row to produce none.** A tax regulation is the
place one would expect them — the taxpayer is the only person who could say whether an absence was
a vacation — and gate 3 refuses every candidate for the same reason: the corpus never makes the
taxpayer's own determination operative, and never states a measure in the same constituent. *"All
the facts and circumstances"* delegates to nobody; it is agentless. Being the only possible source
is not a reason to reclassify
([0010](../../docs/decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md)).

**No gates.** Nothing in this section makes another rule reachable or unreachable, so no entry
carries `enabledBy` or `suspendedBy` — the same outcome Part 107 had before waivers, and the right
one for a corpus with no phases.

**No derived entries.** One candidate was rejected: that a sale of vacant land alone can never
exceed the maximum limitation amount for the pair, which follows from `vacant-land-single-sale`
and `maximum-limitation-amount`. It is arithmetic over two stated rules and it is a *test*, not a
fact the corpus entails and never states — `derivedFrom` is for the second, and the consequence is
recorded in `maximum-limitation-amount`'s note for whoever builds it.

**8 entries carry `definedElsewhere`,** which is the highest proportion of any map here — 26% of
in-scope entries, against Part 107's four of forty-three. That is what a regulation under a statute
looks like: `residence-cooperative-apartment` is section 216(b)(1) and (2)'s, `dwelling-unit-definition`
is section 280A(f)(1)'s, `depreciation-not-excludable` is section 1250(b)(3)'s, `ownership-through-trust`
is sections 671 through 679's, `vacant-land-amended-return` is section 6511's,
`ownership-through-disregarded-entity` is § 301.7701-3's, `vacant-land-ordering-across-years` is
§ 1.121-2(a)(3)(i)'s, and `residence-excludes-personal-property` is local law's. Each answers
`MissingRulesData` and names the reference; none of them was made ambiguous to hide that.

## The cross-reference graph, and its actual shape

**The section makes 21 structural references to its own constituents** — 12 in the form *"paragraph
(x) of this section"* and 9 in the form *"this paragraph (x)"* — at two levels of depth
(`(b)(3)`, `(c)(2)`, `(d)(1)`, `(e)(1)`, `(e)(2)`, and the bare `(b)` … `(e)`). It makes 5
references to four other CFR sections and 54 to the statute.

Nine of the 21 lie in operative text and are answered by this map's `crossReferences`. The other
twelve lie inside `<EXAMPLE>` elements, which are declined and unquotable — finding 2.

`crossReferences` carries **37 items: 26 resolve to an entry and 11 record a reason there is
none.** Every one of the 26 targets is a *constituent* citation — `§ 1.121-1(a)`, `(b)(3)`,
`(c)(2)`, `(d)`, `(e)`, `(e)(3)` — never the bare section. Sixteen are anchored on a structural
pointer and ten on a named one (*"the section 121 exclusion"*, *"the 2-year ownership requirement
of section 121"*), which is trial 8's term-anchored shape appearing in the same map as the
structural shape, and both resolve the same way.

`dependsOn` carries **32 edges over 37 entries, acyclic, longest chain six**, layering the backlog
16 / 3 / 3 / 7 / 6 / 2. The deepest two entries are `depreciation-excludes-allocated-portion` and
`allocation-subject-to-depreciation`, which is the mutual (d)↔(e) qualification: the *references*
run both ways and the *implementation order* does not, because each entry depends on the other's
rule and not on the other entry. The most depended-on entries are `ownership-and-use-test` (5),
`vacant-land-not-principal-residence` (4) and `allocation-required` (4).

The graph is **denser per entry than trial 8's and far shallower in fan-out**: 0.86 `dependsOn`
edges per entry against 1.42, but a longest chain of six against five over a third of the entries.
Trial 8's density was *outward*, condition → vocabulary. This one's is *inward*: a paragraph
qualifying a paragraph of the same section.

## Direct answers to #8's four questions

### Can a citation address a cross-reference?

**Yes.** Not "in principle" and not "the machinery would work" — it happens sixteen times in this
map and the locator checker proves every one of them. The cleanest pair:

| entry (its own locator) | the corpus's words | resolves to | whose locator is |
|---|---|---|---|
| `depreciation-excludes-allocated-portion` (`§ 1.121-1(d)`) | *"the section 121 exclusion does not apply under **paragraph (e) of this section**"* | `allocation-required` | `§ 1.121-1(e)` |
| `allocation-subject-to-depreciation` (`§ 1.121-1(e)`) | *"to the extent provided by **paragraph (d) of this section**"* | `depreciation-not-excludable` | `§ 1.121-1(d)` |
| `vacant-land-two-year-rule-disregard` (`§ 1.121-1(b)(3)(ii)(B)`) | *"that qualify for the section 121 exclusion under **this paragraph (b)(3)**"* | `vacant-land-not-principal-residence` | `§ 1.121-1(b)(3)` |
| `dwelling-unit-definition` (`§ 1.121-1(e)(2)`) | *"For purposes of **this paragraph (e)**"* | `allocation-required` | `§ 1.121-1(e)` |
| `ownership-through-trust` (`§ 1.121-1(c)(3)`) | *"the **2-year ownership requirement** of section 121"* | `ownership-and-use-test` | `§ 1.121-1(a)` |

**Three things that answer is worth unpacking, because two of them are not what #8 expected.**

**One: the field is `crossReferences`, and nothing else was needed.** #8 asked the question as
*"whether a citation can address a cross-reference — `§ 107.29(a)` referring to `§ 107.65`"*, which
reads as a question about the **locator**. It is not. A locator says where *this* entry's rule
sits; it never points anywhere. What points is `crossReferences`, whose `cites` is anchored
verbatim in the pointing entry's own evidence and whose `resolvedBy` is an entry id — and an entry
id resolves to whatever granularity the mapper chose, including a paragraph three levels down. The
schema has expressed this since [0009](../../docs/decisions/0009-absence-is-a-verdict-with-evidence.md)
and no corpus had exercised it structurally until now.

**Two: `dependsOn` is a different answer to a different question, and the two must not be
conflated.** `allocation-subject-to-depreciation` both *cross-references* `§ 1.121-1(d)` and
*depends on* `depreciation-not-excludable`; `dwelling-unit-definition` cross-references
`allocation-required` and depends on nothing, because a definition is implemented before the rule
that consumes it, not after it. Counted over the sixteen structural pointers: **four coincide with
a `dependsOn` edge, one runs the exact opposite way** (`dwelling-unit-definition` points at
`allocation-required`, which depends on it), **and eleven have no edge at all** — ten of those
from the declined *Examples* entries, which point at rules they are illustrations of and are built
after nothing. A map that derived `dependsOn` from the corpus's own pointers would have been wrong
in twelve places out of sixteen, once by reversing the build order and eleven times by inventing
an edge. That is trial 8's finding — *the dense part of the graph is not the part `dependsOn`
carries* — confirmed on a corpus that points in the opposite style.

**Three: the target is addressable only as deep as the corpus's markup allows, not as deep as its
numbering.** *"Paragraph (e) of this section"* resolves to an entry whose locator is
`§ 1.121-1(e)`, and `§ 1.121-1(e)` is as precise as this map can be about the rule in (e)(1),
because the eCFR XML runs *"(e) Property used in part as a principal residence—(1) Allocation
required."* into one `<P>` and the checker can only see the outer designation. The citation is
true and it is one level coarser than the regulation's own numbering, for eighteen of the 37
entries. That is finding 1, and it bounds the answer: a citation can address a cross-reference
**to the depth the adapter exposes**, which here is one level less than the corpus's own
numbering.

### Does `dependsOn` survive a corpus where most entries depend on several others?

**It survives, and this corpus is the wrong instrument to stress it with.** 32 edges over 37
entries, exactly one entry with three or more dependencies, no cycle. Where trial 8's 142 edges
came from 48 effects each consuming five or six pieces of vocabulary, a regulation's paragraphs
are written to stand alone and be *qualified* rather than *composed*: the qualification is a
cross-reference and the composition is thin. Both trials now say the same thing from opposite
directions — `dependsOn` is not where a dense corpus presses.

What did press was a shape neither trial had: **a mutual qualification.** (d) and (e) each carve
themselves back by reference to the other. As `crossReferences` it is two items and reads
correctly. Had a mapper recorded it as `dependsOn` in both directions — the natural mistake, since
each rule genuinely cannot be applied without the other — `check-map.py --only no-cycles` would
have refused the map, and the refusal would have been right for the wrong reason.

### Does the map become unreadable at that density?

**No — and the interesting part is why not, because it sharpens trial 8's answer rather than
repeating it.** Trial 8 found the entries readable and the *file* unreadable: 100 entries and
2,325 lines in which "five entries quote an identical sentence" was invisible. This map is 37
entries and 880 lines — the same 23-ish lines per entry, so nothing about the shape of an entry
got denser or lighter.

What is different is that **no two entries here look alike.** Every span occurs once, no span was
extended past its rule, and the relation a reader most wants to see — which paragraph qualifies
which — is written in the corpus's own words inside each `cites`. The facts this report states
about the graph still had to be computed (layers, in-degree, the sixteen structural pointers), so
trial 8's recommendation stands unchanged: a derived rendering, regenerated and never committed,
rather than a new field. What this trial adds is that **its trigger is repetition, not size**. A
map does not become unreadable because it has many edges; it becomes unreadable when its entries
stop being distinguishable from each other, which is what 48 near-identical effect spans did and
what 37 distinct paragraphs do not.

### Is the backlog ordering the dependency graph produces actually workable?

**Yes, and it inverts the section.** The six layers are:

1. **16** — everything that depends on nothing: the four *Examples* declines, the absence entry,
   the § 1.121-4(j) signpost, the four (b)(1) residence entries, `principal-residence-factors`,
   `maximum-limitation-amount`, `ownership-and-use-aggregation`, `use-requires-occupancy`,
   `dwelling-unit-definition` and `effective-date`;
2. **3** — `principal-residence-facts-and-circumstances`, `ownership-and-use-nonconcurrent`,
   `short-temporary-absences`;
3. **3** — `ownership-and-use-test`, `principal-residence-majority-of-time`,
   `vacant-land-not-principal-residence`;
4. **7** — `exclusion-of-gain`, `vacant-land-single-sale`, `vacant-land-sold-first-is-taxable`,
   `out-of-residence-care`, `ownership-through-trust`, `ownership-through-disregarded-entity`,
   `allocation-required`;
5. **6** — `vacant-land-ordering-across-years`, `vacant-land-two-year-rule-disregard`,
   `vacant-land-amended-return`, `depreciation-not-excludable`,
   `no-allocation-within-dwelling-unit`, `method-of-allocation`;
6. **2** — `depreciation-excludes-allocated-portion`, `allocation-subject-to-depreciation`.

`exclusion-of-gain` is § 1.121-1(a), the first sentence of the section, and it lands in **layer
4**; the definitions in (b) and (c) that a reader meets second and third are layer 1. The two
rules that come last in the print order come last in the backlog too, which is the one place the
two agree. A builder who took the section in paragraph order would build the exclusion before the
test it depends on.

## `section-designation` against `heading-path-and-printed-page`

`check-locators-section.py`'s docstring claims containment makes it **strictly stricter** than a
page-marker grammar, on three counts: containment rather than proximity, every occurrence rather
than the first, exact rather than longest-prefix. This slice is the first independent test of that
claim on a corpus the checker was not written for, and it holds — with one consequence worth
stating.

**The measurement.** Every one of this map's 37 `evidence` spans occurs **exactly once** in the
corpus. Two spans are nested inside another, and both are the deliberate case: the `absentFrom`
entry quotes the whole paragraph the missing rule would be in, which contains two entries' spans.
**No span had to be extended past the rule it carries.**

Set that beside trial 8. There, `check-locators-pdf-text.py` rightly requires every occurrence of
a quote to touch the cited page, and the SRD prints *"Speed 0. Your Speed is 0 and can't
increase."* five times — so **20 of 48 effect entries had to begin their span at the condition's
lead sentence and run forward through every effect between**, and *Round Down*, printed twice
identically, could not be cited without annexing the next glossary entry
([#207](https://github.com/brandonifco/rules-factory/issues/207)).

**Containment is why this map has none of that, and the reason is not that the CFR repeats itself
less.** It does repeat itself: Part 107 prints the anti-collision sentence identically in
§ 107.29(a)(2) and § 107.29(b), which is the case the "every occurrence" rule was written for.
What changes is that a *positional* grammar can only say *near which marker* a quote sits, so two
identical sentences on two pages make one quote resolve twice and neither citation is a lie. A
*containment* grammar asks a different question — is this quote inside this element — and two
identical sentences in two different paragraphs are two different answers, each provable. **The
duplicate-passage problem is a property of the positional grammar, not of the corpus.**

**What that implies, and it is the practical point:** #207 is real and it is bounded. It cannot
arise in `section-designation` at all, so the fix belongs to the printed-page grammars and the
CFR maps need nothing from it. Where a corpus can be had in a structured form, the structured form
is worth a good deal more than convenience — it is the difference between a citation that is
checkable and one that is only checkable when the sentence happens to be unique. Nothing in this
trial touched a locator checker's core semantics, which is #207's territory.

**The cost of containment**, in exchange, is finding 1: a containment grammar can only name what
the markup contains, and eCFR's markup contains less than the CFR's own numbering does.

## Findings: where the method and schema did not fit

### 1. The deepest provable citation is one level shallower than the corpus's own numbering

The eCFR XML runs a paragraph's first sub-paragraph into its parent's element. § 1.121-1(e)(1) is
not an element: it is the text after the run-in heading inside the `<P>` that opens
*"(e) Property used in part as a principal residence—(1) Allocation required."*, and
`check-locators-section.py` rebuilds the designation tree from the designators at the start of
each `<P>`, so it sees `(e)` and never `(e)(1)`.

**Eighteen of the 37 entries are affected** — every rule that sits in a run-in first
sub-paragraph, which in this section is eight of them:

| the rule's own designation | cited as | entries |
|---|---|---:|
| (b)(1) | `§ 1.121-1(b)` | 4 |
| (b)(3)(i) | `§ 1.121-1(b)(3)` | 1 |
| (b)(3)(ii)(A) | `§ 1.121-1(b)(3)(ii)` | 3 |
| (c)(1) | `§ 1.121-1(c)` | 2 |
| (c)(2)(i) | `§ 1.121-1(c)(2)` | 2 |
| (c)(3)(i) | `§ 1.121-1(c)(3)` | 1 |
| (d)(1) | `§ 1.121-1(d)` | 2 |
| (e)(1) | `§ 1.121-1(e)` | 3 |

Citing `§ 1.121-1(e)(1)` fails outright — correctly, because the checker cannot prove it. Note
what the pattern is: **the CFR's own drafting convention, a run-in heading joining a paragraph to
its first child, is invisible to the markup**, so every second-level rule whose siblings are
separate elements loses a level. Paragraphs that are *not* first children — (b)(2), (b)(3)(ii)(B),
(c)(2)(ii), (c)(3)(ii), (e)(2), (e)(3) — are cited exactly.

**Every one of those citations is true**, since a bare paragraph citation names that paragraph and
everything under it (0020), and every one is less precise than a reader of the regulation would
write. The map records the true one. Two things could change that and neither is done here: the
checker could read a run-in designator out of the middle of a `<P>`, which is a guess about
typography rather than about structure and is exactly the kind of guess `level_of` already refuses
to make; or the grammar could gain a way to say "as precise as the markup allows". One corpus is
not enough to write either from
([0005](../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md)).

### 2. `<EXAMPLE>` is invisible to the locator checker, and it holds 12 of the 21 pointers

`paragraphs()` walks a section's direct `<P>` children. The twenty-two worked examples of this
section sit in `<EXAMPLE>` elements — with their own nested `<P>` children for multi-part examples
— and none of that text is indexed. **An entry quoting any example would fail the locator check as
unquotable**, which fails the run.

The map declines the examples anyway, for an independent and sufficient reason (finding 3), so
nothing here is a false verdict. But the arithmetic is worth stating: of the section's 21
structural cross-references, **12 are inside examples** — including the only *"paragraph (d)(1) of
this section"*, the only *"paragraph (e)(2) of this section"* and both *"paragraph (c)(2) of this
section"* pointers. A trial that set out to test structural pointers could reach nine of them.

This was not generalised away, deliberately. Indexing `<EXAMPLE>` means deciding what designation
path an example's own `(i)`/`(ii)` parts take, and they are not section paragraphs; getting it
wrong would move what a citation identifies, which is #207's territory and not this trial's.
Recorded for whoever maps a regulation whose examples are load-bearing — which, in title 26, is
most of them.

**Since resolved, because the blind second mapping found a rule inside one.** An `<EXAMPLE>` is
now indexed under the paragraph that introduces it and nowhere deeper — `("1.121-1", "b", "4",
"Example 4")` — and `§ 1.121-1(b)(4) Example 4` is a citation the checker verifies. The question
this finding held back on, what path an example's own `(i)`/`(ii)` parts take, is still not
answered and did not have to be: an example is indexed whole, so a quote from any part of it
verifies against the example, and nothing claims those parts are paragraphs. Eight tests in
`tools/tests/test_check_locators.py`. See
[blind-mapping/README.md](blind-mapping/README.md#4-a-coverage-miss-verified-against-the-corpus):
a grammar that cannot cite a passage quietly decides the passage holds no rules, and that is what
happened here.

### 3. Declining the examples is right by the method and costs two real answers

Phase 2 says advice is dropped and the drop is recorded. A Treasury regulation's examples are the
same shape — they apply rules stated elsewhere in the section and state none of their own — so
each *Examples* paragraph is one `scope: out` entry quoting its lead-in, and the four notes say
what was declined. They are the slice's **test suite**, not its rules: every number in them is an
output of an entry this map already has, which is where Phase 6 puts them.

**And two of the eight ambiguities would be settled by an example.** (c)(4) Example 4 says a
one-year sabbatical is *not* a short temporary absence and Example 5 counts two-month vacations,
which is most of what `short-temporary-absences` declines; (e)(4) Examples 1–6 distinguish a
stable, a barn, a basement apartment with its own entrance and a law office inside the house,
which is most of what `allocation-required`'s *"separate from the dwelling unit"* declines, and
Example 6 is precisely the no-depreciation case `method-of-allocation` declines.

The map does not resolve any of them from an illustration. Doing so would be a Phase 4 decision —
the reading *is* defensible, and in tax practice the examples are authoritative — and a decision
record is where that belongs, not a `clarity` verdict. **But the shape of the problem is new and
it is not advice:** an example is not guidance a mapper may drop, it is a worked answer that
constrains the rule, and the method has no category for it. That is the finding worth taking
forward from this trial after the headline.

> **Answered 2026-09-17, and the paragraph above is left as it was.** Two of its claims did not
> survive being checked against the corpus. "Two of the eight ambiguities would be settled by an
> example" is wrong three times over: the (c)(4) examples **bracket** "short temporary absences"
> at a year and two months and settle nothing between, the (e)(4) examples illustrate the side
> (e)(1) already settles in terms, and (e)(4) Example 6 resolves under (e)(1) so
> `method-of-allocation`'s question is never reached
> ([#216](https://github.com/brandonifco/rules-factory/issues/216)). All three entries stay
> ambiguous, and the declines stand. What did survive is the last sentence, and it now has an
> answer: [0031](../../docs/decisions/0031-an-example-that-bounds-a-term-is-recorded-as-a-bound.md)
> gives the method two categories, not one — an example that is the only authority for a rule no
> operative sentence states is an entry (`combined-sale-nets-dwelling-loss`, which the blind second
> mapping found this trial had missed), and an example that bounds an open term is
> `ambiguity.bounds` on the rule it bounds, admitted only where the dimension is comparable. The
> (c)(4) pair is now recorded that way and is what an owner's ruling is checked against.

### 4. `definedElsewhere` and `ambiguity` are mutually exclusive, and one entry needs both

`method-of-allocation` says the taxpayer must allocate *"using the same method of allocation that
the taxpayer used to determine depreciation adjustments (as defined in section 1250(b)(3)), if
applicable."* It has two independent reasons not to answer: the definition is the statute's, and
where no depreciation was taken there is no such method and the corpus names no other. The schema
permits one — *"No entry carries either of those and an `ambiguity` block — that is a checkable
exclusion"* — so the entry records the gap and answers the section 1250(b)(3) pointer as an
`unmapped` cross-reference instead.

That is a defensible choice (the gap is the sharper defect and `RequiresInterpretation` is the
honest runtime answer) and it loses a fact: an engine reading this entry cannot tell that its
other half is `MissingRulesData`. The exclusion exists so that two rows of the correspondence
table cannot fire with different answers on one entry, and the case it did not anticipate is an
entry that genuinely is on two rows. One instance is not a schema change; a second would be.

### 5. `definedElsewhere` names a corpus, and "local law" is a class of corpora

*"Personal property that is not a fixture **under local law**"* fixes the rule's meaning outside
this corpus, so `residence-excludes-personal-property` carries `definedElsewhere`. The manifest
reference it names is `local-law`, with **no `citation`**, because the corpus names no single body
of law: it names whichever one governs the property. `check-map.py` accepts it — a reference with
a `sourceId` whose parts are words is recognised by the words — and the record is honest, but what
it records is "fifty-odd corpora, one of which applies" and nothing in the schema says so. Part
107's `air-almanac` reference is citationless too and is a single publication; this is the first
reference that is a *category*.

### 6. A `scope: out` entry that points into an unadmitted corpus has no `definedElsewhere` to
answer with

`examples-c`'s lead-in carries a premise: *"The examples assume that § 1.121-3 (relating to the
reduced maximum exclusion) does not apply."* The schema's rule is that a pointer into an
unadmitted corpus is `definedElsewhere`'s and not `crossReferences`'s
([#62](https://github.com/brandonifco/rules-factory/issues/62)). But this entry does not decline
for want of § 1.121-3; it declines because an illustration is not a rule, and an entry carries one
runtime reason. So the pointer is answered as `unmapped` with the reason written out. The checker
accepts it — the #62 refusal only fires where the entry's own `definedElsewhere` names the same
reference — so nothing is broken. What is recorded is that the rule as *stated* is wider than the
rule as *checked*, and the gap is exactly the case where an out-of-scope entry points outward.

### 7. `crossReferences` resolves one pointer to one entry, and a structural pointer names many

*"The provisions of **this paragraph (b)** are illustrated by the following examples"* points at a
paragraph that holds thirteen of this map's entries. `resolvedBy` is one entry id, so the
declaration is repeated with the same `cites` once per target — three times here, three for
(c), two for (d), three for (e). Trial 8 hit the same wall from the other side, where one noun
phrase made two `dependsOn` edges.

Repeating `cites` works and the checker is content, and it means a reader cannot tell a pointer
answered *completely* from one answered by a mapper's selection of three heads out of thirteen.
This map's four instances are all selections and all of them say so in their notes. Nothing here
argues for a list-valued `resolvedBy`: a pointer at a paragraph is genuinely a pointer at every
rule in it, and writing all thirteen would be noise. It argues for being able to say *"and the
rest of the paragraph"*, which is a schema change one trial should not make.

### 8. `check-locators-section.py` has no `absence` check

`tools/check-locators.py` searches the declared extent for every term an `absentFrom` entry names
and **fails the entry if one turns up** — 0009 calls it the only check that goes red by finding
something. The section-designation checker implements no such check. So
`uniformed-services-suspension-absent`'s five search terms were verified by the mapper and by
nothing else, and the same is true of any absence claim in either Part 107 map. The claim here is
true (the terms do not occur in the committed section), and the point is that the run would have
said `ok` either way. Cheap to add and not added here; it is a checker change, and the checker is
shared with two other maps.

### 9. The publish gate does not require that anyone read the map

*As it stood when this finding was written.* The map it describes is the first mapping, which
carried a `map-package.json` and a review recorded as an **exemption**; the map here now carries a
`blind-second-mapping` review, so the gap below is no longer open for this map. It is still open
for the gate, which is what the finding is about.

`scripts/validate.sh` step 5 checks the licence class (0028), `check-map.py --phase publish`,
every locator against the corpus, and that two packs produce identical bytes. Step 3 checks that a
review record names the map's current sha256 — and an exemption satisfies it, printed. So a map
that has never had a blind second mapping is publishable, and the strongest thing the gate says
about its content is that every quote is where it claims to be. That was already true and no map
had stood in the gap before; the exemption said it in the record rather than only here. The
record that replaced it is in [review.json](review.json), and the exemption's own words are in
git, at the commit before the promotion.

### 10. Where the checker was Part-107-shaped, exactly

The task was to reuse `examples/faa-part-107/check-locators-section.py` rather than copy it. Two
things blocked that and both were generalised in place, in nine lines:

- **`paragraphs()` walked `DIV6` subparts and only then `DIV8` sections.** The versioner serves a
  whole part as `DIV5`/`DIV6`/`DIV8` and a single section as a bare `DIV8`, so § 1.121-1 indexed
  as zero paragraphs and every entry came back unchecked. It now finds every `DIV8` and reads its
  subpart from its ancestry; a Part 107 path is unchanged because every Part 107 section has a
  `DIV6` ancestor.
- **`CITE_SECTION` read `\d+\.\d+`.** A Treasury regulation's number carries a hyphenated suffix,
  so `§ 1.121-1` parsed as section `1.121` and `§ 1.121-2` parsed as the *same* section — and the
  extent expression, anchored with `$`, rejected `"§ 1.121-1"` outright. Both expressions now read
  `\d+\.\d+(?:-\d+)?`, in the checker and in `tools/mapvalidator/extent.py`, which
  `test_check_map.py` holds to each other over every citation the maps make.

Neither touches what a citation *names*. Both Part 107 maps re-verify unchanged (47 and 39
citations, coverage ok), and `tools/tests` is green at 951 tests.

## The blind second mapping, and what it found

**Run, adjudicated and recorded: [blind-mapping/](blind-mapping/README.md).** A second mapper who
had not seen this map mapped the same section; the two were aligned by the text they quote (36
partnerships), every disagreement was answered from the corpus before any reconciled map existed,
and the result is **Map C, which is [`corpus-map.json`](corpus-map.json): the map this example
publishes and the engine is produced from.** The first mapping is not corrected in place — it is
one of the two frozen inputs to the comparison, so it moved beside the other, to
[`blind-mapping/first-map.json`](blind-mapping/first-map.json), and
[`build-map-c.py`](blind-mapping/build-map-c.py) rebuilds the published map from it and the
rulings on every `validate.sh` run. [review.json](review.json) now records the published map's
`blind-second-mapping` review of its bytes, in place of the first mapping's `legacy` exemption
(#8).

The three things the exemption asked a reviewer to attack were the right three, and they came out
three different ways. Of the six `scope: out` verdicts, one was wrong in a way that lost a rule:
§ 1.121-1(b)(4) Example 4 nets a $25,000 loss on the dwelling unit against $270,000 of gain on the
vacant land, no operative sentence says a loss does that, and declining the *Examples* paragraph
whole is what lost it — finding 3's cost, realised. Of the eight ambiguity verdicts, two of the
three challenged are upheld ("adjacent to" and "physically or mentally incapable of self-care" are
both gaps) and one is overturned: `allocation-required` is not ambiguous, because the separateness
test is stated in (e)(1)'s own third sentence, which **both** mappers read past. And the eighteen
shallow citations are upheld and tested — written at the regulation's own depth, eighteen of
thirty-seven fail the locator checker, for exactly the reason finding 1 gives.

The largest single correction is one this map's own review did not think to ask for: § 1.121-1(f)
gates the whole section and **no entry named it**, so Map C adds 30 `enabledBy` edges. A gate
recorded with none of its reach passes every check in this repository.

## How the evidence spans were produced

The classification, the granularity, the verdicts, the notes and the cross-reference resolutions
are the mapper's. The `evidence` bytes are not typed: every span was sliced out of the committed
XML as `corpus_index` normalises it, by a script that asserts both of its anchors are present, so
a span cannot differ from the corpus by a character. That is the same precaution trial 8 took, for
the reason [#18](https://github.com/brandonifco/rules-factory/issues/18) names.
