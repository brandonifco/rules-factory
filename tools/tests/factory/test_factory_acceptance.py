#!/usr/bin/env python3
"""An engine that declares an action surface proves it through that surface (decision 0078).

`acceptance.json` at the engine root is the declaration, and its presence is all `produce` needs to
emit `tests/{name}.Tests/Generated/ActionSurfaceAcceptance.g.cs`: the harness that plays whole runs
through the engine's own surface and holds eight invariants over them. No example engine declares a
surface, so what is asserted here is asserted against a fixture: a counter that offers +1 and +2 and
is over at 10 (tools/tests/factory/fixtures/action-surface/ActionSurface.cs), written as the adapter
an engine would write, in the HoyleBackgammon engine `scripts/validate-engine.sh` produces.

  * **Without a .NET SDK** (always run): the declaration is validated at produce time and a bad one
    is refused naming its field; no declaration means no harness, no record of one and nothing in any
    generated file; a declaration emits the harness with its numbers baked in, records the declaration
    as a build input, and `produce` never writes it; a harness whose source is gone is removed; the
    engine's own gate regenerates it and refuses a stray one; and the harness is the eight facts, the
    six members and the three constants, and has no parameter that applies a subset of the actions.
  * **With the pinned SDK** (skipped, saying why, without it): the harness passes on a correct adapter;
    each invariant goes red under an adapter that violates exactly it; an allowlisted locator another
    entry cites is refused by its own fact; and a declaration with no adapter does not build, the
    compiler naming each member. One produced engine is built once, and the violations are selected by
    an environment variable the fixture adapter reads, so a case costs a test run and not a build.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")
FIXTURE = os.path.join(HERE, "fixtures", "action-surface", "ActionSurface.cs")

_spec = importlib.util.spec_from_file_location("factory_main_acceptance", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
import acceptance  # noqa: E402  (tools/factory is on sys.path now)
import pins  # noqa: E402

HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
NAME = "HoyleBackgammon"
HARNESS = f"tests/{NAME}.Tests/Generated/ActionSurfaceAcceptance.g.cs"
ADAPTER = f"tests/{NAME}.Tests/ActionSurface.cs"
DECLARATION = {
    "seedsPerConfiguration": 20,
    "stepCap": 40,
    "leastCompleted": 0.5,
    "allowlist": {"rubber-scoring": "docs/rubber.md, the reading of a rubber"},
}
#: The facts the harness holds, in the record's numbering (section 2), and the one of section 3.
FACTS = ("Every_offered_action_is_accepted", "Nothing_throws", "Nothing_stalls_without_a_reason",
         "A_run_ends_within_the_step_cap", "Runs_stop_early_only_on_the_allowlist", "Enough_runs_complete",
         "Replay_is_deterministic_compared_structurally", "Allowlisted_locators_are_cited_by_one_entry_only")
MEMBERS = ("Configurations", "Start", "IsOver", "LegalActions", "Apply", "Render")


def pack(map_dir, out):
    subprocess.run([sys.executable, PACK, map_dir, "--out", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
    return os.path.join(out, name)


def produce(package, out, expect=factory.NOT_VERIFIED):
    """`factory produce --no-verify` in this process: (exit code, output)."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = factory.main(["produce", "--package", package, "--corpus", os.path.join(HOYLE, "hoyle.txt"),
                             "--name", NAME, "--out", out,
                             "--allow-dirty",  # this checkout's state is not under test here
                             "--no-verify"])  # nor is building it: that is the dotnet class's
    if expect is not None and code != expect:
        raise AssertionError(f"produce exited {code}, not {expect}\n{buffer.getvalue()}")
    return code, buffer.getvalue()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def write_declaration(engine, declaration=None, raw=None):
    write(os.path.join(engine, "acceptance.json"),
          raw if raw is not None else json.dumps(DECLARATION if declaration is None else declaration, indent=2) + "\n")


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def tree(root):
    found = {}
    for directory, _, names in os.walk(root):
        for name in names:
            found[os.path.relpath(os.path.join(directory, name), root).replace(os.sep, "/")] = read(
                os.path.join(directory, name))
    return found


def record(engine):
    with open(os.path.join(engine, "provenance.json"), encoding="utf-8") as handle:
        return json.load(handle)


class Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        cls.nupkg = pack(HOYLE, os.path.join(cls.shared, "feed"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def engine(self, declaration=None, declare=True):
        out = tempfile.mkdtemp(dir=self.tmp)  # a fresh engine each time: a subtest may leave a refused declaration
        shutil.rmtree(out)
        produce(self.nupkg, out)
        if declare:
            write_declaration(out, declaration)
            produce(self.nupkg, out)
        return out

    def script(self, engine, *args):
        done = subprocess.run([sys.executable, os.path.join(engine, "scripts", "engine-gate.py"), *args], cwd=engine,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return done.returncode, done.stdout

    def recompute(self, engine):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = factory.main(["provenance", "--engine", engine, "--package", self.nupkg])
        return code, buffer.getvalue()


class TestNoDeclarationNoHarness(Case):
    def test_an_engine_with_no_acceptance_json_gets_no_harness_and_no_trace_of_one(self):
        engine = self.engine(declare=False)
        files = tree(engine)
        self.assertNotIn(HARNESS, files)
        self.assertEqual([p for p in files if "ActionSurface" in p or p == "acceptance.json"], [])
        recorded = record(engine)
        self.assertEqual([item["path"] for item in recorded["generated"] if "ActionSurface" in item["path"]], [])
        self.assertNotIn("acceptance.json", [item["path"] for item in recorded["buildInputs"]])
        self.assertNotIn("acceptance.json", [item["path"] for item in recorded["engineOwned"]])
        generated = [p for p in files if p.endswith(".g.cs")]
        for path in generated:
            self.assertNotIn(b"ActionSurface", files[path], f"{path} says something about a surface nobody declared")

    def test_two_produces_without_a_declaration_are_byte_identical(self):
        first = self.engine(declare=False)
        second = os.path.join(self.tmp, "second")
        produce(self.nupkg, second)
        self.assertEqual(tree(first), tree(second))


class TestDeclaredSurface(Case):
    def test_a_declaration_emits_the_harness_with_its_numbers_baked_in(self):
        engine = self.engine()
        text = read(os.path.join(engine, *HARNESS.split("/"))).decode("utf-8")
        self.assertIn("internal const int SeedsPerConfiguration = 20;", text)
        self.assertIn("internal const int StepCap = 40;", text)
        self.assertIn("internal const double LeastCompleted = 0.5;", text)
        self.assertIn('("rubber-scoring", "docs/rubber.md, the reading of a rubber"),', text)
        self.assertIn(f"namespace {NAME}.Tests;", text)
        self.assertTrue(text.startswith("// <auto-generated>"))
        for marker in ("@HEADER@", "@NAME@", "@SEEDS@", "@CAP@", "@LEAST@", "@ALLOWLIST@", "@DUMP@"):
            self.assertNotIn(marker, text, "a marker was left unreplaced")

    def test_the_harness_is_recorded_as_generated_and_the_declaration_as_the_engines_own_input(self):
        engine = self.engine()
        recorded = record(engine)
        generated = {item["path"] for item in recorded["generated"]}
        self.assertIn(HARNESS, generated)
        self.assertIn("acceptance.json", [item["path"] for item in recorded["engineOwned"]])
        inputs = {item["path"]: item["sha256"] for item in recorded["buildInputs"]}
        import hashlib
        self.assertEqual(inputs["acceptance.json"], hashlib.sha256(read(os.path.join(engine, "acceptance.json"))).hexdigest())
        self.assertNotIn("acceptance.json", generated, "the declaration is the engine's, not generated")
        self.assertEqual(self.recompute(engine)[0], 0, self.recompute(engine)[1])

    def test_produce_never_writes_or_rewrites_the_declaration(self):
        engine = self.engine(declare=False)
        self.assertFalse(os.path.exists(os.path.join(engine, "acceptance.json")))
        raw = '{\n"stepCap":   40, "seedsPerConfiguration": 20,\n  "leastCompleted": 0.5, "allowlist": {}}\n'
        write_declaration(engine, raw=raw)
        produce(self.nupkg, engine)
        self.assertEqual(read(os.path.join(engine, "acceptance.json")).decode("utf-8"), raw)

    def test_editing_the_declaration_without_a_produce_is_a_named_provenance_mismatch(self):
        engine = self.engine()
        write_declaration(engine, dict(DECLARATION, stepCap=41))
        code, output = self.recompute(engine)
        self.assertEqual(code, 1, output)
        self.assertIn("MISMATCH buildInputs[acceptance.json]", output)

    def test_a_harness_emitted_earlier_disappears_with_its_source(self):
        engine = self.engine()
        self.assertTrue(os.path.isfile(os.path.join(engine, *HARNESS.split("/"))))
        os.remove(os.path.join(engine, "acceptance.json"))
        _, output = produce(self.nupkg, engine)
        self.assertFalse(os.path.exists(os.path.join(engine, *HARNESS.split("/"))))
        self.assertIn(f"(removed) {HARNESS}", output)
        recorded = record(engine)
        self.assertEqual([item["path"] for item in recorded["generated"] if "ActionSurface" in item["path"]], [])
        self.assertNotIn("acceptance.json", [item["path"] for item in recorded["buildInputs"]])
        self.assertEqual(self.recompute(engine)[0], 0)

    def test_the_engines_own_gate_regenerates_the_harness_and_refuses_a_stray_one(self):
        engine = self.engine()
        with __import__("zipfile").ZipFile(self.nupkg) as archive:
            for part, name in (("map/corpus-map.json", "package-map.json"), ("map/corpus-manifest.json", "package-manifest.json")):
                with open(os.path.join(self.tmp, name), "wb") as handle:
                    handle.write(archive.read(part))
        args = ["regenerate", "--package-map", os.path.join(self.tmp, "package-map.json"),
                "--package-manifest", os.path.join(self.tmp, "package-manifest.json"),
                "--package-id", "RulesFactory.Maps.HoyleBackgammon", "--package-version", "6.0.0", "--name", NAME]
        code, output = self.script(engine, *args)
        self.assertEqual(code, 0, output)
        write_declaration(engine, dict(DECLARATION, seedsPerConfiguration=21))
        code, output = self.script(engine, *args)
        self.assertEqual(code, 1, output)
        self.assertIn(f"{HARNESS} differs from a fresh regeneration", output)
        os.remove(os.path.join(engine, "acceptance.json"))
        code, output = self.script(engine, *args)
        self.assertEqual(code, 1, output)
        self.assertIn(f"{HARNESS} is a *.g.cs file the factory does not generate", output)
        write_declaration(engine, dict(DECLARATION, stepCap=0))
        code, output = self.script(engine, *args)
        self.assertEqual(code, 1, output)
        self.assertIn("`stepCap`", output, "the gate refuses a malformed declaration the way produce does")

    def test_the_harness_is_these_facts_these_members_and_these_constants_and_nothing_that_takes_a_subset(self):
        text = read(os.path.join(self.engine(), *HARNESS.split("/"))).decode("utf-8")
        self.assertEqual(re.findall(r"\[Fact\]\s+public void (\w+)\(", text), list(FACTS))
        self.assertEqual(re.findall(r"internal static partial [\w<>.,\s]+? (\w+)\(", text), list(MEMBERS))
        self.assertEqual(re.findall(r"internal const \w+ (\w+) =", text), ["SeedsPerConfiguration", "StepCap", "LeastCompleted"])
        # Decision 0078 section 4: no knob applies some of the offered actions. The three numbers above
        # are the only ones, and every offered action of every step is applied.
        for forbidden in ("Sample", "Subset", "Skip(", "MaxActions", "ActionsPerStep"):
            self.assertNotIn(forbidden, text)
        self.assertIn("for (var i = 0; i < offered.Length; i++)", text)


class TestTheDeclarationIsValidated(Case):
    def refused(self, *needles, declaration=None, raw=None):
        engine = self.engine()
        before = tree(engine)
        write_declaration(engine, declaration, raw)
        before["acceptance.json"] = read(os.path.join(engine, "acceptance.json"))
        code, output = produce(self.nupkg, engine, expect=None)
        self.assertEqual(code, 1, output)
        self.assertIn("acceptance.json:", output)
        for needle in needles:
            self.assertIn(needle, output)
        self.assertEqual(tree(engine), before, "a refused produce leaves the engine as it was")

    def test_a_declaration_that_is_not_json_is_refused(self):
        self.refused("cannot be read as JSON", raw="{not json")

    def test_a_declaration_that_is_not_an_object_is_refused(self):
        self.refused(raw="[1, 2]\n")

    def test_a_duplicate_key_is_refused(self):
        self.refused("appears twice", raw='{"stepCap": 1, "stepCap": 2}\n')

    def test_an_unknown_field_is_refused_by_name(self):
        self.refused("'sampleActions'", declaration=dict(DECLARATION, sampleActions=3))

    def test_each_missing_field_is_refused_by_name(self):
        for field in DECLARATION:
            with self.subTest(field=field):
                declaration = {k: v for k, v in DECLARATION.items() if k != field}
                self.refused(f"`{field}` is missing", declaration=declaration)

    def test_a_count_that_is_not_an_integer_of_at_least_one_is_refused_by_name(self):
        for field in ("seedsPerConfiguration", "stepCap"):
            for bad in (0, -3, 1.5, True, "3", None):
                with self.subTest(field=field, value=bad):
                    self.refused(f"`{field}` is {bad!r}", declaration=dict(DECLARATION, **{field: bad}))

    def test_a_completion_fraction_outside_zero_exclusive_to_one_inclusive_is_refused_by_name(self):
        for bad in (0, 0.0, -0.5, 1.5, True, "0.5", None):
            with self.subTest(value=bad):
                self.refused(f"`leastCompleted` is {bad!r}", declaration=dict(DECLARATION, leastCompleted=bad))
        self.refused("NaN is not a number", raw=json.dumps(DECLARATION).replace("0.5", "NaN"))

    def test_the_fraction_one_is_admitted(self):
        engine = self.engine(dict(DECLARATION, leastCompleted=1))
        self.assertIn("internal const double LeastCompleted = 1.0;", read(os.path.join(engine, *HARNESS.split("/"))).decode())

    def test_an_allowlist_that_is_not_an_object_is_refused_by_name(self):
        self.refused("`allowlist`", declaration=dict(DECLARATION, allowlist=["rubber-scoring"]))

    def test_an_allowlist_item_must_say_where_the_reading_is_documented(self):
        for bad in ("", "   ", None, 3, ["docs"]):
            with self.subTest(value=bad):
                self.refused("`allowlist` item 'rubber-scoring'",
                             declaration=dict(DECLARATION, allowlist={"rubber-scoring": bad}))

    def test_an_allowlist_id_that_is_not_an_entry_of_the_map_is_refused(self):
        self.refused("`allowlist` item 'no-such-rule' is not an entry of this engine's map",
                     declaration=dict(DECLARATION, allowlist={"no-such-rule": "docs/x.md"}))

    def test_the_id_form_is_the_one_the_registry_uses_which_for_a_composed_engine_is_qualified(self):
        model = types.SimpleNamespace(by_id={"Srd52Combat.round-down": {}, "Srd52Rules.round-down": {}})
        root = os.path.join(self.tmp, "composed")
        write_declaration(root, dict(DECLARATION, allowlist={"Srd52Combat.round-down": "docs/x.md"}))
        self.assertEqual(list(acceptance.load(root, model)["allowlist"]), ["Srd52Combat.round-down"])
        write_declaration(root, dict(DECLARATION, allowlist={"round-down": "docs/x.md"}))
        with self.assertRaises(acceptance.semantics.GenerationError) as raised:
            acceptance.load(root, model)
        self.assertIn("'round-down' is not an entry", str(raised.exception))

    def test_no_file_is_no_declaration(self):
        self.assertIsNone(acceptance.load(self.tmp, types.SimpleNamespace(by_id={})))


# --- with the pinned SDK ----------------------------------------------------------------------


def _pinned_sdk():
    if os.environ.get("RULES_FACTORY_SKIP_DOTNET") or not shutil.which("dotnet"):
        return False
    try:
        listed = subprocess.run(["dotnet", "--list-sdks"], cwd=tempfile.gettempdir(), stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(line.split(" ")[0] == pins.SDK_VERSION for line in listed.splitlines())


#: The violations the fixture adapter commits (selected by ACTION_SURFACE_FIXTURE), and the one fact
#: each must turn red, and only it. Every violation is committed in some of one configuration's runs,
#: so the completion fraction still holds and invariant 6 is not what goes red by accident.
VIOLATIONS = {
    "refuse": ("Every_offered_action_is_accepted", "was answered with UnsupportedRule"),
    "throw": ("Nothing_throws", "threw System.InvalidOperationException: the fixture throws here"),
    "stall": ("Nothing_stalls_without_a_reason", "offers no action and gives no reason"),
    "loop": ("A_run_ends_within_the_step_cap", "not over after 40 steps"),
    "decline-outside": ("Runs_stop_early_only_on_the_allowlist", "which is not an allowlisted reading"),
    "decline-reason": ("Runs_stop_early_only_on_the_allowlist", "stopped on OutsideCurrentScope"),
    "slow": ("Enough_runs_complete", "beta: 0 of 20 seeds reached a natural end, below the declared 0.5"),
    "drift": ("Replay_is_deterministic_compared_structurally", "the final states differ structurally"),
    "history-drift": ("Replay_is_deterministic_compared_structurally", "the histories first differ at step 0"),
}


@unittest.skipUnless(_pinned_sdk(), f"needs the .NET SDK {pins.SDK_VERSION} the kernel pins (dotnet --list-sdks), "
                                    f"or RULES_FACTORY_SKIP_DOTNET is set; the `validate` runner has it")
class TestHarnessRunsInDotnet(Case):
    """One engine, built once; the violations are selected by an environment variable, not a rebuild."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = os.path.join(cls.shared, "base")
        produce(cls.nupkg, cls.base)
        write_declaration(cls.base)
        shutil.copyfile(FIXTURE, os.path.join(cls.base, *ADAPTER.split("/")))
        produce(cls.nupkg, cls.base)
        code, output = cls.dotnet(cls.base, "build", f"tests/{NAME}.Tests/{NAME}.Tests.csproj", "-f", "net10.0",
                                  "-warnaserror", "-nologo")
        if code != 0:
            raise AssertionError("the fixture engine does not build:\n" + output[-4000:])

    @staticmethod
    def dotnet(engine, *args, variant=None):
        env = {k: v for k, v in os.environ.items() if k not in ("CI", "ACTION_SURFACE_FIXTURE")}
        env.update({"DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1", "MSBUILDDISABLENODEREUSE": "1",
                    "DOTNET_CLI_USE_MSBUILD_SERVER": "0"})
        if variant:
            env["ACTION_SURFACE_FIXTURE"] = variant
        # No compiler server and no reused build node: nothing is left running after the tests.
        extra = ["-p:UseSharedCompilation=false", "-nr:false"] if args[0] == "build" else []
        # A harness that never ended a run would otherwise hang the suite: five minutes is generous.
        done = subprocess.run(["dotnet", *args, *extra], cwd=engine, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, env=env, timeout=300)
        return done.returncode, done.stdout

    def run_variant(self, variant, engine=None, filter_="ActionSurfaceAcceptance"):
        """{test name: outcome} and the output, from the already built test project."""
        engine = engine or self.base
        results = os.path.join(self.tmp, f"{variant}.trx")
        code, output = self.dotnet(engine, "test", f"tests/{NAME}.Tests/{NAME}.Tests.csproj", "-f", "net10.0",
                                   "--no-build", "--filter", f"FullyQualifiedName~{filter_}",
                                   "--logger", f"trx;LogFileName={results}", variant=variant)
        outcomes = {}
        if os.path.isfile(results):
            for result in ET.parse(results).getroot().iter("{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}UnitTestResult"):
                outcomes[result.get("testName").rsplit(".", 1)[-1]] = result.get("outcome")
        return outcomes, output, code

    def test_the_harness_passes_on_a_correct_adapter_and_runs_every_fact(self):
        outcomes, output, code = self.run_variant("correct")
        self.assertEqual(outcomes, {fact: "Passed" for fact in FACTS}, output[-3000:])
        self.assertEqual(code, 0)

    def test_an_allowlisted_decline_ends_a_run_early_without_failing_anything(self):
        outcomes, output, _ = self.run_variant("decline-allowed")
        self.assertEqual(outcomes, {fact: "Passed" for fact in FACTS}, output[-3000:])

    def test_each_invariant_goes_red_under_the_adapter_that_violates_exactly_it(self):
        for variant, (fact, observed) in VIOLATIONS.items():
            with self.subTest(violation=variant):
                outcomes, output, code = self.run_variant(variant)
                self.assertEqual({name for name, outcome in outcomes.items() if outcome == "Failed"}, {fact}, output[-3000:])
                self.assertEqual(sorted(outcomes), sorted(FACTS), "every fact ran")
                self.assertEqual(code, 1)
                self.assertIn(observed, output)

    def test_equality_alone_cannot_tell_the_replays_apart_and_the_structural_dump_can(self):
        # The fixture's state compares by its value, as a record that compares its collections by
        # reference would: a replay whose final state differs only in a private field is equal to it.
        outcomes, output, _ = self.run_variant("drift", filter_="FixtureEquality")
        self.assertEqual(outcomes, {"Equality_cannot_see_a_private_field": "Passed"}, output[-3000:])
        outcomes, _, _ = self.run_variant("drift")
        self.assertEqual(outcomes["Replay_is_deterministic_compared_structurally"], "Failed")

    def test_an_allowlisted_locator_another_entry_cites_is_refused_by_its_own_fact(self):
        engine = os.path.join(self.tmp, "shared-locator")
        shutil.copytree(self.base, engine, ignore=shutil.ignore_patterns("bin", "obj"))
        # stake-multiplier is a premise of a derived entry, and four other entries cite its passage.
        write_declaration(engine, dict(DECLARATION, allowlist={"stake-multiplier": "docs/stakes.md"}))
        produce(self.nupkg, engine)
        code, output = self.dotnet(engine, "build", f"tests/{NAME}.Tests/{NAME}.Tests.csproj", "-f", "net10.0",
                                   "-warnaserror", "-nologo")
        self.assertEqual(code, 0, output[-3000:])
        outcomes, output, _ = self.run_variant("correct", engine=engine)
        self.assertEqual({n for n, o in outcomes.items() if o == "Failed"},
                         {"Allowlisted_locators_are_cited_by_one_entry_only"}, output[-3000:])
        self.assertIn("stake-multiplier (docs/stakes.md): its locator is also cited by", output)

    def test_a_declaration_without_an_adapter_does_not_build_and_the_compiler_names_each_member(self):
        engine = os.path.join(self.tmp, "no-adapter")
        shutil.copytree(self.base, engine, ignore=shutil.ignore_patterns("bin", "obj"))
        os.remove(os.path.join(engine, *ADAPTER.split("/")))
        code, output = self.dotnet(engine, "build", f"tests/{NAME}.Tests/{NAME}.Tests.csproj", "-f", "net10.0", "-nologo")
        self.assertNotEqual(code, 0, output[-3000:])
        for member in MEMBERS:
            self.assertTrue(re.search(rf"error CS8795: Partial method 'ActionSurfaceAcceptance\.{member}\(", output),
                            f"{member} is not named by CS8795:\n{output[-1500:]}")


if __name__ == "__main__":
    unittest.main()
