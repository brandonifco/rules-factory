# Trial 10 — 49 CFR § 172.101 and § 172.102

**The admission record below was written before anything was mapped, and is unchanged.** The
corpus was pinned, the slice settled, the two protocols finalized and the hypotheses written down
**before** a single entry existed, which is the point of
[#262](https://github.com/brandonifco/rules-factory/issues/262): a trial that states its
hypotheses after it has mapped its corpus has tested nothing. Nothing in that record says what any
rule *means*, so a second mapper can still be staged against it.

[`corpus-map.json`](corpus-map.json) is **step 2** of the same issue, written by a different
mapper against the settled slice, and [what the map found](#step-2--the-map-as-first-mapped) is
at the end of this file. Steps 3 and 4 — the blind second mapping and the mutation run — are
still to come, and [`review.json`](review.json) says so out loud rather than claiming a review the
trial has not run.

## Why this corpus

Every corpus mapped so far states a rule as a sentence. A citation names the container the
sentence sits in and `evidence` quotes it. 49 CFR § 172.101, the Hazardous Materials Table,
does four things no admitted corpus has done:

- **It states rules as a grid.** A rule is a row × a column; the column's meaning is in a
  paragraph 400,000 characters away, printed once for 3,687 rows.
- **It points with codes.** Column 7 holds `IB2, T4, TP1`. There is no English pointer phrase and
  no defined term — the cell holds the tokens and nothing else.
- **It encodes applicability in the shape of an identifier**, and then § 172.102(b) states in
  ordinary prose what each shape means.
- **It makes a specific provision govern a general one**, in § 172.102(a)(2), which is neither
  `dependsOn` nor a gate.

It is also the first corpus where the same substance is stated three times at three concentration
thresholds, with two identification numbers between them, which is the row family that makes a
wrong threshold look like a plausible map.

## The admission record

Phase 1's four questions, answered in [`corpus-manifest.json`](corpus-manifest.json) and not
re-answered informally anywhere else.

| | |
|---|---|
| **What is it** | `cfr-49-172.101` and `cfr-49-172.102`, two corpora, because the eCFR serves them as two documents with two hashes |
| **What exactly** | `979bfc51b90b56ce337662ff6cb39d159c460e79a61f9b716a97be3cd0ee8227` and `09f66e5b3716c520d881cf5e6e42fc050616b8ebbabcf64f7df8e587f9f4d42e`, `hashDerivation: ecfr-versioner-xml` — the bytes the versioner served, not the rendered HTML |
| **As of when** | `2026-01-01`. The **same baseline trials 3 and 9 used**, chosen so the three eCFR trials stay comparable: an entry-per-character rate measured against one date and compared against another would be measuring the amendment, not the method |
| **May it be committed** | `licence: public-domain-us-government`, `boundaryPolicy: pin-in-repo`, `verification: committed-copy`, `quotation: verbatim`. [`CORPUS-LICENCE.txt`](CORPUS-LICENCE.txt) states it in full ([0028](../../docs/decisions/0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md)) |

Retrieved with, and reproducible by:

```bash
curl -sS --compressed -H 'User-Agent: rules-factory-trial/1.0' -o section-172.101.xml \
  "https://www.ecfr.gov/api/versioner/v1/full/2026-01-01/title-49.xml?part=172&section=172.101"
curl -sS --compressed -H 'User-Agent: rules-factory-trial/1.0' -o section-172.102.xml \
  "https://www.ecfr.gov/api/versioner/v1/full/2026-01-01/title-49.xml?part=172&section=172.102"
```

### Why 2.9 MB is committed whole

`section-172.101.xml` is **2,919,857 bytes**. The largest corpus committed to this repository
until now is 80 KB. It is committed whole anyway, and the reason is not tidiness:

**Any reduction is an extraction a mapper chose.** Cutting the table to the seven rows of the
slice would make the committed bytes a selection, and a mapper-chosen extraction of a table is
exactly the failure [#261](https://github.com/brandonifco/rules-factory/issues/261) exists to
prevent — the whole spike was about what a table loses on the way out of its markup. The hash has
to cover **what the eCFR actually served**, so that anyone can re-run the two commands above and
compare digests, and so that a later reader can check the slice against the corpus rather than
against a copy of the slice. A baseline over a private extraction verifies the extraction.

It is also what makes the extent honest. [0035](../../docs/decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)
requires a map to account for **every** table in every cited section, with rows or with a reason;
that account is worth nothing if the committed corpus only holds the tables the map took.

**Related and open, not fixed here:**
[#229](https://github.com/brandonifco/rules-factory/issues/229) — package intake applies no size
limit to a corpus. A 2.9 MB corpus is the first that makes the absence visible rather than
theoretical. Fixing it is not this change's work.

## The slice, as settled on #262

### In scope

- **§ 172.101(a)** and the column paragraphs for columns 1–9: **(b) through (j)**. Measured: 69
  indexed paragraph units, 25,236 characters.
- **Seven rows** of § 172.101 table 3, the Hazardous Materials Table, each named by its column 2
  value, which for these seven resolves to exactly one row with no discriminating column needed.
- **§ 172.102(a)**, **(b)(1)–(9)**, and **only the 20 provisions those seven rows invoke**.
  Measured: 13 indexed units and 2,358 characters for (a) and (b); 2,756 characters for the
  twenty provisions.

The seven rows:

| Row (column 2, exactly as the corpus prints it) | Why it is in |
|---|---|
| `Acetal` | the ordinary case: PG II, three provisions, both aircraft limits present |
| `Acetaldehyde` | `Forbidden` on passenger aircraft and `30 L` on cargo — the two limits disagree inside one row |
| `Acetic acid, glacial or Acetic acid solution, with more than 80 percent acid, by mass` | concentration band 1: PG II, UN2789 |
| `Acetic acid solution, not less than 50 percent but not more than 80 percent acid, by mass` | band 2: PG II, **UN2790**, and provision `148` appears |
| `Acetic acid solution, with more than 10 percent and less than 50 percent acid, by mass` | band 3: PG **III**, same UN2790, different limits |
| `Acetyl acetone peroxide with more than 9 percent by mass active oxygen` | `Forbidden` as a whole row: column 3 says `Forbidden` and thirteen cells are empty |
| `Alkali metal amalgam, solid` | carries `N40` (non-bulk only) and `W31` (water only) — the modal codes H3 is about |

### Explicitly out of scope

- **The three appendix tables of § 172.101** — the reportable-quantity table (table 4, 1,356
  rows), the radionuclide table (table 5, 770 rows) and the marine-pollutant table (table 6, 555
  rows) — and the paragraphs that govern them.
- **§ 172.101(k) and (l)**: column 10 vessel stowage, and the rules for changes to the Table. 17
  indexed units, 4,228 characters. The seven admitted rows still *print* their 10A and 10B cells,
  because 0035 keeps a row's columns; § 176.63 and § 176.84, where those cells' meanings live, are
  listed in the manifest as referenced and not admitted.
- **§ 172.102's other 313 provisions**, and the tables' other rows.

### Two corrections the settled slice needed, found while verifying it

Neither is a finding against the repository; both are corrections to #262's own words, made here
because the slice has to be exact for the row keys to resolve.

1. **Band 3's column 2 value is not what the issue wrote.** #262's comment names it *"Acetic acid
   solution, more than 10 and less than 50 percent"*. The corpus prints *"Acetic acid solution,
   **with** more than 10 percent and less than 50 percent acid, by mass"*. A row key written from
   the issue's shorthand resolves to **0 rows** and is refused — which is 0035 working, and is
   also why a slice has to be settled against the corpus and not against a description of it.
2. **§ 172.102(b) has nine subparagraphs, not eight.** #261 and #262 both write "(b)(1)–(8)".
   (b)(9) is *"A code containing the letter 'W' refers to a special provision that applies only to
   transportation by water."* — the paragraph that gives `W31` its reach, and `W31` is on one of
   the seven rows. The slice is (b)(1)–(9).

## The hypotheses, before anything is mapped

Verbatim from [#262](https://github.com/brandonifco/rules-factory/issues/262). A run that
confirms all six is a failure to have picked a hard enough corpus.

> - **H1 — the evidence model survives.** An entry can be supported by one contiguous verbatim
>   span even where meaning comes from row × column. The contract's own answer to distributed
>   meaning is *that is evidence the entry is two entries*; H1 says decomposition under the
>   existing model is enough, and no `evidenceGraph` is needed.
> - **H2 — `mappingProtocol` can express a coded pointer.** `IB2`, `T4`, `TP1`, `202`, `242` are
>   pointers with no English pointer phrase anywhere. Neither `phrase` nor `defined-term-use`
>   ([0026](../../docs/decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md))
>   is the mechanism. H2 says the protocol's shape holds and only its vocabulary grows.
> - **H3 — the existing relations carry modal applicability.** A special provision beginning `A`
>   binds only air, `B` bulk, `N` non-bulk, `R` rail, `W` water — applicability encoded in the
>   shape of the identifier. H3 says `enabledBy` / `suspendedBy` / `dependsOn` express that
>   without a new field. The failure mode to look for is trial 9's: a gate recorded with none of
>   its reach, 30 missing `enabledBy` edges that no check could see.
> - **H4 — coverage can be evidenced.** Every selected cell, every governing heading and every
>   referenced special provision can be shown to have been examined. Today nothing does this
>   (#255), so H4 is a claim about what an inventory would have to hold, and this corpus is the
>   one that says what shape it needs.
> - **H5 — a blind second mapping converges.** Two independent mappers produce substantially the
>   same decomposition of a table. Trial 9's blind pass found 36 aligned partnerships and 0
>   disagreements about scope on prose; H5 says table geometry does not break that.
> - **H6 — a removed restriction is detectable.** Deleting one mode restriction or one
>   special-provision pointer is caught by something other than a person's memory.

One thing has moved under H4 since it was filed: #255 has closed and the mapping inventory exists.
[#270](https://github.com/brandonifco/rules-factory/issues/270) is the part of it this corpus is
about — a unit counted as reached the moment one quote lands in it, over a table of 3,687 rows.

### The two corrections #262's later comment makes

1. **The trial was blocked by #280, not by #261.** The table's geometry survives the eCFR markup
   cleanly; what did not survive was the indexer, which read 6.6% of § 172.101 and 5.7% of
   § 172.102 and missed the entire normative table. #280 is now closed by
   [0035](../../docs/decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md), which is
   what makes this corpus citable at all and therefore what makes admission worth doing.
2. **H3 is stated, not merely encoded, and is therefore harder.** § 172.102(b)(1)–(9) says in
   ordinary prose — in paragraphs the indexer can already see — what each code shape means, and
   § 172.102(a)(2) states the precedence rule the same way:
   > To the extent a special provision imposes limitations or additional requirements on the
   > packaging provisions set forth in column 8 of the § 172.101 table, packagings must conform to
   > the requirements of the special provision.

   So H3 is not *"can the map infer applicability from an identifier's shape"* but: **can the map
   hold a stated general rule whose trigger is the shape of a token sitting in another section's
   table cell — without the mapper quietly doing the derivation itself.**

   H1, H2, H4, H5 and H6 stand as filed.

### What would falsify each

Written now, so that the map cannot be read backwards into a confirmation.

| | Falsified if |
|---|---|
| H1 | an entry of the slice needs evidence from two non-contiguous places at once — a cell and its column heading, say — and splitting it into two entries produces two entries neither of which states a rule |
| H2 | no protocol this corpus can honestly declare passes `tools/mapper/protocol.py`. **Already partly falsified at admission** — see below |
| H3 | modal reach ends up recorded in a `note`, or recorded on the wrong side, or a mutation removing one mode restriction leaves every check green |
| H4 | the sweeps and the inventory cannot distinguish "this cell was read and decided" from "this cell was never looked at", at 3,687 rows |
| H5 | the blind mapper decomposes a row differently enough that the two maps cannot be aligned by quoted text |
| H6 | deleting `W31` from a row, or deleting a `suspendedBy`, passes `check-map.py` and the locator run |

## What was verified at admission

Everything below was run against the committed bytes with the repository's own code
(`examples/faa-part-107/check-locators-section.py`), not re-derived from #261's comment.

**Measurements reproduced from #261.** § 172.101: 449,986 characters of text, **29,549 indexed
(6.6%)** in 86 units, one paragraph refused as an ambiguous designator (*"(i) Such a change does
not apply to the shipment of any package filled prior to …"*, the amendment transition rule — out
of the slice, so it costs this trial nothing). § 172.102: 159,251 characters, **9,115 indexed
(5.7%)** in 37 units. Table 3 is 3,689 rows — 2 heading rows and **3,687 body rows** — of 14
columns, and **1,112 body rows have exactly one empty cell**.

**The columns are the corpus's own.** § 172.101 table 3 numbers as
`1 2 3 4 5 6 7 8A 8B 8C 9A 9B 10A 10B`. `column 9` is not a column of it. All six tables of
§ 172.101 and all seven of § 172.102 resolve; none is refused.

**Each of the seven rows resolves from its `column 2` key to exactly one row.** Seven keys, seven
single matches, no discriminator needed:

```
| Acetal | 3 | UN1088 | II | 3 | IB2, T4, TP1 | 150 | 202 | 242 | 5 L | 60 L | E |
| Acetaldehyde | 3 | UN1089 | I | 3 | B16, T11, TP2, TP7 | None | 201 | 243 | Forbidden | 30 L | E |
| Acetyl acetone peroxide with more than 9 percent by mass active oxygen | Forbidden | | | | | | | | | | |
```

Each rendering begins with a bare `|` because column 1, the symbol column, is empty on all seven —
an absence that is quotable because 0035 keeps the columns.

**`column 9A` and `9B` on the Acetal row are `5 L` and `60 L`**, checked end to end through
`check_table_row`, which returns `ok` for each:

```
§ 172.101 table 3, row [column 2 = "Acetal"], column 9A   evidence "5 L"        ok
§ 172.101 table 3, row [column 2 = "Acetal"], column 9B   evidence "60 L"       ok
§ 172.101 table 3, row [column 2 = "Acetaldehyde"], column 9A  evidence "Forbidden"  ok
```

**The seven rows invoke exactly the 20 codes #262 settled on** — `148, A3, A7, A10, B2, B16, IB2,
IB3, IB4, IP1, N40, T4, T7, T9, T11, TP1, TP2, TP7, TP33, W31` — six of which carry a modal
letter.

**The seven rows measure 1,012 characters joined, 992 as 0035 renders them.** #262's figure is
the raw `' | '` join; 0035 normalises the rendering, which strips the leading and trailing spaces
a row carries, and a quote is held to the normalised form. Both numbers are reproduced here
because the difference is exactly the adjustment 0035 recorded, and a trial that quotes 1,012 at
the checker would fail.

**Size of the slice, against the calibration.** In-scope text is ~31,300 characters: 25,236
(§ 172.101(a)–(j)) + 2,358 (§ 172.102(a)–(b)) + 2,756 (the twenty provisions) + 992 (the seven
rows). At `examples/README.md`'s rate of roughly 24 entries per 8,000 characters that implies
**~94 entries**, which sits between trial 7's 86 and trial 8's 100 and is therefore within what
#262 asked for. It is not small.

### Whether the 20 invoked provisions can be cited — and 12 cannot

This is the finding of the admission. 0035 gave the *pointer's source* an address; the
*pointer's target* still has none for most of these.

| Code | Where § 172.102 states it | Citable today |
|---|---|---|
| `IB2` | row of table 2, `row [column 1 = "IB2"]` | yes |
| `IB3` | row of table 2 **and** row of table 4 — two different rules, IBCs and Large Packagings | yes, both |
| `IB4` | row of table 2 | yes |
| `IP1` | row of table 3 | yes |
| `T4` `T7` `T9` `T11` | rows of table 6 | yes |
| `148` `A3` `A7` `A10` `B2` `B16` `N40` `W31` | `DIV8/EXTRACT/FP-1` | **no** |
| `TP1` `TP2` `TP7` `TP33` | `DIV8/EXTRACT/P` | **no** |

Each of the eight table-stated codes resolves to exactly one row of its table, checked with
`Table.matching`. The twelve others sit inside an `<EXTRACT>`, and the section indexer walks the
**direct** `P` and `EXAMPLE` children of a `DIV8` and nothing deeper, so none of them is in the
index at all — they are ordinary paragraphs of the regulation sitting inside a wrapper nothing
descends into. That is not the defect 0035 answered.

Filed as [#285](https://github.com/brandonifco/rules-factory/issues/285). Not fixed here:
admission does not change tooling, and what unit an `EXTRACT` child should enumerate as is a
question the map should force rather than one answered in advance
([#265](https://github.com/brandonifco/rules-factory/issues/265)).

One more thing about those twelve: `TP1` and `TP2` state their rule as a `MATH` element, the
degree-of-filling formula, with the prose saying only *"determined by the following:"*. Even once
reachable, they are `beyondAdapter` — but `beyondAdapter` goes on an entry, and an entry needs a
citation.

## The protocol question — recorded, not solved

`mapping-protocol.json` is **not in this directory**, on purpose. Drafting one for this corpus
runs into the closed vocabularies of `tools/mapper/protocol.py`, and what they refuse was measured
rather than argued. The draft:

```json
{
  "protocolVersion": 1,
  "corpus": "cfr-49-172.101-172.102",
  "units": ["paragraph", "table", "table-row", "list-item"],
  "pointerMechanisms": [
    { "mechanism": "section-designation" },
    { "mechanism": "phrase" },
    { "mechanism": "coded-pointer", "vocabularyFrom": "special-provision-codes" }
  ],
  "requiredSweeps": ["tables", "cross-references", "applicability", "exceptions",
                     "prohibitions", "definitions", "extent-coverage"],
  "adapterReach": { "text": "readable", "tables": "readable", "columns": "readable",
                    "formatting": "unsupported", "illustrations": "unsupported",
                    "equations": "unsupported" }
}
```

Run through `protocol.check()`, unmodified, it returns two refusals, verbatim:

```
pointerMechanisms[2]: mechanism 'coded-pointer' is outside the closed set: defined-term-use, phrase, section-designation
modality 'equations' is outside the closed set: text, tables, columns, formatting, illustrations
```

Three things it does **not** refuse matter as much:

- **`units` needs nothing.** `table-row` is already a unit (0035), and `list-item` is in
  `protocol.UNITS`. But `mapper/corpus.py`'s `KINDS` is
  `("section", "paragraph", "heading", "worked-example", "table", "table-row")` — `list-item` is
  not in it, so a protocol may declare a unit the adapter can never enumerate. That is the unit
  the twelve `EXTRACT` provisions would need.
- **`defined-term-use` would be accepted and would fire.** `pointers._names` matches a term on
  word boundaries exactly as printed, so a vocabulary entry mapping `"IB2"` to an entry makes the
  detector work mechanically. Whether that is the mechanism or the mechanism bent is H2's real
  question — and note that `\b148\b` matches inside `§ 173.148`, so a numeric provision would be
  "detected" in every section designation ending in its digits.
- **A protocol names one corpus and this trial admits two.** `protocol["corpus"]` is a single
  `sourceId` checked against the manifest. Every column 7 pointer crosses from `cfr-49-172.101` to
  `cfr-49-172.102`.

**No vocabulary was extended and no decision record was written.** That is H2, and the standard
this project is adopting ([#265](https://github.com/brandonifco/rules-factory/issues/265)) is that
a concept is added only after a corpus has actually forced it under mapping — established by
trying decomposition under the existing model, blind-mapping it and mutating it — not in
anticipation. Filed as [#284](https://github.com/brandonifco/rules-factory/issues/284), linked to
#262 as H2's evidence.

**A map of this corpus cannot pass `scripts/validate.sh` step 3 until #284 is settled.** The step
fails a map whose protocol is refused, and a protocol declaring `phrase` for a pointer that is not
a phrase would pass the checker while stating something false — the
[#208](https://github.com/brandonifco/rules-factory/issues/208) failure repeated with the
mechanism known in advance.

## H2, as it stands after #307, #311 and #314

Recorded here because the admission record above says *"no vocabulary was extended and no decision
record was written"*, and three have been since. H2 is **qualified, not confirmed**, and the
wording it was filed in — *"the protocol's shape holds and only its vocabulary grows"* — is half
right:

```
coded-pointer concept:          forced        (0041, measured on this corpus, #307)
protocol mechanism-list shape:  held          (a mechanism object with its own parameters)
pointerMechanisms vocabulary:   +1            (coded-pointer)
single vocabularyFrom entry:    falsified     (#314: this corpus prints no such passage)
map contract:                   needs one evidence-anchored definition declaration (`defines`, 0045)
equations proposal:             rejected by evidence (0041: an image-served formula is
                                              `illustrations: unsupported` and `beyondAdapter`)
```

The falsified line is the one worth keeping in view. 0041 assumed `coded-pointer` could reuse
`defined-term-use`'s vocabulary — one entry whose `crossReferences` list the corpus's terms — and
that assumption held for the SRD by an accident of that corpus: its glossary list prints all
fifteen condition names in one sentence. § 172.102 prints no equivalent, so the entry could only
be written by inventing the list, and `check-map.py --only cross-references` refuses it. The
alternative was to exempt that entry from the anchoring rule, which would have kept H2's wording
clean at the cost of letting a map assert references its evidence does not make. It was rejected
([0045](../../docs/decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md)).

**A qualified H2 is a better trial result than a clean one bought that way**, and this is what the
trial was for: the corpus attacked a part of the contract the previous nine did not reach.
[0044](../../docs/decisions/0044-one-printed-code-can-name-more-than-one-rule.md) is unchanged and
[0026](../../docs/decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)
is untouched. H1 and H3–H6 remain open; nothing here is evidence about them.

## The two protocols, finalized before the map

[`mapping-protocol-cfr-49-172.101.json`](mapping-protocol-cfr-49-172.101.json) and
[`mapping-protocol-cfr-49-172.102.json`](mapping-protocol-cfr-49-172.102.json), one per corpus
([0040](../../docs/decisions/0040-a-protocol-is-about-one-corpus-and-a-map-has-one-per-corpus-it-cites.md)).
They are written **before** the map for the reason the hypotheses were: a protocol written after a
map describes the walk that happened rather than the walk that was owed, and nothing would catch
the difference.

Four choices are not obvious, and each was settled against the committed bytes rather than argued:

1. **`formatting: "rendered-page-required"`, on both.** § 172.101(c)(10) makes italics
   load-bearing — italicised words in column 2 are **not part of the proper shipping name** — and
   two of the seven rows carry them: *"Acetic acid, glacial `or` Acetic acid solution, `with more
   than 80 percent acid, by mass`"*, and the whole of *"Acetyl acetone peroxide with more than 9
   percent by mass active oxygen"*. The corpus marks them `<E T="03">`, and the `ecfr-xml`
   adapter's cell text is `"".join(cell.itertext())`, which flattens the tag. So the extraction
   does not carry the distinction, the rendered page does, and an entry that turns on which words
   are italic owes a rendered reading ([0004](../../docs/decisions/0004-adapter-reach-is-a-property-of-the-entry.md)).
2. **Column 6 gets its own `coded-pointer` and its own vocabulary.** § 172.101(g) ends *"The codes
   contained in Column 6 are defined according to the following table:"* — the corpus itself says
   those codes are defined by table 1, the Label Substitution Table. That is exactly the shape
   [0045](../../docs/decisions/0045-a-vocabulary-is-distributed-over-the-entries-that-define-its-terms.md)
   is for, and `hazard-label-codes` is a different vocabulary from `special-provision-codes`
   because a token of one does not answer the other: column 6's `3` is a hazard label, and column
   7 holds numeric special provisions such as `148`.
3. **§ 172.102 declares no `coded-pointer`.** Its tables' column 1 holds the codes, but there they
   are **defined**, not pointed with. It points the ordinary two ways — `phrase`, over the
   manifest's declared phrases, and `section-designation`, which its provisions use heavily
   (`§ 178.274(d)(2)`).
4. **Neither declares `defined-term-use`.** Both corpora use terms § 171.8 defines, and § 171.8 is
   listed in the manifest as referenced and **not admitted**, so no entry of this map can be its
   vocabulary; a pointer into it is `definedElsewhere`'s
   ([0026](../../docs/decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)).

Run against a map that declares both vocabularies, `protocol.check` returns nothing for either.
Run against an empty map, § 172.101's is refused twice, and those two refusals are the obligation
the protocol places on the mapper:

```
pointerMechanisms[2]: no entry in this map declares `defines` for vocabulary 'hazard-label-codes'
pointerMechanisms[3]: no entry in this map declares `defines` for vocabulary 'special-provision-codes'
```

`requiredSweeps` names ten of the eleven challenges for each corpus; `examples` is the one neither
requires, because neither states a worked example. Whether any of the ten is silent on this corpus
— fires on nothing anywhere, which is the outcome that needs a `sweepCuesReason` — cannot be known
before a map exists, and is measured when Mapper A's sweeps run.

## Step 2 — the map, as first mapped

[`corpus-map.json`](corpus-map.json): **135 entries**, 129 of them `scope: in`, 7 carrying an
unresolved question, 1 `kind: assertion`, 2 `beyondAdapter` for a formula the extraction does not
carry and 2 for italics it flattens. Every quote was cut out of the committed XML through this
repository's own readers; none was typed by hand.

| where | entries |
|---|---:|
| § 172.101(a)–(j), the paragraphs that give the columns their meaning | 51 |
| § 172.101(k) and (l), read and declined | 2 |
| § 172.101 table 1, the three label codes the mapped rows invoke | 3 |
| § 172.101 table 3, the seven settled rows | 39 |
| § 172.102(a) and (b)(1)–(9) | 13 |
| § 172.102(c) and three table leads, and the twelve provisions stated as prose | 16 |
| § 172.102 tables 2, 3, 4 and 6, the eight table-stated codes | 11 |

The seven rows decompose into **six entries each** — the proper shipping name (column 2), the
classification (columns 3–5 as one contiguous span), the label codes (column 6), the special
provisions (column 7), the packaging authorisations (8A–8C) and the aircraft quantity limits
(9A–9B) — except the Forbidden row, which produces **two**, because column 3 says `Forbidden` and
the eleven cells after it are empty. That asymmetry is the corpus's and not the mapper's. The
thirty-ninth entry is `alkali-metal-amalgam-vessel-stowage-codes`, a column 10B cell the slice
puts out of scope and which is mapped anyway because it prints `148`.

### H1 — held, and the IB2 decomposition is where it strained

**H1 as filed:** an entry can be supported by one contiguous verbatim span even where meaning
comes from row × column. **Falsified if** an entry of the slice needs evidence from two
non-contiguous places at once and splitting it into two entries produces two entries neither of
which states a rule.

**Verdict: held, and it is the *citation* that holds it, not the quote.** The Acetal row's column
7 cell prints `IB2, T4, TP1` and nothing else. Those four tokens state no rule by themselves; what
makes them one is `§ 172.101 table 3, row [column 2 = "Acetal"], column 7`, which names the row
and the column that a reader would otherwise have to get from a heading 400,000 characters away.
0035 moved the row × column into the locator, and H1 survives **because of that** — on a corpus
where a cell had no address, the same entry would need the cell and its heading at once and would
falsify H1 immediately. So the honest statement is narrower than H1's wording: the evidence model
survives a grid **once the grid is addressable**.

Attempted explicitly, as the brief asked. The IB2 chain is:

```
acetal-special-provisions   § 172.101 table 3, row [column 2 = "Acetal"], column 7   "IB2, T4, TP1"
  -> ib2-authorized-ibcs    § 172.102 table 2, row [column 1 = "IB2"]
                            "IB2 | Authorized IBCs: Metal (31A, 31B and 31N); Rigid plastics ..."
  -> ib2-vapour-pressure-limit
                            § 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]
                            "| Additional Requirement: Only liquids with a vapor pressure ..."
```

Three entries, three contiguous spans, three citations that each resolve to exactly one passage.
Two things strained, and both are worth more than the confirmation:

1. **`ib2-vapour-pressure-limit` barely states a rule on its own.** Read apart from the row above
   it, *"Additional Requirement: Only liquids with a vapor pressure less than or equal to 110 kPa
   … are authorized"* does not say what it is additional **to**, and its text is byte-identical to
   the row printed under `IB1`. That the entry is nonetheless not H1's falsification is a close
   call: the split produces one entry that plainly states a rule (`ib2-authorized-ibcs`) and one
   that states half of one, where the falsification condition asks for two that state **neither**.
   The map records the gap where it belongs — as `clarity: ambiguous` on that entry, because
   § 172.102 nowhere states the convention that a row blank in the code column continues the row
   above it, and 0043 measured that the markup does not carry it either.
2. **The vocabulary cannot hold the second rule.** 0045 anchors `defines` in the defining entry's
   own evidence, and that row does not print `IB2`, so one of the code's two rules is outside
   `special-provision-codes` and 0044's *name every defining entry* invariant cannot reach it.
   `acetal-special-provisions` declares both targets anyway, and the second declaration is obliged
   by nothing: deleting it leaves `mapper pointers` clean. Filed as
   [#321](https://github.com/brandonifco/rules-factory/issues/321). `IB3` is the same shape from
   the other side — its additional-requirement row has an ordinary key only because a trailing
   *except for UN2672* clause makes its text unique.

One more thing H1 did not predict: **a contiguous span can cover several cells**, because 0035
renders a row as its cells joined by ` | `. `3 | UN1088 | II` is one span of the Acetal row and it
states one rule — the classification — where three cell entries would have stated three tokens.
Six of the map's entries are such multi-cell spans (classification, packaging, quantity limits),
and the rule they state is the corpus's, not the mapper's: § 172.101(i) explains 8A, 8B and 8C
together and § 172.101(j) explains 9A and 9B together.

### What the runs say

| run | verdict |
|---|---|
| `check-map.py` | 18 ok, 0 failed, 8 not verified |
| `check-locators-section.py` | all 135 citations resolve; coverage ok; 15 passages of § 172.101 have no address, every one declared in `extent.unreachable` |
| `mapper protocol` | both protocols act on; `hazard-label-codes` and `special-provision-codes` both declared by entries |
| `mapper pointers` | **runs nothing** — see [#318](https://github.com/brandonifco/rules-factory/issues/318) |
| `mapper inventory` | 747 units, 615 unaccounted, 14 unaddressable, 123 of 135 entries located (exit 3) |
| `mapper sweeps` | all 10 sweeps fire on both corpora; 87 findings on § 172.101, 1,203 on § 172.102 (exit 3) |

**No sweep is silent on either corpus**, so neither protocol owes a `sweepCuesReason` — the
question the admission record left open, answered. The smallest yield is `vocabulary`, 1 finding
on § 172.101 and 2 on § 172.102, and both corpora also have accounted units the same cues fire on.

**The coded-pointer interrogation is clean when it is run by hand**: 7 codes in 6 cells against
`hazard-label-codes`, 33 codes in 6 cells against `special-provision-codes`, 0 undeclared —
matching the 33 column 7 occurrences #307 measured over the same seven rows. It is not run by
`mapper pointers`, and that is [#318](https://github.com/brandonifco/rules-factory/issues/318):
the command returns early unless the protocol declares `defined-term-use`, so a protocol whose
only detected-here mechanism is `coded-pointer` prints *"nothing here detects the ways it does
point"* beside *"coded-pointer: detected here"* and exits 0 having examined nothing.

**The map carries no `mapping-inventory.json`, and cannot.** `mapping-inventory.json` names one
`corpus` and `mapper inventory` walks every corpus a map cites (0042), so the file is refused with
exit 2 for whichever corpus it does not name — watched failing, and filed as
[#319](https://github.com/brandonifco/rules-factory/issues/319). About forty of the 615
unaccounted units were read and declined by this mapping — § 172.101's two appendices, the ten
stowage categories of (k), the four paragraphs of (l), seven headings, six `(c)(n)` code-run leads
of § 172.102 that restate § 172.102(b), and the nine rows of § 172.102 table 2 the extent had to
take whole under 0043 — and not one of them can be recorded as such. **That is H4's sharpest
result:** for a map citing two corpora, the inventory cannot tell *read and dismissed* from
*never opened* at all.

### H2 and H3, as the map bears on them

**H2** is qualified as the section above already records, and the map adds one thing: the
`coded-pointer`'s column restriction is load-bearing and demonstrable inside the slice.
`alkali-metal-amalgam-vessel-stowage-codes` quotes `13, 52, 148` from **column 10B**, where `148`
is a vessel stowage provision of § 176.84 and not special provision 148 — which two of the mapped
rows do carry, in column 7. The detector reads column 6 and column 7 and never sees it. That is
0041's claim, and it is the measurement #307 made when a lexical detector read the same numeral as
a pointer twice.

**H3** is recorded and not yet tested. Modal reach is in `enabledBy` on every provision entry —
`code-a-aircraft-only` reaches three, `code-b-bulk-only` two, `code-ib-ip-ibcs-only` five,
`code-n-non-bulk-only` one, `code-t-portable-tanks-only` four, `code-tp-portable-tank-provisions`
four, `code-w-water-only` one, `code-numeric-multimodal` one — 23 gated entries in all, and
`code-r-rail-only` reaches none because no mapped row carries an R code. Nothing in a column 7
cell says any of this; § 172.102(b)(1)–(9) states it in prose and the map points at the paragraph
rather than deriving it from the letter. Whether a mutation deleting one of those edges is caught
is step 4, and trial 9's answer for `drop-enabled-by` was **missed**.

### The seven unresolved questions

`what-an-ib-code-reaches` is a **conflict** with three members — `code-ib-ip-ibcs-only`,
`ib-and-ip-code-authorizations` and `ib3-authorized-large-packagings`. § 172.102(b)(4) says an IB
code applies **only** to transportation in IBCs; § 172.102(c)(4) authorises Large Packagings
through IB codes, and § 172.102 table 4 states that rule for `IB3`. A Large Packaging is not an
IBC, and the same paragraph names the two apart. The map chooses neither reading.

The other four: `ib2-vapour-pressure-limit` and `ib3-vapour-pressure-limit` (which code does a
blank-coded row qualify — a gap, not a contradiction, so no conflict slug);
`mixture-of-same-class-materials` (§ 172.101(c)(10)(iii)'s *"the name that most appropriately
describes the material"* fixes no test, names no decider, and states nothing the choice is
measured against — gate 3 returns a gap); and `sp-tp33-molten-solids`, where a tank with *"more
stringent requirements"* is named over four dimensions with no rule ordering them, and the Alkali
metal amalgam row carries TP33 and T9 together so the question is reachable inside the slice.

Five per cent of in-scope entries carry a question, against trial 7's 27% and trial 9's 25%. That
is not a claim that this corpus is clearer: 39 of the 135 entries are cells of a table that states
a value and nothing else, and a value has little to be unclear about. The prose paragraphs alone
are 4 of 64.

### What else is recorded and not fixed

- [#318](https://github.com/brandonifco/rules-factory/issues/318) — `mapper pointers` never runs
  the coded-pointer detector.
- [#319](https://github.com/brandonifco/rules-factory/issues/319) — `mapping-inventory.json` is
  single-corpus, so a two-corpus map can record no rejection at all.
- [#320](https://github.com/brandonifco/rules-factory/issues/320) — `mapper inventory` drops a
  quote under four words, so 12 of the map's 135 entries — every single-cell entry — are *not
  located inside the extent* although the locator checker verifies each exactly.
- [#321](https://github.com/brandonifco/rules-factory/issues/321) — a code's second rule, stated
  in a row that leaves the code column blank, cannot join its vocabulary.
- [#322](https://github.com/brandonifco/rules-factory/issues/322) — `mapper inventory` marks the
  byte-identical row under `IB1` reached because the entry for the row under `IB2` quotes the same
  words.
- [#323](https://github.com/brandonifco/rules-factory/issues/323) — the manifest's `references`
  are short of six sections the mapped spans point at, and `§ 173.2a` matches the declared
  designation pattern as `§ 173.2`.

Nothing under `tools/` was changed to make this map pass, and neither protocol was edited: both
were run against the map as committed and neither needed a word altered.

## What happens next

Steps 3 and 4 of #262: blind-map the slice a second time, adjudicate, mutate, and report every
hypothesis as held or falsified with what it cost to find out. #262 is not closed by this
directory; the map is the second of its four steps.
