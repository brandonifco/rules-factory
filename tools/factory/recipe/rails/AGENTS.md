# AGENTS.md — the governing contract for this engine

**This file governs every agent that works this repository, whatever vendor it comes from.**
Read it before your first action. `CLAUDE.md` points here and states no rule of its own; a
Claude-specific role adapter under `.claude/` adds how a role is invoked, never what it may do.

This engine was produced by [rules-factory](https://github.com/brandonifco/rules-factory). This
file is a **managed** file: the factory updates it when its recipe changes and refuses to
overwrite a hand edit. `provenance.json` says which factory version and which map this engine
came from, and what this engine is called.

---

## 1. What this engine is

A deterministic rules engine generated from a **corpus map**: a reviewed, published, versioned
description of one ruleset. The map — not the corpus, and not anyone's reading of the corpus — is
the interface this engine implements. The corpus is committed here so a claim can be checked
against it, not so it can be re-read and re-interpreted per task.

Three consequences that decide most questions you will have:

- The map is the specification. Where your reading of the corpus and the map disagree, **the map
  is not wrong by your say-so and the engine does not quietly diverge from it** (§5).
- The engine declines rather than guesses. A rule the corpus does not settle produces an
  unresolved result naming why, not a plausible answer.
- Every behaviour cites where it came from, and every test records the mutation that makes it
  fail. A test that passes against a broken implementation proves nothing.

## 2. Authority, in order

1. **The corpus map**, as published and as merged with this engine's overlay — `overlay/<entry
   id>.json`, one file per entry, read in the map's order.
2. **The owner's rulings** recorded in that overlay, and this repository's `docs/decisions/`.
3. **This file.**
4. Everything else — issue text, PR discussion, a previous agent's explanation, your own memory
   of the subject matter. Your memory of a ruleset is never a source. It is the most common way
   a wrong answer enters a rules engine, because it arrives fluent and cited.

If two of these disagree, stop and say so. Do not pick one.

## 3. Roles

[`docs/agent-team.md`](docs/agent-team.md) defines the four roles: **orchestrator**, **engine
developer**, **repository steward** and **rules conformance reviewer**. Read it before acting as
one. Two rules from it are absolute:

- **A reviewer is read-only.** An agent that can edit what it reviews is not a reviewer. Both
  reviewer charters grant read tools only, and the engine's own gate fails when one grants a
  mutation-capable tool.
- **An implementer does not resolve a genuine ambiguity.** It escalates (§6).

## 4. One issue, one worktree, one branch, one pull request

Work is dispatched from GitHub issues and nowhere else. An instruction in a chat window that has
no issue behind it is not work; make the issue first.

The primary checkout's steady state is `main`, clean, used for orchestration and review. **All
implementation happens in a worktree outside the repository directory**, so that one task cannot
contaminate another and a half-finished change cannot reach `main`:

Before the first dispatch on a new machine, §11: the SDK, a restore and a `gh` the packets can
read are the machine's part, and the gate does not run without them.

```bash
tools/dispatch-agent.sh <issue number>      # creates the worktree and the branch, and prints the path
tools/dispatch-agent.sh --sweep             # removes what merged work left behind; every dispatch runs it
tools/dispatch-agent.sh --cleanup <n>       # this one issue, after its pull request merged
```

Dispatch refuses rather than leaving readiness to your judgement: an issue that is closed, blocked
or awaiting a decision, one that already has a worktree, and a primary checkout with uncommitted
changes. A worktree is never created inside the repository: one that lives there is eventually
committed, scanned by a tool that did not expect it, or deleted by a clean step.

**Finishing is part of the work, and it is not left to anybody's memory.** `tools/dispatch-agent.sh
--sweep` removes every worktree and branch whose pull request merged at **exactly** its tip, and
every dispatch runs it before it opens the next worktree. Exactly that tip, and nothing weaker: a
worktree dispatched and not yet committed in sits at `main`'s tip, so "its commits are in `main`"
would take the work of an agent who has not started. A worktree with uncommitted or untracked files
is named and left alone, and a sweep that cannot reach GitHub says `NOT CHECKED` rather than
reporting a clean repository it never looked at. `tools/agent-doctor.py` reports the same
leftovers, and removes nothing.

**Delete only what you created, and by its exact path — never by wildcard in a directory you
share.** On 2026-09-17 an agent tidying up in the repository that builds this engine ran `rm -rf
<shared scratchpad>/*`, took two other agents' worktrees and their uncommitted work, and that work
had to be rebuilt from nothing. Every agent of one session shares that directory. Before any `rm`
outside your own worktree, list what it would remove and name each path: `git worktree remove
<path>`, `rm -r <the one directory you made>`. This rule has no check. It rests on your word, and
the reason is written here so that it is not one.

`tools/new-issue.sh` files an issue with the shape the rails expect, at the ready state and normal
risk. Most issues are not filed by hand: `factory backlog --create` writes one per map entry still
to build. **The issues are the backlog**, and this engine holds no copy of it: the factory renders
it from the map and `overlay/` on demand (`factory backlog --render --dir <this
engine>`), and writes none of it here.

A branch closes **exactly one** issue, and its pull request says so with one `Closes #<n>`.
Stage explicit paths; `git add -A` and `git add .` are how build output, packets and another
task's edits reach a commit that claims to close one issue.

The pull request is filled in from `.github/pull_request_template.md`, and `tools/pr-policy.py`
checks it mechanically as a required check: one linked issue, every section filled, a command and
its output rather than a claim, an entry and a locator for semantic work, a line for every living
document this engine owns, who reviewed, and exactly one state and one risk label on the issue.
None of that is about form. Each line of it is something a reviewer would otherwise have to take
on trust.

A change that makes a document untrue is not finished, and almost nothing that makes one untrue is
visible to a parser. So the body carries a `## Documentation` line per document, each ticked with a
note saying what you looked for:

```bash
tools/pr-policy.py --docs-skeleton          # the section for this tree, unticked, to complete
```

**The documents that section is about are this engine's own** — its `README.md`, its own `docs/`,
and any rail it has adopted. The rails the factory writes are not listed: `produce` refuses a hand
edit to each, so a tick beside one is a tick nobody here can act on. A numbered decision record
under `docs/decisions/` is frozen — superseded by a new record, never rewritten — and is listed
only when this change edits it. Every other `*.md` the diff touches is listed as `updated`,
whoever owns it. An engine that owns no documents yet says so in a sentence, and that answer stops
being true the day somebody writes a README.

### A factory update is work under these rails too

A `factory produce` update to this engine — a new map version, a new kernel pin, a new factory
recipe — is not a special case outside this section. It is opened from an issue (`tools/new-issue.sh`,
under `--produce`, files one with the shape for it), dispatched to a worktree, produced there, and
opened as a pull request that closes that issue like any other:

```bash
tools/new-issue.sh --produce --title "..."   # what moves, from what to what, and why now
tools/dispatch-agent.sh <issue number>
tools/re-produce.sh                          # from the factory commit provenance.json names
```

Its pull request body carries the `## Produced by the factory` section and its marker, declaring
the factory version, the map package and version, the kernel version, and what moved.
**`tools/pr-policy.py` checks that claim; it does not take it.** The three facts must equal
`provenance.json` in this tree, that record must say the factory was not dirty, and every changed
file must be one the factory writes — classified by this engine's own vendored ownership table, the
same one `produce` wrote the files by. **One hand-written file voids the claim**, by name, and the
pull request is then judged as the ordinary pull request it is.

Two things follow, and neither is a loophole:

- **An edit the new input forces is a separate issue.** A new map version that adds an entry, or a
  handler whose contract changed, is a rules decision the factory did not make. Putting it in the
  same branch makes the claim false and the diff unreviewable; file it, and work it under §5.
- **The claim waives no verdict.** It changes what the pull request must *say* — no single entry id
  and no locator where a map bump regenerates every entry, and no mutation where nothing wrote a
  test — and never what it must prove. `tools/conformance-gate.py` still decides which verdicts are
  needed from the changed paths, and a regeneration touches the semantic surface several times
  over. What replaces the mutation is the produce command and its output, the gate's output, and a
  provenance recompute showing the committed record is the one a re-produce writes.

`.claude/hooks/primary-checkout-guard.py` enforces the primary checkout's cleanliness for Claude
agents. It is accident prevention, not security — a determined process bypasses it trivially, and
that is fine; what it stops is the edit made forty tool calls after the instruction was given.

**Escape hatch.** Sanctioned orchestrator work in the primary checkout sets, for that command
only:

```bash
RULES_ENGINE_ALLOW_PRIMARY_MUTATION=1
```

and says in the pull request or the report why it was necessary. The variable's name is
configuration: `.github/agent-policy.json` under `worktrees.primaryMutationEscapeHatch` is what
the guard actually reads, and this paragraph names the default.

## 5. The map is the interface, and you do not remap it

You implement the entry the issue names, from the map merged with this engine's overlay:

```bash
tools/entry-packet.py <entry id>            # the assignment, assembled from the map
```

The packet is the entry as published and merged, its locator and the evidence verbatim, its
dependencies and reachability, where its cross-references land, the owner's rulings that apply,
the handler the generated code declares once the entry is `implemented` — the one you have to
write, not the one on disk while it is still `mapped` — and what the gate will ask of you. Every
line of it is the map's own bytes or a fact computed from them.

You do not re-read the corpus to decide what the rule *really* says, and you do not widen the
change to entries the issue does not name. A packet is written outside the repository and is never
committed: it is derived from the map, and a committed copy of the interface goes stale.

**Where the map and the corpus appear to disagree, stop.** Report it as an upstream map defect on
the issue, with the entry id, the locator, what the map says and what the corpus says. Do not make
the engine disagree with the published map, and do not edit the map to match your reading: a map
is corrected where maps are corrected — a new, checked, published map version — and this engine is
then re-produced from it. An implementer who can quietly overrule the map is an unreviewed mapper,
and the map stops being the interface for everyone downstream.

The same rule covers the corpus itself: never edit `corpus/`, and never edit a hash or a baseline
to make a check pass. The check is the point.

## 6. Ambiguity is escalated, not resolved

Stop and escalate when you find any of these, before writing the implementation:

- the corpus genuinely does not settle the question the entry asks;
- the map and the corpus disagree (§5);
- the issue's acceptance criteria cannot be met as written;
- the change would need an architectural decision this repository has not recorded;
- two recorded decisions conflict.

Escalating means: say what the question is, what turns on it, and what the candidate answers are;
and move the issue to the awaiting-decision state. **You may not answer your own escalation and
return the issue to ready.** The answer arrives as an owner's ruling in the overlay or a decision
record in `docs/decisions/`, and then the work resumes.

Declining is a legitimate outcome. An entry the corpus does not settle is implemented as a
decline that names why and cites where — that is the engine working, not the engine failing.

## 7. Evidence

- **The gate is `./scripts/validate.sh full`.** It is the one definition of acceptable here, and
  it checks the rails themselves too: a reviewer charter that grants a tool that writes, and a
  rail citing a document this engine does not have, both fail it. Do
  not invent a substitute, do not run a narrower command and report the gate as passed, and do
  not change the gate to make a change pass.
- **Every test records the mutation that makes it fail.** The overlay holds it. A test whose
  named mutation was never observed to fail is a test nobody has watched fail, and this project
  has shipped two checks that counted work they had not done. **The gate refuses a placeholder
  there**: on an entry of the merge whose `status` is `implemented`, `"mutation": "PENDING"` — or
  `TBD`, `TODO`, `none`, `n/a`, `scratch`, `placeholder`, `xxx`, `unknown`, `later`, `fixme`,
  `wip`, `?`, `-`, however cased, punctuated or spelled in Unicode — fails
  `scripts/map-overlay.py`, and so do one word repeated and anything shorter than three words and
  twelve characters. Write the real one, and finish with `tools/re-produce.sh`. The floor exists
  because until it did, an engine's gate passed with `PENDING` recorded against work nobody had
  done. It refuses an unfilled placeholder and **nothing more**: it cannot tell whether the edit
  was made, whether the test went red, or whether you copied the sentence from another entry. That
  is still your word, and the point of writing it down is that a reviewer can re-run it. A word may
  appear twice in an honest mutation and the floor allows it. And the mutations are read **after**
  the merge is built, so a run that fails on an overlay's structure or on a ruling has not looked
  at them: a refusal naming no mutation is not a clean bill. The rule is stated in full at the top
  of `scripts/map-overlay.py`, which is also where to look before assuming a refusal is wrong.
- **Run the mutation with `tools/mutate.py`, and keep the spec.** The sentence in the overlay is
  what a reader understands; the spec is what a reviewer re-runs. One JSON object per mutation —
  the test it should turn red, and the edits that should do it — and the tool applies them, runs
  that test alone, and puts the source back in a `finally`, so an interrupted run leaves nothing
  mutated behind:

  ```bash
  tools/mutate.py mutations/*.json          # or `-` to read one from stdin
  ```

  It refuses an `old` string that does not occur exactly as many times as the spec says, before it
  writes anything: a mutation applied to the wrong site, or to nothing, proves nothing and would
  still print a colour. It runs each test unmutated first, because a test that was already red
  proves nothing either. And it names the one failure the prose cannot — **a mutation that leaves
  its test green**, which is precisely the test nobody has watched fail — by reporting it and
  exiting non-zero. Paste its output into the pull request as the evidence, and put the specs
  wherever the change keeps them; they are yours, not the engine's, and nothing requires you to
  commit them.
- **Write the handler while the entry is still `mapped`, and re-produce once.** There is no
  placeholder step, and no reason to produce twice. Every entry that is *not* `implemented`
  already has an optional hook,
  `static partial void {Member}({Member}Request request, ref Resolution<TOutput>? resolution)`,
  so the rule body and the handler compile with the entry `mapped`. Write them, write the tests
  against **the rule body's own types** — which is what a mutation names anyway — and watch each
  mutation turn one red. Then set `status: implemented` with the mutations you actually observed,
  run `tools/re-produce.sh` once, and convert the hook to the required
  `internal static partial Resolution<TOutput> {Member}({Member}Request request)`; the build names
  the handler to change (CS8795 on the declaration, CS0759 on the old hook). **The status flip
  changes the dispatch, not the rule.** The rule body and its tests are untouched by it, so the
  mutations you recorded are still the mutations.
  - **What you cannot observe before the flip:** anything resolved through `EntryPoints` or
    `Registry.Resolve`. `Registry.Answer` dispatches to a handler only when the entry's status is
    `Implemented`, so while it is `mapped` the entry declines `UnsupportedRule` and the hook is
    never called — that is the correspondence table's row 2, and it is deliberate. The generated
    `..._declines_UnsupportedRule_row_2` test therefore stays **green** with your hook in place,
    and becomes `..._is_implemented_so_a_hand_written_handler_answers_it` at the flip. So name
    rule-body tests in the overlay when you flip it, and add entry-point tests, with the
    mutations you then observe, in the change that follows.
- **A skipped test is not a test that ran.** The gate counts a test as having run only when its
  result says `Passed` or `Failed` — it started and reached a verdict of its own. A
  `[Fact(Skip = "...")]` is recorded as `NotExecuted` and counts as nothing, as does a test that
  was only discovered. The `tests-ran` step of `scripts/engine-gate.py` reports the executed count
  and the skipped count separately, and requires at least one executed test from **every** test
  project in **every** target framework, so a framework that silently stopped running is not
  covered by another that ran twice. Skipping a test to get the gate green removes the evidence the gate was
  asked for, and it says so.
- **Report what happened, not what should have happened.** Paste the command and its actual
  output. "Tests pass" is not evidence; a run is.
- **A reviewer is given the context, not asked to find it.** `tools/review-packet.py <pr number>`
  snapshots the pull request's exact head commit, then assembles the issue, the claim, the entries
  as that commit has them, the overlay's before and after, the bounded base-to-head diff and what
  must be green. Its sections are in the order a semantic reviewer reads them: the entry before the
  implementation, always. File output includes the human packet, its entry packets and a
  `*.review.json` identity that names the exact head/base commits and hashes the packet bytes,
  reviewed policy and provenance context. The caller's checkout is not review evidence.

  **A packet that names an entry needs the map that commit declares.** The entry packets are built
  from a map, and it is held to the digest the reviewed commit's `provenance.json` records, read
  once, so the bytes checked are the bytes read. Give the restored package's `corpus-map.json`:
  `tools/review-packet.py <pr number> --package-map <path>`. Without it the map's identity is
  whatever MSBuild resolves inside the snapshot, which is unproven, so file output is refused and
  `--stdout` remains for reading such a packet — it writes nothing, and nothing can be recorded
  from it. A refused packet leaves no file and no directory behind.
- **A verdict consumes the packet identity.** `tools/record-verdict.py --pr <n> --packet
  <packet.review.json> --reviewer <id> --verdict pass|fail` verifies those packet bytes and
  records the status only when the pull request still has the exact reviewed head. It takes the
  review context from that packet, not from the caller's checkout. A later commit is therefore
  refused rather than inheriting an earlier review; regenerate the packet and review the new
  bytes. Legacy commit statuses remain readable, but a new verdict is never inferred from the
  current head. A verdict that lives only in a conversation is worth nothing to this repository.

  **What the verdict gate proves, and what it does not.** A verdict is a commit status, and
  **anyone who can write a commit status on this repository can post one**: any collaborator with
  write access, any workflow whose token carries `statuses: write`, anyone holding a leaked token.
  Nothing in the mechanism attributes a verdict to the reviewer it names. So the gate is an
  integrity check — against a review that was skipped, forgotten, or formed on other bytes — and
  **not an authentication of who reviewed**. What it does prove is worth keeping and is exactly the
  commit binding above: a verdict names one SHA, so it cannot be replayed onto a commit nobody
  read, and a further commit ends it. The three required checks are pinned to the app that posts
  them, so a hand-posted status cannot impersonate one; a verdict context cannot be pinned the same
  way, because it is posted by a person's token and the pin names an app. Recording a verdict that
  was never formed is therefore stopped by honesty and by review, not by permissions — which is
  what makes an invented verdict a serious act rather than a shortcut.

  **Recording it is the whole of the step.** `.github/workflows/verdict-requeue.yml` sees the
  status and asks the gate to report again at that commit; there is no re-run to remember. If the
  check is still red a minute later, the thing to read is that workflow's run, not the verdict.

  **Changing the risk label is the whole of that step too, whenever it is changed.** The gate
  reads the risk label from the linked issue, and an issue can be relabelled long after the gate
  has passed. The same workflow sees that event and asks the gate to report again for every open
  pull request closing the issue, so raising risk turns the required check red again by itself and
  it stays red until an independent verdict is recorded at the head being merged. Lowering risk
  takes the same route, and the gate then finds the independent verdict no longer required.

  A change touching the semantic surface needs the semantic verdict; an issue classified as
  needing independent review needs one of the configured independent contexts as well. **A
  recorded failure at any configured context blocks outright**, and a pass recorded elsewhere does
  not clear it: the chain advances when a provider is unavailable, never because its verdict was
  unwelcome. A failure is answered by fixing the code, fixing the map, or getting an owner's
  ruling.
- **An overlay change is finished by a re-produce.** `tools/re-produce.sh` runs it. Marking an
  entry implemented writes `overlay/<entry id>.json`, and the generated files and `provenance.json`
  are both derived from the overlay; the gate hashes the derived files against the record.
  Regenerating the C# moves those hashes, but an overlay edited and nothing else run moves only
  `buildInputs[overlay/<entry id>.json]` — the record's hashes of the overlay files against the
  files on disk, compared as a **set**, so a file added or removed is caught as loudly as one
  edited — so that is the comparison that catches every form of it. Only the factory can write that record: it names the
  factory commit the engine was produced from and hashes every one of that factory's recipe files,
  so nothing inside the engine can refresh it — and nothing should try. A record an engine wrote
  about itself would hash whatever is on disk, and a gate that re-blesses its own bytes proves
  nothing.

  One file per entry is what keeps two entry branches out of each other's way, and
  `provenance.json` is the one place they still meet: merging one into the other leaves conflict
  markers in it, and a file with markers in it is not JSON. **That is not a conflict to resolve by
  hand.** Every hash in the record is recomputed by the re-produce that follows, so both sides are
  discarded whichever is kept and neither is more right than the other. `tools/re-produce.sh`
  recognises it and says so, and `tools/re-produce.sh --resolve-record` takes a side and
  re-produces over it in one command.

- A check that examines nothing is a failure, never an ok. If a step could not run, say it could
  not run.

## 8. Determinism

Same inputs, same outputs, on any machine, in any order, forever. No wall-clock time, no
ambient locale or culture, no environment-dependent ordering, no unseeded randomness, no hash
codes or object identity in anything observable. Where the corpus declares randomness, it is
drawn only through the kernel's seeded facilities, and `provenance.json` records that
declaration. An engine whose corpus declares no randomness does not reference a randomness
package at all, and the gate checks it.

## 9. Configuration, not code

`.github/agent-policy.json` is this engine's own. It holds the issue state and risk label
strings, the review contexts, the paths that count as a semantic surface, the ordered
independent-review chain, and the worktree environment variables. The factory writes it once and
never touches it again.

**Change the chain, the labels or the roots by editing that file — never by editing a script.**
No emitted **script** names a vendor: a vendor named in code would be one you had to edit code to
change, and that is a defect worth an issue.

Two emitted things do name vendors, and both are defaults rather than the contract:

- **A bundled Claude adapter.** `CLAUDE.md` and `.claude/` point at this file and state no rule of
  their own (§2). An engine worked by another agent reads `AGENTS.md`, which is the governing
  document and names no vendor; the adapter is there because one vendor needed a file of its own,
  and adding another is configuration, not a change to the contract.
- **A default review chain.** The `independentReviewChain` this engine's policy shipped with names
  vendors, in order. It is engine-owned, written once, and never touched again: yours to reorder,
  cut, or replace with names of your own.

## 10. For a non-Claude agent

- Run `tools/agent-doctor.py --local` first. Its first three rows are the machine's
  prerequisites (§11), and the gate cannot run until they are true.
- You are probably in a worktree. Confirm before your first write: `git rev-parse
  --git-common-dir` differing from `git rev-parse --git-dir` means you are.
- The gate is `./scripts/validate.sh full`. Nothing else is.
- Never implement a rule from memory. Work from the entry the issue names.
- Never edit `corpus/`, `provenance.json`, or a generated file under `Generated/` by hand. The
  generated files are rewritten from the map; an edit there is overwritten and reported.
- After changing anything under `overlay/`, run `tools/re-produce.sh`. The record and the
  generated files are the factory's to write, and the gate fails while they are older than the
  overlay.
- A pull request that is a `factory produce` update says so in its `## Produced by the factory`
  section, and carries what produce wrote and nothing else (§4). One file that produce did not
  write voids the claim, which is why the files named above are also the only ones it can cover.

## 11. What this checkout needs before you run anything

Three things are true of the **machine**, not of this repository, and none of them is visible in a
file listing. `tools/agent-doctor.py --local` reports all three before any other row, and it
changes nothing; run it before your first command rather than discovering them one refusal at a
time.

- **The SDK `global.json` pins.** It is pinned with `rollForward: disable`, so a machine with a
  different .NET SDK cannot run the gate at all, and the failure does not name the pin. Install
  the exact version user-locally if you cannot install it system-wide:

  ```bash
  curl -sSL https://dot.net/v1/dotnet-install.sh | bash -s -- --version <the pinned version> --install-dir ~/.dotnet
  export PATH="$HOME/.dotnet:$PATH"
  ```

  `FACTORY_DOTNET_SDK_OVERRIDE` is for a local run only. A run under it proves that SDK and not
  the one `provenance.json` records, and says so in its own output; it is never how a verdict is
  reached.

- **A restore, before the first packet.** `tools/entry-packet.py` asks MSBuild where the restore
  put the map package, so in a fresh worktree it refuses until `dotnet restore` has run. Run it
  once per worktree.

- **A `gh` new enough for the fields the packets read.** `tools/review-packet.py` and
  `tools/conformance-gate.py` ask `gh pr view --json closingIssuesReferences`. An older `gh` — the
  2.45.0 Ubuntu 24.04 packages, for one — refuses that field, and on such a `gh` some of
  `gh pr edit` and `gh issue view` fail on these repositories as well. Install a newer `gh` and
  point `$RULES_ENGINE_GH` at it; every rail that shells out reads that variable.

None of these is a defect in this engine, and none of them is fixed by editing a rail. They are
what the machine owes the work.
