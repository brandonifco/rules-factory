#!/bin/bash
# dispatch-guest -- the guest's half of trusted dispatch (decision 0080). Run as root, only by the
# host's dispatcher and `factory-ci`, through the admin account. It never sees a GitHub credential
# but the one-job runner configuration it is handed on stdin.
#
#   trust NAME OWNER/REPO       serve OWNER/REPO by dispatch, as account fci-NAME (never registered)
#   untrust NAME                stop serving it; its one-job runners are stopped
#   admit NAME RUN-ATTEMPT...   let these runs' jobs past the job-started hook on fci-NAME
#   start NAME RUNNER_ID        start a one-job runner from the JIT configuration on stdin
#   stop RUNNER_ID              stop one (an idle listener exits; a running job may finish)
#   reap                        remove finished one-job runners and admissions older than a day
#   inventory                   "dispatch ACCOUNT REPO", "persistent ACCOUNT URL", "jit ID ACCOUNT STATE"
#
# A repository served here is public, so its account never holds a standing registration: a
# runner registered with a public repository would take a fork's job. `trust` refuses an account
# that has one, and register refuses an account that is trusted.
set -euo pipefail
marks=/etc/factory-ci/dispatch admissions=/run/factory-ci-trust units=/run/systemd/system
template=/etc/systemd/system/factory-ci-runner@.service
die() { echo "dispatch-guest: $*" >&2; exit 2; }
name_ok() { [[ ${1:-} =~ ^[a-z0-9][a-z0-9-]{0,23}$ ]] || die "bad name: ${1:-}"; }
id_ok() { [[ ${1:-} =~ ^[0-9]{1,19}$ ]] || die "bad runner id: ${1:-}"; }
trusted() { name_ok "$1"; [[ -f $marks/fci-$1 ]] || die "fci-$1 is not served by dispatch (factory-ci trust)"; }
unit_of() { echo "factory-ci-jit-$1"; }

cmd_trust() {
  name_ok "${1:-}"; [[ ${2:-} =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "give NAME OWNER/REPO"
  local user="fci-$1" home="/srv/factory-ci/fci-$1"
  [[ -f $home/runner/.runner ]] && die "$user has a standing registration; deregister it first (a public repository never has one)"
  id "$user" >/dev/null 2>&1 ||
    useradd --system --home-dir "$home" --create-home --shell /usr/sbin/nologin --groups factory-ci "$user"
  chmod 0700 "$home"
  install -d -m 0755 "$marks"
  printf '%s\n' "$2" | install -m 0644 /dev/stdin "$marks/$user"
  install -d -m 0755 -o root -g root "$admissions/$user"
  echo "fci-$1 serves $2 by dispatch"
}

cmd_untrust() {
  name_ok "${1:-}"; local user="fci-$1" f
  rm -f "$marks/$user"; rm -rf "${admissions:?}/$user"
  for f in "$units"/factory-ci-jit-*.service; do
    [[ -f $f ]] && grep -qx "User=$user" "$f" && systemctl stop "$(basename "$f" .service)" || true
  done
  cmd_reap
}

cmd_admit() {
  trusted "${1:-}"; local user="fci-$1" a; shift
  install -d -m 0755 -o root -g root "$admissions/$user"
  for a in "$@"; do
    [[ $a =~ ^[0-9]{1,19}-[0-9]{1,6}$ ]] || die "bad run-attempt: $a"
    : >"$admissions/$user/$a"; chmod 0644 "$admissions/$user/$a"
  done
}

cmd_start() {
  trusted "${1:-}"; id_ok "${2:-}"
  local user="fci-$1" id="$2" config dir unit
  dir="/srv/factory-ci/fci-$1/jit/$id" unit="$(unit_of "$id")"
  IFS= read -r config; [[ -n $config ]] || die "no JIT configuration on stdin"
  [[ -e $dir || -e $units/$unit.service ]] && die "runner $id exists already"
  install -d -o "$user" -g "$user" -m 0700 "/srv/factory-ci/fci-$1/jit" "$dir"
  runuser -u "$user" -- tar -xzf /opt/factory-ci/dist/actions-runner-linux-x64.tar.gz -C "$dir"
  install -o "$user" -g "$user" -m 0600 /etc/factory-ci/runner.env "$dir/.env"
  sed -n 's/^PATH=//p' /etc/factory-ci/runner.env | install -o "$user" -g "$user" -m 0600 /dev/stdin "$dir/.path"
  printf '%s' "$config" | install -o "$user" -g "$user" -m 0600 /dev/stdin "$dir/.jitconfig"
  # The standing runners' unit, with its hardening, for one job: one place states the sandbox.
  sed -e "s#%i#$user#g" \
      -e "s#^Description=.*#Description=One-job GitHub Actions runner $id for $user (factory-ci, decision 0080)#" \
      -e "s#^ConditionPathExists=.*#ConditionPathExists=$dir/.jitconfig#" \
      -e "s#^WorkingDirectory=.*#WorkingDirectory=$dir#" \
      -e "s#^ExecStart=.*#ExecStart=/opt/factory-ci/bin/jit-run#" \
      -e "s#^Restart=.*#Restart=no\nRuntimeMaxSec=8h#" \
      -e "/^RestartSec=/d" \
      -e "s#^KillMode=.*#KillMode=mixed#" \
      -e '/^\[Install\]/,$d' "$template" >"$units/$unit.service.tmp"
  local want
  for want in "User=$user" "WorkingDirectory=$dir" "ExecStart=/opt/factory-ci/bin/jit-run" "Restart=no" \
              "KillMode=mixed" "ReadWritePaths=/srv/factory-ci/$user /run/factory-ci" "NoNewPrivileges=yes"; do
    [[ $(grep -cx "$want" "$units/$unit.service.tmp") == 1 ]] || { rm -f "$units/$unit.service.tmp"; rm -rf "$dir"; die "unit for $id lacks: $want"; }
  done
  mv "$units/$unit.service.tmp" "$units/$unit.service"
  systemctl daemon-reload
  systemctl start "$unit"
  echo "started $unit as $user"
}

cmd_stop() { id_ok "${1:-}"; systemctl stop "$(unit_of "$1")" 2>/dev/null || true; }

cmd_reap() {
  local f unit dir changed=
  for f in "$units"/factory-ci-jit-*.service; do
    [[ -f $f ]] || continue
    unit="$(basename "$f" .service)"
    systemctl is-active --quiet "$unit" && continue
    dir="$(sed -n 's/^WorkingDirectory=//p' "$f")"
    case "$dir" in /srv/factory-ci/fci-*/jit/[0-9]*) rm -rf "$dir" ;; esac
    systemctl reset-failed "$unit" 2>/dev/null || true
    rm -f "$f"; changed=1
  done
  [[ -n $changed ]] && systemctl daemon-reload
  [[ -d $admissions ]] && find "$admissions" -mindepth 2 -maxdepth 2 -type f -mmin +1440 -delete
  return 0
}

cmd_inventory() {
  local f d user
  for f in "$marks"/fci-*; do [[ -f $f ]] && echo "dispatch ${f##*/} $(cat "$f")"; done
  for d in /srv/factory-ci/fci-*/runner; do
    [[ -f $d/.runner ]] || continue
    user="${d%/runner}"; echo "persistent ${user##*/} $(jq -r .gitHubUrl "$d/.runner")"
  done
  for f in "$units"/factory-ci-jit-*.service; do
    [[ -f $f ]] || continue
    user="$(sed -n 's/^User=//p' "$f")"; f="$(basename "$f" .service)"
    echo "jit ${f#factory-ci-jit-} $user $(systemctl is-active "$f" || true)"
  done
}

[[ $(id -u) == 0 ]] || die "run as root"
c="${1:-}"; shift || true
case "$c" in
  trust|untrust|admit|start|stop|reap|inventory) "cmd_$c" "$@" ;;
  *) sed -n '2,15s/^# \{0,1\}//p' "$0" >&2; exit 2 ;;
esac
