# 0009: The owner's rulings on two open questions are ruleset version five

**Status:** accepted, 2026-09-15. Supersedes [decision 0008](0008-map-6-0-0-is-ruleset-version-four.md)
where it declines the second parts of two questions. The rest of 0008 stands. Superseded in part by
[decision 0010](0010-owner-rulings-are-ruleset-version-six.md), which rules on the first parts it still declines
and on `game-value`'s question (ruleset 6, replay schema 4).

> **Amendment, 2026-09-15: the rulings are held in the overlay (rules-factory 0.6.0, decision 0027).**
> The factory gained the carrier this record's last paragraph asked for, and the rulings moved into it
> with no change of behaviour.
>
> - **`corpus-map.overlay.json`** holds both rulings, on `must-play-whole-throw` and
>   `bearing-off-eligible`. Each has its `id`, the `span` of the entry's question it answers (the
>   sentences from "Nor does it say …" to the end), a one-line `answer`, `ruledBy`, `ruledOn`, this
>   record, and the tests that show it. Beside each is `declines`, quoting the question's first part
>   with the tests that show the decline. Together the spans cover each question, and `factory produce`
>   and the gate check that they do. Neither key reaches the merged map.
> - **The hand-written `OwnerRuling.cs` is gone.** `factory produce` writes
>   `src/HoyleBackgammon/Generated/Rulings.g.cs` from the overlay: the record
>   `OwnerRuling(Id, EntryId, Span, Answer, RuledBy, RuledOn, Record)` and `OwnerRulings`, with
>   `MustPlayWholeThrow2`, `BearingOffEligible2` and `All`. `OwnerRulings.cs` keeps this record's
>   names, `APlayIsThePositionItReaches` and `BearingOffBeginsWithinTheThrow`, as aliases. `Entry`
>   (a `MapEntry`) became `EntryId` (its id), and `Ruling` became `Answer`.
> - **`QuestionPart` stays, derived** from the number after the slash in the id, on a partial of the
>   generated record. The overlay names a part by its span, and that is what the factory checks. The
>   number is kept because replay schema 3 records `questionPart`, so the record's bytes, and the
>   pinned replay hash, did not change. The ruleset stays version 5 and the replay schema 3.
> - Where this record says the factory has no carrier and no check sees the rulings (Context, *What
>   the factory offers for this*, and the last Consequence), that is no longer so. What the factory
>   still cannot check is listed in rules-factory 0027 § 7.

## Context

`RulesFactory.Maps.HoyleBackgammon` 6.0.0 records two questions that the corpus does not settle.
Each is the second part of an existing entry's `ambiguity.question`, with `clarity: ambiguous`,
`fate: unresolved` and `unresolvedReason: RequiresInterpretation`:

- **`must-play-whole-throw`, second part** (BACKGAMMON / Playing / p. 275): whether two orders that
  use the same numbers and reach the same position are one play or two, where the rule that permits
  a move differs between the orders.
- **`bearing-off-eligible`, second part** (BACKGAMMON / Bearing off the Men / p. 275): whether a
  number left after the move that brings the last man home is played under bearing off.

> [redacted by build-brief.py: test-literal]

On 2026-09-15 **Brandon, the engine's owner, ruled on both second parts**:

1. **`bearing-off-eligible`, second part: yes.** Once a player's first number brings his last man
   home, the number left bears off. With the last man on the nine point and six-trois, 9/3 then off
   with the trois is legal, and so is 9/6 then off with the six.
2. **`must-play-whole-throw`, second part: one play.** A play is the position it reaches. Two orders
   of the same numbers that reach the same position are offered once, crediting the rules of the first
   order found. This was the behaviour before 6.0.0 ([0007](0007-an-equivalent-order-is-offered-once-until-the-map-says-otherwise.md)).

**These are the owner's interpretations, not readings of the corpus.** The text still does not
settle either question, so the map does not change. Both entries stay `fate: unresolved`. Nobody
has claimed that the corpus says what the rulings say.

**The first parts are not ruled on**, and they still decline:

- `must-play-whole-throw`: either die alone playable, but not both.
- `bearing-off-eligible`: a man hit after bearing off has begun, who re-enters with men still at
  home.

### What the factory offers for this

The factory and this engine's conventions were checked for a supported way to apply a recorded
owner ruling to an unresolved question instead of declining:

- **`ambiguity.fate` has two values** (`rules-factory/docs/corpus-map.md`, "`ambiguity.fate`";
  [rules-factory 0005](https://github.com/brandonifco/rules-factory/blob/main/docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md)).
  `decision` means "the project rules on what the passage means, records it, and implements as though
  the corpus had said so". `unresolved` means the engine declines. "There is no third value."
  `decision` is the factory's carrier for a ruling, but it lives in the map. Using it would record
  the rulings as what the passage means, which they are not. An engine also cannot set it:
  the overlay holds only `status`, `implementedIn` and `tests` (rules-factory 0015, `method.md`, "What
  an engine owes its map's source"). So the factory has **no supported carrier for an owner's
  ruling that is held by the engine and leaves the map unresolved.**
> [redacted by build-brief.py: test-name]
- **What that leaves unenforced.** `corpus-map.md` says that for an `implemented` entry with
  `fate: unresolved`, "the verdict covers every case except the one `ambiguity.question` names". This
  engine now answers part of what each of those two questions names. No check reads that. The
  convention holds only through this record, and through the answer naming the ruling (below).
  [rules-factory 0021](https://github.com/brandonifco/rules-factory/blob/main/docs/decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md)
  was also checked. It concerns a gate out of scope whose state the *caller* asserts. That does not
  fit here: the owner rules for every caller, not per call.

## Decision

**The engine applies both rulings, names them wherever a result relies on one, and the ruleset is
`hoyle-1909-backgammon` version 5.**

- **`OwnerRuling`** is a public record: an id (`must-play-whole-throw/2`, `bearing-off-eligible/2`),
  the map entry, the question part (2), who ruled (`Brandon`), when (2026-09-15), the ruling in a
  sentence, and this record's path. `OwnerRulings` holds the two rulings.
- **`LegalPlays.For`** (and so `EntryPoints.MustPlayWholeThrow` and `Game.Play`) no longer declines
  either second part. Rule 4 of the enumeration contract prunes every later order that reaches a state
  already reached, as it did under version 3. Bearing off begins as soon as every man is home,
  partway through a throw included.
- **`Play.Rulings`** lists the rulings a play relies on, and is empty otherwise:
  - `must-play-whole-throw/2` where some order the search pruned reached the play's state under a
    different multiset of authorities. The search records the state where two such orders met, and
    every play reached from that state. From there the pruned order goes on exactly as the offered
    one does, because a move's authority depends only on the position it is played from. Orders under
    the same rules never needed the ruling and are not marked, e.g. bar/22 22/16 and bar/19 19/16
    with a man up.
  - `bearing-off-eligible/2` where the player was not eligible at the start of the throw and a move of
    the play is made under a bearing-off rule.

  Each move's `Authority` is still the map entry that permits it once the ruling is applied: in
  8/6 6/5, the ace is `bearing-off-move-or-remove`. The authority names a rule of the corpus. The
  play names the ruling that made that rule reach the move.
- **The canonical record names the rulings.** Each turn in `GameRecord.ToCanonicalJson` gains
  `rulings`: for each ruling, its `id`, `entry`, `questionPart`, `ruledBy`, `ruledOn` and `record`.
  The value is `[]` where the play relies on none, and `null` where no play was made, as `moves` is.
  The record's shape changes, so **the replay schema is 3**.
- **The declines that stay:** the first parts of both questions, `game-value`'s two overlaps,
  `rubber-scoring`, `inner-table-handedness`, the out-of-scope entries and the double suspension.
  None of them changes.
- **`implementedIn` moves to 5 on every implemented entry**, for the reason 0004 gives.
- **The map is unchanged.** No finding is filed, because the map is right: the corpus does not
  settle either question. If a later map version settles either one, the engine follows the map, and
  that ruling is withdrawn in a new record.

## Consequences

- **The answer is never passed off as Hoyle.** Every result that relies on a ruling says so. A caller
  of the entry point finds the ruling on `Play.Rulings`. A reader of a recorded game finds it on the
  turn, with who ruled and when. An `UnresolvedResult` has nowhere to carry a ruling, and none is
  needed: a decline relies on no ruling.
> [redacted by build-brief.py: test-literal]
> [redacted by build-brief.py: test-literal, test-name]
> [redacted by build-brief.py: test-name]
> [redacted by build-brief.py: test-name]
- **The factory could carry this.** It has no field for "unresolved in the corpus, ruled by the
  owner". This record and `Play.Rulings` hold that fact, and no factory check sees it. If the factory
  gains a carrier, such as an overlay or engine-side ruling that correspondence row 6 honours, these
  rulings move into it.
