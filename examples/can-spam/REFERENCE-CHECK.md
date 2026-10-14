# Reference check: the regulation and the codified statute against their reference texts

This is a report, not code. It compares, by text alone and without interpreting anything, each
text this example corpus is built from against the text that is the law it claims to be.

| Text checked | Edition | Reference text | Edition |
|---|---|---|---|
| 16 CFR 316.1-316.6, `part316.xml` (SHA-256 `45bf26b6…83b0`) | eCFR, point-in-time 2026-10-01 | the official annual edition of 16 CFR Part 316, Title 16 Vol. 1, GPO XML (SHA-256 `a6730763…7da2`) | revised as of 2026-01-01 |
| 15 U.S.C. 7701-7713, chapter 103, section bodies without notes: member `usc15.xml` of the OLRC USLM release point 119-120 (zip SHA-256 `e053dcad…9e699`; member `f645b7be…93b`) | current through Pub. L. 119-120 | the CAN-SPAM Act as enacted, Pub. L. 108-187, 117 Stat. 2699, GPO plain-text rendition (SHA-256 `cf42d67e…ef4f`), sections 2-15 | 2003-12-16 |

The two editions of the regulation are nine months apart (2026-01-01 and 2026-10-01). A
difference between them could be an amendment as well as an error; the comparison cannot tell,
and nothing below is read as either.

## Method

Normalized, and nothing else:

- **Whitespace**: every sequence collapsed to one space, including line breaks inside a paragraph.
- **Markup**: XML elements removed, text kept in document order. Footnotes are kept where they
  stand. In the statute, `<notes>` and `<sourceCredit>` are removed (the section bodies "without
  notes"); in the Act, the GPO `[[Page 117 STAT. n]]` markers and the `<<NOTE: …>>` insertions are
  removed, a word broken at a line end after a hyphen is joined, and the typewriter forms
  ``` `` ```, `''` and `--` are read as the typographic “ ” and —. These last conversions are the
  plain-text rendition's only way to print those characters, and they are stated here because they
  are the one place the normalization is not purely whitespace and markup.

Everything else is compared as it stands, word by word and punctuation mark by punctuation mark,
case-sensitively, headings included. Each difference below is listed with both texts quoted (cut to
25 words) and where it falls. A difference is called **explained by the source** only where a note
in the same source says so; every other difference is **unexplained**, whatever it looks like.
Differences of the same kind are listed once with every location.

## 16 CFR 316.1-316.6

Section by section, with paragraph, footnote and heading text included, the two texts have the
same words and the same order: 316.1 (23 words), 316.2 (501-502), 316.3 (652), 316.4 (390),
316.5 (119), 316.6 (38).

| Differences | Explained by the source | Unexplained |
|---:|---:|---:|
| 1 | 0 | 1 |

| Location | eCFR 2026-10-01 | Annual edition 2026-01-01 |
|---|---|---|
| 16 CFR 316.6, only paragraph | “The provisions of this part are separate and severable from one another.” | “The provisions of this Part are separate and severable from one another.” |

One more place differs in the bytes and not in the text: in 316.2(m) the annual edition puts a
line break between the italic “provided that” and the comma that follows it, which is whitespace and
is normalized away.

## 15 U.S.C. 7701-7713 against Pub. L. 108-187

The Act's sections 2-15 are aligned to the codified sections by the `15 USC` note GPO prints at
each, and by heading. Act section 12 (“Restrictions on other transmissions”) has no counterpart in
chapter 103: the note to § 7711 says it amended 47 U.S.C. 227. Act sections 1 and 16 are in the
codification only as notes, and notes are outside this comparison. The table shows which Act
section meets which codified section.

Total: **303** differences — **43 explained by the source**, **260 unexplained**.

| Codified § | Act § | Explained | Unexplained |
|---|---|---:|---:|
| 7701 | 2 | 0 | 5 |
| 7702 | 3 | 5 | 36 |
| 7703 | 4 | 1 | 13 |
| 7704 | 5 | 1 | 35 |
| 7705 | 6 | 2 | 17 |
| 7706 | 7 | 18 | 106 |
| 7707 | 8 | 5 | 13 |
| 7708 | 9 | 0 | 7 |
| 7709 | 10 | 2 | 4 |
| 7710 | 11 | 4 | 4 |
| 7711 | 13 | 0 | 8 |
| 7712 | 14 | 3 | 11 |
| 7713 | 15 | 2 | 1 |

| Class | Count | Explained by source |
|---|---:|---|
| "this chapter" (code) for "this Act" (Act) — explained by the source | 40 | yes |
| § 7703 body "Omitted" — explained by the source | 1 | yes |
| § 7706(d) footnote "So in original." — explained by the source | 2 | yes |
| "December 16, 2003" (code) for "the date of (the) enactment of this Act" (Act) | 7 | no |
| cross-references: Act section numbers (5, 7, 13, 3) against codified section numbers (7704, 7706, 7711, 7702), the Act's "of this title" qualifier, and en dash for hyphen in "80a–1" | 75 | no |
| ", United States Code" after "title 18" / "title 28" / "title 49" / "title 5" in the Act, absent from the code | 14 | no |
| citations to other Acts: the Act names the Act (and its U.S.C. place), the code says "of this title"/"title"; and "of this title" for "of this Act" at § 7706(f)(1) | 12 | no |
| heading capitalisation and terminal punctuation (Act: capitals or title case; code: sentence case) | 60 | no |
| apostrophe: ’ in the code, ' in the Act | 11 | no |
| run-in heading delimiter ".—" in the Act, absent in the code | 81 | no |

#### "this chapter" (code) for "this Act" (Act) — explained by the source (40)

| Location (codified § / Act §) | Code (USLM) | Act (enacted) |
|---|---|---|
| § 7702; § 7702(16)(B); § 7702(17)(B); § 7702(2)(D); § 7704(a)(4)(A)(iv); § 7705(d); § 7706(a); § 7706(b); § 7706(b)(6); § 7706(c); § 7706(d); § 7706(e); § 7706(f)(2); § 7706(f)(6); § 7706(f)(8); § 7706(f)(9); § 7706(g)(2); § 7707(a)(1); § 7707(a)(2); § 7707(b)(1); § 7707(b)(2); § 7707(c); § 7709(a); § 7709(b)(1); § 7710(1); § 7710(1)(A); § 7710(1)(A)(i); § 7710(1)(B); § 7712(a); § 7712(b)(3); § 7712(b)(4); § 7713 (×40; Act §§ 3, 5, 6, 7, 8, 10, 11, 14, 15) | “chapter” | “Act” |

#### § 7703 body "Omitted" — explained by the source (1)

| Location (codified § / Act §) | Code (USLM) | Act (enacted) |
|---|---|---|
| § 7703(a) / Act §4 | “Omitted” | “Offense. — (1) In general. — Chapter 47 of title 18, United States Code, is amended by adding at the end the following new section: … [829 words in all]” |

#### § 7706(d) footnote "So in original." — explained by the source (2)

| Location (codified § / Act §) | Code (USLM) | Act (enacted) |
|---|---|---|
| § 7706(d) / Act §7 | “11 So in original.” | — |
| § 7706(d) / Act §7 | “1” | — |

#### "December 16, 2003" (code) for "the date of (the) enactment of this Act" (Act) (7)

| Location (codified § / Act §) | Code (USLM) | Act (enacted) |
|---|---|---|
| § 7702(2)(C) / Act §3; § 7704(d)(3) / Act §5; § 7709(a) / Act §10 | “December 16, 2003” | “the date of the enactment of this Act” |
| § 7708(a) / Act §9; § 7708(b) / Act §9; § 7710(1) / Act §11; § 7710(2) / Act §11 | “December 16, 2003” | “the date of enactment of this Act” |

#### cross-references: Act section numbers (5, 7, 13, 3) against codified section numbers (7704, 7706, 7711, 7702), the Act's "of this title" qualifier, and en dash for hyphen in "80a–1" (75)

| Location (codified § / Act §) | Code (USLM) | Act (enacted) |
|---|---|---|
| § 7702(2)(C) / Act §3; § 7702(17)(B) / Act §3; § 7704(c) / Act §5 | “7711 of this title” | “13” |
| § 7704(a)(2) / Act §5; § 7712(a) / Act §14 | “of this title” | “)” |
| § 7705(a); § 7705(b)(2)(B)(i); § 7706(e); § 7706(f)(1); § 7706(f)(1)(A); § 7706(f)(2); § 7706(f)(3)(B); § 7706(f)(3)(C)(ii); § 7706(f)(9); § 7706(g)(1); § 7706(g)(3)(A); § 7706(g)(3)(A)(i); § 7706(g)(3)(B); § 7706(g)(3)(C)(ii); § 7711(b) (×31; Act §§ 6, 7, 13) | “7704” | “5” |
| § 7705(a); § 7705(b)(2)(B)(i); § 7705(d); § 7706(e); § 7706(f)(2); § 7706(f)(3)(B); § 7706(f)(3)(C)(ii); § 7706(f)(9); § 7706(g)(1); § 7706(g)(2); § 7706(g)(3)(A); § 7706(g)(3)(A)(i); § 7706(g)(3)(B); § 7706(g)(3)(C)(ii); § 7711(b) (×29; Act §§ 6, 7, 13) | “of this title” | — |
| § 7705(c) / Act §6 | “7706 of this title” | “7” |
| § 7705(d) / Act §6 | “7706” | “7” |
| § 7706(b)(4) / Act §7; § 7706(b)(5) / Act §7 | “–” | “-” |
| § 7706(f)(3)(B) / Act §7; § 7706(g)(3)(A)(ii) / Act §7; § 7706(g)(3)(B) / Act §7 | “7704 of this title” | “5” |
| § 7706(g)(1) / Act §7; § 7706(g)(1) / Act §7 | — | “5” |
| § 7706(g)(2) / Act §7 | “7702” | “3” |

#### ", United States Code" after "title 18" / "title 28" / "title 49" / "title 5" in the Act, absent from the code (14)

| Location (codified § / Act §) | Code (USLM) | Act (enacted) |
|---|---|---|
| § 7702(13); § 7703(c)(2); § 7704(d)(4); § 7706(f)(7)(A); § 7711(a) (×8; Act §§ 3, 4, 5, 7, 13) | — | “, United States Code” |
| § 7703(b)(1) / Act §4; § 7703(b)(2)(A) / Act §4; § 7706(b)(7) / Act §7 | — | “, United States Code,” |
| § 7703(b)(1) / Act §4; § 7704(d)(5) / Act §5; § 7707(a)(1) / Act §8 | — | “United States Code,” |

#### citations to other Acts: the Act names the Act (and its U.S.C. place), the code says "of this title"/"title"; and "of this title" for "of this Act" at § 7706(f)(1) (12)

| Location (codified § / Act §) | Code (USLM) | Act (enacted) |
|---|---|---|
| § 7702(11) / Act §3; § 7707(a)(1) / Act §8; § 7712(a) / Act §14; § 7712(d) / Act §14 | “title” | “the Communications Act of 1934 (” |
| § 7702(11) / Act §3 | — | “U.S.C. 231(e)(4))” |
| § 7704(a)(2) / Act §5 | — | “5 of the Federal Trade Commission Act (15 U.S.C.” |
| § 7706(f)(1) / Act §7; § 7706(f)(1)(A) / Act §7 | “title” | “Act” |
| § 7707(a)(1) / Act §8 | — | “U.S.C. 223 or 231, respectively)” |
| § 7712(a) / Act §14 | — | “U.S.C. 227)” |
| § 7712(a) / Act §14 | — | “3 of the Telemarketing and Consumer Fraud and Abuse Prevention Act (15 U.S.C.” |
| § 7712(d) / Act §14 | — | “U.S.C. 332(d))” |

#### heading capitalisation and terminal punctuation (Act: capitals or title case; code: sentence case) (60)

| Location (codified § / Act §) | Code (USLM) | Act (enacted) |
|---|---|---|
| § 7701 / Act §2 | “Congressional findings and policy” | “CONGRESSIONAL FINDINGS AND POLICY.” |
| § 7701(b) / Act §2 | “determination” | “Determination” |
| § 7701(b) / Act §2 | “public policy” | “Public Policy. —” |
| § 7702 / Act §3 | “Definitions” | “DEFINITIONS.” |
| § 7702(7) / Act §3 | “Act” | “act. —” |
| § 7703 / Act §4 | “Prohibition against predatory and abusive commercial e” | “PROHIBITION AGAINST PREDATORY AND ABUSIVE COMMERCIAL E” |
| § 7703 / Act §4 | “mail” | “MAIL.” |
| § 7704 / Act §5 | “Other protections for users of commercial electronic mail” | “OTHER PROTECTIONS FOR USERS OF COMMERCIAL ELECTRONIC MAIL.” |
| § 7704(a) / Act §5 | “transmission” | “Transmission” |
| § 7704(a) / Act §5 | “messages” | “Messages. —” |
| § 7704(b) / Act §5 | “violations relating” | “Violations Relating” |
| § 7704(b) / Act §5 | “commercial electronic mail” | “Commercial Electronic Mail. —” |
| § 7704(c) / Act §5 | “rulemaking authority” | “Rulemaking Authority. —” |
| § 7704(d) / Act §5 | “to place warning labels” | “To Place Warning Labels” |
| § 7704(d) / Act §5 | “commercial electronic mail containing sexually oriented material” | “Commercial Electronic Mail Containing Sexually Oriented Material. —” |
| § 7705 / Act §6 | “Businesses knowingly promoted by electronic mail with false or misleading transmission information” | “BUSINESSES KNOWINGLY PROMOTED BY ELECTRONIC MAIL WITH FALSE OR MISLEADING TRANSMISSION INFORMATION.” |
| § 7705(a) / Act §6; § 7708(a) / Act §9; § 7709(a) / Act §10; § 7711(a) / Act §13 | “general” | “General. —” |
| § 7705(b) / Act §6 | “enforcement against third parties” | “Enforcement Against Third Parties. —” |
| § 7705(c) / Act §6 | “enforcement” | “Enforcement” |
| § 7705(d) / Act §6 | “provision” | “Provision. —” |
| § 7706 / Act §7 | “Enforcement generally” | “ENFORCEMENT GENERALLY.” |
| § 7706(a) / Act §7 | “is unfair” | “Is Unfair” |
| § 7706(a) / Act §7 | “deceptive act” | “Deceptive Act” |
| § 7706(a) / Act §7 | “practice” | “Practice. —” |
| § 7706(b) / Act §7 | “certain other agencies” | “Certain Other Agencies. —” |
| § 7706(c) / Act §7 | “certain powers” | “Certain Powers. —” |
| § 7706(e) / Act §7 | “cease” | “Cease” |
| § 7706(e) / Act §7 | “desist orders” | “Desist Orders” |
| § 7706(e) / Act §7 | “injunctive relief without showing” | “Injunctive Relief Without Showing” |
| § 7706(e) / Act §7 | “knowledge” | “Knowledge. —” |
| § 7706(f)(5) / Act §7; § 7706(f)(8) / Act §7 | “Federal” | “federal” |
| § 7706(f)(8) / Act §7 | “State” | “state” |
| § 7706(g) / Act §7 | “provider” | “Provider” |
| § 7706(g) / Act §7; § 7707(c) / Act §8 | “access service” | “Access Service. —” |
| § 7707 / Act §8 | “Effect on other laws” | “EFFECT ON OTHER LAWS.” |
| § 7707(a) / Act §8; § 7707(b) / Act §8 | “law” | “Law. —” |
| § 7707(c) / Act §8 | “effect” | “Effect” |
| § 7707(c) / Act §8 | “policies” | “Policies” |
| § 7707(c) / Act §8 | “providers” | “Providers” |
| § 7708 / Act §9 | “Do” | “DO” |
| § 7708 / Act §9 | “Not” | “NOT” |
| § 7708 / Act §9 | “Mail registry” | “MAIL REGISTRY.” |
| § 7708(b) / Act §9 | “to implement” | “To Implement. —” |
| § 7709 / Act §10 | “Study of effects of commercial electronic mail” | “STUDY OF EFFECTS OF COMMERCIAL ELECTRONIC MAIL.” |
| § 7709(b) / Act §10 | “analysis” | “Analysis. —” |
| § 7710 / Act §11 | “Improving enforcement by providing rewards for information about violations” | “IMPROVING ENFORCEMENT BY PROVIDING REWARDS FOR INFORMATION ABOUT VIOLATIONS” |
| § 7710 / Act §11 | “labeling” | “LABELING.” |
| § 7711 / Act §13 | “Regulations” | “REGULATIONS.” |
| § 7712 / Act §14 | “Application to wireless” | “APPLICATION TO WIRELESS.” |
| § 7712(a) / Act §14 | “other law” | “Other Law. —” |
| § 7712(b) / Act §14 | “rulemaking” | “Rulemaking. —” |
| § 7712(c) / Act §14 | “factors considered” | “Factors Considered. —” |
| § 7712(d) / Act §14 | “service commercial message defined” | “Service Commercial Message Defined. —” |
| § 7713 / Act §15 | “Separability” | “SEPARABILITY.” |

#### apostrophe: ’ in the code, ' in the Act (11)

| Location (codified § / Act §) | Code (USLM) | Act (enacted) |
|---|---|---|
| § 7701(a)(8); § 7702(1)(A); § 7702(1)(B); § 7702(12); § 7702(17)(A)(iii)(II); § 7705(a); § 7705(a)(1); § 7706(f)(3)(C)(ii); § 7706(g)(3)(C)(ii); § 7706(g)(4); § 7707(a)(2) (×11; Act §§ 2, 3, 6, 7, 8) | “’” | “'” |

#### run-in heading delimiter ".—" in the Act, absent in the code (81)

Code: heading element with no delimiter. Act: “Heading.—Text”. Locations (codified § in the cell): 

- 7701: 7701(a)
- 7702: 7702(1), 7702(2), 7702(2)(A), 7702(2)(B), 7702(2)(C), 7702(2)(D), 7702(3), 7702(4), 7702(5), 7702(6), 7702(8), 7702(9), 7702(10), 7702(11), 7702(12), 7702(13), 7702(14), 7702(15), 7702(16), 7702(16)(A), 7702(16)(B), 7702(17), 7702(17)(A), 7702(17)(B)
- 7703: 7703(b), 7703(b)(1), 7703(b)(2), 7703(c)
- 7704: 7704(a)(1), 7704(a)(2), 7704(a)(3), 7704(a)(3)(A), 7704(a)(3)(B), 7704(a)(3)(C), 7704(a)(4), 7704(a)(4)(A), 7704(a)(4)(B), 7704(a)(5), 7704(a)(6), 7704(b)(1), 7704(b)(1)(A), 7704(b)(1)(B), 7704(b)(2), 7704(b)(3), 7704(d)(1), 7704(d)(2), 7704(d)(3), 7704(d)(4), 7704(d)(5)
- 7705: 7705(b)(1), 7705(b)(2), 7705(c)
- 7706: 7706(d), 7706(f), 7706(f)(1), 7706(f)(2), 7706(f)(3), 7706(f)(3)(A), 7706(f)(3)(B), 7706(f)(3)(C), 7706(f)(3)(D), 7706(f)(4), 7706(f)(5), 7706(f)(6), 7706(f)(7), 7706(f)(7)(A), 7706(f)(7)(B), 7706(f)(8), 7706(f)(9), 7706(g)(1), 7706(g)(2), 7706(g)(3), 7706(g)(3)(A), 7706(g)(3)(B), 7706(g)(3)(C), 7706(g)(3)(D), 7706(g)(4)
- 7707: 7707(b)(1), 7707(b)(2)
- 7711: 7711(b)

