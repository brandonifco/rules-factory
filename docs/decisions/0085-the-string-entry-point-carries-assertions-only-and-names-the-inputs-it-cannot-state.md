# 0085 — The string entry point carries assertions only, and the registry names the inputs it cannot state

## Status

Accepted — 2026-10-26. Records the change on
[#692](https://github.com/brandonifco/rules-factory/issues/692), which takes its **option 3**: the
reading the existing contract ([#93](https://github.com/brandonifco/rules-factory/issues/93),
`docs/corpus-map.md`, "the typed entry point passes that request, inputs included, to the handler")
already implies, made explicit and held by a generated test. **Option 2**, a new way to carry inputs
on the string path, is **not built and stays open**: it would be a new contract, with its own type
story for an input the map does not name, and would need its own decision. Changes the generated
`Registry.g.cs` and `CorrespondenceTests.g.cs`; changes no behaviour of either `Registry.Resolve`
overload, no map, no overlay and no engine-owned file. Numbered 0085 because 0083 and 0084 are
taken and 0081 is held by an open pull request.

## Context

The generated `Registry.Resolve(string entryId, RuleRequest request)` hands a typed handler
`request as <Entry>Request ?? new(assertions)`. A `RuleRequest` carries assertions only (row 8), so on
that path every input an engine declared on the entry's partial request type is unstated, whatever
the caller asserts. Measured on the CanSpam engine at `c2a848d`, by a reflection probe over every
implemented entry's declared inputs: 39 of 55 implemented entries declare inputs; every one of them
loses outcomes on the string path, and 38 reach no value at all on it. The string path never reached
an outcome the typed path could not. The cases #692 collects (a caller-stated gate that the string
path reports as `MissingRulesData` and the typed path resolves) are one cause, and each engine's
typed path behaved as the entry specifies.

The architecture already says where inputs go. The map declares no inputs; the engine declares them
on the partial request type; the typed entry point carries them. So the string path was never a
second way to state an input. What was missing was saying so where a caller reads it, a way to ask
which inputs a given entry has, and a test that notices a hand-written handler answering the two paths
differently when nothing is stated.

## Decision

1. **`Resolve(string, RuleRequest)` is not expected to carry an engine-declared input.** Its
   documentation says so: a `RuleRequest` carries assertions only (row 8); on this path an entry
   resolves as though the caller stated none of its `DeclaredInputs`; to state them, resolve through
   `Resolve(IEntryRequest)` or `EntryPoints`. Its behaviour does not change.
2. **`Registry.DeclaredInputs(string entryId)`** returns the names of the inputs the engine declared on
   the entry's request type: the public instance properties with a public `set` or `init`, other than
   `EntryId` and `Assertions`, in declaration order (metadata token). Empty for an entry that declares
   none; `KeyNotFoundException` for an id the map does not have, as `Citations` does. The generator
   maps each id to its request type; it knows no rule, fact or name.
3. **A generated test per `implemented` entry**,
   `<id>__string_entry_point_is_the_typed_one_with_no_input_stated`, asserts that
   `Registry.Resolve(id, RuleRequest.Empty)` and `EntryPoints.<Member>.Resolve(<Request>.Empty)` have
   the same outcome: both throw an exception of the same type, or both resolve to `Equals` values, or
   both decline with an equal reason, locator and message. It claims nothing where the two contracts
   differ: only the "nothing stated" request exists on both paths.

## What this does not decide

* **Option 2.** A way to carry an input on the string path (a keyed bag on `RuleRequest`, say) is
  not built. Whether the string path should ever state an input is a question about a second contract
  for inputs the map does not name, and it stays open on #692.
* **That the two paths agree when something is stated.** They cannot be compared there; the string
  path cannot state it.
* **That an engine's string path is useful.** For an entry that declares inputs it answers the
  unstated case. `DeclaredInputs` says which entries those are.

## Consequence for engines

Each engine takes the new API and the new test on its next `produce`. A hand-written handler that
answers the string path differently from the typed path with nothing stated, for instance one that
tells the two apart by the identity of the request it was handed, now fails a generated test
(`validate.sh` runs it). A handler that reads only the inputs and assertions of its request is
unaffected: with nothing stated the two requests are equal in every respect it can read.

## Compatibility

Additive: one public method, new documentation, and one test per `implemented` entry plus one private
helper in the generated `CorrespondenceTests`. No signature changes. An engine that does not
re-produce is unchanged.
