#!/usr/bin/env python3
"""check-workflow-pins.py, proved able to fail.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(ROOT, "tools", "check-workflow-pins.py")

_spec = importlib.util.spec_from_file_location("check_workflow_pins", TOOL)
pins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pins)

GOOD = """\
jobs:
  validate:
    steps:
      - uses: actions/setup-python@abc # v5
        with:
          python-version: '3.12.14'
      - run: python3 -m pip install --quiet --require-hashes -r tools/requirements-dev.txt
"""


class Cases(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def run_on(self, **files):
        for name, text in files.items():
            with open(os.path.join(self.dir, name), "w", encoding="utf-8") as handle:
                handle.write(text)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = pins.main(["--workflows", self.dir])
        return code, out.getvalue() + err.getvalue()

    def test_exact_python_and_a_hash_locked_install_pass(self):
        code, output = self.run_on(**{"a.yml": GOOD})
        self.assertEqual(code, 0, output)

    def test_a_minor_only_python_fails(self):
        code, output = self.run_on(**{"a.yml": GOOD.replace("'3.12.14'", "'3.12'")})
        self.assertEqual(code, 1, output)
        self.assertIn("a.yml:6: python-version '3.12' is not an exact X.Y.Z", output)

    def test_an_unquoted_or_wildcard_python_is_judged_by_its_value(self):
        self.assertEqual(self.run_on(**{"a.yml": GOOD.replace("'3.12.14'", "3.12.14")})[0], 0)
        self.assertEqual(self.run_on(**{"a.yml": GOOD.replace("'3.12.14'", "'3.12.x'")})[0], 1)

    def test_an_unpinned_pip_install_fails(self):
        code, output = self.run_on(**{"a.yml": GOOD.replace("--require-hashes -r tools/requirements-dev.txt", "pytest")})
        self.assertEqual(code, 1, output)
        self.assertIn("pip install without --require-hashes", output)

    def test_hashes_without_a_requirements_file_fails(self):
        code, _ = self.run_on(**{"a.yml": GOOD.replace("-r tools/requirements-dev.txt", "pytest")})
        self.assertEqual(code, 1)

    def test_no_workflows_proved_nothing(self):
        code, output = self.run_on()
        self.assertEqual(code, 1)
        self.assertIn("proved nothing", output)

    def test_no_python_proved_nothing(self):
        code, output = self.run_on(**{"a.yml": "jobs: {}\n"})
        self.assertEqual(code, 1)
        self.assertIn("no workflow sets up Python", output)

    def test_the_real_workflows_are_pinned(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = pins.main([])
        self.assertEqual(code, 0, out.getvalue())


if __name__ == "__main__":
    unittest.main()
