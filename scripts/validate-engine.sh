#!/usr/bin/env bash
# The factory's output, held to the same standard as the factory: produce an engine from
# scratch, then prove it restores, builds warning-free, passes its generated tests, and
# recomputes to the provenance it records.
#
# What makes an engine acceptable is defined once, by `factory verify` (tools/factory/verify.py),
# and this script does not restate it. It runs verify once, the way a default `produce` does: on
# produce's staging copy, before the commit -- provenance; restore, which writes the lock files,
# recorded in provenance.json before anything builds; then the engine's own gate
# (scripts/validate.sh full: SDK pin, locked restore, merge, posture, regeneration, format, build
# -warnaserror and tests in Debug and Release). The solution is built once per configuration.
# What stays here is what only a CI run of the factory needs: the pinned SDK, a scratch local
# feed so restore takes the very .nupkg that was packed, the sha512 check that it did, and a
# final recompute of the committed record.
#
# scripts/validate.sh proves the Python machinery. It cannot prove that what the machinery
# writes is a .NET solution that builds, because that needs the SDK the kernel pins, and the
# only test that tried (tools/tests/test_factory_provenance.py) skips without it. A green run
# that skipped the one check that mattered is a check that examined nothing, so here a missing
# or wrong SDK is a failure, never a skip.
#
# The engine is produced from the hoyle-backgammon example: a small map, a non-RPG domain, and
# a package published on nuget.org (restore resolves it, and RulesKernel, from there).
#
# Local runs only: FACTORY_DOTNET_SDK_OVERRIDE=<version> rewrites the scratch engine's
# global.json to that SDK, for a machine that lacks the pinned one. global.json is a managed file
# (decision 0018), so the re-produce below adopts it, like the NuGet.config edit, and provenance
# records it -- and the build then proves the engine on a toolchain the kernel does not pin. CI never
# sets it, and this script refuses it when CI=true.
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
sys.path.insert(0, sys.argv[1])  # generate.py imports ownership.py beside it
spec =importlib.util.spec_from_file_location("factory_generate_pin", os.path.join(sys.argv[1], "generate.py"))
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
# --no-verify only because global.json and NuGet.config must be edited before anything restores;
# the re-produce below verifies.
step "produce $NAME from scratch (unverified)"
python3 tools/factory produce --package "$PACKAGE" --corpus "$CORPUS" --name "$NAME" --out "$ENGINE" --no-verify

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
# a managed file (decision 0018), so the re-produce below adopts it, and provenance then records
# it as an engine-owned build input (#69).
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

[ "$(cd "$ENGINE" && dotnet --version)" = "$SDK" ] || fail "global.json selected SDK $(cd "$ENGINE" && dotnet --version), not $SDK"

# The engine now differs from what produce recorded in build inputs only: NuGet.config (the local
# feed) and global.json (under the override). Re-running produce is how a record comes to cover
# such edits (#69), and this time produce verifies, as it does by default: in its staging copy,
# provenance matches, restore writes the lock files (locked mode forced off: there are none yet),
# provenance.json is rewritten to record them before anything builds, and the engine's gate runs
# as the engine's own CI runs it, with CI=true. Only then is the result committed, and it must be
# exactly the two lock files added and provenance.json changed.
step "re-produce, verifying: records the edited scaffold and lock files, then runs the engine's gate"
# NuGet.config and global.json are managed files (tools/factory/ownership.py, decision 0018): a
# re-produce refuses a hand edit to them. The edits above are deliberate, so the re-produce adopts
# exactly the files this script edited, as an engine with a private feed would; provenance records
# them as engine-owned, and every later recompute's re-produce reads that adoption back.
ADOPT=(--adopt NuGet.config)
[ "$SDK" = "$PIN" ] || ADOPT+=(--adopt global.json)
CI=true python3 tools/factory produce --package "$PACKAGE" --corpus "$CORPUS" --name "$NAME" --out "$ENGINE" \
  "${ADOPT[@]}" | tee "$SCRATCH/reproduce.log"
grep -qxF "committed to $(cd "$ENGINE" && pwd -P): 2 added, 1 changed, 0 removed" "$SCRATCH/reproduce.log" \
  || fail "re-producing should add the 2 lock files and change provenance.json only: $(grep '^committed to' "$SCRATCH/reproduce.log")"
tail -1 "$SCRATCH/reproduce.log" | grep -q ', verified$' || fail "produce did not end verified"
python3 - "$ENGINE/provenance.json" <<'PY'
import json, sys
inputs = [b["path"] for b in json.load(open(sys.argv[1], encoding="utf-8"))["buildInputs"]]
locks = [p for p in inputs if p.endswith("packages.lock.json")]
if len(locks) < 2:
    print(f"provenance.json records {len(locks)} lock file(s) after restore; expected one per project", file=sys.stderr); sys.exit(1)
print(f"ok   {len(inputs)} build input(s) recorded, {len(locks)} of them lock files")
PY

cd "$ENGINE"
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

cd "$ROOT"
# The gate already ran, in the staging copy, on exactly these bytes (its locked restore proved
# the lock files complete and consistent with the projects -- not that their hashes were
# reviewed, since a fresh engine has nothing earlier to compare them with). Running it again here
# would build the solution twice more to learn nothing. What remains is that the committed record
# is true of the committed engine, every build input and lock file included.
step "factory provenance recomputes on the committed engine"
python3 tools/factory provenance --engine "$ENGINE" --package "$PACKAGE"

printf '\nvalidate-engine.sh: PASS (SDK %s%s)\n' "$SDK" "$([ "$SDK" = "$PIN" ] || echo ", OVERRIDDEN from $PIN")"
