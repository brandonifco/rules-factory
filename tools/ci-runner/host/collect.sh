#!/bin/bash
# factory-ci-collect -- the two things about a factory-ci host only root can read, and nothing else
# (decision 0081). install-collector.sh installs it root-owned as /usr/local/sbin/factory-ci-collect
# and lets the account that runs factory-ci run it through sudo without a password, so that
# host/verify-live.sh, which judges what it prints, runs unprivileged. It changes nothing.
#
#   factory-ci-collect tables           the live tables inet and bridge factory_ci, then `== file`
#                                       and what /etc/factory-ci/isolation.nft loads into an empty
#                                       network namespace
#   factory-ci-collect capture SECONDS  for SECONDS (1-300), every frame on the uplink to or from a
#                                       libvirt MAC (52:54:00:...) or with an address in
#                                       192.168.150.0/24, then `== other`: every frame leaving the
#                                       uplink with a source MAC other than its own. Headers only.
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
    [[ -n $dev && -e /sys/class/net/$dev/address ]] || { echo "no uplink" >&2; exit 1; }
    mac="$(cat "/sys/class/net/$dev/address")"
    work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
    timeout "$2" tcpdump -l -n -e -i "$dev" \
      '(ether[0:2] = 0x5254 and ether[2] = 0) or (ether[6:2] = 0x5254 and ether[8] = 0) or net 192.168.150.0/24' \
      >"$work/guest" 2>/dev/null &
    timeout "$2" tcpdump -Q out -l -n -e -i "$dev" "not ether src $mac" >"$work/other" 2>/dev/null &
    wait || true
    echo "== uplink $dev $mac"; cat "$work/guest"; echo "== other"; cat "$work/other" ;;
  *) sed -n '2,/^set -euo/{/^set -euo/d;s/^# \{0,1\}//p}' "$0" >&2; exit 2 ;;
esac
