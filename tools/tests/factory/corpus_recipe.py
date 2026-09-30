"""A corpus file with the rules-corpus recipe committed beside it, for tests (#558).

Intake builds and verifies every corpus with rules-corpus from the build definition and expectation
beside its file (tools/factory/rulescorpus.py), so a test that puts a corpus somewhere puts its
recipe there too.
"""
import json
import os
import sys

FACTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "factory")
if FACTORY not in sys.path:
    sys.path.insert(0, FACTORY)
import rulescorpus  # noqa: E402


def _write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def write_corpus(directory, name, data, source_id, derivation, as_of=None, expect=()):
    """`data` at `directory/name`, with a definition whose baseline names it and an expectation."""
    path = os.path.join(directory, name)
    with open(path, "wb") as handle:
        handle.write(data)
    baseline = {"artifact": "corpus", "hashDerivation": derivation, "sourceId": source_id}
    if as_of is not None:
        baseline["asOf"] = as_of
    definition = {"schema": "rules-corpus/build/1", "corpusId": "synthetic",
                  "sources": [{"id": "corpus", "mediaType": "text/plain", "origin": "synthetic", "path": name}],
                  "derivations": [], "external": [], "baselines": [baseline]}
    definition_path, expectation_path = rulescorpus.companions(path)
    _write(definition_path, json.dumps(definition, indent=2, sort_keys=True) + "\n")
    _write(expectation_path, json.dumps({"expectNotVerified": list(expect)}) + "\n")
    return path


def carry_recipe(source_corpus, corpus):
    """Beside `corpus`, the build definition and expectation committed beside `source_corpus`, the
    definition naming `corpus`'s file: a copy of a corpus is built from its recipe."""
    for source, target in zip(rulescorpus.companions(source_corpus), rulescorpus.companions(corpus)):
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        _write(target, text.replace(json.dumps(os.path.basename(source_corpus)),
                                    json.dumps(os.path.basename(corpus))))
