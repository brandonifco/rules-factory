# 0026 — A meaning the same corpus gives outside the slice is a `scope: out` entry the rule names, and each corpus declares the words it points with

## Status

Accepted — 2026-09-15. Records the fixes for
[#115](https://github.com/brandonifco/rules-factory/issues/115) and
[#116](https://github.com/brandonifco/rules-factory/issues/116), findings 3 and 4 of trial 7
([`examples/srd-52-combat/`](../../examples/srd-52-combat/README.md)). **Extends
[0009](0009-absence-is-a-verdict-with-evidence.md)** (`crossReferences`), **[0020](0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)
§ 4** (`definedElsewhere` alone answers a pointer to an unadmitted corpus) and
**[0021](0021-a-gate-outside-the-slice-is-held-by-the-caller.md)** (a rule outside the slice is
named by a `scope: out` entry). Adds no entry field. Adds two optional manifest keys.

**Amended 2026-09-15**: the example in the last *Limits* bullet of *Consequences* is no longer
true of either Part 107 map. See *Amendment — the (b) pointer resolves* below. The limit, the
decision and the § 5 table, which records what #116 found and did, are unchanged.

## Amendment — the (b) pointer resolves

The last *Limits* bullet says Part 107's `paragraph (b) of this section` "fires on a self-reference
inside `civil-twilight-operation`, and the answer is an `unmapped` reason that says so". The reason
#116 wrote was "no other entry states (b) whole", and it was false at both dates:
`anti-collision-lighting` quotes all of § 107.29(b).

- **2020-01-01 map.** [#124](https://github.com/brandonifco/rules-factory/pull/124) changed the
  item to `resolvedBy: anti-collision-lighting`, which cites § 107.29(b) and quotes it whole.
  [#130](https://github.com/brandonifco/rules-factory/pull/130) wrote the reason into the entry's
  note, and added the `dependsOn` edge to `civil-twilight-alaska` the map lacked.
- **2026-01-01 map.** [#126](https://github.com/brandonifco/rules-factory/issues/126)
  (`faa-part-107` 4.0.0) made the same change: `anti-collision-lighting` cites § 107.29(a)(2) and
  (b) and quotes all of (b) as amended.

No Part 107 item is now answered by an `unmapped` reason for that phrase. The limit the bullet
states still holds. The built-in list's rule against self-references (0009) is not enforced on a
corpus's own phrases, and the phrase still fires on words the entry's own evidence quotes. It is
answered here by the entry that states (b), not by a reason.

## Context

**#115.** The SRD's Rules Glossary is the same admitted corpus as the combat chapter the map
reads, 170 pages later. It states things the chapter's rules need: when a creature is surprised
("caught unawares by the start of combat", p. 189), that a creature Incapacitated when it rolls
Initiative has Disadvantage (p. 184), how Advantage and Disadvantage change an Initiative score
when the GM uses scores instead of rolls (p. 184), and a fuller list of what makes a space
Difficult Terrain (p. 181). The first map recorded some of these as `scope: out` entries and
connected none of them. `surprise-glossary`'s note said it was "recorded so that the in-slice gap
can point at it", and nothing pointed at it. The Incapacitated modifier was connected to
`initiative-roll` only in a note. `definedElsewhere` was the obvious field and the wrong one: it
names a corpus that was **not** admitted (0005, 0020 § 4), and its runtime row is
`MissingRulesData`, which is false of a rule the corpus has.

**#116.** `check-map.py --only cross-references` detected pointers with a closed list of nine
phrases written from CFR and Hoyle ("except as provided in", "as in Fig."). The SRD points with
`(see “Rules Glossary”)`, `(see the next section)`, `as detailed earlier in “Playing the
Game.”`. The check found **0 pointers** in the SRD map and reported `ok` over its 22 declared
cross-references, because declaring one obliged nothing and not declaring one was invisible. The
same measurement on the other maps: Part 107 detected 2 pointers against 26 declarations (every
"under § 107.200" and "Section 107.25" went unseen), Hoyle 3 against 5, and the 2020 temporal
map 0 against 0.

## Decision

### 1. A term whose meaning the same corpus gives outside the slice is a `scope: out` entry, named by `crossReferences`

The passage is recorded as a `scope: out` entry that cites it with the corpus's own locator and
quotes it, exactly like any other entry. The locator checker verifies it, and `extent` already
lets a `scope: out` entry cite beyond the slice. The in-scope entry names it with a
`crossReferences` item whose `resolvedBy` is that entry.

`cites` is anchored in the in-scope entry's evidence, as every item's is. Where the corpus's
words point ("(see “Rules Glossary”)"), `cites` quotes them. Where no words point, because the
chapter simply uses a term the glossary defines, `cites` quotes **the term as the evidence uses
it**: `surprised`, `Opportunity Attack`, `rolls Initiative`, `Difficult Terrain`, `only the most protective degree of cover applies`. That is
checkable with no new field. The item is anchored in the evidence, it resolves to an entry in
the map, and the entry it resolves to is located in the corpus.

### 2. Where the passage modifies the rule, `dependsOn` names it too. No `modifiedBy`

The test is the one `dependsOn` already has. **If the engine cannot resolve the in-scope rule in
some case without the passage, the in-scope entry depends on it.** A modifier has to be
implemented before the rule it modifies is complete, which is implementation order and nothing
else. Applied to the SRD map, against `srd-5.2.1.txt`:

| in-scope entry | names | `dependsOn`? | why |
|---|---|---|---|
| `surprised` | `surprise-glossary` (p. 189) | yes | The slice gives only an example of surprise. The glossary is the corpus's one statement of the condition. It is still an open term, so the entry stays ambiguous. |
| `initiative-roll` | `incapacitated-condition` (p. 184) | yes | "If you're Incapacitated when you roll Initiative, you have Disadvantage on the roll." The roll is wrong without it. The entry's evidence now runs to that line. |
| `initiative-roll` | `invisible-condition` (p. 184, new) | yes | "If you're Invisible when you roll Initiative, you have Advantage on the roll." |
| `initiative-roll` | `initiative-score-option` (p. 184) | no, already `suspendedBy` | A gate outside the slice (0021). The cross-reference names the passage the gate already names. |
| `surprise-disadvantage` | `initiative-score-option` (p. 184) | yes | Under scores there is no roll, and "If you have Disadvantage on those rolls, decrease that score by 5". The entry's evidence now runs to that sentence. |
| `difficult-terrain` | `difficult-terrain-glossary` (p. 181, new) | yes | The glossary's list gives cases with a measure that the slice's examples do not (a slope of 20 degrees or more, liquid by depth, a narrow opening), and qualifies two it does give ("Heavy snow"; furniture "sized for creatures of your size or larger" against "Low furniture"). Which list governs where they differ is added to the entry's open question. |
| `cover-no-stacking` | `cover-glossary` (p. 179, new) | yes | The slice's rule is for a target "behind multiple sources of cover". One object covering three-quarters of a target also covers "at least half", and only the glossary's "more than one degree of cover" decides that. |
| `opportunity-attack` | `opportunity-attacks-glossary` (p. 185) | yes | The glossary's trigger says how the creature leaves reach ("using its action, its Bonus Action, its Reaction, or one of its speeds"). That decides a case the slice leaves open: a creature that leaves reach without doing any of those. Teleporting is not a conflict, because the glossary's "Teleportation" (p. 190) says "teleportation never provokes Opportunity Attacks". |
| `opportunity-attack-avoidance` | `disengage-action` (p. 181, new) | yes | The slice says only "You can avoid provoking an Opportunity Attack by taking the Disengage action". The glossary limits that to "your movement" and "the rest of the current turn". |

The first draft of this table said `opportunity-attack` needed no `dependsOn`, and it missed
Invisible, Cover and Disengage. The independent verdict found all four against the text, over
three rounds. In the passages this table names, none only restates its rule, so every
cross-reference here has a `dependsOn` beside it. The rule allows a cross-reference alone, for a
passage the slice already decides in every case. **The table is not a census.** The glossary
defines many terms the chapter uses, and nothing found all of them. Each row is a passage a mapper
or reviewer noticed, and was then checked against the text.

**Why not `modifiedBy`.** The question was whether any real SRD case needs it. None does. Every
modifier above is expressed by `dependsOn` plus a cross-reference. A `modifiedBy` list would order
exactly what `dependsOn` orders, and would add a distinction, *modifier* against *prerequisite*,
that no check can test and no runtime row reads. 0005 rejected fields of that kind. The runtime
reading is unchanged: an in-scope entry depending on a declined `scope: out` entry is the shape
`initiative-roll` → `ability-checks` and Part 107's `over-human-beings` → `subpart-d-categories`
already had.

### 3. `definedElsewhere` names a corpus that was not admitted, and `check-map.py` refuses anything else

`check-map.py --only manifest` refuses a `definedElsewhere.reference` that is a corpus the manifest
declares, or a reference marked `admitted: true`. The message points to § 1.

### 4. Each corpus declares its pointer phrases, and a silent zero fails

A manifest corpus may declare `pointerPhrases`, a list whose items are a literal phrase (a
string) or `{"regex": "..."}`. Both match case-insensitively, and a literal matches across any run
of whitespace. They are read **in addition to** the built-in list, for entries whose
`locator.sourceId` is that corpus, and for no other corpus.

- **What is one pointer.** Matches that overlap, or that only whitespace separates, are one
  pointer. Part 107's "Except as provided in" (built-in) and "paragraph (d) of this section"
  (declared) make one pointer, not two.
- **What claims it.** A pointer is claimed when it lies wholly inside an occurrence of some item's
  `cites` in the same evidence. A `cites` that covers half a pointer does not claim it. A pointer
  whose words name the entry's own `definedElsewhere` reference is claimed by that field, which
  0020 § 4 made the only place it is answered. There is one exception. A `scope: out` entry quoted
  only to decline a section works no rule, so `definedElsewhere` has no meaning to route and would
  put a `MissingRulesData` reading beside `OutsideCurrentScope`. It answers its pointers into an
  unadmitted corpus with `unmapped`, naming that corpus. Part 107's `knowledge-recency` does this
  for "part 61 of this chapter … § 61.56".
- **What is reported.** For each corpus the map quotes, the number of pointers detected in its
  quoted spans, whether phrases were declared, and how many declared items sit on a detected
  pointer.
- **What fails.** A corpus that declares no `pointerPhrases` and on which the built-in list
  detects nothing. A corpus that really points at nothing declares `pointerPhrases: []` and
  `pointerPhrasesReason`. The reason is refused beside a non-empty list and without a list,
  because nothing would read it (#60). A malformed item, a regex that does not compile, and a
  regex that matches the empty string all fail. With no manifest, only the built-in list is read
  and the zero is not judged. The `manifest` check already reports that case as NOT VERIFIED.

Each corpus's phrases were derived from its own text, not from memory:

- **SRD.** A search of all 364 pages for "see", "explained/described/detailed/defined/listed/noted/stated
  in", "earlier/later in" and "the next section" gave seven patterns: `(see …)`, `see (also) “…”`,
  a verb + `in “…”`, `“…” earlier/later in “…”`, `noted/stated in their descriptions`, `shown on
  the … table`, and `the next/previous/following section`. "Described later in this chapter" does
  not occur in the text. The nearest is "later in this document", once.
- **Part 107**, from `part107.xml`: `§ N.N(x)`, `Section N.N`, `paragraph (x) of this section`,
  `subpart X of this part`, `part N of this chapter`, `N CFR N` / `N U.S.C. N`, and "as defined in
  the Air Almanac". The same phrases go in the 2020 manifest, which is the same corpus id.
- **Hoyle**: `shown in {N} Fig.`, a regex that reaches past the page marker that hid
  `starting-position`'s pointer (0009's stated limit), and "as in the earlier stage of the game".

### 5. What the check found once it could see

| map | pointers detected, before → after | declared, before → after | revealed |
|---|---|---|---|
| `srd-52-combat` | 0 → 19 | 22 → 32 | `flanking` (an absence entry quoting the Modifiers step) said "(see the next section)" and declared nothing; it now resolves to `cover-degree`, as `attack-modifiers` does for the same span. The other 9 new items are § 1's. |
| `faa-part-107` | 2 → 38 | 26 → 36 | `night-operation` "under § 107.65". It now resolves to a new `scope: out` entry, `knowledge-recency` (§ 107.65), and so does `night-training-completed`, which was `unmapped` and now also depends on it: its open question is which of § 107.65's ways qualifies. The new entry quotes the whole section, and 5 items answer the 7 pointers detected in it. Also `civil-twilight-operation` "paragraph (b) of this section" (unmapped: (b) is its own evidence) and "as defined in the Air Almanac" (→ `civil-twilight-alaska`); `subpart-d-categories` "§ 107.39(a) and (b)" (→ `direct-participation` and `reasonable-protection`). |
| `hoyle-backgammon` | 3 → 5 | 5 → 5 | Nothing. Both undetected declarations are now detected, and the map is unchanged. |
| `faa-part-107-temporal` | 0 → 6 | 0 → 4 | `civil-twilight-operation` (the same two), `visual-line-of-sight` and `visual-observer-conditions` (resolved as the 2026 map resolves them). The other 2 pointers are answered by `definedElsewhere`. |

In the SRD map, 19 of the 32 declared items sit on a detected pointer. The other 13 are the 9
term-anchored items of § 1 and 4 pointers the mapper declared in words no phrase covers: "any of
these activities" (twice), "Other effects might make a square cost even more." and "spells,
special abilities, and other effects can apply penalties or bonuses". They were declared by
judgement, and they stay declared. #116 counted 25 declarations; the map had 22.

## Alternatives considered

**Extend `definedElsewhere` to take a same-corpus locator.** The option #115 asked about.
Rejected. A locator inside `definedElsewhere` is a citation that no locator checker reads, since
checkers read entries, and a quote could not go with it. Its runtime row, `MissingRulesData`,
says the corpus lacks the rule, and here it does not. And it would give one field two
discriminated meanings, which 0005 rejected when it kept `beyondAdapter` and `definedElsewhere`
apart.

**A `modifiedBy` field.** Rejected in § 2. It stays open for a case `dependsOn` cannot express,
which would be one where the modifier must *not* be implemented first. None is known.

**A wider built-in list.** Rejected. "(see …)" is how the SRD points, and in another corpus it is
a parenthesis. A universal list either fires on words that are not pointers in some corpus or
misses the ones that are, and it still passes a corpus none of its phrases fit. The failure that
matters is the silent zero, and only a per-corpus declaration can turn that into a question with
an answer.

**Detect a quoted section title as a pointer in every corpus.** Considered for the SRD, whose
pointers nearly all name a heading in curly quotes. Rejected as a built-in. It is a property of
this corpus's typography, so it belongs in this corpus's phrases, and two of them do use it.

## Consequences

**The in-scope entries that use a glossary term now name it.** In the SRD map: one new
`scope: out` entry, `difficult-terrain-glossary`; four new `dependsOn` edges; seven new
`crossReferences` items; the evidence of `incapacitated-condition` and `initiative-score-option`
extended to the sentence that modifies the rule. Three notes that said "the schema has no field"
or "reached by no pointer" now say what names the passage. `cover-degree`'s note cited the
glossary for a rule the slice states (`cover-no-stacking`, p. 15), and now cites the slice.

**Limits, stated where the claim is.**

- A term-anchored `cites` is weaker than a pointer. Nothing checks that the entry it resolves to
  defines the term, or that every glossary definition an in-scope rule relies on is recorded. A
  same-corpus meaning nobody noticed is invisible, as a cross-reference nobody noticed was
  (0009).
- Detection is still a list. It is now the corpus's own list, written by the mapper and read by
  review. A corpus that points in words its phrases do not cover passes.
- The `dependsOn` test in § 2 is a judgement made per entry, and nothing checks it. The table
  above is the record a reviewer holds it to.
- A regex can over-detect. Part 107's `paragraph (b) of this section` fires on a self-reference
  inside `civil-twilight-operation`, and the answer is an `unmapped` reason that says so. The
  built-in list's rule against self-references (0009) is not enforced on a corpus's own phrases.

**Reviews.** The SRD and Part 107 maps change meaning and carry independent verdicts (0017). The
temporal map is still under its `legacy` exemption, which names the change. Hoyle's map is
unchanged. Manifest bytes change for all four, and so do their packages. Versions are not bumped
here (trial 7's fixes bump once).
