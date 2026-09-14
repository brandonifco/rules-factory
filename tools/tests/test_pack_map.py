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
        code, output = self.pack("--tag", "map/hoyle-backgammon/v1.0.0")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.packages(), [f"{PACKAGE}.1.0.0.nupkg"], output)

    def test_the_package_carries_the_map_verbatim_and_nothing_unexpected(self):
        code, output = self.pack()
        self.assertEqual(code, 0, output)
        with zipfile.ZipFile(os.path.join(self.out, f"{PACKAGE}.1.0.0.nupkg")) as archive:
            names = archive.namelist()
            self.assertEqual(
                sorted(n for n in names if not n.endswith(".psmdcp")),
                sorted(["_rels/.rels", "[Content_Types].xml", f"{PACKAGE}.nuspec",
                        "map/corpus-map.json", "map/corpus-manifest.json", f"build/{PACKAGE}.props"]))
            self.assertEqual(len([n for n in names if n.endswith(".psmdcp")]), 1, names)
            with open(os.path.join(HOYLE, "corpus-map.json"), "rb") as handle:
                self.assertEqual(archive.read("map/corpus-map.json"), handle.read())
            with open(os.path.join(HOYLE, "corpus-manifest.json"), "rb") as handle:
                self.assertEqual(archive.read("map/corpus-manifest.json"), handle.read())
            nuspec = archive.read(f"{PACKAGE}.nuspec").decode("utf-8")
            self.assertIn(f"<id>{PACKAGE}</id>", nuspec)
            self.assertIn("<version>1.0.0</version>", nuspec)
            self.assertIn("schemaVersion 1", nuspec)
            self.assertIn("5d505fa9f6202340eb55313b8ef607b816087a860d3d51b1bf92b5f65240645e", nuspec)

    def test_two_packs_are_byte_identical(self):
        second = os.path.join(self.tmp, "again")
        self.assertEqual(self.pack()[0], 0)
        self.assertEqual(self.pack(out=second)[0], 0)
        digests = set()
        for directory in (self.out, second):
            with open(os.path.join(directory, f"{PACKAGE}.1.0.0.nupkg"), "rb") as handle:
                digests.add(hashlib.sha256(handle.read()).hexdigest())
        self.assertEqual(len(digests), 1, digests)

    def test_a_manifest_declaring_an_uncited_corpus_is_narrowed(self):
        def add_corpus(manifest):
            extra = dict(manifest["corpora"][0], sourceId="some-other-book")
            manifest["corpora"].append(extra)
        self.edit("corpus-manifest.json", add_corpus)
        code, output = self.pack()
        self.assertEqual(code, 0, output)
        with zipfile.ZipFile(os.path.join(self.out, f"{PACKAGE}.1.0.0.nupkg")) as archive:
            packaged = json.loads(archive.read("map/corpus-manifest.json"))
        self.assertEqual([c["sourceId"] for c in packaged["corpora"]], ["hoyle-1909"])


class TestRefuses(PackCase):
    def test_a_depends_on_cycle_is_refused_and_writes_nothing(self):
        # Trial 5's depends-cycle: the injection #39 records passing the engine's gate green.
        self.edit("corpus-map.json", lambda m: self.entry(m, "point-designations")
                  .setdefault("dependsOn", []).append("starting-position"))
        code, output = self.pack("--tag", "map/hoyle-backgammon/v1.0.0")
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
        code, output = self.pack("--tag", "map/hoyle-backgammon/v1.0.1")
        self.assert_refused(code, output, expect_code=2)

    def test_a_tag_naming_another_map_is_refused(self):
        code, output = self.pack("--tag", "map/faa-part-107/v1.0.0")
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
