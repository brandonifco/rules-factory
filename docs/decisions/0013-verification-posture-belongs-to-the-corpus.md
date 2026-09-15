# 0013 — How a corpus is verified, and whether a map may quote it, belong to the corpus too

## Status

Accepted — 2026-09-14. Decided by Brandon on
[#15](https://github.com/brandonifco/rules-factory/issues/15) (the second half). **Extends
[0002](0002-boundary-policy-belongs-to-the-corpus.md)**; adds no new principle. **Extended** by
[0019](0019-randomness-is-declared-by-the-corpus.md): whether an engine may draw random values
is declared per corpus on the same ground. **Extended** by
[0022](0022-a-licensed-copy-is-used-locally-by-a-named-operator-and-never-published.md): a named
operator holding the licensed copy may pack and produce from a `local-copy` corpus on their own
machine; everyone else, CI included, is still told `NOT VERIFIED`.

## Context

0002 ruled that *where a corpus lives* is a property of its licence, declared per corpus as
`boundaryPolicy`, because the two engines the method came from answer it in opposite directions
and both are right. It was decided about the factory's repository.

Moving a map into an engine asked the next question. A `contentHash` claim is only checkable
where the bytes are. `hoyle-backgammon` committed its public-domain corpus, paid the size a
second time, and its gate re-derives the hash — right there, and obviously impossible for a
`never-commit` corpus, whose engine could not verify its own baseline at all. The engine's map
copy is now hash-pinned the way the corpus is, which answers *how a consumer verifies a map*,
not *what a corpus that may not be committed does*.

Since the issue was filed, [#18](https://github.com/brandonifco/rules-factory/issues/18) made
every entry's `evidence` a verbatim span. A map now carries a few hundred quoted sentences of its
corpus. For a `never-commit` corpus **the map itself is the redistribution question**, not only
the corpus file — and that is a licence question this project cannot settle once for everyone.

## Decision

**Per corpus, recorded in the manifest. No repository-wide answer.** Verification is 0002's
question one step later, and gets 0002's answer.

### Two verification postures

Each admitted corpus declares `verification`:

- **`committed-copy`** — the corpus's bytes are committed beside the manifest, at
  `committedPath`. Anyone, CI included, can verify the baseline hash. Every corpus in this
  repository today.
- **`local-copy`** — the bytes are not in the repository. Anyone holding a legal copy points
  `envVar` at it and verifies locally. **Everyone else, including every CI run, is told
  `NOT VERIFIED` with the reason — never `ok`.**

A `never-commit` corpus is always `local-copy`. A `pin-in-repo` corpus is usually
`committed-copy`, and need not be: 0002 lets it commit "a declared derivation" rather than the
bytes the hash covers, and then the hash is verifiable only where the original is. That is why
the posture is a field of its own and not read off `boundaryPolicy`.

### Whether a map may quote its corpus

Each admitted corpus declares `quotation`:

- **`verbatim`** — entries carry `evidence` as corpus-map.md requires: one contiguous span.
- **`withheld`** — the licence does not permit the map to carry spans. No entry citing the corpus
  carries `evidence`; the span is recorded as absent, never quoted and never summarised. Its
  citations are then unverifiable by `check-locators.py`, which reports them and fails rather
  than counting them.

**This is a declaration by a person, and nothing infers it** — for the reason 0002 declined to
infer `boundaryPolicy` from `licence`: guessing wrong in one direction is a licence violation.
`never-commit` does not imply `withheld`; a commercial licence may well permit short quotation.
The field makes someone answer, per corpus, and puts the answer where a check reads it.

Stated for the corpora this repository holds:

| corpus | licence | boundary | verification | quotation |
|---|---|---|---|---|
| `hoyle-1909` | public domain (Gutenberg trademark terms on the edition) | `pin-in-repo` | `committed-copy` | `verbatim` |
| `cfr-14-107` (2026-01-01) | US government, public domain | `pin-in-repo` | `committed-copy` | `verbatim` |
| `cfr-14-107` (2020-01-01) | US government, public domain | `pin-in-repo` | `committed-copy` | `verbatim` |

### What is checked

`tools/check-map.py --only postures`, over every admitted corpus in the manifest:

- `verification` is `committed-copy` or `local-copy`; `quotation` is `verbatim` or `withheld`.
  Missing is a failure, not a default — 0002's rule for `boundaryPolicy`;
- `never-commit` is not `committed-copy`;
- `local-copy` names `envVar`;
- `committed-copy` names `committedPath`, and that file exists beside the manifest;
- under `withheld`, an entry that carries `evidence` fails, and `required-fields` does not
  demand `evidence` of it.

## Alternatives considered

**One repository-wide answer** — commit everything verifiable, or verify nothing in CI. Rejected
by the decision, for 0002's reason: the two engines answer it in opposite directions and both
are right.

**Derive the posture from `boundaryPolicy`.** Rejected: a `pin-in-repo` corpus that commits a
derivation is verifiable only locally, so the two fields come apart, and a field fully
determined by another would fail [0005](0005-a-field-earns-its-place-by-being-checkable.md)'s
test anyway.

**A third posture, `unverifiable`.** Not added. No corpus in hand is one, and a posture nobody
can verify under is what `local-copy` with no legal copy already reports: `NOT VERIFIED`.

## Consequences

**The gate reporting the posture is not in this change.** The decision's third item — an
engine's gate reports which posture is in force and never says `ok` for an unverified corpus —
belongs to the engine, and is follow-up. `check-map.py` checks the declaration; it hashes
nothing, because it does not know how to recompute any `hashDerivation`, so a committed file with
the wrong bytes passes it.

**No `withheld` corpus exists yet**, so the withheld rules are exercised only by the checker's
tests. The first licensed corpus will find what they miss — at minimum, that a map with no spans
has no `extent` coverage and no located citations, so `check-locators.py` fails it by design and
the posture that says so has to be read before that failure is.

**The map of a `never-commit` corpus may itself be unpublishable.** Where `quotation: withheld`,
`name`, `note` and `ambiguity.question` still paraphrase the corpus, and nothing here measures
how closely. That is a licence judgement and stays one.
