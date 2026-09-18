#!/usr/bin/env python3
"""A protocol is about one corpus, and a map citing several has one per corpus (0040).

[#304](https://github.com/brandonifco/rules-factory/issues/304), recorded in advance as point 3
of [#284](https://github.com/brandonifco/rules-factory/issues/284). A map may cite several
corpora ([0039](../../../docs/decisions/0039-the-manifest-pins-every-corpus-a-map-cites.md)) and
had exactly one `mapping-protocol.json`, about one of them. Trial 10's two corpora communicate
rules in materially different ways — § 172.101 states a rule in a table row and points with bare
codes, § 172.102 states prose inside `EXTRACT` wrappers and points with section designations — so
one protocol over both would be a true account of one and a false one of the other.

That is worse than a gap. `protocol.py`'s own opening says why: *a declared interrogation nobody
performs is worse than none — it reads as coverage.*

Watched here:

  * a map citing two corpora resolves **two** protocols, one per corpus, by filename;
  * a cited corpus with **no** protocol is refused, naming which;
  * a `mapping-protocol-<sourceId>.json` for a corpus the map does **not** cite is refused, so a
    leftover cannot sit beside a map claiming to govern it;
  * a protocol whose `corpus` the map does not cite is a problem, even when the manifest declares
    it — declared is not read;
  * `--protocol`, which names one file, is refused for a map citing several rather than letting
    one protocol stand for all of them;
  * and the plain `mapping-protocol.json` still serves a map citing one corpus, which is every
    map committed before trial 10.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

sys.path.insert(0, TOOLS)
try:
    from mapper import protocol
finally:
    sys.path.remove(TOOLS)

FIRST, SECOND = "cfr-9-9.101", "cfr-9-9.102"


def a_map(*cited):
    principal = cited[0]
    return {"schemaVersion": 1, "corpus": principal,
            "entries": [{"id": f"entry-{i}", "locator": {"sourceId": source, "citation": "§ 9.1"}}
                        for i, source in enumerate(cited)]}


def a_protocol(source_id):
    return {"protocolVersion": 1, "corpus": source_id, "units": ["paragraph"],
            "pointerMechanisms": [{"mechanism": "section-designation"}],
            "requiredSweeps": ["definitions"], "adapterReach": {"text": "readable"}}


class OneProtocolPerCitedCorpus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="protocol-per-corpus-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, document):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        return path

    def map_at(self, *cited):
        return self.write("corpus-map.json", a_map(*cited))

    # --- resolving -------------------------------------------------------------------------

    def test_two_corpora_resolve_two_protocols(self):
        map_path = self.map_at(FIRST, SECOND)
        self.write(protocol.per_corpus_filename(FIRST), a_protocol(FIRST))
        self.write(protocol.per_corpus_filename(SECOND), a_protocol(SECOND))
        found = protocol.paths_beside(map_path, a_map(FIRST, SECOND))
        self.assertEqual(sorted(found), [FIRST, SECOND])
        self.assertTrue(found[SECOND].endswith(f"mapping-protocol-{SECOND}.json"), found[SECOND])

    def test_one_corpus_still_reads_the_plain_file(self):
        map_path = self.map_at(FIRST)
        self.write(protocol.PROTOCOL_FILENAME, a_protocol(FIRST))
        found = protocol.paths_beside(map_path, a_map(FIRST))
        self.assertEqual(list(found), [FIRST])
        self.assertTrue(found[FIRST].endswith(protocol.PROTOCOL_FILENAME), found[FIRST])

    def test_one_corpus_may_also_use_the_per_corpus_name(self):
        map_path = self.map_at(FIRST)
        self.write(protocol.per_corpus_filename(FIRST), a_protocol(FIRST))
        found = protocol.paths_beside(map_path, a_map(FIRST))
        self.assertTrue(found[FIRST].endswith(f"mapping-protocol-{FIRST}.json"), found[FIRST])

    # --- refusing --------------------------------------------------------------------------

    def test_a_cited_corpus_with_no_protocol_is_refused_by_name(self):
        map_path = self.map_at(FIRST, SECOND)
        self.write(protocol.per_corpus_filename(FIRST), a_protocol(FIRST))
        with self.assertRaises(protocol.Refused) as caught:
            protocol.paths_beside(map_path, a_map(FIRST, SECOND))
        self.assertIn(SECOND, str(caught.exception))
        self.assertIn("nothing says how it was read", str(caught.exception))

    def test_the_plain_file_does_not_stand_for_two_corpora(self):
        """The whole defect: one protocol silently covering a corpus it is not about."""
        map_path = self.map_at(FIRST, SECOND)
        self.write(protocol.PROTOCOL_FILENAME, a_protocol(FIRST))
        with self.assertRaises(protocol.Refused) as caught:
            protocol.paths_beside(map_path, a_map(FIRST, SECOND))
        self.assertIn(FIRST, str(caught.exception))
        self.assertIn(SECOND, str(caught.exception))

    def test_a_protocol_for_an_uncited_corpus_is_refused(self):
        map_path = self.map_at(FIRST)
        self.write(protocol.per_corpus_filename(FIRST), a_protocol(FIRST))
        self.write(protocol.per_corpus_filename("cfr-9-9.404"), a_protocol("cfr-9-9.404"))
        with self.assertRaises(protocol.Refused) as caught:
            protocol.paths_beside(map_path, a_map(FIRST))
        self.assertIn("cfr-9-9.404", str(caught.exception))
        self.assertIn("does not cite", str(caught.exception))

    # --- checking --------------------------------------------------------------------------

    def test_a_protocol_about_a_declared_but_uncited_corpus_is_a_problem(self):
        """Declared in the manifest is not the same as read by the map."""
        manifest = {"corpora": [{"sourceId": FIRST}, {"sourceId": SECOND}]}
        problems = protocol.check(a_protocol(SECOND), a_map(FIRST), manifest)
        self.assertTrue(any("is not cited by this map" in line for line in problems), problems)

    def test_a_protocol_about_a_cited_corpus_is_not(self):
        manifest = {"corpora": [{"sourceId": FIRST}, {"sourceId": SECOND}]}
        problems = protocol.check(a_protocol(SECOND), a_map(FIRST, SECOND), manifest)
        self.assertEqual([line for line in problems if "cited" in line], [], problems)


class TheCommittedMapsDoNotMove(unittest.TestCase):
    """Every map committed before trial 10 cites one corpus and keeps mapping-protocol.json."""

    def test_each_resolves_its_own_plain_protocol(self):
        for name in ("faa-part-107", "tax-121-principal-residence", "srd-52-combat",
                     "hoyle-backgammon", "srd-52-conditions", "faa-part-107-temporal"):
            directory = os.path.join(REPO, "examples", name)
            maps = [f for f in os.listdir(directory) if f.startswith("corpus-map")]
            if not maps:
                continue
            with self.subTest(map=name):
                map_path = os.path.join(directory, maps[0])
                with open(map_path, encoding="utf-8") as handle:
                    document = json.load(handle)
                found = protocol.paths_beside(map_path, document)
                self.assertEqual(len(found), 1, found)
                self.assertTrue(next(iter(found.values())).endswith(protocol.PROTOCOL_FILENAME))


if __name__ == "__main__":
    unittest.main()
