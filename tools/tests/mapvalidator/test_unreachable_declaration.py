#!/usr/bin/env python3
"""A map declares the passages its grammar has no address for, and what reaching each requires.

Decision 0038, [#299](https://github.com/brandonifco/rules-factory/issues/299). Before this, the
locator run failed whenever **any** paragraph of the corpus had no address -- asked of the whole
document, with the extent not consulted. That is the right invariant: a passage no citation can
name is one a quote could silently be verified against. But it made § 172.101 unpassable for
every map, including a map quoting none of the refused text, because the section's two appendices
are opened by an `HD1` and [0036](../../../docs/decisions/0036-a-paragraph-inside-a-wrapper-takes-the-designation-the-wrapper-continues.md)
is explicit that nothing inside such a wrapper is indexed.

The answer is not to narrow the invariant to the extent -- "inside the extent" is the map's own
claim, so the map would decide what it is checked against. It is for the map to **declare** what
it could not reach, and for the run to hold that declaration to the corpus in both directions.

Watched here:

  * a declaration covering every refused passage lets the run pass, and the run says how many;
  * a refused passage the map does **not** declare still fails, which is the invariant unmoved;
  * a declaration the walk **reaches** fails -- a stale bound is not a bound;
  * a declaration naming the wrong `reason` fails, so the map cannot mislabel why it could not
    look;
  * a declaration with no `requires` fails: "I could not reach it" without "and this is what it
    would take" is the silence the field exists to break;
  * `reason` is a closed set, and the set `check-map.py` enforces is **the same set** the walk
    produces -- a vocabulary copied and left to drift would let a map declare a reason no run can
    give.

The corpus is a synthetic eCFR-shaped fixture. § 172.101 is the corpus that forced this, and it
is measured in the pull request, not here.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

sys.path.insert(0, TOOLS)
try:
    from mapvalidator import extent as extent_module
finally:
    sys.path.remove(TOOLS)

SECTION_TOOL = os.path.join(REPO, "examples", "faa-part-107", "check-locators-section.py")
_spec = importlib.util.spec_from_file_location("check_locators_section", SECTION_TOOL)
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

# One ordinary paragraph, and an appendix opened by an HD1 -- the shape of § 172.101, at a size
# that fits on a screen. The appendix holds two paragraphs, and neither can be addressed.
CORPUS = """<ROOT><DIV8 N="9.101" TYPE="SECTION"><HEAD>&#167; 9.101 The table.</HEAD>
<P>(a) Each material is listed in the table with the provisions that apply to it.</P>
<EXTRACT><HD1>Appendix A to &#167; 9.101&#8212;List of Reportable Quantities</HD1>
<P>1. This appendix lists materials and their reportable quantities.</P>
<P>2. This appendix is divided into two tables.</P>
</EXTRACT></DIV8></ROOT>"""

APPENDIX = ("Appendix A to § 9.101—List of Reportable Quantities",
            "1. This appendix lists materials and their reportable quantities.",
            "2. This appendix is divided into two tables.")

REQUIRES = "a citation grammar for a section's appendices, which 0036 declined to give one"


def declaration(opens, reason="division-wrapper", requires=REQUIRES, source="cfr-9-9.101"):
    return {"sourceId": source, "opensWith": opens[:60], "reason": reason, "requires": requires}


BASE = {
    "schemaVersion": 1,
    "corpus": "cfr-9-9.101",
    "extent": {"unit": "section-designation", "sections": ["§ 9.101"]},
    "entries": [{
        "id": "listed-in-the-table",
        "locator": {"sourceId": "cfr-9-9.101", "citation": "§ 9.101(a)"},
        "evidence": "Each material is listed in the table with the provisions that apply to it.",
    }],
}


def with_unreachable(items):
    document = json.loads(json.dumps(BASE))
    if items is not None:
        document["extent"]["unreachable"] = items
    return document


class TheRunHoldsTheDeclarationToTheCorpus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.corpus = os.path.join(self.tmp, "section-9.101.xml")
        with open(self.corpus, "w", encoding="utf-8") as handle:
            handle.write(CORPUS)

    def run_tool(self, document):
        path = os.path.join(self.tmp, "corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = checker.main(["check-locators-section.py", path, self.corpus])
        return code, out.getvalue() + err.getvalue()

    def test_a_declaration_covering_every_refusal_passes(self):
        code, output = self.run_tool(with_unreachable([declaration(t) for t in APPENDIX]))
        self.assertEqual(code, 0, output)
        self.assertIn("3 passage(s) with no address, every one declared", output)
        self.assertIn("locators ok", output)

    def test_an_undeclared_refusal_still_fails(self):
        code, output = self.run_tool(with_unreachable([declaration(t) for t in APPENDIX[:2]]))
        self.assertNotEqual(code, 0, output)
        self.assertIn("the map does not declare it", output)
        self.assertIn(APPENDIX[2][:40], output)

    def test_declaring_nothing_fails_exactly_as_before(self):
        code, output = self.run_tool(with_unreachable(None))
        self.assertNotEqual(code, 0, output)
        self.assertIn("the map does not declare it", output)

    def test_a_declaration_the_walk_reaches_fails(self):
        items = [declaration(t) for t in APPENDIX]
        items.append(declaration("(a) Each material is listed in the table with the provisions"))
        code, output = self.run_tool(with_unreachable(items))
        self.assertNotEqual(code, 0, output)
        self.assertIn("this run places it", output)

    def test_a_declaration_naming_the_wrong_reason_fails(self):
        items = [declaration(t) for t in APPENDIX]
        items[1] = declaration(APPENDIX[1], reason="ambiguous-designator")
        code, output = self.run_tool(with_unreachable(items))
        self.assertNotEqual(code, 0, output)
        self.assertIn("declared unreachable for 'ambiguous-designator'", output)

    def test_a_declaration_with_no_requires_fails(self):
        items = [declaration(t) for t in APPENDIX]
        items[0] = declaration(APPENDIX[0], requires="")
        code, output = self.run_tool(with_unreachable(items))
        self.assertNotEqual(code, 0, output)
        self.assertIn("says nothing about what reaching it would require", output)


class TheVocabularyHasOneSource(unittest.TestCase):
    def test_the_checker_and_check_map_close_the_same_set(self):
        """A reason a map may declare is exactly a reason a walk can give."""
        self.assertEqual(set(extent_module.UNREACHABLE_REASONS),
                         set(checker.UNREACHABLE_REASONS))

    def test_every_reason_is_produced_somewhere_in_the_walk(self):
        """Not a list someone can extend without a refusal that gives it."""
        source = open(SECTION_TOOL, encoding="utf-8").read()
        for reason in checker.UNREACHABLE_REASONS:
            self.assertIn(f'("{reason}"', source,
                          f"{reason} is in the vocabulary and nothing in the walk emits it")


if __name__ == "__main__":
    unittest.main()
