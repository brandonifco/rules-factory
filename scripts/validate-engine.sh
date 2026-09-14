#!/usr/bin/env bash
# The factory's output, held to the same standard as the factory: produce an engine from
# scratch, then prove it restores, builds warning-free, passes its generated tests, and
# recomputes to the provenance it records.
#
# scripts/validate.sh proves the Python machinery. It cannot prove that what the machinery
# writes is a .NET solution that builds, because that needs the SDK the kernel pins, and the
# only test that tried (tools/tests/test_factory_provenance.py) skips without it. A green run
# that skipped the one check that mattered is a check that examined nothing, so here a missing
# or wrong SDK is a failure, never a skip.
#
# After its own restore/build/test, it also runs the gate the engine ships with
# (scripts/validate.sh full, emitted from tools/factory/recipe/).
#
# The engine is produced from the hoyle-backgammon example: a small map, a non-RPG domain, and
# a package published on nuget.org (restore resolves it, and RulesKernel, from there).
#
# Local runs only: FACTORY_DOTNET_SDK_OVERRIDE=<version> rewrites the scratch engine's
# global.json to that SDK, for a machine that lacks the pinned one. global.json is write-once
# scaffold, not a generated file, so provenance is unaffected -- but the build then proves the
# engine on a toolchain the kernel does not pin. CI never sets it, and this script refuses it
# when CI=true.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
NAME=HoyleBackgammon
MAP_DIR=examples/hoyle-backgammon
CORPUS="$MAP_DIR/hoyle.txt"

fail() { printf 'validate-engine.sh: FAIL -- %s\n' "$*" >&2; exit 1; }
step() { printf '\n==> %s\n' "$*"; }

# The one source of truth for the SDK: the pin generate.py writes into every global.json.
sdk_pin() {
  python3 - "$ROOT/tools/factory" <<'PY'
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("factory_generate_pin", os.path.join(sys.argv[1], "generate.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.SDK_VERSION)
PY
}

if [ "${1:-}" = "--print-sdk" ]; then
  sdk_pin
  exit 0
fi
[ $# -eq 0 ] || { echo "usage: $0 [--print-sdk]" >&2; exit 2; }

PIN="$(sdk_pin)"
[ -n "$PIN" ] || fail "could not read SDK_VERSION from tools/factory/generate.py"
SDK="$PIN"
if [ -n "${FACTORY_DOTNET_SDK_OVERRIDE:-}" ]; then
  [ "${CI:-}" != "true" ] || fail "FACTORY_DOTNET_SDK_OVERRIDE is for local runs only and is refused when CI=true"
  SDK="$FACTORY_DOTNET_SDK_OVERRIDE"
  printf 'WARNING: FACTORY_DOTNET_SDK_OVERRIDE=%s replaces the pinned SDK %s; this run does not prove the pinned toolchain\n' "$SDK" "$PIN" >&2
fi

step "the .NET SDK $SDK is installed"
command -v dotnet >/dev/null || fail "no dotnet on PATH; install the .NET SDK $SDK (the version tools/factory/generate.py pins)"
dotnet --list-sdks | awk '{print $1}' | grep -qxF "$SDK" \
  || fail "the .NET SDK $SDK is not installed (found: $(dotnet --list-sdks | awk '{print $1}' | paste -sd, -)); a produced engine cannot be built, and this check does not skip"
echo "ok   SDK $SDK"

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
ENGINE="$SCRATCH/engine"

step "pack $MAP_DIR"
python3 tools/pack-map.py "$MAP_DIR" --out "$SCRATCH/package" | tail -1
shopt -s nullglob
packages=("$SCRATCH"/package/*.nupkg)
shopt -u nullglob
[ "${#packages[@]}" -eq 1 ] || fail "expected exactly one .nupkg from pack-map.py, found ${#packages[@]}"
PACKAGE="${packages[0]}"

# No --allow-dirty: the engine's provenance must name a commit that actually produced it.
step "produce $NAME from scratch"
python3 tools/factory produce --package "$PACKAGE" --corpus "$CORPUS" --name "$NAME" --out "$ENGINE"

grep -qF "\"version\": \"$PIN\"" "$ENGINE/global.json" \
  || fail "the produced global.json does not pin $PIN: $(cat "$ENGINE/global.json")"
if [ "$SDK" != "$PIN" ]; then
  python3 - "$ENGINE/global.json" "$SDK" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    document = json.load(handle)
document["sdk"]["version"] = sys.argv[2]
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(json.dumps(document, indent=2) + "\n")
PY
fi

# The build must restore the very .nupkg intake read and provenance hashed, not whatever
# nuget.org serves under the same id and version: otherwise this job proves a different package
# from the one the engine was produced from. So, in this scratch copy only, a fresh global
# packages folder (nothing cached from an earlier restore can stand in) and a local feed holding
# the packed map, with source mapping that resolves RulesFactory.Maps.* from that feed alone.
# Everything else (RulesKernel, the test packages) still comes from nuget.org. NuGet.config is
# write-once scaffold, not generated, so provenance does not see this edit.
export NUGET_PACKAGES="$SCRATCH/nuget-packages"
python3 - "$ENGINE/NuGet.config" "$SCRATCH/package" <<'PY'
import sys
import xml.etree.ElementTree as ET
path, feed = sys.argv[1], sys.argv[2]
tree = ET.parse(path)
root = tree.getroot()
sources, mapping = root.find("packageSources"), root.find("packageSourceMapping")
if sources is None or mapping is None:
    print(f"{path} has no packageSources or packageSourceMapping to extend", file=sys.stderr); sys.exit(1)
ET.SubElement(sources, "add", key="local-map", value=feed)
local = ET.SubElement(mapping, "packageSource", key="local-map")
ET.SubElement(local, "package", pattern="RulesFactory.Maps.*")
tree.write(path, encoding="utf-8", xml_declaration=True)
PY

cd "$ENGINE"
SOLUTION="$NAME.slnx"
[ "$(dotnet --version)" = "$SDK" ] || fail "global.json selected SDK $(dotnet --version), not $SDK"

# The factory writes no packages.lock.json: the first restore of a fresh engine creates them.
# CI=true would switch on RestoreLockedMode, which cannot create them, so that first restore
# runs with locked mode forced off. The second restore is locked: it proves the lock files the
# first one wrote are complete and consistent with the projects. It does not prove the pinned
# hashes were reviewed; for a fresh engine there is nothing earlier to compare them with.
step "restore (writes packages.lock.json)"
dotnet restore "$SOLUTION" -p:RestoreLockedMode=false
locks=$(find . -name packages.lock.json -not -path '*/obj/*' | wc -l)
[ "$locks" -ge 2 ] || fail "restore wrote $locks packages.lock.json file(s); expected one per project (2)"
echo "ok   $locks lock file(s)"

step "restore --locked-mode"
dotnet restore "$SOLUTION" --locked-mode

step "the restored map package is the packed .nupkg"
python3 - "$PACKAGE" "$NUGET_PACKAGES" <<'PY'
import base64, hashlib, json, pathlib, sys, zipfile
package, cache = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
expected = base64.b64encode(hashlib.sha512(package.read_bytes()).digest()).decode("ascii")
with zipfile.ZipFile(package) as archive:
    (nuspec,) = [n for n in archive.namelist() if n.endswith(".nuspec") and "/" not in n]
    text = archive.read(nuspec).decode("utf-8")
import re
pid = re.search(r"<id>([^<]+)</id>", text).group(1)
version = re.search(r"<version>([^<]+)</version>", text).group(1)
bad = False
marker = cache / pid.lower() / version.lower() / f"{pid.lower()}.{version.lower()}.nupkg.sha512"
if not marker.is_file():
    print(f"  X  {marker} does not exist: the map was not restored into the scratch packages folder"); bad = True
elif marker.read_text(encoding="utf-8").strip() != expected:
    print(f"  X  restored {pid} {version} has sha512 {marker.read_text().strip()}, the packed .nupkg {expected}"); bad = True
locks = sorted(pathlib.Path(".").rglob("packages.lock.json"))
seen = 0
for lock in locks:
    for framework, deps in json.loads(lock.read_text(encoding="utf-8"))["dependencies"].items():
        for name, dep in deps.items():
            if name.lower() == pid.lower():
                seen += 1
                if dep.get("contentHash") != expected:
                    print(f"  X  {lock} [{framework}] pins {name} to {dep.get('contentHash')}, not the packed .nupkg"); bad = True
if seen == 0:
    print(f"  X  no lock file names {pid} -- nothing was compared"); bad = True
if bad:
    sys.exit(1)
print(f"ok   {pid} {version}: restored sha512 and {seen} lock-file contentHash(es) equal the packed .nupkg")
PY

step "build, warnings as errors"
dotnet build "$SOLUTION" --no-restore -c Release -warnaserror

step "test"
dotnet test "$SOLUTION" --no-build -c Release --logger "trx;LogFilePrefix=results" --results-directory "$SCRATCH/results"
# A green dotnet test over zero tests is the same lie as a check with no inputs.
python3 - "$SCRATCH/results" <<'PY'
import pathlib, re, sys
counters = [pathlib.Path(p).read_text(encoding="utf-8") for p in pathlib.Path(sys.argv[1]).rglob("*.trx")]
if not counters:
    print("dotnet test wrote no results -- nothing was proven", file=sys.stderr); sys.exit(1)
total = passed = 0
for text in counters:
    match = re.search(r'<Counters total="(\d+)"[^>]*passed="(\d+)"', text)
    if not match:
        print("a results file has no counters", file=sys.stderr); sys.exit(1)
    total += int(match.group(1)); passed += int(match.group(2))
if total == 0 or passed != total:
    print(f"{passed} of {total} tests passed -- not a pass", file=sys.stderr); sys.exit(1)
print(f"ok   {passed} of {total} tests passed across {len(counters)} target framework run(s)")
PY

# The gate the factory ships with every engine (tools/factory/recipe/validate.sh), run the way
# the engine's own CI runs it. The steps above do not depend on that recipe being right; this
# one proves the recipe passes on a real engine rather than only in its unit tests.
step "the engine's own gate: scripts/validate.sh full"
[ -x scripts/validate.sh ] || fail "the produced engine has no executable scripts/validate.sh"
CI=true ./scripts/validate.sh full

cd "$ROOT"
step "factory provenance recomputes"
python3 tools/factory provenance --engine "$ENGINE" --package "$PACKAGE"

printf '\nvalidate-engine.sh: PASS (SDK %s%s)\n' "$SDK" "$([ "$SDK" = "$PIN" ] || echo ", OVERRIDDEN from $PIN")"
