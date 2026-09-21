# 0058 — A pointer is declared by the passage that makes it, whatever the engine does with the rule

## Status

Accepted — 2026-09-21. Records the decision on
[#254](https://github.com/brandonifco/rules-factory/issues/254), found by the `defined-term-use`
detector on its first run ([#249](https://github.com/brandonifco/rules-factory/issues/249)), and
closes [#208](https://github.com/brandonifco/rules-factory/issues/208), which asked for the
mechanism that detector is.

**Extends
[0026](0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)**
§ 1, which says an in-scope entry names an out-of-slice meaning with `crossReferences` and does
not say whether a `scope: out` entry owes the same. Adds no field. Amends no other record.

## Context

0026 § 1 is written from the in-scope side. Its sentences say *the in-scope entry names it*, and
`docs/corpus-map.md` says *where the chapter uses a word the corpus defines outside the slice*.
Both were true of the case that forced them and neither says what an entry outside the slice owes,
because in trial 7 no out-of-scope entry pointed anywhere.

`examples/srd-52-conditions/` is the corpus where that stops being hypothetical. Its
`defined-term-use` mechanism reads the fifteen condition names out of `condition-list` and finds
**54 namings of one outside its own passage, in 22 entries**. Fifty-one are declared. Three are
not, and all three are `scope: out`, `status: declined`:

```
?  suffocation-hazard: names 'Exhaustion' x2 and declares no crossReference to 'exhaustion'
?  dead-revival-conditions: names 'Exhaustion' x1 and declares no crossReference to 'exhaustion'
?  grappling-ends: names 'Grappled' x2 and declares no crossReference to 'grappled'
```

#254 put two readings. **It owes it**, because the declaration is about the corpus and not about
the engine — then these are map errors. **It does not**, because an out-of-scope entry states no
rule for the engine to gate or depend on — then the detector should exclude out-of-scope entries
and the rule should say so.

## Decision

**A `crossReferences` declaration is owed by the passage that makes the pointer. `scope` and
`status` do not bear on it.**

The map did not need a new principle to settle this; it needed reading. **Two `scope: out`,
`status: declined` entries in this same map already declare**, and one of them declares for a bare
naming with no pointer words in it at all:

| entry | scope / status | declares | anchored on |
|---|---|---|---|
| `heavily-obscured` | out / declined | `blinded`, twice | `the Blinded condition` — a bare naming — and `See also "Blinded," …` |
| `grappling-ends` | out / declined | `incapacitated` | `the Incapacitated condition` — a bare naming |
| `malnutrition-hazard` | out / declined | `exhaustion` | `See also "Exhaustion."` |

So the three the detector flags are not a convention the map holds and the detector fails to
know about. They are **omissions**, and `grappling-ends` is the proof: it declares for the
Incapacitated it names and not for the Grappled it names twice, in one entry, under one scope and
one status. No reading of "out-of-scope entries do not declare" survives an entry that declares.

The principle behind that practice is 0026's own, stated from the other side. `crossReferences`
records what the **corpus** does; `scope` and `status` record what the **engine** does. They are
orthogonal, and reading 2 collapses them: it would let a decision about implementation silence a
fact about the text. The map's job is to be true about the corpus first, and an out-of-scope
entry's evidence is quoted precisely so a reader can see what was declined — a reader who cannot
see where that passage points is reading less than the map knows.

The check conditions 0026 already states mention neither axis: an item is anchored verbatim in the
entry's own evidence, and resolves to exactly one of `resolvedBy` or `unmapped`. Both hold for an
out-of-scope entry unchanged.

**And the pointer runs the other way.** 0026 § 1 is written in one direction — an in-scope entry
names a `scope: out` entry that quotes a meaning from outside the slice. All three entries here
are the reverse: a `scope: out`, `status: declined` entry naming an **in-scope** entry, because
the passage outside the slice is the one doing the pointing and the condition it names is mapped.
The independent reviewer raised that as something § 1's text does not state, and it is worth
stating: the field records a pointer, and a pointer has a direction the corpus chose, not one the
slice chose. `grappling-ends`' pre-existing item already ran that way.

### What the three entries become

`cites` quotes the term as the evidence uses it (0026 § 1), not as some house phrasing would:

| entry | `cites` | `resolvedBy` |
|---|---|---|
| `suffocation-hazard` | `Exhaustion` | `exhaustion` |
| `dead-revival-conditions` | `Exhaustion` | `exhaustion` |
| `grappling-ends` | `Grappled` | `grappled` |

Each term is defined in exactly one entry here, so 0044's *all of them or none* is satisfied by
one target each.

**The spans are bare terms because the first drafts were not, and the review caught it.** They
were written as the surrounding phrase — `1 Exhaustion level`, `any Exhaustion levels`,
`A Grappled creature` — and the independent verdict disagreed on two of the three: a span carrying
the numeral and `level` **no longer names the condition**. It names a level count, which this map
defines in a different entry, `exhaustion-levels`, at the same citation. A level-unit span paired
with a condition-hub target is a precision defect even though the relation is the right relation,
and the reviewer found the fix in the corpus's own words — suffocation's second sentence says
*all levels of **Exhaustion** it gained from suffocating*. All three are now the bare term
`condition-list` itself declares, which is also what makes them comparable with the other 107.

### The gate stops accepting NOT VERIFIED on this step

`validate.sh`'s `every protocol's own detectors find its pointers` accepted exit 3 with a comment
pointing at #254, because whether a naming is owed was an open question and the tool was right not
to rule. It is no longer open. The step accepts only 0.

## Consequences

- **A detector that finds a naming in an out-of-scope entry is finding a defect**, not a false
  positive, and needs no scope filter. That is why `pointers.py` carries none and gains none here.
- **The rule now reads from the pointing side** in `docs/corpus-map.md`, where a mapper looks:
  it is the passage that points, not the entry's fate, that obliges the declaration.
- **#208 closes with no new mechanism.** It asked for "a declared vocabulary read out of the map
  rather than a phrase list", where the phrase list detects 0 of 51 references and no regex can
  separate a pointer from a definition because the strings are identical. That mechanism is
  `defined-term-use` with `vocabularyFrom` (#249), specified in
  [mapper.md](../mapper.md) and blessed for the coded case by
  [0045](0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md). It was built
  before this record and it works: 54 detected where the phrase list found 5, all of them
  `See also` sentences in out-of-slice entries. What #208 was missing was not a design. It was
  this ruling, without which the detector could report and not conclude.

## Limits

- **Satisfaction is per term, not per naming.** A declaration counts for a term when one item's
  `cites` contains it, so `malnutrition-hazard`'s single item anchored on `See also "Exhaustion."`
  accounts for its four bare namings of Exhaustion as well. Whether a passage that names a term
  five times in five different ways owes one item or five is a real question and this record does
  not answer it; it is
  [#399](https://github.com/brandonifco/rules-factory/issues/399). Nothing here gets worse by
  leaving it open — the entry declares, and the target is right.
- **The detector reads `evidence`, not the passage.** A naming outside every entry's quoted span
  is invisible to it, so "54" is a count over what the map quotes and never over what the corpus
  says. Stated in `pointers.py`'s own docstring and unchanged by this.
- **The term is matched exactly as printed.** A corpus that inflects its defined terms needs a
  mechanism this is not.
- **This says nothing about `dependsOn`.** 0026 § 2's test is unchanged: an entry depends on a
  passage when the engine cannot resolve its rule without it. A declined entry states no rule the
  engine resolves, so the question does not arise for these three, and none gains an edge.
- **The vocabulary is the fifteen condition names, and the corpus defines more terms than that.**
  `dead-revival-conditions` quotes *"returns to life with any **conditions** … if the durations of
  those effects are still ongoing"*, and its own note names `condition-definition` in prose while
  declaring nothing — the shape 0026 § 1 exists to stop, found by the same review and filed as
  [#400](https://github.com/brandonifco/rules-factory/issues/400) rather than fixed here, because
  whether a corpus's *general* terms belong in a declared vocabulary is a different question with
  a cost that should be measured before it is answered.
- **The review also found a missing entry, not a missing declaration.** Dehydration (p. 181) is
  `suffocation-hazard`'s structural twin, has no entry at all, and two notes in this map count the
  routes into and out of Exhaustion without it —
  [#401](https://github.com/brandonifco/rules-factory/issues/401). A count is a completeness claim,
  which is why it is filed rather than left in a reviewer's report.
