"""`ambiguity.bounds`: what an authored example fixes about a term an operative rule leaves
open (0031).

The field exists to be compared against something. 0005 admits a field when a check can read it
and say what it is read *against*; here that is an owner's ruling under 0027, which
`tools/factory/rulings.py` refuses when it contradicts a bound. That comparison is only possible
where the example's fact pattern and the ruling's line live in one dimension and one ordering, so
a bound is admitted only in a dimension this module can compare, and `DIMENSIONS` is the whole of
that. A bound in any other dimension is refused here rather than accepted as prose in a
structured field -- an ambiguity nothing can compare stays prose in `ambiguity.question`,
unchecked and admittedly so.

What this file cannot do: read the corpus. That the quoted `text` really sits at the `locator`
it names is the locator checkers' work, on the same terms as `evidence`
(`examples/faa-part-107/check-locators-section.py`, `tools/check-locators.py`).
"""
import re

from .diagnostics import skip, verdict
from mapcontract.entry import block, entries_of, label

BOUND_FIELDS = ("term", "dimension", "examples")
EXAMPLE_FIELDS = ("locator", "text", "verdict", "value")
VERDICTS = {"applies", "doesNotApply"}

# A duration is written in the ISO 8601 form the corpus's own quantities fit -- P1Y, P18M, P2M,
# P730D -- and compared in 30-day months and 12-month years, so P1Y and P12M are one value and a
# ruling cannot slip past a bound by restating the same length in other units. No time part: a
# corpus that bounds a term in hours would extend this parser and its tests, and none does.
DURATION = re.compile(r"^P(?=\d)(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?$")


def duration_in_days(value):
    """`P1Y` as 360, `P18M` as 540, or None when the value is not a duration this compares.

    `tools/factory/rulings.py` carries the same parser, because it is vendored into every engine
    and imports nothing of this checker; `tools/tests/mapvalidator/test_check_map.py` holds the two to each
    other over one table, as it already does for the section-designation expression.
    """
    match = DURATION.match(value) if isinstance(value, str) else None
    if not match:
        return None
    years, months, weeks, days = (int(g) if g else 0 for g in match.groups())
    return years * 360 + months * 30 + weeks * 7 + days


# Every dimension a bound may be stated in, with the function that puts a value on one scale.
# A dimension is admitted when a corpus states a bound in it and a parser and its tests arrive
# with it -- never before, which is the mistake 0004 avoided with `modality`.
DIMENSIONS = {"duration": duration_in_days}


def check_bounds(ctx):
    """The shape of a bound, the dimension it must be comparable in, and that two bounds on one
    term do not contradict each other.

    Six rules:

      * `bounds` lives inside the `ambiguity` block and nowhere else, because it bounds a term
        an ambiguity records as open;
      * only on `fate: unresolved`. A bound's whole force is that an owner's ruling is compared
        against it (0027), and a `fate: decision` has no ruling to compare: the decision record
        is prose and this checker cannot read it, so a bound there would be recorded and never
        checked, which is what 0005 refuses;
      * the block carries exactly `term`, `dimension` and `examples`, and each example exactly
        `locator`, `text`, `verdict` and `value`;
      * the `term` occurs verbatim in the entry's own `evidence`, so a bound names a term the
        cited passage actually leaves open rather than one the mapper supplied;
      * the `dimension` is one `DIMENSIONS` compares, and every `value` parses in it;
      * the examples are mutually consistent: some threshold in the dimension separates the fact
        patterns the term applies to from those it does not. Two examples that cannot both be
        true of one term are a defect in the map, not an ambiguity in the corpus.

    What it does not buy: nothing detects an example the mapper never read. A term bounded by an
    example nobody recorded produces a map that passes here, which is the blind spot an
    unrecorded conflict already has (0007).
    """
    bad, carriers, examples = [], 0, 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        if "bounds" in entry:
            bad.append(f"  X  {name}: carries `bounds` at entry level; it belongs in the "
                       f"`ambiguity` block, because a bound bounds a term an ambiguity records as open")
        ambiguity = block(entry, "ambiguity")
        if "bounds" not in ambiguity:
            continue
        carriers += 1
        bounds = ambiguity["bounds"]
        if not isinstance(bounds, dict):
            bad.append(f"  X  {name}: `ambiguity.bounds` is not an object ({', '.join(BOUND_FIELDS)})")
            continue
        if ambiguity.get("fate") != "unresolved":
            bad.append(f"  X  {name}: carries `ambiguity.bounds` and `fate: "
                       f"{ambiguity.get('fate')}`. A bound is checked against an owner's ruling on an "
                       f"open question (0027); a settled ambiguity has none, so the bound would be "
                       f"recorded and never read")
        missing = [f for f in BOUND_FIELDS if f not in bounds]
        extra = sorted(set(bounds) - set(BOUND_FIELDS))
        if missing or extra:
            bad.append(f"  X  {name}: `ambiguity.bounds` carries exactly {', '.join(BOUND_FIELDS)}"
                       + (f"; it lacks {', '.join(missing)}" if missing else "")
                       + (f"; it carries {', '.join(extra)}" if extra else ""))
        term = bounds.get("term")
        evidence = entry.get("evidence")
        if not isinstance(term, str) or not term.strip():
            bad.append(f"  X  {name}: bounds has no `term`; a bound names the term the rule leaves open")
        elif not isinstance(evidence, str):
            bad.append(f"  X  {name}: bounds names term {term!r} and the entry has no `evidence` to "
                       f"find it in; a derived entry quotes no passage, so no passage of it leaves a term open")
        elif term not in evidence:
            bad.append(f"  X  {name}: bounds names term {term!r}, which does not occur in the entry's "
                       f"`evidence`. The term a bound bounds is one the cited passage uses, in its words")
        dimension = bounds.get("dimension")
        scale = DIMENSIONS.get(dimension) if isinstance(dimension, str) else None
        if scale is None:
            bad.append(f"  X  {name}: bounds.dimension is {dimension!r}, which is not a dimension this "
                       f"checker can compare ({', '.join(sorted(DIMENSIONS))}). A bound is admitted only "
                       f"where a later ruling's line and this example's fact pattern are values on one "
                       f"scale -- that comparison is the whole of what the field earns its place by "
                       f"(0005, 0031). An example whose fact pattern is comparable to no threshold a "
                       f"ruling would state stays prose in `ambiguity.question`, unchecked")
        listed = bounds.get("examples")
        if not isinstance(listed, list) or not listed:
            bad.append(f"  X  {name}: bounds.examples is not a non-empty list; a bound with no example "
                       f"records nothing the corpus authored")
            continue
        placed = []
        for index, example in enumerate(listed, start=1):
            where = f"{name}: bounds.examples[{index}]"
            if not isinstance(example, dict):
                bad.append(f"  X  {where} is not an object")
                continue
            examples += 1
            lacks = [f for f in EXAMPLE_FIELDS if f not in example]
            carries = sorted(set(example) - set(EXAMPLE_FIELDS))
            if lacks or carries:
                bad.append(f"  X  {where} carries exactly {', '.join(EXAMPLE_FIELDS)}"
                           + (f"; it lacks {', '.join(lacks)}" if lacks else "")
                           + (f"; it carries {', '.join(carries)}" if carries else ""))
            locator = example.get("locator")
            if not isinstance(locator, dict) or not locator.get("sourceId") or not locator.get("citation"):
                bad.append(f"  X  {where}: `locator` names the example's own citation, as an entry's does "
                           f"({{sourceId, citation}}); without one nothing can find the text")
            elif locator.get("sourceId") != block(entry, "locator").get("sourceId"):
                bad.append(f"  X  {where}: cites corpus {locator['sourceId']!r} and the entry cites "
                           f"{block(entry, 'locator').get('sourceId')!r}. A bound is the same corpus's own "
                           f"example of its own term; a meaning another corpus gives is `definedElsewhere` "
                           f"or an entry of its own (0026)")
            text = example.get("text")
            if not isinstance(text, str) or not text.strip():
                bad.append(f"  X  {where}: `text` is the example's words, one contiguous verbatim span")
            elif "..." in text or "…" in text:
                bad.append(f"  X  {where}: `text` elides its middle. One contiguous span, as `evidence` is: "
                           f"a checker matches what is before the ellipsis and reports a pass over the rest")
            if example.get("verdict") not in VERDICTS:
                bad.append(f"  X  {where}: verdict is {example.get('verdict')!r}, outside "
                           f"{{{', '.join(sorted(VERDICTS))}}} -- the term applies to this fact pattern, or it "
                           f"does not; an example that says neither bounds nothing")
            if scale is None:
                continue
            on_scale = scale(example.get("value"))
            if on_scale is None:
                bad.append(f"  X  {where}: value {example.get('value')!r} is not a {dimension} this checker "
                           f"can place on a scale, so no ruling could be compared against it")
            elif example.get("verdict") in VERDICTS:
                placed.append((on_scale, example.get("verdict"), example.get("value")))
        bad.extend(_inconsistent(name, dimension, placed))

    if not carriers and not bad:
        return skip("no entry carries `ambiguity.bounds`, so no authored example bounds a term in "
                    "this map and the rule is vacuous over it", had_subject=False)
    return verdict(bad, f"{examples} authored example(s) bound a term on {carriers} "
                        f"{'entry' if carriers == 1 else 'entries'}: each in a dimension this checker "
                        f"compares, and mutually consistent",
                   "a bound is not well-formed, or two bounds contradict each other")


def _inconsistent(name, dimension, placed):
    """The examples of one term contradict each other unless a threshold separates them.

    A bounded term is one-sided -- short, long, near, far -- so the fact patterns it applies to
    sit wholly on one side of the ones it does not. Which side is the corpus's to say and the
    examples' to show, so nothing here declares a direction: the examples are consistent when
    every `applies` value is below every `doesNotApply` value, or every one is above. A value
    carrying both verdicts fails both ways, which is the same defect stated once.
    """
    applies = [(value, written) for value, verdict_, written in placed if verdict_ == "applies"]
    excluded = [(value, written) for value, verdict_, written in placed if verdict_ == "doesNotApply"]
    if not applies or not excluded:
        return []
    if max(v for v, _ in applies) < min(v for v, _ in excluded):
        return []
    if min(v for v, _ in applies) > max(v for v, _ in excluded):
        return []
    inside = ", ".join(sorted({w for _, w in applies}))
    outside = ", ".join(sorted({w for _, w in excluded}))
    return [f"  X  {name}: the bounds contradict each other in {dimension}. The term applies at "
            f"{inside} and does not apply at {outside}, and no threshold separates them, so no reading "
            f"of the term satisfies both examples. Two bounds that cannot both hold are a defect in the "
            f"map, not an ambiguity in the corpus"]
