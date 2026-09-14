# 0005 — One carrier per runtime behaviour, not one per prose distinction

## Status

Proposed — 2026-09-14.

## Context

[#24](https://github.com/brandonifco/rules-factory/issues/24) collected five open issues that
turned out to be one question. Six situations arise in which a map entry is not a plain
implementable rule, and three fields — `clarity`, `status`, and the `ambiguity` block — are
being asked to carry all six between them.

The instinct is to add carriers until each situation has one. That is the wrong test. This
project's standing test for a field is whether the distinction is **load-bearing at runtime**:
`beyondAdapter` earned its place by mapping onto `MissingRulesData`, not by being a distinct
kind of sentence. Applying that test to the six collapses the problem sharply.

### The six, and what each actually does at runtime

**1. The corpus did not say.** A genuine gap. The engine declines with
`RequiresInterpretation`. `clarity: ambiguous`, `fate: unresolved`. Already correct.

**2. The corpus deliberately delegated.** `well clear`, `reasonable protection`, *"either
thrice or four times (as may have been agreed)"*. The corpus is not vague here; it named who
decides. **The runtime behaviour is not an unresolved result at all** — it is a required
input. The engine demands the value, attributes it, records it alongside the outcome, and
never infers it.

That is `kind: assertion`, which already exists and already says exactly this. #6 offered
three options and worried that `well clear` was not like *"if the pilot determines"* because
"nobody asserts it, a court decides it". On inspection they are the same shape: the operator
asserts they remained well clear, and a reviewer may disagree. The engine's obligation is
identical in both.

`stake-multiplier` shows what the misclassification costs. Read as an ambiguity, the engine
returns `RequiresInterpretation` and **throws away a rule the corpus states** — that the
multiplier is three or four and nothing else. Read as an assertion, the bound survives into
the signature. #11 is answered by the same stroke: the maps are behind the schema.

**3. The corpus said it in a corpus we did not admit.** `civil-twilight-alaska`,
`hazardous-material`. `MissingRulesData`.

**4. The corpus said it in a modality our adapter cannot read.** `inner-table-handedness`.
`MissingRulesData`. Settled in [0004](0004-adapter-reach-is-a-property-of-the-entry.md).

3 and 4 are **one runtime behaviour with two different pieces of evidence**, which is exactly
the shape `beyondAdapter` already has.

**5. The corpus said it twice, differently.** `enter-from-bar` names two legal destinations
where `legal-destination`, three sentences earlier, names three. This needs no new machinery
at all: the spec says `clarity: clear` asserts *"the corpus determines exactly one answer for
every valid input"*, and a corpus that contradicts itself does not. **A conflict is
`ambiguous` by the existing definition.** #19 is a misclassification, not a gap — and had the
entries been classified correctly, the `fate: decision` the engine silently made would have
had to be written down.

**6. The corpus said it clearly, and a reader will disbelieve it.** `bearing-off-highest`.
The runtime behaviour is *identical to any other clear entry*. By this project's own test it
earns no field.

### What is actually missing

One thing. `must-play-whole-throw` implements the rule and declines **one stated case**. The
spec forces `fate: unresolved` to imply `status: declined`, which is false — the engine
implements almost all of it. The map has no way to say "implemented, and declines a case."

This is not a sixth kind of uncertainty. It is two fields that were coupled and should not
have been: `status` is a fact about **the entry's implementation**; `fate` is a fact about
**a case's runtime**. An entry can be fully implemented and still have a declining path
through it, exactly as a function can be complete and still throw.

## Decision

**Three corrections of misuse, one decoupling, one new field. No new vocabulary for
uncertainty.**

**A. A deliberately delegated judgement is `kind: assertion`, never an ambiguity.** The four
entries across two trials that use `RequiresInterpretation` for a standard are reclassified.
`docs/corpus-map.md`'s `kind: assertion` section already says this; the maps did not follow it.
Closes #6 and #11.

**B. A corpus that contradicts itself is `clarity: ambiguous`.** The `ambiguity.question`
states both readings and cites both passages; `fate` records which governs, or declines.
Closes #19.

**C. `status` and `ambiguity.fate` are decoupled.** `status` answers *has the engine built
this entry* — `mapped`, `blocked`, `implemented`, `declined`. `fate` answers *what happens at
runtime when the declining case is reached*. `implemented` with `fate: unresolved` is legal
and means "built, and declines the stated case". `declined` is reserved for an entry with **no
implemented path at all**: scope out, or nothing reachable. Closes #15's first half.

**D. A new field `definedElsewhere`, parallel to `beyondAdapter`.** It names the manifest
`references` entry that holds the definition:

```json
"definedElsewhere": { "reference": "49-cfr-171-8" }
```

Checkable the way `beyondAdapter` is: the id must resolve in the manifest. Both fields map to
`MissingRulesData`; they differ only in what the reader is told is in the way. The
`ambiguity` block is thereby relieved of duty as a general decline carrier and goes back to
meaning what it says. Closes #10.

**E. Surprise gets a rail, not a field.** An entry whose correct reading diverges from what a
competent reader would assume ships with a **test that fails under the assumed reading**. The
artifact is the test, not the annotation: an entry claiming to be surprising with no such test
is claiming something unchecked, which is the failure mode this project keeps finding. Recorded
in `docs/method.md`, not in the schema. Closes #23.

### The correspondence table, rewritten

A runtime reason is derivable from `scope`, `kind`, `fate`, `definedElsewhere` and
`beyondAdapter` — and **never from `status`**, which is why the table could not previously be
turned into a check.

| A map entry that is… | At runtime the engine returns… |
|---|---|
| `scope: out` | `OutsideCurrentScope` |
| `status: mapped` or `blocked` — read, not built | `UnsupportedRule` |
| `ambiguity.fate: unresolved` | `RequiresInterpretation` |
| carries `definedElsewhere` | `MissingRulesData` |
| carries `beyondAdapter` | `MissingRulesData` |
| an `operation` whose `value` dependency is unimplemented | `MissingRulesData` |
| two implemented entries with no entry for their combination | `UnsupportedInteraction` |
| `kind: assertion` | **nothing — the engine demands the value and proceeds** |

The last row is the point of correction A. An assertion is not a failure to resolve; it is a
parameter. Every entry currently returning `RequiresInterpretation` for a delegated judgement
is an engine declining to do a job the corpus gave it the means to do.

This table is now writable as the check in #21.

## Alternatives considered

**A `fate` vocabulary of six, one per case.** Rejected. It is the obvious move and it fails
the project's own test: `surprising` and `delegated` have no distinct runtime, so two of the
six values would be annotation. It also leaves the `status`/`fate` coupling — the one real
defect — untouched, because that bug is not about how many kinds of uncertainty there are.

**Split `must-play-whole-throw` into two entries, one implemented and one declined.**
Rejected, though it is the purist reading of 0001's granularity claim. The declining case is
not a separate rule — it is the same rule at a boundary — and splitting it would put a
sentence of the corpus under two ids, which makes `locator` ambiguous and `dependsOn`
meaningless between them. The trial that produced this entry also produced the strongest
evidence yet that the decomposition granularity is right; this is not the place to weaken it.

**Keep `RequiresInterpretation` for delegated standards and widen its documentation** (#6's
option 2). Rejected: it is the status quo and it is lossy in a way the `stake-multiplier` case
makes concrete. An engine that declines where the corpus told it what to ask for is not being
careful, it is being unhelpful — and it discards whatever bounds the corpus *did* state.

**Add `surprising: true`.** Rejected under E. The honest artifact is a failing test.

## Consequences

**Three maps migrate**, in both copies (#17): both Part 107 maps and the backgammon map. The
reclassifications are behaviour-changing, not cosmetic — an entry moving from ambiguity to
assertion changes an engine's signature, and `hoyle-backgammon` has a shipped `Outcome.Pays`
overload that already anticipates it.

**#21's check becomes writable**, in both directions, against the table above.

**What this does not settle.** Correction E puts an obligation in the method and no mechanism
behind it: nothing can detect a surprising entry whose author did not notice it was
surprising. That is the same class of failure as a mapper who stopped reading (0004's
amendment, #20), and no field on a map has ever been able to reach it. Stating it plainly here
so the rail is not mistaken for a guarantee.

**And the evidence base is two corpora.** Six situations, four trials, one built engine. The
argument for deciding now is that trials 3 and 4 produced no new *kinds* — only new instances
— which is the signal that the vocabulary has converged. It is not proof. A regulation engine
([#3](https://github.com/brandonifco/rules-factory/issues/3)) is the next thing likely to
falsify it, and it is being built next on purpose.
