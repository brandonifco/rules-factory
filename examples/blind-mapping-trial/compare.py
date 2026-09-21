#!/usr/bin/env python3
"""Trial 6 -- compare a blind second mapping against a reference map, field by field.

Two jobs, one script:

  1. The comparator. Given a reference map and a blind map of the same corpus slice, align
     entries by what they quote, not by id, and list every field on which an aligned pair
     disagrees. A disagreement is a flag for a person to resolve against the corpus.
  2. The measurement. Run the comparator on the clean reference (the baseline: every flag
     there is a cost), then on the reference with each of trial 5's comprehension-stratum
     injections applied exactly as injections.py applies them, and score an injection
     CAUGHT when a flag on the injected entry appears that the baseline did not have.

Nothing here reads the corpus. Alignment and the evidence check are both text overlap
between the two maps' `evidence` spans, which is a proxy for "does the evidence support
the entry" and not that question. See README.md.

Alignment, precisely:

  * tokens: lower-cased [a-z0-9]+ words, after deleting page markers {273} and footnote
    markers [65].
  * shared text between two spans: difflib's matching blocks over the token lists, counting
    only blocks of MIN_BLOCK or more tokens, so shared function words do not link entries.
  * a LINK between reference entry r and blind entry b: shared >= LINK_SHARE of the shorter
    span, and the cited pages differ by at most PAGE_SLACK.
  * the PARTNER of r, the one blind entry its fields are compared with: among r's links, the
    highest cov_r * cov_b + name-word Jaccard (content words of 3+ letters, crudely stemmed,
    stopwords removed), where cov_r and cov_b are the shared tokens as a fraction of each
    span. Names only choose among entries that already quote the same text; they never
    create a link. Name-free choice fails where one map quotes a claim sentence and the
    other quotes the whole passage around it (die-faces). This is a heuristic; the
    alignment it produced is printed in results.json for checking.
  * unaligned reference entry: no link. Unaligned blind entry: no link to any reference entry.
    A blind entry that links but is nobody's partner is reported separately, not flagged.

Fields compared on each (r, partner) pair: kind, scope, clarity, ambiguity presence,
ambiguity fate (when both have one), dependsOn and gatedBy edge by edge (blind ids
translated to reference ids through the partner relation), and evidence nesting.

Usage: compare.py            writes results.json beside this file and prints a summary
"""
import copy as copymod
import difflib
import json
import os
import re
import subprocess
import sys

# Imports another of this repository's files by path, and the loader writes that file's
# bytecode beside it. No caller's environment is relied on to stop it (#384): module level
# and above the import, because the loader reads the flag when the import happens.
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "examples", "injection-trial"))
from injections import INJECTIONS, FACTORY  # noqa: E402

# The reference trial 5 injected into: the factory copy at the commit its run-trial.py pins.
REFERENCE_COMMIT = "ecc53b8c231c0eef67ee081c29043ddbf8004336"
REFERENCE_PATH = "examples/hoyle-backgammon/corpus-map.json"
BLIND_PATH = os.path.join(HERE, "blind-map.json")

MIN_BLOCK = 4
LINK_SHARE = 0.5
PAGE_SLACK = 1
EVIDENCE_NESTED = 0.9
NAME_WEIGHT = 1.0

# Verdicts the blind mapper reported having seen in docs/corpus-map.md or docs/method.md
# before mapping. Ids are the reference map's; `conflict` is the points-open-to-an-entering-man
# conflict, which touches the three entries that carry it.
LEAKED = {
    "point-designations", "direction-of-travel", "strategy-advice", "die-faces",
    "doubling-cube", "game-value", "must-play-whole-throw", "stake-multiplier",
    "enter-from-bar", "legal-destination", "full-table-suspension", "bearing-off-doublets",
    "bearing-off-eligible", "move-by-pip", "bearing-off-highest", "starting-position",
    "opening-roll",
}
LEAKED_CONFLICT_ENTRIES = {"legal-destination", "enter-from-bar", "full-table-suspension"}

# Not on the mapper's list, found by searching the two docs it saw for the injected entries'
# subject matter. Recorded apart so the mapper's own report stays what it was.
LEAKED_FOUND_IN_DOCS = {
    "agreed-backgammon-multiple": "docs/method.md and docs/corpus-map.md both quote 'either "
                                  "thrice or four times (as may have been agreed)' as the "
                                  "clearest case of a standard that is not an ambiguity",
    "board-tables": "docs/method.md: 'Twelve points to a table named ace through six'",
}

STOP = {"the", "and", "a", "an", "of", "to", "is", "are", "or", "in", "on", "by", "for",
        "its", "his", "may", "be", "each", "one", "all", "with", "what", "who", "how",
        "has", "can", "them"}


def tokens(text):
    text = re.sub(r"\{\d+\}|\[\d+\]", " ", text)
    return re.findall(r"[a-z0-9]+", text.lower())


def page(e):
    m = re.search(r"p\. (\d+)", e["locator"]["citation"])
    return int(m.group(1)) if m else None


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


def align(ref, blind):
    rt = {e["id"]: tokens(e["evidence"]) for e in ref["entries"]}
    bt = {e["id"]: tokens(e["evidence"]) for e in blind["entries"]}
    links = {}  # ref id -> {blind id: stats}
    for r in ref["entries"]:
        for b in blind["entries"]:
            pr, pb = page(r), page(b)
            if pr is None or pb is None or abs(pr - pb) > PAGE_SLACK:
                continue
            s = shared(rt[r["id"]], bt[b["id"]])
            lr, lb = len(rt[r["id"]]), len(bt[b["id"]])
            if not lr or not lb or s < LINK_SHARE * min(lr, lb):
                continue
            links.setdefault(r["id"], {})[b["id"]] = {
                "shared": s, "cov_ref": round(s / lr, 3), "cov_blind": round(s / lb, 3),
                "name": round(jaccard(name_words(r["name"]), name_words(b["name"])), 3),
            }
    partner = {}
    for rid, cands in links.items():
        partner[rid] = max(cands, key=lambda bid: (
            cands[bid]["cov_ref"] * cands[bid]["cov_blind"] + NAME_WEIGHT * cands[bid]["name"], bid))
    linked_blind = {bid for c in links.values() for bid in c}
    return {
        "links": links,
        "partner": partner,
        "unaligned_ref": sorted(e["id"] for e in ref["entries"] if e["id"] not in links),
        "unaligned_blind": sorted(e["id"] for e in blind["entries"] if e["id"] not in linked_blind),
        "linked_not_partner": sorted(linked_blind - set(partner.values())),
    }


def compare(ref, blind):
    al = align(ref, blind)
    R = {e["id"]: e for e in ref["entries"]}
    B = {e["id"]: e for e in blind["entries"]}
    # blind id -> reference ids it is partner of
    back = {}
    for rid, bid in al["partner"].items():
        back.setdefault(bid, set()).add(rid)

    flags = []

    def flag(rid, field, detail, ref_value, blind_value, bid):
        flags.append({"entry": rid, "field": field, "detail": detail, "blind": bid,
                      "ref_value": ref_value, "blind_value": blind_value})

    for rid in al["unaligned_ref"]:
        flag(rid, "entry", "no blind entry quotes this text", None, None, None)
    for bid in al["unaligned_blind"]:
        flags.append({"entry": None, "field": "entry", "detail": "no reference entry quotes this text",
                      "blind": bid, "ref_value": None, "blind_value": None})

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
        for field in ("dependsOn", "gatedBy"):
            rset = set(r.get(field) or [])
            braw = list(b.get(field) or [])
            translated = set()
            for dep in braw:
                translated |= back.get(dep, set())
            translated.discard(rid)
            for d in sorted(rset - translated):
                flag(rid, field, f"reference has edge to {d}; blind has no edge to its partner",
                     d, None, bid)
            for dep in braw:
                t = back.get(dep, set()) - {rid}
                if not t:
                    continue  # blind dep has no reference counterpart; not comparable
                if not (t & rset):
                    flag(rid, field, f"blind has edge to {dep}; reference has no edge to "
                                     f"its partner", sorted(t), dep, bid)
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
    return al, flags


def key(f):
    """A flag's identity for baseline comparison. Values are excluded on purpose for
    fields whose value the injection changes (kind, scope, ...): a flag that was already
    raised on that field is not a new flag because its value moved."""
    return (f["entry"], f["field"], f["detail"], f["blind"])


def load_reference():
    out = subprocess.run(["git", "show", f"{REFERENCE_COMMIT}:{REFERENCE_PATH}"],
                         cwd=REPO, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def injected_entries(before, after):
    B = {e["id"]: e for e in before["entries"]}
    A = {e["id"]: e for e in after["entries"]}
    return sorted(i for i in set(A) | set(B) if A.get(i) != B.get(i))


def changed_fields(before, after, entry_id):
    B = {e["id"]: e for e in before["entries"]}.get(entry_id)
    A = {e["id"]: e for e in after["entries"]}.get(entry_id)
    if B is None or A is None:
        return ["entry"]
    return sorted(k for k in set(A) | set(B) if A.get(k) != B.get(k))


def measure(ref, blind):
    base_al, base_flags = compare(ref, blind)
    base_keys = {key(f) for f in base_flags}
    runs = []
    for inj in INJECTIONS:
        if inj["stratum"] != "human" or FACTORY not in inj["applies"]:
            continue
        mutated = copymod.deepcopy(ref)
        inj["patch"](mutated, FACTORY)
        touched = injected_entries(ref, mutated)
        fields = {t: changed_fields(ref, mutated, t) for t in touched}
        al, flags = compare(mutated, blind)
        new = [f for f in flags if key(f) not in base_keys]
        on_entry = [f for f in new if f["entry"] in touched]
        now = {key(f) for f in flags}
        gone = sorted((k for k in base_keys if k not in now), key=str)
        partners = {t: al["partner"].get(t) for t in touched}
        on_field = [f for f in on_entry
                    if "entry" in fields[f["entry"]]
                    or f["field"].split(".")[0] in fields[f["entry"]]]
        runs.append({
            "id": inj["id"], "family": inj["family"],
            "counted": not inj.get("probe") and not inj.get("invalid"),
            "probe": bool(inj.get("probe")),
            "trial5_caught": inj["id"] == "absence-stated-in-other-words",
            "entries": touched, "changed_fields": fields, "partners": partners,
            "leaked_entry": any(t in LEAKED for t in touched),
            "leaked_partner": any(p in LEAKED for p in partners.values() if p),
            "leaked_found_in_docs": any(t in LEAKED_FOUND_IN_DOCS for t in touched),
            "caught": bool(on_entry),
            "caught_on_injected_field": bool(on_field),
            "new_flags_on_entry": on_entry,
            "new_flags_elsewhere": [f for f in new if f["entry"] not in touched],
            "baseline_flags_gone": [list(k) for k in gone],
        })
    return base_al, base_flags, runs


def summary(base_flags, runs):
    counted = [r for r in runs if r["counted"]]

    def cut(pred):
        sel = [r for r in counted if pred(r)]
        return {"n": len(sel), "caught": sum(r["caught"] for r in sel)}
    return {
        "by_leak": {
            "entry_on_mapper_list": cut(lambda r: r["leaked_entry"]),
            "entry_not_on_mapper_list": cut(lambda r: not r["leaked_entry"]),
            "entry_or_partner_on_mapper_list": cut(
                lambda r: r["leaked_entry"] or r["leaked_partner"]),
            "entry_or_partner_on_mapper_list_or_found_in_docs": cut(
                lambda r: r["leaked_entry"] or r["leaked_partner"] or r["leaked_found_in_docs"]),
            "no_leak_found": cut(
                lambda r: not (r["leaked_entry"] or r["leaked_partner"]
                               or r["leaked_found_in_docs"])),
        },
        "baseline_flags": len(base_flags),
        "counted": len(counted),
        "caught": sum(r["caught"] for r in counted),
        "caught_on_injected_field": sum(r["caught_on_injected_field"] for r in counted),
        "caught_ids": [r["id"] for r in counted if r["caught"]],
    }


SWEEP = [
    ("MIN_BLOCK", 3), ("MIN_BLOCK", 6),
    ("LINK_SHARE", 0.3), ("LINK_SHARE", 0.7),
    ("PAGE_SLACK", 0), ("PAGE_SLACK", 2),
    ("EVIDENCE_NESTED", 0.8), ("EVIDENCE_NESTED", 1.0),
    ("NAME_WEIGHT", 0.0),
]


def main():
    ref = load_reference()
    blind = json.load(open(BLIND_PATH, encoding="utf-8"))
    base_al, base_flags, runs = measure(ref, blind)

    sensitivity = []
    for name, value in SWEEP:
        saved = globals()[name]
        globals()[name] = value
        try:
            _, bf, rr = measure(ref, blind)
            sensitivity.append({"parameter": name, "value": value, **summary(bf, rr)})
        finally:
            globals()[name] = saved

    by_field = {}
    for f in base_flags:
        by_field[f["field"]] = by_field.get(f["field"], 0) + 1
    result = {
        "reference": {"commit": REFERENCE_COMMIT, "path": REFERENCE_PATH,
                      "entries": len(ref["entries"])},
        "blind": {"path": "blind-map.json", "entries": len(blind["entries"])},
        "parameters": {"MIN_BLOCK": MIN_BLOCK, "LINK_SHARE": LINK_SHARE,
                       "PAGE_SLACK": PAGE_SLACK, "EVIDENCE_NESTED": EVIDENCE_NESTED,
                       "NAME_WEIGHT": NAME_WEIGHT},
        "summary": summary(base_flags, runs),
        "sensitivity": sensitivity,
        "baseline": {
            "alignment": {
                "partner": base_al["partner"],
                "links": base_al["links"],
                "unaligned_ref": base_al["unaligned_ref"],
                "unaligned_blind": base_al["unaligned_blind"],
                "linked_not_partner": base_al["linked_not_partner"],
            },
            "flag_count": len(base_flags),
            "flags_by_field": by_field,
            "flags": base_flags,
        },
        "runs": runs,
    }
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as h:
        json.dump(result, h, indent=2, ensure_ascii=False)
        h.write("\n")

    print(f"baseline flags: {len(base_flags)}  {by_field}")
    print("unaligned ref:", base_al["unaligned_ref"])
    print("unaligned blind:", base_al["unaligned_blind"])
    print("linked, not partner:", base_al["linked_not_partner"])
    for r in runs:
        tag = "CAUGHT" if r["caught"] else "missed"
        print(f"{tag:7} field={'y' if r['caught_on_injected_field'] else 'n'} "
              f"leak={'E' if r['leaked_entry'] else '-'}{'P' if r['leaked_partner'] else '-'}"
              f"{'D' if r['leaked_found_in_docs'] else '-'} "
              f"{'probe ' if r['probe'] else ''}{r['id']}")
    print("summary:", result["summary"])
    for s in sensitivity:
        print("  sweep", s)


if __name__ == "__main__":
    main()
