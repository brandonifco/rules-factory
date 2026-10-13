#!/bin/bash
# factory-ci-collect -- the two things about a factory-ci host only root can read, and nothing else
# (decision 0081). install-collector.sh installs it root-owned as /usr/local/sbin/factory-ci-collect
# and lets the account that runs factory-ci run it through sudo without a password, so that
# host/verify-live.sh, which judges what it prints, runs unprivileged. It changes nothing.
#
#   factory-ci-collect tables           the live tables inet and bridge factory_ci, then `== file`
#                                       and what /etc/factory-ci/isolation.nft loads into an empty
#                                       network namespace
#   factory-ci-collect capture SECONDS  for SECONDS (1-300), after `== uplink DEV MAC FRAMES`, every
#                                       frame on the uplink to or from a libvirt MAC (52:54:00:...)
#                                       or with an IPv4 or ARP address in 192.168.150.0/24, then
#                                       `== other`: every frame leaving it with a source MAC other
#                                       than its own. Addresses only, never a payload.
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
tables() { nft list table inet factory_ci && nft list table bridge factory_ci; }
case "${1:-}" in
  tables)
    (( $# == 1 )) || exit 2
    tables; echo "== file"
    unshare -n bash -c "nft -f /etc/factory-ci/isolation.nft && $(declare -f tables); tables" ;;
  capture)
    (( $# == 2 )) && [[ $2 =~ ^[1-9][0-9]{0,2}$ ]] && (( $2 <= 300 )) || { echo "capture SECONDS, 1-300" >&2; exit 2; }
    dev="$(ip -o route get 1.1.1.1 | sed -n 's/.* dev \([^ ]*\).*/\1/p')"
    mac="$(ip -o link show "$dev" | grep -oE 'link/ether ([0-9a-f]{2}:){5}[0-9a-f]{2}' | cut -d' ' -f2)"  # netlink, not /sys
    [[ -n $dev && -n $mac ]] || { echo "no uplink" >&2; exit 1; }
    # A raw socket that stops on its own clock. Not tcpdump: Ubuntu's AppArmor profile for tcpdump
    # refuses signals from any peer but `unconfined`, so a tcpdump started from a confined session
    # (Claude Desktop's, on Office) could not be stopped by timeout or by this script, root or not.
    python3 -I - "$dev" "$mac" "$2" <<'EOF'
import ipaddress, select, socket, struct, sys, time
dev, mac, seconds = sys.argv[1], bytes.fromhex(sys.argv[2].replace(":", "")), int(sys.argv[3])
guest_net, libvirt = ipaddress.ip_network("192.168.150.0/24"), b"\x52\x54\x00"
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))  # ETH_P_ALL
s.bind((dev, 0))
end, frames, guest, other = time.monotonic() + seconds, 0, [], []
def text(m): return ":".join(f"{b:02x}" for b in m)
while (left := end - time.monotonic()) > 0:
    if not select.select([s], [], [], min(left, 1.0))[0]:
        continue
    data, (_, _, pkttype, _, _) = s.recvfrom(65535)
    if len(data) < 14:
        continue
    frames += 1
    dst, src, kind = data[0:6], data[6:12], struct.unpack("!H", data[12:14])[0]
    addrs = []
    if kind == 0x0800 and len(data) >= 34:
        addrs = [data[26:30], data[30:34]]
    elif kind == 0x0806 and len(data) >= 42:
        addrs = [data[28:32], data[38:42]]
    line = f"{'out' if pkttype == socket.PACKET_OUTGOING else 'in'} {text(src)} > {text(dst)} type 0x{kind:04x} " + \
        " > ".join(str(ipaddress.ip_address(a)) for a in addrs)
    if src[:3] == libvirt or dst[:3] == libvirt or any(ipaddress.ip_address(a) in guest_net for a in addrs):
        guest.append(line)
    if pkttype == socket.PACKET_OUTGOING and src != mac:
        other.append(line)
print(f"== uplink {dev} {sys.argv[2]} {frames}")
print("\n".join(guest[:50]) + ("\n" if guest else ""), end="")
print("== other")
print("\n".join(other[:50]) + ("\n" if other else ""), end="")
EOF
    ;;
  *) sed -n '2,/^set -euo/{/^set -euo/d;s/^# \{0,1\}//p}' "$0" >&2; exit 2 ;;
esac
