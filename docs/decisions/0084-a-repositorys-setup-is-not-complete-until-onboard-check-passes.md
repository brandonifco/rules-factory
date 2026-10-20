# 0084 — A repository's setup is not complete, and its CI-dependent work does not start, until `onboard-check` passes

## Status

Accepted — 2026-10-19, on the owner's directive that every owner-authorized CI run executes on the
existing KVM runners (`factory-ci-1` at home, `factory-ci-2` at the office where configured) and that
GitHub-hosted compute is never a fallback. Implements
[#687](https://github.com/brandonifco/rules-factory/issues/687). Extends
[0079](0079-a-repository-chooses-its-runner-through-factory-runs-on.md) and
[0080](0080-execution-trust-not-visibility-decides-whether-a-run-reaches-the-self-hosted-runner.md); changes
no recipe, no emitted file and no engine-owned file.

## Context

A new private engine repository was produced and pushed. Its workflows carried `RUNS_ON_LINE` and
`FACTORY_RUNS_ON` was set, but no runner was registered for it, so its `validate` run sat queued for
about 23 hours until the owner ran `factory-ci register` by hand. Nothing said so: `factory rails
--check` reports the labels, the ruleset and the required checks, not whether a job can execute anywhere,
and onboarding was three manual commands (`setup`, `register`, `enable`) that nothing verified.

## Decision

1. **The invariant.** A repository's setup is not complete, and work that depends on its CI (a pull
   request whose required checks must report, a produce that is merged, an agent run that waits for a
   check) does not start, until `factory-ci onboard-check OWNER/REPO` passes for it. The check proves a
   route, not that commands ran: only authorized runners (the reviewed
   [`runners.json`](../../tools/ci-runner/runners.json)), at least one online with exactly factory-ci's labels
   (private), routing exact (private: `FACTORY_RUNS_ON`, no `FACTORY_RUNS_ON_TRUSTED`; public: trusted
   dispatch, no standing runner), and every job of every workflow on the default branch on
   `RUNS_ON_LINE`. It writes JSON evidence (`factory-ci/onboarding/1`) and exits non-zero on any
   finding; a GitHub read that fails is exit 2 naming what could not be read, never a pass. The one
   exception to "every job on `RUNS_ON_LINE`" is a job that [0080](0080-execution-trust-not-visibility-decides-whether-a-run-reaches-the-self-hosted-runner.md)
   point 8 keeps hosted (publication credentials, manual maintenance), and only when it is declared: an
   entry of `runners.json`'s `hosted_jobs` names the repository, workflow path, job id, the exact
   `runs-on` (`ubuntu-24.04`) and the reason. The check records such a job as deliberately hosted, not a
   finding, only when the repository is public and the job's `runs-on` is exactly the listed one. A
   private repository may have none (its entry is a finding); any other literal `runs-on`, a changed
   listed one and an entry whose job no longer exists are findings. There is no blanket allowance of
   `ubuntu-24.04`.
2. **Enforced at the provisioning boundary, not in `produce`.** `produce` stays deterministic and
   offline: it writes files and cannot know what runners a repository has. The boundary where the
   fact is knowable is the host that runs the VM, and the repository settings the factory already
   checks. So: `factory-ci onboard` (idempotent; private only) makes the route and then runs the check;
   `factory rails --check` has a `Self-hosted CI route` row, OK only when the same verification passes,
   with its findings in `problems`, so setup cannot be declared complete without it; `rails --apply`
   registers no runner (that is the host's `onboard`) and says so.
3. **Never replace another host's runner.** `onboard` and `register` refuse to replace a same-named
   runner the guest does not hold (`.runner`'s `agentId` is not GitHub's id for it), so a second host
   (#643) never loses its registration to the first; a runner of `runners.json`'s other name is never
   touched. A public repository is refused by `onboard`: it has no standing registration, ever (0080).
4. **One list, held by tests.** `LABELS` in `dispatch.py`, `runners.json`, `register.sh`'s labels,
   `factory-ci`'s `enable` value and `repository.py`'s `RUNS_ON_LINE` are held to one another by
   `tools/tests/test_ci_runner_onboard.py`.

## Alternatives considered

- **Check in `produce`.** It would make an offline, deterministic command depend on GitHub and on a
  host it does not run on, and a produce on a laptop would fail for want of a VM.
- **A host-identity file (which runner this machine is).** The runner name is the guest's hostname,
  already what GitHub lists, and the guest's `.runner` file already says which registration it holds;
  a second source of identity would drift from both (and #643 is deciding that separately).
- **Let `rails --apply` register.** It runs wherever the owner has `gh`, with no guest to hold a
  registration; registering is the KVM host's act with the guest.

## Consequences

- The guest gains two subcommands of `dispatch-guest` (`held`, `register`); the next `factory-ci
  setup` installs them, and `onboard` says so if the guest is older.
- A private repository that keeps a hosted job fails `rails --check` until it is onboarded: that is the
  point, and hosted compute for owner-authorized runs is the owner's decision, not a default. A public
  repository's publication and manual maintenance jobs are declared in `hosted_jobs`, so they do not fail
  it, and a new hosted job that is not declared does.
- `onboard-check` needs a `gh` login with repository administration (runners, variables) and contents
  read. Without it the row is NOT VERIFIED and `--check` exits 1.
