# The agent team

Four roles. [`AGENTS.md`](../AGENTS.md) is the contract they all work under; this file says who
does what, and what each one may not do.

**A role is added when a failure mode demands one, never in anticipation.** There is no architect
agent, testing agent, documentation agent, GitHub agent or security agent here. Each of those
mostly adds a handoff: another context to load, another summary to trust, another place for a
fact to be lost in translation. If a recurring failure appears that none of these four can catch,
that is the argument for a fifth, and it belongs in a decision record with the evidence.

---

## Orchestrator

The main session. It holds the project's context across issues, which is exactly what the other
three deliberately do not.

**Does:** groom the backlog; classify risk; dispatch one ready issue at a time; collect reviews;
start a fresh attempt when a review sends work back; escalate to the owner; merge; clean up
worktrees and branches afterwards; keep the primary checkout clean on `main`.

**Does not:** implement ordinary issues in the primary checkout. An orchestrator that starts
editing is no longer holding the thread it exists to hold, and its edits land where nothing
isolates them.

**Judgement it owns:** whether an issue is high risk, when an escalation goes to the owner, and
whether a review finding is blocking. It does not own the answer to a rules question — that is
the owner's, recorded (`AGENTS.md` §6).

**What it does not hold is the project's state.** It holds the *current scheduling decision*, and
reads the rest with `tools/orchestrator-status.py` (`AGENTS.md` §3). That is the whole of how a
fresh orchestrator resumes, and resuming is ordinary: in the measured session, 51.1M effective
tokens went on carrying and re-reading orchestration history, against 4.3M for every scheduling
decision it wrote.

## Engine developer

Implements exactly one ready issue, in exactly one worktree, on exactly one branch, opening
exactly one pull request that closes exactly that issue — in exactly **one attempt**.

One instance is one attempt: implement, validate, open or update the pull request, stop. A
blocking review finding starts a *new* instance against the same issue, branch, worktree and the
current head, briefed by `tools/repair-packet.py <pr number> --finding "..."` (`AGENTS.md` §4).
This is not a fifth role. It is this one, invoked again, narrowly — which is the opposite of what
the rule at the top of this file guards against, and is why "repair" gets a packet rather than a
charter.

**Does:** read the issue and the entry it names; write the smallest implementation that satisfies
it; write the tests and record each test's mutation in the overlay; regenerate what the factory
generates; run `./scripts/validate.sh full`; open the pull request with real evidence in it.

**Does not:** resolve a genuine ambiguity (`AGENTS.md` §6); remap the corpus or edit the map
(§5); widen the change beyond the issue; edit the gate to make its change pass; bulk-stage.

**May edit:** this engine's source, its tests, its overlay, and the decision records the issue
calls for.

## Repository steward

Cheap, **read-only**, structural review on every pull request. It runs **first**, before semantic
review, so that a scope or evidence defect is found before expensive reasoning is spent on a
change that is going back anyway.

**Runs on the cheaper tier**, and "cheap" here is a dispatch instruction rather than a
description. What this role checks has a right answer that does not need the model that catches a
fluent implementation of the wrong rule; running it on the same tier as the next role costs the
same as the review it exists to run before, and buys nothing. See *What a turn costs*, below.

**Reads:** the packet cut for this role — `tools/review-packet.py <pr number> --role structural`
— which is the whole context, and nothing here needs rediscovering from the diff. It carries the
pull request's claim in full, because judging that claim is this role's, and the changed paths
with the ownership class of each, because the first thing this role asks is whether a generated or
managed file was hand-edited. It carries **no entry packet**: what the rule says is the next
role's, and a cut that leaves it out needs no restored map package to make, which is part of what
makes this review the cheap one. Keep the adjacent `*.review.json`: it records which bytes you
were given.

**Checks:** the change is within the issue's scope and contains nothing unrelated; generated
files were not hand-edited and the ownership classes are respected; the determinism rules hold;
provenance and citations are present; the overlay's mutation evidence is real and specific;
documents and decision records that the change contradicts were updated; the pull request
template is filled with actual output rather than claims.

**Does not:** fix what it finds, or judge whether the implementation reads the rule correctly.
That is the next role's, and a structural reviewer that starts arguing semantics stops being
cheap.

## Rules conformance reviewer

High-reasoning, **read-only**, semantic review: does this implementation actually do what the
mapped rule says?

**Runs on the deepest tier available, and is the role not to economise on.** It is the one that
catches a well-tested, fluently argued implementation of the wrong rule, which is the defect no
other role in this team can see. A cheaper pass here does not find less; it finds nothing and
reports that it found nothing.

**Reads the entry packet before it reads the implementation** (`tools/review-packet.py <pr>
--role semantic` assembles both, in that order, and leaves out the pull request's own argument).
Anchoring is the failure this role exists to catch, and a reviewer who reads the code first will
find the code's reading of the rule persuasive, because it was written to be.

**Tries to falsify.** Finite tables are checked exhaustively rather than sampled; boundaries are
checked at and either side of every stated threshold; gating and ordering are checked in both
directions; every unresolved case is checked for citing the right reason and the right locator.

**Does not:** fix findings, negotiate them down, or accept "the implementer explained it in the
pull request" as an answer. Where two reviewers disagree, the packet and the map decide — not
seniority, not the model, not the implementer's explanation.

---

## What a turn costs, and what follows

This section exists because the tiering above is a cost claim, and a cost claim with no numbers
behind it is the kind of sentence that stays true-sounding after it stops being true. It is
vendor-neutral on purpose: which model is which tier is the engine team's choice, and where that
choice is written down for a given vendor is that vendor's adapter.

**An agent's cost is its number of turns multiplied by the size of its context, not the size of
what it prints.** Context grows monotonically within one agent's life and every later turn pays
for the whole of it. Measured over one live run of this team on a real engine — six agents, 65.9M
raw tokens — the most expensive agent spent **81%** of its cost on re-reading context, 16% on
writing it, and **2.6%** on its own output. Everything it printed all run, every test result and
every file it read, came to 0.26% of its raw tokens.

Four things follow, in the order they are worth acting on:

1. **A narrow assignment is cheaper than a wide one by more than its share of the work.** In that
   run a narrowly-scoped follow-up fix did real work at an 84k peak context; the implementer it
   followed reached 275k and cost seven times as much. The packet is what makes an assignment
   narrow (`AGENTS.md`), so an orchestrator that widens a brief pays for it on every subsequent
   turn of that agent, not once.
2. **Batch an inner loop into one invocation rather than driving it turn by turn.** A mutation
   loop run interactively is a dozen turns over a context that is already large; the same work
   through one command is one. This is why the contract names a tool for it instead of leaving
   the loop to each implementer.
3. **Tier the reviews, and tier them the right way round.** In that same run both reviewers ran
   on the top tier and the "cheap" structural review cost **2% more** than the semantic one —
   together a third of the whole session, for one pull request. The saving is in the first
   review; the second is where the money should go.
4. **End the agent at the review boundary.** Because context grows monotonically and never
   shrinks, a conversation that survives review after review is the one shape of agent whose cost
   compounds. A larger run — 72 agents, 797 turns, 280M effective tokens — put **59%** of itself
   into implementers, and its worst single implementer spent about 45M effective tokens over
   roughly eight review rounds it stayed alive through. One instance is one attempt
   (`AGENTS.md` §4), and the next attempt reads the repository rather than the last one's
   transcript.

**What none of this justifies.** Skipping the semantic review, sampling instead of checking
exhaustively, or accepting a thinner verdict because a thorough one is dear. The cost of the
review that sends a pull request back is small against the cost of an engine that reports a rule
wrongly, and this section is about spending the budget in the right place rather than spending
less of it.

## Independent review

An issue classified as high risk needs a second, independent verdict, from the first available
provider in the chain in `.github/agent-policy.json` (`review.independentFallback`).

The value of that verdict is **independence**, not throughput. A reviewer from the same family as
the implementer tends to reproduce the implementer's misreading, which is the exact failure a
second verdict exists to catch — so a fallback to another in-house pass is a real weakening,
accepted deliberately to avoid every merge being blocked by one provider's outage, and made
visible by recording the verdict under its own context rather than a generic one.

**The independent reviewer receives** `tools/review-packet.py <pr> --role independent`: the entry
packets, the issue's acceptance criteria, and the current bytes of the change in full. **It does
not receive any other reviewer's conclusions** before producing its own — not a finding, not a
repair discussion, and not the pull request's narrative, which by the time an independent review
happens is often a record of what earlier reviewers asked for. That packet says so in a section of
its own, because independence is a property of what a reviewer was handed rather than of its
intentions.

A verdict is recorded with `tools/record-verdict.py --pr <n> --packet <packet.review.json>
--reviewer <id> --verdict pass|fail`. The recorder verifies the human/entry packet digests, uses
the review context captured from that reviewed commit, and refuses if the pull request has moved.
`tools/conformance-gate.py` requires the resulting status at the commit being merged. Recording
it is the whole of the step: `.github/workflows/verdict-requeue.yml` asks the gate to report again
at that commit, so a gate still red for a moment afterwards is bookkeeping catching up, not the
verdict failing to register.

**The chain advances because a provider was unavailable, never because its verdict was
unwelcome.** Unavailable means it could not be reached or returned no verdict at all. A provider
that returned a fail was available: the answer is to fix the code, fix the map, or get an owner's
ruling — never to ask another provider until one agrees. A recorded fail at any configured
context blocks the merge outright, and a later pass elsewhere does not clear it.
