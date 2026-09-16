#!/usr/bin/env bash
# The factory's output, held to the same standard as the factory: produce an engine from
# scratch, then prove it restores, builds warning-free, passes its generated tests, and
# recomputes to the provenance it records.
#
# This is the entry point CI (.github/workflows/validate.yml) and people call, with the same
# arguments (--print-sdk) and environment (FACTORY_DOTNET_SDK_OVERRIDE, refused when CI=true) as
# ever. What it checks, in what order, and why each check exists is in tools/validate-engine.py,
# which this runs: 45 KB of shell was an application in a language with weak structure, error
# handling and testability (#172). A missing or wrong SDK is still a failure there, never a skip.
set -euo pipefail

VALIDATE_ENGINE_ARGV0="$0" exec python3 "$(dirname "$0")/../tools/validate-engine.py" "$@"
