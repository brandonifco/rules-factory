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

**May it be committed?** This is a property of the corpus's licence, not a house style, and
the two existing engines answer it in opposite directions and are both right. A commercial
rulebook is `never-commit`: the repository holds its hash and its metadata and nothing else.
A CC-BY SRD or a public-domain statute is `pin-in-repo`: committing it is what makes the
engine reproducible without a licence. Getting this wrong is a legal problem in one
direction and a reproducibility problem in the other.

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

**Cite, do not copy.** The map records where a rule lives and what it is called. It does not
reproduce the corpus. For a licensed corpus that is a legal requirement; for every corpus it
is a discipline that keeps the map reviewable.

**Do not classify while walking.** A first pass that is simultaneously deciding value versus
operation, in scope versus out, produces worse results at both. Enumerate first.

## Phase 3 — Classify

Each entry gets three verdicts.

### Value or operation

Does the corpus state a **fact** or a **procedure**?

A fact is a value: a table of thresholds, a list of conditions, a creature's statistics, a
contribution limit for a given year. Values live in the engine's `Data` layer. They are
transcribed and verified against the source, and the whole table is verified, never a
sample — a table is exactly the kind of thing where a spot check passes and the transcription
is still wrong.

A procedure is an operation: how a test resolves, how damage applies, how a limit is
computed. Operations live in the `Rules` layer and consume values.

When an entry is both — a procedure with a table inside it — it is two entries with a
dependency between them. This is the most common decomposition error: a single entry that
needs "and" in its description is two entries.

### In scope or out

Out-of-scope is a *recorded* verdict with a reason, not an omission. An entry ruled out is
still in the map, marked, and becomes `OutsideCurrentScope` if an engine operation can reach
it. A rule that is simply absent from the map is indistinguishable from one nobody read.

### Clear or ambiguous

Clear means: for every valid input, the corpus determines exactly one answer. Anything else
is ambiguous, and **the implementer does not resolve it.** See Phase 4.

Be suspicious of "clear". Totality is the claim that needs justifying; ambiguity is the
default. An entry marked clear should be able to say *why* it is total.

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
- **Source** — the locator, verbatim from the entry.
- **Dependencies** — the entries this one depends on, which determine order. Damage after
  attack; the limit after the table it reads.
- **Acceptance criteria** — observable conditions, derived from what the entry claims.
- **Required evidence** — what must be demonstrated. Where the corpus prints a finite table,
  the whole table, not a sample.

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

**Preserve determinism deliberately.** Changes to random consumption, ordering, serialization
or identity are compatibility events. An extra draw shifts every later result.

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

## Phase 8 — Close the entry

The entry's status advances, and it records which ruleset revision implemented it. That is
what makes the map a live artifact rather than a plan: at any moment it says what the engine
covers, what it deliberately does not, and what it cannot yet answer — which is the same
question `UnresolvedReason` answers at runtime, from the other side.

## What this method refuses to do

**It does not resolve ambiguity by implementation.** Phase 4 is not optional.

**It does not accept an uncited rule.** Not in the map, not in the code, not in an
unresolved result.

**It does not treat a passing test as conformance.** A test proves the code does what the
test says. Phase 7 is what connects that to the corpus.

**It does not let a corpus be read informally.** Everything goes through a bounded,
hash-verified extract, so every reader sees the same bytes produced the same way and no one
works from memory of the book.
