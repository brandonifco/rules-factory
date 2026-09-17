# 0025 — An assertion names who asserts it, and an operation names what it draws, in the corpus's words

## Status

Accepted — 2026-09-15. Decides
[#117](https://github.com/brandonifco/rules-factory/issues/117) and
[#118](https://github.com/brandonifco/rules-factory/issues/118), both found by trial 7
(`examples/srd-52-combat/README.md`, findings). **Extends
[0005](0005-a-field-earns-its-place-by-being-checkable.md)**: two fields, each checkable. **Amends
[0019](0019-randomness-is-declared-by-the-corpus.md)** where it says that no field of a map says
"this rule throws a die". `draws` is that field, and it is narrower than the sentence 0019 ruled out.
It extends the assertion contract of
[0010](0010-whose-fact-it-is-does-not-decide-the-kind.md) and the caller-held fact of
[0021](0021-a-gate-outside-the-slice-is-held-by-the-caller.md). It changes neither.

## Context

**Attribution had nowhere to go.** An engine owes an assertion four things: *demand it, attribute it,
record it with the outcome, never infer it* (corpus-map.md, `kind: assertion`). The map said
nothing about the second. `initiative-ties` names two deciders in one sentence: the GM for tied
monsters and for a monster tied with a player character, the players for tied characters. Its note
said the attribution was one "which the map has no field to record". So srd-52-combat checks the
decider in engine code (its PR #1) from its own reading of the corpus. That is the kind of reading
the map exists to hold.

**Draws are part of what a replay means.** Under `randomness: seeded`, every draw comes from one
replayable source, so one extra or missing draw shifts every later one (method.md, Phase 6). Two
trial-7 cases showed that whether a draw happens, or how many, can be unsettled. Is an attack
against an empty location rolled? Is a "group of identical creatures" one roll or many? An engine
answering either question differently from another engine is not just giving a different answer. It
is replaying a different game. The map could record the question (`ambiguity`), but not the fact
that it moves the draw count, nor what the count is where it is settled.

## Decision

### 1. `assertedBy`, on every `kind: assertion` entry

```json
"kind": "assertion",
"assertedBy": ["GM", "players"],
```

A non-empty list of **who the corpus says supplies or decides the fact**, in the corpus's own words.
Its rules:

- It is required on every assertion and refused on every other kind.
- Its values are distinct, ignoring case and spacing.
- **Anchored.** Each value appears in the entry's `evidence`, or inside a span the entry's `note` quotes. The match ignores case and runs of whitespace, and must be a whole word or phrase: "pilot" inside "autopilot" is not the pilot. A value in the note but outside quotation marks anchors nothing, because that is the mapper's sentence, not the corpus's. The note route exists for the regulation's lead-in: § 107.49's *"Prior to flight, the remote pilot in command must:"* governs (a)–(e) and lies outside each paragraph's evidence.
- **`caller`, where the corpus names nobody.** `["caller"]` stands alone, and the entry's `note` says why, naming the caller. *"(as may have been agreed)"* is an agentless passive (corpus-map.md, gate 3). § 107.37(b)'s *"No person may operate … so close … as to create a collision hazard"* names the subject of a prohibition and nobody whose determination settles the hazard. `caller` does not mean "anyone". It means that the corpus does not narrow who may assert, so the engine attributes the assertion to whoever the caller says made it.

`check-map.py --only asserted-by` enforces all of it. It is a publish-time check, and no overlay field
changes its verdict.

**Generated code exposes it.** `MapEntry`, `DerivedMapEntry` and `RegisteredEntry` gain
`ImmutableArray<string> AssertedBy { get; init; } = []`. It is set by an object initializer on
assertion entries and is empty everywhere else. It is an init property, not a positional parameter,
so the records' constructors and deconstructors are unchanged, and an engine that never reads it is
unaffected. An engine checks a tie break's decider against `Registry.Entry("initiative-ties").AssertedBy`
instead of a string it typed.

### 2. `draws`, on an operation whose own resolution draws

```json
"kind": "operation",
"draws": { "dice": "d20", "count": "one per participant …" }
```

The field is an object `{dice, count}`, or a non-empty list of them for an entry that rolls two
different things (`attack-resolution`: the attack roll, then damage dice on a hit). Its rules:

- `dice` names what is rolled and is anchored exactly as `assertedBy` is. The SRD's Initiative evidence says only *"they make a Dexterity check"*. The die is in the p. 6 sentence the note quotes: *"the game uses a d20 roll to determine success or failure"*. Hoyle has no dice notation, so its `dice` is the corpus's word, `die` or `dice`. The six faces are `die-faces`'s.
- `count` is a positive number, or a short statement where the number depends on the position ("one per player, and one per player again after each tie").
- Only an `operation` that is `scope: in` may carry it. The engine declines an out-of-scope rule and draws nothing for it.
- Refused under `randomness: none`. Not verified (a failing skip) where no manifest says the corpus is `seeded`.

**Whose draw it is.** A draw belongs to the entry whose own resolution makes it, and to no other.
An entry that reaches a roll through another entry does not declare it. That covers a gate
(`full-table-suspension` suspends `throw-two-dice`), a dependency (`attack-structure` →
`attack-resolution`) and a cross-reference (`next-game-opening`'s *"as at starting"* → `opening-roll`).
The count may name the other entry, so that one draw is counted once
(`initiative-roll`: "one per participant not in a group of identical creatures, whose roll is
group-initiative's"). Without this rule the same d20 would be declared on three entries, and a reader
counting draws would count three.

### 3. `ambiguity.affectsDraws`

```json
"ambiguity": { "question": "What makes creatures a “group of identical creatures”? …",
               "fate": "unresolved", "unresolvedReason": "RequiresInterpretation",
               "affectsDraws": true }
```

A boolean inside the `ambiguity` block. `true` says **the unsettled point changes how many draws this
entry's own resolution makes**. Such an entry must declare `draws`, and its `count` may name the
alternatives. `check-map.py --only draws` refuses `affectsDraws` that is not a boolean, one at entry
level, and a `true` with no `draws`.

It lives inside the block for 0007's reason: only an ambiguous entry has an unsettled point.

### Applied

| map | entries | change |
|---|---|---|
| `faa-part-107` (2026) | 10 assertions | `remote pilot in command` ×6 (4 anchored in § 107.49's quoted lead-in), the three named persons on § 107.31(a) and § 107.33(c), `caller` on `collision-hazard-proximity`, `reasonable-protection`, `flash-rate-sufficient` |
| `faa-part-107-temporal` (2020) | 9 assertions | the same, without `flash-rate-sufficient` |
| `hoyle-backgammon` | 1 assertion, 2 operations | `agreed-backgammon-multiple`: `caller`; `opening-roll`: die, one per player and again after each tie; `throw-two-dice`: dice, 2 |
| `srd-52-combat` | 3 assertions, 4 operations | `initiative-ties`: GM, players; `gm-requires-action`: GM; `sides-agree-to-end`: both sides; `initiative-roll`, `group-initiative` (`affectsDraws: true`), `attack-resolution`, `falling-off` |

No Part 107 entry draws.

**Where this departs from the direction it was given, and why.** The direction proposed `["players"]`
for hoyle's agreed multiple. Nothing in the pages says the players agree. The sentence is *"(as may have
been agreed)"*, and corpus-map.md's gate 3 already records that it names nobody. An anchor found
elsewhere would have to be a quote about something else. The value is `caller`, and the note says the
parties to the agreement are not named. The direction also named the attack on an empty location as
an ambiguous-draw case. Since #106's blind mapping that entry has been `clear`: the roll is made, and
the location decides only that it misses. That roll is `attack-resolution`'s, so
`wrong-location-misses` declares nothing (the reviewer's round 1).

## Alternatives considered

**A closed set of asserters per corpus, in the manifest.** Rejected for now. It would let a check
refuse a party the corpus never uses. Three corpora supply eleven distinct values between them (with
`caller`), and two of them are one person under two spellings (`person manipulating the flight control` /
`… controls`). A closed vocabulary written from that would be written from spelling. The anchor is
checkable today, and a closed set can be derived from anchored values later.

**Free text in `note`.** Rejected: 0005. A prose attribution names a distinction and checks nothing,
which is exactly where `initiative-ties` already recorded it.

**Require `draws` on every operation of a seeded corpus.** Rejected. Most operations draw nothing, so
the field would have to be present and empty on most entries, and that emptiness is the claim nobody
could check. An operation that draws and omits `draws` passes, the same blind spot as an unrecorded
conflict. The field is *required* only where a mapper has recorded that the count is unsettled.

**Mark every ambiguity or gate upstream of a draw.** Rejected (§ 2). `surprised` decides whether an
Initiative roll has Disadvantage, and `full-table-suspension` decides whether a player throws. Either
could change every later draw, and so could nearly every gate in a game. The map already records those
routes as edges to the drawing entry. Flagging them would count one throw in several places.

**Expose `draws` in generated code.** Not done. `count` is prose, so a typed contract could only carry
a string. The replay test an engine owes (method.md, Phase 6) pins draws by running them. If a
structured count is ever decided, it will be decided here first.

**A positional `AssertedBy` parameter on the records.** Rejected. It breaks every engine that
deconstructs a `MapEntry` or `RegisteredEntry`. An init property is additive.

## Consequences

**Every `kind: assertion` entry in every map now needs `assertedBy`**, so a map without it fails
`check-map.py` at publish. Published packages that predate the field are unaffected downstream. The
factory's intake runs `--phase consumer`, and neither new check is in it, so an engine produced from
an older version still intakes and generates, with `AssertedBy` empty.

**What the checks do not buy.**
- A span quoted in `note` is not located by `check-map.py`, which reads no corpus. `tools/tests/mapvalidator/test_map_anchors.py` holds every note anchor of the four example maps to the committed corpus text, and proves it can fail. A new map outside that list gets no such test.
- The anchor proves the word is in the passage, not that it names the right party. A bystander named in the evidence passes.
- `assertedBy` records who bears the duty or holds the decision. Where a section lists persons who *must be able to see* (§ 107.31(a)), the attribution is to them, and the list does not say that § 107.31(b) lets some of them exercise the ability instead of the others. That is `visual-line-of-sight`'s rule.
- Nothing reads `count`.

**The review gate.** All four maps changed bytes. Each map's `review.json` records an independent
verdict on these fields, chained from its previous review. The 2020 map keeps its legacy exemption
with its digest updated, and its reason names this change and the reviewer who read it with the 2026
map. Package versions are not bumped here.
