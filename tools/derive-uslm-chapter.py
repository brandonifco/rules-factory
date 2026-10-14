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

The member is parsed to *locate* the elements and its own byte offsets are what is cut, so
the output is the release's own bytes: re-serialising would rewrite entity references, attribute
order and whitespace, and a quote checked against a re-serialisation is not checked against what
the OLRC published. Locating by parsing, and not by searching the text, is what makes a chapter
inside a comment or a CDATA section, a `data-identifier` attribute and an identifier in single
quotes mean what they are. The member must be UTF-8 (a declaration of any other encoding, a
byte-order mark or invalid bytes are refused, because the slice's declaration says UTF-8 and
would otherwise re-label the bytes) and carry no DOCTYPE. The slice is parsed afterwards, only to
refuse a result that holds a carriage return.

Usage:
  derive-uslm-chapter.py --from <usc-release.zip> --chapter </us/usc/t15/ch103> --into <slice.xml>
  derive-uslm-chapter.py --from <usc-release.zip> --chapter </us/usc/t15/ch103> --check <slice.xml>

Exit 0 when the slice was derived (or matched), 1 otherwise, 2 on a usage error.
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
import xml.parsers.expat
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


def elements_of(data, chapter):
    """(root start tag, meta element, chapter element) as byte strings, located by parsing.

    The scan is by a parser's own byte offsets, not by searching the text for a string: a
    comment or CDATA section that holds `<chapter identifier="...">`, an attribute named
    `data-identifier`, or an identifier in single quotes are all text a search finds and a parser
    does not call a chapter (#655 review). Exactly one `chapter` element must carry the
    identifier, and the member's one `meta` must be a child of its root.
    """
    if data.startswith(b"\xef\xbb\xbf"):
        raise Refused("the member starts with a byte-order mark; the slice declares UTF-8 without one")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Refused(f"the member is not valid UTF-8: {error}")
    parser = xml.parsers.expat.ParserCreate()
    parser.buffer_text = False
    state = {"stack": [], "root": None, "meta": [], "chapters": [], "open": None}

    def declared(version, encoding, standalone):
        if encoding is not None and encoding.upper() != "UTF-8":
            raise Refused(f"the member declares encoding {encoding!r}; this derivation replaces "
                          f"the declaration with UTF-8's and will not re-label other bytes")

    def doctype(*_):
        raise Refused("the member has a DOCTYPE; it is refused so no entity is ever expanded")

    def start(name, attributes):
        at = parser.CurrentByteIndex
        stack = state["stack"]
        if not stack:
            if name != "uscDoc":
                raise Refused(f"the member's root is <{name}>, not <uscDoc>")
            quote, end = None, at
            while True:
                byte = data[end:end + 1]
                if quote:
                    quote = None if byte == quote else quote
                elif byte in (b'"', b"'"):
                    quote = byte
                elif byte == b">":
                    break
                end += 1
            state["root"] = data[at:end + 1]
        if name == "meta" and len(stack) == 1:
            state["meta"].append([at, None])
        if name == "chapter":
            if state["open"] is not None:
                raise Refused("a chapter element contains another chapter element; its close "
                              "cannot be told from the inner one's")
            if attributes.get("identifier") == chapter:
                state["open"] = [at, None]
                state["chapters"].append(state["open"])
        stack.append(name)

    def end(name):
        at = parser.CurrentByteIndex
        stack = state["stack"]
        stack.pop()
        if data[at:at + 2] != b"</":
            if name == "chapter" and state["open"] is not None:
                raise Refused(f"the chapter {chapter} is an empty element")
            if name == "meta" and len(stack) == 1:
                raise Refused("the member's meta is an empty element")
            return
        close = data.index(b">", at) + 1
        if name == "meta" and len(stack) == 1:
            state["meta"][-1][1] = close
        if name == "chapter" and state["open"] is not None:
            state["open"][1] = close
            state["open"] = None

    parser.XmlDeclHandler = declared
    parser.StartDoctypeDeclHandler = doctype
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    try:
        parser.Parse(data, True)
    except xml.parsers.expat.ExpatError as error:
        raise Refused(f"the member is not well-formed XML: {error}")
    if len(state["chapters"]) != 1:
        raise Refused(f"the release holds {len(state['chapters'])} chapter elements identified "
                      f"{chapter}, not exactly one")
    if len(state["meta"]) != 1:
        raise Refused(f"the member holds {len(state['meta'])} meta elements under its root, "
                      f"not exactly one")
    (c0, c1), (m0, m1) = state["chapters"][0], state["meta"][0]
    return state["root"], data[m0:m1], data[c0:c1]


def derive(archive_path, chapter):
    """The slice's bytes for `chapter` of the release in `archive_path`."""
    named = CHAPTER.match(chapter)
    if not named:
        raise Refused(f"{chapter!r} is not a chapter identifier like /us/usc/t15/ch103")
    data = member_of(archive_path, named.group(1))
    root, meta, element = elements_of(data, chapter)
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
