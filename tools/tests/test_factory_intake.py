#!/usr/bin/env python3
"""The factory's intake (#3, M1) accepts a real map package and refuses each thing it exists to catch.

The packages are built here with tools/pack-map.py from examples/, not downloaded: the tests
need no network, and pack-map.py is deterministic, so `examples/hoyle-backgammon` packs to
RulesFactory.Maps.HoyleBackgammon 6.0.0 with the map, manifest, checker and props that
nuget.org serves (their bytes were compared against the published 2.0.0 package when this test
was written; the published package adds only nuget.org's signature, and later versions differ
from 2.0.0 in the checker's bytes and, from #95, #102, 0025, 0026 and #125, the map's; from 0023, the packaged licence). When that published package is in the NuGet global
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
import struct
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
HOYLE_ID, HOYLE_VERSION = "RulesFactory.Maps.HoyleBackgammon", "6.0.0"
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
        # `--no-verify` ends NOT VERIFIED (3), never 0: the engine was written but never built
        # or tested (tools/factory/__main__.py).
        self.assertEqual(code, factory.NOT_VERIFIED, output)
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
        self.assertIn("47 entries", output)

    def test_returns_what_later_steps_read(self):
        self.assertEqual(intake.intake(self.hoyle, HOYLE_TEXT, log=None).randomness, "seeded")
        result = intake.intake(self.part107, PART107_XML, log=None)
        self.assertEqual(result.randomness, "none")
        self.assertEqual(result.package_id, PART107_ID)
        self.assertEqual(len(result.map["entries"]), 47)
        self.assertEqual(result.corpus["sourceId"], "cfr-14-107")
        with open(PART107_XML, "rb") as handle:
            self.assertEqual(result.corpus_bytes, handle.read())

    def test_every_example_corpus_licence_is_admitted(self):
        """0028: the committed corpora the factory produces from are all public domain or open."""
        classes = {}
        for name in ("hoyle-backgammon", "faa-part-107", "srd-52-combat"):
            with open(os.path.join(REPO, "examples", name, "corpus-manifest.json"), encoding="utf-8") as handle:
                for corpus in json.load(handle)["corpora"]:
                    classes[corpus["sourceId"]] = intake.licence_class(corpus.get("licence"))
        self.assertEqual(classes, {"hoyle-1909": "public-domain", "cfr-14-107": "public-domain", "srd-5.2.1": "open"})

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

    def part107_with_licence(self, licence, **changes):
        with zipfile.ZipFile(self.part107) as archive:
            manifest = json.loads(archive.read("map/corpus-manifest.json"))
        corpus = manifest["corpora"][0]
        if licence is None:
            corpus.pop("licence", None)
        else:
            corpus["licence"] = licence
        corpus.update(changes)
        return rewrite(self.part107, os.path.join(self.tmp, "licence.nupkg"),
                       {"map/corpus-manifest.json": json.dumps(manifest).encode("utf-8")})

    def test_a_licence_that_is_not_public_domain_or_open(self):
        """0028: the factory admits only corpora whose licence permits committing and publishing them."""
        for licence in ("commercial", "All rights reserved", "CC-BY-NC-4.0", "CC-BY-4.0-with-exceptions",
                        "public-domainish", "Public-Domain", "", None):
            with self.subTest(licence=licence):
                package = self.part107_with_licence(licence)
                self.assert_refused(package, PART107_XML, f"cfr-14-107's manifest `licence` is {licence!r}",
                                    "neither public domain", "docs/decisions/0028")
                self.assertFalse(os.path.exists(os.path.join(self.tmp, "out")), "a refused intake wrote the engine")

    def test_a_licensed_corpus_is_refused_by_its_licence_before_its_posture(self):
        package = self.part107_with_licence("commercial", verification="local-copy", boundaryPolicy="never-commit",
                                            quotation="withheld", envVar="PART107_XML")
        output = self.assert_refused(package, PART107_XML, "docs/decisions/0028")
        self.assertNotIn("NOT VERIFIED", output)

    def test_open_and_public_domain_licences_are_admitted(self):
        for licence in ("public-domain", "public-domain-us-government", "CC0-1.0",
                        "CC-BY-4.0. Attribution required: This work includes material from a test corpus."):
            with self.subTest(licence=licence):
                self.assert_passes(self.part107_with_licence(licence), PART107_XML)
                shutil.rmtree(os.path.join(self.tmp, "out"), True)

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


class TestNothingIsReadWithoutALimit(IntakeCase):
    """#187: a package is bounded on the way in, before any of it has been verified.

    Every guarantee intake offers is computed from bytes it already holds, so the caps are the
    only thing standing between a hostile or broken package and the operator's memory or disk.
    """

    def repacked(self, name, member, data, compress_type=zipfile.ZIP_STORED):
        """Hoyle's package with one member replaced, stored or deflated as asked."""
        target = os.path.join(self.tmp, name)
        with zipfile.ZipFile(self.hoyle) as src, zipfile.ZipFile(target, "w") as dst:
            for info in src.infolist():
                if info.filename == member:
                    info = zipfile.ZipInfo(member, date_time=info.date_time)
                    info.compress_type = compress_type
                    dst.writestr(info, data)
                else:
                    dst.writestr(info, src.read(info.filename))
        return target

    def opens_during(self, call):
        """(the exception, the member names intake actually opened) -- what proves "unread"."""
        opened = []
        original = zipfile.ZipFile.open

        def spy(archive, name, *args, **kwargs):
            opened.append(name if isinstance(name, str) else name.filename)
            return original(archive, name, *args, **kwargs)

        zipfile.ZipFile.open = spy  # ZipFile.read() goes through open(), so it is caught here too
        try:
            with self.assertRaises(intake.Refused) as raised:
                call()
        finally:
            zipfile.ZipFile.open = original
        return raised.exception, opened

    def test_a_member_over_the_size_cap_is_refused_without_being_read(self):
        oversized = intake.MAX_MEMBER_BYTES + 1
        package = self.repacked("big-map.nupkg", "map/corpus-map.json", b"x" * oversized)
        error, opened = self.opens_during(lambda: intake.read_package(package))
        self.assertIn(str(oversized), str(error))
        self.assertIn(str(intake.MAX_MEMBER_BYTES), str(error))
        self.assertNotIn("map/corpus-map.json", opened, "the oversized member was read before it was refused")

    def test_a_member_over_the_compression_ratio_is_refused_without_being_read(self):
        """Under the size cap and still a bomb: 4 MiB of zeros is a few KB on the wire."""
        package = self.repacked("bomb.nupkg", "map/corpus-map.json", b"\0" * (4 * 1024 * 1024),
                                compress_type=zipfile.ZIP_DEFLATED)
        error, opened = self.opens_during(lambda: intake.read_package(package))
        self.assertIn(f"over the {intake.MAX_COMPRESSION_RATIO}", str(error))
        self.assertNotIn("map/corpus-map.json", opened)

    def test_a_member_that_declares_less_than_it_holds_is_refused_not_a_traceback(self):
        """`file_size` is the package's claim, not a measurement -- so a package can lie about it.

        It does not get more memory by lying: zipfile stops at the declared size and the CRC then
        fails. What this asserts is that the failure comes out as a refusal.
        """
        member = "map/corpus-map.json"
        package = self.repacked("liar.nupkg", member, b"y" * 4096, zipfile.ZIP_DEFLATED)
        with open(package, "rb") as handle:  # understate the member in both headers, as a hostile packer would
            raw = handle.read().replace(struct.pack("<I", 4096), struct.pack("<I", 16))
        with open(package, "wb") as handle:
            handle.write(raw)
        with zipfile.ZipFile(package) as archive:
            self.assertEqual(archive.getinfo(member).file_size, 16)
            with self.assertRaises(intake.Refused) as raised:
                intake._read_member(archive, member)
        self.assertIn("cannot be read as the 16 bytes it declares", str(raised.exception))

    def test_a_package_that_passes_is_unaffected_by_the_caps(self):
        """The caps are sized off real packages; the ones this factory builds are far under them."""
        self.assert_passes(self.hoyle, HOYLE_TEXT)
        with zipfile.ZipFile(self.hoyle) as archive:
            for info in archive.infolist():
                self.assertLess(info.file_size, intake.MAX_MEMBER_BYTES)
        self.assertLess(os.path.getsize(self.hoyle), intake.MAX_PACKAGE_BYTES)


class TestADocumentTypeIsRefused(IntakeCase):
    """#210: a nuspec or props that declares a DTD is refused before it is parsed.

    The size caps bound the bytes read, not what the parser expands them to, and a map package has
    no reason to carry a DTD: nothing tools/pack-map.py builds declares one.
    """

    NUSPEC = f"{HOYLE_ID}.nuspec"
    PROPS = f"build/{HOYLE_ID}.props"
    LAUGHS = (b'<!DOCTYPE lolz [\n  <!ENTITY lol "lol">\n'
              + b"".join(b'  <!ENTITY lol%d "%s">\n' % (n, (b"&lol%s;" % (str(n - 1).encode() if n > 1 else b"")) * 10)
                         for n in range(1, 10))
              + b"]>\n")

    def member(self, name):
        with zipfile.ZipFile(self.hoyle) as archive:
            return archive.read(name)

    def with_declaration(self, name, declaration, entity=b""):
        """Hoyle's member with a document type declared after its XML declaration (if any), and
        `entity` referenced in its first element's text."""
        data = self.member(name)
        head, sep, rest = data.partition(b"?>\n") if data.startswith(b"<?xml") else (b"", b"", data)
        if entity:
            rest = rest.replace(b"<id>", b"<id>" + entity, 1) if name == self.NUSPEC else \
                rest.replace(b"<ItemGroup>", b"<ItemGroup>" + entity, 1)
        return head + sep + declaration + rest

    def test_a_nuspec_that_declares_a_doctype_is_refused_naming_why(self):
        package = rewrite(self.hoyle, os.path.join(self.tmp, "doctype.nupkg"),
                          {self.NUSPEC: self.with_declaration(self.NUSPEC, b"<!DOCTYPE package>\n")})
        self.assert_refused(package, HOYLE_TEXT, self.NUSPEC, "declares a document type (DTD)", "0016")

    def test_a_props_that_declares_a_doctype_is_refused_naming_why(self):
        package = rewrite(self.hoyle, os.path.join(self.tmp, "doctype.nupkg"),
                          {self.PROPS: self.with_declaration(self.PROPS, b"<!DOCTYPE Project>\n")})
        self.assert_refused(package, HOYLE_TEXT, self.PROPS, "declares a document type (DTD)", "0016")

    def test_a_billion_laughs_in_either_member_is_refused_not_expanded(self):
        for name in (self.NUSPEC, self.PROPS):
            with self.subTest(member=name):
                package = rewrite(self.hoyle, os.path.join(self.tmp, "laughs.nupkg"),
                                  {name: self.with_declaration(name, self.LAUGHS, b"&lol9;")})
                self.assert_refused(package, HOYLE_TEXT, name, "declares a document type (DTD)")

    def test_a_doctype_in_another_encoding_is_still_refused(self):
        """A search of the bytes for `<!DOCTYPE` reads straight past UTF-16; the parser does not."""
        text = self.with_declaration(self.NUSPEC, b"<!DOCTYPE package>\n").decode("utf-8")
        text = text.replace('encoding="utf-8"', 'encoding="utf-16"', 1)
        package = rewrite(self.hoyle, os.path.join(self.tmp, "utf16.nupkg"), {self.NUSPEC: text.encode("utf-16")})
        self.assert_refused(package, HOYLE_TEXT, self.NUSPEC, "declares a document type (DTD)")

    def test_a_malformed_nuspec_is_refused_not_a_traceback(self):
        package = rewrite(self.hoyle, os.path.join(self.tmp, "malformed.nupkg"),
                          {self.NUSPEC: self.member(self.NUSPEC).replace(b"</package>", b"")})
        self.assert_refused(package, HOYLE_TEXT, self.NUSPEC, "is not well-formed XML")

    def test_packages_pack_map_builds_are_unaffected(self):
        """The refusal is a boundary pack-map.py's output is inside: both real packages still pass."""
        self.assert_passes(self.hoyle, HOYLE_TEXT)
        self.assert_passes(self.part107, PART107_XML)
        for package in (self.hoyle, self.part107):
            with zipfile.ZipFile(package) as archive:
                for name in archive.namelist():
                    if name.endswith((".nuspec", ".props")):
                        self.assertNotIn(b"<!DOCTYPE", archive.read(name))


class FakeResponse:
    """A urlopen response that serves `body` in chunks, or raises partway through."""

    def __init__(self, body, fail_after=None):
        self.stream, self.fail_after, self.served = io.BytesIO(body), fail_after, 0

    def read(self, size):
        if self.fail_after is not None and self.served >= self.fail_after:
            raise OSError("the mirror hung up")
        chunk = self.stream.read(size)
        self.served += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestDownloadIsBounded(IntakeCase):
    """#187: the download is capped and hashed as it streams, and a refusal leaves nothing behind."""

    SPEC = "Not.A.Real.Package@9.9.9"

    def serve(self, body, fail_after=None):
        original = intake.urllib.request.urlopen
        intake.urllib.request.urlopen = lambda url, timeout=None: FakeResponse(body, fail_after)
        self.addCleanup(setattr, intake.urllib.request, "urlopen", original)

    def downloaded(self):
        return sorted(os.listdir(self.tmp))

    def test_a_download_over_the_cap_is_refused_and_the_partial_file_removed(self):
        self.serve(b"n" * (intake.MAX_PACKAGE_BYTES + intake.DOWNLOAD_CHUNK))
        with self.assertRaises(intake.Refused) as raised:
            intake.resolve_package(self.SPEC, self.tmp)
        self.assertIn(str(intake.MAX_PACKAGE_BYTES), str(raised.exception))
        self.assertEqual(self.downloaded(), [], "the partial download was left on disk")

    def test_a_download_that_fails_partway_leaves_nothing_behind(self):
        self.serve(b"n" * (4 * intake.DOWNLOAD_CHUNK), fail_after=intake.DOWNLOAD_CHUNK)
        with self.assertRaises(intake.Usage):
            intake.resolve_package(self.SPEC, self.tmp)
        self.assertEqual(self.downloaded(), [])

    def test_a_download_under_the_cap_is_hashed_as_it_streams(self):
        with open(self.hoyle, "rb") as handle:
            body = handle.read()
        self.serve(body)
        path, digest = intake.resolve_package(self.SPEC, self.tmp)
        self.assertEqual(self.downloaded(), [os.path.basename(path)])
        self.assertEqual(digest, intake.sha256_of_file(self.hoyle))
        self.assertEqual(intake.intake(path, HOYLE_TEXT, log=None).nupkg_sha256, digest)


if __name__ == "__main__":
    unittest.main()
