#!/usr/bin/env python3
"""Align Map A with Map B and print every field-level difference between them.

0014's comparison, for 26 CFR § 1.121-1. The two maps are frozen inputs and neither is
written to:

  A  examples/tax-121-principal-residence/corpus-map.json   (the first mapping, trial 9)
  B  examples/tax-121-principal-residence/blind-mapping/blind-map.json  (the blind second)

Entries are aligned **by the text they quote**, not by id, because the two mappers chose ids
independently and a shared id would be a coincidence rather than a claim. Two entries are
partners when their `evidence`, normalised to lowercase words, overlaps: the score is the
length of the longer common run of words divided by the length of the shorter quote, and a
pair scores at least 0.5 to be a candidate. Each entry takes its best-scoring candidate, and
a pair is a partnership only when each is the other's best -- so a split (one entry of A
against two of B) leaves the unpartnered one showing as one-sided, which is what it is.

An entry with no `evidence` cannot be aligned this way and is reported as unalignable rather
than assumed to match nothing.

`python3 compare.py` writes results.json beside this file.
`python3 compare.py --table` prints the difference table as markdown.

Exit 0 always: this prints a comparison, it does not grade one. `resolutions.md` is where the
differences are answered, and the README says which of them were answered from the corpus.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
MAP_A = HERE.parent / "corpus-map.json"
MAP_B = HERE / "blind-map.json"
RESULTS = HERE / "results.json"

# Compared field by field, as 0014 lists them.
VERDICT_FIELDS = ("kind", "scope", "clarity")
EDGE_FIELDS = ("dependsOn", "enabledBy", "suspendedBy")


def words(text):
    return re.findall(r"[a-z0-9$]+", (text or "").lower())


def overlap(left, right):
    """Longest common run of words, as a fraction of the shorter quote."""
    if not left or not right:
        return 0.0
    # Classic longest-common-substring over word lists; the quotes are short enough.
    best = 0
    previous = [0] * (len(right) + 1)
    for i in range(1, len(left) + 1):
        current = [0] * (len(right) + 1)
        for j in range(1, len(right) + 1):
            if left[i - 1] == right[j - 1]:
                current[j] = previous[j - 1] + 1
                best = max(best, current[j])
        previous = current
    return best / min(len(left), len(right))


def align(entries_a, entries_b):
    """(pairs, only_a, only_b, unalignable) -- mutual-best partnerships by quoted text."""
    quoted_a = {e["id"]: words(e.get("evidence")) for e in entries_a}
    quoted_b = {e["id"]: words(e.get("evidence")) for e in entries_b}
    unalignable = [("A", i) for i, w in quoted_a.items() if not w]
    unalignable += [("B", i) for i, w in quoted_b.items() if not w]

    scores = {}
    for a, wa in quoted_a.items():
        if not wa:
            continue
        for b, wb in quoted_b.items():
            if not wb:
                continue
            score = overlap(wa, wb)
            if score >= 0.5:
                scores[(a, b)] = score

    best_a, best_b = {}, {}
    for (a, b), score in scores.items():
        if score > best_a.get(a, (0.0,))[0]:
            best_a[a] = (score, b)
        if score > best_b.get(b, (0.0,))[0]:
            best_b[b] = (score, a)

    pairs = []
    for a, (score, b) in sorted(best_a.items()):
        if best_b.get(b, (0.0, None))[1] == a:
            pairs.append({"a": a, "b": b, "score": round(score, 3)})
    paired_a = {p["a"] for p in pairs}
    paired_b = {p["b"] for p in pairs}
    only_a = sorted(i for i, w in quoted_a.items() if w and i not in paired_a)
    only_b = sorted(i for i, w in quoted_b.items() if w and i not in paired_b)
    return pairs, only_a, only_b, sorted(unalignable)


def flags_for(a, b):
    """Every field-level difference between two partnered entries."""
    out = []
    for field in VERDICT_FIELDS:
        if a.get(field) != b.get(field):
            out.append({"field": field, "a": a.get(field), "b": b.get(field)})
    if bool(a.get("ambiguity")) != bool(b.get("ambiguity")):
        out.append({"field": "ambiguity",
                    "a": "present" if a.get("ambiguity") else "absent",
                    "b": "present" if b.get("ambiguity") else "absent"})
    if a["locator"]["citation"] != b["locator"]["citation"]:
        out.append({"field": "citation",
                    "a": a["locator"]["citation"], "b": b["locator"]["citation"]})
    if bool(a.get("definedElsewhere")) != bool(b.get("definedElsewhere")):
        out.append({"field": "definedElsewhere",
                    "a": "present" if a.get("definedElsewhere") else "absent",
                    "b": "present" if b.get("definedElsewhere") else "absent"})
    for field in EDGE_FIELDS:
        edges_a, edges_b = len(a.get(field, [])), len(b.get(field, []))
        if edges_a != edges_b:
            out.append({"field": field, "a": edges_a, "b": edges_b})
    return out


def last_commit(path):
    """The commit that last wrote `path`, so the review can name the bytes it compared.

    0017 binds a review to a map's bytes and `check-map-review.py` requires the comparison to
    name the same commit the review's `compared.commit` does. Not knowing is recorded as not
    knowing: a checkout with no git history writes null rather than a plausible string.
    """
    try:
        out = subprocess.run(["git", "-C", str(HERE), "log", "-1", "--format=%H", "--", str(path)],
                             capture_output=True, text=True, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def compare():
    a_map = json.loads(MAP_A.read_text(encoding="utf-8"))
    b_map = json.loads(MAP_B.read_text(encoding="utf-8"))
    by_a = {e["id"]: e for e in a_map["entries"]}
    by_b = {e["id"]: e for e in b_map["entries"]}
    pairs, only_a, only_b, unalignable = align(a_map["entries"], b_map["entries"])

    flagged = []
    for pair in pairs:
        differences = flags_for(by_a[pair["a"]], by_b[pair["b"]])
        if differences:
            flagged.append({**pair, "differences": differences})

    return {
        "about": "0014's field-by-field comparison of two independent mappings of 26 CFR "
                 "§ 1.121-1. Neither map is written to. Written by compare.py.",
        "reference": {
            "path": "examples/tax-121-principal-residence/corpus-map.json",
            "commit": last_commit(MAP_A),
            "sha256": hashlib.sha256(MAP_A.read_bytes()).hexdigest(),
            "entries": len(a_map["entries"]),
        },
        "blind": {
            "path": "examples/tax-121-principal-residence/blind-mapping/blind-map.json",
            "sha256": hashlib.sha256(MAP_B.read_bytes()).hexdigest(),
            "entries": len(b_map["entries"]),
        },
        "counts": {
            "partnered": len(pairs),
            "agreeing": len(pairs) - len(flagged),
            "flagged": len(flagged),
            "onlyA": len(only_a),
            "onlyB": len(only_b),
            "unalignable": len(unalignable),
        },
        "flags": flagged,
        "onlyA": only_a,
        "onlyB": only_b,
        "unalignable": [{"map": m, "id": i} for m, i in unalignable],
    }


def table(results):
    lines = ["| A | B | field | A said | B said |", "|---|---|---|---|---|"]
    for flag in results["flags"]:
        for difference in flag["differences"]:
            lines.append(f"| `{flag['a']}` | `{flag['b']}` | {difference['field']} | "
                         f"{difference['a']} | {difference['b']} |")
    lines.append("")
    lines.append("Entries only one map has:")
    for side in ("onlyA", "onlyB"):
        for entry in results[side]:
            lines.append(f"- {side[-1]} only: `{entry}`")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", action="store_true", help="print the table, write nothing")
    arguments = parser.parse_args()
    results = compare()
    if arguments.table:
        print(table(results))
        return 0
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    counts = results["counts"]
    print(f"{counts['partnered']} partnership(s); {counts['flagged']} carry a difference, "
          f"{counts['agreeing']} agree on every compared field.")
    print(f"{counts['onlyA']} entry(ies) only A has, {counts['onlyB']} only B has, "
          f"{counts['unalignable']} unalignable (no quote).")
    print(f"wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
