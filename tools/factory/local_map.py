"""Where a licensed-copy engine's map package comes from on the operator's machine (#142, decision 0028).

A map of a licensed `local-copy` corpus is never published (0022), so nuget.org never serves it, and
the managed NuGet.config (generate.py) names nuget.org and nothing else. The package reaches restore
through the NuGet global packages folder instead: the operator packs it (`pack-map.py
--licensed-copy-exception --out <feed>`), names that directory in FEED_VAR, and `produce`, `verify`
and `provenance` under the exception do the rest:

  * `resolve` -- the `.nupkg` to read. A `--package` file is itself. `Id@Version` (given, or read
    from provenance.json) is the global packages folder's copy when it has one, and otherwise
    `<feed>/<Id>.<Version>.nupkg`, so intake never goes to nuget.org for a package that is not there.
  * `seed` -- before anything restores, the global packages folder holds exactly that package. When
    it is absent, a throwaway restore runs in a temporary directory outside the engine: one project
    referencing `Id` at `[Version]`, and a NuGet.config whose only source is a temporary folder
    holding a copy of the one `.nupkg`. NuGet itself extracts it, so the folder's layout is NuGet's.
    When a package of that id and version is already there, its `.nupkg.sha512` must be the
    package's, or the run is refused naming the directory to delete: the lock files pin the content
    hash, so a different package under the same id and version would fail the gate's locked restore
    with a message that does not say why.

Before either, the file's SHA-256 must be what provenance records (`nupkgSha256`), when there is a
record: the package that is restored is the package the engine was produced from.

What this never does: add a source to the engine's NuGet.config, write anything into the engine, or
run in CI (the exception is refused there before this module is reached). The feed directory must
be outside every git work tree, as the licensed copy is, so the package cannot be committed by a
`git add` in the directory that holds it.

Standard library only. Not vendored into engines: the engine's gate restores from the global
packages folder like any other package, and knows nothing of where the package came from.
"""
import base64
import hashlib
import os
import re
import shutil
import subprocess
import tempfile

import intake as intake_step

FEED_VAR = "RULES_FACTORY_LOCAL_MAP_FEED"
PACKAGE_REF = intake_step.PACKAGE_REF
# Seconds the throwaway restore may take: it reads one local file, and needs no network.
SEED_TIMEOUT = 600


def global_packages_folder():
    return os.environ.get("NUGET_PACKAGES") or os.path.join(os.path.expanduser("~"), ".nuget", "packages")


def cached(package_id, version):
    """The global packages folder's directory for `package_id` `version` (it may not exist)."""
    return os.path.join(global_packages_folder(), package_id.lower(), version.lower())


def _sha512_b64(path):
    with open(path, "rb") as handle:
        return base64.b64encode(hashlib.sha512(handle.read()).digest()).decode("ascii")


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def inside_git_work_tree(directory):
    """Whether `directory` is inside a git work tree. No git on PATH counts as not knowing: False."""
    try:
        done = subprocess.run(["git", "-C", directory, "rev-parse", "--is-inside-work-tree"],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stdout.strip() == "true"


def feed(environ=None):
    """The directory FEED_VAR names, refused when it is unset, relative, missing or inside a git work tree."""
    environ = os.environ if environ is None else environ
    value = (environ.get(FEED_VAR) or "").strip()
    if not value:
        raise intake_step.Refused(
            f"${FEED_VAR} is not set. A licensed-copy map is never published, so restore can only find it where "
            f"you put it: set {FEED_VAR} to the directory `pack-map.py --licensed-copy-exception --out` wrote the "
            f".nupkg into, outside any git work tree (docs/decisions/0028)")
    if not os.path.isabs(value) or not os.path.isdir(value):
        raise intake_step.Refused(f"${FEED_VAR} is {value!r}, which is not an absolute path to a directory")
    if inside_git_work_tree(value):
        raise intake_step.Refused(f"${FEED_VAR} is {value!r}, which is inside a git work tree; a licensed-copy map "
                                  f"package is never committed, so keep it outside every repository (0022, 0028)")
    return value


def in_feed(directory, package_id, version):
    """`<directory>/<Id>.<Version>.nupkg`, matched case-insensitively as NuGet matches ids; None when absent."""
    wanted = f"{package_id}.{version}.nupkg".lower()
    matches = sorted(name for name in os.listdir(directory) if name.lower() == wanted)
    return os.path.join(directory, matches[0]) if matches else None


def resolve(spec, record=None, strict=True):
    """The package spec `produce`, `verify` or `provenance` should read, for a licensed-copy engine.

    `spec` is `--package` (a path, `Id@Version`, or None for provenance's), `record` the engine's
    provenance.json (or None). A file is returned as it is; so is `Id@Version` that the global packages
    folder holds. Otherwise the feed's file is returned, or the run is refused naming FEED_VAR. With
    `strict` False (produce, before intake knows the corpus is local-copy), `spec` is returned when
    FEED_VAR is unset or holds no such file; a FEED_VAR that is set and unusable is still refused.
    """
    if spec and os.path.isfile(spec):
        return spec
    if spec:
        match = PACKAGE_REF.match(spec)
        if not match:
            return spec  # intake names the usage error
        package_id, version = match["id"], match["version"]
    else:
        source = (record or {}).get("map") or {}
        package_id, version = source.get("packageId"), source.get("version")
        if not (isinstance(package_id, str) and isinstance(version, str)):
            return spec
    name = f"{package_id.lower()}.{version.lower()}.nupkg"
    if os.path.isfile(os.path.join(cached(package_id, version), name)):
        return spec or f"{package_id}@{version}"
    if not strict and not (os.environ.get(FEED_VAR) or "").strip():
        return spec
    directory = feed()
    found = in_feed(directory, package_id, version)
    if found is None and not strict:
        return spec
    if found is None:
        raise intake_step.Refused(f"{package_id} {version} is not in the NuGet global packages folder, and "
                                  f"${FEED_VAR} ({directory}) holds no {package_id}.{version}.nupkg; pack it there "
                                  f"with `pack-map.py --licensed-copy-exception --out {directory}`")
    return found


def seed(nupkg, package_id, version, expected_sha256, dotnet="dotnet"):
    """Make the global packages folder hold `nupkg` as `package_id` `version`, through NuGet itself.

    Returns what happened, as a line for the log. Raises intake.Refused when the file is not the
    package provenance records, when the folder holds another package under that id and version, or
    when the throwaway restore fails or does not leave the package there.
    """
    if expected_sha256 and _sha256(nupkg) != expected_sha256:
        raise intake_step.Refused(f"{nupkg} has sha256 {_sha256(nupkg)}, and the engine was produced from "
                                  f"{package_id} {version} at {expected_sha256}; restore would take a different map")
    expected = _sha512_b64(nupkg)
    directory = cached(package_id, version)
    marker = os.path.join(directory, f"{package_id.lower()}.{version.lower()}.nupkg.sha512")
    if os.path.isfile(marker):
        with open(marker, encoding="utf-8") as handle:
            present = handle.read().strip()
        if present != expected:
            raise intake_step.Refused(
                f"the NuGet global packages folder already holds {package_id} {version} with sha512 {present}, not "
                f"{nupkg} ({expected}); another package was restored under that id and version. Delete {directory} "
                f"and run this again")
        return f"{package_id} {version} is already in the NuGet global packages folder ({directory}), sha512 matches"
    with tempfile.TemporaryDirectory(prefix="factory-local-map-") as scratch:
        source = os.path.join(scratch, "source")
        os.makedirs(source)
        shutil.copyfile(nupkg, os.path.join(source, os.path.basename(nupkg)))
        project = os.path.join(scratch, "seed")
        os.makedirs(project)
        with open(os.path.join(project, "NuGet.config"), "w", encoding="utf-8") as handle:
            handle.write(
                '<?xml version="1.0" encoding="utf-8"?>\n<configuration>\n'
                f'  <packageSources>\n    <clear />\n    <add key="local-map" value="{_xml(source)}" />\n'
                '  </packageSources>\n'
                '  <packageSourceMapping>\n    <clear />\n    <packageSource key="local-map">\n'
                '      <package pattern="*" />\n    </packageSource>\n  </packageSourceMapping>\n'
                '</configuration>\n')
        framework = _framework(dotnet, project)
        with open(os.path.join(project, "Seed.csproj"), "w", encoding="utf-8") as handle:
            handle.write(
                '<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n'
                f"    <TargetFramework>{framework}</TargetFramework>\n"
                "    <RestorePackagesWithLockFile>false</RestorePackagesWithLockFile>\n"
                "    <ManagePackageVersionsCentrally>false</ManagePackageVersionsCentrally>\n"
                "  </PropertyGroup>\n  <ItemGroup>\n"
                f'    <PackageReference Include="{_xml(package_id)}" Version="[{_xml(version)}]" />\n'
                "  </ItemGroup>\n</Project>\n")
        # Nothing above the scratch directory may supply MSBuild files of its own.
        for guard in ("Directory.Build.props", "Directory.Build.targets", "Directory.Packages.props"):
            with open(os.path.join(project, guard), "w", encoding="utf-8") as handle:
                handle.write("<Project />\n")
        try:
            done = subprocess.run([dotnet, "restore", "Seed.csproj", "-p:RestoreLockedMode=false"], cwd=project,
                                  capture_output=True, text=True, timeout=SEED_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as error:
            raise intake_step.Refused(f"cannot run `{dotnet} restore` to put {package_id} {version} in the NuGet "
                                      f"global packages folder: {error}")
        if done.returncode != 0:
            tail = " ".join((done.stdout + done.stderr).split())[-600:]
            raise intake_step.Refused(f"`dotnet restore` could not put {package_id} {version} from {nupkg} in the "
                                      f"NuGet global packages folder: {tail}")
    if not os.path.isfile(marker):
        raise intake_step.Refused(f"`dotnet restore` passed, and {marker} does not exist; NUGET_PACKAGES may name "
                                  f"another folder than the one restore used")
    with open(marker, encoding="utf-8") as handle:
        if handle.read().strip() != expected:
            raise intake_step.Refused(f"{marker} does not hold the sha512 of {nupkg} after restore")
    return f"put {package_id} {version} from {nupkg} in the NuGet global packages folder ({directory})"


def _xml(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _framework(dotnet, cwd):
    """`net<major>.0` for the SDK `dotnet` runs in `cwd`, whose targeting pack ships with it; net8.0 when unknown."""
    try:
        done = subprocess.run([dotnet, "--version"], cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return "net8.0"
    match = re.match(r"^(\d+)\.", done.stdout.strip()) if done.returncode == 0 else None
    return f"net{match.group(1)}.0" if match else "net8.0"
