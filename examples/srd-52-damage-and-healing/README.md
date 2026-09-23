# SRD 5.2.1, *Damage and Healing* pp. 16–18 — the rest of the chapter

Not a numbered trial. A trial exists to change the method
([examples/README.md](../README.md)), and this run was not chosen to break anything: it is the
half of *Playing the Game* that [trial 12](../srd-52-playing-the-game/) could not declare, mapped
as soon as the schema could say where it starts.

Trial 7 mapped [Combat](../srd-52-combat/), pp. 13–16, and stopped halfway down p. 16 at the
*Damage and Healing* heading. Trial 12 mapped pp. 5–12. What was left began at that same line, and
a page extent had no way to say so: `{"from": 16, "to": 18}` would have claimed the combat half of
p. 16 that trial 7 read ([#434](https://github.com/brandonifco/rules-factory/issues/434)).
[0064](../../docs/decisions/0064-a-page-extent-can-start-after-a-heading-and-the-heading-joins-two-maps.md)
gave the extent `startsAfter`, and this is the first committed map to declare one:

```json
"extent": { "unit": "page", "from": 16, "to": 18, "startsAfter": "Damage and Healing", "quoted": 0.72 }
```

The *Playing the Game* chapter is now mapped end to end, across three maps and one line that
belongs to none of them.

Nothing is built from the map yet. It is packable, which is the first thing a composed engine over this corpus needs.

| | |
|---|---|
| Corpus | SRD 5.2.1, CC-BY-4.0, the same pinned `srd-5.2.1.txt` trials 7, 8 and 12 read |
| Extent | `{"unit": "page", "from": 16, "to": 18, "startsAfter": "Damage and Healing", "quoted": 0.72}` |
| Entries | 42 — 40 in scope, 2 declined |
| Kinds | 24 `operation`, 17 `value`, 1 `assertion` |
| Ambiguous | 1 of 40 in scope (3%) — `bloodied`, ruled on by [0065](../../docs/decisions/0065-bloodied-is-measured-against-the-hit-point-maximum.md) |
| Relations | 40 `dependsOn` edges, no cycle; **no gate** — `enabledBy` and `suspendedBy` are empty |
| Pointers | 22 `crossReferences`, 7 of them `unmapped`; 22 namings of a defined term, every one declared |
| Vocabulary | `damage-and-healing-terms`, 8 terms over 7 entries (0045) |
| Draws | 5 entries declare one; the corpus is `randomness: seeded` |
| Extraction | 1 `split-by-sidebar` |
| Inventory | 60 units, 28 reached, 32 rejected, 0 unaccounted |
| Coverage | 73% of the extent quoted, against the 72% the map declares |
| Review | none; `exemption`, first mapping, [review.json](review.json) names seven things a second reading should look hardest at |

## What the run found

No hypotheses were written before it, because none was owed: #434 named the one thing this slice
was supposed to establish — that `startsAfter` lets a real corpus be sliced where a section
begins — and it did. Four other things turned up, and three of them are the same three trial 12
reported, met again in a different part of the same chapter.

### The extent field works on the corpus that forced it

`extent-start` passes on the first run: *Damage and Healing* occurs exactly once as a line on
p. 16, seventeen quote occurrences on that page lie after it, and none lies at or before it. The
two maps of p. 16 are complementary, and the heading line itself is in neither — it is one of the
32 units this map rejects as `ground: heading`, and trial 7's map does not enumerate it at all.

### An extraction put a whole section inside a sentence

p. 16's *Hit Points* paragraph opens **"Your Hit Point maximum is the number of"** and finishes
**"Hit Points you have when uninjured."** Between the two halves the extraction's reading order
puts the entire *Resting* section, the folio `16` and the running head — because the page is two
columns and pdftotext runs down one before starting the other.

`hit-point-maximum` therefore quotes a span that ends mid-sentence and carries
`extraction: {defect: "split-by-sidebar", renderedReading: …}`. **The defect is not a sidebar**,
and `split-by-sidebar` is the closest value in
[0024](../../docs/decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)'s
closed set: its test is that the quote begins or ends mid-sentence, which is exactly the shape
here, and its name is about the cause rather than the shape. Trial 12 found the same thing three
times and reported it as *an extraction can split one sentence into two entries*. This is the
fourth occurrence, and the first where the inserted material is a whole named section rather than
a column or a table. Whether the closed set wants a fourth value is not settled by one more case
in one corpus; what is settled is that the value that fits is named after the wrong thing.

### A quote crossing a page turn, again — and this time it is counted

`damage-types` is printed across the p. 16/17 turn:

> Each instance of damage has a type, like Fire or Slashing. Damage types are listed in “Rules
> **{17}** Glossary” and have no rules of their own, but other rules, such as Resistance, rely on
> damage types.

The quote carries the corpus's own `{17}` marker, because `check-locators.py` searches the pinned
bytes with the markers in place. Under
[#437](https://github.com/brandonifco/rules-factory/issues/437) the inventory could not find such
a quote at all and the two blocks it reaches would have gone to the unaccounted pile; that was
fixed before this map was written, and the blocks are counted.

### A run-in heading, again

`temporary-hit-points-duration` quotes **"Duration Temporary Hit Points last until they’re
depleted…"**. *Duration* is a heading the SRD prints run-in, and the extraction gives it no line
of its own, so the entry's evidence begins with the heading's word and its citation can name only
*Temporary Hit Points*. That is
[#435](https://github.com/brandonifco/rules-factory/issues/435), which trial 12 found and which
says no current entry requires run-in-heading addressing. This entry does not require it either —
the quote is unique and locates — so #435 is confirmed as real and still not forced.

### The map's one ambiguity was nearly hidden in a note

The first draft of `bloodied` was `clarity: clear` with a `note` reading *"'half your Hit Points'
is half the maximum rather than half the current total"*. That is a decision, written where a
decision cannot be checked. The corpus says only:

> If you have half your Hit Points or fewer, you’re Bloodied …

and two sentences of the same paragraph use *your Hit Points* for the **current** total, on which
the test holds only at 0. The entry is now `ambiguous`, the question quotes the words both
readings turn on, and
[0065](../../docs/decisions/0065-bloodied-is-measured-against-the-hit-point-maximum.md) rules that
the half is of the maximum. The map did not get worse; what it asserted got checkable.

## Why 3% ambiguous, against trial 12's 5% and trial 7's 27%

This is the most mechanical slice of the chapter. Damage arithmetic, a clamp at 0, an order of
application the corpus works an example through, three counters and a d20 — the passages state
numbers and comparisons, and where the corpus hands something to a person it hands it over whole:
the GM's power to ignore `monster-death` is a per-creature parameter, not a vagueness, and
`spell-damage-dice` is the map's one `assertion` because the spell supplies both facts and the
corpus states neither.

What the slice leans on instead is **material outside it**. Seven of its 22 cross-references are
`unmapped`, and six of those point into the Rules Glossary: the Short Rest and Long Rest, the
Unconscious condition, the Dead condition, and the list of damage types. Trial 8 maps that
glossary, over the same pinned bytes — and `resolvedBy` resolves only inside one map, so this map
can record that the Unconscious condition is defined elsewhere and cannot say where. That is
trial 12's H3 met a second time, from the other side.

## What is in the slice

| Section | Entries | What they state |
|---|---:|---|
| Hit Points | 5 | the maximum, the range down to 0, the subtraction, that loss does nothing until 0, and Bloodied |
| Resting | 1 | that rests exist and how long they are; what they *do* is in the Rules Glossary |
| Damage Rolls | 6 | roll-add-deal, the floor at 0, the weapon modifier, the spell's own dice, fixed damage, and where the dice are printed |
| Critical Hits | 2 | the attack's dice twice, and any other dice twice |
| Saving Throws and Damage | 2 | one roll for all targets; half damage rounded down on a success |
| Damage Types | 1 | every instance of damage carries a type |
| Resistance, Vulnerability, Immunity | 4 | halve, double, no stacking, the order of application, and Immunity's two kinds |
| Healing | 3 | what restores Hit Points, the cap at the maximum, and knocking a creature out instead |
| Dropping to 0 Hit Points | 6 | the two outcomes, three instant deaths, and falling unconscious |
| Death Saving Throws | 5 | the trigger, no ability score, three and three, a 1 and a 20, and damage at 0 |
| Stabilizing a Character | 2 | the DC 10 check, and what Stable does |
| Temporary Hit Points | 5 | what they are, lost first, their duration, no stacking, and that they are not Hit Points |

## Files

| File | What it is |
|---|---|
| [corpus-map.json](corpus-map.json) | the map |
| [corpus-manifest.json](corpus-manifest.json) | the corpus, pinned by hash to the copy in [../srd-52-combat/](../srd-52-combat/) |
| [mapping-protocol.json](mapping-protocol.json) | how this corpus communicates rules, and the sweeps the walk owes |
| [mapping-inventory.json](mapping-inventory.json) | the 32 units the walk examined and produced no entry for |
| [review.json](review.json) | no review, and what a second reading should look at |
| [CORPUS-LICENCE.txt](CORPUS-LICENCE.txt) | CC-BY-4.0 and the attribution it requires |
| [map-package.json](map-package.json) | the version this map would publish as, so it can be packed for a composed engine ([#446](https://github.com/brandonifco/rules-factory/issues/446)). Declared, not tagged: publishing is a person's decision (AGENTS.md §5) |
