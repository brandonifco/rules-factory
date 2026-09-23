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
        self.assertEqual((code, out, err), (2, "", "usage: ./scripts/validate-engine.sh [--print-sdk]\n"))

    def test_the_wrapper_passes_arguments_exit_codes_and_its_name_through(self):
        pin = subprocess.run([WRAPPER, "--print-sdk"], capture_output=True, text=True)
        self.assertEqual((pin.returncode, pin.stdout), (0, generate_pin() + "\n"), pin.stderr)
        bad = subprocess.run([WRAPPER, "nope"], capture_output=True, text=True)
        self.assertEqual((bad.returncode, bad.stderr), (2, f"usage: {WRAPPER} [--print-sdk]\n"))

    def test_the_wrapper_stays_a_wrapper(self):
        self.assertLess(os.path.getsize(WRAPPER), 2048)


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
