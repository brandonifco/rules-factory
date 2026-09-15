#!/usr/bin/env python3
"""Copy docs/method.md and docs/corpus-map.md into a blind bundle for the SRD 5.2.1 combat map.

Adapted from examples/hoyle-backgammon/blind-mapping/redact.py. The docs still carry the
backgammon examples that file removed, and its edits are kept: backgammon is another corpus, but
its examples name dice, turns, suspensions and a phase gate, which are this chapter's shapes too,
and removing them again costs nothing. One of its edits changed: the page-extent example, whose
old target no longer matches, and whose replacement (pages 12-19) would have overlapped this
slice; it is now pages 40-47. The SRD edits at the end remove the corpus's name and the combat
vocabulary the method's generic prose carries (damage after attack, a person under cover, a
creature's statistics). The first mapping (#108) added no SRD example to either doc.

Each edit must match exactly once (whitespace-insensitive). Writes the redacted docs and a
REDACTIONS.md listing every edit."""
import pathlib, re, sys

SRC = pathlib.Path(sys.argv[1])      # repo root
OUT = pathlib.Path(sys.argv[2])      # bundle dir
LOG = pathlib.Path(sys.argv[3])      # REDACTIONS.md path

M = "method.md"
C = "corpus-map.md"

EDITS = [
 # ---------------- method.md ----------------
 (M, "adapter-illustration example",
  "The starting position of a backgammon board, in a trial corpus, is given entirely\nas an illustration — fully determined, and invisible to a plain-text adapter.",
  "A table of freight rates, in a hypothetical tariff, may be printed only as an\nimage — fully determined, and invisible to a plain-text adapter."),
 (M, "derived-entry example (hit pays single stake)",
  "a hit pays the single stake, because a gammon and\na backgammon are both paid as multiples of it",
  "a lease charging a late fee of 2% of the rent per week, capped at 10%, reaches its cap in the\nfifth week"),
 (M, "count of wrong backgammon citations",
  "Thirteen of the backgammon\nmap's twenty-four citations were wrong by a page or two, and survived a mapping trial, a build\nand a review, because every one of them was summarised.",
  "In one trial, more than half of a\nmap's citations were wrong by a page or two, and survived a mapping trial, a build\nand a review, because every one of them was summarised."),
 (M, "definitions paragraph: board vocabulary quotes, entry ids point-designations / direction-of-travel, #13",
  "Twelve points to a table named ace through six, inner tables numbering from the far end and\nouter tables from the bar, men travelling \"from the ace point in his opponent's home table\ntowards the like point in his own\" — these read as preamble and are load-bearing. Without them\nthe entries that use the vocabulary cannot be interpreted at all, and nothing else in the map\nsays a board has twenty-four points or that the course has a direction. Both were missed on the\nfirst pass of the second trial for the same reason: a mapper hunting for rules reads past\nvocabulary. `point-designations` and `direction-of-travel` are the instances\n([#13](https://github.com/brandonifco/rules-factory/issues/13)).",
  "Zones of a pitch named by letter, distances measured from a named line, a season \"running from\nthe first Saturday in March to the last Sunday in October\" — these read as preamble and are\nload-bearing. Without them the entries that use the vocabulary cannot be interpreted at all.\nDefinitions like these have been missed on a first pass for one reason: a mapper hunting for\nrules reads past vocabulary."),
 (M, "advice example quoting the corpus (\"It is always an object to do this\")",
  "\"It is\nalways an object to do this\" sits in the middle of a trial corpus's movement rules.",
  "\"It is\nusually wise to keep a reserve\" can sit in the middle of a rulebook's supply rules."),
 (M, "phase-gate examples (bearing off / man on the bar)",
  "bearing off begins once every man is home;\na man on the bar suspends every other move.",
  "overtime begins once regulation time ends level;\na player serving a penalty takes no part in play."),
 (M, "gate-reach example naming full-table-suspension",
  "A rule that suspends\na player's whole turn reaches the throw and everything a throw leads to; the backgammon map\nrecorded none of that for `full-table-suspension` through a trial, a build and a review, and\nthe omission changed every later throw of a seeded game while passing every legality test.",
  "A rule that suspends\nevery action of a participant reaches all of those actions, not only the one it is written\nbeside; one trial map recorded a suspension on none of the entries it reached, through a trial,\na build and a review."),
 (M, "scope example (1909 text has no doubling cube)",
  "A 1909 games text has no doubling cube; an engine built from it is a 1909 engine,",
  "A 1950 edition has no rule the 1980 edition added; an engine built from it is a 1950 engine,"),
 (M, "per-rule scope example (Hints for Play / die faces, #20)",
  "The\nbackgammon map excluded *Hints for Play* wholesale as advice and so lost the only authority in\nthe corpus for how many faces a die has\n([#20](https://github.com/brandonifco/rules-factory/issues/20)).",
  "A\nsection titled as commentary can still state a rule, and only reading it shows whether it does."),
 (M, "delegated-choice example quoting the corpus (\"thrice or four times (as may have been agreed)\")",
  "*\"Either\nthrice or four times (as may have been agreed)\"* is the clearest case — read as an ambiguity,\nthe engine discards the rule that the multiplier is three or four and nothing else.",
  "*\"A\ndeposit of one month's or two months' rent, at the tenant's election\"* is the clearest case —\nread as an ambiguity, the engine discards the rule that the deposit is one or two months' rent\nand nothing else."),
 (M, "gate 1 examples (thrice or four times; wholly/partly play; game-value, must-play-whole-throw)",
  "*\"Either thrice or four\n   times\"* leaves the multiplier unfixed and is a blank; *\"either wholly by moving men forward …\n   or partly by the one method and partly by the other\"* states every branch and is not. \"Or case\"\n   is what catches a defective enumeration — `game-value`, `must-play-whole-throw` — which is a\n   gap without being an open degree.",
  "*\"One month's or two\n   months' rent\"* leaves the deposit unfixed and is a blank; *\"by bank transfer, by cheque, or\n   partly by each\"* states every branch and is not. \"Or case\" is what catches a defective\n   enumeration — a list of cases that does not cover every input — which is a gap without being\n   an open degree."),
 (M, "derived-consequence examples (must-play-whole-throw, opening throw never doublets, bearing-off-highest)",
  "that `must-play-whole-throw`\ndeclines in exactly one shape of throw, that the adopted opening throw can never be doublets\nbecause a tie is thrown again, that `bearing-off-highest` is the opposite of what a modern\nplayer expects.",
  "that a fee rule\ndeclines in exactly one shape of input, that a late fee can never reach its cap in the first\nmonth, that a tie-break rule is the opposite of what a modern reader expects."),
 (M, "derived-consequence rot example (the opening rule changes)",
  "silently become false the day the opening rule changes;",
  "silently become false the day the rule changes;"),
 (M, "replay-list example (chosen play among the legal plays)",
  "the index of the chosen play among the legal plays",
  "the index of the chosen action among the legal actions"),
 (M, "replay-list rule naming hoyle-backgammon LegalPlays.For",
  "Decided on\n[#22](https://github.com/brandonifco/rules-factory/issues/22); `hoyle-backgammon` pins\n`LegalPlays.For` this way.",
  "Decided on #22."),
 (M, "engine feedback example (backgammon map moved twice)",
  "The backgammon map moved twice in one day because of what its engine found.",
  "One trial map moved twice in one day because of what its engine found."),
 # ---------------- corpus-map.md ----------------
 (C, "page-extent example 271-280 (the backgammon chapter)",
  "\"extent\": { \"unit\": \"page\", \"from\": 271, \"to\": 280 }",
  "\"extent\": { \"unit\": \"page\", \"from\": 40, \"to\": 47 }"),
 (C, "extent paragraph: backgammon citations 271-277 and throw enumeration on 278-280 (#20)",
  "which deriving the extent from the citations would have allowed: the backgammon\ncitations run 271–277, and the throw enumeration that #20 is about is on 278–280.",
  "which deriving the extent from the citations would have allowed."),
 (C, "gate-scope sentence quoting strategy-advice (\"make points whenever you fairly can\")",
  "`strategy-advice`'s \"make points whenever you **fairly** can\" is an undefined degree that demands\nnothing of anybody",
  "a strategy note's \"keep a reserve whenever you **reasonably** can\" is an undefined degree that\ndemands nothing of anybody"),
 (C, "gate 1 examples (thrice or four times; wholly/partly; game-value and must-play-whole-throw verdicts)",
  "Applying *\"either thrice or four times\"* requires fixing the multiplier;\n   applying *\"either wholly by moving men forward … or partly by the one method and partly by the\n   other\"* requires fixing nothing, because the corpus states every branch. Whether ATC authorized\n   is a fact the rule tests, not a blank. **\"Or case\" is load-bearing and is there for two\n   instances**: `game-value`'s three named results do not cover a reachable finish and\n   `must-play-whole-throw` does not say which die is lost when only one is playable. Neither is an\n   open degree, both are gaps, and a gate written only for undefined terms cannot see either.",
  "Applying *\"one month's or two months' rent\"* requires fixing the deposit;\n   applying *\"by bank transfer, by cheque, or partly by each\"* requires fixing nothing, because\n   the corpus states every branch. Whether ATC authorized is a fact the rule tests, not a blank.\n   **\"Or case\" is load-bearing**: a fee schedule that prices one-, two- and three-bedroom units\n   and says nothing of a studio is not an open degree, is a gap, and a gate written only for\n   undefined terms cannot see it."),
 (C, "gate 3 fixed-set example and agentless passive quoting the corpus",
  "or the fixed set: \"**either thrice or four times**\". An\nassertion entry that can quote neither is a gap. The disjunction is the two arms, delegated\nstandard and delegated choice, and the second has no measure and must not need one. Parties need\nnot be **named**: *\"(as may have been agreed)\"* is an agentless passive and names nobody, which is\nwhat refuted two of the five tests.",
  "or the fixed set: \"**one month's or two months' rent**\".\nAn assertion entry that can quote neither is a gap. The disjunction is the two arms, delegated\nstandard and delegated choice, and the second has no measure and must not need one. Parties need\nnot be **named**: an agentless passive that names nobody still delegates, which is what refuted\ntwo of the five tests."),
 (C, "count of wrong backgammon citations",
  "**thirteen of the backgammon map's citations were wrong by a page or\ntwo through a mapping trial, a build and a review**",
  "**more than half of one trial map's citations were wrong by a page or\ntwo through a mapping trial, a build and a review**"),
 (C, "ellipsis example naming point-designations and its word count",
  "`point-designations`\nwas exactly this: a 118-word `evidence` of which 11 words were ever checked.",
  "One trial entry\nwas exactly this: most of its `evidence` was never checked."),
 (C, "page-straddle example (arrangement sentence p. 272, {273} marker)",
  "The arrangement sentence begins\non p. 272 and the `{273}` marker falls mid-sentence.",
  "A sentence may begin on one page\nwith the next page's marker falling mid-sentence."),
 (C, "note examples (quatre and trois; throw fully/partly/unplayable)",
  "\"Both figures\",\n\"the worked distribution, for both the quatre and the trois\", \"a throw fully playable, partly\nplayable, and unplayable\"",
  "\"Both figures\",\n\"every row of the fee schedule\", \"a notice served on a working day and on a holiday\""),
 (C, "note-claim example (opening throw never doublets)",
  "*\"The adopted opening throw can never be doublets\"* is a claim about the engine's answers\nthat a test can assert and that will silently become false if the opening rule changes;",
  "*\"A late fee can never reach its cap in the first month\"* is a claim about the engine's\nanswers that a test can assert and that will silently become false if the fee rule changes;"),
 (C, "out/absent examples (strategy-advice, doubling-cube, 29 checked)",
  "`strategy-advice` quotes the opening sentence of the advice it declines, and demands nothing\nof the engine. A rule the corpus does not state at all — `doubling-cube`, which this 1909 text\npredates — quotes **the passage the rule would be in**, and carries `absentFrom` to say that is\nwhat the span is. There is no exception and no entry without a span. Until\n[0009](decisions/0009-absence-is-a-verdict-with-evidence.md) there was: the citation read\n`(absent)`, the checker special-cased it, and the gate's line \"all 29 checked\" meant\ntwenty-eight.",
  "a declined strategy note quotes the opening sentence of the advice it declines, and demands\nnothing of the engine. A rule the corpus does not state at all — one a later edition added,\nsay — quotes **the passage the rule would be in**, and carries `absentFrom` to say that is\nwhat the span is. There is no exception and no entry without a span. Until decision 0009 there\nwas: the citation read `(absent)`, the checker special-cased it, and the gate's count included\nan entry it had not checked."),
 (C, "self-contradiction example (enter-from-bar vs legal-destination)",
  "`enter-from-bar` names two legal destinations where `legal-destination`, three sentences\nearlier, names three.",
  "A lease that says in clause 4 that rent is due on the first and in clause 11 that it is due on\nthe fifth is the shape."),
 (C, "conflict JSON example (points-open-to-an-entering-man, decision 0006)",
  "\"conflict\": \"points-open-to-an-entering-man\",\n  \"fate\": \"decision\",\n  \"decision\": \"docs/decisions/0006-the-general-rule-governs-entry-and-full-means-adversely-full.md\"",
  "\"conflict\": \"rent-due-day\",\n  \"fate\": \"decision\",\n  \"decision\": \"docs/decisions/0098-the-later-clause-governs-the-due-day.md\""),
 (C, "conflict paragraph naming enter-from-bar / full-table-suspension / legal-destination",
  "The three backgammon entries carrying this slug do\nnot each contradict each other — `enter-from-bar` and `full-table-suspension` fit together\nexactly, and both disagree with `legal-destination`. What makes them one conflict is that they\nare three answers to *which points are open to a man entering from the bar*.",
  "Three entries carrying one slug need\nnot each contradict each other — two can fit together exactly, and both disagree with the\nthird. What makes them one conflict is that they are three answers to one question, such as\n*on which day rent falls due*."),
 (C, "phase-gate examples (bearing off / entry from the bar)",
  "bearing off\nbegins once every man is home; entry from the bar suspends every other move",
  "overtime\nbegins once regulation time ends level; a penalty suspends a player from play"),
 (C, "dependsOn vs gates example (bearing-off-doublets, move-by-pip, enter-from-bar)",
  "In the backgammon map, `bearing-off-doublets` has six `dependsOn` ancestors and\nexactly one of them is its gate; `move-by-pip` is suspended by `enter-from-bar`, which is not\namong its ancestors, and nor is `move-by-pip` among `enter-from-bar`'s.",
  "In one trial map an entry had six `dependsOn` ancestors and exactly one of them\nwas its gate; another was suspended by a rule that was not among its ancestors, and nor was it\namong that rule's."),
 (C, "direction example (bearing-off-eligible in enabledBy / suspendedBy)",
  "`bearing-off-eligible` is in\n`bearing-off-highest`'s `enabledBy` and in `move-by-pip`'s `suspendedBy`, because once every\nman is home bearing off governs every forward move.",
  "an overtime rule can be in\nthe golden-goal entry's `enabledBy` and in the regulation-clock entry's `suspendedBy`, because\nonce overtime starts it governs play."),
 (C, "repetition example (full-table-suspension named by seven entries)",
  "`full-table-suspension` is named by seven entries, each with the judgement in its `note`.",
  "in one trial map a single suspension was named by seven entries, each with the judgement in\nits `note`."),
 (C, "beyondAdapter modality: 'the one observed case'",
  "`illustration` in the one\nobserved case. Deliberately not a closed vocabulary: one instance is not enough to write\none from, and it can be closed later from evidence.",
  "`illustration`, for\nexample. Deliberately not a closed vocabulary: it can be closed later from evidence."),
 (C, "beyondAdapter locator example (men placed as in Fig. 1)",
  "the\nsentence saying the men are placed as in Fig. 1.",
  "the\nsentence saying the rates are as printed in the table."),
 (C, "beyondAdapter general case (the one illustration; both corpora text)",
  "The general case is worse than the one illustration: a PDF rulebook read as extracted text\nloses exactly the tables a rules engine most needs. No trial has produced that — both\ncorpora were text end to end — and the field does not detect it.",
  "The general case is worse than a single illustration: a PDF rulebook read as extracted text\nloses exactly the tables a rules engine most needs, and the field does not detect it."),
 (C, "absentFrom example terms (doubling, doubling cube, redouble, offer to double)",
  "\"absentFrom\": { \"searched\": [\"doubling\", \"doubling cube\", \"redouble\", \"offer to double\"] }",
  "\"absentFrom\": { \"searched\": [\"sublet\", \"subletting\", \"sublease\", \"underlet\"] }"),
 (C, "absentFrom extent example (\"doubling\" not in Hoyle's backgammon chapter)",
  "\"doubling\" does not occur in Hoyle's backgammon\nchapter and does occur elsewhere in the same volume, so a whole-volume search would refuse a\ntrue absence and teach mappers to write vaguer terms.",
  "a term can be absent from the chapter mapped\nand occur elsewhere in the same volume, so a whole-volume search would refuse a true absence\nand teach mappers to write vaguer terms."),
 (C, "absentFrom locator example (doubling-cube cites apparatus sentence)",
  "for `doubling-cube`, the sentence that enumerates the\napparatus and closes the list.",
  "for an absent subletting rule, the clause that lists\nwhat the tenant may and may not do."),
 (C, "derivedFrom example (hit-pays-single-stake, gammon/backgammon stake quotes)",
  "{ \"id\": \"hit-pays-single-stake\", \"kind\": \"value\", \"scope\": \"in\", \"clarity\": \"clear\",\n  \"derivedFrom\": [\"stake-multiplier\", \"agreed-backgammon-multiple\"], \"dependsOn\": [\"game-value\"],\n  \"status\": \"mapped\", \"note\": \"…\" }\n```\n\nHoyle says a gammon pays *\"double the agreed stake\"* and a backgammon *\"thrice or four times …\nthe amount of the single stake\"*, and never says what a hit pays. That it pays the single stake\nis one step of arithmetic over two stated rules. It used to sit inside `stake-multiplier`,\n`clear`, with nothing to quote.",
  "{ \"id\": \"late-fee-cap-week\", \"kind\": \"value\", \"scope\": \"in\", \"clarity\": \"clear\",\n  \"derivedFrom\": [\"late-fee-rate\", \"late-fee-cap\"], \"dependsOn\": [\"late-fee\"],\n  \"status\": \"mapped\", \"note\": \"…\" }\n```\n\nA lease says a late fee accrues at *\"2% of the month's rent per week\"* and is *\"capped at\n10%\"*, and never says in which week the cap is reached. That it is the fifth is one step of\narithmetic over two stated rules. Put inside `late-fee-rate`, `clear`, it would have nothing to\nquote."),
 (C, "per-rule scope instance (Hints for Play, die-faces, strategy-advice)",
  "The instance: the backgammon map excluded *Hints for Play* wholesale as advice, and inside it\nsits the only authority in the corpus for a die having six faces — *\"all the possible throws\"*,\nfollowed by twenty-one of them, and *n(n+1)/2 = 21* has one positive solution.\n`strategy-advice` declines **the advice**; `die-faces` is `scope: in` and cites the same\nsection. Two entries citing one section, with opposite verdicts, is correct.",
  "Two entries citing one section, with opposite verdicts, is correct."),
 (C, "crossReferences JSON example (as at starting / opening-roll; as in Fig. 1)",
  "{ \"cites\": \"as at starting\", \"resolvedBy\": \"opening-roll\" },\n  { \"cites\": \"as in Fig. 1\", \"unmapped\": \"Fig. 1 is an illustration, not a passage.\" }",
  "{ \"cites\": \"as provided in clause 9\", \"resolvedBy\": \"early-termination\" },\n  { \"cites\": \"as shown in Schedule B\", \"unmapped\": \"Schedule B is a floor plan, not a passage.\" }"),
 (C, "crossReferences limit example (starting-position quotes as shown in {273} Fig. 1)",
  "`starting-position` quotes *\"as shown in\n{273} Fig. 1\"* and the page marker falling inside the phrase hides it,",
  "a page marker falling inside a pointer\nphrase hides it,"),
 (C, "status decoupling instance (must-play-whole-throw)",
  "`must-play-whole-throw` is the instance — the engine implements the compulsion and\ndeclines only where two maximal plays are incomparable, which is neither `declined` nor a\nclean `implemented` under the old coupling.",
  "A fee rule that is built and declines only where two charges fall on one day is the\ninstance, which is neither `declined` nor a clean `implemented` under the old coupling."),
 (C, "tests JSON example (WholeThrowTests)",
  "{ \"test\": \"WholeThrowTests.Where_either_die_alone_can_be_played_but_not_both_the_throw_declines\",\n    \"mutation\": \"Let the engine play the higher die when only one of two is playable; this test went red.\" }",
  "{ \"test\": \"LateFeeTests.Where_two_charges_fall_on_one_day_the_fee_declines\",\n    \"mutation\": \"Let the engine charge the earlier fee when two fall on one day; this test went red.\" }"),
 (C, "26 backgammon entries claimed implemented",
  "26 backgammon entries claimed it in the engine's copy",
  "26 entries of one trial map claimed it in the engine's copy"),
 (C, "one shape of throw",
  "declines one shape of throw from one that declines everything.",
  "declines one shape of input from one that declines everything."),
 (C, "surprising reading example (bearing-off-highest)",
  "`bearing-off-highest` is clear, correct,\nand the opposite of what a modern player expects,",
  "An entry can be clear, correct,\nand the opposite of what a modern reader expects,"),
 (C, "count of mapped/unresolved entries across three maps",
  " — eleven entries across the three maps today —",
  " —"),
 (C, "row 8 example (stake-multiplier as ambiguity)",
  "which is what reading `stake-multiplier` as an ambiguity costs.",
  "which is what reading a delegated choice as an ambiguity costs."),
 (C, "#32 summary (gate suspending seven entries)",
  "a gate that suspends seven\n  entries was named by none of them,",
  "a gate was named by none of\n  the entries it reaches,"),
 (C, "#31 summary (rate the corpus implies)",
  "an entry claimed a rate the\n  corpus implies and never states.",
  "an entry claimed a fact the\n  corpus implies and never states."),
 (C, "#18 summary (thirteen wrong citations)",
  "no citation was checkable and thirteen wrong ones survived a build.",
  "no citation was checkable and wrong ones survived a build."),
 # ---------------- SRD 5.2.1, the corpus under mapping ----------------
 (C, "entry example: an RPG opposed test (dice pool, hits, attacker/defender tie)",
  "\"id\": \"opposed-test-tie\",\n  \"name\": \"Resolving a tie in an opposed test\",\n  \"locator\": { \"sourceId\": \"core-rules\", \"citation\": \"Game Concepts / Tests / printed p. 36\" },",
  "\"id\": \"match-score-tie\",\n  \"name\": \"Resolving a tie on points\",\n  \"locator\": { \"sourceId\": \"core-rules\", \"citation\": \"Competition / Scoring / printed p. 36\" },"),
 (C, "entry example: tie question in hits",
  "\"The text does not say which side prevails when both achieve equal hits.\",\n    \"fate\": \"decision\",\n    \"decision\": \"docs/decisions/0099-opposed-test-tie-break.md\"",
  "\"The text does not say which side prevails when both score equal points.\",\n    \"fate\": \"decision\",\n    \"decision\": \"docs/decisions/0099-match-tie-break.md\""),
 (C, "entry example: dependsOn, evidence and ruleset of the RPG example",
  "\"dependsOn\": [\"simple-test\", \"dice-pool-assembly\"],\n  \"evidence\": \"Compare the hits scored by each side. The side with more hits prevails, and the difference is the margin.\",\n  \"status\": \"implemented\",\n  \"implementedIn\": { \"ruleset\": \"sr6\", \"version\": 4 },",
  "\"dependsOn\": [\"points-scoring\", \"scorecard-totals\"],\n  \"evidence\": \"Compare the points scored by each side. The side with more points prevails, and the difference is the margin.\",\n  \"status\": \"implemented\",\n  \"implementedIn\": { \"ruleset\": \"league\", \"version\": 4 },"),
 (C, "entry example: tie test (defender / attacker)",
  "{ \"test\": \"OpposedTestTieTests.A_tie_goes_to_the_defender\",\n      \"mutation\": \"Awarded ties to the attacker; this test went red.\" }",
  "{ \"test\": \"MatchTieTests.A_tie_goes_to_the_away_side\",\n      \"mutation\": \"Awarded ties to the home side; this test went red.\" }"),
 (C, "entry example note (one more hit)",
  "the boundary where one side has one more hit.",
  "the boundary where one side has one more point."),
 (M, "corpus id example names this corpus (srd-5.2.1)",
  "A stable identifier — `srd-5.2.1`, `cfr-26`, `core-rules`.",
  "A stable identifier — `tax-code-2024`, `cfr-26`, `core-rules`."),
 (M, "boundary-policy example names a CC-BY SRD",
  "A CC-BY SRD or a public-domain statute is `pin-in-repo`",
  "A CC-BY rulebook or a public-domain statute is `pin-in-repo`"),
 (M, "value examples: a creature's statistics",
  "a list of conditions, a creature's statistics, a\ncontribution limit for a given year.",
  "a list of conditions, a vehicle's specifications, a\ncontribution limit for a given year."),
 (M, "operation examples: how damage applies",
  "how a test resolves, how damage applies, how a limit is\ncomputed.",
  "how a test resolves, how a penalty applies, how a limit is\ncomputed."),
 (M, "0010 example: whether a person was under cover (Cover is a rule in this slice)",
  "whether it was raining, whether a person was under\ncover —",
  "whether it was raining, whether a road was\nclosed —"),
 (M, "dependency example: damage after attack",
  "Damage after\n  attack; the limit after the table it reads.",
  "The invoice\n  after the order; the limit after the table it reads."),
 (C, "boundary-policy history names the SRD",
  "one commits its extracted corpus because the\nSRD is CC-BY,",
  "one commits its extracted corpus because its\nlicence is CC-BY,"),
 (C, "#20 summary (number of faces on a die)",
  "`scope: out` applied to a\n  section cost the map the number of faces on a die.",
  "`scope: out` applied to a\n  section cost the map a fact stated inside it."),
]


def pattern(old):
    parts = re.split(r"\s+", old.strip())
    return re.compile(r"\s+".join(re.escape(p) for p in parts))


texts = {f: (SRC / "docs" / f).read_text(encoding="utf-8") for f in (M, C)}
log = ["# Redactions", "",
       "Source: docs/method.md and docs/corpus-map.md at the commit named in README.md. Every edit "
       "below matched exactly once (whitespace-insensitive).", "", "## Content edits", ""]
for f, why, old, new in EDITS:
    pat = pattern(old)
    hits = pat.findall(texts[f])
    if len(hits) != 1:
        sys.exit(f"{f}: {why}: {len(hits)} matches")
    line = texts[f][: pat.search(texts[f]).start()].count("\n") + 1
    texts[f] = pat.sub(lambda _m: new, texts[f], count=1)
    log.append(f"- {f} L{line}: {why}")

# Links the mapper cannot follow (decision records, issues, examples) become plain text.
link_log = {}
def plain(m):
    text, target = m.group(1), m.group(2)
    if target.startswith(("method.md", "corpus-map.md")):
        return m.group(0)
    link_log.setdefault(target.split("#")[0], 0)
    link_log[target.split("#")[0]] += 1
    return text
for f in texts:
    texts[f] = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", plain, texts[f])

log += ["", "## Links made plain text", "",
        "Every markdown link not to method.md or corpus-map.md (decision records, issues, example "
        "directories) was replaced by its link text; the mapper has none of those files.", ""]
for t, n in sorted(link_log.items()):
    log.append(f"- {t} ({n})")

OUT.mkdir(parents=True, exist_ok=True)
for f, t in texts.items():
    (OUT / f).write_text(t, encoding="utf-8")
LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
print(f"{len(EDITS)} edits, {sum(link_log.values())} links made plain")
