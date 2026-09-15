# 0002 — A game begins from a position the caller asserts

**Status:** accepted; amended in part by
[0003](0003-the-engine-derives-the-starting-position.md).

> **Amendment.** The Context below is written against a version of `corpus-map.json` that has
> since been retracted. `starting-position` is not declined, the engine derives it, and
> `Setup.StartingPositionFromCorpus()` no longer returns a `Resolution` — so the first bullet
> of the Decision, and the first rejected alternative, no longer describe the engine. The rest
> stands, for the reason the Context's own parenthesis anticipated: a caller may want to start
> from a position that is not the corpus's, and most do. Read 0003 for what changed.

## Context

`starting-position` is `declined`. The map records it as beyond the plain-text adapter's
reach, and by the correspondence table that is `MissingRulesData` at runtime.

This is not a peripheral entry. It is the one fact without which no game can begin, and an
engine that cannot begin a game cannot demonstrate the other twenty in-scope entries either.
The decline threatens to spread from one rule to all of them.

(The map is wrong about this entry — the arrangement is stated in prose on p. 272. See
finding 1 in `MAP-FINDINGS.md`. This decision is about what the engine does given the map as
written, and it would be the right shape even if the entry were corrected, because a caller
may want to start from a position that is not the corpus's.)

## Decision

The engine has no starting position and never invents one.

- `Setup.StartingPositionFromCorpus()` returns `Resolution<Position>` and always declines,
  `MissingRulesData`, citing `starting-position` and p. 271. The decline is a reachable
  answer, not a hole.
- `Game.Play` takes an `AssertedPosition`: a `Position`, the name of whoever is answerable
  for it, and an optional `SourceLocator` for where they say it came from.
- The assertion is carried into `GameRecord.Start`, so a result is never separated from the
  thing it depended on that the corpus did not supply.
- `Position.Create` validates the assertion against the rules that do exist — fifteen men a
  side (`men-count`), and no point holding men of both players.

The test suite is a caller like any other. It asserts the arrangement it read from the
corpus's prose, cites p. 272 in the assertion's `Justification`, and says in
`Corpus.StartingPosition`'s remarks that it is doing so.

## Why

**This is the shape the method already prescribes for a fact no computation settles.** The
corpus-map document says an engine owes an assertion four things: demand it, attribute it,
record it alongside the outcome, and never infer it. It says that about `kind: assertion`,
and `starting-position` is `kind: value` — but the runtime obligation is identical, because
what makes it an obligation is that the engine does not have the fact, not which field says
so. Defaulting an unasserted condition substitutes the engine's judgement for a person's,
silently; there is no version of that failure that is better because the missing fact came
from an illustration rather than from a pilot.

**Attribution is the part that makes it honest.** A `Position` parameter alone would let the
engine accept anything and report nothing. `AssertedPosition` makes every game record say
whose arrangement it was and what, if anything, they cited for it. A caller who has nothing
to cite passes null, which is an honest answer and a visible one.

## What was rejected

**Hard-coding the standard modern setup.** This is the failure the map exists to prevent: it
would implement a rule the corpus does not state, and it would then be invisible, because the
standard setup is also what the corpus's prose gives — the engine would look right and be
unjustified. The difference between "the engine knows the arrangement" and "a caller asserted
one and cited p. 272" is the entire difference between an engine built from a corpus and an
engine built from what its author already knew about backgammon.

**Refusing to start at all.** Defensible, and it makes the decline maximally loud. Rejected
because it converts one declined entry into twenty unimplementable ones: nothing downstream
of a position could be evidenced, and the map's whole claim — that these entries are
separable units of work — would be untestable. A decline should cost what it costs and no
more.

**A `Resolution<GameRecord>` that declines when no position is supplied.** This makes the
position optional and the decline the default, which reads well and is worse: it puts a
`MissingRulesData` in the path of every caller who does have a position, and it makes the
type say the engine might know where the men go. It does not.

**Reading the prose and correcting the map in code.** The most tempting option, since the
corpus does state it. Rejected because the engine would then be right and the map would still
be wrong, and nobody would find out. The finding is worth more than the convenience; the
correction belongs in the map, where a reviewer can see it.
