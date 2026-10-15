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

## The statute: 15 U.S.C. chapter 103

| File | What it is |
|---|---|
| `usc15-ch103.xml` | chapter 103 of Title 15 as the Office of Law Revision Counsel's USLM XML, release point 119-120 (current through Public Law 119-120, 10/07/2026), cut from the release's `usc15.xml` by the derivation below; 141,128 bytes, SHA-256 `be849fb57eb2c2aa914f7369ec5ec3f52091ebbee7ae0e6ef0fc270772449d89`; a work of the United States Government |
| `usc15-ch103.corpus.build.json` | the build definition ([0074](../../docs/decisions/0074-a-corpus-is-built-and-verified-by-rules-corpus-from-the-definition-committed-beside-it.md)): the release zip declared unstored, the slice an `external` derivation of it, and the `xml` adapter's segmentation of the slice |
| `usc15-ch103.corpus.expect.json` | the two checks this corpus accepts as not verified: `artifact usc-15-release-zip` and `rebuild usc-15-ch103-extraction` |

**The derivation is `olrc-uslm-chapter-slice-verbatim`** ([0082](../../docs/decisions/0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md)).
From the release zip `xml_usc15@119-120.zip` (5,028,058 bytes, SHA-256
`e053dcada37ec19ab55ec063abd415642b09a3e8ef9a37cc70ca88030d59e699`, one member `usc15.xml` of
30,777,201 bytes), the slice is, in order, LF-ended:

1. `<?xml version="1.0" encoding="UTF-8"?>`;
2. the member's root `<uscDoc ...>` start tag, verbatim;
3. the member's `<meta>...</meta>` element, verbatim;
4. `<main>`;
5. the one `<chapter>` element whose `identifier` is `/us/usc/t15/ch103`, from `<chapter` to the
   first `</chapter>`, byte for byte;
6. `</main>` and `</uscDoc>`.

```sh
python3 tools/derive-uslm-chapter.py --from xml_usc15@119-120.zip --chapter /us/usc/t15/ch103 --check examples/can-spam/usc15-ch103.xml
```

**What rules-corpus verifies, and what it cannot.** At the pinned commit rules-corpus has no step
that opens a zip or cuts an element, so the zip is declared by length and digest only and the
cut is an `external` derivation: `verify --rebuild` reports both not verified, and the expectation
names both. The `xml` adapter's segmentation of the slice is rebuilt and verified byte for byte.
What holds the slice to the release is the `--check` above, which needs the zip and so is not run
in CI.

### Accounting unit: the subsection of a section

A segment is each `<subsection>` element, and its id is the element's OLRC `id` attribute (a
rules-corpus segment id may not begin with `/`, so the USLM `identifier` cannot be one; it is in
the same start tag). A subsection holds its paragraphs, subparagraphs and clauses, which are not
units of their own. A section's heading, its `<sourceCredit>` and its `<notes>` (the OLRC's
statutory and editorial notes) sit outside every subsection and are not units.

**A section that prints no subsection is counted as one unit, the section element itself.** Those
are not rules-corpus segments: the adapter segments one element name, so this count is made here
and not by the tool. Three of the thirteen sections are of that kind.

| Section | Heading | Subsections | Units |
|---|---|---:|---:|
| 7701 | Congressional findings and policy | 2 | 2 |
| 7702 | Definitions | 0 | 1 |
| 7703 | Prohibition against predatory and abusive commercial e-mail | 3 | 3 |
| 7704 | Other protections for users of commercial electronic mail | 4 | 4 |
| 7705 | Businesses knowingly promoted by electronic mail with false or misleading transmission information | 4 | 4 |
| 7706 | Enforcement generally | 7 | 7 |
| 7707 | Effect on other laws | 3 | 3 |
| 7708 | Do-Not-E-Mail registry | 2 | 2 |
| 7709 | Study of effects of commercial electronic mail | 2 | 2 |
| 7710 | Improving enforcement by providing rewards for information about violations; labeling | 0 | 1 |
| 7711 | Regulations | 2 | 2 |
| 7712 | Application to wireless | 4 | 4 |
| 7713 | Separability | 0 | 1 |
| | **Chapter 103** | **33** | **36** |

The count is coarse where a section is not divided: section 7702 prints seventeen numbered
paragraphs of definitions and counts as one unit, section 7710 two paragraphs and section 7713 one
undivided text.

### Citing it

A passage is cited by its USLM identifier, `/us/usc/t15/s7704/a/1` (a section is
`/us/usc/t15/s7704`), which `examples/frcp-6-12-81/check-locators-uslm.py` holds a quote to
([0082](../../docs/decisions/0082-a-chapter-of-the-united-states-code-is-admitted-as-a-verbatim-slice-and-cited-by-its-uslm-identifier.md)).
Title 15 is not positive law: the file's own `is-positive-law` property is `no`, and the Code is
prima facie evidence of the law.
