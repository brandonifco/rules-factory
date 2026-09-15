# Conventions the engine must follow that nothing else in this brief states

The corpus, the map, the owner's rulings, the decision records and `api-contract.md` fix almost
everything a caller of the engine can observe. What they do not fix is listed here. Each item is
something the engine's own test suite observes, written as a requirement on the engine. None of it
is a rule of backgammon: where a rule is involved, the corpus, the map or a ruling decides it, and
this file only says how the answer is shaped.

This file is a disclosure. Every line of it is information a fully blind implementer would not have,
and the rebuild's evidence counts it as help received (`examples/hoyle-blind-rebuild/README.md` in
rules-factory, Brandon's decisions H1 and H2 of 2026-09-15). It was written by someone who has read the target's tests, and was
checked by `build-brief.py` for test names, copied test text and test literals.

## 1. Layout and build

- The engine is named `HoyleBackgammon`. The repository root holds `HoyleBackgammon.slnx`, and the
  four projects are `src/HoyleBackgammon`, `src/Tabletop.Dice`, `tests/HoyleBackgammon.Tests` and
  `tests/Tabletop.Dice.Tests`. `build-files/` holds the solution, `Directory.Packages.props` and both
  `src` project files as the target has them; use them unchanged. In particular the engine project
  must keep the `RulesFactoryMapItem` target and embed `provenance.json` under the logical name
  `HoyleBackgammon.provenance.json`, because a test project built against the engine reads both.
- `Tabletop.Dice` references `RulesKernel.Randomness` and nothing else, and the engine references
  `Tabletop.Dice`, `RulesKernel` and `RulesKernel.Randomness`. No other package: the test projects'
  lock files are the target's, and restore runs in locked mode.
- No public type or member name in `Tabletop.Dice` may contain, ignoring case, any of: backgammon,
  hoyle, blot, gammon, checker, board, point, pip, bar, men, stake, table, home, player.

## 2. The overlay

- `overlay-skeleton.json` gives every entry's `status` and `implementedIn` as the target has them,
  and the owner's rulings with their `declines`. Use those values. `tests` is yours: name your own
  tests, as `rules-factory` requires.
- Exactly three entries are declared fully ruled (`rulings` present, `declines: []`):
  `bearing-off-eligible`, `game-value` and `must-play-whole-throw`.

## 3. How hand-written code declines

The engine's hand-written source (every `*.cs` under `src/` outside `Generated/`) is inspected as
text, with `///` lines removed and whitespace collapsed.

- Every `UnresolvedResult` constructed in hand-written source is written as
  `new UnresolvedResult(UnresolvedReason.<Reason>, <what was attempted>, MapEntries.<Entry>.Locator)`:
  a literal reason first and a `MapEntries` member's `Locator` last. There is no other construction
  of `UnresolvedResult` in hand-written source, and there is at least one.
- The reason at each site is the one the entry's correspondence row predicts
  (`inputs/factory-docs/docs/corpus-map.md`, "The map and the engine agree"). `UnsupportedInteraction`
  appears only for an `implemented` entry that matches no decline row.
- Every entry whose row predicts a decline has at least one such site in hand-written source, even
  where the generated registry already declines it, except the three fully ruled entries, which have
  none.
- `BeyondAdapter.WhichCompartmentIsTheInnerTable` lives in a file named `BeyondAdapter.cs`, and no
  other hand-written file mentions `BeyondAdapter.`.

## 4. What each entry point answers

Every entry point answers `Resolution<object>`. Where it resolves, the value is:

| Entry | Request inputs | Value |
|---|---|---|
| `player-count` | none | `Players.Both` |
| `men-count` | none | `Position.MenPerPlayer` |
| `board-tables` | `Pip` | `Geometry.QuarterOf(pip)` |
| `point-designations` | `Pip` | `Geometry.NameOf(pip)` |
| `direction-of-travel` | `Pip` | `Geometry.Mirror(pip)` |
| `starting-position` | none | `Setup.StartingPositionFromCorpus()` |
| `opening-roll` | `Source` | `Opening.RollForTheRight(source)` |
| `opening-thrower-option` | `Roll`, `Adopt`, `Source` | `Opening.OpeningThrow(roll, adopt, source)` |
| `throw-two-dice` | `Source` | `Opening.Throw(source)` |
| `die-faces` | `Source` | `Die.D6.Throw(source)` |
| `doublets` | `Thrown` | `Movement.Entitlement(thrown)` |
| `move-by-pip` | `Position`, `Player`, `Die` | `AssertedAnswer<ImmutableArray<Move>>` of `Movement.MovesForDie` |
| `legal-destination` | `Position`, `Player`, `Pip` | `AssertedAnswer<bool>` of `Movement.IsPermittedDestination` |
| `made-point` | `Position`, `Player`, `Pip` | `AssertedAnswer<bool>` of `Position.HasMadePoint` |
| `blot-hit` | `Position`, `Player`, `From`, `To` | `AssertedAnswer<Position>` of `Position.Apply` |
| `enter-from-bar` | `Position`, `Player` | `AssertedAnswer<bool>` of `Movement.MustEnterFromBar` |
| `full-table-suspension` | `Position`, `Player` | `AssertedAnswer<bool>` of `Movement.IsWhollySuspended` |
| `must-play-whole-throw` | `Position`, `Player`, `Thrown` | `AssertedAnswer<ImmutableArray<Play>>` of `LegalPlays.For(position, player, Movement.Entitlement(thrown))` |
| `bearing-off-eligible` | `Position`, `Player` | `AssertedAnswer<BearingOffEligibility>` of `BearingOff.Eligibility` |
| `bearing-off-move-or-remove` | `Position`, `Player`, `Die` | `AssertedAnswer<ImmutableArray<Move>>` of `BearingOff.MovesForDie` |
| `bearing-off-highest` | `Position`, `Player`, `Die` | the same as `bearing-off-move-or-remove` |
| `bearing-off-doublets` | `Position`, `Player`, `Thrown` | the same as `must-play-whole-throw` |
| `win-condition` | `Position`, `Player` | `AssertedAnswer<bool>` of `BearingOff.HasWon` |
| `game-value` | `Position`, `Winner` | `AssertedAnswer<GameResult>` of `Outcome.ResultOf` |
| `stake-multiplier` | `Value`, and the asserted `agreed-backgammon-multiple` | `Outcome.Pays(value, agreed)` |
| `hit-pays-single-stake` | the asserted `agreed-backgammon-multiple` | `Outcome.Pays(GameValue.Hit, agreed)` |
| `next-game-opening` | `Value` | `Outcome.Next(value)` |
| `rubber-scoring` | `Games` | `RubberResult` of `Outcome.RubberWinner(games)` |

- An `AssertedAnswer<T>` carries the caller's own `AssertedPosition` object, not a copy.
- Where the rule declines, the entry point returns the rule's `UnresolvedResult` unchanged.
- A request missing an input the rule needs throws `ArgumentException` whose `ParamName` is the
  request property's name (`"Position"`, `"Player"`, ...). A missing asserted
  `agreed-backgammon-multiple` throws `ArgumentException` too.

## 5. Exceptions and text

- `Position.Create` throws `ArgumentException`. When a side does not hold fifteen men its message
  contains `men-count`; when a point holds men of both players it contains `both players hold men`.
- `new AgreedBackgammonMultiple(...)` throws `ArgumentOutOfRangeException` for a multiple other than 3
  or 4, with the `agreed-backgammon-multiple` entry's citation in the message;
  `ArgumentNullException` for a null `AgreedBy`; `ArgumentException` for a blank one. Its
  `ToString()` contains the word `uncited` when `Justification` is null.
- `BearingOff.MovesForDie` for a player with a man on the bar throws `InvalidOperationException` with
  the `enter-from-bar` entry's citation in the message.
- `ScriptedDecider`, asked for a decision it does not have, throws `InvalidOperationException` whose
  message contains `were scripted`.
- `default(Die).Throw(...)` throws `InvalidOperationException`.
- `Move.ToString()` is `from/to(die)`, with `bar` for pip 25 as the origin, `off` for pip 0 as the
  destination, and `*` appended when the move takes up a blot: `bar/19(6)`, `5/off(3)`, `9/6(3)*`.
- `Play.ToString()` is its moves' `ToString()` joined by single spaces.
- `Geometry.NameOf(pip)` is `the <name> point in <whose> <which> table`: `<name>` is ace, deuce,
  trois, quatre, cinque or six, except that each outer table's first point from the bar is `bar`;
  `<whose>` is `his` or `the adversary's`; `<which>` is `inner` or `outer`.

## 6. How `Game.Play` spends draws and decisions

The draws and decisions below are what a replayed game is made of, so their order is part of the
record.

- With no `opener`, the roll for the right to begin comes first: White's die, then Black's, repeated
  while they tie.
- Each turn, in order from the opener, alternating:
  1. A wholly suspended player does not throw and is not asked anything: the turn is recorded with
     no throw and no play, and play passes. If his adversary is wholly suspended too, the game
     declines with `UnsupportedInteraction` citing `full-table-suspension`.
  2. Otherwise he throws. On the opener's first throw of a game that began with a roll for the right,
     the decider is asked `AdoptOpeningThrow` first; adopting draws nothing, and not adopting throws
     both dice. Every other throw is `Opening.Throw`.
  3. The plays are `LegalPlays.For(position, player, Movement.Entitlement(thrown))`, and the decider
     is asked `ChoosePlay` once, with that list.
  4. The turn is recorded with the throw, the play and the position it leaves. If that position has a
     winner, the game ends: its value, rulings and next opener come from `Outcome.ResultOf` and
     `Outcome.Next`.
- The option is asked at most once per game, and only when the opener actually throws.

## 7. The canonical record

`engine/decisions/0006` gives the shape of `GameRecord.ToCanonicalJson()`; 0009 adds each turn's
`rulings` and 0010 the top-level `valueRulings`. The paragraph of 0006 that defined its terms was
redacted with a test name, so its facts are restated here:

- `POSITION` is `{"Black":[26 integers],"White":[26 integers]}`: each player's men by his own pip,
  index 0 borne off, 1 to 24 the points, 25 the bar.
- A turn whose player was wholly suspended has `"thrown":null`, `"moves":null` and `"rulings":null`.
  A turn where nothing could be played has `"moves":[]` and `"rulings":[]`.
- Enum values are written as their C# names, and a move's `authority` is its map entry's id.
- A ruling is written as `{"entry","id","questionPart","record","ruledBy","ruledOn"}`, with
  `ruledOn` as `yyyy-MM-dd`.
