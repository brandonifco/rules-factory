"""`extent`, the map's claim about how much of its corpus it read (0009), in the two units a
corpus map has: printed pages, and CFR-style section designations (0020).
"""
import re

from .diagnostics import fail, skip, verdict
from .extent_tables import _place_row, _tables_extent
from .locators import (cited_page, cited_row, cited_section, extent_designation,
                       printed_designation)
from mapcontract.entry import block, entries_of, label


EXTENT_UNITS = ("page", "section-designation")


def _quoted(extent, bad):
    """`extent.quoted`: the fraction of the extent the map claims it can show quoted (0054).

    Optional, and a map declaring none is reported by the locator checkers and not failed --
    measured across the five committed maps the fraction runs from 20% to 99.9%, so no single
    threshold could be right for all of them. Shape only here: whether the map meets its own
    floor needs the corpus, and `coverage` in each of the three locator checkers is what
    measures it. The same bargain `extent` itself makes (0009), one level down: nothing sizes
    the claim, and what the field buys is that the claim is written down.
    """
    if "quoted" not in extent:
        return ""
    value = extent.get("quoted")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
        bad.append(f"  X  extent: `quoted` is {value!r}; it is the fraction of the extent this "
                   f"map claims its verified evidence quotes, above 0 and at most 1. A map "
                   f"claiming none claims nothing, which is what omitting the field already says")
        return ""
    return f", declaring at least {value:.0%} of it quoted"


def _page_extent(extent, bad):
    for field in sorted(set(extent) - {"unit", "from", "to", "endsBefore", "quoted"}):
        bad.append(f"  X  extent: `{field}` is not a field of a page extent (unit, from, to, "
                   f"endsBefore, quoted)")
    first, last = extent.get("from"), extent.get("to")
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (first, last)):
        bad.append(f"  X  extent: a page extent names integer `from` and `to`; got {first!r}..{last!r}")
    elif last < first:
        bad.append(f"  X  extent: `to` {last} is before `from` {first}")
    if "endsBefore" in extent:
        heading = extent.get("endsBefore")
        if not isinstance(heading, str) or not heading.strip() or "\n" in heading \
                or heading != heading.strip():
            bad.append(f"  X  extent: endsBefore is {heading!r}; it names one heading on page `to`, "
                       f"as a single line of text with no surrounding whitespace (0024)")


def _placed_entries(doc):
    """(name, citation, entry) for every entry a declared extent has to place.

    A derived entry cites nothing and is not placed (0012); an entry with no locator has no
    citation to read. Both exemptions are the section branch's, taken here so that the two units
    exempt the same entries.
    """
    for position, entry in enumerate(entries_of(doc)):
        if not isinstance(entry, dict) or "derivedFrom" in entry or "locator" not in entry:
            continue
        yield label(entry, position), block(entry, "locator").get("citation"), entry


def _place_pages(doc, first, last, bad):
    """Every `scope: in` citation names a page inside `first`..`last` (#269).

    The page unit's half of what this check has always done for section designations. A page
    citation carries an integer page number the locator grammar already reads, so a map that
    narrows its declared extent below what it cites is as visible here as a map that drops a
    section it cites -- and `coverage` cannot see it either way round, because narrowing the
    extent makes coverage *easier* to satisfy: there are fewer units to reach.

    The three exemptions are the section branch's, for the same three reasons: a `scope: out`
    entry may cite beyond the extent, because recording what lies beyond the slice is what it is
    for (the SRD combat map cites the Rules Glossary at pp. 178-189 from an extent of 13-16), and
    is named in the summary rather than passed or failed; a derived entry cites nothing; and an
    entry with no locator has no citation to place.
    """
    placed, beyond = 0, []
    for name, citation, entry in _placed_entries(doc):
        page = cited_page(citation)
        if page is None:
            bad.append(f"  X  {name}: citation {citation!r} names no page, so it cannot be "
                       f"placed inside the extent")
            continue
        if first <= page <= last:
            placed += 1
        elif entry.get("scope") == "out":
            beyond.append(f"{name} ({citation})")
        else:
            bad.append(f"  X  {name}: cites p. {page}, outside the declared extent "
                       f"(pages {first}-{last}), and is not `scope: out`; an in-scope rule is "
                       f"cited inside what the map claims to have read")
    return placed, beyond


#: The reasons a `section-designation` citation grammar can have no address for a passage. The
#: authority is `examples/faa-part-107/check-locators-section.py`'s `UNREACHABLE_REASONS`, which
#: produces each at exactly one place in its walk; `test_check_map.py` holds the two sets equal,
#: the way `CITE_SECTION` is already held to the checker's own expression. A vocabulary copied
#: and left to drift would let a map declare a reason no run can give.
UNREACHABLE_REASONS = (
    "ambiguous-designator",
    "captioned-after-undesignated",
    "division-wrapper",
    "example-head-unreadable",
    "no-unit-for-element",
    "note-heading-elsewhere",
    "note-heading-unreadable",
    "states-own-designation",
)


def _unreachable(extent, bad):
    """`extent.unreachable`: the passages this grammar has no address for, and what each needs.

    Decided in [0038]. Shape only -- that the declaration is *true of the corpus* is the locator
    run's to establish, in both directions, because only a run of the walk knows what it refused.
    A map may omit the field; a map whose corpus has an unreachable passage and omits it fails
    there, not here.
    """
    items = extent.get("unreachable")
    if items is None:
        return
    if not isinstance(items, list) or not items:
        bad.append("  X  extent: `unreachable` is a non-empty list, or is absent. An empty list "
                   "says nothing a missing field does not")
        return
    seen = set()
    for position, item in enumerate(items, start=1):
        where = f"extent: unreachable[{position}]"
        if not isinstance(item, dict):
            bad.append(f"  X  {where} is not an object")
            continue
        for field in sorted(set(item) - {"sourceId", "opensWith", "reason", "requires"}):
            bad.append(f"  X  {where}: `{field}` is not a field of an unreachable passage "
                       f"(sourceId, opensWith, reason, requires)")
        for field in ("sourceId", "opensWith", "reason", "requires"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                bad.append(f"  X  {where}: `{field}` is a non-empty string")
        reason = item.get("reason")
        if isinstance(reason, str) and reason not in UNREACHABLE_REASONS:
            bad.append(f"  X  {where}: reason {reason!r} is outside the closed set "
                       f"({', '.join(UNREACHABLE_REASONS)}); a reason no walk can give is a "
                       f"declaration nothing could ever hold to the corpus")
        key = (item.get("sourceId"), item.get("opensWith"))
        if all(isinstance(part, str) for part in key):
            if key in seen:
                bad.append(f"  X  {where}: {key[1]!r} in {key[0]} is declared twice")
            seen.add(key)


def _section_extent(extent, bad):
    """The declared sections as numbers, or None when the list is malformed."""
    for field in sorted(set(extent) - {"unit", "sections", "tables", "unreachable", "quoted"}):
        bad.append(f"  X  extent: `{field}` is not a field of a section-designation extent "
                   f"(unit, sections, tables, unreachable, quoted)")
    _unreachable(extent, bad)
    sections = extent.get("sections")
    if not isinstance(sections, list) or not sections:
        bad.append("  X  extent: a section-designation extent names a non-empty `sections` list")
        return None
    numbers = []
    for item in sections:
        designation = extent_designation(item)
        if designation is None:
            bad.append(f"  X  extent: sections holds {item!r}, which is not one structural "
                       f"designation such as \"§ 107.25\" or \"Rule 6\"")
            continue
        if designation in numbers:
            bad.append(f"  X  extent: {printed_designation(designation)} is listed twice")
            continue
        numbers.append(designation)
    return numbers


def check_extent(ctx):
    """The declared extent has the shape of its unit, and every citation lies inside it.

    A `page` extent is a range, `{unit, from, to}`. Whether every page of it is reached is
    `check-locators.py`'s `coverage`, which reads the corpus; **that every `scope: in` citation
    names a page inside it** is checked here, in the same three exemptions and for the same
    reason as the section unit below (#269). It may also name `endsBefore`, a heading on page
    `to` at which the slice stops (0024), whose shape alone is checked here: that the heading is
    a line on that page, and that no in-scope quote lies at or after it, need the corpus's lines,
    and the page-marked PDF text checker is what reads them.

    A `section-designation` extent is a list, `{unit, sections: ["§ 107.25", ...]}` (0020):
    CFR sections are not contiguous in what a mapper reads, so a range would claim the sections
    between. Whether every listed section is reached is `check-locators-section.py`'s `coverage`.

    It may also carry `tables` (0035), one item per table of a cited section: `rows` (a list of
    row keys, or `"all"`) or `excluded` with a reason. What is checked here is the shape of that
    list, and that every in-scope entry citing a table row cites a row the slice took. That
    **every** table printed inside a cited section appears in the list needs the corpus, and the
    `ecfr-xml` adapter refuses one the extent passes over in silence (`mapper inventory`).

    Every `scope: in` entry's locator names a section in that list -- or, in a page extent, a
    page in the range -- parsed by the locator
    grammar; a section outside it, or a whole subpart, fails. A `scope: out` entry may cite
    beyond the extent, because recording what lies beyond the slice is what an out-of-scope entry
    is for (Part 107's `subpart-d-categories`). Such an entry is named in the summary as an
    out-of-scope citation beyond the extent, and neither passes nor fails. A derived entry cites
    nothing and is not placed (0012). A map declaring no extent is not refused here: `coverage`, which
    has the corpus, is where an undeclared extent fails.

    Either unit may carry `quoted` (0054, #270), the fraction of the extent the map claims its
    verified evidence quotes. Only its shape is checked here; each locator checker's `coverage`
    measures the fraction and holds the map to the floor it declared.
    """
    doc = ctx["map"]
    if "extent" not in doc:
        return skip("the map declares no `extent`, so there is no shape to check and no bound "
                    "for a citation to lie inside; check-locators' `coverage` refuses the omission",
                    had_subject=False)
    extent, bad = doc.get("extent"), []
    if not isinstance(extent, dict):
        return fail(["  X  extent: `extent` is not an object"], "the declared extent is malformed")
    unit = extent.get("unit")
    if unit not in EXTENT_UNITS:
        return fail([f"  X  extent: unit is {unit!r}, outside {{{', '.join(EXTENT_UNITS)}}}"],
                    "the declared extent is in no unit a map may use")
    if unit == "page":
        _page_extent(extent, bad)
        claim = _quoted(extent, bad)
        end = (f", ending before the heading {extent['endsBefore']!r} on p. {extent.get('to')}"
               if isinstance(extent.get("endsBefore"), str) else "")
        if bad:
            return fail(bad, "the declared extent is malformed")
        placed, beyond = _place_pages(doc, extent["from"], extent["to"], bad)
        aside = (f"; {len(beyond)} out-of-scope citation{'' if len(beyond) == 1 else 's'} beyond "
                 f"the extent, neither passed nor failed: {', '.join(beyond)}") if beyond else ""
        return verdict(bad, f"page extent {extent.get('from')}-{extent.get('to')}{end} is well formed"
                            f"{claim}; {placed} locators each name a page inside it{aside}; whether "
                            f"each page is reached, and how much of it is quoted, is "
                            f"check-locators' `coverage`",
                       "a locator cites a page outside the declared extent")

    claim = _quoted(extent, bad)
    numbers = _section_extent(extent, bad)
    taken = _tables_extent(extent, numbers or [], bad)
    if numbers is None or bad:
        return fail(bad, "the declared extent is malformed")
    placed, beyond, rows = 0, [], 0
    for name, citation, entry in _placed_entries(doc):
        row = cited_row(citation)
        if row is not None and entry.get("scope") != "out":
            rows += 1
            bad += _place_row(name, citation, row, numbers, taken)
            continue
        cited = cited_section(citation)
        if cited is None:
            bad.append(f"  X  {name}: citation {citation!r} names no section or subpart, so it "
                       f"cannot be placed inside the extent")
            continue
        inside = cited[0] == "section" and cited[1] in numbers
        if inside:
            placed += 1
        elif entry.get("scope") == "out":
            beyond.append(f"{name} ({citation})")
        else:
            where = (printed_designation(cited[1]) if cited[0] == "section"
                     else f"subpart {cited[1]}")
            bad.append(f"  X  {name}: cites {where}, outside the declared extent "
                       f"({len(numbers)} sections), and is not `scope: out`; an in-scope rule is "
                       f"cited inside what the map claims to have read")
    aside = (f"; {len(beyond)} out-of-scope citation{'' if len(beyond) == 1 else 's'} beyond the "
             f"extent, neither passed nor failed: {', '.join(beyond)}") if beyond else ""
    sliced = (f"; {len(taken)} table(s) accounted for, {rows} locator(s) naming a row the extent "
              f"takes") if taken or rows else ""
    return verdict(bad, f"{len(numbers)} sections declared{claim}; {placed} locators each name "
                        f"one of them{sliced}{aside}",
                   "a locator cites a section outside the declared extent")
