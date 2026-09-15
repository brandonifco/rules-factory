#!/usr/bin/env python3
"""Derive the committed text corpus from the committed SRD 5.2.1 PDF, and check the two agree.

The map quotes and cites `srd-5.2.1.txt`. That file is not what Wizards of the Coast publishes:
WotC publishes `SRD_CC_v5.2.1.pdf`, and the text is derived from it by this script. So there are
two digests and two facts, and the manifest records both (method.md, Phase 1, "What exactly?"):

  * `sourcePdf.sha256` -- SHA-256 over the PDF's bytes as retrieved from `retrievedFrom`;
  * `contentHash` -- SHA-256 over the bytes of `srd-5.2.1.txt`, under the derivation named
    `srd-5.2.1-pdftotext-24.02.0-page-marked`, which is exactly what this script writes.

The derivation, in full, and nothing else is done to the text:

  1. `pdftotext -enc UTF-8 SRD_CC_v5.2.1.pdf -` from poppler-utils **24.02.0**, default
     (non-layout, reading-order) mode, no other options. poppler separates pages with a form
     feed; the text after the last one is empty and is dropped.
  2. Before the text of the page at physical index N (1-based), the line `{N}` is written. That
     is the page-marker form `tools/check-locators.py` already reads, and no `{` or `}` occurs
     anywhere in the extracted SRD, so a marker cannot be confused with the corpus's own words.
  3. The pages are joined with nothing between them, and the result is written as UTF-8.

**Physical page N is printed page N, for every page of this PDF**, and step 2 refuses to write
otherwise: each page's extracted text must contain a line that is exactly its own index (the
printed folio). So a citation's `p. 15` is at once the printed page a reader turns to and the
PDF's fifteenth page.

What pdftotext does to the text, recorded rather than corrected (README, findings): it joins a
word hyphenated across a line break, it linearises two columns and the sidebars between them in
its own reading order, it flattens tables into one cell per line, and it keeps the running
header and the folio as lines of text. The map quotes the text as extracted. Correcting any of
that would be a normalisation this script does not do, and a derivation that normalised would be
a different derivation with a different name.

Usage:
  extract.py --write     re-derive srd-5.2.1.txt from the PDF (needs pdftotext 24.02.0)
  extract.py --check     verify both digests against the manifest (standard library only), and
                         re-derive and compare byte for byte where pdftotext 24.02.0 is present;
                         where it is not, say so as NOT VERIFIED rather than ok
Exit 0 when every check that could run passed; 1 on a mismatch; 2 on a usage error.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "corpus-manifest.json")
POPPLER_VERSION = "24.02.0"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def corpus_entry():
    with open(MANIFEST, encoding="utf-8") as handle:
        manifest = json.load(handle)
    corpora = manifest.get("corpora") or []
    if len(corpora) != 1:
        raise SystemExit(f"{MANIFEST}: expected exactly one corpus")
    return corpora[0]


def pdftotext_version():
    tool = shutil.which("pdftotext")
    if tool is None:
        return None
    completed = subprocess.run([tool, "-v"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    found = re.search(r"pdftotext version (\S+)", completed.stdout)
    return found.group(1) if found else None


def derive(pdf_path):
    """The committed text's bytes, from the PDF, by the derivation the docstring states."""
    completed = subprocess.run(["pdftotext", "-enc", "UTF-8", pdf_path, "-"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    text = completed.stdout.decode("utf-8")
    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages = pages[:-1]
    out = []
    for number, page in enumerate(pages, 1):
        folios = {line.strip() for line in page.split("\n") if re.fullmatch(r"\s*\d+\s*", line)}
        if str(number) not in folios:
            raise SystemExit(f"physical page {number} does not print the folio {number}; the page "
                             f"grammar assumes printed page = physical page, and here it does not hold")
        out.append("{%d}\n%s" % (number, page))
    return "".join(out).encode("utf-8")


def main(argv):
    if len(argv) != 1 or argv[0] not in ("--write", "--check"):
        print(__doc__.split("Usage:")[1], file=sys.stderr)
        return 2
    corpus = corpus_entry()
    source = corpus.get("sourcePdf") or {}
    pdf_path = os.path.join(HERE, source.get("committedPath", ""))
    text_path = os.path.join(HERE, corpus.get("committedPath", ""))
    with open(pdf_path, "rb") as handle:
        pdf = handle.read()
    failed = False

    if sha256(pdf) != source.get("sha256") or len(pdf) != source.get("bytes"):
        print(f"FAIL pdf: {os.path.basename(pdf_path)} is {len(pdf)} bytes, sha256 {sha256(pdf)}; "
              f"the manifest records {source.get('bytes')} bytes, {source.get('sha256')}")
        return 1
    print(f"ok   pdf: {os.path.basename(pdf_path)}, {len(pdf)} bytes, sha256 {sha256(pdf)}")

    version = pdftotext_version()
    if argv[0] == "--write":
        if version != POPPLER_VERSION:
            print(f"refusing to write: pdftotext is {version!r}, the derivation is pinned to {POPPLER_VERSION}",
                  file=sys.stderr)
            return 1
        data = derive(pdf_path)
        with open(text_path, "wb") as handle:
            handle.write(data)
        print(f"wrote {os.path.basename(text_path)}, {len(data)} bytes, sha256 {sha256(data)}")
        return 0

    with open(text_path, "rb") as handle:
        committed = handle.read()
    if sha256(committed) != corpus.get("contentHash"):
        print(f"FAIL text: {os.path.basename(text_path)} has sha256 {sha256(committed)}; the manifest's "
              f"contentHash is {corpus.get('contentHash')}")
        failed = True
    else:
        print(f"ok   text: {os.path.basename(text_path)}, sha256 {sha256(committed)} = contentHash")

    if version != POPPLER_VERSION:
        print(f"NOT VERIFIED -- re-derivation: pdftotext is {version!r} here and the derivation is pinned "
              f"to {POPPLER_VERSION}, so the text was not re-derived from the PDF on this machine. Both "
              f"digests above were checked; that the one follows from the other was not.")
    elif derive(pdf_path) != committed:
        print(f"FAIL re-derivation: pdftotext {version} over the PDF does not give the committed text")
        failed = True
    else:
        print(f"ok   re-derivation: pdftotext {version} over the PDF gives the committed text byte for byte")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
