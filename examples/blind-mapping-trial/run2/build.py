#!/usr/bin/env python3
"""Build blind-map.json for the Backgammon chapter of Hoyle's Games Modernized (1909)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "hoyle-1909"

def cit(section, page):
    return f"BACKGAMMON / {section} / p. {page}"

def unres(q, conflict=None):
    a = {"question": q}
    if conflict:
        a["conflict"] = conflict
    a["fate"] = "unresolved"
    a["unresolvedReason"] = "RequiresInterpretation"
    return a

E = []
def entry(id, name, section, page, kind, scope, evidence, clarity="clear", ambiguity=None,
          dependsOn=None, gatedBy=None, crossReferences=None, absentFrom=None, note=None):
    e = {"id": id, "name": name, "locator": {"sourceId": SRC, "citation": cit(section, page)},
         "kind": kind, "scope": scope, "clarity": clarity}
    if ambiguity: e["ambiguity"] = ambiguity
    e["dependsOn"] = dependsOn or []
    if gatedBy: e["gatedBy"] = gatedBy
    if absentFrom: e["absentFrom"] = absentFrom
    if crossReferences: e["crossReferences"] = crossReferences
    e["evidence"] = evidence
    e["status"] = "mapped"
    if note: e["note"] = note
    E.append(e)

S0 = "Backgammon"  # opening, unheaded section
entry("players-and-men", "Players and men", S0, 271, "value", "in",
      'Backgammon is played by two persons, on a special "board" with thirty "men," fifteen white and fifteen black (or red)',
      note="Two players, fifteen men each. Colour of the second side (black or red) has no rule effect.")

entry("board-tables", "Inner (home) and outer tables", S0, 272, "value", "in",
      'The board is so placed in use that the two compartments, known as "tables," shall lie longitudinally between the players. One of these is known as the "outer," the other as the "inner" or "home" table. Which of the two is for the time being the inner and which the outer table is governed by the arrangement of the men at starting. With the men placed as in Fig. 1, the right hand is the inner or home table, and the left hand consequently the outer table. The portions of the two latter nearest to each player are known as _his_ inner and outer tables respectively.',
      dependsOn=["initial-arrangement"],
      crossReferences=[{"cites": "as in Fig. 1", "resolvedBy": "initial-arrangement"}],
      note="Four quarters: each player's inner and outer table. Fig. 1 is an illustration; the arrangement it shows is also stated in text (initial-arrangement), so no beyondAdapter.")

entry("point-names", "Points and their names", S0, 272, "value", "in",
      'Each table is marked with twelve "points," six at either end. They are alternately of black and white, black and red, or other distinctive colours. The two points in the inner table farthest from the dividing partition or "bar" are known as the "ace" points, and those next in order as the two or "deuce" points, followed in succession by the three or "trois" points, the four or "quatre" points, the five or "cinque" points, and finally the "six"[65] points, next the bar. The points in the outer tables are designated in like manner, but starting in this case from the dividing partition. The ace point in the outer table is more commonly known as the "bar" point.',
      dependsOn=["board-tables"],
      crossReferences=[{"cites": "[65]", "unmapped": "Footnote 65 is not part of the extract."}],
      note="Whole naming table: inner ace..six counting toward the bar; outer ace..six counting away from the bar; outer ace == 'bar point'. Point colours are cosmetic.")

entry("dice-apparatus", "Dice and dice-boxes", S0, 272, "value", "in",
      'A pair of dice (or sometimes a pair for each player) and a couple of dice-boxes complete the apparatus of the game.',
      note="Two dice per throw. Whether a shared pair or a pair each has no rule effect. Die faces are not stated; six faces is inferred from throw names used later (ace..six).")

entry("initial-arrangement", "Arrangement of the men at starting", S0, 272, "value", "in",
      "The men are arranged at starting as shown in {273} Fig. 1--viz., two of White's men are placed on the ace point in Black's inner table, five are placed on the six point in Black's outer table, three on the deuce point in White's outer table, and five on the six point in White's inner table. Black's men are placed in like manner on the points immediately facing these.",
      dependsOn=["players-and-men", "point-names"],
      crossReferences=[{"cites": "as shown in", "unmapped": "Fig. 1 is an illustration; the same arrangement is stated in full by this passage."}],
      note="Whole table: 2 on opponent's inner ace, 5 on opponent's outer six, 3 on own outer deuce, 5 on own inner six (totals 15); mirror for Black.")

S1 = "Playing"
entry("opening-throw", "Throwing for the right to begin", S1, 273, "operation", "in",
      "The game is commenced by each player throwing on the centre of the board a single die, the higher throw of the two giving the right to begin. In the event of a tie, the players throw again. All subsequent throws are with both dice.",
      dependsOn=["dice-apparatus"],
      note="Demonstrate higher single die wins, a tie rethrows (repeatedly), and every later throw uses two dice.")

entry("opening-throw-adopt", "Adopting the opening dice or throwing again", S1, 273, "operation", "in",
      "The thrower of the higher number may either adopt the points shown by the two dice as his own throw, or throw again.",
      clarity="ambiguous",
      ambiguity=unres("'The points shown by the two dice' most naturally means the two single dice just thrown for the start (his and his opponent's), but the text does not say so; nor whether 'throw again' means both dice. The choice between the two branches is the winner's and is a parameter, not a gap."),
      dependsOn=["opening-throw"], gatedBy=["opening-throw"])

entry("calling-the-throw", "Calling the throw aloud", S1, 273, "operation", "out",
      'After throwing, he calls the number of the throw, the higher number first, as "six deuce," "cinque trois," "quatre ace," or as the case may be, and then proceeds to make his move in accordance with it.',
      note="Out of scope: an announcement convention with no effect on game state. Its naming convention (higher number first) is used by the opening-play hints.")

entry("direction-and-object", "Direction of movement and object of the game", S1, 273, "value", "in",
      "The movement of the men of each player is from the ace point in his opponent's home table towards the like point in his own, though for many purposes it suffices if he can play them into his own table, independently of their reaching any particular point therein, the object of the game being first to get all the player's men into his own inner table, and then to play them out of it again, according to certain rules to be hereafter stated.",
      dependsOn=["point-names", "board-tables"],
      crossReferences=[{"cites": "rules to be hereafter stated", "resolvedBy": "bear-off-condition"}],
      note="Path runs opponent's inner ace -> opponent's inner six -> opponent's outer -> own outer -> own inner six -> own ace; 24 points. The object clause is restated operationally by bear-off-condition and win-game.")

entry("die-movement", "Moving men by the number on each die", S1, 273, "operation", "in",
      'The number uppermost on each die entitles the player to move one man forward a corresponding number of points. Thus if he threw "six trois," he is entitled to move one man six points onward, and then the same or another man {274} three points onward.',
      clarity="ambiguous",
      ambiguity=unres("When one man takes both numbers, the text does not say whether the intermediate point must itself be a legal resting point, nor whether the numbers may be taken in either order (the example gives six then three)."),
      dependsOn=["direction-and-object", "legal-destination"],
      gatedBy=["bar-entry", "home-table-closed"],
      note="Turn alternation between players is never stated outright; it is implied by 'the adversary continuing to throw and move' (home-table-closed).")

entry("doublets", "Doublets played twice over", S1, 274, "operation", "in",
      'In the event of his throwing the same points with both dice (known as "doublets"), he is entitled to play the throw twice over. Suppose, for example, that he throws two aces; he may move one or more men forward to an aggregate extent of four points. If he throw double deuces, he may move to an aggregate extent of eight points; if double threes, twelve points, and so on.',
      clarity="ambiguous",
      ambiguity=unres("'Play the throw twice over' implies four moves of the die's number; 'an aggregate extent of eight points' for deuces could be read as a pool divisible arbitrarily (e.g. 5 + 3). The text does not say which."),
      dependsOn=["die-movement"],
      gatedBy=["bar-entry", "home-table-closed"],
      note="Whole table by extrapolation of 'and so on': 1-1=4, 2-2=8, 3-3=12, 4-4=16, 5-5=20, 6-6=24.")

entry("legal-destination", "Points a man may be played to", S1, 274, "operation", "in",
      "The right to move is subject to a certain qualification--viz., that a man can only be played to a point which is either vacant or occupied by one or more men of the player, or by one man only of the adversary.",
      clarity="ambiguous",
      ambiguity=unres("This permits a point occupied by the player's own men; bar-entry permits entering only on 'a vacant point or blot', which excludes a point the entering player already holds. Which governs a man entering from the bar?", conflict="entry-onto-own-point"),
      dependsOn=["point-names"],
      note="Demonstrate vacant, own men (1 and several), one opposing man (legal), two or more opposing men (illegal).")

entry("make-point", "Making a point", S1, 274, "value", "in",
      'A player getting two men on a given point is said to "make" such point, and as he thereby secures such men from capture, and at the same time impedes the onward march of the enemy, it is always an object to do this.',
      dependsOn=["legal-destination"],
      note="Definition: two or more own men on a point. The closing 'it is always an object to do this' is advice and is dropped.")

entry("blot", "Blot", S1, 274, "value", "in",
      'A single man on a given point is known as a "blot," and not only does not prevent the enemy playing to that point',
      dependsOn=["legal-destination"])

entry("hit-blot", "Hitting a blot", S1, 274, "operation", "in",
      'in the event of its being "hit"--_i.e._, reached by an adverse throw, it is "taken up" (placed on the bar between the two tables), and, however far advanced it may have been, has to begin its journey anew from the inner table of the adversary.',
      clarity="ambiguous",
      ambiguity=unres("'Reached by an adverse throw' does not say whether a blot touched at the intermediate point of a man playing both numbers is hit, or whether a hitting man may continue past it."),
      dependsOn=["blot", "die-movement"])

entry("bar-entry", "Entering a man from the bar", S1, 274, "operation", "in",
      "Nor can such man again start on its journey until its owner is fortunate enough to make a throw corresponding with a vacant point or blot in such table. Until he does this, the play of his other men is suspended.",
      clarity="ambiguous",
      ambiguity=unres("Entry is stated as permitted only on 'a vacant point or blot'; legal-destination also permits a point occupied by the player's own men. Which governs a man entering from the bar? Also unstated: with two men up, whether both must enter before other men move.", conflict="entry-onto-own-point"),
      dependsOn=["hit-blot", "legal-destination"],
      gatedBy=["hit-blot"],
      note="Suspension: while a man is up, no other man of that player moves.")

entry("home-table-closed", "Play suspended when the entry table is full", S1, 274, "operation", "in",
      "If the adverse player's home table is completely full--_i.e._, each point occupied by two or more men, his play is altogether suspended, the adversary continuing to throw and move until the course of play again throws open one or more points in his table.",
      clarity="ambiguous",
      ambiguity=unres("'Occupied by two or more men' does not say whose men; read literally, a point holding two of the entering player's own men counts toward 'completely full', which bears on the entry-onto-own-point question."),
      dependsOn=["bar-entry", "make-point"],
      gatedBy=["hit-blot"],
      note="The suspended player does not throw at all; the adversary throws repeatedly.")

entry("whole-throw-compulsion", "Unplayable parts lost; whole throw compulsory", S1, 275, "operation", "in",
      "Any part of a throw which cannot be played is lost to the thrower, but every player is compelled to play the whole of his throw if it is possible to do so.",
      clarity="ambiguous",
      ambiguity=unres("Where either number can be played alone but not both, the text does not say which must be played (e.g. the higher)."),
      dependsOn=["die-movement", "doublets"],
      note="Demonstrate: nothing playable; part playable (lost remainder); whole playable only in one sequence (that sequence compulsory).")

S2 = "Bearing off the men"
entry("bear-off-condition", "When bearing off begins", S2, 275, "operation", "in",
      'When either player has succeeded in getting all his men into his home table, he proceeds to "bear them off"--_i.e._, to remove them from the board.',
      clarity="ambiguous",
      ambiguity=unres("The text does not say what happens if a man is taken up after bearing off has begun: whether bearing off is suspended until all men are home again."),
      dependsOn=["direction-and-object"])

entry("bear-off-move", "Moving or removing in the bearing-off stage", S2, 275, "operation", "in",
      "When the game has reached this stage, each throw entitles the player either to move forward a man or men (to the extent indicated by the throw) within the limits of his own table, or to remove men from the corresponding points.",
      dependsOn=["bear-off-condition", "die-movement"],
      gatedBy=["bear-off-condition", "bar-entry"],
      note="Choice between moving and removing is the player's; a parameter. Fig. 2 worked example (5 on cinque, 3 quatre, 3 deuce, 4 ace) is stated in text.")

entry("bear-off-empty-point", "Numbers with no man on the corresponding point", S2, 276, "operation", "in",
      "In the case of the trois, he has no man on that point, and therefore _must_ play forward, either by advancing a man from the cinque to the deuce, or from the quatre to the ace point. If, however, he throws a number which he cannot deal with after either of these fashions--_e.g._, a six, he is entitled to bear off a man from his highest occupied point, in this case the cinque.",
      clarity="ambiguous",
      ambiguity=unres("Stated only by worked example. The general condition 'cannot deal with after either of these fashions' would, read literally, allow bearing off from the highest occupied point even when that point is above the number thrown (forward movement blocked by adverse men); the example only shows a number above the highest occupied point."),
      dependsOn=["bear-off-move"],
      gatedBy=["bear-off-condition", "bar-entry"])

entry("bear-off-doublets", "Doublets when bearing off", S2, 276, "operation", "in",
      "Doublets have, as in the earlier stage of the game, a twofold value, and may be played either wholly by moving men forward, wholly by bearing off, or partly by the one method and partly by the other, as may be desirable. Suppose, for instance, that the player, having his men as shown in the figure, throws deuces; having only three men on the deuce point, he can only bear off that number; the fourth man must be played forward, either from the cinque or quatre point.",
      dependsOn=["doublets", "bear-off-move"],
      gatedBy=["bear-off-condition", "bar-entry"],
      crossReferences=[{"cites": "as in the earlier stage of the game", "resolvedBy": "doublets"},
                       {"cites": "as shown in the figure", "unmapped": "Fig. 2 is an illustration; its distribution is stated in text in bear-off-move's evidence."}],
      note="Every branch stated (wholly move, wholly bear off, mixed); the mix is the player's choice, a parameter.")

entry("win-game", "Winning the game", S2, 276, "operation", "in",
      "The player who first succeeds in removing all his men from the board wins the game, but the _value_ of the game depends upon the stage reached by the adverse player, as follows:--",
      dependsOn=["bear-off-move"])

GV = ("The three value definitions do not partition the reachable states. Gammon ('before his adversary has begun to do the same') and backgammon (a man up or in the winner's home table) overlap whenever the adversary has not begun to bear off; and an adversary who has begun to bear off and then had a man taken up satisfies neither 'hit' (not all men home) nor 'gammon', but satisfies 'backgammon'. Which value applies in the overlap and uncovered cases?")
entry("hit-value", "A hit (single game)", S2, 276, "value", "in",
      'If the adversary has got all his men into his own home table, and has begun to bear off, the game of the winner is known as a "hit."',
      clarity="ambiguous", ambiguity=unres(GV, conflict="game-value-classification"),
      dependsOn=["win-game"],
      note="Payment for a hit is not stated directly; 'double the agreed stake' and 'the single stake' imply one stake. The stake amount is a caller parameter.")

entry("gammon", "A gammon", S2, 276, "operation", "in",
      'If the winner has borne off all his men before his adversary has begun to do the same, the game is known as a "gammon." The loser is said to be "gammoned," and pays double the agreed stake.',
      clarity="ambiguous", ambiguity=unres(GV, conflict="game-value-classification"),
      dependsOn=["win-game"])

entry("backgammon", "A backgammon", S2, 276, "operation", "in",
      'If the winner has borne off all his men while the adversary has still a man or men "up" (_i.e._, on the bar) or in his (the winner\'s) home table, the game is a "backgammon,"',
      clarity="ambiguous", ambiguity=unres(GV, conflict="game-value-classification"),
      dependsOn=["win-game", "backgammon-multiplier"])

entry("backgammon-multiplier", "Backgammon stake multiple (as agreed)", S2, 276, "assertion", "in",
      "and the loser pays {277} either thrice or four times (as may have been agreed) the amount of the single stake.",
      note="Delegated choice from a fixed set: 'either thrice or four times (as may have been agreed)'. Demand 3 or 4, attribute to the players' agreement, never default.")

entry("successive-games", "First throw in successive games", S2, 277, "operation", "in",
      'Where several games are played in succession, the winner of a "hit" throws first in the game next following. After a gammon or backgammon, the players throw again for the right to begin, as at starting.',
      dependsOn=["hit-value", "gammon", "backgammon", "opening-throw"],
      crossReferences=[{"cites": "as at starting", "resolvedBy": "opening-throw"}],
      note="Inherits the game-value-classification ambiguity: which rule applies depends on the value reached.")

S3 = "Hints for play"
entry("general-principles-advice", "General principles of play", S3, 277, "operation", "out",
      'A leading principle is to "make points" whenever you fairly can, especially in or close to your home table.',
      note="Advice, dropped: making points, avoiding blots, and when being hit may be desirable. Demands nothing.")

entry("rubber-scoring", "Rubber: a gammon reckons as a double game", S3, 278, "value", "in",
      "This case often arises where the player has already lost the first hit of a rubber, in which case, if he loses the next game, he has lost the rubber also; but if he can secure a gammon (reckoning as a double game), he becomes the winner of the rubber.",
      clarity="ambiguous",
      ambiguity=unres("The rubber is never defined. The example implies a rubber is won at two games with a gammon counting two, but the length of a rubber, and how a backgammon reckons in it (three? four?), are not stated."),
      dependsOn=["hit-value", "gammon"],
      note="A rule stated inside the advice section; scoped in per rule, unlike the surrounding advice.")

entry("opening-plays-advice-a", "Recommended opening plays, aces to trois deuce", S3, 278, "operation", "out",
      'ACES.--(The best possible throw at starting.) Play two men on your "bar" point, and two on your cinque point.[67]',
      crossReferences=[{"cites": "[67]", "unmapped": "Footnote 67 is not part of the extract; and the entry is advice."}],
      note="Advice, dropped: recommended plays for each opening throw (pp. 277-279), including hit/gammon alternatives. Not rules; any legal play is permitted.")

entry("opening-plays-advice-b", "Recommended opening plays, double trois to sixes", S3, 279, "operation", "out",
      "DOUBLE TROIS.--There are three ways of playing this throw.",
      note="Advice, dropped: continuation of the opening-play recommendations through p. 280.")

entry("throw-ranking-advice", "Ranking of opening throws", S3, 280, "value", "out",
      "Of the above throws (at the outset of the game), double aces are reckoned the best, and double sixes next best.",
      note="Advice, dropped: ranking of throws and the 'two in advance' observation.")

entry("doubling-cube", "Doubling the stake during play", S2, 276, "operation", "out",
      'The loser is said to be "gammoned," and pays double the agreed stake.',
      absentFrom={"searched": ["redouble", "cube", "doubling", "offer to double", "accept the double"]},
      note="Not in the corpus: no mid-game offer to double the stake. Quoted passage is where stake payment is stated.")

doc = {
    "schemaVersion": 1,
    "corpus": SRC,
    "baseline": {"contentHash": "5d505fa9f6202340eb55313b8ef607b816087a860d3d51b1bf92b5f65240645e",
                 "hashDerivation": "gutenberg-plain-text-including-boilerplate"},
    "extent": {"unit": "page", "from": 271, "to": 280},
    "manifest": {"schemaVersion": 1, "corpora": [{
        "sourceId": SRC, "title": "Hoyle's Games Modernized", "edition": "1909",
        "adapter": "plain-text", "locatorGrammar": "printed-page",
        "contentHash": "5d505fa9f6202340eb55313b8ef607b816087a860d3d51b1bf92b5f65240645e",
        "hashDerivation": "gutenberg-plain-text-including-boilerplate",
        "boundaryPolicy": "pin-in-repo", "licence": "public-domain", "references": []}]},
    "entries": E,
}
with open(os.path.join(HERE, "blind-map.json"), "w") as f:
    json.dump(doc, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(len(E), "entries")
