#!/usr/bin/env python3
"""`factory trace --html` renders the trace and says nothing the trace does not (#580).

The page is compared with the trace it was rendered from, never with pixels: every relationship
appears once, wearing the badge of its own evidence class, with its value and how it is known;
inferred implementation candidates are boxed differently from recorded test evidence; every entry
has an anchor the index links to; the filters are CSS over radio buttons that are siblings of the
entries; the page's own words claim no more than the evidence; it is one file with no script and
no external asset, the same bytes every time, and a function of the trace alone; a private engine's
page says so first; and a report inside the engine is refused.

Run: python3 -m pytest tools/tests/factory/test_factory_trace_report.py
"""
import collections
import copy
import html
import html.parser
import json
import os
import re
import shutil
import tempfile
import unittest

# The fixtures, by module: a TestCase bound here would be collected and run a second time.
from tests.factory import test_factory_trace as fixture  # noqa: E402
from tests.factory import test_two_corpus_map as two  # noqa: E402

factory = fixture.factory
tracereport = factory.tracereport
trace_step = factory.trace_step

#: Words that claim more than any evidence class supports, which the page's own text never uses.
OVERCLAIMS = re.compile(r"\b(prove[sd]?|proof|implements|verif(?:y|ied|ies)|conformant|healthy|score|grade)\b", re.I)


class Facts(html.parser.HTMLParser):
    """Each element carrying `data-evidence`, with its text, and the classes of the boxes it sits in."""

    def __init__(self):
        super().__init__()
        self.stack, self.facts, self.open, self.ids, self.links = [], [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append((tag, attrs.get("class") or ""))
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.links.append(attrs["href"][1:])
        if "data-evidence" in attrs:
            item = {"evidence": attrs["data-evidence"], "boxes": [c for _, c in self.stack[:-1]], "text": ""}
            self.facts.append(item)
            self.open.append((item, len(self.stack)))

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()[0] == tag:
                break
        self.open = [(item, depth) for item, depth in self.open if depth <= len(self.stack)]

    def handle_data(self, data):
        for item, _ in self.open:
            item["text"] += data


def every_fact(node):
    yield from fixture.facts(node)


class TraceReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp(prefix="trace-report-")
        map_dir = two.TwoCorpusMap.write_map(os.path.join(cls.shared, "two-section-fixture"))
        nupkg = two.TwoCorpusMap.pack(map_dir, os.path.join(cls.shared, "feed"))
        cls.packages = fixture.feed(os.path.join(cls.shared, "packages"), [nupkg])
        cls.engine = os.path.join(cls.shared, "engine")
        fixture.produce([nupkg], [os.path.join(map_dir, name) for _, name, _ in two.SECTIONS], "TwoSection", cls.engine)
        os.makedirs(os.path.join(cls.engine, "overlay"), exist_ok=True)
        with open(os.path.join(cls.engine, "overlay", "listed-in-the-table.json"), "w", encoding="utf-8") as handle:
            json.dump({"status": "implemented", "implementedIn": {"ruleset": "fixture", "version": 1},
                       "tests": [{"test": "ListedTests.Holds", "mutation": fixture.MUTATION}]}, handle)
        handler = os.path.join(cls.engine, "src", "TwoSection", "Handlers", "ListedInTheTable.cs")
        os.makedirs(os.path.dirname(handler), exist_ok=True)
        with open(handler, "w", encoding="utf-8") as handle:
            handle.write(fixture.HANDLER)
        code, out, err = fixture.run(["trace", "--engine", cls.engine, "--json"], cls.packages)
        assert code == 0, err
        cls.trace = json.loads(out)
        cls.page = tracereport.render(cls.trace)
        cls.parsed = Facts()
        cls.parsed.feed(cls.page)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def test_every_relationship_appears_once_with_the_badge_of_its_own_class(self):
        wanted = collections.Counter(f["evidence"] for f in every_fact(self.trace))
        shown = collections.Counter(f["evidence"] for f in self.parsed.facts)
        self.assertEqual(shown, wanted)
        self.assertEqual(dict(wanted), {c: n for c, n in self.trace["summary"]["evidence"].items() if n})
        for item in self.parsed.facts:
            self.assertIn(item["evidence"].upper(), item["text"])

    def test_every_value_and_how_it_is_known_is_on_the_page(self):
        for item in every_fact(self.trace):
            how = item.get("basis") or item.get("mechanism") or item.get("why")
            self.assertIn(html.escape(how, quote=True), self.page)
            if item["evidence"] != "unknown":
                self.assertIn(html.escape(tracereport.shown(item["value"]), quote=True), self.page)

    def test_inferred_candidates_are_boxed_apart_from_recorded_test_evidence(self):
        candidates = [f for f in self.parsed.facts if any("candidate" in b.split() for b in f["boxes"])]
        tested = [f for f in self.parsed.facts if any("test" in b.split() for b in f["boxes"])]
        self.assertTrue(candidates)
        self.assertTrue(tested)
        self.assertEqual({f["evidence"] for f in candidates}, {"inferred", "unknown"})
        self.assertEqual({f["evidence"] for f in tested}, {"recorded"})
        css = tracereport.CSS
        rule = lambda name: re.search(r"\." + re.escape(name) + r" \{([^}]*)\}", css).group(1)  # noqa: E731
        self.assertIn("dashed", rule("candidate"))
        self.assertNotIn("dashed", rule("test"))
        self.assertIn("dashed", rule("b-inferred"))
        self.assertNotIn("dashed", rule("b-recorded"))

    def test_every_entry_has_an_anchor_and_the_index_links_to_it(self):
        links = collections.Counter(self.parsed.links)
        for listed in self.trace["entries"]:
            target = tracereport.anchor(listed["id"]["value"])
            self.assertEqual(self.parsed.ids.count(target), 1)
            # One link from the index of entries, and one from the entry's own heading.
            self.assertEqual(links[target], 2, target)

    def test_every_gap_is_on_the_page_under_its_subject(self):
        for gap in self.trace["gaps"]:
            self.assertIn(html.escape(gap["why"], quote=True), self.page)
        section = self.page.split(f'id="{tracereport.anchor("w-is-water-only")}"', 1)[1].split("</section>", 1)[0]
        own = [g for g in self.trace["gaps"] if g["subject"] == "entry:w-is-water-only"]
        self.assertIn(f"Gaps ({len(own)})", section)

    def test_the_filters_are_css_over_radios_beside_the_entries(self):
        self.assertIn("#f-gaps:checked ~ .entries .entry:not(.has-gaps) { display: none; }", self.page)
        self.assertIn("#f-s-implemented:checked ~ .entries .entry:not(.status-implemented) { display: none; }",
                      self.page)
        filters = self.page.split('<div class="filters">', 1)[1].split('<div class="entries">', 1)[0]
        self.assertNotIn("<div", filters, "a radio inside another element is no sibling of .entries")
        self.assertIn('id="f-gaps"', filters)

    def test_the_pages_own_words_claim_no_more_than_the_evidence(self):
        # The fixture's own data says none of these words, so any on the page are the renderer's.
        self.assertIsNone(OVERCLAIMS.search(json.dumps(self.trace)))
        text = html.unescape(re.sub(r"<[^>]+>", " ", self.page.split("</style>", 1)[1]))
        self.assertIsNone(OVERCLAIMS.search(text), OVERCLAIMS.search(text))

    def test_one_file_no_script_no_external_asset_and_the_same_bytes_every_time(self):
        self.assertNotIn("<script", self.page)
        self.assertNotIn("<link", self.page)
        self.assertNotRegex(self.page, r'\b(?:src|href)="(?!#)')
        self.assertNotIn("url(", self.page)
        self.assertEqual(tracereport.render(copy.deepcopy(self.trace)), self.page)

    def test_the_page_is_a_function_of_the_trace_alone(self):
        moved = os.path.join(self.shared, "gone")
        os.rename(self.engine, moved)
        try:
            self.assertEqual(tracereport.render(copy.deepcopy(self.trace)), self.page)
        finally:
            os.rename(moved, self.engine)

    def test_a_private_engines_page_says_so_before_anything_else(self):
        private = copy.deepcopy(self.trace)
        private["engine"]["distribution"]["value"] = "private"
        page = tracereport.render(private)
        banner = page.index("as private as the engine")
        self.assertLess(banner, page.index("How to read it"))
        self.assertNotIn("as private as the engine", self.page)

    def test_the_cli_writes_the_page_outside_the_engine_and_the_same_bytes_twice(self):
        target = os.path.join(self.shared, "out", "trace.html")
        os.makedirs(os.path.dirname(target))
        self.addCleanup(shutil.rmtree, os.path.dirname(target), True)
        written = []
        for _ in range(2):
            code, out, err = fixture.run(["trace", "--engine", self.engine, "--html", target], self.packages)
            self.assertEqual(code, 0, err)
            with open(target, encoding="utf-8") as handle:
                written.append(handle.read())
        self.assertEqual(written[0], written[1])
        self.assertEqual(written[0], self.page)
        self.assertIn("wrote", out)

    def test_a_report_inside_the_engine_is_refused_and_nothing_is_written(self):
        target = os.path.join(self.engine, "docs", "trace.html")
        code, _, err = fixture.run(["trace", "--engine", self.engine, "--html", target], self.packages)
        self.assertEqual(code, 1)
        self.assertIn("inside the engine", err)
        self.assertFalse(os.path.exists(target))

    def test_json_and_html_together_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as caught:
            fixture.run(["trace", "--engine", self.engine, "--json", "--html", os.path.join(self.shared, "x.html")],
                        self.packages)
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
