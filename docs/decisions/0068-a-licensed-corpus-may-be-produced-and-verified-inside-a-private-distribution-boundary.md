# 0068 — A licensed corpus may be produced and verified inside a private distribution boundary

## Status

Accepted — 2026-09-27. Decided by Brandon on 2026-09-27. Records the decision on
[#497](https://github.com/brandonifco/rules-factory/issues/497). **Partially supersedes
[0028](0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)**, which
remains authoritative for public distribution and is marked where it stands. **Does not revive
[0022](0022-a-licensed-copy-is-used-locally-by-a-named-operator-and-never-published.md)**, which
stays withdrawn. **Adds no map concept** — no field, no kind, no relation, no unit, no vocabulary
value on an entry — so [0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md) does not
govern it; what it adds is a manifest fact about the corpus, and a consequence for where the
artifacts may go.

## Context

0028 admits a corpus only when its licence permits committing **and publishing** its text and its
map. One sentence, two facts:

1. **Admission** — may the factory read and process this corpus at all?
2. **Distribution** — may what comes out of it be handed to the public?

0028 answers the second by reading the first, and a corpus is refused at admission for a reason
that is really about publication. That is correct for everything the factory has held so far,
because every admitted corpus was publicly distributable and every product of it was published.
It is wrong the moment someone holds a licence that permits building a private product.

The case is real: a licensed board-game rulebook, properly licensed for this use, whose corpus,
map and engine will live in one private repository and be published nowhere. Nothing about that
work needs a weaker factory. It needs the ordinary one, pointed at a repository that is not public.

### Why this is not 0022

0022 let one named operator use a `local-copy` corpus on their own machine. It was withdrawn
because it built a **second path** that only its operator could run: an allowlist checked against
`gh api user`, a `--licensed-copy-exception` flag on four commands, a backlog that withheld every
quoted string, a provenance field recording the operator, and a CI that said NOT VERIFIED because
no runner could ever hold the corpus. An engine whose map, corpus and CI can be verified by exactly
one person is not verified.

This record shares none of that machinery and none of its shape:

| 0022, withdrawn | 0068 |
|---|---|
| a named operator, on an allowlist | nobody is named; the manifest declares a fact about the corpus |
| `gh api user` consulted at run time | no identity is consulted, ever |
| `--licensed-copy-exception` on four commands | no flag; there is nothing to pass |
| `local-copy`, bytes outside the repository | `committed-copy`, bytes in the private repository |
| verification possible only on one machine | verification possible in any checkout of that repository, CI included |
| CI intentionally NOT VERIFIED | CI verifies, exactly as a public engine's does |
| separate production semantics, withheld backlog | one production path; nothing is withheld that the licence permits storing |

The difference in one line: **0022 made the corpus unreachable and then weakened everything that
needed to reach it. 0068 keeps the corpus in hand and restricts only where the results may go.**

## Decision

**Licence and distribution are two independent declared facts. The factory admits a corpus on its
licence, and constrains where its artifacts may go on its distribution. A licensed-proprietary
corpus is admitted when, and only when, it declares private distribution, and it then uses the
ordinary production and verification path in full.**

### 1. The classes

| licence class | declared distribution | result |
|---|---|---|
| `public-domain`, or `public-domain-<whose>` | `public`, `private`, or undeclared | admitted |
| open: `CC-BY-4.0`, `CC0-1.0` | `public`, `private`, or undeclared | admitted |
| `licensed-proprietary` | `private` | admitted |
| `licensed-proprietary` | `public` | **refused** |
| `licensed-proprietary` | undeclared | **refused** |
| anything else, or no `licence` | any | **refused** |

`licensed-proprietary` follows the existing leading-identifier convention: the identifier is read
from the front of `licence`, before the first whitespace, `;`, `,` or closing `.`, so
`licensed-proprietary; publisher's written permission of 2026-09-01, reference ABC-123` classifies
and still carries a human statement of what the permission is.

The two facts do not read each other. A public-domain corpus may be placed in a private project and
declare `distribution: private`, and the factory honours it. A licensed-proprietary corpus may never
reach public distribution, whatever else it declares.

### 2. Undeclared distribution

`distribution` is optional, and absence reads as `public` — **except** under
`licensed-proprietary`, where absence is refused and there is no default.

This is the one place the two facts touch, and it is deliberate. Requiring the field everywhere
would be more uniform and is what the repository's habit suggests ("a corpus with no declared
posture is a failure, not a default", 0013). It was rejected for what it costs: `distribution`
lives in the corpus manifest, the manifest's bytes are packaged verbatim, and a published version
is immutable (0015). Adding a required field to four published maps' manifests would force a major
version bump and a republish of each, to state about `hoyle-1909` and `cfr-14-107` a fact that
their licence class already makes unambiguous and that no reader would dispute.

So the default exists only where it cannot be wrong: a corpus whose licence permits publishing its
text and its map has no publication restriction to declare. Where a restriction is possible — that
is, under `licensed-proprietary`, the only class this record admits that carries one — silence is a
refusal. Fail-closed where it matters, unchanged where it does not.

### 3. Strictest wins

A product's distribution requirement is the strictest of the corpora it is made from:

```text
public  + public   -> public
public  + private  -> private
private + private  -> private
```

This holds for a map citing several corpora, for a map package, for a composition (0067), and for
a produced engine. There is one implementation of it, `intake.strictest_distribution`, and every
one of those reads it.

### 4. Private is distribution-restricted, never unverifiable

A licensed-private corpus is `pin-in-repo` and `committed-copy` like any other, and receives the
same substantive verification: content hash, hash derivation, locator checks, map checks,
provenance, correspondence and conformance, the engine gate, and reproducible production. No
verdict is weakened because distribution is private. A result that says *verified* means the same
thing in a private repository as in a public one.

The bytes are in the private repository, so any checkout of it — a person's, or its CI — can verify
them. That is the whole of the difference from 0022.

### 5. Where the restriction is enforced

**Admission** (`tools/factory/intake.py`). One function classifies, `admit(corpus)`, returning the
licence class and the distribution requirement or raising. It replaces the string parsing 0028 left
in `refuse_unadmitted_licence`, and `factory produce`, `verify`, `provenance` and `pack-map.py` all
reach it. Fail-closed: anything it cannot classify is refused.

**Public publication** (`tools/pack-map.py`). `--tag` is how a pack becomes a publication:
`publish-map.yml` passes it, and nothing else does. A pack with `--tag` whose inherited distribution
is private is refused and nothing is written. There is no `--force`, no `--allow-private`, no
environment variable and no allowlist; the public workflow has no interface that reaches a private
package.

Packing **without** `--tag` is not refused, because that is how a private project builds the package
its own `factory produce` consumes. The package is written into that project; publishing it is a
separate act that this repository's public workflow cannot perform.

**The package** records its inherited requirement in `map/verification.json` as
`"distribution": "private"`, written when and only when the requirement is private. A public
package is byte-for-byte what it was, which is why no published map needs a version bump.

**The backlog.** `factory backlog --create` sends every item's body — the entry's evidence, quoted
from the corpus, included — to a GitHub repository the operator names. That is the other path in
this repository by which map-derived content reaches somewhere public, so it is refused when the
engine records `private` and `gh` does not say the target repository is private. Fail-closed both
ways: an engine whose record does not say, and a repository `gh` cannot answer for, are both
refusals. `--create` already requires `gh`, which is why the question is free there and is asked
nowhere else. `backlog --render` writes locally and is unaffected.

**The engine** inherits the strictest requirement of its admitted corpora, records it in
`provenance.json` (format 8), and, when private, carries a generated `DISTRIBUTION.md` saying so.
Its CI fails loudly when GitHub reports the repository as public. That notice and that check are a
machine-checkable contract and a guardrail against accidental publication. **Neither is a security
mechanism**, and nothing here encrypts, hides or access-controls anything.

Local verification never depends on GitHub: `scripts/validate.sh` and `scripts/engine-gate.py` run
and pass with no network, and the public-repository check lives only in the CI workflow, where the
answer is free.

### 6. What this repository may hold

`rules-factory` is public. **No proprietary corpus, rulebook text, card text, artwork or licence
document may be added to it**, and none is. Every test of licensed-private behaviour uses synthetic
invented fixtures. 0028's reason for that is untouched by this record.

### 7. What the manifest records, and what it does not

`distribution` is an assertion by the person who wrote the manifest, as `licence`, `quotation` and
`boundaryPolicy` already are (0002, 0013). **The factory does not determine whether anyone actually
holds sufficient rights**, and nothing here is legal advice. What the factory does is enforce the
assertion mechanically once it is made: a corpus declared `licensed-proprietary` cannot reach public
publication through any supported interface, whatever anyone intended.

No contract, licence secret, key or commercial term goes in a manifest. The field needs only enough
to enforce the contract.

## Alternatives considered

**Require `distribution` on every corpus, with no default.** Rejected for its cost, above: four
published maps republished at a new major version to declare a fact their licence class settles.
Recorded here so that if a second class ever admits both distributions, the default is revisited
rather than inherited.

**Read distribution from `boundaryPolicy` or `verification`.** Rejected, for the reason 0028
rejected reading the licence class from them: those say where bytes live and how they are checked,
not where the results may go. A private product can be `pin-in-repo` and `committed-copy`, and is.

**Put the distribution in `check-map.py`.** Rejected. The checker is packaged verbatim into every
map package, so a change to it changes the bytes of every package and forces four version bumps for
a check that intake and the publish gate already make. The map checker is unchanged by this record.

**A new verification format carrying `distribution` always.** Rejected for the same reason: a field
written on every package changes every package. Written only when private, no existing package moves
and the fact is still explicit wherever it matters.

**Refuse to pack a private map at all, so no private package can exist.** Rejected: it would leave a
private project with no way to feed `factory produce`, which takes a package. The refusal belongs at
publication, which is where the restriction is.

**A separate private-factory fork, or a licensed mode.** Rejected. That is 0022's shape again —
a second path, tested against fixtures, diverging quietly.

## Consequences

- A licensed-proprietary corpus can be mapped, packed, produced from and verified, in a private
  repository, with no reduction in what any check establishes.
- `hoyle-backgammon`, `faa-part-107`, `srd-52-combat` and every other admitted public example behave
  exactly as before, and their published packages keep their bytes. What changes for them is
  `provenanceFormat` 7 to 8 and the factory modules engines vendor — the churn any change to
  `intake.py` or `provenance.py` causes, versioned the way those always are.
- A produced engine now states its distribution requirement. Reading provenance tells a reader, and
  a tool, whether the engine may be made public.
- 0028 continues to govern public distribution. A corpus intended for a public product still needs a
  public-domain or open licence, and proprietary material still cannot enter this repository's
  examples or its map publication.
- The factory still refuses a licence it does not know. Admitting another open licence, or another
  proprietary form, is a decision recorded like this one.
