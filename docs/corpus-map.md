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
| `dependsOn` | Entry ids. Determines backlog order — the sequence entries must be *implemented* in. **Not** a runtime precondition; see `gatedBy`. |
| `gatedBy` | Entry ids. The rules that govern whether this one is reachable at runtime. Absent on an entry that always applies. Orders nothing. See below. |
| `beyondAdapter` | Present only when the declared adapter cannot read the rule the locator cites. Names the adapter and the modality. See below. |
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

`ambiguity.unresolvedReason` names the `UnresolvedReason` the engine will return, and is
present when the fate is `unresolved`. It is the field that ties an entry to the
correspondence table below.

Both Part 107 maps also use the `ambiguity` block to carry a decline that is **not** an
ambiguity — `civil-twilight-alaska` and `hazardous-material` are `clarity: clear` and carry
one, because their meaning is defined in a corpus that was not admitted. The block is
specified as absent when clear, and those four entries contradict that. Recorded here rather
than quietly reconciled; see the open questions.

### `dependsOn` orders work; `gatedBy` does not

`dependsOn` orders *implementation*. A rule that applies only in a phase — bearing off
begins once every man is home; entry from the bar suspends every other move — has a
**runtime precondition**, which is a different fact. `gatedBy` is where it lives. Decided in
[0003](decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md).

The two relations coincide often enough to be confused, and they are not derivable from each
other. In the backgammon map, `bearing-off-doublets` has six `dependsOn` ancestors and
exactly one of them is its gate; `move-by-pip` is gated by `enter-from-bar`, which is not
among its ancestors, and nor is `move-by-pip` among `enter-from-bar`'s. A stateless corpus
never asks: a regulation evaluating one flight against a set of limits has no phase for a
rule to be scoped to, and both Part 107 maps carry `gatedBy` on no entry at all.

**`gatedBy` holds entry ids and nothing else.** No predicate, no state name, no threshold,
no sentence. A gate is itself a rule the corpus states, so it already has an entry with a
locator; if a gate you want to record has no entry, the map is missing an entry. The
condition is the engine's to implement — the map says which rule governs reachability and
points at where to read it.

It says nothing about *direction*. `bearing-off-eligible` permits the entries it gates;
`enter-from-bar` suspends them. Only the referenced entry's text distinguishes those, and a
reader who does not follow the id has learned less than they may think.

It is **not transitive and not inherited through `dependsOn`.** Every entry a gate reaches
names it, even where a `dependsOn` ancestor names the same gate — the two relations are
independent, so inheriting along one of them would be a guess. Expect repetition.

It orders nothing. `dependsOn` remains the only input to backlog order.

### `beyondAdapter`

The rule is in the corpus, stated in a modality the declared adapter cannot read. Decided in
[0004](decisions/0004-adapter-reach-is-a-property-of-the-entry.md).

```json
"beyondAdapter": { "adapter": "plain-text", "modality": "illustration" }
```

`adapter` must match the `adapter` declared in the manifest for the entry's
`locator.sourceId`. The fact is adapter-relative, not absolute: a reader that can see
figures reaches the entry, and naming the reader that could not makes "what did the old
adapter miss" a query rather than a re-read.

`modality` is a short noun phrase naming what holds the rule — `illustration` in the one
observed case. Deliberately not a closed vocabulary: one instance is not enough to write
one from, and it can be closed later from evidence. Explanation goes in `note`, not here.

`locator` is still required and still cites the passage that *states* the rule — the
sentence saying the men are placed as in Fig. 1. The entry is unreadable, not uncitable.

This is a different fact from the manifest's `references`, and telling them apart is the
whole point. `references` says the rule is defined in a corpus that was not admitted;
`beyondAdapter` says the rule is here and our reader cannot see it. Both decline as
`MissingRulesData` at runtime, and before this field they were indistinguishable without
reading a prose reason.

The general case is worse than the one illustration: a PDF rulebook read as extracted text
loses exactly the tables a rules engine most needs. No trial has produced that — both
corpora were text end to end — and the field does not detect it. It records a limit a human
recognised. An adapter that silently drops a table produces an entry nobody writes, and no
field can help with an entry that does not exist.

### `status`

```
mapped       enumerated and classified; not yet worked
blocked      a dependency is unmet
implemented  in the engine, with a recorded conformance verdict
declined     scope is out, the ambiguity's fate is unresolved, or the entry is
             beyond the adapter's reach
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
| carries `beyondAdapter` | `MissingRulesData` |
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
  implementation order with runtime precondition. Decided:
  [0003](decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md) adds `gatedBy`.
- [#6](https://github.com/brandonifco/rules-factory/issues/6) — a standard is not a gap.
  Both available fates imply the corpus failed to say something, and sometimes it did not.
- [#7](https://github.com/brandonifco/rules-factory/issues/7) — an entry beyond the
  adapter's reach has no field to say so. Decided:
  [0004](decisions/0004-adapter-reach-is-a-property-of-the-entry.md) adds `beyondAdapter`.

**Where a decline's runtime reason lives.** Opened by 0004 rather than answered by it. An
entry beyond the adapter's reach now records its reason structurally; an entry whose meaning
is defined in an unadmitted corpus still records the same reason in an `ambiguity` block, on
an entry that is not ambiguous. The two are the same kind of fact — the engine cannot see
the rule — and are represented two different ways. Part 107's `civil-twilight-alaska` and
`hazardous-material` are the instances.

**Nothing yet uses `kind: assertion`.** It was added after the first trial and argued for at
length above, and no entry in any of the three maps carries it — all 71 entries across them
are `value` or `operation`. The Part 107 entries the first trial identified, such as
`visual-line-of-sight` and `preflight-actions`, are still `operation` with an explanatory
`note`, which is exactly what that trial reported as wrong. Either the maps are behind the
schema or the category is narrower than the trial claimed, and which is not settled here.

**Who writes it.** The ambition is that an agent produces a first draft from the corpus and
a human reviews the decomposition. Whether the first draft is good enough to be worth
reviewing is unknown, and is the main thing the first real run will test.

**Drift.** The map claims things about the engine (`status`, `implementedIn`) that the engine
could contradict. The correspondence table above is checkable and should become a check.
