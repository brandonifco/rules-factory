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

# Every map carries a review of its exact bytes (0017): a blind second mapping, a verdict from a
# separate context, or an exemption that says why. The checker counts the maps it examined and
# fails on none, and prints every exemption, so neither an empty glob nor a waiver passes quietly.
check_map_reviews() {
  python3 tools/check-map-review.py
}

# A citation is a promise. Three grammars, three checkers: page markers for a Gutenberg text,
# containment in the section tree for eCFR XML, and page markers over PDF-extracted text held
# exactly. None generalises to the others, and pointing one at the wrong corpus exits 2 rather
# than passing.
check_locators() {
  python3 tools/check-locators.py \
    examples/hoyle-backgammon/corpus-map.json \
    examples/hoyle-backgammon/hoyle.txt || return 1
  python3 examples/faa-part-107/check-locators-section.py \
    examples/faa-part-107/corpus-map.json examples/faa-part-107/part107.xml || return 1
  python3 examples/faa-part-107/check-locators-section.py \
    examples/faa-part-107-temporal/corpus-map-2020-01-01.json \
    examples/faa-part-107-temporal/part107-2020-01-01.xml || return 1
  # A third corpus through the same eCFR checker, and a different title of the CFR: trial 9's
  # § 1.121-1. It is reused and not copied, which is the point -- the grammar is the grammar.
  # Two things in it were title-14 shaped and were generalised rather than duplicated: a
  # section's subpart is now read from its ancestry, so a single section served as a bare DIV8
  # indexes like one inside a subpart, and a section designation may carry a hyphenated suffix
  # (§ 1.121-1). tools/checkmap/extent.py carries the same expression, and test_check_map.py
  # holds the two to each other.
  python3 examples/faa-part-107/check-locators-section.py \
    examples/tax-121-principal-residence/corpus-map.json \
    examples/tax-121-principal-residence/section-1.121-1.xml || return 1
  # A third grammar: page markers over text extracted from a PDF. extract.py first holds the
  # committed text to the manifest's contentHash and the committed PDF to sourcePdf.sha256, and
  # re-derives the text from the PDF where the pinned pdftotext is installed (NOT VERIFIED,
  # printed, where it is not). The locator checker then holds each quote to the text.
  python3 examples/srd-52-combat/extract.py --check || return 1
  python3 examples/srd-52-combat/check-locators-pdf-text.py \
    examples/srd-52-combat/corpus-map.json examples/srd-52-combat/srd-5.2.1.txt || return 1
  # A second slice of the same corpus. The checker and the text stay where they were committed:
  # the conditions map declares its own manifest and points `committedPath` at that one copy,
  # because a 6 MB PDF and a 1.4 MB text duplicated per slice would be a second baseline to keep
  # in step, not a second corpus.
  python3 examples/srd-52-combat/check-locators-pdf-text.py \
    examples/srd-52-conditions/corpus-map.json examples/srd-52-combat/srd-5.2.1.txt || return 1
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
#
# tools/factory/recipe/ is skipped here and nowhere else: those files are not this repository's
# documents but the bytes an engine receives, and their links resolve against the engine's layout
# (AGENTS.md at its root, not in a recipe directory). Checking them here would compare a rail
# against the wrong tree. tools/tests/test_factory_rails.py checks them against the right one --
# skipping them without checking them somewhere is the failure this step exists to catch.
check_doc_references() {
  python3 - "$ROOT" <<'PY'
import pathlib, re, sys

root = pathlib.Path(sys.argv[1])
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")
# .claude/worktrees is where a worktree lands when one is made inside the repository. The rails
# warn that such a worktree is "scanned by a tool that did not expect it", and this is that tool:
# the rails copies under it resolve against an engine's layout, not this repository's, so they
# would all read as broken. git already ignores the directory; so does this.
IGNORED = {".git", "node_modules"}
IGNORED_PATHS = {root / ".claude" / "worktrees"}
RECIPE = root / "tools" / "factory" / "recipe"

broken = examined = 0
for md in sorted(root.rglob("*.md")):
    if any(part in IGNORED for part in md.parts) or RECIPE in md.parents:
        continue
    if any(ignored in md.parents for ignored in IGNORED_PATHS):
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

# The README's status table names every subcommand and argument the factory CLI takes, and marks
# what it does not take `not implemented` (#75). The checker imports the parser rather than
# grepping for flags, and fails on a table with no rows.
check_readme_status() {
  python3 tools/check-readme-status.py
}

# A README sentence that something is "not yet" or "not done" cites an open issue (#170). The prose
# beside #75's table drifted within days of it; this reads GitHub, fails when a state cannot be
# read, and says NOT CHECKED only when RULES_FACTORY_OFFLINE=1 asks it to.
check_status_issues() {
  python3 tools/check-status-issues.py
}

# CI runs on an exact Python patch and installs only hash-locked packages (#173). The runner and
# the actions were already pinned; a floating Python or pytest could change this gate's verdict
# with no commit here.
check_workflow_pins() {
  python3 tools/check-workflow-pins.py
}

# check-map.py ships as one file inside every map package, so it is built from tools/checkmap/
# rather than edited (#74). A module changed without rebuilding would ship, and be judged by,
# the checks as they were; every step after this one runs the built file.
run "check-map.py is what tools/checkmap/ builds"      python3 tools/build-check-map.py --check
run "every corpus map satisfies the schema"            check_all_maps
run "every corpus map carries a review of its bytes"   check_map_reviews
run "every citation resolves in its corpus"            check_locators
run "every map package passes its publish gate"        check_map_packages
run "the checkers' own tests"                          check_tool_tests
run "every repository link resolves"                   check_doc_references
run "every decision record is indexed"                 check_decision_index
run "every workflow pins its Python and its packages"  check_workflow_pins
run "the README's status table matches the factory CLI" check_readme_status
run "the README cites no closed issue as not yet done"  check_status_issues

printf '\n'
if [ "$failed" -ne 0 ]; then
  echo "validate.sh: FAIL"
  exit 1
fi
echo "validate.sh: PASS"
