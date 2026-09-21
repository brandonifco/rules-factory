# 0056 — A wrapper whose heading names a division of the corpus continues nothing, and a grammar that reads one form refuses the rest out loud

## Status

Accepted — 2026-09-21. Records the decisions on
[#291](https://github.com/brandonifco/rules-factory/issues/291),
[#292](https://github.com/brandonifco/rules-factory/issues/292) and
[#293](https://github.com/brandonifco/rules-factory/issues/293), the three findings split out of
[#290](https://github.com/brandonifco/rules-factory/issues/290) and recorded as *what this does
not reach* by [0036](0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md).
**Supersedes one sentence of 0036** — that the division test reads no words — and leaves the rest
of that record standing. The specification is [mapper.md](../mapper.md).

## Context

0036 refuses a wrapper on two structural tests. It opens a division of the section if it holds an
`HD1`, a heading at the level directly below the section; or if it holds a heading of any level
while the element printed before it is not a designated paragraph. 0036 chose those two on
purpose, and rejected reading the heading's words, "because a heading's wording is not a thing the
markup states".

**One shape defeats both at once, and it is the shape that hands out a wrong address.** A wrapper
that opens a division, carries an `HD2` rather than an `HD1`, and is printed directly after a
designated paragraph passes the first test (no `HD1`), passes the second (it follows a designated
paragraph), and passes the third of 0036's refusals (no ordinary `<P>` of it prints a designator).
It then inherits that paragraph's designation, and a citation of that paragraph accepts a quote of
the division. Of the five findings in #290 this is the only one that reports `ok`.

**No admitted corpus prints it**, and this is why the fixture had to be constructed: § 172.101's
two appendices are titled `HD1` *and* follow a table, so either test refuses them; § 172.102's six
captioned provision runs are titled `HD2` and follow the designated paragraph that introduces
them, and must keep their address, because reaching them is what 0036 exists for.

**Measured, and this is the decisive measurement: no further reading of the markup separates the
two.** Across every committed corpus, the children of a wrapper are these:

| wrapper | heading | body |
|---|---|---|
| § 172.101 appendix A, B | `HD1` | 7 and 5 `P` |
| § 172.102 "A"/"B"/"N"/"W"/numeric runs | `HD2` | `FP-1`, `FP1-2` |
| § 172.102 portable-tank run | `HD2` | **34 `P`**, `MATH`, `FP`, `FP-2` |
| § 172.102 portable-tank continuation | none | `FP-1` |

Two candidate structural signals were tried against that table and both fail. *A captioned wrapper
whose body is ordinary `<P>` rather than formatted-paragraph blocks* refuses the portable-tank run
and takes `TP1`, `TP2`, `TP7` and `TP33` with it — four of the twelve provisions 0036 was written
to reach. *A captioned wrapper after which the section's designated run does not resume* refuses
whichever run is printed last, which on § 172.102 is the "W" codes and `W31`. The remaining
difference between a division and a run is what the heading says: `Appendix A to § 172.101—List of
Hazardous Substances and Reportable Quantities` against `Code/Special Provisions`.

Two further limits of the same rule were filed beside it, and both are safe — they withhold an
address rather than inventing one.

- **The adapter decides fewer tests than the checker** (#292). `tools/mapper/corpus.py` builds no
  designator tree, by design and by 0032's subsystem boundary: a unit key says where a paragraph
  sits in reading order and asserts no containment. So it cannot ask whether the paragraph a
  note's heading names is a paragraph the note is printed in. 0036 recorded the gap as one test
  wide. **Measured here, it was two:** an `<EXAMPLE>` whose head names no example was left
  unplaced by the checker and counted addressable by the adapter, and reading a head needs no
  designation at all.
- **`NOTE_HEAD` and `EXAMPLE_HEAD` each read exactly one printed form** (#293).
  `Note to paragraph (c)(11):` and `Example 4.` are the forms § 172.101 and § 1.121-1 print. A
  corpus numbering its examples `Ex. 1` would have every example unaddressable, and nothing in the
  run would distinguish that from a corpus whose examples are genuinely unreachable — which is the
  symptom [#267](https://github.com/brandonifco/rules-factory/issues/267) already reports for a
  different reason. **And one heading form was not safe:** `NOTE_HEAD`'s guard asked whether a
  heading opened `Note to paragraph`, so `Note to (c)(11):` claimed nothing the walk noticed, and
  the note inherited the designation it happened to be printed under — preferring position over
  the corpus's own word, which is exactly the reading 0036 part 4 refused.

## Decision

**A wrapper whose own heading names a division of the corpus continues nothing; the adapter asks
every placement test that needs no designation, and the one it cannot ask is bounded by a test;
and a grammar that reads one printed form refuses every other by name.** Four parts.

### 1. A third thing says a wrapper opens a division, and it reads the heading's address

`DIVISION_TITLE`, in both walks. A wrapper carrying a heading that **states an address of its
own** is unplaced, **whatever it is printed after**, under the same `division-wrapper` reason the
other two give — it is a third signal for one refusal, not a new kind of refusal, so the closed
vocabulary `extent.unreachable` declares against (0038) is unchanged and every map that already
declares an appendix declares the same thing.

Two forms, each a statement of address and not of meaning:

- the heading opens with one of the corpus's own names for a division — `appendix`, `subpart`,
  `subchapter`, `annex`;
- or it says which division it belongs *to*, by a citation — `… to § 172.101`, `… to part 107`.

**This reads words, and 0036 said it would not.** That sentence is superseded, narrowly and on the
evidence above: 0036 rejected reading words *where a reading of structure was available*, and its
worked example of the rejection is the prose test it turned down — treating a wrapper as a
continuation because the paragraph before it ends in a colon. Here no reading of structure is
available, and what is read is not prose but **an address the corpus states about itself**. That
reading is already in 0036: part 4 takes a note's address out of the note's own heading, in
preference to where the note is printed. This is the same rule applied to the same kind of
sentence one element up.

The reading is deliberately **broad**, because 0036 already settled which way this asymmetry
falls: *refusing too widely only withholds an address; inheriting too widely hands out a wrong
one.* A corpus whose captions this refuses loses coverage and reports it on every run, in the
denominator and in `no address: N`. A corpus whose appendix it misses is quotable at a paragraph
that does not contain it, and nothing says so.

### 2. The adapter asks every test that needs no designator tree

It always could ask the example-head test, and now does: a worked example whose head names no
example is `unaddressable` to the inventory as well as unplaced to the checker. The gap between
the two walks is therefore **one test, and the test is named**: `note-heading-elsewhere`, whether
the paragraph a note's heading names is a paragraph the note is printed in. That one genuinely
needs a designator path, and giving the adapter one is refused for the reason it was refused
before — a unit key asserts reading order and no containment, and two implementations of the
designator tree is the drift the two-walk tests exist to prevent.

**The asymmetry is intended, and it is now bounded mechanically rather than in prose.** The test
no longer asserts only the direction (everything the adapter refuses the checker refuses). It
asserts, over both fixtures and every committed corpus, restricted to what the descent into a
wrapper reaches, that the **only** reason code the checker gives and the adapter does not is
`note-heading-elsewhere`. A second gap opening for a third reason fails, and names it. That is
what #292's third option — record it as intended and close it — is worth only if it is held.

The restriction to *inside a wrapper* is not a hedge: at the top level the checker has a
designator tree and the adapter has reading order, so an ambiguous designator is unplaced to one
and keyed by the other. That is a different subject, and it is #290's.

### 3. Neither one-form grammar is widened, and each refusal names the words it could not read

`NOTE_HEAD` still reads `Note to paragraph (c)(11):` and `EXAMPLE_HEAD` still reads
`^Examples?\s*(\d+)?`. [#265](https://github.com/brandonifco/rules-factory/issues/265)'s proposed
standard — no new map concept without a corpus that forces it — applies directly, and a wider
expression guessed in advance is a grammar written for a corpus nobody has read. Trial 11
([#264](https://github.com/brandonifco/rules-factory/issues/264)) is the next corpus that will
print heading forms this grammar has not seen, and the expression is widened when it does, with
the corpus recorded beside it.

What a narrow reader owes instead is a **loud** refusal, and that is what changes here. Each
refusal quotes the head it could not read: `its head does not name an example: 'Ex. 1'`, `its
heading names no single paragraph this grammar can read: 'Note to (a):'`. A corpus numbering its
examples differently now prints that form on every run, in the unplaced list and in the
inventory's `no address` line, so it is a visible fact about the corpus rather than a silent
property of the expression — and it is distinguishable from #267's genuinely unreachable
examples, which the generic message was not.

### 4. A note heading that claims an address this grammar cannot read is unplaced, not inherited

`NOTE_CLAIMS_AN_ADDRESS` is widened from `^note to paragraphs?` to `^note to`. This widens the
**refusal** and not the reading: nothing new is parsed, and one more class of heading is declined.
Anything opening `Note to …` states an address. A note stating one this grammar cannot read is
unplaced, exactly as `Note to paragraphs (a) and (1):` already was, rather than being filed under
whichever designator happened to be open where the corpus printed it.

### Where each half is held

| Held by | What it holds |
|---|---|
| `examples/faa-part-107/check-locators-section.py` | `DIVISION_TITLE` and the third division test in `wrapper_reach`; `NOTE_CLAIMS_AN_ADDRESS` in `note_reach`; `head_of`, and the head quoted back in each refusal |
| `tools/mapper/corpus.py` (`ecfr-xml`) | the same expressions and the same tests in `wrapper_is_addressable`, plus `example_is_unaddressable`, the test it could always have asked |
| `tools/tests/mapper/test_mapper_nested_paragraphs.py` | that the two hold the same expressions; that the constructed shape is refused and cited by nothing; that the gap between the walks is `note-heading-elsewhere` and nothing else |

## Alternatives considered

**Leave #291 open until a corpus prints the shape.** This is #265's standard applied to a defect,
and it is the wrong way round: #265 governs *adding a concept*, and what is proposed here removes
an address rather than inventing one. A shape that hands out a wrong address is not made safe by
being hypothetical, and 0036's own asymmetry says a refusal may be broader than the evidence when
the alternative is a citation that resolves into the wrong passage.

**A structural third signal.** Two were tried against the corpus and are in the table above: the
body-tag test costs four of the twelve provisions 0036 reaches, and the run-resumes test costs
whichever run is printed last. Neither was adopted, and the measurement is why the words are read
at all. Had either worked it would have been preferred, for 0036's reason.

**Read the outermost heading level the section prints.** Rejected by 0036 and still rejected:
§ 172.102 prints no `HD1`, so its outermost level is 2 and the rule refuses all six of its runs.

**Give the adapter a designator tree, to close #292's gap.** Rejected. 0032's subsystem boundary
is part of it, but the stronger reason is that the tree would be a second implementation of
`level_of` and its ambiguity rule, in a file whose stated guarantee is that *nothing here can be
wrong about the nesting, because nothing here asserts any*.

**Move the note rule into a shared grammar module**, in the shape #281 used for the table grammar.
It would share the expression and not the gap: what the adapter lacks is the path to compare the
heading against, not the parser for the heading. The expressions are instead held equal by test,
which is what the tag tables already do.

**Widen `EXAMPLE_HEAD` to `Ex.`, `Illustration`, lettered examples.** Rejected under #265. A
corpus forces it, and then the corpus is named beside the expression.

## Consequences

**No committed corpus moves.** Every heading `DIVISION_TITLE` refuses in the committed corpora was
already refused as `division-wrapper` by the `HD1` test, and the new test is asked after the two
old ones, so no passage changes its reason and no map's `extent.unreachable` declaration changes.
No example head in any committed corpus fails `EXAMPLE_HEAD`, and no note heading in any committed
corpus opens `Note to` without matching `NOTE_HEAD`. The maps under `examples/` are byte-identical
and their locator runs, inventories and sweeps are unchanged, which is what 0017 requires of a
change that would otherwise invalidate a review.

**What was `ok` is now reported.** On the constructed fixture, `§ 1.21(h)` accepted a quote of the
appendix printed after it and now reports `unchecked`; the appendix and its paragraph are in the
unplaced list with the heading quoted, in the inventory's denominator, and on `no address`.

**The refusal can now cost coverage on a corpus nobody has read.** A caption of the form
`Provisions applicable to part 173 shipments` would be refused as a division title and its run
left unplaced. That is the broad reading taken deliberately, it fails in the direction that
withholds, and it is visible on every run — which is the difference between this and the state it
replaces.

**One sentence of 0036 is superseded and the rest stands.** The division test is no longer
tag-only and no longer word-free. Every other part of 0036 — the closed wrapper set, the descent
to any depth losing nothing, the designation a wrapped paragraph takes, the note's address, and
that a unit with no address is counted, reported and never coverage — is unchanged.
