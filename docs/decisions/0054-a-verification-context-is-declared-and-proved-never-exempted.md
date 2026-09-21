# 0054 — A verification context is declared and proved, never exempted

## Status

Accepted — 2026-09-20. Records the decision on
[#336](https://github.com/brandonifco/rules-factory/issues/336), the last open finding of the
round-five assurance list ([#338](https://github.com/brandonifco/rules-factory/issues/338)).
**Extends [0018](0018-every-file-the-factory-writes-has-one-owner.md)**, which made `global.json` a
managed file whose bytes `provenance.json` hashes, and leaves that ownership exactly as it was.

## Context

An engine's `global.json` pins the SDK the kernel pins, with roll-forward disabled, and it is the
only thing that selects an SDK for the `dotnet` the gate runs. A machine without that exact SDK can
neither restore nor run the gate. So `factory verify` supports a local override: for the length of
`dotnet restore` and of the gate, and no longer, `overridden_sdk` re-pins `global.json` to
`$FACTORY_DOTNET_SDK_OVERRIDE` and puts the original bytes back after, pass or fail.

Stage 3 is the engine's own gate, and that gate checks the managed files against `provenance.json`
— `global.json` among them. Reproduced on a freshly produced engine:

- `scripts/engine-gate.py provenance` passes on the engine as it stands;
- inside the documented override context it fails, `managed[global.json].sha256: recorded …, on
  disk …`;
- the original is restored afterwards, and it passes again.

One run therefore made two claims at once: *these bytes are the factory's, hashed against the
record*, and *this engine's `global.json` is not what the record hashes*. Neither mechanism was
wrong about its own claim. What was missing was between them: nothing said which tree was under
verification. That is [#338](https://github.com/brandonifco/rules-factory/issues/338)'s failure mode
exactly — artifact A reported as verified from evidence produced in state B, with no proof that B is
the state A embodies.

## Decision

**The substitution is declared to the checker that would otherwise refuse it, and that checker
proves it.** `overridden_sdk` keeps the recorded bytes in a directory of its own outside the engine
— nothing may appear inside an engine without an owner (0018) — and hands the gate
`FACTORY_SDK_OVERRIDE_RECORDED`, a path to them. For `global.json`, and only when a declaration is
in force, the gate's provenance step proves **two** things where it otherwise proves one:

1. the declared original hashes to what `provenance.json` records, and
2. `global.json` on disk is exactly that original re-pinned to `$FACTORY_DOTNET_SDK_OVERRIDE`.

So the tree under verification is known exactly, it differs from the recorded tree in one field of
one file, and the difference is the one the operator asked for. Everything else follows:

- **The normal path is untouched.** With no declaration — CI, or any run that did not re-pin — the
  recorded hash is compared byte for byte, as before. `$FACTORY_DOTNET_SDK_OVERRIDE` alone declares
  nothing: a shell that exports it, or an engine that adopted the override into its own record
  (`scripts/validate-engine.sh`), is compared exactly.
- **A declaration cannot be a cover story.** It cannot hand the gate a `global.json` the record
  never saw (proof 1), cannot move `rollForward: disable`, which is the other half of the pin, and
  cannot touch any other managed file (proof 2 compares whole bytes, and the re-pin is recomputed
  rather than trusted). An undeclared re-pin fails exactly as it did before any of this existed.
- **It is refused where a green run must mean the pinned toolchain.** `verify` refuses the override
  under `CI=true` before anything runs, and the gate refuses a declaration under `CI=true` too — an
  engine's gate is run by engine CI, not only by the factory, and a refused declaration leaves the
  exact comparison in force rather than a hole.
- **The run says which SDK it verified on.** The provenance step names the recorded pin and the
  override above its comparison and again in its `ok` line; the SDK-pin step says the pin it just
  checked is the override's; `verify` warns before the stages and in the line that ends the run;
  `produce` repeats it in `produced … verified on SDK X by FACTORY_DOTNET_SDK_OVERRIDE, not the
  pinned Y`. No output of an override run reads as a claim about the pinned toolchain.
- **Restoration is unchanged and now also covers a partial write.** `global.json` is put back from
  the bytes held in memory whether the stage passed, failed or raised, and the recorded copy is
  removed with it.

## What was rejected

- **Exempting `global.json` from provenance.** The issue rules it out, and rightly: the file that
  selects the toolchain is precisely the one worth hashing. A conditional exemption keyed on an
  environment variable is the same hole with a longer key.
- **Selecting the SDK without touching the file.** There is no mechanism to: the muxer resolves
  `global.json` from the working directory upwards, the gate runs from the engine root, and the
  engine's own file wins with roll-forward disabled. "Select it another way" would have meant a
  wrapper on `dotnet` — a second, untested SDK-selection path whose agreement with the recorded pin
  nothing could check.
- **Re-writing `provenance.json` around the override.** That makes the record agree by forging it,
  which is the defect the provenance step exists to catch.
- **Withdrawing the override.** It is the only way a machine without the pinned SDK can run the gate
  at all, and `scripts/validate-engine.sh` depends on it for local runs. Removing a supported path
  to end a contradiction about it removes the verification too.
- **Adopting the re-pinned file, as `scripts/validate-engine.sh` does.** Adoption is right when the
  engine really is pinned to another SDK: the record then says so. It is wrong for a standalone
  `verify`, which writes no record, runs on the engine in place, and must leave the committed pin
  exactly as it found it.

## What would reopen this

A second thing a run needs to substitute. The declaration is deliberately one file and one field,
and a general "verification context" of many declared substitutions is a different decision: each
one widens what a green run can mean, and the argument that this one is safe rests on its being
recomputable from the recorded bytes. Two of them, and the shape to reach for is a recorded context
in `provenance.json` — a verification that says what it ran against — not a longer list of
environment variables.
