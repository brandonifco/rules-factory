# 0050 — A pull request is gated on what its own diff owes, and a release gate narrows only packing

## Status

Accepted — 2026-09-20. Records the decision on
[#347](https://github.com/brandonifco/rules-factory/issues/347).
**Carries out [0049](0049-the-gate-can-say-which-of-its-checks-a-change-owes.md)**, which added the
scopes and explicitly did not decide whether CI would ask for them — it recorded that the
workflows still ran `--full` on every pull request. This is that decision.
**Bounded by [0015](0015-a-map-is-published-as-a-versioned-package.md)**, whose two independent
packs of a tagged map are the thing no scope may narrow, and which this makes a tested fact rather
than a commented intention.

## Context

0049 gave the gate three scopes and nothing asked for anything but `--full`. Three questions
were still answered the same way, and each has a different right answer:

- **A pull request.** Its diff is what could have broken something. 0049's classifier already
  decides this and widens to `--full` on anything it cannot place.
- **A push to `main`, and a scheduled run.** There is no diff to be narrow about. `main` is what
  a release is cut from, and a schedule exists precisely to run the checks no diff ever owes.
- **A tag.** A map is certified against this repository's rules and not its own, so every
  structural and corpus check is owed. Packing the other three maps is not: they are packed
  twice on every pull request that touches them, and a release is not the occasion to
  re-establish that.

There was also a check in the wrong place. `check-status-issues.py` reads GitHub to ask whether a
README sentence citing an issue as open still can. It is the one step in the gate that needs the
network — a flake source and a rate-limit consumer — and what it asks about is a README sentence
and an issue's state, neither of which a diff of code touches.

## Decision

**A pull request runs `validate-repo.py --changed --base <its own base>`.** The rule that decides
the scope stays in that file, covered by tests. "Force `--full` for core tooling" is *not*
written in the workflow: that would be a second copy of the rule, in YAML, with nothing holding
the two together, which is the drift this repository keeps finding in itself. The classifier
widens for core tooling because that is its own rule.

The checkout is unshallowed. `git diff <base>...HEAD` needs the base commit present; without it
the diff is unreadable, which widens to `--full` correctly but *silently*, and a scope nobody can
compute is a feature that quietly does not exist.

**A push to `main` and a weekly schedule run `--full`.** The schedule is what makes the network
check reachable without a code change: an issue closing is not an event in this repository, and
until now nothing would have noticed the README going stale in a week where nobody touched it.

**`check-status-issues.py` runs under `--full` and not under `--changed`.** `scripts/validate.sh`,
`main` and the schedule all keep it. A diff that touches `README.md` is placed by no rule and
widens to `--full` anyway, so the case it exists for still reaches it.
`check-readme-status.py` — the half that imports the factory's parser and needs no network — runs
at every scope, because a code change is exactly what moves it.

**The publish gate runs `--release <map>`, and its double pack is untouched.** The tagged map is
packed in the `gate` job and packed again in `publish` from a separate checkout, and the two
SHA-256 digests are compared before anything is pushed. Publishing cannot be undone, and that
comparison was held by nothing but its own comment; `tools/tests/test_ci_scope.py` now holds it,
along with the facts that make it mean anything — two checkouts, the comparison before the push,
an absent digest refused rather than treated as a match, and `id-token: write` on the publishing
job alone.

## A flag 0049 got wrong

`Scope.engine` said whether an engine produced from scratch is owed, and 0049 set it for
`tools/factory/` alone. `tools/validate-engine.py` produces its engine from
`examples/hoyle-backgammon` and reads every `examples/*/map-package.json`, so a change to any
packable map owes that job too. Nothing consumed the flag, so nothing had broken — and a CI
workflow was the first thing that would have. The claim is now held to `validate-engine.py`'s own
source by a test rather than trusted.

## What this does not decide

- **Whether the engine job is ever skipped.** It is not the critical path — it runs in parallel
  with `validate` and finishes sooner — and skipping a real check to save no wall clock is a bad
  trade. `Scope.engine` is now correct and still unconsumed; a test says so, and that test is
  what has to change first.
- **What the scheduled run should do when it fails.** It reports like any other run.
