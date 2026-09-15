# Trial: the same corpus at two dates

Third run of [the method](../../docs/method.md), and the first to exercise the temporal
axis rather than assume it works. Same corpus as [trial 1](../faa-part-107/README.md),
pinned twice.

**Corpus:** 14 CFR Part 107, at `2020-01-01` and `2026-01-01` — either side of Amendment
107-8 (86 FR 4382, January 2021), which rewrote night operations and added subpart D.

**Slice:** the same twelve sections both times, mapped independently against each text.

**Result:** 44 sections → 61. Of the twelve mapped, **eight unchanged, four changed, none
removed.** 39 entries in 2020, 47 in 2026 — 23 and 24 as first mapped, before
[0005](../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md) split the
delegated standards into entries of their own,
[#26](https://github.com/brandonifco/rules-factory/issues/26) added the fifth,
[0008](../../docs/decisions/0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md)'s
procedure split `well-clear` and `prominent-objects` out as gaps, and
[0010](../../docs/decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md) split the ten
terms [#11](https://github.com/brandonifco/rules-factory/issues/11) had been open over into
five assertions and three gaps, one paragraph that splits into one of each, and one term
that turned out to be part of another entry's measure — and gave § 107.29(d) the entry
[#28](https://github.com/brandonifco/rules-factory/issues/28) asked for. **The entry count has
grown by more than half over four passes and the corpus has not moved once.** What keeps being
re-mapped is the map. Since then the 2026 map gained five entries from its
[blind second mapping](../faa-part-107/blind-mapping/) and #116, and both maps gained the two
`scope: out` waiver entries of
[0021](../../docs/decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md) — the 2020
map a pass later, read from its own text: see [waivers at two dates](#waivers-at-two-dates).

```
$ python3 examples/faa-part-107-temporal/diff-maps.py \
      examples/faa-part-107-temporal/corpus-map-2020-01-01.json examples/faa-part-107/corpus-map.json
2020-01-01  ->  2026-01-01

  ADDED    flash-rate-sufficient  (The anti-collision lighting has a flash rate sufficient to avoid a collision)
             suspendedBy None -> ['waivable-regulations']
  ADDED    knowledge-recency  (Aeronautical knowledge recency)
  ADDED    moving-aircraft-operation  (Operation from a moving aircraft)
             suspendedBy None -> ['waivable-regulations']
  ADDED    night-training-completed  (The remote pilot in command has completed the knowledge test or training for night operation)
  ADDED    night-waiver-bar  (No night operation after May 17, 2021 under a waiver issued before April 21, 2021)
  ADDED    night-waiver-termination  (Termination of night waivers issued before March 16, 2021)
  ADDED    operating-limitations  (The operating limitations are complied with)
             suspendedBy None -> ['waivable-regulations']
  ADDED    subpart-d-categories  (Operational categories for flight over human beings)
  CHANGED  anti-collision-lighting: name, evidence, note, locator, dependsOn
             name 'Anti-collision lighting during civil twilight'
               -> 'Anti-collision lighting is fitted and visible for 3 statute miles'
  CHANGED  civil-twilight-alaska: suspendedBy
             suspendedBy ['waivable-regulations'] -> None
  CHANGED  civil-twilight-operation: evidence, dependsOn, crossReferences
  CHANGED  civil-twilight-window: suspendedBy
             suspendedBy ['waivable-regulations'] -> None
  CHANGED  cloud-clearance: clarity, note, ambiguity
             clarity clear -> ambiguous
             ambiguity None -> ('unresolved', 'RequiresInterpretation', 'The two minimums are joined by "and" and no clearance above …')
  CHANGED  direct-participation: evidence
  CHANGED  intensity-reduction-in-interest-of-safety: evidence, note, locator
  CHANGED  moving-vehicle-operation: name, evidence, note
             name 'Operation from a moving vehicle or aircraft'
               -> 'Operation from a moving land or water-borne vehicle'
  CHANGED  night-operation: name, evidence, note, dependsOn, suspendedBy, crossReferences
             suspendedBy ['waivable-regulations'] -> None
             name 'Night operation is prohibited'
               -> 'Operation at night'
  CHANGED  over-human-beings: evidence, note, dependsOn, crossReferences
  CHANGED  preflight-actions: evidence, note, dependsOn, crossReferences
  CHANGED  reasonable-protection: evidence, note
  CHANGED  single-aircraft: evidence, note
  CHANGED  speed-limit: clarity, note, ambiguity
             clarity clear -> ambiguous
             ambiguity None -> ('unresolved', 'RequiresInterpretation', 'The limit is printed in two units that are not equal — 87 kn…')
  CHANGED  speed-within-limit: note
  CHANGED  sufficient-available-power: evidence
  CHANGED  visual-observer-conditions: note
  CHANGED  waivable-regulations: evidence, note, crossReferences
  CHANGED  waiver-policy: note
  CHANGED  weather-minimums-met: note
```

More entries report an `evidence` change than before, and that is a consequence of
[#18](https://github.com/brandonifco/rules-factory/issues/18) rather than of the corpus: now
that `evidence` holds the corpus's own words, **any rewording of a mapped passage moves it**.
A summary of what a passage shows survives a rewrite of the passage; a quote does not. That
makes the field a text-diff of the mapped slice, which is more than it was and worth knowing
before reading the output — `civil-twilight-operation`, for instance, changes only because
§ 107.29(b) gained the flash-rate clause and the extinguish bound.

Both maps' citations are checked against the corpus by
[check-locators-section.py](../faa-part-107/check-locators-section.py), which reads a
`section-designation` locator by containment rather than by page marker — see
[trial 1's README](../faa-part-107/README.md#is-a-section-citation-checkable) for why that is
a different tool and not a flag on the shipped one:

```
$ python3 examples/faa-part-107/check-locators-section.py \
      examples/faa-part-107-temporal/corpus-map-2020-01-01.json \
      examples/faa-part-107-temporal/part107-2020-01-01.xml
locators ok (all 39 checked against the section tree); coverage ok (all 12 sections of the declared extent are reached)
```

## Waivers at two dates

[0021](../../docs/decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md) recorded
waivers in the 2026 map and left this one alone, because its § 107.205 is a different list.
It is now recorded from the 2020-01-01 text, not copied from the 2026 map: the same two
`scope: out` entries, `waiver-policy` (§ 107.200) and `waivable-regulations` (§ 107.205), and
`suspendedBy: [waivable-regulations]` on every entry whose locator states a regulation the 2020
list names. § 107.200 reads the same at both dates. At 2020 it sits in "Subpart D - Waivers";
the amendment made subpart D the operational categories and moved waivers to subpart E.

§ 107.205 differs in two items. At 2020, (b) is **"Section 107.29 - Daylight operation"**, the
whole section; at 2026 it is "Section 107.29(a)(2) and (b)", the lighting only. And 2020 has
no (j): § 107.145 does not occur anywhere in the 2020 part.

Both maps now have **27 suspended entries**, and they are not the same 27. With the new gate
printing in [diff-maps.py](diff-maps.py) (it used to print only the field name, which does not
say which way an edge moved), the waiver lines of its output, names dropped, are:

```
  ADDED    flash-rate-sufficient
             suspendedBy None -> ['waivable-regulations']
  ADDED    moving-aircraft-operation
             suspendedBy None -> ['waivable-regulations']
  ADDED    operating-limitations
             suspendedBy None -> ['waivable-regulations']
  CHANGED  civil-twilight-alaska: suspendedBy
             suspendedBy ['waivable-regulations'] -> None
  CHANGED  civil-twilight-window: suspendedBy
             suspendedBy ['waivable-regulations'] -> None
  CHANGED  night-operation: name, evidence, note, dependsOn, suspendedBy, crossReferences
             suspendedBy ['waivable-regulations'] -> None
  CHANGED  waivable-regulations: evidence, note, crossReferences
```

Read against the two texts, the six lines are three different kinds of difference, and only
one kind is the amendment:

| entry | waivable in 2020 | in 2026 | why |
|---|---|---|---|
| `night-operation` | yes | no | **the amendment.** 2020 lists § 107.29 whole, so a waiver reaches the night prohibition itself. 2026 lists only (a)(2) and (b), so a waiver reaches night lighting and (a)(1)'s training condition still applies. |
| `civil-twilight-window`, `civil-twilight-alaska` | yes | no | **the amendment.** § 107.29(c) is inside the listed section at 2020 and outside the listed paragraphs at 2026. |
| `flash-rate-sufficient` | — | yes | **the amendment**, but of § 107.29 rather than § 107.205: the flash-rate clause does not exist at 2020. |
| `moving-aircraft-operation` | — | yes | **the map.** § 107.25 is listed whole at both dates; the 2026 blind second mapping split `moving-vehicle-operation` in two, and the 2020 `moving-vehicle-operation`, which is suspended, still states both limbs. |
| `operating-limitations` | — | yes | **the map.** § 107.51 is listed whole at both dates; only the 2026 map has an entry for its introductory text. The 2020 map's missing entry is recorded as an `unmapped` item on `waivable-regulations` and left to the blind second mapping it owes. |
| § 107.205(j), § 107.145 | — | listed | **the amendment**, and invisible to the differ: (j) suspends nothing in scope at 2026, so no entry's edge moves. It shows only as `waivable-regulations: evidence`. |

So the same count hides a narrowing: **a 2020 waiver of § 107.29 lifted the night ban, and a
2026 one cannot.** What replaced it is a conditional permission (§ 107.29(a)(1)-(2)) whose
lighting half is waivable and whose training half is not. And half of what the differ reports
as a change in the waiver set is the two maps having been read to different depths — the
finding this trial keeps making, now about a gate rather than an entry.

**Four cross-references reviewed.** #116 (0026) added four `crossReferences` to this map, taken
from the 2026 map's answers to the same words, and nobody read them against the 2020 text.
Three hold: `visual-line-of-sight` "the ability described in paragraph (a) of this section" →
`unaided-visual-contact`, `visual-observer-conditions` "in the manner specified in § 107.31" →
`visual-line-of-sight`, and `civil-twilight-operation` "as defined in the Air Almanac" →
`civil-twilight-alaska`. One did not: `civil-twilight-operation`'s "paragraph (b) of this
section" was `unmapped` because "no other entry states (b) whole", and at 2020
`anti-collision-lighting` cites § 107.29(b) and quotes all of it. It now resolves to
`anti-collision-lighting`. `visual-observer-conditions`' note still said its pointer was outside
the checker's list and nothing demanded a declaration; that stopped being true with 0026, and
the sentence is replaced.

**Checked against every rule added since.** The map was last changed by 0026, which is the newest
checker change, so every rule — 0020's extent and introductory-text grammar, 0024's extraction
rules, 0025's `assertedBy` and draws, 0026's declared pointer phrases — already runs on it, and
nothing in `tools/checkmap/` or `check-locators-section.py` names this map, a date or an
exemption. The six checks that report NOT VERIFIED on it report the same on the reviewed 2026
map, each because no entry carries the field it reads (`derivedFrom`, `extraction`, `implemented`,
`fate: decision`, `ambiguity.conflict`, `absentFrom`). `gates` was a seventh until this change.

**Review.** The map's `legacy` exemption stands: none of this is a blind second mapping. The
change itself was read by a reviewer in a separate context, given only the 2020 text of the
eleven sections involved and a before/after of the 29 entries changed or added; the verdict is
[independent-verdict-2020-waivers.json](independent-verdict-2020-waivers.json), and `review.json`'s
exemption names it and the digest it covers. Round 1: all 29 entries agreed; one cross-reference
disagreed (the Air Almanac one, as circular) and five nits. Two nits were adopted — the unmapped
`Section 107.51` item and a proviso sentence that claimed more than the text — and the
disagreement was withdrawn in round 2 once the reviewer had the method's rule that a pointer
into a corpus not admitted is answered by `definedElsewhere`, which here lives on
`civil-twilight-alaska`. Round 2, on the final bytes: 29 of 29 entries, 4 of 4 cross-references,
and completeness agree.

## The finding worth the trial, withdrawn and replaced

**Withdrawn: "an amendment turned a rule the engine computes into one that demands a caller's
assertion."** It has been stated three times, and it never had the premise it needed.

The premise was that in 2020 § 107.29(a) — "No person may operate a small unmanned aircraft
system during night" — was cleanly computable: *given the time, the engine answers*. It was not.
**§ 107.3 defines six terms at that date and seven in 2026, and `night` is not among them in
either**, read directly from both corpus files. The 2020 rule *is* the undefined word and nothing
else. An engine built from that map would decide night operations with no definition of night,
and the comparison the finding rested on was between two entries that are both incomplete —
[#33](https://github.com/brandonifco/rules-factory/issues/33).

Both entries are now `definedElsewhere` against 14 CFR § 1.1, which § 107.3 puts in force for
this part, and both decline with `MissingRulesData`. See the entry notes for the limit on that
claim: § 107.3's clause is a general priority rule, so it becomes checkable only when `cfr-14-1`
is admitted. It is listed as a `reference` in both manifests and admitted in neither.

**What the diff now shows, stated plainly.**

| | 2020 | 2026 |
|---|---|---|
| § 107.29(a) turns on | "night", undefined in the corpus | "night", undefined in the corpus |
| the engine's answer | `MissingRulesData` | `MissingRulesData` |
| what else the rule defers | nothing | the flash rate, to the caller (`flash-rate-sufficient`) |
| what else the rule gained | — | a computable training date, and a bound on reducing intensity |

So the amendment **added a delegated standard to a rule that was already undecidable, for a
different reason, at both dates**. That is a weaker claim than the one withdrawn and it is the
one the corpus supports. `flash-rate-sufficient` is still an entry the 2020 map has no
counterpart for, and the differ still reports it as an addition rather than as a change of
`clarity` — that half never depended on the 2020 entry being computable.

**The direction-of-travel claim survives on its own evidence**, which is the second instance
below rather than this one: a map is a statement about one text, and what an engine can answer
alone changes with the text without the engine changing at all.

**Why it took three passes, which is the part worth keeping.** Each restatement was forced by
looking at a field nothing checks. The first reading recorded the amendment as introducing an
ambiguity; 0005 rejected that, because a delegated standard is not a defect in the text. The
second kept `clarity` out of it and rested on "computable in 2020". This one removes that, and
only because
[0008](../../docs/decisions/0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md)'s
procedure was applied to every entry rather than to the interesting ones. **`clarity` is the one
field nothing compares against the corpus**, and all three errors lived in it. The undefined-term
sweep behind this is in [trial 1's README](../faa-part-107/README.md#the-undefined-term-sweep):
49 terms, 21 that carry a rule, 3 recorded wrong — and then **seven more**, once 0010
re-derived the ten rows the sweep had deferred to #11 instead of running the gate on them.
Ten of twenty-one, which is the number to quote.

**A finding the corrected maps make visible.** `well-clear` and `prominent-objects` are new
entries in **both** maps, identical at both dates, so the differ reports them nowhere. That is
the point: these gaps are not amendments, they are two places where the corpus was open all
along and the map said otherwise. A diff of two maps can only show what the mapper noticed at
both dates, and it is silent by construction about what was missed at both.

**0010 turned that from an observation into a measurement.** It added ten entries to each map
and **eight of the ten are identical at both dates** — only `direct-participation` and
`sufficient-available-power` differ, and both differ in punctuation and paragraph lead-in
rather than in rule. So twenty entry instances appeared, sixteen of them invisible to the
differ, and every one was a place where both maps agreed and both were wrong. The ratio is
the finding: **what a two-date diff cannot see is not a corner case here, it is most of what
the passes have found.**

**A second instance of the same shape, found by [#26](https://github.com/brandonifco/rules-factory/issues/26).**
`intensity-reduction-in-interest-of-safety` — the remote pilot's judgement that reducing the
anti-collision lighting is in the interest of safety — exists at both dates and moved in a way
worth separating from the one above. In 2020 the clause sits in § 107.29(b) alone and grants
the permission **unbounded**: "may reduce the intensity of the anti-collision lighting". By
2026 it sits in § 107.29(a)(2) *and* (b), identically worded, and reads "may reduce the
intensity of, but **may not extinguish**". So the amendment did the opposite of the
`flash-rate-sufficient` case: it added a bound the engine *can* compute around a judgement it
already could not. The delegated judgement is unchanged; the rule that consumes it gained a
constraint. Both directions exist, and a map that recorded only the first would have suggested
they do not.

## Three more, smaller

**A stable id can hide a reversal.** `night-operation` exists in both maps with the same id
and opposite meaning — prohibition against conditional permission. Diffing entry *lists*
would have reported nothing. Only diffing entry *content* caught it. Ids should stay stable
across versions, which is what makes diffing possible; but stability is exactly what lets a
reversal pass unnoticed if the diff is shallow.

**A new section reached into an old one.** § 107.39 gained a third exception, "(c) meets the
requirements of at least one of the operational categories specified in subpart D" — a
subpart that did not exist in 2020. Amendments are not confined to the sections they add.
Re-mapping only the changed sections would have caught this one, because § 107.39 itself
changed; the risk is the case where a new section is referenced by text that did not
otherwise move.

**The wording of § 107.35 narrowed** from "may not operate" to "may not manipulate flight
controls" without changing what the map records, because the map records the rule and not
its phrasing. Correct, and worth noting: a text diff would have flagged it, a map diff did
not, and the map diff is right — but only if the mapper noticed and judged.

## What the kernel got right, tested rather than assumed

`ReplayCompatibilityIdentity` **refuses two baselines for the same corpus**, including at
two different dates. Run directly against the published 0.2.0 package:

```
two dates are two baselines: True
BOTH-AT-ONCE: refused -> sourceBaselines contains more than one entry for corpus
              'cfr-14-107'; a locator names a corpus by id alone, so duplicate ids
              make citations ambiguous
one run per date, and they differ: True
```

That constraint was added on reasoning, not evidence, and this is the first test of it. It
holds: a `SourceLocator("cfr-14-107", "§ 107.29")` would be genuinely ambiguous about which
version it cited if both were present, and § 107.29 is precisely a section where the two
versions say opposite things.

An engine answering "was this legal then, and is it legal now" composes **two runs with two
identities**, not one run with two baselines. That is the right shape, and the kernel
enforces it.

## What broke

**A map did not record which corpus version it described.** The first run of the differ
printed `2020-01-01 -> ?`, because `asOf` lived in the manifest and the map carried no
reference to the baseline it was built against.

A map is only true of one corpus state. Without a stamp it cannot be compared to another
map, cannot be checked against the corpus it claims to describe, and silently outlives the
text it was written from. Maps now carry `baseline` — `contentHash`, `hashDerivation`, and
`asOf` when the corpus has one.

**And the differ itself was wrong.** It compared only the first 60 characters of an
ambiguity's question, so a real change to `over-human-beings` — where the 2026 text adds a
third exception and the 2020 note says "there is no third exception in this version" —
did not appear in the output at all. The truncation was for readability and it cost a
finding. A diff that abbreviates what it compares is not a diff.

Recorded rather than quietly fixed, because it is the same failure that has recurred
throughout this project: a check whose fidelity is lower than its apparent confidence.

**And it happened again, in the same file, to a field added after it.**
[0009](../../docs/decisions/0009-absence-is-a-verdict-with-evidence.md) added
`crossReferences` and `absentFrom`, and neither was ever added to what the differ compares.
So when 0010 changed `night-operation`'s carve-out from `unmapped` to `resolvedBy` — which
is the whole of [#28](https://github.com/brandonifco/rules-factory/issues/28), the finding
this trial's own cross-reference obligation exists for — **the differ printed nothing**. It
is fixed here, and the fix is one line per field. What is worth keeping is why it was
invisible: every *other* field the schema defines was already compared, so the output looked
complete, and a diff that is complete except for the newest field is exactly the shape that
survives review. **A schema change is a change to everything that reads the schema**, and this
repository has now missed that twice in one file.

That change is now beyond the differ's reach to miss, for a reason worth naming. § 107.39(c)
used to be recorded as a second sentence inside an `ambiguity.question` — prose, which only a
full-text comparison could catch. Under 0005 the two causes are two entries, and the deferral
is a `dependsOn` edge to `subpart-d-categories`. The differ reports it as a dependency change,
which is what a structural fact should look like to a diff. `definedElsewhere` is compared
whole for the same reason, alongside `beyondAdapter`.

## Cost

Fetching both versions, slicing, mapping the second text and diffing: under an hour, and
most of that was reading the 2020 text closely enough to be sure which differences were
real. Re-mapping was much cheaper than mapping, because the question is "what moved" rather
than "what is here" — which suggests a maintained map is considerably cheaper to keep
current than to create.
