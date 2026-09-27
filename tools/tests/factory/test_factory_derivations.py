#!/usr/bin/env python3
"""A scan with no text layer has a hashDerivation of its own (#499).

`HASH_DERIVATIONS` is closed, and a corpus whose derivation is not in it is refused. Every entry
in it until now described text a tool produced. A published source can also be a **scan**: a PDF
carrying page images and no text layer, from which `pdftotext` returns nothing. The only text
such a source can have is one a reader transcribed from the page images, and the honest name for
that says so.

Watched here: the entry exists, it is SHA-256 over the committed bytes exactly as the other
page-marked entry is, and the closed set is still closed -- a near-miss spelling is refused, and
so is a corpus whose committed bytes have moved off the digest it declares.

The fixtures are invented. No transcription of any real proprietary source appears in this
repository.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest

FACTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "factory")
_spec = importlib.util.spec_from_file_location("factory_intake_derivations", os.path.join(FACTORY, "intake.py"))
intake = importlib.util.module_from_spec(_spec)
# Loading by path caches bytecode beside the source, and the factory refuses to run with a `.pyc`
# it did not write (#373) -- so this import, like validate.sh's whole run, leaves none behind.
_writes_bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
try:
    _spec.loader.exec_module(intake)
finally:
    sys.dont_write_bytecode = _writes_bytecode

TRANSCRIBED = "transcribed-from-page-images-page-marked"
CORPUS = b"{1}\nA synthetic page-marked transcription.\n1\n"


class TestTranscribedFromPageImages(unittest.TestCase):
    def test_the_derivation_is_registered(self):
        self.assertIn(TRANSCRIBED, intake.HASH_DERIVATIONS)

    def test_it_is_sha256_over_the_committed_bytes(self):
        self.assertEqual(hashlib.sha256(CORPUS).hexdigest(),
                         intake.HASH_DERIVATIONS[TRANSCRIBED](CORPUS))

    def test_a_corpus_declaring_it_verifies_against_its_committed_bytes(self):
        digest = hashlib.sha256(CORPUS).hexdigest()
        corpus = {"hashDerivation": TRANSCRIBED, "contentHash": digest}
        self.assertEqual(digest, intake.verify_declared_corpus_digest(
            "synthetic-scan", corpus, CORPUS, "synthetic.txt"))

    def test_bytes_that_moved_are_refused(self):
        corpus = {"hashDerivation": TRANSCRIBED, "contentHash": hashlib.sha256(CORPUS).hexdigest()}
        with self.assertRaises(intake.Refused) as raised:
            intake.verify_declared_corpus_digest("synthetic-scan", corpus, CORPUS + b"\n", "synthetic.txt")
        self.assertIn(TRANSCRIBED, str(raised.exception))

    def test_the_set_is_still_closed(self):
        for near_miss in ("transcribed-from-page-images",
                          "page-images-transcribed-page-marked",
                          "Transcribed-From-Page-Images-Page-Marked"):
            with self.subTest(derivation=near_miss):
                corpus = {"hashDerivation": near_miss, "contentHash": hashlib.sha256(CORPUS).hexdigest()}
                with self.assertRaises(intake.Refused) as raised:
                    intake.verify_declared_corpus_digest("synthetic-scan", corpus, CORPUS, "synthetic.txt")
                self.assertIn("no way to compute hashDerivation", str(raised.exception))

    def test_read_corpus_reads_a_committed_transcription_whole(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "synthetic.txt")
            with open(path, "wb") as handle:
                handle.write(CORPUS)
            self.assertEqual(CORPUS, intake.read_corpus(path))


if __name__ == "__main__":
    unittest.main()
