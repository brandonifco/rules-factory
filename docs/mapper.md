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

Beside the map, and `validate.sh` fails a map without one: a map with no protocol cannot say how
it was read.

**One protocol is about one corpus, and a map has one per corpus it cites**
([0040](decisions/0040-a-protocol-is-about-one-corpus-and-a-map-has-one-per-corpus-it-cites.md)).
`mapping-protocol.json` for a map citing one corpus — every map committed before trial 10 — and
`mapping-protocol-<sourceId>.json` once it cites several
([0039](decisions/0039-the-manifest-pins-every-corpus-a-map-cites.md)). Trial 10's two corpora are
why: § 172.101 states a rule in a table row and points with a bare code in column 7, § 172.102
states prose inside an `EXTRACT` and points with a section designation. A single protocol over
both would have to declare the union of their units and mechanisms, and a union says of each
corpus things that are true only of the other. The protocol's value is that it is specific enough
to be wrong.

A cited corpus with no protocol is refused, naming which; so is a
`mapping-protocol-<sourceId>.json` for a corpus the map does not cite, and a protocol whose
`corpus` the manifest declares but the map never reads. Declared is not read.

It is **not** packed into the map package
([0015](decisions/0015-a-map-is-published-as-a-versioned-package.md)). The package carries the
map, the manifest, the checker and the deterministic verification record that binds those artifacts
to every cited corpus the publish locator run actually read ([0048](decisions/0048-a-verified-map-package-binds-the-exact-artifacts-its-publish-gate-read.md)).
The protocol is how the map was *made*, which is the mapper's business and not the factory's — the
factory asks for a valid, verified map and nothing about how it was read.

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

What separates them is **not** the entry's `scope` or `status`. A `scope: out`, `status: declined`
entry declares the pointers its evidence makes like any other, so this mechanism carries no scope
filter and a naming it finds in one is a defect rather than a false positive
([0058](decisions/0058-a-pointer-is-declared-by-the-passage-that-makes-it-whatever-the-engine-does-with-the-rule.md),
which settled [#254](https://github.com/brandonifco/rules-factory/issues/254) and closed #208).
Satisfaction is per term: one item whose `cites` contains the term discharges it, however many
times the passage names it ([#399](https://github.com/brandonifco/rules-factory/issues/399)).

The vocabulary is read **out of the map**, never out of the protocol: the corpus already states
its defined terms somewhere, that statement is an entry, and its term-anchored `crossReferences`
are already term → defining entries. A second copy in the protocol would be a second definition to
keep in step.

**A term names one or more defining entries, and a pointer is accounted for only when it names
them all** ([0044](decisions/0044-one-printed-code-can-name-more-than-one-rule.md),
[#311](https://github.com/brandonifco/rules-factory/issues/311)). § 172.102(c)(4) says `IB3` in
column 7 authorises IBCs unconditionally and Large Packagings for Packing Group III only — two
rules, in two of its tables, under one printed code. Two term-anchored references say so and
nothing is added to the map:

```json
{ "cites": "IB3", "resolvedBy": "ib3-authorized-ibcs" },
{ "cites": "IB3", "resolvedBy": "ib3-authorized-large-packagings" }
```

The reader kept a `dict` of one target per term, so the **last** declaration won, the first was
discarded, and every check passed: both were real entries, so nothing could see that a declaration
had been dropped. Now both are kept, declaration order decides nothing, a finding names each
target the entry points at none of, and the same target declared twice is **reported** rather than
collapsed — a term may name several entries, and naming one of them twice says nothing the first
declaration does not.

A mechanism is either detected by this subsystem or detected somewhere the protocol checker
names; a mechanism in neither is refused. `phrase` is detected by
`check-map.py --only cross-references`, and `section-designation` by the corpus's own locator
checker. They are declared here anyway, so a protocol is the whole account of how a corpus
points rather than the part this package happens to implement.

### `coded-pointer` — a pointer its column makes

Decided in [0041](decisions/0041-a-coded-pointer-is-made-by-the-column-it-sits-in.md), with its
defining set extended by [0046](decisions/0046-an-additional-rule-can-continue-a-definition.md)
([#321](https://github.com/brandonifco/rules-factory/issues/321)). The mechanism itself was forced by
[#307](https://github.com/brandonifco/rules-factory/issues/307) in trial 10.

```json
{ "mechanism": "coded-pointer", "column": 7, "vocabulary": "special-provision-codes" }
```

49 CFR § 172.101 column 7 holds `IB2, T4, TP1` and nothing else — each a pointer into § 172.102,
with no pointer phrase and no defined term named anywhere near it. `defined-term-use` was
declared for it and **run**, over the seven rows the trial settled: it detected all **33** column
7 occurrences, missed none, and also read the numeric code `148` as a pointer twice where it is
not one — in **column 14**, whose vessel stowage provisions are § 176.84's, and in *"46 CFR parts
30 to 40, 70, 98, 148, 151, 153 and 154"*, where it is a part number.

Firing is not the same as being right. A column 7 code is a pointer **because of the column it
sits in**, and no lexical mechanism can say that, because column membership is not text.

So the detector reads the **structural context** and never the prose: an entry is examined only
when its citation names a cell in the declared column
([0035](decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)'s `…, column 7`), and
each comma- or space-separated token of its evidence is a pointer. The same characters in another
column are not. A token in the pointer-bearing column that the vocabulary does not declare is
reported rather than dropped: it is either a pointer nobody recorded or a vocabulary that is
short.

`vocabulary` names a vocabulary **distributed over the entries that define its terms**
([0045](decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md),
[#314](https://github.com/brandonifco/rules-factory/issues/314)), and this is where it differs
from `defined-term-use`. That mechanism reads its terms out of **one** entry, because the corpus
that forced it prints one — the SRD's glossary list names all fifteen conditions in a sentence.
§ 172.102 prints no such passage: its codes are one per table row, and § 172.102(c) says only
*"The following tables list … the special provisions referred to in column 7"*. An entry indexing
twenty codes it does not print would be refused by the anchoring rule
([0026](decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)),
and rightly: it would be a registry someone wrote, not a passage of the corpus.

So a passage that prints a term declares it directly, anchored in its own evidence
([`defines`](corpus-map.md#defines)). Where a second passage states an additional defining rule
without repeating the term, it can join that direct definition only through an explicitly
[anchored `continuesDefinition`](corpus-map.md#continuesdefinition) (0046). The vocabulary is what
those direct and continued definitions add up to: `(vocabulary, term) → one or more entry ids`.
The continuation copies neither vocabulary nor term, so it cannot become a second registry.

`vocabularyFrom` on a `coded-pointer` is refused, and `vocabulary` on a mechanism that reads
neither kind is refused — each names a different kind of vocabulary, and a mechanism reading the
wrong one would report a clean run over nothing. A name no direct definition establishes is
refused too.

**`defined-term-use` reads either, and exactly one.** Trial 11's corpus is a second one with a
distributed vocabulary, and it has nothing to do with tables: the Federal Rules of Civil
Procedure define *"Last Day"*, *"Next Day"*, *"Legal holiday"* and *"State Law"* in the very
paragraphs the rules using them sit beside, and print no index for `vocabularyFrom` to name.
Declaring the mechanism with neither would leave the terms unstated; declaring it with both would
be two vocabularies for one mechanism, and nothing would say which the detector reads. So the
protocol names `vocabularyFrom`, the one entry that lists the corpus's terms, **or** `vocabulary`,
a name the entries that define its terms distribute — and `_check_defined_vocabulary`, the check
0045 already owns, is what holds the second form to the map. Two
columns may read two vocabularies, and a token of one does not satisfy the other because the text
matches: column 6's `3` is a hazard label, and column 7's numeric codes are special provisions.

`column` is a mechanism parameter, not a protocol field — the protocol's shape is a list of
mechanism objects each carrying its own, and it does not change. `column` on any other mechanism
is refused, and `coded-pointer` without one is refused: without it the mechanism would be a scan
of the corpus's words, which is the failure that forced it.

One thing the measurement says about clean runs generally: the **letter** codes do not collide in
this slice. A seven-row slice chosen without a numeric code would have run clean and concluded
the existing vocabulary sufficed.

## The inventory

`extent` claims coverage — pages 177–191, or a list of section designations — and until
[#255](https://github.com/brandonifco/rules-factory/issues/255) nothing evidenced the claim. The
locator checkers' `coverage` comes closest and asks a much coarser question: is every *page*, or
every *section*, of the extent touched by some quote? A map satisfies that by reaching one
sentence on a page. Since
[0055](decisions/0055-coverage-reports-how-much-of-the-extent-is-quoted-and-a-map-declares-the-floor.md)
it also reports **how much** of the extent the quotes cover, in characters, which says something
about the rest of it — but as a fraction of the whole slice, not as a verdict on any unit inside
it, and that is the difference this section is about.

`mapper inventory` asks it at the grain the corpus states rules in. It enumerates the units the
extent selects, through the adapter the corpus manifest names, and gives each one of three
verdicts:

**Every corpus the map cites is walked, not only the principal one**
([0042](decisions/0042-the-mapper-walks-every-corpus-a-map-cites.md),
[#305](https://github.com/brandonifco/rules-factory/issues/305)). A map may cite several
([0039](decisions/0039-the-manifest-pins-every-corpus-a-map-cites.md)) and declares **one** extent
across them all. Each walk gets its own adapter, its own share of that extent — the sections its
corpus contains, with their table slices — its own protocol
([0040](decisions/0040-a-protocol-is-about-one-corpus-and-a-map-has-one-per-corpus-it-cites.md)),
and only the entries that cite it. The report is per corpus and in total, and the run's verdict is
the **worst** of them: a corpus nobody measured is not measured by another corpus being clean.

Measured on trial 10's two corpora before this: an extent naming both sections was refused
outright, and an extent naming only § 172.101 while entries cited § 172.102 **ran**, enumerated
104 units, reported coverage over them, and never enumerated § 172.102's **612**. Formally green,
and a completeness claim over 15% of the map. A section the extent names that *no* cited corpus
contains is still refused — the invariant asked of the union, so splitting the extent cannot lose
it.

| Verdict | What it means |
|---|---|
| **reached** | a quote the map makes of the corpus sits in the unit — an entry's `evidence`, or an example quoted in an entry's `ambiguity.bounds`, which is 0031's second fate for a worked example and which `check-locators.py` holds to the corpus the same way ([#393](https://github.com/brandonifco/rules-factory/issues/393)). Found in the unit's own text, never a citation naming it, and a bound never stands in for an entry's own missing quote |
| **rejected** | the mapper examined it, it produced no entry, and the reason is recorded. Its identity is (`sourceId`, `unit`), because a unit key has meaning inside the corpus whose adapter enumerated it. [method.md](method.md) says to drop advice and *note in the entry that you dropped it*; a passage that produced no entry at all has no entry to note it in, and that note lives in `mapping-inventory.json` |
| **unaccounted** | neither. Nobody can tell from the map whether it was read and dismissed or never opened, which is the state a map exists to distinguish from a recorded verdict |

Unaccounted units are **NOT VERIFIED** (exit 3), never a failure: whether a passage owed an entry
is decided by reading the corpus, and this tool does not read it. What *is* a failure is an
enumeration of no units, or a run in which no entry's quote is found at all — an inventory of
nothing has nothing unaccounted.

The nine committed maps whose extent one corpus holds report 408 unaccounted units of 1,351,
against 227 recorded rejections
([#267](https://github.com/brandonifco/rules-factory/issues/267) holds the numbers and what each
one is on reading it). None of the maps was edited to improve them: a map's bytes cannot change
without invalidating its review
([0017](decisions/0017-a-map-change-carries-a-review-of-its-bytes.md)), and the walks these
numbers measure happened months ago. The number was 540 until
[#392](https://github.com/brandonifco/rules-factory/issues/392): a quote that crosses a page turn
carries the corpus's own `{N}` marker, because `check-locators.py` searches the pinned bytes with
the markers in place, and the units it is searched against have them taken out — so six of the
backgammon map's entries quoted nothing this tool could find, and 23 units that are quoted were
counted as read by nobody. The adapter now takes the markers out of the quote as well, and no
committed entry is reported unlocated. Two more units moved with
[#393](https://github.com/brandonifco/rules-factory/issues/393): § 1.121-1(c)(4) Examples 4 and 5
are the corpus's only authority on *short temporary absences*, the tax map quotes both in
`ambiguity.bounds`, and a measurement that read only `evidence` counted the strongest quote the
map makes as having read nothing. Twenty-eight moved with
[#437](https://github.com/brandonifco/rules-factory/issues/437), which is #392 again in the
grammar #392 did not reach: the pdftotext adapter marks a page turn with `{N}` on a line of its
own and anchored its pattern to that line, and a map's `evidence` has its whitespace collapsed,
so the marker in a quote sat at no line boundary and was never taken out. Trial 12's map has
three quotes that straddle a turn; the units they reach include the whole twelve-row Actions
table. Four of that map's rejections named units one of those quotes reaches, which is a
contradiction a reader who could not see the quote had no way to record, and they are gone from
its `mapping-inventory.json` — the only edit any of these numbers has had, and it removes a
claim rather than improving a count.

### `mapping-inventory.json`

Beside the map, like the protocol, and optional — a map that rejected nothing has no file. It is
not packed into the map package either ([0015](decisions/0015-a-map-is-published-as-a-versioned-package.md)):
it is a record of how the map was made, which is the mapper's business and not a consumer's.

```json
{
  "inventoryVersion": 2,
  "rejected": [
    { "sourceId": "hoyle-1909", "unit": "p. 277 block 2",
      "ground": "heading", "note": "the chapter's own heading line" },
    { "sourceId": "hoyle-1909", "unit": "p. 277 block 3", "ground": "advice",
      "note": "counsel on which point to make first; it obliges nothing" }
  ]
}
```

`sourceId` is required on every version 2 rejection and must be a corpus the map cites. Rejections
are partitioned by it before any walk is accounted: a rejection of corpus A cannot satisfy corpus
B, even when their adapters emit the same unit key. A duplicate (`sourceId`, `unit`) is refused.
This is the unit identity 0039 and 0042 already require, not a claim that every cited corpus had a
rejection; the file still contains only explicit examined-and-rejected verdicts.

`ground` is closed (`advice`, `preamble`, `heading`, `page-furniture`, `restatement`,
`out-of-extent`, `beyond-adapter`), and a `note` is required: a ground alone is a label, not a
reading. A rejection naming a unit that corpus's extent does not enumerate is a claim about
nothing, and one naming a unit an entry quotes is a contradiction; both fail the run.

Version 1 bound the whole document to one top-level `corpus`. It remains readable, without
reinterpretation, for a single-corpus map. A map citing several corpora is refused until its file
is migrated to version 2 by moving that `corpus` value onto every rejection as `sourceId`; no
version 1 inventory can truthfully account for a multi-corpus walk. No committed inventory file
uses version 1.

All nine carry one. Six were written by re-reading each unaccounted unit against the map that
left it ([#267](https://github.com/brandonifco/rules-factory/issues/267)); trials 11 and 12 and
the map of pp. 16-18 wrote theirs with the walk, which is what it is for:

| map | rejections | still unaccounted | what the rejections are |
|---|---:|---:|---|
| `faa-part-107` | 12 | 0 | the twelve section headings |
| `faa-part-107-temporal` | 12 | 1 | the twelve section headings; § 107.51's lead-in is a rule the map owes an entry ([#396](https://github.com/brandonifco/rules-factory/issues/396)) |
| `hoyle-backgammon` | 9 | 0 | four section titles, both `[Illustration]` placeholders the adapter cannot read, the printer's rule, and two paragraphs of counsel on which throw to prefer |
| `srd-52-combat` | 32 | 0 | 25 heading lines the extraction gives as blocks of their own, four folios and running heads, the chapter opener, the underwater lead-in, and the `Ranged Attacks` lead-in |
| `srd-52-conditions` | 28 | 407 | the folios and running heads only |
| `frcp-6-12-81` | 15 | 0 | the three rules' own titles, the nine subdivision captions that open paragraphs carrying the whole of what they name, and three amendment histories |
| `srd-52-damage-and-healing` | 32 | 0 | 24 section headings, six folios and running heads, the chapter's lead-in and the Saving Throws and Damage lead-in |
| `srd-52-playing-the-game` | 73 | 0 | 54 section headings and table header cells the extraction gives as blocks of their own, 15 folios and running heads, two halves of the Rhythm of Play advice, and two lead-ins that point at a table. A 74th rejected the Round Down sidebar under `restatement`, which its own note said was not the true reason; the true reason was that no citation could name the earlier of two identical printings, and with [0066](decisions/0066-the-cited-page-chooses-among-the-printings-the-heading-path-selects.md) one can, so the passage is an entry |
| `tax-121-principal-residence` | 14 | 0 | the section heading and the thirteen worked examples the map's own `scope: out` entries declined, one per example |

A rejection is a reading and not a tidy-up, which is why two of the piles do not close. The 2020
part 107 map's one unit states who § 107.51's limitations bind, and the 2026 map maps the same
sentence; calling it *examined and produced no entry* would be false. And `srd-52-conditions`
declares an extent of fifteen whole glossary pages in order to map sixteen entries scattered
through them, so 407 of its units are other terms' rules that this walk never claimed to read.
No `ground` in the closed set says that, and inventing one would turn a known limit of `extent`
into a record of work nobody did.

### The adapter interface

The corpus grammars already had a locator checker each, and each answers *where is the
passage this citation names*. None could answer *what is in the extent that no citation named*.
[`tools/mapper/corpus.py`](../tools/mapper/corpus.py) is the other half: an `Adapter` cuts a
corpus into the units an extent selects, in reading order, each with a stable key and its text.

| Manifest `adapter` | Extent it reads | What a unit is |
|---|---|---|
| `plain-text` | `page` | a blank-line-separated block, keyed `p. 271 block 3` |
| `pdftotext-page-marked` | `page`, with `startsAfter` and `endsBefore` (0024, 0064) | the same, with the marker on a line of its own |
| `ecfr-xml` | `section-designation`, with `tables` (0035) | a paragraph, a worked example, a section's heading, or a **row** of a table the extent slices, keyed `§ 107.29 ¶4 (a)` or `§ 172.101 table 3, row [column 2 = "Acetal"]` |
| `uslm-xml` | `section-designation`, spelled `Rule 6` | the text an identified element prints **itself**, keyed by the citation that names it: `Rule 6(a)(1)(A)`. The rule element prints twice — its heading, then its source credit — so it yields two units, `Rule 6 heading` and `Rule 6 source credit` |

The two cuts are implemented once, in the base both page adapters share, so `plain-text` honours
them here as well; a `plain-text` map declaring one would still fail its run, because
`tools/check-locators.py` reads whitespace-collapsed text with no lines to find the heading in and
reports the cut NOT VERIFIED. A cut is taken against the **numbered** units, so a unit's key is
its position on its own page and does not move when either end of the extent does — which is what
lets two maps of one split page record rejections that mean the same thing.

That is the whole interface, and it is small on purpose. Marking a unit *reached* could have been
done by parsing each entry's citation and comparing it against the unit's designation, which
would have put a second citation parser per grammar into the mapper. It is instead done by
finding the entry's **quoted evidence** in the units' own text: a quote is the same kind of
object in every corpus, so the measurement is one implementation, and it is the stricter reading
— a citation naming a section is not a quote sitting in it.

The ordinary evidence search keeps a **four-word minimum fragment** so a short prose phrase cannot
wander across unrelated units and manufacture reach. A `table-row` is structurally narrower:
0035 makes the row unit's key the citation that names it, and 0030 identifies repeated text by
the container its citation names. For table-row evidence of any length, the inventory therefore
searches only the `table-row` unit structurally named by the entry's citation, and still requires
the quoted words to occur in that unit's own text. Byte-identical text in another row earns no
reach merely by matching. The citation narrows the search domain; it never establishes reach by
itself. Where the locator does not mechanically identify a table-row unit, four-word-or-longer
evidence keeps the corpus-wide search, including the existing behavior that lets one quote span
unit boundaries; short prose remains below the floor. `units()` is also what [a
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
whole, a row another row matches in every nameable cell **and that no anchor reaches**. A row the
corpus leaves blank in a column an earlier row fills is addressed relative to that earlier row
rather than refused
([0043](decisions/0043-a-row-blank-in-the-column-that-names-the-row-above-is-named-below-it.md)):
`§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]`, with an ordinary
`column = value` discriminator where the run holds more than one. The anchor is an ordinary row
key, so there is still no ordinal, and the refusal now says both addresses were tried.
Two more are refused for the same reason:
a table whose body carries a cell into the row below, or whose headings do not number its body's
cells one for one, because which column a cell sits in is then not in the markup and a guessed
alignment names the wrong cell silently; and a corpus that prints one section designation twice,
because indexing it would drop the other printing's paragraphs and tables out of the corpus and
every check over them would pass by having nothing to look at. A **two-level heading is read**,
not refused — the spans are expanded into a grid — and a heading row is a unit like any other. A section's table rows
are enumerated after its paragraphs rather than in the place the table is printed: this grammar
walks a section's direct children, a table sits below them, and a reading order it cannot see is
not one it should assert.

**A paragraph the corpus prints inside a wrapper is a unit of its section**
([#285](https://github.com/brandonifco/rules-factory/issues/285),
[0036](decisions/0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md)).
Walking a `DIV8`'s direct children left out every paragraph further down, and § 172.102 states its
special provisions that way: `A3`, `B2`, `N40`, `TP1` and `148` are `FP-1` and `P` elements inside
an `<EXTRACT>` beside the paragraph that introduces the run. The set of wrappers descended into is
**closed** and lives in `NESTED_CONTAINERS` — `EXTRACT` and `NOTE` — with the reason for each
member beside it, and the descent is to **any depth**; a `DIV` holding a table is not in it,
because a table is addressed by its rows and flattening one into the paragraph index is the
reading 0035 refused. The section locator checker descends into the same wrappers with the same
table of tags, and a test holds the two equal, because a unit one half can cite and the other
cannot see is a denominator that shrinks to fit what was read.

The descent **loses nothing**: every text-bearing element it reaches is enumerated, including one
whose tag the table does not name, and a test asserts that over the committed corpora and every
fixture. A unit nothing counts is a unit no sweep can ever report.

**Nor does the top level** ([#290](https://github.com/brandonifco/rules-factory/issues/290)). That
guarantee was made of the descent first, and a section's *direct* children were older and
unchanged: one that is not a `P`, an `EXAMPLE` or a wrapper was dropped with no record. Across the
committed corpora that is 120 `HEAD`, 30 `CITA`, 12 `DIV`, 2 `EDNOTE` and 1 `HD1` — nothing
normative, as far as anyone had looked, and nothing checking that. `TOP_LEVEL_PASSED_OVER` is now
the closed set that may be stepped over, held equal across the two walks by
`tools/tests/mapper/test_mapper_top_level.py`, and anything outside it that has words in it is
enumerated with its reason here and **fails the run** in the section locator checker.

Two of its members were already settled — a section's `HEAD` is enumerated as its own unit, and a
`DIV` is a table addressed by its rows (0035). The other three are a *reading* of what the eCFR
prints rather than a check: `CITA` is the authority citation, `EDNOTE` the Federal Register's
editorial annotation, `HD1` a division title. So the checker **prints the tally by tag on every
run** — `83 top-level element(s) stepped over, by tag: CITA 22, HEAD 61` — because a reading that
is visible every run is one a corpus can contradict, and a reading buried in a constant is not.

**A wrapper whose own heading names a division of the corpus continues nothing**
([#291](https://github.com/brandonifco/rules-factory/issues/291),
[0056](decisions/0056-a-wrapper-whose-heading-names-a-division-continues-nothing.md)). 0036 asked
two structural questions — does the wrapper hold an `HD1`, and is it captioned while following
something that is not a designated paragraph — and one shape defeats both at once: an appendix
titled `HD2` and printed directly after a designated paragraph. It inherited that paragraph's
designation, which is the one shape of #290 that handed out a wrong address rather than
withholding one. Measured against every committed corpus, no further reading of the markup
separates that shape from § 172.102's six captioned provision runs, which must keep their address;
the heading's own words do. So `DIVISION_TITLE` refuses a wrapper whose heading opens with one of
the corpus's names for a division (`Appendix A to § 172.101—…`, `Subpart B—…`) or says which
division it belongs *to*, under the same `division-wrapper` reason the other two give. It is a
broad reading on purpose: refusing too widely withholds an address and says so, and inheriting too
widely hands out a wrong one.

The two walks part company on **one test**, and the bound is asserted rather than described. The
checker builds the designator tree and so leaves a wrapper **unplaced** where the markup does not
say the wrapper is inside the paragraph it follows — an appendix, a wrapper holding a `<P>` that
states its own designation, a note whose heading names the wrong paragraph. This file builds no
tree, because a unit key says where a paragraph sits in the section's reading order and asserts no
containment, so it asks **every** placement test that needs no designation and not the one that
does: `note-heading-elsewhere`, whether the paragraph a note's heading names is one the note is
printed in. A second gap was measured and closed
([#292](https://github.com/brandonifco/rules-factory/issues/292)) — reading a worked example's
head needs no designation either, and an example whose head names no example was counted
addressable here while the checker left it unplaced. A test now holds the difference, over both
fixtures and every committed corpus and restricted to what the descent reaches, to
`note-heading-elsewhere` and nothing else, so a third gap fails and names itself.

**Two grammars read exactly one printed form, and refuse the rest out loud**
([#293](https://github.com/brandonifco/rules-factory/issues/293)). `NOTE_HEAD` reads
`Note to paragraph (c)(11):` and `EXAMPLE_HEAD` reads `Example 4.`; neither is widened ahead of a
corpus that prints another form, under
[#265](https://github.com/brandonifco/rules-factory/issues/265)'s standard. What each refusal owes
instead is the words it could not read — `its head does not name an example: 'Ex. 1'` — so a
corpus numbering its examples differently shows that form on every run rather than reporting a
generic reason. What a note heading *claims* is read far more widely than what it can be parsed
as: anything opening `Note to …` states an address, and a note stating one this grammar cannot
read is unplaced rather than filed under whichever designator happened to be open where it was
printed.

Such a unit is enumerated and carries its reason (`Unit.unaddressable`). The inventory counts it,
prints it on a `no address` line, exits NOT VERIFIED while any exist, and **fails** a map whose
entry quotes one: a quote of a passage no citation can name is not coverage of it, and the locator
run would report that entry unchecked. Accounting for one means recording a rejection against it,
the one verdict that needs no address.

A fifth grammar subclasses `Adapter`, implements `units(extent)`, and registers its manifest
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

What the sweeps found on the seven maps committed when it was measured, per map and per
sweep, is
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
| `3` | **NOT VERIFIED**: the run found what it cannot judge — a pointer the map does not declare, a unit inside the extent that no quote reaches and no rejection accounts for, a sweep finding, a required sweep the registry does not implement, or a staged document naming a word that is both an entry of this corpus and ordinary English. Whether each is owed, or is a leak, is decided by reading (0026), not here. For an undeclared naming, 0058 settles the one question that was open about *who* owes it — the passage that points, whatever its scope and status — so `validate.sh` accepts only 0 on that step, and a 3 there is now a map to correct rather than a question to answer |

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
- **The inventory measures the walk, and one map's extent still outruns its answer.** Every
  unit inside every committed map's extent is enumerated and counted, 227 are recorded as
  examined and rejected, and 408 of 1,351 are unaccounted
  ([#267](https://github.com/brandonifco/rules-factory/issues/267)). Seven of the nine maps now
  account for every unit, trials 11's and 12's and the pp. 16-18 map's from their first mapping;
  the 2020 part 107 map has one left, which is a rule it owes an entry
  ([#396](https://github.com/brandonifco/rules-factory/issues/396)) and not something a
  rejection may absorb. The remaining 407 are all in `srd-52-conditions`, whose `extent` claims
  fifteen whole glossary pages in order to map sixteen scattered entries: the units are other
  glossary terms' rules, and no `ground` in the closed set says *inside the extent and outside
  what this walk was about*. That is a contract question about `extent`, not a missing record.
- **The detector reads `evidence`,** which is the corpus's words for one rule and not the whole
  passage, so a naming outside every entry's quoted span is invisible to it. And it matches a
  term exactly, so a corpus that inflects its defined terms needs a mechanism this is not.


### Section-designation pointer identity

A corpus-declared pointer regex is an interrogation, not permission to rename a citation. For a
section designation, detection must preserve the complete section identity the corpus printed.
The shared CFR grammar reads ordinary numeric sections, bare-letter suffixes such as `§ 173.2a`,
hyphenated suffixes such as `§ 1.121-1`, and their paragraph chains. A regex match containing
`§` that stops inside an alphanumeric-or-hyphen designation token is discarded rather than
reported as a shorter section. Thus `§ 173.2a` can never be reported as `§ 173.2`; malformed longer suffixes are not
accepted by prefix either. (#323)
