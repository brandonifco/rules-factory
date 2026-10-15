#!/usr/bin/env python3
"""Every difference between the CAN-SPAM texts in this directory and the texts they claim to be.

Two comparisons, each from the staged files and nothing else:

  statute     15 U.S.C. 7701-7713 (chapter 103, section bodies without notes) in the OLRC USLM
              release point 119-120, against Pub. L. 108-187 sections 2-15 as enacted (the GPO
              plain-text rendition).
  regulation  16 CFR 316.1-316.6 in the eCFR (point in time 2026-10-01) against the official
              annual edition (Title 16 Vol. 1, revised as of 2026-01-01).

The script reads the files, checks their SHA-256 against the digests staged with them, aligns the
two texts and emits every difference as one record of a JSON document
(`reference-differences.json`). `--render` writes REFERENCE-CHECK.md from that JSON and from
nothing else. It reads no network, writes only what `--out`/`--into` name, and uses the standard
library only. Run it under `python3 -I -B`.

Usage:
  reference-check.py --uslm-zip ZIP --act-html HTML --ecfr-xml XML --annual-xml XML [--out JSON]
  reference-check.py --uslm-zip ZIP ... --check JSON      regenerate and compare; exit 1 on a change
  reference-check.py --render JSON [--into MARKDOWN]      the report, from the JSON alone
  reference-check.py --render JSON --check-report MARKDOWN

Exit 0 on success, 1 on a failed check, 2 on a usage error or a file that is not the staged one.

What is compared, and how (all of it is in this file; the rule ids below are the ones in the JSON)
----------------------------------------------------------------------------------------------

Alignment. Act section N is aligned to the codified section whose own source credit reads
"Pub. L. 108-187, § N" (the file states the mapping; nothing is assumed). Inside a section a
paragraph is aligned to the paragraph with the same chain of markers, (a)(1)(A)(i)(I) in both. The
Act's paragraphs are found from the typewriter indentation of the GPO rendition, a marker's place
in its sequence (a, b, c / 1, 2, 3 / A, B, C / i, ii, iii / I, II, III) and, for the few markers
printed inside a line, the run-in heading before them; a marker that does not continue its
sequence stops the run. Text the file sets as a `continuation` is aligned, in order, with the Act's
flush text that follows a nested list. A paragraph that exists in one text only is a difference.

Base normalization, applied to both texts before anything is compared:

  N-WHITESPACE   every run of whitespace, line breaks included, is one space; a line break after a
                 hyphen is a line break, and the hyphen stays.
  N-USLM-MARKUP  XML elements are removed and their text kept in document order; the USLM
                 `<notes>` and `<sourceCredit>` of a section are not text of its body, and an
                 inline footnote (`<note type="footnote">`) and its reference marks are kept.
  N-GPO-MARKUP   in the Act, the `[[Page 117 STAT. n]]` markers and the `<<NOTE: ...>>` insertions
                 are removed, the HTML entities of the rendition are decoded, and the text between
                 `<pre>` and `</pre>` is the Act.
  N-TOKENS       a text is compared as a sequence of words and punctuation marks (a run of letters
                 and digits, or one other mark; the rendition's ``, '' and -- are one mark each),
                 case-sensitively. The text of a heading is kept apart from the text of the
                 paragraph it heads, and the marker "(a)" apart from both.

Everything else is a difference, and each difference gets the first class below whose rules
apply, in this order and no other:

  formatting     the difference vanishes under a typographic rule: F-QUOTE-DOUBLE, F-QUOTE-SINGLE,
                 F-APOSTROPHE, F-DASH-EM, F-DASH-EN, F-RUNIN-DELIM, F-HEADCASE, F-HYPHENATION.
  codification   a substitution the codifier makes and the USLM file documents for that location:
                 C-THIS-ACT, C-SECTION-NUMBER, C-SECTION-HEADING, C-OMITTED-SUBSECTION,
                 C-ACT-SECTION-ELSEWHERE, C-FOOTNOTE. A substitution the file does not document
                 for that location is not codification, however usual it is.
  textual        a difference confined to the form of a heading or a citation, where both texts
                 name the same thing and the file or the Act says why: T-CITATION-FORM,
                 T-CITATION-QUALIFIER, T-OF-THIS-TITLE, T-UNITED-STATES-CODE.
  potentially-substantive
                 everything else, and every case in which a rule's condition is not met: P-REMAINDER.

A class says what kind of textual difference this is. It does not say whether it matters.
"""
import argparse
import difflib
import hashlib
import html
import io
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

SCHEMA = "rules-factory/reference-differences/1"

#: The staged files, by the SHA-256 recorded with them. A file whose digest is another is not the
#: file this comparison was written for, and nothing is compared.
EXPECTED = {
    "uslm-zip": ("xml_usc15@119-120.zip", "e053dcada37ec19ab55ec063abd415642b09a3e8ef9a37cc70ca88030d59e699"),
    "uslm-member": ("usc15.xml", "f645b7bd6febb9c734299d637e5478de0f5091e1cec2bcd7f44e8c1a0b9bc93b"),
    "act-html": ("PLAW-108publ187.htm", "cf42d67e2eef175afab70e6e9576e90f065918212db597b4d1011addfdfdef4f"),
    "ecfr-xml": ("title-16.part-316.xml", "45bf26b68a06dc81f55388a06eb4e376ceb061a490e3858fb6105143d1d583b0"),
    "annual-xml": ("CFR-2026-title16-vol1-part316.xml", "a673076327582e9f435af822c7522bcce3c50fb82571d14b479089ae07067da2"),
}

NS = "{http://xml.house.gov/schemas/uslm/1.0}"
CHAPTER_ID = "/us/usc/t15/ch103"
MEMBER = "usc15.xml"
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_RATIO = 200

FORMATTING, CODIFICATION, TEXTUAL, SUBSTANTIVE = (
    "formatting", "codification", "textual", "potentially-substantive")
CLASSES = (FORMATTING, CODIFICATION, TEXTUAL, SUBSTANTIVE)

#: id -> (class, what the rule says). The JSON carries this table, so a record's rule is readable
#: without this file.
RULES = {
    "F-QUOTE-DOUBLE": (FORMATTING, "The Act's typewriter double quotes `` and '' are the typographic marks “ and ”."),
    "F-QUOTE-SINGLE": (FORMATTING, "In the Act, ` opens and a ' that closes it is the typographic ‘ and ’."),
    "F-APOSTROPHE": (FORMATTING, "In the Act, a ' that closes no ` is the apostrophe ’."),
    "F-DASH-EM": (FORMATTING, "The Act's -- is the em dash —."),
    "F-DASH-EN": (FORMATTING, "A hyphen is the en dash – (a range, as in 80a–1)."),
    "F-RUNIN-DELIM": (FORMATTING, "The Act sets a heading in the line of text it heads, closed by .-- (and a section heading closed by a period); the USLM file holds the heading apart, with no delimiter."),
    "F-HEADCASE": (FORMATTING, "A heading's words are the same words; the Act capitalizes them differently (capitals or title case) from the file's sentence case."),
    "F-HYPHENATION": (FORMATTING, "A word the Act breaks with a hyphen at a line end is the word without the break."),
    "C-THIS-ACT": (CODIFICATION, "'this Act' is 'this chapter' where a References in Text note of the section says that this chapter was in the original 'this Act' for that location."),
    "C-SECTION-NUMBER": (CODIFICATION, "A reference to Act section N is a reference to the codified section whose own source credit reads 'Pub. L. 108-187, § N'."),
    "C-SECTION-HEADING": (CODIFICATION, "The Act's section designation 'SEC. N.' is the codified section's '§ M.' where M's own source credit reads 'Pub. L. 108-187, § N'."),
    "C-OMITTED-SUBSECTION": (CODIFICATION, "A subsection the file prints as 'Omitted' is the Act subsection that a Codification note of the section says was classified elsewhere."),
    "C-ACT-SECTION-ELSEWHERE": (CODIFICATION, "An Act section with no codified section in the chapter is one that a note of the chapter says amended or enacted law elsewhere in the Code."),
    "C-FOOTNOTE": (CODIFICATION, "A footnote (and its reference marks) set in the body of a codified section is the codifier's own annotation; the Act has none."),
    "T-CITATION-FORM": (TEXTUAL, "A citation of a section of another Act, given with the Act's name and its Code place, is the Code citation of the same section: the Act's parenthetical and the file's citation name the same Code section."),
    "T-CITATION-QUALIFIER": (TEXTUAL, "'of this Act' qualifying a citation of a section of this Act is 'of this title' qualifying the citation of the codified section it maps to."),
    "T-OF-THIS-TITLE": (TEXTUAL, "'of this title' follows the file's citation of a section of this title; the Act cites its own sections without it."),
    "T-UNITED-STATES-CODE": (TEXTUAL, "', United States Code' after 'title N' in the Act is absent from the file, whose citation of title N is to the Code (a reference of the file resolves 'title N' to /us/usc/tN)."),
    "P-REMAINDER": (SUBSTANTIVE, "No formatting, codification or textual rule applies to the difference."),
}

NORMALIZATION = (
    ("N-WHITESPACE", "Every run of whitespace, line breaks included, is one space; a line break after a hyphen is a line break and the hyphen stays."),
    ("N-USLM-MARKUP", "USLM elements are removed and their text kept in document order; a section's notes and source credit are not its body; an inline footnote and its reference marks are kept."),
    ("N-GPO-MARKUP", "The Act's [[Page 117 STAT. n]] markers and <<NOTE: ...>> insertions are removed, HTML entities decoded, and the text between <pre> and </pre> is the Act."),
    ("N-TOKENS", "Texts are compared as words and punctuation marks, case-sensitively; a heading is kept apart from the paragraph it heads and the marker from both."),
)

#: Deliberately bounded, so that a rule can be watched failing on a small thing.
CITE_WINDOW = 14
#: The Act sections compared with the chapter: sections 2-15 (section 1, the short title, and section 16,
#: the effective date, are in the codification as notes, and notes are outside the comparison).
IN_SCOPE = range(2, 16)


class InputError(Exception):
    """A staged file is not the one this comparison was written for."""


# --------------------------------------------------------------------------------- tokens
TOKEN = re.compile(r"``|''|--|\w+|[^\w\s]")


class Tok:
    __slots__ = ("text", "start", "end", "role", "href", "brk", "closing", "composite")

    def __init__(self, text, start, end, role, href=None, brk=False):
        self.text, self.start, self.end, self.role = text, start, end, role
        self.href, self.brk = href, brk
        self.closing = False
        self.composite = None


class Unit:
    """One paragraph (or heading, or footnote) of a text: its normalized string and its tokens."""

    def __init__(self, label, s, toks, ident=None, path=(), kind="unit"):
        self.label, self.s, self.toks, self.ident, self.path, self.kind = label, s, toks, ident, path, kind

    def group(self, name):
        roles = GROUPS[name]
        return [t for t in self.toks if t.role in roles]


GROUPS = {"num": ("num",), "head": ("heading", "delim"), "body": ("text", "footnote")}
HEADING_ROLES = ("heading", "delim")


def collapse(text):
    return re.sub(r"\s+", " ", text)


class Builder:
    """A unit's string, built from segments that each carry the role of the element they came from."""

    def __init__(self):
        self.s = ""
        self.ann = []

    def add(self, text, role, href=None):
        text = collapse(text)
        if self.s.endswith(" ") and text.startswith(" "):
            text = text[1:]
        if not text:
            return
        a = len(self.s)
        self.s += text
        self.ann.append((a, len(self.s), role, href))

    def space(self):
        if self.s and not self.s.endswith(" "):
            self.s += " "

    def tokens(self):
        out = []
        ai = 0
        for m in TOKEN.finditer(self.s):
            while self.ann[ai][1] <= m.start():
                ai += 1
            out.append(Tok(m.group(), m.start(), m.end(), self.ann[ai][2], self.ann[ai][3]))
        return out


def local(el):
    return el.tag.rsplit("}", 1)[-1]


def text_of(el):
    return collapse("".join(el.itertext())).strip()


# --------------------------------------------------------------------------------- USLM
UNIT_TAGS = {"section", "subsection", "paragraph", "subparagraph", "clause", "subclause", "item", "subitem"}
BLOCK_TAGS = {"p", "note", "num", "heading", "chapeau", "content", "continuation"}


def _flat(el, b, role, href=None):
    if el.text:
        b.add(el.text, role, href)
    for c in el:
        t = local(c)
        if t == "ref" and c.get("href") is None:
            # a reference mark to a footnote
            b.space()
            _flat(c, b, "footnote", None)
            b.space()
        elif t == "ref":
            _flat(c, b, role, c.get("href"))
        elif t == "note":
            b.space()
            _flat(c, b, "footnote", href)
            b.space()
        elif t in BLOCK_TAGS:
            b.space()
            _flat(c, b, role, href)
            b.space()
        else:
            _flat(c, b, role, href)
        if c.tail:
            b.add(c.tail, role, href)


def read_chapter(zip_path, check=True):
    """The chapter element of the release point's one member, parsed in memory."""
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if names != [MEMBER]:
            raise InputError(f"{zip_path}: expected exactly one member, {MEMBER}; found {names}")
        info = z.getinfo(MEMBER)
        if info.file_size > MAX_MEMBER_BYTES or info.file_size > MAX_RATIO * max(info.compress_size, 1):
            raise InputError(f"{zip_path}: member {MEMBER} is not the size of a release point")
        data = z.read(MEMBER)
    if check:
        verify_digest("uslm-member", data, f"{zip_path}:{MEMBER}")
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise InputError(f"{zip_path}: {MEMBER} declares a DTD or an entity")
    return chapter_from_member(data)


def chapter_from_member(data):
    inside = False
    chapter = None
    for event, el in ET.iterparse(io.BytesIO(data), events=("start", "end")):
        if event == "start":
            if el.tag == NS + "chapter" and el.get("identifier") == CHAPTER_ID:
                inside = True
        else:
            if inside:
                if el.tag == NS + "chapter" and el.get("identifier") == CHAPTER_ID:
                    chapter = el
                    break
            else:
                el.clear()
    if chapter is None:
        raise InputError(f"{MEMBER} holds no chapter {CHAPTER_ID}")
    return chapter


def uslm_section_number(sec):
    return int(sec.get("identifier").rsplit("/s", 1)[1])


def uslm_units(sec):
    """[Unit] of one section in document order; `continuation` text is a unit of its own."""
    out = []
    cont = [0]

    def walk(u):
        b = Builder()
        for c in u:
            t = local(c)
            if t in ("num", "heading", "chapeau", "content"):
                b.space()
                _flat(c, b, {"num": "num", "heading": "heading"}.get(t, "text"))
                b.space()
        ident = u.get("identifier")
        path = tuple(ident.split("/")[5:])
        out.append(Unit(label_of(path), b.s.strip(), b.tokens(), ident, path))
        # children in document order, continuation text as its own unit
        for c in u:
            t = local(c)
            if t in UNIT_TAGS:
                walk(c)
            elif t == "continuation":
                cont[0] += 1
                cb = Builder()
                cb.space()
                _flat(c, cb, "text")
                out.append(Unit(f"~continuation{cont[0]}", cb.s.strip(), cb.tokens(), ident,
                                ("~continuation", str(cont[0])), "continuation"))
    walk(sec)
    return out


def label_of(path):
    return "".join(f"({p})" for p in path)


def source_credit(sec):
    for c in sec:
        if local(c) == "sourceCredit":
            return text_of(c)
    return None


def build_notes(sec):
    """[(topic, [paragraph text])] of a section's notes, with the note's place."""
    out = []
    for notes in sec:
        if local(notes) != "notes":
            continue
        for note in notes:
            topic = note.get("topic")
            paras = [text_of(p) for p in note if local(p) == "p"]
            out.append((topic, paras))
    return out


# ------------------------------------------------------------ the codification's own statements
CREDIT = re.compile(r"Pub\. L\. 108[–-]187, § (\d+)\b")
THIS_ACT_NOTE = re.compile(r"^This chapter, referred to in (?P<scope>.+?), was in the original “this Act”")


def parse_scope(scope):
    """'text' -> None (the whole section); 'subsecs. (a) and (b)(3), (4)' -> [[a], [b, 3], [b, 4]]."""
    scope = scope.strip()
    if scope == "text":
        return None
    scope = re.sub(r"^(?:subsecs?|pars?|subpars?|cls?)\.\s*", "", scope)
    paths = []
    for item in re.split(r",\s*|\s+and\s+", scope):
        item = item.strip()
        if not item:
            continue
        marks = re.findall(r"\(([A-Za-z0-9]+)\)", item)
        if not marks:
            raise InputError(f"cannot read the scope of a References in Text note: {scope!r}")
        if paths and len(marks) < len(paths[-1]):
            marks = paths[-1][:len(paths[-1]) - len(marks)] + marks
        paths.append(marks)
    return paths


class Statute:
    """What the codification says about itself, by section."""

    def __init__(self, chapter):
        self.sections = {}      # codified number -> element
        self.act_to_code = {}   # Act section -> codified number
        self.credit = {}        # codified number -> source credit text
        self.ident = {}         # codified number -> identifier
        self.notes = {}         # codified number -> [(topic, [paragraph])]
        self.scopes = {}        # codified number -> [(scope paths | None, paragraph, index)]
        for sec in chapter.findall(NS + "section"):
            n = uslm_section_number(sec)
            self.sections[n] = sec
            self.ident[n] = sec.get("identifier")
            credit = source_credit(sec)
            m = CREDIT.search(credit or "")
            if not m:
                raise InputError(f"section {n} has no source credit naming a section of Pub. L. 108-187")
            self.credit[n] = credit
            self.act_to_code[int(m.group(1))] = n
            self.notes[n] = build_notes(sec)
            self.scopes[n] = []
            for topic, paras in self.notes[n]:
                if topic != "referencesInText":
                    continue
                for k, p in enumerate(paras, 1):
                    m2 = THIS_ACT_NOTE.match(p)
                    if m2:
                        self.scopes[n].append((parse_scope(m2.group("scope")), p, k))

    def scope_covering(self, n, path):
        """The References in Text paragraph of section n that covers `path`, or None."""
        for paths, p, k in self.scopes.get(n, ()):
            if paths is None or any(list(path[:len(s)]) == s for s in paths):
                return p, k
        return None

    def ev_credit(self, n):
        return {"kind": "source-credit", "location": f"{self.ident[n]} sourceCredit", "quote": self.credit[n]}

    def ev_note(self, n, topic, k, paragraph):
        return {"kind": "note", "location": f"{self.ident[n]} notes/note[@topic={topic}]/p[{k}]", "quote": paragraph}

    def omitted_note(self, n, letter):
        """The Codification paragraph of section n that says subsection `letter` was classified elsewhere."""
        act = next((a for a, c in self.act_to_code.items() if c == n), None)
        for topic, paras in self.notes[n]:
            if topic != "codification":
                continue
            for k, p in enumerate(paras, 1):
                if re.search(rf"Subsec\. \({letter}\) of section {act} of Pub\. L\. 108[–-]187 (?:enacted|amended)", p):
                    return topic, k, p
        return None

    def credit_in_notes(self, act):
        """Notes of the chapter that print 'Pub. L. 108-187, § N' for an Act section N."""
        out = []
        for n in sorted(self.notes):
            for topic, paras in self.notes[n]:
                for k, p in enumerate(paras, 1):
                    if re.search(rf"Pub\. L\. 108[–-]187, § {act},", p):
                        out.append(self.ev_note(n, topic, k, p))
        return out

    def elsewhere_note(self, act):
        """A note of the chapter saying Act section `act` amended or enacted law elsewhere."""
        for n in sorted(self.notes):
            for topic, paras in self.notes[n]:
                for k, p in enumerate(paras, 1):
                    for sent in re.split(r"(?<=[.])\s+", p):
                        if re.match(rf"Section {act} (?:amended|enacted) ", sent):
                            return n, topic, k, p, sent
        return None

    def has_ref_to_title(self, n, title):
        """A reference of the file that resolves a citation of 'title N' to /us/usc/tN: this section's
        first, then any other section of the chapter. -> (text, href, identifier of its paragraph)."""
        def find(el, ident):
            ident = el.get("identifier") or ident
            for c in el:
                if local(c) in ("notes", "sourceCredit"):
                    continue
                if local(c) == "ref" and (c.get("href") or "").startswith(f"/us/usc/t{title}/"):
                    return text_of(c), c.get("href"), ident
                got = find(c, ident)
                if got:
                    return got
            return None
        for m in [n] + [x for x in sorted(self.sections) if x != n]:
            got = find(self.sections[m], self.ident[m])
            if got:
                return got
        return None


# --------------------------------------------------------------------------------- the Act
LEVELS = {4: 0, 12: 1, 20: 2, 26: 3, 36: 4}
MARK = re.compile(r"^( *)\(([A-Za-z0-9]+)\)(?= |$)")
SEC = re.compile(r"^SEC(?:TION|\.) (\d+)\.")
ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
ROMAN_FORMS = ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
               (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))


def roman_value(s):
    if not s or any(ch not in ROMAN_VALUES for ch in s):
        return None
    v = 0
    for k, ch in enumerate(s):
        n = ROMAN_VALUES[ch]
        v += -n if k + 1 < len(s) and ROMAN_VALUES[s[k + 1]] > n else n
    back, rest = "", v
    for val, sym in ROMAN_FORMS:
        while rest >= val:
            back += sym
            rest -= val
    return v if back == s else None


def ordinal(marker, level):
    """Where a marker stands in the sequence of a level, or None if it cannot be at that level."""
    if level == 1:
        return int(marker) if marker.isdigit() else None
    if level == 0:
        return ord(marker) - 96 if re.fullmatch(r"[a-z]", marker) else None
    if level == 2:
        return ord(marker) - 64 if re.fullmatch(r"[A-Z]", marker) else None
    if level == 3:
        return roman_value(marker) if marker.islower() else None
    if level == 4:
        return roman_value(marker.lower()) if marker.isupper() else None
    return None


def act_text(raw):
    m = re.search(r"<pre>(.*)</pre>", raw, re.S)
    if not m:
        raise InputError("the Act's HTML holds no <pre> text")
    return html.unescape(m.group(1))


def act_sections(text):
    """{Act section number: [line]} with the GPO markup removed (N-GPO-MARKUP)."""
    text = re.sub(r"\[\[Page [^\]]*\]\]", "", text)
    text = re.sub(r"<<NOTE:.*?>>", "", text, flags=re.S)
    secs = {}
    cur = None
    for line in text.split("\n"):
        m = SEC.match(line)
        if m:
            cur = int(m.group(1))
            if cur in secs:
                raise InputError(f"Act section {cur} appears twice")
            secs[cur] = []
        elif line.startswith("Approved "):
            cur = None
        if cur is not None:
            secs[cur].append(line)
    return secs


def act_units(lines):
    """-> [(path, lines, kind)] for one Act section, in text order. path () is the section's own text."""
    prepared = []
    for ln in lines:
        if ln.lstrip().startswith("``"):
            prepared.append((ln, None))
            continue
        m = re.match(r"^( *)(\([A-Za-z0-9]+\))(?=\([A-Za-z0-9]+\) )", ln)
        if m and len(m.group(1)) in LEVELS:
            first = m.group(1) + m.group(2)
            prepared.append((first, None))
            prepared.append((ln[len(first):], "inline"))
            continue
        k = ln.find(".--(")
        if k >= 0 and re.match(r"\.--\([A-Za-z0-9]+\) ", ln[k:]):
            prepared.append((ln[:k + 3], None))
            prepared.append((ln[k + 3:], "inline"))
            continue
        prepared.append((ln, None))
    units = []
    stack = []
    last = {}
    cur_path, cur, cur_kind = (), [], "unit"
    cont = 0
    wrap_of = [0]   # the indent at which the current paragraph's lines wrap

    def flush():
        if cur:
            units.append((cur_path, list(cur), cur_kind))

    for ln, flag in prepared:
        m = MARK.match(ln)
        quoted = ln.lstrip().startswith("``")
        standard = bool(m) and len(m.group(1)) in LEVELS and not quoted
        if m and (standard or flag == "inline"):
            marker = m.group(2)
            indent_level = LEVELS.get(len(m.group(1)))

            def parent_of(level):
                return tuple(x[1] for x in stack if x[0] < level)

            def fits(level):
                sib = last.get((parent_of(level), level))
                return ordinal(marker, level) == (1 if sib is None else sib + 1)

            ok = [lv for lv in range(5) if ordinal(marker, lv) is not None and fits(lv)]
            if indent_level in ok:
                level = indent_level
            elif len(ok) == 1:
                level = ok[0]
            elif len(ok) > 1:
                level = ok[0] if flag == "inline" else min(ok, key=lambda x: abs(x - (indent_level or 0)))
            else:
                raise InputError(f"Act marker ({marker}) does not continue its sequence: {ln.strip()[:70]!r}")
            host_wrap = wrap_of[0]
            flush()
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = tuple(x[1] for x in stack)
            wrap_of[0] = host_wrap if flag == "inline" else len(m.group(1)) - 4
            stack.append((level, marker, wrap_of[0]))
            last[(parent, level)] = ordinal(marker, level)
            for key in [k for k in last if len(k[0]) > len(parent)]:
                del last[key]
            cur_path, cur, cur_kind = tuple(x[1] for x in stack), [ln], "unit"
            continue
        # flush text that follows a nested list: it is set at the wrapping indent of an ancestor
        if not quoted and ln.strip() and flag is None and cur_kind == "unit" and cur_path:
            indent = len(ln) - len(ln.lstrip())
            owner = [x for x in stack[:-1] if x[2] == indent]
            if indent > 0 and indent < wrap_of[0] and owner \
                    and not any(x.lstrip().startswith("``") for x in cur):
                flush()
                cont += 1
                cur_path, cur, cur_kind = ("~continuation", str(cont)), [ln], "continuation"
                continue
        cur.append(ln)
    flush()
    return units


def join_lines(lines):
    s = ""
    brk = set()
    for ln in lines:
        piece = collapse(ln.strip())
        if not piece:
            continue
        if s:
            if re.search(r"[A-Za-z0-9]-$", s):
                brk.add(len(s) - 1)
            s += " "
        s += piece
    return s, brk


def act_unit(path, lines, kind):
    """The Unit of one Act paragraph, with the role of each token."""
    if kind == "continuation":
        s, brk = join_lines(lines)
        toks = [Tok(t.group(), t.start(), t.end(), "text", None, t.start() in brk) for t in TOKEN.finditer(s)]
        mark_quotes(toks)
        return Unit(f"~continuation{path[1]}", s, toks, None, path, "continuation")
    if path == ():
        k = next((i for i, l in enumerate(lines) if not l.strip()), len(lines))
        head, _ = join_lines(lines[:k])
        body, brk = join_lines(lines[k:])
        m = re.match(r"(SEC(?:TION|\.) \d+\.)(?: (.*))?$", head)
        s = head + (" " + body if body else "")
        shift = len(head) + 1
        toks = []
        n_num, n_head = len(m.group(1)), len(head)
        for t in TOKEN.finditer(s):
            role = "num" if t.end() <= n_num else "heading" if t.end() <= n_head else "text"
            toks.append(Tok(t.group(), t.start(), t.end(), role, None, (t.start() - shift) in brk))
        heads = [t for t in toks if t.role == "heading"]
        if heads and heads[-1].text == ".":
            heads[-1].role = "delim"
        mark_quotes(toks)
        return Unit("", s, toks, None, path)
    s, brk = join_lines(lines)
    toks = [Tok(t.group(), t.start(), t.end(), "text", None, t.start() in brk) for t in TOKEN.finditer(s)]
    if len(toks) < 3 or toks[0].text != "(" or toks[2].text != ")":
        raise InputError(f"Act paragraph does not begin with its marker: {s[:50]!r}")
    for t in toks[:3]:
        t.role = "num"
    # a run-in heading: words up to the first '.--' within the first 30 tokens, no sentence mark before it
    for j in range(3, min(len(toks) - 1, 34)):
        if toks[j].text == "." and toks[j + 1].text == "--":
            if any(t.text == "." for t in toks[3:j]):
                break
            for t in toks[3:j]:
                t.role = "heading"
            toks[j].role = toks[j + 1].role = "delim"
            break
    mark_quotes(toks)
    return Unit(label_of(path), s, toks, None, path)


def mark_quotes(toks):
    """A ' that closes a ` is a closing quote, any other ' is an apostrophe."""
    opened = 0
    for t in toks:
        if t.text == "`":
            opened += 1
        elif t.text == "'" and opened:
            opened -= 1
            t.closing = True


# --------------------------------------------------------------------------------- 16 CFR 316
def cfr_units(root, side):
    """{section number: [Unit]}: the heading, each paragraph, each footnote, by position."""
    out = {}
    if side == "ecfr":
        secs = [e for e in root.iter("DIV8") if e.get("TYPE") == "SECTION"]
    else:
        secs = list(root.iter("SECTION"))
    for sec in secs:
        if side == "ecfr":
            head = collapse("".join(sec.find("HEAD").itertext())).strip()
            number = sec.get("N")
        else:
            head = (text_of(sec.find("SECTNO")) + " " + text_of(sec.find("SUBJECT"))).strip()
            number = re.sub(r"^§\s*", "", text_of(sec.find("SECTNO")))
        units = []
        b = Builder()
        b.add(head, "heading")
        units.append(Unit("heading", b.s, b.tokens(), None, ("heading",), "heading"))
        counts = {"P": 0, "FTNT": 0}
        for child in sec:
            if child.tag in counts:
                counts[child.tag] += 1
                b = Builder()
                for piece in child.itertext():
                    b.add(piece, "text")
                label = f"{child.tag}{counts[child.tag]}"
                units.append(Unit(label, b.s.strip(), b.tokens(), None, (label,), "paragraph"))
        out[number] = units
    return out


# --------------------------------------------------------------------------------- comparison
class Ctx:
    """What the rules may consult."""

    def __init__(self, statute=None):
        self.statute = statute


def prev_text(toks, i, n=1):
    return toks[i - n].text if i - n >= 0 else None


def loose_key(toks, i, ctx):
    """The coarse class a token aligns by. A rule decides afterwards whether a pair is a rule's."""
    t = toks[i]
    x = t.text
    x = {"``": "“", "''": "”", "`": "‘", "'": "’", "--": "—", "–": "-"}.get(x, x)
    if t.role in HEADING_ROLES:
        x = x.lower()
    if t.composite:
        return t.composite
    p = prev_text(toks, i)
    if ctx.statute is not None:
        if x.isdigit() and p in ("section", "sections"):
            return "SECNUM"
        if t.text in ("Act", "chapter", "title") and p is not None and p.lower() == "this":
            return "THISX"
    return x


ACT_CITE = re.compile(
    r"(?<=\bsection )(?P<num>\d+[A-Za-z]*(?:\([A-Za-z0-9]+\))*(?: or \d+[A-Za-z]*(?:\([A-Za-z0-9]+\))*)?)"
    r" of (?:the )?(?P<name>[A-Z][^()]*?) \((?P<title>\d+) U\.S\.C\. "
    r"(?P<usc>[^()]*(?:\([^()]*\)[^()]*)*)\)")
CODE_CITE = re.compile(
    r"(?<=\bsection )(?P<num>\d+[A-Za-z]*(?:\([A-Za-z0-9]+\))*(?: or \d+[A-Za-z]*(?:\([A-Za-z0-9]+\))*)?)"
    r" of (?P<where>this title|title (?P<title>\d+))")
SECTION_RE = re.compile(r"\d+[A-Za-z]*(?:\([A-Za-z0-9]+\))*")


def cite_key(title, sections):
    return f"CITE:{title}:" + ",".join(sections)


def collapse_span(toks, start_char, end_char, s, key, href=None):
    """Replace the tokens in [start_char, end_char) by one composite token."""
    idx = [k for k, t in enumerate(toks) if t.start >= start_char and t.end <= end_char]
    if not idx:
        return False
    first, last = idx[0], idx[-1]
    c = Tok(s[toks[first].start:toks[last].end], toks[first].start, toks[last].end, toks[first].role, href)
    c.composite = key
    toks[first:last + 1] = [c]
    return True


def collapse_citations(ref_unit, corpus_unit, ref_toks, corpus_toks):
    """Citations of a section of another Act: the Act's name and Code place against the Code citation.
    Only a citation that both texts make is collapsed, so that one text's citation that the other does
    not make is compared word by word."""
    act_cites = {}
    for m in ACT_CITE.finditer(ref_unit.s):
        sections = SECTION_RE.findall(m.group("usc"))
        if sections:
            act_cites.setdefault(cite_key(m.group("title"), sections), []).append(m)
    code_cites = {}
    for m in CODE_CITE.finditer(corpus_unit.s):
        sections = SECTION_RE.findall(m.group("num"))
        code_cites.setdefault(cite_key(m.group("title") or "15", sections), []).append(m)
    for key in act_cites:
        if key not in code_cites:
            continue
        for m in act_cites[key]:
            collapse_span(ref_toks, m.start("num"), m.end(), ref_unit.s, key)
        for m in code_cites[key]:
            href = next((t.href for t in corpus_toks if t.href and t.start >= m.start("num") and t.end <= m.end()), None)
            collapse_span(corpus_toks, m.start("num"), m.end(), corpus_unit.s, key, href)


class Result:
    """The records of one comparison, numbered as they come."""

    def __init__(self, scope):
        self.scope = scope
        self.records = []
        self.counter = {}

    def add(self, unit_label, group, cls, rule, ref, corpus, ref_unit, corpus_unit, evidence, where):
        k = (unit_label, group)
        self.counter[k] = self.counter.get(k, 0) + 1
        self.records.append({
            "id": f"{unit_label}/{group}/{self.counter[k]}",
            "scope": self.scope,
            "uslmIdentifier": where.get("ident"),
            "actSection": where.get("act"),
            "actParagraph": where.get("actpath"),
            "corpusLocation": where.get("cloc"),
            "referenceLocation": where.get("rloc"),
            "part": group,
            "corpusText": corpus,
            "referenceText": ref,
            "corpusUnitText": corpus_unit.s if corpus_unit is not None else None,
            "referenceUnitText": ref_unit.s if ref_unit is not None else None,
            "class": cls,
            "rule": rule,
            "evidence": evidence,
        })


def span_text(unit, toks):
    if not toks:
        return ""
    return unit.s[toks[0].start:toks[-1].end]


# ------------------------------------------------------------------------------ rules: pairs
def ev_rule(rule):
    return {"kind": "normalization", "rule": rule, "statement": RULES[rule][1]}


def pair_formatting(a, c):
    """The formatting rule under which reference token a and corpus token c are the same, or None."""
    t, u = a.text, c.text
    if (t, u) in (("``", "“"), ("''", "”")):
        return "F-QUOTE-DOUBLE"
    if t == "`" and u == "‘":
        return "F-QUOTE-SINGLE"
    if t == "'" and u == "’":
        return "F-QUOTE-SINGLE" if a.closing else "F-APOSTROPHE"
    if (t, u) == ("--", "—"):
        return "F-DASH-EM"
    if (t, u) == ("-", "–"):
        return "F-DASH-EN"
    if a.role in HEADING_ROLES and c.role in HEADING_ROLES and t != u and t.lower() == u.lower():
        return "F-HEADCASE"
    return None


def pair_codification(ctx, where, rt, ct, i, j):
    a, c = rt[i], ct[j]
    st = ctx.statute
    if st is None:
        return None
    n = where.get("code")
    if a.composite and a.composite.startswith("SECNUM:") and a.composite == c.composite and a.text != c.text:
        m = int(a.composite.split(":")[1])
        return "C-SECTION-HEADING", [st.ev_credit(m)]
    if a.text == "Act" and c.text == "chapter" and (prev_text(rt, i) or "").lower() == "this" \
            and (prev_text(ct, j) or "").lower() == "this":
        cover = st.scope_covering(n, where.get("path", ())) if n else None
        if cover:
            p, k = cover
            return "C-THIS-ACT", [st.ev_note(n, "referencesInText", k, p)]
        return None
    if a.text.isdigit() and c.text.isdigit() and prev_text(rt, i) in ("section", "sections") \
            and prev_text(ct, j) in ("section", "sections"):
        m = st.act_to_code.get(int(a.text))
        if m is not None and m == int(c.text) and m in st.credit:
            return "C-SECTION-NUMBER", [st.ev_credit(m)]
    return None


def ref_around(ct, j):
    """The text and target of the reference (tokens sharing an href) that holds corpus token j."""
    href = ct[j].href
    if not href:
        return None
    lo = j
    while lo > 0 and ct[lo - 1].href == href:
        lo -= 1
    hi = j
    while hi + 1 < len(ct) and ct[hi + 1].href == href:
        hi += 1
    return lo, hi, href


def pair_textual(ctx, where, ru, cu, rt, ct, i, j):
    a, c = rt[i], ct[j]
    st = ctx.statute
    if st is None:
        return None
    if a.composite and a.composite.startswith("CITE:") and a.composite == c.composite and a.text != c.text:
        ev = [{"kind": "reference-text", "location": f"Pub. L. 108-187 §{where.get('act')}", "quote": a.text}]
        if c.href:
            ev.append({"kind": "ref", "location": where.get("ident"), "href": c.href, "quote": c.text})
        else:
            ev.append({"kind": "corpus-text", "location": where.get("ident"), "quote": c.text})
        return "T-CITATION-FORM", ev
    if a.text == "Act" and c.text == "title" and (prev_text(rt, i) or "").lower() == "this" \
            and (prev_text(ct, j) or "").lower() == "this" \
            and prev_text(rt, i, 2) == "of" and prev_text(ct, j, 2) == "of":
        # the section the Act cites and the section the file cites must be the same section
        act_num = next_cite(rt, i)
        code_num = next_cite(ct, j)
        if act_num is not None and code_num is not None and st.act_to_code.get(act_num) == code_num:
            ev = [st.ev_credit(code_num),
                  {"kind": "reference-text", "location": f"Pub. L. 108-187 §{where.get('act')}",
                   "quote": span_text(ru, rt[cite_start(rt, i):i + 1])},
                  {"kind": "corpus-text", "location": where.get("ident"),
                   "quote": span_text(cu, ct[cite_start(ct, j):j + 1])}]
            r = ref_around(ct, j)
            if r:
                ev.append({"kind": "ref", "location": where.get("ident"), "href": r[2],
                           "quote": span_text(cu, ct[r[0]:r[1] + 1])})
            return "T-CITATION-QUALIFIER", ev
    return None


def cite_start(toks, i):
    """Index of the 'section' that begins the nearest citation before token i."""
    for k in range(i - 1, max(i - CITE_WINDOW, 0) - 1, -1):
        if toks[k].text.isdigit() and prev_text(toks, k) in ("section", "sections"):
            return k - 1
    return i


def next_cite(toks, i):
    """The number of the nearest 'section N' before token i, within CITE_WINDOW tokens."""
    for k in range(i - 1, max(i - CITE_WINDOW, 0) - 1, -1):
        if toks[k].text.isdigit() and prev_text(toks, k) in ("section", "sections"):
            return int(toks[k].text)
    return None


def classify_pair(ctx, where, ru, cu, rt, ct, i, j):
    f = pair_formatting(rt[i], ct[j])
    if f:
        return FORMATTING, f, [ev_rule(f)]
    c = pair_codification(ctx, where, rt, ct, i, j)
    if c:
        return CODIFICATION, c[0], c[1]
    t = pair_textual(ctx, where, ru, cu, rt, ct, i, j)
    if t:
        return TEXTUAL, t[0], t[1]
    return None


# ------------------------------------------------------------------- rules: unpaired spans
def runs(idx):
    out = []
    for k in idx:
        if out and k == out[-1][1] + 1:
            out[-1][1] = k
        else:
            out.append([k, k])
    return out


def droppable(ctx, where, ru, cu, rt, ct, i1, i2, j1, j2):
    """Spans of an unpaired hunk that a rule accounts for: (side, lo, hi, class, rule, evidence)."""
    spans = []
    # F-RUNIN-DELIM: the Act's closing delimiter of a heading
    for lo, hi in runs([k for k in range(i1, i2) if rt[k].role == "delim"]):
        spans.append(("ref", lo, hi, FORMATTING, "F-RUNIN-DELIM", [ev_rule("F-RUNIN-DELIM")]))
    st = ctx.statute
    if st is None:
        return spans
    # C-FOOTNOTE
    for lo, hi in runs([k for k in range(j1, j2) if ct[k].role == "footnote"]):
        spans.append(("corpus", lo, hi, CODIFICATION, "C-FOOTNOTE",
                      [{"kind": "footnote", "location": where.get("ident"), "quote": span_text(cu, ct[lo:hi + 1])}]))
    # T-OF-THIS-TITLE: the words follow the file's citation of a section of this title
    k = j1
    while k + 2 < j2:
        if [t.text for t in ct[k:k + 3]] == ["of", "this", "title"] and all(
                t.href and t.href.startswith("/us/usc/t15/") for t in ct[k:k + 3]):
            r = ref_around(ct, k)
            ev = [{"kind": "ref", "location": where.get("ident"), "href": r[2], "quote": span_text(cu, ct[r[0]:r[1] + 1])}]
            m = re.match(r"/us/usc/t15/s(\d+)(?:/|$)", r[2])
            target = int(m.group(1)) if m else None
            if target in st.credit:
                ev.append(st.ev_credit(target))
            spans.append(("corpus", k, k + 2, TEXTUAL, "T-OF-THIS-TITLE", ev))
            k += 3
        else:
            k += 1
    # T-UNITED-STATES-CODE
    k = i1
    while k + 2 < i2:
        if [t.text for t in rt[k:k + 3]] == ["United", "States", "Code"]:
            lo, hi = k, k + 2
            if lo - 1 >= i1 and rt[lo - 1].text == ",":
                lo -= 1
            if hi + 1 < i2 and rt[hi + 1].text == ",":
                hi += 1
            q = k - 1
            if q >= 0 and rt[q].text == ",":
                q -= 1
            if q >= 1 and rt[q].text.isdigit() and rt[q - 1].text == "title":
                title = rt[q].text
                found = st.has_ref_to_title(where["code"], title)
                if found:
                    ev = [{"kind": "reference-text", "location": f"Pub. L. 108-187 §{where.get('act')}",
                           "quote": span_text(ru, rt[q - 1:hi + 1])},
                          {"kind": "ref", "location": found[2], "href": found[1], "quote": found[0]}]
                    spans.append(("ref", lo, hi, TEXTUAL, "T-UNITED-STATES-CODE", ev))
            k = hi + 1
        else:
            k += 1
    # one token is accounted for once
    spans.sort(key=lambda s: (s[0], s[1]))
    kept, taken = [], set()
    for sp in spans:
        cells = {(sp[0], x) for x in range(sp[1], sp[2] + 1)}
        if cells & taken:
            continue
        taken |= cells
        kept.append(sp)
    return kept


# ------------------------------------------------------------------------------- comparison
def compare_group(res, ctx, label, group, where, ru, cu, rt, ct):
    """Align the tokens of one group (marker, heading or body) of two aligned paragraphs; emit records."""
    rk = [loose_key_side(rt, i, ctx, "r") for i in range(len(rt))]
    ck = [loose_key_side(ct, j, ctx, "c") for j in range(len(ct))]
    sm = difflib.SequenceMatcher(None, rk, ck, autojunk=False)

    covered_r, covered_c = set(), set()

    def emit(cls, rule, ri, ci, evidence):
        covered_r.update(ri)
        covered_c.update(ci)
        res.add(label, group, cls, rule,
                span_text(ru, [rt[k] for k in ri]), span_text(cu, [ct[k] for k in ci]),
                ru, cu, evidence, where)

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            pending = None  # (class, rule, [ri], [ci], evidence)
            for d in range(i2 - i1):
                i, j = i1 + d, j1 + d
                if rt[i].text == ct[j].text and rt[i].composite == ct[j].composite:
                    if pending:
                        emit(pending[0], pending[1], pending[2], pending[3], pending[4])
                        pending = None
                    continue
                got = classify_pair(ctx, where, ru, cu, rt, ct, i, j)
                cls, rule, ev = got if got else (SUBSTANTIVE, "P-REMAINDER", [])
                if pending and pending[0] == cls and pending[1] == rule and pending[2][-1] == i - 1 \
                        and pending[3][-1] == j - 1 and not rt[i].composite:
                    pending[2].append(i)
                    pending[3].append(j)
                    pending[4].extend(e for e in ev if e not in pending[4])
                else:
                    if pending:
                        emit(pending[0], pending[1], pending[2], pending[3], pending[4])
                    pending = (cls, rule, [i], [j], list(ev))
            if pending:
                emit(pending[0], pending[1], pending[2], pending[3], pending[4])
            continue
        spans = droppable(ctx, where, ru, cu, rt, ct, i1, i2, j1, j2)
        taken_r = {x for sp in spans if sp[0] == "ref" for x in range(sp[1], sp[2] + 1)}
        taken_c = {x for sp in spans if sp[0] == "corpus" for x in range(sp[1], sp[2] + 1)}
        # records in text order: spans and the remainder, by where they start
        items = []
        for sp in spans:
            if sp[0] == "ref":
                items.append((sp[1], 0, sp))
            else:
                items.append((i1, 1, sp))
        rest_r = [k for k in range(i1, i2) if k not in taken_r]
        rest_c = [k for k in range(j1, j2) if k not in taken_c]
        if rest_r or rest_c:
            items.append((rest_r[0] if rest_r else i1, 2, ("rest", rest_r, rest_c)))
        items.sort(key=lambda x: (x[0], x[1]))
        for _, _, sp in items:
            if sp[0] == "ref":
                emit(sp[3], sp[4], list(range(sp[1], sp[2] + 1)), [], sp[5])
            elif sp[0] == "corpus":
                emit(sp[3], sp[4], [], list(range(sp[1], sp[2] + 1)), sp[5])
            else:
                rr = [rt[k] for k in sp[1]]
                cc = [ct[k] for k in sp[2]]
                if rr and cc and any(t.brk and t.text == "-" for t in rr) \
                        and "".join(t.text for t in rr if not (t.brk and t.text == "-")) == "".join(t.text for t in cc):
                    emit(FORMATTING, "F-HYPHENATION", sp[1], sp[2], [ev_rule("F-HYPHENATION")])
                else:
                    emit(SUBSTANTIVE, "P-REMAINDER", sp[1], sp[2], [])
    # what no record covers must be the same words in the same order, or a difference was lost
    left = [rt[k].text for k in range(len(rt)) if k not in covered_r]
    right = [ct[k].text for k in range(len(ct)) if k not in covered_c]
    if left != right:
        raise InputError(f"internal error: {label} {group}: the words no difference covers are not the same")


def loose_key_side(toks, i, ctx, side):
    """A closing delimiter of the Act and a footnote of the file have no counterpart: each is its own key."""
    if toks[i].role in ("delim", "footnote"):
        return f"\x00{side}{i}"
    return loose_key(toks, i, ctx)


def compare_unit(res, ctx, label, where, ru, cu, omitted):
    """Compare two aligned paragraphs, group by group."""
    st = ctx.statute
    for group in ("num", "head", "body"):
        rt = ru.group(group)
        ct = cu.group(group)
        if group == "num" and ru.path == () and st is not None:
            # the section designation: 'SEC. 2.' against '§ 7701.'
            if rt and ct:
                act = int(next(t.text for t in rt if t.text.isdigit()))
                code = next((t.text for t in ct if t.text.isdigit()), "")
                key = f"SECNUM:{st.act_to_code.get(act)}"
                ckey = f"SECNUM:{code}"
                rt = [collapse_group(ru, rt, key)]
                ct = [collapse_group(cu, ct, ckey)]
        if group == "head" and st is not None and where.get("code") and len(cu.path) == 1 \
                and [t.text.lower() for t in ct] == ["omitted"] and not cu.group("body"):
            note = st.omitted_note(where["code"], cu.path[0])
            if note and rt:
                topic, k, p = note
                omitted.add(cu.path)
                res.add(label, group, CODIFICATION, "C-OMITTED-SUBSECTION", span_text(ru, rt), span_text(cu, ct),
                        ru, cu, [st.ev_note(where["code"], topic, k, p)], where)
                continue
        if group == "body" and st is not None:
            collapse_citations(ru, cu, rt, ct)
        compare_group(res, ctx, label, group, where, ru, cu, rt, ct)


def collapse_group(unit, toks, key):
    c = Tok(unit.s[toks[0].start:toks[-1].end], toks[0].start, toks[-1].end, toks[0].role)
    c.composite = key
    return c


def whole_unit_record(res, label, side, unit, cls, rule, evidence, where):
    """A paragraph that exists in one text only: one record, holding all of it."""
    text = unit.s
    if side == "reference":
        res.add(label, "unit", cls, rule, text, "", unit, None, evidence, where)
    else:
        res.add(label, "unit", cls, rule, "", text, None, unit, evidence, where)


# ------------------------------------------------------------------------- the statute
def statute_where(ident, act, path, code):
    shown = "".join(f"({p})" for p in path) if path[:1] != ("~continuation",) else f" continuation {path[1]}"
    return {"ident": ident, "act": act, "actpath": shown, "code": code, "path": path,
            "cloc": ident, "rloc": f"Pub. L. 108-187 § {act}{shown}"}


def compare_statute(chapter, act_raw):
    """-> (alignment, records) of 15 U.S.C. 7701-7713 against Pub. L. 108-187 sections 2-15."""
    st = Statute(chapter)
    ctx = Ctx(st)
    secs = act_sections(act_text(act_raw))
    res = Result("statute")
    alignment, unaligned = [], []
    for act_n in sorted(secs):
        code_n = st.act_to_code.get(act_n)
        if code_n is None:
            found = st.elsewhere_note(act_n)
            lines = secs[act_n]
            text, _ = join_lines(lines)
            where = statute_where(None, act_n, (), None)
            if act_n not in IN_SCOPE:
                unaligned.append({"actSection": act_n, "reason": "outside sections 2-15 of the Act, which are what is compared",
                                  "evidence": st.credit_in_notes(act_n), "text": text})
                continue
            if found:
                n, topic, k, p, sent = found
                ev = [st.ev_note(n, topic, k, sent)]
                rec_unit = Unit(f"act{act_n}", text, [], None, ())
                whole_unit_record(res, f"act-{act_n}", "reference", rec_unit, CODIFICATION, "C-ACT-SECTION-ELSEWHERE", ev, where)
            else:
                rec_unit = Unit(f"act{act_n}", text, [], None, ())
                whole_unit_record(res, f"act-{act_n}", "reference", rec_unit, SUBSTANTIVE, "P-REMAINDER", [], where)
            unaligned.append({"actSection": act_n, "reason": "no codified section of the chapter has this Act section as its source credit",
                              "evidence": [], "text": text})
            continue
        sec = st.sections[code_n]
        ident = st.ident[code_n]
        alignment.append({"actSection": act_n, "codifiedSection": code_n, "identifier": ident,
                          "sourceCredit": st.credit[code_n]})
        c_units = uslm_units(sec)
        r_units = [act_unit(p, l, k) for p, l, k in act_units(secs[act_n])]
        c_by = {u.path: u for u in c_units}
        r_by = {u.path: u for u in r_units}
        omitted = set()
        for cu in c_units:
            label = f"{code_n}{label_of(cu.path) if cu.path[:1] != ('~continuation',) else '~continuation' + cu.path[1]}"
            ru = r_by.get(cu.path)
            where = statute_where(cu.ident, act_n, cu.path, code_n)
            if ru is None:
                whole_unit_record(res, label, "corpus", cu, SUBSTANTIVE, "P-REMAINDER", [], where)
                continue
            compare_unit(res, ctx, label, where, ru, cu, omitted)
        for ru in r_units:
            if ru.path in c_by:
                continue
            label = f"{code_n}{label_of(ru.path) if ru.path[:1] != ('~continuation',) else '~continuation' + ru.path[1]}"
            where = statute_where(None, act_n, ru.path, code_n)
            above = next((ru.path[:k] for k in range(len(ru.path), 0, -1) if ru.path[:k] in omitted), None)
            if above:
                topic, k, p = st.omitted_note(code_n, above[0])
                whole_unit_record(res, label, "reference", ru, CODIFICATION, "C-OMITTED-SUBSECTION",
                                  [st.ev_note(code_n, topic, k, p)], where)
            else:
                whole_unit_record(res, label, "reference", ru, SUBSTANTIVE, "P-REMAINDER", [], where)
    return alignment, unaligned, res.records


# ------------------------------------------------------------------------ the regulation
def regulation_where(number, label):
    return {"ident": None, "act": None, "actpath": None,
            "cloc": f"16 CFR {number} {label} (eCFR, point in time 2026-10-01)",
            "rloc": f"16 CFR {number} {label} (annual edition, revised as of 2026-01-01)"}


def compare_regulation(ecfr_bytes, annual_bytes):
    corpus = cfr_units(ET.fromstring(ecfr_bytes), "ecfr")
    reference = cfr_units(ET.fromstring(annual_bytes), "annual")
    ctx = Ctx(None)
    res = Result("regulation")
    alignment = []
    if sorted(corpus) != sorted(reference):
        raise InputError(f"the two editions of 16 CFR 316 do not hold the same sections: {sorted(corpus)} / {sorted(reference)}")
    for number in sorted(corpus, key=lambda x: [int(p) for p in x.split(".")]):
        c_by = {u.label: u for u in corpus[number]}
        r_by = {u.label: u for u in reference[number]}
        alignment.append({"section": f"16 CFR {number}", "units": len(corpus[number]),
                          "words": {"eCFR": sum(1 for u in corpus[number] for t in u.toks if re.match(r"\w", t.text)),
                                    "annual": sum(1 for u in reference[number] for t in u.toks if re.match(r"\w", t.text))}})
        for cu in corpus[number]:
            ru = r_by.get(cu.label)
            where = regulation_where(number, cu.label)
            label = f"{number}/{cu.label}"
            if ru is None:
                whole_unit_record(res, label, "corpus", cu, SUBSTANTIVE, "P-REMAINDER", [], where)
                continue
            compare_unit(res, ctx, label, where, ru, cu, set())
        for ru in reference[number]:
            if ru.label not in c_by:
                whole_unit_record(res, f"{number}/{ru.label}", "reference", ru, SUBSTANTIVE, "P-REMAINDER", [],
                                  regulation_where(number, ru.label))
    return alignment, res.records


# ------------------------------------------------------------------------------ the document
def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_digest(role, data, shown):
    name, want = EXPECTED[role]
    got = sha256(data)
    if got != want:
        raise InputError(f"{shown}: SHA-256 {got} is not the staged {name} ({want}); nothing was compared")


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def build(zip_path, act_path, ecfr_path, annual_path, check=True):
    """-> the document, as a dict."""
    zip_bytes = read_bytes(zip_path)
    act_bytes = read_bytes(act_path)
    ecfr_bytes = read_bytes(ecfr_path)
    annual_bytes = read_bytes(annual_path)
    if check:
        verify_digest("uslm-zip", zip_bytes, zip_path)
        verify_digest("act-html", act_bytes, act_path)
        verify_digest("ecfr-xml", ecfr_bytes, ecfr_path)
        verify_digest("annual-xml", annual_bytes, annual_path)
    chapter = read_chapter(zip_path, check)
    alignment, unaligned, statute = compare_statute(chapter, act_bytes.decode("utf-8"))
    reg_alignment, regulation = compare_regulation(ecfr_bytes, annual_bytes)
    records = regulation + statute
    return {
        "schema": SCHEMA,
        "inputs": [
            {"role": "uslm-zip", "file": EXPECTED["uslm-zip"][0], "sha256": EXPECTED["uslm-zip"][1],
             "describes": "OLRC USLM release point 119-120, Title 15"},
            {"role": "uslm-member", "file": f"{EXPECTED['uslm-zip'][0]}:{MEMBER}", "sha256": EXPECTED["uslm-member"][1],
             "describes": "the member of the zip; chapter 103, section bodies without notes"},
            {"role": "act-html", "file": EXPECTED["act-html"][0], "sha256": EXPECTED["act-html"][1],
             "describes": "Pub. L. 108-187, 117 Stat. 2699, GPO plain-text rendition; sections 2-15"},
            {"role": "ecfr-xml", "file": EXPECTED["ecfr-xml"][0], "sha256": EXPECTED["ecfr-xml"][1],
             "describes": "16 CFR Part 316, eCFR versioner XML, point in time 2026-10-01"},
            {"role": "annual-xml", "file": EXPECTED["annual-xml"][0], "sha256": EXPECTED["annual-xml"][1],
             "describes": "16 CFR Part 316, official annual edition (Title 16 Vol. 1), revised as of 2026-01-01"},
        ],
        "normalization": [{"id": i, "statement": t} for i, t in NORMALIZATION],
        "rules": [{"id": i, "class": c, "statement": t} for i, (c, t) in RULES.items()],
        "alignment": {
            "statute": alignment,
            "statuteUnaligned": unaligned,
            "regulation": reg_alignment,
        },
        "differences": records,
    }


def dump(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------- the report
#: The categories of the previous, hand-run report and the counts it gave. Its 43 "explained by the
#: source" were the first three; its 260 "unexplained" the rest.
PREVIOUS = (
    ("“this chapter” (code) for “this Act” (Act)", 40, "explained"),
    ("§ 7703 body “Omitted”", 1, "explained"),
    ("§ 7706(d) footnote “So in original.”", 2, "explained"),
    ("“December 16, 2003” (code) for “the date of (the) enactment of this Act” (Act)", 7, "unexplained"),
    ("cross-references: Act section numbers against codified section numbers, “of this title”, en dash in “80a–1”", 75, "unexplained"),
    ("“, United States Code” after “title N” in the Act", 14, "unexplained"),
    ("citations to other Acts, and “of this title” for “of this Act” at § 7706(f)(1)", 12, "unexplained"),
    ("heading capitalisation and terminal punctuation", 60, "unexplained"),
    ("apostrophe", 11, "unexplained"),
    ("run-in heading delimiter “.—”", 81, "unexplained"),
)
NOT_COUNTED = "not in the previous report"


def previous_category(r):
    """Which of the previous report's categories a statute difference belongs to, by rule and text."""
    rule, ref = r["rule"], r["referenceText"]
    if rule == "C-THIS-ACT":
        return PREVIOUS[0][0]
    if rule == "C-OMITTED-SUBSECTION":
        return PREVIOUS[1][0] if r["part"] == "head" else NOT_COUNTED
    if rule == "C-FOOTNOTE":
        return PREVIOUS[2][0]
    if rule == "P-REMAINDER" and ref.startswith("the date of"):
        return PREVIOUS[3][0]
    if rule in ("C-SECTION-NUMBER", "T-OF-THIS-TITLE", "T-CITATION-QUALIFIER", "F-DASH-EN"):
        return PREVIOUS[4][0]
    if rule == "P-REMAINDER" and (ref == "5" or r["corpusText"] == "of this title"):
        return PREVIOUS[4][0]
    if rule == "T-UNITED-STATES-CODE" or (rule == "P-REMAINDER" and "United States Code" in ref):
        return PREVIOUS[5][0]
    if rule == "T-CITATION-FORM":
        return PREVIOUS[6][0]
    if rule == "F-HEADCASE" or (rule == "F-RUNIN-DELIM" and ref == "."):
        return PREVIOUS[7][0]
    if rule == "F-APOSTROPHE":
        return PREVIOUS[8][0]
    if rule == "F-RUNIN-DELIM":
        return PREVIOUS[9][0]
    return NOT_COUNTED


def cell(text):
    return "“" + text.replace("|", "\\|") + "”" if text else "—"


def render(doc):
    """REFERENCE-CHECK.md, from the document and nothing else."""
    diffs = doc["differences"]
    stat = [d for d in diffs if d["scope"] == "statute"]
    reg = [d for d in diffs if d["scope"] == "regulation"]
    inputs = {i["role"]: i for i in doc["inputs"]}

    def counts(rs):
        by_class = {c: 0 for c in CLASSES}
        by_rule = {}
        for d in rs:
            by_class[d["class"]] += 1
            by_rule[d["rule"]] = by_rule.get(d["rule"], 0) + 1
        return by_class, by_rule

    def short(role):
        return inputs[role]["sha256"][:8] + "…" + inputs[role]["sha256"][-4:]

    out = []
    w = out.append
    w("# Reference check: the regulation and the codified statute against their reference texts")
    w("")
    w("This file is written by `reference-check.py --render reference-differences.json` from that JSON and")
    w("from nothing else; edit neither by hand. `reference-check.py` regenerates the JSON from the staged")
    w("files (their SHA-256 checked), and `--check` fails when the JSON is not what the files give. It compares,")
    w("by text alone and without interpreting anything, each text this example corpus is built from against")
    w("the text that is the law it claims to be. A class says what kind of textual difference a difference")
    w("is. It does not say whether the difference matters.")
    w("")
    w("| Text checked | Edition | Reference text | Edition |")
    w("|---|---|---|---|")
    w(f"| 16 CFR 316.1-316.6, `part316.xml` (SHA-256 `{short('ecfr-xml')}`) | eCFR, point-in-time 2026-10-01 | "
      f"the official annual edition of 16 CFR Part 316, Title 16 Vol. 1, GPO XML (SHA-256 `{short('annual-xml')}`) | revised as of 2026-01-01 |")
    w(f"| 15 U.S.C. 7701-7713, chapter 103, section bodies without notes: member `usc15.xml` of the OLRC USLM release point "
      f"119-120 (zip SHA-256 `{short('uslm-zip')}`; member `{short('uslm-member')}`) | current through Pub. L. 119-120 | "
      f"the CAN-SPAM Act as enacted, Pub. L. 108-187, 117 Stat. 2699, GPO plain-text rendition (SHA-256 `{short('act-html')}`), sections 2-15 | 2003-12-16 |")
    w("")
    w("The two editions of the regulation are nine months apart (2026-01-01 and 2026-10-01). A difference between")
    w("them could be an amendment as well as an error; the comparison cannot tell, and nothing below is read as either.")
    w("")
    w("## Method")
    w("")
    w("Both texts are first normalized, and only this way:")
    w("")
    for n in doc["normalization"]:
        w(f"- **{n['id']}**: {n['statement']}")
    w("")
    w("Everything else is compared as it stands, word by word and punctuation mark by punctuation mark,")
    w("case-sensitively. A statute's Act section N is aligned to the codified section whose own source credit reads")
    w("\"Pub. L. 108–187, § N\", and a paragraph to the paragraph with the same chain of markers. Each difference then")
    w("gets the first class whose rules apply, in this order and no other:")
    w("")
    w("| Class | Rule | What the rule says | Differences |")
    w("|---|---|---|---:|")
    all_counts = counts(diffs)[1]
    for c in CLASSES:
        for r in doc["rules"]:
            if r["class"] == c:
                w(f"| {c} | `{r['id']}` | {r['statement'].replace('|', chr(92) + '|')} | {all_counts.get(r['id'], 0)} |")
    w("")
    w("A substitution that is conventional but is not documented in the USLM file for that location is not")
    w("`codification`. Where a rule's condition is not met, or the rules do not settle it, the difference is")
    w("`potentially-substantive`: no difference is argued into a lighter class.")
    w("")
    w("## 16 CFR 316.1-316.6")
    w("")
    sections = ", ".join(f"{a['section'].replace('16 CFR ', '')} ({a['words']['eCFR']} words)" for a in doc["alignment"]["regulation"])
    w(f"Section by section, with paragraph, footnote and heading text included, the two texts hold the same words in the")
    w(f"same order but for what is listed here: {sections}.")
    w("")
    byc, _ = counts(reg)
    w(f"Total: **{len(reg)}** difference{'s' if len(reg) != 1 else ''}"
      + (": " + ", ".join(f"{n} {c}" for c, n in byc.items() if n) if reg else "") + ".")
    w("")
    for d in reg:
        w(f"- `{d['id']}` {d['class']} (`{d['rule']}`): eCFR {cell(d['corpusText'])}, annual edition {cell(d['referenceText'])}.")
    w("")
    w("## 15 U.S.C. 7701-7713 against Pub. L. 108-187")
    w("")
    w("| Codified § | Act § | Source credit |")
    w("|---|---|---|")
    for a in doc["alignment"]["statute"]:
        w(f"| {a['codifiedSection']} | {a['actSection']} | {a['sourceCredit']} |")
    w("")
    for u in doc["alignment"]["statuteUnaligned"]:
        held = "; ".join(e["location"] for e in u["evidence"])
        w(f"Act section {u['actSection']} has no counterpart in the chapter: {u['reason']}"
          + (f" (the file holds it as a note: {held})" if held else "") + ".")
        w("")
    w("")
    byc, byr = counts(stat)
    w(f"Total: **{len(stat)}** differences.")
    w("")
    w("| Class | Count |")
    w("|---|---:|")
    for c in CLASSES:
        w(f"| {c} | {byc[c]} |")
    w("")
    w("| Rule | Class | Count |")
    w("|---|---|---:|")
    for r in doc["rules"]:
        if byr.get(r["id"]):
            w(f"| `{r['id']}` | {r['class']} | {byr[r['id']]} |")
    w("")
    w("| Codified § | Act § | " + " | ".join(CLASSES) + " |")
    w("|---|---|" + "---:|" * len(CLASSES))
    secs = {}
    for d in stat:
        key = (d["actSection"], section_of(d))
        secs.setdefault(key, {c: 0 for c in CLASSES})[d["class"]] += 1
    for (act, code), cs in sorted(secs.items(), key=lambda kv: kv[0][0]):
        w(f"| {code if code else '—'} | {act} | " + " | ".join(str(cs[c]) for c in CLASSES) + " |")
    w("")
    w("### The previous report's 43 and 260")
    w("")
    typographic = sum(byr.get(r, 0) for r in ("F-QUOTE-DOUBLE", "F-QUOTE-SINGLE", "F-DASH-EM"))
    designations = byr.get("C-SECTION-HEADING", 0) + byr.get("C-ACT-SECTION-ELSEWHERE", 0)
    w("The previous, hand-run report found 303 differences in the statute: 43 \"explained by the source\" and 260")
    w(f"\"unexplained\". This report finds **{len(stat)}**, which is {len(stat) - 303:+d}. The count differs because the")
    w("unit of count differs, and not because a text changed:")
    w("")
    w(f"- the previous report read the Act's typewriter quotation marks and dashes as typographic ones before it compared;")
    w(f"  here each is a difference of class `formatting` ({typographic} of them: `F-QUOTE-DOUBLE`, `F-QUOTE-SINGLE`, `F-DASH-EM`);")
    w(f"- the section designations (\"SEC. 2.\" against \"§ 7701.\") and Act section 12 were outside its comparison; here they are")
    w(f"  `C-SECTION-HEADING` and `C-ACT-SECTION-ELSEWHERE` ({designations}), and the Act paragraphs that the file prints as \"Omitted\" are")
    w(f"  one record each, besides the heading ({byr.get('C-OMITTED-SUBSECTION', 0)} for the previous report's 1);")
    w("- it listed one difference where a section number changes and \"of this title\" is added, and where a heading's")
    w("  case and closing delimiter differ; here each rule's part is its own record, and a citation of another Act is one record")
    w("  where the previous report listed its words as several.")
    w("")
    w("Its 43 \"explained by the source\" are the three rows below marked so; the rest of its 260 are spread over `formatting`,")
    w("`codification`, `textual` and `potentially-substantive` as the columns show.")
    w("")
    w("| Previous category | Previous count | Previous status | " + " | ".join(CLASSES) + " | Now |")
    w("|---|---:|---|" + "---:|" * len(CLASSES) + "---:|")
    mapping = {}
    for d in stat:
        mapping.setdefault(previous_category(d), {c: 0 for c in CLASSES})[d["class"]] += 1
    for label, n, status in PREVIOUS:
        cs = mapping.get(label, {c: 0 for c in CLASSES})
        w(f"| {label} | {n} | {status} | " + " | ".join(str(cs[c]) for c in CLASSES) + f" | {sum(cs.values())} |")
    cs = mapping.get(NOT_COUNTED, {c: 0 for c in CLASSES})
    w(f"| {NOT_COUNTED} | 0 | — | " + " | ".join(str(cs[c]) for c in CLASSES) + f" | {sum(cs.values())} |")
    w(f"| **Total** | **303** | **43 + 260** | " + " | ".join(f"**{byc[c]}**" for c in CLASSES) + f" | **{len(stat)}** |")
    w("")
    ps = [d for d in diffs if d["class"] == SUBSTANTIVE]
    w("## Potentially-substantive differences")
    w("")
    w(f"{len(ps)} in all ({len([d for d in ps if d['scope'] == 'statute'])} in the statute, "
      f"{len([d for d in ps if d['scope'] == 'regulation'])} in the regulation), each with both texts and the paragraph that holds it.")
    w("")
    w("| Id | Where | Corpus text | Reference text | Corpus paragraph | Reference paragraph |")
    w("|---|---|---|---|---|---|")
    for d in ps:
        where = d["uslmIdentifier"] or d["corpusLocation"] or ""
        ref_where = d["referenceLocation"] or ""
        w(f"| `{d['id']}` | {where}; {ref_where} | {cell(d['corpusText'])} | {cell(d['referenceText'])} | "
          f"{cell(d['corpusUnitText'] or '')} | {cell(d['referenceUnitText'] or '')} |")
    w("")
    return "\n".join(out)


def section_of(d):
    m = re.match(r"/us/usc/t15/s(\d+)", d["uslmIdentifier"] or "")
    if m:
        return int(m.group(1))
    m = re.match(r"(\d{4})", d["id"])
    return int(m.group(1)) if m else None


# ----------------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(prog="reference-check.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--uslm-zip")
    ap.add_argument("--act-html")
    ap.add_argument("--ecfr-xml")
    ap.add_argument("--annual-xml")
    ap.add_argument("--out", help="write the JSON here (default: standard output)")
    ap.add_argument("--check", metavar="JSON", help="regenerate and compare with this JSON; exit 1 when it differs")
    ap.add_argument("--render", metavar="JSON", help="write the report from this JSON")
    ap.add_argument("--into", help="with --render: write the report here (default: standard output)")
    ap.add_argument("--check-report", metavar="MARKDOWN", help="with --render: exit 1 when this file is not the report")
    args = ap.parse_args(argv)
    try:
        if args.render:
            with open(args.render, encoding="utf-8") as f:
                doc = json.load(f)
            text = render(doc)
            if args.check_report:
                with open(args.check_report, encoding="utf-8") as f:
                    have = f.read()
                if have != text:
                    print(f"{args.check_report} is not the report of {args.render}; run --render --into", file=sys.stderr)
                    return 1
                print(f"{args.check_report} is the report of {args.render}")
                return 0
            if args.into:
                with open(args.into, "w", encoding="utf-8") as f:
                    f.write(text)
            else:
                sys.stdout.write(text)
            return 0
        paths = (args.uslm_zip, args.act_html, args.ecfr_xml, args.annual_xml)
        if not all(paths):
            ap.error("--uslm-zip, --act-html, --ecfr-xml and --annual-xml are all required")
        doc = build(*paths)
        text = dump(doc)
        if args.check:
            with open(args.check, encoding="utf-8") as f:
                have = f.read()
            if have != text:
                print(f"{args.check} is not what the staged files give", file=sys.stderr)
                return 1
            print(f"{args.check} is what the staged files give: {len(doc['differences'])} differences")
            return 0
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            sys.stdout.write(text)
        return 0
    except InputError as e:
        print(f"reference-check.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
