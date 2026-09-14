# Trial: the same corpus at two dates

Third run of [the method](../../docs/method.md), and the first to exercise the temporal
axis rather than assume it works. Same corpus as [trial 1](../faa-part-107/README.md),
pinned twice.

**Corpus:** 14 CFR Part 107, at `2020-01-01` and `2026-01-01` — either side of Amendment
107-8 (86 FR 4382, January 2021), which rewrote night operations and added subpart D.

**Slice:** the same twelve sections both times, mapped independently against each text.

**Result:** 44 sections → 61. Of the twelve mapped, **eight unchanged, four changed, none
removed.** 25 entries in 2020, 27 in 2026 — 23 and 24 as first mapped, before
[0005](../../docs/decisions/0005-a-field-earns-its-place-by-being-checkable.md) split the
delegated standards into entries of their own and
[#26](https://github.com/brandonifco/rules-factory/issues/26) added the fifth.

```
2020-01-01  ->  2026-01-01

  ADDED    flash-rate-sufficient
  ADDED    subpart-d-categories
  CHANGED  anti-collision-lighting: name, evidence, note, locator, dependsOn
  CHANGED  civil-twilight-operation: evidence
  CHANGED  intensity-reduction-in-interest-of-safety: evidence, note, locator
  CHANGED  night-operation: name, evidence, note, dependsOn
  CHANGED  over-human-beings: evidence, note, dependsOn
  CHANGED  preflight-actions: evidence, note
  CHANGED  reasonable-protection: evidence, note
  CHANGED  single-aircraft: evidence, note
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
locators ok (all 25 checked against the section tree)
```

## The finding worth the trial

**An amendment turned a rule the engine computes into one that demands a caller's
assertion.**

In 2020, § 107.29 was titled *Daylight operation* and said: "No person may operate a small
unmanned aircraft system during night." A flat prohibition — perfectly clear, trivially
implementable, and total: given the time, the engine answers.

By 2026 it is titled *Operation at night* and permits night flight subject to training and
"lighted anti-collision lighting visible for at least 3 statute miles **that has a flash rate
sufficient to avoid a collision**." That clause states no rate, and it is not meant to: the
regulator wrote a standard where a number would have gone. The rule is still clear and still
implementable — but the engine can no longer answer from the flight alone. It must **demand
an assertion**, attribute it, and record it with the outcome.

That is what the map now says. The 2026 map gains an entry the 2020 map has no counterpart
for — `flash-rate-sufficient`, `kind: assertion` — and the differ reports it as an addition
rather than as a change of `clarity` on `night-operation`.

**As first mapped, this was recorded as an amendment introducing an ambiguity**, and read as
the first evidence that `clarity` is a property of a corpus version rather than of a rule.
0005 rejected that reading: a delegated standard is not a defect in the text, so `clarity`
does not move, and under the corrected classification that finding has zero instances in any
map. What survives is the stronger half, and it did not need `clarity` to carry it — the
direction of travel is not always toward precision, a map is a statement about one text, and
an engine's honesty about what it cannot answer alone can change without the engine changing
at all.

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
