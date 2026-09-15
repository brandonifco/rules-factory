"""What an entry takes from outside the engine at runtime: who asserts an assertion
(`assertedBy`) and what random values an operation draws (`draws`), each anchored in the words
of the corpus (0025).
"""
import re

from .diagnostics import skip, verdict
from .model import block, corpora_of, entries_of, label

# The one value that names nobody the corpus names: the caller, implied (0025).
CALLER = "caller"
DRAW_FIELDS = ("dice", "count")
# Straight and curly double quotes. A single quote is not a delimiter: it is also an apostrophe.
QUOTED_SPAN = re.compile(r'"([^"]+)"|“([^”]+)”')


def quoted_spans(note):
    """The spans a `note` quotes, which is where a mapper cites a passage outside the evidence."""
    if not isinstance(note, str):
        return []
    return [a or b for a, b in QUOTED_SPAN.findall(note)]


def names_term(text, term):
    """Whether `text` contains `term` as a whole word or phrase, ignoring case and spacing."""
    if not isinstance(text, str) or not isinstance(term, str) or not term.strip():
        return False
    words = [re.escape(word) for word in term.split()]
    pattern = r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


def anchored(entry, term):
    """Where `term` is anchored: "evidence", "note", or None when it is in neither."""
    if names_term(entry.get("evidence"), term):
        return "evidence"
    if any(names_term(span, term) for span in quoted_spans(entry.get("note"))):
        return "note"
    return None


def check_asserted_by(ctx):
    """Every `kind: assertion` entry says who the corpus lets assert it (0025, #117).

    An engine owes an assertion four things, and the second is *attribute it*. Until 0025 the map
    did not say to whom, so an engine that checked the decider did it from its own reading of the
    corpus (srd-52-combat checks `initiative-ties`' GM and players in code).

      * `assertedBy` is on every assertion entry and on no other: a non-empty list of distinct,
        non-blank strings;
      * each value is anchored in the corpus's words: it appears, ignoring case, as a whole word or
        phrase in the entry's `evidence`, or inside a span its `note` quotes;
      * where the corpus names nobody, the value is `["caller"]`, alone, and the entry carries a
        `note` saying why, which names the caller.

    What it cannot do: read the corpus. A span quoted in `note` is not located here, so a quote
    the corpus does not contain passes this check (the example maps' quotes are held to their
    corpora by a test). Nor does it prove the value is the *right* party: a word in the evidence
    that names a bystander passes.
    """
    bad, carriers, anchors = [], [], {"evidence": 0, "note": 0, CALLER: 0}
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        is_assertion = entry.get("kind") == "assertion"
        if "assertedBy" not in entry:
            if is_assertion:
                bad.append(f"  X  {name}: is `kind: assertion` and has no `assertedBy`; an engine "
                           f"attributes an assertion, and the map says to whom")
            continue
        carriers.append(name)
        if not is_assertion:
            bad.append(f"  X  {name}: carries `assertedBy` while kind is {entry.get('kind')!r}; only an "
                       f"assertion is asserted")
            continue
        values = entry["assertedBy"]
        if not isinstance(values, list) or not values:
            bad.append(f"  X  {name}: `assertedBy` is not a non-empty list of who asserts it")
            continue
        if any(not isinstance(v, str) or not v.strip() for v in values):
            bad.append(f"  X  {name}: `assertedBy` holds something that is not a name")
            continue
        folded = [" ".join(v.split()).casefold() for v in values]
        if len(set(folded)) != len(folded):
            bad.append(f"  X  {name}: `assertedBy` names one party twice")
        if CALLER in folded:
            if len(values) > 1:
                bad.append(f"  X  {name}: `assertedBy` names `caller` beside other parties; `caller` "
                           f"means the corpus names nobody, so it stands alone")
            elif not names_term(entry.get("note"), CALLER):
                bad.append(f"  X  {name}: `assertedBy` is `caller` and no `note` says why the corpus "
                           f"names nobody; a `caller` with no reason is a party nobody looked for")
            else:
                anchors[CALLER] += 1
            continue
        for value in values:
            where = anchored(entry, value)
            if where is None:
                bad.append(f"  X  {name}: `assertedBy` names {value!r}, which is neither in its "
                           f"`evidence` nor in a span its `note` quotes; name the party in the "
                           f"corpus's words, or `caller` with the reason")
            else:
                anchors[where] += 1
    if not carriers and not bad:
        return skip("no entry is `kind: assertion`, so nobody was attributed", had_subject=False)
    return verdict(bad, f"{len(carriers)} assertion entr{'y names' if len(carriers) == 1 else 'ies name'} who "
                        f"asserts it: {anchors['evidence']} part{'y' if anchors['evidence'] == 1 else 'ies'} "
                        f"named in the evidence, {anchors['note']} in a span the note quotes, and "
                        f"{anchors[CALLER]} caller{'' if anchors[CALLER] == 1 else 's'} with a reason",
                   "an assertion does not say who asserts it, or says it in words the corpus does not use")


def draws_problems(name, draws):
    """What is wrong with the shape of a `draws` value, as report lines."""
    items = draws if isinstance(draws, list) else [draws]
    if isinstance(draws, list) and not draws:
        return [f"  X  {name}: `draws` is an empty list; an operation that draws nothing omits it"]
    bad = []
    for position, item in enumerate(items):
        where = f"draws[{position}]" if isinstance(draws, list) else "draws"
        if not isinstance(item, dict):
            bad.append(f"  X  {name}: `{where}` is not an object of {', '.join(DRAW_FIELDS)}")
            continue
        extra = sorted(set(item) - set(DRAW_FIELDS))
        if extra:
            bad.append(f"  X  {name}: `{where}` carries {extra}; a draw is {', '.join(DRAW_FIELDS)} and nothing else")
        dice, count = item.get("dice"), item.get("count")
        if not isinstance(dice, str) or not dice.strip():
            bad.append(f"  X  {name}: `{where}` names no `dice`")
        if isinstance(count, bool) or not (
                (isinstance(count, int) and count > 0) or (isinstance(count, str) and count.strip())):
            bad.append(f"  X  {name}: `{where}.count` is {count!r}; a positive number, or a short "
                       f"statement of how many when the number depends on the position")
    return bad


def check_draws(ctx):
    """An operation that draws random values says how many of what (0025, #118).

    Under `randomness: seeded` (0019) every draw comes from one replayable source, so one extra or
    missing draw changes every later one. How many draws an entry makes is therefore part of what
    a replay means, and where the corpus leaves the number open, the ambiguity is about replay
    identity as well as about one answer.

      * `draws` is an object `{dice, count}`, or a non-empty list of them: `dice` names what is
        rolled, `count` is a positive number or a short statement ("one per participant");
      * only an `operation` that is `scope: in` draws, and only from a corpus declaring
        `randomness: seeded`; under `none` the field is refused;
      * each `dice` is anchored in the corpus's words, as `assertedBy` is: in the `evidence`, or in
        a span the `note` quotes (the corpus's dice notation, where the evidence names only the
        roll);
      * `ambiguity.affectsDraws` is a boolean, and where it is `true` the entry declares `draws`,
        whose `count` may name the unsettled alternatives.

    What it cannot do: find a draw nobody declared. An operation that rolls and omits `draws`
    passes, exactly as an unrecorded conflict does; the field is required only where a mapper has
    said the draw count is unsettled. Nor is `count` read: it is prose, anchored by nothing.
    """
    corpora, bad, carriers, flagged, unread = corpora_of(ctx.get("manifest")), [], [], [], []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        affects = block(entry, "ambiguity").get("affectsDraws")
        if "affectsDraws" in block(entry, "ambiguity"):
            if not isinstance(affects, bool):
                bad.append(f"  X  {name}: ambiguity.affectsDraws is {affects!r}, not true or false")
            elif affects:
                flagged.append(name)
                if "draws" not in entry:
                    bad.append(f"  X  {name}: ambiguity.affectsDraws is true and the entry declares no "
                               f"`draws`; say what is drawn, and let `count` name the alternatives")
        if "affectsDraws" in entry:
            bad.append(f"  X  {name}: carries `affectsDraws` at entry level; it belongs in the "
                       f"`ambiguity` block, because only an unsettled point can unsettle a draw count")
        if "draws" not in entry:
            continue
        carriers.append(name)
        if entry.get("kind") != "operation":
            bad.append(f"  X  {name}: carries `draws` while kind is {entry.get('kind')!r}; only an "
                       f"operation resolves, and so only an operation draws")
        if entry.get("scope") != "in":
            bad.append(f"  X  {name}: carries `draws` while scope is {entry.get('scope')!r}; the engine "
                       f"declines an out-of-scope rule and draws nothing for it")
        problems = draws_problems(name, entry["draws"])
        bad.extend(problems)
        source_id = block(entry, "locator").get("sourceId") or (ctx["map"].get("corpus")
                                                                if isinstance(ctx["map"], dict) else None)
        randomness = (corpora.get(source_id) or {}).get("randomness")
        if randomness == "none":
            bad.append(f"  X  {name}: carries `draws` and {source_id} declares `randomness: none`; an "
                       f"engine for it draws no random value (0019)")
        elif randomness != "seeded":
            unread.append(name)
        if problems:
            continue
        for item in entry["draws"] if isinstance(entry["draws"], list) else [entry["draws"]]:
            if anchored(entry, item["dice"]) is None:
                bad.append(f"  X  {name}: `draws` names dice {item['dice']!r}, which are neither in its "
                           f"`evidence` nor in a span its `note` quotes")
    if unread and not bad:
        return skip(f"{len(unread)} entr{'y' if len(unread) == 1 else 'ies'} ({', '.join(unread)}) declare "
                    f"`draws` and no manifest says their corpus is `randomness: seeded`. Pass --manifest.")
    randomness = sorted({str(c.get("randomness")) for c in corpora.values()})
    if not carriers and not flagged and not bad:
        if corpora and randomness == ["none"]:
            return verdict([], "no entry draws, and every corpus declares `randomness: none`", "")
        return skip("no entry declares `draws` or an ambiguity that affects them, so the rules about "
                    "draws are vacuous over this map", had_subject=False)
    return verdict(bad, f"{len(carriers)} drawing entr{'y' if len(carriers) == 1 else 'ies'}, each an "
                        f"in-scope operation of a seeded corpus naming dice the corpus names; "
                        f"{len(flagged)} ambiguit{'y' if len(flagged) == 1 else 'ies'} affecting draws, "
                        f"each declaring them",
                   "a draw is declared where nothing may draw, or named in words the corpus does not use")
