#!/usr/bin/env python3
"""pack-map.py packs a map that passes its publish gate, and refuses one that does not.

0015's publish workflow runs this tool and pushes whatever it writes, so "refuses" has to
mean *writes nothing*: every refusal test below asserts the output directory holds no
package, not merely that the exit code was 1.

The subject is a copy of examples/hoyle-backgammon, the map 0015 publishes first. The
refusal case is trial 5's `depends-cycle` injection (examples/injection-trial), the cycle
#39 records passing an engine's gate green: `point-designations` made to depend on
`starting-position`, which already depends on it.

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
import zipfile
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(os.path.dirname(HERE), "pack-map.py")
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")

_spec = importlib.util.spec_from_file_location("pack_map", TOOL)
pack_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pack_map)

PACKAGE = "RulesFactory.Maps.HoyleBackgammon"
with open(os.path.join(HOYLE, "map-package.json"), encoding="utf-8") as _handle:
    VERSION = json.load(_handle)["version"]
NUPKG = f"{PACKAGE}.{VERSION}.nupkg"
TAG = f"map/hoyle-backgammon/v{VERSION}"


class PackCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.map_dir = os.path.join(self.tmp, "hoyle-backgammon")
        os.makedirs(self.map_dir)
        for name in ("corpus-map.json", "corpus-manifest.json", "hoyle.txt", "map-package.json"):
            shutil.copy(os.path.join(HOYLE, name), self.map_dir)
        self.out = os.path.join(self.tmp, "out")

    def edit(self, name, change):
        path = os.path.join(self.map_dir, name)
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        change(document)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)

    def entry(self, document, entry_id):
        return next(e for e in document["entries"] if e["id"] == entry_id)

    def pack(self, *extra, out=None):
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = pack_map.main([self.map_dir, "--out", out or self.out, *extra])
        return code, buffer.getvalue()

    def packages(self, out=None):
        directory = out or self.out
        return sorted(os.listdir(directory)) if os.path.isdir(directory) else []

    def assert_refused(self, code, output, expect_code=1):
        self.assertEqual(code, expect_code, output)
        self.assertEqual(self.packages(), [], f"a refused map left a package behind:\n{output}")


class TestPacksTheExample(PackCase):
    def test_the_example_passes_its_gate_and_packs(self):
        code, output = self.pack("--tag", TAG)
        self.assertEqual(code, 0, output)
        self.assertEqual(self.packages(), [NUPKG], output)

    def test_the_package_carries_the_map_verbatim_and_nothing_unexpected(self):
        code, output = self.pack()
        self.assertEqual(code, 0, output)
        with zipfile.ZipFile(os.path.join(self.out, NUPKG)) as archive:
            names = archive.namelist()
            self.assertEqual(
                sorted(n for n in names if not n.endswith(".psmdcp")),
                sorted(["_rels/.rels", "[Content_Types].xml", f"{PACKAGE}.nuspec",
                        "map/corpus-map.json", "map/corpus-manifest.json", "tools/check-map.py",
                        f"build/{PACKAGE}.props"]))
            self.assertEqual(len([n for n in names if n.endswith(".psmdcp")]), 1, names)
            with open(os.path.join(HOYLE, "corpus-map.json"), "rb") as handle:
                self.assertEqual(archive.read("map/corpus-map.json"), handle.read())
            with open(os.path.join(HOYLE, "corpus-manifest.json"), "rb") as handle:
                self.assertEqual(archive.read("map/corpus-manifest.json"), handle.read())
            nuspec = archive.read(f"{PACKAGE}.nuspec").decode("utf-8")
            self.assertIn(f"<id>{PACKAGE}</id>", nuspec)
            self.assertIn(f"<version>{VERSION}</version>", nuspec)
            self.assertIn("<licenseUrl>https://licenses.nuget.org/Apache-2.0</licenseUrl>", nuspec)
            self.assertIn("schemaVersion 1", nuspec)
            self.assertIn("5d505fa9f6202340eb55313b8ef607b816087a860d3d51b1bf92b5f65240645e", nuspec)

    def test_two_packs_are_byte_identical(self):
        second = os.path.join(self.tmp, "again")
        self.assertEqual(self.pack()[0], 0)
        self.assertEqual(self.pack(out=second)[0], 0)
        digests = set()
        for directory in (self.out, second):
            with open(os.path.join(directory, NUPKG), "rb") as handle:
                digests.add(hashlib.sha256(handle.read()).hexdigest())
        self.assertEqual(len(digests), 1, digests)

    def test_a_manifest_declaring_an_uncited_corpus_is_narrowed(self):
        def add_corpus(manifest):
            extra = dict(manifest["corpora"][0], sourceId="some-other-book")
            manifest["corpora"].append(extra)
        self.edit("corpus-manifest.json", add_corpus)
        code, output = self.pack()
        self.assertEqual(code, 0, output)
        with zipfile.ZipFile(os.path.join(self.out, NUPKG)) as archive:
            packaged = json.loads(archive.read("map/corpus-manifest.json"))
        self.assertEqual([c["sourceId"] for c in packaged["corpora"]], ["hoyle-1909"])


class TestCarriesTheConsumerChecker(PackCase):
    """#51: the engine runs the status-dependent checks from the package, not from a copy.

    Each test runs the packaged checker from a directory holding only the extracted package,
    so a checker that needed anything from this repository beyond its own bytes fails here.
    """

    def extract(self):
        code, output = self.pack()
        self.assertEqual(code, 0, output)
        root = os.path.join(self.tmp, "restored")
        with zipfile.ZipFile(os.path.join(self.out, NUPKG)) as archive:
            archive.extractall(root)
        return root

    def run_packaged(self, root, map_path):
        return subprocess.run(
            [sys.executable, os.path.join(root, "tools", "check-map.py"), map_path, "--phase", "consumer"],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def test_the_package_carries_the_checker_verbatim_and_the_props_names_it(self):
        code, output = self.pack()
        self.assertEqual(code, 0, output)
        with zipfile.ZipFile(os.path.join(self.out, NUPKG)) as archive:
            with open(os.path.join(os.path.dirname(HERE), "check-map.py"), "rb") as handle:
                self.assertEqual(archive.read("tools/check-map.py"), handle.read())
            props = archive.read(f"build/{PACKAGE}.props").decode("utf-8")
        self.assertIn('ConsumerChecker="$(MSBuildThisFileDirectory)../tools/check-map.py"', props)

    def test_the_packaged_checker_passes_the_packaged_map_in_the_consumer_phase(self):
        root = self.extract()
        completed = self.run_packaged(root, os.path.join(root, "map", "corpus-map.json"))
        self.assertEqual(completed.returncode, 0, completed.stdout)
        for check in ("vocabulary", "status", "absent", "correspondence"):
            self.assertRegex(completed.stdout, rf"\[(ok|skip)\] {check}:")
        self.assertNotIn("] schema:", completed.stdout)  # structure was discharged at publish

    def test_the_packaged_checker_fails_a_merge_with_a_status_dependent_error(self):
        root = self.extract()
        with open(os.path.join(root, "map", "corpus-map.json"), encoding="utf-8") as handle:
            merged = json.load(handle)
        # What an overlay can do and structure cannot see: claim `implemented` with no tests.
        entry = self.entry(merged, "player-count")
        entry.update(status="implemented", implementedIn={"ruleset": "hoyle", "version": 1})
        entry.pop("tests", None)
        path = os.path.join(root, "map", "merged.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(merged, handle, indent=2)
        completed = self.run_packaged(root, path)
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("[fail] status:", completed.stdout)


class TestRefuses(PackCase):
    def test_a_depends_on_cycle_is_refused_and_writes_nothing(self):
        # Trial 5's depends-cycle: the injection #39 records passing the engine's gate green.
        self.edit("corpus-map.json", lambda m: self.entry(m, "point-designations")
                  .setdefault("dependsOn", []).append("starting-position"))
        code, output = self.pack("--tag", TAG)
        self.assert_refused(code, output)
        self.assertIn("dependsOn cycle", output)
        self.assertIn("REFUSED", output)

    def test_a_citation_to_the_wrong_page_is_refused(self):
        def move(document):
            locator = self.entry(document, "player-count")["locator"]
            locator["citation"] = locator["citation"].replace("p. 271", "p. 279")
        self.edit("corpus-map.json", move)
        code, output = self.pack()
        self.assert_refused(code, output)
        self.assertIn("check-locators.py", output)

    def test_a_status_dependent_failure_is_refused_at_publish_too(self):
        self.edit("corpus-map.json", lambda m: self.entry(m, "player-count")
                  .__setitem__("implementedIn", {"ruleset": "hoyle", "version": 1}))
        code, output = self.pack()
        self.assert_refused(code, output)

    def test_a_corpus_that_is_not_committed_is_not_verified_and_refused(self):
        def local(manifest):
            corpus = manifest["corpora"][0]
            corpus.update(verification="local-copy", envVar="HOYLE_TXT")
            corpus.pop("committedPath")
        self.edit("corpus-manifest.json", local)
        code, output = self.pack()
        self.assert_refused(code, output)

    def test_an_adapter_with_no_locator_checker_is_refused(self):
        self.edit("corpus-manifest.json", lambda m: m["corpora"][0].__setitem__("adapter", "pdf"))
        code, output = self.pack()
        self.assert_refused(code, output)
        self.assertIn("NOT VERIFIED", output)

    def test_a_tag_that_disagrees_with_the_reviewed_version_is_refused(self):
        code, output = self.pack("--tag", "map/hoyle-backgammon/v0.0.1")
        self.assert_refused(code, output, expect_code=2)

    def test_a_tag_naming_another_map_is_refused(self):
        code, output = self.pack("--tag", f"map/faa-part-107/v{VERSION}")
        self.assert_refused(code, output, expect_code=2)

    def test_a_version_that_is_not_semver_is_refused(self):
        with open(os.path.join(self.map_dir, "map-package.json"), "w") as handle:
            json.dump({"version": "1.0"}, handle)
        code, output = self.pack()
        self.assert_refused(code, output, expect_code=2)


class TestPackageId(unittest.TestCase):
    def test_the_id_is_derived_from_the_directory_name(self):
        self.assertEqual(pack_map.package_id("hoyle-backgammon"), PACKAGE)
        self.assertEqual(pack_map.package_id("faa-part-107"), "RulesFactory.Maps.FaaPart107")


if __name__ == "__main__":
    unittest.main()
