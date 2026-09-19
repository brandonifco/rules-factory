# 0045 — A vocabulary is distributed over the entries that define its terms

## Status

Accepted — 2026-09-19. Records the decision on
[#314](https://github.com/brandonifco/rules-factory/issues/314), found by trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)) on the first attempt to write
the map and before any entry was committed.

**Amends [0041](0041-a-coded-pointer-is-made-by-the-column-it-sits-in.md)** where it gives
`coded-pointer` the same `vocabularyFrom` `defined-term-use` has: a single entry that states the
corpus's terms. That part is falsified — the corpus that forced the mechanism prints no such
passage — and `coded-pointer` names a **vocabulary** instead. Everything else 0041 decided stands:
the pointer is made by the column the token sits in, `column` is a mechanism parameter, and the
protocol's shape does not change.

**[0026](0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)
is not amended.** Its anchoring rule — every `cites` appears verbatim in the evidence of the entry
that makes the reference — is correct and is what forced this decision rather than what obstructed
it. **[0044](0044-one-printed-code-can-name-more-than-one-rule.md) is not amended** either: a term
still names one or more defining entries, and here that cardinality stops being a special case and
becomes the ordinary result of two entries declaring they define the same term.

The specification is [mapper.md](../mapper.md#coded-pointer--a-pointer-its-column-makes) and
[corpus-map.md](../corpus-map.md#defines).

## Context

0041 gave `coded-pointer` a vocabulary the way `defined-term-use` has one:

```json
{ "mechanism": "coded-pointer", "column": 7, "vocabularyFrom": "column-7-codes" }
```

`protocol._check_vocabulary` resolves that id to an entry and reads its `crossReferences` as
term → defining entries. And `check-map.py --only cross-references` requires every `cites` to
appear **verbatim in that entry's own `evidence`**, with no exemption for any entry. So the
vocabulary entry has to be a passage that **prints the codes**.

**49 CFR § 172.102 prints no such passage.** Its codes are one per table row — `IB2 | Authorized
IBCs: …` — and one per provision paragraph. The nearest candidate is § 172.102(c), whose whole
text is:

> (c) Tables of special provisions. The following tables list, and set forth the requirements of,
> the special provisions referred to in column 7 of the § 172.101 table.

A `special-provision-codes` entry citing and quoting exactly that, and indexing the twenty codes:

```
X  special-provision-codes: crossReferences cites 'IB2', which does not appear in this entry's
   `evidence`; a reference is anchored to the passage that makes it
X  special-provision-codes: crossReferences cites 'T4', which does not appear in this entry's
   `evidence`; a reference is anchored to the passage that makes it
```

§ 172.101 column 6 is the same case: § 172.101(g) ends *"The codes contained in Column 6 are
defined according to the following table:"* and prints no code.

**Why it was not caught when 0041 was decided.** 0041 was measured with a proposition test over
synthetic documents and with `protocol.check`, neither of which runs the anchoring check, and the
ADR's example entry was never built. `defined-term-use`'s vocabulary had always satisfied the
anchoring rule by an accident of its one corpus: the SRD's `condition-list` quotes *"This glossary
defines these conditions: Blinded Charmed Deafened …"*, which prints all fifteen terms. **A corpus
whose index is a table, rather than a sentence, has no such passage**, and one entry per corpus
that happens to print everything is not a general property of a vocabulary.

## Decision

**A vocabulary is distributed over the entries that define its terms. A definition is anchored in
the defining entry's evidence; a `crossReference` remains anchored in the pointing entry's
evidence.**

### 1. `defines` — an optional, evidence-anchored declaration of the terms an entry defines

```json
"defines": [
  { "vocabulary": "special-provision-codes", "term": "IB3" }
]
```

For § 172.102:

```
ib2-authorized-ibcs             defines special-provision-codes / IB2
ib3-authorized-ibcs             defines special-provision-codes / IB3
ib3-authorized-large-packagings defines special-provision-codes / IB3
t4-portable-tank                defines special-provision-codes / T4
```

For § 172.101 table 1, the same shape over a different vocabulary:

```
class-3-flammable-liquid        defines hazard-label-codes / 3
class-8-corrosive               defines hazard-label-codes / 8
```

### 2. `coded-pointer` names the vocabulary, not an entry

```json
{ "mechanism": "coded-pointer", "column": 7, "vocabulary": "special-provision-codes" }
{ "mechanism": "coded-pointer", "column": 6, "vocabulary": "hazard-label-codes" }
```

The vocabulary is derived from the defining entries, `(vocabulary, term) -> one or more entry
ids`, and **a token of one vocabulary does not satisfy another because the text matches**: column
6's `3` is a hazard label and column 7's numeric codes are special provisions, and the two
mechanisms read two names. `vocabularyFrom` on a `coded-pointer` is refused, and `vocabulary` on
any other mechanism is refused: each names a different kind of vocabulary, and a mechanism reading
the wrong one would report a clean run over nothing.

### 3. 0044's cardinality is what falls out of it

```
special-provision-codes / IB3
    ├── ib3-authorized-ibcs
    └── ib3-authorized-large-packagings
```

No declaration is discarded and no entry states another entry's term. The pointing cell's
`crossReferences` are unchanged and still ordinary:

```json
{ "cites": "IB3", "resolvedBy": "ib3-authorized-ibcs" },
{ "cites": "IB3", "resolvedBy": "ib3-authorized-large-packagings" }
```

Both are anchored, because `IB3` really does appear in the column 7 cell's evidence. A coded
pointer is accounted for only when the entry names **every** defining entry of its token, which is
0044 unchanged.

### 4. `defines` does not imply a `crossReference`, and never will

Definition and reference are opposite directions and stay distinct. An entry that defines `IB3`
points at nothing by doing so; an entry that prints `IB3` in column 7 points at both definitions
and declares both. Deriving one from the other would make a defining entry assert a reference its
passage does not make, which is the thing the anchoring rule refuses.

### 5. What `--only defines` holds

Narrow and mechanical. `defines` is optional; when present:

1. it is a non-empty list;
2. each item holds exactly `vocabulary` and `term`;
3. both are non-empty strings;
4. `term` occurs **verbatim in that entry's own `evidence`**;
5. a derived entry may not carry it (`--only derived`, which refuses every passage field on one);
6. the same `(vocabulary, term)` declared twice on one entry is refused;
7. several different entries **may** define the same `(vocabulary, term)` — that is 0044's case;
8. a `coded-pointer` naming a vocabulary no entry defines is refused by `mapper protocol`;
9. a code in a pointer-bearing cell that no entry defines is reported, never dropped.

What it does not hold: that the passage really *defines* the term rather than printing it. That is
interpretive, as `unmapped` is, and the anchor is the mechanical part.

## What was rejected

**Exempting the entry a protocol names in `vocabularyFrom` from the anchoring rule** (#314's
option 1, the narrowest). A `special-provision-codes` entry whose evidence says only *"the
following tables list …"* and whose `crossReferences` invent twenty code names would be a
synthetic registry disguised as a corpus entry. The anchoring rule is the one thing standing
between a map and an index someone wrote from memory, and buying a mechanism with it is the wrong
trade.

**Several `vocabularyFrom` entries** (option 2). It does not solve the semantic problem by itself:
each named entry would still have to declare codes other than its own to be worth anything, and a
`crossReferences` item resolving to its own entry is refused outright.

**Dropping the central vocabulary** and reading each pointing entry's own `crossReferences`
(option 3). It loses 0044: with no vocabulary the detector cannot know that `IB3` names two rules,
so it cannot report the second target missing.

**Migrating the committed `defined-term-use` maps to `defines`,** to make the model uniform. Their
`vocabularyFrom` representation is valid where a real entry actually prints and indexes the terms,
which is exactly the SRD's case, and #265's standard is that a concept is added where a corpus
forces one. Both models are read, by two mechanisms that name their vocabulary two different ways,
so nothing is ambiguous about which is in force.

**Broadening this into a rewrite of 0026.** The anchoring rule is correct. This decision is about
`coded-pointer` being forced by a vocabulary the corpus distributes over its table.

## Consequences

- **Trial 10's protocol and map pass the complete validator**, not merely `protocol.check`. The
  integration regression 0041 lacked is
  [`tools/tests/mapper/test_distributed_vocabulary.py`](../../tools/tests/mapper/test_distributed_vocabulary.py),
  which runs the real § 172.101 / § 172.102 case — the seven settled rows, the corpus's own cell
  text, both columns and both vocabularies — through every check in `check-map.py` and through
  `mapper protocol`.
- **The old synthetic vocabulary entry still fails**, and is watched failing: an entry whose
  `crossReferences.cites` are absent from its evidence is refused exactly as it was before this
  change. Nothing here creates an exemption.
- **`check-map.py` gains one check**, `defines`, and the map gains one optional field. No
  committed map carries it, so every committed map's verdict is unchanged.
- **H2 is qualified rather than confirmed.** The `coded-pointer` concept is forced, the protocol's
  mechanism-list shape held, `pointerMechanisms` grew by one member — and the assumption that the
  new member could reuse a single `vocabularyFrom` entry is falsified, and the map contract needed
  one evidence-anchored declaration. `examples/hazmat-172-table/README.md` says so in those terms.
  A hypothesis kept clean by weakening `crossReferences` would have been the worse trial result.
