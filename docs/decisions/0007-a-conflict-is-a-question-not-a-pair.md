# 0007 — A conflict is a question, not a pair

## Status

Accepted — 2026-09-14. Settles
[#25](https://github.com/brandonifco/rules-factory/issues/25), which
[0005](0005-a-field-earns-its-place-by-being-checkable.md) section B opened by stating a rule
the schema could not express.

## Context

0005 section B says that where a corpus contradicts itself and the conflict is settled by
decision, **every entry in the conflict names the same decision record** — otherwise one side
can be decided and the other left open with nothing noticing. Two paragraphs later it
concedes the rule is unenforceable: "A conflict is a property of a pair, recorded on entries.
Nothing links them."

`tools/check-map.py` says so on every run against the backgammon map:

```
[skip] conflicts: NOT VERIFIED -- 3 entries carry `fate: decision`
(legal-destination, enter-from-bar, full-table-suspension) and no field identifies
which of them are in the same conflict, so 0005 section B's rule that they name the
same record cannot be enforced
```

That is the honest behaviour — it fails the run exactly when the rule could be broken — and
it is not a check. It has never reported `ok` and never could.

The rule has one instance, decided in
[0006](0006-the-general-rule-governs-entry-and-full-means-adversely-full.md): Hoyle states
where a man may be played twice, and the two statements disagree. Three entries carry
`fate: decision` naming that record.

### What the data actually says, which is not what #25 assumed

#25 proposes a symmetric list of ids inside the `ambiguity` block:

```json
"ambiguity": { "conflictsWith": ["legal-destination"], "fate": "decision", "decision": "…" }
```

Read against the one instance, that shape records the wrong fact. The three entries are not
three mutually contradicting sentences. 0006 establishes, at argument 7, that they are **one
question with three bearings on it** — *which points are open to a man entering from the
bar?*

- `legal-destination` answers it with three arms: vacant, own men, one adverse man.
- `enter-from-bar` answers it with two: "a vacant point or blot".
- `full-table-suspension` answers what follows when **none** are open, and its gloss "each
  point occupied by two or more men" is unqualified as to whose men they are.

Pairwise, `enter-from-bar` and `full-table-suspension` do not contradict each other at all.
0006 says the opposite of a contradiction about them: read strictly they "are exact negations
of one another", which is to say they *agree*, and that mutual fit is one of the two things
that makes the strict reading coherent. Their conflict is with `legal-destination`, not with
each other. So the honest pairwise record is a star, not a triangle — and the set of entries
the rule must range over is recoverable from it only by transitive closure.

**Transitive closure over "disagrees with" is not sound.** An entry can disagree with one
entry about one thing and with another about something else, without those two being in any
conflict together; closing over the relation merges two conflicts into one and then demands
they name a single record. Closure is therefore wrong in general and right here only by
accident — a shape that needs it is a shape that cannot say what it means.

The rule 0005 B states is a rule about a **set**: every member names the same record. A
pairwise relation does not denote a set. It denotes edges, from which a set must be derived
by an inference the data does not license.

## Decision

**The `ambiguity` block gains `conflict`: a slug naming the question the corpus answers
twice.** Entries carrying the same slug are the members of one conflict.

```json
"ambiguity": {
  "question": "…",
  "conflict": "points-open-to-an-entering-man",
  "fate": "decision",
  "decision": "docs/decisions/0006-the-general-rule-governs-entry-and-full-means-adversely-full.md"
}
```

Absent on an ambiguity that is a gap rather than a contradiction — which is most of them.
`must-play-whole-throw` and `game-value` are ambiguous because the corpus did not say, not
because it said two things, and they carry no slug.

Four rules, all checkable, enforced by the `conflicts` check:

1. **`conflict` is a non-empty slug inside an `ambiguity` block.** It cannot appear on an
   entry that is `clarity: clear`, because `exclusions` already requires the block to be
   present exactly when the clarity is `ambiguous`. A conflict is a species of ambiguity under
   0005 B, not a relation that stands beside it.
2. **A conflict has at least two members.** A slug carried by one entry records a
   contradiction with nothing, and is what a typo and a deleted counterpart both look like.
3. **Every member of a conflict has the same `fate`.** One question cannot be both settled and
   declined. This is the failure 0005 B names — one side decided and the other left open —
   stated in the form a check can read.
4. **Where that fate is `decision`, every member names the same record.** 0005 B's rule,
   now enforceable because rule 1 gives it a set to range over.

### Why a grouping key rather than a relation

**Because the fact is a grouping.** The conflict is the question; the entries are where the
corpus answers it. Naming the question is a more faithful record than enumerating the edges
between the answers, and `points-open-to-an-entering-man` tells a reader what the argument is
about in a way `conflictsWith: ["legal-destination"]` does not.

**Because a key cannot be malformed in the way a relation can.** #25's own acceptance
criteria include "the relation is symmetric" — a check that can only report an asymmetry
after someone has written one. A shared key is symmetric and transitive by construction;
there is no half-declared edge to detect. **A shape that cannot express the error beats a
check that catches it**, and this repository has three checks in `check-map.py` that exist
only because a field admits a state the spec forbids.

**Because it scales the way the instance does.** Three members require three declarations,
not six; a fourth entry joining the conflict edits one entry, not four. Under a symmetric
pairwise list the cost of adding a member is quadratic in a field a human maintains by hand,
which is how a list ends up half-updated.

### Why inside `ambiguity`

#25 argues against this placement: "a conflict is not the only reason two entries relate, and
*these two sentences disagree* is a different fact from *this entry is ambiguous*."

The first half is true and does not apply. This field records no relation in general; it
records **which ambiguity this is**. If some other reason for two entries to relate is found
later, it earns its own field on its own evidence — which is exactly what 0003 did rather than
overload `dependsOn`.

The second half is false under 0005 B. A corpus that says it twice, differently, *is*
ambiguous — that is the whole of section B, and it is why the kernel gains no
`CorpusDisagreesWithItself` reason. The `question` on each of these three entries already
states both readings; all `conflict` adds is that the three questions are one question.
Putting the slug outside the block would let a `clarity: clear` entry declare itself in a
conflict, which 0005 B forbids and which `exclusions` could then no longer catch without a
new cross-field rule.

#25's analogy to `dependsOn` before 0003 runs backwards. `dependsOn` was one field carrying
**two** relations, implementation order and runtime reachability, and 0003 split them.
`ambiguity` carries one fact — this entry's ambiguity — of which the conflict slug states a
property.

## Alternatives considered

**`ambiguity.conflictsWith`, a symmetric list of ids** (#25's proposal). Rejected on the
evidence above: pairwise edges do not denote the set the rule ranges over; the one instance is
a star and not a clique, so the members are reachable only by an unsound closure; symmetry
becomes something to check rather than something that cannot fail; and maintenance is
quadratic. It is the shape every other relation in this schema has, which is the strongest
thing that can be said for it — and `dependsOn` and `gatedBy` really are relations, edge by
edge, where this is not.

**An entry-level `conflictsWith`, outside the `ambiguity` block.** Rejected for the same
reasons plus one: it separates the conflict from the `question` that states both readings, so
a reader of the entry learns that it conflicts with something without learning what about, and
`exclusions` loses the guarantee that a conflict member is an ambiguous entry.

**A map-level list of conflicts**, each naming its members and its decision:

```json
"conflicts": [ { "id": "…", "members": [ … ], "decision": "…" } ]
```

Genuinely attractive, because a conflict really is a fact about a set and a map-level record is
where a fact about a set belongs; and because it makes "every member names the same record"
true by construction rather than checked. Rejected on three counts.

*It moves the fact off the entry, and the entry is the unit everything downstream consumes.*
`corpus-map.md` is explicit that an agent is dispatched against an entry and gets "one concern,
a citation, its dependencies, and a statement of what evidence would settle it". An agent
handed `enter-from-bar` would have to scan a separate table to discover its reading was
contested. 0004 decided this exact question for adapter reach — the title is *adapter reach is
a property of the entry* — and the argument transfers: a property of an entry that a reader of
the entry cannot see is a property the reader does not have.

*Truth by construction here is truth relocated, not truth gained.* `fate` is and must remain a
property of the entry: it says what the engine returns when *that entry* is reached. So a
map-level record naming a decision does not stop an entry from carrying `fate: unresolved`
while the conflict says `decision`. The drift 0005 B exists to prevent survives the move; only
its location changes, and a cross-check between the two places is needed anyway. Given that,
the key form needs one place where the list form needs two.

*Two places to update is an error the key form cannot make.* Under the list, adding an entry to
a conflict means editing the entry and the list; the failure is a membership list naming an
entry whose own block says nothing. That is detectable, but rule 2 above shows the key form's
equivalent failure — a slug with one member — is the *same* detection with none of the
duplication.

The brief for this decision recorded that 0003 had rejected a map-level list for `gatedBy`.
It did not: 0003's rejected alternatives are no field at all, a `precondition` holding the
condition, a free-text `phase` string, and a flag on `dependsOn` edges. The argument above is
made here for the first time.

**Derive the conflict from a shared `ambiguity.decision` path.** Rejected: it makes 0005 B's
rule true by definition and therefore unfalsifiable. Every member of a derived group names the
same record because naming the same record is what put them in the group. It also cannot
represent a conflict whose fate is `unresolved`, which has no record to group by and is a
fate 0005 explicitly permits for a conflict.

**Leave it unenforceable and keep the honest `NOT VERIFIED`.** The status quo, and defensible
— a gate that reports what it cannot prove is the second-best outcome, and this repository
prefers it to a false `ok`. Rejected because the checker's noise is permanent: every map that
ever settles a conflict by decision fails its own gate forever, and a gate that always fails
stops being read.

## Consequences

**`conflicts` becomes a check.** It reports `ok` on a map whose conflicts are well-formed,
`fail` on one that breaks any of the four rules, and skips without failing the run only on a
map where no entry carries a slug. The trigger changes: the old check had subject matter
whenever any entry carried `fate: decision`, which was over-broad — `fate: decision` does not
imply a conflict, because a plain gap can be settled by a decision too.

**Three backgammon entries gain `conflict: "points-open-to-an-entering-man"`**, and the
backgammon map's `check-map.py` run goes from 10 ok / 2 not-verified / **exit 1** to 11 ok / 1
not-verified / **exit 0**. The remaining skip is `status`, which has nothing built to look at in
the factory's copy of the map and so skips without subject matter. It is the first run of that
gate to pass.

**Nothing detects a conflict nobody noticed.** A mapper who reads `enter-from-bar` and never
turns back three sentences to `legal-destination` writes two `clarity: clear` entries and a
map that validates. That is the same class of failure as an incomplete `gatedBy` list (0003)
and a mapper who stopped reading (0004's amendment,
[#20](https://github.com/brandonifco/rules-factory/issues/20)), and no field has ever reached
it. What this decision buys is that a conflict **someone recorded** cannot be half-settled.

**The slug has no registry and is not validated against anything.** Two mappers could name the
same conflict differently, which splits it into two singletons — and rule 2 catches that,
which is the one way this field differs from `beyondAdapter.modality`, deliberately left open
by 0004 with nothing to catch a divergence. A typo is a singleton, and a singleton fails.

**A conflict spanning two corpora is unrepresentable, and is not a thing that has been seen.**
The slug groups entries within one map. Two corpora disagreeing with each other is a different
fact — the manifest's `references` is where a second corpus is named at all — and inventing a
shape for it from zero instances is the mistake 0004 avoided with `modality`.

**One member is one member, even when the corpus repeats itself harmlessly.** A corpus stating
the same rule twice in *compatible* terms is not a conflict and gets no slug; `clarity` stays
`clear`, because the corpus still determines exactly one answer. Nothing checks that
distinction, and it is a judgement, not a lookup.
