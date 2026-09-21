# 0051 — Every evidence artifact says which check reads it, and the answer is measured

## Status

Accepted — 2026-09-20. Records the decision on
[#349](https://github.com/brandonifco/rules-factory/issues/349).
**Extends [0017](0017-a-map-change-carries-a-review-of-its-bytes.md)**, which pinned a map's bytes
to a review, to the evidence beside it that no review or manifest ever pinned.
**Sibling of [0049](0049-the-gate-can-say-which-of-its-checks-a-change-owes.md)**: that one says
which checks a change owes, and this says which artifacts a check reads. Together they are the
two halves of being able to state what a green run examined.

## Context

`examples/` is 189 tracked files and 15.5 MB of the repository's 18.7. Some of it is read on
every gate run, some only when a package is built, and some by nothing at all. Nothing said which
was which, and three things followed:

- **Nothing could be retired.** A transcript may be what a decision record rests on, or a file
  nobody has opened since it was written. Telling them apart meant reading every checker.
- **Nothing hashed the spare.** A corpus is pinned by its manifest's `contentHash`, a staged blind
  input by its record's digests, trial 9's first mapping by `build-map-c.py --check`. The 892 KB
  no check reads was pinned by nothing: its bytes could change and no run would notice.
- **No claim about coverage could be made.** "The evidence suite passed" says nothing without a
  list of what the suite is.

## Decision

`tools/evidence-lock.json` names every tracked artifact under `examples/` with its SHA-256, its
size, the parts of CI that read it, and the role that follows.
`tools/check-evidence.py` is a gate step at every scope — 40 milliseconds over 15.5 MB — and holds
the tree to the lock **in both directions**: an artifact the lock does not mention and a lock entry
naming a file that is gone are each a failure.

| role | reader | may its bytes live outside this repository? |
|---|---|---|
| `release` | `tools/pack-map.py` | no: its bytes reach nuget.org |
| `active` | some other part of the gate | no: a check that fetches its inputs cannot run offline |
| `archived` | nothing | yes |

**The role is measured, not declared.** `--measure` runs the gate and the packer with a Python
audit hook installed in every process they start, recording each file opened and the tool that
opened it. A hand-written role is a claim about what a checker does, and this repository has twice
shipped a checker that did not do what its author believed.

Two attributions decide whether the measurement means anything, and both were wrong on the first
attempt:

- **The lock's own hashing does not count as a read.** `check-evidence.py` hashes every artifact it
  names. Counting that found every artifact read and classified nothing `archived` — the checker
  standing in as the evidence that something uses the bytes. It reads from its own process and,
  through its tests, from inside pytest's, so the exclusion is by call stack and not by command.
- **Opening a file is not depending on it.** The repository-wide markdown link check opens every
  tracked `*.md` to resolve its links. That read is recorded as `links` rather than `checks`, so
  the 884 KB whose only verification is that its links resolve stays visible as exactly that. The
  lock refuses a role its own `readBy` does not support.

## The extraction #349 asked about is not done, and the number is why

#349 asked whether `archived` material should move to a versioned, content-addressed, immutable
archive. The movable set is **892 KB — 4.8% of what is tracked, about 1.7% of a clone** once the
33 MB of history is counted. Against that: an external store to keep alive for as long as the
decision records citing it, a fetch inside the verification path, and a reviewer who cannot follow
a link to a trial report without a network.

`tools/fetch-evidence.py --verify` exists and is tested anyway, so the decision stays reversible
with a measurement rather than a rewrite. It reads each artifact wherever the lock says it lives —
this repository today, `file:` or `https:` if one is ever moved — hashes it against the lock, and
refuses an identifier it cannot resolve rather than skipping it. The `file:` path is exercised end
to end, including the three refusals, so a move would not begin by trusting an untested mechanism.

**Not Git LFS**, whichever way that goes. LFS makes the bytes a property of the clone rather than
of the artifact: a partial fetch yields a pointer file that reads like a document, and there is no
digest in the repository to hold the bytes to.

## What this does not decide

- **Whether an `archived` artifact should exist.** The lock says nothing reads it. Whether that
  means it is spare, or that a check is missing, is a question for a person — and for six
  independent verdicts and the injection trial's results, it is a live one.
- **Whether the bytes are right.** It holds them to what they were, not to what they should be.
- **Reads from outside Python.** `dotnet` and `pdftotext` open files the audit hook does not see.
  Every corpus they touch has a Python reader too — `extract.py` hashes the PDF before `pdftotext`
  is asked for it — so nothing is `archived` because a non-Python reader was missed. An artifact
  read *only* by a non-Python tool would be, and `--measure` reporting a role change is where that
  would surface.
