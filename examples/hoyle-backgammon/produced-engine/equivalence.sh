#!/usr/bin/env bash
# Is hoyle-backgammon the factory's output, or files added to a hand-built repository? (#3, criterion 2)
#
#   examples/hoyle-backgammon/produced-engine/equivalence.sh <engine sha> [factory ref]
#
# Clones brandonifco/hoyle-backgammon at <engine sha> ($ENGINE_REPO overrides the URL), checks out
# the factory at [factory ref] (default factory/v0.4.1) in a scratch git worktree, and requires that
# ref to be the commit the engine's provenance.json names. Then, with the package and engine name
# that provenance.json records and the engine's own corpus copy:
#
#   1. produces the engine from scratch into an empty directory ("bare");
#   2. produces it again into an empty directory holding only the engine's corpus-map.overlay.json
#      ("seeded"), the one engine-owned file generation reads, since the generated files are
#      merge(package map, overlay);
#   3. classifies every difference with that factory's own ownership table (classify.py): every
#      generated file byte-identical, every managed file identical, provenance.json differing only
#      in buildInputs and engineOwned with each item explained, everything else engine-owned;
#   4. runs `factory provenance --engine` on the clone, which re-produces it and names every field
#      that does not match.
#
# Both produces pass --no-verify: whether the engine builds and its tests pass is the engine's own
# CI, and verify needs the SDK the kernel pins. The question here is only whether the committed
# files are what the factory writes.
#
# Not run by scripts/validate.sh or CI: it needs the network (GitHub, and nuget.org unless the
# package is in the NuGet cache) and a published package. Its recorded output is EVIDENCE.md.
# Exit 0 when every difference is engine-owned and provenance matches; 1 otherwise; 2 on usage.
# Standard library and git only.
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 <engine sha> [factory ref, default factory/v0.4.1]" >&2
  exit 2
fi
ENGINE_SHA="$1"
FACTORY_REF="${2:-factory/v0.4.1}"
ENGINE_REPO="${ENGINE_REPO:-https://github.com/brandonifco/hoyle-backgammon}"

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(git -C "$HERE" rev-parse --show-toplevel)"
WORK="$(mktemp -d)"
cleanup() {
  git -C "$ROOT" worktree remove --force "$WORK/factory" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

step() { printf '\n==> %s\n' "$1"; }
json() { python3 -c 'import json, sys; d = json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."): d = d[k]
print(d)' "$1" "$2"; }

step "engine $ENGINE_REPO at $ENGINE_SHA"
git init -q "$WORK/engine"
git -C "$WORK/engine" fetch -q --depth 1 "$ENGINE_REPO" "$ENGINE_SHA"
git -C "$WORK/engine" checkout -q FETCH_HEAD
ENGINE_HEAD="$(git -C "$WORK/engine" rev-parse HEAD)"
echo "engine commit    $ENGINE_HEAD"
if [ "$ENGINE_HEAD" != "$ENGINE_SHA" ]; then
  echo "fetched $ENGINE_HEAD, not $ENGINE_SHA (pass the full 40-character sha)" >&2
  exit 1
fi

PROV="$WORK/engine/provenance.json"
NAME="$(json "$PROV" engine.name)"
PACKAGE="$(json "$PROV" map.packageId)@$(json "$PROV" map.version)"
RECORDED_FACTORY="$(json "$PROV" factory.commit)"
echo "engine name      $NAME"
echo "package          $PACKAGE"
echo "factory recorded $(json "$PROV" factory.version) at $RECORDED_FACTORY"

corpora=("$WORK"/engine/corpus/*)
if [ "${#corpora[@]}" -ne 1 ] || [ ! -f "${corpora[0]}" ]; then
  echo "the engine's corpus/ does not hold exactly one file -- nothing to produce from" >&2
  exit 1
fi
CORPUS="${corpora[0]}"
echo "corpus           corpus/$(basename "$CORPUS") sha256 $(sha256sum "$CORPUS" | cut -d' ' -f1)"

step "factory at $FACTORY_REF"
git -C "$ROOT" rev-parse -q --verify "$FACTORY_REF^{commit}" >/dev/null || git -C "$ROOT" fetch -q --tags origin
git -C "$ROOT" worktree add -q --detach "$WORK/factory" "$FACTORY_REF"
FACTORY_HEAD="$(git -C "$WORK/factory" rev-parse HEAD)"
echo "factory commit   $FACTORY_HEAD"
if [ "$FACTORY_HEAD" != "$RECORDED_FACTORY" ]; then
  echo "$FACTORY_REF is not the factory commit the engine's provenance.json records" >&2
  exit 1
fi

produce() {
  (cd "$WORK/factory" && python3 tools/factory produce --package "$PACKAGE" --corpus "$CORPUS" \
    --name "$NAME" --out "$1" --no-verify) >"$WORK/$(basename "$1").log" 2>&1 \
    || { cat "$WORK/$(basename "$1").log"; return 1; }
  tail -1 "$WORK/$(basename "$1").log" | sed "s|$WORK|\$WORK|g"
}

step "produce from scratch into an empty directory (bare)"
mkdir "$WORK/bare"
produce "$WORK/bare"

step "produce into an empty directory holding only the engine's overlay (seeded)"
mkdir "$WORK/seeded"
cp "$WORK/engine/corpus-map.overlay.json" "$WORK/seeded/"
produce "$WORK/seeded"

status=0
step "classify every difference by the factory's ownership table"
python3 "$HERE/classify.py" --factory "$WORK/factory" --engine "$WORK/engine" --name "$NAME" \
  --bare "$WORK/bare" --seeded "$WORK/seeded" | sed "s|$WORK|\$WORK|g" || status=1

step "factory provenance --engine"
(cd "$WORK/factory" && python3 tools/factory provenance --engine "$WORK/engine") 2>&1 \
  | sed "s|$WORK|\$WORK|g" || status=1

printf '\n'
if [ "$status" -ne 0 ]; then
  echo "equivalence.sh: FAIL"
  exit 1
fi
echo "equivalence.sh: PASS"
