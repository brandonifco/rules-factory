#!/bin/bash
# isolation-watch -- keep the host's isolation (decision 0081) loaded, or take the guest off the
# network. Run as root when factory-ci-isolation starts and every 10 seconds by its timer; installed
# by prepare-host.sh as /usr/local/sbin/factory-ci-isolation-watch.
#
# A unit that ran `nft -f` once stays "active" whatever happens to the tables after it: another
# firewall loader's `flush ruleset`, or a hand that deletes one. So this compares the live tables
# with what /etc/factory-ci/isolation.nft gives when loaded into an empty network namespace, and
#   * equal: records `loaded`;
#   * different or missing: loads the file again and records `reloaded` if that makes them equal;
#   * still different: records `failed`, takes the guest's bridge down and stops libvirt's network,
#     so the guest has no network at all, and exits 1.
# The record, /run/factory-ci-isolation/status ("STATE EPOCH"), is what `factory-ci` reads, unprivileged,
# before it provisions or starts the VM, and what `factory-ci verify` reports.
set -uo pipefail
rules=/etc/factory-ci/isolation.nft dir=/run/factory-ci-isolation
tables() { nft list table inet factory_ci 2>/dev/null && nft list table bridge factory_ci 2>/dev/null; }
want="$(unshare -n bash -c "nft -f '$rules' && $(declare -f tables); tables" 2>/dev/null)"
if [[ -n $want && "$(tables)" == "$want" ]]; then
  state=loaded
elif [[ -n $want ]] && nft -f "$rules" && [[ "$(tables)" == "$want" ]]; then
  state=reloaded; logger -t factory-ci -p warning "isolation: the live tables differed from $rules; reloaded"
else
  state=failed; logger -t factory-ci -p err "isolation: cannot load $rules; the guest's network is taken down"
  ip link set virbr-fci down 2>/dev/null
  virsh -c qemu:///system net-destroy factory-ci >/dev/null 2>&1
fi
install -d -m 0755 "$dir"
printf '%s %s\n' "$state" "$(date +%s)" >"$dir/.status"; chmod 0644 "$dir/.status"; mv -f "$dir/.status" "$dir/status"
[[ $state != failed ]]
