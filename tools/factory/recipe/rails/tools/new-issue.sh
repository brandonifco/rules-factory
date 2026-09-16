#!/usr/bin/env bash
# new-issue.sh -- file an issue with the shape the rails expect.
#
#   tools/new-issue.sh --title "Widen the altitude limit to the tolerance case"
#   tools/new-issue.sh --title "..." --entry altitude-limit --risk independent --dry-run
#
# Emitted by rules-factory as a managed file (decision 0029).
#
# Most issues in an engine are not filed by hand: `factory backlog --create` writes one per map
# entry still to build, with the entry, its source, its dependencies and its acceptance criteria
# already in it. This is for the rest -- a defect, a piece of engine work, an upstream map defect
# -- so that an issue filed from a terminal by an agent and one filed by a person look the same
# six months later, and so that both carry exactly one state label and one risk label.
#
# Every issue starts at the ready state and normal risk. Promoting risk, or moving an issue to the
# awaiting-decision state, is the orchestrator's judgement (AGENTS.md section 6, docs/agent-team.md)
# and is done deliberately afterwards -- not asserted by whoever filed it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GH="${RULES_ENGINE_GH:-gh}"
POLICY=".github/agent-policy.json"

label() {
  python3 - "$POLICY" "$1" "$2" <<'PY' 2>/dev/null || printf '%s' "$3"
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        value = (json.load(handle).get("labels") or {}).get(sys.argv[2])
except Exception:
    value = None
print(value or sys.argv[3])
PY
}

TITLE=""
ENTRY=""
RISK="normal"
BODY_FILE=""
DRY_RUN=0
EXTRA_LABELS=()

die() { printf 'error: %s\n' "$1" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title) TITLE="${2:-}"; shift 2 ;;
    --entry) ENTRY="${2:-}"; shift 2 ;;
    --risk) RISK="${2:-}"; shift 2 ;;
    --body-file) BODY_FILE="${2:-}"; shift 2 ;;
    --label) EXTRA_LABELS+=("${2:-}"); shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,6p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -n "$TITLE" ]] || die "--title is required"
case "$RISK" in
  normal|independent) ;;
  *) die "--risk is normal or independent, got: $RISK" ;;
esac

READY="$(label ready "ready" "state:ready")"
if [[ "$RISK" == "independent" ]]; then
  RISK_LABEL="$(label independentRisk "independentRisk" "risk:independent-review")"
else
  RISK_LABEL="$(label normalRisk "normalRisk" "risk:normal")"
fi

MARKER=""
[[ -n "$ENTRY" ]] && MARKER="<!-- rules-factory-entry: $ENTRY -->

"

if [[ -n "$BODY_FILE" ]]; then
  [[ -f "$BODY_FILE" ]] || die "no such file: $BODY_FILE"
  BODY="$MARKER$(cat "$BODY_FILE")"
else
  BODY="$MARKER$(cat <<'TPL'
## What this is

<!-- One concern. If the sentence needs an "and", it is two issues. -->

## Why it exists

<!-- What becomes possible, or what is currently wrong. -->

## The rule, if this is rules work

<!-- The map entry id, and nothing quoted from the corpus that the map does not already quote.
     `tools/entry-packet.py <entry-id>` is the assignment; this section only needs to name it.
     If this is an upstream map defect: what the map says, what the corpus says, and the locator. -->

N/A

## Scope, and what it deliberately does not do

<!-- The non-goals are what keep the pull request reviewable. -->

## Acceptance criteria

<!-- Observable conditions. Someone other than the implementer must be able to check each one. -->

- [ ]

## Required evidence

<!-- What must be demonstrated, and how. Every test names the mutation that makes it fail.
     Where the corpus prints a finite table, the whole table is checked, not a sample. -->

## Dependencies

<!-- Issues or decision records this waits on. "None" is a valid answer. -->

None
TPL
)"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'title:  %s\nlabels: %s\n\n%s\n' "$TITLE" "$READY,$RISK_LABEL${EXTRA_LABELS[*]:+,$(IFS=,; printf '%s' "${EXTRA_LABELS[*]}")}" "$BODY"
  exit 0
fi

command -v "$GH" >/dev/null 2>&1 || die "$GH is required to file an issue"

ARGS=(issue create --title "$TITLE" --body "$BODY" --label "$READY" --label "$RISK_LABEL")
for extra in "${EXTRA_LABELS[@]+"${EXTRA_LABELS[@]}"}"; do
  ARGS+=(--label "$extra")
done
"$GH" "${ARGS[@]}"
