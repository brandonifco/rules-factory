#!/usr/bin/env python3
"""The locator run checks each entry against the corpus its own `locator.sourceId` names (#298).

Every map admitted before trial 10 cited one corpus, so the run took one map and one file and
checked every entry against it. Trial 10 admits two -- the eCFR serves § 172.101 and § 172.102 as
two documents with two hashes -- and every column 7 pointer crosses between them: a code printed
in § 172.101's table is stated in § 172.102. Run against either file alone, neither pass is
possible: the other corpus's entries report unchecked and `coverage` then fails, because the
extent names both sections and only one of them is in the file being read.

Watched here:

  * two corpora, each named by the `sourceId` its entries cite, are indexed in one run and each
    entry is checked against **its own**, so a map spanning two corpora can pass;
  * an entry citing a corpus the run was **not given** fails, rather than reporting unchecked --
    a map that names a corpus nobody read is not a map this tool verified;
  * `coverage` is computed over every corpus of the run, so a section of the declared extent is
    reached by evidence in whichever corpus holds it;
  * the one-bare-path form is **unchanged** for a single-corpus map, which is what the four
    committed eCFR runs use;
  * and that form is **refused** for a map whose entries cite more than one corpus, where it
    would silently check every entry against whichever file it was handed.

The corpora are synthetic eCFR-shaped fixtures written here. No real corpus is admitted by this
test.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

SECTION_TOOL = os.path.join(REPO, "examples", "faa-part-107", "check-locators-section.py")
_spec = importlib.util.spec_from_file_location("check_locators_section", SECTION_TOOL)
check_locators_section = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_locators_section)

# Two sections served as two documents, in the shape the eCFR versioner serves one section in:
# a bare DIV8 with no subpart around it (trial 9 generalised the walk to read that).
FIRST = """<ROOT><DIV8 N="9.101" TYPE="SECTION"><HEAD>&#167; 9.101 The table.</HEAD>
<P>(a) Each material is listed in the table with the provisions that apply to it.</P>
<P>(b) A code in column 7 is a special provision stated in &#167; 9.102.</P>
</DIV8></ROOT>"""

SECOND = """<ROOT><DIV8 N="9.102" TYPE="SECTION"><HEAD>&#167; 9.102 Special provisions.</HEAD>
<P>(a) A special provision is in addition to the requirements of the table.</P>
<P>(b) A code containing the letter W applies only to transportation by water.</P>
</DIV8></ROOT>"""


def entry(eid, source, citation, evidence):
    return {"id": eid, "locator": {"sourceId": source, "citation": citation},
            "evidence": evidence}


MAP = {
    "schemaVersion": 1,
    "corpus": "cfr-9-9.101",
    "extent": {"unit": "section-designation", "sections": ["§ 9.101", "§ 9.102"]},
    "entries": [
        entry("listed-in-the-table", "cfr-9-9.101", "§ 9.101(a)",
              "Each material is listed in the table with the provisions that apply to it."),
        entry("w-is-water-only", "cfr-9-9.102", "§ 9.102(b)",
              "A code containing the letter W applies only to transportation by water."),
    ],
}


class LocatorsAcrossCorpora(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))
        self.first = self.write("section-9.101.xml", FIRST)
        self.second = self.write("section-9.102.xml", SECOND)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def map_at(self, document, name="corpus-map.json"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        return path

    def run_tool(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_locators_section.main(["check-locators-section.py", *args])
        return code, out.getvalue() + err.getvalue()

    # --- the defect -----------------------------------------------------------------------

    def test_two_corpora_each_named_by_its_source_id_pass(self):
        code, output = self.run_tool(self.map_at(MAP),
                                     f"cfr-9-9.101={self.first}", f"cfr-9-9.102={self.second}")
        self.assertEqual(code, 0, output)
        self.assertIn("locators ok", output)
        self.assertIn("coverage ok", output)

    def test_one_corpus_of_the_two_cannot_pass(self):
        """What #298 measured: each single-file run leaves the other corpus's entries unchecked."""
        code, output = self.run_tool(self.map_at(MAP), self.first)
        self.assertNotEqual(code, 0, output)

    def test_an_entry_citing_a_corpus_the_run_was_not_given_fails(self):
        document = json.loads(json.dumps(MAP))
        document["entries"].append(
            entry("stated-elsewhere", "cfr-9-9.103", "§ 9.103(a)",
                  "A special provision is in addition to the requirements of the table."))
        document["extent"]["sections"].append("§ 9.103")
        code, output = self.run_tool(self.map_at(document),
                                     f"cfr-9-9.101={self.first}", f"cfr-9-9.102={self.second}")
        self.assertNotEqual(code, 0, output)
        self.assertIn("cfr-9-9.103", output)
        self.assertIn("stated-elsewhere", output)

    # --- what must not move ---------------------------------------------------------------

    def test_the_one_bare_path_form_is_unchanged(self):
        document = json.loads(json.dumps(MAP))
        document["entries"] = [document["entries"][0]]
        document["extent"]["sections"] = ["§ 9.101"]
        code, output = self.run_tool(self.map_at(document), self.first)
        self.assertEqual(code, 0, output)
        self.assertIn("locators ok", output)

    def test_the_bare_path_form_is_refused_for_a_map_citing_two_corpora(self):
        code, output = self.run_tool(self.map_at(MAP), self.first)
        self.assertEqual(code, 2, output)
        self.assertIn("cfr-9-9.102", output)

    def test_a_corpus_given_twice_is_a_usage_error(self):
        code, output = self.run_tool(self.map_at(MAP),
                                     f"cfr-9-9.101={self.first}", f"cfr-9-9.101={self.second}")
        self.assertEqual(code, 2, output)

    def test_a_malformed_corpus_argument_is_a_usage_error(self):
        code, output = self.run_tool(self.map_at(MAP), f"cfr-9-9.101={self.first}", self.second)
        self.assertEqual(code, 2, output)


if __name__ == "__main__":
    unittest.main()
