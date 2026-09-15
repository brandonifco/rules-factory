"""tools/extract-pdf-pages.py, and the derived text it writes read by the PDF text checker (0028, #139).

Every PDF here is synthetic, and so is pdftotext: a stand-in script on PATH that reads the "PDF"
as a JSON list of page texts and answers `-f Q -l Q` with page Q and a form feed, the way poppler
does. The derivation is about which pages are asked for, how they are marked and what is refused,
and all of that is exercised without poppler or any real book.
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools", "factory"))
import intake  # noqa: E402


def load(name, *path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, *path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extractor = load("extract_pdf_pages", "tools", "extract-pdf-pages.py")
pdf_text_checker = load("check_locators_pdf_text_0028", "examples", "srd-52-combat", "check-locators-pdf-text.py")
check_map = load("check_map_0028", "tools", "check-map.py")

# A book whose front matter is unnumbered: PDF page Q prints folio Q - 1. Page 1 is the cover.
PAGES = [
    "Demo Rules\n\nCover\n",
    "Contents\n\n1\n",
    "Rolling\nA roll is made with two dice.\n\n2\n",
    "Results\nThe higher total wins the round.\n\n3\n",
    "Setup\nEach player takes ten counters.\n\n4\n",
    "Ties\nOn a tie, both players roll again.\n\n5\n",
]


def manifest(pdf_bytes, pages=((2, 3), (5, 5)), offset=1, content_hash="0" * 64):
    return {
        "schemaVersion": 1,
        "corpora": [{
            "sourceId": "demo-book",
            "adapter": "pdftotext-page-marked",
            "locatorGrammar": "heading-path-and-printed-page",
            "contentHash": content_hash,
            "hashDerivation": extractor.DERIVATION,
            "quotedText": {"derivation": extractor.DERIVATION, "extractedFrom": "demo.pdf"},
            "sourcePdf": {"sha256": hashlib.sha256(pdf_bytes).hexdigest(), "bytes": len(pdf_bytes),
                          "envVar": "DEMO_BOOK_PDF"},
            "derivedText": {"extractor": "pdftotext", "extractorVersion": "24.02.0", "pdfPageOffset": offset,
                            "printedPages": [{"from": a, "to": b} for a, b in pages]},
            "boundaryPolicy": "never-commit",
            "licence": "commercial",
            "verification": "local-copy",
            "envVar": "DEMO_BOOK_TEXT",
            "quotation": "verbatim",
            "randomness": "seeded",
        }],
    }


FAKE_PDFTOTEXT = textwrap.dedent("""\
    #!{python}
    import json, os, sys
    args = sys.argv[1:]
    if args == ["-v"]:
        sys.stderr.write("pdftotext version " + os.environ.get("FAKE_PDFTOTEXT_VERSION", "24.02.0") + "\\n")
        sys.exit(0)
    first = int(args[args.index("-f") + 1])
    last = int(args[args.index("-l") + 1])
    with open(os.environ["FAKE_PDFTOTEXT_LOG"], "a") as log:
        log.write(" ".join(args) + "\\n")
    pages = json.load(open(args[-2]))
    for page in range(first, last + 1):
        sys.stdout.write(pages[page - 1] + "\\f")
""")


class ExtractCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.bin = os.path.join(self.root, "bin")
        os.makedirs(self.bin)
        fake = os.path.join(self.bin, "pdftotext")
        with open(fake, "w", encoding="utf-8") as handle:
            handle.write(FAKE_PDFTOTEXT.format(python=sys.executable))
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
        self.log = os.path.join(self.root, "calls.log")
        self.work = os.path.join(self.root, "local")
        os.makedirs(self.work)
        self.write_pdf(PAGES)
        env = {"PATH": self.bin + os.pathsep + os.environ.get("PATH", ""), "FAKE_PDFTOTEXT_LOG": self.log,
               "FAKE_PDFTOTEXT_VERSION": "24.02.0"}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_pdf(self, page_texts, **overrides):
        self.pdf = os.path.join(self.root, "demo.pdf")
        with open(self.pdf, "w", encoding="utf-8") as handle:
            json.dump(page_texts, handle)
        with open(self.pdf, "rb") as handle:
            self.pdf_bytes = handle.read()
        self.write_manifest(manifest(self.pdf_bytes, **overrides))

    def write_manifest(self, document):
        self.manifest = os.path.join(self.work, "corpus-manifest.json")
        with open(self.manifest, "w", encoding="utf-8") as handle:
            json.dump(document, handle)

    def run_tool(self, *args):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = extractor.main(["--manifest", self.manifest, "--pdf", self.pdf, *args])
        return code, out.getvalue()

    def derive(self):
        text = os.path.join(self.work, "demo.txt")
        code, output = self.run_tool("--write", text)
        self.assertEqual(code, 0, output)
        return text


class TestWrite(ExtractCase):
    def test_markers_are_printed_pages_and_only_the_declared_pdf_pages_are_read(self):
        with open(self.derive(), encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(text, "{pdftotext-24.02.0-printed-page-marked pages=2-3,5 offset=+1}\n"
                               "{2}\n" + PAGES[2] + "{3}\n" + PAGES[3] + "{5}\n" + PAGES[5])
        with open(self.log, encoding="utf-8") as handle:
            asked = [re.search(r"-f (\d+) -l (\d+)", line).groups() for line in handle]
        self.assertEqual(asked, [("3", "3"), ("4", "4"), ("6", "6")])

    def test_the_record_names_the_extractor_and_the_body_digest_and_holds_no_text(self):
        text = self.derive()
        with open(text, "rb") as handle:
            body = handle.read()
        with open(text + ".derivation.json", encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(record["bodySha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual((record["extractor"], record["extractorVersion"]), ("pdftotext", "24.02.0"))
        self.assertEqual(record["argv"], extractor.ARGV_TEMPLATE)
        self.assertEqual(record["pdfPages"], [3, 4, 6])
        self.assertEqual(record["sourcePdf"]["sha256"], hashlib.sha256(self.pdf_bytes).hexdigest())
        self.assertNotIn("dice", json.dumps(record))

    def test_the_body_hashes_under_intakes_derivation(self):
        with open(self.derive(), "rb") as handle:
            body = handle.read()
        self.assertEqual(intake.HASH_DERIVATIONS[extractor.DERIVATION](body), hashlib.sha256(body).hexdigest())

    def assert_refused(self, *expected, out=None):
        target = out or os.path.join(self.work, "demo.txt")
        code, output = self.run_tool("--write", target)
        self.assertEqual(code, 1, output)
        for fragment in expected:
            self.assertIn(fragment, output)
        self.assertFalse(os.path.exists(target), "a refused derivation wrote the text")

    def test_an_output_inside_a_git_work_tree_is_refused(self):
        repo = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(repo, ".git"))
        self.assert_refused("inside the git work tree", out=os.path.join(repo, "sub", "demo.txt"))

    def test_a_worktree_git_file_counts_as_a_work_tree(self):
        repo = os.path.join(self.root, "worktree")
        os.makedirs(repo)
        with open(os.path.join(repo, ".git"), "w", encoding="utf-8") as handle:
            handle.write("gitdir: elsewhere\n")
        self.assert_refused("inside the git work tree", out=os.path.join(repo, "demo.txt"))

    def test_a_different_pdf_is_refused(self):
        document = manifest(self.pdf_bytes)
        document["corpora"][0]["sourcePdf"]["sha256"] = "f" * 64
        self.write_manifest(document)
        self.assert_refused("sourcePdf records")

    def test_another_pdftotext_version_is_refused(self):
        os.environ["FAKE_PDFTOTEXT_VERSION"] = "25.01.0"
        self.assert_refused("pinned to 24.02.0")

    def test_a_wrong_offset_is_refused_at_the_first_page_without_its_folio(self):
        self.write_pdf(PAGES, offset=2)
        self.assert_refused("PDF page 4 does not print the folio 2")

    def test_a_braced_line_a_marker_could_be_confused_with_is_refused(self):
        pages = list(PAGES)
        pages[3] = pages[3].replace("Results\n", "Results\n{7}\n")
        self.write_pdf(pages)
        self.assert_refused("a line wholly in braces")

    def test_a_malformed_page_declaration_is_a_usage_error(self):
        self.write_pdf(PAGES, pages=((3, 3), (2, 2)))
        code, output = self.run_tool("--write", os.path.join(self.work, "demo.txt"))
        self.assertEqual(code, 2, output)
        self.assertIn("ascending", output)


class TestCheck(ExtractCase):
    def pinned(self):
        text = self.derive()
        with open(text, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        self.write_manifest(manifest(self.pdf_bytes, content_hash=digest))
        return text

    def test_the_text_it_wrote_checks_and_re_derives(self):
        code, output = self.run_tool("--check", self.pinned())
        self.assertEqual(code, 0, output)
        self.assertIn("ok   re-derivation", output)

    def test_without_the_pinned_pdftotext_re_derivation_is_not_verified(self):
        text = self.pinned()
        os.environ["FAKE_PDFTOTEXT_VERSION"] = "23.0.0"
        code, output = self.run_tool("--check", text)
        self.assertEqual(code, 0, output)
        self.assertIn("NOT VERIFIED -- re-derivation", output)
        self.assertNotIn("ok   re-derivation", output)

    def test_a_changed_text_fails(self):
        text = self.pinned()
        with open(text, "a", encoding="utf-8") as handle:
            handle.write("an added line\n")
        code, output = self.run_tool("--check", text)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL text", output)

    def test_pages_the_manifest_no_longer_declares_fail_the_header(self):
        text = self.pinned()
        document = manifest(self.pdf_bytes, pages=((2, 3),))
        with open(text, "rb") as handle:
            document["corpora"][0]["contentHash"] = hashlib.sha256(handle.read()).hexdigest()
        self.write_manifest(document)
        code, output = self.run_tool("--check", text)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL header", output)


def located_map(citation="Ties / p. 5", extent=(2, 3)):
    return {
        "schemaVersion": 1, "corpus": "demo-book",
        "extent": {"unit": "page", "from": extent[0], "to": extent[1]},
        "entries": [
            {"id": "roll", "locator": {"sourceId": "demo-book", "citation": "Rolling / p. 2"},
             "evidence": "A roll is made with two dice.", "scope": "in"},
            {"id": "wins", "locator": {"sourceId": "demo-book", "citation": "Results / p. 3"},
             "evidence": "The higher total wins the round.", "scope": "in"},
            {"id": "ties", "locator": {"sourceId": "demo-book", "citation": citation},
             "evidence": "On a tie, both players roll again.", "scope": "in"},
        ],
    }


class TestLocatedInTheDerivedText(ExtractCase):
    """check-locators-pdf-text.py reads the derived text's printed-page markers (0028)."""

    def check(self, document, text=None):
        text = text or self.derive()
        path = os.path.join(self.work, "corpus-map.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = pdf_text_checker.main([path, text])
        return code, out.getvalue()

    def test_printed_page_citations_resolve(self):
        code, output = self.check(located_map())
        self.assertEqual(code, 0, output)
        self.assertIn("[ok] locators: all 3 citations verified", output)
        self.assertIn("[ok] coverage: all 2 pages", output)

    def test_citing_the_pdf_page_fails(self):
        code, output = self.check(located_map(citation="Ties / p. 6"))
        self.assertEqual(code, 1, output)
        self.assertIn("ties: cited p. 6, evidence is on p. 5", output)

    def test_a_heading_on_a_page_before_a_gap_is_searched_from_the_cited_page(self):
        code, output = self.check(located_map(citation="Results / p. 5"))
        self.assertEqual(code, 1, output)
        self.assertIn("between the start of p. 5 and the quote", output)

    def test_a_marker_the_header_does_not_declare_is_a_usage_error(self):
        text = self.derive()
        with open(text, encoding="utf-8") as handle:
            body = handle.read()
        with open(text, "w", encoding="utf-8") as handle:
            handle.write(body.replace("{5}\n", "{4}\n"))
        code, output = self.check(located_map(), text)
        self.assertEqual(code, 2, output)
        self.assertIn("missing [5]; undeclared [4]", output)

    def test_an_extent_claiming_a_page_not_derived_is_a_usage_error(self):
        code, output = self.check(located_map(extent=(2, 4)))
        self.assertEqual(code, 2, output)
        self.assertIn("the extent claims p. 4, which the text does not hold", output)


class TestNamesAgree(unittest.TestCase):
    """The derivation's name and header live in three files that cannot import each other."""

    def test_the_derivation_is_one_name(self):
        self.assertEqual(extractor.DERIVATION, check_map.PRINTED_PAGE_DERIVATION)
        self.assertIn(extractor.DERIVATION, intake.HASH_DERIVATIONS)
        self.assertEqual((extractor.EXTRACTOR, extractor.POPPLER_VERSION), check_map.DERIVED_TEXT_EXTRACTOR)

    def test_the_header_is_one_grammar(self):
        self.assertEqual(extractor.HEADER.pattern, pdf_text_checker.HEADER.pattern)


if __name__ == "__main__":
    unittest.main()
