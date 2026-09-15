#!/usr/bin/env python3
"""Build out/blind-map.json for srd-5.2.1 pages 13-16 ("Combat").

Evidence is extracted from srd-5.2.1.txt, never typed: each entry names a page to start
searching from, a start fragment and an end fragment, and the span between them (inclusive)
is taken from the whitespace-normalised text. Whitespace runs are collapsed to one space,
which the citation check treats as equal to the original runs.
"""
import json, re, pathlib

B = pathlib.Path(__file__).resolve().parent.parent
RAW = (B / "srd-5.2.1.txt").read_text(encoding="utf-8")
NORM = re.sub(r"\s+", " ", RAW)

def ev(page, start, end=None):
    base = NORM.index("{%d}" % page)
    s = NORM.index(start, base)
    if end is None:
        return start
    e = NORM.index(end, s)
    return NORM[s:e + len(end)]

SRC = "srd-5.2.1"
PG = "Playing the Game"
CB = PG + " / Combat"
OC = CB + " / The Order of Combat"
MP = CB + " / Movement and Position"
MA = CB + " / Making an Attack"
RG = "Rules Glossary"

entries = []

def E(id, name, path, page, frag, kind, *, scope="in", q=None, conflict=None, dep=(),
      en=(), su=(), xr=(), note="", absent=None, from_page=None):
    start, end = frag if isinstance(frag, tuple) else (frag, None)
    e = {"id": id, "name": name,
         "locator": {"sourceId": SRC, "citation": f"{path} / p. {page}"},
         "kind": kind, "scope": scope,
         "clarity": "ambiguous" if q else "clear"}
    if q:
        a = {"question": q}
        if conflict:
            a["conflict"] = conflict
        a["fate"] = "unresolved"
        a["unresolvedReason"] = "RequiresInterpretation"
        e["ambiguity"] = a
    e["dependsOn"] = list(dep)
    if en:
        e["enabledBy"] = list(en)
    if su:
        e["suspendedBy"] = list(su)
    if absent:
        e["absentFrom"] = {"searched": list(absent)}
    if xr:
        e["crossReferences"] = [dict(x) for x in xr]
    e["evidence"] = ev(from_page or page, start, end)
    e["status"] = "declined" if scope == "out" else "mapped"
    e["note"] = note
    entries.append(e)
    return e

def D(id, name, kind, derived, *, dep=(), en=(), su=(), note=""):
    e = {"id": id, "name": name, "kind": kind, "scope": "in", "clarity": "clear",
         "derivedFrom": list(derived), "dependsOn": list(dep)}
    if en:
        e["enabledBy"] = list(en)
    if su:
        e["suspendedBy"] = list(su)
    e["status"] = "mapped"
    e["note"] = note
    entries.append(e)

def X(cites, to=None, unmapped=None):
    return {"cites": cites, "resolvedBy": to} if to else {"cites": cites, "unmapped": unmapped}

# ---------------------------------------------------------------- p. 13: The Order of Combat
E("combat-intro", "Combat (introduction)", CB, 13,
  ("Adventurers encounter many dangerous monsters", "combat often breaks out."), "value", scope="out",
  note="Read and declined: scene-setting prose that states no rule. It demands nothing of an engine.")

E("combat-rounds-and-turns", "Combat as a cycle of rounds and turns", OC, 13,
  ("A typical combat encounter is a clash between two sides", "the fight continues to the next round if neither side is defeated."),
  "operation",
  q="This passage says the fight continues to the next round whenever neither side is defeated, while 'Ending Combat' says combat can also end when both sides agree to end it. Read literally, a combat in which both sides agree to stop but neither is defeated both continues (here) and ends (there). Which governs?",
  conflict="combat-continuation",
  dep=["initiative-roll", "initiative-order"],
  su=["combat-end-defeat", "combat-end-agreement"],
  note="The phase rule for combat: every turn-scoped entry in this slice names it in enabledBy. Whether combat has started is a fact the caller supplies (a parameter, no entry). The 'about 6 seconds' round length is mapped separately as combat-round-duration. Demonstrate: every participant takes exactly one turn per round; a new round starts only after all have had a turn.")

E("combat-round-duration", "Length of a round", OC, 13,
  "A round represents about 6 seconds in the game world.", "value",
  q="'About 6 seconds' does not fix the length of a round. Whether an engine may convert between rounds and game-world time as exactly 6 seconds per round (e.g. for durations stated in minutes) is not settled by this sentence.",
  note="Prior knowledge pulls towards '10 rounds = 1 minute'; this slice does not say that, and 'about' was left open rather than read as exact.")

E("combat-step-establish-positions", "Combat step 1: Establish Positions", OC + " / Combat Step by Step", 13,
  ("1: Establish Positions.", "how far away and in what direction."), "assertion",
  dep=[], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="Gate 3: the Game Master's own determination is operative, and the same constituent states what it is measured against: 'Given the adventurers' marching order or their stated positions in the room or other location'. The GM is treated as the engine's caller (see MAPPER-NOTES). The engine demands the positions, attributes them to the GM, records them, and never infers them.")

E("combat-step-by-step", "Combat steps 2-3: Roll Initiative, Take Turns", OC + " / Combat Step by Step", 13,
  ("2: Roll Initiative.", "Repeat this step until the fighting stops."), "operation",
  dep=["combat-step-establish-positions", "initiative-roll", "initiative-order", "combat-rounds-and-turns"],
  en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="'Until the fighting stops' is read as pointing at 'Ending Combat' (no pointer phrase, so no crossReference). Demonstrate the order: positions, then Initiative once, then repeated rounds of turns in Initiative order.")

E("initiative-roll", "Rolling Initiative", OC + " / Initiative", 13,
  ("Initiative determines the order of turns during combat.", "The GM rolls for monsters."), "operation",
  dep=["ability-check"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="Every participant makes a Dexterity check once, when combat starts; the GM rolls for monsters (attribution of who rolls, not a delegated judgement). Other passages outside the slice modify this roll (Incapacitated and Invisible conditions in the Rules Glossary); they are not mapped here.")

E("initiative-group-roll", "One Initiative roll for a group of identical creatures", OC + " / Initiative", 13,
  ("For a group of identical creatures, the GM makes a single roll", "the group has the same Initiative."), "operation",
  q="Neither 'group' nor 'identical creatures' is defined: which creatures form a group that shares one roll (same stat block? acting together? the GM's choice?) is not fixed, and the passage names no one who fixes it by a stated measure.",
  dep=["initiative-roll"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="Prior knowledge suggests 'same stat block'; the text does not say so.")

E("initiative-surprise", "Surprise: Disadvantage on Initiative", OC + " / Initiative", 13,
  ("Surprise. If a combatant is surprised by combat starting", "that foe is surprised."), "operation",
  q="The slice says what being surprised does but defines 'surprised' only by one example (an ambusher hidden from a foe unaware that combat is starting). Whether any other situation makes a combatant surprised is not fixed, and no one is named to decide it. (The Rules Glossary's 'Surprise' entry, p. 189, says 'caught unawares by the start of combat', which is itself an undefined degree.)",
  dep=["glossary-disadvantage", "initiative-roll"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="The effect (Disadvantage on the Initiative roll) is clear; the ambiguity is the trigger. Demonstrate that a surprised combatant still rolls and still takes turns.")

E("initiative-count", "Initiative count", OC + " / Initiative", 13,
  "A combatant’s check total is called their Initiative count, or Initiative for short.", "value",
  dep=["initiative-roll"],
  note="A definition: the vocabulary initiative-order and mount-controlled-initiative use.")

E("initiative-order", "Initiative order", OC + " / Initiative", 13,
  ("The GM ranks the combatants, from highest to lowest Initiative.", "The Initiative order remains the same from round to round."), "operation",
  dep=["initiative-count"], en=["combat-rounds-and-turns"],
  su=["combat-end-defeat", "combat-end-agreement", "mount-controlled-initiative"],
  note="Highest acts first; order fixed across rounds. suspendedBy mount-controlled-initiative because a controlled mount's Initiative 'changes to match yours', which departs from 'remains the same from round to round' for that mount only (the gate is entry-level; the reach is that one combatant). Ties are initiative-ties.")

E("initiative-ties", "Initiative ties", OC + " / Initiative", 13,
  ("Ties. If a tie occurs, the GM decides the order among tied monsters", "the tie is between a monster and a player character."), "assertion",
  q="The corpus fixes who orders ties among monsters, among 'characters', and between 'a monster and a player character', but not: (a) what happens when the players whose characters are tied do not agree; (b) whether 'characters' includes characters that are not player characters, and who orders a tie between a monster and such a character.",
  dep=["initiative-order"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="Gate 3, delegated-choice arm: the GM's or players' choice is operative and the set of values is fixed in the same constituent ('the order among tied monsters' / 'among tied characters', i.e. an ordering of the tied combatants). The span crosses the page-13 footer ('13 System Reference Document 5.2.1') in the extraction; on the printed page the sentence continues at the top of the right-hand column.")

# ---------------------------------------------------------------- Your Turn
YT = OC + " / Your Turn"
E("turn-move-and-action", "Your turn: move and one action", YT, 13,
  ("On your turn, you can move a distance up to your Speed and take one action.", "move first or take your action first."), "operation",
  dep=["glossary-speed", "actions-list"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="Demonstrate both orders (move then act, act then move). Incapacitated removes the action half only; the gate is not recorded on this entry because it does not suspend the move (see MAPPER-NOTES).")

E("action-options", "Where action options come from", YT, 13,
  ("The main actions you can take are listed in", "gives the rules for movement."), "value",
  dep=["actions-list"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  xr=[X("listed in “Actions” earlier in “Playing the Game.”", "actions-list"),
      X("“Movement and Position” later in “Playing the Game” gives the rules for movement", "movement-up-to-speed")],
  note="A pointer passage: the set of actions is the Actions table plus features and stat blocks, which are outside the slice.")

E("communicate-brief", "Brief communication is free", YT, 13,
  ("Communicating. You can communicate however you are able", "Doing so uses neither your action nor your move."), "operation",
  q="Where 'brief utterances and gestures' end and 'extended communication' (which requires an action) begins is not fixed; the corpus gives only examples of each ('a detailed explanation of something or an attempt to persuade a foe').",
  en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="Same question as communicate-extended; it is a gap between two stated classes, not a contradiction, so no conflict slug.")

E("communicate-extended", "Extended communication requires an action", YT, 13,
  ("Extended communication, such as a detailed explanation", "main way you try to influence a monster."), "operation",
  q="Where 'brief utterances and gestures' end and 'extended communication' begins is not fixed; only examples are given.",
  dep=["actions-list"], en=["combat-rounds-and-turns"],
  su=["combat-end-defeat", "combat-end-agreement", "incapacitated-condition"],
  note="'The Influence action is the main way you try to influence a monster' is kept in the span as a pointer to the Influence action (Rules Glossary), which is not mapped: the sentence says 'main way', not that persuasion must use it.")

E("object-interaction-free", "One free object interaction", YT, 13,
  ("Interacting with Things. You can interact with one object", "as you stride toward a foe."), "operation",
  en=["combat-rounds-and-turns"],
  su=["combat-end-defeat", "combat-end-agreement", "object-interaction-always-action", "gm-may-require-action"],
  note="One free interaction per turn, during the move or the action. Suspended for a particular object by an item that always requires an action, and by a GM requirement.")

E("object-interaction-second", "A second interaction needs the Utilize action", YT, 13,
  "If you want to interact with a second object, you need to take the Utilize action.", "operation",
  dep=["object-interaction-free", "utilize-action"], en=["combat-rounds-and-turns"],
  su=["combat-end-defeat", "combat-end-agreement", "incapacitated-condition"],
  note="Demonstrate: first interaction free, second costs the Utilize action.")

E("object-interaction-always-action", "Objects that always require an action", YT, 13,
  ("Some magic items and other special objects always require an action", "as stated in their descriptions."), "operation",
  dep=["actions-list"], en=["combat-rounds-and-turns"],
  su=["combat-end-defeat", "combat-end-agreement", "incapacitated-condition"],
  xr=[X("as stated in their descriptions", unmapped="Item and object descriptions (e.g. 'Magic Items') are outside this slice; the requirement is data an item supplies, not a passage in the slice.")],
  note="Which objects are such is supplied by each object's description.")

E("gm-may-require-action", "GM may require an action for an interaction", YT, 14,
  ("The GM might require you to use an action for any of these activities", "turn a crank to lower a drawbridge."), "assertion",
  q="'Any of these activities' has no explicit antecedent. On the printed page it follows the 'Interacting with Things' paragraphs (in the extraction the 'Playing on a Grid' sidebar falls between them), so it plausibly means object interactions, but it could also take in the free communication described earlier under 'Your Turn'.",
  dep=["actions-list"], en=["combat-rounds-and-turns"],
  su=["combat-end-defeat", "combat-end-agreement", "incapacitated-condition"],
  note="Gate 3: the GM's determination is operative and the constituent states its measure: 'when it needs special care or when it presents an unusual obstacle'. Heading: the passage continues 'Your Turn' from p. 13 (printed page top-left of p. 14).")

E("doing-nothing", "Doing nothing on your turn", YT, 14,
  "Doing Nothing on Your Turn. You can forgo moving, taking an action, or doing anything at all on your turn.", "operation",
  en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="The advice in the following sentence is mapped separately as doing-nothing-advice (declined).")

E("doing-nothing-advice", "Advice: Dodge or Ready if undecided", YT, 14,
  ("If you can’t decide what to do, consider taking the defensive Dodge action", "to delay acting."), "value", scope="out",
  note="Advice, not a rule ('consider'); dropped and recorded here so it is not mistaken for a silent omission.")

# ---------------------------------------------------------------- Playing on a Grid (sidebar, p. 13)
GR = OC + " / Playing on a Grid"
E("grid-play", "Grid rules apply when playing on a grid", GR, 13,
  ("If you play using a square grid and miniatures or other tokens", "follow these rules."), "operation",
  note="The gate for every grid entry: whether the table plays on a square grid is a caller-supplied parameter. The sidebar sits in the right column of p. 13; its placement under 'Your Turn' in the heading path follows the page layout.")

E("grid-square-size", "Each square is 5 feet", GR, 13, "Squares. Each square represents 5 feet.", "value",
  en=["grid-play"])

E("grid-speed-squares", "Speed in squares", GR, 13,
  ("Speed. Rather than moving foot by foot, move square by square", "a Speed of 30 feet translates into 6 squares."), "operation",
  q="Dividing Speed by 5 is stated without saying what happens to a remainder (a Speed that is not a multiple of 5, e.g. after halving): whether it is rounded down under the general 'Round Down' rule (p. 5) or leftover feet are usable is not stated here.",
  dep=["grid-square-size", "glossary-speed"], en=["grid-play"],
  note="Prior knowledge suggests rounding down; the passage does not say it, and the general 'Round Down' rule speaks of dividing a number, which may settle it, so the question is left for Phase 4.")

E("grid-speed-advice", "Advice: write Speed in squares", GR, 13,
  ("If you use a grid often, consider writing your Speed in squares", "character sheet."), "value", scope="out",
  note="Advice, dropped.")

E("grid-entering-square", "Cost to enter a square", GR, 13,
  ("Entering a Square. To enter a square, you must have enough movement left", "Other effects might make a square cost even more."), "operation",
  q="The passage prices an unoccupied adjacent square (1) and a square of Difficult Terrain (2), but not a square occupied by a creature whose space is not Difficult Terrain for you (an ally, or a Tiny creature), which the 'Moving around Other Creatures' rules let you pass through. The case is not fixed.",
  dep=["grid-square-size", "difficult-terrain-definition", "unoccupied-space"], en=["grid-play"],
  note="Diagonal adjacency costs the same as orthogonal (stated). 'Other effects might make a square cost even more' points to unnamed effects; no pointer phrase.")

E("grid-corners", "Diagonal movement and corners", GR, 13,
  ("Corners. Diagonal movement can’t cross the corner of a wall", "that fills its space."), "operation",
  en=["grid-play"], dep=["grid-entering-square"],
  note="Whether a terrain feature fills its space is a fact of the map (parameter).")

E("grid-ranges", "Counting range on a grid", GR, 13,
  ("Ranges. To determine the range on a grid between two things", "Count by the shortest route."), "operation",
  q="'Count by the shortest route' does not say whether the route must go around walls and other obstacles (and Corners) or is a straight count of squares ignoring them, nor restates whether a diagonal step counts as one square for range as it does for movement.",
  dep=["grid-square-size"], en=["grid-play"],
  note="Prior knowledge pulls toward 'diagonals count as 5 feet, obstacles ignored'; the passage is silent on both.")

D("grid-diagonal-step-cost", "A diagonal step on a grid costs 5 feet of Speed", "value",
  ["grid-square-size", "grid-entering-square"], dep=["grid-square-size", "grid-entering-square"], en=["grid-play"],
  note="grid-entering-square says entering a diagonally adjacent unoccupied square costs 1 square of movement; grid-square-size says a square represents 5 feet. Together: a diagonal step costs 5 feet of Speed, the same as an orthogonal one. No sentence states the diagonal cost in feet.")

# ---------------------------------------------------------------- Ending Combat (p. 14)
EC = OC + " / Ending Combat"
E("combat-end-defeat", "Combat ends when a side is defeated", EC, 14,
  ("Combat ends when one side or the other is defeated", "surrendered or fled."), "operation",
  q="'Defeated' is illustrated ('can mean the creatures are killed or knocked out or have surrendered or fled') rather than defined: whether a side is defeated when only some of its creatures are, or in a situation not listed, is not fixed, and nobody is named to decide.",
  en=["combat-rounds-and-turns"],
  note="A gate: it suspends every combat-phase entry. The conflict with combat-rounds-and-turns is about the agreement clause (combat-end-agreement), not this one.")

E("combat-end-agreement", "Combat ends by agreement", EC, 14,
  "Combat can also end when both sides agree to end it.", "operation",
  q="This says combat can end when both sides agree; 'The Order of Combat' says the fight continues to the next round if neither side is defeated. Which governs when both sides agree and neither is defeated?",
  conflict="combat-continuation", en=["combat-rounds-and-turns"],
  note="Whether both sides agree is a fact the rule tests (gate 1 parameter). A gate on every combat-phase entry.")

# ---------------------------------------------------------------- Movement and Position (p. 14)
E("movement-up-to-speed", "Move up to your Speed", MP, 14,
  ("On your turn, you can move a distance equal to your Speed or less.", "Or you can decide not to move."), "operation",
  dep=["glossary-speed"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  note="Restates the move half of turn-move-and-action consistently.")

E("movement-modes", "Climbing, crawling, jumping, swimming as part of a move", MP, 14,
  ("Your movement can include climbing, crawling, jumping, and swimming", "or they can constitute your entire move."), "operation",
  dep=["movement-up-to-speed", "glossary-climbing", "glossary-crawling", "glossary-jumping", "glossary-swimming"],
  xr=[X("climbing", "glossary-climbing"), X("crawling", "glossary-crawling"),
      X("jumping", "glossary-jumping"),
      X("swimming (each explained in “Rules Glossary”)", "glossary-swimming")],
  note="One pointer ('each explained in \"Rules Glossary\"') reaching four glossary entries; declared once per term.")

E("movement-deduct", "Deducting movement from Speed", MP, 14,
  ("However you’re moving with your Speed, you deduct the distance", "whichever comes first."), "operation",
  dep=["movement-up-to-speed"],
  note="Demonstrate a move split into parts using different modes, each part deducted from the same Speed.")

E("speed-source", "Where Speed comes from", MP, 14,
  ("A character’s Speed is determined during character creation.", "a Climb Speed, Fly Speed, or Swim Speed."), "value",
  dep=["glossary-speed"],
  xr=[X("See “Rules Glossary” for more about Speed", "glossary-speed"),
      X("determined during character creation", unmapped="Character creation is outside this slice; Speed reaches the engine as a caller-supplied parameter.")],
  note="Speed itself is a parameter (from character creation or stat block).")

E("difficult-terrain-definition", "What Difficult Terrain is", MP + " / Difficult Terrain", 14,
  ("Combatants are often slowed down by Difficult Terrain.", "are examples of Difficult Terrain."), "value",
  q="The slice gives only examples of Difficult Terrain ('Low furniture, rubble, undergrowth, steep stairs, snow, and shallow bogs'); what else counts is not fixed here and no one is named to decide. (The Rules Glossary's list, p. 181, ends 'or something similar' and is outside the slice.)",
  note="Another creature's space is Difficult Terrain by other-creature-space-difficult, which is stated and needs no judgement.")

E("difficult-terrain-cost", "Movement cost in Difficult Terrain", MP + " / Difficult Terrain", 14,
  ("Every foot of movement in Difficult Terrain costs 1 extra foot", "count as Difficult Terrain."), "operation",
  dep=["difficult-terrain-definition", "movement-deduct"],
  note="Demonstrate that overlapping sources of Difficult Terrain still cost only 1 extra foot per foot.")

E("break-up-move", "Breaking up your move", MP + " / Breaking Up Your Move", 14,
  ("You can break up your move, using some of its movement before and after", "and then go 20 feet."), "operation",
  dep=["movement-deduct", "bonus-action-rule", "reaction-once"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"])

E("drop-prone", "Dropping Prone", MP + " / Dropping Prone", 14,
  ("On your turn, you can give yourself the Prone condition", "if your Speed is 0."), "operation",
  dep=["prone-condition"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  xr=[X("(see “Rules Glossary”)", "prone-condition")],
  note="Free (no action, no Speed), barred at Speed 0. Demonstrate both.")

# Creature Size
CS = MP + " / Creature Size"
E("size-categories", "Size categories and space", CS, 14,
  ("A creature belongs to a size category, which determines the width", "from smallest (Tiny) to largest (Gargantuan)."), "value",
  xr=[X("as shown on the Creature Size and Space table", "size-space-table")],
  note="Fixes the order of sizes, which 'two sizes larger or smaller' and 'of a larger size' consume.")

E("creature-space-definition", "What a creature's space is", CS, 14,
  "A creature’s space is the area that it effectively controls in combat and the area it needs to fight effectively.", "value",
  dep=["size-categories"],
  note="A definition; descriptive, with the operative measure in size-space-table.")

E("size-source", "Where size comes from", CS, 14,
  ("A character’s size is determined by species", "specified in the monster’s stat block."), "value",
  note="Size is a caller-supplied parameter.")

E("size-space-table", "Creature Size and Space table", CS, 14,
  ("Creature Size and Space Size Space (Feet)", "16 squares (4 by 4)"), "value",
  dep=["size-categories", "grid-square-size"],
  note="The whole table, all six rows: Tiny 2½ by 2½ feet / 4 per square; Small and Medium 5 by 5 / 1 square; Large 10 by 10 / 4 squares (2 by 2); Huge 15 by 15 / 9 squares (3 by 3); Gargantuan 20 by 20 / 16 squares (4 by 4). Transcription must be verified against every row.")

# Moving around Other Creatures
MO = MP + " / Moving around Other Creatures"
E("move-through-space", "Passing through other creatures' spaces", MO, 14,
  ("During your move, you can pass through the space of an ally", "two sizes larger or smaller than you."), "operation",
  q="(a) 'A creature that is two sizes larger or smaller than you' does not say whether exactly two sizes or at least two sizes is meant (e.g. Tiny passing through Huge, three sizes apart). (b) The passage grants permission for four cases and does not say whether the space of any other creature (e.g. a hostile creature one size apart) can be passed through.",
  dep=["glossary-ally", "incapacitated-condition", "size-categories"],
  xr=[X("(see “Rules Glossary”)", "incapacitated-condition")],
  note="Prior knowledge (an earlier edition's 'at least two sizes' and 'you can't move through a hostile creature's space') pulls at both halves; neither is in this text.")

E("other-creature-space-difficult", "Another creature's space is Difficult Terrain", MO, 14,
  ("Another creature’s space is Difficult Terrain for you", "unless that creature is Tiny or your ally."), "operation",
  dep=["difficult-terrain-cost", "glossary-ally"])

D("pass-through-costs-extra", "Passing through a larger or smaller non-ally costs extra movement", "operation",
  ["move-through-space", "other-creature-space-difficult"], dep=["move-through-space", "other-creature-space-difficult"],
  note="move-through-space lets you pass through a creature two sizes larger or smaller (and an Incapacitated creature); other-creature-space-difficult makes its space Difficult Terrain unless it is Tiny or your ally. So passing through such a creature that is neither Tiny nor an ally is permitted and costs 1 extra foot per foot. No sentence states the combination.")

E("no-ending-move-in-occupied", "Can't willingly end a move in an occupied space", MO, 14,
  "You can’t willingly end a move in a space occupied by another creature.", "operation",
  dep=["occupied-space"],
  note="'Willingly' is a fact the rule tests (parameter).")

E("end-turn-in-occupied-prone", "Ending a turn in another creature's space", MO, 14,
  ("If you somehow end a turn in a space with another creature", "larger size than the other creature."), "operation",
  dep=["prone-condition", "size-categories"], en=["combat-rounds-and-turns"], su=["combat-end-defeat", "combat-end-agreement"],
  xr=[X("(see “Rules Glossary”)", "prone-condition")],
  note="Note the corpus says 'end a move' in the preceding sentence and 'end a turn' here; they are mapped as two rules. Demonstrate Tiny and larger-size exemptions.")

# ---------------------------------------------------------------- Making an Attack (pp. 14-15)
E("attack-sources", "What lets you make an attack", MA, 14,
  ("When you take the Attack action, you make an attack.", "Reactions also let you make an attack."), "operation",
  dep=["attack-action"], su=["incapacitated-condition"],
  note="Which other actions, Bonus Actions and Reactions allow an attack is supplied by those features (outside the slice).")

E("attack-structure", "The structure of an attack", MA, 15,
  "or make an attack roll as part of a spell, an attack has the following structure:", "operation",
  dep=["attack-choose-target", "attack-determine-modifiers", "attack-resolve"],
  note="The sentence begins on p. 14 ('Whether you strike with a Melee weapon, fire a Ranged weapon,'); the extraction places the 'Unseen Attackers and Targets' sidebar between the halves, so the span quotes the p. 15 half only. It applies to weapon attacks, and to attack rolls made as part of a spell.")

E("attack-choose-target", "Attack step 1: Choose a Target", MA, 15,
  ("1: Choose a Target.", "a creature, an object, or a location."), "operation",
  dep=["range-single", "reach-default"])

E("attack-determine-modifiers", "Attack step 2: Determine Modifiers", MA, 15,
  ("2: Determine Modifiers.", "penalties or bonuses to your attack roll."), "operation",
  dep=["cover-degree-determination", "cover-degree-benefits", "glossary-advantage", "glossary-disadvantage"],
  xr=[X("(see the next section)", "cover-degree-benefits")],
  note="The GM's cover determination is the assertion cover-degree-determination, whose measure is in the Cover table; this step consumes it. Whether Advantage or Disadvantage applies is decided by the rules that grant them.")

E("attack-resolve", "Attack step 3: Resolve the Attack", MA, 15,
  ("3: Resolve the Attack.", "in addition to or instead of damage."), "operation",
  dep=["attack-rolls", "damage-rolls"],
  xr=[X("as detailed earlier in “Playing the Game.”", "attack-rolls")],
  note="Damage is rolled on a hit unless the attack's own rules say otherwise; damage rules begin after this slice.")

UA = MA + " / Unseen Attackers and Targets"
E("unseen-target-disadvantage", "Attacking a target you can't see", UA, 14,
  ("When you make an attack roll against a target you can’t see", "a creature you can hear but not see."), "operation",
  dep=["glossary-disadvantage"])

E("unseen-target-wrong-location", "Targeting the wrong location misses", UA, 14,
  "If the target isn’t in the location you targeted, you miss.", "operation",
  dep=["attack-choose-target"])

E("unseen-attacker-advantage", "Attacking a creature that can't see you", UA, 14,
  "When a creature can’t see you, you have Advantage on attack rolls against it.", "operation",
  dep=["glossary-advantage"])

E("hidden-attack-reveals", "Attacking while hidden gives away your location", UA, 14,
  ("If you are hidden when you make an attack roll", "when the attack hits or misses."), "operation",
  dep=["hide-action"], en=["hide-action"],
  note="Being hidden is established by the Hide action (Rules Glossary), which is the gate that makes this reachable.")

# ---------------------------------------------------------------- Cover (p. 15)
CV = CB + " / Cover"
E("cover-definition", "Cover and its degrees", CV, 15,
  ("Walls, trees, creatures, and other obstacles can provide cover", "gives a different benefit to a target."), "value",
  xr=[X("As detailed in the Cover table", "cover-degree-benefits")])

E("cover-origin-side", "Cover only against effects from the far side", CV, 15,
  ("A target can benefit from cover only when an attack or other effect originates on the opposite side", "of the cover."), "operation",
  dep=["cover-definition"],
  note="Which side an effect originates on is a geometric fact (parameter).")

E("cover-no-stacking", "Only the most protective degree of cover applies", CV, 15,
  ("If a target is behind multiple sources of cover", "the target has Three-Quarters Cover."), "operation",
  dep=["cover-degree-benefits"],
  note="Demonstrate Half + Three-Quarters = Three-Quarters, never +7.")

E("cover-degree-benefits", "Cover table: benefits", CV, 15,
  ("Cover Degree Benefit to Target Offered By", "Can’t be targeted directly"), "value",
  q="Total Cover's benefit is 'Can't be targeted directly'. What counts as targeting 'directly', and so which effects still reach a target with Total Cover, is not fixed in the slice.",
  note="The whole table. The extraction interleaves the cells ('Three+5 bonus to AC Quarters and Dexterity saving throws' is 'Three-Quarters | +5 bonus to AC and Dexterity saving throws'; the Total row prints 'Offered By' before 'Benefit'). Read from the render: Half +2 AC and Dex saves; Three-Quarters +5 AC and Dex saves; Total can't be targeted directly.")

E("cover-degree-determination", "Which degree of cover a target has", CV, 15,
  ("Another creature or an object that covers at least half of the target", "An object that covers the whole target"), "assertion",
  q="In the Half row, 'Another creature or an object that covers at least half of the target' does not settle whether 'that covers at least half of the target' qualifies 'another creature' too, or whether any creature gives Half Cover.",
  dep=["cover-definition"],
  note="Gate 3: attack-determine-modifiers makes the GM's determination operative ('The GM determines whether the target has Cover') and the Offered By column states the measure: 'covers at least half of the target', 'covers at least three-quarters of the target', 'covers the whole target'. The GM is treated as the caller (MAPPER-NOTES). Only an object gives Three-Quarters or Total.")

# ---------------------------------------------------------------- Ranged Attacks (p. 15)
RA = CB + " / Ranged Attacks"
E("ranged-attack-definition", "What a ranged attack is", RA, 15,
  ("When you make a ranged attack, you fire a bow", "Many spells also involve making a ranged attack."), "value",
  note="Vocabulary. Whether a given attack is ranged is supplied by the weapon or spell.")

E("range-single", "Ranged attacks only within range", RA + " / Range", 15,
  ("You can make ranged attacks only against targets within a specified range.", "you can’t attack a target beyond this range."), "operation",
  dep=["ranged-attack-definition"])

E("range-normal-long", "Normal and long range", RA + " / Range", 15,
  ("Some ranged attacks, such as those made with a Longbow, have two ranges.", "you can’t attack a target beyond long range."), "operation",
  dep=["range-single", "glossary-disadvantage"], su=["underwater-ranged"],
  note="Demonstrate: within normal range no penalty; beyond normal and within long, Disadvantage; beyond long, no attack. suspendedBy underwater-ranged, which replaces the long-range rule for weapon attacks underwater (beyond normal range auto-misses). The span follows the p. 15 footer in the extraction and is still p. 15.")

E("ranged-close-combat", "Ranged attacks in close combat", RA + " / Ranged Attacks in Close Combat", 15,
  ("Aiming a ranged attack is more difficult when a foe is next to you.", "the Incapacitated condition (see “Rules Glossary”)."), "operation",
  dep=["glossary-enemy", "incapacitated-condition", "glossary-disadvantage"],
  xr=[X("(see “Rules Glossary”)", "incapacitated-condition")],
  note="Demonstrate each condition: within 5 feet, enemy can see you, enemy not Incapacitated.")

# ---------------------------------------------------------------- Melee Attacks (p. 15)
ME = CB + " / Melee Attacks"
E("melee-attack-definition", "Melee attacks are within reach", ME, 15,
  ("A melee attack allows you to attack a target within your reach.", "A few spells also involve melee attacks."), "operation",
  dep=["reach-default", "unarmed-strike"])

E("reach-default", "Reach", ME + " / Reach", 15,
  ("A creature has a 5-foot reach and can thus attack targets within 5 feet", "as noted in their descriptions."), "value",
  xr=[X("as noted in their descriptions", unmapped="Creature descriptions (stat blocks) are outside this slice; a greater reach is data the creature supplies.")])

OA = ME + " / Opportunity Attacks"
E("oa-provoke", "Moving past foes provokes an Opportunity Attack", OA, 15,
  ("Combatants watch for enemies to drop their guard.", "provoking an Opportunity Attack."), "operation",
  q="'If you move heedlessly past your foes' is worded differently from the trigger stated two sentences later ('when a creature that you can see leaves your reach'). Whether it states any further trigger (e.g. moving past a foe without leaving its reach) or only introduces the later one is not fixed.",
  dep=["oa-make"], su=["oa-avoid-disengage", "oa-no-provoke-teleport-forced"],
  note="Suspended by the two 'don't provoke' rules, which speak of provoking directly. Mapped rather than declined as prose because it is worded as a condition; the likely reading is that it introduces oa-make.")

E("oa-avoid-disengage", "Disengage avoids Opportunity Attacks", OA, 15,
  "Avoiding Opportunity Attacks. You can avoid provoking an Opportunity Attack by taking the Disengage action.", "operation",
  dep=["disengage-action"], su=["incapacitated-condition"])

E("oa-no-provoke-teleport-forced", "Teleporting and forced movement don't provoke", OA, 15,
  ("You also don’t provoke an Opportunity Attack when you Teleport", "if you fall past an enemy."), "operation",
  dep=["teleportation"],
  note="Demonstrate teleport, being moved by an effect, and falling.")

E("oa-make", "Making an Opportunity Attack", OA, 15,
  ("Making an Opportunity Attack. You can make an Opportunity Attack when a creature that you can see leaves your reach.", "right before it leaves your reach."), "operation",
  dep=["reach-default", "reaction-once", "unarmed-strike", "melee-attack-definition"],
  su=["oa-avoid-disengage", "oa-no-provoke-teleport-forced", "reaction-once", "incapacitated-condition"],
  note="Trigger: a creature you can see leaves your reach; cost: your Reaction; one melee attack with a weapon or Unarmed Strike; timing: right before it leaves. Suspended while the mover has Disengaged or is teleported or moved without its own movement, while your Reaction is spent, and while you are Incapacitated.")

# ---------------------------------------------------------------- Mounted Combat (pp. 15-16)
MC = CB + " / Mounted Combat"
E("mount-eligibility", "What can serve as a mount", MC, 15,
  ("A willing creature that is at least one size larger than a rider", "using the following rules."), "operation",
  q="'An appropriate anatomy' is not defined and no one is named to decide it, so which willing, larger creatures can serve as a mount is not fixed.",
  dep=["size-categories"],
  note="'Willing' and relative size are facts the rule tests. The gate for all mounted entries.")

E("mount-dismount-cost", "Mounting and dismounting", MC + " / Mounting and Dismounting", 15,
  ("During your move, you can mount a creature that is within 5 feet of you or dismount.", "15 feet of movement to mount a horse."), "operation",
  dep=["movement-deduct", "round-down"], en=["mount-eligibility"],
  note="Half Speed, round down, for either. Demonstrate an odd Speed.")

E("mount-control-training", "Only trained mounts can be controlled", MC + " / Controlling a Mount", 16,
  ("You can control a mount only if it has been trained to accept a rider.", "similar creatures have such training."), "operation",
  q="Whether a given creature 'has been trained to accept a rider' is given only by examples ('Domesticated horses, mules, and similar creatures'); which other creatures are 'similar' is not fixed and no one is named to decide.",
  en=["mount-dismount-cost"],
  note="Training is a fact the rule tests; the question is the stated default for 'similar creatures'.")

E("mount-controlled-initiative", "A controlled mount's Initiative matches the rider's", MC + " / Controlling a Mount", 16,
  "The Initiative of a controlled mount changes to match yours when you mount it.", "operation",
  dep=["initiative-count", "mount-control-training"], en=["mount-control-training"])

E("mount-controlled-movement", "A controlled mount moves on the rider's turn", MC + " / Controlling a Mount", 16,
  "It moves on your turn as you direct it,", "operation",
  dep=["mount-controlled-initiative"], en=["mount-control-training"])

E("mount-controlled-actions", "A controlled mount's three action options", MC + " / Controlling a Mount", 16,
  "it has only three action options during that turn: Dash, Disengage, and Dodge.", "operation",
  dep=["dash-action", "disengage-action", "dodge-action", "mount-controlled-movement"],
  en=["mount-control-training"], su=["incapacitated-condition"],
  note="The whole set of three, and that nothing else (including Attack) is available.")

E("mount-controlled-same-turn", "A controlled mount can act on the turn it is mounted", MC + " / Controlling a Mount", 16,
  "A controlled mount can move and act even on the turn that you mount it.", "operation",
  dep=["mount-controlled-actions"], en=["mount-control-training"])

E("mount-independent", "Independent mounts", MC + " / Controlling a Mount", 16,
  ("In contrast, an independent mount", "moves and acts as it likes."), "operation",
  q="The corpus defines an independent mount as 'one that lets you ride but ignores your control' but does not say what makes a mount independent: whether every mount without the training is independent, or a trained mount may choose to be.",
  en=["mount-dismount-cost"],
  note="'Moves and acts as it likes' leaves the mount's choices to whoever runs it (for a monster, the GM).")

E("falling-off-forced-move", "Falling off when the mount is moved against its will", MC + " / Falling Off", 16,
  ("If an effect is about to move your mount against its will while you’re on it", "within 5 feet of the mount."), "operation",
  q="Where more than one unoccupied space lies within 5 feet of the mount, the passage does not say who chooses the space the rider lands in.",
  dep=["saving-throws", "prone-condition", "unoccupied-space"], en=["mount-dismount-cost"],
  xr=[X("(see “Rules Glossary”)", "prone-condition")],
  note="DC 10 Dexterity saving throw; on failure, fall off and land Prone.")

E("falling-off-prone", "Falling off when rider or mount is knocked Prone", MC + " / Falling Off", 16,
  ("While mounted, you must make the same save", "or the mount is."), "operation",
  dep=["falling-off-forced-move"], en=["mount-dismount-cost"])

E("mount-target-choice", "Choosing to attack the rider or the mount", MC + " / Controlling a Mount", 16,
  ("The Initiative of a controlled mount changes to match yours", "moves and acts as it likes."), "operation",
  scope="out", absent=["redirect", "target the mount", "targets the mount", "attacks against the mount", "rider or the mount"],
  note="Not in the corpus: the slice's mounted rules say nothing about whether attacks aimed at a mount can be shifted to the rider or vice versa. The span is where such a rule would sit. The search is prior-knowledge driven (an earlier edition had such a rule).")

# ---------------------------------------------------------------- Underwater Combat (p. 16)
UW = CB + " / Underwater Combat"
E("underwater-combat", "Underwater rules apply to fights underwater", UW, 16,
  "A fight underwater follows these rules.", "operation",
  note="Gate for the underwater entries. Whether the fight is underwater is a caller-supplied parameter.")

E("underwater-melee", "Impeded melee weapons underwater", UW + " / Impeded Weapons", 16,
  ("When making a melee attack roll with a weapon underwater", "unless the weapon deals Piercing damage."), "operation",
  dep=["swim-speed", "glossary-disadvantage"], en=["underwater-combat"],
  note="Demonstrate: Swim Speed or Piercing weapon removes the Disadvantage.")

E("underwater-ranged", "Ranged weapons underwater", UW + " / Impeded Weapons", 16,
  ("A ranged attack roll with a weapon underwater automatically misses", "against a target within normal range."), "operation",
  dep=["range-normal-long", "glossary-disadvantage"], en=["underwater-combat"],
  note="Beyond normal range: automatic miss; within: Disadvantage. Applies to weapons only (spell attacks are not named).")

E("underwater-fire-resistance", "Resistance to Fire underwater", UW + " / Fire Resistance", 16,
  ("Anything underwater has Resistance to Fire damage", "(explained in “Damage and Healing”)."), "operation",
  dep=["resistance-rule"], en=["underwater-combat"],
  xr=[X("explained in “Damage and Healing”", "resistance-rule")])

# ---------------------------------------------------------------- Absences
E("flanking", "Flanking bonus", MA, 15,
  ("2: Determine Modifiers.", "penalties or bonuses to your attack roll."), "operation",
  scope="out", absent=["flank", "flanking", "opposite sides of"],
  note="Not in the corpus: no rule grants a bonus for attacking a creature an ally also threatens. The span is the step where attack modifiers are determined. Prior knowledge (an optional rule elsewhere in the game's history) prompted the search.")

E("surprise-lose-turn", "Surprised combatants lose their first turn", OC + " / Initiative", 13,
  ("Surprise. If a combatant is surprised by combat starting", "Disadvantage on their Initiative roll."), "operation",
  scope="out", absent=["surprise round", "first turn", "can’t move or take an action", "can't move or take an action"],
  note="Not in the corpus: the slice's only effect of surprise is Disadvantage on Initiative. The span is where a lost-turn rule would be stated. The search is prior-knowledge driven (an earlier edition's surprise rule).")

# ---------------------------------------------------------------- Out-of-scope rules the slice depends on or is gated by
def OUT(id, name, path, page, frag, kind, note):
    E(id, name, path, page, frag, kind, scope="out",
      note="Outside the extent (" + path.split(" / ")[-1] + ", p. %d). " % page + note)

OUT("exceptions-supersede", "Exceptions supersede general rules", PG + " / Exceptions Supersede General Rules", 5,
    ("When an exception and a general", "the exception wins."), "operation",
    "Named because it bears on how the slice's specific rules (mounted Initiative, underwater ranged attacks) override general ones; no entry depends on it by edge.")
OUT("round-down", "Round Down", PG + " / Round Down", 5,
    ("Whenever you divide or multiply a number in the game, round down", "tell you to round up. {6}"), "operation",
    "Consumed by mount-dismount-cost. The Rules Glossary repeats this passage word for word (p. 187), so the span carries the following {6} page marker to be unique to p. 5.")
OUT("ability-check", "Ability checks named for their ability", PG + " / D20 Tests / Ability Checks", 6,
    "An ability check is named for the ability modifier it uses: a Strength check, an Intelligence check, and so on.", "operation",
    "Initiative is a Dexterity check.")
OUT("saving-throws", "Saving throws", PG + " / D20 Tests / Saving Throws", 7,
    ("A saving throw—also called a save—represents an attempt to evade or resist a threat", "A save’s result is detailed in the effect that caused it."), "operation",
    "Consumed by the Falling Off entries.")
OUT("attack-rolls", "Attack rolls", PG + " / D20 Tests / Attack Rolls", 7,
    ("An attack roll determines whether an attack hits", "exceeds the target’s Armor Class."), "operation",
    "The attack roll that Resolve the Attack points to.")
OUT("actions-list", "The Actions table", PG + " / Actions", 9,
    ("When you do something other than moving or communicating, you typically take an action.", "defined in more detail in “Rules Glossary.”"), "value",
    "The main actions a turn's action can be.")
OUT("bonus-action-rule", "Bonus Actions", PG + " / Bonus Actions", 10,
    ("can take a Bonus Action only when a special ability", "you can do something as a Bonus Action."), "operation",
    "Named by break-up-move.")
OUT("reaction-once", "One Reaction until your next turn", PG + " / Reactions", 10,
    "When you take a Reaction, you can’t take another one until the start of your next turn.", "operation",
    "Consumed and gated by oa-make.")
OUT("damage-rolls", "Damage rolls", PG + " / Damage and Healing / Damage Rolls", 16,
    ("Each weapon, spell, and damaging monster ability specifies the damage it deals.", "deal the damage to your target."), "operation",
    "On p. 16 but after the end of the slice ('Damage and Healing' begins the next section). Consumed by attack-resolve.")
OUT("resistance-rule", "Resistance", PG + " / Damage and Healing / Resistance and Vulnerability", 17,
    ("Some creatures and objects have Resistance or Vulnerability to certain damage types.", "damage of that type is halved against you (round down)."), "operation",
    "The target of Fire Resistance's pointer.")
OUT("glossary-advantage", "Advantage", RG + " / Advantage", 176,
    ("If you have Advantage on a D20 Test, roll two d20s,", "and use the higher roll."), "operation", "")
OUT("glossary-ally", "Ally", RG + " / Ally", 176,
    ("A creature is your ally if it is a member of your adventuring party", "designates as your ally."), "value", "")
OUT("attack-action", "Attack [Action]", RG + " / Attack [Action]", 177,
    ("When you take the Attack action, you can make one", "attack roll with a weapon or an Unarmed Strike."), "operation", "")
OUT("glossary-climbing", "Climbing", RG + " / Climbing", 178,
    ("While you’re climbing, each foot of movement costs", "use it to climb."), "operation", "")
OUT("glossary-crawling", "Crawling", RG + " / Crawling", 179,
    ("While you’re crawling, each foot of movement costs", "(2 extra feet in Difficult Terrain)."), "operation", "")
OUT("dash-action", "Dash [Action]", RG + " / Dash [Action]", 180,
    ("When you take the Dash action, you gain extra", "movement for the current turn."), "operation", "")
OUT("glossary-disadvantage", "Disadvantage", RG + " / Disadvantage", 181,
    ("If you have Disadvantage on a D20 Test, roll two", "d20s and use the lower roll."), "operation", "")
OUT("disengage-action", "Disengage [Action]", RG + " / Disengage [Action]", 181,
    ("If you take the Disengage action, your movement", "the current turn."), "operation", "")
OUT("dodge-action", "Dodge [Action]", RG + " / Dodge [Action]", 181,
    ("If you take the Dodge action, you gain the following", "throws with Advantage."), "operation", "")
OUT("glossary-enemy", "Enemy", RG + " / Enemy", 181,
    ("A creature is your enemy if it fights against you in", "designated as your enemy by the rules or GM."), "value", "")
OUT("hide-action", "Hide [Action]", RG + " / Hide [Action]", 183,
    ("With the Hide action, you try to hide yourself.", "the Invisible condition while hidden."), "operation", "")
OUT("incapacitated-condition", "Incapacitated [Condition]", RG + " / Incapacitated [Condition]", 184,
    ("While you have the Incapacitated condition, you experience the following effects. Inactive.", "or Reaction."), "operation",
    "A gate: 'You can't take any action, Bonus Action, or Reaction' suspends every in-slice entry that consists of taking one.")
OUT("glossary-jumping", "Jumping", RG + " / Jumping", 184,
    ("When you jump, you make either a Long Jump", "or a High Jump (vertical)."), "operation", "")
OUT("occupied-space", "Occupied Space", RG + " / Occupied Space", 185,
    ("A space is occupied if a creature is in it or if it is", "completely filled by objects."), "value", "")
OUT("prone-condition", "Prone [Condition]", RG + " / Prone [Condition]", 186,
    ("While you have the Prone condition, you experience", "right yourself and thereby end the condition."), "operation", "")
OUT("glossary-speed", "Speed", RG + " / Speed", 188,
    ("A creature has a Speed, which is the distance in feet", "when it moves on its turn."), "value", "")
OUT("glossary-swimming", "Swimming", RG + " / Swimming", 189,
    ("While you’re swimming, each foot of movement", "use it to swim."), "operation", "")
OUT("swim-speed", "Swim Speed", RG + " / Swim Speed", 189,
    ("A Swim Speed can be used to swim without expending", "normally associated with swimming."), "value", "")
OUT("teleportation", "Teleportation", RG + " / Teleportation", 190,
    ("This transportation doesn’t expend movement unless a rule tells you otherwise", "never provokes Opportunity Attacks."), "operation", "")
OUT("unarmed-strike", "Unarmed Strike", RG + " / Unarmed Strike", 190,
    ("Instead of using a weapon to make a melee attack,", "similar forceful blow."), "operation", "")
OUT("unoccupied-space", "Unoccupied Space", RG + " / Unoccupied Space", 191,
    ("A space is unoccupied if no creatures are in it and it", "completely filled by objects."), "value", "")
OUT("utilize-action", "Utilize [Action]", RG + " / Utilize [Action]", 191,
    ("When an object requires", "you take the Utilize action."), "operation", "")

m = {"schemaVersion": 1, "corpus": SRC,
     "baseline": {"contentHash": "c55926cb77bc7ea09096fc652db1411d763eae89d430c52221ed8709a075b100",
                  "hashDerivation": "srd-5.2.1-pdftotext-24.02.0-page-marked"},
     "extent": {"unit": "page", "from": 13, "to": 16},
     "entries": entries}
(B / "out" / "blind-map.json").write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(len(entries), "entries")
