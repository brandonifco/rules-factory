#!/usr/bin/env python3
"""Check that each map entry's *rule* citation matches where its evidence actually sits.

The third citation grammar this repository checks, and the second structural one. `Rule
6(a)(1)(A)` names a rule, a subsection, a paragraph and a subparagraph, and the question is the
one `examples/faa-part-107/check-locators-section.py` asks of `§ 107.29(a)(2)`: **is the quoted
passage inside the element the citation names?**

The principle generalises and the implementation does not, which is why this is a third file and
not a flag on a second. What makes it a *short* file is the corpus. The eCFR's XML carries no
designation path, so that checker rebuilds the CFR's designator tree by form -- `(a)`, `(1)`,
`(i)` -- and spends most of its length on the cases where the form is ambiguous, on wrappers that
may or may not continue the paragraph they are printed after, and on tables. The Office of Law
Revision Counsel's USLM markup carries the path outright:

    <subparagraph identifier="/us/usc/t28a/courtRules/Civil/rule6/a/1/A">

So there is no tree to rebuild, nothing to infer, and no passage this grammar has no address for:
every character of a `<courtRule>` is inside that rule's element, so the coarsest citation any
quote can need is the rule itself. `extent.unreachable` is therefore neither read nor needed
here, and a run says so rather than leaving its absence to be read as an omission.

Three properties are the section checker's, deliberately, and each makes this stricter rather
than looser:

  * **Containment, not proximity.** A quote is inside the cited element or it is not.
  * **Every occurrence, not the first.** A quote that appears N times must have all N
    occurrences inside the citation. This corpus repeats sentences: *"21 days after being served
    with"* opens both Rule 81(c)(2)(A) and Rule 81(c)(2)(B), and *"or"* is not what tells them
    apart.
  * **Exact, not longest-prefix.** A quote either appears verbatim or the entry fails. ` ... `
    splits it into fragments, each of which must appear in order, and an ellipsis may skip whole
    units and never words inside one
    ([0037](../../docs/decisions/0037-an-ellipsis-skips-whole-paragraphs-and-never-words-inside-one.md)).

It does not check that the evidence is the *right* passage for the entry, only that the citation
names where it is. It cannot check an entry whose evidence is not a quote: such an entry is
reported and **fails the run**. It never reports ok for a citation it did not check.

Usage: check-locators-uslm.py <corpus-map.json> <corpus.xml>
       check-locators-uslm.py <corpus-map.json> <sourceId>=<corpus.xml> ...
Exit 0 if every entry was checked and agreed, 1 otherwise, 2 on a usage error.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://xml.house.gov/schemas/uslm/1.0}"
#: The identifier prefix every unit of this corpus carries. A document whose elements are
#: identified under another prefix is not the one this grammar reads, and is refused rather than
#: enumerated into an index that would verify nothing.
PREFIX = "/us/usc/t28a/courtRules/Civil/rule"
ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*")

#: `Rule 6`, as an item of `extent.sections` and nothing else -- no subsection, no range.
EXTENT_RULE = re.compile(r"^Rule\s+(\d+(?:\.\d+)?)$")
#: The rule a citation opens with. The first one, which is the only one this grammar reads: a
#: citation names paragraphs of one rule, and `Rule 12(b)(6) or 12(c)` in a *quotation* is the
#: corpus pointing, not a locator.
CITE_RULE = re.compile(r"\bRule\s+(\d+(?:\.\d+)?)(?![\d.])")
CITE_GROUP = re.compile(r"\(([A-Za-z0-9]{1,4})\)")


class Refused(Exception):
    """A corpus this grammar cannot index."""


def normalise(text):
    """Collapse whitespace, so a quote that wraps lines matches the corpus."""
    return re.sub(r"\s+", " ", text).strip()


def path_of(identifier):
    """`Rule 6(a)(1)(A)` as the tuple `("6", "a", "1", "A")`, or None for another document."""
    if not isinstance(identifier, str) or not identifier.startswith(PREFIX):
        return None
    return tuple(identifier[len(PREFIX):].split("/"))


def corpus_index(path):
    """(flat text, [(start, end, path)]) for one committed slice.

    The flat text is every text node in document order, whitespace-collapsed, with a single space
    between adjacent nodes -- which is what makes a quote of *"(A) exclude the day of the event"*
    findable across the `<num>`/`<content>` boundary the markup puts inside it.

    A span covers the text an identified element contributes **directly**: its `<num>`, its
    `<heading>`, its `<chapeau>`, its `<content>`, and nothing that belongs to an identified
    descendant. That is the eCFR checker's shape and it is the shape containment needs -- there,
    a `<P>` cannot contain a `<P>`, so one span per paragraph is already the innermost owner;
    here, elements nest, and a span per element *including* its descendants would make every
    quote sit in four elements at once and `Rule 6` true of all of them. The innermost owner is
    recorded and the ancestors are recovered by prefix, which is what `matches` does.

    An element may own two spans, one before its first identified child and one after its last.
    Nothing reads a span count, so that is left as it falls rather than merged across a gap that
    is another unit's words.
    """
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise Refused(f"cannot parse {path} as USLM XML: {error}")
    pieces = []

    def walk(element, owner):
        here = path_of(element.get("identifier"))
        owner = here if here is not None else owner
        if element.text and element.text.strip():
            pieces.append((normalise(element.text) + " ", owner))
        for child in element:
            walk(child, owner)
            if child.tail and child.tail.strip():
                pieces.append((normalise(child.tail) + " ", owner))

    walk(root, None)
    corpus, spans, cursor = [], [], 0
    for text, owner in pieces:
        start = cursor
        corpus.append(text)
        cursor += len(text)
        if owner is None:
            continue
        if spans and spans[-1][2] == owner and spans[-1][1] == start:
            spans[-1] = (spans[-1][0], cursor, owner)
        else:
            spans.append((start, cursor, owner))
    if not spans:
        raise Refused(f"{path} holds no element identified under {PREFIX}; it is not the "
                      f"court-rule slice this grammar reads")
    return "".join(corpus), spans


def cited_paths(citation):
    """The designation-path prefixes a citation names, or None for one outside this grammar.

    The forms the map uses:
      `Rule 6`                     the whole rule
      `Rule 6(a)`                  one subsection and everything under it
      `Rule 6(a)(1)(A)`            one subparagraph
      `Rule 6(a)(1)(A), (a)(1)(B)` a list, **each item read against the rule**
      `Rule 12(b)(1)-(7)`          a range at the deepest level, the stem stated in the item

    Each item states its own path from the rule down, which is the section checker's rule for
    `§ 107.29(a)(2), (b)` and is kept here for the reason it was chosen there: an item that
    inherits a stem from the item before it reads differently depending on what precedes it, and
    a citation has to mean one thing on its own.
    """
    rule = CITE_RULE.search(citation)
    if not rule:
        return None
    number = rule.group(1)
    tail = citation[rule.end():]
    if not tail.strip():
        return [(number,)]
    prefixes = []
    for item in tail.split(","):
        if not item.strip():
            return None
        groups = CITE_GROUP.findall(item)
        if not groups:
            return None
        if "-" in item or "\u2013" in item:
            head, _, rest = item.partition("-") if "-" in item else item.partition("\u2013")
            lead, last = CITE_GROUP.findall(head), CITE_GROUP.findall(rest)
            if len(last) != 1 or not lead:
                return None
            for token in span_of(lead[-1], last[0]):
                prefixes.append((number,) + tuple(lead[:-1]) + (token,))
            continue
        prefixes.append((number,) + tuple(groups))
    return prefixes or None


def span_of(lo, hi):
    """The designators from lo to hi inclusive, for a range like (b)(1)-(7) or (2)-(5)."""
    if lo.isdigit() and hi.isdigit():
        return [str(n) for n in range(int(lo), int(hi) + 1)]
    if len(lo) == 1 and len(hi) == 1 and lo.isalpha() and hi.isalpha():
        return [chr(c) for c in range(ord(lo), ord(hi) + 1)]
    return [lo, hi]


def matches(prefix, path):
    """True when `prefix` names `path` or an ancestor of it."""
    return len(prefix) <= len(path) and tuple(path[:len(prefix)]) == tuple(prefix)


def occurrences(fragment, corpus):
    at, found = corpus.find(fragment), []
    while at != -1:
        found.append((at, at + len(fragment)))
        at = corpus.find(fragment, at + 1)
    return found


def at_unit_edge(position, spans, which):
    """Whether `position` falls on the opening or closing edge of some identified element.

    0037's rule, asked of this grammar's units: an ellipsis may skip whole units and may never
    drop words from inside one, so the text before each ellipsis ends where a unit ends and the
    text after it begins where one begins. The quote's own two ends are exempt -- a span may be
    shortened at either end, and never in the middle.
    """
    for start, end, _ in spans:
        if which == "start" and position == start:
            return True
        if which == "end" and position == end:
            return True
    return False


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


def designation(path):
    """`("6", "a", "1", "A")` written the way the corpus and the map write it."""
    return "Rule " + path[0] + "".join(f"({token})" for token in path[1:])


def check(entry, corpus, spans, reached=None, quoted=None):
    """(verdict, message) where verdict is 'ok', 'bad' or 'unchecked'.

    On 'ok', the rule of every element the evidence touched is added to `reached`, and every
    occurrence of every fragment to `quoted` -- the spans the quoted fraction is the union of.
    """
    citation = entry.get("locator", {}).get("citation", "")
    prefixes = cited_paths(citation)
    if prefixes is None:
        return "unchecked", f"citation {citation!r} is outside the grammar this check reads"

    evidence = normalise(entry.get("evidence", ""))
    fragments = [f for f in ELLIPSIS.split(evidence) if f]
    if not fragments:
        return "unchecked", "evidence is empty"

    seen, cursor, rules, found = 0, 0, set(), []
    for index, fragment in enumerate(fragments):
        hits = occurrences(fragment, corpus)
        if not hits:
            got = longest_prefix(fragment, corpus)
            return "unchecked", (f"evidence fragment not found verbatim "
                                 f"({got:.0%} of it is in the corpus): {fragment[:70]!r}")
        ordered = [h for h in hits if h[0] >= cursor]
        if not ordered:
            return "bad", f"evidence fragments are out of corpus order: {fragment[:70]!r}"
        here = ordered[0]
        if index > 0 and not at_unit_edge(here[0], spans, "start"):
            return "bad", (f"cited {citation}, and the ellipsis before {fragment[:40]!r} resumes "
                           f"inside a unit rather than at the start of one: an ellipsis may skip "
                           f"whole units and never words within one, or the words it drops are "
                           f"exactly the ones nothing then checks")
        if index < len(fragments) - 1 and not at_unit_edge(here[1], spans, "end"):
            return "bad", (f"cited {citation}, and the ellipsis after {fragment[-40:]!r} opens "
                           f"inside a unit rather than at the end of one: an ellipsis may skip "
                           f"whole units and never words within one, or the words it drops are "
                           f"exactly the ones nothing then checks")
        seen += len(hits)
        found.extend(hits)
        for hit in hits:
            paths = touched(hit, spans)
            if not paths:
                return "bad", (f"cited {citation}, and this occurrence of {fragment[:40]!r} sits "
                               f"in no identified element of the corpus")
            for path in paths:
                rules.add(path[0])
                if not any(matches(p, path) for p in prefixes):
                    return "bad", (f"cited {citation}, evidence also sits in "
                                   f"{designation(path)} ({len(hits)} occurrence(s) of this "
                                   f"fragment)")
        cursor = ordered[0][1]
    if reached is not None:
        reached.update(rules)
    if quoted is not None:
        quoted.extend(found)
    return "ok", f"{len(fragments)} fragment(s), {seen} occurrence(s), all inside {citation}"


def merged(spans):
    """The union of `spans` as disjoint (start, end) pairs in order."""
    union = []
    for start, end in sorted(spans):
        if end <= start:
            continue
        if union and start <= union[-1][1]:
            union[-1][1] = max(union[-1][1], end)
        else:
            union.append([start, end])
    return [(start, end) for start, end in union]


def quoted_of(region, spans):
    """(quoted characters, characters in `region`) for the union of `spans` inside it.

    The third grammar's copy of the measure
    [0055](../../docs/decisions/0055-coverage-reports-how-much-of-the-extent-is-quoted-and-a-map-declares-the-floor.md)
    defines: a character quoted twice was read once, so the union and not the sum.
    """
    size = sum(end - start for start, end in region)
    inside = merged([(max(start, low), min(end, high))
                     for low, high in region for start, end in spans])
    return sum(end - start for start, end in inside), size


def declared_floor(extent):
    """`extent.quoted`, the fraction a map claims its verified evidence quotes, or None."""
    floor = extent.get("quoted") if isinstance(extent, dict) else None
    ok_type = isinstance(floor, (int, float)) and not isinstance(floor, bool)
    return floor if ok_type and 0 < floor <= 1 else None


def extent_rules(document):
    """The rule numbers a `section-designation` extent names, or [] where it names none."""
    extent = document.get("extent")
    if not isinstance(extent, dict) or extent.get("unit") != "section-designation":
        return []
    listed = extent.get("sections")
    if not isinstance(listed, list):
        return []
    matched = [EXTENT_RULE.match(s) for s in listed if isinstance(s, str)]
    return [m.group(1) for m in matched if m]


def quoted_extent(numbers, indexes, quoted):
    """(quoted characters, characters) over every corpus of the run, for the rules named."""
    total = covered = 0
    for source, (_, spans) in indexes.items():
        region = merged([(start, end) for start, end, path in spans if path[0] in numbers])
        got, size = quoted_of(region, quoted.get(source, []))
        covered += got
        total += size
    return covered, total


def coverage(document, reached, measured=None):
    """(problems, summary): every rule of the declared extent is reached by a verified quote."""
    extent = document.get("extent")
    if not isinstance(extent, dict):
        return ["  X  the map declares no `extent`, so what it claims to have read is unstated "
                "and 'no entry cites this rule' cannot be a fact (0009)"], None
    if extent.get("unit") != "section-designation":
        return [f"  X  extent.unit is {extent.get('unit')!r}; this checker reads a designation "
                f"tree and can prove nothing about another unit"], None
    listed = extent.get("sections")
    matched = [EXTENT_RULE.match(s) for s in listed if isinstance(s, str)] \
        if isinstance(listed, list) else []
    numbers = [m.group(1) for m in matched if m]
    if not numbers:
        return ["  X  extent names no rule designation this checker can read"], None
    problems = [f"  X  Rule {n}: inside the declared extent and reached by no entry's verified "
                f"evidence" for n in numbers if n not in reached]
    phrase = ""
    if measured is not None and measured[1]:
        got, size = measured
        fraction, floor = got / size, declared_floor(extent)
        if floor is None:
            phrase = (f"; verified evidence quotes {fraction:.0%} of their text; the map declares "
                      f"no floor (`extent.quoted`) to be held to")
        elif fraction < floor:
            problems.append(
                f"  X  extent.quoted: the map declares its verified evidence quotes at least "
                f"{floor:.0%} of the declared extent, and it quotes {fraction:.0%} ({got} of "
                f"{size} characters of its rules' text). A map shows the reading it claims, or "
                f"lowers the claim")
        else:
            phrase = (f"; verified evidence quotes {fraction:.0%} of their text, above the "
                      f"{floor:.0%} the map declares")
    return problems, f"all {len(numbers)} rules of the declared extent are reached{phrase}"


def check_absence(entries, corpus):
    """An `absentFrom` entry's search terms do not occur in the corpus (0009).

    The same claim `tools/check-locators.py` checks over a page range: an entry saying *the
    corpus does not state this rule* names the terms it searched for, and a term that turns up
    falsifies the entry. The extent here is the whole committed slice, which is what the map's
    `extent` names.
    """
    problems, checked = [], 0
    haystack = corpus.lower()
    for entry in entries:
        absent = entry.get("absentFrom")
        if not isinstance(absent, dict):
            continue
        checked += 1
        for term in absent.get("searched") or []:
            if isinstance(term, str) and term.lower() in haystack:
                problems.append(f"  X  {entry.get('id')}: claims the corpus does not state this "
                                f"rule, and its own search term {term!r} occurs in the extent")
    return problems, checked


USAGE = ("Usage: check-locators-uslm.py <corpus-map.json> <corpus.xml>\n"
         "       check-locators-uslm.py <corpus-map.json> <sourceId>=<corpus.xml> ...")


class Usage(Exception):
    """A command line this tool cannot read."""


def named_corpora(args):
    """`{sourceId: path}`, or `{None: path}` for the one-corpus form."""
    if len(args) == 1 and "=" not in args[0]:
        return {None: args[0]}
    named = {}
    for arg in args:
        source, sep, path = arg.partition("=")
        if not sep or not source or not path:
            raise Usage(f"{arg!r} is not <sourceId>=<corpus.xml>. With more than one corpus, "
                        f"every one names the sourceId its entries cite")
        if source in named:
            raise Usage(f"sourceId {source!r} is given twice")
        named[source] = path
    return named


def cited_sources(entries):
    """Every `locator.sourceId` the map's entries name, in the order they first appear."""
    seen = []
    for entry in entries:
        source = (entry.get("locator") or {}).get("sourceId")
        if source is not None and source not in seen:
            seen.append(source)
    return seen


def main(argv):
    if len(argv) < 3:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        wanted = named_corpora(argv[2:])
    except Usage as error:
        print(f"{error}\n{USAGE}", file=sys.stderr)
        return 2
    document = json.load(open(argv[1], encoding="utf-8"))
    entries = document["entries"]
    cited = cited_sources(entries)
    if None in wanted and len(cited) > 1:
        print(f"the map's entries cite {len(cited)} corpora ({', '.join(cited)}) and this run was "
              f"given one file naming no sourceId, so every entry would be checked against "
              f"whichever corpus that file is. Name each one: <sourceId>=<corpus.xml>",
              file=sys.stderr)
        return 2

    indexes = {}
    for source, path in wanted.items():
        try:
            indexes[source] = corpus_index(path)
        except Refused as error:
            print(f"  X  {error}")
            return 1

    label = (lambda source: "") if None in indexes else (lambda source: f"{source}: ")
    bad = unchecked = 0
    reached = set()
    quoted = {source: [] for source in indexes}
    for entry in entries:
        source = (entry.get("locator") or {}).get("sourceId")
        key = None if None in indexes else source
        index = indexes.get(key)
        if index is None:
            bad += 1
            print(f"  X  {entry['id']}: cites corpus {source!r}, which this run was not given "
                  f"(given: {', '.join(sorted(str(s) for s in wanted))})")
            continue
        corpus, spans = index
        verdict, message = check(entry, corpus, spans, reached, quoted[key])
        if verdict == "bad":
            bad += 1
            print(f"  X  {label(source)}{entry['id']}: {message}")
        elif verdict != "ok":
            unchecked += 1
            print(f"  ?  {label(source)}{entry['id']}: {message}")

    absence_problems, absences = [], 0
    for source, (corpus, _) in indexes.items():
        problems, count = check_absence(entries, corpus)
        absence_problems += problems
        absences += count

    total = len(entries)
    checked = total - unchecked
    uncovered, covered = coverage(document, reached,
                                  quoted_extent(extent_rules(document), indexes, quoted))
    for line in uncovered:
        print(line)
    for line in absence_problems:
        print(line)
    if absence_problems:
        print(f"\n{len(absence_problems)} absence claim(s) are falsified by the corpus itself")
        return 1
    if bad:
        print(f"\n{bad} of {total} entries cite a passage their evidence is not in "
              f"({unchecked} unchecked)")
        return 1
    if checked == 0:
        print("\nskip: no entry's evidence appears verbatim in the corpus, so no citation was "
              "checked. This is not a pass.", file=sys.stderr)
        return 1
    if checked < total:
        print(f"\n{checked} of {total} citations verified; {unchecked} could not be checked")
        return 1
    if uncovered:
        print(f"\nlocators ok (all {total} checked), but coverage fails: "
              f"{len(uncovered)} problem(s) with the declared extent")
        return 1
    print(f"locators ok (all {total} checked against the designation tree"
          + (f", {absences} absence claim(s)" if absences else "")
          + "); every passage of a <courtRule> is inside that rule's element, so this grammar "
            "has no unaddressed passage to declare; "
          + f"coverage ok ({covered})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
