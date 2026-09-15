# Brief: rebuild the HoyleBackgammon engine, blind

You are to produce a rules engine for backgammon as *Hoyle's Games Modernized* (1909) describes it,
using the rules-factory and the published map of that corpus, and implementing the rules by hand
where the factory leaves them to you. An engine built this way already exists. Your engine will be
judged by that engine's own test suite, which you will not see.

The point of the exercise is to show that the factory, the map and the owner's recorded decisions are
enough to rebuild an engine without copying it. So what you may look at is limited, and the limits
are the substance of the task.

## What this brief holds

| Path | What it is |
|---|---|
| `inputs/map/rulesfactory.maps.hoylebackgammon.6.0.0.nupkg` | The published map package, `RulesFactory.Maps.HoyleBackgammon` 6.0.0, byte for byte as nuget.org serves it. Your build restores this package; the copy is here so you can read it. |
| `inputs/corpus/hoyle.txt` | The corpus, Project Gutenberg's plain text, public domain. |
| `inputs/factory/rules-factory/` | The factory, a git checkout of the tag you must produce with, holding only its tools. Copy it out before running it (`cp -a brief/inputs/factory/rules-factory /workspace/factory`): the brief is read-only, and `factory produce` records the checkout's commit and refuses a dirty one. |
| `inputs/factory-docs/` | rules-factory's `README.md` and `docs/` at that tag. Redacted where they name the target's tests. |
| `engine/api-contract.md` | The public API of the engine: every public type and member with its signature and documentation. No code. Redacted where the documentation names a test. |
| `engine/conventions.md` | What the tests observe that nothing else here states. Read it. |
| `engine/overlay-skeleton.json` | Every entry's `status` and `implementedIn`, and the owner's rulings and declines, for your `corpus-map.overlay.json`. |
| `engine/build-files/` | The solution and the engine-owned build files, verbatim. |
| `engine/decisions/` | The engine owner's decision records 0001 to 0010. Redacted where they name tests or quote test data. |
| `MANIFEST.json` | The sha256 of every file here, every redaction (what kind, where, and the hash of what was removed) and every disclosure. |

Also allowed, because they are public packages the factory's output depends on: `RulesKernel` and
`RulesKernel.Randomness` 0.3.0 from nuget.org, their XML documentation, and the .NET SDK and
xUnit documentation.

Some things are named and not provided:

- the engine's `MAP-FINDINGS.md` and `README.md` (findings against earlier map versions, all resolved
  into map 6.0.0 or into the decision records, and a design narrative; both name tests and code
  throughout);
- rules-factory's `examples/`, `tools/tests/` and anything else outside `tools/factory/`,
  `tools/check-map.py` and the docs given here.

## Rules

1. **Do not look at `brandonifco/hoyle-backgammon`**: not its code, tests, issues, pull requests,
   commits, CI logs, releases, or any fork, mirror, cache or copy of them, on GitHub or anywhere else.
2. **Do not look at rules-factory beyond what this brief gives you.** In particular not
   `examples/hoyle-blind-rebuild/`, `examples/hoyle-backgammon/`, `tools/tests/`, or rules-factory's
   issues and pull requests (#3 and its links discuss the target). The factory is in the brief; you
   need no access to github.com at all.
3. **Do not use the target's test names, test data or code from memory**, if you have met them before.
   If you have seen hoyle-backgammon's source or tests, say so and stop: you cannot do this task.
4. Network access is allowed for nuget.org restores, the .NET SDK, and documentation of .NET and
   xUnit, and nothing else: no other backgammon implementation. The session's network may be limited
   to exactly those hosts, and every request is logged.
5. If something you need is not here, **ask in writing**: write `/workspace/questions/NNN-question.md`
   (001, 002, ...), one question a file. An answer arrives as `NNN-answer.md` beside it. Every question
   and answer is published with the result, and more than 10 answers labels it "assisted". Do not guess
   from outside sources.
6. Keep a log of what you read outside this brief (a URL per line), and hand it in.

## What to produce

- A git repository whose first commit is exactly what `factory produce` writes from the map package
  above, with the factory at its tag, for the engine name `HoyleBackgammon` (plus a licence and a
  README if you like), and whose later commits implement the rules.
- `factory provenance --engine .` reports every field matching, and `./scripts/validate.sh full`
  passes, on the SDK the factory pins.
- Your own tests, named in your overlay as rules-factory requires. They are yours; the judgement uses
  the target's.
- The reading log (rule 6), and a signed statement that rules 1 to 3 were kept.

## How you will be judged

All of these, for one commit of your repository; there is no partial pass:

1. Your `tests/` directory is replaced by the target's, unmodified and with no adapter shims, and with
   `CI=true` on the SDK the factory pins, locked restore, a warnings-as-errors Release build and every
   test case pass.
2. Your `provenance.json` names the same factory, map, kernel, corpus, randomness and owner's rulings as
   the target's.
3. Every generated and managed file is byte-identical to the target's. (It can be: `factory produce`
   from this brief, with `overlay-skeleton.json`, gives exactly those files.)
4. None of your files is a copy of the target's, and a reviewer reads every source line yours shares
   with it.
5. `factory provenance --engine .` matches every field and your CI is green.
6. The rules above were kept: your transcript and the network log are searched, and every question
   you asked is published with its answer.

The result is labelled "with a written interface", because this brief gives you the engine's API
contract and its conventions, and "blind" or, after more than 10 answers, "assisted". However many
cases pass, the count is reported.

The target's tests are frozen at a commit you are not told.
