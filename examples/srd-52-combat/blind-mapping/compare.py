#!/usr/bin/env python3
"""Compare the srd-52-combat blind map against the reference map, field by field (0014).

Copied from examples/hoyle-backgammon/blind-mapping/compare.py, with only the reference commit
and path changed. That comparator aligns by page, and so does this corpus's locator grammar
(`heading-path-and-printed-page`); the `{N}` markers in the extracted text are the same shape as
Hoyle's. Its description, unchanged:

Adapted from examples/faa-part-107/blind-mapping/compare.py, which was adapted from
examples/blind-mapping-trial/compare.py. The trial's alignment is kept, because this corpus
cites by page as the trial's did:

  * tokens: lower-cased [a-z0-9]+ words, after deleting page markers {273} and footnote
    markers [65].
  * a LINK between reference entry r and blind entry b: difflib matching blocks of MIN_BLOCK+
    tokens cover at least LINK_SHARE of the shorter span, and the cited pages differ by at most
    PAGE_SLACK.
  * PARTNER of r: among its links, the highest cov_ref * cov_blind + name-word Jaccard.

From the Part 107 comparator: edges translate through links rather than partners; a blind entry
that links but is nobody's partner is compared on scope, clarity and ambiguity against the
reference entry it links to best; every flag must have a row in resolutions.json, and the script
exits 1 otherwise.

Added for this map's fields:

  * derived entries (no evidence). A reference derived entry links to a blind derived entry
    when at least one source of each translates to a source of the other through links. They
    are then compared as any pair, plus derivedFrom source by source.
  * beyondAdapter and absentFrom, presence on each pair.
  * ambiguity.conflict, presence on each pair (the slugs are the mappers' own words).
  * crossReferences, compared per pair by the cited phrase (page markers removed, lower-cased):
    a phrase one side declares and the other does not, on entries that both quote it, is a
    flag; where both declare it, resolvedBy vs unmapped, and resolvedBy targets through links.

It reads the reference from git at REFERENCE_COMMIT, so the flags are the ones raised against the
map before it was corrected.

Every flag must have a row in resolutions.json, the adjudication record, whose shape and whose
declared verdict vocabulary are 0059's; the script exits 1 otherwise, and 1 again if the record
does not declare a `verdicts` legend, an `unsettledVerdict` the legend defines, and a verdict the
legend defines on every row.

Usage: compare.py            writes results.json and resolutions.json's structural
                            fields beside this file, and prints a summary
       compare.py --table    prints the resolution table as markdown
       compare.py --dry      prints the summary and writes neither file
       compare.py --against PATH   compare a working-tree map instead (implies --dry)
"""
import difflib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
REFERENCE_COMMIT = "5216c6280c559387eee8ffb51d5a4aa2344300a4"
REFERENCE_PATH = "examples/srd-52-combat/corpus-map.json"
BLIND_PATH = os.path.join(HERE, "blind-map.json")
RES_PATH = os.path.join(HERE, "resolutions.json")

MIN_BLOCK = 4
LINK_SHARE = 0.5
PAGE_SLACK = 1
EVIDENCE_NESTED = 0.9
NAME_WEIGHT = 1.0

STOP = {"the", "and", "a", "an", "of", "to", "is", "are", "or", "in", "on", "by", "for",
        "its", "his", "may", "be", "each", "one", "all", "with", "what", "who", "how",
        "has", "can", "them", "from", "not", "no"}


def tokens(text):
    text = re.sub(r"\{\d+\}|\[\d+\]", " ", text or "")
    return re.findall(r"[a-z0-9]+", text.lower())


def page(e):
    m = re.search(r"p\.\s*(\d+)", (e.get("locator") or {}).get("citation", ""))
    return int(m.group(1)) if m else None


def pages(e):
    """The cited page through every page marker inside the evidence: a span may run over
    several pages (die-faces runs 277-280) and still cite the first."""
    p = page(e)
    if p is None:
        return None
    inside = [int(n) for n in re.findall(r"\{(\d+)\}", e.get("evidence") or "")]
    return (min([p] + inside), max([p] + inside))


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
    if len(w) > 3 and w[-1] == w[-2]:
        w = w[:-1]
    return w


def name_words(name):
    return {stem(w) for w in re.findall(r"[a-z]+", name.lower()) if len(w) >= 3 and w not in STOP}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def score(c):
    return c["cov_ref"] * c["cov_blind"] + NAME_WEIGHT * c["name"]


def align(ref, blind):
    R = [e for e in ref["entries"] if "derivedFrom" not in e]
    Bl = [e for e in blind["entries"] if "derivedFrom" not in e]
    rt = {e["id"]: tokens(e.get("evidence")) for e in R}
    bt = {e["id"]: tokens(e.get("evidence")) for e in Bl}
    links = {}
    for r in R:
        for b in Bl:
            pr, pb = pages(r), pages(b)
            if pr is None or pb is None or pr[0] - pb[1] > PAGE_SLACK or pb[0] - pr[1] > PAGE_SLACK:
                continue
            s = shared(rt[r["id"]], bt[b["id"]])
            lr, lb = len(rt[r["id"]]), len(bt[b["id"]])
            if not lr or not lb or s < LINK_SHARE * min(lr, lb):
                continue
            links.setdefault(r["id"], {})[b["id"]] = {
                "shared": s, "cov_ref": round(s / lr, 3), "cov_blind": round(s / lb, 3),
                "name": round(jaccard(name_words(r["name"]), name_words(b["name"])), 3),
            }
    # Derived entries: link through their sources.
    b2r = {}
    for rid, c in links.items():
        for bid in c:
            b2r.setdefault(bid, set()).add(rid)
    for r in (e for e in ref["entries"] if "derivedFrom" in e):
        for b in (e for e in blind["entries"] if "derivedFrom" in e):
            reach = set().union(*(b2r.get(s, set()) for s in b["derivedFrom"]))
            common = reach & set(r["derivedFrom"])
            if common:
                n = len(common)
                links.setdefault(r["id"], {})[b["id"]] = {
                    "derived": True, "shared_sources": sorted(common),
                    "cov_ref": round(n / len(r["derivedFrom"]), 3),
                    "cov_blind": round(min(1.0, n / len(b["derivedFrom"])), 3),
                    "name": round(jaccard(name_words(r["name"]), name_words(b["name"])), 3),
                }
    partner = {rid: max(c, key=lambda bid: (score(c[bid]), bid)) for rid, c in links.items()}
    linked_blind = {bid for c in links.values() for bid in c}
    return {
        "links": links,
        "partner": partner,
        "unaligned_ref": sorted(e["id"] for e in ref["entries"] if e["id"] not in links),
        "unaligned_blind": sorted(e["id"] for e in blind["entries"] if e["id"] not in linked_blind),
        "linked_not_partner": sorted(linked_blind - set(partner.values())),
    }


def phrase(cites):
    """Cited words without page markers, lower-cased. A pointer made only of a footnote marker
    ([68]) has no words, and is kept as written so it matches nothing but itself."""
    return " ".join(tokens(cites)) or cites


def compare(ref, blind):
    al = align(ref, blind)
    R = {e["id"]: e for e in ref["entries"]}
    B = {e["id"]: e for e in blind["entries"]}
    b2r = {}
    for rid, c in al["links"].items():
        for bid in c:
            b2r.setdefault(bid, set()).add(rid)
    flags, skipped = [], []

    def flag(rid, field, detail, ref_value, blind_value, bid):
        flags.append({"entry": rid, "field": field, "detail": detail, "blind": bid,
                      "ref_value": ref_value, "blind_value": blind_value})

    for rid in al["unaligned_ref"]:
        flag(rid, "entry", "no blind entry quotes this text", None, None, None)
    for bid in al["unaligned_blind"]:
        flag(None, "entry", "no reference entry quotes this text", None, None, bid)

    def edges(rid, bid, field):
        r, b = R[rid], B[bid]
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

    for rid, bid in sorted(al["partner"].items()):
        r, b = R[rid], B[bid]
        for field in ("kind", "scope", "clarity"):
            if r.get(field) != b.get(field):
                flag(rid, field, "differs", r.get(field), b.get(field), bid)
        ra, ba = r.get("ambiguity"), b.get("ambiguity")
        if bool(ra) != bool(ba):
            flag(rid, "ambiguity", "present in one map only", bool(ra), bool(ba), bid)
        elif ra and ba:
            if ra.get("fate") != ba.get("fate"):
                flag(rid, "ambiguity.fate", "differs", ra.get("fate"), ba.get("fate"), bid)
            if bool(ra.get("conflict")) != bool(ba.get("conflict")):
                flag(rid, "ambiguity.conflict", "present in one map only",
                     ra.get("conflict"), ba.get("conflict"), bid)
        for field in ("beyondAdapter", "absentFrom", "definedElsewhere"):
            if bool(r.get(field)) != bool(b.get(field)):
                flag(rid, field, "present in one map only", r.get(field), b.get(field), bid)
        for field in ("dependsOn", "enabledBy", "suspendedBy", "derivedFrom"):
            edges(rid, bid, field)
        link = al["links"][rid][bid]
        if not link.get("derived"):
            if link["cov_ref"] < EVIDENCE_NESTED and link["cov_blind"] < EVIDENCE_NESTED:
                flag(rid, "evidence", "spans overlap but neither contains the other",
                     link["cov_ref"], link["cov_blind"], bid)
            elif link["cov_blind"] < EVIDENCE_NESTED:
                flag(rid, "evidence", "blind span quotes text the reference span omits",
                     link["cov_ref"], link["cov_blind"], bid)
            elif link["cov_ref"] < EVIDENCE_NESTED:
                flag(rid, "evidence", "reference span quotes text the blind span omits",
                     link["cov_ref"], link["cov_blind"], bid)

    for bid in al["linked_not_partner"]:
        cands = {rid: c[bid] for rid, c in al["links"].items() if bid in c}
        rid = max(cands, key=lambda i: (score(cands[i]), i))
        r, b = R[rid], B[bid]
        for field in ("scope", "clarity"):
            if r.get(field) != b.get(field):
                flag(rid, field, "differs (blind entry links here but is not its partner)",
                     r.get(field), b.get(field), bid)
        if bool(r.get("ambiguity")) != bool(b.get("ambiguity")):
            flag(rid, "ambiguity", "present in one map only (blind entry links here but is not "
                                   "its partner)", bool(r.get("ambiguity")),
                 bool(b.get("ambiguity")), bid)

    # crossReferences, map-wide by cited phrase: the two maps put a pointer on whichever entry
    # quotes it, so a declaration is matched against any declaration of the same phrase.
    def decls(m):
        out = {}
        for e in m["entries"]:
            for x in e.get("crossReferences") or []:
                out.setdefault(phrase(x["cites"]), []).append((e["id"], x))
        return out
    rd, bd = decls(ref), decls(blind)
    for p in sorted(set(rd) | set(bd)):
        rv = [f"{i}: " + (f"resolvedBy {x['resolvedBy']}" if "resolvedBy" in x else "unmapped")
              for i, x in rd.get(p, [])]
        bv = [f"{i}: " + (f"resolvedBy {x['resolvedBy']}" if "resolvedBy" in x else "unmapped")
              for i, x in bd.get(p, [])]
        if p in rd and p in bd:
            rx, bx = rd[p][0][1], bd[p][0][1]
            if ("resolvedBy" in rx) != ("resolvedBy" in bx):
                flag(rd[p][0][0], "crossReferences", f"'{p}': resolvedBy in one map, unmapped in "
                     "the other", rv, bv, bd[p][0][0])
            elif "resolvedBy" in rx and rx["resolvedBy"] not in b2r.get(bx["resolvedBy"], set()):
                flag(rd[p][0][0], "crossReferences", f"'{p}': resolved to entries that do not link",
                     rv, bv, bd[p][0][0])
            continue
        if p in rd:
            quoting = [e["id"] for e in blind["entries"] if p in " ".join(tokens(e.get("evidence")))]
            flag(rd[p][0][0], "crossReferences", f"'{p}': declared only in the reference map",
                 rv, None, ",".join(quoting) or None)
        else:
            quoting = [e["id"] for e in ref["entries"] if p in " ".join(tokens(e.get("evidence")))]
            flag(",".join(quoting) or None, "crossReferences",
                 f"'{p}': declared only in the blind map", None, bv, bd[p][0][0])
    return al, flags, skipped


def load_reference():
    if "--against" in sys.argv:
        return json.load(open(sys.argv[sys.argv.index("--against") + 1], encoding="utf-8"))
    out = subprocess.run(["git", "show", f"{REFERENCE_COMMIT}:{REFERENCE_PATH}"],
                         cwd=REPO, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def key(f):
    return f"{f['entry']}|{f['field']}|{f['blind']}|{f['detail']}"


# The adjudication record (0059). Every trial's is one shape: `verdicts` is the legend, in the
# file rather than in a README; `unsettledVerdict` names the one term that means *the corpus does
# not settle it*, which is the term `check-map.py --only superposition` turns on; and every row
# carries its verdict in a field. The structural fields -- `id`, `field`, `entries` -- belong to
# this script, because they are the comparison's; the verdict and the prose belong to the
# adjudicator and are copied verbatim, in the order that row already had them in.
ROW_PROSE = ("verdict", "reason", "locator", "quote")


def prose_of(row):
    return {k: row[k] for k in row if k in ROW_PROSE}


def read_record():
    """(the record, {row id: row}, [problem]) from resolutions.json."""
    record = json.load(open(RES_PATH, encoding="utf-8")) if os.path.exists(RES_PATH) else {}
    legend, rows, problems = record.get("verdicts"), record.get("adjudications"), []
    if not isinstance(legend, dict) or not legend:
        problems.append("resolutions.json declares no `verdicts` legend (0059)")
        legend = {}
    if record.get("unsettledVerdict") not in legend:
        problems.append(f"`unsettledVerdict` is {record.get('unsettledVerdict')!r}, which the "
                        f"`verdicts` legend does not define (0059)")
    if not isinstance(rows, list):
        problems.append("resolutions.json carries no `adjudications` list (0059)")
        rows = []
    by_id = {}
    for row in rows:
        by_id[row.get("id")] = row
        if legend and row.get("verdict") not in legend:
            problems.append(f"row {row.get('id')!r} is answered {row.get('verdict')!r}, which "
                            f"the `verdicts` legend does not define")
    return record, by_id, problems


def write_record(record, by_id, flags):
    """resolutions.json, its structural fields rewritten from the flags this run raised."""
    rows, seen = [], set()
    for f in flags:
        seen.add(f["key"])
        rows.append({"id": f["key"], "field": f["field"],
                     "entries": [i for i in (f["entry"], f["blind"]) if i],
                     **prose_of(by_id.get(f["key"]) or {})})
    # A row matching no flag is kept and reported, never dropped: it is somebody's adjudication,
    # and this script is not the thing that decides it is spent.
    rows += [by_id[i] for i in sorted(set(by_id) - seen, key=str)]
    written = dict(record)
    written["adjudications"] = rows
    with open(RES_PATH, "w", encoding="utf-8") as h:
        json.dump(written, h, indent=2, ensure_ascii=False)
        h.write("\n")


def main():
    ref = load_reference()
    blind = json.load(open(BLIND_PATH, encoding="utf-8"))
    al, flags, skipped = compare(ref, blind)
    record, by_id, problems = read_record()
    for f in flags:
        f["key"] = key(f)
        row = by_id.get(f["key"])
        f["resolution"] = prose_of(row) if row else None
    missing = [f["key"] for f in flags if not f["resolution"]]
    stale = sorted(set(by_id) - {f["key"] for f in flags}, key=str)

    if "--table" in sys.argv:
        print("| # | reference entry | blind entry | field | reference | blind | verdict | quote / reason |")
        print("|---|---|---|---|---|---|---|---|")
        for i, f in enumerate(flags, 1):
            r = f["resolution"] or {}
            cell = lambda v: "" if v is None else str(v).replace("|", "\\|").replace("\n", " ")
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
        "parameters": {"MIN_BLOCK": MIN_BLOCK, "LINK_SHARE": LINK_SHARE, "PAGE_SLACK": PAGE_SLACK,
                       "EVIDENCE_NESTED": EVIDENCE_NESTED, "NAME_WEIGHT": NAME_WEIGHT},
        "alignment": al,
        "edges_not_comparable": skipped,
        "flag_count": len(flags),
        "flags_by_field": by_field,
        "flags_by_verdict": by_verdict,
        "flags": flags,
    }
    dry = "--dry" in sys.argv or "--against" in sys.argv
    if not dry:
        with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as h:
            json.dump(result, h, indent=2, ensure_ascii=False)
            h.write("\n")
        write_record(record, by_id, flags)
    print(f"flags: {len(flags)}  {by_field}")
    print(f"verdicts: {by_verdict}")
    print("unaligned ref:", al["unaligned_ref"])
    print("unaligned blind:", al["unaligned_blind"])
    print("linked, not partner:", al["linked_not_partner"])
    if stale and not dry:
        print("resolution rows matching no flag:", stale)
    if problems and not dry:
        print(f"{len(problems)} problem(s) with the adjudication record's shape:")
        for p in problems:
            print("  ", p)
        sys.exit(1)
    if missing and not dry:
        print(f"{len(missing)} flag(s) have no resolution row:")
        for k in missing:
            print("  ", k)
        sys.exit(1)


if __name__ == "__main__":
    main()
