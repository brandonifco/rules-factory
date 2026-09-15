# Trial: the method by hand, against 14 CFR Part 107

The first run of [the method](../../docs/method.md) against a real corpus. Done by hand,
before building anything to automate it, to find out which phases survive contact.

**Corpus:** 14 CFR Part 107 — Small Unmanned Aircraft Systems, as of 2026-01-01, fetched
from the eCFR versioner API. Public domain, `pin-in-repo`, citations by section
designation.

**Slice mapped:** twelve sections of subpart B, the operating rules — 8,887 characters,
readable in one sitting. The engine this would produce answers one question: *may this
flight operate?*

**Result as mapped:** 24 entries. 6 values, 18 operations. 19 clear, 5 ambiguous. 3 declined.

**Result as it stands**, after
[0005](../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md) landed
findings 1–4 in the map itself,
[#26](https://github.com/brandonifco/rules-factory/issues/26) added the fifth delegated
judgement, and
[0008](../../docs/decisions/0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md)'s
procedure was applied to every entry
([#33](https://github.com/brandonifco/rules-factory/issues/33),
[#34](https://github.com/brandonifco/rules-factory/issues/34)), and
[0010](../../docs/decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md) settled the
sweep's residue and #28's missing carve-out, and the
[blind second mapping](blind-mapping/README.md) (0014) added four entries and three open
questions. [0021](../../docs/decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md)
then recorded waivers ([#61](https://github.com/brandonifco/rules-factory/issues/61)). Two
`scope: out` entries cite §§ 107.200 and 107.205, and 27 entries name the waiver list in
`suspendedBy`: **46 entries. 6 values, 30 operations, 10 assertions. 36 clear, 10 ambiguous. 6
declined.** [0026](../../docs/decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)
added `knowledge-recency` (§ 107.65, `scope: out`), the target of § 107.29(a)(1)'s "under § 107.65",
once the CFR's declared pointer phrases made the check see it: 47 entries, 31 operations, 7 declined. The delegated standards are entries split
out of the rules that consume them; so are the gaps the sweep below found. `right-of-way`
stopped being an assertion, `night-operation` stopped being a rule this map could claim to
have derived from the text it admitted, and the four entries #11 had been open over since
this trial turned out to hold **both** answers rather than either.

**The map is a third larger than the sections it reads suggest**, and that is the cost of
`kind` being entry-level: twelve sections, forty-four entries before the two waiver entries, of which twenty are an assertion
or a gap — seventeen of those split out of a rule that consumes them, and three gaps that are
whole entries: `moving-vehicle-operation`, and the two figures the blind second mapping found
open, `speed-limit` and `cloud-clearance`.

Every entry's `evidence` is now a **verbatim span of the corpus**
([#18](https://github.com/brandonifco/rules-factory/issues/18)), and the mapper's summary of
what that span shows has moved to `note`. See *Is a section citation checkable?* below for
what that buys and what it does not.

Chosen deliberately to stress the parts of the design that tabletop corpora flatter: no
dice, no pages, no printing, and effective dates that bite.

## What held

**The locator grammar.** `§ 107.51(b)(2)` is precise, stable and machine-addressable, and
nothing in the pipeline wanted a page number. The kernel's decision to keep citations
opaque and adapter-defined is correct, and this is the first evidence for it that did not
come from a book.

**Bounded extraction.** Twelve sections was the right size — enough to find real structure,
small enough to hold. An unbounded read of all 61 sections would have produced a worse map.

**Enumerate before classifying.** The method warns against doing both in one pass. The pull
to classify while reading was strong and resisting it was right: three entries changed
classification once the whole slice was in view, and two sections turned out to be one
entry rather than two.

**The value/operation split, where it applies.** § 107.51 separates cleanly: four figures
the corpus states, three operations that compare against them. Splitting the figure from
the comparison is not bureaucracy — the altitude limit has three distinct figures inside one
paragraph, and a single "400 feet" entry would have lost two of them.

**Ratio.** Twelve sections produced twenty-four entries, almost exactly 2:1 — twenty-nine once
0005 split the delegated standards out and 0008's procedure split the gaps, and **forty** once
0010 split the rest. That is 3.3:1, and the earlier estimate was low by a third because every
pass so far has found more standards to split, never fewer. Useful for estimating: this slice
is 1/5 of the part, so the whole is roughly 200 entries — stated as a moving number, since
it has moved upward three times.

## What broke

### 1. `value` and `operation` are not exhaustive. The missing kind is an asserted fact.

The largest single finding. A great deal of Part 107 is neither a figure the engine stores
nor a computation it performs — it is **a fact about the world the caller must assert**.

§ 107.31 requires that a person *was able to see* the aircraft. § 107.33 requires that
communication *was maintained*. § 107.49 lists six things the remote pilot must *have done*
before flight. No engine can compute any of these. What an engine can do — and what makes
it useful — is **demand the assertion, record who made it, and refuse to proceed without
it**.

I marked eight entries `operation` with an explanatory note, which is wrong. They are a
third kind. Calling them operations implies the engine computes something it cannot.

This is not a regulatory quirk. A tabletop engine has the same shape wherever a rule turns
on what the table agreed, and it was invisible in the two existing engines because both
compute from complete state.

**The map needs `kind: assertion`,** and the method needs a paragraph on what an engine owes
an asserted fact: demand it, attribute it, store it, never infer it.

### 2. Judgement deliberately vested in a person is not ambiguity

§ 107.29 permits the remote pilot to reduce anti-collision light intensity "if he or she
determines that, because of operating conditions, it would be in the interest of safety to
do so."

Nothing here is ambiguous. The corpus is entirely clear: the decision belongs to the pilot.
Classifying it `RequiresInterpretation` would misrepresent a deliberate delegation as a
defect in the text.

It is an assertion — see finding 1 — and the two findings converge on the same fix.

**And it had no entry until [#26](https://github.com/brandonifco/rules-factory/issues/26).**
This clause is the example [method.md](../../docs/method.md) and
[corpus-map.md](../../docs/corpus-map.md) both reach for when explaining `kind: assertion`,
and in both maps it lived in a prose `note` on `anti-collision-lighting` — the one case in
the corpus that unambiguously satisfies the category was the one case not mapped to it. It is
now `intensity-reduction-in-interest-of-safety`, and `anti-collision-lighting` depends on it,
which is the `speed-limit` / `speed-within-limit` shape 0005 names. The computable half stays
where it was: *may reduce, may not extinguish* is a bound the corpus states, and an entry
reclassified whole would have thrown it away.

The 2020 text states the clause **without that bound** — "may reduce the intensity of the
anti-collision lighting", full stop — and states it in § 107.29(b) only. Amendment 107-8 both
repeated the sentence into § 107.29(a)(2) and added the prohibition on extinguishing, so the
consuming rule gained a computable constraint at the same moment the delegated judgement
gained a second home. The differ reports that as `locator`, `evidence` and `note` moving on
one entry.

### 3. A standard is not a gap

`well clear` (§ 107.37(a)), `so close as to create a collision hazard` (§ 107.37(b)),
`reasonable protection` (§ 107.39(b)), `flash rate sufficient to avoid a collision`
(§ 107.29(a)(2)).

The method's Phase 4 treats ambiguity as something to be resolved — by a recorded decision
or by declining at runtime. But a regulator writing "well clear" has not been vague by
accident. The standard is the rule, chosen over a number on purpose, and an engine that
resolved it to a number would be substituting its own rule for the corpus's.

Both available fates are still wrong-shaped for it. `RequiresInterpretation` is the closest
and it implies the corpus failed to say something. The honest reading is that the corpus
said exactly what it meant, and what it meant is not computable. I used
`RequiresInterpretation` for four entries here and flagged each, but the method should
distinguish a *gap* from a *standard*.

**Settled by [0005](../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md).**
A delegated standard is `kind: assertion`, and because `kind` is entry-level it is an entry of
its own wherever the rule around it computes something. All four are now in the map that way:
`well clear` and `so close as to create a collision hazard` are the whole of § 107.37(a) and
(b), so those entries are assertions themselves; `reasonable protection` and `flash rate
sufficient` are one clause of a rule that still computes, so they became
`reasonable-protection` and `flash-rate-sufficient` and the rules depend on them.

The test the decision gives is whether the corpus names a decider. Taken literally it is thin
against this text — § 107.37 writes "unless well clear" without saying who judges it, and so
does § 107.29(a)(2) of the flash rate. What actually separates those four from § 107.25 is
that each states a **standard the operator must meet**, where "sparsely populated area" is an
undefined factual predicate vested in nobody. `moving-vehicle-operation` stays a gap on either
reading.

**And that separation did not survive.** Five one-sentence tests have now failed, and
[0008](../../docs/decisions/0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md)
replaces them with an ordered procedure whose last gate requires the corpus to state, **in the
same constituent as the open term**, either the measure or the set of values the term may take.
Three of the four above quote one — "sufficient **to avoid a collision**", "reasonable protection
**from a falling small unmanned aircraft**", "so close **as to create a collision hazard**".
**`well clear` quotes neither.** § 107.37(a) is a definition whose definiens has two coordinate
conjuncts; "must give way" is a second obligation, not what the clearance is measured against;
the term occurs exactly once in the corpus and § 107.3 does not define it. So it is a gap, it is
the same shape as "sparsely populated area", and the procedure returns the same answer for both —
which is the first time any formulation has. `right-of-way` is now an `operation` over its two
computable enumerations, `well-clear` is its own entry with `fate: unresolved`, and what
separated them before was aviation practice, which is in neither text.

### 4. External corpora are pervasive, and the manifest cannot describe one it has not admitted

Three of twelve sections defer their meaning elsewhere: § 107.36 defines hazardous material
by reference to 49 CFR 171.8; § 107.29(c)(3) defers Alaskan civil twilight to the Air
Almanac; § 107.39(c) defers to subpart D.

At runtime this works — the entries become `MissingRulesData` and `OutsideCurrentScope`,
which is exactly right. But the *manifest* has no way to record "this corpus is referenced
and not admitted", so the reason an entry is declined lives only in that entry's prose.

A quarter of the sections in this slice needed it. A `references` list in the manifest, with
admitted and unadmitted corpora distinguished, would make the boundary of the engine
inspectable instead of inferred.

**Both halves have since landed.** The manifest carries `references`, and
[0005](../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md) added
`definedElsewhere`, which names one of them from the entry: `hazardous-material` →
`cfr-49-171`, `civil-twilight-alaska` → `air-almanac`. The reason no longer lives in prose,
and neither entry carries an `ambiguity` block, because neither is ambiguous. The third
deferral, § 107.39(c) to subpart D, is not an unadmitted corpus at all — it is this corpus,
out of scope, and it is `subpart-d-categories`. Subpart E is the same kind of boundary, reached
the other way: a certificate of waiver suspends the rules § 107.205 lists, so `waiver-policy` and
`waivable-regulations` are `scope: out` entries that 27 in-scope entries name in `suspendedBy`
([0021](../../docs/decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md)).

**Three of twelve was an undercount, and the fourth is the one that mattered.** § 107.3 puts
"the definitions specified in § 1.1 of this chapter" in force for the whole part, which is a
deferral to an unadmitted corpus covering *every* term § 107.3 does not define — including
`night`, which § 107.29 turns on entirely at both dates. Both manifests now list `cfr-14-1`
alongside `cfr-49-171` and `air-almanac`, admitted in neither, and `night-operation` names it.
It is a weaker citation than the other two: § 107.36 and § 107.29(c)(3) each name the corpus
**for the term**, where § 107.3 states only a priority rule and leaves which terms § 1.1 supplies
unknowable until it is admitted. Recorded in the entry's note, because a reference that resolves
in the manifest can still be a claim nobody has checked.

### 5. Temporal handling covers one of two temporal things

`asOf` pins which text is in force — that works, and is the whole reason the kernel has it.

But the text contains its own dates. § 107.29(a)(1) requires training completed "after
April 6, 2021"; § 107.29(d) terminates certain waivers on dates in 2021. Those are ordinary
operations over a date input, not corpus versioning — but a reader of the method could
easily conflate them, and the method never mentions the second kind.

## Is a section citation checkable?

[#18](https://github.com/brandonifco/rules-factory/issues/18) asks for the Part 107 maps to
get the same treatment as the backgammon map, "or a recorded reason their locator grammar
cannot be checked this way". This is that record, and the answer is **yes, checkable — and
not by the same tool**.

`tools/check-locators.py` verifies a `printed-page` citation by finding the entry's evidence
in a flat text corpus, walking back to the nearest `{NNN}` page marker, and comparing. Part
107 has no page markers, and there is no way to give it any: a section designation is not a
position in a stream. Three things differ, and none of them is a regex the shipped tool could
be handed.

| | backgammon | Part 107 |
|---|---|---|
| corpus reader | flat text | eCFR XML, parsed as a tree |
| position model | walk back to the nearest marker | the element that **encloses** the text |
| citation grammar | `p. 273` | `§ 107.29(a)(2), (b)`, with ranges, lists and `subpart D` |

The `--marker-re` / `--page-re` flags parameterise the wrong layer. They vary the *pattern* a
positional model looks for; Part 107 needs a different model. Pointing the shipped tool at
`part107.xml` finds no markers, reports `no page markers found; nothing to check`, and exits
2 — which is the correct behaviour and not a check.

So the generalisation is the **principle**, not the code: resolve a quote to a structural
position in the corpus and compare that position to the citation. A proof of concept lives at
[check-locators-section.py](check-locators-section.py), here rather than in `tools/` because
`tools/` is not this directory's to change. It runs:

```
$ python3 examples/faa-part-107/check-locators-section.py \
      examples/faa-part-107/corpus-map.json examples/faa-part-107/part107.xml
locators ok (all 40 checked against the section tree)
```

**Containment makes it stricter than the page version, in three places.**

- A page marker is positional, so a quote straddling a break leaves two citations honest and
  the checker has to accept either. An element encloses its text: a quote is inside the cited
  paragraph or it is not, and there is nothing to concede.
- The page checker takes the **first** `find` hit. This corpus repeats whole sentences
  verbatim — § 107.29(a)(2) and § 107.29(b) state the anti-collision sentence and the
  reduce-intensity sentence identically — so a first-hit probe would verify such a quote
  against whichever copy came first and call it checked. Here a quote occurring *n* times must
  have all *n* occurrences inside the citation. Citing the reduce-intensity sentence to
  § 107.29(b) alone fails, correctly, because it also sits in (a)(2).
- The page checker matches the longest contiguous prefix and reports coverage, because it was
  retrofitted onto evidence that was never a quote. Here a fragment either appears or the
  entry is unchecked and the run fails. ` ... ` splits a quote into fragments, each of which
  must appear, in corpus order, inside the citation — the ellipsis rule #18 asks for, proposed
  from this end rather than settled.

**The one inference, stated where the claim is.** eCFR XML flattens a section's paragraphs
into sibling `<P>` elements with the designator left in the text, so `(b)`, `(1)` and `(2)`
are siblings and the tree has to be rebuilt from the designator forms. `(i)`, `(v)` and `(x)`
are both letters and roman numerals; the tool resolves one only when exactly one open run it
could continue, and **refuses the paragraph otherwise** rather than picking a reading. Across
both corpora — 352 and 215 paragraphs — nothing is refused, and § 107.135(c)(1)'s `(i)`–`(v)`
run is the case that exercises it.

**What it does not check, and this is the limit that matters.** It proves a quote sits where
the citation says. It cannot prove the quote is the *right* passage for the entry: a mapper
who cites the wrong section and then quotes from that section passes. The backgammon failure
mode — thirteen page numbers wrong by a page or two — is a *counting* error, and a section
designation is copied from a heading rather than counted, so that mode does not exist here.
What this check does catch is drift (a citation edited later while the quote stays put), a
paraphrase presented as evidence, and a quote that turns out to live in more places than the
citation admits.

Which is why the result is worth stating plainly: **40 of 40 citations in the 2026 map and 37
of 37 in the 2020 map verify, none was found wrong, and none was corrected** (44 of 44 in the
2026 map since the blind second mapping) — 29 and 27
before 0010's migration, and all twenty-one entries it added verified on the first run.
Against
backgammon the same class of check found thirteen errors in twenty-four. That is a fact about
the two locator grammars, not about the two mappers.

## The evidence sweep

`evidence` is specified as *"for a finite table: the whole table, not a sample."*
[#26](https://github.com/brandonifco/rules-factory/issues/26) named one entry whose evidence
dropped a case the section states — `moving-vehicle-operation`, "a moving land vehicle" where
§ 107.25(b) reads "moving land **or water-borne** vehicle" — and asked for the remaining
entries to be swept, because one instance found by accident is not a count.

**The count is 17: nine of twenty-six entries in the 2026 map and eight of twenty-four in the
2020 map**, the named instance included. Every one is fixed by #18's rewrite, since a verbatim
span of the cited passage cannot drop a case the passage states.

| entry | what the section states | what the evidence covered |
|---|---|---|
| `single-aircraft` | three roles: manipulating the controls, remote pilot in command, visual observer | the visual observer |
| `restricted-area-permitted` | two designations: prohibited, restricted | neither, only the permission axis |
| `moving-vehicle-operation` | land **or water-borne** vehicle | land |
| `right-of-way` | three protected kinds: aircraft, airborne vehicles, launch and reentry vehicles | "another aircraft" |
| `over-human-beings` | (b) a covered structure **or** a stationary vehicle | "the covered-structure case" |
| `anti-collision-lighting` | fitted, visible for 3 statute miles, **and** may be reduced but not extinguished | fitted, and the 3-mile figure |
| `visual-line-of-sight` | (b)(1) the remote pilot **and** the person manipulating the controls, or (b)(2) an observer | the remote pilot; an observer; neither |
| `visual-observer-conditions` | three requirements: communication, the pilot ensuring the observer can see, coordination | communication |
| `night-operation` (2026 only) | "Except as provided in paragraph (d)" | no mention of (d) |

Eight of the nine appear in both maps. `night-operation` differs because the 2020 rule is a
flat prohibition with no carve-out to drop.

**Three are judgement calls and are listed as hits deliberately rather than quietly.**
`over-human-beings`'s (c) case and `night-operation`'s (d) carve-out are each reachable as
another entry or another rule, so a reader could call them delegated rather than dropped; and
`restricted-area-permitted`'s two designations behave identically, so sampling them costs
nothing at runtime. They are counted because the test is what the cited passage *states*, not
what would have gone wrong — a sample that happens to be representative is still a sample, and
the entry that proved the point was the one where a reader decided "land vehicle" was close
enough.

**One further defect the sweep found, which is not a dropped case.** The 2020
`preflight-actions` evidence read *"Each of (a) through (e) asserted and unasserted. (f) is
reachable only through subpart D"* — and § 107.49 has no paragraph (f) at that date. That is a
case asserted about a text that does not state it, copied across from the 2026 map, and the
entry's own `note` contradicted it two lines later ("Five obligations"). A summary can claim a
case the corpus does not contain; a quote cannot.

## The undefined-term sweep

`clarity` is the one field nothing compares against the corpus, and the map was caught giving
**opposite verdicts on identical ground**: `moving-vehicle-operation` was `ambiguous` because
"sparsely populated area" is undefined, while `night-operation` was `clear` although "night" is
undefined in exactly the same sense — and in 2020 the undefined word *is* the entire rule.
[#33](https://github.com/brandonifco/rules-factory/issues/33) and
[#34](https://github.com/brandonifco/rules-factory/issues/34) each asked for the same thing from
opposite ends: not four fixes, but **every term every mapped entry relies on, against the terms
§ 107.3 defines.** One instance found by inspection is not a count — that is the argument that
turned #26's single dropped case into seventeen.

**§ 107.3 defines seven terms in the 2026 text and six in 2020** — control station, corrective
lenses, *declaration of compliance* (2026 only), small unmanned aircraft, small unmanned aircraft
system, unmanned aircraft, visual observer — and **night is not among them at either date**, read
directly from `part107.xml` and `part107-2020-01-01.xml`.

**The count is 49 distinct terms undefined by § 107.3 across the two maps' in-scope entries, of
which 21 carry a rule. Three of the 21 were recorded as needing nothing — six entry instances,
three per map.** The remaining 28 are disposed of before gate 3: 5 are fixed elsewhere in the
admitted corpus (`remote pilot in command` at §§ 107.12 and 107.19, `civil twilight` at
§ 107.29(c), `flight visibility` at § 107.51(c), *yielding the right of way* at § 107.37(a), the
knowledge test at § 107.65) and 23 are ordinary caller-supplied parameters that gate 1 stops —
groundspeed, altitude above ground level, a structure and its uppermost limit, a cloud, the
airspace class, a prohibited or restricted area, the three protected kinds and the three relative
positions in § 107.37(a), a human being, a covered structure, a stationary vehicle, whether the
vehicle is moving, whether lighting is fitted. **A parameter is not a rule and gets no entry**, as
`corpus-map.md` rules for `airspace-authorized`.

The 21 that carry a rule:

| term | entries relying on it | 0008 returns | recorded as | verdict |
|---|---|---|---|---|
| "night" | `night-operation` ×2 | gate 2 → `definedElsewhere`, 14 CFR § 1.1 | `clear`, computable | **wrong — fixed** |
| "well clear" | `right-of-way` ×2 | gate 3 → gap | `kind: assertion` | **wrong — fixed** |
| "prominent" | `weather-minimums-met` ×2 | gate 3 → gap | `clear` | **wrong — fixed** |
| "sparsely populated area" | `moving-vehicle-operation` ×2 | gate 3 → gap | gap, `unresolved` | agrees |
| "hazardous material" | `hazardous-material` ×2 | gate 2 → `definedElsewhere` | `definedElsewhere` | agrees |
| Alaskan civil twilight | `civil-twilight-alaska` ×2 | gate 2 → `definedElsewhere` | `definedElsewhere` | agrees |
| "a flash rate sufficient" | `flash-rate-sufficient` ×1 | gate 3 → assertion | assertion | agrees |
| "so close … as to create a collision hazard" | `collision-hazard-proximity` ×2 | gate 3 → assertion | assertion | agrees |
| "reasonable protection" | `reasonable-protection` ×2 | gate 3 → assertion | assertion | agrees |
| "in the interest of safety" | `intensity-reduction-in-interest-of-safety` ×2 | gate 3 → assertion | assertion | agrees |
| "official sunrise", "official sunset" | `civil-twilight-window` ×2, `civil-twilight-operation` ×2 | gate 1 → parameter | `clear` | agrees, with a caveat below |
| "directly participating" | `over-human-beings` ×2, `preflight-actions` ×2 | gate 3 → gap | `operation`, `clear` | **wrong — fixed** |
| "effective communication" | `visual-observer-conditions` ×2 | gate 3 → gap | `operation`, `clear` | **wrong — fixed** |
| "coordinate", "maintain awareness" | `visual-observer-conditions` ×2 | gate 3 → **assertion** | `operation`, `clear` | **wrong — fixed** |
| "able to see … throughout the entire flight" | `visual-line-of-sight` ×2 | gate 3 → **assertion** | `operation`, `clear` | **wrong — fixed** |
| "endanger the life or property of another" | `visual-line-of-sight` ×2 | inside (a)'s measure — **not an open term** | `operation`, `clear` | **sweep wrong, entry right** |
| "assess … considering risks" | `preflight-actions` ×2 | gate 3 → **assertion** | `operation`, `clear` | **wrong — fixed** |
| "informed about" | `preflight-actions` ×2 | gate 3 → **assertion** | `operation`, `clear` | **wrong — fixed** |
| "working properly" | `preflight-actions` ×2 | gate 3 → gap | `operation`, `clear` | **wrong — fixed** |
| "enough available power … for the intended operational time" | `preflight-actions` ×2 | gate 3 → **assertion** | `operation`, `clear` | **wrong — fixed** |
| "secure and does not adversely affect" | `preflight-actions` ×2 | gate 3 → **one of each** | `operation`, `clear` | **wrong — fixed** |

**The three that were wrong on the sweep's own reckoning are the three #33 and #34 named, and
the sweep found no fourth.** That was worth stating as a result and not as an absence: the two
issues were written from the interesting entries, and this was the first pass that looked at
the boring ones. **It did not hold.** 0010 found seven more wrong among the ten rows the sweep
marked #11 and left standing — see below. Three of twenty-one was the count of entries the
sweep *re-derived*; the ten it deferred were never re-derived at all.

**The residue was one open question, not ten new ones, and it is now decided.** The ten rows
last in the table were a single family — facts a *person* asserts, in the three entries
[#11](https://github.com/brandonifco/rules-factory/issues/11) had been open over since the
first trial, plus `over-human-beings`. The sweep left them alone deliberately, because a sweep
that settled #11 as a side effect would be doing exactly what 0008 rejected test 4 for; what
it added was the count, **ten terms across four entries, twenty instances**, not three
entries.

[0010](../../docs/decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md) re-derived all
twenty from the paragraphs they sit in, and **the sweep's own verdict column was wrong on
seven of the ten rows.** The sweep recorded *gate 3 → gap* for every one; running the gate
on the words rather than on the family gives **ten assertion instances, six gaps, two that
split inside one paragraph, and two that are not open terms at all.** § 107.31(a) states
four purposes in an explicit *"in order to"* clause — a stronger statement of the measure
than any of the four assertions 0005 and 0008 already accept — and calling that a gap was
the sweep reading the family rather than the sentence. **The lesson is the sweep's own, turned
on itself:** a verdict recorded for a group of entries at once is a verdict nobody derived
per entry.

**The sweep also undercounted by one row.** *"Directly participating"* is recorded above
against `over-human-beings`; § 107.49(b) uses the same undefined term to delimit **who must
be briefed**, at both dates. The residue was eleven rows and twenty-two instances. The table
is corrected in place.

**One caveat, recorded where the claim is made.** "Official sunrise" and "official sunset" anchor
both civil-twilight windows and are undefined in the corpus. They are treated as parameters —
sunrise at a place and date is an objective fact the caller supplies — but *"official"* is doing
work that the corpus does not do, and § 107.29(c)(3) shows the drafter naming a publication (the
Air Almanac) when he means one. If that word is a deferral, `civil-twilight-window` is a second
`definedElsewhere` and not a clear value. Not changed here; stated so that the next reader is
deciding it rather than inheriting it.

**What this says about the checks.** Every check in the repository was green while the map
carried three verdicts its own corpus contradicts, because `clarity` is compared against nothing.
`check-map.py` cannot close this — it does not read the corpus, by design — and
`check-locators-section.py` verifies that a citation resolves, not that the passage it resolves to
supports the verdict. A checker that could catch this would need the list of terms § 107.3 defines
and the list each entry relies on, and the second list is the part that is judgement. **The
honest position is that this is a review obligation with a recorded count, not a gate.**

## What it means for the kernel

Nothing needs changing. The five `UnresolvedReason` values covered every declined entry,
and the two that fired — `MissingRulesData` and `OutsideCurrentScope` — fired for exactly
the reasons their documentation describes. The map-to-runtime correspondence held on a
corpus it was not designed against.

`SourceLocator`'s opaque citation and `SourceBaselineId`'s `hashDerivation` both earned
their keep: this corpus is hashed as `ecfr-versioner-xml`, which is a different thing from
the rendered HTML or the printed volume, and a digest alone would not have said so.

## What it means for the factory

Findings 1 and 2 are a change to the corpus map's schema and should land before any
tooling reads it. Finding 4 is a change to the manifest. Finding 3 is a change to the
method's prose. None of them would have been found by writing a scaffolder first.

The intake itself took well under an hour by hand, most of it reading. The mechanical
parts — fetch, hash, slice, count — were trivial and are the parts most obviously
automatable. The judgement parts were not hard either, but they were the parts that
produced every finding above, which suggests the first automation should draft the
enumeration and leave classification to review.
