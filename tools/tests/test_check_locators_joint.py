"""A map citing corpora read by two grammars is locator-checked and packed (#681).

The fixtures are built in a temporary directory from corpora this repository already commits: the
eCFR Part 107 slice (`ecfr-xml`), the FRCP slice and the Code chapter of examples/can-spam (`uslm-xml`).
Nothing under examples/ is written.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(TOOLS)
JOINT = os.path.join(TOOLS, "check-locators-joint.py")
PACK = os.path.join(TOOLS, "pack-map.py")


def example(*parts):
    return os.path.join(REPO, "examples", *parts)


def load(*parts):
    with open(example(*parts), encoding="utf-8") as handle:
        return json.load(handle)


def entry_of(map_name, entry_id):
    """A committed entry, without the edges that name entries the fixture does not carry."""
    found = next(e for e in load(map_name, "corpus-map.json")["entries"] if e["id"] == entry_id)
    return {k: v for k, v in found.items() if k not in ("dependsOn", "enabledBy", "suspendedBy", "crossReferences")}


def corpus_row(map_name, source_id):
    return next(c for c in load(map_name, "corpus-manifest.json")["corpora"] if c["sourceId"] == source_id)


def run(*argv):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, *argv], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          env=env, cwd=REPO)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="joint-locators-")
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name, value):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            if isinstance(value, str):
                handle.write(value)
            else:
                json.dump(value, handle, indent=2, ensure_ascii=False)
        return path

    def copy(self, *parts):
        shutil.copy(example(*parts), self.dir)


class JointCheck(Fixture):
    """Part 107 (eCFR) and FRCP Rule 6 (USLM) in one map with one extent."""

    def setUp(self):
        super().setUp()
        self.copy("faa-part-107", "part107.xml")
        self.copy("frcp-6-12-81", "frcp-6-12-81.xml")
        self.manifest = self.write("corpus-manifest.json", {"schemaVersion": 1, "corpora": [
            corpus_row("faa-part-107", "cfr-14-107"), corpus_row("frcp-6-12-81", "frcp-6-12-81")]})
        self.document = {
            "schemaVersion": 1, "corpus": "cfr-14-107", "baseline": load("faa-part-107", "corpus-map.json")["baseline"],
            "extent": {"unit": "section-designation", "sections": ["§ 107.51", "§ 107.65", "Rule 6"]},
            "entries": [entry_of("faa-part-107", "altitude-limit"), entry_of("faa-part-107", "knowledge-recency"),
                        entry_of("frcp-6-12-81", "court-may-extend-for-good-cause")],
        }

    def check(self, document=None):
        return run(JOINT, self.write("corpus-map.json", document or self.document), "--manifest", self.manifest)

    def test_each_grammar_checks_its_own_share_and_the_map_passes(self):
        done = self.check()
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("share 1: ecfr-xml, cfr-14-107: 2 entries, 2 extent section(s)", done.stdout)
        self.assertIn("share 2: uslm-xml, frcp-6-12-81: 1 entries, 1 extent section(s)", done.stdout)
        self.assertIn("ok -- 3 entries in 2 share(s)", done.stdout)

    def test_a_wrong_citation_in_either_grammar_fails_the_map(self):
        for position, wrong in ((0, "§ 107.51(a)"), (2, "Rule 6(b)(2)")):
            with self.subTest(wrong=wrong):
                document = json.loads(json.dumps(self.document))
                document["entries"][position]["locator"]["citation"] = wrong
                done = self.check(document)
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn(f"share {1 if position == 0 else 2} (", done.stdout)

    def test_a_map_that_cannot_be_divided_is_not_verified(self):
        def broken(change):
            document = json.loads(json.dumps(self.document))
            change(document)
            return document
        cases = {
            "no locator.sourceId": broken(lambda d: d["entries"][2]["locator"].pop("sourceId")),
            "which the manifest does not declare": broken(lambda d: d["entries"][2]["locator"].update(sourceId="usc-1-1")),
            "which no corpus this map cites contains": broken(lambda d: d["extent"]["sections"].append("Rule 99")),
            "not a corpus this map's entries cite": broken(lambda d: d["extent"].update(unreachable=[
                {"sourceId": "usc-1-1", "opensWith": "x", "reason": "no-unit-for-element", "requires": "x"}])),
        }
        for why, document in cases.items():
            with self.subTest(why=why):
                done = self.check(document)
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn("NOT VERIFIED", done.stdout)
                self.assertIn(why, done.stdout)


class JointPack(Fixture):
    """pack-map.py packs a map citing an eCFR and a USLM corpus, each rebuilt by rules-corpus (0048)."""

    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.dir, "two-grammar-map")  # the package id is made from the directory's name
        os.mkdir(self.dir)
        for name in ("part107.xml", "part107.corpus.build.json", "part107.corpus.expect.json"):
            self.copy("faa-part-107", name)
        for name in ("usc15-ch103.xml", "usc15-ch103.corpus.build.json", "usc15-ch103.corpus.expect.json"):
            self.copy("can-spam", name)

    def test_the_two_grammar_map_packs_and_its_record_binds_both_corpora(self):
        with open(os.path.join(self.dir, "usc15-ch103.xml"), "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        uslm = dict(corpus_row("frcp-6-12-81", "frcp-6-12-81"), sourceId="usc-15-ch103", title="15 U.S.C. chapter 103",
                    contentHash=digest, hashDerivation="olrc-uslm-chapter-slice-verbatim", asOf="2026-10-07",
                    committedPath="usc15-ch103.xml", references=[],
                    pointerPhrases=[], pointerPhrasesReason="the fixture cites one passage and follows no pointer")
        self.write("corpus-manifest.json", {"schemaVersion": 1, "corpora": [corpus_row("faa-part-107", "cfr-14-107"), uslm]})
        separability = ("If any provision of this chapter or the application thereof to any person or circumstance is "
                        "held invalid, the remainder of this chapter and the application of such provision to other "
                        "persons or circumstances shall not be affected.")
        self.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "cfr-14-107", "baseline": load("faa-part-107", "corpus-map.json")["baseline"],
            "extent": {"unit": "section-designation", "sections": ["§ 107.51", "/us/usc/t15/s7713"]},
            "entries": [entry_of("faa-part-107", "altitude-limit"),
                        {"id": "fixture-statute-passage", "name": "A passage of the second corpus",
                         "locator": {"sourceId": "usc-15-ch103", "citation": "/us/usc/t15/s7713"},
                         "kind": "value", "scope": "out", "clarity": "clear", "evidence": separability,
                         "status": "declined", "note": "A fixture entry: it exists so the map cites a second grammar."}],
        })
        self.write("CORPUS-LICENCE.txt", "Fixture corpora.\n\nAs the manifest's `licence` field records it:\n\n"
                                         "public-domain-us-government\n")
        self.write("map-package.json", {"version": "0.1.0", "licence": {"corpusTerms": "CORPUS-LICENCE.txt"}})
        out = tempfile.mkdtemp(prefix="joint-pack-")
        self.addCleanup(shutil.rmtree, out)
        done = run(PACK, self.dir, "--out", out, "--repo-root", REPO)
        self.assertEqual(done.returncode, 0, done.stdout[-4000:])
        self.assertIn("tools/check-locators-joint.py (ecfr-xml, uslm-xml)", done.stdout)
        (package,) = os.listdir(out)
        with zipfile.ZipFile(os.path.join(out, package)) as archive:
            record = json.loads(archive.read("map/verification.json"))
        self.assertEqual([c["sourceId"] for c in record["corpora"]], ["cfr-14-107", "usc-15-ch103"])


if __name__ == "__main__":
    unittest.main()
