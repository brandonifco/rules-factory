#!/usr/bin/env python3
"""`factory produce` (#3, M3) emits the gate that judges the engine, and the gate fails when it should.

Two layers:

  * **Without a .NET SDK** (always run): the recipe is emitted, executable and deterministic, and
    each non-dotnet check the gate runs -- scripts/map-overlay.py and scripts/engine-gate.py --
    passes on fresh output and fails on the mutation it exists for: a changed citation or a hand
    edit in a `*.g.cs`, an overlay key the map lacks, `implemented` without `tests`, a lock file
    or project resolving RulesKernel.Randomness, a corpus that is not the baseline.
  * **With a .NET SDK** (skipped cleanly when `dotnet` is absent, as in this repository's CI, or
    when RULES_FACTORY_SKIP_DOTNET is set): the emitted `scripts/validate.sh` itself passes on
    fresh output and fails on each of those mutations. The engine is a scratch copy: its
    global.json is re-pinned to the SDK installed here, and its NuGet.config gains a local folder
    feed holding the map package packed by tools/pack-map.py (Part 107 1.0.0 is not on
    nuget.org) and the user's global packages folder as a read-only fallback. Packages restore
    into a scratch NUGET_PACKAGES, so an unpublished map package never enters the user's cache.

Run: python3 -m unittest discover -s tools/tests
"""
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")

_spec = importlib.util.spec_from_file_location("factory_main_gate", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)

PART107 = os.path.join(REPO, "examples", "faa-part-107")
PART107_XML = os.path.join(PART107, "part107.xml")
NAME = "FaaPart107"
PACKAGE_ID = "RulesFactory.Maps.FaaPart107"
MAP_ENTRIES = f"src/{NAME}/Generated/MapEntries.g.cs"
REGISTRY = f"src/{NAME}/Generated/Registry.g.cs"
RECIPE = ("scripts/validate.sh", "scripts/map-overlay.py", "scripts/engine-gate.py",
          "scripts/factory/generate.py", "scripts/factory/intake.py", "scripts/factory/provenance.py", ".github/workflows/validate.yml")
IMPLEMENTED_IN = {"ruleset": "faa-part-107", "version": 1}


def pack(map_dir, out):
    subprocess.run([sys.executable, PACK, map_dir, "--out", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
    return os.path.join(out, name)


def produce(package, out):
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = factory.main(["produce", "--package", package, "--corpus", PART107_XML, "--name", NAME, "--out", out,
                             "--allow-dirty",  # this checkout's state is not under test here
                             "--no-verify"])  # nor is building it: no SDK assumed (test_factory_verify.py)
    if code != 0:
        raise AssertionError(buffer.getvalue())


def edit(path, change):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    changed = change(text)
    assert changed != text, f"the mutation did not change {path}"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(changed)


def write_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)


def change_a_citation(text):
    return text.replace('"§ 107.51(a)"', '"§ 107.51(b)"', 1)


def hand_edit(text):
    return text.replace("public static class Registry\n{\n", "public static class Registry\n{\n    // tweaked by hand\n", 1)


class GateCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        cls.nupkg = pack(PART107, os.path.join(cls.shared, "feed"))
        cls.package_map = os.path.join(cls.shared, "package-map.json")
        cls.package_manifest = os.path.join(cls.shared, "package-manifest.json")
        with zipfile.ZipFile(cls.nupkg) as archive:
            with open(cls.package_map, "wb") as handle:
                handle.write(archive.read("map/corpus-map.json"))
            with open(cls.package_manifest, "wb") as handle:
                handle.write(archive.read("map/corpus-manifest.json"))
            cls.checker = os.path.join(cls.shared, "check-map.py")
            with open(cls.checker, "wb") as handle:
                handle.write(archive.read("tools/check-map.py"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def engine(self):
        out = os.path.join(self.tmp, "engine")
        produce(self.nupkg, out)
        return out

    def script(self, engine, script, *args, env=None):
        completed = subprocess.run([sys.executable, os.path.join(engine, "scripts", script), *args], cwd=engine,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                   env={**os.environ, **(env or {})})
        return completed.returncode, completed.stdout

    def regenerate(self, engine):
        return self.script(engine, "engine-gate.py", "regenerate", "--package-map", self.package_map,
                           "--package-id", PACKAGE_ID, "--package-version", "1.0.0", "--name", NAME)

    def merge(self, engine):
        merged = os.path.join(self.tmp, "merged.json")
        code, output = self.script(engine, "map-overlay.py", "merge", "--package-map", self.package_map,
                                   "--overlay", os.path.join(engine, "corpus-map.overlay.json"), "--out", merged)
        return code, output, merged


class TestRecipeIsEmitted(GateCase):
    def test_every_recipe_file_is_written_and_the_scripts_are_executable(self):
        engine = self.engine()
        for relative in RECIPE:
            self.assertTrue(os.path.isfile(os.path.join(engine, *relative.split("/"))), relative)
        for relative in RECIPE[:3]:
            self.assertTrue(os.access(os.path.join(engine, *relative.split("/")), os.X_OK), relative)
        with open(os.path.join(engine, "scripts", "validate.sh"), encoding="utf-8") as handle:
            gate = handle.read()
        self.assertIn(f'NAME="{NAME}"', gate)
        self.assertNotIn("@NAME@", gate)
        subprocess.run(["bash", "-n", os.path.join(engine, "scripts", "validate.sh")], check=True)
        for module in ("generate.py", "intake.py", "provenance.py"):
            with open(os.path.join(FACTORY, module), "rb") as a, \
                    open(os.path.join(engine, "scripts", "factory", module), "rb") as b:
                self.assertEqual(a.read(), b.read(), "the gate regenerates with the factory's own generator")
        with open(os.path.join(engine, ".github", "workflows", "validate.yml"), encoding="utf-8") as handle:
            workflow = handle.read()
        self.assertEqual(re.findall(r"^\s*run: (.+)$", workflow, re.M)[-1], "./scripts/validate.sh full")
        with open(os.path.join(engine, "provenance.json"), encoding="utf-8") as handle:
            recorded = {item["path"] for item in json.load(handle)["generated"]}
        self.assertLessEqual(set(RECIPE), recorded, "provenance records every recipe file's bytes")

    def test_a_hand_edit_to_the_recipe_is_undone_by_the_next_produce(self):
        engine = self.engine()
        edit(os.path.join(engine, "scripts", "validate.sh"), lambda t: t.replace("set -euo pipefail", "exit 0", 1))
        produce(self.nupkg, engine)
        with open(os.path.join(engine, "scripts", "validate.sh"), encoding="utf-8") as handle:
            self.assertNotIn("exit 0\n", handle.read().split("NAME=")[0])


class TestGeneratedFilesMatchARegeneration(GateCase):
    def test_passes_on_fresh_output(self):
        code, output = self.regenerate(self.engine())
        self.assertEqual(code, 0, output)
        self.assertIn("6 generated file(s) match", output)

    def test_fails_on_a_changed_citation(self):
        engine = self.engine()
        edit(os.path.join(engine, *MAP_ENTRIES.split("/")), change_a_citation)
        code, output = self.regenerate(engine)
        self.assertEqual(code, 1, output)
        self.assertIn(f"{MAP_ENTRIES} differs from a fresh regeneration", output)
        self.assertIn("107.51(b)", output)

    def test_fails_on_a_hand_edit(self):
        engine = self.engine()
        edit(os.path.join(engine, *REGISTRY.split("/")), hand_edit)
        code, output = self.regenerate(engine)
        self.assertEqual(code, 1, output)
        self.assertIn(f"{REGISTRY} differs", output)

    def test_fails_on_a_stray_generated_file(self):
        engine = self.engine()
        with open(os.path.join(engine, "src", NAME, "Mine.g.cs"), "w", encoding="utf-8") as handle:
            handle.write("// not the factory's\n")
        code, output = self.regenerate(engine)
        self.assertEqual(code, 1, output)
        self.assertIn(f"src/{NAME}/Mine.g.cs is a *.g.cs file the factory does not generate", output)

    def test_fails_when_the_overlay_changed_without_a_regeneration(self):
        engine = self.engine()
        write_json(os.path.join(engine, "corpus-map.overlay.json"), {"speed-limit": {"status": "blocked"}})
        code, output = self.regenerate(engine)
        self.assertEqual(code, 1, output)
        produce(self.nupkg, engine)
        self.assertEqual(self.regenerate(engine)[0], 0)


class TestOverlayMerge(GateCase):
    def test_passes_on_fresh_output(self):
        code, output, merged = self.merge(self.engine())
        self.assertEqual(code, 0, output)
        with open(merged, encoding="utf-8") as a, open(self.package_map, encoding="utf-8") as b:
            self.assertEqual(json.load(a), json.load(b))

    def test_fails_on_an_overlay_key_not_in_the_map(self):
        engine = self.engine()
        write_json(os.path.join(engine, "corpus-map.overlay.json"), {"no-such-entry": {"status": "mapped"}})
        code, output, _ = self.merge(engine)
        self.assertEqual(code, 1, output)
        self.assertIn("'no-such-entry', which the package map has no entry for", output)

    def test_merge_rules_2_and_3(self):
        engine = self.engine()
        overlay = os.path.join(engine, "corpus-map.overlay.json")
        write_json(overlay, {"speed-limit": {"status": "mapped", "note": "mine"}})
        self.assertIn("sets 'note'", self.merge(engine)[1])
        write_json(overlay, {"speed-limit": {"tests": []}})
        self.assertIn("does not set status", self.merge(engine)[1])
        write_json(overlay, {"speed-limit": {"status": "blocked"}})
        code, output, merged = self.merge(engine)
        self.assertEqual(code, 0, output)
        with open(merged, encoding="utf-8") as handle:
            entry = json.load(handle)["entries"][0]
        with open(self.package_map, encoding="utf-8") as handle:
            upstream = json.load(handle)["entries"][0]
        self.assertEqual((entry["id"], entry["status"]), ("speed-limit", "blocked"))
        self.assertEqual(list(entry), list(upstream), "the overlay's status lands where upstream's was")
        self.assertEqual({k: v for k, v in entry.items() if k != "status"},
                         {k: v for k, v in upstream.items() if k != "status"})


class TestImplementedNamesItsTests(GateCase):
    def named(self, engine, merged, results=None):
        results = results or os.path.join(self.tmp, "no-results")
        os.makedirs(results, exist_ok=True)
        return self.script(engine, "engine-gate.py", "named-tests", results, "--map", merged)

    def test_passes_when_nothing_is_implemented(self):
        engine = self.engine()
        code, output = self.named(engine, self.merge(engine)[2])
        self.assertEqual(code, 0, output)

    def test_fails_on_implemented_without_tests(self):
        engine = self.engine()
        write_json(os.path.join(engine, "corpus-map.overlay.json"),
                   {"speed-limit": {"status": "implemented", "implementedIn": IMPLEMENTED_IN}})
        code, output, merged = self.merge(engine)
        self.assertEqual(code, 0, output)
        code, output = self.named(engine, merged)
        self.assertEqual(code, 1, output)
        self.assertIn("speed-limit: implemented, and names no test", output)
        # and the package's own consumer phase, which the gate also runs, refuses it
        checked = subprocess.run([sys.executable, self.checker, merged, "--manifest", self.package_manifest,
                                  "--phase", "consumer"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertNotEqual(checked.returncode, 0, checked.stdout)

    def test_fails_on_a_named_test_that_did_not_run(self):
        engine = self.engine()
        write_json(os.path.join(engine, "corpus-map.overlay.json"), {"speed-limit": {
            "status": "implemented", "implementedIn": IMPLEMENTED_IN,
            "tests": [{"test": "SpeedTests.Nobody_wrote_this", "mutation": "m"}]}})
        code, output = self.named(engine, self.merge(engine)[2])
        self.assertEqual(code, 1, output)
        self.assertIn("'SpeedTests.Nobody_wrote_this', which no result file shows running", output)

    def test_tests_ran_fails_on_no_result_files(self):
        engine = self.engine()
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        code, output = self.script(engine, "engine-gate.py", "tests-ran", empty, "2")
        self.assertEqual(code, 1, output)
        code, output = self.script(engine, "engine-gate.py", "expected-results")
        self.assertEqual(output.strip(), "2", "one test project x net8.0;net10.0")


class TestNoRandomness(GateCase):
    def lock(self, engine, packages):
        for project in (f"src/{NAME}", f"tests/{NAME}.Tests"):
            write_json(os.path.join(engine, *project.split("/"), "packages.lock.json"),
                       {"version": 1, "dependencies": {"net8.0": {p: {"type": "Transitive"} for p in packages}}})

    def gate(self, engine, command):
        return self.script(engine, "engine-gate.py", command)

    def test_lock_files_are_required(self):
        engine = self.engine()
        code, output = self.gate(engine, "lock-files")
        self.assertEqual(code, 1, output)
        self.assertIn("has no packages.lock.json", output)
        self.assertEqual(self.gate(engine, "no-randomness")[0], 1, "no lock file proves nothing")
        self.lock(engine, ["RulesKernel"])
        self.assertEqual(self.gate(engine, "lock-files")[0], 0)

    def test_passes_without_randomness(self):
        engine = self.engine()
        self.lock(engine, ["RulesKernel", PACKAGE_ID])
        code, output = self.gate(engine, "no-randomness")
        self.assertEqual(code, 0, output)

    def test_fails_when_a_lock_file_resolves_randomness(self):
        engine = self.engine()
        self.lock(engine, ["RulesKernel", "RulesKernel.Randomness"])
        code, output = self.gate(engine, "no-randomness")
        self.assertEqual(code, 1, output)
        self.assertIn("resolves RulesKernel.Randomness", output)

    def test_fails_when_a_project_references_randomness(self):
        engine = self.engine()
        self.lock(engine, ["RulesKernel"])
        edit(os.path.join(engine, "Directory.Packages.props"), lambda t: t.replace(
            "  </ItemGroup>", '    <PackageVersion Include="RulesKernel.Randomness" Version="0.2.0" />\n  </ItemGroup>', 1))
        code, output = self.gate(engine, "no-randomness")
        self.assertEqual(code, 1, output)
        self.assertIn("Directory.Packages.props references RulesKernel.Randomness", output)


class TestCorpusPosture(GateCase):
    def posture(self, engine, manifest=None, env=None):
        merged = self.merge(engine)[2]
        return self.script(engine, "engine-gate.py", "posture", "--manifest", manifest or self.package_manifest,
                           "--map", merged, "--name", NAME, env=env)

    def test_committed_copy_verifies(self):
        code, output = self.posture(self.engine())
        self.assertEqual(code, 0, output)
        self.assertIn("verified: cfr-14-107 (committed-copy", output)

    def test_a_changed_corpus_fails(self):
        engine = self.engine()
        with open(os.path.join(engine, "corpus", "part107.xml"), "ab") as handle:
            handle.write(b"\n")
        code, output = self.posture(engine)
        self.assertEqual(code, 1, output)
        self.assertIn("the manifest pins", output)

    def test_local_copy_without_its_bytes_is_not_verified_never_ok(self):
        engine = self.engine()
        with open(self.package_manifest, encoding="utf-8") as handle:
            manifest = json.load(handle)
        corpus = manifest["corpora"][0]
        corpus.update(verification="local-copy", boundaryPolicy="never-commit", envVar="FACTORY_TEST_CORPUS")
        corpus.pop("committedPath")
        path = os.path.join(self.tmp, "local-manifest.json")
        write_json(path, manifest)
        code, output = self.posture(engine, path, env={"FACTORY_TEST_CORPUS": ""})
        self.assertEqual(code, 3, output)
        self.assertIn("NOT VERIFIED", output)
        code, output = self.posture(engine, path, env={"FACTORY_TEST_CORPUS": PART107_XML})
        self.assertEqual(code, 0, output)


# --- the whole gate, with dotnet -------------------------------------------------------------


def _sdk():
    if os.environ.get("RULES_FACTORY_SKIP_DOTNET") or not shutil.which("dotnet"):
        return None
    try:
        version = subprocess.run(["dotnet", "--version"], cwd=tempfile.gettempdir(), stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return version if re.match(r"^10\.", version) else None


SDK = _sdk()


@unittest.skipUnless(SDK, "needs a .NET 10 SDK (dotnet on PATH); this repository's CI has none")
class TestValidateShWithDotnet(GateCase):
    """scripts/validate.sh, run for real. One fresh engine is locked once, then copied per mutation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.packages = os.path.join(cls.shared, "nuget-packages")
        cls.base = os.path.join(cls.shared, "base")
        produce(cls.nupkg, cls.base)
        cls.localize(cls.base)
        cls.fresh = cls.validate(cls.base, "lock")

    @classmethod
    def localize(cls, engine):
        """Scratch copy only: re-pin the SDK to the one installed, and restore the map from a folder feed."""
        path = os.path.join(engine, "global.json")
        with open(path, encoding="utf-8") as handle:
            pin = json.load(handle)
        pin["sdk"]["version"] = SDK
        write_json(path, pin)
        fallback = os.path.join(os.path.expanduser("~"), ".nuget", "packages")
        feed = os.path.dirname(cls.nupkg)
        edit(os.path.join(engine, "NuGet.config"), lambda t: t
             .replace("<clear />", f'<clear />\n    <add key="local-maps" value="{feed}" />', 1)
             .replace("  </packageSourceMapping>", '    <packageSource key="local-maps">\n'
                      '      <package pattern="RulesFactory.Maps.*" />\n    </packageSource>\n'
                      "  </packageSourceMapping>" + (f'\n  <fallbackPackageFolders>\n    <add key="user" value="{fallback}" />\n'
                                                     "  </fallbackPackageFolders>" if os.path.isdir(fallback) else ""), 1))

    @classmethod
    def validate(cls, engine, mode):
        env = {k: v for k, v in os.environ.items() if k not in ("CI", "MSBUILDNOINPROCNODE")}
        env["NUGET_PACKAGES"] = cls.packages
        completed = subprocess.run(["bash", os.path.join(engine, "scripts", "validate.sh"), mode], cwd=engine,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, timeout=900)
        return completed.returncode, completed.stdout

    def copy(self):
        engine = os.path.join(self.tmp, "engine")
        shutil.copytree(self.base, engine, ignore=shutil.ignore_patterns("bin", "obj"))
        return engine

    def assertFailsAt(self, result, *labels):
        code, output = result
        self.assertEqual(code, 1, output[-4000:])
        self.assertRegex(output, r"validate\.sh \w+: FAIL")
        for label in labels:
            self.assertIn(f"FAIL {label}", output, output[-4000:])

    def test_passes_on_fresh_output(self):
        code, output = self.fresh
        self.assertEqual(code, 0, output[-4000:])
        self.assertIn("validate.sh lock: PASS\n", output)
        for step in ("SDK ", "every project has a packages.lock.json", "dotnet restore --locked-mode",
                     "no lock file or project resolves RulesKernel.Randomness", "packaged check-map.py --phase consumer",
                     "every corpus verified", "every *.g.cs matches a fresh regeneration", "dotnet format",
                     "build Debug", "test Debug", "build Release", "test Release"):
            self.assertIn(f"ok   {step}", output)
        self.assertNotIn("FAIL", output)
        self.assertNotIn("skip ", output)
        # and full, which is what CI runs, passes on the committed lock files without rewriting them
        engine = self.copy()
        code, output = self.validate(engine, "full")
        self.assertEqual(code, 0, output[-4000:])
        self.assertIn("validate.sh full: PASS\n", output)

    def test_passes_with_an_implemented_entry_whose_tests_ran(self):
        engine = self.copy()
        os.makedirs(os.path.join(engine, "src", NAME, "Rules"))
        with open(os.path.join(engine, "src", NAME, "Rules", "Speed.cs"), "w", encoding="utf-8") as handle:
            handle.write("using RulesKernel.Resolution;\n\nnamespace FaaPart107.Rules;\n\n"
                         "internal static class Speed\n{\n"
                         "    [Implements(\"speed-limit\")]\n"
                         "    private static Resolution<object> Limit(RuleRequest request) =>\n"
                         "        Resolution<object>.FromValue(87);\n}\n")
        test = "CorrespondenceTests.speed_limit__is_implemented_so_a_hand_written_handler_answers_it"
        write_json(os.path.join(engine, "corpus-map.overlay.json"), {"speed-limit": {
            "status": "implemented", "implementedIn": IMPLEMENTED_IN, "tests": [{"test": test, "mutation": "m"}]}})
        produce(self.nupkg, engine)
        code, output = self.validate(engine, "full")
        self.assertEqual(code, 0, output[-4000:])
        self.assertIn("1 test(s) named by 1 implemented entries, every one found and executed in all 2", output)

    def test_fails_on_a_changed_citation_in_a_generated_file(self):
        engine = self.copy()
        edit(os.path.join(engine, *MAP_ENTRIES.split("/")), change_a_citation)
        self.assertFailsAt(self.validate(engine, "full"), "every *.g.cs matches a fresh regeneration (no hand edits)")

    def test_fails_on_an_overlay_key_not_in_the_map(self):
        engine = self.copy()
        write_json(os.path.join(engine, "corpus-map.overlay.json"), {"no-such-entry": {"status": "mapped"}})
        self.assertFailsAt(self.validate(engine, "full"),
                           f"merge({PACKAGE_ID}@1.0.0, corpus-map.overlay.json) obeys 0015")

    def test_fails_on_implemented_without_tests(self):
        engine = self.copy()
        write_json(os.path.join(engine, "corpus-map.overlay.json"),
                   {"speed-limit": {"status": "implemented", "implementedIn": IMPLEMENTED_IN}})
        produce(self.nupkg, engine)  # regenerated, so only the claim itself is wrong
        self.assertFailsAt(self.validate(engine, "full"),
                           "packaged check-map.py --phase consumer passes on the merged map",
                           "every test an implemented entry names exists and ran (Debug)")

    def test_fails_on_adding_rules_kernel_randomness(self):
        engine = self.copy()
        # The kernel's own pin is generated (RulesFactory.Packages.g.props); the engine adds the
        # randomness package in the file it owns.
        edit(os.path.join(engine, "Directory.Packages.props"), lambda t: t.replace(
            "  </ItemGroup>", '    <PackageVersion Include="RulesKernel.Randomness" Version="0.2.0" />\n  </ItemGroup>', 1))
        edit(os.path.join(engine, "src", NAME, f"{NAME}.csproj"), lambda t: t.replace(
            '    <PackageReference Include="RulesKernel" />',
            '    <PackageReference Include="RulesKernel" />\n    <PackageReference Include="RulesKernel.Randomness" />', 1))
        # full: the committed lock files no longer agree with the projects
        self.assertFailsAt(self.validate(engine, "full"), "dotnet restore --locked-mode",
                           "no lock file or project resolves RulesKernel.Randomness")
        # lock: even with lock files rewritten to agree, the randomness package is found in them
        result = self.validate(engine, "lock")
        self.assertFailsAt(result, "no lock file or project resolves RulesKernel.Randomness")
        self.assertIn("packages.lock.json (net8.0) resolves RulesKernel.Randomness", result[1])
        self.assertIn("ok   dotnet restore --locked-mode", result[1])

    def test_fails_on_a_hand_edit_to_a_generated_file(self):
        engine = self.copy()
        edit(os.path.join(engine, *REGISTRY.split("/")), hand_edit)
        self.assertFailsAt(self.validate(engine, "full"), "every *.g.cs matches a fresh regeneration (no hand edits)")


if __name__ == "__main__":
    unittest.main()
