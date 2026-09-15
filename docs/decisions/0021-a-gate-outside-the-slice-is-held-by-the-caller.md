# 0021 — A gate outside the map's slice is out of scope, and whether it holds is the caller's to state

## Status

Accepted — 2026-09-14. Records the fix for
[#61](https://github.com/brandonifco/rules-factory/issues/61), raised by the Part 107 blind second
mapping ([0014](0014-a-map-is-checked-by-a-blind-second-mapping.md)). Brandon chose the approach:
the map records waivers rather than ignoring them. **Extends
[0003](0003-a-phase-gate-names-a-rule-not-a-condition.md) and
[0011](0011-a-gate-has-a-direction.md)** to a stateless corpus, and adds a runtime reading to the
correspondence table without adding a row. **Reverses one rejected alternative of
[0010](0010-whose-fact-it-is-does-not-decide-the-kind.md)**, *"Add a § 107.200 entry while there"*,
which was rejected as scope creep while § 107.200 was reached only by § 107.29(d)'s pointer. A gate
that reaches 27 entries is not creep.

## Context

§ 107.205 lists the regulations a certificate of waiver issued under § 107.200 may authorize
deviation from: § 107.25, § 107.29(a)(2) and (b), § 107.31, § 107.33, § 107.35, § 107.37(a),
§ 107.39, § 107.41, § 107.51 and § 107.145. A holder "may deviate from the regulations of this part
to the extent specified in the certificate of waiver" (§ 107.200(d)(1)). While a waiver holds, the
rules it covers do not apply, which is what `suspendedBy` records.

Two things stopped the map recording it. `suspendedBy` holds entry ids, and §§ 107.200 and 107.205
are in subpart E, outside a slice of twelve subpart B sections. And the method said a stateless
corpus has no gates: *"Both Part 107 maps carry neither field on any entry"*, in `corpus-map.md`,
in `method.md` and in 0003. The blind mapper wrote the same sentence into the `note` of eleven
entries instead; the reference map said nothing about waivers.

The issue asked three questions: is a waiver a gate at all in a stateless corpus, or a fact the
caller supplies; if a gate, how an entry names a rule outside the slice; and whether the Part 107 map
should carry it now.

## Decision

### 1. A waiver is a gate, and its gate is the rule that lists it

0003's test is whether the corpus **states** a rule that governs reachability. It does: § 107.205,
under § 107.200(d)(1). The rule that makes § 107.41 unreachable while it holds is written down, has a
locator and can be quoted. That the condition is not engine state does not matter; 0003 put the
condition in the engine and kept only the rule in the map. "A stateless corpus has no phases" stays
true. "A stateless corpus has no gates" was an inference from it, and it is withdrawn.

### 2. A rule outside the slice is named by a `scope: out` entry

The shape `subpart-d-categories` already has for § 107.39(c). The Part 107 map gains two entries,
both `scope: out` and `status: declined`, each quoting its whole section:

- **`waiver-policy`**, § 107.200: the Administrator's finding, the request, the additional
  limitations, and the holder's deviation.
- **`waivable-regulations`**, § 107.205: the list. `dependsOn: [waiver-policy]`, and its lead-in's
  *"pursuant to § 107.200"* resolves to `waiver-policy`, as `waiver-policy`'s *"specified in
  § 107.205"* resolves back. (j)'s *"Section 107.145"* resolves to `subpart-d-categories`, which
  declines subpart D whole. Each other item resolves to the entry that states the listed regulation
  whole, or to its lighting rule for (b). *"Section 107.25"* is declared twice, because no one entry
  states both of its limbs.

Every in-scope entry whose locator states a regulation on the list names `waivable-regulations` in
`suspendedBy`: 27 entries. The judgement, paragraph by paragraph, is in `waivable-regulations`'
`note`. The two entries that cite waivers without being suspended by one, `night-waiver-bar` and
`night-waiver-termination`, now resolve *"under § 107.200"* to `waiver-policy` rather than
recording it as unmapped.

`suspendedBy` names `waivable-regulations`, not `waiver-policy`. The list decides *which* rules a
waiver can reach, which is what an edge claims; § 107.200 is what the list depends on.

### 3. Whether a waiver holds is a fact the caller states. It is not `kind: assertion`

The gate's rule is in the corpus. Whether it holds is not, and nothing the engine computes settles
it. Is that a caller-supplied fact or an assertion? 0008's gates and
[0010](0010-whose-fact-it-is-does-not-decide-the-kind.md) answer it without amendment:

- **Gate 1.** Does applying § 107.205 require fixing a threshold, degree, value or case the corpus
  left open? No. What the caller must supply is that a certificate was issued and what it authorizes
  deviation from. That is a fact the rule *tests*, like "prior authorization from Air Traffic Control"
  in `airspace-authorized`, and a fact a rule tests is a parameter and gets no entry.
- **Gate 3.** Even read as an open term, the determination is not the caller's.
  *"If the Administrator finds that a proposed small UAS operation can safely be conducted"* is a third
  party's determination and a separate act, and gate 3 routes that away from `kind: assertion`. The
  certificate is not a corpus that can be admitted either: it is issued to one operator, and its terms
  are not published text. So it is not `definedElsewhere`.

So a waiver is a delegated determination whose **output** reaches the engine as a caller-supplied
fact. What the engine owes it:

- **It demands the fact and never infers it, in either direction.** Defaulting to "no waiver"
  convicts a holder. Defaulting to "waiver" excuses everyone. A gate is the one input whose absence
  changes *which* rule applies rather than what a rule returns, so a missing answer is a missing input,
  never a default.
- **It records the statement with the outcome and attributes it to the caller**, because the outcome
  turns on it and the engine cannot check it. These are the obligations row 8 already imposes on an
  assertion. They are borrowed; the kind is not. 0010 ruled that whose fact it is does not decide the
  kind, and here it does not.
- **Where the caller states that a waiver covering the rule holds**, the suspended entry answers
  `OutsideCurrentScope` and cites `waivable-regulations`. What the operation then requires is "the extent
  specified in the certificate" and its "conditions or limitations" (§ 107.200(d)), and those are out of
  scope. This is row 1, reached through the edge.
- **Where the caller states that none holds**, the entry is evaluated as though it had no gate.

### 4. The schema needed no change

`suspendedBy` can already name a `scope: out` entry. `references` resolves it. `absent` forbids an edge
only to an absent rule, and that ban is right: an absent rule can never hold, and an out-of-scope one
can. What was missing was the runtime reading above. The correspondence table classifies an entry by
its own fields and said nothing about an entry whose gate is out of scope. The reading goes in
`corpus-map.md` beside the table, as `absentFrom`'s did, and adds no row.

## Alternatives considered

**Leave waivers to the caller entirely: no edge, no entry.** The status quo, which the blind mapper
recorded eleven times in prose. Rejected. An engine built from the map would evaluate § 107.41 for a
waiver holder and return a violation, and nothing in the map would tell its implementer that the
corpus provides otherwise. It is the `full-table-suspension` omission (0011) in a regulation: every
test of the rule passes and the rule answers a question the corpus closed.

**`kind: assertion` entries, one per waivable regulation ("a waiver authorizing deviation from
§ 107.41 is held").** Rejected by gate 3 and 0010, above. It would also give the map entries no
sentence states. The corpus says what a waiver *may* authorize, never that one is held, so the
evidence would quote a list and claim a fact.

**A new field naming a gate outside the slice**, for example `suspendedOutside: "§ 107.205"`.
Rejected. A citation in place of an id is the prose carrier 0003 rejected. And `scope: out` entries
already exist to be named; `subpart-d-categories` has been named from `dependsOn` since the first trial.

**One `scope: out` entry per paragraph of § 107.205.** Considered, since it would make each edge name
its paragraph. Rejected. Each paragraph is an item of one printed list, and its lead-in is what makes
the item a rule; quoting a paragraph without the lead-in quotes a section heading. And the entry the
edge is on already states which regulation it is, so the paragraph is one lookup away. The whole list
is one span, which is how the method treats a finite table.

**Admit subpart E into the slice.** Out of proportion to the issue. The rules would need mapping,
not just citing, and their substance is an instrument the corpus does not contain.

## Consequences

**The claim that a stateless corpus carries no gates is withdrawn** from `corpus-map.md` and
`method.md`. It stands in 0003 and 0011 as written, marked by this record.

**Nothing checks the edges.** A waivable rule with no edge, or an edge on an entry § 107.205 does
not list, passes `check-map.py`. That is the same limit 0011 names for every gate. Here each edge can be
checked by hand against one list, and the independent verdict in
`examples/faa-part-107/review.json` did that for this change.

**Nothing checks that an engine demands the waiver.** The factory's generated contract types what the
map fixes, and a gate's state is not a field of any entry. An engine declares the input on the
handler, as it does an operation's inputs (#93). Whether it declines to default is checked in the
engine's own tests, which the backlog item asks for: *"A test shows the rule does not apply while
`waivable-regulations` holds."*

**The 2020 map is not changed.** `faa-part-107-temporal` maps the 2020-01-01 text. Its § 107.205
differs: the 2021 amendment added § 107.145 and narrowed § 107.29 to (a)(2) and (b). It carries a
legacy review exemption. Recording its waivers means reading that text, and belongs with its review.

**`FaaPart107` stays at 2.0.0**, which is set and not published (0015). Two entries and 27 edges land
in it.
