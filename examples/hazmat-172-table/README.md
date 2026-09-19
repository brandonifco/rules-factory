# Trial 10 — 49 CFR § 172.101 and § 172.102, admitted

**Nothing here is mapped.** This directory is phase 1 of [the method](../../docs/method.md) and
nothing else: the corpus is pinned, the slice is settled, the hypotheses are written down, and
what the corpus is expected to attack is stated **before** a single entry exists. There is no
`corpus-map.json`, no `mapping-protocol.json`, and no reading of what any rule means. That is
deliberate and it is the point of [#262](https://github.com/brandonifco/rules-factory/issues/262):
a trial that states its hypotheses after it has mapped its corpus has tested nothing. A different
mapper writes the map next, and anything written here about what a rule *means* would contaminate
it.

The map steps of `scripts/validate.sh` iterate `examples/*/corpus-map*.json`. This directory has
none, so it is invisible to every one of them — confirmed by running the script, not assumed.

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

## What happens next

Steps 2 to 4 of #262: map the slice by the method, blind-map it a second time, adjudicate, mutate,
and report every hypothesis as held or falsified with what it cost to find out. #262 is not closed
by this directory; admission is one of its four steps.
