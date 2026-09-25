# How the backlog is organised

Two labels on every issue: **what kind of thing it is**, and **what it blocks**.

## Category — the project's own decomposition

| Label | What belongs in it |
|---|---|
| `schema` | The corpus map's shape. [0001](decisions/0001-the-corpus-map-is-the-interface.md) says the map is the interface, so a wrong schema is wrong everywhere downstream at once. |
| `method` | The written procedure a mapper or builder follows. Distinct from the schema: a correct schema with a method that contradicts it produces wrong maps, which is exactly how the delegated-standard entries got misclassified. |
| `enforcement` | A check that turns a stated rule into a fact. "A rule worth stating is worth a check" is the kernel's second governing principle and it applies here. |
| `rails` | What a produced engine ships with for the team that maintains it. |
| `evidence` | Measures whether the method works — trials, miss rates, the acceptance test. |
| `map-data` | An error in a specific map rather than in the schema. Cheap to fix, and worth keeping separate so a pile of them is not mistaken for a design problem. |
| `factory` | The factory's own implementation: intake, generation, the gate recipe, provenance, backlog, verify. Distinct from `enforcement`, which holds this repository's documents to their word; a `factory` defect is in what `tools/factory/` does to a produced engine. |
| `mapper` | The mapper subsystem: what turns a corpus into a candidate map — its protocol, its inventory, its sweeps, its blind staging. A sibling of the factory and not part of it ([0032](decisions/0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md)), so a mapping finding has an owner instead of being filed against `schema` and `method` for want of one. |

`documentation` (GitHub's default label) is used for text that is wrong about the code, such as
[#75](https://github.com/brandonifco/rules-factory/issues/75).

## Priority — distance from the next engine

The spine of this project is [#3](https://github.com/brandonifco/rules-factory/issues/3), the
acceptance test. Priority is not urgency; it is **what happens if you build the next engine
without doing this**.

### `p1-next-engine` — settle first, or the next engine inherits the defect

A schema defect costs once per engine, and migrating two engines costs more than deciding once.
Everything here is either a schema question, the enforcement that makes a schema answer real, or
data an engine would be built from.

The evidence for putting these first is concrete: the first engine was built from a map with
eleven errors in it, and the correction to `starting-position` invalidated an architectural
commitment the engine had already shipped.

### `p2-acceptance` — needed for the acceptance test, not blocking the next build

Measurement and the builds themselves. These are the work, not the preconditions for it.

### `p3-needs-two-engines` — cannot be generalised from one

Rails especially. Deciding what every produced engine ships with, from a sample of one board
game, is how the predecessor repository ended up encoding one team's operating model as a
framework. Wait for a corpus that is not a game.

**The hold is lifted for the rails, 2026-09-15.** `faa-part-107` is a regulation and
`srd-52-combat` is not backgammon, so the sample is no longer one board game. What the factory
emits, and where the line falls between it and one team's operating model, is
[0029](decisions/0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md).

### `review-p0`, `review-p1`, `review-p2` — findings of the September 2026 external review

The factory's code was reviewed from outside in September 2026, and each finding became an
issue. These labels carry the review's own priority, which answers a different question from the
`p1`–`p3` scheme: not what the next engine inherits, but **how badly the factory breaks its own
promises today**.

| Label | Meaning |
|---|---|
| `review-p0` | Breaks the factory's trust, correspondence or refusal promise: a package that runs code, pins that disagree with provenance, a refusal that leaves output half-written. |
| `review-p1` | The factory cannot yet prove its product or keep its relationship with it: an engine never built in CI, backlog issues matched by title, provenance blind to build inputs. |
| `review-p2` | Policy, provenance depth, maintainability and accuracy, including this README's status. |

A review issue carries a review label *instead of* a `p1`–`p3` label, and one or more category
labels as usual (#65 is `enforcement` and `factory`). The thirteen findings are one ordered list
(#65 to #77), P0 before P1 before P2, and each issue's first line gives its place in it:
"Review priority P2 (11 of 13)". Findings that were not in the review's priority table are
ordered after those that were, and the issue says so.

The two schemes answer different questions, and no decision orders one against the other. What
the labels do say: a `review-p0` or `review-p1` issue is a defect in the factory as merged, where
`p1-next-engine` is a question to settle before the next map or engine. The acceptance test
([#3](https://github.com/brandonifco/rules-factory/issues/3), `p2-acceptance`) runs through the
factory, so it measures a factory with whatever review findings are still open. The review labels
belong to that one review; work found later is labelled under the scheme above.

### `review2-p1`, `review2-p2`, `review2-p3` — findings of the 2026-09-16 review

A second review, of `factory/v0.8.1`, labelled the same way: a review label instead of a
`p1`–`p3` label, category labels as usual, and a first line giving the issue's place in the
review's one ordered list of twelve ("Review priority P2 (6 of 12)"). Two of the twelve were
already open, #157 and #8, and carry the label beside their own.

| Label | What belongs in it |
|---|---|
| `review2-p1` | Prove what exists before building more: the rails' live acceptance (#157), the dense cross-reference trial (#8), a second independent review, and status text that is true about `main`. |
| `review2-p2` | Maintainability and reproducibility of the factory as merged: refactors that change no output byte, floating CI tooling, the rails as their own bounded context. |
| `review2-p3` | Deeper trust that does not block 1.0: signed release tags, an expected package digest, an engine-owned domain-type contract, build attestation. |

The review's other recommendation is not an issue: hold new factory features until the P1 items
are done, and let real engine work, not anticipated needs, propose the next abstraction.

### `review3-*`, `review4-*` — independent reviews by Codex

Rounds three and four are the independent reviews #169 asked for, by a different model family,
of `ba1a27f` (2026-09-16) and `cc2cd9c` (2026-09-17). They use the same three levels as the first
review — `p0` breaks the trust, correspondence or refusal promise; `p1` the factory cannot prove
its product; `p2` policy, depth and hardening — with the same first line giving each issue's place
in its round. Every finding was verified against the code before it was filed, and several were
filed at a different level from the one the reviewer gave, each saying why. How a round is run is
[AGENTS.md](../AGENTS.md) §6. An open `review*-p0` issue blocks `factory/v1.0.0`, and a closed
`review*-p0` or `review*-p1` makes a release due (AGENTS.md §5).

### `review5-*` — the assurance-identity review

Round five is an independent assurance review of `9c94e0c` (2026-09-20), run under the same
section of [AGENTS.md](../AGENTS.md) §6 and reproducing each finding against the code before
filing it. Every implicated file was also compared against `main` at `161368e2` to establish that
the defect had not already been fixed, which is why each issue names two commits rather than one.

It found no `p0`, so the round uses two levels:

| Label | What belongs in it |
|---|---|
| `review5-p1` | The factory cannot prove its product: package certification unbound from the corpus bytes the baseline declares (#333), and review evidence recordable against a commit nobody reviewed (#334). |
| `review5-p2` | Policy, depth and hardening: a verified produce that can commit source the verification never saw (#335), an SDK override that contradicts managed-file provenance (#336), and a gate that reports discovered tests as executed (#337). |

**The round's ordered list is [#338](https://github.com/brandonifco/rules-factory/issues/338),
not each issue's first line.** That is the one departure from rounds one to four, and it is
deliberate: the five findings share a single failure mode, which #338 states —

> Artifact A is reported as verified using evidence produced from state B, but the handoff does
> not mechanically prove that B is the exact state embodied by A.

— and the order between them is an argument about which identity has to be bound first, rather
than five independent severities. #338 carries that argument and the remediation order; each
finding carries its own reproduction.

Read this round beside the release rule above. The round's findings began closing on 2026-09-20,
so `repo-hygiene.py` reports a release due; which of them are still open is what the `review5-*`
labels say, against a factory the next tag will ship. Stated that way on purpose: a count written
here is wrong the next time one of them closes, and this one already was.

### `review6-*` — the review of round five's own remediation

Round six is an independent Codex review of `34b6a71`, the commit at which every finding of round
five was merged. Its subject is not the factory as built but **the fixes themselves**: the round
closed six findings, and this asked what those six left unbound. It found no `p0`, so it uses two
levels, and its ordered list is [#375](https://github.com/brandonifco/rules-factory/issues/375).

| Label | What belongs in it |
|---|---|
| `review6-p1` | The factory cannot prove its product: a verified commit over a tree nobody tested (#370), and a packet that hashes one map and opens another (#371). |
| `review6-p2` | Policy, depth and hardening: a verdict on evidence the packet marks NOT VERIFIED (#372), bytecode exempt from the intactness check (#373), a test matrix that collapses two projects (#374). |

Nine findings were reported and five filed. #375 records **why each of the other four was not**,
which is the part worth keeping: one read a superseded branch, one is a limit `record-verdict.py`
and 0053 declare out of scope on purpose, one was already fixed on `main`, and one — folding
homoglyphs into the placeholder rule — is a limit [#240](https://github.com/brandonifco/rules-factory/issues/240)
asked to have **stated** rather than closed. A review round's value is in what it declines to file
as much as in what it files, and an unfiled finding with no reason recorded is one somebody will
rediscover and file again.

### `review7-*` — the review of the 1.0 release candidate

Round seven is an independent Codex review of `3d20430`, the commit frozen as the
`factory/v1.0.0` release candidate. Its subject is the whole product rather than a previous
round's fixes, and it was given the release directive's eight ship-blocking criteria and asked to
apply them strictly. It found **no p0** and recommended shipping. Its ordered list is
[#431](https://github.com/brandonifco/rules-factory/issues/431).

| Label | What belongs in it |
|---|---|
| `review7-p1` | The factory cannot yet prove something it claims: a named-test check that counts result files rather than target frameworks (#428), and a gate that consumes a restored package without comparing it with the digests intake recorded (#429). |
| `review7-p2` | The accuracy of a stated claim: the README saying provenance identifies the engine's source tree when it identifies a narrower subset (#430). |

Three findings were reported and all three filed, each with its reproduction. **#430 is the only
one fixed in the release candidate**, because the change freeze that governs a release candidate
allows documentation work exactly when a shipped claim is false, and this one was — verified by
running `provenance.is_build_input` over four paths. #428 and #429 are `post-1.0`: each is an
assurance gap rather than a demonstrated failure, and the issues say why neither meets criterion 4
or criterion 5.

**What the round did not examine is in #431 and is part of its result.** The reviewer's sandbox had
no writable temporary directory, so the full suite never started and no full-gate or .NET run is
claimed; the recovery, concurrency and publication paths were reasoned about rather than
exercised. Those are covered for this release by other evidence — CI ran the full gate and a
produced engine green on the reviewed commit, and rounds five and six are what read the recovery
paths — and saying so is the point. A round that reports what it could not reach is what makes the
rest of its verdict worth something.

### `review8-*` — the review of the context-cost rails, 2026-09-24

Round eight is an independent Codex review of `b4bfceb`, run read-only against a detached worktree
pinned to that commit and given no earlier reviewer's conclusions. Its subject is narrow and was
named in the brief: the five changes merged since `68c1218` that exist to reduce what an agent
re-reads — [#465](https://github.com/brandonifco/rules-factory/issues/465) the repair packet and
"one agent, one attempt", [#466](https://github.com/brandonifco/rules-factory/issues/466) the
orchestrator's status report, [#467](https://github.com/brandonifco/rules-factory/issues/467)
`--role` and the verdict's role binding, [#470](https://github.com/brandonifco/rules-factory/issues/470)
the gate's `--brief`, and [#475](https://github.com/brandonifco/rules-factory/issues/475) the
semantic cut naming what it withheld. Its ordered list is
[#485](https://github.com/brandonifco/rules-factory/issues/485).

It found **no p0 and no p1**. Nothing it found weakens provenance integrity, the verdict-to-commit
binding, [0053](decisions/0053-a-review-verdict-binds-the-exact-packet-and-reviewed-commit.md)'s map-byte
binding, the read-only reviewer rule, determinism, or "a check that examined nothing is a failure".
It demonstrated no way to turn a FAIL into a pass and no merge bypass.

| Label | What belongs in it |
|---|---|
| `review8-p2` | **A tool asserting something it did not establish.** Twelve findings, every one an instance of that: a packet cut from a file list GitHub truncates (#478); a report that says it is read-only and rewrites the git index (#479); counts from truncated queries, swallowed local failures, and an exit code that ignores the branch (#480); a `--brief` that can lose the output it says it kept and keep it where it must not (#481); a repair brief pointing at a worktree nobody checked (#482); a repair brief asserting two things the repository contradicts (#483); and a section parser that drops what is nested under the heading it kept (#484). |

**Why twelve findings are seven issues.** Findings in one file and about one rule are one issue,
and each issue says which findings it carries. That is a judgement this round made and recorded
rather than a convention; a reader who wants the twelve has them in #485.

**#483 is the only one that weakens a protection the rails already had.**
`tools/dispatch-agent.sh` refuses to dispatch an issue in the needs-decision or blocked state, with
the reason written beside the refusal, and a repair brief — which is an implementation brief —
evaded it.

**What it declined to file is part of the result.** It dropped the concerns that a structural packet
needs the map's bytes, that shared helpers are hidden from the semantic cut (the default `src/**`
pattern includes them), and that the role check proves a reviewer read what it was given: "the code
supports none of those claims". On the last it is exactly right, and says the useful half out loud —
the check closes incompatible-role use of an honestly generated packet and cannot establish that
anybody read it, which is the same boundary `AGENTS.md` §7 already states about verdicts. An
independent reviewer confirming a stated limit is worth as much as one finding a defect.

**What it did not examine** is the map and corpus work in the same commit range, which the brief put
out of scope. It read source, tests and the installed git documentation, created no files, and left
the pinned worktree clean; the worktree was removed when the findings were filed (`AGENTS.md` §6).

### `post-1.0`, `known-limitation` — the ship-first triage, 2026-09-21

An open issue records knowledge. It does not authorise implementation. From 2026-09-21 every open
issue carries a disposition, and a finding delays a release only when it is demonstrably one of
these: the factory cannot produce, update, verify or maintain a real engine; it can silently
generate materially wrong code from a valid supported input; it can overwrite or discard
engine-owned work; it can report an engine as verified when its build or tests failed or did not
run; its map, package or provenance inputs can be substituted in a way that defeats the claims
ordinary use rests on; a real corpus shows the map contract cannot represent a rule category the
supported product needs; normal installation, operation or upgrading is impractical for the
intended user; or a concrete security or supply-chain defect is a realistic risk for the
distribution model as it actually is.

| Label | What belongs in it |
|---|---|
| `post-1.0` | A real improvement — hardening, an abstraction, broader checking, better ergonomics — that meets none of those. Filed, kept, not implemented before the release. |
| `known-limitation` | A boundary of the product rather than work: it is stated where a reader will meet it, and built only when real use forces it. |

The two labels exist because the failure this project was drifting into is not under-checking. It
is the recursive one: a mechanism, then a checker for the mechanism, then evidence proving the
checker, then provenance proving the evidence. A check earns its maintenance by protecting a
product-critical invariant; one that does not is simplified or removed, and a claim that is hard
to verify is narrowed rather than propped up by another layer. An explicit, truthful limitation is
a finished outcome, not a deferred defect.

## The hub

[#24](https://github.com/brandonifco/rules-factory/issues/24) is not one issue among the
`p1-next-engine` set — it subsumes five of them. #6, #10, #11, #15, #19 and #23 are one question
asked six times, answered in
[0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md). Work #24 and most of the
`schema` label closes with it.

## What this ordering is betting on

That the vocabulary has converged. Trials 3 and 4 produced new *instances* of the six situations
and no new *kinds*, which is the signal that a decision can be derived rather than guessed. If a
regulation engine produces a seventh kind, this ordering was wrong and the schema work should
have waited. That is the bet, and it is recorded here so it can be judged later rather than
rationalised.
