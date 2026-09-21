#!/usr/bin/env python3
"""Score results.json into results.md. Nothing here decides anything by judgement.

An injection counts as caught by a check when that check was **not already failing in the
control run and is red in this one** -- green-to-red, or, for a check whose subject matter the injection
creates, skip-to-red. That rule is the whole of the scoring, and it is why the controls are
runs rather than assumptions: a check already red before any injection cannot become a
catch, and nothing about a catch rests on the injector's opinion of what the output means.

Three exclusions, each mechanical:

  * checks classed `excluded` -- the map's own hash pin, which any edit fails, and the
    whitespace step. See run-trial.py on the pin.
  * checks classed `code` -- they compare the map with an engine built from the CORRECT
    map, so they detect divergence from an answer a real trial does not have. Counted and
    reported, never in the rate. See the README.
  * injections carrying `invalid` (not errors at all) or `probe` (designed to evade a
    documented limitation). Both are printed; neither is in the denominator.

Usage: score.py  -- writes results.md beside results.json.
"""
import json
import os
import sys

# Imports another of this repository's files by path, and the loader writes that file's
# bytecode beside it. No caller's environment is relied on to stop it (#384): module level
# and above the import, because the loader reads the flag when the import happens.
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from injections import INJECTIONS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MECHANICAL = ("schema", "corpus")


def load():
    with open(os.path.join(HERE, "results.json"), encoding="utf-8") as handle:
        return json.load(handle)


def control_verdicts(results):
    """Per copy, the checks that were green with no injection at all."""
    for run in results["runs"]:
        if run["id"] == "control-unmodified":
            return {copy: {k: v for k, v in entry["checks"].items()}
                    for copy, entry in run["copies"].items()}
    raise SystemExit("no control run in results.json -- nothing can be scored")


def catches(run, controls, classes):
    """{class: [check names]} for checks green in the control and red here."""
    found = {}
    for copy, entry in run["copies"].items():
        if entry.get("not_applied"):
            continue
        for check, verdict in entry["checks"].items():
            if verdict != "fail":
                continue
            baseline = controls.get(copy, {}).get(check)
            if baseline is None or baseline == "fail":
                # Already red, or not a check this copy ran at all: proves nothing. A
                # baseline `skip` is different and does count -- a check that said it had no
                # subject matter, and then failed once the injection gave it some, caught the
                # injection. `status` is the instance: no entry in the upstream map is
                # `implemented`, so the rule that an implemented entry names its revision was
                # vacuous until an injection claimed one.
                continue
            found.setdefault(classes.get(check, "unclassified"), []).append(
                f"{copy}: {check}")
    return found


def not_reached(run, controls):
    out = {}
    for copy, entry in run["copies"].items():
        if entry.get("not_applied"):
            continue
        missing = [c for c in controls.get(copy, {}) if c not in entry["checks"]]
        if missing:
            out[copy] = missing
    return out


def main():
    results = load()
    classes = results["detector_class"]
    controls = control_verdicts(results)
    by_id = {i["id"]: i for i in INJECTIONS}

    rows, scored, counted_miss = [], [], []
    excluded_rows = []
    build_reached = build_red = 0

    for run in results["runs"]:
        injection = by_id[run["id"]]
        if injection["family"] == "control":
            continue
        found = catches(run, controls, classes)
        mechanical = [c for k in MECHANICAL for c in found.get(k, [])]
        code_only = found.get("code", [])
        missed = not mechanical
        row = {
            "id": run["id"],
            "family": run["family"],
            "predicted": run["predicted_stratum"],
            "mechanical": mechanical,
            "code": code_only,
            "build": found.get("build", []),
            "not_reached": not_reached(run, controls),
            "invalid": injection.get("invalid"),
            "probe": injection.get("probe"),
        }
        engine = run["copies"].get("engine")
        if engine and not engine.get("not_applied"):
            steps = {c: v for c, v in engine["checks"].items() if classes.get(c) == "build"}
            if steps:
                build_reached += 1
                build_red += any(v == "fail" for v in steps.values())
        if injection.get("invalid") or injection.get("probe"):
            excluded_rows.append(row)
        else:
            rows.append(row)
            scored.append(row)
            if missed:
                counted_miss.append(row)

    caught = [r for r in scored if r["mechanical"]]
    lines = []
    w = lines.append

    w("# Results\n")
    w("Generated by `score.py` from `results.json`. Do not edit by hand.\n")
    w(f"**{len(scored)} injections scored. {len(caught)} caught by a mechanical detector, "
      f"{len(counted_miss)} not: a miss rate of {len(counted_miss) / len(scored):.0%}.** "
      "Read the README before quoting that number; it is a miss rate for *these* "
      "injections against *these* detectors, and the strata below are the part that "
      "carries meaning.\n")

    w("## Every injection, and what actually went red\n")
    w("`caught by` names the check, and a check counts only where the control run did not "
      "already fail it. `map-vs-code` verdicts are reported and never counted -- see the "
      "README.\n")
    w("| injection | family | predicted | caught by | map-vs-code |")
    w("|---|---|---|---|---|")
    for r in rows + excluded_rows:
        mark = ""
        if r["invalid"]:
            mark = " *(invalid, not counted)*"
        elif r["probe"]:
            mark = " *(probe, not counted)*"
        caught_by = ", ".join(f"`{c}`" for c in r["mechanical"]) or "**nothing**"
        code = ", ".join(f"`{c}`" for c in r["code"]) or "--"
        w(f"| `{r['id']}`{mark} | {r['family']} | {r['predicted']} | {caught_by} | {code} |")
    w("")

    w("## By predicted stratum\n")
    w("The stratum was written down with the injection, before any detector ran. A "
      "prediction the run contradicted is a result, not an embarrassment.\n")
    w("| predicted stratum | n | caught mechanically | missed |")
    w("|---|---:|---:|---:|")
    strata = {}
    for r in scored:
        strata.setdefault(r["predicted"], []).append(r)
    for name in ("schema", "corpus", "human"):
        group = strata.get(name, [])
        if not group:
            continue
        hit = sum(1 for r in group if r["mechanical"])
        w(f"| {name} | {len(group)} | {hit} | {len(group) - hit} |")
    w(f"| **all** | **{len(scored)}** | **{len(caught)}** | **{len(counted_miss)}** |")
    w("")

    w("## By family\n")
    w("| family | n | caught mechanically | missed |")
    w("|---|---:|---:|---:|")
    families = {}
    for r in scored:
        families.setdefault(r["family"], []).append(r)
    for name in sorted(families):
        group = families[name]
        hit = sum(1 for r in group if r["mechanical"])
        w(f"| {name} | {len(group)} | {hit} | {len(group) - hit} |")
    w("")

    w("## Predictions the run contradicted\n")
    wrong = [r for r in scored
             if (r["predicted"] == "human") != (not r["mechanical"])]
    if wrong:
        for r in wrong:
            direction = ("predicted a miss and a detector caught it"
                         if r["mechanical"] else "predicted a catch and nothing did")
            w(f"- `{r['id']}`: {direction} ({', '.join(r['mechanical']) or 'no detector'})")
    else:
        w("None.")
    w("")

    w("## What the build and the tests did\n")
    engine_runs = sum(1 for r in results["runs"]
                      if "engine" in r["copies"]
                      and not r["copies"]["engine"].get("not_applied")
                      and by_id[r["id"]]["family"] != "control")
    w(f"Of {engine_runs} injections applied to the engine's copy of the map, "
      f"{build_reached} reached the build and the 350 tests, and **{build_red} of those "
      "went red**. The gate stops at its first failing step, so in the rest the build was "
      "*not reached* rather than silent -- `results.json` lists which steps each run never "
      "got to. Nothing in `src/` reads `corpus-map.json`; the map reaches the engine as "
      "transcribed constants in `MapEntries.cs`. A compiler and a test suite cannot see a "
      "map error, and these runs are the evidence rather than the argument.\n")

    w("## Controls\n")
    for run in results["runs"]:
        if run["family"] != "control":
            continue
        found = catches(run, controls, classes)
        w(f"- `{run['id']}`: " + (", ".join(
            f"{k}: {v}" for k, v in found.items()) if found else
            "no check went red. No false positive."))
    w("")

    with open(os.path.join(HERE, "results.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
