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
    hypothetical.)
  * **The heading is checked too.** The last heading in the citation must occur as a line of its
    own between the start of the page before the cited page and the start of the quote. That is a
    weak test, and deliberately: pdftotext linearises columns and sidebars in its own order, so
    "the nearest heading above the quote" is not a fact the text preserves, and a stronger test
    would fail honest citations. What it does catch is a heading that is not near the quote at all.

`absence` and `coverage` are `tools/check-locators.py`'s checks, loaded from that file and run
unchanged, because a page extent means the same thing in both corpora.

What it does not buy: that the quote is the right passage for the entry, and that the extracted
text says what the printed page says. pdftotext joins words hyphenated at a line end, interleaves
table cells, and places sidebars and folios mid-sentence; the quote is held to the extraction, and
the extraction to the PDF only by `extract.py --check`.

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


def heading_near(heading, cited, span_start, corpus, starts):
    """The heading occurs as a whole line from the start of page cited-1 up to the quote."""
    first = max(1, cited - 1)
    begin = next((offset for offset, number in starts if number == first), 0)
    window = corpus[begin:span_start]
    return re.search(r"^[ \t]*" + re.escape(heading) + r"[ \t]*$", window, re.M) is not None


def check_locators(page_checker, entries, corpus, starts, reached):
    derived = [e.get("id", "?") for e in entries if "derivedFrom" in e]
    located = [e for e in entries if "derivedFrom" not in e]
    bad, checked, repeated = [], 0, 0
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
        for span in spans:
            touched = pages_touched(span, starts)
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
                           f"{'' if repeated == 1 else 's'} occur more than once){aside}")


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
    normalised = page_checker.normalise(corpus)
    index = page_checker.page_index(normalised, page_checker.DEFAULT_MARKER)
    extent = None
    declared = document.get("extent")
    if isinstance(declared, dict) and isinstance(declared.get("from"), int) and isinstance(declared.get("to"), int):
        extent = page_checker.extent_text(normalised, index, declared["from"], declared["to"])

    reached = set()
    print(f"{map_path} ({len(entries)} entries) against {corpus_path}")
    results = [
        ("locators", check_locators(page_checker, entries, corpus, starts, reached)),
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
