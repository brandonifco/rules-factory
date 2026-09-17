# rules-factory / tax-121 — handoff, 2026-09-17

Everything below is pushed to GitHub. Nothing needed is local except the environment notes.

## The question being tested

Does `rules-kernel` + `rules-factory` deserve to be the central investment? The test: take
`tax-121-principal-residence` (26 CFR 1.121-1, the home-sale gain exclusion, 24 mapped rules)
through the full rails and measure what it costs and what breaks.

## State

**tax-121-principal-residence** — 7 of 24 entries merged, `main` green, 45 tests.
Merged: `effective-date` (#24), the owner's ruling + gate helper (#26), `residence-facts-and-circumstances` (#1),
`residence-may-include` (#2), `principal-residence-factors` (#3), `maximum-limitation-amount` (#8),
`ownership-and-use-aggregation` (#12), `use-requires-occupancy` (#14).
Ready to build: #4, #13, #17, #27. Blocked behind them: the rest, including #15 `ownership-and-use-test`
and #16 `exclusion-of-gain`, which are the two that would let the engine answer "do I qualify, and how much".

**rules-factory** — #239 merged (PR #241): the gate refuses placeholder mutation evidence.
#242 is the design decision on the regeneration fan-out: **A and B now, C deferred**.
#243 (A, the backlog leaves the repository) is in flight. B (overlay splits per entry) is not filed yet.
A release tag is due: 5 factory commits are untagged since `factory/v0.10.0`, with #8, #169, #228 closed since.

## Measured cost (7 entries, ~2h)

~17 min and ~230k tokens per merged entry: ~5 min to implement (1/3 rule work, 2/3 process),
two reviews at 1-2 min each, 1-3 min serial integration. Zero map defects, zero escalations,
zero blocking review findings, 14 non-blocking notes.

## Why parallel work does not work yet

A one-entry PR touches 27 files; 3 are real work. 19 are backlog files that renumber whenever any
entry is finished, 3 are generated C#, 1 is `provenance.json`, 1 is the shared overlay. So any two
entry PRs conflict. Six agents building in parallel still merged one at a time.
#243 (A) removes 19. B removes 1. Then measure: two branches from one commit, merged in either
order, no hand resolution, combined tree green.

## The open design idea: superposition

Where an outcome depends on an answer only a person can give, return the outcome under each answer
instead of declining: merge branches whose outcomes are equal, express numeric unknowns as
constraints, and list the context needed to decide with who supplies it and its citation.
Evidence gathered: `principal-residence-factors` declines under the effective-date gate although both
branches give the identical six factors — the engine **over-declines**. `maximum-limitation-amount`
($250k vs $500k on a joint-return fact) is the clean two-branch case. `short-temporary-absences`
is the bounded-interval case (corpus examples put 2 months in, 1 year out).
Decision: keep it out of the kernel; prototype engine-local; promote only when a second consumer
needs the same shape. `Resolution<T>`'s two cases are deliberately exhaustive.

## Outside review

Codex (GPT-6-Astra) reviewed the build-order decision and PR #241 twice. It found a real bypass in
#241 that the tests agreed with. **Use medium reasoning, not xhigh — the subscription is $20/mo.**
Its sandbox cannot run here (needs unprivileged user namespaces); pipe the diff and sources into
the prompt instead, or run:
`sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`

## Environment gotchas

- The pinned .NET SDK 10.0.112 is at `/usr/lib/dotnet`. `~/.bashrc` points `DOTNET_ROOT` at
  `~/.dotnet`, which has only SDK 8, so every gate run needs:
  `export DOTNET_ROOT=/usr/lib/dotnet PATH=/usr/lib/dotnet:$PATH;`
- `tools/entry-packet.py` needs a `dotnet restore` first.
- `tools/re-produce.sh` clones the factory from GitHub at the pinned commit; `RULES_ENGINE_FACTORY_REPO`
  points it at a local checkout.
- Engine work happens in worktrees outside the repo (`tools/dispatch-agent.sh <issue>`); rules-factory
  worktrees go under `.claude/worktrees/`.

## What I would do next

1. Land #243 (A), file and land B, then run the acceptance test and decide whether C is needed.
2. Then #15 and #16 — but note Codex's finding: the ordinary-sale cap lives in §121(b) and §1.121-2,
   which are **outside this corpus**, so finishing them proves composition, not the commercial question.
   Pick one supported scenario end to end and measure active minutes and dollars for it.
