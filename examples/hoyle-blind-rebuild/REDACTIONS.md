# Redactions in the blind brief, for the owner's review

Written by `build-brief.py assemble --review`. **Not part of the brief: it quotes what was removed, test names included.** An implementer may not read it.

Brief MANIFEST.json sha256 `da6726e61c3cbb3d8c179eccde0930c61aca082d5ac6a4388789a3dc19de8dcc`. 26 redaction(s). A block is a paragraph, a top-level list item with what it nests, or a fenced block; a line is one documentation line of the API contract. Findings: `test-name` (a hand-written test method or class), `test-literal` (a number or hash a test holds and no allowed source does), `copied-text` (eight words from a test, an engine statement or comment, or mutation text). In the removed text, every markdown link's `](` is written `] (` so that this file's links are not checked as links; nothing else is changed.

## 1. `inputs/factory-docs/docs/corpus-map.md`, block 309

- Reasons: test-name
- Found: test-name `WholeThrowTests`
- Removed text sha256: `1d1810edd96459884f7473c4dac91c31763dab4d56dcd6cee261158a3f0e0b54`
- Owner's verdict: 

````text
```json
"tests": [
  { "test": "WholeThrowTests.Where_either_die_alone_can_be_played_but_not_both_the_throw_declines",
    "mutation": "Let the engine play the higher die when only one of two is playable; this test went red." }
]
```
````

## 2. `inputs/factory-docs/docs/decisions/0006-the-general-rule-governs-entry-and-full-means-adversely-full.md`, block 76

- Reasons: test-name
- Found: test-name `DeterminismTests`; test-name `Two_players_suspended_against_each_other_is_an_interaction_no_entry_covers`
- Removed text sha256: `534683d2444e68b8dadf9320432dc622605da4c70eb52224aa7767455052bd67`
- Owner's verdict: 

```text
It is nonetheless reachable, because `Game.Play` demands an `AssertedPosition` and a caller
may assert one — a mid-game study, a replayed log, a position from another engine. Fifteen men
a side permits it: a man up and twelve men making all six points of one's own home table, for
each player. `DeterminismTests.Two_players_suspended_against_each_other_is_an_interaction_no_entry_covers`
constructs exactly that and reaches the branch. So the branch is not dead, and the honest
statement of what it is — unreachable by play under this decision, reachable by assertion — now
sits next to it in `Game.Play` instead of the bare "which fifteen men a side does permit" that
said neither half.
```

## 3. `inputs/factory-docs/docs/decisions/0006-the-general-rule-governs-entry-and-full-means-adversely-full.md`, block 82

- Reasons: test-name
- Found: test-name `EnterFromBarTests`; test-name `FullTableSuspensionTests`
- Removed text sha256: `ec23962c968ce1dc4c80b0d92f4f611b17843a1fa52f94a69fbddb395c26a191`
- Owner's verdict: 

```text
**The decision is falsifiable and the map now says where.** Two tests make the reading
observable — one entering on a point the player's own men hold in the adversary's home table,
one against a home table whose six points are all occupied but one of them by the entering
player's own men, which suspends nobody. Under the strict reading both fail. Before this,
`EnterFromBarTests` and `FullTableSuspensionTests` both avoided the case, which is why the
choice was invisible: every test in the repository passed under either reading.
```

## 4. `inputs/factory-docs/docs/decisions/0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md`, block 24

- Reasons: test-name
- Found: test-name `A_number_left_after_the_last_man_comes_home_bears_off_naming_the_owners_ruling`; test-name `BearingOffEligibilityTests`; test-name `MustPlayWholeThrowEntryPointTests`
- Removed text sha256: `96a7d7cc02ba09328fffb6939aba2dd8aa1706460479987f625ac1b0618f5b9d`
- Owner's verdict: 

````text
```json
"bearing-off-eligible": {
  "status": "implemented",
  "implementedIn": { "ruleset": "hoyle-1909-backgammon", "version": 5 },
  "tests": [ { "test": "…", "mutation": "…" }, … ],
  "rulings": [
    {
      "id": "bearing-off-eligible/2",
      "span": "Nor does it say when within a throw the stage begins. If a man played with … so it does not decide the case.",
      "answer": "Yes: once a player's first number brings his last man home, the number left bears off.",
      "ruledBy": "Brandon",
      "ruledOn": "2026-09-15",
      "record": "docs/decisions/0009-owner-rulings-are-ruleset-version-five.md",
      "tests": ["MustPlayWholeThrowEntryPointTests.A_number_left_after_the_last_man_comes_home_bears_off_naming_the_owners_ruling"]
    }
  ],
  "declines": [
    {
      "span": "The stage begins 'when either player … must first bring every man home again.",
      "tests": ["BearingOffEligibilityTests.A_man_re_entered_after_bearing_off_began_is_the_case_the_corpus_does_not_settle"]
    }
  ]
}
```
````

## 5. `engine/api-contract.md`, line 558

- Reasons: test-name
- Found: test-name `PlayEnumerationTests`
- Removed text sha256: `49f4f963df5098d16dcf66a4b30061010b477a25d9331927765366c9185c92ec`
- Owner's verdict: 

```text
      /// No hash-set or dictionary iteration order reaches the list. `PlayEnumerationTests` pins the result for six-trois and double deuces from the starting position.
```

## 6. `engine/decisions/0001-the-dice-pack-is-its-own-project.md`, block 16

- Reasons: test-name
- Found: test-name `PackIsRulesetAgnosticTests`
- Removed text sha256: `2229046bbc6fdafafc292e3b239878a362f409404a2a0b697233309fa03375c8`
- Owner's verdict: 

```text
**Agnosticism is a claim about a boundary, and a folder has no boundary.** In a folder,
`Die` can reference `Position`, `DiceThrow` can grow a `PlayedTwiceOver` property, and
nothing fails. Nobody plans to do that; the point is that the discipline is unverifiable, and
an unverifiable claim about what code does not contain is worth about as much as a comment.
As a project the claim is a property of the reference graph: `Tabletop.Dice` cannot see
`HoyleBackgammon`, and `PackIsRulesetAgnosticTests` checks both halves — that the pack
references no engine, and that no public name in it is ruleset vocabulary.
```

## 7. `engine/decisions/0004-map-3-0-0-is-ruleset-version-two.md`, block 6

- Reasons: test-name
- Found: test-name `IdentityTests`
- Removed text sha256: `f4703b5832d7148a43899ed549d5d0a63eff2c407ec3471c73d453d97681f3dd`
- Owner's verdict: 

```text
`Game.Identity` decides whether two recorded games are comparable. It names a ruleset, a replay
schema, the pinned corpus and a generator. `IdentityTests` pins each one to a literal and says a
change to any of them is a decision to record here.
```

## 8. `engine/decisions/0005-map-4-0-0-is-ruleset-version-three.md`, block 26

- Reasons: test-name
- Found: test-name `A_man_in_the_winners_home_table_makes_it_a_backgammon`; test-name `GameValueTests`
- Removed text sha256: `102d95e0d1e070cecc5957704454869043634c59553540ad030013e7feae2b93`
- Owner's verdict: 

```text
- `GameValueTests.A_man_in_the_winners_home_table_makes_it_a_backgammon` now uses a loser with two
  men off, who is a backgammon and nothing else. The loser it used to use is
  `GameValueTests.A_man_in_the_winners_home_table_before_bearing_off_is_both_a_gammon_and_a_backgammon`,
  which holds the decline.
```

## 9. `engine/decisions/0006-a-game-record-carries-its-identity-and-serialises-itself.md`, block 6

- Reasons: test-name
- Found: test-name `SeededGameReplayTests`
- Removed text sha256: `710118561e0f51c5717dae98090fab873ab18c65e09184153ba50bc8dd8a5fac`
- Owner's verdict: 

```text
The end-to-end tests of PR #11 found that a `GameRecord` could not be compared with another one
on its own. It held the game (start, opening roll, turns, winner, value, next opener) and nothing
that said which engine played it. `Game.Identity` had the ruleset and the replay schema, but no
map version; that was reachable only by parsing `EngineProvenance.ReadBytes()`. And the record had
no byte form, so `SeededGameReplayTests` built its own line rendering out of public members and
hashed that. Two tools hashing the same game would each have had to invent the same rendering.
```

## 10. `engine/decisions/0006-a-game-record-carries-its-identity-and-serialises-itself.md`, block 27

- Reasons: test-name
- Found: test-name `SeededGameReplayTests`; test-name `The_canonical_serialisation_is_rfc_8785_json_of_every_field_of_the_record`
- Removed text sha256: `2c2cb2dbc77e5bdc378267572639822e842463d832ab7dee36ae851c37a8ed84`
- Owner's verdict: 

```text
`POSITION` is `{ "Black": [26 ints], "White": [26 ints] }`: each player's men by his own pip,
index 0 borne off, 1 to 24 the points, 25 the bar. A turn whose player was wholly suspended has
`"thrown": null` and `"moves": null`. A turn where nothing could be played has `"moves": []`.
Enum values are their C# names, and a move's `authority` is its map entry id (`move-by-pip`,
`enter-from-bar`, ...). `SeededGameReplayTests.The_canonical_serialisation_is_rfc_8785_json_of_every_field_of_the_record`
spells out one record byte for byte.
```

## 11. `engine/decisions/0006-a-game-record-carries-its-identity-and-serialises-itself.md`, block 35

- Reasons: test-name
- Found: test-name `SeededGameReplayTests`
- Removed text sha256: `bdc21287d60585548c8212a76a4bf2bff28e328b992d8b1bd1448d1aeea1f31b`
- Owner's verdict: 

```text
- `SeededGameReplayTests` hashes `ToCanonicalJson()`, and its pinned SHA-256 moves from
  `606eb92458af7754b365c76b3d3eba436cd919a2c7db4d1c593b9a65e8500b9a` to
  `878936f1b49d970059f7231cecd9feb80ae93d27ea77d2cc8b5498100604da3d`, only because the bytes
  moved. The test no longer reads the provenance to build a rendering. It still reads it once, to
  check that the record's `Map` is the one the provenance names.
```

## 12. `engine/decisions/0007-an-equivalent-order-is-offered-once-until-the-map-says-otherwise.md`, block 35

- Reasons: test-name
- Found: test-name `MustPlayWholeThrowEntryPointTests`
- Removed text sha256: `554ca4b635ef194125fcf0f8d2bf1edf404a3af4b8db629ba2531fafac7047c6`
- Owner's verdict: 

```text
- `MustPlayWholeThrowEntryPointTests.Two_orders_reaching_the_same_position_are_offered_once_though_their_authorities_differ`
  pins the behaviour through the public surface. It asserts the offered order and its authorities.
  Through `EntryPoints.MoveByPip`, it also asserts that the other order is legal move by move,
  under `move-by-pip` twice, and reaches the same position.
```

## 13. `engine/decisions/0008-map-6-0-0-is-ruleset-version-four.md`, block 39

- Reasons: test-literal
- Found: test-literal `20260900`
- Removed text sha256: `0fc14030938622559ea71d5eb7b9a97742c39b345d032fe45342d26482744e24`
- Owner's verdict: 

```text
- A throw that brings the player's last man home with a number left now declines wherever it is
  played. In a game played to the end that is the usual case, not an edge: of the hundred seeds
  from 20260900, 8 games finish with the first play always taken and 3 with the middle play taken.
  Under version 3 they all finished. A tool comparing recorded games must refuse to compare a
  version 3 record with a version 4 one.
```

## 14. `engine/decisions/0008-map-6-0-0-is-ruleset-version-four.md`, block 40

- Reasons: test-literal, test-name
- Found: test-literal `20260905`; test-literal `20260913`; test-literal `20260914`; test-literal `20260921`; test-literal `20260965`; test-name `DeterminismTests`; test-name `PlayerCountTests`; test-name `SeededGameReplayTests`
- Removed text sha256: `e68a10e420de4a51b7d69da126e3ccb0aaa710ea5f1a6a15505e09fe36826147`
- Owner's verdict: 

```text
- The tests that played a game through move to seeds that still finish:
  `DeterminismTests` and `PlayerCountTests` from 20260913 to 20260905 (20260921 for the other
  seed, which was 1), and `SeededGameReplayTests` from 20260914 to 20260965, with its hash re-pinned.
  `DeterminismTests.A_game_that_finished_under_ruleset_three_declines_citing_page_275` keeps the old
  seed and holds its decline.
```

## 15. `engine/decisions/0008-map-6-0-0-is-ruleset-version-four.md`, block 41

- Reasons: test-name
- Found: test-name `MustPlayWholeThrowEntryPointTests`
- Removed text sha256: `09ee0976997afcc2df99abed02be55c565246e65296c7ef528acd86c540c63c5`
- Owner's verdict: 

```text
- `MustPlayWholeThrowEntryPointTests.Two_orders_reaching_the_same_position_are_offered_once_though_their_authorities_differ`,
  which pinned 0007's behaviour, is replaced by
  `Two_orders_reaching_the_same_position_under_different_rules_decline_citing_page_275`. It still
  shows both orders move by move through `EntryPoints.MoveByPip`, under different authorities.
  `A_number_left_after_the_last_man_comes_home_declines_citing_bearing_off_eligible` holds the second
  decline, and that a throw whose last number brings the man home still resolves.
```

## 16. `engine/decisions/0008-map-6-0-0-is-ruleset-version-four.md`, block 42

- Reasons: test-name
- Found: test-name `WholeThrowTests`
- Removed text sha256: `e01448c67fa3bed0cd8d53bd2d220dbe85b0da416d0f41f70a902074fe0a6fb8`
- Owner's verdict: 

```text
- `WholeThrowTests.The_rule_declines_in_exactly_one_shape_either_die_alone_playable_but_not_both`
  counts only the first question's decline, told apart from the second by what the engine attempted,
  since both cite `must-play-whole-throw`.
```

## 17. `engine/decisions/0009-owner-rulings-are-ruleset-version-five.md`, block 13

- Reasons: test-literal
- Found: test-literal `20260900`
- Removed text sha256: `35511252cac9294e39242e9346f8db28074d645f66810d8714cd5525f68f4cc9`
- Owner's verdict: 

```text
Ruleset version 4 declined both ([0008] (0008-map-6-0-0-is-ruleset-version-four.md)). Most games
played to the end reach one of them: 8 of the hundred seeds from 20260900 finished with the first
play always taken, and 3 with the middle play taken.
```

## 18. `engine/decisions/0009-owner-rulings-are-ruleset-version-five.md`, block 32

- Reasons: test-name
- Found: test-name `MapCorrespondenceTests`
- Removed text sha256: `72079bce2d48902d546cb4b878b2dc717e25982ee3b6fecf2b6d31debcdfdc61`
- Owner's verdict: 

```text
- **Nothing refuses it either.** Correspondence row 6 predicts `RequiresInterpretation` for an entry
  whose fate is `unresolved`. Since 0005 C that means "declines for at least one input", and the
  declining case ships a test. Both entries still decline their first parts, and each names that
  decline's test. The generated `CorrespondenceTests` check that an `implemented` entry has a
  handler; they do not check which inputs decline. `check-map.py --phase consumer` reads the merged
  map, not runtime behaviour. The engine's own `MapCorrespondenceTests` require that every entry
  predicting `RequiresInterpretation` has a code path returning it, and both still do. So
  `factory verify` and the gate pass an engine that answers a case the question names.
```

## 19. `engine/decisions/0009-owner-rulings-are-ruleset-version-five.md`, block 52

- Reasons: test-literal
- Found: test-literal `20260900`
- Removed text sha256: `154b893cd35a613c6bd75e63b155c484135d59d4dc11cbeaffe6bc767088223d`
- Owner's verdict: 

```text
- **Games finish again as they did under version 3.** Over the hundred seeds from 20260900, 67 finish
  with the first play always taken (59 of them name a ruling on at least one turn), and 33 with the
  middle play taken and the opening throw adopted (30 name one). Under version 4 the figures were 8
  and 3. The games are move for move those of version 3: the same finish counts, lengths and results.
  The declines that remain are the first parts, and `game-value`'s overlap. A tool comparing recorded
  games must refuse to compare a version 5 record with a version 4 one, and a schema 3 record with a
  schema 2 one.
```

## 20. `engine/decisions/0009-owner-rulings-are-ruleset-version-five.md`, block 53

- Reasons: test-literal, test-name
- Found: test-literal `20260913`; test-literal `20260914`; test-name `A_game_version_four_declined_finishes_and_names_the_owners_rulings_it_relied_on`; test-name `DeterminismTests`; test-name `PlayerCountTests`; test-name `SeededGameReplayTests`
- Removed text sha256: `cd3732deb0060722931acd9ee832ac75503a1b4a44899776ad111ab283796373`
- Owner's verdict: 

```text
- **The game tests return to their earlier seeds.** `DeterminismTests` and `PlayerCountTests` go
  back to 20260913 (and 1 for the other seed). `SeededGameReplayTests` goes back to 20260914, 65 turns
  and a gammon for White, with one turn naming `bearing-off-eligible/2`. Its hash is re-pinned for
  ruleset 5 and schema 3. `DeterminismTests.A_game_that_finished_under_ruleset_three_declines_citing_page_275`
  becomes `A_game_version_four_declined_finishes_and_names_the_owners_rulings_it_relied_on`.
```

## 21. `engine/decisions/0009-owner-rulings-are-ruleset-version-five.md`, block 54

- Reasons: test-name
- Found: test-name `A_number_left_after_the_last_man_comes_home_bears_off_naming_the_owners_ruling`; test-name `MustPlayWholeThrowEntryPointTests`; test-name `Two_orders_reaching_the_same_position_under_different_rules_are_one_play_naming_the_owners_ruling`
- Removed text sha256: `da3a49744d142e701e84d5d39abdab6080c95b40103d3a4df88cfd198614e9c3`
- Owner's verdict: 

```text
- **Two tests are replaced.** Version 4's two decline tests become
  `MustPlayWholeThrowEntryPointTests.Two_orders_reaching_the_same_position_under_different_rules_are_one_play_naming_the_owners_ruling`
  and `A_number_left_after_the_last_man_comes_home_bears_off_naming_the_owners_ruling`. Each is named
  in the overlay with the mutations that turned it red: restoring version 4's decline, never naming
  the ruling, and naming it where it is not relied on.
```

## 22. `engine/decisions/0009-owner-rulings-are-ruleset-version-five.md`, block 55

- Reasons: test-name
- Found: test-name `BearingOffEligibilityTests`; test-name `WholeThrowTests`
- Removed text sha256: `d80e70573aed30fb3b250499fcd554001d444129366554c8e356c9a539b20797`
- Owner's verdict: 

```text
- **The first-part declines keep their tests unchanged:** `Either_die_alone_playable_but_not_both_declines_citing_page_275`,
  `WholeThrowTests.Where_either_die_alone_can_be_played_but_not_both_the_corpus_does_not_settle_it`
  and `The_rule_declines_in_exactly_one_shape_either_die_alone_playable_but_not_both`, and
  `BearingOffEligibilityTests.A_man_re_entered_after_bearing_off_began_is_the_case_the_corpus_does_not_settle`.
```

## 23. `engine/decisions/0010-owner-rulings-are-ruleset-version-six.md`, block 39

- Reasons: test-name
- Found: test-name `MapCorrespondenceTests`
- Removed text sha256: `f0dc7d4824169b4ea51bf1e38c2a0b764e6d79e64291b4b8377cc90fabd0cce1`
- Owner's verdict: 

```text
- **`MapCorrespondenceTests` honour `declines: []`.** Row 6 still predicts `RequiresInterpretation` for
  the three entries, because the map is unchanged. For an entry the overlay declares fully ruled, the test
  now requires the opposite: that no hand-written code path declines citing it. A pinned test holds the set
  of fully ruled entries to these three.
```

## 24. `engine/decisions/0010-owner-rulings-are-ruleset-version-six.md`, block 44

- Reasons: test-literal
- Found: test-literal `20260900`
- Removed text sha256: `487c9bdf3c61d05a1089e34da694d99f933a3a857ced9e5b63f561bd90389da0`
- Owner's verdict: 

```text
- **Every game played from the corpus's start finishes.** Over the hundred seeds from 20260900
  (`Pcg32.FromSeed(seed, stream: 1)`):
```

## 25. `engine/decisions/0010-owner-rulings-are-ruleset-version-six.md`, block 50

- Reasons: test-literal, test-name
- Found: test-literal `20260914`; test-name `SeededGameReplayTests`
- Removed text sha256: `480f9f7039497a2c1486cddd1ee1bd5d4d15f9069c0aeb3769344e002a84f0d8`
- Owner's verdict: 

```text
- **The seeded replay is re-pinned.** `SeededGameReplayTests` (seed 20260914) plays the same 65 turns and
  the same gammon for White. Its bytes differ in the ruleset and schema versions and in `"valueRulings":[]`.
  With those three set back, the bytes hash to version 5's pin. A tool comparing recorded games must refuse
  to compare a version 6 record with a version 5 one, and a schema 4 record with a schema 3 one.
```

## 26. `engine/decisions/0010-owner-rulings-are-ruleset-version-six.md`, block 51

- Reasons: test-literal, test-name
- Found: test-literal `20260907`; test-name `A_game_version_five_declined_finishes_and_names_the_owners_rulings_it_relied_on`; test-name `A_man_re_entered_after_bearing_off_began_bears_off_again_only_once_every_man_is_home_naming_the_owners_ruling`; test-name `A_rubber_scored_from_a_game_valued_by_an_owners_ruling_names_that_ruling`; test-name `BearingOffEligibilityTests`; test-name `DeterminismTests`; test-name `Either_die_alone_playable_but_not_both_plays_the_higher_naming_the_owners_ruling`; test-name `GameValueEntryPointTests`; test-name `GameValueTests`; test-name `MustPlayWholeThrowEntryPointTests`; test-name `Nothing_borne_off_with_a_man_up_or_in_the_winners_home_table_is_a_backgammon_naming_the_owners_ruling`; test-name `RubberScoringTests`; test-name `The_finish_no_named_result_covers_is_a_hit_naming_the_owners_ruling`; test-name `The_finish_no_named_result_covers_resolves_to_a_hit_naming_the_owners_ruling`; test-name `The_owners_ruling_is_named_in_exactly_one_shape_either_die_alone_playable_but_not_both`; test-name `The_re_entry_ruling_is_named_only_where_the_question_arises`; test-name `Where_either_die_alone_can_be_played_but_not_both_the_higher_is_compelled_naming_the_owners_ruling`; test-name `WholeThrowTests`
- Removed text sha256: `1833ec7f379cb3a67dd5edf278bffef286c5e55435fd851a41fdeda2581319e6`
- Owner's verdict: 

```text
- **The first-part decline tests became ruling tests.** Each is named in the overlay with the mutations
  that turned it red: restoring version 5's decline, the ruling's other reading, never naming the ruling,
  and naming it where it is not relied on.
  - `WholeThrowTests.Where_either_die_alone_can_be_played_but_not_both_the_higher_is_compelled_naming_the_owners_ruling`
    and `The_owners_ruling_is_named_in_exactly_one_shape_either_die_alone_playable_but_not_both`
  - `MustPlayWholeThrowEntryPointTests.Either_die_alone_playable_but_not_both_plays_the_higher_naming_the_owners_ruling`
  - `BearingOffEligibilityTests.A_man_re_entered_after_bearing_off_began_bears_off_again_only_once_every_man_is_home_naming_the_owners_ruling`
    and `The_re_entry_ruling_is_named_only_where_the_question_arises`
  - `GameValueTests.The_finish_no_named_result_covers_is_a_hit_naming_the_owners_ruling` and the two
    `…before_bearing_off_is_a_backgammon_and_not_a_gammon_naming_the_owners_ruling`
  - `GameValueEntryPointTests.The_finish_no_named_result_covers_resolves_to_a_hit_naming_the_owners_ruling`
    and `Nothing_borne_off_with_a_man_up_or_in_the_winners_home_table_is_a_backgammon_naming_the_owners_ruling`
  - `RubberScoringTests.A_rubber_scored_from_a_game_valued_by_an_owners_ruling_names_that_ruling`
  - `DeterminismTests.A_game_version_five_declined_finishes_and_names_the_owners_rulings_it_relied_on`
    (seed 20260907, middle play), which names `bearing-off-eligible/1` on two turns and `game-value/2` on
    its value
```
