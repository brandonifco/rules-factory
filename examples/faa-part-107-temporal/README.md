# Trial: the same corpus at two dates

Third run of [the method](../../docs/method.md), and the first to exercise the temporal
axis rather than assume it works. Same corpus as [trial 1](../faa-part-107/README.md),
pinned twice.

**Corpus:** 14 CFR Part 107, at `2020-01-01` and `2026-01-01` — either side of Amendment
107-8 (86 FR 4382, January 2021), which rewrote night operations and added subpart D.

**Slice:** the same twelve sections both times, mapped independently against each text.

**Result:** 44 sections → 61. Of the twelve mapped, **eight unchanged, four changed, none
removed.** 37 entries in 2020, 40 in 2026 — 23 and 24 as first mapped, before
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
re-mapped is the map.

```
2020-01-01  ->  2026-01-01

  ADDED    flash-rate-sufficient
  ADDED    night-waiver-termination
  ADDED    subpart-d-categories
  CHANGED  anti-collision-lighting: name, evidence, note, locator, dependsOn
  CHANGED  civil-twilight-operation: evidence
  CHANGED  direct-participation: evidence
  CHANGED  intensity-reduction-in-interest-of-safety: evidence, note, locator
  CHANGED  night-operation: name, evidence, note, dependsOn, crossReferences
  CHANGED  over-human-beings: evidence, note, dependsOn
  CHANGED  preflight-actions: evidence, note, dependsOn
  CHANGED  reasonable-protection: evidence, note
  CHANGED  single-aircraft: evidence, note
  CHANGED  sufficient-available-power: evidence
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
locators ok (all 37 checked against the section tree)
```

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
