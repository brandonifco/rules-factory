#!/usr/bin/env python3
"""Build the NuGet package for one map, and refuse to if the map fails its publish gate.

0015 publishes each map as a versioned package on nuget.org, so a map that fails a check
must never become a version anyone can depend on: a published version can be unlisted and
never deleted. This tool is therefore the gate and the packer in one step. There is no
flag that packs without gating, because a package built without its gate is the artifact
0015 exists to prevent.

The gate, in order:

  * `check-map.py --phase publish` -- every check, structural and status-dependent;
  * the locator checker for the corpus's adapter -- every citation resolves in the
    committed corpus, every absence is searched for, every page of the extent is reached.
    An adapter with no checker here, a corpus that is not `committed-copy`, or a map citing
    more than one corpus is refused as NOT VERIFIED: none of those is a pass.

The licensed-copy exception (0022, #105). With `--licensed-copy-exception`, and only when
tools/factory/licensed_copy.py establishes an allowlisted operator from `gh api user` outside CI,
a `local-copy` corpus is not refused: the file the manifest's `envVar` names on this machine (the
variable an engine's gate reads, 0013) must hash to the manifest's `contentHash` under its
`hashDerivation` (intake's derivations), so a wrong edition does not pack; the locator checker
then runs against it, and every other gate is unchanged. The package has the same parts, and is marked: its nuspec `<tags>` carry
`licensed-copy-exception` and its description begins NOT PUBLISHABLE, naming the operator. The
exception never publishes: the flag is refused with `--tag` (the publish path) and in CI, and
publish-map.yml refuses a `local-copy` map and a marked package on its own account. Without the
flag nothing differs, and a `local-copy` corpus is refused as it always was.

The package, and why it is byte-for-byte deterministic:

  * id `RulesFactory.Maps.<MapName>` from the map's directory name (`hoyle-backgammon` ->
    `RulesFactory.Maps.HoyleBackgammon`); version from `map-package.json` beside the map;
  * `map/corpus-map.json` -- the reviewed file's bytes, verbatim;
  * `map/corpus-manifest.json` -- the manifest's bytes verbatim when it declares exactly the
    corpora the map cites, otherwise only those corpora;
  * `tools/check-map.py` -- the checker's bytes, verbatim (#51). An engine runs its
    `--phase consumer` checks from the restored package rather than from a copy of its own, so
    a change to a status-dependent check reaches the engine with the next version. It imports
    only the standard library, so it is the whole of what that phase needs;
  * `build/<id>.props` -- one `RulesFactoryMap` item, so an engine finds the files (the
    checker included, as `ConsumerChecker`) without knowing where NuGet extracts packages;
  * `LICENCE.txt` -- the package's licence, which the nuspec names with `<license type="file">`
    (0023). The map quotes its corpus verbatim, so the package cannot be under the factory's
    Apache-2.0 alone: the file gives the corpus's terms for the quotations, in the words of the
    map's own terms file, and Apache-2.0 (this repository's LICENSE, verbatim) for the rest;
  * the nuspec and the OPC parts NuGet requires.

The licence (0023). `map-package.json` names the map's corpus terms file, `licence.corpusTerms`, a
.txt file beside it. The corpus's terms are the manifest's `licence` field, which 0015 already makes
a reviewed, major-versioned fact of the corpus; the terms file writes them out for a reader (the
SRD's attribution statement, what "public domain" means for this text) and must restate that field
verbatim, whitespace aside, for every corpus the map cites. A map with no terms file, a terms file
that does not restate the manifest, or a cited corpus with no `licence` is refused and nothing is
written. Nothing defaults to Apache-2.0.

Entries are stored uncompressed with a fixed timestamp and fixed attributes, in a fixed
order, and the core-properties part is named from a digest of the content rather than a
random GUID. `dotnet pack` does none of that (measured: two packs of the same project a
second apart differed in every timestamp, in the psmdcp name, and it stamps the NuGet
client version into the package), which is why this is a script and not a pack project:
the bytes depend on the inputs and nothing else, so the publish job can rebuild them and
prove they are the bytes the gate job checked.

What it cannot do: tell whether the version number is the right one. 0015 says what counts
as a major, minor or patch change; nothing here compares against the previous published
version. The tag-to-version check only proves the tag and the reviewed file agree.

Usage: pack-map.py <map-dir> --out DIR [--tag map/<name>/vX.Y.Z] [--commit SHA]
                   [--licensed-copy-exception]
Exit 0 when the gate passed and the package was written; 1 when the gate refused it;
2 on a usage error.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
# The consumer-phase checker the package carries (#51), and where it sits inside the package.
CHECKER = os.path.join(TOOLS, "check-map.py")
CHECKER_IN_PACKAGE = "tools/check-map.py"
PROJECT_URL = "https://github.com/brandonifco/rules-factory"
sys.path.insert(0, os.path.join(TOOLS, "factory"))
import intake  # noqa: E402  (its HASH_DERIVATIONS, for the local copy's baseline; standard library only)
import licensed_copy  # noqa: E402  (standard library only; decision 0022)

# The nuspec tag that marks a package built under the licensed-copy exception (0022).
# publish-map.yml refuses a package that carries it.
EXCEPTION_TAG = "licensed-copy-exception"

# The locator checker for each adapter. A corpus whose adapter is not here cannot have its
# citations checked, and a map whose citations cannot be checked is not published.
#
# `pdftotext-page-marked` reads both page-marked PDF derivations: the SRD's, every page from 1, and
# `pdftotext-24.02.0-printed-page-marked` (tools/extract-pdf-pages.py, 0028), the printed pages a
# manifest declares, marked with their printed numbers. The checker tells them apart by the latter's
# header line and holds the markers to it; the hash step before it holds the text to contentHash.
LOCATOR_CHECKERS = {
    "plain-text": os.path.join(REPO, "tools", "check-locators.py"),
    "ecfr-xml": os.path.join(REPO, "examples", "faa-part-107", "check-locators-section.py"),
    "pdftotext-page-marked": os.path.join(REPO, "examples", "srd-52-combat", "check-locators-pdf-text.py"),
}

MAP_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
ZIP_TIME = (2000, 1, 1, 0, 0, 0)
# The package's licence file (0023), and this repository's own licence, which covers the factory's
# work inside the package.
LICENCE_IN_PACKAGE = "LICENCE.txt"
FACTORY_LICENCE = os.path.join(REPO, "LICENSE")
# nuget.org requires this licenseUrl beside `<license type="file">`, for clients that predate the
# element; the expression form needs https://licenses.nuget.org/<expression> instead (#50).
FILE_LICENCE_URL = "https://aka.ms/deprecateLicenseUrl"
TERMS_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.txt$")


class Refused(Exception):
    """The gate did not pass. Nothing is written."""


class Usage(Exception):
    """The inputs are not a packable map at all."""


def package_id(map_name):
    return "RulesFactory.Maps." + "".join(part.capitalize() for part in map_name.split("-"))


def tag_for(map_name, version):
    return f"map/{map_name}/v{version}"


def only_one(directory, prefix):
    found = sorted(n for n in os.listdir(directory) if n.startswith(prefix) and n.endswith(".json"))
    if len(found) != 1:
        raise Usage(f"{directory}: expected exactly one {prefix}*.json, found {found or 'none'}")
    return os.path.join(directory, found[0])


def load(path):
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        return raw, json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as error:
        raise Usage(f"cannot read {path}: {error}")


def read_inputs(map_dir):
    map_dir = os.path.abspath(map_dir)
    if not os.path.isdir(map_dir):
        raise Usage(f"{map_dir} is not a directory")
    name = os.path.basename(map_dir)
    if not MAP_NAME.match(name):
        raise Usage(f"map directory {name!r} is not lower-case kebab-case, so it names no package id")
    map_path = only_one(map_dir, "corpus-map")
    manifest_path = only_one(map_dir, "corpus-manifest")
    version_path = os.path.join(map_dir, "map-package.json")
    _, settings = load(version_path)
    version = settings.get("version") if isinstance(settings, dict) else None
    if not isinstance(version, str) or not SEMVER.match(version):
        raise Usage(f"{version_path}: `version` is {version!r}, which is not MAJOR.MINOR.PATCH")
    map_raw, document = load(map_path)
    manifest_raw, manifest = load(manifest_path)
    try:
        with open(CHECKER, "rb") as handle:
            checker_raw = handle.read()
    except OSError as error:
        raise Usage(f"cannot read the consumer-phase checker {CHECKER}: {error}")
    try:
        with open(FACTORY_LICENCE, "rb") as handle:
            factory_licence_raw = handle.read()
    except OSError as error:
        raise Usage(f"cannot read the factory's own licence {FACTORY_LICENCE}: {error}")
    return {
        "dir": map_dir, "name": name, "version": version, "id": package_id(name),
        "settings_path": version_path, "settings": settings,
        "map_path": map_path, "map_raw": map_raw, "map": document,
        "manifest_path": manifest_path, "manifest_raw": manifest_raw, "manifest": manifest,
        "checker_raw": checker_raw, "factory_licence_raw": factory_licence_raw,
    }


def squash(text):
    return " ".join(text.split())


def corpus_terms(inputs):
    """(terms file name, its bytes), once they are shown to state the cited corpus's licence (0023).

    Raises Refused when map-package.json declares no terms file, the file is missing or not UTF-8,
    a cited corpus has no `licence`, or the file does not restate that `licence` verbatim. There is
    no default: a package whose licence was not declared is not packed.
    """
    where = inputs["settings_path"]
    licence = inputs["settings"].get("licence")
    terms = licence.get("corpusTerms") if isinstance(licence, dict) else None
    if not isinstance(terms, str) or not terms:
        raise Refused(f"{where} declares no `licence.corpusTerms`. The package quotes its corpus, so its "
                      f"licence follows the corpus and is never assumed (docs/decisions/0023); name a .txt "
                      f"file beside it that states the corpus's terms")
    if not TERMS_NAME.match(terms):
        raise Refused(f"{where}: `licence.corpusTerms` is {terms!r}; it must name a .txt file in the map "
                      f"directory, with no path")
    path = os.path.join(inputs["dir"], terms)
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise Refused(f"cannot read the corpus terms {path} as UTF-8 text: {error}")
    corpora = {c.get("sourceId"): c for c in inputs["manifest"].get("corpora") or [] if isinstance(c, dict)}
    for source_id in sorted(cited_corpora(inputs["map"])):
        stated = (corpora.get(source_id) or {}).get("licence")
        if not isinstance(stated, str) or not stated.strip():
            raise Refused(f"the manifest gives {source_id} no `licence`, so the terms its quotations would "
                          f"travel under are unknown")
        if squash(stated) not in squash(text):
            raise Refused(f"{terms} does not restate {source_id}'s manifest `licence` verbatim ({stated!r}). "
                          f"The manifest is the source of truth for a corpus's terms, and the package's "
                          f"licence file must carry them (docs/decisions/0023)")
    return terms, raw


def licence_file(inputs):
    """The package's LICENCE.txt: the corpus's terms for the quotations, Apache-2.0 for the rest."""
    terms, terms_raw = inputs["corpus_terms"]
    cited = ", ".join(sorted(cited_corpora(inputs["map"])))
    head = (
        f"{inputs['id']} {inputs['version']} -- licence\n"
        "\n"
        "This package holds material under two sets of terms. Neither replaces the other.\n"
        "\n"
        "1. The corpus text it quotes. The `evidence` quotations in map/corpus-map.json, and any\n"
        f"   other verbatim text of corpus {cited} in map/corpus-map.json or\n"
        "   map/corpus-manifest.json, are that corpus's text, excerpted verbatim from the corpus file\n"
        "   the manifest identifies by its contentHash. They are under the corpus's terms, part A\n"
        "   below. rules-factory does not relicense them, and Apache-2.0 does not apply to them.\n"
        "\n"
        "2. Everything else. tools/check-map.py, build/*.props, and map/corpus-map.json and\n"
        "   map/corpus-manifest.json apart from the corpus text they quote (the entries' structure,\n"
        "   ids, names, notes, relations and questions) are the work of rules-factory\n"
        "   (https://github.com/brandonifco/rules-factory), licensed under the Apache License,\n"
        "   Version 2.0, part B below.\n"
        "\n"
        f"===== A. Terms of the corpus text ({terms}, beside the map in rules-factory) =====\n"
        "\n"
    ).encode("utf-8")
    middle = (
        "\n"
        "===== B. Apache License, Version 2.0 (rules-factory's LICENSE) =====\n"
        "\n"
    ).encode("utf-8")
    if not terms_raw.endswith(b"\n"):
        terms_raw += b"\n"
    return head + terms_raw + middle + inputs["factory_licence_raw"]


def cited_corpora(document):
    cited = {document.get("corpus")} if isinstance(document, dict) else set()
    for item in document.get("entries") or [] if isinstance(document, dict) else []:
        locator = item.get("locator") if isinstance(item, dict) else None
        if isinstance(locator, dict) and locator.get("sourceId"):
            cited.add(locator["sourceId"])
    return {c for c in cited if isinstance(c, str)}


def run_step(what, argv):
    print(f"--- gate: {what}", flush=True)
    completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n", flush=True)
    if completed.returncode != 0:
        raise Refused(f"{what} exited {completed.returncode}")


def gate(inputs, repo_root, operator=None):
    """Run every gate, raising Refused at the first that fails.

    `operator` is the allowlisted login when the licensed-copy exception is in force (0022), else
    None; it changes only where a `local-copy` corpus's bytes are read from. Returns the sourceId
    the exception was used for, or None when it was not needed.
    """
    run_step("check-map.py --phase publish", [
        sys.executable, CHECKER, inputs["map_path"],
        "--manifest", inputs["manifest_path"], "--repo-root", repo_root, "--phase", "publish"])

    corpora = {c.get("sourceId"): c for c in inputs["manifest"].get("corpora") or [] if isinstance(c, dict)}
    cited = cited_corpora(inputs["map"])
    if len(cited) != 1:
        raise Refused(f"NOT VERIFIED -- the map cites {sorted(cited)}; every locator checker reads "
                      f"exactly one corpus, so these citations cannot all be checked")
    source_id = next(iter(cited))
    corpus = corpora.get(source_id)
    if corpus is None:
        raise Refused(f"the map cites {source_id!r}, which the manifest does not declare")
    excepted = operator is not None and corpus.get("verification") == "local-copy"
    if corpus.get("verification") != "committed-copy" and not excepted:
        raise Refused(f"NOT VERIFIED -- {source_id} is {corpus.get('verification')!r}, not "
                      f"`committed-copy`, so no publish job can read the corpus to check a citation")
    checker = LOCATOR_CHECKERS.get(corpus.get("adapter"))
    if checker is None:
        raise Refused(f"NOT VERIFIED -- no locator checker for adapter {corpus.get('adapter')!r}; "
                      f"known: {', '.join(sorted(LOCATOR_CHECKERS))}")
    if excepted:
        variable = corpus.get("envVar")
        text = os.environ.get(variable) if isinstance(variable, str) and variable else None
        if not text:
            raise Refused(f"NOT VERIFIED -- {source_id} is `local-copy` and ${variable} is not set, so the "
                          f"licensed copy is not here to check citations against; set it to the local file")
        if not os.path.isfile(text):
            raise Refused(f"NOT VERIFIED -- ${variable} is {text!r}, which is not a file")
        # A wrong edition could still resolve most citations; only the baseline hash says it is the
        # corpus the map was made of. Computed as intake computes it, with intake's own derivations.
        derive = intake.HASH_DERIVATIONS.get(corpus.get("hashDerivation"))
        if derive is None:
            raise Refused(f"NOT VERIFIED -- no way to compute hashDerivation {corpus.get('hashDerivation')!r} "
                          f"for the local copy; known: {', '.join(sorted(intake.HASH_DERIVATIONS))}")
        with open(text, "rb") as handle:
            actual = derive(handle.read())
        if actual != corpus.get("contentHash"):
            raise Refused(f"${variable} ({text}) is not {source_id} at the manifest's baseline: "
                          f"{corpus.get('hashDerivation')} gives {actual}, the manifest pins {corpus.get('contentHash')}")
        print(f"--- gate: the local copy at ${variable} hashes to the manifest's contentHash "
              f"({corpus.get('hashDerivation')})", flush=True)
        what = f"{os.path.relpath(checker, REPO)} ({corpus.get('adapter')}, the local copy at ${variable})"
    else:
        text = os.path.join(os.path.dirname(inputs["manifest_path"]), str(corpus.get("committedPath")))
        what = f"{os.path.relpath(checker, REPO)} ({corpus.get('adapter')})"
    run_step(what, [sys.executable, checker, inputs["map_path"], text])
    return source_id if excepted else None


def packaged_manifest(inputs):
    """The manifest entries for the corpora this map cites -- verbatim when that is all of it."""
    manifest = inputs["manifest"]
    cited = cited_corpora(inputs["map"])
    corpora = [c for c in manifest.get("corpora") or [] if isinstance(c, dict)]
    if {c.get("sourceId") for c in corpora} == cited and len(corpora) == len(cited):
        return inputs["manifest_raw"]
    narrowed = dict(manifest, corpora=[c for c in corpora if c.get("sourceId") in cited])
    return (json.dumps(narrowed, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def xml_escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def description(inputs):
    document = inputs["map"]
    baseline = document.get("baseline") or {}
    as_of = baseline.get("asOf")
    operator = inputs.get("exception_operator")
    marker = (f"NOT PUBLISHABLE: built locally under the licensed-copy exception by {operator} "
              f"(docs/decisions/0022); its corpus is licensed. " if operator else "")
    return (marker + f"Corpus map {inputs['name']} ({len(document.get('entries') or [])} entries), true of corpus "
            f"{document.get('corpus')} at baseline {baseline.get('hashDerivation')}:"
            f"{baseline.get('contentHash')}"
            + (f" as of {as_of}" if as_of else " (timeless: no asOf)")
            + f", schemaVersion {document.get('schemaVersion')}. Carries corpus-map.json, the "
              f"manifest entry of the corpus it cites, and tools/check-map.py for an engine's "
              f"--phase consumer checks. Published by rules-factory; see "
              f"docs/decisions/0015 for what a version asserts and what a consumer may overlay. "
              f"Licence: {LICENCE_IN_PACKAGE}. The map quotes its corpus verbatim, and those quotations "
              f"are under the corpus's own terms, not Apache-2.0 (docs/decisions/0023).")


def parts(inputs, commit):
    pid, version = inputs["id"], inputs["version"]
    marker = f" {EXCEPTION_TAG}" if inputs.get("exception_operator") else ""
    repository = (f'    <repository type="git" url="{PROJECT_URL}.git"'
                  + (f' commit="{xml_escape(commit)}"' if commit else "") + " />\n")
    nuspec = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">\n'
        "  <metadata>\n"
        f"    <id>{pid}</id>\n"
        f"    <version>{version}</version>\n"
        "    <authors>Brandon</authors>\n"
        # A file, not an SPDX expression (0023): no expression says which parts are under which
        # terms, carries an attribution statement, or names a public-domain corpus.
        f'    <license type="file">{LICENCE_IN_PACKAGE}</license>\n'
        # nuget.org rejects a licence without the licenseUrl old clients read (#50).
        f"    <licenseUrl>{FILE_LICENCE_URL}</licenseUrl>\n"
        f"    <projectUrl>{PROJECT_URL}</projectUrl>\n"
        f"    <description>{xml_escape(description(inputs))}</description>\n"
        f"    <tags>rules-factory corpus-map {xml_escape(inputs['map'].get('corpus'))}{marker}</tags>\n"
        + repository +
        "  </metadata>\n"
        "</package>\n"
    ).encode("utf-8")
    props = (
        "<Project>\n"
        "  <!-- Generated by rules-factory tools/pack-map.py. The map this package carries, for an\n"
        "       engine's gate to merge its overlay onto, and the checker that gate runs on the merge\n"
        "       in its consumer phase (docs/decisions/0015). -->\n"
        "  <ItemGroup>\n"
        f'    <RulesFactoryMap Include="$(MSBuildThisFileDirectory)../map/corpus-map.json"\n'
        f'                     Manifest="$(MSBuildThisFileDirectory)../map/corpus-manifest.json"\n'
        f'                     ConsumerChecker="$(MSBuildThisFileDirectory)../{CHECKER_IN_PACKAGE}"\n'
        f'                     PackageId="{pid}"\n'
        f'                     PackageVersion="{version}" />\n'
        "  </ItemGroup>\n"
        "</Project>\n"
    ).encode("utf-8")
    content = [
        (f"{pid}.nuspec", nuspec),
        ("map/corpus-map.json", inputs["map_raw"]),
        ("map/corpus-manifest.json", packaged_manifest(inputs)),
        (CHECKER_IN_PACKAGE, inputs["checker_raw"]),
        (f"build/{pid}.props", props),
        (LICENCE_IN_PACKAGE, licence_file(inputs)),
    ]
    digest = hashlib.sha256()
    for path, data in content:
        digest.update(path.encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
    core_name = f"package/services/metadata/core-properties/{digest.hexdigest()[:32]}.psmdcp"
    core = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<coreProperties xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns="http://schemas.openxmlformats.org/package/2006/metadata/core-properties">\n'
        "  <dc:creator>Brandon</dc:creator>\n"
        f"  <dc:description>{xml_escape(description(inputs))}</dc:description>\n"
        f"  <dc:identifier>{pid}</dc:identifier>\n"
        f"  <version>{version}</version>\n"
        f"  <keywords>rules-factory corpus-map {xml_escape(inputs['map'].get('corpus'))}{marker}</keywords>\n"
        "  <lastModifiedBy>rules-factory tools/pack-map.py</lastModifiedBy>\n"
        "</coreProperties>\n"
    ).encode("utf-8")
    rels = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        f'  <Relationship Type="http://schemas.microsoft.com/packaging/2010/07/manifest" '
        f'Target="/{pid}.nuspec" Id="Rnuspec" />\n'
        f'  <Relationship Type="http://schemas.openxmlformats.org/package/2006/relationships/'
        f'metadata/core-properties" Target="/{core_name}" Id="Rcore" />\n'
        "</Relationships>\n"
    ).encode("utf-8")
    types = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />\n'
        '  <Default Extension="psmdcp" ContentType="application/vnd.openxmlformats-package.core-properties+xml" />\n'
        '  <Default Extension="nuspec" ContentType="application/octet" />\n'
        '  <Default Extension="json" ContentType="application/octet" />\n'
        '  <Default Extension="props" ContentType="application/octet" />\n'
        '  <Default Extension="py" ContentType="application/octet" />\n'
        '  <Default Extension="txt" ContentType="application/octet" />\n'
        "</Types>\n"
    ).encode("utf-8")
    return [("_rels/.rels", rels)] + content + [(core_name, core), ("[Content_Types].xml", types)]


def write_package(inputs, out_dir, commit):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{inputs['id']}.{inputs['version']}.nupkg")
    temporary = path + ".partial"
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in parts(inputs, commit):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, data)
    os.replace(temporary, path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gate and pack one corpus map as a NuGet package (0015).")
    parser.add_argument("map_dir")
    parser.add_argument("--out", required=True, help="directory the .nupkg is written to")
    parser.add_argument("--tag", help="the pushed tag; must be map/<map-dir-name>/v<version>")
    parser.add_argument("--commit", help="commit recorded in the nuspec's <repository>")
    parser.add_argument("--repo-root", default=REPO, help="root decision-record paths resolve against")
    parser.add_argument(licensed_copy.FLAG, dest="licensed_copy_exception", action="store_true",
                        help="an allowlisted operator packs a local-copy map into a local package marked "
                             "unpublishable (decision 0022); refused with --tag and in CI")
    args = parser.parse_args(argv)

    try:
        inputs = read_inputs(args.map_dir)
        if args.tag is not None and args.tag != tag_for(inputs["name"], inputs["version"]):
            raise Usage(f"tag {args.tag!r} does not match {tag_for(inputs['name'], inputs['version'])!r} "
                        f"from map-package.json; bump the version in a reviewed commit, then tag that commit")
        operator = None
        if args.licensed_copy_exception:
            if args.tag is not None:
                raise Refused(f"{licensed_copy.FLAG} never publishes, and --tag is the publish path (0022)")
            operator = licensed_copy.authorise()
        print(f"{inputs['id']} {inputs['version']} from {inputs['map_path']}")
        inputs["corpus_terms"] = corpus_terms(inputs)
        if gate(inputs, args.repo_root, operator):
            inputs["exception_operator"] = operator
    except Usage as error:
        print(f"pack-map: {error}", file=sys.stderr)
        return 2
    except (Refused, licensed_copy.Refused) as error:
        print(f"pack-map: REFUSED -- {error}. No package was written.", file=sys.stderr)
        return 1

    path = write_package(inputs, args.out, args.commit)
    with open(path, "rb") as handle:
        sha = hashlib.sha256(handle.read()).hexdigest()
    print(f"packed {path}")
    if inputs.get("exception_operator"):
        print(f"{licensed_copy.attestation(operator)}: NOT PUBLISHABLE, tagged {EXCEPTION_TAG}")
    print(f"sha256 {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
