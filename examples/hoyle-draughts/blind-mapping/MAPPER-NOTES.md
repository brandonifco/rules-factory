# Blind mapper notes

I read SLICE.md first, then method.md and corpus-map.md, the manifest, and the complete DRAUGHTS article after {427} and before {447}. I followed only the article's footnote calls 107 and 108 into the collected footnotes. I used no other mapper's work, game reference, network source, git operation, or file outside this directory.

The SHA-256 of hoyle.txt matches the required baseline:
5d505fa9f6202340eb55313b8ef607b816087a860d3d51b1bf92b5f65240645e.
The derivation is gutenberg-plain-text-including-boilerplate. This is a fixed edition; I supplied no asOf date. The manifest was left unchanged.

## What the map contains

blind-map.json has exactly the five contracted envelope fields. Its extent remains printed pages 427–446. There are 96 entries: 77 in scope and 19 out of scope; 42 values, 51 operations and 3 assertions. Fifteen entries have unresolved ambiguities. No entry claims implementation or tests of a game engine.

I mapped the apparatus and vocabulary as well as move procedures: counts, side names and colours, board orientation, placement, numbering, the crown-head, promotion, King directions, the draw definition, match colour selection, timing, handling, forfeitures, huffing, movement and captures. The three assertions are the lot winner's bounded colour choice, the opponent's bounded response to an own piece being removed, and the player's bounded election among huffing, compelling a take and leaving the piece. These are choices the text expressly supplies; they are not guessed adjudication standards.

I separated stated quantities from the procedures consuming them where useful, including the timing durations, ordinary step distance and forty-own-move count. Relations in dependsOn concern what must be implemented to resolve an entry; enabledBy records setup, promotion, the huff election and the stronger-side notice procedure where those rules open the operation. No implicit cancellation of the general timing provision by the one-way-taking provision was asserted.

All fifteen named openings are defining values. Their sequences and printed move counts remain exact, including the compact punctuation in Old Fourteenth. Their names do not impose a required opening on every game.

The named First, Second, Third and Fourth Positions are also defining data: the article identifies them as four recurring named situations and then supplies their grids. I retained each complete literal grid as a value. I declined the following result captions and solution lines as worked examples. This is a decomposition choice: the identities of the named positions are data; the particular winning or drawing lines illustrate play rather than prescribe it. The King-direction sentence repeated on p. 431 has its own value entry, rather than being left unaccounted for because p. 429 already mentions the directions.

## Adapter and footnote boundaries

The board diagrams are ASCII text in the pinned corpus. Their cell boundaries, side labels, numbers and piece letters can be read by the declared plain-text adapter. I therefore did not use beyondAdapter, pretend the diagrams were absent, or obtain images from another source. Fig. 2 supplies eight-by-eight geometry and the complete thirty-two-square numbering; sixty-four squares alone would not establish the board's shape. Every diagram-data entry asks for verification of the whole grid.

The doubled B and W labels in the named positions are read together with the same-colour stacking instruction and the explicitly described Two Kings to One illustration. I did not silently add an independent diagram legend from game knowledge. The original diagrams and labels stay in the evidence so that this reading can be reviewed.

Footnote 107 explains the distinction between operative black-square placement and the white-square convention used in treatise diagrams. It also describes historical English practice. I did not turn that historical account into an additional operative choice of board orientation.

Footnote 108 states two distinct qualifications: a player may be huffed for failing to complete the adopted capture, while a player choosing between two captures need not choose the larger one. Both are recorded as separate entries with the full footnote as evidence.

The collected footnotes occur after the last printed page, with {475} as their last preceding marker. Under the supplied positional locator rule, their true citations are p. 475, not the pages carrying their calls. Because in-scope evidence must be inside the assigned extent, the three footnote entries are scope out, status declined, with explicit boundary reasons. The in-slice callers resolve to them, and operative dependencies name them where they modify a rule. This records that the footnotes were read and that a consumer bounded strictly to this extent reaches them as out-of-scope dependencies. It does not misclassify them as an unadmitted corpus, unreadable illustrations or ambiguous merely because of their location.

## Questions left unresolved

All fifteen questions use fate unresolved; I made no decision records or house rulings.

- initial-colour-lots: the casting apparatus, draw distribution, count and handling of ties are unspecified. The entry declares Lots as the draw source and affectsDraws true, without inventing dice or a seeded algorithm.
- ordinary-time-forfeit: the five-minute clock's starting event is unstated.
- forced-take-time-forfeit: the one-minute clock's starting/reset event and the consequence of omitting a mandatory Time call are unstated.
- unplayable-touch-penalty: the reference to the preceding law does not say whether it imports only forfeiture or also that law's notice condition and exception.
- improper-move-forfeit: false or improper moves are not exhaustively distinguished from missed captures, for which three different remedies are expressly offered.
- huff-removal: when several pieces could have taken, the number of eligible pieces removable by a single huff is not expressly fixed.
- compelled-take: the board-restoration and selection procedure for enforcing a missed or unfinished take is unspecified.
- king-movement: the exception for promoted men and the permission to move backwards or forwards do not unambiguously settle the King's travel distance and surviving ordinary-movement restrictions.
- promotion-capture-continuation: arrival fixes promotion, but continuation or termination of that same capturing play is unstated.
- stronger-side-assessment: no determinate strength test or authoritative assessor/notice initiator is named.
- decided-advantage: no determinate success criterion or requirement that the advantage be newly acquired since notice is supplied.
- forty-move-draw: the text does not settle what happens after the advantage alternative is satisfied, including discharge, reset or fresh notice.
- man-movement: ordinary noncapture destination occupancy is not expressly restricted, although capture landing vacancy is explicit.
- single-capture: a contiguous opponent and vacant landing behind it are specified, but an exclusive immediately-beyond landing distance is not expressly supplied. The example demonstrates one landing, not a maximum range for every case.
- multiple-capture: changing diagonals, the timing of removal within a chain and revisiting earlier squares are not settled by the general wording.

These are gaps or readings I could not settle from the slice, not assertions delegated to a named adjudicator. In particular, I did not replace relative strength or decided advantage with a count of men. Worked examples may suggest familiar mechanics, but a demonstrated move is not an exhaustive prohibition of every unillustrated alternative. I recorded no formal ambiguity bounds: the contract's available duration dimension does not encode these spatial or case-pattern examples.

No absentFrom entries were invented for features remembered from other versions of the game. No derived rule was needed to carry the stated content. I recorded no conflict slug: the two provisions most likely to look inconsistent are explicitly qualified by the diagram footnote or give different timing conditions; the remaining uncertainties are not two demonstrably incompatible stated answers.

## Declines and other text read

The nineteen out-of-scope entries comprise the three footnote boundary entries, eight advice paragraphs, the Two Kings to One and Three Kings to Two instructional examples, four elementary-position solution examples, the practical opening/capture example as a particular line, and the final bibliography.

The general-advice paragraphs were read separately. Centralisation, exchanges, learning pace, choice of opponents, simplification, concentration, attention to opposing plans and study recommendations are coaching. I also declined the imperative about touching board squares as playing manners in its sentence with forming an off-hand playing habit; it does not state the touch-piece penalty. The exhortation to take quickly supplies no replacement timing limit. The one-man-ahead assessment supplies no automatic game-ending rule.

The practical capture illustration is not discarded wholesale. Its explicit removal of a captured piece and its explanation that huffing does not restore the other piece moved are separate in-scope procedures. Its particular opening sequence remains an example. Similarly, the named elementary grids are data while their solution lines are examples. I read all columns and all variations, including First Position's return to S, Third Position's A continuation, and both Fourth Position starting-player alternatives. I did not convert the column-interleaved solution text into an asserted new move ordering.

The unquoted residue was reviewed after the quotation check. It consists of headings, page markers, the introductory rule-list label, the Longfellow epigraph, opening-name histories and explanations, the recommendation to study the elementary positions, and the closing ornament. These produced no additional operative entries. In particular:

- The Bristol, Fife, Glasgow, Laird and Lady, Maid of the Mill, Old Fourteenth and Souter stories are naming/publication history.
- Cross, Defiance, Second Double Corner and Single Corner have explanatory naming rationales. Defiance's reference to Fife describes why the opening is named; it adds no rule requiring a player to prevent that formation.
- Whilter/Wholter's Scottish meaning is etymology, not an additional mechanically defined opening sequence.
- The final recommendations do not incorporate the contents of any external work into the rules being mapped. I did not follow those recommendations or amend the manifest's empty external-authority list.

## Pointer mechanisms found

The manifest declares no pointerPhrases. Following SLICE.md, I recorded the phrases here rather than rewriting the admission manifest. Literal forms below are verbatim after whitespace collapse:

- Footnote calls: [107] and [108].
- Backward law reference: according to the preceding law.
- Diagram pointers: The above diagram (Fig. 1), Fig. 2, as shown in Fig. 1, and (see Fig. 3).
- Return to the initial arrangement: as for a game.
- A backward procedural continuation: This done.
- Forward study pointer: (see _post_), accompanied by the First, Second, Third and Fourth names.
- Forward example pointer: the position following.
- Backward example pointer: as we have seen.
- Solution branches: V.1--, V.2--, V.3--, V.4--, A-- and the paired A label; S-- marks the trunk return target. The normalized First Position table interleaves the continuation words with move columns, so the anchored cross-reference retains those intervening tokens.
- Further-reading pointer: see the article, followed by the named external publication. Other named publications in that paragraph are additional recommendations.

Defined vocabulary also points by naming: men, first side, second side, Huff/Blow, King/Kings, Draw, crown-head, the fifteen opening names and the named positions. I did not treat a figure's own caption as a pointer to an unseen rule. Cross-reference declarations either resolve to entries or explain that the reference is to illustrative material included in the same declined span or an external reading recommendation. There are 48 declarations. The missing-capture footnote has two target entries because it states two distinct qualifications.

## Verification and limits

build_blind_map.py constructs the deliverable from bounded, whitespace-normalized spans of the pinned file. It preserves punctuation, case, emphasis marks, diagram cells and internal page markers. check_blind_map.py independently reloads the JSON and source, checks the hash and five envelope fields, and resolves every full evidence span to its cited page. It also checks unique IDs, all dependency/gate/reference targets, reference and definition anchors, assertion attribution anchors, question anchors, draw anchors, dependency acyclicity and page reach. Every check passed. All twenty assigned pages are reached; the only citations beyond the extent are the three deliberately out-of-scope p. 475 footnote entries.

The manual completion sweeps were: every article paragraph and diagram; every opening and named position; all footnote calls; forward/backward/diagram/variation pointers; defined terms and apparently undefined operative conditions; explicit gates and exceptions; every unquoted residue run; and exact quotations and page locations. No supplied mapping-protocol.json, formal mapper command, JSON Schema file or factory locator checker was used. These are the slice deliverables, not a claim that a full publishable map package, formal mapping inventory or independent semantic adjudication has been produced. The scripts verify where the words are; they cannot prove my interpretation of them.
