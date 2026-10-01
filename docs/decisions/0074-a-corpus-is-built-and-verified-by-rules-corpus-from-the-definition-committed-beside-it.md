# 0074 — A corpus is built and verified by rules-corpus from the definition committed beside it

## Status

Accepted — 2026-09-30. Records the change on
[#558](https://github.com/brandonifco/rules-factory/issues/558), which is rules-corpus milestone M4
([brandonifco/rules-corpus#4](https://github.com/brandonifco/rules-corpus/issues/4)): *both
consumers eliminate local duplicate corpus infrastructure*. **Amends
[0048](0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md)** (the
identities a package binds are now computed by rules-corpus, not by intake) and
**[0039](0039-the-manifest-pins-every-corpus-a-map-cites.md)** (each cited corpus is carried with
what rebuilds it). The two architectural choices below were the owner's, made on rules-corpus#4:
invoke rules-corpus with `dotnet run` against a pinned commit until its 1.0 tool exists, and build
the corpus at intake from committed sources rather than accept a pre-built one.

## Context

Until this change the factory owned a digest recipe. `intake.HASH_DERIVATIONS` mapped each
`hashDerivation` name to a function, and every function was SHA-256 over the whole committed file.
Five places recomputed a baseline through it:

- intake's `verify_declared_corpus_digest`;
- intake's `verify_resolved_corpora_binding`;
- `tools/pack-map.py`'s verification record;
- `provenance.py`'s re-hash of an engine's `corpus/`;
- every engine's own gate (`scripts/engine-gate.py posture`), through the copy of `intake.py` that
  `produce` vendors into it.

The copies in engines produced earlier had already drifted from the factory's (rules-corpus#4,
calibration record of 2026-09-30).

rules-corpus exists to own exactly that: given retained source bytes and a declared derivation, it
reproducibly builds a corpus and verifies it, and it records what each derivation lost and what it
could not verify (its decisions 0004 and 0008). With the factory keeping its own recipe, there
were two implementations of one responsibility.

## Decision

1. **The recipe is committed beside the corpus.** A corpus file `F` has, in the same directory:
   - `<stem of F>.corpus.build.json`: a rules-corpus build definition. It stores `F` at `F`'s own
     name, and its baseline names the artifact the map cites, by `sourceId`, `hashDerivation` and
     `asOf`.
   - `<stem of F>.corpus.expect.json`: `{"expectNotVerified": [...]}`, the rules-corpus checks this
     corpus accepts as not verified (rules-corpus decision 0008).

   Both files are required. `[]` means nothing may be left unverified. The rule is fixed, so
   `produce --corpus <file>` is unchanged and nothing new is declared on the command line.
2. **rules-corpus is run from one pinned commit.** `tools/factory/rulescorpus.py` names
   `REPOSITORY` and `COMMIT`. It fetches that commit into the user's cache directory, checks before
   every use that HEAD is the pin and that no tracked file is modified, builds it once, and runs its
   CLI with `dotnet run --no-build` under that checkout's own `global.json`. A checkout that fails
   a check is refused, never repaired. There is no fallback: if the tool cannot be fetched, built or
   run, nothing is verified.
3. **Intake builds and verifies.** For each cited corpus, the definition, the expectation and every
   source the definition stores are copied into a fresh temporary directory. Intake then runs
   `rules-corpus build` and `rules-corpus verify --rebuild`, passing `--expect-not-verified` when
   the expectation names anything. Anything but exit 0 is a refusal carrying rules-corpus's own
   report. The built baseline must:
   - name the supplied file;
   - equal the manifest's `hashDerivation`, `contentHash` and `asOf`;
   - equal the package verification record's `contentHash`.
4. **The factory's vocabulary stays the factory's.** `intake.ADMITTED_HASH_DERIVATIONS` is the
   closed set of names the factory admits, with what each one claims. It is the old table's keys,
   with no functions. rules-corpus accepts any label and does not own which claims about a text a
   reviewer has read. So the name check is admission, not recipe, and is kept: an unadmitted name
   is refused before anything is built.
5. **One check, every caller.** `intake.verify_declared_corpus` is the only verification. Intake,
   `pack-map.py` (through `intake.verify_corpora`), the engine gate's `posture` (through the
   vendored intake) and provenance's recompute (through the re-produce, which runs intake) all
   reach it. `provenance.py` no longer re-hashes; it checks that `corpus/` holds exactly the cited
   corpora and what rebuilds them (`rulescorpus.carried`).
6. **An engine carries the recipe.** `produce` writes the definition, the expectation and every
   stored source into `corpus/`, beside the corpus. They are generated files, hashed in
   provenance, so the engine's gate builds the corpus again with the same rules-corpus.
   `scripts/factory/rulescorpus.py` is vendored with the rest of the recipe.

## What remains the factory's

- Admission: licence, distribution, posture and randomness (0013, 0019, 0028, 0068).
- The admitted `hashDerivation` vocabulary.
- Binding a package's verification record to its members (0048).
- Size limits on everything intake reads.
- Which corpus file is bound to which cited corpus (0039).
- Everything after intake.

rules-corpus owns building the corpus, its derivation chain, the digest of every artifact, and
what verified means.

## Consequences

- **Supplied file names.** A corpus supplied under a name other than its manifest `committedPath`
  basename is refused. Its definition names the file it was supplied as, and the engine carries it
  under the committed name.
- **SDK and network.** Intake, and every engine's gate, now needs the .NET SDK (the engines
  already did) and, once per machine and pinned commit, network access to fetch rules-corpus. The
  factory's `validate` CI job installs the pinned SDK for this.
- **Unverifiable corpora fail closed.** A corpus declaring an external derivation or an unstored
  source verifies only when its expectation names exactly the checks rules-corpus cannot verify.
  srd-5.2.1 names `artifact srd-pdf` and `rebuild srd-extraction`.
- **Engines produced before this change** keep their vendored table until they are produced again.
  A re-produce gives them the definition, the expectation and `rulescorpus.py`.
- **When rules-corpus ships 1.0 (its M7),** the pin becomes a package version, and this record's
  semantics do not change.
