# 0014 — A map is checked by a blind second mapping, and every disagreement is resolved against the corpus before it is used

## Status

Accepted — 2026-09-14. Decided by Brandon on
[#9](https://github.com/brandonifco/rules-factory/issues/9).

## Context

#9 asked whether a wrong map is caught at all. Trial 5
([`examples/injection-trial/`](../../examples/injection-trial/)) injected known errors into the
`hoyle-backgammon` map and supplied the denominator. The result split by shape: mechanically
checkable errors were caught (13 of 13), and **1 of 15 corpus-comprehension errors** was. The
build and its tests caught 0 of the 9 run through them.

Every miss had one property. `evidence` is checked to be *where* the entry says it is, never to
*say* what the entry says. `kind`, `clarity` and `scope` are compared against nothing that reads
the corpus.

## Decision

**Before a map is used, a second mapper who has not seen it maps the same slice. The two are
compared field by field, and every disagreement is resolved by a quote from the corpus and
recorded.** The procedure is in [method.md](../method.md), between Phase 3 and Phase 4.

Compared: `kind`, `scope`, `clarity`, presence of `ambiguity`, `dependsOn`, `enabledBy` and
`suspendedBy` edge by edge, whether each side's `evidence` supports its entry, and entries only
one side has. A disagreement is not settled by vote or by seniority of the first map. It is
answered from the corpus: one map is right, the corpus does not settle it (the entry goes to
Phase 4 as ambiguous), or it is not a disagreement about the corpus.

### What independence requires

Independence is the whole mechanism, so it is defined by what the second mapper must not have:

- the first map, its notes, decision records or findings about it;
- a prompt or brief that states the first mapper's reading;
- **any worked example drawn from the corpus under mapping, in the docs they work from.** Run 1
  gave the mapper `corpus-map.md` and `method.md` as they stood; they named about 17 of the
  corpus's entries and several verdicts, and 14 of the 15 injections touched a verdict the
  mapper could have read there. Run 2 replaced those examples, and the mapper reported that some
  replacements still paraphrased the chapter closely. Paraphrase leaks too. Examples come from
  another corpus or are removed.

## Evidence

[`examples/blind-mapping-trial/`](../../examples/blind-mapping-trial/README.md) replayed trial 5's
15 comprehension injections through a comparator
([`compare.py`](../../examples/blind-mapping-trial/compare.py)) against a blind map.

| | mechanical checks (trial 5) | blind run 1 | blind run 2 |
|---|---:|---:|---:|
| comprehension injections caught | 1 of 15 | 11 of 15 | 10 of 15 |
| flags on the clean map | — | 71 | 78 |

[Run 2](../../examples/blind-mapping-trial/run2/README.md) used a fresh mapper and docs with the
backgammon examples replaced. The two runs agree to within one, which says the catch rate is not
one mapper's accident. It is one corpus, two mappers and 15 purposive injections, and it gives no
rate for other corpora.

### A natural case, 2026-09-17

The evidence above is synthetic: errors were injected on purpose, so it shows the procedure can
find an error someone planted. It does not show that a map made in good faith contains one to
find. [Trial 9](../../examples/tax-121-principal-residence/blind-mapping/README.md) supplied that.

26 CFR § 1.121-1 was mapped, packed, and passed every check the factory has — `check-map.py
--phase publish`, all 37 locators against the section tree, the extent reached, byte-identical
packing twice. A blind second mapping then found a rule the first map does not contain.

§ 1.121-1(b)(4) Example 4 nets a $25,000 loss on one sale against $270,000 of gain on another and
excludes $245,000. The cap is $250,000, so the cap is not what produces that figure, and the
merger of the two sales is expressly bounded to the maximum limitation amount: nothing in the
operative text says a loss on one reduces the gain excludable on the other. **No entry of the
first map can produce $245,000.** An engine built from it answers $250,000 for the regulation's
own worked facts, in the regulation's voice.

Two things follow that the injection trial could not show:

  * **A map can pass every mechanical check and still be missing a rule.** Not a misclassified
    entry -- an absent one. The completeness machinery examines the entries a map has; it cannot
    ask after one nobody wrote. That is the question [#9](https://github.com/brandonifco/rules-factory/issues/9)
    asked, and this is the first answer to it from a map nobody tampered with.
  * **The comparison is worth more than the second map.** The blind mapper also produced a
    principle for its own disagreements that did not survive being tested against the
    ambiguities both mappers agreed on, and a `definedElsewhere` attribution its own map
    contradicts two entries away. Adjudication against the corpus ruled two of four
    disagreements *for the first map*, on evidence neither mapper had used. A second reading is
    not a better reading; it is a second reading, and what it is worth is the argument the two
    force.

The same exercise also found 30 `enabledBy` edges missing from the first map, which no review had
asked after.

## Alternatives considered

**A checkable claim per entry** (trial 5's suggestion). The stronger form if it can be designed,
but it is undesigned and adds schema while the schema is being settled.

**Accept the gap.** That is the state that missed 14 of 15.

**Resolve disagreements by majority or by a third mapper.** Rejected: three readers who share a
misreading outvote the corpus. The quote is the resolution, and it can be re-checked.

## Consequences

**Review load is large.** A correct map raised 71 and 78 flags. In run 1, adjudicated by hand,
35 of 71 were noise — mostly split and merge artefacts of aligning two maps with different
granularity — 13 were questions the corpus does not settle, and 23 were real errors, 13 of them
in the reference map. Run 2's flags have not been adjudicated. Each injected error added one to
four flags on top of that baseline. Cutting the split/merge noise is the next piece of work.

**Mapping cost roughly doubles** for the slice, before the review.

**Shared misreadings stay silent.** Where both mappers make the same error there is no flag. In
run 1, `depends-dropped` was missed because the blind map lacked the same edge.

**The comparator's evidence check is a proxy.** It compares span extents; the reviewer still has
to read whether a span supports its entry. Fields it does not compare (`status`, `beyondAdapter`,
`name`) produced two of run 1's four misses.

**Mapper instructions carry a maintenance duty.** Every future worked example added to
`corpus-map.md` or `method.md` from a corpus is one more thing to remove before that corpus is
blind-mapped.
