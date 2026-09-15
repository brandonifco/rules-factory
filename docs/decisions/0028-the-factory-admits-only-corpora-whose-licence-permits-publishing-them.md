# 0028 — The factory admits only corpora whose licence permits committing and publishing their text and maps

## Status

Accepted — 2026-09-15. Decided by Brandon on 2026-09-15. **Supersedes
[0022](0022-a-licensed-copy-is-used-locally-by-a-named-operator-and-never-published.md)**, which
is withdrawn in full. **Supersedes the parts of
[0013](0013-verification-posture-belongs-to-the-corpus.md),
[0015](0015-a-map-is-published-as-a-versioned-package.md) and
[0023](0023-a-map-package-is-licensed-as-its-corpus-and-the-factory-are.md)** that were there only
for a licensed corpus; each is marked where it stands. Changes criterion 1 of
[#3](https://github.com/brandonifco/rules-factory/issues/3).

## Context

0022 let one named operator use a licensed `local-copy` corpus on their own machine, so that
criterion 1 of #3 could rebuild `deckard` from the SR6 core rulebook. It needed a flag on four
commands, an allowlist checked against `gh api user`, a refusal in CI, a marker on the package, two
guard steps in `publish-map.yml`, a backlog that withholds every quoted and paraphrased string, and a
provenance field recording the operator.

Starting the rebuild found that this was the beginning, not the end. Four more pieces of work were
opened, and each was the licence showing up somewhere new:

- a PDF text derived for a declared set of printed pages, so that no more of the book existed
  locally than the map needed ([#139](https://github.com/brandonifco/rules-factory/issues/139));
- page extents listing more than one span, because deckard's slice is two disjoint pieces of the
  book ([#140](https://github.com/brandonifco/rules-factory/issues/140));
- an owner's ruling that names its span by offsets and a hash, because 0027's verbatim span would
  commit the question's text three times over
  ([#141](https://github.com/brandonifco/rules-factory/issues/141));
- a way for a licensed-copy engine to restore a map package that is never published, and a CI that
  says NOT VERIFIED instead of failing, because no runner can ever hold the package
  ([#142](https://github.com/brandonifco/rules-factory/issues/142)).

Pull requests #143–#146 carried that work. Every piece was a second path beside the one the public
corpora use, tested only on synthetic fixtures, and it made the factory's guarantees weaker: an
engine whose map, corpus and CI can never be verified by anyone but its operator.

The corpora the factory has actually produced from need none of it. Hoyle 1909 and 14 CFR Part 107
are public domain. The SRD 5.2.1 is CC-BY-4.0, and 0023 already carries its attribution. Each is
committed, each map is published, and every CI run verifies all of it.

## Decision

**The factory will not use licensed rules at all. It admits only a corpus whose licence permits
committing and publishing both its text and its map: public domain, or an open licence.** 0022 is
withdrawn. #139–#142 and #143–#146 are closed and stay closed.

### What counts

The licence class is read from the manifest's `licence`, which a person already declares for every
corpus (0002, 0013) and which 0023 already holds the package's terms file to. Its leading identifier,
up to the first whitespace, `;`, `,` or closing `.`, decides:

| identifier | class |
|---|---|
| `public-domain`, or `public-domain-<whose>` (`public-domain-us-government`, `public-domain-underlying-work`) | public domain |
| `CC-BY-4.0`, `CC0-1.0` | open |
| anything else, or no `licence` | refused |

The corpora held today classify as `hoyle-1909` public domain, `cfr-14-107` public domain and
`srd-5.2.1` open. The list of open identifiers is closed. Admitting another licence is a decision,
recorded like this one, and then a change to `intake.py`'s `OPEN_LICENCES`.

### What is refused, and where

- **Intake** (`tools/factory/intake.py`, `refuse_unadmitted_licence`) refuses the corpus the map
  cites when its licence is not public domain or open. It runs before the posture check, so a licensed
  `local-copy` corpus is refused for its licence, naming this record, not as NOT VERIFIED. Intake is
  the first step of `factory produce`, and `factory verify` and `factory provenance` re-produce
  through it, so all three refuse. Nothing is written.
- **The publish gate** (`tools/pack-map.py`) refuses the same, with the same message, before
  `check-map.py` or any locator checker runs. No package is written, so `publish-map.yml`, which
  publishes only what `pack-map.py` wrote, cannot publish one.
- **`--licensed-copy-exception` no longer exists**, on `pack-map.py`, `produce`, `verify` or
  `provenance`. Passing it is a usage error. `tools/factory/licensed_copy.py` and its allowlist are
  deleted.
- **Unchanged:** a corpus that is not `committed-copy` is still refused by intake and by
  `pack-map.py` as NOT VERIFIED (0013), whatever its licence.

### What is removed with 0022

- The withheld backlog: items always quote `evidence`, `note`, `ambiguity.question` and each
  cross-reference as they did before 0022, and `backlog --create` checks bodies only for 0023's
  attribution.
- The `licensedCopyException` provenance field, and recompute's engine that holds no corpus.
- Generation's refusal of an engine whose `corpus/` holds files: every engine commits its corpus.
- `publish-map.yml`'s two guard steps, a local-copy map and a package tagged
  `licensed-copy-exception`. `pack-map.py` refused a `local-copy` map before 0022, and does again with
  no flag to open it; the marker no longer exists to look for.
- The synthetic licensed fixture and its tests.

### What stays, and why

- **0023's licence files and attribution.** An open licence still has terms. The SRD's CC-BY-4.0
  statement is carried in its package's `LICENCE.txt` and in every backlog item and issue, exactly as
  before.
- **0013's vocabulary: `never-commit`, `local-copy`, `quotation: withheld`, `envVar`.** It is how a
  manifest describes a corpus, and `check-map.py --only postures` and every engine's
  `scripts/engine-gate.py posture` still read it. The factory admits no corpus that uses it. It stays
  because both files ship in what the factory produces for public corpora: `check-map.py` inside
  every map package, and `engine-gate.py` in every engine as a managed recipe. Removing the
  vocabulary would change the bytes of every package and engine for no public corpus's benefit, and
  0013 also allows a `pin-in-repo` corpus that commits only a derivation to be `local-copy` for a
  reason that is not its licence.
- **The `licence` field and `boundaryPolicy` as declared facts.** 0002's reason not to infer
  `boundaryPolicy` from `licence` still holds for writing a manifest. This record reads `licence`
  only to refuse, never to fill in another field.

### What this means for `deckard`

`deckard` stays hand-built and outside the factory. Its corpus, the SR6 core rulebook, is commercial,
and the factory does not map it, pack it, produce from it or verify it. No example, map or target of
it is kept in this repository.

### What this means for #3

Criterion 1 was "rebuild `deckard`": rebuild an engine that already exists, so the target cannot be
quietly redefined. That test is kept, with a target whose corpus is public domain. **Criterion 1 is
now a blind rebuild of `hoyle-backgammon`.** What counts as blind and as equivalent is #3's to state.

## Alternatives considered

**Keep 0022 and finish #139–#142.** Rejected by the decision. Each piece was needed only because the
text could not be committed or published, and each added a path that only its operator could run.

**Keep the licensed code but leave it unused.** Rejected. Code that no admitted corpus reaches is
tested only against fixtures, and it keeps the exception one flag away.

**Read the class from `boundaryPolicy` or `verification`.** Rejected. Those say where the bytes live
and how they are checked, not whether they may be published. A public-domain corpus can be
`local-copy` under 0013, and a manifest could mark a licensed corpus `committed-copy` in error. The
licence is the fact this decision turns on, so it is what is read.

**A licence class field in the manifest.** Not chosen. `licence` is already declared, reviewed and
major-versioned (0015), and 0023 holds the terms file to it. A second field could disagree with it.

**Remove 0013's `local-copy` and `withheld` from the checker and the engine gate.** Not done here,
because it changes the bytes of every map package and produced engine (above). It can be its own
change, with the map version bumps 0015 requires, if keeping it ever costs something.

## Consequences

- Admitting a new corpus starts with its licence. A corpus whose licence is not in the table is
  refused at the first command that reads it, with a message naming this record.
- The factory's guarantees are the same for every corpus it admits: its text is committed, its map
  is published, and any CI run can verify both.
- `hoyle-backgammon`, `faa-part-107` and `srd-52-combat` produce what they produced before. Only the
  factory's own files that engines vendor (`scripts/factory/intake.py`, `generate.py`,
  `provenance.py`) and the recipe hashes provenance records for them change, as they do with any
  change to those modules.
- A licence the table does not know, such as CC-BY-SA-4.0, is refused until a decision admits it.
  That is deliberate: share-alike terms on a map package need reading before the factory publishes one.
- The issues and pull requests of the licensed work remain as history of why this was decided.
