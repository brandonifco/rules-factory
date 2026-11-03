# 0088 — A huff is read with the footnote the passage calls

## Status

Accepted — 2026-11-02. Rules on one `ambiguity` in the map of *Hoyle's Games Modernized*'s
Draughts chapter, pp. 427–446
([`examples/hoyle-draughts/`](../../examples/hoyle-draughts/README.md)). A reading of one passage,
under [0005](0005-a-field-earns-its-place-by-being-checkable.md)'s `fate: decision`. **Adds no
field, no vocabulary value and no check**, so
[0063](0063-no-new-map-concept-without-a-corpus-that-forces-it.md) does not govern it.

## Context

p. 429 defines the huff, and the next sentence calls a footnote:

> The "Huff" or "Blow" is, _before one plays his own piece_, to remove from the board any of the
> adverse pieces that might or should have taken. The "Huff" does not constitute a move.
>
> The player has the power either to _huff_, _compel the take_, or to _let the piece remain on the
> board_, as he thinks proper.[108]

p. 432 makes a capture of several men permissive, *"they may be all taken at one capture"*, and
p. 429 says a play is complete when the hand is withdrawn *"even though two or more pieces should
have been taken"*. So a play that stops part way is a completed play, and nothing in pp. 427–446
says whether the piece that made it *"should have taken"* the men it left. Nor does anything there
say whether a piece that took by one capturing play, where another would have taken more men, is
liable. Each reading of both is coherent with the chapter's text.

Footnote 108 answers both:

> A player may be huffed for not taking the full number of men he should have taken by the play
> adopted. Thus if he takes one man only, where by the same play, duly continued, he could have
> taken two, he is liable to the huff. If, however, he has the choice of two moves, by one of which
> he would take a larger number of men taken than by the other, he is under no obligation to adopt
> that move.

The Project Gutenberg edition prints its footnotes together after the book's last page, so the
footnote's own page marker is p. 475. A page extent is a contiguous range, and one reaching p. 475
would claim every chapter from Draughts to the end of the book. The map therefore holds footnote
108 as `huff-footnote`, `scope: out`, which may cite beyond the extent, and `huff-defined` carries
the question.

## Decision

**`huff-defined` is implemented with footnote 108's answer, as though the chapter had printed it.**

1. A piece that took, but stopped before taking every man the same play, duly continued, could have
   taken, is a piece that should have taken, and is liable to the huff.
2. A piece that took the full number its own play could take is not liable because another
   capturing play would have taken more. The choice between capturing plays is the player's.

## Why the question is not left open

`fate: unresolved` is for a question no reading is defensible enough to bake in. Here the corpus
answers in its own words, in a footnote the passage itself calls; the only obstacle is where the
edition put it. An engine that declined `RequiresInterpretation` on every partial capture would be
declining a question the book answers. Recording the entry as `clear` would hide that the answer is
not in the extent.

## Consequences

**One entry moves**, `huff-defined`, and `huff-footnote` is in its `dependsOn` so the backlog
carries the footnote to whoever builds it. The footnote stays `scope: out`: the engine does not
answer for the footnote as a rule of its own, only through `huff-defined`.

**What this does not settle.** Whether a page extent should be able to reach a footnote the passage
calls is a contract question, and it is not decided here: the map records the footnote where the
edition prints it and nothing new is added to the contract.
