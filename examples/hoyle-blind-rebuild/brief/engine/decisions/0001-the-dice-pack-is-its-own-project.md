# 0001 — The tabletop dice pack is its own project, not a folder

**Status:** accepted

## Context

The kernel ships no dice, on purpose
([RulesKernel decision 0002](https://github.com/brandonifco/rules-kernel)): randomness is an
optional package and a die is subject-matter vocabulary. What it ships is
`UniformInt.Below(source, bound)` returning `[0, bound)`, with the `f - 1` face convention
documented on the method.

So a dice vocabulary has to live somewhere, and the brief requires it to be
ruleset-agnostic — "it must contain nothing about backgammon". The choice is a folder inside
`HoyleBackgammon`, or a project of its own.

## Decision

Its own project, `src/Tabletop.Dice`, referencing `RulesKernel.Randomness` and nothing else.

## Why

> [redacted by build-brief.py: test-name]

**It is the same argument the kernel makes about itself.** The kernel is a separate
repository because a correction made in it should reach every engine through a version bump
rather than being stranded. The pack is a weaker version of the same claim — the next engine
built from a map over a dice game wants this vocabulary, and wants it without a backgammon
dependency. Putting it behind a project boundary now is what makes lifting it out later a
move rather than a rewrite.

**The boundary had to be drawn somewhere, and drawing it forced a real question.** Doublets
are the case. "Both dice show the same face" is dice vocabulary and lives in the pack as
`DiceThrow.IsDoublets`. "Doublets are played twice over" is a backgammon rule with a map
entry and a page number, and lives in `Movement.Entitlement`. A folder would not have
prompted the question and the natural thing to write would have been a pack that returns four
numbers for a doublet — which is Hoyle's rule wearing the pack's clothes, and wrong for any
game that treats doublets differently or not at all.

## Cost

One `.csproj`, one more assembly in the build, and a two-project solution where a
one-project solution would do. Nineteen tests in the pack's own suite that would otherwise
have been part of the engine's.

## What was rejected

**A folder in the engine.** Cheaper, and gives up the only mechanism that makes the
agnosticism claim checkable.

**Putting dice in the kernel instead.** Not ours to decide, and decided the other way
already: the kernel privileges no subject matter and contains no dice. An engine that wanted
them there would be asking the kernel to take a side about what rules are about.

**A pack that knows about doublet expansion.** Rejected above: it is the one place the
boundary is genuinely tempting to cross, and crossing it would make the pack silently
Hoyle-shaped.
