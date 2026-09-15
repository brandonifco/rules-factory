# 0015 — A map is published as a versioned package, checked before it can be a version, and overlaid by its engine on three fields

## Status

Accepted — 2026-09-14. Records what Brandon decided on
[#27](https://github.com/brandonifco/rules-factory/issues/27) (publish maps as versioned
artifacts, stop vendoring), [#17](https://github.com/brandonifco/rules-factory/issues/17) (an
engine owns a fixed set of fields, checked by an offline merge) and
[#39](https://github.com/brandonifco/rules-factory/issues/39) (structure is checked at publish;
the engine runs only the checks that read its own fields). The package format, id, version rule
and the list of which check runs where are this record's. **Widens #17's field lock from two
fields to three** (`tests`); see *The overlay*.

**Amended 2026-09-14** for [#51](https://github.com/brandonifco/rules-factory/issues/51)
(Brandon: ship the consumer-phase checks inside the map package). The package now carries
`tools/check-map.py`, and the engine runs `--phase consumer` from the restored package rather
than from a copy of its own. The table in *The artifact*, the bump rule for package contents,
rule 6 of the merge and the vendoring alternative changed; nothing else did.

**Extended by [0022](0022-a-licensed-copy-is-used-locally-by-a-named-operator-and-never-published.md)**
(#105): `pack-map.py --licensed-copy-exception` packs a `local-copy` map locally for an
allowlisted operator, into a package marked unpublishable. Publishing a `local-copy` map stays
refused, and `publish-map.yml` now refuses one, and a marked package, on its own account.

**Amended by [0023](0023-a-map-package-is-licensed-as-its-corpus-and-the-factory-are.md)**
(#106): the package carries `LICENCE.txt`, the nuspec names it with `<license type="file">`
instead of the `Apache-2.0` expression, and `map-package.json` names the map's corpus terms file,
which must restate the manifest's `licence`. The next versions of `hoyle-backgammon` and
`faa-part-107` are major for it.

**Amended by [0016](0016-a-map-package-is-data-not-code.md)** (#65): the packaged checker is for
the engine's build only. The factory's intake never runs it; it checks a package with its own
`tools/check-map.py` and refuses a `schemaVersion` that checker does not read.

## Context

A vendored map goes stale without failing (#27). The backgammon map moved twice in one day and
the engine was rebased by hand both times. For about four hours its gate enforced a map the
factory had already retracted, and everything was green. The engine's copy had also dropped a
sentence from `stake-multiplier`'s note, which a hash pin shows in a diff but nothing fails on
(#17). And the engine never checked its map's structure. Trial 5's `dependsOn` cycle passed its
gate green (#39).

The project already solved this once, for code. `rules-kernel` is referenced from nuget.org and
never copied, and an outdated dependency shows up in every tool that already exists. A map is
the same kind of thing: a shared artifact with consumers.

## Decision

### The artifact

**One NuGet package per map, published to nuget.org.** A map is a directory under `examples/`
holding exactly one `corpus-map*.json`, one `corpus-manifest*.json` and a `map-package.json`
that states the version. [`tools/pack-map.py`](../../tools/pack-map.py) builds the package:

| path in the package | what it is |
|---|---|
| `map/corpus-map.json` | the reviewed map, **byte for byte** |
| `map/corpus-manifest.json` | the manifest entries for the corpora the map cites. It is the manifest's own bytes when that is all the manifest declares, which is true of every map today |
| `tools/check-map.py` | the checker, **byte for byte** from the commit that was gated. It imports only the standard library, so this one file is everything `--phase consumer` needs. The engine runs the status-dependent checks from here (#51) |
| `build/<id>.props` | one MSBuild item, `RulesFactoryMap`, pointing at the map and manifest, with `ConsumerChecker` (the path of `tools/check-map.py`), `PackageId` and `PackageVersion` as metadata. An engine's gate finds the map and its checker without knowing where NuGet extracts packages |
| `LICENCE.txt` | the package's licence (0023): the corpus's terms for the quoted text, from the map's corpus terms file, and Apache-2.0 for the rest. The nuspec names it with `<license type="file">` |
| `<id>.nuspec` | id, version, and a description stating the corpus, baseline, `asOf` and `schemaVersion`. `<repository commit>` names the factory commit that was gated |

The corpus text is not in the package. How a consumer verifies a corpus is
[0013](0013-verification-posture-belongs-to-the-corpus.md)'s question. Its answer is declared
per corpus, and putting a corpus into a public registry is a licence decision that no packaging
rule should make.

**The build is deterministic.** Given the same inputs, the package has the same bytes. Entries
are stored uncompressed, with fixed timestamps and attributes, in a fixed order, and the
core-properties part is named from a content digest. `dotnet pack` was measured and is not
deterministic: two packs a second apart differed in every timestamp and in the random part name,
and the package also records the NuGet client version. So packing is a script, and packing needs
no .NET SDK. The publish workflow uses determinism: its credentialed job re-packs and refuses to
push unless it gets the digest the gate job checked.

### The package id

**`RulesFactory.Maps.<MapName>`**, where `<MapName>` is the map's directory name in PascalCase:
`hoyle-backgammon` gives `RulesFactory.Maps.HoyleBackgammon`, and `faa-part-107` gives
`RulesFactory.Maps.FaaPart107`. The directory name must be lower-case kebab-case.

The id names the **map**, not the corpus. One corpus can have several maps, as
`faa-part-107` and `faa-part-107-temporal` already show, and they are different artifacts. A map
that has to stay available at an old baseline alongside the new one is a separate directory and
a separate package. Replacing a baseline inside one package is a major version (below).

### What a version asserts

A published `id@version` asserts four things:

1. **These bytes, forever.** nuget.org lets a version be unlisted but never replaced or deleted.
2. **They passed the publish gate** at the commit named in the nuspec (below).
3. **The map is true of exactly one corpus baseline**: `baseline.contentHash` under
   `baseline.hashDerivation`, and `baseline.asOf` where the corpus is revised over time. A map
   with no `asOf` is of a timeless corpus. That means timeless, never unknown
   ([corpus-map.md](../corpus-map.md)).
4. **It is written in `schemaVersion`** as that file states it.

**The baseline and the schema are read from the file, not encoded in the version number.** A
date-shaped version (`2026.1.1`) was rejected. A timeless corpus has no date, and two corrections
to one baseline need different versions. A date would also say nothing about whether an engine
built on the previous version still merges. The version number answers that compatibility
question, and the baseline and schema are among the inputs to it.

### What counts as a major, minor or patch change

The question every bump answers: **could an engine that was correct against the previous
version be wrong under this one, or could its overlay stop merging?** Minor and patch are closed
lists. **Any change not listed there is major**, including a field added to the schema later,
until a record lists it.

**Patch** is prose that no check and no engine reads:
- an entry's `name` or `note`;
- a manifest corpus's `title`, `edition` or `retrievedFrom`.

**Minor** is additive, or a corrected citation for an unchanged rule claim:
- a new entry that no existing entry names in any relation;
- `extent` widened;
- a new `crossReferences` item on an existing entry;
- `evidence` or `locator.citation` corrected on an entry whose other fields do not change.

**Major** covers everything else. In particular:
- `schemaVersion` changes;
- the baseline changes: `contentHash`, `hashDerivation` or `asOf`;
- an entry is removed or its `id` changes. This is what breaks an overlay, and the merge check
  fails on it;
- on an existing entry: `kind`, `scope`, `clarity`, anything in `ambiguity`, `dependsOn`,
  `enabledBy`, `suspendedBy`, `derivedFrom`, `beyondAdapter`, `definedElsewhere`, `absentFrom`,
  `locator.sourceId`, an existing `crossReferences` item, or the upstream `status`,
  `implementedIn` or `tests`;
- `extent` narrowed;
- a manifest corpus's `adapter`, `locatorGrammar`, `licence`, `boundaryPolicy`, `verification`,
  `quotation`, `randomness` ([0019](0019-randomness-is-declared-by-the-corpus.md)) or `references`.

**Package contents other than the map and manifest are not listed either, so they are major.**
That includes adding `tools/check-map.py` (#51) and any later change to its bytes: a changed
status-dependent check can fail an overlay that passed before, and a changed message cannot be
told apart from that without a record that lists it.

A correction to what a rule says is major even when the old reading was wrong. Code was built on
the old reading, and the version bump is how its engine finds out.

The tag is **`map/<map-directory>/v<version>`**, and it must equal `version` in that map's
`map-package.json`. The version is a reviewed change on `main`, and the tag only confirms it, as
in `rules-kernel`. Maps are versioned independently of each other.

### Where each check runs

**Structure is checked before a map can be a version. The engine re-runs only the checks its
own overlay can change.** The split lives in `STATUS_DEPENDENT` in
[`tools/check-map.py`](../../tools/check-map.py) and is not maintained anywhere else, this table
included. `tools/tests/test_check_map.py` holds it in both directions. It sets the overlay fields
every way an overlay can and requires that each structural check keeps its verdict and that each
status-dependent check can be changed.

| check | runs | why |
|---|---|---|
| `schema`, `required-fields`, `unique-ids`, `references`, `no-cycles`, `gates`, `derived`, `manifest`, `postures`, `exclusions`, `decision-records`, `conflicts`, `cross-references` | **publish** | They read no overlay field, so no overlay can change their verdict. `required-fields` reads whether `status` is present, and an overlay must set it, so it cannot remove it |
| `check-locators.py` (and the eCFR section checker) | **publish** | They read `locator`, `evidence`, `extent` and `absentFrom`, and need the corpus |
| `vocabulary` | **publish and consumer** | `status` is one of its closed vocabularies. #39's list missed this one, and the split test found it |
| `status` | **publish and consumer** | `implementedIn` appears exactly when the entry is `implemented`, with its `tests`, each with a mutation |
| `absent` | **publish and consumer** | An `absentFrom` entry must be `status: declined` |
| `correspondence` | **publish and consumer** | Rows 2 and 5 depend on `status`, and a `declined` entry must have a runtime row |

`check-map.py --phase publish` (the default) runs every check. `--phase consumer` runs the four
status-dependent checks. **The consumer runs them from the package** (`tools/check-map.py`, the
props item's `ConsumerChecker`), so the checks an engine runs are the checks that version was
published with, and a change to one reaches the engine as a new version rather than not at all
(#51). **The publish gate is `tools/pack-map.py`.** It runs `check-map.py
--phase publish` and then the locator checker for the corpus's adapter, and it writes no package
if either fails. A map citing more than one corpus, a corpus that is not `committed-copy`, or an
adapter with no locator checker is refused as NOT VERIFIED. No option packs a map without the
gate. [`publish-map.yml`](../../.github/workflows/publish-map.yml) runs the gate on the tag, and
`validate.sh` runs it on every pull request, so a map that could not be published is found before
a version number is chosen for it.

### The overlay, and the offline merge check

**An engine may set exactly three fields on the map it consumes: `status`, `implementedIn` and
`tests`.** Any other difference from the package is drift, and the gate fails on it.

#17 locked the set at two fields and said that needing a third would reopen the decision. This
record reopens it for `tests`, with the evidence. Since #2, `tests` is **required and non-empty
when `status` is `implemented`** ([corpus-map.md](../corpus-map.md), the `tests` row;
`check-map.py`'s `status` check). Each item names an engine test and the mutation that turned it
red, and only the engine knows those. With two fields, an engine could set `implemented`, fail
`status` for missing `tests`, and have no way to add them. It could never honestly close an entry
(method.md, Phase 8). **Brandon should confirm this reading.**

The overlay is the engine's own file: `{ "<entry id>": { "status": …, "implementedIn": …,
"tests": [ … ] } }`. `merge(package, overlay)` is defined as follows, and each rule is part of
the check:

1. **Every overlay key names an entry in the package map.** An upstream rename or removal fails
   here, not silently.
2. **Every overlay item sets `status`, and holds no key outside the three.**
3. **For a named entry, the three fields come from the overlay alone.** Remove them from the
   upstream entry, then set the ones the overlay item carries. An overlay can therefore state
   any build state, including "no longer implemented". Every other field of the entry stays
   upstream's, byte for byte in value.
4. **An entry the overlay does not name is upstream's, verbatim.** So are the entry order and
   the top-level fields: `schemaVersion`, `corpus`, `baseline`, `extent`.
5. **If the engine commits a materialised `corpus-map.json`, it must equal the merge as parsed
   JSON.** Computing the merge in the gate and committing only the overlay is simpler, because
   then there is no second copy to drift.
6. **The package's own `tools/check-map.py --phase consumer` passes on the merge.** Not a copy:
   a copy does not change when the factory's checks do.

It is **offline**. The inputs are the restored package and a file in the engine's own repository.

**The engine's other obligation is that it has the exact published version.** It references the
package at an exact version (`Version="[1.0.0]"`) and restores with a lock file in locked mode.
NuGet then pins the package's content hash, and the engine does not hash the map itself. That
lock-file hash is of the package **as nuget.org serves it**, which includes the repository
signature nuget.org adds. It is therefore not the `sha256` that `pack-map.py` prints. The files
under `map/` are identical in both.

## Alternatives considered

**Keep vendoring and add a scheduled staleness check** (#27 as filed). Rejected by the decision.
It detects what a dependency makes visible, and it only works if someone reads its output.

**Vendor or generate `check-map.py` into each engine** (#39's three routes). Rejected. A map that
fails structure never becomes a version, so the engine needs only the four status-dependent
checks, and #51 found what happens when it copies them: `hoyle-backgammon` ran a hand copy that
nothing told when `check-map.py` changed. The package carries the checker instead (#51).
**Recording a checker version in the package for the engine gate to compare** was the other
option on #51 and was not chosen: it detects a stale copy but still leaves the engine
maintaining one.

**`dotnet pack` over a pack-only project.** Rejected on measurement: it is not deterministic
(above). It also ties every local pack to one SDK. `rules-kernel`'s `global.json` pins 10.0.112
with roll-forward disabled, and this machine has 10.0.111.

**GitHub Packages.** Rejected for `rules-kernel`'s reason. It cannot serve NuGet anonymously, so
every engine would need a token to restore a public map.

**Version per corpus baseline in the id** (`RulesFactory.Maps.FaaPart107.20260101`). Rejected.
The id would change with every amendment, so a consumer could not see through its dependency
tooling that a newer baseline exists, and that visibility is what #27 decided to get.

## Consequences

**Nothing enforces the bump.** Nothing compares a new map against the previous published version
to check that the major/minor/patch rule was followed. The rule is written above, and it is
mechanical enough to check with a map differ: every field is assigned a class and anything
unlisted is major. That check is follow-up. Until it exists, the version in `map-package.json`
is a reviewed claim.

**A licensed corpus's map cannot be published from CI yet.** A `local-copy` corpus's citations
cannot be read by a publish job, so the gate refuses the map as NOT VERIFIED. This is intentional
for now. The first licensed corpus will reopen it, together with 0013's open question of whether
such a map can be redistributed at all. It did (#105), and the answer for now is 0022's: packed
locally by a named operator, never published.

**Configuring Trusted Publishing on nuget.org is an account setting,** and nothing in this
repository can do it. Until the policy exists for this repository and `publish-map.yml`, a tag
passes the gate and fails at login, and nothing is published.

**`hoyle-backgammon`'s migration off its vendored copy is the engine's change**, not this
record's (#27's third to-do). The factory side is a package the engine can depend on. The first
version was `1.0.0`. `2.0.0` is the first to carry the checker (#51): an added package file is
not on the minor or patch list. `3.0.0` changes three things, each major on its own:
- the checker's bytes (#79's `SCHEMA_VERSIONS`, and #87's build of `tools/check-map.py` from
  `tools/checkmap/` with a generated header), and a changed package file is not on the minor or
  patch list;
- the manifest's `randomness` field (0019);
- the map, corrected by the blind second mapping (#95).

`4.0.0` corrects `game-value`'s ambiguity question to name both cases where
the gammon and backgammon conditions overlap (#102); a correction to what the map says is major.
`faa-part-107`'s first version was `1.0.0`; `2.0.0` is the same checker change
and the same `randomness` field (0019). Its map also changed: the section-designation `extent` and
introductory-text citation (0020) and the waiver gate (#61, 0021).
`srd-52-combat`'s first version was `1.0.0`, carrying its `LICENCE.txt` from the start (0023).

Each package's next version is one major bump for everything merged since its last publish; the
checker's bytes changed in all three (0024, 0025, 0026), which is major on its own.
- `hoyle-backgammon` `5.0.0`: the packaged `LICENCE.txt` and `map-package.json`'s `licence`
  (0023, #110); `assertedBy` on `agreed-backgammon-multiple` and `draws` on `opening-roll` and
  `throw-two-dice` (0025, #120); the manifest's `pointerPhrases` (0026, #121).
- `faa-part-107` `3.0.0`: the packaged `LICENCE.txt` and `map-package.json`'s `licence` (0023,
  #110); `assertedBy` on its ten assertions (0025, #120); the manifest's `pointerPhrases`, the new
  `scope: out` entry `knowledge-recency` (§ 107.65) with `night-training-completed` depending on
  it, and `crossReferences` changed on four entries (0026, #121). 47 entries.
- `srd-52-combat` `2.0.0`: the manifest's `quotedText`, the extent's `endsBefore` and `extraction`
  on six entries (0024, #119); `assertedBy` on three assertions and `draws` on four operations
  (0025, #120); the manifest's `pointerPhrases`, four new `scope: out` glossary entries
  (`difficult-terrain-glossary`, `invisible-condition`, `cover-glossary`, `disengage-action`), two
  existing ones' evidence extended, and `crossReferences`/`dependsOn` added on in-scope entries
  (0026, #121). 95 entries.

**corpus-map.md's "Where the map lives" changes.** A map is published from the factory and
consumed as a package. The engine owns only its overlay.
