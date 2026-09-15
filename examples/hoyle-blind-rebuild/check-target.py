#!/usr/bin/env python3
"""Hold TARGET.json to the hoyle-backgammon commit it freezes (#3, criterion 1: a blind rebuild).

    python3 examples/hoyle-blind-rebuild/check-target.py ENGINE_CLONE [--factory RULES_FACTORY_CLONE]
            [--nupkg MAP.nupkg] [--run-tests [--dotnet DOTNET] [--sdk-override VERSION]]
    python3 examples/hoyle-blind-rebuild/check-target.py ENGINE_CLONE --emit
    python3 examples/hoyle-blind-rebuild/check-target.py --self-check

ENGINE_CLONE is any git clone of brandonifco/hoyle-backgammon that holds the pinned commit. Nothing is
read from its working tree: every fact comes from the git objects at TARGET's commit, so a dirty clone,
or one checked out elsewhere, cannot change the answer. The checker re-derives, and refuses on any
difference:

  * the commit is the full sha TARGET names, and `<commit>:tests` has TARGET's tree hash;
  * every xUnit test method under tests/ ([Fact] or [Theory] on a public void method), as
    Namespace.Class.Method, per test project, split into hand-written and factory-generated
    (tests/*/Generated/*.g.cs);
  * what provenance.json records: the factory version and commit, the map package, version and nupkg
    sha256, the kernel, the corpus, the randomness, the recipes digest, every generated and managed
    file with its sha256, and every owner's ruling;
  * the pins the tests assert as literals: the ruleset id and version, the replay schema, and the
    seeded game's canonical-JSON sha256 with its seed;
  * RulesFactory.Packages.g.props pins the same kernel and map version provenance names;
  * the overlay's implemented entries, and the entries it declares fully ruled (rulings, declines: []);
  * the sha256 of every file the brief hands over verbatim (TARGET brief.verbatim).

--factory also checks that TARGET's factory tag names TARGET's factory commit in that clone, and
recomputes the recipes digest from the git blobs at that commit (provenance.py's digest rule), so
the digest provenance.json records is the tag's and not merely a string.

--nupkg checks the map package file's sha256.

--run-tests exports the commit (git archive) to a temporary directory and runs `dotnet test -c
Release` with a TRX logger. Every case must pass, the cases per project and target framework must
equal TARGET's, and the methods the TRX files name must equal the methods read from source.
hoyle-backgammon's global.json pins SDK 10.0.112 with roll-forward disabled. --sdk-override rewrites
global.json in the exported copy only, and the run then ends NOT VERIFIED (exit 3) rather than PASS,
because it did not run on the pinned SDK. Without --run-tests the check exits 3, NOT VERIFIED: never 0.

--emit prints the derived facts as JSON, which is how TARGET's pinned sections were written.

--self-check needs no clone: TARGET is internally consistent (counts equal lists, hashes are hashes,
disclosures name pinned methods, every decision has an id). tools/tests runs it offline.

Exit 0 when every pin matches and the tests ran on the pinned SDK; 1 on any mismatch or refusal;
2 on usage; 3 NOT VERIFIED. Standard library and git only.
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

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
NAMESPACE = re.compile(r"^\s*namespace\s+([\w.]+)\s*;")
CLASS = re.compile(r"^\s*public\s+(?:sealed\s+|static\s+|abstract\s+|partial\s+)*class\s+(\w+)")
TEST_ATTR = re.compile(r"^\s*\[(Fact|Theory)\b")
METHOD = re.compile(r"^\s*public\s+(?:async\s+)?(?:void|Task)\s+(\w+)\s*\(")
TRX_NS = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
FRAMEWORK = re.compile(r"/bin/[^/]+/(net[0-9.]+)/")
# provenance.py's digest rule, restated so a digest can be recomputed from git objects.
RECIPE_FILES = ("tools/check-map.py",)
RECIPE_DIR = "tools/factory/"


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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------- derivation

def is_generated(path: str) -> bool:
    return "/Generated/" in path and path.endswith(".g.cs")


def test_methods(clone: Path, commit: str) -> dict[str, dict[str, list[str]]]:
    """{project: {"handWritten": [...], "generated": [...]}} for every [Fact]/[Theory] method."""
    projects: dict[str, dict[str, set]] = {}
    for path in ls(clone, commit, "tests"):
        if not path.endswith(".cs"):
            continue
        project = path.split("/")[1]
        text = blob(clone, commit, path).decode("utf-8")
        namespace = cls = None
        pending = False
        found = set()
        for number, line in enumerate(text.splitlines(), 1):
            if m := NAMESPACE.match(line):
                namespace = m.group(1)
            if m := CLASS.match(line):
                cls = m.group(1)
            if TEST_ATTR.match(line):
                pending = True
                continue
            if pending and (not line.strip() or line.strip().startswith(("[", "//"))):
                continue
            if pending:
                m = METHOD.match(line)
                if not m:
                    raise Refusal(f"{path}:{number}: [Fact]/[Theory] not followed by a public void method")
                if not (namespace and cls):
                    raise Refusal(f"{path}:{number}: test method outside a namespace or public class")
                name = f"{namespace}.{cls}.{m.group(1)}"
                if name in found:
                    raise Refusal(f"{path}:{number}: {name} declared twice (overloads are not pinned)")
                found.add(name)
                pending = False
        kind = "generated" if is_generated(path) else "handWritten"
        entry = projects.setdefault(project, {"handWritten": set(), "generated": set()})
        clash = found & (entry["handWritten"] | entry["generated"])
        if clash:
            raise Refusal(f"{path}: {sorted(clash)} declared in two files")
        entry[kind] |= found
    return {p: {k: sorted(v) for k, v in kinds.items()} for p, kinds in sorted(projects.items())}


def test_classes(clone: Path, commit: str, generated: bool = False) -> list[str]:
    """Every public class declared in the test tree's hand-written (or generated) files."""
    classes = set()
    for path in ls(clone, commit, "tests"):
        if path.endswith(".cs") and is_generated(path) == generated:
            for line in blob(clone, commit, path).decode("utf-8").splitlines():
                if m := CLASS.match(line):
                    classes.add(m.group(1))
    return sorted(classes)


def literal(pattern: str, text: str, what: str) -> str:
    found = re.findall(pattern, text)
    if len(found) != 1:
        raise Refusal(f"{what}: expected exactly one match of {pattern!r}, found {len(found)}")
    return found[0]


def recipes_digest(clone: Path, commit: str) -> str:
    paths = sorted([p for p in ls(clone, commit, RECIPE_DIR) if "__pycache__" not in p and not p.endswith(".pyc")]
                   + list(RECIPE_FILES), key=lambda p: p.encode("utf-8"))
    text = "".join(f"{sha256(blob(clone, commit, p))}  {p}\n" for p in paths)
    return sha256(text.encode("utf-8"))


def derive(clone: Path, target: dict) -> dict:
    engine = target["engine"]
    commit = git(clone, "rev-parse", "--verify", f"{engine['commit']}^{{commit}}").strip()
    provenance = json.loads(blob(clone, commit, "provenance.json"))
    overlay = json.loads(blob(clone, commit, "corpus-map.overlay.json"))
    props = blob(clone, commit, "RulesFactory.Packages.g.props").decode("utf-8")
    identity_tests = blob(clone, commit, "tests/HoyleBackgammon.Tests/IdentityTests.cs").decode("utf-8")
    replay_tests = blob(clone, commit, "tests/HoyleBackgammon.Tests/EntryPointTests.cs").decode("utf-8")

    methods = test_methods(clone, commit)
    derived = {
        "engine": {
            "repository": engine["repository"],
            "commit": commit,
            "testsTree": git(clone, "rev-parse", f"{commit}:tests").strip(),
            "provenanceSha256": sha256(blob(clone, commit, "provenance.json")),
        },
        "tests": {
            "projects": {
                name: {
                    "handWritten": kinds["handWritten"],
                    "generated": kinds["generated"],
                    "methodCount": len(kinds["handWritten"]) + len(kinds["generated"]),
                }
                for name, kinds in methods.items()
            },
            "methodCount": sum(len(k["handWritten"]) + len(k["generated"]) for k in methods.values()),
            "handWrittenClasses": test_classes(clone, commit),
            "generatedClasses": test_classes(clone, commit, generated=True),
        },
        "factory": {
            "version": provenance["factory"]["version"],
            "commit": provenance["factory"]["commit"],
            "dirty": provenance["factory"]["dirty"],
            "recipesDigest": provenance["recipes"]["digest"],
        },
        "map": {
            "packageId": provenance["map"]["packageId"],
            "version": provenance["map"]["version"],
            "nupkgSha256": provenance["map"]["nupkgSha256"],
        },
        "kernel": provenance["kernel"],
        "corpus": {k: provenance["corpus"][k] for k in ("sourceId", "contentHash", "hashDerivation", "asOf")},
        "randomness": provenance["randomness"],
        "packs": provenance["packs"],
        "identity": {
            "ruleset": {
                "id": literal(r'Assert\.Equal\("([^"]+)", Game\.Identity\.Ruleset\.Id\)', identity_tests, "ruleset id"),
                "version": int(literal(r"Assert\.Equal\((\d+), Game\.Identity\.Ruleset\.Version\)", identity_tests,
                                       "ruleset version")),
            },
            "replaySchema": int(literal(r"Assert\.Equal\((\d+), Game\.Identity\.ReplaySchema\.Version\)",
                                        identity_tests, "replay schema")),
            "randomAlgorithm": literal(r'Assert\.Equal\("([^"]+)", Game\.Identity\.RandomAlgorithm', identity_tests,
                                       "random algorithm"),
        },
        "replay": {
            "seed": int(literal(r"private const ulong Seed = (\d+)UL;", replay_tests, "replay seed")),
            "canonicalJsonSha256": literal(r'RecordedReplaySha256 = "([0-9a-f]{64})"', replay_tests, "replay sha256"),
            "pinnedIn": "tests/HoyleBackgammon.Tests/EntryPointTests.cs",
        },
        "packagePins": {
            "kernel": literal(r'<PackageVersion Include="RulesKernel" Version="([^"]+)"', props, "kernel pin"),
            "randomness": literal(r'<PackageVersion Include="RulesKernel.Randomness" Version="([^"]+)"', props,
                                  "randomness pin"),
            "map": literal(r'<PackageVersion Include="' + re.escape(provenance["map"]["packageId"])
                           + r'" Version="\[([^\]]+)\]"', props, "map pin"),
        },
        "generatedFiles": sorted(provenance["generated"], key=lambda f: f["path"]),
        "managedFiles": sorted(provenance["managed"], key=lambda f: f["path"]),
        "ownerRulings": [
            {k: r[k] for k in ("id", "entry", "span", "answer", "ruledBy", "ruledOn", "record")} for r in provenance["rulings"]
        ],
        "overlay": {
            "implemented": sorted(k for k, v in overlay.items() if v.get("status") == "implemented"),
            "fullyRuled": sorted(k for k, v in overlay.items()
                                 if v.get("rulings") and v.get("declines") == []),
        },
        "verbatim": [
            {"path": item["path"], "sha256": sha256(blob(clone, commit, item["path"]))}
            for item in target.get("brief", {}).get("verbatim", [])
        ],
    }
    return derived


def run_tests(clone: Path, commit: str, dotnet: str, sdk_override: str | None) -> dict[str, dict]:
    """Export the commit, run its tests, and read back cases per project and framework, and methods."""
    with tempfile.TemporaryDirectory(prefix="hoyle-target-") as work:
        tree = Path(work, "tree")
        results = Path(work, "results")
        tree.mkdir()
        archive = git(clone, "archive", "--format=tar", commit, binary=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tree, filter="data")
        if sdk_override:
            global_json = json.loads((tree / "global.json").read_text(encoding="utf-8"))
            global_json["sdk"]["version"] = sdk_override
            (tree / "global.json").write_text(json.dumps(global_json), encoding="utf-8")
        solutions = sorted(p.name for p in tree.glob("*.slnx"))
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
        return read_trx(trx_files)


def read_trx(trx_files: list[Path]) -> dict[str, dict]:
    projects: dict[str, dict] = {}
    for trx in trx_files:
        root = ET.parse(trx).getroot()
        definitions = {}
        for unit in root.iterfind(".//t:TestDefinitions/t:UnitTest", TRX_NS):
            method = unit.find("t:TestMethod", TRX_NS)
            code_base = method.get("codeBase").replace("\\", "/")
            framework = FRAMEWORK.search(code_base)
            project = Path(code_base).stem
            definitions[unit.get("id")] = (project, framework.group(1) if framework else "?",
                                           f"{method.get('className')}.{method.get('name')}")
        for result in root.iterfind(".//t:Results/t:UnitTestResult", TRX_NS):
            project, framework, method = definitions[result.get("testId")]
            entry = projects.setdefault(project, {"cases": {}, "methods": set(), "notPassed": []})
            entry["cases"][framework] = entry["cases"].get(framework, 0) + 1
            entry["methods"].add(method)
            if result.get("outcome") != "Passed":
                entry["notPassed"].append(f"{result.get('testName')}: {result.get('outcome')}")
    return projects


# ---------------------------------------------------------------------------- comparison

class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, what: str) -> None:
        print(f"ok   {what}")

    def fail(self, what: str) -> None:
        print(f"FAIL {what}")
        self.failures.append(what)

    def expect(self, what: str, expected, actual) -> None:
        if expected == actual:
            self.ok(what)
            return
        if isinstance(expected, list) and isinstance(actual, list) and all(isinstance(x, str) for x in expected + actual):
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            self.fail(f"{what} (in TARGET only: {missing}; in the engine only: {extra})")
        else:
            self.fail(f"{what} (TARGET {json.dumps(expected)[:300]}, engine {json.dumps(actual)[:300]})")


PINNED = ("engine", "factory", "map", "kernel", "corpus", "randomness", "packs", "identity", "replay",
          "packagePins", "generatedFiles", "managedFiles", "ownerRulings", "overlay")


# Fields of a pinned section that record why, not what, and so have nothing to re-derive.
ANNOTATIONS = {"branch", "frozenOn", "note", "tag"}


def compare(target: dict, derived: dict, report: Report) -> None:
    for key in PINNED:
        if isinstance(derived.get(key), dict):
            unknown = sorted(set(target.get(key, {})) - set(derived[key]) - ANNOTATIONS)
            report.expect(f"{key}: no pinned field the checker does not derive", [], unknown)
            for sub in sorted(derived[key]):
                report.expect(f"{key}.{sub}", target.get(key, {}).get(sub), derived[key].get(sub))
        else:
            report.expect(key, target.get(key), derived.get(key))
    tests = target["tests"]
    for name in sorted(set(tests["projects"]) | set(derived["tests"]["projects"])):
        pinned = tests["projects"].get(name, {})
        actual = derived["tests"]["projects"].get(name, {})
        for kind in ("handWritten", "generated"):
            report.expect(f"tests.{name}.{kind}", pinned.get(kind), actual.get(kind))
        report.expect(f"tests.{name}.methodCount", pinned.get("methodCount"), actual.get("methodCount"))
    report.expect("tests.methodCount", tests["methodCount"], derived["tests"]["methodCount"])
    report.expect("tests.handWrittenClasses", tests["handWrittenClasses"], derived["tests"]["handWrittenClasses"])
    report.expect("tests.generatedClasses", tests["generatedClasses"], derived["tests"]["generatedClasses"])
    report.expect("provenance and the package pins agree on the kernel", target["kernel"]["version"],
                  derived["packagePins"]["kernel"])
    report.expect("provenance and the package pins agree on the map version", target["map"]["version"],
                  derived["packagePins"]["map"])
    report.expect("brief.verbatim sha256", target["brief"]["verbatim"], derived["verbatim"])


def compare_runs(target: dict, derived: dict, runs: dict[str, dict], report: Report) -> None:
    tests = target["tests"]
    for name, pinned in sorted(tests["projects"].items()):
        run = runs.get(name)
        if run is None:
            report.fail(f"run: {name} produced no TRX results")
            continue
        report.expect(f"run: {name} cases per framework", pinned["casesPerFramework"], run["cases"])
        report.expect(f"run: {name} every case passed", [], run["notPassed"])
        report.expect(f"run: {name} methods that ran are the methods in source",
                      sorted(pinned["handWritten"] + pinned["generated"]), sorted(run["methods"]))
    report.expect("run: no test project TARGET does not name", sorted(tests["projects"]), sorted(runs))


def self_check(target: dict, report: Report) -> None:
    engine = target.get("engine", {})
    report.expect("engine.commit is a full sha", True, bool(HEX40.match(engine.get("commit", ""))))
    report.expect("engine.testsTree is a full sha", True, bool(HEX40.match(engine.get("testsTree", ""))))
    report.expect("engine.provenanceSha256 is a sha256", True, bool(HEX64.match(engine.get("provenanceSha256", ""))))
    report.expect("factory.commit is a full sha", True, bool(HEX40.match(target.get("factory", {}).get("commit", ""))))
    report.expect("factory.tag names factory.version", f"factory/v{target['factory']['version']}",
                  target["factory"].get("tag"))
    report.expect("map.nupkgSha256 is a sha256", True, bool(HEX64.match(target["map"].get("nupkgSha256", ""))))
    report.expect("replay.canonicalJsonSha256 is a sha256", True,
                  bool(HEX64.match(target["replay"].get("canonicalJsonSha256", ""))))

    tests = target["tests"]
    everything = []
    cases = 0
    for name, project in tests["projects"].items():
        methods = project["handWritten"] + project["generated"]
        everything += methods
        report.expect(f"{name}: methodCount equals its lists", project["methodCount"], len(methods))
        for kind in ("handWritten", "generated"):
            report.expect(f"{name}: {kind} is sorted", sorted(project[kind]), project[kind])
        frameworks = project.get("casesPerFramework", {})
        report.expect(f"{name}: cases for every target framework", sorted(tests["targetFrameworks"]), sorted(frameworks))
        report.expect(f"{name}: at least one case per method", True,
                      all(count >= len(methods) for count in frameworks.values()))
        cases += sum(frameworks.values())
    report.expect("every method is Namespace.Class.Method", [], [m for m in everything if not IDENT.match(m)])
    report.expect("method names are unique", len(everything), len(set(everything)))
    report.expect("tests.methodCount is the sum over projects", tests["methodCount"], len(everything))
    report.expect("tests.caseCount is the sum over projects and frameworks", tests["caseCount"], cases)

    brief = target["brief"]
    report.expect("brief.manifestSha256 is a sha256", True, bool(HEX64.match(brief.get("manifestSha256", ""))))
    report.expect("brief.apiContract.rawSha256 is a sha256", True,
                  bool(HEX64.match(brief.get("apiContract", {}).get("rawSha256", ""))))
    for item in brief["verbatim"]:
        if not HEX64.match(item.get("sha256", "")):
            report.fail(f"brief.verbatim {item.get('path')}: sha256 is not a sha256")
    names = {m.rsplit(".", 1)[1] for m in everything}
    for disclosure in brief["disclosures"]:
        if disclosure["name"] not in names | set(tests["handWrittenClasses"]):
            report.fail(f"disclosure {disclosure['name']} names no pinned test method or class")
        if not (isinstance(disclosure.get("count"), int) and disclosure["count"] > 0):
            report.fail(f"disclosure {disclosure['name']}: count must be a positive integer")
    ids = [d.get("id") for d in target.get("openDecisions", [])]
    report.expect("open decision ids are unique", len(ids), len(set(ids)))
    report.expect("every open decision has an id, question and recommendation", [],
                  [d.get("id") for d in target.get("openDecisions", [])
                   if not (d.get("id") and d.get("question") and d.get("recommendation"))])


# ---------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("engine", nargs="?", type=Path, help="a git clone of brandonifco/hoyle-backgammon")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--factory", type=Path, help="a git clone of brandonifco/rules-factory holding the tag")
    parser.add_argument("--nupkg", type=Path, help="the map package file")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--dotnet", default=os.environ.get("DOTNET", "dotnet"))
    parser.add_argument("--sdk-override", help="rewrite global.json in the exported copy (ends NOT VERIFIED)")
    parser.add_argument("--emit", action="store_true", help="print the derived facts as JSON")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)

    try:
        target = json.loads(args.target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"cannot read {args.target}: {error}", file=sys.stderr)
        return 2

    report = Report()
    if args.self_check:
        self_check(target, report)
        print(f"check-target --self-check: {'FAIL' if report.failures else 'PASS'}")
        return 1 if report.failures else 0
    if args.engine is None:
        parser.print_usage(sys.stderr)
        return 2

    try:
        derived = derive(args.engine, target)
        if args.emit:
            print(json.dumps(derived, indent=2))
            return 0
        compare(target, derived, report)
        if args.factory:
            tag_commit = git(args.factory, "rev-parse", "--verify", f"{target['factory']['tag']}^{{commit}}").strip()
            report.expect("factory tag names the factory commit", target["factory"]["commit"], tag_commit)
            report.expect("recipes digest recomputed from the tag's git objects", target["factory"]["recipesDigest"],
                          recipes_digest(args.factory, tag_commit))
        if args.nupkg:
            report.expect("map package sha256", target["map"]["nupkgSha256"], sha256(args.nupkg.read_bytes()))
        if args.run_tests:
            compare_runs(target, derived, run_tests(args.engine, derived["engine"]["commit"], args.dotnet,
                                                    args.sdk_override), report)
    except Refusal as refusal:
        report.fail(str(refusal))

    if report.failures:
        print(f"check-target: FAIL ({len(report.failures)} mismatch(es))")
        return 1
    if not args.run_tests:
        print("check-target: pins match; tests not run: NOT VERIFIED")
        return 3
    if args.sdk_override:
        print(f"check-target: pins match and every case passed, on SDK {args.sdk_override} rather than the pinned "
              "SDK: NOT VERIFIED")
        return 3
    print(f"check-target: PASS against {target['engine']['commit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
