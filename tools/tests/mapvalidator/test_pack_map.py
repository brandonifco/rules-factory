#!/usr/bin/env python3
"""pack-map.py packs a map that passes its publish gate, and refuses one that does not.

0015's publish workflow runs this tool and pushes whatever it writes, so "refuses" has to
mean *writes nothing*: every refusal test below asserts the output directory holds no
package, not merely that the exit code was 1.

The subject is a copy of examples/hoyle-backgammon, the map 0015 publishes first. The
refusal case is trial 5's `depends-cycle` injection (examples/injection-trial), the cycle
#39 records passing an engine's gate green: `point-designations` made to depend on
`starting-position`, which already depends on it.

Run: python3 -m unittest discover -s tools/tests -t tools
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
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "pack-map.py")
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
        for name in ("corpus-map.json", "corpus-manifest.json", "hoyle.txt", "map-package.json",
                     "CORPUS-LICENCE.txt"):
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
                        f"build/{PACKAGE}.props", "LICENCE.txt"]))
            self.assertEqual(len([n for n in names if n.endswith(".psmdcp")]), 1, names)
            with open(os.path.join(HOYLE, "corpus-map.json"), "rb") as handle:
                self.assertEqual(archive.read("map/corpus-map.json"), handle.read())
            with open(os.path.join(HOYLE, "corpus-manifest.json"), "rb") as handle:
                self.assertEqual(archive.read("map/corpus-manifest.json"), handle.read())
            nuspec = archive.read(f"{PACKAGE}.nuspec").decode("utf-8")
            self.assertIn(f"<id>{PACKAGE}</id>", nuspec)
            self.assertIn(f"<version>{VERSION}</version>", nuspec)
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
            with open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "check-map.py"), "rb") as handle:
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

    def test_a_corpus_whose_licence_is_not_public_domain_or_open_is_refused_before_any_check(self):
        """0028: a licensed corpus's map is never packed, even with a terms file that states its licence."""
        self.edit("corpus-manifest.json", lambda m: m["corpora"][0].__setitem__("licence", "commercial"))
        with open(os.path.join(self.map_dir, "CORPUS-LICENCE.txt"), "w", encoding="utf-8") as handle:
            handle.write("The corpus is commercial.\n")
        code, output = self.pack()
        self.assert_refused(code, output)
        self.assertIn("hoyle-1909's manifest `licence` is 'commercial'", output)
        self.assertIn("docs/decisions/0028", output)
        self.assertNotIn("check-map.py --phase publish", output, "the licence is refused before any gate runs")

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


def nuspec_and_licence(nupkg, package):
    with zipfile.ZipFile(nupkg) as archive:
        return (archive.read(f"{package}.nuspec").decode("utf-8"),
                archive.read("LICENCE.txt").decode("utf-8"),
                archive.read("[Content_Types].xml").decode("utf-8"))


class TestLicence(PackCase):
    """0023: the package's licence follows its corpus, is declared, and travels in the package."""

    def write_settings(self, settings):
        with open(os.path.join(self.map_dir, "map-package.json"), "w", encoding="utf-8") as handle:
            json.dump(settings, handle)

    def test_the_nuspec_names_the_packaged_licence_file_and_no_expression(self):
        code, output = self.pack()
        self.assertEqual(code, 0, output)
        nuspec, licence, types = nuspec_and_licence(os.path.join(self.out, NUPKG), PACKAGE)
        self.assertIn('<license type="file">LICENCE.txt</license>', nuspec)
        # nuget.org's required companion to a licence file (#50 found the expression's).
        self.assertIn("<licenseUrl>https://aka.ms/deprecateLicenseUrl</licenseUrl>", nuspec)
        self.assertNotIn('type="expression"', nuspec)
        self.assertNotIn("licenses.nuget.org", nuspec)
        self.assertIn('Extension="txt"', types)

    def test_a_public_domain_corpus_is_stated_as_such_and_not_as_apache_or_cc0(self):
        code, output = self.pack()
        self.assertEqual(code, 0, output)
        _, licence, _ = nuspec_and_licence(os.path.join(self.out, NUPKG), PACKAGE)
        with open(os.path.join(HOYLE, "CORPUS-LICENCE.txt"), encoding="utf-8") as handle:
            terms = handle.read()
        self.assertIn(terms, licence)
        self.assertIn("public-domain-underlying-work; Project Gutenberg trademark terms apply to the edition",
                      licence)
        self.assertIn("Apache-2.0 does not apply to them", licence)
        part_a = licence.split("===== A.")[1].split("===== B.")[0]
        self.assertNotIn("Apache", part_a)
        self.assertIn("not placed under CC0", part_a)

    def test_the_factory_code_is_under_the_repositorys_own_apache_licence_verbatim(self):
        code, output = self.pack()
        self.assertEqual(code, 0, output)
        _, licence, _ = nuspec_and_licence(os.path.join(self.out, NUPKG), PACKAGE)
        with open(os.path.join(REPO, "LICENSE"), encoding="utf-8") as handle:
            self.assertTrue(licence.endswith(handle.read()))
        self.assertIn("tools/check-map.py", licence.split("===== A.")[0])

    def test_part_107_packs_with_its_us_government_terms(self):
        part107 = os.path.join(REPO, "examples", "faa-part-107")
        inputs = pack_map.read_inputs(part107)
        inputs["corpus_terms"] = pack_map.corpus_terms(inputs)
        licence = pack_map.licence_file(inputs).decode("utf-8")
        self.assertIn("public-domain-us-government", licence)
        self.assertIn("17 U.S.C. 105", licence)

    def test_no_licence_declared_is_refused_and_nothing_defaults(self):
        self.write_settings({"version": VERSION})
        code, output = self.pack("--tag", TAG)
        self.assert_refused(code, output)
        self.assertIn("licence.corpusTerms", output)

    def test_a_missing_terms_file_is_refused(self):
        os.remove(os.path.join(self.map_dir, "CORPUS-LICENCE.txt"))
        code, output = self.pack()
        self.assert_refused(code, output)

    def test_a_terms_path_outside_the_map_directory_is_refused(self):
        self.write_settings({"version": VERSION, "licence": {"corpusTerms": "../LICENSE.txt"}})
        code, output = self.pack()
        self.assert_refused(code, output)

    def test_terms_that_do_not_restate_the_manifest_licence_are_refused(self):
        with open(os.path.join(self.map_dir, "CORPUS-LICENCE.txt"), "w", encoding="utf-8") as handle:
            handle.write("Apache-2.0\n")
        code, output = self.pack()
        self.assert_refused(code, output)
        self.assertIn("does not restate hoyle-1909", output)

    def test_a_changed_manifest_licence_is_refused_until_the_terms_follow_it(self):
        self.edit("corpus-manifest.json", lambda m: m["corpora"][0].__setitem__("licence", "CC-BY-4.0"))
        code, output = self.pack()
        self.assert_refused(code, output)

    def test_a_corpus_with_no_licence_is_refused(self):
        self.edit("corpus-manifest.json", lambda m: m["corpora"][0].pop("licence"))
        code, output = self.pack()
        self.assert_refused(code, output)
        self.assertIn("no `licence`", output)

    def test_a_licence_change_changes_the_bytes_and_repacking_does_not(self):
        self.assertEqual(self.pack()[0], 0)
        with open(os.path.join(self.out, NUPKG), "rb") as handle:
            before = handle.read()
        with open(os.path.join(self.map_dir, "CORPUS-LICENCE.txt"), "a", encoding="utf-8") as handle:
            handle.write("\nA clarification.\n")
        again = os.path.join(self.tmp, "again")
        self.assertEqual(self.pack(out=again)[0], 0)
        with open(os.path.join(again, NUPKG), "rb") as handle:
            self.assertNotEqual(handle.read(), before)


class TestSrdAttribution(unittest.TestCase):
    """The SRD 5.2.1 map quotes CC-BY-4.0 text: its package carries WotC's statement word for word."""

    SRD = os.path.join(REPO, "examples", "srd-52-combat")
    PACKAGE = "RulesFactory.Maps.Srd52Combat"
    STATEMENT = ("This work includes material from the System Reference Document 5.2.1 (“SRD 5.2.1”) by "
                 "Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is "
                 "licensed under the Creative Commons Attribution 4.0 International License, available at "
                 "https://creativecommons.org/licenses/by/4.0/legalcode.")

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.map_dir = os.path.join(cls.tmp, "srd-52-combat")
        os.makedirs(cls.map_dir)
        for name in ("corpus-map.json", "corpus-manifest.json", "srd-5.2.1.txt", "map-package.json",
                     "CORPUS-LICENCE.txt"):
            shutil.copy(os.path.join(cls.SRD, name), cls.map_dir)
        with open(os.path.join(cls.SRD, "map-package.json"), encoding="utf-8") as handle:
            version = json.load(handle)["version"]
        cls.nupkg = f"{cls.PACKAGE}.{version}.nupkg"
        cls.digests, cls.outputs = [], []
        for out in ("a", "b"):
            buffer = io.StringIO()
            with redirect_stdout(buffer), redirect_stderr(buffer):
                code = pack_map.main([cls.map_dir, "--out", os.path.join(cls.tmp, out)])
            cls.outputs.append((code, buffer.getvalue()))
            if code == 0:
                with open(os.path.join(cls.tmp, out, cls.nupkg), "rb") as handle:
                    cls.digests.append(hashlib.sha256(handle.read()).hexdigest())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def test_the_srd_map_packs_twice_to_the_same_bytes(self):
        for code, output in self.outputs:
            self.assertEqual(code, 0, output)
        self.assertEqual(len(set(self.digests)), 1, self.digests)

    def test_the_attribution_statement_is_embedded_verbatim_in_the_licence_file(self):
        self.assertEqual(self.outputs[0][0], 0, self.outputs[0][1])
        nuspec, licence, _ = nuspec_and_licence(os.path.join(self.tmp, "a", self.nupkg), self.PACKAGE)
        self.assertIn(self.STATEMENT, licence)
        self.assertIn("CC-BY-4.0", licence)
        self.assertIn('<license type="file">LICENCE.txt</license>', nuspec)
        # Its terms ask for no other attribution to Wizards: the nuspec itself names none.
        self.assertNotIn("Wizards", nuspec)

    def test_the_statement_the_test_holds_is_the_one_on_the_corpus_legal_page(self):
        with open(os.path.join(self.SRD, "srd-5.2.1.txt"), encoding="utf-8") as handle:
            page_one = handle.read(4000)
        self.assertIn(pack_map.squash(self.STATEMENT).replace("4.0/legalcode", "4.0/ legalcode"),
                      pack_map.squash(page_one))


class TestPackageId(unittest.TestCase):
    def test_the_id_is_derived_from_the_directory_name(self):
        self.assertEqual(pack_map.package_id("hoyle-backgammon"), PACKAGE)
        self.assertEqual(pack_map.package_id("faa-part-107"), "RulesFactory.Maps.FaaPart107")


if __name__ == "__main__":
    unittest.main()
