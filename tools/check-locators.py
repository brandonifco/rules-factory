#!/usr/bin/env python3
"""Check a map against the corpus it claims to describe: citations, absences, and reach.

A corpus with page markers in the text makes four different claims mechanically testable,
and this tool runs them as four named checks rather than one verdict, because they fail
for different reasons and a single number hid that:

  `locators`  Every entry's evidence is found in the corpus, walked back to the nearest
              marker, and compared against the page its citation names. This does not check
              that the evidence is the *right* sentence for the entry -- only that the page
              it is cited to is the page it is on.

  `absence`   Every `absentFrom` entry (0009) claims the corpus does not state its rule and
              names the terms it would state it in. Each of those terms is searched for
              inside the declared extent, and one that turns up fails the entry. This is the
              only check in the repository that can go red by *finding* something.

  `coverage`  Every page of the extent the map declares it read is reached by some entry's
              verified evidence. A page inside the extent that no entry's quote touches is
              a page nobody demonstrably read, which is the state -- "nobody looked" -- that
              a map exists to distinguish from a recorded verdict.

  `extent-bounds`
              The other direction, and the one `coverage` is structurally blind to (#269):
              no `scope: in` entry's verified quote lies outside the declared range. Narrowing
              an extent makes `coverage` *easier* to satisfy -- fewer pages to reach -- so a
              map that claims to have read less than it quotes passes every check that counts
              units reached. A `scope: out` entry may quote beyond the extent and is named.

`locators` can only run where `evidence` holds a **quoted span** of the corpus. Where it
held a summary ("Both figures.", "Both elections."), nothing was locatable and nothing was
checkable, which is why thirteen wrong citations survived a build. An unlocatable entry is
reported and fails the run; it is never reported as ok.

What none of the three buys, stated here rather than in a commit message:

  * A term absent from the extent is not a rule absent from the extent. The corpus could
    state the rule in words the mapper did not think to search for, and `absence` would pass.
    What it does catch is the mapper who declared an absence without looking -- and that is
    the failure both #20 and #29 are instances of.
  * A page reached by one quote is not a page read. `coverage` catches a mapper who stopped,
    not one who skimmed.
  * `extent` is the map's own claim about how much of the corpus it read. Nothing verifies
    that the claim is ambitious enough; a map declaring one page of a four-hundred-page book
    covers it trivially. What the field buys is that the claim is *written down* and can be
    argued with.

Usage: check-locators.py <corpus-map.json> <corpus.txt> [--marker-re RE] [--page-re RE]
Exit 0 only if every check that ran passed and at least one proved something; 1 if any
check failed or declined to prove what it claims; 2 on a usage error.
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


def extent_text(corpus, index, first, last):
    """The slice of the corpus between the marker for `first` and the one after `last`.

    An absence is claimed over what the map says it read, not over the whole volume. The
    distinction is load-bearing here: "doubling" does not occur in Hoyle's backgammon
    chapter and does occur elsewhere in the same book, so a whole-volume search would
    refuse a true absence and a mapper would learn to write vaguer terms.
    """
    start = next((offset for offset, number in index if number == first), None)
    if start is None:
        return None
    end = next((offset for offset, number in index if offset > start and number > last), len(corpus))
    return corpus[start:end]


class Result:
    """One check's verdict. `skip` never becomes `ok`; it fails the run if it had work."""

    def __init__(self, status, summary, details=None, had_subject=True):
        self.status = status  # "ok" | "fail" | "skip"
        self.summary = summary
        self.details = details or []
        self.had_subject = had_subject

    @property
    def fatal(self):
        return self.status == "fail" or (self.status == "skip" and self.had_subject)


def ok(summary, details=None):
    return Result("ok", summary, details)


def fail(details, summary):
    return Result("fail", summary, details)


def skip(summary, had_subject=True):
    return Result("skip", "NOT VERIFIED -- " + summary, had_subject=had_subject)


def bounds_of(entry):
    """The authored examples in `ambiguity.bounds` (0031), each a text and a locator of its own."""
    ambiguity = entry.get("ambiguity")
    bounds = ambiguity.get("bounds") if isinstance(ambiguity, dict) else None
    listed = bounds.get("examples") if isinstance(bounds, dict) else None
    return [e for e in listed if isinstance(e, dict)] if isinstance(listed, list) else []


def check_extent_bounds(document, located):
    """No `scope: in` entry's verified quote lies outside the declared page range (#269).

    `extent` in check-map.py places an entry's **citation** inside the range; this places its
    **quote**, which is the other thing a page extent bounds and the half no citation carries. A
    map can cite fewer pages than it declares -- `hoyle-backgammon` cites 271-278 inside a
    declared 271-280 -- and then narrowing the declaration moves no citation at all, while the
    text the map quotes still runs past the new end.

    0024 already made exactly this statement about the one end a heading can stop: an in-scope
    quote at or after `endsBefore` is not inside the slice, and `check-locators-pdf-text.py`'s
    `extent-end` refuses it. Both ends of a range are the same fact, and this is it without a
    heading.

    A `scope: out` entry may quote beyond the extent, for 0020's reason and in the summary's
    words: recording what lies beyond the slice is what an out-of-scope entry is for. A quote
    that *runs across* the end is outside it, as it is for `extent-end`: the pages the quote
    touches are the pages it is read on.

    `located` is {id: (entry, pages touched)} for every entry whose evidence was found, filled
    by `check_locators` above, so a quote counts here exactly where it counted for `coverage`.
    """
    extent = document.get("extent")
    if not isinstance(extent, dict) or extent.get("unit") != "page":
        return skip("the map declares no page extent, so there is no range for a quote to lie "
                    "outside; `coverage` is where an undeclared extent fails", had_subject=False)
    first, last = extent.get("from"), extent.get("to")
    if not isinstance(first, int) or not isinstance(last, int) or last < first:
        return skip(f"extent names the range {first!r}..{last!r}, which is not a page range")
    if not located:
        return skip("no entry's evidence was located, so no quote was placed inside the range")
    bad, beyond, inside = [], [], 0
    for name, (entry, pages) in located.items():
        outside = sorted(p for p in pages if not first <= p <= last)
        if not outside:
            inside += 1
            continue
        where = " or ".join(f"p. {p}" for p in outside)
        if entry.get("scope") == "out":
            beyond.append(f"{name} ({where})")
        else:
            bad.append(f"  X  {name}: evidence lies on {where}, outside the declared extent "
                       f"(pages {first}-{last}); an in-scope rule is quoted inside what the map "
                       f"claims to have read")
    aside = (f"; {len(beyond)} out-of-scope quote{'' if len(beyond) == 1 else 's'} beyond the "
             f"extent, neither passed nor failed: {', '.join(beyond)}") if beyond else ""
    if bad:
        return fail(bad, f"a quote lies outside the declared extent (pages {first}-{last})")
    return ok(f"all {inside} located in-scope quotes lie inside the declared extent "
              f"(pages {first}-{last}){aside}")


def check_locators(entries, corpus, index, page_re, reached, located=None):
    """Each entry's cited page against the page its evidence sits on.

    A derived entry (0012) is not located: no sentence states its fact, so it carries no
    locator and no evidence, and its sources are located as ordinary entries. It is counted
    and named in the summary rather than silently dropped, so "all N verified" says how many
    entries it left out and why. That it really cites nothing is `check-map.py --only derived`.
    """
    derived = [e.get("id", "?") for e in entries if "derivedFrom" in e]
    entries = [e for e in entries if "derivedFrom" not in e]
    aside = (f"; {len(derived)} derived entr{'y' if len(derived) == 1 else 'ies'} "
             f"({', '.join(derived)}) not located, because a derived entry cites nothing"
             ) if derived else ""
    bad, unlocatable, uncited, checked = [], 0, 0, 0
    for entry in entries:
        name = entry.get("id", "?")
        citation = entry.get("locator", {}).get("citation", "")
        claimed = re.search(page_re, citation)
        if not claimed:
            uncited += 1
            bad.append(f"  X  {name}: citation {citation!r} names no page, so nothing can be "
                       f"compared. An entry for a rule the corpus does not contain cites the "
                       f"passage the rule would be in and carries `absentFrom` (0009); it does "
                       f"not cite nothing.")
            continue
        span, coverage = probe(normalise(entry.get("evidence", "")), corpus)
        if span is None:
            unlocatable += 1
            bad.append(f"  ?  {name}: evidence not found verbatim; cannot check")
            continue
        checked += 1
        actual = pages_spanned(span, index)
        reached.update(actual)
        if located is not None:
            located[name] = (entry, actual)
        if int(claimed.group(1)) not in actual:
            partial = "" if coverage > 0.95 else f" (matched {coverage:.0%} of the evidence)"
            found = " or ".join(f"p. {p}" for p in sorted(actual))
            bad.append(f"  X  {name}: cited p. {claimed.group(1)}, evidence is on {found}{partial}")
        # An authored example that bounds an open term quotes the corpus and cites it, exactly as
        # `evidence` does (0031), so it is located by the same probe and held to the same page --
        # a bound whose words are not where it says they are would admit or refuse an owner's
        # ruling on a quotation of nothing. Its pages are not added to `reached`: coverage asks
        # which pages an entry's own evidence reached, and an example quoted to bound a term is
        # not a verdict on the page it sits on.
        for index_of, example in enumerate(bounds_of(entry), start=1):
            where = f"{name}: bounds.examples[{index_of}]"
            cited = re.search(page_re, (example.get("locator") or {}).get("citation", ""))
            if not cited:
                bad.append(f"  X  {where}: citation names no page, so nothing can be compared")
                continue
            at, _ = probe(normalise(example.get("text", "")), corpus)
            if at is None:
                bad.append(f"  ?  {where}: the example's text is not in the corpus verbatim; cannot check")
            elif int(cited.group(1)) not in pages_spanned(at, index):
                on = " or ".join(f"p. {p}" for p in sorted(pages_spanned(at, index)))
                bad.append(f"  X  {where}: cited p. {cited.group(1)}, the example is on {on}")
    if not entries:
        return skip("the map has no entries to locate")
    if checked == 0:
        return skip(
            "no entry's evidence appears verbatim in the corpus, so no citation was checked. "
            "`evidence` must carry a quoted span for a locator to be verifiable at all",
        )
    if bad:
        return fail(bad, f"{checked} of {len(entries)} citations verified; {unlocatable} "
                         f"unlocatable, {uncited} citing no page{aside}")
    return ok(f"all {checked} citations verified against the page their evidence sits on{aside}")


def check_absence(entries, extent):
    """Every term an `absentFrom` entry says it searched for is in fact not there."""
    carriers = [e for e in entries if isinstance(e.get("absentFrom"), dict)]
    if not carriers:
        return Result("skip", "NOT VERIFIED -- no entry carries `absentFrom`, so no absence was "
                              "claimed and none was searched for", had_subject=False)
    if extent is None:
        return skip("the map declares no `extent`, so there is no passage an absence could be "
                    "claimed over. A search with no bounds is not a search")
    haystack = extent.lower()
    bad, searched = [], 0
    for entry in carriers:
        name = entry.get("id", "?")
        terms = entry["absentFrom"].get("searched") or []
        for term in terms:
            if not isinstance(term, str) or not term.strip():
                continue
            searched += 1
            at = haystack.find(normalise(term).lower())
            if at != -1:
                context = extent[max(0, at - 60):at + 80]
                bad.append(f"  X  {name}: claims the corpus does not state this rule and names "
                           f"{term!r} among the words it would use -- and the extent contains "
                           f"it: ...{context}...")
    if not searched:
        return skip("every `absentFrom` names an empty `searched` list, so nothing was looked for")
    return fail(bad, f"an absence is contradicted by the corpus") if bad else ok(
        f"{searched} terms across {len(carriers)} absent-rule "
        f"entr{'y' if len(carriers) == 1 else 'ies'} occur nowhere in the declared extent")


def check_coverage(document, reached):
    """Every page of the declared extent is reached by some entry's verified evidence."""
    extent = document.get("extent")
    if not isinstance(extent, dict):
        return skip("the map declares no `extent`, so what it claims to have read is unstated "
                    "and 'no entry cites this section' cannot be a fact. Add `extent` "
                    "(0009): {\"unit\": \"page\", \"from\": N, \"to\": M}")
    if extent.get("unit") != "page":
        return skip(f"extent.unit is {extent.get('unit')!r}; this checker reads page markers and "
                    f"can prove nothing about another unit")
    first, last = extent.get("from"), extent.get("to")
    if not isinstance(first, int) or not isinstance(last, int) or last < first:
        return skip(f"extent names the range {first!r}..{last!r}, which is not a page range")
    missing = [page for page in range(first, last + 1) if page not in reached]
    if missing:
        return fail(
            [f"  X  p. {page}: inside the declared extent and reached by no entry's verified "
             f"evidence" for page in missing],
            f"{len(missing)} of {last - first + 1} pages in the extent are reached by no entry",
        )
    return ok(f"all {last - first + 1} pages of the declared extent ({first}-{last}) are reached "
              f"by some entry's verified evidence")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("map_path")
    parser.add_argument("corpus_path")
    parser.add_argument("--marker-re", default=DEFAULT_MARKER)
    parser.add_argument("--page-re", default=DEFAULT_PAGE)
    args = parser.parse_args(argv)

    try:
        with open(args.map_path, encoding="utf-8") as handle:
            document = json.load(handle)
        corpus = normalise(open(args.corpus_path, encoding="utf-8").read())
    except (OSError, ValueError) as error:
        print(f"cannot read {args.map_path} or {args.corpus_path}: {error}", file=sys.stderr)
        return 2

    entries = [e for e in document.get("entries") or [] if isinstance(e, dict)]
    index = page_index(corpus, args.marker_re)
    if not index:
        print("no page markers found; nothing to check", file=sys.stderr)
        return 2

    extent = None
    declared = document.get("extent")
    if isinstance(declared, dict) and isinstance(declared.get("from"), int) \
            and isinstance(declared.get("to"), int):
        extent = extent_text(corpus, index, declared["from"], declared["to"])

    reached, located = set(), {}
    print(f"{args.map_path} ({len(entries)} entries) against {args.corpus_path}")
    results = [
        ("locators", check_locators(entries, corpus, index, args.page_re, reached, located)),
        ("absence", check_absence(entries, extent)),
        ("coverage", check_coverage(document, reached)),
        ("extent-bounds", check_extent_bounds(document, located)),
    ]
    if isinstance(declared, dict) and "endsBefore" in declared:
        # 0024: this checker collapses the corpus's lines, so it cannot find a heading line, and
        # its absence and coverage above ran over the whole last page. Refuse rather than pass.
        results.append(("extent-end", skip(
            f"the extent ends before the heading {declared.get('endsBefore')!r}, and this checker "
            f"reads whitespace-collapsed text with no lines to find it in; absence and coverage "
            f"above ran over the whole of p. {declared.get('to')}. The page-marked PDF text checker "
            f"reads endsBefore")))
    passed = failed = skipped = fatal = 0
    for name, result in results:
        print(f"[{result.status}] {name}: {result.summary}")
        for line in result.details:
            print(line)
        if result.status == "fail":
            failed += 1
        elif result.status == "skip":
            skipped += 1
        else:
            passed += 1
        if result.fatal:
            fatal += 1

    print(f"\n{passed} ok, {failed} failed, {skipped} not verified")
    if fatal:
        return 1
    if not passed:
        print("nothing was actually checked; this is not a pass", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
