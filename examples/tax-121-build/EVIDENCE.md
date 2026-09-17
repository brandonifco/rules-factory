# Evidence: building seven entries of 26 CFR § 1.121-1

Trial 9 in [the log](../README.md) mapped this corpus. This is the **build** from that map:
`tax-121-principal-residence`, seven of 24 backlog entries taken from `factory backlog --create`
to merged `main` through the rails, on 2026-09-17, between 13:10 and 15:15 EDT.

It was run to answer one question — *what does an entry actually cost, and what breaks* — because
the argument for the rules platform being the central investment rested on estimates.

**Result: seven entries merged, no map defect found downstream, no escalation, no blocking review
finding. Four defects in the rails, one of them a real bypass of the evidence rule. The measured
cost is ~17 minutes and ~230k tokens per merged entry, of which roughly two thirds is process.**

The numbers below are counted, not estimated, unless a line says otherwise. Where a claim is a
judgement it says so.

## What was run

`factory rails --apply` and `factory backlog --create` against an engine that had neither (no
labels, no ruleset, no issues). Then, per entry: `tools/dispatch-agent.sh <issue>`, an
implementing agent in its own worktree, two read-only reviewers, a recorded semantic verdict, and
a merge. Entries: `effective-date` (#24), a decision record and shared gate helper (#26),
`residence-facts-and-circumstances` (#1), `residence-may-include` (#2),
`principal-residence-factors` (#3), `maximum-limitation-amount` (#8),
`ownership-and-use-aggregation` (#12), `use-requires-occupancy` (#14).

`main` ended green: 45 tests named by 7 implemented entries, `validate.sh full: PASS`.

## Cost

| | Wall clock | Tokens | Tool calls |
|---|---|---|---|
| Implement one entry | ~5 min | 80–100k | 20–25 |
| Structural review | ~1 min | ~55–80k | 8–19 |
| Semantic review | ~1.5 min | ~40–78k | 7–16 |
| Integrate onto a moved `main` | 1–3 min hands-on | — | 8 |
| **Per merged entry, all in** | **~17 min** | **~230k** | — |

Roughly one third of an implementer's tool calls went to the rule and two thirds to process: two
`re-produce` cycles, gate runs, the pull request template, waiting on checks, and resolving the
integration conflicts. That split is counted from the agents' own reports, which are their
estimates of their own work, so treat it as ±1 call, not exact.

The second entry cost 84k tokens against the first entry's 138k, once the conventions existed and
the prompt carried what the first had learned.

**Not measured, and it matters:** the owner's own active minutes, and the dollar cost. Tokens are
not dollars and tool calls are not wall time for the person watching.

## What the reviews caught

Nothing blocking, in seven entries — which is itself a measurement of the map, not only of the
implementers. Fourteen non-blocking notes. The three that changed something:

1. **`Applies == false` is not a plain "no".** § 1.121-1(f) points at a retroactive election
   (§ 1.121-4(j)) that this engine maps as out of scope, so "the section does not apply" cannot
   be read as "no exclusion". This produced the owner's ruling recorded as the engine's decision
   0001, and the shared gate helper every later entry calls.
2. **730 is the corpus's own figure**, not the implementer's arithmetic: line 30 prints
   "24 full months or 730 days (365 × 2)". The reviewer checked the source line rather than the
   plausible-looking constant.
3. **The engine over-declines.** `principal-residence-factors` declines under the effective-date
   gate although *both* branches of that unknown yield the identical six factors. The answer never
   depended on the election. Decision 0001, applied as a blanket rule, makes the engine refuse
   where the unknown cannot change the outcome.

Finding 3 is unfiled against this engine as of 2026-09-17. An independent review (OpenAI Codex,
GPT-6-Astra) added the correction that identical *printed factors* do not prove identical
*applicability*, since the engine holds none of the retroactive-election rules: the defect is in
the query's design — "what does this corpus list?" needs no transaction date, "do these govern this
sale?" does — not in the implementer following the map.

## What broke in the rails

| # | What | State |
|---|---|---|
| 1 | The gate accepted `"mutation": "PENDING"`: any non-empty string passed as evidence. | Filed #239, fixed, merged (PR #241) |
| 2 | Any two entry pull requests always conflict. A one-entry pull request touched **27 files**, of which 3 were the work: 19 backlog files that renumber whenever any entry is finished, 3 generated C#, `provenance.json`, and the shared overlay. Six entries built in parallel still merged strictly one at a time. | Filed #242 (decided: A and B now, C deferred), #243 in flight |
| 3 | Two issues filed by hand carried the same `rules-factory-entry` marker as a backlog issue, and `factory backlog --create` then refused the **whole** sync. Correct refusal; the consequence was that every dependent issue kept a stale `state:blocked` label until the markers were stripped, and nothing said so. | Unfiled |
| 4 | Five of seven entries share a paragraph citation with another entry, so a citation-swap mutation survives: the locator cannot tell two entries apart. | Unfiled. Codex's view, which I accept, is that swapping a locator for an equal locator is an equivalent mutation and not worth killing; the fix, if wanted, is to return and assert **entry identity alongside** the locator |

Defect 1's fix was reviewed twice from outside under AGENTS.md §6. The first round found that the
new check read only *overlay* items, so an `implemented` entry whose tests came from the package
map bypassed it entirely with an empty overlay — a real bypass, which the change's own tests
agreed with. The second round found the fix had overshot: counting only *distinct* words refused
honest evidence such as ``Increment `increment`; fails``.

**The honest limit of that check, as merged:** it refuses an unfilled placeholder. It cannot tell
whether the edit was made or the test went red. That still rests on the implementer's word.

## What the run says about the platform

Stated as judgement, not measurement.

- The map held. Zero downstream defects across seven entries and 45 tests is evidence that the
  blind second mapping (trial 9) did its job. It is **not** evidence that the map's boundary is
  the right boundary for a product.
- The expensive part is not the rules. Two thirds of the work is the apparatus around them, and
  that fraction is addressable: 19 of the 24 derived files in a pull request are a rendering
  nothing reads.
- Seven entries of constants, lists, a threshold value and deliberate declines do not establish
  that the hard part composes. `ownership-and-use-test` (#15, date arithmetic over a five-year
  window) and `exclusion-of-gain` (#16) are the untested part.
- **The corpus boundary may defeat the product.** The ordinary-sale $250,000/$500,000 cap is in
  § 121(b) and § 1.121-2, which this corpus does not admit; `maximum-limitation-amount` covers the
  combined vacant-land case. So finishing #15 and #16 proves composition within the slice and does
  *not* answer "can I exclude, and how much" in general. This was Codex's finding and it is
  correct.

## The idea the run produced

Where an outcome depends on an answer only a person can give, an engine could return the outcome
*under each answer* rather than declining: branches whose outcomes are equal merge, numeric
unknowns become constraints, and the result carries the context still needed, each item with who
supplies it and its citation. A decline becomes the degenerate case — a superposition where the
engine cannot say what would resolve it.

Evidence from this run, unforced by any wish to build it:

- `principal-residence-factors` — both branches equal, so the answer needed no election at all
  (the over-declining above);
- `maximum-limitation-amount` — a clean two-branch case, $250,000 or $500,000 on a joint-return
  fact the caller supplies;
- `short-temporary-absences` (not built) — a bounded judgement: the corpus's own examples put two
  months inside and a year outside, so an absence of *N* is settled at the ends and open between
  them, which is [0031](../../docs/decisions/0031-an-example-that-bounds-a-term-is-recorded-as-a-bound.md)'s
  bound seen at runtime.

Decided on 2026-09-17, on Codex's advice and mine: **keep it out of the kernel.**
`Resolution<T>`'s two cases are deliberately exhaustive and changing that contract now spreads an
experiment across every consumer. Prototype it engine-local, and promote it only when a second
consumer independently needs the same shape.

## Files

- [`learning-log.md`](learning-log.md) — the log as it was kept during the run, verbatim, including
  the friction items that did not become issues.
- [`HANDOFF.md`](HANDOFF.md) — the state at the end of the run, and what to do next.
