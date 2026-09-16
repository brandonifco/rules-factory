#!/usr/bin/env python3
"""check-status-issues.py, proved able to fail.

Issue state is a dictionary here, never the network, so a case does not move when an issue
closes. validate.sh runs the checker against the real README and the real issues.

Run: python3 -m unittest discover -s tools/tests
"""
import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(ROOT, "tools", "check-status-issues.py")

_spec = importlib.util.spec_from_file_location("check_status_issues", TOOL)
status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(status)

REPO = "brandonifco/rules-factory"
URL = f"https://github.com/{REPO}/issues"
STATES = {3: "closed", 152: "closed", 155: "closed", 157: "open", 8: "open"}


class Cases(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.readme = os.path.join(self._tmp.name, "README.md")
        self.asked = []

    def tearDown(self):
        self._tmp.cleanup()

    def state_of(self, repo, number):
        self.asked.append(number)
        if number not in STATES:
            raise status.Problem(f"could not read the state of #{number}: no such issue")
        return STATES[number]

    def run_on(self, text, env=None):
        with open(self.readme, "w", encoding="utf-8") as handle:
            handle.write(text)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env or {}, clear=False), redirect_stdout(out), redirect_stderr(err):
            if not env:
                os.environ.pop("RULES_FACTORY_OFFLINE", None)
            code = status.main(["--readme", self.readme], state_of=self.state_of)
        return code, out.getvalue() + err.getvalue()

    def test_not_done_citing_a_closed_issue_fails(self):
        code, output = self.run_on(f"| Acceptance | | not done ([#3]({URL}/3)) |\n")
        self.assertEqual(code, 1, output)
        self.assertIn("README line 1: says 'not done' citing #3, which is closed", output)

    def test_not_yet_citing_a_closed_range_names_both_ends(self):
        code, output = self.run_on(f"| rails | | Not yet: gates ([#152]({URL}/152)–[#155]({URL}/155)) |\n")
        self.assertEqual(code, 1, output)
        self.assertIn("citing #152", output)
        self.assertIn("citing #155", output)

    def test_not_yet_citing_an_open_issue_passes(self):
        code, output = self.run_on(f"Para one.\n\nNot yet proven end to end ([#157]({URL}/157)).\n")
        self.assertEqual(code, 0, output)
        self.assertIn("1 issue citation(s)", output)

    def test_a_bare_hash_reference_is_checked(self):
        code, output = self.run_on("The blind rebuild is not done, see #3.\n")
        self.assertEqual(code, 1, output)

    def test_another_repository_s_issue_is_not_this_repository_s(self):
        code, output = self.run_on("Not yet: hoyle-backgammon#3 and "
                                   "https://github.com/brandonifco/faa-part-107/issues/3.\n")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.asked, [])

    def test_a_closed_issue_outside_an_absence_claim_is_fine(self):
        code, output = self.run_on(f"Merged in [#3]({URL}/3).\n\nNot yet: [#157]({URL}/157).\n")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.asked, [157])

    def test_a_claim_is_one_paragraph_not_the_whole_file(self):
        code, output = self.run_on(f"Nothing is not yet here.\n\nClosed: [#3]({URL}/3).\n")
        self.assertEqual(code, 0, output)

    def test_a_multi_line_paragraph_is_one_claim(self):
        code, output = self.run_on(f"This part is\nnot yet built, tracked in\n[#3]({URL}/3).\n")
        self.assertEqual(code, 1, output)
        self.assertIn("README line 1", output)

    def test_each_table_row_is_its_own_claim(self):
        code, output = self.run_on(f"| a | not yet | |\n| b | merged [#3]({URL}/3) | |\n")
        self.assertEqual(code, 0, output)

    def test_an_unreadable_state_fails_rather_than_passes(self):
        code, output = self.run_on(f"Not yet: [#99999]({URL}/99999).\n")
        self.assertEqual(code, 1, output)
        self.assertIn("could not read the state of #99999", output)

    def test_offline_says_not_checked(self):
        code, output = self.run_on(f"not done [#3]({URL}/3)\n", env={"RULES_FACTORY_OFFLINE": "1"})
        self.assertEqual(code, 0, output)
        self.assertIn("NOT CHECKED", output)
        self.assertEqual(self.asked, [])


if __name__ == "__main__":
    unittest.main()
