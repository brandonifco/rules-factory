#!/usr/bin/env python3
"""The subsystem boundary is a fact, not an intention (#248, 0032).

`tools/check-boundaries.py` exists because an `import` is one line and the reason not to write
it is invisible at the moment someone does. A checker that only ever passes proves nothing, so
each rule below is watched failing on a tree built to break it, and the mutation is named:

  * a sibling import -- checkmap reaching into factory;
  * an import of a subsystem below the contract -- mapcontract reaching back into checkmap;
  * a deferred import, inside a function, which is a dependency all the same;
  * a relative import that climbs out of its own package;
  * a subsystem that is declared and absent, and one whose statement of what it owns is gone;
  * an examined-nothing run.

Run: python3 -m unittest discover -s tools/tests
"""
import importlib.util
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)

_spec = importlib.util.spec_from_file_location("check_boundaries",
                                               os.path.join(TOOLS, "check-boundaries.py"))
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = checker.main(argv)
    return code, out.getvalue(), err.getvalue()


class TestTheCommittedTree(unittest.TestCase):
    def test_every_subsystem_holds_the_direction(self):
        code, out, err = run([])
        self.assertEqual(code, 0, out + err)
        self.assertIn("hold the direction", out)

    def test_it_examined_something(self):
        problems, files = checker.check(TOOLS)
        self.assertEqual(problems, [])
        self.assertGreater(files, 20, "the check examined almost nothing")

    def test_the_engines_bytes_are_excluded_and_exist(self):
        """The exclusion is real, so it has to name a directory that is really there."""
        for excluded in checker.EXCLUDED:
            self.assertTrue(os.path.isdir(os.path.join(TOOLS, excluded)), excluded)
        examined = {relative for relative, _ in checker._sources(TOOLS, "factory")}
        self.assertTrue(examined, "no factory source was examined")
        self.assertFalse([r for r in examined if r.startswith("factory/recipe/")])


class MutationCase(unittest.TestCase):
    """A copy of tools/, mutated one way, checked through --root."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.tools = os.path.join(self.tmp, "tools")
        os.makedirs(self.tools)
        for name, _, _ in checker.SUBSYSTEMS:
            shutil.copytree(os.path.join(TOOLS, name), os.path.join(self.tools, name),
                            ignore=shutil.ignore_patterns("__pycache__"))

    def path(self, relative):
        return os.path.join(self.tools, *relative.split("/"))

    def prepend(self, relative, line):
        """Put a line just after the module's docstring, where an import belongs."""
        path = self.path(relative)
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        end = text.index('"""', text.index('"""') + 3) + 4
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text[:end] + line + "\n" + text[end:])

    def assert_refused(self, *expected):
        code, out, err = run(["--root", self.tmp])
        self.assertEqual(code, 1, out + err)
        for text in expected:
            self.assertIn(text, out + err)


class TestMutations(MutationCase):
    def test_a_sibling_import(self):
        self.prepend("checkmap/schema.py", "import factory")
        self.assert_refused("checkmap/schema.py", "import factory",
                            "a subsystem beside it")

    def test_the_contract_importing_a_consumer(self):
        self.prepend("mapcontract/entry.py", "from checkmap.diagnostics import verdict")
        self.assert_refused("mapcontract/entry.py", "is the contract and imports no subsystem")

    def test_a_deferred_import_inside_a_function(self):
        path = self.path("checkmap/cli.py")
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        marker = "def find_manifest(map_path):\n"
        self.assertIn(marker, text)
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text.replace(marker, marker + "    import factory\n", 1))
        self.assert_refused("checkmap/cli.py", "import factory")

    def test_a_relative_import_that_climbs_out(self):
        self.prepend("mapcontract/entry.py", "from ..checkmap import diagnostics")
        self.assert_refused("mapcontract/entry.py", "climbs out of tools/mapcontract/")

    def test_a_declared_subsystem_that_is_not_there(self):
        shutil.rmtree(self.path("mapcontract"))
        self.assert_refused("tools/mapcontract/ is declared a subsystem and does not exist")

    def test_a_subsystem_that_says_nothing_about_what_it_owns(self):
        with io.open(self.path("checkmap/__init__.py"), "w", encoding="utf-8") as handle:
            handle.write("# nothing\n")
        self.assert_refused("checkmap/__init__.py", "statement of what it owns")

    def test_a_missing_statement_file(self):
        os.remove(self.path("factory/__main__.py"))
        self.assert_refused("factory/__main__.py cannot be read")


class TestNothingExamined(unittest.TestCase):
    def test_an_empty_tools_directory_is_not_a_pass(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "tools"))
        code, out, err = run(["--root", tmp])
        self.assertEqual(code, 1)
        self.assertIn("proved nothing", err)

    def test_a_root_with_no_tools_is_a_usage_error(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        code, _, err = run(["--root", tmp])
        self.assertEqual(code, 2)
        self.assertIn("no tools directory", err)


if __name__ == "__main__":
    unittest.main()
