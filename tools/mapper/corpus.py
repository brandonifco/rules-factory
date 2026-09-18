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
KINDS = ("section", "paragraph", "heading", "worked-example", "table")


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


class EcfrXml(Adapter):
    """The eCFR versioner's XML: the unit is a paragraph, an example, or a section's heading.

    The section tree is the corpus's own hierarchy, so unlike a flat text this grammar can say
    what kind each unit is. It does **not** rebuild the CFR's designator tree -- `(a)`, `(1)`,
    `(i)` nest by form, and resolving the forms that are ambiguous is the section locator
    checker's work, needed there because a *citation* names a designation path. An inventory
    needs only to enumerate and to key, so a paragraph is keyed by its designator as printed and
    its position in the section: `§ 107.29 ¶4 (a)`. Nothing here can be wrong about the nesting,
    because nothing here asserts any.
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
        return {section.get("N"): section for section in self.root.iter("DIV8")
                if section.get("N")}

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
        found = []
        for number in wanted:
            found += self._section_units(number, sections[number])
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
