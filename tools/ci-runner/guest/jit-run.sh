#!/bin/bash
# jit-run -- ExecStart of a one-job factory-ci runner (dispatch-guest start, decision 0080), run as
# the repository's account in the runner's own directory. The JIT configuration is that runner's
# credential for its one job. Its file is gone before the listener starts; the value stays readable
# in this process's environment by the same account, which is the job's own account and nothing
# else's (an account has one runner at a time, and ProtectProc hides other accounts' processes),
# exactly as any self-hosted runner's credential is readable by the job it runs.
set -euo pipefail
ACTIONS_RUNNER_INPUT_JITCONFIG="$(cat .jitconfig)"
export ACTIONS_RUNNER_INPUT_JITCONFIG
rm -f .jitconfig
exec ./run.sh
