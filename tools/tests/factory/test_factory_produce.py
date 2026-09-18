#!/usr/bin/env python3
"""`factory produce` (#3, M2) scaffolds an engine once, regenerates its `*.g.cs` every time, and
generates exactly what the correspondence table says.

What is asserted here without a .NET SDK: two runs give byte-identical trees; a second run into
the same directory leaves engine-owned files (the overlay above all) alone and rewrites the
generated ones (managed files: test_factory_ownership.py); a re-run with a newer or older version of the map leaves nothing naming the
version it replaced, pins included (#66); every one of Part 107's 47 entries is emitted with its citation verbatim and
the correspondence row the table's first match gives it; the overlay moves an entry between
rows; an overlay that breaks 0015's merge rules is refused; and a `backlog/` an earlier produce
committed is removed, because the pattern is retired (#243). And produce is transactional (#67):
a refusal after generation and after the retired files were removed leaves an existing engine
byte-identical (modes included) and a fresh `--out` uncreated; a failure injected into the commit (os.replace patched
in-process) is rolled back; a commit whose rollback also failed is rolled back by the next run,
and a copy of that half-committed engine is refused, naming the journal.

What is not: that the produced solution builds and its generated tests pass. That needs the
SDK the kernel pins and nuget.org, so it is not a unit test here, and produce runs with
`--no-verify`: scripts/validate-engine.sh produces the backgammon engine from scratch and runs
`factory verify` on it (restore, build `-warnaserror`, test, the engine's gate), and CI's `engine`
job runs that script with the pinned SDK installed. verify's own logic is test_factory_verify.py's.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")

_spec = importlib.util.spec_from_file_location("factory_main_produce", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
generate = factory.generate
import csharp  # noqa: E402
import entries as entries_step  # noqa: E402
import correspondence  # noqa: E402
import registry as registry_step  # noqa: E402
import semantics  # noqa: E402
overlay = factory.generate.overlay_step

PART107 = os.path.join(REPO, "examples", "faa-part-107")
PART107_XML = os.path.join(PART107, "part107.xml")
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
NAME = "FaaPart107"
GENERATED = (
    f"src/{NAME}/Generated/MapEntries.g.cs",
    f"src/{NAME}/Generated/Registry.g.cs",
    f"tests/{NAME}.Tests/Generated/CorrespondenceTests.g.cs",
    f"src/{NAME}/Generated/Contracts.g.cs",
    f"src/{NAME}/Generated/Requests.g.cs",
    f"src/{NAME}/Generated/Provenance.g.cs",
    f"tests/{NAME}.Tests/Generated/ProvenanceTests.g.cs",
)
PACKAGES_PROPS = "RulesFactory.Packages.g.props"
MAP_ID = "RulesFactory.Maps.FaaPart107"


def write_overlay(engine, items):
    """Replace the engine's overlay/ with one file per entry of `items` (#247)."""
    directory = os.path.join(engine, "overlay")
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            os.remove(os.path.join(directory, name))
    os.makedirs(directory, exist_ok=True)
    for entry_id, item in items.items():
        with open(os.path.join(directory, f"{entry_id}.json"), "w", encoding="utf-8") as handle:
            json.dump(item, handle, indent=2)
            handle.write("\n")


def pack(map_dir, out):
    subprocess.run([sys.executable, PACK, map_dir, "--out", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
    return os.path.join(out, name)


def pack_version(map_dir, version, root):
    """`map_dir` packed as `version`: a copy under `root` whose map-package.json says so."""
    copy = os.path.join(root, f"v{version}", os.path.basename(map_dir))
    shutil.copytree(map_dir, copy)
    settings_path = os.path.join(copy, "map-package.json")
    with open(settings_path, encoding="utf-8") as handle:
        settings = json.load(handle)
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(dict(settings, version=version), handle)
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

    def produce(self, out, package=None, corpus=PART107_XML, name=NAME, report=None):
        # --allow-dirty: this checkout's own state is not under test here (test_factory_provenance.py
        # runs a committed copy of the factory to test the refusal).
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["produce", "--package", package or self.part107, "--corpus", corpus,
                                 "--name", name, "--out", out, "--allow-dirty",
                                 # nor is building it: no SDK assumed (test_factory_verify.py)
                                 "--no-verify", *(["--produce-report", report] if report else [])])
        return code, buffer.getvalue()

    def produced(self, out=None, **kwargs):
        out = out or os.path.join(self.tmp, "engine")
        code, output = self.produce(out, **kwargs)
        # `--no-verify` ends NOT VERIFIED (3), never 0: the engine was written but never built
        # or tested (tools/factory/__main__.py).
        self.assertEqual(code, factory.NOT_VERIFIED, output)
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
                         "corpus/part107.xml", "provenance.json", PACKAGES_PROPS, *GENERATED):
            self.assertIn(expected, files)
        generated_code = {f for f in files if f.endswith(".cs")}
        self.assertEqual(generated_code, set(GENERATED), "every C# file the factory writes is *.g.cs")

    def test_pins(self):
        out = self.produced()
        self.assertEqual(json.loads(self.read(out, "global.json"))["sdk"], {"version": "10.0.112", "rollForward": "disable"})
        packages = self.read(out, PACKAGES_PROPS)
        self.assertIn('<PackageVersion Include="RulesKernel" Version="0.3.0" />', packages)
        self.assertIn(f'<PackageVersion Include="{MAP_ID}" Version="[4.0.0]" />', packages)
        self.assertIn(f"<ItemGroup Condition=\"'$(MSBuildProjectName)' == '{NAME}'\">", packages)
        self.assertIn(f'<PackageReference Include="{MAP_ID}" PrivateAssets="all" />', packages)
        central = self.read(out, "Directory.Packages.props")
        self.assertIn(f'<Import Project="$(MSBuildThisFileDirectory){PACKAGES_PROPS}" />', central)
        for scaffold_file in ("Directory.Packages.props", "Directory.Build.props", f"{NAME}.slnx",
                              f"src/{NAME}/{NAME}.csproj", f"tests/{NAME}.Tests/{NAME}.Tests.csproj"):
            text = self.read(out, scaffold_file)
            self.assertNotIn(MAP_ID, text, f"{scaffold_file} is write-once and must not name the map package")
            self.assertNotIn("0.3.0", text, f"{scaffold_file} is write-once and must not pin the kernel")
        build = self.read(out, "Directory.Build.props")
        self.assertIn("<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>", build)
        self.assertIn("<RestoreLockedMode", build)
        # #247: the overlay is a directory of one file per implemented entry, scaffolded by
        # nothing. A fresh engine has implemented nothing, so it has no overlay file at all.
        self.assertFalse(os.path.exists(os.path.join(out, "corpus-map.overlay.json")))
        self.assertFalse(os.path.isdir(os.path.join(out, "overlay")))
        with open(PART107_XML, "rb") as handle, open(os.path.join(out, "corpus", "part107.xml"), "rb") as copy:
            self.assertEqual(handle.read(), copy.read())

    def test_hand_written_and_scaffold_files_survive_a_rerun(self):
        out = self.produced()
        hand = os.path.join(out, "src", NAME, "Rules", "Speed.cs")
        os.makedirs(os.path.dirname(hand))
        with open(hand, "w", encoding="utf-8") as handle:
            handle.write("// mine\n")
        with open(os.path.join(out, "Directory.Packages.props"), "a", encoding="utf-8") as handle:
            handle.write("<!-- edited -->\n")
        generated_file = os.path.join(out, *GENERATED[0].split("/"))
        with open(generated_file, "w", encoding="utf-8") as handle:
            handle.write("// hand edit to a generated file\n")
        self.produced(out)
        self.assertEqual(self.read(out, f"src/{NAME}/Rules/Speed.cs"), "// mine\n")
        self.assertTrue(self.read(out, "Directory.Packages.props").endswith("<!-- edited -->\n"))
        self.assertIn("public static class MapEntries", self.read(out, GENERATED[0]))


class TestMapVersionChange(ProduceCase):
    """#66: re-producing with another version of the map moves every pin with the code."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Both above the map's real version, and not 6.0.0: the emitted validate.yml pins
        # actions/setup-dotnet "# v6.0.0", which assert_names_only would read as a stale pin.
        cls.v1 = pack_version(PART107, "5.0.0", os.path.join(cls.shared, "versions"))
        cls.v2 = pack_version(PART107, "7.0.0", os.path.join(cls.shared, "versions"))

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
        self.assert_names_only(out, "5.0.0", "7.0.0")
        self.produced(out, package=self.v2)
        self.assert_names_only(out, "7.0.0", "5.0.0")
        self.assert_same_as_fresh(out, self.v2)

    def test_downgrade(self):
        out = self.produced(package=self.v2)
        self.produced(out, package=self.v1)
        self.assert_names_only(out, "5.0.0", "7.0.0")
        self.assert_same_as_fresh(out, self.v1)

    def test_the_produce_report_says_what_moved_and_what_it_wrote(self):
        """#193: a factory update's pull request is filled in from the run, not from memory."""
        out = self.produced(package=self.v1)
        report_path = os.path.join(self.tmp, "report.json")
        self.produced(out, package=self.v2, report=report_path)
        with open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual(report["map"], {"packageId": MAP_ID, "from": "5.0.0", "to": "7.0.0"})
        self.assertEqual(report["kernel"]["from"], report["kernel"]["to"], "only the map moved")
        self.assertEqual(report["moved"], ["the map, 5.0.0 to 7.0.0"])
        # The four fields the emitted pull request template asks for, under its own labels, so
        # nothing is retyped from a terminal into a pull request body.
        self.assertEqual(report["declaration"]["map package and version"], f"{MAP_ID} 7.0.0")
        self.assertEqual(report["declaration"]["what moved"], "the map, 5.0.0 to 7.0.0")
        self.assertEqual(report["declaration"]["factory version"], report["factory"]["version"])
        # Every path this run put in place, classified by the table produce wrote them by: a map
        # bump rewrites the pins and the generated code, and nothing engine-owned.
        by_path = {item["path"]: item for item in report["paths"]}
        self.assertEqual(by_path[PACKAGES_PROPS], {"path": PACKAGES_PROPS, "change": "changed", "class": "generated"})
        self.assertEqual({item["class"] for item in report["paths"]}, {"generated"})
        self.assertTrue(any(line.startswith("map.version:") for line in report["provenanceDiff"]),
                        report["provenanceDiff"])

    def test_the_report_calls_a_retired_path_retired_only_where_it_deleted_one(self):
        """`retired` is a class of change, not of file (#243).

        A run deletes what it recorded under a retired pattern; nothing writes one. So a path that
        *appears* or *changes* under the pattern is somebody's own, and reporting it `retired` would
        say the opposite of what the section is for -- and is what `tools/pr-policy.py` reads to
        decide whether a produce claim covers it.
        """
        out = self.produced(package=self.v1)
        committed_backlog(out, ("999-stale.md",))
        report_path = os.path.join(self.tmp, "report.json")
        self.produced(out, package=self.v2, report=report_path)
        with open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
        by_path = {item["path"]: item for item in report["paths"]}
        self.assertEqual(by_path["backlog/999-stale.md"],
                         {"path": "backlog/999-stale.md", "change": "removed", "class": "retired"})
        self.assertEqual({item["change"] for item in report["paths"] if item["class"] == "retired"}, {"removed"})
        for change in ("added", "changed"):
            classified = factory.classified_paths(NAME, *[["backlog/notes.md"] if how == change else []
                                                         for how in ("added", "changed", "removed")])
            self.assertEqual(classified, [{"path": "backlog/notes.md", "change": change, "class": None}],
                             "a file appearing or changing under a retired pattern is nobody's but the engine's")

    def test_the_report_of_a_run_that_moved_nothing_says_so(self):
        out = self.produced(package=self.v1)
        report_path = os.path.join(self.tmp, "report.json")
        self.produced(out, package=self.v1, report=report_path)
        with open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual(report["moved"], [])
        self.assertIn("reproduced the engine from the inputs it already had", report["declaration"]["what moved"])
        self.assertEqual(report["paths"], [], "a re-produce from the same inputs writes nothing new")

    def test_a_report_path_in_no_directory_is_refused_before_anything_is_produced(self):
        out = os.path.join(self.tmp, "engine")
        code, output = self.produce(out, report=os.path.join(self.tmp, "nowhere", "report.json"))
        self.assertEqual(code, 2, output)
        self.assertIn("is not a directory", output)
        self.assertFalse(os.path.exists(out), "nothing was produced")

    def test_engine_owned_scaffold_edits_survive_a_version_change(self):
        out = self.produced(package=self.v1)
        with open(os.path.join(out, "Directory.Packages.props"), "a", encoding="utf-8") as handle:
            handle.write("<!-- edited -->\n")
        self.produced(out, package=self.v2)
        self.assertTrue(self.read(out, "Directory.Packages.props").endswith("<!-- edited -->\n"))
        self.assert_names_only(out, "7.0.0", "5.0.0")


class TestGeneration(ProduceCase):
    def test_every_entry_with_its_citation_verbatim(self):
        out = self.produced()
        entries = self.read(out, GENERATED[0])
        registry = self.read(out, GENERATED[1])
        tests = self.read(out, GENERATED[2])
        self.assertEqual(len(self.map["entries"]), 47)
        for entry in self.map["entries"]:
            literal = csharp.cs_string(entry["locator"]["citation"])
            self.assertIn(f'new SourceLocator("cfr-14-107", {literal})', entries, entry["id"])
            self.assertIn(f'new("{entry["id"]}", EntryStatus.', registry)
            self.assertIn(f'        "{entry["id"]}",\n', tests)
        self.assertIn('contentHash: "80f6bc4b002df9dcc60a651fec30a2dc3590081cc3e5fd431d9885c69b7ce35e"', entries)
        self.assertIn("asOf: new DateOnly(2026, 1, 1)", entries)
        self.assertEqual(registry.count("MapEntries."), 47)

    def test_rows_follow_the_table_first_match(self):
        out = self.produced()
        tests = self.read(out, GENERATED[2])
        declines = dict(re.findall(r'AssertDeclines\("([a-z0-9-]+)", UnresolvedReason\.(\w+),', tests))
        self.assertEqual(len(declines), 47, "every mapped, declined or out-of-scope entry declines")
        self.assertEqual(declines["subpart-d-categories"], "OutsideCurrentScope")
        self.assertEqual(declines["knowledge-recency"], "OutsideCurrentScope")
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
        write_overlay(out, {"speed-within-limit": implemented, "reasonable-protection": implemented})
        self.produced(out)
        tests = self.read(out, GENERATED[2])
        registry = self.read(out, GENERATED[1])
        # speed-limit, a value it depends on, is still mapped: row 5.
        self.assertIn('new("speed-within-limit", EntryStatus.Implemented, CorrespondenceRow.ValueDependencyUnimplemented,', registry)
        self.assertIn("speed_within_limit__is_implemented_so_a_hand_written_handler_answers_it", tests)
        self.assertIn('new("reasonable-protection", EntryStatus.Implemented, CorrespondenceRow.Assertion,', registry)
        self.assertIn("reasonable_protection__is_implemented_and_answers_or_demands_the_assertion", tests)

        # #76: the handler a correspondence test demands becomes one the build demands. Row 5 has
        # a default, but an implemented entry off row 8 still needs a handler, so it is required;
        # an implemented assertion keeps its optional hook, because row 8's default can answer.
        contracts = self.read(out, GENERATED[3])
        self.assertIn("    internal static partial Resolution<object> SpeedWithinLimit("
                      "global::FaaPart107.Requests.SpeedWithinLimitRequest request);\n", contracts)
        # #93: the handler receives the caller's typed request, and a request built from the
        # assertions only on the dictionary dispatch.
        self.assertIn("                resolution = SpeedWithinLimit(request as global::FaaPart107.Requests.SpeedWithinLimitRequest "
                      "?? new(assertions));\n", contracts)
        self.assertIn("                ReasonableProtection(request as global::FaaPart107.Requests.ReasonableProtectionRequest "
                      "?? new(assertions), ref resolution);\n", contracts)
        self.assertIn('        "speed-within-limit" => true,\n', contracts)
        self.assertIn("    static partial void ReasonableProtection(global::FaaPart107.Requests.ReasonableProtectionRequest request, "
                      "ref Resolution<object>? resolution);\n", contracts)
        self.assertEqual(contracts.count("internal static partial Resolution<"), 1)

    def test_every_entry_has_a_typed_contract(self):
        """#76: a request type, a typed entry point and a handler declaration per entry, all `object`
        where the map declares no type, which today is everywhere."""
        out = self.produced()
        contracts = self.read(out, GENERATED[3])
        requests = self.read(out, GENERATED[4])
        tests = self.read(out, GENERATED[2])
        self.assertIn("public sealed class RuleEntry<TInput, TOutput>\n    where TInput : IEntryRequest\n", contracts)
        self.assertIn("internal static partial class Handlers\n", contracts)
        self.assertIn(f"namespace {NAME}.Requests;\n", requests)
        for entry in self.map["entries"]:
            member = semantics.pascal(entry["id"])
            request = f"global::{NAME}.Requests.{member}Request"
            with self.subTest(entry["id"]):
                self.assertIn(f"    public static RuleEntry<{request}, object> {member} {{ get; }} =\n"
                              f'        new("{entry["id"]}", request => Registry.Resolve(request));\n',
                              contracts)
                # Nothing is implemented in the package map, so every handler is an optional hook.
                self.assertIn(f"    static partial void {member}({request} request, ref Resolution<object>? resolution);\n", contracts)
                self.assertIn(f'        "{entry["id"]}" => Hooked("{member}", typeof({request})),\n', contracts)
                # #93: partial, so an engine declares the entry's inputs, with a parameterless
                # constructor for an object initializer.
                self.assertIn(f"public sealed partial class {member}Request : IEntryRequest\n", requests)
                self.assertIn(f"    public {member}Request()\n        : this(RuleRequest.Empty)\n", requests)
                self.assertIn(f"    public {member}Request(RuleRequest assertions)\n", requests)
                self.assertIn(f'    public string EntryId => "{entry["id"]}";\n', requests)
                self.assertIn(f"            EntryPoints.{member}.Id,\n", tests)
                asserting = f"    public static {member}Request Asserting(object value) => " \
                            f'new(RuleRequest.Empty.Assert("{entry["id"]}", value));\n'
                if entry["kind"] == "assertion":
                    self.assertIn(asserting, requests)
                else:
                    self.assertNotIn(asserting, requests)
        self.assertNotIn("internal static partial Resolution<", contracts)
        self.assertNotIn("public sealed class", requests)
        # #93: the typed entry points dispatch the request object; the dictionary dispatch stays.
        registry = self.read(out, GENERATED[1])
        self.assertIn("    public static Resolution<object> Resolve(IEntryRequest request)\n", registry)
        self.assertIn("    public static Resolution<object> Resolve(string entryId, RuleRequest request)\n", registry)
        self.assertIn("    internal static Resolution<object>? Dispatch(string entryId, RuleRequest assertions, IEntryRequest? request)\n",
                      contracts)
        # Every decline is proved through the typed entry point as well as the dictionary.
        self.assertEqual(tests.count("AssertDeclines(\""), len(self.map["entries"]))
        self.assertEqual(len(re.findall(r'AssertDeclines\("[a-z0-9-]+", UnresolvedReason\.\w+, EntryPoints\.\w+\.Resolve\(', tests)),
                         len(self.map["entries"]))

    def test_the_contract_types_what_the_map_declares_and_object_elsewhere(self):
        intake = type("Intake", (), {"package_id": "RulesFactory.Maps.Test", "version": "1.0.0"})()
        entries = [
            {"id": "a-value", "name": "v", "kind": "value", "scope": "in", "status": "implemented",
             "locator": {"sourceId": "corpus", "citation": "p. 1"}},
            {"id": "an-assertion", "name": "a", "kind": "assertion", "scope": "in", "status": "implemented",
             "locator": {"sourceId": "corpus", "citation": "p. 2"}},
            {"id": "entry-points", "name": "e", "kind": "operation", "scope": "in", "status": "mapped",
             "locator": {"sourceId": "corpus", "citation": "p. 3"}},
        ]
        model = semantics.Model(intake, {"corpus": "corpus", "entries": entries,
                                        "baseline": {"contentHash": "sha256:0", "hashDerivation": "raw", "asOf": None}}, "Test")
        value, assertion, reserved = (semantics.contract(model, item) for item in model.entries)
        self.assertEqual((value["output"], value["asserts"], value["required"]), ("object", False, True))
        self.assertEqual((assertion["output"], assertion["asserts"], assertion["required"]), ("object", True, False))
        # A member may not take the name of a class the generated code declares around it.
        self.assertEqual(reserved["request_cs"], "global::Test.Requests.EntryPointsEntryRequest")
        self.assertFalse(reserved["required"])

    def test_a_derived_entry_cites_every_premise(self):
        """#73: hit-pays-single-stake rests on two passages, and the runtime names both."""
        out = self.produced(package=self.hoyle, corpus=os.path.join(HOYLE, "hoyle.txt"), name="HoyleBackgammon")
        entries = self.read(out, "src/HoyleBackgammon/Generated/MapEntries.g.cs")
        registry = self.read(out, "src/HoyleBackgammon/Generated/Registry.g.cs")
        tests = self.read(out, "tests/HoyleBackgammon.Tests/Generated/CorrespondenceTests.g.cs")
        self.assertIn("public static DerivedMapEntry HitPaysSingleStake", entries)
        both = ("MapEntries.StakeMultiplier.Locator, MapEntries.AgreedBackgammonMultiple.Locator")
        self.assertIn(f'new("hit-pays-single-stake", EntryStatus.Mapped, CorrespondenceRow.NotBuilt, '
                      f'[{both}]),', registry)
        self.assertNotIn("MapEntries.HitPaysSingleStake.Locator", registry)
        self.assertIn('new("inner-table-handedness", EntryStatus.Declined, CorrespondenceRow.BeyondAdapter,', registry)
        self.assertIn("hit_pays_single_stake__cites_every_premise", tests)
        decline = re.search(r'AssertDeclines\("hit-pays-single-stake", UnresolvedReason\.UnsupportedRule, (.*)\);', tests)
        self.assertIsNotNone(decline)
        self.assertEqual(decline.group(1).count("new SourceLocator("), 2)


class TestDerivedProvenance(unittest.TestCase):
    """#73: a derived entry's citation is every leaf locator, found recursively, in a fixed order.

    Built on a synthetic map, because neither example map has a derived entry whose source is
    itself derived, which is the case the recursion exists for.
    """

    @staticmethod
    def located(entry_id, citation):
        return {"id": entry_id, "name": entry_id, "kind": "value", "scope": "in", "status": "mapped",
                "locator": {"sourceId": "corpus", "citation": citation}}

    @staticmethod
    def derived(entry_id, *sources):
        return {"id": entry_id, "name": entry_id, "kind": "value", "scope": "in", "status": "mapped",
                "derivedFrom": list(sources)}

    def model(self, entries):
        intake = type("Intake", (), {"package_id": "RulesFactory.Maps.Test", "version": "1.0.0"})()
        merged = {"corpus": "corpus", "entries": entries,
                  "baseline": {"contentHash": "sha256:0", "hashDerivation": "raw", "asOf": None}}
        return semantics.Model(intake, merged, "Test")

    def citations(self, model, entry_id):
        return [model.locator_of(m)["citation"] for m in model.by_id[entry_id]["locators"]]

    def test_two_sources_one_derived_report_every_leaf_depth_first(self):
        # `top` derives from `middle` (itself derived from b and c) and from `a`; `c` is reached
        # twice and keeps its first place. The derived entry comes first in the map on purpose.
        model = self.model([
            self.derived("top", "middle", "a", "c"),
            self.located("a", "p. 1"),
            self.derived("middle", "b", "c"),
            self.located("b", "p. 2"),
            self.located("c", "p. 3"),
        ])
        self.assertEqual(self.citations(model, "top"), ["p. 2", "p. 3", "p. 1"])
        self.assertEqual(self.citations(model, "middle"), ["p. 2", "p. 3"])

        entries = entries_step.map_entries_cs(model)
        top = entries[entries.index("DerivedMapEntry Top"):]
        top = top[:top.index(");\n") + 3]
        self.assertIn('["middle", "a", "c"]', top)
        self.assertEqual(re.findall(r'new SourceLocator\("corpus", "([^"]+)"\)', top), ["p. 2", "p. 3", "p. 1"])

        registry = registry_step.registry_cs(model)
        self.assertIn('new("top", EntryStatus.Mapped, CorrespondenceRow.NotBuilt, '
                      '[MapEntries.B.Locator, MapEntries.C.Locator, MapEntries.A.Locator]),', registry)

        tests = correspondence.tests_cs(model)
        self.assertIn("public void top__cites_every_premise()", tests)
        self.assertIn('AssertDeclines("top", UnresolvedReason.UnsupportedRule, EntryPoints.Top.Resolve(global::Test.Requests.TopRequest.Empty), '
                      'new SourceLocator("corpus", "p. 2"), '
                      'new SourceLocator("corpus", "p. 3"), new SourceLocator("corpus", "p. 1"));', tests)

    def test_a_located_entry_cites_itself_alone(self):
        model = self.model([self.located("a", "p. 1")])
        self.assertEqual(model.by_id["a"]["locators"], ["A"])
        self.assertIn('new("a", EntryStatus.Mapped, CorrespondenceRow.NotBuilt, [MapEntries.A.Locator]),',
                      registry_step.registry_cs(model))
        tests = correspondence.tests_cs(model)
        self.assertIn('AssertDeclines("a", UnresolvedReason.UnsupportedRule, EntryPoints.A.Resolve(global::Test.Requests.ARequest.Empty), '
                      'new SourceLocator("corpus", "p. 1"));', tests)
        self.assertNotIn("cites_every_premise", tests)

    def test_an_assertion_carries_who_asserts_it_and_nothing_else_does(self):
        """0025: assertedBy is exposed on the generated MapEntry and RegisteredEntry, additively."""
        assertion = dict(self.located("ties", "p. 13"), kind="assertion", assertedBy=["GM", "players"])
        model = self.model([assertion, self.located("a", "p. 1")])
        entries = entries_step.map_entries_cs(model)
        self.assertIn("public sealed record MapEntry(string Id, string Name, SourceLocator Locator)\n", entries)
        self.assertIn("public ImmutableArray<string> AssertedBy { get; init; } = [];", entries)
        self.assertIn('new SourceLocator("corpus", "p. 13")) { AssertedBy = ["GM", "players"] };', entries)
        self.assertIn('new SourceLocator("corpus", "p. 1"));', entries)
        registry = registry_step.registry_cs(model)
        self.assertIn("public sealed record RegisteredEntry(string Id, EntryStatus Status, CorrespondenceRow Row, "
                      "ImmutableArray<SourceLocator> Locators)\n", registry)
        self.assertIn("public ImmutableArray<string> AssertedBy { get; init; } = [];", registry)
        self.assertIn('new("ties", EntryStatus.Mapped, CorrespondenceRow.NotBuilt, [MapEntries.Ties.Locator]) '
                      '{ AssertedBy = ["GM", "players"] },', registry)
        self.assertIn('new("a", EntryStatus.Mapped, CorrespondenceRow.NotBuilt, [MapEntries.A.Locator]),', registry)

    def test_a_cycle_is_refused(self):
        with self.assertRaisesRegex(semantics.GenerationError, "through a cycle"):
            self.model([self.derived("x", "y", "a"), self.derived("y", "x", "a"), self.located("a", "p. 1")])

    def test_a_source_the_map_lacks_is_refused_wherever_it_stands(self):
        with self.assertRaisesRegex(semantics.GenerationError, "'missing'"):
            self.model([self.derived("x", "a", "missing"), self.located("a", "p. 1")])


class TestRefuses(ProduceCase):
    def overlay(self, content):
        out = os.path.join(self.tmp, "engine")
        os.makedirs(out, exist_ok=True)
        write_overlay(out, content)
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
            f'    <PackageVersion Include="{MAP_ID}" Version="[4.0.0]" />\n'
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


def committed_backlog(engine, names=("999-stale.md", "README.md")):
    """A `backlog/` as a produce before #243 left one: the files, **and the record that hashed them**.

    Writing the files alone would not be that state. A retirement deletes only what the engine's own
    provenance.json attributes to the factory (ownership.remove_retired), so a fixture that skipped
    the record would be testing the case where nothing is removed.
    """
    directory = os.path.join(engine, "backlog")
    os.makedirs(directory, exist_ok=True)
    record_path = os.path.join(engine, "provenance.json")
    with open(record_path, encoding="utf-8") as handle:
        record = json.load(handle)
    for name in names:
        text = f"# committed by a produce before #243: {name}\n"
        with open(os.path.join(directory, name), "w", encoding="utf-8") as handle:
            handle.write(text)
        record["generated"].append({"path": f"backlog/{name}",
                                    "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
    record["generated"].sort(key=lambda item: item["path"])
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    return [f"backlog/{name}" for name in names]


def snapshot(root):
    """Every directory, and every file with its mode and bytes, under `root`."""
    entries = {}
    for directory, dirs, names in os.walk(root):
        for name in dirs:
            entries[os.path.relpath(os.path.join(directory, name), root) + "/"] = None
        for name in names:
            path = os.path.join(directory, name)
            with open(path, "rb") as handle:
                entries[os.path.relpath(path, root)] = (os.stat(path).st_mode, handle.read())
    return entries


def shared_overlay(engine, document):
    """`corpus-map.overlay.json` as every engine produced before #247 holds it.

    The file alone is not that state: the record hashed it in `buildInputs`, and the engine had no
    `overlay/`. A fixture that skipped the record would still migrate -- the split's witness is the
    content, not the record -- but it would not be the state a real engine is in.
    """
    text = json.dumps(document, indent=2) + "\n"
    path = os.path.join(engine, "corpus-map.overlay.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    record_path = os.path.join(engine, "provenance.json")
    with open(record_path, encoding="utf-8") as handle:
        record = json.load(handle)
    record["buildInputs"].append({"path": "corpus-map.overlay.json",
                                  "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
    record["buildInputs"].sort(key=lambda item: item["path"].encode("utf-8"))
    record["engineOwned"].append({"path": "corpus-map.overlay.json", "adopted": False})
    record["engineOwned"].sort(key=lambda item: item["path"].encode("utf-8"))
    record["provenanceFormat"] = 3
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    return path


class TestTheOverlayIsOneFilePerEntry(ProduceCase):
    """#247: `overlay/<entry id>.json`, so two entry branches never write the same file.

    Part B of #242. The shared `corpus-map.overlay.json` was the last file two entry pull requests
    on one engine were *guaranteed* to collide in, because every implemented entry appended to it.
    """

    BLOCKED = {"status": "blocked"}

    def test_the_merge_reads_the_files_in_map_order_not_directory_order(self):
        """Deterministic whatever the filesystem lists first: the map decides the order.

        Written in the reverse of the map's order, and the merge must still come out in the map's.
        Directory order is not guaranteed by anything -- `os.listdir` is arbitrary, and differs
        between filesystems -- so an overlay read in it would generate different bytes on two
        machines from the same files, which is exactly what provenance is meant to rule out.
        """
        out = self.produced()
        first, second = [entry["id"] for entry in self.map["entries"]][:2]
        self.assertEqual(sorted((first, second)), [second, first],
                         "the fixture only proves anything if the map's order is not the path order")
        write_overlay(out, {second: self.BLOCKED, first: self.BLOCKED})
        self.assertEqual(list(overlay.load(out, self.map)), [first, second],
                         "the map's order, not the path order and not the order they were written in")

    def test_an_overlay_file_that_names_no_entry_is_still_refused(self):
        """0015 rule 1, which is also how an entry renamed upstream is caught (#247's non-scope)."""
        out = self.produced()
        write_overlay(out, {"no-such-entry": self.BLOCKED})
        code, output = self.produce(out)
        self.assertEqual(code, 1, output)
        self.assertIn("overlay/no-such-entry.json names 'no-such-entry', which the package map has no "
                      "entry for", output)

    def test_an_engine_produced_before_the_split_is_migrated_by_the_next_produce(self):
        """The migration, end to end: split, then #246's retirement deletes the file it came from."""
        out = self.produced()
        ids = [entry["id"] for entry in self.map["entries"]][:2]
        shared_overlay(out, {entry_id: self.BLOCKED for entry_id in ids})
        code, output = self.produce(out)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertFalse(os.path.exists(os.path.join(out, "corpus-map.overlay.json")),
                         "the file the split replaced is gone")
        self.assertIn("migrated corpus-map.overlay.json to 2 file(s) under overlay/", output)
        self.assertIn("removed 1 file(s) matching the retired pattern corpus-map.overlay.json", output)
        for entry_id in ids:
            self.assertEqual(json.loads(self.read(out, f"overlay/{entry_id}.json")), self.BLOCKED)
        record = json.loads(self.read(out, "provenance.json"))
        self.assertEqual(record["provenanceFormat"], 4)
        self.assertEqual({item["path"] for item in record["buildInputs"] if item["path"].startswith("overlay/")},
                         {f"overlay/{entry_id}.json" for entry_id in ids})
        self.assertFalse([item for item in record["buildInputs"] + record["engineOwned"]
                          if item["path"] == "corpus-map.overlay.json"])

    def test_an_overlay_the_split_does_not_carry_is_kept_and_named(self):
        """The witness is the content, so a file `overlay/` does not account for is nobody's to delete.

        Here the engine has already migrated -- `overlay/` holds one entry -- and somebody has left a
        `corpus-map.overlay.json` behind saying something else. `split` does not run (the directory is
        not empty), and the witness refuses the deletion because the files beside it do not carry
        what it holds. Deleting it on the strength of the pathname would take somebody's work.
        """
        out = self.produced()
        entry_id = self.map["entries"][0]["id"]
        write_overlay(out, {entry_id: self.BLOCKED})
        shared_overlay(out, {entry_id: {"status": "implemented", "implementedIn": {"ruleset": "x", "version": 1},
                                        "tests": []}})
        code, output = self.produce(out)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertTrue(os.path.isfile(os.path.join(out, "corpus-map.overlay.json")),
                        "an overlay the split does not carry was deleted anyway")
        self.assertIn("kept corpus-map.overlay.json", output)
        self.assertIn("overlay/ does not carry what it holds", output)
        self.assertEqual(json.loads(self.read(out, f"overlay/{entry_id}.json")), self.BLOCKED,
                         "and the migrated files were not rewritten from it either")


class TestTransactional(ProduceCase):
    """#67: a refusal, or a failed commit, leaves --out as it was."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.v1 = pack_version(PART107, "5.0.0", os.path.join(cls.shared, "versions"))
        cls.v2 = pack_version(PART107, "7.0.0", os.path.join(cls.shared, "versions"))

    def existing(self):
        """A v1 engine still holding a committed backlog, as every engine produced before #243 does.

        A v2 run changes, adds and removes files: the removals are the retired `backlog/*.md`
        (ownership.RETIRED), which is the migration, and they go through the same journal and
        rollback as everything else.
        """
        out = self.produced(package=self.v1)
        committed_backlog(out)
        os.makedirs(os.path.join(out, "bin"))
        with open(os.path.join(out, "bin", "build.dll"), "wb") as handle:
            handle.write(b"built")
        return out

    def fail_after_generation(self):
        """A refusal at the last step before provenance, once the run has already written and removed."""
        real = factory.remove_retired

        def remove_then_refuse(name, out):
            real(name, out)
            raise semantics.GenerationError("forced after generation and the retired files were removed")
        return mock.patch.object(factory, "remove_retired", remove_then_refuse)

    def fail_replace_after(self, out, count):
        real, calls = os.replace, []
        root = os.path.realpath(out) + os.sep

        def replace(src, dst, *args, **kwargs):
            if os.path.realpath(dst).startswith(root) and not dst.endswith(factory.transaction.JOURNAL):
                calls.append(dst)
                if len(calls) == count + 1:  # once: rollback's own os.replace calls go through
                    raise OSError("forced failure during commit")
            return real(src, dst, *args, **kwargs)
        return mock.patch.object(os, "replace", replace)

    def assert_no_leftovers(self, parent):
        self.assertEqual([n for n in os.listdir(parent) if ".factory-produce-" in n], [])

    def test_a_refusal_after_generation_leaves_an_existing_engine_byte_identical(self):
        out = self.existing()
        before = snapshot(out)
        with self.fail_after_generation():
            code, output = self.produce(out, package=self.v2)
        self.assertEqual(code, 1, output)
        self.assertIn("forced after generation", output)
        self.assertIn("Nothing was produced.", output)
        self.assertEqual(before, snapshot(out))
        self.assert_no_leftovers(self.tmp)

    def test_a_refusal_leaves_a_fresh_out_uncreated(self):
        out = os.path.join(self.tmp, "missing", "parent", "engine")
        with self.fail_after_generation():
            code, output = self.produce(out)
        self.assertEqual(code, 1, output)
        self.assertEqual(os.listdir(self.tmp), [])

    def test_a_refusal_leaves_an_empty_out_empty(self):
        out = os.path.join(self.tmp, "engine")
        os.makedirs(out)
        with self.fail_after_generation():
            code, output = self.produce(out)
        self.assertEqual(code, 1, output)
        self.assertEqual(os.listdir(out), [])
        self.assert_no_leftovers(self.tmp)

    def test_a_commit_removes_and_leaves_bin_alone(self):
        out = self.existing()
        self.produced(out, package=self.v2)
        self.assertFalse(os.path.exists(os.path.join(out, "backlog")),
                         "the retired backlog/ an earlier produce committed is removed, directory and all")
        self.assertTrue(os.path.isfile(os.path.join(out, "bin", "build.dll")))
        shutil.rmtree(os.path.join(out, "bin"))
        fresh = tree(self.produced(os.path.join(self.tmp, "fresh"), package=self.v2))
        self.assertEqual(fresh, tree(out))
        self.assert_no_leftovers(self.tmp)

    def test_a_file_under_a_retired_pattern_the_record_does_not_own_is_kept_and_named(self):
        """A retired pattern is not a licence to delete by pathname (#243).

        `backlog/notes.md` matches `backlog/*.md` and was never emitted by anything; an item file
        somebody edited after the last produce no longer hashes to what the record says. Neither is
        the factory's to remove, and both are named in the output, because a file under a pattern
        nothing maintains any more is something its owner has to be told about.
        """
        out = self.produced(package=self.v1)
        committed_backlog(out)
        mine = os.path.join(out, "backlog", "notes.md")
        with open(mine, "w", encoding="utf-8") as handle:
            handle.write("# my own notes, never emitted by anything\n")
        edited = os.path.join(out, "backlog", "999-stale.md")
        with open(edited, "a", encoding="utf-8") as handle:
            handle.write("a line I added after the last produce\n")

        code, output = self.produce(out, package=self.v2)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertTrue(os.path.isfile(mine), "a hand-written file under a retired pattern was deleted")
        self.assertTrue(os.path.isfile(edited), "an edited file the record no longer matches was deleted")
        self.assertFalse(os.path.exists(os.path.join(out, "backlog", "README.md")),
                         "the one file the record does attribute to the factory is still removed")
        self.assertIn("kept backlog/notes.md", output)
        self.assertIn("provenance.json does not record the factory as having written it", output)
        self.assertIn("kept backlog/999-stale.md", output)
        self.assertIn("edited after the last produce", output)

    def test_modes_git_does_not_track_are_not_counted_as_changed(self):
        """A clone under umask 002 has 0664 and 0775 where the factory writes 0644 and 0755."""
        out = self.produced(package=self.v1)
        for directory, _, names in os.walk(out):
            for name in names:
                path = os.path.join(directory, name)
                os.chmod(path, os.stat(path).st_mode | 0o020)
        code, output = self.produce(out, package=self.v1)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertIn(f"wrote to {os.path.realpath(out)}: 0 added, 0 changed, 0 removed", output)

    def test_an_executable_bit_that_differs_is_counted_as_changed(self):
        out = self.produced(package=self.v1)
        script = os.path.join(out, "scripts", "validate.sh")
        os.chmod(script, 0o664)
        code, output = self.produce(out, package=self.v1)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertIn(f"wrote to {os.path.realpath(out)}: 0 added, 1 changed, 0 removed", output)
        self.assertEqual(stat.S_IMODE(os.stat(script).st_mode), 0o755)

    def test_a_failure_during_commit_is_rolled_back(self):
        out = self.existing()
        before = snapshot(out)
        with self.fail_replace_after(out, 3):
            code, output = self.produce(out, package=self.v2)
        self.assertEqual(code, 1, output)
        self.assertIn("was rolled back", output)
        self.assertNotIn("Nothing was produced", output)
        self.assertEqual(before, snapshot(out))
        self.assert_no_leftovers(self.tmp)

    def test_a_symlinked_directory_it_would_write_through_is_refused_and_nothing_is_written(self):
        """#184: backlog/ turned into a link (git stores links) must not carry produce's removals outside --out."""
        out = self.existing()
        outside = os.path.join(self.tmp, "outside")
        shutil.move(os.path.join(out, "backlog"), outside)
        os.symlink(outside, os.path.join(out, "backlog"))
        before, before_outside = snapshot(out), snapshot(outside)
        code, output = self.produce(out, package=self.v2)
        self.assertEqual(code, 1, output)
        self.assertIn("through backlog", output)
        self.assertIn("Nothing was produced.", output)
        self.assertEqual(before, snapshot(out))
        self.assertEqual(before_outside, snapshot(outside))
        self.assert_no_leftovers(self.tmp)

    def test_an_interrupted_commit_is_rolled_back_by_the_next_run(self):
        out = self.existing()
        before = snapshot(out)
        with self.fail_replace_after(out, 3), \
                mock.patch.object(factory.transaction, "_rollback", side_effect=OSError("the process died")):
            code, output = self.produce(out, package=self.v2)
        self.assertEqual(code, 1, output)
        self.assertIn("partly written", output)
        journal = os.path.join(out, factory.transaction.JOURNAL)
        self.assertTrue(os.path.isfile(journal), output)
        self.assertNotEqual(before, snapshot(out))

        # A copy of the engine taken mid-commit is refused, naming the journal, and changes nothing.
        copy = os.path.join(self.tmp, "copy")
        shutil.copytree(out, copy)
        code, output = self.produce(copy, package=self.v2)
        self.assertEqual(code, 1, output)
        self.assertIn(factory.transaction.JOURNAL, output)
        self.assertIn("not to this directory", output)

        # The rollback alone restores --out exactly.
        buffer = io.StringIO()
        factory.transaction.recover(out, buffer)
        self.assertIn("rolled back an interrupted commit", buffer.getvalue())
        self.assertEqual(before, snapshot(out))
        self.assertFalse(os.path.exists(journal))

        # And a run that finds the journal rolls back, then produces as usual.
        with self.fail_replace_after(out, 3), \
                mock.patch.object(factory.transaction, "_rollback", side_effect=OSError("the process died")):
            self.produce(out, package=self.v2)
        code, output = self.produce(out, package=self.v2)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertIn("rolled back an interrupted commit", output)
        self.assertFalse(os.path.exists(journal))
        shutil.rmtree(os.path.join(out, "bin"))
        self.assertEqual(tree(self.produced(os.path.join(self.tmp, "fresh"), package=self.v2)), tree(out))
        shutil.rmtree(copy)
        self.assert_no_leftovers(self.tmp)


class TestSaysWhatItDidToGit(ProduceCase):
    """produce writes files and makes no git commit, and its output may not suggest otherwise.

    The message used to read `committed to <engine>: N added, ...` while `git log` was unchanged and
    the engine left dirty, so four runs were believed saved that were not. What is asserted here is
    the git state the output claims: no commit is made, and a run into a git checkout says the
    changes are uncommitted.
    """

    def git(self, out, *args):
        done = subprocess.run(["git", "-C", out, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, check=True)
        return done.stdout

    def engine_repo(self):
        """A produced engine whose files are committed, so a re-produce is the only thing git sees."""
        out = self.produced(package=self.part107)
        self.git(out, "-c", "init.defaultBranch=main", "init", "-q")
        self.git(out, "-c", "user.email=t@example.com", "-c", "user.name=T", "add", "-A")
        self.git(out, "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "-m", "produced")
        self.assertEqual(self.git(out, "status", "--porcelain"), "")
        return out

    def test_a_produce_into_a_git_engine_makes_no_commit_and_does_not_claim_one(self):
        out = self.engine_repo()
        head = self.git(out, "rev-parse", "HEAD")
        code, output = self.produce(out, package=self.hoyle_version())
        self.assertEqual(code, factory.NOT_VERIFIED, output)

        # What actually happened: files changed in the working tree, and git recorded nothing.
        self.assertEqual(self.git(out, "rev-parse", "HEAD"), head, "produce must not create a commit")
        dirty = [line for line in self.git(out, "status", "--porcelain").splitlines() if line.strip()]
        self.assertTrue(dirty, output)

        # So the output may not say the engine was committed, and must say the changes are not.
        self.assertNotIn("committed to", output)
        self.assertIn(f"wrote to {os.path.realpath(out)}: ", output)
        self.assertIn("produce writes files and makes no commit", output)
        self.assertIn(f"{len(dirty)} uncommitted change(s)", output)

    def test_a_produce_that_changes_nothing_says_nothing_about_git(self):
        out = self.engine_repo()
        code, output = self.produce(out, package=self.part107)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertEqual(self.git(out, "status", "--porcelain"), "")
        self.assertNotIn("uncommitted change(s)", output)

    def test_a_produce_outside_a_git_checkout_says_nothing_about_git(self):
        out = self.produced(package=self.part107)
        self.assertFalse(os.path.isdir(os.path.join(out, ".git")))
        code, output = self.produce(out, package=self.part107)
        self.assertEqual(code, factory.NOT_VERIFIED, output)
        self.assertNotIn("uncommitted change(s)", output)

    def hoyle_version(self):
        """The Part 107 map packed at another version: a re-produce that changes files."""
        if not hasattr(self.__class__, "_bumped"):
            self.__class__._bumped = pack_version(PART107, "9.0.0", os.path.join(self.shared, "git-versions"))
        return self._bumped


if __name__ == "__main__":
    unittest.main()
