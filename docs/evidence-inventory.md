# The evidence inventory

`examples/` is this repository's evidence: four corpora, seven maps, the transcripts of blind
second mappings, trial reports, independent verdicts, and the results of the injection, collapse
and validator-attack measurements. 197 tracked files, 15.3 MB, out of 19.5 MB tracked in all.

Until [#349](https://github.com/brandonifco/rules-factory/issues/349) nothing said which of it any
check reads. This document and [`tools/evidence-lock.json`](../tools/evidence-lock.json) say so,
and [`tools/check-evidence.py`](../tools/check-evidence.py) holds the tree to the lock on every
gate run — in both directions, and by SHA-256.

## The roles are measured, not declared

`check-evidence.py --measure` runs the gate and then the packer with a Python audit hook installed
in every process they start, recording each file opened **and the tool that opened it**. The
classification is therefore what the checks actually read.

Two attributions in that measurement are the reason it is worth doing properly.

**The lock's own hashing does not count.** `check-evidence.py` hashes every artifact it names, so
a measurement that counted its reads would find every artifact read and classify none of them
`archived` — the checker standing in as the evidence that something uses the bytes. It reads from
its own process and, through its tests, from inside pytest's, so the exclusion is by call stack
rather than by command. Both mistakes were made and measured before this was fixed: the first
returned "0 archived", the second returned "0 archived" again from a different direction.

**Opening a file is not the same as depending on it.** The repository-wide markdown link check
opens every tracked `*.md` to resolve its links. That is a real check, and a weak one: what it
proves about a trial report is that the report's links work. So a read by that step is recorded as
`links` and not as `checks`, and the lock keeps the distinction.

| `readBy` | what reads it | files | size |
|---|---|---|---|
| `checks` | a gate step, for what is in it | 73 | 10.6 MB |
| `checks`, `package` | that, and `pack-map.py` | 18 | 2.5 MB |
| `checks`, `links` | a gate step, and the link check | 17 | 419 KB |
| `links` | **only** the markdown link check | 44 | 892 KB |
| `package` | only `pack-map.py` | 2 | 1 KB |
| *(nothing)* | nothing the measurement could see | **43** | **1.0 MB** |

The role follows from the readers:

| role | files | size | may its bytes live outside the repository? |
|---|---|---|---|
| `release` — `pack-map.py` reads it | 20 | 2.5 MB | no: its bytes reach nuget.org |
| `active` — some other part of the gate reads it | 134 | 11.9 MB | no: a check that fetches its inputs cannot be run offline |
| `archived` — nothing reads it | 43 | 1.0 MB | yes |

`check-evidence.py` refuses a lock that gives a non-null `archive` to an `active` or `release`
artifact, and refuses a role its own `readBy` does not support. That pair of rules is what keeps a
clean checkout sufficient for normal development.

## By trial

Measured at `63a42c5`:

| directory | active | release | archived |
|---|---|---|---|
| `examples/srd-52-combat` | 6.2 MB | 1.5 MB | 476 KB |
| `examples/hazmat-172-table` | 3.2 MB | — | 7 KB |
| `examples/hoyle-backgammon` | 523 KB | 783 KB | — |
| `examples/faa-part-107` | 535 KB | 158 KB | — |
| `examples/hoyle-blind-rebuild` | 432 KB | — | 61 KB |
| `examples/blind-mapping-trial` | 141 KB | — | 207 KB |
| `examples/srd-52-conditions` | 354 KB | — | 29 KB |
| `examples/tax-121-principal-residence` | 189 KB | 87 KB | 101 KB |
| `examples/faa-part-107-temporal` | 137 KB | — | 43 KB |
| `examples/injection-trial` | 22 KB | — | 100 KB |
| `examples/validator-attack` | 53 KB | — | — |
| `examples/tax-121-build` | 31 KB | — | — |
| `examples/acceptance-4-5` | 28 KB | — | 2 KB |
| `examples/collapse-trial` | 6 KB | — | 11 KB |

Three things there are worth saying out loud.

**The two largest artifacts are load-bearing.** The 5.9 MB `SRD_CC_v5.2.1.pdf` is read by
`extract.py --check`, which hashes it and re-derives the committed text from it where the pinned
`pdftotext` is installed. The 2.9 MB `section-172.101.xml` is read by the locator checker on every
run. Neither can move without putting a fetch inside the gate.

**`blind-mapping/` is not one thing.** `faa-part-107`'s and `hoyle-backgammon`'s whole
blind-mapping directories are read; `srd-52-combat`'s and `tax-121-principal-residence`'s are read
only in part. Trial 9's `first-map.json` is held by `build-map-c.py --check`, trial 12's
`staged-inputs.json` is re-hashed by `mapper stage --verify`, and four trials' `results.json` are
read by `check-map-review.py`. The second mapper's own `blind-map.json`, the `build.py` that
produced it and the `compare.py` that compared the two are, for two of the four trials, read by
nothing.

**`archived` does not mean disposable.** It means nothing reads the bytes. Whether that is because
an artifact is spare or because a check is missing is a question for a person. Eight of the
fourteen `independent-verdict-*.json` records are read by `check-map-review.py` and six are not —
the difference is which map's review record cites them, not which review mattered.

## The artifacts nothing reads

892 KB across 42 files, listed by `check-evidence.py --roles`. By kind:

- **blind-mapping working files** — the second mapper's `blind-map.json`, the `build.py` that made
  it and the `compare.py` that compared it, for `blind-mapping-trial` (both runs), `srd-52-combat`
  and `tax-121-principal-residence`. The *result* of each comparison is read; these are what it
  was derived from.
- **trial results** — `examples/injection-trial/` (100 KB: `results.json`, `injections.py`,
  `run-trial.py`, `score.py`), `examples/collapse-trial/` (11 KB), and `blind-mapping-trial`'s two
  runs (243 KB).
- **independent verdicts** — six JSON records of a reviewer's findings, cited in the exemption
  notes of the maps they cover but read by no checker.
- **an engine brief** — `examples/hoyle-blind-rebuild/brief/` (61 KB), the documents a blind
  rebuild was given.

Their bytes are now pinned by the lock. Before it, nothing hashed them: a corpus is pinned by its
manifest's `contentHash`, a staged blind input by its record's digests, trial 9's first mapping by
`build-map-c.py --check`, and these by nothing at all.

## On moving them out of the repository

[#349](https://github.com/brandonifco/rules-factory/issues/349) asked whether `archived` material
should go to a versioned, content-addressed, immutable archive, with
[`tools/fetch-evidence.py`](../tools/fetch-evidence.py) retrieving and hash-verifying it.

**Nothing has been moved, and the number is why.** The movable set is 892 KB: 4.8% of what is
tracked, and about 1.7% of a clone once the 33 MB of history is counted. Against that: an external
store to keep alive for as long as the decision records that cite it, a fetch inside the
verification path, and a reviewer who cannot follow a link to a trial report without a network.

The mechanism exists and is tested anyway, so the decision stays reversible with a measurement
rather than a rewrite. `fetch-evidence.py --verify` reads each artifact wherever the lock says it
lives — this repository today, `file:` or `https:` if one is ever moved — hashes it against the
lock, and refuses an identifier it cannot resolve rather than skipping it.
[`tools/tests/test_check_evidence.py`](../tools/tests/test_check_evidence.py) exercises the `file:`
path end to end: fetched and verified, refused when the bytes differ, refused when the file is
absent, refused when the scheme is one the tool does not know.

**Not Git LFS**, whichever way that decision goes. LFS makes the bytes a property of the clone
rather than of the artifact: a reviewer with a partial fetch gets a pointer file that reads like a
document, and there is no digest in the repository to hold the bytes to. A content-addressed
identifier plus the SHA-256 in the lock can be checked by anyone holding the bytes, with no
special client.

## Keeping this true

```bash
python3 tools/check-evidence.py            # the gate's step: lock against tree, both ways, by hash
python3 tools/check-evidence.py --roles    # the classification and its totals
python3 tools/check-evidence.py --measure  # re-run the readers and rewrite the lock (~2 min)
python3 tools/fetch-evidence.py --verify   # verify every artifact wherever the lock says it lives
```

Evidence added to `examples/` fails the gate until `--measure` has been run: the lock does not
mention it, and an artifact the lock does not mention is what this exists to catch. `--measure`
accepts a gate run that failed, as long as it ran every step, because re-measuring after adding an
artifact necessarily happens while the evidence step is failing — and it prints which steps failed
while it was watching. A role that changes, because a check started or stopped reading something,
is printed as a line naming the artifact and both roles.
