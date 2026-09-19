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


if __name__ == "__main__":
    unittest.main()
