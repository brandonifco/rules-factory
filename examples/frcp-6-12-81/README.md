# Trial 11 — Federal Rules of Civil Procedure 6, 12 and 81

Run of [the method](../../docs/method.md) against a corpus chosen for a different axis of
attack from every corpus before it. [#264](https://github.com/brandonifco/rules-factory/issues/264)
is the trial; [#265](https://github.com/brandonifco/rules-factory/issues/265) is why a trial is
run before a concept is admitted, and
[0063](../../docs/decisions/0063-no-new-map-concept-without-a-corpus-that-forces-it.md) is the
rule that governs what this trial is allowed to change.

**It is the last pre-1.0 architecture experiment.** What it is for is to find out whether the
map contract, exactly as it stands, can say what this corpus says. Not whether a nicer contract
could.

## Why this corpus

Where trial 10's Hazardous Materials Table attacks *where a rule lives*, the Federal Rules of
Civil Procedure attack **when a rule applies and who may change it**:

- **Rule 6** is exact calendar arithmetic — count forward, count backward, exclude the trigger
  day, roll off weekends and legal holidays, an inaccessible clerk's office — sitting directly
  beside `for good cause`, `excusable neglect` and a court's order, and with a short list of
  extensions a court **must not** grant. Computation an engine can do to the day, and delegation
  it cannot, in one rule.
- **Rule 12** hangs deadlines off **procedural state**: what was served, what was waived, what
  was joined, what is preserved. A deadline whose condition is history is a gate no mapped
  corpus has had.
- **Rule 81** makes **applicability itself conditional** across whole classes of proceeding, and
  then gives removed actions their own deadlines on top.

Nothing in the six committed maps has any of this. The nearest is § 1.121-1(f)'s flat effective
date, which gates a section and turns on nothing.

## The admission record

| | |
|---|---|
| `sourceId` | `frcp-6-12-81` |
| Title | Federal Rules of Civil Procedure, Rules 6, 12 and 81 |
| Adapter | `uslm-xml` |
| Locator grammar | `section-designation` — `Rule 6(a)(1)(A)` |
| `contentHash` | `d4e63d1f…` over [`frcp-6-12-81.xml`](frcp-6-12-81.xml) |
| `hashDerivation` | `uslm-courtrule-without-usc-notes` |
| `asOf` | 2025-12-03, the release point's own stamp |
| Licence | `public-domain-us-government` ([CORPUS-LICENCE.txt](CORPUS-LICENCE.txt)) |
| Posture | `pin-in-repo`, `committed-copy`, `quotation: verbatim`, `randomness: none` |
| Retrieved from | `https://uscode.house.gov/download/releasepoints/us/pl/119/110/xml_usc28A@119-110.zip` |

### Why the committed bytes are a derivation

The Office of Law Revision Counsel serves Title 28 Appendix as **one** 4.7 MB USLM document
holding the Appellate, Civil and Evidence rules together. Every other corpus this repository
admits arrives as its own served document — the eCFR versioner returns one section, Project
Gutenberg returns one book — so `retrievedFrom` alone has always said what the digest covers.
Here it cannot: a digest over the release would cover two other rulebooks, and no reader could
tell which bytes a quote is held to.

[`derive-corpus.py`](derive-corpus.py) is the derivation, and `hashDerivation` names it. It takes
the three `<courtRule>` elements **verbatim from the release's bytes** — by text scan, not by
parse and re-serialise, so nothing rewrites an entity reference or an attribute order — and drops
one child of each: `<notes type="uscNote">`, the Notes of the Advisory Committee on Rules and the
editorial amendment notes. `derive-corpus.py --from <release> --check frcp-6-12-81.xml` re-derives
and compares.

**Dropping the notes is an admission decision and it has a cost.** The Advisory Committee Notes
are transmitted with the rules and courts read them as an interpretive aid; they are not the
rule, which is what the Supreme Court prescribed under 28 U.S.C. 2072 and Congress let take
effect. A map built over them would quote a commentator's account of a rule as though it were
the rule. What it costs is stated rather than hidden: **no entry of this map may be supported by
an Advisory Committee Note, and a rule stated only in one is beyond this adapter's reach.** The
`<sourceCredit>` is kept, because it is the rule's own amendment history and is inside the
`<courtRule>` element the Code prints.

## The slice

All of Rule 6, all of Rule 12, all of Rule 81. Three whole rules and no part of a fourth:
15,549 characters of whitespace-normalised text — 4,569 in Rule 6, 6,250 in Rule 12, 4,730 in
Rule 81 — against the ~8,000 characters both of the first two trials took.

Whole rather than sliced, because every question this trial asks is about how the rules reach
each other. Rule 6(a) is what every period in Rule 12 and Rule 81(c) is counted by; Rule 6(b) is
what a court may do to any of them; Rule 81(a) is what decides whether any of it applies at all.
A slice that cut inside one of the three would produce a map whose gates point outside it, which
is the shape trial 9 already measured.

## The hypotheses, before anything is mapped

Written from a reading of the corpus and before a single entry exists, so that the map cannot be
read backwards into a confirmation. A run that confirms all seven is a failure to have picked a
hard enough corpus.

- **H1 — a computed deadline is one entry.** *"within 21 days after being served with the summons
  and complaint"* states a period, a trigger and an actor in one sentence. H1 says that is one
  `kind: operation` entry which `dependsOn` Rule 6(a)'s counting rules, and that no field is
  needed to hold the period, the unit or the triggering event: they are in the quote, and what
  computes them is the engine's code, which the map deliberately does not type
  ([corpus-map.md](../../docs/corpus-map.md), *the map declares no types*).
- **H2 — the two gate fields carry a court's power over time.** Rule 6(b)(1) lets a court extend
  any period for good cause; Rule 6(b)(2) forbids it for six named rules; Rule 6(c)(1)(C) lets a
  court order displace the 14-day notice period; Rule 12(a)(4) says a motion alters the Rule 12(a)
  periods. H2 says `enabledBy` and `suspendedBy`, holding entry ids and nothing else
  ([0003](../../docs/decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md),
  [0011](../../docs/decisions/0011-a-gate-has-a-direction.md)), express all four with no new
  relation, and that whether a gate holds is a fact the caller states
  ([0021](../../docs/decisions/0021-a-gate-outside-the-slice-is-held-by-the-caller.md)).
- **H3 — delegated judgement is an assertion, not an ambiguity.** *"for good cause"*, *"excusable
  neglect"*, *"so vague or ambiguous that the party cannot reasonably prepare a response"*,
  *"early enough not to delay trial"*, *"to the extent applicable"*. H3 says these are open terms
  the corpus deliberately delegated with a measure, so they are `kind: assertion` with
  `assertedBy` naming the court
  ([0025](../../docs/decisions/0025-an-assertion-names-who-asserts-it-and-an-operation-names-what-it-draws.md)),
  and that `clarity: ambiguous` would report a deliberate delegation as a defect.
- **H4 — conditional applicability is a gate.** Rule 81(a) turns whole classes of proceeding on
  and off; Rule 81(c)(1) turns the rules on for a removed action. H4 says these are ordinary
  entries named in `enabledBy` / `suspendedBy`, and that
  [`applicability-reach`](../../docs/validator.md) sees them.
- **H5 — procedural history is a caller-supplied parameter and gets no entry.** What was served,
  waived, joined or omitted is a fact about a case, not a rule of the corpus, so phase 4's gate 1
  gives it no entry and the rules that turn on it are ordinary operations over facts the caller
  states. H5 says the map needs no state machine and no `state` field.
- **H6 — the existing checks can see a removed deadline.** Deleting a period, a trigger or a gate
  from one entry is caught by something other than a person's memory. Trial 10 falsified its own
  H6 on a tabular corpus; this asks the same question of prose.
- **H7 — the contract can read this corpus's designations.** `Rule 6(a)(1)(A)` is a structural
  designation, listed and not ranged, exactly as `§ 107.29(a)(2)` is, and
  `extent.unit: "section-designation"` is the unit for it. **Already known to be strained at
  admission** — see below — and stated anyway, because what is strained and what is broken are
  different findings.

### What would falsify each

| | Falsified if |
|---|---|
| H1 | the period, the unit or the triggering event has to go in a field the contract does not have, or splitting a deadline sentence produces two entries neither of which states a rule |
| H2 | a rule that *alters* a period rather than enabling or suspending one has to be recorded as a gate that is false about the corpus, or the relation ends up in a `note` |
| H3 | one of the delegated terms states no measure **and** names no party, so it is neither an assertion nor a clear rule, and `ambiguity` cannot hold it either |
| H4 | an applicability whose condition is a class of proceeding cannot be a gate because the class has no entry, or `applicability-reach` cannot see a gate whose reach is a corpus outside the slice |
| H5 | a waiver rule — Rule 12(g)(2), Rule 12(h)(1) — cannot be stated without the map recording what has already happened in the case |
| H6 | deleting a period from an entry's evidence, or a `dependsOn` edge to Rule 6(a), passes `check-map.py` and the locator run |
| H7 | the contract's reading of `section-designation` is CFR-specific, and a second designation-cited corpus needs a new `extent.unit` value — which under 0063 is a new map concept and needs the full four steps |

### H7 is strained at admission, and the strain is recorded here before it is repaired

`tools/mapvalidator/locators.py` reads a `section-designation` citation with two expressions
copied from `examples/faa-part-107/check-locators-section.py`:

```python
CITE_SECTION   = re.compile(r"§+\s*(\d+\.\d+(?:[A-Za-z]|-\d+)?)(?![A-Za-z0-9-])")
EXTENT_SECTION = re.compile(r"^§\s*(\d+\.\d+(?:[A-Za-z]|-\d+)?)$")
```

Both spell the Code of Federal Regulations and only it. `Rule 6` matches neither, so before a
single entry is written it is already certain that *something* must change for this corpus to be
citable at all. What the trial has to decide is **which** thing, and 0063 is what decides it: a
value in a closed vocabulary is a map concept and needs a corpus that forces it; a check that
reads the wrong thing is a repair and does not. The answer is recorded under
[the outcome](#the-outcome) with the reasoning, not here.
