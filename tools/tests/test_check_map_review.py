#!/usr/bin/env python3
"""check-map-review.py, proved able to fail.

Each case builds a scratch repository with one map and the review the gate asks for, shows
the gate passes, then does the thing the gate exists to catch -- edits the map and leaves the
review alone, records a digest from before, drops the reason from an exemption -- and shows
it fails. The maps are a few bytes of JSON written here: the gate reads bytes, not entries,
and a fixture drawn from `examples/` would move whenever a real map did.

Run: python3 -m unittest discover -s tools/tests
"""
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "check-map-review.py")

_spec = importlib.util.spec_from_file_location("check_map_review", TOOL)
check_map_review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_map_review)

MAP = b'{"schemaVersion": 1, "entries": []}\n'
EDITED = b'{"schemaVersion": 1, "entries": [{"id": "new"}]}\n'
COMMIT = "0" * 40


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Repo:
    """A scratch root holding examples/widget/corpus-map.json and its review.json."""

    def __init__(self, tmp):
        self.root = pathlib.Path(tmp)
        self.dir = self.root / "examples" / "widget"
        self.dir.mkdir(parents=True)
        self.map = self.dir / "corpus-map.json"
        self.map.write_bytes(MAP)

    def review(self, review, name="corpus-map.json"):
        doc = {"reviews": {name: review}}
        (self.dir / "review.json").write_text(json.dumps(doc), encoding="utf-8")

    def blind(self, sha=None, commit=COMMIT):
        (self.dir / "blind").mkdir(exist_ok=True)
        (self.dir / "blind" / "results.json").write_text(
            json.dumps({"reference": {"commit": COMMIT, "path": "x"}}), encoding="utf-8")
        (self.dir / "blind" / "resolutions.json").write_text("[]", encoding="utf-8")
        self.review({
            "sha256": sha or digest(MAP), "method": "blind-second-mapping",
            "comparison": "blind/results.json", "resolutions": "blind/resolutions.json",
            "compared": {"commit": commit, "sha256": "1" * 64},
        })

    def run(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_map_review.main(["--root", str(self.root)])
        return code, out.getvalue() + err.getvalue()


class BlindSecondMapping(unittest.TestCase):
    def test_current_digest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.blind()
            code, out = repo.run()
            self.assertEqual(code, 0, out)
            self.assertIn("ok  examples/widget/corpus-map.json  blind-second-mapping", out)

    def test_map_changed_without_review_update_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.blind()
            repo.map.write_bytes(EDITED)
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("stale review", out)
            self.assertIn(digest(EDITED), out)
            self.assertIn("run a blind second mapping", out)

    def test_stale_digest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.map.write_bytes(EDITED)
            repo.blind(sha=digest(MAP))
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn(f"records '{digest(MAP)}'", out)

    def test_comparison_naming_another_commit_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.blind(commit="f" * 40)
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("names reference commit", out)

    def test_missing_comparison_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.blind()
            (repo.dir / "blind" / "resolutions.json").unlink()
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("resolutions blind/resolutions.json does not exist", out)


class Missing(unittest.TestCase):
    def test_no_review_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("no review", out)

    def test_review_for_another_map_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.review({"sha256": digest(MAP), "method": "exemption"}, name="corpus-map-old.json")
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("has no review for corpus-map.json", out)
            self.assertIn("reviews corpus-map-old.json, which does not exist", out)

    def test_no_maps_proves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = check_map_review.main(["--root", tmp])
            self.assertEqual(code, 1)
            self.assertIn("proved nothing", err.getvalue())

    def test_unknown_method_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.review({"sha256": digest(MAP), "method": "looked-at-it"})
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("expected one of", out)


class IndependentVerdict(unittest.TestCase):
    def test_verdict_must_name_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            verdict = repo.dir / "verdict.json"
            repo.review({"sha256": digest(MAP), "method": "independent-verdict",
                         "verdict": "verdict.json"})
            verdict.write_text(json.dumps({"sha256": digest(MAP)}), encoding="utf-8")
            self.assertEqual(repo.run()[0], 0)

            verdict.write_text(json.dumps({"sha256": digest(EDITED)}), encoding="utf-8")
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("not the map's", out)


class Exemption(unittest.TestCase):
    def test_legacy_exemption_passes_and_is_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.review({"sha256": digest(MAP), "method": "exemption",
                         "exemption": {"kind": "legacy", "issue": "#3",
                                       "reason": "predates the gate"}})
            code, out = repo.run()
            self.assertEqual(code, 0, out)
            self.assertIn("EXEMPT  examples/widget/corpus-map.json  legacy (#3): predates the gate", out)
            self.assertIn("(1 by exemption)", out)

    def test_non_semantic_exemption_passes_and_is_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.map.write_bytes(EDITED)
            repo.review({"sha256": digest(EDITED), "method": "exemption",
                         "exemption": {"kind": "non-semantic", "previousSha256": digest(MAP),
                                       "reason": "reindented"}})
            code, out = repo.run()
            self.assertEqual(code, 0, out)
            self.assertIn("EXEMPT  examples/widget/corpus-map.json  non-semantic: reindented", out)

    def test_exemption_does_not_survive_a_later_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.review({"sha256": digest(MAP), "method": "exemption",
                         "exemption": {"kind": "legacy", "issue": "#3", "reason": "old"}})
            repo.map.write_bytes(EDITED)
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("stale review", out)

    def test_exemption_without_reason_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.review({"sha256": digest(MAP), "method": "exemption",
                         "exemption": {"kind": "legacy", "issue": "#3", "reason": " "}})
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("exemption.reason is empty", out)

    def test_legacy_exemption_without_issue_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.review({"sha256": digest(MAP), "method": "exemption",
                         "exemption": {"kind": "legacy", "reason": "old"}})
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("names the issue", out)

    def test_non_semantic_exemption_without_previous_digest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.review({"sha256": digest(MAP), "method": "exemption",
                         "exemption": {"kind": "non-semantic", "reason": "typo"}})
            code, out = repo.run()
            self.assertEqual(code, 1, out)
            self.assertIn("previousSha256", out)


if __name__ == "__main__":
    unittest.main()
