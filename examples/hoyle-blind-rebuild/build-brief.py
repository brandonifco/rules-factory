#!/usr/bin/env python3
"""Assemble the blind brief for the hoyle-backgammon rebuild from pinned inputs, and prove what it holds.

    build-brief.py api      ENGINE_CLONE --out API.md [--dotnet DOTNET] [--sdk-override VERSION]
    build-brief.py assemble ENGINE_CLONE --factory RULES_FACTORY_CLONE --nupkg MAP.nupkg
                            --api-contract API.md --out DIR
    build-brief.py scan     ENGINE_CLONE --factory RULES_FACTORY_CLONE --nupkg MAP.nupkg DIR

Every input is read from git objects at a commit TARGET.json pins, or from a file whose sha256 it pins.

`api` exports the engine commit, builds it in Release, and runs api-surface/ over the compiled
assemblies: public signatures, constant values and public XML documentation, never a method body. The
result is TARGET brief.apiContract.rawSha256 when built on the pinned SDK.

`assemble` writes the brief (README.md in this directory, "What the brief holds"):

  inputs/map/<package>.nupkg          the published map package, byte for byte
  inputs/corpus/hoyle.txt             the public-domain corpus, byte for byte
  inputs/factory/GET-FACTORY.sh       how to check out the factory at its tag, tools only
  inputs/factory-docs/                rules-factory README.md and docs/ at the tag, redacted
  engine/api-contract.md              the API contract, redacted
  engine/conventions.md               conventions the tests observe that nothing above states
  engine/overlay-skeleton.json        each entry's status and implementedIn, the owner's rulings and declines
  engine/build-files/                 the engine-owned build files the tests' project needs, verbatim
  engine/decisions/                   the engine's decision records 0001-0010, redacted
  README.md                           the brief's front page
  MANIFEST.json                       every file's sha256, every redaction, every disclosure

`scan` re-runs the leak checks over a brief directory, and over the map package and the factory files
at the tag, which the implementer also sees, and checks every file against MANIFEST.json and
MANIFEST.json against TARGET brief.manifestSha256. Both `assemble` and `scan` exit 1 on any finding that is
not a disclosure TARGET pins with its exact count.

What counts as a finding, in any file of the brief:

  * test-name   a hand-written test method of the engine (TARGET tests.projects.*.handWritten), or a
                hand-written test class, as a whole word. The factory's generated tests are not
                findings: the factory writes them and a rebuild produces them.
  * test-literal an integer of six or more digits, or a hex string of sixteen or more characters, that
                a hand-written test file contains and no allowed source does (a seed, a pinned hash).
  * copied-text eight consecutive words, case and punctuation ignored, from a line of a hand-written
                test file or of hand-written engine source that is not documentation or a declaration
                (a statement, an assertion, a comment), or from the overlay's `tests` and `mutation` fields, that no
                allowed source also contains. Allowed sources: the corpus, the map package, the
                engine's generated files and provenance.json, the factory's docs and tools at the tag,
                the engine's decision records, and the engine's /// documentation lines. In the API
                contract's documentation, code spans (`...`) are dropped first, because the contract
                renders a cref differently from the source. Decision records do not allow a literal.

Redaction is mechanical and logged. In the API contract the unit is a documentation line; a signature
line is held only to test-name and test-literal, and a finding there is a refusal, not a redaction. In a markdown document the unit is a block (a
paragraph, a top-level list item with what it nests, a fenced block). A redacted unit is replaced by a marker, and MANIFEST.json
records its file, position, reasons and the sha256 of what was removed. A relative markdown link whose
target is not in the brief is unlinked (its text kept). JSON files and the hand-written brief sources
are never redacted: a finding there is a refusal.

A disclosure file (TARGET brief.disclosureFiles, today engine/conventions.md) is written from the tests on
purpose, so copied-text is not a finding in it; test-name and test-literal still are. A disclosure
(TARGET brief.disclosures) is a test name that an input the brief cannot change already carries, such as
the published map package: it is allowed in exactly that file, exactly that many times.

Standard library, git and (for `api`) dotnet only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TARGET = HERE / "TARGET.json"
SOURCES = HERE / "brief-source"

_spec = importlib.util.spec_from_file_location("check_target", HERE / "check-target.py")
check_target = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_target)
git, blob, ls, sha256, Refusal = (check_target.git, check_target.blob, check_target.ls, check_target.sha256,
                                  check_target.Refusal)

SHINGLE = 8
WORD = re.compile(r"[a-z0-9]+")
LONG_INT = re.compile(r"(?<![0-9A-Za-z_])([0-9]{6,})(?:[uUlL]{1,2})?(?![0-9A-Za-z_])")
LONG_HEX = re.compile(r"(?<![0-9A-Za-z_])[0-9a-f]{16,}(?![0-9A-Za-z_])")
DECLARATION = re.compile(r"^\s*(?:public|internal|private|protected|using|namespace|\[|///|\{|\}|$)")
REDACTED_LINE = "/// [redacted by build-brief.py: {reasons}]"
REDACTED_BLOCK = "> [redacted by build-brief.py: {reasons}]"
# The API contract renders a cref as a qualified id in backticks; the source has it as an XML tag. Both
# are dropped before comparing documentation prose, so the prose is compared and the rendering is not.
XML_CODE = re.compile(r"<c>.*?</c>|<(?:see|seealso|paramref|typeparamref)\b[^>]*/>|<[^>]+>")
TOP_LEVEL_ITEM = re.compile(r"^ ?(?:[-*+]|[0-9]+\.) ")
CODE_SPAN = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"\[([^\]]*)\]\(([^)#\s]+)(#[^)\s]*)?\)")


# ---------------------------------------------------------------------------- text model

def words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def shingles(text: str) -> set[tuple[str, ...]]:
    w = words(text)
    return {tuple(w[i:i + SHINGLE]) for i in range(len(w) - SHINGLE + 1)}


def line_runs(lines: list[str], keep) -> list[str]:
    """Consecutive kept lines joined, so a shingle may span lines but never skips over a dropped one."""
    runs, current = [], []
    for line in lines:
        if keep(line):
            current.append(line)
        elif current:
            runs.append("\n".join(current))
            current = []
    if current:
        runs.append("\n".join(current))
    return runs


class Knowledge:
    """What may not appear in the brief, and what is allowed to."""

    def __init__(self, target: dict, engine: Path, factory: Path, nupkg: Path):
        self.target = target
        commit = target["engine"]["commit"]
        factory_commit = target["factory"]["commit"]
        tests = target["tests"]
        self.method_names = sorted({m.rsplit(".", 1)[1] for p in tests["projects"].values() for m in p["handWritten"]})
        self.class_names = list(tests["handWrittenClasses"])
        self.name_pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted(self.method_names + self.class_names,
                                                                                key=len, reverse=True))) + r")\b")

        allowed_texts = []
        with zipfile.ZipFile(nupkg) as package:
            for name in package.namelist():
                if name.endswith((".json", ".py", ".props", ".txt", ".nuspec")):
                    allowed_texts.append(package.read(name).decode("utf-8", "replace"))
        allowed_texts.append(blob(factory, factory_commit, "examples/hoyle-backgammon/hoyle.txt").decode("utf-8", "replace"))
        for path in ls(factory, factory_commit, "README.md", "docs", "tools/factory", "tools/check-map.py"):
            allowed_texts.append(blob(factory, factory_commit, path).decode("utf-8", "replace"))
        engine_files = ls(engine, commit)
        for path in engine_files:
            if path.endswith(".g.cs") or path.endswith(".g.props") or path == "provenance.json":
                allowed_texts.append(blob(engine, commit, path).decode("utf-8", "replace"))
        # A literal in a decision record is not thereby allowed: records quote seeds and hashes the tests pin.
        literal_sources = len(allowed_texts)
        for path in engine_files:
            if path.startswith("docs/decisions/"):
                allowed_texts.append(blob(engine, commit, path).decode("utf-8", "replace"))
        overlay = json.loads(blob(engine, commit, "corpus-map.overlay.json"))
        for item in overlay.values():
            for ruling in item.get("rulings", []):
                allowed_texts += [ruling["span"], ruling["answer"]]

        forbidden_texts = []
        for path in engine_files:
            if not path.endswith(".cs") or path.endswith(".g.cs"):
                continue
            lines = blob(engine, commit, path).decode("utf-8", "replace").splitlines()
            if path.startswith("src/"):
                docs = line_runs(lines, lambda line: line.lstrip().startswith("///"))
                allowed_texts += docs + [XML_CODE.sub(" ", run) for run in docs]
            if path.startswith(("src/", "tests/")):
                # Declarations are the API contract's business (a test's own names are test-name findings).
                forbidden_texts += line_runs(lines, lambda line: not DECLARATION.match(line))
        for item in overlay.values():
            for test in item.get("tests", []):
                forbidden_texts += [test.get("test", ""), test.get("mutation", "")]

        allowed = set()
        allowed_joined = "\n".join(allowed_texts[:literal_sources])
        for text in allowed_texts:
            allowed |= shingles(text)
        self.forbidden_shingles = set()
        for text in forbidden_texts:
            self.forbidden_shingles |= shingles(text)
        self.forbidden_shingles -= allowed

        literals = set()
        for path in engine_files:
            if path.startswith("tests/") and path.endswith(".cs") and not path.endswith(".g.cs"):
                text = blob(engine, commit, path).decode("utf-8", "replace")
                literals |= set(LONG_INT.findall(text)) | set(LONG_HEX.findall(text))
        self.literals = sorted(lit for lit in literals if lit not in allowed_joined)

    def findings(self, text: str, prose_only: bool = False) -> list[tuple[str, str]]:
        found = [("test-name", m.group(1)) for m in self.name_pattern.finditer(text)]
        found += [("test-literal", lit) for lit in self.literals if re.search(r"(?<![0-9A-Za-z_])" + lit + r"(?![0-9A-Za-z_])", text)]
        copied = shingles(CODE_SPAN.sub(" ", text) if prose_only else text) & self.forbidden_shingles
        found += [("copied-text", " ".join(s)) for s in sorted(copied)[:3]]
        return found


def reasons(found: list[tuple[str, str]]) -> str:
    kinds = sorted({kind for kind, _ in found})
    return ", ".join(kinds)


# ---------------------------------------------------------------------------- redaction

def markdown_blocks(text: str) -> list[str]:
    blocks, current, fenced = [], [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            current.append(line)
            fenced = not fenced
            if not fenced:
                blocks.append("\n".join(current))
                current = []
            continue
        if fenced:
            current.append(line)
        elif line.strip() == "":
            if current:
                blocks.append("\n".join(current))
                current = []
            blocks.append("")
        elif TOP_LEVEL_ITEM.match(line) and current:
            # Each top-level list item is its own unit, with its nested items and continuation lines.
            blocks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def redact_markdown(text: str, knowledge: Knowledge, path: str, log: list) -> str:
    out = []
    for index, block in enumerate(markdown_blocks(text)):
        found = knowledge.findings(block) if block else []
        if found:
            out.append(REDACTED_BLOCK.format(reasons=reasons(found)))
            log.append({"path": path, "unit": "block", "index": index, "reasons": reasons(found),
                        "removedSha256": sha256(block.encode("utf-8"))})
        else:
            out.append(block)
    return "\n".join(out)


def redact_contract(text: str, knowledge: Knowledge, path: str, log: list) -> str:
    out = []
    for number, line in enumerate(text.split("\n"), 1):
        found = knowledge.findings(line, prose_only=True)
        if not line.lstrip().startswith("///"):
            # A signature is the contract's point: its words may match a declaration spread over source
            # lines, so only names and literals count against it.
            found = [f for f in found if f[0] != "copied-text"]
        if not found:
            out.append(line)
        elif line.lstrip().startswith("///"):
            indent = line[:len(line) - len(line.lstrip())]
            out.append(indent + REDACTED_LINE.format(reasons=reasons(found)))
            log.append({"path": path, "unit": "line", "index": number, "reasons": reasons(found),
                        "removedSha256": sha256(line.encode("utf-8"))})
        else:
            raise Refusal(f"{path}:{number}: a signature line has a finding ({reasons(found)}), which is not redacted")
    return "\n".join(out)


def unlink_missing(text: str, here: Path, root: Path) -> str:
    def replace(match):
        label, target = match.group(1), match.group(2)
        if target.startswith(("http://", "https://", "mailto:")):
            return match.group(0)
        resolved = (here.parent / target).resolve()
        if resolved.is_relative_to(root.resolve()) and resolved.exists():
            return match.group(0)
        return f"{label} (`{target}`, not in the brief)"
    return LINK.sub(replace, text)


# ---------------------------------------------------------------------------- api

def api(args, target: dict) -> int:
    commit = target["engine"]["commit"]
    with tempfile.TemporaryDirectory(prefix="hoyle-api-") as work:
        tree = Path(work, "tree")
        tree.mkdir()
        with tarfile.open(fileobj=io.BytesIO(git(args.engine, "archive", "--format=tar", commit, binary=True))) as tar:
            tar.extractall(tree, filter="data")
        if args.sdk_override:
            global_json = json.loads((tree / "global.json").read_text(encoding="utf-8"))
            global_json["sdk"]["version"] = args.sdk_override
            (tree / "global.json").write_text(json.dumps(global_json), encoding="utf-8")
        env = dict(os.environ, DOTNET_NOLOGO="1", DOTNET_CLI_TELEMETRY_OPTOUT="1")
        subprocess.run([args.dotnet, "build", "HoyleBackgammon.slnx", "-c", "Release", "--nologo"], cwd=tree, env=env,
                       check=True, capture_output=True)
        bin_dir = tree / "tests/HoyleBackgammon.Tests/bin/Release/net10.0"
        subprocess.run([args.dotnet, "run", "--project", str(HERE / "api-surface/ApiSurface.csproj"), "-c", "Release", "--",
                        "--bin", str(bin_dir), "--assembly", "HoyleBackgammon", "--assembly", "Tabletop.Dice",
                        "--generated", str(tree / "src/HoyleBackgammon/Generated"), "--out", str(args.out)],
                       env=env, check=True)
    digest = sha256(Path(args.out).read_bytes())
    pinned = target["brief"]["apiContract"]["rawSha256"]
    print(f"api contract {args.out}: sha256 {digest} ({'matches' if digest == pinned else 'differs from'} TARGET)")
    return 0 if digest == pinned else 1


# ---------------------------------------------------------------------------- assemble

def write(root: Path, relative: str, data: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def overlay_skeleton(overlay: dict) -> dict:
    skeleton = {}
    for entry, item in overlay.items():
        kept = {k: item[k] for k in ("status", "implementedIn") if k in item}
        if "rulings" in item:
            kept["rulings"] = [{k: r[k] for k in ("id", "span", "answer", "ruledBy", "ruledOn", "record")}
                               for r in item["rulings"]]
        if "declines" in item:
            kept["declines"] = [{"span": d["span"]} for d in item["declines"]]
        skeleton[entry] = kept
    return skeleton


def verify_inputs(target: dict, engine: Path, factory: Path, nupkg: Path) -> None:
    commit = git(engine, "rev-parse", "--verify", f"{target['engine']['commit']}^{{commit}}").strip()
    if commit != target["engine"]["commit"]:
        raise Refusal(f"engine commit {commit} is not TARGET's")
    tag = git(factory, "rev-parse", "--verify", f"{target['factory']['tag']}^{{commit}}").strip()
    if tag != target["factory"]["commit"]:
        raise Refusal(f"{target['factory']['tag']} is {tag} in {factory}, not TARGET's {target['factory']['commit']}")
    if sha256(nupkg.read_bytes()) != target["map"]["nupkgSha256"]:
        raise Refusal(f"{nupkg} is not the pinned map package")


def assemble(args, target: dict) -> int:
    verify_inputs(target, args.engine, args.factory, args.nupkg)
    knowledge = Knowledge(target, args.engine, args.factory, args.nupkg)
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    commit = target["engine"]["commit"]
    factory_commit = target["factory"]["commit"]
    log: list = []

    write(out, f"inputs/map/{args.nupkg.name.lower()}", args.nupkg.read_bytes())
    corpus = blob(args.factory, factory_commit, "examples/hoyle-backgammon/hoyle.txt")
    if sha256(corpus) != target["corpus"]["contentHash"]:
        raise Refusal("the corpus at the factory tag does not hash to the pinned baseline")
    write(out, "inputs/corpus/hoyle.txt", corpus)
    get_factory = (SOURCES / "GET-FACTORY.sh").read_text(encoding="utf-8")
    write(out, "inputs/factory/GET-FACTORY.sh", get_factory.replace("@TAG@", target["factory"]["tag"])
          .replace("@COMMIT@", factory_commit).encode("utf-8"))

    for path in ls(args.factory, factory_commit, "README.md", "docs"):
        if path.endswith(".md"):
            text = blob(args.factory, factory_commit, path).decode("utf-8")
            write(out, f"inputs/factory-docs/{path}", redact_markdown(text, knowledge, f"inputs/factory-docs/{path}",
                                                                      log).encode("utf-8"))

    raw = Path(args.api_contract).read_bytes()
    if sha256(raw) != target["brief"]["apiContract"]["rawSha256"]:
        raise Refusal(f"{args.api_contract} is not the pinned API contract (build it with `api`)")
    write(out, "engine/api-contract.md", redact_contract(raw.decode("utf-8"), knowledge, "engine/api-contract.md",
                                                         log).encode("utf-8"))
    write(out, "engine/conventions.md", (SOURCES / "conventions.md").read_bytes())
    write(out, "README.md", (SOURCES / "README.md").read_bytes())
    overlay = json.loads(blob(args.engine, commit, "corpus-map.overlay.json"))
    write(out, "engine/overlay-skeleton.json", (json.dumps(overlay_skeleton(overlay), indent=2, ensure_ascii=False)
                                                + "\n").encode("utf-8"))
    for item in target["brief"]["verbatim"]:
        write(out, f"engine/build-files/{item['path']}", blob(args.engine, commit, item["path"]))
    for path in ls(args.engine, commit, "docs/decisions"):
        text = blob(args.engine, commit, path).decode("utf-8")
        write(out, f"engine/decisions/{Path(path).name}",
              redact_markdown(text, knowledge, f"engine/decisions/{Path(path).name}", log).encode("utf-8"))

    for md in sorted(out.rglob("*.md")):
        md.write_text(unlink_missing(md.read_text(encoding="utf-8"), md, out), encoding="utf-8")

    problems, disclosures = scan_directory(out, knowledge, target, args.factory, args.nupkg)
    manifest = {
        "target": "rules-factory examples/hoyle-blind-rebuild/TARGET.json (not part of the brief)",
        "factory": {"tag": target["factory"]["tag"], "commit": factory_commit},
        "map": {"packageId": target["map"]["packageId"], "version": target["map"]["version"],
                "nupkgSha256": target["map"]["nupkgSha256"]},
        "apiContractRawSha256": target["brief"]["apiContract"]["rawSha256"],
        "files": [{"path": p.relative_to(out).as_posix(), "sha256": sha256(p.read_bytes())}
                  for p in sorted(out.rglob("*"), key=lambda p: p.relative_to(out).as_posix()) if p.is_file()],
        "redactions": log,
        "disclosures": disclosures,
    }
    data = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    write(out, "MANIFEST.json", data)
    for problem in problems:
        print(f"FAIL {problem}")
    print(f"brief {out}: {len(manifest['files'])} files, {len(log)} redaction(s), "
          f"{sum(d['count'] for d in disclosures)} disclosed occurrence(s); MANIFEST.json sha256 {sha256(data)}")
    return 1 if problems else 0


# ---------------------------------------------------------------------------- scan

def scan_directory(root: Path, knowledge: Knowledge, target: dict, factory: Path, nupkg: Path):
    """Every finding in the brief, the map package and the factory's tools; disclosures are counted, not failed."""
    texts: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if not path.is_file() or rel == "MANIFEST.json" or rel.endswith(".nupkg"):
            continue
        texts.append((rel, path.read_text(encoding="utf-8", errors="replace")))
    with zipfile.ZipFile(nupkg) as package:
        for name in sorted(package.namelist()):
            if name.endswith((".json", ".py", ".props", ".txt", ".nuspec")):
                texts.append((f"inputs/map/{nupkg.name.lower()}!{name}", package.read(name).decode("utf-8", "replace")))
    for path in ls(factory, target["factory"]["commit"], "tools/factory", "tools/check-map.py", ".gitignore"):
        texts.append((f"factory-checkout/{path}", blob(factory, target["factory"]["commit"], path).decode("utf-8", "replace")))

    allowed = {(d["file"], d["kind"], d["name"]): d["count"] for d in target["brief"]["disclosures"]}
    disclosure_files = set(target["brief"]["disclosureFiles"])
    counted: dict[tuple, int] = {}
    problems = []
    for rel, text in texts:
        if rel == "engine/api-contract.md":
            found = [f for line in text.split("\n") for f in knowledge.findings(line, prose_only=True)
                     if line.lstrip().startswith("///") or f[0] != "copied-text"]
        else:
            found = knowledge.findings(text)
        if rel in disclosure_files:
            found = [f for f in found if f[0] != "copied-text"]
        for kind, detail in found:
            key = (rel, kind, detail)
            if key in allowed:
                counted[key] = counted.get(key, 0) + 1
            else:
                problems.append(f"{rel}: {kind}: {detail}")
    for key, count in allowed.items():
        if key[1] == "test-name":
            actual = len(re.findall(r"\b" + re.escape(key[2]) + r"\b", dict(texts).get(key[0], "")))
            if actual != count:
                problems.append(f"{key[0]}: disclosure {key[2]} pinned {count} time(s), found {actual}")
    # By hash: the manifest is part of the brief, and must not point at a name the implementer would otherwise pass over.
    disclosures = [{"file": f, "kind": k, "nameSha256": sha256(n.encode("utf-8")), "count": allowed[(f, k, n)]}
                   for (f, k, n) in sorted(allowed)]
    return sorted(set(problems)), disclosures


def scan(args, target: dict) -> int:
    verify_inputs(target, args.engine, args.factory, args.nupkg)
    knowledge = Knowledge(target, args.engine, args.factory, args.nupkg)
    problems, disclosures = scan_directory(Path(args.dir), knowledge, target, args.factory, args.nupkg)
    manifest = json.loads((Path(args.dir) / "MANIFEST.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path = Path(args.dir) / item["path"]
        if not path.is_file() or sha256(path.read_bytes()) != item["sha256"]:
            problems.append(f"{item['path']}: not the file MANIFEST.json records")
    listed = {item["path"] for item in manifest["files"]}
    extra = [p.relative_to(args.dir).as_posix() for p in Path(args.dir).rglob("*")
             if p.is_file() and p.name != "MANIFEST.json" and p.relative_to(args.dir).as_posix() not in listed]
    problems += [f"{p}: in the brief but not in MANIFEST.json" for p in extra]
    manifest_sha = sha256((Path(args.dir) / "MANIFEST.json").read_bytes())
    if manifest_sha != target["brief"].get("manifestSha256"):
        problems.append(f"MANIFEST.json sha256 {manifest_sha} is not TARGET brief.manifestSha256: not the pinned brief")
    for problem in problems:
        print(f"FAIL {problem}")
    print(f"scan {args.dir}: {'FAIL' if problems else 'PASS'}; {sum(d['count'] for d in disclosures)} disclosed occurrence(s); "
          f"MANIFEST.json sha256 {sha256((Path(args.dir) / 'MANIFEST.json').read_bytes())}")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("api")
    a.add_argument("engine", type=Path)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--dotnet", default=os.environ.get("DOTNET", "dotnet"))
    a.add_argument("--sdk-override")
    b = sub.add_parser("assemble")
    b.add_argument("engine", type=Path)
    b.add_argument("--factory", type=Path, required=True)
    b.add_argument("--nupkg", type=Path, required=True)
    b.add_argument("--api-contract", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("scan")
    s.add_argument("engine", type=Path)
    s.add_argument("--factory", type=Path, required=True)
    s.add_argument("--nupkg", type=Path, required=True)
    s.add_argument("dir", type=Path)
    args = parser.parse_args(argv)
    target = json.loads(args.target.read_text(encoding="utf-8"))
    try:
        return {"api": api, "assemble": assemble, "scan": scan}[args.command](args, target)
    except Refusal as refusal:
        print(f"FAIL {refusal}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
