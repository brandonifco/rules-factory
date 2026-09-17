# AGENTS.md — how work on rules-factory is done

**This file governs every agent, and every person, changing this repository.** Read it before
your first action. `CLAUDE.md` points here and states no rule of its own.

It is not the contract a produced engine ships with. That one is
[`tools/factory/recipe/rails/AGENTS.md`](tools/factory/recipe/rails/AGENTS.md), and it governs
work on an engine. What this repository is, and what is true about it today, is in the
[README](README.md).

Each rule below names the check that enforces it, or says plainly that it rests on your word. On
2026-09-17 this repository held 79 merged local branches, 9 finished worktrees, 59 merged branches
on GitHub and an untagged P0 fix. Each was harmless on the day it was left, and no rule had a
check.

---

## 1. The steady state

The primary checkout is on `main`, clean, and level with `origin/main`. No branch, worktree or
cache outlives the work it was made for.

```bash
python3 tools/repo-hygiene.py          # report leftovers; exit 1 when there are any
python3 tools/repo-hygiene.py --fix    # remove what is provably finished
```

`--fix` only removes what is finished: a branch whose commits are already in `origin/main`, a
worktree whose pull request merged at exactly its tip, a clean detached worktree more than a day
old. It never forces anything, never deletes on GitHub without `--remote`, and never tags. It
reports what it will not touch and why. For Claude Code, `.claude/settings.json` runs `--fix` at
the start of every session, so a session starts from the steady state or is told why it cannot.

## 2. One change: an issue, a branch, a worktree, a pull request

- The work has an issue. A finding outside the change is a new issue, not a second commit.
- The branch is named for what becomes true, in words: `produce-stays-inside-out`, not `fix-183`.
- Implementation happens in a worktree, never the primary checkout, and never in a shared scratch
  directory. Claude Code's isolated agents get one under `.claude/worktrees/`, which git and
  `validate.sh` both ignore; a worktree you make yourself goes there too. The engine rails put
  worktrees outside the repository instead, because an engine's tools were not written to skip
  one; this repository's were, and Claude Code's isolation chooses the location.
- Commit as you go. Work that exists only in a working tree is one mistaken delete from gone.
- The pull request says `Closes #N` for each issue it finishes, and nothing it does not.
- `./scripts/validate.sh` passes locally before the pull request is opened. CI runs it again, with
  the engine job, and both are required checks on `main`.
- A test is watched failing. The pull request names the mutation that made each new test fail.

## 3. Every pull request checks all documentation

A change that makes a document untrue is not finished, and most of what makes one untrue is not
something a parser can see. So every pull request description carries a `## Documentation`
section with a line for **every living document** in the repository:

```markdown
- [x] `docs/method.md` — updated: phase 3 names the bound category
- [x] `README.md` — checked, no change: the status table does not describe map checks
```

```bash
python3 tools/check-pr-docs.py --skeleton     # the section for your diff, to complete
python3 tools/check-pr-docs.py --pr <number>  # what CI will say
```

"Checked" means read against the change, and the note says what you looked for. The
`documentation` check ([`tools/check-pr-docs.py`](tools/check-pr-docs.py), run by
`.github/workflows/documentation.yml`) fails a pull request that leaves a living document out,
calls a changed document unchanged, or claims an update the diff does not contain. It cannot tell
whether anyone read a file. That part rests on your word, and the note is where you give it.

Living means every tracked `*.md` except numbered decision records and trial evidence under
`examples/<trial>/`, which record what was decided or what happened and are superseded rather
than rewritten. A changed frozen document is still listed, as `updated`.

What `validate.sh` already holds mechanically, on every run: every repository link resolves,
every decision record is indexed, the README's CLI table matches the parser, and no README
sentence says something is not done, not passed or open while citing a closed issue.

## 4. Finishing is part of the work

An operation is not done until what it made for itself is gone, and **only** what it made for
itself. Report completion only after:

- **A merged pull request.** Run `python3 tools/repo-hygiene.py --fix`. It removes the worktree
  and the local branch, and fast-forwards `main`. GitHub deletes the head branch on merge.
- **A closed or abandoned pull request.** Delete its branch deliberately (`git branch -D`, and on
  GitHub). `repo-hygiene.py` names unmerged branches and leaves them, because only a person knows
  they are abandoned.
- **A review, a reproduction, or a scratch file.** Remove each thing you created, by its exact
  path, before reporting the result: `git worktree remove <path>`, `rm -r <the directory you
  made>`.
- **A test or a checker run.** Nothing is left in the checkout. `validate.sh` writes no bytecode
  and no pytest cache, and its last step fails when a run added an untracked or ignored file. A
  test that needs files uses its own temporary directory and removes it.
- **A background agent.** Its brief says to clean up after itself under this section, and the
  orchestrator runs `repo-hygiene.py --fix` after merging its pull request.

**Never delete by wildcard in a directory you share.** A session's scratch directory is shared by
every agent that session starts. On 2026-09-17 an agent tidying up ran `rm -rf <scratchpad>/*`,
took two worktrees and uncommitted work that were not its own, and the work had to be rebuilt.
Before an `rm` outside your own worktree, list what it will remove, and name each path.

## 5. Releases

The factory is released by an annotated tag, `factory/vX.Y.Z`, on a commit of `origin/main` whose
CI is green. Provenance records the tag's version, so an untagged commit produces engines that say
`0.0.0-dev+<commit>`. The message names the merged pull requests since the previous tag.

```bash
git tag -a factory/vX.Y.Z -m "<summary>" <commit>
git push origin factory/vX.Y.Z
```

- **When one is due.** When an issue labelled `review*-p0` or `review*-p1` has closed since the
  last tag and `tools/factory/` has changed since it. `repo-hygiene.py` reports `release` until
  the tag exists. Before 1.0, a release that only fixes is a patch; anything else is a minor.
- **What `factory/v1.0.0` requires.** No open issue labelled `review*-p0`. An independent review
  of the release candidate (§6), with every finding filed. A human review is recommended as well
  (#169).
- **Maps** are released separately, by `map/<name>/vX.Y.Z`, which `publish-map.yml` publishes to
  nuget.org. A map whose `map-package.json` declares a version with no tag is reported as `map`.
  Publishing cannot be undone, so that tag is a person's decision.

## 6. Independent review

The factory's trust boundaries are reviewed from outside, by a different model family, because
the implementation and its tests share assumptions (#169). The reviewer is OpenAI Codex, run
read-only against a detached worktree pinned to the commit under review, and given no earlier
review's conclusions.

Each finding is verified against the code, and reproduced where it can be, before it is filed.
Issues are labelled `reviewN-pX` for the round ([docs/backlog.md](docs/backlog.md)), and each
says where it falls in the round's ordered list. When the findings are filed, the pinned worktree
is removed (§4).

## 7. Where the rest lives

| Question | Answer |
|---|---|
| How a corpus is mapped | [docs/method.md](docs/method.md) |
| What a map is | [docs/corpus-map.md](docs/corpus-map.md) |
| What was decided, and why | [docs/decisions/](docs/decisions/README.md) |
| How issues are labelled and ordered | [docs/backlog.md](docs/backlog.md) |
| What each trial changed | [examples/README.md](examples/README.md) |
