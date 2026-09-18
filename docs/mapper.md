# The mapper

The subsystem that turns a corpus into a candidate map, and the record of how it was read.

It is a sibling of map validation and of the factory, over the map contract they share
([0032](decisions/0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md)).
Three different questions, three trust boundaries:

| Subsystem | The question it asks |
|---|---|
| **Mapper** | What does this corpus say, and where does its certainty end? |
| **[Validator](validator.md)** | Has the mapper justified those claims, and is this map safe to rely on? |
| **Factory** | Given an acceptable map, what follows mechanically? |

The mapper is an interpreter, and it is not allowed to certify itself. That is the whole reason
[the validator](validator.md) is a sibling and not a utility hanging off this one.

## What is here and what is in the method

[`docs/method.md`](method.md) is the method: what a mapper does, in what order, and why. It stays
a document, because most of it is judgement a program cannot make — whether a sentence states a
rule, whether two readings are both defensible, whether an example bounds a term or is one.

`tools/mapper/` is the part of it that is mechanical: **the protocol that says how a particular
corpus communicates rules, and the interrogation a protocol obliges.** The method says *walk the
corpus*; the protocol says what walking this corpus means.

## The mapping protocol

`mapping-protocol.json`, beside the map. One per map, and `validate.sh` fails a map without one:
a map with no protocol cannot say how it was read.

It is **not** packed into the map package
([0015](decisions/0015-a-map-is-published-as-a-versioned-package.md)). The package carries the
map, the manifest and the checker, because those are what a consumer needs to judge and build
from the map. The protocol is how the map was *made*, which is the mapper's business and not the
factory's — the factory asks for a valid, certified map and nothing about how it was read.

```json
{
  "protocolVersion": 1,
  "corpus": "srd-5.2.1",
  "units": ["glossary-definition", "heading", "paragraph", "list-item"],
  "pointerMechanisms": [
    { "mechanism": "phrase" },
    { "mechanism": "defined-term-use", "vocabularyFrom": "condition-list" }
  ],
  "requiredSweeps": ["definitions", "vocabulary", "applicability", "exceptions",
                     "undefined-terms", "cross-references", "extent-coverage"],
  "adapterReach": {
    "text": "readable",
    "tables": "rendered-page-required",
    "columns": "rendered-page-required",
    "illustrations": "unsupported"
  }
}
```

Every vocabulary is closed, for the reason every vocabulary in the map is closed: a value
nothing holds to a set means whatever the last writer thought. The sets are in
[`tools/mapper/protocol.py`](../tools/mapper/protocol.py), which is where they are enforced.

| Field | What it says |
|---|---|
| `units` | the shapes this corpus states rules in — what a mapper reads one at a time. The walk is bounded ([method](method.md#phase-2--map-the-corpus)); this says by what |
| `pointerMechanisms` | how this corpus points at a meaning it gives elsewhere ([0026](decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)) |
| `requiredSweeps` | the completeness challenge this mapping owes, run by [`mapper sweeps`](#the-sweeps) over the units the walk left unaccounted ([#250](https://github.com/brandonifco/rules-factory/issues/250)). A required sweep the registry does not implement is reported by name and exits NOT VERIFIED |
| `sweepCues`, `sweepCuesReason` | optional. The cues *this* corpus states a kind of rule with, read in addition to the built-in list, and the account of a sweep whose cues fire nowhere in the extent. Both take `pointerPhrases`' shape ([0026](decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)) |
| `adapterReach` | how far the extraction reaches into each modality ([0004](decisions/0004-adapter-reach-is-a-property-of-the-entry.md), [0024](decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)) |

### Why `pointerMechanisms` exists

Because a phrase list was the wrong interrogation mechanism for a corpus and nothing could say
so. [#208](https://github.com/brandonifco/rules-factory/issues/208) measured it: against the
SRD's conditions the declared `pointerPhrases` detect **0** pointers in passages holding **51**
bare condition-name references, leaving 102 of 107 `crossReferences` declarations obliged by
nothing. No regex fixes that, because the corpus points by **naming a defined term**, and the
words of a pointer in one entry are the words of the definition in another.

What separates them is where the sentence is. A naming of a term inside the passage that defines
it is the definition; a naming of it anywhere else is a pointer. The passage is the container the
citation names ([0030](decisions/0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md)),
so two entries citing the same container are inside the same definition.

The vocabulary is read **out of the map**, never out of the protocol: the corpus already states
its defined terms somewhere, that statement is an entry, and its term-anchored `crossReferences`
are already term → defining entry. A second copy in the protocol would be a second definition to
keep in step.

A mechanism is either detected by this subsystem or detected somewhere the protocol checker
names; a mechanism in neither is refused. `phrase` is detected by
`check-map.py --only cross-references`, and `section-designation` by the corpus's own locator
checker. They are declared here anyway, so a protocol is the whole account of how a corpus
points rather than the part this package happens to implement.

## The inventory

`extent` claims coverage — pages 177–191, or a list of section designations — and until
[#255](https://github.com/brandonifco/rules-factory/issues/255) nothing evidenced the claim. The
locator checkers' `coverage` comes closest and asks a much coarser question: is every *page*, or
every *section*, of the extent touched by some quote? A map satisfies that by reaching one
sentence on a page and says nothing about the rest of it.

`mapper inventory` asks it at the grain the corpus states rules in. It enumerates the units the
extent selects, through the adapter the corpus manifest names, and gives each one of three
verdicts:

| Verdict | What it means |
|---|---|
| **reached** | some entry's quoted `evidence` sits in the unit — a quote found in the unit's own text, not a citation naming it |
| **rejected** | the mapper examined it, it produced no entry, and the reason is recorded. [method.md](method.md) says to drop advice and *note in the entry that you dropped it*; a passage that produced no entry at all has no entry to note it in, and that note lives in `mapping-inventory.json` |
| **unaccounted** | neither. Nobody can tell from the map whether it was read and dismissed or never opened, which is the state a map exists to distinguish from a recorded verdict |

Unaccounted units are **NOT VERIFIED** (exit 3), never a failure: whether a passage owed an entry
is decided by reading the corpus, and this tool does not read it. What *is* a failure is an
enumeration of no units, or a run in which no entry's quote is found at all — an inventory of
nothing has nothing unaccounted.

The six committed maps report 540 unaccounted units of 806
([#267](https://github.com/brandonifco/rules-factory/issues/267) holds the numbers and what each
one is on reading it). None of the maps was edited to improve them: a map's bytes cannot change
without invalidating its review
([0017](decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)), and the walks these
numbers measure happened months ago.

### `mapping-inventory.json`

Beside the map, like the protocol, and optional — a map that rejected nothing has no file. It is
not packed into the map package either ([0015](decisions/0015-a-map-is-published-as-a-versioned-package.md)):
it is a record of how the map was made, which is the mapper's business and not a consumer's.

```json
{
  "inventoryVersion": 1,
  "corpus": "hoyle-1909",
  "rejected": [
    { "unit": "p. 277 block 2", "ground": "heading", "note": "the chapter's own heading line" },
    { "unit": "p. 277 block 3", "ground": "advice",
      "note": "counsel on which point to make first; it obliges nothing" }
  ]
}
```

`ground` is closed (`advice`, `preamble`, `heading`, `page-furniture`, `restatement`,
`out-of-extent`, `beyond-adapter`), and a `note` is required: a ground alone is a label, not a
reading. A rejection naming a unit the extent does not enumerate is a claim about nothing, and
one naming a unit an entry quotes is a contradiction; both fail the run.

### The adapter interface

The three corpus grammars already had three locator checkers, and each answers *where is the
passage this citation names*. None could answer *what is in the extent that no citation named*.
[`tools/mapper/corpus.py`](../tools/mapper/corpus.py) is the other half: an `Adapter` cuts a
corpus into the units an extent selects, in reading order, each with a stable key and its text.

| Manifest `adapter` | Extent it reads | What a unit is |
|---|---|---|
| `plain-text` | `page` | a blank-line-separated block, keyed `p. 271 block 3` |
| `pdftotext-page-marked` | `page`, with `endsBefore` (0024) | the same, with the marker on a line of its own |
| `ecfr-xml` | `section-designation`, with `tables` (0035) | a paragraph, a worked example, a section's heading, or a **row** of a table the extent slices, keyed `§ 107.29 ¶4 (a)` or `§ 172.101 table 3, row [column 2 = "Acetal"]` |

That is the whole interface, and it is small on purpose. Marking a unit *reached* could have been
done by parsing each entry's citation and comparing it against the unit's designation, which
would have put a second citation parser per grammar into the mapper. It is instead done by
finding the entry's **quoted evidence** in the units' own text: a quote is the same kind of
object in every corpus, so the measurement is one implementation, and it is the stricter reading
— a citation naming a section is not a quote sitting in it. `units()` is also what [a
sweep](#the-sweeps) walks, which is why it returns the text rather than a locator: a sweep asks
what a unit says.

**A table's rows are units, and the extent says which of them it took**
([0035](decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md),
[#280](https://github.com/brandonifco/rules-factory/issues/280)). A row's unit key *is* the
citation that names it, so a rejection, an inventory line and a locator say the same words, and
its text is its cells in column order with the empty ones kept. Three things are refused rather
than enumerated: a table of a cited section the extent's `tables` list passes over in silence — a
3,687-row table counted as one unit reached by one quote is the measurement this exists to make
impossible — a declared row key that resolves to none or to two rows, and, where a table is taken
whole, a row another row matches in every nameable cell. Two more are refused for the same reason:
a table whose body carries a cell into the row below, or whose headings do not number its body's
cells one for one, because which column a cell sits in is then not in the markup and a guessed
alignment names the wrong cell silently; and a corpus that prints one section designation twice,
because indexing it would drop the other printing's paragraphs and tables out of the corpus and
every check over them would pass by having nothing to look at. A **two-level heading is read**,
not refused — the spans are expanded into a grid — and a heading row is a unit like any other. A section's table rows
are enumerated after its paragraphs rather than in the place the table is printed: this grammar
walks a section's direct children, a table sits below them, and a reading order it cannot see is
not one it should assert.

A fourth grammar subclasses `Adapter`, implements `units(extent)`, and registers its manifest
`adapter` name. A manifest naming an adapter nothing implements is **refused**: a corpus nothing
can enumerate must not report an inventory of zero unaccounted units.

An enumeration is not a claim that each unit states a rule, nor that the cut is the one a human
would make. A page-marked plain text has no hierarchy at all — pdftotext linearises columns,
Gutenberg wraps lines — so the finest honest cut is the block, and a heading is a block like any
other. A cut that is too fine reports *more* unaccounted units, not fewer: it errs towards
reporting work as unevidenced.

## The sweeps

`requiredSweeps` named eleven completeness challenges and nothing ran any of them, so
`mapper protocol` printed `NOT RUN` on every invocation to keep the declaration from reading as
coverage. `mapper sweeps` is what makes that line stop being true
([#250](https://github.com/brandonifco/rules-factory/issues/250)).

A sweep is **not** a scan of the corpus for cue phrases. That is the shape
[#208](https://github.com/brandonifco/rules-factory/issues/208) measured as structurally blind,
and over a whole corpus it would produce thousands of hits nobody can act on. What changed is the
**candidate set**: the inventory above sorts every unit of the extent into reached, rejected and
unaccounted, and a sweep runs over the unaccounted pile alone, asking

> is there an **unaccounted** unit that looks like it states a rule of this kind, and no entry
> quotes it?

That makes each sweep a recall device over a bounded set, and it changes the risk profile
completely: **a cue a sweep misses does not hide the unit**, because the inventory reports it as
unaccounted regardless. The cues sort a pile that is already visible; they are not what makes it
visible. A finding is **NOT VERIFIED**, never a failure — whether an unaccounted unit owed an
entry is decided by reading the corpus, which this does not do.

Each sweep carries a built-in cue list, and a corpus adds its own in `sweepCues`, read **in
addition** to it, in `pointerPhrases`' shape (0026). Two sweeps do not carry cues of their own:

| Sweep | Why it is not a second implementation |
|---|---|
| `extent-coverage` | it **delegates to the inventory**. Its candidate set is the whole extent, because its yield *is* the unaccounted pile — the denominator every other sweep is measured against. The name is kept rather than retired because a protocol has to be able to say a mapping owes a coverage challenge, and `mapper inventory` is a separate command `requiredSweeps` cannot oblige. It is also the one sweep a zero yield is a **pass** for |
| `cross-references` | `mapper pointers` implements `defined-term-use` and `check-map.py --only cross-references` implements `phrase`, and both read **entries' quoted evidence**: they ask whether a pointer the map already quotes is declared. Neither can see a pointer in a passage no entry quotes, which is exactly the unaccounted pile. This sweep asks that other half, and takes its corpus-specific cues from the manifest's own `pointerPhrases` rather than keeping a second copy. It does not count a unit naming **its own** section: 0009 refuses a self-reference as a pointer, and without that it fires on every heading of a designated corpus and has sorted nothing |

### A zero that means something, and a zero that does not

A sweep that fires on no unaccounted unit but fires on units the walk **reached** is not silent:
its cues work in this corpus, and the walk reached every unit of that kind. That is the outcome a
completeness challenge is asking for, and the run says how many. Part 107's twelve unaccounted
units are its twelve section headings, and all six of its cue sweeps report exactly this.

A sweep that fires **nowhere in the extent at all** is the ambiguous one: either the cues are
wrong for this corpus or it states nothing of that kind, and the two must be distinguishable. So
it fails (exit 1) unless the protocol declares `sweepCuesReason` for it, and a reason a live cue
contradicts fails too. Hoyle declares two: `except`, `unless`, `other than`, `notwithstanding`
and `provided that` do not occur anywhere on pages 271–280, and neither does any definitional
verb.

What the sweeps found on the six committed maps, per map and per sweep, is
[#277](https://github.com/brandonifco/rules-factory/issues/277). No map was edited to improve
those numbers, for the reason no map was edited to improve the inventory's: a map's bytes cannot
change without invalidating its review ([0017](decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)).

## Commands

```bash
python3 tools/mapper protocol <corpus-map.json>   # is this a protocol the mapper can act on?
python3 tools/mapper pointers <corpus-map.json>   # run the interrogation it obliges
python3 tools/mapper inventory <corpus-map.json>  # what the extent claims, against what the walk reached
python3 tools/mapper sweeps <corpus-map.json>     # the completeness challenge it owes, over what the walk left
python3 tools/mapper stage <staging.json>         # stage the inputs a blind second mapping gets
python3 tools/mapper stage --verify <staged-inputs.json>   # was a blind run given what it says?
```

Four exit codes, the factory's four:

| Exit | Meaning |
|---|---|
| `0` | every declaration held, and something was actually examined |
| `1` | a declaration is wrong, or an interrogation that was declared detected nothing at all |
| `2` | a usage error |
| `3` | **NOT VERIFIED**: the run found what it cannot judge — a pointer the map does not declare, a unit inside the extent that no quote reaches and no rejection accounts for, a sweep finding, a required sweep the registry does not implement, or a staged document naming a word that is both an entry of this corpus and ordinary English. Whether each is owed, or is a leak, is decided by reading (0026), not here |

A silent zero is a failure, not a pass: a corpus that declares a mechanism and on which nothing
fires has either the wrong mechanism declared or a map whose evidence spans do not reach its
pointers. That is the same rule 0026 already applies to phrases, and it is exactly the shape #208
measured. A sweep whose cues fire nowhere in the extent is the same failure, answered the same
way: with the corpus's own cues, or with a reason.

## Staging a blind second mapping

[The method](method.md#before-the-map-is-used--a-blind-second-mapping) says a second mapper gets
the corpus extract and the two specification documents *with every worked example drawn from the
corpus under mapping removed*. Staging that is mapping — producing both mappings from
independently staged inputs — so it lives here, and comparison, adjudication and certification
stay with [the validator](validator.md) ([0032](decisions/0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md),
[0033](decisions/0033-the-validator-is-the-adversary-and-validates-the-uncertainty-too.md)).

`stage` reads a **staging spec** committed with the run and writes a bundle beside it:

| in the spec | what it says |
|---|---|
| `map` | the map of the slice being mapped; every committed map of the same `corpus` supplies the scan's vocabulary |
| `documents` | the documents to stage, by path |
| `edits` | one declared substitution per worked example, each with a `why`, each required to match its document **exactly once** |
| `acknowledged` | a term the scan will find that is not a leak, by document, with the reason |

| in the bundle | what it is |
|---|---|
| the documents | as redacted, with every link the mapper cannot follow reduced to its text |
| `REDACTIONS.md` | every edit with its line, every link flattened, everything named and left in, and what the scan did not look for |
| `staged-inputs.json` | the digests of all of it, the maps the vocabulary came from, and the vocabulary itself |

Which examples are "drawn from the corpus under mapping" is a judgement, and the substitutions
are where it is made. What is mechanical is **completeness**: an occurrence of a hyphenated entry
id or of the corpus id is `certain` and fails the staging; a one-word id, an entry `name` or a
word of the corpus id is `possible`, because a document uses those words for its own reasons, and
the run is NOT VERIFIED until the spec rules on each. A heuristic that silently missed a leak
would be worse than no tool, so nothing here passes an occurrence it cannot decide.

`--verify` re-hashes every file a record names *and re-runs the scan over the staged documents*,
because a digest proves the bytes did not move and not that they were redacted. `validate.sh`
runs it on every committed record, and `tools/check-map-review.py` requires a
`blind-second-mapping` review to name one — or to say, out loud and on every run, that it has
none.

## What it does not do yet

- **It produces no map.** Mapping is still done by hand, by the method. What this makes checkable
  is that the walk was the walk this corpus requires.
- **A sweep sorts the unaccounted pile; it does not read it.** Every finding is a unit the
  inventory already reports, ordered by what its words look like. Deciding whether one owed an
  entry is still a mapper's reading of the corpus, and the sweeps make that pile approachable
  rather than answering it. `check-map.py --only cross-references` and `mapper pointers` still
  own the entry-side question, and neither is re-implemented here
  ([#250](https://github.com/brandonifco/rules-factory/issues/250)).
- **A staged blind input is checked for what it names, and not for what it means**
  ([#223](https://github.com/brandonifco/rules-factory/issues/223) is closed; `stage` is below).
  The scan holds the staged documents to the vocabulary of every map of the corpus. An example
  that paraphrases a rule of that corpus while naming no entry, no id and not the corpus is
  invisible to it, and the spec's declared substitutions are the only thing that covers it. Every
  run says so, and so does every record it writes.
- **The inventory measures the walk, and nobody has answered it.** Every unit inside every
  committed map's extent is enumerated and counted, and 540 of 806 are unaccounted
  ([#267](https://github.com/brandonifco/rules-factory/issues/267)). No map records a rejection
  yet, so *examined and dismissed* and *never opened* still read the same for those units — what
  changed is that the number is now a fact rather than an impression.
- **The detector reads `evidence`,** which is the corpus's words for one rule and not the whole
  passage, so a naming outside every entry's quoted span is invisible to it. And it matches a
  term exactly, so a corpus that inflects its defined terms needs a mechanism this is not.
