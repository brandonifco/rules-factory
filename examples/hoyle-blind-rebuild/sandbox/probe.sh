#!/usr/bin/env bash
# What the isolated session can reach. Run as: sandbox/run-isolated.sh WORKSPACE -- sandbox/probe.sh
# Expected: the allowlisted hosts answer, everything else is refused (403 from the proxy), and a
# connection that bypasses the proxy reaches nothing.
set -uo pipefail
check() {
  local label="$1"; shift
  local code
  code="$(curl -sS -m 15 -o /dev/null -w '%{http_code}' "$@" 2>/dev/null)" || code="${code:-000} (failed)"
  printf '%-58s %s\n' "$label" "$code"
}
check "allowed:  https://api.nuget.org/v3/index.json" https://api.nuget.org/v3/index.json
check "allowed:  https://learn.microsoft.com/dotnet/" https://learn.microsoft.com/dotnet/
check "refused:  https://github.com/ (via proxy)" https://github.com/
check "refused:  https://example.com/ (via proxy)" https://example.com/
check "refused:  http://example.com/ (plain http)" http://example.com/
check "bypass:   https://api.nuget.org/ with --noproxy '*'" --noproxy '*' https://api.nuget.org/v3/index.json
check "bypass:   direct IP 140.82.112.3:443" --noproxy '*' -k https://140.82.112.3/
dotnet --list-sdks
for path in /home /root /var/snap /tmp/claude-1000 /workspace/../home; do
  if [[ -e "$path" ]] && [[ -n "$(ls -A "$path" 2>/dev/null)" ]]; then
    printf '%-58s %s\n' "filesystem: $path" "VISIBLE"
  else
    printf '%-58s %s\n' "filesystem: $path" "not visible"
  fi
done
printf '%-58s %s\n' "filesystem: / holds" "$(ls / | tr '\n' ' ')"
