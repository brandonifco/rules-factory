# 0066 — The cited page chooses among the printings the heading path selects

## Status

Accepted — 2026-09-22. Records the decision on
[#436](https://github.com/brandonifco/rules-factory/issues/436), found mapping SRD 5.2.1 pp. 5–12
for [#433](https://github.com/brandonifco/rules-factory/issues/433). **Extends
[0030](0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md)**, which gave
the `heading-path-and-printed-page` grammar its container and left one case it cannot reach.
**Adds no field, no vocabulary value, no schema version and no locator grammar**; it changes one
rule in `examples/srd-52-combat/check-locators-pdf-text.py`, which is the shape 0030 itself had.

## Context

0030 states its own limit, and states it as permanent:

> The rule is asymmetric where a heading repeats, and deliberately so.
> `Playing the Game / Round Down / p. 5` does *not* resolve, because `Playing the Game` precedes
> both printings and the path selects two. The extraction does not record where a chapter ends, so
> there is no honest way to exclude the later printing.

The asymmetry is not incidental. The SRD prints *Round Down* word for word, heading included, as a
sidebar on p. 5 and again in the Rules Glossary on p. 187. 0030's rule is a **prefix** test — a
heading line counts where the citation's earlier headings occur as lines, in order, before it — and
the earlier printing comes first, so **every** heading above p. 5's is above p. 187's too. No path
can ever exclude the later printing of anything. The later can always be named; the earlier never
can.

What that cost, measured:

- **The rule was in no map's scope.** *Round Down* is the arithmetic convention every division in
  the corpus is read under. Trial 8 cites the p. 187 printing, `scope: out`, as a glossary entry.
  Trial 12, whose slice contains the p. 5 sidebar, had to leave it out and record the sidebar in
  `mapping-inventory.json` under ground `restatement` — with a note saying `restatement` is not
  the true reason and that none of the seven grounds says *no citation this grammar can write
  identifies this passage*.
- **A committed map survived by the practice 0030 abolished.**
  `examples/srd-52-combat/corpus-map.json`'s `round-down` quotes
  *"… tell you to round up. **{6}**"* — a page marker that is not a word of the rule, carried to
  make the quote unique to its cited page. That is span extension for uniqueness, which 0030
  replaced and says explicitly is not a fallback. It passed only because the entry is `scope: out`,
  where a quote beyond the extent is named and neither passed nor failed. An in-scope entry cannot
  do it.

## The failed representation

Everything the contract offers was tried, in #436 and here:

| attempt | what the map would have to assert |
|---|---|
| `Playing the Game / Round Down / p. 5` | refused: the path selects two passages |
| any longer heading path | refused for the same reason — a prefix before p. 5 is a prefix before p. 187 |
| `… round up. {6}` | that a page marker is part of the rule's words |
| quote on into the next passage | that another rule is evidence for this one — the thing 0030 was decided to stop |
| leave it out, reject the unit as `restatement` | that a mapper read the sidebar and found it a restatement, when what they found is that they could not cite it |

None is inconvenient. Each is a sentence that is false about the corpus or about the walk.

## Decision

**Where the heading path selects several printings, the cited page chooses among them.**

`check-locators-pdf-text.py`, in the branch that runs when a quote occurs off the cited page as
well as on it:

1. the path selects, exactly as 0030 says — each line of its own matching the citation's last
   heading selects the first occurrence after it, counted only where the earlier headings occur as
   lines in order before it;
2. **if it selected more than one and exactly one of those is on the cited page, that is the one**;
3. the citation must then identify exactly one occurrence, and that occurrence must touch the cited
   page and still have its heading near it. Selecting none, or more than one, fails as before.

Step 2 is the whole change, and it is bounded on every side:

- **The page narrows; it does not select.** A path that selects nothing is refused whatever is
  printed on the cited page. The heading still has to be above the printing.
- **It changes nothing where the path already decided.** One selected printing behaves as it did.
- **It decides nothing where two of the selected printings are on the cited page.** The refusal
  then says so: *selects 3 of them, 2 of those on the cited p. 1*.
- **Where every printing is on the cited page, the branch does not run at all.** That is 0030's
  rule and is untouched.

Every run says when the page did the work: *N of those needing the cited page to choose among the
printings the path selected*.

## Why this is honest, where 0030 thought nothing was

0030 asked for *a heading above it that the later printing does not fall under, or a container the
text actually delimits*, and found neither. It did not consider the other half of the locator it
already had.

A locator in this grammar is **a heading path and a printed page**. 0030 gave the path the whole of
the identification and left the page to be asserted afterwards — the quote must *touch* the cited
page, checked after the choice was made. That is what creates the asymmetry: half of the locator
was doing none of the work of locating.

The page is not being asked to *contain*, which is the thing 0030 correctly says a printed page
cannot do. It is being asked to distinguish between candidates a container already admitted. That
is what a reader does with the same citation: the heading says which passage, the page says which
printing of it — and both facts are printed on the page, verifiable by anyone holding the PDF.

Compare the alternative 0030 rejected, an `"occurrence": 2` selector: an ordinal is a fact about
the extraction, it re-points silently when the corpus gains a printing, and nobody can check it by
reading. A page number is none of those things.

## Against 0063

[0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md) governs a new map concept. This
adds none — no field, no kind, no relation, no unit, no vocabulary value, no manifest key — and
0063 exempts repairs: *a check that reads the wrong thing* is its own example. Taken as a concept
change anyway, its four steps hold: decomposition was attempted and is the table above; the failed
representation is exhibited, with the sentence each option would make the map assert; the second
reading is the blind second mapping of trial 7, which **added** `round-down` to the combat map and
whose `{6}` workaround is the artefact this record removes — a second mapper met the same wall and
worked around it the same way; and the check is `locators` in
`check-locators-pdf-text.py`, with the refusal message naming both the count the path selected and
the count on the cited page.

## Consequences

**Two committed maps change, and each carries a review of its bytes (0017).**

- `examples/srd-52-combat` — `round-down` loses the trailing `{6}` and its note says what the
  marker was for. Nothing else: same id, locator, kind, scope, clarity, dependencies, status. A
  `non-semantic` exemption over the independent verdict it departs from, which stays as
  `previousReview`.
- `examples/srd-52-playing-the-game` — gains `round-down` **in scope**, the p. 5 sidebar it had to
  leave out, and its inventory loses the `restatement` rejection that was never the true reason.
  Still a first mapping, still unreviewed, so the `legacy` exemption is unchanged in kind; its
  reason gains an eighth thing for a second reading to look at.

**One rule of this corpus is now mapped in scope where none was.** Trial 8's p. 187 entry is
unchanged and still `scope: out`.

**Nothing in the slice depends on it, and what does is in other maps.** Half damage on a successful
save and Resistance are pp. 16–17; `grid-speed-in-squares` is the combat map. `dependsOn` holds an
id in one map, so the dependency that actually exists cannot be written down. That is the
composition limit trial 12's H3 records, met from a third side, and it is not this record's to
solve.

**[#435](https://github.com/brandonifco/rules-factory/issues/435) is not dragged in.** Addressing a
run-in heading would be a second way to name the p. 5 printing, and the minimal truthful solution
did not need it: the page was already in the citation. #435 stays filed, and still says no
committed entry requires it.

**What it does not buy.** Two printings of one passage on one page, under two lines of the same
heading, are still uncitable — and are now uncitable with a message that says which half of the
locator ran out. A corpus that does that has a repetition neither half of this grammar reaches, and
it would be the case that forces the next decision.
