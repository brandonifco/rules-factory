"""M1 of #3: intake. Open a map package, prove the corpus in hand is the one it was mapped from.

An engine is only as right as the correspondence between its map and its corpus, so nothing
is scaffolded until four things are shown, in this order, and any one that is not shown is a
refusal rather than a warning:

  1. **The package is a map package.** A `.nupkg` built by `tools/pack-map.py` (0015): its
     `build/<id>.props` declares exactly one `RulesFactoryMap` item, and the map, manifest and
     `ConsumerChecker` that item names are all inside the archive. A package without its
     checker (pre-2.0.0 backgammon, or a hand-built zip) cannot run the consumer phase, so it
     is refused, not tolerated.
  2. **The corpus is verifiable here.** The map cites exactly one corpus, the manifest declares
     it, and its `verification` is `committed-copy` (0013). A `local-copy` corpus is NOT
     VERIFIED: an engine produced from it could not re-derive its own baseline in CI.
  3. **The corpus file is the baseline.** The map's `baseline` agrees with the manifest, and
     the file given on the command line hashes to `contentHash` under `hashDerivation`. A
     derivation this module does not know is refused -- a digest computed the wrong way is
     indistinguishable from a changed corpus.
  4. **The package's own checker passes, in its consumer phase**, on the packaged map. Before
     any overlay exists this is the map exactly as published, so a failure here means the
     checker and the map disagree and no engine should be built on them.

What intake cannot do: tell whether the map is *right* about the corpus (the publish gate's
locator checkers and review did that), or whether a newer version of the package exists.

Standard library only.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

FLAT_CONTAINER = "https://api.nuget.org/v3-flatcontainer"

# What each `hashDerivation` covers, and how to recompute it from the file an engine commits.
#
# Both derivations in use today are SHA-256 over the file's bytes exactly as retrieved from
# the manifest's `retrievedFrom`; their names differ because the *bytes* differ from what a
# reader might assume, and that is the whole point of naming a derivation (corpus-map.md):
#
#   * ecfr-versioner-xml -- the XML document the eCFR versioner API serves for the part and
#     date, not the rendered HTML or the printed volume (examples/faa-part-107/README.md);
#   * gutenberg-plain-text-including-boilerplate -- the Project Gutenberg `.txt.utf-8`
#     including its licence header and footer, not the work text alone
#     (examples/hoyle-backgammon/README.md, finding 6).
#
# A derivation that needs normalisation (stripping boilerplate, canonicalising XML) gets its
# own function here; it must never be approximated by the raw-bytes one.
def _sha256_of_bytes(data):
    return hashlib.sha256(data).hexdigest()


HASH_DERIVATIONS = {
    "ecfr-versioner-xml": _sha256_of_bytes,
    "gutenberg-plain-text-including-boilerplate": _sha256_of_bytes,
}

PACKAGE_REF = re.compile(r"^(?P<id>[A-Za-z0-9_.-]+)@(?P<version>[0-9A-Za-z.+-]+)$")
THIS_DIR = "$(MSBuildThisFileDirectory)"


class Refused(Exception):
    """Intake did not pass. Nothing is produced."""


class Usage(Exception):
    """The inputs are not usable at all (missing file, unreadable archive)."""


class Intake:
    """Everything later milestones read, established as true of each other."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


def _note(log, message):
    if log is not None:
        print(message, file=log, flush=True)


# --- locating the package ----------------------------------------------------------------


def _global_packages_folder():
    return os.environ.get("NUGET_PACKAGES") or os.path.join(os.path.expanduser("~"), ".nuget", "packages")


def resolve_package(spec, download_dir, log=None):
    """A `.nupkg` path for `spec`: a file path, or `Id@Version` from the NuGet cache or nuget.org."""
    if os.path.isfile(spec):
        return os.path.abspath(spec)
    match = PACKAGE_REF.match(spec)
    if not match:
        raise Usage(f"--package {spec!r} is neither a .nupkg file nor Id@Version")
    lower_id, version = match["id"].lower(), match["version"].lower()
    name = f"{lower_id}.{version}.nupkg"
    cached = os.path.join(_global_packages_folder(), lower_id, version, name)
    if os.path.isfile(cached):
        _note(log, f"package {spec} from the NuGet global packages folder: {cached}")
        return cached
    url = f"{FLAT_CONTAINER}/{lower_id}/{version}/{name}"
    target = os.path.join(download_dir, name)
    _note(log, f"package {spec} from {url}")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, open(target, "wb") as handle:
            handle.write(response.read())
    except OSError as error:
        raise Usage(f"cannot fetch {url}: {error}")
    return target


# --- reading the package -----------------------------------------------------------------


def _props_path(ref):
    """`$(MSBuildThisFileDirectory)../map/x.json` -> `map/x.json`, relative to the archive root."""
    if not isinstance(ref, str) or not ref.startswith(THIS_DIR):
        raise Refused(f"RulesFactoryMap path {ref!r} is not relative to $(MSBuildThisFileDirectory)")
    joined = os.path.normpath(os.path.join("build", ref[len(THIS_DIR):].replace("\\", "/")))
    if joined.startswith(".."):
        raise Refused(f"RulesFactoryMap path {ref!r} leaves the package")
    return joined.replace(os.sep, "/")


def read_package(nupkg):
    try:
        archive = zipfile.ZipFile(nupkg)
    except (OSError, zipfile.BadZipFile) as error:
        raise Usage(f"{nupkg} is not a readable .nupkg: {error}")
    with archive:
        names = set(archive.namelist())
        nuspecs = [n for n in names if "/" not in n and n.endswith(".nuspec")]
        if len(nuspecs) != 1:
            raise Refused(f"{nupkg}: expected one root .nuspec, found {sorted(nuspecs) or 'none'}")
        metadata = ET.fromstring(archive.read(nuspecs[0])).find("{*}metadata")
        package_id = metadata.findtext("{*}id") if metadata is not None else None
        version = metadata.findtext("{*}version") if metadata is not None else None
        if not package_id or not version:
            raise Refused(f"{nupkg}: the nuspec names no id and version")

        props_name = f"build/{package_id}.props"
        # NuGet matches the props name case-insensitively; so does this.
        props = [n for n in names if n.lower() == props_name.lower()]
        if not props:
            raise Refused(f"{package_id} {version} has no {props_name}, so it declares no "
                          f"RulesFactoryMap item and is not a map package (0015)")
        items = [e for e in ET.fromstring(archive.read(props[0])).iter() if e.tag.endswith("RulesFactoryMap")]
        if len(items) != 1:
            raise Refused(f"{props_name} declares {len(items)} RulesFactoryMap items; a map package declares one")
        item = items[0].attrib
        for field in ("Include", "Manifest", "ConsumerChecker"):
            if not item.get(field):
                raise Refused(f"{props_name}: the RulesFactoryMap item has no {field}")
        if item.get("PackageId") != package_id or item.get("PackageVersion") != version:
            raise Refused(f"{props_name} says {item.get('PackageId')} {item.get('PackageVersion')}; "
                          f"the nuspec says {package_id} {version}")

        parts = {}
        for field, label in (("Include", "map"), ("Manifest", "manifest"), ("ConsumerChecker", "checker")):
            path = _props_path(item[field])
            if path not in names:
                what = ("the consumer-phase checker (#51), so the engine could not run the checks "
                        "its own overlay can change" if label == "checker" else f"its {label}")
                raise Refused(f"{package_id} {version} names {path} as {what}, and the package does not contain it")
            parts[label] = (path, archive.read(path))
    return package_id, version, parts


def _json(label, raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise Refused(f"the packaged {label} is not JSON: {error}")


# --- the corpus --------------------------------------------------------------------------


def verify_corpus(document, manifest, corpus_path):
    if not isinstance(document, dict) or not isinstance(manifest, dict):
        raise Refused("the packaged map or manifest is not a JSON object")
    source_id = document.get("corpus")
    cited = {source_id}
    for entry in document.get("entries") or []:
        locator = entry.get("locator") if isinstance(entry, dict) else None
        if isinstance(locator, dict) and locator.get("sourceId"):
            cited.add(locator["sourceId"])
    if len(cited) != 1:
        raise Refused(f"the map cites {sorted(map(str, cited))}; an engine is produced from exactly one corpus")
    corpora = [c for c in manifest.get("corpora") or [] if isinstance(c, dict) and c.get("sourceId") == source_id]
    if len(corpora) != 1:
        raise Refused(f"the packaged manifest declares {source_id!r} {len(corpora)} times; it must declare it once")
    corpus = corpora[0]

    posture = corpus.get("verification")
    if posture != "committed-copy":
        raise Refused(f"NOT VERIFIED -- {source_id} is {posture!r}, not `committed-copy` (0013): an engine "
                      f"produced from it could not re-derive its baseline wherever it is built")

    baseline = document.get("baseline") or {}
    for field in ("contentHash", "hashDerivation"):
        if baseline.get(field) != corpus.get(field):
            raise Refused(f"the map's baseline.{field} is {baseline.get(field)!r} and the manifest's is "
                          f"{corpus.get(field)!r}; the map is not of the corpus the manifest declares")
    if baseline.get("asOf") != corpus.get("asOf"):
        raise Refused(f"the map's baseline.asOf is {baseline.get('asOf')!r} and the manifest's is {corpus.get('asOf')!r}")

    derivation = corpus.get("hashDerivation")
    derive = HASH_DERIVATIONS.get(derivation)
    if derive is None:
        raise Refused(f"NOT VERIFIED -- no way to compute hashDerivation {derivation!r}; known: "
                      f"{', '.join(sorted(HASH_DERIVATIONS))}")
    try:
        with open(corpus_path, "rb") as handle:
            corpus_bytes = handle.read()
    except OSError as error:
        raise Usage(f"cannot read corpus {corpus_path}: {error}")
    actual = derive(corpus_bytes)
    if actual != corpus.get("contentHash"):
        raise Refused(f"{corpus_path} is not {source_id} at the map's baseline: {derivation} gives {actual}, "
                      f"the map was made of {corpus.get('contentHash')}")
    return corpus, corpus_bytes


# --- the consumer phase ------------------------------------------------------------------


def run_consumer_checks(parts, log=None):
    with tempfile.TemporaryDirectory(prefix="factory-intake-") as scratch:
        paths = {}
        for label, (path, data) in parts.items():
            target = os.path.join(scratch, *path.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(data)
            paths[label] = target
        completed = subprocess.run(
            [sys.executable, paths["checker"], paths["map"], "--manifest", paths["manifest"], "--phase", "consumer"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=scratch)
    _note(log, completed.stdout.rstrip("\n"))
    if completed.returncode != 0:
        raise Refused(f"the package's own check-map.py --phase consumer exited {completed.returncode}")


# --- the whole of intake -----------------------------------------------------------------


def intake(package_spec, corpus_path, log=None):
    with tempfile.TemporaryDirectory(prefix="factory-download-") as downloads:
        nupkg = resolve_package(package_spec, downloads, log)
        package_id, version, parts = read_package(nupkg)
        with open(nupkg, "rb") as handle:
            nupkg_sha256 = hashlib.sha256(handle.read()).hexdigest()
    _note(log, f"--- intake: {package_id} {version}")
    document = _json("map", parts["map"][1])
    manifest = _json("manifest", parts["manifest"][1])
    corpus, corpus_bytes = verify_corpus(document, manifest, corpus_path)
    _note(log, f"corpus {corpus['sourceId']}: {corpus['hashDerivation']} {corpus['contentHash']} matches {corpus_path}")
    _note(log, "--- intake: the package's check-map.py --phase consumer")
    run_consumer_checks(parts, log)
    return Intake(
        package_id=package_id, version=version, nupkg_sha256=nupkg_sha256,
        map=document, map_raw=parts["map"][1],
        manifest=manifest, manifest_raw=parts["manifest"][1],
        checker_raw=parts["checker"][1],
        part_paths={label: path for label, (path, _) in parts.items()},
        corpus=corpus, corpus_bytes=corpus_bytes, corpus_name=os.path.basename(corpus_path),
    )
