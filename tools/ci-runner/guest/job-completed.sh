#!/bin/bash
# job-completed -- the runner's ACTIONS_RUNNER_HOOK_JOB_COMPLETED on a factory-ci guest.
# Empties the job's workspace (no build output or checkout survives into the next job; the
# runner itself clears _temp) and gives back the job slot job-started took.
set -uo pipefail
me="$(id -un)"
for d in "${GITHUB_WORKSPACE:-}" "${RUNNER_TEMP:-}"; do
  case "$d" in
    "$HOME"/runner/_work/?*)
      chmod -R u+rwX "$d" 2>/dev/null
      find "$d" -mindepth 1 -delete 2>/dev/null || echo "::warning::factory-ci: could not empty $d"
      ;;
  esac
done
if read -r pid slot _ <"/run/factory-ci/hold-$me" 2>/dev/null; then
  kill "$pid" 2>/dev/null
  rm -f "/run/factory-ci/hold-$me"
  echo "factory-ci: slot $slot released"
fi
exit 0
