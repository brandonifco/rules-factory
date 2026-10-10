#!/bin/bash
# setup-guest.sh -- make a fresh Ubuntu 24.04 guest a factory-ci runner host. Idempotent; run as
# root from the directory holding this kit (the host's `factory-ci setup` copies it over).
#
# It installs the pinned toolchain (versions.env) read-only under /opt/factory-ci, the job hooks,
# the runner unit and the slice that caps every runner together. It registers no runner:
# `factory-ci register OWNER/REPO` does that, one unprivileged account per repository.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=versions.env
. "$here/versions.env"
[[ $(id -u) == 0 ]] || { echo "run as root" >&2; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
# shellcheck disable=SC2086
apt-get install -y -q --no-install-recommends $APT_PACKAGES

fetch() { # url dest algo hash
  local tmp; tmp="$(mktemp)"
  curl -fsSL --retry 3 -o "$tmp" "$1"
  echo "$4  $tmp" | "${3}sum" -c --quiet - || { rm -f "$tmp"; echo "hash mismatch: $1" >&2; exit 1; }
  install -m 0644 "$tmp" "$2"; rm -f "$tmp"
}

install -d -m 0755 /opt/factory-ci /opt/factory-ci/bin /opt/factory-ci/dist /opt/factory-ci/dotnet /etc/factory-ci

# .NET SDKs: one shared, root-owned, read-only install. actions/setup-dotnet finds the pinned
# version already in DOTNET_INSTALL_DIR and downloads nothing; a job cannot change it.
for v in $DOTNET_SDKS; do
  if [[ ! -d /opt/factory-ci/dotnet/sdk/$v ]]; then
    var="DOTNET_SDK_SHA512_${v//./_}"
    f=/opt/factory-ci/dist/dotnet-sdk-$v-linux-x64.tar.gz
    fetch "https://builds.dotnet.microsoft.com/dotnet/Sdk/$v/dotnet-sdk-$v-linux-x64.tar.gz" "$f" sha512 "${!var}"
    tar -xzf "$f" -C /opt/factory-ci/dotnet && rm -f "$f"
  fi
done

for v in $DOTNET_RUNTIMES; do
  if [[ ! -d /opt/factory-ci/dotnet/shared/Microsoft.NETCore.App/$v ]]; then
    var="DOTNET_RUNTIME_SHA512_${v//./_}"
    f=/opt/factory-ci/dist/dotnet-runtime-$v-linux-x64.tar.gz
    fetch "https://builds.dotnet.microsoft.com/dotnet/Runtime/$v/dotnet-runtime-$v-linux-x64.tar.gz" "$f" sha512 "${!var}"
    tar -xzf "$f" -C /opt/factory-ci/dotnet && rm -f "$f"
  fi
done

if [[ "$(/opt/factory-ci/gh/bin/gh --version 2>/dev/null | head -1)" != "gh version $GH_VERSION"* ]]; then
  f=/opt/factory-ci/dist/gh_${GH_VERSION}_linux_amd64.tar.gz
  fetch "https://github.com/cli/cli/releases/download/v$GH_VERSION/gh_${GH_VERSION}_linux_amd64.tar.gz" "$f" sha256 "$GH_SHA256"
  rm -rf /opt/factory-ci/gh && install -d -m 0755 /opt/factory-ci/gh
  tar -xzf "$f" -C /opt/factory-ci/gh --strip-components=1 && rm -f "$f"
fi

# Node (GitHub's hosted image ships one; reykholt-web's CI uses it).
if [[ "$(/opt/factory-ci/node/bin/node --version 2>/dev/null)" != "v$NODE_VERSION" ]]; then
  f=/opt/factory-ci/dist/node-v$NODE_VERSION-linux-x64.tar.xz
  fetch "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.xz" "$f" sha256 "$NODE_SHA256"
  rm -rf /opt/factory-ci/node && install -d -m 0755 /opt/factory-ci/node
  tar -xJf "$f" -C /opt/factory-ci/node --strip-components=1 && rm -f "$f"
fi

# Python in the hosted tool cache's layout (/opt/hostedtoolcache/Python/<v>/x64 + x64.complete),
# installed by the build's own setup.sh, then left root-owned.
if [[ ! -f /opt/hostedtoolcache/Python/$PYTHON_TOOLCACHE_VERSION/x64.complete ]]; then
  install -d -m 0755 /opt/hostedtoolcache
  t="$(mktemp -d)"; fetch "$PYTHON_TOOLCACHE_URL" "$t/python.tar.gz" sha256 "$PYTHON_TOOLCACHE_SHA256"
  tar -xzf "$t/python.tar.gz" -C "$t" && (cd "$t" && RUNNER_TOOL_CACHE=/opt/hostedtoolcache AGENT_TOOLSDIRECTORY=/opt/hostedtoolcache bash ./setup.sh >/dev/null)
  rm -rf "$t"
fi

# The runner distribution every registration is unpacked from. The runner updates itself after
# that (GitHub refuses runners that fall too far behind); this pin is only the starting point.
f=/opt/factory-ci/dist/actions-runner-linux-x64-$RUNNER_VERSION.tar.gz
[[ -f $f ]] || fetch "https://github.com/actions/runner/releases/download/v$RUNNER_VERSION/actions-runner-linux-x64-$RUNNER_VERSION.tar.gz" "$f" sha256 "$RUNNER_SHA256"
ln -sfn "$f" /opt/factory-ci/dist/actions-runner-linux-x64.tar.gz

# Job hooks and the slot holder.
install -m 0755 "$here/job-started.sh" /opt/factory-ci/bin/job-started.sh
install -m 0755 "$here/job-completed.sh" /opt/factory-ci/bin/job-completed.sh
install -m 0755 "$here/slot-hold.sh" /opt/factory-ci/bin/slot-hold
install -m 0700 "$here/register.sh" /opt/factory-ci/bin/register
install -m 0644 "$here/runner.env" /etc/factory-ci/runner.env
# Two job slots, as measured on 2026-10-09 (docs/self-hosted-runners.md, Everyday operation).
[[ -f /etc/factory-ci/slots ]] || echo 2 > /etc/factory-ci/slots

# Shared job-slot locks. The group lets runner accounts take a slot; nothing else is shared.
getent group factory-ci >/dev/null || groupadd --system factory-ci
install -m 0644 "$here/factory-ci.tmpfiles" /etc/tmpfiles.d/factory-ci.conf
systemd-tmpfiles --create /etc/tmpfiles.d/factory-ci.conf
install -d -m 0755 /srv/factory-ci

install -m 0644 "$here/factory-ci.slice" /etc/systemd/system/factory-ci.slice
install -m 0644 "$here/factory-ci-runner@.service" /etc/systemd/system/factory-ci-runner@.service
systemctl daemon-reload
# Registered runners take a changed runner.env and unit on restart.
for d in /srv/factory-ci/fci-*/runner; do
  [[ -f $d/.runner ]] || continue
  u="$(stat -c %U "$d")"
  install -o "$u" -g "$u" -m 0600 /etc/factory-ci/runner.env "$d/.env"
  sed -n 's/^PATH=//p' /etc/factory-ci/runner.env | install -o "$u" -g "$u" -m 0600 /dev/stdin "$d/.path"
done
for u in $(systemctl list-units --plain --no-legend 'factory-ci-runner@*' | awk '{print $1}'); do
  systemctl restart "$u"
done
echo "factory-ci guest ready: runner $RUNNER_VERSION, .NET $DOTNET_SDKS (+ runtimes $DOTNET_RUNTIMES), gh $GH_VERSION, node $NODE_VERSION, python toolcache $PYTHON_TOOLCACHE_VERSION, slots $(cat /etc/factory-ci/slots)"
