# 0075 — Observability is a reading of the owners' evidence, and needs no fifth component

## Status

Accepted — 2026-10-01. Records the decision on
[#591](https://github.com/brandonifco/rules-factory/issues/591). It closes the question the
observability work was asked to settle from evidence, not from taste: whether anything about a
produced engine needs a fifth platform component beside the four -- rules-corpus, rules-factory,
rules-kernel and rules-api -- or beside agent-harness, which orchestrates work on them. It adds no map concept, manifest field or engine file, so neither
[0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md) nor
[0018](0018-every-file-the-factory-writes-has-one-owner.md) governs it.

## Context

The work had two parts.

- **Reading commands.** `factory trace` ([#576](https://github.com/brandonifco/rules-factory/issues/576),
  `--html` [#580](https://github.com/brandonifco/rules-factory/issues/580)) and `factory status`
  ([#585](https://github.com/brandonifco/rules-factory/issues/585), `--verify`
  [#586](https://github.com/brandonifco/rules-factory/issues/586)) read what an engine already
  records. The trace labels every relationship recorded, derived, inferred or unknown, and lists
  every unknown as a gap; status reports the trace's evidence and gaps as counts, beside a few facts
  of its own. Neither holds state of its own or issues a verdict: `status --verify` runs
  `factory verify` and reports what it said.
- **A trial.** The trace was run on four engines that differ in the ways that matter:
  - faa-part-107: a public regulation, a repository-root engine, an XML corpus.
  - reykholt: a private licensed game, embedded under `engine/`, three corpora.
  - srd-52-combat: a public rulebook whose handler files also extend the entry's partial request type.
  - hallertau: a private licensed game, embedded.

Every relationship the trace could not establish, and every relationship it could establish only
weakly, was classified by owner:

- **A**: the factory should know it.
- **B**: an existing artifact should record it.
- **C**: rules-api / runtime.
- **D**: agent-harness / orchestration.
- **E**: no existing owner.

## The evidence

| Gap | Seen in | Class | Owner, and what was done |
|---|---|---|---|
| A review claim never rested on its entry's own tests: `reviewscope` read an overlay test under `name`, and the overlay writes `test` | all four (the overlay shape) | A | the factory's review model; fixed in [#577](https://github.com/brandonifco/rules-factory/issues/577) |
| A string nested in an interpolation hole made `blank_literals` swallow the rest of a file, and with it the members declared after it | hallertau (9 of 35 implemented entries lost their handler file) | A | the factory's lexical analysis; fixed in [#581](https://github.com/brandonifco/rules-factory/issues/581). Every required handler in all four engines now has its file inferred: 29, 122, 52 and 35 |
| Entry → handler: `implementedIn` is `{ruleset, version}` in every engine, so nothing *records* where an entry is implemented | all four | A, not B | The generator already binds every entry to `Handlers.<Member>`, required when the entry is implemented and not an assertion (correspondence row 8), and then the build fails without it. The trace derives the symbol from `semantics.contract` ([#582](https://github.com/brandonifco/rules-factory/issues/582)). No overlay field was added. The handler's *file* stays inferred: no consumer needs it recorded |
| Every implemented entry's review claim rests on every source file, for the same reason | all four | A | the factory's review model, which can anchor on the derived handler's declaring file; filed as [#584](https://github.com/brandonifco/rules-factory/issues/584) |
| Locator → corpus segment is unknown for every entry | all four | B | The publish gate resolves every citation and records none. The factory's own span function places most quotes in the plain-text corpora (reykholt 199 of 199, srd-52-combat 94 of 95, hallertau 129 of 131) but only 21 of 47 in faa-part-107's XML one, so it is not the authority. Recording the resolution in `map/verification.json` changes a published package format and means republishing maps, a person's decision, and the trace is the only consumer. Filed and held: [#583](https://github.com/brandonifco/rules-factory/issues/583) |
| Review attestations are not read by the trace | faa-part-107, srd-52-combat | A | the factory's review model reads them (`validate_attestation`); left out of the trace v1 as optional, with no consumer yet |
| Deployed API state, or which package a running service loaded | none | C | not asked for by any trace or status use |
| Which agent holds a pull request, or whether a review packet is stale | none | D | not asked for; agent-harness and the engine rails own it |

Every gap the trial found has an owner that already holds the adjacent facts. None is a fact that
spans components and belongs to none of them. The two private engines added no requirement either:
the trace states the engine's recorded distribution, and the page says first that it is as private
as the engine.

## Decision

**There is no fifth component.** No rules-platform repository, service, control plane or GUI is
created. `factory trace` and `factory status` are the observability layer, and they stay in the
factory, the component whose records they read.

1. **Observability is a reading, never an authority.** A fact shown by trace or status is read or
   computed from the artifact that owns it, at the moment it is asked for. Nothing inside an engine
   records a trace, a status or a lifecycle state -- `trace --html` writes only where its caller
   asks, and is refused inside the engine -- so nothing the engine carries can go stale. A gap the
   trace reveals is fixed in its owner, as #577 and #581 were, or closed by reading what an owner
   already establishes, as #582 reads the generator's own contract, and never by teaching the trace
   a second version of the fact.
2. **A future interface consumes the contracts.** A GUI, a dashboard or a cross-repository view, if
   one is ever built, reads `factory trace --json` and `factory status --json` and the owners'
   published interfaces. It is never an upstream dependency of rules-corpus, rules-factory,
   rules-kernel or rules-api, and never an evidence authority of its own.
3. **What would reopen this.** One of two things:
   - **Two current consumers of one Type E fact.** That is two workflows that need one fact which
     crosses components and which no existing owner can hold without a circular dependency or a
     broken boundary.
   - **One unavoidable cross-component workflow.**

   A single speculative case is filed and held, not built.

## Consequences

- The program ends here, with trace and status as its product. The gaps it found are fixed in their
  owners (#577, #581), closed by reading an owner (#582), filed with an owner (#584), held for a
  person's decision (#583), or left out of the trace's first version with no consumer (review
  attestations).
- The trace's `unknown`s are the work list for the owners, not for the trace. When #583 or #584
  lands, the trace consumes the new evidence and drops the corresponding inference. It does not keep
  both.
