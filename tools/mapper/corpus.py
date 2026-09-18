"""Enumerating a corpus's units inside a declared extent: the adapter interface.

Three locator checkers already resolve a citation to its passage -- page markers over a
Gutenberg text (`tools/check-locators.py`), containment in an eCFR section tree
(`examples/faa-part-107/check-locators-section.py`), page markers over PDF-extracted text
(`examples/srd-52-combat/check-locators-pdf-text.py`). Each answers *where is the passage this
citation names*. None can answer the other half: **what is in the extent that no citation
named**, which is what an inventory measures (#255). A map's `extent` claims coverage, and
until something enumerates the units inside it, nothing evidences the claim.

## The interface, and why it is this small

An adapter does one thing: **cut a corpus into the units the extent selects**, in reading
order, each with a stable key and its text. Everything after that -- finding which units an
entry's quoted evidence reaches, reading declared rejections, counting what is left -- is the
same work in every grammar and lives in `inventory.py`, over `Unit`s.

That split is deliberate, and it is why no citation grammar appears in this file. Marking a
unit *reached* could have been done by parsing each entry's citation and comparing it against
the unit's designation, which is what the section checker does; it would have put a second
citation parser per grammar in here and made the inventory as grammar-specific as the
checkers. It is instead done by finding the entry's **quoted evidence** in the units' own text.
A quote is the same kind of object in every corpus, so the measurement is one implementation,
and it is the stricter of the two readings: a citation naming a section is not a quote sitting
in it.

What an adapter therefore has to know is only its corpus's shape: where the units are, and
which of them an extent selects. `units()` is also what a sweep walks
([#250](https://github.com/brandonifco/rules-factory/issues/250)), which is the other reason it
returns the text rather than a locator -- a sweep asks what a unit says.

## Adding the fourth grammar

Subclass `Adapter`, implement `units(extent)`, and register the manifest `adapter` name in
`ADAPTERS`. A manifest naming an adapter with no implementation is **refused**, never skipped:
a corpus nothing can enumerate must not report an inventory of zero unaccounted units.

## What an enumeration is not

It is not a claim that each unit states a rule, nor that the cut is the one a human would make.
A page-marked plain text has no hierarchy at all -- pdftotext linearises columns, Gutenberg
wraps lines -- so the finest honest cut is the blank-line-separated block, and a heading is a
block like any other. The count is a denominator the walk is measured against, and a
denominator that is too fine reports more unaccounted units, not fewer: it errs towards
reporting work as unevidenced, which is the direction this repository wants to be wrong in.
"""
import os
import re
import xml.etree.ElementTree as ET

from mapper.protocol import Refused

# What a unit can be. A subset of `protocol.UNITS` -- the kinds an enumerator can actually tell
# apart from the corpus's own structure. `sentence`, for one, is not in it: a corpus that states
# rules in sentences is still cut into paragraphs here, because splitting prose into sentences is
# a judgement, and a wrong split would invent units nothing could ever reach.
KINDS = ("section", "paragraph", "heading", "worked-example", "table", "table-row")


def normalise(text):
    """Collapse whitespace, so a quote that wraps lines matches the corpus.

    Every grammar here needs it, for the same reason: a quotation is of the words, and where the
    extraction broke the line is not one of the words.
    """
    return re.sub(r"\s+", " ", text).strip()


class Unit:
    """One thing a mapper reads one at a time, and one thing a walk can fail to reach.

    `key` identifies it inside its corpus and is what a rejection names, so it has to be stable
    across runs and legible in a report: `p. 177 block 4`, `§ 107.29(a)(2)`.
    """

    def __init__(self, key, kind, text):
        if kind not in KINDS:
            raise Refused(f"unit kind {kind!r} is outside the closed set: " + ", ".join(KINDS))
        self.key = key
        self.kind = kind
        self.text = text

    def __repr__(self):
        return f"Unit({self.key!r}, {self.kind!r}, {len(self.text)} chars)"


class Adapter:
    """A corpus grammar, from the inventory's side: what the units are and which ones an
    extent selects.

    Constructed from the bytes of the committed corpus, because that is what a manifest pins
    (`committedPath`) and what every checker already reads.
    """

    #: the `adapter` name in a corpus manifest that this class serves
    name = None
    #: the `extent.unit` values it can read; any other extent is refused, not passed
    extent_units = ()

    def __init__(self, path):
        self.path = path

    def units(self, extent):
        """Every unit the extent selects, in the corpus's reading order.

        Raises `Refused` when the extent is not one this grammar can read. Returning an empty
        list is allowed only when the extent genuinely selects nothing; the caller fails the run
        on it either way, because an inventory of no units accounts for nothing.
        """
        raise NotImplementedError

    def _refuse_unit(self, extent):
        unit = extent.get("unit") if isinstance(extent, dict) else None
        raise Refused(f"extent.unit is {unit!r}; the {self.name!r} adapter enumerates "
                      f"{' or '.join(self.extent_units)} extents and can enumerate nothing "
                      f"in another")


class PageMarkedText(Adapter):
    """A flat text with `{N}` page markers: the unit is the blank-line-separated block.

    Both text corpora here are page-marked, and their markers are written differently -- Project
    Gutenberg puts `{271}` inline where the page turns, `extract.py` puts `{13}` on a line of its
    own before each page -- so the marker is the only thing the two differ in, and the subclass
    below changes it and nothing else.

    A block is assigned the page its **first character** sits on, so a paragraph that runs across
    a page turn is one unit and not two. The consequence is stated rather than hidden: a block
    beginning on the page before the extent's first page is outside the extent even though part
    of it is printed inside, which under-counts by at most one block per extent.
    """

    name = "plain-text"
    extent_units = ("page",)
    MARKER = re.compile(r"\{(\d+)\}")
    BLOCK_BREAK = re.compile(r"\n[ \t]*\n")

    def __init__(self, path):
        Adapter.__init__(self, path)
        with open(path, encoding="utf-8") as handle:
            self.text = handle.read()
        self.starts = [(m.start(), int(m.group(1))) for m in self.MARKER.finditer(self.text)]
        if not self.starts:
            raise Refused(f"{os.path.basename(path)} has no {{N}} page markers, so it is not the "
                          f"page-marked extraction this adapter reads")

    def _page_at(self, offset):
        page = None
        for start, number in self.starts:
            if start > offset:
                break
            page = number
        return page

    def _blocks(self):
        """(offset, text) for every blank-line-separated block, markers removed from the text."""
        found, cursor = [], 0
        for piece in self.BLOCK_BREAK.split(self.text):
            offset = self.text.index(piece, cursor) if piece else cursor
            cursor = offset + len(piece)
            text = normalise(self.MARKER.sub(" ", piece))
            if text:
                found.append((offset, text))
        return found

    def units(self, extent):
        if not isinstance(extent, dict) or extent.get("unit") != "page":
            self._refuse_unit(extent)
        first, last = extent.get("from"), extent.get("to")
        if not isinstance(first, int) or not isinstance(last, int) or last < first:
            raise Refused(f"extent names the range {first!r}..{last!r}, which is not a page range")
        found, seen = [], {}
        for offset, text in self._blocks():
            page = self._page_at(offset)
            if page is None or not first <= page <= last:
                continue
            seen[page] = seen.get(page, 0) + 1
            found.append(Unit(f"p. {page} block {seen[page]}", "paragraph", text))
        return self._end_before(found, extent, last)

    @staticmethod
    def _end_before(found, extent, last):
        """A page extent may end before a heading on its last page (0024).

        The heading is a block of its own -- that is what makes it findable in a text with no
        hierarchy -- and every block from it to the end of the page is outside the extent. A
        heading this does not find is refused: an extent that ends at a heading nobody can locate
        would otherwise enumerate the whole of the last page and call the surplus unaccounted.
        """
        heading = extent.get("endsBefore")
        if heading is None:
            return found
        prefix = f"p. {last} block "
        cut = [position for position, unit in enumerate(found)
               if unit.key.startswith(prefix) and unit.text == normalise(heading)]
        if len(cut) != 1:
            raise Refused(f"extent ends before {heading!r}, which is {len(cut)} block(s) on "
                          f"p. {last}; an extent ending at a heading nothing can find would "
                          f"enumerate the whole page and call the surplus unaccounted")
        return found[:cut[0]]


class PageMarkedPdfText(PageMarkedText):
    """`extract.py`'s output: the same grammar, with the marker on a line of its own.

    Written as a subclass rather than a copy because that is the whole of the difference, and a
    copy would be a second place to fix the block rule.
    """

    name = "pdftotext-page-marked"
    MARKER = re.compile(r"^\{(\d+)\}$", re.M)


# --- table geometry, and the row key a citation names (0035) -----------------------------------
# A rule stated in a row of a table is cited by a cell that identifies the row, in the corpus's
# own column numbering, and never by the row's position: a table this corpus amends constantly
# moves its rows, and an ordinal that silently re-points at a different material is worse than a
# key that stops resolving. The citation the key is written into is
#
#     § 172.101 table 3, row [column 2 = "Acetal"]
#
# and `examples/faa-part-107/check-locators-section.py` holds a quote to the row it names. That
# checker parses the form and this one writes it; the two expressions are held to each other by
# `tools/tests/mapper/test_mapper_table_rows.py`, the way CITE_SECTION already is.

#: A heading's own label for a column, read wherever the heading prints it: this corpus writes a
#: parent as a prefix, `(8)Packaging(§ 173.***)`, and its children as suffixes, `Exceptions(8A)`.
#: `(§ 173.***)` is not one of these, which is why the token is held to four characters of
#: letters and digits.
COLUMN_LABEL = re.compile(r"\(([A-Za-z0-9]{1,4})\)")
#: A cell that spans rows or columns. In a **heading** that is how a two-level heading is
#: written, and it is expanded into a grid; in a body row it means the markup no longer says
#: which column a cell sits in, and the table is refused rather than addressed (0035).
SPAN_ATTRIBUTES = {"COLSPAN": ("COLSPAN", "colspan"), "ROWSPAN": ("ROWSPAN", "rowspan")}
#: The separator between a row's cells in the extraction of a row. Empty cells are kept as
#: empty, which is what makes a blank cell quotable: 1,112 rows of the corpus that forced this
#: have exactly one empty cell, and flattened into prose a missing symbol and a missing packing
#: group are the same absence (#261).
CELL_SEPARATOR = " | "


def sub_column_of(label, other):
    """True when `other` is a sub-column of `label`: `10A` is one of `10`, `10` is not one of `1`.

    A heading split into sub-columns names no column of its own, and what "split" means is the
    parent's label plus letters -- not a string prefix. Read as a prefix, column `1` is swallowed
    by `10A` and the Hazardous Materials Table loses its own numbering: 13 leaves against a width
    of 14, a silent fall back to positional numbering, and `column 9` addressing column 8B.
    """
    return other != label and other.startswith(label) and other[len(label):].isalpha()


def row_text(cells):
    """A row's text: its cells in column order, empty cells kept as empty (0035).

    Normalised like every other unit's text, so an empty cell reads as the two separators
    around it -- `| |` -- rather than as whitespace a quote would have to reproduce exactly.
    The cell is still there to be quoted, which is the whole point: flattened into prose, a
    missing column 1 symbol and a missing column 5 packing group are the same absence (#261).
    """
    return normalise(CELL_SEPARATOR.join(cells))


def quotable(value):
    """True when a value can be written into a row key and read back out of it.

    A key delimits its values with `"` and defines no escape, so a cell holding one names
    nothing. Such a cell is passed over when a key is chosen, rather than written into a
    citation nothing can parse.
    """
    return '"' not in value


def row_key_text(pairs):
    """`column 2 = "Acetal"; column 1 = "I"` for [(column, value), ...]."""
    return "; ".join(f'column {column} = "{value}"' for column, value in pairs)


def row_key_pairs(key):
    """[(column, value), ...] for a declared row key, or None where it is not one.

    A key is one `{"column": 2, "is": "Acetal"}` object, or a list of them read as a
    conjunction: the second column is how an ambiguous key is answered.
    """
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
        pairs.append((str(column), normalise(value)))
    return pairs


def row_citation(number, position, pairs):
    """The citation naming one row: `§ 172.101 table 3, row [column 2 = "Acetal"]`."""
    return f"§ {number} table {position}, row [{row_key_text(pairs)}]"


def addressable_row(spans):
    """Whether a body row's cells can be told apart by column.

    A row whose cells each occupy one cell is addressable, and so is a row that is **one cell
    across the whole width** -- the footnote and sub-heading rows every printed regulation ends a
    table with; `§ 172.101`'s reportable-quantity table carries four of them, and refusing a
    1,356-row table because of them would be refusing the table for its footnotes. What is not
    addressable is a row that spans *part* of its width: a `COLSPAN` in the middle displaces every
    cell after it, and which column those cells are in is then not in the markup.
    """
    if all(across == 1 and down == 1 for across, down in spans):
        return True
    return len(spans) == 1 and spans[0][1] == 1


def span_of_cell(cell, which):
    """How many columns or rows a cell covers: 1 where it says nothing, and 1 where what it says
    is not a count. A span this cannot read is left at 1, and the leaf count then fails to match
    the body's width, which is a refusal rather than a wrong address."""
    for attribute in SPAN_ATTRIBUTES[which]:
        value = cell.get(attribute)
        if value is not None:
            return int(value) if value.isdigit() and int(value) > 0 else 1
    return 1


class Table:
    """One table of a section: the columns its headings print, its rows, and where it sits.

    `columns` is the corpus's own numbering -- the labels its headings print -- because that is
    the numbering the corpus uses to explain itself (§ 172.101(b)-(l)) and the one a reader sees.

    **A two-level heading is read, not refused.** The corpus that forced 0035 prints one: a first
    heading row of ten cells, seven of them `rowspan="2"` and three of them `colspan="3"`, `"2"`
    and `"2"`, over a second row of seven. That is 7 + 3 + 2 + 2 = 14 leaves over 14 body cells,
    and the alignment is stated outright by the markup. The heading rows are expanded into a grid
    the way any table is laid out -- `colspan` widens a cell, `rowspan` carries it down -- and a
    column's label is read from the **bottom-most heading cell covering it**.

    A label is read wherever the cell prints it, because this corpus prints the parents as
    prefixes (`(8)Packaging(§ 173.***)`) and the children as suffixes (`Exceptions(8A)`). A
    heading cell that names two columns, or names none while its neighbours name theirs, is
    refused: half a numbering is not one.

    Three outcomes, and the middle one is the point:

      **printed**     the leaf labels number the body's cells one for one, and they are the
                      columns. A label split into sub-columns names no column of its own, so
                      where the headings print `(8)`, `(8A)`, `(8B)` and `(8C)` in one row, the
                      columns are the three leaves.
      **positional**  the table prints no numbering of its own, or prints one label twice; the
                      columns are `1`..`n` by position, which is all the markup then says.
      **refused**     a cell of a **body** row spans, or the leaf labels do not number the body's
                      cells. `unresolved` then says so and the table addresses nothing: a guessed
                      alignment between a heading and a cell names the wrong cell and says
                      nothing about having done so.

    Rows are the rows of *this* table: a nested table's rows belong to the table that encloses
    them, not to this one. Heading rows are rows like any other, because the column semantics of
    a regulation live in its headings and this corpus prints them once for 3,687 rows.
    """

    def __init__(self, number, position, element):
        self.number = number
        self.position = position
        self.unresolved = None
        self.numbering = "printed"
        self.numbering_note = None
        parents = {child: parent for parent in element.iter() for child in parent}

        def nearest_table(node):
            node = parents.get(node)
            while node is not None and node.tag != "TABLE":
                node = parents.get(node)
            return node

        def in_head(node):
            while node is not None and node is not element:
                if node.tag == "THEAD":
                    return True
                node = parents.get(node)
            return False

        self.rows, self.heads, self.addressable, self._headings = [], [], [], []
        carried = False
        for row in element.iter("TR"):
            if nearest_table(row) is not element:
                continue
            cells = [cell for cell in row if cell.tag in ("TD", "TH")]
            text = [normalise("".join(cell.itertext())) for cell in cells]
            if not text:
                continue
            head = in_head(row)
            spans = [(span_of_cell(cell, "COLSPAN"), span_of_cell(cell, "ROWSPAN"))
                     for cell in cells]
            if head:
                self._headings.append(list(zip(text, spans)))
            else:
                carried = carried or any(down != 1 for _, down in spans)
            self.heads.append(head)
            self.addressable.append(head or addressable_row(spans))
            self.rows.append(text)
        self.columns = self._columns(carried)

    def _leaf_headings(self):
        """The heading cell that covers each column, bottom-most first covered wins.

        The ordinary table layout: a cell is placed in the first column free on its row, occupies
        `colspan` columns, and is carried down `rowspan` rows. The bottom-most cell covering a
        column is the one that names it -- `Exceptions(8A)` and not the `(8)Packaging` above it.
        """
        covered = {}
        for depth, cells in enumerate(self._headings):
            at = 0
            for text, (across, down) in cells:
                while (depth, at) in covered:
                    at += 1
                for column in range(at, at + across):
                    for row in range(depth, depth + down):
                        covered[(row, column)] = text
                at += across
        if not covered:
            return []
        width = max(column for _, column in covered) + 1
        leaves = []
        for column in range(width):
            depths = [row for row, other in covered if other == column]
            leaves.append(covered[(max(depths), column)] if depths else None)
        return leaves

    def _columns(self, carried):
        body = [cells for cells, head, fit in zip(self.rows, self.heads, self.addressable)
                if not head and fit and len(cells) > 1]
        width = len(body[0]) if body else 0
        positional = [str(n) for n in range(1, width + 1)]
        if carried:
            self.unresolved = ("a cell of one of its rows spans rows, carrying it into the row "
                               "below, so which column a later cell sits in is not in the markup")
            return []
        if not width:
            self.unresolved = ("no row of it has cells that can be told apart by column: every "
                               "row spans part of its width, or the table has no body row")
            return []
        leaves = self._leaf_headings()
        printed = [COLUMN_LABEL.findall(text or "") for text in leaves]
        crowded = [text for text, found in zip(leaves, printed) if len(found) > 1]
        labelled = [found[0] for found in printed if len(found) == 1]
        unlabelled = [found for found in printed if not found]
        # A heading split into sub-columns names no column of its own. The grid above already
        # drops a parent that spans its children; this drops one printed beside them in a single
        # heading row, which is the same table written flat. It happens after the counting below,
        # because a parent that names no column of its own is not a heading that prints no number.
        labels = [l for l in labelled if not any(sub_column_of(l, o) for o in labelled)]

        # Every way the *printed* numbering can fail to be one falls back to position, which is
        # what the markup still says. None of them is a refusal: which cell is which column is
        # determined either way, and a table that prints an unusable numbering is not a table
        # nobody can address. Each reason is recorded, and every message that names the columns
        # names the numbering and why.
        if crowded:
            self.numbering = "positional"
            self.numbering_note = (f"one of its headings names more than one column "
                                   f"({crowded[0][:40]!r})")
        elif not labelled:
            self.numbering = "positional"
            self.numbering_note = "it prints no column numbers of its own"
        elif unlabelled:
            self.numbering = "positional"
            self.numbering_note = "some of its headings print a column number and some do not"
        elif labels[0] != "1":
            # A corpus that numbers its columns numbers them from 1. A heading whose parenthesised
            # token is a footnote marker rather than a column number reads exactly like a label,
            # and this is the one cheap thing that tells the two apart.
            self.numbering = "positional"
            self.numbering_note = f"its first numbered heading is ({labels[0]}) and not (1)"
        elif len(set(labels)) != len(labels):
            self.numbering = "positional"
            self.numbering_note = "it prints one column number twice"
        if self.numbering == "positional":
            return positional

        if len(labels) != width:
            self.unresolved = (f"its headings number {len(labels)} column(s) and its rows hold "
                               f"{width} cell(s), so no heading can be matched to a cell")
            return []
        return labels

    def index_of(self, column):
        """Which cell a column names, or None where this table prints no such column."""
        column = str(column)
        return self.columns.index(column) if column in self.columns else None

    def matching(self, pairs):
        """Every row whose cells hold all of `pairs`, as (position, cells).

        A row that spans part of its width is passed over: a key names a column, and that row has
        no columns to name. It is still a row -- its text is what it is -- and a citation reaching
        it fails rather than reaching a neighbour.
        """
        found = []
        for position, cells in enumerate(self.rows):
            if not self.addressable[position]:
                continue
            if all(self._holds(cells, column, value) for column, value in pairs):
                found.append((position, cells))
        return found

    def _holds(self, cells, column, value):
        at = self.index_of(column)
        return at is not None and at < len(cells) and cells[at] == normalise(str(value))

    def key_for(self, position):
        """A key of `column = value` pairs naming row `position` and no other row, or None.

        The narrowest cell first, then the cell that narrows what is left the most, until one
        row is named: one column where one will do, and as many as it takes where one will not.
        An empty cell is a legitimate value -- a blank column 1 symbol is a fact about the row,
        which is the whole reason the extraction keeps the columns -- but it is taken only where
        it narrows further than a cell that says something, because a row identified by what is
        absent from it is the weaker name of the two. A cell holding a `"` is passed over
        altogether: no key written from it could be read back.

        None means no combination of this table's cells names the row: another row holds the
        same value in every nameable column. That is the refusal 0035 makes for an ambiguous
        citation, made here, where the citation is written.
        """
        if not self.addressable[position]:
            return None
        cells = self.rows[position]
        candidates = [(column, cells[at]) for at, column in enumerate(self.columns)
                      if at < len(cells) and quotable(cells[at])]
        chosen, matched = [], self.matching([])
        while len(matched) > 1 or not chosen:
            rest = [pair for pair in candidates if pair not in chosen]
            if not rest:
                return None
            best = min(rest, key=lambda pair: (len(self.matching(chosen + [pair])),
                                               pair[1] == "", candidates.index(pair)))
            narrowed = self.matching(chosen + [best])
            if chosen and len(narrowed) >= len(matched):
                return None
            chosen, matched = chosen + [best], narrowed
        return chosen


class EcfrXml(Adapter):
    """The eCFR versioner's XML: the unit is a paragraph, an example, or a section's heading.

    The section tree is the corpus's own hierarchy, so unlike a flat text this grammar can say
    what kind each unit is. It does **not** rebuild the CFR's designator tree -- `(a)`, `(1)`,
    `(i)` nest by form, and resolving the forms that are ambiguous is the section locator
    checker's work, needed there because a *citation* names a designation path. An inventory
    needs only to enumerate and to key, so a paragraph is keyed by its designator as printed and
    its position in the section: `§ 107.29 ¶4 (a)`. Nothing here can be wrong about the nesting,
    because nothing here asserts any.

    **A table's rows are units too** (0035), where the extent says which of them it takes. A row
    is keyed by the citation that names it -- `§ 172.101 table 3, row [column 2 = "Acetal"]` --
    and its text is its cells in column order, empty cells kept as empty. The rows of a section's
    table are enumerated after that section's paragraphs rather than in the place the table is
    printed: this grammar walks a section's direct children, a table sits below them, and a
    reading order this cannot see is not one it should assert.
    """

    name = "ecfr-xml"
    extent_units = ("section-designation",)
    SECTION = re.compile(r"§+\s*(\d+\.\d+(?:-\d+)?)")
    DESIGNATOR = re.compile(r"^\(([A-Za-z0-9]{1,4})\)")

    def __init__(self, path):
        Adapter.__init__(self, path)
        try:
            self.root = ET.parse(path).getroot()
        except ET.ParseError as error:
            raise Refused(f"cannot parse {os.path.basename(path)} as eCFR XML: {error}")

    def _sections(self):
        """The section tree by designation, refusing a designation the corpus prints twice.

        Keeping the last of two `DIV8`s with the same `N` is what a dictionary does by itself,
        and it is silent: everything in the first section -- its paragraphs, and every table the
        extent then has to account for -- disappears, and both the accounting and the coverage
        check pass over a section nobody read. An extent that names such a designation names two
        passages, and this refuses rather than choosing one.
        """
        found = {}
        for section in self.root.iter("DIV8"):
            number = section.get("N")
            if not number:
                continue
            if number in found:
                raise Refused(f"the corpus prints § {number} twice; a designation that names two "
                              f"passages names neither, and an extent over it would enumerate "
                              f"one of them and account for the other's tables by accident")
            found[number] = section
        return found

    def units(self, extent):
        if not isinstance(extent, dict) or extent.get("unit") != "section-designation":
            self._refuse_unit(extent)
        listed = extent.get("sections")
        if not isinstance(listed, list) or not listed:
            raise Refused("extent names no section, so it selects nothing to enumerate")
        wanted = []
        for item in listed:
            match = self.SECTION.search(item) if isinstance(item, str) else None
            if not match:
                raise Refused(f"extent names {item!r}, which is not a section designation this "
                              f"adapter can find in the section tree")
            wanted.append(match.group(1))
        sections = self._sections()
        missing = [number for number in wanted if number not in sections]
        if missing:
            raise Refused(f"the extent names {', '.join('§ ' + n for n in missing)}, which the "
                          f"corpus does not contain; an extent over a section that is not there "
                          f"claims coverage of nothing")
        slices = self._slices(extent, wanted, sections)
        found = []
        for number in wanted:
            found += self._section_units(number, sections[number])
            found += self._table_units(number, sections[number], slices)
        return found

    def _tables(self, number, section):
        """Every table the section prints, in document order, numbered from 1."""
        return [Table(number, position, element)
                for position, element in enumerate(section.iter("TABLE"), start=1)]

    def _slices(self, extent, wanted, sections):
        """`extent.tables` as (section, table position) -> the slice declared for it (0035).

        Every table of every cited section is either sliced, taken whole or excluded with a
        reason, and `units` refuses one the extent passes over in silence. That is 0020's own
        principle -- a map may not quietly shrink its extent to match what it happened to read --
        applied to the unit a table cell now has.
        """
        declared = extent.get("tables")
        if declared is None:
            return {}
        if not isinstance(declared, list) or not declared:
            raise Refused("extent.tables is present and names no table; an extent that slices "
                          "nothing declares no `tables`")
        slices = {}
        for position, item in enumerate(declared):
            where = f"extent.tables[{position}]"
            if not isinstance(item, dict):
                raise Refused(f"{where} is not an object")
            number = item.get("section")
            match = self.SECTION.search(number) if isinstance(number, str) else None
            if not match or match.group(1) not in wanted:
                raise Refused(f"{where} names section {number!r}, which the extent does not cite; "
                              f"a slice of a table outside the extent takes nothing")
            number = match.group(1)
            table = item.get("table")
            if not isinstance(table, int) or isinstance(table, bool) or table < 1:
                raise Refused(f"{where} names table {table!r}; a table is named by its position "
                              f"in the section, counted from 1")
            if (number, table) in slices:
                raise Refused(f"{where}: § {number} table {table} is declared twice")
            printed = len(self._tables(number, sections[number]))
            if table > printed:
                raise Refused(f"{where}: § {number} prints {printed} table(s) and this names "
                              f"table {table}")
            if ("rows" in item) == ("excluded" in item):
                raise Refused(f"{where}: a table is sliced (`rows`), taken whole (`rows: \"all\"`) "
                              f"or excluded with a reason (`excluded`), and this declares "
                              + ("both" if "rows" in item else "neither"))
            slices[(number, table)] = item
        return slices

    def _table_units(self, number, section, slices):
        found = []
        for table in self._tables(number, section):
            declared = slices.get((number, table.position))
            if declared is None:
                raise Refused(f"§ {number} table {table.position} is inside the declared extent "
                              f"and extent.tables neither slices it, takes it whole nor excludes "
                              f"it with a reason; a table left out is an extent shrunk to what "
                              f"the walk happened to read (0035)")
            if "excluded" in declared:
                continue
            if table.unresolved:
                raise Refused(f"§ {number} table {table.position} cannot be addressed: "
                              f"{table.unresolved}. A table whose geometry the markup does not "
                              f"carry is refused, not guessed at; exclude it with a reason, or "
                              f"read it from the rendered page (0004)")
            found += self._rows_of(table, declared.get("rows"))
        return found

    def _rows_of(self, table, rows):
        where = f"§ {table.number} table {table.position}"
        if rows == "all":
            taken = list(range(len(table.rows)))
            keys = []
            for position in taken:
                key = table.key_for(position)
                if key is None:
                    raise Refused(f"{where} holds a row no combination of its cells names: "
                                  f"another row holds the same value in every column that can be "
                                  f"written into a key, so the citation that would reach it names "
                                  f"two rows. The row is {row_text(table.rows[position])[:70]!r}")
                keys.append(key)
            return [Unit(row_citation(table.number, table.position, key), "table-row",
                         row_text(table.rows[position]))
                    for position, key in zip(taken, keys)]
        if not isinstance(rows, list) or not rows:
            raise Refused(f"{where}: `rows` is a non-empty list of row keys, or \"all\"; "
                          f"{rows!r} is neither")
        found = []
        for position, key in enumerate(rows):
            pairs = row_key_pairs(key)
            if pairs is None:
                raise Refused(f"{where}: rows[{position}] is not a row key -- one or more "
                              f"{{\"column\": 2, \"is\": \"Acetal\"}} objects")
            hits = table.matching(pairs)
            if len(hits) != 1:
                raise Refused(f"{where}, row [{row_key_text(pairs)}] names {len(hits)} rows of "
                              f"the table; a row key resolves to exactly one row, and a second "
                              f"match is answered with a discriminating column, never with the "
                              f"first hit")
            found.append(Unit(row_citation(table.number, table.position, pairs), "table-row",
                              row_text(hits[0][1])))
        return found

    def _section_units(self, number, section):
        found, position = [], 0
        head = section.find("HEAD")
        if head is not None and normalise("".join(head.itertext())):
            found.append(Unit(f"§ {number} heading", "heading",
                              normalise("".join(head.itertext()))))
        for child in section:
            text = normalise("".join(child.itertext()))
            if not text:
                continue
            if child.tag == "P":
                position += 1
                designator = self.DESIGNATOR.match(text)
                label = f" ({designator.group(1)})" if designator else ""
                found.append(Unit(f"§ {number} ¶{position}{label}", "paragraph", text))
            elif child.tag == "EXAMPLE":
                position += 1
                found.append(Unit(f"§ {number} ¶{position} example", "worked-example", text))
        return found


ADAPTERS = {cls.name: cls for cls in (PageMarkedText, PageMarkedPdfText, EcfrXml)}


def open_corpus(manifest, source_id, manifest_dir):
    """The adapter for the corpus a map declares, over the bytes the manifest pins.

    The manifest is the one place that already says which adapter read the corpus and where the
    committed copy is, so the inventory reads it from there rather than being told on the command
    line: a map cannot be inventoried against a corpus its manifest does not name.
    """
    corpora = manifest.get("corpora") if isinstance(manifest, dict) else None
    declared = [c for c in corpora or [] if isinstance(c, dict) and c.get("sourceId") == source_id]
    if not declared:
        raise Refused(f"the manifest declares no corpus {source_id!r}, which is the corpus this "
                      f"map says it maps")
    corpus = declared[0]
    name = corpus.get("adapter")
    if name not in ADAPTERS:
        raise Refused(f"corpus {source_id!r} was read by the {name!r} adapter, which enumerates "
                      f"nothing here. A corpus nothing can enumerate is refused rather than "
                      f"reported as fully accounted for: add an Adapter in mapper/corpus.py")
    committed = corpus.get("committedPath")
    if not isinstance(committed, str) or not committed:
        raise Refused(f"corpus {source_id!r} pins no `committedPath`, so there are no bytes to "
                      f"enumerate")
    path = os.path.normpath(os.path.join(manifest_dir, committed))
    if not os.path.exists(path):
        raise Refused(f"the corpus {source_id!r} pins {committed!r}, which is not at {path}")
    return ADAPTERS[name](path)
