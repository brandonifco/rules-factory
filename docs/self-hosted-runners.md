# Self-hosted runners

The owner's CI runs on one KVM virtual machine on the owner's home server, `factory-ci-1`, whatever
the repository's visibility. **Trust decides where a run executes, not visibility**
([decision 0080](decisions/0080-execution-trust-not-visibility-decides-whether-a-run-reaches-the-self-hosted-runner.md)): the owner's own runs go to the VM, and everybody else's (a fork's pull
request, a bot's update, a contributor's edited workflow) stay on GitHub-hosted runners and can
never reach it. GitHub still schedules every job and still reports every check and verdict.

The kit is [`tools/ci-runner/`](../tools/ci-runner/factory-ci): one host command, `factory-ci`, the
dispatcher it runs ([`dispatch.py`](../tools/ci-runner/dispatch.py)), and the guest baseline it
installs. Nothing in it is a credential.

## What runs where

| Runs | Runner | How they get there |
|---|---|---|
| Every run of a private repository (since 2026-10-09: reykholt, reykholt-web, reykholt-art, hallertau) | `factory-ci` VM, standing registration | The variable `FACTORY_RUNS_ON` ([0079](decisions/0079-a-repository-chooses-its-runner-through-factory-runs-on.md)). Only the owner and the owner's agents can start a run there, and GitHub runs no fork pull request of a private repository while its Actions setting for that stays off (keep it off). |
| The owner's own runs of a public repository (since 2026-10-10: see [Repositories](#repositories)) | `factory-ci` VM, one one-job runner per job | The variable `FACTORY_RUNS_ON_TRUSTED` routes them; the **trusted dispatcher** admits each one and starts its runner ([The boundary](#the-boundary-for-public-repositories)). |
| Everything else in a public repository: fork pull requests, bots (Dependabot), a re-run of either | GitHub-hosted `ubuntu-24.04` | The runner line sends them there unmodified. A fork that rewrites its `runs-on` gets a job that is never served and is cancelled. Hosted runs are free on public repositories. |
| Publishing (`publish-map.yml`, a library's `publish.yml`) and manual maintenance workflows | GitHub-hosted `ubuntu-24.04` | Pinned in the file. The NuGet key is never on the VM. |

Every factory workflow, and this repository's own CI jobs, carry the one line `repository.py` holds
as `RUNS_ON_LINE`. `FACTORY_RUNS_ON_TRUSTED` takes a run only when its actor and triggering actor
are the owner and its code is this repository's, not a fork's. `FACTORY_RUNS_ON` takes every run.
**Never set `FACTORY_RUNS_ON` on a public repository**: a fork's run reads it too. `factory-ci
enable` sets the right one for the repository's visibility, and `factory-ci audit` reports the
wrong one.

There is **no fallback**. When the VM or the dispatcher is down, a run that asked for it waits in
GitHub's queue and fails after GitHub's 24-hour queue limit. It does not move to a billed hosted
runner. Moving a repository back to hosted runners is a deliberate act, described below.

## The boundary for public repositories

A runner registered with a repository takes any of that repository's jobs whose labels it has, and
a fork's pull request writes its own `runs-on`. Repository variables are readable by a fork's run,
and workflow-restricted runner groups exist only for organizations. So nothing written in a
workflow can be the boundary. It is held in three places a fork cannot write:

1. **No standing registration, ever.** A public repository has no runner at all except a one-job
   runner the dispatcher started for an admitted job. `register` refuses a public repository; the
   guest refuses to register an account served by dispatch; `audit` reports anything else.
2. **The dispatcher admits runs, not workflows.** `factory-ci dispatch`, a user service on the
   host holding the owner's `gh` login (never the guest), reads every unfinished job a factory-ci
   runner could take (all of its labels factory-ci's, `[self-hosted]` alone included). It admits a
   run only if GitHub's record of the run says its head repository is this repository, its actor
   and triggering actor are the owner, and its event is `push`, `pull_request`,
   `workflow_dispatch`, `schedule`, `status` or `issues`, and the repository's activity log says
   the owner put its exact head commit on its branch. It cancels any other run. While an
   unadmitted job is unfinished it starts no runner in that repository. For an admitted job it
   writes the admission into the guest as root, then starts a GitHub just-in-time runner: one job,
   exactly factory-ci's labels, as the repository's own account, in a fresh directory that is
   removed afterwards.
3. **The guest refuses and stops anything else.** On an account served by dispatch, the
   job-started hook requires a one-job runner and an admission for the job's repository, run and
   attempt, under `/run/factory-ci-trust`, where no runner account can write. Otherwise it kills
   the job's `Runner.Worker`. That kill is the point: after a failed hook the runner still runs
   actions' `pre:` and `post:` steps and any `if: always()` step.

`factory-ci trust` also sets the repository's fork pull request approval to
`all_external_contributors`. It is one more door, not the lock.

What was verified on 2026-10-10 (runner 2.338.0), on a throwaway branch of rules-factory:

| Probe | Result |
|---|---|
| A job on a one-job runner with no admission | Refused; worker killed; its action's `pre:` step did not run (before the kill was added, it did) |
| A job whose `env:` forged `GITHUB_RUN_ID` and `GITHUB_RUN_ATTEMPT` to an admitted run, and set `BASH_ENV` to a command | Refused; `BASH_ENV` did not execute. A job's `env:` does not reach the hook |
| The owner's push | Admitted 9 s after it queued; ran on a one-job runner as `fci-rules-factory`; the runner deregistered itself and was reaped |
| An event that is not admitted (`create`), asking for `[self-hosted]` alone | Refused and cancelled while queued; it never had a runner. The owner's run queued beside it waited until it was gone |
| The owner's pull requests and pushes of rules-factory ([#638](https://github.com/brandonifco/rules-factory/pull/638) onward) | `validate`, `engine` and `documentation` ran on the VM and reported on the pull request's commits |

Not probed live: a pull request from a real fork, which needs a second GitHub account. Its run is
refused by the same head-repository rule as any other, which the dispatcher's tests hold
([`test_ci_runner_dispatch.py`](../tools/tests/test_ci_runner_dispatch.py)). **Repeat the probes
after a runner version change** (the runner updates itself): hook behaviour is the runner's, not
ours. [Running the boundary probe](#running-the-boundary-probe) says how.

## The VM

| | |
|---|---|
| Name | `factory-ci-1`, libvirt `qemu:///system`, autostart |
| Guest | Ubuntu Server 24.04, from the cloud image the script pins by release and SHA-256 |
| Size | 6 vCPU (host-passthrough), 12 GiB, 100 GiB qcow2 in the `default` pool |
| Network | libvirt network `factory-ci`: NAT, bridge `virbr-fci`, 192.168.150.0/24, guest at .11 |
| Egress | nwfilter `factory-ci-egress` on the guest's NIC. Allowed: DHCP; DNS to the gateway; outbound TCP 80/443 and NTP to public addresses. Dropped: everything else, including the host, the LAN, every RFC 1918, link-local and CGNAT range, other libvirt networks, and IPv6. Only the host may open SSH to the guest. |
| Admin | `ciadmin`, key-only SSH from the host (`~/.ssh/factory-ci_ed25519`, made for this VM and used for nothing else); passwordless sudo |
| Toolchain | `/opt/factory-ci` (root-owned, read-only to jobs): the .NET SDK the engines pin (10.0.112) and the .NET 8 runtime their tests also target, the GitHub CLI (the engines' `pr-policy` and `conformance-gate` call `gh`), Node, and the runner distribution. `/opt/hostedtoolcache` holds Python 3.12.15 and 3.12.14 (rules-factory's pin) in the hosted image's layout, for `actions/setup-python`. The Ubuntu packages a job would otherwise `sudo apt-get` (poppler-utils and others) are installed. All are pinned with hashes in [`guest/versions.env`](../tools/ci-runner/guest/versions.env). `actions/setup-dotnet` and `setup-python` find what they need and download nothing. A version that is not there fails the job, rather than being written into a cache another job could change. |
| Runners | One system account per repository, `fci-<repo>`, home `/srv/factory-ci/fci-<repo>` (0700). No sudo, no login shell, no SSH key. A private repository's standing runner is the service `factory-ci-runner@fci-<repo>`; a public repository's one-job runners are `factory-ci-jit-<id>`, generated from the same unit, in `~/jit/<id>`, removed when done. All are systemd-hardened (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `ProtectProc=invisible`, so an account sees no other account's processes) and in `factory-ci.slice`, which caps all runners together at 11 GiB. |
| Concurrency | `/etc/factory-ci/slots`, which is 2 (measured; see Everyday operation). GitHub cannot share one runner registration between personal repositories, so each repository's listener could take a job at the same moment. The job-started hook takes one of N slot locks before the first step and keeps it until the job's worker exits. A job that waits says so in its log, and the wait counts against its `timeout-minutes`. |
| Workspaces | The job-completed hook empties the checkout and `_temp`. The job-started hook empties whatever a job killed with the VM left behind. Every job starts from a fresh clone. |
| Kept between jobs | Only each repository's own home: its NuGet global packages folder, and what `pip` installs for it under `~/.local` (the tool cache's Python is read-only). The engines' locked restore still verifies every package against its lock file. No cache is shared between repositories, and the shared toolchain is read-only. |

### Residual risks of a persistent VM

This is **not** equivalent to an ephemeral runner. Know these:

- A job can leave a process or a file in its own account's home that a later job of the **same
  repository** sees. Examples: a poisoned NuGet package in `~/.nuget/packages`, or a planted
  `~/.bashrc`. The runner kills a job's orphan processes, and the hook empties the workspace,
  but the home persists. That is what makes the caches work. The boundary between repositories
  is the Unix account. The boundary to the host is the VM and its network filter.
- Outbound HTTPS goes to any public address. The filter limits ports and keeps the guest off
  private networks; it does not allowlist domains. A job could send what it can read to the
  internet. That means its own checkout, its `GITHUB_TOKEN` (scoped by each workflow's
  `permissions:`) and its own account's files. It cannot reach other accounts, the host, or the
  host's credentials.
- A local root exploit in the guest kernel would cross the account boundary, but not the VM's.
- Only trusted code may run here: the owner's runs, from a private repository (whose pull requests
  come only from the owner and the owner's agents; GitHub runs no fork pull request of a private
  repository while its Actions setting for that stays off: keep it off), or from a public one
  through the dispatcher. A same-repository job of the owner's can still run a dependency the
  owner did not write, just as on a hosted runner; the account boundary, the VM and the network
  filter are what contain it.
- The dispatcher is a single point of service, not of trust: when it is down, the owner's public
  repository jobs wait, and nothing reaches the VM without it.

Rebuild the VM (below) if a job is ever suspected of tampering with it.

## Everyday operation

Run these from a rules-factory checkout on the host. `gh` must be logged in as the owner with
`repo` scope.

```bash
tools/ci-runner/factory-ci status                          # VM, services, slots, GitHub's view
tools/ci-runner/factory-ci runners                         # every registered repository: online/busy
tools/ci-runner/factory-ci queue brandonifco/reykholt      # queued and running runs
tools/ci-runner/factory-ci logs brandonifco/reykholt -n 200
tools/ci-runner/factory-ci start | stop | restart          # the VM (stop is graceful)
tools/ci-runner/factory-ci runner stop|start|restart [OWNER/REPO]   # the runner services
tools/ci-runner/factory-ci ssh                             # admin shell in the guest
tools/ci-runner/factory-ci audit                           # the trust boundary, every repository
tools/ci-runner/factory-ci logs dispatch -n 200            # what the dispatcher admitted, refused, started
tools/ci-runner/factory-ci timings brandonifco/rules-factory 20   # queue and run time, by runner
```

**The dispatcher** is the user service `factory-ci-dispatch` on the host, installed by
`factory-ci install-dispatcher` from the checkout it should run (the primary one, on `main`). It
stops at logout unless lingering is on for the host account (`loginctl enable-linger <user>`, a
one-time setting the owner makes). `factory-ci status` shows whether it is active and which
one-job runners exist. A public repository's run that sits queued with nothing in `logs dispatch`
means the dispatcher is down: `systemctl --user restart factory-ci-dispatch`. A line `1 admitted
job(s) wait` means an unadmitted job is still unfinished in that repository; it clears when that
job is cancelled, which takes GitHub up to about a minute and a half.

**A stalled or failed job.** Start with the job's log on GitHub. A `factory-ci: all 1 slot(s) busy`
line means the job is queued behind another; the line names that job's repository and run. If a
run sits `queued` and `runners` shows the repository `offline`, read `logs` for that repository,
then `runner restart OWNER/REPO`. If the VM is unreachable, use `start`. If the runner's
credentials were revoked, `register` again. A runner's own diagnostics are in
`/srv/factory-ci/fci-<repo>/runner/_diag/` in the guest.

**Host restart.** Nothing is needed. With the host's libvirt-guests defaults (not changed for
this), the host saves the VM's memory at shutdown and resumes it at boot, and the listener
reconnects by itself. A VM that was off is autostarted, and its runner services are enabled. After
a cold start the listeners were back in about two minutes. If the VM dies under a job, the job
fails and GitHub says so. A hard power-off in the middle of `validate` was reported about ten
minutes later as "The self-hosted runner lost communication with the server", and nothing moved to
a hosted runner. Re-run the job with `gh run rerun <id>`. Check with `status` afterwards.

**Updating.** The runner updates itself; GitHub stops sending jobs to a runner that falls too far
behind. Ubuntu security updates install automatically (unattended-upgrades). To move a pinned
toolchain, such as a new .NET SDK that an engine's `global.json` pins: edit
`guest/versions.env`, then run `factory-ci setup`, then `factory-ci ssh 'sudo apt-get update &&
sudo apt-get -y upgrade'` for everything else. `setup` is idempotent. It restarts runners only
between jobs, because the unit lets a running job finish.

**Resources and concurrency.** `factory-ci slots N` (1–4) lets N jobs run at once. It is 2 because
of what was measured on 2026-10-09 with `sar` in the guest:

- Reykholt's `validate` alone took 145 s. It used 61% of the 6 vCPU on average, with an 88% peak,
  and at most 1.7 GB of memory.
- Run beside reykholt-web's `validate`, it took 155 s; reykholt-web's took 73 s (82 s alone).
  Together they peaked at 96% CPU and 2.3 GB, and both finished in 155 s instead of 227 s one after
  the other.

CPU is the limit, so a third heavy job would only slow the other two. Re-measure before raising it,
with `factory-ci ssh 'sar -u -r 5'` during the runs. To resize the VM:
shut it down, then `virsh -c qemu:///system setvcpus factory-ci-1 N --config --maximum` (and
`setvcpus ... --config`) and `setmaxmem`/`setmem ... --config`. Raise `MemoryMax` in
`guest/factory-ci.slice` to match, then run `setup`.

## Adding a repository

Its jobs must not need `sudo`. Anything a job installs with `apt-get` belongs in `APT_PACKAGES` in
`guest/versions.env`, and the step should skip the install when the tool is already present. A
Python version a workflow pins goes in `PYTHON_TOOLCACHE`. Its workflows must carry the runner line:
a produced engine does once it is produced from a factory release that contains decision 0080
(re-produce it on its own issue, `tools/re-produce.sh` after moving `factory.commit`; an engine
produced before factory 1.3 first needs a rules-corpus build definition beside each corpus,
decision 0074). A repository's own hand-written workflow uses the same line, copied from
`RUNS_ON_LINE` in `tools/factory/repository.py`; a job that publishes keeps `ubuntu-24.04`.

**A private repository:**

```bash
tools/ci-runner/factory-ci setup                          # if versions.env changed
tools/ci-runner/factory-ci register brandonifco/<repo>    # one standing registration
tools/ci-runner/factory-ci enable brandonifco/<repo>      # sets FACTORY_RUNS_ON
```

**A public repository:**

```bash
tools/ci-runner/factory-ci setup                          # if versions.env changed
tools/ci-runner/factory-ci trust brandonifco/<repo>       # account, dispatch, fork approval
tools/ci-runner/factory-ci audit                          # must report no finding
tools/ci-runner/factory-ci enable brandonifco/<repo>      # sets FACTORY_RUNS_ON_TRUSTED
```

Then push a pull request and confirm in the job metadata that it ran on the VM:
`gh api repos/O/R/actions/runs/<id>/jobs --jq '.jobs[]|[.name,.runner_name,(.labels|join(","))]'`
must name `factory-ci-1` (a standing runner) or `factory-ci-1-jit-<hex>` (a one-job runner).

### Repositories

| Repository | Visibility | Runner | Note |
|---|---|---|---|
| reykholt, reykholt-web, reykholt-art, hallertau | private | standing | since 2026-10-09 |
| rules-factory | public | dispatch | since 2026-10-10; `validate`, `engine`, `documentation` (`publish-map`, `judge-rebuild` hosted) |

### Running the boundary probe

On a throwaway branch of a served public repository, with the dispatcher **stopped**
(`systemctl --user stop factory-ci-dispatch`):

1. A workflow on `push` to that branch, one job with `runs-on: [self-hosted, linux, x64,
   factory-ci]`, a step that prints a marker, and a `uses:` of a JavaScript action on the same
   branch whose `pre:` prints another. Push it; the job queues.
2. Start a one-job runner by hand without admitting the run: `gh api -X POST
   repos/O/R/actions/runners/generate-jitconfig` (labels as above, `runner_group_id=1`) piped as
   `.encoded_jit_config` into `factory-ci ssh "sudo /opt/factory-ci/bin/dispatch-guest start <name> <id>"`.
   The job must fail with neither marker anywhere; the guest's journal says `refused run`.
3. Give the job `env:` with `GITHUB_RUN_ID`/`GITHUB_RUN_ATTEMPT` of a run you admit by hand
   (`dispatch-guest admit <name> <run>-<attempt>`) and a `BASH_ENV` that writes a file in the
   account's home. Repeat 2: refused, no file.
4. Start the dispatcher and push again: admitted, run, runner gone afterwards.
5. A workflow `on: create` asking for `[self-hosted]`, then create a branch: refused and cancelled.

Remove the admission, the branches and anything left in the guest (`dispatch-guest reap`) afterwards.

## Credentials

- **Registration tokens** are fetched by `factory-ci register` from the GitHub API and passed to the
  guest on stdin. They are never written to disk, an argument list, or a log, and they expire
  within an hour.
- **Runner credentials** (`.credentials`, `.credentials_rsaparams`) live only in each runner
  account's 0700 home. To rotate them, run `factory-ci register OWNER/REPO` again: `--replace` swaps
  the GitHub-side runner, and the old credentials are deleted first. To revoke one, run
  `factory-ci deregister OWNER/REPO`, or delete the runner under the repository's Settings → Actions →
  Runners.
- **The admin key** `~/.ssh/factory-ci_ed25519` never leaves the host. To rotate it, generate a new
  key, append its public half to `ciadmin`'s `authorized_keys` through `factory-ci ssh`, test it,
  then remove the old line.

## Recovery

**Rebuild from the baseline.** This covers a broken or suspect VM.

```bash
tools/ci-runner/factory-ci destroy-vm
tools/ci-runner/factory-ci provision      # network, filter, pinned cloud image, cloud-init
tools/ci-runner/factory-ci setup          # toolchain, hooks, units
for r in reykholt reykholt-web reykholt-art hallertau; do
  tools/ci-runner/factory-ci register brandonifco/$r
done
tools/ci-runner/factory-ci trust brandonifco/rules-factory   # each public repository served by dispatch
```

A rebuild takes about ten minutes. It loses only caches and admissions (the dispatcher writes
those again before it starts a runner). Each `register` replaces that repository's old runner on
GitHub; a public repository has none to replace.

## Hosted usage, and going back

- **Which runner ran a job:** `gh api repos/O/R/actions/runs/<id>/jobs --jq '.jobs[].runner_name'`.
  `factory-ci-1` means self-hosted, and self-hosted minutes are never billed. `GitHub Actions N`
  means hosted.
- **Why this matters:** on 2026-10-09 the account's hosted budget for private repositories ran out
  mid-migration. Every hosted job then failed before it started, with "The job was not started
  because recent account payments have failed or your spending limit needs to be increased". A
  private repository whose workflows still pin a hosted runner cannot run CI at all until the owner
  raises the limit.
- **Billed minutes:** Settings → Billing → Usage on github.com, or
  `gh api /users/<owner>/settings/billing/usage`. That API needs a token with the `user` scope
  (`gh auth refresh -h github.com -s user`).
- **Returning a repository to hosted runners** costs minutes, so it needs the owner's explicit
  decision. Run `tools/ci-runner/factory-ci disable OWNER/REPO`, which deletes the variable; the
  next run goes to `ubuntu-24.04`. To undo it, run `enable`. For a public repository this costs
  nothing; `untrust` also stops the dispatcher serving it.
