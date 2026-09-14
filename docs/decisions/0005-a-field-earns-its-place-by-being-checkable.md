# 0005 — A field earns its place by being checkable, not by naming a distinction

## Status

Accepted — 2026-09-14. Revised before acceptance after adversarial review, which found the
four substantive moves sound and the argument for three of them wrong. The revision is
recorded rather than rewritten away: see *What the first draft got wrong* at the end.

## Context

[#24](https://github.com/brandonifco/rules-factory/issues/24) collected five open issues that
turned out to be one question. Six situations arise in which a map entry is not a plain
implementable rule, and three fields — `clarity`, `status`, and the `ambiguity` block — are
being asked to carry all six between them.

The instinct is to add carriers until each situation has one. The right test is narrower, and
it is the one 0003 and 0004 actually applied: **a field earns its place by being checkable.**
0004 rejected a reason-string because "a convention no check can read is one nobody can be
shown to have broken"; 0003 rejected prose for the same reason. Checkability, not runtime
behaviour — `dependsOn` is explicitly *not* a runtime precondition, `name` and `evidence` have
no runtime role at all, and 0004 itself concedes that `beyondAdapter`'s only confirmed
instance is inert. A "must be load-bearing at runtime" standard would condemn half this
schema.

So the question is not how many kinds of sentence there are. It is: **for each situation, what
could a check read, and what would it compare it against?**

### How the maps got this way

Not by ignoring the spec. `docs/method.md` contradicts itself. Phase 3 (`:149-152`) says a
deliberately delegated judgement is an assertion. Phase 4 (`:205-212`) says the opposite — "A
standard is not a gap… its fate is **almost always a runtime unresolved**" — and names three of
the four entries at issue. A mapper following Phase 4 produced exactly what the maps contain.
That is a better account than "the maps are behind the schema," and it means the fix is in the
method, not only in the data.

### The six, and what a check could read

**1. The corpus did not say.** A genuine gap. `RequiresInterpretation`. `clarity: ambiguous`,
`fate: unresolved`. Already correct and already checkable.

**2. The corpus deliberately delegated.** `well clear`, `reasonable protection`, `a flash rate
sufficient`, *"either thrice or four times (as may have been agreed)"*. The corpus is not vague;
it named who decides. The engine's obligation is `kind: assertion`'s four words — demand,
attribute, record alongside the outcome, never infer — and that is a **required input**, not an
unresolved result.

**3. Defined in a corpus we did not admit.** `MissingRulesData`. A check can read an id and
resolve it against the manifest's `references`.

**4. In a modality our adapter cannot read.** `MissingRulesData`. `beyondAdapter`, settled in
[0004](0004-adapter-reach-is-a-property-of-the-entry.md). A check resolves the adapter against
the manifest.

3 and 4 share a runtime and have **nothing in common to check**. That is why they are two
fields and not one — see Alternatives.

**5. The corpus said it twice, differently.** `clear` asserts "the corpus determines exactly one
answer for every valid input" (`corpus-map.md:64`, and `method.md:176` says *the corpus*, not
*the passage*). A corpus that contradicts itself does not. **A conflict is `ambiguous` under the
existing definition**, and conflict and vagueness genuinely do want the same runtime — the
kernel's enum has no value for "the corpus disagrees with itself" and should not gain one.

**6. Clear, correct, and the opposite of what a reader expects.** Nothing here is checkable
*until the entry names the test that distinguishes the two readings*. A `surprising: true` flag
is unfalsifiable. The test is not.

### What is actually missing

One thing. `must-play-whole-throw` implements the rule and declines **one stated case**
(`LegalPlays.For` declines only where two maximal plays are incomparable). The spec forces
`fate: unresolved` to imply `status: declined`, which is false.

Two fields were coupled that answer different questions: `status` is a fact about **the entry's
implementation**; `fate` is a fact about **a case's runtime**.

## Decision

**Three corrections of misuse, one decoupling, one new field, one rail. No new vocabulary for
uncertainty.**

### A. A deliberately delegated judgement is an assertion — **and it is an entry**

Not "the entry containing it is an assertion." `kind` is entry-level, and in two of the four
Part 107 cases the delegated standard is one clause of an otherwise computable rule:

- `night-operation` — the standard is "flash rate sufficient"; the rest is computable, and the
  entry's own `evidence` says so ("Night with training and lighting; night without either; and
  the § 107.65 training date boundary of April 6, 2021"). Reclassifying the entry destroys the
  computable half and demands an input no caller can supply: *"was my night operation lawful"*
  is the question, not the input.
- `over-human-beings` — its `question` carries **two** causes: *"'Reasonable protection…' is a
  judgement; **and (c) defers to subpart D, which this map has not covered**."* The second has a
  different runtime reason entirely — `subpart-d-categories` is `scope: out`, i.e.
  `OutsideCurrentScope`. One row per entry leaves nowhere for it to go. (The 2020 copy of this
  entry has only the first cause and does *not* break — so the correction is right for one copy
  of an entry and wrong for the other, which no migration written from the first draft would
  have caught.)

The fix is the map's own established pattern: `speed-limit` (value) + `speed-within-limit`
(operation, `dependsOn: [speed-limit]`), which `corpus-map.md:281-285` names as the granularity
finding that mattered. **The standard becomes its own `kind: assertion` entry** —
`well-clear`, `reasonable-protection`, `flash-rate-sufficient` — and the operation `dependsOn`
it. Every entry then has one runtime reason again.

What this costs and what it buys, concretely: read as an ambiguity, `stake-multiplier` makes the
engine return `RequiresInterpretation` and **throw away a rule the corpus states** — that the
multiplier is three or four and nothing else. Read as an assertion, the bound survives into the
signature.

**Scale.** Eight entry instances across three maps, in four repositories' copies — not the
"four across two trials" #6 counted before trial 3 existed:

| map | entries |
|---|---|
| 2026 Part 107 | `night-operation`, `right-of-way`, `collision-hazard-proximity`, `over-human-beings` |
| 2020 Part 107 | `right-of-way`, `collision-hazard-proximity`, `over-human-beings` |
| backgammon | `stake-multiplier` |

**Ruled on explicitly, because a migrator will hit it:** `moving-vehicle-operation` ("Part 107
does not define 'sparsely populated area'") looks identical in the map and is **situation 1, a
gap**.

**Amended 2026-09-14, during the migration this decision ordered.** The draft gave the test as
*whether the corpus names a decider*. It does not discriminate: § 107.37 writes "unless **well
clear**" and § 107.29(a)(2) "a flash rate **sufficient** to avoid a collision" naming no decider
at all — no more than § 107.25 does for "sparsely populated area". All three would fail the
test as stated, and two of them are the cases this correction exists for.

The test that actually separates them: **a delegated standard states a standard of conduct the
subject must meet; a gap leaves a factual predicate undefined and vests it in nobody.** "Well
clear" tells an operator what to achieve, and the operator asserts they achieved it. "Sparsely
populated" tells nobody to do anything; it is a condition the corpus uses and never defines, so
an engine does not even know what it would be demanding.

This is the same failure the draft records about itself below — a right ruling with a wrong
argument — found for the third time by someone checking rather than reading. The residual case
is genuinely unsettled and is filed rather than waved at: a world fact an *operator could
perfectly well assert* sits close to a gap, and `corpus-map.md` separately says facts about the
physical world are consumed rather than derived.

**A does not close [#11](https://github.com/brandonifco/rules-factory/issues/11).** #11's
acceptance is that *every* entry that is a fact only a caller can supply is `kind: assertion`,
and `visual-line-of-sight`, `preflight-actions` and `visual-observer-conditions` are still
`operation` with an explanatory note. Those are facts-a-person-asserts, not delegated
standards. #11 stays open with the remainder named.

### B. A corpus that contradicts itself is `clarity: ambiguous`

The `ambiguity.question` states both readings; `fate` records which governs, or declines.

**B does not close [#19](https://github.com/brandonifco/rules-factory/issues/19)** — it makes
the classification available for someone to close it. #19 involves a third entry
(`full-table-suspension`), whose reading decides whether `Game.Play`'s `UnsupportedInteraction`
branch is live code or dead, and requires a test with an own-held point in the adversary's home
table.

Two things B cannot do as written, recorded rather than hidden:

- **A conflict is a property of a pair, recorded on entries.** Nothing links them or keeps
  their `fate` in step. Rule: where both carry `fate: decision`, the decision id must be the
  same on both. That is checkable and closes the hole.
- **"Cites both passages" has nowhere to go.** `locator` is singular and required. Either the
  `ambiguity` block gains a citation list, or the second citation stays prose — which is what
  0003 and 0004 both rejected. **Left open deliberately**, because deciding it from one instance
  is the mistake 0004 avoided with `modality`.

### C. `status` and `ambiguity.fate` are decoupled

`status` answers *has the engine built this entry*. `fate` answers *what happens at runtime when
the declining case is reached*. `implemented` + `fate: unresolved` is legal and means "built,
and declines the stated case." `declined` is reserved for an entry with **no implemented path at
all**.

**The conformance verdict covers every case except the one `ambiguity.question` names, and the
declining case ships a test.** Without that sentence, C legalises a combination `corpus-map.md`
says requires a verdict, over a case that has none. (Separately: the map has no field for the
verdict at all — only `implementedIn` — so that requirement is currently unenforceable across
all 26 `implemented` entries. Pre-existing; C is the moment it becomes load-bearing.)

**What C costs.** After it, `fate: unresolved` means "returns `RequiresInterpretation` for **at
least one** input", not "for every input", and nothing distinguishes `must-play-whole-throw`
from an entry that declines everything. That is a real loss of the totality claim and it is the
price of the decoupling.

### D. A new field `definedElsewhere`, parallel to `beyondAdapter`

```json
"definedElsewhere": { "reference": "49-cfr-171-8" }
```

The id must resolve in the manifest's `references`, exactly as `beyondAdapter`'s adapter must.
This relieves the `ambiguity` block of duty as a general decline carrier. Closes
[#10](https://github.com/brandonifco/rules-factory/issues/10).

**Exclusion rule, so rows cannot double-fire:** no entry carries `definedElsewhere` or
`beyondAdapter` *and* an `ambiguity` block. This is #10's own acceptance criterion — no
`ambiguity` block while `clarity` is `clear` — restated as a check.

### E. Surprise gets a rail, and the entry names its test

An entry whose correct reading diverges from what a competent reader would assume ships with a
**test that fails under the assumed reading**, and **the entry names that test**. Naming it is
what makes the rail checkable rather than an exhortation: `bearing-off-highest` points at the
one case in 167 where Hoyle's rule and the modern rule differ.

### The correspondence table, with precedence

A runtime reason is derivable from `scope`, `status`, `kind`, `fate`, `definedElsewhere` and
`beyondAdapter`. **Rows are checked in order and the first match wins** — not-in-scope and
not-built dominate; the remaining rows describe what a *built* entry returns.

| # | A map entry that is… | At runtime the engine returns… |
|---|---|---|
| 1 | `scope: out` | `OutsideCurrentScope` |
| 2 | `status: mapped` or `blocked` — read, not built | `UnsupportedRule` |
| 3 | carries `definedElsewhere` | `MissingRulesData` |
| 4 | carries `beyondAdapter` | `MissingRulesData` |
| 5 | an `operation` whose `value` dependency is unimplemented | `MissingRulesData` |
| 6 | `ambiguity.fate: unresolved` | `RequiresInterpretation` |
| 7 | two implemented entries with no entry for their combination | `UnsupportedInteraction` |
| 8 | `kind: assertion` | **nothing — the engine demands the value and proceeds** |

Precedence is not cosmetic. Without it, every `status: mapped` entry with `fate: unresolved`
matches rows 2 and 6 — six entries in the 2026 map, five in the 2020 map — and
[#21](https://github.com/brandonifco/rules-factory/issues/21)'s check is unwritable in either
direction.

Row 8 is the point of correction A. An assertion is not a failure to resolve; it is a parameter.

## Alternatives considered

**A `fate` vocabulary of six, one per case.** Rejected. Two of the six have nothing a check
could read — `surprising` is unfalsifiable, and `delegated` is already `kind`. It also leaves
the `status`/`fate` coupling, the one real defect, untouched.

**Merge `definedElsewhere` into `beyondAdapter` under one field with a discriminator.** Argued
and rejected. A single `unreadable: { kind, adapter, modality, reference }` has two payloads
with nothing in common, so half the object is always absent and the check becomes conditional
on the discriminator. Two fields whose required contents each resolve against the manifest are
strictly more checkable — and 0004's closing paragraph already pointed here.

**Split `must-play-whole-throw` into an implemented entry and a declined one.** Rejected,
though it is the purist reading of 0001. The declining case is the same rule at a boundary;
splitting it puts one sentence of the corpus under two ids, which makes `locator` ambiguous.

**Keep `RequiresInterpretation` for delegated standards and widen its documentation** (#6's
option 2). Rejected: it is the status quo, and the `stake-multiplier` case shows it is lossy.

**`surprising: true`.** Rejected under E: unfalsifiable.

## Consequences

**The migration is larger than the first draft said.** Eight entry instances for A, plus new
assertion entries for the standards they depend on, across three maps in four repositories'
copies ([#17](https://github.com/brandonifco/rules-factory/issues/17)).

**`method.md` Phase 4 must be rewritten**, not only extended for E. It currently states the
position this decision rejects, and it is where the misclassification came from.

**Trial 3's headline finding must be restated, not deleted.** `night-operation` is the *only*
instance of "clarity belongs to a version of the corpus, not to a rule", asserted in
`method.md`, the temporal trial's README, and the trial log. Under A the 2026 entry is no
longer `ambiguous` and the finding has zero instances. The finding survives in a better form:
**an amendment can turn a rule the engine computes into one that demands a caller's
assertion.** Still a change the engine cannot make on its own; still evidence that a map is a
statement about one text.

**`hoyle-backgammon`'s migration is bigger than "an overload already anticipates it".**
`Outcome.Pays(GameValue)` must go — a source-breaking removal from a shipped public type with
tests on it. And `Pays(GameValue, int)` takes a bare `int`, which satisfies *demand* and
*never infer* but not *attribute* and *record alongside the outcome*. The honest landing is an
attributed-assertion parameter type, shaped like `AssertedPosition`. Also: the engine's map
copy is hash-pinned in `corpus-manifest.json`, so the pin updates in the same commit or the
gate fails on day one.

**Three things the migration must fix that this decision did not create:**

- **Four Part 107 entries have an elsewhere-defined *input*, not an elsewhere-defined *rule*.*
  `airspace-authorized` and `restricted-area-permitted`, in both maps: the rule is fully
  implementable and one input comes from outside. `definedElsewhere` is wrong for them and
  would not validate anyway — there is no airspace corpus in the manifest to name. They are
  `kind: assertion` per `method.md:154-156`, facts about the world the engine consumes. Same
  shape as A: an operation depending on an assertion.
- **`direction-of-travel` was `kind: "rule"`**, outside the closed vocabulary, in both copies of
  the backgammon map — introduced yesterday and caught by this review. Nothing checked `kind`
  because nothing consumed it; row 8 makes it load-bearing for the first time. Corrected in the
  factory copy; the engine copy follows with the migration.
- **`game-value` is the live #21 violation**: `clarity: clear`, no `ambiguity` block,
  `status: implemented`, while `Outcome.ValueOf` returns `RequiresInterpretation` citing it. It
  is situation 1 misrecorded as no situation, and it is the entry #21's check is guaranteed to
  fail on first.

**What this does not settle.** E makes the rail checkable *once an entry names its test*, and
nothing can detect a surprising entry whose author never noticed it was surprising. That is the
same class as a mapper who stopped reading (0004's amendment,
[#20](https://github.com/brandonifco/rules-factory/issues/20)), and no field has ever reached
it.

**The evidence base is two corpora and three mapping trials plus one build.** The argument for
deciding now is that the trials stopped producing new *kinds* — only new instances. That is not
proof. A regulation engine ([#3](https://github.com/brandonifco/rules-factory/issues/3)) is the
next thing likely to falsify it, and it is being built next on purpose.

## What the first draft got wrong

Recorded because this project's rule is that a correction is more useful than a clean record.

- **The test.** The draft said a field earns its place by being *load-bearing at runtime*, and
  quoted 0004 saying `beyondAdapter` earned its place that way — while omitting that 0004
  immediately qualified it, and that `hoyle-backgammon`'s gate contains a check whose entire
  purpose is to prove nothing ever calls `BeyondAdapter`. Under that standard `dependsOn`,
  `name`, `evidence` and `implementedIn` would all fail. The real standard is checkability, and
  E's conclusion is *stronger* under it.
- **"Never from `status`."** The draft gave that as the reason the table becomes checkable,
  and then wrote two rows keyed on `status`. The table is checkable because the *fate* row no
  longer has to be read through `status` — and because the rows are now ordered.
- **The title.** *One carrier per runtime behaviour* is a slogan the draft's own Decision
  section broke, by adding `definedElsewhere` alongside `beyondAdapter` for one behaviour. The
  rule actually applied is one carrier per (behaviour × independently checkable evidence),
  which admits `definedElsewhere` and still excludes `surprising`.

In all three the decision survived and the argument did not — the third time that has happened
in this project, and the reason the reviews keep being worth their cost.
