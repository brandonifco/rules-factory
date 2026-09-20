# 0048 — A verified map package binds the exact artifacts its publish gate read

## Status

Accepted — 2026-09-20. Records the repair for
[#333](https://github.com/brandonifco/rules-factory/issues/333), the first remediation under
[#338](https://github.com/brandonifco/rules-factory/issues/338). **Amends
[0015](0015-a-map-is-published-as-a-versioned-package.md)** and extends
[0039](0039-the-manifest-pins-every-corpus-a-map-cites.md). It does not change the separation in
[0016](0016-a-map-package-is-data-not-code.md): factory intake never executes code from a package.

## Context

The publish gate checked citations against corpus files and then packaged a manifest that declared
which corpus bytes those files were supposed to be. It never proved that the files the locator
checker read actually had the manifest's declared digest. Intake later re-hashed its own corpus
file against the packaged manifest, but that established a different relationship.

That allowed every individual check to be green while the handoff was false. A copy of the Hoyle
example changed the corpus and matching map evidence from "played by two persons" to "played by
three persons", retained the original baseline and manifest hashes, packed successfully, and was
then accepted by intake alongside the original two-person corpus. The packer had checked map M
against corpus B while the package declared corpus A and intake resolved corpus A.

Hashing a live corpus immediately before invoking the locator checker is not enough. The file can
change between the hash and the check. The bytes whose identity is recorded have to be the bytes
the checker actually read.

## Decision

**A package is verified only when its package artifacts and every corpus used by the publish gate
are bound in a deterministic machine-readable verification record, and intake independently
re-establishes that binding.**

### 1. One corpus-digest interpretation

tools/factory/intake.py remains the one implementation of manifest hashDerivation. The packer
already imports intake for the shared admission contract; it uses the same digest code rather than
growing a second table. An unknown derivation or a malformed declared digest is refused.

For every corpus the map cites, the packer reads its committed bytes once, derives the digest under
the manifest's declared method, and requires the result to equal the declared contentHash.
No principal-corpus shortcut exists: all cited corpora are required and sorted by sourceId.

### 2. Verification runs on immutable staged inputs

The packer snapshots the exact map bytes, the packaged manifest bytes, and each verified corpus
byte sequence into a private temporary tree. check-map.py --phase publish and the adapter's
locator checker are invoked against that tree. The package is then assembled from the same
in-memory map, manifest and checker bytes, while the corpus identities recorded in the package are
the digests of the same in-memory corpus bytes written to that tree.

Therefore a live source file changing after it was read can affect neither the verification run
nor the emitted package. This is a narrow packaging boundary; it is not a repository lock and does
not decide #335's source-tree transaction question.

### 3. The package carries map/verification.json

The record has verificationFormat 1 and contains:

- the SHA-256 and package path of the exact map bytes;
- the SHA-256 and package path of the exact manifest bytes;
- the SHA-256 and package path of the packaged tools/check-map.py bytes that also ran the publish
  structural gate;
- one corpus record per cited sourceId, with its hashDerivation and verified contentHash.

The corpus list is sorted by sourceId; JSON is emitted with fixed formatting and no timestamp,
machine path, random value or mutable external state. The package stays byte-for-byte
deterministic for identical inputs.

The adapter-specific locator checker remains factory publish machinery rather than a consumer
artifact. The package's repository commit continues to identify the factory revision that selected
and ran it; this decision does not turn locator checkers into package plugins. The byte identity
that travels as the package's validation artifact is tools/check-map.py, whose exact bytes are
both run by the publish gate and carried by the package.

### 4. Intake verifies relationships, not components in isolation

The RulesFactoryMap item names the verification record. Intake refuses a package that has no
record. It parses the record as data and never executes it.

Intake then requires:

- exactly the map, manifest and checker paths named by the package item are represented once;
- each recorded SHA-256 equals the actual bytes of that package member;
- the verification corpus set equals the map's cited corpus set exactly — no missing, extra or
  duplicate identity;
- each verification corpus identity equals the corresponding packaged manifest declaration; and
- every corpus file resolved by intake derives to that same recorded digest under that same
  derivation.

Only after those relationships hold does the ordinary consumer-phase validation continue. A
self-reported digest that is not compared with its artifact is not accepted as a binding.

### 5. Legacy packages are unbound

A package without map/verification.json does not provide this guarantee and is refused by the
verified intake path. It is not silently upgraded from individually valid parts to a verified
relationship.

Adding the record and the props metadata changes package contents, so under 0015 it is a **major
package change**. This decision does not mass-bump committed map versions. The next publication of
an existing map must take the major bump required by 0015, as 0023 established for the earlier
addition of LICENCE.txt.

## What this proves

After this decision, a successful package/intake chain proves a narrow identity statement:

> The packaged map, packaged manifest and packaged validation artifact are the bytes bound by the
> package verification record; every corpus digest in that record was derived from the exact
> corpus bytes against which the publish citation check ran; and intake resolved those same corpus
> identities again before accepting the package.

It does not prove that the map interpreted the corpus correctly, that mapping was complete, that
a human independently reviewed it, that the final engine source tree equals a verified staging
snapshot, or any of #334–#337. Those remain separate assurance questions.

## Alternatives rejected

**Hash each live corpus and then run the checker on the same path.** Rejected: there is a TOCTOU
window between the read and the checker.

**Trust the packaged manifest at intake.** Rejected: that is the original failure. A declaration
of corpus A cannot prove that packaging checked corpus A.

**Record only one principal corpus.** Rejected by 0039. A clean principal corpus cannot carry a
secondary corpus the map also cites.

**Treat old packages as verified because intake can still hash their corpora.** Rejected: intake
can prove its own corpus matches the manifest, but cannot recover which bytes the old publish
locator run saw.

**Sign the verification record.** Not required for this defect. #333 is an artifact-relationship
gap inside a package flow whose package authenticity and registry transport are separate concerns.

## Consequences

- Every new verified package has one deterministic relationship record.
- Changing, deleting or substituting its map, manifest, checker or any cited corpus is refused at
  the boundary where the mismatch is observed.
- Existing published packages remain historical artifacts, but current verified intake refuses
  them as legacy/unbound.
- Provenance may record the verification member beside the map, manifest and checker so a produced
  engine can name every package data file on which intake relied; this does not change the corpus
  provenance model from 0039.
