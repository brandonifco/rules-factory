# 0067 — A composition is a union with a namespace, and what it merges it derives from the corpus

## Status

Accepted — 2026-09-23. Records the decision on
[#446](https://github.com/brandonifco/rules-factory/issues/446). **Extends
[0039](0039-the-manifest-pins-every-corpus-a-map-cites.md)** and
[0042](0042-the-mapper-walks-every-corpus-a-map-cites.md), which made a map cite several corpora
and gave a unit its identity as `(sourceId, unit)`; this is that answer one level up, for an
engine that reads several maps. **Adds no map concept** — no field, no kind, no relation, no unit,
no vocabulary value, no manifest key — so [0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md)
does not govern it: a map is unchanged, and what changes is what a consumer may do with several of
them.

## Context

Four maps read SRD 5.2.1 over one pinned text: *Playing the Game* pp. 5–12, *Combat* pp. 13–16,
*Damage and Healing* pp. 16–18, and the Rules Glossary pp. 177–191. 329 entries, one
`contentHash`. They depend on each other, and nothing could put them together:
`tools/factory/intake.py` opened one package and returned one document.

#446 measures what that costs. In short: thirteen of `srd-52-combat`'s declined entries name a
passage another of these maps holds in scope; twenty `crossReferences` items are `unmapped` for a
reason another map disproves; and nine entry ids collide across pairs, meaning different things in
different pairs.

## Decision

**Several map packages may be composed into one document. A composition is a union with a
namespace, and what it merges it derives from the corpus and reports.**

### 1. Compatibility: a composition is of readings of one ruleset over one corpus

Refused, each by its own rule and with its own message: the same package twice; two principal
corpora; one `sourceId` whose `contentHash` or `hashDerivation` differs between packages; two
`baseline` stamps; two `randomness` postures. Each is a way two packages are not two readings of
one thing, and a union of them would be a map of neither.

Overlapping extents are **not** refused. Two maps may read overlapping pages and quote different
passages, and what actually matters — two in-scope entries claiming one passage — is caught below
by the passage rule rather than by a proxy.

### 2. Identity is `(package, entry id)`

An entry id is unique in a map by the contract, and was never unique across maps. In a composition
an entry is `Srd52Combat.round-down`: the package id's last segment, a `.`, and the map's own id.
The separator is a `.` because the result must be one path segment for `overlay/<id>.json` and must
pascal to a C# member, and `Srd52Combat.round-down` is both — `overlay/Srd52Combat.round-down.json`
and `Srd52CombatRoundDown`.

Every reference **inside that package** moves with it: `dependsOn`, `enabledBy`, `suspendedBy`,
`derivedFrom`, `crossReferences[].resolvedBy` and `continuesDefinition.definedBy`. A reference to
no entry of that package is left exactly as written, because a dangling reference is
`check-map.py`'s to refuse and renaming it would hide it.

**A single package is not namespaced.** An engine produced from one map is byte for byte what it
was; nothing about four example engines, their overlays or their tests moves because composition
exists.

### 3. Supersession is derived from the corpus, and never authored

A `scope: out`, `status: declined` entry of one package is **superseded** by an in-scope entry of
another when both quote one passage and the declined entry's span lies inside the in-scope one's.
The stub exists because that map's slice stopped short; a composition holding both should answer
the rule rather than decline it.

**What says two entries are one passage is the span their evidence occupies in the corpus.** Two
candidates were tried against the four maps and both are wrong:

| candidate | what it gets wrong |
|---|---|
| the same text | merges the two printings of *Round Down*, p. 5 and p. 187 — which is the thing [0030](0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md) exists to stop |
| the same citation | misses `srd-52-combat`'s `resistance` and `srd-52-damage-and-healing`'s `resistance-and-vulnerability`, one passage under two heading paths, because a path's earlier segments are a prefix test and two mappers wrote different chapters above one line |

So the rule is the span, and it carries its own limit: **a quote the corpus prints more than once
has no span this can name.** The composition then supersedes nothing and says so. Over the three
SRD maps that is exactly the two `round-down` stubs, reported and untouched, and eight
supersessions found.

A repeated quote is reported only for a **declined** entry. An in-scope entry whose words the
corpus repeats is 0030's ordinary case — `srd-52-conditions` quotes *"Speed 0. Your Speed is 0 and
can't increase."* under five conditions and its heading path says which — and was never a
candidate to be superseded. Naming those twenty-one would bury the two that matter.

### 4. The composed document declares no extent

Two page ranges are not one page range. `--phase consumer` reads no extent
([phases.py](../../tools/mapvalidator/phases.py)), so the composed document says nothing about
coverage rather than something false. Each package's own extent was checked at publish, against
its own map, which is where the claim belongs.

## Against the alternatives

**Merge by passage, dropping ids as identity.** Closest to what a reader means, and it makes the
surviving *name* a rule nobody can predict — and it renames every overlay file and registry id in
every existing engine. Rejected: identity qualified by the thing that enumerated it is the answer
0039 already gave for units, and it costs nothing to an engine that composes one package.

**Namespace only, and merge nothing.** Safe and useless: a caller asking about Round Down gets two
entries and must know which package to ask, and the thirteen declined stubs stay declined beside
their mapped twins. The whole value of a composition is that it answers what a constituent
declined.

**Refuse id collisions, and make maps author around them.** It makes global id uniqueness a new
obligation on every future mapper, which the contract has never asked for, and the four SRD maps
would have to be edited — each edit carrying a review under
[0017](0017-a-map-change-carries-a-review-of-its-bytes.md). Rejected.

**Let the mapper declare a cross-map `resolvedBy`.** Rejected: it makes a map depend on a
*package*, which nothing in the contract does, and it asks a mapper to know which engine will
compose their map. What a composition knows, a composition derives.

## Consequences

**`factory compose` exists and `factory produce` does not yet take several packages.** The command
reads the packages, applies every rule above, and reports; `--out` writes the composed map. What a
produced engine does with a supersession — the registry answering the superseded id with the
superseding entry rather than `OutsideCurrentScope` — is the next step, and it moves
`provenance.json`'s `map` to a list of maps, which six rail tools read.

**The composition is a function of its inputs, not of their order.** Every rule above reads the
packages as a set; the order of `--package` decides the order entries are listed in and nothing
else. A provenance record of a composition must therefore name its packages in a fixed order, not
the order they were given.

**A passage the corpus prints twice is still not composable**, and now says so on every run. The
heading path resolves exactly that case for a citation (0030), and bringing a locator checker into
the composition would settle the two `round-down` stubs. It is not done here: the corpus forced
composition, and it has not yet forced the composition to resolve citations.

**Nothing about a single-package engine changes.** That is the property the namespace rule exists
to keep, and the four example engines are what would say otherwise.
