# 0027 — An owner's ruling on an unresolved question is held in the engine's overlay, never in the map, and the factory checks it

## Status

Accepted — 2026-09-15. Decided by Brandon, the owner, on 2026-09-15. **Extends
[0015](0015-a-map-is-published-as-a-versioned-package.md)** (*The overlay, and the offline merge
check*): an overlay item may hold `rulings` and `declines` beside the three fields, and neither is
merged. **Amends [0005](0005-a-field-earns-its-place-by-being-checkable.md) C** where it says an
`implemented` entry with `fate: unresolved` "declines the stated case": part of that case may now be
answered by a ruling. Changes no map field and no check in `check-map.py`.

**Amended 2026-09-15**: § 4 did not say whether a result computed from ruled results relies on
those rulings. It does, and it names them. See *Amendment — a derived result names its inputs'
rulings* below. No check, field or generated file changes.

**Amended 2026-09-15, again** ([#141](https://github.com/brandonifco/rules-factory/issues/141)),
decided by Brandon: § 2's `span` quoted the question into three committed files, which
[0022](0022-a-licensed-copy-is-used-locally-by-a-named-operator-and-never-published.md) forbids for
a licensed `local-copy` corpus. For such a corpus a span is offsets and a hash, and nothing committed
may carry fifteen words of the map. See *Amendment — a licensed corpus's question is named, never
quoted* below. A committed-copy corpus's overlay, generated files and provenance are unchanged.

## Amendment — a derived result names its inputs' rulings

§ 4 asks every result that relies on a ruling to name it, and gives a play as the pattern. It is
silent on a result that is computed from other results, where one of those inputs rests on a ruling.
`hoyle-backgammon` met the case on the day this record was accepted. Brandon ruled on all of
`game-value`'s question: the finish no named result covers is a hit, and the overlaps are a
backgammon. That engine's `rubber-scoring` scores a rubber from its games' values, and a rubber whose
first game is a hit only by the ruling now scores where it declined before.

**A result derived from ruled results relies on those rulings, and names them**, on the same terms as
§ 4: as data the caller can read, and in any record of the result. A rubber scored from a game valued
by a ruling names that ruling, as the game does. Where several inputs carry rulings, the derived
result names their union, once each, in a stable order. The derivation needs no ruling of its own for
this: the rulings are its inputs', carried through. What the derivation still does not settle, it
still declines, and a decline names no ruling.

`hoyle-backgammon` decision 0010 is the case. `GameResult.Rulings` carries the rulings a game's value
relied on. `RubberResult.Rulings` is the union over the games a rubber was scored from, in overlay
order. `rubber-scoring`'s overlay item carries no `rulings` or `declines`, because it has no ruling of
its own.

As with the rest of § 4, nothing checks this (§ 7). An input that reaches the derivation as a bare
value, with its rulings dropped on the way, is the engine's to avoid. In that engine, the stake and the
next game's opener take a bare `GameValue`, and its record 0010 says so.

## Amendment — a licensed corpus's question is named, never quoted

§ 2 names a part of the question by quoting it, and § 4 and § 5 carry the quotation on. It lands in
`corpus-map.overlay.json`, as `OwnerRuling.Span` in `Rulings.g.cs`, and under `rulings[].span` in
`provenance.json`. An engine commits all three. For a `local-copy` corpus, 0022 withholds
`ambiguity.question` from everything the factory writes into the engine, since a question is written
about the passage and often quotes it. Nothing refused a quoted span, so the first ruling on a
licensed corpus would have committed its question. The deckard rebuild (#3, criterion 1) is that
case: Brandon adopts as his own rulings the decisions its book leaves open.

**For a corpus whose manifest says `verification: local-copy`, a ruling or decline names its span
without its words.**

```json
"rulings": [
  {
    "id": "occupied-square/own-pawn",
    "span": { "start": 0, "end": 94, "sha256": "<64 hex digits>" },
    "answer": "Yes: a pawn of the moving side blocks the move as well.",
    "ruledBy": "Brandon",
    "ruledOn": "2026-09-15",
    "record": "docs/decisions/0003-own-pawns-block.md",
    "tests": ["OccupiedSquareTests.The_owner_rules_a_captains_own_pawn_blocks_the_square"]
  }
],
"declines": [ { "span": { "start": 95, "end": 129, "sha256": "<64 hex digits>" }, "tests": ["…"] } ]
```

(The entry is `tools/tests/licensed_fixture.py`'s, whose corpus is invented.)

- **The question is normalised first**: every run of whitespace becomes one space, with none at
  either end. `start` and `end` are character offsets into that string, end exclusive, and `sha256`
  is the SHA-256 of the UTF-8 of the text between them. A span begins and ends on a character of the
  question's words, not on a space.
- **The checks are § 5's, on the normalised question.** The factory holds each span to the map
  wherever it has the map: on every `produce`, in the gate's merge and regeneration steps, and so in
  `factory verify` on the operator's machine. A span's text must hash to its `sha256`. Spans may not
  overlap, and together they cover the question, whitespace aside. `declines: []` still declares the
  question fully ruled. A question the map rewrote moves the offsets or changes the hash, and § 6
  applies as before. What cannot run without the map, an engine's CI (0022), cannot check this either,
  and says NOT VERIFIED already.
- **Committed files hold only** the span's offsets and hash, and the ruling's `id`, `answer`,
  `ruledBy`, `ruledOn`, `record` and `tests`. The overlay and provenance carry the span object as
  written. `OwnerRuling.Span` carries `sha256:<hex> [start, end)`, and its documentation says the
  part is named without its words.
- **`answer` stays, in the owner's own words.** So do the other strings. The factory refuses a
  ruling or decline whose `id`, `answer`, `ruledBy`, `record` or any test name, or whose decision
  record's text, carries **fifteen or more consecutive words** of any string the map holds for an
  entry: its `evidence`, its `note`, its `ambiguity.question`, or any other. Words are compared
  case-folded, split on everything that is not a letter or digit, so a test name's underscores
  separate words as spaces do.
- **A message never repeats the words.** A gap is named by its offsets, a mismatch by its hash, and a
  field that quotes by its name and the word it begins at. A quoted span is refused with the span
  object that would replace it. `python3 scripts/factory/rulings.py locate --map M --entry ID` prints
  the object for text typed on stdin, so the operator never writes the question into the engine to
  learn its offsets.
- **The posture is the package manifest's.** `produce` reads it from intake. The gate reads it from the
  restored package, as it reads `randomness` (0019), and `map-overlay.py` takes `--package-manifest`.
  Where the posture is not given, any ruling or decline is refused, because which rule applies is
  unknown.
- **A committed-copy corpus is unchanged.** Its spans stay verbatim quotations, a span object is
  refused there, and no word count applies. `hoyle-backgammon`'s six rulings need no change.

**Not checked.** A span hash covers a few words. A short span's hash could be recovered by guessing
the words, so the hash is a check that the span still matches, not a way to keep it secret. Fifteen
words is a threshold for quotation, not a measure of paraphrase: an answer can follow the book's
wording closely in fourteen-word pieces, and nothing measures how closely. That was 0022's caveat
for the backlog too. And `mutation` strings, which the overlay also commits, are outside this
record's fields and are not examined.

**Rejected.** *Keep the verbatim span and trust the operator.* That breaks 0022 in three files on the
first ruling. *Withhold spans from the generated and provenance files only.* The overlay is committed
too, and a withheld span leaves nothing that § 6 can hold to a rewritten question. *A hash of the
whole question per ruling.* It names no part, and § 2's alternative already rejected it for that
reason. Offsets and a span hash keep coverage, which is what makes every change to the question come
back to the owner.

## Context

A map entry records a question the corpus does not settle with `ambiguity.fate: unresolved`. The
map is data ([0016](0016-a-map-package-is-data-not-code.md)), and its whole value is that it says
only what the corpus says, so nobody's answer to such a question can go in it. `fate: decision` is
not the carrier either. It means the project rules on what the passage *means* and implements "as
though the corpus had said so" ([corpus-map.md](../corpus-map.md), `ambiguity.fate`). It lives in the
map, and an engine cannot set it.

Until now an engine could only decline. [corpus-map.md](../corpus-map.md) says that for an
`implemented` entry with `fate: unresolved` "the verdict covers every case except the one
`ambiguity.question` names, and the declining case ships a test". Nothing checks that. The
overlay's tests are required only to be non-empty, and nothing marks which of them declines.

`hoyle-backgammon` got there first. On 2026-09-15 Brandon ruled on the second part of two questions
in that engine's map, `must-play-whole-throw` and `bearing-off-eligible`, and three more rulings are
coming for the same engine. The engine had no factory support, so it did the whole job itself. It
wrote its decision record 0009. It hand-wrote an `OwnerRuling` record and an `OwnerRulings` class
(`must-play-whole-throw/2`, who ruled, when, the record path). It put `Play.Rulings` on every answer
that relies on a ruling, and `rulings` on each turn of its replay record. Its 0009 lists what that
left open. The factory had no field for the ruling. No check saw it. The factory's gate passed the
engine only because both entries still decline their first parts. That record also named the fix:
"If the factory gains a carrier, such as an overlay or engine-side ruling that correspondence row 6
honours, these rulings move into it."

## Decision

### 1. A ruling is the engine's, and it lives in the engine's overlay

**A ruling is an engine-owned interpretation of part of an unresolved question.** The owner gives
it, the engine records it and applies it, and it binds no other engine built from the same map. It
lives in `corpus-map.overlay.json`, on the item of the entry whose question it answers, and **it is
never merged into the map**. The merged map the packaged checker reads is byte for byte what it was
without it. So the map never claims the corpus said what a ruling says, and a map package's checker,
which predates this record, needs no change to be run on the merge.

A ruling and a `fate: decision` are different claims, and the difference is who is speaking. A
decision says what the passage means. It is the map's, it applies to every engine, and it is
reviewed with the map ([0017](0017-a-map-change-carries-a-review-of-its-bytes.md)). A ruling says
what this engine does where the passage says nothing. It is one owner's, and it is never presented
as a reading.

### 2. What a ruling names

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

(The spans are elided here. In an overlay each is quoted in full, and together they are the whole
question.)

- **The entry** is the overlay key the ruling sits under. The `id` is `<entry id>/<slug>`, unique
  in the overlay, so an id alone names its entry.
- **`span`** says which part of the question the ruling answers. It is a quotation of the entry's
  current `ambiguity.question`, verbatim, and it must occur there exactly once. A part is named by
  its words, not by a number, because the map does not number parts, and a number would still
  point somewhere after the question was rewritten.
- **`answer`** is the ruling stated briefly, on one line of at most 300 characters. The reasons are
  the record's.
- **`ruledBy`, `ruledOn`** (YYYY-MM-DD) and **`record`**, the engine's decision record that holds
  the ruling, as a path relative to the engine root. The record is a file the engine commits.
- **`tests`** are the tests that show the ruled behaviour, and that the ruling is surfaced to the
  caller. Each is one of the entry's own `tests`, so each already carries the mutation that turned
  it red. A ruling adds no second list of tests with no mutations.

**`declines` goes with `rulings`.** It lists the parts of the same question the engine still
declines, each by `span` and with the tests that show the decline. **Together, the rulings' spans
and the declines' spans cover the whole question** (whitespace between them aside), and no two
overlap. `declines: []` is how an engine declares that the question is **fully ruled**: every part
has a ruling, and the entry declines nothing. An item may carry `declines` with no rulings, and is
then held to the same rules. That is a way to name a declining test, and nothing requires it.

### 3. An implemented unresolved entry declines, is ruled, or both, and says which

For an `implemented` entry with `fate: unresolved`:

- **No `rulings` and no `declines`**: as before. The entry names its tests, and the declining case
  is one of them (corpus-map.md). Nothing marks which one.
- **`rulings`**: at least one ruling, and `declines` beside it. The declining test the entry owes
  is the declines' tests. With `declines: []` the question is declared fully ruled, and no
  declining test is owed. That declaration is checked (§ 5): the rulings' spans alone must cover
  the question.

### 4. How an engine surfaces a ruling, so it is never passed off as the corpus

- **Every result that relies on a ruling names it**, as data the caller can read, with at least the
  ruling's id, and through it the entry, who ruled, when, and the record. A result that relies on
  no ruling names none. `hoyle-backgammon`'s `Play.Rulings` is the pattern. A result computed from
  results that rely on rulings relies on them too, and names them (amended 2026-09-15, above).
- **A record of the result carries it too.** A replay record, a log or a serialised answer that
  would let a reader reconstruct the answer carries the rulings the answer relied on.
- **The ruling never stands in for the corpus's authority.** Where a result cites the map entry
  that permits it, that citation stays the map entry. The ruling is named beside it, not in its
  place. A decline relies on no ruling and names none.
- **The factory generates what the engine would otherwise restate.** When the overlay holds a
  ruling, `factory produce` writes `src/<Engine>/Generated/Rulings.g.cs`. It declares a record,
  `OwnerRuling(Id, EntryId, Span, Answer, RuledBy, RuledOn, Record)`, and `OwnerRulings`, with one
  static per ruling and `All`, in overlay order. Both are `partial`, so an engine can add an alias
  or a derived member in a file of its own. The metadata has one home, the overlay, and the gate's
  regeneration step holds the generated file to it byte for byte. An engine with no ruling gets no
  such file and no new type. Which results rely on which ruling is the engine's code, and the
  factory does not generate it.

### 5. What the factory checks

`generate.merge` (every `produce`, and the gate's regeneration) and the gate's `map-overlay.py`
(merge rule 2) both run `tools/factory/rulings.py`. The factory vendors it into every engine as
`scripts/factory/rulings.py`. They refuse:

1. a ruling or decline on an entry whose `ambiguity.fate` is not `unresolved` in the package map,
   or whose overlay status is not `implemented`;
2. a ruling missing any of `id`, `span`, `answer`, `ruledBy`, `ruledOn`, `record`, `tests`;
   carrying any other key; with a blank field; with an `id` not `<entry>/<slug>` or used twice; with
   an `answer` not one line of at most 300 characters; or with a `ruledOn` that is not a real
   YYYY-MM-DD date. A decline carrying anything but `span` and `tests` is refused too;
3. a `span` not in the current question exactly once, spans that overlap, and spans that leave any
   of the question unquoted;
4. `tests` that are empty, or that name a test the overlay item's `tests` does not;
5. a `record` that is not a plain relative path inside the engine, or not a file there;
6. `rulings` without `declines`, `declines: []` without `rulings`, and `rulings: []`.

**The rulings are reported.** `produce` prints one line per ruling ("owner's ruling
`bearing-off-eligible/2` on `bearing-off-eligible`, not the corpus: …, ruled by Brandon on
2026-09-15, …"). So does the gate's merge step, which `factory verify` runs, and every entry
declared fully ruled gets a line too. `provenance.json` gains `rulings`, only when there are any:
`[{id, entry, span, answer, ruledBy, ruledOn, record, recordSha256}]`. `recordSha256` is the hash
of the decision record when `produce` ran, so a record edited since is a named mismatch until the
engine is produced again.

### 6. Rulings and map versions

The span is what ties a ruling to the question as the owner read it. On a new map version:

- **The question is reworded, grows a part, or loses one.** A span no longer in it, or text no
  span covers, refuses the merge. That holds even when the version is a patch, since the question
  is prose. The engine re-divides the question. It re-quotes a ruling's span **only once the owner
  has confirmed that the ruling answers the question as it now reads**, and the record says so (a
  new record, or an amendment with its date). A new part is declined or newly ruled, never
  silently covered.
- **The entry is settled** (`fate: decision`, or the ambiguity removed). Every ruling on it is
  refused. The engine follows the map and withdraws the ruling in a decision record. This is
  0009's commitment in `hoyle-backgammon`, made general.
- **The entry is renamed or removed.** Merge rule 1 already refuses the overlay key.
- **Nothing in the question changed.** The ruling stands, and nothing is re-confirmed.

A ruling is never a reason to hold an engine on an old map version, and never a finding against
the map. If the owner believes the corpus *does* settle the question, that is a finding. Filed
upstream, it becomes a map change, and the ruling is withdrawn when the map moves.

### 7. What is machine-checked, and what is not

**Checked**: everything in § 5. In particular, a ruling can exist only on an open question in
the map the engine builds from. It names, in the question's current words, exactly the text it
answers. Every character of that question (whitespace aside) is claimed by exactly one ruling or
one decline. Its tests exist in the overlay, and the gate's `named-tests` step shows that they ran
in every target framework. Its record is committed, and provenance hashes it. The generated
registry equals the overlay.

**Not checked**, because the map does not divide a question into parts and the factory cannot run
an engine's semantics:

- **That the spans divide the question where its parts really divide.** An engine could quote the
  whole question as one ruling's span and declare it fully ruled while the owner ruled on half. The
  check sees words, and "every part is either declined or ruled" is enforced only as "every word is
  quoted by a ruling or a decline". Review of the overlay and of the record is what catches a bad
  division.
- **That the engine does what `answer` says, declines what `declines` names, or surfaces the
  ruling.** The named tests are required to exist and run, not to test those things, as with every
  `tests` item (corpus-map.md, `status`).
- **That `ruledBy` is the owner.** It is a name the engine writes.
- **That a declining test is among an entry's tests when it has neither `rulings` nor `declines`.**
  That stays as it was: prose in corpus-map.md, and unchecked.

## Alternatives considered

**A third `fate`, or a ruling field on the map entry.** Rejected. It puts the owner's answer in the
map, which then claims more than the corpus says. And it would bind every engine built from the map
to one engine's owner.

**Number the parts** (`questionPart: 2`, as `hoyle-backgammon` does). Rejected. Nothing in the map
defines part 2, so no check can hold the number to anything. A question rewritten with its parts
reordered keeps the number and changes its meaning.

**A span that must only be present, without covering the question.** This was the first draft. It
catches a rewritten sentence, and misses a part the map adds while the quoted words stay. And an
engine could declare a question fully ruled while one of its parts was never answered. Covering the
question costs longer spans. In return, every change to the question comes back to the owner.

**A hash of the question in each ruling.** It catches every change, just as coverage does. But it
names no part, and a question with two rulings would need the same hash stated twice. Coverage gives
the same guarantee through the spans the ruling needs anyway.

**`fullyRuled: true`.** Rejected in favour of `declines: []`. A flag asserts completeness and says
nothing checkable. An empty list of declines, with the rulings' spans covering the question, is the
same statement in a form the check reads.

**Generate `Play.Rulings`-style plumbing.** Rejected. Which answers rely on which ruling is the
engine's logic, and the map declares no output types to hang it on (#76). The factory generates
the registry and nothing more.

## Consequences

- **An engine can answer part of an open question without the map changing,** and without anything
  claiming the corpus settled it. The factory's gate now sees the ruling, and refuses one that has
  stopped matching the map.
- **An engine with no rulings is unchanged.** Its overlay needs nothing new, it generates no new file
  or type, its provenance gains no field, and its gate prints nothing new. The example engines
  `scripts/validate-engine.sh` produces are such engines. The same script also builds a scratch
  engine that has a ruling, so `Rulings.g.cs` is compiled with `-warnaserror` on every pull request.
- **`hoyle-backgammon` moves its two rulings into its overlay** at its next `produce` from a
  factory with this record. It divides each question into two spans, a ruling and a decline. It
  replaces its hand-written `OwnerRuling`/`OwnerRulings` with the generated ones, or keeps its
  member names as partial aliases. `questionPart` gives way to `span` (its replay schema decides
  whether to derive `questionPart` or change the record). The factory's changes stop at that
  engine's repository.
- **A map version that rewords an open question now costs an engine with rulings a re-confirmation.**
  That cost is intended. The owner ruled on words, and when the words change the owner decides again.
- **The totality loss 0005 C recorded is partly repaid.** For an entry with `rulings` or `declines`,
  the overlay now says which parts of its question decline and which the owner answered. For every
  other `implemented` unresolved entry, nothing distinguishes one that declines a single shape from
  one that declines everything, as before.
