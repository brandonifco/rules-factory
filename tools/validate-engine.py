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
only test that tried (tools/tests/factory/test_factory_provenance.py) skips without it. A green run
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
tools/tests/factory/test_validate_engine.py.

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


def porcelain(repo):
    """`git -C repo status --porcelain`, stripped: exactly what tools/dispatch-agent.sh reads to
    decide whether the primary checkout is clean enough to dispatch from (#194)."""
    done = subprocess.run(["git", "-C", repo, "status", "--porcelain"], stdout=subprocess.PIPE)
    return done.stdout.decode("utf-8", errors="replace").strip()


def bytecode_dirs(root):
    """Every __pycache__ directory under root, .git aside; sorted, relative to root."""
    found = []
    for base, directories, _ in os.walk(root):
        directories[:] = [d for d in directories if d != ".git"]
        found += [os.path.relpath(os.path.join(base, d), root) for d in directories if d == "__pycache__"]
    return sorted(found)


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


def write_overlay(root, document):
    """The engine's overlay/ as `document` says: one file per entry, `overlay/<entry id>.json` (#247)."""
    directory = os.path.join(root, "overlay")
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            os.remove(os.path.join(directory, name))
    # An engine with no implemented entry has no overlay/ at all: nothing scaffolds one (#247).
    os.makedirs(directory, exist_ok=True)
    for entry_id, item in json.loads(document).items():
        write(os.path.join(directory, f"{entry_id}.json"), json.dumps(item, indent=2) + "\n")


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
                             "mutation": "Registry.HasImplementation was made to answer false for every entry (`=> false` for `Implementations.Value.ContainsKey(entryId) || Handlers.Has(entryId)` in Registry.g.cs); this test went red. Deleting the handler instead is CS8795, a build error, not a red test."}]}}
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
# shows so (tools/tests/factory/test_factory_gate.py) skips without an SDK, as in this repository's
# validate job. So here, on a scratch copy of the committed engine: mark one entry implemented,
# regenerate, and build the engine project with a hand-written handler of the declared type
# (builds), none (CS8795) and one of another return type (CS8817).
def a_mistyped_handler_is_a_build_error(r):
    step("a missing or mis-typed handler for an implemented entry is a build error")
    typed = r.s("typed")
    copy_engine(r.engine, typed)
    write_overlay(typed, PLAYER_COUNT_OVERLAY)
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


# #192: implementing an entry changes the overlay, and provenance.json is generated from that
# overlay. `regenerate --write` refreshes the generated C# and nothing else, so on its own it leaves
# a record hashing bytes that are gone and hashing the overlay as it was before the edit -- which is
# what the live run of #157 merged, because the gate did not look. Since #243 took the backlog out
# of the engine, `buildInputs[overlay/<entry id>.json]` is the only comparison that carries this
# case -- compared as a set since #247, so an entry's evidence added, as it is here, is caught like
# one edited -- and this is where it is proven on a real engine end to end. On the same
# scratch copy as the check above, and with no extra dotnet build: mark an entry implemented,
# regenerate, and hold the gate's own provenance step to failing and then, after a produce, passing.
def a_stale_record_fails_the_gate(r):
    step("an overlay edit that was regenerated but never re-produced fails the engine's gate")
    stale = r.s("stale")
    copy_engine(r.engine, stale)
    parts = r.s("stale-package")
    os.makedirs(parts, exist_ok=True)
    with zipfile.ZipFile(r.package) as archive:
        nuspec = nuspec_text(archive)
        for member in ("map/corpus-map.json", "map/corpus-manifest.json"):
            with open(os.path.join(parts, os.path.basename(member)), "wb") as handle:
                handle.write(archive.read(member))
    package_id = re.search(r"<id>([^<]+)</id>", nuspec).group(1)
    version = re.search(r"<version>([^<]+)</version>", nuspec).group(1)
    write_overlay(stale, PLAYER_COUNT_OVERLAY)

    log = r.s("stale.log")
    gate = [PYTHON, "scripts/engine-gate.py"]
    if run_to(log, gate + ["regenerate", "--package-map", os.path.join(parts, "corpus-map.json"),
                           "--package-manifest", os.path.join(parts, "corpus-manifest.json"),
                           "--package-id", package_id, "--package-version", version, "--name", NAME,
                           "--write"], cwd=stale, both=True) != 0:
        tail(log, 20)
        fail("the regeneration an implementer runs after an overlay edit failed")
    ok("regenerate --write refreshed the generated C#, and that is all it did")

    if run_to(log, gate + ["provenance"], cwd=stale, both=True) == 0:
        tail(log, 20)
        fail("the gate passed on an engine whose record is older than the overlay it was generated from")
    for named in ("buildInputs[overlay/player-count.json]", "tools/re-produce.sh"):
        if not grep_fixed(log, named):
            tail(log, 20)
            fail(f"the stale-record failure does not name {named}")
    ok("provenance fails, naming the overlay and the one command that fixes it")

    # That command clones rules-factory at the commit the record names and runs exactly this
    # produce; that it takes the recorded commit and never `main` is tools/tests/factory/test_factory_rails.py's
    # to prove. The factory under test here is this checkout, so the produce is run from it directly.
    with open(os.devnull, "wb") as null:
        check(unverified_produce(["--package", r.package, "--corpus", CORPUS, "--name", NAME, "--out", stale],
                                 stdout=null))
    if run_to(log, gate + ["provenance"], cwd=stale, both=True) != 0:
        tail(log, 20)
        fail("the record is still stale after a re-produce")
    ok("a re-produce makes the record true of the tree again")


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
                             "mutation": "Registry.HasImplementation was made to answer false for every entry (`=> false` for `Implementations.Value.ContainsKey(entryId) || Handlers.Has(entryId)` in Registry.g.cs); this test went red. Deleting the handler instead is CS8795, a build error, not a red test."}]},
 "bearing-off-eligible": {"status": "implemented", "implementedIn": {"ruleset": "scratch", "version": 1},
                          "tests": [{"test": "RulingsTests.the_generated_ruling_is_surfaced_on_the_answer",
                                     "mutation": "Handlers.BearingOffEligible answered no rulings (`FromValue(Array.Empty<OwnerRuling>())` for `FromValue(OwnerRulings.All)`), so Assert.Single found none; this test went red."},
                                    {"test": "CorrespondenceTests.bearing_off_eligible__is_implemented_so_a_hand_written_handler_answers_it",
                                     "mutation": "Registry.HasImplementation was made to answer false for every entry (`=> false` for `Implementations.Value.ContainsKey(entryId) || Handlers.Has(entryId)` in Registry.g.cs); this test went red. Deleting the handler instead is CS8795, a build error, not a red test."}],
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
# generates Rulings.g.cs from it. The Python tests (tools/tests/factory/test_factory_rulings.py) show what is
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
    write_overlay(typed, RULING_OVERLAY)
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
# tests skip by passing --package-map -- the packet leaving git status --porcelain empty in a
# committed checkout, so the next dispatch is not refused (#194), and the guard refusing a commit
# in a produced engine's own checkout. Then the four behaviours #157 names, run as the produced
# engine's own files with a stand-in for GitHub: the pull request contract, the verdict tied to the
# head commit, the independent-risk issue, the recorded verdict re-running the required check
# through the emitted workflow's own wiring (#191), a factory update's claim checked against the
# engine's own record and vendored ownership table (#193), and the provider chain as configuration.
# tools/tests/factory/test_factory_rails.py proves the same logic in depth; what only this can prove is that it holds in what an engine
# actually receives, after produce has written it -- not in the recipe copies the tests read.
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
    github = FakeGitHub(r.s("fake-gh"))
    the_entry_packet_resolves_through_msbuild(r, railed)
    the_doctor_names_the_remote_half_unexamined(r, railed)
    the_entry_packet_leaves_the_checkout_clean(r, railed)
    # Before the guard check, which turns `railed` itself into a git repository: this one makes its
    # own committed copy, and a copy of a checkout is a different thing from a copy of a tree.
    the_sweep_removes_what_merged_work_left_behind(r, railed, github)
    the_guard_refuses_a_primary_checkout_commit(r, railed)
    a_malformed_pull_request_is_refused_by_the_contract(r, railed, github)
    a_verdict_at_one_commit_does_not_pass_another(r, railed, github)
    an_independent_risk_issue_needs_more_than_the_semantic_verdict(r, railed, github)
    the_verdict_re_runs_the_gate(r, railed, github)
    a_late_risk_label_re_runs_the_gate(r, railed, github)
    a_factory_update_is_checked_against_the_tree_that_produced_it(r, railed, github)
    swapping_the_provider_chain_is_an_edit_to_the_policy_alone(r, railed, github)


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
                             ("^Review chain .* OK", "no review chain is configured"),
                             # #236: the one question --local cannot answer, answered as NOT
                             # CHECKED rather than as an OK about a listing nobody read.
                             ("^Leftovers from merged work .* NOT CHECKED", "the doctor called leftovers from "
                              "merged work OK, or left the row out, with the merged listing unread")):
        if not grep(log, pattern):
            cat(log)
            fail(message)
    ok("tools/agent-doctor.py --local: every local rail true, the remote half and the leftovers named unexamined")


# The four lines brandonifco/faa-part-107 carries today, and the reason this check is worth
# running: the factory emits no .gitignore, so this is a hand-made file downstream, and it does
# not mention __pycache__.
ENGINE_GITIGNORE = """bin/
obj/
artifacts/
TestResults/
"""


# Running the packet leaves the checkout clean, so the next `tools/dispatch-agent.sh` still opens
# a worktree (#194): the live run of #157 on brandonifco/faa-part-107 was stopped by
# "?? scripts/factory/__pycache__/" after the packet imported the vendored scripts/factory.
#
# The ignore list written below is that engine's own, verbatim, and it does not name __pycache__.
# That is the point: what is proved here is that the tool's own sys.dont_write_bytecode keeps the
# checkout clean on an engine as it exists today, with no help from an ignore list -- which is why
# the fix for #194 did not have to invent a factory-emitted .gitignore. PYTHONDONTWRITEBYTECODE is
# removed from the environment for the same reason: the gate and `factory verify` export it, but
# the agent shell that runs the packet exports nothing, and only the tool's own flag stands
# between the import and a __pycache__.
#
# A copy, and shutil.copytree rather than copy_engine: obj/ must survive, because the packet asks
# MSBuild where the map package is and MSBuild can only answer where the restore above happened.
def the_entry_packet_leaves_the_checkout_clean(r, railed):
    engine = r.s("pycache")
    shutil.copytree(railed, engine, symlinks=True)
    write(os.path.join(engine, ".gitignore"), ENGINE_GITIGNORE)
    identity = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]
    with open(os.devnull, "wb") as null:
        check(run(["git", "-C", engine, "init", "-q", "-b", "main"]))
        check(run(["git", "-C", engine, *identity, "add", "-A"], stdout=null))
        check(run(["git", "-C", engine, *identity, "commit", "-qm", "produced"], stdout=null))
    if porcelain(engine):
        print(porcelain(engine), file=sys.stderr, flush=True)
        fail("the committed copy of the produced engine is not clean before the packet runs")

    env = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
    log = r.s("pycache-packet.log")
    if run_to(log, [PYTHON, "tools/entry-packet.py", "player-count", "--out", r.s("packets-clean")],
              cwd=engine, env=env, both=True) != 0:
        cat(log)
        fail("tools/entry-packet.py could not assemble a packet with PYTHONDONTWRITEBYTECODE unset")
    written = bytecode_dirs(engine)
    if written:
        fail(f"tools/entry-packet.py wrote bytecode into the engine: {', '.join(written)}")
    dirty = porcelain(engine)
    if dirty:
        fail(f"the packet left the checkout dirty, so dispatch-agent.sh would refuse:\n{dirty}")

    # The control. This import suppresses nothing, so it must write the __pycache__ the packet did
    # not -- and if it does not, then this engine, this git and this environment cannot tell a
    # fixed engine from a broken one, and the two assertions above proved nothing.
    if run_to(log, [PYTHON, "-c", "import sys; sys.path.insert(0, 'scripts/factory'); import generate"],
              cwd=engine, env=env, both=True) != 0:
        cat(log)
        fail("the control could not import the vendored scripts/factory")
    control = bytecode_dirs(engine)
    if not control:
        fail("an import that suppresses nothing left no __pycache__ either, so this check cannot "
             "distinguish a fixed engine from a broken one and proves nothing")
    if not porcelain(engine):
        fail("the control's __pycache__ does not show in git status, so the clean status above "
             "proves nothing about what dispatch-agent.sh would see")
    for relative in control:
        shutil.rmtree(os.path.join(engine, relative))
    ok("tools/entry-packet.py leaves git status --porcelain empty on a produced engine whose "
       ".gitignore does not name __pycache__, where an unsuppressed import does not")


def head_of(repo):
    """`git -C repo rev-parse HEAD`, stripped."""
    return subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


# #236: what merged work left behind is removed before the next dispatch, and what somebody is
# still working in is not. tools/tests/factory/test_factory_rails.py proves each branch of the rule
# in depth; what only this can prove is that the file an engine actually receives does it, against
# a real `git worktree` in a produced engine's own checkout.
#
# The order below is the sequence an engine lives through: dispatch, nothing merged yet, work
# committed, the pull request merged, and the next dispatch finding the leftover in its way. Each
# assertion names the sentence and not only the exit code (#283) -- a sweep that refused, a sweep
# that could not reach GitHub and a sweep with nothing to do all leave the same directory behind.
def the_sweep_removes_what_merged_work_left_behind(r, railed, github):
    engine = r.s("swept")
    copy_engine(railed, engine)
    shutil.rmtree(os.path.join(engine, ".git"), ignore_errors=True)
    write(os.path.join(engine, ".gitignore"), ENGINE_GITIGNORE)
    identity = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]
    with open(os.devnull, "wb") as null:
        check(run(["git", "-C", engine, "init", "-q", "-b", "main"]))
        check(run(["git", "-C", engine, *identity, "add", "-A"], stdout=null))
        check(run(["git", "-C", engine, *identity, "commit", "-qm", "produced"], stdout=null))

    roots = r.s("sweep-worktrees")
    env = dict(os.environ, RULES_ENGINE_GH=github.script, VALIDATE_ENGINE_FAKE_GH_STATE=github.state,
               RULES_ENGINE_WORKTREE_ROOT=roots)
    log = r.s("sweep.log")
    branch = f"issue-{ISSUE}-widen-the-altitude-limit"
    worktree = os.path.join(roots, branch)
    github.dispatchable(ISSUE, "Widen the altitude limit", ready(railed_policy(railed), "normalRisk"))
    if run_to(log, ["bash", "tools/dispatch-agent.sh", str(ISSUE)], cwd=engine, env=env, both=True) != 0:
        cat(log)
        fail("tools/dispatch-agent.sh could not open a worktree in a produced engine")
    if not os.path.isdir(worktree):
        cat(log)
        fail(f"dispatch reported success and there is no worktree at {worktree}")

    # Nothing has merged, and this worktree's branch tip IS main's tip: the case every weaker rule
    # than "a pull request merged at exactly this commit" gets wrong, by removing the worktree of
    # an agent who has not committed yet.
    if head_of(worktree) != head_of(engine):
        fail("a fresh worktree is not at main's tip, so the check below proves nothing")
    if run_to(log, ["bash", "tools/dispatch-agent.sh", "--sweep"], cwd=engine, env=env, both=True) != 0:
        cat(log)
        fail("the sweep did not exit 0 on a repository with nothing finished in it")
    if not grep_fixed(log, "sweep: nothing to remove"):
        cat(log)
        fail("the sweep removed nothing and did not say so: 'it refused' and 'it did nothing' must not read alike")
    if not os.path.isdir(worktree):
        fail("the sweep removed the worktree of an agent who had committed nothing")

    write(os.path.join(worktree, "note.txt"), "the work of this issue\n")
    with open(os.devnull, "wb") as null:
        check(run(["git", "-C", worktree, *identity, "add", "note.txt"], stdout=null))
        check(run(["git", "-C", worktree, *identity, "commit", "-qm", "the work of this issue"], stdout=null))
    github.merged([(branch, head_of(worktree))])

    # The doctor names it, and removes nothing: it is the report that makes a leftover visible
    # before anybody dispatches again. It runs without --local here, so the fake `gh` answers the
    # merged listing; the rest of the remote half is not this check's subject.
    doctor = r.s("sweep-doctor.log")
    github.tool(engine, doctor, "tools/agent-doctor.py")
    if not grep(doctor, r"^Leftovers from merged work .* 1 left over: .*\(worktree\)"):
        cat(doctor)
        fail("tools/agent-doctor.py did not report the worktree of a merged pull request as a leftover")
    if not os.path.isdir(worktree):
        fail("tools/agent-doctor.py removed a worktree; it reports and never acts")

    # The acceptance criterion: nobody has to remember. Dispatching #27 again finds its finished
    # worktree in the way, and would refuse -- except that dispatch sweeps before it creates one.
    finished = head_of(worktree)
    if run_to(log, ["bash", "tools/dispatch-agent.sh", str(ISSUE)], cwd=engine, env=env, both=True) != 0:
        cat(log)
        fail("dispatch refused because a merged issue's worktree was still in the way; it must sweep first")
    if not grep_fixed(log, f"swept    {worktree} ({branch}, its pull request merged at this tip)"):
        cat(log)
        fail("dispatch opened a worktree without saying it had swept the finished one")
    if not grep_fixed(log, f"swept    branch {branch} (its pull request merged at this tip)"):
        cat(log)
        fail("the sweep took the worktree and left its branch behind")
    if not os.path.isdir(worktree) or head_of(worktree) == finished:
        fail("the worktree at that path is the finished one: nothing was swept, or nothing was opened")

    # And a finished worktree with uncommitted work in it is named and left exactly where it is.
    write(os.path.join(worktree, "half-done.txt"), "not committed\n")
    github.merged([(branch, head_of(worktree))])
    if run_to(log, ["bash", "tools/dispatch-agent.sh", "--sweep"], cwd=engine, env=env, both=True) != 1:
        cat(log)
        fail("the sweep did not report a finished worktree it had refused to remove")
    if not grep_fixed(log, "it has uncommitted or untracked files; look at them before removing it"):
        cat(log)
        fail("the sweep kept a dirty worktree without saying why, which reads as a sweep that found nothing")
    if not os.path.isfile(os.path.join(worktree, "half-done.txt")):
        fail("the sweep removed a worktree with uncommitted work in it")
    ok("tools/dispatch-agent.sh --sweep removes a merged issue's worktree and branch before the next "
       "dispatch, keeps a fresh and a dirty one, and the doctor names what it would remove")


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


# A stand-in for `gh`, answering exactly the calls the emitted rails make and nothing else. The
# state -- pull requests, issues, the repository name and the commit statuses -- is one JSON file
# the checks below rewrite. A call it does not know, or a --json field the state does not hold, is
# an error rather than an empty answer: a rail whose `gh` call changed must fail these checks, not
# be fed a None it happens to tolerate.
FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys

path = os.environ["VALIDATE_ENGINE_FAKE_GH_STATE"]
with open(path, encoding="utf-8") as handle:
    state = json.load(handle)
argv = sys.argv[1:]


def refuse(why):
    sys.stderr.write(f"fake gh: {why}: gh {' '.join(argv)}\n")
    sys.exit(2)


def answer(record):
    if "--json" not in argv:
        refuse("no --json")
    wanted = argv[argv.index("--json") + 1].split(",")
    missing = [field for field in wanted if field not in record]
    if missing:
        refuse(f"no {', '.join(missing)} in the state")
    document = {field: record[field] for field in wanted}
    if "--jq" not in argv:
        print(json.dumps(document))
        return
    # Exactly the three expressions tools/dispatch-agent.sh writes, and no evaluator: a rail whose
    # call changed must fail here rather than be handed something that looks like an answer.
    expression = argv[argv.index("--jq") + 1]
    if expression in (".title", ".state"):
        print(document[expression[1:]])
    elif expression == '[.labels[].name] | join(",")':
        print(",".join(label["name"] for label in document["labels"]))
    else:
        refuse(f"a --jq expression the rails do not use: {expression}")


if argv[:2] in (["pr", "view"], ["issue", "view"]) and len(argv) > 2:
    record = state["pulls" if argv[0] == "pr" else "issues"].get(argv[2])
    if record is None:
        refuse(f"no {argv[0]} {argv[2]}")
    answer(record)
elif argv[:2] == ["repo", "view"]:
    answer({"nameWithOwner": state["repository"]})
elif argv[:1] == ["api"] and len(argv) > 1:
    prefix = f"repos/{state['repository']}/"
    route = argv[1]
    if route.startswith(prefix + "statuses/") and argv[2:4] == ["-X", "POST"]:
        fields = dict(argv[i + 1].split("=", 1) for i in range(len(argv) - 1) if argv[i] == "-f")
        sha = route[len(prefix + "statuses/"):]
        # Newest first, as GitHub's combined status lists them.
        state["statuses"].setdefault(sha, []).insert(0, {"context": fields["context"], "state": fields["state"]})
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        print("{}")
    elif route.startswith(prefix + "contents/") and "?ref=" in route:
        # The base commit's provenance.json, which pr-policy.py reads for a retired deletion (#243).
        body = state.get("contents", {}).get(route.split("?ref=", 1)[1])
        if body is None:
            refuse("no contents at that ref")
        print(json.dumps(body))
    elif route.startswith(prefix + "commits/") and route.endswith("/status"):
        sha = route[len(prefix + "commits/"):-len("/status")]
        print(json.dumps({"sha": sha, "statuses": state["statuses"].get(sha, [])}))
    elif route.startswith(prefix + "actions/workflows/") and "/runs?" in route:
        query = dict(pair.split("=", 1) for pair in route.split("?", 1)[1].split("&"))
        if query.get("event") != "pull_request":
            refuse("the runs query does not ask for the pull_request event")
        print(json.dumps({"workflow_runs": state.get("runs", {}).get(query.get("head_sha", ""), [])}))
    elif route.startswith(prefix + "actions/runs/") and route.endswith("/rerun") and argv[2:4] == ["-X", "POST"]:
        run = route[len(prefix + "actions/runs/"):-len("/rerun")]
        state.setdefault("reruns", []).append(run)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        print("{}")
    else:
        refuse("an api route the rails do not call")
elif argv[:2] == ["pr", "list"]:
    if "--state" not in argv:
        refuse("a pull request listing that does not say which state it wants")
    wanted = argv[argv.index("--json") + 1].split(",") if "--json" in argv else refuse("no --json")
    asked = argv[argv.index("--state") + 1]
    if asked == "open":
        listed = [pull for pull in state["pulls"].values() if pull.get("state") == "OPEN"]
    elif asked == "merged":
        # tools/dispatch-agent.sh --sweep and tools/agent-doctor.py's leftovers row (#236): what
        # merged, by head branch and head commit. Empty unless a check below puts something there.
        listed = state.get("merged") or []
    else:
        refuse(f"a pull request listing for state {asked}")
    print(json.dumps([{field: pull[field] for field in wanted} for pull in listed]))
else:
    refuse("a command the rails do not call")
'''

PR = "5"
ISSUE = 27
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
# A commit no open pull request heads: #191's second acceptance criterion is about this one.
COMMIT_STRANGER = "c" * 40
# The commit a pull request is based on: pr-policy.py reads its provenance.json when the diff holds
# a path under a retired pattern (#243).
COMMIT_BASE = "d" * 40
GATE_RUN = 4242

# A pull request filled the way the emitted template asks: every section, one `Closes`, a command
# and its output, a mutation, and who implemented and reviewed. If the contract rejects this, the
# rejection of the malformed body below proves nothing about the body.
WELL_FORMED_PR_BODY = f"""## Linked issue

Closes #{ISSUE}

## Exact behavioural claim

`PlayerCount` answers two, citing the corpus, where it declined before.

## Scope, and what this deliberately does not do

Only the player count. No other entry is touched.

## Map and rules conformance

- entry id(s): player-count
- map package and version: the package this engine was produced from
- source locator(s): the locator the entry packet names
- owner's rulings used, if any: none

## Tests and evidence

```
$ ./scripts/validate.sh full
ok   test Release
validate.sh full: PASS
```

Mutations observed: `PlayerCount_IsTwo` fails with the mutation "answer three" (observed).

## Documentation

None: this engine has no documents of its own, and nothing here changes one.

## Determinism

Nothing here reads the machine.

## Decisions and trade-offs

None beyond the entry's own evidence.

## Known limitations and unresolved behaviour

None.

## Agent provenance

- implemented by: engine-dev
- structurally reviewed by: repo-steward
- semantically reviewed by: rules-conformance
- independently reviewed by: not required

## Unrelated changes

None
"""


class FakeGitHub:
    """The stand-in's script and state, and the rails run against it in a produced engine."""

    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True)
        self.script = os.path.join(directory, "gh")
        self.state = os.path.join(directory, "state.json")
        write(self.script, FAKE_GH)
        os.chmod(self.script, 0o755)

    def serve(self, railed, head, labels, body=WELL_FORMED_PR_BODY):
        """One open pull request at `head`, touching the semantic surface, closing one issue with `labels`.

        The commit statuses start empty: each check records its own verdicts through record-verdict.py.
        `runs` is the conformance-gate run GitHub holds at that head -- there is one as soon as a
        pull request is opened -- and `reruns` the re-requests the rails make of it, which start none."""
        changed = [{"path": f"src/{NAME}/Rules/PlayerCount.cs", "changeType": "MODIFIED"}]
        document = {
            "repository": "owner/engine",
            # `baseRefOid` and `changeType` are what pr-policy.py reads to decide whether a deletion
            # under a retired pattern is the factory's (#243); `contents` is the base commit's
            # provenance.json, which nothing here asks for until a test puts a retired path in the diff.
            "pulls": {PR: {"number": int(PR), "title": "Implement the player count", "body": body, "state": "OPEN",
                           "headRefOid": head, "baseRefOid": COMMIT_BASE, "files": changed,
                           "changedFiles": len(changed),
                           "closingIssuesReferences": [{"number": ISSUE}]}},
            "issues": {str(ISSUE): {"number": ISSUE, "state": "OPEN", "labels": [{"name": name} for name in labels]}},
            "statuses": {},
            "runs": {head: [{"id": GATE_RUN, "run_number": 1, "status": "completed", "conclusion": "failure"}]},
            "reruns": [],
        }
        write(self.state, json.dumps(document, indent=2))

    def dispatchable(self, number, title, labels, merged=()):
        """An issue `tools/dispatch-agent.sh` can open a worktree for, and what has merged (#236).

        A state of its own rather than `serve`'s: dispatch reads an issue's title, which a pull
        request's fixture has no reason to carry, and the sweep reads a listing `serve` has none of.
        """
        document = {
            "repository": "owner/engine",
            "pulls": {},
            "issues": {str(number): {"number": number, "state": "OPEN", "title": title,
                                     "labels": [{"name": name} for name in labels]}},
            "statuses": {}, "runs": {}, "reruns": [],
            "merged": [{"headRefName": branch, "headRefOid": head} for branch, head in merged],
        }
        write(self.state, json.dumps(document, indent=2))

    def merged(self, pairs):
        """The merged pull requests, as (head branch, head commit), leaving the rest of the state."""
        with open(self.state, encoding="utf-8") as handle:
            document = json.load(handle)
        document["merged"] = [{"headRefName": branch, "headRefOid": head} for branch, head in pairs]
        write(self.state, json.dumps(document, indent=2))

    def reruns(self):
        with open(self.state, encoding="utf-8") as handle:
            return json.load(handle).get("reruns") or []

    def files(self, paths):
        """The pull request's changed files, and GitHub's own count of them.

        Both, because `changedFiles` is what tells a rail that `files` was truncated at a hundred
        (#193); a mutator that set only the list would make the two disagree and every check that
        reads the diff would refuse.
        """
        with open(self.state, encoding="utf-8") as handle:
            document = json.load(handle)
        document["pulls"][PR]["files"] = [{"path": path, "changeType": "MODIFIED"} for path in paths]
        document["pulls"][PR]["changedFiles"] = len(paths)
        write(self.state, json.dumps(document, indent=2))

    def body(self, text):
        with open(self.state, encoding="utf-8") as handle:
            document = json.load(handle)
        document["pulls"][PR]["body"] = text
        write(self.state, json.dumps(document, indent=2))

    def move_head(self, head):
        """A further commit pushed to the pull request: the statuses stay on the commits they were recorded at."""
        with open(self.state, encoding="utf-8") as handle:
            document = json.load(handle)
        document["pulls"][PR]["headRefOid"] = head
        write(self.state, json.dumps(document, indent=2))

    def tool(self, railed, log, *command):
        """An emitted rail, run in the produced engine against the stand-in; its exit code, its output in `log`."""
        env = dict(os.environ, RULES_ENGINE_GH=self.script, VALIDATE_ENGINE_FAKE_GH_STATE=self.state)
        return run_to(log, [PYTHON, *command], cwd=railed, env=env, both=True)

    def review_identity(self, railed):
        """A packet identity for the fake PR head, carrying the produced engine's exact review context.

        The fake GitHub uses synthetic commit ids so review-packet.py cannot make a real detached
        worktree for them. review-packet.py itself is exercised in the Python rail tests; this
        engine smoke test needs the recorder's real format and exact-head discipline.
        """
        with open(self.state, encoding="utf-8") as handle:
            state = json.load(handle)
        head = state["pulls"][PR]["headRefOid"]

        packet_dir = os.path.join(os.path.dirname(self.state), "review-packets")
        os.makedirs(packet_dir, exist_ok=True)
        human = os.path.join(packet_dir, f"pr-{PR}-{head[:12]}.md")
        write(human, f"# Review packet\n\nHead commit `{head}`.\n")

        policy_path = os.path.join(railed, ".github", "agent-policy.json")
        provenance_path = os.path.join(railed, "provenance.json")
        with open(policy_path, "rb") as handle:
            policy_bytes = handle.read()
        with open(provenance_path, "rb") as handle:
            provenance_bytes = handle.read()
        policy = json.loads(policy_bytes)
        provenance = json.loads(provenance_bytes)

        identity = {
            "reviewPacketFormat": 1,
            "pullRequest": int(PR),
            "reviewedCommit": head,
            "baseCommit": COMMIT_BASE,
            "reviewPacket": {
                "path": os.path.basename(human),
                "sha256": hashlib.sha256(open(human, "rb").read()).hexdigest(),
            },
            "reviewContext": {
                "policy": {
                    "path": ".github/agent-policy.json",
                    "sha256": hashlib.sha256(policy_bytes).hexdigest(),
                    "semanticContext": policy["review"]["semanticContext"],
                    "independentFallback": policy["review"]["independentFallback"],
                },
                "provenance": {
                    "path": "provenance.json",
                    "sha256": hashlib.sha256(provenance_bytes).hexdigest(),
                },
                "map": {
                    "packageId": provenance["map"]["packageId"],
                    "version": provenance["map"]["version"],
                    "nupkgSha256": provenance["map"].get("nupkgSha256", ""),
                },
            },
            "entryPackets": [],
        }
        path = os.path.join(packet_dir, f"pr-{PR}-{head[:12]}.review.json")
        write(path, json.dumps(identity, indent=2) + "\n")
        return path

    def record(self, railed, log, reviewer):
        packet = self.review_identity(railed)
        if self.tool(railed, log, "tools/record-verdict.py", "--pr", PR, "--packet", packet,
                     "--reviewer", reviewer, "--verdict", "pass") != 0:
            cat(log)
            fail(f"tools/record-verdict.py could not record a pass by {reviewer} in a produced engine")

    def gate(self, railed, log):
        return self.tool(railed, log, "tools/conformance-gate.py", PR)


def railed_policy(railed):
    with open(os.path.join(railed, ".github", "agent-policy.json"), encoding="utf-8") as handle:
        return json.load(handle)


def ready(policy, risk):
    """An issue's labels: the policy's ready state, and its `risk` label -- by the policy's names, not by literals."""
    return [policy["labels"]["ready"], policy["labels"][risk]]


# The pull request contract (#157): the engine's own template, opened and left as it is, is refused
# by the engine's own tools/pr-policy.py, which names what is missing. The well-formed body is
# accepted first, against the same issue and the same stand-in, so the refusal is about the body.
def a_malformed_pull_request_is_refused_by_the_contract(r, railed, github):
    policy = railed_policy(railed)
    log = r.s("pr-policy.log")
    github.serve(railed, COMMIT_A, ready(policy, "normalRisk"))
    if github.tool(railed, log, "tools/pr-policy.py", PR) != 0 or not grep_fixed(log, "satisfies the contract"):
        cat(log)
        fail("tools/pr-policy.py refused a well-formed pull request, so its refusals prove nothing")
    with open(os.path.join(railed, ".github", "pull_request_template.md"), encoding="utf-8") as handle:
        template = handle.read()
    github.serve(railed, COMMIT_A, ready(policy, "normalRisk"), body=template)
    if github.tool(railed, log, "tools/pr-policy.py", PR) != 1:
        cat(log)
        fail("tools/pr-policy.py did not refuse a pull request body left as the template")
    for text, message in (("does not satisfy the contract", "tools/pr-policy.py exited 1 without refusing the contract"),
                          ("no `Closes #<n>`", "tools/pr-policy.py did not name the missing `Closes #<n>`"),
                          ("`## Exact behavioural claim` is empty", "tools/pr-policy.py did not name the empty sections"),
                          # #236: the section is the engine's own, and an unfilled template leaves
                          # it as guidance, which is not an answer about any document.
                          ("`## Documentation` is empty", "tools/pr-policy.py did not name the empty documentation "
                           "section, so a pull request that accounts for no document passes")):
        if not grep_fixed(log, text):
            cat(log)
            fail(message)

    # And the section is held to the diff, not merely required: a document this engine owns, added
    # in the branch and left out of the listing, is named. `README.md` is a hand-written file in a
    # produced engine -- the factory emits none -- so it is exactly the case the living-document
    # rule is for, and the rails the factory does write are not asked about.
    write(os.path.join(railed, "README.md"), "# The engine\n")
    github.serve(railed, COMMIT_A, ready(policy, "normalRisk"))
    refused = github.tool(railed, log, "tools/pr-policy.py", PR)
    os.remove(os.path.join(railed, "README.md"))
    if refused != 1:
        cat(log)
        fail("tools/pr-policy.py accepted a pull request that left this engine's own README unaccounted for")
    if not grep_fixed(log, "`README.md` is a living document of this engine and is not listed"):
        cat(log)
        fail("tools/pr-policy.py refused for some other reason than the unlisted document")
    if grep_fixed(log, "`AGENTS.md` is a living document"):
        cat(log)
        fail("tools/pr-policy.py asked this engine to account for a rail the factory writes and it may not edit")
    ok("tools/pr-policy.py refuses the template left unfilled, naming what is missing, accepts it filled, and "
       "names this engine's own document left out of `## Documentation`")


# A verdict is on the bytes somebody read (#157). Recorded by the engine's record-verdict.py at the
# head A, it satisfies the engine's conformance-gate.py at A; one more commit moves the head to B,
# the status stays on A, and the same gate now blocks -- with nothing having had to notice.
def a_verdict_at_one_commit_does_not_pass_another(r, railed, github):
    policy = railed_policy(railed)
    log = r.s("verdict-at-sha.log")
    github.serve(railed, COMMIT_A, ready(policy, "normalRisk"))
    github.record(railed, log, "semantic")
    if github.gate(railed, log) != 0:
        cat(log)
        fail(f"a semantic verdict recorded at the head {COMMIT_A[:12]} did not satisfy the gate there")
    github.move_head(COMMIT_B)
    if github.gate(railed, log) != 1:
        cat(log)
        fail(f"a verdict recorded at {COMMIT_A[:12]} satisfied the gate with the head at {COMMIT_B[:12]}")
    if not grep_fixed(log, f"{policy['review']['semanticContext']} is not recorded as a success at {COMMIT_B[:12]}"):
        cat(log)
        fail("the gate blocked a moved head for some other reason than the missing verdict at the new head")
    ok("a verdict recorded at one commit satisfies tools/conformance-gate.py there, and not at the next")


# An issue the policy labels for independent review (#157): the semantic verdict alone does not
# satisfy the gate, and a success from the first link of the configured chain then does.
def an_independent_risk_issue_needs_more_than_the_semantic_verdict(r, railed, github):
    policy = railed_policy(railed)
    chain = policy["review"]["independentFallback"]
    log = r.s("independent-risk.log")
    github.serve(railed, COMMIT_A, ready(policy, "independentRisk"))
    github.record(railed, log, "semantic")
    if github.gate(railed, log) != 1:
        cat(log)
        fail(f"an issue labelled {policy['labels']['independentRisk']} passed the gate on the semantic verdict alone")
    if not grep_fixed(log, f"one of {' or '.join(link['context'] for link in chain)} must also be recorded as a success"):
        cat(log)
        fail("the gate blocked an independent-risk issue without naming the independent chain it needs")
    github.record(railed, log, chain[0]["id"])
    if github.gate(railed, log) != 0:
        cat(log)
        fail(f"an independent verdict at {chain[0]['context']} did not satisfy the gate beside the semantic one")
    ok("an independent-risk issue is not satisfied by the semantic verdict alone, and is with the chain's")


# --- the emitted workflows, read and dispatched -------------------------------------------------
#
# #157's checks called tools/conformance-gate.py directly, so nothing had ever read the workflow
# that runs it -- which is where #191's defect lived: a `status:` trigger whose only job was gated
# to `pull_request` events, so recording a verdict re-ran nothing and the required check stayed
# red. What follows is the smallest thing that can see that class of defect: the emitted workflow's
# own triggers, job conditions, step environments and commands, read from the file the engine
# received, and the command run with the variable names the YAML binds. Rename VERDICT_SHA in the
# workflow and not in the script, or the other way round, and this fails.
#
# It reads lines, not YAML: the standard library has no YAML parser, and tools/check-workflow-pins.py
# sets the precedent of saying so rather than adding a dependency to the factory. It therefore
# understands exactly the shape the factory emits -- one `on:` block of bare triggers, jobs at one
# indent, steps with an `env:` map and a one-line `run:` -- and fails loudly where it cannot tell.
JOB_IF = re.compile(r"^github\.event_name == '([a-z_]+)'$")
EXPRESSION = re.compile(r"^\$\{\{\s*(.+?)\s*\}\}$")
STATUS_PAYLOAD_FIELDS = ("sha", "context", "state")


def read_workflow(path):
    """{"triggers": [...], "jobs": {name: {"if": str|None,
                                          "steps": [{"env": {}, "run": str|None, "if": str|None}]}}}."""
    triggers, jobs = [], {}
    section, job, step, env_indent = None, None, None, None
    for line in read_lines(path):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            section, job, step, env_indent = text.rstrip(":"), None, None, None
        elif section == "on" and indent == 2:
            triggers.append(text.rstrip(":"))
        elif section == "jobs" and indent == 2:
            job, step, env_indent = text.rstrip(":"), None, None
            jobs[job] = {"if": None, "steps": []}
        elif section == "jobs" and job and indent == 4 and text.startswith("if:"):
            jobs[job]["if"] = text[len("if:"):].strip()
        elif section == "jobs" and job and indent == 6 and text.startswith("- "):
            step, env_indent = {"env": {}, "run": None, "if": None}, None
            jobs[job]["steps"].append(step)
        elif step is not None and indent == 8:
            env_indent = 10 if text == "env:" else None
            if text.startswith("run:"):
                step["run"] = text[len("run:"):].strip()
            # A step's own condition, which a workflow with two triggers needs (#230). Read here
            # rather than assumed absent: a step condition this parser did not see is a step the
            # dispatch below would run for the wrong event, with the wrong payload.
            elif text.startswith("if:"):
                step["if"] = text[len("if:"):].strip()
        elif step is not None and env_indent is not None and indent == env_indent and ": " in text:
            key, value = text.split(": ", 1)
            step["env"][key] = value
    return {"triggers": triggers, "jobs": jobs}


def jobs_selected(workflow, event_name, path):
    """The jobs a `event_name` run would actually execute, by each job's `if:`."""
    selected = []
    for name, job in workflow["jobs"].items():
        if job["if"] is None:
            selected.append(name)
            continue
        found = JOB_IF.fullmatch(job["if"])
        if not found:
            # An undecidable check fails. Saying "no job matched" here would read as a pass.
            fail(f"{path}: this check understands one form of `if:`, `github.event_name == '<x>'`; the job "
                 f"{name} now uses another ({job['if']!r}), so it cannot tell whether the job runs")
        if found.group(1) == event_name:
            selected.append(name)
    return selected


def steps_selected(job, event_name, path):
    """The job's steps that run for `event_name`.

    The job's own `if:` is the one #191 turned on, and jobs_selected above reads it. A *step* may
    carry one too, and must once a workflow has two triggers: verdict-requeue.yml now answers
    `status` and `issues`, and each step reads a payload the other event does not carry (#230).
    A step with no condition runs for both, as the checkout does.
    """
    selected = []
    for step in job["steps"]:
        condition = step.get("if")
        if condition is None:
            selected.append(step)
            continue
        found = JOB_IF.fullmatch(condition)
        if not found:
            # An undecidable check fails, for the same reason jobs_selected says so.
            fail(f"{path}: this check understands one form of step `if:`, `github.event_name == '<x>'`; a step "
                 f"of {job.get('name') or 'this job'} now uses another ({condition!r}), so it cannot tell "
                 f"whether the step runs")
        if found.group(1) == event_name:
            selected.append(step)
    return selected


def step_environment(step, payload, path):
    """The step's `env:` map with each `${{ }}` resolved against the event payload."""
    env = {}
    for key, value in step["env"].items():
        found = EXPRESSION.fullmatch(value)
        if not found:
            fail(f"{path}: {key} is {value!r}, which this check cannot resolve; it understands `${{{{ ... }}}}`")
        expression = found.group(1)
        if expression == "github.token":
            env[key] = "fake-token-the-stand-in-ignores"
        elif expression.startswith("github.event."):
            field = expression[len("github.event."):]
            if field not in payload:
                fail(f"{path}: {key} reads {expression}, and this payload carries "
                     f"{', '.join(sorted(payload))}. A step reading another event's fields needs an "
                     f"`if: github.event_name == '<x>'` saying which event it is for")
            env[key] = payload[field]
        else:
            fail(f"{path}: {key} reads {expression}, which this check cannot synthesise for this event")
    return env


def dispatch_status(railed, github, workflow, payload, log, path):
    """Deliver a `status` event to the emitted workflow: its jobs' steps, run as the YAML declares them.

    The command and the variable names are the workflow's own, so this is the wiring under test and
    not a paraphrase of it."""
    if "status" not in workflow["triggers"]:
        fail(f"{path} does not trigger on `status`, so a recorded verdict reaches nothing")
    selected = jobs_selected(workflow, "status", path)
    if selected != ["verdict-requeue"]:
        fail(f"{path}: a status event selects {selected or 'no job'}; #191 was this job being skipped, and a job "
             f"named conformance-gate here would report the required check onto the default branch's commit")
    code = 0
    for name in selected:
        for step in steps_selected(workflow["jobs"][name], "status", path):
            if not step["run"]:
                continue
            env = dict(os.environ, RULES_ENGINE_GH=github.script, VALIDATE_ENGINE_FAKE_GH_STATE=github.state,
                       **step_environment(step, payload, path))
            code = run_to(log, ["bash", "-c", step["run"]], cwd=railed, env=env, both=True)
            if code != 0:
                return code
    return code


def status_payload(sha, context, state):
    return {"sha": sha, "context": context, "state": state}


def issues_payload(number, label, action):
    """What GitHub delivers for `issues: [labeled, unlabeled]`, as the workflow reads it."""
    return {"issue.number": str(number), "label.name": label, "action": action}


def dispatch_issues(railed, github, workflow, payload, log, path):
    """Deliver an `issues` event to the emitted workflow, the way dispatch_status does a status.

    The same job, selected by its own `if:` (it has none), and the steps that event selects."""
    if "issues" not in workflow["triggers"]:
        fail(f"{path} does not trigger on `issues`, so a risk label changed after the gate passed reaches "
             f"nothing and the required check keeps an answer the issue no longer supports (#230)")
    selected = jobs_selected(workflow, "issues", path)
    if selected != ["verdict-requeue"]:
        fail(f"{path}: an issues event selects {selected or 'no job'}")
    code = 0
    for name in selected:
        steps = steps_selected(workflow["jobs"][name], "issues", path)
        if not [step for step in steps if step["run"]]:
            fail(f"{path}: an issues event selects no step that runs anything, so the trigger is decoration")
        for step in steps:
            if not step["run"]:
                continue
            env = dict(os.environ, RULES_ENGINE_GH=github.script, VALIDATE_ENGINE_FAKE_GH_STATE=github.state,
                       **step_environment(step, payload, path))
            code = run_to(log, ["bash", "-c", step["run"]], cwd=railed, env=env, both=True)
            if code != 0:
                return code
    return code


# Risk is the orchestrator's call and may be made at any time (0029). The gate reads it from the
# linked issue and runs on `pull_request` events, so raising it after the gate passed left a green
# required check that no longer reflected the issue's risk, and the pull request could merge
# without the independent verdict it now needed (#230). The whole chain, in the produced engine:
# the gate passes at normal risk, the label is raised, the emitted workflow is dispatched the
# `issues` event that would cause, its own command re-requests the gate's run, and the gate -- the
# run that would execute -- then refuses until the independent verdict is recorded.
#
# **What this cannot prove**, as for the verdict half: that GitHub delivers the `issues` event at
# all, and that the re-run's check run supersedes the green one for the ruleset. Both are GitHub's
# behaviour rather than the engine's.
def a_late_risk_label_re_runs_the_gate(r, railed, github):
    workflows = os.path.join(railed, ".github", "workflows")
    requeue_path = os.path.join(workflows, "verdict-requeue.yml")
    requeue = read_workflow(requeue_path)
    policy = railed_policy(railed)
    # The reviewer the policy configures, by its id, not a literal: "independent" is not a
    # reviewer, and record-verdict.py rightly refuses one the reviewed packet does not name.
    chain = policy["review"]["independentFallback"]
    log = r.s("risk-requeue.log")

    # Normal risk, the semantic verdict recorded: the gate passes, and the pull request may merge.
    github.serve(railed, COMMIT_A, ready(policy, "normalRisk"))
    github.record(railed, log, "semantic")
    if github.gate(railed, log) != 0:
        cat(log)
        fail("the gate did not pass at normal risk with the semantic verdict recorded, so nothing below "
             "would prove that raising risk changed the answer")

    # The orchestrator raises risk on the issue. No commit changed, and no pull_request event.
    github.serve(railed, COMMIT_A, ready(policy, "independentRisk"))
    before = list(github.reruns())
    if dispatch_issues(railed, github, requeue,
                       issues_payload(ISSUE, policy["labels"]["independentRisk"], "labeled"),
                       log, requeue_path) != 0:
        cat(log)
        fail("the workflow's own command failed on the issues event raising the risk label causes")
    if github.reruns() != before + [str(GATE_RUN)]:
        cat(log)
        fail(f"raising the risk label re-requested {github.reruns()[len(before):] or 'no run'}, not the gate's "
             f"run {GATE_RUN} at the head of the pull request that closes the issue; without that the required "
             f"check keeps its green answer (#230)")

    # And the re-requested run is the point: it now refuses.
    if github.gate(railed, log) != 1:
        cat(log)
        fail("the gate still passes after the issue was labelled independent-review, so the required check "
             "would stay green and the pull request could merge without the independent verdict")
    github.record(railed, log, chain[0]["id"])
    if github.gate(railed, log) != 0:
        cat(log)
        fail("the gate does not pass once the independent verdict is recorded, so raising risk blocks a "
             "pull request nothing can clear")

    # A label the gate does not read re-runs nothing: the filter is the argument, not a precaution
    # on top of it, exactly as the verdict half's context filter is.
    before = list(github.reruns())
    if dispatch_issues(railed, github, requeue, issues_payload(ISSUE, "documentation", "labeled"),
                       log, requeue_path) != 0:
        cat(log)
        fail("a label that is not the risk label failed the requeue instead of being ignored")
    if github.reruns() != before:
        fail(f"{len(github.reruns()) - len(before)} run(s) were re-requested by a label the gate does not "
             f"read; that would re-run the gate on anything that moves")
    ok("raising the risk label on the linked issue re-runs the gate, which then refuses until the "
       "independent verdict is recorded, and a label the gate does not read re-runs nothing")


# Recording a verdict turns the required check green with no manual step (#191, acceptance
# criterion 1), and a verdict on a commit no open pull request heads produces a failing check
# nowhere (criterion 2). The whole chain, in the engine the factory produced: the emitted
# record-verdict.py writes the status, the emitted verdict-requeue.yml is dispatched the `status`
# event that status would cause, its own command re-requests the gate's run, and the emitted
# conformance-gate.py -- which that run would execute -- then passes.
#
# **What this cannot prove.** That GitHub delivers the `status` event to the workflow at all; that
# `actions: write` is the permission the re-run POST needs; and that the check run the re-run
# produces supersedes the failed one for the ruleset, so the pull request stops being BLOCKED. All
# three are GitHub's behaviour, not the engine's, and the evidence for them is the live #157 run.
def the_verdict_re_runs_the_gate(r, railed, github):
    workflows = os.path.join(railed, ".github", "workflows")
    requeue_path = os.path.join(workflows, "verdict-requeue.yml")
    gate_path = os.path.join(workflows, "conformance-gate.yml")
    requeue, gate_workflow = read_workflow(requeue_path), read_workflow(gate_path)
    if "status" in gate_workflow["triggers"]:
        fail("the conformance-gate workflow triggers on `status`, whose run belongs to the default branch's "
             "commit: that is how #191 painted the required check's name onto a commit nobody heads")
    if "conformance-gate" not in jobs_selected(gate_workflow, "pull_request", gate_path):
        fail("a pull_request event selects no conformance-gate job, so the required check has no producer")

    policy = railed_policy(railed)
    semantic = policy["review"]["semanticContext"]
    log = r.s("verdict-requeue.log")
    github.serve(railed, COMMIT_A, ready(policy, "normalRisk"))
    if github.gate(railed, log) != 1:
        cat(log)
        fail("the gate passed before any verdict was recorded, so nothing here would prove a re-run was needed")

    github.record(railed, log, "semantic")
    if dispatch_status(railed, github, requeue, status_payload(COMMIT_A, semantic, "success"), log,
                       requeue_path) != 0:
        cat(log)
        fail("the verdict-requeue workflow's own command failed on the status event a recorded verdict causes")
    if github.reruns() != [str(GATE_RUN)]:
        cat(log)
        fail(f"the recorded verdict re-requested {github.reruns() or 'no run'}, not the gate's run {GATE_RUN} "
             f"at the head it names")
    # No status and no check run of the required check's name, ever: a status would stand beside the
    # failed check run rather than replace it, and a second check run of that name is ambiguous. The
    # stand-in refuses every route but the three the rails call, so a check run would have failed the
    # dispatch above; what is asserted here is the commit's statuses, which it does serve.
    with open(github.state, encoding="utf-8") as handle:
        recorded = json.load(handle)["statuses"][COMMIT_A]
    if [status["context"] for status in recorded] != [semantic]:
        fail(f"the requeue wrote {[s['context'] for s in recorded]} at {COMMIT_A[:12]}; it must write no status "
             f"of its own, least of all one named conformance-gate")
    if github.gate(railed, log) != 0:
        cat(log)
        fail("the re-requested gate run does not pass at the commit the verdict names, so the chain from "
             "recording a verdict to a green required check is still broken")

    # A verdict on a commit no open pull request heads: nothing to re-run, and nothing red anywhere.
    before = list(github.reruns())
    if dispatch_status(railed, github, requeue, status_payload(COMMIT_STRANGER, semantic, "success"), log,
                       requeue_path) != 0:
        cat(log)
        fail(f"a status on {COMMIT_STRANGER[:12]}, which no open pull request heads, failed; a failing check "
             f"on a commit nobody heads is exactly what #191's second criterion forbids")
    if not grep_fixed(log, f"no open pull request heads {COMMIT_STRANGER}"):
        cat(log)
        fail("the requeue passed on a commit nobody heads without saying which commit it was asked about")

    # A status somebody else's service wrote, and a verdict still being formed: neither is a verdict
    # recorded at a head, and neither may re-run anything.
    for context, state, why in ((f"ci/{NAME.lower()}-coverage", "success", "a status that is not a verdict"),
                                (semantic, "pending", "a verdict that has not concluded")):
        if dispatch_status(railed, github, requeue, status_payload(COMMIT_A, context, state), log,
                           requeue_path) != 0:
            cat(log)
            fail(f"{why} failed the requeue instead of being ignored")
    if github.reruns() != before:
        fail(f"{len(github.reruns()) - len(before)} run(s) were re-requested by a status that is no recorded "
             f"verdict; the context filter is what keeps this from re-running the gate on anything that moves")
    ok("a recorded verdict re-runs the gate through the emitted workflow, and a status on a commit nobody "
       "heads re-runs nothing")


def tree_hashes(directory):
    """relative path -> sha256, for every file under `directory` but .git."""
    found = {}
    for parent, directories, files in os.walk(directory):
        directories[:] = [d for d in directories if not (parent == directory and d == ".git")]
        for name in files:
            path = os.path.join(parent, name)
            if not os.path.islink(path):
                found[os.path.relpath(path, directory)] = sha256(path)
    return found


# The provider chain is configuration (decision 0029, #157). Swapping it is an edit to
# .github/agent-policy.json and to nothing else: every other file in the engine hashes the same
# after, and the engine's own record-verdict.py and conformance-gate.py read the new chain -- the old
# ids are no longer reviewers, an old context's success no longer satisfies the gate, and the new
# one does.
def swapping_the_provider_chain_is_an_edit_to_the_policy_alone(r, railed, github):
    policy_path = os.path.join(railed, ".github", "agent-policy.json")
    policy = railed_policy(railed)
    old = policy["review"]["independentFallback"]
    new = [{"id": "swapped-first", "context": "rules-verdict/swapped-first"},
           {"id": "swapped-second", "context": "rules-verdict/swapped-second"}]
    if {link["id"] for link in old} & {link["id"] for link in new} or {link["context"] for link in old} & {link["context"] for link in new}:
        fail("the swapped chain shares an id or a context with the emitted one, so the swap would prove nothing")
    before = tree_hashes(railed)
    policy["review"]["independentFallback"] = new
    write(policy_path, json.dumps(policy, indent=2) + "\n")
    after = tree_hashes(railed)
    changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    if changed != [os.path.join(".github", "agent-policy.json")]:
        fail(f"swapping the provider chain changed {', '.join(changed) or 'nothing'}, not .github/agent-policy.json alone")

    log = r.s("provider-swap.log")
    github.serve(railed, COMMIT_A, ready(policy, "independentRisk"))
    if github.tool(railed, log, "tools/record-verdict.py", "--pr", PR, "--reviewer", old[0]["id"], "--verdict", "pass") != 1:
        cat(log)
        fail(f"tools/record-verdict.py still records for {old[0]['id']}, which the swapped policy no longer names")
    github.record(railed, log, "semantic")
    # The old chain's context, recorded as a success at the head as though the rail had never changed.
    with open(github.state, encoding="utf-8") as handle:
        document = json.load(handle)
    document["statuses"][COMMIT_A].insert(0, {"context": old[0]["context"], "state": "success"})
    write(github.state, json.dumps(document, indent=2))
    if github.gate(railed, log) != 1:
        cat(log)
        fail(f"a success at {old[0]['context']}, dropped from the chain, still satisfied tools/conformance-gate.py")
    if not grep_fixed(log, f"one of {' or '.join(link['context'] for link in new)} must also be recorded"):
        cat(log)
        fail("tools/conformance-gate.py did not name the swapped chain's contexts; it is not reading the policy")
    github.record(railed, log, new[0]["id"])
    if github.gate(railed, log) != 0:
        cat(log)
        fail(f"a success at the swapped chain's {new[0]['context']} did not satisfy tools/conformance-gate.py")
    ok("swapping the provider chain edits .github/agent-policy.json alone, and the gate requires the new contexts")


# A `factory produce` update's pull request, as the emitted template asks for it. The three declared
# facts are filled in from the engine's own provenance.json at the moment of the check: they are the
# claim, and the whole point of the claim is that the tree can contradict it.
PRODUCE_PR_BODY = WELL_FORMED_PR_BODY.replace("""- entry id(s): player-count
- map package and version: the package this engine was produced from
- source locator(s): the locator the entry packet names
- owner's rulings used, if any: none""", "- map package and version: {map}").replace(
    """Mutations observed: `PlayerCount_IsTwo` fails with the mutation "answer three" (observed).""",
    """```
$ python3 tools/factory produce --package ... --name ... --out .
produced in ., verified
$ python3 tools/factory provenance --engine .
provenance of .: every field matches
```""").replace("## Exact behavioural claim", """## Produced by the factory

<!-- rules-factory-produce -->

- factory version: {factory}
- map package and version: {map}
- kernel version: {kernel}
- what moved: the map, from the version before this one

## Exact behavioural claim""")


# The predicate #193 decided, run against a real produced tree and the engine's own vendored
# ownership table. tools/tests/factory/test_factory_rails.py proves the logic in depth against the recipe
# bytes; what only this can prove is that the file set a real `produce` wrote classifies as the
# factory's in the engine that received it -- a fixture of invented path strings would agree with
# itself whatever the table said.
def a_factory_update_is_checked_against_the_tree_that_produced_it(r, railed, github):
    policy = railed_policy(railed)
    log = r.s("produce-claim.log")
    with open(os.path.join(railed, "provenance.json"), encoding="utf-8") as handle:
        record = json.load(handle)
    if record["factory"]["dirty"] is not False:
        fail("the produced engine's record says the factory was dirty, so no produce claim could be admitted")
    body = PRODUCE_PR_BODY.format(factory=record["factory"]["version"],
                                  map=f"{record['map']['packageId']} {record['map']['version']}",
                                  kernel=record["kernel"]["version"])
    # Drawn from the record rather than listed here: these are the paths this produce wrote.
    written = ["provenance.json"] + [item["path"] for item in record["generated"]]

    github.serve(railed, COMMIT_A, ready(policy, "normalRisk"), body=body)
    github.files(written)
    if github.tool(railed, log, "tools/pr-policy.py", PR) != 0:
        cat(log)
        fail("tools/pr-policy.py refused a factory update whose every changed file this engine's own "
             "provenance.json records as produced, so its refusal below would prove nothing")
    if not grep_fixed(log, "claim was admitted"):
        cat(log)
        fail("tools/pr-policy.py passed the factory update without saying the produce claim was admitted")

    # One hand-written file among them. Nothing else changes: the same body, the same engine, the
    # same declared facts -- and the claim is void, by name. This is the escape hatch, closed.
    smuggled = f"src/{NAME}/Rules/SmuggledByHand.cs"
    github.files(written + [smuggled])
    if github.tool(railed, log, "tools/pr-policy.py", PR) != 1:
        cat(log)
        fail(f"tools/pr-policy.py admitted a produce claim over a diff carrying {smuggled}, which no produce writes")
    for text, message in ((smuggled, "the refusal does not name the hand-written file that voided the claim"),
                          ("not files a produce writes", "the refusal does not say why the claim is void"),
                          ("names no mutation", "the voided pull request was not judged as the ordinary one it is")):
        if not grep_fixed(log, text):
            cat(log)
            fail(message)

    # And the claim buys no verdict: the same diff, which regenerates the map's code, still needs
    # the semantic verdict at the head, and gets it only when one is recorded there.
    github.files(written)
    if github.gate(railed, log) != 1:
        cat(log)
        fail("tools/conformance-gate.py passed a regeneration with no verdict recorded; the produce claim waived it")
    if not grep_fixed(log, f"{policy['review']['semanticContext']} is not recorded as a success at {COMMIT_A[:12]}"):
        cat(log)
        fail("the gate blocked the factory update for some other reason than the missing semantic verdict")
    github.record(railed, log, "semantic")
    if github.gate(railed, log) != 0:
        cat(log)
        fail("a semantic verdict at the head did not satisfy the gate for a factory update")
    ok("a factory update's claim is admitted against this engine's own record and ownership table, is void "
       "when one hand-written file joins it, and waives no verdict")


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
            a_stale_record_fails_the_gate(r)
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
