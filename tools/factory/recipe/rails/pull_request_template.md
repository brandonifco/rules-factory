<!--
Emitted by rules-factory as a managed file (decision 0029). Every section below is required, and
tools/pr-policy.py checks that mechanically on every push to this pull request. A section left as
its placeholder, or filled with a claim where the template asks for output, is a failed check —
not because the form matters, but because a reviewer who cannot see what you ran has to take your
word for it, and this repository does not run on anybody's word.
-->

## Linked issue

<!-- Exactly one. A branch closes exactly one issue (AGENTS.md section 4). -->

Closes #

## Exact behavioural claim

<!-- What this engine does after this change that it did not do before, in terms a caller would
     recognise. Not "adds support for X" — what input now produces what output, and what is
     declined and why. -->

## Scope, and what this deliberately does not do

<!-- The non-goals are what make the diff reviewable. Anything you noticed and did not fix
     belongs here by name, as a new issue, not as a second commit. -->

## Map and rules conformance

<!-- For anything touching the rules surface. "N/A" only where nothing here does. -->

- entry id(s):
- map package and version:
- source locator(s):
- owner's rulings used, if any:

## Tests and evidence

<!-- The exact commands, and what they actually printed. "Tests pass" is not evidence; a run is.
     Every test names the mutation that makes it fail, and you must have watched it fail — a test
     nobody has watched fail is not yet a test. -->

```
$ ./scripts/validate.sh full
```

Mutations observed:

<!-- one line per test: the test name, the mutation, and that it failed with it in place -->

## Determinism

<!-- What this change does about wall-clock time, ambient locale or culture, environment-dependent
     ordering, randomness, and hash codes or object identity in anything observable. "Nothing here
     reads the machine" is a fine answer where it is true. -->

## Decisions and trade-offs

<!-- What you chose, what you rejected, and why. If you resolved something that felt like a
     judgement call about what a rule means, it was probably an escalation you should have raised
     instead (AGENTS.md section 6) — say so here rather than leaving it buried in the diff. -->

## Known limitations and unresolved behaviour

<!-- What this does not answer, and what the engine declines. A decline that names why and cites
     where is the engine working; say which cases they are. -->

## Agent provenance

<!-- Who did what. "Independently reviewed by" is required only for an issue classified as
     needing independent review; say "not required" otherwise. -->

- implemented by:
- structurally reviewed by:
- semantically reviewed by:
- independently reviewed by:

## Unrelated changes

None
