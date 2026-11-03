# Map: Hoyle's Cribbage

A map of the Cribbage chapter of *Hoyle's Games Modernized* (1909), made to produce an engine
from ([#704](https://github.com/brandonifco/rules-factory/issues/704)). It is not a numbered trial.
It was chosen to ship a second game from the corpus the backgammon trial pinned, not to stress the
method, and the [log](../README.md) lists it for that reason.

**Corpus:** `hoyle-1909`, the Project Gutenberg text the [backgammon trial](../hoyle-backgammon/README.md)
committed. This map's manifest restates that corpus and points `committedPath` at the backgammon
directory's one copy. It does not hold a second copy, for the reason the SRD slices share theirs:
a second copy would be a second baseline to keep in step. The two manifests differ only in
`pointerPhrases`, because each map's evidence points with different words.

**Slice mapped:** pp. 34–52, the whole chapter: the five-card game and its scoring, the scoring
tables, the advice on laying out and on play, two hands played through, then the six-card,
seven-card, three-handed and four-handed games.

**Result:** 70 entries. 44 are in scope, 9 of them ambiguous, and every ambiguity is decided:
[0088](../../docs/decisions/0088-cribbage-play-counts-the-cards-most-recently-played.md) covers the
play and [0089](../../docs/decisions/0089-cribbage-deals-from-a-recut-and-gives-three-for-last-once.md)
the deal. Five of those decisions are the owner's rulings on #704. One entry, `game-won`, is
derived. 26 entries are declined:

- the advice;
- the tables and the illustrative hands, whose figures are tests;
- the scoring board;
- restatements of the game points;
- the three- and four-handed games, which this engine does not play.

Every one of the 86 paragraphs in the extent is either quoted or recorded in
`mapping-inventory.json`.

## What this corpus turned up

**Two printed totals are wrong.** The table of five-card hands on p. 39 prints three
combinations at 13 for "fifteen four, pair, and double run of three". That is 4 + 2 + 6 = 12,
which is what the table gives the same combination two rows above. The table of cribs on p. 41
prints three tenth cards in sequence and two fives at 11 for "fifteen twelve, pair, and run of
three". That is 12 + 2 + 3 = 17, and footnote 18's 14 for the case without the pair and the run
agrees with 17. Every other row adds up. `five-card-hand-table` and `five-card-crib-table` record
both misprints. The engine scores the rules, so its tests give the true figures.

**The worked example settles a rule the text leaves open.** "Three for last" is "a set-off for
the advantage of first deal". The two hands played through on pp. 46–49 score it once: B is the
non-dealer of the second deal and finishes it on 27, which is 15 + 12 with no three. 0089 reads the
rule as once a game, on that evidence and on the purpose clause.

**Footnotes have no address.** Footnote 14 says court cards pair only with their own rank, which
is a rule. It is printed with the volume's other footnotes after p. 475, outside every page
extent, and the plain-text page grammar has no address for a footnote. The entries that point at
footnotes declare the pointers `unmapped` and say why. For footnote 14, the rule it states is
already in its entry's own examples ("as a king to a king"). The map needs no new field for this,
so it is recorded here rather than filed against the contract.

**The two-handed lead is stated only by example.** No sentence of the two-handed game says who
leads. The three- and four-handed sections say "the player to the dealer's left". The two hands
played through both have the non-dealer lead, and `non-dealer-leads` takes that as the rule's
authority under 0031.

## Corrected in 1.0.1

Two notes said three for last could win a game, and asked an engine to show a win by it. Under
0089 three for last is scored only at the game's first deal, from nothing, so it cannot. The
engine's independent conformance review found the contradiction. 1.0.1 corrects those two notes
and changes nothing else.

## Review

`review.json` records an exemption, the same way the other first mappings do: no second reading
has been run. A second reader should look hardest at:

- whether `runs-in-show` is honestly `clear` for the six- and seven-card hands, whose longer runs
  no sentence names;
- whether `hand-flush`'s figures for four- and five-card hands follow from "one for each card";
- whether `game-won` should be derived or ambiguous: no sentence says the game ends the moment its
  points are made.
