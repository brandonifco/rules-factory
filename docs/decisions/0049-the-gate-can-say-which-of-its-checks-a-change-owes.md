# 0049 — The gate can say which of its checks a change owes, and widens on anything it cannot place

## Status

Accepted — 2026-09-20. Records the decision on
[#342](https://github.com/brandonifco/rules-factory/issues/342).
**Extends [0033](0033-the-validator-is-the-adversary-and-validates-the-uncertainty-too.md)**,
whose layout of the checkers' tests by subsystem this reuses as the layout of the scope table,
and **bounded by [0015](0015-a-map-is-published-as-a-versioned-package.md)**, whose byte-identical
double pack is the one thing the narrowest scope here still does in full.

## Context

`scripts/validate.sh` was the one definition of "acceptable" and it was all-or-nothing: every
corpus, every package, every test, on every invocation. Three questions that are not the same
were answered the same way:

- a pull request touching one map, where the other six maps' fixtures prove nothing about it;
- a release of one map, where every structural check is owed and packing the other three is not;
- a change under the contract or a subsystem over it, where everything is owed.

Nothing could tell those apart, and the rule that would decide was written nowhere.

The measurement that shapes this record: on main at 45cfeca, `validate.sh` takes 3m05s.
`pytest tools/tests` is 2m32s of it and `tools/tests/factory/` alone is 2m18s. All seven maps'
fixture checks together are about 3s. So **narrowing the map work is not where the wall clock
is**, and this record does not claim it is. A factory-only change measured 2m47s scoped against
3m01s full — 8%.

What it is for is the vocabulary. A release that packs three maps it is not publishing is
gating the tag on work that proves nothing about the tag, and a CI workflow cannot ask for
less without a place to ask it.

## Decision

`tools/validate-repo.py` owns the steps and carries three scopes:

- `--full` — the list scripts/validate.sh ran, in its order, over every map. The default.
- `--changed --base <sha>` — the tests and every repository-wide check, always; only the map
  fixtures the diff could have broken.
- `--release <map>` — every structural and corpus check, because a map is certified against this
  repository's rules and not its own; only the tagged map is packed.

`scripts/validate.sh` stays and passes `--full`: it is what AGENTS.md §2 names, what CI runs, and
what is in every contributor's shell history.

Scoping a gate is how a gate stops examining things, so the rules are built to fail towards
running more:

- The scope is decided by three tables of paths in the orchestrator — `CORE_PREFIXES`,
  `CORE_FILES` and `FACTORY_PREFIXES` — and every row of each is covered by a test.
- Anything the table cannot place widens to `full`: an unknown path, an `examples/` directory
  that is not a map fixture, a missing base, a diff git cannot read, and any exception raised
  while classifying.
- `full` is not computed. It is the literal step list over every map, and a step that tries to
  skip under it raises rather than printing a skip.
- A narrowed step prints what it did not run. A skipped check that prints nothing is
  indistinguishable from a passing one.
- The unit tests run at every scope. Which of them a diff could have broken is not a question a
  path table can answer honestly.
- The validator attack runs at every scope: it measures the validator rather than any one map.

The one hand-written list is `FIXTURES`, the per-map citation grammars — three corpora, three
grammars, none derivable from a path. A new step holds it to the globs in both directions, so a
map added without a row fails the run instead of going unchecked, which is the shape of defect
`validate.sh`'s own header says this repository has shipped twice.

## What this does not decide

- **Whether CI uses the narrower scopes.** This adds the vocabulary; the workflows still run
  `--full` on every pull request.
- **Where the wall clock actually is.** It is the test suite, and the suite is not narrowed here.
- **Which checks a release could drop.** Only packing is narrowed, and only to the tagged map.
