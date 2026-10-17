#!/usr/bin/env python3
"""Compare the CAN-SPAM blind map against the reference map, field by field (0014).

Adapted from examples/faa-part-107/blind-mapping/compare.py. Two corpora here, one of each
kind of citation, so a link between a reference entry and a blind entry needs all three:

  * the same locator.sourceId;
  * designation: the two citations name the same place.
      - regulation (cfr-16-316, "§ 316.4(a)(2)(iv)"): the same section and either one cites the
        whole section or the two share a top-level paragraph, as in Part 107.
      - statute (usc-15-ch103, USLM identifier "/us/usc/t15/s7704/a/3/A"): one identifier is a
        prefix of the other on "/" boundaries, or both share the path to the subsection (the
        section and the first step under it: s7704/a, s7702/16).
    A citation may be a comma-separated list ("/us/usc/t15/s7706/f/3/B, /us/usc/t15/s7706/f/3/C",
    "§ 316.3(a)(2)(i), (a)(2)(ii)"); any item counts. A regulation citation is read as a path
    of parenthesised steps, so "prefix" and "whole section" are the same test for both corpora.
  * evidence: difflib matching blocks of MIN_BLOCK+ tokens cover at least LINK_SHARE of the
    shorter span. A link that rests on the shared paragraph / subsection alone (neither citation
    contains the other) also needs one span to be EVIDENCE_NESTED-contained in the other: sibling
    provisions repeat each other's boilerplate ("it is unlawful for any person to initiate the
    transmission ...", "a recipient reasonably interpreting the ...") and passed LINK_SHARE
    without quoting the same text (found by hand-checking the first run's links).

PARTNER of a reference entry: among its links, the highest cov_ref * cov_blind + name-word
Jaccard, as in Part 107. Names only choose among entries that already link.

Compared on each (reference, partner) pair: kind, scope, clarity, ambiguity presence and fate,
definedElsewhere presence and target, dependsOn / enabledBy / suspendedBy edge by edge, and
evidence nesting (a proxy for whether each side's evidence supports its entry).

crossReferences are compared across the whole map, not per pair, because the two maps split
the same sentence differently and a declaration sits on whichever entry quotes the pointer.
Each declaration is normalised to (section of the declaring entry, cited target): a defined
term is its lower-cased text; "section 7704(a)(1) of this title", "15 U.S.C. 7704(a)(1)" and
"subsection (a)" in a section 7704 entry are all section 7704's subsection (a) or the paragraph
named; "paragraph (c) of this section" in a § 316.5 entry is § 316.5(c); a pointer to another
title stays its own lower-cased text. A target one map declares and the other declares nowhere
is a flag on that key.

Edge translation. A blind edge target stands for every reference entry it LINKS to (not only
the one it is partner of), so an edge into a split entry still compares. A reference edge is
matched when some blind edge target links to the edge's target. A blind edge whose target links
to no reference entry cannot be compared and is skipped (listed in results.json).

This script writes the alignment and the flags and no verdicts: adjudication is a later,
separate step, so flags_by_verdict is empty.

Usage: python3 examples/can-spam/blind-mapping/compare.py
       writes results.json beside this file and prints a summary
"""
import difflib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REF_PATH = os.path.join(os.path.dirname(HERE), "corpus-map.json")
BLIND_PATH = os.path.join(HERE, "blind-map.json")

MIN_BLOCK = 4
LINK_SHARE = 0.5
EVIDENCE_NESTED = 0.9
NAME_WEIGHT = 1.0

STOP = {"the", "and", "a", "an", "of", "to", "is", "are", "or", "in", "on", "by", "for",
        "its", "may", "be", "each", "one", "all", "with", "from", "has", "can", "not", "no"}


def tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


# --- designations ---------------------------------------------------------------------------

def reg_items(citation):
    """[(section, path)] of a regulation citation or a comma-separated list of them (the section
    is stated once, in the first item): "§ 316.3(a)(2)(i), (a)(2)(ii)" is (316.3, (a, 2, i)) and
    (316.3, (a, 2, ii)); "§ 316.5" is (316.5, ())."""
    m = re.match(r"§\s*(\d+\.\d+)", citation.strip())
    sec = m.group(1)
    out = []
    for item in citation.split(","):
        out.append((sec, tuple(re.findall(r"\(([^)]+)\)", item))))
    return out


def usc_items(citation):
    """[(section, path)] of a USLM identifier or a comma-separated list of them."""
    out = []
    for item in citation.split(","):
        p = item.strip().strip("/").split("/")
        out.append((p[3], tuple(p[4:])))
    return out


def place(source_id, r, b):
    """How two citations name the same place: 'contains' (one item's path is a prefix of the
    other's on step boundaries, a whole-section citation containing every path in the section),
    'shared' (no containment, but both items share the top-level paragraph / the subsection), or
    None."""
    items = reg_items if source_id.startswith("cfr") else usc_items
    best = None
    for (sx, px) in items(r):
        for (sy, py) in items(b):
            if sx != sy:
                continue
            n = min(len(px), len(py))
            if px[:n] == py[:n]:
                return "contains"
            if px[:1] == py[:1]:
                best = "shared"
    return best


def section_of(entry):
    """The section an entry sits in: '7704' or '316.5'."""
    c = entry["locator"]["citation"]
    if entry["locator"]["sourceId"].startswith("cfr"):
        return reg_items(c)[0][0]
    return usc_items(c)[0][0][1:]


# --- alignment ------------------------------------------------------------------------------

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
            sid = r["locator"]["sourceId"]
            if sid != b["locator"]["sourceId"]:
                continue
            how = place(sid, r["locator"]["citation"], b["locator"]["citation"])
            if how is None:
                continue
            s = shared(rt[r["id"]], bt[b["id"]])
            lr, lb = len(rt[r["id"]]), len(bt[b["id"]])
            if not lr or not lb or s < LINK_SHARE * min(lr, lb):
                continue
            # Two sibling provisions under one paragraph repeat each other's boilerplate
            # ("a recipient reasonably interpreting ...", "it is unlawful for any person to
            # initiate the transmission ..."), enough to pass LINK_SHARE. A link that rests on
            # the shared paragraph alone, not on one citation containing the other, therefore
            # also needs one span to contain the other.
            if how == "shared" and max(s / lr, s / lb) < EVIDENCE_NESTED:
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


# --- crossReferences ------------------------------------------------------------------------

def norm_term(t):
    t = re.sub(r"[’']s\b", "", t.lower().strip())
    t = re.sub(r"\s+", " ", t)
    words = t.split(" ")
    if len(words[-1]) > 3 and words[-1].endswith("s") and not words[-1].endswith("ss"):
        words[-1] = words[-1][:-1]
    return " ".join(words)


def first_group(chain):
    m = re.match(r"\(([a-z0-9]+)\)", chain)
    return f"({m.group(1)})" if m else ""


def xref_target(entry, cites):
    """(declaring key, normalised target) of one declaration."""
    sec = section_of(entry)
    cfr = entry["locator"]["sourceId"].startswith("cfr")
    key = f"§ {sec}" if cfr else f"15 U.S.C. {sec}"
    t = re.sub(r"\s+", " ", cites.strip().lower())
    m = re.search(r"(?:section\s+|u\.s\.c\.\s*)(77\d\d)(\s*[-–]\s*(77\d\d))?((?:\([a-z0-9]+\))*)", t)
    other_title = re.search(r"title\s+(?!15\b)\d+|\b(?!15\b)\d+\s+u\.s\.c|\b\d+ cfr(?! 316)", t)
    if m and not other_title:
        if m.group(2):
            return key, "15 U.S.C. 7701-7713"
        return key, f"15 U.S.C. {m.group(1)}{first_group(m.group(4))}"
    m = re.search(r"cfr\s*(316\.\d+)((?:\([a-z0-9]+\))*)", t)
    if m:
        return key, f"§ {m.group(1)}{first_group(m.group(2))}"
    if re.fullmatch(r"this part", t):
        return key, "part 316"
    if t in ("this chapter",):
        return key, "chapter 103"
    pointer = re.match(r"(?:\w+ )*?(subsections?|paragraphs?|subparagraphs?|clauses?|subclauses?)\s*\(", t)
    if pointer:
        kind = pointer.group(1)
        g = re.search(r"\(([a-z0-9]+)\)", t[pointer.end() - 1:])
        if cfr and "of this section" in t:
            return key, f"§ {sec}({g.group(1)})"
        if kind.startswith("subsection") and not cfr:
            return key, f"15 U.S.C. {sec}({g.group(1)})"
        if not cfr:  # relative to the subsection the declaring entry sits in
            c = entry["locator"]["citation"].strip().split(",")[0].strip("/").split("/")
            top = c[4] if len(c) > 4 else ""
            return f"{key}({top})", t
        return key, t
    if re.search(r"this (section|subsection|paragraph|title)", t) and len(t) < 20:
        return key, t
    return key, norm_term(t)


def xref_keys(m):
    """{(declaring key, target): [(entry id, 'resolvedBy <id>' | 'unmapped')]} for a whole map."""
    out = {}
    for e in m["entries"]:
        for x in e.get("crossReferences") or []:
            k = xref_target(e, x["cites"])
            how = f"resolvedBy {x['resolvedBy']}" if "resolvedBy" in x else "unmapped"
            out.setdefault(k, []).append((e["id"], how))
    return out


# --- comparison -----------------------------------------------------------------------------

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
    # would otherwise go uncompared. Compared on scope, clarity and ambiguity presence only,
    # against the reference entry it links to best; kind is not compared (a split changes
    # kind by construction).
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
            cites = {x["cites"] for i, _ in bk[k] for x in B[i].get("crossReferences") or []
                     if xref_target(B[i], x["cites"]) == k}
            quoting = [e["id"] for e in ref["entries"]
                       if section_of(e) == section_of(B[ids[0][0]])
                       and e["locator"]["sourceId"] == B[ids[0][0]]["locator"]["sourceId"]
                       and any(c.lower() in e["evidence"].lower() for c in cites)]
            entry = ",".join(quoting) or None
        flags.append({"entry": entry, "field": "crossReferences",
                      "detail": f"{k[1]} cited from {k[0]}: declared only in the {side} map",
                      "blind": None if k in rk else ids[0][0],
                      "ref_value": rk.get(k) and [f"{i}: {h}" for i, h in rk[k]],
                      "blind_value": bk.get(k) and [f"{i}: {h}" for i, h in bk[k]]})
    return al, flags, skipped


def key(f):
    return f"{f['entry']}|{f['field']}|{f['blind']}|{f['detail']}"


def main():
    ref = json.load(open(REF_PATH, encoding="utf-8"))
    blind = json.load(open(BLIND_PATH, encoding="utf-8"))
    al, flags, skipped = compare(ref, blind)
    by_field = {}
    for f in flags:
        f["key"] = key(f)
        by_field[f["field"]] = by_field.get(f["field"], 0) + 1
    result = {
        "reference": {"path": "examples/can-spam/corpus-map.json", "entries": len(ref["entries"])},
        "blind": {"path": "blind-map.json", "entries": len(blind["entries"])},
        "parameters": {"MIN_BLOCK": MIN_BLOCK, "LINK_SHARE": LINK_SHARE,
                       "EVIDENCE_NESTED": EVIDENCE_NESTED, "NAME_WEIGHT": NAME_WEIGHT},
        "alignment": al,
        "edges_not_comparable": skipped,
        "flag_count": len(flags),
        "flags_by_field": by_field,
        "flags_by_verdict": {},
        "flags": flags,
    }
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as h:
        json.dump(result, h, indent=2, ensure_ascii=False)
        h.write("\n")
    print(f"flags: {len(flags)}  {by_field}")
    print(f"reference entries: {len(ref['entries'])}  aligned: {len(al['links'])}  "
          f"unaligned: {len(al['unaligned_ref'])}")
    print(f"blind entries: {len(blind['entries'])}  unaligned: {len(al['unaligned_blind'])}  "
          f"linked, not partner: {len(al['linked_not_partner'])}")
    print("unaligned ref:", al["unaligned_ref"])
    print("unaligned blind:", al["unaligned_blind"])


if __name__ == "__main__":
    main()
