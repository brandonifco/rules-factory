# The bearer test, applied to every Part 107 entry

Working paper for [#30](https://github.com/brandonifco/rules-factory/issues/30). Covers the
two Part 107 maps only; `hoyle-backgammon` is another agent's half of the same exercise.

**Entries examined: 52.** Not 50. `examples/faa-part-107/corpus-map.json` holds **27** entries
and `examples/faa-part-107-temporal/corpus-map-2020-01-01.json` holds **25**; the issue and the
brief both say 26 and 24. The count is confirmed independently by
`check-locators-section.py`, which reports `all 27 checked` and `all 25 checked` and exits 0
against both corpora — so every `evidence` span quoted below is verbatim corpus text sitting
inside the paragraph its `locator` names, verified, not transcribed from the map on trust.

---

## Verdict

**The candidate fails.** Not narrowly, and not on the entry it was expected to fail on alone.

It is not too narrow. Applied to all 52 entries it confirms every one of the five
`kind: assertion` entries; none of them comes back out. It is too **wide**, and it is too wide
in three independent directions, each traceable to a different word in its own statement:

| # | the phrase that over-fires | entries it wrongly sweeps in | instances |
|---|---|---|---|
| 1 | "the subject, by telling them a standard to meet and holding them answerable" | `moving-vehicle-operation` | 2 |
| 2 | "named parties, by fixing a set of permitted values and vesting the choice between them" | `airspace-authorized`, `restricted-area-permitted` | 4 |
| 3 | "a standard to meet" cannot be told from "a fact a person supplies" | `visual-line-of-sight`, `visual-observer-conditions`, `preflight-actions`, `weather-minimums-met` | 8 |

Fourteen disagreements out of fifty-two. **Failure 1 is the one the brief named as fatal and it
is fatal**: § 107.25(b) and § 107.37(a) are the same sentence shape — a prohibition with an
`unless` clause turning on an undefined term, addressed to an operator who is answerable for the
clause — and the bearer test cannot tell them apart, because both have a bearer in exactly the
sense it defines. **Failure 2 is worse in kind**, because it is not a new error: it re-makes the
error `docs/corpus-map.md:325-332` had to withdraw, by the direct route of reading "prior
authorization from Air Traffic Control" as a value a named party chooses from a fixed set —
which, read literally, is limb (ii) verbatim.

A better test is proposed in [§ 5](#5-a-better-test) and applied to all 52 in the same tables.
It is two-stage rather than one sentence, and I think the reason three one-sentence tests have
now failed is that one sentence is the wrong shape for this.

---

## 1. The candidate, stated precisely

The candidate as given:

> The corpus puts the missing fact in somebody's hands — it has a **bearer**. Either the
> subject, by telling them a standard to meet and holding them answerable for having met it;
> or named parties, by fixing a set of permitted values and vesting the choice between them. A
> gap has no bearer: only a word the corpus uses and never defines.

Two limbs, disjunctive, gated on there being a missing fact at all:

- **(i) delegated standard** — a fact the corpus leaves unfixed, placed in the hands of the
  answerable subject.
- **(ii) delegated choice** — a fact the corpus leaves unfixed, placed in the hands of named
  parties who choose among values the corpus fixes.

The gate matters and I have applied it in the subject's favour throughout. Without it the
candidate would call `speed-within-limit` an assertion: § 107.51(a) tells an answerable subject
a standard to meet ("may not exceed 87 knots") and holds them to it. It survives only because
nothing is *missing* — the corpus fixed 87. Every judgement below assumes that reading.

---

## 2. The 2026 map — all 27 entries

`kind` is the current entry's value. "Candidate" is what the bearer test yields when applied to
the entry's `locator` and the corpus text at it. Corpus words are quoted verbatim; where the
whole evidence span is not at issue I quote the operative clause and nothing else.

| # | id | kind | the corpus's own words at the locator | candidate says | agree |
|---|---|---|---|---|---|
| 1 | `speed-limit` | value | "may not exceed 87 knots (100 miles per hour)" | not an assertion — nothing missing | yes |
| 2 | `altitude-limit` | value | "cannot be higher than 400 feet above ground level" | not an assertion — nothing missing | yes |
| 3 | `visibility-minimum` | value | "must be no less than 3 statute miles" | not an assertion — the figure is fixed | yes (see #8) |
| 4 | `cloud-clearance` | value | "500 feet below the cloud; and … 2,000 feet horizontally" | not an assertion — nothing missing | yes |
| 5 | `civil-twilight-window` | value | "begins 30 minutes before official sunrise and ends at official sunrise" | not an assertion — nothing missing | yes |
| 6 | `speed-within-limit` | operation | "may not exceed 87 knots" | not an assertion — nothing missing | yes |
| 7 | `altitude-within-limit` | operation | "within a 400-foot radius of a structure"; "the structure's immediate uppermost limit" | not an assertion — nothing missing | yes |
| 8 | `weather-minimums-met` | operation | "the average slant distance … at which **prominent** unlighted objects **may be seen and identified**" | **assertion** — the RPIC observes and is answerable | **no** — § 4.4 |
| 9 | `single-aircraft` | operation | "may not manipulate flight controls or act as a remote pilot in command or visual observer … more than one … at the same time" | not an assertion — nothing missing | yes |
| 10 | `airspace-authorized` | operation | "unless that person has **prior authorization from Air Traffic Control (ATC)**" | **assertion** — limb (ii), ATC is a named party choosing | **no** — § 4.2 |
| 11 | `restricted-area-permitted` | operation | "unless that person has **permission from the using or controlling agency**, as appropriate" | **assertion** — limb (ii), named agency choosing | **no** — § 4.2 |
| 12 | `moving-vehicle-operation` | operation, `ambiguous` (gap) | "unless the small unmanned aircraft is flown over a **sparsely populated area**" | **assertion** — limb (i), the operator is answerable for the exception | **no** — § 4.1 |
| 13 | `night-operation` | operation, clear | "no person may operate … **at night** unless — (1) … completed an initial knowledge test or training … after April 6, 2021" | not an assertion — its delegated clauses are split out | yes on `kind`; see § 4.5 on `clarity` |
| 14 | `civil-twilight-operation` | operation | "during periods of civil twilight unless … lighted anti-collision lighting visible for at least 3 statute miles" | not an assertion — delegated clauses split out | yes |
| 15 | `civil-twilight-alaska` | value, `definedElsewhere` | "In Alaska, the period of civil twilight **as defined in the Air Almanac**" | not an assertion — handed to a text, not a person | yes |
| 16 | `hazardous-material` | operation, `definedElsewhere` | "the term hazardous material **is defined in 49 CFR 171.8**" | not an assertion — handed to a text, not a person | yes |
| 17 | `right-of-way` | **assertion** | "may not pass over, under, or ahead of it **unless well clear**" | assertion — limb (i) | yes on `kind`; § 4.6 on the entry |
| 18 | `collision-hazard-proximity` | **assertion** | "**so close** to another aircraft **as to create a collision hazard**" | assertion — limb (i) | yes |
| 19 | `reasonable-protection` | **assertion** | "that can provide **reasonable protection** from a falling small unmanned aircraft" | assertion — limb (i) | yes |
| 20 | `over-human-beings` | operation | "(a) … directly participating in the operation"; "(c) … at least one of the operational categories specified in subpart D" | not an assertion — the judgement in (b) is split out | yes |
| 21 | `subpart-d-categories` | operation, `scope: out` | "This subpart prescribes the eligibility and operating requirements … to operate over human beings" | not an assertion | yes |
| 22 | `flash-rate-sufficient` | **assertion** | "a **flash rate sufficient to avoid a collision**" | assertion — limb (i) | yes |
| 23 | `intensity-reduction-in-interest-of-safety` | **assertion** | "**if he or she determines** that … it would be **in the interest of safety** to do so" | assertion — limb (i), decider named outright | yes |
| 24 | `anti-collision-lighting` | operation | "may reduce the intensity of, **but may not extinguish**, the anti-collision lighting" | not an assertion — the bound is computable, the judgement is split out | yes |
| 25 | `visual-line-of-sight` | operation | "**must be able to see** the unmanned aircraft throughout the entire flight **in order to** … (4) **Determine that the unmanned aircraft does not endanger the life or property of another**" | **assertion** — limb (i) | **no** — § 4.3 |
| 26 | `visual-observer-conditions` | operation | "must maintain **effective communication** with each other at all times" | **assertion** — limb (i) | **no** — § 4.3 |
| 27 | `preflight-actions` | operation | "**Assess** the operating environment, **considering risks**"; "**enough** available power … for the intended operational time"; "secure and **does not adversely affect** the flight characteristics or controllability" | **assertion** — limb (i) | **no** — § 4.3 |

**2026: 20 agree, 7 disagree.**

---

## 3. The 2020 map — all 25 entries

The 2020 map is not a subset of the 2026 map with two rows deleted: five entries quote
materially different corpus text, and one of those differences matters to the test.

| # | id | kind | the corpus's own words at the locator | candidate says | agree |
|---|---|---|---|---|---|
| 1 | `speed-limit` | value | "may not exceed 87 knots (100 miles per hour)" | not an assertion | yes |
| 2 | `altitude-limit` | value | "cannot be higher than 400 feet above ground level" | not an assertion | yes |
| 3 | `visibility-minimum` | value | "must be no less than 3 statute miles" | not an assertion | yes (see #8) |
| 4 | `cloud-clearance` | value | "500 feet below the cloud; and … 2,000 feet horizontally" | not an assertion | yes |
| 5 | `civil-twilight-window` | value | "begins 30 minutes before official sunrise and ends at official sunrise" | not an assertion | yes |
| 6 | `speed-within-limit` | operation | "may not exceed 87 knots" | not an assertion | yes |
| 7 | `altitude-within-limit` | operation | "the structure's immediate uppermost limit" | not an assertion | yes |
| 8 | `weather-minimums-met` | operation | "the average slant distance … at which **prominent** unlighted objects **may be seen and identified**" | **assertion** | **no** — § 4.4 |
| 9 | `single-aircraft` | operation | "may not **operate** or act as a remote pilot in command or visual observer …" (this text; the 2026 text reads "manipulate flight controls") | not an assertion | yes |
| 10 | `airspace-authorized` | operation | "unless that person has **prior authorization from Air Traffic Control (ATC)**" | **assertion** — limb (ii) | **no** — § 4.2 |
| 11 | `restricted-area-permitted` | operation | "unless that person has **permission from the using or controlling agency**" | **assertion** — limb (ii) | **no** — § 4.2 |
| 12 | `moving-vehicle-operation` | operation, `ambiguous` (gap) | "unless … flown over a **sparsely populated area**" | **assertion** — limb (i) | **no** — § 4.1 |
| 13 | `night-operation` | operation, clear | "No person may operate a small unmanned aircraft system **during night**." — the whole entry | not an assertion — no bearer, but no definition either | yes on `kind`; **§ 4.5** is sharpest here |
| 14 | `civil-twilight-operation` | operation | "unless the small unmanned aircraft has lighted anti-collision lighting visible for at least 3 statute miles" — **no flash-rate clause at this date** | not an assertion | yes |
| 15 | `civil-twilight-alaska` | value, `definedElsewhere` | "as defined in the Air Almanac" | not an assertion | yes |
| 16 | `hazardous-material` | operation, `definedElsewhere` | "is defined in 49 CFR 171.8" | not an assertion | yes |
| 17 | `right-of-way` | **assertion** | "may not pass over, under, or ahead of it **unless well clear**" (identical to 2026) | assertion — limb (i) | yes on `kind`; § 4.6 |
| 18 | `collision-hazard-proximity` | **assertion** | "**so close** … **as to create a collision hazard**" | assertion — limb (i) | yes |
| 19 | `reasonable-protection` | **assertion** | "(b) Located under a covered structure or inside a stationary vehicle that can provide **reasonable protection** from a falling small unmanned aircraft." | assertion — limb (i) | yes |
| 20 | `over-human-beings` | operation | "(a) Directly participating in the operation …; or (b) Located under a covered structure …" — **two limbs only, no subpart D at this date** | not an assertion | yes |
| 21 | `intensity-reduction-in-interest-of-safety` | **assertion** | "may reduce the intensity … **if he or she determines** that … **in the interest of safety**" — and **no "but may not extinguish"** at this date | assertion — limb (i) | yes |
| 22 | `anti-collision-lighting` | operation | "lighted anti-collision lighting visible for at least 3 statute miles" | not an assertion | yes, **but** — § 4.7 |
| 23 | `visual-line-of-sight` | operation | "must be able to see … **in order to** … Determine that the unmanned aircraft does not endanger the life or property of another" | **assertion** | **no** — § 4.3 |
| 24 | `visual-observer-conditions` | operation | "must maintain **effective communication** … at all times" | **assertion** | **no** — § 4.3 |
| 25 | `preflight-actions` | operation | "**Assess** … **considering risks**"; "**enough** available power"; "does not **adversely affect** the flight characteristics" — five limbs, (a)–(e), no (f) | **assertion** | **no** — § 4.3 |

**2020: 18 agree, 7 disagree.**

---

## 4. The disagreements

### 4.1 `moving-vehicle-operation` — the fatal one

§ 107.25 reads, in full:

> No person may operate a small unmanned aircraft system— (a) From a moving aircraft; or
> (b) From a moving land or water-borne vehicle unless the small unmanned aircraft is flown
> over a sparsely populated area and is not transporting another person's property for
> compensation or hire.

§ 107.37(a) reads:

> Each small unmanned aircraft must yield the right of way to all aircraft, airborne vehicles,
> and launch and reentry vehicles. Yielding the right of way means that the small unmanned
> aircraft must give way to the aircraft or vehicle and may not pass over, under, or ahead of it
> unless well clear.

Set them side by side and the candidate has nothing to work with:

|  | § 107.25(b) | § 107.37(a) |
|---|---|---|
| form | prohibition + `unless` | prohibition + `unless` |
| the open term | "sparsely populated area" | "well clear" |
| defined in the corpus? | no — § 107.3 does not define it, nothing else does | no — § 107.3 does not define it, nothing else does |
| who is addressed | "No person may operate …" | "may not pass over, under, or ahead of it …" |
| who is answerable if the term is not satisfied | the operator | the operator |

The candidate says a gap is "a word the corpus uses and never defines" with "no bearer at all".
Both are words the corpus uses and never defines. The bearer the candidate points at for "well
clear" — "the addressee of the obligation, who is answerable for having met it" — is present,
identically, for "sparsely populated area": § 107.25 is addressed to a person, that person may
only operate from a moving vehicle if the area is sparsely populated, and that person answers for
it in an enforcement action. There is no reading of "bearer" on which one has one and the other
does not.

**What would have to be true for the candidate to be right here?** That "sparsely populated
area" is a condition the corpus states about the world without addressing anyone, while "well
clear" is a standard addressed to the operator. That is not true. Both sit in the `unless` clause
of a prohibition addressed to the operator, and the operator's compliance turns on both. The
brief's own framing — "'sparsely populated area' is a condition on an operator's conduct, and an
operator could perfectly well assert it" — is exactly right, and the candidate has no answer to
it.

Two rescues were tried and neither works:

- *"A standard is something you meet by trying; sparse population is not."* An operator complies
  with § 107.25(b) by **choosing where to fly** — precisely as they comply with § 107.37(a) by
  choosing how far to stay away. Both are met by choosing. Symmetric.
- *"Well clear is about the operator's own aircraft; sparse population is a fact about the
  world."* `docs/corpus-map.md:91-93` says facts about the physical world "are consumed, not
  derived" — that is, they are **assertions**. So this rescue, if taken, makes
  `moving-vehicle-operation` an assertion by a second route rather than saving it as a gap.

My conclusion is stronger than "the candidate mis-sorts this entry". **The line between
`right-of-way` and `moving-vehicle-operation` is not drawn by anything in the text at the two
locators, on any of the three tests tried.** The one textual difference I can find is set out in
§ 5; it is thin, and if a future reviewer decides it is too thin, the honest landing is a
decision recording that the line is drawn by aviation practice (where "well clear" is a
recognised operational standard the regulator delegates to pilot judgement) rather than by the
corpus — which would be a real constraint on what a map can claim to derive.

### 4.2 `airspace-authorized` and `restricted-area-permitted` — the withdrawn error, re-made

The brief asked whether the candidate accidentally sweeps these in. It does, and not through
limb (i) — through **limb (ii), read verbatim**.

§ 107.41: "…unless that person has **prior authorization from Air Traffic Control (ATC)**."
§ 107.45: "…unless that person has **permission from the using or controlling agency**, as
appropriate."

Limb (ii) is "named parties, by fixing a set of permitted values and vesting the choice between
them." Check it clause by clause against § 107.41:

- *named parties* — "Air Traffic Control (ATC)", named in the text.
- *a set of permitted values* — {authorized, not authorized}.
- *vesting the choice between them* — ATC grants or withholds. Nobody else may.

Every clause is satisfied. And the backgammon instance limb (ii) exists to cover — "either
thrice or four times (as may have been agreed)" — is also a **binary** choice between two fixed
values vested in named parties, so "a set of two is not really a set" is not available as a
distinction without also discarding the motivating case.

`docs/corpus-map.md:325-332` rules the opposite way in terms, and gives the reason: "the rule is
fully implementable and one input comes from outside… **A parameter is not a rule, so it gets no
entry at all**." That ruling is right, and the candidate contradicts it. **This is the more
serious of the two over-fires**, because failure 4.1 is a new error on an unsettled boundary
while this one re-opens a boundary 0005 had already closed — and closed after a review.

What separates the ATC case from the backgammon case is real but is nowhere in the candidate:
§ 107.41 is a **complete rule with an input**. Once you know the class and whether authorization
was given, the corpus determines the answer, for every combination. The stake multiplier is not
that: the corpus leaves **a term of the rule itself** — how much the stake is multiplied by —
unfixed, and the rule cannot be applied at all until somebody says three or four. "Is there an
authorization" is a fact the rule *tests*; "what is the multiplier" is a blank in the rule.
The candidate's "missing fact … in somebody's hands" collapses that distinction, because a fact
the rule tests is also, trivially, missing until supplied.

### 4.3 `visual-line-of-sight`, `visual-observer-conditions`, `preflight-actions` — the candidate decides #11 by accident

0005 rules explicitly that these three are "facts-a-person-asserts, **not delegated standards**",
leaves them `kind: operation` with a note, and keeps [#11](https://github.com/brandonifco/rules-factory/issues/11)
open over exactly them. The candidate cannot reproduce that ruling, because limb (i) is satisfied
by every one of them:

- § 107.31(a) does not merely require a fact. It states a **purpose clause** — "must be able to
  see the unmanned aircraft throughout the entire flight **in order to**: … (4) Determine that
  the unmanned aircraft does not endanger the life or property of another." Sub-paragraph (4) is
  a judgement the corpus vests in the named persons in the same sentence. That is a delegated
  standard on any reading of limb (i), and it is a delegated standard on the *stated-purpose*
  reading too.
- § 107.33(a) requires "**effective** communication … at all times". "Effective" is an open
  degree borne by the three named persons.
- § 107.49 is built out of them: "**Assess** the operating environment, **considering risks** to
  persons and property"; "ensure that there is **enough** available power … for the intended
  operational time"; "ensure that any object … is secure and **does not adversely affect** the
  flight characteristics or controllability". The map's own `note` on the entry calls these
  "six obligations, **all assertions** about what a person did" while the `kind` stays
  `operation`.

So the candidate resolves #11 in the affirmative — these become `kind: assertion` — without a
decision being taken, and in direct contradiction of a ruling 0005 records. **Whichever way #11
should go, a test that settles it as a side-effect is not fit to be adopted**, and adopting the
candidate would ship that side-effect into eight entry instances across the two maps.

Note the direction of the failure. Limb (i) has no machinery at all for the distinction between
*the corpus left a term of its rule open* and *the corpus stated a complete rule about something
only a person can report*. Both are "a missing fact in somebody's hands".

### 4.4 `weather-minimums-met` — an entry nobody has looked at

This one was not on anybody's list, and it is the clearest demonstration that the candidate's
reach is not bounded by the entries under discussion.

§ 107.51(c) fixes a number and then defines the metric:

> The minimum flight visibility, as observed from the location of the control station must be no
> less than 3 statute miles. For purposes of this section, flight visibility means the average
> slant distance from the control station at which **prominent** unlighted objects **may be seen
> and identified** by day and **prominent** lighted objects may be seen and identified by night.

"Prominent" is undefined in Part 107 — § 107.3 does not define it and no other section does —
and it carries the whole metric: change what counts as prominent and the measured visibility
changes. "May be seen and identified" is an observational judgement, and the corpus says whose
vantage point governs ("as observed from the location of the control station"), which in practice
is the remote pilot in command's.

Under the candidate: a fact the corpus leaves unfixed, in the hands of an answerable subject who
observes and reports it. **Assertion.** The entry is `operation`, `clarity: clear`, in both maps.

I record this as a disagreement rather than as a recommendation to reclassify. My own reading is
that `weather-minimums-met` is correctly an `operation` — "prominent" is an undefined qualifier
sitting inside a **definition**, vested in nobody, with no purpose stated for prominence itself
beyond the circular one, which makes it the `sparsely populated area` shape rather than the `well
clear` shape. The point is that the candidate has no way to reach that reading, and that a test
which mis-sorts an entry nobody was arguing about is mis-sorting it for structural reasons, not
by oversight.

### 4.5 `night-operation` — a finding that is not about the test at all

Going through all 52 turned up a defect independent of the assertion question, and it is in the
entry that has carried the temporal trial's headline finding.

**"Night" is not defined anywhere in either admitted corpus.** § 107.3 in the 2026 text defines
*control station*, *corrective lenses*, *declaration of compliance*, *small unmanned aircraft*,
*small unmanned aircraft system*, *unmanned aircraft*, *visual observer* — and not *night*. The
2020 § 107.3 defines the same list less *declaration of compliance*, and not *night*. The word
"night" occurs seven times in the 2026 corpus and twice in the 2020 corpus, in every case as a
use and never as a definition.

The 2020 `night-operation` entry is the whole of § 107.29(a) — "No person may operate a small
unmanned aircraft system during night." — and it is recorded `clarity: clear`, with the note
"Night, and not-night. There is no condition under which night operation is permitted." The
entry's entire content is an undefined term. Compare `moving-vehicle-operation`, recorded
`ambiguous` on the stated ground that "Part 107 does not define 'sparsely populated area', and
the term carries the whole exception in (b)". **Same ground, opposite verdict, in the same map.**

The 2026 entry inherits it: § 107.29(a) turns on "at night" and is likewise `clarity: clear`.

This is not, I think, a gap. § 107.3 opens by naming where the rest of this chapter's vocabulary
lives — "If there is a conflict between the definitions of this part and definitions specified in
**§ 1.1 of this chapter**, the definitions in this part control for purposes of this part" —
which is the corpus saying that § 1.1 supplies what it does not. That is the
`civil-twilight-alaska` / `hazardous-material` shape: **`definedElsewhere`**, pointing at
14 CFR § 1.1. It cannot be recorded today, because neither manifest lists a `cfr-14-1` reference
(both list only `cfr-49-171` and `air-almanac`), and `definedElsewhere.reference` must resolve.
So the fix is a manifest entry plus an entry change, in both maps — and it should be filed, not
folded into #30, since it is an unrelated axis.

I flag one consequence, because it touches a claim the project has made in three places: the
temporal trial's headline finding rests on `night-operation`'s clarity changing between the two
dates. If the 2020 entry is `definedElsewhere` rather than `clear`, that finding is resting on a
value that was wrong at both dates.

### 4.6 `right-of-way` — the candidate agrees, and both are wrong about the *entry*

The brief's highest-value ask was an assertion the candidate takes back out. There is none: all
five survive. But re-deriving `right-of-way` from first principles surfaces something else.

The entry is `kind: assertion` covering the whole of § 107.37(a), and its `note` gives the
reason for not splitting:

> The duty runs to every aircraft, airborne vehicle, and launch and reentry vehicle without
> exception, **so nothing here is computed**: the entry is the standard 'well clear' and nothing
> else, and is reclassified in place rather than split.

The corpus contradicts the premise. § 107.37(a) enumerates **three protected classes** — "all
aircraft, airborne vehicles, and launch and reentry vehicles" — and **three prohibited relative
positions** — "may not pass over, under, or ahead of it". Both enumerations are computable
content. An engine told that the object was a launch vehicle and that the aircraft passed
beneath it, and given the `well-clear` assertion, decides the case; told that the object was not
one of the three classes, it decides the case **without the assertion at all**. That is a
computable half, and it is precisely what 0005's correction A says must not be destroyed by
classifying a whole entry from one of its clauses.

"Without exception" is true and does not entail "nothing is computed". The absence of exceptions
means the *duty* is unconditional; the enumerations are still tests.

**Recommended change**: split, exactly as `night-operation` and `over-human-beings` were split —
a new `kind: assertion` entry `well-clear` on the `unless` clause, and `right-of-way` becomes
`kind: operation`, `dependsOn: ["well-clear"]`, retaining the protected-class and
relative-position enumerations. Two instances, one per map. This is the fourth entry — after
`night-operation`, `over-human-beings` and `anti-collision-lighting` — where the standard is one
clause of a rule with computable content, and it is the only one of the four still
reclassified in place. `collision-hazard-proximity` is genuinely different and should stay as it
is: § 107.37(b) is one sentence and the standard is the whole of it.

A smaller observation on `reasonable-protection`, recorded and not recommended: its `evidence`
span necessarily carries a non-standard clause — "That human being is **located under** a covered
structure or inside a stationary vehicle" is an ordinary caller-supplied fact, bundled into an
entry whose `name` correctly scopes itself to the standard. There is no shorter contiguous corpus
span that states the standard alone, so this is a genuine tension between 0005's one-runtime-
reason-per-entry rule and the contiguous-evidence rule, not an error in the entry.

### 4.7 A note on the 2020 `anti-collision-lighting`

The candidate and the entry agree, but the 2020 text differs from the 2026 text in a way that
matters to the *bound*, and the map records it correctly: at this date the permission reads
"may reduce the intensity of the anti-collision lighting if he or she determines…" with **no**
"but may not extinguish". So the 2020 `anti-collision-lighting` entry consumes a delegated
judgement whose exercise the corpus does not bound at all, while the 2026 entry consumes one it
does. Both entries are `operation` and both are right. I mention it because it is the cleanest
instance in either map of an amendment adding computable content *around* an unchanged
assertion — the shape 0005's restated trial-3 finding describes — and it is recorded accurately.

---

## 5. A better test

Three one-sentence tests have failed. I do not think the fourth one-sentence test is the answer,
because the failures are not all of the same kind: 4.1 and 4.4 are failures to separate *a
delegated standard from an undefined term*, while 4.2 and 4.3 are failures to separate *a blank
in the rule from an input the rule tests*. Those are two questions, and a single sentence keeps
answering one of them.

**Proposal — two stages, in order.**

> **Stage 1. Is the open thing a blank in the rule, or a fact the rule tests?**
> Ask whether applying the corpus's words requires **fixing a threshold, degree or value the
> corpus did not fix**. If it does not — the term is determinate and what is missing is only
> whether it obtained — the entry is an ordinary `operation` or `value` with a caller-supplied
> input, and **the input gets no entry of its own**.
>
> **Stage 2. For a blank only: did the corpus hand it to somebody?**
> - **To the answerable subject, with the purpose stated at the locator** — the corpus leaves the
>   degree open but says what it is measured against, so the subject knows what to achieve →
>   **`kind: assertion`, delegated standard**, and it is an entry of its own.
> - **To named parties, among values the corpus fixes** → **`kind: assertion`, delegated
>   choice**, and it is an entry of its own.
> - **To nobody: no purpose stated, no set of values fixed** → **gap**, `clarity: ambiguous`,
>   `fate: unresolved`.

Stage 1 is what neither the candidate nor either predecessor has. It is what excludes ATC
authorization (determinate: did ATC authorize, yes or no), the airspace class (determinate and
published), whether anyone could see the aircraft (determinate: they could or they could not),
and whether a preflight assessment was performed. None of them asks anyone to fix a threshold the
corpus left open; all of them are facts a total rule tests. It is also what keeps the candidate
from deciding #11 sideways — #11 becomes a question about whether a caller-supplied *fact*
deserves `kind: assertion`, which is a separate and legitimate question, rather than being
answered by a test aimed at delegated standards.

The purpose clause in stage 2 is what separates `well clear` from `sparsely populated area`, and
it is the only textual difference I can find between them:

| locator | the degree left open | the purpose stated at the locator |
|---|---|---|
| § 107.29(a)(2), (b) | the flash rate | "**sufficient to avoid a collision**" |
| § 107.39(b) | "reasonable" | "**protection from a falling small unmanned aircraft**" |
| § 107.37(b) | "so close" | "**as to create a collision hazard**" |
| § 107.29(a)(2), (b) | whether to reduce intensity | "**in the interest of safety**", decider named |
| § 107.37(a) | the margin | the sentence states the interest the margin protects: "must **give way to** the aircraft or vehicle" |
| § 107.25(b) | how sparse | **none. § 107.25 states no purpose for sparseness anywhere.** |

Applied to all 52 the proposal changes four verdicts relative to the candidate and agrees with
every current entry except `right-of-way`, where it produces the split argued in § 4.6:

| entry | candidate | proposal | current entry |
|---|---|---|---|
| `moving-vehicle-operation` (×2) | assertion | **gap** | gap ✓ |
| `airspace-authorized`, `restricted-area-permitted` (×4) | assertion | **operation, input, no entry** | operation ✓ |
| `visual-line-of-sight`, `visual-observer-conditions`, `preflight-actions` (×6) | assertion | **operation** (stage 1: determinate facts) — with § 107.31(a)(4) named as the residual case | operation ✓, #11 left open as 0005 left it |
| `weather-minimums-met` (×2) | assertion | **operation** (stage 2: "prominent" has no stated purpose, so it is not delegated; it is a small gap inside a definition) | operation ✓ |
| the five `kind: assertion` entries (×9 instances) | assertion | **assertion** | assertion ✓ |
| `right-of-way` (×2) | assertion (whole entry) | **split**: `well-clear` assertion + `right-of-way` operation | assertion, whole entry ✗ |

**Where I am least confident, stated plainly.** The § 107.37(a) row of the purpose table is the
weakest. The other four assertions carry an explicit purpose phrase — *avoid a collision*,
*protection from a falling aircraft*, *create a collision hazard*, *interest of safety*. "Well
clear" carries none; I am reading the purpose off the duty the same sentence states. If that is
too thin, the proposal cannot separate `right-of-way` from `moving-vehicle-operation` either, and
the correct response is § 4.1's conclusion — record that the line is not derivable from the text
— rather than a fifth test. The proposal's advantage over the candidate does not depend on that
row: stage 1 alone repairs 4.2 and 4.3, which are ten of the fourteen disagreements.

The proposal is also **checkable in the way 0005's rail E is checkable**: an entry claiming
`kind: assertion` under stage 2's first branch must name the words in its own `evidence` that
state the purpose. That is a quotable obligation a reviewer can fail, not an exhortation. An
assertion entry that cannot point at its purpose clause is either a delegated choice (second
branch, which must instead point at the fixed set) or a gap.

---

## 6. Outside the corpus

Four cases from outside Part 107. **These are from my own knowledge of the instruments, not from
files in this repository; the wording is paraphrased and would need checking against the source
before any of it is cited.** They are chosen to stress the two limbs separately.

### 6.1 The OSHA general duty clause — both hold

29 U.S.C. § 654(a)(1) requires each employer to furnish a workplace free from recognized hazards
that are causing or are likely to cause death or serious physical harm.

Candidate: the employer is the bearer, told a standard and answerable for it → assertion.
Proposal: stage 1 — "free from recognized hazards" requires fixing a degree the statute does not
fix, so it is a blank. Stage 2 — the purpose is stated in the clause itself ("death or serious
physical harm") and the employer is answerable → delegated standard, assertion.

Both agree, and this is the archetype. It is not a discriminating case; I include it because a
test that got *this* wrong would be dead on arrival, and neither is.

### 6.2 A force majeure definition — the candidate fails again, the same way

A standard commercial clause: *Force Majeure means any event beyond the reasonable control of the
affected Party, including but not limited to …*

Candidate: "beyond the **reasonable** control" is a degree the contract does not fix; the
affected Party is the one who invokes it and is answerable for the invocation in arbitration →
bearer present → **assertion**.

Proposal: stage 1 — a blank, yes. Stage 2 — the contract states no purpose the reasonableness is
measured against, and fixes no set of values; and critically the affected Party is not *handed*
the question, they merely have an interest in the answer. An arbitrator decides, and the
arbitrator is not named by the clause. → **gap**.

This is 4.1 generalised, and it is the sharpest statement of what is wrong with the word
"bearer": **being the party who will claim a standard was met is not the same as being the party
the instrument made answerable for meeting it**, and the candidate has no way to tell them apart.
The same objection applies to "sparsely populated area" and to "prominent". Anywhere an open term
appears in a clause that some party benefits from, the candidate finds a bearer.

### 6.3 Two delegated choices — limb (ii) is real and worth keeping

A delivery clause: *the Delivery Date shall be such date as the Parties may agree, being not
later than 31 December.* And FIDE's laws, where the rate of play for an event is as announced by
the organiser, and where the arbiter may impose one of an enumerated list of penalties.

All three are the backgammon shape: a term of the rule left unfixed, values bounded by the
instrument, choice vested in named parties. Candidate limb (ii) → assertion. Proposal stage 2,
second branch → assertion. **Both hold**, and this is the case that shows limb (ii) is not
redundant and must survive into any successor test: none of the three is a standard of conduct,
and the bound the instrument states ("not later than 31 December", the enumerated penalty list)
is content an engine must keep rather than discard, which is exactly the loss 0005 was correcting.

### 6.4 A rate set by an agency — limb (ii)'s instability

A state wage statute of the common form: *the minimum wage shall be the rate established annually
by the Commissioner.*

The right answer is `definedElsewhere`: the rule is complete, the value is fixed in a document
outside the corpus, and an engine should say `MissingRulesData` rather than demand an assertion.

Candidate limb (ii) requires *a set of permitted values the corpus fixes*, and here the corpus
fixes none — so limb (ii) fails and the candidate gets this right. **But it gets it right only on
a strict reading of "fixes a set", and § 4.2 shows the strict reading is not the one limb (ii)
bears in practice**: {authorized, not authorized} counted as a fixed set for § 107.41, and by that
standard {every dollar amount the Commissioner might pick} is a set too. A test whose correct
answers depend on which of two readings you take to a case you have not seen is the failure mode
0005 records twice already.

The proposal does not have that instability, because stage 1 disposes of § 107.41 before limb
(ii) is ever reached, leaving "fixes a set" to mean what it means in the backgammon and FIDE
cases.

### What the outside cases add up to

The candidate holds on 6.1 and 6.3, fails on 6.2, and is unstable on 6.4. Its two failures
outside the corpus are the same two failures as inside it: "bearer" collapses *answerable* into
*interested* (6.2, 4.1, 4.4), and limb (ii) collapses *a value the rule leaves blank* into *an
outcome the rule tests* (6.4, 4.2). That the same two failures reappear in a contract, a game and
a state statute is the strongest evidence I have that they are structural rather than artefacts of
this regulation.

---

## 7. Summary

- **Verdict: fails.** 14 disagreements in 52 entries, on three independent over-fires. It fails on
  `moving-vehicle-operation`, which the brief named as its killer, and it re-makes the
  `airspace-authorized` error `docs/corpus-map.md` had already withdrawn.
- **No current `kind: assertion` comes out.** All five are confirmed by the candidate and by the
  proposal. There is no "most valuable find" of that shape in these two maps.
- **One `kind` should change**: `right-of-way` should be split into an `assertion` (`well-clear`)
  and an `operation` (`right-of-way`, `dependsOn: ["well-clear"]`), in both maps — 2 instances.
  Its stated reason for not splitting, "nothing here is computed", is contradicted by the two
  enumerations in § 107.37(a).
- **One finding outside the test**: "night" is undefined in both admitted corpora, and both
  `night-operation` entries are `clarity: clear`. It should be `definedElsewhere` against
  14 CFR § 1.1, which requires a manifest `references` entry that does not exist. Worth its own
  issue; it also undercuts the temporal trial's headline finding, which rests on that entry's
  clarity.
- **A successor test is proposed in § 5**, two-stage, and applied to all 52. It agrees with every
  current entry except `right-of-way`, keeps `moving-vehicle-operation` a gap, keeps the
  caller-supplied parameters out, and leaves #11 open rather than deciding it by accident. Its
  weakest joint is named in § 5 and is the same joint the candidate broke on.
- **Entries examined: 52** — 27 in `examples/faa-part-107/corpus-map.json`, 25 in
  `examples/faa-part-107-temporal/corpus-map-2020-01-01.json`. Both counts confirmed by
  `check-locators-section.py`, which also verifies every quoted span above as verbatim corpus
  text at the cited paragraph.
