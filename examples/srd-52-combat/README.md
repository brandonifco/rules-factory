# Trial 7: the method by hand, against the SRD 5.2.1 combat chapter

A run of [the method](../../docs/method.md), and the first against a PDF. Chosen
([#106](https://github.com/brandonifco/rules-factory/issues/106)) to stress what the earlier
corpora did not: a real PDF, so an adapter and page locators over extracted text; actions,
reactions and turn structure as gates; many rules left to the Game Master; and dense pointers into
conditions and spellcasting outside the slice.

**Status: steps 1–3 of #106.** The corpus is admitted, a first map is written, and the map has had
a blind second mapping (0014): [blind-mapping/](blind-mapping/README.md) compared a map written by
a mapper who had not seen this one, resolved all 259 flags against the corpus, and corrected the
map to them. `review.json` records that as a `blind-second-mapping` review naming the corrected
bytes. The package (step 4) and the engine (step 5) are still to come. The counts below are the
corrected map's; the first map had 86 entries, 17 of them ambiguous.

The trial was numbered 5 in #106 and in the pull request that admitted the corpus. Trials 5 and 6
were already the injection trial and the blind-mapping trial (0014, 0015), so it is trial 7.

> This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of
> the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the
> Creative Commons Attribution 4.0 International License, available at
> https://creativecommons.org/licenses/by/4.0/legalcode.

That is the attribution statement the SRD's own Legal Information page (p. 1) requires, word for
word. The same page asks that no other attribution to Wizards be given. It is also in the
manifest's `licence` field. Anything that carries the quotes onward (the map, and a map package)
has to carry it too. See [Follow-ups](#follow-ups-for-later-steps) for the package.

## Admission

### Which text

| | |
|---|---|
| Source | https://www.dndbeyond.com/srd, the official Wizards of the Coast / D&D Beyond SRD page |
| Retrieved from | https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf |
| File | `SRD_CC_v5.2.1.pdf`, 6,031,375 bytes, 364 pages, last modified 2025-05-01 |
| PDF sha256 | `8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87` |
| Committed text | `srd-5.2.1.txt`, 1,413,945 bytes |
| Text sha256 (`contentHash`) | `c55926cb77bc7ea09096fc652db1411d763eae89d430c52221ed8709a075b100` |
| Licence | CC-BY-4.0 (stated on the SRD page and on p. 1 of the PDF) |

**The corpus is 5.2.1, not 5.2.** #106 names "SRD 5.2". The official page now links only 5.2.1
in English ("Published: May 01, 2025"). A `SRD_CC_v5.2.pdf` still answers at the same media path,
but nothing official links to it, so it was not used. The corpus id is therefore `srd-5.2.1`. The
package id keeps `Srd52Combat`, which names the 5.2 line rather than the point release.

### Decisions

**`boundaryPolicy: pin-in-repo`.** CC-BY-4.0 permits redistribution with attribution, so the
corpus is committed (0002). Both the PDF and the text derived from it are committed: the PDF so
that the derivation can be re-run from this repository alone, and the text because it is what the
map quotes and the checker reads. **Size:** the PDF is 6.0 MB and the text 1.4 MB, about 7.4 MB
in all. That is eight times Hoyle's 740 KB. It was committed anyway, because a derivation whose
input is not in the repository cannot be checked from it, and CC-BY allows it.

**`verification: committed-copy`, `committedPath: srd-5.2.1.txt`.** CI can verify the text's
hash. **`quotation: verbatim`**: CC-BY permits quoting with attribution. **`randomness: seeded`**
(0019): Initiative is a Dexterity check (a d20), and damage, saving throws and attack rolls are all
dice.

**`hashDerivation: srd-5.2.1-pdftotext-24.02.0-page-marked`.** A digest says nothing without what
it covers, and here there are two things it could cover. `contentHash` covers **the bytes of the
committed text file**, exactly. Those bytes are not what Wizards publishes; they are produced from
the PDF by [extract.py](extract.py), and its docstring is the derivation in full:

1. `pdftotext -enc UTF-8` from **poppler-utils 24.02.0**, default reading-order mode, no other
   options;
2. before physical page *N*, a line `{N}` (no `{` or `}` occurs anywhere in the SRD text);
3. pages joined with nothing between, written as UTF-8.

Nothing is normalised. The PDF's own digest is recorded beside it as `sourcePdf.sha256`, with its
byte count and path. `extract.py --check` verifies both digests using only the standard library,
and it re-derives the text and compares it byte for byte wherever pdftotext 24.02.0 is installed.
Where it is not, it prints NOT VERIFIED for that step and does not call it ok. `intake.py`'s
`HASH_DERIVATIONS` gains the name, mapped to the raw-bytes function. That is exact, not an
approximation, because the committed file *is* the derivation's output.

The alternative, `contentHash` over the PDF bytes with the checker extracting text itself, was
rejected. A standard-library PDF text extractor is a project in its own right. Any extractor
defines a derivation of its own, so the text it gives would still have to be named and pinned.

**Adapter `pdftotext-page-marked`, locator grammar `heading-path-and-printed-page`.** A citation
reads `Combat / Making an Attack / p. 15`: the corpus's own headings, then a page. **Printed and
physical page numbers coincide for all 364 pages.** Physical page *N* prints folio *N*, and
`extract.py` refuses to write the text if any page does not. So `p. 15` is both the page a reader
turns to and the PDF's fifteenth page, and the grammar does not have to choose.

**Locator checker: [check-locators-pdf-text.py](check-locators-pdf-text.py)**, standard library
only, registered for the adapter in `pack-map.py`'s `LOCATOR_CHECKERS` and run by `validate.sh`.
It is stricter than Hoyle's `tools/check-locators.py` in three ways. The whole quote must occur,
not its longest five-word prefix. Every occurrence must touch the cited page, not only the first.
The citation's last heading must occur as a line between the start of the previous page and the
quote. `absence` and `coverage` are Hoyle's checks, loaded from that file and run unchanged. Its
failing cases are in `tools/tests/test_check_locators.py`.

**`extent`: pages 13–16**, the "Combat" section of "Playing the Game", from the heading at the top
of p. 13 to the end of "Underwater Combat" on p. 16.

## The map

**91 entries**: 70 in scope, 21 out. The blind second mapping added five and changed eighteen;
[blind-mapping/README.md](blind-mapping/README.md) lists each change.

| | in scope | out of scope |
|---|---:|---:|
| operation | 61 | 20 |
| value | 6 | 1 |
| assertion | 3 | 0 |
| clear | 51 | 21 |
| ambiguous | **19 (27%)** | 0 |
| status | 70 `mapped` | 21 `declined` |

- **Out of scope, 21.** 16 decline rules outside the extent that in-scope entries depend on, gate on or
  restate: the Actions table, Bonus Actions, Reactions, attack rolls, Advantage/Disadvantage, saving
  throws, ability checks, Round Down, Prone, Incapacitated, the movement modes, the Initiative-score
  option, Damage Rolls, Resistance, and the Glossary's restatements of Surprise and Opportunity
  Attacks. 3 decline pointer passages inside the extent (`action-options`, `speed-and-size-sources`,
  `damage-and-healing`). **2 are absences** (`absentFrom`): `flanking` and a `surprise-round` in
  which the surprised lose their first turn. The corpus states neither.
- **Gates, 15 entries.** Five grid rules are `enabledBy: grid-play`. Five mount rules are enabled
  by `mount-eligibility` or `mount-control-requires-training`, and four of them also by
  `mounting-cost`, the rule that puts a rider on a mount. `opportunity-attack` is `suspendedBy`
  `opportunity-attack-avoidance`, and by `reactions` and `incapacitated-condition`, gates outside the
  slice (0021). `attack-sources` is suspended by `incapacitated-condition` too. `initiative-roll` is
  suspended by `initiative-score-option` (Rules Glossary, p. 184), also outside the slice.
  `free-object-interaction` and `communication-cost` are suspended by the assertion
  `gm-requires-action`.
- **One conflict**, `does-combat-end-without-a-defeat`. p. 13 says the fight goes on to the next
  round "if neither side is defeated". p. 14 says combat can also end "when both sides agree".
  Both members are `unresolved`. The likelier reading, that the specific rule governs, is a
  Phase 4 decision and is not taken here.
- **22 `crossReferences`**, 16 resolved to entries and 6 `unmapped` with a reason.
- **No derived entries.** No fact was needed that two stated rules entail and none states.

**Assertions, 3.** `initiative-ties` (the GM or the players decide "the order among tied"
combatants, which is a fixed set). `gm-requires-action` ("when it needs special care or when it
presents an unusual obstacle", a stated measure). `sides-agree-to-end` (an agreement whose only
value is to end combat).

**Ambiguous, 19.** Two are the conflict above. Five are "or case" gaps (gate 1), where the words
are clear and a reachable case is not covered: whether "two sizes larger or smaller" means exactly
two (`moving-through-creatures`); what the shortest route may pass through (`grid-range`); what
entering a square occupied by an ally or a Tiny creature costs (`grid-entering-square`); who picks
the space you fall into (`falling-off`); and the Initiative ties the tie rule does not assign
(`initiative-ties-uncovered`). Two turn on what words attach to: whether "that covers at least half"
qualifies "another creature" (`cover-degree`), and whether "any of these activities" reaches
communication (`communication-cost`). Ten are open terms with no measure: `round-duration` ("about
6 seconds"), `group-initiative`, `surprised`, `difficult-terrain`, `brief-or-extended-communication`,
`side-defeated`, `total-cover` ("directly"), `appropriate-anatomy`,
`mount-control-requires-training` ("similar creatures") and `independent-mount`.

Three questions the first map asked are answered by the corpus and are no longer ambiguous:
`grid-speed-in-squares` (the general Round Down rule, p. 5), `wrong-location-misses` (the roll is
made) and `mounting-cost` (movement cannot go below zero).

Calibration: the slice is ~15,000 characters of extracted text, twice the earlier trials' ~8,000,
and produced 68 in-scope entries against their ~24 (70 after the blind second mapping). The rate per character is higher. The SRD
packs a rule into nearly every sentence.

## Findings: where the method and schema did not fit

Every place this corpus did not go through cleanly. None of them was solved by inventing schema.

### 1. The quote is verbatim of the extraction, and the extraction is not the page

The map quotes `srd-5.2.1.txt`, because that is what a checker can hold a quote to. pdftotext made
that text differ from the printed page in five ways, and each one showed up in an entry:

- **Folio and running header mid-sentence.** `initiative-ties` quotes "The GM decides the 13 System
  Reference Document 5.2.1 order if the tie is between…". pdftotext emits the page's footer between
  its two columns, inside a sentence that runs from one column into the next.
- **A sidebar splits a sentence.** The sentence introducing an attack's structure starts on p. 14.
  pdftotext puts the whole "Unseen Attackers and Targets" sidebar and the p. 15 marker between its
  halves. No contiguous span holds that sentence, so `attack-structure` quotes from its second half
  ("or make an attack roll as part of a spell…"). The "Playing on a Grid" sidebar does the same
  between `free-object-interaction` and `gm-requires-action`, the paragraph that continues it.
- **A table's cells are interleaved.** The Cover table's Three-Quarters row comes out as "Three+5
  bonus to AC Quarters and Dexterity saving throws". The Total row's two cells come out in the
  opposite order to the printed columns. `cover-bonuses` quotes that, and says in its `note` that
  its values were read from the rendered page. This is the case `corpus-map.md` predicted ("a PDF
  rulebook read as extracted text loses exactly the tables a rules engine most needs"). Here the
  table was **garbled, not lost.** `beyondAdapter` is binary, the rule is here and the reader cannot
  see it, and it has no way to say *the reader sees it wrongly*. The entry is left in reach, with a
  note. The whole-table rule is met by reading the image, which no check covers.
- **Line-end hyphens are joined.** The page breaks "hand-held" across a line and the text reads
  "handheld". Nothing in the PDF says whether the hyphen was the word's or the typesetter's.
- **A line ending in an em dash loses its space.** The quote in `grid-range` has to read
  "objects— count", with a space the printed page does not have. A quote that followed the page,
  "objects—count", does not occur in the text, because whitespace-run matching cannot match *no*
  whitespace.

What this means for the method: "`evidence` is the corpus's words" now has to say *which* words.
For a PDF it is the committed derivation's words, and the gap between the derivation and the page
is checked by nothing except a person looking. That is recorded here and not decided.

### 2. A page extent cannot say where a chapter ends on a page

"Combat" ends halfway down p. 16. "Damage and Healing" begins beside it and is not in this slice.
The `page` unit covers whole pages. So `coverage` is satisfied for p. 16 by combat entries, and
`absence` searches Damage and Healing's text too (harmlessly here). `damage-and-healing` declines
that section explicitly, so the half-page is not silently claimed as read. 0020 gave sections a list
because a range claims too much. For a page grammar a page is the smallest unit there is, and the
same over-claim happens inside a single page.

### 3. A term defined in the same corpus, outside the slice, has no field

The Rules Glossary defines or restates a good deal of what the chapter uses. Surprise is "caught
unawares by the start of combat" (p. 189). Opportunity Attacks lists the ways of leaving reach
(p. 185). Incapacitated gives Disadvantage on Initiative (p. 184). "Sometimes a GM might have
combatants use their Initiative scores instead of rolling" (p. 184). `definedElsewhere` names an
**unadmitted corpus** in the manifest's `references`, so it is the wrong carrier. These are the
same admitted corpus, outside the map's extent. They are recorded as `scope: out` entries that
quote the glossary, reached by `crossReferences` or by a gate (0021). Where the glossary text is a
modifier rather than a gate (Incapacitated's Initiative penalty), no field connects it to
`initiative-roll` at all, and the connection is only in a note. This is issue #8's "dense internal
cross-reference graph", and the schema's answer to it is still scope-out entries one at a time.

### 4. `crossReferences` detects none of this corpus's pointers

`check-map.py --only cross-references` reads a closed phrase list, written from CFR and Hoyle
wording ("except as provided in", "as in Fig."). The SRD points with `(see "Rules Glossary")`,
`(see the next section)`, `as detailed earlier in "Playing the Game"`, `(explained in "Damage and
Healing")` and `as noted in their descriptions`. The check found **0 pointers**. The 25 declarations
are the mapper's own, anchored in the evidence and resolved, and nothing obliged them. Extending the
phrase list is a checker change and is not made here.

### 5. "The GM determines" usually is not an assertion, and 0010 is what says so

The SRD says "the GM determines" of rules it also makes computable. The GM "determines whether the
target has Cover", and the Cover table states what cover is. The GM establishes positions, and
range, reach and cover test them. Under 0010, whose fact it is decides nothing. So
`attack-modifiers` and `combat-steps` are operations over caller-supplied facts, and only three
entries pass gate 3. That held up well. Without 0010, every one of these would have been an assertion.

**Attribution has no field.** An engine owes an assertion "demand it, **attribute it**, record it".
`initiative-ties` has two different deciders in one sentence: the GM for monsters and mixed ties,
the players for characters. The map can record who only in `note`. This is not new: Hoyle's "as
may have been agreed" names nobody. But a tabletop RPG is the first corpus with two standing
roles at the table, and the method's "caller" is one.

### 6. Ambiguity about whether a draw happens

`randomness: seeded` is corpus-level, and no field says an entry draws. Three entries turn on
whether, or how often, a die is rolled. `wrong-location-misses`: "you miss", but is an attack roll
still made? `group-initiative`: one roll per group, but what is a group? `initiative-score-option`:
no roll at all when the GM chooses it. A seeded engine that guesses changes every later draw of a
replay. The first map recorded two of the three as ambiguous and one as a gate the caller holds.
The blind second mapping answered the first from the corpus: the preceding sentence gives the roll
Disadvantage "whether you're guessing the target's location", so the roll is made. The point stands
for `group-initiative`. The method's replay
guidance (Phase 6, "preserve determinism") assumes the corpus fixes the draws. Here it sometimes
does not, and the only place that shows is `ambiguity.question`.

### 7. A conflict inside one chapter, a page apart

The earlier trials' conflicts lay across sections. `next-round` and `combat-end` are one page
apart, in the same chapter, and the one that looks like a summary ("The Order of Combat") is the
one that is wrong on a literal reading. 0007 handled it without strain.

### 8. Admission details the schema did not anticipate

- **Two digests, one `contentHash`.** The manifest has one digest field, and the text it hashes is
  not what was retrieved. The PDF's digest went into a new manifest key, `sourcePdf`. `check-map.py`
  does not read that key. `extract.py --check`, which `validate.sh` runs, does. A key only one
  script reads is close to the "field a checker ignores" that #60 warns about. It is recorded
  rather than added to the schema.
- **The derivation depends on a tool outside the standard library.** pdftotext 24.02.0 may not be
  on a CI runner, and there the re-derivation step reports NOT VERIFIED. The two hashes are still
  checked everywhere.
- **`intake.py`'s comment** says every derivation in use is "SHA-256 over the file's bytes exactly
  as retrieved". That is no longer true of every entry. The new entry carries its own comment, and
  the general comment is left for the #105 change that owns that file.
- **Package directory name.** `pack-map.py` requires lower-case kebab-case without dots, so the
  map's directory is `srd-52-combat`, not `srd-5.2-combat`. That gives exactly
  `RulesFactory.Maps.Srd52Combat` under 0015's rule.
- **The trial number was taken.** #106 called this trial 5, but "trial 5" already names the
  injection trial ([../injection-trial/](../injection-trial/README.md), cited so in 0014 and 0015),
  and "trial 6" names [the blind-mapping trial](../blind-mapping-trial/README.md). Step 3 renumbered
  it trial 7 here, in the trial log and in #106's title.
- **No exemption kind means "review pending".** `legacy` is defined as "the map predates this
  gate", which is not true of a new map. It is the only kind that names a tracking issue, so it was
  used between steps 2 and 3, with a reason saying the kind was a misfit. Step 3 replaced it with a
  `blind-second-mapping` review.

## Follow-ups for later steps

- **Step 3 (blind second mapping):** done, in [blind-mapping/](blind-mapping/README.md). The mapper
  had no README and no SRD-derived example, and got the rendered pages 13–16 beside the text, because
  of finding 1.
- **Step 4 (publish):** `pack-map.py` writes `<license type="expression">Apache-2.0</license>` for
  every map, and no nuspec field carries the CC-BY attribution. The map quotes CC-BY text, so the
  package needs the attribution statement: at least in `<description>` or a packaged
  `NOTICE`/readme, and probably a licence expression covering both (`Apache-2.0 AND CC-BY-4.0`).
  Nuspec has a `<copyright>` element, but the SRD's terms ask for its statement and no other
  attribution, so the statement's exact wording should go where it is carried. Not changed here.
- The pointer phrase list (finding 4) and a same-corpus-outside-extent relation (finding 3) are
  candidate issues.
