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

Run: python3 -m unittest discover -s tools/tests -t tools
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
TOOLS = os.path.dirname(os.path.dirname(HERE))
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
import pins  # noqa: E402  (the SDK and kernel pins; tools/factory is on sys.path now)
import scaffold  # noqa: E402  (the managed recipes)

# What produce appends to the last line of a `--no-verify` run, so the line and the exit code
# can never be read apart.
NOT_VERIFIED_TAIL = f" -- nothing was built or tested, so this run exits {factory.NOT_VERIFIED}, not 0"

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
# Which SDK each call would run on: the version the global.json it starts beside pins.
if os.environ.get("FAKE_DOTNET_SDK_LOG") and os.path.exists("global.json"):
    with open("global.json", encoding="utf-8") as handle:
        sdk = json.load(handle)["sdk"]["version"]
    with open(os.environ["FAKE_DOTNET_SDK_LOG"], "a", encoding="utf-8") as log:
        log.write("%s %s\n" % (command, sdk))
if command == "--list-sdks":
    for sdk in os.environ.get("FAKE_DOTNET_SDKS", "").split():
        print("%s [/usr/share/dotnet/sdk]" % sdk)
    sys.exit(0)
if command == "--version" and os.environ.get("FAKE_DOTNET_FAIL") != "--version":
    print(os.environ.get("FAKE_DOTNET_VERSION", "10.0.0"))
    sys.exit(0)
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
        # `--no-verify` ends NOT VERIFIED (3), never 0 (tools/factory/__main__.py).
        assert code == factory.NOT_VERIFIED, log

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
        self.assertIn(f"wrote to {os.path.realpath(self.engine)}: 0 added, 0 changed, 0 removed", output)

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
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        spy.assert_not_called()
        self.assertIn("verification SKIPPED (--no-verify)", output)
        self.assertEqual(output.splitlines()[-1],
                         f"produced {NAME} in {out}, NOT VERIFIED" + NOT_VERIFIED_TAIL)


class TestAVerifiedProduceCommitsWhatItVerified(VerifyCase):
    """#335: produce refuses to call a tree verified when --out moved after the gate ran on it.

    Independent review reproduced this: an engine-owned source file edited in --out while produce
    ran was kept -- which is right -- and the run committed its generated files over it and printed
    `verified`, though the engine the gate built and tested had the old source in it and the
    engine now on disk had never been built at all.

    Each assertion names the refusal's own words and the path it names, not the exit code alone:
    a verify failure, a symlink in --out and the older mutation-set refusal all end a produce the
    same way, so `code == 1` would pass on any of them for the wrong reason (#283).
    """

    def assert_no_staging(self, parent):
        self.assertEqual([n for n in os.listdir(parent) if ".factory-produce-" in n], [])

    def read(self, relative):
        with open(os.path.join(self.engine, *relative.split("/")), encoding="utf-8") as handle:
            return handle.read()

    def edit_out_during_verify(self, edit):
        """Run `edit(--out)` while verify is building and testing the staging copy."""
        real = verify_step.verify_staged

        def edit_then_verify(root, *args, **kwargs):
            edit(self.engine)
            return real(root, *args, **kwargs)
        return mock.patch.object(verify_step, "verify_staged", edit_then_verify)

    def produce_with(self, edit):
        with mock.patch.dict(os.environ, self.env), self.edit_out_during_verify(edit):
            return self.produce_into(self.engine)

    def test_an_engine_owned_source_edited_during_verify_refuses_and_keeps_the_edit(self):
        source = f"src/{NAME}/{NAME}.csproj"
        mine = self.read(source) + "<!-- my own ItemGroup -->\n"

        def edit(out):
            with open(os.path.join(out, *source.split("/")), "w", encoding="utf-8") as handle:
                handle.write(mine)
        code, output = self.produce_with(edit)
        self.assertEqual(code, 1, output)
        self.assertIn("--out changed after the engine was verified", output)
        self.assertIn(f"{source} (changed)", output)
        self.assertIn("run produce again to verify the engine with it", output)
        self.assertIn("Nothing was produced.", output)
        self.assertNotIn(f"produced {NAME} in", output)
        # The edit stands, and nothing the run staged -- the lock files restore wrote above all --
        # was written over it.
        self.assertEqual(self.read(source), mine)
        self.assertEqual(verify_step.lock_files(self.engine), [])
        self.assert_no_staging(self.tmp)

    def test_a_source_file_added_to_out_during_verify_refuses(self):
        added = f"src/{NAME}/MyRule.cs"

        def edit(out):
            with open(os.path.join(out, *added.split("/")), "w", encoding="utf-8") as handle:
                handle.write("// a rule of my own\n")
        code, output = self.produce_with(edit)
        self.assertEqual(code, 1, output)
        self.assertIn("--out changed after the engine was verified", output)
        self.assertIn(f"{added} (added)", output)
        self.assertTrue(os.path.isfile(os.path.join(self.engine, *added.split("/"))))
        self.assert_no_staging(self.tmp)

    def test_test_output_written_during_verify_is_not_an_input_and_the_engine_is_committed(self):
        """The guard is no broader than necessary: TRX files are the gate's output, not its input."""
        def edit(out):
            os.makedirs(os.path.join(out, "TestResults"), exist_ok=True)
            with open(os.path.join(out, "TestResults", "run.trx"), "w", encoding="utf-8") as handle:
                handle.write("<TestRun />\n")
        code, output = self.produce_with(edit)
        self.assertEqual(code, 0, output)
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {self.engine}, verified")
        self.assertEqual(self.read("TestResults/run.trx"), "<TestRun />\n")
        self.assertEqual(len(verify_step.lock_files(self.engine)), 2, "the verified engine was committed")

    def test_a_no_verify_produce_is_not_held_to_a_build_it_never_made(self):
        """--no-verify claims nothing about a build, so a concurrent edit is kept and the run goes on."""
        source = f"src/{NAME}/{NAME}.csproj"
        mine = self.read(source) + "<!-- my own ItemGroup -->\n"
        real = factory.transaction.Stage.commit

        def edit_then_commit(stage, *args, **kwargs):
            with open(os.path.join(self.engine, *source.split("/")), "w", encoding="utf-8") as handle:
                handle.write(mine)
            return real(stage, *args, **kwargs)
        with mock.patch.object(factory.transaction.Stage, "commit", edit_then_commit):
            code, output = self.produce_into(self.engine, "--no-verify")
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertNotIn("changed after the engine was verified", output)
        self.assertEqual(self.read(source), mine)


class TestExitCodes(VerifyCase):
    """What a caller reading only the exit code learns.

    The defect this class exists for: `produce --no-verify` printed NOT VERIFIED twice and exited 0,
    so a script or CI job checking `$?` alone could not tell an engine that was never built or
    tested from a verified one. It now ends NOT VERIFIED (3) -- the code this lineage already uses
    for that outcome (`engine-gate.py posture`, `check-rebuild.py`, `check-target.py`), and which
    0013 requires to be neither ok nor FAIL. A caller for which an unverified engine is the point
    accepts exactly 3; 0 still means verified and 1 still means refused.
    """

    def test_not_verified_is_three_the_code_this_lineage_already_uses(self):
        self.assertEqual(factory.NOT_VERIFIED, 3)

    def test_no_verify_exits_not_verified_and_never_zero(self):
        out = os.path.join(self.tmp, "fresh")
        code, output = self.produce_into(out, "--no-verify")
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertNotEqual(code, 0, "an engine that was never built or tested is not a success")
        # The engine was still written: --no-verify stays a usable mode, it just is not a pass.
        self.assertTrue(os.path.isfile(os.path.join(out, "provenance.json")), output)
        self.assertIn("NOT VERIFIED", output)

    def test_a_verified_produce_still_exits_zero(self):
        out = os.path.join(self.tmp, "verified")
        with mock.patch.dict(os.environ, self.env):
            code, output = self.produce_into(out)
        self.assertEqual(code, 0, output)
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {out}, verified")
        # (intake's packaged-checker summary carries its own per-check NOT VERIFIED lines; the
        # verdict line is the one a caller reads, and it says verified.)
        self.assertNotIn("NOT VERIFIED", output.splitlines()[-1])

    def test_the_three_outcomes_a_caller_can_see_are_three_different_codes(self):
        """verified, NOT VERIFIED and refused must not collide: that collision was the defect."""
        out = os.path.join(self.tmp, "codes")
        with mock.patch.dict(os.environ, self.env):
            verified, _ = self.produce_into(out + "-ok")
        unverified, _ = self.produce_into(out + "-nv", "--no-verify")
        with mock.patch.dict(os.environ, {**self.env, "FAKE_DOTNET_FAIL": "build"}):
            refused, refusal = self.produce_into(out + "-bad")
        self.assertEqual([verified, unverified, refused], [0, factory.NOT_VERIFIED, 1], refusal)
        self.assertEqual(len({verified, unverified, refused}), 3)

    def test_a_usage_error_is_still_two(self):
        code, output = run(["produce", "--package", self.nupkg, "--corpus", CORPUS, "--name", "not pascal",
                            "--out", os.path.join(self.tmp, "never"), "--allow-dirty", "--no-verify"])
        self.assertEqual(code, 2, output)

    def test_verify_and_provenance_still_exit_zero_when_they_prove_their_claim(self):
        code, output = self.verify()
        self.assertEqual(code, 0, output)
        code, output = run(["provenance", "--engine", self.engine, "--package", self.nupkg])
        self.assertEqual(code, 0, output)

    def test_every_shipped_caller_of_no_verify_handles_the_new_code(self):
        """The scripts in this repository that run `produce --no-verify` must handle its exit code.

        Each of them runs it in exactly one place, which captures the status rather than letting
        `set -e` (or a check of the code) abort on it, and the script names 3 as the code it accepts.
        A new bare `tools/factory produce ... --no-verify` anywhere else fails this test, which is the
        point: that is how the defect would come back. scripts/validate-engine.sh is a wrapper since
        #172, so its orchestration, tools/validate-engine.py, is the caller examined: there the command
        is a list, and the status is captured as `status = run(...)`.
        """
        callers = (("tools/validate-engine.py", '"tools/factory", "produce"', "status = "),
                   ("examples/hoyle-backgammon/produced-engine/equivalence.sh", "tools/factory produce", "status=$?"))
        for relative, invocation, capture in callers:
            with open(os.path.join(REPO, *relative.split("/")), encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            # The invocation and its continuation lines: a produce command here spans at most two.
            blocks = [(number, "\n".join(lines[number - 1:number + 1]))
                      for number, line in enumerate(lines, 1)
                      if invocation in line and not line.lstrip().startswith("#")]
            unverified = [(number, block) for number, block in blocks if "--no-verify" in block]
            self.assertEqual(len(unverified), 1,
                             f"{relative} runs `produce --no-verify` in {len(unverified)} places, not one")
            (number, block) = unverified[0]
            self.assertIn(capture, block,
                          f"{relative}:{number} does not capture produce's exit code, so it cannot accept "
                          f"{factory.NOT_VERIFIED} and reject the rest")
            self.assertIn(str(factory.NOT_VERIFIED), "\n".join(lines),
                          f"{relative} never names the NOT VERIFIED exit code")


class TestSdkOverride(VerifyCase):
    """FACTORY_DOTNET_SDK_OVERRIDE: restore and the gate run on another SDK; global.json and provenance do not move."""

    OTHER = "10.0.1"

    def setUp(self):
        super().setUp()
        self.sdk_log = os.path.join(self.tmp, "sdk.log")
        self.env["FAKE_DOTNET_SDK_LOG"] = self.sdk_log
        self.pinned = verify_step.pinned_sdk(self.engine)
        assert self.pinned and self.pinned != self.OTHER

    def sdks(self):
        if not os.path.exists(self.sdk_log):
            return []
        with open(self.sdk_log, encoding="utf-8") as handle:
            return handle.read().splitlines()

    def global_json(self, engine=None):
        with open(os.path.join(engine or self.engine, "global.json"), "rb") as handle:
            return handle.read()

    def test_restore_and_the_gate_run_on_the_override_and_global_json_is_put_back(self):
        before = self.global_json()
        code, output = self.verify(FACTORY_DOTNET_SDK_OVERRIDE=self.OTHER, CI="")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.sdks(), [f"restore {self.OTHER}", f"restore {self.OTHER}", f"build {self.OTHER}",
                                       f"test {self.OTHER}"])
        self.assertEqual(before, self.global_json(), "global.json is byte-identical after verify")
        self.assertIn(f"WARNING: FACTORY_DOTNET_SDK_OVERRIDE={self.OTHER} replaces the pinned SDK {self.pinned}; "
                      "this run does not prove the pinned toolchain", output)
        self.assertLess(output.index("ok   provenance"), output.index("WARNING: FACTORY_DOTNET_SDK_OVERRIDE"))
        self.assertEqual(output.splitlines()[-1], f"verify {self.engine}: PASS on SDK {self.OTHER} by "
                                                  f"FACTORY_DOTNET_SDK_OVERRIDE, not the pinned {self.pinned}")
        code, recomputed = run(["provenance", "--engine", self.engine, "--package", self.nupkg])
        self.assertEqual(code, 0, recomputed)

    def test_without_the_override_nothing_changes(self):
        code, output = self.verify(FACTORY_DOTNET_SDK_OVERRIDE="")
        self.assertEqual(code, 0, output)
        self.assertEqual(set(line.split(" ")[1] for line in self.sdks()), {self.pinned})
        self.assertNotIn("WARNING", output)
        self.assertEqual(output.splitlines()[-1], f"verify {self.engine}: PASS")

    def test_an_engine_that_already_pins_the_override_is_left_alone(self):
        code, output = self.verify(FACTORY_DOTNET_SDK_OVERRIDE=self.pinned, CI="")
        self.assertEqual(code, 0, output)
        self.assertNotIn("WARNING", output)
        self.assertEqual(output.splitlines()[-1], f"verify {self.engine}: PASS")

    def test_a_failing_gate_still_puts_global_json_back(self):
        before = self.global_json()
        code, output = self.verify(FACTORY_DOTNET_SDK_OVERRIDE=self.OTHER, CI="", FAKE_DOTNET_FAIL="build")
        self.assertEqual(code, 1, output)
        self.assertIn("verify FAILED at stage gate", output)
        self.assertIn(f"build {self.OTHER}", self.sdks())
        self.assertEqual(before, self.global_json())

    def test_the_override_is_refused_in_ci_before_anything_runs(self):
        before = self.global_json()
        code, output = self.verify(FACTORY_DOTNET_SDK_OVERRIDE=self.OTHER, CI="true")
        self.assertEqual(code, 2, output)
        self.assertIn("FACTORY_DOTNET_SDK_OVERRIDE is for local runs only and is refused when CI=true", output)
        self.assertNotIn("] provenance", output)
        self.assertEqual(self.dotnet_calls(), [])
        self.assertEqual(before, self.global_json())

    def test_a_hand_edited_global_json_still_fails_provenance(self):
        """The override is not a way past stage 1: the committed pin is what provenance checks."""
        text = verify_step.repin(self.global_json().decode("utf-8"), self.OTHER)
        with open(os.path.join(self.engine, "global.json"), "w", encoding="utf-8") as handle:
            handle.write(text)
        code, output = self.verify(FACTORY_DOTNET_SDK_OVERRIDE=self.OTHER, CI="")
        self.assertEqual(code, 1, output)
        self.assertIn("MISMATCH managed[global.json]", output)
        self.assertEqual(self.dotnet_calls(), [])

    def test_produce_verifies_on_the_override_and_commits_and_records_the_pinned_global_json(self):
        out = os.path.join(self.tmp, "fresh")
        with mock.patch.dict(os.environ, {**self.env, "FACTORY_DOTNET_SDK_OVERRIDE": self.OTHER, "CI": ""}):
            code, output = self.produce_into(out)
        self.assertEqual(code, 0, output)
        self.assertEqual(self.sdks(), [f"restore {self.OTHER}", f"restore {self.OTHER}", f"build {self.OTHER}",
                                       f"test {self.OTHER}"])
        self.assertEqual(self.global_json(out), self.global_json(), "the committed global.json pins the kernel's SDK")
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {out}, verified on SDK {self.OTHER} by "
                                                  f"FACTORY_DOTNET_SDK_OVERRIDE, not the pinned {self.pinned}")
        # after_restore rewrote provenance.json while global.json was the pinned file, so it recomputes.
        code, recomputed = run(["provenance", "--engine", out, "--package", self.nupkg])
        self.assertEqual(code, 0, recomputed)

    def test_repin_writes_global_json_as_generate_does(self):
        text = scaffold.managed_files()["global.json"]
        self.assertEqual(verify_step.repin(text, pins.SDK_VERSION), text)
        self.assertEqual(json.loads(verify_step.repin(text, self.OTHER))["sdk"],
                         {"version": self.OTHER, "rollForward": "disable"})


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
        real = pins.packages_props
        with mock.patch.object(pins, "packages_props", lambda model: real(model) + "<!-- relaid -->\n"):
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


def nuget_lock(pins, transitive=False, extra=None, requested=None):
    """A packages.lock.json in NuGet's shape resolving `pins` ({id: version}) in two frameworks.

    Each entry records the range the generated props request, as NuGet writes it: exact for a map
    (`[5.0.0, 5.0.0]`), a minimum otherwise (`[0.2.0, )`); `requested` ({id: range}) overrides it."""
    kind = "CentralTransitive" if transitive else "Direct"

    def recorded(package, version):
        if package in (requested or {}):
            return requested[package]
        return f"[{version}, {version}]" if package.startswith("RulesFactory.Maps.") else f"[{version}, )"
    packages = {package: {"type": kind, "requested": recorded(package, version), "resolved": version, "contentHash": "x=="}
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

    def test_a_stale_requested_range_is_stale_though_the_version_agrees(self):
        """A pin that changes form but not version leaves `resolved` agreeing; the range still disagrees."""
        root = self.engine({
            "src/E/packages.lock.json": nuget_lock({"RulesKernel": "0.2.0", "RulesFactory.Maps.HoyleBackgammon": "5.0.0"},
                                                   requested={"RulesKernel": "[0.2.0, 0.2.0]",
                                                              "RulesFactory.Maps.HoyleBackgammon": "[5.0.0, )"}),
        })
        self.assertEqual(verify_step.stale_locks(root, self.PINS), [
            ("src/E/packages.lock.json", "RulesKernel", "[0.2.0, 0.2.0]", "0.2.0"),
            ("src/E/packages.lock.json", "RulesFactory.Maps.HoyleBackgammon", "[5.0.0, )", "[5.0.0]"),
        ])

    def test_ranges_compare_as_nuget_writes_them(self):
        root = self.engine({
            "src/E/packages.lock.json": nuget_lock({"RulesKernel": "0.2.0", "RulesFactory.Maps.HoyleBackgammon": "5.0.0"},
                                                   requested={"RulesKernel": "[0.2, )",
                                                              "RulesFactory.Maps.HoyleBackgammon": "[5.0.0.0,5.0.0]"}),
        })
        self.assertEqual(verify_step.stale_locks(root, self.PINS), [])

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
    """--no-verify builds nothing, but re-locks lock files the generated pins have moved past, or refuses."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.nupkg_bumped = pack_version(HOYLE, "7.0.0", cls.shared)
        cls.kernel = verify_step.read_pins(cls.base)["ruleskernel"]
        cls.map_id = f"RulesFactory.Maps.{NAME}"
        assert cls.map_id.lower() in verify_step.read_pins(cls.base)

    LOCKS = (f"src/{NAME}/packages.lock.json", f"tests/{NAME}.Tests/packages.lock.json")

    def write_locks(self, map_version, requested=None):
        pins = {"RulesKernel": self.kernel, self.map_id: map_version}
        for relative, text in zip(self.LOCKS, (nuget_lock(pins, requested=requested),
                                               nuget_lock(pins, transitive=True, requested=requested))):
            with open(os.path.join(self.engine, *relative.split("/")), "w", encoding="utf-8") as handle:
                handle.write(text)

    def produce_bumped(self, *extra, **env):
        with mock.patch.dict(os.environ, {"CI": "", "FACTORY_DOTNET_SDK_OVERRIDE": "", **env}):
            return run(["produce", "--package", self.nupkg_bumped, "--corpus", CORPUS, "--name", NAME,
                        "--out", self.engine, "--allow-dirty", *extra])

    def command(self, override=None):
        return ((f"FACTORY_DOTNET_SDK_OVERRIDE={override} " if override else "")
                + f"python3 tools/factory produce --package {self.nupkg_bumped} --corpus {CORPUS} --name {NAME} "
                  f"--out {self.engine} --allow-dirty --no-verify")

    def assert_refused_unchanged(self, before, code, output):
        self.assertEqual(code, 1, output)
        self.assertIn("REFUSED -- --no-verify must re-lock the lock files that disagree with the generated pins", output)
        for relative in self.LOCKS:
            self.assertIn(f"{relative}: {self.map_id} locked at 6.0.0, pinned at [7.0.0]", output)
        self.assertIn("Nothing was produced.", output)
        self.assertNotIn("re-locks them", output)
        self.assertNotIn("--no-verify: re-locked", output)
        self.assertEqual(before, snapshot(self.engine))
        self.assertEqual([n for n in os.listdir(self.tmp) if ".factory-produce-" in n], [])

    def test_stale_lock_files_are_re_locked_recorded_and_committed_unverified(self):
        self.write_locks("6.0.0")
        code, output = self.produce_bumped("--no-verify", **self.env)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertEqual(self.dotnet_calls(), ["--version", "restore --force-evaluate"], "restore only: no build, no test")
        self.assertEqual(self.gate_calls, [])
        self.assertIn(f"--no-verify: re-locked the lock files that disagreed with the generated pins", output)
        self.assertIn("verification SKIPPED (--no-verify)", output)
        self.assertEqual(output.splitlines()[-1],
                         f"produced {NAME} in {self.engine}, NOT VERIFIED" + NOT_VERIFIED_TAIL)
        self.assertEqual(verify_step.stale_locks(self.engine, verify_step.read_pins(self.engine)), [])
        with open(os.path.join(self.engine, "provenance.json"), encoding="utf-8") as handle:
            recorded = {i["path"]: i["sha256"] for i in json.load(handle)["buildInputs"]
                        if i["path"].endswith("packages.lock.json")}
        self.assertEqual(sorted(recorded), sorted(self.LOCKS))
        for relative in self.LOCKS:
            with open(os.path.join(self.engine, *relative.split("/")), "rb") as handle:
                data = handle.read()
            self.assertIn(b"[7.0.0]", data)
            self.assertEqual(recorded[relative], hashlib.sha256(data).hexdigest())
        for directory, dirs, _ in os.walk(self.engine):
            self.assertFalse({"bin", "obj"} & set(dirs), directory)
        code, recomputed = run(["provenance", "--engine", self.engine, "--package", self.nupkg_bumped])
        self.assertEqual(code, 0, recomputed)

    def test_the_relock_runs_on_the_sdk_override_and_commits_the_pinned_global_json(self):
        self.write_locks("6.0.0")
        sdk_log = os.path.join(self.tmp, "sdk.log")
        with open(os.path.join(self.engine, "global.json"), "rb") as handle:
            pinned_bytes = handle.read()
        pinned = verify_step.pinned_sdk(self.engine)
        code, output = self.produce_bumped("--no-verify", FACTORY_DOTNET_SDK_OVERRIDE="10.0.1",
                                           FAKE_DOTNET_SDK_LOG=sdk_log, **self.env)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        with open(sdk_log, encoding="utf-8") as handle:
            self.assertEqual(handle.read().splitlines(), ["--version 10.0.1", "restore 10.0.1"])
        with open(os.path.join(self.engine, "global.json"), "rb") as handle:
            self.assertEqual(handle.read(), pinned_bytes)
        self.assertIn(f"WARNING: FACTORY_DOTNET_SDK_OVERRIDE=10.0.1 replaces the pinned SDK {pinned}", output)
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {self.engine}, NOT VERIFIED, lock files "
                                                  f"re-locked on SDK 10.0.1 by FACTORY_DOTNET_SDK_OVERRIDE, not the pinned "
                                                  f"{pinned}" + NOT_VERIFIED_TAIL)

    def test_without_any_sdk_the_refusal_names_the_pinned_sdk_and_the_command(self):
        self.write_locks("6.0.0")
        before = snapshot(self.engine)
        code, output = self.produce_bumped("--no-verify", **{**self.env, "FACTORY_DOTNET": os.path.join(self.tmp, "no", "dotnet")})
        self.assert_refused_unchanged(before, code, output)
        self.assertIn(f"no .NET SDK can run here", output)
        self.assertIn(f"install the .NET SDK {verify_step.pinned_sdk(self.engine)}, then run `{self.command()}`", output)

    def test_without_any_sdk_nothing_before_the_refusal_says_restore_re_locks(self):
        """No SDK runs, so no restore runs: the lock files are named by the refusal alone."""
        self.write_locks("6.0.0")
        code, output = self.produce_bumped("--no-verify", **{**self.env, "FACTORY_DOTNET": os.path.join(self.tmp, "no", "dotnet")})
        self.assertEqual(code, 1, output)
        (refusal,) = [line for line in output.splitlines() if "locked at 6.0.0" in line]
        self.assertIn("REFUSED -- --no-verify must re-lock", refusal)
        self.assertNotIn("--- relock", output)

    def test_without_the_pinned_sdk_the_refusal_names_the_override_at_an_installed_one(self):
        self.write_locks("6.0.0")
        before = snapshot(self.engine)
        code, output = self.produce_bumped("--no-verify", FAKE_DOTNET_FAIL="--version",
                                           FAKE_DOTNET_SDKS="8.0.100 10.0.111", **self.env)
        self.assert_refused_unchanged(before, code, output)
        self.assertEqual(self.dotnet_calls(), ["--version", "--list-sdks"])
        self.assertIn(f"with one that is, run `{self.command('10.0.111')}`", output)

    def test_a_failing_relock_is_refused(self):
        self.write_locks("6.0.0")
        before = snapshot(self.engine)
        code, output = self.produce_bumped("--no-verify", FAKE_DOTNET_FAIL="restore", **self.env)
        self.assert_refused_unchanged(before, code, output)
        self.assertIn("the re-lock failed: dotnet restore failed", output)

    def test_lock_files_a_relock_leaves_stale_are_never_committed(self):
        """#123's guarantee: whatever the relock did, stale lock files are refused, not committed."""
        self.write_locks("6.0.0")
        before = snapshot(self.engine)
        with mock.patch.object(verify_step, "relock", lambda engine, log: None):
            code, output = self.produce_bumped("--no-verify", **self.env)
        self.assert_refused_unchanged(before, code, output)
        self.assertIn("after re-locking they still disagree", output)

    def test_lock_files_already_re_locked_are_committed_unverified(self):
        self.write_locks("7.0.0")
        before = snapshot(self.engine)
        code, output = self.produce_bumped("--no-verify", **self.env)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertEqual(self.dotnet_calls(), [], "lock files that agree need no dotnet")
        self.assertEqual(output.splitlines()[-1],
                         f"produced {NAME} in {self.engine}, NOT VERIFIED" + NOT_VERIFIED_TAIL)
        self.assertEqual(verify_step.read_pins(self.engine)[self.map_id.lower()], "[7.0.0]")
        after = snapshot(self.engine)
        for relative in self.LOCKS:
            self.assertEqual(before[relative.replace("/", os.sep)], after[relative.replace("/", os.sep)])

    def test_lock_files_whose_requested_range_alone_is_stale_are_re_locked(self):
        """The version agrees with the pin, the range does not: a locked restore refuses it, so it re-locks."""
        self.write_locks("7.0.0", requested={self.map_id: "[7.0.0, )"})
        code, output = self.produce_bumped("--no-verify", **self.env)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertEqual(self.dotnet_calls(), ["--version", "restore --force-evaluate"])
        self.assertIn(f"{self.LOCKS[0]}: {self.map_id} locked at [7.0.0, ), pinned at [7.0.0]", output)
        self.assertEqual(verify_step.stale_locks(self.engine, verify_step.read_pins(self.engine)), [])

    def test_lock_files_whose_requested_range_a_relock_leaves_stale_are_never_committed(self):
        self.write_locks("7.0.0", requested={self.map_id: "[7.0.0, )"})
        before = snapshot(self.engine)
        with mock.patch.object(verify_step, "relock", lambda engine, log: None):
            code, output = self.produce_bumped("--no-verify", **self.env)
        self.assertEqual(code, 1, output)
        self.assertIn("after re-locking they still disagree", output)
        self.assertEqual(before, snapshot(self.engine))

    def test_an_engine_without_lock_files_is_unaffected(self):
        code, output = self.produce_bumped("--no-verify", **self.env)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertEqual(self.dotnet_calls(), [])
        self.assertEqual(verify_step.read_pins(self.engine)[self.map_id.lower()], "[7.0.0]")

    def test_the_verify_path_still_re_locks_stale_lock_files(self):
        self.write_locks("6.0.0")
        code, output = self.produce_bumped(**self.env)
        self.assertEqual(code, 0, output)
        self.assertIn("the generated pins changed, so this restore re-locks the 2 lock file(s)", output)
        self.assertEqual(output.splitlines()[-1], f"produced {NAME} in {self.engine}, verified")


if __name__ == "__main__":
    unittest.main()
