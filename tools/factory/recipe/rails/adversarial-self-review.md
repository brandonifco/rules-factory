# Adversarial self-review: attack it before anyone is paid to

This document is managed by rules-factory (decision 0071). [`AGENTS.md`](../AGENTS.md) §7 is the
contract.

The semantic reviewer is the most expensive agent this team runs, and most of what it has found in
practice was not a misreading of the rule. It was a boundary nobody tried, an empty list nobody
passed, a refusal that happened after a field had already been written. Those are cheap to find by
the person who wrote the code, and expensive to find by anyone else. So before a semantic packet can
be written, **every entry it names has a committed record of this attack**.

```bash
tools/review-scope.py self-review <entry id> --package-map <map>           # the skeleton, with the claim digest
tools/review-scope.py self-review <entry id> --package-map <map> --check   # what the packet will hold you to
```

Write the record to `reviews/self-review/<entry id>.json` and commit it. Each of the twenty classes
below is answered `tested`, naming the tests that attack it, or `not-applicable`, with a reason a
reviewer can check. The record carries the entry's **claim digest** — a fingerprint of everything
the entry rests on — so a repair that touches any of it makes the record stale, and the attack is
redone before the next reviewer is paid. That the tests named exist is checked; that they attack
what they say is your word, and a reviewer will read them.

Each class below has the question it asks and a test template to start from. The templates are
xUnit, written against the rule body's own types, as the mutations are (`AGENTS.md` §7).

## The classes

**`integer-extremes`** — What happens at `int`/`long` `MinValue` and `MaxValue`, and at zero and
one either side of every stated bound?

```csharp
[Theory]
[InlineData(int.MinValue)] [InlineData(-1)] [InlineData(0)] [InlineData(1)] [InlineData(int.MaxValue)]
public void Rule_answers_or_refuses_at_every_extreme(int value) =>
    Assert.NotNull(Rule.Resolve(Request.With(value)));
```

**`overflow-underflow`** — Can arithmetic on a caller-supplied value overflow or underflow,
silently or by exception? Assert the refusal, and build the engine's arithmetic `checked` where the
rule sums caller values.

**`empty-collections`** — What happens when every collection the request carries is empty?

```csharp
[Fact]
public void Rule_with_nothing_to_act_on_refuses_rather_than_answering_vacuously() =>
    Assert.True(Rule.Resolve(Request.With(Array.Empty<Item>())).IsRefused);
```

**`invalid-public-input`** — `null`, `default`, negative, crafted or out-of-range values at every
public entry point: each is a refusal with a reason, never an exception.

**`invalid-construction`** — Can a value object or enum be constructed invalid — a `default`
struct, `(Kind)99`, a `with` copy that skips validation — and reach the rule?

```csharp
[Fact]
public void An_undefined_enum_value_is_refused() =>
    Assert.True(Rule.Resolve(Request.With((Phase)99)).IsRefused);
```

**`phase-state-boundaries`** — Does the rule hold at the first and last moment of every phase or
state it names, and refuse one step outside them?

**`order-dependence`** — Does the answer change with the order of inputs, or of actions that should
commute? Resolve the same request with its collections reversed and assert the same answer.

**`partial-mutation-before-refusal`** — Is any state changed before a refusal is decided?

```csharp
[Fact]
public void A_refused_request_leaves_the_state_as_it_was()
{
    var before = State.Sample();
    var snapshot = before with { };
    Rule.Apply(before, Request.Invalid());
    Assert.Equal(snapshot, before);
}
```

**`exception-leakage`** — Can any public resolution path throw? Drive every entry point with the
crafted inputs above inside `Record.Exception` and assert it is `null`.

**`refusal-classification`** — Is each non-answer the right one of refused, unresolved and outside
scope, with the right reason and locator?

**`missing-content-masking`** — Can missing or unavailable content hide a refusal already settled by
what is present? Remove the optional content and assert the settled refusal still comes back first.

**`sentinel-wraparound`** — Is a sentinel, wraparound or modular value (`-1`, a turn counter, an
index) reachable as a real value? Assert the value one past the wrap.

**`idempotence`** — Does repeating the request or action give the same answer where the rule says it
should, and a different one where it says it should not?

**`immutability`** — Can a caller mutate state the engine returned, or state it was handed after
validation? Mutate the argument after the call and assert the answer did not move.

**`caller-controlled-sizes`** — Is every size or count the caller controls bounded before it drives
work or allocation? Pass `int.MaxValue` as a count and assert a refusal, promptly.

**`exact-min-max`** — Are "at least", "at most", "more than" and "fewer than" each inclusive or
exclusive exactly as the corpus words them?

```csharp
[Theory]
[InlineData(Bound - 1, false)] [InlineData(Bound, true)] [InlineData(Bound + 1, true)]   // "at least Bound"
public void The_bound_is_inclusive_as_the_corpus_says(int value, bool allowed) =>
    Assert.Equal(allowed, Rule.Resolve(Request.With(value)).IsAllowed);
```

**`exclusive-or`** — Where the corpus says "or", is it exclusive or inclusive, and does the code
choose the same? Test the case where both hold.

**`count-semantics`** — Are "exactly", "up to" and "at least N" implemented as worded? Test N−1, N
and N+1.

**`action-dependency-interactions`** — Does the rule still hold when the actions or entries it depends
on are applied in combination, in each order the rules allow?

**`invalid-intermediate-state`** — Can a public API or a record copy produce an intermediate state
the rule assumes impossible? Build it through the public surface and resolve against it.

## What a record looks like

```json
{
  "selfReviewFormat": 1,
  "entry": "altitude-limit",
  "claimSha256": "<from tools/review-scope.py self-review>",
  "classes": {
    "exact-min-max": {"outcome": "tested", "tests": ["AltitudeLimit_DeclinesAboveTheCeiling"]},
    "exclusive-or": {"outcome": "not-applicable", "reason": "the entry's evidence states one condition and no disjunction"}
  }
}
```

Every one of the twenty classes appears. A class discovered by a review that none of these names is
worth an issue against rules-factory, so that the next engine inherits the question.
