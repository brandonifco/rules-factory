#!/usr/bin/env python3
"""Hold TARGET.json to the deckard commit it freezes (#3, criterion 1, step S0 / E0).

    python3 examples/sr6-deckard/check-target.py DECKARD_CLONE [--target TARGET.json]
                                                 [--skip-tests] [--require-approved]
    python3 examples/sr6-deckard/check-target.py --self-check [--target TARGET.json]

DECKARD_CLONE is any git clone of brandonifco/deckard that holds the pinned commit. Nothing is
read from its working tree: every fact comes from the git objects at TARGET's commit, so a dirty
or checked-out-elsewhere clone cannot change the answer. The checker re-derives, and refuses on
any difference:

  * the commit resolves to the full sha TARGET names, and `<commit>:tests` has TARGET's tree hash;
  * every xUnit test method under tests/ ([Fact] or [Theory] on a public void/Task method in a
    *Tests.cs file), as Namespace.Class.Method, and the count per project;
  * every method's class sits in exactly one TARGET category;
  * the sha256 of each decision record docs/decisions/0001-*.md .. 0007-*.md, and that there are
    exactly seven;
  * the sha256 of every line range a code-comment decision or a gate names, and that every test a
    decision names as pinning it exists;
  * the gate inventory: every `step "..."` in scripts/validate.sh, every CHECKS key in
    tools/repo-checks.py, every .github/workflows/*.yml and every .claude/hooks/* file has a row;
  * the test cases: the commit is exported (git archive) to a temporary directory and
    `dotnet test` runs it in Release with a TRX logger. Every case must pass, the count per
    project must equal TARGET's, and the methods the TRX files name must equal the methods read
    from source. $DOTNET names the dotnet to run (default `dotnet`); deckard's global.json pins
    its SDK with roll-forward disabled, so the machine needs that SDK.

--skip-tests does everything but the last item and exits 3, NOT VERIFIED: never 0.

Gate classification is Brandon's to approve (plan E5). A `divergent` row without an approval is
printed as PENDING and does not fail the pin check; --require-approved makes it fail, which is how
the equivalence step runs this.

--self-check needs no clone. It checks TARGET is internally consistent (counts equal lists,
categories partition the methods, classes are from the vocabulary, approvals name a recorded
owner decision, hashes are hashes) and contains nothing shaped like quoted corpus text. It is
what tools/tests runs offline.

Exit 0 when every pin matches; 1 on any mismatch or refusal; 2 on usage; 3 NOT VERIFIED.
Standard library and git only.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TARGET = HERE / "TARGET.json"

GATE_CLASSES = {"equivalent", "stronger", "carried-as-test", "repository-process", "divergent", "composite"}
CATEGORIES = ("architecture", "test-double", "prng-and-dice", "replay-identity", "sr6-rules")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
LINES = re.compile(r"^([1-9][0-9]*)(?:-([1-9][0-9]*))?$")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
ADR = re.compile(r"^docs/decisions/(000[1-7])-[a-z0-9-]+\.md$")
STEP = re.compile(r'^\s*step "([^"]+)"')
CHECK_KEY = re.compile(r'^\s*"([a-z][a-z0-9-]*)":\s*check_\w+,\s*$')
NAMESPACE = re.compile(r"^\s*namespace\s+([\w.]+)\s*;")
CLASS = re.compile(r"^\s*public\s+(?:sealed\s+|static\s+|abstract\s+|partial\s+)*class\s+(\w+)")
TEST_ATTR = re.compile(r"^\s*\[(Fact|Theory)\b")
METHOD = re.compile(r"^\s*public\s+(?:async\s+)?(?:void|Task)\s+(\w+)\s*\(")
TRX_NS = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}

# Free-text fields are the checker's own words about deckard, capped so none can carry a passage.
FREE_TEXT_FIELDS = {"summary", "note", "$comment", "decision"}
FREE_TEXT_MAX = 400
QUOTE_SHAPED = re.compile(r"[\"“”]")


class Refusal(Exception):
    pass


# ---------------------------------------------------------------------------- git objects

def git(clone: Path, *args: str, binary: bool = False):
    proc = subprocess.run(["git", "-C", str(clone), *args], capture_output=True)
    if proc.returncode != 0:
        raise Refusal(f"git {' '.join(args)}: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout if binary else proc.stdout.decode("utf-8")


def blob(clone: Path, commit: str, path: str) -> bytes:
    return git(clone, "show", f"{commit}:{path}", binary=True)


def ls(clone: Path, commit: str, *paths: str) -> list[str]:
    out = git(clone, "ls-tree", "-r", "--name-only", commit, "--", *paths)
    return [line for line in out.splitlines() if line]


def lines_sha256(data: bytes, spec: str, path: str) -> str:
    m = LINES.match(spec)
    if not m:
        raise Refusal(f"{path}: line range {spec!r} is not N or N-M")
    start = int(m.group(1))
    end = int(m.group(2) or start)
    lines = data.decode("utf-8").split("\n")
    if end < start or end > len(lines):
        raise Refusal(f"{path}:{spec} is outside the file ({len(lines)} lines)")
    return hashlib.sha256("\n".join(lines[start - 1:end]).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------- derivation

def derive_methods(clone: Path, commit: str) -> dict[str, list[str]]:
    """Namespace.Class.Method for every [Fact]/[Theory] method, grouped by test project."""
    projects: dict[str, list[str]] = {}
    for path in ls(clone, commit, "tests"):
        if not path.endswith("Tests.cs"):
            continue
        project = path.split("/")[1]
        text = blob(clone, commit, path).decode("utf-8")
        namespace = cls = None
        pending = False
        grep_style = set()
        found = set()
        for number, line in enumerate(text.splitlines(), 1):
            if m := NAMESPACE.match(line):
                namespace = m.group(1)
            elif m := CLASS.match(line):
                cls = m.group(1)
            if TEST_ATTR.match(line):
                pending = True
                continue
            m = METHOD.match(line)
            if m:
                grep_style.add(m.group(1))
                if pending:
                    if not (namespace and cls):
                        raise Refusal(f"{path}:{number}: test method outside a namespace or public class")
                    name = f"{namespace}.{cls}.{m.group(1)}"
                    if name in found:
                        raise Refusal(f"{path}:{number}: {name} declared twice (overloads are not pinned)")
                    found.add(name)
                pending = False
            elif pending and line.strip() and not line.strip().startswith("["):
                raise Refusal(f"{path}:{number}: [Fact]/[Theory] not followed by a public void/Task method")
        # The plan's own derivation was a grep for public void/Task methods; the two must agree, or
        # a helper method or an unattributed test is being counted or missed.
        if {n.rsplit(".", 1)[1] for n in found} != grep_style:
            raise Refusal(f"{path}: attributed test methods {sorted(found)} differ from public void/Task methods "
                          f"{sorted(grep_style)}")
        projects.setdefault(project, []).extend(found)
    return {p: sorted(ms) for p, ms in sorted(projects.items())}


def derive_gate_inventory(clone: Path, commit: str) -> dict[str, tuple[str, int]]:
    """Gate id -> (path, line) for every gate a family of deckard files declares."""
    inventory: dict[str, tuple[str, int]] = {}

    def scan(path: str, pattern: re.Pattern, prefix: str) -> None:
        for number, line in enumerate(blob(clone, commit, path).decode("utf-8").splitlines(), 1):
            if m := pattern.match(line):
                gid = f"{prefix}/{m.group(1)}"
                if gid in inventory:
                    raise Refusal(f"{path}:{number}: {gid} declared twice")
                inventory[gid] = (path, number)

    scan("scripts/validate.sh", STEP, "validate.sh")
    scan("tools/repo-checks.py", CHECK_KEY, "repo-checks")
    for path in ls(clone, commit, ".github/workflows"):
        if path.endswith((".yml", ".yaml")):
            inventory[f"workflow/{path.rsplit('/', 1)[1]}"] = (path, 1)
    for path in ls(clone, commit, ".claude/hooks"):
        inventory[f"hook/{path.rsplit('/', 1)[1]}"] = (path, 1)
    return inventory


def run_tests(clone: Path, commit: str, dotnet: str) -> dict[str, dict]:
    """Export the commit, run its tests, and read back per-project cases and methods from TRX."""
    with tempfile.TemporaryDirectory(prefix="deckard-target-") as work:
        tree = Path(work, "tree")
        results = Path(work, "results")
        tree.mkdir()
        archive = git(clone, "archive", "--format=tar", commit, binary=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tree, filter="data")
        solutions = sorted(p.name for p in tree.glob("*.slnx")) + sorted(p.name for p in tree.glob("*.sln"))
        if len(solutions) != 1:
            raise Refusal(f"expected one solution at the root of {commit}, found {solutions}")
        env = dict(os.environ, DOTNET_NOLOGO="1", DOTNET_CLI_TELEMETRY_OPTOUT="1")
        proc = subprocess.run(
            [dotnet, "test", solutions[0], "-c", "Release", "--nologo",
             "--logger", "trx", "--results-directory", str(results)],
            cwd=tree, env=env, capture_output=True, text=True)
        trx_files = sorted(results.glob("*.trx")) if results.is_dir() else []
        if proc.returncode != 0 or not trx_files:
            tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-15:])
            raise Refusal(f"dotnet test exited {proc.returncode} with {len(trx_files)} TRX file(s):\n{tail}")
        projects: dict[str, dict] = {}
        for trx in trx_files:
            root = ET.parse(trx).getroot()
            definitions = {}
            for unit in root.iterfind(".//t:TestDefinitions/t:UnitTest", TRX_NS):
                method = unit.find("t:TestMethod", TRX_NS)
                project = Path(method.get("codeBase").replace("\\", "/")).stem
                definitions[unit.get("id")] = (project, f"{method.get('className')}.{method.get('name')}")
            for result in root.iterfind(".//t:Results/t:UnitTestResult", TRX_NS):
                project, method = definitions[result.get("testId")]
                entry = projects.setdefault(project, {"cases": 0, "methods": set(), "notPassed": []})
                entry["cases"] += 1
                entry["methods"].add(method)
                if result.get("outcome") != "Passed":
                    entry["notPassed"].append(f"{result.get('testName')}: {result.get('outcome')}")
        return projects


# ---------------------------------------------------------------------------- comparison

class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.pending: list[str] = []

    def ok(self, what: str) -> None:
        print(f"ok   {what}")

    def fail(self, what: str) -> None:
        print(f"FAIL {what}")
        self.failures.append(what)

    def expect(self, what: str, expected, actual) -> None:
        if expected == actual:
            self.ok(what)
        else:
            detail = ""
            if isinstance(expected, (list, set)) and isinstance(actual, (list, set)):
                missing = sorted(set(expected) - set(actual))
                extra = sorted(set(actual) - set(expected))
                detail = f" (in TARGET only: {missing}; in deckard only: {extra})"
            else:
                detail = f" (TARGET {expected!r}, deckard {actual!r})"
            self.fail(f"{what}{detail}")


def self_check(target: dict, report: Report) -> None:
    deckard = target.get("deckard", {})
    report.expect("deckard.commit is a full sha", True, bool(HEX40.match(deckard.get("commit", ""))))
    report.expect("deckard.testsTree is a full sha", True, bool(HEX40.match(deckard.get("testsTree", ""))))

    tests = target.get("tests", {})
    projects = tests.get("projects", {})
    methods = [m for p in projects.values() for m in p.get("methods", [])]
    report.expect("every method name is Namespace.Class.Method", [],
                  [m for m in methods if not IDENT.match(m)])
    report.expect("method names are unique", len(methods), len(set(methods)))
    for name, project in projects.items():
        report.expect(f"{name}: methodCount equals its list", project.get("methodCount"), len(project.get("methods", [])))
        report.expect(f"{name}: methods are sorted", sorted(project.get("methods", [])), project.get("methods", []))
    report.expect("tests.methodCount is the sum over projects", tests.get("methodCount"), len(methods))
    report.expect("tests.caseCount is the sum over projects", tests.get("caseCount"),
                  sum(p.get("caseCount", -1) for p in projects.values()))

    categories = tests.get("categories", {})
    report.expect("categories are the fixed five", sorted(CATEGORIES), sorted(categories))
    owner = {}
    for category, spec in categories.items():
        for cls in spec.get("classes", []):
            if cls in owner:
                report.fail(f"class {cls} is in both {owner[cls]} and {category}")
            owner[cls] = category
    counts = {c: 0 for c in categories}
    unplaced = []
    for method in methods:
        cls = method.rsplit(".", 1)[0]
        if cls in owner:
            counts[owner[cls]] += 1
        else:
            unplaced.append(method)
    report.expect("every method's class is in a category", [], unplaced)
    report.expect("category methodCounts", {c: s.get("methodCount") for c, s in categories.items()}, counts)
    superseded = [c for c, s in categories.items() if s.get("runVerbatim") is not True]
    report.expect("every category runs verbatim; none superseded (D5)", [], superseded)

    records = target.get("decisionRecords", [])
    report.expect("seven decision records, 0001..0007", [f"{n:04d}" for n in range(1, 8)],
                  [ADR.match(r.get("path", "")).group(1) if ADR.match(r.get("path", "")) else r.get("path")
                   for r in records])
    report.expect("decision record hashes are sha256", [], [r.get("path") for r in records
                                                           if not HEX64.match(r.get("sha256", ""))])

    method_set = set(methods)
    decisions = target.get("codeCommentDecisions", [])
    report.expect("code-comment decision ids are unique", len(decisions), len({d.get("id") for d in decisions}))
    for d in decisions:
        report.expect(f"{d.get('id')}: has locators", True, bool(d.get("locators")))
        report.expect(f"{d.get('id')}: locator hashes are sha256", [],
                      [loc for loc in d.get("locators", []) if not (HEX64.match(loc.get("sha256", ""))
                                                                    and LINES.match(loc.get("lines", "")))])
        report.expect(f"{d.get('id')}: every pinning test is a pinned method", [],
                      sorted(set(d.get("pinnedBy", [])) - method_set) if d.get("pinnedBy") else ["(none named)"])

    owner_decisions = target.get("ownerDecisions", {})
    gates = target.get("gates", [])
    report.expect("gate ids are unique", len(gates), len({g.get("id") for g in gates}))
    for g in gates:
        gid = g.get("id")
        cls = g.get("class")
        if cls not in GATE_CLASSES:
            report.fail(f"gate {gid}: class {cls!r} is not one of {sorted(GATE_CLASSES)}")
        loc = g.get("locator", {})
        if not (loc.get("path") and LINES.match(str(loc.get("lines", ""))) and HEX64.match(loc.get("sha256", ""))):
            report.fail(f"gate {gid}: locator needs path, lines and sha256")
        approval = g.get("approvedBy")
        if approval is not None and (cls != "divergent" or approval not in owner_decisions):
            report.fail(f"gate {gid}: approvedBy {approval!r} must name a recorded owner decision on a divergent row")
        if cls == "divergent" and approval is None:
            report.pending.append(gid)

    offenders = []

    def walk(node, key=None):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str) and key in FREE_TEXT_FIELDS:
            if len(node) > FREE_TEXT_MAX or QUOTE_SHAPED.search(node):
                offenders.append(f"{key}: {node[:60]}")

    walk(target)
    report.expect("free text is short and quotes nothing", [], offenders)


def check_against(target: dict, clone: Path, report: Report, skip_tests: bool, dotnet: str) -> None:
    deckard = target["deckard"]
    commit = deckard["commit"]
    resolved = git(clone, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").strip()
    report.expect("the clone holds the pinned commit", commit, resolved)
    report.expect("git tree hash of <commit>:tests", deckard["testsTree"],
                  git(clone, "rev-parse", f"{commit}:tests").strip())

    derived = derive_methods(clone, commit)
    projects = target["tests"]["projects"]
    report.expect("test projects", sorted(projects), sorted(derived))
    for name in sorted(set(projects) | set(derived)):
        report.expect(f"{name}: test methods", projects.get(name, {}).get("methods", []), derived.get(name, []))

    paths = ls(clone, commit, "docs/decisions")
    adrs = sorted(p for p in paths if ADR.match(p))
    report.expect("decision records 0001..0007 at the commit",
                  [r["path"] for r in target["decisionRecords"]], adrs)
    for record in target["decisionRecords"]:
        if record["path"] in adrs:
            report.expect(f"sha256 {record['path']}", record["sha256"],
                          hashlib.sha256(blob(clone, commit, record["path"])).hexdigest())

    def locator(what: str, loc: dict) -> None:
        try:
            actual = lines_sha256(blob(clone, commit, loc["path"]), str(loc["lines"]), loc["path"])
        except Refusal as refusal:
            report.fail(f"{what}: {refusal}")
            return
        report.expect(f"{what}: sha256 of {loc['path']}:{loc['lines']}", loc["sha256"], actual)

    for d in target["codeCommentDecisions"]:
        for loc in d["locators"]:
            locator(f"decision {d['id']}", loc)

    inventory = derive_gate_inventory(clone, commit)
    rows = {g["id"]: g for g in target["gates"]}
    report.expect("every gate deckard declares has a row", [], sorted(set(inventory) - set(rows)))
    for gid, (path, line) in sorted(inventory.items()):
        if gid in rows:
            loc = rows[gid]["locator"]
            report.expect(f"gate {gid}: locator", f"{path}:{line}", f"{loc['path']}:{loc['lines']}")
    for g in target["gates"]:
        locator(f"gate {g['id']}", g["locator"])

    if skip_tests:
        return
    try:
        ran = run_tests(clone, commit, dotnet)
    except Refusal as refusal:
        report.fail(f"test cases could not be re-derived: {refusal}")
        return
    report.expect("projects dotnet test ran", sorted(projects), sorted(ran))
    for name in sorted(projects):
        got = ran.get(name, {"cases": 0, "methods": set(), "notPassed": []})
        report.expect(f"{name}: every case passed", [], got["notPassed"])
        report.expect(f"{name}: cases", projects[name]["caseCount"], got["cases"])
        report.expect(f"{name}: methods that ran equal methods in source", projects[name]["methods"],
                      sorted(got["methods"]))
    report.expect("total cases", target["tests"]["caseCount"], sum(r["cases"] for r in ran.values()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("deckard", nargs="?", type=Path, help="a git clone holding the pinned commit")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--self-check", action="store_true", help="check TARGET alone; no clone")
    parser.add_argument("--skip-tests", action="store_true", help="do not run dotnet test; exits 3")
    parser.add_argument("--require-approved", action="store_true", help="fail on an unapproved divergent gate")
    args = parser.parse_args(argv)
    if args.self_check == (args.deckard is not None):
        parser.error("give a deckard clone, or --self-check, not both")
    if args.self_check and args.skip_tests:
        parser.error("--skip-tests needs a deckard clone")

    try:
        target = json.loads(args.target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"FAIL cannot read {args.target}: {error}")
        return 1

    report = Report()
    self_check(target, report)
    if not args.self_check:
        if report.failures:
            print("\nTARGET is not internally consistent; refusing to compare it with deckard")
            return 1
        try:
            check_against(target, args.deckard, report, args.skip_tests, os.environ.get("DOTNET", "dotnet"))
        except (Refusal, KeyError) as refusal:
            report.fail(f"refused: {refusal}")

    for gid in report.pending:
        print(f"PENDING divergent gate {gid} has no owner approval")
    if args.require_approved and report.pending:
        report.fail(f"{len(report.pending)} divergent gate(s) not approved: {', '.join(report.pending)}")

    print()
    if report.failures:
        print(f"check-target: FAIL ({len(report.failures)} mismatch(es))")
        return 1
    if args.skip_tests:
        print("check-target: every other pin matches, and NOT VERIFIED: test cases (--skip-tests)")
        return 3
    print("check-target: PASS" + (" (TARGET alone)" if args.self_check else f" against {target['deckard']['commit']}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
