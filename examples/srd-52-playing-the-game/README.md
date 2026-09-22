# Trial 12 — SRD 5.2.1, *Playing the Game* pp. 5–12

The third slice of one corpus, and the first chosen because two committed maps already point
into it.

Trial 7 mapped [Combat](../srd-52-combat/) (pp. 13–16) and trial 8 the
[fifteen conditions](../srd-52-conditions/) (Rules Glossary, pp. 177–191). Both use *D20 Test*,
*ability check*, *Advantage*, *Disadvantage* and *Proficiency Bonus*, and both read past the
chapter that defines them. That chapter is **Playing the Game, pp. 5–18** — not pp. 5–23, which
an early scoping note had; *Character Creation* opens on p. 19.

This slice is **pp. 5–12**, from *Rhythm of Play* to the end of *Travel*, ending where Combat
begins on p. 13. It is contiguous, which the `page` unit requires. The rest of the chapter —
*Damage and Healing* through *Temporary Hit Points*, pp. 16–18 — cannot be declared under the
schema as it stands, because a page extent has no `startsAfter` and a map of pp. 16–18 would
claim the combat half of p. 16 it did not read
([#434](https://github.com/brandonifco/rules-factory/issues/434)).

Filed as [#433](https://github.com/brandonifco/rules-factory/issues/433). Nothing is built from
the map.

| | |
|---|---|
| Corpus | SRD 5.2.1, CC-BY-4.0, the same pinned `srd-5.2.1.txt` trials 7 and 8 read |
| Extent | `{"unit": "page", "from": 5, "to": 12, "quoted": 0.85}` |
| Entries | 91 — 80 in scope, 11 declined |
| Kinds | 43 `value`, 40 `operation`, 8 `assertion` |
| Ambiguous | 4 of 80 in scope (5%) |
| Relations | 92 `dependsOn` edges, no cycle; **no gate** — `enabledBy` and `suspendedBy` are empty |
| Pointers | 195 `crossReferences`, 40 of them `unmapped`; 199 namings of a defined term, every one declared |
| Vocabulary | `playing-the-game-terms`, 55 terms distributed over 18 entries (0045) |
| Extraction | 12 `interleaved-table`, 3 `split-by-sidebar` |
| Inventory | 374 units, 300 reached, 74 rejected, 0 unaccounted — measured at 268/78/28 when the trial ran, all of it [#437](https://github.com/brandonifco/rules-factory/issues/437) |
| Review | none; `exemption`, first mapping, [review.json](review.json) says what a second reading should look at |

## The hypotheses, before anything was mapped

They are in [#433](https://github.com/brandonifco/rules-factory/issues/433), written before the
first entry existed, which is the practice [#262](https://github.com/brandonifco/rules-factory/issues/262)
established. What each one did:

### H1 — a page grammar cannot cite a table row. **Held, and it cost more than predicted.**

Eleven tables are printed inside the slice and seven of them state rules an engine answers with.
`heading-path-and-printed-page` addresses a page and a heading line, and
[0035](../../docs/decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md) gave a row a
citation only in the `section-designation` grammar
([#265](https://github.com/brandonifco/rules-factory/issues/265) left the page grammars alone).
So every table here is **one entry**, whatever it holds:

| Entry | Rows | What a row states |
|---|---:|---|
| [`skills-table`](corpus-map.json) | 18 | which ability a skill's checks use |
| `actions-table` | 12 | what an action does |
| `ability-modifier-table` | 16 | the modifier a score band yields |
| `proficiency-bonus-table` | 8 | the bonus a level or CR yields |
| `ability-descriptions-table` | 6 | the six abilities |
| `attack-roll-abilities-table` | 3 | which modifier an attack type uses |
| `travel-pace-table` | 3 | distance per minute, hour and day |

Three consequences, and only the first was predicted.

**A rule-bearing column and an advisory one share a citation.** The Skills table's *Ability*
column binds and its *Example Uses* column does not, and no citation can name one and not the
other. The two are in one span, in one entry, with one `scope`. The map says so in a note,
which is the weakest place it could say it.

**Three rules the corpus states only in a row could be separated, and only because their text
differs.** `score-floor`, `score-cap-adventurer` and `score-cap-absolute` are three rows of the
Ability Scores table and carry one citation between them, `Playing the Game / Ability Scores /
p. 5`. They are told apart by their quotes alone — each opens with its row's key, `1`, `20`,
`30` — which works here and would not work for a table whose rows repeat, and that is exactly
what [0030](../../docs/decisions/0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md)
replaced.

**The protocol can say `table-row` and the citation cannot.** `mapping-protocol.json` declares
`table-row` among its units, which is true of the corpus — the Skills table states eighteen
rules in eighteen rows — and the grammar has no address for one. The two halves of the mapper
subsystem disagree about what this corpus's units are, and nothing holds them to each other.

### H2 — the heading path cannot narrow *Round Down*. **Held, and sharper than predicted.**

The rule is printed identically on p. 5 and p. 187. The run says it plainly:

```
round-down: the corpus prints this quote 2 times (p. 5, p. 187), and the heading path
'Playing the Game / Round Down' selects 2 of them; the citation does not identify one
passage, and this checker does not guess which was meant (0030)
```

The prediction was that this slice could not cite its own printing. What the run shows is
structural and more general: **every heading above the p. 5 printing is also above the p. 187
one, because p. 5 comes first.** The heading path can disambiguate the *later* of two identical
printings and never the earlier. 0030's own worked example is the later one.

Two things follow, both filed as [#436](https://github.com/brandonifco/rules-factory/issues/436).
The entry is withdrawn from this map and recorded in
[`mapping-inventory.json`](mapping-inventory.json) under ground `restatement`, which is the
closest of seven and **is not the true reason** — none of `advice`, `preamble`, `heading`,
`page-furniture`, `restatement`, `out-of-extent`, `beyond-adapter` means *no citation this
grammar can write identifies this passage*. `Inventory.unaddressable` means exactly that, for
the other grammar, via [0036](../../docs/decisions/0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md).

And the combat map's own `round-down` — `scope: out`, same citation — passes today only because
its `evidence` ends with a `{6}` page marker the rule does not contain, with a note saying the
marker is there to make the quote unique. That is span-extension for uniqueness, which 0030
retired and calls "not a fallback". No map of this corpus holds Round Down in scope.

### H3 — nothing joins two maps of one corpus. **Held.**

`heavily-obscured` is the clean case. The rule is *"You have the Blinded condition (see "Rules
Glossary") when trying to see something there"*, and it is complete only with the Blinded
condition — which **is** mapped, by trial 8, over the same pinned bytes, as `blinded`.
`resolvedBy` holds an id in this map, so the pointer can only be recorded as `unmapped` with a
sentence saying where the answer is. Fifteen of this map's 40 `unmapped` references point into
the Rules Glossary, and trial 8's slice covers those pages.

The manifest is restated a third time, and nothing compares the three copies — trial 8's
finding, unchanged. `corpus-manifest.json` here is trial 8's file, `committedPath` and all, and
the only thing holding the three together is that `validate-repo.py` now lists
`examples/srd-52-combat` among this map's corpora so a change to the text checks all three.

### H4 — advice and obligation are interleaved at the sentence grain. **Falsified, interestingly.**

The prediction was a higher `scope: out` share than any mapped slice. It came out at **11 of 91,
12%** — against trial 7's 26% (25 of 95) and trial 8's 34% (34 of 100). The chapter is *less*
advisory than the two slices that preceded it.

What the prediction got wrong is where the guidance lives. It is not interleaved at the sentence
grain: it is in whole named sections — *Roleplaying*, *Social Interaction*, *Adventuring
Equipment*, *Marching Order* — each declined as one entry quoting its opening. `scope` excludes
an entry and not a sentence, and that cost nothing here, because the corpus had already done the
separating.

The real cost landed somewhere the hypothesis did not look: **eight assertions**, 9% of the map — behind
trial 1's 21% and level with trial 11's 10%, and against 3%, 3%, 0%, 0% and 1% on the other five. `check-difficulty-class`,
`heroic-inspiration-award`, `improvised-actions`, `hiding`, `carrying-objects` and
`travel-is-summarised-or-paced` each record a judgement the corpus hands a person outright. The
GM's say is not vagueness to be resolved and it is not advice to be dropped; it is a parameter,
and trial 1's `kind: assertion` is what carries it. That the chapter needed eight of them, and
only four ambiguities, is the finding H4 should have been about.

### H5 — the inventory cannot be closed from the first mapping. **Held, for the wrong reason.**

28 of 374 units are unaccounted. H1 was named as the cause and is not: every table is quoted
whole and every table's units are reached.

The cause is [#437](https://github.com/brandonifco/rules-factory/issues/437), a defect this trial
found. `PageMarkedPdfText` overrides the marker pattern with a line-anchored `^\{(\d+)\}$`, and
`unmarked()` — which exists so a quote straddling a page turn can be searched against units that
carry no marker — applies it to a map's `evidence`, where whitespace is already collapsed and no
anchor can hold. The substitution never fires, the quote never matches, and the entry is reported
not located. Three entries here quote across a page turn, `actions-table`, `roleplaying` and
`object-interaction-is-narrative`, and the 28 units they reach go to the unaccounted pile — the
whole twelve-row Actions table among them. `check-locators-pdf-text.py` locates all three
without complaint. **Two readers of the same map disagree about the same bytes**, and
*unaccounted* is the inventory's word for *nobody looked*.

#437 is fixed and this pile closes: 300 reached, 74 rejected, 0 unaccounted. The map's own bytes
are untouched — [0017](../../docs/decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)
would have invalidated its review — and what changed is the tool and four lines of
[mapping-inventory.json](mapping-inventory.json). Those four rejected the Actions table's column
headers on both sides of the turn, `Actions Action` / `Summary` on p. 9 and `Action` / `Summary`
on p. 10, as table headings that state no rule. `actions-table` quotes all four. A reader that
cannot see the quote cannot see the contradiction, so the walk recorded a verdict about a passage
its own map had already reached; the rejections are gone rather than reworded, because a passage
cannot have produced no entry and be the evidence for one.

So H5's answer is narrower than the heading says. The inventory *was* closable from this first
mapping, and nothing about the walk was in the way. What was in the way was the measurement.

## What was not predicted at all

**An extraction can split one sentence into two entries.** Three times. The extraction's reading
order puts a whole column, a sidebar or an eighteen-row table between a sentence's halves:

| First half | What the extraction inserts | Second half |
|---|---|---|
| `advantage-disadvantage`, p. 7, ends at *"…special abilities and actions. The"* | the Heroic Inspiration sidebar and the whole Proficiency section | `advantage-granted-by-gm`, p. 8, begins at *"GM can also decide…"* |
| `skill-proficiency-bonus`, p. 8, ends at *"…can still make ability checks involving"* | the eighteen-row Skills table | `skill-proficiency-absent`, p. 9, begins at *"that skill but doesn't add…"* |

[0037](../../docs/decisions/0037-an-ellipsis-skips-whole-paragraphs-and-never-words-inside-one.md)
forbids an ellipsis inside a paragraph, and a span is contiguous, so one rule becomes two entries
on two pages — and **nothing in the map says the two are one sentence** except a note. The
`assertedBy` check found the seam on its own: `advantage-granted-by-gm` must name its party as
`GM` and not `the GM`, because the article is printed on the page before.

**A run-in heading is not a heading this grammar can name.** The SRD sets *Only One Base AC*,
*Only One at a Time* and *Gaining Heroic Inspiration* in bold at the head of a paragraph, with
the rule's first sentence continuing on the same line, and `pdftotext` gives them no line of
their own — so the heading path cannot name the level the corpus states many of its rules at.
Three citations were flattened to the section above them, and two entries now share one citation.
Filed as [#435](https://github.com/brandonifco/rules-factory/issues/435), with the same shape as
H1: the grammar addresses a page and a line, and this corpus has a level below both.

**The corpus numbers a three-step procedure 4, 5, 6.** The D20 Test steps continue the numbering
of the Rhythm of Play list two pages earlier. The rendered page was read to confirm it is the
corpus's own and not an extraction defect, and the map records the corpus's numbering.

**A vocabulary of 55 terms costs 199 declarations.** `defined-term-use` reads a distributed
vocabulary (0045) because the SRD's index — the Rules Glossary — is outside the slice, which is a
shape 0045 was decided for a corpus that prints *no* index at all. Every naming of a term outside
its defining passage owes a `crossReferences` item to every entry that defines it (0044, 0058),
and there are 199 of them across 48 entries. They were generated from the same detector that
obliges them; what a mapper decided is which terms the vocabulary holds, and the 138 that were
added mechanically are named in [review.json](review.json) as something a second reading should
check.

Which is where [#422](https://github.com/brandonifco/rules-factory/issues/422) got measured.
*Attack*, *Dodge* and *Influence* are actions the corpus defines **and** ordinary words it uses:
*"Attack rolls usually occur in battle"* at the head of a sentence, the column header *"Attack
Type"*, the *"Opportunity Attack"* that contains the word, and *"Dodge out of harm's way"* and
*"Influence, entertain, or deceive"* in two tables of examples. Three mechanisms, five false
namings in 144. The detector cannot tell them apart, `unmapped` does not satisfy it, and the only
move available is to leave the terms out of the vocabulary — which loses one true naming, in
`one-action-at-a-time`. The map takes that trade and says so.

## What this slice can and cannot answer

It holds the arithmetic the other two slices assume: the six abilities, the modifier table, the
D20 Test and its three kinds, `>=` as the success test, Advantage and its cancellation, the
Proficiency Bonus and its two stacking rules, the eighteen skills and the twelve actions.

It cannot answer what any of the named things outside it mean. Four special senses, five hazards,
three NPC attitudes, the Blinded condition, a Short or Long Rest, a character's level, a
monster's Challenge Rating: each is a closed list this map holds and cannot resolve. That is the
engine's honesty working as designed — and, for the Rules Glossary at least, it is a boundary
between two maps of one corpus rather than a boundary of the corpus.

**No entry carries a gate.** 92 `dependsOn` edges and not one `enabledBy` or `suspendedBy`, which
is the right outcome for a chapter with no turn structure: the turn is in Combat, trial 7's
slice. The one rule that looks like a gate, `free-object-interaction`'s *"when time is short,
such as in combat"*, gates on a state the corpus does not define — combat is given as an instance
and not as the condition — so it is recorded in a note and not as an edge.
