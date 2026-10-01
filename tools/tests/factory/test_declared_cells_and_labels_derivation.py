#!/usr/bin/env python3
"""A born-digital board whose cells are declared, and whose artwork is labelled by a reader, has
a hashDerivation of its own (#527).

`intake.ADMITTED_HASH_DERIVATIONS` is closed, and a printed game board fits none of its page-marked names. Its
action-space text is real text in the layer, read by grid position rather than by reading order,
so a committed declaration of cell rectangles (geometry, never text) makes those bytes
mechanically re-derivable -- which `...declared-reading-order-page-marked` claims for prose and
`transcribed-from-page-images-page-marked` disclaims altogether. But what the board prints as
artwork -- which spaces bear a flag, the tables of a track -- is not in the layer at all, and a
corpus that wants it quotable carries it as labels a reader wrote. The name has to say both.

Watched here: the name is admitted, rules-corpus's baseline for it is SHA-256 over the committed bytes like its siblings, a
corpus whose bytes have moved is refused, the closed set stays closed against a near-miss
spelling, and neither of the two names it sits beside is displaced or reused.

The fixtures are invented. No text of any real proprietary source appears in this repository.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest

FACTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "factory")
_spec = importlib.util.spec_from_file_location("factory_intake_declared_order",
                                               os.path.join(FACTORY, "intake.py"))
intake = importlib.util.module_from_spec(_spec)
# Loading by path caches bytecode beside the source, and the factory refuses to run with a `.pyc`
# it did not write (#373) -- so this import, like validate.sh's whole run, leaves none behind.
_writes_bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
sys.path.insert(0, FACTORY)  # intake imports rulescorpus beside it
try:
    _spec.loader.exec_module(intake)
finally:
    sys.dont_write_bytecode = _writes_bytecode

DECLARED = "pdftotext-24.02.0-bbox-layout-declared-cells-and-artwork-labels-page-marked"
CORPUS = b"{1}\nA synthetic board, cells read by declared position.\n1\n"

from tests.factory.corpus_recipe import write_corpus  # noqa: E402


def declared(source_id, corpus, data):
    """The baseline intake accepts for `data` as `corpus`: rules-corpus's SHA-256 of the committed
    bytes, built from a recipe declaring the corpus's own hashDerivation (#558)."""
    with tempfile.TemporaryDirectory() as directory:
        path = write_corpus(directory, "synthetic.txt", data, source_id, corpus["hashDerivation"])
        return intake.verify_declared_corpus(source_id, dict(corpus, asOf=None), path)["baselines"][source_id]["contentHash"]


class TestDeclaredCellsAndLabelsDerivation(unittest.TestCase):
    def test_the_derivation_is_registered(self):
        self.assertIn(DECLARED, intake.ADMITTED_HASH_DERIVATIONS)

    def test_a_corpus_declaring_it_verifies_against_its_committed_bytes(self):
        digest = hashlib.sha256(CORPUS).hexdigest()
        corpus = {"hashDerivation": DECLARED, "contentHash": digest}
        self.assertEqual(digest, declared("synthetic-board", corpus, CORPUS))

    def test_bytes_that_moved_are_refused(self):
        corpus = {"hashDerivation": DECLARED, "contentHash": hashlib.sha256(CORPUS).hexdigest()}
        with self.assertRaises(intake.Refused) as raised:
            declared("synthetic-board", corpus, CORPUS + b"\n")
        self.assertIn(DECLARED, str(raised.exception))

    def test_the_set_is_still_closed_against_a_near_miss(self):
        near = DECLARED.replace("cells-and-artwork-labels", "cells")
        self.assertNotIn(near, intake.ADMITTED_HASH_DERIVATIONS)
        corpus = {"hashDerivation": near, "contentHash": hashlib.sha256(CORPUS).hexdigest()}
        with self.assertRaises(intake.Refused) as raised:
            declared("synthetic-board", corpus, CORPUS)
        self.assertIn(near, str(raised.exception))

    def test_it_does_not_displace_the_names_it_sits_between(self):
        for name in ("srd-5.2.1-pdftotext-24.02.0-page-marked",
                     "transcribed-from-page-images-page-marked",
                     "pdftotext-24.02.0-bbox-layout-declared-reading-order-page-marked"):
            self.assertIn(name, intake.ADMITTED_HASH_DERIVATIONS)


if __name__ == "__main__":
    unittest.main()
