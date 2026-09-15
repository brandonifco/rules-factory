# Mapper notes: blind map of srd-5.2.1, pages 13–16 ("Combat")

## What I read

- `SLICE.md`, `method.md`, `corpus-map.md`, `corpus-manifest.json`, all in full.
- `pages/p-013.png` … `pages/p-016.png`, all four, to read column order, sidebars ("Playing on a
  Grid", "Unseen Attackers and Targets", "Resting") and the Cover and Creature Size tables.
- `srd-5.2.1.txt`:
  - the extent: lines 1734–2253 (`{13}` to `{17}`), including the part of p. 16 after the slice
    ("Damage and Healing", "Resting");
  - the end of p. 12 (Travel pace, Vehicles; and the "Time-Limited Object Interactions" passage);
  - table of contents (lines 20–70) for the heading structure;
  - p. 5 "Exceptions Supersede General Rules", "Round Down"; p. 6 "D20 Tests", "Ability Checks";
    p. 7 "Saving Throws", "Attack Rolls", "Advantage/Disadvantage" opening; pp. 9–10 "Actions"
    table, "Bonus Actions", "Reactions"; p. 17 "Resistance and Vulnerability";
  - Rules Glossary entries (pp. 176–191): Advantage, Ally, Attack Roll, Attack [Action], Bonus
    Action, Climbing, Climb Speed, Cover, Crawling, Critical Hit, Dash, Disadvantage, Difficult
    Terrain, Disengage, Dodge, Enemy, Hide, Hit Points, Improvised Weapons, Incapacitated,
    Initiative, Influence, Invisible, Jumping, Occupied Space, Opportunity Attacks, Paralyzed,
    Prone, Reach, Reaction, Ready, Resistance, Round Down (glossary copy), Size, Speed, Stat Block,
    Surprise, Swimming, Swim Speed, Teleportation, Unarmed Strike, Unconscious, Unoccupied Space,
    Utilize (and whatever else fell inside those read windows);
  - `grep` over the whole file for heading lines, page markers, and for the absence terms
    (`flank`, `surprise round`, `redirect`, `supersede`, "exceptions").

## What I ran

- `sha256sum srd-5.2.1.txt` → `c55926cb…a075b100`, equal to `SLICE.md`'s `contentHash`.
- `ls`, `grep -n`, and the Read tool on bundle files only.
- `python3 out/build.py` writes `out/blind-map.json`. Evidence is **extracted** from the
  whitespace-normalised corpus text between a start and end fragment, not typed, so the quotes
  are the extraction's characters. Newline runs are stored as single spaces, which `SLICE.md`
  says the check treats as equal.
- `python3 out/check.py` is my self-check (below). Final run: 0 failures.

## Isolation

I kept to the isolation rules. Every file read, list and search was under
`/tmp/claude-1000/blind-srd52-106/bundle/`. I used no git or gh, no network, and no subagents, and
I did not look for another map. One harness detail: one compound shell command was refused
by the environment's worktree guard before it ran. It would only have read the bundle file. I
re-did it with the Read tool on the same bundle file. My process's working directory was a
worktree, and I never read, listed or wrote in it.

## Self-check (`out/check.py`) — results

All of these pass, 0 failures:

- JSON parses; top level is exactly `schemaVersion`, `corpus`, `baseline`, `extent`, `entries`; the
  baseline hash equals the file's hash; `corpus` is in the manifest.
- Every entry has `id`, `name`, `kind`, `scope`, `clarity`, `dependsOn`, `status`, `note`; values
  from the vocabularies. Located entries have `locator` + `evidence`, and derived entries have
  neither. There are no unknown fields and the ids are unique.
- `clarity: ambiguous` ⇔ an `ambiguity` block, with `fate: unresolved`,
  `unresolvedReason: RequiresInterpretation` and no decision. Conflict slug has ≥2 members sharing a fate.
- Every id in `dependsOn`, `enabledBy`, `suspendedBy`, `derivedFrom`, `crossReferences.resolvedBy`
  exists; no gate/dependency names an absent entry; no id in both gate fields; no cycles in
  `dependsOn` or `derivedFrom`; derived entries have ≥2 in-scope sources.
- Each `crossReferences.cites` occurs verbatim in its own evidence. Each has exactly one of
  `resolvedBy` and `unmapped`.
- The three citation checks from `SLICE.md`, on the raw text:
  1. the evidence occurs with whitespace runs equal;
  2. every occurrence touches page N;
  3. the last heading in the path is a line between the start of page N−1 and the quote.
  Also: every in-scope citation page lies in 13–16.
- Coverage: pages 13, 14, 15, 16 are all reached by in-scope evidence.
- Every `absentFrom.searched` term is absent from the text of pages 13–16, case-insensitive.
  I searched both the raw text and the whitespace-normalised text.
- One failure was found and fixed along the way. `round-down`'s quote occurs word for word twice,
  on p. 5 and in the glossary on p. 187, so its span now runs on to take in the `{6}` marker.
- Re-read against the renders: I compared every in-scope evidence span with the printed page, and
  the list is in the entry notes. The spans the extraction reorders are these:
  - `initiative-ties` crosses the p. 13 footer;
  - `gm-may-require-action` is the p. 14 continuation of "Your Turn", with the grid sidebar
    between it and p. 13 in the extraction;
  - `attack-structure` quotes only the p. 15 half of a sentence split by the "Unseen Attackers"
    sidebar;
  - the Cover table cells are interleaved ("Three+5 bonus to AC Quarters…"), and I read that
    table from the render.
  In each case the entry says what the page says.

I did not mutation-test `check.py` itself, beyond its having gone red once on `round-down`.

## Counts

- Entries: **121**. In scope **83**, out of scope **38**.
- Kinds (all): operation 92, value 25, assertion 4. In scope: operation 64, value 15, assertion 4
  (`combat-step-establish-positions`, `initiative-ties`, `gm-may-require-action`,
  `cover-degree-determination`).
- Clarity: clear 99, ambiguous 22 (all 22 in scope, all `fate: unresolved`). One conflict:
  `combat-continuation` (`combat-rounds-and-turns`, `combat-end-agreement`).
- Gates: 41 entries carry `enabledBy` (41 edges), 27 carry `suspendedBy` (59 edges), and 17
  distinct gating entries:
  - combat phase: `combat-rounds-and-turns`, `combat-end-defeat`, `combat-end-agreement`;
  - `grid-play` and `underwater-combat`;
  - the mount chain;
  - `incapacitated-condition`, `reaction-once` and `hide-action` (all out of scope);
  - Opportunity Attack exemptions;
  - object-interaction overrides;
  - `mount-controlled-initiative`;
  - `underwater-ranged`.
- Absences: 3 (`flanking`, `surprise-lose-turn`, `mount-target-choice`).
- Derived: 2 (`grid-diagonal-step-cost`, `pass-through-costs-extra`).
- crossReferences: 20 (17 resolvedBy, 3 unmapped).
- Out-of-scope breakdown:
  - 31 rules outside the extent that entries depend on or are gated by (pp. 5, 6, 7, 9, 10, 17
    and the Rules Glossary);
  - 1 on p. 16 after the slice's end (`damage-rolls`);
  - 3 declined non-rules (`combat-intro`, `doing-nothing-advice`, `grid-speed-advice`);
  - 3 absences.

## Where the method or specification was unclear for this corpus, and what I did

1. **Who is the caller in a tabletop game.** The method's worked assertions are about a
   regulated operator. It also says a third party whose determination is a separate act is "not a
   caller assertion". Here many rules make the Game Master's determination operative. I treated
   the GM (and the players) as the engine's caller, not as a third party: the engine serves the
   table, and the corpus makes the GM the one who "determines target numbers". So a GM
   determination with a stated measure or a fixed set is `kind: assertion` (4 entries). The
   other reading would make those four entries gaps or parameters. This is the choice I would
   most expect a second mapper to make differently.
2. **Partial gates.** `enabledBy` and `suspendedBy` are entry-level, but several gates here reach
   only part of an entry or only one combatant:
   - Incapacitated removes the action but not the move in `turn-move-and-action`;
   - `mount-controlled-initiative` departs from "the Initiative order remains the same" for the
     mount only;
   - `underwater-ranged` replaces the long-range rule for weapons only.
   Where the gate reaches the whole rule for the affected case, I recorded it and explained the
   reach in `note`. Where it reaches only a sub-part (Incapacitated on
   `turn-move-and-action`; Speechless on `communicate-brief`), I did not record it, and said so
   in the note. A finer split would remove the problem.
3. **What enables "combat".** Whether combat has started is a fact the caller supplies, so it has
   no entry. I used the rule that organises combat into rounds and turns
   (`combat-rounds-and-turns`) as the `enabledBy` gate on every turn- or round-scoped entry. The
   two Ending Combat rules are `suspendedBy` on the same set, named on each entry because gates
   are not inherited. I did not gate Movement, Attack or Cover rules that do not mention a turn,
   because nothing in their text confines them to combat.
4. **One pointer, several targets.** `crossReferences.resolvedBy` names a single id. "climbing,
   crawling, jumping, and swimming (each explained in 'Rules Glossary')" points at four entries, so
   I declared four items, each citing a substring of the evidence.
5. **The closed pointer-phrase list** that `check-map.py` uses is not in the bundle. I declared
   crossReferences for every "see …", "(see the next section)", "listed in", "detailed earlier
   in", "explained in", "as stated in", "as noted in" and "as shown on" in in-scope evidence, and
   for "later in 'Playing the Game'". I did not declare them for glossary-term mentions with no
   pointer phrase, such as "the Utilize action" or "the Influence action", which I handled by
   `dependsOn` or `note`.
6. **Heading levels for sidebars.** "Playing on a Grid" and "Unseen Attackers and Targets" are
   sidebars. I put them in the path under the section they print beside ("The Order of Combat",
   "Making an Attack"). Only the last heading is checked.
7. **Table captions as headings.** "Cover" and "Creature Size and Space" are also table captions
   on their own line. I cited the section heading, not the caption.
8. **Whether an out-of-scope entry may cite a page inside the extent's range but outside the
   slice.** `damage-rolls` is on p. 16, after the slice's end. The specification only speaks of
   citing *beyond* the extent. I marked it `scope: out` with the reason in `note`, and used
   no in-scope evidence from that part of p. 16.
9. **Kind on out-of-scope and absent entries.** The specification requires `kind` on every entry
   but gives no guidance for declined non-rules. I gave declined prose and advice `value`, and gave
   absences the kind the rule would have had.
10. **Intro sentences that read like triggers.** "If you move heedlessly past your foes, you put
    yourself in danger by provoking an Opportunity Attack" is worded as a condition but differs
    from the stated trigger. I mapped it as an ambiguous in-scope entry rather than declining it
    as prose. That is a judgement call.
11. **Overlapping spans.** `combat-round-duration` quotes a sentence inside
    `combat-rounds-and-turns`' span. `cover-degree-determination` quotes the "Offered By" cells
    inside `cover-degree-benefits`' span, because the extraction interleaves the two columns and a
    contiguous span of one column is not possible. `flanking` (absent) quotes the same step as
    `attack-determine-modifiers`, and `mount-target-choice` overlaps the Controlling a Mount
    entries.
12. **Assertions carrying an ambiguity.** Nothing in the specification excludes it. Three
    assertions have a stated measure or set but also an unfixed case, so I gave them both. Two
    examples: players who disagree on a tie, and whether "that covers at least half" also
    qualifies "another creature".

## Where prior knowledge pulled at a reading

- `combat-round-duration`: "10 rounds = 1 minute". The text says "about 6 seconds", and I left it
  open.
- `move-through-space`: an earlier edition's "at least two sizes", and "can't move through a
  hostile creature's space". The text says "two sizes larger or smaller" and states only
  permissions. Recorded as ambiguous.
- `grid-ranges` and `grid-speed-squares`: habits of "diagonals count 5 feet, obstacles ignored"
  and "round Speed down to squares". The text is silent, so both are ambiguous.
- `initiative-group-roll`: "identical" meaning "same stat block". Not stated.
- `initiative-surprise`: the pull to "surprised creatures lose their first turn". It is not in this
  text, and it prompted the absence `surprise-lose-turn`.
- `flanking` and `mount-target-choice`: both absences exist only because I know rules like them
  from elsewhere in the game's history. The searches confirm the extent does not state them. The
  choice of what to search for is prior knowledge, and I say so in each note.
- Opportunity Attacks: I know the glossary wording ("leaves your reach using its action, its Bonus
  Action, its Reaction, or one of its speeds"). I read it in the bundle, and I did not import it
  into the in-scope entries.
- Cover, Half row: the familiar reading is that any creature gives Half Cover. The text's
  attachment of "that covers at least half" is ambiguous, and I recorded it.

## Files written

- `/tmp/claude-1000/blind-srd52-106/bundle/out/blind-map.json`
- `/tmp/claude-1000/blind-srd52-106/bundle/out/build.py`
- `/tmp/claude-1000/blind-srd52-106/bundle/out/check.py`
- `/tmp/claude-1000/blind-srd52-106/bundle/out/MAPPER-NOTES.md`
