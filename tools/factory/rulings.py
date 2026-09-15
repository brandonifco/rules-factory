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
  * `rulings` without `declines`, `declines: []` without `rulings`, and an empty `rulings`.

**A licensed `local-copy` corpus's question is never quoted (0027, amended 2026-09-15).** Its words
may not be committed to an engine (0022), and the overlay, `Rulings.g.cs` and provenance.json all
are. So for such a corpus `span` is not a quotation but an object naming the part without its
text: `{"start", "end", "sha256"}`, character offsets into the question after `normalise` (every
run of whitespace one space, none at either end), and the SHA-256 of the UTF-8 of the normalised
question between them. The same coverage and overlap rules hold, on the normalised question. A
verbatim span is refused there, and an object span is refused for a committed-copy corpus, which
keeps quoting. Every committed string a ruling or decline carries (`id`, `answer`, `ruledBy`,
`record`, each test name), and the decision record's own text, is refused when it carries a run of
LEAK_WORDS or more words of any text the map holds for any entry (its `evidence`, `note`,
`ambiguity.question`, and every other string in it). `locate` computes a span object, and so does
`python3 rulings.py locate --map M --entry ID` from the part typed on stdin, so nobody writes the
text into the engine to learn its offsets. For such a corpus no message here repeats the
question's words: a gap or a mismatch is named by its offsets.

What no check here can show, and 0027 says so: that the engine divided the question where its
parts really divide (the map does not divide a question into parts, so a span is only words), that
the engine does what a ruling answers and declines what a decline names, or that the named tests
surface the ruling to a caller. The gate shows the tests exist and ran.

Standard library only, and imports nothing of the factory's: the gate's map-overlay.py imports
it from scripts/factory/ as well as generate.py.
"""
import datetime
import hashlib
import json
import os
import re
import sys

RULINGS = "rulings"
DECLINES = "declines"
KEYS = (RULINGS, DECLINES)
RULING_FIELDS = ("id", "span", "answer", "ruledBy", "ruledOn", "record", "tests")
DECLINE_FIELDS = ("span", "tests")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ANSWER_LIMIT = 300
DECISION = "rules-factory decision 0027"
# A span of a local-copy corpus's question (0027, amended 2026-09-15): offsets and a hash, no text.
HASHED_SPAN_FIELDS = ("start", "end", "sha256")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
# A committed string carrying this many consecutive words of the map's text is refused (local-copy only).
LEAK_WORDS = 15
LOCAL_COPY = "local-copy"
AMENDED = "0027, amended 2026-09-15"


def normalise(text):
    """`text` with every run of whitespace one space and none at either end: what a hashed span indexes."""
    return " ".join(text.split())


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def locate(question, text):
    """The span object naming `text` in `question`, both normalised, or None unless it occurs there
    exactly once: what a local-copy engine's overlay carries in place of a quotation."""
    normal, part = normalise(question), normalise(text)
    if not part or normal.count(part) != 1:
        return None
    start = normal.find(part)
    return {"start": start, "end": start + len(part), "sha256": _sha256(part)}


def posture(manifest, package):
    """(local_copy, problem): whether the manifest declares the corpus the package map cites
    `verification: local-copy`. Exactly one of the two is None."""
    source_id = package.get("corpus") if isinstance(package, dict) else None
    corpora = [c for c in (manifest.get("corpora") if isinstance(manifest, dict) else None) or []
               if isinstance(c, dict) and c.get("sourceId") == source_id]
    if len(corpora) != 1:
        return None, f"the package manifest declares the map's corpus {source_id!r} {len(corpora)} times, not once"
    return corpora[0].get("verification") == LOCAL_COPY, None


def label(span):
    """A span as the generated registry and the reports carry it: the quotation, or for a local-copy
    corpus `sha256:<hex> [start, end)` of the normalised question, which names the part and quotes nothing."""
    if isinstance(span, dict):
        return f"sha256:{span['sha256']} [{span['start']}, {span['end']})"
    return span


def _blank(value):
    return not isinstance(value, str) or not value.strip()


def _occurrences(text, span):
    count, start = 0, text.find(span)
    while start != -1:
        count += 1
        start = text.find(span, start + 1)
    return count


def _words(text):
    return re.findall(r"[^\W_]+", text.casefold())


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _runs(package):
    """Every run of LEAK_WORDS consecutive words in any string of any entry of the map."""
    runs = set()
    for entry in package.get("entries") or []:
        for text in _strings(entry):
            words = _words(text)
            for index in range(len(words) - LEAK_WORDS + 1):
                runs.add(tuple(words[index:index + LEAK_WORDS]))
    return runs


def _leak(text, runs):
    """The 1-based position of the first word in `text` that begins a run of the map's words, or None."""
    words = _words(text)
    for index in range(len(words) - LEAK_WORDS + 1):
        if tuple(words[index:index + LEAK_WORDS]) in runs:
            return index + 1
    return None


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


def _span(where, span, question, spans, problems, local_copy=False):
    if local_copy:
        _hashed_span(where, span, question, spans, problems)
        return
    if isinstance(span, dict):
        problems.append(f"{where}: `span` is offsets and a hash, and the corpus is not a local-copy corpus; quote the "
                        "part of `ambiguity.question` it concerns, verbatim (0027)")
        return
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


def _hashed_span(where, span, question, spans, problems):
    """A local-copy corpus's span, {start, end, sha256} of the normalised question. No message repeats its words."""
    normal = normalise(question)
    if isinstance(span, str):
        located = locate(question, span) if span.strip() else None
        problems.append(f"{where}: `span` quotes the question, and the corpus is a licensed local-copy corpus, whose "
                        "words are never committed to an engine (0022). Name the part by offsets and hash instead"
                        + (f": {json.dumps(located)}" if located else " (`python3 scripts/factory/rulings.py locate`)")
                        + f" ({AMENDED})")
        return
    if not isinstance(span, dict) or set(span) != set(HASHED_SPAN_FIELDS):
        problems.append(f"{where}: `span` must be an object of exactly {', '.join(HASHED_SPAN_FIELDS)}: character "
                        "offsets into the whitespace-normalised question and the SHA-256 of the text between them "
                        f"({AMENDED})")
        return
    start, end, digest = span["start"], span["end"], span["sha256"]
    rewritten = ("If the map rewrote the question, the ruling no longer names a part of it: withdraw it, or identify "
                 "the part again only once the owner has confirmed the ruling answers the question as it now reads (0027)")
    if not isinstance(digest, str) or not SHA256.match(digest):
        problems.append(f"{where}: span `sha256` is not 64 lower-case hexadecimal digits")
        return
    if any(isinstance(n, bool) or not isinstance(n, int) for n in (start, end)) or not 0 <= start < end <= len(normal):
        problems.append(f"{where}: span offsets [{start!r}, {end!r}) are not a non-empty range inside the normalised "
                        f"question, which has {len(normal)} characters. {rewritten}")
        return
    if _sha256(normal[start:end]) != digest:
        problems.append(f"{where}: span [{start}, {end}) of the normalised question hashes to "
                        f"{_sha256(normal[start:end])}, not the recorded {digest}. {rewritten}")
        return
    if normal[start] == " " or normal[end - 1] == " ":
        problems.append(f"{where}: span [{start}, {end}) begins or ends on a space of the normalised question; "
                        "a span begins and ends on a character of the question's words")
        return
    spans.append((start, end, where))


def _leaks(where, item, runs, root, problems):
    """A local-copy corpus: refuse a committed string of a ruling or decline, or its decision record,
    carrying LEAK_WORDS consecutive words of the map's text. The message names the field, never the words."""
    fields = [(f"`{field}`", item[field]) for field in ("id", "answer", "ruledBy", "record")
              if isinstance(item.get(field), str)]
    fields += [(f"test {position + 1}", test) for position, test in enumerate(item.get("tests") or [])
               if isinstance(test, str)]
    record = item.get("record")
    if root is not None and isinstance(record, str) and not _blank(record) and not _record_problem(record, root):
        with open(os.path.join(os.path.realpath(root), *record.split("/")), encoding="utf-8", errors="replace") as handle:
            fields.append((f"its decision record {record}", handle.read()))
    for name, text in fields:
        position = _leak(text, runs)
        if position is not None:
            problems.append(f"{where}: {name} carries {LEAK_WORDS} or more consecutive words of the map's text, from "
                            f"its word {position}. The corpus is a licensed local-copy corpus, and nothing committed to "
                            f"the engine quotes it (0022): say it in the owner's own words ({AMENDED})")


def problems(package, overlay, root=None, local_copy=None):
    """Every way `overlay`'s rulings and declines break 0027 against `package`; [] when none.

    `root` is the engine directory, for the check that each `record` is a file; None skips only
    that check. `local_copy` is whether the map's corpus is a `local-copy` corpus (`posture`): True
    holds spans to offsets and a hash and refuses committed text carrying the map's words, False
    holds them to verbatim quotation, and None (not known) refuses any ruling or decline, since
    which rule applies is unknown. Items that are not objects, and keys naming no entry, are merge
    rules 1 and 2's to report, and are skipped here."""
    if not isinstance(overlay, dict):
        return []
    if local_copy is None:
        if any(isinstance(item, dict) and any(key in item for key in KEYS) for item in overlay.values()):
            return ["the overlay carries rulings or declines, and the corpus's verification posture was not given, "
                    "so whether a span may quote the question is unknown (a local-copy corpus's may not, "
                    f"{AMENDED}); pass the package manifest"]
        return []
    entries = {e.get("id"): e for e in (package.get("entries") or []) if isinstance(e, dict)}
    runs = _runs(package) if local_copy else set()
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
                extra = sorted(set(ruling) - set(RULING_FIELDS))
                if extra:
                    found.append(f"{where} carries {', '.join(extra)}, which is not a field of a ruling "
                                 f"({', '.join(RULING_FIELDS)})")
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
                    _span(where, ruling["span"], question, spans, found, local_copy)
                if "tests" in ruling:
                    _tests(where, ruling["tests"], named, found)
                if local_copy:
                    _leaks(where, ruling, runs, root, found)

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
                    _span(where, decline["span"], question, spans, found, local_copy)
                if "tests" in decline:
                    _tests(where, decline["tests"], named, found)
                if local_copy:
                    _leaks(where, decline, runs, root, found)
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
            uncovered = _uncovered(normalise(question) if local_copy else question, spans)
            if uncovered:
                start, end, gap = uncovered
                shown = (f"characters [{start}, {end}) of the normalised question" if local_copy
                         else f"{(gap if len(gap) <= 160 else gap[:157] + '...')!r} of the question")
                found.append(f"{entry_id}: the rulings' and declines' spans leave {shown} "
                             "unquoted. Every part of the question is either ruled or declined, so together the spans "
                             "cover all of it (whitespace between them aside); a part of the question the map added "
                             "since is one the owner has not ruled on and the engine has not declared a decline of")
    return found


def _uncovered(question, spans):
    """(start, end, text) of the first stretch of `question` outside every span that is not
    whitespace, with the whitespace at its ends left out; None when there is none."""
    position = 0
    for start, end, _ in spans + [(len(question), len(question), None)]:
        stretch = question[position:start]
        if stretch.strip():
            lead = len(stretch) - len(stretch.lstrip())
            gap = stretch.strip()
            return position + lead, position + lead + len(gap), gap
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
    for entry_id, item in (overlay.items() if isinstance(overlay, dict) else ()):
        if isinstance(item, dict) and item.get(RULINGS) and item.get(DECLINES) == []:
            lines.append(f"{entry_id}: declared fully ruled (`declines: []`); it declines no part of its question")
    return lines


def main(argv=None):
    """`locate --map M --entry ID`: the span object for the part of the question on stdin (a local-copy engine)."""
    import argparse
    parser = argparse.ArgumentParser(description="name part of an entry's question by offsets and hash (0027)")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("locate", help="print the span object for the part of the question read from stdin")
    command.add_argument("--map", required=True, help="the package map, corpus-map.json")
    command.add_argument("--entry", required=True, help="the entry whose ambiguity.question the part is of")
    args = parser.parse_args(argv)
    with open(args.map, encoding="utf-8") as handle:
        package = json.load(handle)
    entry = next((e for e in package.get("entries") or [] if isinstance(e, dict) and e.get("id") == args.entry), None)
    ambiguity = (entry or {}).get("ambiguity")
    question = ambiguity.get("question") if isinstance(ambiguity, dict) else None
    if not isinstance(question, str):
        print(f"error: the map has no entry {args.entry!r} with an ambiguity.question", file=sys.stderr)
        return 1
    located = locate(question, sys.stdin.read())
    if located is None:
        print("error: that text is not in the question exactly once, whitespace aside", file=sys.stderr)
        return 1
    print(json.dumps(located))
    return 0


if __name__ == "__main__":
    sys.exit(main())
