# 0003 — The engine derives the starting position

**Status:** accepted. Amends [0002](0002-a-game-begins-from-an-asserted-position.md) in part.

## Context

This engine was built from a version of `corpus-map.json` that has since been retracted. In
it, `starting-position` was `status: declined`, `beyondAdapter: { adapter: "plain-text",
modality: "illustration" }`, on the ground that the arrangement is stated only in Fig. 1.

Finding 1 in `MAP-FINDINGS.md` reported that this was wrong: the arrangement is stated in
prose as well, and a plain-text adapter reads it perfectly. The factory accepted the finding
and corrected the map (commit `de59930`). In the corrected map:

- `starting-position` is an ordinary `status: mapped` entry, cited to p. 273, with the prose
  as its evidence, and noted as over-determined — footnote 67 needs exactly three men on the
  outer deuce point for its blot to exist, and nineteen opening lines in *Hints for Play* are
  consistent with this arrangement and no other.
- Four entries are new. `point-designations` (p. 272) and `direction-of-travel` (p. 273) are
  findings 2 and 3, also accepted. `player-count` (p. 271) is the sentence `men-count` took
  the thirty men out of and left the two persons in. `inner-table-handedness` (p. 272) is
  finding 5's second half, now its own entry — and it is the entry that carries
  `beyondAdapter`.
- `board-tables` is narrowed to player-relative structure only, which is finding 5's first
  half.

The decision to rebase onto the corrected map was taken outside this repository. What is
recorded here is what the rebase does to the engine.

## Decision

**`Setup.StartingPositionFromCorpus()` returns a `Position`, not a `Resolution<Position>`.**
It derives the arrangement — 24(2)/13(5)/8(3)/6(5) in the mover's own pips, fifteen men,
mirrored by `pip + (25 - pip)` — from the prose, read through `point-designations` and
`direction-of-travel`. There is nothing left for a caller to settle, so there is nothing for a
`Resolution` to carry. The rest of the engine returns plain values where a rule is determinate
and a `Resolution` only where it is not, and this is now the former.

**`AssertedPosition` stays, and `Game.Play` still demands one.** 0002's mechanism was right
for a reason that outlives its premise: most positions are not the starting one. A mid-game
study, a replayed log and an endgame all begin somewhere the corpus never states, and for
those the engine has no fact and must not invent one. What changes is that a caller who does
want the corpus's start no longer has to supply it himself — he can hand
`Setup.StartingPositionFromCorpus()` straight back in, which is what the test suite now does.

**`inner-table-handedness` becomes the engine's `MissingRulesData` decline**, reachable
through `BeyondAdapter.WhichCompartmentIsTheInnerTable()`. Its shape is `OutOfScope`'s and for
the same reason: a caller who asks must be able to tell "the corpus does not carry this in a
form the adapter can read" from "nobody looked".

**And the decline is declared unreached, checkably.** Nothing inside this engine calls it, and
nothing can: every position here is held in player-relative pips, so no rule has occasion to
ask which physical compartment of a board is whose. That is a claim about the engine, so
`scripts/validate.sh` checks it — `BeyondAdapter` appears in no source file but its own,
outside doc comments. Without that, the sentence saying the decline is unreached would quietly
outlive the day some rule reached for it.

**`UnmappedRules` is deleted.** It existed to collect rules the engine had to implement that
the map had no entry for — `point-designations` and `direction-of-travel`. The map has entries
for both now, so `MapEntries` carries them and the class has nothing left to hold. An empty
class kept for its remarks would say the map is still missing something.

## What was decided rather than derived

Two things the corrected map does not settle.

**`player-count`, `point-designations` and `direction-of-travel` are stamped
`status: implemented` here.** The map arrived with them `mapped`, and whether this engine
implements them is the engine's call, not the map's. `point-designations` is `Geometry.NameOf`
and the twenty-four points; `direction-of-travel` is `Geometry.Mirror` and the pip numbering;
`player-count` is `Player` being closed over exactly two, which every player-relative rule
rests on. Each is now cited from the code that implements it. The alternative — leaving them
`mapped` because the engine implemented them before they were entries — would have made the
engine's own map understate what it has done.

**`BeyondAdapter` is a new public type rather than a method on `Setup` or `OutOfScope`.** The
brief allowed saying plainly that nothing reaches the decline instead of giving it a call
site at all. A call site was kept because `OutOfScope` already establishes the pattern in this
engine and the reachability it buys is real — but it is deliberately not on `OutOfScope`,
because "out of scope" and "beyond the adapter" are different answers to a caller and the
correspondence table treats them as different reasons.

## What was rejected

**Keeping the decline and implementing the derivation beside it.** Symmetrical with 0002's
"reading the prose and correcting the map in code", and wrong for the mirror-image reason:
there the finding was worth more than the convenience because the map was wrong and nobody
would find out. Here the map is right. A decline kept alongside a working derivation would be
a decline of nothing.

**Defaulting `Game.Play`'s position to the corpus's.** It reads well and it erases the one
distinction `GameRecord.Start` exists to keep: whether the position played from was the
corpus's arrangement or whatever the caller had in mind. Two lines of caller code is a small
price for a record that cannot lie about where a game began.
