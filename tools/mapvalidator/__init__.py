# Map validation: the adversary. One of the three subsystems the map contract joins (0032,
# 0033), and the one whose attitude is "I don't care that the mapper thinks this is right,
# show me". It reads tools/mapcontract/ for what the map's fields mean and defines none of that
# itself; it knows nothing of the mapper that produced the map or the factory that consumes it,
# and a map written by hand is validated the same way.
#
# What it challenges is six kinds of truth (0033): structural, evidentiary, completeness,
# interpretive, relational and epistemic. The checks below are most of the first and none of the
# last three; docs/validator.md says which is which and what each still owes.
#
# tools/build-check-map.py joins these modules, and the contract's, into tools/check-map.py --
# the one standard-library file a map package ships (0015) and the factory imports (0016).
# The docstring below becomes that file's docstring and describes the built command, so
# "below" in it means further down check-map.py.
"""Validate a corpus map against docs/corpus-map.md and docs/decisions/0005.

`schema/` is empty and nothing has ever validated these maps. That is how
`kind: "rule"` -- outside the closed vocabulary -- shipped in both copies of the
backgammon map, and it is the gap this tool closes for everything the spec states
*structurally*. It does not read the corpus: `check-locators.py` does that.

What it cannot do, stated here rather than in a commit message. Each item says whether it is
**measured** -- a committed map was damaged that exact way and this file was watched not
noticing -- or **reasoned**, argued from the code and not yet attacked. `tools/mutate-map.py`
is what damages them, and `examples/validator-attack/` is the record.

  * **The measured miss rate of everything below is 74%.** Fourteen mutations over five
    committed maps and three locator grammars: 62 landed, 18 are refused, 44 pass (#259;
    16 and 46 when first measured at 69167d8, the two rows that moved being the epistemic
    checks 0034 added). Five of the twenty-five checks this file held when it was
    measured ever turned; there are twenty-seven now; `definition-continuations` (0046) is the
    newest and unmeasured. Read
    the list below as what a reader should expect to get away with, not as a list of
    theoretical gaps.
  * **A conflict nobody recorded is invisible.** `ambiguity.conflict` (0007) groups the
    entries that answer one contradicted question, and `conflicts` enforces that a group
    has two or more members, one fate, and one decision record. Nothing detects the
    conflict a mapper never noticed: two `clarity: clear` entries stating incompatible
    rules pass every check here. *Reasoned.* Its neighbour is measured, and the measurement
    moved: deleting a recorded ambiguity and asserting one reading -- premature collapse --
    passed on 5 maps of 5 before `superposition` existed, and is refused on 1 of 5 now; over
    every recorded ambiguity rather than one per map it is 12 of 64
    (`examples/collapse-trial/`). What that check reaches is narrower
    than the general case and is the one mechanical part of it (0034): where a *blind second
    mapping* read the passage as ambiguous and the adjudication answered "the corpus does not
    settle it", the map must record that doubt somewhere. Where both readers made the same
    silent choice there is no record, no flag and no trace. Inventing an ambiguity the corpus
    settles passes on 5 of 5, and is catchable and is #271: `ambiguity.question` is free prose,
    where `crossReferences.cites` on the same entry must appear verbatim in the evidence.
  * **A gate is not checked against the corpus at all.** A missing `enabledBy` edge, a
    missing `suspendedBy` edge and an invented `dependsOn` edge each leave the map
    internally consistent, and `gates`, `references` and `no-cycles` all pass.
    *Measured: 0 of 13.*
  * **An entry can quote the wrong sentence of the right passage.** The locator resolves and
    the quote is verbatim of the extraction, so nothing here and nothing in the locator
    checkers can say the entry is about a different sentence than the one it cites.
    *Measured: 1 of 5, and that one caught by `cross-references` bookkeeping rather than by
    anything having read the corpus.*
  * **A rule nobody mapped leaves no trace.** An omitted definition, and an applicability
    rule removed together with the edges that named it, both pass every check here; the
    entry that is gone is not owed by anything that remains. *Measured: 0 of 4 and 0 of 4.*
  * **A check whose subject matter the damage removed says NOT VERIFIED and the run stays
    green,** because such a check declares it had no subject. Turning a map's only assertion
    into an operation silences `asserted-by`; removing the rule every other entry was
    suspended by silences `gates`. *Measured, and filed as #268.*
  * **Correspondence row 7** ("two implemented entries with no entry for their
    combination") is a fact about pairs and about interactions the map does not enumerate.
    It is not evaluated. The `correspondence` check therefore proves that every entry is
    reachable by rows 1-6 and 8, not by all eight.
  * Rows 1-8 are not exhaustive by design: a built, clear, unambiguous rule matches no row
    because the engine simply answers. Unmatched entries are reported; an unmatched entry
    is a **failure** only when `status: declined`, which asserts no implemented path at all
    and therefore owes a runtime reason.
  * **An absence is claimed here and proved elsewhere.** `absentFrom` (0009) asserts the
    corpus does not contain the rule. Nothing in this file reads a corpus, so the `absent`
    check enforces only the shape of the claim -- that it is non-empty, that it excludes
    the fields it contradicts, and that nothing depends on a rule that does not exist. The
    claim itself is falsified by `check-locators.py`, which searches the text.
  * **A cross-reference nobody noticed is invisible.** `cross-references` reads the
    pointer phrases in `POINTER_PHRASES` and those the corpus declares as `pointerPhrases` in
    its manifest (0026), and no others; a corpus that points somewhere in words outside both
    produces a map that passes. What it does refuse is a silent zero: a corpus that declares
    no phrases and on which the built-in list detects nothing fails, and each corpus's count
    is printed.
  * Nothing here checks that an entry is the *right* decomposition of the corpus, that a
    gate list (`enabledBy`, `suspendedBy`) is complete, or that `evidence` is sufficient.
    Those are review.

Where each check runs is stated in STATUS_DEPENDENT below (0015): every check runs before a
map is published; the status-dependent ones run again in the engine, on its merged map.

Usage: check-map.py <corpus-map.json> [--manifest PATH] [--repo-root PATH] [--only CHECK]
                    [--phase publish|consumer]
Exit 0 only if every check that ran passed and at least one check actually checked
something; 1 if any check failed or skipped with subject matter; 2 on a usage error.
"""
