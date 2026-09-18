"""The epistemic kind of truth (0033 §2, 0034): was the uncertainty preserved where the corpus
supports two readings, or collapsed into one?

Every other check in this package asks *is this value valid?* These ask **is this uncertainty
valid?** -- which is a success condition, not a failure to find the answer. A map that records
reading A, reading B and no authority between them has said something true about the corpus, and
the validator's job is to establish that the record holds together, never to choose.

The dangerous direction is the other one. A **premature collapse** -- a `clarity: clear` entry
whose evidence supports two readings -- passes every check in this file and every check beside
it, produces a confident engine, and leaves no doubt recorded for anyone to find. Whether a
passage supports two readings is not mechanical and nothing here pretends it is; 0034 states
where the judgement stays a judgement. What is mechanical is the **trace** a collapse leaves in
the records that already exist, and that is the whole of what these checks read.
"""
import json
import os
import re

from .diagnostics import skip, verdict
from mapcontract.entry import block, entries_of

# The fields of a blind second mapping's comparison whose disagreement is about whether the
# corpus settles the rule (0014 compares these two among others). A disagreement about
# `dependsOn` is about structure; a disagreement about `clarity` is about certainty.
CLARITY_FIELDS = ("clarity", "ambiguity")

# The adjudication record has two committed shapes and two verdict vocabularies, which is a
# finding rather than a design: `compare.py` writes per-flag resolutions carrying a one-letter
# verdict, and trial 9's record is hand-written with the verdict as the leading clause of a
# prose `ruling` and its own legend under `verdicts`. Both are read; neither is guessed at.
# In each, one verdict means *the corpus does not settle it*, and that is the one this file
# turns on.
FLAG_VERDICTS = {"R": "the reference is right",
                 "B": "the blind map is right",
                 "U": "the corpus does not settle it",
                 "N": "not a disagreement about the corpus"}
FLAG_UNSETTLED = "U"
RULING_UNSETTLED = "open"

# An entry id is a slug, so it is found in prose by its own characters and nothing adjacent.
ID_EDGE = r"[A-Za-z0-9_-]"



def find_comparison(map_path):
    """The blind second mapping's adjudication record beside the map, when there is one.

    `blind-mapping/` beside the map is where every committed one sits. A map package does not
    ship it -- the package's bytes are what passed (0015) -- so a consumer finds nothing here
    and the check says so rather than passing.

    Given a directory rather than a map, that directory is searched instead -- which is what
    `--comparison` accepts, so a caller holding the map somewhere else (the mutation laboratory
    writes it into a temporary directory) names the record's home and does not have to know which
    of the two files below is the readable one.

    Two file names, because the record has two committed shapes and they are not in the same
    file: `compare.py` writes its flags and their resolutions into `results.json`, and trial 9's
    hand-written adjudication is `resolutions.json` beside a `results.json` that carries the
    comparison and no verdicts. So the first candidate whose contents this file can actually read
    is the record; where neither can be read, the first that exists is returned, and the check
    reports that it could not read it rather than reporting nothing was there.
    """
    directory = os.path.abspath(map_path)
    directory = directory if os.path.isdir(directory) else os.path.join(
        os.path.dirname(directory) or ".", "blind-mapping")
    present = [os.path.join(directory, name) for name in ("results.json", "resolutions.json")]
    present = [path for path in present if os.path.isfile(path)]
    for path in present:
        try:
            with open(path, encoding="utf-8") as handle:
                if _adjudications(json.load(handle)) is not None:
                    return path
        except (OSError, ValueError):
            continue
    return present[0] if present else None


def _verdict_of_ruling(ruling, legend):
    """The verdict a hand-written `ruling` opens with, or None.

    The record declares its own vocabulary under `verdicts`, and a ruling states its verdict as
    its leading clause -- "A.", "B, and it is a coverage miss ...", "Neither, on the reasoning;
    ...". Longest first, so "not-a-corpus-disagreement" is not read as something shorter. A
    verdict that appears anywhere later in the prose is not read, and that is the limit.
    """
    if not isinstance(ruling, str):
        return None
    head = ruling.strip()
    for value in sorted(legend, key=len, reverse=True):
        if head.lower().startswith(value.lower()):
            return value
    return None


def _adjudications(record):
    """Every adjudicated disagreement about certainty, as (where, verdict, ids, prose).

    `verdict` is None where the record states one this cannot read -- that is a failure, not a
    thing to skip past. Returns None where the record is of no shape this knows.
    """
    if not isinstance(record, dict):
        return None
    found = []
    flags = record.get("flags")
    if isinstance(flags, list) and any(isinstance(f, dict) and "resolution" in f for f in flags):
        for position, flag in enumerate(flags):
            if not isinstance(flag, dict) or flag.get("field") not in CLARITY_FIELDS:
                continue
            resolution = flag.get("resolution") if isinstance(flag.get("resolution"), dict) else {}
            got = resolution.get("verdict")
            found.append((flag.get("key") or f"flags[{position}]",
                          got if got in FLAG_VERDICTS else None,
                          {flag.get("entry")}, resolution.get("reason") or "",
                          FLAG_UNSETTLED))
        return found
    legend = record.get("verdicts")
    if isinstance(legend, dict) and legend:
        for group in ("disagreements", "families"):
            for position, row in enumerate(record.get(group) or []):
                if not isinstance(row, dict) or row.get("field") not in CLARITY_FIELDS:
                    continue
                named = row.get("entry") if isinstance(row.get("entry"), dict) else {}
                found.append((f"{group}[{position}] {row.get('id')!r}",
                              _verdict_of_ruling(row.get("ruling"), legend),
                              set(named.values()), row.get("ruling") or "",
                              RULING_UNSETTLED if RULING_UNSETTLED in legend else None))
        return found
    return None


def check_superposition(ctx):
    """An adjudicated *the corpus does not settle it* is recorded in the map as unresolved.

    0014 makes a map be read a second time by a mapper who has not seen the first, compares the
    two field by field, and answers every disagreement from the corpus. Where that answer is
    **the corpus does not settle it**, two readings have been shown defensible by two mappers and
    adjudicated against the text: that is a valid unresolved state, established rather than
    asserted, and it belongs in the map. Nothing carried it forward. A `clear` entry whose blind
    reading was ambiguous, adjudicated unsettled and left `clear`, is a premature collapse with a
    paper trail -- the one form of collapse that is fully mechanical, because the second reading
    already exists in a committed file.

    Two rules:

      * every disagreement about `clarity` or the presence of an `ambiguity` block carries a
        verdict this can read. 0014: every disagreement must be dispositioned, and one whose
        disposition nothing can read is one nobody can be shown to have made.
      * every unsettled verdict lands somewhere the map records as `clarity: ambiguous` -- the
        flagged entry, or an entry the adjudication names by id. It lands elsewhere often and
        legitimately: `die-faces` was adjudicated unsettled and the question went to a new
        `rubber-scoring` entry, because the doubt was about a sentence inside its span. So the
        rule is that the doubt is somewhere, not that it is here.

    What it cannot do. It reads the verdict, never the reasoning: an adjudication that says
    unsettled and means something else passes, and one that names an unrelated ambiguous entry in
    its prose passes too. It sees only `clarity` and `ambiguity` disagreements, so an unsettled
    verdict about coverage or `kind` is invisible here. And it is worth nothing on a map nobody
    mapped twice: with no adjudication record beside the map there is no second reading to carry,
    and this reports NOT VERIFIED rather than ok.
    """
    record, where = ctx.get("comparison"), ctx.get("comparison_path")
    if record is None:
        return skip("no blind second mapping's adjudication record sits beside this map "
                    "(blind-mapping/results.json or blind-mapping/resolutions.json), so no "
                    "second reading of this corpus exists for a collapse to be measured against "
                    "(0014, 0034)", had_subject=False)
    adjudicated = _adjudications(record)
    if adjudicated is None:
        return skip(f"the adjudication record {os.path.basename(where)} is of no shape this "
                    f"knows: it carries neither per-flag `resolution.verdict`s nor a `verdicts` "
                    f"legend over `disagreements`, so nothing here can say how a disagreement "
                    f"about certainty was answered")

    ambiguous = {e.get("id") for e in entries_of(ctx["map"])
                 if isinstance(e, dict) and e.get("clarity") == "ambiguous"}
    ids = [e.get("id") for e in entries_of(ctx["map"])
           if isinstance(e, dict) and isinstance(e.get("id"), str)]

    # The `clarity` row and the `ambiguity` row on one entry are one disagreement recorded twice:
    # the comparator emits both from the same reading, and the records say so in as many words --
    # "Same as the clarity row." So the ids an adjudication reaches are the union over every
    # adjudication about the same entry. Otherwise the terser of the two rows, which cites the
    # other instead of repeating it, reads as a doubt that landed nowhere.
    reach = {}
    for _, _, named, prose, _ in adjudicated:
        found = {i for i in named if i} | {
            i for i in ids if re.search(rf"(?<!{ID_EDGE}){re.escape(i)}(?!{ID_EDGE})", prose)}
        for one in (i for i in named if i):
            reach.setdefault(one, set()).update(found)

    bad, unsettled = [], 0
    for place, got, named, prose, unsettled_value in adjudicated:
        if got is None:
            bad.append(f"  X  {place}: a disagreement about certainty with no verdict this can "
                       f"read. Every disagreement is dispositioned before the map is used (0014); "
                       f"one whose disposition nothing can read is one nobody can be shown to "
                       f"have made")
            continue
        if unsettled_value is None or got != unsettled_value:
            continue
        unsettled += 1
        reached = {i for i in named if i} | {
            i for i in ids if re.search(rf"(?<!{ID_EDGE}){re.escape(i)}(?!{ID_EDGE})", prose)}
        for one in (i for i in named if i):
            reached |= reach.get(one, set())
        if not (reached & ambiguous):
            bad.append(f"  X  {place}: adjudicated {got!r} -- the corpus does not settle it -- and "
                       f"no entry it names is `clarity: ambiguous` in this map "
                       f"({', '.join(sorted(i for i in reached)) or 'it names none'}). Two mappers "
                       f"read the passage differently, the corpus was asked and did not answer, and "
                       f"the map records one reading: that is a premature collapse (0034)")
    if not adjudicated:
        return skip(f"{os.path.basename(where)} records no disagreement about `clarity` or about "
                    f"the presence of an `ambiguity` block, so the two mappings agreed about where "
                    f"this corpus's certainty ends and there is nothing to carry", had_subject=False)
    return verdict(bad, f"{len(adjudicated)} adjudicated disagreement(s) about certainty, "
                        f"{unsettled} of them unsettled, each recorded in the map as ambiguous; "
                        f"{_census(ctx, adjudicated)}",
                   "an unsettled reading was adjudicated and the map records one reading")


def _census(ctx, adjudicated):
    """How many of the map's ambiguities have a second reading anything can read.

    Not a verdict. 0034 decides that the map records no competing readings of its own -- a
    `readings` field could only ever be carried by an entry that already admits its doubt, and
    is absent exactly where a collapse happens -- so the corroboration an ambiguity has is
    whatever other record holds it: a `conflict` (0007, the corpus says it twice), a `bounds`
    (0031, an authored example fixes one end of the term), a `decision` record, or an
    adjudicated disagreement. An ambiguity with none of those rests on the mapper's word, and
    this line is how many do, so that the number is on the page rather than in an argument.
    """
    named = set()
    for _, _, ids, prose, _ in adjudicated:
        named |= {i for i in ids if i}
        named |= {e.get("id") for e in entries_of(ctx["map"])
                  if isinstance(e, dict) and isinstance(e.get("id"), str)
                  and re.search(rf"(?<!{ID_EDGE}){re.escape(e['id'])}(?!{ID_EDGE})", prose)}
    total = corroborated = 0
    for entry in entries_of(ctx["map"]):
        if not isinstance(entry, dict) or entry.get("clarity") != "ambiguous":
            continue
        total += 1
        ambiguity = block(entry, "ambiguity")
        if (ambiguity.get("conflict") or ambiguity.get("bounds")
                or ambiguity.get("fate") == "decision" or entry.get("id") in named):
            corroborated += 1
    return (f"{corroborated} of {total} recorded ambiguities carry a second reading something can "
            f"read, and {total - corroborated} rest on `ambiguity.question` alone (0034)")
