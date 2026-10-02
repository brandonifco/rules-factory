# 0076 — What a change owes the semantic review is its review class, computed from the diff

## Status

Accepted — 2026-10-02. Records the decision on
[#595](https://github.com/brandonifco/rules-factory/issues/595), on the owner's instruction.
**Narrows the trust model's answer to "which changes are reviewed as rules"**, which is why it is
recorded rather than just done: it makes some pull requests owe less than they did, and that is
only safe if it can be shown no change to a rule is among them. **Extends
[0071](0071-review-evidence-is-reused-by-semantic-impact-not-discarded-by-a-changed-commit.md)**,
whose adversarial self-review and attestation chain it leaves whole for the changes that owe them,
and **[0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)**'s
`review.semanticPaths`, which it leaves where it is and reads more finely. **Does not touch
[0072](0072-an-embedded-engines-semantic-surface-is-its-own-alone-and-the-host-gates-its-own-files.md)**:
the surface is still the engine's alone.

## Context

Until 0071 the semantic surface decided one thing, and decided it once: a pull request that changed
a path on `review.semanticPaths` needed a semantic verdict, and one that did not needed none. 0071
hung more on the same question. A packet that names an entry is refused until each entry has a
committed `reviews/self-review/<entry>.json`; a full review is owed when a decision record or a
managed review file moved; and `pr-policy.py` asks any change on the surface for an entry, a map and
a locator. The default surface is `src/**`, `tests/**`, `overlay/**`, the pins, `corpus/**` and
**`docs/decisions/**`**.

A question that coarse has answers that are not about rules. Three pull requests in one private
engine, all inside one week, are the measurement:

* **A decision record and nothing else** (Reykholt #79): one new file under `docs/decisions/`, no
  code, no overlay, no map, "No behaviour changes". It records the owner's rulings on fifteen
  Story Mode questions, which the work that builds to them will implement. The rails asked it for an
  entry, so it named `story-mode-follows-base-game` as a "principal entry" that it does not
  implement, and for that entry a self-review answering all twenty classes `not-applicable`, about
  code that was not written. The record in the pull request says as much. A reviewer cannot learn
  anything from that file that the diff does not already say, and the one thing the ceremony could
  have caught, a ruling that contradicts one in force, is not something an all-N/A record can see.
* **A real implementation** (Reykholt #77): ninety-one files, among them twenty-seven overlay rows,
  twenty-four source files and twenty-one test files. Every protection 0071 added is right for it,
  and nothing here changes it.
* **A factory and kernel update** (Reykholt #68): the rails, the kernel pin and the regenerated
  `MapEntries.g.cs` and lock files, with the map, the corpora and every handler unmoved. It claims no
  behavioural change and says what moved. The pins, the generated code and the locks are on the
  surface, so the gate owed a semantic verdict, and a reviewer was asked to read as a rule a diff
  that no rule is in. Since #572 it could at least be given a packet; it could not be given a reason.

The cost is not the minutes. A check that is satisfied by a sentence nobody can disagree with
teaches the people who meet it to write that sentence, and it is then the one standing between a
reviewer and a self-review that means something. The ceremony was weakening the review it was there
to protect.

## Decision

**What a change owes the semantic review is its review class, and the class is computed from the
diff.** One module, `tools/factory/reviewclass.py`, vendored into every engine as
`scripts/factory/reviewclass.py`, names it, and `tools/pr-policy.py`, `tools/conformance-gate.py`,
`tools/review-packet.py`, `tools/repair-packet.py` and `tools/record-verdict.py` read that one
answer. Five classes:

| Class | A diff that is | Owes |
|---|---|---|
| `semantic-implementation` | handlers, rule behaviour, the overlay, the corpus; anything on the surface not shown below to be inert | named entries, a map and a locator; `reviews/self-review/<entry>.json` for each; a semantic packet; a semantic verdict; a mutation |
| `semantic-ruling` | a decision that changes how rules are read: an existing decision record edited non-cosmetically or deleted, or a new one whose header says `Supersedes:` another | the entries it affects or a `decision scope:`; `reviews/rulings/<decision>.json`, in place of a self-review; a semantic packet; a semantic verdict |
| `decision-record-only` | one or more new decision records that overrule none, and nothing else | structural validation |
| `generated-or-provenance` | a factory update: every changed file one the factory writes, `provenance.json` among them, the maps, corpora and randomness the same at the base and the head, each file the bytes the head record hashes | structural and provenance validation: the `## Produced by the factory` section, admitted |
| `documentation` | a document, a process file, or C# that differs from its base in comments and formatting alone, proved by the scanner | structural validation |

**The diff decides; the pull request's words can only add review.** The pull request carries a
`- review class:` line in `## Map and rules conformance`, and it is checked against the computed
class. It can claim an exemption the diff shows, and it can raise a class. It cannot lower one. A
diff that touches the surface and claims nothing is reviewed as a `semantic-implementation`, exactly
as it was before, and `pr-policy.py` prints how to claim the exemption without failing the pull
request. **An exemption must be claimed**, because the claim is also the author's statement that no
behaviour changes, which is a thing a person should have to say once.

**The classifier fails closed.** Anything it cannot prove inert is an implementation: a path the
ownership table cannot place, a file it cannot read at either side, a provenance record it cannot
compare, a scanner that cannot tell where a comment ends, an ownership module it cannot load, a
class that is not one of the five. Each exemption is a closed predicate over bytes and not a
judgement:

* **A new decision record that overrules nothing is `decision-record-only`.** A new record binds
  nothing until the work that builds to it is reviewed, and that work is its own pull request with
  its own entries. What makes a record overrule another is a **header line** (`**Supersedes:**`,
  `Amends:`, `Overrules:`, ...), never a word in the prose: the record of the rulings that found
  this says that it can be "overruled by a later record", and a matcher on the word would have
  made it the ruling it is not. An edit to an existing record that is more than whitespace, and a
  deletion, is a `semantic-ruling`: it may be the one the engine is built to, and a tool cannot tell
  a typo from a reversal where a reviewer can. A decision that overrules one in force without
  saying so in its header is not seen by this, and the class a pull request can *raise* itself to is
  the answer to that: a record the diff shows overrules nothing may still say it is a ruling.
* **A regeneration is `generated-or-provenance` only when the rules did not move.** Every changed
  path is one the factory writes, by the ownership table the commit was produced with (the corpus
  copy is excluded: it is rule text); `provenance.json` is among them, because a regeneration cannot
  write a generated file without moving its record; the base and head records name the same maps
  (package, version, package digest), the same corpora (source, content hash) and the same
  randomness; the head record says the factory was not dirty; each generated or managed file's bytes
  are the ones the head record hashes; and a lock file moves only beside the pins that explain it. The
  factory and the kernel may differ, which is what a factory update is. A moved map, a hand-written
  file, an overlay row, a decision record, a retired path, a dirty factory and a hand-edited generated
  file each leave a pull request an implementation, and each is a test.
* **C# is `documentation` only if its code is the same.** Comments are removed and replaced by a
  separator, every string and character literal and every preprocessor line is kept byte for byte,
  and whether two tokens are separated is kept while by how much is not, so `a + ++b` and `a++ + b`
  differ. A literal or comment the scanner cannot end is unprovable. It is built on the scanner the
  reference graph already uses, and a `//` inside a changed string is code.

**What each class owes is one table**, `reviewclass.OWES`, which the rails read, so "owes a
verdict" has one source. `review-packet.py` **refuses a semantic packet** for a change that owes
none: an entry, a self-review and a packet written to satisfy a policy are what this removes. The
structural cut, `--stdout`, and an independent packet (an issue labelled for independent review still
owes one, whatever the class) are unaffected. The packet's first section states the class and why,
and its identity records it, so a status can be read for what it was. `record-verdict.py` refuses a
semantic verdict on a packet whose class owes none. The mutation requirement moves with the self-review: only an
implementation writes a test, so only an implementation names a mutation.

**A ruling is reviewed with a record of its own.** `reviews/rulings/<decision record name>.json`,
one per decision record the pull request changes, bound to that record's SHA-256 so an edit after the
review makes it stale, with a `scope`, the `entries` it affects, and six classes — `corpus-basis`,
`owner-authority`, `conflicts`, `implemented-behaviour`, `unreached-cases` and `pinning-test` —
each answered or not applicable with a reason held to the floor a self-review reason is.
`tools/review-scope.py ruling-review` prints the skeleton and checks it. A ruling that names entries
is still handed their packets, and owes no self-review of code it does not write.

## What this does not decide

* **That a factory or kernel update changed no behaviour.** The classifier can see that the rules
  did not move (the map, the corpora, the randomness, every hand-written file) and cannot see
  whether a new generator or kernel changed what the engine does with them. That is what the
  engine's own tests are for, and `validate.sh full` runs them against a regeneration byte for byte;
  the class removes a reviewer's reading of generated code, not that gate. If it is ever shown that
  a produce with these facts unmoved changed an answer, the answer is a fact added to the
  predicate, not a reviewer asked to find it by reading.
* **That a comment says what the rule says.** A comment that misstates the rule has no semantic
  effect, and a comment-only change owes none. That reviews have failed on prose beside code is a
  reason for a reviewer to read a comment when they read the code, which they still do for any change
  that has code in it.
* **A weaker surface.** `review.semanticPaths` is still the engine's, still the policy's, and still
  what decides which paths *can* be semantic. This only decides, for the ones that are on it, which
  the diff proves are not.

## Compatibility

Fourteen managed files change: six tools (`pr-policy`, `conformance-gate`, `review-packet`,
`review-scope`, `repair-packet` and `record-verdict`) and the eight documents that say what they do
(the contract, the three charters, the pull request template, and the agent-team, review-evidence and
adversarial-self-review documents). One module is vendored that was not
(`scripts/factory/reviewclass.py`). **Nothing engine-owned changes.** `.github/agent-policy.json`
keeps `docs/decisions/**` on the surface, which is now right: the classifier reads it. An engine takes
this with one `factory produce`, which is a `generated-or-provenance` pull request under the rails
it brings.

Before an engine re-produces nothing changes for it; after it, **no pull request owes more than it
did**. A pull request body that writes no `review class:` line is read exactly as before, and the one
new finding a body can earn is a claim the diff contradicts. What changes is that a pull request that
shows and claims one of the three exemptions stops owing what it never needed. An existing
`reviews/self-review/<entry>.json` that was written only to satisfy the old rule is neither read nor
deleted: it is evidence about an entry that no longer owes it.
