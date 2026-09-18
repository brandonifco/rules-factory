#!/usr/bin/env python3
"""An ellipsis skips whole paragraphs and never words inside one (0037, #282, #18).

`docs/corpus-map.md` said a quote carries no ellipsis. The section locator checker split a prose
`evidence` on ` ... ` and checked each fragment in order, so an entry could quote
*"A remote pilot ... must comply"* and pass with the condition between the halves removed. 0035
had already settled the same question for a table row the other way. Two documents contradicting
each other out loud is what #282 filed.

Neither end of that range was right, and the reason is in what the three committed ellipses turn
out to be doing: every one **joins two separately-cited paragraphs**, which is not a
correspondence failure — each fragment is verified, in order, inside a paragraph the citation
names. Only one of them drops words from inside a paragraph, and that one is the defect.

So the rule is the paragraph boundary, and what is watched here is both halves of it:

  * an ellipsis standing between two whole paragraphs is **accepted**, because the words it skips
    are named by the citation;
  * an ellipsis that resumes or opens inside a paragraph is **refused**, because the words it
    drops are named by nothing;
  * the quote's own two ends stay exempt — a span may be shortened at either end, which
    `corpus-map.md` always said;
  * the committed map still passes, with the one entry 0037 required re-quoted.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

_spec = importlib.util.spec_from_file_location(
    "check_locators_section",
    os.path.join(REPO, "examples", "faa-part-107", "check-locators-section.py"))
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

#: Two designated paragraphs, each of two sentences. The second sentence of (a) is the
#: qualification a dishonest quote would drop.
CORPUS = """<ROOT><DIV6 N="B" TYPE="SUBPART">
<DIV8 N="4.10" TYPE="SECTION"><HEAD>§ 4.10 Lighting.</HEAD>
<P>(a) The aircraft has lighting visible for three miles. The pilot may reduce its intensity but may not extinguish it.</P>
<P>(b) No person may operate at twilight without lighting visible for three miles.</P>
<P>(c) A third paragraph nobody quotes.</P>
</DIV8></DIV6></ROOT>"""

WHOLE_A = ("(a) The aircraft has lighting visible for three miles. The pilot may reduce its "
           "intensity but may not extinguish it.")
WHOLE_B = "(b) No person may operate at twilight without lighting visible for three miles."
FIRST_SENTENCE_OF_A = "(a) The aircraft has lighting visible for three miles."


class Fixture(unittest.TestCase):
    def setUp(self):
        directory = tempfile.mkdtemp(prefix="ellipsis-")
        self.addCleanup(shutil.rmtree, directory)
        self.path = os.path.join(directory, "corpus.xml")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(CORPUS)
        self.corpus, self.spans, _, _ = checker.corpus_index(self.path)

    def verdict(self, evidence, citation="§ 4.10(a), (b)"):
        entry = {"id": "probe", "locator": {"citation": citation}, "evidence": evidence}
        return checker.check(entry, self.corpus, self.spans, None, None)[:2]


class TestAnEllipsisMaySkipAWholeParagraph(Fixture):
    """The legitimate use, which a flat refusal would have broken.

    Mutation: refuse any ellipsis (what corpus-map.md literally said). This fails, and so do the
    two committed entries that use one.
    """

    def test_two_whole_paragraphs_joined_by_an_ellipsis_are_accepted(self):
        status, message = self.verdict(f"{WHOLE_A} ... {WHOLE_B}")
        self.assertEqual(status, "ok", message)

    def test_a_quote_may_still_be_short_at_its_own_two_ends(self):
        # First fragment starts mid-paragraph, last fragment ends mid-paragraph: both are the
        # quote's own ends, not an elision, and `corpus-map.md` has always allowed them.
        evidence = ("The pilot may reduce its intensity but may not extinguish it. "
                    "... (b) No person may operate at twilight without lighting")
        status, message = self.verdict(evidence)
        self.assertEqual(status, "ok", message)


class TestAnEllipsisMayNotDropWordsInsideAParagraph(Fixture):
    """The defect #282 filed, now refused.

    Mutation: drop either `at_paragraph_edge` guard in `check`. Each of these goes green while
    the quote still hides a qualifying clause, which is the whole complaint.
    """

    def test_a_quote_that_stops_mid_paragraph_before_an_ellipsis_is_refused(self):
        status, message = self.verdict(f"{FIRST_SENTENCE_OF_A} ... {WHOLE_B}")
        self.assertEqual(status, "bad", message)
        self.assertIn("opens inside a paragraph", message)

    def test_a_quote_that_resumes_mid_paragraph_after_an_ellipsis_is_refused(self):
        evidence = (f"{WHOLE_A} ... without lighting visible for three miles.")
        status, message = self.verdict(evidence, citation="§ 4.10")
        self.assertEqual(status, "bad", message)
        self.assertIn("resumes inside a paragraph", message)

    def test_the_refusal_says_what_the_rule_is(self):
        _, message = self.verdict(f"{FIRST_SENTENCE_OF_A} ... {WHOLE_B}")
        self.assertIn("skip whole paragraphs and never words within one", message)


class TestTheCommittedMapStillPasses(unittest.TestCase):
    """0037 required exactly one entry to be re-quoted, and this is that claim.

    Mutation: revert `flash-rate-sufficient`'s evidence to its elided form. This fails and names
    it, which is what makes the map's non-semantic exemption checkable rather than asserted.
    """

    def test_every_faa_part_107_entry_still_resolves(self):
        map_path = os.path.join(REPO, "examples", "faa-part-107", "corpus-map.json")
        xml_path = os.path.join(REPO, "examples", "faa-part-107", "part107.xml")
        if not os.path.exists(map_path):
            self.skipTest("faa-part-107 is not in this checkout")
        corpus, spans, _, _ = checker.corpus_index(xml_path)
        with open(map_path, encoding="utf-8") as handle:
            entries = json.load(handle)["entries"]
        bad = []
        for entry in entries:
            if entry.get("scope") != "in":
                continue
            status, message = checker.check(entry, corpus, spans, None, None)[:2]
            if status != "ok":
                bad.append(f"{entry['id']}: {message}")
        self.assertEqual(bad, [])

    def test_flash_rate_sufficient_now_quotes_its_paragraph_whole(self):
        map_path = os.path.join(REPO, "examples", "faa-part-107", "corpus-map.json")
        if not os.path.exists(map_path):
            self.skipTest("faa-part-107 is not in this checkout")
        with open(map_path, encoding="utf-8") as handle:
            entries = json.load(handle)["entries"]
        entry = [e for e in entries if e["id"] == "flash-rate-sufficient"][0]
        self.assertIn("may reduce the intensity of, but may not extinguish", entry["evidence"],
                      "the intensity-reduction clause is the one 0037 required back")


if __name__ == "__main__":
    unittest.main()
