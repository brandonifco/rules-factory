# tax-121 learning log

Goal (2026-09-17): finish `tax-121-principal-residence` for its mapped slice (26 CFR 1.121-1,
24 backlog entries) through the full rails, and learn from it whether rules-kernel + rules-factory
deserve to be the central investment.

Questions this run must answer:

1. **Cost.** Wall time, agent turns and escalations per entry, and how that splits between rule
   work and process work.
2. **Explanations.** Does composing entries (e.g. `exclusion-of-gain` over ownership/use,
   principal residence, limitation amount) force an explanation or trace capability into the
   kernel, or is Resolution + locator enough?
3. **Dates.** `effective-date` is a date *inside* the rule. Does anything in this slice force
   point-in-time corpus selection (several versions of the text), or does it stay unforced?
4. **Map quality.** Map defects found downstream of the blind second mapping: how many, what kind.
5. **Factory/kernel gaps.** Anything the engine had to work around.

## Setup (2026-09-17 ~13:10 EDT)

- Repo had no issues, labels, or branch protection. `factory rails --apply` put them in place;
  `factory backlog --create` filed issues #1-#24 (the numbers match the backlog order). 7 ready:
  #1 #2 #3 #8 #12 #14 #24.
- `rails --check` still reports `tools/agent-doctor.py` from an earlier recipe. That needs a factory
  update PR; deferred.
- Environment friction: `~/.bashrc` sets `DOTNET_ROOT=~/.dotnet`, which only has SDK 8. The gate pins
  10.0.112, which is in `/usr/lib/dotnet`. The gate fails at step 1 unless
  `DOTNET_ROOT=/usr/lib/dotnet`. With that set, `main` passes (84 tests, ~10s).

## Entries

| # | entry | started | PR | merged | escalations | notes |
|---|---|---|---|---|---|---|
| 24 | effective-date | 13:24 | #25 (13:31) | 13:45 | 0 | impl ~7 min, ~138k tokens, 43 tool calls (~17 rule / ~28 process). `DateOnly? SaleOrExchangeDate` required; a pre-2002 sale resolves to the value `Applies=false`, not a decline. 1 surviving mutation (two entries share the § 1.121-1(f) locator) |

## Friction (from engine-dev on #24)

- **F1** The order in the charter is wrong for the first implementation. The handler only compiles after a re-produce, so it takes two re-produces with placeholder mutations in between. Only the entry packet mentions this.
- **F2** **Gate gap:** `validate.sh full` passes with `"mutation": "PENDING"` in the overlay. The mutation record isn't checked for content. This is a factory defect.
- **F3** `re-produce.sh` clones the factory from GitHub. `RULES_ENGINE_FACTORY_REPO` is undocumented in the charter.
- **F4** `entry-packet.py` needs `dotnet restore` first and the right `DOTNET_ROOT`.
- **F5** The entry packet doesn't show the kernel API. The agent grepped XML docs in the NuGet cache.
- **F6** `implementedIn.ruleset` id isn't specified anywhere.
- **F7** **Design gap:** no guidance on "rule does not apply" as a value versus a decline. This is the first place the method's five-category vocabulary doesn't cover a case, and every gated entry will hit it.
- **Process deviation (orchestrator):** the steward and semantic reviews ran in parallel rather than steward first, to save wall time.

## Review of #25 (steward ~1 min / 65k tokens; semantic ~1.5 min / 71k tokens): both pass

Total for entry 1: about 21 min wall time and about 275k tokens across three agents.
Findings the implementer and its own tests missed:
- **R1** The mutation `==` for `>=` survives. The map only named the 23/24 pair, so the "after" side went untested. Follow-up issue: a test for 2002-12-25.
- **R2** **The important one.** `Applies == false` is not a plain "no" downstream, because § 1.121-1(f) points to the retroactive election in § 1.121-4(j), which is out of scope. This needs an owner's ruling before the gated entries are built. The factory's `enabledBy` vocabulary says "the rule is reachable". It has no way to say "unreachable, and here is why that is out of scope rather than false."
- **R3** Two entries share one locator, so the citation can't be asserted uniquely. That is a kernel or registry gap.
- **R4** Nothing shares the fact shape (`SaleOrExchangeDate`) across request types. Each generated request is partial and separate, so there's a risk of drift across 23 entries. That is a factory gap: no shared-fact vocabulary.

## Owner's ruling (13:50): pre-2002 sale → gated entries decline OutsideCurrentScope

- Brandon chose option A. Filed as #26 (decision record + shared gate helper) and #27 (the 2002-12-25 test from R1).
- **F8** The factory's ruling mechanism (0027) can't hold this ruling. A ruling has to quote an entry's `ambiguity.question`, and `effective-date` is clear. A cross-entry *reachability* ruling has no structured home, so it goes in an engine decision record plus a hand-written helper. The factory can't check that gated entries use it.
- Entries 1, 2, 3, 8, 12 and 14 are held until #26 merges, because each one gates on it. #27 is held too: its overlay edits would conflict with #26's.

## #26 → PR #28 (13:55–14:00, ~5 min, ~84k tokens, 25 tool calls, ~12 rule / ~8 process)

- Helper: `Applicability.Gate(MapEntry, DateOnly?) -> UnresolvedResult?`. Decision record 0001. The 2002-12-25 test was added here and kills the `==` mutation, so #27 is probably satisfied; I'll close it after merge if the review agrees.
- Implementation of the second entry was noticeably cheaper than the first (84k vs 138k tokens) once the conventions existed and the prompt carried the friction learned on #24.

## Parallelism: F9, a structural throughput limit

Every entry PR touches all remaining `backlog/*.md` files (the `enabledBy`/state lines are regenerated), `backlog/README.md`, `provenance.json`, `Generated/*.g.cs` and the overlay. **Any two entry PRs in flight conflict, always.** After one merges, the next has to merge main, re-produce, re-run the gate and push, and that new commit invalidates any verdict already recorded (by design: verdicts are pinned to the head SHA).
So the rails give **one merge at a time per engine**. Plan: implement in parallel; then integrate one at a time (merge main → re-produce → gate → push) and review only at the integrated SHA, so no review runs twice.
Factory implication: the generated backlog/provenance fan-out turns every entry change into a whole-repo change. Candidates: generate the backlog outside the repo, or make re-produce conflict-free (merge driver: "re-produce on conflict").

## Candidate kernel feature: a conditional answer (raised by Brandon, 14:05)

Instead of declining, an entry would return branches keyed on a named open question: who decides it, where it is cited, and the outcome under each answer, branching only where the outcome differs.
- Precedent: faa-part-107 `speed-within-limit` already resolves where both readings agree and declines only where they differ.
- Distinct from a caller-asserted fact (`WaiverStatement`, 0025 `assertedBy`), which already works.
- **Watch for it:** #26 retroactive election (declines for now), #3/#4 principal-residence facts and circumstances, #5 majority-of-time. If 2+ tax entries plus FAA want the same shape, that is the evidence to add it to rules-kernel.

## #28 merged (~14:12). Superposition framing (Brandon)

Brandon's idea: hold the answer "in superposition" until a person's answer is observed. Formally this is partial evaluation: the engine returns the residual outcome over named unknowns, each unknown carrying who decides it and its locator. Three rules make it work:
1. merge branches whose outcomes are equal;
2. unknowns can be conditional (they only exist in some branches), so the result is a tree;
3. numeric unknowns become constraints (e.g. "met if days of use ≥ 730").
Each engine-dev agent now reports the superposition its entry would have returned.

## Fan-out (14:15): #1 #2 #3 #8 #12 #14 dispatched in parallel

Integration will be serial: merge main → re-produce → gate → push → review at that SHA → merge.

## Superposition refinement (Brandon, ~14:20): "add the context so you know WHICH answer is correct"

A superposed result carries both the possible outcomes AND the context needed to choose between them. For each piece of context: who supplies it, its locator, and which outcomes it separates. Only questions that separate outcomes are asked, and only in the branches where they matter.
- This makes the engine an **interview generator** built from the map, with citations, updated as the rules change.
- Two kinds of unknown: **context** (a fact someone knows, which collapses deterministically) and **judgment** (still open once all facts are in). Context can shrink a judgment; for example, all six factors pointing to one house settles it.
- A decline is the degenerate case: a superposition where the engine doesn't know what would resolve it.
- Candidate kernel shape: `Resolved | Superposed{outcomes, neededContext[]} | Unresolved`. Watch whether #3 and #12 fit it.

## #1 residence-facts-and-circumstances → PR #29 (~5 min, 86k tokens, ~6 rule / ~11 process)

- A pure decline, `RequiresInterpretation` § 1.121-1(b). Input: free-text `FactsAndCircumstances` (required), echoed back in the decline.
- **Superposition fit:** two branches (residence / not), a judgment decided by the taxpayer and subject to the IRS or a court. Neither branch collapses, and the map lists no context that would narrow it. This is the case of a "judgment with no named context". The free-text facts list is the engine's placeholder for context the corpus never names.
- Survivor again: a shared locator (b) with `residence-may-include`. Third time (R3 pattern): locators are not unique per entry.
- PRs open so far: #29 (#1), #30 (#2), #31 (#3), #32 (#8). Review started on #29, first in the merge queue.

## #12 ownership-and-use-aggregation → PR #33 (~5 min, 89k tokens, ~9 rule / ~15 process)

- A value: 2 years / 24 full months / 730 days, with ≥ predicates. Counting months from dates (month ends, leap years) is deferred to `ownership-and-use-test` (#15), which will be the real date-arithmetic test.
- Superposition: the constraint form showed up naturally, "met if full months ≥ 24 or days ≥ 730". Numeric unknowns as constraints, confirmed.
- **F10** Re-produce deletes and renumbers backlog files, so staging with a glob missed the deletions and needed a second commit. Conflict size between parallel PRs grows with each merged entry.

## #8 maximum-limitation-amount → PR #32 (~5 min, 94k tokens, ~7 rule / ~10 process)

- $250k, or $500k for "certain joint returns". `bool? CertainJointReturn` is required; the qualification test is in § 121(b)(2), which is not in the corpus.
- **Superposition, cleanest example yet:** a context unknown (joint-return qualification, supplied by the caller or preparer) splits {$250k, $500k}. This is exactly the "add context to know WHICH answer" case: today the engine refuses without the flag, where it could return both amounts and ask the question.
- Shared-locator survivor again (§ 1.121-1(b)(3)(ii), with vacant-land-single-sale). Fourth instance.

## #14 use-requires-occupancy → PR #34 (~5 min, 82k tokens, ~9 rule / ~12 process)

- Clear; always resolves. Requires `TaxpayerOwned` and `TaxpayerOccupied`.
- **Superposition, a new form: a bounded judgment.** For `short-temporary-absences` (#17), the corpus examples put 2 months inside and 1 year outside, so an absence of N months is settled for N ≤ 2 and N ≥ 12 and open in between. That is factory decision 0031 ("an example that bounds a term is a bound") turned into a runtime constraint. A superposition can carry a **known-settled region plus an open interval**.
- Shared-locator survivor, fifth instance. This is now a factory/kernel defect worth filing: every entry sharing a paragraph citation is indistinguishable by locator.

## Principle (Brandon, ~14:45): "requires human observation or judgment" IS a deterministic answer

- The engine is total: every input yields a determined answer, and some answers are "depends on X, supplied by Y, per Z". The human observation is an attributed input at a clean seam, so replaying it gives the same superposition and the same collapse.
- This extends kernel ADR 0004 (the totality burden) from "unresolved is a result" to "the superposition is the result".
- Corollary: where the line between settled and open falls is a claim the map makes, and it can be wrong in both directions (dodging or overreaching). The blind second mapping and the conformance review are what verify it. The line is part of the answer.
- Product guarantee: a complete answer to every question, with the gaps named, cited, and assigned to whoever must fill them.

## #2 residence-may-include → PR #30; integrated at 41e3925 (~1 min hands-on)

- A value: [houseboat, house trailer], citing § 1.121-1(b). Superposition: only the date gate.
- **F11** A code-level merge conflict, not just generated files: both #1 and #2 created `Rules/Residence.cs` with `class Residence`, and the integrator merged them by hand. **The mutations were observed before the merge and not re-run at the integrated head**, so the rails' "a verdict names a commit" doesn't extend to mutation evidence. Parallel agents naming files by topic will collide.
- **F12** Re-produce writes nothing when its verify step fails, which is correct but opaque. The conformance-gate failure reason only appears in the Actions log.

## #3 principal-residence-factors → PR #31 at e3651e4 (~6 rule / ~18 process tool calls)

- The six factors (i)-(vi) verbatim, `IsExhaustive = false`, § 1.121-1(b)(2).
- **The strongest superposition finding yet.** Both branches of the effective-date unknown print the same six factors, so they merge and the answer needs no election at all: **this entry never needed to decline.** Decision 0001, as a blanket rule, makes the engine decline where the outcome doesn't depend on the unknown. The branch-merging rule isn't just better presentation, it's more correct. Over-declining is as much a defect as over-answering.
- **On the weighing itself:** a superposition over *weights* isn't buildable ("not limited to" makes inputs unbounded, and no weights exist), but a superposition over *candidate properties* is: the outcome set is finite (which house), with each branch carrying its factor evidence. So judgment collapses to a choice among named outcomes.
- **F13** `re-produce` runs the gate, so the handler must be written before the first re-produce or a cycle is wasted (about 5 min). Backlog renumbering conflicts cost about 10 min per integration.

## Batch 1 complete: 7 of 24 entries merged (13:10-15:15 EDT, ~2h05m)

Merged: #24 effective-date, #26 the ruling + gate helper, #1, #2, #3, #8, #12, #14. On main: 45 tests named by 7 implemented entries, gate green.

**Cost, measured.**
- Implementation: ~5 min and 80-100k tokens per entry, about 20-25 tool calls, roughly 1/3 rule work and 2/3 process.
- Review: two reviewers per PR, ~1-2 min and ~60-80k tokens each.
- Integration (merge main, re-produce, re-gate, push): ~1-3 min hands-on per PR, serial, plus about a minute of CI each.
- Orchestration (me): packets, verdicts, merges, label sync.
- **Total for 7 entries: about 2 hours wall clock, roughly 1.6M tokens across 20 agent runs.** That works out to about 17 min and ~230k tokens per merged entry, at 6-way parallel implementation with serial integration.

**Reviews caught in this batch:** 0 blocking findings, 14 non-blocking notes. The most valuable were R2 (Applies==false is not a plain "no"), the #3 branch-merging insight, and confirmation that 730 is the corpus's own figure and not the implementer's arithmetic. No map defects, and no escalations in 7 entries — which is itself evidence the blind second mapping did its job.

**F14** My two hand-filed issues carried `<!-- rules-factory-entry: effective-date -->`, the same marker as #24, and `factory backlog --create` then REFUSED the whole sync (correctly: one marker, one issue). Until I stripped the markers, every dependent issue kept a stale `state:blocked` label. A non-entry issue must not carry an entry marker, and `tools/new-issue.sh --entry` invites exactly that mistake.

**Now ready:** #4 principal-residence-facts-and-circumstances, #13 ownership-and-use-nonconcurrent, #17 short-temporary-absences, #27 the boundary test. #4 and #17 are the two judgment-heavy entries; #17 is the bounded-interval superposition case.

## Fix 1 done: the gate refuses a mutation nobody ran (rules-factory #239, PR #241 merged ~16:40)

Codex (GPT-6-Astra, medium) reviewed it twice under AGENTS.md §6. Round 1 found a **blocking** hole: the check read only overlay items, so an `implemented` entry whose tests came from the package map bypassed it entirely with an empty overlay — the hole was on the engine path, not just the publishing path the follow-up issue covers. Also unicode bypasses (curly quotes, zero-width padding, fullwidth, homoglyphs), tests that survived deleting half the rule, and fixtures asserting a mutation result that cannot occur (deleting a required handler is CS8795, not a runtime decline). Round 2 confirmed the fixes and caught the overshoot: counting only distinct words refused honest evidence like "Increment `increment`; fails".
Shipped: the check runs over the merged entries; NFKD + drop Mn/Me/Cf + strip by Unicode category + casefold; floor of 3 words / 12 characters counted over visible characters; separate refusals for "every distinct word is a placeholder" and "one word repeated"; 28 tests, each watched red.
**Honest limit, stated in the PR:** the rule refuses an *unfilled placeholder*. It cannot tell whether the edit was made or the test went red. That still rests on the implementer's word. The agent also stated plainly that it did not execute the corrected fixtures' mutations and said how it checked them instead.
**Audit:** all 45 mutations across the 7 merged tax-121 entries are real; nothing had slipped through.
**Cost:** ~1h wall, ~1M tokens for the implementer across 4 rounds, plus 3 Codex runs (~70k tokens). Two review rounds were worth it: round 1's finding was a genuine bypass.
