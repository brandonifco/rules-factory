# Hoyle's Draughts, pp. 427–446 — a second slice of the Hoyle corpus

Not a numbered trial. A trial exists to change the method ([examples/README.md](../README.md)),
and this run was chosen to build an engine, not to break anything
([#705](https://github.com/brandonifco/rules-factory/issues/705)). It maps the DRAUGHTS article of
*Hoyle's Games Modernized* (1909), the corpus the [backgammon trial](../hoyle-backgammon/) admitted,
over the same pinned `hoyle.txt`. The corpus is committed once, under that trial, and this map's
manifest points at it.

| | |
|---|---|
| Corpus | `hoyle-1909`, Project Gutenberg eBook 39445, public domain; the same pinned bytes as [../hoyle-backgammon/](../hoyle-backgammon/) |
| Extent | `{"unit": "page", "from": 427, "to": 446}`, the whole article |
| Entries | 52 — 39 in scope, 13 declined |
| Kinds | 36 `operation`, 13 `value`, 3 `assertion` (the colour the lot's winner chooses, the opponent's choice when a player removes his own piece, the player's choice to huff, compel or let the piece remain) |
| Ambiguous | 9 of 39 in scope (23%): eight unresolved, one decided by [0088](../../docs/decisions/0088-a-huff-is-read-with-the-footnote-that-the-passage-calls.md) |
| Relations | 66 `dependsOn` edges, no cycle; 8 entries gated by `enabledBy` or `suspendedBy` |
| Pointers | 10 `crossReferences`, one `unmapped` |
| Draws | 1 entry, `lots-for-colour`; the corpus is `randomness: seeded` |
| Absences | 2 `absentFrom`: a draw by agreement and a draw by repetition |
| Inventory | 106 units, 42 reached, 64 rejected, 0 unaccounted |
| Coverage | 39% of the extent quoted; no floor declared |
| Review | blind second mapping by OpenAI Codex, 211 flags adjudicated ([review.json](review.json), [blind-mapping/](blind-mapping/)) |
| Package | `RulesFactory.Maps.HoyleDraughts` 1.0.0, `held` from publication ([map-package.json](map-package.json), [0073](../../docs/decisions/0073-a-map-held-from-publication-declares-why-in-the-file-that-declares-its-version.md)) |

## What the corpus does not settle

The article's rules are on pp. 427–432; the rest is advice, the names of fifteen openings, and six
end-game studies, all declined. Eight questions the rules leave open are recorded unresolved, and an
engine built from this map declines each one, by name, where it arises:

| Entry | The open question |
|---|---|
| `compel-the-take` | The player may "compel the take", and the corpus never says what that does to the move already made, or which take is compelled when several were open |
| `becomes-king` | Whether a man that reaches the far line by taking may go on taking, as a King, in the same play |
| `loss-when-none-can-be-played` | Whether "the person whose side is brought to this state loses" is judged at once, or only when that side is to play |
| `forty-move-limit` | What "a decided advantage" is, who judges it, and who decides a side "appears stronger" |
| `king-movement` | Whether a King's ordinary move may cross more than one square |
| `multiple-capture` | Whether a capturing piece may land again on a square it already stood on in the same capture |
| `time-limit` | Whether the further minute runs from the call of Time or from the end of the five minutes |
| `touched-piece-must-be-played` | Whether "penalised according to the preceding law" brings in that law's condition about intimation |

The first two were found by both mappers independently. The last four were the blind mapping's, and
the adjudication upheld them.

## What this slice found

### A rule printed in a footnote the page extent cannot reach

p. 429 calls footnote 108, which answers the huff's hardest case: a player who stops a capture
short of what the same play could take is liable to the huff, and one who takes by the play that
takes fewer men is not. The Gutenberg edition prints every footnote together after the book's last
page, so the footnote's page marker is p. 475, and a page extent is a range: one reaching p. 475
would claim every chapter from Draughts to the end of the book. Both mappers, working apart, did
the same thing: the footnote is a `scope: out` entry citing p. 475, and the entry that needs it
names it in `dependsOn`. [0088](../../docs/decisions/0088-a-huff-is-read-with-the-footnote-that-the-passage-calls.md)
then rules that `huff-defined` is implemented with the footnote's answer. Whether an extent should
be able to reach a footnote its passage calls is a contract question, and it is not decided here.

### Every entry has a locator of its own

The rules on pp. 427–432 print no headings, so a citation in the backgammon map's form,
`DRAUGHTS / p. 429`, was shared by thirteen entries in the first mapping. An engine names a decline by its entry's
locator, and its acceptance harness (0078) refuses an allowlisted reading whose locator another
entry also cites. Each citation's section slot therefore carries the passage's own words,
`DRAUGHTS / compel the take / p. 429`. The checkers read only the page.

### The figures are text

Fig. 1 and Fig. 2 are printed into this edition as character grids, not as image placeholders as in
the backgammon chapter. The protocol declares illustrations `readable` for this map, and
`square-numbering` quotes Fig. 2 whole: it is the only statement of which square is which number,
and every move the corpus prints is written in those numbers.

### The huff makes a missed take a move, not a false move

p. 429 forfeits the game for "a false or improper move". p. 432's worked example has Black miss a
take and be "liable to be huffed", which only makes sense if the move stands. The map holds that
example as `not-taking-is-liable-to-huff`, in scope, because it is the only passage that says so,
and `false-move-forfeits`' note says why a missed take is not one. The adjudication upheld the
reading against the blind map's doubt.

## The blind second mapping

Run by OpenAI Codex (`codex exec`, workspace-write, no network) in a bundle outside the repository
holding the pinned corpus, the manifest without its `pointerPhrases`, `SLICE.md`, and `method.md`
and `corpus-map.md` as staged by `mapper stage` ([blind-mapping/staging.json](blind-mapping/staging.json),
[REDACTIONS.md](blind-mapping/REDACTIONS.md)): 45 edits replacing the backgammon map's entry ids,
which are this corpus's vocabulary. Its account is [MAPPER-NOTES.md](blind-mapping/MAPPER-NOTES.md);
its scripts are committed as it left them, with paths into the bundle. [compare.py](blind-mapping/compare.py)
is the backgammon slice's comparator with only the reference changed, and read this map at
`0f613b8`. The 211 flags were answered by an adjudicator that mapped neither side, a fresh agent
given both maps, the corpus and the contract and none of either mapper's reasoning:
136 not a disagreement, 55 reference right, 12 blind right, 8 unsettled.

What it did not catch: two mappers who share a misreading agree, and agreement is silent. Both
read the openings and the named positions as out of scope, and both left `compel-the-take` open.

## Files

| File | What it is |
|---|---|
| [corpus-map.json](corpus-map.json) | the map |
| [corpus-manifest.json](corpus-manifest.json) | the corpus, pinned by hash to the copy in [../hoyle-backgammon/](../hoyle-backgammon/), and the phrases this article points with |
| [mapping-protocol.json](mapping-protocol.json) | how this corpus is read here, and the sweeps the walk owes |
| [mapping-inventory.json](mapping-inventory.json) | the 64 units the walk examined and produced no entry for |
| [review.json](review.json) | the blind-second-mapping review of these bytes |
| [blind-mapping/](blind-mapping/) | the staged inputs, the blind map, the comparator, its results and the adjudication |
| [CORPUS-LICENCE.txt](CORPUS-LICENCE.txt) | the terms, as for the backgammon slice |
| [map-package.json](map-package.json) | version 1.0.0, held: publishing cannot be undone, so the tag is a person's decision (AGENTS.md §5) |
