#!/usr/bin/env bash
# Criterion 4 of #3, from clean clones: every produced engine's committed provenance.json is
# true of the engine as it stands, checked by the factory at the version the engine records.
#
#   examples/acceptance-4-5/check-provenance.sh <work dir>
#
# For each engine it clones the repository, reads `factory.commit` out of its provenance.json,
# checks a clone of rules-factory out at that commit, and runs `factory provenance --engine`,
# which re-produces the engine in a scratch copy and names every field that does not match.
# Nothing is built, so no .NET SDK is needed; the map packages are fetched from nuget.org by
# `produce` itself when they are not already in the NuGet global packages folder.
#
# Exit 0 when every engine matches every field, 1 when any does not.
set -euo pipefail

ENGINES=(hoyle-backgammon faa-part-107 srd-52-combat hoyle-blind-rebuild)
WORK="${1:-}"
[ -n "$WORK" ] || { echo "usage: $0 <work dir>" >&2; exit 2; }
mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd)"

git clone -q https://github.com/brandonifco/rules-factory.git "$WORK/factory"

failed=0
for engine in "${ENGINES[@]}"; do
  printf '\n==> %s\n' "$engine"
  git clone -q "https://github.com/brandonifco/$engine.git" "$WORK/$engine"
  head="$(git -C "$WORK/$engine" rev-parse HEAD)"
  commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["factory"]["commit"])' "$WORK/$engine/provenance.json")"
  version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["factory"]["version"])' "$WORK/$engine/provenance.json")"
  dirty="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["factory"]["dirty"])' "$WORK/$engine/provenance.json")"
  echo "     engine at $head; produced by factory $version ($commit), dirty: $dirty"
  [ "$dirty" = "False" ] || { echo "     FAIL: the record says the factory was dirty"; failed=1; continue; }
  git -C "$WORK/factory" checkout -q "$commit"
  ( cd "$WORK/factory" && python3 tools/factory provenance --engine "$WORK/$engine" ) || failed=1
done

printf '\n'
[ "$failed" = 0 ] && echo "check-provenance.sh: PASS -- every engine's record is true of the engine" \
                  || echo "check-provenance.sh: FAIL -- see the mismatches above"
exit "$failed"
