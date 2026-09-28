#!/usr/bin/env python3
"""A produced engine's rails are where GitHub runs them, wherever the engine is (#501, 0069).

GitHub reads a workflow only from `.github/workflows/` at the **root** of a repository, and a pull
request template only from the root. Every engine the factory had produced was its own repository
root, so nobody had asked what happens to an engine produced into a subdirectory of a larger
repository: the answer was four workflows and a template written under the engine, where nothing
would ever read them, recorded in `provenance.json` as generated and reported by the rails doctor
as present. The gate, the pull request policy, the conformance gate and the verdict requeue were
all dark, and no check anywhere said so.

What is tested here, in the order it matters:

  * a standalone engine is byte-identical to what it always was -- the same four workflows at the
    same paths, from the same recipes;
  * an `--out` under a repository root is **refused** until it says which root it is in, so no
    engine is ever produced with dark rails by omission;
  * an embedded engine's rails are at the repository root, run in the engine, and are not under
    the engine at all;
  * regeneration writes one copy and no second implementation;
  * an engine produced before this -- the migration -- loses the inert copies it carried;
  * a repository's own file at one of those paths is never overwritten silently;
  * and `assure_active`, the invariant as code: a run that writes a workflow writes one where
    GitHub will run it. That last is the regression test for the bug itself.

The repository fixtures are `git init` in a temporary directory. Nothing here needs a .NET SDK:
every produce is `--no-verify`.

Run: python3 -m unittest discover -s tools/tests -t tools
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
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")
PART107 = os.path.join(REPO, "examples", "faa-part-107")
PART107_XML = os.path.join(PART107, "part107.xml")
NAME = "FaaPart107"

_spec = importlib.util.spec_from_file_location("factory_main_repository", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
import ownership  # noqa: E402  (tools/factory is on sys.path now)
import repository  # noqa: E402

WORKFLOWS = repository.WORKFLOWS
TEMPLATE = repository.TEMPLATE
FILES = repository.FILES


def git(where, *args):
    subprocess.run(["git", "-C", where, *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def init(where):
    """A git repository at `where`: what makes a directory a root, and the only thing that does."""
    os.makedirs(where, exist_ok=True)
    git(where, "init", "-q")
    return where


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


class RepositoryCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        subprocess.run([sys.executable, PACK, PART107, "--out", os.path.join(cls.shared, "feed")], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        feed = os.path.join(cls.shared, "feed")
        (name,) = [n for n in os.listdir(feed) if n.endswith(".nupkg")]
        cls.nupkg = os.path.join(feed, name)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def produce(self, out, *extra, expect=None):
        """`factory produce --no-verify` into `out`; the output, and the exit code checked."""
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["produce", "--package", self.nupkg, "--corpus", PART107_XML,
                                 "--name", NAME, "--out", out, "--allow-dirty", "--no-verify", *extra])
        wanted = factory.NOT_VERIFIED if expect is None else expect
        if code != wanted:
            raise AssertionError(f"produce exited {code}, not {wanted}\n{buffer.getvalue()}")
        return buffer.getvalue()

    def record(self, engine):
        with open(os.path.join(engine, "provenance.json"), encoding="utf-8") as handle:
            return json.load(handle)


class TestStandaloneIsUnchanged(RepositoryCase):
    """An engine that is its own repository root produces exactly what it always did."""

    def test_the_four_workflows_and_the_template_are_the_engine_s_own_recipe_bytes(self):
        engine = os.path.join(self.tmp, "engine")
        self.produce(engine)
        recipes = repository.recipes(NAME)
        for relative in FILES:
            path = os.path.join(engine, *relative.split("/"))
            self.assertTrue(os.path.isfile(path), f"{relative} is the engine's own file when it is the root")
            self.assertEqual(recipes[relative].encode("utf-8"), read(path),
                             f"{relative} is the recipe, byte for byte: a standalone engine is not rendered")

    def test_the_record_says_the_engine_is_its_own_repository_root(self):
        engine = os.path.join(self.tmp, "engine")
        self.produce(engine)
        section = self.record(engine)["repository"]
        self.assertIsNone(section["enginePath"], "null, not a path: the engine is the root")
        self.assertEqual([], section["automation"], "a standalone engine's root holds nothing of its own")

    def test_an_out_that_is_a_repository_root_needs_no_declaration(self):
        engine = init(os.path.join(self.tmp, "engine"))
        self.produce(engine)
        self.assertTrue(os.path.isfile(os.path.join(engine, *WORKFLOWS[0].split("/"))))
        self.assertIsNone(self.record(engine)["repository"]["enginePath"])

    def test_repo_root_equal_to_out_declares_the_engine_its_own_root_inside_another_checkout(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", engine)
        self.assertTrue(os.path.isfile(os.path.join(engine, *WORKFLOWS[0].split("/"))))
        self.assertFalse(os.path.exists(os.path.join(host, ".github")),
                         "a declared root of its own writes nothing into the checkout above it")


class TestAnEmbeddedEngineIsRefusedUndeclared(RepositoryCase):
    """The bug's first line of defence: nothing is produced with rails GitHub cannot run."""

    def test_an_out_under_a_repository_root_is_refused_and_nothing_is_written(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        output = self.produce(engine, expect=1)
        self.assertIn("is not the root of its repository", output)
        self.assertIn("--repo-root", output)
        self.assertIn(host, output)
        self.assertFalse(os.path.exists(engine), "a refusal produces nothing")

    def test_the_refusal_names_both_answers(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "products", "engine")
        output = self.produce(engine, expect=1)
        self.assertIn(f"--repo-root {host}", output)
        self.assertIn(f"--repo-root {engine}", output)
        self.assertIn("products/engine", output)

    def test_a_repo_root_that_is_not_a_repository_root_is_refused(self):
        host = init(os.path.join(self.tmp, "host"))
        middle = os.path.join(host, "middle")
        engine = os.path.join(middle, "engine")
        os.makedirs(engine)
        output = self.produce(engine, "--repo-root", middle, expect=1)
        self.assertIn("is not a repository root", output)

    def test_a_repo_root_that_does_not_contain_out_is_refused(self):
        host = init(os.path.join(self.tmp, "host"))
        elsewhere = os.path.join(self.tmp, "elsewhere", "engine")
        output = self.produce(elsewhere, "--repo-root", host, expect=1)
        self.assertIn("does not contain --out", output)


class TestAnEmbeddedEngineTakesItsRailsFromTheRoot(RepositoryCase):
    def embedded(self, path="engine"):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, *path.split("/"))
        output = self.produce(engine, "--repo-root", host)
        return host, engine, output

    def test_the_rails_are_at_the_repository_root_and_not_under_the_engine(self):
        host, engine, _ = self.embedded()
        for relative in FILES:
            self.assertTrue(os.path.isfile(os.path.join(host, *relative.split("/"))),
                            f"{relative} is at the repository root, where GitHub reads it")
            self.assertFalse(os.path.exists(os.path.join(engine, *relative.split("/"))),
                             f"{relative} is not under the engine: a copy there would be inert")
        self.assertFalse(os.path.isdir(os.path.join(engine, ".github", "workflows")),
                         "not even an empty directory is left to read as rails")
        self.assertTrue(os.path.isfile(os.path.join(engine, ".github", "agent-policy.json")),
                        "the engine keeps what its own scripts read by path; GitHub never looks at it")

    def test_every_run_step_executes_in_the_engine(self):
        host, _engine, _ = self.embedded()
        for relative in WORKFLOWS:
            text = read(os.path.join(host, *relative.split("/"))).decode("utf-8")
            self.assertIn("    defaults:\n      run:\n        working-directory: engine\n", text, relative)
            self.assertLess(text.index("working-directory: engine"), text.index("    runs-on:"),
                            "the job's working directory is set on the job, above the runner")
        gate = read(os.path.join(host, *WORKFLOWS[0].split("/"))).decode("utf-8")
        self.assertIn("run: ./scripts/validate.sh full", gate,
                      "the command is the engine's own and is not rewritten: the working directory carries it")
        self.assertIn('scripts/engine-gate.py repository --root "$GITHUB_WORKSPACE"', gate,
                      "the root's copies are held to the engine's record by the engine's own gate")

    def test_a_deeper_engine_path_is_rendered_with_that_path(self):
        host, _engine, _ = self.embedded("products/engine")
        text = read(os.path.join(host, *WORKFLOWS[1].split("/"))).decode("utf-8")
        self.assertIn("working-directory: products/engine", text)
        self.assertIn("run: python3 tools/pr-policy.py", text, "the command stays the engine's")

    def test_the_private_distribution_guardrail_is_carried_to_the_root_unchanged(self):
        """0068's refusal is a step of the gate workflow, and moving the file must not weaken it."""
        host, _engine, _ = self.embedded()
        recipe = repository.recipes(NAME)[WORKFLOWS[0]]
        start = recipe.index("      - name: Refuse a private engine in a public repository")
        end = recipe.index("      - name: Read the pinned SDK version")
        guardrail = recipe[start:end]
        self.assertIn("::error::provenance.json records distribution private", guardrail)
        text = read(os.path.join(host, *WORKFLOWS[0].split("/"))).decode("utf-8")
        self.assertIn(guardrail, text, "the guardrail step is at the root byte for byte")
        self.assertIn('json.load(open("provenance.json"))', text)
        self.assertLess(text.index("working-directory: engine"), text.index(guardrail),
                        "and it reads the engine's provenance.json, because the job runs there")

    def test_the_pull_request_template_says_which_directory_its_paths_are_in(self):
        host, _engine, _ = self.embedded()
        text = read(os.path.join(host, *TEMPLATE.split("/"))).decode("utf-8")
        self.assertIn("every path named below is relative to `engine/`", text)
        self.assertIn(repository.recipes(NAME)[TEMPLATE], text, "the contract itself is unchanged")

    def test_the_record_names_the_engine_path_and_hashes_what_the_root_holds(self):
        host, engine, _ = self.embedded()
        section = self.record(engine)["repository"]
        self.assertEqual("engine", section["enginePath"])
        self.assertEqual(sorted(FILES), sorted(item["path"] for item in section["automation"]))
        for item in section["automation"]:
            self.assertEqual(repository._sha256(read(os.path.join(host, *item["path"].split("/")))),
                             item["sha256"], f"{item['path']}: the record hashes the bytes at the root")

    def test_the_run_says_where_the_rails_went(self):
        host, _engine, output = self.embedded()
        self.assertIn("the engine is embedded at engine/", output)
        self.assertIn("GitHub reads them only from the repository root", output)

    def test_provenance_recomputes_for_an_embedded_engine(self):
        _host, engine, _ = self.embedded()
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            mismatches = factory.recompute_provenance(engine, self.nupkg)
        self.assertEqual([], mismatches, buffer.getvalue())


class TestRegenerationKeepsOneCopy(RepositoryCase):
    def test_producing_twice_writes_the_same_one_copy(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        first = {relative: read(os.path.join(host, *relative.split("/"))) for relative in FILES}
        self.produce(engine, "--repo-root", host)
        for relative, data in first.items():
            self.assertEqual(data, read(os.path.join(host, *relative.split("/"))), relative)
            self.assertFalse(os.path.exists(os.path.join(engine, *relative.split("/"))),
                             f"a second produce did not grow a second {relative} under the engine")

    def test_a_hand_edit_at_the_root_is_overwritten_by_the_next_produce(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        path = os.path.join(host, *WORKFLOWS[0].split("/"))
        recipe_bytes = read(path)
        with open(path, "ab") as handle:
            handle.write(b"\n# tweaked by hand\n")
        self.produce(engine, "--repo-root", host)
        self.assertEqual(recipe_bytes, read(path),
                         "generated, not managed: the root's copy is rewritten from the recipe every run")

    def test_the_repository_table_classifies_every_file_the_factory_writes_at_a_root(self):
        for relative in FILES:
            self.assertIsNotNone(ownership.classify_repository(relative),
                                 f"{relative} is written at a repository root and must have one owner")
        self.assertIsNone(ownership.classify_repository(".github/workflows/something-else.yml"),
                          "a repository's own workflow is not the factory's")


class TestMigratingAnEngineThatCarriedInertRails(RepositoryCase):
    """The repair path for an engine produced before 0069 under a host repository."""

    def migrated(self):
        standalone = os.path.join(self.tmp, "engine")
        self.produce(standalone)
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        shutil.move(standalone, engine)
        return host, engine

    def test_the_inert_copies_are_removed_and_the_root_gets_them(self):
        host, engine = self.migrated()
        for relative in FILES:
            self.assertTrue(os.path.isfile(os.path.join(engine, *relative.split("/"))))
        output = self.produce(engine, "--repo-root", host)
        for relative in FILES:
            self.assertFalse(os.path.exists(os.path.join(engine, *relative.split("/"))),
                             f"{relative}: the inert copy is gone")
            self.assertTrue(os.path.isfile(os.path.join(host, *relative.split("/"))),
                            f"{relative}: the repository root holds it now")
            self.assertIn(f"removed {relative}", output)

    def test_a_workflow_the_factory_did_not_write_is_kept_and_named(self):
        host, engine = self.migrated()
        mine = os.path.join(engine, ".github", "workflows", "mine.yml")
        with open(mine, "w", encoding="utf-8") as handle:
            handle.write("name: mine\n")
        output = self.produce(engine, "--repo-root", host)
        self.assertTrue(os.path.isfile(mine), "somebody else's file is not the factory's to delete")
        self.assertIn("WARNING .github/workflows/mine.yml", output)
        self.assertIn("GitHub reads no workflow below the repository root", output)

    def test_an_edited_rail_is_kept_and_named_rather_than_deleted(self):
        host, engine = self.migrated()
        edited = os.path.join(engine, *WORKFLOWS[2].split("/"))
        with open(edited, "ab") as handle:
            handle.write(b"\n# somebody's change\n")
        output = self.produce(engine, "--repo-root", host)
        self.assertTrue(os.path.isfile(edited), "an edit nobody has seen is not deleted")
        self.assertIn(f"WARNING {WORKFLOWS[2]}", output)
        self.assertIn("not the ones the engine's record hashed", output)


class TestARepositorysOwnFileIsNotOverwritten(RepositoryCase):
    def test_a_workflow_the_repository_kept_by_hand_refuses_the_run(self):
        host = init(os.path.join(self.tmp, "host"))
        os.makedirs(os.path.join(host, ".github", "workflows"))
        path = os.path.join(host, *WORKFLOWS[0].split("/"))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("name: validate\n# this repository's own\n")
        engine = os.path.join(host, "engine")
        output = self.produce(engine, "--repo-root", host, expect=1)
        self.assertIn("is not a file this factory wrote", output)
        self.assertIn(WORKFLOWS[0], output)
        self.assertFalse(os.path.exists(engine), "nothing was produced")
        self.assertIn("this repository's own", read(path).decode("utf-8"), "and the file is untouched")

    def test_the_factory_s_own_previous_bytes_are_not_a_refusal(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        self.produce(engine, "--repo-root", host)  # the record's hashes are the way back in

    def test_a_repository_file_the_factory_does_not_write_is_left_alone(self):
        host = init(os.path.join(self.tmp, "host"))
        os.makedirs(os.path.join(host, ".github", "workflows"))
        theirs = os.path.join(host, ".github", "workflows", "product.yml")
        with open(theirs, "w", encoding="utf-8") as handle:
            handle.write("name: product\n")
        codeowners = os.path.join(host, ".github", "CODEOWNERS")
        with open(codeowners, "w", encoding="utf-8") as handle:
            handle.write("* @somebody\n")
        self.produce(os.path.join(host, "engine"), "--repo-root", host)
        self.assertEqual("name: product\n", read(theirs).decode("utf-8"))
        self.assertEqual("* @somebody\n", read(codeowners).decode("utf-8"))


class TestNoSilentInertRails(RepositoryCase):
    """`assure_active`: the invariant of #501, as code. This is the regression test for the bug.

    It is asserted against the function and not only end to end, because the way the bug comes
    back is a recipe added to the emission without a thought for the topology -- a produce that
    writes every workflow under the engine and reports success.
    """

    def test_a_run_that_wrote_every_workflow_under_an_embedded_engine_is_refused(self):
        embedded = repository.Topology("/repo", "engine")
        with self.assertRaises(repository.RepositoryError) as caught:
            repository.assure_active(embedded, set(WORKFLOWS), {})
        self.assertIn("GitHub will never run them", str(caught.exception))
        self.assertIn(WORKFLOWS[0], str(caught.exception))

    def test_an_embedded_run_that_wrote_no_workflow_at_the_root_is_refused(self):
        embedded = repository.Topology("/repo", "engine")
        with self.assertRaises(repository.RepositoryError) as caught:
            repository.assure_active(embedded, {"src/X/Generated/Map.g.cs"}, {})
        self.assertIn("no workflow at the repository root", str(caught.exception))

    def test_an_embedded_run_that_wrote_the_root_s_workflows_passes(self):
        embedded = repository.Topology("/repo", "engine")
        repository.assure_active(embedded, {"src/X/Generated/Map.g.cs"}, dict.fromkeys(WORKFLOWS, b""))

    def test_a_standalone_run_writes_its_own_workflows_and_nothing_at_another_root(self):
        standalone = repository.Topology("/repo", None)
        repository.assure_active(standalone, set(WORKFLOWS), {})
        with self.assertRaises(repository.RepositoryError):
            repository.assure_active(standalone, set(WORKFLOWS), dict.fromkeys(WORKFLOWS, b""))

    def test_no_produce_of_an_embedded_engine_leaves_a_workflow_under_the_engine(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        found = [os.path.join(where, name) for where, _dirs, names in os.walk(engine) for name in names
                 if repository.is_workflow(os.path.relpath(os.path.join(where, name), engine).replace(os.sep, "/"))]
        self.assertEqual([], found, "an embedded engine carries no workflow file at all")
        at_root = sorted(n for n in os.listdir(os.path.join(host, ".github", "workflows")))
        self.assertEqual(sorted(w.split("/")[-1] for w in WORKFLOWS), at_root)


if __name__ == "__main__":
    unittest.main()


class TestTheEngineGateChecksTheRepositoryRoot(RepositoryCase):
    """`scripts/engine-gate.py repository` is what the root's gate workflow runs (0069)."""

    def gate(self, engine, *args):
        done = subprocess.run([sys.executable, os.path.join(engine, "scripts", "engine-gate.py"),
                               "repository", *args], cwd=engine, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        return done.returncode, done.stdout

    def test_a_standalone_engine_passes_because_it_carries_its_own_rails(self):
        engine = os.path.join(self.tmp, "engine")
        self.produce(engine)
        code, output = self.gate(engine)
        self.assertEqual(0, code, output)
        self.assertIn("its own repository root", output)

    def test_an_embedded_engine_passes_against_its_repository_root(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        for args in ((), ("--root", host)):
            code, output = self.gate(engine, *args)
            self.assertEqual(0, code, output)
            self.assertIn("carries no workflow of its own", output)

    def test_a_hand_edited_rail_at_the_root_fails_the_check(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        with open(os.path.join(host, *WORKFLOWS[1].split("/")), "ab") as handle:
            handle.write(b"\n# a rail nobody produced\n")
        code, output = self.gate(engine, "--root", host)
        self.assertEqual(1, code, output)
        self.assertIn("the record hashes", output)

    def test_a_missing_rail_at_the_root_fails_the_check(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        os.remove(os.path.join(host, *WORKFLOWS[0].split("/")))
        code, output = self.gate(engine, "--root", host)
        self.assertEqual(1, code, output)
        self.assertIn("runs nowhere", output)

    def test_a_workflow_planted_under_an_embedded_engine_fails_the_check(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        os.makedirs(os.path.join(engine, ".github", "workflows"))
        with open(os.path.join(engine, ".github", "workflows", "validate.yml"), "w", encoding="utf-8") as handle:
            handle.write("name: validate\n")
        code, output = self.gate(engine, "--root", host)
        self.assertEqual(1, code, output)
        self.assertIn("where GitHub will never run it", output)

    def test_a_record_from_before_the_topology_was_recorded_is_named_not_assumed(self):
        engine = os.path.join(self.tmp, "engine")
        self.produce(engine)
        path = os.path.join(engine, "provenance.json")
        document = json.loads(read(path).decode("utf-8"))
        del document["repository"]
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)
        code, output = self.gate(engine)
        self.assertEqual(1, code, output)
        self.assertIn("records no `repository` section", output)


class TestTheRailsReadAPathInTheEnginesOwnTerms(RepositoryCase):
    """A path GitHub reports is not the path an embedded engine's own tables are written in (#507).

    The workflows being at the root (#501) is half of it. The scripts they run read `gh pr view
    --json files`, whose paths are relative to the **repository**, and judge them against the
    engine's semantic surface, its ownership table and its documents, all of which are written in
    engine-relative paths. For an embedded engine `engine/src/Rules/X.cs` matches none of `src/**`,
    and a conformance gate that finds nothing semantic requires no verdict of the one kind of change
    it exists to hold.
    """

    def embedded(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        return host, engine

    def script(self, engine, name):
        """The emitted script as a module, with its ROOT at `engine`."""
        spec = importlib.util.spec_from_file_location(f"emitted_{name}_{id(engine)}",
                                                     os.path.join(engine, "tools", f"{name}.py"))
        module = importlib.util.module_from_spec(spec)
        writes, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = writes
        return module

    def test_the_conformance_gate_reads_the_engine_path_from_the_record(self):
        _host, engine = self.embedded()
        gate = self.script(engine, "conformance-gate")
        self.assertEqual("engine", gate.engine_path(), "the record says where the engine is (0069)")

    def test_a_changed_source_under_the_engine_is_on_the_semantic_surface(self):
        _host, engine = self.embedded()
        gate = self.script(engine, "conformance-gate")
        patterns = ["src/**", "overlay/**"]
        changed = [f"engine/src/{NAME}/Rules/AltitudeLimit.cs", "engine/overlay/altitude-limit.json",
                   "corpus/hallertau/README.md", "README.md", ".github/workflows/validate.yml"]
        self.assertEqual(sorted(["overlay/altitude-limit.json", f"src/{NAME}/Rules/AltitudeLimit.cs"]),
                         sorted(gate.semantic_surface(changed, patterns, "engine")),
                         "the engine's sources are semantic; the repository's own files are not this "
                         "engine's surface and cannot be what a verdict about it is about")

    def test_a_standalone_engine_s_surface_is_unchanged(self):
        engine = os.path.join(self.tmp, "engine")
        self.produce(engine)
        gate = self.script(engine, "conformance-gate")
        self.assertEqual("", gate.engine_path())
        self.assertEqual([f"src/{NAME}/Rules/AltitudeLimit.cs"],
                         gate.semantic_surface([f"src/{NAME}/Rules/AltitudeLimit.cs", "README.md"],
                                               ["src/**"], ""))

    def test_the_documentation_skeleton_speaks_one_path_language(self):
        host, engine = self.embedded()
        git(host, "add", "-A")
        git(host, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "the engine")
        git(host, "branch", "-M", "main")
        git(host, "checkout", "-q", "-b", "two-documents")
        with open(os.path.join(engine, "AGENTS.md"), "a", encoding="utf-8") as handle:
            handle.write("\n<!-- a change to the engine's own contract -->\n")
        with open(os.path.join(host, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("# the repository's own README\n")
        git(host, "add", "-A")
        git(host, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "two documents")
        done = subprocess.run([sys.executable, os.path.join(engine, "tools", "pr-policy.py"), "--docs-skeleton"],
                              cwd=engine, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(0, done.returncode, done.stdout)
        listed = [line.split("`")[1] for line in done.stdout.splitlines() if line.startswith("- [ ]")]
        self.assertIn("AGENTS.md", listed, "the engine's own contract, by the path the engine knows it as")
        self.assertNotIn("engine/AGENTS.md", listed, "and not a second time under the repository's path for it")
        self.assertNotIn("README.md", listed,
                         "the repository's own README is not a document this engine owns, and the check "
                         "the skeleton is written for would reject it")
        self.assertIn("updated", [line.split("—")[1].split(":")[0].strip()
                                  for line in done.stdout.splitlines()
                                  if line.startswith("- [ ]") and "`AGENTS.md`" in line])


class TestARailAtTheRootIsReportedWhereItIs(RepositoryCase):
    """A report about where the rails are must be right about where they are (#509).

    `factory rails --check` and `tools/agent-doctor.py` both judged every rail by looking for it in
    the engine and comparing its bytes with the recipe history. Four of them are not in an embedded
    engine and must not be, and their bytes at the root are rendered for the engine's path, so no
    version of any recipe wrote them: both reports called four rails absent that were exactly where
    they belong, and told the reader to run the produce that had just put them there.
    """

    def embedded(self):
        host = init(os.path.join(self.tmp, "host"))
        engine = os.path.join(host, "engine")
        self.produce(engine, "--repo-root", host)
        return host, engine

    def test_the_record_places_the_root_and_the_rails_it_holds(self):
        host, engine = self.embedded()
        self.assertEqual("engine", ownership.engine_path(engine))
        self.assertEqual(os.path.realpath(host), os.path.realpath(ownership.repository_root(engine)))
        states = ownership.repository_states(engine)
        self.assertEqual(sorted(FILES), sorted(states))
        self.assertEqual({ownership.CURRENT}, {state for state, _ in states.values()},
                         "every rail at the root is the bytes the record names")

    def test_a_standalone_engine_has_no_rails_at_another_root(self):
        engine = os.path.join(self.tmp, "engine")
        self.produce(engine)
        self.assertEqual("", ownership.engine_path(engine))
        self.assertEqual({}, ownership.repository_states(engine),
                         "its own .github IS its repository's, and managed_states judges those")

    def test_an_edited_or_missing_rail_at_the_root_is_named_as_that(self):
        host, engine = self.embedded()
        with open(os.path.join(host, *WORKFLOWS[1].split("/")), "ab") as handle:
            handle.write(b"\n# somebody's change\n")
        os.remove(os.path.join(host, *WORKFLOWS[2].split("/")))
        states = ownership.repository_states(engine)
        self.assertEqual(ownership.EDITED, states[WORKFLOWS[1]][0])
        self.assertEqual(ownership.ABSENT, states[WORKFLOWS[2]][0])
        self.assertEqual(ownership.CURRENT, states[WORKFLOWS[0]][0])

    def test_the_rails_report_says_the_root_holds_them_rather_than_that_they_are_missing(self):
        host, engine = self.embedded()
        import rails as rails_step
        files = rails_step.agent_files(engine)
        wrong = rails_step.unfaithful_files(files)
        self.assertEqual([], [path for path, _state, _versions in wrong],
                         "nothing is missing: three rails are at the root and the rest in the engine")
        self.assertEqual(sorted(p for p in FILES if p in files),
                         sorted(p for p in files if p in ownership.repository_states(engine)),
                         "and the ones at the root are the ones judged there")
