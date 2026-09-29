#!/usr/bin/env python3
"""A born-digital PDF whose reading order is declared has a hashDerivation of its own (#524).

`HASH_DERIVATIONS` is closed. Two of its names describe page-marked text, and a source has
appeared that neither fits. `srd-5.2.1-pdftotext-24.02.0-page-marked` names a straight
`pdftotext` of a PDF whose pages are single columns, where extraction order is reading order.
`transcribed-from-page-images-page-marked` names a scan with no text layer, where a person wrote
the text and no machine can re-derive it.

Between them: a print master whose text layer is real and complete -- so nothing is transcribed
-- but whose extraction order is not its reading order, so a straight `pdftotext` is not the
document either. Such a corpus commits a per-page declaration of which rectangle holds which
column and which holds artwork, and stays mechanically reproducible, which a transcription is
not.

Watched here: the entry exists, it is SHA-256 over the committed bytes exactly as the other two
page-marked entries are, the closed set is still closed against a near-miss spelling, and a
corpus whose committed bytes have moved off its declared digest is refused.

The fixtures are invented. No text of any real proprietary source appears in this repository.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import hashlib
import importlib.util
import os
import sys
import unittest

FACTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "factory")
_spec = importlib.util.spec_from_file_location("factory_intake_declared_order",
                                               os.path.join(FACTORY, "intake.py"))
intake = importlib.util.module_from_spec(_spec)
# Loading by path caches bytecode beside the source, and the factory refuses to run with a `.pyc`
# it did not write (#373) -- so this import, like validate.sh's whole run, leaves none behind.
_writes_bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
try:
    _spec.loader.exec_module(intake)
finally:
    sys.dont_write_bytecode = _writes_bytecode

DECLARED = "pdftotext-24.02.0-bbox-layout-declared-reading-order-page-marked"
CORPUS = b"{1}\nA synthetic two-column page, read in a declared order.\n1\n"


class TestDeclaredReadingOrderDerivation(unittest.TestCase):
    def test_the_derivation_is_registered(self):
        self.assertIn(DECLARED, intake.HASH_DERIVATIONS)

    def test_it_is_sha256_over_the_committed_bytes(self):
        self.assertEqual(hashlib.sha256(CORPUS).hexdigest(),
                         intake.HASH_DERIVATIONS[DECLARED](CORPUS))

    def test_a_corpus_declaring_it_verifies_against_its_committed_bytes(self):
        digest = hashlib.sha256(CORPUS).hexdigest()
        corpus = {"hashDerivation": DECLARED, "contentHash": digest}
        self.assertEqual(digest, intake.verify_declared_corpus_digest(
            "synthetic-print-master", corpus, CORPUS, "synthetic.txt"))

    def test_bytes_that_moved_are_refused(self):
        corpus = {"hashDerivation": DECLARED, "contentHash": hashlib.sha256(CORPUS).hexdigest()}
        with self.assertRaises(intake.Refused) as raised:
            intake.verify_declared_corpus_digest("synthetic-print-master", corpus,
                                                 CORPUS + b"\n", "synthetic.txt")
        self.assertIn(DECLARED, str(raised.exception))

    def test_the_set_is_still_closed_against_a_near_miss(self):
        near = DECLARED.replace("bbox-layout", "bbox")
        self.assertNotIn(near, intake.HASH_DERIVATIONS)
        corpus = {"hashDerivation": near, "contentHash": hashlib.sha256(CORPUS).hexdigest()}
        with self.assertRaises(intake.Refused) as raised:
            intake.verify_declared_corpus_digest("synthetic-print-master", corpus, CORPUS,
                                                 "synthetic.txt")
        self.assertIn(near, str(raised.exception))

    def test_it_does_not_displace_the_names_it_sits_between(self):
        for name in ("srd-5.2.1-pdftotext-24.02.0-page-marked",
                     "transcribed-from-page-images-page-marked"):
            self.assertIn(name, intake.HASH_DERIVATIONS)


if __name__ == "__main__":
    unittest.main()
