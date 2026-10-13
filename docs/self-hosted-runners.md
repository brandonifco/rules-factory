# Self-hosted runners

The owner's CI runs on KVM virtual machines the owner hosts, whatever the repository's visibility:
`factory-ci-1` on the home server, and, pending (see [A workstation host](#a-workstation-host)),
`factory-ci-2` on the owner's Office workstation. **Trust decides where a run executes, not
visibility**
([decision 0080](decisions/0080-execution-trust-not-visibility-decides-whether-a-run-reaches-the-self-hosted-runner.md)): the owner's own runs go to a VM, and everybody else's (a fork's pull
request, a bot's update, a contributor's edited workflow) stay on GitHub-hosted runners and can
never reach one. GitHub still schedules every job and still reports every check and verdict.

The two VMs are independent and share nothing: no network, key, token or cache
([decision 0081](decisions/0081-a-second-vm-adds-capacity-through-standing-registrations-and-a-public-repository-has-one-dispatcher.md)).
Each private repository has a standing registration on every VM, named for the VM, and GitHub gives
each job to exactly one runner; a VM that is off is offline and gets nothing. Public repositories
stay served only by `factory-ci-1`'s dispatcher. Sections that say "the VM" describe each VM; the
numbers are `factory-ci-1`'s unless they say otherwise.

The kit is [`tools/ci-runner/`](../tools/ci-runner/factory-ci): one host command, `factory-ci`, the
dispatcher it runs ([`dispatch.py`](../tools/ci-runner/dispatch.py)), and the guest baseline it
installs. Nothing in it is a credential.

## What runs where

| Runs | Runner | How they get there |
|---|---|---|
| Every run of a private repository (since 2026-10-09: reykholt, reykholt-web, reykholt-art, hallertau) | `factory-ci-1` VM, standing registration; `factory-ci-2` too once provisioned (pending), and GitHub picks one | The variable `FACTORY_RUNS_ON` ([0079](decisions/0079-a-repository-chooses-its-runner-through-factory-runs-on.md)). Only the owner and the owner's agents can start a run there, and GitHub runs no fork pull request of a private repository while its Actions setting for that stays off (keep it off). |
| The owner's own runs of a public repository (since 2026-10-10: see [Repositories](#repositories)) | `factory-ci-1` VM only, one one-job runner per job | The variable `FACTORY_RUNS_ON_TRUSTED` routes them; the **trusted dispatcher** on the home server admits each one and starts its runner ([The boundary](#the-boundary-for-public-repositories)). Never `trust` a public repository on a second VM. |
| Everything else in a public repository: fork pull requests, bots (Dependabot), a re-run of either | GitHub-hosted `ubuntu-24.04` | The runner line sends them there unmodified. A fork that rewrites its `runs-on` gets a job that is never served and is cancelled. Hosted runs are free on public repositories. |
| Publishing (`publish-map.yml`, a library's `publish.yml`) and manual maintenance workflows | GitHub-hosted `ubuntu-24.04` | Pinned in the file. The NuGet key is never on the VM. |

Every factory workflow, and this repository's own CI jobs, carry the one line `repository.py` holds
as `RUNS_ON_LINE`. `FACTORY_RUNS_ON_TRUSTED` takes a run only when its actor and triggering actor
are the owner and its code is this repository's, not a fork's. `FACTORY_RUNS_ON` takes every run.
**Never set `FACTORY_RUNS_ON` on a public repository**: a fork's run reads it too. `factory-ci
enable` sets the right one for the repository's visibility, and `factory-ci audit` reports the
wrong one.

There is **no fallback**. When every VM that could take a run, or the dispatcher, is down, a run that
asked for it waits in GitHub's queue and fails after GitHub's 24-hour queue limit. It does not move to a billed hosted
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
   unadmitted job is unfinished, or it could not read GitHub's lists to the end, it starts no runner
   in that repository and deletes every runner there still waiting for a job. For an admitted job it
   writes the admission into the guest as root, then starts a GitHub just-in-time runner: one job,
   exactly factory-ci's labels.
3. **The guest keeps one job from reaching another, and refuses and stops anything else.** A
   one-job runner runs as one of the repository's two accounts (`fci-<repo>`, `fcj-<repo>`), and
   an account never has two runners up, so a job never shares its UID with a listener still
   waiting for one. Root builds the runner under the root-owned `/srv/factory-ci-jit`, fills it,
   and only then hands it over. The job-started hook fails closed: on a one-job runner, an account
   that serves dispatch, or a guest whose dispatch policy it cannot read, it requires that the
   runner was started for this account less than 15 minutes before it got the job (its lease),
   that the job is of the repository the account serves, and that its run and attempt are
   admitted, all under `/run/factory-ci-trust` and `/etc/factory-ci`, where no runner account can
   write. Otherwise it kills the job's `Runner.Worker`. That kill is the point: after a failed
   hook the runner still runs actions' `pre:` and `post:` steps and any `if: always()` step.

`factory-ci trust` also sets the repository's fork pull request approval to
`all_external_contributors`. It is one more door, not the lock.

A public repository is served by one VM's dispatcher only. An admission is written into the guest of
the dispatcher that judged the run, so a job handed to a peer VM's waiting runner before the peer
admitted it would be killed by its hook. A dispatcher that sees a peer's one-job runner (a name in
`FACTORY_CI_PEERS`) in a repository it serves deletes its own waiting runners there, stops serving
it, and logs `NOT SERVED ... of a peer VM`. `audit` and `timings` know the peers: a peer's one-job
runner is not a standing registration, and a trusted repository this VM does not serve is a note
pointing at the peer's audit, not a finding.

What was verified on 2026-10-10 (runner 2.338.0), on a throwaway branch of rules-factory:

| Probe | Result |
|---|---|
| A job on a one-job runner with no admission | Refused; worker killed; its action's `pre:` step did not run (before the kill was added, it did) |
| A job whose `env:` forged `GITHUB_RUN_ID` and `GITHUB_RUN_ATTEMPT` to an admitted run, and set `BASH_ENV` to a command | Refused; `BASH_ENV` did not execute. A job's `env:` does not reach the hook |
| The owner's push | Admitted 9 s after it queued; ran on a one-job runner as `fci-rules-factory`; the runner deregistered itself and was reaped |
| An event that is not admitted (`create`), asking for `[self-hosted]` alone | Refused and cancelled while queued; it never had a runner. The owner's run queued beside it waited until it was gone |
| An admitted run, handed to a runner past its lease | Refused (`got its job after its lease`) |
| A second runner for an account that has one up | Refused by the guest |
| The owner's re-run (attempt 2) | Admitted as a new attempt; ran on a one-job runner 16 s after it queued |
| The owner's pull requests and pushes of rules-factory ([#638](https://github.com/brandonifco/rules-factory/pull/638) onward) | `validate`, `engine` and `documentation` ran on the VM and reported on the pull request's commits |

The design was reviewed independently before any public repository was enabled (AGENTS.md §6;
what it found and what answers it is in decision 0080's Consequences). Not probed live: a pull
request from a real fork, which needs a second GitHub account. Its run is
refused by the same head-repository rule as any other, which the dispatcher's tests hold
([`test_ci_runner_dispatch.py`](../tools/tests/test_ci_runner_dispatch.py)). **Repeat the probes
after a runner version change** (the runner updates itself): hook behaviour is the runner's, not
ours. [Running the boundary probe](#running-the-boundary-probe) says how.

## The VM

The table is `factory-ci-1`'s. `factory-ci-2` differs in its size and its host's controls, which
[A workstation host](#a-workstation-host) gives.

| | |
|---|---|
| Name | `factory-ci-1`, libvirt `qemu:///system`, autostart. The name is `FACTORY_CI_VM` ([The host file](#the-host-file)); the home server has no host file and keeps this default. |
| Guest | Ubuntu Server 24.04, from the cloud image the script pins by release and SHA-256 |
| Size | 6 vCPU (host-passthrough), 12 GiB, 100 GiB qcow2 in the `default` pool. The balloon has `freePageReporting`, which returns freed guest memory to the host. |
| Network | libvirt network `factory-ci`: NAT, bridge `virbr-fci`, 192.168.150.0/24, guest at .11 |
| Egress | nwfilter `factory-ci-egress` on the guest's NIC. Allowed: DHCP; DNS to the gateway; outbound TCP 80/443 and NTP to public addresses. Dropped: everything else, including the host, the LAN, every RFC 1918, link-local and CGNAT range, other libvirt networks, and IPv6. Only the host may open SSH to the guest. `factory-ci filter` defines it, and also drops the host's own global IPv4 networks and `FACTORY_CI_BLOCK`; on the home server (a private LAN) that adds nothing. |
| Admin | `ciadmin`, key-only SSH from the host (`~/.ssh/factory-ci_ed25519`, made for this VM and used for nothing else); passwordless sudo |
| Toolchain | `/opt/factory-ci` (root-owned, read-only to jobs): the .NET SDK the engines pin (10.0.112) and the .NET 8 runtime their tests also target, the GitHub CLI (the engines' `pr-policy` and `conformance-gate` call `gh`), Node, and the runner distribution. `/opt/hostedtoolcache` holds Python 3.12.15 and 3.12.14 (rules-factory's pin) in the hosted image's layout, for `actions/setup-python`. The Ubuntu packages a job would otherwise `sudo apt-get` (poppler-utils and others) are installed. All are pinned with hashes in [`guest/versions.env`](../tools/ci-runner/guest/versions.env). `actions/setup-dotnet` and `setup-python` find what they need and download nothing. A version that is not there fails the job, rather than being written into a cache another job could change. |
| Runners | One system account per private repository, `fci-<repo>`, and two per public one, `fci-<repo>` and `fcj-<repo>`; home `/srv/factory-ci/<account>` (0700). No sudo, no login shell, no SSH key. A private repository's standing runner is the service `factory-ci-runner@fci-<repo>`; a public repository's one-job runners are `factory-ci-jit-<id>`, generated from the same unit, in `/srv/factory-ci-jit/<id>`, removed when done, at most one per account at a time. All are systemd-hardened (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `ProtectProc=invisible`, so an account sees no other account's processes) and in `factory-ci.slice`, which caps all runners together at 11 GiB on a 12 GiB guest (`setup` scales it down on a smaller guest, below). |
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
`repo` scope. Each host's commands act on its own VM, the one its host file names; neither host
reaches the other's VM. `runners` and `audit` show GitHub's view, which includes the other VM's
runners.

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
one-time setting the owner makes). Lingering starts it at boot, but `gh` keeps its token in the
desktop keyring, which stays locked until a graphical login: on 2026-10-10 the dispatcher failed
eight times after a reboot until the owner logged in. So it reads its token from
`~/.config/factory-ci/dispatch-token` when that file exists ([Credentials](#credentials)), and
its journal's first line says which one it used (`token from ...`). `factory-ci status` shows
whether it is active and which one-job runners exist. A public repository's run that sits queued with nothing in `logs dispatch`
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

**A private repository** (on every VM that should serve it; run `register` from each host):

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
must name `factory-ci-1` or `factory-ci-2` (a standing runner) or `factory-ci-1-jit-<hex>` (a one-job runner).

### Repositories

| Repository | Visibility | Runner | Note |
|---|---|---|---|
| reykholt, reykholt-web, reykholt-art, hallertau | private | standing | `factory-ci-1` since 2026-10-09; `factory-ci-2` standing too, **pending** (not provisioned) |
| rules-factory | public | dispatch | since 2026-10-10; `validate`, `engine`, `documentation` (`publish-map`, `judge-rebuild` hosted) |
| faa-part-107 | public | dispatch | since 2026-10-10, re-produced from factory 1.6.0 (faa-part-107#147); `validate`, `pr-policy`, `conformance-gate`, `verdict-requeue` (`package`, `publish` hosted) |
| srd-52-combat | public | dispatch | since 2026-10-10, re-produced from factory 1.6.0 (srd-52-combat#81) |
| rules-corpus | public | dispatch | since 2026-10-10 (rules-corpus#22); `build-and-test` |
| rules-kernel | public | dispatch | since 2026-10-10 (rules-kernel#83); `build-and-test` (`pcg-vectors` hosted: it needs a C compiler; `publish` hosted) |
| tax-121-principal-residence, hoyle-backgammon, hoyle-blind-rebuild | public | hosted | **Not migrated.** Their workflows are factory-generated, so they change only by re-producing, and they cannot be re-produced: each consumes a map published before decision 0048 (no `map/verification.json`) and has no rules-corpus build definition (0074). A new map version is a publication, the owner's decision. |
| brandonifco.github.io, brandonifco, hollow-crown | public | — | No workflows. |

### Running the boundary probe

On a throwaway branch of a served public repository, with the dispatcher **stopped**
(`systemctl --user stop factory-ci-dispatch`):

1. A workflow on `push` to that branch, one job with `runs-on: [self-hosted, linux, x64,
   factory-ci]`, a step that prints a marker, and a `uses:` of a JavaScript action on the same
   branch whose `pre:` prints another. Push it; the job queues.
2. Start a one-job runner by hand without admitting the run: `gh api -X POST
   repos/O/R/actions/runners/generate-jitconfig` (labels as above, `runner_group_id=1`) piped as
   `.encoded_jit_config` into `factory-ci ssh "sudo /opt/factory-ci/bin/dispatch-guest start <name> a <id>"`.
   The job must fail with neither marker anywhere; the guest's journal says `refused run`.
3. Give the job `env:` with `GITHUB_RUN_ID`/`GITHUB_RUN_ATTEMPT` of a run you admit by hand
   (`dispatch-guest admit <name> <run>-<attempt>`) and a `BASH_ENV` that writes a file in the
   account's home. Repeat 2: refused, no file.
4. Start the dispatcher and push again: admitted, run, runner gone afterwards.
5. A workflow `on: create` asking for `[self-hosted]`, then create a branch: refused and cancelled.
6. Start a runner by hand with nothing queued, set its lease in `/run/factory-ci-trust/runners/<id>`
   to the past, push and admit: refused after its lease. Start a second on the same lane: refused.

Remove the admission, the branches and anything left in the guest (`dispatch-guest reap`) afterwards.

## Measured

On 2026-10-10, the jobs' own timestamps (`factory-ci timings`; queue is created to started, run is
started to completed), successful runs only, against each repository's hosted history:

| Repository | Job | Hosted median run (n) | factory-ci run | factory-ci queue |
|---|---|---|---|---|
| rules-factory | `validate` (pull request) | 760 s (34) | 280 s | 19 s |
| rules-factory | `validate` (push, full) | 729 s (19) | 275 s | 50 s |
| rules-factory | `engine` | 450 s (36) | 269–275 s | 15–40 s |
| rules-corpus | `build-and-test` | 121 s (27) | 47 s | 17 s |
| rules-kernel | `build-and-test` | 120 s (39) | 63 s | 38 s |
| faa-part-107 | `validate` | 87 s (9) | 40 s | 54 s |
| srd-52-combat | `validate` | 53 s (23) | 30 s | 47 s |
| any | `pr-policy`, `conformance-gate` | 8 s | 5–7 s | 21–39 s |

- **Run time** is about 40% to 60% shorter on the VM: 6 vCPU with host-passthrough against the hosted
  runner's 4, and the account's NuGet and pip caches kept between jobs.
- **Queue time** is what dispatch costs: hosted jobs start in 2 to 3 s; a dispatched job waits for
  the dispatcher's 10 s poll, a one-job runner's start (about 4 s) and, when a repository's two
  jobs are already running, a lane. A run's total time still falls because the jobs it waits for
  are the long ones.
- **Cancellations and recovery**: a refused run was cancelled while queued and never had a runner;
  a cancelled run's job took GitHub up to about 90 s to finish, during which nothing started beside
  it. Until rules-factory#639, a one-job runner was known in the guest by GitHub's runner
  number alone, which GitHub assigns per repository; two repositories' runners with the same number
  collided, the start was refused, the runner deleted and started again. Nothing ran where it
  should not, but faa-part-107's `conformance-gate` queued for 191 s. The guest now knows a runner
  by its repository and number together.
- **Slots**: of the 20 jobs the VM ran from 18:00 to 18:45 UTC, while four repositories' CI was
  migrating at once, 19 took a job slot within a second and one waited 18 s. The wait that remains
  is dispatch, not capacity.
- **CPU and memory** (`sar` every 10 s, 18:25 to 18:56 UTC): the guest was over 10% busy in 23 of
  189 samples, with a median of 48% and a 90th percentile of 82% when busy; it touched 90% twice
  (96% at the peak, two heavy jobs together). Memory in use peaked at 2.3 GiB of 12 GiB.

These are `factory-ci-1`'s measurements; `factory-ci-2` has none. Nothing measured asks for more capacity: a second slot's worth of CPU is rarely in use, memory is
at a fifth, and a job almost never waits for a slot. `factory-ci-1` stays at 6 vCPU, 12 GiB and two slots. Re-measure with `factory-ci timings`
and `factory-ci ssh 'sar -u -r 10'` before changing any of them.

## The host file

Every `factory-ci` command and the dispatcher read `~/.config/factory-ci/host.env` (mode 0600;
`FACTORY_CI_HOST_ENV` names another path). The home server has none and keeps the defaults:
`factory-ci-1`, 6 vCPU, 12 GiB. Office's:

```
FACTORY_CI_VM=factory-ci-2
FACTORY_CI_PEERS=factory-ci-1
FACTORY_CI_VCPUS=6
FACTORY_CI_MEMORY_MB=8192
FACTORY_CI_DISK=100G
FACTORY_CI_BLOCK=131.238.0.0/16
FACTORY_CI_ISOLATION=required
FACTORY_CI_DNS="1.1.1.1 9.9.9.9"
```

`FACTORY_CI_BLOCK` adds ranges the guest may not reach to the host's own networks. `required`
makes `provision` and `start` refuse unless the host's isolation is active. `register` refuses when
the guest's hostname is not `FACTORY_CI_VM`, or when an online runner of that name exists that this
guest does not hold. The runner's `config.sh` runs with `--replace`, so without that a host that
forgot its file would take over `factory-ci-1`'s registrations.

## A workstation host

**Status: pending.** `factory-ci-2` is not provisioned. Host isolation is not yet installed, and the
university's authorization for host NAT is not yet obtained. Everything below is the procedure and
the configuration, and nothing in it has been run or measured on Office. Office is Ubuntu 24.04,
an i7-13700 (24 threads) with 31 GiB, NVMe measured at 3.3 GB/s write and 4.4 GB/s read, on the
University of Dayton's wired network (131.238.112.0/21, inside 131.238.0.0/16), with ufw active
and forwarding dropped.

**The network rule.** The campus enforces MAC filtering and may shut a switch port that shows a
second MAC. So **no guest MAC may ever reach the physical link**: the guest is only on libvirt's NAT
network `factory-ci` (bridge `virbr-fci`, 192.168.150.0/24, bound to no physical interface), never
bridged, macvtap, direct or passed through. Two layers hold it:

- **The guest's nwfilter** `factory-ci-egress`, as above, which `factory-ci filter` defines with the
  host's networks and `FACTORY_CI_BLOCK` dropped. Office's own address is public (131.238.0.0/16),
  which the fixed private-range drops would not have covered.
- **The host's layer**, [`host/isolation.nft`](../tools/ci-runner/host/isolation.nft), installed by
  `host/prepare-host.sh` as `/etc/factory-ci/isolation.nft` and loaded by the unit
  `factory-ci-isolation.service`, which `libvirtd.service` Requires (drop-in
  `/etc/systemd/system/libvirtd.service.d/10-factory-ci-isolation.conf`), so no VM starts without
  it. It owns the tables `inet factory_ci` and `bridge factory_ci` and never flushes ufw's or
  libvirt's. It holds: `virbr-fci` forwards frames only to `vnet*` taps; the guest reaches only TCP
  80/443 and UDP 123 on non-blocked addresses, and the host only for DHCP and DNS; nothing opens a
  connection in to the guest; a guest packet that would leave untranslated (NAT missing) is dropped;
  no IPv6.

DNS: the guest's dnsmasq forwards to `FACTORY_CI_DNS` (1.1.1.1, 9.9.9.9), never the campus
resolvers (10.72.27.23, .24), which answer for internal names; DNS to anything but the gateway is
dropped. `prepare-host.sh` also turns off the libvirt package's stock `default` network (virbr0) and
its autostart, and turns `ip_forward` off when no NAT network runs.

**Resource controls** (`machine.slice`, set by `prepare-host.sh`; change live with `sudo systemctl
set-property machine.slice ...`):

| Control | Value | Kind |
|---|---|---|
| `CPUWeight` | 50 | soft: the user wins under contention |
| `CPUQuota` | 600% | hard: 6 CPUs' time |
| `MemoryHigh` / `MemoryMax` | 9G / 10G | hard; the guest's RAM is 8 GiB |
| `IOReadBandwidthMax`, `IOWriteBandwidthMax` | 500M each | hard; about 15% of the measured bandwidth |
| `IOReadIOPSMax`, `IOWriteIOPSMax` | 20000 each | hard; on the disk holding `/var/lib/libvirt/images` |

The VM is 6 vCPU, 8 GiB and a 100 GiB thin qcow2, with 2 job slots. Freed guest memory goes back
to the host (the balloon's `freePageReporting`), and `setup-guest.sh` scales the guest slice to
leave 1 GiB (`MemoryMax`) and 2 GiB (`MemoryHigh`) for the guest's system whenever the guest has
under 11 GiB. The size follows `factory-ci-1`'s peak of 2.3 GiB and 96% of 6 vCPU for two heavy
jobs, and Office's desktop already using about 9 GB. To resize, shut the VM down and use `virsh
setvcpus` and `setmaxmem` with `--config`; the host's caps change with `set-property`.

**Bring-up**, in this order. Step 2 needs sudo and installs the host's firewall layer and libvirt. Step 5 onward starts libvirt's
NAT network, which changes host networking, so it **waits for the university's written
authorization** (below). The tcpdump in step 6 needs sudo.

```bash
tools/ci-runner/host/prepare-host.sh --dry-run --block 131.238.0.0/16 --cpu 6 --memory-max 10G --io-bandwidth 500M --io-iops 20000   # 1: read every step
sudo tools/ci-runner/host/prepare-host.sh --block 131.238.0.0/16 --cpu 6 --memory-max 10G --io-bandwidth 500M --io-iops 20000        # 2: sudo
tools/ci-runner/factory-ci verify                 # 3: before provisioning: the ruleset passes test-isolation; host checks
# 4: only after UDit has authorized host NAT for this workstation:
tools/ci-runner/factory-ci provision              # 5: network, filter, VM (refuses unless isolation is active)
tools/ci-runner/factory-ci verify                 # 6: with the guest running: guest probes; then root's nft listing and
                                                  #    a tcpdump on eno1 for ether src 52:54:00:fc:01:01 (must show no frame)
tools/ci-runner/factory-ci setup
tools/ci-runner/factory-ci register brandonifco/hallertau   # one repository first; then the other three
```

**Verification.** `host/test-isolation.sh` needs no privilege. In network namespaces it first shows
each probe connecting without the ruleset and refused with it, and checks NAT, NAT missing and the
MAC capture. It is also a test, `tools/tests/test_ci_runner_isolation.py`, skipped where
unprivileged namespaces are unavailable. `factory-ci verify` lists what else it checks (no physical
port in a bridge, no macvtap, the libvirt network and VM XML, the nwfilter's drops, nothing but the
gateway listening on :53, the guest's reach). Until the live checks in step 6 have run, the
properties above are **proven only in namespaces**: the real nftables load order with ufw and
libvirt, libvirt's actual NAT rules, and that no frame leaves `eno1` are not yet shown.

**Availability.** A workstation may sleep or shut down. libvirt-guests saves the VM; its runners go
offline, and GitHub sends private-repository jobs to `factory-ci-1`. A job it held at that moment
fails and is re-run.

**Rollback**, which never touches `factory-ci-1`:

```bash
tools/ci-runner/factory-ci deregister brandonifco/<repo>    # each private repository; GitHub then sends everything to factory-ci-1
tools/ci-runner/factory-ci destroy-vm
virsh -c qemu:///system net-destroy factory-ci && virsh -c qemu:///system net-undefine factory-ci
sudo tools/ci-runner/host/prepare-host.sh --remove          # refuses while a VM runs
```

The packages stay unless removed with apt.

**The university's policy.** The Fair, Responsible and Acceptable Use policy (approved 2022) and the
2003 guidelines say nothing specific about NAT or VMs. The guidelines forbid DNS or DHCP servers
that interfere with the university network (libvirt's dnsmasq binds only to `virbr-fci`, and
`verify` checks that nothing else listens on :53). The 2025 IT Remote Access policy says solutions
that circumvent routing and security controls will be disabled. So host NAT for `factory-ci-2` waits
for UDit's written authorization. NAT hides the guest's MAC, not its traffic, and nothing here is
meant to evade campus controls.

## Credentials

- **The dispatcher's token** is a fine-grained personal access token in
  `~/.config/factory-ci/dispatch-token` on the host: one line, mode 0600, owned by the host
  account; the dispatcher refuses a file anyone else can read, or a link. It is scoped to the
  repositories served by dispatch and nothing else, with these repository permissions: **Actions**
  read and write (read queued runs, cancel a refused one), **Administration** read and write
  (create and delete one-job runners), **Contents** read (the activity log), **Metadata** read
  (always included). It never leaves the host. `factory-ci dispatch-check` proves it can do every
  one of those things on every served repository, the two writes without effect (a cancel of a
  finished run, and a one-job runner created and deleted unstarted); run it after creating or
  rotating the token, and after `trust`ing a new repository, which must be added to the token's
  repositories first. Rotate it before it expires: create the new one, replace the file, run
  `dispatch-check`, `systemctl --user restart factory-ci-dispatch`, then delete the old token on
  GitHub. Without the file the dispatcher uses the owner's `gh` login, which works only after a
  graphical login. `audit` and `timings` read every repository and always use `gh`.
- **Registration tokens** are fetched by `factory-ci register` from the GitHub API and passed to the
  guest on stdin. They are never written to disk, an argument list, or a log, and they expire
  within an hour.
- **Runner credentials** (`.credentials`, `.credentials_rsaparams`) live only in each runner
  account's 0700 home. To rotate them, run `factory-ci register OWNER/REPO` again: `--replace` swaps
  the GitHub-side runner, and the old credentials are deleted first. To revoke one, run
  `factory-ci deregister OWNER/REPO`, or delete the runner under the repository's Settings → Actions →
  Runners.
- **Each host has its own** admin key, `gh` login and (on the home server only) dispatcher token;
  none is copied between hosts. Office has no dispatcher token, because it runs no dispatcher.
- **The admin key** `~/.ssh/factory-ci_ed25519` never leaves its host. To rotate it, generate a new
  key, append its public half to `ciadmin`'s `authorized_keys` through `factory-ci ssh`, test it,
  then remove the old line.

## Recovery

**Rebuild from the baseline.** This covers a broken or suspect VM, on the host that holds it; the
other VM is untouched. (`factory-ci-2`'s rollback is in [A workstation host](#a-workstation-host).)

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
  `factory-ci-1` or `factory-ci-2` means self-hosted, and self-hosted minutes are never billed. `GitHub Actions N`
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
