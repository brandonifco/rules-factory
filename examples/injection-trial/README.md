# Trial 5 — injecting known errors into a map, to find out what survives

Trial 4 built an engine from a map and found **eleven map errors**. Every one was real and
every one was found in earnest. Nothing said how many were *missed*: eleven were caught and
the denominator did not exist, so every claim this project makes about the build catching map
errors was unquantified. This trial supplies a denominator, for one part of the pipeline, and
is careful about which part.

**The number, first, and then the sentence that governs it.**

> **Twenty-seven known errors were injected into the backgammon map, one at a time. Thirteen
> were caught by a mechanical detector. Fourteen — 52% — passed every checker, the engine's
> full gate, its build, and its 350 tests, leaving the pipeline green.**
>
> **That is not a miss rate for the method. It is a miss rate for the method's automation.**
> The stage that found all eleven of trial 4's errors — a person implementing the map against
> the corpus — is not measured here and cannot be measured by the person who wrote the
> injections. What this trial measures is what survives when nobody is reading.

The stratification below is the part worth quoting. The headline on its own is a number about
a sample somebody chose.

## What is being measured, exactly

A corpus map passes through detectors of five kinds. This trial runs four of them and says
plainly that it does not run the fifth.

| stratum | detector | run here? |
|---|---|---|
| schema | `tools/check-map.py` — structure, vocabulary, references, cycles, exclusions | yes, all 14 checks |
| corpus | `tools/check-locators.py` — citations, absences, coverage, against the corpus text; and the engine gate's own citation step | yes, all 3 checks plus the engine's |
| code | the engine gate's map-to-code steps | run, reported, **never counted** — see below |
| build | the engine's build and 350 tests | yes |
| human | a person reading the corpus against what the entry claims | **no. Not measurable by the injector** |

**The catch rate reported is the schema and corpus strata only.** The `code` stratum is
excluded on a specific ground, not a vague one: `hoyle-backgammon` was built from the
*corrected* map, so its `MapEntries.cs` holds the right entry names and the right citations.
A check that compares an injected map against that code is comparing it against the answer.
In a real trial the error precedes the build, the implementer transcribes it, and the check
passes. Counting those as catches would inflate the rate by six injections — the difference
between a 52% miss rate and a 30% one, which is the whole finding. They are reported in their
own column because what they *would* catch on a re-map of an existing engine is worth knowing.

The `human` stratum is where trial 4's eleven findings came from, and it is the interesting
one. This trial cannot touch it: I designed the injections, so "would I have caught it while
implementing" is worth nothing. What can honestly be said is which injections a person would
have to catch **because nothing else can**, and that is what the 14 misses are.

## The injections

Twenty-nine injections plus two controls, in `injections.py`; each is a patch on a parsed map
carrying why it is false, the real finding it reproduces, and the stratum predicted for it
before anything ran.

**Chosen to match the real distribution, not the checkers' aim.** Injecting only what a
checker catches measures the checker. The families and their weights come from what trial 4
and its two review passes actually found in a map written in earnest — wrong `dependsOn` (six
instances, issue #13), missing `gatedBy` (two, one with a determinism consequence no
correctness test could see), a wrong `clarity` (#14), thirteen wrong page citations out of
twenty-four (#18), four unmapped rules (#20), a delegated standard typed as a value (#33), and
the worst of them: an entry declaring a rule unreadable when the corpus states it in prose
(#31). Fifteen of the twenty-seven scored injections reproduce a specific real finding;
`beyond-adapter-false` and `clarity-ambiguous-to-clear` restore two of them exactly.

**Every injection is checked for being an error at all.** One was not, and the run is how that
was found: `cite-page-off-by-one` moves a citation onto the second page of a quote that
straddles a page break, and `check-locators.py` accepts any page a quote touches, on the
stated ground that citing either is honest. It is kept, marked `invalid`, and excluded from
the denominator. One more, `absence-in-unused-words`, was written *after* seeing a result, to
probe a limitation the tooling documents; a chosen evasion is not a sample, so it is reported
apart and excluded too. Both exclusions are in the code, not in the prose.

## How a catch is decided

Not by me. A check counts as catching an injection when **the control run did not already
fail it and this run does**. The controls are runs, not assumptions. `control-unmodified`
establishes the starting state before anything is injected: 16 of the 17 factory checks green,
the seventeenth (`status`) reporting that this map gives it no subject matter, and all 14
engine steps green. `control-harmless-note` rewords a `note` and confirms nothing fires on a
change that alters no claim. Neither control produced a false positive.

A baseline `skip` is not treated as a baseline pass. It counts as a catch only where the
injection *created* the check's subject matter and the check then failed — which is exactly
what `status-claimed-without-revision` does, and the one place it happens.

This replaces blinding for the mechanical strata, which is the honest version of what blinding
would have bought. I wrote the injections and ran the detectors, so "did I catch it" would be
worthless — but no detector verdict here passes through my judgement. Each is an exit code and
a named check parsed out of the tool's own output, scored against the control by
`score.py`. For the human stratum there is no such substitute, which is why no human-stratum
result is claimed.

Two further mechanics, both of which would otherwise have produced a fake number:

- **The map's hash pin is recomputed after each injection.** The engine's gate pins the map's
  bytes in `corpus-manifest.json`, so *any* edit fails that step. Left alone, every injection
  would have been "detected" by a check that never read a word of the map. Recomputing is what
  the gate's own failure message tells a mapper to do when the map was meant to change. That
  step is excluded from scoring.
- **The engine gate stops at its first failing step**, so an injection caught by the
  map-to-code step never reaches the gate's one corpus-facing check. "Not reached" is recorded
  as not reached, never as "did not catch", and that citation step is additionally run in
  isolation — its own source, sliced out of `scripts/validate.sh` unmodified — so every
  injection faces it. One injection (`cite-wrong-section-right-page`) is caught *only* there.

## Running it

```bash
python3 run-trial.py          # ~2 minutes; 31 runs, both repositories, the real gates
python3 score.py              # writes results.md
```

Each run gets a clean `git archive` export of both repositories at a pinned commit —
`rules-factory` at `ecc53b8`, `hoyle-backgammon` at `67563b3` — so another agent editing
either working tree while this ran could not change what was measured. Nothing is written
outside a scratch directory and this folder.

## Results

Full table, per-family breakdown and the raw per-check verdicts: [results.md](results.md),
generated from [results.json](results.json), which holds every detector's actual output lines.

| predicted stratum | n | caught mechanically | missed |
|---|---:|---:|---:|
| schema | 5 | 5 | 0 |
| corpus | 7 | 7 | 0 |
| human | 15 | 1 | 14 |
| **all** | **27** | **13** | **14** |

**The split is almost total, and it is the result.** Every error with a structural or textual
signature was caught — all twelve of them, plus one predicted miss that a checker caught after
all. Every error that requires knowing what the corpus *says* was missed, fourteen times out
of fifteen. Twenty-six of the twenty-seven predictions written before the run were right,
which is itself worth stating: the boundary between what a checker can see and what it cannot
is predictable from the shape of the error, and this project has been drawing it correctly.

**What survived everything** — each of these left `check-map.py`, `check-locators.py` and
`./scripts/validate.sh full` entirely green:

- `beyond-adapter-false` — the exact error of trial 4's finding 1, restored: `starting-position`
  declared unreadable by the plain-text adapter while its own evidence is the prose statement
  of it, verbatim, on the page cited. This one error produced a decision record, a schema field,
  a trial-report headline and an engine architecture before a human caught it. Nothing
  mechanical caught it here.
- `clarity-ambiguous-to-clear` — trial 4's finding 4 restored: an entry asserting the corpus
  determines one answer for every input, where a reachable finish has none.
- `depends-dropped`, `depends-spurious`, `gate-dropped`, `gate-spurious` — the relation errors,
  which were trial 4's largest family. A map can order the work wrongly, gate a rule by a
  phase that cannot precede it, or drop the edge to the rule producing its input, and every
  check in both repositories stays green.
- `kind-operation-to-value`, `kind-assertion-to-value`, `scope-in-to-out` — a rule can be
  retyped, or silently declared out of scope, without a murmur.
- `evidence-adjacent-sentence`, `evidence-truncated` — a verbatim sentence of the corpus, on
  the page it is really on, attached to an entry it does not support. Every citation check
  passes, because every citation check asks whether the quote is where the entry says it is,
  never whether it says what the entry says it says.
- `entry-fabricated-real-quote` — a whole entry for a compulsion to hit, which backgammon has
  not got, cited to a real sentence on its real page.
- `name-contradicts-corpus` — an entry whose name says each table carries fourteen points,
  above a verbatim quotation saying otherwise. The number the engine is built around, wrong in
  the field a reader reads first.

**What the build and the tests did: nothing.** Of the 21 injections applied to the engine's
copy, 9 reached the build and the 350 tests and **none went red**. That is not a criticism of
the suite: nothing in `src/` reads `corpus-map.json` — no file I/O at all — and the map
reaches the engine as constants transcribed into `MapEntries.cs`. A compiler and a test suite
cannot see a map error. The runs are the evidence for that rather than the argument.

## What this number does and does not mean

**It is not an estimate of a population parameter.** The twenty-seven injections are a
purposive sample, chosen to span the families trial 4 found, not drawn at random from any
population of mapper errors. There is no such population to draw from. So "52% of map errors
are missed" is a sentence this trial does not support, and the sentence it does support is
narrower: *of twenty-seven errors of the kinds a real map was found to contain, fourteen
survived every mechanical check this pipeline has.*

**What n = 27 buys, and what it does not.** As a binomial proportion the headline carries a
95% interval of roughly 34–69%, which is nearly useless on its own — a hundred injections
would have narrowed it, and a hundred injections of my own devising would not have made it a
better number. The precision worth having is in the strata, and there it is not really
statistical: the variance is between families, not within them. Whether a checker sees an
error is a property of the error's shape, near-deterministic, which is why 26 of 27
predictions held. The stratum figures (5, 7, 15) are enough to say which side of the line each
family falls on and not enough to put a rate on anything narrower.

**Injecting after the build is not the same as mapping wrongly before it.** A real error
propagates: the implementer transcribes the wrong citation, builds against the wrong gate, and
the map-to-code checks agree with each other. Injecting into a finished map creates a
disagreement that a real error would not create, which is exactly why those checks are
excluded here — but it also means this trial cannot say what a build *from* a wrong map does.
Only trial 4 can speak to that, and it found eleven.

**The human stratum is unmeasured, in both directions.** Fourteen errors reaching a human is
not fourteen errors shipping. Trial 4's evidence is that a person implementing a map against a
corpus catches a great deal — eleven errors, several of them subtle. It is also the evidence
that a person *stops reading*: three of trial 4's four biggest findings were that same failure
in different clothes. This trial says how much weight that person is carrying. It does not say
whether they carry it.

**Some misses matter far more than others.** A spurious `dependsOn` edge costs an implementer
an afternoon. `beyond-adapter-false` cost a decision record, a schema field and an engine's
architecture. The rate counts them the same, and no rate should be read as though severity
were uniform.

## Limitations I could not design away

- **The two copies of the map have diverged**, and the engine's is behind. `hoyle-backgammon`'s
  `corpus-map.json` pins itself to factory commit `7d13c27`; upstream has since corrected every
  `evidence` field from a summary to a quoted span (#18). So on the engine's copy most entries'
  evidence is not locatable, and its citation step verifies a page-in-section and nothing
  below it. Every injection touching evidence was therefore applied to the factory copy only,
  and the engine's corpus-facing detector is weaker here than the tooling can be. **Nothing
  detects that a downstream copy has fallen behind upstream** — the pin records which commit
  it was taken from and nothing compares it with what that path holds now. That is a finding of
  this trial rather than a property of it, and it is not mine to fix from this directory.
- **The engine repository runs no structural map checker at all.** `check-map.py` lives here;
  `hoyle-backgammon`'s gate never calls it. A map with a `dependsOn` cycle passed the engine's
  full gate — build, tests, correspondence, citations — green. The cycle was caught in this
  repository, by a tool the engine does not run.
- **One detector's verdict is a fact about one map.** `check-map.py` reports `skip` for checks
  this map gives no subject matter (`conflicts`, `absent` on the engine copy). A skip counted
  as a catch only where an injection *created* the subject matter and the check then failed,
  which happened once, deliberately.
- **I wrote the injections, so the catalogue's coverage is my judgement.** The families come
  from trial 4, but which errors within a family, and how subtle, is mine. A different author
  would produce a different 52%.

## What follows from this

Stated as claims this trial supports, with what would falsify each:

1. **The mechanical half of the pipeline is a filter on error *shape*, not on error
   *severity*.** It catches what is structurally or textually checkable, completely, and
   nothing else. Falsified by an injection with no structural signature that a checker catches
   — one was attempted (`absence-stated-in-other-words`) and the checker caught it, because the
   corpus happens to use the word "capture" once, inside the passage that states the rule.
2. **Downstream of the map, automation contributes nothing.** The build and the tests cannot
   see a map error at all, and the gate's map-to-code checks compare the map against a
   transcription of itself. The one uncontaminated downstream detector is the citation step,
   which duplicates what `check-locators.py` already does upstream.
3. **The countermeasure that works is the one already identified.** Every catch in the corpus
   stratum came from comparing a claim against the corpus's own bytes — which is what #18
   shipped. The gap it does not close is the one the fourteen misses share: `evidence` proves
   the quote is *where* the entry says, never that it *says* what the entry says.

The obvious next thing this trial suggests, and does not do, is a checkable form for the other
half of that promise — an entry stating what its evidence establishes in a form something can
test — plus running `check-map.py` in the engine's gate, and a check that a downstream map copy
is not behind its upstream. Those are recommendations, not findings.

## Should the number be quoted?

The stratified figures, yes: 13 of 13 mechanically checkable errors caught, 14 of 15
corpus-comprehension errors missed, 0 of 9 caught by the build and tests. Those are facts about
runs that happened, with the outputs in `results.json`.

The 52% headline, only with the sentence it comes with. On its own it will be read as "the
method misses half of all map errors", which is not what was measured, and this project has
spent two trials catching exactly that kind of overclaim in its own documents.
