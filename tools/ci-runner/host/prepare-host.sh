#!/bin/bash
# prepare-host.sh -- make an Ubuntu 24.04 machine a factory-ci KVM host, isolation first (decision
# 0081). Run with sudo by the account that runs `factory-ci`; nothing after it needs sudo.
# Idempotent: a second run, or a run after a failed one, does each step again from what it finds.
#
#   sudo prepare-host.sh --dns IP... [--block CIDR]... [--cpu N] [--memory-max SIZE]
#                        [--io-bandwidth BYTES] [--io-iops N] [--dry-run]
#   sudo prepare-host.sh --remove
#
# --dry-run prints every privileged step and changes nothing. A run refuses while any VM runs (a
# connection a VM already holds would outlive a tightened ruleset), and in order:
#   1. refuses a host where a bridge holds a physical port, or a macvtap/macvlan/ipvlan exists:
#      a guest MAC must never reach a physical link;
#   2. installs libvirt, virt-install, qemu and xorriso with every service start held back
#      (policy-rc.d), so nothing runs before step 4;
#   3. removes the autostart of libvirt's stock `default` network and stops it if it runs; on any
#      failure from step 2 on, an exit trap still removes that autostart;
#   4. installs /etc/factory-ci/isolation.nft (host/isolation.nft: the host's own IPv4 networks and
#      each --block added to `blocked`, the --dns resolvers, libvirt-dnsmasq's uid), the unit
#      factory-ci-isolation that loads it, a drop-in by which libvirtd Requires it, and the watch
#      (host/isolation-watch.sh, every 10 s by a timer) that reloads it or takes the guest's network
#      down. It owns its two nftables tables and never flushes anything else;
#   5. turns IPv4 forwarding off when no libvirt NAT network runs;
#   6. puts the account in the libvirt group and makes the `default` storage pool;
#   7. caps machine.slice, where every VM runs: CPU weight 50 (the user's work wins under
#      contention) and hard limits when given: --cpu N (N CPUs' time), --memory-max (MemoryHigh 1G
#      under it), --io-bandwidth and --io-iops on the disk holding the VM images.
# --remove undoes 4 and 7, and refuses unless it can show that no VM runs. Packages, the group and
# the pool stay (apt remove, gpasswd -d, virsh pool-undefine).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dry= remove= block=() dns=() cpu= memmax= iobw= ioiops=
while (( $# )); do
  case "$1" in
    --dry-run) dry=1 ;;
    --remove) remove=1 ;;
    --block) block+=("${2:?}"); shift ;;
    --dns) dns+=("${2:?}"); shift ;;
    --cpu) cpu="${2:?}"; shift ;;
    --memory-max) memmax="${2:?}"; shift ;;
    --io-bandwidth) iobw="${2:?}"; shift ;;
    --io-iops) ioiops="${2:?}"; shift ;;
    *) sed -n '2,/^set -euo/{/^set -euo/d;s/^# \{0,1\}//p}' "$0" >&2; exit 2 ;;
  esac
  shift
done
for b in "${block[@]}"; do
  [[ $b =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]] || { echo "not an IPv4 CIDR: $b" >&2; exit 2; }
done
[[ -z $cpu || $cpu =~ ^[1-9][0-9]?$ ]] || { echo "--cpu is a number of CPUs" >&2; exit 2; }
[[ -z $memmax || $memmax =~ ^[1-9][0-9]*G$ ]] || { echo "--memory-max is whole GiB, e.g. 10G" >&2; exit 2; }
[[ -z $iobw || $iobw =~ ^[1-9][0-9]*[KMG]$ ]] || { echo "--io-bandwidth is e.g. 500M (bytes per second)" >&2; exit 2; }
[[ -z $ioiops || $ioiops =~ ^[1-9][0-9]*$ ]] || { echo "--io-iops is a number" >&2; exit 2; }
[[ -n $dry || ( $(id -u) == 0 && -n ${SUDO_USER:-} && ${SUDO_USER:-} != root ) ]] ||
  { echo "run with sudo, as the account that runs factory-ci (or --dry-run)" >&2; exit 2; }
user="${SUDO_USER:-$USER}"
step() { echo "+ $*"; }
do_() { step "$*"; [[ -n $dry ]] || "$@"; }
virsh_() { do_ virsh -c qemu:///system "$@"; }
rules=/etc/factory-ci/isolation.nft watch=/usr/local/sbin/factory-ci-isolation-watch
unit=/etc/systemd/system/factory-ci-isolation.service
wunit=/etc/systemd/system/factory-ci-isolation-watch.service wtimer=/etc/systemd/system/factory-ci-isolation-watch.timer
dropin=/etc/systemd/system/libvirtd.service.d/10-factory-ci-isolation.conf
autostart=/etc/libvirt/qemu/networks/autostart/default.xml

no_vm() { # fail unless it is certain that no VM runs: libvirt answers, and no qemu or tap exists
  local listed
  if command -v virsh >/dev/null; then
    listed="$(virsh -c qemu:///system list --name 2>&1)" || { echo "cannot ask libvirt which VMs run: $listed" >&2; return 1; }
    [[ -z ${listed//[[:space:]]/} ]] || { echo "VM(s) running: $listed" >&2; return 1; }
  fi
  if pgrep -x 'qemu-system-x86_64' >/dev/null; then echo "a qemu process runs" >&2; return 1; fi
  if ls /sys/class/net | grep -q '^vnet'; then echo "a VM tap (vnet*) exists" >&2; return 1; fi
  return 0
}

if [[ -n $remove ]]; then
  no_vm || { echo "refusing: a VM must never outlive its isolation (factory-ci stop first)" >&2; exit 1; }
  do_ systemctl disable --now factory-ci-isolation-watch.timer factory-ci-isolation.service || true
  no_vm || { echo "refusing: a VM appeared" >&2; exit 1; }
  do_ rm -f "$unit" "$wunit" "$wtimer" "$dropin" "$rules" "$watch"
  do_ nft delete table inet factory_ci 2>/dev/null || true
  do_ nft delete table bridge factory_ci 2>/dev/null || true
  for p in CPUWeight CPUQuota MemoryHigh MemoryMax IOReadBandwidthMax IOWriteBandwidthMax IOReadIOPSMax IOWriteIOPSMax; do
    do_ rm -f "/etc/systemd/system.control/machine.slice.d/50-$p.conf"
  done
  do_ systemctl daemon-reload
  echo "factory-ci host isolation and slice limits removed; libvirt itself stays"
  exit 0
fi

(( ${#dns[@]} )) || { echo "--dns is required: the resolvers the guest's DNS goes to, never the host's own" >&2; exit 2; }
mapfile -t hostnets < <(ip -4 -o addr show scope global | awk '$2 !~ /^virbr/ {print $4}')
# Every resolver a global unicast IPv4 address, outside every blocked and host network.
python3 -I - "${dns[@]}" -- "${block[@]}" "${hostnets[@]}" <<'EOF' || exit 2
import ipaddress, sys
args = sys.argv[1:]; cut = args.index("--")
resolvers, nets = args[:cut], [ipaddress.ip_network(n, strict=False) for n in args[cut + 1:]]
for r in resolvers:
    try:
        a = ipaddress.ip_address(r)
    except ValueError:
        sys.exit(f"--dns {r}: not an IP address")
    if a.version != 4 or not a.is_global or any(a in n for n in nets):
        sys.exit(f"--dns {r}: a resolver must be a public IPv4 address outside the blocked and host networks")
EOF
[[ -n $dry ]] || no_vm || { echo "refusing while a VM runs: shut it down (factory-ci stop), then run this again" >&2; exit 1; }

echo "== 1. physical network"
for port in /sys/class/net/*/brif/*; do
  [[ -e $port ]] || continue
  [[ -e /sys/class/net/${port##*/}/device ]] && { echo "a bridge holds the physical port ${port##*/}: refusing" >&2; exit 1; }
done
links="$(ip -d -o link)"  # read whole first: grep -q under pipefail would read a match as none
if grep -qE ' (macvtap|macvlan|ipvlan) ' <<<"$links"; then echo "a macvtap/macvlan/ipvlan link exists: refusing" >&2; exit 1; fi
grep -qE '(vmx|svm)' /proc/cpuinfo && [[ -c /dev/kvm ]] || { echo "no hardware virtualization (/dev/kvm)" >&2; exit 1; }
command -v nft >/dev/null || { echo "nft is missing (apt install nftables)" >&2; exit 1; }
echo "  no bridge holds a physical port; no macvtap, macvlan or ipvlan"

echo "== 2. packages, with every service start held back"
policy=/usr/sbin/policy-rc.d held=
finish() { # on any exit: the default network never autostarts, and our hold on services goes
  [[ -n $dry ]] && return 0
  rm -f "$autostart"
  [[ -z $held ]] || rm -f "$policy"
  return 0
}
trap finish EXIT
if [[ ! -e $policy ]]; then
  step "write $policy (exit 101: no service starts during the install), removed on exit"
  [[ -n $dry ]] || { printf '#!/bin/sh\nexit 101\n' >"$policy"; chmod 0755 "$policy"; held=1; }
else echo "  $policy exists already and is left as it is"; fi
export DEBIAN_FRONTEND=noninteractive
do_ apt-get install -y -q --no-install-recommends libvirt-daemon-system libvirt-clients virtinst qemu-system-x86 qemu-utils xorriso
if [[ -n $held ]]; then rm -f "$policy"; held=; fi

echo "== 3. libvirt's default network"
do_ rm -f "$autostart"
if info="$(virsh -c qemu:///system net-info default 2>/dev/null)" && [[ $info =~ Active:\ *yes ]]; then virsh_ net-destroy default; fi

echo "== 4. isolation (tables inet and bridge factory_ci) and its watch"
uid="$(id -u libvirt-dnsmasq 2>/dev/null || true)"
if [[ ! $uid =~ ^[0-9]+$ ]]; then
  [[ -n $dry ]] || { echo "no libvirt-dnsmasq user after the install" >&2; exit 1; }
  uid=0
fi
extra="$(for b in "${hostnets[@]}" "${block[@]}"; do printf ', %s' "$b"; done)"
resolvers="$(printf '%s, ' "${dns[@]}")"; resolvers="${resolvers%, }"
rendered="$(sed -e "s#@BLOCKED@#$extra#" -e "s#@RESOLVERS@#$resolvers#" -e "s#@DNSMASQ_UID@#$uid#" "$here/isolation.nft")"
check=(nft -c -f -); [[ $(id -u) == 0 ]] || check=(unshare -rn nft -c -f -)  # a dry run as the user
"${check[@]}" <<<"$rendered" || { echo "isolation.nft does not parse" >&2; exit 1; }
step "write $rules (blocked besides the private ranges: ${extra#, }; resolvers: $resolvers; dnsmasq uid $uid)"
step "write $watch, $unit, $wunit, $wtimer (every 10 s) and $dropin (libvirtd Requires= and After= the isolation)"
if [[ -z $dry ]]; then
  install -d -m 0755 /etc/factory-ci "${dropin%/*}"
  printf '%s\n' "$rendered" >"$rules.tmp"; chmod 0644 "$rules.tmp"; mv -f "$rules.tmp" "$rules"
  install -m 0755 "$here/isolation-watch.sh" "$watch"
  cat >"$unit" <<EOF
# factory-ci host isolation (rules-factory decision 0081). Written by prepare-host.sh.
[Unit]
Description=factory-ci host isolation (nftables tables inet/bridge factory_ci)
DefaultDependencies=no
After=local-fs.target nftables.service ufw.service firewalld.service
Before=libvirtd.service libvirt-guests.service network-pre.target
Wants=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f $rules
ExecStartPost=$watch

[Install]
WantedBy=multi-user.target
EOF
  printf '%s\n' "[Unit]" "Description=factory-ci: reload the host isolation, or take the guest's network down" \
    "[Service]" "Type=oneshot" "ExecStart=$watch" >"$wunit"
  printf '%s\n' "[Unit]" "Description=factory-ci: check the host isolation every 10 seconds" \
    "[Timer]" "OnActiveSec=10s" "OnUnitActiveSec=10s" "AccuracySec=1s" "[Install]" "WantedBy=timers.target" >"$wtimer"
  printf '%s\n' "# rules-factory decision 0081: no VM starts without the host's isolation." \
    "[Unit]" "Requires=factory-ci-isolation.service" "After=factory-ci-isolation.service" >"$dropin"
fi
do_ systemctl daemon-reload
do_ systemctl enable factory-ci-isolation.service factory-ci-isolation-watch.timer
do_ systemctl restart factory-ci-isolation.service
do_ systemctl start factory-ci-isolation-watch.timer

echo "== 5. forwarding"
nat=
for n in $(virsh -c qemu:///system net-list --name 2>/dev/null); do
  [[ $n == default ]] && continue
  [[ "$(virsh -c qemu:///system net-dumpxml "$n")" =~ \<forward\ mode=.(nat|route) ]] && nat="$nat $n"
done
if [[ -z $nat ]]; then do_ sysctl -q -w net.ipv4.ip_forward=0
else echo "  forwarding stays on for the running NAT network(s):$nat (ufw's forward policy and isolation.nft still apply)"; fi

echo "== 6. group and pool"
do_ usermod -aG libvirt "$user"
pool="$(virsh -c qemu:///system pool-info default 2>/dev/null)" || { virsh_ pool-define-as default dir --target /var/lib/libvirt/images; pool=; }
virsh_ pool-autostart default
[[ $pool =~ State:\ *running ]] || virsh_ pool-start default
do_ systemctl enable libvirt-guests.service

echo "== 7. machine.slice"
props=(CPUWeight=50)
[[ -z $cpu ]] || props+=("CPUQuota=$((cpu * 100))%")
[[ -z $memmax ]] || props+=("MemoryHigh=$(( ${memmax%G} - 1 ))G" "MemoryMax=$memmax")
images=/var/lib/libvirt/images
[[ -z $iobw ]] || props+=("IOReadBandwidthMax=$images $iobw" "IOWriteBandwidthMax=$images $iobw")
[[ -z $ioiops ]] || props+=("IOReadIOPSMax=$images $ioiops" "IOWriteIOPSMax=$images $ioiops")
do_ systemctl set-property machine.slice "${props[@]}"

echo "== done"
[[ -z $dry ]] || { echo "dry run: nothing was changed"; exit 0; }
systemctl is-active --quiet factory-ci-isolation.service || { echo "factory-ci-isolation is not active" >&2; exit 1; }
read -r state _ </run/factory-ci-isolation/status
[[ $state == loaded || $state == reloaded ]] || { echo "the isolation watch says: $state" >&2; exit 1; }
systemctl show machine.slice -p CPUWeight -p CPUQuotaPerSecUSec -p MemoryHigh -p MemoryMax -p IOReadBandwidthMax \
  -p IOWriteBandwidthMax -p IOReadIOPSMax -p IOWriteIOPSMax | sed 's/^/  /'
echo "factory-ci host ready; isolation $state; $user is in the libvirt group from its next login (until then: sg libvirt -c ...)"
