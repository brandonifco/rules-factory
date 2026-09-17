#!/usr/bin/env python3
"""Check a map's citations against a page-marked text extracted from a PDF (adapter
`pdftotext-page-marked`, locator grammar `heading-path-and-printed-page`).

The corpus this reads is `srd-5.2.1.txt`, which `extract.py` derives from the committed SRD 5.2.1
PDF: pdftotext's text for each physical page, each preceded by a `{N}` marker line, where physical
page N is printed page N. A citation reads `Combat / Making an Attack / p. 15`: a path of the
corpus's own headings, then the printed page.

It is `tools/check-locators.py`'s page-marker idea with three differences, each stricter:

  * **Exact, not longest-prefix.** The whole of `evidence` must appear in the text, with only runs
    of whitespace treated as equal (a quote wraps where pdftotext broke the line). The page checker
    accepts the longest prefix of five words or more, because it was retrofitted onto evidence that
    was never a quote; here a quote appears or the entry fails.
  * **Every occurrence, not the first.** A sentence the corpus repeats, or one the map quotes twice
    under two entries, is found everywhere it occurs, and every occurrence must touch the cited
    page. The count is reported. (The SRD restates rules in its Rules Glossary, so this is not
    hypothetical.) **Where an occurrence lies off the cited page, the heading path decides whether
    it is this entry's passage at all** (0030, #207): see below.
  * **The heading is checked too.** The last heading in the citation must occur as a line of its
    own between the start of the page before the cited page and the start of the quote. That is a
    weak test, and deliberately: pdftotext linearises columns and sidebars in its own order, so
    "the nearest heading above the quote" is not a fact the text preserves, and a stronger test
    would fail honest citations. What it does catch is a heading that is not near the quote at all.

**A passage the corpus prints more than once is identified by its heading path** (0030,
[#207](https://github.com/brandonifco/rules-factory/issues/207)). `Speed 0. Your Speed is 0 and
can't increase.` is printed under five conditions and `Round Down` twice, heading included, so
"every occurrence touches the cited page" made twenty of the conditions map's entries extend their
span through every rule between the condition's lead and their own, and made `round-down`
uncitable without annexing the next glossary entry. What identifies a passage in a
`section-designation` corpus is the container the citation names, and the page in a page-marked one
is positional, not containing. The heading path is the container this grammar has, so when a quote
occurs off the cited page, the path is asked which occurrence the citation means:

  * each line of its own matching the citation's **last** heading selects the **first** occurrence
    of the quote after it, and a heading selects nothing when no occurrence follows it;
  * a heading line counts only where the citation's **earlier** headings occur as lines, in order,
    before it;
  * the citation must select **exactly one** occurrence, and that occurrence must touch the cited
    page. Selecting none, or more than one, fails: this checker refuses an ambiguous citation
    rather than picking an occurrence for the mapper.

The rule is the extraction's reading order, which is all a flat text has: pdftotext gives no
hierarchy, so "under this heading" can only mean "after this heading line, and before the same
quote appears again". Two consequences, both deliberate. A citation whose last heading is repeated
is separated only by a heading above it that is not — `Rules Glossary / Round Down / p. 187`
resolves, because no `Rules Glossary` line precedes p. 5's `Round Down`, and `Playing the Game /
Round Down / p. 5` does not, because `Playing the Game` precedes both. And an entry citing a
heading its quote does not follow fails rather than reaching for a distant occurrence.

`absence` and `coverage` are `tools/check-locators.py`'s checks, loaded from that file and run
unchanged, because a page extent means the same thing in both corpora. Two things differ in
what they are given, both from `extent.endsBefore` (0024): `absence` searches the extent only up
to that heading, and a quote at or after it does not reach page `to` for `coverage`.

Two checks are this checker's own (0024):

  * **`extent-end`.** A page extent may end before a heading on its last page,
    `{"unit": "page", "from": 13, "to": 16, "endsBefore": "Damage and Healing"}`. The heading must
    occur exactly once as a line of its own on page `to`, and no `scope: in` entry's quote may
    lie at or after it on that page, or run across it. A `scope: out` entry may quote beyond it
    (0020), and is named in the summary, neither passed nor failed. "After", like everything
    here, is in pdftotext's reading order, which on a two-column page is the extraction's and
    not necessarily the eye's.
  * **`extraction`.** The quote is verbatim of the extraction, and where the extraction garbles
    the passage the entry declares `extraction: {defect, renderedReading}`. For each declared
    defect, a cheap test that the defect is really there, at every occurrence of the quote:
    `interrupted-by-page-furniture`, the quote runs across a line that is the page's own folio;
    `interleaved-table`, it runs across three or more blank-line-separated blocks, the shape
    pdftotext gives table cells; `split-by-sidebar`, it begins or ends mid-sentence. And the
    other way: a quote that runs across a folio line and does not declare
    `interrupted-by-page-furniture` fails, so that defect cannot be silent. `renderedReading` is
    printed for every entry and marked NOT VERIFIED: nothing here reads the page.

What it does not buy: that the quote is the right passage for the entry, and that the extracted
text says what the printed page says. pdftotext joins words hyphenated at a line end, interleaves
table cells, and places sidebars and folios mid-sentence; the quote is held to the extraction, and
the extraction to the PDF only by `extract.py --check`. The `extraction` tests show that a
declared defect has the shape it names, not that the cells are out of order or that the text
between a sentence's halves is a sidebar, and not that `renderedReading` is right. An undeclared
interleaved table or split sentence passes.

Usage: check-locators-pdf-text.py <corpus-map.json> <srd-5.2.1.txt>
Exit 0 if every entry was located on its cited page and the other checks passed; 1 otherwise; 2 on
a usage error (including a corpus with no page markers, or markers out of sequence).
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_CHECKER = os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools", "check-locators.py")
MARKER = re.compile(r"^\{(\d+)\}$", re.M)
PAGE = re.compile(r"\bp\.\s*(\d+)\s*$")
FOLIO_LINE = re.compile(r"^[ \t]*(\d+)[ \t]*$", re.M)
BLOCK_BREAK = re.compile(r"\n[ \t]*\n")
TABLE_BLOCKS = 3
SENTENCE_END = tuple(".:!?”\"’)")


def load_page_checker():
    spec = importlib.util.spec_from_file_location("check_locators", PAGE_CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def page_starts(corpus):
    """[(offset, page)] for every marker, which must run 1, 2, 3, ... with no gap."""
    starts = [(m.start(), int(m.group(1))) for m in MARKER.finditer(corpus)]
    if not starts:
        raise ValueError("no {N} page markers; this is not a page-marked extraction")
    for expected, (_, number) in enumerate(starts, 1):
        if number != expected:
            raise ValueError(f"page marker {number} where {expected} was expected; markers must be consecutive")
    return starts


def page_at(offset, starts):
    page = None
    for start, number in starts:
        if start > offset:
            break
        page = number
    return page


def occurrences(evidence, corpus):
    """Every (start, end) where the evidence occurs, whitespace runs matching any whitespace."""
    words = evidence.split()
    if not words:
        return []
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words))
    return [(m.start(), m.end()) for m in pattern.finditer(corpus)]


def pages_touched(span, starts):
    start, end = span
    touched = {page_at(start, starts)}
    touched.update(number for offset, number in starts if start < offset < end)
    return {p for p in touched if p is not None}


def heading_lines(heading, corpus):
    """Every offset where `heading` occurs as a line of its own."""
    return [m.start() for m in
            re.finditer(r"^[ \t]*" + re.escape(heading) + r"[ \t]*$", corpus, re.M)]


def selected_by_path(headings, spans, corpus):
    """The occurrences of a repeated quote that the citation's heading path picks out (0030).

    One per line matching the citation's last heading: the first occurrence after it, which is
    the only sense "under this heading" has in a flat text with no hierarchy. A line counts only
    where the citation's earlier headings occur as lines, in order, before it, so a heading the
    corpus repeats is separated by a heading above it that it is not repeated under.

    Returns the occurrences in corpus order, without duplicates. The caller requires exactly one:
    none and several are both citations that do not identify a passage, and neither is guessed at.
    """
    inner, above = headings[-1], headings[:-1]
    picked = []
    for line in heading_lines(inner, corpus):
        cursor, resolved = -1, True
        for outer in above:
            at = next((o for o in heading_lines(outer, corpus) if cursor < o < line), None)
            if at is None:
                resolved = False
                break
            cursor = at
        if not resolved:
            continue
        first = next((span for span in spans if span[0] > line), None)
        if first is not None and first not in picked:
            picked.append(first)
    return sorted(picked)


def entry_occurrences(entry, corpus, starts):
    """The occurrences of an entry's quote that its own citation covers (0030).

    Every occurrence, except that where the quote is printed off the cited page as well, the
    heading path identifies which one the entry means, and the others are another entry's passage
    or nobody's. `locators` is where an unidentifiable citation fails; the checks that use this --
    the extent's end and the extraction defects -- ask only about the entry's own passage, and
    fall back to every occurrence when the path settles nothing, which is the reading they had
    before there was a path to ask.
    """
    citation = str(entry.get("locator", {}).get("citation", ""))
    page = PAGE.search(citation)
    spans = occurrences(str(entry.get("evidence", "")), corpus)
    segments = [s.strip() for s in citation.split(" / ")]
    if not page or len(segments) < 2 or len(spans) < 2:
        return spans
    cited = int(page.group(1))
    if all(cited in pages_touched(span, starts) for span in spans):
        return spans
    picked = selected_by_path(segments[:-1], spans, corpus)
    return picked if len(picked) == 1 else spans


def heading_near(heading, cited, span_start, corpus, starts):
    """The heading occurs as a whole line from the start of page cited-1 up to the quote."""
    first = max(1, cited - 1)
    begin = next((offset for offset, number in starts if number == first), 0)
    window = corpus[begin:span_start]
    return re.search(r"^[ \t]*" + re.escape(heading) + r"[ \t]*$", window, re.M) is not None


def page_bounds(page, corpus, starts):
    """(start, end) offsets of physical page `page`, or (None, None) when there is no such page."""
    begin = next((offset for offset, number in starts if number == page), None)
    if begin is None:
        return None, None
    return begin, next((offset for offset, number in starts if number == page + 1), len(corpus))


def page_extent(document):
    """The declared extent when it is a page range with integer bounds, else None."""
    declared = document.get("extent")
    if isinstance(declared, dict) and declared.get("unit") == "page" \
            and all(isinstance(declared.get(k), int) and not isinstance(declared.get(k), bool)
                    for k in ("from", "to")):
        return declared
    return None


def extent_end(extent, corpus, starts):
    """(offset, problem): where the `endsBefore` heading's line starts on page `to`.

    (None, None) when the extent names no `endsBefore`. The heading must be a whole line, and
    exactly one on that page: two would leave where the slice stops undecided.
    """
    if extent is None or "endsBefore" not in extent:
        return None, None
    heading, last = extent.get("endsBefore"), extent["to"]
    if not isinstance(heading, str) or not heading.strip():
        return None, f"endsBefore is {heading!r}, which is not a heading"
    begin, end = page_bounds(last, corpus, starts)
    if begin is None:
        return None, f"the extent ends on p. {last}, and the text has no such page"
    lines = [begin + m.start() for m in
             re.finditer(r"^[ \t]*" + re.escape(heading.strip()) + r"[ \t]*$", corpus[begin:end], re.M)]
    if not lines:
        return None, f"endsBefore names {heading!r}, which does not occur as a line of its own on p. {last}"
    if len(lines) > 1:
        return None, (f"endsBefore names {heading!r}, which occurs {len(lines)} times as a line on "
                      f"p. {last}, so where the slice stops is not decided")
    return lines[0], None


def check_locators(page_checker, entries, corpus, starts, reached, end=None):
    """Every occurrence of every quote, on its cited page, under a heading near it.

    `end` is (page, offset) when the extent stops at a heading on its last page: a quote starting
    at or after that offset does not reach that page for `coverage`.
    """
    derived = [e.get("id", "?") for e in entries if "derivedFrom" in e]
    located = [e for e in entries if "derivedFrom" not in e]
    bad, checked, repeated, identified = [], 0, 0, 0
    for entry in located:
        name = entry.get("id", "?")
        citation = str(entry.get("locator", {}).get("citation", ""))
        page = PAGE.search(citation)
        segments = [s.strip() for s in citation.split(" / ")]
        if not page or len(segments) < 2:
            bad.append(f"  X  {name}: citation {citation!r} is not `Heading / ... / p. N`")
            continue
        cited, heading = int(page.group(1)), segments[-2]
        spans = occurrences(str(entry.get("evidence", "")), corpus)
        if not spans:
            bad.append(f"  ?  {name}: evidence does not occur in the extracted text; nothing was checked")
            continue
        checked += 1
        if len(spans) > 1:
            repeated += 1
        # 0030: an occurrence off the cited page is another printing of the same words, and the
        # heading path says whether it is this entry's. Where every occurrence is on the cited
        # page there is nothing to identify: the quote is checked at all of them, as before.
        elsewhere = [s for s in spans if cited not in pages_touched(s, starts)]
        if elsewhere:
            picked = selected_by_path(segments[:-1], spans, corpus)
            where = ", ".join(f"p. {p}" for p in sorted(
                {p for span in spans for p in pages_touched(span, starts)}))
            path = " / ".join(segments[:-1])
            if len(picked) != 1:
                bad.append(f"  X  {name}: the corpus prints this quote {len(spans)} times ({where}), "
                           f"and the heading path {path!r} "
                           + (f"selects none of them" if not picked else
                              f"selects {len(picked)} of them")
                           + f"; the citation does not identify one passage, and this checker does "
                             f"not guess which was meant (0030)")
                continue
            identified += 1
            spans = picked
        for span in spans:
            touched = pages_touched(span, starts)
            if end is not None and span[0] >= end[1]:
                reached.update(touched - {end[0]})
            else:
                reached.update(touched)
            if cited not in touched:
                found = " or ".join(f"p. {p}" for p in sorted(touched))
                where = f" (occurrence {spans.index(span) + 1} of {len(spans)})" if len(spans) > 1 else ""
                bad.append(f"  X  {name}: cited p. {cited}, evidence{where} is on {found}")
            elif not heading_near(heading, cited, span[0], corpus, starts):
                bad.append(f"  X  {name}: heading {heading!r} does not occur as a line between the start "
                           f"of p. {max(1, cited - 1)} and the quote")
    aside = (f"; {len(derived)} derived entr{'y' if len(derived) == 1 else 'ies'} not located, because a "
             f"derived entry cites nothing") if derived else ""
    if not located:
        return page_checker.skip("the map has no entries to locate")
    if bad:
        return page_checker.fail(bad, f"{checked} of {len(located)} entries located exactly{aside}")
    return page_checker.ok(f"all {checked} citations verified: every occurrence of each quote, exactly, on the "
                           f"cited page, under a heading near it ({repeated} quoted text"
                           f"{'' if repeated == 1 else 's'} occur more than once, {identified} of them "
                           f"printed off the cited page too and identified by the heading path){aside}")


def bound_examples(entries):
    """Each authored example in `ambiguity.bounds` as an entry of its own (rules-factory 0031).

    A bound quotes the corpus and carries a `locator`, exactly as `evidence` does, so it is
    checked by `check_locators` above rather than by a second implementation of finding a quote:
    an owner's ruling is admitted or refused by comparing it against that quotation, so a bound
    whose words are not at its citation is a bound of nothing. They are located with a `reached`
    of their own, because coverage asks which pages an entry's own evidence reached and an example
    quoted to bound someone else's term is not a verdict on the page it sits on.
    """
    out = []
    for entry in entries:
        ambiguity = entry.get("ambiguity")
        bounds = ambiguity.get("bounds") if isinstance(ambiguity, dict) else None
        listed = bounds.get("examples") if isinstance(bounds, dict) else None
        for index, example in enumerate(listed if isinstance(listed, list) else [], start=1):
            if isinstance(example, dict):
                out.append({"id": f"{entry.get('id', '?')}: bounds.examples[{index}]",
                            "locator": example.get("locator") or {},
                            "evidence": example.get("text", "")})
    return out


def located_entries(entries):
    return [e for e in entries if "derivedFrom" not in e]


def check_extent_end(page_checker, entries, corpus, starts, extent, boundary, problem):
    """No in-scope quote lies at or after the heading the extent ends before (0024)."""
    if extent is None or "endsBefore" not in extent:
        return page_checker.Result("skip", "NOT VERIFIED -- the extent names no `endsBefore`, so it "
                                           "ends with its last page and there is no heading to hold "
                                           "quotes before", had_subject=False)
    if problem:
        return page_checker.fail([f"  X  extent: {problem}"], "the heading the extent ends before is not on its last page")
    last = extent["to"]
    page_begin, page_end = page_bounds(last, corpus, starts)
    bad, beyond, held = [], [], 0
    for entry in located_entries(entries):
        name = entry.get("id", "?")
        for span in entry_occurrences(entry, corpus, starts):
            if span[1] <= page_begin or span[0] >= page_end:
                continue  # not on the last page
            if span[1] <= boundary:
                held += 1
                continue
            if entry.get("scope") == "out":
                beyond.append(name)
            else:
                where = "runs across" if span[0] < boundary else "lies after"
                bad.append(f"  X  {name}: is scope: in, and its quote {where} the heading "
                           f"{extent['endsBefore']!r} on p. {last}, where the extent ends")
    if bad:
        return page_checker.fail(bad, f"an in-scope quote lies beyond the heading the extent ends before")
    aside = (f"; {len(beyond)} out-of-scope quote{'' if len(beyond) == 1 else 's'} beyond it, neither "
             f"passed nor failed: {', '.join(sorted(set(beyond)))}") if beyond else ""
    return page_checker.ok(f"the extent ends before {extent['endsBefore']!r}, a line on p. {last}; "
                           f"{held} quote occurrence{'' if held == 1 else 's'} on that page lie before it "
                           f"and no in-scope quote lies at or after it{aside}")


def folios_inside(span, corpus, starts):
    """The folio lines lying wholly inside the span, each the number of the page it is on."""
    start, end = span
    return [m.group(1) for m in FOLIO_LINE.finditer(corpus, start, end)
            if start < m.start() and m.end() < end and int(m.group(1)) == page_at(m.start(), starts)]


def defect_present(defect, evidence, span, corpus, starts):
    """None when the declared defect has its shape at this occurrence, else what is missing."""
    if defect == "interrupted-by-page-furniture":
        return None if folios_inside(span, corpus, starts) else \
            "runs across no folio line, so no page furniture interrupts it"
    if defect == "interleaved-table":
        blocks = len(BLOCK_BREAK.split(corpus[span[0]:span[1]]))
        return None if blocks >= TABLE_BLOCKS else \
            (f"runs across {blocks} blank-line-separated block{'' if blocks == 1 else 's'}, fewer than "
             f"the {TABLE_BLOCKS} a table's cells give")
    if defect == "split-by-sidebar":
        text = evidence.strip()
        mid_start = text[:1].islower()
        mid_end = not text.endswith(SENTENCE_END)
        return None if (mid_start or mid_end) else \
            "begins and ends on a sentence boundary, so no sentence in it is split"
    return f"{defect!r} is not a defect this checker has a test for"


def check_extraction(page_checker, entries, corpus, starts):
    """A declared extraction defect is really there, and a folio inside a quote is declared (0024)."""
    bad, declared, readings = [], 0, []
    for entry in located_entries(entries):
        name = entry.get("id", "?")
        evidence = str(entry.get("evidence", ""))
        spans = entry_occurrences(entry, corpus, starts)
        extraction = entry.get("extraction")
        defect = extraction.get("defect") if isinstance(extraction, dict) else None
        if "extraction" in entry:
            declared += 1
            if not isinstance(extraction, dict):
                bad.append(f"  X  {name}: extraction is not an object")
                continue
            if not spans:
                bad.append(f"  ?  {name}: declares {defect!r}, and its evidence does not occur in the "
                           f"extracted text, so the defect was not tested")
                continue
            for position, span in enumerate(spans, 1):
                missing = defect_present(defect, evidence, span, corpus, starts)
                if missing:
                    where = f" (occurrence {position} of {len(spans)})" if len(spans) > 1 else ""
                    bad.append(f"  X  {name}: declares extraction defect {defect!r}, and its quote{where} "
                               f"{missing}")
            readings.append(f"  ~  {name}: {defect}; renderedReading NOT VERIFIED -- read from the "
                            f"rendered page, which nothing here reads: {extraction.get('renderedReading')!r}")
        if defect != "interrupted-by-page-furniture":
            for span in spans:
                folios = folios_inside(span, corpus, starts)
                if folios:
                    bad.append(f"  X  {name}: its quote runs across the folio line {folios[0]!r}, page "
                               f"furniture the printed sentence does not contain, and the entry does "
                               f"not declare extraction.defect interrupted-by-page-furniture")
                    break
    if bad:
        return page_checker.fail(bad, "an extraction defect is undeclared, or declared and not there")
    if not declared:
        return page_checker.ok("no quote runs across a folio line, and no entry declares an extraction defect")
    return page_checker.ok(f"{declared} declared extraction defect{'' if declared == 1 else 's'} each have "
                           f"their shape at every occurrence, and no other quote runs across a folio "
                           f"line; {len(readings)} renderedReading{'' if len(readings) == 1 else 's'} "
                           f"not verified, listed below", readings)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__.split("Usage:")[1].strip(), file=sys.stderr)
        return 2
    map_path, corpus_path = argv
    try:
        with open(map_path, encoding="utf-8") as handle:
            document = json.load(handle)
        with open(corpus_path, encoding="utf-8") as handle:
            corpus = handle.read()
        starts = page_starts(corpus)
    except (OSError, ValueError) as error:
        print(f"cannot check {map_path} against {corpus_path}: {error}", file=sys.stderr)
        return 2

    page_checker = load_page_checker()
    entries = [e for e in document.get("entries") or [] if isinstance(e, dict)]
    declared = page_extent(document)
    boundary, problem = extent_end(declared, corpus, starts)
    extent = None
    if declared is not None:
        begin = page_bounds(declared["from"], corpus, starts)[0]
        stop = boundary if boundary is not None else page_bounds(declared["to"], corpus, starts)[1]
        if begin is not None and stop is not None:
            extent = page_checker.normalise(corpus[begin:stop])

    reached = set()
    end = (declared["to"], boundary) if boundary is not None else None
    print(f"{map_path} ({len(entries)} entries) against {corpus_path}")
    bounds = bound_examples(entries)
    results = [
        ("locators", check_locators(page_checker, entries, corpus, starts, reached, end)),
        ("bounds", check_locators(page_checker, bounds, corpus, starts, set())
         if bounds else page_checker.skip("no entry carries `ambiguity.bounds`, so no authored "
                                          "example bounds a term in this map", had_subject=False)),
        ("extent-end", check_extent_end(page_checker, entries, corpus, starts, declared, boundary, problem)),
        ("extraction", check_extraction(page_checker, entries, corpus, starts)),
        ("absence", page_checker.check_absence(entries, extent)),
        ("coverage", page_checker.check_coverage(document, reached)),
    ]
    passed = failed = skipped = fatal = 0
    for name, result in results:
        print(f"[{result.status}] {name}: {result.summary}")
        for line in result.details:
            print(line)
        passed += result.status == "ok"
        failed += result.status == "fail"
        skipped += result.status == "skip"
        fatal += result.fatal
    print(f"\n{passed} ok, {failed} failed, {skipped} not verified")
    if fatal:
        return 1
    if not passed:
        print("nothing was actually checked; this is not a pass", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
