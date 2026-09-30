#!/usr/bin/env python3
"""tools/validate-engine.py, in the parts that need no dotnet (#172).

The checks themselves build and test a real engine, and are CI's `engine` job to run. What is
asserted here is what the shell it replaced could never have had a test for: the arguments it
takes, the SDK pin it prints for CI, the override refused before anything runs when CI=true, the
exact failure and step lines, and the helpers the checks lean on -- the local feed, the restored
package's hashes, and the `produce --no-verify` exit code it accepts.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import base64
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
TOOL = os.path.join(ROOT, "tools", "validate-engine.py")
WRAPPER = os.path.join(ROOT, "scripts", "validate-engine.sh")

_spec = importlib.util.spec_from_file_location("validate_engine", TOOL)
engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engine)
# The real one, kept before a test patches the module's name to put its logs where they are cleaned up.
_brief_log = engine.brief_log

NUGET_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
  <packageSourceMapping>
    <packageSource key="nuget.org">
      <package pattern="*" />
    </packageSource>
  </packageSourceMapping>
</configuration>
"""


def generate_pin():
    spec = importlib.util.spec_from_file_location("generate_pin_for_test", os.path.join(ROOT, "tools", "factory", "generate.py"))
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.join(ROOT, "tools", "factory"))
    spec.loader.exec_module(module)
    return module.SDK_VERSION


def run_main(argv, **environ):
    """main(argv) under `environ` added to this process's, its cwd put back: (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    cwd = os.getcwd()
    try:
        with mock.patch.dict(os.environ, environ), redirect_stdout(out), redirect_stderr(err):
            code = engine.main(argv)
    finally:
        os.chdir(cwd)
    return code, out.getvalue(), err.getvalue()


class Arguments(unittest.TestCase):
    def test_print_sdk_prints_the_pin_generate_py_writes(self):
        code, out, err = run_main(["--print-sdk"])
        self.assertEqual((code, out, err), (0, generate_pin() + "\n", ""))

    def test_print_sdk_ignores_what_follows_it_as_the_shell_did(self):
        code, out, _ = run_main(["--print-sdk", "extra"])
        self.assertEqual((code, out), (0, generate_pin() + "\n"))

    def test_print_sdk_is_not_refused_under_ci_with_an_override(self):
        """CI reads the pin before setting up .NET; the override is refused only for a run."""
        code, out, _ = run_main(["--print-sdk"], CI="true", FACTORY_DOTNET_SDK_OVERRIDE="1.2.3")
        self.assertEqual((code, out), (0, generate_pin() + "\n"))

    def test_any_other_argument_is_a_usage_error_naming_the_entry_point(self):
        code, out, err = run_main(["--full"], VALIDATE_ENGINE_ARGV0="./scripts/validate-engine.sh")
        self.assertEqual((code, out, err), (2, "", "usage: ./scripts/validate-engine.sh [--print-sdk] [--brief]\n"))

    def test_the_wrapper_passes_arguments_exit_codes_and_its_name_through(self):
        pin = subprocess.run([WRAPPER, "--print-sdk"], capture_output=True, text=True)
        self.assertEqual((pin.returncode, pin.stdout), (0, generate_pin() + "\n"), pin.stderr)
        bad = subprocess.run([WRAPPER, "nope"], capture_output=True, text=True)
        self.assertEqual((bad.returncode, bad.stderr), (2, f"usage: {WRAPPER} [--print-sdk] [--brief]\n"))

    def test_the_wrapper_stays_a_wrapper(self):
        self.assertLess(os.path.getsize(WRAPPER), 2048)


# The names main() calls after the SDK check, in order. The brief tests below run main() with each
# replaced by a fake that prints what a real step prints; test_the_list_is_what_main_calls holds
# this list to main's source, so a step added there cannot slip past a test that then runs it.
STEP_FUNCTIONS = [
    "pack_the_map", "produce_from_scratch", "reproduce_verifying",
    "the_restored_package_is_the_packed_one", "provenance_recomputes",
    "a_seeded_engine_references_randomness", "a_mistyped_handler_is_a_build_error",
    "a_stale_record_fails_the_gate", "a_request_input_reaches_its_handler",
    "an_owners_ruling_is_surfaced", "reproduce_beside_the_engines_own_projects",
    "a_map_version_bump_relocks", "the_rails_run_in_a_produced_engine",
    "a_determinism_defect_stops_the_build", "every_other_example_passes_its_gate",
    "a_composed_engine_passes_its_gate",
]


class BriefPrintsLessAndProvesTheSame(unittest.TestCase):
    """`--brief`: the same steps, the same verdicts, the same exit code, and a passing run that
    says what it proved rather than everything it did (#476, the rule #470 settled).

    A green run of this script is 720 lines and 45 KB, and almost none of it is evidence anybody
    reads on a pass. What must not move is anything else, so the tests are mostly about that: a
    failing step still prints everything it printed, `NOT VERIFIED` is counted rather than
    dropped, the exit code is the one a loud run gives, and the whole output is really kept where
    the run says it is.
    """

    def setUp(self):
        self.calls = []
        self.behaviours = {}

        def make(name):
            def fake(r):
                self.calls.append(name)
                behaviour = self.behaviours.get(name)
                if behaviour is not None:
                    return behaviour()
                # Noise a real step makes: this module's own print, and a subprocess writing to
                # fd 1 and fd 2 directly, which is where the engine gates and `dotnet` write.
                engine.step(f"step {name}")
                print(f"noise from {name}")
                subprocess.run(["sh", "-c", f"echo child stdout of {name}; echo child stderr of {name} >&2"])
                engine.ok(f"verdict of {name}")
            return fake

        patches = [mock.patch.object(engine, name, make(name)) for name in STEP_FUNCTIONS]
        patches.append(mock.patch.object(engine, "the_sdk_is_installed", lambda sdk: None))
        self.logs = []

        def log_that_is_cleaned_up(*args, **kwargs):
            path = _brief_log(*args, **kwargs)
            self.logs.append(path)
            self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
            return path
        patches.append(mock.patch.object(engine, "brief_log", log_that_is_cleaned_up))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_the_list_is_what_main_calls(self):
        import ast
        with open(TOOL, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        called = [n.value.func.id for n in ast.walk(main)
                  if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                  and isinstance(n.value.func, ast.Name)
                  and [a.id for a in n.value.args if isinstance(a, ast.Name)] == ["r"]]
        self.assertEqual(called, STEP_FUNCTIONS)

    def test_the_same_steps_run_in_the_same_order_with_the_same_exit_code(self):
        loud_code, loud, _ = run_main([])
        loud_calls, self.calls = self.calls, []
        brief_code, brief, _ = run_main(["--brief"])
        self.assertEqual(loud_calls, STEP_FUNCTIONS)
        self.assertEqual(self.calls, STEP_FUNCTIONS, "brief ran a different list of steps")
        self.assertEqual((loud_code, brief_code), (0, 0))
        self.assertIn("validate-engine.sh: PASS", brief)

    def test_a_passing_step_prints_its_heading_and_its_verdict_and_not_what_it_did(self):
        _, loud, _ = run_main([])
        _, out, _ = run_main(["--brief"])
        for name in STEP_FUNCTIONS:
            self.assertIn(f"==> step {name}\nok   verdict of {name}\n", out)
            self.assertNotIn(f"noise from {name}", out)
            self.assertNotIn(f"child stdout of {name}", out)
            self.assertNotIn(f"child stderr of {name}", out)
        self.assertLess(len(out), len(loud), "brief did not print less")

    def test_a_step_that_wrote_no_verdict_prints_the_last_line_it_printed(self):
        def silent():
            engine.step("a step whose tool says its own count")
            print("many lines")
            print("3 lock file(s) compared")
        self.behaviours["pack_the_map"] = silent
        _, out, _ = run_main(["--brief"])
        self.assertIn("==> a step whose tool says its own count\n3 lock file(s) compared\n", out)
        self.assertNotIn("many lines", out)

    def test_the_whole_of_it_is_in_the_log_the_run_names(self):
        _, out, _ = run_main(["--brief"])
        (log,) = self.logs
        self.assertIn(f"the whole output of every step above: {log}", out)
        self.assertTrue(os.path.isfile(log))
        with open(log, encoding="utf-8") as handle:
            kept = handle.read()
        for name in STEP_FUNCTIONS:
            for said in (f"==> step {name}", f"noise from {name}", f"child stdout of {name}",
                         f"child stderr of {name}", f"verdict of {name}"):
                self.assertIn(said, kept, "a log the run names must hold what the run hid")

    def test_the_log_is_named_before_the_first_step_and_is_outside_the_checkout(self):
        _, out, _ = run_main(["--brief"])
        (log,) = self.logs
        self.assertLess(out.index(f"the whole output is in {log}"), out.index("==> step pack_the_map"))
        self.assertFalse(os.path.realpath(log).startswith(os.path.realpath(ROOT) + os.sep))

    def test_a_failing_step_prints_everything_it_printed_and_stops_with_its_code(self):
        def fails():
            engine.step("the step that breaks")
            print("the first clue")
            sys.stdout.flush()
            subprocess.run(["sh", "-c", "echo the second clue >&2"])
            engine.ok("a check that passed first")
            engine.fail("something broke")
        self.behaviours["provenance_recomputes"] = fails
        code, out, err = run_main(["--brief"])
        self.assertEqual(code, 1)
        for clue in ("the first clue", "the second clue", "ok   a check that passed first",
                     "validate-engine.sh: FAIL -- something broke"):
            self.assertIn(clue, out + err, "a failure's output is the diagnosis")
        self.assertNotIn("a_seeded_engine_references_randomness", out + err, "nothing runs after a failure")
        self.assertEqual(self.calls[-1], "provenance_recomputes")
        (log,) = self.logs
        self.assertIn(f"the whole output of every step above: {log}", out)
        with open(log, encoding="utf-8") as handle:
            self.assertIn("the second clue", handle.read())

    def test_a_failure_gives_the_exit_code_a_loud_run_gives(self):
        def stops_with_seven():
            engine.step("a command that fails")
            engine.check(7)
        self.behaviours["pack_the_map"] = stops_with_seven
        loud = run_main([])[0]
        quiet = run_main(["--brief"])[0]
        self.assertEqual((loud, quiet), (7, 7))

    def test_an_exception_still_prints_the_step_it_interrupted_and_puts_the_descriptors_back(self):
        def explodes():
            engine.step("a step that raises")
            print("as far as it got")
            raise RuntimeError("the thing that went wrong")
        self.behaviours["produce_from_scratch"] = explodes
        before = os.fstat(1).st_ino, os.fstat(2).st_ino
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), self.assertRaises(RuntimeError):
            engine.main(["--brief"])
        self.assertIn("as far as it got", out.getvalue())
        self.assertEqual((os.fstat(1).st_ino, os.fstat(2).st_ino), before)
        self.assertIsNone(engine.BRIEF, "a later run in this process would inherit a stale capture")
        (log,) = self.logs
        with open(log, encoding="utf-8") as handle:
            self.assertIn("as far as it got", handle.read())

    def test_a_not_verified_is_counted_rather_than_dropped(self):
        """A step that passed while examining nothing is the defect this repository has found in
        its own tools twice. Brief may make it quieter; it may not make it invisible."""
        def unverified():
            engine.step("a produce that is not verified")
            print("[skip] status: NOT VERIFIED -- nothing to exercise")
            print("produced X, NOT VERIFIED -- nothing was built or tested")
            print("2 files written")
        self.behaviours["pack_the_map"] = unverified
        _, out, _ = run_main(["--brief"])
        (log,) = self.logs
        self.assertIn(f"2 NOT VERIFIED in this step, named in {log}", out)
        self.assertNotIn("[skip] status", out)

    def test_a_step_with_nothing_unverified_says_nothing_about_it(self):
        self.assertNotIn("NOT VERIFIED", run_main(["--brief"])[1])

    def test_output_before_the_first_step_is_printed_in_full(self):
        """A refusal or a warning has no heading and no verdict to reduce it to."""
        with mock.patch.object(engine, "sdk_override", return_value="9.9.9"), \
                mock.patch.object(engine, "verify_module") as module:
            module.return_value.override_warning.return_value = "warning: the SDK is overridden"
            _, out, err = run_main(["--brief"])
        self.assertIn("warning: the SDK is overridden", out + err)

    def test_a_temporary_directory_inside_the_checkout_is_refused(self):
        inside = tempfile.mkdtemp(prefix=".brief-tmp-for-a-test-", dir=ROOT)
        self.addCleanup(lambda: os.path.isdir(inside) and os.rmdir(inside))
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(engine.Stop) as refused:
            _brief_log(inside)
        self.assertEqual(refused.exception.code, 2)
        self.assertIn("inside the checkout", err.getvalue())
        self.assertIn("$TMPDIR", err.getvalue())
        self.assertEqual(os.listdir(inside), [], "a refused run wrote a log anyway")

    def test_brief_is_accepted_beside_print_sdk_and_any_other_argument_is_still_refused(self):
        code, out, _ = run_main(["--brief", "--print-sdk"])
        self.assertEqual((code, out), (0, generate_pin() + "\n"))
        code, out, err = run_main(["--brief", "--nope"], VALIDATE_ENGINE_ARGV0="x")
        self.assertEqual((code, out, err), (2, "", "usage: x [--print-sdk] [--brief]\n"))


class Override(unittest.TestCase):
    def test_the_override_is_refused_when_ci_is_true_before_anything_runs(self):
        with mock.patch.object(engine, "the_sdk_is_installed") as installed:
            code, out, err = run_main([], CI="true", FACTORY_DOTNET_SDK_OVERRIDE="10.0.111")
        installed.assert_not_called()
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(err, "FACTORY_DOTNET_SDK_OVERRIDE is for local runs only and is refused when CI=true\n"
                              "validate-engine.sh: FAIL -- the SDK override was refused (above)\n")

    def test_an_accepted_override_warns_and_is_the_sdk_checked(self):
        with mock.patch.dict(os.environ, {"CI": "false"}), \
                mock.patch.object(engine, "the_sdk_is_installed", side_effect=engine.Stop(1)) as installed:
            code, _, err = run_main([], FACTORY_DOTNET_SDK_OVERRIDE="9.9.9")
        installed.assert_called_once_with("9.9.9")
        self.assertEqual(code, 1)
        self.assertIn(f"WARNING: FACTORY_DOTNET_SDK_OVERRIDE=9.9.9 replaces the pinned SDK {generate_pin()}", err)

    def test_repin_rewrites_global_json_only_under_the_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "global.json")
            original = json.dumps({"sdk": {"version": "10.0.112", "rollForward": "disable"}}, indent=2) + "\n"
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(original)
            engine.Run("10.0.112", "10.0.112", directory).repin_sdk(directory)
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), original)
            run = engine.Run("10.0.112", "10.0.111", directory)
            run.repin_sdk(directory)
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["sdk"], {"version": "10.0.111", "rollForward": "disable"})
            self.assertEqual(run.adopt(), ["--adopt", "NuGet.config", "--adopt", "global.json"])
            self.assertEqual(engine.Run("1", "1", directory).adopt(), ["--adopt", "NuGet.config"])


class Messages(unittest.TestCase):
    def test_fail_prints_the_one_failure_line_and_stops_with_1(self):
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(engine.Stop) as stopped:
            engine.fail("something broke")
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(err.getvalue(), "validate-engine.sh: FAIL -- something broke\n")

    def test_step_and_ok_lines(self):
        out = io.StringIO()
        with redirect_stdout(out):
            engine.step("a step")
            engine.ok("a check")
        self.assertEqual(out.getvalue(), "\n==> a step\nok   a check\n")

    def test_check_carries_a_command_exit_code_out_unchanged(self):
        engine.check(0)
        with self.assertRaises(engine.Stop) as stopped:
            engine.check(7)
        self.assertEqual(stopped.exception.code, 7)

    def test_a_verifying_produce_runs_under_ci_without_the_override(self):
        with mock.patch.dict(os.environ, {"FACTORY_DOTNET_SDK_OVERRIDE": "1.2.3", "CI": "false"}):
            env = engine.verified_produce_env()
        self.assertEqual(env["CI"], "true")
        self.assertNotIn("FACTORY_DOTNET_SDK_OVERRIDE", env)


class Greps(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.log = os.path.join(self._tmp.name, "log")
        with open(self.log, "w", encoding="utf-8") as handle:
            handle.write("wrote to /x: 2 added, 1 changed, 0 removed\nrestore -- skipped\nproduced HoyleBackgammon, verified\n")

    def test_exact_fixed_and_pattern_matches_are_per_line(self):
        self.assertTrue(engine.grep_exact(self.log, "wrote to /x: 2 added, 1 changed, 0 removed"))
        self.assertFalse(engine.grep_exact(self.log, "wrote to /x: 2 added"))
        self.assertTrue(engine.grep_fixed(self.log, "2 added"))
        self.assertTrue(engine.grep(self.log, "^restore -- skipped$"))
        self.assertFalse(engine.grep(self.log, "skipped.*verified"))
        self.assertEqual(engine.matching(self.log, "^wrote to"), "wrote to /x: 2 added, 1 changed, 0 removed")

    def test_the_last_line_ends_verified(self):
        self.assertTrue(engine.last_line_verified(self.log))
        with open(self.log, "a", encoding="utf-8") as handle:
            handle.write("NOT VERIFIED\n")
        self.assertFalse(engine.last_line_verified(self.log))

    def test_an_unreadable_file_matches_nothing(self):
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertFalse(engine.grep_fixed(os.path.join(self._tmp.name, "missing"), ""))
        self.assertIn("grep:", err.getvalue())


class LocalFeed(unittest.TestCase):
    def test_the_map_packages_resolve_from_the_local_feed_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "NuGet.config")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(NUGET_CONFIG)
            engine.add_local_feed(path, "/scratch/package")
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        self.assertIn('<add key="local-map" value="/scratch/package" />', text)
        self.assertIn('<packageSource key="local-map"><package pattern="RulesFactory.Maps.*" /></packageSource>', text)

    def test_a_config_without_source_mapping_stops_the_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "NuGet.config")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("<configuration><packageSources /></configuration>")
            err = io.StringIO()
            with redirect_stderr(err), self.assertRaises(engine.Stop):
                engine.add_local_feed(path, "/feed")
        self.assertIn("has no packageSources or packageSourceMapping to extend", err.getvalue())


class RestoredPackage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = self._tmp.name
        self.package = os.path.join(root, "RulesFactory.Maps.Demo.1.2.3.nupkg")
        with zipfile.ZipFile(self.package, "w") as archive:
            archive.writestr("RulesFactory.Maps.Demo.nuspec",
                             "<package><metadata><id>RulesFactory.Maps.Demo</id><version>1.2.3</version></metadata></package>")
        with open(self.package, "rb") as handle:
            self.hash = base64.b64encode(hashlib.sha512(handle.read()).digest()).decode("ascii")
        self.cache = os.path.join(root, "cache")
        marker = os.path.join(self.cache, "rulesfactory.maps.demo", "1.2.3", "rulesfactory.maps.demo.1.2.3.nupkg.sha512")
        os.makedirs(os.path.dirname(marker))
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write(self.hash)
        self.engine = os.path.join(root, "engine")
        self.lock(self.hash)

    def lock(self, content_hash):
        path = os.path.join(self.engine, "src", "Demo", "packages.lock.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"dependencies": {"net10.0": {"RulesFactory.Maps.Demo": {"contentHash": content_hash}}}}, handle)

    def check(self):
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                engine.check_restored_package(self.engine, self.package, self.cache)
            except engine.Stop as stop:
                return stop.code, out.getvalue()
        return 0, out.getvalue()

    def test_the_packed_hash_everywhere_passes(self):
        self.assertEqual(self.check(), (0, "ok   RulesFactory.Maps.Demo 1.2.3: restored sha512 and 1 lock-file "
                                           "contentHash(es) equal the packed .nupkg\n"))

    def test_a_lock_file_pinning_another_hash_fails(self):
        self.lock("other")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("  X  src/Demo/packages.lock.json [net10.0] pins RulesFactory.Maps.Demo to other, not the packed .nupkg", out)

    def test_no_lock_file_naming_the_package_fails(self):
        os.remove(os.path.join(self.engine, "src", "Demo", "packages.lock.json"))
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("  X  no lock file names RulesFactory.Maps.Demo -- nothing was compared", out)


class Bytecode(unittest.TestCase):
    """The two helpers the #194 check reads the world through: what git would report, and what is
    on disk. They answer different questions, and the check needs both."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self._tmp.name
        subprocess.run(["git", "-C", self.repo, "init", "-q", "-b", "main"], check=True)

    def write(self, relative, text=""):
        path = os.path.join(self.repo, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def commit(self):
        identity = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]
        subprocess.run(["git", "-C", self.repo, *identity, "add", "-A"], check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run(["git", "-C", self.repo, *identity, "commit", "-qm", "x"], check=True,
                       stdout=subprocess.DEVNULL)

    def test_porcelain_is_empty_only_while_nothing_is_untracked_or_changed(self):
        self.write("scripts/factory/generate.py", "x\n")
        self.commit()
        self.assertEqual(engine.porcelain(self.repo), "")
        self.write("scripts/factory/__pycache__/generate.pyc", "")
        # The line dispatch-agent.sh printed when it refused on brandonifco/faa-part-107 (#194).
        self.assertEqual(engine.porcelain(self.repo), "?? scripts/factory/__pycache__/")

    def test_bytecode_dirs_finds_every_pycache_and_never_looks_inside_git(self):
        self.write("a.txt", "one\n")
        self.commit()
        self.assertEqual(engine.bytecode_dirs(self.repo), [])
        self.write("scripts/factory/__pycache__/generate.pyc", "")
        self.write("tools/__pycache__/x.pyc", "")
        os.makedirs(os.path.join(self.repo, ".git", "__pycache__"))
        self.assertEqual(engine.bytecode_dirs(self.repo),
                         [os.path.join("scripts", "factory", "__pycache__"), os.path.join("tools", "__pycache__")])

    def test_an_ignored_pycache_is_on_disk_but_not_in_git_status(self):
        """The distinction the #194 check rests on. A downstream engine whose .gitignore did name
        __pycache__ would leave git status clean while the bytecode was still written, so a check
        that only read porcelain() would pass on an unfixed tool."""
        self.write(".gitignore", "__pycache__/\n")
        self.commit()
        self.write("scripts/factory/__pycache__/generate.pyc", "")
        self.assertEqual(engine.porcelain(self.repo), "")
        self.assertEqual(engine.bytecode_dirs(self.repo), [os.path.join("scripts", "factory", "__pycache__")])


class UnverifiedProduce(unittest.TestCase):
    def status_for(self, code):
        err = io.BytesIO()
        with mock.patch.object(engine, "run", return_value=code) as run:
            status = engine.unverified_produce(["--name", "X"], stdout=io.BytesIO(), stderr=err)
        self.assertEqual(run.call_args.args[0][-1], "--no-verify")
        return status, err.getvalue()

    def test_not_verified_is_the_one_accepted_code(self):
        self.assertEqual(self.status_for(3), (0, b""))

    def test_zero_is_refused_with_why(self):
        self.assertEqual(self.status_for(0),
                         (1, b"produce --no-verify exited 0; an engine that was not built or tested must exit 3\n"))

    def test_any_other_code_passes_through(self):
        self.assertEqual(self.status_for(1), (1, b""))
        self.assertEqual(self.status_for(2), (2, b""))


class DescribeExample(unittest.TestCase):
    """The corpus a packed example is produced against is the committed copy its manifest names,
    resolved against the map directory. Taking the basename assumed every map owns its corpus
    copy, which stopped being true when four maps of SRD 5.2.1 came to share one (#446)."""

    def package(self, committed_path):
        path = os.path.join(self.tmp, "x.nupkg")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("x.nuspec", "<package><metadata><id>RulesFactory.Maps.Demo</id>"
                                         "</metadata></package>")
            archive.writestr("map/corpus-map.json", json.dumps({"corpus": "demo"}))
            archive.writestr("map/corpus-manifest.json", json.dumps({"corpora": [
                {"sourceId": "demo", "verification": "committed-copy",
                 "committedPath": committed_path}]}))
        return path

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)

    def test_a_corpus_in_the_map_directory(self):
        name, corpus, source = engine.describe_example(
            self.package("demo.txt"), os.path.join("examples", "demo"))
        self.assertEqual(("Demo", os.path.join("examples", "demo", "demo.txt"), "demo"),
                         (name, corpus, source))

    def test_a_corpus_committed_beside_the_map(self):
        _, corpus, _ = engine.describe_example(
            self.package("../shared/demo.txt"), os.path.join("examples", "demo"))
        self.assertEqual(os.path.join("examples", "shared", "demo.txt"), corpus)

    def test_a_corpus_that_is_not_committed_is_refused(self):
        path = os.path.join(self.tmp, "y.nupkg")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("x.nuspec", "<package><metadata><id>RulesFactory.Maps.Demo</id>"
                                         "</metadata></package>")
            archive.writestr("map/corpus-map.json", json.dumps({"corpus": "demo"}))
            archive.writestr("map/corpus-manifest.json", json.dumps({"corpora": [
                {"sourceId": "demo", "verification": "local-copy"}]}))
        with self.assertRaises(engine.Refused):
            engine.describe_example(path, os.path.join("examples", "demo"))


if __name__ == "__main__":
    unittest.main()
