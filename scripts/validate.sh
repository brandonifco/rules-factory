#!/usr/bin/env bash
# The one definition of "acceptable" for this repository, at its widest scope.
#
# This repo is documents plus the checkers that hold the documents to their word. Until this
# script existed those checkers only ever ran on the author's machine, which is the failure the
# repo's own README describes in its predecessor: enforcement machinery shipped beside documents
# it cited and did not have.
#
# The steps moved to tools/validate-repo.py (#342), which can also answer a narrower question --
# what a diff owes, what a release owes -- and this stayed, because `./scripts/validate.sh` is
# what AGENTS.md section 2 names, what CI runs, and what is in every contributor's shell history.
# It passes --full and nothing else: full is the whole list, over every map, and a caller who
# wants less has to say so in the orchestrator's own words rather than by editing this.
#
# Every step there either proves something or says it could not. A step that reports ok while
# examining nothing is the defect this project has found in its own tools twice.
set -euo pipefail

cd "$(dirname "$0")/.."
exec python3 tools/validate-repo.py --full "$@"
