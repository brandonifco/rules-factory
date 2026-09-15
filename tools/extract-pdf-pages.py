#!/usr/bin/env python3
"""Derive a page-marked text of the printed pages a manifest declares, from a PDF whose printed
page numbers are not its PDF page numbers (derivation `pdftotext-24.02.0-printed-page-marked`,
decision 0028, #139).

The SRD's `examples/srd-52-combat/extract.py` derives its whole PDF and refuses a page whose folio
is not its own index. A book whose front matter is unnumbered prints page N-1 (or N-k) on PDF
page N, and a licensed book (0022) should exist as text on the operator's machine only as far as
the map needs it. This tool is the general form of that derivation, for any corpus whose manifest
declares it:

```json
"hashDerivation": "pdftotext-24.02.0-printed-page-marked",
"quotedText": { "derivation": "pdftotext-24.02.0-printed-page-marked", "extractedFrom": "the PDF" },
"sourcePdf": { "sha256": "…64 hex…", "bytes": 123, "envVar": "CORE_RULES_PDF" },
"derivedText": { "extractor": "pdftotext", "extractorVersion": "24.02.0", "pdfPageOffset": 1,
                 "printedPages": [ { "from": 35, "to": 36 }, { "from": 44, "to": 44 } ] }
```

`pdfPageOffset` is k in "PDF page = printed page + k". `contentHash` is SHA-256 over the text this
tool writes, and `sourcePdf.sha256` over the PDF it read, so quotes stay held to the bytes the
baseline covers (0024) while the PDF's own identity is recorded too.

The derivation, in full, and nothing else is done to the text:

  1. The first line is `{pdftotext-24.02.0-printed-page-marked pages=35-36,44 offset=+1}`: the
     derivation, the printed pages in order as ranges, and the offset. The locator checker reads
     it and requires the page markers to be exactly those pages, so a text missing a page, or
     holding one the manifest did not declare, is refused rather than read.
  2. For each printed page P, in ascending order: the line `{P}`, then the output of
     `pdftotext -enc UTF-8 -f Q -l Q <pdf> -` for PDF page Q = P + offset, from poppler-utils
     **24.02.0**, default (non-layout) mode, with its one trailing form feed removed.
  3. Everything is joined with nothing between, and written as UTF-8.

It refuses to write, and writes nothing, when:

  * the PDF's size or SHA-256 is not `sourcePdf`'s -- a different printing would be quoted as this one;
  * pdftotext is not 24.02.0 -- another version breaks lines differently, and the hash would differ;
  * a page's text has no line that is exactly its printed page number -- that folio is what shows
    the offset is right, page by page;
  * a page's text has a line that is wholly `{…}`, which a marker could be confused with, or a
    second form feed;
  * the output path is inside a git work tree -- licensed text is never where a commit can reach it.

Beside the text it writes `<out>.derivation.json`: the derivation, extractor, version, the argv
template, the PDF's digest, the pages, and the text's `bodySha256`. It holds no corpus text.

What it does not buy: that pdftotext read the page the way it is printed. pdftotext linearises
columns and sidebars and flattens tables, exactly as for the SRD; 0024's `extraction` declarations
are how a map says so.

Usage:
  extract-pdf-pages.py --manifest M [--source-id ID] [--pdf PDF] --write OUT
  extract-pdf-pages.py --manifest M [--source-id ID] [--pdf PDF] --check TEXT
The PDF defaults to the file `sourcePdf.envVar` names. `--check` holds TEXT to `contentHash` and
its header to `derivedText` (standard library only), and re-derives and compares where the PDF and
pdftotext 24.02.0 are both here; where they are not it says NOT VERIFIED, never ok.
Exit 0 when every check that could run passed; 1 on a refusal or mismatch; 2 on a usage error.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

DERIVATION = "pdftotext-24.02.0-printed-page-marked"
EXTRACTOR = "pdftotext"
POPPLER_VERSION = "24.02.0"
ARGV_TEMPLATE = [EXTRACTOR, "-enc", "UTF-8", "-f", "{pdfPage}", "-l", "{pdfPage}", "{sourcePdf}", "-"]
HEADER = re.compile(r"\A\{(?P<derivation>[^\s{}]+) pages=(?P<pages>\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*) "
                    r"offset=(?P<offset>[+-]\d+)\}\n")
BRACED_LINE = re.compile(r"^[ \t]*\{.*\}[ \t]*$", re.M)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Refused(Exception):
    """The derivation or the check did not pass."""


class Usage(Exception):
    """The inputs are not usable."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def corpus_entry(manifest_path, source_id):
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as error:
        raise Usage(f"cannot read {manifest_path}: {error}")
    corpora = [c for c in manifest.get("corpora") or [] if isinstance(c, dict)]
    if source_id is not None:
        corpora = [c for c in corpora if c.get("sourceId") == source_id]
    if len(corpora) != 1:
        raise Usage(f"{manifest_path}: expected exactly one corpus"
                    + (f" with sourceId {source_id!r}" if source_id else "; pass --source-id"))
    return corpora[0]


def declaration(corpus):
    """(printed pages, offset, sourcePdf) from the manifest, refusing anything not well formed.

    The same shape `check-map.py --only extraction` checks; repeated here so a malformed manifest
    never reaches pdftotext.
    """
    name = corpus.get("sourceId")
    if corpus.get("hashDerivation") != DERIVATION:
        raise Usage(f"{name}: hashDerivation is {corpus.get('hashDerivation')!r}, not {DERIVATION!r}")
    derived, source = corpus.get("derivedText"), corpus.get("sourcePdf")
    if not isinstance(derived, dict) or not isinstance(source, dict):
        raise Usage(f"{name}: declares no `derivedText` and `sourcePdf` objects")
    if derived.get("extractor") != EXTRACTOR or derived.get("extractorVersion") != POPPLER_VERSION:
        raise Usage(f"{name}: derivedText names {derived.get('extractor')!r} "
                    f"{derived.get('extractorVersion')!r}; {DERIVATION} is {EXTRACTOR} {POPPLER_VERSION}")
    offset = derived.get("pdfPageOffset")
    if not is_int(offset):
        raise Usage(f"{name}: derivedText.pdfPageOffset is {offset!r}, not an integer")
    pages, previous = [], 0
    for span in derived.get("printedPages") or []:
        first, last = (span.get("from"), span.get("to")) if isinstance(span, dict) else (None, None)
        if not (is_int(first) and is_int(last)) or first < 1 or last < first or first + offset < 1 \
                or first <= previous:
            raise Usage(f"{name}: derivedText.printedPages holds {span!r}; each is {{from, to}}, "
                        f"ascending, not overlapping, on a PDF page that exists")
        pages.extend(range(first, last + 1))
        previous = last
    if not pages:
        raise Usage(f"{name}: derivedText.printedPages declares no pages")
    if not isinstance(source.get("sha256"), str) or not SHA256.match(source["sha256"]):
        raise Usage(f"{name}: sourcePdf.sha256 is {source.get('sha256')!r}, not 64 lower-case hex")
    return pages, offset, source


def page_list(pages):
    """`35-36,44` for [35, 36, 44]."""
    spans, start = [], None
    for position, page in enumerate(pages):
        if start is None:
            start = page
        if position + 1 == len(pages) or pages[position + 1] != page + 1:
            spans.append(str(start) if start == page else f"{start}-{page}")
            start = None
    return ",".join(spans)


def header(pages, offset):
    return "{%s pages=%s offset=%+d}\n" % (DERIVATION, page_list(pages), offset)


def pdftotext_version():
    tool = shutil.which(EXTRACTOR)
    if tool is None:
        return None
    completed = subprocess.run([tool, "-v"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    found = re.search(r"pdftotext version (\S+)", completed.stdout)
    return found.group(1) if found else None


def inside_work_tree(path):
    """The git work tree containing `path`, or None. Walks up for `.git`, a directory or a file."""
    here = os.path.realpath(path)
    while True:
        if os.path.exists(os.path.join(here, ".git")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def pdf_path(args, source):
    if args.pdf:
        return args.pdf
    variable = source.get("envVar")
    value = os.environ.get(variable) if isinstance(variable, str) and variable else None
    return value


def verify_pdf(path, source):
    with open(path, "rb") as handle:
        data = handle.read()
    if sha256(data) != source["sha256"] or ("bytes" in source and len(data) != source["bytes"]):
        raise Refused(f"the PDF is {len(data)} bytes, sha256 {sha256(data)}; sourcePdf records "
                      f"{source.get('bytes')} bytes, {source['sha256']}")


def derive(path, pages, offset):
    """The text's bytes, by the derivation the docstring states."""
    out = [header(pages, offset)]
    for page in pages:
        argv = [EXTRACTOR, "-enc", "UTF-8", "-f", str(page + offset), "-l", str(page + offset), path, "-"]
        completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if completed.returncode != 0:
            raise Refused(f"pdftotext exited {completed.returncode} on PDF page {page + offset}: "
                          f"{completed.stderr.decode('utf-8', 'replace').strip()}")
        text = completed.stdout.decode("utf-8")
        if text.endswith("\f"):
            text = text[:-1]
        if "\f" in text:
            raise Refused(f"PDF page {page + offset} gave more than one page of text")
        folios = {line.strip() for line in text.split("\n") if re.fullmatch(r"\s*\d+\s*", line)}
        if str(page) not in folios:
            raise Refused(f"PDF page {page + offset} does not print the folio {page} as a line, so "
                          f"offset {offset:+d} is not shown to hold there")
        if BRACED_LINE.search(text):
            raise Refused(f"PDF page {page + offset} has a line wholly in braces, which a page "
                          f"marker could be confused with")
        out.append("{%d}\n%s" % (page, text))
    return "".join(out).encode("utf-8")


def record(corpus, pages, offset, data):
    source = corpus["sourcePdf"]
    return {
        "derivation": DERIVATION,
        "sourceId": corpus.get("sourceId"),
        "extractor": EXTRACTOR,
        "extractorVersion": POPPLER_VERSION,
        "argv": ARGV_TEMPLATE,
        "sourcePdf": {k: source[k] for k in ("sha256", "bytes") if k in source},
        "pdfPageOffset": offset,
        "printedPages": corpus["derivedText"]["printedPages"],
        "pdfPages": [page + offset for page in pages],
        "bytes": len(data),
        "bodySha256": sha256(data),
    }


def write(args, corpus, pages, offset):
    out = os.path.abspath(args.write)
    tree = inside_work_tree(os.path.dirname(out))
    if tree is not None:
        raise Refused(f"{out} is inside the git work tree {tree}; a licensed text is written only "
                      f"where no commit can reach it")
    path = pdf_path(args, corpus["sourcePdf"])
    if not path or not os.path.isfile(path):
        raise Usage(f"no PDF: pass --pdf, or set ${corpus['sourcePdf'].get('envVar')} to the file")
    verify_pdf(path, corpus["sourcePdf"])
    version = pdftotext_version()
    if version != POPPLER_VERSION:
        raise Refused(f"pdftotext is {version!r}, and {DERIVATION} is pinned to {POPPLER_VERSION}")
    data = derive(path, pages, offset)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as handle:
        handle.write(data)
    provenance = record(corpus, pages, offset, data)
    with open(out + ".derivation.json", "w", encoding="utf-8") as handle:
        json.dump(provenance, handle, indent=2)
        handle.write("\n")
    print(f"wrote {out}: {len(pages)} printed pages ({page_list(pages)}, PDF page = printed page "
          f"{offset:+d}), {len(data)} bytes, bodySha256 {provenance['bodySha256']}")
    if provenance["bodySha256"] != corpus.get("contentHash"):
        print(f"note: the manifest's contentHash is {corpus.get('contentHash')!r}; set it to "
              f"{provenance['bodySha256']} once the text is the one the map is made of")
    return 0


def check(args, corpus, pages, offset):
    try:
        with open(args.check, "rb") as handle:
            data = handle.read()
    except OSError as error:
        raise Usage(f"cannot read {args.check}: {error}")
    failed = False
    if sha256(data) != corpus.get("contentHash"):
        print(f"FAIL text: sha256 {sha256(data)}; the manifest's contentHash is {corpus.get('contentHash')}")
        failed = True
    else:
        print(f"ok   text: sha256 {sha256(data)} = contentHash")
    expected = header(pages, offset).encode("utf-8")
    if not data.startswith(expected):
        print(f"FAIL header: the text does not begin {expected.decode().strip()!r}, the pages and offset "
              f"the manifest's derivedText declares")
        failed = True
    else:
        print(f"ok   header: {expected.decode().strip()}")

    path, version = pdf_path(args, corpus["sourcePdf"]), pdftotext_version()
    if not path or not os.path.isfile(path):
        print("NOT VERIFIED -- re-derivation: the PDF is not here (pass --pdf or set "
              f"${corpus['sourcePdf'].get('envVar')}), so the text was not re-derived from it")
    elif version != POPPLER_VERSION:
        print(f"NOT VERIFIED -- re-derivation: pdftotext is {version!r} here and the derivation is pinned "
              f"to {POPPLER_VERSION}, so the text was not re-derived from the PDF")
    else:
        verify_pdf(path, corpus["sourcePdf"])
        print("ok   pdf: size and sha256 = sourcePdf")
        if derive(path, pages, offset) != data:
            print(f"FAIL re-derivation: pdftotext {version} over the PDF does not give this text")
            failed = True
        else:
            print(f"ok   re-derivation: pdftotext {version} over the PDF gives this text byte for byte")
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Derive a printed-page-marked text from a PDF (0028).")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-id")
    parser.add_argument("--pdf", help="the PDF; defaults to the file sourcePdf.envVar names")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", metavar="OUT")
    action.add_argument("--check", metavar="TEXT")
    args = parser.parse_args(argv)
    try:
        corpus = corpus_entry(args.manifest, args.source_id)
        pages, offset, _ = declaration(corpus)
        return write(args, corpus, pages, offset) if args.write else check(args, corpus, pages, offset)
    except Usage as error:
        print(f"extract-pdf-pages: {error}", file=sys.stderr)
        return 2
    except (Refused, OSError, UnicodeDecodeError) as error:
        print(f"extract-pdf-pages: REFUSED -- {error}. Nothing was written.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
