# 0017 — A map change carries a review of its exact bytes, and a check refuses one that does not

## Status

Accepted — 2026-09-14. Records the fix for
[#77](https://github.com/brandonifco/rules-factory/issues/77), finding 9 of the September 2026
external review. **Enforces [0014](0014-a-map-is-checked-by-a-blind-second-mapping.md)**; the
procedure it enforces is unchanged.

## Context

0014 measured the class of defect automation does not see. Mechanical checks caught 1 of 15
injected comprehension errors, the build and its tests 0 of 9, and a blind second mapping 10 or
11 of 15. It decided that no map is used until a second mapping has been compared with it and
every disagreement resolved.

Nothing enforced that. `protect-main` requires no approvals, and `validate.sh` checked a map's
schema and citations, which is the part 0014 showed catches least. A map could change on a pull
request, pass every required check and merge with no second reading of any kind.

The repository has one maintainer. A required approval would be the author approving their own
change, which records nothing.

## Decision

**Every committed corpus map has a review record beside it, `review.json`, that names the SHA-256
of the map bytes it covers. `tools/check-map-review.py`, run by `validate.sh`, fails any map whose
current digest is not the one recorded.** A change to a map's bytes therefore fails the required
check until its review is updated too.

A review names one method:

- **`blind-second-mapping`** — the 0014 procedure. It points at the comparator's output and the
  resolution record, and names the commit and digest of the map the comparator read. That commit
  must be the one the comparator's output names. The reviewed digest is the map corrected to the
  resolutions, because that is the map that is used.
- **`independent-verdict`** — a reviewer in a separate context read the map against the corpus.
  Their verdict file must itself name the same digest.
- **`exemption`** — no review, and a stated reason. `non-semantic` is for a change that alters no
  entry's meaning and names the digest it departs from. `legacy` is for a map that predates this
  gate and names the issue under which its review is owed. The checker prints every exemption, so
  a waiver is visible in every run.

The file layout and fields are in the checker's docstring. The check reads bytes and JSON and
runs no git, so a shallow checkout gets the same answer.

### What the existing maps record

| map | method | why |
|---|---|---|
| `faa-part-107/corpus-map.json` | `blind-second-mapping` | [`blind-mapping/`](../../examples/faa-part-107/blind-mapping/README.md) compared the map at `85e416f`, resolved all 88 flags, and corrected the map to them in `a5a4d66`. The bytes have not changed since. |
| `hoyle-backgammon/corpus-map.json` | `exemption`, `legacy` | Trial 6 measured the method against this map but was not a review: its mapper had backgammon examples in their docs, its 71 flags have no resolution record, and #42 corrected only the flags scored B. |
| `faa-part-107-temporal/corpus-map-2020-01-01.json` | `exemption`, `legacy` | Never blind-mapped. The Part 107 review covered the 2026 map and text only. |

Both legacy exemptions point at [#3](https://github.com/brandonifco/rules-factory/issues/3), the
issue under which these maps are reference targets.

## Alternatives considered

**Require an approving review in branch protection.** Rejected for a solo repository: the only
possible approver is the author, and an approval says nothing about the map's bytes.

**Diff-based: fail only a pull request that touches a map without touching its review.** Rejected.
It needs the base ref, it behaves differently on push and in a shallow checkout, and it passes a
review edited for an earlier version of the map. A digest makes the same check stateless.

**Record no exemption; require a blind mapping for every change.** Rejected. It makes a reindent or
a typo fix in a `note` cost a full second mapping, which invites a second-mapping record written
for a change nobody re-read. An exemption that has to say so is the honest version.

**Fake a review for the maps that have none.** Rejected. A record claiming a method that was not
run is the defect this repository keeps finding in its own tools.

## Consequences

**The check binds a record to bytes, not a review to a map.** Editing a map and pasting its new
digest into `review.json` passes. What is prevented is changing the map without saying anything,
and what is gained is that the claim is a line in the diff naming a method.

**`non-semantic` is the author's word.** Nothing compares the two versions. A later change could
add that comparison, a field-by-field diff that proves only `note` or whitespace moved.

**Every map change now touches two files.** For a semantic change that is the cost 0014 already
set, and the second file is the smaller one.

**Two maps pass by exemption.** Until they are blind-mapped, the gate protects them only from
changing silently, not from being wrong. Any change to either one ends its exemption, because the
recorded digest no longer matches.
