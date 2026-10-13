#!/bin/bash
# test-isolation.sh [BLOCKED...] -- prove isolation.nft in network namespaces, without root.
# FCI_RULES=/etc/factory-ci/isolation.nft tests the ruleset a host installed instead of the template.
#
# It runs itself in a new user, network and mount namespace (unshare -r), so it needs no
# privilege and touches nothing on the host: no interface, rule or route outside it exists after
# it exits. Inside, it builds the host's shape:
#
#   guest (ns g) --vnet0-- virbr-fci 192.168.150.1 [host] eno1 131.238.119.32/21 --- ns w
#   ns w answers as the campus (131.238.112.1, the gateway), the internet (203.0.113.10,
#   2001:db8::10) and, with eno2 put into the guest's bridge by mistake, a LAN host (ns l).
#
# with libvirt's NAT (a masquerade, as libvirt writes it), and checks every probe twice: first
# without isolation.nft, where each one that must be refused has to get through (else the probe
# proves nothing), then with it. A tcpdump on every outside link counts frames from the guest's
# MAC, which must be none. Exit 0 only when every check holds.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
if [[ ${FCI_ISOLATION_NS:-} != 1 ]]; then
  exec unshare -rnm --propagation private env FCI_ISOLATION_NS=1 "$0" "$@"
fi
blocked="${*:-131.238.0.0/16}"
work="$(mktemp -d)"; trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$work"' EXIT
mount -t tmpfs tmpfs /run && mkdir -p /run/netns
ip netns add g; ip netns add w; ip netns add l
G="ip netns exec g" W="ip netns exec w" L="ip netns exec l"
MAC=52:54:00:fc:01:01

# The host: the guest's bridge, its tap, the uplink, forwarding, and libvirt's NAT.
ip link set lo up
ip link add virbr-fci type bridge && ip link set virbr-fci up
ip addr add 192.168.150.1/24 dev virbr-fci; ip addr add fd00:fc::1/64 dev virbr-fci nodad
ip link add vnet0 type veth peer name eth0 netns g
ip link set vnet0 master virbr-fci up
ip link add eno1 type veth peer name up0 netns w
ip addr add 131.238.119.32/21 dev eno1; ip addr add 2001:db8::32/64 dev eno1 nodad; ip link set eno1 up
ip route add default via 131.238.112.1; ip -6 route add default via 2001:db8::10
ip link add eno2 type veth peer name lan0 netns l; ip link set eno2 up
echo 1 >/proc/sys/net/ipv4/ip_forward; echo 1 >/proc/sys/net/ipv6/conf/all/forwarding
nft -f - <<'EOF'
table ip nat_libvirt {
	chain postrouting { type nat hook postrouting priority srcnat; ip saddr 192.168.150.0/24 ip daddr != 192.168.150.0/24 masquerade; }
}
EOF
# The guest.
$G ip link set lo up; $G ip link set eth0 address $MAC up
$G ip addr add 192.168.150.11/24 dev eth0; $G ip addr add fd00:fc::11/64 dev eth0 nodad
$G ip route add default via 192.168.150.1; $G ip -6 route add default via fd00:fc::1
# Outside: campus and internet in w, a LAN host in l.
$W ip link set lo up; $W ip link set up0 up
$W ip addr add 131.238.112.1/21 dev up0; $W ip addr add 203.0.113.10/32 dev up0; $W ip addr add 2001:db8::10/64 dev up0 nodad
$W ip route add 192.168.150.0/24 via 131.238.119.32; $W ip -6 route add fd00:fc::/64 via 2001:db8::32
$L ip link set lo up; $L ip link set lan0 up; $L ip addr add 192.168.150.50/24 dev lan0

cat >"$work/net.py" <<'EOF'
import socket, sys, threading
def serve(ports, log):
    def one(family, port):
        s = socket.socket(family, socket.SOCK_STREAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if family == socket.AF_INET6: s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        s.bind(("::" if family == socket.AF_INET6 else "0.0.0.0", port)); s.listen()
        while True:
            c, peer = s.accept()
            with open(log, "a") as f: f.write(f"{port} {peer[0]}\n")
            c.close()
    for p in ports:
        for fam in (socket.AF_INET, socket.AF_INET6):
            threading.Thread(target=one, args=(fam, p), daemon=True).start()
    threading.Event().wait()
def probe(host, port):
    try:
        socket.create_connection((host, int(port)), timeout=1.5).close(); print("open")
    except OSError:
        print("closed")
if sys.argv[1] == "serve": serve([int(p) for p in sys.argv[3:]], sys.argv[2])
else: probe(sys.argv[2], sys.argv[3])
EOF
$W python3 -I "$work/net.py" serve "$work/w.log" 22 53 80 443 &
$L python3 -I "$work/net.py" serve "$work/l.log" 443 &
python3 -I "$work/net.py" serve "$work/host.log" 22 53 443 &
$G python3 -I "$work/net.py" serve "$work/g.log" 22 &
sleep 1.5

# from|to|port|expected with isolation.nft (the guest's own, or an outsider's)
checks="
g|203.0.113.10|443|open|the internet on HTTPS
g|203.0.113.10|80|open|the internet on HTTP
g|192.168.150.1|53|open|DNS at the gateway
g|203.0.113.10|22|closed|the internet on another port
g|203.0.113.10|53|closed|DNS anywhere but the gateway
g|131.238.112.1|443|closed|the campus on HTTPS
g|131.238.119.32|22|closed|the host's LAN address
g|131.238.119.32|443|closed|the host's LAN address on HTTPS
g|192.168.150.1|22|closed|the host at the gateway
g|192.168.150.50|443|closed|a LAN host on a physical port in the guest's bridge
g|2001:db8::10|443|closed|the internet over IPv6
g|fd00:fc::1|22|closed|the host over IPv6
w|192.168.150.11|22|closed|the campus opening a connection to the guest
"
ip link set eno2 master virbr-fci  # the mistake the bridge table exists for
fail=0 n=0
run() { # phase
  local from to port want why got
  while IFS='|' read -r from to port want why; do
    [[ -n $from ]] || continue
    got="$(ip netns exec "$from" python3 -I "$work/net.py" probe "$to" "$port")"
    if [[ $1 == bare ]]; then
      # Without the table, every probe must connect, or it cannot show the table refusing it.
      [[ $got == open ]] || { echo "  X   probe proves nothing: $why ($to:$port) is $got without isolation"; fail=1; }
    else
      n=$((n + 1))
      if [[ $got == "$want" ]]; then echo "  ok  $why ($to:$port): $got"; else echo "  X   $why ($to:$port): $got, want $want"; fail=1; fi
    fi
  done <<<"$checks"
}
echo "without isolation.nft (each probe must get through):"; run bare
[[ $fail == 0 ]] && echo "  ok  all $(grep -c '|' <<<"$checks") probes connect"
: >"$work/w.log"
sed "s#@BLOCKED@#$(for b in $blocked; do printf ', %s' "$b"; done)#" "${FCI_RULES:-$here/isolation.nft}" | nft -f -
$W tcpdump -Z root -l -n -e -i up0 "ether src $MAC" >"$work/w.pcap.txt" 2>/dev/null &
$L tcpdump -Z root -l -n -e -i lan0 "ether src $MAC" >"$work/l.pcap.txt" 2>/dev/null &
sleep 1
echo "with isolation.nft (blocked: $blocked):"; run isolated
# Broadcast and multicast from the guest, which a bridge floods to every port.
$G ping -6 -c 2 -i 0.2 -W 1 ff02::1%eth0 >/dev/null 2>&1 || true
$G ip neigh flush dev eth0; $G ping -c 1 -W 1 192.168.150.77 >/dev/null 2>&1 || true
if grep -q "^443 131.238.119.32$" "$work/w.log" && ! grep -q "192.168.150" "$work/w.log"; then
  echo "  ok  the internet sees the host's address, never the guest's"; else echo "  X   NAT: the internet saw $(tr '\n' ' ' <"$work/w.log")"; fail=1; fi
nft delete table ip nat_libvirt
[[ "$($G python3 -I "$work/net.py" probe 203.0.113.10 443)" == closed ]] &&
  ! grep -q "192.168.150" "$work/w.log" &&
  echo "  ok  with libvirt's NAT gone, nothing leaves with the guest's address" ||
  { echo "  X   with libvirt's NAT gone, the guest still got out"; fail=1; }
sleep 0.5
frames=$(( $(wc -l <"$work/w.pcap.txt") + $(wc -l <"$work/l.pcap.txt") ))
if [[ $frames == 0 ]]; then echo "  ok  no frame from the guest's MAC $MAC on any outside link"
else echo "  X   $frames frame(s) from the guest's MAC outside:"; cat "$work/w.pcap.txt" "$work/l.pcap.txt"; fail=1; fi
[[ $fail == 0 ]] && echo "isolation: PASS ($n probes, NAT, MAC)" || echo "isolation: FAIL"
exit "$fail"
