# 0081 — A second VM adds capacity through standing registrations, and a public repository has one dispatcher

## Status

Accepted — 2026-10-13. Records the owner's direction on
[#643](https://github.com/brandonifco/rules-factory/issues/643). Extends
[0079](0079-a-repository-chooses-its-runner-through-factory-runs-on.md) and
[0080](0080-execution-trust-not-visibility-decides-whether-a-run-reaches-the-self-hosted-runner.md),
which describe one KVM virtual machine. Changes no workflow, recipe, label or runner line, so no
engine is re-produced and no required check changes.

## Context

On 2026-10-13 the owner directed a second CI VM, `factory-ci-2`, on the Office workstation. It adds
capacity beside `factory-ci-1` on the home server and does not replace it. The kit was written for
one VM, and reading it found four places where that matters:

- Every command defaulted to `factory-ci-1`. A second host that forgot `FACTORY_CI_VM` would make a
  guest named `factory-ci-1`, and `register` passes `--replace`, so its runner would take over the
  home server's registration on GitHub.
- The egress filter drops the private, link-local and CGNAT ranges, then accepts 80/443 to any
  public address. The home server's LAN is private. The Office host's is not: it sits in the
  University of Dayton's public 131.238.0.0/16, so a job could have reached the host's own LAN
  address and the institution's internal web services from an address inside it.
- The guest slice caps all runners at 11G, which is a 12 GiB guest's number. A smaller guest,
  which a workstation calls for, would have had no effective cap.
- The dispatcher assumes it is alone. An admission is written into the guest of the dispatcher that
  judged the run. If two dispatchers served one public repository, each would start runners for the
  same queued jobs. GitHub hands a job to whichever matching runner is idle, so a job could reach
  the other VM's waiting runner before that dispatcher had admitted it, and its hook would kill the
  job. Today a peer's runner counts as foreign, so each dispatcher would refuse to serve the
  repository at all. That is safe, but it serves nothing.

A private repository needs no coordination. Each VM holds its own standing registration, named for
the VM, and GitHub's broker assigns a job to exactly one runner session. That guarantee is GitHub's.
This record does not reimplement it.

## Decision

1. **A host names its VM in one file.** `~/.config/factory-ci/host.env` (or
   `$FACTORY_CI_HOST_ENV`) sets `FACTORY_CI_VM`, the VM's size, its peers and any extra blocked
   ranges. Every `factory-ci` command and the dispatcher read it. A host without the file keeps
   today's defaults, so the home server is unchanged. `register` refuses when the guest's hostname
   is not the VM's name. It also refuses to replace an online runner of that name that this guest
   does not hold.
2. **A private repository is registered on every VM.** Each VM's runner is named for the VM
   (`factory-ci-1`, `factory-ci-2`), with the same labels. GitHub chooses between them. Each guest
   still bounds its own concurrency with its own job slots. A VM that is off or stopped is offline,
   and GitHub sends its jobs to the other.
3. **A public repository is served by exactly one VM's dispatcher.** `trust` it on one VM only. A
   dispatcher that finds a peer's one-job runner in a repository it serves retires its own waiting
   runners and stops serving that repository, and says why. `audit` and `timings` recognise the
   peers named in `FACTORY_CI_PEERS`: a peer's one-job runner is not a standing registration, and
   a trusted repository this VM does not serve is a note pointing at the peer's audit, not a
   finding. Without peers, both stay findings, as before.
4. **The egress filter drops the host's own networks.** `factory-ci filter` defines the filter. It
   adds a drop for each global IPv4 network on the host and for each range in `FACTORY_CI_BLOCK`,
   ahead of the 80/443 accept. Run it again when the host changes networks.
5. **A guest smaller than the slice's caps keeps the same headroom.** Below 11 GiB, `setup` caps
   the slice at the guest's memory less 1 GiB (`MemoryMax`) and less 2 GiB (`MemoryHigh`). A
   12 GiB guest keeps the slice file's 10G and 11G.
6. **A workstation host yields to its user.** `host/prepare-host.sh`, run once with sudo, installs
   libvirt and lowers `machine.slice`'s CPU weight to 50 against the user's 100. Under contention
   the VM takes idle CPU, not the user's. The VM's vCPU count and memory are hard upper bounds.

## Consequences

- The two VMs share nothing: not a network, a key, a token or a cache. Each host has its own NAT
  network (the same addresses on each, never routed between them), its own admin key and its own
  `gh` login. Losing either VM leaves the other serving every private repository.
- Capacity for public repositories does not grow. They are served by `factory-ci-1`'s dispatcher,
  as before. Moving one to `factory-ci-2` means `untrust` on the home server, `trust` there on
  Office, a dispatcher and its token on Office, and `dispatch-check`. That is an operation on the
  home server, so it waits for the owner.
- Serving one public repository from both VMs at once needs one place that writes admissions into
  both guests: a single dispatcher driving two guests, or admissions both can read. This record
  does not build that. It keeps the safe refusal until there is a measured need.
- A workstation is not always on. When it sleeps or shuts down, its VM is saved by libvirt-guests,
  and its runners are offline until it resumes. A job it held when it went away fails as a job on
  a dead VM does, and is re-run (the runbook, Host restart). GitHub sends nothing to an offline
  runner.

## What this does not decide

Which public repository, if any, moves to `factory-ci-2`, and whether a third VM is added. Each
VM's size is the runbook's, measured, as `factory-ci-1`'s is.
