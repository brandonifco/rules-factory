# Trial: the method by hand, against Hoyle's Backgammon

Second run of [the method](../../docs/method.md). Chosen to stress the opposite of what
[the FAA trial](../faa-part-107/README.md) stressed: dice instead of no randomness, turn
order instead of stateless evaluation, and a corpus written to be complete rather than one
written to set standards.

**Corpus:** *Hoyle's Games Modernized* (1909), Project Gutenberg eBook 39445. Public domain,
`pin-in-repo`, plain text.

**Slice mapped:** the Backgammon rules — The Board and Men, Playing, Bearing off the Men.
8,013 characters, **1.1% of a 740 KB corpus**. Hints for Play excluded as advice.

**Result:** 24 entries. 5 values, 19 operations. 22 clear, 2 ambiguous. 3 declined.

## Against the first trial

| | Part 107 | Backgammon |
|---|---|---|
| Entries from the slice | 24 | 24 |
| Ambiguous | 5 (21%) | 2 (8%) |
| Slice as share of corpus | 11% | **1.1%** |
| Locator grammar | designation — `§ 107.51(b)(2)` | **page** — `Playing / p. 273` |
| Randomness | none at all | central |

The ambiguity rate is the finding. A regulator writes standards on purpose and expects a
human to apply them; a games author is trying to settle every case at the table. Two genres,
two rates, and the method should expect them to differ rather than treat a high rate as a
mapping failure.

The two locator grammars together are the strongest evidence yet for keeping citations
opaque to the kernel. The same pipeline addressed both with no special-casing.

Randomness validates the kernel's optional-randomness decision **from both directions**:
one corpus draws nothing, the other cannot be modelled without dice.

## What this corpus broke

### 1. A rule can live in an image

The starting arrangement — without which no game can begin — is stated as *"with the men
placed as in Fig. 1."* It is fully determined in the corpus. It is unreachable by a
plain-text adapter.

This is `MissingRulesData` of a kind the first trial did not produce. There the missing data
lived in **another corpus** (49 CFR 171.8, the Air Almanac). Here it lives in **another
modality of the same corpus**.

That matters because the manifest's `references` list, added after the first trial, does not
help: there is nothing to reference. What determines reachability is the **adapter**, and
the map had no way to say "this entry is beyond what the declared adapter can read."

*Resolved.* [0004](../../docs/decisions/0004-adapter-reach-is-a-property-of-the-entry.md)
adds `beyondAdapter`, and `starting-position` carries
`{ "adapter": "plain-text", "modality": "illustration" }`. It no longer carries an
`ambiguity` block, because nothing about it was ambiguous.

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

### 3. Non-normative text sits inside normative sections

*Hints for Play* is plainly advice and is excluded as a whole section. But "it is always an
object to do this" sits in the middle of the Playing rules, and "as may be desirable" in the
middle of bearing off.

`scope` operates on entries. There is no mechanism for a sentence of advice inside a rule,
and an agent enumerating mechanically will either map it as a rule or silently drop it.
Dropping it is right; doing so silently is not.

### 4. The corpus bounds the engine, not the subject

This text predates the doubling cube. A modern player would call an engine built from it
incomplete, and they would be right about the *game* and wrong about the *engine*: the rule
is not in the corpus, so it is not in the map.

`doubling-cube` is recorded as `scope: out` with that reason rather than omitted, because
"absent from the corpus" and "nobody looked" must not be indistinguishable. **An engine built
from a 1909 corpus is a 1909 engine**, and the map is what makes that legible rather than
embarrassing.

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
