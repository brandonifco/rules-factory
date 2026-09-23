#!/usr/bin/env python3
"""The inventory measures a walk, and a measurement that examined nothing is not a pass.

`extent` claims coverage; the inventory is what evidences it (#255). Three things are watched
here, because each of them is a way this tool could report coverage it did not measure:

  * the enumeration is of the corpus the manifest pins, and an extent it cannot read, an adapter
    nothing implements, or a corpus with no units is **refused** rather than reported as fully
    accounted for -- an inventory of zero units has zero unaccounted units;
  * a unit is reached by a **quote** found in its text, including a quote that runs from one unit
    into the next, and a run in which no entry's quote is found at all fails;
  * a recorded rejection is held to the units that exist: one naming a unit the extent does not
    contain accounts for nothing, and one naming a unit an entry quotes is a contradiction;
  * a version 2 rejection's unit identity includes its corpus `sourceId`; version 1 remains the
    original single-corpus representation and an empty file is still not evidence.

The six committed maps are then run through it, because a checker nobody has watched over real
corpora is one that has only ever seen its own fixtures.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import glob
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
    from mapper import cli, corpus, inventory, protocol
finally:
    sys.path.remove(TOOLS)

NOT_VERIFIED = 3

# A corpus of four blocks over two pages, marked the way Project Gutenberg marks one. Page 8
# exists so that an extent of page 9 has something outside it to exclude.
FIXTURE = """{8} A page before the extent, stating nothing this map claims.

{9} The first rule. A player who is on the bar must
enter before moving any other man.

A block of advice about how to play well, which states no rule at all.

The second rule, whose quotation runs on
into the block after it.

and finishes here, in a block of its own.

{10} A page after the extent.
"""


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue() + err.getvalue()


def maps():
    found = sorted(glob.glob(os.path.join(REPO, "examples", "*", "corpus-map*.json")))
    found += sorted(glob.glob(os.path.join(REPO, "examples", "*", "*", "corpus-map*.json")))
    return found


class Fixture:
    """A map, a manifest and a corpus in a directory of this test's own, removed after it."""

    def __init__(self, corpus_text=FIXTURE, extent=None, entries=None, adapter="plain-text"):
        self.directory = tempfile.mkdtemp(prefix="inventory-test-")
        self.corpus_path = os.path.join(self.directory, "corpus.txt")
        with open(self.corpus_path, "w", encoding="utf-8") as handle:
            handle.write(corpus_text)
        self.map_path = os.path.join(self.directory, "corpus-map.json")
        self.write("corpus-manifest.json", {
            "schemaVersion": 1,
            "corpora": [{"sourceId": "fixture", "adapter": adapter,
                         "committedPath": "corpus.txt", "verification": "committed-copy"}],
        })
        self.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": extent if extent is not None else {"unit": "page", "from": 9, "to": 9},
            "entries": entries if entries is not None else [
                {"id": "enter-from-the-bar", "evidence":
                    "A player who is on the bar must enter before moving any other man."},
            ],
        })

    def write(self, name, document):
        with open(os.path.join(self.directory, name), "w", encoding="utf-8") as handle:
            json.dump(document, handle)

    def remove(self):
        shutil.rmtree(self.directory)


class TestTheEnumerationIsOfThePinnedCorpus(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.remove)

    def test_a_quote_reaches_its_unit_and_the_rest_are_unaccounted(self):
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, NOT_VERIFIED, out)
        self.assertIn("enumerated:  4 unit(s)", out)
        self.assertIn("reached:     1", out)
        self.assertIn("unaccounted: 3", out)

    def test_a_quote_running_across_two_units_reaches_both(self):
        self.fixture.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": {"unit": "page", "from": 9, "to": 9},
            "entries": [{"id": "runs-on", "evidence": "The second rule, whose quotation runs on "
                                                      "into the block after it. and finishes "
                                                      "here, in a block of its own."}],
        })
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, NOT_VERIFIED, out)
        self.assertIn("reached:     2", out)

    def test_a_page_outside_the_extent_is_not_enumerated(self):
        units = corpus.PageMarkedText(self.fixture.corpus_path).units(
            {"unit": "page", "from": 9, "to": 9})
        self.assertEqual([unit.key for unit in units],
                         ["p. 9 block 1", "p. 9 block 2", "p. 9 block 3", "p. 9 block 4"])
        self.assertTrue(all("page before" not in unit.text and "page after" not in unit.text
                            for unit in units), [unit.text for unit in units])

    def test_an_extent_the_adapter_cannot_read_is_refused(self):
        self.fixture.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": {"unit": "section-designation", "sections": ["§ 107.25"]},
            "entries": [{"id": "one", "evidence": "The first rule."}],
        })
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 2, out)
        self.assertIn("section-designation", out)

    def test_an_extent_that_enumerates_nothing_fails(self):
        self.fixture.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": {"unit": "page", "from": 99, "to": 99},
            "entries": [{"id": "one", "evidence": "The first rule."}],
        })
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("enumerated no unit", out)

    def test_a_map_no_entry_of_which_is_located_fails(self):
        self.fixture.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": {"unit": "page", "from": 9, "to": 9},
            "entries": [{"id": "not-a-quote", "evidence": "A summary of the rule, in my words."}],
        })
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("silent zero", out)

    def test_an_adapter_nothing_implements_is_refused(self):
        self.fixture.write("corpus-manifest.json", {
            "schemaVersion": 1,
            "corpora": [{"sourceId": "fixture", "adapter": "docx-styles",
                         "committedPath": "corpus.txt"}],
        })
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 2, out)
        self.assertIn("docx-styles", out)


class TestARejectionIsHeldToTheUnitsThatExist(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture(entries=[
            {"id": "enter-from-the-bar", "evidence":
                "A player who is on the bar must enter before moving any other man."},
            {"id": "second", "evidence": "The second rule, whose quotation runs on"},
            {"id": "third", "evidence": "and finishes here, in a block of its own."},
        ])
        self.addCleanup(self.fixture.remove)

    def reject(self, *items):
        self.fixture.write("mapping-inventory.json",
                           {"inventoryVersion": 1, "corpus": "fixture", "rejected": list(items)})

    def reject_v2(self, *items):
        self.fixture.write("mapping-inventory.json", {
            "inventoryVersion": 2,
            "rejected": [dict(item, sourceId="fixture") for item in items],
        })

    def test_a_rejected_unit_accounts_for_itself(self):
        self.reject({"unit": "p. 9 block 2", "ground": "advice",
                     "note": "guidance on how to play well; it obliges nothing"})
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 0, out)
        self.assertIn("rejected:    1", out)
        self.assertIn("unaccounted: 0", out)

    def test_version_two_is_valid_for_one_corpus_too(self):
        self.reject_v2({"unit": "p. 9 block 2", "ground": "advice",
                        "note": "guidance on how to play well; it obliges nothing"})
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 0, out)
        self.assertIn("rejected:    1", out)
        self.assertIn("unaccounted: 0", out)

    def test_a_version_two_file_with_zero_rejections_is_refused(self):
        self.reject_v2()
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 2, out)
        self.assertIn("records no rejection", out)

    def test_the_same_unit_key_in_two_corpora_is_two_rejections(self):
        self.fixture.write("mapping-inventory.json", {
            "inventoryVersion": 2,
            "rejected": [
                {"sourceId": source, "unit": "p. 9 block 2", "ground": "advice",
                 "note": "the same local key can identify a unit in each separate corpus"}
                for source in ("first", "second")
            ],
        })
        loaded = inventory.load_rejections(
            os.path.join(self.fixture.directory, "mapping-inventory.json"), ("first", "second"))
        self.assertEqual(set(loaded), {"first", "second"})
        self.assertEqual(set(loaded["first"]), {"p. 9 block 2"})
        self.assertEqual(set(loaded["second"]), {"p. 9 block 2"})

    def test_a_rejection_of_a_unit_the_extent_does_not_contain_fails(self):
        self.reject({"unit": "p. 9 block 44", "ground": "advice", "note": "no such block"})
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("rejection of nothing", out)

    def test_a_rejection_of_a_unit_an_entry_quotes_fails(self):
        self.reject({"unit": "p. 9 block 1", "ground": "advice",
                     "note": "claimed as advice, and quoted as a rule"})
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("cannot have produced no entry", out)

    def test_a_ground_outside_the_closed_set_is_refused(self):
        self.reject({"unit": "p. 9 block 2", "ground": "not-a-rule", "note": "why"})
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 2, out)
        self.assertIn("outside the closed set", out)

    def test_a_rejection_with_no_note_is_refused(self):
        self.reject({"unit": "p. 9 block 2", "ground": "advice"})
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 2, out)
        self.assertIn("`note`", out)

    def test_a_rejection_file_for_another_corpus_is_refused(self):
        self.fixture.write("mapping-inventory.json", {
            "inventoryVersion": 1, "corpus": "another-corpus",
            "rejected": [{"unit": "p. 9 block 2", "ground": "advice", "note": "why"}]})
        code, out = run(["inventory", self.fixture.map_path])
        self.assertEqual(code, 2, out)
        self.assertIn("another-corpus", out)


class TestThePageExtentEndsWhereItSaysItDoes(unittest.TestCase):
    """0024: a page extent may end before a heading on its last page, and the enumeration must
    stop there. Enumerating past it would call the rest of the page unaccounted -- reporting as
    unevidenced a part of the corpus the map never claimed."""

    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.remove)

    def test_the_units_stop_at_the_heading(self):
        adapter = corpus.PageMarkedText(self.fixture.corpus_path)
        whole = adapter.units({"unit": "page", "from": 9, "to": 9})
        cut = adapter.units({"unit": "page", "from": 9, "to": 9,
                             "endsBefore": "The second rule, whose quotation runs on into the "
                                           "block after it."})
        self.assertEqual(len(whole), 4)
        self.assertEqual([unit.key for unit in cut], ["p. 9 block 1", "p. 9 block 2"])

    def test_a_heading_that_is_not_a_block_of_its_own_is_refused(self):
        adapter = corpus.PageMarkedText(self.fixture.corpus_path)
        with self.assertRaises(protocol.Refused):
            adapter.units({"unit": "page", "from": 9, "to": 9, "endsBefore": "Nowhere On The Page"})


class TestThePageExtentStartsWhereItSaysItDoes(unittest.TestCase):
    """0064: the mirror. A page extent may start after a heading on its first page, and the
    enumeration must begin there -- enumerating from the top of the page would call the half
    another map read unaccounted, which is the overclaim #434 refused to write."""

    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.remove)

    def test_the_units_start_after_the_heading(self):
        adapter = corpus.PageMarkedText(self.fixture.corpus_path)
        whole = adapter.units({"unit": "page", "from": 9, "to": 9})
        cut = adapter.units({"unit": "page", "from": 9, "to": 9,
                             "startsAfter": "A block of advice about how to play well, which "
                                            "states no rule at all."})
        self.assertEqual(len(whole), 4)
        self.assertEqual([unit.key for unit in cut], ["p. 9 block 3", "p. 9 block 4"])

    def test_a_unit_keeps_its_place_on_its_own_page(self):
        """The key is the block's position on the page, not its position in what was selected.

        Two maps of one page have to be able to record rejections that mean the same thing, and a
        key that counted from the cut would give the same block two names.
        """
        adapter = corpus.PageMarkedText(self.fixture.corpus_path)
        whole = {unit.key: unit.text for unit in adapter.units({"unit": "page", "from": 9, "to": 9})}
        cut = adapter.units({"unit": "page", "from": 9, "to": 9,
                             "startsAfter": "A block of advice about how to play well, which "
                                            "states no rule at all."})
        for unit in cut:
            self.assertEqual(whole[unit.key], unit.text)

    def test_both_cuts_apply_together(self):
        adapter = corpus.PageMarkedText(self.fixture.corpus_path)
        cut = adapter.units({"unit": "page", "from": 9, "to": 9,
                             "startsAfter": "A block of advice about how to play well, which "
                                            "states no rule at all.",
                             "endsBefore": "and finishes here, in a block of its own."})
        self.assertEqual([unit.key for unit in cut], ["p. 9 block 3"])

    def test_a_heading_that_is_not_a_block_of_its_own_is_refused(self):
        adapter = corpus.PageMarkedText(self.fixture.corpus_path)
        with self.assertRaises(protocol.Refused):
            adapter.units({"unit": "page", "from": 9, "to": 9, "startsAfter": "Nowhere On The Page"})

    def test_an_extent_that_ends_where_it_has_not_begun_is_refused(self):
        adapter = corpus.PageMarkedText(self.fixture.corpus_path)
        with self.assertRaises(protocol.Refused) as caught:
            adapter.units({"unit": "page", "from": 9, "to": 9,
                           "startsAfter": "and finishes here, in a block of its own.",
                           "endsBefore": "A block of advice about how to play well, which states "
                                         "no rule at all."})
        self.assertIn("ends where it has not begun", str(caught.exception))


class TestUnitKeysIdentifyOneUnit(unittest.TestCase):
    def test_no_two_units_of_a_committed_map_share_a_key(self):
        """A rejection names a unit by its key, so a key naming two units would reject both."""
        examined = 0
        for path in maps():
            with self.subTest(map=os.path.relpath(path, REPO)):
                keys = [unit.key for unit in units_of(path)]
                self.assertEqual(len(keys), len(set(keys)))
                examined += len(keys)
        self.assertTrue(examined, "no units enumerated -- this test proved nothing")


def units_of(map_path):
    """Every unit of every corpus the map cites, the way `mapper inventory` enumerates them.

    A map may cite several corpora and declares one extent across them all (0039, 0042), so each
    corpus gets its own adapter and its own share of that extent. Opening only
    `document["corpus"]` and handing it the whole extent refused trial 10's map outright -- the
    principal corpus does not contain § 172.102 -- and would have measured 15% of a two-corpus
    map's units had it not.
    """
    document = json.load(open(map_path, encoding="utf-8"))
    manifest_path = cli._find_manifest(map_path)
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    here = os.path.dirname(os.path.abspath(manifest_path))
    units = []
    for source in sorted(protocol.cited_corpora(document)):
        adapter = corpus.open_corpus(manifest, source, here)
        portion, _ = adapter.portion_of(document.get("extent"))
        units.extend(adapter.units(portion))
    return units


class TestEveryCommittedMapIsInventoried(unittest.TestCase):
    """The six maps, over three corpus grammars. A map that cannot be inventoried at all is a
    corpus this interface does not reach, which is the thing the interface exists to make
    visible."""

    def test_every_map_enumerates_units_and_locates_quotes(self):
        paths = maps()
        self.assertTrue(paths, "no example maps -- this test proved nothing")
        for path in paths:
            with self.subTest(map=os.path.relpath(path, REPO)):
                code, out = run(["inventory", path])
                self.assertIn(code, (0, NOT_VERIFIED), out)
                self.assertNotIn("enumerated:  0 unit(s)", out)
                self.assertNotIn("of 0 entries", out)

    def test_all_three_grammars_are_exercised(self):
        """Three adapters, and each one is reached by some committed map: an adapter no map
        exercises has only ever been run on this file's own fixture."""
        used = set()
        for path in maps():
            document = json.load(open(path, encoding="utf-8"))
            manifest = json.load(open(cli._find_manifest(path), encoding="utf-8"))
            for declared in manifest.get("corpora") or []:
                if declared.get("sourceId") == document.get("corpus"):
                    used.add(declared.get("adapter"))
        self.assertEqual(used, set(corpus.ADAPTERS))


# A corpus whose page turn falls mid-sentence, the way Project Gutenberg's does. The quote of
# that sentence carries the marker, because `check-locators.py` searches a corpus with its markers
# in place and `pages_spanned` exists for exactly this case; the adapter takes markers out of a
# unit's text, so the search of the units has to take them out of the quote too (#392).
MARKED_MID_SENTENCE = """{8} A page before the extent, stating nothing this map claims.

{9} The first rule. A player who is on the bar must enter before moving any other man.

The men are arranged at starting as shown in {10} Fig. 1, with two men on the ace point.

A block that begins on the page after the turn.

{11} A page after the extent.
"""


class TestAQuoteKeepsThePageMarkerTheCorpusPrints(unittest.TestCase):
    """The marker is not a word of the quote, and it is not a reason to report the map unevidenced.

    `check-locators.py` holds every quote to the pinned bytes *including* the `{N}` markers, so a
    quote that crosses a page turn has to carry one. `PageMarkedText._blocks` removes them from
    each unit's text. Before #392 that made a marked quote the one string that could not be found
    in the units it came from, and six of the backgammon map's entries -- the starting
    arrangement, the pip move, both stake rules and the enumeration of throws that is the only
    authority in that corpus for a six-faced die -- were reported as quoting nothing.
    """

    def setUp(self):
        self.fixture = Fixture(corpus_text=MARKED_MID_SENTENCE,
                               extent={"unit": "page", "from": 9, "to": 10},
                               entries=[{"id": "starting-arrangement", "evidence":
                                         "The men are arranged at starting as shown in {10} "
                                         "Fig. 1, with two men on the ace point."}])
        self.addCleanup(self.fixture.remove)

    def test_a_quote_carrying_a_marker_reaches_the_unit_it_came_from(self):
        code, out = run(["inventory", self.fixture.map_path, "--list"])
        self.assertEqual(code, NOT_VERIFIED, out)
        self.assertIn("reached:     1 by the quoted evidence of 1 entry", out)
        self.assertNotIn("not located inside the extent", out)
        self.assertNotIn("?  p. 9 block 2", out)

    def test_an_ecfr_quote_is_searched_exactly_as_written(self):
        """The eCFR adapter prints no markers, so nothing is taken out of its quotes: a map that
        wrote `{10}` into an eCFR quote quoted something the corpus does not say."""
        units = [corpus.Unit("\u00a7 1.1 \u00b61", "paragraph",
                             "The rule as the corpus states it, with no marker in it.")]
        measured = inventory.take(units, {"entries": [{
            "id": "invented-marker",
            "evidence": "The rule as {10} the corpus states it, with no marker in it.",
        }]}, {})
        self.assertEqual(measured.reached, {})
        self.assertEqual(measured.unlocated, ["invented-marker"])


class TestTheCommittedBackgammonMapQuotesItsCorpus(unittest.TestCase):
    def test_every_entry_of_the_backgammon_map_is_located(self):
        """Measured: six entries were reported unlocated, every one of them for its marker.

        The nine units those quotes did not reach are now recorded as examined and rejected in
        that map's `mapping-inventory.json` (#267), so the run is VERIFIED; what this test
        watches is the reach, which is what #392 changed.
        """
        path = os.path.join(REPO, "examples", "hoyle-backgammon", "corpus-map.json")
        code, output = run(["inventory", path, "--list"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("not located inside the extent", output)
        self.assertIn("reached:     37 by the quoted evidence of 32 entries", output)
        self.assertIn("unaccounted: 0", output)


# The same page turn as `MARKED_MID_SENTENCE`, marked the way `extract.py` marks one: `{N}` on a
# line of its own, before the page it opens. Two blocks straddle the turn, so a quote of both
# carries the marker printed between them.
MARKED_ON_ITS_OWN_LINE = """{9}

The first rule, whose quotation runs on

{10}

into the block after the page turn.

A block on the page after, printing a {6} that is the corpus's own text and not a page turn.
"""


class TestAQuoteStraddlingATurnReachesBothSidesOfIt(unittest.TestCase):
    """#437: `unmarked()` reads a **quote**, whose whitespace is already collapsed.

    `PageMarkedPdfText` marks a page turn with `{N}` on a line of its own and anchors `MARKER` to
    that line, which is right for the corpus and cannot hold against a map's `evidence`: there
    the marker sits between two spaces, at no line boundary, so the substitution never fired and
    every quote carrying one was reported as quoting nothing. Trial 12's map has three, and the
    28 units they reach -- the whole twelve-row Actions table among them -- were reported
    unaccounted, which is the inventory's word for *nobody looked*, while
    `check-locators-pdf-text.py` located all three without complaint.
    """

    def setUp(self):
        self.fixture = Fixture(corpus_text=MARKED_ON_ITS_OWN_LINE,
                               adapter="pdftotext-page-marked",
                               extent={"unit": "page", "from": 9, "to": 10},
                               entries=[{"id": "runs-across-the-turn", "evidence":
                                         "The first rule, whose quotation runs on {10} into the "
                                         "block after the page turn."}])
        self.addCleanup(self.fixture.remove)

    def test_the_quote_reaches_the_units_on_both_sides_of_the_turn(self):
        code, out = run(["inventory", self.fixture.map_path, "--list"])
        self.assertEqual(code, NOT_VERIFIED, out)
        self.assertIn("reached:     2 by the quoted evidence of 1 entry", out)
        self.assertNotIn("not located inside the extent", out)

    def test_the_marker_is_taken_out_of_a_flattened_quote(self):
        adapter = corpus.PageMarkedPdfText(self.fixture.corpus_path)
        self.assertEqual(adapter.unmarked("runs on {10} into the block"),
                         "runs on into the block")

    def test_the_corpus_marker_is_still_read_line_anchored(self):
        """The two patterns are separate, and only the quote-side one lost its anchors.

        Unanchoring `MARKER` as well would have been the shorter fix and is a different claim
        about the corpus: a `{6}` the corpus prints inside a line is its own text, the units keep
        it, and the anchors are what say so.
        """
        adapter = corpus.PageMarkedPdfText(self.fixture.corpus_path)
        units = adapter.units({"unit": "page", "from": 10, "to": 10})
        self.assertEqual([unit.key for unit in units], ["p. 10 block 1", "p. 10 block 2"])
        self.assertIn("{6}", units[1].text)


class TestTheCommittedPlayingTheGameMapAccountsForItsExtent(unittest.TestCase):
    def test_every_unit_of_trial_12s_extent_is_reached_or_rejected(self):
        """Measured: three entries were reported unlocated and 28 units unaccounted (#437).

        Four of that map's recorded rejections named units `actions-table` quotes -- the Actions
        table's column headers on both sides of the turn -- which a reader who could not see the
        quote had no way to tell. They are gone from `mapping-inventory.json`: a passage cannot
        have produced no entry and be the evidence for one.

        A fifth left later and the other way about: the Round Down sidebar was rejected because no
        citation could name the earlier of two identical printings, and 0066 made one, so the
        passage is an entry (#436).
        """
        path = os.path.join(REPO, "examples", "srd-52-playing-the-game", "corpus-map.json")
        code, output = run(["inventory", path, "--list"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("not located inside the extent", output)
        self.assertIn("reached:     301 by the quoted evidence of 92 entries", output)
        self.assertIn("unaccounted: 0", output)


class TestABoundIsAQuoteOfTheUnitItNames(unittest.TestCase):
    """0031 gives a worked example three fates, and a bound is the one the inventory could not see.

    An entry, a bound on an entry's ambiguity, or declined with the reading in a note: the first
    is `evidence`, the third is `mapping-inventory.json`, and the second is `ambiguity.bounds`,
    which `check-locators.py` already holds to the corpus the way it holds `evidence`. Before
    #393 the passage a map quoted for the strongest reason it has -- the corpus's only authority
    on an open term -- was counted as read by nobody.
    """

    def entry(self, evidence, bound_text):
        return {
            "id": "open-term",
            "locator": {"sourceId": "fixture", "citation": "p. 9"},
            "evidence": evidence,
            "ambiguity": {"question": "How short is short?", "fate": "unresolved",
                          "bounds": {"term": "short temporary absences", "dimension": "duration",
                                     "examples": [{"locator": {"sourceId": "fixture",
                                                               "citation": "p. 9 block 3"},
                                                   "text": bound_text, "verdict": "outside",
                                                   "value": "1 year"}]}},
        }

    def test_a_unit_quoted_only_by_a_bound_is_reached(self):
        units = [
            corpus.Unit("p. 9 block 1", "paragraph",
                        "Short temporary absences are counted as periods of use."),
            corpus.Unit("p. 9 block 3", "paragraph",
                        "Example 4. He goes abroad for a 1-year sabbatical leave, which is not "
                        "a short temporary absence."),
        ]
        measured = inventory.take(units, {"entries": [self.entry(
            "Short temporary absences are counted as periods of use.",
            "He goes abroad for a 1-year sabbatical leave, which is not a short temporary "
            "absence.")]}, {})
        self.assertEqual(sorted(measured.reached), ["p. 9 block 1", "p. 9 block 3"])
        self.assertEqual(measured.unaccounted, [])

    def test_a_bound_does_not_rescue_an_entry_whose_own_quote_is_missing(self):
        """`evidence` is what an entry claims to quote. A bound that locates while the entry's
        own quote does not would hide exactly the defect this line reports."""
        units = [corpus.Unit("p. 9 block 3", "paragraph",
                             "Example 4. He goes abroad for a 1-year sabbatical leave.")]
        measured = inventory.take(units, {"entries": [self.entry(
            "A sentence this corpus does not contain anywhere at all.",
            "He goes abroad for a 1-year sabbatical leave.")]}, {})
        self.assertEqual(sorted(measured.reached), ["p. 9 block 3"])
        self.assertEqual(measured.unlocated, ["open-term"])

    def test_a_rejection_of_a_unit_only_a_bound_quotes_is_a_contradiction(self):
        """The map cannot say both that it read this passage and produced nothing, and that the
        passage is what bounds an open term."""
        units = [
            corpus.Unit("p. 9 block 1", "paragraph",
                        "Short temporary absences are counted as periods of use."),
            corpus.Unit("p. 9 block 3", "paragraph",
                        "Example 4. He goes abroad for a 1-year sabbatical leave."),
        ]
        measured = inventory.take(units, {"entries": [self.entry(
            "Short temporary absences are counted as periods of use.",
            "He goes abroad for a 1-year sabbatical leave.")]},
            {"p. 9 block 3": {"ground": "restatement", "note": "an illustration"}})
        self.assertTrue(any("cannot have produced no entry and be the evidence for one"
                            in problem for problem in measured.problems), measured.problems)


class TestTheCommittedTaxMapAccountsForItsBoundedExamples(unittest.TestCase):
    def test_the_two_bounded_examples_are_no_longer_unaccounted(self):
        """Measured: (c)(4) Examples 4 and 5 are the corpus's only authority on `short temporary
        absences`, and the map quotes both in `bounds`."""
        path = os.path.join(REPO, "examples", "tax-121-principal-residence", "corpus-map.json")
        code, output = run(["inventory", path, "--list"])
        self.assertEqual(code, 0, output)
        self.assertIn("reached:     34", output)
        self.assertIn("rejected:    14", output)
        self.assertNotIn("?  \u00a7 1.121-1 \u00b632 example", output)
        self.assertNotIn("?  \u00a7 1.121-1 \u00b633 example", output)


class TestShortEvidenceKeepsItsSafetyBoundary(unittest.TestCase):
    def test_a_short_prose_fragment_is_not_enough_to_reach_a_unit(self):
        units = [
            corpus.Unit("p. 1 block 1", "paragraph", "A common short phrase appears here."),
            corpus.Unit("p. 1 block 2", "paragraph", "Later the common short phrase appears again."),
        ]
        measured = inventory.take(units, {"entries": [{
            "id": "ambiguous-prose",
            "locator": {"sourceId": "fixture", "citation": "p. 1"},
            "evidence": "common short phrase",
        }]}, {})
        self.assertEqual(measured.reached, {})
        self.assertEqual(measured.unlocated, ["ambiguous-prose"])

    def test_trial_10_duplicate_ib1_row_remains_unaccounted(self):
        path = os.path.join(REPO, "examples", "hazmat-172-table", "corpus-map.json")
        code, output = run(["inventory", path, "--list"])
        self.assertEqual(code, NOT_VERIFIED, output)
        self.assertIn(
            "total across 2 corpora: 747 unit(s), 615 unaccounted, 14 unaddressable, "
            "135 entr(ies) located",
            output,
        )
        self.assertIn(
            '§ 172.102 table 2, row blank in column 1 below row [column 1 = "IB1"]',
            output,
        )
        self.assertNotIn(
            '?  § 172.102 table 2, row blank in column 1 below row [column 1 = "IB2"]',
            output,
        )

    def test_trial_10_short_table_quotes_are_not_reported_unlocated(self):
        path = os.path.join(REPO, "examples", "hazmat-172-table", "corpus-map.json")
        _, output = run(["inventory", path])
        short_entries = (
            "label-code-8-corrosive",
            "acetal-proper-shipping-name",
            "acetaldehyde-proper-shipping-name",
            "acetyl-acetone-peroxide-forbidden",
            "acetal-label-codes",
            "acetaldehyde-label-codes",
            "acetic-acid-glacial-label-codes",
            "acetic-acid-50-to-80-label-codes",
            "acetic-acid-10-to-50-label-codes",
            "alkali-metal-amalgam-label-codes",
            "acetal-special-provisions",
            "alkali-metal-amalgam-vessel-stowage-codes",
        )
        for entry in short_entries:
            with self.subTest(entry=entry):
                self.assertNotIn(entry, output, output)


if __name__ == "__main__":
    unittest.main()
