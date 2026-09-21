# 0061 — An injection names the refusal it expects, and a catch by another rule is a different outcome

## Status

Accepted — 2026-09-21. Closes
[#362](https://github.com/brandonifco/rules-factory/issues/362), item 3 of
[#283](https://github.com/brandonifco/rules-factory/issues/283), split out when the rest of that
issue closed in #359. **Extends [0034](0034-a-valid-unresolved-state-is-established-not-asserted.md)**'s
measurement rather than its rules. Adds no entry field, no manifest key, and no check. Changes no
check's verdict on any committed map: what changes is what the measurement of those checks means.

## Context

`tools/mutate-map.py` damages a committed map one named way at a time and records whether the
validator refused it (#259, `examples/validator-attack/`). The headline is a catch rate: 28 of 62.

#283's first two items fixed the same defect one level down. `assert_catches` in the validator's
own unit tests now requires the refusal fragment its test is about, so a test cannot be written
that asserts only *that* a check refused. That holds the unit tests. It did not hold the
measurement over whole committed maps, where an injection declared what it damaged and **not
which rule should object** — so a mutation refused by a different rule than the one it exercises
counted as caught.

On #283's own evidence that is not hypothetical: `extraction` fires two rules at once on one
mutation. A catch rate can be right about the number and wrong about which rules are load-bearing,
and **a rule that never catches anything on its own is invisible in it**.

## Decision

**Every injection names the refusal it expects, and the harness reads it.**

`MUTATIONS` gains an `expect` field, which is one of three things:

* **a rule name** — the rule the mutation is written to exercise;
* **a family of rule names** — where several rules are faces of one question and which one answers
  depends on the corpus's grammar rather than on whether the check works. `narrow-extent` expects
  `extent`, `extent-bounds` or `extent-end`: a page-marked corpus has an end to overrun that a
  section-designated one has not;
* **`None`** — where *no rule is written to catch the error at all*, and the mutation measures
  that gap. Four are like this, and each says why in the table: a removed `enabledBy` or
  `suspendedBy` edge reads exactly like a rule that never had one; an invented `dependsOn` is
  chosen so it makes no cycle, so the order is as well formed as a true one; and
  `same-passage-evidence` leaves the quote inside the passage the entry cites, so every locator
  check is satisfied and nothing structural can tell which sentence states the rule.

**A catch by any other rule is a distinct outcome, not a catch.** The run records `expected`,
`byIntendedRule` and `byNeighbourOnly`; the table prints `neighbour only: <rules>` rather than the
rule names alone; and the report says how many of the catches were by the rule the mutation
exercises. `byIntendedRule` joins the shape the gate holds the committed measurement to, so a
mutation that stops being caught by its own rule and starts being caught by a neighbour is a row
nobody chose to move.

The intended rule counts only where **its own detector refused**. A rule that turned inside a tool
that still exited 0 did not stop the map, which is what the existing scoring already means by
detected: a signal nobody is obliged to act on is the shape of this repository's two checkers that
counted work they had not done.

## Consequences

The measurement now reads:

> 28 of 62 mutations detected; 34 missed.
> **25 of those 28 were refused by the rule the mutation exercises; 3 only by another.**

Three things follow, and none of them is a bug in a check.

**`same-passage-evidence` has no rule, and its one catch was luck.** It was refused on
`hoyle-backgammon` by `cross-references` — a rule about whether a pointing passage says where it
points, which has nothing to do with which sentence of a cited passage states the rule. On the
other four maps it is missed. So the validator has no check for this error, the headline counted
one anyway, and the record now says so on its face.

**`applicability-reach` catches one of the three mutations written for it.** `remove-applicability`
is refused on all three applicable maps, but by `applicability-reach` only on
`tax-121-principal-residence`; on `hoyle-backgammon` it is `superposition` and on `faa-part-107`
`gates`. The rule works — it is not dead — but two thirds of its apparent evidence belongs to
other rules, and a change that broke it would have moved one row rather than three.

**The catch rate did not move, and that is the point.** 28 of 62 is what it was. What was not
knowable before is that three of the 28 say nothing about the rule they were counted for.

What this still does not do: say whether the *intended* rule is the right rule for the error, or
notice a rule that catches its own mutation for the wrong reason. `expect` is a claim about what
the mutation is for, written from its `models` and `wrong` and not read off what the validator
happens to do — which is what makes a disagreement between them a finding. It is a claim a person
made, and the argument for it is in the table beside it.
