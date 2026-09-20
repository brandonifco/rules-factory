# 0039 — The manifest pins every corpus a map cites, the envelope's baseline stamps the principal one, and provenance records them all

## Status

Accepted — 2026-09-18. Records the decision on
[#300](https://github.com/brandonifco/rules-factory/issues/300), forced by trial 10
([#262](https://github.com/brandonifco/rules-factory/issues/262)).
**Extends [0013](0013-verification-posture-belongs-to-the-corpus.md)**, which put verification
posture on the corpus, and **[0015](0015-a-map-is-published-as-a-versioned-package.md)**, which
put the manifest inside the package beside the map. **Sibling of
[0038](0038-a-map-declares-the-passages-its-grammar-cannot-address.md)**, which is the other half
of what trial 10's corpus forced. The specification is [corpus-map.md](../corpus-map.md).
\n\n**Amended by [0048](0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md)** (#333): packaging now re-hashes every cited corpus before publication, runs locator verification against an immutable snapshot of those exact bytes, and records the per-corpus identities in a package binding that intake must independently match. 0039's manifest authority and every-corpus cardinality remain unchanged.\n
## Context

The eCFR serves 49 CFR § 172.101 and § 172.102 as **two documents with two hashes**, and every
column 7 pointer in the Hazardous Materials Table crosses between them: a code printed in
§ 172.101's table is *stated* in § 172.102. One regulatory rule, two served documents.

The map contract already permitted this. `locator.sourceId` need only be declared in the
manifest — it does not have to equal the envelope's `corpus` — and since
[#301](https://github.com/brandonifco/rules-factory/pull/301) the `section-designation` locator
run reads a map citing several corpora, checking each entry against the corpus its own
`sourceId` names.

The factory did not. Two gates refused the shape outright:

```python
# tools/pack-map.py
raise Refused(f"NOT VERIFIED -- the map cites {sorted(cited)}; every locator checker reads "
              f"exactly one corpus, so these citations cannot all be checked")

# tools/factory/intake.py
raise Refused(f"the map cites {sorted(map(str, cited))}; an engine is produced from exactly one corpus")
```

So trial 10's map could be written, and could pass `scripts/validate.sh` in full, and could
never be packaged or produce an engine. Two subsystems over one contract disagreed about what the
contract allows, which is what [0032](0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md)
exists to prevent. And `pack-map.py`'s stated reason had **expired**: every locator checker no
longer reads exactly one corpus.

The refusals were the safe direction, and worth saying plainly: provenance never recorded a
half-verified correspondence, because the map never reached provenance. What was wrong was the
restriction, not a hole behind it.

## Decision

**A map may cite several corpora. The manifest is the authority for which, and for the bytes of
each. The envelope's `corpus`/`baseline` remains the map's principal stamp, pinning that corpus
and claiming nothing about the others. Intake resolves and independently hashes every cited
corpus. Packaging also binds every one of those identities to the exact corpus bytes its locator run read (0048); the engine carries them all, and provenance records them all.**

### 1. No per-corpus baseline is added to the map

The manifest already declares, per corpus, `sourceId`, `contentHash`, `hashDerivation`, `asOf`,
`verification`, `licence`, `randomness` and `committedPath`, and it travels *inside the package*
(0015). Adding a second per-corpus baseline to the map schema would duplicate information the
manifest already owns and create two authorities for the same fact — the failure mode the
decision discipline calls two sources of truth.

The envelope's stamp still has to agree with its own corpus's manifest entry; that is
`check-map.py --only manifest`'s, unchanged. It now claims only that.

### 2. Intake hashes every cited corpus, from the bytes in hand

`--corpus` is repeatable, once per cited corpus. Where a map cites one and one file is supplied
they are bound directly, which is what every existing invocation means and keeps working whatever
the file is called. Beyond one, a file is bound to the corpus whose manifest `committedPath` it is
the basename of — the manifest already says where each corpus is committed, so nothing new is
declared and nothing is guessed. A file matching no cited corpus, two files matching one, or a
cited corpus with no file, is refused rather than resolved.

Each corpus is then refused unless it is declared exactly once, licence-admitted (0028),
`committed-copy` (0013), declares its randomness (0019), names a computable `hashDerivation`, and
**hashes to its declared `contentHash` under that derivation, recomputed here**. The manifest says
which bytes are wanted; it is not evidence that these are they.

Cited corpora that disagree about `randomness` are **refused**. An engine has one randomness
posture and nothing says whose it would be; taking the principal's would be behaviour invented for
the envelope's field, and §5 declines to invent any.

### 3. Provenance records `corpora`, and `provenanceFormat` becomes 5

```json
"corpora": [
  { "sourceId": "cfr-49-172.101", "contentHash": "...", "hashDerivation": "ecfr-versioner-xml",
    "asOf": "2026-01-01", "path": "corpus/section-172.101.xml", "principal": true, "recomputed": true },
  { "sourceId": "cfr-49-172.102", "contentHash": "...", "hashDerivation": "ecfr-versioner-xml",
    "asOf": "2026-01-01", "path": "corpus/section-172.102.xml", "principal": false, "recomputed": true }
]
```

Sorted by `sourceId`, so the record is canonical and deterministic. The single `corpus` object is
**gone** rather than kept beside the list: a legacy field naming one of several corpora would be a
misleading shape, and a reader cannot tell a one-corpus record from a truncated one.

Recomputation re-hashes each named corpus from the engine's own copy and requires the set of
`corpus/` files the record generated to be exactly the set it names. Changing, removing or
substituting any one of them is a named mismatch — `corpora[<sourceId>].contentHash` — not a
silence. A record from before format 5 is reported as not comparable; the next `produce` migrates
it, as it does for every earlier format.

### 4. The engine carries every cited corpus

A rule the map states from § 172.102 is unreadable beside an engine carrying only § 172.101. Two
cited corpora committed under the same file name are refused, because the engine's `corpus/`
directory would hold one of them.

### 5. `principal` is a stamp, not a behaviour

Nothing in the factory branches on which corpus occupies the envelope's `corpus` field, beyond the
baseline having to agree with it. `principal: true` is recorded because a reader of the provenance
should be able to tell which corpus the map's own stamp covers — not because the engine treats it
differently. No behaviour was invented for it.

### 6. `pack-map.py`'s refusal is replaced with an accurate one

The publish gate now gates **every** cited corpus — declared, `committed-copy`, licence-admitted —
and refuses precisely two things: a map citing corpora read by **more than one adapter**, since a
locator run reads one grammar; and a map citing several corpora whose adapter's checker reads one
per run. `MULTI_CORPUS_ADAPTERS` names the adapters whose checker reads several, which today is
`ecfr-xml` alone. The refusal is no longer made of a claim about the whole class of checkers.

## Why not the alternatives

**Option 1 — hold a map to one corpus, and make the contract say what the factory enforced.**
Rejected. A served-document boundary is a **delivery artifact**, not a property of the rule. The
eCFR chooses to serve § 172.101 and § 172.102 as separate documents; the Hazardous Materials Table
does not stop being one rule system because of it, and a special provision is *stated* in one
document and *invoked* in the other. Splitting the map along that seam would split one logical
mapping problem into two maps that could not express the relation between them, and trial 10's
finding would become "the method cannot represent this", which would be an artifact of the
factory's plumbing rather than a fact about the corpus.

**Option 2 — give the map a per-corpus baseline.** Rejected. It duplicates pinning information the
manifest already owns, and creates **two baseline authorities** for the same bytes: a map and a
manifest that can disagree, with nothing to say which wins. The manifest is already in the
package, already per corpus, and already the thing intake reads.

**Option 3 — the manifest is the corpus-set authority.** Chosen. It accompanies the map in the
package (0015), it already declares every field pinning a corpus, it is already narrowed at
packaging to exactly the corpora the map cites, and it already carries each corpus's verification
posture. Nothing new is declared anywhere; what changes is that the factory reads all of it
instead of one entry of it.

## Consequences

- **Every committed map package is byte-identical.** Measured: `faa-part-107`,
  `hoyle-backgammon`, `srd-52-combat` and `tax-121-principal-residence` all pack to the same
  SHA-256 before and after.
- **`provenanceFormat` 4 → 5** is the one intentional migration. An engine produced before it is
  migrated by its next `produce`.
- **An unrelated manifest entry is not an engine dependency.** `pack-map.py`'s `packaged_manifest`
  already narrows the packaged manifest to exactly the cited corpora; this decision relies on that
  invariant, so it is now held by a test rather than assumed.
- **`tools/review-packet.py` moves to recipe version 3**, listing every corpus an engine was
  produced from rather than one.
- **Trial 10's map can become an engine.** With 0038 it can also pass the locator run.
- **What a map version asserts has changed** and [corpus-map.md](../corpus-map.md) says so: one
  principal corpus stamp, and a dependency on every manifest-pinned corpus it cites.
