# 0010 — Whose fact it is does not decide the kind; the measure the corpus states does

## Status

Accepted — 2026-09-14. Closes the half of
[#11](https://github.com/brandonifco/rules-factory/issues/11) that
[0005](0005-a-field-earns-its-place-by-being-checkable.md) A explicitly left open, and closes
[#28](https://github.com/brandonifco/rules-factory/issues/28)'s Part 107 data fix in passing,
because the same entry raised both.

## Context

`kind: assertion` was added after the first trial for *"facts a person asserts"*. 0005 settled
the **delegated standard** half — a standard is an assertion and it is an entry of its own —
and ruled that `visual-line-of-sight`, `visual-observer-conditions` and `preflight-actions` are
*"facts-a-person-asserts, not delegated standards"*, which is a different argument, and left it.
0008 adopted a three-gate procedure for delegated standards and recorded that #11 stays open
because **gate 1 routes a caller-supplied fact to "no entry of its own"** while `corpus-map.md`
separately says *"facts about the physical world are consumed, not derived"*, and listed that
tension as the thing #11 is.

Trial 1's undefined-term sweep then measured the residue: **ten terms across four entries,
twenty instances** — `visual-line-of-sight`, `visual-observer-conditions`,
`preflight-actions` and `over-human-beings`, at both dates. Every one returns a **gap** on
0008's gates, and the question this record answers is whether that is right.

**Three readings were on the table.**

1. **They are assertions.** The fact is unobtainable by computation, the person is the only
   source, and the four obligations — demand it, attribute it, record it alongside the
   outcome, never infer it — are exactly what an engine owes. The gap verdict is 0008's gates
   tuned for delegation and blind to this.
2. **They are gaps.** *"Effective communication"* states no measure, the same as *"prominent"*,
   which 0008 has already ruled a gap. An operator asserting that communication was effective is
   asserting a conclusion, not a fact, and an engine accepting it has accepted a judgement it
   cannot check and has no corpus warrant to delegate.
3. **Both, and the entries are mis-split** — the way `right-of-way` / `well-clear` and
   `weather-minimums-met` / `prominent-objects` were split.

## The evidence

Every term was re-derived from `part107.xml` and `part107-2020-01-01.xml` at the paragraph
it sits in, through 0008's procedure, and not from the sweep's table. Ten rows, two dates,
twenty instances. **Reading 3 accounts for all twenty. Reading 1 accounts for ten of them and
reading 2 for six.**

| # | term | § | gate 3 | instances |
|---|---|---|---|---|
| 1 | "able to see … throughout the entire flight" | 107.31(a) | **assertion** | 2 |
| 2 | "endanger the life or property of another" | 107.31(a)(4) | **inside another entry's measure — no entry** | 2 |
| 3 | "effective communication" | 107.33(a) | **gap** | 2 |
| 4 | "coordinate" / "maintain awareness" | 107.33(c) | **assertion** | 2 |
| 5 | "directly participating" | 107.39(a) | **gap** | 2 |
| 6 | "assess … considering risks" | 107.49(a) | **assertion** | 2 |
| 7 | "informed about" | 107.49(b) | **assertion** | 2 |
| 8 | "working properly" | 107.49(c) | **gap** | 2 |
| 9 | "enough available power … for the intended operational time" | 107.49(d) | **assertion** | 2 |
| 10 | "secure **and** does not adversely affect …" | 107.49(e) | **one of each** | 2 |

**Ten assertion instances, six gap instances, two that split inside one paragraph, and two
that are not open terms at all.** Every one of the four entries is misclassified today, and
**two of the four contain both answers**.

### What actually fires, term by term

**Gate 3's first arm fires wherever the corpus states the measure in the same constituent**,
which is the test 0008 already adopted and 0005 already checked against four uncontested
assertions:

- § 107.31(a) is the plainest instance in the corpus. The open ability — *"must be able to
  see the unmanned aircraft throughout the entire flight"* — is followed by *"in order to:"*
  and **four enumerated purposes**. That is *"sufficient **to avoid a collision**"* with four
  adjuncts instead of one.
- § 107.33(c): *"must coordinate **to do the following:**"* and a closed two-item
  enumeration, the second of which fixes its own means (*"through direct visual observation"*).
- § 107.49(a): *"considering risks to persons and property in the immediate vicinity both on
  the surface and in the air"*, then a closed four-item list of what the assessment must include.
- § 107.49(b): *"informed about"* a **fixed set of five** matters — gate 3's second arm,
  the delegated choice among values the corpus fixes, the *"either thrice or four times"* shape.
- § 107.49(d): *"**enough** available power **for the small unmanned aircraft system to
  operate for the intended operational time**"* — an infinitival adjunct on *enough*, the
  same construction as the flash rate.

**It does not fire where the corpus states no measure**, and those paragraphs are indis-
tinguishable in shape from `prominent-objects` and `well-clear`:

- § 107.33(a): *"must maintain **effective** communication with each other at all times."*
  *"With each other at all times"* fixes between whom and when. Nothing says what
  effectiveness is measured against, and nobody's determination is made operative.
- § 107.49(c): *"all control links … are **working properly**."* *"Between ground control
  station and the small unmanned aircraft"* identifies which links, not what *properly* means.
- § 107.39(a): *"**directly participating** in the operation of the small unmanned
  aircraft."* The complement says what the participation is in, not how direct it must be.

**Two terms are not open terms.** § 107.31(a)(4)'s *"endanger the life or property of
another"* is one of the four purposes that fix *"able to see"*: § 107.31 does not prohibit
endangering, it requires the ability to see well enough to **determine**. Counting it as a
second open term would count the measure twice. *"Maintain awareness"* in § 107.33(c)(2) is
the same, inside the enumeration that fixes *"coordinate"*.

**One paragraph splits.** § 107.49(e) reads *"is **secure** and **does not adversely affect
the flight characteristics or controllability** of the aircraft."* 0008 § 2 ruled that a
coordinate conjunct is a second obligation and not a measure — that is precisely how *"must
give way"* was refused as the measure of *"well clear"*. Applied here, *"secure"* has no
measure and the second conjunct has its own, stated and enumerated. One sentence, two verdicts.

### The two counterexamples that kill readings 1 and 2

They sit in one section, one sentence apart.

| § 107.39 | whose fact | measure stated | verdict |
|---|---|---|---|
| (a) *"directly participating in the operation"* | a third party's | none | **gap** |
| (b) *"reasonable protection **from a falling small unmanned aircraft**"* | a third party's | yes | **assertion** (already) |

And in § 107.49, both about the caller's own conduct and equipment, with opposite answers:
(a) *"assess … considering risks to …"* is an assertion; (c) *"working properly"* is a gap.

So *whose* fact it is does not predict the answer in either direction. A third party's fact
can be an assertion; the caller's own can be a gap.

## Decision

### 1. There is no "facts a person asserts" category. Gate 3 already decides them

The family #11 named is not a third thing beside the delegated standard and the gap. It is a
mixture of the two, and **0008's procedure separates it without amendment**. No new gate, no
new `kind`, no new field. Ten instances are assertions, six are gaps, two split, two are not
open terms.

**The four obligations follow the measure, not the person.** *Demand it, attribute it, record
it alongside the outcome, never infer it* is what an engine owes wherever the corpus left a
degree open **and said what it is measured against**. Where the corpus left a degree open and
said nothing, an engine has no statement of what it would be demanding — and a person who
answers *"yes, communication was effective"* has supplied a conclusion, not a fact. Accepting
it is the substitution of judgement that *never infer it* exists to prevent, arriving from the
other side.

That is 0008 § 2's ruling applied to a second family: where the project believes such a term
is nevertheless determinate because practice outside the corpus fixes it, that belief is
`fate: decision` with a record, or `definedElsewhere` if the practice is a corpus that can be
admitted. **Never a `kind`**, because a map may not claim to have derived from a text what the
text does not say.

### 2. A fact the rule merely tests is a parameter and gets no entry, and the physical-world sentence goes

`corpus-map.md`'s *"facts about the physical world are consumed, not derived"* and
`method.md` Phase 3's *"Facts about the physical world. Whether it was raining, whether a
structure was within 400 feet, whether a person was under cover"* are **withdrawn**. They
name an engine's input, which is true, and then classify it as `kind: assertion`, which
contradicts gate 1 and contradicts `corpus-map.md`'s own ruling on `airspace-authorized`
(*"a parameter is not a rule, so it gets no entry at all"*).

The rule that replaces them: **`kind: assertion` is a property of an open term the corpus
delegated with a stated measure or a fixed set. A fact the rule merely tests — the airspace
class, the groundspeed, whether a visual observer was used, whether the aircraft is powered
— is a caller-supplied parameter, gets no entry, and is named in the consuming entry's
`note`.** The engine demands both; only one of them is a rule.

This is the tension 0008 named as being what #11 *is*, and it is resolved in gate 1's
favour, because gate 1 is the clause both independent passes found and it is what silences
every runtime input in both maps.

### 3. The four entries are split, and § 107.29(d) gains the entry #28 asked for

Ten new entries per map, following 0005's `speed-limit` / `speed-within-limit` shape:

| new entry | § | kind |
|---|---|---|
| `unaided-visual-contact` | 107.31(a) | assertion |
| `effective-communication` | 107.33(a) | gap |
| `observer-coordination` | 107.33(c) | assertion |
| `direct-participation` | 107.39(a) | gap |
| `preflight-risk-assessment` | 107.49(a) | assertion |
| `participant-briefing` | 107.49(b) | assertion |
| `control-links-working` | 107.49(c) | gap |
| `sufficient-available-power` | 107.49(d) | assertion |
| `attached-object-secure` | 107.49(e) | gap |
| `attached-object-no-adverse-effect` | 107.49(e) | assertion |

`visual-line-of-sight` keeps § 107.31(b)'s two permitted combinations, which are a
membership test and computable; `visual-observer-conditions` keeps (b) and the condition of
application; `over-human-beings` gains a third dependency; `preflight-actions` keeps the
conjunction. 2026: 29 → 40 entries. 2020: 27 → 37, with no § 107.29(d) and no
§ 107.49(f) at that date.

**§ 107.29(d) is `scope: in`, not spent.** § 107.29(a) opens *"Except as provided in
paragraph (d) of this section"*, `night-operation` declared that pointer `unmapped`, and the
target had no entry. It gets one, `night-waiver-termination`, and the verdict is *in* because
both of (d)'s sentences are in force at the 2026-01-01 baseline: the first is a standing
prohibition with no sunset, and **a rule whose condition can no longer be met is not a rule
that is no longer in force.** `method.md` Phase 1 already draws that line — dates inside a
rule are ordinary operations over a date the caller supplies, not corpus versioning — and
the temporal trial is the standing argument that such dates are answerable. `night-operation`'s
`crossReferences` changes from `unmapped` to `resolvedBy`.

The 2020 map needs none of this: § 107.29 is *Daylight operation* at that date and (a)
reads *"No person may operate a small unmanned aircraft system during night"*, with no
carve-out and no paragraph (d), read directly from `part107-2020-01-01.xml`.

### 4. Two corrections to records this decision had to read

**The undefined-term sweep undercounted by one row.** Trial 1's README records *"directly
participating"* against `over-human-beings` only. § 107.49(b) uses the same undefined term
to delimit **who must be briefed**, at both dates. Two further instances; the residue is
eleven rows and twenty-two instances, not ten and twenty. `participant-briefing` depends on
`direct-participation` for that reason.

**`night-operation`'s `unmapped` reason misread a date.** It said the waivers issued before
March 16, 2021 *"terminated on that date"*. § 107.29(d) says they *"terminate on May 17,
2021"*, and March 16, 2021 is the issuance cut-off. Prose the checker could only require, not
read — which is the limit 0009 states for `unmapped`, met on its first instance.

## Alternatives considered

**Reading 1 — the family is assertions, and the gates are blind to it.** Rejected on the
evidence: it is right about ten of the twenty instances and wrong about six, and it cannot
say what an engine would be demanding for *"working properly"* or *"effective"*. It is also
the answer 0008 rejected **test 4** for producing — *"a test that settles #11 by accident is
not fit to adopt"* — and adopting it here as a deliberate ruling would need the argument
test 4 never had. The argument offered for it is that the person is the only possible source,
and § 107.39(b) refutes that as a criterion: the only possible source there is also a
person, and the entry is an assertion because of the **measure**, not the source.

**Reading 2 — the family is gaps, and 0005's remainder was a mis-reading.** Rejected on the
evidence: it is right about six of twenty. § 107.31(a) states four purposes in an explicit
*"in order to"* clause, which is a stronger statement of the measure than any of the four
assertions 0005 and 0008 already accept; calling it a gap would make the map say the corpus
was silent where it enumerated.

**Split the difference by entry rather than by term** — call `visual-line-of-sight` an
assertion and `preflight-actions` a gap, and stop. Rejected: `preflight-actions` contains
three assertions and two gaps, and § 107.49(e) contains one of each in one sentence.
`kind` is entry-level, which is exactly why 0005 ruled that the standard becomes its own
entry; classifying a whole entry by one of its clauses is the error 0005 named and this would
repeat it four times.

**A fourth `kind`, or a field for "only a person can know this".** Rejected on 0005's
standard. It names a true distinction and nothing could check it: every entry in both maps
consumes facts only a person can supply, and the field would be true of all of them. It is
`surprising: true` in a new costume.

**Keep § 107.29(d) out of scope as spent.** Rejected. *Spent* is a claim about the rule's
reachability, not about whether it is in force, and (d)'s first sentence has no sunset. The
project's own temporal axis is the reason: this repository maps the same corpus at two dates
precisely because *"was this legal then"* is a question it takes seriously, and a rule whose
operative dates are in the past is answerable for a caller-supplied date in the past.

**Add a `§ 107.200` entry while there.** Rejected as scope creep. The reference is recorded
as `unmapped` with a reason, which is the weaker of the two answers 0009 allows, and
`night-waiver-termination`'s `note` says so.

## Consequences

**`corpus-map.md` and `method.md` are brought into line in the same change**, and both name
this record. They have now disagreed twice — 0005 records that a mapper following Phase 4
produced exactly what the maps contained, and 0008 had to repair the same joint — so the
`kind: assertion` section and Phase 3/Phase 4 state one procedure and one ruling on parameters.

**Trial 1's undefined-term sweep table is updated in place**, its ten `#11` rows replaced by
the verdicts above and the eleventh row added, because a table citing an open issue that has
been decided sends the next reader to the wrong place.

**The maps grow by a third.** 40 and 37 entries against 29 and 27, and **33 of the 77 entry
instances are now an assertion (19) or a gap (14)**, almost all of them split out of a rule
that consumes them — `moving-vehicle-operation` is the one gap that is a whole rule. That is
the cost of 0005's ruling that `kind` is entry-level, paid in full for the first time, and it
is worth stating plainly: the decomposition a map needs is finer than the section structure
a regulation is written in, by roughly a third on this corpus.

**What this does not settle, stated where the claim is made.**

- **A measure can itself be open, and gate 3 does not ask.** § 107.49(a) states what the
  assessment is measured against — *"risks to persons and property in the **immediate
  vicinity**"* — and the measure carries an undefined degree of its own. § 107.49(b)'s
  five briefing topics are each open-textured. Gate 3 asks whether a measure is *stated*, not
  whether it is *determinate*, so both fire. A measure that needs a measure is a shape 0008's
  procedure cannot see, and this record names it rather than deciding it: **filed, with two
  instances per map**.
- **Splitting one sentence under two ids.** 0005 refused it for `must-play-whole-throw`
  because it makes `locator` ambiguous; `right-of-way` / `well-clear` does it anyway, and so
  does § 107.49(e) here. The two precedents are not reconciled and this record does not
  reconcile them; it follows the nearer one and says so in `attached-object-secure`'s `note`.
- **One term, two sections, one locator.** `direct-participation` governs § 107.39(a) and
  § 107.49(b) and cites only the first, because `check-locators-section.py` reads one
  section per citation. The second use is recorded in prose, which is the carrier 0003 and 0004
  both rejected. A grammar limit rather than a schema one, and it will recur on any corpus that
  uses one undefined term in two places.
- **Nothing here is a check.** `clarity` and `kind` are still compared against nothing that
  reads the corpus. Trial 1's sweep is a review obligation with a recorded count, and so is
  this. Every verdict above could be wrong and every gate in the repository would stay green.

**The evidence base is one corpus at two dates, twenty-two instances, and the four uncontested
assertions 0008 tested the gates against.** The regulation engine
([#3](https://github.com/brandonifco/rules-factory/issues/3)) is the next thing likely to
falsify it, and it is being built next on purpose.
