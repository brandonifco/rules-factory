#!/bin/bash
# verify-root.sh -- the host-level checks of decision 0081 that only root can make. Run with sudo by
# the account that runs `factory-ci`, on a prepared host with its VM provisioned. It starts the VM
# if it is off, makes guest traffic with `factory-ci verify` and a few commands of its own, and:
#   1. the live tables are the installed file's (the watch's own comparison);
#   2. not one frame leaves the uplink with a source MAC other than the uplink's own, and not one
#      packet leaves with a guest address, while the guest makes traffic, DHCP, ARP and IPv6
#      multicast included;
#   3. a listener on the bridge address: the host reaches it, the guest does not;
#   4. the watch: a deleted table is back within 15 seconds;
#   5. NAT failure: with libvirt's masquerade for the guest's network removed, the guest gets
#      nothing out and nothing leaves with its address; restarting libvirtd puts libvirt's rules
#      back (running guests keep running), and the guest gets out again.
# It changes nothing that outlives it. Exit 0 only when every check holds.
set -euo pipefail
kit="$(cd "$(dirname "$0")/.." && pwd)"
[[ $(id -u) == 0 && -n ${SUDO_USER:-} && $SUDO_USER != root ]] || { echo "run with sudo, as the account that runs factory-ci" >&2; exit 2; }
home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
as_user() { runuser -u "$SUDO_USER" -- env HOME="$home" sg libvirt -c "$*"; }
fci() { as_user "$kit/factory-ci $*"; }
fail=0
ok() { echo "  ok  $*"; }; no() { echo "  X   $*"; fail=1; }
work="$(mktemp -d)"; trap 'kill $(jobs -p) 2>/dev/null; wait 2>/dev/null; rm -rf "$work"' EXIT
dev="$(ip -o route get 1.1.1.1 | sed -n 's/.* dev \([^ ]*\).*/\1/p')"
mac="$(cat "/sys/class/net/$dev/address")"
vm="$(as_user "set -a; . $home/.config/factory-ci/host.env; echo \$FACTORY_CI_VM")"

echo "== the VM"
if [[ "$(as_user "virsh -c qemu:///system domstate $vm")" != running ]]; then fci start >/dev/null; fi
for _ in $(seq 60); do fci ssh true 2>/dev/null && break; sleep 3; done
fci ssh true || { echo "the guest does not answer" >&2; exit 1; }
ok "$vm runs and answers"

echo "== 1. the live tables"
/usr/local/sbin/factory-ci-isolation-watch && read -r state _ </run/factory-ci-isolation/status
if [[ ${state:-} == loaded ]]; then ok "inet and bridge factory_ci equal /etc/factory-ci/isolation.nft"; else no "the watch says ${state:-nothing}"; fi

echo "== 2. the uplink $dev ($mac) while the guest makes traffic"
tcpdump -Q out -l -n -e -i "$dev" "not ether src $mac" >"$work/mac.txt" 2>/dev/null &
tcpdump -Q out -l -n -i "$dev" "ip src net 192.168.150.0/24" >"$work/ip.txt" 2>/dev/null &
sleep 2
fci verify >"$work/verify.txt" 2>&1 || true
fci ssh "'curl -fsS -o /dev/null https://api.nuget.org/v3/index.json; ping -6 -c 2 ff02::1%ci0 >/dev/null 2>&1; sudo networkctl renew ci0; sleep 3; ping -c 1 -W 1 192.168.150.77 >/dev/null 2>&1; true'"
sleep 2
if grep -q '^verify: PASS' "$work/verify.txt"; then ok "factory-ci verify passes ($(grep -c '^  ok' "$work/verify.txt") checks)"; else no "factory-ci verify: $(grep '^  X' "$work/verify.txt" | head -3)"; fi
if [[ ! -s $work/mac.txt ]]; then ok "no frame left $dev with a source MAC other than $mac"; else no "frames left $dev with another source MAC: $(head -3 "$work/mac.txt")"; fi
if [[ ! -s $work/ip.txt ]]; then ok "no packet left $dev with a guest address"; else no "packets left $dev with a guest address: $(head -3 "$work/ip.txt")"; fi

echo "== 3. a listener on the bridge address"
python3 -I -c "import socket,time;s=socket.socket();s.bind(('192.168.150.1',18443));s.listen();time.sleep(15)" &
sleep 1
probe="import socket
try: socket.create_connection(('192.168.150.1',18443),3).close(); print('open')
except OSError: print('closed')"
host="$(python3 -I -c "$probe")"; guest="$(fci ssh python3 -I - <<<"$probe")"
if [[ $host == open && $guest == closed ]]; then ok "the host reaches 192.168.150.1:18443, the guest does not"
else no "192.168.150.1:18443: host $host (want open), guest $guest (want closed)"; fi

echo "== 4. the watch"
nft delete table inet factory_ci
for i in $(seq 15); do sleep 1; nft list table inet factory_ci >/dev/null 2>&1 && break; done
read -r state _ </run/factory-ci-isolation/status
if nft list table inet factory_ci >/dev/null 2>&1 && [[ $state == reloaded ]]; then ok "a deleted table was back after ${i}s (watch: $state)"
else /usr/local/sbin/factory-ci-isolation-watch || true; no "a deleted table was not back within 15s (watch: $state; reloaded now)"; fi

echo "== 5. libvirt's NAT removed"
: >"$work/ip.txt"
mapfile -t masq < <(iptables -t nat -S | grep -E '^-A .*-s 192\.168\.150\.0/24.*MASQUERADE' || true)
if (( ${#masq[@]} )); then
  for r in "${masq[@]}"; do eval "iptables -t nat ${r/-A /-D }"; done
  out="$(fci ssh "'curl -fsS -m 5 -o /dev/null https://api.nuget.org/v3/index.json && echo out || echo none'")"; sleep 1
  if [[ $out == none && ! -s $work/ip.txt ]]; then ok "without NAT the guest got nothing out, and nothing left with its address"
  else no "without NAT: guest $out, on the wire $(head -2 "$work/ip.txt")"; fi
  systemctl restart libvirtd; sleep 3
  if [[ "$(iptables -t nat -S | grep -cE '192\.168\.150\.0/24.*MASQUERADE')" -ge 1 ]] &&
     [[ "$(fci ssh "'curl -fsS -m 10 -o /dev/null https://api.nuget.org/v3/index.json && echo out'")" == out ]]; then
    ok "restarting libvirtd put NAT back, and the guest gets out again"
  else no "NAT is not back: virsh net-destroy factory-ci && virsh net-start factory-ci, then factory-ci restart"; fi
else no "found no masquerade rule for 192.168.150.0/24 in iptables' nat table"; fi

[[ $fail == 0 ]] && echo "verify-root: PASS" || echo "verify-root: FAIL"
exit "$fail"
