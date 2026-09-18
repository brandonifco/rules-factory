# 0037. An ellipsis skips whole paragraphs and never words inside one

Date: 2026-09-18
Status: accepted
Issues: [#282](https://github.com/brandonifco/rules-factory/issues/282),
[#18](https://github.com/brandonifco/rules-factory/issues/18),
[#280](https://github.com/brandonifco/rules-factory/issues/280)

## Context

[#18](https://github.com/brandonifco/rules-factory/issues/18) is where `evidence` stopped being a
summary and became a span: thirteen wrong citations had survived because nothing held a quote to
its citation. It left one question open, and the section locator checker said so in its own
docstring — that the ellipsis rule was "proposed rather than settled, since `docs/` is not this
directory's to change".

Two documents then said opposite things out loud.

`docs/corpus-map.md`:

> **Contiguous, and no ellipsis.** The checker matches the longest contiguous *prefix* of the
> span, so a `...` in the middle silently reduces what was verified to the words before it.

`examples/faa-part-107/check-locators-section.py` did something else: it split a prose `evidence`
on ` ... ` and checked each fragment separately, in order, requiring each to sit inside the
citation. So a prose entry could quote *"A remote pilot ... must comply"* and pass with the
condition between the halves removed — and the passage nothing then checks is exactly the one a
reader would want checked.

[0035](0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md) settled the same question for a
**table row** the other way, four days ago: a row quote carries no ellipsis, because a row is
short and an ellipsis in the middle of one elides a column. The row path refuses one outright.

## What the corpus actually does with an ellipsis

The three entries in any committed map that carry one were measured before this was decided, and
none of them is the shape the warning describes. Every one uses the ellipsis to **join two
separately-cited paragraphs** — `§ 107.29(a)(2), (b)` names both halves, and each fragment is
already verified in order and in place.

| entry | what the ellipsis does | under a flat refusal |
|---|---|---|
| `moving-vehicle-operation` | joins § 107.25's lead-in to `(b)`, skipping `(a)` whole | cannot be re-quoted; needs decomposition |
| `anti-collision-lighting` | joins `(a)(2)` and `(b)`, both quoted whole | cannot be re-quoted contiguously |
| `flash-rate-sufficient` | joins `(a)(2)` and `(b)` — but **stops mid-paragraph**, dropping the intensity-reduction sentence from inside `(a)(2)` | correctly refused |

A flat refusal would therefore have broken two entries that rest on genuinely non-adjacent text,
forcing them to be decomposed into new entries. That is a *semantic* change to a map whose bytes
are pinned ([0017](0017-a-map-change-carries-a-review-of-its-bytes.md)), and it would have settled
trial 10's first hypothesis — *decomposition under the existing model is enough*
([#262](https://github.com/brandonifco/rules-factory/issues/262)) — by fiat, before the trial
designed to test it had run.

## Decision

**An ellipsis may skip whole paragraphs. It may never drop words from inside one.**

Concretely, at every ellipsis in a prose `evidence`: the text before it must end where a paragraph
ends, and the text after it must begin where one begins. The two ends of the whole quote stay
exempt, which is what `corpus-map.md` has always said in its other half — a span may be shortened
at either end and never in the middle.

A **table row** keeps the stricter rule 0035 gave it: no ellipsis at all. A row has no paragraphs
inside it to skip, so the general rule collapses to the specific one rather than contradicting it.

## Why this rule and not the other two

The rule that was written down (*no ellipsis*) and the rule that was implemented (*fragments in
order*) are the two ends of a range, and both are wrong in the same way: neither asks **what the
ellipsis is standing in for**.

- *Fragments in order* permits dropping a qualifying clause from the middle of the very sentence
  an entry rests on. That is #282's complaint and it is right.
- *No ellipsis at all* forbids quoting two paragraphs a citation already names together, which is
  not a correspondence failure — every word is verified, in order, in a paragraph the citation
  names. It buys nothing and costs a map change.

A paragraph boundary is the line between them because it is the corpus's own unit, not one this
repository invented: the checker already indexes by it, the inventory already counts by it, and a
citation already names one. Skipping a paragraph is visible in the citation, which must name every
paragraph the quote touches. Dropping words from inside a paragraph is visible nowhere.

## Consequences

- One entry changes: `flash-rate-sufficient`'s evidence extends to the end of § 107.29(a)(2). Its
  citation, kind, `assertedBy`, relations and note are untouched, and the widened span is a
  superset of the old one, so `examples/faa-part-107/review.json` records a **non-semantic**
  exemption rather than a fresh independent verdict.
- `docs/corpus-map.md` says this rule now, in place of the sentence that described the
  longest-prefix behaviour of a different checker.
- The three locator checkers agree: the section checker enforces this, the row path refuses an
  ellipsis outright (0035), and the page checker's evidence is not a span of a paragraph tree at
  all — it matches a longest contiguous prefix and reports coverage, which `corpus-map.md` names
  as the thing being described and is #18's unfinished business, not this record's.
- **What this does not settle**: whether an entry resting on two non-adjacent passages should be
  one entry or two. Trial 10 ([#262](https://github.com/brandonifco/rules-factory/issues/262))
  asks exactly that as H1, and the two entries this record leaves standing are live instances of
  it. If H1 falsifies, they are the first things to revisit.
