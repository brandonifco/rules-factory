# 0069 — Repository-level automation belongs to the repository root, even when the engine is embedded beneath it

## Status

Accepted — 2026-09-27. Decided by Brandon on 2026-09-27. Records the decision on
[#501](https://github.com/brandonifco/rules-factory/issues/501). **Amends
[0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)**,
which says the rails are emitted with the engine and does not say where the four of them GitHub
reads live when the engine is not the repository. **Amends
[0018](0018-every-file-the-factory-writes-has-one-owner.md)** with one table more: the files a
*repository root* holds for an embedded engine, each of them generated. **Adds no map concept**, so
[0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md) does not govern it; what it adds
is a fact about where a produced engine sits, recorded in `provenance.json` (`provenanceFormat` 9).

## Context

GitHub reads a workflow file only from `.github/workflows/` at the **root of a repository**, and a
pull request template only from the root (or `docs/`). Nothing below the root is ever loaded, and
nothing tells you: there is no error, no warning and no missing-file diagnostic. A workflow in the
wrong directory is a text file.

Every engine the factory had produced was its own repository root, so `--out` and the repository
root were the same directory and the question never arose. `gate.py` wrote
`.github/workflows/validate.yml` relative to `--out`; `agentrails.py` wrote `pr-policy.yml`,
`conformance-gate.yml` and `verdict-requeue.yml` and `.github/pull_request_template.md` the same
way. The assumption was not stated anywhere, because nothing had contradicted it.

Then an engine was produced into a subdirectory of a larger private repository, beside the corpus
it is made from, the tooling that maps it and an archived prototype. Everything the factory
reported was true of the files and false of the repository:

* four workflows written, recorded in `provenance.json` as generated and managed;
* `tools/agent-doctor.py` reporting the gate workflow present;
* a pull request template in the engine;
* and not one of them ever read by GitHub. The gate, the pull request policy, the conformance gate
  and the verdict requeue were **dark**, and the engine looked like an engine with rails.

That is worse than having no rails at all. An engine with no gate is obviously ungated. An engine
whose gate is a file GitHub never loads is ungated and reads as gated, in its own record, in its
own doctor, and to anyone who opens the directory.

### Why not the obvious repairs

**Copy the four files to the root by hand.** Two copies of every gate, no owner, and the first
recipe change makes them disagree. [0052](0052-the-rails-stay-in-the-engine-that-runs-on-them.md)
is the same argument in the other direction: one definition, in one place, or it drifts.

**Make the root's workflows thin wrappers that call the engine's.** GitHub has no such call. A
local reusable workflow is referenced as `./.github/workflows/<file>`, which is the root directory
again; `./engine/.github/workflows/validate.yml` is not a path GitHub resolves. There is no
delegation from the root to a subdirectory, so the actual YAML has to be at the root.

**Keep templates under the engine and have the root copy them in CI.** Nothing runs at the root to
do the copying: the thing that would run is the workflow that does not exist yet.

**Let the produce output root be the repository, with the engine at a subpath.** This is the tidy
answer and it is a rewrite: every ownership pattern, every `provenance.json` path, every vendored
gate script and the whole transaction are written in engine-relative paths, and a host repository's
corpus and archive would be staged and drift-checked on every produce. The cost is paid by every
standalone engine to serve the embedded case.

## Decision

**A produced engine knows whether it is its own repository root or embedded beneath one, and the
files GitHub reads only from a repository root are written where GitHub reads them.**

### 1. The topology is a fact of the run, decided before anything is written

`tools/factory/repository.py` decides it, and `produce` calls it first:

| `--out` | `--repo-root` | Topology |
|---|---|---|
| a git work tree's top level, or in no repository | absent | **standalone** |
| under a git work tree's top level | absent | **refused**, naming both answers |
| anything | equal to `--out` | **standalone**, declared |
| anything | an ancestor of `--out` that is a repository root | **embedded** at the path between them |
| anything | an ancestor that git says is not a root | refused |
| anything | not an ancestor of `--out` | refused |

git is asked rather than the operator, because where the engine is is not a matter of opinion; the
operator is asked to *confirm* it, because the answer decides that bytes are written outside
`--out`, and no run does that silently. The refusal is the important half: it is what makes it
impossible to produce an engine with dark rails by omission, including for every caller written
before this record.

### 2. What a repository root holds, and what an embedded engine does not

Five files: `validate.yml`, `pr-policy.yml`, `conformance-gate.yml`, `verdict-requeue.yml` and
`pull_request_template.md`. For an embedded engine they are written at the root and **not under the
engine at all** — not even as templates. An inert copy that reads as a live rail is the whole of
#501, and a directory of workflow files that GitHub never loads cannot be made honest by a comment.

`.github/agent-policy.json` stays in the engine. It is not read by GitHub: the engine's own scripts
read it by path, and it is engine-owned configuration under 0029. `AGENTS.md`, `CLAUDE.md` and
`.claude/` stay in the engine for the same reason — they are read from the working directory of
whoever works the engine, not by the forge.

### 3. One rendering, from the same recipes

The root's copies are rendered from exactly the bytes a standalone engine would have received
(`repository.recipes()` reads `gate.py` and `agentrails.py`), plus what the root needs and nothing
else:

* a job-level `defaults: run: working-directory: <engine path>`, so every `run:` step executes in
  the engine and no command is rewritten — `./scripts/validate.sh full` stays
  `./scripts/validate.sh full`, and `json.load(open("provenance.json"))` still reads the engine's
  record;
* a note at the top saying who wrote the file, that it is rewritten by every produce, and where the
  engine is;
* in the gate workflow alone, one step: `python3 scripts/engine-gate.py repository --root
  "$GITHUB_WORKSPACE"`;
* in the pull request template, a note that every path below it is relative to the engine.

A standalone engine's files are the recipe bytes, unrendered and unchanged. **No existing produced
engine's bytes move**: the rendering is reached only when there is an engine path to render for.

A recipe whose shape those insertions do not fit — a second job, a missing checkout — is refused
rather than guessed at, because a repository root's rails are not the place to find out that an
assumption expired.

### 4. Ownership: generated, and hashed in the record

The five are **generated** (0018): rewritten by every produce, a hand edit overwritten, and hashed
in `provenance.json` — in a section of their own, `repository.automation`, because `generated` is
engine-relative and these are not the engine's paths. They are not *managed*, deliberately: a
managed recipe's bytes must be one fixed sequence per version (0018), and these depend on the
engine's path under its root. Generated is also the stronger anti-drift class, which is what this
record needs most.

`provenance.json` grows `repository`, and `provenanceFormat` becomes 9:

```json
"repository": { "enginePath": "engine", "automation": [ { "path": ".github/workflows/validate.yml", "sha256": "..." } ] }
```

`"enginePath": null` is a standalone engine — stated rather than omitted, so a reader can tell it
from a record written by a factory that could not say.

### 5. The root is not an empty lot

A file at one of those five paths that the factory did not write refuses the run, by name. A
repository root is somebody's product: its own workflows, its own template. What the factory
recognises as its own is the bytes it is about to write or a path the last run's record names at
that root; everything else is refused with the two ways on (remove it, or keep it under a name the
factory does not write). Every other file in `.github/` is copied and left exactly as it is.

### 6. Regeneration, and the migration

Producing again rewrites the five at the root and writes nothing under the engine. An engine
produced *before* this record under a host repository has the five inert copies; the next produce
deletes them, in the staging copy and so in the same transaction, and **only where the engine's own
record says the bytes are the factory's** — the rule `ownership.remove_retired` already deletes by.
An edited rail, or a workflow somebody else added under the engine, is kept and named as something
that cannot run where it is.

Two transactions, not one: the engine's `--out` (0067's #67 guarantee, untouched) and
`<root>/.github`. Every refusal this run can make is made before either commits, so the ordinary
outcomes are both written or neither. The engine commits first, because the root's rails name the
engine they run.

### 7. What checks it

* **`repository.assure_active()`**, in the factory, over the paths the run actually wrote: a run
  that wrote a workflow file and none where GitHub will run it is refused. This is the invariant of
  #501 as code rather than as care, and it is what fails if the bug returns by another road — a
  recipe added to the emission without a thought for the topology.
* **`scripts/engine-gate.py repository`**, in the engine, run by the root's gate workflow: no
  workflow file anywhere under an embedded engine, the record names every rail the root holds, each
  is there with the recorded bytes, and the engine really is `enginePath` under that root.
* **`tools/pr-policy.py`** judges a changed path in the engine's own terms: GitHub reports
  `engine/src/X.cs` where the ownership table says `src/X.cs`, and the rails at the root are the
  factory's work on every run.
* **`tools/agent-doctor.py`** looks for the gate workflow where GitHub reads one. Reporting a rail
  present where nothing would run it is the failure this record exists to prevent, and the doctor
  was one of the things that reported it.

### 8. What this does not do

It does not make the factory write anywhere but `--out` and one declared repository root's
`.github`. It does not move the engine's own gate: `./scripts/validate.sh full` is still the one
definition of acceptable, still passes with no network and no forge, and still knows nothing about
GitHub. And it does not give an embedded engine a second gate — there is one gate, run from the one
place a gate can be run from.

## Consequences

* `produce` gains `--repo-root`. Every existing call is unaffected unless its `--out` is under a
  repository root, and such a call is refused with the command that fixes it.
* `provenanceFormat` 9. A re-produce rewrites the record, as any factory version change does; the
  engine's other bytes do not move for a standalone engine.
* `tools/pr-policy.py` recipe 9 and `tools/agent-doctor.py` recipe 7: a managed-byte migration
  every engine receives on its next produce, because both read paths and one of them reports where
  the rails are.
* An embedded engine's pull requests are governed from the root: the template GitHub shows, the
  checks GitHub requires, and the working directory each of them runs in.
* `factory rails --apply` is unchanged. The required check names are the workflow names, and those
  are the same names at a root as in an engine.
