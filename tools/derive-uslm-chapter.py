#!/usr/bin/env python3
"""Derive a chapter of the United States Code, as the Office of Law Revision Counsel publishes it.

The OLRC serves each title of the Code as a release-point zip holding one USLM XML member,
`usc<NN>.xml`, which for Title 15 is 30 MB. A corpus that held the whole title would be a corpus
no reader could say which bytes a quote was held to, so the derivation named
`olrc-uslm-chapter-slice-verbatim` takes **one chapter** of it and nothing else is rewritten:

  1. the zip must hold exactly one member, named `usc<NN>.xml`, with <NN> the title the chapter
     identifier names (`/us/usc/t15/ch103` is title 15);
  2. the chapter is the one `<chapter ...>` element whose `identifier` attribute is the chapter
     identifier, from its `<chapter` to the first `</chapter>` after it, **byte for byte**. A
     chapter that nests another `<chapter` is refused rather than cut at the wrong close;
  3. the slice is the following bytes, UTF-8, LF line endings, in this order:

        <?xml version="1.0" encoding="UTF-8"?>\\n
        <uscDoc ...>                    the member's root start tag, verbatim, with its namespaces
        \\n
        <meta> ... </meta>              the member's one <meta> element, verbatim
        \\n
        <main>\\n
        <chapter ...> ... </chapter>    the chapter, verbatim
        \\n</main>\\n
        </uscDoc>\\n

The member's own XML declaration and processing instructions are not carried: the declaration
is replaced by the one above (the member's ends in a carriage return, which the corpus format
refuses), and the stylesheet instruction names a CSS file the zip does not hold. Nothing between
`<main>` and the chapter is carried either: the title's own heading, table of contents and the
chapters around this one are not what a corpus of this chapter is held to.

The scan is textual because the output must be the release's own bytes: parsing and
re-serialising would rewrite entity references, attribute order and whitespace, and a quote
checked against a re-serialisation is not checked against what the OLRC published. The slice is
parsed afterwards, only to refuse a result that is not well-formed or holds a carriage return.

Usage:
  derive-uslm-chapter.py --from <usc-release.zip> --chapter </us/usc/t15/ch103> --into <slice.xml>
  derive-uslm-chapter.py --from <usc-release.zip> --chapter </us/usc/t15/ch103> --check <slice.xml>

Exit 0 when the slice was derived (or matched), 1 otherwise, 2 on a usage error.
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

CHAPTER = re.compile(r"^/us/usc/t([0-9]+[A-Za-z]*)/ch([0-9]+[A-Za-z]*)$")
#: Bounds on what is read from a zip a person fetched from the internet. The Code's largest title
#: is some 150 MB of XML; a member far past that is not a release point.
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_RATIO = 200
DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'


class Refused(Exception):
    """A release or a chapter this derivation will not slice."""


def member_of(archive_path, title):
    """The bytes of `usc<title>.xml`, the zip's only member."""
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as error:
        raise Refused(f"cannot read {archive_path} as a zip: {error}")
    with archive:
        members = archive.infolist()
        wanted = f"usc{title}.xml"
        if [m.filename for m in members] != [wanted]:
            raise Refused(f"{archive_path} holds {[m.filename for m in members]}, not exactly "
                          f"the one member {wanted!r}")
        info = members[0]
        if info.file_size > MAX_MEMBER_BYTES or (
                info.compress_size and info.file_size / info.compress_size > MAX_RATIO):
            raise Refused(f"{wanted} declares {info.file_size} bytes from {info.compress_size}; "
                          f"that is outside what a release point weighs")
        data = archive.read(info)
    if len(data) != info.file_size:
        raise Refused(f"{wanted} read {len(data)} bytes, not the {info.file_size} it declares")
    return data


def one(data, opening, closing, what):
    """`data[start:end]` for the single `what` element, `opening` through `closing`."""
    if data.count(opening) != 1:
        raise Refused(f"the member holds {data.count(opening)} {what} elements opened by "
                      f"{opening.decode()!r}, not exactly one")
    start = data.index(opening)
    end = data.find(closing, start)
    if end < 0:
        raise Refused(f"the {what} element is not closed")
    return data[start:end + len(closing)]


def derive(archive_path, chapter):
    """The slice's bytes for `chapter` of the release in `archive_path`."""
    named = CHAPTER.match(chapter)
    if not named:
        raise Refused(f"{chapter!r} is not a chapter identifier like /us/usc/t15/ch103")
    data = member_of(archive_path, named.group(1))
    # The chapter: its start tag is the one carrying this identifier. `identifier="..."` quoted
    # in full, so `/ch10` never matches `/ch103`.
    needle = f'identifier="{chapter}"'.encode()
    found = data.count(needle)
    if found != 1:
        raise Refused(f"the release holds {found} elements identified {chapter}, not exactly one")
    anchor = data.index(needle)
    start = data.rfind(b"<", 0, anchor)
    if not data.startswith(b"<chapter ", start):
        raise Refused(f"{chapter} identifies a {data[start:start + 12]!r} element, not a chapter")
    end = data.find(b"</chapter>", anchor)
    if end < 0:
        raise Refused(f"the chapter {chapter} is not closed")
    element = data[start:end + len(b"</chapter>")]
    if element.count(b"<chapter") != 1:
        raise Refused(f"{chapter} contains another chapter element; its close cannot be told "
                      f"from the inner one's by this scan")
    root = data[data.index(b"<uscDoc "):]
    root = root[:root.index(b">") + 1]
    meta = one(data, b"<meta>", b"</meta>", "meta")
    out = (DECLARATION.encode() + root + b"\n" + meta + b"\n<main>\n" + element
           + b"\n</main>\n</uscDoc>\n")
    if b"\r" in out:
        raise Refused("the slice holds a carriage return; the corpus format reads LF line "
                      "endings only, and this derivation does not rewrite what it carries")
    try:
        ET.fromstring(out)
        out.decode("utf-8")
    except (ET.ParseError, UnicodeDecodeError) as error:
        raise Refused(f"the slice is not well-formed UTF-8 XML: {error}")
    return out


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0], add_help=True)
    parser.add_argument("--from", dest="source", required=True, help="the release-point zip")
    parser.add_argument("--chapter", required=True, help="e.g. /us/usc/t15/ch103")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--into", help="write the slice here")
    mode.add_argument("--check", help="compare the slice with this file")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as error:
        return 2 if error.code else 0
    try:
        derived = derive(args.source, args.chapter)
    except Refused as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 1
    if args.into:
        with open(args.into, "wb") as handle:
            handle.write(derived)
        print(f"derived {len(derived)} bytes into {args.into}")
        return 0
    try:
        with open(args.check, "rb") as handle:
            held = handle.read()
    except OSError as error:
        print(f"cannot read {args.check}: {error}", file=sys.stderr)
        return 2
    if held != derived:
        print(f"MISMATCH: {args.check} is {len(held)} bytes and the derivation is "
              f"{len(derived)}; they differ", file=sys.stderr)
        return 1
    print(f"matches: {args.check} is the derivation, {len(derived)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
