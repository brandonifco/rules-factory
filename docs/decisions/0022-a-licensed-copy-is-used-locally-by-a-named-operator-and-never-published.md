# 0022 — A licensed `local-copy` corpus may be used locally by a named operator, and a map of one is never published

## Status

Accepted — 2026-09-14. Decided by Brandon on
[#105](https://github.com/brandonifco/rules-factory/issues/105). **Extends
[0013](0013-verification-posture-belongs-to-the-corpus.md) and
[0015](0015-a-map-is-published-as-a-versioned-package.md)**. Blocks criterion 1 of
[#3](https://github.com/brandonifco/rules-factory/issues/3).

**Superseded 2026-09-15** by [0028](0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md), and withdrawn in
full: the factory admits no licensed corpus, so there is no exception to make. The flag, the
allowlist, `licensed_copy.py`, the marked package, the publish-workflow guards, the withheld backlog
and the `licensedCopyException` provenance field are removed. The record below is kept as it was
written, except that its links to the two deleted files are now plain names, and describes nothing
the factory now does.

## Context

Criterion 1 of #3 rebuilds `deckard` from its corpus, and that corpus is licensed: `never-commit`,
`verification: local-copy`. Its text may not be committed (0002, 0013), and a map quoting it may
not be redistributed. The factory refused it at every step. `pack-map.py` refused the map as NOT
VERIFIED, so no package existed for intake to read. Intake refused any corpus that was not
`committed-copy`. The engine gate reported `local-copy` as NOT VERIFIED unless its `envVar` was
set.

That is right for everyone in general. Nobody but the holder of a licensed copy can verify one,
and no CI runner holds one. It also meant the person who does hold the copy could not use the
factory on it at all.

## Decision

**One named operator, who holds the licensed copy, may use a `local-copy` corpus on their own
machine. The exception covers what stays on that machine and nothing that distributes.**

### Who counts

All three, or the exception is refused:

1. **An explicit flag, `--licensed-copy-exception`**, on `tools/pack-map.py`, `factory produce`,
   `factory verify` and `factory provenance`. Without it nothing differs: every refusal fires with
   the message it always had, and no identity is asked for.
2. **Not in CI.** The flag is refused when `GITHUB_ACTIONS` is set or `CI` is set and not false.
   A runner is where publishing happens, and nobody's licensed copy is there.
3. **The authenticated GitHub identity is on the allowlist.** The login is
   `gh api user --jq .login`, run through `$FACTORY_GH` when set (as `backlog --create` runs `gh`)
   with a timeout. `gh` missing, unauthenticated, hung or failing is a refusal. `git config` is
   never read, because anyone can set it.

**The allowlist is
`tools/factory/licensed-copy-operators.json`**,
a committed list of logins holding `brandonifco` only. It changes only by pull request. It sits
beside `licensed_copy.py`, the one module that reads it,
so it is also among the recipe files every engine's `provenance.json` hashes: an engine records
the allowlist it was produced under.

### What the exception allows

- **`pack-map.py` packs a `local-copy` map into a local `.nupkg`.** The file the manifest's
  **`envVar`** names must hash to the manifest's baseline, and the locator checker for the
  corpus's adapter runs against it. That is the same
  variable an engine's gate reads (0013), so an operator sets one variable for both, and no
  second way of naming the path exists to disagree with it. Every other gate
  (`check-map.py --phase publish`, one corpus, a known adapter) is unchanged. The package has the
  same parts as any other, and is **marked**: its nuspec `<tags>` carry `licensed-copy-exception`
  and its description begins `NOT PUBLISHABLE: built locally under the licensed-copy exception
  by <operator>`.
- **`factory produce`, `verify` and `provenance` intake the corpus**, hashing the local file
  against `contentHash` under `hashDerivation` exactly as for a committed copy. `produce` takes it
  from `--corpus`; a re-produce (recompute, and so `verify`) takes it from `envVar`, because the
  engine holds none. **No corpus bytes are written into the engine**, and an engine whose
  `corpus/` already holds files is refused. The engine's gate verifies through `envVar`, as it
  always did.
- **Provenance records `licensedCopyException: {operator, corpus}`** (the login and the
  sourceId), absent otherwise. Recompute compares it like any field: re-producing as a different
  operator, or without the exception, is a named mismatch.
- **Nothing that would say verified says it plainly.** `produce`, `verify` and `provenance` say
  `verified locally under the licensed-copy exception by <operator>`, and so does `pack-map.py`.

### What stays refused, flag or not

- **Publishing a `local-copy` map.** `pack-map.py` refuses the flag with `--tag`, the publish
  path, and in CI; without the flag it refuses the map as NOT VERIFIED. And
  [`publish-map.yml`](../../.github/workflows/publish-map.yml) refuses on its own account, so a
  change to the packer cannot open the path: its gate job refuses a map whose manifest declares
  any corpus that is not `committed-copy`, and its publish job refuses to push a package carrying
  the `licensed-copy-exception` tag.
- **Committing corpus bytes anywhere.**
- **A package or engine built under the exception claiming what a committed copy proves.**

### What it is

**A guardrail against accidental use and accidental distribution, not a security boundary.**
Anyone who can edit the checkout can edit the allowlist, `licensed_copy.py` or `$FACTORY_GH`, or
unset `CI`. What it stops is a licensed corpus being used, or a map of one packed, by someone who
did not mean to and would not notice: a contributor, a CI job, or the operator logged in to the
wrong account.

## Alternatives considered

**Trust `git config user.email`.** Rejected in the decision: anyone can set it.

**An explicit `--corpus` argument on `pack-map.py`.** Not chosen. The engine gate already reads
the local copy from `envVar`, and a second way of pointing at it is a second thing to get wrong.

**No marker on the package.** Not chosen. The package is otherwise indistinguishable from a
publishable one, and a local `.nupkg` is easy to copy somewhere it should not go. The marker costs
one tag and lets the publish workflow refuse by looking at the bytes.

**A security boundary: signing, or a secret only the operator holds.** Not attempted. The licence
risk is accidental distribution, and this repository is public; nothing committed here can keep a
determined person out, and pretending otherwise would be the worse failure.

## Consequences

**The engine's own gate output is unchanged.** Under `local-copy` with `envVar` set, the emitted
`engine-gate.py posture` prints `verified: <corpus> (local-copy, never-commit): local copy at
$VAR hashes to the pinned baseline`, and the gate knows no operator. It is the factory's output
(`produce`, `verify`, `provenance`) that names the exception.

**An engine's CI cannot verify its corpus.** Its `validate.yml` runs without `envVar`, so posture
is NOT VERIFIED there, as 0013 says it must be.

**An engine of a `local-copy` corpus quotes nothing from it, and neither does any issue.** An
engine's repository and its GitHub issues are distribution even when the map package is not. So
whenever the corpus is `local-copy`, whatever its `quotation`:

- **What the factory writes into the engine carries no corpus text.** The generated C# already
  carried only each entry's id, name and locator citation, and provenance.json and the gate recipe
  carry none. The `backlog/` files did: each item quoted `evidence`, the entry's `note` and
  `ambiguity.question` verbatim. For a `local-copy` corpus each of the three is replaced by a notice
  pointing at the citation in the licensed copy. `note` and `question` are withheld as well as
  `evidence` because both are written about the passage and often quote words of it, and nothing
  measures how closely. What remains is the entry id, name, structural fields (kind, clarity,
  status, relations, ambiguity fate and reason) and the locator.
- **`factory backlog --create` refuses before any write** for an engine whose provenance.json records
  `licensedCopyException`, unless every body carries that notice and none contains any `evidence`,
  `note` or `question` string (whitespace-normalised, 12 characters or more) of the map provenance
  names. The map is read from `--package`, or `Id@Version` from the NuGet global packages folder,
  and is never downloaded; it must hash to the map provenance recorded.
- **The map package is unchanged.** It is local, marked NOT PUBLISHABLE, and is the operator's own
  working copy of the map.

A committed-copy corpus's engine is byte-identical to what it was: it still quotes its evidence.

**`pack-map.py` hashes the local copy before packing.** Under the exception, the file `envVar`
names must hash to the manifest's `contentHash` under its `hashDerivation` (intake's derivations),
or the pack is refused: a wrong edition can resolve most citations and still not be the corpus the
map was made of.

**Tests use a synthetic corpus only** (`tools/tests/licensed_fixture.py`): invented text, a map
and a manifest declaring `never-commit` and `local-copy`. No real licensed text is in the
repository.
