"""The locator grammars, as a validator reads them without a corpus.

`examples/faa-part-107/check-locators-section.py` resolves a citation against the corpus; this
reads the same citations without one, to place each entry inside the extent its map declares.
The expressions are that checker's, and `test_check_map.py` runs both over every citation the
committed maps make and over the forms each decision adds, so the two cannot drift apart
silently.

Three things are named here: a **section** or a subpart
([0020](../../docs/decisions/0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md)),
and a **row of a table**
([0035](../../docs/decisions/0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md)), which is
the address a table cell did not have. A row is named by a cell that identifies it, in the
corpus's own column numbering, and never by where it sits: the corpus that forced this amends
constantly, and an ordinal that silently re-points at a different material is worse than a key
that stops resolving. And a **printed page**, which the page grammars address a passage by, read
here for the same reason the section is: so that `extent` can place a page citation inside the
range a map declares it read ([#269](https://github.com/brandonifco/rules-factory/issues/269)).
"""
import re


# The section-designation locator grammar's section and subpart, read the way
# examples/faa-part-107/check-locators-section.py reads them. `CITE_SECTION` and `CITE_SUBPART`
# are that checker's expressions, verbatim; `test_check_map.py` runs both over every citation in
# the Part 107 maps and requires them to agree, so the two cannot drift apart silently.
CITE_SECTION = re.compile(r"§+\s*(\d+\.\d+(?:[A-Za-z]|-\d+)?)(?![A-Za-z0-9-])")
CITE_SUBPART = re.compile(r"\bsubpart\s+([A-Z])\b", re.I)
# One item of `extent.sections`: a section and nothing else -- no paragraph, no range.
EXTENT_SECTION = re.compile(r"^§\s*(\d+\.\d+(?:[A-Za-z]|-\d+)?)$")


def section_pointer_match_is_complete(text, match):
    """Whether a section-sign match ends at a complete designation token (#323).

    Corpus regexes are interrogations, not permission to rename a citation. A match may end
    before punctuation or prose, but not while the printed designation continues with an
    alphanumeric character or a hyphen.
    """
    return ("§" not in match.group(0) or match.end() >= len(text)
            or not (text[match.end()].isalnum() or text[match.end()] == "-"))


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
    r'^\s*§+\s*(?P<section>\d+\.\d+(?:[A-Za-z]|-\d+)?)\s+table\s+(?P<table>\d+)\s*,\s*row\s*'
    r'\[(?P<key>.*)\](?:\s*,\s*column\s+[A-Za-z0-9]{1,4})?\s*\.?\s*$')
# A row the corpus leaves blank in the column that names the row above it (0043). What this file
# needs of it is only the table, because no declared row key names such a row: it is inside the
# extent where the extent takes its table **whole**, and nowhere else.
CITE_TABLE_ROW_BELOW = re.compile(
    r'^\s*§+\s*(?P<section>\d+\.\d+(?:[A-Za-z]|-\d+)?)\s+table\s+(?P<table>\d+)\s*,\s*row\s+'
    r'blank\s+in\s+column\s+[A-Za-z0-9]{1,4}\s*(?:\[[^\]]*\]\s*)?'
    r'below\s+row\s*\[[^\]]*\](?:\s*,\s*column\s+[A-Za-z0-9]{1,4})?\s*\.?\s*$')
CITE_ROW_KEY_PAIR = re.compile(r'column\s+([A-Za-z0-9]{1,4})\s*=\s*"([^"]*)"')


# The printed page a page-grammar citation names, read the way the two page locator checkers
# read it. `tools/check-locators.py`'s `--page-re` default is this expression verbatim, and
# `examples/srd-52-combat/check-locators-pdf-text.py`'s `PAGE` is this expression with `\s*$`
# after it, because `Combat / Making an Attack / p. 15` puts the page last. Reading the looser of
# the two here is deliberate: placing a citation inside the extent is a weaker question than
# resolving it, and a citation whose page is not where its own grammar requires is refused by
# that grammar's checker rather than twice. `test_check_map.py` runs all three over every
# citation the committed page maps make, so they cannot drift apart silently.
CITE_PAGE = re.compile(r"\bp\.\s*(\d+)")


def cited_page(citation):
    """The printed page a citation names, as an int, or None.

    The first page the citation names, which is the only one the grammar reads: a page citation
    names one page, and a quote that straddles a break cites either of the two it touches.
    """
    match = CITE_PAGE.search(str(citation or ""))
    return int(match.group(1)) if match else None


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
