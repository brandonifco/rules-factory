# 0012 — A fact the corpus implies and never states is a derived entry, and it cites nothing

## Status

Accepted — 2026-09-14. Decided by Brandon on
[#31](https://github.com/brandonifco/rules-factory/issues/31).

## Context

`stake-multiplier` was `clarity: clear` and its note asked for a demonstration of "the single
stake for a hit". **The corpus never says what a hit pays.** It says a gammon pays *"double the
agreed stake"* and a backgammon *"thrice or four times (as may have been agreed) the amount of
the single stake"*. That a hit pays the single stake is read off those two being multiples of
one stake — a good inference, and not a sentence.

It surfaced only because [#18](https://github.com/brandonifco/rules-factory/issues/18) made
`evidence` a verbatim span and there was no span to quote. The entry's own note had already
conceded as much: "an inference, not a sentence, and the only part of this entry the span does
not carry."

The issue set out three readings: `clear` is right and `evidence` may quote two passages; the
hit rate is its own entry, derived; or `clarity: ambiguous` with a recorded decision. The
first collides with [0007](0007-a-conflict-is-a-question-not-a-pair.md)'s rule that a span is
contiguous and a rule needing two separated passages is two entries. The third claims a gap
where the corpus is not silent and not vague.

## Decision

**The fact is its own entry, marked derived. `stake-multiplier` keeps only what the corpus
states.**

### The relation: `derivedFrom`

The map had three relations between entries, and none of them is this one:

| field | says |
|---|---|
| `dependsOn` | implement that before this |
| `enabledBy` / `suspendedBy` ([0011](0011-a-gate-has-a-direction.md)) | that governs whether this is reachable |
| `crossReferences` | the corpus points from this passage to that one |
| **`derivedFrom`** | **this fact is entailed by those facts** |

A derived entry is not implemented *after* its sources; it *is* them, combined. So
`derivedFrom` orders nothing, like the gate fields, and an entry that also needs another built
first says so in `dependsOn` as any entry does. `hit-pays-single-stake` depends on `game-value`
for what a hit *is*; it derives from `stake-multiplier` and `agreed-backgammon-multiple` for
what one *pays*.

### What `evidence` holds for a derived entry: nothing

**A derived entry carries no `locator` and no `evidence`.** The issue's worry was that quoting
the sources would make `evidence` mean two things depending on the entry. It does not have to:
no sentence contains a derived fact, so there is no span, and the sources' own spans — already
located and checked on their own entries — are the derived entry's citation. `evidence` keeps
one meaning, a verbatim span, on every entry that has it.

This is the one exception to "an entry without a locator is not an entry", and it is exact: an
entry is exempt if and only if it carries `derivedFrom`, and then it must carry neither field.
It is also barred from what only a passage can carry — `crossReferences`, `absentFrom`,
`beyondAdapter`, `definedElsewhere`.

### Whether `kind` needs a value: no

`kind` still answers *fact, procedure, or condition only the caller can supply* —
`hit-pays-single-stake` is a `value`, and the correspondence table reads `kind` for rows 5 and
8. A `kind: derived` would put a second carrier on what `derivedFrom` already says, and would
throw away the answer `kind` exists to give. Under
[0005](0005-a-field-earns-its-place-by-being-checkable.md), the presence of a checkable field is
the discriminator; a vocabulary value naming the same distinction adds nothing a check can read.

### What is checked

`check-map.py --only derived`:

- `derivedFrom` is a list of **at least two** entry ids. A fact that follows from one entry is
  that entry's consequence, and [#16](https://github.com/brandonifco/rules-factory/issues/16)
  discharges it as a test the entry names, not as an entry;
- every source resolves in this map, is not the entry itself, and is **`scope: in`** — a fact is
  not derived from a rule the engine does not cover, and an absent rule is `scope: out`;
- no derivation is circular;
- a derived entry carries none of `locator`, `evidence`, `crossReferences`, `absentFrom`,
  `beyondAdapter`, `definedElsewhere`.

`check-locators.py` leaves derived entries out of locating and names them in its summary, so
"all N verified" says what it did not look at.

**Chosen where the decision was silent, on 0005's test:** the two-source minimum, and the ban on
the four passage-only fields, are not in the decision comment. Both are checkable and both
follow from "the new entry cites nothing and derives from two"; a one-source "derivation" would
otherwise be a way to create an entry that escapes the locator check.

### The sweep

The backgammon map's 30 entries and the 2026 Part 107 map's 40 were read, name and note against
span, for a claim the span does not carry that is an answer the engine must give. Of the 2020
Part 107 map's 37 entries, the ten whose name, kind, clarity, evidence or note differ from the
2026 entry of the same id were read the same way; the other 27 are identical in all five. One
instance — this one.

Examined and not derived, with the reason:

| entry | what is inferred | why not a derived entry |
|---|---|---|
| `die-faces` | a die has six faces | one source: the enumeration of "all the possible throws" names every face; a consequence of one entry |
| `starting-position` | the pip numbers 24/13/8/6 | a representation of designations the span states, from one entry |
| `opening-thrower-option` | the adopted throw is never doublets | a property of two stated rules, not an answer anyone asks the engine for — #16's test, not an entry |
| `airspace-authorized` (both Part 107 maps) | Class G needs no authorization | the complement of the stated prohibition; one source |

**The sweep is a reading, and one reader did it.** Nothing detects an entry whose note claims
more than its span; that is why this instance lived through a trial, a build and a review.

## Alternatives considered

**`clarity: clear` with `evidence` quoting both passages.** Rejected by the decision: it breaks
0007's contiguity rule, and a checker that matches the longest prefix of a span would verify the
first passage and report the pair.

**`clarity: ambiguous`, `fate: decision`.** Rejected: it records a gap the corpus does not have,
and it would make a decision record carry arithmetic.

**Quote the sources in the derived entry's `evidence`, as a list.** Rejected here in favour of
no evidence at all: the sources are already entries with located spans, and a copy would be a
second place to keep them in step.

## Consequences

**The derived entry asserts an entailment nothing checks.** What is verified is that it names
two covered rules and cites nothing itself. Whether they entail it is the mapper's reading, in
`note`.

**`examples/faa-part-107/check-locators-section.py` does not know the field.** No Part 107 entry
is derived, so it has nothing to skip; a derived entry in a `section-designation` map would be
reported there as unchecked and fail the run until it learns the exemption — the safe direction.

**The engine's copy of the backgammon map migrates in the engine repository.** Its
`stake-multiplier` still names the hit case.
