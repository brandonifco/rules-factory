#!/usr/bin/env python3
"""Check that each map entry's *section* citation matches where its evidence actually sits.

Companion to `tools/check-locators.py`, which checks a `printed-page` locator grammar by
finding the evidence in a flat text corpus and walking back to the nearest `{NNN}` page
marker. Part 107 has no page markers: its `locatorGrammar` is `section-designation` and a
citation reads `§ 107.29(a)(2), (b)`. The principle generalises; the implementation does
not share a line with it. See ../README.md, "Is a section citation checkable?", for why.

What it does: parse the eCFR XML, give every paragraph its designation path by containment
(`107.29` / `a` / `2`), find the entry's evidence quote verbatim, and require that **every**
paragraph the quote touches lies inside the paragraph set the citation names.

Three deliberate differences from the page-marker checker, each of which makes this one
stricter rather than looser:

  * **Containment, not proximity.** A page marker is positional, so a quote straddling a
    break makes two citations honest and the checker accepts either. An XML element
    encloses its text, so there is nothing to accept either way: a quote is inside the
    cited paragraph or it is not.
  * **Every occurrence, not the first.** The corpus repeats whole sentences verbatim -- the
    anti-collision sentence appears identically in § 107.29(a)(2) and again in (b). A
    `find`-the-first-hit probe would verify such a quote against whichever copy came first
    and call it checked. Here a quote that appears N times must have all N occurrences
    inside the citation, and the count is reported.
  * **Exact, not longest-prefix.** The page checker matches the longest contiguous prefix
    of the evidence and reports coverage, because it was retrofitted onto evidence that was
    never a quote. Here a quote either appears or the entry fails. Ellipsis (` ... `)
    splits a quote into fragments, each of which must appear in order and inside the
    citation -- that is the ellipsis rule #18 asks for, proposed rather than settled, since
    `docs/` is not this directory's to change.

**It reads any corpus the eCFR versioner serves, not only Part 107.** Two things were title-14
shaped and are not any more (trial 9, examples/tax-121-principal-residence): a section's subpart
is read from its ancestry instead of assumed, so a single section served as a bare `DIV8` is
indexed like one served inside a `DIV5`/`DIV6`; and a section designation may carry a hyphenated
suffix, so `§ 1.121-1` and `§ 1.121-2` are two sections rather than one. Nothing else about what
a citation names changed, and no Part 107 path moves.

**A rule stated in a table row has an address, and the quote is held to the row** (rules-factory
decision 0035). `§ 172.101 table 3, row [column 2 = "Acetal"], column 7` names a table by its
position in the section, a row by a cell that identifies it in the corpus's own column numbering,
and a cell by its column. The row's text is its cells in column order joined by ` | `, empty cells
kept as empty, and `evidence` is one contiguous verbatim span of that. A key that resolves to two
rows is **refused**, never resolved to the first of them. Until this the section tree indexed a
section's `<P>` and `<EXAMPLE>` children and nothing else, which is 6.6% of § 172.101 (#261).

**An authored example that bounds a term is held to the same standard** (rules-factory decision
0031). `ambiguity.bounds.examples[].text` is a quotation with a `locator` of its own, so each is
checked here by the same function as `evidence`, and a bound whose words are not at its citation
fails the run: a ruling is refused or admitted by comparing it against that quotation.

It does not check that the evidence is the *right* passage for the entry, only that the
citation names where it is. And it cannot check an entry whose evidence is not a quote:
such an entry is reported and **fails the run**. It never reports ok for a citation it did
not check.

Usage: check-locators-section.py <corpus-map.json> <corpus.xml>
Exit 0 if every entry was checked and agreed, 1 otherwise, 2 on a usage error.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET

ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*")
DESIGNATOR = re.compile(r"^\(([A-Za-z0-9]{1,4})\)\s")
ROMAN = re.compile(r"^(?:i|ii|iii|iv|v|vi|vii|viii|ix|x{1,3}(?:i[xv]|v?i{0,3}))$")

# Which nesting level a designator opens, by its form. CFR numbers paragraphs
# (a) / (1) / (i) / (A) from the outside in, and eCFR XML flattens them into sibling <P>
# elements with the designator left in the text, so the tree has to be rebuilt from the
# forms. Where a form is genuinely ambiguous the paragraph is refused, not guessed: see
# `level_of`.
LEVEL_LOWER, LEVEL_DIGIT, LEVEL_ROMAN, LEVEL_UPPER = 1, 2, 3, 4


class Ambiguous(Exception):
    """A designator that could open two different levels. Never resolved by guessing."""


ROMAN_ORDER = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
               "xi", "xii", "xiii", "xiv", "xv"]


def level_of(token, stack):
    """The level a designator opens, or Ambiguous.

    `(i)`, `(v)` and `(x)` are both lowercase letters and roman numerals, so the form alone
    does not decide. What does decide is **what the token would have to continue**: a run
    proceeds one step at a time, so a token is placed at a level only if it is that level's
    next designator, and a token that could continue two open runs at once is refused.

    § 107.135(c)(1) is the case that exercises it: (i)...(v) under a digit. (v) is the
    successor of the open (iv) at the roman level and is not the successor of the open
    letter at the first level, so it resolves. A letter run reaching (i) directly after (h)
    *while a digit level is open* would satisfy both and raises -- the corpus contains no
    such paragraph, and inventing a tie-break from zero instances is the guess this refuses
    to make.
    """
    if token.isdigit():
        return LEVEL_DIGIT
    if token.isupper():
        return LEVEL_UPPER
    if not token.islower():
        raise Ambiguous(token)
    looks_roman = bool(ROMAN.fullmatch(token))
    if not (looks_roman and len(token) == 1):
        return LEVEL_ROMAN if looks_roman else LEVEL_LOWER

    candidates = set()
    if continues(token, stack.get(LEVEL_ROMAN), ROMAN_ORDER) or (
        token == "i" and LEVEL_ROMAN not in stack and LEVEL_DIGIT in stack
    ):
        candidates.add(LEVEL_ROMAN)
    if continues(token, stack.get(LEVEL_LOWER), None) or (
        token == "a" and LEVEL_LOWER not in stack
    ):
        candidates.add(LEVEL_LOWER)
    if len(candidates) != 1:
        raise Ambiguous(token)
    return candidates.pop()


def continues(token, open_designator, order):
    """True when `token` is the next designator after `open_designator` in a run."""
    if open_designator is None:
        return False
    if order is None:
        return len(open_designator) == 1 and token == chr(ord(open_designator) + 1)
    if open_designator not in order:
        return False
    at = order.index(open_designator)
    return at + 1 < len(order) and order[at + 1] == token


def subpart_of(section, parents):
    """The N of the DIV6 a section sits in, or None where it sits in no subpart.

    The eCFR versioner serves a whole part as DIV5/DIV6/DIV8 and a single section as a bare
    DIV8, so a section's subpart is read from its ancestry rather than assumed. Every Part 107
    section is inside a subpart and keeps the path it always had; § 1.121-1, fetched on its
    own, has None there, which `matches` already drops for a section-anchored citation.
    """
    node = parents.get(section)
    while node is not None:
        if node.tag == "DIV6":
            return node.get("N")
        node = parents.get(node)
    return None


def paragraphs(root):
    """Every <P> in document order with its designation path and its normalised text.

    Path is (subpart, section, *designators) -- e.g. ("B", "107.29", "a", "2"). A <P> with
    no designator (a section's lead-in) takes the path of its section.
    """
    out = []
    parents = {child: parent for parent in root.iter() for child in parent}
    for section in root.iter("DIV8"):
        subpart = subpart_of(section, parents)
        stack = {}  # level -> designator, for the levels currently open
        for p in section:
            if p.tag == "EXAMPLE":
                label = example_label(p)
                text = normalise("".join(p.itertext()))
                if label is None or not text:
                    continue
                path = (subpart, section.get("N")) + tuple(
                    stack[k] for k in sorted(stack)
                ) + (label,)
                out.append((path, text, None))
                continue
            if p.tag != "P":
                continue
            text = normalise("".join(p.itertext()))
            if not text:
                continue
            match = DESIGNATOR.match(text)
            if match:
                token = match.group(1)
                try:
                    level = level_of(token, stack)
                except Ambiguous:
                    out.append((("?",), text, token))
                    continue
                stack = {k: v for k, v in stack.items() if k < level}
                stack[level] = token
            path = (subpart, section.get("N")) + tuple(
                stack[k] for k in sorted(stack)
            )
            out.append((path, text, None))
    return out


def normalise(text):
    return re.sub(r"\s+", " ", text).strip()


# An <EXAMPLE>'s <HED>: "Example 4.", "Example.", or "Example 1 Non-residential use of property
# not within the dwelling unit." The label is the word and its number and stops there, because
# the rest of a Treasury regulation's example heading is a descriptive title that the map must
# be free to quote rather than to cite.
EXAMPLE_HEAD = re.compile(r"^Examples?\s*(\d+)?", re.I)


def example_label(element):
    """`Example 4`, or `Example` for an unnumbered one; None where the head is not one.

    A worked example in an eCFR-served regulation is an <EXAMPLE> sibling of the <P>
    elements, not a designated paragraph, so the designator tree above cannot reach it and
    a map could not cite one at all: trial 9's first mapping recorded that as its finding 3
    and declined all four examples paragraphs partly for that reason. Examples in a Treasury
    regulation are promulgated text and can be the only authority in the corpus for a rule
    (§ 1.121-1(b)(4) Example 4 is), so they are indexed under the paragraph that introduces
    them, one level deeper: ("1.121-1", "b", "4", "Example 4").
    """
    head = element.find("HED")
    if head is None:
        return None
    match = EXAMPLE_HEAD.match(normalise("".join(head.itertext())))
    if not match:
        return None
    return "Example" + (f" {match.group(1)}" if match.group(1) else "")


def corpus_index(xml_path):
    """The whole corpus as one normalised string, plus the span each paragraph occupies."""
    root = ET.parse(xml_path).getroot()
    pieces, spans, refused = [], [], []
    cursor = 0
    for path, text, bad in paragraphs(root):
        if bad is not None:
            refused.append((text[:60], bad))
            continue
        start = cursor
        pieces.append(text)
        cursor += len(text) + 1  # the space this join inserts
        spans.append((start, start + len(text), path))
    return " ".join(pieces), spans, refused


# A section designation: `107.29` in title 14, `1.121-1` in title 26, where a Treasury
# regulation's number carries a hyphenated suffix. The suffix is part of the section number and
# never a paragraph, so reading it is what lets `§ 1.121-1` and `§ 1.121-2` be two sections
# rather than one. `tools/mapvalidator/extent.py` holds the same expression, and
# `test_check_map.py` runs both over every citation the maps make.
CITE_SECTION = re.compile(r"§+\s*(\d+\.\d+(?:-\d+)?)")
CITE_GROUP = re.compile(r"\(([A-Za-z0-9]{1,4})\)")
CITE_SUBPART = re.compile(r"\bsubpart\s+([A-Z])\b", re.I)
# The grammar's words for a section's undesignated lead-in, and the last element of a prefix
# that names the lead-in and nothing under it. Never a designator: CITE_GROUP reads one to four
# letters or digits.
LEAD_IN = "introductory text"
# `Example 4` at the end of a citation item, naming one <EXAMPLE> under the paragraph the rest
# of the item names: `§ 1.121-1(b)(4) Example 4`. Written after a comma as well, because that is
# how a regulation's own prose cites one; a bare `Example 4` item extends the item before it
# rather than being read against the section, which is what the comma means here.
CITE_EXAMPLE = re.compile(r"\bExamples?(?:\s+(\d+))?\s*\.?\s*$", re.I)


# --- a rule stated in a table row (rules-factory decision 0035) --------------------------------
# A table cell had no address. The section tree above indexes a section's <P> and <EXAMPLE>
# children and nothing else, so of § 172.101 -- 450,000 characters, 3,687 rows -- it could see
# 6.6% (#261). A citation now reaches a row, and a row is named by a cell that identifies it:
#
#     § 172.101 table 3, row [column 2 = "Acetal"]
#     § 172.101 table 3, row [column 2 = "Acetal"], column 7
#     § 172.101 table 3, row [column 2 = "Ammonia, anhydrous"; column 1 = "I"]
#
# The table is named by its position in the section, which is mechanical and never absent. The
# row is named in the corpus's own column numbering, the numbering its headings print, and
# **exactly one row must match**: two matches is a refusal and never a first hit, answered by a
# discriminating column. `tools/mapper/corpus.py` writes the same form when it enumerates a row
# as a unit, and `tools/tests/mapper/test_mapper_table_rows.py` holds the two to each other.
TABLE_CITATION = re.compile(
    r'^\s*§+\s*(?P<section>\d+\.\d+(?:-\d+)?)\s+table\s+(?P<table>\d+)\s*,\s*row\s*'
    r'\[(?P<key>.*)\](?:\s*,\s*column\s+(?P<column>[A-Za-z0-9]{1,4}))?\s*\.?\s*$')
ROW_KEY_PAIR = re.compile(r'column\s+([A-Za-z0-9]{1,4})\s*=\s*"([^"]*)"')
COLUMN_LABEL = re.compile(r"^\(([A-Za-z0-9]{1,4})\)")
CELL_SEPARATOR = " | "


def table_citation(citation):
    """(section, table position, [(column, value)...], column or None), or None.

    None means the citation is not a table-row citation at all, and the designation grammar
    above reads it. A citation that is one but whose key is malformed returns None too and is
    reported unchecked by `check`, which is what every citation outside a grammar gets: this
    checker never reports ok for a citation it did not read.
    """
    match = TABLE_CITATION.match(str(citation or ""))
    if not match:
        return None
    key = match.group("key")
    pairs = ROW_KEY_PAIR.findall(key)
    if not pairs:
        return None
    # The pairs must be the whole of the key, separated by semicolons: a key this read only
    # part of would resolve on the part it understood.
    if normalise(key) != "; ".join(f'column {c} = "{v}"' for c, v in pairs):
        return None
    return (match.group("section"), int(match.group("table")),
            [(c, normalise(v)) for c, v in pairs], match.group("column"))


def cells_of(row):
    return [normalise("".join(cell.itertext())) for cell in row if cell.tag in ("TD", "TH")]


class Table:
    """One table of a section: the columns its headings print, and its body rows.

    Columns are the corpus's own numbering and not this checker's count, because that is the
    numbering the corpus uses to explain itself -- § 172.101(b)-(l) explains columns 1 to 10 --
    and the one printed in the table's own headings. A heading split into sub-columns names no
    column of its own: where the headings print (8), (8A), (8B) and (8C), the columns are the
    three leaves. A table whose labels do not number its rows' cells one for one is numbered
    positionally, because a guessed alignment between a heading and a cell addresses the wrong
    cell and says nothing about it.
    """

    def __init__(self, section, position, element):
        self.section = section
        self.position = position
        heads = [row for head in element.iter("THEAD") for row in head.iter("TR")]
        head_rows = {id(row) for row in heads}
        self.rows = [cells for cells in
                     (cells_of(row) for row in element.iter("TR") if id(row) not in head_rows)
                     if cells]
        labels = [m.group(1) for m in
                  (COLUMN_LABEL.match(cell) for row in heads for cell in cells_of(row)) if m]
        leaves = [l for l in labels if not any(o != l and o.startswith(l) for o in labels)]
        width = len(self.rows[0]) if self.rows else 0
        self.columns = leaves if (width and len(leaves) == width) \
            else [str(n) for n in range(1, width + 1)]

    def index_of(self, column):
        return self.columns.index(column) if column in self.columns else None

    def matching(self, pairs):
        found = []
        for cells in self.rows:
            if all(self._holds(cells, column, value) for column, value in pairs):
                found.append(cells)
        return found

    def _holds(self, cells, column, value):
        at = self.index_of(column)
        return at is not None and at < len(cells) and cells[at] == value


def table_index(xml_path):
    """Every table in the corpus, as (section number, position) -> Table.

    A table is numbered by its position in the section it is printed in, counted from 1 in
    document order. That is the one thing about a table this corpus always states: a caption is
    optional, and the map's `note` is where a caption belongs.
    """
    root = ET.parse(xml_path).getroot()
    found = {}
    for section in root.iter("DIV8"):
        number = section.get("N")
        for position, element in enumerate(section.iter("TABLE"), start=1):
            found[(number, position)] = Table(number, position, element)
    return found


def row_text(cells):
    """A row's text: its cells in column order, empty cells kept as empty.

    This is the extraction of a row, and 0024's rule -- a quote is one contiguous verbatim span
    of the extraction -- is then applied to it unchanged. It has to be this and not a flattened
    sentence because a blank cell is a rule: 1,112 rows of the corpus that forced this have
    exactly one empty cell and 419 have thirteen, and joined into prose a missing column 1
    symbol and a missing column 5 packing group are the same absence (#261).

    It is normalised like every other passage this checker indexes, so an empty cell reads as
    the two separators around it -- `| |` -- and not as whitespace a quote would have to
    reproduce exactly. The cell is still there to be quoted, which is the point.
    """
    return normalise(CELL_SEPARATOR.join(cells))


def check_table_row(entry, cited, tables):
    """(verdict, message, section) for an entry whose citation names a table row.

    The row -- or the cell, where the citation names a column -- is the container, so there is
    nothing to disambiguate by uniqueness: 0030's rule that a repeated passage is identified by
    the container its citation names is what a row key gives a table, which had none.
    """
    number, position, pairs, column = cited
    table = tables.get((number, position))
    citation = entry.get("locator", {}).get("citation", "")
    if table is None:
        return "bad", (f"cited {citation}, and § {number} prints no table {position}"), None
    unknown = [c for c, _ in pairs if table.index_of(c) is None]
    if unknown:
        return "bad", (f"cited {citation}, and § {number} table {position} prints no column "
                       f"{', '.join(unknown)} (its columns are "
                       f"{', '.join(table.columns) or 'unreadable'})"), None
    hits = table.matching(pairs)
    if len(hits) != 1:
        return "bad", (f"cited {citation}, which names {len(hits)} rows of the table; a row key "
                       f"resolves to exactly one row, and a second match is answered with a "
                       f"discriminating column, never with the first hit"), None
    cells = hits[0]
    where = f"the row"
    text = row_text(cells)
    if column is not None:
        at = table.index_of(column)
        if at is None:
            return "bad", (f"cited {citation}, and § {number} table {position} prints no column "
                           f"{column}"), None
        text = cells[at] if at < len(cells) else ""
        where = f"column {column} of the row"

    evidence = normalise(entry.get("evidence", ""))
    fragments = [f for f in ELLIPSIS.split(evidence) if f]
    if not fragments:
        return "unchecked", "evidence is empty", None
    cursor = 0
    for fragment in fragments:
        at = text.find(fragment, cursor)
        if at == -1:
            got = "; it does appear earlier in the row" if text.find(fragment) != -1 else ""
            return "bad", (f"cited {citation}, and the evidence is not a span of {where}"
                           f"{got}: {fragment[:70]!r} is not in {text[:90]!r}"), None
        cursor = at + len(fragment)
    return "ok", f"{len(fragments)} fragment(s), all inside {where} {citation} names", number


def cited_paths(citation):
    """The set of designation-path prefixes a citation names.

    Handles the grammar the two Part 107 maps actually use:
      `§ 107.35`                whole section
      `§ 107.51 introductory text`  the section's undesignated lead-in, and only that (0020)
      `§ 107.33 introductory text, (a)`  the lead-in and a paragraph, as a list
      `§ 107.51(a)`             one paragraph and everything under it
      `§ 107.29(c)(1)-(2)`      a range at the deepest level
      `§ 107.29(a)(2), (b)`     a list, each item read against the section
      `§ 107.51(c)-(d)`         a range at the first level
      `subpart D`               every section in a subpart
      `§ 1.121-1(b)(4) Example 4`   one worked example under a paragraph, and
      `§ 1.121-1(b)(4), Example 4`  the same, written the way a regulation cites one
    Returns a list of prefixes; a paragraph matches if any prefix is a prefix of its path.
    Returns None for a citation this grammar does not cover -- reported, never assumed ok.
    A paragraph's own introductory text, `§ 107.29(a) introductory text`, is not in the grammar.
    """
    subpart = CITE_SUBPART.search(citation)
    if subpart and not CITE_SECTION.search(citation):
        return [(subpart.group(1).upper(),)]
    section = CITE_SECTION.search(citation)
    if not section:
        return None
    number = section.group(1)
    tail = citation[section.end():]
    if not tail.strip():
        return [(None, number)]

    prefixes = []
    for item in tail.split(","):
        example = CITE_EXAMPLE.search(item)
        if example:
            label = "Example" + (f" {example.group(1)}" if example.group(1) else "")
            item = item[: example.start()]
            if not item.strip():
                # A bare `, Example 4`: it names an example under the paragraph just cited.
                if not prefixes:
                    return None
                prefixes[-1] = prefixes[-1] + (label,)
                continue
            groups = CITE_GROUP.findall(item)
            if not groups or "-" in item or "–" in item:
                return None
            prefixes.append((None, number) + tuple(groups) + (label,))
            continue
        groups = CITE_GROUP.findall(item)
        if " ".join(item.split()).lower() == LEAD_IN:
            prefixes.append((None, number, LEAD_IN))
            continue
        if LEAD_IN in " ".join(item.split()).lower():
            return None
        if not groups:
            if item.strip():
                return None
            continue
        if "-" in item or "–" in item:
            # A range: every designator before the dash is the shared stem, and the two
            # sides of the dash are the endpoints at the deepest level.
            head, _, tail_part = item.partition("-") if "-" in item else item.partition("–")
            stem = CITE_GROUP.findall(head)
            last = CITE_GROUP.findall(tail_part)
            if len(last) != 1 or not stem:
                return None
            lo, hi = stem[-1], last[0]
            for token in span_of(lo, hi):
                prefixes.append((None, number) + tuple(stem[:-1]) + (token,))
        else:
            prefixes.append((None, number) + tuple(groups))
    return prefixes or None


def span_of(lo, hi):
    """The designators from lo to hi inclusive, for a range like (c)-(d) or (1)-(2)."""
    if lo.isdigit() and hi.isdigit():
        return [str(n) for n in range(int(lo), int(hi) + 1)]
    if len(lo) == 1 and len(hi) == 1 and lo.isalpha() and hi.isalpha():
        return [chr(c) for c in range(ord(lo), ord(hi) + 1)]
    return [lo, hi]


def matches(prefix, path):
    """True when `prefix` names `path` or an ancestor of it.

    A prefix whose first element is None is section-anchored: it is compared against the
    path with its subpart dropped, so `§ 107.29(a)` matches whatever subpart 107.29 sits in.

    A prefix ending in LEAD_IN names the section's lead-in and matches only a paragraph whose
    path is the section itself. `paragraphs` gives an undesignated <P> the path of the
    designators open above it, so the only paragraphs with a bare section path are the ones
    before the section's first designated paragraph.
    """
    if prefix[-1] == LEAD_IN:
        return prefix[0] is None and tuple(path[1:]) == tuple(prefix[1:-1])
    if prefix[0] is None:
        prefix, path = prefix[1:], path[1:]
    return len(prefix) <= len(path) and tuple(path[: len(prefix)]) == tuple(prefix)


def occurrences(fragment, corpus):
    at, found = corpus.find(fragment), []
    while at != -1:
        found.append((at, at + len(fragment)))
        at = corpus.find(fragment, at + 1)
    return found


def touched(span, spans):
    start, end = span
    return [path for lo, hi, path in spans if lo < end and start < hi]


def longest_prefix(fragment, corpus):
    """How much of a fragment does appear, for a diagnosis when none of it does."""
    words = fragment.split()
    for length in range(len(words), 0, -1):
        if corpus.find(" ".join(words[:length])) != -1:
            return length / len(words)
    return 0.0


def check(entry, corpus, spans, reached=None, tables=None):
    """(verdict, message) where verdict is 'ok', 'bad' or 'unchecked'.

    On 'ok', the section of every paragraph the evidence touched is added to `reached`.

    A citation naming a table row is resolved against `tables` instead of the section tree: the
    row is a container of its own, and the quote is held to the row's cells in column order. A
    run given no table index reports such a citation unchecked rather than reading it against the
    paragraphs, where a row's words are not.
    """
    citation = entry.get("locator", {}).get("citation", "")
    cited_row = table_citation(citation)
    if cited_row is not None:
        if tables is None:
            return "unchecked", (f"citation {citation!r} names a table row and this run indexed "
                                 f"no table")
        verdict, message, section = check_table_row(entry, cited_row, tables)
        if verdict == "ok" and reached is not None and section is not None:
            reached.add(section)
        return verdict, message
    prefixes = cited_paths(citation)
    if prefixes is None:
        return "unchecked", f"citation {citation!r} is outside the grammar this check reads"

    for prefix in prefixes:
        if prefix[-1] == LEAD_IN and not any(p[1] == prefix[1] and len(p) > 2 for _, _, p in spans):
            return "bad", (f"cited {citation}, and § {prefix[1]} has no designated paragraph, so it "
                           f"has no introductory text; cite the section")

    evidence = normalise(entry.get("evidence", ""))
    fragments = [f for f in ELLIPSIS.split(evidence) if f]
    if not fragments:
        return "unchecked", "evidence is empty"

    seen, cursor, sections = 0, 0, set()
    for fragment in fragments:
        hits = occurrences(fragment, corpus)
        if not hits:
            got = longest_prefix(fragment, corpus)
            return "unchecked", (
                f"evidence fragment not found verbatim "
                f"({got:.0%} of it is in the corpus): {fragment[:70]!r}"
            )
        ordered = [h for h in hits if h[0] >= cursor]
        if not ordered:
            return "bad", f"evidence fragments are out of corpus order: {fragment[:70]!r}"
        seen += len(hits)
        for hit in hits:
            for path in touched(hit, spans):
                sections.add(path[1])
                if not any(matches(p, path) for p in prefixes):
                    where = "/".join(x for x in path[1:] if x)
                    return "bad", (
                        f"cited {citation}, evidence also sits in {where} "
                        f"({len(hits)} occurrence(s) of this fragment)"
                    )
        cursor = ordered[0][1]
    if reached is not None:
        reached.update(sections)
    return "ok", f"{len(fragments)} fragment(s), {seen} occurrence(s), all inside {citation}"


def bounds_of(entry):
    """`(label, quoting entry)` for each authored example in `ambiguity.bounds` (0031).

    A bound quotes the corpus and cites it, exactly as `evidence` and `locator` do, so it is
    checked by the same `check` above rather than by a second implementation of finding a quote:
    the pair is handed over as an entry of its own. Its sections are deliberately **not** added to
    `reached`: coverage asks which sections an entry's own evidence reached, and an example quoted
    to bound someone else's term is not a verdict on the paragraph it sits in.
    """
    bounds = (entry.get("ambiguity") or {}).get("bounds") if isinstance(entry.get("ambiguity"), dict) else None
    if not isinstance(bounds, dict):
        return []
    out = []
    for index, example in enumerate(bounds.get("examples") or [], start=1):
        if not isinstance(example, dict):
            continue
        out.append((f"{entry.get('id', '?')}: bounds.examples[{index}]",
                    {"locator": example.get("locator") or {}, "evidence": example.get("text", "")}))
    return out


EXTENT_SECTION = re.compile(r"^§\s*(\d+\.\d+(?:-\d+)?)$")


def coverage(document, reached):
    """(problems, summary): every section of the declared extent is reached by a verified quote.

    The section-designation counterpart of `tools/check-locators.py`'s `coverage` (0009, 0020).
    The extent is `{"unit": "section-designation", "sections": ["§ 107.25", ...]}`. A section
    counts as reached only through an entry whose citation this tool verified, so a citation
    naming a section is not a quote sitting in it. A map declaring no extent, or one in another
    unit, is a problem: what it claims to have read is unstated. The shape of the list itself is
    `check-map.py --only extent`.
    """
    extent = document.get("extent")
    if not isinstance(extent, dict):
        return ["  X  the map declares no `extent`, so what it claims to have read is unstated and "
                "'no entry cites this section' cannot be a fact (0009)"], None
    if extent.get("unit") != "section-designation":
        return [f"  X  extent.unit is {extent.get('unit')!r}; this checker reads the section tree "
                f"and can prove nothing about another unit"], None
    sections = extent.get("sections")
    matched = [EXTENT_SECTION.match(s) for s in sections if isinstance(s, str)] \
        if isinstance(sections, list) else []
    numbers = [m.group(1) for m in matched if m]
    if not numbers:
        return ["  X  extent names no section designation this checker can read"], None
    missing = [n for n in numbers if n not in reached]
    problems = [f"  X  § {n}: inside the declared extent and reached by no entry's verified "
                f"evidence" for n in missing]
    return problems, f"all {len(numbers)} sections of the declared extent are reached"


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[-2], file=sys.stderr)
        return 2
    document = json.load(open(argv[1], encoding="utf-8"))
    entries = document["entries"]
    corpus, spans, refused = corpus_index(argv[2])
    tables = table_index(argv[2])
    for text, token in refused:
        print(f"  !  paragraph designator ({token}) is ambiguous; not indexed: {text}...")

    bad = unchecked = bounds = bad_bounds = 0
    reached = set()
    for entry in entries:
        verdict, message = check(entry, corpus, spans, reached, tables)
        if verdict == "bad":
            bad += 1
            print(f"  X  {entry['id']}: {message}")
        elif verdict != "ok":
            unchecked += 1
            print(f"  ?  {entry['id']}: {message}")
        for name, quoting in bounds_of(entry):
            bounds += 1
            verdict, message = check(quoting, corpus, spans, None, tables)
            if verdict != "ok":
                bad_bounds += 1
                print(f"  {'X' if verdict == 'bad' else '?'}  {name}: {message}")

    total = len(entries)
    checked = total - unchecked
    uncovered, covered = coverage(document, reached)
    for line in uncovered:
        print(line)
    if refused:
        print(f"\n{len(refused)} paragraph(s) could not be placed in the section tree")
        return 1
    if bad_bounds:
        print(f"\n{bad_bounds} of {bounds} authored example(s) in `ambiguity.bounds` do not quote "
              f"the corpus at the citation they name. A bound is checked against an owner's ruling "
              f"(0031), so a bound whose words are not there would refuse or admit a ruling on a "
              f"quotation of nothing")
        return 1
    if bad:
        print(f"\n{bad} of {total} entries cite a passage their evidence is not in "
              f"({unchecked} unchecked)")
        return 1
    if checked == 0:
        print("\nskip: no entry's evidence appears verbatim in the corpus, so no citation "
              "was checked. This is not a pass.", file=sys.stderr)
        return 1
    if checked < total:
        print(f"\n{checked} of {total} citations verified; {unchecked} could not be checked")
        return 1
    if uncovered:
        print(f"\nlocators ok (all {total} checked), but coverage fails: "
              f"{len(uncovered)} problem(s) with the declared extent")
        return 1
    print(f"locators ok (all {total} checked against the section tree"
          + (f", and {bounds} authored example(s) bounding a term" if bounds else "")
          + f"); coverage ok ({covered})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
