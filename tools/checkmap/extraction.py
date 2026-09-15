"""What a quote is verbatim of, when the corpus text is an extraction (0024): the manifest's
`quotedText` declaration, and an entry's `extraction` defect with its rendered reading.
"""
import re

from .diagnostics import skip, verdict
from .model import block, corpora_of, entries_of, label, quotes_withheld


# The ways an extraction was seen to garble a quote, and no others: each is a case trial 7 met in
# the SRD 5.2.1 map (examples/srd-52-combat/README.md, finding 1). A hyphen joined at a line end and
# a space after a line-end em dash were seen too, and neither changes what a quoted rule says, so
# neither is here (0024). Closed, because the corpus-reading checker has a test per value.
EXTRACTION_DEFECTS = ("interleaved-table", "interrupted-by-page-furniture", "split-by-sidebar")
QUOTED_TEXT_FIELDS = ("derivation", "extractedFrom")
EXTRACTION_FIELDS = ("defect", "renderedReading")
# A text derived from a PDF for the printed pages the manifest declares, marked in printed page
# numbers (0028). `tools/extract-pdf-pages.py` writes it, and `test_extract_pdf_pages.py` holds
# these names to that tool's and to intake's HASH_DERIVATIONS.
PRINTED_PAGE_DERIVATION = "pdftotext-24.02.0-printed-page-marked"
DERIVED_TEXT_FIELDS = ("extractor", "extractorVersion", "pdfPageOffset", "printedPages")
DERIVED_TEXT_EXTRACTOR = ("pdftotext", "24.02.0")
SOURCE_PDF_FIELDS = ("sha256", "bytes", "committedPath", "envVar", "retrieved")


def _words(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _derived_text(name, corpus, bad):
    """A printed-page derivation is declared whole, or not at all (0028). Returns 1 when declared."""
    derived, derivation = corpus.get("derivedText"), corpus.get("hashDerivation")
    if "derivedText" not in corpus:
        if derivation == PRINTED_PAGE_DERIVATION:
            bad.append(f"  X  {name}: hashDerivation is {PRINTED_PAGE_DERIVATION}, and the corpus declares "
                       f"no `derivedText`, so which pages were derived, and at what offset, is unstated")
        return 0
    if derivation != PRINTED_PAGE_DERIVATION:
        bad.append(f"  X  {name}: declares `derivedText`, and its hashDerivation is {derivation!r}, not "
                   f"{PRINTED_PAGE_DERIVATION!r}, the derivation that field describes")
    if "quotedText" not in corpus:
        bad.append(f"  X  {name}: declares `derivedText` and no `quotedText`; a derived text's quotes "
                   f"are of the derivation, and the manifest says so")
    if not isinstance(derived, dict):
        bad.append(f"  X  {name}: derivedText is not an object {{{', '.join(DERIVED_TEXT_FIELDS)}}}")
        return 1
    for field in sorted(set(derived) - set(DERIVED_TEXT_FIELDS)):
        bad.append(f"  X  {name}: `{field}` is not a field of derivedText ({', '.join(DERIVED_TEXT_FIELDS)})")
    if (derived.get("extractor"), derived.get("extractorVersion")) != DERIVED_TEXT_EXTRACTOR:
        bad.append(f"  X  {name}: derivedText names {derived.get('extractor')!r} "
                   f"{derived.get('extractorVersion')!r}; {PRINTED_PAGE_DERIVATION} is pinned to "
                   f"{' '.join(DERIVED_TEXT_EXTRACTOR)}")
    offset = derived.get("pdfPageOffset")
    if not _is_int(offset):
        bad.append(f"  X  {name}: derivedText.pdfPageOffset is {offset!r}; it is the integer k in "
                   f"\"PDF page = printed page + k\"")
        offset = 0
    spans, previous = derived.get("printedPages"), 0
    if not isinstance(spans, list) or not spans:
        bad.append(f"  X  {name}: derivedText.printedPages is not a non-empty list of {{from, to}}")
        spans = []
    for span in spans:
        if not isinstance(span, dict) or set(span) != {"from", "to"} \
                or not (_is_int(span["from"]) and _is_int(span["to"])):
            bad.append(f"  X  {name}: derivedText.printedPages holds {span!r}, which is not {{from, to}} "
                       f"with integer bounds")
            continue
        if span["from"] < 1 or span["to"] < span["from"] or span["from"] + offset < 1:
            bad.append(f"  X  {name}: derivedText.printedPages holds {span!r}, which is not a page range "
                       f"on pages the PDF has")
        elif span["from"] <= previous:
            bad.append(f"  X  {name}: derivedText.printedPages holds {span!r}, which overlaps or follows "
                       f"out of order the range before it; list them ascending and disjoint")
        previous = max(previous, span["to"])
    source = corpus.get("sourcePdf")
    if not isinstance(source, dict):
        bad.append(f"  X  {name}: declares `derivedText` and no `sourcePdf` object; the PDF the text "
                   f"was derived from is identified by its own digest")
        return 1
    for field in sorted(set(source) - set(SOURCE_PDF_FIELDS)):
        bad.append(f"  X  {name}: `{field}` is not a field of sourcePdf ({', '.join(SOURCE_PDF_FIELDS)})")
    digest = source.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        bad.append(f"  X  {name}: sourcePdf.sha256 is {digest!r}, not 64 lower-case hex")
    elif digest == corpus.get("contentHash"):
        bad.append(f"  X  {name}: sourcePdf.sha256 is the contentHash; contentHash covers the derived "
                   f"text, and the PDF's digest is a different fact")
    if "bytes" in source and not (_is_int(source["bytes"]) and source["bytes"] > 0):
        bad.append(f"  X  {name}: sourcePdf.bytes is {source['bytes']!r}, not a positive integer")
    return 1


def check_extraction(ctx):
    """Quotes are held to an extraction only where the manifest says so, and a garbled one says so.

    A corpus whose committed text is derived from what was published (a PDF read by pdftotext)
    may declare `quotedText: {derivation, extractedFrom}` in the manifest: its quotes are verbatim
    of the derived text, not of the page. `derivation` must be the corpus's own `hashDerivation`,
    because the text the quotes are held to is the text `contentHash` covers; any other name would
    hold them to bytes nobody hashed. `extractedFrom` names what was extracted. It is not required
    to be a file here: a map package carries the manifest and the text and not the published file,
    and holding the text to that file is the derivation's own check (the SRD's `extract.py --check`).

    An entry whose quote the extraction garbles carries `extraction: {defect, renderedReading}`.
    `defect` is one of EXTRACTION_DEFECTS. `renderedReading` is the passage as read from the
    rendered page, and it must differ from `evidence` (with whitespace runs equal), or there is
    no gap to declare. The entry's corpus must declare `quotedText`, since a defect of an
    extraction means nothing for a corpus whose quotes are of the text as published. Not beside
    `beyondAdapter`: a rule the adapter cannot read is not one it reads wrongly. Not under
    `quotation: withheld`, because a rendered reading is a quote of the page.

    A text derived for the printed pages the manifest declares (0028) names its derivation whole:
    `hashDerivation` is PRINTED_PAGE_DERIVATION if and only if `derivedText` is present;
    `derivedText` pins the extractor and version, gives the integer `pdfPageOffset` and ascending,
    disjoint `printedPages`; `quotedText` is declared; and `sourcePdf.sha256` is the PDF's own
    digest, which is never the `contentHash`, since that covers the text.

    What it does not buy: that `renderedReading` is what the page says, or that the text is the
    derivation of the PDF (`tools/extract-pdf-pages.py --check` re-derives it where it can). Nothing here reads the
    page, and the locator checker does not either; it holds `evidence` to the extraction, tests
    that the declared defect is present where a cheap test exists, and prints every
    `renderedReading` as not verified. A reviewer reading the page is what stands behind it.
    """
    doc, bad = ctx["map"], []
    corpora = corpora_of(ctx.get("manifest"))
    declared = derivations = 0
    for source_id, corpus in corpora.items():
        derivations += _derived_text(f"manifest {source_id}", corpus, bad)
        if "quotedText" not in corpus:
            continue
        declared += 1
        name = f"manifest {source_id}"
        quoted = corpus.get("quotedText")
        if not isinstance(quoted, dict):
            bad.append(f"  X  {name}: quotedText is not an object {{derivation, extractedFrom}}")
            continue
        for field in sorted(set(quoted) - set(QUOTED_TEXT_FIELDS)):
            bad.append(f"  X  {name}: `{field}` is not a field of quotedText (derivation, extractedFrom)")
        if quoted.get("derivation") != corpus.get("hashDerivation"):
            bad.append(f"  X  {name}: quotedText.derivation is {quoted.get('derivation')!r}, not the "
                       f"corpus's hashDerivation {corpus.get('hashDerivation')!r}; quotes are held to "
                       f"the text contentHash covers, and to no other")
        source = quoted.get("extractedFrom")
        if not isinstance(source, str) or not source.strip():
            bad.append(f"  X  {name}: quotedText names no `extractedFrom`, what the text was extracted from")

    carriers = []
    for position, entry in enumerate(entries_of(doc)):
        if not isinstance(entry, dict) or "extraction" not in entry:
            continue
        name = label(entry, position)
        carriers.append(name)
        extraction = entry.get("extraction")
        if not isinstance(extraction, dict):
            bad.append(f"  X  {name}: extraction is not an object {{defect, renderedReading}}")
            continue
        for field in sorted(set(extraction) - set(EXTRACTION_FIELDS)):
            bad.append(f"  X  {name}: `{field}` is not a field of extraction (defect, renderedReading)")
        if extraction.get("defect") not in EXTRACTION_DEFECTS:
            bad.append(f"  X  {name}: extraction.defect is {extraction.get('defect')!r}, outside "
                       f"{{{', '.join(EXTRACTION_DEFECTS)}}}")
        reading = extraction.get("renderedReading")
        if not isinstance(reading, str) or not reading.strip():
            bad.append(f"  X  {name}: extraction names no `renderedReading`, the passage as read "
                       f"from the rendered page")
        elif _words(reading) == _words(entry.get("evidence")):
            bad.append(f"  X  {name}: renderedReading is the evidence itself; an extraction that "
                       f"reads as the page does has no defect to declare")
        if "beyondAdapter" in entry:
            bad.append(f"  X  {name}: carries both extraction and beyondAdapter; the adapter either "
                       f"cannot read the rule or reads it garbled, not both")
        source_id = block(entry, "locator").get("sourceId")
        source = corpora.get(source_id)
        if quotes_withheld(ctx, entry):
            bad.append(f"  X  {name}: carries extraction under `quotation: withheld`; a rendered "
                       f"reading is a quote of the page")
        elif source is not None and "quotedText" not in source:
            bad.append(f"  X  {name}: declares an extraction defect, but {source_id} declares no "
                       f"`quotedText`, so its quotes are not of an extraction")

    if not carriers and not declared and not derivations:
        return skip("no corpus declares `quotedText` and no entry carries `extraction`, so there "
                    "was nothing to check", had_subject=False)
    if carriers and not corpora and not bad:
        return skip("entries carry `extraction` and there is no manifest, so whether their corpus "
                    "declares `quotedText` was not checked. Pass --manifest.")
    readings = f"; {len(carriers)} renderedReading{'' if len(carriers) == 1 else 's'} not verified here" \
        if carriers else ""
    derived = (f"{derivations} printed-page derivation{'' if derivations == 1 else 's'} well formed, "
               if derivations else "")
    return verdict(bad, derived + f"{declared} corpus declaration{'' if declared == 1 else 's'} of quoted text, "
                        f"{len(carriers)} extraction defect{'' if len(carriers) == 1 else 's'} well "
                        f"formed{readings}",
                   "an extraction declaration or defect is malformed or contradicted")
