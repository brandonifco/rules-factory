# 0004 — Adapter reach is a property of the entry, recorded structurally

## Status

Accepted — 2026-09-13.

## Context

The second trial — [Hoyle's Backgammon](../../examples/hoyle-backgammon/README.md) — found a
rule that is fully determined in the corpus and invisible to the reader admitted to read it.
The starting arrangement of the board, without which no game begins, is stated entirely as
*"with the men placed as in Fig. 1."* The declared adapter is `plain-text`. The figure is
not text.

At runtime this is `MissingRulesData`, which is right, and the kernel needed no change. The
problem is upstream of runtime. The first trial produced `MissingRulesData` too — § 107.36
defines hazardous material by reference to 49 CFR 171.8, and § 107.29(c)(3) defers Alaskan
civil twilight to the Air Almanac — and the manifest's `references` list, added after that
trial, describes those: named corpora, marked not admitted, boundary inspectable.

`references` cannot describe the backgammon case, because there is nothing to reference. The
rule is in *this* corpus, in another modality of it. What stands between the engine and the
rule is the adapter.

The method currently instructs a mapper to name the modality in the reason string. That is
prose discipline. It means "this corpus contains the rule and our reader cannot see it" and
"this rule is defined in a corpus we did not admit" are the same shape in the map, and
telling them apart requires reading a sentence and trusting that whoever wrote it observed
the convention.

The one illustration is the mild case. The general case is worse, and it is the case the
factory is most likely to meet: a PDF rulebook read as extracted text loses exactly the
tables a rules engine most needs, and it loses them silently — the adapter returns text, the
text is missing a column, and nothing anywhere says a column was lost. No trial has produced
that: both corpora mapped so far are text end to end. It is the reason to build the
structure now rather than after a trial finds it expensively.

The fact is also **adapter-relative, not absolute**. The same corpus read by an adapter that
can see figures reaches `starting-position`. A record that says only "unreachable" would be
false the moment the adapter is upgraded, and — more usefully — a record that names the
adapter turns "what did the old reader miss?" into a query rather than a re-read.

## Decision

An entry may carry **`beyondAdapter`**, an object with two required fields:

```json
"beyondAdapter": { "adapter": "plain-text", "modality": "illustration" }
```

`adapter` is the `adapter` id of the corpus in the manifest — the reader that cannot reach
the rule. Checkable: it must match the adapter declared for the entry's `locator.sourceId`.

`modality` is a short noun phrase naming what holds the rule in the corpus: `illustration`
here. It is **not** a reason sentence and not a place for explanation; the entry's `note` is
that.

`modality` is deliberately **not** a closed vocabulary. One instance has been observed. A
closed set written from one instance — illustration, table-as-image, layout, typography — is
invented rather than derived, and the map has enough closed vocabularies that are earned
(`kind`, `scope`, `clarity`, `fate`, `status`) to be careful about adding one that is not.
It can be closed later, from evidence.

The entry's `locator` is still required and still points at the passage that *states* the
rule — here, the sentence that says the men are placed as in Fig. 1. `beyondAdapter` says
the statement cannot be read through, not that there is nothing to cite.

`beyondAdapter` joins the map-to-runtime correspondence table: an entry carrying it is
`MissingRulesData`. That makes the record load-bearing rather than annotation, which is the
test this project applies to every field.

## Alternatives considered

**The reason string is sufficient — record a decision saying so.** Rejected. It is the
status quo, it is what the issue offered as the honest cheap answer, and the argument
against it is that the project has repeatedly found confidently-worded prose sitting next to
code that did not match. A convention no check can read is one nobody can be shown to have
broken. The specific loss is that the boundary of an engine becomes uninspectable: with
`references` describing elsewhere-defined and `beyondAdapter` describing adapter-unreachable,
"what can this engine not see, and why" is answerable from the manifest and the map. With
one of the two carried in prose it is not.

**A boolean `unreachable: true`.** Rejected: it states an absolute where the fact is
relative. It is false under a better adapter and it discards the two things worth knowing —
which reader failed, and what it failed on.

**A manifest-level list, like `references`.** Rejected: reachability is per-entry, not
per-corpus. The plain-text adapter reads twenty-three of the twenty-four backgammon entries
perfectly well. A manifest-level statement would either condemn the whole corpus or say
nothing.

**Declare a second adapter for the figure and admit the corpus twice.** Rejected as a
different failure: the kernel refuses two baselines for the same corpus by id, and for good
reason — a locator names a corpus by id alone, so two entries for `hoyle-1909` make every
citation ambiguous. Confirmed in the third trial against the published package. The adapter
is not the corpus's identity and must not be smuggled into it.

## Consequences

An entry beyond the adapter's reach is now distinguishable from one defined elsewhere
without reading prose, and the distinction is checkable: `adapter` must match the manifest,
`modality` must be present.

**It does not make the rule reachable, and it does not find the ones nobody noticed.** Both
are worth stating plainly. `beyondAdapter` records a limit a human recognised; an adapter
that silently drops a table produces an entry nobody writes, and no field on a map that does
not exist can help. Detecting that is an adapter's problem — a text adapter that knows it
skipped a `<table>` element could say so — and it is not solved here.

**It leaves an asymmetry.** The backgammon map's `starting-position` now carries its decline
reason structurally, in `beyondAdapter`. Part 107's `civil-twilight-alaska` and
`hazardous-material` still carry theirs in an `ambiguity` block, on entries whose `clarity`
is `clear` — the block is doing duty as a general carrier for "declined, and here is the
runtime reason", which is not what it is specified to be. Those two entries could point at
the manifest's `references` the way this one points at the adapter. That is a third schema
question, it was not what either issue asked, and it is recorded as an open question rather
than answered here.
