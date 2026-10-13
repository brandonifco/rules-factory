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
#   2001:db8::10), an approved resolver (203.0.113.53) and, with eno2 put into the guest's bridge by
#   mistake, a LAN host (ns l).
#
# with libvirt's NAT (a masquerade, as libvirt writes it). Every probe runs twice: first without
# isolation.nft, where each one that must be refused has to get through (else it proves nothing),
# then with it. Connections opened before the ruleset loads are held open across the load, and
# must carry nothing after it. Then libvirt's NAT is removed and nothing may leave with the guest's
# address. A capture on every outside link counts frames from the guest's MAC, which must be none.
# Exit 0 only when every check holds.
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
# Outside: campus, internet and a resolver in w, a LAN host in l.
$W ip link set lo up; $W ip link set up0 up
$W ip addr add 131.238.112.1/21 dev up0; $W ip addr add 203.0.113.10/32 dev up0; $W ip addr add 203.0.113.53/32 dev up0
$W ip addr add 2001:db8::10/64 dev up0 nodad
$W ip route add 192.168.150.0/24 via 131.238.119.32; $W ip -6 route add fd00:fc::/64 via 2001:db8::32
$L ip link set lo up; $L ip link set lan0 up; $L ip addr add 192.168.150.50/24 dev lan0

cat >"$work/net.py" <<'EOF'
import os, socket, sys, threading, time
def serve(ports, log):
    def echo(c, peer):
        try:
            while (data := c.recv(64)):
                with open(log, "a") as f: f.write(f"data {peer}\n")
                c.sendall(data)
        except OSError:
            pass
        c.close()
    def one(family, port):
        s = socket.socket(family, socket.SOCK_STREAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # a held client may share the port
        if family == socket.AF_INET6: s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        s.bind(("::" if family == socket.AF_INET6 else "0.0.0.0", port)); s.listen()
        while True:
            c, peer = s.accept()
            with open(log, "a") as f: f.write(f"{port} {peer[0]}\n")
            threading.Thread(target=echo, args=(c, peer[0]), daemon=True).start()
    for p in ports:
        for fam in (socket.AF_INET, socket.AF_INET6):
            threading.Thread(target=one, args=(fam, p), daemon=True).start()
    threading.Event().wait()
def talk(s):
    s.sendall(b"x"); s.settimeout(1.5); return s.recv(1) == b"x"
def probe(host, port):
    try:
        with socket.create_connection((host, int(port)), timeout=1.5) as s: print("open" if talk(s) else "closed")
    except OSError:
        print("closed")
def hold(host, port, result, go, sport="0"):
    # Open now (from SPORT, if given) and prove it carries; once `go` exists, see whether it still does.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1.5)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1); s.bind(("0.0.0.0", int(sport)))
        s.connect((host, int(port))); first = talk(s)
    except OSError:
        first = False
    with open(result, "w") as f: f.write("open" if first else "closed")
    while not os.path.exists(go): time.sleep(0.1)
    try: after = talk(s)
    except OSError: after = False
    with open(result, "w") as f: f.write("open" if after else "closed")
def udp(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b"x", (host, int(port)))
cmd = sys.argv[1]
if cmd == "serve": serve([int(p) for p in sys.argv[3:]], sys.argv[2])
elif cmd == "probe": probe(sys.argv[2], sys.argv[3])
elif cmd == "hold": hold(*sys.argv[2:7])
elif cmd == "udp": udp(sys.argv[2], sys.argv[3])
EOF
net() { local ns="$1"; shift; if [[ $ns == h ]]; then python3 -I "$work/net.py" "$@"; else ip netns exec "$ns" python3 -I "$work/net.py" "$@"; fi; }
# In the background, as the job itself (exec), so the trap's kill reaches it.
bgnet() { local ns="$1"; shift; if [[ $ns == h ]]; then exec python3 -I "$work/net.py" "$@"; else exec ip netns exec "$ns" python3 -I "$work/net.py" "$@"; fi; }
bgnet w serve "$work/w.log" 22 53 80 443 2222 &
bgnet l serve "$work/l.log" 443 &
bgnet h serve "$work/host.log" 22 53 443 2222 &
bgnet g serve "$work/g.log" 22 2222 &
sleep 1.5

# from|to|port|expected with isolation.nft|why (from: g the guest, w outside, h the host itself,
# standing in for libvirt's dnsmasq, whose uid the test ruleset names)
checks="
g|203.0.113.10|443|open|the internet on HTTPS
g|203.0.113.10|80|open|the internet on HTTP
g|192.168.150.1|53|open|DNS at the gateway
g|203.0.113.10|22|closed|the internet on another port
g|203.0.113.10|53|closed|DNS anywhere but the gateway
g|131.238.112.1|443|closed|the campus on HTTPS
g|131.238.119.32|22|closed|the host's LAN address
g|131.238.119.32|443|closed|the host's LAN address on HTTPS
g|131.238.119.32|53|closed|DNS at the host's LAN address
g|192.168.150.1|22|closed|the host at the gateway
g|192.168.150.50|443|closed|a LAN host on a physical port in the guest's bridge
g|2001:db8::10|443|closed|the internet over IPv6
g|fd00:fc::1|22|closed|the host over IPv6
w|192.168.150.11|22|closed|the campus opening a connection to the guest
h|203.0.113.53|53|open|dnsmasq asking the approved resolver
h|131.238.112.1|53|closed|dnsmasq asking another resolver (the campus's)
"
# from|to|port|source port|why: connections opened before the ruleset loads, held across the load.
# The campus's comes from port 443, so the guest's replies go to port 443, as HTTPS would.
holds="
g|192.168.150.1|2222|0|the guest's connection to a host service
g|203.0.113.10|2222|0|the guest's connection to the internet on another port
g|131.238.112.1|443|0|the guest's connection to the campus
w|192.168.150.11|2222|443|the campus's connection to the guest
"
ip link set eno2 master virbr-fci  # the mistake the bridge table exists for
fail=0 n=0
run() { # phase
  local from to port want why got
  while IFS='|' read -r from to port want why; do
    [[ -n $from ]] || continue
    got="$(net "$from" probe "$to" "$port")"
    if [[ $1 == bare ]]; then
      [[ $got == open ]] || { echo "  X   probe proves nothing: $why ($to:$port) is $got without isolation"; fail=1; }
    else
      n=$((n + 1))
      if [[ $got == "$want" ]]; then echo "  ok  $why ($to:$port): $got"; else echo "  X   $why ($to:$port): $got, want $want"; fail=1; fi
    fi
  done <<<"$checks"
}
echo "without isolation.nft (each probe must get through):"; run bare
i=0
while IFS='|' read -r from to port sport why; do
  [[ -n $from ]] || continue; i=$((i + 1))
  bgnet "$from" hold "$to" "$port" "$work/hold-$i" "$work/go" "$sport" & sleep 0.3
done <<<"$holds"
sleep 2
for f in "$work"/hold-*; do [[ $(cat "$f") == open ]] || { echo "  X   a held connection did not open without isolation"; fail=1; }; done
[[ $fail == 0 ]] && echo "  ok  all $(grep -c '|' <<<"$checks") probes and $i held connections get through"
: >"$work/w.log"
# FCI_RULES is already rendered; the template gets the test's ranges, resolver and uid (0, the
# user namespace's root, which every process here runs as).
sed -e "s#@BLOCKED@#$(for b in $blocked; do printf ', %s' "$b"; done)#" -e "s#@RESOLVERS@#203.0.113.53#" \
    -e "s#@DNSMASQ_UID@#0#" "${FCI_RULES:-$here/isolation.nft}" | nft -f -
$W tcpdump -Z root -l -n -e -i up0 "ether src $MAC" >"$work/w.pcap.txt" 2>/dev/null &
$L tcpdump -Z root -l -n -e -i lan0 "ether src $MAC" >"$work/l.pcap.txt" 2>/dev/null &
sleep 1
echo "with isolation.nft (blocked: $blocked):"; run isolated
inbound="$(grep -c "^data 131.238.112.1$" "$work/g.log" || true)"
touch "$work/go"; sleep 2.5
if [[ "$(grep -c "^data 131.238.112.1$" "$work/g.log" || true)" == "$inbound" ]]; then
  echo "  ok  nothing more reaches the guest on the campus's connection held across the load"; n=$((n + 1))
else echo "  X   the campus's connection held across the load still delivers data to the guest"; fail=1; fi
i=0
while IFS='|' read -r from to port sport why; do
  [[ -n $from ]] || continue; i=$((i + 1)); n=$((n + 1))
  if [[ $(cat "$work/hold-$i") == closed ]]; then echo "  ok  $why, open before the load, carries nothing after it"
  else echo "  X   $why, open before the load, still carries traffic"; fail=1; fi
done <<<"$holds"
# Broadcast and multicast from the guest, which a bridge floods to every port.
$G ping -6 -c 2 -i 0.2 -W 1 ff02::1%eth0 >/dev/null 2>&1 || true
$G ip neigh flush dev eth0; $G ping -c 1 -W 1 192.168.150.77 >/dev/null 2>&1 || true
if grep -q "^443 131.238.119.32$" "$work/w.log" && ! grep -q "192.168.150" "$work/w.log"; then
  echo "  ok  the internet sees the host's address, never the guest's"; else echo "  X   NAT: the internet saw $(tr '\n' ' ' <"$work/w.log")"; fail=1; fi
# libvirt's NAT gone: not one packet, TCP or UDP, may leave with the guest's address.
$W tcpdump -Z root -l -n -i up0 "ip src net 192.168.150.0/24" >"$work/leak.txt" 2>/dev/null &
sleep 1
nft delete table ip nat_libvirt
got="$(net g probe 203.0.113.10 443)"; net g udp 203.0.113.10 123; net g udp 203.0.113.10 443; sleep 1
if [[ $got == closed && ! -s $work/leak.txt ]]; then echo "  ok  with libvirt's NAT gone, no packet leaves with the guest's address (TCP, UDP)"
else echo "  X   with libvirt's NAT gone: $got, and on the wire: $(head -3 "$work/leak.txt")"; fail=1; fi
sleep 0.5
frames=$(( $(wc -l <"$work/w.pcap.txt") + $(wc -l <"$work/l.pcap.txt") ))
if [[ $frames == 0 ]]; then echo "  ok  no frame from the guest's MAC $MAC on any outside link"
else echo "  X   $frames frame(s) from the guest's MAC outside:"; cat "$work/w.pcap.txt" "$work/l.pcap.txt"; fail=1; fi
[[ $fail == 0 ]] && echo "isolation: PASS ($n probes, NAT, MAC)" || echo "isolation: FAIL"
exit "$fail"
