#!/usr/bin/env python3
"""examples/hoyle-blind-rebuild: the target checker, the brief builder and the rebuild checker, proved
able to refuse.

The committed TARGET.json is checked here only for internal consistency (--self-check): comparing it
with hoyle-backgammon needs a clone, the map package and the .NET SDK, which CI does not have, so that
run is documented in the example's README. Every comparison is instead exercised against synthetic
repositories built here: an engine shaped like hoyle-backgammon, a factory with a tag, a map package,
and a fake dotnet that writes TRX files. A TARGET derived from the fixture passes, and each pin,
changed on its own, is refused; a brief assembled from the fixture holds none of its test names, test
literals or copied test text, and each kind of leak planted in it is found.

Run: python3 -m pytest tools/tests/test_hoyle_blind_rebuild.py
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXAMPLE = ROOT / "examples" / "hoyle-blind-rebuild"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_target = load("hoyle_check_target", EXAMPLE / "check-target.py")
build_brief = load("hoyle_build_brief", EXAMPLE / "build-brief.py")
check_rebuild = load("hoyle_check_rebuild", EXAMPLE / "check-rebuild.py")


def run(module, *argv, env=None):
    out = io.StringIO()
    old = dict(os.environ)
    try:
        if env:
            os.environ.update(env)
        with redirect_stdout(out), redirect_stderr(out):
            code = module.main([str(a) for a in argv])
    finally:
        os.environ.clear()
        os.environ.update(old)
    return code, out.getvalue()


def sha(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


SECRET_SEED = "31415926"
SECRET_HASH = "0badc0ffee0ddf00d5eed5eed5eed5eed5eed5eed5eed5eed5eed5eed5eed5e"

HAND_TESTS = textwrap.dedent(f"""\
    using Xunit;

    namespace HoyleBackgammon.Tests;

    public class SecretBoardTests
    {{
        private const ulong Hidden = {SECRET_SEED}UL;

        [Fact]
        public void A_well_hidden_test_name_nobody_should_see()
        {{
            // the frobnicator must twiddle every widget before the gadget sings loudly
            Assert.Equal("{SECRET_HASH}", Engine.Hash());
        }}

        [Theory]
        // a comment between the attributes
        [InlineData(1)]
        [InlineData(2)]
        public void A_theory_with_two_cases(int value) => Assert.True(value > 0);
    }}
    """)

IDENTITY_TESTS = textwrap.dedent("""\
    using Xunit;

    namespace HoyleBackgammon.Tests;

    public class IdentityTests
    {
        [Fact]
        public void Pins()
        {
            Assert.Equal("hoyle-1909-backgammon", Game.Identity.Ruleset.Id);
            Assert.Equal(6, Game.Identity.Ruleset.Version);
            Assert.Equal(4, Game.Identity.ReplaySchema.Version);
            Assert.Equal("pcg_setseq_64_xsh_rr_32", Game.Identity.RandomAlgorithm!.Value.Name);
        }
    }
    """)

REPLAY_TESTS = textwrap.dedent("""\
    using Xunit;

    namespace HoyleBackgammon.Tests;

    public class SeededGameReplayTests
    {
        private const ulong Seed = 20260914UL;

        private const string RecordedReplaySha256 = "24af54b1bd433e2ba9bb12f2a9e3ecc5bf660290a9d415e4eb9087dda24ba274";

        [Fact]
        public void Replays() { }
    }
    """)

GENERATED_TESTS = textwrap.dedent("""\
    namespace HoyleBackgammon.Tests;

    public sealed class CorrespondenceTests
    {
        [Fact]
        public void Every_map_entry_is_registered_in_map_order() { }
    }
    """)

ENGINE_SOURCE = textwrap.dedent("""\
    namespace HoyleBackgammon;

    /// <summary>The engine. Its documentation talks about the gadget and the widget openly.</summary>
    public static class Engine
    {
        /// <summary>A hash.</summary>
        public static string Hash()
        {
            var widgets = CountTheWidgetsCarefullyBeforeTheGadgetStartsToSingLoudly();
            return widgets.ToString();
        }
    }
    """)

FAKE_DOTNET = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys, uuid
    from pathlib import Path
    spec = json.loads(os.environ["FAKE_TRX_SPEC"])
    args = sys.argv[1:]
    if args[0] != "test":
        sys.exit(0)
    results = Path(args[args.index("--results-directory") + 1])
    results.mkdir(parents=True, exist_ok=True)
    ns = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"
    for n, (key, cases) in enumerate(spec.items()):
        project, framework = key.split("|")
        defs, res = [], []
        for cls, method, outcome in cases:
            tid = str(uuid.uuid4())
            defs.append(f'<UnitTest name="{method}" id="{tid}"><TestMethod codeBase="/x/{project}/bin/Release/{framework}/{project}.dll" className="{cls}" name="{method}"/></UnitTest>')
            res.append(f'<UnitTestResult testId="{tid}" testName="{method}" outcome="{outcome}"/>')
        (results / f"run{n}.trx").write_text(f'<TestRun xmlns="{ns}"><Results>{"".join(res)}</Results><TestDefinitions>{"".join(defs)}</TestDefinitions></TestRun>')
    sys.exit(int(os.environ.get("FAKE_DOTNET_EXIT", "0")))
    """)


def trx_spec(outcome="Passed", drop_one=False):
    cases = [
        ["HoyleBackgammon.Tests.SecretBoardTests", "A_well_hidden_test_name_nobody_should_see", outcome],
        ["HoyleBackgammon.Tests.SecretBoardTests", "A_theory_with_two_cases", "Passed"],
        ["HoyleBackgammon.Tests.SecretBoardTests", "A_theory_with_two_cases", "Passed"],
        ["HoyleBackgammon.Tests.IdentityTests", "Pins", "Passed"],
        ["HoyleBackgammon.Tests.SeededGameReplayTests", "Replays", "Passed"],
        ["HoyleBackgammon.Tests.CorrespondenceTests", "Every_map_entry_is_registered_in_map_order", "Passed"],
    ]
    if drop_one:
        cases = cases[:-1]
    return {f"HoyleBackgammon.Tests|{fw}": cases for fw in ("net8.0", "net10.0")}


class Repos(unittest.TestCase):
    """A hoyle-shaped engine, a factory with a tag, a map package, and a TARGET derived from them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.base = base

        # ---- the factory
        self.factory = base / "factory"
        factory_files = {
            "README.md": "# Factory\n\nIt produces engines.\n",
            ".gitignore": "__pycache__/\n",
            "docs/method.md": "# Method\n\nA general paragraph about mapping.\n\n"
                              "The SecretBoardTests class once pinned this.\n\n- one item\n- A_well_hidden_test_name_nobody_should_see was here\n",
            "tools/factory/__main__.py": "print('factory')\n",
            "tools/factory/generate.py": "GENERATED = 'Every_map_entry_is_registered_in_map_order'\n",
            "tools/check-map.py": "print('check')\n",
            "examples/hoyle-backgammon/hoyle.txt": "BACKGAMMON.\nThe game is played by two persons.\n",
        }
        self.write_repo(self.factory, factory_files)
        self.factory_commit = self.commit_all(self.factory)
        self.git(self.factory, "tag", "factory/v0.7.0")
        digest = check_target.recipes_digest(self.factory, self.factory_commit)
        corpus_hash = sha(factory_files["examples/hoyle-backgammon/hoyle.txt"])

        # ---- the map package
        self.nupkg = base / "rulesfactory.maps.hoylebackgammon.6.0.0.nupkg"
        with zipfile.ZipFile(self.nupkg, "w") as package:
            package.writestr("map/corpus-map.json", json.dumps(
                {"entries": [{"id": "e1", "note": "observable in SecretBoardTests only"}]}))
            package.writestr("map/corpus-manifest.json", "{}")
        nupkg_sha = sha(self.nupkg.read_bytes())

        # ---- the engine
        self.engine = base / "engine"
        generated = {
            "src/HoyleBackgammon/Generated/Registry.g.cs": "// generated registry\n",
            "tests/HoyleBackgammon.Tests/Generated/CorrespondenceTests.g.cs": GENERATED_TESTS,
        }
        managed = {"global.json": '{"sdk":{"version":"10.0.112","rollForward":"disable"}}\n'}
        ruling = {"id": "game-value/1", "entry": "game-value", "span": "The three named results do not cover every finish.",
                  "answer": "A hit.", "ruledBy": "Brandon", "ruledOn": "2026-09-15",
                  "record": "docs/decisions/0001-rulings.md"}
        provenance = {
            "factory": {"version": "0.7.0", "commit": self.factory_commit, "dirty": False},
            "map": {"packageId": "RulesFactory.Maps.HoyleBackgammon", "version": "6.0.0", "nupkgSha256": nupkg_sha},
            "corpus": {"sourceId": "hoyle-1909", "contentHash": corpus_hash,
                       "hashDerivation": "gutenberg-plain-text-including-boilerplate", "asOf": None, "recomputed": True},
            "kernel": {"packageId": "RulesKernel", "version": "0.3.0"},
            "packs": [],
            "recipes": {"digest": digest},
            "generated": [{"path": p, "sha256": sha(t)} for p, t in sorted(generated.items())],
            "managed": [{"path": p, "recipeVersion": 1, "sha256": sha(t)} for p, t in sorted(managed.items())],
            "randomness": "seeded",
            "rulings": [{**ruling, "recordSha256": "0" * 64}],
        }
        overlay = {
            "game-value": {"status": "implemented", "implementedIn": {"ruleset": "hoyle-1909-backgammon", "version": 6},
                           "tests": [{"test": "SecretBoardTests.A_well_hidden_test_name_nobody_should_see",
                                      "mutation": "the zorblax returned seventeen instead of the eleven it should have"}],
                           "rulings": [{**{k: ruling[k] for k in ("id", "span", "answer", "ruledBy", "ruledOn", "record")},
                                        "tests": ["SecretBoardTests.A_well_hidden_test_name_nobody_should_see"]}],
                           "declines": []},
            "men-count": {"status": "mapped"},
        }
        self.engine_files = {
            **generated, **managed,
            "provenance.json": json.dumps(provenance, indent=2),
            "corpus-map.overlay.json": json.dumps(overlay, indent=2),
            "RulesFactory.Packages.g.props": textwrap.dedent("""\
                <Project><ItemGroup>
                <PackageVersion Include="RulesKernel" Version="0.3.0" />
                <PackageVersion Include="RulesKernel.Randomness" Version="0.3.0" />
                <PackageVersion Include="RulesFactory.Maps.HoyleBackgammon" Version="[6.0.0]" />
                </ItemGroup></Project>
                """),
            "HoyleBackgammon.slnx": "<Solution />\n",
            "Directory.Packages.props": "<Project />\n",
            "src/HoyleBackgammon/HoyleBackgammon.csproj": "<Project><!-- builds --></Project>\n",
            "src/Tabletop.Dice/Tabletop.Dice.csproj": "<Project />\n",
            "src/HoyleBackgammon/Engine.cs": ENGINE_SOURCE,
            "tests/HoyleBackgammon.Tests/HoyleBackgammon.Tests.csproj": "<Project />\n",
            "tests/HoyleBackgammon.Tests/SecretBoardTests.cs": HAND_TESTS,
            "tests/HoyleBackgammon.Tests/IdentityTests.cs": IDENTITY_TESTS,
            "tests/HoyleBackgammon.Tests/EntryPointTests.cs": REPLAY_TESTS,
            "docs/decisions/0001-rulings.md": "# 0001\n\nThe owner ruled.\n\n"
                                              f"The replay used seed {SECRET_SEED} for SecretBoardTests.\n",
        }
        self.write_repo(self.engine, self.engine_files)
        self.engine_commit = self.commit_all(self.engine)

        self.dotnet = base / "fake-dotnet"
        self.dotnet.write_text(FAKE_DOTNET)
        self.dotnet.chmod(self.dotnet.stat().st_mode | stat.S_IEXEC)

        self.target_path = base / "TARGET.json"
        self.target = self.make_target()
        self.save(self.target)

    def tearDown(self):
        self.tmp.cleanup()

    # -- helpers
    def write_repo(self, repo, files):
        for path, text in files.items():
            full = repo / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(text)
        self.git(repo, "init", "-q")

    def git(self, repo, *args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    def commit_all(self, repo):
        self.git(repo, "add", "-A")
        self.git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "fixture")
        return self.git(repo, "rev-parse", "HEAD")

    def save(self, target):
        self.target_path.write_text(json.dumps(target, indent=2))

    def make_target(self):
        seed = {"engine": {"repository": "brandonifco/hoyle-backgammon", "commit": self.engine_commit},
                "brief": {"verbatim": [{"path": p} for p in ("HoyleBackgammon.slnx", "Directory.Packages.props",
                                                             "src/HoyleBackgammon/HoyleBackgammon.csproj",
                                                             "src/Tabletop.Dice/Tabletop.Dice.csproj")]}}
        derived = check_target.derive(self.engine, seed)
        projects = {name: {"methodCount": p["methodCount"],
                           "casesPerFramework": {"net10.0": 6, "net8.0": 6},
                           "handWritten": p["handWritten"], "generated": p["generated"]}
                    for name, p in derived["tests"]["projects"].items()}
        contract = "# Public API contract\n\n#### public static class Engine\n\n    public static string Hash()\n      /// A hash.\n"
        self.contract = self.base / "api.md"
        self.contract.write_text(contract)
        target = {
            "engine": derived["engine"],
            "tests": {"targetFrameworks": ["net10.0", "net8.0"], "methodCount": derived["tests"]["methodCount"],
                      "caseCount": 12, "handWrittenClasses": derived["tests"]["handWrittenClasses"],
                      "generatedClasses": derived["tests"]["generatedClasses"], "projects": projects},
            "factory": {"tag": "factory/v0.7.0", **derived["factory"]},
            **{k: derived[k] for k in ("map", "kernel", "corpus", "randomness", "packs", "identity", "replay",
                                        "packagePins", "generatedFiles", "managedFiles", "ownerRulings", "overlay")},
            "brief": {"apiContract": {"rawSha256": sha(contract)}, "verbatim": derived["verbatim"],
                      "manifestSha256": "0" * 64,
                      "disclosureFiles": ["engine/conventions.md"],
                      "disclosures": [{"file": f"inputs/map/{self.nupkg.name}!map/corpus-map.json", "kind": "test-name",
                                       "name": "SecretBoardTests", "count": 1}]},
            "equivalence": {"allowedShims": [], "casesRequired": "all", "assistedAfterAnswers": 10},
            "decisions": [{"id": "H1", "question": "q?", "decision": "d.", "decidedBy": "Brandon",
                           "decidedOn": "2026-09-15"}],
        }
        return target

    def check(self, *extra, target=None, env=None):
        if target is not None:
            self.save(target)
        return run(check_target, self.engine, "--target", self.target_path, *extra, env=env)


class CommittedTarget(unittest.TestCase):
    def test_the_committed_target_is_internally_consistent(self):
        code, out = run(check_target, "--self-check")
        self.assertEqual(code, 0, out)


class CheckTarget(Repos):
    def test_a_target_derived_from_the_fixture_matches_and_is_not_verified_without_tests(self):
        code, out = self.check("--factory", self.factory, "--nupkg", self.nupkg)
        self.assertEqual(code, 3, out)
        self.assertNotIn("FAIL", out)

    def test_the_methods_are_split_into_hand_written_and_generated(self):
        project = self.target["tests"]["projects"]["HoyleBackgammon.Tests"]
        self.assertEqual(project["generated"], ["HoyleBackgammon.Tests.CorrespondenceTests.Every_map_entry_is_registered_in_map_order"])
        self.assertIn("HoyleBackgammon.Tests.SecretBoardTests.A_theory_with_two_cases", project["handWritten"])
        self.assertEqual(project["methodCount"], 5)

    def test_the_tests_run_and_pass(self):
        env = {"DOTNET": str(self.dotnet), "FAKE_TRX_SPEC": json.dumps(trx_spec())}
        code, out = self.check("--run-tests", env=env)
        self.assertEqual(code, 0, out)

    def test_an_sdk_override_is_never_a_pass(self):
        env = {"DOTNET": str(self.dotnet), "FAKE_TRX_SPEC": json.dumps(trx_spec())}
        # The fake repository has a global.json, so the override rewrites it in the export.
        code, out = self.check("--run-tests", "--sdk-override", "10.0.111", env=env)
        self.assertEqual(code, 3, out)

    def test_a_failed_case_or_a_missing_case_is_refused(self):
        for spec in (trx_spec(outcome="Failed"), trx_spec(drop_one=True)):
            env = {"DOTNET": str(self.dotnet), "FAKE_TRX_SPEC": json.dumps(spec)}
            code, out = self.check("--run-tests", env=env)
            self.assertEqual(code, 1, out)

    def test_every_pin_changed_on_its_own_is_refused(self):
        mutations = {
            "commit": lambda t: t["engine"].__setitem__("testsTree", "1" * 40),
            "provenance": lambda t: t["engine"].__setitem__("provenanceSha256", "2" * 64),
            "hand-written method": lambda t: t["tests"]["projects"]["HoyleBackgammon.Tests"]["handWritten"].pop(),
            "generated method": lambda t: t["tests"]["projects"]["HoyleBackgammon.Tests"]["generated"].append("X.Y.Z"),
            "classes": lambda t: t["tests"]["handWrittenClasses"].append("OtherTests"),
            "factory commit": lambda t: t["factory"].__setitem__("commit", "3" * 40),
            "recipes digest": lambda t: t["factory"].__setitem__("recipesDigest", "4" * 64),
            "map version": lambda t: t["map"].__setitem__("version", "6.0.1"),
            "nupkg": lambda t: t["map"].__setitem__("nupkgSha256", "5" * 64),
            "kernel": lambda t: t["kernel"].__setitem__("version", "0.2.0"),
            "corpus": lambda t: t["corpus"].__setitem__("contentHash", "6" * 64),
            "randomness": lambda t: t.__setitem__("randomness", "none"),
            "ruleset": lambda t: t["identity"]["ruleset"].__setitem__("version", 5),
            "replay schema": lambda t: t["identity"].__setitem__("replaySchema", 3),
            "replay hash": lambda t: t["replay"].__setitem__("canonicalJsonSha256", "7" * 64),
            "replay seed": lambda t: t["replay"].__setitem__("seed", 1),
            "generated file": lambda t: t["generatedFiles"][0].__setitem__("sha256", "8" * 64),
            "managed file": lambda t: t["managedFiles"].pop(),
            "ruling": lambda t: t["ownerRulings"][0].__setitem__("answer", "A gammon."),
            "fully ruled": lambda t: t["overlay"].__setitem__("fullyRuled", []),
            "implemented": lambda t: t["overlay"]["implemented"].append("men-count"),
            "verbatim": lambda t: t["brief"]["verbatim"][0].__setitem__("sha256", "9" * 64),
            "unknown pinned field": lambda t: t["map"].__setitem__("extra", 1),
        }
        for name, mutate in mutations.items():
            with self.subTest(name):
                target = copy.deepcopy(self.target)
                mutate(target)
                code, out = self.check("--factory", self.factory, "--nupkg", self.nupkg, target=target)
                self.assertEqual(code, 1, f"{name} was not refused:\n{out}")

    def test_a_tag_naming_another_commit_is_refused(self):
        self.git(self.factory, "tag", "-f", "factory/v0.7.0", "HEAD~0")
        (self.factory / "tools/factory/extra.py").write_text("x = 1\n")
        self.commit_all(self.factory)
        self.git(self.factory, "tag", "-f", "factory/v0.7.0")
        code, out = self.check("--factory", self.factory)
        self.assertEqual(code, 1, out)
        self.assertIn("factory tag names the factory commit", out)

    def test_self_check_refusals(self):
        mutations = {
            "count": lambda t: t["tests"]["projects"]["HoyleBackgammon.Tests"].__setitem__("methodCount", 99),
            "unsorted": lambda t: t["tests"]["projects"]["HoyleBackgammon.Tests"]["handWritten"].reverse(),
            "cases": lambda t: t["tests"].__setitem__("caseCount", 13),
            "framework": lambda t: t["tests"]["projects"]["HoyleBackgammon.Tests"]["casesPerFramework"].pop("net8.0"),
            "disclosure": lambda t: t["brief"]["disclosures"][0].__setitem__("name", "NoSuchTests"),
            "decision": lambda t: t["decisions"].append(dict(t["decisions"][0])),
            "undated decision": lambda t: t["decisions"][0].pop("decidedOn"),
            "open decision": lambda t: t.__setitem__("openDecisions", []),
            "shim": lambda t: t["equivalence"]["allowedShims"].append("Adapter.cs"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name):
                target = copy.deepcopy(self.target)
                mutate(target)
                self.save(target)
                code, out = run(check_target, "--self-check", "--target", self.target_path)
                self.assertEqual(code, 1, f"{name} was not refused:\n{out}")


class Brief(Repos):
    def assemble(self):
        out = self.base / "brief"
        code, text = run(build_brief, "--target", self.target_path, "assemble", self.engine, "--factory", self.factory,
                         "--nupkg", self.nupkg, "--api-contract", self.contract, "--out", out)
        return code, text, out

    def scan(self, out, pin=True):
        if pin:
            target = json.loads(self.target_path.read_text())
            target["brief"]["manifestSha256"] = sha((out / "MANIFEST.json").read_bytes())
            self.save(target)
        return run(build_brief, "--target", self.target_path, "scan", self.engine, "--factory", self.factory,
                   "--nupkg", self.nupkg, out)

    def test_the_brief_assembles_redacts_and_holds_no_test_name_literal_or_copied_text(self):
        code, text, out = self.assemble()
        self.assertEqual(code, 0, text)
        everything = "\n".join(p.read_text(errors="replace") for p in out.rglob("*") if p.is_file() and p.suffix != ".nupkg")
        for secret in ("A_well_hidden_test_name_nobody_should_see", "SecretBoardTests", SECRET_SEED, SECRET_HASH,
                       "zorblax", "twiddle"):
            with self.subTest(secret):
                self.assertNotIn(secret, everything)
        manifest = json.loads((out / "MANIFEST.json").read_text())
        reasons = {(r["path"], r["reasons"]) for r in manifest["redactions"]}
        self.assertIn(("inputs/factory-docs/docs/method.md", "test-name"), reasons)
        self.assertIn(("engine/decisions/0001-rulings.md", "test-literal, test-name"), reasons)
        method = (out / "inputs/factory-docs/docs/method.md").read_text()
        self.assertIn("- one item", method, "a list item without a finding survives its neighbour's redaction")
        self.assertIn("A general paragraph about mapping.", method)
        skeleton = json.loads((out / "engine/overlay-skeleton.json").read_text())
        self.assertNotIn("tests", skeleton["game-value"])
        self.assertEqual(skeleton["game-value"]["declines"], [])
        self.assertEqual(skeleton["game-value"]["rulings"][0]["answer"], "A hit.")
        code, text = self.scan(out)
        self.assertEqual(code, 0, text)

    def test_each_kind_of_leak_planted_in_the_brief_is_found(self):
        code, text, out = self.assemble()
        self.assertEqual(code, 0, text)
        plants = {
            "engine/decisions/0001-rulings.md": "\nA_well_hidden_test_name_nobody_should_see\n",
            "engine/api-contract.md": f"\n      /// seeded with {SECRET_SEED}\n",
            "engine/overlay-skeleton.json": "\n the frobnicator must twiddle every widget before the gadget sings loudly\n",
            "inputs/factory-docs/README.md": "\nwidgets = CountTheWidgetsCarefullyBeforeTheGadgetStartsToSingLoudly(); return widgets.ToString();\n",
            "inputs/corpus/hoyle.txt": "\nthe zorblax returned seventeen instead of the eleven it should have\n",
        }
        for path, plant in plants.items():
            with self.subTest(path):
                file = out / path
                original = file.read_bytes()
                file.write_text(original.decode() + plant)
                code, text = self.scan(out)
                self.assertEqual(code, 1, f"{path}: planted leak not found:\n{text}")
                file.write_bytes(original)
        code, text = self.scan(out)
        self.assertEqual(code, 0, text)

    def test_a_disclosure_file_may_copy_text_but_not_names(self):
        code, text, out = self.assemble()
        conventions = out / "engine/conventions.md"
        original = conventions.read_text()
        conventions.write_text(original + "\nthe frobnicator must twiddle every widget before the gadget sings loudly\n")
        code, text = self.scan(out)
        self.assertNotIn("engine/conventions.md: copied-text", text)
        conventions.write_text(original + "\nSecretBoardTests\n")
        code, text = self.scan(out)
        self.assertIn("engine/conventions.md: test-name", text)

    def test_a_disclosure_count_that_changes_is_refused(self):
        target = copy.deepcopy(self.target)
        target["brief"]["disclosures"][0]["count"] = 2
        self.save(target)
        code, text, out = self.assemble()
        self.assertEqual(code, 1, text)
        self.assertIn("pinned 2 time(s), found 1", text)

    def test_a_signature_naming_a_test_is_refused_not_redacted(self):
        self.contract.write_text(self.contract.read_text() + "    public static void SecretBoardTests()\n")
        target = copy.deepcopy(self.target)
        target["brief"]["apiContract"]["rawSha256"] = sha(self.contract.read_text())
        self.save(target)
        code, text, out = self.assemble()
        self.assertEqual(code, 1, text)
        self.assertIn("signature line has a finding", text)

    def test_a_brief_whose_manifest_is_not_the_pinned_one_is_refused(self):
        code, text, out = self.assemble()
        target = json.loads(self.target_path.read_text())
        target["brief"]["manifestSha256"] = "f" * 64
        self.save(target)
        code, text = self.scan(out, pin=False)
        self.assertEqual(code, 1, text)
        self.assertIn("not the pinned brief", text)

    def test_a_brief_file_changed_after_assembly_is_refused(self):
        code, text, out = self.assemble()
        (out / "engine/conventions.md").write_text("changed\n")
        code, text = self.scan(out)
        self.assertEqual(code, 1, text)
        self.assertIn("not the file MANIFEST.json records", text)

    def test_the_factory_is_staged_as_a_clean_tools_only_checkout_of_the_tag(self):
        code, text, out = self.assemble()
        self.assertEqual(code, 0, text)
        stage = out / build_brief.STAGE
        self.assertEqual(self.git(stage, "rev-parse", "HEAD"), self.factory_commit)
        self.assertEqual(self.git(stage, "remote"), "")
        self.assertTrue((stage / "tools/factory/generate.py").is_file())
        self.assertFalse((stage / "docs").exists())
        self.assertNotEqual(subprocess.run(["git", "-C", str(stage), "cat-file", "-e", "HEAD:docs/method.md"],
                                           capture_output=True).returncode, 0, "a blob outside the sparse paths is present")
        manifest = json.loads((out / "MANIFEST.json").read_text())
        self.assertFalse([f for f in manifest["files"] if "/.git/" in f["path"]])
        # Running the factory writes __pycache__, which neither dirties the stage nor fails the scan.
        (stage / "tools/factory/__pycache__").mkdir()
        (stage / "tools/factory/__pycache__/generate.cpython-312.pyc").write_bytes(b"\0")
        self.assertEqual(build_brief.check_stage(out, self.target, self.factory), [])

    def test_a_tampered_stage_is_refused(self):
        code, text, out = self.assemble()
        stage = out / build_brief.STAGE
        cases = {
            "edited tool": lambda: (stage / "tools/factory/generate.py").write_text("changed\n"),
            "remote": lambda: self.git(stage, "remote", "add", "origin", "https://example.invalid/x"),
        }
        for name, tamper in cases.items():
            with self.subTest(name):
                tamper()
                self.assertTrue(build_brief.check_stage(out, self.target, self.factory), name)
                code, text = self.scan(out)
                self.assertEqual(code, 1, text)
                self.git(stage, "checkout", "--", ".")
                subprocess.run(["git", "-C", str(stage), "remote", "remove", "origin"], capture_output=True)

    def test_the_review_quotes_what_was_removed_and_the_manifest_does_not(self):
        review = self.base / "REDACTIONS.md"
        out = self.base / "brief"
        code, text = run(build_brief, "--target", self.target_path, "assemble", self.engine, "--factory", self.factory,
                         "--nupkg", self.nupkg, "--api-contract", self.contract, "--out", out, "--review", review)
        self.assertEqual(code, 0, text)
        body = review.read_text()
        self.assertIn("The SecretBoardTests class once pinned this.", body)
        self.assertIn("test-name `SecretBoardTests`", body)
        self.assertIn(f"test-literal `{SECRET_SEED}`", body)
        self.assertNotIn("SecretBoardTests", (out / "MANIFEST.json").read_text())

    def test_an_answer_is_checked_like_the_brief(self):
        clean = self.base / "001-answer.md"
        clean.write_text("Moves are listed highest origin first.\n")
        leaky = self.base / "002-answer.md"
        leaky.write_text("See A_well_hidden_test_name_nobody_should_see.\n")
        common = ("--target", self.target_path, "check-text", self.engine, "--factory", self.factory, "--nupkg", self.nupkg)
        self.assertEqual(run(build_brief, *common, clean)[0], 0)
        code, text = run(build_brief, *common, clean, leaky)
        self.assertEqual(code, 1, text)
        self.assertIn("002-answer.md: test-name", text)

    def test_markdown_units_and_unlinking(self):
        blocks = build_brief.markdown_blocks("para one\nline two\n\n- a\n  - nested\n- b\n\n```\ncode\n\nmore\n```\n")
        self.assertIn("- a\n  - nested", blocks)
        self.assertIn("- b", blocks)
        self.assertIn("```\ncode\n\nmore\n```", blocks)
        root = self.base / "links"
        (root / "docs").mkdir(parents=True)
        (root / "docs/here.md").write_text("x")
        page = root / "README.md"
        text = build_brief.unlink_missing("[ok](docs/here.md) [gone](tools/x.py) [web](https://example.com)", page, root)
        self.assertIn("[ok](docs/here.md)", text)
        self.assertIn("gone (`tools/x.py`, not in the brief)", text)
        self.assertIn("[web](https://example.com)", text)


class CheckRebuild(Repos):
    def rebuild(self, **changes):
        repo = self.base / "rebuild"
        files = {k: v for k, v in self.engine_files.items()
                 if (not k.startswith("tests/") or "/Generated/" in k) and k != "src/HoyleBackgammon/Engine.cs"}
        files["src/HoyleBackgammon/Mine.cs"] = "namespace HoyleBackgammon;\npublic static class Engine { public static string Hash() => \"x\"; }\n"
        files["docs/decisions/0001-rulings.md"] = "# my own record\n"
        files.update(changes)
        self.write_repo(repo, files)
        return repo, self.commit_all(repo)

    def judge(self, repo, commit, *extra, env=None):
        return run(check_rebuild, repo, self.engine, "--commit", commit, "--target", self.target_path, *extra, env=env)

    def test_a_rebuild_with_the_same_provenance_and_generated_files_passes(self):
        repo, commit = self.rebuild()
        code, out = self.judge(repo, commit, "--skip-tests")
        self.assertEqual(code, 3, out)
        env = {"DOTNET": str(self.dotnet), "FAKE_TRX_SPEC": json.dumps(trx_spec())}
        code, out = self.judge(repo, commit, env=env)
        self.assertEqual(code, 0, out)

    def test_provenance_generated_files_and_copies_are_refused(self):
        provenance = json.loads(self.engine_files["provenance.json"])
        other_factory = copy.deepcopy(provenance)
        other_factory["factory"]["commit"] = "a" * 40
        other_ruling = copy.deepcopy(provenance)
        other_ruling["rulings"][0]["answer"] = "A gammon."
        cases = {
            "factory": {"provenance.json": json.dumps(other_factory)},
            "ruling": {"provenance.json": json.dumps(other_ruling)},
            "generated file edited": {"src/HoyleBackgammon/Generated/Registry.g.cs": "// edited\n"},
            "copied source": {"src/HoyleBackgammon/Engine.cs": ENGINE_SOURCE},
        }
        for name, change in cases.items():
            with self.subTest(name):
                repo, commit = self.rebuild(**change)
                code, out = self.judge(repo, commit, "--skip-tests")
                self.assertEqual(code, 1, f"{name} was not refused:\n{out}")
                subprocess.run(["rm", "-rf", str(repo)], check=True)

    def test_the_pass_count_and_the_label_are_reported(self):
        repo, commit = self.rebuild()
        questions = self.base / "questions"
        questions.mkdir()
        env = {"DOTNET": str(self.dotnet), "FAKE_TRX_SPEC": json.dumps(trx_spec(outcome="Failed"))}
        code, out = self.judge(repo, commit, "--questions", questions, env=env)
        self.assertEqual(code, 1, out)
        self.assertIn("info P1 10 of 12 case(s) passed", out)
        self.assertIn("label: blind, with a written interface (0 answer(s)", out)
        for n in range(11):
            (questions / f"{n:03d}-answer.md").write_text("an answer\n")
        code, out = self.judge(repo, commit, "--skip-tests", "--questions", questions)
        self.assertIn("label: assisted, with a written interface (11 answer(s)", out)

    def test_failing_target_tests_fail_the_rebuild(self):
        repo, commit = self.rebuild()
        env = {"DOTNET": str(self.dotnet), "FAKE_TRX_SPEC": json.dumps(trx_spec(outcome="Failed"))}
        code, out = self.judge(repo, commit, env=env)
        self.assertEqual(code, 1, out)


search_transcript = load("hoyle_search_transcript", EXAMPLE / "search-transcript.py")
proxy = load("hoyle_allowlist_proxy", EXAMPLE / "sandbox" / "allowlist-proxy.py")


class SearchTranscript(Repos):
    def search(self, *files, network_log=None):
        argv = ["--target", self.target_path, *files]
        if network_log:
            argv += ["--network-log", network_log]
        return run(search_transcript, *argv)

    def jsonl(self, name, *records):
        path = self.base / name
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return path

    def test_a_clean_session_passes_and_disclosed_names_are_not_failures(self):
        transcript = self.jsonl(
            "clean.jsonl",
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "input": {"command": "dotnet test"}}]}},
            # The brief's own README names the target repository; reading it is not an action.
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "Do not look at brandonifco/hoyle-backgammon"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "observable in SecretBoardTests only"}]}})
        log = self.jsonl("network.jsonl",
                         {"method": "CONNECT", "target": "api.nuget.org:443", "allowed": True},
                         {"method": "GET", "target": "http://ocsp.digicert.com/abc", "allowed": False})
        code, out = self.search(transcript, network_log=log)
        self.assertEqual(code, 0, out)
        self.assertIn("REVIEW network.jsonl:2: refused GET http://ocsp.digicert.com/abc", out)

    def test_each_sign_of_looking_is_a_failure(self):
        cases = {
            "test method in a result": [{"type": "user", "message": {"content": [
                {"type": "tool_result", "content": "A_theory_with_two_cases"}]}}],
            "github fetch": [{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "input": {"url": "https://github.com/brandonifco/hoyle-backgammon"}}]}}],
            "reading the example": [{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "input": {"file_path": "/src/rules-factory/examples/hoyle-blind-rebuild/TARGET.json"}}]}}],
        }
        for name, records in cases.items():
            with self.subTest(name):
                code, out = self.search(self.jsonl(f"{name}.jsonl", *records))
                self.assertEqual(code, 1, out)
        for name, entry in {"refused github": {"method": "CONNECT", "target": "github.com:443", "allowed": False},
                            "allowed off-list": {"method": "CONNECT", "target": "evil.example:443", "allowed": True}}.items():
            with self.subTest(name):
                code, out = self.search(network_log=self.jsonl(f"{name}.jsonl", entry))
                self.assertEqual(code, 1, out)


class AllowlistProxy(unittest.TestCase):
    def test_hosts(self):
        rules = ["api.nuget.org", ".nuget.org", "learn.microsoft.com"]
        self.assertTrue(proxy.allowed("api.nuget.org", rules))
        self.assertTrue(proxy.allowed("globalcdn.nuget.org", rules))
        self.assertTrue(proxy.allowed("nuget.org", rules))
        self.assertTrue(proxy.allowed("LEARN.microsoft.com.", rules))
        self.assertFalse(proxy.allowed("github.com", rules))
        self.assertFalse(proxy.allowed("evilnuget.org", rules))
        self.assertFalse(proxy.allowed("learn.microsoft.com.evil.example", rules))

    def test_the_committed_allowlist_names_no_github_host(self):
        rules = search_transcript.allowlist(EXAMPLE / "sandbox" / "allowlist.txt")
        self.assertTrue(rules)
        self.assertFalse([r for r in rules if "github" in r])


if __name__ == "__main__":
    unittest.main()
