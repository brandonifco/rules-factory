#!/usr/bin/env python3
"""`factory produce` (#3, M2) scaffolds an engine once, regenerates its `*.g.cs` every time, and
generates exactly what the correspondence table says.

What is asserted here without a .NET SDK: two runs give byte-identical trees; a second run into
the same directory leaves scaffold files (the overlay above all) alone and rewrites the
generated ones; a re-run with a newer or older version of the map leaves nothing naming the
version it replaced, pins included (#66); every one of Part 107's 44 entries is emitted with its citation verbatim and
the correspondence row the table's first match gives it; the overlay moves an entry between
rows; an overlay that breaks 0015's merge rules is refused.

What is not: that the produced solution builds and its generated tests pass. That needs the
SDK the kernel pins and nuget.org, so it is not a unit test here: scripts/validate-engine.sh
produces the backgammon engine from scratch and restores, builds (`-warnaserror`) and tests it,
and CI's `engine` job runs that script with the pinned SDK installed.

Run: python3 -m unittest discover -s tools/tests
"""
import hashlib
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
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")

_spec = importlib.util.spec_from_file_location("factory_main_produce", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
generate = factory.generate

PART107 = os.path.join(REPO, "examples", "faa-part-107")
PART107_XML = os.path.join(PART107, "part107.xml")
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
NAME = "FaaPart107"
GENERATED = (
    f"src/{NAME}/Generated/MapEntries.g.cs",
    f"src/{NAME}/Generated/Registry.g.cs",
    f"tests/{NAME}.Tests/Generated/CorrespondenceTests.g.cs",
    f"src/{NAME}/Generated/Provenance.g.cs",
    f"tests/{NAME}.Tests/Generated/ProvenanceTests.g.cs",
)
PACKAGES_PROPS = "RulesFactory.Packages.g.props"
MAP_ID = "RulesFactory.Maps.FaaPart107"


def pack(map_dir, out):
    subprocess.run([sys.executable, PACK, map_dir, "--out", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
    return os.path.join(out, name)


def pack_version(map_dir, version, root):
    """`map_dir` packed as `version`: a copy under `root` whose map-package.json says so."""
    copy = os.path.join(root, f"v{version}", os.path.basename(map_dir))
    shutil.copytree(map_dir, copy)
    with open(os.path.join(copy, "map-package.json"), "w", encoding="utf-8") as handle:
        json.dump({"version": version}, handle)
    return pack(copy, os.path.join(root, f"v{version}", "out"))


def tree(root):
    files = {}
    for directory, _, names in os.walk(root):
        for name in names:
            path = os.path.join(directory, name)
            with open(path, "rb") as handle:
                files[os.path.relpath(path, root).replace(os.sep, "/")] = handle.read()
    return files


class ProduceCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        cls.part107 = pack(PART107, os.path.join(cls.shared, "part107"))
        cls.hoyle = pack(HOYLE, os.path.join(cls.shared, "hoyle"))
        with open(os.path.join(PART107, "corpus-map.json"), encoding="utf-8") as handle:
            cls.map = json.load(handle)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def produce(self, out, package=None, corpus=PART107_XML, name=NAME):
        # --allow-dirty: this checkout's own state is not under test here (test_factory_provenance.py
        # runs a committed copy of the factory to test the refusal).
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["produce", "--package", package or self.part107, "--corpus", corpus,
                                 "--name", name, "--out", out, "--allow-dirty"])
        return code, buffer.getvalue()

    def produced(self, out=None, **kwargs):
        out = out or os.path.join(self.tmp, "engine")
        code, output = self.produce(out, **kwargs)
        self.assertEqual(code, 0, output)
        return out

    def read(self, out, relative):
        with open(os.path.join(out, *relative.split("/")), encoding="utf-8") as handle:
            return handle.read()


class TestDeterminism(ProduceCase):
    def test_two_runs_are_byte_identical(self):
        first = tree(self.produced(os.path.join(self.tmp, "a")))
        second = tree(self.produced(os.path.join(self.tmp, "b")))
        self.assertEqual(sorted(first), sorted(second))
        for path in first:
            self.assertEqual(first[path], second[path], path)

    def test_a_rerun_in_place_changes_nothing(self):
        out = self.produced()
        before = tree(out)
        self.produced(out)
        self.assertEqual(before, tree(out))

    def test_no_machine_path_leaks_into_the_output(self):
        out = self.produced()
        for path, data in tree(out).items():
            if path.startswith("corpus/"):
                continue
            self.assertNotIn(self.tmp.encode(), data, path)
            self.assertNotIn(self.shared.encode(), data, path)


class TestScaffold(ProduceCase):
    def test_layout(self):
        out = self.produced()
        files = set(tree(out))
        for expected in ("global.json", "NuGet.config", "Directory.Build.props", "Directory.Packages.props",
                         f"{NAME}.slnx", f"src/{NAME}/{NAME}.csproj", f"tests/{NAME}.Tests/{NAME}.Tests.csproj",
                         "corpus-map.overlay.json", "corpus/part107.xml", "provenance.json", PACKAGES_PROPS, *GENERATED):
            self.assertIn(expected, files)
        generated_code = {f for f in files if f.endswith(".cs")}
        self.assertEqual(generated_code, set(GENERATED), "every C# file the factory writes is *.g.cs")

    def test_pins(self):
        out = self.produced()
        self.assertEqual(json.loads(self.read(out, "global.json"))["sdk"], {"version": "10.0.112", "rollForward": "disable"})
        packages = self.read(out, PACKAGES_PROPS)
        self.assertIn('<PackageVersion Include="RulesKernel" Version="0.2.0" />', packages)
        self.assertIn(f'<PackageVersion Include="{MAP_ID}" Version="[1.0.0]" />', packages)
        self.assertIn(f"<ItemGroup Condition=\"'$(MSBuildProjectName)' == '{NAME}'\">", packages)
        self.assertIn(f'<PackageReference Include="{MAP_ID}" PrivateAssets="all" />', packages)
        central = self.read(out, "Directory.Packages.props")
        self.assertIn(f'<Import Project="$(MSBuildThisFileDirectory){PACKAGES_PROPS}" />', central)
        for scaffold_file in ("Directory.Packages.props", "Directory.Build.props", f"{NAME}.slnx",
                              f"src/{NAME}/{NAME}.csproj", f"tests/{NAME}.Tests/{NAME}.Tests.csproj"):
            text = self.read(out, scaffold_file)
            self.assertNotIn(MAP_ID, text, f"{scaffold_file} is write-once and must not name the map package")
            self.assertNotIn("0.2.0", text, f"{scaffold_file} is write-once and must not pin the kernel")
        build = self.read(out, "Directory.Build.props")
        self.assertIn("<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>", build)
        self.assertIn("<RestoreLockedMode", build)
        self.assertEqual(json.loads(self.read(out, "corpus-map.overlay.json")), {})
        with open(PART107_XML, "rb") as handle, open(os.path.join(out, "corpus", "part107.xml"), "rb") as copy:
            self.assertEqual(handle.read(), copy.read())

    def test_hand_written_and_scaffold_files_survive_a_rerun(self):
        out = self.produced()
        hand = os.path.join(out, "src", NAME, "Rules", "Speed.cs")
        os.makedirs(os.path.dirname(hand))
        with open(hand, "w", encoding="utf-8") as handle:
            handle.write("// mine\n")
        with open(os.path.join(out, "Directory.Build.props"), "a", encoding="utf-8") as handle:
            handle.write("<!-- edited -->\n")
        generated_file = os.path.join(out, *GENERATED[0].split("/"))
        with open(generated_file, "w", encoding="utf-8") as handle:
            handle.write("// hand edit to a generated file\n")
        self.produced(out)
        self.assertEqual(self.read(out, f"src/{NAME}/Rules/Speed.cs"), "// mine\n")
        self.assertTrue(self.read(out, "Directory.Build.props").endswith("<!-- edited -->\n"))
        self.assertIn("public static class MapEntries", self.read(out, GENERATED[0]))


class TestMapVersionChange(ProduceCase):
    """#66: re-producing with another version of the map moves every pin with the code."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.v1 = pack_version(PART107, "1.0.0", os.path.join(cls.shared, "versions"))
        cls.v2 = pack_version(PART107, "2.0.0", os.path.join(cls.shared, "versions"))

    def assert_names_only(self, out, now, before):
        files = tree(out)
        for path, data in files.items():
            # The corpus, and the factory's own source vendored for the gate (its prose happens to
            # mention versions), are the same bytes whatever map version is produced.
            if path.startswith(("corpus/", "scripts/factory/")):
                continue
            self.assertNotIn(before.encode(), data, f"{path} still names {before}")
        self.assertIn(f'<PackageVersion Include="{MAP_ID}" Version="[{now}]" />', self.read(out, PACKAGES_PROPS))
        for path in GENERATED[:3]:
            self.assertIn(f"from {MAP_ID} {now}.", self.read(out, path), path)
        self.assertIn(now, self.read(out, "backlog/README.md"))
        record = json.loads(self.read(out, "provenance.json"))
        self.assertEqual(record["map"]["version"], now)
        generated = {g["path"]: g["sha256"] for g in record["generated"]}
        self.assertIn(PACKAGES_PROPS, generated, "the pins are recorded")
        with open(os.path.join(out, PACKAGES_PROPS), "rb") as handle:
            self.assertEqual(generated[PACKAGES_PROPS], hashlib.sha256(handle.read()).hexdigest())

    def assert_same_as_fresh(self, out, package):
        fresh = tree(self.produced(os.path.join(self.tmp, "fresh"), package=package))
        self.assertEqual(fresh, tree(out), "a re-run gives what a fresh run gives")

    def test_upgrade(self):
        out = self.produced(package=self.v1)
        self.assert_names_only(out, "1.0.0", "2.0.0")
        self.produced(out, package=self.v2)
        self.assert_names_only(out, "2.0.0", "1.0.0")
        self.assert_same_as_fresh(out, self.v2)

    def test_downgrade(self):
        out = self.produced(package=self.v2)
        self.produced(out, package=self.v1)
        self.assert_names_only(out, "1.0.0", "2.0.0")
        self.assert_same_as_fresh(out, self.v1)

    def test_engine_owned_scaffold_edits_survive_a_version_change(self):
        out = self.produced(package=self.v1)
        with open(os.path.join(out, "Directory.Packages.props"), "a", encoding="utf-8") as handle:
            handle.write("<!-- edited -->\n")
        self.produced(out, package=self.v2)
        self.assertTrue(self.read(out, "Directory.Packages.props").endswith("<!-- edited -->\n"))
        self.assert_names_only(out, "2.0.0", "1.0.0")


class TestGeneration(ProduceCase):
    def test_every_entry_with_its_citation_verbatim(self):
        out = self.produced()
        entries = self.read(out, GENERATED[0])
        registry = self.read(out, GENERATED[1])
        tests = self.read(out, GENERATED[2])
        self.assertEqual(len(self.map["entries"]), 44)
        for entry in self.map["entries"]:
            literal = generate.cs_string(entry["locator"]["citation"])
            self.assertIn(f'new SourceLocator("cfr-14-107", {literal})', entries, entry["id"])
            self.assertIn(f'new("{entry["id"]}", EntryStatus.', registry)
            self.assertIn(f'        "{entry["id"]}",\n', tests)
        self.assertIn('contentHash: "80f6bc4b002df9dcc60a651fec30a2dc3590081cc3e5fd431d9885c69b7ce35e"', entries)
        self.assertIn("asOf: new DateOnly(2026, 1, 1)", entries)
        self.assertEqual(registry.count("MapEntries."), 44)

    def test_rows_follow_the_table_first_match(self):
        out = self.produced()
        tests = self.read(out, GENERATED[2])
        declines = dict(re.findall(r'AssertDeclines\("([a-z0-9-]+)", UnresolvedReason\.(\w+),', tests))
        self.assertEqual(len(declines), 44, "every mapped, declined or out-of-scope entry declines")
        self.assertEqual(declines["subpart-d-categories"], "OutsideCurrentScope")
        for defined_elsewhere in ("night-operation", "civil-twilight-alaska", "hazardous-material"):
            self.assertEqual(declines[defined_elsewhere], "MissingRulesData")
        # mapped wins over the ambiguity (row 2 before row 6) and over the assertion (row 2 before 8)
        self.assertEqual(declines["prominent-objects"], "UnsupportedRule")
        self.assertEqual(declines["reasonable-protection"], "UnsupportedRule")
        self.assertEqual(sum(1 for r in declines.values() if r == "UnsupportedRule"), 40)

    def test_the_overlay_moves_entries_between_rows(self):
        out = os.path.join(self.tmp, "engine")
        os.makedirs(out)
        implemented = {"status": "implemented", "implementedIn": {"ruleset": "faa-part-107", "version": 1},
                       "tests": [{"test": "T.t", "mutation": "m"}]}
        with open(os.path.join(out, "corpus-map.overlay.json"), "w", encoding="utf-8") as handle:
            json.dump({"speed-within-limit": implemented, "reasonable-protection": implemented}, handle)
        self.produced(out)
        tests = self.read(out, GENERATED[2])
        registry = self.read(out, GENERATED[1])
        # speed-limit, a value it depends on, is still mapped: row 5.
        self.assertIn('new("speed-within-limit", EntryStatus.Implemented, CorrespondenceRow.ValueDependencyUnimplemented,', registry)
        self.assertIn("speed_within_limit__is_implemented_so_a_hand_written_handler_answers_it", tests)
        self.assertIn('new("reasonable-protection", EntryStatus.Implemented, CorrespondenceRow.Assertion,', registry)
        self.assertIn("reasonable_protection__is_implemented_and_answers_or_demands_the_assertion", tests)

    def test_a_derived_entry_declines_citing_its_first_source(self):
        out = self.produced(package=self.hoyle, corpus=os.path.join(HOYLE, "hoyle.txt"), name="HoyleBackgammon")
        entries = self.read(out, "src/HoyleBackgammon/Generated/MapEntries.g.cs")
        registry = self.read(out, "src/HoyleBackgammon/Generated/Registry.g.cs")
        self.assertIn("public static DerivedMapEntry HitPaysSingleStake", entries)
        self.assertRegex(registry, r'new\("hit-pays-single-stake", EntryStatus\.Mapped, CorrespondenceRow\.NotBuilt, MapEntries\.\w+\.Locator\)')
        self.assertNotIn("MapEntries.HitPaysSingleStake.Locator", registry)
        self.assertIn('new("inner-table-handedness", EntryStatus.Declined, CorrespondenceRow.BeyondAdapter,', registry)


class TestRefuses(ProduceCase):
    def overlay(self, content):
        out = os.path.join(self.tmp, "engine")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "corpus-map.overlay.json"), "w", encoding="utf-8") as handle:
            json.dump(content, handle)
        code, output = self.produce(out)
        self.assertEqual(code, 1, output)
        self.assertIn("REFUSED", output)
        return out, output

    def test_an_overlay_naming_no_entry(self):
        out, output = self.overlay({"no-such-entry": {"status": "mapped"}})
        self.assertIn("no-such-entry", output)
        self.assertFalse(os.path.exists(os.path.join(out, *GENERATED[0].split("/"))))

    def test_an_overlay_setting_a_field_the_engine_does_not_own(self):
        _, output = self.overlay({"speed-limit": {"status": "mapped", "scope": "out"}})
        self.assertIn("'scope'", output)

    def test_an_overlay_item_without_status(self):
        _, output = self.overlay({"speed-limit": {"tests": []}})
        self.assertIn("does not set status", output)

    def split_pin(self, relative, text):
        out = self.produced()
        before = tree(out)
        with open(os.path.join(out, *relative.split("/")), "w", encoding="utf-8") as handle:
            handle.write(text)
        code, output = self.produce(out)
        self.assertEqual(code, 1, output)
        self.assertIn("REFUSED", output)
        self.assertIn(PACKAGES_PROPS, output)
        after = tree(out)
        del before[relative], after[relative]
        self.assertEqual(before, after, "nothing is written")
        return output

    def test_an_engine_scaffolded_with_the_pins_in_directory_packages_props(self):
        output = self.split_pin("Directory.Packages.props", (
            "<Project>\n  <ItemGroup>\n"
            f'    <PackageVersion Include="RulesKernel" Version="0.2.0" />\n'
            f'    <PackageVersion Include="{MAP_ID}" Version="[1.0.0]" />\n'
            "  </ItemGroup>\n</Project>\n"))
        self.assertIn("Directory.Packages.props pins RulesKernel", output)
        self.assertIn(f"Directory.Packages.props pins {MAP_ID}", output)
        self.assertIn(f"does not import {PACKAGES_PROPS}", output)

    def test_a_project_that_references_the_map_itself(self):
        output = self.split_pin(f"src/{NAME}/{NAME}.csproj", (
            '<Project Sdk="Microsoft.NET.Sdk">\n  <ItemGroup>\n'
            f'    <PackageReference Include="{MAP_ID}" PrivateAssets="all" />\n'
            "  </ItemGroup>\n</Project>\n"))
        self.assertIn(f"references the map package {MAP_ID}", output)

    def test_a_name_that_is_not_a_csharp_identifier(self):
        code, output = self.produce(os.path.join(self.tmp, "engine"), name="faa-part-107")
        self.assertEqual(code, 2, output)


if __name__ == "__main__":
    unittest.main()
