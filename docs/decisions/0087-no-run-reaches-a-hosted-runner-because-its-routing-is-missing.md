# 0087 — No run reaches a hosted runner because its routing is missing, and the audit runs itself

## Status

Accepted — 2026-10-27, on the owner's directive that unintended GitHub-hosted execution caused by a
runner-selection fallback be eliminated and mechanically prevented. **Partially supersedes
[0079](0079-a-repository-chooses-its-runner-through-factory-runs-on.md)** point 2 (a repository without
the variable runs hosted) and **[0080](0080-execution-trust-not-visibility-decides-whether-a-run-reaches-the-self-hosted-runner.md)**
point 5's runner line, and **[0084](0084-a-repositorys-setup-is-not-complete-until-onboard-check-passes.md)**
point 1's acceptance of 0079's line on a private repository. Everything else in those three stands: the
two variables and what each is for, the trusted-run test, the dispatcher and the guest as the boundary,
publication and manual maintenance hosted and declared in `runners.json`, `onboard-check` as the
setup invariant. Changes the generated `.github/workflows/validate.yml` recipe and the three managed
rails, `pr-policy.yml` (recipe 3 → 4), `conformance-gate.yml` (5 → 6) and `verdict-requeue.yml` (4 → 5),
decision [0018](0018-every-file-the-factory-writes-has-one-owner.md). Changes no job id, name, trigger,
permission, timeout, concurrency group or step, so no required status-check identity changes.

## Context

0079 said there is no fallback to a billable runner, and its line had one: `|| '"ubuntu-24.04"'`. 0080's
line kept it, so in every recipe, in this repository's own CI, and in every repository that copied the
line, a run whose variables named no runner went to GitHub-hosted compute without anyone choosing that.
A trusted run of a public repository whose `FACTORY_RUNS_ON_TRUSTED` was deleted, or of a private one
whose `FACTORY_RUNS_ON` was, went hosted; so did a run whose variable held a hosted label by mistake.
Nothing found it afterwards: `factory-ci audit` counted a missing `FACTORY_RUNS_ON_TRUSTED` on a served
repository as correct, `onboard-check` accepted 0079's line, and nothing ran the audit unless a person
did.

Measured on GitHub on 2026-10-27 (rules-factory branch `routing-probe-fail-closed`, deleted afterwards):
a `runs-on` whose `fromJSON` cannot parse fails the run as a **workflow file issue, with no job and no
check run**, so a required check named for the job is never reported and waits; a label no runner has
queues; `runs-on: {group: "<a group that does not exist>"}` creates the job and fails it at once, with
no runner, a check run concluded `failure`, and the annotation "Required runner group '…' not found".

## Decision

1. **The routing contract.** The runner line (`repository.RUNS_ON_LINE`, carried exactly by every recipe
   and every job of this repository's CI that is not declared hosted) resolves as follows. A *trusted* run
   is 0080's: actor and triggering actor the owner, code of this repository.

   | Configuration | Trusted run | Any other run |
   |---|---|---|
   | private, standing runner: `FACTORY_RUNS_ON` exactly `["self-hosted","linux","x64","factory-ci"]`, the other unset | factory-ci | factory-ci |
   | public, served by dispatch: `FACTORY_RUNS_ON_TRUSTED` exactly those labels, the other unset | factory-ci, admitted by the dispatcher | hosted `ubuntu-24.04` (0080: a fork's run) |
   | deliberately hosted: `FACTORY_RUNS_ON` exactly `"ubuntu-24.04"`, the other unset (`factory-ci disable`, the owner's decision) | hosted | hosted |
   | anything else: neither set, both set, a value that is empty, malformed, reordered, respaced, or names another runner | **fails** | **fails** |

   "Exactly" is GitHub's string comparison, which ignores case. No variable's value is ever passed to
   `fromJSON`: the line compares each with the one value it may hold and emits a fixed runner of its own
   (`RUNS_ON_LABELS`, `RUNS_ON_HOSTED` or `RUNS_ON_UNSET`), so no duplicate key, malformed text or other
   spelling can carry a runner through, and no value can become a workflow file issue. A first version
   handed a value to `fromJSON` once it merely contained `"factory-ci"`; the independent review of
   `4879e9e` showed that `{"labels":"factory-ci","labels":"ubuntu-latest"}` parses to a hosted runner, and
   that a malformed trusted value still sent a fork's run hosted. Every other case asks for
   `RUNS_ON_UNSET`, the runner group `FACTORY_RUNS_ON or FACTORY_RUNS_ON_TRUSTED is unset or invalid`,
   which a personal account cannot have: the job fails when it is created, with no runner, and its
   required check reports `failure`. The line reads only the run and the variables, so a busy or
   offline runner changes nothing: its job waits, and is never sent elsewhere.

2. **Values are judged in one place.** `onboard.verify` (`factory-ci onboard-check`, the rails' `Self-hosted
   CI route` row) holds a repository's variables to the exact values above, compared as the line compares
   them (private: `FACTORY_RUNS_ON` exactly `LABELS_VALUE`, no `FACTORY_RUNS_ON_TRUSTED`; public: the
   reverse, and no standing runner), so a value it passes is a value the line routes,
   and every job's `runs-on` to `RUNS_ON_LINE` or a `hosted_jobs` entry. 0079's and 0080's lines are
   findings that say so: an implicit fallback, with the command that replaces it. The judgement of a
   workflow's jobs is one function, `workflow_findings`, applied to a repository on GitHub and to a
   checkout, and the gate applies it to this repository's own workflows, so `validate.sh` refuses before a
   merge exactly what the audit finds after one.

3. **The audit verifies every served repository, and runs itself.** `factory-ci audit` runs `verify` on
   every repository the guest serves, by a standing runner or by dispatch; a repository it cannot read is
   a finding ("NOT VERIFIED, which is not a pass"). The trusted dispatcher, the service that already runs
   on the host at all times, starts that audit at start and every hour (`AUDIT_EVERY`) as a child process
   it does not wait for, so a slow or hung read cannot stop admission (the review of `4879e9e` found the
   first version ran it inside the loop); one still running after `AUDIT_TIMEOUT` (15 minutes) is killed
   and recorded as a failure. The audit logs each finding and writes the verdict to
   `~/.local/state/factory-ci/audit.json`. `repo-hygiene.py`, which every Claude
   Code session in this repository runs at its start, reports a failing audit, or one missing or more than
   three hours old, as a `ci-route` leftover. So a variable deleted or a workflow edited on GitHub is found
   within the hour and said at the next session, with nobody asking. No scheduler is added.

4. **Hosted is said, not implied.** `factory-ci disable` writes `FACTORY_RUNS_ON` = `"ubuntu-24.04"` instead
   of deleting the variables, and `untrust` does the same, so returning a repository to hosted runners stays
   one deliberate command. A public repository may hold that exact value (a fork's run reads it and is
   hosted); any other `FACTORY_RUNS_ON` on a public repository remains a finding. `enable` on a public
   repository replaces it with `FACTORY_RUNS_ON_TRUSTED`.

5. **Repositories reach the new line as they reached 0080's.** An engine re-produces from a factory that
   contains this decision; a repository's own workflow copies `RUNS_ON_LINE`. Until then the audit names
   each job still carrying 0079's or 0080's line.

## What this does not decide

The boundary does not move: the dispatcher's admission and the guest's hook decide what runs on the VM, as
in 0080, and nothing here admits a run they would refuse. The variables keep their names and their JSON
form, but 0079's "a label, or a list of labels" narrows to the values above, the only ones `onboard-check`
accepted already; a repository holding another value was failing that check before this decision.
