# Frozen target: rebuilding deckard through the factory

[#3](https://github.com/brandonifco/rules-factory/issues/3), criterion 1, asks whether the factory
can produce an engine equivalent to [deckard](https://github.com/brandonifco/deckard), the
hand-built Shadowrun Sixth World engine. This directory fixes what "deckard" means for that
question **before** any mapping or implementation starts. It is step S0 of the rebuild plan (E0).

[TARGET.json](TARGET.json) pins:

- deckard commit `9825f249d2566312f987bb5fcc04bfa2d2ee84ca`, and the git tree hash of its `tests/`;
- all 110 xUnit test methods, as `Namespace.Class.Method`, and the 324 cases they run
  (Core 64 / 256, Rules 45 / 67, Data 1 / 1), in five categories: architecture 3, test double 5,
  PRNG and dice 30, replay identity 28, SR6 rules 44. Every category runs verbatim (D5);
- the sha256 of decision records 0001–0007;
- the decisions deckard made only in code comments, each with `path` and line range at the commit,
  the sha256 of those lines, and the deckard tests that pin it;
- every deckard gate with its class (`equivalent`, `stronger`, `carried-as-test`,
  `repository-process`, `divergent`) and a line locator. Only the SDK pin is an approved divergence
  (D6). The other `divergent` rows are proposed and wait for Brandon's approval;
- Brandon's decisions D5–D8 of 2026-09-15, and the slice as printed page numbers.

It holds no text from the rulebook: names, hashes, page numbers and locators only. The short
`summary` and `note` fields are this repository's own words about deckard, and the checker refuses
any that are long or contain a quotation mark.

## This target is not edited to fit a result

The target exists so that the rebuilt engine is judged against deckard as it was, not against
whatever the rebuild turns out to do. A mismatch found later is a finding about the rebuild. It is
resolved by a map correction backed by the corpus, or by an owner ruling (0027), never by changing
TARGET.json or deckard's tests. TARGET.json changes only through a pull request that says why,
reviewed by Brandon, and the checker below then has to pass against the same commit.

## Checking it

```sh
git clone https://github.com/brandonifco/deckard /tmp/deckard
python3 examples/sr6-deckard/check-target.py /tmp/deckard                      # every pin
python3 examples/sr6-deckard/check-target.py /tmp/deckard --require-approved   # as the equivalence step runs it
python3 examples/sr6-deckard/check-target.py --self-check                      # TARGET alone, offline
```

[check-target.py](check-target.py) reads deckard only from git objects at the pinned commit, never
from a working tree. It re-derives every pin and exits 1 on any difference. To count cases it
exports the commit and runs `dotnet test` in Release, so it needs the SDK deckard's `global.json`
pins (10.0.111, roll-forward disabled). `--skip-tests` checks the rest and exits 3, NOT VERIFIED.
An unapproved `divergent` gate prints PENDING, and fails under `--require-approved`.

It is not run by `scripts/validate.sh`, because it needs a deckard clone and the .NET SDK. The
equivalence step (`equivalence.sh`, E0) runs it first. What CI does run is
[tools/tests/test_sr6_deckard_target.py](../../tools/tests/test_sr6_deckard_target.py): the
self-check on the committed TARGET.json, and every refusal against a synthetic deckard-shaped
repository with a fake `dotnet`.
