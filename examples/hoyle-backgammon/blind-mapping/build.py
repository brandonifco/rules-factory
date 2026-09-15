#!/usr/bin/env python3
"""Build and self-check the blind corpus map for hoyle-1909 BACKGAMMON pp. 271-280."""
import json, re, sys, collections

BUNDLE = "/tmp/claude-1000/blind-hoyle-95/bundle"
SRC = "hoyle-1909"
C = "BACKGAMMON"

def loc(section, page):
    return {"sourceId": SRC, "citation": f"{C} / {section} / p. {page}"}

INTRO = "(introduction)"
PLAY = "PLAYING"
BEAR = "BEARING OFF THE MEN"
HINTS = "HINTS FOR PLAY"

def unres(q, conflict=None):
    a = {"question": q}
    if conflict:
        a["conflict"] = conflict
    a["fate"] = "unresolved"
    a["unresolvedReason"] = "RequiresInterpretation"
    return a

E = []
def add(**kw):
    d = {"id": kw.pop("id"), "name": kw.pop("name")}
    if "derivedFrom" not in kw:
        d["locator"] = loc(kw.pop("section"), kw.pop("page"))
    for k in ["kind", "scope", "clarity", "ambiguity", "dependsOn", "enabledBy", "suspendedBy",
              "beyondAdapter", "absentFrom", "derivedFrom", "crossReferences", "evidence"]:
        if k in kw:
            d[k] = kw.pop(k)
    d["status"] = kw.pop("status", "mapped")
    d["note"] = kw.pop("note")
    assert not kw, kw
    E.append(d)

# ---------------- page 271: apparatus ----------------
add(id="players-and-men", name="Two players, fifteen men each", section=INTRO, page=271,
    kind="value", scope="in", clarity="clear",
    evidence='Backgammon is played by two persons, on a special "board" with thirty "men," fifteen white and fifteen black (or red), similar to those used for the game of Draughts.',
    note="Two players; thirty men, fifteen per side, distinguished by colour (white against black or red). The colour choice and the likeness to draughtsmen have no rules consequence. A test must show each side starts with exactly fifteen men.")

add(id="board-two-compartments", name="The board: two equal compartments", section=INTRO, page=271,
    kind="value", scope="in", clarity="clear",
    crossReferences=[{"cites": "(see Fig. 1)", "resolvedBy": "fig1-orientation"}],
    evidence='The board (see Fig. 1) is square, usually of wood, lined with leather, and is divided into two equal compartments, each with a raised wall or border.',
    note="The rule-bearing part is that the board is divided into two equal compartments (named 'tables' in board-tables). Material, shape and border are physical description with no rules consequence; they are declined in board-physical-construction, not here.")

add(id="board-physical-construction", name="Physical construction of the board", section=INTRO, page=271,
    kind="value", scope="out", clarity="clear", status="declined",
    evidence='It is usually made in two portions, {272} hinged so as to fold together, and bearing on their outward surfaces the necessary squares for draughts or chess, so that the one board may answer both purposes.',
    note="Declined: manufacture of the board (hinged, doubling as a draughts or chess board) describes the object, not play. Straddles the {272} marker; cited on p. 271 where it starts.")

# ---------------- page 272: tables, points, dice, set-up ----------------
add(id="board-tables", name="Tables: outer and inner (home)", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear", dependsOn=["board-two-compartments"],
    evidence='The board is so placed in use that the two compartments, known as "tables," shall lie longitudinally between the players. One of these is known as the "outer," the other as the "inner" or "home" table.',
    note="Vocabulary: a 'table' is one compartment; one is the outer, the other the inner or home table. The compartments lie between the players, so each is shared by both sides; see player-inner-outer-tables for 'his' table.")

add(id="inner-table-by-arrangement", name="Which table is inner is fixed by the starting arrangement", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear", dependsOn=["board-tables", "starting-arrangement"],
    evidence='Which of the two is for the time being the inner and which the outer table is governed by the arrangement of the men at starting.',
    note="The inner/outer labelling is not a fixed physical property of the board; it follows the set-up. A test must show the labelling is derived from starting-arrangement rather than fixed to a side.")

add(id="fig1-orientation", name="Left/right orientation of inner and outer tables as in Fig. 1", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear", status="declined",
    beyondAdapter={"adapter": "plain-text", "modality": "illustration"},
    crossReferences=[{"cites": "as in Fig. 1", "unmapped": "Fig. 1 is an illustration; the plain-text edition has only the placeholder '[Illustration: FIG. 1.]', so whose right hand is meant cannot be read."}],
    evidence='With the men placed as in Fig. 1, the right hand is the inner or home table, and the left hand consequently the outer table.',
    note="Which physical side (right hand, from whose seat) is the inner table is fixed only by the figure. The logical geometry an engine needs is recoverable from starting-arrangement and the point names without it, so nothing depends on this entry.")

add(id="player-inner-outer-tables", name="A player's own inner and outer tables", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear", dependsOn=["board-tables"],
    evidence='The portions of the two latter nearest to each player are known as _his_ inner and outer tables respectively.',
    note="Each compartment splits into the half nearest each player, giving four six-point tables: White's inner, White's outer, Black's inner, Black's outer. The text then uses 'table' for both the compartment (twelve points) and a player's half of it (six points); later rules (home table full, bearing off) mean the player's half. Mapper's reading, from context.")

add(id="points-per-table", name="Twelve points per table", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear", dependsOn=["board-tables"],
    evidence='Each table is marked with twelve "points," six at either end.',
    note="Each compartment has twelve points, six at each player's end, so the board has 24 points and each player's inner and outer table has six. A test must show 24 points, six per player table.")

add(id="point-colours", name="Alternating colours of the points", section=INTRO, page=272,
    kind="value", scope="out", clarity="clear", status="declined",
    evidence='They are alternately of black and white, black and red, or other distinctive colours.',
    note="Declined: the colouring of the points is visual only and has no rules consequence.")

add(id="inner-point-names", name="Names of the points in the inner table, and the bar", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear", dependsOn=["player-inner-outer-tables", "points-per-table"],
    evidence='The two points in the inner table farthest from the dividing partition or "bar" are known as the "ace" points, and those next in order as the two or "deuce" points, followed in succession by the three or "trois" points, the four or "quatre" points, the five or "cinque" points, and finally the "six"[65] points, next the bar.',
    note="Vocabulary: the dividing partition is the 'bar'. In each inner table, counting from the point farthest from the bar: ace (1), deuce (2), trois (3), quatre (4), cinque (5), six (6, next the bar). Footnote [65] gives pronunciations only (not a rule). A test must cover all six names.")

add(id="outer-point-names", name="Names of the points in the outer table", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear", dependsOn=["inner-point-names"],
    evidence='The points in the outer tables are designated in like manner, but starting in this case from the dividing partition.',
    note="Outer-table points are named ace to six counting from the bar outward, so the outer ace point is next to the bar and the outer six point is at the far edge. Needed to read starting-arrangement (e.g. 'deuce point in White's outer table').")

add(id="bar-point-name", name="The bar point", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear", dependsOn=["outer-point-names"],
    evidence='The ace point in the outer table is more commonly known as the "bar" point.',
    note="Vocabulary: 'bar point' = ace point of the outer table. Distinct from 'the bar' itself (the partition, where hit men are placed). Used by the opening-move hints.")

add(id="dice", name="A pair of dice", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear",
    evidence='A pair of dice (or sometimes a pair for each player) and a couple of dice-boxes complete the apparatus of the game.',
    note="Play uses two dice. Whether both players share a pair or each has one, and the dice-boxes, have no effect on outcomes. The number of faces is not stated here; see die-faces-absent and possible-throws.")

add(id="die-faces-absent", name="Number and numbering of a die's faces", section=INTRO, page=272,
    kind="value", scope="out", clarity="clear", status="declined",
    absentFrom={"searched": ["pips", "spots", "six-sided", "six faces"]},
    evidence='A pair of dice (or sometimes a pair for each player) and a couple of dice-boxes complete the apparatus of the game.',
    note="The chapter never describes a die (faces, spots). This quotes the apparatus sentence where it would be. The range of throws is nonetheless fixed by the enumeration of all possible throws (possible-throws); this entry records only that no sentence describes the die itself. Note 'faces' and 'sides' could not be searched: they occur as substrings ('surfaces', 'both sides').")

add(id="starting-arrangement", name="Arrangement of the men at starting", section=INTRO, page=272,
    kind="value", scope="in", clarity="clear",
    dependsOn=["players-and-men", "inner-point-names", "outer-point-names"],
    crossReferences=[{"cites": "as shown in {273} Fig. 1", "unmapped": "Fig. 1 is an illustration the plain-text adapter cannot read; the arrangement is restated in full in the prose of this same span, which is what the entry maps."}],
    evidence="The men are arranged at starting as shown in {273} Fig. 1--viz., two of White's men are placed on the ace point in Black's inner table, five are placed on the six point in Black's outer table, three on the deuce point in White's outer table, and five on the six point in White's inner table. Black's men are placed in like manner on the points immediately facing these.",
    note="White: 2 on ace point of Black's inner table, 5 on six point of Black's outer table, 3 on deuce point of White's outer table, 5 on six point of White's inner table (15 in all). Black mirrors this on the facing points. The test must check the whole arrangement for both colours and that it totals fifteen each. Straddles {273}; cited on p. 272.")

# ---------------- page 273: PLAYING ----------------
add(id="first-player", name="Throwing for first move", section=PLAY, page=273,
    kind="operation", scope="in", clarity="clear", dependsOn=["dice"],
    evidence='The game is commenced by each player throwing on the centre of the board a single die, the higher throw of the two giving the right to begin. In the event of a tie, the players throw again.',
    note="Each player throws one die; the higher begins; a tie means both throw again (repeat until unequal). Where on the board the die lands has no consequence. A test must show higher wins and a tie re-throws.")

add(id="subsequent-throws-two-dice", name="All later throws use both dice", section=PLAY, page=273,
    kind="value", scope="in", clarity="clear", dependsOn=["dice", "first-player"],
    evidence='All subsequent throws are with both dice.',
    note="After the single-die throw for first move, every throw is made with both dice. Also governs a re-throw under opening-throw-choice.")

add(id="opening-throw-choice", name="Winner of the first throw adopts it or throws again", section=PLAY, page=273,
    kind="operation", scope="in", clarity="clear",
    dependsOn=["first-player", "subsequent-throws-two-dice"], enabledBy=["first-player"],
    evidence='The thrower of the higher number may either adopt the points shown by the two dice as his own throw, or throw again.',
    note="The player who won the throw for first move chooses: use the two single-die numbers just thrown (his and his opponent's) as his first throw, or make a fresh throw (with both dice, per subsequent-throws-two-dice). Kind operation: a choice between two stated moves, not an open term. A test must show both branches.")

add(id="throw-naming", name="Calling a throw, higher number first", section=PLAY, page=273,
    kind="value", scope="in", clarity="clear", dependsOn=["inner-point-names"],
    evidence='After throwing, he calls the number of the throw, the higher number first, as "six deuce," "cinque trois," "quatre ace," or as the case may be, and then proceeds to make his move in accordance with it.',
    note="Vocabulary: a throw is named by its two numbers using the point names, higher first ('six deuce'). The spoken call itself has no effect on play; the naming convention is what the hints and examples use.")

add(id="direction-of-movement", name="Direction in which a player's men move", section=PLAY, page=273,
    kind="value", scope="in", clarity="clear", dependsOn=["player-inner-outer-tables", "inner-point-names"],
    evidence="The movement of the men of each player is from the ace point in his opponent's home table towards the like point in his own,",
    note="Each side moves from the ace point of the opponent's home table round to the ace point of his own home table, so the two sides move in opposite directions. A test must show both colours' directions.")

add(id="object-of-game", name="Object: bring all men home, then bear them off", section=PLAY, page=273,
    kind="value", scope="in", clarity="clear", dependsOn=["direction-of-movement"],
    crossReferences=[{"cites": "according to certain rules to be hereafter stated", "resolvedBy": "bearing-off-stage"}],
    evidence="the object of the game being first to get all the player's men into his own inner table, and then to play them out of it again, according to certain rules to be hereafter stated.",
    note="Statement of the object; the operative rules are bearing-off-stage, bear-off-by-number and win-condition. The preceding clause ('for many purposes it suffices if he can play them into his own table') is commentary and is dropped as a rule.")

add(id="die-movement", name="Each die moves one man forward its number of points", section=PLAY, page=273,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("The example plays the six and 'then' the three. The text does not say whether the player may choose which die's number to play first, which matters when only one order is legal."),
    dependsOn=["direction-of-movement", "subsequent-throws-two-dice", "landing-restriction"],
    suspendedBy=["bar-suspends-other-men", "closed-home-table"],
    evidence='The number uppermost on each die entitles the player to move one man forward a corresponding number of points. Thus if he threw "six trois," he is entitled to move one man six points onward, and then the same or another man {274} three points onward.',
    note="Each die's number is one move of one man that many points forward; the two numbers may go to one man (in two stages) or to two men. Each stage is a separate move, so each landing is subject to landing-restriction. Suspended while the player has a man on the bar (bar-suspends-other-men). Straddles {274}; cited on p. 273.")

# ---------------- page 274 ----------------
add(id="doublets", name="Doublets are played twice over", section=PLAY, page=274,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("'Play the throw twice over' reads as four moves of the die's number; the examples then speak of moving 'one or more men forward to an aggregate extent' of four, eight or twelve points. Does 'aggregate extent' allow any split of the total (e.g. 3 and 5 for deuces), or only four moves of the die's number?"),
    dependsOn=["die-movement"], suspendedBy=["bar-suspends-other-men", "closed-home-table"],
    evidence='In the event of his throwing the same points with both dice (known as "doublets"), he is entitled to play the throw twice over. Suppose, for example, that he throws two aces; he may move one or more men forward to an aggregate extent of four points. If he throw double deuces, he may move to an aggregate extent of eight points; if double threes, twelve points, and so on.',
    note="Vocabulary: 'doublets' = both dice showing the same number. The throw is played twice over. A test must show double aces = 4, double deuces = 8, double threes = 12, and the rest in the same pattern.")

add(id="landing-restriction", name="Points a man may be played to", section=PLAY, page=274,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("This general rule lets a man be played to a point held by his own men. The entry rule (bar-entry) lets a man on the bar enter only on 'a vacant point or blot'. Can a man enter on a point already held by his own men?", conflict="entry-onto-own-point"),
    evidence='The right to move is subject to a certain qualification--viz., that a man can only be played to a point which is either vacant or occupied by one or more men of the player, or by one man only of the adversary.',
    note="Legal destination: vacant, held by any number of the mover's own men, or held by exactly one enemy man. Two or more enemy men block the point. Nothing restricts intermediate points passed over. A test must cover all four cases (vacant, own, one enemy, two or more enemy).")

add(id="make-point", name="Making a point", section=PLAY, page=274,
    kind="value", scope="in", clarity="clear", dependsOn=["landing-restriction"],
    evidence='A player getting two men on a given point is said to "make" such point,',
    note="Vocabulary: two men of one side on a point is a 'made' point. The rest of the sentence (it secures the men and hinders the enemy, 'it is always an object to do this') is advice and a consequence of landing-restriction; dropped as a rule.")

add(id="blot", name="Blot", section=PLAY, page=274,
    kind="value", scope="in", clarity="clear",
    evidence='A single man on a given point is known as a "blot," and not only does not prevent the enemy playing to that point,',
    note="Vocabulary: a single man on a point is a 'blot'; the enemy may still play to it, per landing-restriction.")

add(id="hit-blot", name="Hitting a blot: taken up to the bar", section=PLAY, page=274,
    kind="operation", scope="in", clarity="clear", dependsOn=["blot", "landing-restriction"],
    evidence='but in the event of its being "hit"--_i.e._, reached by an adverse throw, it is "taken up" (placed on the bar between the two tables), and, however far advanced it may have been, has to begin its journey anew from the inner table of the adversary.',
    note="An enemy man played onto a blot 'hits' it. The blot is taken up, placed on the bar, and must restart from the adversary's inner table. Mapper's reading: 'reached' means a man played to that point, including an intermediate stage of die-movement. 'Hit' here is a different sense from game-value-hit.")

add(id="bar-entry", name="Entering a man from the bar", section=PLAY, page=274,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("This rule lets a man on the bar enter only on 'a vacant point or blot' in the adversary's table. landing-restriction lets a man be played to a point held by his own men. Can a man enter on a point already held by his own men?", conflict="entry-onto-own-point"),
    dependsOn=["hit-blot", "direction-of-movement", "inner-point-names"],
    enabledBy=["hit-blot"], suspendedBy=["closed-home-table"],
    evidence='Nor can such man again start on its journey until its owner is fortunate enough to make a throw corresponding with a vacant point or blot in such table.',
    note="A man on the bar re-enters the adversary's inner table on the point corresponding to a die thrown (mapper's reading: die n to point n counted from the ace, following direction-of-movement), if that point is vacant or a blot. Entering on a blot presumably hits it, per hit-blot. A test must show entry on vacant, on blot, and refusal on a point of two or more enemy men.")

add(id="bar-suspends-other-men", name="Other men may not move while a man is on the bar", section=PLAY, page=274,
    kind="operation", scope="in", clarity="clear", dependsOn=["bar-entry"], enabledBy=["hit-blot"],
    evidence='Until he does this, the play of his other men is suspended.',
    note="Gate: while a player has a man on the bar, none of his other men may move. It closes die-movement, doublets and the bearing-off moves (named in their suspendedBy). A test must show a legal-looking move of another man refused while a man is up.")

add(id="closed-home-table", name="Closed home table: play altogether suspended", section=PLAY, page=274,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("The sentence follows the bar-entry rule and reads as applying to a player with a man on the bar. Its own words ('If the adverse player's home table is completely full') set no such condition. Is play suspended whenever the adversary's home table is closed, or only while the player has a man up?"),
    dependsOn=["bar-entry", "make-point"], enabledBy=["hit-blot"],
    evidence="If the adverse player's home table is completely full--_i.e._, each point occupied by two or more men, his play is altogether suspended, the adversary continuing to throw and move until the course of play again throws open one or more points in his table.",
    note="'Completely full' is defined: all six points of the adversary's home table held by two or more men. The player then does not play at all, and the adversary throws and moves repeatedly until a point opens. A test must show consecutive turns for the adversary and resumption when a point opens. The {275} marker falls just after the span.")

add(id="throw-alternation", name="Players throw in turn", section=PLAY, page=274,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("No sentence states that the players throw and move alternately. It is only presupposed, by the closed-table rule's 'the adversary continuing to throw and move'. Is alternation the rule, and what is the turn unit (one throw and its move)?"),
    dependsOn=["subsequent-throws-two-dice"], suspendedBy=["closed-home-table"],
    evidence='the adversary continuing to throw and move until the course of play again throws open one or more points in his table.',
    note="Recorded so that turn order is not filled in from outside knowledge. Until Phase 4, the only textual support is this presupposition.")

# ---------------- page 275 ----------------
add(id="unplayable-part-lost", name="Unplayable part of a throw is lost", section=PLAY, page=275,
    kind="operation", scope="in", clarity="clear", dependsOn=["die-movement", "landing-restriction"],
    evidence='Any part of a throw which cannot be played is lost to the thrower,',
    note="Where a die's number (or part of doublets) has no legal move, it is forfeited; it is not carried over. A test must show a partially and a wholly blocked throw.")

add(id="must-play-whole-throw", name="Compulsion to play the whole throw", section=PLAY, page=275,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("When either number could be played but not both, the text does not say which the player must play. Whether he must choose the sequence that uses the most of the throw follows from 'if it is possible', but the case where the choice is between the two numbers is not settled."),
    dependsOn=["die-movement", "doublets", "unplayable-part-lost"],
    evidence='but every player is compelled to play the whole of his throw if it is possible to do so.',
    note="If any sequence of legal moves uses the whole throw, the player must use one. A test must show a move that would leave part unplayed is refused when a full-use alternative exists.")

add(id="bearing-off-stage", name="Bearing off begins when all men are home", section=BEAR, page=275,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("The stage starts once all a player's men are in his home table. The text does not say what happens if one of his men is then hit and taken up: does bearing off stop until every man is home again?"),
    dependsOn=["object-of-game", "player-inner-outer-tables"],
    evidence='When either player has succeeded in getting all his men into his home table, he proceeds to "bear them off"--_i.e._, to remove them from the board.',
    note="Vocabulary: 'bear off' = remove men from the board. Gate: this entry enables the bearing-off moves. A test must show no man can be borne off while any man is outside the home table.")

add(id="bear-off-by-number", name="In bearing off, a throw moves within the table or removes from the corresponding point", section=BEAR, page=275,
    kind="operation", scope="in", clarity="clear",
    dependsOn=["bearing-off-stage", "die-movement", "inner-point-names"],
    enabledBy=["bearing-off-stage"], suspendedBy=["bar-suspends-other-men"],
    evidence='When the game has reached this stage, each throw entitles the player either to move forward a man or men (to the extent indicated by the throw) within the limits of his own table, or to remove men from the corresponding points.',
    note="Each number either moves a man forward inside the home table or removes a man from the point of that number (ace = 1 ... six = 6). The worked example (Fig. 2 distribution, throw quatre trois) is the acceptance case: quatre removes from the quatre point or moves cinque to ace.")

add(id="bear-off-example-distribution", name="Worked example: Fig. 2 distribution and quatre trois", section=BEAR, page=275,
    kind="value", scope="in", clarity="clear", dependsOn=["bear-off-by-number"],
    crossReferences=[{"cites": "(see Fig. 2)", "unmapped": "Fig. 2 is an illustration the plain-text adapter cannot read; the distribution it shows is restated in full in this span's prose."}],
    evidence='Thus, suppose that the player\'s men are thus distributed in his table: five men on the cinque point, three on the quatre point, three on the deuce, and four on the ace point, the trois and six points being unoccupied (see Fig. 2). Suppose that the player throws "quatre trois." For the quatre, he may either remove a man from the quatre point or advance a man from the "cinque" {276} to the "ace" point.',
    note="Test fixture stated by the corpus: cinque 5, quatre 3, deuce 3, ace 4, trois and six empty. For a quatre the legal options are exactly: bear off from quatre, or move cinque to ace. The same fixture is used by must-play-forward-no-man and bear-off-doublets. Straddles {276}.")

# ---------------- page 276 ----------------
add(id="must-play-forward-no-man", name="No man on the thrown point: must play forward", section=BEAR, page=276,
    kind="operation", scope="in", clarity="clear", dependsOn=["bear-off-by-number", "bear-off-example-distribution"],
    enabledBy=["bearing-off-stage"], suspendedBy=["bar-suspends-other-men"],
    evidence='In the case of the trois, he has no man on that point, and therefore _must_ play forward, either by advancing a man from the cinque to the deuce, or from the quatre to the ace point.',
    note="When no man stands on the point matching the number but a forward move within the table exists, the man must be moved forward, not borne off from another point. In the fixture, trois allows only cinque to deuce or quatre to ace.")

add(id="bear-off-from-highest", name="Number too high: bear off from the highest occupied point", section=BEAR, page=276,
    kind="operation", scope="in", clarity="clear", dependsOn=["bear-off-by-number", "must-play-forward-no-man"],
    enabledBy=["bearing-off-stage"], suspendedBy=["bar-suspends-other-men"],
    evidence='If, however, he throws a number which he cannot deal with after either of these fashions--_e.g._, a six, he is entitled to bear off a man from his highest occupied point, in this case the cinque.',
    note="Only when a number can neither remove from its own point nor move a man forward may it bear off a man from the highest occupied point. Fixture: a six bears off from the cinque. A test must also show this is refused where a forward move exists.")

add(id="bear-off-doublets", name="Doublets while bearing off", section=BEAR, page=276,
    kind="operation", scope="in", clarity="clear",
    dependsOn=["doublets", "bear-off-by-number", "bear-off-example-distribution"],
    enabledBy=["bearing-off-stage"], suspendedBy=["bar-suspends-other-men"],
    crossReferences=[{"cites": "as in the earlier stage of the game", "resolvedBy": "doublets"}],
    evidence='Doublets have, as in the earlier stage of the game, a twofold value, and may be played either wholly by moving men forward, wholly by bearing off, or partly by the one method and partly by the other, as may be desirable. Suppose, for instance, that the player, having his men as shown in the figure, throws deuces; having only three men on the deuce point, he can only bear off that number; the fourth man must be played forward, either from the cinque or quatre point.',
    note="Each of the four parts of a doublet may be a forward move or a removal, in any mix. Fixture with deuces: at most three removals from the deuce point; the fourth part must move forward from the cinque or quatre. ('as shown in the figure' refers to the distribution already restated in bear-off-example-distribution.)")

add(id="win-condition", name="First to bear off all men wins", section=BEAR, page=276,
    kind="operation", scope="in", clarity="clear", dependsOn=["bearing-off-stage", "bear-off-by-number"],
    evidence='The player who first succeeds in removing all his men from the board wins the game, but the _value_ of the game depends upon the stage reached by the adverse player, as follows:--',
    note="The game ends when a player has removed all fifteen men; he wins. Its value is decided by game-value-hit, gammon or backgammon.")

add(id="game-value-hit", name="Value of the game: a hit", section=BEAR, page=276,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("The text names the game a 'hit' but never states what a hit pays. Gammon pays 'double the agreed stake' and backgammon a multiple of 'the single stake', which suggests a hit pays the single stake, but no sentence says so."),
    dependsOn=["win-condition", "bearing-off-stage"], enabledBy=["win-condition"],
    evidence='If the adversary has got all his men into his own home table, and has begun to bear off, the game of the winner is known as a "hit."',
    note="Condition: the loser has all men home and has borne off at least one. 'Hit' here is the game value, not hit-blot.")

add(id="gammon", name="Value of the game: a gammon (double stake)", section=BEAR, page=276,
    kind="operation", scope="in", clarity="clear", dependsOn=["win-condition"], enabledBy=["win-condition"],
    evidence='If the winner has borne off all his men before his adversary has begun to do the same, the game is known as a "gammon." The loser is said to be "gammoned," and pays double the agreed stake.',
    note="Condition: the loser has not borne off any man. Payment: twice the agreed stake. The stake itself is a caller-supplied parameter (no entry). See game-value-coverage for how it overlaps backgammon.")

add(id="backgammon-multiplier-agreed", name="Backgammon pays three or four stakes, as agreed", section=BEAR, page=276,
    kind="assertion", scope="in", clarity="clear",
    evidence='the loser pays {277} either thrice or four times (as may have been agreed) the amount of the single stake.',
    note="Assertion (delegated choice with a fixed set): the players' prior agreement fixes the multiplier, and the corpus fixes its values, 'either thrice or four times'. The engine demands 3 or 4, records it, and never defaults it. Straddles {277}; cited on p. 276.")

add(id="backgammon", name="Value of the game: a backgammon", section=BEAR, page=276,
    kind="operation", scope="in", clarity="clear",
    dependsOn=["win-condition", "hit-blot", "backgammon-multiplier-agreed"], enabledBy=["win-condition"],
    evidence='If the winner has borne off all his men while the adversary has still a man or men "up" (_i.e._, on the bar) or in his (the winner\'s) home table, the game is a "backgammon,"',
    note="Condition: the loser has at least one man on the bar or in the winner's home table when the winner finishes. 'Up' = on the bar. Payment per backgammon-multiplier-agreed. Tests must cover the bar case and the winner's-home-table case.")

add(id="game-value-coverage", name="Hit/gammon/backgammon cases overlap and leave a gap",
    derivedFrom=["game-value-hit", "gammon", "backgammon"],
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("(1) A loser with a man up or in the winner's home table has usually not begun bearing off, so both gammon and backgammon apply. No sentence says backgammon prevails, though the ascending order suggests it. (2) A loser who began bearing off and was then hit, with a man outside his home table but neither on the bar nor in the winner's home table, fits none of the three definitions."),
    dependsOn=["game-value-hit", "gammon", "backgammon"],
    note="No sentence states either finding; both follow from comparing the three definitions. Overlap: gammon ('before his adversary has begun') and backgammon ('still a man or men up or in his home table') share cases. Gap: 'has begun to bear off' without 'all his men' in the home table. Case (2) needs a man hit after bearing off began, which bearing-off-stage leaves open.")

# ---------------- page 277 ----------------
add(id="next-game-first-throw", name="Who begins the next game", section=BEAR, page=277,
    kind="operation", scope="in", clarity="clear",
    dependsOn=["game-value-hit", "gammon", "backgammon", "first-player"], enabledBy=["win-condition"],
    crossReferences=[{"cites": "as at starting", "resolvedBy": "first-player"}],
    evidence='Where several games are played in succession, the winner of a "hit" throws first in the game next following. After a gammon or backgammon, the players throw again for the right to begin, as at starting.',
    note="Applies only to a series of games. After a hit, its winner begins the next game (mapper's reading: with a normal two-dice throw; the adopt-or-rethrow option belongs to first-player's throw and does not arise). After a gammon or backgammon, first-player is repeated. Tests must show both branches.")

add(id="hints-general-principles", name="General hints: make points, avoid blots", section=HINTS, page=277,
    kind="operation", scope="out", clarity="clear", status="declined",
    evidence='A leading principle is to "make points" whenever you fairly can, especially in or close to your home table. A second general principle is to avoid the leaving of "blots," particularly where they are likely to be "hit" by the adversary.[66]',
    note="Declined: strategy advice, which demands nothing of any player. Footnote [66] and the rest of the paragraph (spreading men, sometimes wanting to be hit) are advice too.")

add(id="possible-throws", name="The set of possible throws", section=HINTS, page=277,
    kind="value", scope="in", clarity="clear", dependsOn=["throw-naming", "doublets"],
    evidence='We will go _seriatim_ through all the possible throws.',
    note="The only place the chapter fixes the range of a die. The headings that follow (pp. 277-280), said to be all the possible throws, are: aces, deuce ace, deuces, trois ace, trois deuce, double trois, quatre ace, quatre deuce, quatre trois, double quatre, cinque ace, cinque deuce, cinque trois, cinque quatre, double cinque, six ace, six deuce, six trois, six quatre, six cinque, sixes. That is every unordered pair from ace (1) to six (6), 21 throws. The advice under each heading is declined separately; this entry takes only the enumeration as fact. A test must pin the whole set.")

add(id="rubber-scoring", name="Rubber: games won, gammon reckoned a double game", section=HINTS, page=278,
    kind="operation", scope="in", clarity="ambiguous",
    ambiguity=unres("The rubber is only mentioned, in passing, inside strategy advice. It implies a rubber can be decided within two games by one side winning two games' worth (a gammon counts double), but never defines a rubber's length or winning total. It also does not say how a backgammon is reckoned in a rubber."),
    dependsOn=["game-value-hit", "gammon"],
    evidence='This case often arises where the player has already lost the first hit of a rubber, in which case, if he loses the next game, he has lost the rubber also; but if he can secure a gammon (reckoning as a double game), he becomes the winner of the rubber.',
    note="Mapped in scope, although it sits in HINTS FOR PLAY, because it states how rubbers are scored rather than advising a play. Scope is decided per rule. A test must show: lose hit then lose the next game, rubber lost; lose hit then win a gammon, rubber won.")

# ---------------- opening-move advice pp. 277-280 (declined) ----------------
advice = [
    ("hint-aces", "ACES", 278, 'ACES.--(The best possible throw at starting.) Play two men on your "bar" point, and two on your cinque point.[67]'),
    ("hint-deuce-ace", "DEUCE ACE", 278, 'DEUCE ACE.--For a hit, play the deuce from the five men in your adversary\'s outer-table, and the ace from the ace point in his inner table. For a gammon, play the ace from the six to the ace point in your own table.'),
    ("hint-deuces", "DEUCES", 278, 'DEUCES.--For a hit, play two from the six to the quatre point in your own table, and the other two from the ace to the trois point in your opponent\'s inner table. For a gammon, play the second pair from the five men in his outer table.'),
    ("hint-trois-ace", "TROIS ACE", 278, 'TROIS ACE.--Make your cinque point.'),
    ("hint-trois-deuce", "TROIS DEUCE", 278, 'TROIS DEUCE.--The approved play is to carry two men from the five in your adversary\'s outer table to the quatre and cinque points in your own outer table. This, of course, makes two blots. To avoid this, some, for a hit, play one man from the same {279} point to the _deuce_ point in the above-mentioned table, but the bolder play is to be preferred.'),
    ("hint-double-trois", "DOUBLE TROIS", 279, 'DOUBLE TROIS.--There are three ways of playing this throw. Some players make the bar point. The more usual play is, for a hit, to play two to the cinque point in the player\'s own, and the other two to the quatre point in the adversary\'s table. For a gammon, play the last two from the six to the trois point in your own table.'),
    ("hint-quatre-ace", "QUATRE ACE", 279, 'QUATRE ACE.--Play the quatre from the five men in your opponent\'s outer table, and the ace from his ace point. (Timid players, fearing to leave two blots, sometimes play the whole throw from the first-mentioned point, but the plan is not to be recommended.)'),
    ("hint-quatre-deuce", "QUATRE DEUCE", 279, 'QUATRE DEUCE.--Make your quatre point.'),
    ("hint-quatre-trois", "QUATRE TROIS", 279, 'QUATRE TROIS.--Play two men from the five in your adversary\'s outer table.'),
    ("hint-double-quatre", "DOUBLE QUATRE", 279, 'DOUBLE QUATRE.--Play two men from the ace to the cinque point in the adversary\'s inner table, and two from the five in his outer table. For a gammon, play two men only, from the point last mentioned to the cinque point in your own table.'),
    ("hint-cinque-ace", "CINQUE ACE", 279, 'CINQUE ACE.--Play the cinque from the five men in your adversary\'s outer table, and the ace from the ace point in his inner table. For a gammon, play the ace from the six to the cinque point in your own table.'),
    ("hint-cinque-deuce", "CINQUE DEUCE", 279, 'CINQUE DEUCE.--Play both men from the five in your adversary\'s outer table.'),
    ("hint-cinque-trois", "CINQUE TROIS", 279, 'CINQUE TROIS.--Make your trois point.'),
    ("hint-cinque-quatre", "CINQUE QUATRE", 279, 'CINQUE QUATRE.--Move one man from your adversary\'s ace point to the trois point in his outer table.'),
    ("hint-double-cinque", "DOUBLE CINQUE", 280, 'DOUBLE CINQUE.--Carry two men from the five in the adversary\'s outer table, and make your trois point.'),
    ("hint-six-ace", "SIX ACE", 280, 'SIX ACE.--Make your bar point.'),
    ("hint-six-deuce", "SIX DEUCE", 280, 'SIX DEUCE.--Move a man from the five in your adversary\'s outer table to the cinque point in your own table.'),
    ("hint-six-trois-quatre-cinque", "SIX TROIS, SIX QUATRE, SIX CINQUE", 280, 'SIX TROIS, SIX QUATRE, SIX CINQUE.--Carry one man from your adversary\'s ace point as far as the throw will permit.'),
    ("hint-sixes", "SIXES", 280, 'SIXES.--Place two men on your adversary\'s bar point, and two on your own.'),
]
pointer_notes = {
    "hint-trois-deuce": [{"cites": "above-mentioned table", "unmapped": "Points back to the adversary's outer table named earlier in this same declined advice; no rule is referenced."}],
    "hint-quatre-ace": [{"cites": "first-mentioned point", "unmapped": "Points back to the five men in the opponent's outer table named earlier in this same declined advice; no rule is referenced."}],
    "hint-double-quatre": [{"cites": "point last mentioned", "unmapped": "Points back to a point named earlier in this same declined advice; no rule is referenced."}],
}
for aid, head, pg, ev in advice:
    kw = dict(id=aid, name=f"Opening-move advice: {head}", section=HINTS, page=pg,
              kind="operation", scope="out", clarity="clear", status="declined", evidence=ev,
              note="Declined: a recommended play for this opening throw. It is advice; any legal play is permitted. Only the heading's contribution to the set of possible throws is mapped (possible-throws).")
    if aid in pointer_notes:
        kw["crossReferences"] = pointer_notes[aid]
    if aid == "hint-aces":
        kw["note"] += " Footnote [67] (why the blot this play leaves matters little) is advice too."
    add(**kw)

add(id="hints-throw-ranking", name="Ranking of opening throws", section=HINTS, page=280,
    kind="value", scope="out", clarity="clear", status="declined",
    crossReferences=[{"cites": "Of the above throws", "resolvedBy": "possible-throws"}],
    evidence='Of the above throws (at the outset of the game), double aces are reckoned the best, and double sixes next best. Double trois comes third, followed by trois ace and six ace. Doublets, if playable, are good, as covering greater distance.',
    note="Declined: an evaluation of opening throws, not a rule.")

add(id="hints-two-apart", name="Throws whose numbers differ by two", section=HINTS, page=280,
    kind="value", scope="out", clarity="clear", status="declined",
    crossReferences=[{"cites": "[68]", "unmapped": "Footnote [68] refers the reader to the Backgammon article in 'The Book of Card and Table Games' (Routledge), of which this chapter is an abridgment. That work is not admitted, and the manifest lists no references. The footnote is a further-reading pointer, not a rule deferral."}],
    evidence='Any throw in which the higher of the two numbers is _two in advance of the other_ (as cinque trois, trois ace) is also good, as enabling you to make a point in your table.[68]',
    note="Declined: advice. '[68]' is recorded as a pointer, although it is not an 'as provided in' phrase, because it names a fuller source this abridgment rests on.")

# ---------------- absences ----------------
add(id="doubling-cube-absent", name="Doubling the stake during play", section=BEAR, page=276,
    kind="operation", scope="out", clarity="clear", status="declined",
    absentFrom={"searched": ["cube", "redouble", "doubling", "raise the stake"]},
    evidence='The loser is said to be "gammoned," and pays double the agreed stake.',
    note="The stake is agreed in advance and multiplied only by the game's value (gammon, backgammon). No rule lets a player raise it during play. Quotes the stake passage where such a rule would sit. 'double' itself occurs, as the gammon multiplier and for doublets, so it could not be searched.")

add(id="irregularities-absent", name="Irregular throws and misplays", section=PLAY, page=275,
    kind="operation", scope="out", clarity="clear", status="declined",
    absentFrom={"searched": ["cocked", "penalty", "misplay", "irregular", "error"]},
    evidence='Any part of a throw which cannot be played is lost to the thrower, but every player is compelled to play the whole of his throw if it is possible to do so.',
    note="The chapter has no laws on dice that land badly, wrong moves, or penalties (the only 'must play' rule is must-play-whole-throw). Quotes the closing rule of PLAYING where such provisions would follow. The playing-surface wording ('throwing on the centre of the board') states no consequence for a throw elsewhere.")

add(id="bar-man-blocks-bearing-off", name="A player with a man on the bar cannot bear off",
    derivedFrom=["bearing-off-stage", "hit-blot"],
    kind="operation", scope="in", clarity="clear", dependsOn=["bearing-off-stage", "hit-blot"],
    note="bearing-off-stage requires all a player's men in his home table. hit-blot places a taken-up man on the bar, 'between the two tables', which is not his home table. So a man up bars bearing off. No sentence says so. A test must show a player with fourteen men home and one on the bar has no bearing-off move.")

# ====================== write + check ======================
M = {
    "schemaVersion": 1,
    "corpus": SRC,
    "baseline": {"contentHash": "5d505fa9f6202340eb55313b8ef607b816087a860d3d51b1bf92b5f65240645e",
                 "hashDerivation": "gutenberg-plain-text-including-boilerplate"},
    "extent": {"unit": "page", "from": 271, "to": 280},
    "entries": E,
}
out = f"{BUNDLE}/out/blind-map.json"
with open(out, "w") as f:
    json.dump(M, f, indent=2, ensure_ascii=False)
    f.write("\n")

text = open(f"{BUNDLE}/hoyle.txt", encoding="utf-8").read()
norm_chars, norm_pos = [], []
prev_ws = False
for i, ch in enumerate(text):
    if ch.isspace():
        if prev_ws:
            continue
        norm_chars.append(" "); norm_pos.append(i); prev_ws = True
    else:
        norm_chars.append(ch); norm_pos.append(i); prev_ws = False
norm = "".join(norm_chars)
markers = [(m.start(), int(m.group(1))) for m in re.finditer(r"\{(\d+)\}", norm)]
ext_start = norm.index("{271}"); ext_end = norm.index("{281}")
extent_text = norm[ext_start:ext_end].lower()

def page_at(p):
    pg = None
    for pos, n in markers:
        if pos <= p: pg = n
        else: break
    return pg

errs = []
ids = [e["id"] for e in E]
dups = [i for i, c in collections.Counter(ids).items() if c > 1]
if dups: errs.append(f"duplicate ids {dups}")
idset = set(ids)
byid = {e["id"]: e for e in E}
reached = set()
for e in E:
    for fld in ["dependsOn", "enabledBy", "suspendedBy", "derivedFrom"]:
        for r in e.get(fld, []):
            if r not in idset: errs.append(f"{e['id']}.{fld} -> missing {r}")
            elif fld != "derivedFrom" and "absentFrom" in byid[r]: errs.append(f"{e['id']}.{fld} -> absent {r}")
    if set(e.get("enabledBy", [])) & set(e.get("suspendedBy", [])):
        errs.append(f"{e['id']} same id in enabledBy and suspendedBy")
    for x in e.get("crossReferences", []):
        if ("resolvedBy" in x) == ("unmapped" in x): errs.append(f"{e['id']} xref needs exactly one of resolvedBy/unmapped")
        if "resolvedBy" in x and x["resolvedBy"] not in idset: errs.append(f"{e['id']} xref -> missing {x['resolvedBy']}")
        if x["cites"] not in e.get("evidence", ""): errs.append(f"{e['id']} xref cites not in evidence: {x['cites']}")
    if "derivedFrom" in e:
        if len(e["derivedFrom"]) < 2: errs.append(f"{e['id']} derivedFrom <2")
        for k in ["locator", "evidence", "crossReferences", "absentFrom", "beyondAdapter"]:
            if k in e: errs.append(f"{e['id']} derived carries {k}")
        for r in e["derivedFrom"]:
            if r in byid and byid[r]["scope"] != "in": errs.append(f"{e['id']} derives from out-of-scope {r}")
        continue
    ev = re.sub(r"\s+", " ", e["evidence"]).strip()
    if "..." in ev or "…" in ev: errs.append(f"{e['id']} ellipsis")
    p = norm.find(ev)
    if p < 0:
        errs.append(f"{e['id']} evidence NOT FOUND"); continue
    if norm.find(ev, p + 1) >= 0 and not (ext_start <= p < ext_end):
        errs.append(f"{e['id']} evidence ambiguous location")
    if not (ext_start <= p < ext_end): errs.append(f"{e['id']} evidence outside extent")
    start_pg = page_at(p); end_pg = page_at(p + len(ev) - 1)
    cited = int(e["locator"]["citation"].rsplit("p. ", 1)[1])
    if cited not in (start_pg, end_pg): errs.append(f"{e['id']} cites p.{cited}, span on {start_pg}-{end_pg}")
    for pg in range(start_pg, end_pg + 1): reached.add(pg)
    if "absentFrom" in e:
        if e["scope"] != "out" or e["status"] != "declined": errs.append(f"{e['id']} absent must be out/declined")
        for term in e["absentFrom"]["searched"]:
            if term.lower() in extent_text: errs.append(f"{e['id']} absent term found in extent: {term}")
    if "ambiguity" in e and ("beyondAdapter" in e or "absentFrom" in e): errs.append(f"{e['id']} ambiguity with decline field")
    if (e["clarity"] == "ambiguous") != ("ambiguity" in e): errs.append(f"{e['id']} clarity/ambiguity mismatch")
    if e["scope"] == "out" and e["status"] != "declined": errs.append(f"{e['id']} out but not declined")
for e in E:
    if "derivedFrom" in e and (e["clarity"] == "ambiguous") != ("ambiguity" in e):
        errs.append(f"{e['id']} clarity/ambiguity mismatch")
# conflicts
conf = collections.defaultdict(list)
for e in E:
    c = e.get("ambiguity", {}).get("conflict")
    if c: conf[c].append(e)
for c, mem in conf.items():
    if len(mem) < 2: errs.append(f"conflict {c} has one member")
    if len({m["ambiguity"]["fate"] for m in mem}) > 1: errs.append(f"conflict {c} mixed fates")
missing = [pg for pg in range(271, 281) if pg not in reached]
if missing: errs.append(f"pages not reached: {missing}")

print("entries:", len(E))
for fld in ["kind", "scope", "clarity", "status"]:
    print(fld, dict(collections.Counter(e[fld] for e in E)))
print("derived:", sum("derivedFrom" in e for e in E), "absent:", sum("absentFrom" in e for e in E),
      "beyondAdapter:", sum("beyondAdapter" in e for e in E), "ambiguity:", sum("ambiguity" in e for e in E),
      "conflicts:", {k: len(v) for k, v in conf.items()})
print("pages reached:", sorted(reached))
print("ERRORS:" if errs else "SELF-CHECK OK", *errs, sep="\n  ")
sys.exit(1 if errs else 0)
