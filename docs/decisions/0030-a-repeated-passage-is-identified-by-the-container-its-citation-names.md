# 0030 — A repeated passage is identified by the container its citation names, and the heading path is that container in a page-marked corpus

## Status

Accepted — 2026-09-16. Records the decision on
[#207](https://github.com/brandonifco/rules-factory/issues/207), finding 2 of trial 8
([`examples/srd-52-conditions/README.md`](../../examples/srd-52-conditions/README.md)).
**Extends [0024](0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)**,
which fixed what a quote is verbatim *of*, and **[0020](0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)**,
which fixed what a citation may *name*. Neither could say which printing of a repeated passage an
entry means. The specification is [corpus-map.md](../corpus-map.md).

## Context

`evidence` is one contiguous verbatim span (0005, #18), and
`examples/srd-52-combat/check-locators-pdf-text.py` requires **every** occurrence of it to touch
the cited page. Against a corpus that prints a sentence once, those two rules identify a passage
between them. The SRD 5.2.1 Rules Glossary does not:

- *"Speed 0. Your Speed is 0 and can't increase."* is printed under five conditions, *"Attacks
  Affected. Attack rolls against you have Advantage."* under three (five, counting the two longer
  sentences it is a prefix of), *"Saving Throws Affected…"* under four, *"Incapacitated. You have
  the Incapacitated condition."* under three. **Twenty of the conditions map's 48 effect entries
  could not quote their own sentence.** Each began its span at the condition's lead and ran forward
  through every effect between, so `petrified-saving-throws` carried four rules to state one, and
  two entries that differ by a whole rule read as two spans differing in a word of preamble.
- *Round Down* is printed identically on p. 5 and p. 187, heading included. `round-down`'s only
  unique span ran on into the **next glossary entry**: *"…tell you to round up. Save Save is
  another name for a saving throw."* That passed `check-map.py --phase publish` and the locator
  checker. **A citation every gate approved, carrying a rule the entry is not about**, which is
  worse than a refusal.

The gate's line `0 quoted texts occur more than once` was true only because every span had been
extended until it was true. The check was satisfied by the thing that broke the entries.

**The same repetition is a non-issue in the `section-designation` grammar.** Part 107 prints the
anti-collision sentence identically in § 107.29(a)(2) and again in (b), and
`examples/faa-part-107/check-locators-section.py` says why it does not matter: *"An XML element
encloses its text, so there is nothing to accept either way: a quote is inside the cited paragraph
or it is not."* What identifies a passage there is **the container the citation names**, not the
uniqueness of the words. A printed page is positional, not containing — which is why that
checker's implementation shares not a line with the page-marker one — so a page-marked corpus had
no container, and uniqueness was doing the container's job.

## Decision

**A repeated passage is identified by the container its citation names. In the
`heading-path-and-printed-page` grammar, the heading path is that container**, and the checker asks
it which occurrence the entry means, instead of requiring the quote to be unique to a page.

`check-locators-pdf-text.py`, where a quote occurs off the cited page as well as on it:

- each line of its own matching the citation's **last** heading selects the **first** occurrence of
  the quote after it; a heading with no occurrence after it selects nothing;
- a heading line counts only where the citation's **earlier** headings occur as lines, in order,
  before it;
- the citation must select **exactly one** occurrence, and that occurrence must touch the cited
  page and still have its heading near it. **Selecting none, or more than one, fails.** The checker
  reports how many printings there are and how many the path selected, and picks none of them.

Where every occurrence is on the cited page, nothing has to be identified and the check is what it
was. Nothing in the map changes: **no field, no schema version, no locator grammar.** A citation
that was already written names the container it always named; the checker stopped discarding it.

So `Rules Glossary / Round Down / p. 187` resolves — no `Rules Glossary` line precedes p. 5's
`Round Down` — and each of the twenty effect entries resolves under its own
`<Condition> [Condition]` heading. All 21 spans are now the rule the entry is about and nothing
else, and the run says so: *21 quoted texts occur more than once, 21 of them printed off the cited
page too and identified by the heading path*.

**"Under a heading" is the extraction's reading order, because that is all a flat text has.**
pdftotext emits no hierarchy: a heading is a line, and a section ends where the next occurrence of
the same words begins. That is why an occurrence belongs to the *first* heading line above it that
has no other printing of the quote in between, and why the earlier segments of the path are a
prefix test and not containment.

## Alternatives considered

**An occurrence selector on the locator** — `"occurrence": 2`, which printing within the page or
extent this entry means. Rejected. It makes a quote plus a page no longer sufficient to identify a
passage, which is a real loss in what a locator *is*, and it records a fact about the extraction's
ordinal, not about the corpus: re-extracting with a different pdftotext, or a corpus that gains a
printing, silently re-points every selector that survives. It also asks the mapper for a number
nobody can verify by reading the page, where the heading path is something the corpus prints. It
was the option trial 8's own README proposed, and one instance did not justify it (0005); the
investigation for #207 found the corpus already carries what is needed.

**A manifest declaration beside `extraction`** — this corpus repeats these passages, and the
checker then requires disambiguation rather than span extension. Rejected on two grounds. The
checker already **computes** repetition: it finds every occurrence, and its summary counts them, so
the declaration restates data the tool derives and would go stale against the text it describes
(0005's test is a field that becomes checkable, not one that repeats what is checked). And it says
only *that* a passage repeats; it supplies no way to say *which* printing an entry means, so the
mechanism above would still be needed underneath it.

**Let the map cite a heading path with no page.** Rejected. The page is what `coverage` counts and
what a reader turns to; the extent is in pages. Dropping it to solve repetition would trade a
narrow defect for the loss of the check that a mapper read what they claim.

**Keep "every occurrence" and require the mapper to extend the span.** This is the status quo, and
it is what produced `round-down`. A rule whose only compliant citation carries a different rule is
not a strict rule; it is a rule that is satisfied by being wrong.

## Consequences

**The conditions map's bytes change and every quote gets shorter.** Twenty effect entries now
quote their own sentence; `round-down` quotes *Round Down* and not *Save*. No entry's rule, scope,
clarity or dependency changed. `review.json` records this against the `legacy` exemption #8 already
carries; the blind second mapping it owes is unchanged and still owed.

**The checker's own strictness is unchanged where it was doing work.** The whole quote must occur,
exactly; the occurrence must be on the cited page; the heading must be near it; a quote that occurs
nowhere still fails; **and an ambiguous citation is refused rather than guessed at**. What was
removed is a rule that discarded the heading path — the only thing in the grammar capable of
identifying a repeated passage.

**The rule is asymmetric where a heading repeats, and deliberately so.**
`Playing the Game / Round Down / p. 5` does *not* resolve, because `Playing the Game` precedes both
printings and the path selects two. The extraction does not record where a chapter ends, so there
is no honest way to exclude the later printing; the checker says the citation identifies two
passages and stops. A corpus that needed that citation would need a heading above it that the later
printing does not fall under, or a container the text actually delimits.

**The other two grammars are unchanged, and only one of them has the defect.**
`section-designation` already names a container and resolves the case by containment: an entry
about the copy in § 107.29(b) cites `§ 107.29(b)`, and the checker requires the occurrences to sit
inside it. That extends to a citation naming a deeper constituent — `paragraph (b)(2)` of a
tax-code section is the same containment one level down — so a 26 CFR map inherits this decision
with no change to make. `tools/check-locators.py` (Hoyle, `printed-page`) matches the longest
prefix at its **first** occurrence and never checked the others; it is looser than both, its
corpus has no heading grammar, and #207 does not reach it. A page-marked corpus with no headings
would have no container and would be back where this started; none exists.

**What it does not buy.** The path says which printing the citation means, not that it is the right
passage for the entry — the limit 0024 already states. Two printings under genuinely identical
heading paths remain uncitable, which is a refusal and not a wrong citation. And a heading path is
only as good as the extraction's line breaks: a heading pdftotext does not emit as a line of its
own cannot identify anything, and the entry fails rather than passing on a different printing.
