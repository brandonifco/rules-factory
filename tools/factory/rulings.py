"""Owner's rulings on unresolved questions, held in the engine's overlay (decision 0027).

An entry with `ambiguity.fate: unresolved` records a question the corpus does not settle. An
engine may decline it, or its owner may rule on part of it. A ruling is the engine's, never the
map's: it sits in `corpus-map.overlay.json` beside the three fields 0015 lets an engine set, and
it never reaches the merged map. So the map keeps saying only what the corpus says, and the
package's own checker, which reads the merge, is unchanged by it.

An overlay item may carry two keys besides `status`, `implementedIn` and `tests`:

  "rulings":  [{"id", "span", "answer", "ruledBy", "ruledOn", "record", "tests"}, ...]
  "declines": [{"span", "tests"}, ...]

`span` is a quotation from the entry's `ambiguity.question`, verbatim, that names the part a
ruling answers or a decline refuses. `declines` is required beside `rulings`: it lists the parts
the engine still declines, and `declines: []` is the declaration that the question is fully
ruled. `problems` is every way an overlay breaks that shape against the package map:

  * a ruling or decline on an entry the map does not record as `fate: unresolved`, or that the
    overlay does not mark `implemented`;
  * a ruling missing a field, carrying one it does not have, or with a blank one; an `id` that is
    not `<entry id>/<slug>` or is used twice; an `answer` that is not one short line; a `ruledOn`
    that is not a YYYY-MM-DD date;
  * a `span` that is not in the current question exactly once, or that overlaps another span on
    the same entry (one part is not both ruled and declined, or ruled twice);
  * spans that together leave any of the question, whitespace aside, unquoted: every part of it is
    either ruled or declined, so a question the map has grown or rewritten is refused until the
    engine re-divides it;
  * `tests` empty, or naming a test the overlay item's own `tests` does not;
  * a `record` that is not a relative path inside the engine, or, when the engine root is known,
    is not a file there;
  * `rulings` without `declines`, `declines: []` without `rulings`, and an empty `rulings`;
  * **a ruling that contradicts a bound the map records on the same question** (decision 0031).
    Where the entry's `ambiguity` carries `bounds` -- the authored examples that fix what the open
    term does and does not reach, in a dimension that can be compared -- a ruling states the line
    it draws as `"boundary": {"dimension", "operator", "value"}`, or `null` to declare that it
    draws no line in that dimension. A stated line is evaluated at each example's value and must
    give the verdict the example states: an owner who rules that a short temporary absence is one
    of 18 months or less is refused, naming § 1.121-1(c)(4) Example 4, which says a 1-year
    sabbatical is not one. A `boundary` on a ruling whose entry carries no bounds is refused too,
    because nothing would compare it.

What no check here can show, and 0027 says so: that the engine divided the question where its
parts really divide (the map does not divide a question into parts, so a span is only words), that
the engine does what a ruling answers and declines what a decline names, or that the named tests
surface the ruling to a caller. The gate shows the tests exist and ran. 0031 adds two of its own:
that a `boundary` says the same thing as the `answer` beside it in prose, and that a
`boundary: null` is honest -- a ruling that does draw a line in the bounded dimension and declares
that it does not passes here, and review is what reads it.

Standard library only, and imports nothing of the factory's: the gate's map-overlay.py imports
it from scripts/factory/ as well as generate.py.
"""
import datetime
import os
import re

RULINGS = "rulings"
DECLINES = "declines"
KEYS = (RULINGS, DECLINES)
RULING_FIELDS = ("id", "span", "answer", "ruledBy", "ruledOn", "record", "tests")
# Required on a ruling whose entry carries `ambiguity.bounds`, and refused on one whose entry does
# not: a line drawn in a dimension nothing bounds is prose in a structured field (0031).
BOUNDARY = "boundary"
BOUNDARY_FIELDS = ("dimension", "operator", "value")
DECLINE_FIELDS = ("span", "tests")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ANSWER_LIMIT = 300
DECISION = "rules-factory decision 0027"
BOUNDS_DECISION = "rules-factory decision 0031"

# The same ISO 8601 durations, on the same scale, as tools/checkmap/bounds.py. That module is
# joined into check-map.py, which a map package ships, and this one is vendored into every engine
# and imports nothing of it, so the parser is written twice on purpose and
# tools/tests/test_check_map.py holds the two to each other over one table -- the arrangement
# tools/checkmap/extent.py and the section locator checker already have.
DURATION = re.compile(r"^P(?=\d)(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?$")


def duration_in_days(value):
    """`P1Y` as 360, `P18M` as 540, or None when the value is not a duration this compares."""
    match = DURATION.match(value) if isinstance(value, str) else None
    if not match:
        return None
    years, months, weeks, days = (int(g) if g else 0 for g in match.groups())
    return years * 360 + months * 30 + weeks * 7 + days


DIMENSIONS = {"duration": duration_in_days}
# What a boundary says: the term the ruling draws a line for applies to a value `operator` the
# line. The bound says what the corpus's own example is, so the two are compared directly.
OPERATORS = {
    "<=": lambda value, line: value <= line,
    "<": lambda value, line: value < line,
    ">=": lambda value, line: value >= line,
    ">": lambda value, line: value > line,
}


def _blank(value):
    return not isinstance(value, str) or not value.strip()


def _occurrences(text, span):
    count, start = 0, text.find(span)
    while start != -1:
        count += 1
        start = text.find(span, start + 1)
    return count


def _record_problem(record, root):
    if "\\" in record or os.path.isabs(record) or re.match(r"^[A-Za-z]:", record):
        return "is not a relative POSIX path inside the engine"
    if any(part in ("", ".", "..") for part in record.split("/")):
        return "is not a plain relative path inside the engine (no empty, '.' or '..' segments)"
    if root is None:
        return None
    base = os.path.realpath(root)
    path = os.path.realpath(os.path.join(base, *record.split("/")))
    if not path.startswith(base + os.sep):
        return "resolves outside the engine"
    if not os.path.isfile(path):
        return "is not a file in the engine; the ruling's decision record must be committed with it"
    return None


def _tests(where, value, named, problems):
    if not isinstance(value, list) or not value:
        problems.append(f"{where} names no tests; it must name at least one of the entry's `tests`")
        return
    for test in value:
        if _blank(test):
            problems.append(f"{where} names a test that is not a non-blank string: {test!r}")
        elif test not in named:
            problems.append(f"{where} names test {test!r}, which is not among the overlay item's `tests`; "
                            "a ruling's or decline's tests are tests the entry already names, each with its mutation")


def _span(where, span, question, spans, problems):
    if _blank(span):
        problems.append(f"{where} has no `span`: quote the part of `ambiguity.question` it concerns, verbatim")
        return
    count = _occurrences(question, span)
    if count == 0:
        problems.append(f"{where}: span {span!r} is not in the entry's current `ambiguity.question`. If the map "
                        "rewrote the question, the ruling no longer names a part of it: withdraw it, or quote the "
                        "rewritten question only once the owner has confirmed the ruling answers it (0027)")
    elif count > 1:
        problems.append(f"{where}: span {span!r} occurs {count} times in `ambiguity.question`; quote enough to "
                        "name one place")
    else:
        start = question.find(span)
        spans.append((start, start + len(span), where))


def _bounds_of(entry):
    """The entry's `ambiguity.bounds` block, or None where it has none (0031)."""
    ambiguity = entry.get("ambiguity") if isinstance(entry.get("ambiguity"), dict) else {}
    bounds = ambiguity.get("bounds")
    return bounds if isinstance(bounds, dict) else None


def _quote(text):
    """The bound's words, whitespace collapsed and nothing else.

    Not shortened. The sentence that states the verdict is usually the last one of a worked
    example -- "Because his leave is not considered to be a short temporary absence ..." -- so a
    refusal that truncated the quote would name the authority and hide what it says.
    """
    return " ".join(str(text).split())


def _boundary(where, ruling, bounds, problems):
    """A ruling's line, against the examples the corpus itself authored (0031).

    An owner may rule that a short temporary absence is one of 18 months or less. The corpus's
    own Example 4 says a 1-year sabbatical is not one. Both are durations, so the ruling is
    evaluated at each bound's value and must give the verdict the example states; where it does
    not, the engine is refused and the bound is named. This is the check the bound exists for, and
    the reason `ambiguity.bounds` earns its place under 0005.

    `boundary: null` says the ruling draws no line in the bounded dimension -- it answers some
    other part of the question -- and nothing is compared. That is a declaration, printed by
    `describe`, and it is what review reads; it is not checked, and 0031 says so.
    """
    if BOUNDARY not in ruling:
        problems.append(f"{where}: the entry's question carries `ambiguity.bounds` in "
                        f"{bounds.get('dimension')!r}, and this ruling names no `boundary`. A ruling on a "
                        f"bounded question states the line it draws, as {{{', '.join(BOUNDARY_FIELDS)}}}, so "
                        f"it can be compared against the examples the corpus authored -- or `boundary: null` "
                        f"to declare that it draws no line in that dimension ({BOUNDS_DECISION})")
        return
    boundary = ruling[BOUNDARY]
    if boundary is None:
        return
    if not isinstance(boundary, dict):
        problems.append(f"{where}: `boundary` is neither an object of "
                        f"{{{', '.join(BOUNDARY_FIELDS)}}} nor null")
        return
    missing = [f for f in BOUNDARY_FIELDS if f not in boundary]
    extra = sorted(set(boundary) - set(BOUNDARY_FIELDS))
    if missing or extra:
        problems.append(f"{where}: `boundary` carries exactly {', '.join(BOUNDARY_FIELDS)}"
                        + (f"; it lacks {', '.join(missing)}" if missing else "")
                        + (f"; it carries {', '.join(extra)}" if extra else ""))
        if missing:
            return
    dimension = bounds.get("dimension")
    scale = DIMENSIONS.get(dimension)
    if boundary.get("dimension") != dimension:
        problems.append(f"{where}: `boundary` is in {boundary.get('dimension')!r} and the entry's bounds are "
                        f"in {dimension!r}. A line in a dimension nothing bounds is compared against nothing; "
                        f"a ruling that draws no line in the bounded dimension says `boundary: null`")
        return
    if scale is None:
        problems.append(f"{where}: the map's bounds are in {dimension!r}, which this factory cannot compare "
                        f"({', '.join(sorted(DIMENSIONS))}); the map should not have passed its own "
                        f"`check-map.py --only bounds`, and nothing here can hold the ruling to them")
        return
    operator = OPERATORS.get(boundary.get("operator"))
    if operator is None:
        problems.append(f"{where}: `boundary.operator` is {boundary.get('operator')!r}, outside "
                        f"{{{', '.join(sorted(OPERATORS))}}}; it says which side of the line the term applies on")
        return
    line = scale(boundary.get("value"))
    if line is None:
        problems.append(f"{where}: `boundary.value` is {boundary.get('value')!r}, which is not a {dimension} "
                        f"this can place on a scale, so it can be compared against nothing")
        return
    for index, example in enumerate(bounds.get("examples") or [], start=1):
        if not isinstance(example, dict):
            continue
        value = scale(example.get("value"))
        if value is None or example.get("verdict") not in ("applies", "doesNotApply"):
            problems.append(f"{where}: bounds.examples[{index}] of the map is not one this can compare "
                            f"({example.get('value')!r}, {example.get('verdict')!r})")
            continue
        applies = operator(value, line)
        if applies != (example.get("verdict") == "applies"):
            citation = (example.get("locator") or {}).get("citation", "?")
            problems.append(
                f"{where}: the ruling draws the line at {boundary.get('operator')} "
                f"{boundary.get('value')}, so {bounds.get('term')!r} "
                f"{'applies' if applies else 'does not apply'} at {example.get('value')} -- and "
                f"{citation}, which the map records as a bound on this question, states that it "
                f"{'does not apply' if example.get('verdict') == 'doesNotApply' else 'applies'} there: "
                f"\"{_quote(example.get('text'))}\". The corpus's own worked example is authority the "
                f"owner's ruling cannot contradict; withdraw the ruling or draw the line where the "
                f"examples leave it open ({BOUNDS_DECISION})")


def problems(package, overlay, root=None):
    """Every way `overlay`'s rulings and declines break 0027 against `package`; [] when none.

    `root` is the engine directory, for the check that each `record` is a file; None skips only
    that check. Items that are not objects, and keys naming no entry, are merge rules 1 and 2's
    to report, and are skipped here."""
    if not isinstance(overlay, dict):
        return []
    entries = {e.get("id"): e for e in (package.get("entries") or []) if isinstance(e, dict)}
    found, ids = [], {}
    for entry_id, item in overlay.items():
        if not isinstance(item, dict) or not any(key in item for key in KEYS) or entry_id not in entries:
            continue
        entry = entries[entry_id]
        ambiguity = entry.get("ambiguity") if isinstance(entry.get("ambiguity"), dict) else {}
        fate = ambiguity.get("fate")
        if fate != "unresolved":
            found.append(f"{entry_id}: the overlay carries rulings or declines, and the map records "
                         f"{'no ambiguity' if not ambiguity else f'fate: {fate}'}; only an open question "
                         f"(`fate: unresolved`) can be ruled on or declined by part. If a map version settled "
                         f"it, the engine follows the map and withdraws the ruling in a decision record (0027)")
            continue
        if item.get("status") != "implemented":
            found.append(f"{entry_id}: the overlay carries rulings or declines, and its status is "
                         f"{item.get('status')!r}; they describe what a built entry does, so it must be `implemented`")
            continue
        question = ambiguity.get("question") if isinstance(ambiguity.get("question"), str) else ""
        named = {t.get("test") for t in item.get("tests") or [] if isinstance(t, dict)}
        spans = []

        rulings = item.get(RULINGS)
        if RULINGS in item:
            if not isinstance(rulings, list) or not rulings:
                found.append(f"{entry_id}: `rulings` must be a non-empty list; an entry with no ruling omits the key")
                rulings = []
            for position, ruling in enumerate(rulings):
                where = f"{entry_id}: ruling {position + 1}"
                if not isinstance(ruling, dict):
                    found.append(f"{where} is not an object")
                    continue
                if not _blank(ruling.get("id")):
                    where = f"{entry_id}: ruling {ruling['id']!r}"
                missing = [f for f in RULING_FIELDS if f not in ruling]
                if missing:
                    found.append(f"{where} lacks {', '.join(missing)}; a ruling names "
                                 f"{', '.join(RULING_FIELDS)} ({DECISION})")
                bounds = _bounds_of(entry)
                allowed = set(RULING_FIELDS) | ({BOUNDARY} if bounds else set())
                extra = sorted(set(ruling) - allowed)
                if extra:
                    found.append(f"{where} carries {', '.join(extra)}, which is not a field of a ruling "
                                 f"({', '.join(RULING_FIELDS)})"
                                 + (f". `{BOUNDARY}` is a field of a ruling only where the entry's question "
                                    f"carries `ambiguity.bounds` for it to be compared against "
                                    f"({BOUNDS_DECISION})" if BOUNDARY in extra else ""))
                if bounds:
                    _boundary(where, ruling, bounds, found)
                for field in ("id", "answer", "ruledBy", "record"):
                    if field in ruling and _blank(ruling[field]):
                        found.append(f"{where}: `{field}` is blank")
                rid = ruling.get("id")
                if not _blank(rid):
                    prefix, _, slug = rid.partition("/")
                    if prefix != entry_id or not SLUG.match(slug):
                        found.append(f"{where}: the id must be `{entry_id}/<slug>` (lower-case letters, digits "
                                     f"and hyphens after the slash), so it names its entry")
                    if rid in ids:
                        found.append(f"{where}: the id is used twice (also on {ids[rid]})")
                    ids[rid] = entry_id
                answer = ruling.get("answer")
                if not _blank(answer) and ("\n" in answer or len(answer) > ANSWER_LIMIT):
                    found.append(f"{where}: `answer` is the ruling stated briefly, one line of at most "
                                 f"{ANSWER_LIMIT} characters; the reasoning belongs in the decision record")
                if "ruledOn" in ruling:
                    on = ruling["ruledOn"]
                    try:
                        if not isinstance(on, str) or not DATE.match(on):
                            raise ValueError
                        datetime.date.fromisoformat(on)
                    except ValueError:
                        found.append(f"{where}: `ruledOn` is {on!r}, not a YYYY-MM-DD date")
                record = ruling.get("record")
                if not _blank(record):
                    problem = _record_problem(record, root)
                    if problem:
                        found.append(f"{where}: record {record!r} {problem}")
                if "span" in ruling:
                    _span(where, ruling["span"], question, spans, found)
                if "tests" in ruling:
                    _tests(where, ruling["tests"], named, found)

        if DECLINES in item:
            declines = item[DECLINES]
            if not isinstance(declines, list):
                found.append(f"{entry_id}: `declines` must be a list (empty to declare the question fully ruled)")
                declines = []
            if not declines and not rulings:
                found.append(f"{entry_id}: `declines: []` declares every part of the question ruled, and the item "
                             "names no ruling")
            for position, decline in enumerate(declines):
                where = f"{entry_id}: decline {position + 1}"
                if not isinstance(decline, dict):
                    found.append(f"{where} is not an object")
                    continue
                missing = [f for f in DECLINE_FIELDS if f not in decline]
                extra = sorted(set(decline) - set(DECLINE_FIELDS))
                if missing or extra:
                    found.append(f"{where} must carry exactly {', '.join(DECLINE_FIELDS)}"
                                 f"{'; it lacks ' + ', '.join(missing) if missing else ''}"
                                 f"{'; it carries ' + ', '.join(extra) if extra else ''}")
                if "span" in decline:
                    _span(where, decline["span"], question, spans, found)
                if "tests" in decline:
                    _tests(where, decline["tests"], named, found)
        elif RULINGS in item:
            found.append(f"{entry_id}: names rulings and no `declines`. List each part of the question the engine "
                         "still declines, with its span and the test that shows the decline, or write "
                         "`declines: []` to declare the whole question ruled (0027)")

        spans.sort()
        overlapping = False
        for (_, end, first), (start, _, second) in zip(spans, spans[1:]):
            if start < end:
                overlapping = True
                found.append(f"{first} and {second} quote overlapping spans of the question; one part is either "
                             "ruled once or declined, never both")
        given = len(rulings or []) + len(item.get(DECLINES) if isinstance(item.get(DECLINES), list) else [])
        if not overlapping and spans and len(spans) == given:
            uncovered = _uncovered(question, spans)
            if uncovered:
                found.append(f"{entry_id}: the rulings' and declines' spans leave {uncovered!r} of the question "
                             "unquoted. Every part of the question is either ruled or declined, so together the spans "
                             "cover all of it (whitespace between them aside); a part of the question the map added "
                             "since is one the owner has not ruled on and the engine has not declared a decline of")
    return found


def _uncovered(question, spans):
    """The first stretch of `question` outside every span that is not whitespace, or None."""
    position = 0
    for start, end, _ in spans + [(len(question), len(question), None)]:
        gap = question[position:start].strip()
        if gap:
            return gap if len(gap) <= 160 else gap[:157] + "..."
        position = max(position, end)
    return None


def collect(overlay):
    """Every ruling in `overlay`, in overlay order, each with its entry: the shape generation and
    provenance read. Assumes `problems` found nothing."""
    out = []
    if not isinstance(overlay, dict):
        return out
    for entry_id, item in overlay.items():
        if not isinstance(item, dict):
            continue
        for ruling in item.get(RULINGS) or []:
            out.append({"id": ruling["id"], "entry": entry_id, "span": ruling["span"], "answer": ruling["answer"],
                        "ruledBy": ruling["ruledBy"], "ruledOn": ruling["ruledOn"], "record": ruling["record"],
                        "tests": list(ruling["tests"])})
    return out


def describe(overlay):
    """One line per ruling, and one per entry declared fully ruled, for a gate's or produce's output."""
    lines = []
    for ruling in collect(overlay):
        lines.append(f"owner's ruling {ruling['id']} on {ruling['entry']}, not the corpus: {ruling['answer']} "
                     f"(ruled by {ruling['ruledBy']} on {ruling['ruledOn']}, {ruling['record']})")
    # A ruling on a bounded question says where it drew its line, or that it drew none (0031).
    # Both are printed: the one that was checked against the corpus's own examples, and the one
    # that declares nothing to check, which is what makes a `boundary: null` visible to a reader.
    for entry_id, item in (overlay.items() if isinstance(overlay, dict) else ()):
        if not isinstance(item, dict):
            continue
        for ruling in item.get(RULINGS) or []:
            if not isinstance(ruling, dict) or BOUNDARY not in ruling:
                continue
            boundary = ruling[BOUNDARY]
            if isinstance(boundary, dict):
                lines.append(f"{ruling.get('id')}: draws the line at {boundary.get('operator')} "
                             f"{boundary.get('value')} in {boundary.get('dimension')}, and agrees with every "
                             f"authored example {entry_id} is bounded by")
            elif boundary is None:
                lines.append(f"{ruling.get('id')}: draws no line in the dimension {entry_id}'s bounds are in, "
                             f"so no authored example was compared against it")
    for entry_id, item in (overlay.items() if isinstance(overlay, dict) else ()):
        if isinstance(item, dict) and item.get(RULINGS) and item.get(DECLINES) == []:
            lines.append(f"{entry_id}: declared fully ruled (`declines: []`); it declines no part of its question")
    return lines
