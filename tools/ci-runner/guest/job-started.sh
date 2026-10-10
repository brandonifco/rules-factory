#!/bin/bash
# job-started -- the runner's ACTIONS_RUNNER_HOOK_JOB_STARTED on a factory-ci guest.
#
# Every repository has its own runner registration (GitHub cannot share one between personal
# repositories), so several listeners run on this VM and each would take a job. This hook makes
# the VM run at most N jobs at once, N = /etc/factory-ci/slots: a job takes a slot before its
# first step and keeps it until its Runner.Worker exits. A job that finds every slot taken waits
# here, visibly, and the wait counts against its timeout-minutes.
set -euo pipefail
state=/run/factory-ci
slots="$(cat /etc/factory-ci/slots 2>/dev/null || echo 1)"
me="$(id -un)"
ready="$state/hold-$me"

pid=$PPID worker=
while [[ $pid -gt 1 ]]; do
  if [[ "$(cat "/proc/$pid/comm" 2>/dev/null)" == Runner.Worker ]]; then worker=$pid; break; fi
  pid="$(awk '{print $4}' "/proc/$pid/stat")"
done
[[ -n $worker ]] || { echo "::error::factory-ci: no Runner.Worker above the job-started hook"; exit 1; }

# A repository served by trusted dispatch is public (decision 0080). Its jobs reach this VM only on
# a one-job runner the host's dispatcher started, under /srv/factory-ci-jit, and only for a run it
# admitted. What says so is root's, under /run/factory-ci-trust and /etc/factory-ci, where no runner
# account can write. The check fails closed: a one-job runner, or an account that serves dispatch,
# is refused unless every condition holds -- the runner was started for this account, it got its
# job within its lease, the job is of the repository the account serves, and its run and attempt
# were admitted. Failing this hook is not enough to stop a job: the runner still runs every action's
# `pre:` and `post:` step after a failed job-started hook (seen on 2026-10-10, runner 2.338.0), as
# it would a step marked `if: always()`, and a fork writes both. So a refusal kills the job's
# Runner.Worker, which runs every step there is, before it returns; GitHub then has no log for the
# job, so the refusal goes to the guest's journal too. (A job's `env:` does not reach this hook:
# neither a forged GITHUB_RUN_ID nor BASH_ENV did, same day.)
exe="$(readlink "/proc/$worker/exe" 2>/dev/null || true)"
if [[ $exe == /srv/factory-ci-jit/* || -e /etc/factory-ci/dispatch-accounts/$me || ! -r /etc/factory-ci/dispatch-accounts ]]; then
  run="${GITHUB_RUN_ID:-}" attempt="${GITHUB_RUN_ATTEMPT:-}" why=
  id="$(sed -n 's#^/srv/factory-ci-jit/\([a-z0-9][a-z0-9-]*-[0-9]\{1,19\}\)/bin/Runner.Worker$#\1#p' <<<"$exe")"
  owner= name= deadline=
  [[ -n $id ]] && read -r owner name deadline _ 2>/dev/null </run/factory-ci-trust/runners/"$id" || true
  if [[ -z $id ]]; then why="not a one-job runner"
  elif [[ $owner != "$me" ]]; then why="runner $id was not started for $me"
  elif [[ ! $deadline =~ ^[0-9]+$ ]] || (( $(date +%s) > deadline )); then why="runner $id got its job after its lease"
  elif [[ ! $name =~ ^[a-z0-9][a-z0-9-]{0,23}$ ]] || [[ $id != "$name"-* ]] ||
       [[ "$(cat "/etc/factory-ci/dispatch-accounts/$me" 2>/dev/null)" != "$name" ]]; then why="$me does not serve $name"
  elif [[ "${GITHUB_REPOSITORY:-}" != "$(head -1 "/etc/factory-ci/dispatch/$name" 2>/dev/null)" ]]; then why="the job is not of the repository $name serves"
  elif [[ ! $run =~ ^[0-9]+$ ]] || [[ ! $attempt =~ ^[0-9]+$ ]] || [[ ! -f /run/factory-ci-trust/$name/$run-$attempt ]]; then why="run ${run:-?} attempt ${attempt:-?} was not admitted"
  fi
  if [[ -n $why ]]; then
    echo "::error::factory-ci: ${GITHUB_REPOSITORY:-?} run ${run:-?} attempt ${attempt:-?} refused: $why; its worker is killed before any step (decision 0080)"
    logger -t factory-ci "refused ${GITHUB_REPOSITORY:-?} run ${run:-?} attempt ${attempt:-?} on $me: $why"
    kill -KILL "$worker"
    exit 1
  fi
  echo "factory-ci: run $run attempt $attempt of $GITHUB_REPOSITORY admitted by the trusted dispatcher"
fi

# A job killed with the VM never ran job-completed: empty what it may have left before this one.
case "${GITHUB_WORKSPACE:-}" in
  "$HOME"/runner/_work/?*)
    if [[ -d $GITHUB_WORKSPACE ]] && [[ -n "$(ls -A "$GITHUB_WORKSPACE" 2>/dev/null)" ]]; then
      chmod -R u+rwX "$GITHUB_WORKSPACE" 2>/dev/null
      find "$GITHUB_WORKSPACE" -mindepth 1 -delete 2>/dev/null
      echo "factory-ci: emptied a workspace an interrupted job left behind"
    fi
    ;;
esac

started=$SECONDS last=-1
while :; do
  for i in $(seq 1 "$slots"); do
    rm -f "$ready"
    # setsid and no RUNNER_TRACKING_ID: the holder outlives this hook and is not reaped as a
    # job orphan; it exits with the worker, or when job-completed ends it.
    env -u RUNNER_TRACKING_ID setsid /opt/factory-ci/bin/slot-hold "$state/slot-$i.lock" "$worker" "$ready" "$i" \
      </dev/null >/dev/null 2>&1 &
    h=$!
    while kill -0 "$h" 2>/dev/null && [[ ! -s $ready ]]; do sleep 0.1; done
    if [[ -s $ready ]]; then
      echo "factory-ci: $(hostname) slot $i/$slots taken for $GITHUB_REPOSITORY run $GITHUB_RUN_ID after $((SECONDS - started))s"
      exit 0
    fi
  done
  if (( SECONDS - last >= 30 )); then
    last=$SECONDS
    echo "factory-ci: all $slots slot(s) busy, waiting ($((SECONDS - started))s):"
    cat "$state"/hold-* 2>/dev/null | awk '{print "  slot " $2 ": " $3 " run " $4 " since " $5}' || true
  fi
  sleep 2
done
