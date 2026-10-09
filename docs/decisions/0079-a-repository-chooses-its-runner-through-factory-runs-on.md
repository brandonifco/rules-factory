# 0079 — A repository chooses its runner through the variable `FACTORY_RUNS_ON`

## Status

Accepted — 2026-10-09. Records the owner's direction on
[#633](https://github.com/brandonifco/rules-factory/issues/633). Changes the generated
`.github/workflows/validate.yml` recipe and the three managed rails, `pr-policy.yml` (recipe
1 → 2), `conformance-gate.yml` (3 → 4) and `verdict-requeue.yml` (2 → 3), decision
[0018](0018-every-file-the-factory-writes-has-one-owner.md). Changes no job id, name, trigger,
permission, timeout, concurrency group or step, so no required status-check identity changes, and
no engine-owned file.

## Context

Every workflow the factory emits had one line, `runs-on: ubuntu-24.04`, so every engine's CI ran on
a GitHub-hosted runner and a repository could change that only by editing a generated or managed
file, which the next `produce` rewrites or refuses.

On 2026-10-09 the owner directed that private factory consumers run their CI on a self-hosted
runner: one KVM virtual machine on the owner's home server, registered with the labels
`self-hosted`, `linux`, `x64` and `factory-ci`. The runner has to be a choice a repository makes,
not a fork of the recipes, because the same recipes also serve repositories that must stay hosted.

## Decision

1. **One repository variable, one expression.** In all four recipes the job's runner is the single
   line

   ```yaml
   runs-on: ${{ fromJSON(vars.FACTORY_RUNS_ON || '"ubuntu-24.04"') }}
   ```

   The variable holds JSON: a label, or a list of labels. The name, the default label and the line
   are held once, in `tools/factory/repository.py` (`RUNS_ON_VARIABLE`, `RUNS_ON_DEFAULT`,
   `RUNS_ON_LINE`), and tests hold every recipe to that line and to no other `runs-on`.
2. **The default does not change.** A repository without the variable, or with it empty, runs on
   the pinned GitHub-hosted `ubuntu-24.04`, a fixed release and not `ubuntu-latest`, exactly as
   before. Nothing a gate validates is different.
3. **There is no fallback, by design.** A value that is not JSON fails the workflow where it can be
   seen. A private repository whose own runner is offline queues its jobs or fails them; it never
   quietly spends a billable hosted runner, which is the failure a fallback would hide.
4. **Public repositories that accept untrusted contributions stay on hosted runners, deliberately,
   and never set the variable.** A self-hosted runner executes the code of any pull request that
   reaches it, and on a machine that persists between runs. Hosted runners are the isolation such a
   repository relies on. The variable is for private repositories whose contributors are trusted.
5. **Setting or unsetting the variable is the switch, and it is explicit and auditable** as a
   repository setting, not an edit to a workflow:

   ```bash
   gh variable set FACTORY_RUNS_ON --repo O/R --body '["self-hosted","linux","x64","factory-ci"]'
   gh variable delete FACTORY_RUNS_ON --repo O/R
   ```

6. **An engine reaches the new recipes by re-producing** from a factory tag that contains this
   change. The three managed rails move by recipe version, the old hashes are kept in
   `RECIPE_SHA256`, so an engine still on the old bytes is recognised as unedited and upgraded by
   the next `produce`; the generated gate is rewritten by it. An engine embedded under a host
   repository (decision [0069](0069-repository-level-automation-belongs-to-the-repository-root.md))
   gets the same line, with the job's `defaults.run.working-directory` inserted above it. Until it
   re-produces, an engine keeps `ubuntu-24.04`, and the variable does nothing for it.

## What this does not decide

The runner host's own setup and runbook, its registration, its updates and its isolation, are
documented separately. This record decides only how a repository selects its runner.
rules-factory's own `.github/workflows` are unchanged: this repository is public and stays hosted.
