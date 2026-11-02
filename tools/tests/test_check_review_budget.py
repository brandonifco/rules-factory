#!/usr/bin/env python3
"""check-review-budget.py, proved able to fail.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(ROOT, "tools", "check-review-budget.py")

_spec = importlib.util.spec_from_file_location("check_review_budget", TOOL)
budget = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(budget)


def review(n=1):
    return {"body": f"Independent review (round {n}, abc123)\n\nfindings"}


BODY = "Closes #1\n\n## Documentation\n\nx\n"
FILLED = BODY + "\n## Review budget exceeded\n\nCause: one parser, two jobs. Redesign: split it.\n"
EMPTY = BODY + "\n## Review budget exceeded\n\n<!-- say why -->\n\n## Tests\n\nran\n"


class Verdict(unittest.TestCase):
    def test_two_rounds_pass_without_the_section(self):
        code, line = budget.verdict(BODY, [review(1), review(2)])
        self.assertEqual(code, 0)
        self.assertIn("2 independent review round(s)", line)

    def test_three_rounds_without_the_section_fail(self):
        code, line = budget.verdict(BODY, [review(1), review(2), review(3)])
        self.assertEqual(code, 1)
        self.assertIn("3 independent review rounds exceed the budget of 2", line)

    def test_three_rounds_with_an_empty_section_fail(self):
        self.assertEqual(budget.verdict(EMPTY, [review(i) for i in range(3)])[0], 1)

    def test_three_rounds_with_a_filled_section_pass(self):
        code, line = budget.verdict(FILLED, [review(i) for i in range(3)])
        self.assertEqual(code, 0)
        self.assertIn("3 independent review rounds", line)

    def test_comments_without_the_header_do_not_count(self):
        others = [{"body": "LGTM"}, {"body": "Re: Independent review (round 1)"},
                  {"body": "independent review ("}, {"body": None}]
        self.assertEqual(budget.rounds(others), 0)
        self.assertEqual(budget.verdict(BODY, [review(1), review(2)] + others)[0], 0)
        self.assertEqual(budget.rounds([review(1)] + others), 1)


class Main(unittest.TestCase):
    def run_main(self, run):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(budget.subprocess, "run", run), \
                redirect_stdout(out), redirect_stderr(err):
            code = budget.main(["--pr", "7"])
        return code, out.getvalue(), err.getvalue()

    def test_a_gh_error_fails_rather_than_passes(self):
        failed = mock.Mock(return_value=mock.Mock(returncode=1, stdout="", stderr="HTTP 502"))
        code, out, err = self.run_main(failed)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("HTTP 502", err)

    def test_unparseable_gh_output_fails(self):
        garbled = mock.Mock(return_value=mock.Mock(returncode=0, stdout="not json", stderr=""))
        self.assertEqual(self.run_main(garbled)[0], 2)

    def test_the_count_is_printed_on_success(self):
        payload = '{"body": "", "comments": [{"body": "Independent review (round 1)"}]}'
        ok = mock.Mock(return_value=mock.Mock(returncode=0, stdout=payload, stderr=""))
        code, out, _ = self.run_main(ok)
        self.assertEqual(code, 0)
        self.assertIn("1 independent review round(s)", out)


if __name__ == "__main__":
    unittest.main()
