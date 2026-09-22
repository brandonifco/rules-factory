#!/usr/bin/env python3
"""Derive this trial's three committed corpora from one Office of Law Revision Counsel release.

The Federal Rules of Civil Procedure are published as part of Title 28 Appendix of the United
States Code, and the OLRC serves that title as **one** 4.7 MB USLM XML document per release
point. Every other corpus this repository admits arrives as its own served document -- the eCFR
versioner returns one section, Gutenberg returns one book -- so `retrievedFrom` alone has always
said what the digest covers. Here it cannot: a digest over the whole title would cover the
Appellate and Evidence rules as well, and no reader could tell which bytes a quote was held to.

So the derivation is named, written down, and reproducible. For each rule it takes:

  * the `<courtRule>` element **verbatim from the release's bytes**, from `<courtRule` to the
    matching `</courtRule>`, including its `<sourceCredit>`; and
  * **not** the `<notes type="uscNote">` child the OLRC appends -- the Notes of the Advisory
    Committee on Rules and the editorial amendment notes.

and wraps it in a minimal `<uscDoc>` root carrying the USLM namespace, so each file is a
well-formed document an XML reader can open on its own.

**Dropping the notes is an admission decision and not a convenience.** The Advisory Committee
Notes are transmitted with the rules and are read by courts as an interpretive aid, but they are
not the rule: the rule is what the Supreme Court prescribed and Congress let take effect. A map
built over the notes would quote a commentator's account of a rule as if it were the rule. The
manifest records the choice in `hashDerivation`, the protocol records it in `adapterReach`, and
README.md says what it costs: no entry of this map can be supported by an Advisory Committee
Note, and a rule stated only in one is beyond this adapter's reach.

Nothing else is removed, rewritten or normalised. The bytes between `<courtRule` and
`</courtRule>`, minus that one child element, are the release's own.

The three rules go in **one** file, in the order the release prints them, because they are one
document sliced once: Part 107's twelve sections arrive the same way and its extent lists them.
Nothing here splits one mapping problem into three corpora (0039).

Usage:
  derive-corpus.py --from <usc28a.xml> --into <frcp-6-12-81.xml>
  derive-corpus.py --from <usc28a.xml> --check <frcp-6-12-81.xml>

Exit 0 when the slice was derived (or matched), 1 otherwise, 2 on a usage error.
"""
from __future__ import annotations

import argparse
import filecmp
import pathlib
import re
import sys
import tempfile

# The rules this trial admits, and the identifier each one carries in the release.
RULES = ("6", "12", "81")
IDENTIFIER = "/us/usc/t28a/courtRules/Civil/rule%s"
NAMESPACE = "http://xml.house.gov/schemas/uslm/1.0"
HEADER = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<!-- Derived by examples/frcp-6-12-81/derive-corpus.py from the OLRC release named\n'
          '     in corpus-manifest.json. One <courtRule> element, verbatim, without the\n'
          '     <notes type="uscNote"> child. -->\n'
          f'<uscDoc xmlns="{NAMESPACE}" identifier="/us/usc/t28a">\n')
FOOTER = "\n</uscDoc>\n"


def subtree(release: str, number: str) -> str:
    """One rule's `<courtRule>` element, verbatim, with the uscNote child removed.

    The scan is textual because the output must be the release's own bytes: parsing and
    re-serialising would rewrite entity references, attribute order and whitespace, and a quote
    checked against a re-serialisation is not checked against what the OLRC published.
    """
    anchor = release.find('identifier="%s"' % (IDENTIFIER % number))
    if anchor < 0:
        raise LookupError(f"the release holds no {IDENTIFIER % number}")
    start = release.rfind("<courtRule", 0, anchor)
    # `<courtRule>` does not nest, so the first close after the anchor is this element's.
    end = release.find("</courtRule>", anchor)
    if start < 0 or end < 0:
        raise LookupError(f"rule {number}'s element is not delimited")
    element = release[start:end + len("</courtRule>")]
    notes = re.search(r'<notes type="uscNote"', element)
    if notes is None:
        raise LookupError(f"rule {number} carries no <notes type=\"uscNote\"> to remove")
    return element[:notes.start()].rstrip() + "</courtRule>"


def derive(release_path: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    release = release_path.read_text(encoding="utf-8")
    body = "\n".join(subtree(release, number) for number in RULES)
    target.write_text(HEADER + body + FOOTER, encoding="utf-8")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="release", type=pathlib.Path,
                        help="the release's usc28a.xml")
    parser.add_argument("--into", type=pathlib.Path)
    parser.add_argument("--check", type=pathlib.Path,
                        help="an already-derived slice to compare a fresh derivation against")
    args = parser.parse_args(argv)

    if args.check is not None:
        if args.release is None:
            parser.error("--check needs --from <usc28a.xml> to re-derive from")
        with tempfile.TemporaryDirectory() as scratch:
            fresh = derive(args.release, pathlib.Path(scratch) / "fresh.xml")
            same = filecmp.cmp(fresh, args.check, shallow=False)
        print(f"{args.check}: {'matches' if same else 'DIFFERS FROM'} a fresh derivation of "
              f"{args.release}")
        return 0 if same else 1

    if args.release is None or args.into is None:
        parser.error("--from and --into are both required")
    print(f"wrote {derive(args.release, args.into)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
