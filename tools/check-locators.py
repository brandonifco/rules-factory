#!/usr/bin/env python3
"""Check that each map entry's page citation matches where its evidence actually sits.

A corpus with page markers in the text makes `locator` mechanically verifiable: find the
entry's evidence in the corpus, walk back to the nearest marker, compare. This does not
check that the evidence is the *right* sentence for the entry -- only that the page it is
cited to is the page it is on.

It can only do that where `evidence` holds a **quoted span** of the corpus. In the
backgammon map it holds a summary of what the evidence shows ("Both figures.", "Both
elections."), so nothing is locatable and nothing can be checked -- which is why thirteen
wrong citations survived a build. An unlocatable entry is reported and fails the run; it is
never reported as ok.

Usage: check-locators.py <corpus-map.json> <corpus.txt> [--marker-re RE] [--page-re RE]
Exit 0 if every locatable entry agrees, 1 otherwise, 2 on a usage error.
"""
import argparse
import json
import re
import sys

DEFAULT_MARKER = r"\{(\d+)\}"
DEFAULT_PAGE = r"\bp\.\s*(\d+)"


def normalise(text):
    """Collapse whitespace so a quote that wraps lines matches the corpus."""
    return re.sub(r"\s+", " ", text).strip()


def page_index(corpus, marker_re):
    """Offsets in the normalised corpus where each page begins."""
    return [(m.start(), int(m.group(1))) for m in re.finditer(marker_re, corpus)]


def page_of(offset, index):
    page = None
    for start, number in index:
        if start > offset:
            break
        page = number
    return page


def probe(evidence, corpus):
    """Longest prefix of the evidence that appears verbatim: its span and how much matched."""
    words = evidence.split()
    for length in range(len(words), 4, -1):
        needle = " ".join(words[:length])
        at = corpus.find(needle)
        if at != -1:
            return (at, at + len(needle)), length / len(words)
    return None, 0.0


def pages_spanned(span, index):
    """Every page the matched text touches.

    A quote may straddle a page break -- the backgammon arrangement sentence begins on p. 272
    and the marker for 273 falls before "Fig. 1", mid-sentence. Citing either page is honest,
    so the check accepts any of them rather than picking one and inventing a rule.
    """
    start, end = span
    pages = {page_of(start, index)}
    pages.update(number for offset, number in index if start < offset < end)
    return {p for p in pages if p is not None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("map_path")
    parser.add_argument("corpus_path")
    parser.add_argument("--marker-re", default=DEFAULT_MARKER)
    parser.add_argument("--page-re", default=DEFAULT_PAGE)
    args = parser.parse_args()

    entries = json.load(open(args.map_path))["entries"]
    corpus = normalise(open(args.corpus_path, encoding="utf-8").read())
    index = page_index(corpus, args.marker_re)
    if not index:
        print("no page markers found; nothing to check", file=sys.stderr)
        return 2

    bad = unlocatable = 0
    for entry in entries:
        citation = entry.get("locator", {}).get("citation", "")
        claimed = re.search(args.page_re, citation)
        if not claimed:
            continue
        span, coverage = probe(normalise(entry.get("evidence", "")), corpus)
        if span is None:
            unlocatable += 1
            print(f"  ?  {entry['id']}: evidence not found verbatim; cannot check")
            continue
        actual = pages_spanned(span, index)
        if int(claimed.group(1)) not in actual:
            bad += 1
            partial = "" if coverage > 0.95 else f" (matched {coverage:.0%} of the evidence)"
            found = " or ".join(f"p. {p}" for p in sorted(actual))
            print(f"  X  {entry['id']}: cited p. {claimed.group(1)}, evidence is on {found}{partial}")

    total = len(entries)
    checked = total - unlocatable
    if bad:
        print(f"\n{bad} of {total} entries cite the wrong page ({unlocatable} unlocatable)")
        return 1
    if checked == 0:
        print(
            f"\nskip: no entry's evidence appears verbatim in the corpus, so no citation "
            f"was checked. This is not a pass. `evidence` must carry a quoted span for a "
            f"locator to be verifiable at all.",
            file=sys.stderr,
        )
        return 1
    if checked < total:
        print(f"\n{checked} of {total} citations verified; {unlocatable} could not be checked")
        return 1
    print(f"locators ok (all {total} checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
