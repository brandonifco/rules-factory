#!/usr/bin/env bash
# dispatch-agent.sh -- one issue, one worktree, one branch.
#
#   tools/dispatch-agent.sh 42              create a worktree for issue #42
#   tools/dispatch-agent.sh --cleanup 42    remove it after the pull request merged
#   tools/dispatch-agent.sh --sweep         remove every worktree and branch whose PR merged
#   tools/dispatch-agent.sh --list          show live worktrees
#
# Emitted by rules-factory as a managed file (decision 0029). AGENTS.md section 4 is the rule this
# implements; the labels and the worktree root are read from .github/agent-policy.json, which the
# engine owns.
#
# The primary checkout is for orchestration, and its steady state is: on main, clean. Implementation
# in the primary checkout produces a repository where nobody can tell which change belongs to which
# issue, and where two agents working at once corrupt each other's tree.
#
# Worktrees live OUTSIDE the repository. One inside it eventually gets committed, scanned by a tool
# that did not expect it, or deleted by a clean step.
#
# Dispatch refuses work that is not ready, rather than leaving that to an agent's judgement: an
# issue that is closed, blocked, or awaiting a decision, one that already has a worktree, and a
# primary checkout with uncommitted changes.
#
# Cleaning up is not left to anyone's memory either. `--cleanup <n>` is one issue, run by hand;
# `--sweep` removes everything merged work left behind, and every dispatch runs it first, so a
# repository that dispatches at all stays clean without anybody deciding to tidy up.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GH="${RULES_ENGINE_GH:-gh}"
POLICY=".github/agent-policy.json"

# One label vocabulary, read from the engine's own policy. A script that hard-codes `state:ready`
# is a script a consumer has to edit to rename a label, which is what 0029 puts in the policy to
# avoid.
label() {
  python3 - "$POLICY" "$1" <<'PY' 2>/dev/null || true
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        print((json.load(handle).get("labels") or {}).get(sys.argv[2], ""))
except Exception:
    print("")
PY
}

WORKTREE_ROOT_VARIABLE="$(python3 - "$POLICY" <<'PY' 2>/dev/null || true
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        print((json.load(handle).get("worktrees") or {}).get("rootEnvironmentVariable") or "RULES_ENGINE_WORKTREE_ROOT")
except Exception:
    print("RULES_ENGINE_WORKTREE_ROOT")
PY
)"
[[ -n "$WORKTREE_ROOT_VARIABLE" ]] || WORKTREE_ROOT_VARIABLE="RULES_ENGINE_WORKTREE_ROOT"
WORKTREE_ROOT="${!WORKTREE_ROOT_VARIABLE:-$HOME/rules-engine-worktrees/$(basename "$REPO_ROOT")}"

BLOCKED="$(label blocked)";        BLOCKED="${BLOCKED:-state:blocked}"
NEEDS_DECISION="$(label needsDecision)"; NEEDS_DECISION="${NEEDS_DECISION:-state:needs-decision}"
READY="$(label ready)";            READY="${READY:-state:ready}"

if [[ -t 1 ]]; then BOLD=$'\033[1m'; RED=$'\033[31m'; GRN=$'\033[32m'; OFF=$'\033[0m'
else BOLD=""; RED=""; GRN=""; OFF=""; fi

die() { printf '%serror%s %s\n' "$RED" "$OFF" "$1" >&2; exit 1; }

usage() {
  sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

assert_primary_checkout() {
  local common dir
  common="$(git rev-parse --git-common-dir)"
  dir="$(git rev-parse --git-dir)"
  [[ "$common" == "$dir" ]] || die "run this from the primary checkout, not a worktree"
}

# A dirty primary checkout is either someone implementing where they should not be, or a half-done
# orchestration. Either way the new worktree would be based on a tree nobody has looked at.
assert_primary_checkout_is_clean() {
  local dirty
  dirty="$(git status --porcelain)"
  [[ -z "$dirty" ]] || die "the primary checkout has uncommitted changes:
$(printf '%s\n' "$dirty" | sed 's/^/         /')
       Its steady state is main, clean (AGENTS.md section 4). Commit, stash or discard first."
}

assert_worktree_root_is_outside_repo() {
  local resolved
  resolved="$(mkdir -p "$WORKTREE_ROOT" 2>/dev/null; cd "$WORKTREE_ROOT" 2>/dev/null && pwd -P)" || {
    printf 'error: cannot create worktree root: %s\n' "$WORKTREE_ROOT" >&2; exit 1; }
  case "$resolved/" in
    "$REPO_ROOT"/*)
      printf 'error: %s resolves inside the repository:\n' "$WORKTREE_ROOT_VARIABLE" >&2
      printf '         %s\n       repo: %s\n\n' "$resolved" "$REPO_ROOT" >&2
      printf '       Worktrees live outside the repository: one inside it eventually gets committed,\n' >&2
      printf '       scanned by a tool that did not expect it, or deleted by a clean step.\n' >&2
      exit 1
      ;;
  esac
}

slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -e 's/[^a-z0-9]\+/-/g' -e 's/^-\+//' -e 's/-\+$//' \
    | cut -c1-40 \
    | sed -e 's/-\+$//'
}

do_list() {
  printf '%sLive worktrees%s\n' "$BOLD" "$OFF"
  git worktree list | sed 's/^/  /'
}

do_cleanup() {
  local issue="$1" found=0 path branch
  while read -r path _; do
    [[ "$path" == "$REPO_ROOT" ]] && continue
    if [[ "$(basename "$path")" == issue-"$issue"-* ]]; then
      found=1
      git worktree remove "$path" 2>/dev/null \
        || die "worktree has uncommitted changes: $path
       Inspect it, then force with: git worktree remove --force '$path'"
      printf '%sremoved%s %s\n' "$GRN" "$OFF" "$path"
    fi
  done < <(git worktree list --porcelain | awk '/^worktree /{print $2}')
  [[ "$found" -eq 1 ]] || die "no worktree found for issue #$issue"
  git worktree prune

  branch="$(git branch --list "issue-$issue-*" --format='%(refname:short)' | head -1)"
  if [[ -n "$branch" ]]; then
    if git branch -d "$branch" 2>/dev/null; then
      printf '%sdeleted%s branch %s (it was merged)\n' "$GRN" "$OFF" "$branch"
    else
      printf 'branch %s kept: it is not merged into main.\n' "$branch"
      printf 'Delete it deliberately with: git branch -D %s\n' "$branch"
    fi
  fi
}

# The merged pull requests of this repository, as "branch<TAB>head-commit" lines. The newest
# SWEEP_LIMIT of them: a worktree left behind by merged work is recent by definition, and a cap
# that misses an older one costs a leftover that is reported next time, never a wrong removal.
SWEEP_LIMIT=500

sweep_pulls() {
  "$GH" pr list --state merged --limit "$SWEEP_LIMIT" --json headRefName,headRefOid \
    | python3 -c 'import json, sys
for row in json.load(sys.stdin) or []:
    print(row["headRefName"] + "\t" + row["headRefOid"])'
}

# Every registered worktree, the primary included, as "path<TAB>HEAD<TAB>ref" (ref empty when
# detached). git prints these as a stanza per worktree; awk flushes on the next one and at the end
# rather than on the blank line between them, so a listing that ends without one still reports.
registered_worktrees() {
  git worktree list --porcelain | awk '
    /^worktree /  { if (path != "") print path "\t" head "\t" ref; path = substr($0, 10); head = ""; ref = "" }
    /^HEAD /      { head = substr($0, 6) }
    /^branch /    { ref  = substr($0, 8) }
    END           { if (path != "") print path "\t" head "\t" ref }'
}

# --sweep: everything merged work left behind, removed at exactly its tip and nothing else.
#
# **The rule is the one rules-factory holds itself to** (its tools/repo-hygiene.py, which is not
# vendored here): a worktree or a branch is finished when a pull request merged at EXACTLY its tip.
# Not "its commits are in main" -- a worktree dispatched a minute ago and never committed in is on
# a branch whose tip is main's tip, so that weaker rule removes the work of an agent who has not
# started. Not "its branch was merged once" -- a worktree committed to since its pull request
# merged is somebody working in it now.
#
# And never a dirty one. Uncommitted or untracked files are either work nobody has looked at or a
# build output nobody expected; both are named and left where they are.
#
# What cannot be read is not called clean: with `gh` unavailable or refusing, this says NOT CHECKED
# and exits 3 rather than reporting an empty sweep, because "nothing had merged" and "I could not
# ask" leave exactly the same repository behind.
do_sweep() {
  local pulls why="" readable=1 path head ref branch name sha checked_out
  local swept_trees=0 swept_branches=0 kept=0 trees=0 branches=0

  pulls="$(mktemp "${TMPDIR:-/tmp}/dispatch-agent-sweep.XXXXXX")"
  if ! command -v "$GH" >/dev/null 2>&1; then
    why="$GH is not installed"; readable=0
  elif ! why="$(sweep_pulls 2>&1 >"$pulls")"; then
    why="${why:-$GH pr list --state merged failed}"; readable=0
  fi
  if [[ "$readable" -eq 0 ]]; then
    rm -f "$pulls"
    printf 'NOT CHECKED  merged pull requests could not be read (%s).\n' "$why"
    printf '             Nothing was swept, and a worktree or branch left behind by merged work is not reported by this run.\n'
    return 3
  fi

  while IFS=$'\t' read -r path head ref; do
    [[ "$path" == "$REPO_ROOT" ]] && continue
    trees=$((trees + 1))
    branch="${ref#refs/heads/}"
    # A detached worktree belongs to a review or a bisect, not to an issue, and no pull request
    # names it. Nothing here can prove it is finished, so nothing here touches it.
    [[ -n "$branch" ]] || continue
    grep -Fqx "$branch$(printf '\t')$head" "$pulls" || continue
    if [[ -n "$(git -C "$path" status --porcelain --untracked-files=all 2>/dev/null)" ]]; then
      printf 'kept     %s (%s): it has uncommitted or untracked files; look at them before removing it\n' \
        "$path" "$branch"
      kept=$((kept + 1))
      continue
    fi
    if git worktree remove "$path" >/dev/null 2>&1; then
      printf 'swept    %s (%s, its pull request merged at this tip)\n' "$path" "$branch"
      swept_trees=$((swept_trees + 1))
    else
      printf 'kept     %s (%s): git worktree remove refused it; inspect it before forcing\n' "$path" "$branch"
      kept=$((kept + 1))
    fi
  done < <(registered_worktrees)
  git worktree prune

  # Re-read after the removals: a branch a surviving worktree has checked out is that worktree's,
  # and the primary checkout's own branch is in this list too, which is how `main` is spared
  # without naming it.
  checked_out="$(registered_worktrees | cut -f3)"
  while read -r name sha; do
    branches=$((branches + 1))
    if printf '%s\n' "$checked_out" | grep -Fqx "refs/heads/$name"; then
      continue
    fi
    grep -Fqx "$name$(printf '\t')$sha" "$pulls" || continue
    # update-ref with the expected old value, never `git branch -d`: -d judges "merged" against
    # the local main, which may be behind the remote, and what proves this branch finished is the
    # pull request at exactly this commit -- the same proof the worktrees above are judged by.
    if git update-ref -d "refs/heads/$name" "$sha" 2>/dev/null; then
      printf 'swept    branch %s (its pull request merged at this tip)\n' "$name"
      swept_branches=$((swept_branches + 1))
    else
      printf 'kept     branch %s: git refused to delete it at %s\n' "$name" "${sha:0:12}"
      kept=$((kept + 1))
    fi
  done < <(git for-each-ref --format='%(refname:short) %(objectname)' refs/heads)

  rm -f "$pulls"
  if [[ $((swept_trees + swept_branches)) -gt 0 ]]; then
    printf 'sweep: removed %d worktree(s) and %d branch(es) whose pull request merged at their tip\n' \
      "$swept_trees" "$swept_branches"
  elif [[ "$kept" -eq 0 ]]; then
    printf 'sweep: nothing to remove; %d worktree(s) and %d branch(es) examined, none finished by a merged pull request at its tip\n' \
      "$trees" "$branches"
  fi
  if [[ "$kept" -gt 0 ]]; then
    printf 'sweep: %d finished worktree(s) or branch(es) kept and named above; each is somebody to ask, not this command to decide\n' "$kept"
    return 1
  fi
  return 0
}

do_create() {
  local issue="$1" title state labels branch path base

  assert_primary_checkout_is_clean
  assert_worktree_root_is_outside_repo
  # Every dispatch starts clean, so that cleaning up is nobody's to remember. The exit code is
  # deliberately ignored: a sweep that could not reach GitHub, or that found a worktree somebody
  # is still working in, says so above and must not stop the next issue from being dispatched.
  do_sweep || true
  command -v "$GH" >/dev/null 2>&1 || die "$GH is required: work starts from an issue, and this checks the issue exists"

  if ! title="$("$GH" issue view "$issue" --json title --jq .title 2>/dev/null)"; then
    die "issue #$issue does not exist or is not visible.
       Work starts from an issue. File one first: GitHub is the only queue (AGENTS.md section 4)."
  fi
  state="$("$GH" issue view "$issue" --json state --jq .state)"
  labels="$("$GH" issue view "$issue" --json labels --jq '[.labels[].name] | join(",")')"

  [[ "$state" == "OPEN" ]] || die "issue #$issue is $state. Reopen it, or pick another."

  if [[ ",$labels," == *",$NEEDS_DECISION,"* ]]; then
    die "issue #$issue is $NEEDS_DECISION, and is not implementable.
       An implementation agent may not resolve the open question itself (AGENTS.md section 6).
       The answer is the owner's, recorded as a ruling or a decision record; then the label moves."
  fi
  if [[ ",$labels," == *",$BLOCKED,"* ]]; then
    die "issue #$issue is $BLOCKED: something it depends on is not built yet.
       Work that dependency first, or re-run the backlog sync if it is already done."
  fi

  branch="issue-$issue-$(slugify "$title")"
  path="$WORKTREE_ROOT/$branch"
  [[ -e "$path" ]] && die "a worktree for this issue already exists: $path
       Finish it, or clean it up first:  tools/dispatch-agent.sh --cleanup $issue"

  # Base on the freshest origin/main visible, but never fail because the network is down: an
  # offline agent should still get a worktree, told what it is based on.
  base="main"
  if git remote get-url origin >/dev/null 2>&1 && git fetch -q origin main 2>/dev/null; then
    base="origin/main"
  else
    printf 'note: could not fetch origin; basing on local main\n' >&2
  fi

  mkdir -p "$WORKTREE_ROOT"
  # `git worktree add -b` creates the branch and checks it out IN THE WORKTREE. The primary
  # checkout is never moved off main by this command.
  git worktree add -b "$branch" "$path" "$base" >/dev/null

  printf '\n%sWorktree ready%s\n' "$BOLD$GRN" "$OFF"
  printf '  issue    #%s  %s\n' "$issue" "$title"
  printf '  labels   %s\n' "${labels:-none}"
  printf '  branch   %s\n' "$branch"
  printf '  path     %s\n' "$path"
  printf '  base     %s\n\n' "$base"
  printf 'Work there, not here:\n  cd %s\n\n' "$path"
  printf 'The entry this issue names, as the map has it:\n  tools/entry-packet.py <entry-id>\n\n'
  # The re-produce comes first, and is printed whether or not this issue's work will touch the
  # overlay (#202). Marking an entry `implemented` edits corpus-map.overlay.json, and since #192
  # the gate's provenance step fails by design while the record is older than the overlay,
  # so the gate alone is an order no entry implementation can follow. Unconditional rather than
  # guessed: a re-produce on an unchanged overlay writes nothing, and dispatch cannot know what the
  # work will touch before it is done.
  printf 'Before opening the pull request:\n'
  printf '  tools/re-produce.sh          # an overlay change is finished by a re-produce\n'
  printf '  ./scripts/validate.sh full   # the gate, whole, after the record is current\n'
  printf 'The pull request must say:  Closes #%s\n' "$issue"
}

[[ $# -eq 0 ]] && usage 1

case "${1:-}" in
  -h|--help) usage 0 ;;
  --list) assert_primary_checkout; do_list ;;
  --sweep)
    [[ $# -eq 1 ]] || die "usage: dispatch-agent.sh --sweep  (it takes no argument; --cleanup <n> is the one-issue form)"
    assert_primary_checkout; do_sweep ;;
  --cleanup)
    [[ $# -eq 2 ]] || die "usage: dispatch-agent.sh --cleanup <issue-number>"
    [[ "$2" =~ ^[0-9]+$ ]] || die "issue number must be numeric, got: $2"
    assert_primary_checkout; do_cleanup "$2" ;;
  *)
    [[ "$1" =~ ^[0-9]+$ ]] || die "issue number must be numeric, got: $1"
    assert_primary_checkout; do_create "$1" ;;
esac
