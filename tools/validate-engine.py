#!/usr/bin/env python3
"""The factory's output, held to the same standard as the factory: produce an engine from
scratch, then prove it restores, builds warning-free, passes its generated tests, and
recomputes to the provenance it records.

What makes an engine acceptable is defined once, by `factory verify` (tools/factory/verify.py),
and this script does not restate it. It runs verify once, the way a default `produce` does: on
produce's staging copy, before the commit -- provenance; restore, which writes the lock files,
recorded in provenance.json before anything builds; then the engine's own gate
(scripts/validate.sh full: SDK pin, locked restore, merge, posture, regeneration, format, build
-warnaserror and tests in Debug and Release). The solution is built once per configuration.
What stays here is what only a CI run of the factory needs: the pinned SDK, a scratch local
feed so restore takes the very .nupkg that was packed, the sha512 check that it did, and a
final recompute of the committed record.

Then two re-produces into that existing engine (#94), each verified the same way: one after the
engine adds a src and a test project of its own, which must stay untouched, and one with the map
packed at the next patch version, which changes the generated pins, so verify re-locks the lock
files before the gate and provenance records them.

scripts/validate.sh proves the Python machinery. It cannot prove that what the machinery
writes is a .NET solution that builds, because that needs the SDK the kernel pins, and the
only test that tried (tools/tests/test_factory_provenance.py) skips without it. A green run
that skipped the one check that mattered is a check that examined nothing, so here a missing
or wrong SDK is a failure, never a skip.

The engine is produced from the hoyle-backgammon example: a small map, a non-RPG domain, and
a package published on nuget.org (restore resolves it, and RulesKernel, from there). Last, every
other example map with a map-package.json is produced and verified once, gate and all (#106).

Local runs only: FACTORY_DOTNET_SDK_OVERRIDE=<version> rewrites the scratch engine's
global.json to that SDK, for a machine that lacks the pinned one. global.json is a managed file
(decision 0018), so the re-produce below adopts it, like the NuGet.config edit, and provenance
records it -- and the build then proves the engine on a toolchain the kernel does not pin. CI never
sets it, and this script refuses it when CI=true. The variable is read, refused and re-pinned by
the functions `factory verify` uses for the same override (tools/factory/verify.py), so the two
cannot drift; the verifying produces below run with it unset, since CI=true refuses it and each
engine they verify already pins $SDK in its adopted global.json.

Why Python and not the shell it was (#172): this was 45 KB of bash, an application in a language
with weak structure, error handling and testability. scripts/validate-engine.sh stays the entry
point CI and people call, with the same arguments and environment, and execs this. The move is a
refactor only: the same checks, in the same order, failing on the same conditions with the same
messages, printing the same `ok` lines and exiting with the same codes. So each check is one
function below, and where the shell let a command's own exit code end the run (`set -e`), `Stop`
carries that code out unchanged. The parts that need no dotnet are tested in
tools/tests/test_validate_engine.py.

Usage: validate-engine.sh [--print-sdk]
Exit 0 when every check passes; 1 when one fails; 2 on a usage error; otherwise the exit code of
the factory command that stopped the run. Standard library only.
"""
import base64
import glob
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True  # the shell imported verify with `python3 -B`

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FACTORY = os.path.join(ROOT, "tools", "factory")
NAME = "HoyleBackgammon"
MAP_DIR = "examples/hoyle-backgammon"
CORPUS = f"{MAP_DIR}/hoyle.txt"
PYTHON = "python3"
# `produce --no-verify` exits 3, NOT VERIFIED (tools/factory/__main__.py).
NOT_VERIFIED = 3
# The name usage names: the entry point that exec'd this, as `$0` named it.
ARGV0 = "VALIDATE_ENGINE_ARGV0"


class Stop(Exception):
    """End the run with `code`. What the shell's `set -e` did with a failing command's exit code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def fail(message):
    """validate-engine.sh's one failure line, on stderr, and exit 1."""
    print(f"validate-engine.sh: FAIL -- {message}", file=sys.stderr, flush=True)
    raise Stop(1)


def step(message):
    print(f"\n==> {message}", flush=True)


def ok(message):
    print(f"ok   {message}", flush=True)


def check(code):
    """A command run without `|| fail`: under `set -e`, its failure ended the run with its code."""
    if code != 0:
        raise Stop(code)


def run(command, cwd=None, env=None, stdout=None, stderr=None, stdin=None):
    """Run a command with this process's streams (or those given); its exit code."""
    sys.stdout.flush()
    sys.stderr.flush()
    return subprocess.run(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr, input=stdin).returncode


def run_to(path, command, cwd=None, env=None, both=False, stdin=None):
    """`command > path` (with `2>&1` when `both`); its exit code."""
    with open(path, "wb") as log:
        return run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT if both else None, stdin=stdin)


def run_tee(path, command, env=None):
    """`command | tee path`, under pipefail: its exit code."""
    sys.stdout.flush()
    sys.stderr.flush()
    with open(path, "wb") as log, subprocess.Popen(command, env=env, stdout=subprocess.PIPE) as process:
        for line in process.stdout:
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
            log.write(line)
    return process.returncode


def run_tail_1(command, cwd=None):
    """`command | tail -1`, under pipefail: its exit code."""
    sys.stdout.flush()
    sys.stderr.flush()
    result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE)
    lines = _lines(result.stdout)
    if lines:
        sys.stdout.buffer.write(lines[-1] + b"\n")
        sys.stdout.buffer.flush()
    return result.returncode


def _lines(data):
    """Lines as `tail` and `grep` count them: split on newline, a final unterminated line included."""
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    return lines


def tail(path, count):
    """`tail -<count> path`: each line with its newline, the last without one if the file ends without one."""
    with open(path, "rb") as handle:
        data = handle.read()
    lines = _lines(data)[-count:]
    chunk = b"".join(line + b"\n" for line in lines)
    if lines and not data.endswith(b"\n"):
        chunk = chunk[:-1]
    sys.stdout.flush()
    sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()


def cat(path):
    tail(path, sys.maxsize)


def read_lines(path):
    """A file's lines as grep reads them; None, with grep's complaint, when it cannot be read."""
    try:
        with open(path, "rb") as handle:
            return [line.decode("utf-8", errors="replace") for line in _lines(handle.read())]
    except OSError as error:
        print(f"grep: {path}: {error.strerror}", file=sys.stderr, flush=True)
        return None


def grep(path, pattern):
    """`grep -q` (a Python regular expression, translated from the shell's): any line matches."""
    lines = read_lines(path)
    return lines is not None and any(re.search(pattern, line) for line in lines)


def grep_fixed(path, text):
    """`grep -qF`: a line contains any one of text's lines."""
    lines = read_lines(path)
    return lines is not None and any(needle in line for needle in text.split("\n") for line in lines)


def grep_exact(path, text):
    """`grep -qxF`: a line is exactly text."""
    lines = read_lines(path)
    return lines is not None and text in lines


def matching(path, pattern):
    """`$(grep pattern path)`: the matching lines, for a failure message."""
    return "\n".join(line for line in read_lines(path) or [] if re.search(pattern, line))


def last_line_verified(path):
    """`tail -1 path | grep -q ', verified$'`."""
    lines = read_lines(path)
    return bool(lines) and lines[-1].endswith(", verified")


def write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def remove_build_output(engine):
    """`rm -rf engine/src/*/bin engine/src/*/obj engine/tests/*/bin engine/tests/*/obj`."""
    for pattern in ("src/*/bin", "src/*/obj", "tests/*/bin", "tests/*/obj"):
        for path in glob.glob(os.path.join(engine, pattern)):
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)


def copy_engine(source, destination):
    """`cp -R source destination`, then its build output removed."""
    shutil.copytree(source, destination, symlinks=True)
    remove_build_output(destination)


def one_package(pattern):
    """The .nupkg files a glob names (nullglob)."""
    return sorted(glob.glob(pattern))


# The one source of truth for the SDK: the pin generate.py writes into every global.json.
def sdk_pin():
    sys.path.insert(0, FACTORY)  # generate.py imports ownership.py beside it
    spec = importlib.util.spec_from_file_location("factory_generate_pin", os.path.join(FACTORY, "generate.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(module.SDK_VERSION)


# The SDK override, through tools/factory/verify.py.
def verify_module():
    if FACTORY not in sys.path:
        sys.path.insert(0, FACTORY)
    import verify  # noqa: E402 -- tools/factory is not a package on the default path
    return verify


def sdk_override():
    """The override version, "" when unset; a refusal (printed above the failure) when CI=true."""
    try:
        verify = verify_module()
        return verify.sdk_override() or ""
    except Exception as error:  # the shell's `python3 -c` failed the same way whatever stopped it
        if type(error).__name__ == "Usage":
            print(str(error), file=sys.stderr, flush=True)
        else:
            traceback.print_exc()
        fail("the SDK override was refused (above)")


class Run:
    """One run's state: what the shell held in $PIN, $SDK, $SCRATCH, $ENGINE and $PACKAGE."""

    def __init__(self, pin, sdk, scratch):
        self.pin = pin
        self.sdk = sdk
        self.scratch = scratch
        self.engine = os.path.join(scratch, "engine")
        self.package = None

    def s(self, *parts):
        return os.path.join(self.scratch, *parts)

    # Local runs only (FACTORY_DOTNET_SDK_OVERRIDE): re-pin a scratch engine's global.json to $SDK.
    def repin_sdk(self, engine):
        if self.sdk == self.pin:
            return
        path = os.path.join(engine, "global.json")
        with open(path, encoding="utf-8") as handle:
            text = verify_module().repin(handle.read(), self.sdk)
        write(path, text)

    def adopt(self):
        """NuGet.config always; global.json too when the override rewrote it."""
        adopt = ["--adopt", "NuGet.config"]
        if self.sdk != self.pin:
            adopt += ["--adopt", "global.json"]
        return adopt


# A verifying produce, as CI runs one (CI=true). FACTORY_DOTNET_SDK_OVERRIDE is unset for it: CI=true
# refuses the override, and the engine it verifies already pins $SDK in its adopted global.json.
def verified_produce_env():
    env = dict(os.environ)
    env.pop("FACTORY_DOTNET_SDK_OVERRIDE", None)
    env["CI"] = "true"
    return env


def verified_produce_command(args):
    return [PYTHON, "tools/factory", "produce", *args]


# A `--no-verify` produce, whose engine is deliberately not built or tested here. That run exits 3,
# NOT VERIFIED, never 0 (tools/factory/__main__.py), so this wrapper accepts exactly 3 and passes
# every other code through: 0 would mean produce verified after all, and 1 is still a refusal.
# Callers keep their own failure handling, and their redirections apply to this function: its
# complaint about a 0 goes where the caller sends stderr.
def unverified_produce(args, stdout=None, stderr=None):
    status = run([PYTHON, "tools/factory", "produce", *args, "--no-verify"], stdout=stdout, stderr=stderr)
    if status == NOT_VERIFIED:
        return 0
    if status == 0:
        message = b"produce --no-verify exited 0; an engine that was not built or tested must exit 3\n"
        if stderr is subprocess.STDOUT:
            stdout.write(message)
            stdout.flush()
        elif stderr is not None:
            stderr.write(message)
            stderr.flush()
        else:
            sys.stderr.flush()
            sys.stderr.buffer.write(message)
            sys.stderr.buffer.flush()
        return 1
    return status


def unverified_produce_to(path, args, both=False):
    """`unverified_produce args > path` (with `2>&1` when `both`)."""
    with open(path, "wb") as log:
        return unverified_produce(args, stdout=log, stderr=subprocess.STDOUT if both else None)


# A scratch engine's NuGet.config gains a local folder feed, the only source of RulesFactory.Maps.*.
def add_local_feed(path, feed):
    tree = ET.parse(path)
    root = tree.getroot()
    sources, mapping = root.find("packageSources"), root.find("packageSourceMapping")
    if sources is None or mapping is None:
        print(f"{path} has no packageSources or packageSourceMapping to extend", file=sys.stderr, flush=True)
        raise Stop(1)
    ET.SubElement(sources, "add", key="local-map", value=feed)
    local = ET.SubElement(mapping, "packageSource", key="local-map")
    ET.SubElement(local, "package", pattern="RulesFactory.Maps.*")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def nuspec_text(archive):
    (nuspec,) = [n for n in archive.namelist() if n.endswith(".nuspec") and "/" not in n]
    return archive.read(nuspec).decode("utf-8")


# Run in the engine directory: every lock file under it must pin the package's content hash.
def check_restored_package(engine, package, cache):
    package, cache, engine = pathlib.Path(package), pathlib.Path(cache), pathlib.Path(engine)
    expected = base64.b64encode(hashlib.sha512(package.read_bytes()).digest()).decode("ascii")
    with zipfile.ZipFile(package) as archive:
        text = nuspec_text(archive)
    pid = re.search(r"<id>([^<]+)</id>", text).group(1)
    version = re.search(r"<version>([^<]+)</version>", text).group(1)
    bad = False
    marker = cache / pid.lower() / version.lower() / f"{pid.lower()}.{version.lower()}.nupkg.sha512"
    if not marker.is_file():
        print(f"  X  {marker} does not exist: the map was not restored into the scratch packages folder"); bad = True
    elif marker.read_text(encoding="utf-8").strip() != expected:
        print(f"  X  restored {pid} {version} has sha512 {marker.read_text().strip()}, the packed .nupkg {expected}"); bad = True
    locks = sorted(lock.relative_to(engine) for lock in engine.rglob("packages.lock.json"))
    seen = 0
    for lock in locks:
        for framework, deps in json.loads((engine / lock).read_text(encoding="utf-8"))["dependencies"].items():
            for name, dep in deps.items():
                if name.lower() == pid.lower():
                    seen += 1
                    if dep.get("contentHash") != expected:
                        print(f"  X  {lock} [{framework}] pins {name} to {dep.get('contentHash')}, not the packed .nupkg"); bad = True
    if seen == 0:
        print(f"  X  no lock file names {pid} -- nothing was compared"); bad = True
    sys.stdout.flush()
    if bad:
        raise Stop(1)
    ok(f"{pid} {version}: restored sha512 and {seen} lock-file contentHash(es) equal the packed .nupkg")


def the_sdk_is_installed(sdk):
    step(f"the .NET SDK {sdk} is installed")
    if shutil.which("dotnet") is None:
        fail(f"no dotnet on PATH; install the .NET SDK {sdk} (the version tools/factory/generate.py pins)")
    sys.stdout.flush()
    listed = subprocess.run(["dotnet", "--list-sdks"], stdout=subprocess.PIPE)
    found = [line.split()[0] for line in listed.stdout.decode("utf-8", errors="replace").splitlines() if line.split()]
    if listed.returncode != 0 or sdk not in found:
        fail(f"the .NET SDK {sdk} is not installed (found: {','.join(found)}); a produced engine cannot be built, "
             f"and this check does not skip")
    ok(f"SDK {sdk}")


def pack_the_map(r):
    step(f"pack {MAP_DIR}")
    check(run_tail_1([PYTHON, "tools/pack-map.py", MAP_DIR, "--out", r.s("package")]))
    packages = one_package(r.s("package", "*.nupkg"))
    if len(packages) != 1:
        fail(f"expected exactly one .nupkg from pack-map.py, found {len(packages)}")
    r.package = packages[0]


# No --allow-dirty: the engine's provenance must name a commit that actually produced it.
# --no-verify only because global.json and NuGet.config must be edited before anything restores;
# the re-produce below verifies.
def produce_from_scratch(r):
    step(f"produce {NAME} from scratch (unverified)")
    check(unverified_produce(["--package", r.package, "--corpus", CORPUS, "--name", NAME, "--out", r.engine]))

    global_json = os.path.join(r.engine, "global.json")
    if not grep_fixed(global_json, f'"version": "{r.pin}"'):
        fail(f"the produced global.json does not pin {r.pin}: {chr(10).join(read_lines(global_json) or [])}")
    r.repin_sdk(r.engine)

    # The build must restore the very .nupkg intake read and provenance hashed, not whatever
    # nuget.org serves under the same id and version: otherwise this job proves a different package
    # from the one the engine was produced from. So, in this scratch copy only, a fresh global
    # packages folder (nothing cached from an earlier restore can stand in) and a local feed holding
    # the packed map, with source mapping that resolves RulesFactory.Maps.* from that feed alone.
    # Everything else (RulesKernel, the test packages) still comes from nuget.org. NuGet.config is
    # a managed file (decision 0018), so the re-produce below adopts it, and provenance then records
    # it as an engine-owned build input (#69).
    os.environ["NUGET_PACKAGES"] = r.s("nuget-packages")
    add_local_feed(os.path.join(r.engine, "NuGet.config"), r.s("package"))

    sys.stdout.flush()
    selected = subprocess.run(["dotnet", "--version"], cwd=r.engine, stdout=subprocess.PIPE)
    selected = selected.stdout.decode("utf-8", errors="replace").rstrip("\n")
    if selected != r.sdk:
        fail(f"global.json selected SDK {selected}, not {r.sdk}")


# The engine now differs from what produce recorded in build inputs only: NuGet.config (the local
# feed) and global.json (under the override). Re-running produce is how a record comes to cover
# such edits (#69), and this time produce verifies, as it does by default: in its staging copy,
# provenance matches, restore writes the lock files (locked mode forced off: there are none yet),
# provenance.json is rewritten to record them before anything builds, and the engine's gate runs
# as the engine's own CI runs it, with CI=true. Only then is the result committed, and it must be
# exactly the two lock files added and provenance.json changed.
def reproduce_verifying(r):
    step("re-produce, verifying: records the edited scaffold and lock files, then runs the engine's gate")
    # NuGet.config and global.json are managed files (tools/factory/ownership.py, decision 0018): a
    # re-produce refuses a hand edit to them. The edits above are deliberate, so the re-produce adopts
    # exactly the files this script edited, as an engine with a private feed would; provenance records
    # them as engine-owned, and every later recompute's re-produce reads that adoption back.
    log = r.s("reproduce.log")
    check(run_tee(log, verified_produce_command(
        ["--package", r.package, "--corpus", CORPUS, "--name", NAME, "--out", r.engine, *r.adopt()]),
        env=verified_produce_env()))
    if not grep_exact(log, f"wrote to {os.path.realpath(r.engine)}: 2 added, 1 changed, 0 removed"):
        fail(f"re-producing should add the 2 lock files and change provenance.json only: {matching(log, '^wrote to')}")
    if not last_line_verified(log):
        fail("produce did not end verified")
    build_inputs_record_the_lock_files(r)


def build_inputs_record_the_lock_files(r):
    with open(os.path.join(r.engine, "provenance.json"), encoding="utf-8") as handle:
        inputs = [b["path"] for b in json.load(handle)["buildInputs"]]
    locks = [p for p in inputs if p.endswith("packages.lock.json")]
    if len(locks) < 2:
        print(f"provenance.json records {len(locks)} lock file(s) after restore; expected one per project",
              file=sys.stderr, flush=True)
        raise Stop(1)
    ok(f"{len(inputs)} build input(s) recorded, {len(locks)} of them lock files")


def the_restored_package_is_the_packed_one(r):
    step("the restored map package is the packed .nupkg")
    check_restored_package(r.engine, r.package, os.environ["NUGET_PACKAGES"])


# The gate already ran, in the staging copy, on exactly these bytes (its locked restore proved
# the lock files complete and consistent with the projects -- not that their hashes were
# reviewed, since a fresh engine has nothing earlier to compare them with). Running it again here
# would build the solution twice more to learn nothing. What remains is that the committed record
# is true of the committed engine, every build input and lock file included.
def provenance_recomputes(r):
    step("factory provenance recomputes on the committed engine")
    check(run([PYTHON, "tools/factory", "provenance", "--engine", r.engine, "--package", r.package]))


SEEDED_DIE = """\
using RulesKernel.Randomness;

namespace {name};

internal static class SeededDie
{{
    internal static int Throw(ulong seed) => UniformInt.InRange(Pcg32.FromSeed(seed, 54), 1, 6);
}}
"""


# #92 (decision 0019): hoyle-1909 declares `randomness: seeded`, so its engine may draw. On a scratch
# copy, reference RulesKernel.Randomness (pinned only by the generated props), throw a seeded die,
# and run the engine's own gate in lock mode, since a new reference needs new lock files: it restores
# the package, accepts it under the corpus's declaration, and builds and tests.
def a_seeded_engine_references_randomness(r):
    step("a seeded corpus's engine references RulesKernel.Randomness, and its gate passes")
    seeded = r.s("seeded")
    copy_engine(r.engine, seeded)
    path, anchor = os.path.join(seeded, "src", NAME, f"{NAME}.csproj"), '    <PackageReference Include="RulesKernel" />\n'
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if anchor not in text:
        raise AssertionError(f"{path} has no RulesKernel reference to add beside")
    write(path, text.replace(anchor, anchor + '    <PackageReference Include="RulesKernel.Randomness" />\n', 1))
    write(os.path.join(seeded, "src", NAME, "SeededDie.cs"), SEEDED_DIE.format(name=NAME))
    env = dict(os.environ)
    env.pop("CI", None)
    log = r.s("seeded.log")
    if run_to(log, ["./scripts/validate.sh", "lock"], cwd=seeded, env=env, both=True) != 0:
        tail(log, 40)
        fail("the gate refused an engine of a seeded corpus that references RulesKernel.Randomness")
    if not grep(log, r"randomness: seeded -- .*\([1-9][0-9]* lock-file resolution"):
        tail(log, 40)
        fail("the seeded engine's gate passed without a lock file resolving RulesKernel.Randomness")
    ok("RulesKernel.Randomness restored under randomness: seeded; the engine's gate passes")


PLAYER_COUNT_OVERLAY = """\
{"player-count": {"status": "implemented", "implementedIn": {"ruleset": "scratch", "version": 1},
                  "tests": [{"test": "CorrespondenceTests.player_count__is_implemented_so_a_hand_written_handler_answers_it",
                             "mutation": "scratch"}]}}
"""

HANDLER = "    internal static partial Resolution<object> PlayerCount(Requests.PlayerCountRequest request) => Resolution<object>.FromValue(2);"


def typed_build(typed, handler):
    """Write a Handlers partial holding `handler` and build the engine project: its exit code, output to typed.log."""
    write(os.path.join(typed, "src", NAME, "PlayerCount.cs"),
          f"using RulesKernel.Resolution;\n\nnamespace {NAME};\n\ninternal static partial class Handlers\n{{\n{handler}\n}}\n")
    return run_to(os.path.join(os.path.dirname(typed), "typed.log"),
                  ["dotnet", "build", f"src/{NAME}/{NAME}.csproj", "-f", "net10.0", "-warnaserror", "-nologo"],
                  cwd=typed, both=True)


# #76: the typed contract is only a contract if the compiler enforces it, and the Python test that
# shows so (tools/tests/test_factory_gate.py) skips without an SDK, as in this repository's
# validate job. So here, on a scratch copy of the committed engine: mark one entry implemented,
# regenerate, and build the engine project with a hand-written handler of the declared type
# (builds), none (CS8795) and one of another return type (CS8817).
def a_mistyped_handler_is_a_build_error(r):
    step("a missing or mis-typed handler for an implemented entry is a build error")
    typed = r.s("typed")
    copy_engine(r.engine, typed)
    write(os.path.join(typed, "corpus-map.overlay.json"), PLAYER_COUNT_OVERLAY)
    with open(os.devnull, "wb") as null:
        check(unverified_produce(["--package", r.package, "--corpus", CORPUS, "--name", NAME, "--out", typed], stdout=null))
    if not grep_fixed(os.path.join(typed, "src", NAME, "Generated", "Contracts.g.cs"),
                      "internal static partial Resolution<object> PlayerCount("):
        fail("the implemented entry player-count has no required handler declaration in Contracts.g.cs")
    log = r.s("typed.log")
    if typed_build(typed, HANDLER) != 0:
        tail(log, 30)
        fail("the handler of the declared type does not build")
    ok("the handler of the declared type builds")
    for label, code, handler in (("missing", "CS8795", ""),
                                 ("another return type", "CS8817", HANDLER.replace("Resolution<object>", "Resolution<int>"))):
        if typed_build(typed, handler) == 0:
            fail(f"a handler with {label} built; the typed contract is not enforced")
        if not grep(log, re.escape(f"error {code}:")):
            tail(log, 30)
            fail(f"a handler with {label} failed to build without error {code}")
        ok(f"a handler with {label}: error {code}")


PLAYER_COUNT_REQUEST = """\
namespace {name}.Requests;

public sealed partial class PlayerCountRequest
{{
    /// <summary>An engine-declared input: the players at the table.</summary>
    public int Players {{ get; init; }}
}}
"""

TYPED_INPUT_TESTS = """\
using RulesKernel.Resolution;
using Xunit;

namespace {name}.Tests;

public sealed class TypedInputTests
{{
    [Fact]
    public void an_engine_declared_input_reaches_the_handler_through_EntryPoints()
    {{
        var typed = EntryPoints.PlayerCount.Resolve(new Requests.PlayerCountRequest {{ Players = 4 }});
        Assert.Equal(4, typed.Match<object?>(v => v, _ => null));
        var generic = Registry.Resolve(new Requests.PlayerCountRequest(RuleRequest.Empty) {{ Players = 3 }});
        Assert.Equal(3, generic.Match<object?>(v => v, _ => null));
        var dictionary = Registry.Resolve("player-count", RuleRequest.Empty);
        Assert.Equal(0, dictionary.Match<object?>(v => v, _ => null));
    }}
}}
"""


def dotnet_test(typed, results, trx, classes):
    """The engine's test project, filtered to `classes`, writing a TRX."""
    return ["dotnet", "test", f"tests/{NAME}.Tests/{NAME}.Tests.csproj", "-f", "net10.0", "-warnaserror", "-nologo",
            "--results-directory", results, "--logger", f"trx;LogFileName={trx}",
            "--filter", "|".join(f"FullyQualifiedName~{NAME}.Tests.{name}" for name in classes)]


# #93: a typed request carries the engine's inputs to its handler. On the same scratch copy, an
# engine-side partial declares an input on PlayerCountRequest, the handler answers with it, and a
# test outside the generated code resolves through EntryPoints (the value arrives) and through the
# dictionary dispatch (a request rebuilt from assertions, so the input is at its default). The
# generated correspondence tests run beside it, so the dispatch change keeps them passing.
def a_request_input_reaches_its_handler(r):
    step("an engine-declared request input reaches its handler through EntryPoints")
    typed = r.s("typed")
    log = r.s("typed.log")
    write(os.path.join(typed, "src", NAME, "PlayerCountRequest.cs"), PLAYER_COUNT_REQUEST.format(name=NAME))
    if typed_build(typed, "    internal static partial Resolution<object> PlayerCount(Requests.PlayerCountRequest request) => Resolution<object>.FromValue(request.Players);") != 0:
        tail(log, 30)
        fail("a request partial with an input property does not build")
    write(os.path.join(typed, "tests", f"{NAME}.Tests", "TypedInputTests.cs"), TYPED_INPUT_TESTS.format(name=NAME))
    if run_to(log, dotnet_test(typed, r.s("typed-results"), "typed.trx", ("TypedInputTests", "CorrespondenceTests")),
              cwd=typed, both=True) != 0:
        tail(log, 40)
        fail("the engine-declared input did not reach its handler, or a correspondence test failed")
    # A filter matching nothing also exits 0, so the test must be in the results, and have passed.
    if not grep(r.s("typed-results", "typed.trx"),
                r'testName="[^"]*TypedInputTests\.an_engine_declared_input_reaches_the_handler_through_EntryPoints"[^>]*outcome="Passed"'):
        fail(f"TypedInputTests did not run and pass: {matching(log, 'Passed!|Failed!')}")
    ok("an input set on PlayerCountRequest arrives through EntryPoints; the dictionary dispatch still resolves")


RULING_OVERLAY = """\
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
"""

BEARING_OFF_ELIGIBLE = """\
using RulesKernel.Resolution;

namespace {name};

internal static partial class Handlers
{{
    internal static partial Resolution<object> BearingOffEligible(Requests.BearingOffEligibleRequest request) =>
        Resolution<object>.FromValue(OwnerRulings.All);
}}

/// <summary>An engine's own member beside the generated rulings.</summary>
public static partial class OwnerRulings
{{
    /// <summary>The ruling under the engine's own name.</summary>
    public static OwnerRuling BearingOffBeginsWithinTheThrow => BearingOffEligible2;
}}

/// <summary>An engine's own member on the generated record.</summary>
public sealed partial record OwnerRuling
{{
    /// <summary>The slug of the id, after the entry.</summary>
    public string Part => Id[(Id.IndexOf('/', StringComparison.Ordinal) + 1)..];
}}
"""

RULINGS_TESTS = """\
using Xunit;

namespace {name}.Tests;

public sealed class RulingsTests
{{
    [Fact]
    public void the_generated_ruling_is_surfaced_on_the_answer()
    {{
        var answer = EntryPoints.BearingOffEligible.Resolve(Requests.BearingOffEligibleRequest.Empty).Match<object?>(v => v, _ => null);
        var ruling = Assert.Single(Assert.IsAssignableFrom<IEnumerable<OwnerRuling>>(answer));
        Assert.Same(OwnerRulings.BearingOffBeginsWithinTheThrow, ruling);
        Assert.Equal(("bearing-off-eligible/2", "bearing-off-eligible", "the owner", new DateOnly(2026, 9, 15), "2"),
            (ruling.Id, ruling.EntryId, ruling.RuledBy, ruling.RuledOn, ruling.Part));
        Assert.StartsWith("Nor does it say when within a throw the stage begins.", ruling.Span, StringComparison.Ordinal);
    }}
}}
"""


# Decision 0027: an owner's ruling on part of an unresolved question lives in the overlay, and the factory
# generates Rulings.g.cs from it. The Python tests (tools/tests/test_factory_rulings.py) show what is
# generated and refused; only a build shows it compiles warning-free beside an engine's own partial members
# and a handler that surfaces it. On the same scratch copy: bearing-off-eligible is implemented with a
# ruling on its second part and a decline of its first, produce accepts it and says whose answer it is, and
# a test outside the generated code resolves the entry and finds the ruling on the answer.
def an_owners_ruling_is_surfaced(r):
    step("an owner's ruling in the overlay generates a registry the engine surfaces")
    typed = r.s("typed")
    log = r.s("ruling.log")
    os.makedirs(os.path.join(typed, "docs", "decisions"), exist_ok=True)
    write(os.path.join(typed, "docs", "decisions", "0001-scratch-ruling.md"),
          "# 0001: a scratch ruling\n\nThe owner ruled; this record holds it.\n")
    write(os.path.join(typed, "corpus-map.overlay.json"), RULING_OVERLAY)
    if unverified_produce_to(log, ["--package", r.package, "--corpus", CORPUS, "--name", NAME, "--out", typed]) != 0:
        tail(log, 20)
        fail("produce refused an overlay with a well-formed owner's ruling")
    if not grep_fixed(log, "owner's ruling bearing-off-eligible/2 on bearing-off-eligible, not the corpus"):
        fail("produce did not say that bearing-off-eligible/2 is the owner's answer")
    if not os.path.isfile(os.path.join(typed, "src", NAME, "Generated", "Rulings.g.cs")):
        fail("no Rulings.g.cs was generated for an overlay with a ruling")
    write(os.path.join(typed, "src", NAME, "BearingOffEligible.cs"), BEARING_OFF_ELIGIBLE.format(name=NAME))
    write(os.path.join(typed, "tests", f"{NAME}.Tests", "RulingsTests.cs"), RULINGS_TESTS.format(name=NAME))
    if run_to(log, dotnet_test(typed, r.s("ruling-results"), "ruling.trx", ("RulingsTests", "CorrespondenceTests")),
              cwd=typed, both=True) != 0:
        tail(log, 40)
        fail("the generated rulings did not build warning-free, or a test failed")
    if not grep(r.s("ruling-results", "ruling.trx"),
                r'testName="[^"]*RulingsTests\.the_generated_ruling_is_surfaced_on_the_answer"[^>]*outcome="Passed"'):
        fail(f"RulingsTests did not run and pass: {matching(log, 'Passed!|Failed!')}")
    ok("Rulings.g.cs builds with -warnaserror beside engine partials, and the answer carries the ruling")


DOUBLER = """\
namespace Extra;

/// <summary>A project the engine added itself.</summary>
public static class Doubler
{
    /// <summary>Doubles a value.</summary>
    /// <param name="value">The value to double.</param>
    /// <returns>Twice <paramref name="value"/>.</returns>
    public static int Twice(int value) => value * 2;
}
"""

EXTRA_TESTS_PROJECT = """\
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
"""

DOUBLER_TESTS = """\
using Xunit;

namespace Extra.Tests;

public class DoublerTests
{
    [Fact]
    public void Twice_doubles_its_argument() => Assert.Equal(4, Doubler.Twice(2));
}
"""


def own_files(engine):
    """`find <the engine's own files> -type f -print0 | sort -z | xargs -0 sha256sum`, as text; None when one is missing."""
    missing = False
    files = []
    for top in ("src/Extra", "tests/Extra.Tests", f"{NAME}.slnx", f"src/{NAME}/packages.lock.json",
                f"tests/{NAME}.Tests/packages.lock.json"):
        path = os.path.join(engine, top)
        if os.path.isdir(path) and not os.path.islink(path):
            for directory, _, names in os.walk(path):
                files += [os.path.relpath(os.path.join(directory, name), engine) for name in names
                          if os.path.isfile(os.path.join(directory, name)) and not os.path.islink(os.path.join(directory, name))]
        elif os.path.isfile(path) and not os.path.islink(path):
            files.append(top)
        elif not os.path.lexists(path):
            print(f"find: '{top}': No such file or directory", file=sys.stderr, flush=True)
            missing = True
    text = "".join(f"{sha256(os.path.join(engine, name))}  {name}\n" for name in sorted(files))
    return None if missing else text


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


# #94, case 1 of 2: produce into an existing engine that has projects of its own. An engine adds a
# src project and a test project to its solution and locks them itself (a plain restore writes
# their lock files and leaves the committed ones as they are). A re-produce with the same package
# must commit verified, change provenance.json only (the new projects are build inputs it now
# records), and leave every file of the engine's own projects byte-identical.
def reproduce_beside_the_engines_own_projects(r):
    step("re-produce into an engine with its own src and test projects")
    engine = r.engine
    os.makedirs(os.path.join(engine, "src", "Extra"), exist_ok=True)
    os.makedirs(os.path.join(engine, "tests", "Extra.Tests"), exist_ok=True)
    write(os.path.join(engine, "src", "Extra", "Extra.csproj"), '<Project Sdk="Microsoft.NET.Sdk">\n</Project>\n')
    write(os.path.join(engine, "src", "Extra", "Doubler.cs"), DOUBLER)
    write(os.path.join(engine, "tests", "Extra.Tests", "Extra.Tests.csproj"), EXTRA_TESTS_PROJECT)
    write(os.path.join(engine, "tests", "Extra.Tests", "DoublerTests.cs"), DOUBLER_TESTS)
    solution = os.path.join(engine, f"{NAME}.slnx")
    with open(solution, encoding="utf-8") as handle:
        text = handle.read()
    extra = '  <Project Path="src/Extra/Extra.csproj" />\n  <Project Path="tests/Extra.Tests/Extra.Tests.csproj" />\n'
    write(solution, text.replace("</Solution>", extra + "</Solution>"))
    if run_to(r.s("extra-lock.log"), ["dotnet", "restore", f"{NAME}.slnx", "-p:RestoreLockedMode=false", "-nologo"],
              cwd=engine) != 0:
        tail(r.s("extra-lock.log"), 30)
        fail("restoring the engine's own projects failed")
    remove_build_output(engine)
    if not (os.path.isfile(os.path.join(engine, "src", "Extra", "packages.lock.json"))
            and os.path.isfile(os.path.join(engine, "tests", "Extra.Tests", "packages.lock.json"))):
        fail("restore wrote no lock files for the engine's own projects")
    before = own_files(engine)
    if before is None:
        raise Stop(1)
    write(r.s("own-before.txt"), before)
    log = r.s("extra.log")
    check(run_tee(log, verified_produce_command(
        ["--package", r.package, "--corpus", CORPUS, "--name", NAME, "--out", engine]), env=verified_produce_env()))
    if not last_line_verified(log):
        fail("re-producing into an engine with its own projects did not end verified")
    if not grep_exact(log, f"wrote to {os.path.realpath(engine)}: 0 added, 1 changed, 0 removed"):
        fail(f"re-producing into an engine with its own projects should change provenance.json only: {matching(log, '^wrote to')}")
    if not grep(log, "restore -- skipped"):
        fail("the pins did not change, yet verify did not skip its restore")
    after = own_files(engine)
    # diff prints what moved, as the shell's `own_files | diff before -` did.
    if run(["diff", r.s("own-before.txt"), "-"], stdin=(after or "").encode("utf-8")) != 0 or after is None:
        fail("re-producing changed the engine's own projects or lock files")
    ok("the engine's own projects and every lock file are byte-identical after a verified re-produce")


def lock_hashes(engine):
    """`sha256sum engine/src/*/packages.lock.json engine/tests/*/packages.lock.json`."""
    paths = []
    for pattern in ("src/*/packages.lock.json", "tests/*/packages.lock.json"):
        paths += sorted(glob.glob(os.path.join(engine, pattern)))
    return [(path, sha256(path)) for path in paths]


def bump_version(path):
    """map-package.json at the next patch version; that version."""
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    major, minor, patch = document["version"].split(".")
    document["version"] = f"{major}.{minor}.{int(patch) + 1}"
    write(path, json.dumps(document, indent=2) + "\n")
    return document["version"]


def provenance_records_the_bump(engine, bumped):
    """provenance.json names the bumped map and records exactly the lock files on disk; the complaint, or None."""
    engine = pathlib.Path(engine)
    record = json.loads((engine / "provenance.json").read_text(encoding="utf-8"))
    if record["map"]["version"] != bumped:
        return f"provenance.json records map {record['map']['version']}, not {bumped}"
    recorded = {b["path"]: b["sha256"] for b in record["buildInputs"] if b["path"].endswith("packages.lock.json")}
    on_disk = {str(p.relative_to(engine)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in engine.rglob("packages.lock.json") if not {"bin", "obj"} & set(p.relative_to(engine).parts)}
    if recorded != on_disk:
        return f"provenance.json records lock files {sorted(recorded)} that are not the re-locked ones on disk {sorted(on_disk)}"
    ok(f"provenance.json records map {bumped} and the {len(recorded)} re-locked lock files")
    return None


# #94, case 2 of 2: a map version bump into a locked engine (the engine above, own projects
# included). The same map, packed at the next patch version into the local feed, changes the pins
# in RulesFactory.Packages.g.props, so verify must re-lock before the gate's locked restore;
# provenance.json must record the re-locked files, the committed record must recompute, and the
# restored package must be the newly packed one.
def a_map_version_bump_relocks(r):
    step("a map version bump re-produces verified, re-locking the lock files")
    bump_dir = r.s("bump", os.path.basename(MAP_DIR))
    os.makedirs(os.path.dirname(bump_dir), exist_ok=True)
    shutil.copytree(MAP_DIR, bump_dir, symlinks=True)
    bumped = bump_version(os.path.join(bump_dir, "map-package.json"))
    check(run_tail_1([PYTHON, "tools/pack-map.py", bump_dir, "--out", r.s("package")]))
    packages = one_package(r.s("package", f"*.{glob.escape(bumped)}.nupkg"))
    if len(packages) != 1:
        fail(f"expected one .nupkg at version {bumped} from pack-map.py, found {len(packages)}")
    package_bumped = packages[0]
    locks_before = lock_hashes(r.engine)
    log = r.s("bump.log")
    check(run_tee(log, verified_produce_command(
        ["--package", package_bumped, "--corpus", CORPUS, "--name", NAME, "--out", r.engine]), env=verified_produce_env()))
    if not last_line_verified(log):
        fail("the map version bump did not commit verified")
    if not grep(log, re.escape("the generated pins changed, so this restore re-locks the 4 lock file(s)")):
        fail("the map version bump did not re-lock the 4 lock files")
    if not grep(log, r"^re-locked [0-9]* packages.lock.json file\(s\) because the generated pins changed"):
        fail("produce did not report re-locked lock files")
    if lock_hashes(r.engine) == locks_before:
        fail("the map version bump committed without changing any lock file")
    try:
        complaint = provenance_records_the_bump(r.engine, bumped)
    except Exception:  # the shell's inline Python died with a traceback, and the run failed the same way
        traceback.print_exc()
        complaint = ""
    if complaint is not None:
        if complaint:
            print(complaint, file=sys.stderr, flush=True)
        fail("provenance.json does not record the bump")
    check_restored_package(r.engine, package_bumped, os.environ["NUGET_PACKAGES"])
    step("factory provenance recomputes on the bumped engine")
    check(run([PYTHON, "tools/factory", "provenance", "--engine", r.engine, "--package", package_bumped]))


def player_count_evidence():
    with open("examples/hoyle-backgammon/corpus-map.json") as handle:
        entry = next(e for e in json.load(handle)["entries"] if e["id"] == "player-count")
    return str(entry["evidence"])


# The rails an engine ships with, run in a produced engine rather than in a fixture (rules-factory
# decision 0029, #157). What is proved here and cannot be proved in tools/tests: the entry packet
# resolving the map package through MSBuild -- the path a real agent takes, and the one the unit
# tests skip by passing --package-map -- and the guard refusing a commit in a produced engine's own
# checkout. The rails' own logic (the verdict invalidated by a new head commit, the chain read from
# the policy, the pull request contract) is proved in tools/tests/test_factory_rails.py against
# this same output, and is not restated here: a second definition would be one more thing to drift.
def the_rails_run_in_a_produced_engine(r):
    step("the rails a produced engine ships with run in it")
    # In a copy, which is then restored: the packet asks MSBuild where the map package is, and MSBuild
    # can only answer that where a restore has happened. `produce` commits no obj/, so a freshly
    # committed engine has no answer yet -- which is what an agent's first command in a new worktree
    # hits too, and why the packet says "restore first" rather than guessing at the packages folder.
    railed = r.s("railed")
    copy_engine(r.engine, railed)
    if run_to(r.s("railed-restore.log"), ["dotnet", "restore", f"{NAME}.slnx"], cwd=railed, both=True) != 0:
        tail(r.s("railed-restore.log"), 20)
        fail("the copy of the engine does not restore")
    the_entry_packet_resolves_through_msbuild(r, railed)
    the_doctor_names_the_remote_half_unexamined(r, railed)
    the_guard_refuses_a_primary_checkout_commit(r, railed)


# The packet, with no --package-map: it asks MSBuild where the restore put the map, as the gate does.
def the_entry_packet_resolves_through_msbuild(r, railed):
    sys.stdout.flush()
    result = subprocess.run([PYTHON, "tools/entry-packet.py", "player-count", "--out", r.s("packets")],
                            cwd=railed, stdout=subprocess.PIPE)
    if result.returncode != 0:
        fail("tools/entry-packet.py could not assemble an entry packet in a produced engine")
    packet = result.stdout.decode("utf-8", errors="replace").rstrip("\n")
    if not grep_fixed(packet, "# Entry packet: `player-count`"):
        fail("the packet is not the entry it was asked for")
    if not grep_fixed(packet, player_count_evidence()):
        fail("the packet does not carry the entry's evidence verbatim")
    if not grep(packet, re.escape("PlayerCount(")):
        fail("the packet does not declare the handler the engine generates")
    ok("tools/entry-packet.py resolved the map package through MSBuild and assembled player-count")


# The doctor: every local row true of a freshly produced engine, and the remote half named as not
# examined rather than counted as passing.
def the_doctor_names_the_remote_half_unexamined(r, railed):
    log = r.s("doctor.log")
    if run_to(log, [PYTHON, "tools/agent-doctor.py", "--local"], cwd=railed, both=True) == 0:
        cat(log)
        fail("agent-doctor.py --local exited 0; it must say the remote half was not examined")
    for pattern, message in (("NOT EXAMINED", "the doctor did not say the remote half was unexamined"),
                             ("^Rail files .* OK", "a produced engine is missing a rail"),
                             ("^Guard wired to the tools .* OK", "the guard is not wired to anything"),
                             ("^Gate checks the rails .* OK", "the gate does not check the rails"),
                             ("^Review chain .* OK", "no review chain is configured")):
        if not grep(log, pattern):
            cat(log)
            fail(message)
    ok("tools/agent-doctor.py --local: every local rail true, the remote half named unexamined")


def guard(railed, **extra):
    """The primary-checkout guard, asked about `git commit` in the railed engine, with `extra` in its environment."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=railed, **extra)
    event = f'{{"tool_name": "Bash", "tool_input": {{"command": "git commit -m x"}}, "cwd": "{railed}"}}'
    return [PYTHON, ".claude/hooks/primary-checkout-guard.py"], env, event.encode("utf-8")


# The guard, in the produced engine's own checkout: a commit on the primary checkout is refused,
# and the escape hatch AGENTS.md documents is the thing that lifts it.
def the_guard_refuses_a_primary_checkout_commit(r, railed):
    identity = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]
    with open(os.devnull, "wb") as null:
        check(run(["git", "-C", railed, "init", "-q", "-b", "main"]))
        check(run(["git", "-C", railed, *identity, "add", "AGENTS.md"], stdout=null))
        check(run(["git", "-C", railed, *identity, "commit", "-qm", "first"], stdout=null))
    log = r.s("guard.log")
    command, env, event = guard(railed, IGNORED="1")
    if run_to(log, command, cwd=railed, env=env, both=True, stdin=event) == 0:
        cat(log)
        fail("the guard allowed a commit in the primary checkout")
    if not grep(log, "commit in the primary checkout"):
        cat(log)
        fail("the guard blocked for some other reason")
    if not grep(log, "RULES_ENGINE_ALLOW_PRIMARY_MUTATION"):
        fail("the guard does not name its escape hatch where it blocks")
    if not grep_fixed(os.path.join(railed, "AGENTS.md"), "RULES_ENGINE_ALLOW_PRIMARY_MUTATION"):
        fail("the escape hatch is not documented in AGENTS.md; that is the predecessor's exact failure")
    command, env, event = guard(railed, RULES_ENGINE_ALLOW_PRIMARY_MUTATION="1")
    if run_to(log, command, cwd=railed, env=env, both=True, stdin=event) != 0:
        cat(log)
        fail("the documented escape hatch did not lift the guard")
    ok("the guard refuses a commit in the primary checkout, and the documented hatch lifts it")


AMBIENT_CLOCK = """\
namespace {namespace};

internal static class AmbientClock
{{
    internal static int Hour() => System.DateTime.Now.Hour;
}}
"""


# The kernel's determinism analyzers, on the engine the factory just produced (rules-factory
# decision 0029). A pin in a props file and a severity in .editorconfig prove nothing on their own:
# what has to be true is that a non-deterministic construct in the rules stops the build, and that
# the same construct in a test does not. Both directions are checked here, on the engine's real
# toolchain, because nothing else can check them.
def a_determinism_defect_stops_the_build(r):
    step("a determinism defect in the engine is a build error, and in a test it is not")
    analyzed = r.s("analyzed")
    copy_engine(r.engine, analyzed)
    if not grep_fixed(os.path.join(analyzed, "RulesFactory.Packages.g.props"), '<PackageVersion Include="RulesKernel.Analyzers"'):
        fail("the produced engine does not pin RulesKernel.Analyzers")
    if not grep_fixed(os.path.join(analyzed, ".editorconfig"), "dotnet_diagnostic.RK0002.severity = warning"):
        fail("the produced engine's .editorconfig does not set the analyzers' severities")

    # RK0002: an ambient clock. The same two lines in both places, so the only difference is where.
    clock = os.path.join(analyzed, "src", NAME, "AmbientClock.cs")
    write(clock, AMBIENT_CLOCK.format(namespace=NAME))
    log = r.s("analyzed.log")
    if run_to(log, ["dotnet", "build", f"src/{NAME}/{NAME}.csproj", "-f", "net10.0", "-nologo"], cwd=analyzed, both=True) == 0:
        tail(log, 20)
        fail("an ambient clock in the engine built; the determinism analyzers are not enforced")
    if not grep(log, "RK0002"):
        tail(log, 30)
        fail("the engine failed to build without RK0002; something else broke it")
    ok("an ambient clock in src/ is RK0002, and the build stops")
    os.remove(clock)

    write(os.path.join(analyzed, "tests", f"{NAME}.Tests", "AmbientClock.cs"), AMBIENT_CLOCK.format(namespace=f"{NAME}.Tests"))
    log = r.s("analyzed-tests.log")
    if run_to(log, ["dotnet", "build", f"tests/{NAME}.Tests/{NAME}.Tests.csproj", "-f", "net10.0", "-warnaserror", "-nologo"],
              cwd=analyzed, both=True) != 0:
        tail(log, 30)
        fail("the same construct in a test stopped the build; tests are scaffolding, not the product")
    ok("the same construct in tests/ builds: a test may fix a clock")


class Refused(Exception):
    """An example map CI cannot produce an engine from."""


def describe_example(package, directory):
    """(engine name, corpus path, corpus source id) for an example's package.

    The engine name is the package id's last segment; the corpus is the committed copy the manifest names."""
    with zipfile.ZipFile(package) as archive:
        package_id = re.search(r"<id>([^<]+)</id>", nuspec_text(archive)).group(1)
        cited = json.loads(archive.read("map/corpus-map.json"))["corpus"]
        corpora = [c for c in json.loads(archive.read("map/corpus-manifest.json"))["corpora"] if c.get("sourceId") == cited]
    if len(corpora) != 1 or corpora[0].get("verification") != "committed-copy":
        raise Refused(f"{directory}: {cited} is not one committed-copy corpus, so CI cannot produce its engine")
    return package_id.rsplit(".", 1)[-1], os.path.join(directory, os.path.basename(corpora[0]["committedPath"])), cited


def an_example_engine_passes_its_gate(r, directory):
    """One example map, produced from scratch and verified the way a default `produce` verifies one."""
    slug = os.path.basename(directory)
    feed = r.s("feeds", slug)
    check(run_tail_1([PYTHON, "tools/pack-map.py", directory, "--out", feed]))
    packages = one_package(os.path.join(glob.escape(feed), "*.nupkg"))
    if len(packages) != 1:
        fail(f"expected exactly one .nupkg from pack-map.py {directory}, found {len(packages)}")
    package = packages[0]
    try:
        name, corpus, source = describe_example(package, directory)
    except Refused as refusal:
        print(refusal, file=sys.stderr, flush=True)
        fail(f"cannot read what {package} produces")
    except Exception:
        traceback.print_exc()
        fail(f"cannot read what {package} produces")
    engine = r.s("examples", slug)
    log = r.s(f"example-{slug}.log")
    if unverified_produce_to(log, ["--package", package, "--corpus", corpus, "--name", name, "--out", engine], both=True) != 0:
        tail(log, 40)
        fail(f"producing {name} from {directory} failed")
    r.repin_sdk(engine)
    add_local_feed(os.path.join(engine, "NuGet.config"), feed)
    if run_to(log, verified_produce_command(["--package", package, "--corpus", corpus, "--name", name, "--out", engine,
                                             *r.adopt()]), env=verified_produce_env(), both=True) != 0:
        tail(log, 60)
        fail(f"{name}, produced from {directory}, did not pass verify (its gate's output is above)")
    if not last_line_verified(log):
        tail(log, 40)
        fail(f"producing {name} did not end verified")
    if not grep_fixed(log, f"verified: {source} (committed-copy"):
        tail(log, 60)
        fail(f"{name}'s gate did not recompute the {source} baseline")
    check_restored_package(engine, package, os.environ["NUGET_PACKAGES"])
    ok(f"{name} ({directory}): verified, its gate recomputed the {source} baseline")


# #106: everything above is one map's engine, and a corpus admitted with something only its own
# engine exercises (the SRD's hashDerivation, which the gate could not recompute) passed every check
# here while no SRD engine could pass its gate. So every other example map that declares a package is
# produced from scratch too, and its engine verified the way a default `produce` verifies one: restore
# from the packed .nupkg, then the whole gate, posture (the baseline recomputed under the corpus's own
# derivation) through build and tests. Only the scratch feed and SDK edits are shared with the engine
# above; none of the mutations are repeated.
def every_other_example_passes_its_gate(r):
    step("every other packable example map produces an engine whose gate passes")
    examples = 0
    # Without nullglob, as the shell had it: no match leaves the pattern itself, which then fails to pack.
    for settings in sorted(glob.glob("examples/*/map-package.json")) or ["examples/*/map-package.json"]:
        directory = os.path.dirname(settings)
        examples += 1
        if directory == MAP_DIR:
            print(f"     {directory}: produced and verified above", flush=True)
            continue
        an_example_engine_passes_its_gate(r, directory)
    if examples < 2:
        fail(f"found {examples} packable example map(s); this step proved nothing beyond the engine above")


def usage(argv0):
    return f"usage: {argv0} [--print-sdk]"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    argv0 = os.environ.pop(ARGV0, "scripts/validate-engine.sh")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(line_buffering=True)
    try:
        if argv[:1] == ["--print-sdk"]:
            print(sdk_pin())
            return 0
        if argv:
            print(usage(argv0), file=sys.stderr)
            return 2
        os.chdir(ROOT)
        pin = sdk_pin()
        if not pin:
            fail("could not read SDK_VERSION from tools/factory/generate.py")
        override = sdk_override()
        sdk = override or pin
        if override:
            print(verify_module().override_warning(sdk, pin), file=sys.stderr, flush=True)

        the_sdk_is_installed(sdk)
        scratch = tempfile.mkdtemp()
        try:
            r = Run(pin, sdk, scratch)
            pack_the_map(r)
            produce_from_scratch(r)
            reproduce_verifying(r)
            the_restored_package_is_the_packed_one(r)
            provenance_recomputes(r)
            a_seeded_engine_references_randomness(r)
            a_mistyped_handler_is_a_build_error(r)
            a_request_input_reaches_its_handler(r)
            an_owners_ruling_is_surfaced(r)
            reproduce_beside_the_engines_own_projects(r)
            a_map_version_bump_relocks(r)
            the_rails_run_in_a_produced_engine(r)
            a_determinism_defect_stops_the_build(r)
            every_other_example_passes_its_gate(r)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

        print(f"\nvalidate-engine.sh: PASS (SDK {sdk}{'' if sdk == pin else f', OVERRIDDEN from {pin}'})")
        return 0
    except Stop as stop:
        return stop.code


if __name__ == "__main__":
    sys.exit(main())
