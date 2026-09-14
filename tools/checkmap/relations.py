"""The structural relations between entries: `dependsOn`, the two gate fields (0011) and
`derivedFrom` (0012). Each names entries in the same map, and each has its own rule about what
it may name and whether it may loop.
"""
import sys

from .diagnostics import skip, verdict
from .model import GATE_FIELDS, ID_LIST_FIELDS, PASSAGE_FIELDS, entries_of, index, label


def check_references(ctx):
    """`dependsOn`, `enabledBy` and `suspendedBy` hold entry ids in the same map, and nothing else.

    0003: "If a proposed gate has no entry, the map is missing an entry; that is the
    finding, not a reason to write prose here."
    """
    by_id, bad, edges = index(ctx["map"]), [], 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        for field in ID_LIST_FIELDS:
            for ref in entry.get(field) or []:
                edges += 1
                if not isinstance(ref, str):
                    bad.append(f"  X  {name}: {field} holds {ref!r}, which is not an id")
                elif ref not in by_id:
                    bad.append(f"  X  {name}: {field} names {ref!r}, which is not an entry in this map")
                elif ref == entry.get("id"):
                    bad.append(f"  X  {name}: {field} names itself")
    if not edges:
        return skip("no entry names a dependsOn, enabledBy or suspendedBy, so no reference was resolved",
                    had_subject=False)
    return verdict(bad, f"{edges} dependsOn/enabledBy/suspendedBy references all resolve",
                   "a reference names no entry")


def check_no_cycles(ctx):
    """`dependsOn` determines backlog order, so a cycle means no order exists.

    The gate fields are deliberately not checked for cycles: they order nothing (0003), and a
    mutual gate is a legitimate shape -- entry from the bar suspends other moves while
    those moves' own gate names it back.
    """
    by_id = index(ctx["map"])
    colour, bad = {}, []

    def walk(node, trail):
        colour[node] = "open"
        for dep in by_id.get(node, {}).get("dependsOn") or []:
            if not isinstance(dep, str) or dep not in by_id:
                continue
            if colour.get(dep) == "open":
                cycle = trail[trail.index(dep):] if dep in trail else [dep]
                bad.append("  X  dependsOn cycle: " + " -> ".join(cycle + [dep]))
            elif dep not in colour:
                walk(dep, trail + [dep])
        colour[node] = "closed"

    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    for node in by_id:
        if node not in colour:
            walk(node, [node])
    if not any(by_id[node].get("dependsOn") for node in by_id):
        return skip("no entry depends on another, so acyclicity was not exercised", had_subject=False)
    return verdict(sorted(set(bad)), f"dependsOn over {len(by_id)} entries is acyclic", "dependsOn has a cycle")


def check_gates(ctx):
    """A gate has a direction, and the field it sits in states it (0011).

    0003 recorded a gate as one undirected list, `gatedBy`, and accepted as a cost that
    `bearing-off-eligible` (which opens a phase) and `enter-from-bar` (which closes one) looked
    identical on the entries they gate. 0011 splits the list: `enabledBy` names the rules that
    make this rule reachable, `suspendedBy` the rules that make it unreachable. Resolving the
    ids is `references`' job; what is checked here is what the split adds:

      * `gatedBy` is refused by name. A map still carrying it states gates with no direction,
        which is what 0011 removed, and ignoring the field would make every gate in an
        unmigrated map vanish from every other check without a word;
      * no entry names one rule in both fields, because one rule cannot both open and close
        the same entry's reachability.

    What it cannot do: tell whether a gate is in the right field. A permitting rule filed under
    `suspendedBy` resolves, is not duplicated, and passes. That is review -- what 0011 buys is
    that the direction is written where a reviewer reads it, rather than recovered by following
    the id.
    """
    bad, gated = [], 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        if "gatedBy" in entry:
            bad.append(f"  X  {name}: carries `gatedBy`, which 0011 split by direction; name each "
                       f"gate in `enabledBy` (makes this rule reachable) or `suspendedBy` (makes it "
                       f"unreachable)")
        lists = {field: entry.get(field) if isinstance(entry.get(field), list) else []
                 for field in GATE_FIELDS}
        if any(lists.values()):
            gated += 1
        both = {x for x in lists["enabledBy"] if isinstance(x, str)} & \
            {x for x in lists["suspendedBy"] if isinstance(x, str)}
        for ref in sorted(both):
            bad.append(f"  X  {name}: names {ref!r} in both `enabledBy` and `suspendedBy`; one rule "
                       f"cannot both open and close this one")
    if not gated and not bad:
        return skip("no entry carries `enabledBy` or `suspendedBy`, so no gate's direction was "
                    "checked -- the right outcome for a stateless corpus", had_subject=False)
    return verdict(bad, f"{gated} gated entr{'y' if gated == 1 else 'ies'}: every gate is filed by "
                        f"direction, and none in both directions",
                   "a gate does not state its direction")


def check_derived(ctx):
    """A derived entry is a fact the corpus entails and never states (0012).

    `stake-multiplier`'s span states what a gammon and a backgammon pay, both as multiples of
    a single stake, and never what a hit pays. That a hit pays the single stake is read off
    the other two. 0012 gives the fact its own entry and a fourth relation, `derivedFrom`: not
    implementation order (`dependsOn`), not reachability (the gate fields), not a pointer the
    corpus makes (`crossReferences`), but *this fact is entailed by those facts*.

      * `derivedFrom` is a list of at least two ids. A consequence of one entry is that
        entry's, and 0012 discharges it as a test the entry names, not as an entry;
      * every source resolves in this map, is not the entry itself, and is `scope: in` -- a
        fact cannot be derived from a rule the engine does not cover, or from an absence;
      * no derivation is circular, following `derivedFrom` through derived sources;
      * a derived entry cites nothing: no `locator`, no `evidence`, and nothing only a passage
        carries (`crossReferences`, `absentFrom`, `beyondAdapter`, `definedElsewhere`). No
        sentence contains its fact, so `evidence` keeps one meaning -- a verbatim span -- on
        every entry that has it, and the derived entry's citation is its sources'.

    What it cannot do: tell whether the sources actually entail the fact. That a hit pays one
    stake *follows* from the two payouts is the mapper's reading, written in `note`; this check
    proves only that the reading names what it rests on and that those are rules the map
    covers.
    """
    by_id, bad, carriers = index(ctx["map"]), [], []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict) or "derivedFrom" not in entry:
            continue
        name = label(entry, position)
        carriers.append(name)
        sources = entry.get("derivedFrom")
        if not isinstance(sources, list) or any(not isinstance(s, str) for s in sources):
            bad.append(f"  X  {name}: `derivedFrom` is not a list of entry ids")
            continue
        if len(set(sources)) < 2:
            bad.append(f"  X  {name}: `derivedFrom` names {len(set(sources))} source(s); a fact "
                       f"that follows from one entry is that entry's consequence, and is a test "
                       f"that entry names (0012), not an entry")
        for ref in sources:
            target = by_id.get(ref)
            if target is None:
                bad.append(f"  X  {name}: derivedFrom names {ref!r}, which is not an entry in this map")
            elif ref == entry.get("id"):
                bad.append(f"  X  {name}: derivedFrom names itself")
            elif target.get("scope") != "in":
                bad.append(f"  X  {name}: derivedFrom names {ref!r}, which is scope "
                           f"{target.get('scope')!r}; a fact is not derived from a rule the engine "
                           f"does not cover")
        for field in PASSAGE_FIELDS:
            if field in entry:
                bad.append(f"  X  {name}: is derived and carries `{field}`; no sentence states a "
                           f"derived fact, so it cites nothing and its sources are its citation")

    colour = {}

    def walk(node, trail):
        colour[node] = "open"
        sources = by_id.get(node, {}).get("derivedFrom")
        for ref in sources if isinstance(sources, list) else []:
            if not isinstance(ref, str) or ref not in by_id or ref == node:
                continue
            if colour.get(ref) == "open":
                bad.append("  X  derivedFrom cycle: " + " -> ".join(trail[trail.index(ref):] + [ref]))
            elif ref not in colour:
                walk(ref, trail + [ref])
        colour[node] = "closed"

    for node, entry in by_id.items():
        if "derivedFrom" in entry and node not in colour:
            walk(node, [node])

    if not carriers:
        return skip("no entry carries `derivedFrom`, so no derivation was checked", had_subject=False)
    return verdict(sorted(set(bad), key=bad.index),
                   f"{len(carriers)} derived entr{'y' if len(carriers) == 1 else 'ies'} "
                   f"({', '.join(sorted(carriers))}): each derives from two or more in-scope "
                   f"entries and cites nothing itself",
                   "a derived entry is not well-formed")
