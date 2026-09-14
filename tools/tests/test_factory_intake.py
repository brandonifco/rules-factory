#!/usr/bin/env python3
"""The factory's intake (#3, M1) accepts a real map package and refuses each thing it exists to catch.

The packages are built here with tools/pack-map.py from examples/, not downloaded: the tests
need no network, and pack-map.py is deterministic, so `examples/hoyle-backgammon` packs to
RulesFactory.Maps.HoyleBackgammon 2.0.0 with the map, manifest, checker and props that
nuget.org serves (their bytes were compared against the published package when this test was
written; the published package adds only nuget.org's signature). When that published package
is in the NuGet global packages folder it is also run through intake, and that test says it
was skipped otherwise.

Each refusal starts from a package that passes and changes exactly one thing, and asserts a
non-zero exit -- a refusal test that also fails on the unchanged package proves nothing, so
the unchanged package is asserted to pass first.

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
HOYLE_ID, HOYLE_VERSION = "RulesFactory.Maps.HoyleBackgammon", "2.0.0"
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

    def produce(self, package, corpus):
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["produce", "--package", package, "--corpus", corpus,
                                 "--name", "Engine", "--out", os.path.join(self.tmp, "out")])
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
        self.assertIn("--phase consumer", output)

    def test_part_107(self):
        output = self.assert_passes(self.part107, PART107_XML)
        self.assertIn("ecfr-versioner-xml", output)
        self.assertIn("40 entries", output)

    def test_returns_what_later_steps_read(self):
        result = intake.intake(self.part107, PART107_XML, log=None)
        self.assertEqual(result.package_id, PART107_ID)
        self.assertEqual(len(result.map["entries"]), 40)
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

    def test_a_map_its_own_consumer_checks_fail(self):
        with zipfile.ZipFile(self.hoyle) as archive:
            document = json.loads(archive.read("map/corpus-map.json"))
        document["entries"][0]["status"] = "finished"
        package = rewrite(self.hoyle, os.path.join(self.tmp, "status.nupkg"),
                          {"map/corpus-map.json": json.dumps(document).encode("utf-8")})
        self.assert_refused(package, HOYLE_TEXT, "check-map.py --phase consumer exited 1")


if __name__ == "__main__":
    unittest.main()
