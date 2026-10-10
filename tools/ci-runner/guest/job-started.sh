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
# a one-job runner the host's dispatcher started, and only for a run it admitted, recorded where
# no runner account can write. Anything else stops here, before the job's first step: a runner
# that is not one of those, a run of another repository, or a run nobody admitted.
if [[ -e /etc/factory-ci/dispatch/$me ]]; then
  run="${GITHUB_RUN_ID:-}" attempt="${GITHUB_RUN_ATTEMPT:-}"
  exe="$(readlink "/proc/$worker/exe" 2>/dev/null || true)"
  if [[ $exe != "$HOME"/jit/*/bin/Runner.Worker ]] || [[ ! $run =~ ^[0-9]+$ ]] || [[ ! $attempt =~ ^[0-9]+$ ]] ||
     [[ "${GITHUB_REPOSITORY:-}" != "$(cat "/etc/factory-ci/dispatch/$me")" ]] ||
     [[ ! -f /run/factory-ci-trust/$me/$run-$attempt ]]; then
    echo "::error::factory-ci: run ${run:-?} attempt ${attempt:-?} of ${GITHUB_REPOSITORY:-?} was not admitted by the trusted dispatcher; refused before its first step (decision 0080)"
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
