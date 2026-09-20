#!/usr/bin/env python3
"""validate-repo.py's scope table, proved unable to skip a check by accident (#342).

Scoping a gate is how a gate stops examining things. Every test here is about the one direction
that matters: a rule that is wrong must run more, never less. So the cases are not "does this
path map to that scope" alone -- they are also "is there any tracked path in this repository for
which the answer is silently nothing", and "does --full still refuse to skip".

Run: python3 -m pytest tools/tests/test_validate_repo.py
"""
import importlib.util
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(ROOT, "tools", "validate-repo.py")

_spec = importlib.util.spec_from_file_location("validate_repo", TOOL)
vr = importlib.util.module_from_spec(_spec)
# Registered before exec: the module's dataclasses resolve their own annotations through
# sys.modules, and `from __future__ import annotations` makes that resolution happen here.
sys.modules["validate_repo"] = vr
_spec.loader.exec_module(vr)


class TestEveryRowOfTheTable(unittest.TestCase):
    """Every row of the path table, and the widening it is there to cause."""

    def test_the_contract_and_its_subsystems_widen_to_full(self):
        for prefix in vr.CORE_PREFIXES:
            with self.subTest(prefix=prefix):
                scope = vr.classify([prefix + "anything.py"])
                self.assertEqual("full", scope.name)
                self.assertEqual(len(vr.discover_maps()), len(scope.maps))

    def test_every_named_core_file_widens_to_full(self):
        for path in vr.CORE_FILES:
            with self.subTest(path=path):
                self.assertEqual("full", vr.classify([path]).name)

    def test_every_named_core_file_exists(self):
        # A row naming a file that was renamed stops widening, and stops doing it quietly.
        for path in vr.CORE_FILES:
            with self.subTest(path=path):
                self.assertTrue(os.path.exists(os.path.join(ROOT, path)), path)

    def test_the_factory_asks_for_its_tests_and_an_engine(self):
        for prefix in vr.FACTORY_PREFIXES:
            with self.subTest(prefix=prefix):
                path = prefix + "x.py" if prefix.endswith("/") else prefix
                scope = vr.classify([path])
                self.assertEqual("changed", scope.name)
                self.assertTrue(scope.engine)
                self.assertEqual((), scope.maps)

    def test_a_change_to_one_map_narrows_to_that_map(self):
        scope = vr.classify(["examples/hoyle-backgammon/corpus-map.json"])
        self.assertEqual("changed", scope.name)
        self.assertEqual(("examples/hoyle-backgammon/corpus-map.json",), scope.maps)
        self.assertEqual(("examples/hoyle-backgammon/map-package.json",), scope.packages)
        self.assertFalse(scope.engine)

    def test_a_shared_corpus_narrows_to_every_map_that_reads_it(self):
        # srd-52-conditions cites the text committed under srd-52-combat. Deriving the affected
        # map from the changed path alone would check one of the two.
        scope = vr.classify(["examples/srd-52-combat/srd-5.2.1.txt"])
        self.assertEqual(
            ("examples/srd-52-combat/corpus-map.json",
             "examples/srd-52-conditions/corpus-map.json"),
            scope.maps,
        )

    def test_an_examples_directory_that_is_not_a_map_widens_to_full(self):
        for path in ("examples/validator-attack/results.json",
                     "examples/blind-mapping-trial/report.md",
                     "examples/hoyle-blind-rebuild/pins.json"):
            with self.subTest(path=path):
                self.assertEqual("full", vr.classify([path]).name)

    def test_a_path_no_row_places_widens_to_full(self):
        for path in ("README.md", "AGENTS.md", "docs/method.md", ".github/workflows/validate.yml",
                     "schema/corpus-map.schema.json", "tools/check-pr-docs.py", "examples/README.md"):
            with self.subTest(path=path):
                self.assertEqual("full", vr.classify([path]).name)

    def test_an_unscopable_examples_directory_widens_even_beside_a_map(self):
        # Ignoring the path instead of widening looks harmless on a diff that touches nothing
        # else, because a scope with no maps widens anyway. Beside a map it is not harmless: the
        # run would narrow to that map and the evidence directory would go unexamined.
        scope = vr.classify(["examples/validator-attack/results.json",
                             "examples/hoyle-backgammon/corpus-map.json"])
        self.assertEqual("full", scope.name)

    def test_one_widening_path_widens_the_whole_diff(self):
        scope = vr.classify(["examples/hoyle-backgammon/corpus-map.json", "tools/mapper/walk.py"])
        self.assertEqual("full", scope.name)


class TestNoTrackedPathIsSilentlyNothing(unittest.TestCase):
    """The property the table exists for, asked of every file this repository actually has."""

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout
        cls.tracked = [p for p in out.splitlines() if p]

    def test_there_are_tracked_files_to_judge(self):
        self.assertGreater(len(self.tracked), 100)

    def test_every_tracked_path_asks_for_something(self):
        # The failure this guards is a scope of "changed" with no map and no engine: every
        # narrowable step skipped, the run green, and nothing examined but the tests.
        for path in self.tracked:
            scope = vr.classify([path])
            if scope.name == "full":
                continue
            with self.subTest(path=path):
                self.assertTrue(scope.maps or scope.engine, f"{path} narrowed to nothing")


class TestFailingSafe(unittest.TestCase):
    def test_an_empty_diff_is_full(self):
        self.assertEqual("full", vr.classify([]).name)
        self.assertEqual("full", vr.classify(["", "  "]).name)

    def test_no_base_is_full(self):
        self.assertEqual("full", vr.classify_diff("").name)

    def test_a_base_git_cannot_read_is_full(self):
        scope = vr.classify_diff("this-is-not-a-commit")
        self.assertEqual("full", scope.name)
        self.assertIn("could not be read", " ".join(scope.reasons))

    def test_a_classifier_that_raises_is_full(self):
        original = vr.classify
        def explode(paths, root=vr.ROOT):
            raise RuntimeError("the table is broken")
        vr.classify = explode
        try:
            scope = vr.classify_diff("HEAD")
        finally:
            vr.classify = original
        self.assertEqual("full", scope.name)
        self.assertIn("RuntimeError", " ".join(scope.reasons))
        self.assertEqual(len(vr.discover_maps()), len(scope.maps))


class TestFullSkipsNothing(unittest.TestCase):
    def test_full_carries_every_map_and_every_package(self):
        scope = vr.full_scope()
        self.assertEqual(vr.discover_maps(), list(scope.maps))
        self.assertEqual(vr.discover(vr.ROOT, vr.PACKAGE_GLOB), list(scope.packages))

    def test_a_step_that_tries_to_skip_under_full_is_a_hard_error(self):
        run = vr.Run(vr.ROOT, vr.full_scope())
        with self.assertRaises(AssertionError):
            run.skip("any map's citations")

    def test_a_narrower_scope_may_skip_and_says_so(self):
        scope = vr.classify(["tools/factory/generate.py"])
        run = vr.Run(vr.ROOT, scope)
        self.assertTrue(run.skip("packing any map"))


class TestRelease(unittest.TestCase):
    def test_a_release_checks_every_map_and_packs_one(self):
        scope = vr.release_scope("hoyle-backgammon")
        self.assertEqual("release", scope.name)
        self.assertEqual(vr.discover_maps(), list(scope.maps))
        self.assertEqual(("examples/hoyle-backgammon/map-package.json",), scope.packages)

    def test_a_release_accepts_the_directory_spelling_too(self):
        self.assertEqual(vr.release_scope("hoyle-backgammon").packages,
                         vr.release_scope("examples/hoyle-backgammon").packages)

    def test_a_map_that_declares_no_package_cannot_be_released(self):
        with self.assertRaises(SystemExit):
            vr.release_scope("srd-52-conditions")


class TestTheFixtureTable(unittest.TestCase):
    """FIXTURES is the only hand-written list of inputs, so it is the only one that goes stale."""

    def test_every_map_on_disk_has_a_row(self):
        self.assertEqual(sorted(vr.discover_maps()), sorted(f.map for f in vr.FIXTURES))

    def test_every_row_names_files_that_exist(self):
        for fixture in vr.FIXTURES:
            with self.subTest(map=fixture.map):
                self.assertTrue(os.path.exists(os.path.join(ROOT, fixture.map)))
                for corpus in fixture.corpora:
                    self.assertTrue(os.path.isdir(os.path.join(ROOT, corpus)), corpus)
                for argv in fixture.locators:
                    self.assertTrue(os.path.exists(os.path.join(ROOT, argv[0])), argv[0])

    def test_every_row_names_its_own_directory_among_its_corpora(self):
        for fixture in vr.FIXTURES:
            with self.subTest(map=fixture.map):
                self.assertIn(fixture.directory, fixture.corpora)


class TestAMapWithNoRowIsNotQuietlyUnchecked(unittest.TestCase):
    """The two places FIXTURES is held to the maps on disk, each watched refusing."""

    def test_the_table_step_fails_on_a_map_it_does_not_name(self):
        scope = vr.full_scope()
        run = vr.Run(vr.ROOT, scope)
        original = vr.FIXTURES
        vr.FIXTURES = tuple(f for f in original if "hoyle" not in f.map)
        try:
            self.assertFalse(vr.step_fixture_table(run))
        finally:
            vr.FIXTURES = original

    def test_the_table_step_fails_on_a_row_naming_a_map_that_is_gone(self):
        run = vr.Run(vr.ROOT, vr.full_scope())
        original = vr.FIXTURES
        vr.FIXTURES = original + (
            # The corpus directory exists, so only the "row names a map that is not here" branch
            # can refuse this one. A row pointing a grammar at a map that moved is the failure.
            vr.Fixture(map="examples/hoyle-backgammon/corpus-map-gone.json",
                       corpora=("examples/hoyle-backgammon",), locators=()),
        )
        try:
            self.assertFalse(vr.step_fixture_table(run))
        finally:
            vr.FIXTURES = original

    def test_the_locator_step_refuses_a_map_with_no_grammar_rather_than_counting_it(self):
        # Skipping it would report "6 map(s) whose citations resolve" on seven maps: a count that
        # is true about what ran and false about what was proved.
        run = vr.Run(vr.ROOT, vr.full_scope())
        original = vr.FIXTURES
        vr.FIXTURES = tuple(f for f in original if "hoyle" not in f.map)
        try:
            self.assertFalse(vr.step_locators(run))
        finally:
            vr.FIXTURES = original


class TestTheStepsAreTheStepsThatRanBefore(unittest.TestCase):
    """--full is a promise about behaviour, and the step list is the part of it a test can hold.

    The names below are the ones scripts/validate.sh printed, in its order, plus the one step
    this change adds. A step deleted or reordered without a decision fails here.
    """

    BEFORE = (
        "each subsystem imports only the map contract",
        "check-map.py is what the two packages build",
        "every corpus map satisfies the schema",
        "every map says how its corpus is read",
        "every protocol's own detectors find its pointers",
        "every extent's units are enumerated and accounted",
        "every protocol's required sweeps run and report",
        "every corpus map carries a review of its bytes",
        "every blind mapping was given what it recorded",
        "every citation resolves in its corpus",
        "the measured miss rate still describes the validator",
        "every map package passes its publish gate",
        "the checkers' own tests",
        "every repository link resolves",
        "every decision record is indexed",
        "every workflow pins its Python and its packages",
        "the README's status table matches the factory CLI",
        "the README cites no closed issue as not yet done",
    )
    ADDED = ("every map has a row that names its corpora and its grammar",)

    def test_every_step_the_old_script_ran_still_runs_in_its_order(self):
        names = [name for name, _ in vr.STEPS]
        self.assertEqual(list(self.BEFORE), [n for n in names if n not in self.ADDED])

    def test_the_only_new_steps_are_declared_here(self):
        names = {name for name, _ in vr.STEPS}
        self.assertEqual(set(self.ADDED), names - set(self.BEFORE))


class TestTheWrapper(unittest.TestCase):
    def test_validate_sh_runs_the_full_scope(self):
        script = os.path.join(ROOT, "scripts", "validate.sh")
        text = open(script, encoding="utf-8").read()
        self.assertIn("tools/validate-repo.py", text)
        self.assertIn("--full", text)

    def test_explain_runs_nothing_and_prints_the_scope(self):
        proc = subprocess.run(
            [sys.executable, TOOL, "--explain", "--changed", "--base", "HEAD"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("scope:", proc.stdout)
        self.assertNotIn("==> [1]", proc.stdout)

    def test_changed_without_a_base_is_a_usage_error_and_not_a_silent_full_run(self):
        proc = subprocess.run([sys.executable, TOOL, "--changed"], cwd=ROOT,
                              capture_output=True, text=True)
        self.assertEqual(2, proc.returncode)
        self.assertIn("--base", proc.stderr)

    def test_two_scopes_at_once_is_a_usage_error(self):
        proc = subprocess.run([sys.executable, TOOL, "--full", "--release", "hoyle-backgammon"],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(2, proc.returncode)


class TestTheSuiteIsDistributedAndHeldToItsCollection(unittest.TestCase):
    """The tests run on every core the machine gives, and a lost worker is not a pass (#344).

    Serial, "N passed" with a plausible N was evidence the suite ran. Distributed, it is not:
    a worker that dies takes its tests with it and the number left is still plausible. So the
    step collects first and holds the run to the count, and these are the shapes that must fail.
    """

    class FakePytest:
        """Stands in for subprocess.run, answering collection and the run separately."""

        def __init__(self, collected="1750 tests collected in 0.5s\n",
                     ran="1750 passed, 1204 subtests passed in 78.2s\n",
                     collect_code=0, run_code=0):
            self.collected, self.ran = collected, ran
            self.collect_code, self.run_code = collect_code, run_code
            self.calls = []

        def __call__(self, argv, **kwargs):
            self.calls.append(argv)
            collecting = "--collect-only" in argv
            return subprocess.CompletedProcess(
                argv,
                self.collect_code if collecting else self.run_code,
                self.collected if collecting else self.ran,
                "",
            )

    def _step(self, fake):
        run = vr.Run(vr.ROOT, vr.full_scope())
        original = vr.subprocess.run
        vr.subprocess.run = fake
        try:
            return vr.step_tool_tests(run)
        finally:
            vr.subprocess.run = original

    def test_the_run_asks_for_every_core(self):
        fake = self.FakePytest()
        self.assertTrue(self._step(fake))
        run_argv = [a for a in fake.calls if "--collect-only" not in a][0]
        self.assertIn("-n", run_argv)
        self.assertEqual("auto", run_argv[run_argv.index("-n") + 1])

    def test_the_collection_is_taken_before_the_run(self):
        fake = self.FakePytest()
        self._step(fake)
        self.assertIn("--collect-only", fake.calls[0])

    def test_fewer_accounted_for_than_collected_is_a_failure(self):
        # The shape of a lost worker: pytest's own exit code is 0 and the number reads fine.
        self.assertFalse(self._step(self.FakePytest(ran="1400 passed in 60s\n")))

    def test_a_skip_accounts_for_its_test(self):
        # This job has no .NET SDK, so the tests that need one skip and the engine job runs them.
        # A skip is an outcome; refusing it here would fail every CI run for telling the truth.
        self.assertTrue(self._step(self.FakePytest(ran="1748 passed, 2 skipped in 174s\n")))

    def test_a_skip_does_not_cover_a_test_that_vanished(self):
        self.assertFalse(self._step(self.FakePytest(ran="1400 passed, 2 skipped in 60s\n")))

    def test_a_run_in_which_everything_skipped_proves_nothing(self):
        # Every test accounted for and not one of them run. Accounting alone would call this a
        # pass, which is the "reports ok while examining nothing" shape in its purest form.
        self.assertFalse(self._step(self.FakePytest(ran="1750 skipped in 3.1s\n")))

    def test_the_other_outcome_counters_account_too(self):
        self.assertTrue(self._step(
            self.FakePytest(ran="1745 passed, 2 skipped, 2 xfailed, 1 xpassed in 174s\n")))

    def test_a_collection_that_found_nothing_proves_nothing(self):
        self.assertFalse(self._step(self.FakePytest(collected="no tests ran in 0.1s\n")))

    def test_a_collection_that_failed_proves_nothing(self):
        self.assertFalse(self._step(self.FakePytest(collect_code=2)))

    def test_a_run_that_reports_no_passing_tests_proves_nothing(self):
        self.assertFalse(self._step(self.FakePytest(ran="no tests ran in 0.1s\n")))

    def test_more_passed_than_collected_is_not_a_failure(self):
        # Collection and the run can legitimately disagree upward; only downward is a loss.
        self.assertTrue(self._step(self.FakePytest(ran="1751 passed in 78s\n")))

    def test_the_counts_are_read_from_pytest_s_own_lines(self):
        self.assertEqual(1750, vr._count("1750 tests collected in 0.51s", r"(\d+) tests? collected"))
        self.assertEqual(1, vr._count("1 test collected in 0.1s", r"(\d+) tests? collected"))
        self.assertEqual(1750, vr._count("1750 passed, 1204 subtests passed", r"(\d+) passed"))
        self.assertEqual(0, vr._count("no tests ran in 0.1s", r"(\d+) passed"))


class TestTheRunnerIsLocked(unittest.TestCase):
    """The packages that decide this repository's verdict are pinned and hashed (#173, #344)."""

    @classmethod
    def setUpClass(cls):
        cls.text = open(os.path.join(ROOT, "tools", "requirements-dev.txt"), encoding="utf-8").read()

    def test_the_distributed_runner_is_in_the_locked_list(self):
        self.assertIn("pytest-xdist==", self.text)
        self.assertIn("execnet==", self.text)

    def test_every_pinned_package_carries_hashes(self):
        pinned = [line for line in self.text.splitlines()
                  if line and not line.startswith(("#", " ")) and "==" in line]
        self.assertGreaterEqual(len(pinned), 7)
        for line in pinned:
            with self.subTest(line=line):
                self.assertTrue(line.rstrip().endswith("\\"),
                                f"{line} names no hash continuation")


if __name__ == "__main__":
    unittest.main()
