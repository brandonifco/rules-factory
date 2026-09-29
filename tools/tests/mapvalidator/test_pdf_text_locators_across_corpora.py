#!/usr/bin/env python3
"""The page-marked locator run checks each entry against the corpus its own `locator.sourceId`
names (#529).

`check-locators-section.py` learned this in #298 for two eCFR sections. The page-marked checker
never did, so a map citing two page-marked corpora could not be packed: `pack-map.py` refused it as
NOT VERIFIED, accurately. Watched here:

  * two page-marked corpora, each named by the `sourceId` its entries cite, are read in one run
    and each entry is checked against **its own**;
  * a corpus of the run that the map does not cite is not an error, but an entry citing a corpus
    the run was **not given** fails rather than reporting unchecked;
  * an entry whose quote is only in the *other* corpus fails -- the check is per corpus, not
    against whichever text happens to contain the words;
  * the page cited is the page of the entry's own corpus;
  * the map's page `extent` describes the principal corpus, and a secondary corpus makes no extent
    claim: the run says so as NOT VERIFIED, and does not pass it silently;
  * the one-bare-path form is unchanged for a one-corpus map, and refused for a map citing two,
    where it would silently check every entry against whichever file it was handed;
  * a corpus named twice, or an argument that is not `<sourceId>=<path>`, is a usage error.

The corpora are synthetic. No real source is admitted by this test.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
TOOL = os.path.join(REPO, "examples", "srd-52-combat", "check-locators-pdf-text.py")
_spec = importlib.util.spec_from_file_location("check_locators_pdf_text_many", TOOL)
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

PROSE = """{1}
Widgets
A widget is played by two persons.
{2}
Rounds
The winner of a round moves first.
"""

GRID = """{1}
{2}
{3}
Front side
Left column
Row 1
Take one widget.
Right column
Row 1
Pass the widget.
"""


def entry(eid, source, citation, evidence):
    return {"id": eid, "locator": {"sourceId": source, "citation": citation}, "evidence": evidence}


def map_document():
    return {
        "schemaVersion": 1,
        "corpus": "prose",
        "baseline": {"contentHash": "a" * 64, "hashDerivation": "demo"},
        "extent": {"unit": "page", "from": 1, "to": 2},
        "entries": [
            entry("players", "prose", "Widgets / p. 1", "A widget is played by two persons."),
            entry("winner-first", "prose", "Rounds / p. 2", "The winner of a round moves first."),
            entry("take-one", "grid", "Front side / Left column / Row 1 / p. 3", "Take one widget."),
            entry("pass-it", "grid", "Front side / Right column / Row 1 / p. 3", "Pass the widget."),
        ],
    }


class PdfTextLocatorsAcrossCorpora(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp, True))
        self.prose = self.write("prose.txt", PROSE)
        self.grid = self.write("grid.txt", GRID)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_tool(self, document, *args):
        path = os.path.join(self.tmp, "corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = tool.main([path, *args])
        return code, out.getvalue()

    def both(self):
        return f"prose={self.prose}", f"grid={self.grid}"

    # --- the defect -----------------------------------------------------------------------

    def test_two_corpora_each_named_by_its_source_id_pass(self):
        code, output = self.run_tool(map_document(), *self.both())
        self.assertEqual(code, 0, output)
        self.assertIn("[ok] locators", output)

    def test_each_entry_is_checked_against_its_own_corpus(self):
        document = map_document()
        # The words are in the prose corpus only; the entry says the grid corpus holds them.
        document["entries"][2] = entry("take-one", "grid", "Front side / Left column / Row 1 / p. 3",
                                       "A widget is played by two persons.")
        code, output = self.run_tool(document, *self.both())
        self.assertNotEqual(code, 0, output)
        self.assertIn("take-one", output)

    def test_the_page_is_the_page_of_the_entrys_own_corpus(self):
        document = map_document()
        document["entries"][3]["locator"]["citation"] = "Front side / Right column / Row 1 / p. 1"
        code, output = self.run_tool(document, *self.both())
        self.assertNotEqual(code, 0, output)
        self.assertIn("pass-it", output)

    def test_a_corpus_the_run_was_not_given_fails_naming_it(self):
        code, output = self.run_tool(map_document(), f"prose={self.prose}")
        self.assertNotEqual(code, 0, output)
        self.assertIn("grid", output)
        self.assertIn("take-one", output)

    # --- what a secondary corpus does not claim -------------------------------------------

    def test_a_secondary_corpus_makes_no_extent_claim_and_says_so(self):
        code, output = self.run_tool(map_document(), *self.both())
        self.assertEqual(code, 0, output)
        self.assertIn("grid", output)
        self.assertRegex(output, r"(?is)== corpus grid.*\[skip\] extent: NOT VERIFIED")

    def test_the_principal_corpus_is_still_held_to_its_extent(self):
        document = map_document()
        document["extent"]["to"] = 3      # page 3 of the prose corpus does not exist
        code, output = self.run_tool(document, *self.both())
        self.assertNotEqual(code, 0, output)

    # --- what must not move ---------------------------------------------------------------

    def test_the_one_bare_path_form_is_unchanged_for_a_one_corpus_map(self):
        document = map_document()
        document["entries"] = document["entries"][:2]
        code, output = self.run_tool(document, self.prose)
        self.assertEqual(code, 0, output)
        self.assertIn("[ok] locators", output)

    def test_the_bare_path_form_is_refused_for_a_map_citing_two_corpora(self):
        code, output = self.run_tool(map_document(), self.prose)
        self.assertNotEqual(code, 0, output)
        self.assertIn("sourceId", output)

    def test_a_corpus_given_twice_is_a_usage_error(self):
        code, output = self.run_tool(map_document(), f"prose={self.prose}", f"prose={self.prose}")
        self.assertEqual(code, 2, output)

    def test_a_malformed_corpus_argument_is_a_usage_error(self):
        code, output = self.run_tool(map_document(), f"prose={self.prose}", self.grid)
        self.assertEqual(code, 2, output)


if __name__ == "__main__":
    unittest.main()
