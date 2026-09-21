#!/usr/bin/env python3
"""Run the injection trial: inject, run every detector, record what each one actually said.

One run per injection. Each run gets a clean export of both repositories at a pinned
commit -- `git archive`, not a copy of the working tree, so that another agent editing
either repository while this runs cannot change what was measured -- applies the injection
to the map, and runs the detectors that exist for that copy:

    factory   tools/check-map.py           structure, vocabulary, references, exclusions
              tools/check-locators.py      citations, absences and coverage, against the corpus
    engine    scripts/validate.sh full     the real gate: corpus hash, map-to-code
                                           correspondence, the correspondence table,
                                           citations against the corpus, build, 350 tests

Nothing here decides whether an injection was caught. A detector's verdict is read out of
its own output, per named check, and scored later by comparing it with the same check's
verdict in the control run. A check that was already red proves nothing and is excluded by
construction rather than by judgement.

One deliberate intervention, and it matters: the engine's gate pins the map's hash in
corpus-manifest.json, so ANY edit to the map fails that step. Left alone, every injection
would be "detected" by a check that has not read a word of the map. The pin is therefore
recomputed after each injection -- exactly what the gate's own failure message tells a
mapper to do when the map was meant to change -- and that step is excluded from scoring.

Usage: run-trial.py [--out DIR] [--only ID[,ID...]] [--skip-engine]
"""
import argparse
import copy as copymod
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

# Imports another of this repository's files by path, and the loader writes that file's
# bytecode beside it. No caller's environment is relied on to stop it (#384): module level
# and above the import, because the loader reads the flag when the import happens.
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from injections import INJECTIONS, FACTORY, ENGINE  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# The two subjects, pinned. Both are recorded in results.json and in the README: a trial
# against "whatever was checked out" is not reproducible, and one repository was being
# edited by other hands while this ran.
SUBJECTS = {
    FACTORY: {
        "repo": "/home/brandon/rules-factory",
        "commit": "ecc53b8c231c0eef67ee081c29043ddbf8004336",
        "map": "examples/hoyle-backgammon/corpus-map.json",
    },
    ENGINE: {
        "repo": "/home/brandon/hoyle-backgammon",
        "commit": "67563b35bed185a0ffa4706622858c5cb40df791",
        "map": "corpus-map.json",
        "manifest": "corpus-manifest.json",
    },
}

# What each named check reads, and therefore what a verdict from it is worth. See the
# README: `code` verdicts are excluded from the headline because the engine was built from
# the corrected map, so they compare the map against the right answer.
DETECTOR_CLASS = {
    # tools/check-map.py -- reads the map and the repository, never the corpus
    "schema": "schema", "required-fields": "schema", "vocabulary": "schema",
    "unique-ids": "schema", "references": "schema", "no-cycles": "schema",
    "manifest": "schema", "exclusions": "schema", "status": "schema",
    "decision-records": "schema", "conflicts": "schema", "absent": "schema",
    "cross-references": "schema", "correspondence": "schema",
    # tools/check-locators.py -- reads the corpus
    "locators": "corpus", "absence": "corpus", "coverage": "corpus",
    # the engine gate's steps, by their labels
    "corpus/hoyle.txt matches the pinned baseline hash": "excluded",
    "corpus-map.json matches its pinned hash": "excluded",
    "MapEntries matches corpus-map.json entry for entry": "code",
    "every unresolved reason and every map entry agree with the correspondence table": "code",
    "nothing inside the engine calls BeyondAdapter": "code",
    "every corpus-map.json citation resolves to its page in corpus/hoyle.txt": "corpus",
    "engine citation step, run in isolation": "corpus",
    "dotnet restore": "build", "dotnet format --verify-no-changes": "build",
    "build Debug (0 warnings)": "build", "test Debug": "build",
    "build Release w/ CI=true (0 warnings)": "build", "test Release w/ CI=true": "build",
    "git diff --check": "excluded",
}


def run(cmd, cwd):
    started = time.time()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return {
        "cmd": cmd if isinstance(cmd, str) else " ".join(cmd),
        "exit": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "seconds": round(time.time() - started, 1),
    }


def export(subject, into):
    """A clean tree at the pinned commit, independent of anybody's working copy."""
    os.makedirs(into, exist_ok=True)
    archive = subprocess.run(
        ["git", "archive", subject["commit"]], cwd=subject["repo"],
        capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", into], input=archive.stdout, check=True)
    # The engine's gate ends with `git diff --check` over uncommitted changes. An exported
    # tree is not a repository, so that step would error for a reason that has nothing to do
    # with the map. An empty repository with everything untracked diffs nothing and the step
    # is green, as it is after a clean checkout.
    subprocess.run(["git", "init", "-q"], cwd=into, check=True)


def apply_injection(injection, copy_name, tree):
    """Patch the map in `tree`. Returns None on success, or the reason it did not apply."""
    path = os.path.join(tree, SUBJECTS[copy_name]["map"])
    with open(path, encoding="utf-8") as handle:
        mapped = json.load(handle)
    before = copymod.deepcopy(mapped)
    try:
        injection["patch"](mapped, copy_name)
    except Exception as exc:  # the patch's own guard; recorded, never swallowed
        return f"{type(exc).__name__}: {exc}"
    if injection["family"] != "control" and mapped == before:
        return "the patch changed nothing, which would score as an undetected error"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(mapped, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return None


def repin_map(tree):
    """Update the engine manifest's pin to the mutated map -- see the module docstring."""
    manifest_path = os.path.join(tree, SUBJECTS[ENGINE]["manifest"])
    map_path = os.path.join(tree, SUBJECTS[ENGINE]["map"])
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    digest = hashlib.sha256(open(map_path, "rb").read()).hexdigest()
    pins = [m for m in manifest.get("maps", []) if m.get("path") == "corpus-map.json"]
    assert len(pins) == 1, "the engine manifest no longer pins its map exactly once"
    pins[0]["contentHash"] = digest
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def isolated_citation_step(tree):
    """The engine gate's citation step, alone.

    `set -e` makes the gate stop at its first failing step, and the step that compares the
    map with the code comes first. So on every injection that step catches, the gate never
    reaches the only check it has that reads the corpus -- and "not reached" must not be
    recorded as "did not catch". The step's own source is sliced out of scripts/validate.sh
    between its heredoc markers and run unmodified: the real detector, invoked directly.
    """
    gate = open(os.path.join(tree, "scripts/validate.sh"), encoding="utf-8").read()
    body = gate.split("<<'PYCITE'\n", 1)[1].split("\nPYCITE", 1)[0]
    script = os.path.join(tree, ".isolated-citation-step.py")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(body)
    result = run(["python3", script], cwd=tree)
    os.remove(script)
    return result


CHECK_LINE = re.compile(r"^\[(ok|fail|skip)\] ([a-z-]+):")
GATE_LINE = re.compile(r"^(ok|FAIL|skip)\s+(.+?)(?: \(depends on a step that failed\))?$")


def read_checker(result):
    """Per-check verdicts out of check-map.py / check-locators.py output."""
    verdicts = {}
    for line in result["stdout"].splitlines():
        found = CHECK_LINE.match(line.strip())
        if found:
            verdicts[found.group(2)] = found.group(1)
    return verdicts


def read_gate(result):
    """Per-step verdicts out of the engine's validate.sh output."""
    verdicts = {}
    for line in result["stdout"].splitlines():
        # Strip the ANSI the gate emits when it thinks it is on a terminal.
        line = re.sub(r"\033\[[0-9;]*m", "", line).rstrip()
        found = GATE_LINE.match(line)
        if found and not line.startswith(("Passed", "Failed")):
            status = {"ok": "ok", "FAIL": "fail", "skip": "skip"}[found.group(1)]
            label = found.group(2).strip()
            if label in DETECTOR_CLASS:
                verdicts[label] = status
    return verdicts


def failure_lines(result, limit=4):
    lines = [l for l in result["stderr"].splitlines() if l.strip()]
    lines += [l for l in result["stdout"].splitlines() if l.strip().startswith(("X ", "  X"))]
    return lines[:limit]


def one_run(injection, out_dir, skip_engine):
    record = {
        "id": injection["id"],
        "family": injection["family"],
        "predicted_stratum": injection["stratum"],
        "modelled_on": injection.get("modelled"),
        "why_wrong": injection["wrong"],
        "applies": list(injection["applies"]),
        "copies": {},
    }
    work = os.path.join(out_dir, injection["id"])
    shutil.rmtree(work, ignore_errors=True)

    if FACTORY in injection["applies"]:
        tree = os.path.join(work, "factory")
        export(SUBJECTS[FACTORY], tree)
        failed = apply_injection(injection, FACTORY, tree)
        entry = {"not_applied": failed, "checks": {}, "evidence": {}}
        if not failed:
            for tool, args in (
                ("check-map", ["tools/check-map.py", SUBJECTS[FACTORY]["map"]]),
                ("check-locators", ["tools/check-locators.py", SUBJECTS[FACTORY]["map"],
                                    "examples/hoyle-backgammon/hoyle.txt"]),
            ):
                result = run(["python3"] + args, cwd=tree)
                entry["checks"].update(read_checker(result))
                entry[tool + "_exit"] = result["exit"]
                if result["exit"] != 0:
                    entry["evidence"][tool] = failure_lines(result)
        record["copies"][FACTORY] = entry

    if ENGINE in injection["applies"] and not skip_engine:
        tree = os.path.join(work, "engine")
        export(SUBJECTS[ENGINE], tree)
        failed = apply_injection(injection, ENGINE, tree)
        entry = {"not_applied": failed, "checks": {}, "evidence": {}}
        if not failed:
            repin_map(tree)
            result = run(["./scripts/validate.sh", "full"], cwd=tree)
            entry["checks"].update(read_gate(result))
            entry["gate_exit"] = result["exit"]
            entry["seconds"] = result["seconds"]
            if result["exit"] != 0:
                entry["evidence"]["validate.sh"] = failure_lines(result, limit=6)
            isolated = isolated_citation_step(tree)
            label = "engine citation step, run in isolation"
            entry["checks"][label] = "ok" if isolated["exit"] == 0 else "fail"
            if isolated["exit"] != 0:
                entry["evidence"][label] = failure_lines(isolated)
        record["copies"][ENGINE] = entry

    shutil.rmtree(work, ignore_errors=True)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.environ.get(
        "INJECTION_TRIAL_OUT", "/tmp/injection-trial"))
    parser.add_argument("--only", help="comma-separated injection ids")
    parser.add_argument("--skip-engine", action="store_true",
                        help="factory checkers only; no dotnet")
    args = parser.parse_args()

    wanted = set(args.only.split(",")) if args.only else None
    chosen = [i for i in INJECTIONS if wanted is None or i["id"] in wanted]
    os.makedirs(args.out, exist_ok=True)

    records = []
    for injection in chosen:
        print(f"==> {injection['id']}", flush=True)
        record = one_run(injection, args.out, args.skip_engine)
        records.append(record)
        for copy_name, entry in record["copies"].items():
            if entry["not_applied"]:
                print(f"    {copy_name}: NOT APPLIED -- {entry['not_applied']}")
            else:
                red = sorted(k for k, v in entry["checks"].items() if v == "fail")
                print(f"    {copy_name}: {len(entry['checks'])} checks, red: {red or 'none'}")

    results = {
        "subjects": {k: {kk: vv for kk, vv in v.items()} for k, v in SUBJECTS.items()},
        "detector_class": DETECTOR_CLASS,
        "runs": records,
    }
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=1, ensure_ascii=False)
        handle.write("\n")
    print(f"\n{len(records)} run(s) written to results.json")


if __name__ == "__main__":
    main()
