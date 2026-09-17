#!/usr/bin/env python3
"""`factory produce` (#3, M3) emits the gate that judges the engine, and the gate fails when it should.

Two layers:

  * **Without a .NET SDK** (always run): the recipe is emitted, executable and deterministic, and
    each non-dotnet check the gate runs -- scripts/map-overlay.py and scripts/engine-gate.py --
    passes on fresh output and fails on the mutation it exists for: a changed citation or a hand
    edit in a `*.g.cs`, an overlay key the map lacks, `implemented` without `tests`, a lock file
    or project resolving RulesKernel.Randomness for a corpus that declares `randomness: none`, or
    pinning it outside the generated props for one that declares `seeded` (0019), a corpus that is
    not the baseline, or an overlay edit that was regenerated but never followed by a re-produce,
    which leaves provenance.json hashing bytes that are gone and the backlog listing an entry that
    is already built (#192).
  * **With a .NET SDK** (skipped cleanly when `dotnet` is absent, as in this repository's CI, or
    when RULES_FACTORY_SKIP_DOTNET is set): the emitted `scripts/validate.sh` itself passes on
    fresh output and fails on each of those mutations. The engine is a scratch copy: its
    global.json is re-pinned to the SDK installed here, and its NuGet.config gains a local folder
    feed holding the map package packed by tools/pack-map.py (Part 107 4.0.0 is not on
    nuget.org until it is tagged) and the user's global packages folder as a read-only fallback. Packages restore
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
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
PART107_XML = os.path.join(PART107, "part107.xml")
NAME = "FaaPart107"
PACKAGE_ID = "RulesFactory.Maps.FaaPart107"
MAP_ENTRIES = f"src/{NAME}/Generated/MapEntries.g.cs"
REGISTRY = f"src/{NAME}/Generated/Registry.g.cs"
RECIPE = ("scripts/validate.sh", "scripts/map-overlay.py", "scripts/engine-gate.py",
          "scripts/factory/generate.py", "scripts/factory/intake.py", "scripts/factory/ownership.py",
          "scripts/factory/provenance.py", "scripts/factory/rulings.py", ".github/workflows/validate.yml")
IMPLEMENTED_IN = {"ruleset": "faa-part-107", "version": 1}
# Mutations these fixtures can record. Since #239 the gate refuses a placeholder one, so "m" no
# longer stands in for a sentence -- and a fixture nobody could have observed is the habit the
# refusal exists to break, so each names an edit that would genuinely turn the named test red.
# MUTATION goes with the invented SpeedTests; CORRESPONDENCE with the generated correspondence
# test, which asserts Registry.HasImplementation and so is not reddened by editing a handler
# (deleting one is CS8795, a build error).
MUTATION = "GroundspeedLimit.Knots printed 88 knots (`InKnots(88m)` for `InKnots(87m)`); it went red."
CORRESPONDENCE = ("Registry.HasImplementation was made to answer false for every entry (`=> false` "
                  "for `Implementations.Value.ContainsKey(entryId) || Handlers.Has(entryId)`); this "
                  "test went red.")
OVERLAY = "corpus-map.overlay.json"


def pack(map_dir, out):
    subprocess.run([sys.executable, PACK, map_dir, "--out", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
    return os.path.join(out, name)


def produce(package, out, *extra):
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = factory.main(["produce", "--package", package, "--corpus", PART107_XML, "--name", NAME, "--out", out,
                             "--allow-dirty",  # this checkout's state is not under test here
                             "--no-verify", *extra])  # nor is building it: no SDK assumed (test_factory_verify.py)
    # `--no-verify` ends NOT VERIFIED (3), never 0 (tools/factory/__main__.py).
    if code != factory.NOT_VERIFIED:
        raise AssertionError(f"produce --no-verify exited {code}, not {factory.NOT_VERIFIED}\n"
                             + buffer.getvalue())


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
                           "--package-manifest", self.package_manifest,
                           "--package-id", PACKAGE_ID, "--package-version", "4.0.0", "--name", NAME)

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
        self.assertIn("export PYTHONDONTWRITEBYTECODE=1", gate.split("MODE=")[0],
                      "run by hand, the gate leaves no scripts/factory/__pycache__ in the engine")
        subprocess.run(["bash", "-n", os.path.join(engine, "scripts", "validate.sh")], check=True)
        for module in ("generate.py", "intake.py", "ownership.py", "provenance.py", "rulings.py"):
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
        self.assertIn("8 generated file(s) match", output)

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


class TestTheRecordHashesWhatIsOnDisk(GateCase):
    """#192: `provenance` compares the record with the tree, and an overlay edit is only finished
    by a re-produce.

    The defect this exists for passed `validate.sh full` in the live run of #157: marking an entry
    implemented changes the overlay, `regenerate --write` refreshes the generated C# and nothing
    else, and `provenance.json` and `backlog/` -- both generated, both `factory produce`'s alone --
    are left hashing bytes that no longer exist and listing an entry that is already built.
    """

    IMPLEMENTED = {"speed-limit": {"status": "implemented", "implementedIn": IMPLEMENTED_IN,
                                   "tests": [{"test": "SpeedTests.t", "mutation": MUTATION}]}}

    def provenance(self, engine):
        return self.script(engine, "engine-gate.py", "provenance")

    def test_passes_on_fresh_output_having_examined_something(self):
        code, output = self.provenance(self.engine())
        self.assertEqual(code, 0, output)
        count = re.search(r"(\d+) recorded file\(s\) hash as provenance\.json records", output)
        self.assertIsNotNone(count, output)
        self.assertGreater(int(count.group(1)), 0, "a check that examined nothing reported an ok")
        self.assertIn(OVERLAY, output, "the overlay is named as examined, not merely implied")

    def test_a_regeneration_alone_leaves_the_record_stale(self):
        """The whole of #192, end to end: the leak, the failure that closes it, and the fix."""
        engine = self.engine()
        write_json(os.path.join(engine, OVERLAY), self.IMPLEMENTED)
        code, output = self.script(engine, "engine-gate.py", "regenerate", "--package-map", self.package_map,
                                   "--package-manifest", self.package_manifest, "--package-id", PACKAGE_ID,
                                   "--package-version", "4.0.0", "--name", NAME, "--write")
        self.assertEqual(code, 0, output)  # the leak: refreshing the C# is not a failure, and it is not enough

        code, output = self.provenance(engine)
        self.assertEqual(code, 1, output)
        self.assertIn(f"buildInputs[{OVERLAY}].sha256", output)
        self.assertRegex(output, r"generated\[[^\]]+\.g\.cs\]\.sha256")
        self.assertIn("tools/re-produce.sh", output, "the failure names the command that fixes it")

        produce(self.nupkg, engine)
        code, output = self.provenance(engine)
        self.assertEqual(code, 0, output)

    def test_a_hand_edited_gate_fails(self):
        """Why an engine must not rewrite its own record: it cannot re-derive these bytes.

        `scripts/validate.sh` is generated and hashed, and no engine can regenerate it -- only the
        factory that emitted it can. An engine-side rewrite of the record would hash whatever is on
        disk and hand this edit a fresh matching SHA-256.
        """
        engine = self.engine()
        edit(os.path.join(engine, "scripts", "validate.sh"),
             lambda t: t.replace("FAILED=0", "FAILED=0\nexit 0  # tweaked by hand", 1))
        code, output = self.provenance(engine)
        self.assertEqual(code, 1, output)
        self.assertIn("generated[scripts/validate.sh].sha256", output)

    def test_a_deleted_backlog_item_fails(self):
        engine = self.engine()
        items = sorted(f for f in os.listdir(os.path.join(engine, "backlog")) if f.endswith(".md"))
        self.assertTrue(items, "the produced engine has no backlog to delete from")
        os.remove(os.path.join(engine, "backlog", items[0]))
        code, output = self.provenance(engine)
        self.assertEqual(code, 1, output)
        self.assertIn(f"generated[backlog/{items[0]}]: recorded, missing on disk", output)

    def test_a_hand_edited_managed_file_fails(self):
        engine = self.engine()
        with open(os.path.join(engine, "AGENTS.md"), "a", encoding="utf-8") as handle:
            handle.write("\n## Our own section\n")
        code, output = self.provenance(engine)
        self.assertEqual(code, 1, output)
        self.assertIn("managed[AGENTS.md].sha256", output)

    def test_a_record_that_lists_nothing_fails_rather_than_passing(self):
        engine = self.engine()
        os.remove(os.path.join(engine, OVERLAY))
        with open(os.path.join(engine, "provenance.json"), "wb") as handle:
            handle.write((json.dumps({"engine": {"name": NAME}, "generated": [], "managed": [],
                                      "buildInputs": []}, indent=2) + "\n").encode("utf-8"))
        code, output = self.provenance(engine)
        self.assertEqual(code, 1, output)
        self.assertIn("examined nothing", output)

    def test_a_hand_edited_record_is_not_in_the_factory_s_canonical_form(self):
        engine = self.engine()
        path = os.path.join(engine, "provenance.json")
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)  # every hash still true; only the serialisation differs
        code, output = self.provenance(engine)
        self.assertEqual(code, 1, output)
        self.assertIn("not in the factory's canonical form", output)


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
            "tests": [{"test": "SpeedTests.Nobody_wrote_this", "mutation": MUTATION}]}})
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


def lock(engine, name, packages):
    for project in (f"src/{name}", f"tests/{name}.Tests"):
        write_json(os.path.join(engine, *project.split("/"), "packages.lock.json"),
                   {"version": 1, "dependencies": {"net8.0": {p: {"type": "Transitive"} for p in packages}}})


def add_randomness_pin(text):
    return text.replace("  </ItemGroup>", '    <PackageVersion Include="RulesKernel.Randomness" Version="0.2.0" />\n  </ItemGroup>', 1)


class TestRandomnessNone(GateCase):
    """Part 107 declares `randomness: none` (0019): nothing may reach RulesKernel.Randomness."""

    def gate(self, engine, command):
        if command == "randomness":
            return self.script(engine, "engine-gate.py", "randomness", "--manifest", self.package_manifest,
                               "--map", self.package_map)
        return self.script(engine, "engine-gate.py", command)

    def test_lock_files_are_required(self):
        engine = self.engine()
        code, output = self.gate(engine, "lock-files")
        self.assertEqual(code, 1, output)
        self.assertIn("has no packages.lock.json", output)
        self.assertEqual(self.gate(engine, "randomness")[0], 1, "no lock file proves nothing")
        lock(engine, NAME, ["RulesKernel"])
        self.assertEqual(self.gate(engine, "lock-files")[0], 0)

    def test_passes_without_randomness(self):
        engine = self.engine()
        lock(engine, NAME, ["RulesKernel", PACKAGE_ID])
        code, output = self.gate(engine, "randomness")
        self.assertEqual(code, 0, output)
        self.assertIn("randomness: none", output)
        with open(os.path.join(engine, "RulesFactory.Packages.g.props"), encoding="utf-8") as handle:
            self.assertNotIn("RulesKernel.Randomness", handle.read(), "a none corpus gets no pin")

    def test_fails_when_a_lock_file_resolves_randomness(self):
        engine = self.engine()
        lock(engine, NAME, ["RulesKernel", "RulesKernel.Randomness"])
        code, output = self.gate(engine, "randomness")
        self.assertEqual(code, 1, output)
        self.assertIn("resolves RulesKernel.Randomness", output)

    def test_fails_when_a_project_references_randomness(self):
        engine = self.engine()
        lock(engine, NAME, ["RulesKernel"])
        edit(os.path.join(engine, "Directory.Packages.props"), add_randomness_pin)
        code, output = self.gate(engine, "randomness")
        self.assertEqual(code, 1, output)
        self.assertIn("Directory.Packages.props references RulesKernel.Randomness", output)

    def test_fails_when_the_generated_props_is_edited_to_pin_randomness(self):
        engine = self.engine()
        lock(engine, NAME, ["RulesKernel"])
        edit(os.path.join(engine, "RulesFactory.Packages.g.props"), add_randomness_pin)
        code, output = self.gate(engine, "randomness")
        self.assertEqual(code, 1, output)
        self.assertIn("RulesFactory.Packages.g.props references RulesKernel.Randomness", output)
        self.assertEqual(self.regenerate(engine)[0], 1, "and the regeneration names the hand edit")

    def test_a_manifest_that_declares_nothing_fails_rather_than_defaulting(self):
        engine = self.engine()
        lock(engine, NAME, ["RulesKernel"])
        with open(self.package_manifest, encoding="utf-8") as handle:
            manifest = json.load(handle)
        del manifest["corpora"][0]["randomness"]
        path = os.path.join(self.tmp, "undeclared.json")
        write_json(path, manifest)
        code, output = self.script(engine, "engine-gate.py", "randomness", "--manifest", path, "--map", self.package_map)
        self.assertEqual(code, 1, output)
        self.assertIn("declares randomness None", output)
        code, output = self.script(engine, "engine-gate.py", "regenerate", "--package-map", self.package_map,
                                   "--package-manifest", path, "--package-id", PACKAGE_ID,
                                   "--package-version", "4.0.0", "--name", NAME)
        self.assertEqual(code, 1, output)


class TestRandomnessSeeded(unittest.TestCase):
    """Backgammon declares `randomness: seeded` (0019): its engine may reference the package, pinned once."""

    HOYLE_NAME = "HoyleBackgammon"

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        cls.nupkg = pack(HOYLE, os.path.join(cls.shared, "feed"))
        cls.package_map = os.path.join(cls.shared, "package-map.json")
        cls.package_manifest = os.path.join(cls.shared, "package-manifest.json")
        with zipfile.ZipFile(cls.nupkg) as archive:
            with open(cls.package_map, "wb") as handle:
                handle.write(archive.read("map/corpus-map.json"))
            with open(cls.package_manifest, "wb") as handle:
                handle.write(archive.read("map/corpus-manifest.json"))
            cls.version = re.search(r"<version>([^<]+)</version>",
                                    archive.read("RulesFactory.Maps.HoyleBackgammon.nuspec").decode("utf-8")).group(1)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def engine(self):
        out = os.path.join(self.tmp, "engine")
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["produce", "--package", self.nupkg, "--corpus", os.path.join(HOYLE, "hoyle.txt"),
                                 "--name", self.HOYLE_NAME, "--out", out, "--allow-dirty", "--no-verify"])
        # `--no-verify` ends NOT VERIFIED (3), never 0 (tools/factory/__main__.py).
        self.assertEqual(code, factory.NOT_VERIFIED, buffer.getvalue())
        return out

    def gate(self, engine, *args):
        completed = subprocess.run([sys.executable, os.path.join(engine, "scripts", "engine-gate.py"), *args], cwd=engine,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return completed.returncode, completed.stdout

    def randomness(self, engine, manifest=None):
        return self.gate(engine, "randomness", "--manifest", manifest or self.package_manifest, "--map", self.package_map)

    def reference_randomness(self, engine):
        edit(os.path.join(engine, "src", self.HOYLE_NAME, f"{self.HOYLE_NAME}.csproj"), lambda t: t.replace(
            '    <PackageReference Include="RulesKernel" />',
            '    <PackageReference Include="RulesKernel" />\n    <PackageReference Include="RulesKernel.Randomness" />', 1))
        lock(engine, self.HOYLE_NAME, ["RulesKernel", "RulesKernel.Randomness"])

    def test_the_generated_props_pins_randomness_at_the_kernel_version_and_references_nothing(self):
        engine = self.engine()
        with open(os.path.join(engine, "RulesFactory.Packages.g.props"), encoding="utf-8") as handle:
            props = handle.read()
        self.assertIn(f'<PackageVersion Include="RulesKernel.Randomness" Version="{factory.generate.KERNEL_VERSION}" />', props)
        self.assertNotIn('<PackageReference Include="RulesKernel.Randomness"', props)
        with open(os.path.join(engine, "provenance.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["randomness"], "seeded")
        code, output = self.gate(engine, "regenerate", "--package-map", self.package_map, "--package-manifest",
                                 self.package_manifest, "--package-id", "RulesFactory.Maps.HoyleBackgammon",
                                 "--package-version", self.version, "--name", self.HOYLE_NAME)
        self.assertEqual(code, 0, output)

    def test_an_engine_may_reference_randomness(self):
        engine = self.engine()
        lock(engine, self.HOYLE_NAME, ["RulesKernel"])
        code, output = self.randomness(engine)
        self.assertEqual(code, 0, output)
        self.reference_randomness(engine)
        code, output = self.randomness(engine)
        self.assertEqual(code, 0, output)
        self.assertIn("randomness: seeded", output)

    def test_the_same_engine_fails_when_its_corpus_declares_none(self):
        engine = self.engine()
        self.reference_randomness(engine)
        with open(self.package_manifest, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["corpora"][0]["randomness"] = "none"
        path = os.path.join(self.tmp, "none.json")
        write_json(path, manifest)
        code, output = self.randomness(engine, path)
        self.assertEqual(code, 1, output)
        self.assertIn(f"src/{self.HOYLE_NAME}/{self.HOYLE_NAME}.csproj references RulesKernel.Randomness", output)
        self.assertIn("resolves RulesKernel.Randomness", output)

    def test_a_pin_or_version_of_its_own_fails(self):
        engine = self.engine()
        self.reference_randomness(engine)
        edit(os.path.join(engine, "Directory.Packages.props"), add_randomness_pin)
        code, output = self.randomness(engine)
        self.assertEqual(code, 1, output)
        self.assertIn("Directory.Packages.props pins RulesKernel.Randomness", output)
        # and produce refuses it too, before writing anything (the pin has one home)
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            refused = factory.main(["produce", "--package", self.nupkg, "--corpus", os.path.join(HOYLE, "hoyle.txt"),
                                    "--name", self.HOYLE_NAME, "--out", engine, "--allow-dirty", "--no-verify"])
        self.assertNotEqual(refused, 0, buffer.getvalue())
        self.assertIn("Directory.Packages.props pins RulesKernel.Randomness", buffer.getvalue())


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

    def test_the_gate_recomputes_with_intakes_table_and_has_none_of_its_own(self):
        """#106: the gate kept a copy of the derivation table, and the SRD's derivation was missing from it."""
        engine = self.engine()
        with open(os.path.join(engine, "scripts", "engine-gate.py"), encoding="utf-8") as handle:
            own = re.search(r"(?m)^\s*[A-Z_]*DERIVATIONS\s*=.*$", handle.read())
        self.assertIsNone(own, "the gate declares a derivation table of its own, which can drift from intake's")
        # Take Part 107's derivation out of the vendored intake.py: the gate must stop being able to verify.
        edit(os.path.join(engine, "scripts", "factory", "intake.py"),
             lambda t: t.replace('    "ecfr-versioner-xml": _sha256_of_bytes,\n', "", 1))
        code, output = self.posture(engine)
        self.assertEqual(code, 1, output)
        self.assertIn("cannot recompute hashDerivation 'ecfr-versioner-xml'", output)

    def test_every_packable_example_maps_engine_verifies_its_baseline(self):
        """A corpus admitted with a derivation its engine's gate cannot recompute fails here, without an SDK."""
        maps = sorted(os.path.dirname(p) for p in
                      (os.path.join(REPO, "examples", d, "map-package.json") for d in os.listdir(os.path.join(REPO, "examples")))
                      if os.path.isfile(p))
        self.assertGreaterEqual(len(maps), 3, maps)
        for map_dir in maps:
            with self.subTest(map=os.path.basename(map_dir)):
                work = tempfile.mkdtemp(dir=self.tmp)
                nupkg = pack(map_dir, os.path.join(work, "feed"))
                with zipfile.ZipFile(nupkg) as archive:
                    (nuspec,) = [n for n in archive.namelist() if n.endswith(".nuspec") and "/" not in n]
                    package_id = re.search(r"<id>([^<]+)</id>", archive.read(nuspec).decode("utf-8")).group(1)
                    files = {}
                    for label, member in (("map", "map/corpus-map.json"), ("manifest", "map/corpus-manifest.json")):
                        files[label] = os.path.join(work, os.path.basename(member))
                        with open(files[label], "wb") as handle:
                            handle.write(archive.read(member))
                with open(files["map"], encoding="utf-8") as handle:
                    cited = json.load(handle)["corpus"]
                with open(files["manifest"], encoding="utf-8") as handle:
                    (corpus,) = [c for c in json.load(handle)["corpora"] if c["sourceId"] == cited]
                name = package_id.rsplit(".", 1)[-1]
                engine = os.path.join(work, "engine")
                buffer = io.StringIO()
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    code = factory.main(["produce", "--package", nupkg, "--corpus",
                                         os.path.join(map_dir, corpus["committedPath"]), "--name", name, "--out", engine,
                                         "--allow-dirty", "--no-verify"])
                self.assertEqual(code, factory.NOT_VERIFIED, buffer.getvalue())  # `--no-verify`: NOT VERIFIED (3), never 0
                merged = os.path.join(work, "merged.json")
                code, output = self.script(engine, "map-overlay.py", "merge", "--package-map", files["map"],
                                           "--overlay", os.path.join(engine, "corpus-map.overlay.json"), "--out", merged)
                self.assertEqual(code, 0, output)
                code, output = self.script(engine, "engine-gate.py", "posture", "--manifest", files["manifest"],
                                           "--map", merged, "--name", name)
                self.assertEqual(code, 0, output)
                self.assertIn(f"verified: {cited} (committed-copy", output)


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
        # global.json and NuGet.config are managed (tools/factory/ownership.py): the localised copies
        # are hand edits, so the tests below that re-produce would be refused. Adopting them once
        # here is what a real engine that must move its SDK or add a feed does.
        produce(cls.nupkg, cls.base, "--adopt", "global.json", "--adopt", "NuGet.config")
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
                     "RulesKernel.Randomness is reachable only as the corpus declares", "packaged check-map.py --phase consumer",
                     "every corpus verified", "every *.g.cs matches a fresh regeneration",
                     "provenance.json hashes the generated files, the managed files and the overlay", "dotnet format",
                     "build Debug", "test Debug", "build Release", "test Release"):
            self.assertIn(f"ok   {step}", output)
        self.assertNotIn("FAIL", output)
        self.assertNotIn("skip ", output)
        # and full, which is what CI runs, passes on the committed lock files without rewriting them
        engine = self.copy()
        code, output = self.validate(engine, "full")
        self.assertEqual(code, 0, output[-4000:])
        self.assertIn("validate.sh full: PASS\n", output)

    def implement_speed_limit(self, engine, handler):
        """Mark speed-limit implemented, re-produce, and put `handler` in a hand-written file."""
        test = "CorrespondenceTests.speed_limit__is_implemented_so_a_hand_written_handler_answers_it"
        write_json(os.path.join(engine, "corpus-map.overlay.json"), {"speed-limit": {
            "status": "implemented", "implementedIn": IMPLEMENTED_IN,
            "tests": [{"test": test, "mutation": CORRESPONDENCE}]}})
        produce(self.nupkg, engine)
        with open(os.path.join(engine, "src", NAME, "Speed.cs"), "w", encoding="utf-8") as handle:
            handle.write("using RulesKernel.Resolution;\n\nnamespace FaaPart107;\n\n"
                         "internal static partial class Handlers\n{\n" + handler + "}\n")

    def build(self, engine):
        """One target framework of the engine project, warnings as errors, as the gate builds it."""
        env = {k: v for k, v in os.environ.items() if k not in ("CI", "MSBUILDNOINPROCNODE")}
        env["NUGET_PACKAGES"] = self.packages
        completed = subprocess.run(["dotnet", "build", os.path.join("src", NAME, f"{NAME}.csproj"), "-f", "net10.0",
                                    "-warnaserror", "-nologo"], cwd=engine, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, env=env, timeout=900)
        return completed.returncode, completed.stdout

    def test_passes_with_an_implemented_entry_whose_tests_ran(self):
        engine = self.copy()
        # #93: the handler answers with an input the engine declares on its partial request type, and
        # a hand-written test proves the value arrives through EntryPoints (and, through the
        # dictionary dispatch, which has no inputs, that it is at its default).
        self.implement_speed_limit(engine, "    internal static partial Resolution<object> SpeedLimit("
                                           "Requests.SpeedLimitRequest request) =>\n"
                                           "        Resolution<object>.FromValue(request.Knots);\n")
        with open(os.path.join(engine, "src", NAME, "SpeedLimitRequest.cs"), "w", encoding="utf-8") as handle:
            handle.write("namespace FaaPart107.Requests;\n\npublic sealed partial class SpeedLimitRequest\n{\n"
                         "    /// <summary>An engine-declared input.</summary>\n"
                         "    public int Knots { get; init; } = 87;\n}\n")
        with open(os.path.join(engine, "tests", f"{NAME}.Tests", "InputTests.cs"), "w", encoding="utf-8") as handle:
            handle.write("using RulesKernel.Resolution;\nusing Xunit;\n\nnamespace FaaPart107.Tests;\n\n"
                         "public sealed class InputTests\n{\n"
                         "    [Fact]\n"
                         "    public void an_engine_declared_input_reaches_the_handler()\n"
                         "    {\n"
                         "        Assert.Equal(100, EntryPoints.SpeedLimit.Resolve(new Requests.SpeedLimitRequest { Knots = 100 }).Match<object?>(v => v, _ => null));\n"
                         "        Assert.Equal(87, Registry.Resolve(\"speed-limit\", RuleRequest.Empty).Match<object?>(v => v, _ => null));\n"
                         "    }\n}\n")
        code, output = self.validate(engine, "full")
        self.assertEqual(code, 0, output[-4000:])
        self.assertIn("1 test(s) named by 1 implemented entries, every one found and executed in all 2", output)

    def test_a_missing_or_mis_typed_handler_or_request_is_a_build_error(self):
        """#76: what reflection used to refuse at runtime, or never checked, the compiler refuses."""
        engine = self.copy()
        good = "    internal static partial Resolution<object> SpeedLimit(Requests.SpeedLimitRequest request) => Resolution<object>.FromValue(87);\n"
        cases = {
            "the typed handler builds": (good, None),
            "a missing handler": ("", "error CS8795: Partial method 'Handlers.SpeedLimit(SpeedLimitRequest)' must have an implementation part"),
            "another return type": (good.replace("Resolution<object>", "Resolution<int>"),
                                    "error CS8817: Both partial method declarations must have the same return type"),
            "another parameter type": (good.replace("Requests.SpeedLimitRequest", "RuleRequest"),
                                       "error CS0759: No defining declaration found for implementing declaration of partial method 'Handlers.SpeedLimit(RuleRequest)'"),
            "an optional hook with another entry's request": (
                good + "    static partial void AltitudeLimit(Requests.SpeedLimitRequest request, ref Resolution<object>? resolution) { }\n",
                "error CS0759: No defining declaration found for implementing declaration of partial method 'Handlers.AltitudeLimit(SpeedLimitRequest, ref Resolution<object>?)'"),
            "a typed entry point handed another entry's request": (
                good + "    internal static Resolution<object> Call() => EntryPoints.SpeedLimit.Resolve(Requests.AltitudeLimitRequest.Empty);\n",
                "error CS1503: Argument 1: cannot convert from 'FaaPart107.Requests.AltitudeLimitRequest' to 'FaaPart107.Requests.SpeedLimitRequest'"),
        }
        for label, (handler, expected) in cases.items():
            with self.subTest(label):
                self.implement_speed_limit(engine, handler)
                code, output = self.build(engine)
                if expected is None:
                    self.assertEqual(code, 0, output[-4000:])
                else:
                    self.assertNotEqual(code, 0, output[-4000:])
                    self.assertIn(expected, output)

    def test_fails_on_a_changed_citation_in_a_generated_file(self):
        engine = self.copy()
        edit(os.path.join(engine, *MAP_ENTRIES.split("/")), change_a_citation)
        self.assertFailsAt(self.validate(engine, "full"), "every *.g.cs matches a fresh regeneration (no hand edits)")

    def test_fails_on_an_overlay_key_not_in_the_map(self):
        engine = self.copy()
        write_json(os.path.join(engine, "corpus-map.overlay.json"), {"no-such-entry": {"status": "mapped"}})
        self.assertFailsAt(self.validate(engine, "full"),
                           f"merge({PACKAGE_ID}@4.0.0, corpus-map.overlay.json) obeys 0015")

    def test_fails_on_implemented_without_tests(self):
        engine = self.copy()
        write_json(os.path.join(engine, "corpus-map.overlay.json"),
                   {"speed-limit": {"status": "implemented", "implementedIn": IMPLEMENTED_IN}})
        # Regenerated, and given the typed handler an implemented entry now needs to build (#76),
        # so only the claim itself is wrong.
        produce(self.nupkg, engine)
        with open(os.path.join(engine, "src", NAME, "Speed.cs"), "w", encoding="utf-8") as handle:
            handle.write("using RulesKernel.Resolution;\n\nnamespace FaaPart107;\n\ninternal static partial class Handlers\n{\n"
                         "    internal static partial Resolution<object> SpeedLimit(Requests.SpeedLimitRequest request) =>\n"
                         "        Resolution<object>.FromValue(87);\n}\n")
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
        # full: the committed lock files no longer agree with the projects, so nothing after restore
        # is judged -- the randomness step included, since it reads the restored package's manifest
        self.assertFailsAt(self.validate(engine, "full"), "dotnet restore --locked-mode")
        # lock: even with lock files rewritten to agree, Part 107 declares `randomness: none` and the
        # package is found in them
        result = self.validate(engine, "lock")
        self.assertFailsAt(result, "RulesKernel.Randomness is reachable only as the corpus declares")
        self.assertIn("packages.lock.json (net8.0) resolves RulesKernel.Randomness", result[1])
        self.assertIn("ok   dotnet restore --locked-mode", result[1])

    def test_fails_on_a_hand_edit_to_a_generated_file(self):
        engine = self.copy()
        edit(os.path.join(engine, *REGISTRY.split("/")), hand_edit)
        self.assertFailsAt(self.validate(engine, "full"), "every *.g.cs matches a fresh regeneration (no hand edits)")

    def test_fails_when_an_overlay_edit_was_regenerated_but_never_re_produced(self):
        """#192 through the whole gate: the regeneration step is green and the record is stale."""
        engine = self.copy()
        write_json(os.path.join(engine, "corpus-map.overlay.json"),
                   {"speed-limit": {"status": "implemented", "implementedIn": IMPLEMENTED_IN,
                                    "tests": [{"test": "SpeedTests.t", "mutation": MUTATION}]}})
        code, output = self.script(engine, "engine-gate.py", "regenerate", "--package-map", self.package_map,
                                   "--package-manifest", self.package_manifest, "--package-id", PACKAGE_ID,
                                   "--package-version", "4.0.0", "--name", NAME, "--write")
        self.assertEqual(code, 0, output)
        result = self.validate(engine, "full")
        self.assertFailsAt(result, "provenance.json hashes the generated files, the managed files and the overlay")
        self.assertIn("tools/re-produce.sh", result[1])


if __name__ == "__main__":
    unittest.main()
