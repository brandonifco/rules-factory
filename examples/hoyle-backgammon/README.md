# Trial: the method by hand, against Hoyle's Backgammon

Second run of [the method](../../docs/method.md). Chosen to stress the opposite of what
[the FAA trial](../faa-part-107/README.md) stressed: dice instead of no randomness, turn
order instead of stateless evaluation, and a corpus written to be complete rather than one
written to set standards.

**Corpus:** *Hoyle's Games Modernized* (1909), Project Gutenberg eBook 39445. Public domain,
`pin-in-repo`, plain text.

**Slice mapped:** the Backgammon chapter, pages 271–280 — The Board and Men, Playing,
Bearing off the Men, and Hints for Play. The map declares that range as its `extent`, and
every page in it is reached by some entry's located evidence
([0009](../../docs/decisions/0009-absence-is-a-verdict-with-evidence.md)). Hints for Play was
excluded as advice until #20; its advice still is, and the throw enumeration inside it is
not.

**Result, as first mapped:** 24 entries. 5 values, 19 operations. 22 clear, 2 ambiguous. 3
declined.

**Result today:** 30 entries. 9 values, 20 operations, 1 assertion. 25 clear, 5 ambiguous. 3
declined. The difference is corrections, not a wider slice: `player-count`,
`point-designations` and `direction-of-travel` are rules the first pass read past
([#13](https://github.com/brandonifco/rules-factory/issues/13)); `inner-table-handedness` and
`agreed-backgammon-multiple` were split out of entries that held two facts
([0004](../../docs/decisions/0004-adapter-reach-is-a-property-of-the-entry.md),
[0005](../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md)); and
`legal-destination`, `enter-from-bar`, `full-table-suspension` and `game-value` moved from
`clear` to `ambiguous` under
[0006](../../docs/decisions/0006-the-general-rule-governs-entry-and-full-means-adversely-full.md)
and [#14](https://github.com/brandonifco/rules-factory/issues/14); and `die-faces` is the
corpus's only statement of how many faces a die has, which sat unmapped inside the section
the map had excluded wholesale
([#20](https://github.com/brandonifco/rules-factory/issues/20),
[0009](../../docs/decisions/0009-absence-is-a-verdict-with-evidence.md)).

## Against the first trial

| | Part 107 | Backgammon (as mapped) | Backgammon (today) |
|---|---|---|---|
| Entries from the slice | 24 | 24 | 29 |
| Ambiguous | 5 (21%) | 2 (8%) | 5 (17%) |
| Slice as share of corpus | 11% | **1.1%** | 1.1% |
| Locator grammar | designation — `§ 107.51(b)(2)` | **page** — `Playing / p. 273` | page — `Playing / p. 274` |
| Randomness | none at all | central | central |

The ambiguity rate was the finding, and the third column is what became of it. A regulator
writes standards on purpose and expects a human to apply them; a games author is trying to
settle every case at the table. That argument survives — 17% is still below 21% — but **most of
the gap the trial reported was not a property of the genre. It was three contradictions and a
gap nobody had noticed yet**, and 8% was a measurement of the mapper. The method should expect
genres to differ, and should expect a low ambiguity rate on a first pass to be the least
trustworthy number a trial produces.

The locator grammar row moved too. Six entries cited `p. 273` and are on `p. 274`; thirteen
citations in all were wrong by a page or two, and none was caught until `evidence` held a span a
checker could find ([#18](https://github.com/brandonifco/rules-factory/issues/18)).

The two locator grammars together are the strongest evidence yet for keeping citations
opaque to the kernel. The same pipeline addressed both with no special-casing.

Randomness validates the kernel's optional-randomness decision **from both directions**:
one corpus draws nothing, the other cannot be modelled without dice.

## What this corpus broke

### 1. A rule can live in an image — and the rule we said did, does not

> **Corrected 2026-09-13.** This section originally said the starting arrangement is stated
> as *"with the men placed as in Fig. 1."* That was a misreading, and it is the single worst
> error this trial produced. The arrangement is stated in prose on p. 273, completely, and
> over-determined three further ways. The sentence quoted is real but belongs to a different
> paragraph about a different fact. See the amendment to
> [0004](../../docs/decisions/0004-adapter-reach-is-a-property-of-the-entry.md) and
> [#12](https://github.com/brandonifco/rules-factory/issues/12).

What survives is the finding, on a different entry. The **handedness of a physical board** —
which compartment is the inner table — is stated once and only as a reference to the figure:

> Which of the two is for the time being the inner and which the outer table is governed by
> the arrangement of the men at starting. **With the men placed as in Fig. 1, the right hand
> is the inner or home table**, and the left hand consequently the outer table.

That is `MissingRulesData` of a kind the first trial did not produce. There the missing data
lived in **another corpus** (49 CFR 171.8, the Air Almanac). Here it lives in **another
modality of the same corpus**.

That matters because the manifest's `references` list, added after the first trial, does not
help: there is nothing to reference. What determines reachability is the **adapter**, and
the map had no way to say "this entry is beyond what the declared adapter can read."

*Resolved.* [0004](../../docs/decisions/0004-adapter-reach-is-a-property-of-the-entry.md)
adds `beyondAdapter`, now carried by `inner-table-handedness`, split out of `board-tables`.

**Two things this trial got wrong about its own best finding, both worth keeping.** The
instance is inert — an engine that models positions player-relatively never asks for the
handedness, so the field's only confirmed use is one nothing consumes. And the original
entry said *"Cannot be evidenced from this corpus"* about a rule the corpus states four
times over, which no field on a map could have caught, because it is a fact about where a
human stopped reading.

### 2. `dependsOn` conflates two different orderings

Bearing-off rules apply only once every man is home. Entry from the bar applies only while a
man is on the bar. These are **runtime preconditions**.

`dependsOn` means something else: the order in which entries must be *implemented*. The two
usually coincide and here they do not — `bearing-off-highest` depends on
`bearing-off-move-or-remove` for implementation, and separately is unreachable until a phase
condition holds.

A stateless corpus hides this. Part 107 evaluates one flight against a set of limits and
never asked the question. Any corpus with turn structure asks it immediately.

*Resolved.* [0003](../../docs/decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md)
adds `gatedBy`, an array of entry ids and nothing else. Six entries in this map carry it:
three gated by `enter-from-bar`, three by `bearing-off-eligible`. Filling it showed that the
gate relation is not recoverable from `dependsOn` — `bearing-off-doublets` has six
implementation ancestors and one gate, and `move-by-pip` is gated by an entry that is
neither its ancestor nor its descendant.

### 3. Non-normative text sits inside normative sections — and normative text inside advice

*Hints for Play* is plainly advice, and was excluded **as a whole section**. But "it is always
an object to do this" sits in the middle of the Playing rules, and "as may be desirable" in the
middle of bearing off.

`scope` operates on entries. There is no mechanism for a sentence of advice inside a rule, and
an agent enumerating mechanically will either map it as a rule or silently drop it. Dropping it
is right; doing so silently is not.

**The mirror image is worse, and it is what excluding by section cost.** Inside *Hints for
Play* sits the only statement in this corpus of how many faces a die has: *"We will go
seriatim through all the possible throws"*, followed by twenty-one of them — nineteen
headings, because SIX TROIS, SIX QUATRE and SIX CINQUE share one — and an unordered pair over
*n* faces has *n(n+1)/2* throws, which equals 21 for exactly one positive *n*. The normative
sections never say. `DicePair.OfSixes` was an engine assumption with no mapped authority
([#20](https://github.com/brandonifco/rules-factory/issues/20)).

[0009](../../docs/decisions/0009-absence-is-a-verdict-with-evidence.md) rules that `scope` is
decided per rule and a section has no scope of its own. `strategy-advice` declines the advice;
`die-faces` is `scope: in` and cites the same section. What makes "no entry anywhere cites this
section" a fact rather than a hope is the map's declared `extent`: pages 278–280 held the
enumeration and no entry's evidence reached them.

### 4. The corpus bounds the engine, not the subject

This text predates the doubling cube. A modern player would call an engine built from it
incomplete, and they would be right about the *game* and wrong about the *engine*: the rule
is not in the corpus, so it is not in the map.

`doubling-cube` is recorded rather than omitted, because "absent from the corpus" and "nobody
looked" must not be indistinguishable. **An engine built from a 1909 corpus is a 1909 engine**,
and the map is what makes that legible rather than embarrassing.

It took two goes to record it honestly. The first spelled it `scope: out` with the citation
`(absent)`, which is the same two words as "we read this and declined it" plus a locator that
cites nothing — and `check-locators.py` had to special-case it, so the gate's "all 29 checked"
verified twenty-eight
([#29](https://github.com/brandonifco/rules-factory/issues/29)). It now carries
[`absentFrom`](../../docs/decisions/0009-absence-is-a-verdict-with-evidence.md), names four
terms the corpus would use if it had the rule — none of which occurs in pages 271–280 — and
cites and quotes the passage the rule *would* be in: the sentence that enumerates the apparatus
and closes the list.

### 5. Delegation to a person, confirmed in a second genre

A backgammon pays *"either thrice or four times (as may have been agreed)."* The corpus is
entirely clear; it simply assigns the figure to the players.

This is the same shape as Part 107 delegating a safety judgement to the pilot — a regulator
and a Victorian games author reaching the same construction. Two independent instances in
two genres is good evidence that `kind: assertion`, added after the first trial, is a real
category and not an artifact of reading regulation.

### 6. Hash derivation, confirmed independently

The pinned hash covers the Gutenberg text *including* its licence header and footer — some
20 KB of boilerplate that is not the work. `work-text-only` would produce a different digest
for identical rules.

Second corpus, second confirmation that a digest alone does not say what it covers. Recorded
honestly as `gutenberg-plain-text-including-boilerplate`.

### 7. A corpus can be overwhelmingly irrelevant to its engine

1.1%. The first trial was 11%.

`pin-in-repo` committed 740 KB to make 8 KB reproducible. Correct, and worth noticing: at a
larger ratio, boundary policy and extraction strategy start to interact, and "commit the
corpus" stops being obviously free.

## What it means for the kernel

Again, nothing. `MissingRulesData` covered a rule locked in an illustration as naturally as
one locked in another title of the CFR. The five reasons have now absorbed two corpora a
century and a subject apart without strain.

## What it means for the factory

Findings 1 and 2 are schema changes. Finding 3 is a method change. Finding 4 is a paragraph
the method was missing and the map already supported. All four are cheap now and would be
expensive after tooling reads the map.

Findings 1 and 2 have since been decided —
[0004](../../docs/decisions/0004-adapter-reach-is-a-property-of-the-entry.md) and
[0003](../../docs/decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md) — and this
map is written against the result. Finding 3 remains a method change with no field behind
it: `scope` still excludes an entry and not a sentence.
