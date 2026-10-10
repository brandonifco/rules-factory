#!/bin/bash
# register NAME OWNER/REPO [LABELS] -- (re-)register this guest's runner for one repository.
# Reads the registration token from stdin (never argv). Run as root by `factory-ci register`.
#
# Each repository gets its own system account fci-NAME (no sudo, no login shell, no SSH key),
# home /srv/factory-ci/fci-NAME (0700), so one repository's jobs cannot read or poison another's
# workspace, NuGet cache or credentials.
set -euo pipefail
name="$1" repo="$2" labels="${3:-factory-ci}"
[[ $name =~ ^[a-z0-9][a-z0-9-]{0,23}$ ]] || { echo "bad name: $name" >&2; exit 2; }
[[ $repo =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "bad repo: $repo" >&2; exit 2; }
IFS= read -r token
[[ -n $token ]] || { echo "no registration token on stdin" >&2; exit 2; }
user="fci-$name" home="/srv/factory-ci/fci-$name" dir="/srv/factory-ci/fci-$name/runner"

id "$user" >/dev/null 2>&1 ||
  useradd --system --home-dir "$home" --create-home --shell /usr/sbin/nologin --groups factory-ci "$user"
chmod 0700 "$home"
systemctl stop "factory-ci-runner@$user" 2>/dev/null || true
if [[ ! -x $dir/config.sh ]]; then
  install -d -o "$user" -g "$user" -m 0700 "$dir"
  runuser -u "$user" -- tar -xzf /opt/factory-ci/dist/actions-runner-linux-x64.tar.gz -C "$dir"
  chmod 0700 "$dir"
fi
# A re-registration replaces the runner of the same name on GitHub (--replace); the local
# credentials of the old one go first, or config.sh refuses.
rm -f "$dir/.runner" "$dir/.credentials" "$dir/.credentials_rsaparams"
cd "$dir"
runuser -u "$user" -- env -i HOME="$home" PATH=/usr/bin:/bin LANG=C.UTF-8 ACTIONS_RUNNER_INPUT_TOKEN="$token" \
  ./config.sh --unattended --url "https://github.com/$repo" --name "$(hostname)" \
  --labels "$labels" --work _work --replace >/dev/null
install -o "$user" -g "$user" -m 0600 /etc/factory-ci/runner.env "$dir/.env"
# runsvc.sh exports .path as the listener's PATH; keep it the one runner.env names.
sed -n 's/^PATH=//p' /etc/factory-ci/runner.env | install -o "$user" -g "$user" -m 0600 /dev/stdin "$dir/.path"
systemctl enable --now "factory-ci-runner@$user" >/dev/null
echo "registered $(hostname) for $repo as $user (labels: self-hosted, Linux, X64, $labels)"
