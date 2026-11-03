# 0089 — Cribbage deals from a recut, and gives three for last once

## Status

Accepted — 2026-11-02. Rules on three of the nine `ambiguity` blocks in the map of Hoyle's
Cribbage, pp. 34–52 ([`examples/hoyle-cribbage/`](../../examples/hoyle-cribbage/README.md),
[#704](https://github.com/brandonifco/rules-factory/issues/704)). The first two rulings are the
owner's, given on #704; the third is the project's. These are readings under
[0005](0005-a-field-earns-its-place-by-being-checkable.md)'s `fate: decision`, and add no concept.

## Context

> The pack of fifty-two cards is used, and the players cut for deal, the lowest dealing.

> The pack having been shuffled, the non-dealer cuts, and his opponent deals, one at a time, five
> cards to each player. Meanwhile the non-dealer scores three holes, known as "three for last,"
> and regarded as a set-off for the advantage of first deal.

1. **A tied cut** is not provided for.
2. **The order of the deal** is not stated. For a pack shuffled from a seed, the order decides
   which cards each player holds.
3. **How often three for last is scored.** The sentence comes in the middle of the procedure for a
   deal, which suggests every deal. But it is "a set-off for the advantage of first deal", and the
   advantage of first deal is gained once a game. The corpus's own play of two hands (pp. 46–49)
   scores it once. After the first deal "the score stands eight to fifteen", and A's 8 includes his
   three for last as non-dealer. After the second deal "the game now stands--A 20, B 27". B was
   the non-dealer of that deal, and 27 is his 15 and the 12 of his hand, with no three for last.
   With it he would stand at 30.

## Decision

1. **A tied cut is cut again.** (Owner's ruling.)
2. **The deal begins with the non-dealer and alternates.** (Owner's ruling.)
3. **Only the non-dealer of the game's first deal scores three for last**, at that deal, in the
   five-card game. Both arguments for this reading come from the corpus, the purpose clause and
   the worked example, and nothing in the text speaks for the every-deal reading except where the
   sentence sits.

## Consequences

`cut-for-deal`, `deal` and `three-for-last` carry `fate: decision` naming this record. The
three-for-last test is the corpus's own second deal: the illustrative hands, replayed, end at A 20,
B 27. Under the every-deal reading they would end at A 20, B 30.

The modern game gives a set-off to neither player, and the five-card game is no longer played
widely enough to have a modern rule. If a later slice of an admitted corpus states the rule, this
record is superseded by that passage.
