# CLAUDE.md

**[`AGENTS.md`](AGENTS.md) governs work on this repository. Read it first.**

This file states no rule of its own, on purpose: two copies of a contract drift. What is
Claude-specific is how the rules are applied:

| Path | What it does |
|---|---|
| `.claude/settings.json` | a `SessionStart` hook that runs `tools/repo-hygiene.py --fix`, so a session starts level with `origin/main` and with nothing finished left behind, or is told what is in the way (AGENTS.md §1, §4) |
| `.claude/worktrees/` | where an isolated agent's worktree lands, and where a worktree you make yourself goes; ignored by git and by `validate.sh` |

A background agent's brief carries four lines from AGENTS.md: the `## Documentation` section of
its pull request (§3); clean up after itself, deleting only what it created, by exact path, never
by wildcard in the shared scratch directory (§4); commit as it goes (§2); and do not merge. The
orchestrator runs `repo-hygiene.py --fix` after merging what the agent opened.
