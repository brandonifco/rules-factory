# Map validation: the checks that hold a map to docs/corpus-map.md, and one of the three
# subsystems the map contract joins (0032). It reads tools/mapcontract/ for what the map's
# fields mean and defines none of that itself; it knows nothing of the mapper that produced
# the map or the factory that consumes it.
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

What it cannot do, stated here rather than in a commit message:

  * **A conflict nobody recorded is invisible.** `ambiguity.conflict` (0007) groups the
    entries that answer one contradicted question, and `conflicts` enforces that a group
    has two or more members, one fate, and one decision record. Nothing detects the
    conflict a mapper never noticed: two `clarity: clear` entries stating incompatible
    rules pass every check here.
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
