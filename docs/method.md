# The method

The rules for turning a written ruleset into a deterministic engine. It applies whether the
corpus is a tabletop rulebook, a board game's rules, a statute, or a regulation — the
subject matter changes what the rules *say*, not how you get from prose to code.

This is the document agents work from. It is prescriptive on purpose.

## The one idea

Between "here is a corpus" and "here is an engine" sits a third thing: **the corpus map** —
a structured entry for every rule the corpus states. Everything upstream produces it;
everything downstream consumes it. Agents are never dispatched against the corpus. They are
dispatched against entries in the map.

The map is specified in [corpus-map.md](corpus-map.md). The rest of this document is how to
build one and what to do with it.

**The map's vocabulary and the engine's runtime vocabulary are the same five categories.**
An entry that is unimplemented is exactly what `UnresolvedReason.UnsupportedRule` means at
runtime; one ruled out of scope is `OutsideCurrentScope`; one whose corpus is ambiguous and
undecided is `RequiresInterpretation`; one whose algorithm exists but whose table has not
been transcribed is `MissingRulesData`; one whose parts exist but whose combination does not
is `UnsupportedInteraction`. The map is the design-time view of the engine's honesty, and
the engine's unresolved results are the runtime view of the map. If those two ever disagree,
the map is wrong.

## Phase 1 — Admit the corpus

Before anything is read, the corpus is pinned. Four questions, answered in the corpus
manifest and never re-answered informally:

**What is it?** A stable identifier — `srd-5.2.1`, `cfr-26`, `core-rules`. Ordinal and
case-sensitive; it is the name every citation will use.

**What exactly?** A content hash, and **what the hash covers**. These are two facts, not
one. Hashing a PDF's bytes, its extracted text, and a roster of the ids it defines are all
legitimate and all different; a baseline that records only the digest cannot tell you which
was done. Declare the derivation alongside the digest.

**As of when?** A corpus that is revised over time — a regulation, an errata'd rulebook —
is pinned to a date. A corpus that is a fixed printing has no temporal dimension and is
pinned without one. Absent means "timeless", never "unknown": if the corpus is revisable and
you do not know the date, the baseline is not pinned and the work cannot start.

This pins *which text is in force* and nothing else. A rule may contain dates of its own —
a requirement that applies only to training completed after a given day, an authorisation
that expires. Those are ordinary operations over a date the caller supplies, and are not
corpus versioning. Two different temporal things, easily conflated.

**May it be committed?** This is a property of the corpus's licence, not a house style, and
the two existing engines answer it in opposite directions and are both right. A commercial
rulebook is `never-commit`: the repository holds its hash and its metadata and nothing else.
A CC-BY SRD or a public-domain statute is `pin-in-repo`: committing it is what makes the
engine reproducible without a licence. Getting this wrong is a legal problem in one
direction and a reproducibility problem in the other.

**How is it verified, and may the map quote it?** The same question, asked for whoever consumes
the map — an engine built from it included. A committed corpus is `committed-copy` and anyone
can check its hash. A corpus that is not committed is `local-copy`: whoever holds a legal copy
verifies locally, and every other run — CI above all — reports `NOT VERIFIED` with the reason,
never `ok`. And because a map quotes its corpus sentence by sentence, whether it may do so at all
is declared too: `quotation: verbatim`, or `withheld` where the licence forbids it. Both are
answered per corpus in the manifest, by a person, never inferred. See
[0013](decisions/0013-verification-posture-belongs-to-the-corpus.md).

**Record what the adapter cannot reach.** A corpus states its rules in more than one
modality. The starting position of a backgammon board, in a trial corpus, is given entirely
as an illustration — fully determined, and invisible to a plain-text adapter. That is not a
reference to another corpus, so the references list below does not describe it; it is a
limit of the adapter chosen in this phase. An entry beyond the adapter's reach is declined
as `MissingRulesData` and carries `beyondAdapter`, naming the reader that failed and the
modality that defeated it — structurally, in the entry, not in a sentence the next reader has
to parse. The field and its limits are specified in [corpus-map.md](corpus-map.md); the
argument is [0004](decisions/0004-adapter-reach-is-a-property-of-the-entry.md).

Choosing the adapter is therefore choosing which rules the engine can reach, and it happens
here, before anything is read. A plain-text adapter over a PDF rulebook will lose the tables
a rules engine most needs, and it will lose them without complaint: the adapter returns text,
the text is missing a column, and nothing says so. `beyondAdapter` records a limit a human
recognised. It does not find one nobody recognised.

**Record what it defers to.** A corpus routinely defines its own terms by reference to
another — a regulation citing a different title, a rulebook citing a supplement, a statute
citing a schedule. Those references are the boundary of any engine built from it, and the
manifest should name them as referenced-but-not-admitted rather than leave the boundary to
be inferred from whichever entries happen to be declined. In one trial slice, a quarter of
the sections deferred their meaning to a corpus that had not been admitted.

Choose the adapter that can read the format, and the locator grammar it produces. Page
numbers for a printed book; designations like `§ 1.401(k)-1(b)(4)(ii)` for a regulation;
numbered rules like `4.2.1` for a board game. The kernel does not privilege any of these and
neither should the map.

## Phase 2 — Map the corpus

Walk the corpus and write an entry for every rule it states. The walk is bounded: read in
slices small enough to hold, never the whole corpus at once.

**Every entry carries a locator.** An entry without one is not an entry. This is the single
rule that makes the map trustworthy, because it is the one an agent is most tempted to skip
when a rule "obviously" says something.

**The one exception is a fact no sentence states.** Where two or more rules the corpus does
state entail an answer the engine must give — a hit pays the single stake, because a gammon and
a backgammon are both paid as multiples of it — that answer is its own entry, carrying
`derivedFrom` and no locator or quote: its sources' citations are its citation. Do not put the
inference inside one of the source entries, where it passes as stated. See
[0012](decisions/0012-a-fact-the-corpus-implies-is-a-derived-entry.md).

**Cite, do not copy.** The map records where a rule lives and what it is called. It does not
reproduce the corpus. For a licensed corpus that is a legal requirement; for every corpus it
is a discipline that keeps the map reviewable.

**Quote before you summarise.** One bounded span per entry is not reproducing the corpus; it
is what makes the citation checkable at all. `evidence` holds the contiguous verbatim passage
that states the rule, and the mapper's summary of what a test must demonstrate goes in `note`
beside it. Write the quote first and the summary from it — not the other way round. A mapper
who summarises first is writing from what they remember reading, and there is then nothing in
the entry that a tool or a reviewer can hold against the page. Thirteen of the backgammon
map's twenty-four citations were wrong by a page or two, and survived a mapping trial, a build
and a review, because every one of them was summarised. See
[corpus-map.md](corpus-map.md#evidence-is-the-corpuss-words-not-the-mappers). Where a licence
forbids the quote, the entry records that the span is withheld; it does not put a summary in
the field and leave the citation looking verified.

**A corpus that defines its own terms is stating rules, and the definitions are entries.**
Twelve points to a table named ace through six, inner tables numbering from the far end and
outer tables from the bar, men travelling "from the ace point in his opponent's home table
towards the like point in his own" — these read as preamble and are load-bearing. Without them
the entries that use the vocabulary cannot be interpreted at all, and nothing else in the map
says a board has twenty-four points or that the course has a direction. Both were missed on the
first pass of the second trial for the same reason: a mapper hunting for rules reads past
vocabulary. `point-designations` and `direction-of-travel` are the instances
([#13](https://github.com/brandonifco/rules-factory/issues/13)).

**Advice is not a rule, and it is not always in its own section.** A corpus usually
separates guidance from obligation — but not reliably, and not sentence by sentence. "It is
always an object to do this" sits in the middle of a trial corpus's movement rules. Drop
advice, and note in the entry that you dropped it: an agent enumerating mechanically will
otherwise map it as a rule, or drop it silently, and silently is worse because the next
reader cannot tell which happened.

**Record what gates an entry, separately from what it depends on.** A corpus with turn
structure has rules that only apply in a phase: bearing off begins once every man is home;
a man on the bar suspends every other move. That is a different fact from implementation
order, and it goes in one of two fields by direction: `enabledBy` for a rule that makes this
one reachable, `suspendedBy` for a rule that makes it unreachable while it holds. Both hold
**entry ids and nothing else** — the rule that governs reachability, not the condition. Write
the condition and you have written a second implementation of the rule in a format nothing
executes. A gate is itself a rule the corpus states, so it already has an entry; if the gate you
want to record has none, the finding is that the map is missing an entry. See
[0003](decisions/0003-a-phase-gate-names-a-rule-not-a-condition.md) and
[0011](decisions/0011-a-gate-has-a-direction.md).

**Ask of every gate which entries it reaches, not only the obvious ones.** A rule that suspends
a player's whole turn reaches the throw and everything a throw leads to; the backgammon map
recorded none of that for `full-table-suspension` through a trial, a build and a review, and
the omission changed every later throw of a seeded game while passing every legality test.

A stateless corpus will produce none of these, and that is the right outcome rather than an
oversight. Both Part 107 maps carry neither field on any entry.

**Do not classify while walking.** A first pass that is simultaneously deciding value versus
operation, in scope versus out, produces worse results at both. Enumerate first.

## Phase 3 — Classify

Each entry gets three verdicts.

### Value, operation, or assertion

Does the corpus state a **fact**, a **procedure**, or **a condition the engine cannot
check**?

A fact is a value: a table of thresholds, a list of conditions, a creature's statistics, a
contribution limit for a given year. Values live in the engine's `Data` layer. They are
transcribed and verified against the source, and the whole table is verified, never a
sample — a table is exactly the kind of thing where a spot check passes and the transcription
is still wrong.

A procedure is an operation: how a test resolves, how damage applies, how a limit is
computed. Operations live in the `Rules` layer and consume values.

An **assertion** is neither: an **open term the corpus deliberately delegated, having said
what it is measured against or what set of values it may take**. A regulation requiring that a
pilot was able to see the aircraft *"in order to"* four stated purposes, or that there was
*"enough available power … to operate for the intended operational time"*, states a real
and binding rule that no computation settles. What an engine owes an assertion is: **demand
it, attribute it to whoever made it, record it with the outcome, and never infer it.** An
engine that quietly defaults an unasserted condition to true has substituted its own
judgement for the person's.

*Judgement the corpus deliberately delegates* looks ambiguous and is not. "If the pilot
determines it would be in the interest of safety" is not a defect in the text — the corpus
is perfectly clear that the decision belongs to the pilot. Classifying it as ambiguous would
report a deliberate delegation as a defect.

**Whose fact it is decides nothing.** Until
[0010](decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md) this section also listed
*"facts about the physical world"* — whether it was raining, whether a person was under
cover — as assertions. **That is withdrawn.** It is true that the engine consumes such
facts and does not derive them, and false that they are therefore rules: the airspace class,
the groundspeed and whether a visual observer was used are **caller-supplied parameters that
get no entry at all**, which is Phase 4's gate 1 and what `corpus-map.md` rules for
`airspace-authorized`. § 107.39 shows both answers one sentence apart, on two facts about
the same third party: *"directly participating"* states no measure and is a gap, while
*"reasonable protection **from a falling small unmanned aircraft**"* states one and is an
assertion. **The measure decides; the source never did.**

When an entry is both value and operation — a procedure with a table inside it — it is two
entries with a dependency between them. This is the most common decomposition error: a
single entry that needs "and" in its description is two entries.

### In scope or out

**The corpus bounds the engine, not the subject.** A map can only contain what its corpus
states. A 1909 games text has no doubling cube; an engine built from it is a 1909 engine,
and that is a correct outcome rather than an incomplete one.

Out-of-scope is a *recorded* verdict with a reason, not an omission. An entry ruled out is
still in the map, marked, and becomes `OutsideCurrentScope` if an engine operation can reach
it. A rule that is simply absent from the map is indistinguishable from one nobody read.

**Three states, and the map must tell them apart.** Read and declined; read and *not in the
corpus at all*; and nobody looked. The first two are both `scope: out` and the third is a
missing entry, so until
[0009](decisions/0009-absence-is-a-verdict-with-evidence.md) the map spelled all three the
same — and this section asked for the difference in a **reason string**, which is the carrier
0003, 0004 and 0005 each rejected. It is now structural:

- **Read and declined** — `scope: out`, quoting the passage declined.
- **Not in the corpus** — `scope: out` plus `absentFrom`, naming the terms you searched for,
  and citing and quoting **the passage the rule would be in**. `check-locators.py` searches the
  declared extent for those terms and fails the entry if one turns up. Writing this entry is
  more work than declining a rule, deliberately: every instance of this failure so far has been
  a mapper who stopped reading.
- **Nobody looked** — no entry, and two things narrow it. The map's `extent`, every page or section of
  which must be reached by some entry's located evidence; and `crossReferences`, which turns
  the corpus's own pointers into obligations.

**`scope` is decided per rule, never per section, and excluding a section requires reading it
first.** A section is a unit of the corpus's layout; `scope` is a judgement about a rule. The
backgammon map excluded *Hints for Play* wholesale as advice and so lost the only authority in
the corpus for how many faces a die has
([#20](https://github.com/brandonifco/rules-factory/issues/20)). Two entries citing one section
with opposite verdicts is the correct shape, not a conflict.

**Follow every cross-reference the corpus makes.** *"Except as provided in paragraph (d)"* is a
reference, and a reference is an entry or a recorded reason there is none. Declare it in
`crossReferences`, quoting the words that make it.

### Clear or ambiguous

Clear means: for every valid input, the corpus determines exactly one answer. Anything else
is ambiguous, and **the implementer does not resolve it.** See Phase 4.

Be suspicious of "clear". Totality is the claim that needs justifying; ambiguity is the
default. An entry marked clear should be able to say *why* it is total.

**An amendment can change what an entry *is*, not only what it says.** In the third trial, a
flat prohibition on night flight was amended into a conditional permission turning on "a flash
rate sufficient to avoid a collision", which states no rate.

**Withdrawn, in place:** this section said the older rule was "perfectly clear and trivially
implementable", and concluded that *an amendment can turn a rule the engine computes into one
that demands a caller's assertion*. **It never had that premise.** § 107.3 defines six terms
at the 2020 date and seven in 2026, and *night* is not among them at either; the 2020 rule —
*"No person may operate a small unmanned aircraft system during night"* — **is** the
undefined word and nothing else. Both entries are now `definedElsewhere` against 14 CFR
§ 1.1 and both decline with `MissingRulesData`
([#33](https://github.com/brandonifco/rules-factory/issues/33)).

**What the corpus supports instead:** the amendment **added a delegated standard to a rule
that was already undecidable, for a different reason, at both dates.** That is weaker than the
claim withdrawn, and it is the restatement
[examples/faa-part-107-temporal](../examples/faa-part-107-temporal/README.md) carries. What
survives untouched is the reason a map is a statement about one text: under
[0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md) the newer entry gains an
assertion dependency (`flash-rate-sufficient`) that has no 2020 counterpart, without the
engine changing at all. Re-mapping a revised corpus re-asks `kind`, `clarity` and the
dependency graph of every entry it touches rather than carrying the previous verdict forward.

The claim was stated three times and corrected three times, each time by someone looking at
`clarity` — **the one field nothing compares against the corpus.** That is the more durable
finding, and it is why trial 1's undefined-term sweep exists.

## Before the map is used — a blind second mapping

Mechanical checks prove a quote is *where* an entry says, never that it *says* what the entry
says; they caught 1 of 15 injected comprehension errors. So no map goes on to Phase 4 until a
second mapping of the same slice has been compared with it and every disagreement resolved. See
[0014](decisions/0014-a-map-is-checked-by-a-blind-second-mapping.md).

**Who maps.** Someone who has not seen the first map, its notes, its decision records or its
findings — and does not get them through a prompt, a brief or a review thread that states the
first mapper's reading.

**What they get.** The pinned corpus extract, [corpus-map.md](corpus-map.md) and this document,
**with every worked example drawn from the corpus under mapping removed.** An example that names
an entry leaks its verdict; so does one rewritten to paraphrase the corpus. Replace examples from
another corpus, or delete them.

**What is compared,** entry against the entry that quotes the same text:

- `kind`, `scope`, `clarity`, and whether `ambiguity` is present;
- `dependsOn`, `enabledBy` and `suspendedBy`, edge by edge;
- whether each side's `evidence` supports its entry — read, not measured by span length;
- entries only one side has.

**How a disagreement is resolved.** Not by vote, and not by deferring to the first map. Each is a
question answered by a quote from the corpus, with its locator: the first map is right, the
second is right, the corpus does not settle it (the entry is ambiguous and goes to Phase 4), or
it is not a disagreement about the corpus (a split, a merge, a choice of span). The map is
corrected to the answer.

**Where the record lives.** Beside the map, committed with the corrected map: one row per
disagreement, with the entry, the field, both values, the verdict and the quote. A disagreement
with no row is unresolved, and the map is not used.

**What it does not catch.** Two mappers who share a misreading agree, and agreement is silent.

**How the review is held to the map.** `review.json` beside the map names the SHA-256 of the map
bytes the review covers and points at the comparison and resolution record. `validate.sh` fails a
map whose bytes no longer match, so a map changed after its review is refused until it is
reviewed again or given a recorded exemption. See
[0017](decisions/0017-a-map-change-carries-a-review-of-its-bytes.md).

## Phase 4 — Decide the ambiguities

An ambiguous entry has exactly two possible fates, and choosing between them is the most
consequential judgment in the method.

**A recorded decision.** The corpus is unclear, and the project rules on what it means. That
ruling is written down as a decision record — the question, the readings considered, the
choice, and the consequences. It is then implemented as if the corpus had said so. This is
the right fate when the engine must produce an answer and a defensible one exists.

**A runtime unresolved.** The engine returns `RequiresInterpretation` and declines. This is
the right fate when no reading is defensible enough to bake in, or when the ambiguity is the
caller's to resolve rather than the engine's.

**A standard is not a gap, and it is not an ambiguity either.** "Well clear", "reasonable
protection", "a flash rate sufficient to avoid a collision" — a regulator who writes these has
not been vague by accident. The standard *is* the rule, chosen over a number deliberately, and
an engine that resolved it to a number would substitute its own rule for the corpus's.

**So it is not a fate at all. It is `kind: assertion`, and it is its own entry.** The corpus
left the degree open and said what it is measured against; the engine's obligation is the
assertion contract from Phase 3 — demand it,
attribute it, record it alongside the outcome, never infer it. Declining with
`RequiresInterpretation` is the wrong answer twice over: it refuses a job the corpus gave the
engine the means to do, and it throws away whatever bounds the corpus *did* state. *"Either
thrice or four times (as may have been agreed)"* is the clearest case — read as an ambiguity,
the engine discards the rule that the multiplier is three or four and nothing else.

Because `kind` is entry-level, split the standard out rather than reclassifying the rule that
consumes it: `night-operation` states a computable rule about training and lighting *and*
defers the flash rate. The standard becomes `flash-rate-sufficient`, an assertion, and
`night-operation` depends on it — the same move as `speed-limit` and `speed-within-limit`.
Decided in [0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md).

**There is no test for recognising one. There is a procedure, and it is three gates in order.**
Five one-sentence tests have failed, three of them after surviving a review; the last two each
agreed with the corpus they were derived from and were refuted on the other. Decided in
[0008](decisions/0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md), which
carries the counts; `corpus-map.md`'s `kind: assertion` section states the same three gates, and
the two documents say the same thing deliberately, because when they did not the maps followed
this one and were wrong.

The gates run only on an entry that is `scope: in` and normative — advice demands nothing of
anybody, and an absent rule has no words to read; row 1 of the correspondence table disposes of
both first.

1. **A blank in the rule, or a fact the rule tests?** Does applying the corpus's words require
   fixing a threshold, degree, value **or case** the corpus did not fix? If not, it is an ordinary
   rule with a caller-supplied parameter, and the parameter gets no entry. *"Either thrice or four
   times"* leaves the multiplier unfixed and is a blank; *"either wholly by moving men forward …
   or partly by the one method and partly by the other"* states every branch and is not. "Or case"
   is what catches a defective enumeration — `game-value`, `must-play-whole-throw` — which is a
   gap without being an open degree.
2. **Unsupplied by the corpus, or only to us?** → `beyondAdapter`, `definedElsewhere`, or a
   conflict.
3. **Whose hands?** The caller's own determination is operative **and the corpus states, in the
   same constituent as the open term, either what the term is measured against or the set of
   values it may take** → `kind: assertion`, and the entry must be able to quote those words from
   its own `evidence`. A third party whose determination is a separate act → not a caller
   assertion. Nobody → a genuine gap, its fate a runtime unresolved.

**Gate 1's parameter and gate 3's assertion are different things, and the difference is not
who supplies the fact.** An engine demands both. Only one of them is a rule. The airspace
class, the groundspeed, whether a visual observer was used — these are facts the rule
*tests*, and gate 1 stops them: **no entry, named in the consuming entry's `note`.** An
assertion is an open term the rule *leaves blank* and the corpus then bounds. § 107.39
states both, one sentence apart and both about the same third party: *"directly
participating"* is a gap, *"reasonable protection **from a falling small unmanned
aircraft**"* is an assertion. Deciding by who could answer would have made them the same, and
they are not. Decided in
[0010](decisions/0010-whose-fact-it-is-does-not-decide-the-kind.md), which closes the half of
[#11](https://github.com/brandonifco/rules-factory/issues/11) 0005 left open by finding that
there is no "facts a person asserts" category: ten of the twenty measured instances are
assertions, six are gaps, and two paragraphs split inside themselves.

**A stated measure may itself be open, and gate 3 does not ask.** *"Considering risks to
persons and property in the **immediate vicinity**"* states what the assessment is measured
against, and the measure carries an undefined degree of its own. Gate 3 asks whether a measure
is stated, not whether it is determinate, so the entry is an assertion. Named by 0010 with two
instances per map, and filed rather than decided.

**The gates do not separate § 107.37(a)'s "unless well clear" from § 107.25(b)'s "sparsely
populated area", and nothing in the corpus does.** Both are open degrees in the `unless` clause
of a prohibition with no measure stated in their own constituent; "well clear" appears once and
§ 107.3 defines neither. The procedure returns a gap for both. Where the project believes such a
term is nevertheless determinate — because practice outside the corpus fixes it — that is a
recorded decision or a `definedElsewhere`, which are the two fates this phase is about. It is
never a `kind`, because a map may not claim to have derived from a text what the text does not
say. `right-of-way` rested on that belief without recording it; it is now split, and
`well-clear` is a gap beside `moving-vehicle-operation`. Four more terms sit in the same
residue — *"effective communication"*, *"working properly"*, *"directly participating"*,
*"secure"* — where the operator is plainly the only person who could answer and the corpus
still states no measure. Being the only possible source is not a reason to reclassify (0010).

**A corpus that contradicts itself is ambiguous**, and its `question` states both readings.
`clear` asserts the corpus determines exactly one answer, and one that states a rule twice in
incompatible terms does not. Every entry bearing on the same contradiction carries the same
`ambiguity.conflict` slug — the conflict is the *question*, not a pair of sentences, and an
entry may answer it without contradicting every other member. A conflict's members share a
fate, and where that fate is `decision` they name the same record; otherwise one side is
settled and the other left open with nothing noticing. See
[0007](decisions/0007-a-conflict-is-a-question-not-a-pair.md).

What is never acceptable is the third option: an implementer picking a reading silently.
That produces an engine that is reproducibly wrong, which is worse than one that is
unreliable, because nothing signals the guess.

**Recorded decisions are the only part of an engine nothing else can inherit.** The
mechanics are transcription; another engine over the same corpus would arrive at the same
code. The rulings on what an ambiguous passage means belong to that engine and that reading.
Treat them accordingly.

## Phase 5 — Generate the backlog

Each entry, or each coherent cluster of entries, becomes one issue. The map has already
supplied most of what an issue needs:

- **Scope** — one concern. If it needs "and", it is two issues, and the map should have
  split them in Phase 3.
- **Source** — the locator, verbatim from the entry, and the `evidence` span it resolves to.
- **Dependencies** — the entries this one depends on, which determine order. Damage after
  attack; the limit after the table it reads.
- **Reachability** — the entries in `enabledBy` and `suspendedBy`, which determine nothing
  about order and everything about what the issue must set up, and what it must show does
  not happen. A phase-scoped rule cannot be exercised
  outside its phase, so an acceptance criterion that ignores the gate is testing a situation
  the corpus does not describe.
- **Acceptance criteria** — observable conditions, derived from what the entry claims.
- **Required evidence** — what must be demonstrated, from the entry's `note`. Where the corpus
  prints a finite table, the whole table, not a sample.

Order the backlog by the dependency graph, not by the corpus's page order. A corpus is
organised for a reader; a backlog is organised for a builder.

## Phase 6 — Implement

The smallest coherent change per issue. The engine's own rails govern the rest, and they are
not this document's business. Three things belong to the method:

**Cite in the code.** Every implemented rule carries its locator into the source, so a
reader can check the implementation against the passage without going through the map.

**Tests are the evidence.** A behavioural claim without a test is a claim. For rules work,
the tests derive their expectations from the corpus — never from the implementation. An
expectation computed the same way as the thing it checks can only confirm that the code does
what it does.

**A derived consequence is discharged as a test, and the entry names the test.** A mapper
working an entry often proves something the entry does not say: that `must-play-whole-throw`
declines in exactly one shape of throw, that the adopted opening throw can never be doublets
because a tie is thrown again, that `bearing-off-highest` is the opposite of what a modern
player expects. That reasoning is not stored as prose in the map. It becomes **a test named for
what it proves** — one that constructs the case and fails if the consequence stops holding —
and the entry names that test — among its `tests`, with the mutation that turned it red, once
the entry is `implemented`. No field holds the reasoning itself. Decided on
[#16](https://github.com/brandonifco/rules-factory/issues/16), for the reason
[0005](decisions/0005-a-field-earns-its-place-by-being-checkable.md)'s rail E and
[0004](decisions/0004-adapter-reach-is-a-property-of-the-entry.md) already gave: prose about a
claim cannot be shown to have gone wrong, and a test can. "This branch is unreachable" will
silently become false the day the opening rule changes; as a sentence it rots, as a test it
fails.

This is different from a derived *entry*
([0012](decisions/0012-a-fact-the-corpus-implies-is-a-derived-entry.md)). A derived entry is an
answer the engine must give that no sentence states, and it follows from two or more rules. A
derived consequence is a property of answers that are each stated — often of one entry alone —
and nobody asks the engine for it; it is what a test asserts about the engine's answers.

**The limit, accepted rather than hidden:** reasoning that does not reduce to a test has nowhere
to go and is lost. Reasoning that cannot be reduced to a check is also reasoning nobody can be
shown to have got wrong.

**Preserve determinism deliberately.** Changes to random consumption, ordering, serialization
or identity are compatibility events. An extra draw shifts every later result.

**State what fixes any list a replay indexes into.** If a recorded game stores a position in a
list — the index of the chosen play among the legal plays — then the order and length of that
list are part of the replay format. The engine states the rule that fixes them where the list is
produced, and ships a test pinning the whole list for at least one non-trivial position, proven
able to fail by permuting it. The kernel stays out: the list is the engine's. Decided on
[#22](https://github.com/brandonifco/rules-factory/issues/22); `hoyle-backgammon` pins
`LegalPlays.For` this way.

## Phase 7 — Verify against the source

Implementation is not the same as conformance, and an author checking their own reading is
not a check.

Extract a **bounded packet** of the exact passages the entry cites — bounded because an
unbounded extract is how a repository accidentally grows a transcription of its corpus, and
how a reviewer's attention is spent on material they will not read carefully.

Review **adversarially**, against the packet, by someone other than the implementer. The
question is not "does this look right" but "does this do what page 48 says, in every case
page 48 covers".

**Record the verdict against the exact commit**, naming the packet it was checked against.
A verdict that is not pinned to a commit stops being true the moment the code changes, and a
verdict that does not name its packet cannot be re-derived.

Be honest about what this proves. Recording a verdict proves accountability — a specific
person or agent checked a specific reading against a specific extract. It does not prove the
reading was right. No mechanism can. What it removes is the ability to skip the step
silently.

## Re-mapping a revised corpus

A corpus that is revised gets re-mapped, not re-read from scratch. The question becomes
"what moved", which is markedly cheaper than "what is here" — a maintained map costs far
less to keep current than to create.

Three things the third trial found, which a re-map must account for:

**A stable id can hide a reversal.** Ids should survive across versions — that is what makes
two maps comparable at all — but stability is exactly what lets an opposite rule keep its
name. Diff entry *content*, never the entry list.

**An amendment reaches into sections it did not add.** A new subpart appeared as a third
exception inside an existing section. Re-mapping only the sections whose text changed caught
it, because that section's text did change; the hazard is a new section referenced by text
that did not otherwise move.

**A text diff and a map diff disagree, and both are right.** A section reworded from "may not
operate" to "may not manipulate flight controls" changed no entry, because the map records
the rule and not its phrasing. The text diff flags it, the map diff does not, and the mapper
has to judge — which is the work, and is not automatable by either diff alone.

## Phase 8 — Close the entry

The entry's status advances, and it records which ruleset revision implemented it **and the
tests that prove it, each with the mutation that was recorded turning it red**. An entry that
cannot name a test that has been seen to fail does not advance to `implemented`; it stays
`mapped`, whatever code exists ([#2](https://github.com/brandonifco/rules-factory/issues/2)),
**and the engine declines it with `UnsupportedRule` until that test exists**
([#47](https://github.com/brandonifco/rules-factory/issues/47)). Code for an unproven entry is not
reachable at runtime. An engine that answers an entry its map calls `mapped` breaks row 2 of the
correspondence table, and the fix is to decline it or prove it, never to list it as an exception.
That is
what makes the map a live artifact rather than a plan: at any moment it says what the engine
covers, what it deliberately does not, and what it cannot yet answer — which is the same
question `UnresolvedReason` answers at runtime, from the other side.

## What an engine owes its map's source, over time

An engine does not own its map. The factory publishes it as a versioned package
([0015](decisions/0015-a-map-is-published-as-a-versioned-package.md)), and the engine
**references it and never copies it**, the way it references `rules-kernel`. A copy that goes
stale does not fail, and it keeps passing indefinitely
([#27](https://github.com/brandonifco/rules-factory/issues/27)). A dependency that falls behind
is visible to every tool that already exists. What the engine owes follows from that:

1. **It depends on one exact version and can prove which one.** It references the package at an
   exact version and restores with a lock file in locked mode, so the bytes it builds against are
   pinned by hash rather than by memory.
2. **It writes only its overlay: `status`, `implementedIn` and `tests`.** These are the build
   facts, and only the engine can know them. Every other field belongs to the map's source. An
   engine that disagrees with an entry's content has a finding to file against the factory. It
   does not get to correct its own copy, because it has no copy.
3. **Its gate merges the overlay offline and checks the result.** Every overlay key names an
   entry in the package, and only the three fields are set. The package's own
   `tools/check-map.py --phase consumer` passes on the merge. The engine runs the checker it
   restored, not a copy, so a change to a status-dependent check reaches it with the next version
   ([#51](https://github.com/brandonifco/rules-factory/issues/51)). The structural checks were run
   before the version existed, and an overlay cannot change their verdict, so the engine does not
   repeat them.
4. **It moves when the source moves, and the version number says how hard that is.** A patch
   changes prose only. A minor adds entries or corrects citations, so the overlay still merges and
   new entries are `mapped`, which is `UnsupportedRule` until built. **A major means an entry the
   engine may have implemented now says something different, or is gone.** Every `implemented`
   claim on an entry the major changed goes back through Phase 7 before it stays `implemented`.
   The merge check fails outright on a removed or renamed entry, which is the intent.
5. **It reports back what only it can see.** Building an engine is the most thorough reading the
   map will get. The backgammon map moved twice in one day because of what its engine found. An
   engine that notices a wrong entry files it upstream and waits for a version. That way the next
   engine built from the same map gets the correction too.

What the engine does not owe: a copy of any checker, or a scheduled job that watches
the factory. The package makes both unnecessary.

## What this method refuses to do

**It does not resolve ambiguity by implementation.** Phase 4 is not optional.

**It does not accept an uncited rule.** Not in the map, not in the code, not in an
unresolved result.

**It does not treat a passing test as conformance.** A test proves the code does what the
test says. Phase 7 is what connects that to the corpus.

**It does not let a corpus be read informally.** Everything goes through a bounded,
hash-verified extract, so every reader sees the same bytes produced the same way and no one
works from memory of the book.
