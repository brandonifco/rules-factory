#!/bin/bash
# verify-root.sh -- the host-level checks of decision 0081 that need root, made passively. Run with
# sudo by the account that runs `factory-ci`, on a prepared host with its VM provisioned.
#
# It changes no firewall rule, table, NAT rule, libvirt definition or limit: it reads them. What it
# starts it stops: captures, one listener on the bridge address, and the VM itself, which it shuts
# down again at the end if it found it off. Failure injection (a removed table, a removed NAT rule,
# an unloadable ruleset) runs in network namespaces, in test-isolation.sh, never on the live host.
#
#   1. the live tables equal what the installed file loads into an empty namespace; the only
#      exemption for `lo` is the postrouting drop's, and no rule names a physical interface; the
#      isolation unit is active, libvirtd requires it, the watch's timer runs and its status is
#      fresh;
#   2. libvirt: the network, the VM and the guest's filter as the kit defines them (factory-ci
#      verify), the filter bound to the guest's tap, and nothing but that tap in the bridge;
#   3. the kernel's limits on machine.slice, and the VM's own vCPUs and memory;
#   4. with captures on the uplink: allowed traffic works and prohibited destinations stay closed,
#      each against a control from the host, while the guest also makes DHCP, ARP and IPv6
#      multicast traffic; no frame carries the guest's MAC, no frame leaves with another source MAC
#      than the uplink's, and no packet carries a guest address;
#   5. the installed ruleset in network namespaces, with the watch and NAT failure (test-isolation).
# Exit 0 only when every check holds.
set -euo pipefail
kit="$(cd "$(dirname "$0")/.." && pwd)"
[[ $(id -u) == 0 && -n ${SUDO_USER:-} && $SUDO_USER != root ]] || { echo "run with sudo, as the account that runs factory-ci" >&2; exit 2; }
home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
as_user() { runuser -u "$SUDO_USER" -- env HOME="$home" sg libvirt -c "$*"; }
fci() { as_user "$kit/factory-ci $*"; }
fail=0 pids=() work= vm= started=
ok() { echo "  ok  $*"; }; no() { echo "  X   $*"; fail=1; }
cleanup() { # every capture and listener this started, its files, and the VM back as it was found
  local p
  for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
  [[ -n $work ]] && rm -rf "$work"
  if [[ -n $started ]]; then fci stop >/dev/null 2>&1 || true; echo "  ..  $vm was off when this began; it is shutting down again"; fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM
work="$(mktemp -d)"
dev="$(ip -o route get 1.1.1.1 | sed -n 's/.* dev \([^ ]*\).*/\1/p')"
mac="$(cat "/sys/class/net/$dev/address")"
vm="$(as_user "set -a; . $home/.config/factory-ci/host.env; echo \$FACTORY_CI_VM")"
gmac="$(as_user "virsh -c qemu:///system domiflist $vm" | awk '$3 == "factory-ci" {print $5}')"
[[ $gmac =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]] || { echo "cannot read $vm's MAC from libvirt" >&2; exit 1; }

echo "== the VM"
if [[ "$(as_user "virsh -c qemu:///system domstate $vm")" != running ]]; then fci start >/dev/null; started=1; fi
for _ in $(seq 60); do fci ssh true 2>/dev/null && break; sleep 3; done
fci ssh true || { echo "the guest does not answer" >&2; exit 1; }
ok "$vm runs and answers (MAC $gmac)"

echo "== 1. the installed rules, live"
tables() { nft list table inet factory_ci && nft list table bridge factory_ci; }
want="$(unshare -n bash -c "nft -f /etc/factory-ci/isolation.nft && $(declare -f tables); tables")"
live="$(tables)"
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
else no "factory-ci verify: $(grep '^  X' "$work/verify.txt" | head -3 | tr '\n' ' ')"; fi
tap="$(as_user "virsh -c qemu:///system domiflist $vm" | awk '$3 == "factory-ci" {print $1}')"
if as_user "virsh -c qemu:///system nwfilter-binding-list" | grep -qE "^ *$tap +factory-ci-egress *$"; then ok "the filter factory-ci-egress is bound to the guest's tap $tap"
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
info="$(as_user "virsh -c qemu:///system dominfo $vm")"
ok "$vm has $(sed -n 's/^CPU(s): *//p' <<<"$info") vCPU and $(( $(sed -n 's/^Max memory: *\([0-9]*\).*/\1/p' <<<"$info") >> 20 )) GiB"

echo "== 4. the uplink $dev ($mac), passively, while the guest works"
tcpdump -l -n -e -i "$dev" "ether host $gmac" >"$work/gmac.txt" 2>/dev/null & pids+=($!)
tcpdump -Q out -l -n -e -i "$dev" "not ether src $mac" >"$work/other.txt" 2>/dev/null & pids+=($!)
tcpdump -l -n -i "$dev" "net 192.168.150.0/24" >"$work/gnet.txt" 2>/dev/null & pids+=($!)
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
from_host="$(runuser -u "$SUDO_USER" -- python3 -I - $targets <"$work/probe.py")"  # stdin: $work is root's
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
fci ssh "'curl -fsS -o /dev/null https://api.nuget.org/v3/index.json; ping -6 -c 2 ff02::1%ci0 >/dev/null 2>&1; sudo networkctl renew ci0; sleep 3; ping -c 1 -W 1 192.168.150.77 >/dev/null 2>&1; true'"
sleep 2
for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done; wait 2>/dev/null || true; pids=()
if [[ ! -s $work/gmac.txt ]]; then ok "no frame to or from the guest's MAC $gmac on $dev"; else no "frames with the guest's MAC on $dev: $(head -2 "$work/gmac.txt")"; fi
if [[ ! -s $work/other.txt ]]; then ok "no frame left $dev with a source MAC other than $mac"; else no "frames left $dev with another source MAC: $(head -2 "$work/other.txt")"; fi
if [[ ! -s $work/gnet.txt ]]; then ok "no packet on $dev to or from 192.168.150.0/24"; else no "packets on $dev with a guest address: $(head -2 "$work/gnet.txt")"; fi

echo "== 5. failure, in network namespaces (test-isolation; nothing live is touched)"
if runuser -u "$SUDO_USER" -- env FCI_RULES=/etc/factory-ci/isolation.nft "$kit/host/test-isolation.sh" >"$work/ns.txt" 2>&1 && grep -q 'isolation: PASS' "$work/ns.txt"; then
  ok "the installed rules pass: $(grep -E '^  ok  (with libvirt|the watch|a file)' "$work/ns.txt" | sed 's/^  ok  //' | tr '\n' ';')"
else no "test-isolation on the installed rules: $(grep '^  X' "$work/ns.txt" | head -3 | tr '\n' ' ')"; fi

[[ $fail == 0 ]] && echo "verify-root: PASS" || echo "verify-root: FAIL"
exit "$fail"
