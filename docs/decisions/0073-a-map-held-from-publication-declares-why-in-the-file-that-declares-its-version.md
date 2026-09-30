# 0073 — A map held from publication declares why, in the file that declares its version

## Status

Accepted — 2026-09-29. Records the decision on
[#448](https://github.com/brandonifco/rules-factory/issues/448), taking its first option
(*honour the remedy, as a declared field*) as the change assigned to close it. **Extends
[0015](0015-a-map-is-published-as-a-versioned-package.md)**, which makes a map's version a reviewed
fact of `map-package.json` and a tag the act of publishing, with the one fact that a version may be
declared and deliberately not published. **Adds no map concept**, so
[0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md) does not govern it: the field is
package metadata in `map-package.json`, not an entry field, a manifest key or a check of the map,
and it is in neither the corpus-map schema nor the bytes of the package. What is left open is
whether to hold or to publish any particular map, which is the owner's ([AGENTS.md](../../AGENTS.md)
section 5) and which this record does not decide for any of them.

## Context

`repo-hygiene.py` reports a map whose `map-package.json` declares a version that has no
`map/<name>/v<version>` tag as a `map` leftover, and until now named two ways to clear it:
publish it, "or say in the map's README why it is held". The second was never implemented. The
function opens no README, and no sentence in one changes its verdict. A person who did what the
report said wrote a true sentence into a document and was told the same thing at the start of
every session (#448).

That is not a cosmetic fault. The tool runs at `SessionStart`, and its `CLEAN` is worth what a
leftover is worth: something to act on. A leftover that only an irreversible publish to nuget.org
can clear is a permanent line in a report whose purpose is to be empty, which is how a check
stops being read. Three maps were in that state on the day it was filed, held on purpose.

### Why not the README

Prose in a README is what [0005](0005-a-field-earns-its-place-by-being-checkable.md)
rejects in every form: a convention no check can read is one nobody can be shown to have broken.
A checker cannot hold a sentence to a meaning, and it would have to guess which README, which
sentence, and whether it is still true.

### Why not withdraw the remedy

Dropping the clause is honest and one line. It also leaves `CLEAN` unreachable while any map is
deliberately held, which is the state this repository is in and expects to stay in for a while, so
the report would be permanently non-empty and would be read that way.

## Decision

**`map-package.json` may declare `"held": "<why>"`.** It says that the version declared beside it
is deliberately not published, and gives the reason. It is read by exactly the two tools that
already read that file for the version, and by nothing else.

1. **The reason is a non-empty string.** `tools/pack-map.py` refuses a `held` that is empty,
   whitespace, or not a string, as a usage error (exit 2), whether or not `--tag` is given. A
   declaration with no reason says nothing a reader could use, and a missing reason is how a hold
   becomes a habit.
2. **A held map is not published by a tag.** `pack-map.py --tag` refuses a map that declares
   `held` (exit 1), before it gates or writes anything. `publish-map.yml` reaches the publish path
   only through `pack-map.py --tag`, in its `gate` job, and `publish` needs `gate`, so a tag pushed
   over a held map fails there and pushes nothing. The workflow needs no change and gets none.
   To publish, a reviewed commit removes `held`, and then the tag is pushed: two deliberate acts
   where a hold used to have none.
3. **A held map still packs without `--tag`.** A composed engine packs the maps it is built from,
   and every pull request's gate packs every map, so refusing there would stop the work a hold
   exists to leave alone. `held` is not written into the package, so a held map's bytes are those
   of the same map unheld.
4. **`repo-hygiene.py` reports a held map as a note, not a leftover.** The note names the version,
   that it is held on purpose, the reason as declared, and how to publish it. Two cases stay
   leftovers, because the declaration is then not true or not there: an empty or malformed `held`,
   and a `held` beside a version that is already tagged (the version is published, so it is not
   held).
5. **The leftover's remedy now names the accepted second way out**: `"held": "<why>"` in
   `examples/<name>/map-package.json`, and this record.

Whether a given map is held or published is not decided here, and no map is given a `held` by
this change.

### What this does not do

It does not stop a person removing `held` and tagging in one push. The refusal is at the tag, on
the checked-out file, and a reviewed commit that removes the field is the deliberate act; nothing
here can tell a considered removal from a careless one. It does not read the reason: a hold whose
reason is "x" is a hold. And it does not make the version any less declared: the map still
appears in `map-package.json` at the version it will publish as.

## Consequences

* The three maps whose versions are declared and untagged stay leftovers until the owner either
  tags them or records a `held` on each. Neither is done by this change.
* `CLEAN` is reachable while a map is held, and a held map stays visible as a note every session
  until it is published or its hold is removed.
* A future reason to distinguish kinds of hold (waiting on an owner, on a corpus licence, on a
  review) would be a second field or a vocabulary, and would need the same argument 0005 asks for.
  A free reason is enough while the report only has to show it to a person.
