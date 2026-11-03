# 0088 — Cribbage play counts the cards most recently played

## Status

Accepted — 2026-11-02. Rules on five of the nine `ambiguity` blocks in the map of Hoyle's Cribbage,
pp. 34–52 ([`examples/hoyle-cribbage/`](../../examples/hoyle-cribbage/README.md),
[#704](https://github.com/brandonifco/rules-factory/issues/704)). Three of the rulings below are the
owner's, given on #704; the compulsion to play after a go is the project's. These are readings of
passages under [0005](0005-a-field-earns-its-place-by-being-checkable.md)'s `fate: decision`. **No
field, vocabulary value or check is added**, so
[0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md) does not govern it.

## Context

Hoyle writes the scores of the play for two players taking turns:

> PAIRS.--A player playing a similar card to the card last played by his adversary (as a king to a
> king, or a seven to a seven) is entitled to score _two_ for a _pair_.

> SEQUENCES, OR RUNS.--Three or more cards of any suit but forming a regular numerical succession
> … count one for each card to the last player. The sequence need not be played in regular order,
> so long as the cards exposed for the time being form an unbroken series.

> … he says, "Go." His opponent then plays any other card or cards up to that limit. If they make
> thirty-one exactly, he scores two; if not, he scores one for "last card," _i.e._ the last card
> played. This (at five-card cribbage) terminates the hand.

Four questions are left open:

1. **Which cards make a run.** "The cards exposed for the time being" can be every card of the
   current series, or the cards most recently played. Every example on pp. 36–37 is a series in
   which every card belongs to the run, so the examples agree with both readings. They part when an
   earlier card breaks the series: after nine, five, four, three, the first reading scores nothing
   and the second scores three.
2. **Whether a player can pair his own card.** After a go, one player can play two cards in
   succession. Read literally, "the card last played by his adversary" means a card matching his
   own previous card is no pair. The pair-royal ("the first player … can follow with a third
   card") and the double pair-royal ("the second player replies") are worded the same way.
3. **Whether the opponent must play after a go.** "Plays any other card or cards up to that limit"
   does not say whether he must play every card he can.
4. **The five-card play with no go.** Six cards counting less than thirty-one can all be played
   without a go. The text ties "last card" to the go, and the six-card section says the player of
   the last card scores one.

## Decision

1. **A run is counted from the most recent cards.** The player of a card scores, one a card, the
   longest run of three or more formed by that card and the cards played immediately before it in
   the current series, in any order. Nine, five, four, three scores three. (Owner's ruling.)
2. **A card pairs the card played immediately before it, whoever played it.** So do the
   pair-royal and the double pair-royal: three or four cards of one rank in immediate succession
   score six or twelve to the player of the last, after a go as at any other time. "His adversary"
   describes ordinary alternation. (Owner's ruling.)
3. **A player who can play must.** This applies before a go and after it. A player says go only
   when no card of his fits, and his opponent then plays every card he can. The go-sayer's
   compulsion is stated ("can go no further"), the opponent's is not, and a rule under which the
   opponent could keep a playable card back would let him hold it out of the play to protect the
   show, which nothing in the corpus contemplates.
4. **At five-card the last card scores one when no go is called.** The play ends with the last of
   the six cards, which scores one for last card unless it makes thirty-one, as the six-card game
   says. (Owner's ruling.)

## Consequences

`pairs-in-play`, `pair-royal-in-play`, `double-pair-royal-in-play`, `runs-in-play`, `go` and
`five-card-play-ends` carry `fate: decision` naming this record. An engine built from the map
implements these readings as though the corpus stated them. Each entry's `note` names the case that
tells the readings apart, so each reading has a test that fails under the other.

The rulings agree with how cribbage is played today. That is why the owner chose them, but it is
not why they are defensible. Each one is defensible on Hoyle's own words: his examples, the
six-card section, and the compulsion he states.
