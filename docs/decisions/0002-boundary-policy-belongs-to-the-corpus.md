# 0002 — Boundary policy belongs to the corpus, not to the repository

## Status

Accepted — 2026-09-13.

## Context

A predecessor framework held, as a repository-wide invariant, that authoritative source
material is never committed: the repository may contain hashes, metadata, derived code and
citations, but never the corpus, never extracted passages, never a local path to it. Its
checks enforced this, and its documentation stated it as doctrine.

That is correct for a commercial rulebook and wrong for a great deal else, and the evidence
was already in hand. Of the two engines this method was derived from:

- One is built over a commercial RPG rulebook. It commits nothing: the book is licensed
  material, and committing extracted passages would be redistribution.
- The other is built over a CC-BY SRD. It commits eight files of extracted content totalling
  2.9 MB, with attribution, because the licence permits it and committing it is what lets
  anyone reproduce the engine without obtaining the corpus separately.

Both are right. The predecessor's checks would have condemned the second.

The case that makes it unavoidable is law. Federal regulations and statutes are public
domain. An engine over them that refused to commit its corpus would be strictly worse:
unreproducible, for no benefit, in service of a rule that exists to respect a licence the
corpus does not have.

## Decision

Boundary policy is a **declared property of each corpus** in the manifest, not an invariant
of the repository:

- `never-commit` — the repository holds identity, hash, derivation and metadata. The corpus
  is configured locally and verified against the hash. Extracted packets are ephemeral and
  never committed.
- `pin-in-repo` — the corpus, or a declared derivation of it, is committed. The hash still
  pins it; the licence is recorded alongside.

A single repository may hold corpora with different policies, and the checks that enforce
the boundary read the policy rather than assuming one.

## Alternatives considered

**Keep never-commit as the default and allow exceptions.** Rejected: a default implies one
answer is normal and the other is a deviation. For a factory expected to produce engines over
law, that has it backwards as often as not.

**Infer from the licence field.** Attractive, and rejected for now. Licence identifiers are
numerous, their redistribution terms are not mechanically derivable, and the consequence of
guessing wrong in one direction is a licence violation. The policy is stated explicitly and
the licence is recorded next to it so a human can check they agree.

## Consequences

Every corpus entry must answer a question the predecessor answered once for the whole
repository. That is the point: it is a question about the corpus, and only its licence can
answer it.

Boundary checks become policy-driven. A check that hunts for committed source material must
read the manifest first, which means a corpus with no declared policy is a failure rather
than a default.
