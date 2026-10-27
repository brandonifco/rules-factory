# 0086 — A pull request reports one evidenced status per acceptance criterion of its issue

## Status

Accepted — 2026-10-27. Records the change on
[#695](https://github.com/brandonifco/rules-factory/issues/695). It adds **no merge policy**: it makes
visible to `pr-policy` the three outcomes the engine rail's section 6 ("Ambiguity is escalated, not
resolved") already allows. Changes the managed `tools/pr-policy.py`, the managed pull request template
and the managed `AGENTS.md` (section 6 and section 7). Changes no map, no overlay, no generated file and
no engine-owned file.

## Context

brandonifco/can-spam#157 closed can-spam#51 (`identifier-opt-out-and-address-required`). Its body
reported criterion 1 as "NOT MET, escalated". The entry declined `MissingRulesData` for every gate-true
request. `pr-policy` passed, the structural and semantic reviews passed, 9 of 9 mutations were red and CI
was green; the issue closed as completed and stayed `state:ready`. The escalation went to a separate issue,
so the refusal of a linked `state:needs-decision` issue never saw it.

Nothing caught it because `pr-policy` read the linked issue's labels and never its
`## Acceptance criteria`, and the template had no place for a status per criterion. A review verdict
checks conformance, a mutation score checks behaviour, and CI checks the build; none of them says whether a
criterion holds. Implemented, tested and reviewed therefore read the same as complete.

## Decision

**Section 6, read as it stands.** When an issue's acceptance criteria "cannot be met as written", the work
escalates and the issue awaits a decision; and "declining is a legitimate outcome" for an entry the corpus
does not settle. So a criterion stands in one of three states, and only the first is completion:

1. **MET.** Shown by a test or a command whose output the pull request carries.
2. **AUTHORIZED INCOMPLETE.** Not fully performed, where a named authority permits that limitation: a
   decision record, an answered owner decision, or the map basis the specification turns into a decline (an
   entry's `definedElsewhere`, or an `unresolved` ambiguity, or the correspondence row it reaches). The
   limitation is stated. This may merge: it is section 6's legitimate decline, made visible.
3. **BLOCKED.** It waits on an open owner question. Under section 6 the issue awaits a decision, and the
   pull request cannot close it: the rule `check_issue_labels` already applies to the linked issue, applied
   to the blocker a criterion names.

**The check.** Whenever the linked issue's `## Acceptance criteria` lists at least one checklist item
(`- [ ]` or `- [x]`), whatever the review class and including a `factory produce` update, the pull request
must carry an `## Acceptance criteria` section with one numbered item per criterion, `1.` to `N.` in the
issue's order, each beginning with exactly one status (bold is fine). A missing section, a different count or
order, or any other status ("NOT MET", "partly met", "escalated", "met") fails, naming the criterion.

- **MET** needs a backticked test method declared in a `*.cs` file under the engine's `tests/`, or a
  backticked command quoted verbatim in `## Tests and evidence`. A review verdict, a mutation score and a CI
  result are not that. A MET that rests on a decline (its text names `Unresolved`, `MissingRulesData`,
  `RequiresInterpretation`, `UnsupportedRule`, `UnsupportedInteraction` or `OutsideCurrentScope`, or says
  "declin...") also needs an `Authority:`, because a decline fulfils a criterion only where something
  authorizes it as doing so.
- **AUTHORIZED INCOMPLETE** needs `Authority:` naming a reference the check can verify (a
  `docs/decisions/<file>.md` in the tree; `#<n>` of a closed issue of this repository; a backticked map
  entry id followed by `definedElsewhere` or `ambiguity`, where the engine knows the id; or
  `correspondence row <k>` for a row the map specification's table has) and a non-empty `Limitation:`.
- **BLOCKED** always fails. It names the issue it waits on: open, the finding says the issue awaits that
  decision and this pull request cannot close it; closed, it says to classify the criterion again; none
  named, it says so.

An issue that lists no criteria is not checked, and the passing output says so. On success the output counts
the statuses.

## What this does not decide

* **That a criterion's status is true.** The check verifies that the evidence cited exists: a test method is
  declared, a command is quoted, an authority resolves. That the test shows the criterion, or that the
  authority permits this limitation, is a reviewer's.
* **What an authority permits.** Which decisions and rulings may authorize a decline stays where it was:
  with the owner, in a decision record or an overlay ruling.
* **Any change to section 6's escalation.** An unanswerable criterion is still escalated and the issue still
  awaits the decision; BLOCKED only stops the pull request from closing it.

## Consequence for engines

Each engine takes the check, the template and the two paragraphs of `AGENTS.md` on its next `produce`. From
then on a pull request that closes an issue with a criteria checklist must report it. **An open pull request
whose body lacks the `## Acceptance criteria` section fails `pr-policy` until it adds one**, because
`pr-policy` runs on every edit and push. An issue made by `factory backlog --create` carries the checklist,
so this is nearly every implementation pull request. Nothing is rewritten for an engine: its issues, overlay
and code are untouched.

## Compatibility

A pull request whose linked issue lists no criteria is judged as before. A pull request that already
reported its criteria honestly needs only the statuses spelled as above.
