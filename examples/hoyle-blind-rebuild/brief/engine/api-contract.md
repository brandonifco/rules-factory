# Public API contract

Generated from compiled assemblies by examples/hoyle-blind-rebuild/api-surface: signatures, constant
values and public XML documentation only. No method body is read. `[generated]` marks a type the
factory's generated code declares (a rebuild produces it; hand-written partial members may be added).

## Assembly HoyleBackgammon

### namespace HoyleBackgammon

#### public sealed record AgreedBackgammonMultiple
/// The multiple a backgammon pays, as the players agreed it, with the attribution that makes it answerable for.
/// Remarks: `HoyleBackgammon.MapEntries.AgreedBackgammonMultiple` is a delegated standard, not a gap: "the loser pays either thrice or four times (as may have been agreed) the amount of the single stake." The corpus vests the figure in an agreement, so the engine owes it the four things a method owes any condition no computation settles — demand it, attribute it, record it alongside the outcome, and never infer it. This type is the demand and the attribution; `HoyleBackgammon.StakeDue.Agreement` is the record alongside the outcome. Shaped like `HoyleBackgammon.AssertedPosition`, which does the same job for a position, and named for the corpus's own word rather than for the schema's.
/// The corpus also bounds the figure — thrice or four times, and nothing else — and that bound is a rule it states rather than a judgement it delegates, so it is enforced here instead of being discarded. An earlier reading of the entry treated the delegation as an ambiguity and returned `RequiresInterpretation`, which declined a job the corpus gave the engine the means to do and threw the bound away with it. See `rules-factory/docs/decisions/0005` and finding 9 in `MAP-FINDINGS.md`.
/// Who may make the agreement is the map's to say, not the engine's: `HoyleBackgammon.MapEntry.AssertedBy` on `HoyleBackgammon.MapEntries.AgreedBackgammonMultiple` (rules-factory decision 0025). Since map 5.0.0 it is `caller`, because "(as may have been agreed)" names nobody, so any party the caller names is accepted. A map that named the parties would restrict `HoyleBackgammon.AgreedBackgammonMultiple.AgreedBy` to them.
/// Parameter Multiple: The figure agreed: `HoyleBackgammon.AgreedBackgammonMultiple.Thrice` or `HoyleBackgammon.AgreedBackgammonMultiple.FourTimes`.
/// Parameter AgreedBy: Who is answerable for it. Free text where the map's `assertedBy` is `caller`; otherwise one of the parties it names, ignoring case and spacing.
/// Parameter Justification: Where the agreement is recorded, when the parties can cite something — a club's standing terms, a match agreement. Null when they cannot, which is the ordinary case for two people at a board, and saying so is honest.

    public const int FourTimes = 4
      /// The higher of the two figures the corpus admits.

    public const int Thrice = 3
      /// The lower of the two figures the corpus admits.

    public AgreedBackgammonMultiple(int Multiple, string AgreedBy, SourceLocator? Justification = null)
      /// The multiple a backgammon pays, as the players agreed it, with the attribution that makes it answerable for.
      /// Remarks: `HoyleBackgammon.MapEntries.AgreedBackgammonMultiple` is a delegated standard, not a gap: "the loser pays either thrice or four times (as may have been agreed) the amount of the single stake." The corpus vests the figure in an agreement, so the engine owes it the four things a method owes any condition no computation settles — demand it, attribute it, record it alongside the outcome, and never infer it. This type is the demand and the attribution; `HoyleBackgammon.StakeDue.Agreement` is the record alongside the outcome. Shaped like `HoyleBackgammon.AssertedPosition`, which does the same job for a position, and named for the corpus's own word rather than for the schema's.
      /// The corpus also bounds the figure — thrice or four times, and nothing else — and that bound is a rule it states rather than a judgement it delegates, so it is enforced here instead of being discarded. An earlier reading of the entry treated the delegation as an ambiguity and returned `RequiresInterpretation`, which declined a job the corpus gave the engine the means to do and threw the bound away with it. See `rules-factory/docs/decisions/0005` and finding 9 in `MAP-FINDINGS.md`.
      /// Who may make the agreement is the map's to say, not the engine's: `HoyleBackgammon.MapEntry.AssertedBy` on `HoyleBackgammon.MapEntries.AgreedBackgammonMultiple` (rules-factory decision 0025). Since map 5.0.0 it is `caller`, because "(as may have been agreed)" names nobody, so any party the caller names is accepted. A map that named the parties would restrict `HoyleBackgammon.AgreedBackgammonMultiple.AgreedBy` to them.
      /// Parameter Multiple: The figure agreed: `HoyleBackgammon.AgreedBackgammonMultiple.Thrice` or `HoyleBackgammon.AgreedBackgammonMultiple.FourTimes`.
      /// Parameter AgreedBy: Who is answerable for it. Free text where the map's `assertedBy` is `caller`; otherwise one of the parties it names, ignoring case and spacing.
      /// Parameter Justification: Where the agreement is recorded, when the parties can cite something — a club's standing terms, a match agreement. Null when they cannot, which is the ordinary case for two people at a board, and saying so is honest.

    public SourceLocator? Justification { get; init; }
      /// Where the agreement is recorded, when the parties can cite something — a club's standing terms, a match agreement. Null when they cannot, which is the ordinary case for two people at a board, and saying so is honest.

    public int Multiple { get; }
      /// The agreed multiple, checked against the bound the corpus states.

    public string AgreedBy { get; }
      /// Who agreed it, checked to be non-empty and to be a party the map lets assert it.

    public override string ToString()
      /// (documentation inherited)

#### public sealed record AssertedAnswer<T>
/// An entry's answer about a position somebody asserted, with the assertion it rests on.
/// Remarks: What `HoyleBackgammon.EntryPoints` returns for every entry whose request takes a position: the rule's value, and the `HoyleBackgammon.AssertedPosition` it was asked about, so the attribution survives the typed surface as it survives `HoyleBackgammon.Game.Play(HoyleBackgammon.AssertedPosition,RulesKernel.Randomness.IRandomSource,HoyleBackgammon.IDecider,System.Nullable{HoyleBackgammon.Player},System.Int32)` into `HoyleBackgammon.GameRecord.Start` (`docs/decisions/0002`).
/// Type parameter T: The rule's value type.
/// Parameter Value: The rule's value.
/// Parameter Position: The position the rule was asked about, and who asserted it.

    public AssertedAnswer(T Value, AssertedPosition Position)
      /// An entry's answer about a position somebody asserted, with the assertion it rests on.
      /// Remarks: What `HoyleBackgammon.EntryPoints` returns for every entry whose request takes a position: the rule's value, and the `HoyleBackgammon.AssertedPosition` it was asked about, so the attribution survives the typed surface as it survives `HoyleBackgammon.Game.Play(HoyleBackgammon.AssertedPosition,RulesKernel.Randomness.IRandomSource,HoyleBackgammon.IDecider,System.Nullable{HoyleBackgammon.Player},System.Int32)` into `HoyleBackgammon.GameRecord.Start` (`docs/decisions/0002`).
      /// Type parameter T: The rule's value type.
      /// Parameter Value: The rule's value.
      /// Parameter Position: The position the rule was asked about, and who asserted it.

    public AssertedPosition Position { get; init; }
      /// The position the rule was asked about, and who asserted it.

    public SourceLocator? Justification { get; }
      /// Where the asserter says the position comes from, `HoyleBackgammon.AssertedPosition.Justification`.

    public T Value { get; init; }
      /// The rule's value.

    public string AssertedBy { get; }
      /// Who is answerable for the position, `HoyleBackgammon.AssertedPosition.AssertedBy`.

#### public sealed record AssertedPosition
/// A position supplied by somebody outside the engine, with the attribution that makes it answerable for.
/// Remarks: The engine can originate the corpus's starting position — see `HoyleBackgammon.Setup.StartingPositionFromCorpus` — so this type is no longer the only way a game can begin. It stays because most positions are not the starting one: a mid-game study, a replayed log, an endgame the corpus never states. For those the engine has no fact and must not invent one, and the method's treatment of a condition no computation settles applies: demand it, attribute it, record it alongside the outcome, and never infer it. The attribution travels with the game's result; see `docs/decisions/0002`, as amended by `docs/decisions/0003`.
/// Parameter Position: The arrangement being asserted.
/// Parameter AssertedBy: Who is answerable for it. Free text; the engine does not parse it.
/// Parameter Justification: Where the asserter says it comes from, when they can cite something. Null when they cannot — a caller setting up a mid-game study has nothing to cite, and saying so is honest.

    public AssertedPosition(Position Position, string AssertedBy, SourceLocator? Justification = null)
      /// A position supplied by somebody outside the engine, with the attribution that makes it answerable for.
      /// Remarks: The engine can originate the corpus's starting position — see `HoyleBackgammon.Setup.StartingPositionFromCorpus` — so this type is no longer the only way a game can begin. It stays because most positions are not the starting one: a mid-game study, a replayed log, an endgame the corpus never states. For those the engine has no fact and must not invent one, and the method's treatment of a condition no computation settles applies: demand it, attribute it, record it alongside the outcome, and never infer it. The attribution travels with the game's result; see `docs/decisions/0002`, as amended by `docs/decisions/0003`.
      /// Parameter Position: The arrangement being asserted.
      /// Parameter AssertedBy: Who is answerable for it. Free text; the engine does not parse it.
      /// Parameter Justification: Where the asserter says it comes from, when they can cite something. Null when they cannot — a caller setting up a mid-game study has nothing to cite, and saying so is honest.

    public Position Position { get; init; }
      /// The arrangement being asserted.

    public SourceLocator? Justification { get; init; }
      /// Where the asserter says it comes from, when they can cite something. Null when they cannot — a caller setting up a mid-game study has nothing to cite, and saying so is honest.

    public string AssertedBy { get; }
      /// The asserted arrangement, with its asserter checked to be non-empty.

    public override string ToString()
      /// (documentation inherited)

#### public sealed class AssertionRequiredException : ArgumentException  [generated]
/// An assertion the corpus leaves to the caller was not supplied. Not an unresolved result: the corpus gave the engine the means to proceed, and the caller owes the value (row 8).

    public AssertionRequiredException(string entryId)
      /// Creates the exception for the assertion entry `entryId`.
      /// Parameter entryId: The assertion the caller did not supply.

    public string EntryId { get; }
      /// The assertion the caller did not supply.

#### public static class BearingOff
/// Bearing off: the last stage, where a throw may move a man within the home table or take one off the board.

    public static BearingOffEligibility Eligibility(Position position, Player player)
      /// `HoyleBackgammon.MapEntries.BearingOffEligible`'s answer: `HoyleBackgammon.BearingOff.IsEligible(HoyleBackgammon.Position,HoyleBackgammon.Player)`, naming `HoyleBackgammon.OwnerRulings.BearingOffStopsUntilEveryManIsHomeAgain` where `HoyleBackgammon.BearingOff.HasReEnteredMidBearOff(HoyleBackgammon.Position,HoyleBackgammon.Player)` holds, the question's first part, which the corpus does not settle and the owner has ruled on (`docs/decisions/0010`).

    public static ImmutableArray<Move> MovesForDie(Position position, Player player, int die)
      /// Every move a single die of `die` allows a player who is bearing off, highest origin first.
      /// Remarks: `HoyleBackgammon.MapEntries.BearingOffMoveOrRemove`: "each throw entitles the player either to move forward a man or men (to the extent indicated by the throw) within the limits of his own table, or to remove men from the corresponding points." A forward move is still subject to `HoyleBackgammon.MapEntries.LegalDestination` — the bearing-off section does not repeat the qualification and does not withdraw it, and an adversary man can be standing in the winner's home table, which `game-value`'s definition of a backgammon says in so many words.
      /// `HoyleBackgammon.MapEntries.BearingOffHighest`: "If, however, he throws a number which he cannot deal with after either of these fashions — e.g., a six, he is entitled to bear off a man from his highest occupied point." Read literally: the highest-point removal becomes available exactly when the two other fashions yield nothing.
      /// `HoyleBackgammon.MapEntries.BearingOffDoublets` needs nothing here: "Doublets have, as in the earlier stage of the game, a twofold value, and may be played either wholly by moving men forward, wholly by bearing off, or partly by the one method and partly by the other." That is four independent applications of this method, which is what `HoyleBackgammon.Movement.Entitlement(Tabletop.Dice.DiceThrow)` already produces.

    public static bool HasReEnteredMidBearOff(Position position, Player player)
      /// Whether `player` is in the one position the corpus does not settle for `HoyleBackgammon.MapEntries.BearingOffEligible`: he has begun to bear off, a man of his was hit and has re-entered, and he still has men in his home table to bear off. Where it holds, an answer relies on `HoyleBackgammon.OwnerRulings.BearingOffStopsUntilEveryManIsHomeAgain` (`docs/decisions/0010`).
      /// Remarks: The map's question (`bearing-off-eligible`, `fate: unresolved`; blind-mapping resolution rows 12 and 13): "If one of his men is hit after he has begun to bear off and then re-enters, the text does not say whether he may go on bearing off the men still at home or must first bring every man home again."
      /// Written as a predicate on the position, and no wider than the question:
      /// - "has begun to bear off" is at least one man borne off, the reading `HoyleBackgammon.Outcome.ResultOf(HoyleBackgammon.Position,HoyleBackgammon.Player)` already gives the same words in `game-value`;
      /// - "then re-enters" is no man of his on the bar (while one is up, `enter-from-bar` suspends bearing off whichever reading holds);
      /// - "must first bring every man home again" needs a man outside his home table, or both readings agree he is bearing off;
      /// - "the men still at home" needs a man in his home table, or there is nothing to go on bearing off and both readings agree he is simply moving.

    public static bool HasWon(Position position, Player player)
      /// Whether `player` has removed all his men and so has won. `HoyleBackgammon.MapEntries.WinCondition`: "The player who first succeeds in removing all his men from the board wins the game."

    public static bool IsEligible(Position position, Player player)
      /// Whether `player` has got all his men into his home table and may begin to bear off.
      /// Remarks: `HoyleBackgammon.MapEntries.BearingOffEligible`: "When either player has succeeded in getting all his men into his home table, he proceeds to 'bear them off'."
      /// Men already borne off are off the board, not outstanding, so the test is that nothing of his stands on the bar or on any point above his six point: literally, all his men are in his home table.
      /// What this does not decide. The map records (since `RulesFactory.Maps.HoyleBackgammon` 3.0.0, blind-mapping resolution rows 12 and 13) that the corpus never says whether the stage lasts: a player hit after he has begun to bear off, whose man re-enters, may go on bearing off the men still at home, or may have to bring every man home again. This predicate is the literal test and nothing more. Where the question actually arises -- `HoyleBackgammon.BearingOff.HasReEnteredMidBearOff(HoyleBackgammon.Position,HoyleBackgammon.Player)` -- the owner's ruling since ruleset version 6 is that he may not bear off again until every man is home, which is this test's answer; `HoyleBackgammon.BearingOff.Eligibility(HoyleBackgammon.Position,HoyleBackgammon.Player)` gives it with the ruling named, and `HoyleBackgammon.LegalPlays.For(HoyleBackgammon.Position,HoyleBackgammon.Player,System.Collections.Immutable.ImmutableArray{System.Int32})` names it on the plays (`HoyleBackgammon.OwnerRulings.BearingOffStopsUntilEveryManIsHomeAgain`, `docs/decisions/0010`). Versions 2 to 5 declined there. While his man is still up the question does not arise at all: `enter-from-bar` suspends every bearing-off rule (rows 11, 14 and 17), and `HoyleBackgammon.BearingOff.MovesForDie(HoyleBackgammon.Position,HoyleBackgammon.Player,System.Int32)` refuses on that ground first.
      /// Nor does it decide the question's second part, since `RulesFactory.Maps.HoyleBackgammon` 6.0.0 (rules-factory#125): whether a number left after the move that brings the last man home is played under this stage. That is a question about a throw, not a position, so this predicate cannot raise it. The corpus does not settle it; the engine's owner has ruled that it is, and `HoyleBackgammon.LegalPlays.For(HoyleBackgammon.Position,HoyleBackgammon.Player,System.Collections.Immutable.ImmutableArray{System.Int32})` applies the ruling and names it on the play (`HoyleBackgammon.OwnerRulings.BearingOffBeginsWithinTheThrow`, `docs/decisions/0009`).

#### public sealed record BearingOffEligibility
/// Whether a player may bear off, and the owner's rulings that answer relies on.
/// Parameter Eligible: Whether every man of his is in his home table, so that he may bear off.

    public BearingOffEligibility(bool Eligible)
      /// Whether a player may bear off, and the owner's rulings that answer relies on.
      /// Parameter Eligible: Whether every man of his is in his home table, so that he may bear off.

    public ImmutableArray<OwnerRuling> Rulings { get; init; }
      /// The owner's rulings the answer relies on; empty when the corpus gives it unaided. Since ruleset version 6, `HoyleBackgammon.OwnerRulings.BearingOffStopsUntilEveryManIsHomeAgain` where `HoyleBackgammon.BearingOff.HasReEnteredMidBearOff(HoyleBackgammon.Position,HoyleBackgammon.Player)` holds (`docs/decisions/0010`).

    public bool Eligible { get; init; }
      /// Whether every man of his is in his home table, so that he may bear off.

#### public static class BeyondAdapter
/// The one entry the map records as beyond the declared adapter's reach, reachable rather than absent.
/// Remarks: The shape is `HoyleBackgammon.OutOfScope`'s and the reason is the same: "the corpus does not carry this in a form the adapter can read" and "nobody looked" must not be indistinguishable, and at runtime that means the engine has to be able to say which it is.
/// Nothing inside this engine calls it. That is not an oversight and the method is not a stub standing in for work not done — `HoyleBackgammon.Geometry` holds every position in player-relative pips, so no rule here ever has occasion to ask which physical compartment of a board is whose. The method exists for a caller outside the engine — a renderer, say, which must put the men somewhere on a screen — and it is the engine's only `RulesKernel.Resolution.UnresolvedReason.MissingRulesData`.

    public static Resolution<Quarter> WhichCompartmentIsTheInnerTable()
      /// Which side of a physical board is a player's inner table. `HoyleBackgammon.MapEntries.InnerTableHandedness`: "With the men placed as in Fig. 1, the right hand is the inner or home table, and the left hand consequently the outer table."
      /// Remarks: The rule is fully determined in the corpus and is not ambiguous — but the sentence is only meaningful with Fig. 1 in view, because Fig. 1 is what fixes the orientation "right hand" is relative to. The declared adapter is `plain-text` and cannot read a figure, so by the factory's correspondence table this is `RulesKernel.Resolution.UnresolvedReason.MissingRulesData`.
      /// Returns: Always `RulesKernel.Resolution.UnresolvedReason.MissingRulesData`.

#### public enum CorrespondenceRow : int  [generated]
/// The first row of the map-to-runtime correspondence table an entry matches (docs/corpus-map.md).

    None = 0
      /// No row: a built, clear rule the engine simply answers.

    ScopeOut = 1
      /// Row 1, `scope: out`: OutsideCurrentScope.

    NotBuilt = 2
      /// Row 2, `status: mapped` or `blocked`: UnsupportedRule.

    DefinedElsewhere = 3
      /// Row 3, `definedElsewhere`: MissingRulesData.

    BeyondAdapter = 4
      /// Row 4, `beyondAdapter`: MissingRulesData.

    ValueDependencyUnimplemented = 5
      /// Row 5, an operation whose value dependency is unimplemented: MissingRulesData.

    UnresolvedAmbiguity = 6
      /// Row 6, `ambiguity.fate: unresolved`: RequiresInterpretation.

    Assertion = 8
      /// Row 8, `kind: assertion`: nothing; the engine demands the value.

#### public sealed record DerivedMapEntry  [generated]
/// A derived entry (rules-factory decision 0012): a fact the corpus entails and never states.
/// Parameter Id: The map entry's stable slug.
/// Parameter Name: The entry's name, as the map records it.
/// Parameter DerivedFrom: The entry ids it is derived from, in the map's order.
/// Parameter Locators: Its citation: the locator of every located entry it rests on, following derived sources down to located ones, depth-first in `DerivedFrom` order, each locator once, at its first place.

    public DerivedMapEntry(string Id, string Name, ImmutableArray<string> DerivedFrom, ImmutableArray<SourceLocator> Locators)
      /// A derived entry (rules-factory decision 0012): a fact the corpus entails and never states.
      /// Parameter Id: The map entry's stable slug.
      /// Parameter Name: The entry's name, as the map records it.
      /// Parameter DerivedFrom: The entry ids it is derived from, in the map's order.
      /// Parameter Locators: Its citation: the locator of every located entry it rests on, following derived sources down to located ones, depth-first in `DerivedFrom` order, each locator once, at its first place.

    public ImmutableArray<SourceLocator> Locators { get; init; }
      /// Its citation: the locator of every located entry it rests on, following derived sources down to located ones, depth-first in `DerivedFrom` order, each locator once, at its first place.

    public ImmutableArray<string> AssertedBy { get; init; }
      /// Who the corpus lets assert this entry, the map's `assertedBy` (rules-factory decision 0025): the corpus's own words, or `caller` where the corpus names nobody. Empty on an entry that is not `kind: assertion`. An engine checks an assertion's attribution against these, not its own reading.

    public ImmutableArray<string> DerivedFrom { get; init; }
      /// The entry ids it is derived from, in the map's order.

    public string Id { get; init; }
      /// The map entry's stable slug.

    public string Name { get; init; }
      /// The entry's name, as the map records it.

    public override string ToString()
      /// (documentation inherited)

#### public static class EngineProvenance  [generated]
/// The engine's provenance.json (rules-factory #3, M4), embedded when the assembly was built.

    public const string ResourceName = "HoyleBackgammon.provenance.json"
      /// The manifest resource name provenance.json is embedded under.

    public static byte[] ReadBytes()
      /// The embedded provenance.json, byte for byte.
      /// Returns: The file's bytes.
      /// Throws System.InvalidOperationException: The assembly was built without it.

#### public static class EntryPoints  [generated]
/// The typed entry point of every map entry, in the map's order.

    public static RuleEntry<AgreedBackgammonMultipleRequest, object> AgreedBackgammonMultiple { get; }
      /// The multiple the players agreed a backgammon pays (`agreed-backgammon-multiple`).

    public static RuleEntry<BearingOffDoubletsRequest, object> BearingOffDoublets { get; }
      /// Doublets bear off or move, or both (`bearing-off-doublets`).

    public static RuleEntry<BearingOffEligibleRequest, object> BearingOffEligible { get; }
      /// Bearing off begins when all men are home (`bearing-off-eligible`).

    public static RuleEntry<BearingOffHighestRequest, object> BearingOffHighest { get; }
      /// An unusable number bears off from the highest occupied point (`bearing-off-highest`).

    public static RuleEntry<BearingOffMoveOrRemoveRequest, object> BearingOffMoveOrRemove { get; }
      /// Each throw may move within the table or remove a man (`bearing-off-move-or-remove`).

    public static RuleEntry<BlotHitRequest, object> BlotHit { get; }
      /// A single man is a blot and may be hit (`blot-hit`).

    public static RuleEntry<BoardTablesRequest, object> BoardTables { get; }
      /// The board is two tables, inner and outer (`board-tables`).

    public static RuleEntry<CallingTheThrowRequest, object> CallingTheThrow { get; }
      /// The thrower calls his throw, the higher number first (`calling-the-throw`).

    public static RuleEntry<DieFacesRequest, object> DieFaces { get; }
      /// The faces a die bears, and the throws a pair of them can show (`die-faces`).

    public static RuleEntry<DirectionOfTravelRequest, object> DirectionOfTravel { get; }
      /// The twenty-four points are one course with two ends (`direction-of-travel`).

    public static RuleEntry<DoubletsRequest, object> Doublets { get; }
      /// Doublets are played twice over (`doublets`).

    public static RuleEntry<DoublingCubeRequest, object> DoublingCube { get; }
      /// Doubling the stake during play (`doubling-cube`).

    public static RuleEntry<EnterFromBarRequest, object> EnterFromBar { get; }
      /// A man on the bar re-enters before any other man moves (`enter-from-bar`).

    public static RuleEntry<FullTableSuspensionRequest, object> FullTableSuspension { get; }
      /// Play is wholly suspended against a full home table (`full-table-suspension`).

    public static RuleEntry<GameValueRequest, object> GameValue { get; }
      /// A win is a hit, a gammon, or a backgammon (`game-value`).

    public static RuleEntry<HitPaysSingleStakeRequest, object> HitPaysSingleStake { get; }
      /// What a hit pays (`hit-pays-single-stake`).

    public static RuleEntry<InnerTableHandednessRequest, object> InnerTableHandedness { get; }
      /// Which physical compartment of the board is the inner table (`inner-table-handedness`).

    public static RuleEntry<LegalDestinationRequest, object> LegalDestination { get; }
      /// A man may be played only to a permitted point (`legal-destination`).

    public static RuleEntry<MadePointRequest, object> MadePoint { get; }
      /// Two men make a point (`made-point`).

    public static RuleEntry<MenCountRequest, object> MenCount { get; }
      /// Thirty men, fifteen to a side (`men-count`).

    public static RuleEntry<MoveByPipRequest, object> MoveByPip { get; }
      /// Each die moves one man that many points (`move-by-pip`).

    public static RuleEntry<MustPlayWholeThrowRequest, object> MustPlayWholeThrow { get; }
      /// The whole throw must be played if it can be (`must-play-whole-throw`).

    public static RuleEntry<NextGameOpeningRequest, object> NextGameOpening { get; }
      /// Who throws first in the following game (`next-game-opening`).

    public static RuleEntry<OpeningRollRequest, object> OpeningRoll { get; }
      /// Deciding who begins (`opening-roll`).

    public static RuleEntry<OpeningThrowerOptionRequest, object> OpeningThrowerOption { get; }
      /// The opening thrower may keep the throw or throw again (`opening-thrower-option`).

    public static RuleEntry<PlayerCountRequest, object> PlayerCount { get; }
      /// Backgammon is played by two persons (`player-count`).

    public static RuleEntry<PointDesignationsRequest, object> PointDesignations { get; }
      /// How the twenty-four points are named and numbered (`point-designations`).

    public static RuleEntry<RubberScoringRequest, object> RubberScoring { get; }
      /// How games count towards a rubber (`rubber-scoring`).

    public static RuleEntry<StakeMultiplierRequest, object> StakeMultiplier { get; }
      /// What a gammon and a backgammon pay (`stake-multiplier`).

    public static RuleEntry<StartingPositionRequest, object> StartingPosition { get; }
      /// The starting arrangement of the men (`starting-position`).

    public static RuleEntry<StrategyAdviceRequest, object> StrategyAdvice { get; }
      /// The advisory principles of play (`strategy-advice`).

    public static RuleEntry<ThrowTwoDiceRequest, object> ThrowTwoDice { get; }
      /// All subsequent throws use both dice (`throw-two-dice`).

    public static RuleEntry<WinConditionRequest, object> WinCondition { get; }
      /// First to remove all men wins (`win-condition`).

#### public enum EntryStatus : int  [generated]
/// Whether the engine has built an entry, as the map merged with the overlay says.

    Mapped = 0
      /// Enumerated and classified; not yet worked.

    Blocked = 1
      /// A dependency is unmet.

    Implemented = 2
      /// In the engine, naming the tests that prove it.

    Declined = 3
      /// No implemented path at all.

#### public sealed class FirstOptionDecider : IDecider
/// Takes the first option every time: never adopts the opening throw, always plays `plays[0]`. A fixed policy, so a game under it is a function of the seed alone.

    public FirstOptionDecider()

    public bool AdoptOpeningThrow(OpeningRoll roll)
      /// (documentation inherited)

    public int ChoosePlay(Player player, ImmutableArray<Play> plays)
      /// (documentation inherited)

#### public static class Game
/// Plays one game through, from a position somebody asserted.

    public static ReplayCompatibilityIdentity Identity { get; }
      /// The engine's replay identity: which ruleset, which replay schema, which pinned corpus and which generator. Two runs are comparable only if these agree, and every `HoyleBackgammon.GameRecord` carries it.
      /// Remarks: The replay schema is version 4 since the record names the owner's rulings its value relies on (`valueRulings`, `docs/decisions/0010`), and version 3 since each turn of a `HoyleBackgammon.GameRecord` names the owner's rulings its play relies on (`docs/decisions/0009`); version 2 gave the record its identity, its map and a canonical serialisation of its own (`docs/decisions/0006`). The ruleset is version 6 from Brandon's rulings of 2026-09-15 on the first parts of those two questions and on all of `game-value`'s, which make every throw playable and every finish valued: where either number alone can be played the higher is compelled, a man hit mid-bear-off who re-enters bears off again only once every man is home, the finish no named result covers is a hit, and a loser both gammoned and backgammoned by the corpus's words is backgammoned. A throw or finish version 5 declined for any of them is played or valued, and names the ruling (`docs/decisions/0010`). Version 5 began with Brandon's rulings of 2026-09-15 on, which answer the second parts of two questions `RulesFactory.Maps.HoyleBackgammon` 6.0.0 leaves open, and not from the corpus: orders of a throw reaching the same position are one play, and bearing off begins within the throw that brings the last man home. A throw version 4 declined for either is played, and the play names the ruling (`docs/decisions/0009`). Version 4 began with map 6.0.0 and declined both (`docs/decisions/0008`). Version 3 began with `RulesFactory.Maps.HoyleBackgammon` 4.0.0, which makes a win against a loser with nothing off and a man in the winner's home table decline where version 2 valued it a backgammon (`docs/decisions/0005`). Version 2 began with map 3.0.0, whose corrections made some games decline where version 1 finished them (`docs/decisions/0004`).

    public static Resolution<GameRecord> Play(AssertedPosition start, IRandomSource source, IDecider decider, Player? opener = null, int turnLimit = 100000)
      /// Plays a game from `start`.
      /// Remarks: The position is demanded rather than defaulted. The engine does have the corpus's starting arrangement (`HoyleBackgammon.Setup.StartingPositionFromCorpus`) and a caller may hand it straight back in, but most games worth playing out here do not begin there — a mid-game study or a replayed log begins wherever it begins, and defaulting would make "the corpus's arrangement" and "whatever the caller had in mind" look the same in the record. So the assertion travels into `HoyleBackgammon.GameRecord.Start`, and a reader of a result can always see whose position it was played from.
      /// Parameter start: The asserted starting position.
      /// Parameter source: The generator. Consumed one draw per die thrown.
      /// Parameter decider: Where the choices come from.
      /// Parameter opener: Who begins, when the previous game settled it — `HoyleBackgammon.MapEntries.NextGameOpening` gives the winner of a hit the first throw with no roll for the right. Null throws for the right as at starting.
      /// Parameter turnLimit: A runaway guard, not a rule. Nothing in the corpus bounds a game's length; this exists so a bug cannot hang a test run.

#### public sealed record GameRecord
/// A finished game, with the replay identity and the map it was played under.
/// Remarks: Two records are comparable only when `HoyleBackgammon.GameRecord.Identity` and `HoyleBackgammon.GameRecord.Map` agree. `HoyleBackgammon.GameRecord.ToCanonicalJson` is the record as bytes, the engine's own and the only rendering a replay should hash (`docs/decisions/0006`).
/// Parameter Identity: The replay identity the game was played under, `HoyleBackgammon.Game.Identity`.
/// Parameter Map: The map package the engine was produced from, `HoyleBackgammon.MapPackage.FromProvenance`.
/// Parameter Start: The position the game began from, and who asserted it.
/// Parameter OpeningRoll: The throw for the right to begin, or null when the previous game settled who opens.
/// Parameter OpeningThrowAdopted: Whether the opener adopted the deciding pair.
/// Parameter Turns: Every turn, in order.
/// Parameter Winner: Who won.
/// Parameter Value: Whether the win was a hit, a gammon or a backgammon. `HoyleBackgammon.GameRecord.ValueRulings` names any owner's ruling it relies on.
/// Parameter Next: Who throws first in the game after this one.

    public GameRecord(ReplayCompatibilityIdentity Identity, MapPackage Map, AssertedPosition Start, OpeningRoll? OpeningRoll, bool OpeningThrowAdopted, ImmutableArray<Turn> Turns, Player Winner, GameValue Value, NextOpening Next)
      /// A finished game, with the replay identity and the map it was played under.
      /// Remarks: Two records are comparable only when `HoyleBackgammon.GameRecord.Identity` and `HoyleBackgammon.GameRecord.Map` agree. `HoyleBackgammon.GameRecord.ToCanonicalJson` is the record as bytes, the engine's own and the only rendering a replay should hash (`docs/decisions/0006`).
      /// Parameter Identity: The replay identity the game was played under, `HoyleBackgammon.Game.Identity`.
      /// Parameter Map: The map package the engine was produced from, `HoyleBackgammon.MapPackage.FromProvenance`.
      /// Parameter Start: The position the game began from, and who asserted it.
      /// Parameter OpeningRoll: The throw for the right to begin, or null when the previous game settled who opens.
      /// Parameter OpeningThrowAdopted: Whether the opener adopted the deciding pair.
      /// Parameter Turns: Every turn, in order.
      /// Parameter Winner: Who won.
      /// Parameter Value: Whether the win was a hit, a gammon or a backgammon. `HoyleBackgammon.GameRecord.ValueRulings` names any owner's ruling it relies on.
      /// Parameter Next: Who throws first in the game after this one.

    public AssertedPosition Start { get; init; }
      /// The position the game began from, and who asserted it.

    public GameResult Result { get; }
      /// The game's result, for scoring a rubber: the winner and the value, with the rulings the value relies on.

    public GameValue Value { get; init; }
      /// Whether the win was a hit, a gammon or a backgammon. `HoyleBackgammon.GameRecord.ValueRulings` names any owner's ruling it relies on.

    public ImmutableArray<OwnerRuling> ValueRulings { get; init; }
      /// The owner's rulings `HoyleBackgammon.GameRecord.Value` relies on, in `HoyleBackgammon.OwnerRulings.All`'s order; empty when the corpus names the result unaided (`HoyleBackgammon.GameResult.Rulings`, `docs/decisions/0010`).

    public ImmutableArray<Turn> Turns { get; init; }
      /// Every turn, in order.

    public MapPackage Map { get; init; }
      /// The map package the engine was produced from, `HoyleBackgammon.MapPackage.FromProvenance`.

    public NextOpening Next { get; init; }
      /// Who throws first in the game after this one.

    public OpeningRoll? OpeningRoll { get; init; }
      /// The throw for the right to begin, or null when the previous game settled who opens.

    public Player Winner { get; init; }
      /// Who won.

    public ReplayCompatibilityIdentity Identity { get; init; }
      /// The replay identity the game was played under, `HoyleBackgammon.Game.Identity`.

    public bool OpeningThrowAdopted { get; init; }
      /// Whether the opener adopted the deciding pair.

    public byte[] ToCanonicalJson()
      /// The record in its canonical serialisation, replay schema 4: RFC 8785 canonical JSON, UTF-8 without a byte-order mark, every field of the record including `HoyleBackgammon.GameRecord.Identity`, `HoyleBackgammon.GameRecord.Map`, on each turn played the owner's rulings its play relies on (`HoyleBackgammon.Play.Rulings`), and the owner's rulings the game's value relies on (`HoyleBackgammon.GameRecord.ValueRulings`), each with who ruled and when. The same game gives the same bytes on every run, framework and platform (`docs/decisions/0006` defines the shape; `docs/decisions/0009` adds each turn's `rulings`; `docs/decisions/0010` adds `valueRulings`).
      /// Returns: The bytes.

#### public sealed record GameResult
/// A won game: who won it, what kind of win it was, and the owner's rulings its value relied on.
/// Parameter Winner: Who won the game.
/// Parameter Value: Whether it was a hit, a gammon or a backgammon.

    public GameResult(Player Winner, GameValue Value)
      /// A won game: who won it, what kind of win it was, and the owner's rulings its value relied on.
      /// Parameter Winner: Who won the game.
      /// Parameter Value: Whether it was a hit, a gammon or a backgammon.

    public GameValue Value { get; init; }
      /// Whether it was a hit, a gammon or a backgammon.

    public ImmutableArray<OwnerRuling> Rulings { get; init; }
      /// The owner's rulings `HoyleBackgammon.GameResult.Value` relies on, in `HoyleBackgammon.OwnerRulings.All`'s order; empty when the corpus names the result unaided. Since ruleset version 6, `HoyleBackgammon.OwnerRulings.TheUncoveredFinishIsAHit` or `HoyleBackgammon.OwnerRulings.TheOverlapIsABackgammon` (`docs/decisions/0010`). A result built by a caller carries what the caller gives it, and `HoyleBackgammon.Outcome.RubberWinner(System.Collections.Generic.IReadOnlyList{HoyleBackgammon.GameResult})` passes it on.

    public Player Winner { get; init; }
      /// Who won the game.

#### public enum GameValue : int
/// What a won game is worth, in kind.

    Hit = 0
      /// The adversary has got all his men home and has begun to bear off.

    Gammon = 1
      /// The winner bore off all his men before the adversary began to do the same. "The loser is said to be 'gammoned', and pays double the agreed stake."

    Backgammon = 2
      /// The winner bore off all his men while the adversary still had a man up, or in the winner's home table.

#### public static class Geometry
/// The board's fixed geometry: twenty-four points read as one course per player.
/// Remarks: The representation. A point is named by the number of pips a man standing on it still has to travel, counted for the player who owns the man: 24 at the start of his journey, 1 on his own ace point, 0 once borne off. The bar is pip 25, so entering with a die of `f` lands on pip `25 - f`. This is a representation, not a rule.
/// How far the arithmetic reaches. It makes entry (`HoyleBackgammon.MoveKind.Entry`), ordinary play (`HoyleBackgammon.MoveKind.Ordinary`) and a forward move inside the home table (`HoyleBackgammon.MoveKind.BearingOffMove`) one arithmetic: `to = from - die`. It does not extend to removal. `HoyleBackgammon.MoveKind.BearingOffRemove` only looks like it does, because it arises exactly when `from == die`; and `HoyleBackgammon.MoveKind.BearingOffHighest` plainly does not — it sets `To = `HoyleBackgammon.Geometry.BorneOffPip`` whatever the die was, so a man borne off the cinque point by a trois is `5/off(3)` and not `5/2(3)`. That is a rule, not arithmetic: `HoyleBackgammon.MapEntries.BearingOffHighest` names the point to remove from and says nothing about a distance.
/// What the corpus fixes and what it does not. The two ends of the course are stated (`HoyleBackgammon.MapEntries.DirectionOfTravel`): a man begins on the ace point of the adversary's home table and finishes on the like point of his own. The four quarters follow from the point designations (`HoyleBackgammon.MapEntries.PointDesignations`): inner tables number from the far end inward, so the adversary's ace point is his inner table's farthest point (pip 24) and his six point is next the bar (pip 19); outer tables number from the bar outward, so the adversary's outer bar point is pip 18 and his outer six point pip 13, which adjoins the player's own outer six point (pip 12), and the player's own outer bar point (pip 7) adjoins his own six point (pip 6) across the bar.
/// What the corpus does not fix, for lack of a readable Fig. 1, is which physical compartment is the inner table — the text says only that with the men placed as in Fig. 1 the right hand is the inner table. That is its own entry now, `HoyleBackgammon.MapEntries.InnerTableHandedness`, and it is the one fact in this corpus that is genuinely beyond a plain-text adapter. This engine never needs to know: every position it holds is expressed in the player-relative pips above. See `HoyleBackgammon.BeyondAdapter.WhichCompartmentIsTheInnerTable`, which no rule here calls.

    public const int BarPip = 25
      /// The pip a man on the bar occupies, so that entry is an ordinary move.

    public const int BorneOffPip = 0
      /// The pip a man reaches when it is borne off.

    public const int HomeTableHighestPip = 6
      /// The highest pip of a player's own inner (home) table.

    public const int PointCount = 24
      /// The number of points on the board.

    public static Quarter QuarterOf(int pip)
      /// Which quarter of the board a pip sits in, for the player whose pips these are.
      /// Throws System.ArgumentOutOfRangeException: If `pip` is not a point.

    public static bool IsPoint(int pip)
      /// True if `pip` names one of the twenty-four points. The bar (25) and borne off (0) are states a man can be in, not points.

    public static int Mirror(int pip)
      /// The same physical point, named from the other player's end of the course. Implements `HoyleBackgammon.MapEntries.DirectionOfTravel`: the two courses run in opposite directions over one set of twenty-four points, so the pips at a point sum to 25.
      /// Throws System.ArgumentOutOfRangeException: If `pip` is not a point.

    public static string NameOf(int pip)
      /// The point's name in Hoyle's vocabulary — "cinque point", "bar point" and so on — qualified by whose table it is in. Implements `HoyleBackgammon.MapEntries.PointDesignations`.
      /// Throws System.ArgumentOutOfRangeException: If `pip` is not a point.

#### public interface IDecider
/// Where every choice a game needs comes from.
/// Remarks: The engine plays no part in choosing. Determinism is "same seed and same ordered decisions give the same game", so the decisions have to come from somewhere outside the engine and be orderable.

    public bool AdoptOpeningThrow(OpeningRoll roll)
      /// Whether the opener adopts the deciding pair rather than throwing again. `HoyleBackgammon.MapEntries.OpeningThrowerOption`.

    public int ChoosePlay(Player player, ImmutableArray<Play> plays)
      /// Which of the legal plays to make, as an index into `plays`.

#### public interface IEntryRequest  [generated]
/// A request for one map entry; each entry has its own type (`Requests` namespace).

    public RuleRequest Assertions { get; }
      /// What the caller asserts, as the registry's dictionary dispatch reads it.

    public string EntryId { get; }
      /// The map entry this request resolves.

#### public sealed class ImplementsAttribute : Attribute  [generated]
/// Marks an untyped hand-written handler for a map entry. The method must be static, take one `HoyleBackgammon.RuleRequest` and return `Resolution<object>`, and it is checked only at runtime. It answers only once the entry's merged status is `implemented`; until then the entry declines as its row says. Prefer the typed partial method `HoyleBackgammon.Handlers` declares for the entry, which the compiler checks; an entry that has both is refused, and an `implemented` entry whose row has no default needs the typed one to build at all.
/// Parameter entryId: The map entry this method implements.

    public ImplementsAttribute(string entryId)
      /// Marks an untyped hand-written handler for a map entry. The method must be static, take one `HoyleBackgammon.RuleRequest` and return `Resolution<object>`, and it is checked only at runtime. It answers only once the entry's merged status is `implemented`; until then the entry declines as its row says. Prefer the typed partial method `HoyleBackgammon.Handlers` declares for the entry, which the compiler checks; an entry that has both is refused, and an `implemented` entry whose row has no default needs the typed one to build at all.
      /// Parameter entryId: The map entry this method implements.

    public string EntryId { get; }
      /// The map entry this method implements.

#### public static class LegalPlays
/// Turning a throw into the set of plays the corpus allows.

    public static Resolution<ImmutableArray<Play>> For(Position position, Player player, ImmutableArray<int> entitlement)
      /// Every play `player` may make with `entitlement`. Where the corpus does not settle what the throw allows, the owner's rulings do, and each play names those it relies on.
      /// Remarks: `HoyleBackgammon.MapEntries.MustPlayWholeThrow`: "Any part of a throw which cannot be played is lost to the thrower, but every player is compelled to play the whole of his throw if it is possible to do so."
      /// Read as an obligation to play a set of numbers that cannot be extended: if the whole throw can be played, it must be, and nothing less than a maximal set is ever permissible, because a smaller set is precisely one that could be extended. That settles doublets — a line playing three of the four numbers strictly contains one playing two, so the three-number line is compelled — and it settles a throw where only one die can ever be played.
      /// What it does not settle is the map's recorded ambiguity: where either die alone can be played but not both, the two candidate plays are incomparable, neither can be extended, and the text gives no rule for choosing. The entry's fate is `unresolved`. Ruleset versions 2 to 5 returned `RulesKernel.Resolution.UnresolvedReason.RequiresInterpretation` there; since version 6 the owner's ruling compels the higher number, and the play names it (below).
      /// A second question, not this rule's. Where a line of the throw reaches a position in which `HoyleBackgammon.BearingOff.HasReEnteredMidBearOff(HoyleBackgammon.Position,HoyleBackgammon.Player)` holds with a number still to play -- from the start of the throw, or after entering the man that was hit -- which rules govern that number turns on whether bearing off lasts once a man is hit and re-enters, and the corpus does not say. That is `HoyleBackgammon.MapEntries.BearingOffEligible`'s question (`fate: unresolved` since `RulesFactory.Maps.HoyleBackgammon` 3.0.0, blind-mapping resolution rows 12 and 13). Versions 2 to 5 declined the throw citing that entry; since version 6 the owner's ruling answers it (below).
      /// A man up does not lift the compulsion. The map records no `enter-from-bar` suspension of `must-play-whole-throw` since 3.0.0 (row 66): the lines searched below begin with entry whenever a man is up, because `HoyleBackgammon.Movement.MovesForDie(HoyleBackgammon.Position,HoyleBackgammon.Player,System.Int32)` offers nothing else, and are held to the same maximal filter as any other.
      /// The enumeration contract.`HoyleBackgammon.Game.Play(HoyleBackgammon.AssertedPosition,RulesKernel.Randomness.IRandomSource,HoyleBackgammon.IDecider,System.Nullable{HoyleBackgammon.Player},System.Int32)` records a choice as an index into this list, so its length and order are part of replay as much as the dice are, and changing either changes what every recorded index means. They are fixed by, and only by, the following:
      /// - The distinct numbers of the entitlement are tried highest first (`HoyleBackgammon.Movement.Entitlement(Tabletop.Dice.DiceThrow)` already orders a throw higher first; this sorts again, so the order does not depend on the caller).
      /// - For each number, moves come in `HoyleBackgammon.Movement.MovesForDie(HoyleBackgammon.Position,HoyleBackgammon.Player,System.Int32)`'s order — highest origin first.
      /// - The search is depth-first: at each step every number still available is tried in that order, and each move is followed to the end before the next is tried. A line is appended when it cannot be extended, so the list is in depth-first pre-order of lines.
      /// - A memo on (position reached, how many of each number used) prunes any line that reaches a state an earlier line already reached. Of several orderings of moves that arrive at the same state, only the first enumerated survives; this is what fixes the length, and it is why rules 1–3 decide which moves are written down.
      /// - Lines not using the compelled numbers are then removed, keeping the order of the rest.
      /// Four owner's rulings, not Hoyle (`docs/decisions/0009` and `docs/decisions/0010`). Every play lists those it relies on in `HoyleBackgammon.Play.Rulings`, in `HoyleBackgammon.OwnerRulings.All`'s order. The first two, the questions' first parts, are version 6's (`docs/decisions/0010`):
      /// - `HoyleBackgammon.OwnerRulings.TheHigherNumberIsCompelled`, `HoyleBackgammon.MapEntries.MustPlayWholeThrow`'s first part: where the maximal uses are incomparable (either number alone, not both), the plays that use the higher number are the compelled ones, and each names the ruling. A throw with only one playable number compels it, as before, and names nothing: the corpus settles that.
      /// - `HoyleBackgammon.OwnerRulings.BearingOffStopsUntilEveryManIsHomeAgain`, `HoyleBackgammon.MapEntries.BearingOffEligible`'s first part: a player whose man, hit mid-bear-off, has re-entered plays his numbers as ordinary moves until every man is home again, which is what `HoyleBackgammon.BearingOff.IsEligible(HoyleBackgammon.Position,HoyleBackgammon.Player)` already gives. A play is marked where its line passes through a state where `HoyleBackgammon.BearingOff.HasReEnteredMidBearOff(HoyleBackgammon.Position,HoyleBackgammon.Player)` holds with a number still to play, or is reached from one, as for the ruling below.
      /// The second parts are version 5's (`docs/decisions/0009`). Map 6.0.0 (rules-factory#125) added them to the two questions, and ruleset version 4 declined both (`docs/decisions/0008`):
      /// - `HoyleBackgammon.OwnerRulings.APlayIsThePositionItReaches`, `HoyleBackgammon.MapEntries.MustPlayWholeThrow`'s second part: rule 4 stands, and orders reaching the same state are one play even where the rules that permit their moves differ. With the last man outside on the eight point and deuce ace thrown, 8/6 6/5 (a move-by-pip, then the ace under bearing off) is offered and stands for 8/7 7/5 (two move-by-pips). A play is marked with the ruling where some pruned order reaching its state had a different multiset of authorities; orders whose authorities agree (bar/22 22/16 and bar/19 19/16) never needed it and are not marked.
      /// - `HoyleBackgammon.OwnerRulings.BearingOffBeginsWithinTheThrow`, `HoyleBackgammon.MapEntries.BearingOffEligible`'s second part: bearing off begins as soon as every man is home, partway through the throw included, so with the last man on the nine point six-trois plays 9/3 then off with the trois. A play is marked with the ruling where the player was not eligible at the start of the throw and a move of the play is made under a bearing-off rule.
      /// [redacted by build-brief.py: test-name]
      /// Parameter position: The position before the throw is played.
      /// Parameter player: The player to move.
      /// Parameter entitlement: The numbers the throw entitles, from `HoyleBackgammon.Movement.Entitlement(Tabletop.Dice.DiceThrow)`.
      /// Returns: The plays, in a fixed enumeration order, never empty: a throw with nothing playable yields exactly one play, which moves no man. Since ruleset version 6 it never declines; it stays a resolution because the questions it answers are open in the map.

#### public static class MapEntries  [generated]
/// The 33 entries of RulesFactory.Maps.HoyleBackgammon 6.0.0, one static per entry, citations copied verbatim from the map.

    public const string SourceId = "hoyle-1909"
      /// The corpus every entry cites.

    public static DerivedMapEntry HitPaysSingleStake { get; }
      /// What a hit pays (`hit-pays-single-stake`).

    public static MapEntry AgreedBackgammonMultiple { get; }
      /// The multiple the players agreed a backgammon pays (`agreed-backgammon-multiple`).

    public static MapEntry BearingOffDoublets { get; }
      /// Doublets bear off or move, or both (`bearing-off-doublets`).

    public static MapEntry BearingOffEligible { get; }
      /// Bearing off begins when all men are home (`bearing-off-eligible`).

    public static MapEntry BearingOffHighest { get; }
      /// An unusable number bears off from the highest occupied point (`bearing-off-highest`).

    public static MapEntry BearingOffMoveOrRemove { get; }
      /// Each throw may move within the table or remove a man (`bearing-off-move-or-remove`).

    public static MapEntry BlotHit { get; }
      /// A single man is a blot and may be hit (`blot-hit`).

    public static MapEntry BoardTables { get; }
      /// The board is two tables, inner and outer (`board-tables`).

    public static MapEntry CallingTheThrow { get; }
      /// The thrower calls his throw, the higher number first (`calling-the-throw`).

    public static MapEntry DieFaces { get; }
      /// The faces a die bears, and the throws a pair of them can show (`die-faces`).

    public static MapEntry DirectionOfTravel { get; }
      /// The twenty-four points are one course with two ends (`direction-of-travel`).

    public static MapEntry Doublets { get; }
      /// Doublets are played twice over (`doublets`).

    public static MapEntry DoublingCube { get; }
      /// Doubling the stake during play (`doubling-cube`).

    public static MapEntry EnterFromBar { get; }
      /// A man on the bar re-enters before any other man moves (`enter-from-bar`).

    public static MapEntry FullTableSuspension { get; }
      /// Play is wholly suspended against a full home table (`full-table-suspension`).

    public static MapEntry GameValue { get; }
      /// A win is a hit, a gammon, or a backgammon (`game-value`).

    public static MapEntry InnerTableHandedness { get; }
      /// Which physical compartment of the board is the inner table (`inner-table-handedness`).

    public static MapEntry LegalDestination { get; }
      /// A man may be played only to a permitted point (`legal-destination`).

    public static MapEntry MadePoint { get; }
      /// Two men make a point (`made-point`).

    public static MapEntry MenCount { get; }
      /// Thirty men, fifteen to a side (`men-count`).

    public static MapEntry MoveByPip { get; }
      /// Each die moves one man that many points (`move-by-pip`).

    public static MapEntry MustPlayWholeThrow { get; }
      /// The whole throw must be played if it can be (`must-play-whole-throw`).

    public static MapEntry NextGameOpening { get; }
      /// Who throws first in the following game (`next-game-opening`).

    public static MapEntry OpeningRoll { get; }
      /// Deciding who begins (`opening-roll`).

    public static MapEntry OpeningThrowerOption { get; }
      /// The opening thrower may keep the throw or throw again (`opening-thrower-option`).

    public static MapEntry PlayerCount { get; }
      /// Backgammon is played by two persons (`player-count`).

    public static MapEntry PointDesignations { get; }
      /// How the twenty-four points are named and numbered (`point-designations`).

    public static MapEntry RubberScoring { get; }
      /// How games count towards a rubber (`rubber-scoring`).

    public static MapEntry StakeMultiplier { get; }
      /// What a gammon and a backgammon pay (`stake-multiplier`).

    public static MapEntry StartingPosition { get; }
      /// The starting arrangement of the men (`starting-position`).

    public static MapEntry StrategyAdvice { get; }
      /// The advisory principles of play (`strategy-advice`).

    public static MapEntry ThrowTwoDice { get; }
      /// All subsequent throws use both dice (`throw-two-dice`).

    public static MapEntry WinCondition { get; }
      /// First to remove all men wins (`win-condition`).

    public static SourceBaselineId Baseline { get; }
      /// The corpus baseline the map is true of.

#### public sealed record MapEntry  [generated]
/// One located entry of the map: its id, its name and its citation, verbatim.
/// Parameter Id: The map entry's stable slug.
/// Parameter Name: The entry's name, as the map records it.
/// Parameter Locator: Corpus id plus citation, as the map records it.

    public MapEntry(string Id, string Name, SourceLocator Locator)
      /// One located entry of the map: its id, its name and its citation, verbatim.
      /// Parameter Id: The map entry's stable slug.
      /// Parameter Name: The entry's name, as the map records it.
      /// Parameter Locator: Corpus id plus citation, as the map records it.

    public ImmutableArray<string> AssertedBy { get; init; }
      /// Who the corpus lets assert this entry, the map's `assertedBy` (rules-factory decision 0025): the corpus's own words, or `caller` where the corpus names nobody. Empty on an entry that is not `kind: assertion`. An engine checks an assertion's attribution against these, not its own reading.

    public SourceLocator Locator { get; init; }
      /// Corpus id plus citation, as the map records it.

    public string Id { get; init; }
      /// The map entry's stable slug.

    public string Name { get; init; }
      /// The entry's name, as the map records it.

    public override string ToString()
      /// (documentation inherited)

#### public sealed record MapPackage
/// The map package this engine was produced from, as its embedded `provenance.json` records it.
/// Parameter PackageId: The package id, e.g. `RulesFactory.Maps.HoyleBackgammon`.
/// Parameter Version: The package version, e.g. `5.0.0`.

    public MapPackage(string PackageId, string Version)
      /// The map package this engine was produced from, as its embedded `provenance.json` records it.
      /// Parameter PackageId: The package id, e.g. `RulesFactory.Maps.HoyleBackgammon`.
      /// Parameter Version: The package version, e.g. `5.0.0`.

    public static MapPackage FromProvenance { get; }
      /// The map package named by `HoyleBackgammon.EngineProvenance`: the `map.packageId` and `map.version` of the provenance `factory produce` wrote and the build embedded. Read from those bytes, never typed out here, so it cannot drift from what the engine was produced from.
      /// Throws System.InvalidOperationException: The embedded provenance has no map package.

    public string PackageId { get; init; }
      /// The package id, e.g. `RulesFactory.Maps.HoyleBackgammon`.

    public string Version { get; init; }
      /// The package version, e.g. `5.0.0`.

#### public readonly record struct Move
/// One man moved by one die.
/// Parameter From: The pip the man leaves, in the mover's own numbering; 25 is the bar.
/// Parameter To: The pip the man reaches; 0 means borne off.
/// Parameter Die: The number on the die that authorised it.
/// Parameter Kind: Which rule authorised it.
/// Parameter TakesUpBlot: Whether the destination held a lone adversary man, who is taken up onto the bar. `HoyleBackgammon.MapEntries.BlotHit`.

    public Move(int From, int To, int Die, MoveKind Kind, bool TakesUpBlot)
      /// One man moved by one die.
      /// Parameter From: The pip the man leaves, in the mover's own numbering; 25 is the bar.
      /// Parameter To: The pip the man reaches; 0 means borne off.
      /// Parameter Die: The number on the die that authorised it.
      /// Parameter Kind: Which rule authorised it.
      /// Parameter TakesUpBlot: Whether the destination held a lone adversary man, who is taken up onto the bar. `HoyleBackgammon.MapEntries.BlotHit`.

    public MapEntry Authority { get; }
      /// The map entry that authorises this move.

    public MoveKind Kind { get; init; }
      /// Which rule authorised it.

    public bool BearsOff { get; }
      /// True when this move bears a man off the board.

    public bool TakesUpBlot { get; init; }
      /// Whether the destination held a lone adversary man, who is taken up onto the bar. `HoyleBackgammon.MapEntries.BlotHit`.

    public int Die { get; init; }
      /// The number on the die that authorised it.

    public int From { get; init; }
      /// The pip the man leaves, in the mover's own numbering; 25 is the bar.

    public int To { get; init; }
      /// The pip the man reaches; 0 means borne off.

    public override string ToString()
      /// (documentation inherited)

#### public enum MoveKind : int
/// Which rule authorises a move.

    Entry = 0
      /// A man re-entering from the bar. `HoyleBackgammon.MapEntries.EnterFromBar`.

    Ordinary = 1
      /// A man played forward by the number on a die. `HoyleBackgammon.MapEntries.MoveByPip`.

    BearingOffMove = 2
      /// A man moved forward within the home table during bearing off. `HoyleBackgammon.MapEntries.BearingOffMoveOrRemove`.

    BearingOffRemove = 3
      /// A man removed from the point the die names. `HoyleBackgammon.MapEntries.BearingOffMoveOrRemove`.

    BearingOffHighest = 4
      /// A man removed from the highest occupied point because the number could not be dealt with in either other fashion. `HoyleBackgammon.MapEntries.BearingOffHighest`.

#### public static class Movement
/// Moving men: what a die entitles, where a man may be played, and the bar.

    public static ImmutableArray<Move> MovesForDie(Position position, Player player, int die)
      /// Every move `player` may make with a single die of `die`, in a fixed order: highest origin first.
      /// Remarks: Dispatches between the three regimes the corpus describes — entry from the bar, which suspends the rest (`HoyleBackgammon.MapEntries.EnterFromBar`); ordinary play (`HoyleBackgammon.MapEntries.MoveByPip`); and bearing off, once every man is home (`HoyleBackgammon.MapEntries.BearingOffEligible`).

    public static ImmutableArray<int> Entitlement(DiceThrow thrown)
      /// What the throw entitles the player to move, as a list of numbers.
      /// Remarks: `HoyleBackgammon.MapEntries.MoveByPip`: "The number uppermost on each die entitles the player to move one man forward a corresponding number of points." `HoyleBackgammon.MapEntries.Doublets`: "In the event of his throwing the same points with both dice (known as 'doublets'), he is entitled to play the throw twice over" — two aces move an aggregate of four points, double deuces eight, double threes twelve, so the throw yields four numbers, not two.
      /// Ordered higher first, which is the order Hoyle calls a throw in ("six deuce", "cinque trois", "quatre ace"). For doublets the order is immaterial; for the rest it fixes the order legal plays are enumerated in, which replay depends on.

    public static bool IsPermittedDestination(Position position, Player player, int pip)
      /// Whether `player` may play a man to his pip `pip`.
      /// Remarks: `HoyleBackgammon.MapEntries.LegalDestination`: "a man can only be played to a point which is either vacant or occupied by one or more men of the player, or by one man only of the adversary." Two or more adversary men — a point the adversary has made, `HoyleBackgammon.MapEntries.MadePoint` — refuses the move.
      /// This governs entry from the bar as well, which is a decision and not a reading the corpus forces. Three sentences later `HoyleBackgammon.MapEntries.EnterFromBar` gives an entering man only "a vacant point or blot", dropping this rule's second arm — a point the player's own men hold. The corpus says it twice, differently, and `rules-factory/docs/decisions/0006` rules that the general qualification governs and the entry sentence is shorthand for it. Both entries are `clarity: ambiguous` with `fate: decision` naming that record.

    public static bool IsWhollySuspended(Position position, Player player)
      /// Whether `player`'s play is wholly suspended: he has a man up and the adversary's home table is full, so he does not throw at all.
      /// Remarks: `HoyleBackgammon.MapEntries.FullTableSuspension`: "If the adverse player's home table is completely full — i.e., each point occupied by two or more men, his play is altogether suspended, the adversary continuing to throw and move until the course of play again throws open one or more points in his table."
      /// "Altogether suspended" is stronger than "has no legal play", and the difference is observable: a suspended player does not throw, so the dice are not consumed and the next throw from a seeded generator belongs to his adversary. Treating suspension as an empty turn would change every subsequent throw in the game.
      /// "Full" means full of the adversary's men, which the corpus's "each point occupied by two or more men" does not say — read literally, two of the entering player's own men would shut the table against him. That is a decision, not the only reading: `rules-factory/docs/decisions/0006`, the same record that rules the general destination rule governs entry, and necessarily so, since a point a man may enter on cannot be one that shuts him out. Hence `HoyleBackgammon.Position.HasMadePoint(HoyleBackgammon.Player,System.Int32)` against the adversary below, and not a count of whoever's men stand there.

    public static bool MustEnterFromBar(Position position, Player player)
      /// Whether `player` has a man on the bar, which suspends every other man.
      /// Remarks: `HoyleBackgammon.MapEntries.EnterFromBar`: a man taken up "has to begin its journey anew from the inner table of the adversary. Nor can such man again start on its journey until its owner is fortunate enough to make a throw corresponding with a vacant point or blot in such table. Until he does this, the play of his other men is suspended." This is the `suspendedBy` relation the map records on `move-by-pip`, `doublets`, `bearing-off-move-or-remove`, `bearing-off-highest` and `bearing-off-doublets` -- the last three since `RulesFactory.Maps.HoyleBackgammon` 3.0.0 (blind-mapping resolution rows 11, 14 and 17), which is why `HoyleBackgammon.Movement.MovesForDie(HoyleBackgammon.Position,HoyleBackgammon.Player,System.Int32)` tests it before bearing off.
      /// It is not recorded on `must-play-whole-throw` any more (row 66): a man up suspends "the play of his other men", not the throw, and "every player is compelled to play the whole of his throw if it is possible". `HoyleBackgammon.LegalPlays.For(HoyleBackgammon.Position,HoyleBackgammon.Player,System.Collections.Immutable.ImmutableArray{System.Int32})` compels the whole throw with a man up exactly as without one: entering with both numbers where both enter, and playing on once entered.

#### public enum NextOpening : int
/// Who throws first in the game after this one.

    WinnerThrowsFirst = 0
      /// "The winner of a 'hit' throws first in the game next following."

    ThrowAgainForTheRight = 1
      /// "After a gammon or backgammon, the players throw again for the right to begin, as at starting."

#### public static class Opening
/// Beginning a game.

    public static DiceThrow OpeningThrow(OpeningRoll roll, bool adopt, IRandomSource source)
      /// The opener's first throw: either the deciding pair adopted as it stands, or a fresh throw of both dice.
      /// Remarks: `HoyleBackgammon.MapEntries.OpeningThrowerOption`: "The thrower of the higher number may either adopt the points shown by the two dice as his own throw, or throw again."
      /// "The two dice" are the two single dice just thrown for the right to begin — one each — so the first throw of the game is a two-dice throw either way, and `HoyleBackgammon.MapEntries.ThrowTwoDice`'s "all subsequent throws are with both dice" never has to reach back to it. An adopted pair can never be doublets, because a tie would have been thrown again.
      /// Parameter roll: The roll for the right to begin.
      /// Parameter adopt: Whether the opener adopts the deciding pair.
      /// Parameter source: Consulted only when he throws again.

    public static DiceThrow Throw(IRandomSource source)
      /// An ordinary throw of both dice. `HoyleBackgammon.MapEntries.ThrowTwoDice`: "All subsequent throws are with both dice."
      /// Remarks: Six faces a die, from `HoyleBackgammon.MapEntries.DieFaces`: the corpus names twenty-one throws and calls them "all the possible throws", and twenty-one unordered pairs fix six faces. It never says the dice are fair, so this is the support, not the distribution.

    public static OpeningRoll RollForTheRight(IRandomSource source)
      /// Throws for the right to begin.
      /// Remarks: `HoyleBackgammon.MapEntries.OpeningRoll`: "The game is commenced by each player throwing on the centre of the board a single die, the higher throw of the two giving the right to begin. In the event of a tie, the players throw again."
      /// Which player throws his single die first is not stated and does not matter to the outcome; it matters to replay, because it fixes the order draws are taken in. This engine throws White's die then Black's, and that is an engine convention, not a rule.

#### public sealed record OpeningRoll
/// The throw for the right to begin, and its outcome.
/// Parameter Attempts: Every pair thrown, in order, each holding White's die and Black's. A tie throws again, so all but the last are ties.
/// Parameter Opener: The player who threw the higher number and has the right to begin.

    public OpeningRoll(ImmutableArray<DiceThrow> Attempts, Player Opener)
      /// The throw for the right to begin, and its outcome.
      /// Parameter Attempts: Every pair thrown, in order, each holding White's die and Black's. A tie throws again, so all but the last are ties.
      /// Parameter Opener: The player who threw the higher number and has the right to begin.

    public DiceThrow Deciding { get; }
      /// The deciding pair — the two dice whose points the opener may adopt.

    public ImmutableArray<DiceThrow> Attempts { get; init; }
      /// Every pair thrown, in order, each holding White's die and Black's. A tie throws again, so all but the last are ties.

    public Player Opener { get; init; }
      /// The player who threw the higher number and has the right to begin.

#### public static class OutOfScope
/// The three entries the map records as `scope: out`, reachable rather than absent.
/// Remarks: A caller who asks this engine to double, or to tell them how to open, gets an answer that names the entry and says why — not a missing method. "Absent from the corpus" and "nobody looked" must not be indistinguishable, and at runtime that means the engine has to be able to say which one it is.

    public static Resolution<Play> BestOpening()
      /// How to play a given opening throw well. `HoyleBackgammon.MapEntries.StrategyAdvice`, `scope: out`: Hints for Play is advice, not rules.
      /// Returns: Always `RulesKernel.Resolution.UnresolvedReason.OutsideCurrentScope`.

    public static Resolution<int> Double()
      /// Doubling. `HoyleBackgammon.MapEntries.DoublingCube`, `scope: out`: this 1909 corpus predates the doubling cube, so the rule is not in it. An engine built from this corpus is a 1909 engine.
      /// Returns: Always `RulesKernel.Resolution.UnresolvedReason.OutsideCurrentScope`.

    public static Resolution<string> CallTheThrow()
      /// Calling a throw aloud, the higher number first. `HoyleBackgammon.MapEntries.CallingTheThrow`, `scope: out`: the corpus states it and it is normative, but it is spoken by one player to the other, moves no man, and the corpus attaches no consequence to it. The move is made in accordance with the throw, not the call, so an engine handed the dice has nothing to do with it.
      /// Returns: Always `RulesKernel.Resolution.UnresolvedReason.OutsideCurrentScope`.

#### public static class Outcome
/// Winning, and what the win is worth.

    public static NextOpening Next(GameValue value)
      /// Who throws first in the next game. `HoyleBackgammon.MapEntries.NextGameOpening`: "Where several games are played in succession, the winner of a 'hit' throws first in the game next following. After a gammon or backgammon, the players throw again for the right to begin, as at starting."

    public static Player? Winner(Position position)
      /// The player who has won, if either has. `HoyleBackgammon.MapEntries.WinCondition`: "The player who first succeeds in removing all his men from the board wins the game."

    public static Resolution<GameResult> ResultOf(Position position, Player winner)
      /// What kind of win `winner` has: a hit, a gammon or a backgammon, with the owner's rulings the answer relies on (`HoyleBackgammon.GameResult.Rulings`).
      /// Remarks: `HoyleBackgammon.MapEntries.GameValue` gives three conditions on the loser's state: he "has got all his men into his own home table, and has begun to bear off" (a hit); the winner finished "before his adversary has begun to do the same" (a gammon); the adversary "has still a man or men 'up' (i.e., on the bar) or in his (the winner's) home table" (a backgammon).
      /// The overlap. A man up does not imply nothing has been borne off: a player may bear off and then be hit, which is the very manoeuvre the gap case below turns on — a loser holding `{bar 1, off 3}` is a backgammon by the corpus's words, and nothing else. What does overlap is a loser who has borne off nothing and has a man up: he answers the gammon condition and the backgammon condition both. This engine used to test backgammon first, on the ground that the corpus plainly intends the larger name to win, and the map's note recorded that an ordering had been chosen. Since `RulesFactory.Maps.HoyleBackgammon` 3.0.0 the map's `ambiguity.question` names that overlap (blind-mapping resolution row 52) and the ordering is gone from the note, so the case returned `RulesKernel.Resolution.UnresolvedReason.RequiresInterpretation` from ruleset version 2 to 5.
      /// The backgammon condition has two arms, a man up or a man in the winner's home table, and a loser who has borne off nothing answers the gammon condition beside either. Map 3.0.0's question named only the man up, so this declined only him and still valued the man in the winner's home table a backgammon. Finding 17 in `MAP-FINDINGS.md` took that upstream, and since `RulesFactory.Maps.HoyleBackgammon` 4.0.0 (rules-factory#102) the question names both, so both declined.
      /// Since ruleset version 6 both are the owner's ruling, `HoyleBackgammon.OwnerRulings.TheOverlapIsABackgammon` (`docs/decisions/0010`): such a loser is backgammoned, and never gammoned as well, and the result names the ruling. A loser with a man up or in the winner's home table who has borne off is the corpus's own backgammon and names nothing.
      /// The three are not exhaustive. A loser who has borne off a man, been taken up, re-entered and run the man clear of the winner's home table satisfies none of them: he has begun to bear off, so it is not a gammon; his men are not all home, so it is not a hit; he is neither up nor in the winner's home table, so it is not a backgammon. That case returned `RulesKernel.Resolution.UnresolvedReason.RequiresInterpretation` too until ruleset version 6, and since then it is a hit by the owner's ruling, `HoyleBackgammon.OwnerRulings.TheUncoveredFinishIsAHit`, which the result names (`docs/decisions/0010`). The entry is `clarity: ambiguous` with `fate: unresolved` and its `question` names exactly this finish. It used to be recorded `clarity: clear` while this line declined — the map saying the case could not happen while the engine handled it — which is finding 4 in `MAP-FINDINGS.md`.
      /// Throws System.ArgumentException: If `winner` has not in fact won.
      /// Returns: The result. It no longer declines since ruleset version 6, and stays a resolution because the question it answers is open in the map.

    public static Resolution<RubberResult> RubberWinner(IReadOnlyList<GameResult> games)
      /// Who has won the rubber, from its games in the order they were played.
      /// Remarks: `HoyleBackgammon.MapEntries.RubberScoring` (`RulesFactory.Maps.HoyleBackgammon` 3.0.0, blind-mapping resolution rows 114 and 115): "This case often arises where the player has already lost the first hit of a rubber, in which case, if he loses the next game, he has lost the rubber also; but if he can secure a gammon (reckoning as a double game), he becomes the winner of the rubber."
      /// That sentence settles two sequences, and this answers those two and nothing else:
      /// - a hit, then a second game won by the same player, whatever its value: he wins the rubber;
      /// - a hit, then a gammon won by the other player: the other player wins it.
      /// The answer names every owner's ruling the two games' values relied on (`HoyleBackgammon.RubberResult.Rulings`): since ruleset version 6 a game can be a hit or a backgammon by a ruling (`HoyleBackgammon.Outcome.ResultOf(HoyleBackgammon.Position,HoyleBackgammon.Player)`), and a rubber scored from it relies on the ruling too. So a rubber whose first game is the uncovered finish, a hit by `HoyleBackgammon.OwnerRulings.TheUncoveredFinishIsAHit`, now scores, and says so (`docs/decisions/0010`).
      /// Every other sequence returns `RulesKernel.Resolution.UnresolvedReason.RequiresInterpretation`. The map's question is why: the chapter "never defines a rubber's length or winning total, and does not say how a backgammon reckons". So a first game that was not a hit, a second game the loser of the first wins by a hit or a backgammon, a rubber of one game, and a rubber of three or more all decline — the last because nothing says a third game belongs to the rubber rather than to the next one.
      /// Parameter games: The rubber's games, first first.
      /// Throws System.ArgumentNullException: If `games` is null.

    public static StakeDue Pays(GameValue value, AgreedBackgammonMultiple agreed)
      /// What the result pays, as a multiple of the single stake, under the multiple the players agreed for a backgammon.
      /// Remarks: `HoyleBackgammon.MapEntries.StakeMultiplier` states two figures: a gammon "double the agreed stake", and a backgammon "either thrice or four times (as may have been agreed) the amount of the single stake". That a hit pays the single stake is stated nowhere; it is `HoyleBackgammon.MapEntries.HitPaysSingleStake`, derived from those two. Only the last is delegated, to an agreement, so it is not a gap. It is `HoyleBackgammon.MapEntries.AgreedBackgammonMultiple`, an assertion of its own, and this rule depends on it — which is why the parameter is required rather than optional and why there is no overload that does without it. An engine that returned `RulesKernel.Resolution.UnresolvedReason.RequiresInterpretation` here would be declining a job the corpus gave it the means to do.
      /// The result carries the agreement back out (`HoyleBackgammon.StakeDue.Agreement`) for the same reason a `HoyleBackgammon.GameRecord` carries the position it was played from: an asserted input that vanishes into a number cannot be attributed afterwards. It carries it for a hit and a gammon too, which the agreement does not change. There used to be a one-argument overload that declined a backgammon; it was removed with the map's reclassification — a source-breaking change, recorded in `rules-factory/docs/decisions/0005`.
      /// Parameter value: The kind of win.
      /// Parameter agreed: The agreement, attributed to whoever the caller names (the map's `assertedBy` is `caller`). Demanded, never inferred.
      /// Throws System.ArgumentNullException: If `agreed` is null.

#### public sealed record OwnerRuling  [generated]
/// An owner's ruling (rules-factory decision 0027): this engine's answer to part of a question its map records as `fate: unresolved`. It is the owner's, not the corpus's, so a result that relies on it names it, and nothing presents it as what the corpus says.
/// Parameter Id: A stable id, `<entry id>/<slug>`.
/// Parameter EntryId: The map entry whose `ambiguity.question` it answers part of.
/// Parameter Span: The part of that question it answers, quoted verbatim from the map.
/// Parameter Answer: The ruling, stated briefly.
/// Parameter RuledBy: Who ruled.
/// Parameter RuledOn: When.
/// Parameter Record: The engine's decision record that holds the ruling, relative to the engine root.
/// This engine's additions to the `HoyleBackgammon.OwnerRuling` rules-factory generates from the overlay's `rulings` (`Generated/Rulings.g.cs`, rules-factory decision 0027). The metadata is the overlay's; nothing here restates it.

    public OwnerRuling(string Id, string EntryId, string Span, string Answer, string RuledBy, DateOnly RuledOn, string Record)
      /// An owner's ruling (rules-factory decision 0027): this engine's answer to part of a question its map records as `fate: unresolved`. It is the owner's, not the corpus's, so a result that relies on it names it, and nothing presents it as what the corpus says.
      /// Parameter Id: A stable id, `<entry id>/<slug>`.
      /// Parameter EntryId: The map entry whose `ambiguity.question` it answers part of.
      /// Parameter Span: The part of that question it answers, quoted verbatim from the map.
      /// Parameter Answer: The ruling, stated briefly.
      /// Parameter RuledBy: Who ruled.
      /// Parameter RuledOn: When.
      /// Parameter Record: The engine's decision record that holds the ruling, relative to the engine root.

    public DateOnly RuledOn { get; init; }
      /// When.

    public int QuestionPart { get; }
      /// Which part of the entry's `ambiguity.question` the ruling answers, counting from 1: the number after the slash in `HoyleBackgammon.OwnerRuling.Id`, which this engine's ids always carry (`must-play-whole-throw/2`).
      /// Remarks: The overlay names the part by its `HoyleBackgammon.OwnerRuling.Span`, and that is what the factory checks. The number is derived for the replay record, which carries `questionPart` since schema 3 (`docs/decisions/0009`), so the record's bytes did not change when the rulings moved into the overlay.

    public string Answer { get; init; }
      /// The ruling, stated briefly.

    public string EntryId { get; init; }
      /// The map entry whose `ambiguity.question` it answers part of.

    public string Id { get; init; }
      /// A stable id, `<entry id>/<slug>`.

    public string Record { get; init; }
      /// The engine's decision record that holds the ruling, relative to the engine root.

    public string RuledBy { get; init; }
      /// Who ruled.

    public string Span { get; init; }
      /// The part of that question it answers, quoted verbatim from the map.

#### public static class OwnerRulings  [generated]
/// The 6 owner's ruling(s) in corpus-map.overlay.json, one static each, in overlay order.
/// Names for the generated rulings that say what each rules, and the order a result lists them in.

    public static ImmutableArray<OwnerRuling> All { get; }
      /// Every ruling, in overlay order.

    public static OwnerRuling APlayIsThePositionItReaches { get; }
      /// `must-play-whole-throw/2`: a play is the position it reaches (`docs/decisions/0009`).

    public static OwnerRuling BearingOffBeginsWithinTheThrow { get; }
      /// `bearing-off-eligible/2`: bearing off begins within the throw that brings the last man home (`docs/decisions/0009`).

    public static OwnerRuling BearingOffEligible1 { get; }
      /// `bearing-off-eligible/1`: No: a player whose man is hit after he has begun to bear off may not bear off again until every man is back in his home table.

    public static OwnerRuling BearingOffEligible2 { get; }
      /// `bearing-off-eligible/2`: Yes: once a player's first number brings his last man home, the number left bears off.

    public static OwnerRuling BearingOffStopsUntilEveryManIsHomeAgain { get; }
      /// `bearing-off-eligible/1`: a man hit mid-bear-off who re-enters stops bearing off until every man is home again (`docs/decisions/0010`).

    public static OwnerRuling GameValue1 { get; }
      /// `game-value/1`: A single game (a hit): a loser who has borne off a man, has none on the bar or in the winner's home table, and is not all home loses a hit.

    public static OwnerRuling GameValue2 { get; }
      /// `game-value/2`: A backgammon, never also a gammon: a loser who has borne off nothing and has a man on the bar or in the winner's home table is backgammoned.

    public static OwnerRuling MustPlayWholeThrow1 { get; }
      /// `must-play-whole-throw/1`: Where either number alone can be played but not both, the higher number must be played.

    public static OwnerRuling MustPlayWholeThrow2 { get; }
      /// `must-play-whole-throw/2`: One play: orders of the same numbers that reach the same position are offered once, crediting the rules of the first order found.

    public static OwnerRuling TheHigherNumberIsCompelled { get; }
      /// `must-play-whole-throw/1`: where either number alone can be played but not both, the higher is compelled (`docs/decisions/0010`).

    public static OwnerRuling TheOverlapIsABackgammon { get; }
      /// `game-value/2`: a loser with nothing off and a man up or in the winner's home table is backgammoned, not gammoned (`docs/decisions/0010`).

    public static OwnerRuling TheUncoveredFinishIsAHit { get; }
      /// `game-value/1`: the finish none of the three named results covers is a hit (`docs/decisions/0010`).

    public static ImmutableArray<OwnerRuling> InOrder(IEnumerable<OwnerRuling> rulings)
      /// `rulings` without repeats, in `HoyleBackgammon.OwnerRulings.All`'s order (overlay order): the one order every result lists its rulings in, whatever order they were relied on.

#### public sealed record Play
/// A whole throw played out: the moves in the order they were made, and where they left the board.
/// Parameter Moves: The moves, in order. Empty when nothing could be played.
/// Parameter Result: The position after all of them.

    public Play(ImmutableArray<Move> Moves, Position Result)
      /// A whole throw played out: the moves in the order they were made, and where they left the board.
      /// Parameter Moves: The moves, in order. Empty when nothing could be played.
      /// Parameter Result: The position after all of them.

    public ImmutableArray<Move> Moves { get; init; }
      /// The moves, in order. Empty when nothing could be played.

    public ImmutableArray<OwnerRuling> Rulings { get; init; }
      /// The owner's rulings this play relies on, in `HoyleBackgammon.OwnerRulings.All`'s order; empty when it relies on none. A ruling answers part of a question the corpus leaves open, so a play that lists one is offered on its owner's authority and not Hoyle's (`docs/decisions/0009`, `docs/decisions/0010`):
      /// - `HoyleBackgammon.OwnerRulings.TheHigherNumberIsCompelled` where either number of the throw alone could be played but not both, and this play uses the higher;
      /// - `HoyleBackgammon.OwnerRulings.APlayIsThePositionItReaches` where another order of the same numbers reaches the same position under different rules, and this play, the first order found, stands for both;
      /// - `HoyleBackgammon.OwnerRulings.BearingOffStopsUntilEveryManIsHomeAgain` where the play is made by a player whose man, hit after he began to bear off, has re-entered, with a number still to play, so it is made without bearing off;
      /// - `HoyleBackgammon.OwnerRulings.BearingOffBeginsWithinTheThrow` where a move of this play bears off, or moves within the home table under bearing off, in a throw that began before every man was home.
      /// Each move's `HoyleBackgammon.Move.Authority` is still the map entry that permits it once the ruling is applied.

    public Position Result { get; init; }
      /// The position after all of them.

    public int PipsUsed { get; }
      /// The total number of pips this play consumed from the throw.

    public override string ToString()
      /// (documentation inherited)

#### public enum Player : int
/// One of the two players. `HoyleBackgammon.MapEntries.PlayerCount`: "Backgammon is played by two persons."
/// Remarks: The type is closed over exactly two, and every player-relative rule here rests on that: `HoyleBackgammon.Players.Adversary(HoyleBackgammon.Player)` is total only because there is exactly one other player, and `HoyleBackgammon.Geometry.Mirror(System.Int32)` pairs the two courses for the same reason.

    White = 0
      /// White.

    Black = 1
      /// Black — "fifteen white and fifteen black (or red)".

#### public static class Players
/// Helpers over `HoyleBackgammon.Player`.

    public static readonly IReadOnlyList<Player> Both
      /// Both players, White first. The order is the engine's, not the corpus's.

    public static Player Adversary(this Player player)
      /// The other player.

#### public sealed class Position : IEquatable<Position>
/// Where every man stands. Immutable; each move produces a new position.
/// Remarks: Held as two arrays of counts, one per player, each indexed by that player's own pip numbering (see `HoyleBackgammon.Geometry`): index 0 is men borne off, 1 through 24 the points, and 25 the bar. The same physical point is index `p` for one player and `HoyleBackgammon.Geometry.Mirror(System.Int32)` of `p` for the other.
/// Nothing in this type knows the starting arrangement, and that is now a separation of concerns rather than a decline: the corpus's arrangement is `HoyleBackgammon.Setup.StartingPositionFromCorpus`, which builds one of these like any other caller. Any other position comes from a caller who is answerable for it — see `HoyleBackgammon.AssertedPosition`.

    public const int MenPerPlayer = 15
      /// Fifteen. `HoyleBackgammon.MapEntries.MenCount`: "thirty 'men,' fifteen white and fifteen black (or red)".

    public const int TotalMen = 30
      /// Thirty. `HoyleBackgammon.MapEntries.MenCount`.

    public IEnumerable<int> OccupiedPoints(Player player)
      /// The pips on which `player` has at least one man, highest first.

    public Position Apply(Player player, int from, int to)
      /// The result of moving one of `player`'s men from `from` to `to`, taking up an adversary blot on the destination.
      /// Remarks: Applies `HoyleBackgammon.MapEntries.BlotHit`: a lone adversary man on the destination is "taken up (placed on the bar between the two tables)". This method does not ask whether the move is legal; that is `HoyleBackgammon.Movement`'s and `HoyleBackgammon.BearingOff`'s work.

    public bool Equals(Position? other)
      /// (documentation inherited)

    public bool HasBlot(Player player, int pip)
      /// True when `player` has exactly one man on `pip` — a blot. `HoyleBackgammon.MapEntries.BlotHit`.

    public bool HasMadePoint(Player player, int pip)
      /// True when `player` has two or more men on `pip` — he has "made" the point. `HoyleBackgammon.MapEntries.MadePoint`.

    public int AdversaryMen(Player player, int pip)
      /// How many of the adversary's men stand on the point `player` calls `pip`.

    public int BorneOff(Player player)
      /// How many of `player`'s men have been borne off.

    public int Men(Player player, int pip)
      /// How many of `player`'s men stand on his pip `pip`.

    public int OnBar(Player player)
      /// How many of `player`'s men are on the bar.

    public override bool Equals(object? obj)
      /// (documentation inherited)

    public override int GetHashCode()
      /// (documentation inherited)

    public override string ToString()
      /// A stable, replayable rendering: White's men by his own pips, then Black's. Used in tests as the evidence that two runs produced the same game, not merely the same winner.

    public static Position Create(IReadOnlyDictionary<int, int> white, IReadOnlyDictionary<int, int> black)
      /// Builds a position from each player's men, keyed by that player's own pip numbering (0 borne off, 1-24 the points, 25 the bar).
      /// Remarks: Enforces `HoyleBackgammon.MapEntries.MenCount` — fifteen men a side, thirty in all — and the geometric fact that one point cannot hold men of both players, which is `HoyleBackgammon.MapEntries.LegalDestination` read as an invariant rather than as a test on a move.
      /// Throws System.ArgumentException: If either side does not hold exactly fifteen men, or if a point holds men of both players.

#### public enum Quarter : int
/// Which of the four quarters of the board a point sits in, relative to one player.

    OwnInner = 0
      /// The player's own inner (home) table: his pips 1 through 6.

    OwnOuter = 1
      /// The player's own outer table: his pips 7 through 12.

    AdversaryOuter = 2
      /// The adversary's outer table: his pips 13 through 18.

    AdversaryInner = 3
      /// The adversary's inner (home) table: his pips 19 through 24.

#### public sealed record RegisteredEntry  [generated]
/// One registered map entry.
/// Parameter Id: The map entry's id.
/// Parameter Status: Its merged status.
/// Parameter Row: The first correspondence row it matches.
/// Parameter Locators: Every locator the entry cites. One, its own, for a located entry. For a derived entry (rules-factory decision 0012), the locator of every located entry it rests on, following derived sources down, depth-first in `derivedFrom` order, each locator once at its first place: the premises entail the fact together, so a decline citing only the first says less than the map knows. `HoyleBackgammon.Registry.Citations(System.String)` reads them for a declined entry.

    public RegisteredEntry(string Id, EntryStatus Status, CorrespondenceRow Row, ImmutableArray<SourceLocator> Locators)
      /// One registered map entry.
      /// Parameter Id: The map entry's id.
      /// Parameter Status: Its merged status.
      /// Parameter Row: The first correspondence row it matches.
      /// Parameter Locators: Every locator the entry cites. One, its own, for a located entry. For a derived entry (rules-factory decision 0012), the locator of every located entry it rests on, following derived sources down, depth-first in `derivedFrom` order, each locator once at its first place: the premises entail the fact together, so a decline citing only the first says less than the map knows. `HoyleBackgammon.Registry.Citations(System.String)` reads them for a declined entry.

    public CorrespondenceRow Row { get; init; }
      /// The first correspondence row it matches.

    public EntryStatus Status { get; init; }
      /// Its merged status.

    public ImmutableArray<SourceLocator> Locators { get; init; }
      /// Every locator the entry cites. One, its own, for a located entry. For a derived entry (rules-factory decision 0012), the locator of every located entry it rests on, following derived sources down, depth-first in `derivedFrom` order, each locator once at its first place: the premises entail the fact together, so a decline citing only the first says less than the map knows. `HoyleBackgammon.Registry.Citations(System.String)` reads them for a declined entry.

    public ImmutableArray<string> AssertedBy { get; init; }
      /// Who the corpus lets assert this entry, the map's `assertedBy` (rules-factory decision 0025): the corpus's own words, or `caller` where the corpus names nobody. Empty on an entry that is not `kind: assertion`. An engine checks an assertion's attribution against these, not its own reading.

    public SourceLocator Locator { get; }
      /// The locator its declines cite, the first of `HoyleBackgammon.RegisteredEntry.Locators`: the kernel's `RulesKernel.Resolution.UnresolvedResult` holds one, and the rest are read through `HoyleBackgammon.Registry.Citations(System.String)`.

    public string Id { get; init; }
      /// The map entry's id.

#### public static class Registry  [generated]
/// Every map entry, the correspondence row it matches first, and the handler that answers it.

    public static ImmutableArray<RegisteredEntry> Entries { get; }
      /// Every map entry, in the map's order.

    public static ImmutableArray<SourceLocator> Citations(string entryId)
      /// Every locator `entryId` cites, for a caller holding its decline. The kernel's `RulesKernel.Resolution.UnresolvedResult.Locator` is one locator, the first of these; a derived entry rests on all of them.
      /// Parameter entryId: A map entry id.
      /// Returns: The entry's `HoyleBackgammon.RegisteredEntry.Locators`.
      /// Throws System.Collections.Generic.KeyNotFoundException: The map has no such entry.

    public static RegisteredEntry Entry(string entryId)
      /// The registered entry `entryId`.
      /// Parameter entryId: A map entry id.
      /// Returns: The entry.
      /// Throws System.Collections.Generic.KeyNotFoundException: The map has no such entry.

    public static Resolution<object> Resolve(IEntryRequest request)
      /// Resolves the entry `request` is for, exactly as `HoyleBackgammon.Registry.Resolve(System.String,HoyleBackgammon.RuleRequest)` does for its id and assertions, except that a typed handler receives `request` itself, with every input property the engine declared on its type. The typed entry points in `HoyleBackgammon.EntryPoints` resolve through here.
      /// Parameter request: A request for one map entry.
      /// Returns: The resolution.

    public static Resolution<object> Resolve(string entryId, RuleRequest request)
      /// Resolves `entryId`: through its hand-written handler when the entry is `implemented` and has one (the typed handler first, which answers unless an optional hook leaves the resolution null), otherwise through the default its correspondence row fixes. A typed handler receives a request of its entry's type built from `request` alone, so any input property an engine declares on that type has its default value; to pass inputs, resolve through `HoyleBackgammon.Registry.Resolve(HoyleBackgammon.IEntryRequest)` or `HoyleBackgammon.EntryPoints`.
      /// Parameter entryId: A map entry id.
      /// Parameter request: What the caller asserts.
      /// Returns: The resolution.

    public static bool HasImplementation(string entryId)
      /// Whether a hand-written handler exists for `entryId`: a typed partial method of `HoyleBackgammon.Handlers`, or an `HoyleBackgammon.ImplementsAttribute` method.
      /// Parameter entryId: A map entry id.
      /// Returns: True when one exists, whether or not the entry's status lets it answer.
      /// Throws System.InvalidOperationException: An `HoyleBackgammon.ImplementsAttribute` method is malformed or duplicates a handler.

#### public sealed record RubberResult
/// Who won a rubber, and the owner's rulings that answer relied on.
/// Parameter Winner: Who won the rubber.

    public RubberResult(Player Winner)
      /// Who won a rubber, and the owner's rulings that answer relied on.
      /// Parameter Winner: Who won the rubber.

    public ImmutableArray<OwnerRuling> Rulings { get; init; }
      /// The owner's rulings the answer relies on: every ruling the values of the games it was scored from relied on, without repeats, in `HoyleBackgammon.OwnerRulings.All`'s order. A rubber scored from a game valued by a ruling relies on that ruling as much as the game does (`docs/decisions/0010`).

    public Player Winner { get; init; }
      /// Who won the rubber.

#### public sealed class RuleEntry<TInput, TOutput>  [generated]
/// The typed entry point of one map entry. `TInput` is the entry's own request type, so a request for another entry does not compile. `TOutput` is the type the map declares for the entry's value, and `object` where it declares none.
/// Type parameter TInput: The entry's request type.
/// Type parameter TOutput: The entry's value type.

    public RegisteredEntry Registered { get; }
      /// The entry as the registry holds it: status, row and citations.

    public string Id { get; }
      /// The map entry's id.

    public Resolution<TOutput?> Resolve(TInput request)
      /// Resolves the entry through `HoyleBackgammon.Registry.Resolve(HoyleBackgammon.IEntryRequest)`, so its handler receives `request` itself.
      /// Parameter request: The entry's request.
      /// Returns: The resolution.

#### public sealed class RuleRequest  [generated]
/// What a caller supplies to resolve an entry: the values of the assertions it makes (row 8).

    public static RuleRequest Empty { get; }
      /// A request asserting nothing.

    public RuleRequest Assert(string entryId, object value)
      /// This request, also asserting `value` for the assertion entry `entryId`.
      /// Parameter entryId: The id of a `kind: assertion` entry.
      /// Parameter value: The caller's value for it.
      /// Returns: A new request.

    public object Asserted(string entryId)
      /// The value asserted for `entryId`.
      /// Parameter entryId: The id of a `kind: assertion` entry.
      /// Returns: The caller's value.
      /// Throws HoyleBackgammon.AssertionRequiredException: The caller asserted nothing for it.

#### public sealed class ScriptedDecider : IDecider
/// Replays a recorded list of decisions in order: a boolean decision consumes one entry and reads it as non-zero for yes; a play decision consumes one entry and uses it as an index.
/// Remarks: Running out of decisions is an error rather than a silent fallback. A fallback would make two different decision lists produce the same game, which is exactly the confusion the replay contract exists to prevent.

    public ScriptedDecider(IReadOnlyList<int> decisions)
      /// Replays `decisions` in order.

    public int Consumed { get; }
      /// How many decisions have been consumed so far.

    public bool AdoptOpeningThrow(OpeningRoll roll)
      /// (documentation inherited)

    public int ChoosePlay(Player player, ImmutableArray<Play> plays)
      /// (documentation inherited)

#### public static class Setup
/// Setting a game up.

    public static IReadOnlyDictionary<int, int> Arrangement { get; }
      /// The four points of the starting arrangement, in the mover's own pip numbering, with the number of his men on each. Two plus five plus three plus five is fifteen, which `HoyleBackgammon.Position.Create(System.Collections.Generic.IReadOnlyDictionary{System.Int32,System.Int32},System.Collections.Generic.IReadOnlyDictionary{System.Int32,System.Int32})` re-checks against `HoyleBackgammon.MapEntries.MenCount`.

    public static Position StartingPositionFromCorpus()
      /// The starting arrangement, derived from the corpus.
      /// Remarks: `HoyleBackgammon.MapEntries.StartingPosition` states it in prose: "two of White's men are placed on the ace point in Black's inner table, five are placed on the six point in Black's outer table, three on the deuce point in White's outer table, and five on the six point in White's inner table. Black's men are placed in like manner on the points immediately facing these."
      /// Read through `HoyleBackgammon.MapEntries.PointDesignations` and `HoyleBackgammon.MapEntries.DirectionOfTravel`, those four points are the mover's own pips 24, 13, 8 and 6 (`HoyleBackgammon.Setup.Arrangement`): Black's inner ace point is the far end of White's course, Black's outer six point is 13, White's own outer deuce point is 8, and his own inner six point is 6. "Immediately facing" is `HoyleBackgammon.Geometry.Mirror(System.Int32)`, which gives the same four numbers again in Black's own pips — so one table serves both sides.
      /// This returns a plain `HoyleBackgammon.Position` and not a `Resolution`: there is nothing left for a caller to settle. It used to decline, on a map version since retracted; see `docs/decisions/0003`.

#### public sealed record StakeDue
/// What a finished game pays, and the agreement it was settled under.
/// Remarks: The agreement travels with the figure even where it did not decide it — a hit pays the single stake and a gammon double whatever was agreed — because "record it alongside the outcome" is an obligation about the result, not about whichever branch happened to consult the input. A reader of a settled stake can always see whose agreement it was settled under, exactly as a reader of a `HoyleBackgammon.GameRecord` can see whose position it was played from.
/// Parameter Value: The kind of win being paid for.
/// Parameter Multiple: What it pays, as a multiple of the single stake.
/// Parameter Agreement: The players' agreement, as supplied.

    public StakeDue(GameValue Value, int Multiple, AgreedBackgammonMultiple Agreement)
      /// What a finished game pays, and the agreement it was settled under.
      /// Remarks: The agreement travels with the figure even where it did not decide it — a hit pays the single stake and a gammon double whatever was agreed — because "record it alongside the outcome" is an obligation about the result, not about whichever branch happened to consult the input. A reader of a settled stake can always see whose agreement it was settled under, exactly as a reader of a `HoyleBackgammon.GameRecord` can see whose position it was played from.
      /// Parameter Value: The kind of win being paid for.
      /// Parameter Multiple: What it pays, as a multiple of the single stake.
      /// Parameter Agreement: The players' agreement, as supplied.

    public AgreedBackgammonMultiple Agreement { get; init; }
      /// The players' agreement, as supplied.

    public GameValue Value { get; init; }
      /// The kind of win being paid for.

    public int Multiple { get; init; }
      /// What it pays, as a multiple of the single stake.

    public override string ToString()
      /// (documentation inherited)

#### public sealed record Turn
/// One player's turn, as it happened.
/// Parameter Player: Whose turn it was.
/// Parameter Thrown: What he threw, or null when his play was wholly suspended and he did not throw at all.
/// Parameter Play: What he played. Empty of moves when nothing in the throw could be played.
/// Parameter Position: The position his turn left behind.

    public Turn(Player Player, DiceThrow? Thrown, Play? Play, Position Position)
      /// One player's turn, as it happened.
      /// Parameter Player: Whose turn it was.
      /// Parameter Thrown: What he threw, or null when his play was wholly suspended and he did not throw at all.
      /// Parameter Play: What he played. Empty of moves when nothing in the throw could be played.
      /// Parameter Position: The position his turn left behind.

    public DiceThrow? Thrown { get; init; }
      /// What he threw, or null when his play was wholly suspended and he did not throw at all.

    public Play? Play { get; init; }
      /// What he played. Empty of moves when nothing in the throw could be played.

    public Player Player { get; init; }
      /// Whose turn it was.

    public Position Position { get; init; }
      /// The position his turn left behind.

### namespace HoyleBackgammon.Requests

#### public sealed class AgreedBackgammonMultipleRequest : IEntryRequest  [generated]
/// A request to resolve The multiple the players agreed a backgammon pays (`agreed-backgammon-multiple`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.

    public AgreedBackgammonMultipleRequest()
      /// A request for `agreed-backgammon-multiple` asserting nothing.

    public AgreedBackgammonMultipleRequest(RuleRequest assertions)
      /// A request for `agreed-backgammon-multiple` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static AgreedBackgammonMultipleRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

    public static AgreedBackgammonMultipleRequest Asserting(object value)
      /// A request asserting `value` for this assertion entry, which is what it resolves to.
      /// Parameter value: The caller's value.
      /// Returns: The request.

#### public sealed class BearingOffDoubletsRequest : IEntryRequest  [generated]
/// A request to resolve Doublets bear off or move, or both (`bearing-off-doublets`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `bearing-off-doublets`'s rule reads.

    public BearingOffDoubletsRequest()
      /// A request for `bearing-off-doublets` asserting nothing.

    public BearingOffDoubletsRequest(RuleRequest assertions)
      /// A request for `bearing-off-doublets` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public DiceThrow? Thrown { get; init; }
      /// The throw of two dice.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static BearingOffDoubletsRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class BearingOffEligibleRequest : IEntryRequest  [generated]
/// A request to resolve Bearing off begins when all men are home (`bearing-off-eligible`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `bearing-off-eligible`'s rule reads.

    public BearingOffEligibleRequest()
      /// A request for `bearing-off-eligible` asserting nothing.

    public BearingOffEligibleRequest(RuleRequest assertions)
      /// A request for `bearing-off-eligible` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static BearingOffEligibleRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class BearingOffHighestRequest : IEntryRequest  [generated]
/// A request to resolve An unusable number bears off from the highest occupied point (`bearing-off-highest`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `bearing-off-highest`'s rule reads.

    public BearingOffHighestRequest()
      /// A request for `bearing-off-highest` asserting nothing.

    public BearingOffHighestRequest(RuleRequest assertions)
      /// A request for `bearing-off-highest` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public int? Die { get; init; }
      /// The number of one die.

    public static BearingOffHighestRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class BearingOffMoveOrRemoveRequest : IEntryRequest  [generated]
/// A request to resolve Each throw may move within the table or remove a man (`bearing-off-move-or-remove`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `bearing-off-move-or-remove`'s rule reads.

    public BearingOffMoveOrRemoveRequest()
      /// A request for `bearing-off-move-or-remove` asserting nothing.

    public BearingOffMoveOrRemoveRequest(RuleRequest assertions)
      /// A request for `bearing-off-move-or-remove` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public int? Die { get; init; }
      /// The number of one die.

    public static BearingOffMoveOrRemoveRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class BlotHitRequest : IEntryRequest  [generated]
/// A request to resolve A single man is a blot and may be hit (`blot-hit`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `blot-hit`'s rule reads.

    public BlotHitRequest()
      /// A request for `blot-hit` asserting nothing.

    public BlotHitRequest(RuleRequest assertions)
      /// A request for `blot-hit` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public int? From { get; init; }
      /// The pip the man moves from.

    public int? To { get; init; }
      /// The pip the man moves to.

    public static BlotHitRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class BoardTablesRequest : IEntryRequest  [generated]
/// A request to resolve The board is two tables, inner and outer (`board-tables`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `board-tables`'s rule reads.

    public BoardTablesRequest()
      /// A request for `board-tables` asserting nothing.

    public BoardTablesRequest(RuleRequest assertions)
      /// A request for `board-tables` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public int? Pip { get; init; }
      /// A pip, in the numbering of the player whose point it is (`HoyleBackgammon.Geometry`).

    public static BoardTablesRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class CallingTheThrowRequest : IEntryRequest  [generated]
/// A request to resolve The thrower calls his throw, the higher number first (`calling-the-throw`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.

    public CallingTheThrowRequest()
      /// A request for `calling-the-throw` asserting nothing.

    public CallingTheThrowRequest(RuleRequest assertions)
      /// A request for `calling-the-throw` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static CallingTheThrowRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class DieFacesRequest : IEntryRequest  [generated]
/// A request to resolve The faces a die bears, and the throws a pair of them can show (`die-faces`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `die-faces`'s rule reads.

    public DieFacesRequest()
      /// A request for `die-faces` asserting nothing.

    public DieFacesRequest(RuleRequest assertions)
      /// A request for `die-faces` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public IRandomSource? Source { get; init; }
      /// The generator the dice draw from.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static DieFacesRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class DirectionOfTravelRequest : IEntryRequest  [generated]
/// A request to resolve The twenty-four points are one course with two ends (`direction-of-travel`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `direction-of-travel`'s rule reads.

    public DirectionOfTravelRequest()
      /// A request for `direction-of-travel` asserting nothing.

    public DirectionOfTravelRequest(RuleRequest assertions)
      /// A request for `direction-of-travel` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public int? Pip { get; init; }
      /// A pip, in the numbering of the player whose point it is (`HoyleBackgammon.Geometry`).

    public static DirectionOfTravelRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class DoubletsRequest : IEntryRequest  [generated]
/// A request to resolve Doublets are played twice over (`doublets`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `doublets`'s rule reads.

    public DoubletsRequest()
      /// A request for `doublets` asserting nothing.

    public DoubletsRequest(RuleRequest assertions)
      /// A request for `doublets` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public DiceThrow? Thrown { get; init; }
      /// The throw of two dice.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static DoubletsRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class DoublingCubeRequest : IEntryRequest  [generated]
/// A request to resolve Doubling the stake during play (`doubling-cube`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.

    public DoublingCubeRequest()
      /// A request for `doubling-cube` asserting nothing.

    public DoublingCubeRequest(RuleRequest assertions)
      /// A request for `doubling-cube` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static DoublingCubeRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class EnterFromBarRequest : IEntryRequest  [generated]
/// A request to resolve A man on the bar re-enters before any other man moves (`enter-from-bar`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `enter-from-bar`'s rule reads.

    public EnterFromBarRequest()
      /// A request for `enter-from-bar` asserting nothing.

    public EnterFromBarRequest(RuleRequest assertions)
      /// A request for `enter-from-bar` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static EnterFromBarRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class FullTableSuspensionRequest : IEntryRequest  [generated]
/// A request to resolve Play is wholly suspended against a full home table (`full-table-suspension`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `full-table-suspension`'s rule reads.

    public FullTableSuspensionRequest()
      /// A request for `full-table-suspension` asserting nothing.

    public FullTableSuspensionRequest(RuleRequest assertions)
      /// A request for `full-table-suspension` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static FullTableSuspensionRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class GameValueRequest : IEntryRequest  [generated]
/// A request to resolve A win is a hit, a gammon, or a backgammon (`game-value`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `game-value`'s rule reads.

    public GameValueRequest()
      /// A request for `game-value` asserting nothing.

    public GameValueRequest(RuleRequest assertions)
      /// A request for `game-value` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Winner { get; init; }
      /// The player who has won.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static GameValueRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class HitPaysSingleStakeRequest : IEntryRequest  [generated]
/// A request to resolve What a hit pays (`hit-pays-single-stake`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.

    public HitPaysSingleStakeRequest()
      /// A request for `hit-pays-single-stake` asserting nothing.

    public HitPaysSingleStakeRequest(RuleRequest assertions)
      /// A request for `hit-pays-single-stake` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static HitPaysSingleStakeRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class InnerTableHandednessRequest : IEntryRequest  [generated]
/// A request to resolve Which physical compartment of the board is the inner table (`inner-table-handedness`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.

    public InnerTableHandednessRequest()
      /// A request for `inner-table-handedness` asserting nothing.

    public InnerTableHandednessRequest(RuleRequest assertions)
      /// A request for `inner-table-handedness` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static InnerTableHandednessRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class LegalDestinationRequest : IEntryRequest  [generated]
/// A request to resolve A man may be played only to a permitted point (`legal-destination`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `legal-destination`'s rule reads.

    public LegalDestinationRequest()
      /// A request for `legal-destination` asserting nothing.

    public LegalDestinationRequest(RuleRequest assertions)
      /// A request for `legal-destination` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public int? Pip { get; init; }
      /// A pip, in the numbering of the player whose point it is (`HoyleBackgammon.Geometry`).

    public static LegalDestinationRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class MadePointRequest : IEntryRequest  [generated]
/// A request to resolve Two men make a point (`made-point`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `made-point`'s rule reads.

    public MadePointRequest()
      /// A request for `made-point` asserting nothing.

    public MadePointRequest(RuleRequest assertions)
      /// A request for `made-point` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public int? Pip { get; init; }
      /// A pip, in the numbering of the player whose point it is (`HoyleBackgammon.Geometry`).

    public static MadePointRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class MenCountRequest : IEntryRequest  [generated]
/// A request to resolve Thirty men, fifteen to a side (`men-count`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.

    public MenCountRequest()
      /// A request for `men-count` asserting nothing.

    public MenCountRequest(RuleRequest assertions)
      /// A request for `men-count` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static MenCountRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class MoveByPipRequest : IEntryRequest  [generated]
/// A request to resolve Each die moves one man that many points (`move-by-pip`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `move-by-pip`'s rule reads.

    public MoveByPipRequest()
      /// A request for `move-by-pip` asserting nothing.

    public MoveByPipRequest(RuleRequest assertions)
      /// A request for `move-by-pip` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public int? Die { get; init; }
      /// The number of one die.

    public static MoveByPipRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class MustPlayWholeThrowRequest : IEntryRequest  [generated]
/// A request to resolve The whole throw must be played if it can be (`must-play-whole-throw`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `must-play-whole-throw`'s rule reads.

    public MustPlayWholeThrowRequest()
      /// A request for `must-play-whole-throw` asserting nothing.

    public MustPlayWholeThrowRequest(RuleRequest assertions)
      /// A request for `must-play-whole-throw` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public DiceThrow? Thrown { get; init; }
      /// The throw of two dice.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static MustPlayWholeThrowRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class NextGameOpeningRequest : IEntryRequest  [generated]
/// A request to resolve Who throws first in the following game (`next-game-opening`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `next-game-opening`'s rule reads.

    public NextGameOpeningRequest()
      /// A request for `next-game-opening` asserting nothing.

    public NextGameOpeningRequest(RuleRequest assertions)
      /// A request for `next-game-opening` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public GameValue? Value { get; init; }
      /// The kind of win that ended the game.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static NextGameOpeningRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class OpeningRollRequest : IEntryRequest  [generated]
/// A request to resolve Deciding who begins (`opening-roll`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `opening-roll`'s rule reads.

    public OpeningRollRequest()
      /// A request for `opening-roll` asserting nothing.

    public OpeningRollRequest(RuleRequest assertions)
      /// A request for `opening-roll` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public IRandomSource? Source { get; init; }
      /// The generator the dice draw from.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static OpeningRollRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class OpeningThrowerOptionRequest : IEntryRequest  [generated]
/// A request to resolve The opening thrower may keep the throw or throw again (`opening-thrower-option`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `opening-thrower-option`'s rule reads.

    public OpeningThrowerOptionRequest()
      /// A request for `opening-thrower-option` asserting nothing.

    public OpeningThrowerOptionRequest(RuleRequest assertions)
      /// A request for `opening-thrower-option` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public IRandomSource? Source { get; init; }
      /// The generator the dice draw from.

    public OpeningRoll? Roll { get; init; }
      /// The roll for the right to begin.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public bool Adopt { get; init; }
      /// Whether the opener adopts the points shown by the two dice rather than throwing again.

    public static OpeningThrowerOptionRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class PlayerCountRequest : IEntryRequest  [generated]
/// A request to resolve Backgammon is played by two persons (`player-count`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.

    public PlayerCountRequest()
      /// A request for `player-count` asserting nothing.

    public PlayerCountRequest(RuleRequest assertions)
      /// A request for `player-count` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static PlayerCountRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class PointDesignationsRequest : IEntryRequest  [generated]
/// A request to resolve How the twenty-four points are named and numbered (`point-designations`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `point-designations`'s rule reads.

    public PointDesignationsRequest()
      /// A request for `point-designations` asserting nothing.

    public PointDesignationsRequest(RuleRequest assertions)
      /// A request for `point-designations` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public int? Pip { get; init; }
      /// A pip, in the numbering of the player whose point it is (`HoyleBackgammon.Geometry`).

    public static PointDesignationsRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class RubberScoringRequest : IEntryRequest  [generated]
/// A request to resolve How games count towards a rubber (`rubber-scoring`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `rubber-scoring`'s rule reads.

    public RubberScoringRequest()
      /// A request for `rubber-scoring` asserting nothing.

    public RubberScoringRequest(RuleRequest assertions)
      /// A request for `rubber-scoring` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public IReadOnlyList<GameResult>? Games { get; init; }
      /// The rubber's games, first first, each with the owner's rulings its value relied on (`HoyleBackgammon.GameResult.Rulings`).

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static RubberScoringRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class StakeMultiplierRequest : IEntryRequest  [generated]
/// A request to resolve What a gammon and a backgammon pay (`stake-multiplier`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `stake-multiplier`'s rule reads.

    public StakeMultiplierRequest()
      /// A request for `stake-multiplier` asserting nothing.

    public StakeMultiplierRequest(RuleRequest assertions)
      /// A request for `stake-multiplier` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public GameValue? Value { get; init; }
      /// The kind of win.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static StakeMultiplierRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class StartingPositionRequest : IEntryRequest  [generated]
/// A request to resolve The starting arrangement of the men (`starting-position`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.

    public StartingPositionRequest()
      /// A request for `starting-position` asserting nothing.

    public StartingPositionRequest(RuleRequest assertions)
      /// A request for `starting-position` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static StartingPositionRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class StrategyAdviceRequest : IEntryRequest  [generated]
/// A request to resolve The advisory principles of play (`strategy-advice`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.

    public StrategyAdviceRequest()
      /// A request for `strategy-advice` asserting nothing.

    public StrategyAdviceRequest(RuleRequest assertions)
      /// A request for `strategy-advice` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static StrategyAdviceRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class ThrowTwoDiceRequest : IEntryRequest  [generated]
/// A request to resolve All subsequent throws use both dice (`throw-two-dice`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `throw-two-dice`'s rule reads.

    public ThrowTwoDiceRequest()
      /// A request for `throw-two-dice` asserting nothing.

    public ThrowTwoDiceRequest(RuleRequest assertions)
      /// A request for `throw-two-dice` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public IRandomSource? Source { get; init; }
      /// The generator the dice draw from.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static ThrowTwoDiceRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

#### public sealed class WinConditionRequest : IEntryRequest  [generated]
/// A request to resolve First to remove all men wins (`win-condition`).
/// Remarks: Partial: an engine declares the entry's inputs as `init` properties in a file of its own, and a caller sets them in an object initializer; the handler receives this very object through `EntryPoints`.
/// The inputs `win-condition`'s rule reads.

    public WinConditionRequest()
      /// A request for `win-condition` asserting nothing.

    public WinConditionRequest(RuleRequest assertions)
      /// A request for `win-condition` carrying `assertions`.
      /// Parameter assertions: What the caller asserts.

    public AssertedPosition? Position { get; init; }
      /// The position the rule is asked about, and who asserted it. The answer carries the assertion back (`HoyleBackgammon.AssertedAnswer`1`), as `HoyleBackgammon.GameRecord.Start` does for a game.

    public Player? Player { get; init; }
      /// The player the rule is asked about.

    public RuleRequest Assertions { get; }
      /// (documentation inherited)

    public static WinConditionRequest Empty { get; }
      /// A request asserting nothing.

    public string EntryId { get; }
      /// (documentation inherited)

## Assembly Tabletop.Dice

### namespace Tabletop.Dice

#### public readonly record struct DicePair
/// A pair of dice thrown together.
/// Remarks: The two dice are thrown in a fixed order — `Tabletop.Dice.DicePair.First` then `Tabletop.Dice.DicePair.Second` — so that the number and order of draws taken from an `RulesKernel.Randomness.IRandomSource` is a property of this type rather than of a caller's loop. Replay depends on it.

    public DicePair(Die first, Die second)
      /// A pair of the two given dice.

    public Die First { get; }
      /// The die thrown first.

    public Die Second { get; }
      /// The die thrown second.

    public static DicePair OfSixes { get; }
      /// A pair of six-faced dice.

    public DiceThrow Throw(IRandomSource source)
      /// Throws both dice, `Tabletop.Dice.DicePair.First` before `Tabletop.Dice.DicePair.Second`.

    public override string ToString()
      /// (documentation inherited)

#### public readonly record struct DiceThrow
/// The outcome of throwing two dice: the two faces, in the order they were thrown.
/// Remarks: The throw order is retained rather than normalised because it is the only part of the outcome that a replay can check against the generator. Rulesets that name a throw high-first (Hoyle's "six deuce") can read `Tabletop.Dice.DiceThrow.Higher` and `Tabletop.Dice.DiceThrow.Lower`.
/// This type says a throw of equal faces is `Tabletop.Dice.DiceThrow.IsDoublets` and stops there. What doublets are worth is a ruleset's business: Hoyle plays them twice over, other games do something else or nothing at all.

    public DiceThrow(int first, int second)
      /// A throw of the two given faces, in throw order.

    public bool IsDoublets { get; }
      /// True when both dice show the same face.

    public int First { get; }
      /// The face of the first die thrown.

    public int Higher { get; }
      /// The greater of the two faces.

    public int Lower { get; }
      /// The lesser of the two faces.

    public int Second { get; }
      /// The face of the second die thrown.

    public override string ToString()
      /// (documentation inherited)

#### public readonly record struct Die
/// A die of `Tabletop.Dice.Die.Faces` faces, numbered 1 through `Tabletop.Dice.Die.Faces`.
/// Remarks: The kernel ships no dice on purpose (RulesKernel docs/decisions/0002): randomness is an optional package and dice are subject-matter vocabulary. What it ships is `RulesKernel.Randomness.UniformInt.Below(RulesKernel.Randomness.IRandomSource,System.UInt32)`, which returns a value in `[0, bound)`. The face numbering here is the documented `f - 1` convention: face `f` of a d(n) is the raw value `f - 1`.

    public Die(int faces)
      /// A die of `faces` faces.
      /// Throws System.ArgumentOutOfRangeException: If `faces` is below one.

    public bool IsValid { get; }
      /// True unless this is `default(Die)`, which bypasses the constructor.

    public int Faces { get; }
      /// The number of faces. Always at least one.

    public static Die D6 { get; }
      /// The six-faced die.

    public int Throw(IRandomSource source)
      /// Throws the die, consuming exactly one bounded draw from `source` unless `RulesKernel.Randomness.UniformInt.Below(RulesKernel.Randomness.IRandomSource,System.UInt32)` rejects a raw value.
      /// Returns: A face in `[1, Faces]`.

    public override string ToString()
      /// (documentation inherited)
