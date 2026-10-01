#!/usr/bin/env python3
"""A corpus is built and verified by rules-corpus, and by nothing else (0074, #558).

Watched here, on invented corpora:

  * a corpus whose recipe declares nothing unverifiable verifies under `{"expectNotVerified": []}`;
  * rules-corpus decision 0008 holds through the factory: a not-verified check the expectation does
    not name is refused, so is a named check that verified after all, and exactly the named set
    verifies;
  * no expectation turns a refused build into a verified one;
  * a missing definition or expectation is refused, not defaulted;
  * there is no fallback: when the pinned rules-corpus cannot be fetched, or the checkout is not the
    pinned commit or has been edited, nothing is verified and nothing computes a digest instead.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

FACTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "factory")
sys.dont_write_bytecode = True
if FACTORY not in sys.path:
    sys.path.insert(0, FACTORY)
import intake  # noqa: E402
import rulescorpus  # noqa: E402

from tests.factory.corpus_recipe import write_corpus  # noqa: E402

DERIVATION = "transcribed-from-page-images-page-marked"
DATA = b"{1}\nAn invented page.\n"
UNSTORED = {"id": "elsewhere", "stored": False, "bytes": 3, "mediaType": "application/pdf", "origin": "invented",
            "digest": "sha256:" + "0" * 64}


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


class RulesCorpusCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rules-corpus-case-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def corpus(self, expect=(), unstored=False):
        path = write_corpus(self.tmp, "invented.txt", DATA, "invented", DERIVATION, expect=expect)
        if unstored:
            definition_path = rulescorpus.companions(path)[0]
            with open(definition_path, encoding="utf-8") as handle:
                definition = json.load(handle)
            definition["sources"].append(UNSTORED)
            with open(definition_path, "w", encoding="utf-8") as handle:
                json.dump(definition, handle, indent=2, sort_keys=True)
        return path

    def assert_refused(self, path, *expected):
        with self.assertRaises(rulescorpus.Refused) as raised:
            rulescorpus.build_and_verify(path, read)
        for text in expected:
            self.assertIn(text, str(raised.exception))
        return str(raised.exception)


class TestTheExpectation(RulesCorpusCase):
    def test_nothing_unverifiable_verifies_under_an_empty_expectation(self):
        built = rulescorpus.build_and_verify(self.corpus(), read)
        import hashlib
        self.assertEqual(built["baselines"]["invented"]["contentHash"], hashlib.sha256(DATA).hexdigest())
        self.assertEqual(sorted(built["files"]),
                         ["invented.corpus.build.json", "invented.corpus.expect.json", "invented.txt"])

    def test_exactly_the_named_checks_verify(self):
        built = rulescorpus.build_and_verify(self.corpus(expect=["artifact elsewhere"], unstored=True), read)
        self.assertEqual(built["expectNotVerified"], ["artifact elsewhere"])

    def test_an_unexpected_not_verified_check_is_refused(self):
        self.assert_refused(self.corpus(unstored=True), "NOT VERIFIED", "exited 3",
                            "not-verified: artifact elsewhere")

    def test_a_named_check_that_verified_after_all_is_refused(self):
        self.assert_refused(self.corpus(expect=["artifact elsewhere"]), "NOT VERIFIED",
                            "expected not verified but not reported so: artifact elsewhere")

    def test_a_named_set_short_of_what_is_unverified_is_refused(self):
        path = self.corpus(expect=["artifact elsewhere"], unstored=True)
        definition_path = rulescorpus.companions(path)[0]
        with open(definition_path, encoding="utf-8") as handle:
            definition = json.load(handle)
        definition["sources"].append(dict(UNSTORED, id="another"))
        with open(definition_path, "w", encoding="utf-8") as handle:
            json.dump(definition, handle, indent=2, sort_keys=True)
        self.assert_refused(path, "not verified but not expected: artifact another")

    def test_a_refused_build_is_not_rescued_by_any_expectation(self):
        for expect in ([], ["artifact elsewhere"], ["baselines"]):
            with self.subTest(expect=expect):
                path = self.corpus(expect=expect)
                definition_path = rulescorpus.companions(path)[0]
                with open(definition_path, encoding="utf-8") as handle:
                    definition = json.load(handle)
                definition["baselines"][0]["artifact"] = "no-such-artifact"
                with open(definition_path, "w", encoding="utf-8") as handle:
                    json.dump(definition, handle, indent=2, sort_keys=True)
                self.assert_refused(path, "rules-corpus build refused")

    def test_a_missing_expectation_is_refused_not_read_as_empty(self):
        path = self.corpus()
        os.remove(rulescorpus.companions(path)[1])
        self.assert_refused(path, "invented.corpus.expect.json does not exist")

    def test_a_malformed_expectation_is_refused(self):
        path = self.corpus()
        for document in ({"expectNotVerified": "artifact elsewhere"}, {"expectNotVerified": ["a,b"]},
                         {"expectNotVerified": ["x", "x"]}, {"expectNotVerified": [], "also": 1}):
            with self.subTest(document=document):
                with open(rulescorpus.companions(path)[1], "w", encoding="utf-8") as handle:
                    json.dump(document, handle)
                self.assert_refused(path, "must be exactly")

    def test_a_missing_definition_is_refused(self):
        path = self.corpus()
        os.remove(rulescorpus.companions(path)[0])
        self.assert_refused(path, "invented.corpus.build.json does not exist")


class TestAVerifiedBuildIsRememberedOnlyForTheSameBytes(RulesCorpusCase):
    """rulescorpus keeps a verified build for the rest of the process, keyed by every byte it was
    made from (#558). Nothing it keeps may answer for bytes it was not made from."""

    def test_a_changed_corpus_byte_is_built_again(self):
        path = self.corpus()
        first = rulescorpus.build_and_verify(path, read)["baselines"]["invented"]["contentHash"]
        with open(path, "ab") as handle:
            handle.write(b"another line\n")
        second = rulescorpus.build_and_verify(path, read)["baselines"]["invented"]["contentHash"]
        self.assertNotEqual(first, second)
        self.assertEqual(second, __import__("hashlib").sha256(DATA + b"another line\n").hexdigest())

    def test_a_changed_expectation_is_verified_again(self):
        path = self.corpus()
        rulescorpus.build_and_verify(path, read)
        with open(rulescorpus.companions(path)[1], "w", encoding="utf-8") as handle:
            json.dump({"expectNotVerified": ["artifact elsewhere"]}, handle)
        self.assert_refused(path, "expected not verified but not reported so: artifact elsewhere")

    def test_a_refusal_is_not_remembered(self):
        path = self.corpus(unstored=True)
        self.assert_refused(path, "not-verified: artifact elsewhere")
        with open(rulescorpus.companions(path)[1], "w", encoding="utf-8") as handle:
            json.dump({"expectNotVerified": ["artifact elsewhere"]}, handle)
        rulescorpus.build_and_verify(path, read)
        with open(rulescorpus.companions(path)[1], "w", encoding="utf-8") as handle:
            json.dump({"expectNotVerified": []}, handle)
        self.assert_refused(path, "not-verified: artifact elsewhere")


class TestNoFallback(RulesCorpusCase):
    """When the pinned rules-corpus is not there to ask, nothing is verified and nothing hashes instead."""

    def cache(self):
        return mock.patch.dict(os.environ, {"XDG_CACHE_HOME": os.path.join(self.tmp, "cache")})

    def test_a_rules_corpus_that_cannot_be_fetched_verifies_nothing(self):
        path = self.corpus()
        declaration = {"hashDerivation": DERIVATION, "contentHash": "0" * 64, "asOf": None}
        with self.cache(), mock.patch.object(rulescorpus, "REPOSITORY", os.path.join(self.tmp, "no-such-repository")):
            with self.assertRaises(rulescorpus.Unavailable) as raised:
                rulescorpus.build_and_verify(path, read)
            self.assertIn("cannot fetch rules-corpus", str(raised.exception))
            # Through intake, the only verification there is: refused, with no digest computed.
            with self.assertRaises(intake.Refused) as refused:
                intake.verify_declared_corpus("invented", declaration, path)
            self.assertIn("cannot fetch rules-corpus", str(refused.exception))
        self.assertFalse(hasattr(intake, "HASH_DERIVATIONS"), "a digest recipe is back in intake")

    def test_a_checkout_that_is_not_the_pinned_commit_is_refused(self):
        with self.cache():
            target = os.path.join(rulescorpus._cache_root(), rulescorpus.COMMIT)
            os.makedirs(target)
            for argv in (["git", "init", "-q"], ["git", "-c", "user.name=t", "-c", "user.email=t@t",
                                                   "commit", "-q", "--allow-empty", "-m", "not the pin"]):
                subprocess.run(argv, cwd=target, check=True)
            with self.assertRaises(rulescorpus.Unavailable) as raised:
                rulescorpus.checkout()
        self.assertIn(f"not the pinned {rulescorpus.COMMIT}", str(raised.exception))

    def test_a_checkout_with_an_edited_tracked_file_is_refused(self):
        pinned = rulescorpus.checkout()
        with self.cache():
            target = os.path.join(rulescorpus._cache_root(), rulescorpus.COMMIT)
            subprocess.run(["git", "clone", "-q", "--no-checkout", pinned, target], check=True)
            subprocess.run(["git", "-C", target, "checkout", "-q", "--detach", rulescorpus.COMMIT], check=True)
            with open(os.path.join(target, "README.md"), "a", encoding="utf-8") as handle:
                handle.write("\nedited\n")
            with self.assertRaises(rulescorpus.Unavailable) as raised:
                rulescorpus.checkout()
        self.assertIn("has modified tracked files", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
