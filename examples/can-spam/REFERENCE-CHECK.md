# Reference check: the regulation and the codified statute against their reference texts

This file is written by `reference-check.py --render reference-differences.json` from that JSON and
from nothing else; edit neither by hand. `reference-check.py` regenerates the JSON from the staged
files (their SHA-256 checked), and `--check` fails when the JSON is not what the files give. It compares,
by text alone and without interpreting anything, each text this example corpus is built from against
the text that is the law it claims to be. A class says what kind of textual difference a difference
is. It does not say whether the difference matters.

| Text checked | Edition | Reference text | Edition |
|---|---|---|---|
| 16 CFR 316.1-316.6, `part316.xml` (SHA-256 `45bf26b6…83b0`) | eCFR, point-in-time 2026-10-01 | the official annual edition of 16 CFR Part 316, Title 16 Vol. 1, GPO XML (SHA-256 `a6730763…7da2`) | revised as of 2026-01-01 |
| 15 U.S.C. 7701-7713, chapter 103, section bodies without notes: member `usc15.xml` of the OLRC USLM release point 119-120 (zip SHA-256 `e053dcad…e699`; member `f645b7bd…c93b`) | current through Pub. L. 119-120 | the CAN-SPAM Act as enacted, Pub. L. 108-187, 117 Stat. 2699, GPO plain-text rendition (SHA-256 `cf42d67e…ef4f`), sections 2-15 | 2003-12-16 |

The two editions of the regulation are nine months apart (2026-01-01 and 2026-10-01). A difference between
them could be an amendment as well as an error; the comparison cannot tell, and nothing below is read as either.

## Method

Both texts are first normalized, and only this way:

- **N-WHITESPACE**: Every run of whitespace, line breaks included, is one space; a line break after a hyphen is a line break and the hyphen stays.
- **N-USLM-MARKUP**: USLM elements are removed and their text kept in document order; a section's notes and source credit are not its body; an inline footnote and its reference marks are kept.
- **N-GPO-MARKUP**: The Act's [[Page 117 STAT. n]] markers and <<NOTE: ...>> insertions are removed, HTML entities decoded, and the text between <pre> and </pre> is the Act.
- **N-TOKENS**: Texts are compared as words and punctuation marks, case-sensitively; a heading is kept apart from the paragraph it heads and the marker from both.

Everything else is compared as it stands, word by word and punctuation mark by punctuation mark,
case-sensitively. A statute's Act section N is aligned to the codified section whose own source credit reads
"Pub. L. 108–187, § N", and a paragraph to the paragraph with the same chain of markers. Each difference then
gets the first class whose rules apply, in this order and no other:

| Class | Rule | What the rule says | Differences |
|---|---|---|---:|
| formatting | `F-QUOTE-DOUBLE` | The Act's typewriter double quotes `` and '' are the typographic marks “ and ”. | 64 |
| formatting | `F-QUOTE-SINGLE` | In the Act, ` opens and a ' that closes it is the typographic ‘ and ’. | 0 |
| formatting | `F-APOSTROPHE` | In the Act, a ' that closes no ` is the apostrophe ’. | 11 |
| formatting | `F-DASH-EM` | The Act's -- is the em dash —. | 42 |
| formatting | `F-DASH-EN` | A hyphen is the en dash – (a range, as in 80a–1). | 2 |
| formatting | `F-RUNIN-DELIM` | The Act sets a heading in the line of text it heads, closed by .-- (and a section heading closed by a period); the USLM file holds the heading apart, with no delimiter. | 120 |
| formatting | `F-HEADCASE` | A heading's words are the same words; the Act capitalizes them differently (capitals or title case) from the file's sentence case. | 60 |
| formatting | `F-HYPHENATION` | A word the Act breaks with a hyphen at a line end is the word without the break. | 0 |
| codification | `C-THIS-ACT` | 'this Act' is 'this chapter' where a References in Text note of the section says that this chapter was in the original 'this Act' for that location. | 40 |
| codification | `C-SECTION-NUMBER` | A reference to Act section N is a reference to the codified section whose own source credit reads 'Pub. L. 108-187, § N'. | 40 |
| codification | `C-SECTION-HEADING` | The Act's section designation 'SEC. N.' is the codified section's '§ M.' where M's own source credit reads 'Pub. L. 108-187, § N'. | 13 |
| codification | `C-OMITTED-SUBSECTION` | A subsection the file prints as 'Omitted' is the Act subsection that a Codification note of the section says was classified elsewhere. | 3 |
| codification | `C-ACT-SECTION-ELSEWHERE` | An Act section with no codified section in the chapter is one that a note of the chapter says amended or enacted law elsewhere in the Code. | 1 |
| codification | `C-FOOTNOTE` | A footnote (and its reference marks) set in the body of a codified section is the codifier's own annotation; the Act has none. | 2 |
| textual | `T-CITATION-FORM` | A citation of a section of another Act, given with the Act's name and its Code place, is the Code citation of the same section: the Act's parenthetical and the file's citation name the same Code section. | 6 |
| textual | `T-CITATION-QUALIFIER` | 'of this Act' qualifying a citation of a section of this Act is 'of this title' qualifying the citation of the codified section it maps to. | 2 |
| textual | `T-OF-THIS-TITLE` | 'of this title' follows the file's citation of a section of this title; the Act cites its own sections without it. | 35 |
| textual | `T-UNITED-STATES-CODE` | ', United States Code' after 'title N' in the Act is absent from the file, whose citation of title N is to the Code (a reference of the file resolves 'title N' to /us/usc/tN). | 13 |
| potentially-substantive | `P-REMAINDER` | No formatting, codification or textual rule applies to the difference. | 12 |

A substitution that is conventional but is not documented in the USLM file for that location is not
`codification`. Where a rule's condition is not met, or the rules do not settle it, the difference is
`potentially-substantive`: no difference is argued into a lighter class.

## 16 CFR 316.1-316.6

Section by section, with paragraph, footnote and heading text included, the two texts hold the same words in the
same order but for what is listed here: 316.1 (28 words), 316.2 (578 words), 316.3 (663 words), 316.4 (395 words), 316.5 (132 words), 316.6 (39 words).

Total: **1** difference: 1 potentially-substantive.

- `316.6/P1/body/1` potentially-substantive (`P-REMAINDER`): eCFR “part”, annual edition “Part”.

## 15 U.S.C. 7701-7713 against Pub. L. 108-187

| Codified § | Act § | Source credit |
|---|---|---|
| 7701 | 2 | (Pub. L. 108–187, § 2, Dec. 16, 2003, 117 Stat. 2699.) |
| 7702 | 3 | (Pub. L. 108–187, § 3, Dec. 16, 2003, 117 Stat. 2700.) |
| 7703 | 4 | (Pub. L. 108–187, § 4, Dec. 16, 2003, 117 Stat. 2703.) |
| 7704 | 5 | (Pub. L. 108–187, § 5, Dec. 16, 2003, 117 Stat. 2706.) |
| 7705 | 6 | (Pub. L. 108–187, § 6, Dec. 16, 2003, 117 Stat. 2710.) |
| 7706 | 7 | (Pub. L. 108–187, § 7, Dec. 16, 2003, 117 Stat. 2711.) |
| 7707 | 8 | (Pub. L. 108–187, § 8, Dec. 16, 2003, 117 Stat. 2716.) |
| 7708 | 9 | (Pub. L. 108–187, § 9, Dec. 16, 2003, 117 Stat. 2716.) |
| 7709 | 10 | (Pub. L. 108–187, § 10, Dec. 16, 2003, 117 Stat. 2716.) |
| 7710 | 11 | (Pub. L. 108–187, § 11, Dec. 16, 2003, 117 Stat. 2717.) |
| 7711 | 13 | (Pub. L. 108–187, § 13, Dec. 16, 2003, 117 Stat. 2717.) |
| 7712 | 14 | (Pub. L. 108–187, § 14, Dec. 16, 2003, 117 Stat. 2718.) |
| 7713 | 15 | (Pub. L. 108–187, § 15, Dec. 16, 2003, 117 Stat. 2718.) |

Act section 1 has no counterpart in the chapter: outside sections 2-15 of the Act, which are what is compared (the file holds it as a note: /us/usc/t15/s7701 notes/note[@topic=shortTitle]/p[1]).

Act section 12 has no counterpart in the chapter: no codified section of the chapter has this Act section as its source credit.

Act section 16 has no counterpart in the chapter: outside sections 2-15 of the Act, which are what is compared (the file holds it as a note: /us/usc/t15/s7701 notes/note[@topic=effectiveDate]/p[1]).


Total: **465** differences.

| Class | Count |
|---|---:|
| formatting | 299 |
| codification | 99 |
| textual | 56 |
| potentially-substantive | 11 |

| Rule | Class | Count |
|---|---|---:|
| `F-QUOTE-DOUBLE` | formatting | 64 |
| `F-APOSTROPHE` | formatting | 11 |
| `F-DASH-EM` | formatting | 42 |
| `F-DASH-EN` | formatting | 2 |
| `F-RUNIN-DELIM` | formatting | 120 |
| `F-HEADCASE` | formatting | 60 |
| `C-THIS-ACT` | codification | 40 |
| `C-SECTION-NUMBER` | codification | 40 |
| `C-SECTION-HEADING` | codification | 13 |
| `C-OMITTED-SUBSECTION` | codification | 3 |
| `C-ACT-SECTION-ELSEWHERE` | codification | 1 |
| `C-FOOTNOTE` | codification | 2 |
| `T-CITATION-FORM` | textual | 6 |
| `T-CITATION-QUALIFIER` | textual | 2 |
| `T-OF-THIS-TITLE` | textual | 35 |
| `T-UNITED-STATES-CODE` | textual | 13 |
| `P-REMAINDER` | potentially-substantive | 11 |

| Codified § | Act § | formatting | codification | textual | potentially-substantive |
|---|---|---:|---:|---:|---:|
| 7701 | 2 | 12 | 1 | 0 | 0 |
| 7702 | 3 | 75 | 8 | 4 | 1 |
| 7703 | 4 | 11 | 4 | 7 | 0 |
| 7704 | 5 | 49 | 3 | 4 | 1 |
| 7705 | 6 | 19 | 7 | 4 | 0 |
| 7706 | 7 | 73 | 50 | 29 | 4 |
| 7707 | 8 | 15 | 6 | 2 | 0 |
| 7708 | 9 | 9 | 1 | 0 | 2 |
| 7709 | 10 | 7 | 3 | 0 | 1 |
| 7710 | 11 | 8 | 5 | 0 | 2 |
| — | 12 | 0 | 1 | 0 | 0 |
| 7711 | 13 | 5 | 3 | 3 | 0 |
| 7712 | 14 | 14 | 4 | 3 | 0 |
| 7713 | 15 | 2 | 3 | 0 | 0 |

### The previous report's 43 and 260

The previous, hand-run report found 303 differences in the statute: 43 "explained by the source" and 260
"unexplained". This report finds **465**, which is +162. The count differs because the
unit of count differs, and not because a text changed:

- the previous report read the Act's typewriter quotation marks and dashes as typographic ones before it compared;
  here each is a difference of class `formatting` (106 of them: `F-QUOTE-DOUBLE`, `F-QUOTE-SINGLE`, `F-DASH-EM`);
- the section designations ("SEC. 2." against "§ 7701.") and Act section 12 were outside its comparison; here they are
  `C-SECTION-HEADING` and `C-ACT-SECTION-ELSEWHERE` (14), and the Act paragraphs that the file prints as "Omitted" are
  one record each, besides the heading (3 for the previous report's 1);
- it listed one difference where a section number changes and "of this title" is added, and where a heading's
  case and closing delimiter differ; here each rule's part is its own record, and a citation of another Act is one record
  where the previous report listed its words as several.

Its 43 "explained by the source" are the three rows below marked so; the rest of its 260 are spread over `formatting`,
`codification`, `textual` and `potentially-substantive` as the columns show.

| Previous category | Previous count | Previous status | formatting | codification | textual | potentially-substantive | Now |
|---|---:|---|---:|---:|---:|---:|---:|
| “this chapter” (code) for “this Act” (Act) | 40 | explained | 0 | 40 | 0 | 0 | 40 |
| § 7703 body “Omitted” | 1 | explained | 0 | 1 | 0 | 0 | 1 |
| § 7706(d) footnote “So in original.” | 2 | explained | 0 | 2 | 0 | 0 | 2 |
| “December 16, 2003” (code) for “the date of (the) enactment of this Act” (Act) | 7 | unexplained | 0 | 0 | 0 | 7 | 7 |
| cross-references: Act section numbers against codified section numbers, “of this title”, en dash in “80a–1” | 75 | unexplained | 2 | 40 | 37 | 3 | 82 |
| “, United States Code” after “title N” in the Act | 14 | unexplained | 0 | 0 | 13 | 1 | 14 |
| citations to other Acts, and “of this title” for “of this Act” at § 7706(f)(1) | 12 | unexplained | 0 | 0 | 6 | 0 | 6 |
| heading capitalisation and terminal punctuation | 60 | unexplained | 73 | 0 | 0 | 0 | 73 |
| apostrophe | 11 | unexplained | 11 | 0 | 0 | 0 | 11 |
| run-in heading delimiter “.—” | 81 | unexplained | 107 | 0 | 0 | 0 | 107 |
| not in the previous report | 0 | — | 106 | 16 | 0 | 0 | 122 |
| **Total** | **303** | **43 + 260** | **299** | **99** | **56** | **11** | **465** |

## Potentially-substantive differences

12 in all (11 in the statute, 1 in the regulation), each with both texts and the paragraph that holds it.

| Id | Where | Corpus text | Reference text | Corpus paragraph | Reference paragraph |
|---|---|---|---|---|---|
| `316.6/P1/body/1` | 16 CFR 316.6 P1 (eCFR, point in time 2026-10-01); 16 CFR 316.6 P1 (annual edition, revised as of 2026-01-01) | “part” | “Part” | “The provisions of this part are separate and severable from one another. If any provision is stayed or determined to be invalid, it is the Commission's intention that the remaining provisions shall continue in effect.” | “The provisions of this Part are separate and severable from one another. If any provision is stayed or determined to be invalid, it is the Commission's intention that the remaining provisions shall continue in effect.” |
| `7702(2)(C)/body/1` | /us/usc/t15/s7702/2/C; Pub. L. 108-187 § 3(2)(C) | “December 16, 2003” | “the date of the enactment of this Act” | “(C) Regulations regarding primary purpose Not later than 12 months after December 16, 2003, the Commission shall issue regulations pursuant to section 7711 of this title defining the relevant criteria to facilitate the determination of the primary purpose of an electronic mail message.” | “(C) Regulations regarding primary purpose.--Not later than 12 months after the date of the enactment of this Act, the Commission shall issue regulations pursuant to section 13 defining the relevant criteria to facilitate the determination of the primary purpose of an electronic mail message.” |
| `7704(d)(3)/body/1` | /us/usc/t15/s7704/d/3; Pub. L. 108-187 § 5(d)(3) | “December 16, 2003” | “the date of the enactment of this Act” | “(3) Prescription of marks and notices Not later than 120 days after December 16, 2003, the Commission in consultation with the Attorney General shall prescribe clearly identifiable marks or notices to be included in or associated with commercial electronic mail that contains sexually oriented material, in order to inform the recipient of that fact and to facilitate filtering of such electronic mail. The Commission shall publish in the Federal Register and provide notice to the public of the marks or notices prescribed under this paragraph.” | “(3) Prescription of marks and notices.-- Not later than 120 days after the date of the enactment of this Act, the Commission in consultation with the Attorney General shall prescribe clearly identifiable marks or notices to be included in or associated with commercial electronic mail that contains sexually oriented material, in order to inform the recipient of that fact and to facilitate filtering of such electronic mail. The Commission shall publish in the Federal Register and provide notice to the public of the marks or notices prescribed under this paragraph.” |
| `7706(b)(7)/body/1` | /us/usc/t15/s7706/b/7; Pub. L. 108-187 § 7(b)(7) | — | “, United States Code,” | “(7) under part A of subtitle VII of title 49 by the Secretary of Transportation with respect to any air carrier or foreign air carrier subject to that part;” | “(7) under part A of subtitle VII of title 49, United States Code, by the Secretary of Transportation with respect to any air carrier or foreign air carrier subject to that part;” |
| `7706(g)(1)/body/2` | /us/usc/t15/s7706/g/1; Pub. L. 108-187 § 7(g)(1) | — | “5” | “(1) Action authorized A provider of Internet access service adversely affected by a violation of section 7704(a)(1), (b), or (d) of this title, or a pattern or practice that violates paragraph (2), (3), (4), or (5) of section 7704(a) of this title, may bring a civil action in any district court of the United States with jurisdiction over the defendant—” | “(1) Action authorized.--A provider of Internet access service adversely affected by a violation of section 5(a)(1), 5(b), or 5(d), or a pattern or practice that violates paragraph (2), (3), (4), or (5) of section 5(a), may bring a civil action in any district court of the United States with jurisdiction over the defendant--” |
| `7706(g)(1)/body/3` | /us/usc/t15/s7706/g/1; Pub. L. 108-187 § 7(g)(1) | — | “5” | “(1) Action authorized A provider of Internet access service adversely affected by a violation of section 7704(a)(1), (b), or (d) of this title, or a pattern or practice that violates paragraph (2), (3), (4), or (5) of section 7704(a) of this title, may bring a civil action in any district court of the United States with jurisdiction over the defendant—” | “(1) Action authorized.--A provider of Internet access service adversely affected by a violation of section 5(a)(1), 5(b), or 5(d), or a pattern or practice that violates paragraph (2), (3), (4), or (5) of section 5(a), may bring a civil action in any district court of the United States with jurisdiction over the defendant--” |
| `7706(g)(1)/body/4` | /us/usc/t15/s7706/g/1; Pub. L. 108-187 § 7(g)(1) | “of this title” | — | “(1) Action authorized A provider of Internet access service adversely affected by a violation of section 7704(a)(1), (b), or (d) of this title, or a pattern or practice that violates paragraph (2), (3), (4), or (5) of section 7704(a) of this title, may bring a civil action in any district court of the United States with jurisdiction over the defendant—” | “(1) Action authorized.--A provider of Internet access service adversely affected by a violation of section 5(a)(1), 5(b), or 5(d), or a pattern or practice that violates paragraph (2), (3), (4), or (5) of section 5(a), may bring a civil action in any district court of the United States with jurisdiction over the defendant--” |
| `7708(a)/body/1` | /us/usc/t15/s7708/a; Pub. L. 108-187 § 9(a) | “December 16, 2003” | “the date of enactment of this Act” | “(a) In general Not later than 6 months after December 16, 2003, the Commission shall transmit to the Senate Committee on Commerce, Science, and Transportation and the House of Representatives Committee on Energy and Commerce a report that—” | “(a) In General.--Not later than 6 months after the date of enactment of this Act, the Commission shall transmit to the Senate Committee on Commerce, Science, and Transportation and the House of Representatives Committee on Energy and Commerce a report that--” |
| `7708(b)/body/1` | /us/usc/t15/s7708/b; Pub. L. 108-187 § 9(b) | “December 16, 2003” | “the date of enactment of this Act” | “(b) Authorization to implement The Commission may establish and implement the plan, but not earlier than 9 months after December 16, 2003.” | “(b) Authorization To Implement.--The Commission may establish and implement the plan, but not earlier than 9 months after the date of enactment of this Act.” |
| `7709(a)/body/1` | /us/usc/t15/s7709/a; Pub. L. 108-187 § 10(a) | “December 16, 2003” | “the date of the enactment of this Act” | “(a) In general Not later than 24 months after December 16, 2003, the Commission, in consultation with the Department of Justice and other appropriate agencies, shall submit a report to the Congress that provides a detailed analysis of the effectiveness and enforcement of the provisions of this chapter and the need (if any) for the Congress to modify such provisions.” | “(a) In General.--Not later than 24 months after the date of the enactment of this Act, the Commission, in consultation with the Department of Justice and other appropriate agencies, shall submit a report to the Congress that provides a detailed analysis of the effectiveness and enforcement of the provisions of this Act and the need (if any) for the Congress to modify such provisions.” |
| `7710(1)/body/1` | /us/usc/t15/s7710/1; Pub. L. 108-187 § 11(1) | “December 16, 2003” | “the date of enactment of this Act” | “(1) a report, within 9 months after December 16, 2003, that sets forth a system for rewarding those who supply information about violations of this chapter, including—” | “(1) a report, within 9 months after the date of enactment of this Act, that sets forth a system for rewarding those who supply information about violations of this Act, including--” |
| `7710(2)/body/1` | /us/usc/t15/s7710/2; Pub. L. 108-187 § 11(2) | “December 16, 2003” | “the date of enactment of this Act” | “(2) a report, within 18 months after December 16, 2003, that sets forth a plan for requiring commercial electronic mail to be identifiable from its subject line, by means of compliance with Internet Engineering Task Force Standards, the use of the characters “ADV” in the subject line, or other comparable identifier, or an explanation of any concerns the Commission has that cause the Commission to recommend against the plan.” | “(2) a report, within 18 months after the date of enactment of this Act, that sets forth a plan for requiring commercial electronic mail to be identifiable from its subject line, by means of compliance with Internet Engineering Task Force Standards, the use of the characters ``ADV'' in the subject line, or other comparable identifier, or an explanation of any concerns the Commission has that cause the Commission to recommend against the plan.” |
