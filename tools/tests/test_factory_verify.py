#!/usr/bin/env python3
"""`factory verify` (#70) refuses at the stage that failed, and `produce` finishes with it.

The dotnet here is a fake (`$FACTORY_DOTNET`, the way `$FACTORY_GH` stands in for `gh`): a
script that logs its arguments, writes lock files on restore (and refuses a locked restore
without them), writes bin/ and obj/ on build -- noting how many lock files provenance.json lists
at that moment -- and fails the subcommand it is told to fail. The engine's gate is stood in for
by a script that runs that fake's locked restore, build and test from PATH, as the real
`scripts/validate.sh full` does; the real gate is scripts/validate-engine.sh's to run, on a real
engine with the pinned SDK, in CI's `engine` job. So what is asserted here is verify's own logic:
the order of the stages, that each refusal names its stage and stops the run, that restore runs
only for an unlocked engine and the gate always, that produce records the lock files before the
gate builds, and that produce calls verify unless `--no-verify`.

Run: python3 -m unittest discover -s tools/tests
"""
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_factory_produce import pack_version, snapshot  # noqa: E402  (#67's TestTransactional helper)

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
CORPUS = os.path.join(HOYLE, "hoyle.txt")
NAME = "HoyleBackgammon"

_spec = importlib.util.spec_from_file_location("factory_main_verify", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
verify_step = factory.verify_step

FAKE_DOTNET = r'''#!/usr/bin/env python3
import json, os, re, sys
args = sys.argv[1:]
command = args[0] if args else ""
note = ""
if command == "build" and os.path.exists("provenance.json"):
    with open("provenance.json", encoding="utf-8") as handle:
        inputs = json.load(handle).get("buildInputs") or []
    note = " locks-recorded=%d" % sum(1 for i in inputs if i["path"].endswith("packages.lock.json"))
with open(os.environ["FAKE_DOTNET_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join(args) + note + "\n")
print(f"fake dotnet {command}")
if command == os.environ.get("FAKE_DOTNET_FAIL"):
    print(f"error: fake {command} failure")
    sys.exit(1)
projects = [d for d, _, names in os.walk(".") if any(n.endswith(".csproj") for n in names)]
# A lock file records the pins it was resolved against, and a locked restore refuses one that
# records other pins than RulesFactory.Packages.g.props now has, as NuGet refuses a stale lock file.
pins = []
if os.path.exists("RulesFactory.Packages.g.props"):
    with open("RulesFactory.Packages.g.props", encoding="utf-8") as handle:
        pins = sorted("%s=%s" % pin for pin in re.findall(r'<PackageVersion Include="([^"]+)" Version="([^"]+)"', handle.read()))
if command == "restore":
    for project in projects:
        lock = os.path.join(project, "packages.lock.json")
        if "--locked-mode" in args:
            if not os.path.exists(lock):
                print(f"error: {lock} is missing and restore is locked")
                sys.exit(1)
            with open(lock, encoding="utf-8") as handle:
                recorded = json.load(handle).get("pins")
            if recorded is not None and recorded != pins:
                print(f"error: {lock} is not consistent with the project's package versions and restore is locked")
                sys.exit(1)
        else:
            with open(lock, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"version": 1, "pins": pins, "dependencies": {}}) + "\n")
if command == "build":
    for project in projects:
        for sub in ("obj", os.path.join("bin", "Release")):
            os.makedirs(os.path.join(project, sub), exist_ok=True)
        with open(os.path.join(project, "obj", "project.assets.json"), "w", encoding="utf-8") as assets:
            assets.write('{"projectPath": "%s"}\n' % os.path.abspath(project))
        with open(os.path.join(project, "bin", "Release", "Engine.dll"), "wb") as dll:
            dll.write(b"built")
'''

# Stands in for scripts/validate.sh full: its dotnet steps, with `dotnet` found on PATH.
FAKE_GATE = r'''#!/usr/bin/env python3
import subprocess, sys
for step in (["restore", "--locked-mode"], ["build", "-warnaserror"], ["test"]):
    if subprocess.run(["dotnet", *step]).returncode != 0:
        print(f"validate.sh full: FAIL ({step[0]})")
        sys.exit(1)
print("validate.sh full: PASS")
'''


def run(argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = factory.main(argv)
    return code, buffer.getvalue()


class VerifyCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        out = os.path.join(cls.shared, "package")
        subprocess.run([sys.executable, PACK, HOYLE, "--out", out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
        cls.nupkg = os.path.join(out, name)
        cls.base = os.path.join(cls.shared, "engine")
        code, log = cls.produce_into(cls.base, "--no-verify")
        assert code == 0, log

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    @classmethod
    def produce_into(cls, out, *extra):
        # --allow-dirty: this checkout's own git state is not under test (test_factory_provenance.py).
        return run(["produce", "--package", cls.nupkg, "--corpus", CORPUS, "--name", NAME, "--out", out,
                    "--allow-dirty", *extra])

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.engine = os.path.join(self.tmp, "engine")
        shutil.copytree(self.base, self.engine)
        fake = os.path.join(self.tmp, "bin", "dotnet")
        os.makedirs(os.path.dirname(fake))
        with open(fake, "w", encoding="utf-8") as handle:
            handle.write(FAKE_DOTNET)
        os.chmod(fake, 0o755)
        self.log = os.path.join(self.tmp, "dotnet.log")
        self.env = {"FACTORY_DOTNET": fake, "FAKE_DOTNET_LOG": self.log}
        self.fake_gate = os.path.join(self.tmp, "fake-gate.py")
        with open(self.fake_gate, "w", encoding="utf-8") as handle:
            handle.write(FAKE_GATE)
        self.gate_calls = []
        real_run = verify_step._run

        def run_with_fake_gate(stage, argv, cwd, log, env=None):
            if stage != "gate":
                return real_run(stage, argv, cwd, log, env)
            self.gate_calls.append((argv, env))
            return real_run(stage, [sys.executable, self.fake_gate], cwd, log, env)

        patcher = mock.patch.object(verify_step, "_run", run_with_fake_gate)
        patcher.start()
        self.addCleanup(patcher.stop)

    def verify(self, **env):
        with mock.patch.dict(os.environ, {**self.env, **env}):
            return run(["verify", "--engine", self.engine, "--package", self.nupkg])

    def dotnet_lines(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return handle.read().splitlines()

    def dotnet_calls(self):
        return [line.split(" ")[0] + "".join(f" {flag}" for flag in ("--locked-mode", "--force-evaluate")
                                             if flag in line.split(" "))
                for line in self.dotnet_lines()]


FRESH = ["restore", "restore --locked-mode", "build", "test"]


class TestStages(VerifyCase):
    def test_every_stage_passes_and_the_gate_runs_after_restore(self):
        code, output = self.verify()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.dotnet_calls(), FRESH, "one restore that writes lock files, then the gate's")
        for stage in verify_step.STAGES:
            self.assertIn(f"] {stage}", output)
        self.assertIn("ok   restore: 2 lock file(s) written", output)
        self.assertIn("ok   gate: scripts/validate.sh full passed", output)
        self.assertIn("PASS", output.splitlines()[-1])
        ((argv, env),) = self.gate_calls
        self.assertEqual(argv[1:], [os.path.join(os.path.abspath(self.engine), "scripts", "validate.sh"), "full"])
        self.assertTrue(env["PATH"].startswith(os.path.dirname(self.env["FACTORY_DOTNET"])),
                        "the gate's dotnet is the one FACTORY_DOTNET names")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1", "the gate's Python leaves no __pycache__ to commit")

    def test_a_provenance_mismatch_fails_at_stage_one_and_runs_no_dotnet(self):
        registry = os.path.join(self.engine, "src", NAME, "Generated", "Registry.g.cs")
        with open(registry, "a", encoding="utf-8") as handle:
            handle.write("// tweaked by hand\n")
        code, output = self.verify()
        self.assertEqual(code, 1, output)
        self.assertIn(f"MISMATCH generated[src/{NAME}/Generated/Registry.g.cs]", output)
        self.assertIn("verify FAILED at stage provenance", output)
        self.assertEqual(self.dotnet_calls(), [])
        self.assertEqual(self.gate_calls, [])

    def test_a_restore_failure_fails_at_restore_and_runs_no_gate(self):
        code, output = self.verify(FAKE_DOTNET_FAIL="restore")
        self.assertEqual(code, 1, output)
        self.assertIn("verify FAILED at stage restore", output)
        self.assertEqual(self.dotnet_calls(), ["restore"])
        self.assertEqual(self.gate_calls, [])

    def test_a_build_failure_fails_at_the_gate_and_runs_no_tests(self):
        code, output = self.verify(FAKE_DOTNET_FAIL="build")
        self.assertEqual(code, 1, output)
        self.assertIn("error: fake build failure", output)
        self.assertIn("verify FAILED at stage gate", output)
        self.assertEqual(self.dotnet_calls(), ["restore", "restore --locked-mode", "build"])

    def test_a_test_failure_fails_at_the_gate(self):
        code, output = self.verify(FAKE_DOTNET_FAIL="test")
        self.assertEqual(code, 1, output)
        self.assertIn("verify FAILED at stage gate", output)

    def test_a_missing_dotnet_fails_its_stage(self):
        code, output = self.verify(FACTORY_DOTNET=os.path.join(self.tmp, "nowhere", "dotnet"))
        self.assertEqual(code, 1, output)
        self.assertIn("verify FAILED at stage restore -- cannot run", output)

    def test_a_missing_engine_is_a_usage_error(self):
        code, output = run(["verify", "--engine", os.path.join(self.tmp, "absent")])
        self.assertEqual(code, 2, output)

    def test_with_lock_files_restore_is_skipped_and_only_the_gate_restores(self):
        for project in (f"src/{NAME}", f"tests/{NAME}.Tests"):
            with open(os.path.join(self.engine, *project.split("/"), "packages.lock.json"), "w",
                      encoding="utf-8") as handle:
                handle.write("{}\n")
        code, output = self.verify()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.dotnet_calls(), ["restore --locked-mode", "build", "test"])
        self.assertIn("restore -- skipped: 2 lock file(s) present", output)
        self.assertEqual(len(self.gate_calls), 1)


class TestProduce(VerifyCase):
    """produce verifies the staging copy (#67) before committing, so only a verified engine lands."""

    def assert_no_staging(self, parent):
        self.assertEqual([n for n in os.listdir(parent) if ".factory-produce-" in n], [])

    def test_produce_runs_the_gate_on_the_staging_copy_then_commits_it_with_its_lock_files(self):
        out = os.path.join(self.tmp, "fresh")
        with mock.patch.object(verify_step, "verify_staged", wraps=verify_step.verify_staged) as spy, \
                mock.patch.dict(os.environ, self.env):
            code, output = self.produce_into(out)
        self.assertEqual(code, 0, output)
        spy.assert_called_once()
        verified = spy.call_args.args[0]
        self.assertNotEqual(os.path.realpath(verified), os.path.realpath(out), "verify ran before the commit")
        self.assertIn(".factory-produce-", verified)
        self.assertEqual(self.dotnet_calls(), FRESH)
        self.assertEqual(len(self.gate_calls), 1, "a default produce runs the engine's gate")
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {out}, verified")
        self.assertLess(output.index("rewrote provenance.json"), output.index("] gate"))
        self.assertIn("build -warnaserror locks-recorded=2", self.dotnet_lines(),
                      "the gate built with provenance.json already listing the lock files")

        locks = sorted(os.path.relpath(os.path.join(d, "packages.lock.json"), out).replace(os.sep, "/")
                       for d, _, names in os.walk(out) if "packages.lock.json" in names)
        self.assertEqual(locks, [f"src/{NAME}/packages.lock.json", f"tests/{NAME}.Tests/packages.lock.json"])
        self.assertIn("added 2 packages.lock.json file(s) written by restore: review and commit them", output)
        # #69: the committed record lists them, so they are held to it, and it still recomputes.
        with open(os.path.join(out, "provenance.json"), encoding="utf-8") as handle:
            inputs = [item["path"] for item in json.load(handle)["buildInputs"]]
        self.assertEqual([p for p in inputs if p.endswith("packages.lock.json")], locks)
        code, recomputed = run(["provenance", "--engine", out, "--package", self.nupkg])
        self.assertEqual(code, 0, recomputed)
        with open(os.path.join(out, *locks[0].split("/")), "a", encoding="utf-8") as handle:
            handle.write("\n")
        code, recomputed = run(["provenance", "--engine", out, "--package", self.nupkg])
        self.assertEqual(code, 1, recomputed)
        self.assertIn(f"MISMATCH buildInputs[{locks[0]}]", recomputed)
        for directory, dirs, names in os.walk(out):
            self.assertFalse({"bin", "obj"} & set(dirs), f"{directory} got build output from the staging copy")
            for name in names:
                with open(os.path.join(directory, name), "rb") as handle:
                    self.assertNotIn(b".factory-produce-", handle.read(), f"{name} names the staging directory")
        self.assert_no_staging(self.tmp)

    def test_re_producing_a_verified_engine_commits_nothing(self):
        with mock.patch.dict(os.environ, self.env):
            code, output = self.produce_into(self.engine)
            self.assertEqual(code, 0, output)
            code, output = self.produce_into(self.engine)
        self.assertEqual(code, 0, output)
        self.assertIn("restore -- skipped: 2 lock file(s) present", output)
        self.assertIn(f"committed to {os.path.realpath(self.engine)}: 0 added, 0 changed, 0 removed", output)

    def test_standalone_verify_leaves_unrecorded_lock_files_unclaimed(self):
        code, output = self.verify()
        self.assertEqual(code, 0, output)
        code, recomputed = run(["provenance", "--engine", self.engine, "--package", self.nupkg])
        self.assertEqual(code, 0, recomputed)

    def test_a_verify_failure_leaves_an_existing_engine_byte_identical(self):
        before = snapshot(self.engine)
        with mock.patch.dict(os.environ, {**self.env, "FAKE_DOTNET_FAIL": "build"}):
            code, output = self.produce_into(self.engine)
        self.assertEqual(code, 1, output)
        self.assertEqual(self.dotnet_calls(), ["restore", "restore --locked-mode", "build"])
        self.assertIn("verify FAILED at stage gate", output)
        self.assertIn("Nothing was produced.", output)
        self.assertNotIn(f"produced {NAME} in", output)
        self.assertEqual(before, snapshot(self.engine), "restore's lock files and the build output were discarded")
        self.assert_no_staging(self.tmp)

    def test_a_verify_failure_leaves_a_fresh_out_uncreated(self):
        out = os.path.join(self.tmp, "fresh")
        with mock.patch.dict(os.environ, {**self.env, "FAKE_DOTNET_FAIL": "test"}):
            code, output = self.produce_into(out)
        self.assertEqual(code, 1, output)
        self.assertIn("verify FAILED at stage gate", output)
        self.assertIn("Nothing was produced.", output)
        self.assertFalse(os.path.exists(out))
        self.assert_no_staging(self.tmp)

    def test_no_verify_is_explicit_and_says_so(self):
        out = os.path.join(self.tmp, "fresh")
        with mock.patch.object(verify_step, "verify_staged") as spy:
            code, output = self.produce_into(out, "--no-verify")
        self.assertEqual(code, 0, output)
        spy.assert_not_called()
        self.assertIn("verification SKIPPED (--no-verify)", output)
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {out}, NOT VERIFIED")


class TestPins(unittest.TestCase):
    """The relock signal (#94): the resolved pin set, not the bytes of the props."""

    PROPS = ('<Project>\n  <!-- <PackageVersion Include="Old" Version="0.0.1" /> -->\n  <ItemGroup>\n'
             '    <PackageVersion Include="RulesKernel" Version="0.2.0" />\n'
             '    <PackageVersion Version="[3.0.0]" Include="RulesFactory.Maps.HoyleBackgammon" />\n'
             '  </ItemGroup>\n</Project>\n')

    def test_pins_are_every_package_version_outside_comments(self):
        self.assertEqual(verify_step.pins(self.PROPS),
                         {"ruleskernel": "0.2.0", "rulesfactory.maps.hoylebackgammon": "[3.0.0]"})

    def test_a_version_change_is_a_change_and_layout_is_not(self):
        before = verify_step.pins(self.PROPS)
        self.assertTrue(verify_step.pins_changed(before, verify_step.pins(self.PROPS.replace("[3.0.0]", "[4.0.0]"))))
        self.assertTrue(verify_step.pins_changed(before, verify_step.pins(self.PROPS.replace("0.2.0", "0.3.0"))))
        self.assertTrue(verify_step.pins_changed(
            before, verify_step.pins(self.PROPS.replace("  </ItemGroup>", '    <PackageVersion Include="X" Version="1" />\n  </ItemGroup>'))))
        relaid = self.PROPS.replace("<!-- <PackageVersion", "<!-- a new comment --><!-- <PackageVersion").replace("\n    <", "\n\n      <")
        self.assertFalse(verify_step.pins_changed(before, verify_step.pins(relaid)))

    def test_no_props_before_the_run_counts_as_changed(self):
        self.assertTrue(verify_step.pins_changed(None, verify_step.pins(self.PROPS)))
        with tempfile.TemporaryDirectory() as empty:
            self.assertIsNone(verify_step.read_pins(empty))


class TestRelock(VerifyCase):
    """#94: a produce that moves the generated pins re-locks before the gate; nothing else re-locks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.nupkg_bumped = pack_version(HOYLE, "7.0.0", cls.shared)

    def produce_verified(self, package, **env):
        with mock.patch.dict(os.environ, {**self.env, **env}):
            return run(["produce", "--package", package, "--corpus", CORPUS, "--name", NAME, "--out", self.engine,
                        "--allow-dirty"])

    def locks(self):
        found = {}
        for relative in (f"src/{NAME}/packages.lock.json", f"tests/{NAME}.Tests/packages.lock.json"):
            with open(os.path.join(self.engine, *relative.split("/")), encoding="utf-8") as handle:
                found[relative] = handle.read()
        return found

    def recorded_locks(self):
        with open(os.path.join(self.engine, "provenance.json"), encoding="utf-8") as handle:
            return {i["path"]: i["sha256"] for i in json.load(handle)["buildInputs"] if i["path"].endswith(".lock.json")}

    def test_a_map_version_bump_re_locks_records_and_commits_verified(self):
        code, output = self.produce_verified(self.nupkg)
        self.assertEqual(code, 0, output)
        before = self.locks()
        os.remove(self.log)

        code, output = self.produce_verified(self.nupkg_bumped)
        self.assertEqual(code, 0, output)
        self.assertEqual(self.dotnet_calls(), ["restore --force-evaluate", "restore --locked-mode", "build", "test"])
        self.assertIn("the generated pins changed, so this restore re-locks the 2 lock file(s)", output)
        self.assertIn("ok   restore: 2 lock file(s) re-locked", output)
        self.assertLess(output.index("rewrote provenance.json"), output.index("] gate"))
        self.assertIn("re-locked 2 packages.lock.json file(s) because the generated pins changed", output)
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {self.engine}, verified")
        after = self.locks()
        for relative in after:
            self.assertNotEqual(before[relative], after[relative])
            self.assertIn("[7.0.0]", after[relative])
        recorded = self.recorded_locks()
        self.assertEqual(sorted(recorded), sorted(after))
        for relative, text in after.items():
            self.assertEqual(recorded[relative], hashlib.sha256(text.encode("utf-8")).hexdigest())
        code, recomputed = run(["provenance", "--engine", self.engine, "--package", self.nupkg_bumped])
        self.assertEqual(code, 0, recomputed)

    def test_unchanged_pins_do_not_re_lock_even_when_the_props_bytes_change(self):
        code, output = self.produce_verified(self.nupkg)
        self.assertEqual(code, 0, output)
        before = self.locks()
        os.remove(self.log)
        real =factory.generate.packages_props
        with mock.patch.object(factory.generate, "packages_props", lambda model: real(model) + "<!-- relaid -->\n"):
            code, output = self.produce_verified(self.nupkg)
        self.assertEqual(code, 0, output)
        self.assertIn("restore -- skipped: 2 lock file(s) present", output)
        self.assertEqual(self.dotnet_calls(), ["restore --locked-mode", "build", "test"])
        self.assertEqual(before, self.locks())
        self.assertNotIn("re-locked", output)

    def test_a_failed_relock_leaves_the_engine_byte_identical(self):
        code, output = self.produce_verified(self.nupkg)
        self.assertEqual(code, 0, output)
        before = snapshot(self.engine)
        code, output = self.produce_verified(self.nupkg_bumped, FAKE_DOTNET_FAIL="restore")
        self.assertEqual(code, 1, output)
        self.assertIn("verify FAILED at stage restore", output)
        self.assertEqual(before, snapshot(self.engine))

    def test_without_the_relock_the_bumped_gate_fails_its_locked_restore(self):
        """The defect #94 names, shown on the fake: stale lock files cannot pass the gate."""
        code, output = self.produce_verified(self.nupkg)
        self.assertEqual(code, 0, output)
        with mock.patch.object(verify_step, "pins_changed", return_value=False):
            code, output = self.produce_verified(self.nupkg_bumped)
        self.assertEqual(code, 1, output)
        self.assertIn("is not consistent with the project's package versions", output)
        self.assertIn("verify FAILED at stage gate", output)

    def test_standalone_verify_never_re_locks(self):
        code, output = self.produce_verified(self.nupkg)
        self.assertEqual(code, 0, output)
        props = os.path.join(self.engine, verify_step.PACKAGES_PROPS)
        with open(props, encoding="utf-8") as handle:
            text = handle.read()
        with open(props, "w", encoding="utf-8") as handle:
            handle.write(text.replace("[6.0.0]", "[7.0.0]"))
        before = self.locks()
        os.remove(self.log)
        with mock.patch.dict(os.environ, self.env):
            with self.assertRaises(verify_step.Failed) as failure:
                verify_step.verify(self.engine, lambda engine, package: [], log=io.StringIO())
        self.assertEqual(failure.exception.stage, "gate")
        self.assertEqual(self.dotnet_calls(), ["restore --locked-mode"])
        self.assertEqual(before, self.locks())


def nuget_lock(pins, transitive=False, extra=None):
    """A packages.lock.json in NuGet's shape resolving `pins` ({id: version}) in two frameworks."""
    kind = "CentralTransitive" if transitive else "Direct"
    packages = {package: {"type": kind, "requested": f"[{version}, )", "resolved": version, "contentHash": "x=="}
                for package, version in pins.items()}
    packages.update(extra or {})
    return json.dumps({"version": 2, "dependencies": {"net10.0": packages, "net8.0": packages}}, indent=2) + "\n"


class TestStaleLocks(unittest.TestCase):
    """`stale_locks`: which lock-file entries disagree with the generated pins."""

    PINS = {"ruleskernel": "0.2.0", "rulesfactory.maps.hoylebackgammon": "[5.0.0]"}

    def engine(self, locks):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        for relative, text in locks.items():
            path = os.path.join(root, *relative.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        return root

    def test_agreeing_direct_and_transitive_entries_are_not_stale(self):
        root = self.engine({
            "src/E/packages.lock.json": nuget_lock({"RulesKernel": "0.2.0", "RulesFactory.Maps.HoyleBackgammon": "5.0.0"}),
            "tests/E.Tests/packages.lock.json": nuget_lock({"RulesKernel": "0.2.0"}, transitive=True),
        })
        self.assertEqual(verify_step.stale_locks(root, self.PINS), [])

    def test_disagreeing_entries_name_file_package_and_both_versions(self):
        root = self.engine({
            "src/E/packages.lock.json": nuget_lock({"RulesKernel": "0.2.0", "RulesFactory.Maps.HoyleBackgammon": "4.0.0"}),
            "tests/E.Tests/packages.lock.json": nuget_lock({"RulesKernel": "0.1.0"}, transitive=True),
        })
        self.assertEqual(verify_step.stale_locks(root, self.PINS), [
            ("src/E/packages.lock.json", "RulesFactory.Maps.HoyleBackgammon", "4.0.0", "[5.0.0]"),
            ("tests/E.Tests/packages.lock.json", "RulesKernel", "0.1.0", "0.2.0"),
        ])

    def test_packages_outside_the_pin_set_are_ignored(self):
        other = {"xunit": {"type": "Direct", "requested": "[2.9.0, )", "resolved": "2.9.0"},
                 "RulesKernel.Randomness": {"type": "Direct", "resolved": "0.1.0"}}
        root = self.engine({"src/E/packages.lock.json": nuget_lock({"RulesKernel": "0.2.0"}, extra=other)})
        self.assertEqual(verify_step.stale_locks(root, self.PINS), [])

    def test_versions_compare_as_nuget_normalises_them(self):
        root = self.engine({"src/E/packages.lock.json": nuget_lock({"RulesKernel": "0.2", "RulesFactory.Maps.HoyleBackgammon": "5.0.0.0"})})
        self.assertEqual(verify_step.stale_locks(root, self.PINS), [])

    def test_an_unreadable_lock_file_is_reported(self):
        root = self.engine({"src/E/packages.lock.json": "{ not json"})
        ((path, package, _, _),) = verify_step.stale_locks(root, self.PINS)
        self.assertEqual((path, package), ("src/E/packages.lock.json", "(unreadable)"))

    def test_no_lock_files_is_nothing_stale(self):
        self.assertEqual(verify_step.stale_locks(self.engine({}), self.PINS), [])


class TestNoVerifyStaleLocks(VerifyCase):
    """--no-verify cannot re-lock, so it refuses lock files the generated pins have moved past."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.nupkg_bumped = pack_version(HOYLE, "7.0.0", cls.shared)
        cls.kernel = verify_step.read_pins(cls.base)["ruleskernel"]
        cls.map_id = f"RulesFactory.Maps.{NAME}"
        assert cls.map_id.lower() in verify_step.read_pins(cls.base)

    def write_locks(self, map_version):
        pins = {"RulesKernel": self.kernel, self.map_id: map_version}
        for relative, text in ((f"src/{NAME}/packages.lock.json", nuget_lock(pins)),
                               (f"tests/{NAME}.Tests/packages.lock.json", nuget_lock(pins, transitive=True))):
            with open(os.path.join(self.engine, *relative.split("/")), "w", encoding="utf-8") as handle:
                handle.write(text)

    def produce_bumped(self, *extra):
        return run(["produce", "--package", self.nupkg_bumped, "--corpus", CORPUS, "--name", NAME,
                    "--out", self.engine, "--allow-dirty", *extra])

    def test_stale_lock_files_are_refused_and_the_engine_is_byte_identical(self):
        self.write_locks("6.0.0")
        before = snapshot(self.engine)
        code, output = self.produce_bumped("--no-verify")
        self.assertEqual(code, 1, output)
        self.assertIn("REFUSED -- --no-verify cannot re-lock", output)
        for project in (f"src/{NAME}", f"tests/{NAME}.Tests"):
            self.assertIn(f"{project}/packages.lock.json: {self.map_id} locked at 6.0.0, pinned at [7.0.0]", output)
        self.assertIn("produce without --no-verify", output)
        self.assertIn("scripts/validate.sh lock", output)
        self.assertIn("Nothing was produced.", output)
        self.assertEqual(before, snapshot(self.engine))
        self.assertEqual([n for n in os.listdir(self.tmp) if ".factory-produce-" in n], [])

    def test_lock_files_already_re_locked_are_committed_unverified(self):
        self.write_locks("7.0.0")
        before = snapshot(self.engine)
        code, output = self.produce_bumped("--no-verify")
        self.assertEqual(code, 0, output)
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {self.engine}, NOT VERIFIED")
        self.assertEqual(verify_step.read_pins(self.engine)[self.map_id.lower()], "[7.0.0]")
        after = snapshot(self.engine)
        for relative in (f"src/{NAME}/packages.lock.json", f"tests/{NAME}.Tests/packages.lock.json"):
            self.assertEqual(before[relative.replace("/", os.sep)], after[relative.replace("/", os.sep)])

    def test_an_engine_without_lock_files_is_unaffected(self):
        code, output = self.produce_bumped("--no-verify")
        self.assertEqual(code, 0, output)
        self.assertEqual(verify_step.read_pins(self.engine)[self.map_id.lower()], "[7.0.0]")

    def test_the_verify_path_still_re_locks_stale_lock_files(self):
        self.write_locks("6.0.0")
        with mock.patch.dict(os.environ, self.env):
            code, output = self.produce_bumped()
        self.assertEqual(code, 0, output)
        self.assertIn("the generated pins changed, so this restore re-locks the 2 lock file(s)", output)
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {self.engine}, verified")


if __name__ == "__main__":
    unittest.main()
