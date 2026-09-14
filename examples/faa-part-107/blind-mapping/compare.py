#!/usr/bin/env python3
"""Compare the Part 107 blind map against the reference map, field by field (0014).

Adapted from examples/blind-mapping-trial/compare.py. That one aligns Hoyle entries by page
and evidence overlap; Part 107 cites by designation, so here a link needs both:

  * designation: the two citations name the same section and either one cites the whole
    section or they share a top-level paragraph ("introductory text" counts as a paragraph
    of its own). "subpart D" matches only "subpart D".
  * evidence: difflib matching blocks of MIN_BLOCK+ tokens cover at least LINK_SHARE of the
    shorter span.

PARTNER of a reference entry: among its links, the highest cov_ref * cov_blind + name-word
Jaccard, as in the trial. Names only choose among entries that already link.

Compared on each (reference, partner) pair: kind, scope, clarity, ambiguity presence and fate,
definedElsewhere presence and target, dependsOn / enabledBy / suspendedBy edge by edge, and
evidence nesting (a proxy; the reading is in the resolution rows).

crossReferences are compared across the whole map, not per pair, because the two maps split
the same sentence differently and a declaration sits on whichever entry quotes the pointer.
Each declaration is normalised to (section of the declaring entry, cited target) — "paragraph
(d) of this section" in a § 107.29 entry is § 107.29(d) — and a target one map declares and
the other declares nowhere is a flag on that key.

Edge translation. A blind edge target stands for every reference entry it LINKS to (not only
the one it is partner of), so an edge into a split entry still compares. A reference edge is
matched when some blind edge target links to the edge's target. A blind edge whose target links
to no reference entry cannot be compared and is skipped (listed in results.json).

Every flag must have a row in resolutions.json; the script exits 1 otherwise.

Usage: compare.py            writes results.json beside this file and prints a summary
       compare.py --table    prints the resolution table as markdown
"""
import difflib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
# The reference as it stood before this comparison corrected it. The corrected map is the
# working-tree corpus-map.json; comparing against it would hide the flags that led to the fixes.
REFERENCE_COMMIT = "85e416f88552a7c80d2659b8bf7540da39d447c7"
REFERENCE_PATH = "examples/faa-part-107/corpus-map.json"
BLIND_PATH = os.path.join(HERE, "blind-map.json")
RES_PATH = os.path.join(HERE, "resolutions.json")

MIN_BLOCK = 4
LINK_SHARE = 0.5
EVIDENCE_NESTED = 0.9
NAME_WEIGHT = 1.0

STOP = {"the", "and", "a", "an", "of", "to", "is", "are", "or", "in", "on", "by", "for",
        "its", "may", "be", "each", "one", "all", "with", "from", "has", "can", "not", "no"}


def tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def designations(citation):
    """(section, set of top-level paragraphs, or None for the whole section)."""
    if citation.strip().lower().startswith("subpart"):
        return ("subpart " + citation.split()[-1], None)
    m = re.match(r"§\s*(\d+\.\d+)(.*)$", citation.strip())
    sec, rest = m.group(1), m.group(2)
    paras = set()
    if "introductory text" in rest:
        paras.add("intro")
    for a, b in re.findall(r"\(([a-z])\)(?:\([0-9ivx]+\))*(?:\s*-\s*\(([a-z])\))?", rest):
        if b:
            paras.update(chr(c) for c in range(ord(a), ord(b) + 1))
        else:
            paras.add(a)
    return (sec, paras or None)


def same_place(r, b):
    (sr, pr), (sb, pb) = designations(r), designations(b)
    if sr != sb:
        return False
    return pr is None or pb is None or bool(pr & pb)


def shared(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum(blk.size for blk in sm.get_matching_blocks() if blk.size >= MIN_BLOCK)


def stem(w):
    for suffix in ("ing", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[: -len(suffix)]
            break
    if w.endswith("e") and len(w) > 3:
        w = w[:-1]
    return w


def name_words(name):
    return {stem(w) for w in re.findall(r"[a-z]+", name.lower()) if len(w) >= 3 and w not in STOP}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def align(ref, blind):
    rt = {e["id"]: tokens(e["evidence"]) for e in ref["entries"]}
    bt = {e["id"]: tokens(e["evidence"]) for e in blind["entries"]}
    links = {}
    for r in ref["entries"]:
        for b in blind["entries"]:
            if not same_place(r["locator"]["citation"], b["locator"]["citation"]):
                continue
            s = shared(rt[r["id"]], bt[b["id"]])
            lr, lb = len(rt[r["id"]]), len(bt[b["id"]])
            if not lr or not lb or s < LINK_SHARE * min(lr, lb):
                continue
            links.setdefault(r["id"], {})[b["id"]] = {
                "shared": s, "cov_ref": round(s / lr, 3), "cov_blind": round(s / lb, 3),
                "name": round(jaccard(name_words(r["name"]), name_words(b["name"])), 3),
            }
    partner = {rid: max(c, key=lambda bid: (c[bid]["cov_ref"] * c[bid]["cov_blind"]
                                             + NAME_WEIGHT * c[bid]["name"], bid))
               for rid, c in links.items()}
    linked_blind = {bid for c in links.values() for bid in c}
    return {
        "links": links,
        "partner": partner,
        "unaligned_ref": sorted(e["id"] for e in ref["entries"] if e["id"] not in links),
        "unaligned_blind": sorted(e["id"] for e in blind["entries"] if e["id"] not in linked_blind),
        "linked_not_partner": sorted(linked_blind - set(partner.values())),
    }


def xref_keys(m):
    """{(from section, target): [(entry id, 'resolvedBy <id>' | 'unmapped')]} for a whole map."""
    out = {}
    for e in m["entries"]:
        sec = designations(e["locator"]["citation"])[0]
        for x in e.get("crossReferences") or []:
            c = x["cites"]
            p = re.search(r"paragraph (\([a-z]\))", c)
            t = re.search(r"§\s*\d+\.\d+(?:\([a-z0-9]+\))?|subpart [A-Z]|49 CFR 171\.8|Air Almanac", c)
            target = f"§ {sec}{p.group(1)}" if p else (t.group(0) if t else c)
            how = f"resolvedBy {x['resolvedBy']}" if "resolvedBy" in x else "unmapped"
            out.setdefault((f"§ {sec}" if sec[0].isdigit() else sec, target), []).append((e["id"], how))
    return out


def compare(ref, blind):
    al = align(ref, blind)
    R = {e["id"]: e for e in ref["entries"]}
    B = {e["id"]: e for e in blind["entries"]}
    b2r = {}  # blind id -> reference ids it links to
    for rid, c in al["links"].items():
        for bid in c:
            b2r.setdefault(bid, set()).add(rid)
    flags, skipped = [], []

    def flag(rid, field, detail, ref_value, blind_value, bid):
        flags.append({"entry": rid, "field": field, "detail": detail, "blind": bid,
                      "ref_value": ref_value, "blind_value": blind_value})

    for rid in al["unaligned_ref"]:
        flag(rid, "entry", "no blind entry quotes this text at this designation", None, None, None)
    for bid in al["unaligned_blind"]:
        flag(None, "entry", "no reference entry quotes this text at this designation", None, None, bid)

    for rid, bid in sorted(al["partner"].items()):
        r, b = R[rid], B[bid]
        for field in ("kind", "scope", "clarity"):
            if r.get(field) != b.get(field):
                flag(rid, field, "differs", r.get(field), b.get(field), bid)
        ra, ba = r.get("ambiguity"), b.get("ambiguity")
        if bool(ra) != bool(ba):
            flag(rid, "ambiguity", "present in one map only", bool(ra), bool(ba), bid)
        elif ra and ba and ra.get("fate") != ba.get("fate"):
            flag(rid, "ambiguity.fate", "differs", ra.get("fate"), ba.get("fate"), bid)
        rd, bd = r.get("definedElsewhere"), b.get("definedElsewhere")
        if bool(rd) != bool(bd):
            flag(rid, "definedElsewhere", "present in one map only",
                 rd and rd["reference"], bd and bd["reference"], bid)
        elif rd and bd:
            x, y = rd["reference"], bd["reference"]
            if not (x.startswith(y) or y.startswith(x)):
                flag(rid, "definedElsewhere", "targets differ", x, y, bid)
        for field in ("dependsOn", "enabledBy", "suspendedBy"):
            rset = set(r.get(field) or [])
            braw = list(b.get(field) or [])
            reach = set()
            for dep in braw:
                reach |= b2r.get(dep, set())
            for d in sorted(rset - reach):
                flag(rid, field, f"reference has edge to {d}; no blind edge reaches it", d, None, bid)
            for dep in braw:
                t = b2r.get(dep, set()) - {rid}
                if not b2r.get(dep):
                    skipped.append({"entry": rid, "field": field, "blind": bid, "target": dep})
                    continue
                if t and not (t & rset):
                    flag(rid, field, f"blind has edge to {dep}; reference has no edge to what it "
                                     f"links to", sorted(t), dep, bid)
        link = al["links"][rid][bid]
        if link["cov_ref"] < EVIDENCE_NESTED and link["cov_blind"] < EVIDENCE_NESTED:
            flag(rid, "evidence", "spans overlap but neither contains the other",
                 link["cov_ref"], link["cov_blind"], bid)
        elif link["cov_blind"] < EVIDENCE_NESTED:
            flag(rid, "evidence", "blind span quotes text the reference span omits",
                 link["cov_ref"], link["cov_blind"], bid)
        elif link["cov_ref"] < EVIDENCE_NESTED:
            flag(rid, "evidence", "reference span quotes text the blind span omits",
                 link["cov_ref"], link["cov_blind"], bid)
    # A blind entry that links but is nobody's partner is usually a split, and its fields
    # would otherwise go uncompared: a clause the blind map calls ambiguous inside a reference
    # entry that is clear would be silent. Compared on scope, clarity and ambiguity presence
    # only, against the reference entry it links to best; kind is not compared (a split
    # changes kind by construction).
    for bid in al["linked_not_partner"]:
        cands = {rid: c[bid] for rid, c in al["links"].items() if bid in c}
        rid = max(cands, key=lambda i: (cands[i]["cov_ref"] * cands[i]["cov_blind"]
                                        + NAME_WEIGHT * cands[i]["name"], i))
        r, b = R[rid], B[bid]
        for field in ("scope", "clarity"):
            if r.get(field) != b.get(field):
                flag(rid, field, "differs (blind entry links here but is not its partner)",
                     r.get(field), b.get(field), bid)
        if bool(r.get("ambiguity")) != bool(b.get("ambiguity")):
            flag(rid, "ambiguity", "present in one map only (blind entry links here but is not "
                                   "its partner)", bool(r.get("ambiguity")),
                 bool(b.get("ambiguity")), bid)

    rk, bk = xref_keys(ref), xref_keys(blind)
    for k in sorted(set(rk) | set(bk)):
        if k in rk and k in bk:
            continue
        side = "reference" if k in rk else "blind"
        ids = rk.get(k) or bk.get(k)
        if k in rk:
            entry = ids[0][0]
        else:  # the reference entries whose evidence quotes the pointer the blind map declared
            cites = {x["cites"] for i, _ in bk[k] for x in B[i].get("crossReferences") or []}
            quoting = [e["id"] for e in ref["entries"]
                       if designations(e["locator"]["citation"])[0] == designations(
                           B[ids[0][0]]["locator"]["citation"])[0]
                       and any(c in e["evidence"] for c in cites)]
            entry = ",".join(quoting) or None
        flags.append({"entry": entry, "field": "crossReferences",
                      "detail": f"{k[1]} cited from {k[0]}: declared only in the {side} map",
                      "blind": None if k in rk else ids[0][0],
                      "ref_value": rk.get(k) and [f"{i}: {h}" for i, h in rk[k]],
                      "blind_value": bk.get(k) and [f"{i}: {h}" for i, h in bk[k]]})
    return al, flags, skipped


def load_reference():
    out = subprocess.run(["git", "show", f"{REFERENCE_COMMIT}:{REFERENCE_PATH}"],
                         cwd=REPO, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def key(f):
    return f"{f['entry']}|{f['field']}|{f['blind']}|{f['detail']}"


def main():
    ref = load_reference()
    blind = json.load(open(BLIND_PATH, encoding="utf-8"))
    al, flags, skipped = compare(ref, blind)
    res = json.load(open(RES_PATH, encoding="utf-8")) if os.path.exists(RES_PATH) else {}
    for f in flags:
        f["key"] = key(f)
        f["resolution"] = res.get(f["key"])
    missing = [f["key"] for f in flags if not f["resolution"]]
    stale = sorted(set(res) - {f["key"] for f in flags})

    if "--table" in sys.argv:
        print("| # | reference entry | blind entry | field | reference | blind | verdict | quote / reason |")
        print("|---|---|---|---|---|---|---|---|")
        for i, f in enumerate(flags, 1):
            r = f["resolution"] or {}
            cell = lambda v: "" if v is None else str(v).replace("|", "\\|")
            text = r.get("reason", "")
            if r.get("quote"):
                text = f"{r.get('locator', '')} \"{r['quote']}\" — {text}"
            print(f"| {i} | {cell(f['entry'])} | {cell(f['blind'])} | {f['field']} | "
                  f"{cell(f['ref_value'])} | {cell(f['blind_value'])} | {r.get('verdict', '?')} | "
                  f"{cell(text)} |")
        return

    by_field, by_verdict = {}, {}
    for f in flags:
        by_field[f["field"]] = by_field.get(f["field"], 0) + 1
        v = (f["resolution"] or {}).get("verdict", "unresolved")
        by_verdict[v] = by_verdict.get(v, 0) + 1
    result = {
        "reference": {"commit": REFERENCE_COMMIT, "path": REFERENCE_PATH,
                      "entries": len(ref["entries"])},
        "blind": {"path": "blind-map.json", "entries": len(blind["entries"])},
        "parameters": {"MIN_BLOCK": MIN_BLOCK, "LINK_SHARE": LINK_SHARE,
                       "EVIDENCE_NESTED": EVIDENCE_NESTED, "NAME_WEIGHT": NAME_WEIGHT},
        "alignment": al,
        "edges_not_comparable": skipped,
        "flag_count": len(flags),
        "flags_by_field": by_field,
        "flags_by_verdict": by_verdict,
        "flags": flags,
    }
    if "--dry" not in sys.argv:
        with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as h:
            json.dump(result, h, indent=2, ensure_ascii=False)
            h.write("\n")
    print(f"flags: {len(flags)}  {by_field}")
    print(f"verdicts: {by_verdict}")
    print("unaligned ref:", al["unaligned_ref"])
    print("unaligned blind:", al["unaligned_blind"])
    print("linked, not partner:", al["linked_not_partner"])
    if stale:
        print("resolution rows matching no flag:", stale)
    if missing:
        print(f"{len(missing)} flag(s) have no resolution row:")
        for k in missing:
            print("  ", k)
        sys.exit(1)


if __name__ == "__main__":
    main()
