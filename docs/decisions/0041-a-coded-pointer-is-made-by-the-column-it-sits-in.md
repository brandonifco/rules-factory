# 0041 — A coded pointer is made by the structural context it sits in, not by the token's text

## Status

Accepted — 2026-09-18. Records the decision on
[#307](https://github.com/brandonifco/rules-factory/issues/307), the measured outcome of trial
10's **H2** ([#262](https://github.com/brandonifco/rules-factory/issues/262)), recorded in advance
as [#284](https://github.com/brandonifco/rules-factory/issues/284).
**Extends [0026](0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)**,
which made a corpus declare how it points and gave the three mechanisms this adds a fourth to,
and **[0035](0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)**, whose citation grammar
names the column this mechanism reads. **Satisfies the standard
[#265](https://github.com/brandonifco/rules-factory/issues/265) proposes**: the concept was
refused in advance, attempted under mapping with the existing vocabulary, and added only after
the attempt was measured failing. The specification is [mapper.md](../mapper.md).

## Context

49 CFR § 172.101 column 7 holds `IB2, T4, TP1` and nothing else. Each is a pointer into
§ 172.102, and there is no English pointer phrase and no defined term named anywhere near the
cell. Of 0026's three mechanisms, `phrase` is the one [#208](https://github.com/brandonifco/rules-factory/issues/208)
already measured as blind on a corpus that does not point in words, `section-designation` is for
`§ 173.202` (which column 8 really does use), and `defined-term-use` is the only one left.

**So `defined-term-use` was declared and run, on the seven rows the trial settled.** Ground truth
is 33 column 7 code occurrences, 20 distinct codes.

| the row entry's evidence | detected | true positives | false positives | missed |
|---|---:|---:|---:|---:|
| the whole row, cells in column order (0035) | 35 | **33** | **2** | 0 |
| the column 7 cell alone | 34 | **33** | **1** | 0 |

It fires. It misses nothing. And it reads the numeric code `148` as a pointer in two places where
it is not one:

1. **Another provision scheme in the same row.** `Alkali metal amalgam, solid` prints
   `13, 52, 148` in **column 14** — vessel stowage *other provisions*, which are § 176.84's and
   not § 172.102's.
2. **A part number in the section's own prose.** *"(For bulk transportation by vessel, see 46 CFR
   parts 30 to 40, 70, 98, 148, 151, 153 and 154.)"* — a **46 CFR part**. It matches however the
   rows are quoted, so no quoting discipline removes it.

The `§ 173.148` collision #284 predicted is real in kind, and turned up in two other forms.

**Worth recording, because it bears on how much any clean run proves:** the letter codes
(`A3`, `IB2`, `W31` …) do not collide in this slice. A seven-row slice chosen without a numeric
code would have run clean and concluded H2 held.

## Decision

**A `coded-pointer` is a pointer token whose pointer meaning is established by a structural
context the corpus and adapter declare, rather than by the token's lexical text alone. It is the
fourth member of `pointerMechanisms`, and it is detected by reading that context.**

### 1. Why no lexical mechanism could have worked

A column 7 code is a pointer **because of the column it sits in**. `defined-term-use` reads text,
and column membership is not text — it is the table's geometry, which 0035 made addressable and
which the adapter already reads. 0026 defines `defined-term-use` as pointing *by naming a term
the corpus defines*, and a bare code is not a term this corpus names in its prose anywhere.

Declaring it would therefore be a true-sounding statement that is false about how the corpus
points, and `protocol.py` exists to refuse exactly that: *a declared interrogation nobody performs
is worse than none — it reads as coverage.* Firing is not the same as being right.

### 2. Vocabulary growth, not schema growth

```json
{ "mechanism": "coded-pointer", "column": 7, "vocabularyFrom": "column-7-codes" }
```

- `vocabularyFrom` is **the existing key**, reused. The codes resolve through an entry whose
  `crossReferences` are term-anchored, exactly as `defined-term-use`'s do, so the vocabulary is
  still read out of the map and no second list is kept in step.
- `column` is a **mechanism parameter**, precisely as `vocabularyFrom` is for `defined-term-use`.
  The protocol's shape is a list of mechanism objects each carrying its own parameters, and that
  shape does not change. **No protocol field is added, and no new document.**

H2 said the shape would hold and only the vocabulary would grow. That is what happened, by one
member.

### 3. The detector reads the context, never the prose

An entry is examined **only** when its citation names a cell in the declared column — 0035's
`§ 172.101 table 3, row [column 2 = "Acetal"], column 7`. Everything else in the map is not read
at all: another column of the same row, a paragraph of prose, a heading. Tokens are separated by
comma and whitespace, because that is how the corpus prints a cell holding several.

So the same characters in another column are not a pointer, which is the whole proposition and is
what the two measured false positives become. A token in the pointer-bearing column that the
vocabulary does not declare is **reported**, not dropped: it is either a pointer nobody recorded
or a vocabulary that is short, and both are findings.

This is deliberately **not** a regex over arbitrary prose. A mechanism that scanned the corpus's
words for code-shaped tokens would reproduce the failure that forced this decision.

## What was rejected

**An `equations` modality for `adapterReach`.** #284's second finding does not survive contact
with the map. § 172.102 serves TP1's and TP2's formula as
`<MATH><img src="/graphics/en21jn01.000.gif"/></MATH>` — the `MATH` element holds only an image,
and the text walk reads the empty string where the rule is. That much is confirmed. But
`illustrations: "unsupported"` is documented as *"the mapper cannot inspect it at all and an entry
that needs it is `beyondAdapter`"*, which is exactly true of a formula served as a GIF; and
`beyondAdapter.modality` is deliberately **not** a closed vocabulary
([0004](0004-adapter-reach-is-a-property-of-the-entry.md)), so the entry says
`modality: "equation"` with no change anywhere.

Tested rather than argued: such an entry passes `check-map.py` clean, 10 ok and 0 failed. **Two
concepts were predicted and one was forced.**

## Consequences

- **`POINTER_MECHANISMS` gains one member**, and `DETECTED_HERE` gains it too: the mechanism is
  detected by the mapper rather than elsewhere, so a protocol declaring it is obliged to fire.
- **No committed corpus moves.** None declares `coded-pointer`, and `defined-term-use`'s
  behaviour is untouched. One refusal message changed wording, because two mechanisms now read a
  vocabulary where one did.
- **`column` is refused on any other mechanism**, and `coded-pointer` without a `column` is
  refused — without it the mechanism would be the scan this decision exists to avoid.
- **H2 is decided**: existing vocabulary insufficient, protocol shape holds, one mechanism forced,
  the equation proposal rejected by evidence.
