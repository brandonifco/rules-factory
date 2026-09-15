#!/usr/bin/env bash
# Run a command blind: the network reachable only through the allowlist proxy, and the filesystem
# reduced to the system, the .NET SDK and the workspace. RUNBOOK.md, "Isolation".
#
#   sandbox/run-isolated.sh WORKSPACE -- COMMAND [ARGS...]
#
# Needs no sudo. bubblewrap (/usr/bin/bwrap) makes unprivileged user, mount, PID and network
# namespaces. The network namespace has only loopback. The proxy runs outside, on a Unix socket that is
# the only thing bound in from outside the workspace; a bridge inside listens on 127.0.0.1:3128 and
# forwards to it, and HTTPS_PROXY points at the bridge. A process that ignores the proxy reaches nothing.
#
# The filesystem: /usr, /etc and the lib directories read-only, the .NET SDK read-only (and /snap, read-only,
# because the snap-installed SDK's loader lives in /snap/core22), a fresh /tmp,
# and WORKSPACE read-write as the session's HOME. Nothing else of the host is visible: not /home, so not
# any clone of hoyle-backgammon or rules-factory, and not ~/.claude or ~/.nuget.
#
# The proxy's log is written OUTSIDE the workspace, to LOGDIR (default: WORKSPACE/../network-logs),
# where the session cannot reach it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "${1:?usage: run-isolated.sh WORKSPACE -- COMMAND...}" && pwd)"
shift
[[ "${1:-}" == "--" ]] && shift
[[ $# -gt 0 ]] || { echo "usage: run-isolated.sh WORKSPACE -- COMMAND..." >&2; exit 2; }

LOGDIR="${LOGDIR:-$(dirname "$WORKSPACE")/network-logs}"
mkdir -p "$LOGDIR"
# A Unix socket path is limited to 108 bytes, so the socket lives in a short private directory.
SOCKDIR="$(mktemp -d "${XDG_RUNTIME_DIR:-/tmp}/rebuild.XXXXXX")"
SOCKET="$SOCKDIR/proxy.sock"
python3 "$HERE/allowlist-proxy.py" serve --socket "$SOCKET" --allow "$HERE/allowlist.txt" \
  --log "$LOGDIR/network.jsonl" >"$LOGDIR/proxy.out" 2>&1 &
PROXY=$!
trap 'kill $PROXY 2>/dev/null || true; rm -rf "$SOCKDIR"' EXIT
for _ in $(seq 50); do [[ -S "$SOCKET" ]] && break; sleep 0.1; done
[[ -S "$SOCKET" ]] || { echo "the allowlist proxy did not start" >&2; cat "$LOGDIR/proxy.out" >&2; exit 1; }

# The snap wrapper for dotnet refuses to run in a namespace; the SDK binary itself does not.
DOTNET_ROOT="${DOTNET_ROOT:-/var/snap/dotnet/common/dotnet}"

binds=(--ro-bind /usr /usr --ro-bind /etc /etc)
# EXTRA_RO_BINDS: colon-separated host paths made visible read-only at the same path, e.g. the install
# directory of an agent CLI that runs inside (RUNBOOK.md, "Running the agent inside"). Nothing else.
IFS=: read -r -a extra <<<"${EXTRA_RO_BINDS:-}"
for path in "${extra[@]}"; do
  [[ -n "$path" ]] && binds+=(--ro-bind "$path" "$path")
done
for dir in /bin /sbin /lib /lib64 /lib32; do
  [[ -L "$dir" ]] && binds+=(--symlink "$(readlink "$dir")" "$dir") || { [[ -d "$dir" ]] && binds+=(--ro-bind "$dir" "$dir"); }
done

bwrap \
  "${binds[@]}" \
  --ro-bind "$DOTNET_ROOT" /opt/dotnet \
  --ro-bind-try /snap /snap \
  --ro-bind "$HERE/allowlist-proxy.py" /opt/sandbox/allowlist-proxy.py \
  --bind "$SOCKDIR" /run/proxy \
  --bind "$WORKSPACE" /workspace \
  --dev /dev --proc /proc --tmpfs /tmp \
  --unshare-all --die-with-parent \
  --chdir /workspace \
  --clearenv \
  --setenv HOME /workspace/home \
  --setenv PATH /opt/dotnet:/usr/local/bin:/usr/bin:/bin \
  --setenv DOTNET_ROOT /opt/dotnet \
  --setenv NUGET_PACKAGES /workspace/home/.nuget/packages \
  --setenv DOTNET_CLI_TELEMETRY_OPTOUT 1 \
  --setenv DOTNET_NOLOGO 1 \
  --setenv HTTPS_PROXY http://127.0.0.1:3128 --setenv https_proxy http://127.0.0.1:3128 \
  --setenv HTTP_PROXY http://127.0.0.1:3128 --setenv http_proxy http://127.0.0.1:3128 \
  --setenv TERM "${TERM:-dumb}" \
  bash -c '
    mkdir -p "$HOME"
    python3 /opt/sandbox/allowlist-proxy.py bridge --socket /run/proxy/proxy.sock --port 3128 >/dev/null 2>&1 &
    for _ in $(seq 50); do (exec 3<>/dev/tcp/127.0.0.1/3128) 2>/dev/null && break; sleep 0.1; done
    exec "$@"
  ' run-isolated "$@"
