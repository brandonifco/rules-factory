#!/bin/bash
# jit-run -- ExecStart of a one-job factory-ci runner (dispatch-guest start, decision 0080), run as
# the repository's account in the runner's own directory. The JIT configuration is that runner's
# whole credential: it is read into the listener's input variable, which the listener clears from
# its environment, and its file is gone before the listener starts, so no job can read it back.
set -euo pipefail
ACTIONS_RUNNER_INPUT_JITCONFIG="$(cat .jitconfig)"
export ACTIONS_RUNNER_INPUT_JITCONFIG
rm -f .jitconfig
exec ./run.sh
