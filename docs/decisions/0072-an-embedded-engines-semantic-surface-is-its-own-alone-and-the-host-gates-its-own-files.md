# 0072 — An embedded engine's semantic surface is the engine's own alone, and the host repository gates its own files

## Status

Accepted — 2026-09-29. Records the decision on
[#514](https://github.com/brandonifco/rules-factory/issues/514). **Amends
[0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)**'s
configuration section (§4, `.github/agent-policy.json`), which says what `review.semanticPaths`
holds and does not say what it is relative to. **Extends
[0069](0069-repository-level-automation-belongs-to-the-repository-root.md)**, which put an engine
beneath a repository root and did not say what that does to the surface a review is asked about.
**Changes no check, no emitted script and no line of the trust model**: it states what three checks
already do, so that the next reader does not have to read them to find out.

## Context

`review.semanticPaths` in `.github/agent-policy.json` is a list of globs the engine's own team owns:
`src/**`, `tests/**`, `overlay/**`, `corpus/**`. They are written relative to the engine, and since
[#507](https://github.com/brandonifco/rules-factory/issues/507) (and, for the review packet,
[#515](https://github.com/brandonifco/rules-factory/issues/515)) every reader of them takes a path
GitHub reports in the engine's own terms before matching:

* `tools/conformance-gate.py` decides whether a pull request owes the semantic verdict;
* `tools/review-packet.py` decides what the semantic cut of a packet contains;
* `tools/pr-policy.py` decides whether a pull request owes an entry and a locator.

Each calls `engine_relative(path, prefix)`, and each treats a `None` — a path not under the engine —
as not on the surface. For an engine that is its own repository root the prefix is empty and nothing
is dropped. For an engine embedded under a root (0069), everything outside the engine is: the host's
README, its own workflows, and anything else it holds.

A host repository can hold rule-bearing files. The case that found this is a private project that
authors its map in a script at the repository root, beside the committed map it produces and the
engine beneath. Neither file is expressible in `semanticPaths`, and the engine's semantic reviewer
saw that the policy could not say it.

In practice the gate still fires on such a change, because a change to the map regenerates
`src/**` and those files are on the surface, and the host's own workflow holds the generator to the
committed map. That is a side effect of how this engine is generated. It is not something the policy
promises, and a host file that decides a rule where the generated files do not follow it is the case
it would not cover.

## Decision

**The semantic surface is the engine's alone.** `review.semanticPaths` names paths inside the
engine, and only those. A file of the host repository is not on it, and this engine's rails make no
claim about one: not that a semantic verdict is owed for it, and not that it is not rule-bearing.

**A host repository is responsible for gating its own rule-bearing files.** What that gate is — a
workflow at the repository root that regenerates from the file and fails when the committed output
differs, a required review by the people who own it — is the host's choice, made with the host's own
policy. The factory emits none of it, for the reason 0029 §3's line gives: a consumer must not have
to undo something the factory chose for a repository it does not own.

**A `semanticPaths` string does not become a way to reach the host.** There is no form for it.
`../tools/build-map.py` and `engine/src/**` are strings the checks read as engine-relative and match
against nothing the engine holds, so a maintainer who writes one has written a line that does
nothing. `AGENTS.md` §9 of the emitted rails says so where an engine's maintainer reads about the
policy, so that line is not left to be found by its silence.

### What this does not change

* **No check moves.** `conformance-gate.py`, `review-packet.py` and `pr-policy.py` read
  `semanticPaths` exactly as they did. No test's expectation, no recorded hash of a script and no
  provenance format changes. `AGENTS.md` moves one recipe version, because its bytes change.
* **The trust model does not move.** The verdict gate is still an integrity check and not an
  authentication (0029, *Amendment*), and this widens nothing it lets through.
* **Standalone engines are unaffected.** Their prefix is empty; the surface is the engine, which is
  the whole repository.

### Why not the other option

The alternative in #514 was an explicit form by which a `semanticPaths` entry may name a path above
the engine. It is refused for now. Nobody has needed one: the one host that raised the gap is held
today by a generator check of its own, and a path form designed for a case that has not bitten is
designed without the case. It also costs something real. Every current string would mean the engine's
silently, and a second reading would have to be told apart from them by a marker every emitted
script must learn; a verdict about a host file would need the review packet to carry it, the
ownership table to classify it, and the produce predicate to say whether a change to it voids a
produce claim. Each of those is 0018 and 0029 reopened, for a file the factory does not write.

**What would reopen it.** A host repository that shows a rule-bearing file no generated file follows,
and that cannot gate it itself. That is a corpus forcing a concept, in the sense of
[0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md), and it is decided then, on that
file, as a new record that supersedes this one.

## Consequences

* An engine's maintainer who reads `AGENTS.md` §9 learns what `semanticPaths` is relative to and that
  the host owns its own gate. The emitted `AGENTS.md` moves to a new recipe version, with the previous
  version's hash kept: an engine produced from an earlier commit still carries those bytes, and the
  factory must keep recognising them as its own rather than as a local amendment.
* A host that is embedding an engine and holds a rule-bearing file the engine is not generated from
  has a finding to act on, and the finding is named, not inferred.
* The repair packet, unlike the three checks above, still matches repository-relative changed paths
  against the policy's patterns. That disagreement is a defect in that script, not a second reading of
  this decision, and is filed as [#535](https://github.com/brandonifco/rules-factory/issues/535).
