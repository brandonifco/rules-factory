# 0078 — An engine with an action surface proves it through that surface

## Status

Accepted — 2026-10-08. Records the decision on
[#627](https://github.com/brandonifco/rules-factory/issues/627). **Optional.** It applies only to an
engine that declares an action surface. It adds one engine-owned declaration file, which no engine has
today (decision [0018](0018-every-file-the-factory-writes-has-one-owner.md): an `engine-owned` row,
`acceptance.json`), and one generated test file, emitted only when that declaration exists, which falls
under the existing generated row `tests/{name}.Tests/Generated/*.g.cs`. Every engine produced so far,
the FAA, FRCP and SRD engines among them, declares none and gets nothing: no file, no gate step, no
test. The managed `AGENTS.md` takes recipe 30, for one subsection of its section 7.

## Context

Most engines this factory produces answer requests. A rule is asked a question and resolves, refuses or
declines, and the correspondence tests and each entry's own tests hold that at the entry.

Some engines also expose an **action surface**: a way to create a state, read it, list the actions
legal in it, and apply one. A game engine is the obvious case, though not the only possible one. For
such an engine, entry conformance is not the same as the engine working. A
factory-produced game engine reached every entry's tests green while three things that block
ordinary play were still in it: a state that offered nothing and said nothing; a reading declined
far more broadly than the open question required; and actions that were offered and then refused
when applied (brandonifco/reykholt#104, #115, #116). A randomized probe outside the repository found
all three; no entry test and no review did. The same probe found that the engine's state record
compared its collections by reference, so record equality could not tell two replays apart.

That engine's 1.0 rests on a full-play acceptance suite driven through its surface alone
(brandonifco/reykholt#123). Its mechanism is general, and this record adopts that mechanism without
the parts that are about games.

## Decision

### 1. The engine declares its surface; the factory does not guess it

An action surface is a shape of the engine's own public API, and its names and signatures are the
engine's. Detecting it by reflection would take a rules engine with a method named `Apply` for one,
and would miss a surface named any other way. So the surface is **declared**, in two parts, both
engine-owned:

- **`acceptance.json`** at the engine root. Its presence is the declaration. It holds the
  parameters (section 4) and the allowlist (section 3): `seedsPerConfiguration` and `stepCap`
  (integers from 1 to 2147483647, the largest a C# `int` constant holds), `leastCompleted` (a
  number above 0 and at most 1, read exactly, so `1.00000000000000001` is above 1, and held exactly: to
  at most 18 decimal places, emitted as a C# `decimal` literal, so that `completed >= LeastCompleted *
  played` is a product of a `decimal` and an `int` that fits the 28 digits a `decimal` holds, and is
  exact) and `allowlist`
  (an object mapping an entry id to a sentence). `produce` reads it, and never writes or rewrites
  it. It validates it before it writes anything and refuses a malformed one naming the field: a
  missing, unknown, duplicated or mistyped field, an allowlist item whose sentence is a placeholder
  (it is held to the floor an overlay's mutations are held to, by the same function,
  `placeholder_problem` of `map-overlay.py`, and not a copy of it), an allowlist id that is not an
  entry of the engine's map, in the id form the registry uses (a composed engine's
  `Package.entry-id`), and a file that is a symbolic link. Because the harness is
  generated from it, `buildInputs` records its hash, so an edit that is not followed by a produce is
  a named mismatch, and the engine's own gate reads it through the same function to regenerate the
  harness, so a stale or stray one is refused there too.
- **An adapter** in the test project, implementing the members the generated harness declares and
  leaves for the engine: the configurations, how a run begins from a configuration and a seed,
  whether a state is over, the legal actions in a state, how to apply one, and how to render an
  action for the history. **Every member except `Start` is pure.** `IsOver`, `LegalActions`, `Apply`
  and `Render` must not change the state or the action they are given: not by mutating it, and not by
  caching or finalizing a value on it, which is what an `IsOver` that stamps a terminal state does,
  since the harness takes a run's final dump before `IsOver` is asked about it. And `Render` gives
  unequal actions unequal lines. The harness checks the state around `IsOver`, `LegalActions` and
  `Apply`, and the lines of `Render` (section 2); it does not dump an action, so an `Apply` or a
  `Render` that changes the action it was given is the adapter's to avoid and not the harness's to see.
  The engine writes it, in `tests/{name}.Tests/ActionSurface.cs`; `produce` never does. The generated harness declares these members as C# partial methods with an
  accessibility modifier, so a declaration with no adapter fails to build with CS8795, naming each
  missing member. The state and action types are the engine's: the adapter binds them with two
  `global using` aliases, `ActionSurfaceState` and `ActionSurfaceAction`, because a partial method
  cannot take a type the adapter chooses without making the class generic, and xUnit does not run a
  generic test class. Resolutions are the kernel's, `Resolution<T>` and `UnresolvedReason`, so
  `RequiresInterpretation` and the locator a decline carries mean what they mean everywhere else.
  An offer is a resolution of the legal actions, and an application is a resolution of the new
  state: a refusal or a decline is an unresolved one.

When `acceptance.json` exists, `produce` emits
`tests/{name}.Tests/Generated/ActionSurfaceAcceptance.g.cs`. That file is generated, rewritten on
every produce, and holds the invariants. When the file is absent, nothing is emitted, and a harness
emitted earlier is removed like any other generated file that no longer has a source.

### 2. The invariants

Each run starts from one configuration and one seed. At each step it applies the offered actions,
then advances by one action chosen deterministically from the seed. Each of the following is its
own test over the same runs:

1. **Every offered action is accepted.** Each action the surface offers in a state is applied to
   that state, and each application resolves. A refusal, or an unresolved answer other than an
   allowlisted decline, fails. **`IsOver`, `LegalActions` and `Apply` must not change the state they
   are given**, because every offered action is applied to the same state, and one that changed it
   would have the later actions judged against a state that is not the one that offered them; and
   because the state a run ends in is dumped before `IsOver` is asked about it, so an `IsOver` that
   finalizes a value would be inside no comparison. On each configuration's first seed and its replay
   (a dump walks the whole state, so it is not taken in every run), the state is dumped before the
   step's calls, and again after `IsOver`, after `LegalActions` and after each `Apply`; a difference is
   a finding under this invariant, naming the step and the call after which the state changed. The result of the chosen action is dumped as it is returned,
   before any later probe runs, and compared with the state the next step begins in: a probe that
   reaches an earlier result is a finding too.
2. **Nothing throws.** An exception on any surface call fails, and the failure names its type and
   first frame.
3. **Nothing stalls without a reason.** A state that is not over offers at least one action, or
   says why with an unresolved resolution. An empty offer with no reason is a stall.
4. **A run ends within the step cap.** Running past it fails.
5. **Runs stop early only on the allowlist.** A run may end before its natural end only on a
   `RequiresInterpretation` decline whose locator is an allowlisted entry's. Any other unresolved
   reason fails, `UnsupportedRule`, `OutsideCurrentScope` and `MissingRulesData` included: those
   name work the engine has not done, not a reading still open.
6. **Enough runs complete.** In each configuration, at least the declared fraction of seeds reaches
   a natural end, and a configuration that produced no runs, or a surface with no configuration,
   fails rather than passing empty. The comparison is `completed >= LeastCompleted * played` in
   `decimal`, with `LeastCompleted` the declared number exactly, so a fraction a hair above a half is
   not a half.
7. **Replay is deterministic, compared structurally.** Each configuration's first seed is played
   twice. Compared, in each pair of runs: the action **histories**, the line of each chosen action
   recorded before its outcome is resolved, so the step a run ends on is in it; the **state at the
   start of every step**, the last being the state the run ended in, each as the structural dump
   taken when it was reached, never a reference to a live object, which a later play could change;
   and the **ending** of each run, which is `completed`; or `stopped` with its reason, locator and
   attempted operation; or the invariant a finding stopped it under. An ending is structured fields
   (kind; reason; locator source id; citation; attempted), each framed as the dump frames a string
   (below), and it is those fields that are compared and never a display string, which two locators
   that split their source and citation differently can share. Anything not in that list is not
   compared. States are compared by a **structural dump** (below). Record equality is not used,
   because a record compares its collections by reference, so two identical replays would compare
   unequal and two different ones could compare equal. The history comparison relies on **`Render`
   giving unequal actions unequal lines**, so the harness checks that within every step of every
   run: two offered actions that are not equal and render alike are a finding under this
   invariant.

The runs are played once per test run and shared by every test, in parallel. A run stops at the
first failure it can no longer continue past (a throw, a stall, a state with no legal action, an
action that does not resolve). An unresolved answer from the chosen action ends the run early too,
and a failure there is held by invariant 1, not 5: invariant 5 is the one about a state that
cannot go on, where `LegalActions` itself answers unresolved. So each invariant can go red alone.
Each is its own `[Fact]` (`Every_offered_action_is_accepted`, `Nothing_throws`,
`Nothing_stalls_without_a_reason`, `A_run_ends_within_the_step_cap`,
`Runs_stop_early_only_on_the_allowlist`, `Enough_runs_complete`,
`Replay_is_deterministic_compared_structurally`), and the choice at each step depends on nothing but
the seed and the step: no hash code, culture or clock.

The **structural dump** walks every instance field, public and private, sorted by name, **unless a
type is known to be an exact scalar or a known collection**; it skips delegates and pointers.

- **Exact scalars**, a closed list: the primitives, `string`, `char`, `decimal` (written from
  `decimal.GetBits`, so the sign of zero and the scale are kept), enums (the assembly-qualified type
  and the underlying value), `DateTime`, `DateTimeOffset`, `DateOnly` and `TimeOnly` (`"O"`),
  `TimeSpan` (`"c"`), `Guid`, `BigInteger`, `Half` (`"R"`), `Int128` and `UInt128`; `double` and
  `float` are `"R"`, and every format is under the invariant culture. Nothing else is a scalar,
  whatever it formats as.
- **Known collections**, whose fields are bookkeeping and are dumped by items only: arrays, `List<>`,
  `HashSet<>`, `SortedSet<>`, `Queue<>`, `Stack<>`, `LinkedList<>`, `Dictionary<,>`,
  `SortedDictionary<,>`, `SortedList<,>`, and the `System.Collections.Immutable` collection types
  (`ImmutableArray<>`, `ImmutableList<>`, `ImmutableHashSet<>`, `ImmutableSortedSet<>`,
  `ImmutableDictionary<,>`, `ImmutableSortedDictionary<,>`, `ImmutableQueue<>`, `ImmutableStack<>`). A
  map and a set are sorted by the dump of each entry, and every other sequence keeps its order, a
  sequence of `KeyValuePair` included. A default `ImmutableArray<T>` carries `T`.
- **A grouping** (`IGrouping<,>`) is dumped as its `Key`, dumped as a value, and its items; it is not
  walked by fields.
- **Any other enumerable of a `System` namespace, or marked `[CompilerGenerated]`** (the state machine
  of a C# iterator method) is dumped **by its items only**: its fields are iteration machinery. A
  deferred LINQ iterator serves as its own enumerator on the thread that made it, so reading its fields
  and then enumerating it moves them, and a state machine records the thread that made it.
- **Every other type**, any `System` `IFormattable` (such as `Uri`) included, is dumped by its fields,
  and by its items too if it is enumerable. An engine-owned enumerable (any other namespace) is
  **enumerated first** and its fields are read after, so a type that is its own enumerator is in one
  state each time it is dumped. A type that derives from a known collection is walked down to it and no
  further, its items standing for the collection's own fields. A field reached again while it is being
  written is a cycle, written as how far back it is; aliasing without a cycle is written in full each
  time.
- **A `Type`** is written as its `AssemblyQualifiedName`; a generic parameter, which has none, as its
  declaring type's assembly-qualified name and its position.
- **Framing.** Every scalar, and every string-valued element (a type's name, a field's name), is written
  as its kind, its length and its text, `System.String[5]:alice`, so no text can reproduce the prefix of
  a neighbouring field.

A walk by fields reads what an object has computed lazily as well: a `Uri` whose `ToString` has been
called holds fields that one whose has not does not, so a state that holds one is changed, as the dump
sees it, by a call that only reads it. That is a finding under invariant 1, and it is the cost of
walking a type the dump does not know. The dump also enumerates what it dumps, so an engine that
holds a deferred query in its state has it evaluated on every dump; holding materialized collections is
what this record expects. A dump throws past a depth limit rather than loop on a chain
that is not a cycle, and depends on no hash code, culture or clock. **Not compared:** object identity
and aliasing, a collection's comparer, NaN payloads, and array lower bounds.

### 3. The allowlist names readings that were observed, and the harness names the ones it did not reach

Each allowlist item is an entry id mapped to where the engine documents the reading. An item is
matched by that entry's locator, because a decline names the locator. `produce` refuses an
allowlist id that is not an entry of the engine's map. The harness fails an item whose locator
another entry also cites (its `Locators`, which for a derived entry are the premises' passages),
because a shared locator would let one documented decline excuse another. That is the eighth `[Fact]`,
`Allowlisted_locators_are_cited_by_one_entry_only`.

The list is built from declines observed in runs of the surface, in the gate or in a longer
probe, never from readings someone expects to matter. The gate's own seeds may not reach a reading
that a longer probe did, so an item they do not reach is **not a failure**; but the harness names
each such item in the test output (`ITestOutputHelper`, from the allowlist fact), so a stale item
is visible and can be taken off. A decline should be as narrow as the open question
is: where the open readings would give the same answer for the state at hand, the engine answers
and does not decline ([`adversarial-self-review.md`](../../tools/factory/recipe/rails/adversarial-self-review.md),
`refusal-classification`).

### 4. Cost is reduced by making the engine faster, never by checking less of each state

`acceptance.json` declares how many seeds each configuration plays, the step cap, and the
completion fraction. An engine trades coverage for time only through those visible numbers. The
harness has **no** parameter that applies a subset of the offered actions, because doing so
weakens invariant 1 in exactly the states where it is hardest to hold, the ones that offer the
most actions. When the suite is too slow, the remedy is to make the engine faster: optimized
builds ([0077](0077-an-engine-is-built-optimized-in-every-configuration.md)), and shared work between listing actions and applying
them.

The engine this record learned from met its time limit by optimizing without changing a test
(brandonifco/reykholt#134). It later also bounded how many of a step's offered actions its suite
applied, while keeping the games played identical and applying every action in a full run before
each release (#135). This record does not adopt that. Whether the factory should carry a declared
bound of that kind is a question for the owner, and it is open.

### 5. What is not in this record

There is nothing here about players, turns, winners, or the order in which several actors are asked:
those are the adapter's business. Several awaited actors are one offer, the union of what each is
offered. Nothing here derives an engine's prose from its runs.

## Measured

**The fixture.** No example engine in this repository has an action surface, so the harness is
exercised against a toy one in the `HoyleBackgammon` engine `scripts/validate-engine.sh` produces
(`tools/tests/factory/fixtures/action-surface/ActionSurface.cs`, run by
`tools/tests/factory/test_factory_acceptance.py`): a counter that offers +1 and +2 and is over at 10 or
more, in two configurations, with a collection, a dictionary, a set, a default `ImmutableArray`, a
delegate and a private field in its state. `acceptance.json` declares 20 seeds per configuration, a step
cap of 40, a completion fraction of 0.5 and one allowlisted reading. The engine is built once; each
violation is selected by an environment variable the adapter reads, committed in a quarter of one
configuration's seeds (or, for the replay violations, in the first seed's play or replay) so that the
completion fraction still holds and the invariant under test is the only one that goes red. The
adapter file also carries plain facts over the structural dump, on paired values (section 2), and
two engines are built beside it for the exact threshold (two seeds, one of which completes).

**Each invariant goes red under the adapter that violates exactly it**, and it alone (the test asserts
the set of failed facts is that one, and that all eight ran):

| Invariant | Fixture violation | Observed failure |
|---|---|---|
| 1. every offered action is accepted | `Apply` answers an offered +2 with `UnsupportedRule` | `Every_offered_action_is_accepted`: `offered action 1 '+2' was answered with UnsupportedRule` |
| 1. no call changes the state it is given | `Apply` increments a field of its input; separately, `LegalActions` does; separately, `IsOver` caches an incrementing stamp on a terminal state | `Every_offered_action_is_accepted`: `Apply of offered action 0 changed the state it was given`; `LegalActions changed the state it was given`; `IsOver changed the state it was given` |
| 1. the chosen result is kept as returned | `Apply` changes the result of the offered action before it | `Every_offered_action_is_accepted`: `the state the chosen action returned was changed by a later call on the step before` |
| 2. nothing throws | `LegalActions` throws | `Nothing_throws`: `threw System.InvalidOperationException: the fixture throws here [first frame: ...]` |
| 3. nothing stalls without a reason | `LegalActions` offers an empty array | `Nothing_stalls_without_a_reason`: `the state is not over, offers no action and gives no reason` |
| 4. a run ends within the step cap | `Apply` resets the counter, so the run never ends | `A_run_ends_within_the_step_cap`: `not over after 40 steps` |
| 5. runs stop early only on the allowlist | `LegalActions` declines `RequiresInterpretation` at a locator off the allowlist; separately, `OutsideCurrentScope` at an allowlisted one | `Runs_stop_early_only_on_the_allowlist`: `which is not an allowlisted reading`; `stopped on OutsideCurrentScope` |
| 6. enough runs complete | one configuration ends every run early, on an allowlisted decline | `Enough_runs_complete`: `beta: 0 of 20 seeds reached a natural end, below the declared 0.5` |
| 7. replay is deterministic | a private field drawn from a process-wide counter, which the state's own equality cannot see | `Replay_is_deterministic_compared_structurally`: `the states first differ structurally at step 0` |
| 7. a history line drawn from a counter | `Render` appends a process-wide counter | `the histories first differ at step 0` |
| 7. states are captured, not referenced | `Start` returns one shared object, whose private stamp every `Start` moves on | `the states first differ structurally at step 0` |
| 7. the step a run ends on is in the history | the same seed offers +1, +2 on the play and +5, +6 on the replay, and the chosen action declines on the allowlisted locator in both | `the histories first differ at step ...` |
| 7. the ending is compared | the play declines on the allowlisted locator; the replay is over in a state with equal fields | `the runs ended differently: 'stopped: RequiresInterpretation ...' then 'completed'` |
| 7. every step's state is compared | a private stamp in the intermediate states that is gone from the final state | `the states first differ structurally at step ...` |
| 7. unequal actions render unequally | `Render` returns a constant | `offered actions 0 and 1 are not equal and both render as '+'` |
| 7. endings are fields, not a display string | the play and the replay decline off the allowlist on locators that print alike (`a b` and `c`; `a` and `b c`) | `Replay_is_deterministic_compared_structurally` (and `Runs_stop_early_only_on_the_allowlist`, which the decline is also a finding under): `the runs ended differently: 'invariant 5: RequiresInterpretation at a b c ...' then 'invariant 5: RequiresInterpretation at a b c ...'` |
| 6. the threshold is exact | two seeds, one completes, `leastCompleted` is `0.50000000000000001` (and `0.5` passes) | `Enough_runs_complete`: `alpha: 1 of 2 seeds reached a natural end, below the declared 0.50000000000000001` |
| allowlist locator uniqueness | an allowlisted entry whose passage four other entries cite | `Allowlisted_locators_are_cited_by_one_entry_only`: `its locator is also cited by ...` |

The twelve facts over the dump each pass on a correct dump and go red under the edit that breaks them: a
sequence of `KeyValuePair` keeps its order while a dictionary does not depend on the order it was
filled in; a boxed `1` and `1L`, the keys `1` and `1L`, and a default `ImmutableArray<int>` and
`<string>` dump differently; `TimeOnly` seconds apart, ticks apart, `DateTime` kinds and
`DateTimeOffset` offsets dump differently; an engine's own enumerable is its fields and its items,
and a list's capacity is not its value; two groupings with different keys over the same items, a
deferred LINQ iterator, the result of an iterator method (made on two threads) and an engine type that is
its own enumerator, each dumped the same every time, and
two `Uri`s that differ only in the string they were made from, dump differently (a `Uri` made from
one string and read the same way dumps alike); a ring of nodes is written as a reference back, and
two rings with different labels dump differently; `0m` and negative zero, and `1.0m` and `1.00m`,
dump differently; `T` of `List<>` and `TKey` of `Dictionary<,>` (both position 0), and an enum value
of two types, dump differently; a dictionary whose key and value split one text two ways, and a field
that carries the next one, dump differently, and a string is written `System.String[5]:alice`; and the
endings of two declines whose locators split their source and citation differently dump differently.

A correct adapter passes all eight. An allowlisted `RequiresInterpretation` decline ends runs early
and fails nothing. An allowlisted item no run reached is named in the test output of the allowlist
fact (`rubber-scoring ...: no run declined at this reading`), and nothing fails. A declaration with no adapter does not build: CS8795, once for each of the six
members, each named (and CS0246 for the two type aliases the adapter binds).

**Cost, in the gate.** `HoyleBackgammon`, produced and verified by the factory at the branch head, then
the same engine with `acceptance.json` and the fixture adapter, each gate run twice
(`./scripts/validate.sh full`, 24 cores, SDK 10.0.112, re-measured after the second repair). Seconds, run 1 / run 2:

| | without | with |
|---|---|---|
| `produce --no-verify` | 0.9 | 0.9 |
| verified `produce` (restore, build, test, gate) | 11.3 | 13.1 |
| gate: `dotnet format --verify-no-changes` | 2.4 / 2.4 | 4.6 / 4.6 |
| gate: build + test Debug | 2.1 / 2.0 | 2.3 / 1.9 |
| gate: build + test Release | 2.1 / 2.0 | 2.2 / 1.9 |
| whole gate | 8.9 / 8.5 | 11.4 / 10.6 |

The harness plays 40 toy runs plus 2 replays, and dumps the state around every call of the two
capturing runs, in well under a second, so the test steps do not move; the added 2 s is the
formatter reading the adapter. What the harness costs an engine is the cost of the engine's own
runs, and of a dump of its state around every call of two runs per configuration, which is why
section 4 says to make the engine faster.

**Cost, in the factory's own tests.** `test_factory_acceptance.py` runs 39 tests: 29 need no SDK and
take about 9 s, and the 10 that build and run the produced engine add about 48 s (one build, then
about 1 s per violation, and two more builds for the exact threshold), 56 s for the module on this
machine. They skip, saying why, without the pinned SDK, as `test_factory_provenance.py`'s `dotnet
test` of a produced engine does.

**What was watched failing.** Each of these edits to the factory turns the named tests red, and was
reverted: dropping a `[Fact]` from the harness; comparing final states with record equality instead of
the dump; ending the allowlist id check; emitting the harness for an engine with no declaration;
keeping a harness whose source was deleted; leaving `acceptance.json` out of the build inputs; the
engine's gate not reading the declaration; applying only the first offered action; removing the
step-cap finding; accepting any decline reason on the allowlist; and a throw reported under the wrong
invariant.

After the review of the first head, each repair was shown red the same way, by the edit that undoes
it (each reverted): dropping the dump comparison after `LegalActions` and `Apply`; dropping the
comparison of the chosen result with the next step; keeping a reference to each state and dumping it
when the runs are compared; dropping the ending from the replay comparison; recording the chosen
line only after its outcome resolved; comparing only the last state of the two runs; dropping the
finding for two unequal actions with one line; classifying a sequence of `KeyValuePair` as a map;
writing a scalar without its type, and a default `ImmutableArray` without its element type; leaving
`TimeOnly` and `DateTimeOffset` to the `IFormattable` fallback; dumping an engine's enumerable by its
items alone, and by its fields alone; not writing the unreached allowlist items to the test output;
accepting a placeholder allowlist sentence; putting no upper bound on the counts; reading
`leastCompleted` as a float; and following a symlinked `acceptance.json`. The new tests were also run
against the first head's two generator modules (with the dump made reachable so that they build), and
every one of them is red there.

After the second review, each repair was shown red the same way (each reverted): not comparing the
state after `IsOver` (so that the final dump, taken before `IsOver`, is the last one); dumping a
`System` enumerable by its items alone, and a `System` `IFormattable` as a scalar; writing a string
without its length; comparing the endings by their display string; reading the threshold as a
`double`; writing a decimal by its text and not its bits; naming a generic parameter by its `FullName`;
and not recognising a cycle. The new tests were also run against the two generator modules of the
head the second review read, 44614be (with the ending kept as a display string, so that the fixture
builds), and these are red there: the `IsOver` violation, the groupings, the `Uri`s, the framed
strings, the generic parameters, negative zero, the endings, the exact threshold and the emitted
literal.

After the third review, of 62a0677, the repair was shown red the same way: writing the fields of a
`System` enumerable before its items (the dump of the head the review read) turns red a state that holds
`new[] { 1, 2 }.Where(...)` and one that holds the result of a `yield return` method, each over at once,
with `IsOver changed the state it was given`, and the dump fact over deferred iterators; and enumerating
first while still writing a `System` or compiler-generated enumerable's fields turns the dump fact red on
the thread a state machine records (each reverted).

## Compatibility

No engine has `acceptance.json`, so `produce` emits nothing new for any of them: no `*.g.cs`, no
record of one, no change to any engine-owned file or to `buildInputs` or `engineOwned`. An engine
produced from this factory and from the commit before it differs only in what any factory change
moves: the vendored generator under `scripts/factory/` (two new modules, `acceptance.py` and
`acceptancecs.py`, and the changed `generate.py`, `ownership.py`, `provenance.py`, `semantics.py` and
`scripts/engine-gate.py`), the managed `AGENTS.md` at recipe 30, and `provenance.json` as it names
those. An engine that adds the file and re-produces gets the harness, and its adapter is its own to
write.
