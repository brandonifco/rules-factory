#!/usr/bin/env python3
"""Watched reproduction for #333: package verification must bind corpus bytes end to end.

Run: python3 -m unittest tools.tests.mapvalidator.test_package_corpus_identity
"""
import hashlib
import importlib.util
import json
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
PACK = os.path.join(TOOLS, "pack-map.py")
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
ORIGINAL_CORPUS = os.path.join(HOYLE, "hoyle.txt")

_spec = importlib.util.spec_from_file_location("pack_map_identity_repro", PACK)
pack_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pack_map)

sys.path.insert(0, os.path.join(TOOLS, "factory"))
import intake  # noqa: E402


class PackageCorpusIdentityReproduction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="package-corpus-identity-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.map_dir = os.path.join(self.tmp, "hoyle-backgammon")
        os.makedirs(self.map_dir)
        for name in ("corpus-map.json", "corpus-manifest.json", "hoyle.txt",
                     "map-package.json", "CORPUS-LICENCE.txt"):
            shutil.copy2(os.path.join(HOYLE, name), os.path.join(self.map_dir, name))
        self.out = os.path.join(self.tmp, "out")

    @staticmethod
    def replace_once(path, old, new):
        with open(path, "rb") as handle:
            data = handle.read()
        count = data.count(old)
        if count != 1:
            raise AssertionError(f"{path}: expected exactly one watched corpus phrase, found {count}")
        with open(path, "wb") as handle:
            handle.write(data.replace(old, new, 1))

    def mutate_corpus_and_matching_map_evidence_but_not_declared_hash(self):
        self.replace_once(
            os.path.join(self.map_dir, "hoyle.txt"),
            b"Backgammon is played by two persons",
            b"Backgammon is played by three persons",
        )
        path = os.path.join(self.map_dir, "corpus-map.json")
        with open(path, "rb") as handle:
            data = handle.read()
        old = b"Backgammon is played by two persons"
        self.assertGreaterEqual(data.count(old), 2)
        with open(path, "wb") as handle:
            handle.write(data.replace(old, b"Backgammon is played by three persons"))
        # corpus-manifest.json and the map's baseline are deliberately untouched: they still
        # identify the original two-person corpus bytes.

    def pack(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = pack_map.main([self.map_dir, "--out", self.out])
        return code, buffer.getvalue()

    def bind_declarations_to_current_mutated_corpus(self):
        corpus_path = os.path.join(self.map_dir, "hoyle.txt")
        with open(corpus_path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        manifest_path = os.path.join(self.map_dir, "corpus-manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["corpora"][0]["contentHash"] = digest
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        map_path = os.path.join(self.map_dir, "corpus-map.json")
        with open(map_path, encoding="utf-8") as handle:
            document = json.load(handle)
        document["baseline"]["contentHash"] = digest
        with open(map_path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        return digest

    def test_original_cross_stage_identity_break_is_refused(self):
        self.mutate_corpus_and_matching_map_evidence_but_not_declared_hash()

        code, pack_output = self.pack()
        if code != 0:
            self.assertEqual(code, 1, pack_output)
            self.assertFalse(os.path.isdir(self.out) and os.listdir(self.out), pack_output)
            return

        packages = [n for n in os.listdir(self.out) if n.endswith(".nupkg")]
        self.assertEqual(len(packages), 1, pack_output)
        package = os.path.join(self.out, packages[0])

        try:
            intake.intake(package, ORIGINAL_CORPUS, log=None)
        except intake.Refused:
            return

        self.fail(
            "cross-stage corpus identity break reproduced: pack-map accepted altered corpus B "
            "and altered evidence while retaining corpus A's declared hash, then intake accepted "
            "that package alongside original corpus A"
        )

    def test_intake_refuses_original_corpus_a_for_a_package_validly_bound_to_corpus_b(self):
        self.mutate_corpus_and_matching_map_evidence_but_not_declared_hash()
        digest_b = self.bind_declarations_to_current_mutated_corpus()
        code, pack_output = self.pack()
        self.assertEqual(code, 0, pack_output)
        (name,) = [n for n in os.listdir(self.out) if n.endswith(".nupkg")]
        package = os.path.join(self.out, name)
        with self.assertRaises(intake.Refused) as caught:
            intake.intake(package, ORIGINAL_CORPUS, log=None)
        self.assertIn("is not hoyle-1909 at its declared baseline", str(caught.exception))
        self.assertIn(digest_b, str(caught.exception))



if __name__ == "__main__":
    unittest.main()
