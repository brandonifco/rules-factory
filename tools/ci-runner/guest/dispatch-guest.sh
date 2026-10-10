#!/bin/bash
# dispatch-guest -- the guest's half of trusted dispatch (decision 0080). Run as root, only by the
# host's dispatcher and `factory-ci`, through the admin account. It never sees a GitHub credential
# but the one-job runner configuration it is handed on stdin.
#
#   trust NAME OWNER/REPO         serve OWNER/REPO by dispatch, through accounts fci-NAME and fcj-NAME
#   untrust NAME                  stop serving it; its one-job runners are stopped
#   admit NAME RUN-ATTEMPT...     let these runs' jobs past the job-started hook
#   start NAME LANE RUNNER_ID     start a one-job runner (LANE a: fci-NAME, b: fcj-NAME) from the
#                                 JIT configuration on stdin; refused while that account has one
#   stop RUNNER_ID                stop one (an idle listener exits; a running job may finish)
#   reap                          remove finished one-job runners and admissions older than a day
#   inventory                     one JSON object per line: dispatch, persistent and jit entries
#
# A repository served here is public, so its accounts never hold a standing registration: a runner
# registered with a public repository would take a fork's job. Two rules keep a job of the owner's
# that runs a hostile dependency from reaching past its own job:
#   * root never writes through a path a runner account can change. A one-job runner's directory is
#     made under the root-owned /srv/factory-ci-jit (0755: the runner refuses to start unless it can
#     list every directory above it), filled as root, and only then handed over;
#   * an account has at most one runner at a time, so no job shares a UID with a listener that is
#     still waiting for a job. Two accounts per repository keep its two jobs parallel.
set -euo pipefail
marks=/etc/factory-ci/dispatch accounts=/etc/factory-ci/dispatch-accounts
trust=/run/factory-ci-trust units=/run/systemd/system jits=/srv/factory-ci-jit
template=/etc/systemd/system/factory-ci-runner@.service
LEASE=900  # seconds a one-job runner may wait for its job; the hook refuses one assigned later
die() { echo "dispatch-guest: $*" >&2; exit 2; }
name_ok() { [[ ${1:-} =~ ^[a-z0-9][a-z0-9-]{0,23}$ ]] || die "bad name: ${1:-}"; }
id_ok() { [[ ${1:-} =~ ^[0-9]{1,19}$ ]] || die "bad runner id: ${1:-}"; }
served() { name_ok "$1"; [[ -f $marks/$1 && ! -L $marks/$1 ]] || die "$1 is not served by dispatch (factory-ci trust)"; }
lanes() { echo "fci-$1 fcj-$1"; }
unit_user() { sed -n 's/^User=//p' "$1"; }
busy() { # ACCOUNT: whether a one-job runner of this account is still up
  local f
  for f in "$units"/factory-ci-jit-*.service; do
    [[ -f $f ]] || continue
    [[ $(unit_user "$f") == "$1" ]] && systemctl is-active --quiet "$(basename "$f" .service)" && return 0
  done
  return 1
}

cmd_trust() {
  name_ok "${1:-}"; [[ ${2:-} =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "give NAME OWNER/REPO"
  local user home
  for user in $(lanes "$1"); do
    home="/srv/factory-ci/$user"
    [[ -e $home/runner/.runner ]] && die "$user has a standing registration; deregister it first (a public repository never has one)"
    id "$user" >/dev/null 2>&1 ||
      useradd --system --home-dir "$home" --create-home --shell /usr/sbin/nologin --groups factory-ci "$user"
    chmod 0700 "$home"
  done
  install -d -m 0755 "$marks" "$accounts" "$trust" "$trust/runners"
  install -d -m 0755 "$jits"
  printf '%s\n' "$2" >"$marks/.$1.tmp"; chmod 0644 "$marks/.$1.tmp"; mv -f "$marks/.$1.tmp" "$marks/$1"
  for user in $(lanes "$1"); do printf '%s\n' "$1" >"$accounts/$user"; chmod 0644 "$accounts/$user"; done
  install -d -m 0755 "$trust/$1"
  echo "$2 is served by dispatch through $(lanes "$1")"
}

cmd_untrust() {
  name_ok "${1:-}"; local user f
  rm -f "$marks/$1"
  for user in $(lanes "$1"); do
    for f in "$units"/factory-ci-jit-*.service; do
      [[ -f $f && $(unit_user "$f") == "$user" ]] && systemctl stop "$(basename "$f" .service)" || true
    done
    rm -f "$accounts/$user"
  done
  rm -rf "${trust:?}/$1"
  cmd_reap
}

cmd_admit() {
  served "${1:-}"; local name="$1" a; shift
  install -d -m 0755 "$trust/$name"
  for a in "$@"; do
    [[ $a =~ ^[0-9]{1,19}-[0-9]{1,6}$ ]] || die "bad run-attempt: $a"
    : >"$trust/$name/$a"; chmod 0644 "$trust/$name/$a"
  done
}

cmd_start() {
  served "${1:-}"; id_ok "${3:-}"
  local name="$1" id="$3" user config dir unit want
  case "${2:-}" in a) user="fci-$name" ;; b) user="fcj-$name" ;; *) die "lane is a or b" ;; esac
  [[ -f $accounts/$user ]] || die "$user is not one of $name's accounts"
  busy "$user" && die "$user already has a one-job runner up; one per account at a time"
  dir="$jits/$id" unit="factory-ci-jit-$id"
  IFS= read -r config; [[ $config =~ ^[A-Za-z0-9+/=]+$ ]] || die "no JIT configuration on stdin"
  [[ -e $dir || -e $units/$unit.service ]] && die "runner $id exists already"
  install -d -m 0755 "$jits"
  # Made and filled as root, in a directory only root can write, then handed over whole: there is
  # no moment at which the account can put a link where root is about to write.
  mkdir -m 0700 "$dir"
  tar -xzf /opt/factory-ci/dist/actions-runner-linux-x64.tar.gz -C "$dir" --no-same-owner
  chmod 0700 "$dir"  # the archive's own "." entry widens it
  install -m 0600 /etc/factory-ci/runner.env "$dir/.env"
  sed -n 's/^PATH=//p' /etc/factory-ci/runner.env >"$dir/.path"; chmod 0600 "$dir/.path"
  printf '%s' "$config" >"$dir/.jitconfig"; chmod 0600 "$dir/.jitconfig"
  chown -R "$user:$user" "$dir"
  printf '%s %s %s\n' "$user" "$name" "$(( $(date +%s) + LEASE ))" >"$trust/runners/$id"; chmod 0644 "$trust/runners/$id"
  # The standing runners' unit, with its hardening, for one job: one place states the sandbox.
  sed -e "s#%i#$user#g" \
      -e "s#^Description=.*#Description=One-job GitHub Actions runner $id for $user (factory-ci, decision 0080)#" \
      -e "s#^ConditionPathExists=.*#ConditionPathExists=$dir/.jitconfig#" \
      -e "s#^WorkingDirectory=.*#WorkingDirectory=$dir#" \
      -e "s#^ExecStart=.*#ExecStart=/opt/factory-ci/bin/jit-run#" \
      -e "s#^Restart=.*#Restart=no\nRuntimeMaxSec=8h#" \
      -e "/^RestartSec=/d" \
      -e "s#^KillMode=.*#KillMode=mixed#" \
      -e "s#^ReadWritePaths=.*#ReadWritePaths=/srv/factory-ci/$user $dir /run/factory-ci#" \
      -e '/^\[Install\]/,$d' "$template" >"$units/.$unit.tmp"
  for want in "User=$user" "WorkingDirectory=$dir" "ExecStart=/opt/factory-ci/bin/jit-run" "Restart=no" \
              "KillMode=mixed" "ReadWritePaths=/srv/factory-ci/$user $dir /run/factory-ci" "NoNewPrivileges=yes" \
              "ProtectProc=invisible"; do
    [[ $(grep -cx "$want" "$units/.$unit.tmp") == 1 ]] || { rm -f "$units/.$unit.tmp"; rm -rf "$dir"; die "unit for $id lacks: $want"; }
  done
  mv "$units/.$unit.tmp" "$units/$unit.service"
  systemctl daemon-reload
  systemctl start "$unit"
  echo "started $unit as $user"
}

cmd_stop() { id_ok "${1:-}"; systemctl stop "factory-ci-jit-$1" 2>/dev/null || true; }

cmd_reap() {
  local f unit id changed=
  for f in "$units"/factory-ci-jit-*.service; do
    [[ -f $f ]] || continue
    unit="$(basename "$f" .service)" id="${unit#factory-ci-jit-}"
    systemctl is-active --quiet "$unit" && continue
    [[ $id =~ ^[0-9]+$ ]] && rm -rf "${jits:?}/$id" && rm -f "$trust/runners/$id"
    systemctl reset-failed "$unit" 2>/dev/null || true
    rm -f "$f"; changed=1
  done
  [[ -n $changed ]] && systemctl daemon-reload
  [[ -d $trust ]] && find "$trust" -mindepth 2 -maxdepth 2 -type f -not -path "$trust/runners/*" -mmin +1440 -delete
  return 0
}

cmd_inventory() {
  # Emitted with jq --arg, so a value can never become a second entry; what a runner account wrote
  # (a persistent runner's .runner) is checked against the shape it must have, and dropped if not.
  local f d user url
  for f in "$marks"/*; do
    [[ -f $f && ! -L $f && ${f##*/} =~ ^[a-z0-9][a-z0-9-]{0,23}$ ]] || continue
    jq -cn --arg name "${f##*/}" --arg repo "$(head -1 "$f")" '{kind:"dispatch",name:$name,repo:$repo}'
  done
  for d in /srv/factory-ci/fci-*/runner; do
    [[ -f $d/.runner ]] || continue
    user="${d%/runner}"; user="${user##*/}"
    url="$(jq -r '.gitHubUrl // empty' "$d/.runner" 2>/dev/null | head -1)"
    [[ $url =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || url=invalid
    jq -cn --arg account "$user" --arg url "$url" '{kind:"persistent",account:$account,url:$url}'
  done
  for f in "$units"/factory-ci-jit-*.service; do
    [[ -f $f ]] || continue
    unit="$(basename "$f" .service)"
    jq -cn --arg id "${unit#factory-ci-jit-}" --arg account "$(unit_user "$f")" \
      --arg state "$(systemctl is-active "$unit" || true)" '{kind:"jit",id:$id,account:$account,state:$state}'
  done
}

[[ $(id -u) == 0 ]] || die "run as root"
c="${1:-}"; shift || true
case "$c" in
  trust|untrust|admit|start|stop|reap|inventory) "cmd_$c" "$@" ;;
  *) sed -n '2,22s/^# \{0,1\}//p' "$0" >&2; exit 2 ;;
esac
