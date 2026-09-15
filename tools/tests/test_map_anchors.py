#!/usr/bin/env python3
"""The quotes the example maps anchor `assertedBy` and `draws` in are the corpus's words (0025).

`check-map.py` accepts a party or a die named inside a span an entry's `note` quotes, and it
reads no corpus, so it cannot tell a quote from a mapper's sentence in quotation marks. This
test closes that for the maps this repository ships: every quoted span that anchors a value is
found, whitespace-normalised, in the committed corpus text. It is proved able to fail on a span
the corpus does not contain.

Run: python3 -m pytest tools/tests/test_map_anchors.py
"""
import html
import importlib.util
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(REPO, "tools", "check-map.py")

_spec = importlib.util.spec_from_file_location("check_map_anchors", TOOL)
check_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_map)

EXAMPLES = os.path.join(REPO, "examples")
# Each map, and the committed corpus its entries quote.
MAPS = [
    ("hoyle-backgammon/corpus-map.json", "hoyle-backgammon/hoyle.txt"),
    ("srd-52-combat/corpus-map.json", "srd-52-combat/srd-5.2.1.txt"),
    ("faa-part-107/corpus-map.json", "faa-part-107/part107.xml"),
    ("faa-part-107-temporal/corpus-map-2020-01-01.json", "faa-part-107-temporal/part107-2020-01-01.xml"),
]


def normalise(text):
    return " ".join(text.split())


def corpus_text(path):
    with open(os.path.join(EXAMPLES, path), encoding="utf-8") as handle:
        text = handle.read()
    if path.endswith(".xml"):
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return normalise(text)


def anchoring_spans(entry):
    """(value, the note spans naming it) for each value anchored in the note and not the evidence."""
    values = [v for v in entry.get("assertedBy") or [] if v != check_map.CALLER]
    draws = entry.get("draws")
    values += [d["dice"] for d in (draws if isinstance(draws, list) else [draws] if draws else [])]
    found = []
    for value in values:
        if check_map.anchored(entry, value) == "note":
            found.append((value, [s for s in check_map.quoted_spans(entry.get("note"))
                                  if check_map.names_term(s, value)]))
    return found


def unfound(entry, corpus):
    """The values whose every anchoring note span is missing from the corpus."""
    return [(value, spans) for value, spans in anchoring_spans(entry)
            if not any(normalise(span) in corpus for span in spans)]


class TestNoteAnchorsAreTheCorpus(unittest.TestCase):
    def test_every_note_anchor_in_every_example_map_is_in_its_corpus(self):
        anchored = 0
        for map_path, corpus_path in MAPS:
            corpus = corpus_text(corpus_path)
            with open(os.path.join(EXAMPLES, map_path), encoding="utf-8") as handle:
                document = json.load(handle)
            for entry in document["entries"]:
                with self.subTest(map=map_path, entry=entry.get("id")):
                    anchored += len(anchoring_spans(entry))
                    self.assertEqual(unfound(entry, corpus), [])
        self.assertGreater(anchored, 0, "no note anchored anything; this test proved nothing")

    def test_a_quote_the_corpus_does_not_contain_is_found_out(self):
        corpus = corpus_text("faa-part-107/part107.xml")
        entry = {"assertedBy": ["remote pilot in command"], "evidence": "Assess the operating environment.",
                 "note": "Named in the lead-in, \"Before flight, the remote pilot in command must:\"."}
        self.assertEqual(len(unfound(entry, corpus)), 1)
        entry["note"] = "Named in the lead-in, \"Prior to flight, the remote pilot in command must:\"."
        self.assertEqual(unfound(entry, corpus), [])


if __name__ == "__main__":
    unittest.main()
