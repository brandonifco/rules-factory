# 0009 — Absence is a verdict with evidence, and scope belongs to a rule, never to a section

## Status

Accepted — 2026-09-14.

## Context

Three states exist. The schema has two words for them.

| state | instance | recorded as |
|---|---|---|
| read, and deliberately not covered | `strategy-advice` — advice, not rules | `scope: out` |
| read, and the corpus does not state the rule at all | `doubling-cube` — a 1909 text predates it | `scope: out`, locator `(absent)` |
| nobody looked | § 107.29(d), never enumerated | no entry |

The third row is the map's entire reason to exist.
[`method.md`](../method.md) says so in as many words — *"The distinction is the whole reason
the map exists"* — and then instructs a mapper to record it as the **reason string** `"absent
from this corpus"`. That is the carrier 0003 rejected for phase gates, 0004 rejected for
adapter reach, and 0005 rejected for decline reasons, each time for the same stated reason: a
convention no check can read is one nobody can be shown to have broken. It survived here
because nothing consumed it.

Three issues are the same question from three angles.

**[#29](https://github.com/brandonifco/rules-factory/issues/29) — the absent rule has no honest
locator.** `doubling-cube` cites `"(absent)"` because there is no passage. `check-locators.py`
had to special-case it, and the special case leaked into the specification: `corpus-map.md`
conceded that the gate's line *"all 29 checked"* meant twenty-eight.

**[#20](https://github.com/brandonifco/rules-factory/issues/20) — `scope: out` was applied to a
section.** *Hints for Play* was excluded wholesale as advice, and inside it sits the only
authority in the corpus for how many faces a die has. **Verified against the text rather than
taken from the report**, because the report was a previous agent's and the claim is
load-bearing:

- The corpus writes *"We will go seriatim through all the possible throws"* and then prints
  nineteen headings naming **twenty-one** throws — `SIX TROIS, SIX QUATRE, SIX CINQUE` share
  one heading, which is where a heading count goes wrong.
- An unordered pair over *n* faces has *n(n+1)/2* throws. *n(n+1)/2 = 21* has exactly one
  positive solution, *n = 6*. The enumeration is not merely consistent with six faces; it
  admits no other number.
- `die` and `dice` occur in this 740 KB volume **only** in the backgammon chapter, and the
  chapter never writes *six* of a die. There is no second statement anywhere.

So `DicePair.OfSixes` was an engine assumption with no mapped authority, and what cost the map
the dice was excluding a **unit of the corpus's layout** by a judgement that belongs to a
**rule**.

**[#28](https://github.com/brandonifco/rules-factory/issues/28) — a carve-out with no entry in
either direction.** § 107.29(a) opens *"Except as provided in paragraph (d) of this section"*
and (d) has no entry in either Part 107 map. Nothing detected it, because a cross-reference was
a sentence inside an `evidence` span and no field made a mapper answer it.

One thing has changed since `scope` was specified, and it raises the cost of getting this
wrong. `scope` is now load-bearing:
[0008](0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md)'s procedure has
`scope: in` as its precondition, and row 1 of the correspondence table is checked first and
dominates. A wrong `scope` silently changes an entry's classification.

## Decision

**Five moves. One new entry field, one new map field, one correction, and two checks.**

### A. `absentFrom` records the absence, and the entry carries a real locator and a real quote

```json
"absentFrom": { "searched": ["doubling", "doubling cube", "redouble", "offer to double"] }
```

`searched` names the words the corpus **would use** if it stated the rule. It is non-empty,
and `check-locators.py` searches the declared extent for every one of them. **An `absentFrom`
entry whose terms turn up fails.** This is the only check in the repository that goes red by
*finding* something, and it is what makes an absence a fact rather than a confident sentence.

The entry keeps `locator` and `evidence`, unchanged in meaning at the level that matters:
**where to look to settle this entry, and the corpus's own words there.** For an ordinary
entry the words state the rule; for an absent one they are the passage the rule would be in,
and the absence is the hole in them. `doubling-cube` cites p. 272 and quotes

> A pair of dice (or sometimes a pair for each player) and a couple of dice-boxes complete the
> apparatus of the game.

The doubling cube is apparatus. That sentence enumerates the apparatus and **closes the list**.
The stakes passage on pp. 276–277 closes a second one — *"the value of the game depends upon
the stage reached by the adverse player, as follows"*, then three results and nothing else — so
a stake that could be raised during play has no room there either.

The consequence is the point: **an absence now costs a mapper more reading than a scope
verdict, not less.** It must be cited, quoted, page-checked like any other entry, *and*
searched for. That is the right price, given that all three issues here are instances of a
mapper who stopped reading.

`absentFrom` excludes what it contradicts — `beyondAdapter`, `definedElsewhere`, an `ambiguity`
block — and requires `scope: out` and `status: declined`. Nothing may `dependsOn` or `gatedBy`
it: that edge is `blocked` and will never clear.

### B. It is an entry, not a manifest record. This is the crux, and here is the argument

[0004](0004-adapter-reach-is-a-property-of-the-entry.md) put `references` in the manifest and
`beyondAdapter` on the entry, and the test it actually applied was **whether the fact varies
per entry or holds of the corpus**. Absence looks like a corpus fact, and by that test alone it
would go to the manifest beside `references`. Three things decide it the other way.

**1. `references` is bounded by the corpus; absences are not.** The corpus *names* its
references — *"§ 171.8"*, *"the Air Almanac"* are in the text — so the list is finite and
derivable by reading. The set of rules a corpus does not contain is infinite. An absence list
therefore needs a bound from **outside** the corpus, and the only bound available is *a rule
somebody actually asked about*. That bound is precisely what an entry is: an id somebody wanted
an answer for. The record has to attach to the thing that supplies the bound.

**2. The manifest describes a corpus; an absence is a verdict about one.** `contentHash`,
`adapter`, `licence` are true of the text whoever reads it. *"There is no doubling rule here"*
is produced in phase 3 by the same judgement that produces `scope: out`, and it is only
interesting relative to the engine being built. Put it in the manifest and the manifest stops
describing corpora and starts carrying mapping verdicts — and the corpus toolkit, which owns
manifests and does not own maps, inherits a field it cannot evaluate.

**3. A manifest record drops out of everything that makes the map load-bearing.** It has no id,
so nothing can name it; it is outside the correspondence table, so no runtime reason derives
from it; and *"does this engine handle doubling?"* stops being answerable by looking up an id.
[0001](0001-the-corpus-map-is-the-interface.md)'s whole claim is that the map is an interface
rather than documentation. A manifest list of absences would be documentation.

### C. `scope` is decided per rule. A section has no scope of its own

There is no section-level exclusion and no field for one. `strategy-advice` declines **the
advice**, not *Hints for Play*; the same section states `die-faces`, which is `scope: in`. Both
entries cite the same section, and that is correct rather than a conflict.

The recorded reason a section held out can contain an in-scope rule is that nothing was ever
held out: a section is a unit of layout, `scope` is a judgement about a rule, and #20 is what
treating them as one thing costs.

### D. A map declares its `extent`, and every unit inside it is reached by a verified quote

```json
"extent": { "unit": "page", "from": 271, "to": 280 }
```

This is what makes *"no entry anywhere cites this section"* a fact rather than a hope, and it
is the honest answer to C's enforcement problem: **nothing excludes a section, so what records
that a section was read is that the corpus's own units inside the map's declared extent are
each reached by some entry's located evidence.** `check-locators.py` names every page that is
not.

`extent` is a map field and not a manifest one, for B's second reason: it is a claim about what
**this map read**, not about the text.

Implemented for `printed-page`, which is the grammar whose units are in the text. A
`section-designation` corpus needs the paragraph-path equivalent, which
`examples/faa-part-107/check-locators-section.py` is already most of the way to and which this
decision does not build.

### E. A reference the corpus makes is an entry, or a recorded reason there is none

```json
"crossReferences": [
  { "cites": "as at starting", "resolvedBy": "opening-roll" },
  { "cites": "as in Fig. 1", "unmapped": "Fig. 1 is an illustration, not a passage." }
]
```

`check-map.py --only cross-references` reads a closed list of pointer phrases out of each
entry's `evidence` and requires every one of them to be claimed by a declaration whose `cites`
appears **verbatim in that same evidence** — so the answer is anchored in the corpus's words
rather than asserted beside them — and resolved exactly one way.

The obligation an *"except as provided in"* clause places on a mapper is therefore: **follow
it, and produce either an entry or a sentence saying why there is none.** Not a judgement about
whether the target matters.

## Alternatives considered

**A third `scope` value, `absent`.** The obvious move, and the one #29 offers first. Rejected
on the evidence of what now reads `scope`: 0008's procedure takes `scope: in` as its
precondition and its three gates are written against a binary; row 1 of the correspondence
table is checked first and dominates; `check-map.py`'s `matched_rows` tests `scope == "out"`.
A third value makes every one of those a three-way question whose third answer is *the same as
`out`* at runtime — because it is: the engine's honest reply about doubling is
`OutsideCurrentScope` either way. The distinction #29 asks for is the **map's**, not the
engine's, and widening a vocabulary the engine shares is the wrong place to record it. A field
that only the map reads costs the engine nothing.

**Keep `(absent)` and teach the checker to recognise it.** Rejected: it is the status quo, and
the status quo is the evidence. The checker did recognise it — by matching the *shape* of a
citation naming no page — and the recognition leaked into the specification as a conceded
untruth, `corpus-map.md` admitting that *"all 29 checked"* verified twenty-eight. A convention
spelled in a string is a convention a typo silently joins.

**A manifest-level `absences` list beside `references`.** Argued at length above and rejected
on three grounds, the first of which is decisive: `references` is bounded by the corpus and
absence is not, so an absence list has no source to be derived from and no size it should be.

**A boolean `absent: true`.** Rejected for the reason 0004 rejected `unreachable: true` and
0005 rejected `surprising: true`: it states a conclusion a check cannot read. `searched` is the
same claim with its evidence attached, and it is falsifiable — which is the whole difference.

**No record at all; an absent rule is simply not in the map.** Rejected because it is state 3.
It is also the reading that would have deleted the most useful entry in the backgammon map: a
reader asking whether this engine doubles gets a recorded verdict instead of silence.

**A map-level `excludedSections` list, to close #20.** Rejected, and worth stating because it
is the natural first design: it makes the category error into schema. A structure for excluding
sections would have made *Hints for Play* excludable **correctly**, and the dice would still be
unmapped.

**Derive the extent from the citations rather than declaring it.** Tempting, because it needs
no new field. Rejected on a number: the backgammon citations run 271–277, so a derived extent
is 271–277 and pages 278–280 — which hold the throw enumeration — fall outside it. The check
would have been green on the exact defect it exists to catch. An extent that cannot disagree
with the map is not a claim.

## Consequences

`examples/hoyle-backgammon/` migrates: 29 entries to 30. `doubling-cube` gains a locator, a
span and four searched terms; `die-faces` is added with its locator inside a section the map
was read as excluding; `strategy-advice`'s note is restated as a verdict about advice rather
than about a section; `inner-table-handedness` and `next-game-opening` declare the pointers
their evidence makes.

`corpus-map.md` loses the paragraph conceding that the gate's count was one larger than what it
verified. The defect is gone, so the concession would be false.

**Part 107 now fails, and that is the finding.** `check-map.py --only cross-references` reports
`night-operation`'s *"Except as provided in"* as unanswered in the 2026 map. The 2020 map does
not fire — § 107.29 is *Daylight operation* at that date and its (a) opens differently — which
is consistent with #28's own note and is evidence the check reads the corpus's words rather
than a section number. Neither file is changed here.

**Six limits, stated where the claims are made.**

- **A term absent is not a rule absent.** The corpus could state the rule in words nobody
  searched for, and `absence` would pass. What it catches is a mapper who declared an absence
  without looking — which is what all three issues are instances of.
- **A page reached is not a page read.** `coverage` catches a mapper who stopped, not one who
  skimmed.
- **Nothing sizes the extent.** A map declaring one page of a four-hundred-page book covers it
  trivially. What the field buys is that the claim is written down and can be argued with.
- **`unmapped` is prose**, the carrier 0003 and 0004 both rejected. What is checked is that a
  mapper was made to write one and that it is anchored to the passage, not that it is true.
- **The pointer list is closed and short.** `starting-position` quotes *"as shown in {273}
  Fig. 1"* and the page marker falling inside the phrase hides it. A corpus that points
  somewhere in other words produces a map that passes.
- **`coverage` exists for one grammar.** `section-designation` needs the paragraph-path version
  and does not have it, so the state this decision is named for remains undetectable in the
  Part 107 maps by anything but E.

**What it still cannot do.** A rule nobody thought to ask about gets no entry, so no absence is
claimed and nothing notices — the fourth state, below the three. `coverage` narrows it to
*pages nobody quoted*, and E narrows it to *pointers the corpus itself makes*. Neither reaches
a rule the corpus states plainly in a paragraph some other entry happens to quote. That is the
same class as 0004's amendment and #20, and no field has ever reached it.
