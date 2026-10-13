#!/bin/bash
# install-collector.sh [--remove] -- run with sudo by the account that runs factory-ci. Installs
# host/collect.sh as /usr/local/sbin/factory-ci-collect (root-owned, 0755) and a sudoers rule by
# which that account, and only it, runs that one program, with exactly its two forms, without a
# password. Nothing else gains privilege. --remove takes both away. Changes no firewall rule, so it
# may run while the VM runs.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
[[ $(id -u) == 0 && -n ${SUDO_USER:-} && $SUDO_USER != root ]] || { echo "run with sudo, as the account that runs factory-ci" >&2; exit 2; }
bin=/usr/local/sbin/factory-ci-collect rule=/etc/sudoers.d/factory-ci-collect
if [[ ${1:-} == --remove ]]; then rm -f "$rule" "$bin"; echo "removed $bin and $rule"; exit 0; fi
[[ $# == 0 ]] || { echo "usage: install-collector.sh [--remove]" >&2; exit 2; }
install -o root -g root -m 0755 "$here/collect.sh" "$bin"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
printf '%s\n' "# factory-ci (rules-factory decision 0081): read-only host checks, written by install-collector.sh." \
  "$SUDO_USER ALL=(root) NOPASSWD: $bin tables, $bin capture *" >"$tmp"
visudo -cqf "$tmp" || { echo "the sudoers rule does not parse; nothing installed" >&2; rm -f "$bin"; exit 1; }
install -o root -g root -m 0440 "$tmp" "$rule"
echo "installed $bin; $SUDO_USER may run 'sudo -n $bin tables' and 'sudo -n $bin capture SECONDS' without a password"
