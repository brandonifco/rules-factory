"""The section-designation locator grammar, as a validator reads it.

`examples/faa-part-107/check-locators-section.py` resolves a citation against the corpus; this
reads the same citations without one, to place each entry inside the extent its map declares.
The expressions are that checker's, and `test_check_map.py` runs both over every citation the
committed maps make and over the forms each decision adds, so the two cannot drift apart
silently.

Two things are named here: a **section** or a subpart
([0020](../../docs/decisions/0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)),
and a **row of a table**
([0035](../../docs/decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)), which is
the address a table cell did not have. A row is named by a cell that identifies it, in the
corpus's own column numbering, and never by where it sits: the corpus that forced this amends
constantly, and an ordinal that silently re-points at a different material is worse than a key
that stops resolving.
"""
import re


# The section-designation locator grammar's section and subpart, read the way
# examples/faa-part-107/check-locators-section.py reads them. `CITE_SECTION` and `CITE_SUBPART`
# are that checker's expressions, verbatim; `test_check_map.py` runs both over every citation in
# the Part 107 maps and requires them to agree, so the two cannot drift apart silently.
CITE_SECTION = re.compile(r"§+\s*(\d+\.\d+(?:-\d+)?)")
CITE_SUBPART = re.compile(r"\bsubpart\s+([A-Z])\b", re.I)
# One item of `extent.sections`: a section and nothing else -- no paragraph, no range.
EXTENT_SECTION = re.compile(r"^§\s*(\d+\.\d+(?:-\d+)?)$")


def cited_section(citation):
    """("section", "107.29") or ("subpart", "D") or None, for a section-designation citation.

    The section is the first one the citation names, which is the only one the grammar reads:
    `§ 107.29(a)(2), (b)` is two paragraphs of one section, and a citation cannot name two.
    """
    text = str(citation or "")
    section = CITE_SECTION.search(text)
    if section:
        return ("section", section.group(1))
    subpart = CITE_SUBPART.search(text)
    if subpart:
        return ("subpart", subpart.group(1).upper())
    return None


# A citation naming one row of one table (0035), read as the section locator checker reads it:
# `§ 172.101 table 3, row [column 2 = "Acetal"], column 7`. What this file needs of it is the
# table it names and the key it names the row by, so that an extent slicing a table can be held
# to the rows an entry actually cites.
CITE_TABLE_ROW = re.compile(
    r'^\s*§+\s*(?P<section>\d+\.\d+(?:-\d+)?)\s+table\s+(?P<table>\d+)\s*,\s*row\s*'
    r'\[(?P<key>.*)\](?:\s*,\s*column\s+[A-Za-z0-9]{1,4})?\s*\.?\s*$')
# A row the corpus leaves blank in the column that names the row above it (0043). What this file
# needs of it is only the table, because no declared row key names such a row: it is inside the
# extent where the extent takes its table **whole**, and nowhere else.
CITE_TABLE_ROW_BELOW = re.compile(
    r'^\s*§+\s*(?P<section>\d+\.\d+(?:-\d+)?)\s+table\s+(?P<table>\d+)\s*,\s*row\s+'
    r'blank\s+in\s+column\s+[A-Za-z0-9]{1,4}\s*(?:\[[^\]]*\]\s*)?'
    r'below\s+row\s*\[[^\]]*\](?:\s*,\s*column\s+[A-Za-z0-9]{1,4})?\s*\.?\s*$')
CITE_ROW_KEY_PAIR = re.compile(r'column\s+([A-Za-z0-9]{1,4})\s*=\s*"([^"]*)"')


def _normalise(value):
    return re.sub(r"\s+", " ", str(value)).strip()


def cited_row(citation):
    """(section, table position, key) for a table-row citation, or None.

    `key` is the frozen set of `column = value` pairs the citation names the row by, which is
    what an extent's declared row key is compared against: the pairs are a conjunction, so their
    order is not part of what they name. It is **None** for a row named below the row above it
    (0043), which no declared row key can name -- such a row is inside the extent only where the
    extent takes its table whole.
    """
    text = str(citation or "")
    below = CITE_TABLE_ROW_BELOW.match(text)
    if below:
        return (below.group("section"), int(below.group("table")), None)
    match = CITE_TABLE_ROW.match(text)
    if not match:
        return None
    pairs = CITE_ROW_KEY_PAIR.findall(match.group("key"))
    if not pairs or _normalise(match.group("key")) != "; ".join(
            f'column {c} = "{v}"' for c, v in pairs):
        return None
    return (match.group("section"), int(match.group("table")),
            frozenset((c, _normalise(v)) for c, v in pairs))


def _row_key(key):
    """A declared row key as a frozen set of pairs, or None where it is not one."""
    items = key if isinstance(key, list) else [key]
    if not items:
        return None
    pairs = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"column", "is"}:
            return None
        column, value = item.get("column"), item.get("is")
        if isinstance(column, bool) or not isinstance(column, (str, int)) \
                or not str(column).strip() or not isinstance(value, str):
            return None
        pairs.append((str(column), _normalise(value)))
    return frozenset(pairs)
