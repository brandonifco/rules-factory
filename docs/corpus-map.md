# The corpus map

The interface between reading a corpus and building an engine from it. Everything in
[method.md](method.md) phases 1–4 produces it; everything in phases 5–8 consumes it.

A map is a list of entries, one per rule the corpus states, plus the manifest of the corpora
they cite, plus a stamp naming the baseline it was built against:

```json
{ "schemaVersion": 1, "corpus": "cfr-14-107",
  "baseline": { "contentHash": "80f6bc4b…", "hashDerivation": "ecfr-versioner-xml",
                "asOf": "2026-01-01" },
  "entries": [ … ] }
```

The stamp is not decoration. A map is true of **one state of one corpus**. Without it, two
maps cannot be compared, a map cannot be checked against the text it claims to describe, and
it silently outlives that text. The third trial's differ printed `2020-01-01 -> ?` for
exactly this reason.

## Why it exists

Without it, "drop in a ruleset and let agents build the engine" has no interface. An agent
dispatched against a corpus has to decide what a unit of work is, re-read to find it, and
re-derive where it sits in the dependency order — every time, inconsistently. An agent
dispatched against a map entry has one concern, a citation, its dependencies, and a
statement of what evidence would settle it.

It also makes the decomposition *reviewable before any code exists*. A wrong map produces a
wrong engine efficiently; the cheapest moment to catch "this is two rules, not one" is
before either has been implemented.

## An entry

```json
{
  "id": "opposed-test-tie",
  "name": "Resolving a tie in an opposed test",
  "locator": { "sourceId": "core-rules", "citation": "Game Concepts / Tests / printed p. 36" },
  "kind": "operation",
  "scope": "in",
  "clarity": "ambiguous",
  "ambiguity": {
    "question": "The text does not say which side prevails when both achieve equal hits.",
    "fate": "decision",
    "decision": "docs/decisions/0007-opposed-test-tie-break.md"
  },
  "dependsOn": ["simple-test", "dice-pool-assembly"],
  "evidence": "Both tie directions, and the boundary where one side has one more hit.",
  "status": "implemented",
  "implementedIn": { "ruleset": "sr6", "version": 4 }
}
```

### Fields

| Field | Meaning |
|---|---|
| `id` | Stable slug. Referenced by `dependsOn`, by issues, and by the engine's own citations. Never reused. |
| `name` | What the rule is called, in the corpus's language where it has one. |
| `locator` | Corpus id plus a citation in that corpus's grammar. **Required.** An entry without one is not an entry. |
| `kind` | `value`, `operation` or `assertion` — a fact the corpus states, a procedure it describes, or a condition only the caller can supply. See below. |
| `scope` | `in` or `out`. Out is a recorded verdict with a reason, not an omission. |
| `clarity` | `clear` or `ambiguous`. `clear` asserts the corpus determines exactly one answer for every valid input. |
| `ambiguity` | Absent when clear. Otherwise the question, and its `fate`. |
| `dependsOn` | Entry ids. Determines backlog order — the sequence entries must be *implemented* in. **Not** a runtime precondition; see below. |
| `evidence` | What must be demonstrated. For a finite table: the whole table, not a sample. |
| `status` | See below. |
| `implementedIn` | The ruleset revision that implemented it. Set when status becomes `implemented`. |

### `kind: assertion`

Added after the first trial against a real corpus, where eight of twenty-four entries were
neither a value nor an operation.

An assertion is a condition the engine cannot evaluate: that a person could see the
aircraft, that communication was maintained, that a preflight check was performed, that a
pilot judged an action safe. These are real, binding rules — and no computation settles
them.

An engine owes an assertion four things: **demand it, attribute it, record it alongside the
outcome, and never infer it.** Defaulting an unasserted condition to true substitutes the
engine's judgement for a person's, silently, which is the failure the unresolved-result
contract exists to prevent in the other direction.

Two things that look like other kinds are assertions. Judgement the corpus *deliberately*
delegates ("if the pilot determines it would be in the interest of safety") is not
ambiguous — the corpus is entirely clear about who decides. And facts about the physical
world are consumed, not derived.

### `ambiguity.fate`

`decision` — the project rules on what the passage means, records it, and implements as
though the corpus had said so. `decision` names the record.

`unresolved` — the engine declines at runtime and returns `RequiresInterpretation`. Correct
when no reading is defensible enough to bake in, or when the choice belongs to the caller.

There is no third value. An implementer choosing a reading silently is the failure this
field exists to prevent.

### `dependsOn` is not a precondition

`dependsOn` orders *implementation*. A rule that applies only in a phase — bearing off
begins once every man is home; entry from the bar blocks every other move — has a **runtime
precondition**, which is a different fact and currently has nowhere to live.

The two coincide often enough to be confused, and a stateless corpus never distinguishes
them: a regulation evaluating one flight against a set of limits asks the question not at
all. Any corpus with turn structure asks it immediately. Recorded as an open question
rather than guessed at.

### `status`

```
mapped       enumerated and classified; not yet worked
blocked      a dependency is unmet
implemented  in the engine, with a recorded conformance verdict
declined     scope is out, or the ambiguity's fate is unresolved
```

`implemented` requires the verdict. Code without one is `mapped`, whatever the repository
contains — otherwise the map records intent rather than fact, and its whole value is that it
records fact.

## The map and the engine agree, or the map is wrong

The map's classifications correspond exactly to the kernel's closed `UnresolvedReason`
vocabulary. This is the property that makes the map load-bearing rather than documentation:

| A map entry that is… | At runtime the engine returns… |
|---|---|
| `status: mapped` — read, not built | `UnsupportedRule` |
| `scope: out` | `OutsideCurrentScope` |
| `ambiguity.fate: unresolved` | `RequiresInterpretation` |
| an `operation` whose `value` dependency is unimplemented | `MissingRulesData` |
| two implemented entries with no entry for their combination | `UnsupportedInteraction` |

So an engine's honest answer about what it cannot do should be derivable from its map, and
an unresolved result that does not correspond to a map entry means something was implemented
without being mapped. That is a checkable invariant, and it is the first thing the factory
should enforce once it exists.

## The corpus manifest

Beside the entries, the corpora they cite:

```json
{
  "schemaVersion": 1,
  "corpora": [
    {
      "sourceId": "cfr-26",
      "title": "Title 26, Code of Federal Regulations",
      "adapter": "ecfr-xml",
      "locatorGrammar": "section-designation",
      "contentHash": "…64 hex…",
      "hashDerivation": "ecfr-xml",
      "asOf": "2019-03-14",
      "boundaryPolicy": "pin-in-repo",
      "licence": "public-domain"
    },
    {
      "sourceId": "core-rules",
      "title": "Core Rulebook",
      "edition": "First printing",
      "adapter": "pdf",
      "locatorGrammar": "printed-page",
      "contentHash": "…64 hex…",
      "hashDerivation": "pdf-bytes",
      "boundaryPolicy": "never-commit",
      "licence": "commercial",
      "envVar": "CORE_RULES_PDF"
    }
  ]
}
```

`hashDerivation` and `boundaryPolicy` are the two fields most likely to be thought
redundant, and both are load-bearing. A digest without its derivation does not say what it
covers. A boundary policy is a property of the licence, and the two engines this method was
derived from answer it in opposite directions — one commits its extracted corpus because the
SRD is CC-BY, the other commits nothing because its rulebook is commercial.

`references` lists corpora this one defers to — a regulation citing another title, a
rulebook citing a supplement — each marked admitted or not. Those references are the
boundary of any engine built from the corpus, and naming them makes that boundary
inspectable rather than inferred from whichever entries happen to be declined. In the first
trial, three of twelve sections deferred their meaning to a corpus that had not been
admitted.

```json
"references": [
  { "sourceId": "cfr-49-171", "citation": "§ 171.8", "admitted": false },
  { "sourceId": "air-almanac", "admitted": false }
]
```

`asOf` is present only for a corpus that is revised over time. Absent means timeless, never
unknown. It pins which text is in force and nothing more — a rule may carry dates of its
own, which are ordinary operations over a date the caller supplies.

## Where the map lives

In the engine's own repository, under version control, beside the code it describes. It is
not a factory artifact that gets discarded after a run: it changes as the engine grows, and
its `status` fields are only true of a particular commit.

## Open questions

Recorded rather than decided. The first trial —
[examples/faa-part-107](../examples/faa-part-107/README.md) — answered some and sharpened
the rest.

**Granularity.** Partly answered. Twelve sections of regulation produced twenty-four
entries, close to 2:1, and the split that mattered was separating a stated figure from the
comparison against it: one paragraph of § 107.51 holds three distinct figures, and a single
entry would have lost two of them. The dependency graph remains the arbiter for the harder
cases.

Open questions are tracked as issues so they are worked rather than admired:

- [#5](https://github.com/brandonifco/rules-factory/issues/5) — `dependsOn` conflates
  implementation order with runtime precondition. Found in trial 2, invisible in trial 1.
- [#6](https://github.com/brandonifco/rules-factory/issues/6) — a standard is not a gap.
  Both available fates imply the corpus failed to say something, and sometimes it did not.
- [#7](https://github.com/brandonifco/rules-factory/issues/7) — an entry beyond the
  adapter's reach has no field to say so.

**Who writes it.** The ambition is that an agent produces a first draft from the corpus and
a human reviews the decomposition. Whether the first draft is good enough to be worth
reviewing is unknown, and is the main thing the first real run will test.

**Drift.** The map claims things about the engine (`status`, `implementedIn`) that the engine
could contradict. The correspondence table above is checkable and should become a check.
