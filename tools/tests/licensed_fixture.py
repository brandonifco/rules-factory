"""A synthetic `local-copy` corpus, its map and manifest, for the licensed-copy exception's tests (0022).

Every word of the corpus is invented for these tests. No real licensed text is used anywhere: the
point is to exercise what the factory does with a corpus it may not commit, not to hold one.

`write(root)` lays out, under `root`:

  * `synthetic-licensed/` -- a packable map directory (corpus-map.json, corpus-manifest.json,
    map-package.json and the corpus terms file it names, 0023) whose manifest declares the corpus `never-commit`, `local-copy` with
    `envVar` ENV_VAR, and holds no corpus file;
  * `licensed-copy/synthetic.txt` -- the corpus, outside the map directory, as an operator's
    licensed copy would be.

Its `hashDerivation` is DERIVATION, SHA-256 of the file's bytes, which the factory does not know:
a test adds it to intake's HASH_DERIVATIONS for the duration (`derivation()`), so no real
derivation's name is borrowed for a file it does not describe.

The exception is a run with the real dotnet (scripts/validate-engine.sh, decision 0028): the engine's
gate runs as a separate process from the vendored intake.py, where nothing can be patched in. There
`python3 tools/tests/licensed_fixture.py <root> gutenberg-plain-text-including-boilerplate` writes the
same fixture under RAW_BYTES_DERIVATION, the SHA-256 of the file's bytes the vendored table already
has, and its licence text says the name is borrowed.
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
# A derivation intake.HASH_DERIVATIONS knows that is SHA-256 of the file's bytes, for real-dotnet runs only.
RAW_BYTES_DERIVATION = "gutenberg-plain-text-including-boilerplate"
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


def map_document(derivation=DERIVATION):
    return {
        "schemaVersion": 1,
        "corpus": SOURCE_ID,
        "baseline": {"contentHash": content_hash(), "hashDerivation": derivation},
        "extent": {"unit": "page", "from": 1, "to": 2},
        "entries": [
            _entry("captain-count", "Two captains play", "Skirmish / p. 1",
                   "A skirmish of the invented game is played by two captains, each with seven pawns.",
                   "Demonstrate that a skirmish has exactly two captains."),
            _entry("one-pawn-per-turn", "One pawn moves per turn", "Skirmish / p. 2",
                   "A captain moves one pawn per turn, and never onto a square another pawn occupies.",
                   "Demonstrate that a turn moves exactly one pawn."),
            dict(_entry("occupied-square", "A pawn never moves onto an occupied square", "Skirmish / p. 2",
                        "A captain moves one pawn per turn, and never onto a square another pawn occupies.",
                        "The words 'another pawn occupies' are the whole of the rule; whose pawn is not said."),
                 kind="operation", clarity="ambiguous",
                 ambiguity={"question": "Does 'a square another pawn occupies' include a square the moving "
                                        "captain's own pawn occupies, or only an opposing pawn's square?",
                            "fate": "unresolved", "unresolvedReason": "RequiresInterpretation"}),
        ],
    }


def manifest_document(derivation=DERIVATION):
    return {
        "schemaVersion": 1,
        "corpora": [{
            "sourceId": SOURCE_ID,
            "title": "Synthetic Licensed Rulebook (invented for tests)",
            "adapter": "plain-text",
            "locatorGrammar": "chapter-section-and-page-marker",
            "contentHash": content_hash(),
            "hashDerivation": derivation,
            "boundaryPolicy": "never-commit",
            "licence": "commercial (synthetic: stands in for a licensed corpus in tests)"
                       + ("" if derivation == DERIVATION else
                          f"; {derivation} is borrowed only because it is SHA-256 of the bytes, for a real-dotnet run"),
            "verification": "local-copy",
            "envVar": ENV_VAR,
            "quotation": "verbatim",
            "randomness": "none",
            # 0026: the two invented sentences point at nothing, so the zero is declared, not silent.
            "pointerPhrases": [],
            "pointerPhrasesReason": "The corpus is two invented sentences, and neither refers to another passage.",
            "references": [],
        }],
    }


def _dump(path, document):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write(root, derivation=DERIVATION):
    """(map directory, corpus path) under `root`."""
    map_dir = os.path.join(root, MAP_NAME)
    os.makedirs(map_dir)
    _dump(os.path.join(map_dir, "corpus-map.json"), map_document(derivation))
    _dump(os.path.join(map_dir, "corpus-manifest.json"), manifest_document(derivation))
    _dump(os.path.join(map_dir, "map-package.json"),
          {"version": VERSION, "licence": {"corpusTerms": "CORPUS-LICENCE.txt"}})
    with open(os.path.join(map_dir, "CORPUS-LICENCE.txt"), "w", encoding="utf-8") as handle:
        handle.write(manifest_document(derivation)["corpora"][0]["licence"] + "\n")
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


if __name__ == "__main__":
    import sys
    if len(sys.argv) not in (2, 3) or sys.argv[2:] not in ([], [DERIVATION], [RAW_BYTES_DERIVATION]):
        sys.exit(f"usage: {sys.argv[0]} <root> [{RAW_BYTES_DERIVATION}]")
    print(*write(sys.argv[1], *sys.argv[2:]))
