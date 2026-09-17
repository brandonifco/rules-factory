"""The `ambiguity` block: where it may appear (0005 D), that a `fate: decision` names a record
that exists, and that the entries answering one contradicted question agree (0007).
"""
import os

from .diagnostics import skip, verdict
from mapcontract.entry import block, entries_of, fate_of, label


def check_exclusions(ctx):
    """The `ambiguity` block is not a general decline carrier (0005 D).

    Three rules: no entry carries `definedElsewhere` or `beyondAdapter` alongside an
    `ambiguity` block; `ambiguity` is present exactly when `clarity: ambiguous`; and the
    block's own contents -- `question`, `fate`, `decision` when the fate is `decision`,
    `unresolvedReason` when it is `unresolved`.
    """
    bad = []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        has_ambiguity = "ambiguity" in entry
        for field in ("definedElsewhere", "beyondAdapter"):
            if field in entry and has_ambiguity:
                bad.append(f"  X  {name}: carries `{field}` and an `ambiguity` block; two correspondence rows would fire")
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
