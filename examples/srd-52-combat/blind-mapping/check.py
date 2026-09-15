#!/usr/bin/env python3
"""Self-check out/blind-map.json against srd-5.2.1.txt and corpus-map.md's rules."""
import json, re, pathlib, sys, hashlib, collections

B = pathlib.Path(__file__).resolve().parent.parent
RAW = (B / "srd-5.2.1.txt").read_text(encoding="utf-8")
M = json.loads((B / "out" / "blind-map.json").read_text(encoding="utf-8"))
MAN = json.loads((B / "corpus-manifest.json").read_text(encoding="utf-8"))
fails = []
def fail(eid, msg): fails.append(f"{eid}: {msg}")

# ---- baseline and top level
if hashlib.sha256(RAW.encode("utf-8")).hexdigest() != M["baseline"]["contentHash"]:
    fail("<map>", "baseline hash mismatch")
if set(M) != {"schemaVersion", "corpus", "baseline", "extent", "entries"}:
    fail("<map>", f"top-level keys {sorted(M)}")
if M["corpus"] not in {c["sourceId"] for c in MAN["corpora"]}:
    fail("<map>", "corpus not in manifest")
ext = M["extent"]
if not (ext.get("unit") == "page" and ext["from"] <= ext["to"]):
    fail("<map>", "bad extent")

ALLOWED = {"id", "name", "locator", "kind", "scope", "clarity", "ambiguity", "dependsOn", "enabledBy",
           "suspendedBy", "beyondAdapter", "definedElsewhere", "absentFrom", "derivedFrom",
           "crossReferences", "evidence", "status", "implementedIn", "tests", "note"}
E = M["entries"]
ids = [e["id"] for e in E]
byid = {e["id"]: e for e in E}
for i, c in collections.Counter(ids).items():
    if c > 1: fail(i, "duplicate id")

# page index of raw text
marks = [(m.start(), int(m.group(1))) for m in re.finditer(r"^\{(\d+)\}$", RAW, re.M)]
def page_at(pos):
    p = None
    for off, n in marks:
        if off <= pos: p = n
        else: break
    return p
def page_start(n):
    for off, k in marks:
        if k == n: return off
    return 0

for e in E:
    eid = e["id"]
    for k in e:
        if k not in ALLOWED: fail(eid, f"unknown field {k}")
    for k in ("id", "name", "kind", "scope", "clarity", "dependsOn", "status", "note"):
        if k not in e: fail(eid, f"missing {k}")
    if e.get("kind") not in {"value", "operation", "assertion"}: fail(eid, "kind")
    if e.get("scope") not in {"in", "out"}: fail(eid, "scope")
    if e.get("clarity") not in {"clear", "ambiguous"}: fail(eid, "clarity")
    if e.get("status") not in {"mapped", "blocked", "implemented", "declined"}: fail(eid, "status")
    if e["scope"] == "out" and e["status"] != "declined": fail(eid, "out but not declined")
    if (e["clarity"] == "ambiguous") != ("ambiguity" in e): fail(eid, "clarity/ambiguity mismatch")
    if "ambiguity" in e:
        a = e["ambiguity"]
        if a.get("fate") != "unresolved" or a.get("unresolvedReason") != "RequiresInterpretation" or not a.get("question"):
            fail(eid, "ambiguity block")
        if "decision" in a: fail(eid, "decision present")
    if e["kind"] == "assertion" and (e["scope"] != "in"): fail(eid, "assertion out of scope")
    for f in ("dependsOn", "enabledBy", "suspendedBy", "derivedFrom"):
        for t in e.get(f, []):
            if t not in byid: fail(eid, f"{f} -> missing {t}")
            elif f != "derivedFrom" and "absentFrom" in byid[t]: fail(eid, f"{f} -> absent entry {t}")
            if t == eid: fail(eid, f"{f} names itself")
    if set(e.get("enabledBy", [])) & set(e.get("suspendedBy", [])): fail(eid, "id in both gate fields")
    derived = "derivedFrom" in e
    if derived:
        if len(e["derivedFrom"]) < 2: fail(eid, "derived from <2")
        for k in ("locator", "evidence", "crossReferences", "absentFrom", "beyondAdapter", "definedElsewhere"):
            if k in e: fail(eid, f"derived entry has {k}")
        for t in e["derivedFrom"]:
            if t in byid and byid[t]["scope"] != "in": fail(eid, f"derived source {t} not in scope")
        continue
    if "locator" not in e or "evidence" not in e: fail(eid, "missing locator/evidence"); continue
    if "absentFrom" in e:
        if e["scope"] != "out" or e["status"] != "declined" or not e["absentFrom"].get("searched"):
            fail(eid, "absentFrom shape")
        for k in ("beyondAdapter", "definedElsewhere", "ambiguity"):
            if k in e: fail(eid, f"absent entry has {k}")
    for x in e.get("crossReferences", []):
        if x["cites"] not in e["evidence"]: fail(eid, f"cites not in evidence: {x['cites']}")
        if ("resolvedBy" in x) == ("unmapped" in x): fail(eid, "crossReference needs exactly one of resolvedBy/unmapped")
        if "resolvedBy" in x and x["resolvedBy"] not in byid: fail(eid, f"resolvedBy missing {x['resolvedBy']}")
    loc = e["locator"]
    if loc.get("sourceId") != M["corpus"]: fail(eid, "sourceId")
    mm = re.fullmatch(r"(.+) / p\. (\d+)", loc["citation"])
    if not mm: fail(eid, "citation grammar"); continue
    heads, N = mm.group(1).split(" / "), int(mm.group(2))
    if e["scope"] == "in" and not (ext["from"] <= N <= ext["to"]): fail(eid, "in-scope citation outside extent")
    pat = r"\s+".join(re.escape(t) for t in e["evidence"].split())
    occ = list(re.finditer(pat, RAW))
    if not occ: fail(eid, "evidence not found"); continue
    for o in occ:
        sp, ep = page_at(o.start()), page_at(o.end())
        inside = any(o.start() <= off < o.end() and k == N for off, k in marks)
        if not (sp == N or inside): fail(eid, f"occurrence at page {sp} does not touch p. {N}")
        region = RAW[page_start(N - 1):o.start()]
        if not re.search(r"^" + re.escape(heads[-1]) + r"$", region, re.M):
            fail(eid, f"heading '{heads[-1]}' not a line between p. {N-1} and quote")
    e["_pages"] = {page_at(o.start()) for o in occ} | {k for o in occ for off, k in marks if o.start() <= off < o.end()}

# dependency cycles (dependsOn and derivedFrom)
for field in ("dependsOn", "derivedFrom"):
    state = {}
    def visit(n, stack):
        state[n] = 1
        for t in byid[n].get(field, []):
            if t not in byid: continue
            if state.get(t) == 1: fail(n, f"{field} cycle via {t}")
            elif t not in state: visit(t, stack)
        state[n] = 2
    for i in ids:
        if i not in state: visit(i, [])

# conflicts
conf = collections.defaultdict(list)
for e in E:
    c = e.get("ambiguity", {}).get("conflict")
    if c: conf[c].append(e)
for c, mem in conf.items():
    if len(mem) < 2: fail(c, "conflict with one member")
    if len({m["ambiguity"]["fate"] for m in mem}) > 1: fail(c, "conflict fates differ")

# coverage
lo, hi = ext["from"], ext["to"]
reached = set()
for e in E:
    if e["scope"] == "in" and "_pages" in e: reached |= e["_pages"]
for p in range(lo, hi + 1):
    if p not in reached: fail("<coverage>", f"page {p} not reached by in-scope evidence")

# absences searched in extent text
ext_text = RAW[page_start(lo):page_start(hi + 1)].lower()
ext_norm = re.sub(r"\s+", " ", ext_text)
for e in E:
    for t in e.get("absentFrom", {}).get("searched", []):
        if t.lower() in ext_text or t.lower() in ext_norm: fail(e["id"], f"absent term found in extent: {t}")

for e in E: e.pop("_pages", None)
cnt = collections.Counter
print("entries", len(E))
print("scope", dict(cnt(e["scope"] for e in E)))
print("kind (all)", dict(cnt(e["kind"] for e in E)))
print("kind (in)", dict(cnt(e["kind"] for e in E if e["scope"] == "in")))
print("clarity (in)", dict(cnt(e["clarity"] for e in E if e["scope"] == "in")))
print("clarity (all)", dict(cnt(e["clarity"] for e in E)))
print("entries with enabledBy", sum(1 for e in E if e.get("enabledBy")), "edges", sum(len(e.get("enabledBy", [])) for e in E))
print("entries with suspendedBy", sum(1 for e in E if e.get("suspendedBy")), "edges", sum(len(e.get("suspendedBy", [])) for e in E))
print("gating entries", sorted({t for e in E for t in e.get("enabledBy", []) + e.get("suspendedBy", [])}))
print("absences", sum(1 for e in E if "absentFrom" in e))
print("derived", sum(1 for e in E if "derivedFrom" in e))
print("crossReferences", sum(len(e.get("crossReferences", [])) for e in E),
      "resolved", sum(1 for e in E for x in e.get("crossReferences", []) if "resolvedBy" in x))
print("conflicts", {c: [m["id"] for m in v] for c, v in conf.items()})
print("dependsOn edges", sum(len(e["dependsOn"]) for e in E))
print("out-of-scope citations beyond extent", [e["id"] for e in E if e["scope"] == "out" and "locator" in e and not (lo <= int(e["locator"]["citation"].rsplit("p. ", 1)[1]) <= hi)])
print("pages reached", sorted(reached))
print("FAILURES", len(fails))
for f in fails: print("  ", f)
sys.exit(1 if fails else 0)
