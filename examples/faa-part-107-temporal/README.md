# Trial: the same corpus at two dates

Third run of [the method](../../docs/method.md), and the first to exercise the temporal
axis rather than assume it works. Same corpus as [trial 1](../faa-part-107/README.md),
pinned twice.

**Corpus:** 14 CFR Part 107, at `2020-01-01` and `2026-01-01` — either side of Amendment
107-8 (86 FR 4382, January 2021), which rewrote night operations and added subpart D.

**Slice:** the same twelve sections both times, mapped independently against each text.

**Result:** 44 sections → 61. Of the twelve mapped, **eight unchanged, four changed, none
removed.** 23 entries in 2020, 24 in 2026.

```
2020-01-01  ->  2026-01-01

  ADDED    subpart-d-categories
  CHANGED  night-operation: name, clarity, evidence, dependsOn, ambiguity
             clarity clear -> ambiguous
  CHANGED  anti-collision-lighting: name, evidence, note, locator
  CHANGED  preflight-actions: note
  CHANGED  single-aircraft: evidence, note
```

## The finding worth the trial

**An amendment introduced an ambiguity.**

In 2020, § 107.29 was titled *Daylight operation* and said: "No person may operate a small
unmanned aircraft system during night." A flat prohibition — perfectly clear, trivially
implementable, `clarity: clear`.

By 2026 it is titled *Operation at night* and permits night flight subject to training and
"lighted anti-collision lighting visible for at least 3 statute miles **that has a flash rate
sufficient to avoid a collision**." That clause states no rate. `clarity: ambiguous`,
`RequiresInterpretation`.

The rule became more permissive and less determinate at the same time. An engine built
against the older text could answer the question completely; one built against the newer
text cannot, and must decline.

This is the first evidence that **`clarity` is a property of a corpus version, not of a
rule** — and that the direction of travel is not always toward precision. A map is a
statement about one text, and an engine's honesty about what it cannot answer can change
without the engine changing at all.

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

## Cost

Fetching both versions, slicing, mapping the second text and diffing: under an hour, and
most of that was reading the 2020 text closely enough to be sure which differences were
real. Re-mapping was much cheaper than mapping, because the question is "what moved" rather
than "what is here" — which suggests a maintained map is considerably cheaper to keep
current than to create.
