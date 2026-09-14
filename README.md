# Rules Factory

The production apparatus that turns a plain-language ruleset into a deterministic rules
engine.

The engine is the product. This is the factory: it takes a corpus, a domain pack and an
identity, and emits a repository that is already a working engine skeleton — layered
projects, a declared rules surface, a pinned corpus, seeded decision records, agent rails,
gates, and a decomposed backlog ready to be worked.

It is **not** a template you copy and diverge from. A factory keeps a relationship with what
it produced, and every file it writes has one owner
([decision 0018](docs/decisions/0018-every-file-the-factory-writes-has-one-owner.md)).
*Generated* files, such as the code tied to the map, the pins, the gate and the backlog, are
rewritten on every run. *Managed* files (`global.json`, `NuGet.config`,
`Directory.Build.props`) hold the factory's build policy at a recipe version. A re-run updates
them, and refuses to overwrite a hand edit until the engine adopts the file or resets it.
*Engine-owned* files, such as the overlay, the solution and the projects, are written once and
then belong to the engine. Output carries provenance saying which factory version built it from
what, and which class each file is in. The factory validates its own output before declaring
success.

## Status

Design first, deliberately. This repository begins with its operating manual and the
intermediate representation that manual produces, because those settle the questions the
code would otherwise guess at. See [docs/method.md](docs/method.md) and
[docs/corpus-map.md](docs/corpus-map.md).

Nothing here builds anything yet. The method has been run three times by hand against real
corpora — see [examples/](examples/README.md), which logs what each trial changed.

## Where this sits

| Piece | Repository | Status |
|---|---|---|
| Kernel — identity, provenance, resolution | [`rules-kernel`](https://github.com/brandonifco/rules-kernel) | published, 0.2.0 |
| Corpus toolkit — adapters, locators, boundary policy | not started | |
| Domain packs — tabletop, legal | not started | |
| **Factory — intake, scaffold, sign, self-validate** | **this** | design |
| Produced engines | `deckard`, `SRD_Combat` | pre-date the factory |

The two existing engines were built by hand. They are what the method was derived from, and
the factory is finished when it can rebuild them.

## The shape of a run

```
corpus        a ruleset, in whatever format, with its licence and boundary policy
domain pack   the vocabulary its subject matter needs (dice; effective dates; none)
identity      name, prefix, repository
        |
        v
    the factory
        |
        v
engine        layered projects on the kernel, corpus manifest, rules surface,
              seeded decisions, agent rails, gates, and a backlog derived from
              the corpus map
provenance    factory version, corpus identity, packs, recipe hashes
```

## Why a manual before code

The factory's real output is not a repository — it is a *decomposition*. Turning three
hundred pages of prose into a backlog an agent can work is the part that is hard, and it is
not made easier by writing a scaffolder first. [docs/method.md](docs/method.md) is the rules
for doing it; [docs/corpus-map.md](docs/corpus-map.md) is the artifact those rules produce
and everything downstream consumes.

A predecessor attempt shipped the enforcement machinery and deleted the documents it cited,
producing sixty-one references to files that did not exist — several inside runtime error
messages. The manual comes first here partly to avoid repeating that, and partly because
writing it down is what exposes the decisions.

The open work is labelled by what it is and by what it blocks; see
[docs/backlog.md](docs/backlog.md) for the scheme and the reasoning behind the ordering.
