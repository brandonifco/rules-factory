#!/usr/bin/env python3
"""Where a licensed-copy engine's map comes from on the operator's machine (#142, decision 0028): local_map.py.

`dotnet` is a fake that does what NuGet's restore does to the global packages folder for the one
package a seeding project references: it reads the project's NuGet.config, takes the package from
the one source it names, and writes `<id>/<version>/<id>.<version>.nupkg` and its `.sha512` under
$NUGET_PACKAGES. scripts/validate-engine.sh seeds with the real dotnet and runs the engine's gate on
the result.

Asserted:

  * resolve -- a file is itself; Id@Version (given, or from a provenance record) is the global packages
    folder's when it is there, else the feed's file, matched without regard to case; strict, a
    missing feed variable, a relative or absent directory, a directory inside a git work tree and a
    feed without the file are each refused naming what to do; not strict, an unset variable and a
    feed without the file return the spec, and a variable that is set and wrong is still refused;
  * seed -- an absent package is restored through a project whose only package source is a copy of
    the one .nupkg, and the folder then holds it; a package already there with the same sha512 runs
    no dotnet; one with another sha512 is refused naming the directory to delete; a file whose
    sha256 is not the recorded one is refused before dotnet runs; a failing restore, and a restore
    that leaves nothing behind, are refused;
  * the CI a licensed-copy engine gets (recipe/validate-local-copy.yml) -- no step runs validate.sh; a
    job named `NOT VERIFIED: licensed map not available in CI` says so and cannot fail; triggers,
    permissions and action pins are the plain workflow's; its steps, read from the file and run: a
    committed corpus file or .nupkg fails, and only projects whose ProjectReference closure does
    not reach the engine project are restored, built and tested (none, for a fresh engine).

Run: python3 -m unittest discover -s tools/tests
"""
import base64
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.join(os.path.dirname(HERE), "factory")
sys.path.insert(0, FACTORY)

import intake  # noqa: E402
import local_map  # noqa: E402

sys.path.insert(0, HERE)
import workflow_steps  # noqa: E402

PACKAGE_ID = "RulesFactory.Maps.SyntheticLicensed"
VERSION = "1.0.0"

FAKE_DOTNET = r'''#!/usr/bin/env python3
import os, re, shutil, sys, base64, hashlib
args = sys.argv[1:]
with open(os.environ["FAKE_DOTNET_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join(args) + "\n")
if args[:1] == ["--version"]:
    print("10.0.111"); sys.exit(0)
if args[:1] != ["restore"]:
    sys.exit(2)
if os.environ.get("FAKE_RESTORE") == "fail":
    print("error NU1101: Unable to find package"); sys.exit(1)
project = open("Seed.csproj", encoding="utf-8").read()
package, version = re.search(r'Include="([^"]+)" Version="\[([^\]]+)\]"', project).groups()
config = open("NuGet.config", encoding="utf-8").read()
sources = re.findall(r'<add key="[^"]+" value="([^"]+)"', config)
assert "<clear />" in config and len(sources) == 1, config
with open(os.environ["FAKE_DOTNET_LOG"], "a", encoding="utf-8") as log:
    log.write("sources " + " ".join(sorted(os.listdir(sources[0]))) + " framework " + re.search(r"<TargetFramework>([^<]+)", project).group(1) + "\n")
if os.environ.get("FAKE_RESTORE") == "nothing":
    sys.exit(0)
(name,) = os.listdir(sources[0])
target = os.path.join(os.environ["NUGET_PACKAGES"], package.lower(), version.lower())
os.makedirs(target, exist_ok=True)
base = f"{package.lower()}.{version.lower()}.nupkg"
shutil.copyfile(os.path.join(sources[0], name), os.path.join(target, base))
with open(os.path.join(sources[0], name), "rb") as handle:
    digest = base64.b64encode(hashlib.sha512(handle.read()).digest()).decode()
with open(os.path.join(target, base + ".sha512"), "w") as handle:
    handle.write(digest)
'''


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.packages = os.path.join(self.tmp, "nuget-packages")
        self.feed = os.path.join(self.tmp, "feed")
        os.makedirs(self.feed)
        self.nupkg = os.path.join(self.feed, f"{PACKAGE_ID}.{VERSION}.nupkg")
        with open(self.nupkg, "wb") as handle:
            handle.write(b"PK synthetic package bytes")
        self.sha256 = hashlib.sha256(b"PK synthetic package bytes").hexdigest()
        self.dotnet = os.path.join(self.tmp, "dotnet")
        with open(self.dotnet, "w", encoding="utf-8") as handle:
            handle.write(FAKE_DOTNET)
        os.chmod(self.dotnet, 0o755)
        self.log = os.path.join(self.tmp, "dotnet.log")
        patcher = mock.patch.dict(os.environ, {"NUGET_PACKAGES": self.packages, "FAKE_DOTNET_LOG": self.log})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(local_map.FEED_VAR, None)
        os.environ.pop("FAKE_RESTORE", None)

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return handle.read().splitlines()

    def cache(self, data=None):
        directory = os.path.join(self.packages, PACKAGE_ID.lower(), VERSION)
        os.makedirs(directory, exist_ok=True)
        base = f"{PACKAGE_ID.lower()}.{VERSION}.nupkg"
        with open(self.nupkg, "rb") as handle:
            data = handle.read() if data is None else data
        with open(os.path.join(directory, base), "wb") as handle:
            handle.write(data)
        with open(os.path.join(directory, base + ".sha512"), "w", encoding="utf-8") as handle:
            handle.write(base64.b64encode(hashlib.sha512(data).digest()).decode())
        return directory


class TestResolve(Case):
    def test_a_file_is_itself(self):
        self.assertEqual(local_map.resolve(self.nupkg), self.nupkg)

    def test_a_cached_package_is_left_to_intake(self):
        self.cache()
        spec = f"{PACKAGE_ID}@{VERSION}"
        self.assertEqual(local_map.resolve(spec), spec)
        self.assertEqual(local_map.resolve(None, {"map": {"packageId": PACKAGE_ID, "version": VERSION}}), spec)

    def test_otherwise_the_feed_holds_it_whatever_the_case_of_its_name(self):
        lower = os.path.join(self.feed, os.path.basename(self.nupkg).lower())
        os.rename(self.nupkg, lower)
        with mock.patch.dict(os.environ, {local_map.FEED_VAR: self.feed}):
            self.assertEqual(local_map.resolve(f"{PACKAGE_ID}@{VERSION}"), lower)
            self.assertEqual(local_map.resolve(None, {"map": {"packageId": PACKAGE_ID, "version": VERSION}}), lower)

    def test_strict_refusals_name_what_to_do(self):
        spec = f"{PACKAGE_ID}@{VERSION}"
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", repo], check=True)
        for value, expected in ((None, f"${local_map.FEED_VAR} is not set"),
                                ("relative/feed", "not an absolute path to a directory"),
                                (os.path.join(self.tmp, "absent"), "not an absolute path to a directory"),
                                (repo, "inside a git work tree"),
                                (empty, f"holds no {PACKAGE_ID}.{VERSION}.nupkg")):
            with self.subTest(value=value):
                env = {local_map.FEED_VAR: value} if value else {}
                with mock.patch.dict(os.environ, env):
                    with self.assertRaisesRegex(intake.Refused, expected.replace("$", r"\$").replace(".", r"\.")):
                        local_map.resolve(spec)
                    if value in (None, empty):  # a variable that is set and wrong is refused either way
                        self.assertEqual(local_map.resolve(spec, strict=False), spec)


class TestSeed(Case):
    def seed(self, expected=None):
        return local_map.seed(self.nupkg, PACKAGE_ID, VERSION, expected or self.sha256, self.dotnet)

    def test_an_absent_package_is_restored_from_a_source_holding_only_it(self):
        line = self.seed()
        self.assertIn(f"put {PACKAGE_ID} {VERSION} from {self.nupkg}", line)
        calls = self.calls()
        self.assertEqual(calls[0], "--version")
        self.assertTrue(calls[1].startswith("restore Seed.csproj"), calls)
        self.assertEqual(calls[2], f"sources {os.path.basename(self.nupkg)} framework net10.0")
        directory = os.path.join(self.packages, PACKAGE_ID.lower(), VERSION)
        with open(os.path.join(directory, f"{PACKAGE_ID.lower()}.{VERSION}.nupkg"), "rb") as handle, \
                open(self.nupkg, "rb") as original:
            self.assertEqual(handle.read(), original.read())

    def test_the_same_package_already_there_runs_no_dotnet(self):
        self.cache()
        self.assertIn("already in the NuGet global packages folder", self.seed())
        self.assertEqual(self.calls(), [])

    def test_another_package_under_the_same_id_and_version_is_refused(self):
        directory = self.cache(b"PK other bytes")
        with self.assertRaisesRegex(intake.Refused, f"Delete {directory}"):
            self.seed()
        self.assertEqual(self.calls(), [])

    def test_a_package_that_is_not_the_recorded_one_is_refused_before_dotnet(self):
        with self.assertRaisesRegex(intake.Refused, "restore would take a different map"):
            self.seed(expected="0" * 64)
        self.assertEqual(self.calls(), [])

    def test_a_failing_restore_or_one_that_leaves_nothing_is_refused(self):
        for mode, expected in (("fail", "could not put .* NU1101"), ("nothing", "does not exist")):
            with self.subTest(mode=mode), mock.patch.dict(os.environ, {"FAKE_RESTORE": mode}):
                with self.assertRaisesRegex(intake.Refused, expected):
                    self.seed()


RECIPE = os.path.join(FACTORY, "recipe")
LOCAL_COPY_WORKFLOW = os.path.join(RECIPE, "validate-local-copy.yml")

FAKE_CI_DOTNET = r'''#!/usr/bin/env python3
import os, sys
with open(os.environ["FAKE_DOTNET_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join(sys.argv[1:]) + "\n")
sys.exit(1 if os.environ.get("FAKE_DOTNET_FAIL") and os.environ["FAKE_DOTNET_FAIL"] in sys.argv[1:2] else 0)
'''


class TestLocalCopyWorkflow(unittest.TestCase):
    """The CI a licensed-copy engine gets (0028): what needs no licensed input, then NOT VERIFIED."""

    @classmethod
    def setUpClass(cls):
        with open(LOCAL_COPY_WORKFLOW, encoding="utf-8") as handle:
            cls.text = handle.read()
        with open(os.path.join(RECIPE, "validate.yml"), encoding="utf-8") as handle:
            cls.plain = handle.read()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def step(self, name):
        (script,) = [script for step, script in workflow_steps.steps(self.text, "checks") if step == name]
        return script

    def test_it_never_runs_the_full_gate_and_says_not_verified_in_a_job_that_passes(self):
        self.assertNotRegex(self.text, r"(?m)^\s*run:.*validate\.sh", "the full gate needs the map; it runs locally only")
        self.assertIn('  not-verified:\n    name: "NOT VERIFIED: licensed map not available in CI"\n', self.text)
        (notice,) = workflow_steps.steps(self.text, "not-verified")
        self.assertIn("::warning title=NOT VERIFIED::licensed map not available in CI", notice[1])
        self.assertNotIn("exit 1", notice[1])
        self.assertNotIn("continue-on-error", self.text, "nothing that can fail is hidden as passing")
        self.assertIn("NOT VERIFIED: licensed map not available in CI", self.step("Say what was not verified"))

    def test_triggers_permissions_and_action_pins_are_the_plain_workflows(self):
        head = self.plain.split("\njobs:\n")[0].split("\non:\n", 1)[1]
        self.assertIn("\non:\n" + head + "\njobs:\n", self.text)
        pins = set(re.findall(r"uses: (\S+ # \S+)", self.plain))
        self.assertEqual(set(re.findall(r"uses: (\S+ # \S+)", self.text)), pins)
        self.assertEqual(len(pins), 2)

    def test_the_committed_bytes_check_refuses_a_corpus_file_or_a_package(self):
        script = self.step("No corpus bytes and no map package are committed")
        repo = os.path.join(self.tmp, "engine")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", repo], check=True)
        with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("engine\n")
        subprocess.run(["git", "-C", repo, "add", "README.md"], check=True)
        run = subprocess.run(["bash", "-c", script], cwd=repo, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        for path in ("corpus/synthetic.txt", "local/RulesFactory.Maps.X.1.0.0.nupkg"):
            with self.subTest(path=path):
                os.makedirs(os.path.join(repo, os.path.dirname(path)), exist_ok=True)
                with open(os.path.join(repo, path), "w", encoding="utf-8") as handle:
                    handle.write("x\n")
                subprocess.run(["git", "-C", repo, "add", path], check=True)
                run = subprocess.run(["bash", "-c", script], cwd=repo, capture_output=True, text=True)
                self.assertEqual(run.returncode, 1, run.stdout)
                self.assertIn(path, run.stdout)
                subprocess.run(["git", "-C", repo, "rm", "-q", "--cached", path], check=True)

    def project(self, root, relative, references=(), test=False):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        refs = "".join(f'<ProjectReference Include="{r}" />' for r in references)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f'<Project Sdk="Microsoft.NET.Sdk">'
                         f'{"<PropertyGroup><IsTestProject>true</IsTestProject></PropertyGroup>" if test else ""}'
                         f"<ItemGroup>{refs}</ItemGroup></Project>\n")

    def run_projects_step(self, **env):
        root = os.path.join(self.tmp, "engine")
        with open(os.path.join(root, "Deck.slnx"), "w", encoding="utf-8") as handle:
            handle.write("<Solution />\n")
        bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        with open(os.path.join(bin_dir, "dotnet"), "w", encoding="utf-8") as handle:
            handle.write(FAKE_CI_DOTNET)
        os.chmod(os.path.join(bin_dir, "dotnet"), 0o755)
        log = os.path.join(self.tmp, "dotnet.log")
        run = subprocess.run(["bash", "-c", self.step("Projects that do not depend on the map (locked restore, "
                                                      "build -warnaserror, test, Release)")],
                             cwd=root, capture_output=True, text=True,
                             env={**os.environ, "PATH": bin_dir + os.pathsep + os.environ["PATH"],
                                  "FAKE_DOTNET_LOG": log, **env})
        calls = open(log, encoding="utf-8").read().splitlines() if os.path.exists(log) else []
        return run, calls

    def test_only_projects_that_do_not_reach_the_engine_project_are_built(self):
        root = os.path.join(self.tmp, "engine")
        self.project(root, "src/Deck/Deck.csproj", ["../Dice/Dice.csproj"])
        self.project(root, "tests/Deck.Tests/Deck.Tests.csproj", ["../../src/Deck/Deck.csproj"], test=True)
        self.project(root, "src/Dice/Dice.csproj")
        self.project(root, "tests/Dice.Tests/Dice.Tests.csproj", ["../../src/Dice/Dice.csproj"], test=True)
        self.project(root, "src/Deck/obj/Stale.csproj")
        run, calls = self.run_projects_step()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("4 project(s); 2 need the licensed map and are NOT VERIFIED here", run.stdout)
        self.assertEqual(calls, [
            "restore src/Dice/Dice.csproj --locked-mode",
            "build src/Dice/Dice.csproj -c Release --no-restore -warnaserror",
            "restore tests/Dice.Tests/Dice.Tests.csproj --locked-mode",
            "build tests/Dice.Tests/Dice.Tests.csproj -c Release --no-restore -warnaserror",
            "test tests/Dice.Tests/Dice.Tests.csproj -c Release --no-build",
        ])
        run, calls = self.run_projects_step(FAKE_DOTNET_FAIL="build")
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("FAIL dotnet build src/Dice/Dice.csproj", run.stderr)

    def test_a_fresh_engine_has_nothing_independent_and_says_so(self):
        root = os.path.join(self.tmp, "engine")
        self.project(root, "src/Deck/Deck.csproj")
        self.project(root, "tests/Deck.Tests/Deck.Tests.csproj", ["../../src/Deck/Deck.csproj"], test=True)
        run, calls = self.run_projects_step()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("no project is independent of the map, so nothing is built here", run.stdout)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
