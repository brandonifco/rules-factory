"""The correspondence table: which runtime row each entry reaches, and the overlaps that are
data errors rather than precedence.
"""
from .diagnostics import skip, verdict
from mapcontract.entry import entries_of, fate_of, index, label


ROW_DESCRIPTIONS = {
    1: "scope: out -> OutsideCurrentScope",
    2: "status mapped/blocked -> UnsupportedRule",
    3: "definedElsewhere -> MissingRulesData",
    4: "beyondAdapter -> MissingRulesData",
    5: "operation with an unimplemented value dependency -> MissingRulesData",
    6: "fate: unresolved -> RequiresInterpretation",
    8: "kind: assertion -> nothing; the engine demands the value",
}


def matched_rows(entry, by_id):
    """Every correspondence row whose predicate holds, ignoring precedence.

    Row 7 is absent: "two implemented entries with no entry for their combination" is a
    fact about a pair and about an interaction the map does not enumerate.
    """
    rows = []
    if entry.get("scope") == "out":
        rows.append(1)
    if entry.get("status") in ("mapped", "blocked"):
        rows.append(2)
    if "definedElsewhere" in entry:
        rows.append(3)
    if "beyondAdapter" in entry:
        rows.append(4)
    if entry.get("kind") == "operation":
        for dep in entry.get("dependsOn") or []:
            target = by_id.get(dep) if isinstance(dep, str) else None
            if isinstance(target, dict) and target.get("kind") == "value" and target.get("status") != "implemented":
                rows.append(5)
                break
    if fate_of(entry) == "unresolved":
        rows.append(6)
    if entry.get("kind") == "assertion":
        rows.append(8)
    return rows


def check_correspondence(ctx):
    """Every entry is reachable by some correspondence row, or is a plain computable rule.

    Rows are checked in order and the first match wins, so matching two is not itself an
    error -- 0005 notes that `status: mapped` with `fate: unresolved` matches rows 2 and 6
    on eleven entries today and is exactly what precedence is for. What is reported:

      * an entry matching no row at all. A failure when `status: declined`, which claims no
        implemented path and therefore owes a runtime reason; informational otherwise,
        because a built clear rule matches no row by design.
      * two specific unordered overlaps that precedence hides but that are data errors:
        `definedElsewhere` together with `beyondAdapter` (rows 3 and 4 both fire with the
        same runtime reason from contradictory evidence), and a `kind: assertion` that also
        declines (row 8 says an assertion is a parameter, not a failure to resolve).
    """
    by_id, bad, notes, matched = index(ctx["map"]), [], [], 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        rows = matched_rows(entry, by_id)
        if rows:
            matched += 1
            first = rows[0]
            notes.append(f"  .  {name}: row {first} ({ROW_DESCRIPTIONS[first]})")
        elif entry.get("status") == "declined":
            bad.append(f"  X  {name}: status is `declined` -- no implemented path at all -- and no "
                       f"correspondence row says what the engine returns instead")
        else:
            notes.append(f"  .  {name}: matches no row; the engine answers it (status "
                         f"{entry.get('status')!r}, clarity {entry.get('clarity')!r})")
        if 3 in rows and 4 in rows:
            bad.append(f"  X  {name}: carries both `definedElsewhere` and `beyondAdapter`; the rule is "
                       f"either here and unreadable or defined in a corpus not admitted, not both")
        if 8 in rows and (3 in rows or 4 in rows or 6 in rows):
            others = [r for r in rows if r in (3, 4, 6)]
            bad.append(f"  X  {name}: is `kind: assertion` and also matches row(s) {others}; an assertion "
                       f"is a parameter the engine demands, not a decline")
    total = len([e for e in entries_of(ctx["map"]) if isinstance(e, dict)])
    if not total:
        return skip("there are no entries to place in the table")
    result = verdict(bad, f"{matched} of {total} entries match a row; the rest are plainly computable "
                          f"(row 7 is not evaluated)",
                     "an entry cannot be placed in the correspondence table")
    if ctx["verbose"]:
        result.details = result.details + notes
    return result
