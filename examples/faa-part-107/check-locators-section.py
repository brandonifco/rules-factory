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


def paragraphs(root):
    """Every <P> in document order with its designation path and its normalised text.

    Path is (subpart, section, *designators) -- e.g. ("B", "107.29", "a", "2"). A <P> with
    no designator (a section's lead-in) takes the path of its section.
    """
    out = []
    for subpart in root.iter("DIV6"):
        for section in subpart.iter("DIV8"):
            stack = {}  # level -> designator, for the levels currently open
            for p in section:
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
                path = (subpart.get("N"), section.get("N")) + tuple(
                    stack[k] for k in sorted(stack)
                )
                out.append((path, text, None))
    return out


def normalise(text):
    return re.sub(r"\s+", " ", text).strip()


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


CITE_SECTION = re.compile(r"§+\s*(\d+\.\d+)")
CITE_GROUP = re.compile(r"\(([A-Za-z0-9]{1,4})\)")
CITE_SUBPART = re.compile(r"\bsubpart\s+([A-Z])\b", re.I)


def cited_paths(citation):
    """The set of designation-path prefixes a citation names.

    Handles the grammar the two Part 107 maps actually use:
      `§ 107.35`                whole section
      `§ 107.51(a)`             one paragraph and everything under it
      `§ 107.29(c)(1)-(2)`      a range at the deepest level
      `§ 107.29(a)(2), (b)`     a list, each item read against the section
      `§ 107.51(c)-(d)`         a range at the first level
      `subpart D`               every section in a subpart
    Returns a list of prefixes; a paragraph matches if any prefix is a prefix of its path.
    Returns None for a citation this grammar does not cover -- reported, never assumed ok.
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
        groups = CITE_GROUP.findall(item)
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
    """
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


def check(entry, corpus, spans):
    """(verdict, message) where verdict is 'ok', 'bad' or 'unchecked'."""
    citation = entry.get("locator", {}).get("citation", "")
    prefixes = cited_paths(citation)
    if prefixes is None:
        return "unchecked", f"citation {citation!r} is outside the grammar this check reads"

    evidence = normalise(entry.get("evidence", ""))
    fragments = [f for f in ELLIPSIS.split(evidence) if f]
    if not fragments:
        return "unchecked", "evidence is empty"

    seen, cursor = 0, 0
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
                if not any(matches(p, path) for p in prefixes):
                    where = "/".join(x for x in path[1:] if x)
                    return "bad", (
                        f"cited {citation}, evidence also sits in {where} "
                        f"({len(hits)} occurrence(s) of this fragment)"
                    )
        cursor = ordered[0][1]
    return "ok", f"{len(fragments)} fragment(s), {seen} occurrence(s), all inside {citation}"


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[-2], file=sys.stderr)
        return 2
    entries = json.load(open(argv[1], encoding="utf-8"))["entries"]
    corpus, spans, refused = corpus_index(argv[2])
    for text, token in refused:
        print(f"  !  paragraph designator ({token}) is ambiguous; not indexed: {text}...")

    bad = unchecked = 0
    for entry in entries:
        verdict, message = check(entry, corpus, spans)
        if verdict == "ok":
            continue
        if verdict == "bad":
            bad += 1
            print(f"  X  {entry['id']}: {message}")
        else:
            unchecked += 1
            print(f"  ?  {entry['id']}: {message}")

    total = len(entries)
    checked = total - unchecked
    if refused:
        print(f"\n{len(refused)} paragraph(s) could not be placed in the section tree")
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
    print(f"locators ok (all {total} checked against the section tree)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
