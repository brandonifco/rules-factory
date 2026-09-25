#!/usr/bin/env python3
"""validate-repo.py's scope table, proved unable to skip a check by accident (#342).

Scoping a gate is how a gate stops examining things. Every test here is about the one direction
that matters: a rule that is wrong must run more, never less. So the cases are not "does this
path map to that scope" alone -- they are also "is there any tracked path in this repository for
which the answer is silently nothing", and "does --full still refuse to skip".

Run: python3 -m pytest tools/tests/test_validate_repo.py
"""
import importlib.util
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout

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
        # It is packable, and an engine is produced from a package: see
        # TestTheEngineJobIsOwedByWhatProducesAnEngine. This asserted False until #347.
        self.assertTrue(scope.engine)

    def test_a_shared_corpus_narrows_to_every_map_that_reads_it(self):
        # srd-52-conditions, srd-52-playing-the-game and srd-52-damage-and-healing all cite the
        # text committed under srd-52-combat. Deriving the affected map from the changed path
        # alone would check one of the four.
        scope = vr.classify(["examples/srd-52-combat/srd-5.2.1.txt"])
        self.assertEqual(
            ("examples/srd-52-combat/corpus-map.json",
             "examples/srd-52-conditions/corpus-map.json",
             "examples/srd-52-damage-and-healing/corpus-map.json",
             "examples/srd-52-playing-the-game/corpus-map.json"),
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
        # Trial 11's map is trial evidence with no `map-package.json`, so there is no version to
        # release. Three of the four SRD maps gained one with #446's composition work.
        with self.assertRaises(SystemExit):
            vr.release_scope("frcp-6-12-81")


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
    ADDED = (
        "every map has a row that names its corpora and its grammar",
        "every evidence artifact is the bytes the lock names",
    )

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


class TestBriefPrintsLessAndProvesTheSame(unittest.TestCase):
    """`--brief`: the same steps, the same verdicts, and a passing run that says what it examined
    rather than everything it did (#470).

    A successful run of this gate is 1167 lines and 157 KB, and an agent carries that in context
    for the rest of its life and pastes it into a pull request. Almost none of it is evidence
    anybody reads on a pass: the evidence is which steps ran and what each examined, which is the
    last line each step already prints.

    What must not move is anything else, so the tests are mostly about that: a failing step still
    prints the whole of what it printed, a `NOT VERIFIED` is counted rather than dropped, the
    verdicts and the exit code are the ones a full run gives, and the whole output is really kept
    where the run says it is.
    """

    def brief_run(self, steps):
        """Run `steps` through a brief `Run`, and give back what it printed and its log.

        File descriptor 1 and not `sys.stdout`: the thing under test captures fds, because most of
        what a real step prints comes from a subprocess, and a test that redirected `sys.stdout`
        would be testing a path the gate never takes.
        """
        handle, path = tempfile.mkstemp(prefix="validate-repo-test-", suffix=".log")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        run = vr.Run(vr.ROOT, vr.full_scope(), brief=pathlib.Path(path))
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
            sys.stdout.flush()
            saved, stream = os.dup(1), sys.stdout
            try:
                os.dup2(buffer.fileno(), 1)
                sys.stdout = open(1, "w", encoding="utf-8", closefd=False)
                for what, fn in steps:
                    run.run(what, fn)
                sys.stdout.flush()
            finally:
                sys.stdout = stream
                os.dup2(saved, 1)
                os.close(saved)
            buffer.seek(0)
            printed = buffer.read()
        return run, printed, open(path, encoding="utf-8").read()

    @staticmethod
    def noisy(lines, ok=True):
        def step():
            for line in lines:
                print(line)
            return ok
        return step

    def test_a_passing_step_prints_its_verdict_and_what_it_examined(self):
        run, printed, log = self.brief_run([
            ("every map satisfies the schema", self.noisy(
                ["[ok] one thing", "[ok] another thing", "10 map(s) checked"]))])
        self.assertIn("10 map(s) checked", printed, "the line that says the step examined something")
        self.assertIn("ok   every map satisfies the schema", printed)
        self.assertNotIn("[ok] another thing", printed, "and not every line the checkers printed")
        self.assertFalse(run.failed)

    def test_the_whole_of_it_is_in_the_log_the_run_names(self):
        _, printed, log = self.brief_run([("a step", self.noisy(["[ok] one thing", "2 things checked"]))])
        self.assertIn("[ok] one thing", log, "a claim that a raw log was kept, with nothing keeping it, "
                                             "would be worse than keeping none")
        self.assertIn("2 things checked", log)

    def test_a_failing_step_prints_everything_it_printed(self):
        run, printed, _ = self.brief_run([
            ("a step that fails", self.noisy(["the first clue", "the second clue"], ok=False))])
        self.assertIn("the first clue", printed, "a failure's output is the diagnosis")
        self.assertIn("the second clue", printed)
        self.assertIn("FAIL a step that fails", printed)
        self.assertTrue(run.failed)

    def test_a_not_verified_is_counted_rather_than_dropped(self):
        """A step that passed while examining nothing is the defect this repository has found in
        its own tools twice. Brief may make it quieter; it may not make it invisible."""
        _, printed, _ = self.brief_run([
            ("a step", self.noisy(["[skip] absent: NOT VERIFIED -- nothing to check",
                                   "[skip] bounds: NOT VERIFIED -- nothing to check",
                                   "3 map(s) checked"]))])
        self.assertIn("2 NOT VERIFIED in this step", printed)
        self.assertIn("validate-repo-test-", printed, "and where the two of them are named")

    def test_a_step_that_raises_is_still_a_failure_and_its_output_is_not_lost(self):
        def explodes():
            print("as far as it got")
            raise RuntimeError("the thing that went wrong")
        run, printed, log = self.brief_run([("a step that raises", explodes)])
        self.assertTrue(run.failed)
        self.assertIn("as far as it got", printed)
        self.assertIn("RuntimeError: the thing that went wrong", printed)

    def test_the_file_descriptors_come_back_afterwards(self):
        """The capture is fd 1 and 2, not `sys.stdout`, because most of what a step prints comes
        from a subprocess. A restore that only happened on the happy path would take the rest of
        the run's output with the first failing step."""
        run, printed, _ = self.brief_run([
            ("a step that raises", lambda: (_ for _ in ()).throw(RuntimeError("boom"))),
            ("a step after it", self.noisy(["1 thing checked"]))])
        self.assertIn("1 thing checked", printed)
        self.assertIn("ok   a step after it", printed)

    def test_the_verdicts_are_the_verdicts_a_loud_run_reaches(self):
        """The whole claim: `--brief` is about what a passing run prints, and nothing else.

        The same steps, run both ways, must give the same per-step verdict and the same `failed`.
        Asserted by running them rather than by reading the source: what matters is that the
        answer does not move, not where the branch is.
        """
        cases = [("one", self.noisy(["a", "2 checked"])),
                 ("two", self.noisy(["b"], ok=False)),
                 ("three", self.noisy(["c", "NOT VERIFIED -- nothing to check", "1 checked"]))]
        quiet, printed, _ = self.brief_run(cases)
        loud = vr.Run(vr.ROOT, vr.full_scope())
        seen = []
        for what, fn in cases:
            loud.run(what, fn)
            seen.append(loud.failed)
        self.assertEqual(loud.failed, quiet.failed)
        self.assertEqual(seen, [False, True, True], "the verdicts a loud run reaches")
        for what in ("one", "two", "three"):
            self.assertIn(what, printed, "every step still runs and still reports")

    def test_a_step_that_raises_still_has_its_output_in_the_log(self):
        """`_invoke` re-raises AssertionError on purpose -- that is how `--full skipped <step>`
        aborts a run -- and that is exactly when the step's output matters most (#481)."""
        handle, path = tempfile.mkstemp(prefix="validate-repo-test-", suffix=".log")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        run = vr.Run(vr.ROOT, vr.full_scope(), brief=pathlib.Path(path))

        def aborts():
            print("the diagnosis, printed before the abort")
            raise AssertionError("--full skipped a step")

        with self.assertRaises(AssertionError):
            run.run("a step that aborts the run", aborts)
        self.assertIn("the diagnosis, printed before the abort", open(path, encoding="utf-8").read(),
                      "the abort took the step's output with it")

    def test_a_flush_that_fails_does_not_stop_the_descriptors_coming_back(self):
        """Reproduced by the independent review as `fd operations [(900, 1), (900, 2)]` -- the two
        restores absent, so the rest of the run printed into a closed buffer."""
        handle, path = tempfile.mkstemp(prefix="validate-repo-test-", suffix=".log")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        run = vr.Run(vr.ROOT, vr.full_scope(), brief=pathlib.Path(path))

        class Hostile(io.StringIO):
            def flush(self):
                raise OSError("disk full on capture flush")

        # The streams this replaces are the ones `_invoke_captured` opens onto fds 1 and 2.
        import builtins
        opened = []
        real_open = builtins.open

        def fake_open(target, *args, **kwargs):
            if target == 1 or target == 2:
                stream = Hostile()
                opened.append(stream)
                return stream
            return real_open(target, *args, **kwargs)

        before = os.fstat(1).st_ino, os.fstat(2).st_ino
        with unittest.mock.patch("builtins.open", side_effect=fake_open):
            run.run("a step whose flush fails", lambda: True)
        self.assertEqual((os.fstat(1).st_ino, os.fstat(2).st_ino), before,
                         "the descriptors were not restored, so the rest of the run prints nowhere")
        self.assertTrue(opened, "the test did not exercise the stream it meant to")

    def test_a_temporary_directory_inside_the_checkout_is_refused(self):
        """The gate's last step fails on any file a run adds to the checkout, so a log written
        there would fail the gate it belongs to -- a refusal nobody could act on (#481)."""
        inside = os.path.join(ROOT, ".brief-tmp-for-a-test")
        os.makedirs(inside, exist_ok=True)
        self.addCleanup(lambda: os.path.isdir(inside) and os.rmdir(inside))
        with unittest.mock.patch.object(vr.tempfile, "gettempdir", return_value=inside):
            with self.assertRaises(SystemExit) as refused:
                vr.brief_log()
        self.assertIn("inside the checkout", str(refused.exception))
        self.assertIn("$TMPDIR", str(refused.exception))
        self.assertEqual(os.listdir(inside), [], "a refused run wrote a log anyway")

    def test_the_log_is_written_outside_the_checkout(self):
        """The gate's last step fails on a file this run added to the checkout, and a gate that
        failed because of its own log would be a useless gate.

        The path is asked for directly rather than by running the gate: this test lives inside the
        suite the gate's own tool-tests step runs, so a test that invoked the gate would invoke
        the suite that invokes the gate.
        """
        path = vr.brief_log()
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        self.assertTrue(os.path.isfile(path), "the log is created, not merely named")
        self.assertFalse(str(path).startswith(str(ROOT) + os.sep),
                         f"the brief log {path} is inside the checkout")

    def test_explain_with_brief_runs_nothing_and_opens_no_log(self):
        """`--explain` returns before any step, so there is nothing for a log to hold."""
        proc = subprocess.run([sys.executable, TOOL, "--explain", "--brief", "--changed",
                               "--base", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertNotIn("==> [1]", proc.stdout)
        self.assertNotIn("validate-repo-", proc.stdout)


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


class TestTheEngineJobIsOwedByWhatProducesAnEngine(unittest.TestCase):
    """`Scope.engine` says whether an engine produced from scratch is owed (#347).

    #342 set it for `tools/factory/` only. An engine is produced from a packable map, so that was
    wrong in the direction that matters: a map change would have told a workflow the engine job
    could be skipped.
    """

    @classmethod
    def setUpClass(cls):
        cls.engine_source = open(os.path.join(ROOT, "tools", "validate-engine.py"),
                                 encoding="utf-8").read()

    def test_the_engine_is_owed_by_the_map_it_is_produced_from(self):
        # The claim in validate-repo.py, held to the file that makes it true rather than trusted.
        self.assertIn(f'MAP_DIR = "{vr.ENGINE_MAP}"', self.engine_source)

    def test_the_engine_reads_every_packable_map(self):
        # Which is why every packable map owes it, not only the one it produces from.
        self.assertIn('glob.glob("examples/*/map-package.json")', self.engine_source)

    def test_a_change_to_the_produced_map_owes_an_engine(self):
        scope = vr.classify([f"{vr.ENGINE_MAP}/corpus-map.json"])
        self.assertEqual("changed", scope.name)
        self.assertTrue(scope.engine)

    def test_a_change_to_any_packable_map_owes_an_engine(self):
        for settings in vr.discover(vr.ROOT, vr.PACKAGE_GLOB):
            with self.subTest(package=settings):
                scope = vr.classify([os.path.join(os.path.dirname(settings), "corpus-map.json")])
                self.assertTrue(scope.engine, settings)

    def test_a_map_that_is_not_packable_owes_no_engine(self):
        # frcp-6-12-81 declares no map-package.json, so no engine is produced from it.
        scope = vr.classify(["examples/frcp-6-12-81/corpus-map.json"])
        self.assertEqual(("examples/frcp-6-12-81/corpus-map.json",), scope.maps)
        self.assertEqual((), scope.packages)
        self.assertFalse(scope.engine)

    def test_full_and_release_always_owe_an_engine(self):
        self.assertTrue(vr.full_scope().engine)
        self.assertTrue(vr.release_scope("hoyle-backgammon").engine)


class TestTheEvidenceStepAsksTheRightVerifier(unittest.TestCase):
    """--with-evidence verifies the artifacts wherever the lock says they live (#349).

    The step stands down when EVIDENCE_MEASURING is set, because a measurement is rewriting the
    lock it reads and a failing step changes what the run opens (#408). These clear that rather
    than stand down with it: what they hold is the ordinary behaviour, and it has to keep being
    held during a measurement too -- a step that stood down for every caller would be a step
    nobody is running, which is the shape this repository keeps finding.
    """

    def setUp(self):
        self._measuring = os.environ.pop("EVIDENCE_MEASURING", None)

    def tearDown(self):
        if self._measuring is not None:
            os.environ["EVIDENCE_MEASURING"] = self._measuring

    def test_the_step_stands_down_for_a_measurement_and_says_so(self):
        """The other half, asserted here rather than left to the measurement to discover."""
        os.environ["EVIDENCE_MEASURING"] = "1"
        try:
            run = vr.Run(vr.ROOT, vr.full_scope())
            run.python = lambda *argv, **kw: self.fail(f"the step ran {argv} while measuring")
            printed = io.StringIO()
            with redirect_stdout(printed):
                self.assertTrue(vr.step_evidence(run))
            self.assertIn("not run:", printed.getvalue())
        finally:
            os.environ.pop("EVIDENCE_MEASURING")

    def _argv(self, with_evidence):
        run = vr.Run(vr.ROOT, vr.full_scope(), with_evidence=with_evidence)
        seen = []
        run.python = lambda *argv, **kw: seen.append(argv) or True
        self.assertTrue(vr.step_evidence(run))
        return seen[0]

    def test_without_it_the_checkout_is_verified_in_place(self):
        self.assertEqual(("tools/check-evidence.py",), self._argv(False))

    def test_with_it_the_fetching_verifier_runs_instead(self):
        self.assertEqual(("tools/fetch-evidence.py", "--verify"), self._argv(True))

    def test_it_is_off_unless_asked_for(self):
        self.assertFalse(vr.Run(vr.ROOT, vr.full_scope()).with_evidence)

    def test_the_evidence_step_runs_at_every_scope(self):
        # It holds a fact about the tree, not about the change, and takes 40ms over 15.5 MB.
        for scope in (vr.full_scope(), vr.classify(["tools/factory/generate.py"]),
                      vr.release_scope("hoyle-backgammon")):
            with self.subTest(scope=scope.name):
                run = vr.Run(vr.ROOT, scope)
                seen = []
                run.python = lambda *argv, **kw: seen.append(argv) or True
                self.assertTrue(vr.step_evidence(run))
                self.assertEqual([("tools/check-evidence.py",)], seen)


class TestTheNetworkStepRunsWhereItsSubjectChanges(unittest.TestCase):
    """check-status-issues.py reads GitHub, and asks about the README, not about code (#347)."""

    def test_it_runs_under_full(self):
        run = vr.Run(vr.ROOT, vr.full_scope())
        with self.assertRaises(AssertionError):
            # Under --full the step may not skip at all; that it tries is the bug this catches.
            run.skip("reading GitHub for the state of the issues the README cites")

    def test_it_does_not_run_under_a_changed_scope(self):
        # Asserting only that the step passed would be satisfied by it running and succeeding,
        # which is what it does on a healthy README. What it must do is say it did not run.
        scope = vr.classify(["tools/factory/generate.py"])
        run = vr.Run(vr.ROOT, scope)
        printed = io.StringIO()
        with redirect_stdout(printed):
            self.assertTrue(vr.step_status_issues(run))
        self.assertIn("not owed by this change", printed.getvalue())
        self.assertNotIn("NOT CHECKED", printed.getvalue())
        self.assertFalse(run.failed)

    def test_a_readme_change_widens_to_full_so_it_is_still_reached(self):
        # The case the step exists for: prose that cites an issue as open. No rule places
        # README.md, so the diff widens and the step runs.
        self.assertEqual("full", vr.classify(["README.md"]).name)

    def test_the_parser_half_keeps_running_at_every_scope(self):
        # check-readme-status.py needs no network and a code change is what moves it.
        run = vr.Run(vr.ROOT, vr.classify(["tools/factory/generate.py"]))
        self.assertTrue(vr.step_readme_status(run))


if __name__ == "__main__":
    unittest.main()


class TestAnUndeclaredPointerIsNotNotVerified(unittest.TestCase):
    """The pointers step stopped accepting exit 3 when 0058 answered #254.

    While that question was open -- whether a `scope: out`, `status: declined` entry owed a
    `crossReferences` declaration -- `mapper pointers` was right to report NOT VERIFIED and the
    gate was right to accept it. 0058 answers it: the passage that points declares it, whatever
    the engine does with the rule. So a naming the map leaves undeclared is a defect the gate
    names, and the accept set is the one line that says so.

    Watched failing with `accept=(0, 3)` restored in `step_pointers`: the exit-3 case passes and
    this test reports the step accepting NOT VERIFIED.
    """

    class _Recorded:
        """A Run that runs nothing and reports one exit code, recording the accept set it got."""

        def __init__(self, root, scope, code):
            self.root, self.scope, self.code = root, scope, code
            self.accepted = []

        def python(self, *argv, accept=(0,)):
            self.accepted.append(tuple(accept))
            return self.code in accept

    def _step(self, code):
        scope = vr.full_scope()
        run = self._Recorded(vr.ROOT, scope, code)
        with redirect_stdout(io.StringIO()):
            return vr.step_pointers(run), run

    def test_exit_3_now_fails_the_step(self):
        passed, run = self._step(3)
        self.assertFalse(passed, "the gate accepted NOT VERIFIED on an undeclared pointer")
        self.assertNotIn(3, run.accepted[0], "3 is still in the step's accept set")

    def test_exit_0_still_passes_the_step(self):
        passed, _ = self._step(0)
        self.assertTrue(passed)

    def test_exit_1_still_fails_the_step(self):
        passed, _ = self._step(1)
        self.assertFalse(passed)

    def test_every_committed_map_exits_0_so_the_tightening_is_not_theoretical(self):
        """The tightening is only safe because no map on disk needs the 3.

        Seven maps: five declare no mechanism this detects and exit 0 having examined nothing of
        this kind, `hazmat-172-table` declares `coded-pointer` and has every naming declared, and
        `srd-52-conditions` is the one 0058 corrected.
        """
        run = vr.Run(vr.ROOT, vr.full_scope())
        for map_path in run.scope.maps:
            proc = run.quiet("tools/mapper", "pointers", map_path)
            self.assertEqual(proc.returncode, 0,
                             f"{map_path} exits {proc.returncode}:\n{proc.stdout}{proc.stderr}")


class TestNoBytecodeReachesTheCheckout(unittest.TestCase):
    """#384: the step that catches what a run left behind could not see bytecode.

    `main()` used to export PYTHONDONTWRITEBYTECODE for every child before the first step, so a
    checker that writes bytecode wrote none under the gate and wrote it in every other caller's
    checkout. AGENTS.md section 4's promise -- "nothing is left in the checkout" -- was being kept
    by the caller's environment rather than by the tools, which is keeping it by accident.

    So the flag is a property of each tool that imports another of this repository's files by
    path, and the gate sets it only for pytest, whose xdist workers are child processes that
    inherit the environment and nothing else. Both halves are asserted here: the tools say it,
    and the gate does not say it for them.
    """

    IMPORT = ("sys.path.insert", "spec_from_file_location")
    SUPPRESSION = "sys.dont_write_bytecode = True"

    # The imported side. A module with no `__main__` guard is never the process that starts, so
    # its own bytecode is written by whoever imported it and a flag here would be read one file
    # too late -- the carve-out test_factory_rails.py already makes for the vendored modules.
    # Named rather than inferred, so a module that grows an entry point is not quietly exempt.
    IMPORTED_SIDE = ("tools/factory/intake.py",)

    def path_importers(self):
        """Every script run as a command, under tools/ or examples/, that loads another
        repository file by path.

        Both mechanisms, because they have the same consequence and only one of them was
        enumerated before: `tools/factory`'s importers were held to this rule by
        test_factory_provenance.py through `sys.path`, and the SRD locator checker -- which
        reaches for tools/check-locators.py through importlib, from examples/ -- was in neither
        list. tools/mapper/__main__.py was in neither either, and the gate caught it the first
        time the last step could see bytecode.

        tools/tests/ is left out because pytest imports those modules and the gate sets
        PYTHONDONTWRITEBYTECODE for pytest alone: there the environment is the tool's own, not a
        caller's.
        """
        import glob
        found = {}
        for pattern in ("tools/*.py", "tools/*/*.py", "tools/*/*/*.py", "examples/*/*.py"):
            for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
                relative = os.path.relpath(path, ROOT).replace(os.sep, "/")
                if relative.startswith("tools/tests/") or relative in self.IMPORTED_SIDE:
                    continue
                lines = open(path, encoding="utf-8").read().splitlines()
                reaches = next((i for i, line in enumerate(lines)
                                if any(m in line for m in self.IMPORT)
                                and not line.lstrip().startswith("#")), None)
                if reaches is not None:
                    found[relative] = (lines, reaches)
        return found

    def test_the_imported_side_is_still_the_imported_side(self):
        """The exemption is a fact about the file, not a way past the rule: a module that gains
        an entry point starts writing its own bytecode and owes the flag."""
        for relative in self.IMPORTED_SIDE:
            with self.subTest(module=relative):
                text = open(os.path.join(ROOT, relative), encoding="utf-8").read()
                self.assertNotIn('if __name__ == "__main__"', text,
                                 f"{relative} is exempt as the imported side and now runs as a "
                                 f"command (#384)")

    def test_every_script_that_imports_by_path_suppresses_its_bytecode(self):
        for relative, (lines, reaches) in sorted(self.path_importers().items()):
            with self.subTest(script=relative):
                # Column 0, so the flag is module level rather than nested in some function that
                # may never run, and before the import, because the loader reads it then.
                flag = next((i for i, line in enumerate(lines)
                             if line.split("#")[0].rstrip() == self.SUPPRESSION), None)
                self.assertIsNotNone(
                    flag, f"{relative} imports another repository file by path and leaves its "
                          f"bytecode in the checkout (#384)")
                self.assertLess(
                    flag, reaches,
                    f"{relative} sets dont_write_bytecode at line {flag + 1}, after line "
                    f"{reaches + 1} reaches for the import; there it prevents nothing")

    def test_the_importers_are_named(self):
        """Named, so a new script that starts importing by path fails here rather than being
        waved through by a check that examined whatever it happened to find."""
        self.assertEqual(sorted(self.path_importers()), [
            "examples/blind-mapping-trial/compare.py",
            "examples/collapse-trial/collapse.py",
            "examples/hoyle-blind-rebuild/build-brief.py",
            "examples/hoyle-blind-rebuild/check-rebuild.py",
            "examples/injection-trial/run-trial.py",
            "examples/injection-trial/score.py",
            "examples/srd-52-combat/check-locators-pdf-text.py",
            "tools/check-readme-status.py",
            "tools/factory/__main__.py",
            "tools/factory/recipe/engine-gate.py",
            "tools/factory/recipe/map-overlay.py",
            "tools/fetch-evidence.py",
            "tools/mapper/__main__.py",
            "tools/pack-map.py",
            "tools/validate-engine.py",
        ])

    def test_the_gate_does_not_suppress_bytecode_for_every_step(self):
        """The structural half. A gate that exports the flag for all its children cannot fail on
        bytecode, so the last step reports ok over a tree the same run would have dirtied in any
        other environment."""
        source = open(TOOL, encoding="utf-8").read()
        body = source.split("def main(")[1]
        self.assertNotIn('os.environ["PYTHONDONTWRITEBYTECODE"]', body,
                         "main() exports the flag for every child again, and the last step is "
                         "blind to bytecode once more (#384)")

    def test_the_pytest_step_still_suppresses_its_own(self):
        """The one step that needs the environment: pytest imports every test module, and xdist's
        workers are separate processes that inherit env and no interpreter flag."""
        step = open(TOOL, encoding="utf-8").read().split("def step_tool_tests(")[1].split("\ndef ")[0]
        self.assertIn('"PYTHONDONTWRITEBYTECODE": "1"', step)
        self.assertEqual(2, step.count("env=bare"), "both the collection and the run")

    def wrote_bytecode(self, argv):
        """Whether running `argv` writes any bytecode, measured in a directory of its own.

        Not by looking at the checkout: the suite is distributed (`-n auto`), so another worker
        is writing there while this one measures, and a test that compared paths in a shared tree
        fails on files it has nothing to do with. `PYTHONPYCACHEPREFIX` sends every `.pyc` this
        process would write into a private temporary tree instead, so what is measured is this
        process's own behaviour and nothing else's -- and the checkout is not touched either way.

        The environment is otherwise the one a reader following the tool's own usage line has:
        PYTHONDONTWRITEBYTECODE unset, so what is proved is the tool's own
        `sys.dont_write_bytecode` rather than the caller's habits (#384).
        """
        with tempfile.TemporaryDirectory() as prefix:
            env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
            env["PYTHONPYCACHEPREFIX"] = prefix
            proc = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True)
            # The prefix tree mirrors absolute paths, so the standard library's own bytecode
            # lands there too when the interpreter's copy is not already cached. Only this
            # repository's modules are the subject: a tool cannot suppress the stdlib's caching
            # and is not asked to.
            inside = os.path.join(prefix, ROOT.lstrip(os.sep))
            written = [os.path.relpath(os.path.join(base, name), inside)
                       for base, _, names in os.walk(inside) for name in names]
        return proc, sorted(written)

    def test_a_path_importer_run_bare_leaves_nothing(self):
        """The acceptance criterion itself, on the cheapest importer: run it the way its own
        usage line describes, with nothing exported, and it writes no bytecode."""
        proc, written = self.wrote_bytecode(
            [sys.executable, os.path.join(ROOT, "tools", "fetch-evidence.py"), "--help"])
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual([], written,
                         "running a path importer bare wrote bytecode for the modules it imported")

    def test_the_gate_runs_the_mapper_as_a_file_and_not_as_a_directory(self):
        """Executing a directory imports `__main__` and caches it before the file's own
        `sys.dont_write_bytecode` can run, so the one entry point that cannot protect itself is
        invoked the one way that needs no protection (#384)."""
        self.assertEqual("tools/mapper/__main__.py", vr.MAPPER)
        source = open(TOOL, encoding="utf-8").read()
        self.assertNotIn('run.python("tools/mapper"', source,
                         "the gate executes the mapper as a directory again, which caches "
                         "tools/mapper/__pycache__/__main__.cpython-*.pyc whatever the file says")

    def test_the_mapper_run_as_a_file_leaves_nothing(self):
        """The behavioural half, with nothing exported: the form the gate uses is clean.

        What the gate's own first sighted run found it leaving was tools/mapper/__pycache__ and
        tools/mapcontract/__pycache__; here neither is written at all."""
        proc, written = self.wrote_bytecode(
            [sys.executable, os.path.join(ROOT, vr.MAPPER), "protocol",
             os.path.join(ROOT, "examples", "faa-part-107", "corpus-map.json")])
        self.assertEqual(0, proc.returncode, proc.stderr[-2000:])
        self.assertEqual([], written, "the mapper run as a file wrote bytecode for mapper.cli "
                                      "and mapcontract")


class TestTheSkipsAreNotExplainedByAStaleComment(unittest.TestCase):
    """#389: the gate's accounting was right about the number and wrong about the cause.

    `validate-repo.py` held the suite to its collected count and explained the two skips with
    "this job has no .NET SDK, so the tests that need one skip here". ubuntu-24.04 ships a 10.x
    SDK, so the `validate` runner has one and those ten tests have been *running* there. A count
    accepted on the strength of a comment is a count nobody is checking, which is the shape of
    defect this repository keeps finding in its own tools.

    The fix is not a better comment. It is that every skip prints its own reason, so a green log
    says which tests did not run and why.
    """

    FALSE_CLAIM = ("this repository's CI has none", "as in this repository's CI")

    def test_the_run_prints_every_skip_reason(self):
        step = open(TOOL, encoding="utf-8").read().split("def step_tool_tests(")[1].split("\ndef ")[0]
        self.assertIn('"-rs"', step,
                      "without -rs a skip is a number with no reason attached, and the reason "
                      "goes back into a comment that can drift (#389)")

    def test_no_test_claims_this_repository_has_no_sdk(self):
        """The claim is false wherever it appears: as a skip reason a reader sees in a log, or as
        a docstring a reader believes instead of reading the runner."""
        import glob
        for path in sorted(glob.glob(os.path.join(ROOT, "tools", "tests", "factory", "*.py"))):
            text = open(path, encoding="utf-8").read()
            for claim in self.FALSE_CLAIM:
                with self.subTest(file=os.path.basename(path), claim=claim):
                    # The corrected docstring names the claim to say it is false, so what is
                    # refused is the assertion, not the words.
                    offending = [line.strip() for line in text.splitlines()
                                 if claim in line and "*not*" not in line]
                    self.assertEqual([], offending,
                                     f"{os.path.basename(path)} says the validate runner has no "
                                     f".NET SDK; it has a 10.x one and these tests run there (#389)")

    def test_the_two_questions_about_an_sdk_are_asked_separately(self):
        """An SDK is present, and the SDK this engine pins is present, have different
        consequences: a build against a non-pinned 10.x with `rollForward: disable` exits 155.
        A guard that conflates them measures a fallback path and reports it as the real one."""
        factory = os.path.join(ROOT, "tools", "tests", "factory")
        gate = open(os.path.join(factory, "test_factory_gate.py"), encoding="utf-8").read()
        provenance = open(os.path.join(factory, "test_factory_provenance.py"), encoding="utf-8").read()
        # Any 10.x, because the class re-pins each localised engine's global.json to it.
        self.assertIn("def _sdk()", gate)
        self.assertIn('re.match(r"^10\\.", version)', gate)
        # The other question, where no re-pin happens: the exact pinned version or nothing.
        self.assertIn("--list-sdks", provenance,
                      "nothing asks whether the SDK the kernel pins is the one installed (#389)")
        self.assertIn("pins.SDK_VERSION", provenance)
