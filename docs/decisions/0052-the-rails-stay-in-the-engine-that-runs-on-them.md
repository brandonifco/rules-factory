# 0052 — The rails stay in the engine that runs on them

## Status

Accepted — 2026-09-21. Records the decision on
[#353](https://github.com/brandonifco/rules-factory/issues/353), which asked whether the rails
recipe is large enough to externalise.
**Extends [0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)**,
which decided that the rails are emitted by default and that `AGENTS.md` governs, and
**[0018](0018-every-file-the-factory-writes-has-one-owner.md)**, whose managed class is the
mechanism this record is about keeping.

No rail moves under this record. It compares three designs and says why the first stays.

## Context

A produced engine carries the rails as managed files: `AGENTS.md`, `CLAUDE.md`, three agent
definitions, a checkout-guard hook, `.claude/settings.json`, `.editorconfig`, a pull request
template, three GitHub workflows, ten policy scripts under `tools/`, and the three build files
(`global.json`, `NuGet.config`, `Directory.Build.props`). They are copied in, and every engine
carries its own copy.

The proposal was that this is a lot of duplicated bytes. Measured, on `2231460`:

| | |
|---|---|
| the recipe, `tools/factory/recipe/rails/` | 202 KB in 23 files |
| what an engine carries as managed files | **204 KB in 26 files** |
| the `hoyle-backgammon` engine, in all | 1378 KB in 60 files — the rails are **15%** of it |
| the `faa-part-107` engine, in all | 801 KB — the rails are **26%** of it |
| recorded byte-versions across all managed files | 70; `AGENTS.md` alone is at v10 |

The share depends on the map, because the rails are a fixed 204 KB and the generated code is not.
A larger corpus makes them a smaller fraction. 26% is the higher of the two engines that exist.

The proposal said 270 KB. That is `du`'s block count on a directory of small files; the bytes are
202 KB.

## What the current design provides

Each of these is a property something else would have to keep, and each is a thing the managed
class buys rather than a thing that happens to be true.

**Offline verification.** `provenance.json` records `managed: [{path, recipeVersion, sha256}]` for
all 26 files, and the engine's own gate — `scripts/engine-gate.py`, run by the engine's
`scripts/validate.sh` — re-hashes every one of them with no network. An engine can prove its rails
are the recipe's bytes on a machine that has never seen this repository.

**Per-file provenance, and therefore per-file ownership.** `--adopt` makes one rail engine-owned
and `--reset` puts it back. That is expressible only because each file is hashed on its own.

**Migration that cannot overwrite an edit.** `ownership.RECIPE_SHA256` holds every byte-version
each rail has ever had — 70 of them. A produce rewrites a rail whose bytes are *any* recorded
version, and refuses one that matches none. That is how "an engine on an old rail" is told apart
from "an engine that edited its rail", and it is the whole reason a rails fix can be shipped to an
engine at all.

**Inspectable behaviour.** A contributor opens `AGENTS.md` at the engine's root and reads the rules
they are working under; the policy scripts sit in `tools/`, beside the code they judge. The rails
are documents and repository policy, not a library. Their being readable *where the work happens*
is the feature.

## The alternatives, and what each costs

### A pinned, versioned rails distribution the engine restores

A package, pinned by version and digest, restored into the engine.

- **Offline verification is lost or duplicated.** A clean clone would have to restore the package
  before it could verify its own rails; the digest in the engine would attest to a package, not to
  the bytes in the tree. Keeping the present guarantee would mean hashing the unpacked files
  anyway — which is the current design with a download in front of it.
- **Provenance becomes coarser.** One package digest replaces 26 file digests, and `--adopt` of a
  single rail stops being expressible.
- **Some rails cannot move at all.** `AGENTS.md` is read at the engine's root because that is where
  an agent looks; `.claude/settings.json` and the hook are read from `.claude/` by the harness;
  `.editorconfig`, `global.json`, `NuGet.config` and `Directory.Build.props` are read by tools that
  look for them in the tree. A package whose contents must be unpacked into the tree to function is
  a copy with a download in front of it.
- **What it would save.** 204 KB per engine, of an engine that is 1378 KB.

### Reusable GitHub workflows plus local minimal wrappers

The three emitted workflows call a central reusable workflow; thin local wrappers remain.

- **It addresses 6.3 KB of the 204.** The three workflow files are already thin wrappers: each runs
  one `tools/*.py` and states nothing itself, deliberately, so that the contract is stated once.
  The substance is the 130 KB of Python they call. Centralising the YAML centralises the part that
  is already minimal.
- **Centralising the Python is the real proposal, and it inverts the trust boundary.** Every
  produced engine would run code from a repository its owners do not control, with its own token,
  on every pull request. `pr-policy.yml` refuses `pull_request_target` for a smaller version of
  exactly this reason — it will not let attacker-controlled text reach a privileged token.
- **Offline verification goes.** A reusable workflow cannot run or be verified offline, and
  `provenance.json` could not hash what actually ran. A pinned `@<sha>` reference attests to what
  was *asked for*, not to bytes present in the engine.
- **Inspectable behaviour goes.** The rules a contributor is working under would be in another
  repository.

## Decision

**The rails stay copied into the engine, as managed files, unchanged.**

The measurement is the reason. 204 KB — a quarter of the smaller of the two engines, a seventh of
the larger — is not a weight problem, and every
alternative pays for those bytes with one of the four properties above — the ones that make a rail
something an engine can verify, adopt, migrate and read. A produced engine is meant to be
self-contained: given the engine and no network, a person can build it, test it, recompute its
provenance and read its operating rules. That is the product, and the duplication is what it is
made of.

The 70 recorded byte-versions are sometimes cited as the cost of this design. They are its
evidence: every one of them is a rails change that reached an engine without silently overwriting
anybody's edit.

## What would change the answer

Stated so that a later reader can test it rather than re-argue it:

- **The rails outgrowing the engine.** If a produced engine's managed files exceed its own source —
  the rails passing 50% of an engine's bytes — the trade is different and this should be reopened.
  They are at 26% of the smaller engine today, and
  `test_the_rails_are_a_minority_of_the_engine_they_govern` fails at 50% rather than leaving the
  number in this document to drift.
- **Migration lag becoming real.** Today a rails fix reaches an engine on its next `factory
  produce`, and there is one produced engine. With enough engines that some sit for months on a
  known-bad rail, a distribution's push model starts to be worth its costs. What to measure is the
  distribution of `recipeVersion` across live engines, which `provenance.json` already records.
- **A rail that is genuinely a library.** If a policy script grows a dependency tree, it is no
  longer a document to read beside the code and the argument above stops applying to it. It would
  move on its own, not as part of a wholesale externalisation.

## If a move is ever approved

One produced engine is migrated as a compatibility pilot before the default changes: it carries
the externalised rails, its gate is run offline, its provenance is recomputed, and `--adopt` and a
migration across a recipe version are both exercised on it. The default changes only after that
engine has been through a real change under the new arrangement.
