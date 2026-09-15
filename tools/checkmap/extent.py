"""`extent`, the map's claim about how much of its corpus it read (0009), in the two units a
corpus map has: printed pages, and CFR-style section designations (0020).
"""
import re

from .diagnostics import fail, skip, verdict
from .model import block, entries_of, label


EXTENT_UNITS = ("page", "section-designation")

# The section-designation locator grammar's section and subpart, read the way
# examples/faa-part-107/check-locators-section.py reads them. `CITE_SECTION` and `CITE_SUBPART`
# are that checker's expressions, verbatim; `test_check_map.py` runs both over every citation in
# the Part 107 maps and requires them to agree, so the two cannot drift apart silently.
CITE_SECTION = re.compile(r"§+\s*(\d+\.\d+)")
CITE_SUBPART = re.compile(r"\bsubpart\s+([A-Z])\b", re.I)
# One item of `extent.sections`: a section and nothing else -- no paragraph, no range.
EXTENT_SECTION = re.compile(r"^§\s*(\d+\.\d+)$")


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


def _page_extent(extent, bad):
    for field in sorted(set(extent) - {"unit", "from", "to"}):
        bad.append(f"  X  extent: `{field}` is not a field of a page extent (unit, from, to)")
    first, last = extent.get("from"), extent.get("to")
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (first, last)):
        bad.append(f"  X  extent: a page extent names integer `from` and `to`; got {first!r}..{last!r}")
    elif last < first:
        bad.append(f"  X  extent: `to` {last} is before `from` {first}")


def _section_extent(extent, bad):
    """The declared sections as numbers, or None when the list is malformed."""
    for field in sorted(set(extent) - {"unit", "sections"}):
        bad.append(f"  X  extent: `{field}` is not a field of a section-designation extent "
                   f"(unit, sections)")
    sections = extent.get("sections")
    if not isinstance(sections, list) or not sections:
        bad.append("  X  extent: a section-designation extent names a non-empty `sections` list")
        return None
    numbers = []
    for item in sections:
        match = EXTENT_SECTION.match(item) if isinstance(item, str) else None
        if not match:
            bad.append(f"  X  extent: sections holds {item!r}, which is not one section "
                       f"designation such as \"§ 107.25\"")
            continue
        if match.group(1) in numbers:
            bad.append(f"  X  extent: § {match.group(1)} is listed twice")
            continue
        numbers.append(match.group(1))
    return numbers


def check_extent(ctx):
    """The declared extent has the shape of its unit, and every section cited lies inside it.

    A `page` extent is a range, `{unit, from, to}`. Whether every page of it is reached is
    `check-locators.py`'s `coverage`, which reads the corpus.

    A `section-designation` extent is a list, `{unit, sections: ["§ 107.25", ...]}` (0020):
    CFR sections are not contiguous in what a mapper reads, so a range would claim the sections
    between. Every entry's locator names a section in that list, parsed by the locator grammar.
    Whether every listed section is reached is `check-locators-section.py`'s `coverage`.

    What it cannot do. A citation naming a whole subpart names no section, and nothing here reads
    the corpus to learn which sections the subpart holds, so such an entry is not placed; it is
    named in the summary rather than counted as inside. A derived entry cites nothing and is
    not placed either (0012). A map declaring no extent is not refused here: `coverage`, which
    has the corpus, is where an undeclared extent fails.
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
        return verdict(bad, f"page extent {extent.get('from')}-{extent.get('to')} is well formed; "
                            f"whether each page is reached is check-locators' `coverage`",
                       "the declared extent is malformed")

    numbers = _section_extent(extent, bad)
    if numbers is None or bad:
        return fail(bad, "the declared extent is malformed")
    placed, unplaced = 0, []
    for position, entry in enumerate(entries_of(doc)):
        if not isinstance(entry, dict) or "derivedFrom" in entry or "locator" not in entry:
            continue
        name = label(entry, position)
        citation = block(entry, "locator").get("citation")
        cited = cited_section(citation)
        if cited is None:
            bad.append(f"  X  {name}: citation {citation!r} names no section or subpart, so it "
                       f"cannot be placed inside the extent")
        elif cited[0] == "subpart":
            unplaced.append(f"{name} ({citation})")
        elif cited[1] not in numbers:
            bad.append(f"  X  {name}: cites § {cited[1]}, which is outside the declared extent "
                       f"({len(numbers)} sections); a map cites only what it claims to have read")
        else:
            placed += 1
    aside = (f"; {len(unplaced)} cite{'s' if len(unplaced) == 1 else ''} a subpart, which names no "
             f"section and is not placed: {', '.join(unplaced)}") if unplaced else ""
    return verdict(bad, f"{len(numbers)} sections declared; {placed} locators each name one of "
                        f"them{aside}",
                   "a locator cites a section outside the declared extent")
