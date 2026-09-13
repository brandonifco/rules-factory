# 0001 — The corpus map is the interface, and it comes before the scaffolder

## Status

Accepted — 2026-09-13.

## Context

The goal is to drop a plain-language ruleset into a repository and have a team of agents
build a deterministic engine from it. Two engines have been built this way by hand, and both
are real: one over a commercial RPG rulebook, one over a CC-BY SRD, 746 merged pull requests
between them.

In both, the decomposition — turning prose into a backlog of implementable units — happened
in one person's head, one issue at a time. That works and it does not scale, and it is the
only part of the process that is genuinely hard. Everything else downstream (implement, test,
review, record) is already proceduralised and already works.

The temptation is to build the scaffolder first, because scaffolding is tractable: copy a
skeleton, rename things, write a manifest, emit a repository. But a scaffolded repository
with no decomposition is a template, and templates were already tried. The predecessor
attempt produced exactly that, and its remaining gap was never the scaffolding.

## Decision

The factory's interface is **the corpus map**: a structured entry per rule the corpus states,
specified in [../corpus-map.md](../corpus-map.md). Intake produces it; the backlog, the
implementation order, and the engine's own account of what it cannot do all derive from it.

Agents are dispatched against map entries, never against the corpus.

The map is specified, and the method that produces it written, **before** any scaffolding
code. Not as a documentation exercise — because the specification is what forces the
decisions. Writing it surfaced that a digest does not say what it covers, that boundary
policy is a property of the licence rather than of the repository, and that the map's
categories and the kernel's runtime `UnresolvedReason` vocabulary are the same five
categories seen from two sides. None of those would have surfaced by writing a file copier.

## Alternatives considered

**Scaffolder first, decomposition later.** Rejected: it delivers a template, and the
template's missing half was always the decomposition. It would also have hard-coded
assumptions the specification has now shown to be wrong.

**No intermediate representation — agents read the corpus directly per issue.** This is the
status quo in both existing engines. It works, it does not scale, and it produces
inconsistent decomposition because every agent re-derives what a unit of work is.

**A richer representation — a formal rule language.** Rejected as premature. The map records
where a rule is, what kind it is, what it depends on, and whether it is settled. It
deliberately does not attempt to represent what the rule *says*; that is the engine's code,
and a representation that tried would be a second implementation to keep in step with the
first.

## Consequences

The factory cannot be evaluated until a map exists for a real corpus, which makes the first
real intake the first meaningful test of this entire repository.

The map becomes a maintained artifact in every produced engine, not a build-time
intermediate. Its `status` fields make claims about the engine that the engine could
contradict, so the correspondence between map categories and runtime unresolved reasons must
become a check rather than a convention.
