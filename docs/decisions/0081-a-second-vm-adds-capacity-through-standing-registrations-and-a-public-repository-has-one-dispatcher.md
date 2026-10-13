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
- The campus network filters by MAC address, and a switch port that sees a second MAC may shut
  down. A guest MAC on the physical link would cost the workstation its network. Nothing in the kit
  bridged the guest to a physical NIC, but nothing on the host would have stopped it.
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
5. **A workstation host has its own isolation layer, and no VM starts without it.** The guest is
   only ever on the libvirt NAT network `factory-ci`, bound to no interface: never bridged,
   macvtap, direct or passed through, so the only MAC on the physical link is the host's.
   `host/isolation.nft` is a second layer under the guest's nwfilter, in two nftables tables of its
   own, `inet` and `bridge factory_ci`, which never flush or replace ufw's or libvirt's. The guest
   bridge forwards frames only to the guest's tap. The guest reaches only TCP 80/443 and NTP on
   addresses outside the blocked ranges, and the host only for DHCP and DNS. Nothing outside opens a
   connection to it, and only replies reach it, so a connection open before the rules loaded
   carries nothing after. A guest packet that leaves untranslated is dropped, and nothing passes
   over IPv6. The host's dnsmasq may ask only the named resolvers. `prepare-host.sh` installs
   libvirt with service starts held back, then the layer, through a unit that `libvirtd` requires.
   A timer compares the live tables with the file every 10 seconds, reloads them if anything
   removed or changed them, and takes the guest's bridge down if it cannot. Isolation is required
   on any host that installed it and for any VM but `factory-ci-1`. There, `provision` and `start`
   refuse unless the layer is live and holds the host file's ranges and resolvers. They also refuse
   a network or VM that is not the kit's. `host/test-isolation.sh` proves the ruleset in unprivileged network namespaces: each
   probe first connects without it, then is refused with it. `factory-ci verify` checks a live
   host: libvirt's record of the network and the VM, every bridge, the DNS listeners, and probes
   from inside the guest.
6. **The guest's DNS bypasses the host's resolver.** `FACTORY_CI_DNS` makes the network's dnsmasq
   forward to public resolvers. A campus resolver answers for internal names. DNS to anywhere but
   the gateway is dropped.
7. **A guest smaller than the slice's caps keeps the same headroom.** Below 11 GiB, `setup` caps
   the slice at the guest's memory less 1 GiB (`MemoryMax`) and less 2 GiB (`MemoryHigh`). A
   12 GiB guest keeps the slice file's 10G and 11G.
8. **A workstation host yields to its user, within hard caps.** `prepare-host.sh` sets
   `machine.slice`, which holds every VM. CPU weight 50 against the user's 100 means the user wins
   under contention. Optional hard limits cap CPU time (`--cpu`), memory (`--memory-max`, with
   `MemoryHigh` 1G under it), and bandwidth and IOPS on the disk that holds the images. All of them
   can be changed live with `systemctl set-property`. The VM's balloon returns freed guest memory
   to the host, so an idle VM does not hold the memory it once used. On Office the limits are 6
   CPUs, 10G, and 500 MB/s and 20,000 IOPS each way. The VM has 6 vCPU, 8 GiB, a 100 GiB thin disk
   and two job slots.

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
- NAT keeps the guest's MAC off the physical link. It does not hide the guest's traffic, which
  leaves from the workstation's address. Whether the university permits a VM behind host NAT on a
  wired port is the university's decision. Its published policies (Fair, Responsible and
  Acceptable Use, 2022; IT Remote Access, 2025) do not say. The owner holds its written
  authorization for a VM behind NAT on this workstation (recorded 2026-10-13). Its restriction is
  on unauthorized routers and additional MAC addresses on the physical network. The authorization
  covers host-only NAT, with no guest MAC on the physical link, no bridge, macvtap or direct
  attachment, and no guest DHCP, DNS or routing offered to the campus. A change beyond that goes
  back to the university. Nothing here disguises the guest or evades campus controls.
- A full flush of the host's ruleset by root removes every layer at once, libvirt's and ufw's
  included. The watch restores this layer within about 10 seconds, or takes the guest's bridge
  down. For those seconds the guest is unfiltered, behind NAT that is gone too.
- The design was reviewed independently (AGENTS.md §6, Codex, at `dc6288a`) before the host was
  prepared. It found nine gaps: isolation was opt-in; a stale network was trusted; the unit stayed
  active after its tables were gone; dnsmasq could ask any resolver; removal read a failed `virsh`
  as no VM; held connections survived a load; the root ruleset lacked the host file's ranges; a
  failed install left the default network autostarting; and the leak test watched only the MAC.
  Each is answered in point 5. `test-isolation.sh` holds the ruleset's share of them, and each
  check of it fails under a mutation of its rule. The one exception is the drop of a guest's reply
  on a connection opened from outside, which the untranslated-packet drop also covers.
- A workstation is not always on. When it sleeps or shuts down, its VM is saved by libvirt-guests,
  and its runners are offline until it resumes. A job it held when it went away fails as a job on
  a dead VM does, and is re-run (the runbook, Host restart). GitHub sends nothing to an offline
  runner.

## What this does not decide

Which public repository, if any, moves to `factory-ci-2`, and whether a third VM is added. Each
VM's size is the runbook's, measured, as `factory-ci-1`'s is.
