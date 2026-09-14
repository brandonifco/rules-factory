# 0011 — A gate has a direction, and the field it sits in says which

## Status

Accepted — 2026-09-14. Decided by Brandon on
[#32](https://github.com/brandonifco/rules-factory/issues/32). **Supersedes the polarity
paragraph of [0003](0003-a-phase-gate-names-a-rule-not-a-condition.md)**; the rest of 0003
stands.

## Context

0003 gave the map `gatedBy`: the ids of the rules that govern whether an entry is reachable at
runtime. It accepted, as a named cost, that the field says nothing about *direction* —
`bearing-off-eligible` permits the entries it gates, `enter-from-bar` suspends them, and "a
reader who does not follow the id has learned less than they may think."

That was written with two gates over six entries. The build of `hoyle-backgammon` then found
two gates the map did not record (its `MAP-FINDINGS.md`, findings 6 and 7):

- **No entry named `full-table-suspension`.** A player whose adversary's home table is full has
  his play "altogether suspended, the adversary continuing to throw and move". He does not
  throw, so `throw-two-dice` and everything a throw reaches is unreachable on his turn. The
  omission is invisible to every legality test — the set of legal plays is empty either way —
  and changes every later throw, because an engine that throws for a suspended player consumes
  the generator.
- **`move-by-pip` named `enter-from-bar` and not `bearing-off-eligible`.** Once every man is
  home, bearing off governs every forward move.

Recording them puts a third gate on `move-by-pip`. Two of its three gates close it and one
opens it — or, read the other way, `bearing-off-eligible` opens the bearing-off entries and
*closes* `move-by-pip`. The same id means opposite things on different entries, and the
undirected list gives a reader no way to tell. The cost 0003 anticipated now has instances.

## Decision

**`gatedBy` splits into two fields.** Both hold entry ids in the same map and nothing else,
exactly as `gatedBy` did.

- **`enabledBy`** — the rules that make this rule reachable. The entry does not apply until
  one of them holds. `bearing-off-highest` is `enabledBy: ["bearing-off-eligible"]`.
- **`suspendedBy`** — the rules that make this rule unreachable while they hold.
  `move-by-pip` is `suspendedBy: ["enter-from-bar", "full-table-suspension",
  "bearing-off-eligible"]`.

Direction is a property of the **edge**, not of the gating rule: `bearing-off-eligible` is in
the bearing-off entries' `enabledBy` and in `move-by-pip`'s `suspendedBy`. That is why it has
to be written on the gated entry and cannot be written once on the gate.

Everything else 0003 decided is unchanged and applies to both fields: ids, never conditions; not
transitive and not inherited through `dependsOn`; orders nothing.

`tools/check-map.py` gains a `gates` check. It refuses `gatedBy` by name — a map still carrying
it states gates with no direction, and silently ignoring the field would drop every gate of an
unmigrated map out of every check — and it refuses one id named in both fields of one entry.
`references` resolves both fields; `absent` forbids both toward an absent rule.

### The gates `full-table-suspension` reaches

Every candidate was judged against the corpus's words, *"his play is altogether suspended"*,
and the judgement for each entry that names it is in that entry's `note`:

| entry | suspended? | why |
|---|---|---|
| `throw-two-dice` | yes | he does not throw — "the adversary continuing to throw and move" |
| `move-by-pip` | yes | no move is played |
| `doublets` | yes | no throw, so no doublets |
| `must-play-whole-throw` | yes | no throw, so no whole of one to compel |
| `legal-destination` | yes | it qualifies the right to move, and he has none |
| `blot-hit` | yes, on his turn | a hit is made by a move; his blots are still hit by the adversary |
| `enter-from-bar` | yes | the corpus does not have him throw to discover that no point is open |
| `made-point` | no | a description of a position, read on both players' turns — including by `full-table-suspension` itself, which depends on it |
| `direction-of-travel`, `point-designations`, `die-faces` | no | facts about the board and the dice, not steps of a turn |
| `opening-roll`, `opening-thrower-option` | no | no man can be up before the first throw |
| `bearing-off-*` | no | subsumed: a player with a man up is not all home, so `enabledBy: bearing-off-eligible` already excludes him — the same subsumption 0003 recorded for `enter-from-bar` |
| `win-condition`, `game-value`, `next-game-opening` | no | a suspended player has men on the board and cannot be the winner; the loser's state is read, not played |

The issue expected "roughly eight". The judgement gives seven. `made-point` is the one a reader
might expect and it is excluded on purpose: a gate on it would suspend the rule the gate is
defined by.

## Alternatives considered

**Keep `gatedBy`; let 0003's cost stand with the evidence recorded.** Rejected. The cost was
accepted as theoretical and it is now three gates on one entry, one of them pointing the other
way from the same id elsewhere. A reader of `move-by-pip` would have to open three entries to
learn which of them turn it off.

**One list of objects with a direction discriminator**, `gatedBy: [{ "rule": …, "polarity":
"suspends" }]`. Rejected for the reason [0005](0005-a-field-earns-its-place-by-being-checkable.md)
rejected merging `definedElsewhere` into `beyondAdapter`: the check becomes conditional on the
discriminator, and the value type stops being "ids and nothing else" — the property 0003 relied
on to keep conditions out. Two plain id lists keep that property and make direction structural.
This is the same shape the project has settled twice: two fields sharing one runtime concern,
kept apart because each has its own checkable contents.

**Record direction on the gating entry** (`bearing-off-eligible` declares that it permits).
Rejected: direction is per edge, and `bearing-off-eligible` both permits and suspends.

## Consequences

**Nothing checks that a gate is in the right field.** A permitting rule filed under
`suspendedBy` resolves and passes. What the split buys is that the claim is written where a
reviewer reads it, not that it is true. Completeness is as unchecked as it was under 0003: the
injection trial ([examples/injection-trial](../../examples/injection-trial/README.md)) dropped
a gate and added a spurious one, and nothing caught either.

**A reachability check is not part of this record.**
[#32](https://github.com/brandonifco/rules-factory/issues/32) asked for a check that an entry's
gates agree with the engine's reachability "if one is writable". That check lives with an
engine, like `hoyle-backgammon`'s correspondence check, and is not part of this change.

**Every map migrates.** The backgammon map is the only one carrying gates; its six `gatedBy`
lists become three `enabledBy` and three `suspendedBy`, and the eight new gate edges above are
added. Both Part 107 maps carry neither field, which remains the right outcome for a corpus with
no phases. `diff-maps.py` compares the new fields. The engine's own copy of the map migrates
in the engine repository, not here — and until it does, the injection trial's two gate patches
(`gate-dropped`, `gate-spurious`), which are applied to both copies, still name `gatedBy`. They
are a recorded run and are left as they ran; re-running the trial needs them updated alongside
the engine's copy.

**Gate lists are still judged, not enumerated.** The table above is a judgement, done once, and
two mappers may differ on `blot-hit` or `made-point`. It is recorded here and in each entry's
`note` so the difference is at least arguable.
