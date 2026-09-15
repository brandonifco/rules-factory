#!/usr/bin/env python3
"""The factory's intake (#3, M1) accepts a real map package and refuses each thing it exists to catch.

The packages are built here with tools/pack-map.py from examples/, not downloaded: the tests
need no network, and pack-map.py is deterministic, so `examples/hoyle-backgammon` packs to
RulesFactory.Maps.HoyleBackgammon 4.0.0 with the map, manifest, checker and props that
nuget.org serves (their bytes were compared against the published 2.0.0 package when this test
was written; the published package adds only nuget.org's signature, and later versions differ
from 2.0.0 in the checker's bytes and, from #95 and #102, the map's). When that published package is in the NuGet global
packages folder it is also run through intake, and that test says it was skipped otherwise.

Each refusal starts from a package that passes and changes exactly one thing, and asserts a
non-zero exit -- a refusal test that also fails on the unchanged package proves nothing, so
the unchanged package is asserted to pass first.

The package's own checker is never run (0016): the consumer-phase checks are the factory's
tools/check-map.py, and TestPackageIsData replaces the packaged checker with a script that
leaves a sentinel file and lies about the verdict, and asserts intake ignores it both ways.

Run: python3 -m unittest discover -s tools/tests
"""
import importlib.util
import io
import json
import os
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

_spec = importlib.util.spec_from_file_location("factory_main", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
intake = factory.intake_step

HOYLE_TEXT = os.path.join(REPO, "examples", "hoyle-backgammon", "hoyle.txt")
PART107_XML = os.path.join(REPO, "examples", "faa-part-107", "part107.xml")
HOYLE_ID, HOYLE_VERSION = "RulesFactory.Maps.HoyleBackgammon", "4.0.0"
PART107_ID = "RulesFactory.Maps.FaaPart107"


def pack(map_dir, out):
    subprocess.run([sys.executable, PACK, map_dir, "--out", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
    return os.path.join(out, name)


def rewrite(source, target, replace):
    """Copy a package, replacing (bytes) or dropping (None) the named entries."""
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as dst:
        for info in src.infolist():
            if info.filename in replace:
                if replace[info.filename] is not None:
                    dst.writestr(info, replace[info.filename])
            else:
                dst.writestr(info, src.read(info.filename))
    return target


class IntakeCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        cls.hoyle = pack(os.path.join(REPO, "examples", "hoyle-backgammon"), os.path.join(cls.shared, "hoyle"))
        cls.part107 = pack(os.path.join(REPO, "examples", "faa-part-107"), os.path.join(cls.shared, "part107"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def map_with(self, status=None, **top):
        """Hoyle's packaged map, as bytes, with top-level fields set and entry 0's status changed."""
        with zipfile.ZipFile(self.hoyle) as archive:
            document = json.loads(archive.read("map/corpus-map.json"))
        document.update(top)
        if status is not None:
            document["entries"][0]["status"] = status
        return json.dumps(document).encode("utf-8")

    def produce(self, package, corpus):
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["produce", "--package", package, "--corpus", corpus,
                                 "--name", "Engine", "--out", os.path.join(self.tmp, "out"), "--allow-dirty",
                                 "--no-verify"])  # no .NET SDK assumed; test_factory_verify.py covers verify
        return code, buffer.getvalue()

    def assert_passes(self, package, corpus):
        code, output = self.produce(package, corpus)
        self.assertEqual(code, 0, output)
        self.assertIn("intake passed", output)
        return output

    def assert_refused(self, package, corpus, *expected):
        code, output = self.produce(package, corpus)
        self.assertEqual(code, 1, output)
        self.assertIn("REFUSED", output)
        for text in expected:
            self.assertIn(text, output)
        return output


class TestAccepts(IntakeCase):
    def test_hoyle_backgammon_2_0_0(self):
        output = self.assert_passes(self.hoyle, HOYLE_TEXT)
        self.assertIn(f"{HOYLE_ID} {HOYLE_VERSION}", output)
        self.assertIn("gutenberg-plain-text-including-boilerplate", output)
        self.assertIn("the factory's check-map.py --phase consumer", output)
        self.assertIn("map schemaVersion 1", output)

    def test_part_107(self):
        output = self.assert_passes(self.part107, PART107_XML)
        self.assertIn("ecfr-versioner-xml", output)
        self.assertIn("46 entries", output)

    def test_returns_what_later_steps_read(self):
        self.assertEqual(intake.intake(self.hoyle, HOYLE_TEXT, log=None).randomness, "seeded")
        result = intake.intake(self.part107, PART107_XML, log=None)
        self.assertEqual(result.randomness, "none")
        self.assertEqual(result.package_id, PART107_ID)
        self.assertEqual(len(result.map["entries"]), 46)
        self.assertEqual(result.corpus["sourceId"], "cfr-14-107")
        with open(PART107_XML, "rb") as handle:
            self.assertEqual(result.corpus_bytes, handle.read())

    def test_the_published_package_when_cached(self):
        cached = os.path.join(intake._global_packages_folder(), HOYLE_ID.lower(), HOYLE_VERSION,
                              f"{HOYLE_ID.lower()}.{HOYLE_VERSION}.nupkg")
        if not os.path.isfile(cached):
            self.skipTest(f"{HOYLE_ID} {HOYLE_VERSION} as served by nuget.org is not in the global packages folder")
        self.assert_passes(f"{HOYLE_ID}@{HOYLE_VERSION}", HOYLE_TEXT)


class TestRefuses(IntakeCase):
    def test_one_changed_corpus_byte(self):
        with open(PART107_XML, "rb") as handle:
            data = bytearray(handle.read())
        middle = len(data) // 2
        data[middle] = ord("X") if data[middle] != ord("X") else ord("Y")
        changed = os.path.join(self.tmp, "part107.xml")
        with open(changed, "wb") as handle:
            handle.write(data)
        self.assert_refused(self.part107, changed, "is not cfr-14-107 at the map's baseline")

    def test_the_other_corpus(self):
        self.assert_refused(self.part107, HOYLE_TEXT, "is not cfr-14-107")

    def test_a_manifest_that_is_not_committed_copy(self):
        with zipfile.ZipFile(self.part107) as archive:
            manifest = json.loads(archive.read("map/corpus-manifest.json"))
        corpus = manifest["corpora"][0]
        corpus["verification"] = "local-copy"
        corpus["envVar"] = "PART107_XML"
        del corpus["committedPath"]
        package = rewrite(self.part107, os.path.join(self.tmp, "local.nupkg"),
                          {"map/corpus-manifest.json": json.dumps(manifest).encode("utf-8")})
        self.assert_refused(package, PART107_XML, "NOT VERIFIED", "'local-copy'")

    def test_a_manifest_that_does_not_declare_randomness(self):
        """0019: a package from before the field is refused, never read as `none`."""
        with zipfile.ZipFile(self.part107) as archive:
            manifest = json.loads(archive.read("map/corpus-manifest.json"))
        for value in (None, "dice", True):
            with self.subTest(randomness=value):
                corpus = manifest["corpora"][0]
                if value is None:
                    corpus.pop("randomness", None)
                else:
                    corpus["randomness"] = value
                package = rewrite(self.part107, os.path.join(self.tmp, "randomness.nupkg"),
                                  {"map/corpus-manifest.json": json.dumps(manifest).encode("utf-8")})
                self.assert_refused(package, PART107_XML, f"cfr-14-107 declares randomness {value!r}")

    def test_a_package_missing_its_checker(self):
        package = rewrite(self.hoyle, os.path.join(self.tmp, "nochecker.nupkg"), {"tools/check-map.py": None})
        self.assert_refused(package, HOYLE_TEXT, "tools/check-map.py", "consumer-phase checker")

    def test_a_package_that_is_not_a_map_package(self):
        package = rewrite(self.hoyle, os.path.join(self.tmp, "noprops.nupkg"),
                          {f"build/{HOYLE_ID}.props": None})
        self.assert_refused(package, HOYLE_TEXT, "RulesFactoryMap")

    def test_an_unknown_hash_derivation(self):
        with zipfile.ZipFile(self.hoyle) as archive:
            document = json.loads(archive.read("map/corpus-map.json"))
            manifest = json.loads(archive.read("map/corpus-manifest.json"))
        document["baseline"]["hashDerivation"] = "work-text-only"
        manifest["corpora"][0]["hashDerivation"] = "work-text-only"
        package = rewrite(self.hoyle, os.path.join(self.tmp, "derivation.nupkg"), {
            "map/corpus-map.json": json.dumps(document).encode("utf-8"),
            "map/corpus-manifest.json": json.dumps(manifest).encode("utf-8"),
        })
        self.assert_refused(package, HOYLE_TEXT, "no way to compute hashDerivation 'work-text-only'")

    def test_a_map_the_consumer_checks_fail(self):
        package = rewrite(self.hoyle, os.path.join(self.tmp, "status.nupkg"),
                          {"map/corpus-map.json": self.map_with(status="finished")})
        self.assert_refused(package, HOYLE_TEXT, "factory's check-map.py --phase consumer exited 1",
                            "[fail] vocabulary")

    def test_a_schema_version_the_factory_does_not_read(self):
        package = rewrite(self.hoyle, os.path.join(self.tmp, "schema.nupkg"),
                          {"map/corpus-map.json": self.map_with(schemaVersion=2)})
        self.assert_refused(package, HOYLE_TEXT, "schemaVersion 2",
                            "reads schemaVersion " + ", ".join(map(str, intake.checker().SCHEMA_VERSIONS)))


class TestPackageIsData(IntakeCase):
    """0016: nothing from a package runs. Its checker is a hostile script here, and it never fires.

    The script writes a sentinel file at import time, so importing it would fire it as surely
    as running it, and then either exits 0 (claiming every map passes) or 1 (claiming every map
    fails). Intake must decide on the map's merits both ways, and the sentinel must not exist.
    """

    def hostile(self, name, exit_code, **map_changes):
        self.sentinel = os.path.join(self.tmp, "package-code-ran")
        script = (f"import sys\nopen({self.sentinel!r}, 'w').write('ran')\n"
                  f"print('everything passes')\nsys.exit({exit_code})\n").encode("utf-8")
        self.script = script
        replace = {"tools/check-map.py": script}
        if map_changes:
            replace["map/corpus-map.json"] = self.map_with(**map_changes)
        return rewrite(self.hoyle, os.path.join(self.tmp, name), replace)

    def test_a_checker_that_refuses_everything_does_not_refuse_a_good_map(self):
        package = self.hostile("fails.nupkg", 1)
        self.assert_passes(package, HOYLE_TEXT)
        self.assertFalse(os.path.exists(self.sentinel), "the package's checker ran")

    def test_a_checker_that_passes_everything_does_not_pass_a_bad_map(self):
        package = self.hostile("passes.nupkg", 0, status="finished")
        self.assert_refused(package, HOYLE_TEXT, "factory's check-map.py --phase consumer exited 1")
        self.assertFalse(os.path.exists(self.sentinel), "the package's checker ran")

    def test_its_bytes_are_still_what_provenance_hashes(self):
        package = self.hostile("hashed.nupkg", 0)
        result = intake.intake(package, HOYLE_TEXT, log=None)
        self.assertEqual(result.checker_raw, self.script)
        self.assertEqual(result.part_paths["checker"], "tools/check-map.py")
        self.assertFalse(os.path.exists(self.sentinel), "the package's checker ran")


if __name__ == "__main__":
    unittest.main()
