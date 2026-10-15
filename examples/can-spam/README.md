# CAN-SPAM: the regulation and the statute it implements

This directory holds the texts of the CAN-SPAM Act's regulation and statute, as corpora the
factory can build and verify. [REFERENCE-CHECK.md](REFERENCE-CHECK.md) compares each with the
reference text it claims to be.

## The regulation: 16 CFR Part 316

| File | What it is |
|---|---|
| `part316.xml` | the eCFR versioner XML for Title 16, Part 316, point-in-time 2026-10-01, byte for byte as retrieved (13,487 bytes, SHA-256 `45bf26b68a06dc81f55388a06eb4e376ceb061a490e3858fb6105143d1d583b0`); a work of the United States Government |
| `part316.corpus.build.json` | the build definition ([0074](../../docs/decisions/0074-a-corpus-is-built-and-verified-by-rules-corpus-from-the-definition-committed-beside-it.md)): one source, hash derivation `ecfr-versioner-xml`, no derivation step |
| `part316.corpus.expect.json` | `{"expectNotVerified": []}`: the verification accepts no unverified check |

rules-corpus, at the commit `tools/factory/rulescorpus.py` pins, builds and verifies it with
`verify --rebuild`; the content digest of the build is
`sha256:4d818b468353ee5b74d7f11d1e6e0516e232c84b8680ef46ad00b70e67e55ada`.

### Accounting unit: the paragraph of a section

A unit is each `<P>` child of a section (`DIV8`). The text of a footnote (`FTNT`) belongs to the
paragraph that carries its reference mark and is not a unit of its own; a section's heading is not
a unit.

| Section | Heading | Units |
|---|---|---:|
| 316.1 | Scope | 1 |
| 316.2 | Definitions | 16 |
| 316.3 | Primary purpose | 18 |
| 316.4 | Requirement to place warning labels on commercial electronic mail that contains sexually oriented material | 12 |
| 316.5 | Prohibition on charging a fee or imposing other requirements on recipients who wish to opt out | 3 |
| 316.6 | Severability | 1 |
| | **Part 316** | **51** |

Paragraph units are the `(a)`-level and deeper paragraphs the text prints as separate `<P>`
elements: 316.2 has one per defined term (a)-(p); 316.3 has (a), (a)(1)-(3) with their (i)/(ii),
(b), (c) and (c)(1)-(5) with (c)(3)(i)-(iii); 316.4 has (a), (a)(1), (a)(2) with its (i)-(vi) and
(A)/(B), and (b).

## The reference check

[REFERENCE-CHECK.md](REFERENCE-CHECK.md) compares 16 CFR 316.1-316.6 and 15 U.S.C. 7701-7713 (chapter 103,
section bodies without notes) with the texts they claim to be: the official annual edition of the regulation
and Pub. L. 108-187 sections 2-15 as enacted. It is written from a JSON document that a script regenerates
from the staged files, so no comparison is done by hand.

| File | What it is |
|---|---|
| `reference-check.py` | standard-library Python. Reads the OLRC USLM release-point zip, the public-law HTML, the eCFR file and the annual-edition file (SHA-256 of each checked), aligns the texts section by section (Act section N is the codified section whose own source credit reads "Pub. L. 108-187, § N"), and emits every difference. Its normalization and its rules are listed in its docstring and, with their ids, in the JSON |
| `reference-differences.json` | its output: one record per difference, with a stable id, the USLM identifier and the Act section and paragraph, both texts verbatim, the class, the rule that gave it, and the evidence for the rule (for a codification rule, the note or source credit of the USLM file, quoted with its location) |
| `REFERENCE-CHECK.md` | the report, written from the JSON by `reference-check.py --render`: counts per class and per rule, how the previous hand-run report's 43 and 260 map onto the classes, and every `potentially-substantive` difference in full |

A difference is `formatting` (it vanishes under a typographic rule), `codification` (a substitution the
USLM file itself documents for that location), `textual` (the form of a heading or a citation, where both
texts name the same thing and the evidence says why) or `potentially-substantive` (everything else, and every
case of doubt). A class says what kind of textual difference it is, not whether it matters.

```bash
python3 -I -B examples/can-spam/reference-check.py --uslm-zip xml_usc15@119-120.zip \
    --act-html PLAW-108publ187.htm --ecfr-xml title-16.part-316.xml \
    --annual-xml CFR-2026-title16-vol1-part316.xml --check examples/can-spam/reference-differences.json
python3 -I -B examples/can-spam/reference-check.py --render examples/can-spam/reference-differences.json \
    --check-report examples/can-spam/REFERENCE-CHECK.md
```

The staged files are not in this repository. `tools/tests/test_can_spam_reference_check.py` holds each rule to
a small statute and Act written in the test, and holds the committed report to the committed JSON.
