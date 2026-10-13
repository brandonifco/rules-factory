#!/bin/bash
# prepare-host.sh -- make an Ubuntu 24.04 machine a factory-ci KVM host, isolation first. Run with
# sudo by the account that runs `factory-ci`; nothing after it needs sudo. Idempotent: a second
# run, or a run after a failed one, does each step again from the state it finds.
#
#   sudo prepare-host.sh [--dry-run] [--block CIDR]... [--cpu N] [--memory-max SIZE]
#                        [--io-bandwidth BYTES] [--io-iops N]
#   sudo prepare-host.sh --remove
#
# --dry-run prints every privileged step and changes nothing. In order, a run:
#   1. refuses a host where any bridge holds a physical port, or a macvtap/macvlan/ipvlan exists:
#      the guest's MAC must never reach a physical link;
#   2. installs and loads /etc/factory-ci/isolation.nft (host/isolation.nft, with --block added),
#      its own nftables tables, never flushing anything else, through the unit
#      factory-ci-isolation, and makes libvirtd require that unit: no VM starts without it;
#   3. installs libvirt, virt-install, qemu and xorriso;
#   4. turns libvirt's stock `default` network off and stops it autostarting (no VM uses it), and
#      turns IPv4 forwarding back off when no libvirt NAT network is running;
#   5. puts the account in the libvirt group and makes the `default` storage pool;
#   6. caps machine.slice, where every VM runs: CPU weight 50 (the user's work wins under
#      contention), and hard limits when given: --cpu N (N CPUs' time), --memory-max (and
#      MemoryHigh 1G under it), --io-bandwidth and --io-iops on the disk holding the VM's images.
# --remove undoes 2 and 6. It refuses while a VM runs, because a running VM must never outlive its
# isolation. Packages, the group and the pool stay (apt remove, gpasswd -d, virsh pool-undefine).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dry= remove= block=() cpu= memmax= iobw= ioiops=
while (( $# )); do
  case "$1" in
    --dry-run) dry=1 ;;
    --remove) remove=1 ;;
    --block) block+=("${2:?}"); shift ;;
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
unit=/etc/systemd/system/factory-ci-isolation.service
dropin=/etc/systemd/system/libvirtd.service.d/10-factory-ci-isolation.conf
rules=/etc/factory-ci/isolation.nft

if [[ -n $remove ]]; then
  if command -v virsh >/dev/null && [[ -n "$(virsh -c qemu:///system list --name 2>/dev/null | grep .)" ]]; then
    echo "a VM is running; shut it down first (factory-ci stop): it must never outlive its isolation" >&2; exit 1
  fi
  do_ systemctl disable --now factory-ci-isolation.service || true
  do_ rm -f "$unit" "$dropin" "$rules"
  do_ nft delete table inet factory_ci 2>/dev/null || true
  do_ nft delete table bridge factory_ci 2>/dev/null || true
  for p in CPUWeight CPUQuota MemoryHigh MemoryMax IOReadBandwidthMax IOWriteBandwidthMax IOReadIOPSMax IOWriteIOPSMax; do
    do_ rm -f "/etc/systemd/system.control/machine.slice.d/50-$p.conf"
  done
  do_ systemctl daemon-reload
  echo "factory-ci host isolation and slice limits removed; libvirt itself stays"
  exit 0
fi

# 1. Nothing physical in a bridge, no device that puts a guest MAC on a physical link.
echo "== 1. physical network"
for port in /sys/class/net/*/brif/*; do
  [[ -e $port ]] || continue
  [[ -e /sys/class/net/${port##*/}/device ]] &&
    { echo "bridge ${port%/brif/*} holds the physical port ${port##*/}: refusing" >&2; exit 1; }
done
links="$(ip -d -o link)"  # read whole first: grep -q under pipefail would read a match as none
if grep -qE ' (macvtap|macvlan|ipvlan) ' <<<"$links"; then echo "a macvtap/macvlan/ipvlan link exists: refusing" >&2; exit 1; fi
grep -qE '(vmx|svm)' /proc/cpuinfo && [[ -c /dev/kvm ]] || { echo "no hardware virtualization (/dev/kvm)" >&2; exit 1; }
command -v nft >/dev/null || { echo "nft is missing (apt install nftables)" >&2; exit 1; }
echo "  no bridge holds a physical port; no macvtap, macvlan or ipvlan"

# 2. The host's isolation, loaded before libvirt can start anything.
echo "== 2. isolation (tables inet and bridge factory_ci)"
extra="$(for b in "${block[@]}"; do printf ', %s' "$b"; done)"
rendered="$(sed "s#@BLOCKED@#$extra#" "$here/isolation.nft")"
check=(nft -c -f -); [[ $(id -u) == 0 ]] || check=(unshare -rn nft -c -f -)  # a dry run as the user
"${check[@]}" <<<"$rendered" || { echo "isolation.nft does not parse" >&2; exit 1; }
step "write $rules (blocked besides the private ranges: ${extra#, })"
[[ -n $dry ]] || { install -d -m 0755 /etc/factory-ci; printf '%s\n' "$rendered" >"$rules.tmp"; chmod 0644 "$rules.tmp"; mv -f "$rules.tmp" "$rules"; }
step "write $unit: oneshot nft -f $rules, before libvirtd and libvirt-guests, no stop action"
[[ -n $dry ]] || cat >"$unit" <<EOF
# factory-ci host isolation (rules-factory decision 0081). Written by prepare-host.sh.
[Unit]
Description=factory-ci host isolation (nftables tables inet/bridge factory_ci)
DefaultDependencies=no
After=local-fs.target
Before=libvirtd.service libvirt-guests.service network-pre.target
Wants=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f $rules

[Install]
WantedBy=multi-user.target
EOF
step "write $dropin: libvirtd Requires= and After= factory-ci-isolation"
[[ -n $dry ]] || { install -d -m 0755 "${dropin%/*}"; printf '%s\n' "# rules-factory decision 0081: no VM starts without the host's isolation." \
  "[Unit]" "Requires=factory-ci-isolation.service" "After=factory-ci-isolation.service" >"$dropin"; }
do_ systemctl daemon-reload
do_ systemctl enable factory-ci-isolation.service
do_ systemctl restart factory-ci-isolation.service

# 3. libvirt.
echo "== 3. packages"
export DEBIAN_FRONTEND=noninteractive
do_ apt-get install -y -q --no-install-recommends libvirt-daemon-system libvirt-clients virtinst qemu-system-x86 qemu-utils xorriso

# 4. libvirt's stock network off; forwarding off when nothing needs it.
echo "== 4. libvirt's default network and forwarding"
stopped=
if info="$(virsh -c qemu:///system net-info default 2>/dev/null)"; then
  virsh_ net-autostart default --disable
  if [[ $info =~ Active:\ *yes ]]; then
    if [[ -n "$(ls /sys/class/net/virbr0/brif 2>/dev/null)" ]]; then echo "the default network has a port in use; leaving it" >&2; exit 1; fi
    virsh_ net-destroy default; stopped=default
  fi
fi
nat=
for n in $(virsh -c qemu:///system net-list --name 2>/dev/null); do
  [[ $n == "$stopped" ]] && continue
  [[ "$(virsh -c qemu:///system net-dumpxml "$n")" =~ \<forward\ mode=.(nat|route) ]] && nat="$nat $n"
done
if [[ -z $nat ]]; then do_ sysctl -q -w net.ipv4.ip_forward=0
else echo "  forwarding stays on for the running NAT network(s):$nat (ufw's forward policy and isolation.nft still apply)"; fi

# 5. Group and storage pool.
echo "== 5. group and pool"
do_ usermod -aG libvirt "$user"
pool="$(virsh -c qemu:///system pool-info default 2>/dev/null)" || { virsh_ pool-define-as default dir --target /var/lib/libvirt/images; pool=; }
virsh_ pool-autostart default
[[ $pool =~ State:\ *running ]] || virsh_ pool-start default
do_ systemctl enable libvirt-guests.service

# 6. Limits on every VM together.
echo "== 6. machine.slice"
props=(CPUWeight=50)
[[ -n $cpu ]] && props+=("CPUQuota=$((cpu * 100))%")
[[ -n $memmax ]] && props+=("MemoryHigh=$(( ${memmax%G} - 1 ))G" "MemoryMax=$memmax")
images=/var/lib/libvirt/images
[[ -d $images || -n $dry ]] || install -d -m 0711 "$images"
[[ -n $iobw ]] && props+=("IOReadBandwidthMax=$images $iobw" "IOWriteBandwidthMax=$images $iobw")
[[ -n $ioiops ]] && props+=("IOReadIOPSMax=$images $ioiops" "IOWriteIOPSMax=$images $ioiops")
do_ systemctl set-property machine.slice "${props[@]}"

echo "== done"
[[ -n $dry ]] && { echo "dry run: nothing was changed"; exit 0; }
systemctl is-active --quiet factory-ci-isolation.service || { echo "factory-ci-isolation is not active" >&2; exit 1; }
nft list table inet factory_ci >/dev/null && nft list table bridge factory_ci >/dev/null
systemctl show machine.slice -p CPUWeight -p CPUQuotaPerSecUSec -p MemoryHigh -p MemoryMax -p IOReadBandwidthMax \
  -p IOWriteBandwidthMax -p IOReadIOPSMax -p IOWriteIOPSMax | sed 's/^/  /'
echo "factory-ci host ready; $user is in the libvirt group from its next login (until then: sg libvirt -c ...)"
