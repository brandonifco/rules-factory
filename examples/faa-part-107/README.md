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
findings 1–4 in the map itself: 26 entries. 6 values, 16 operations, 4 assertions. 25 clear,
1 ambiguous. 3 declined. The two extra entries are the delegated standards, split out of the
rules that consume them; the four ambiguities that went away were never gaps in the text.

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

**Ratio.** Twelve sections produced twenty-four entries, almost exactly 2:1 — twenty-six once
0005 split the two delegated standards out, which moves the ratio very little. Useful for
estimating: this slice is 1/5 of the part, so the whole is roughly 120 entries.

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
out of scope, and it is `subpart-d-categories`.

### 5. Temporal handling covers one of two temporal things

`asOf` pins which text is in force — that works, and is the whole reason the kernel has it.

But the text contains its own dates. § 107.29(a)(1) requires training completed "after
April 6, 2021"; § 107.29(d) terminates certain waivers on dates in 2021. Those are ordinary
operations over a date input, not corpus versioning — but a reader of the method could
easily conflate them, and the method never mentions the second kind.

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
