#!/usr/bin/env python3
"""The page-marked grammar has a name that does not name a tool (#499).

`PageMarkedPdfText` reads a text whose pages are separated by `{N}` on a line of its own, and
whose units are the blank-line-separated blocks between them. Nothing in it is `pdftotext`'s --
only its registered name, `pdftotext-page-marked`, which was accurate when the only such corpus
came out of `extract.py`.

A scan with no text layer produces the same grammar by a different route: `pdftotext` returns
nothing from it, so the text is transcribed from the page images. Declaring `pdftotext-page-marked`
for that corpus would put a tool in the manifest that never ran. `page-marked-text` is the same
reader under a name that says only what is true of the bytes.

Watched here: the name resolves, it reads a synthetic corpus into exactly the units the
pdftotext-named adapter reads it into, and the older name still resolves to the same reader --
published maps and the four committed SRD manifests declare it.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from mapper import corpus as corpus_module  # noqa: E402

# A page-marked text as the grammar means it: `{N}` on a line of its own, and a blank line
# between blocks -- including the one before the next page's marker, without which the last
# block of a page and the first of the next are one block with the marker line removed.
PAGE_MARKED = ("{1}\nFirst Heading\n\nA synthetic block.\n\n1\n\n"
               "{2}\nSecond Heading\n\nAnother block.\n\n2\n")


class TestPageMarkedTextAdapter(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.directory, True)
        self.path = os.path.join(self.directory, "synthetic.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(PAGE_MARKED)

    def test_the_generic_name_resolves(self):
        self.assertIn("page-marked-text", corpus_module.ADAPTERS)

    def test_the_tool_named_spelling_still_resolves(self):
        self.assertIn("pdftotext-page-marked", corpus_module.ADAPTERS)

    def test_both_names_read_the_same_units(self):
        extent = {"unit": "page", "from": 1, "to": 2}
        generic = corpus_module.ADAPTERS["page-marked-text"](self.path).units(extent)
        named = corpus_module.ADAPTERS["pdftotext-page-marked"](self.path).units(extent)
        self.assertEqual([(unit.key, unit.text) for unit in named],
                         [(unit.key, unit.text) for unit in generic])
        self.assertEqual([("p. 1 block 1", "First Heading"),
                          ("p. 1 block 2", "A synthetic block."),
                          ("p. 1 block 3", "1"),
                          ("p. 2 block 1", "Second Heading"),
                          ("p. 2 block 2", "Another block."),
                          ("p. 2 block 3", "2")],
                         [(unit.key, unit.text) for unit in generic])


if __name__ == "__main__":
    unittest.main()
