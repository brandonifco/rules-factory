#!/usr/bin/env python3
"""A map may cite several corpora, and every one of them is pinned, carried and recorded (0039).

[#300](https://github.com/brandonifco/rules-factory/issues/300). The map contract has always
permitted a map whose entries cite a corpus the envelope does not name — `locator.sourceId` need
only resolve in the manifest — and since
[#301](https://github.com/brandonifco/rules-factory/pull/301) the `section-designation` locator
run reads such a map. The factory refused it, in `pack-map.py` and again in `intake.py`, so a map
of a corpus the eCFR serves as two documents could pass `validate.sh` and never become an engine.

The manifest is the authority for the corpus set: it already declares `sourceId`, `contentHash`,
`hashDerivation`, `asOf` and the posture of every corpus, and it travels inside the package. No
per-corpus baseline is added to the map schema. The envelope's `corpus`/`baseline` stays the
map's **principal** stamp, pinning that corpus and claiming nothing about the others.

Watched here, end to end over a synthetic two-section corpus pair:

  * a valid two-corpus map **packages**, and the packaged manifest carries exactly the cited
    corpora and no other manifest entry;
  * that package **reaches intake**, and each cited corpus is hashed from the bytes in hand
    rather than trusted from the manifest;
  * a **wrong** second-corpus hash is refused, naming that corpus;
  * a **missing** second corpus is refused, naming what was not supplied;
  * an **undeclared** `sourceId` is refused;
  * the engine **carries both** corpora, and provenance names both, sorted by `sourceId`, the
    principal one flagged;
  * recomputation detects modification of **either** corpus, naming which.

One-corpus maps are unchanged, which `test_factory_intake.py`, `test_factory_provenance.py` and
`test_factory_produce.py` hold; the only intentional migration is `provenanceFormat` 4 → 5, where
`corpus` became `corpora`.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
PACK = os.path.join(REPO, "tools", "pack-map.py")

sys.path.insert(0, TOOLS)
try:
    from factory import __main__ as factory
    from factory import intake as intake_step
finally:
    sys.path.remove(TOOLS)

NOT_VERIFIED = 3

FIRST = """<ROOT><DIV8 N="9.101" TYPE="SECTION"><HEAD>&#167; 9.101 The table.</HEAD>
<P>(a) Each material is listed in the table with the provisions that apply to it.</P>
<P>(b) A code in column 7 is a special provision stated in &#167; 9.102 of this subchapter.</P>
</DIV8></ROOT>
"""

SECOND = """<ROOT><DIV8 N="9.102" TYPE="SECTION"><HEAD>&#167; 9.102 Special provisions.</HEAD>
<P>(a) A special provision is in addition to the requirements of the table.</P>
<P>(b) A code containing the letter W applies only to transportation by water.</P>
</DIV8></ROOT>
"""

LICENCE = """Corpus: cfr-9-9.101 and cfr-9-9.102, a synthetic two-section fixture in the shape the
eCFR versioner serves a section in. Not a real regulation.

Terms: public-domain-us-government. Both corpora declare `licence: public-domain-us-government`
in corpus-manifest.json, which is the source of truth for a corpus's terms (decision 0023).
"""

SECTIONS = (("cfr-9-9.101", "section-9.101.xml", FIRST), ("cfr-9-9.102", "section-9.102.xml", SECOND))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def corpus_entry(source_id, path, digest):
    return {
        "sourceId": source_id, "title": f"9 CFR {source_id}", "adapter": "ecfr-xml",
        "locatorGrammar": "section-designation", "contentHash": digest,
        "hashDerivation": "ecfr-versioner-xml", "asOf": "2026-01-01",
        "boundaryPolicy": "pin-in-repo", "licence": "public-domain-us-government",
        "verification": "committed-copy", "committedPath": path, "quotation": "verbatim",
        "randomness": "none", "retrievedFrom": "https://example.invalid/fixture",
        "pointerPhrases": [{"regex": r"§+\s?\d+\.\d+(?:\([A-Za-z0-9]+\))*"}, "of this subchapter"],
        "references": [],
    }


ENTRIES = [
    {"id": "listed-in-the-table", "name": "Each material is listed in the table",
     "locator": {"sourceId": "cfr-9-9.101", "citation": "§ 9.101(a)"},
     "kind": "value", "scope": "in", "clarity": "clear", "status": "mapped",
     "evidence": "Each material is listed in the table with the provisions that apply to it."},
    {"id": "w-is-water-only", "name": "A W code binds water transport only",
     "locator": {"sourceId": "cfr-9-9.102", "citation": "§ 9.102(b)"},
     "kind": "value", "scope": "in", "clarity": "clear", "status": "mapped",
     "evidence": "A code containing the letter W applies only to transportation by water."},
]


class TwoCorpusMap(unittest.TestCase):
    """One packed fixture, reused: packing runs the whole publish gate and is not cheap."""

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp(prefix="two-corpus-")
        cls.map_dir = cls.write_map(os.path.join(cls.shared, "two-section-fixture"))
        cls.nupkg = cls.pack(cls.map_dir, os.path.join(cls.shared, "feed"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    @staticmethod
    def write_map(directory, entries=None, corpora=None):
        os.makedirs(directory, exist_ok=True)
        digests = {}
        for source_id, name, text in SECTIONS:
            path = os.path.join(directory, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            digests[source_id] = sha256(text.encode("utf-8"))
        with open(os.path.join(directory, "CORPUS-LICENCE.txt"), "w", encoding="utf-8") as handle:
            handle.write(LICENCE)
        with open(os.path.join(directory, "map-package.json"), "w", encoding="utf-8") as handle:
            json.dump({"version": "1.0.0", "licence": {"corpusTerms": "CORPUS-LICENCE.txt"}}, handle)
        declared = corpora if corpora is not None else [
            corpus_entry(source_id, name, digests[source_id]) for source_id, name, _ in SECTIONS]
        with open(os.path.join(directory, "corpus-manifest.json"), "w", encoding="utf-8") as handle:
            json.dump({"schemaVersion": 1, "corpora": declared}, handle, indent=2, ensure_ascii=False)
        document = {
            "schemaVersion": 1, "corpus": "cfr-9-9.101",
            "baseline": {"contentHash": digests["cfr-9-9.101"],
                         "hashDerivation": "ecfr-versioner-xml", "asOf": "2026-01-01"},
            "extent": {"unit": "section-designation", "sections": ["§ 9.101", "§ 9.102"]},
            "entries": copy.deepcopy(entries if entries is not None else ENTRIES),
        }
        with open(os.path.join(directory, "corpus-map.json"), "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
        return directory

    @staticmethod
    def pack(map_dir, out):
        completed = subprocess.run([sys.executable, PACK, map_dir, "--out", out],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if completed.returncode != 0:
            raise AssertionError(f"pack-map exited {completed.returncode}\n{completed.stdout}")
        (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
        return os.path.join(out, name)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="two-corpus-case-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def corpus(self, name):
        return os.path.join(self.map_dir, name)

    def produce(self, *corpus_paths, out=None, package=None):
        out = out or os.path.join(self.tmp, "engine")
        argv = ["produce", "--package", package or self.nupkg]
        for path in corpus_paths:
            argv += ["--corpus", path]
        argv += ["--name", "TwoSection", "--out", out, "--allow-dirty", "--no-verify"]
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(argv)
        return code, buffer.getvalue(), out

    # --- packaging -------------------------------------------------------------------------

    def test_a_two_corpus_map_packages(self):
        self.assertTrue(os.path.isfile(self.nupkg), self.nupkg)

    def test_the_packaged_manifest_carries_exactly_the_cited_corpora(self):
        """Requirement that an unrelated manifest entry never becomes an engine dependency."""
        with zipfile.ZipFile(self.nupkg) as archive:
            manifest = json.loads(archive.read("map/corpus-manifest.json"))
        self.assertEqual(sorted(c["sourceId"] for c in manifest["corpora"]),
                         ["cfr-9-9.101", "cfr-9-9.102"])

    def test_a_manifest_corpus_the_map_does_not_cite_is_left_out_of_the_package(self):
        directory = os.path.join(self.tmp, "extra-corpus-fixture")
        extra = corpus_entry("cfr-9-9.999", "section-9.101.xml", sha256(FIRST.encode("utf-8")))
        corpora = [corpus_entry(s, n, sha256(t.encode("utf-8"))) for s, n, t in SECTIONS] + [extra]
        self.write_map(directory, corpora=corpora)
        nupkg = self.pack(directory, os.path.join(self.tmp, "extra-feed"))
        with zipfile.ZipFile(nupkg) as archive:
            manifest = json.loads(archive.read("map/corpus-manifest.json"))
        self.assertEqual(sorted(c["sourceId"] for c in manifest["corpora"]),
                         ["cfr-9-9.101", "cfr-9-9.102"])

    # --- intake ----------------------------------------------------------------------------

    def test_the_package_reaches_intake_and_each_corpus_is_hashed_here(self):
        code, output, _ = self.produce(self.corpus("section-9.101.xml"), self.corpus("section-9.102.xml"))
        self.assertEqual(code, NOT_VERIFIED, output)
        for source_id in ("cfr-9-9.101", "cfr-9-9.102"):
            self.assertIn(f"corpus {source_id}:", output)
            self.assertIn("recomputed from", output)
        self.assertIn("agreed by all 2 cited corpus(es)", output)

    def test_a_wrong_second_corpus_is_refused_by_name(self):
        tampered = os.path.join(self.tmp, "section-9.102.xml")
        with open(tampered, "w", encoding="utf-8") as handle:
            handle.write(SECOND.replace("by water", "by rail"))
        code, output, _ = self.produce(self.corpus("section-9.101.xml"), tampered)
        self.assertNotEqual(code, NOT_VERIFIED, output)
        self.assertIn("is not cfr-9-9.102 at its declared baseline", output)

    def test_a_missing_second_corpus_is_refused_by_name(self):
        code, output, _ = self.produce(self.corpus("section-9.101.xml"))
        self.assertNotEqual(code, NOT_VERIFIED, output)
        self.assertIn("cfr-9-9.102", output)
        self.assertIn("no --corpus was supplied", output)

    def test_an_undeclared_source_id_is_refused(self):
        document = {"corpus": "cfr-9-9.101",
                    "entries": [{"locator": {"sourceId": "cfr-9-9.101"}},
                                {"locator": {"sourceId": "cfr-9-9.404"}}]}
        manifest = {"corpora": [corpus_entry("cfr-9-9.101", "section-9.101.xml",
                                             sha256(FIRST.encode("utf-8")))]}
        with self.assertRaises(intake_step.Refused) as caught:
            intake_step.verify_corpora(document, manifest, [self.corpus("section-9.101.xml")])
        self.assertIn("cfr-9-9.404", str(caught.exception))
        self.assertIn("0 times", str(caught.exception))

    # --- the engine and its record ----------------------------------------------------------

    def test_the_engine_carries_both_corpora_and_provenance_names_both(self):
        code, output, out = self.produce(self.corpus("section-9.101.xml"), self.corpus("section-9.102.xml"))
        self.assertEqual(code, NOT_VERIFIED, output)
        for name in ("section-9.101.xml", "section-9.102.xml"):
            self.assertTrue(os.path.isfile(os.path.join(out, "corpus", name)), name)
        with open(os.path.join(out, "provenance.json"), encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(record["provenanceFormat"], 5)
        self.assertNotIn("corpus", record)
        self.assertEqual([c["sourceId"] for c in record["corpora"]], ["cfr-9-9.101", "cfr-9-9.102"])
        self.assertEqual([c["principal"] for c in record["corpora"]], [True, False])
        self.assertEqual([c["path"] for c in record["corpora"]],
                         ["corpus/section-9.101.xml", "corpus/section-9.102.xml"])
        for corpus in record["corpora"]:
            self.assertTrue(corpus["recomputed"])

    def test_recomputation_detects_modification_of_either_corpus(self):
        for name, source_id in (("section-9.101.xml", "cfr-9-9.101"), ("section-9.102.xml", "cfr-9-9.102")):
            with self.subTest(corpus=source_id):
                out = os.path.join(self.tmp, f"engine-{source_id}")
                code, output, _ = self.produce(self.corpus("section-9.101.xml"),
                                               self.corpus("section-9.102.xml"), out=out)
                self.assertEqual(code, NOT_VERIFIED, output)
                with open(os.path.join(out, "corpus", name), "a", encoding="utf-8") as handle:
                    handle.write("\n<!-- tampered -->")
                buffer = io.StringIO()
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    factory.main(["provenance", "--engine", out, "--package", self.nupkg])
                printed = buffer.getvalue()
                self.assertIn(f"corpora[{source_id}].contentHash", printed)
                self.assertIn(f"generated[corpus/{name}].sha256", printed)


if __name__ == "__main__":
    unittest.main()
