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
findings 1–4 in the map itself and
[#26](https://github.com/brandonifco/rules-factory/issues/26) added the fifth delegated
judgement: 27 entries. 6 values, 16 operations, 5 assertions. 26 clear, 1 ambiguous. 3
declined. The three extra entries are the delegated standards, split out of the rules that
consume them; the four ambiguities that went away were never gaps in the text.

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
locators ok (all 27 checked against the section tree)
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

Which is why the result is worth stating plainly: **27 of 27 citations in the 2026 map and 25
of 25 in the 2020 map verify, none was found wrong, and none was corrected.** Against
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
