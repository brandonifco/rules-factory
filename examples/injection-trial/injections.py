#!/usr/bin/env python3
"""The injection catalogue: twenty-nine known map errors, plus two controls.

Each injection is one deliberate, *realistic* error in a corpus map. Realistic is doing
work here: the distribution is taken from the errors trial 4 found in earnest in a map
written in earnest (rules-factory issues #13, #14, #19, #31, #33, and the engine's
MAP-FINDINGS.md), not invented to suit a checker. Injecting only the kinds a checker
already catches would measure the checker's aim rather than the method's reach.

Every injection carries, in its own record:

  `family`    what kind of error it is, in the vocabulary MAP-FINDINGS.md uses.
  `wrong`     why the mutated map is FALSE about the corpus. An injection whose mutation
              happens to be true is not an injection; it is an edit.
  `modelled`  the real trial-4 finding it reproduces, where it reproduces one.
  `stratum`   the *earliest* stage that could in principle catch it. This is a prediction
              written before the detectors ran, and it is scored against what the
              detectors actually did -- a prediction that was wrong is reported as wrong.
  `invalid`   present where the run showed the injection was not an error at all under this
              project's own rules. Excluded from the denominator, and kept, because an
              injection nobody checked is worth nothing.
  `probe`     present where the injection was designed to slip past a specific check whose
              limitation is already documented. Reported apart from the rate: a chosen
              evasion is not a sample.

Patches are written as operations on a parsed map (drop this dependsOn edge, set this
citation's page) rather than as text substitutions, so that one injection applies to both
copies of the backgammon map even though their evidence strings have diverged.

A patch MUST raise if its target is not where it expects it. A mutation that silently did
nothing would be scored as an undetected error, which is the worst possible failure mode
for this trial.
"""

FACTORY = "factory"   # rules-factory/examples/hoyle-backgammon/corpus-map.json
ENGINE = "engine"     # hoyle-backgammon/corpus-map.json
BOTH = (FACTORY, ENGINE)

# The strata, as predictions of what could catch an error. Named here so the results table
# and the README cannot drift from the code.
STRATA = {
    "schema": "tools/check-map.py -- structure, vocabulary, references, exclusions",
    "corpus": "tools/check-locators.py or the engine gate's citation step -- reads the corpus",
    "code": "the engine gate's map-to-code steps -- see the README on why these are contaminated",
    "human": "nothing mechanical; only a person reading the corpus against the entry",
}


def entry(m, entry_id):
    for e in m["entries"]:
        if e["id"] == entry_id:
            return e
    raise KeyError(f"no entry {entry_id!r} in this map -- injection would have done nothing")


def set_page(m, entry_id, was, now):
    e = entry(m, entry_id)
    citation = e["locator"]["citation"]
    old = f"p. {was}"
    if old not in citation:
        raise ValueError(f"{entry_id}: citation {citation!r} does not name {old}")
    e["locator"]["citation"] = citation.replace(old, f"p. {now}")


def set_section(m, entry_id, was, now):
    e = entry(m, entry_id)
    citation = e["locator"]["citation"]
    if was not in citation:
        raise ValueError(f"{entry_id}: citation {citation!r} does not name section {was!r}")
    e["locator"]["citation"] = citation.replace(was, now)


# The gate fields. docs/decisions/0011 split the undirected `gatedBy` into `enabledBy` and
# `suspendedBy`. The recorded run was against maps that still carried `gatedBy`, and the
# engine's copy has not migrated, so a gate patch names the directed field on a migrated map
# and falls back to `gatedBy` on one that is not. Either way it touches the same edge.
GATE_FIELDS = ("gatedBy", "enabledBy", "suspendedBy")


def gate_field(m, direction):
    """`direction` ('enabledBy' or 'suspendedBy') on a migrated map, `gatedBy` otherwise."""
    if any("gatedBy" in e for e in m["entries"]):
        return "gatedBy"
    return direction


def drop_edge(m, entry_id, field, target):
    e = entry(m, entry_id)
    if target not in (e.get(field) or []):
        raise ValueError(f"{entry_id}: {field} does not contain {target!r}")
    e[field] = [x for x in e[field] if x != target]
    if not e[field] and field in GATE_FIELDS:
        del e[field]


def add_edge(m, entry_id, field, target):
    e = entry(m, entry_id)
    existing = list(e.get(field) or [])
    if target in existing:
        raise ValueError(f"{entry_id}: {field} already contains {target!r}")
    e[field] = existing + [target]


def set_evidence(m, entry_id, text):
    e = entry(m, entry_id)
    if e["evidence"] == text:
        raise ValueError(f"{entry_id}: evidence is already that text")
    e["evidence"] = text


def truncate_evidence(m, entry_id, upto):
    """Cut the evidence at `upto` (kept), leaving a span still verbatim in the corpus."""
    e = entry(m, entry_id)
    cut = e["evidence"].find(upto)
    if cut < 0:
        raise ValueError(f"{entry_id}: evidence does not contain {upto[:40]!r}")
    e["evidence"] = e["evidence"][: cut + len(upto)]


def set_field(m, entry_id, field, value):
    e = entry(m, entry_id)
    if e.get(field) == value:
        raise ValueError(f"{entry_id}: {field} is already {value!r}")
    e[field] = value


def drop_field(m, entry_id, field):
    e = entry(m, entry_id)
    if field not in e:
        raise ValueError(f"{entry_id}: has no {field}")
    del e[field]


def delete_entry(m, entry_id):
    before = len(m["entries"])
    m["entries"] = [e for e in m["entries"] if e["id"] != entry_id]
    if len(m["entries"]) == before:
        raise KeyError(f"no entry {entry_id!r} to delete")


def add_entry(m, new):
    if any(e["id"] == new["id"] for e in m["entries"]):
        raise ValueError(f"entry {new['id']!r} already exists")
    m["entries"].append(new)


# Two sentences quoted verbatim from the corpus (pages 273 and 274 of the extent), used by
# the injections that need a real quote attached to a false claim. Both are already the
# evidence of some other entry in the map, so they are known to be locatable.
OPENING_ROLL_SENTENCE = (
    "The game is commenced by each player throwing on the centre of the board a single die, "
    "the higher throw of the two giving the right to begin."
)
LEGAL_DESTINATION_SENTENCE = (
    "The right to move is subject to a certain qualification--viz., that a man can only be "
    "played to a point which is either vacant or occupied by one or more men of the player, "
    "or by one man only of the adversary."
)


INJECTIONS = [
    # --- controls -----------------------------------------------------------------------
    dict(
        id="control-unmodified",
        family="control",
        applies=BOTH,
        stratum=None,
        wrong="Nothing is wrong. This run establishes that every detector is green before "
              "any injection, so that a detector already red cannot be counted as a catch.",
        patch=lambda m, copy: None,
    ),
    dict(
        id="control-harmless-note",
        family="control",
        applies=BOTH,
        stratum=None,
        wrong="Nothing is wrong. A `note` is reworded without changing any claim; a "
              "detector that fires here is a false positive.",
        patch=lambda m, copy: set_field(
            m, "men-count", "note",
            (entry(m, "men-count").get("note") or "") + " Reworded; no claim changed."),
    ),

    # --- citations ----------------------------------------------------------------------
    # Thirteen of twenty-four citations were wrong in this map and survived a mapping
    # trial, a build and a review (issue #18). This is the largest real family.
    dict(
        id="cite-page-off-by-one",
        family="wrong citation",
        modelled="issue #18 -- 13 of 24 citations named the wrong page",
        applies=BOTH,
        stratum="corpus",
        invalid="Not an error under this project's own rule, and the run is what established "
                "that. move-by-pip's evidence straddles the 273/274 break, and "
                "check-locators.py's `pages_spanned` accepts any page a quote touches, on the "
                "stated ground that citing either is honest. The injection is kept, and "
                "excluded from the denominator, because discovering it is a result: an "
                "injected error has to be checked against the definition of error the project "
                "actually holds, not against the injector's intuition.",
        wrong="move-by-pip's rule sentence is on p. 273; the citation now names p. 274, "
              "which is where the span's worked example continues.",
        patch=lambda m, copy: set_page(m, "move-by-pip", 273, 274),
    ),
    dict(
        id="cite-page-distant",
        family="wrong citation",
        modelled="issue #18",
        applies=BOTH,
        stratum="corpus",
        wrong="win-condition is stated in Bearing off the Men; the citation now names a "
              "page in The Board and Men, five pages earlier, which does not contain it.",
        patch=lambda m, copy: set_page(m, "win-condition", 276 if copy == FACTORY else 275, 271),
    ),
    dict(
        id="cite-wrong-section-right-page",
        family="wrong citation",
        modelled="issue #18",
        applies=BOTH,
        stratum="corpus",
        wrong="p. 274 falls inside Playing. The citation now names Bearing off the Men, a "
              "section that begins a page later, so the citation contradicts itself.",
        patch=lambda m, copy: set_section(
            m, "legal-destination", "Playing", "Bearing off the Men"),
    ),
    dict(
        id="cite-page-plausible-neighbour",
        family="wrong citation",
        modelled="issue #18",
        applies=BOTH,
        stratum="corpus",
        wrong="direction-of-travel's sentence is on p. 273. p. 274 is the next page of the "
              "same section, which is what makes this the error a careless mapper makes.",
        patch=lambda m, copy: set_page(m, "direction-of-travel", 273, 274),
    ),

    # --- evidence -----------------------------------------------------------------------
    dict(
        id="evidence-summarised",
        family="unusable evidence",
        modelled="issue #18 -- evidence held a summary, so no citation was checkable",
        applies=(FACTORY,),  # the engine copy still holds summaries here; see README
        stratum="corpus",
        wrong="`evidence` is meant to hold the corpus's words. Replaced by a summary of "
              "what they show, which is the state the whole map was in before #18.",
        patch=lambda m, copy: set_evidence(m, "men-count", "Both figures."),
    ),
    dict(
        id="evidence-adjacent-sentence",
        family="wrong evidence",
        modelled="MAP-FINDINGS.md finding 10 -- throw-two-dice's evidence described a "
                 "game nobody plays",
        applies=(FACTORY,),  # the engine copy still holds summaries here; see README
        stratum="human",
        wrong="throw-two-dice is about every throw after the opening. Its evidence is now "
              "opening-roll's sentence: verbatim, on the cited page, and about the one "
              "throw this entry does not govern.",
        patch=lambda m, copy: set_evidence(m, "throw-two-dice", OPENING_ROLL_SENTENCE),
    ),
    dict(
        id="evidence-truncated",
        family="wrong evidence",
        applies=(FACTORY,),  # the engine copy still holds summaries here; see README
        stratum="human",
        wrong="legal-destination names three permitted destinations. The evidence is cut "
              "after the first, so the quote is still verbatim and still on the cited "
              "page while supporting a third of the rule the entry states.",
        patch=lambda m, copy: truncate_evidence(
            m, "legal-destination", "which is either vacant"),
    ),

    # --- relations ----------------------------------------------------------------------
    # Six incomplete dependsOn lists and two missing gatedBy: the largest family the build
    # itself found (MAP-FINDINGS.md findings 6, 7, 8).
    dict(
        id="depends-dropped",
        family="incomplete dependsOn",
        modelled="MAP-FINDINGS.md finding 8 -- five dependsOn lists were incomplete",
        applies=BOTH,
        stratum="human",
        wrong="move-by-pip consumes a throw. Dropping throw-two-dice from its dependsOn "
              "puts it before the rule that produces its input.",
        patch=lambda m, copy: drop_edge(m, "move-by-pip", "dependsOn", "throw-two-dice"),
    ),
    dict(
        id="depends-spurious",
        family="wrong dependsOn",
        applies=BOTH,
        stratum="human",
        wrong="Hitting a blot has nothing to do with doublets; the edge orders work that "
              "has no ordering constraint and, in a large map, serialises it wrongly.",
        patch=lambda m, copy: add_edge(m, "blot-hit", "dependsOn", "doublets"),
    ),
    dict(
        id="depends-cycle",
        family="wrong dependsOn",
        applies=BOTH,
        stratum="schema",
        wrong="starting-position already depends on point-designations. The reverse edge "
              "makes the pair mutually dependent, so no implementation order exists.",
        patch=lambda m, copy: add_edge(
            m, "point-designations", "dependsOn", "starting-position"),
    ),
    dict(
        id="depends-dangling",
        family="wrong dependsOn",
        applies=BOTH,
        stratum="schema",
        wrong="Names an entry the map does not carry -- the shape a rename or a typo "
              "leaves behind.",
        patch=lambda m, copy: add_edge(m, "win-condition", "dependsOn", "bearing-off-order"),
    ),
    dict(
        id="gate-dropped",
        family="missing gatedBy",
        modelled="MAP-FINDINGS.md findings 6 and 7 -- two missing gates, one of them with "
                 "a determinism consequence no correctness test would see",
        applies=BOTH,
        stratum="human",
        wrong="bearing-off-highest is reachable only once the player is eligible to bear "
              "off. Without the gate the rule appears to apply from the first throw.",
        patch=lambda m, copy: drop_edge(
            m, "bearing-off-highest", gate_field(m, "enabledBy"), "bearing-off-eligible"),
    ),
    dict(
        id="gate-spurious",
        family="wrong gatedBy",
        applies=BOTH,
        stratum="human",
        wrong="The opening roll happens before any man can be on the bar, so gating it by "
              "enter-from-bar asserts a phase relation the corpus makes impossible.",
        patch=lambda m, copy: add_edge(
            m, "opening-roll", gate_field(m, "suspendedBy"), "enter-from-bar"),
    ),

    # --- classification -----------------------------------------------------------------
    dict(
        id="kind-operation-to-value",
        family="wrong kind",
        applies=BOTH,
        stratum="human",
        wrong="move-by-pip transforms a position given a throw. Typed `value` it claims to "
              "be a fact the corpus states, and the correspondence table treats it as one.",
        patch=lambda m, copy: set_field(m, "move-by-pip", "kind", "value"),
    ),
    dict(
        id="kind-assertion-to-value",
        family="wrong kind",
        modelled="MAP-FINDINGS.md finding 9 -- a delegated standard typed as an ordinary "
                 "value, with the entry's own note contradicting its fields",
        applies=BOTH,
        stratum="human",
        wrong="The multiple is vested in the players by agreement. Typed `value` the "
              "engine owes it none of the four things an assertion is owed -- demand, "
              "attribution, recording, never infer.",
        patch=lambda m, copy: set_field(m, "agreed-backgammon-multiple", "kind", "value"),
    ),
    dict(
        id="clarity-ambiguous-to-clear",
        family="wrong clarity",
        modelled="MAP-FINDINGS.md finding 4 -- game-value was `clear` and a reachable win "
                 "satisfies none of its three named results",
        applies=BOTH,
        stratum="human",
        wrong="Restores the exact error trial 4 found: the entry asserts the corpus "
              "determines one answer for every input, and a reachable finish has none.",
        patch=lambda m, copy: (set_field(m, "game-value", "clarity", "clear"),
                               drop_field(m, "game-value", "ambiguity")),
    ),
    dict(
        id="clarity-clear-to-ambiguous",
        family="wrong clarity",
        applies=BOTH,
        stratum="human",
        wrong="bearing-off-highest is determinate -- a number that cannot be used bears a "
              "man off the highest occupied point. Declaring it unresolved declines a rule "
              "the corpus settles, which is the more expensive direction of this error.",
        patch=lambda m, copy: (
            set_field(m, "bearing-off-highest", "clarity", "ambiguous"),
            set_field(m, "bearing-off-highest", "ambiguity", {
                "question": "The corpus does not say which point counts as highest when "
                            "men stand above the point the number names.",
                "fate": "unresolved",
                "unresolvedReason": "RequiresInterpretation",
            })),
    ),
    dict(
        id="clarity-inconsistent",
        family="wrong clarity",
        applies=BOTH,
        stratum="schema",
        wrong="`clarity: clear` and an `ambiguity` block assert opposite things about the "
              "same entry.",
        patch=lambda m, copy: set_field(m, "game-value", "clarity", "clear"),
    ),

    # --- status and scope ---------------------------------------------------------------
    dict(
        id="scope-in-to-out",
        family="wrong scope",
        applies=BOTH,
        stratum="human",
        wrong="legal-destination is the general qualification on every move in the game. "
              "Marked out of scope, the map says an engine need not implement it and the "
              "correspondence table says the engine should decline citing it.",
        patch=lambda m, copy: (set_field(m, "legal-destination", "scope", "out"),
                               set_field(m, "legal-destination", "status", "declined")),
    ),
    dict(
        id="status-claimed-without-revision",
        family="wrong status",
        applies=(FACTORY,),
        stratum="schema",
        wrong="Claims an entry is implemented without naming the ruleset and revision that "
              "implements it, so the claim names nothing that could be checked.",
        patch=lambda m, copy: set_field(m, "men-count", "status", "implemented"),
    ),

    # --- entries present and absent -----------------------------------------------------
    dict(
        id="entry-deleted-unreferenced",
        family="missing entry",
        modelled="issue #20 -- four unmapped rules, including the corpus's only statement "
                 "of how many faces a die has",
        applies=(FACTORY,),
        stratum="corpus",
        wrong="Deletes die-faces, the corpus's only authority for a die having six faces. "
              "Nothing in the map references it, so its absence leaves no dangling edge.",
        patch=lambda m, copy: delete_entry(m, "die-faces"),
    ),
    dict(
        id="entry-deleted-referenced",
        family="missing entry",
        modelled="issue #20",
        applies=BOTH,
        stratum="schema",
        wrong="Deletes point-designations, which three other entries depend on.",
        patch=lambda m, copy: delete_entry(m, "point-designations"),
    ),
    dict(
        id="entry-fabricated-unquotable",
        family="fabricated entry",
        applies=BOTH,
        stratum="corpus",
        wrong="An entry for a rule the corpus does not contain, with evidence that is not "
              "in the corpus at all -- a mapper writing from knowledge of the game.",
        patch=lambda m, copy: add_entry(m, {
            "id": "borne-off-men-do-not-re-enter",
            "name": "A man once borne off may not re-enter the game",
            "locator": {"sourceId": "hoyle-1909",
                        "citation": "BACKGAMMON / Bearing off the Men / p. 275"},
            "kind": "operation", "scope": "in", "clarity": "clear", "dependsOn": [],
            "evidence": "A man once borne off may not re-enter the game.",
            "status": "mapped",
        }),
    ),
    dict(
        id="entry-fabricated-real-quote",
        family="fabricated entry",
        modelled="an entry claiming a case the corpus does not state (issue #31)",
        applies=BOTH,
        stratum="human",
        wrong="Backgammon has no compulsion to hit. The entry states one, and cites a real "
              "sentence of the corpus, on the page it is really on, which says something "
              "else -- so every mechanical check the citation faces is satisfied.",
        patch=lambda m, copy: add_entry(m, {
            "id": "blot-must-be-hit",
            "name": "A blot must be hit if the throw permits it",
            "locator": {"sourceId": "hoyle-1909",
                        "citation": "BACKGAMMON / Playing / p. 274"},
            "kind": "operation", "scope": "in", "clarity": "clear",
            "dependsOn": ["blot-hit"],
            "evidence": LEGAL_DESTINATION_SENTENCE,
            "status": "mapped",
        }),
    ),

    # --- reach and absence --------------------------------------------------------------
    dict(
        id="beyond-adapter-false",
        family="false unreachability",
        modelled="MAP-FINDINGS.md finding 1 -- the map's worst real error, and the one that "
                 "motivated a schema field, a decision record and an engine's architecture",
        applies=BOTH,
        stratum="human",
        wrong="Restores it exactly: starting-position declared unreadable by the "
              "plain-text adapter because it is in a figure, while the entry's own "
              "evidence is the prose statement of it, verbatim, on the cited page.",
        patch=lambda m, copy: (
            set_field(m, "starting-position", "status", "declined"),
            set_field(m, "starting-position", "beyondAdapter",
                      {"adapter": "plain-text", "modality": "illustration"})),
    ),
    dict(
        id="absence-terms-present",
        family="false absence",
        modelled="issues #20 and #29 -- an absence declared without looking",
        applies=(FACTORY,),
        stratum="corpus",
        wrong="Claims the corpus contains no doubling rule and searches for a term the "
              "corpus does use, for another reason, inside the declared extent.",
        patch=lambda m, copy: set_field(m, "doubling-cube", "absentFrom", {
            "searched": ["doubling", "double", "redouble", "offer to double"]}),
    ),
    dict(
        id="absence-stated-in-other-words",
        family="false absence",
        modelled="check-locators.py's own stated limitation, here made a measurement "
                 "rather than a claim",
        applies=(FACTORY,),
        stratum="human",
        wrong="Claims the corpus contains no rule for taking an adversary's man, and "
              "searches for words the corpus does not use. It states the rule throughout, "
              "in its own vocabulary -- a blot is 'taken up'.",
        patch=lambda m, copy: add_entry(m, {
            "id": "capture-rule-absent",
            "name": "Capturing an adversary's man",
            "locator": {"sourceId": "hoyle-1909",
                        "citation": "BACKGAMMON / Playing / p. 274"},
            "kind": "operation", "scope": "out", "clarity": "clear", "dependsOn": [],
            "evidence": LEGAL_DESTINATION_SENTENCE,
            "status": "declined",
            "note": "The corpus does not state what happens to an adversary's man that is "
                    "landed on. The sentence cited is where the rule would be.",
            "absentFrom": {"searched": ["capture", "captured", "seize", "prisoner"]},
        }),
    ),

    dict(
        id="absence-in-unused-words",
        family="false absence",
        probe="Designed to evade, and reported apart from the rate for that reason. "
              "absence-stated-in-other-words was meant to test check-locators.py's stated "
              "limitation -- that a term absent from the extent is not a rule absent from "
              "the extent -- and failed to, because the corpus does use 'capture' once, in "
              "the very passage that states the rule. This one searches for four terms "
              "verified absent from pages 271-280, which is the limitation itself, "
              "measured rather than assumed. A probe chosen to slip past a check is not a "
              "sample of anything, so it is not counted in the miss rate.",
        modelled="check-locators.py's own stated limitation",
        applies=(FACTORY,),
        stratum="human",
        wrong="Same false claim as absence-stated-in-other-words -- the corpus states the "
              "rule, at length, on p. 274 -- with searched terms the corpus does not use.",
        patch=lambda m, copy: add_entry(m, {
            "id": "capture-rule-absent",
            "name": "Capturing an adversary's man",
            "locator": {"sourceId": "hoyle-1909",
                        "citation": "BACKGAMMON / Playing / p. 274"},
            "kind": "operation", "scope": "out", "clarity": "clear", "dependsOn": [],
            "evidence": LEGAL_DESTINATION_SENTENCE,
            "status": "declined",
            "note": "The corpus does not state what happens to an adversary's man that is "
                    "landed on. The sentence cited is where the rule would be.",
            "absentFrom": {"searched": ["captured", "capturing", "seize", "prisoner"]},
        }),
    ),

    # --- the claim itself ---------------------------------------------------------------
    dict(
        id="name-contradicts-corpus",
        family="entry contradicts corpus",
        applies=BOTH,
        stratum="human",
        wrong="The corpus says twelve points to a table, twenty-four in all. The entry now "
              "says fourteen, above a verbatim quote that says otherwise -- the number the "
              "whole engine is built around, wrong in the field a reader reads first.",
        patch=lambda m, copy: (
            set_field(m, "board-tables", "name",
                      "The board is two tables of fourteen points each"),
            set_field(m, "board-tables", "note",
                      "Each table carries fourteen points, seven at either end, so the "
                      "course is twenty-eight points long.")),
    ),
]


def by_id(injection_id):
    for inj in INJECTIONS:
        if inj["id"] == injection_id:
            return inj
    raise KeyError(injection_id)
