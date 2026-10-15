#!/usr/bin/env python3
"""A map may cite a USLM corpus beside another corpus (0042, #660).

`EcfrXml.portion_of` divides a shared extent between the corpora a map cites. `UslmXml` inherited
the base, which returns the whole extent and claims nothing, so a map citing a USLM corpus beside
a second one handed each adapter the other's sections -- the USLM adapter was refused on
`§ 316.1` -- or, were the extent shaped to avoid that, was stopped by the check that every extent
section is claimed by some corpus.

Watched here, over the committed CAN-SPAM corpora (the chapter of the Code and 16 CFR Part 316)
and a stub map that has no entries to speak of:

  * the joint stub inventories every unit of both corpora, each under its own corpus, by key,
    none twice and none left out;
  * a section no cited corpus holds is refused, and so is one two cited corpora both hold;
  * a lone corpus is still handed the whole extent, so a section it does not hold is refused
    by its own adapter, as before the extent was divided;
  * `UslmXml.portion_of` claims the statute sections and the court rules it holds, and neither
    the other form nor a section of the other title.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout, redirect_stderr

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
CAN_SPAM = os.path.join(REPO, "examples", "can-spam")

sys.path.insert(0, TOOLS)
try:
    from mapper import cli
    from mapper.corpus import EcfrXml, UslmXml
finally:
    sys.path.remove(TOOLS)

STATUTE = "usc-15-ch103"
REGULATION = "cfr-16-316"
SECTIONS = [f"/us/usc/t15/s{number}" for number in range(7701, 7714)]
RULES = [f"§ 316.{number}" for number in range(1, 7)]
EXTENT = {"unit": "section-designation", "sections": SECTIONS + RULES}


def declared(source_id, name, adapter):
    return {"sourceId": source_id, "adapter": adapter, "locatorGrammar": "section-designation",
            "committedPath": name, "contentHash": "x" * 64, "hashDerivation": "stub",
            "asOf": "2026-01-01", "verification": "committed-copy",
            "licence": "public-domain-us-government", "quotation": "verbatim",
            "randomness": "none", "boundaryPolicy": "pin-in-repo"}


class JointStub(unittest.TestCase):
    """A stub map over the two CAN-SPAM corpora: an extent, a manifest, and one placeholder
    entry that makes the second corpus cited. No provision is mapped."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uslm-portion-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name in ("usc15-ch103.xml", "part316.xml"):
            shutil.copy(os.path.join(CAN_SPAM, name), self.tmp)

    def write(self, name, document):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        return path

    def stub(self, extent, corpora, principal=STATUTE, cited=(REGULATION,)):
        self.write("corpus-manifest.json", {"schemaVersion": 1, "corpora": corpora})
        return self.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": principal, "extent": extent,
            "entries": [{"id": f"stub-{source}", "locator": {"sourceId": source, "citation": "x"},
                         "evidence": "x"} for source in cited]})

    def both(self):
        return [declared(STATUTE, "usc15-ch103.xml", "uslm-xml"),
                declared(REGULATION, "part316.xml", "ecfr-xml")]

    def walks(self, path):
        return cli._walks(types.SimpleNamespace(map_path=path, manifest=None))

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue() + err.getvalue()


class TestTheJointStubIsInventoried(JointStub):
    def test_every_unit_of_both_corpora_is_walked_under_its_own_corpus(self):
        walks = {w.source: w for w in self.walks(self.stub(EXTENT, self.both()))}
        self.assertEqual(set(walks), {STATUTE, REGULATION})
        statute = UslmXml(os.path.join(CAN_SPAM, "usc15-ch103.xml")).units(
            {"unit": "section-designation", "sections": SECTIONS})
        regulation = EcfrXml(os.path.join(CAN_SPAM, "part316.xml")).units(
            {"unit": "section-designation", "sections": RULES})
        self.assertEqual(len(statute), 265)
        self.assertEqual(len(regulation), 60)
        self.assertEqual([u.key for u in walks[STATUTE].units], [u.key for u in statute])
        self.assertEqual([u.key for u in walks[REGULATION].units], [u.key for u in regulation])

    def test_no_unit_is_walked_twice_and_none_is_left_out(self):
        walks = self.walks(self.stub(EXTENT, self.both()))
        for walk in walks:
            keys = [u.key for u in walk.units]
            self.assertEqual(len(keys), len(set(keys)), walk.source)
        self.assertEqual(sum(len(w.units) for w in walks), 265 + 60)

    def test_the_inventory_reports_each_corpus_and_the_total(self):
        _, output = self.run_cli("inventory", self.stub(EXTENT, self.both()))
        self.assertIn(f"--- {STATUTE}", output)
        self.assertIn(f"--- {REGULATION}", output)
        self.assertIn("enumerated:  265 unit(s)", output)
        self.assertIn("enumerated:  60 unit(s)", output)
        self.assertIn("total across 2 corpora: 325 unit(s)", output)

    def test_it_does_not_matter_which_corpus_is_the_principal_one(self):
        path = self.stub(EXTENT, self.both(), principal=REGULATION, cited=(STATUTE,))
        self.assertEqual(sum(len(w.units) for w in self.walks(path)), 325)


class TestEverySectionIsClaimedByExactlyOneCorpus(JointStub):
    def test_a_statute_section_no_cited_corpus_holds_is_refused(self):
        extent = dict(EXTENT, sections=EXTENT["sections"] + ["/us/usc/t15/s9999"])
        code, output = self.run_cli("inventory", self.stub(extent, self.both()))
        self.assertEqual(code, 2, output)
        self.assertIn("/us/usc/t15/s9999", output)
        self.assertIn("claims coverage of nothing", output)

    def test_a_regulation_section_no_cited_corpus_holds_is_refused(self):
        extent = dict(EXTENT, sections=EXTENT["sections"] + ["§ 316.99"])
        code, output = self.run_cli("inventory", self.stub(extent, self.both()))
        self.assertEqual(code, 2, output)
        self.assertIn("§ 316.99", output)
        self.assertIn("claims coverage of nothing", output)

    def test_a_section_two_cited_corpora_both_hold_is_refused(self):
        """The chapter, pinned twice under two names: every section is in both. Walking it twice
        would count every unit of it twice and call the total a measurement."""
        shutil.copy(os.path.join(CAN_SPAM, "usc15-ch103.xml"),
                    os.path.join(self.tmp, "usc15-ch103-copy.xml"))
        corpora = self.both() + [declared("usc-15-ch103-copy", "usc15-ch103-copy.xml", "uslm-xml")]
        path = self.stub(EXTENT, corpora, cited=(REGULATION, "usc-15-ch103-copy"))
        code, output = self.run_cli("inventory", path)
        self.assertEqual(code, 2, output)
        self.assertIn("/us/usc/t15/s7701", output)
        self.assertIn("more than one corpus", output)


class TestALoneCorpusKeepsItsOwnRefusal(JointStub):
    """One corpus has nothing to divide the extent with, so it is handed all of it and its own
    adapter says what it does not contain."""

    def test_a_lone_statute_corpus_refuses_a_section_it_does_not_hold(self):
        extent = {"unit": "section-designation", "sections": SECTIONS + ["/us/usc/t15/s9999"]}
        path = self.stub(extent, self.both()[:1], cited=())
        code, output = self.run_cli("inventory", path)
        self.assertEqual(code, 2, output)
        self.assertIn("/us/usc/t15/s9999, which the corpus does not contain", output)

    def test_a_lone_regulation_corpus_refuses_a_section_it_does_not_hold(self):
        extent = {"unit": "section-designation", "sections": RULES + ["§ 316.99"]}
        path = self.stub(extent, self.both()[1:], principal=REGULATION, cited=())
        code, output = self.run_cli("inventory", path)
        self.assertEqual(code, 2, output)
        self.assertIn("§ 316.99, which the corpus does not contain", output)


class TestWhatTheStatuteAdapterClaims(unittest.TestCase):
    def setUp(self):
        self.adapter = UslmXml(os.path.join(CAN_SPAM, "usc15-ch103.xml"))

    def test_it_claims_the_statute_sections_it_prints_and_nothing_else(self):
        extent = {"unit": "section-designation",
                  "sections": ["§ 316.1", "/us/usc/t15/s7704", "/us/usc/t15/s9999",
                               "/us/usc/t26/s7704", "Rule 6", "/us/usc/t15/s7701"]}
        portion, mine = self.adapter.portion_of(extent)
        self.assertEqual(portion["sections"], ["/us/usc/t15/s7704", "/us/usc/t15/s7701"])
        self.assertEqual(mine, {"/us/usc/t15/s7704", "/us/usc/t15/s7701"})
        self.assertEqual(portion["unit"], "section-designation")

    def test_it_claims_nothing_of_an_extent_in_another_unit(self):
        extent = {"unit": "page", "sections": ["/us/usc/t15/s7704"]}
        self.assertEqual(self.adapter.portion_of(extent), (extent, None))

    def test_the_court_rules_walk_claims_its_rules(self):
        path = os.path.join(REPO, "examples", "frcp-6-12-81")
        corpus = [os.path.join(path, name) for name in sorted(os.listdir(path))
                  if name.endswith(".xml")]
        self.assertTrue(corpus, "the court-rule example holds no XML corpus")
        adapter = UslmXml(corpus[0])
        extent = {"unit": "section-designation",
                  "sections": ["Rule 6", "Rule 9999", "§ 316.1", "/us/usc/t15/s7704"]}
        portion, mine = adapter.portion_of(extent)
        self.assertEqual(portion["sections"], ["Rule 6"])
        self.assertEqual(mine, {"Rule 6"})


if __name__ == "__main__":
    unittest.main()
