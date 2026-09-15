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
# Then two re-produces into that existing engine (#94), each verified the same way: one after the
# engine adds a src and a test project of its own, which must stay untouched, and one with the map
# packed at the next patch version, which changes the generated pins, so verify re-locks the lock
# files before the gate and provenance records them.
#
# scripts/validate.sh proves the Python machinery. It cannot prove that what the machinery
# writes is a .NET solution that builds, because that needs the SDK the kernel pins, and the
# only test that tried (tools/tests/test_factory_provenance.py) skips without it. A green run
# that skipped the one check that mattered is a check that examined nothing, so here a missing
# or wrong SDK is a failure, never a skip.
#
# The engine is produced from the hoyle-backgammon example: a small map, a non-RPG domain, and
# a package published on nuget.org (restore resolves it, and RulesKernel, from there). Last, every
# other example map with a map-package.json is produced and verified once, gate and all (#106). And an
# engine of the synthetic licensed fixture is produced and verified with its map restored from a local
# feed, and its emitted CI checks run as a runner would, with no map anywhere (#142, decision 0028).
#
# Local runs only: FACTORY_DOTNET_SDK_OVERRIDE=<version> rewrites the scratch engine's
# global.json to that SDK, for a machine that lacks the pinned one. global.json is a managed file
# (decision 0018), so the re-produce below adopts it, like the NuGet.config edit, and provenance
# records it -- and the build then proves the engine on a toolchain the kernel does not pin. CI never
# sets it, and this script refuses it when CI=true. The variable is read, refused and re-pinned by
# the functions `factory verify` uses for the same override (tools/factory/verify.py), so the two
# cannot drift; the verifying produces below run with it unset, since CI=true refuses it and each
# engine they verify already pins $SDK in its adopted global.json.
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

# The SDK override, through tools/factory/verify.py: $1 is Python run with `verify` imported, the rest its sys.argv[1:].
override_py() {
  python3 -B -c "import sys; sys.path.insert(0, '$ROOT/tools/factory'); import verify
$1" "${@:2}"
}

PIN="$(sdk_pin)"
[ -n "$PIN" ] || fail "could not read SDK_VERSION from tools/factory/generate.py"
OVERRIDE="$(override_py '
try:
    print(verify.sdk_override() or "")
except verify.intake_step.Usage as error:
    sys.exit(str(error))')" || fail "the SDK override was refused (above)"
SDK="${OVERRIDE:-$PIN}"
[ -z "$OVERRIDE" ] || override_py 'print(verify.override_warning(sys.argv[1], sys.argv[2]))' "$SDK" "$PIN" >&2

step "the .NET SDK $SDK is installed"
command -v dotnet >/dev/null || fail "no dotnet on PATH; install the .NET SDK $SDK (the version tools/factory/generate.py pins)"
dotnet --list-sdks | awk '{print $1}' | grep -qxF "$SDK" \
  || fail "the .NET SDK $SDK is not installed (found: $(dotnet --list-sdks | awk '{print $1}' | paste -sd, -)); a produced engine cannot be built, and this check does not skip"
echo "ok   SDK $SDK"

# Local runs only (FACTORY_DOTNET_SDK_OVERRIDE): re-pin a scratch engine's global.json ($1/global.json) to $SDK.
repin_sdk() {
  [ "$SDK" != "$PIN" ] || return 0
  override_py '
path, version = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as handle:
    text = verify.repin(handle.read(), version)
with open(path, "w", encoding="utf-8") as handle:
    handle.write(text)' "$1/global.json" "$SDK"
}

# A verifying produce, as CI runs one (CI=true). FACTORY_DOTNET_SDK_OVERRIDE is unset for it: CI=true
# refuses the override, and the engine it verifies already pins $SDK in its adopted global.json.
verified_produce() {
  env -u FACTORY_DOTNET_SDK_OVERRIDE CI=true python3 tools/factory produce "$@"
}

# A scratch engine's NuGet.config ($1) gains a local folder feed ($2), the only source of RulesFactory.Maps.*.
add_local_feed() {
  python3 - "$1" "$2" <<'PY'
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
}

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
repin_sdk "$ENGINE"

# The build must restore the very .nupkg intake read and provenance hashed, not whatever
# nuget.org serves under the same id and version: otherwise this job proves a different package
# from the one the engine was produced from. So, in this scratch copy only, a fresh global
# packages folder (nothing cached from an earlier restore can stand in) and a local feed holding
# the packed map, with source mapping that resolves RulesFactory.Maps.* from that feed alone.
# Everything else (RulesKernel, the test packages) still comes from nuget.org. NuGet.config is
# a managed file (decision 0018), so the re-produce below adopts it, and provenance then records
# it as an engine-owned build input (#69).
export NUGET_PACKAGES="$SCRATCH/nuget-packages"
add_local_feed "$ENGINE/NuGet.config" "$SCRATCH/package"

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
verified_produce --package "$PACKAGE" --corpus "$CORPUS" --name "$NAME" --out "$ENGINE" \
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

# Run in the engine directory: every lock file under it must pin the package's content hash.
check_restored_package() {
python3 - "$1" "$NUGET_PACKAGES" <<'PY'
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
}

step "the restored map package is the packed .nupkg"
(cd "$ENGINE" && check_restored_package "$PACKAGE")

# The gate already ran, in the staging copy, on exactly these bytes (its locked restore proved
# the lock files complete and consistent with the projects -- not that their hashes were
# reviewed, since a fresh engine has nothing earlier to compare them with). Running it again here
# would build the solution twice more to learn nothing. What remains is that the committed record
# is true of the committed engine, every build input and lock file included.
step "factory provenance recomputes on the committed engine"
python3 tools/factory provenance --engine "$ENGINE" --package "$PACKAGE"

# #92 (decision 0019): hoyle-1909 declares `randomness: seeded`, so its engine may draw. On a scratch
# copy, reference RulesKernel.Randomness (pinned only by the generated props), throw a seeded die,
# and run the engine's own gate in lock mode, since a new reference needs new lock files: it restores
# the package, accepts it under the corpus's declaration, and builds and tests.
step "a seeded corpus's engine references RulesKernel.Randomness, and its gate passes"
SEEDED="$SCRATCH/seeded"
cp -R "$ENGINE" "$SEEDED"
rm -rf "$SEEDED"/src/*/bin "$SEEDED"/src/*/obj "$SEEDED"/tests/*/bin "$SEEDED"/tests/*/obj
python3 - "$SEEDED/src/$NAME/$NAME.csproj" <<'PY'
import sys
path, anchor = sys.argv[1], '    <PackageReference Include="RulesKernel" />\n'
text = open(path, encoding="utf-8").read()
assert anchor in text, f"{path} has no RulesKernel reference to add beside"
open(path, "w", encoding="utf-8").write(text.replace(anchor, anchor + '    <PackageReference Include="RulesKernel.Randomness" />\n', 1))
PY
printf 'using RulesKernel.Randomness;\n\nnamespace %s;\n\ninternal static class SeededDie\n{\n    internal static int Throw(ulong seed) => UniformInt.InRange(Pcg32.FromSeed(seed, 54), 1, 6);\n}\n' "$NAME" \
  > "$SEEDED/src/$NAME/SeededDie.cs"
(cd "$SEEDED" && env -u CI ./scripts/validate.sh lock) > "$SCRATCH/seeded.log" 2>&1 \
  || { tail -40 "$SCRATCH/seeded.log"; fail "the gate refused an engine of a seeded corpus that references RulesKernel.Randomness"; }
grep -qE 'randomness: seeded -- .*\([1-9][0-9]* lock-file resolution' "$SCRATCH/seeded.log" \
  || { tail -40 "$SCRATCH/seeded.log"; fail "the seeded engine's gate passed without a lock file resolving RulesKernel.Randomness"; }
echo "ok   RulesKernel.Randomness restored under randomness: seeded; the engine's gate passes"

# #76: the typed contract is only a contract if the compiler enforces it, and the Python test that
# shows so (tools/tests/test_factory_gate.py) skips without an SDK, as in this repository's
# validate job. So here, on a scratch copy of the committed engine: mark one entry implemented,
# regenerate, and build the engine project with a hand-written handler of the declared type
# (builds), none (CS8795) and one of another return type (CS8817).
step "a missing or mis-typed handler for an implemented entry is a build error"
TYPED="$SCRATCH/typed"
cp -R "$ENGINE" "$TYPED"
rm -rf "$TYPED"/src/*/bin "$TYPED"/src/*/obj "$TYPED"/tests/*/bin "$TYPED"/tests/*/obj
cat > "$TYPED/corpus-map.overlay.json" <<'JSON'
{"player-count": {"status": "implemented", "implementedIn": {"ruleset": "scratch", "version": 1},
                  "tests": [{"test": "CorrespondenceTests.player_count__is_implemented_so_a_hand_written_handler_answers_it",
                             "mutation": "scratch"}]}}
JSON
python3 tools/factory produce --package "$PACKAGE" --corpus "$CORPUS" --name "$NAME" --out "$TYPED" --no-verify >/dev/null
grep -qF 'internal static partial Resolution<object> PlayerCount(' "$TYPED/src/$NAME/Generated/Contracts.g.cs" \
  || fail "the implemented entry player-count has no required handler declaration in Contracts.g.cs"
typed_build() {
  printf 'using RulesKernel.Resolution;\n\nnamespace %s;\n\ninternal static partial class Handlers\n{\n%s\n}\n' "$NAME" "$1" \
    > "$TYPED/src/$NAME/PlayerCount.cs"
  (cd "$TYPED" && dotnet build "src/$NAME/$NAME.csproj" -f net10.0 -warnaserror -nologo 2>&1)
}
HANDLER='    internal static partial Resolution<object> PlayerCount(Requests.PlayerCountRequest request) => Resolution<object>.FromValue(2);\n'
typed_build "$(printf "$HANDLER")" > "$SCRATCH/typed.log" || { tail -30 "$SCRATCH/typed.log"; fail "the handler of the declared type does not build"; }
echo "ok   the handler of the declared type builds"
for mutation in "missing|CS8795|" "another return type|CS8817|$(printf "$HANDLER" | sed 's/Resolution<object>/Resolution<int>/g')"; do
  label="${mutation%%|*}"; rest="${mutation#*|}"; code="${rest%%|*}"; handler="${rest#*|}"
  if typed_build "$handler" > "$SCRATCH/typed.log"; then
    fail "a handler with $label built; the typed contract is not enforced"
  fi
  grep -q "error $code:" "$SCRATCH/typed.log" || { tail -30 "$SCRATCH/typed.log"; fail "a handler with $label failed to build without error $code"; }
  echo "ok   a handler with $label: error $code"
done

# #93: a typed request carries the engine's inputs to its handler. On the same scratch copy, an
# engine-side partial declares an input on PlayerCountRequest, the handler answers with it, and a
# test outside the generated code resolves through EntryPoints (the value arrives) and through the
# dictionary dispatch (a request rebuilt from assertions, so the input is at its default). The
# generated correspondence tests run beside it, so the dispatch change keeps them passing.
step "an engine-declared request input reaches its handler through EntryPoints"
cat > "$TYPED/src/$NAME/PlayerCountRequest.cs" <<CS
namespace $NAME.Requests;

public sealed partial class PlayerCountRequest
{
    /// <summary>An engine-declared input: the players at the table.</summary>
    public int Players { get; init; }
}
CS
typed_build '    internal static partial Resolution<object> PlayerCount(Requests.PlayerCountRequest request) => Resolution<object>.FromValue(request.Players);' \
  > "$SCRATCH/typed.log" || { tail -30 "$SCRATCH/typed.log"; fail "a request partial with an input property does not build"; }
cat > "$TYPED/tests/$NAME.Tests/TypedInputTests.cs" <<CS
using RulesKernel.Resolution;
using Xunit;

namespace $NAME.Tests;

public sealed class TypedInputTests
{
    [Fact]
    public void an_engine_declared_input_reaches_the_handler_through_EntryPoints()
    {
        var typed = EntryPoints.PlayerCount.Resolve(new Requests.PlayerCountRequest { Players = 4 });
        Assert.Equal(4, typed.Match<object?>(v => v, _ => null));
        var generic = Registry.Resolve(new Requests.PlayerCountRequest(RuleRequest.Empty) { Players = 3 });
        Assert.Equal(3, generic.Match<object?>(v => v, _ => null));
        var dictionary = Registry.Resolve("player-count", RuleRequest.Empty);
        Assert.Equal(0, dictionary.Match<object?>(v => v, _ => null));
    }
}
CS
(cd "$TYPED" && dotnet test "tests/$NAME.Tests/$NAME.Tests.csproj" -f net10.0 -warnaserror -nologo \
   --results-directory "$SCRATCH/typed-results" --logger "trx;LogFileName=typed.trx" --filter "FullyQualifiedName~$NAME.Tests.TypedInputTests|FullyQualifiedName~$NAME.Tests.CorrespondenceTests" 2>&1) \
  > "$SCRATCH/typed.log" || { tail -40 "$SCRATCH/typed.log"; fail "the engine-declared input did not reach its handler, or a correspondence test failed"; }
# A filter matching nothing also exits 0, so the test must be in the results, and have passed.
grep -Eq 'testName="[^"]*TypedInputTests\.an_engine_declared_input_reaches_the_handler_through_EntryPoints"[^>]*outcome="Passed"' \
  "$SCRATCH/typed-results/typed.trx" || fail "TypedInputTests did not run and pass: $(grep -E 'Passed!|Failed!' "$SCRATCH/typed.log")"
echo "ok   an input set on PlayerCountRequest arrives through EntryPoints; the dictionary dispatch still resolves"

# Decision 0027: an owner's ruling on part of an unresolved question lives in the overlay, and the factory
# generates Rulings.g.cs from it. The Python tests (tools/tests/test_factory_rulings.py) show what is
# generated and refused; only a build shows it compiles warning-free beside an engine's own partial members
# and a handler that surfaces it. On the same scratch copy: bearing-off-eligible is implemented with a
# ruling on its second part and a decline of its first, produce accepts it and says whose answer it is, and
# a test outside the generated code resolves the entry and finds the ruling on the answer.
step "an owner's ruling in the overlay generates a registry the engine surfaces"
mkdir -p "$TYPED/docs/decisions"
printf '# 0001: a scratch ruling\n\nThe owner ruled; this record holds it.\n' > "$TYPED/docs/decisions/0001-scratch-ruling.md"
cat > "$TYPED/corpus-map.overlay.json" <<'JSON'
{"player-count": {"status": "implemented", "implementedIn": {"ruleset": "scratch", "version": 1},
                  "tests": [{"test": "CorrespondenceTests.player_count__is_implemented_so_a_hand_written_handler_answers_it",
                             "mutation": "scratch"}]},
 "bearing-off-eligible": {"status": "implemented", "implementedIn": {"ruleset": "scratch", "version": 1},
                          "tests": [{"test": "RulingsTests.the_generated_ruling_is_surfaced_on_the_answer", "mutation": "scratch"},
                                    {"test": "CorrespondenceTests.bearing_off_eligible__is_implemented_so_a_hand_written_handler_answers_it",
                                     "mutation": "scratch"}],
                          "rulings": [{"id": "bearing-off-eligible/2",
                                       "span": "Nor does it say when within a throw the stage begins. If a man played with the first number of a throw is the last to come home, the text does not say whether the number left is played under this stage ('each throw entitles the player either to move forward a man or men ... or to remove men'), or as an ordinary move because the throw began before the stage was reached. On the first reading, with his last man outside on the nine point and six-trois thrown, 9/3 then bearing that man off with the trois is a legal play, and so is 9/6 then bearing him off with the six; on the second reading neither is. The quatre-trois example weighs both numbers against a distribution already home, so it does not decide the case.",
                                       "answer": "The number left after the last man comes home bears off.",
                                       "ruledBy": "the owner", "ruledOn": "2026-09-15",
                                       "record": "docs/decisions/0001-scratch-ruling.md",
                                       "tests": ["RulingsTests.the_generated_ruling_is_surfaced_on_the_answer"]}],
                          "declines": [{"span": "The stage begins 'when either player has succeeded in getting all his men into his home table', and the chapter never says whether it lasts. If one of his men is hit after he has begun to bear off and then re-enters, the text does not say whether he may go on bearing off the men still at home or must first bring every man home again.",
                                        "tests": ["CorrespondenceTests.bearing_off_eligible__is_implemented_so_a_hand_written_handler_answers_it"]}]}}
JSON
python3 tools/factory produce --package "$PACKAGE" --corpus "$CORPUS" --name "$NAME" --out "$TYPED" --no-verify > "$SCRATCH/ruling.log" \
  || { tail -20 "$SCRATCH/ruling.log"; fail "produce refused an overlay with a well-formed owner's ruling"; }
grep -qF "owner's ruling bearing-off-eligible/2 on bearing-off-eligible, not the corpus" "$SCRATCH/ruling.log" \
  || fail "produce did not say that bearing-off-eligible/2 is the owner's answer"
[ -f "$TYPED/src/$NAME/Generated/Rulings.g.cs" ] || fail "no Rulings.g.cs was generated for an overlay with a ruling"
cat > "$TYPED/src/$NAME/BearingOffEligible.cs" <<CS
using RulesKernel.Resolution;

namespace $NAME;

internal static partial class Handlers
{
    internal static partial Resolution<object> BearingOffEligible(Requests.BearingOffEligibleRequest request) =>
        Resolution<object>.FromValue(OwnerRulings.All);
}

/// <summary>An engine's own member beside the generated rulings.</summary>
public static partial class OwnerRulings
{
    /// <summary>The ruling under the engine's own name.</summary>
    public static OwnerRuling BearingOffBeginsWithinTheThrow => BearingOffEligible2;
}

/// <summary>An engine's own member on the generated record.</summary>
public sealed partial record OwnerRuling
{
    /// <summary>The slug of the id, after the entry.</summary>
    public string Part => Id[(Id.IndexOf('/', StringComparison.Ordinal) + 1)..];
}
CS
cat > "$TYPED/tests/$NAME.Tests/RulingsTests.cs" <<CS
using Xunit;

namespace $NAME.Tests;

public sealed class RulingsTests
{
    [Fact]
    public void the_generated_ruling_is_surfaced_on_the_answer()
    {
        var answer = EntryPoints.BearingOffEligible.Resolve(Requests.BearingOffEligibleRequest.Empty).Match<object?>(v => v, _ => null);
        var ruling = Assert.Single(Assert.IsAssignableFrom<IEnumerable<OwnerRuling>>(answer));
        Assert.Same(OwnerRulings.BearingOffBeginsWithinTheThrow, ruling);
        Assert.Equal(("bearing-off-eligible/2", "bearing-off-eligible", "the owner", new DateOnly(2026, 9, 15), "2"),
            (ruling.Id, ruling.EntryId, ruling.RuledBy, ruling.RuledOn, ruling.Part));
        Assert.StartsWith("Nor does it say when within a throw the stage begins.", ruling.Span, StringComparison.Ordinal);
    }
}
CS
(cd "$TYPED" && dotnet test "tests/$NAME.Tests/$NAME.Tests.csproj" -f net10.0 -warnaserror -nologo \
   --results-directory "$SCRATCH/ruling-results" --logger "trx;LogFileName=ruling.trx" --filter "FullyQualifiedName~$NAME.Tests.RulingsTests|FullyQualifiedName~$NAME.Tests.CorrespondenceTests" 2>&1) \
  > "$SCRATCH/ruling.log" || { tail -40 "$SCRATCH/ruling.log"; fail "the generated rulings did not build warning-free, or a test failed"; }
grep -Eq 'testName="[^"]*RulingsTests\.the_generated_ruling_is_surfaced_on_the_answer"[^>]*outcome="Passed"' \
  "$SCRATCH/ruling-results/ruling.trx" || fail "RulingsTests did not run and pass: $(grep -E 'Passed!|Failed!' "$SCRATCH/ruling.log")"
echo "ok   Rulings.g.cs builds with -warnaserror beside engine partials, and the answer carries the ruling"

# #94, case 1 of 2: produce into an existing engine that has projects of its own. An engine adds a
# src project and a test project to its solution and locks them itself (a plain restore writes
# their lock files and leaves the committed ones as they are). A re-produce with the same package
# must commit verified, change provenance.json only (the new projects are build inputs it now
# records), and leave every file of the engine's own projects byte-identical.
step "re-produce into an engine with its own src and test projects"
mkdir -p "$ENGINE/src/Extra" "$ENGINE/tests/Extra.Tests"
printf '<Project Sdk="Microsoft.NET.Sdk">\n</Project>\n' > "$ENGINE/src/Extra/Extra.csproj"
cat > "$ENGINE/src/Extra/Doubler.cs" <<'CS'
namespace Extra;

/// <summary>A project the engine added itself.</summary>
public static class Doubler
{
    /// <summary>Doubles a value.</summary>
    /// <param name="value">The value to double.</param>
    /// <returns>Twice <paramref name="value"/>.</returns>
    public static int Twice(int value) => value * 2;
}
CS
cat > "$ENGINE/tests/Extra.Tests/Extra.Tests.csproj" <<'XML'
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <IsPackable>false</IsPackable>
    <IsTestProject>true</IsTestProject>
    <GenerateDocumentationFile>false</GenerateDocumentationFile>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" />
    <PackageReference Include="xunit" />
    <PackageReference Include="xunit.runner.visualstudio" />
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="../../src/Extra/Extra.csproj" />
  </ItemGroup>

</Project>
XML
cat > "$ENGINE/tests/Extra.Tests/DoublerTests.cs" <<'CS'
using Xunit;

namespace Extra.Tests;

public class DoublerTests
{
    [Fact]
    public void Twice_doubles_its_argument() => Assert.Equal(4, Doubler.Twice(2));
}
CS
python3 - "$ENGINE/$NAME.slnx" <<'PY'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
extra = '  <Project Path="src/Extra/Extra.csproj" />\n  <Project Path="tests/Extra.Tests/Extra.Tests.csproj" />\n'
open(path, "w", encoding="utf-8").write(text.replace("</Solution>", extra + "</Solution>"))
PY
(cd "$ENGINE" && dotnet restore "$NAME.slnx" -p:RestoreLockedMode=false -nologo > "$SCRATCH/extra-lock.log") \
  || { tail -30 "$SCRATCH/extra-lock.log"; fail "restoring the engine's own projects failed"; }
rm -rf "$ENGINE"/src/*/obj "$ENGINE"/tests/*/obj "$ENGINE"/src/*/bin "$ENGINE"/tests/*/bin
[ -f "$ENGINE/src/Extra/packages.lock.json" ] && [ -f "$ENGINE/tests/Extra.Tests/packages.lock.json" ] \
  || fail "restore wrote no lock files for the engine's own projects"
own_files() {
  (cd "$ENGINE" && find src/Extra tests/Extra.Tests "$NAME.slnx" "src/$NAME/packages.lock.json" \
    "tests/$NAME.Tests/packages.lock.json" -type f -print0 | sort -z | xargs -0 sha256sum)
}
own_files > "$SCRATCH/own-before.txt"
verified_produce --package "$PACKAGE" --corpus "$CORPUS" --name "$NAME" --out "$ENGINE" \
  | tee "$SCRATCH/extra.log"
tail -1 "$SCRATCH/extra.log" | grep -q ', verified$' || fail "re-producing into an engine with its own projects did not end verified"
grep -qxF "committed to $(cd "$ENGINE" && pwd -P): 0 added, 1 changed, 0 removed" "$SCRATCH/extra.log" \
  || fail "re-producing into an engine with its own projects should change provenance.json only: $(grep '^committed to' "$SCRATCH/extra.log")"
grep -q "restore -- skipped" "$SCRATCH/extra.log" || fail "the pins did not change, yet verify did not skip its restore"
own_files | diff "$SCRATCH/own-before.txt" - || fail "re-producing changed the engine's own projects or lock files"
echo "ok   the engine's own projects and every lock file are byte-identical after a verified re-produce"

# #94, case 2 of 2: a map version bump into a locked engine (the engine above, own projects
# included). The same map, packed at the next patch version into the local feed, changes the pins
# in RulesFactory.Packages.g.props, so verify must re-lock before the gate's locked restore;
# provenance.json must record the re-locked files, the committed record must recompute, and the
# restored package must be the newly packed one.
step "a map version bump re-produces verified, re-locking the lock files"
BUMP_DIR="$SCRATCH/bump/$(basename "$MAP_DIR")"
mkdir -p "$(dirname "$BUMP_DIR")"
cp -R "$MAP_DIR" "$BUMP_DIR"
BUMPED="$(python3 - "$BUMP_DIR/map-package.json" <<'PY'
import json, sys
path = sys.argv[1]
document = json.load(open(path, encoding="utf-8"))
major, minor, patch = document["version"].split(".")
document["version"] = f"{major}.{minor}.{int(patch) + 1}"
open(path, "w", encoding="utf-8").write(json.dumps(document, indent=2) + "\n")
print(document["version"])
PY
)"
python3 tools/pack-map.py "$BUMP_DIR" --out "$SCRATCH/package" | tail -1
shopt -s nullglob
bumped=("$SCRATCH"/package/*."$BUMPED".nupkg)
shopt -u nullglob
[ "${#bumped[@]}" -eq 1 ] || fail "expected one .nupkg at version $BUMPED from pack-map.py, found ${#bumped[@]}"
PACKAGE_BUMPED="${bumped[0]}"
sha256sum "$ENGINE"/src/*/packages.lock.json "$ENGINE"/tests/*/packages.lock.json > "$SCRATCH/locks-before.txt"
verified_produce --package "$PACKAGE_BUMPED" --corpus "$CORPUS" --name "$NAME" --out "$ENGINE" \
  | tee "$SCRATCH/bump.log"
tail -1 "$SCRATCH/bump.log" | grep -q ', verified$' || fail "the map version bump did not commit verified"
grep -q "the generated pins changed, so this restore re-locks the 4 lock file(s)" "$SCRATCH/bump.log" \
  || fail "the map version bump did not re-lock the 4 lock files"
grep -q "^re-locked [0-9]* packages.lock.json file(s) because the generated pins changed" "$SCRATCH/bump.log" \
  || fail "produce did not report re-locked lock files"
sha256sum "$ENGINE"/src/*/packages.lock.json "$ENGINE"/tests/*/packages.lock.json | diff -q "$SCRATCH/locks-before.txt" - >/dev/null \
  && fail "the map version bump committed without changing any lock file"
(cd "$ENGINE" && python3 - "$BUMPED" <<'PY'
import hashlib, json, pathlib, sys
record = json.loads(pathlib.Path("provenance.json").read_text(encoding="utf-8"))
if record["map"]["version"] != sys.argv[1]:
    print(f"provenance.json records map {record['map']['version']}, not {sys.argv[1]}", file=sys.stderr); sys.exit(1)
recorded = {b["path"]: b["sha256"] for b in record["buildInputs"] if b["path"].endswith("packages.lock.json")}
on_disk = {str(p).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path(".").rglob("packages.lock.json")
           if not {"bin", "obj"} & set(p.parts)}
if recorded != on_disk:
    print(f"provenance.json records lock files {sorted(recorded)} that are not the re-locked ones on disk {sorted(on_disk)}", file=sys.stderr); sys.exit(1)
print(f"ok   provenance.json records map {sys.argv[1]} and the {len(recorded)} re-locked lock files")
PY
) || fail "provenance.json does not record the bump"
(cd "$ENGINE" && check_restored_package "$PACKAGE_BUMPED")
step "factory provenance recomputes on the bumped engine"
python3 tools/factory provenance --engine "$ENGINE" --package "$PACKAGE_BUMPED"

# #106: everything above is one map's engine, and a corpus admitted with something only its own
# engine exercises (the SRD's hashDerivation, which the gate could not recompute) passed every check
# here while no SRD engine could pass its gate. So every other example map that declares a package is
# produced from scratch too, and its engine verified the way a default `produce` verifies one: restore
# from the packed .nupkg, then the whole gate, posture (the baseline recomputed under the corpus's own
# derivation) through build and tests. Only the scratch feed and SDK edits are shared with the engine
# above; none of the mutations are repeated.
step "every other packable example map produces an engine whose gate passes"
examples=0
for settings in examples/*/map-package.json; do
  dir="$(dirname "$settings")"
  examples=$((examples + 1))
  if [ "$dir" = "$MAP_DIR" ]; then
    echo "     $dir: produced and verified above"
    continue
  fi
  slug="$(basename "$dir")"
  feed="$SCRATCH/feeds/$slug"
  python3 tools/pack-map.py "$dir" --out "$feed" | tail -1
  shopt -s nullglob
  example_packages=("$feed"/*.nupkg)
  shopt -u nullglob
  [ "${#example_packages[@]}" -eq 1 ] || fail "expected exactly one .nupkg from pack-map.py $dir, found ${#example_packages[@]}"
  example_package="${example_packages[0]}"
  # The engine name is the package id's last segment; the corpus is the committed copy the manifest names.
  described="$(python3 - "$example_package" "$dir" <<'PY'
import json, os, re, sys, zipfile
package, directory = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(package) as archive:
    (nuspec,) = [n for n in archive.namelist() if n.endswith(".nuspec") and "/" not in n]
    package_id = re.search(r"<id>([^<]+)</id>", archive.read(nuspec).decode("utf-8")).group(1)
    cited = json.loads(archive.read("map/corpus-map.json"))["corpus"]
    corpora = [c for c in json.loads(archive.read("map/corpus-manifest.json"))["corpora"] if c.get("sourceId") == cited]
if len(corpora) != 1 or corpora[0].get("verification") != "committed-copy":
    sys.exit(f"{directory}: {cited} is not one committed-copy corpus, so CI cannot produce its engine")
print(package_id.rsplit(".", 1)[-1], os.path.join(directory, os.path.basename(corpora[0]["committedPath"])), cited)
PY
)" || fail "cannot read what $example_package produces"
  read -r example_name example_corpus example_source <<<"$described"
  example_engine="$SCRATCH/examples/$slug"
  python3 tools/factory produce --package "$example_package" --corpus "$example_corpus" --name "$example_name" \
    --out "$example_engine" --no-verify > "$SCRATCH/example-$slug.log" 2>&1 \
    || { tail -40 "$SCRATCH/example-$slug.log"; fail "producing $example_name from $dir failed"; }
  repin_sdk "$example_engine"
  add_local_feed "$example_engine/NuGet.config" "$feed"
  example_adopt=(--adopt NuGet.config)
  [ "$SDK" = "$PIN" ] || example_adopt+=(--adopt global.json)
  verified_produce --package "$example_package" --corpus "$example_corpus" --name "$example_name" \
    --out "$example_engine" "${example_adopt[@]}" > "$SCRATCH/example-$slug.log" 2>&1 \
    || { tail -60 "$SCRATCH/example-$slug.log"; fail "$example_name, produced from $dir, did not pass verify (its gate's output is above)"; }
  tail -1 "$SCRATCH/example-$slug.log" | grep -q ', verified$' \
    || { tail -40 "$SCRATCH/example-$slug.log"; fail "producing $example_name did not end verified"; }
  grep -qF "verified: $example_source (committed-copy" "$SCRATCH/example-$slug.log" \
    || { tail -60 "$SCRATCH/example-$slug.log"; fail "$example_name's gate did not recompute the $example_source baseline"; }
  (cd "$example_engine" && check_restored_package "$example_package")
  echo "ok   $example_name ($dir): verified, its gate recomputed the $example_source baseline"
done
[ "$examples" -ge 2 ] || fail "found $examples packable example map(s); this step proved nothing beyond the engine above"

# #142, decision 0028: a map of a licensed local-copy corpus is never published, so its engine's map
# package reaches restore only from the operator's own feed ($RULES_FACTORY_LOCAL_MAP_FEED), through
# the NuGet global packages folder, with the managed NuGet.config left as it is. And its CI cannot
# restore the map at all, so it gets a workflow that runs what needs no licensed input and says NOT
# VERIFIED. Proven here with the real dotnet on the synthetic licensed fixture (tools/tests/
# licensed_fixture.py: invented text, no licensed text anywhere), under the one raw-bytes derivation the
# vendored gate already knows, since the gate's own process cannot have a test derivation patched in.
#
# The licensed-copy exception refuses CI and needs an allowlisted `gh` login, so these commands run with
# CI and GITHUB_ACTIONS unset and the fixture's fake `gh`, exactly as tools/tests/test_licensed_copy.py
# runs them. That is a test of the machinery on invented text, not a use of the exception.
step "a licensed-copy engine restores its map from the operator's feed, verifies, and its CI says NOT VERIFIED"
LICENSED="$SCRATCH/licensed"
mkdir -p "$LICENSED/feed" "$LICENSED/gh"
read -r LICENSED_MAP LICENSED_CORPUS <<<"$(python3 tools/tests/licensed_fixture.py "$LICENSED/fixture" gutenberg-plain-text-including-boilerplate)"
LICENSED_GH="$(python3 -c 'import sys; sys.path.insert(0, "tools/tests"); import licensed_fixture as f; print(f.fake_gh(sys.argv[1]))' "$LICENSED/gh")"
LICENSED_ENGINE="$LICENSED/engine"
LICENSED_PACKAGES="$LICENSED/nuget-packages"
licensed() {
  env -u CI -u GITHUB_ACTIONS FACTORY_GH="$LICENSED_GH" FAKE_GH_LOG="$LICENSED/gh/log" FAKE_GH_LOGIN=brandonifco \
    RULES_FACTORY_TEST_SYNTHETIC_LICENSED="$LICENSED_CORPUS" RULES_FACTORY_LOCAL_MAP_FEED="$LICENSED/feed" \
    NUGET_PACKAGES="$LICENSED_PACKAGES" "$@"
}
licensed python3 tools/pack-map.py "$LICENSED_MAP" --out "$LICENSED/feed" --licensed-copy-exception | tail -1
LICENSED_PACKAGE="$LICENSED/feed/RulesFactory.Maps.SyntheticLicensed.1.0.0.nupkg"
[ -f "$LICENSED_PACKAGE" ] || fail "pack-map.py --licensed-copy-exception wrote no $LICENSED_PACKAGE"

# Id@Version, not the path: produce finds the package in the feed, since nuget.org never has it.
licensed python3 tools/factory produce --package RulesFactory.Maps.SyntheticLicensed@1.0.0 --corpus "$LICENSED_CORPUS" \
  --name SyntheticLicensed --out "$LICENSED_ENGINE" --licensed-copy-exception > "$LICENSED/produce.log" 2>&1 \
  || { tail -60 "$LICENSED/produce.log"; fail "producing the licensed-copy engine from the operator's feed failed"; }
grep -qF -- "--- local map: put RulesFactory.Maps.SyntheticLicensed 1.0.0 from $LICENSED_PACKAGE in the NuGet global packages folder" "$LICENSED/produce.log" \
  || { tail -60 "$LICENSED/produce.log"; fail "produce did not put the map from the feed into the global packages folder"; }
grep -qF "verified: synthetic-licensed-rules (local-copy, never-commit): local copy at \$RULES_FACTORY_TEST_SYNTHETIC_LICENSED hashes to the pinned baseline" "$LICENSED/produce.log" \
  || { tail -60 "$LICENSED/produce.log"; fail "the licensed-copy engine's gate did not verify the local copy"; }
grep -q "^produced SyntheticLicensed in .*, verified locally under the licensed-copy exception by brandonifco" "$LICENSED/produce.log" \
  || { tail -40 "$LICENSED/produce.log"; fail "producing the licensed-copy engine did not end verified under the exception"; }
(cd "$LICENSED_ENGINE" && NUGET_PACKAGES="$LICENSED_PACKAGES" check_restored_package "$LICENSED_PACKAGE")
[ ! -e "$LICENSED_ENGINE/corpus" ] || fail "the licensed-copy engine has a corpus/ directory"
python3 -B - "$LICENSED_ENGINE/NuGet.config" <<'PY' || fail "the licensed-copy engine's NuGet.config is not the managed recipe"
import sys
sys.path.insert(0, "tools/factory")
import generate
sys.exit(open(sys.argv[1], encoding="utf-8").read() != generate.managed_files()["NuGet.config"])
PY
cmp -s "$LICENSED_ENGINE/.github/workflows/validate.yml" tools/factory/recipe/validate-local-copy.yml \
  || fail "the licensed-copy engine's CI workflow is not recipe/validate-local-copy.yml"
echo "ok   restored from the feed, verified under the exception; managed NuGet.config, no corpus, the NOT VERIFIED workflow"

# The global packages folder cleared: verify, given no --package, finds the map in the feed again.
rm -rf "$LICENSED_PACKAGES"
licensed python3 tools/factory verify --engine "$LICENSED_ENGINE" --licensed-copy-exception > "$LICENSED/verify.log" 2>&1 \
  || { tail -60 "$LICENSED/verify.log"; fail "verify of the licensed-copy engine, with the packages folder cleared, failed"; }
grep -q "^verify .*: PASS, verified locally under the licensed-copy exception by brandonifco" "$LICENSED/verify.log" \
  || { tail -40 "$LICENSED/verify.log"; fail "verify did not pass under the exception"; }
echo "ok   with the packages folder cleared, verify reads the feed, restores the map again and passes"

# The engine's CI, as a runner has it: CI=true, no feed, no local copy, an empty packages folder. The full
# gate fails at its locked restore (why the workflow does not run it), and every step of the emitted
# `checks` job, read from the workflow and run, passes and says NOT VERIFIED.
LICENSED_CI="$LICENSED/ci"
cp -R "$LICENSED_ENGINE" "$LICENSED_CI"
rm -rf "$LICENSED_CI"/src/*/bin "$LICENSED_CI"/src/*/obj "$LICENSED_CI"/tests/*/bin "$LICENSED_CI"/tests/*/obj
repin_sdk "$LICENSED_CI"
git -C "$LICENSED_CI" init -q && git -C "$LICENSED_CI" add -A
ci_env=(env -u RULES_FACTORY_LOCAL_MAP_FEED -u RULES_FACTORY_TEST_SYNTHETIC_LICENSED CI=true
        NUGET_PACKAGES="$LICENSED/ci-packages" GITHUB_OUTPUT="$LICENSED/ci-output" GITHUB_STEP_SUMMARY="$LICENSED/ci-summary")
if (cd "$LICENSED_CI" && "${ci_env[@]}" ./scripts/validate.sh full) > "$LICENSED/ci-full.log" 2>&1; then
  fail "the full gate passed on a runner with no map package; it cannot have restored the map"
fi
grep -q "FAIL dotnet restore --locked-mode" "$LICENSED/ci-full.log" \
  || { tail -40 "$LICENSED/ci-full.log"; fail "without the map, the full gate did not fail at its locked restore"; }
python3 tools/tests/workflow_steps.py "$LICENSED_CI/.github/workflows/validate.yml" checks "$LICENSED/ci-steps" \
  "steps.sdk.outputs.version=$SDK" || fail "cannot read the checks job of the licensed-copy workflow"
for script in "$LICENSED"/ci-steps/*.sh; do
  name="$(cat "${script%.sh}.name")"
  (cd "$LICENSED_CI" && "${ci_env[@]}" bash --noprofile --norc -eo pipefail "$script") > "$LICENSED/ci-step.log" 2>&1 \
    || { tail -40 "$LICENSED/ci-step.log"; fail "the licensed-copy CI step '$name' failed with no licensed input"; }
  echo "ok   CI step: $name"
done
grep -qF "NOT VERIFIED: licensed map not available in CI" "$LICENSED/ci-summary" \
  || fail "the licensed-copy CI did not write NOT VERIFIED to the run summary"
[ ! -e "$LICENSED/ci-packages/rulesfactory.maps.syntheticlicensed" ] || fail "the CI steps restored the map from somewhere"
echo "ok   without the map, the full gate fails at restore, and every CI check passes and says NOT VERIFIED"

printf '\nvalidate-engine.sh: PASS (SDK %s%s)\n' "$SDK" "$([ "$SDK" = "$PIN" ] || echo ", OVERRIDDEN from $PIN")"
