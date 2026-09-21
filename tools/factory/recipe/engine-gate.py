#!/usr/bin/env python3
"""The checks scripts/validate.sh runs that are not a dotnet command.

Emitted by rules-factory tools/factory (the gate recipe, #3). Rewritten by every `factory
produce`; do not edit it here. Each subcommand prints what it examined and exits 0 when it
proved its claim, 1 when it did not; `posture` also exits 3 for NOT VERIFIED. A check that
finds nothing to examine fails: a check with no inputs has proven nothing.

  lock-files                         every project on disk has a packages.lock.json
  randomness --manifest M --map MAP  RulesKernel.Randomness is reachable only as the corpus declares
  posture --manifest M --map MAP --name N
                                     the committed corpus hashes to the baseline, under its posture
  regenerate --package-map P --package-manifest M --package-id ID --package-version V --name N [--write]
                                     every *.g.cs is exactly what the factory generates
  provenance                         provenance.json still hashes the files on disk, the overlay set
                                     included (re-produce after an overlay edit); a local SDK
                                     override declares its re-pinned global.json here (#336)
  expected-results                   test projects on disk x target frameworks
  tests-ran DIR EXPECTED             the TRX files show that many result files, and a test
                                     executed for every test project x target framework
  named-tests DIR --map MAP          every test an implemented entry names exists and ran
  rails                              the agent rails hold: read-only reviewers, no dangling
                                     citation, a policy the rails can read

Run from the engine root. Standard library only.
"""
import argparse
import collections
import difflib
import glob
import hashlib
import json
import os
import pathlib
import re
import sys
import types

# derivations() and regenerate() import the vendored scripts/factory modules, and an imported
# module leaves its bytecode behind: scripts/factory/__pycache__/, a path no ownership row covers,
# so the checkout that ran this goes dirty and tools/dispatch-agent.sh refuses to open a worktree
# for the next issue (#194). scripts/validate.sh, which is what usually runs this, exports
# PYTHONDONTWRITEBYTECODE for the same reason, and so does `factory verify`; nothing exports it
# when an agent runs a subcommand directly from its shell. The loader reads this flag when the
# import happens, so it belongs here and not beside the imports it disarms.
sys.dont_write_bytecode = True

ROOT = pathlib.Path.cwd()
IGNORED = {"bin", "obj", ".git", "artifacts", "TestResults"}
OVERLAY = "overlay"
RANDOMNESS_PACKAGE = "RulesKernel.Randomness"
RANDOMNESS = ("none", "seeded")
GENERATED_PROPS = "RulesFactory.Packages.g.props"
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


def declared_randomness(manifest_path, map_path):
    """The `randomness` the package manifest declares for the corpus the package map cites (0019).

    Read from the restored map package, not from anything the engine commits. The package is
    pinned to one version in the generated RulesFactory.Packages.g.props (the regenerate step holds
    that file to a fresh regeneration) and to one content hash in the lock files (restore runs in
    locked mode), so the engine cannot change the declaration without changing which package it is
    built from. provenance.json records the same value, but it is a file in the engine's tree, and
    only `factory provenance` recomputes it; a check that read it could be escaped by editing it.
    Returns (value, problem): exactly one is None.
    """
    try:
        manifest = json.loads(pathlib.Path(manifest_path).read_text(encoding="utf-8"))
        mapped = json.loads(pathlib.Path(map_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return None, f"cannot read the package manifest or map: {error}"
    source_id = mapped.get("corpus") if isinstance(mapped, dict) else None
    corpora = [c for c in (manifest.get("corpora") if isinstance(manifest, dict) else None) or []
               if isinstance(c, dict) and c.get("sourceId") == source_id]
    if len(corpora) != 1:
        return None, f"the package manifest declares the map's corpus {source_id!r} {len(corpora)} times, not once"
    value = corpora[0].get("randomness")
    if isinstance(value, bool) or value not in RANDOMNESS:
        return None, (f"{source_id} declares randomness {value!r}; it must be one of {', '.join(RANDOMNESS)} "
                      "(rules-factory decision 0019), and nothing is assumed when it is missing")
    return value, None


def randomness(args):
    """rules-factory decision 0019: whether an engine may draw random values is the corpus's to say.

    `none`: a rule-bound engine for a corpus with no chance in it draws no random value, so the
    kernel's randomness package must not be reachable, directly or transitively. Lock files list
    every package restore resolves, so they are the evidence; project files are read too, so a
    reference is found even before a lock file records it.

    `seeded`: the engine may reference RulesKernel.Randomness, and its version has one home, the
    generated RulesFactory.Packages.g.props, at the kernel's version. An engine-owned MSBuild file
    that pins it again or overrides its version is refused, so the version cannot drift where no
    regeneration looks."""
    declared, problem = declared_randomness(args.manifest, args.map)
    if problem:
        return report([problem], "")
    locks = on_disk("packages.lock.json")
    problems = [] if locks else ["no packages.lock.json found, so nothing shows what restore resolves"]
    resolved, referenced = [], []
    for lock in locks:
        try:
            document = json.loads(lock.read_text(encoding="utf-8"))
        except ValueError as error:
            problems.append(f"{lock.relative_to(ROOT)} is not JSON: {error}")
            continue
        for framework, packages in (document.get("dependencies") or {}).items():
            for name in packages or {}:
                if name.lower() == RANDOMNESS_PACKAGE.lower():
                    resolved.append(f"{lock.relative_to(ROOT)} ({framework}) resolves {name}")
    pattern = re.escape(RANDOMNESS_PACKAGE)
    for project in on_disk("*.csproj") + on_disk("*.props") + on_disk("*.targets"):
        relative = str(project.relative_to(ROOT)).replace(os.sep, "/")
        text = project.read_text(encoding="utf-8", errors="replace")
        generated_props = relative == GENERATED_PROPS
        if re.search(r'Include\s*=\s*"' + pattern + r'"', text, re.IGNORECASE):
            if declared == "none" or not generated_props:
                referenced.append(f"{relative} references {RANDOMNESS_PACKAGE}")
        if declared == "seeded" and not generated_props:
            if re.search(r'<PackageVersion\b[^>]*?\bInclude\s*=\s*"' + pattern + r'"', text, re.IGNORECASE):
                problems.append(f"{relative} pins {RANDOMNESS_PACKAGE}; its version belongs in {GENERATED_PROPS}, "
                                "at the kernel's version")
            if re.search(r'<PackageReference\b[^>]*?\bInclude\s*=\s*"' + pattern + r'"[^>]*?\bVersion(Override)?\s*=',
                         text, re.IGNORECASE):
                problems.append(f"{relative} gives {RANDOMNESS_PACKAGE} a version of its own; it belongs in "
                                f"{GENERATED_PROPS}, at the kernel's version")
    if declared == "none":
        problems += resolved + referenced
        return report(problems, f"randomness: none -- {len(locks)} lock file(s) and the project files resolve no "
                                f"{RANDOMNESS_PACKAGE}")
    return report(problems, f"randomness: seeded -- {RANDOMNESS_PACKAGE} may be referenced, pinned only in "
                            f"{GENERATED_PROPS} ({len(resolved)} lock-file resolution(s) of it)")


# --- the corpus --------------------------------------------------------------------------

def derivations():
    """The hashDerivations this gate can recompute: intake's HASH_DERIVATIONS, from the copy of the
    factory's intake.py that `factory produce` vendored under scripts/factory/ beside this file.

    There is one table, not two. This gate once kept its own, and a derivation the factory admitted
    (#108, the SRD's) was missing from it, so every engine of that corpus failed here (#106). The
    vendored intake.py is already what `regenerate` imports its siblings from, and its bytes are in
    provenance.json's `generated`. A declared derivation not in the table is a failure: a digest
    nobody re-derived is unchecked."""
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        import intake  # noqa: E402  (the factory's intake, vendored by produce)
    except ImportError as error:
        return None, f"scripts/factory/intake.py cannot be imported ({error}); run `factory produce` again"
    table = getattr(intake, "HASH_DERIVATIONS", None)
    if not isinstance(table, dict) or not table:
        return None, "scripts/factory/intake.py declares no HASH_DERIVATIONS; run `factory produce` again"
    return table, None


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

    table, problem = derivations()
    if problem:
        return report([problem], "")
    problems, verified, unverified = [], [], []
    corpora = [c for c in manifest.get("corpora") or [] if isinstance(c, dict)]
    if not corpora:
        problems.append("the package manifest declares no corpora, so nothing was verified")
    for corpus in corpora:
        sid = corpus.get("sourceId", "?")
        kind = corpus.get("verification")
        boundary = corpus.get("boundaryPolicy")
        expected = corpus.get("contentHash")
        derive = table.get(corpus.get("hashDerivation"))
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
                            f"so the baseline is unchecked (known: {', '.join(sorted(table))})")
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
    """Every *.g.cs, and RulesFactory.Packages.g.props with the kernel and map pins, is what the
    factory's generator makes of merge(package, overlay) and the package id and version, byte for byte.

    The generator (generate.py, and provenance.py for the files that embed provenance.json) is the
    copy under scripts/factory/, written by the same `factory produce` that wrote the files; that
    its bytes are the factory's is provenance's to show (every recipe file is in provenance.json's
    `generated`), not this step's."""
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    import generate  # noqa: E402  (the factory's generator, vendored by produce)
    import provenance  # noqa: E402  (its generated C# that embeds provenance.json)
    import overlay as overlay_step  # noqa: E402  (where the engine's evidence lives, #247)
    import rulings  # noqa: E402  (the owner's rulings the overlay holds, rules-factory decision 0027)

    package = json.loads(pathlib.Path(args.package_map).read_text(encoding="utf-8"))
    declared, problem = declared_randomness(args.package_manifest, args.package_map)
    if problem:
        return report([problem], "")
    try:
        overlay = overlay_step.load(str(ROOT), package)
    except overlay_step.OverlayError as error:
        return report([str(error)], "")
    try:
        model = generate.Model(types.SimpleNamespace(package_id=args.package_id, version=args.package_version,
                                                     randomness=declared),
                               generate.merge(package, overlay, root=str(ROOT)), args.name, rulings.collect(overlay))
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
                            f"{args.package_id}@{args.package_version} + {OVERLAY}/ ({len(overlay)} entry file(s))")


# --- the record -------------------------------------------------------------------------

RECORD = "provenance.json"
RE_PRODUCE = "tools/re-produce.sh"
#: The first provenance format whose `buildInputs` describe the overlay directory (#247).
OVERLAY_FORMAT = 4

#: The local SDK override (#336). `factory verify` runs restore and the gate on another SDK by
#: re-pinning global.json for the length of each -- and global.json is a managed file whose SHA-256
#: this step checks, so those deliberate bytes used to fail here. The override is **declared**, not
#: exempted: `$FACTORY_SDK_OVERRIDE_RECORDED` is a path to the bytes the record hashes, and this step
#: then proves two things instead of one (`repin_problems`).
SDK_OVERRIDE = "FACTORY_DOTNET_SDK_OVERRIDE"
SDK_OVERRIDE_RECORDED = "FACTORY_SDK_OVERRIDE_RECORDED"
GLOBAL_JSON = "global.json"


def repinned(text, version):
    """global.json text with its SDK version set to `version`, laid out as the factory writes it.

    The same three lines as `repin` in the factory's tools/factory/verify.py, which is what writes
    the file compared against here; test_factory_verify.py holds the two to the same bytes, so a
    change to one that the other did not make fails there rather than here.
    """
    document = json.loads(text)
    document["sdk"]["version"] = version
    return json.dumps(document, indent=2) + "\n"


def sdk_override_declaration(environ=None):
    """What this run declares about global.json: (declaration or None, problems).

    A declaration is `{version, pinned, original}`: the SDK `$FACTORY_DOTNET_SDK_OVERRIDE` names,
    the SDK the recorded file pins, and the recorded bytes themselves, read from the path
    `$FACTORY_SDK_OVERRIDE_RECORDED` gives. Both variables together are the declaration, and
    `factory verify` sets them together or not at all; `$FACTORY_DOTNET_SDK_OVERRIDE` on its own --
    a shell that exports it, or a `scripts/validate-engine.sh` run whose engine already *pins* the
    override and adopted it into its record -- declares nothing, and global.json is then compared
    byte for byte like every other managed file.

    A declaration is refused under CI=true, where a green run must mean the SDK the record pins.
    An incomplete or unreadable one is refused too, and refusing it leaves the exact comparison in
    force, so a re-pin nobody could vouch for still fails.
    """
    environ = os.environ if environ is None else environ
    version = (environ.get(SDK_OVERRIDE) or "").strip()
    recorded = (environ.get(SDK_OVERRIDE_RECORDED) or "").strip()
    if not recorded:
        return None, []
    if environ.get("CI") == "true":
        return None, [f"{SDK_OVERRIDE} is an override of the SDK the engine pins, for local runs only, and is "
                      f"refused when CI=true: a green CI run must mean the SDK {RECORD} records"]
    if not version:
        return None, [f"{SDK_OVERRIDE_RECORDED} is set and {SDK_OVERRIDE} names no SDK, so nothing says which SDK "
                      f"{GLOBAL_JSON} was re-pinned to; `factory verify` sets the two together or neither"]
    try:
        original = pathlib.Path(recorded).read_bytes()
        pinned = str(json.loads(original.decode("utf-8"))["sdk"]["version"])
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as error:
        return None, [f"{SDK_OVERRIDE_RECORDED}={recorded} is not a {GLOBAL_JSON} this can read ({error}), so "
                      f"nothing shows which bytes {GLOBAL_JSON} was re-pinned from"]
    return {"version": version, "pinned": pinned, "original": original}, []


def repin_problems(on_disk, item, declared):
    """Whether global.json on disk is the recorded file re-pinned to the declared SDK, and nothing else.

    Two proofs, and the declaration buys exactly one byte of freedom between them: the declared
    original must hash to what the record hashes, and what is on disk must be that original with its
    SDK version replaced. So a declaration can neither hand the gate a global.json the record never
    saw, nor cover an edit to anything else in the file -- `rollForward: disable` above all, which is
    the other half of the pin.
    """
    original = hashlib.sha256(declared["original"]).hexdigest()
    if original != item.get("sha256"):
        return [f"managed[{GLOBAL_JSON}]: {SDK_OVERRIDE_RECORDED} hands the gate bytes {RECORD} does not record "
                f"(recorded {item.get('sha256')}, declared {original}), so nothing says what was re-pinned"]
    expected = repinned(declared["original"].decode("utf-8"), declared["version"]).encode("utf-8")
    if on_disk != expected:
        return [f"managed[{GLOBAL_JSON}]: {SDK_OVERRIDE} declares SDK {declared['version']}, and {GLOBAL_JSON} on "
                f"disk is not the recorded file re-pinned to it (on disk {hashlib.sha256(on_disk).hexdigest()}, "
                f"the declared re-pin {hashlib.sha256(expected).hexdigest()}); an override moves the SDK version "
                f"and nothing else"]
    return []


def record_matches(_args):
    """provenance.json still hashes the bytes on disk: the derived files are not older than the
    overlay they were derived from (#192).

    This compares and nothing else. It re-derives nothing and writes nothing, because **an engine
    cannot author this record.** `factory produce` writes it from a rules-factory checkout: it
    names that checkout's commit, hashes every one of the factory's recipe files, and lists what
    the run itself wrote. An engine has five vendored modules and no run to observe. Decisively, an
    engine can re-derive its `*.g.cs` but not scripts/validate.sh, this file, scripts/map-overlay.py,
    scripts/factory/*.py or the CI workflow -- all recorded as generated, all hashed here. An
    engine-side rewrite would hash whatever is on disk and hand a fresh matching SHA-256 to a
    hand-edited gate, and a gate that re-blesses its own bytes proves nothing.

    **What is compared, and what deliberately is not.** Every `generated` entry, every `managed`
    entry, and the whole of the overlay -- `buildInputs[overlay/*.json]` -- and no other build
    input. Adding a
    PackageReference, a project to the solution or a version to Directory.Packages.props are
    engine-owned acts (decision 0018); making each of them require a re-produce before this goes
    green would produce a gate people route around. Holding the whole of `buildInputs` is
    `factory provenance`'s job, where a real re-produce can tell a legitimate addition from drift.
    The overlay is different in kind: it is the *input to generation*, and appears in `buildInputs`
    only because it happens to be engine-owned. **It is the only comparison that catches every form
    of an unfinished overlay edit.** The `generated` hashes catch one form -- an overlay edit
    followed by `regenerate --write`, which leaves the `*.g.cs` differing from what the record
    hashed -- but an overlay edited and nothing else run moves no generated byte, and only the
    overlay comparison sees it. The engine's backlog used to be hashed here too and could never see
    either form: an item file that still lists an entry someone has since implemented is
    *unchanged*, so its hash matches. What moved is the overlay, and that is the fact this names.

    **A set, not a file (#247).** The overlay is a directory now, so "the overlay as the record
    hashed it" is the whole set of paths and hashes, and the comparison is symmetric: a file whose
    bytes moved is `edited`, a file on disk the record does not list is `added`, and a file the
    record lists that is not on disk is `removed`. Comparing only the files the record happens to
    name would let a new entry's evidence in without a re-produce -- the generated `*.g.cs` would
    still be the old ones, and nothing would say so -- and comparing only the files on disk would
    let one be deleted the same way.

    An engine with no implemented entry has an empty overlay and always did; that is not "examined
    nothing", it is a complete comparison of a set that is empty on both sides, and the check that
    tells the two apart is `provenanceFormat`. A record written before #247 has format 3 or less and
    describes a layout this engine does not have, so it is refused here and named as what it is: a
    record that predates the split.

    **The one file a run may declare, and what it must prove to (#336).** `factory verify` can run
    restore and the gate on another locally installed SDK, because a machine without the pinned one
    could otherwise run neither. The only way to select it is global.json, which is a managed file
    this step hashes -- so the two mechanisms used to disagree about which tree was under
    verification: the override deliberately wrote bytes this step then called a violation, and the
    run that "passed" had been told its own global.json was forged. Neither claim was wrong; the
    handoff between them said nothing.

    The answer is a declaration, not an exemption. `$FACTORY_SDK_OVERRIDE_RECORDED` names a file
    holding the bytes the record hashes, `$FACTORY_DOTNET_SDK_OVERRIDE` names the SDK they were
    re-pinned to, and this step proves **two** things where it otherwise proves one: the declared
    original is the file the record hashes, and what is on disk is exactly that original with its
    SDK version replaced. The tree under verification is therefore known, exactly, and it is not the
    recorded tree -- so this step says so, in the note above the comparison and in the ok line
    itself, and `verify` says it again at the end of the run. A declaration is refused under CI=true,
    and an incomplete, unreadable or unbacked one is refused too; refusing it leaves the exact
    comparison in force, so an undeclared re-pin fails exactly as it did before any of this existed.
    """
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        import provenance  # noqa: E402  (the factory's own record module, vendored by produce)
    except ImportError as error:
        return report([f"scripts/factory/provenance.py cannot be imported ({error}); run `{RE_PRODUCE}`"], "")

    path = ROOT / RECORD
    if not path.is_file():
        return report([f"{RECORD} is not here, so nothing says what this engine was produced from; "
                       f"run `{RE_PRODUCE}`"], "")
    raw = path.read_bytes()
    try:
        recorded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        return report([f"{RECORD} is not readable JSON ({error})"], "")
    if not isinstance(recorded, dict):
        return report([f"{RECORD} is not a JSON object"], "")

    problems, examined = [], 0
    # The factory's own serialisation, so a hand edit shows up even when it kept every hash true.
    if raw != provenance.serialize(recorded):
        problems.append(f"{RECORD} is not in the factory's canonical form; only `factory produce` writes it, "
                        f"and this file has been through another hand")

    declared, refusals = sdk_override_declaration()
    problems += refusals
    declaration_used = False
    if declared is not None:
        print(f"     {GLOBAL_JSON} is {RECORD}'s own file re-pinned from {declared['pinned']} to "
              f"{declared['version']} by {SDK_OVERRIDE}: that is the tree this run verifies, and it does not "
              f"prove the pinned SDK {declared['pinned']}")

    for section in ("generated", "managed"):
        for item in recorded.get(section) or []:
            if not (isinstance(item, dict) and isinstance(item.get("path"), str)):
                problems.append(f"{section}: {item!r} is not a recorded path and hash")
                continue
            examined += 1
            re_pinned = declared is not None and section == "managed" and item["path"] == GLOBAL_JSON
            declaration_used = declaration_used or re_pinned
            where = ROOT / pathlib.Path(*item["path"].split("/"))
            if not where.is_file():
                problems.append(f"{section}[{item['path']}]: recorded, missing on disk")
            elif re_pinned:
                problems += repin_problems(where.read_bytes(), item, declared)
            else:
                actual = hashlib.sha256(where.read_bytes()).hexdigest()
                if actual != item.get("sha256"):
                    problems.append(f"{section}[{item['path']}].sha256: recorded {item.get('sha256')}, "
                                    f"on disk {actual}")

    if declared is not None and not declaration_used:
        problems.append(f"{SDK_OVERRIDE_RECORDED} declares a re-pinned {GLOBAL_JSON}, and {RECORD} records no "
                        f"managed {GLOBAL_JSON} it could have been re-pinned from")

    import overlay as overlay_step  # noqa: E402  (the layout: which paths are the overlay's, #247)

    format_recorded = recorded.get("provenanceFormat")
    if not isinstance(format_recorded, int) or format_recorded < OVERLAY_FORMAT:
        problems.append(f"provenanceFormat: recorded {format_recorded!r}, and the overlay comparison below needs "
                        f"at least {OVERLAY_FORMAT}. A record written before the overlay became a directory "
                        f"describes a layout this engine does not have, so it cannot say which of "
                        f"{OVERLAY}/<entry id>.json were there; run `{RE_PRODUCE}`")
    else:
        recorded_overlay = {item["path"]: item.get("sha256") for item in recorded.get("buildInputs") or []
                            if isinstance(item, dict) and isinstance(item.get("path"), str)
                            and overlay_step.is_overlay_file(item["path"])}
        on_disk_overlay = {path: hashlib.sha256((ROOT / pathlib.Path(*path.split("/"))).read_bytes()).hexdigest()
                           for path in overlay_step.files(str(ROOT))}
        examined += len(set(recorded_overlay) | set(on_disk_overlay))
        for path in sorted(set(recorded_overlay) - set(on_disk_overlay)):
            problems.append(f"buildInputs[{path}]: recorded, missing on disk. An entry's evidence removed without "
                            f"a re-produce leaves every generated file still carrying it")
        for path in sorted(set(on_disk_overlay) - set(recorded_overlay)):
            problems.append(f"buildInputs[{path}]: on disk, and {RECORD} does not record it. An entry's evidence "
                            f"added without a re-produce leaves every generated file older than it")
        for path in sorted(set(recorded_overlay) & set(on_disk_overlay)):
            if recorded_overlay[path] != on_disk_overlay[path]:
                problems.append(f"buildInputs[{path}].sha256: recorded {recorded_overlay[path]}, on disk "
                                f"{on_disk_overlay[path]}. The overlay is the input the generated files are made "
                                f"from, so everything derived from it is older than it is")

    if not examined:
        print(f"error: {RECORD} lists no generated file, no managed file and no {OVERLAY}/ file, so this check "
              f"examined nothing -- and a check that examines nothing is a failure, never an ok", file=sys.stderr)
        return 1
    if problems:
        source = recorded.get("map") or {}
        name = (recorded.get("engine") or {}).get("name")
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        print(f"error: one command fixes all of the above: `{RE_PRODUCE}`. It clones rules-factory at the commit "
              f"{RECORD} names and runs `factory produce --package {source.get('packageId')}@{source.get('version')} "
              f"--corpus <this engine's corpus> --name {name} --out <this engine>` -- which is the only thing that "
              f"writes {RECORD}. Editing it by hand is the defect this step exists to catch.",
              file=sys.stderr)
        return 1
    success = f"{examined} recorded file(s) hash as {RECORD} records, every {OVERLAY}/ file among them"
    if declared is not None:
        success += (f" -- {GLOBAL_JSON} as re-pinned to {declared['version']} by {SDK_OVERRIDE}, so this run did "
                    f"not verify the engine on the SDK {RECORD} pins ({declared['pinned']})")
    return report([], success)


# --- tests ------------------------------------------------------------------------------


# The skipped/not-executed policy (#337). A TRX result carries an `outcome`, and exactly these two
# mean the test was started and reached a verdict of its own: everything else -- `NotExecuted`,
# which is what a `[Fact(Skip = "...")]` becomes, and `Inconclusive`, `NotRunnable`, `Pending`,
# `InProgress`, `Disconnected`, `Warning`, `Aborted`, `Error`, `Timeout` -- is a test that did not
# run, and a test that did not run proves nothing. They are also exactly the two the TRX writer
# counts in `Counters.executed` (executed = passed + failed), which is what lets the summary and
# the results below be cross-checked against each other. A failure is the suite's to report: this
# check counts execution, not success, so `Failed` is a test that ran.
EXECUTED = ("Passed", "Failed")


def test_projects():
    """{lower-cased assembly name: the project that builds it} for every test project on disk.

    `dotnet test` exits 0 when it finds nothing, so the expectation comes from the projects on
    disk, not the solution: a project dropped from the solution would drop out of both counts.
    Lower-cased because the TRX writer lower-cases the `storage` path it records each test
    against, which is the only place a result file says which assembly ran.
    """
    found = {}
    for project in on_disk("*.csproj"):
        text = project.read_text(encoding="utf-8")
        if not re.search(r"<IsTestProject>\s*true\s*</IsTestProject>", text, re.I):
            continue
        named = re.search(r"<AssemblyName>\s*([^<]+?)\s*</AssemblyName>", text)
        found[(named.group(1) if named else project.stem).lower()] = str(project.relative_to(ROOT))
    return found


def expected_results(_args):
    """One result file per test project per target framework: what `tests-ran` is handed."""
    print(len(test_projects()) * max(1, len(target_frameworks())))
    return 0


def _trx(results_dir):
    return sorted(glob.glob(os.path.join(results_dir, "**", "*.trx"), recursive=True))


def _counted(path, frameworks):
    """One TRX read: (executed, not executed, {(assembly, framework) that executed a test}, problems).

    Read from the results themselves -- one entry per test the run reached -- and never from
    `Counters.total`, which counts tests *discovered*. The summary is used only to contradict
    them: a file whose `Counters.executed` is not the number of executed results it carries is
    not evidence of anything, and fails closed rather than being averaged in.
    """
    import xml.etree.ElementTree as ET
    name = os.path.basename(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        return 0, 0, set(), [f"{name}: is not parseable as XML ({error}), so it shows no test running"]
    storage = {unit.get("id"): (unit.get("storage") or "") for unit in root.iterfind(".//t:UnitTest", TRX_NS)}
    # A result with `InnerResults` is a parent the writer synthesised over the rows beneath it;
    # counting the leaves counts each row once, and is every result for the xunit the factory pins.
    leaves = [r for r in root.iterfind(".//t:UnitTestResult", TRX_NS) if r.find("t:InnerResults", TRX_NS) is None]
    executed = [r for r in leaves if r.get("outcome") in EXECUTED]
    problems, pairs = [], set()
    counters = root.find(".//t:ResultSummary/t:Counters", TRX_NS)
    if counters is None:
        problems.append(f"{name}: has no ResultSummary/Counters, so it says nothing about how many tests ran")
    else:
        total, claimed = counters.get("total"), counters.get("executed")
        if not (isinstance(total, str) and total.isdigit() and isinstance(claimed, str) and claimed.isdigit()):
            problems.append(f"{name}: Counters total={total!r} executed={claimed!r} is not a pair of "
                            f"non-negative integers, so the file's own summary cannot be read")
        elif int(claimed) > int(total):
            problems.append(f"{name}: Counters says executed=\"{claimed}\" of total=\"{total}\" -- more tests ran "
                            f"than were discovered, which cannot have happened")
        elif int(claimed) != len(executed):
            seen = ", ".join(f"{outcome}={count}" for outcome, count in sorted(
                collections.Counter(r.get("outcome") for r in leaves).items())) or "no result at all"
            problems.append(f"{name}: Counters says executed=\"{claimed}\", and the file's own results show "
                            f"{len(executed)} executed ({seen}). A summary that contradicts its results is not "
                            f"evidence that anything ran")
    for result in executed:
        parts = [part.lower() for part in re.split(r"[\\/]", storage.get(result.get("testId"), "")) if part]
        assembly = re.sub(r"\.dll$", "", parts[-1]) if parts else ""
        under = [part for part in parts[:-1] if part in frameworks]
        if not assembly or not under:
            problems.append(f"{name}: {result.get('testName')!r} ran, and the file does not say which test "
                            f"assembly or target framework it ran under (storage "
                            f"{storage.get(result.get('testId'), '')!r}), so it cannot count towards the matrix")
        else:
            pairs.add((assembly, under[-1]))
    return len(executed), len(leaves) - len(executed), pairs, problems


def tests_ran(args):
    """The tests the run actually executed, per test project and target framework (#337).

    Three claims, and the message states only what was measured. Every test project on disk wrote
    a result file for every target framework; every one of those pairs executed at least one test,
    so a framework or a project that silently stopped running is not covered by another one that
    ran twice; and the number reported as having run is the number of executed results, under the
    `EXECUTED` policy above. Summing `Counters.total` counted tests that were only discovered, and
    two files declaring `total=12 executed=0 notExecuted=12` were reported as 24 tests that ran.
    """
    projects, frameworks = test_projects(), {f.lower() for f in target_frameworks()}
    files, executed, skipped, pairs, problems = _trx(args.results_dir), 0, 0, set(), []
    for path in files:
        ran, not_run, covered, found = _counted(path, frameworks)
        executed, skipped, pairs = executed + ran, skipped + not_run, pairs | covered
        problems += found
    if len(files) != args.expected:
        problems.append(f"expected {args.expected} result file(s) (test projects on disk x target frameworks), "
                        f"found {len(files)}. A test project silently stopped running.")
    if executed == 0:
        problems.append(f"0 of {executed + skipped} discovered test(s) were executed across all test projects. "
                        f"A discovered test is not a test that ran")
    expected_pairs = {(assembly, framework) for assembly in projects for framework in (frameworks or {""})}
    for assembly, framework in sorted(expected_pairs - pairs):
        problems.append(f"no test executed for {projects[assembly]} under {framework}: the result files show "
                        f"{sorted(f'{a} ({f})' for a, f in pairs)}, and a result file for one framework does not "
                        f"stand in for another")
    for assembly, framework in sorted(pairs - expected_pairs):
        problems.append(f"{assembly} ({framework}) executed tests, and no test project on disk builds that "
                        f"assembly for that target framework -- the results are not this engine's matrix")
    return report(problems, f"{executed} test(s) actually ran ({skipped} skipped or not executed) across "
                            f"{len(files)} result file(s), covering every one of the {len(expected_pairs)} "
                            f"expected test project x target framework pair(s)")


def named_tests(args):
    """rules-factory#2: an `implemented` entry names the tests that prove it. The map cannot show a
    named test exists or ran, so every one must have an executed result (`EXECUTED` above: a
    failure is the suite's to report, a skip is not a run) in every target framework. Names are
    `Class.Method`; a short class name that resolves to two classes is refused rather than
    guessed."""
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
                     if r.get("outcome") in EXECUTED and r.get("testId") in names}:
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


# --- the rails (rules-factory decision 0029) -------------------------------------------------

POLICY = ".github/agent-policy.json"
# A charter that grants any of these can edit what it reviews. The predecessor's own check caught a
# charter claiming read-only while granting `Bash`, which is why this is a check and not a rule.
MUTATING_TOOLS = {"bash", "edit", "write", "notebookedit", "multiedit", "task", "webfetch", "websearch"}
REVIEWER_CHARTERS = (".claude/agents/repo-steward.md", ".claude/agents/rules-conformance.md")
RAIL_DOCUMENTS = ("AGENTS.md", "CLAUDE.md", "docs/agent-team.md")
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")


def charter_tools(text):
    """The `tools:` line of a charter's front matter, as a set, or None when it grants no list."""
    if not text.startswith("---\n"):
        return None
    for line in text.split("---\n", 2)[1].splitlines():
        if line.startswith("tools:"):
            return {tool.strip().lower() for tool in line.split(":", 1)[1].split(",") if tool.strip()}
    return None


def rails(_args):
    """The rails hold together: read-only means read-only, and nothing cites what is not here.

    Two failures this repository's lineage has actually shipped, turned into checks:

      * a charter that described a reviewer as read-only while granting it a tool that writes. A
        reviewer that can edit what it reviews is not a reviewer, and prose saying otherwise is
        worse than nothing because it is believed;
      * enforcement machinery shipped beside documents it cited and did not have -- sixty-one
        references to files that did not exist, several inside runtime error messages, and a
        pre-armed hook whose escape hatch was documented in a file that had been deleted. Rails
        and their manual ship together or neither ships.
    """
    problems = []
    examined = 0

    for relative in REVIEWER_CHARTERS:
        path = ROOT / relative
        if not path.is_file():
            problems.append(f"{relative} is missing: a reviewer role with no charter is a reviewer with no limits")
            continue
        examined += 1
        granted = charter_tools(path.read_text(encoding="utf-8"))
        if granted is None:
            problems.append(f"{relative} grants no explicit `tools:` list, so it inherits every tool. A reviewer "
                            f"that can edit what it reviews is not a reviewer.")
        elif granted & MUTATING_TOOLS:
            problems.append(f"{relative} grants {', '.join(sorted(granted & MUTATING_TOOLS))}, which can write. "
                            f"A read-only charter that grants a writing tool is the predecessor's own bug.")

    for relative in RAIL_DOCUMENTS + REVIEWER_CHARTERS + (".claude/agents/engine-dev.md",):
        path = ROOT / relative
        if not path.is_file():
            problems.append(f"{relative} is missing, and other rails cite it")
            continue
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            examined += 1
            if not (path.parent / target).resolve().exists():
                problems.append(f"{relative} cites {target}, which does not exist in this engine")

    # Every path a rail names in running text, checked the same way: a command an agent is told to
    # run that is not here is the same defect as a broken link, and reads as more authoritative.
    for relative in RAIL_DOCUMENTS:
        path = ROOT / relative
        if not path.is_file():
            continue
        for named in set(re.findall(r"`((?:tools|scripts)/[A-Za-z0-9_.\-/]+\.(?:py|sh))`",
                                    path.read_text(encoding="utf-8"))):
            examined += 1
            if not (ROOT / named).is_file():
                problems.append(f"{relative} tells an agent to run {named}, which this engine does not have")

    policy_path = ROOT / POLICY
    if not policy_path.is_file():
        problems.append(f"{POLICY} is missing: every rail reads its labels, contexts and chain from it")
    else:
        examined += 1
        try:
            document = json.loads(policy_path.read_text(encoding="utf-8"))
        except ValueError as error:
            problems.append(f"{POLICY} is not JSON ({error}); the rails cannot read their own configuration")
        else:
            # The rule is the factory's, read from the generate.py `produce` vendored beside this
            # file: `factory rails --check` and tools/agent-doctor.py judge the policy through the
            # same function, so the three cannot disagree about one file (rules-factory #211).
            sys.path.insert(0, str(ROOT / "scripts" / "factory"))
            try:
                import generate  # noqa: E402  (the factory's generator, vendored by produce)
            except ImportError as error:
                problems.append(f"scripts/factory/generate.py cannot be imported ({error}), so {POLICY} cannot be "
                                f"judged; run `factory produce` again")
            else:
                problems.extend(generate.policy_problems(document, POLICY))

    if not examined:
        print("no rails found to examine -- this check proved nothing", file=sys.stderr)
        return 1
    return report(problems, f"the rails hold: {len(REVIEWER_CHARTERS)} read-only charter(s), {examined} citation(s) "
                            f"and path(s) that resolve, and a policy the rails can read")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("lock-files").set_defaults(run=lock_files)
    m = sub.add_parser("randomness")
    m.add_argument("--manifest", required=True)
    m.add_argument("--map", required=True)
    m.set_defaults(run=randomness)
    p = sub.add_parser("posture")
    p.add_argument("--manifest", required=True)
    p.add_argument("--map", required=True)
    p.add_argument("--name", required=True)
    p.set_defaults(run=posture)
    r = sub.add_parser("regenerate")
    for flag in ("--package-map", "--package-manifest", "--package-id", "--package-version", "--name"):
        r.add_argument(flag, required=True)
    r.add_argument("--write", action="store_true")
    r.set_defaults(run=regenerate)
    sub.add_parser("provenance").set_defaults(run=record_matches)
    sub.add_parser("expected-results").set_defaults(run=expected_results)
    t = sub.add_parser("tests-ran")
    t.add_argument("results_dir")
    t.add_argument("expected", type=int)
    t.set_defaults(run=tests_ran)
    n = sub.add_parser("named-tests")
    n.add_argument("results_dir")
    n.add_argument("--map", required=True)
    n.set_defaults(run=named_tests)
    sub.add_parser("rails").set_defaults(run=rails)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
