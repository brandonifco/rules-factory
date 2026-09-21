# 0062 — The publish gate reads the version it replaces, from a tag in this repository

## Status

Accepted — 2026-09-21. Closes
[#378](https://github.com/brandonifco/rules-factory/issues/378), found while closing
[#268](https://github.com/brandonifco/rules-factory/issues/268) and filed separately because it
is a second change. **Carries out [0015](0015-a-map-is-published-as-a-versioned-package.md)**,
which made a map's predecessor a fact, and closes the half `docs/validator.md` recorded as open.
Adds no entry field, no manifest key and no check. Changes no check's verdict on any committed
map: what changes is how much subject matter three of them have at publish time.

## Context

A check with no subject matter reports NOT VERIFIED and **passes the run**, because such a check
declares it had nothing to look at. That is right for a corpus that genuinely has no gates and no
assertions. It is wrong when the subject matter was there a moment ago and the damage is what
removed it — and both halves were measured: turning a map's only assertion into an operation
silenced `asserted-by`, removing the rule every other entry was suspended by silenced `gates`,
and the gate stayed green through both (#268).

#268 built the answer. `check-map.py --previous PATH` takes the map this one replaces, re-runs
any check that reports no subject matter against it, and fails where that check had subject
matter there. `tools/mutate-map.py` passes it, which is what moved two mutations from *signalled
only* to refusals.

`tools/pack-map.py` did not. So **the one gate that actually publishes a version — where "this
map replaces that one" is a fact rather than an argument — was the only place the option was not
used.**

## Decision

**The publish gate passes `--previous`, and the predecessor's bytes come from a
`map/<name>/vX.Y.Z` tag in this repository.**

The gate takes the highest such tag strictly below the version being packed, reads
`<map-dir>/corpus-map.json` out of it with `git show`, stages those bytes beside the map in the
private snapshot the publish checks already run against (0048), and passes the staged path.

Three sources were available. Two were refused:

* **The published package from nuget.org.** The truest reading of "the version being replaced",
  and it puts a network read inside a gate. The verdict would then depend on a remote service and
  could differ between runs — which is the defect [#408](https://github.com/brandonifco/rules-factory/issues/408)
  found in a measurement that looked reproducible and was not — and 0048 binds a package to
  artifacts whose bytes *this gate* verified, not to bytes it downloaded while deciding.
* **A path the publisher names.** It proves whatever it was handed.

A tag is offline, reproducible, and bytes a reviewer can read, at a name the tag-to-version check
already holds to the reviewed file.

**A first publish is not refused for having no predecessor.** No earlier tag means no
`--previous`, which is exactly the behaviour #268 describes for a caller who passes nothing.

**A tag that exists and does not contain the map is a refusal**, not a silent skip. The
alternative is the blind spot #268 closed reopening quietly: a predecessor not read is a set of
checks not run against one.

**Which version was compared — or that none was — is printed on every run.** "Nothing was
compared" has to be as visible as a comparison, for the same reason a check with no subject
matter says so rather than passing quietly.

**And the publish workflow checks out the whole history, so the tags are there.** Both jobs of
`.github/workflows/publish-map.yml` were shallow, and a shallow checkout has no tags — so without
this the comparison would silently not happen in the one job that actually publishes, and #378
would be closed by relocating its defect rather than by fixing it. `tools/pack-map.py` does not
refuse a checkout without tags, because packing a map from outside this repository is legitimate
and reports itself as no comparison; that is precisely why the workflow has to ask. A test holds
every checkout in that workflow to it, read from the uncommented text so the comment explaining
the line cannot be what satisfies the test that the line is there.

The `engine` job of `validate.yml` stays shallow and is not an exception to this. It packs a map
as a step in producing an engine, not to publish one, and it now says on each run that it
compared no previous version — which is true, and is the report the decision asks for rather
than a gap it hides.

## Consequences

Three of the four packable maps now compare against a predecessor, and the fourth says why it
does not:

| map | version | compared against |
|---|---|---|
| `hoyle-backgammon` | 6.0.0 | `map/hoyle-backgammon/v5.0.0` |
| `faa-part-107` | 4.0.0 | `map/faa-part-107/v3.0.0` |
| `srd-52-combat` | 2.0.0 | `map/srd-52-combat/v1.0.0` |
| `tax-121-principal-residence` | 2.0.0 | **nothing — and it is not a first version** |

The fourth row is a finding this change surfaced rather than a case it handles. There is a
`map/tax-121-principal-residence/v2.0.0` tag and no v1 tag, so a map at its second version has no
reachable predecessor here. Two situations wear the same shape — a genuine first publish, and a
predecessor that was untagged or never published — and calling both "a first publish" would hide
the second. The gate distinguishes them by the version number and says the second out loud: *the
checks that need the version being replaced did not run.*

It is deliberately not a refusal. Refusing would stop a map publishing for the state of this
repository's tags rather than for anything about the map, and the honest report is what makes the
gap actionable. Whether `tax-121-principal-residence` should have a v1 tag is a question about
that map's history, not about this gate.

What this still does not do, and 0015 still owns: say whether the version number is the right
one. The gate compares verdicts, not the size of a change, so a breaking change published as a
patch passes here exactly as it did.
