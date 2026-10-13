#!/bin/bash
# prepare-host.sh -- make an Ubuntu 24.04 machine a factory-ci KVM host. Run once, with sudo, by the
# account that will run `factory-ci`; everything after this needs no sudo. Idempotent.
#
# It installs libvirt and virt-install, puts the account in the `libvirt` group, makes the `default`
# storage pool the VM's disks go in, starts guests with the host (libvirt-guests), and lowers the
# CPU weight of `machine.slice`, where libvirt puts every VM, so that under contention the host's
# own work wins: on a workstation the CI guest takes idle CPU, never the user's.
set -euo pipefail
[[ $(id -u) == 0 && -n ${SUDO_USER:-} && $SUDO_USER != root ]] || { echo "run with sudo, as the account that runs factory-ci" >&2; exit 2; }
weight="${FACTORY_CI_HOST_CPU_WEIGHT:-50}"  # machine.slice against user.slice and system.slice at 100
grep -qE '(vmx|svm)' /proc/cpuinfo && [[ -c /dev/kvm ]] || { echo "no hardware virtualization (/dev/kvm)" >&2; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends libvirt-daemon-system libvirt-clients virtinst qemu-system-x86 qemu-utils xorriso
usermod -aG libvirt "$SUDO_USER"

virsh -c qemu:///system pool-info default >/dev/null 2>&1 ||
  virsh -c qemu:///system pool-define-as default dir --target /var/lib/libvirt/images >/dev/null
virsh -c qemu:///system pool-autostart default >/dev/null
virsh -c qemu:///system pool-start default >/dev/null 2>&1 || true

systemctl enable --now libvirt-guests.service >/dev/null
systemctl set-property machine.slice CPUWeight="$weight"
echo "factory-ci host ready: $(virsh -c qemu:///system version --daemon | sed -n 's/^Running against daemon: //p'), pool default, machine.slice CPUWeight=$weight"
echo "$SUDO_USER is in the libvirt group from its next login; until then: sg libvirt -c 'tools/ci-runner/factory-ci ...'"
