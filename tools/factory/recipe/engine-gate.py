#!/usr/bin/env python3
"""The checks scripts/validate.sh runs that are not a dotnet command.

Emitted by rules-factory tools/factory (the gate recipe, #3). Rewritten by every `factory
produce`; do not edit it here. Each subcommand prints what it examined and exits 0 when it
proved its claim, 1 when it did not; `posture` also exits 3 for NOT VERIFIED. A check that
finds nothing to examine fails: a check with no inputs has proven nothing.

  lock-files                         every project on disk has a packages.lock.json
  no-randomness                      nothing restores RulesKernel.Randomness
  posture --manifest M --map MAP --name N
                                     the committed corpus hashes to the baseline, under its posture
  regenerate --package-map P --package-id ID --package-version V --name N [--write]
                                     every *.g.cs is exactly what the factory generates
  expected-results                   test projects on disk x target frameworks
  tests-ran DIR EXPECTED             the TRX files show that many result files and >0 tests
  named-tests DIR --map MAP          every test an implemented entry names exists and ran

Run from the engine root. Standard library only.
"""
import argparse
import difflib
import glob
import hashlib
import json
import os
import pathlib
import re
import sys
import types

ROOT = pathlib.Path.cwd()
IGNORED = {"bin", "obj", ".git", "artifacts", "TestResults"}
OVERLAY = "corpus-map.overlay.json"
FORBIDDEN_PACKAGES = ("RulesKernel.Randomness",)
TRX_NS = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


def on_disk(pattern):
    return sorted(p for p in ROOT.rglob(pattern) if not any(part in IGNORED for part in p.relative_to(ROOT).parts))


def report(problems, success):
    for p in problems:
        print(f"error: {p}", file=sys.stderr)
    if problems:
        return 1
    print(f"     {success}")
    return 0


def target_frameworks():
    props = (ROOT / "Directory.Build.props").read_text(encoding="utf-8")
    match = re.search(r"<TargetFrameworks?>([^<]+)</TargetFrameworks?>", props)
    return [f for f in match.group(1).split(";") if f] if match else []


# --- restore ---------------------------------------------------------------------------


def lock_files(_args):
    projects = on_disk("*.csproj")
    missing = [str(p.relative_to(ROOT)) for p in projects if not (p.parent / "packages.lock.json").is_file()]
    problems = [] if projects else ["no project found on disk, so no lock file was required of anything"]
    problems += [f"{m} has no packages.lock.json beside it; run `./scripts/validate.sh lock` and commit "
                 "the lock files" for m in missing]
    return report(problems, f"{len(projects)} project(s), each with its packages.lock.json")


def no_randomness(_args):
    """A rule-bound engine for a corpus with no dice draws no random value: the kernel's randomness
    package must not be reachable, directly or transitively. Lock files list every package restore
    resolves, so they are the evidence; project files are read too, so a reference is found even
    before a lock file records it."""
    locks = on_disk("packages.lock.json")
    problems = [] if locks else ["no packages.lock.json found, so nothing shows what restore resolves"]
    lowered = {name.lower() for name in FORBIDDEN_PACKAGES}
    for lock in locks:
        try:
            document = json.loads(lock.read_text(encoding="utf-8"))
        except ValueError as error:
            problems.append(f"{lock.relative_to(ROOT)} is not JSON: {error}")
            continue
        for framework, packages in (document.get("dependencies") or {}).items():
            for name in packages or {}:
                if name.lower() in lowered:
                    problems.append(f"{lock.relative_to(ROOT)} ({framework}) resolves {name}")
    for project in on_disk("*.csproj") + on_disk("Directory.*.props") + on_disk("Directory.*.targets"):
        text = project.read_text(encoding="utf-8", errors="replace")
        for name in FORBIDDEN_PACKAGES:
            if re.search(r'Include\s*=\s*"' + re.escape(name) + r'"', text, re.IGNORECASE):
                problems.append(f"{project.relative_to(ROOT)} references {name}")
    return report(problems, f"{len(locks)} lock file(s) and the project files resolve no "
                            f"{', '.join(FORBIDDEN_PACKAGES)}")


# --- the corpus --------------------------------------------------------------------------

# The hashDerivations this gate can recompute, as rules-factory tools/factory/intake.py knows
# them. A declared derivation it does not know is a failure: a digest nobody re-derived is unchecked.
DERIVATIONS = {
    "ecfr-versioner-xml": lambda data: hashlib.sha256(data).hexdigest(),
    "gutenberg-plain-text-including-boilerplate": lambda data: hashlib.sha256(data).hexdigest(),
}


def posture(args):
    """rules-factory decision 0013: how a baseline is verified is a property of the corpus.

    committed-copy: the bytes are under corpus/; hashed here and in CI.
    local-copy: the bytes are not in the repository; hashed from $envVar when it is set, and
    otherwise NOT VERIFIED (exit 3) -- neither ok nor FAIL, and never silent.
    """
    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    mapped = json.loads(pathlib.Path(args.map).read_text(encoding="utf-8"))
    entries_cs = ROOT / "src" / args.name / "Generated" / "MapEntries.g.cs"
    cited = re.search(r'contentHash: "([0-9a-f]{64})"', entries_cs.read_text(encoding="utf-8")) if entries_cs.is_file() else None

    problems, verified, unverified = [], [], []
    corpora = [c for c in manifest.get("corpora") or [] if isinstance(c, dict)]
    if not corpora:
        problems.append("the package manifest declares no corpora, so nothing was verified")
    for corpus in corpora:
        sid = corpus.get("sourceId", "?")
        kind = corpus.get("verification")
        boundary = corpus.get("boundaryPolicy")
        expected = corpus.get("contentHash")
        derive = DERIVATIONS.get(corpus.get("hashDerivation"))
        if sid == mapped.get("corpus"):
            if (mapped.get("baseline") or {}).get("contentHash") != expected:
                problems.append(f"{sid}: the map's baseline is {(mapped.get('baseline') or {}).get('contentHash')}, "
                                f"the manifest's is {expected}")
            if cited is None or cited.group(1) != expected:
                problems.append(f"{sid}: MapEntries.Baseline cites {cited.group(1) if cited else 'no contentHash'}, "
                                f"the manifest says {expected}")
        if kind not in ("committed-copy", "local-copy"):
            problems.append(f"{sid}: verification is {kind!r}; it must be committed-copy or local-copy")
            continue
        if boundary == "never-commit" and kind == "committed-copy":
            problems.append(f"{sid}: a never-commit corpus cannot be committed-copy")
            continue
        if derive is None:
            problems.append(f"{sid}: this gate cannot recompute hashDerivation {corpus.get('hashDerivation')!r}, "
                            "so the baseline is unchecked")
            continue
        if kind == "committed-copy":
            name = os.path.basename(str(corpus.get("committedPath") or ""))
            path = ROOT / "corpus" / name if name else None
            if path is None or not path.is_file():
                problems.append(f"{sid}: committed-copy, and corpus/{name} is not a file")
                continue
            where = f"committed at corpus/{name}"
        else:
            var = corpus.get("envVar")
            if not var:
                problems.append(f"{sid}: local-copy names no envVar")
                continue
            if not os.environ.get(var):
                unverified.append(f"{sid} (local-copy, {boundary}): ${var} is not set, so the corpus bytes "
                                  "are not here to hash. Set it to a legal copy to verify.")
                continue
            path = pathlib.Path(os.environ[var])
            if not path.is_file():
                problems.append(f"{sid}: ${var} is {str(path)!r}, which is not a file")
                continue
            where = f"local copy at ${var}"
        digest = derive(path.read_bytes())
        if digest != expected:
            problems.append(f"{sid}: the {where} hashes to {digest}, the manifest pins {expected}")
        else:
            verified.append(f"{sid} ({kind}, {boundary}): {where} hashes to the pinned baseline")

    for p in problems:
        print(f"error: {p}", file=sys.stderr)
    for v in verified:
        print(f"     verified: {v}")
    for u in unverified:
        print(f"     NOT VERIFIED: {u}")
    return 1 if problems else 3 if unverified else 0


# --- the generated files ----------------------------------------------------------------


def regenerate(args):
    """Every *.g.cs is what the factory's generator makes of merge(package, overlay), byte for byte.

    The generator (generate.py, and provenance.py for the files that embed provenance.json) is the
    copy under scripts/factory/, written by the same `factory produce` that wrote the files; that
    its bytes are the factory's is provenance's to show (every recipe file is in provenance.json's
    `generated`), not this step's."""
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    import generate  # noqa: E402  (the factory's generator, vendored by produce)
    import provenance  # noqa: E402  (its generated C# that embeds provenance.json)

    package = json.loads(pathlib.Path(args.package_map).read_text(encoding="utf-8"))
    overlay_path = ROOT / OVERLAY
    overlay = json.loads(overlay_path.read_text(encoding="utf-8")) if overlay_path.is_file() else {}
    try:
        model = generate.Model(types.SimpleNamespace(package_id=args.package_id, version=args.package_version),
                               generate.merge(package, overlay), args.name)
        expected = {**generate.generated(model), **provenance.embedding(model)}
    except generate.GenerationError as error:
        return report([f"the generator refuses merge(package, overlay): {error}"], "")

    if args.write:
        for relative, text in expected.items():
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
        print(f"     wrote {len(expected)} generated file(s)")
        return 0

    problems = []
    for relative, text in sorted(expected.items()):
        target = ROOT / relative
        if not target.is_file():
            problems.append(f"{relative} is missing")
            continue
        actual = target.read_bytes()
        if actual != text.encode("utf-8"):
            diff = list(difflib.unified_diff(actual.decode("utf-8", "replace").splitlines(), text.splitlines(),
                                             f"{relative} (on disk)", f"{relative} (regenerated)", n=0, lineterm=""))
            shown = "\n".join(diff[:12]) + ("\n..." if len(diff) > 12 else "")
            problems.append(f"{relative} differs from a fresh regeneration -- a hand edit, or an overlay "
                            f"changed without re-running `factory produce`:\n{shown}")
    stray = sorted({str(p.relative_to(ROOT)).replace(os.sep, "/") for p in on_disk("*.g.cs")} - set(expected))
    problems += [f"{s} is a *.g.cs file the factory does not generate; hand-written code goes in any other file"
                 for s in stray]
    return report(problems, f"{len(expected)} generated file(s) match a fresh regeneration from "
                            f"{args.package_id}@{args.package_version} + {OVERLAY}")


# --- tests ------------------------------------------------------------------------------


def expected_results(_args):
    """`dotnet test` exits 0 when it finds nothing, so the expectation comes from the projects on
    disk, not the solution: a project dropped from the solution would drop out of both counts."""
    count = sum(1 for p in on_disk("*.csproj")
                if re.search(r"<IsTestProject>\s*true\s*</IsTestProject>", p.read_text(encoding="utf-8"), re.I))
    print(count * max(1, len(target_frameworks())))
    return 0


def _trx(results_dir):
    return sorted(glob.glob(os.path.join(results_dir, "**", "*.trx"), recursive=True))


def tests_ran(args):
    import xml.etree.ElementTree as ET
    files, total = _trx(args.results_dir), 0
    for f in files:
        counters = ET.parse(f).getroot().find(".//t:ResultSummary/t:Counters", TRX_NS)
        if counters is not None:
            total += int(counters.get("total", "0"))
    problems = []
    if len(files) != args.expected:
        problems.append(f"expected {args.expected} result file(s) (test projects on disk x target frameworks), "
                        f"found {len(files)}. A test project silently stopped running.")
    if total == 0:
        problems.append("zero tests were discovered or executed across all test projects")
    return report(problems, f"{total} test(s) across {len(files)} result file(s) actually ran")


def named_tests(args):
    """rules-factory#2: an `implemented` entry names the tests that prove it. The map cannot show a
    named test exists or ran, so every one must have an executed result (Passed or Failed; a
    failure is the suite's to report) in every target framework. Names are `Class.Method`; a short
    class name that resolves to two classes is refused rather than guessed."""
    import xml.etree.ElementTree as ET
    frameworks = max(1, len(target_frameworks()))
    ran, classes = {}, {}
    for f in _trx(args.results_dir):
        root = ET.parse(f).getroot()
        names = {}
        for unit in root.iterfind(".//t:UnitTest", TRX_NS):
            method = unit.find("t:TestMethod", TRX_NS)
            full = method.get("className")
            short = full.rsplit(".", 1)[-1]
            classes.setdefault(short, set()).add(full)
            names[unit.get("id")] = f"{short}.{method.get('name')}"
        for name in {names[r.get("testId")] for r in root.iterfind(".//t:UnitTestResult", TRX_NS)
                     if r.get("outcome") in ("Passed", "Failed") and r.get("testId") in names}:
            ran[name] = ran.get(name, 0) + 1

    mapped = json.loads(pathlib.Path(args.map).read_text(encoding="utf-8"))
    problems, named, implemented = [], 0, 0
    for entry in mapped.get("entries") or []:
        tests = entry.get("tests") or []
        if entry.get("status") == "implemented":
            implemented += 1
            if not tests:
                problems.append(f"{entry.get('id')}: implemented, and names no test")
        for item in tests:
            named += 1
            test = item.get("test", "") if isinstance(item, dict) else ""
            short = test.rsplit(".", 1)[0] if "." in test else ""
            if len(classes.get(short, ())) > 1:
                problems.append(f"{entry.get('id')}: {test!r} is ambiguous; class {short} is {sorted(classes[short])}")
            elif ran.get(test, 0) == 0:
                problems.append(f"{entry.get('id')}: names {test!r}, which no result file shows running -- "
                                "renamed, deleted, skipped, or never a test")
            elif ran[test] != frameworks:
                problems.append(f"{entry.get('id')}: {test!r} ran in {ran[test]} result file(s), expected one per "
                                f"target framework ({frameworks})")
    if not problems and implemented == 0:
        print("     no entry is implemented, so no named test was required (nothing here to prove yet)")
        return 0
    return report(problems, f"{named} test(s) named by {implemented} implemented entries, every one found and "
                            f"executed in all {frameworks} target framework(s)")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("lock-files").set_defaults(run=lock_files)
    sub.add_parser("no-randomness").set_defaults(run=no_randomness)
    p = sub.add_parser("posture")
    p.add_argument("--manifest", required=True)
    p.add_argument("--map", required=True)
    p.add_argument("--name", required=True)
    p.set_defaults(run=posture)
    r = sub.add_parser("regenerate")
    for flag in ("--package-map", "--package-id", "--package-version", "--name"):
        r.add_argument(flag, required=True)
    r.add_argument("--write", action="store_true")
    r.set_defaults(run=regenerate)
    sub.add_parser("expected-results").set_defaults(run=expected_results)
    t = sub.add_parser("tests-ran")
    t.add_argument("results_dir")
    t.add_argument("expected", type=int)
    t.set_defaults(run=tests_ran)
    n = sub.add_parser("named-tests")
    n.add_argument("results_dir")
    n.add_argument("--map", required=True)
    n.set_defaults(run=named_tests)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
