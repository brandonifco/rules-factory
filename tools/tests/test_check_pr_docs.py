#!/usr/bin/env python3
"""check-pr-docs.py, proved able to fail.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(ROOT, "tools", "check-pr-docs.py")

_spec = importlib.util.spec_from_file_location("check_pr_docs", TOOL)
docs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(docs)

LIVING = ["README.md", "docs/method.md"]


def body(*lines):
    return "Closes #1\n\n## Documentation\n\n" + "\n".join(lines) + "\n\n## Tests\n\nran them\n"


GOOD = body(
    "- [x] `README.md` — checked, no change: nothing it says moved",
    "- [x] `docs/method.md` — updated: phase 3 names the bound")


class Problems(unittest.TestCase):
    def test_every_living_document_accounted_for_passes(self):
        self.assertEqual(docs.problems(GOOD, LIVING, ["docs/method.md"]), [])

    def test_no_section_fails_and_says_how_to_get_one(self):
        found = docs.problems("Closes #1\n", LIVING, [])
        self.assertEqual(len(found), 1)
        self.assertIn("--skeleton", found[0])

    def test_a_living_document_left_out_fails(self):
        found = docs.problems(body("- [x] `README.md` — checked, no change: fine"), LIVING, [])
        self.assertEqual(found, ["`docs/method.md` is a living document and is not listed"])

    def test_an_unticked_box_fails(self):
        found = docs.problems(GOOD.replace("[x] `README.md`", "[ ] `README.md`"), LIVING, ["docs/method.md"])
        self.assertEqual(found, ["`README.md` is not ticked"])

    def test_a_verdict_with_no_note_fails(self):
        found = docs.problems(GOOD.replace("nothing it says moved", ""), LIVING, ["docs/method.md"])
        self.assertEqual(found, ["`README.md` has no note after `checked, no change:`"])

    def test_a_changed_document_called_unchanged_fails(self):
        found = docs.problems(GOOD, LIVING, ["docs/method.md", "README.md"])
        self.assertEqual(found, ["`README.md` is changed by this pull request but listed as checked, no change"])

    def test_updated_without_a_change_fails(self):
        found = docs.problems(GOOD, LIVING, [])
        self.assertEqual(found, ["`docs/method.md` is listed as updated but this pull request does not change it"])

    def test_a_changed_frozen_document_must_be_listed(self):
        frozen = "examples/trial-9/REPORT.md"
        found = docs.problems(GOOD, LIVING, ["docs/method.md", frozen])
        self.assertEqual(found, [f"`{frozen}` is changed by this pull request and is not listed"])
        listed = GOOD.replace("\n\n## Tests", f"\n- [x] `{frozen}` — updated: the trial's report\n\n## Tests")
        self.assertEqual(docs.problems(listed, LIVING, ["docs/method.md", frozen]), [])

    def test_a_typo_in_a_path_fails(self):
        typo = GOOD.replace("\n\n## Tests", "\n- [x] `docs/methd.md` — checked, no change: x\n\n## Tests")
        found = docs.problems(typo, LIVING, ["docs/method.md"])
        self.assertEqual(found, ["`docs/methd.md` is neither a living document nor changed here"])

    def test_an_unreadable_line_fails_rather_than_being_skipped(self):
        found = docs.problems(GOOD.replace("— updated:", "— edited:"), LIVING, ["docs/method.md"])
        self.assertTrue(found[0].startswith("cannot read:"), found)

    def test_a_line_inside_an_html_comment_is_not_an_answer(self):
        hidden = body("<!-- the template's example, not an answer:",
                      "- [x] `README.md` — checked, no change: x -->",
                      "- [x] `docs/method.md` — updated: phase 3")
        self.assertIn("`README.md` is a living document and is not listed",
                      docs.problems(hidden, LIVING, ["docs/method.md"]))

    def test_the_section_ends_at_the_next_heading(self):
        after = "Closes #1\n\n## Documentation\n\n- [x] `docs/method.md` — updated: x\n\n## Other\n\n" \
                "- [x] `README.md` — checked, no change: x\n"
        self.assertIn("`README.md` is a living document and is not listed",
                      docs.problems(after, LIVING, ["docs/method.md"]))


class Classification(unittest.TestCase):
    def test_decision_records_and_trial_evidence_are_frozen_and_their_indexes_are_not(self):
        self.assertTrue(docs.is_frozen("docs/decisions/0031-an-example.md"))
        self.assertTrue(docs.is_frozen("examples/tax-121-principal-residence/REPORT.md"))
        self.assertTrue(docs.is_frozen("examples/hoyle-blind-rebuild/brief/engine/decisions/0001-x.md"))
        self.assertFalse(docs.is_frozen("docs/decisions/README.md"))
        self.assertFalse(docs.is_frozen("examples/README.md"))
        self.assertFalse(docs.is_frozen("AGENTS.md"))
        self.assertFalse(docs.is_frozen("tools/factory/recipe/rails/AGENTS.md"))


class AgainstARepository(unittest.TestCase):
    """The diff and the living set are read from git, and the event payload is what CI passes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "readme\n")
        self.write("docs/method.md", "method\n")
        self.write("docs/decisions/0001-x.md", "frozen\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.base = self.git("rev-parse", "HEAD")
        self.write("docs/method.md", "method, changed\n")
        self.git("commit", "-q", "-am", "change")
        self.head = self.git("rev-parse", "HEAD")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t")
        return subprocess.run(["git", *args], cwd=self.root, env=env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, path, text):
        os.makedirs(os.path.dirname(os.path.join(self.root, path)) or self.root, exist_ok=True)
        with open(os.path.join(self.root, path), "w", encoding="utf-8") as handle:
            handle.write(text)

    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = docs.main([*args, "--root", self.root])
        return code, out.getvalue()

    def event(self, text):
        path = os.path.join(self.root, "event.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"pull_request": {"body": text, "base": {"sha": self.base},
                                        "head": {"sha": self.head}}}, handle)
        return path

    def test_the_event_payload_passes_when_the_section_matches_the_diff(self):
        code, output = self.run_main("--event", self.event(GOOD))
        self.assertEqual(code, 0, output)
        self.assertIn("2 living document(s) accounted for, 1 changed", output)

    def test_the_event_payload_fails_when_it_does_not(self):
        code, output = self.run_main("--event", self.event(GOOD.replace("— updated: phase 3 names the bound",
                                                                        "— checked, no change: fine")))
        self.assertEqual(code, 1, output)

    def test_a_null_body_is_a_missing_section_not_a_crash(self):
        code, output = self.run_main("--event", self.event(None))
        self.assertEqual(code, 1, output)

    def test_the_skeleton_lists_the_diff_as_updated_and_passes_once_completed(self):
        code, output = self.run_main("--skeleton", "--base", self.base, "--head", self.head)
        self.assertEqual(code, 0)
        self.assertIn("- [ ] `docs/method.md` — updated: ", output)
        self.assertNotIn("0001-x.md", output)
        completed = output.replace("- [ ]", "- [x]").replace(": \n", ": read it\n")
        self.assertEqual(self.run_main("--event", self.event(completed))[0], 0)

    def test_an_unreadable_base_exits_2(self):
        code, output = self.run_main("--body", os.devnull, "--base", "no-such-ref", "--head", self.head)
        self.assertEqual(code, 2, output)


if __name__ == "__main__":
    unittest.main()
