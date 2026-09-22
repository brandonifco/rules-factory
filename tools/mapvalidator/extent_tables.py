"""`extent.tables`, the rows a section-designation extent took from each table it read (0035).

Split from `extent.py` so that neither file grows past the size the build holds a joined module
to. What lives here is the table half of an extent: the shape of the declared slice, and the
placement of a locator that cites a row against the rows the slice took. The section and page
halves stay in `extent.py`, which imports these two.
"""
from .locators import EXTENT_SECTION, _row_key, printed_designation


def _tables_extent(extent, numbers, bad):
    """`extent.tables` as (section, table) -> "all", "excluded", or the set of row keys (0035).

    Every table of every cited section is sliced, taken whole, or excluded with a reason. Whether
    a table this list does not name is printed inside the extent needs the corpus, and the
    `ecfr-xml` adapter is where it is refused (`mapper inventory`); what is checkable here is the
    shape of the list and the rows an entry cites against the rows the extent took.
    """
    declared = extent.get("tables")
    if declared is None:
        return {}
    if not isinstance(declared, list) or not declared:
        bad.append("  X  extent: `tables` is present and names no table; an extent that slices "
                   "no table declares no `tables`")
        return {}
    taken = {}
    for position, item in enumerate(declared):
        where = f"extent.tables[{position}]"
        if not isinstance(item, dict):
            bad.append(f"  X  {where} is not an object")
            continue
        for field in sorted(set(item) - {"section", "table", "rows", "excluded"}):
            bad.append(f"  X  {where}: `{field}` is not a field of a table slice "
                       f"(section, table, rows, excluded)")
        section = item.get("section")
        # The CFR's spelling, and only it. 0035's table machinery -- the row key, the cell
        # citation, the `ecfr-xml` adapter's table walk -- is the eCFR's, and no other adapter
        # reads a table at all. A slice declared against a designation no adapter can find a
        # table in would be accepted here and enumerate nothing, which is the shape 0035 was
        # careful to avoid: an extent that claims a table nobody read.
        match = EXTENT_SECTION.match(section) if isinstance(section, str) else None
        if not match:
            bad.append(f"  X  {where}: `section` is {section!r}, and a table is named inside one "
                       f"section designation such as \"§ 172.101\"; no other citation grammar "
                       f"has a table reader (0035)")
            continue
        designation = match.group(1)
        if designation not in numbers:
            bad.append(f"  X  {where}: {printed_designation(designation)} is not in the declared "
                       f"extent, so a slice of its table takes nothing the map claims to have read")
            continue
        number, table = designation, item.get("table")
        if not isinstance(table, int) or isinstance(table, bool) or table < 1:
            bad.append(f"  X  {where}: `table` is {table!r}; a table is named by its position in "
                       f"the section, counted from 1")
            continue
        if (number, table) in taken:
            bad.append(f"  X  {where}: § {number} table {table} is declared twice")
            continue
        if ("rows" in item) == ("excluded" in item):
            bad.append(f"  X  {where}: § {number} table {table} is sliced (`rows`), taken whole "
                       f"(`rows: \"all\"`) or excluded with a reason (`excluded`), and it "
                       f"declares " + ("both" if "rows" in item else "neither"))
            continue
        if "excluded" in item:
            reason = item.get("excluded")
            if not isinstance(reason, str) or not reason.strip():
                bad.append(f"  X  {where}: `excluded` is why this table is outside the slice, in "
                           f"words; {reason!r} is not one, and a table left out with no reason is "
                           f"an extent shrunk to what the walk happened to read")
                continue
            taken[(number, table)] = "excluded"
            continue
        rows = item.get("rows")
        if rows == "all":
            taken[(number, table)] = "all"
            continue
        if not isinstance(rows, list) or not rows:
            bad.append(f"  X  {where}: `rows` is \"all\" or a non-empty list of row keys; "
                       f"{rows!r} is neither")
            continue
        keys = set()
        for at, key in enumerate(rows):
            parsed = _row_key(key)
            if parsed is None:
                bad.append(f"  X  {where}: rows[{at}] is not a row key -- one or more "
                           f"{{\"column\": 2, \"is\": \"Acetal\"}} objects, read as a conjunction")
                continue
            if parsed in keys:
                bad.append(f"  X  {where}: rows[{at}] names a row this slice already takes")
                continue
            keys.add(parsed)
        taken[(number, table)] = keys
    return taken


def _place_row(name, citation, row, numbers, taken):
    """An in-scope table-row citation names a row the extent says it took (0035).

    The extent that slices a table names the rows it takes, so a rule cited from a row the slice
    does not hold is cited outside what the map claims to have read -- 0020's rule about sections,
    one unit down, and the reason the row key is the extent's and not an ordinal: both sides name
    the row by the same cells.
    """
    section, table, key = row
    if section not in numbers:
        return [f"  X  {name}: cites § {section}, outside the declared extent "
                f"({len(numbers)} sections), and is not `scope: out`; an in-scope rule is cited "
                f"inside what the map claims to have read"]
    slice_of = taken.get((section, table))
    if slice_of is None:
        return [f"  X  {name}: cites {citation}, and the extent declares no slice of § {section} "
                f"table {table}; a table a map reads a rule out of is one it claims to have read"]
    if slice_of == "excluded":
        return [f"  X  {name}: cites {citation}, and the extent excludes § {section} table "
                f"{table} from the slice; a table can be excluded or read, not both"]
    if slice_of == "all" or (key and key in slice_of):
        return []
    return [f"  X  {name}: cites {citation}, and the extent's slice of § {section} table {table} "
            + ("does not take that row; the rows an extent names are the rows it read" if key else
               "lists row keys, and no key names a row below the row above it (0043)")]
