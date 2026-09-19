# 0046 — A passage may continue a definition through an explicit, structurally witnessed relation

## Status

Accepted — 2026-09-19. Records the decision on
[#321](https://github.com/brandonifco/rules-factory/issues/321), forced by trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)) after
[0043](0043-a-row-blank-in-the-column-that-names-the-row-above-is-named-below-it.md),
[0044](0044-one-printed-code-can-name-more-than-one-rule.md), and
[0045](0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md) were all in
force. It **extends 0044 and 0045** and leaves 0043's locator meaning unchanged.

## Context

§ 172.102 table 2 prints IB2 this way:

```text
IB2 | Authorized IBCs: Metal (31A, 31B and 31N); Rigid plastics (31H1 and 31H2); Composite (31HZ1).
    | Additional Requirement: Only liquids with a vapor pressure less than or equal to 110 kPa
      at 50 °C ... are authorized.
```

The two rows state two independently useful rules. The first says which IBCs IB2 authorises. The
second narrows those authorisations by vapour pressure. Trial 10 therefore maps them as two
entries.

Each existing decision is correct and, together, exposes a gap:

* **0043** can mechanically address the second row relative to the IB2 row, but explicitly says
  that address makes no claim that the row continues the anchor.
* **0044** says one printed term may name several defining entries and a pointer is complete only
  when it names all of them.
* **0045** says a direct `defines.term` is anchored by that term appearing in the defining
  entry's own evidence. The second row does not print `IB2`, so it correctly cannot directly
  declare `special-provision-codes / IB2`.

On main before this decision,
`defined_vocabulary(document, "special-provision-codes")["IB2"]` therefore contains only
`ib2-authorized-ibcs`. A column-7 pointer may voluntarily resolve IB2 to
`ib2-vapour-pressure-limit`, but deleting that second `resolvedBy` is clean because no
vocabulary obligation names it.

This satisfies [#265](https://github.com/brandonifco/rules-factory/issues/265)'s admission
standard. A real corpus now states a rule the contract cannot faithfully represent without either
losing the rule from the vocabulary or weakening an invariant that is still correct.

## Decision

### 1. `continuesDefinition` is a semantic relation, not another `defines`

An entry whose passage gives an additional rule under a term printed by another passage may carry:

```json
"continuesDefinition": {
  "definedBy": "ib2-authorized-ibcs",
  "anchor": {
    "sourceId": "cfr-49-172.102",
    "citation": "§ 172.102 table 2, row blank in column 1 below row [column 1 = \"IB2\"]"
  }
}
```

It means exactly:

> this entry states an additional defining rule for the one vocabulary term directly defined by
> `definedBy`.

The continuation does **not** state a vocabulary or a term of its own. Those are inherited from
the directly defining target. There is therefore no second registry and no term copied from
memory.

### 2. The target is deliberately narrow

For this version:

* `definedBy` names an entry in the same corpus;
* that target has exactly one **direct**, valid `defines` declaration;
* the continuation itself does not also carry `defines`;
* the target is not itself a continuation.

So continuation chains, cycles, one continuation extending several terms, and a target that
defines several terms are unsupported. No corpus has forced any of them. Several continuation
entries may name the same direct definition; 0044 already requires one term to retain every
defining entry.

### 3. The semantic claim has an independent structural witness

`anchor` is a locator, not evidence and not a second definition. It must name the continuation
entry's own passage in a form that also mechanically identifies the directly defining passage it
is under.

For the corpus that forced the concept, the witness is 0043's `row blank ... below row [...]`
selector. The section-designation locator check holds two facts:

1. the witness resolves to the **same table row** as the continuation entry's ordinary
   `locator`; and
2. the row named as the witness's `below row [...]` anchor is the **same row** as
   `definedBy`'s locator.

This is why IB3 can keep its better ordinary primary locator — its additional-requirement row has
a unique column-2 key — while the relation may still use the structural `below` selector as a
witness. 0043's rule that an ordinary row key is the preferred address is not changed.

A `continuesDefinition` whose locator grammar cannot establish such a witness is refused rather
than accepted on metadata alone. Supporting another structural witness waits for a corpus that
forces one.

### 4. The vocabulary reader follows the relation

The canonical contract reader first assembles direct definitions exactly as 0045 does. For each
well-shaped continuation whose `definedBy` target has exactly one direct definition, it adds the
continuation entry id to that target's `(vocabulary, term)`.

Thus:

```text
special-provision-codes / IB2
    ├── ib2-authorized-ibcs
    └── ib2-vapour-pressure-limit
```

and 0044 applies without modification: a coded pointer to IB2 is complete only when its
`crossReferences` name both entries.

### 5. Direct `defines` anchoring does not move

0045's validator remains unchanged: a direct `defines.term` still has to occur verbatim in that
entry's own evidence. A continuation is a different claim with a different mechanical anchor.

In particular, this remains invalid:

```json
"defines": [
  { "vocabulary": "special-provision-codes", "term": "IB2" }
]
```

on an entry whose evidence does not print `IB2`, even when its locator or continuation witness
mentions an IB2 row.

### 6. Schema version remains 1

The field is optional and additive. Every schema-version-1 map that does not carry it keeps the
same meaning and the same reader behavior. This follows the versioning treatment used when 0045
added optional `defines`; no existing representation is reinterpreted.


### 7. The Trial 10 blank-row reading is ambiguous in the corpus and decided in the map

The regulation never states in prose that a blank IBC-code cell continues the code printed on the
row above, and 0043 deliberately records that limitation. The repeated table pattern is nonetheless
strong enough to choose that reading for IB2 and IB3: otherwise each printed
`Additional Requirement` is an orphan restriction with nothing to qualify.

That means the two Trial 10 continuation entries remain `clarity: ambiguous` — a competent reader
can see that the source leaves the convention implicit — but their `ambiguity.fate` is
`decision`, naming **this record**. They do not remain `fate: unresolved`, and they carry no
`unresolvedReason`. A `continuesDefinition` is itself the semantic choice that the additional
rule belongs to the direct definition; asserting that relation while saying the same relationship
is unresolved is contradictory.

This correction was required by the independent review of PR #329. The reviewer agreed with both
IB2 and IB3 continuation relationships from the repeated table pattern, but rejected the first
implementation's simultaneous `continuesDefinition` plus `RequiresInterpretation` state.

The rule is intentionally narrow in this contract version: an entry carrying
`continuesDefinition` may not have `ambiguity.fate: unresolved`. No admitted corpus currently
forces the separate case where a continuation relationship is settled but an unrelated aspect of
that same entry remains open. If one does, it must force a representation that distinguishes those
questions rather than silently weakening this invariant.

## Mechanical invariants

Validation refuses a continuation when:

* the field or its `anchor` is malformed or has an unknown key;
* `definedBy` is absent, names itself, or names no entry;
* the target is in another corpus;
* the target has zero or more than one direct definition;
* the continuation also carries direct `defines`;
* the target is itself a continuation;
* the structural anchor is absent or names another source;
* the anchor does not resolve to the continuation's own passage;
* the anchor's structurally named defining row is not the `definedBy` passage.

A derived entry may not carry the field because it has no passage to anchor.

The validator can establish the relation's map-level shape and target. The corpus locator checker
establishes the two evidentiary/structural facts, as it already does for every locator.

## Rejected alternatives

**Weaken 0045 and allow `defines.term` to be found in the locator.** Rejected. A locator is an
address, not corpus evidence. This would recreate the synthetic vocabulary declarations 0045 was
written to prevent.

**Infer semantic continuation from every 0043 locator.** Rejected. 0043 deliberately separates
address from meaning, and blank-row adjacency is not universally semantic continuation.

**Use `dependsOn`.** Rejected. It means implementation order. The additional requirement does
depend on the authorisation rule, but many dependencies are not definition continuations; making
one imply the other conflates two relations.

**Use `crossReferences`.** Rejected. It records a pointer made by the current passage and is
anchored in words that point. The additional-requirement row does not print `IB2` and makes no
such pointer.

**Merge the two rows into one entry.** Rejected. The authorised-IBC list and the vapour-pressure
ceiling are distinct rules with distinct evidence and mutation behavior. Merging them makes rule
identity less faithful to the corpus in order to avoid representing the relationship between
them.

**A free-form `continuesDefinition: "id"` edge.** Rejected. It would let unrelated evidence
join a vocabulary by metadata alone, which is the same class of unanchored assertion 0045
refused.

**A generic evidence or semantic graph.** Rejected under #265. This corpus forces one
relationship and one structural witness, not arbitrary graph edges.

## Consequences

* Trial 10's IB2 additional-requirement entry can join `special-provision-codes / IB2` without
  printing or inventing `IB2`.
* The analogous IB3 additional-requirement entry can use the same relation while keeping its
  ordinary primary row key.
* Removing either continuation target from a column-7 pointer becomes a coded-pointer finding,
  through the existing 0044 completeness rule.
* Direct `defines`, `crossReferences`, `dependsOn`, and 0043 locators keep their existing
  meanings.
* The two Trial 10 continuation entries stay `clarity: ambiguous` but use
  `ambiguity.fate: decision` naming this ADR; they no longer return
  `RequiresInterpretation` for the association this relation has chosen.
* No support is added for continuation chains, multiple terms per continuation, non-local
  corpora, arbitrary semantic graphs, generic row grouping, or multi-span evidence.
