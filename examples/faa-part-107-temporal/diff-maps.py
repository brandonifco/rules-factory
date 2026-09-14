#!/usr/bin/env python3
"""Diff two corpus maps of the same corpus at different dates.

Written for the temporal trial. It compares entries by id, and for entries present in both
it reports which fields moved. The interesting output is not the added and removed entries --
those are obvious from the section list -- but the entries whose id survived while their
meaning did not.
"""
import json, sys, pathlib

FIELDS = ["name", "kind", "scope", "clarity", "status", "evidence", "note"]


def _short(v, n=60):
    """Abbreviate for display only. Comparison always uses the full value."""
    if v is None:
        return None
    return tuple(x[:n] + "…" if isinstance(x, str) and len(x) > n else x for x in v)

def load(p):
    d = json.loads(pathlib.Path(p).read_text())
    b = d.get("baseline", {})
    label = b.get("asOf") or b.get("contentHash", "?")[:12]
    return label, {e["id"]: e for e in d["entries"]}

def amb(e):
    """The ambiguity, compared in full.

    This truncated the question to 60 characters, for readable output. A real change to an
    entry -- where a later text added a third exception and the earlier note said there was
    none -- differed only after that cutoff, and the diff reported nothing. Abbreviate when
    printing; never when comparing.
    """
    a = e.get("ambiguity")
    return None if a is None else (a.get("fate"), a.get("unresolvedReason"), a.get("question", ""))

def main(a_path, b_path):
    a_date, a = load(a_path); b_date, b = load(b_path)
    print(f"{a_date}  ->  {b_date}\n")

    for i in sorted(set(b) - set(a)):
        print(f"  ADDED    {i}  ({b[i]['name']})")
    for i in sorted(set(a) - set(b)):
        print(f"  REMOVED  {i}  ({a[i]['name']})")

    for i in sorted(set(a) & set(b)):
        ch = []
        for f in FIELDS:
            if a[i].get(f) != b[i].get(f):
                ch.append(f)
        if a[i]["locator"] != b[i]["locator"]:
            ch.append("locator")
        if a[i].get("dependsOn") != b[i].get("dependsOn"):
            ch.append("dependsOn")
        # gatedBy: a re-map can move a rule into or out of a phase, or change which rule
        # gates it, with nothing else about the entry moving. Neither Part 107 map carries
        # the field -- a stateless corpus has no phases for a rule to be scoped to -- so
        # here this compares absent to absent on every entry. It is for corpora that do.
        if a[i].get("gatedBy") != b[i].get("gatedBy"):
            ch.append("gatedBy")
        # beyondAdapter: reachability can change without the rule changing, in either
        # direction -- a better adapter is admitted, or a revision moves a rule out of prose
        # and into a figure. Compared whole, so a change of modality under the same adapter
        # shows up too.
        if a[i].get("beyondAdapter") != b[i].get("beyondAdapter"):
            ch.append("beyondAdapter")
        if amb(a[i]) != amb(b[i]):
            ch.append("ambiguity")
        if ch:
            print(f"  CHANGED  {i}: {', '.join(ch)}")
            if "clarity" in ch:
                print(f"             clarity {a[i]['clarity']} -> {b[i]['clarity']}")
            if "ambiguity" in ch:
                print(f"             ambiguity {_short(amb(a[i]))} -> {_short(amb(b[i]))}")
            if "name" in ch:
                print(f"             name {a[i]['name']!r}")
                print(f"               -> {b[i]['name']!r}")

if __name__ == "__main__":
    main(*sys.argv[1:3])
