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


def _words(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


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

    What it does not buy: that `renderedReading` is what the page says. Nothing here reads the
    page, and the locator checker does not either; it holds `evidence` to the extraction, tests
    that the declared defect is present where a cheap test exists, and prints every
    `renderedReading` as not verified. A reviewer reading the page is what stands behind it.
    """
    doc, bad = ctx["map"], []
    corpora = corpora_of(ctx.get("manifest"))
    declared = 0
    for source_id, corpus in corpora.items():
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

    if not carriers and not declared:
        return skip("no corpus declares `quotedText` and no entry carries `extraction`, so there "
                    "was nothing to check", had_subject=False)
    if carriers and not corpora and not bad:
        return skip("entries carry `extraction` and there is no manifest, so whether their corpus "
                    "declares `quotedText` was not checked. Pass --manifest.")
    readings = f"; {len(carriers)} renderedReading{'' if len(carriers) == 1 else 's'} not verified here" \
        if carriers else ""
    return verdict(bad, f"{declared} corpus declaration{'' if declared == 1 else 's'} of quoted text, "
                        f"{len(carriers)} extraction defect{'' if len(carriers) == 1 else 's'} well "
                        f"formed{readings}",
                   "an extraction declaration or defect is malformed or contradicted")
