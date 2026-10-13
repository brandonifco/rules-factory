#!/bin/bash
# verify-live.sh -- the live host checks of decision 0081, run unprivileged by the account that runs
# factory-ci, on a prepared host with its VM provisioned. The two facts only root can read, the live
# nftables tables and frames on the uplink, come from /usr/local/sbin/factory-ci-collect through
# `sudo -n` (host/install-collector.sh); everything else is read as the user, and judged here.
#
# It changes no firewall rule, table, NAT rule, libvirt definition or limit. What it starts it stops:
# a listener on the bridge address, and the VM itself, which it shuts down again if it found it off.
# The capture is root's and ends on its own clock; nothing here signals it. Failure injection (a removed table, a removed NAT rule,
# an unloadable ruleset) runs in network namespaces, in test-isolation.sh, never on the live host.
#
#   1. the live tables equal what the installed file loads into an empty namespace; the only
#      exemption for `lo` is the postrouting drop's, and no rule names a physical interface; the
#      isolation unit is active, libvirtd requires it, the watch's timer runs and its status is
#      fresh;
#   2. libvirt: the network, the VM and the guest's filter as the kit defines them (factory-ci
#      verify), the filter bound to the guest's tap, and nothing but that tap in the bridge;
#   3. the kernel's limits on machine.slice, and the VM's own vCPUs and memory;
#   4. with a capture on the uplink: allowed traffic works and prohibited destinations stay
#      closed, each against a control from the host, while the guest also makes DHCP, ARP and IPv6
#      multicast traffic; no frame carries a libvirt MAC or a guest address, and no frame leaves
#      with a source MAC other than the uplink's;
#   5. the installed ruleset in network namespaces, with the watch and NAT failure (test-isolation).
# Exit 0 only when every check holds.
set -euo pipefail
kit="$(cd "$(dirname "$0")/.." && pwd)"
collect=/usr/local/sbin/factory-ci-collect
sudo -n "$collect" tables >/dev/null 2>&1 ||
  { echo "cannot run 'sudo -n $collect': install it once with sudo tools/ci-runner/host/install-collector.sh" >&2; exit 2; }
virsh() { command virsh -c qemu:///system "$@"; }
fci() { "$kit/factory-ci" "$@"; }
fail=0 pids=() work= vm= started=
ok() { echo "  ok  $*"; }; no() { echo "  X   $*"; fail=1; }
cleanup() { # the listener, the files, and the VM back as it was found
  local p
  for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; wait "$p" 2>/dev/null || true; done
  [[ -n $work ]] && rm -rf "$work"  # root's capture, if still running, ends on its own clock
  if [[ -n $started ]]; then fci stop >/dev/null 2>&1 || true; echo "  ..  $vm was off when this began; it is shutting down again"; fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM
work="$(mktemp -d)"
vm="$(set -a; . "$HOME/.config/factory-ci/host.env"; echo "$FACTORY_CI_VM")"
gmac="$(virsh domiflist "$vm" | awk '$3 == "factory-ci" {print $5}')"
[[ $gmac =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]] || { echo "cannot read $vm's MAC from libvirt" >&2; exit 1; }

echo "== the VM"
if [[ "$(virsh domstate "$vm")" != running ]]; then fci start >/dev/null; started=1; fi
for _ in $(seq 60); do fci ssh true 2>/dev/null && break; sleep 3; done
fci ssh true || { echo "the guest does not answer" >&2; exit 1; }
ok "$vm runs and answers (MAC $gmac)"

echo "== 1. the installed rules, live"
sudo -n "$collect" tables >"$work/tables"
live="$(sed '/^== file$/,$d' "$work/tables")" want="$(sed '1,/^== file$/d' "$work/tables")"
if [[ -n $want && $live == "$want" ]]; then ok "inet and bridge factory_ci equal /etc/factory-ci/isolation.nft"; else no "the live tables differ from /etc/factory-ci/isolation.nft"; fi
lo_rules="$(grep -n '"lo"' <<<"$live" || true)"
if [[ "$(grep -c . <<<"$lo_rules")" == 1 ]] && grep -qE 'chain postrouting' <<<"$(sed -n "1,${lo_rules%%:*}p" <<<"$live" | grep chain | tail -1)" &&
   grep -qE '^\s*oifname != \{ "lo", "virbr-fci" \} ip saddr 192\.168\.150\.0/24 drop$' <<<"$live"; then
  ok "the only lo exemption is the postrouting drop's: oifname != { lo, virbr-fci } ip saddr 192.168.150.0/24 drop"
else no "lo appears elsewhere, or the postrouting drop is not the expected one: $lo_rules"; fi
named="$(grep -oE '(iif|oif)name [!= ]*("[^"]*"|\{[^}]*\})' <<<"$live" | grep -oE '"[^"]*"' | tr -d '"' | sort -u | tr '\n' ' ')"
if [[ $named == "lo virbr-fci vnet* " ]]; then ok "the rules name only lo, virbr-fci and vnet*, never a physical interface"; else no "the rules name: $named"; fi
systemctl is-active --quiet factory-ci-isolation.service && ok "factory-ci-isolation is active" || no "factory-ci-isolation is not active"
[[ " $(systemctl show libvirtd.service -p Requires --value) " == *" factory-ci-isolation.service "* ]] && ok "libvirtd requires it" || no "libvirtd does not require it"
systemctl is-active --quiet factory-ci-isolation-watch.timer && ok "the watch's timer runs" || no "the watch's timer does not run"
read -r state at </run/factory-ci-isolation/status
age=$(( $(date +%s) - at ))
if [[ $state == loaded ]] && (( age < 30 )); then ok "the watch said $state ${age}s ago"; else no "the watch says $state, ${age}s ago"; fi

echo "== 2. libvirt"
fci verify >"$work/verify.txt" 2>&1 || true
if grep -q '^verify: PASS' "$work/verify.txt"; then ok "factory-ci verify passes ($(grep -c '^  ok' "$work/verify.txt") checks: network, VM, filter, guest probes, the installed rules in namespaces)"
else no "factory-ci verify: $( (grep '^  X' "$work/verify.txt" || tail -3 "$work/verify.txt") | head -3 | tr '\n' ' ')"; fi
tap="$(virsh domiflist "$vm" | awk '$3 == "factory-ci" {print $1}')"
if virsh nwfilter-binding-list | grep -qE "^ *$tap +factory-ci-egress *$"; then ok "the filter factory-ci-egress is bound to the guest's tap $tap"
else no "no factory-ci-egress binding on $tap"; fi
ports="$(ls /sys/class/net/virbr-fci/brif | tr '\n' ' ')"
[[ $ports == "$tap " ]] && ok "virbr-fci holds only $tap" || no "virbr-fci holds: $ports"

echo "== 3. limits"
cg=/sys/fs/cgroup/machine.slice
disk="$(lsblk -no PKNAME "$(findmnt -no SOURCE -T /var/lib/libvirt/images)" | head -1)"; disk="${disk:-$(basename "$(findmnt -no SOURCE -T /var/lib/libvirt/images)")}"
majmin="$(lsblk -dno MAJ:MIN "/dev/$disk" | tr -d ' ')"
read -r quota period <"$cg/cpu.max"
echo "  ..  cpu.max $quota/$period, cpu.weight $(cat "$cg/cpu.weight"), memory.high $(cat "$cg/memory.high"), memory.max $(cat "$cg/memory.max"), io.max $(grep "^$majmin " "$cg/io.max" || echo none)"
[[ $quota != max ]] && ok "CPU is capped at $((quota * 100 / period))% of one CPU" || no "CPU is not capped"
[[ "$(cat "$cg/memory.max")" != max ]] && ok "memory is capped at $(( $(cat "$cg/memory.max") >> 30 )) GiB" || no "memory is not capped"
grep -qE "^$majmin rbps=[0-9]+ wbps=[0-9]+ riops=[0-9]+ wiops=[0-9]+" "$cg/io.max" && ok "disk I/O is capped on /dev/$disk ($majmin)" || no "disk I/O is not capped on /dev/$disk"
info="$(virsh dominfo "$vm")"
ok "$vm has $(sed -n 's/^CPU(s): *//p' <<<"$info") vCPU and $(( $(sed -n 's/^Max memory: *\([0-9]*\).*/\1/p' <<<"$info") >> 20 )) GiB"

echo "== 4. the uplink, captured by root for 75 s while the guest works"
sudo -n "$collect" capture 75 >"$work/capture" 2>"$work/capture.err" & capture=$!
python3 -I -c "import socket,time;s=socket.socket();s.bind(('192.168.150.1',18443));s.listen();time.sleep(60)" & pids+=($!)
sleep 2
cat >"$work/probe.py" <<'EOF'
import socket, sys
for target in sys.argv[1:]:
    host, port = target.rsplit(":", 1)
    try:
        socket.create_connection((host, int(port)), 4).close(); print(target, "open")
    except OSError:
        print(target, "closed")
EOF
targets="api.nuget.org:443 github.com:443 udayton.edu:443 github.com:22 1.1.1.1:53 192.168.150.1:18443"
from_host="$(python3 -I - $targets <"$work/probe.py")"
from_guest="$(fci ssh python3 -I - $targets <"$work/probe.py")"
expect() { # target, host's, guest's, why
  local h g; h="$(awk -v t="$1" '$1 == t {print $2}' <<<"$from_host")"; g="$(awk -v t="$1" '$1 == t {print $2}' <<<"$from_guest")"
  if [[ $h == "$2" && $g == "$3" ]]; then ok "$1: host $h, guest $g ($4)"; else no "$1: host $h (want $2), guest $g (want $3) ($4)"; fi
}
expect api.nuget.org:443 open open "allowed"
expect github.com:443 open open "allowed"
expect udayton.edu:443 open closed "the campus, 131.238.0.0/16"
expect github.com:22 open closed "a port other than 80/443"
expect 1.1.1.1:53 open closed "DNS past the gateway"
expect 192.168.150.1:18443 open closed "a host service on the bridge address"
fci ssh 'curl -fsS -o /dev/null https://api.nuget.org/v3/index.json; ping -6 -c 2 ff02::1%ci0 >/dev/null 2>&1; sudo networkctl renew ci0; sleep 3; ping -c 1 -W 1 192.168.150.77 >/dev/null 2>&1; true'
wait "$capture" || true
read -r _ _ dev mac frames < <(grep '^== uplink ' "$work/capture") || { no "the capture said nothing: $(cat "$work/capture.err")"; dev=; }
if [[ -n $dev ]]; then
  if (( frames > 0 )); then ok "the capture on $dev saw $frames frames in 75 s"; else no "the capture on $dev saw no frame at all, so it proves nothing"; fi
  guest="$(sed -n '/^== uplink /,/^== other$/{/^== /d;p}' "$work/capture")"
  other="$(sed '1,/^== other$/d' "$work/capture")"
  if [[ -z $guest ]]; then ok "no frame on $dev to or from a libvirt MAC (52:54:00:...) or 192.168.150.0/24, guest MAC $gmac"
  else no "frames on $dev with a libvirt MAC or a guest address: $(head -3 <<<"$guest")"; fi
  if [[ -z $other ]]; then ok "no frame left $dev with a source MAC other than its own $mac"
  else no "frames left $dev with another source MAC: $(head -3 <<<"$other")"; fi
fi

echo "== 5. failure, in network namespaces (test-isolation; nothing live is touched)"
if FCI_RULES=/etc/factory-ci/isolation.nft "$kit/host/test-isolation.sh" >"$work/ns.txt" 2>&1 && grep -q 'isolation: PASS' "$work/ns.txt"; then
  ok "the installed rules pass: $(grep -E '^  ok  (with libvirt|the watch|a file)' "$work/ns.txt" | sed 's/^  ok  //' | tr '\n' ';')"
else no "test-isolation on the installed rules: $( (grep '^  X' "$work/ns.txt" || tail -3 "$work/ns.txt") | head -3 | tr '\n' ' ')"; fi

[[ $fail == 0 ]] && echo "verify-live: PASS" || echo "verify-live: FAIL"
exit "$fail"
