"""A synthetic `local-copy` corpus, its map and manifest, for the licensed-copy exception's tests (0022).

Every word of the corpus is invented for these tests. No real licensed text is used anywhere: the
point is to exercise what the factory does with a corpus it may not commit, not to hold one.

`write(root)` lays out, under `root`:

  * `synthetic-licensed/` -- a packable map directory (corpus-map.json, corpus-manifest.json,
    map-package.json) whose manifest declares the corpus `never-commit`, `local-copy` with
    `envVar` ENV_VAR, and holds no corpus file;
  * `licensed-copy/synthetic.txt` -- the corpus, outside the map directory, as an operator's
    licensed copy would be.

Its `hashDerivation` is DERIVATION, SHA-256 of the file's bytes, which the factory does not know:
a test adds it to intake's HASH_DERIVATIONS for the duration (`derivation()`), so no real
derivation's name is borrowed for a file it does not describe.
"""
import hashlib
import json
import os
from unittest import mock

MAP_NAME = "synthetic-licensed"
PACKAGE_ID = "RulesFactory.Maps.SyntheticLicensed"
VERSION = "1.0.0"
SOURCE_ID = "synthetic-licensed-rules"
ENV_VAR = "RULES_FACTORY_TEST_SYNTHETIC_LICENSED"
DERIVATION = "synthetic-test-bytes"
ENGINE = "SyntheticLicensed"

CORPUS = """SYNTHETIC LICENSED RULEBOOK -- invented for rules-factory tests

{1}
A skirmish of the invented game is played by two captains, each with seven pawns.

{2}
A captain moves one pawn per turn, and never onto a square another pawn occupies.
"""


def _entry(entry_id, name, citation, evidence, note):
    return {
        "id": entry_id,
        "name": name,
        "locator": {"sourceId": SOURCE_ID, "citation": citation},
        "kind": "value",
        "scope": "in",
        "clarity": "clear",
        "dependsOn": [],
        "evidence": evidence,
        "status": "mapped",
        "note": note,
    }


def corpus_bytes():
    return CORPUS.encode("utf-8")


def content_hash():
    return hashlib.sha256(corpus_bytes()).hexdigest()


def map_document():
    return {
        "schemaVersion": 1,
        "corpus": SOURCE_ID,
        "baseline": {"contentHash": content_hash(), "hashDerivation": DERIVATION},
        "extent": {"unit": "page", "from": 1, "to": 2},
        "entries": [
            _entry("captain-count", "Two captains play", "Skirmish / p. 1",
                   "A skirmish of the invented game is played by two captains, each with seven pawns.",
                   "Demonstrate that a skirmish has exactly two captains."),
            _entry("one-pawn-per-turn", "One pawn moves per turn", "Skirmish / p. 2",
                   "A captain moves one pawn per turn, and never onto a square another pawn occupies.",
                   "Demonstrate that a turn moves exactly one pawn."),
        ],
    }


def manifest_document():
    return {
        "schemaVersion": 1,
        "corpora": [{
            "sourceId": SOURCE_ID,
            "title": "Synthetic Licensed Rulebook (invented for tests)",
            "adapter": "plain-text",
            "locatorGrammar": "chapter-section-and-page-marker",
            "contentHash": content_hash(),
            "hashDerivation": DERIVATION,
            "boundaryPolicy": "never-commit",
            "licence": "commercial (synthetic: stands in for a licensed corpus in tests)",
            "verification": "local-copy",
            "envVar": ENV_VAR,
            "quotation": "verbatim",
            "randomness": "none",
            "references": [],
        }],
    }


def _dump(path, document):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write(root):
    """(map directory, corpus path) under `root`."""
    map_dir = os.path.join(root, MAP_NAME)
    os.makedirs(map_dir)
    _dump(os.path.join(map_dir, "corpus-map.json"), map_document())
    _dump(os.path.join(map_dir, "corpus-manifest.json"), manifest_document())
    _dump(os.path.join(map_dir, "map-package.json"), {"version": VERSION})
    corpus_dir = os.path.join(root, "licensed-copy")
    os.makedirs(corpus_dir)
    corpus = os.path.join(corpus_dir, "synthetic.txt")
    with open(corpus, "wb") as handle:
        handle.write(corpus_bytes())
    return map_dir, corpus


def derivation(intake_module):
    """A context manager adding DERIVATION to `intake_module.HASH_DERIVATIONS`."""
    return mock.patch.dict(intake_module.HASH_DERIVATIONS,
                           {DERIVATION: lambda data: hashlib.sha256(data).hexdigest()})


FAKE_GH = r'''#!/usr/bin/env python3
"""A stand-in for `gh` (FACTORY_GH): `api user --jq .login` prints $FAKE_GH_LOGIN, or fails as told."""
import os, sys
with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join(sys.argv[1:]) + "\n")
if os.environ.get("FAKE_GH_FAIL"):
    print("To get started with GitHub CLI, please run:  gh auth login", file=sys.stderr)
    sys.exit(4)
if sys.argv[1:] != ["api", "user", "--jq", ".login"]:
    print("fake gh: unexpected arguments", file=sys.stderr)
    sys.exit(2)
print(os.environ["FAKE_GH_LOGIN"])
'''


def fake_gh(directory):
    path = os.path.join(directory, "gh")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(FAKE_GH)
    os.chmod(path, 0o755)
    return path
