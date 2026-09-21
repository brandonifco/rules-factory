"""The `ambiguity` block: where it may appear (0005 D), that a `fate: decision` names a record
that exists, and that the entries answering one contradicted question agree (0007).
"""
import os

from .diagnostics import skip, verdict
from mapcontract.entry import block, entries_of, fate_of, label

# What an owner's ruling would be compared against, and so the reasons the correspondence
# table can produce for an entry whose ambiguity is open (0034). Rows 2 and 5 are deliberately
# not read: an overlay turns both (0015), so a reason justified by them today is unjustified
# tomorrow, and the check would then read an overlay field and belong in STATUS_DEPENDENT.
OPEN_QUESTION_REASON = "RequiresInterpretation"
OUT_OF_SCOPE_REASON = "OutsideCurrentScope"
#: Rows 3 and 4. What an entry returns when a corpus it defers to was not admitted, or an adapter
#: cannot read the passage -- and, since 0059, what such an entry returns even where it also
#: leaves a question open.
MISSING_DATA_REASON = "MissingRulesData"


def check_exclusions(ctx):
    """The `ambiguity` block carries its own contents and nothing else's (0005 D).

    Two rules: `ambiguity` is present exactly when `clarity: ambiguous`; and the block's own
    contents -- `question`, `fate`, `decision` when the fate is `decision`, `unresolvedReason`
    when it is `unresolved`.

    A third rule was here until 0059: no entry carried `definedElsewhere` or `beyondAdapter`
    beside an `ambiguity` block, "to keep two rows of the correspondence table from firing with
    different answers on the same entry". The table gained an order after that was written --
    rows are checked in order and the first match wins -- so two rows matching is one answer and
    a recorded second fact, and the exclusion was costing a true one: `method-of-allocation`
    defers a term to an unadmitted statute *and* has a gap of its own, and had to write the
    deferral as a cross-reference to stay representable. `check_unresolved_reason` is where the
    pair is now held to an answer.
    """
    bad = []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        has_ambiguity = "ambiguity" in entry
        if entry.get("clarity") == "clear" and has_ambiguity:
            bad.append(f"  X  {name}: clarity is `clear` but an `ambiguity` block is present")
        if entry.get("clarity") == "ambiguous" and not has_ambiguity:
            bad.append(f"  X  {name}: clarity is `ambiguous` but no `ambiguity` block states the question")
        if has_ambiguity:
            ambiguity = block(entry, "ambiguity")
            if not isinstance(entry.get("ambiguity"), dict):
                bad.append(f"  X  {name}: `ambiguity` is not an object")
                continue
            if not ambiguity.get("question"):
                bad.append(f"  X  {name}: ambiguity has no `question`")
            if not ambiguity.get("fate"):
                bad.append(f"  X  {name}: ambiguity has no `fate`; there is no third value and no absent one")
            if ambiguity.get("fate") == "decision" and not ambiguity.get("decision"):
                bad.append(f"  X  {name}: fate is `decision` but no record is named")
            if ambiguity.get("fate") == "unresolved" and not ambiguity.get("unresolvedReason"):
                bad.append(f"  X  {name}: fate is `unresolved` but no `unresolvedReason` ties it to the correspondence table")
            if ambiguity.get("fate") == "decision" and ambiguity.get("unresolvedReason"):
                bad.append(f"  X  {name}: fate is `decision`, so there is no runtime unresolved reason to name")
    return verdict(bad, "ambiguity blocks are present exactly where clarity says, and carry nothing else's job",
                   "an ambiguity block is misused")


def check_inherited_reason(ctx):
    """The same rule one edge away: a missing definition dominates an open question (#226).

    Trial 9's adjudication stated it after both mappers got it wrong from opposite sides:

        `definedElsewhere` relocates the reason an entry declines; it never converts a decline
        into an answer.

    An entry whose `dependsOn` reaches an entry carrying `definedElsewhere` or `beyondAdapter`
    cannot be resolved without a corpus nobody admitted, so what it returns is `MissingRulesData`,
    inherited across the edge. An open question recorded on such an entry sends the only party who
    could act on it to interpret something no reading settles -- map A's failure mode, filed under
    `RequiresInterpretation` -- when what is missing is a definition they can go and get.

    0059 made this checkable by dropping the exclusion that hid it: the entry itself may now carry
    both fields, so the rule for one entry and the rule across an edge are one rule, and this is
    the half `check_unresolved_reason` cannot see.

    What it does not do: reach further than one edge, or read `status`. A chain of three is not
    walked, because a `dependsOn` edge to an implemented entry is not a decline and the map cannot
    tell which without reading an overlay -- and no epistemic check may (0034).
    """
    doc = ctx["map"]
    deferring = _deferring_ids(doc)
    bad, checked = [], 0
    for position, entry in enumerate(entries_of(doc)):
        if not isinstance(entry, dict) or fate_of(entry) != "unresolved":
            continue
        if block(entry, "ambiguity").get("unresolvedReason") != OPEN_QUESTION_REASON:
            continue
        reached = _inherits_from(entry, deferring)
        if not reached:
            continue
        checked += 1
        name = label(entry, position)
        bad.append(f"  X  {name}: fate is `unresolved` with {OPEN_QUESTION_REASON!r}, and "
                   f"`dependsOn` reaches {', '.join(reached)}, which defer(s) to a corpus that "
                   f"was not admitted. The reason is inherited: a caller cannot resolve this "
                   f"without that corpus, so it is {MISSING_DATA_REASON!r} (0059)")
    if not bad and not checked:
        return skip("no open question depends on an entry that defers to an unadmitted corpus, "
                    "so no reason is inherited across an edge", had_subject=False)
    return verdict(bad, "no open question hides a missing definition one edge away",
                   "an open question wears a reason its dependency overrides")


def check_decision_records(ctx):
    """A `fate: decision` that names a record means the record exists.

    "Never cite a document you have not written." Paths are resolved against the repository
    root; without one the check reports NOT VERIFIED rather than passing.
    """
    named = [
        (label(e, i), block(e, "ambiguity").get("decision"))
        for i, e in enumerate(entries_of(ctx["map"]))
        if isinstance(e, dict) and fate_of(e) == "decision"
    ]
    if not named:
        return skip("no entry carries `fate: decision`, so no record was named to resolve", had_subject=False)
    root = ctx["repo_root"]
    if root is None or not os.path.isdir(root):
        return skip(f"no repository root ({root!r}) to resolve a decision record path against")
    bad = []
    for name, path in named:
        if not path:
            continue  # reported by `exclusions`
        if not os.path.isfile(os.path.join(root, path)):
            bad.append(f"  X  {name}: names decision record {path!r}, which does not exist under {root}")
    return verdict(bad, f"{len(named)} named decision records all exist", "a decision record does not exist")


def check_conflicts(ctx):
    """`ambiguity.conflict` groups the entries that answer one contradicted question (0007).

    0005 section B required that entries in a conflict settled by decision name the same
    record, and conceded in the same section that nothing linked them. 0007 adds the slug
    and rules that a conflict is a question rather than a pair, so the four rules below are
    the whole of what it claims:

      * the slug lives inside an `ambiguity` block, so only an ambiguous entry is in a
        conflict -- `exclusions` already ties the block to `clarity: ambiguous`;
      * a conflict has at least two members, because a slug carried alone records a
        contradiction with nothing and is what a typo looks like;
      * every member shares a `fate`, because one question is not both settled and declined;
      * where that fate is `decision`, every member names the same record.

    What it cannot do: detect a conflict nobody recorded. Two `clarity: clear` entries
    stating incompatible rules pass every check in this file.
    """
    bad, groups = [], {}
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        slug = block(entry, "ambiguity").get("conflict")
        if slug is None:
            if "conflict" in entry:
                bad.append(f"  X  {name}: carries `conflict` at entry level; it belongs in the "
                           f"`ambiguity` block, because only an ambiguous entry is in a conflict")
            continue
        if not isinstance(slug, str) or not slug.strip():
            bad.append(f"  X  {name}: ambiguity.conflict is {slug!r}, which is not a slug naming a question")
            continue
        groups.setdefault(slug, []).append((name, entry))

    for slug, members in sorted(groups.items()):
        names = [name for name, _ in members]
        if len(members) < 2:
            bad.append(f"  X  {names[0]}: is the only entry in conflict {slug!r}; a conflict is a "
                       f"question the corpus answers twice, so it has at least two members")
            continue
        fates = {fate_of(entry) for _, entry in members}
        if len(fates) > 1:
            bad.append(f"  X  conflict {slug!r} ({', '.join(names)}): members disagree on `fate` "
                       f"({', '.join(sorted(str(f) for f in fates))}); one question is not both "
                       f"settled and declined")
            continue
        if fates == {"decision"}:
            records = {block(entry, "ambiguity").get("decision") for _, entry in members}
            if len(records) > 1:
                bad.append(f"  X  conflict {slug!r} ({', '.join(names)}): members name different "
                           f"decision records ({', '.join(sorted(str(r) for r in records))}); one "
                           f"side can be decided and the other left open")
    if not groups and not bad:
        return skip("no entry carries `ambiguity.conflict`, so no conflict was grouped and the "
                    "rule is vacuous over this map", had_subject=False)
    members = sum(len(m) for m in groups.values())
    return verdict(bad, f"{len(groups)} conflict{'' if len(groups) == 1 else 's'} over {members} "
                        f"entries: each has two or more members, one fate, and one record",
                   "a conflict is not well-formed")


def _defers(entry):
    """Whether this entry's own fields put it on row 3 or row 4."""
    return any(field in entry for field in ("definedElsewhere", "beyondAdapter"))


def _deferring_ids(doc):
    """Every entry id whose own fields defer to a corpus that was not admitted."""
    return {e.get("id") for e in entries_of(doc)
            if isinstance(e, dict) and _defers(e)}


def _inherits_from(entry, deferring):
    """The deferring entries this one's `dependsOn` reaches, sorted."""
    return sorted(set(entry.get("dependsOn") or []) & deferring)


def check_unresolved_reason(ctx):
    """An open question returns the reason a caller can act on.

    `ambiguity.unresolvedReason` is what the engine returns when the declining case is reached,
    and `schema` already holds it to the kernel's vocabulary. That is not enough: the vocabulary
    has five values and the correspondence table produces exactly one of them for a question the
    corpus leaves open. `RequiresInterpretation` tells a caller what to do -- interpret, or rule
    under 0027. `MissingRulesData` tells them to go and find data that does not exist, and
    `UnsupportedRule` tells them to wait for an implementation that would not settle it either.
    An open question wearing either reason is an uncertainty misdescribed to the only party who
    could act on it.

    So the reason must be one the entry's own rows can produce: `RequiresInterpretation` (row 6),
    or `OutsideCurrentScope` where the entry is `scope: out` and row 1 wins first. Rows 3 and 4
    can arise since 0059 dropped the exclusion that kept `definedElsewhere` and `beyondAdapter`
    off an ambiguous entry, and where one of those fields is present it wins: a missing definition
    dominates an open question, which is what trial 9's adjudication established one edge away --
    `definedElsewhere` relocates the reason an entry declines and never converts a decline into an
    answer. Such an entry names `MissingRulesData` and nothing else, because that is the reason its
    first matching row gives. Rows 2 and 5 are read by no check here on purpose: an overlay turns
    both, so a reason they justified would stop being justified in a consuming engine.

    The same rule one edge away is `check_inherited_reason` below (#226).

    What it cannot do: say whether the question is one a caller could act on. That the words of
    `ambiguity.question` name a point somebody could rule on is what 0027's `span` machinery
    tests in the factory, on the overlay, and no check of the map alone reaches it.
    """
    bad, open_questions = [], 0
    deferring = _deferring_ids(ctx["map"])
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict) or fate_of(entry) != "unresolved":
            continue
        open_questions += 1
        name = label(entry, position)
        reason = block(entry, "ambiguity").get("unresolvedReason")
        # Row order, in the one place a map can reach it. Rows 3 and 4 precede row 6, so an entry
        # carrying either field answers with theirs and row 6 never fires for it (0059) -- and
        # the same holds one edge away, or this check and `check_inherited_reason` would demand
        # different reasons of one entry and no map could satisfy both.
        if _defers(entry) or _inherits_from(entry, deferring):
            allowed = {MISSING_DATA_REASON}
        else:
            allowed = {OPEN_QUESTION_REASON}
        if entry.get("scope") == "out":
            allowed.add(OUT_OF_SCOPE_REASON)
        if reason is not None and reason not in allowed:
            # The second sentence says what the wrong reason costs, which differs by direction:
            # an open question dressed as missing data sends a caller after data that does not
            # exist, and a missing definition dressed as an open question sends them to interpret
            # something no reading settles (#226, the failure trial 9's map A made).
            if allowed == {MISSING_DATA_REASON}:
                where = ("this entry defers" if _defers(entry)
                         else f"{', '.join(_inherits_from(entry, deferring))} defers")
                why = (f"{where} to a corpus that was not admitted, so a caller told {reason!r} "
                       f"is sent to interpret what a definition they can go and get would settle")
            else:
                why = (f"a caller told {reason!r} is sent after data or an implementation, and "
                       f"what is missing is an interpretation nobody has made")
            bad.append(f"  X  {name}: fate is `unresolved` and unresolvedReason is {reason!r}. The "
                       f"correspondence table gives this entry {' or '.join(sorted(allowed))}; "
                       f"{why}")
    if not open_questions:
        return skip("no entry carries `ambiguity.fate: unresolved`, so this map leaves no question "
                    "open and there is no runtime reason to hold to the table", had_subject=False)
    return verdict(bad, f"{open_questions} open question(s), each returning a reason the "
                        f"correspondence table produces for it",
                   "an open question returns a reason no row gives it")
