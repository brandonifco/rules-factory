#!/usr/bin/env python3
"""The mapper walks every corpus a map cites, not only its principal one (0042).

[#305](https://github.com/brandonifco/rules-factory/issues/305). A map may cite several corpora
([0039](../../../docs/decisions/0039-the-manifest-pins-every-corpus-a-map-cites.md)) and declares
**one** extent across them all. `_walk` opened `document["corpus"]` and nothing else, so
`mapper inventory` and `mapper sweeps` measured one corpus of several.

Measured on trial 10's two admitted corpora before this change:

  * an extent naming **both** sections is **refused outright** -- *"the extent names § 172.102,
    which the corpus does not contain"* -- so the honest map shape could not be measured at all;
  * an extent naming only § 172.101 while entries cite § 172.102 **runs**, enumerates 104 units
    and reports coverage over them, while § 172.102's **612** units are never enumerated. Nothing
    says it looked at one corpus of two, and no sweep could find anything in the other.

The second is the dangerous one: formally green, and a completeness claim over 15% of the map.
That would have invalidated H4.

Watched here:

  * two corpora are walked, each with its own adapter and its own share of the extent;
  * each walk sees **only the entries that cite its corpus**, so an entry of the second corpus is
    not reported unlocated in the first;
  * the inventory reports per corpus **and** a total;
  * the run's verdict is the **worst** of the corpora, so one clean corpus cannot carry another;
  * an extent section **no** cited corpus contains is still refused -- the invariant `units` held
    for one corpus, asked of the union;
  * each corpus's sweeps run under **its own** protocol, and a corpus with no protocol is refused
    rather than swept under another's;
  * a single-corpus map is unchanged, which the five committed maps prove byte for byte.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
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

sys.path.insert(0, TOOLS)
try:
    from mapper import cli, protocol
finally:
    sys.path.remove(TOOLS)

NOT_VERIFIED = 3

FIRST = """<ROOT><DIV8 N="9.101" TYPE="SECTION"><HEAD>&#167; 9.101 The table.</HEAD>
<P>(a) Each material is listed in the table with the provisions that apply to it.</P>
<P>(b) A code in column 7 is a special provision stated in &#167; 9.102 of this subchapter.</P>
</DIV8></ROOT>"""

SECOND = """<ROOT><DIV8 N="9.102" TYPE="SECTION"><HEAD>&#167; 9.102 Special provisions.</HEAD>
<P>(a) A special provision is in addition to the requirements of the table.</P>
<P>(b) A code containing the letter W applies only to transportation by water.</P>
<P>(c) A code containing the letter B applies only to bulk packagings.</P>
</DIV8></ROOT>"""

SECTIONS = (("cfr-9-9.101", "section-9.101.xml", FIRST), ("cfr-9-9.102", "section-9.102.xml", SECOND))

FIRST_QUOTE = "Each material is listed in the table with the provisions that apply to it."
SECOND_QUOTE = "A code containing the letter W applies only to transportation by water."


def a_protocol(source_id, sweeps=("cross-references",)):
    return {"protocolVersion": 1, "corpus": source_id, "units": ["paragraph", "heading"],
            "pointerMechanisms": [{"mechanism": "section-designation"}],
            "requiredSweeps": list(sweeps),
            "adapterReach": {"text": "readable", "illustrations": "unsupported"}}


class TwoCorpusWalk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="walk-every-corpus-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        corpora = []
        for source_id, name, text in SECTIONS:
            with open(os.path.join(self.tmp, name), "w", encoding="utf-8") as handle:
                handle.write(text)
            corpora.append({"sourceId": source_id, "adapter": "ecfr-xml",
                            "locatorGrammar": "section-designation", "committedPath": name,
                            "contentHash": "x" * 64, "hashDerivation": "ecfr-versioner-xml",
                            "asOf": "2026-01-01", "verification": "committed-copy",
                            "licence": "public-domain-us-government", "quotation": "verbatim",
                            "randomness": "none", "boundaryPolicy": "pin-in-repo"})
        self.write("corpus-manifest.json", {"schemaVersion": 1, "corpora": corpora})
        for source_id, _, _ in SECTIONS:
            self.write(protocol.per_corpus_filename(source_id), a_protocol(source_id))

    def write(self, name, document):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        return path

    def a_map(self, sections=("§ 9.101", "§ 9.102"), entries=None):
        return self.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "cfr-9-9.101",
            "extent": {"unit": "section-designation", "sections": list(sections)},
            "entries": entries if entries is not None else [
                {"id": "listed-in-the-table",
                 "locator": {"sourceId": "cfr-9-9.101", "citation": "§ 9.101(a)"},
                 "evidence": FIRST_QUOTE},
                {"id": "w-is-water-only",
                 "locator": {"sourceId": "cfr-9-9.102", "citation": "§ 9.102(b)"},
                 "evidence": SECOND_QUOTE},
            ]})

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue() + err.getvalue()

    # --- the walk --------------------------------------------------------------------------

    def test_both_corpora_are_walked_and_reported(self):
        code, output = self.run_cli("inventory", self.a_map())
        self.assertIn("--- cfr-9-9.101", output)
        self.assertIn("--- cfr-9-9.102", output)
        self.assertIn("total across 2 corpora", output)
        self.assertEqual(code, NOT_VERIFIED, output)  # units neither quoted nor rejected

    def test_the_total_counts_both_corpora(self):
        _, output = self.run_cli("inventory", self.a_map())
        line = [l for l in output.splitlines() if l.startswith("total across")][0]
        # 2 headings + 5 paragraphs across the two sections.
        self.assertIn("7 unit(s)", line)
        self.assertIn("2 entr(ies) located", line)

    def test_an_entry_of_the_second_corpus_is_not_unlocated_in_the_first(self):
        """Each walk measures the entries that cite it, or every multi-corpus map reads as full
        of quotes the mapper cannot find."""
        _, output = self.run_cli("inventory", "--list", self.a_map())
        first = output.split("--- cfr-9-9.102")[0]
        self.assertNotIn("w-is-water-only", first)

    def test_a_section_no_cited_corpus_contains_is_still_refused(self):
        code, output = self.run_cli("inventory", self.a_map(("§ 9.101", "§ 9.102", "§ 9.999")))
        self.assertEqual(code, 2, output)
        self.assertIn("§ 9.999", output)
        self.assertIn("claims coverage of nothing", output)

    # --- the verdict -----------------------------------------------------------------------

    def test_one_clean_corpus_does_not_carry_another(self):
        """Every unit of § 9.101 quoted or rejected; § 9.102 left unaccounted. The run is not a
        pass, because a corpus nobody measured is not measured by another corpus being clean."""
        entries = [{"id": f"first-{i}",
                    "locator": {"sourceId": "cfr-9-9.101", "citation": "§ 9.101(a)"},
                    "evidence": quote}
                   for i, quote in enumerate((FIRST_QUOTE,), 1)]
        entries.append({"id": "second",
                        "locator": {"sourceId": "cfr-9-9.102", "citation": "§ 9.102(b)"},
                        "evidence": SECOND_QUOTE})
        code, output = self.run_cli("inventory", self.a_map(entries=entries))
        self.assertNotEqual(code, 0, output)

    # --- the sweeps ------------------------------------------------------------------------

    def test_each_corpus_is_swept_under_its_own_protocol(self):
        code, output = self.run_cli("sweeps", self.a_map())
        self.assertIn("mapping-protocol-cfr-9-9.101.json", output)
        self.assertIn("mapping-protocol-cfr-9-9.102.json", output)
        self.assertIn("corpus 'cfr-9-9.102'", output)

    def test_a_cited_corpus_with_no_protocol_is_refused_not_swept_under_another(self):
        os.remove(os.path.join(self.tmp, protocol.per_corpus_filename("cfr-9-9.102")))
        code, output = self.run_cli("sweeps", self.a_map())
        self.assertEqual(code, 2, output)
        self.assertIn("cfr-9-9.102", output)


if __name__ == "__main__":
    unittest.main()
