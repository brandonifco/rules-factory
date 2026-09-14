import json, re
D="/tmp/claude-1000/-home-brandon/c915b81d-7a9c-4add-951f-8d97ef7533e7/scratchpad/blind/"
UR="RequiresInterpretation"
def L(sec,p): return {"sourceId":"hoyle-1909","citation":f"BACKGAMMON / {sec} / p. {p}"}
E=[]
def e(id,name,sec,p,kind,scope,ev,clarity="clear",**kw):
    d={"id":id,"name":name,"locator":L(sec,p),"kind":kind,"scope":scope,"clarity":clarity}
    for k in ["ambiguity","dependsOn","gatedBy","absentFrom","crossReferences"]:
        if k in kw: d[k]=kw[k]
    d["evidence"]=ev
    d["status"]="mapped" if scope=="in" else "declined"
    if "note" in kw: d["note"]=kw["note"]
    E.append(d)
B,P,O,H="Backgammon","Playing","Bearing off the men","Hints for play"
def amb(q,**k): return dict(question=q,**k,fate="unresolved",unresolvedReason=UR)

e("players-and-men","Two players, fifteen men each",B,271,"value","in",
 'Backgammon is played by two persons, on a special "board" with thirty "men," fifteen white and fifteen black (or red)',
 note="Two sides, fifteen men per side, thirty in all. Colour naming (white vs black or red) is presentational.")
e("board-compartments","The board has two equal compartments",B,271,"value","in",
 'The board (see Fig. 1) is square, usually of wood, lined with leather, and is divided into two equal compartments, each with a raised wall or border.',
 crossReferences=[{"cites":"see Fig. 1","unmapped":"Fig. 1 is an illustration; the division into two compartments is stated in this same sentence."}],
 note="Only the division into two compartments is rule-bearing; shape and materials are physical description with no engine consequence.")
e("board-construction","Physical construction of the board",B,271,"value","out",
 'It is usually made in two portions, {272} hinged so as to fold together, and bearing on their outward surfaces the necessary squares for draughts or chess, so that the one board may answer both purposes.',
 note="Out: describes manufacture (hinging, draughts squares on the outside). No bearing on play.")
e("table-designations","Inner (home) and outer tables",B,272,"value","in",
 'The board is so placed in use that the two compartments, known as "tables," shall lie longitudinally between the players. One of these is known as the "outer," the other as the "inner" or "home" table. Which of the two is for the time being the inner and which the outer table is governed by the arrangement of the men at starting. With the men placed as in Fig. 1, the right hand is the inner or home table, and the left hand consequently the outer table. The portions of the two latter nearest to each player are known as _his_ inner and outer tables respectively.',
 dependsOn=["board-compartments","starting-position"],
 crossReferences=[{"cites":"as in Fig. 1","unmapped":"Fig. 1 is an illustration; only the left/right orientation depends on it, which is presentational."},
                  {"cites":"arrangement of the men at starting","resolvedBy":"starting-position"}],
 note="Four quarters: each player's inner and outer table. The definition is mutually recursive with starting-position (which is phrased in terms of inner/outer tables), but the two compartments are symmetric, so either choice yields the same game mirrored: clear. Left/right orientation is not rule-bearing.")
e("point-count","Twelve points to a table",B,272,"value","in",
 'Each table is marked with twelve "points," six at either end.',
 dependsOn=["table-designations"],
 note="Two tables x twelve points = 24 points; six per player-quarter.")
e("point-colours","Alternating point colours",B,272,"value","out",
 'They are alternately of black and white, black and red, or other distinctive colours.',
 note="Out: presentational.")
e("point-designations","Point names ace through six",B,272,"value","in",
 'The two points in the inner table farthest from the dividing partition or "bar" are known as the "ace" points, and those next in order as the two or "deuce" points, followed in succession by the three or "trois" points, the four or "quatre" points, the five or "cinque" points, and finally the "six"[65] points, next the bar. The points in the outer tables are designated in like manner, but starting in this case from the dividing partition. The ace point in the outer table is more commonly known as the "bar" point.',
 dependsOn=["point-count","table-designations"],
 note="Whole table required: inner ace..six counted from the far end toward the bar; outer ace..six counted from the bar outward; outer ace = 'bar point'. Also defines 'bar' as the dividing partition. Demonstrate all 24 designations for both players.")
e("dice-apparatus","A pair of dice and dice-boxes",B,272,"value","in",
 'A pair of dice (or sometimes a pair for each player) and a couple of dice-boxes complete the apparatus of the game.',
 note="Two dice per throw. Whether the pair is shared or per-player, and the dice-boxes, have no effect on outcomes. Number of faces is not stated here; see die-faces.")
e("doubling-cube","Doubling cube / doubling the stake during play",B,272,"value","out",
 'A pair of dice (or sometimes a pair for each player) and a couple of dice-boxes complete the apparatus of the game.',
 absentFrom={"searched":["doubling","redouble","cube","offer to double"]},
 note="Absent: the apparatus list closes without a doubling device, and no in-game doubling of stakes appears in the chapter. Stake multiples that do appear (gammon, backgammon) are mapped separately.")
e("starting-position","Arrangement of the men at starting",B,272,"value","in",
 "The men are arranged at starting as shown in {273} Fig. 1--viz., two of White's men are placed on the ace point in Black's inner table, five are placed on the six point in Black's outer table, three on the deuce point in White's outer table, and five on the six point in White's inner table. Black's men are placed in like manner on the points immediately facing these.",
 dependsOn=["players-and-men","point-designations"],
 crossReferences=[{"cites":"Fig. 1","unmapped":"Illustration; the arrangement is restated in words in this same span, so the plain-text adapter is not defeated."}],
 note="Whole arrangement: White 2 on Black's inner ace, 5 on Black's outer six, 3 on White's outer deuce, 5 on White's inner six (15 men); Black mirrored on facing points. Verify the count sums to 15 per side.")
e("direction-of-travel","Direction of the course",P,273,"value","in",
 "The movement of the men of each player is from the ace point in his opponent's home table towards the like point in his own, though for many purposes it suffices if he can play them into his own table, independently of their reaching any particular point therein, the object of the game being first to get all the player's men into his own inner table, and then to play them out of it again, according to certain rules to be hereafter stated.",
 dependsOn=["point-designations"],
 crossReferences=[{"cites":"rules to be hereafter stated","resolvedBy":"bearing-off-eligible"}],
 note="Course runs opponent's inner ace -> opponent's inner six -> opponent's outer ace..six -> own outer six..ace -> own inner six..ace. The 'suffices' clause and 'object of the game' are commentary; the bearing-off rules they point to are mapped separately.")
e("opening-roll","Throwing for the right to begin",P,273,"operation","in",
 'The game is commenced by each player throwing on the centre of the board a single die, the higher throw of the two giving the right to begin. In the event of a tie, the players throw again. All subsequent throws are with both dice.',
 dependsOn=["dice-apparatus","die-faces"],
 note="Demonstrate higher wins, tie re-throws (repeatedly), and that every later throw uses two dice. Throwing 'on the centre of the board' is physical.")
e("opening-throw-election","Adopting the opening dice or throwing again",P,273,"operation","in",
 'The thrower of the higher number may either adopt the points shown by the two dice as his own throw, or throw again.',
 dependsOn=["opening-roll"], gatedBy=["opening-roll"],
 note="Both branches stated; the election is a caller-supplied choice, not a blank. A re-throw is with both dice (opening-roll: all subsequent throws are with both dice). Demonstrate both elections.")
e("calling-the-throw","Calling the throw aloud",P,273,"operation","out",
 'After throwing, he calls the number of the throw, the higher number first, as "six deuce," "cinque trois," "quatre ace," or as the case may be, and then proceeds to make his move in accordance with it.',
 note="Out: table etiquette / notation with no effect on state. Useful only as naming convention for throws.")
e("move-by-pip","Each die moves one man its number of points",P,273,"operation","in",
 'The number uppermost on each die entitles the player to move one man forward a corresponding number of points. Thus if he threw "six trois," he is entitled to move one man six points onward, and then the same or another man {274} three points onward.',
 dependsOn=["direction-of-travel","dice-apparatus","point-designations"],
 gatedBy=["other-men-suspended","full-table-suspension"],
 note="Two moves, one per die, by the same or different men; each landing is subject to legal-destination. The example's order (six then trois) is illustrative; the text imposes no order on the dice.")
e("doublets","Doublets played twice over",P,274,"operation","in",
 'In the event of his throwing the same points with both dice (known as "doublets"), he is entitled to play the throw twice over. Suppose, for example, that he throws two aces; he may move one or more men forward to an aggregate extent of four points. If he throw double deuces, he may move to an aggregate extent of eight points; if double threes, twelve points, and so on.',
 clarity="ambiguous",
 ambiguity=amb('"Play the throw twice over" implies four moves each of the die\'s number; "move one or more men forward to an aggregate extent of" eight points (double deuces) could also be read as permitting any split of the aggregate (e.g. 5+3). Which reading governs is not stated.'),
 dependsOn=["move-by-pip"], gatedBy=["other-men-suspended","full-table-suspension"],
 note="Demonstrate aces=4, deuces=8, trois=12 aggregates and the four-unit reading; the split-aggregate case is the declining case.")
CONF="points-open-to-a-man-entering-from-the-bar"
e("legal-destination","Points a man may be played to",P,274,"operation","in",
 'The right to move is subject to a certain qualification--viz., that a man can only be played to a point which is either vacant or occupied by one or more men of the player, or by one man only of the adversary.',
 clarity="ambiguous",
 ambiguity=amb("General rule: a man may be played to a vacant point, a point held by his own men, or a single adverse man. For a man entering from the bar, enter-from-bar names only a vacant point or a blot, and full-table-suspension treats a table as closed when each point holds two or more men (of either side). Is a point in the adversary's home table held by the entering player's own men open to him?", conflict=CONF),
 dependsOn=["point-designations"],
 note="Three open states (vacant, own men, one adverse man); closed = two or more adverse men.")
e("make-point","Making a point",P,274,"value","in",
 'A player getting two men on a given point is said to "make" such point',
 dependsOn=["legal-destination"],
 note="Vocabulary: a point with two or more of one player's men. Used by full-table-suspension and throughout the hints.")
e("make-point-advice","It is always an object to make points",P,274,"operation","out",
 'and as he thereby secures such men from capture, and at the same time impedes the onward march of the enemy, it is always an object to do this.',
 note="Out: advice embedded in the movement rules; demands nothing. The consequences it cites (security from capture, impeding) are already entailed by legal-destination.")
e("blot","Blot",P,274,"value","in",
 'A single man on a given point is known as a "blot,"',
 note="Vocabulary: exactly one man on a point.")
e("hit-blot","Hitting a blot",P,274,"operation","in",
 'and not only does not prevent the enemy playing to that point, but in the event of its being "hit"--_i.e._, reached by an adverse throw, it is "taken up" (placed on the bar between the two tables), and, however far advanced it may have been, has to begin its journey anew from the inner table of the adversary.',
 dependsOn=["blot","legal-destination","direction-of-travel"],
 note="An adverse man played to a blot's point sends the blot to the bar; it restarts from the opponent's inner table. 'Reached' is read as 'played to' (a landing, including the intermediate landing when one man plays both dice); passing over does not hit.")
e("enter-from-bar","Entering a man from the bar",P,274,"operation","in",
 'Nor can such man again start on its journey until its owner is fortunate enough to make a throw corresponding with a vacant point or blot in such table.',
 clarity="ambiguous",
 ambiguity=amb("Names only a vacant point or a blot as open to an entering man, where legal-destination also admits a point held by the player's own men.", conflict=CONF),
 dependsOn=["hit-blot","legal-destination","point-designations"],
 gatedBy=["hit-blot","full-table-suspension"],
 note="A die showing n enters on the adversary's inner-table point numbered n (course starts at his ace). Demonstrate entry onto vacant and blot points, and a non-entering die.")
e("other-men-suspended","Other men may not move while a man is on the bar",P,274,"operation","in",
 'Until he does this, the play of his other men is suspended.',
 dependsOn=["enter-from-bar"], gatedBy=["hit-blot"],
 note="While any of his men is on the bar a player may move no other man. With one man entered by one die, the other die may be played by any man.")
e("full-table-suspension","Closed home table suspends all play",P,274,"operation","in",
 "If the adverse player's home table is completely full--_i.e._, each point occupied by two or more men, his play is altogether suspended, the adversary continuing to throw and move until the course of play again throws open one or more points in his table.",
 clarity="ambiguous",
 ambiguity=amb('"Each point occupied by two or more men" does not say whose men; read with legal-destination, a point held by two of the entering player\'s own men would be open, and the table would not be "full" for him.', conflict=CONF),
 dependsOn=["enter-from-bar","make-point"], gatedBy=["hit-blot"],
 note="The barred player forfeits whole turns (does not throw) while the table stays full; the adversary throws consecutively.")
e("throw-part-lost","Unplayable part of a throw is lost",P,275,"operation","in",
 'Any part of a throw which cannot be played is lost to the thrower',
 dependsOn=["move-by-pip","legal-destination"],
 note="Demonstrate a throw fully unplayable and partly playable.")
e("must-play-whole-throw","Compulsion to play the whole throw",P,275,"operation","in",
 'every player is compelled to play the whole of his throw if it is possible to do so.',
 clarity="ambiguous",
 ambiguity=amb("Where either die can be played alone but not both together, the text does not say which die must be played (or whether the player chooses)."),
 dependsOn=["move-by-pip","doublets","throw-part-lost"],
 note="Demonstrate: a sequence playing both dice must be chosen over one playing only one; with doublets, the maximum number of units must be played. Declining case: either-but-not-both.")
e("bearing-off-eligible","Bearing off begins when all men are home",O,275,"operation","in",
 'When either player has succeeded in getting all his men into his home table, he proceeds to "bear them off"--_i.e._, to remove them from the board.',
 clarity="ambiguous",
 ambiguity=amb("The text says when bearing off begins but not whether it is suspended if one of the player's men is subsequently hit and taken up (so that not all his men are home)."),
 dependsOn=["table-designations","direction-of-travel"],
 note="Crossing into bear-off requires all fifteen men in the home table.")
e("bearing-off-move-or-remove","Each throw moves within the table or removes men",O,275,"operation","in",
 'When the game has reached this stage, each throw entitles the player either to move forward a man or men (to the extent indicated by the throw) within the limits of his own table, or to remove men from the corresponding points.',
 dependsOn=["bearing-off-eligible","move-by-pip","legal-destination"],
 gatedBy=["bearing-off-eligible"],
 note="Worked distribution (Fig. 2, stated in words on pp. 275-276): cinque 5, quatre 3, deuce 3, ace 4; throw quatre trois. For the quatre: remove from quatre or move cinque->ace. Demonstrate the whole worked example for both the quatre and the trois.")
e("bearing-off-must-play-forward","No man on the thrown point: play forward",O,276,"operation","in",
 'In the case of the trois, he has no man on that point, and therefore _must_ play forward, either by advancing a man from the cinque to the deuce, or from the quatre to the ace point.',
 dependsOn=["bearing-off-move-or-remove"], gatedBy=["bearing-off-eligible"],
 crossReferences=[],
 note="Rule stated through the worked example: with no man on the corresponding point, a forward move within the table is compulsory if one exists.")
e("bearing-off-highest","Bearing off from the highest occupied point",O,276,"operation","in",
 'If, however, he throws a number which he cannot deal with after either of these fashions--_e.g._, a six, he is entitled to bear off a man from his highest occupied point, in this case the cinque.',
 dependsOn=["bearing-off-must-play-forward"], gatedBy=["bearing-off-eligible"],
 note="Literal condition is 'cannot deal with after either of these fashions', not 'number exceeds highest point'. Surprising case to test: men on the six point only, throw deuce, adversary holding the quatre point with two men -> no man on deuce, no forward move possible -> entitled to bear off from the six. A modern reading would forbid this.")
e("bearing-off-doublets","Doublets while bearing off",O,276,"operation","in",
 'Doublets have, as in the earlier stage of the game, a twofold value, and may be played either wholly by moving men forward, wholly by bearing off, or partly by the one method and partly by the other, as may be desirable.',
 dependsOn=["doublets","bearing-off-move-or-remove","bearing-off-must-play-forward","bearing-off-highest"],
 gatedBy=["bearing-off-eligible"],
 crossReferences=[{"cites":"as in the earlier stage of the game","resolvedBy":"doublets"}],
 note="All three branches stated; the mix is the player's choice. Worked example: deuces with three men on the deuce point -> three borne off, fourth played forward from cinque or quatre.")
e("game-won","Winning the game",O,276,"operation","in",
 'The player who first succeeds in removing all his men from the board wins the game',
 dependsOn=["bearing-off-move-or-remove"], gatedBy=["bearing-off-eligible"])
e("game-value","Hit, gammon and backgammon",O,276,"operation","in",
 'but the _value_ of the game depends upon the stage reached by the adverse player, as follows:-- If the adversary has got all his men into his own home table, and has begun to bear off, the game of the winner is known as a "hit." If the winner has borne off all his men before his adversary has begun to do the same, the game is known as a "gammon." The loser is said to be "gammoned," and pays double the agreed stake. If the winner has borne off all his men while the adversary has still a man or men "up" (_i.e._, on the bar) or in his (the winner\'s) home table, the game is a "backgammon,"',
 clarity="ambiguous",
 ambiguity=amb("Two cases. (1) Uncovered: the loser has begun to bear off, then had a man hit, and at the finish has a man outside his home table but not on the bar or in the winner's home table - not a hit (not all home), not a gammon (has begun), not a backgammon. (2) Overlapping: a loser with a man on the bar who has not begun to bear off satisfies both gammon and backgammon; precedence is not stated. Also the hit's stake is only implied ('single stake')."),
 dependsOn=["game-won","gammon-stake","backgammon-stake","bearing-off-eligible"],
 gatedBy=["game-won"],
 note="Demonstrate each named result, then the uncovered and overlapping finishes as declining cases.")
e("gammon-stake","A gammon pays double",O,276,"value","in",
 'The loser is said to be "gammoned," and pays double the agreed stake.',
 note="Multiplier 2 of the agreed stake; the stake itself is a caller-supplied parameter.")
e("backgammon-stake","Backgammon multiplier, thrice or four times as agreed",O,276,"assertion","in",
 'and the loser pays {277} either thrice or four times (as may have been agreed) the amount of the single stake.',
 note="Assertion: the players' agreement fixes the multiplier from the stated set 'either thrice or four times'. Engine demands 3 or 4, attributes and records it, never defaults. Evidence straddles the p. 277 marker.")
e("successive-games","Who begins the next game",O,277,"operation","in",
 'Where several games are played in succession, the winner of a "hit" throws first in the game next following. After a gammon or backgammon, the players throw again for the right to begin, as at starting.',
 dependsOn=["game-value","opening-roll"], gatedBy=["game-won"],
 crossReferences=[{"cites":"as at starting","resolvedBy":"opening-roll"}],
 note="Demonstrate hit -> winner throws first (two dice, no opening single-die throw); gammon and backgammon -> opening-roll.")
e("strategy-advice","General principles of play",H,277,"operation","out",
 'A leading principle is to "make points" whenever you fairly can, especially in or close to your home table.',
 note="Out: advice. Demands nothing of the engine.")
e("die-faces","A die has six faces",H,277,"value","in",
 'We will go _seriatim_ through all the possible throws.',
 note="In scope despite sitting in the advice section. The enumeration that follows (pp. 278-280) lists 21 distinct throws: aces, deuce ace, deuces, trois ace, trois deuce, double trois, quatre ace, quatre deuce, quatre trois, double quatre, cinque ace, cinque deuce, cinque trois, cinque quatre, double cinque, six ace, six deuce, six trois, six quatre, six cinque, sixes. n(n+1)/2 = 21 gives n = 6, faces ace..six. Require the whole enumeration, not a sample.")
e("rubber","Games in a rubber",H,278,"operation","in",
 'This case often arises where the player has already lost the first hit of a rubber, in which case, if he loses the next game, he has lost the rubber also; but if he can secure a gammon (reckoning as a double game), he becomes the winner of the rubber.',
 clarity="ambiguous",
 ambiguity=amb("A rubber is mentioned only in passing inside advice. The text implies a gammon counts as two games and that a player down one hit loses the rubber on losing the next game, but never states how many games win a rubber, how a backgammon is reckoned, or whether the stated case generalises."),
 dependsOn=["game-value"],
 note="Stated as a consequence inside advice; the rule it presupposes (rubber length) is not stated anywhere in the chapter.")
e("opening-throw-advice","Recommended plays for each opening throw",H,278,"operation","out",
 "TROIS DEUCE.--The approved play is to carry two men from the five in your adversary's outer table to the quatre and cinque points in your own outer table. This, of course, makes two blots. To avoid this, some, for a hit, play one man from the same {279} point to the _deuce_ point in the above-mentioned table, but the bolder play is to be preferred.",
 crossReferences=[{"cites":"above-mentioned table","unmapped":"Internal pointer within advice to the table named earlier in the same paragraph."}],
 note="Out: the whole per-throw opening advice (pp. 277-280, aces through sixes) is declined as advice; this span quotes one representative paragraph. The enumeration's rule content (die faces) is mapped in die-faces.")
e("opening-throw-ranking","Ranking of opening throws",H,280,"value","out",
 'Of the above throws (at the outset of the game), double aces are reckoned the best, and double sixes next best. Double trois comes third, followed by trois ace and six ace.',
 crossReferences=[{"cites":"Of the above throws","unmapped":"Points at the opening-throw advice, which is declined."}],
 note="Out: advice.")

m={"schemaVersion":1,"corpus":"hoyle-1909",
   "baseline":{"contentHash":"5d505fa9f6202340eb55313b8ef607b816087a860d3d51b1bf92b5f65240645e","hashDerivation":"gutenberg-plain-text-including-boilerplate"},
   "extent":{"unit":"page","from":271,"to":280},"entries":E}
for x in E:
    if x.get("crossReferences")==[]: del x["crossReferences"]
json.dump(m,open(D+"blind-map.json","w"),indent=2,ensure_ascii=False)

# checks
n=lambda s: re.sub(r"\s+"," ",s).strip()
txt=open(D+"backgammon-chapter.txt").read(); nt=n(txt)
ids={x["id"] for x in E}; assert len(ids)==len(E)
bad=0
for x in E:
    ev=n(x["evidence"]); i=nt.find(ev)
    if i<0: print("NOT FOUND",x["id"]); bad+=1; continue
    pages=[int(p) for p in re.findall(r"\{(\d+)\}", nt[:i])]
    start=pages[-1] if pages else None
    inside=[int(p) for p in re.findall(r"\{(\d+)\}", ev)]
    cited=int(x["locator"]["citation"].split("p. ")[1])
    if cited not in [start]+inside: print("PAGE",x["id"],start,inside,cited); bad+=1
    for r in x.get("dependsOn",[])+x.get("gatedBy",[]):
        if r not in ids: print("BADREF",x["id"],r); bad+=1
    for c in x.get("crossReferences",[]):
        if c["cites"] not in x["evidence"]: print("XREF",x["id"],c["cites"]); bad+=1
for t in E[[x["id"] for x in E].index("doubling-cube")]["absentFrom"]["searched"]:
    if t.lower() in nt.lower(): print("ABSENT TERM FOUND",t); bad+=1
json.load(open(D+"blind-map.json"))
print(len(E),"entries; problems:",bad)
