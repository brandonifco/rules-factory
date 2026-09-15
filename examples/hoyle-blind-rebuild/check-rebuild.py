#!/usr/bin/env python3
"""Judge a blind rebuild of hoyle-backgammon against TARGET.json (#3, criterion 1; EQUIVALENCE.md).

    python3 examples/hoyle-blind-rebuild/check-rebuild.py REBUILD_CLONE --commit SHA ENGINE_CLONE
            [--questions DIR] [--dotnet DOTNET] [--sdk-override VERSION] [--skip-tests]

REBUILD_CLONE is a git clone of the rebuilt engine and SHA the commit handed in. ENGINE_CLONE is a clone
of brandonifco/hoyle-backgammon holding TARGET's commit. Everything is read from git objects. The
conditions, each printed ok or FAIL:

  P1  The tests. The rebuild's commit is exported, its tests/ directory is removed, and TARGET's tests/
      tree is written in its place from the engine clone, byte for byte (its git tree hash must equal
      TARGET engine.testsTree). No other file is added or changed: the allowed shims are TARGET
      equivalence.allowedShims, which is empty. Then, with CI=true: `dotnet restore --locked-mode`,
      `dotnet build -c Release -warnaserror`, and `dotnet test -c Release` with a TRX logger. Every
      case passes, the cases per project and framework equal TARGET's, and the methods that ran equal
      TARGET's. Anything less is FAIL; there is no partial pass. The number of cases that passed, of
      TARGET's 560, is printed either way (Brandon, 2026-09-15, H4).
  P2  Provenance. The rebuild's provenance.json names TARGET's factory version and commit (not dirty),
      map package, version and nupkg sha256, kernel, corpus, randomness, packs and recipes digest, and
      the same owner's rulings (id, entry, span, answer, ruledBy, ruledOn, record). `recordSha256` may
      differ: the rebuild writes its own records.
  P3  Generated and managed files. provenance.json's `generated` and `managed` lists equal TARGET's,
      path for path and sha256 for sha256, and each file at the commit hashes to what is recorded.
  P4  Not copied. No file of the rebuild at the commit is byte-identical to a hand-written file of the
      target's src/ or tests/ (generated, managed and TARGET brief.verbatim files are expected to be
      identical and are not counted). The share of the rebuild's hand-written source lines that also
      occur in the target's hand-written source, ignoring whitespace, blank lines, braces, usings and
      /// documentation, is printed for the reviewer, with the lines; it is not a pass mark on its own.
  P5  Its own gate. The rebuild's CI `validate` run for the commit is green, and `factory provenance`
      reports every field matching. Neither is run here (they need the factory checkout and CI); this
      prints the commands, and EQUIVALENCE.md makes them part of the pass condition.

The result's label (Brandon, 2026-09-15, H1-H3): every rebuild is "with a written interface", because
the brief carries api-contract.md and conventions.md. --questions names the session's questions
directory (RUNBOOK.md, "Questions"); each NNN-answer.md in it is an answer given. More than 10 answers
labels the result "assisted"; otherwise it is "blind". Without --questions the label is not printed.

--skip-tests does P2 to P4 and exits 3, NOT VERIFIED. --sdk-override rewrites global.json in the
composed copy only, and the result is at best NOT VERIFIED (exit 3).

Exit 0 when P1 to P4 pass on the pinned SDK; 1 on any FAIL; 2 on usage; 3 NOT VERIFIED.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("check_target", HERE / "check-target.py")
check_target = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_target)
git, blob, ls, sha256, Refusal, Report = (check_target.git, check_target.blob, check_target.ls, check_target.sha256,
                                          check_target.Refusal, check_target.Report)

TRIVIAL = re.compile(r"^\s*(?:$|[{}();,\[\]]+$|using\s|namespace\s|///|//\s*$|#)")
RULING_FIELDS = ("id", "entry", "span", "answer", "ruledBy", "ruledOn", "record")


def extract(clone: Path, commit: str, into: Path, *paths: str) -> None:
    archive = git(clone, "archive", "--format=tar", commit, *paths, binary=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(into, filter="data")


def provenance(report: Report, target: dict, rebuild: Path, commit: str) -> dict:
    recorded = json.loads(blob(rebuild, commit, "provenance.json"))
    factory = target["factory"]
    report.expect("P2 factory version", factory["version"], recorded["factory"]["version"])
    report.expect("P2 factory commit", factory["commit"], recorded["factory"]["commit"])
    report.expect("P2 factory not dirty", False, recorded["factory"]["dirty"])
    report.expect("P2 recipes digest", factory["recipesDigest"], recorded["recipes"]["digest"])
    report.expect("P2 map", target["map"], {k: recorded["map"][k] for k in ("packageId", "version", "nupkgSha256")})
    report.expect("P2 kernel", target["kernel"], recorded["kernel"])
    report.expect("P2 corpus", target["corpus"], {k: recorded["corpus"].get(k) for k in target["corpus"]})
    report.expect("P2 randomness", target["randomness"], recorded["randomness"])
    report.expect("P2 packs", target["packs"], recorded["packs"])
    engine_rulings = target["ownerRulings"]
    report.expect("P2 owner's rulings", engine_rulings,
                  [{k: r[k] for k in RULING_FIELDS} for r in recorded.get("rulings", [])])
    return recorded


def generated(report: Report, target: dict, rebuild: Path, commit: str, recorded: dict) -> set[str]:
    for key, pinned in (("generated", target["generatedFiles"]), ("managed", target["managedFiles"])):
        mine = sorted(recorded[key], key=lambda f: f["path"])
        report.expect(f"P3 {key} files: paths", [f["path"] for f in pinned], [f["path"] for f in mine])
        report.expect(f"P3 {key} files: sha256 equal TARGET's", pinned, mine)
        stale = [f["path"] for f in mine if sha256(blob(rebuild, commit, f["path"])) != f["sha256"]]
        report.expect(f"P3 {key} files at the commit hash to provenance.json", [], stale)
    return {f["path"] for f in target["generatedFiles"] + target["managedFiles"]} \
        | {f["path"] for f in target["brief"]["verbatim"]}


def normalised_lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if not TRIVIAL.match(line)]


def not_copied(report: Report, target: dict, rebuild: Path, commit: str, engine: Path, expected_same: set[str]) -> None:
    engine_commit = target["engine"]["commit"]
    hand_written = [p for p in ls(engine, engine_commit, "src", "tests")
                    if p not in expected_same and not p.endswith(".g.cs") and not p.endswith("packages.lock.json")]
    target_hashes = {sha256(blob(engine, engine_commit, p)): p for p in hand_written}
    target_lines = set()
    for p in hand_written:
        if p.startswith("src/") and p.endswith(".cs"):
            target_lines |= set(normalised_lines(blob(engine, engine_commit, p).decode("utf-8", "replace")))
    identical, total, shared = [], 0, []
    for p in ls(rebuild, commit):
        if p in expected_same or p.endswith(".g.cs") or p.endswith("packages.lock.json"):
            continue
        data = blob(rebuild, commit, p)
        if sha256(data) in target_hashes and len(data) > 64:
            identical.append(f"{p} == target {target_hashes[sha256(data)]}")
        if p.startswith("src/") and p.endswith(".cs"):
            lines = normalised_lines(data.decode("utf-8", "replace"))
            total += len(lines)
            shared += [f"{p}: {line}" for line in lines if line in target_lines]
    report.expect("P4 no rebuild file is byte-identical to a hand-written target file", [], identical)
    share = (100.0 * len(shared) / total) if total else 0.0
    print(f"info P4 {len(shared)} of {total} hand-written source line(s) also occur in the target's hand-written "
          f"source ({share:.1f}%); for review, not a pass mark:")
    for line in shared[:200]:
        print(f"       {line}")


def tests(report: Report, target: dict, rebuild: Path, commit: str, engine: Path, dotnet: str,
          sdk_override: str | None) -> None:
    with tempfile.TemporaryDirectory(prefix="hoyle-rebuild-") as work:
        tree = Path(work, "tree")
        results = Path(work, "results")
        tree.mkdir()
        extract(rebuild, commit, tree)
        subprocess.run(["rm", "-rf", str(tree / "tests")], check=True)
        extract(engine, target["engine"]["commit"], tree, "tests")
        shims = target["equivalence"]["allowedShims"]
        report.expect("P1 allowed shims (none are allowed)", [], shims)
        if sdk_override:
            global_json = json.loads((tree / "global.json").read_text(encoding="utf-8"))
            global_json["sdk"]["version"] = sdk_override
            (tree / "global.json").write_text(json.dumps(global_json), encoding="utf-8")
        env = dict(os.environ, CI="true", DOTNET_NOLOGO="1", DOTNET_CLI_TELEMETRY_OPTOUT="1")
        steps = [
            ["restore", "--locked-mode"],
            ["build", "-c", "Release", "--no-restore", "-warnaserror"],
            ["test", "-c", "Release", "--no-build", "--nologo", "--logger", "trx", "--results-directory", str(results)],
        ]
        solutions = sorted(p.name for p in tree.glob("*.slnx"))
        report.expect("P1 the solution is HoyleBackgammon.slnx", ["HoyleBackgammon.slnx"], solutions)
        for step in steps:
            proc = subprocess.run([dotnet, step[0], "HoyleBackgammon.slnx", *step[1:]], cwd=tree, env=env,
                                  capture_output=True, text=True)
            if proc.returncode != 0 and step[0] != "test":
                tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-20:])
                report.fail(f"P1 dotnet {step[0]} exited {proc.returncode}:\n{tail}")
                return
            report.ok(f"P1 dotnet {step[0]}")
        runs = check_target.read_trx(sorted(results.glob("*.trx"))) if results.is_dir() else {}
        passed = sum(sum(run["cases"].values()) - len(run["notPassed"]) for run in runs.values())
        print(f"info P1 {passed} of {target['tests']['caseCount']} case(s) passed")
        check_target.compare_runs(target, {}, {k: v for k, v in runs.items()}, report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("rebuild", type=Path)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--target", type=Path, default=HERE / "TARGET.json")
    parser.add_argument("--dotnet", default=os.environ.get("DOTNET", "dotnet"))
    parser.add_argument("--sdk-override")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--questions", type=Path, help="the session's questions directory, for the label")
    args = parser.parse_args(argv)
    target = json.loads(args.target.read_text(encoding="utf-8"))
    report = Report()
    try:
        commit = git(args.rebuild, "rev-parse", "--verify", f"{args.commit}^{{commit}}").strip()
        tree = git(args.engine, "rev-parse", f"{target['engine']['commit']}:tests").strip()
        report.expect("P1 the engine clone's tests tree is TARGET's", target["engine"]["testsTree"], tree)
        recorded = provenance(report, target, args.rebuild, commit)
        expected_same = generated(report, target, args.rebuild, commit, recorded)
        not_copied(report, target, args.rebuild, commit, args.engine, expected_same)
        if not args.skip_tests:
            tests(report, target, args.rebuild, commit, args.engine, args.dotnet, args.sdk_override)
    except Refusal as refusal:
        report.fail(str(refusal))
    print("todo P5 in the rebuild's checkout, with the factory at the tag (the brief's staged copy, or a checkout in "
          "CI): python3 FACTORY/tools/factory provenance --engine . ; and the rebuild's CI validate run for this commit")
    if args.questions is not None:
        answers = len(list(args.questions.glob("*-answer.md"))) if args.questions.is_dir() else 0
        limit = target["equivalence"]["assistedAfterAnswers"]
        kind = "assisted" if answers > limit else "blind"
        print(f"label: {kind}, with a written interface ({answers} answer(s) given; more than {limit} is assisted)")
    if report.failures:
        print(f"check-rebuild: FAIL ({len(report.failures)})")
        return 1
    if args.skip_tests or args.sdk_override:
        print("check-rebuild: P2-P4 pass" + ("" if args.skip_tests else ", P1 passes on an overridden SDK")
              + ": NOT VERIFIED")
        return 3
    print("check-rebuild: P1-P4 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
