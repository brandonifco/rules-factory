# 0016 — A map package is data, not code: the factory checks it with its own checker and never runs the package's

## Status

Accepted — 2026-09-14. Records the fix for
[#65](https://github.com/brandonifco/rules-factory/issues/65), finding 1 of the September 2026
external review. **Amends [0015](0015-a-map-is-published-as-a-versioned-package.md) and
[#51](https://github.com/brandonifco/rules-factory/issues/51)** on one point: who runs the
checker the package carries. The package format, the version rule, where each check runs and
the engine's merge are unchanged.

## Context

0015, as amended for #51, put `tools/check-map.py` inside every map package and named it in the
props item as `ConsumerChecker`, so that an engine runs `--phase consumer` with the checks its
version was published with. The factory's intake read that item too, and did the same thing:
it pulled the checker out of the `.nupkg`, wrote it to a scratch directory and ran it with
`sys.executable`, with no timeout.

That made a map package a plugin. `factory produce --package Id@Version` takes the package from
the NuGet cache or nuget.org. Nothing checked its signature, owner or hash before the script
ran. The nupkg's SHA-256 went into provenance, but only after the package had already been
trusted as code. A malicious or compromised package ran whatever it liked, with the privileges
of whoever ran the factory, and could also simply exit 0 and pass any map.

The factory's outbound supply chain is strong: pinned Actions, OIDC publishing, a digest-equal
repack. Its inbound side was the weak one.

The engine's position is different. An engine references the package at an exact version and
restores in locked mode, so NuGet pins its content hash (0015, *The overlay*). The engine has
chosen that package, byte for byte, before its build runs anything from it. The factory, when it
opens a package, has chosen nothing yet. Checking the package is the reason it opened it.

## Decision

**The factory never executes, imports or `exec`s any byte that comes from a package.** A map
package is data: JSON to parse and bytes to hash.

- **Intake runs the consumer-phase checks with the factory's own `tools/check-map.py`**, the
  file beside `tools/factory` in the factory's checkout, loaded in-process. It runs on the
  packaged map and manifest, written to a scratch directory. The packaged checker is not
  written there.
- **The package's contract is declarative.** The map's `schemaVersion` must be one the
  factory's checker reads. The set is `SCHEMA_VERSIONS` in `tools/check-map.py`, kept nowhere
  else. Intake refuses any other version and names the versions it reads. There is **no
  fallback** to the package's checker for a version the factory does not know. That fallback is
  the path by which a package becomes code again.
- **`check-map.py`'s `schema` check enforces the same set**, so a map in a version the checker
  does not read fails at publish, not only at intake.
- **The package still carries `tools/check-map.py`, and intake still requires it.** The engine's
  build runs it (0015 rule 6, #51), and a package without it is not one an engine's gate can
  use. Provenance still records its SHA-256. The factory reads and hashes those bytes and does
  nothing else with them.
- **Every child process the factory still starts has a timeout.** Today that is `git` in
  provenance and `gh` in `backlog --create`. Intake starts none.

0015's rule 6 stands as written for the engine: the engine's gate runs the package's own checker
on its merge. What changes is 0015's description of intake by implication, and #51's reasoning,
which was about the engine and was applied to the factory as well.

## Alternatives considered

**Keep running the packaged checker, but sandbox it** (no network, a read-only scratch
directory, a timeout). Rejected. The standard library has no portable sandbox, and a sandbox
only limits the damage. The script would still decide the verdict, so a package could pass its
own bad map by exiting 0.

**Keep running it, after verifying the package's signature or a pinned hash.** Rejected for
intake. nuget.org's repository signature says the package came from nuget.org, not that its
author is trusted. A pinned hash would need a list of trusted packages that the factory does not
have and that a new map would never be on. It would also still make the verdict the package's.

**Run the factory's `check-map.py` as a subprocess with a timeout.** Workable, and rejected as
extra machinery. The checker is the factory's own standard-library code, and the factory's tests
already load hyphenated tools by path. In-process, there is no interpreter to locate, no timeout
to pick, and no exit code to translate across a process boundary.

**Fall back to the package's checker for an unknown `schemaVersion`.** Rejected. It is the
original defect, reached through a version number the package sets.

## Consequences

**Intake and the engine's gate can run different checkers.** Intake uses the factory's current
`check-map.py`. The engine uses the one its package version was published with. When the two
differ, a map can pass one and fail the other. At intake there is no overlay yet, so the consumer
checks read the map exactly as published, and the package's checker passed it at publish. A
refusal at intake therefore means the factory's checks have moved since that version. The fix is
a new map version, not a factory that defers to the old checker.

**A new `schemaVersion` needs a factory release first.** A map in schema 2 is refused by every
factory whose `SCHEMA_VERSIONS` does not list 2. That is intended. The checker is what defines
what a version means.

**Provenance names the checker through the factory's commit, not a digest of its own.**
`recipes` hashes the files under `tools/factory`, and `tools/check-map.py` is outside that
directory. Intake's verdict is reproducible from `factory.commit`, and `dirty` still covers an
edited checker, but no field hashes it on its own. Whether `recipes` should include it is a
follow-up for provenance.

**The engine still executes package code**, in its own build, from a package it pinned. Whether
that is acceptable is the engine's supply-chain question, and nothing here decides it.
