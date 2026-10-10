# Self-hosted runners for private engines

A produced engine's workflows (`validate`, `pr-policy`, `conformance-gate`, `verdict-requeue`)
run wherever the repository's Actions variable `FACTORY_RUNS_ON` sends them
([decision 0079](decisions/0079-a-repository-chooses-its-runner-through-factory-runs-on.md)). Unset, they run on GitHub's hosted
`ubuntu-24.04`, as they always have. Set to `["self-hosted","linux","x64","factory-ci"]`, they run on
the owner's KVM runner VM, which this page describes. GitHub still schedules every job, and still
reports every check and verdict.

The kit is [`tools/ci-runner/`](../tools/ci-runner/factory-ci): one host command, `factory-ci`,
plus the guest baseline it installs. Nothing in it is a credential.

## What runs where

| Repository | Runner | Why |
|---|---|---|
| Private engines and their private companions (since 2026-10-09: reykholt, reykholt-web, reykholt-art, hallertau) | `factory-ci` VM | Hosted minutes on private repositories are billed. |
| Public repositories, including this one | GitHub-hosted | Hosted runs are free there. These repositories accept contributions from anyone, and a pull request's code must never run on the owner's hardware. **Never set `FACTORY_RUNS_ON` on a public repository**: this is a deliberate exception, not a migration left unfinished. `factory-ci enable` refuses a public repository. |

There is **no fallback**. When the VM is down, a private repository's jobs wait in GitHub's
queue, and fail after GitHub's 24-hour queue limit. They do not move to a billed hosted runner.
Moving a repository back to hosted runners is a deliberate act, described below.

## The VM

| | |
|---|---|
| Name | `factory-ci-1`, libvirt `qemu:///system`, autostart |
| Guest | Ubuntu Server 24.04, from the cloud image the script pins by release and SHA-256 |
| Size | 6 vCPU (host-passthrough), 12 GiB, 100 GiB qcow2 in the `default` pool |
| Network | libvirt network `factory-ci`: NAT, bridge `virbr-fci`, 192.168.150.0/24, guest at .11 |
| Egress | nwfilter `factory-ci-egress` on the guest's NIC. Allowed: DHCP; DNS to the gateway; outbound TCP 80/443 and NTP to public addresses. Dropped: everything else, including the host, the LAN, every RFC 1918, link-local and CGNAT range, other libvirt networks, and IPv6. Only the host may open SSH to the guest. |
| Admin | `ciadmin`, key-only SSH from the host (`~/.ssh/factory-ci_ed25519`, made for this VM and used for nothing else); passwordless sudo |
| Toolchain | `/opt/factory-ci` (root-owned, read-only to jobs): the .NET SDK the engines pin (10.0.112) and the .NET 8 runtime their tests also target, the GitHub CLI (the engines' `pr-policy` and `conformance-gate` call `gh`), Node, and the runner distribution. `/opt/hostedtoolcache` holds Python 3.12 in the hosted image's layout, for `actions/setup-python`. The Ubuntu packages a job would otherwise `sudo apt-get` (poppler-utils and others) are installed. All are pinned with hashes in [`guest/versions.env`](../tools/ci-runner/guest/versions.env). `actions/setup-dotnet` and `setup-python` find what they need and download nothing. A version that is not there fails the job, rather than being written into a cache another job could change. |
| Runners | One system account per repository, `fci-<repo>`, home `/srv/factory-ci/fci-<repo>` (0700). No sudo, no login shell, no SSH key. Service `factory-ci-runner@fci-<repo>`: systemd-hardened (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`), and in `factory-ci.slice`, which caps all runners together at 11 GiB. |
| Concurrency | `/etc/factory-ci/slots`, which is 2 (measured; see Everyday operation). GitHub cannot share one runner registration between personal repositories, so each repository's listener could take a job at the same moment. The job-started hook takes one of N slot locks before the first step and keeps it until the job's worker exits. A job that waits says so in its log, and the wait counts against its `timeout-minutes`. |
| Workspaces | The job-completed hook empties the checkout and `_temp`. The job-started hook empties whatever a job killed with the VM left behind. Every job starts from a fresh clone. |
| Kept between jobs | Only each repository's own NuGet global packages folder, in its own home. The engines' locked restore still verifies every package against its lock file. No cache is shared between repositories, and the shared toolchain is read-only. |

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
- Only trusted code may run here: the owner's private repositories, whose pull requests come only
  from the owner and the owner's agents. GitHub does not run fork pull requests of a private
  repository unless the repository's Actions settings allow it. Keep that setting off.

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
```

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

1. It must be private. Public repositories stay hosted.
2. Its workflows must read `FACTORY_RUNS_ON`. A produced engine does once it is produced from a
   factory release that contains decision 0079: re-produce it on its own issue
   (`tools/re-produce.sh` after moving `factory.commit`). An engine produced before factory 1.3
   first needs a rules-corpus build definition beside each corpus (decision 0074). A repository's own hand-written workflow
   uses the same line: `runs-on: ${{ fromJSON(vars.FACTORY_RUNS_ON || '"ubuntu-24.04"') }}`.
   The default it falls back to is that file's existing runner.
3. Its jobs must not need `sudo`. Anything a job installs with `apt-get` belongs in
   `APT_PACKAGES` in `guest/versions.env`, and the step should skip the install when the tool is
   already present.
4. Register it, then switch it over:

   ```bash
   tools/ci-runner/factory-ci setup                          # if versions.env changed
   tools/ci-runner/factory-ci register brandonifco/<repo>    # one registration per repository
   tools/ci-runner/factory-ci enable brandonifco/<repo>      # sets FACTORY_RUNS_ON
   ```

5. Push a pull request and confirm in the job metadata that it ran on the VM:
   `gh api repos/O/R/actions/runs/<id>/jobs --jq '.jobs[]|[.name,.runner_name,(.labels|join(","))]'`
   must name `factory-ci-1`.

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
```

A rebuild takes about ten minutes. It loses only caches. Each `register` replaces that
repository's old runner on GitHub.

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
  next run goes to `ubuntu-24.04`. To undo it, run `enable`.
