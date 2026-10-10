# 0080 — Execution trust, not repository visibility, decides whether a run reaches the self-hosted runner

## Status

Accepted — 2026-10-10. Records the owner's Governance Edict 0080,
[#637](https://github.com/brandonifco/rules-factory/issues/637). **Partially supersedes
[0079](0079-a-repository-chooses-its-runner-through-factory-runs-on.md)**: its point 4 (public
repositories never use the self-hosted runner) is replaced by what follows, and its runner line by
the one below. The rest of 0079 stands: one variable-driven line held in `repository.py`, the
pinned hosted default, no fallback to a billable runner, and engines reach the line by re-producing.
Changes the generated `.github/workflows/validate.yml` recipe and the three managed rails,
`pr-policy.yml` (recipe 2 → 3), `conformance-gate.yml` (4 → 5) and `verdict-requeue.yml` (3 → 4),
decision [0018](0018-every-file-the-factory-writes-has-one-owner.md). Changes no job id, name,
trigger, permission, timeout, concurrency group or step, so no required status-check identity
changes, and no engine-owned file.

## Context

0079 kept every public repository on GitHub-hosted runners because a self-hosted runner executes
the code of any job that reaches it, and a fork's pull request writes its own workflow. The owner
has since directed that the owner's own work in public repositories run on the same VM as the
private ones, with untrusted contributions kept off it, and no new infrastructure: the one VM
`factory-ci-1` (6 vCPU, 12 GB, two job slots).

What GitHub offers a personal account settles the design. A runner registered with a repository is
available to every workflow of that repository and matches jobs by label alone, so a fork's pull
request that writes `runs-on: [self-hosted]` reaches it. The only thing GitHub puts in the way is
the approval prompt for outside contributors, which the edict does not accept as the boundary.
Workflow-restricted runner groups exist only for organizations, and moving a repository into one is
excluded. Every condition a workflow file could state about trust is in a file the fork controls,
and repository variables are readable by a fork's run. So routing can live in the workflow, but the
boundary cannot.

## Decision

1. **A public repository never has a standing runner registration.** `factory-ci register` refuses
   one, the guest refuses to register an account that is served by dispatch, and `factory-ci audit`
   reports any public repository with a runner it did not start.

2. **The owner's runs reach the VM through a trusted dispatcher, one job at a time.** The
   dispatcher (`tools/ci-runner/dispatch.py`, `factory-ci dispatch`) runs on the KVM host with the
   owner's `gh` login, which never enters the guest. For every unfinished job in a served
   repository that a factory-ci runner could be handed, meaning any job all of whose labels are
   factory-ci's, it reads GitHub's own record of the run, never the workflow file, and admits the
   run only if:
   - its head repository is the repository itself, not a fork, and not a deleted one;
   - its actor and its triggering actor are both the repository's owner, so a re-run does not
     launder a bot's or a fork's run;
   - its event is one whose code is the repository's own revision (`push`, `pull_request`,
     `workflow_dispatch`, `schedule`, `status`, `issues`). Never `pull_request_target`,
     `workflow_run`, a comment or a review event;
   - its exact head commit was put on its branch by the owner, by the repository's activity record
     (a push, a branch creation or a merge). That binds the authorization to the revision that
     executes, not to a username or an event name.

   A run that fails is cancelled. While any job that was not admitted is still unfinished in a
   repository, no runner starts there at all. For an admitted job the dispatcher writes the
   admission into the guest, root-owned, and then has GitHub create a just-in-time runner. That is
   one job, ephemeral, with exactly factory-ci's labels, run in the guest as that repository's own
   unprivileged account, in a fresh directory removed afterwards. An idle runner is deleted.

3. **The guest refuses what was not admitted, and stops it.** The job-started hook, on an account
   served by dispatch, requires that the job runs on a one-job runner and that its repository, run
   and attempt are admitted. Otherwise it kills the job's `Runner.Worker` before returning. Failing
   the hook is not enough: on 2026-10-10 a refused job still ran an action's `pre:` step after a
   failed hook (runner 2.338.0), and a step marked `if: always()` runs the same way. Killing the
   worker stops every step there is. The same probes showed that a job's `env:` does not reach the
   hook: a forged `GITHUB_RUN_ID` naming an admitted run was refused, and a `BASH_ENV` did not
   execute.

4. **One runner line, trust-aware for routing.** Every recipe, and this repository's own CI jobs,
   carry `repository.RUNS_ON_LINE`:

   ```yaml
   runs-on: ${{ fromJSON(github.actor == github.repository_owner && github.triggering_actor == github.repository_owner && (github.event.pull_request.head.repo.full_name || !github.event.pull_request && github.repository) == github.repository && vars.FACTORY_RUNS_ON_TRUSTED || vars.FACTORY_RUNS_ON || '"ubuntu-24.04"') }}
   ```

   `FACTORY_RUNS_ON_TRUSTED` takes a run only when the run passes the same owner and same-repository
   test the dispatcher applies, so a fork's or a bot's unmodified run asks for the hosted default and
   keeps its validation path. `FACTORY_RUNS_ON` means what it meant in 0079 and is for private
   repositories alone. A private repository never sets the trusted variable, so for it the line
   evaluates exactly as 0079's did. The line is routing and not the boundary: a fork that rewrites
   it gets a job that waits for a runner that never starts and is then cancelled.

5. **The approval prompt is one more door, not the lock.** `factory-ci trust` sets the repository's
   fork pull request approval to `all_external_contributors`, and `audit` reports a served
   repository that has any other setting.

6. **Capacity does not change.** One-job runners add no execution capacity: the guest's two job
   slots still bound what runs at once, across private and public repositories, and the VM stays at
   6 vCPU and 12 GB. A cap of four one-job runners at a time keeps idle listeners few.

7. **Publication stays hosted.** Workflows that hold publication credentials (`publish-map.yml`,
   a library's `publish.yml`) and manual maintenance workflows keep `runs-on: ubuntu-24.04`.
   Release checks run where they always did, and the NuGet key is never on the VM.

## Consequences

- The boundary is enforced in two places a fork cannot write: the dispatcher's admission, read
  from GitHub's record of the run and the activity log, and the guest's hook, which reads only what
  the dispatcher wrote as root. The workflow line only decides what an honest run asks for.
- A forged job is assignable to a one-job runner only if GitHub hands a runner a job queued after
  an admitted one, while the dispatcher has started no runner beside any unadmitted job. If that
  happens, the hook kills it before any step. GitHub's assignment order is not documented, so this
  record does not claim more than that.
- The dispatcher is a single point of service, not of trust. When it is down, the owner's jobs in
  public repositories wait in GitHub's queue, as a private repository's do when the VM is down.
  Nothing moves to an unverified path.
- The runner updates itself. Hook behaviour was verified on 2.338.0, so the runbook's boundary
  probe is repeated after a runner version change.
- On a personal account's public repository the required checks are server-side (a ruleset). The
  dispatcher changes where they run, not what they are.

## What this does not decide

Which repositories are migrated, and when, is the runbook's and each repository's own pull
request's. An engine reaches the new line by re-producing from a factory tag that contains this
decision. Until then it keeps whatever line it has, and the trusted variable does nothing for it.
