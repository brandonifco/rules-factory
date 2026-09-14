#!/usr/bin/env bash
# The one definition of "acceptable" for this repository.
#
# This repo is documents plus the checkers that hold the documents to their word. Until now
# those checkers only ever ran on the author's machine, which is the failure the repo's own
# README describes in its predecessor: enforcement machinery shipped beside documents it
# cited and did not have.
#
# Every step below either proves something or says it could not. A step that reports ok
# while examining nothing is the defect this project has found in its own tools twice.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
failed=0
step=0

run() {
  local what="$1"; shift
  step=$((step + 1))
  printf '\n==> [%d] %s\n' "$step" "$what"
  if "$@"; then
    printf 'ok   %s\n' "$what"
  else
    printf 'FAIL %s\n' "$what"
    failed=1
  fi
}

# Every map, against the schema its own specification describes.
maps_checked=0
check_all_maps() {
  local map
  for map in examples/*/corpus-map*.json; do
    [ -e "$map" ] || continue
    printf -- '--- %s\n' "$map"
    python3 tools/check-map.py "$map" || return 1
    maps_checked=$((maps_checked + 1))
  done
  if [ "$maps_checked" -eq 0 ]; then
    echo "no corpus maps found -- this step proved nothing" >&2
    return 1
  fi
  printf '%d map(s) checked\n' "$maps_checked"
}

# A citation is a promise. Two grammars, two checkers: page markers for a Gutenberg text,
# containment in the section tree for eCFR XML. Neither generalises to the other, and
# pointing one at the wrong corpus exits 2 rather than passing.
check_locators() {
  python3 tools/check-locators.py \
    examples/hoyle-backgammon/corpus-map.json \
    examples/hoyle-backgammon/hoyle.txt || return 1
  python3 examples/faa-part-107/check-locators-section.py \
    examples/faa-part-107/corpus-map.json examples/faa-part-107/part107.xml || return 1
  python3 examples/faa-part-107/check-locators-section.py \
    examples/faa-part-107-temporal/corpus-map-2020-01-01.json \
    examples/faa-part-107-temporal/part107-2020-01-01.xml || return 1
}

# Every map that declares a package version passes the gate its publish workflow runs, and
# packs to the same bytes twice (0015). A map that could not be published is found here, on
# the pull request, rather than on the tag -- after the version number was already chosen.
check_map_packages() {
  local settings dir out packed=0 first second
  out="$(mktemp -d)"
  for settings in examples/*/map-package.json; do
    [ -e "$settings" ] || continue
    dir="$(dirname "$settings")"
    printf -- '--- %s\n' "$dir"
    python3 tools/pack-map.py "$dir" --out "$out/a" >"$out/log" 2>&1 || { cat "$out/log"; rm -rf "$out"; return 1; }
    tail -1 "$out/log"
    python3 tools/pack-map.py "$dir" --out "$out/b" >/dev/null 2>&1 || { rm -rf "$out"; return 1; }
    packed=$((packed + 1))
  done
  if [ "$packed" -eq 0 ]; then
    echo "no map declares map-package.json -- this step proved nothing" >&2
    rm -rf "$out"; return 1
  fi
  first="$(cd "$out/a" && sha256sum -- *.nupkg)"
  second="$(cd "$out/b" && sha256sum -- *.nupkg)"
  rm -rf "$out"
  if [ "$first" != "$second" ]; then
    printf 'two packs of the same inputs differ:\n%s\n%s\n' "$first" "$second" >&2
    return 1
  fi
  printf '%d map package(s) gated and packed, byte-identical twice\n' "$packed"
}

# The checkers' own tests. A checker nobody has watched fail is not yet a checker, and this
# repo has shipped two that counted work they had not done.
check_tool_tests() {
  local out
  out="$(python3 -m pytest tools/tests -q 2>&1)" || { printf '%s\n' "$out"; return 1; }
  printf '%s\n' "$out" | tail -1
  # A green pytest run over an empty suite is the same lie as a check with no inputs.
  printf '%s\n' "$out" | grep -qE '[0-9]+ passed' || {
    echo "pytest reported no passing tests -- nothing was proven" >&2; return 1; }
}

# Every markdown link to a file in this repository resolves. The predecessor repo shipped
# sixty-one references to files that did not exist, several inside runtime error messages.
check_doc_references() {
  python3 - "$ROOT" <<'PY'
import pathlib, re, sys

root = pathlib.Path(sys.argv[1])
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")
IGNORED = {".git", "node_modules"}

broken = examined = 0
for md in sorted(root.rglob("*.md")):
    if any(part in IGNORED for part in md.parts):
        continue
    for target in LINK.findall(md.read_text(encoding="utf-8", errors="replace")):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        examined += 1
        if not (md.parent / target).resolve().exists():
            broken += 1
            print(f"  X  {md.relative_to(root)} -> {target}")

if examined == 0:
    print("no repository-relative links found -- this check proved nothing", file=sys.stderr)
    sys.exit(1)
if broken:
    print(f"\n{broken} of {examined} repository links do not resolve")
    sys.exit(1)
print(f"{examined} repository link(s) resolve")
PY
}

# Every decision record is in the index, and every indexed record exists. Numbering is
# permanent here; a record that exists unindexed is one nobody finds.
check_decision_index() {
  python3 - "$ROOT" <<'PY'
import pathlib, re, sys

decisions = pathlib.Path(sys.argv[1], "docs", "decisions")
index = decisions / "README.md"
if not index.exists():
    print("docs/decisions/README.md is missing -- nothing to check", file=sys.stderr)
    sys.exit(1)

listed = set(re.findall(r"\((\d{4}-[^)]+\.md)\)", index.read_text(encoding="utf-8")))
on_disk = {p.name for p in decisions.glob("[0-9][0-9][0-9][0-9]-*.md")}
if not on_disk:
    print("no decision records found -- this check proved nothing", file=sys.stderr)
    sys.exit(1)

bad = False
for missing in sorted(on_disk - listed):
    print(f"  X  {missing} exists but is not in the index"); bad = True
for phantom in sorted(listed - on_disk):
    print(f"  X  {phantom} is indexed but does not exist"); bad = True
sys.exit(1 if bad else print(f"{len(on_disk)} decision record(s), all indexed") or 0)
PY
}

# check-map.py ships as one file inside every map package, so it is built from tools/checkmap/
# rather than edited (#74). A module changed without rebuilding would ship, and be judged by,
# the checks as they were; every step after this one runs the built file.
run "check-map.py is what tools/checkmap/ builds"      python3 tools/build-check-map.py --check
run "every corpus map satisfies the schema"            check_all_maps
run "every citation resolves in its corpus"            check_locators
run "every map package passes its publish gate"        check_map_packages
run "the checkers' own tests"                          check_tool_tests
run "every repository link resolves"                   check_doc_references
run "every decision record is indexed"                 check_decision_index

printf '\n'
if [ "$failed" -ne 0 ]; then
  echo "validate.sh: FAIL"
  exit 1
fi
echo "validate.sh: PASS"
