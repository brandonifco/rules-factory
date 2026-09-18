"""Stage the inputs a blind second mapping is given, and hold a staged run to what it staged.

[docs/method.md](../../docs/method.md), *Before the map is used*, says what a second mapper
receives: the pinned corpus extract, `docs/corpus-map.md` and `docs/method.md`, **with every
worked example drawn from the corpus under mapping removed**. Until #223 nothing enforced that.
Staging was a paragraph of prose addressed to whoever ran the exercise, the exercise was run by
hand, and staging a second mapping of `srd-52-conditions` copied both documents verbatim. Both
leaked: `docs/corpus-map.md` named an entry id from the slice under mapping and part of what its
text says, and `docs/method.md` carried eight references to the neighbouring slice of the same
corpus. The mapper read the leak and disclosed it. The staging did not, and could not: the
comparison tooling compares two maps and cannot see what the second mapper was given.

A leak is not a spoiled run. 0014's claim is that a second reading is worth something *because
it is independent*, so a contaminated run reported as blind **manufactures agreement**, and
agreement is the evidence the procedure produces.

Staging belongs to the mapper (0032, 0033): producing both mappings from independently staged
inputs is mapping, and comparison, adjudication and certification stay with the validator.

## What is judgement here, and what is not

Which example is "drawn from the corpus under mapping" is a judgement, and a tool that guessed
at it and passed would be worse than no tool, because it would manufacture the confidence the
leak destroys. So this splits the work in two:

  * **The substitutions are declared**, in a staging spec committed with the run: one edit per
    example, each saying why, each required to match its document exactly once. That half is
    trial 7's `redact.py` with the edit list moved out of the code and the code moved out of
    the trial.

  * **Completeness is mechanical.** An example is *drawn from the corpus under mapping* when it
    names something that corpus's maps name. The vocabulary is read out of the maps -- every
    map of the same `corpus`, the neighbouring slices included, because a sibling slice's entry
    id is this corpus's vocabulary and `cover-degree` in `method.md` is exactly the leak #223
    found -- and the redacted documents are scanned for it. Nothing here decides *whether* an
    occurrence is a leak. It decides only whether a human still has to look:

      `certain`  an entry id with a hyphen in it, or the corpus id itself. `incapacitated-condition`
                 is not a phrase English produces by accident. A run with one is not staged.

      `possible` a one-word entry id, an entry's `name`, or a word of the corpus id -- `action`,
                 `reach`, `Flanking`, `SRD`. These are words a document uses for its own reasons,
                 and no rule tells the two apart. The run is NOT VERIFIED until each is either
                 edited away or acknowledged in the spec, by document and term, with a reason.
                 Acknowledgement records the count, so a later occurrence is a change.

## What it cannot see, stated here rather than in a commit message

  * **Paraphrase.** The method warns that an example "rewritten to paraphrase the corpus" leaks
    too. An example that describes a rule of the corpus under mapping in words that name no
    entry and no id is invisible to this, and always will be. That is the declared half's job.
  * **Examples from another corpus that share this one's shapes.** Trial 7 removed the
    backgammon examples from an SRD staging anyway, because dice, turns and a phase gate are
    the SRD's shapes too. No scan can judge that.
  * **Anything outside the documents staged.** A prompt, a brief or a review thread that states
    the first mapper's reading leaks the whole map, and this never sees one.

Every run prints these, and the record repeats them, because a limit that is only in the source
is a limit the reader of the evidence does not have.
"""
import hashlib
import json
import os
import re

from mapcontract.entry import entries_of

from mapper.protocol import Refused

SPEC_VERSION = 1
RECORD_VERSION = 1
RECORD_FILENAME = "staged-inputs.json"
LOG_FILENAME = "REDACTIONS.md"

# A leak nothing else would produce, and a leak a document produces every other page. Split on
# the one thing that is mechanical about them: a hyphenated slug is a coinage, a bare word is a
# word. Both are reported; only the first is an answer.
CERTAIN, POSSIBLE = "certain", "possible"

LIMITS = (
    "Paraphrase: an example that describes a rule of the corpus under mapping without naming an "
    "entry, an id or the corpus is invisible to the scan. The declared edits are what covers it.",
    "Examples from another corpus that share this corpus's shapes -- dice, turns, a phase gate -- "
    "are not leaks of this corpus and are not detected. Whether to replace them anyway is a "
    "judgement the spec makes.",
    "Anything the second mapper is given that is not one of these documents: a prompt, a brief or "
    "a review thread that states the first mapper's reading is outside what this stages.",
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as handle:
        return sha256_bytes(handle.read())


def _read_json(path, what):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"cannot read {what} {path}: {error}")


def _read_text(path, what):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        raise Refused(f"cannot read {what} {path}: {error}")


# ---------------------------------------------------------------- the spec

def load_spec(path):
    """The staging spec: what is being staged, and every substitution, declared."""
    spec = _read_json(path, "staging spec")
    if not isinstance(spec, dict):
        raise Refused(f"{path}: a staging spec is a JSON object")
    if spec.get("stagingVersion") != SPEC_VERSION:
        raise Refused(f"{path}: stagingVersion is {spec.get('stagingVersion')!r}; this mapper "
                      f"stages version {SPEC_VERSION}")
    for field in ("map", "documents"):
        if not spec.get(field):
            raise Refused(f"{path}: a staging spec names {field}")
    if not isinstance(spec["documents"], list) or not all(isinstance(d, str) for d in spec["documents"]):
        raise Refused(f"{path}: documents is a list of paths, relative to the spec")
    names = [os.path.basename(d) for d in spec["documents"]]
    if len(set(names)) != len(names):
        raise Refused(f"{path}: two staged documents share a file name: {', '.join(sorted(names))}")
    for position, edit in enumerate(spec.get("edits") or []):
        if not isinstance(edit, dict):
            raise Refused(f"{path}: edit {position} is not an object")
        for field in ("document", "why", "find"):
            if not isinstance(edit.get(field), str) or not edit[field].strip():
                raise Refused(f"{path}: edit {position} needs a non-empty {field}")
        if not isinstance(edit.get("replace", ""), str):
            raise Refused(f"{path}: edit {position}'s replace is text (\"\" deletes)")
        if edit["document"] not in names:
            raise Refused(f"{path}: edit {position} edits {edit['document']!r}, which is not one "
                          f"of the staged documents ({', '.join(names)})")
    for position, ack in enumerate(spec.get("acknowledged") or []):
        if not isinstance(ack, dict) or not all(
                isinstance(ack.get(f), str) and ack[f].strip() for f in ("document", "term", "reason")):
            raise Refused(f"{path}: acknowledgement {position} needs document, term and reason")
        if ack["document"] not in names:
            raise Refused(f"{path}: acknowledgement {position} names document {ack['document']!r}, "
                          f"which is not staged")
    return spec


# ---------------------------------------------------------------- the vocabulary

def corpus_of(document):
    value = document.get("corpus") if isinstance(document, dict) else None
    return value if isinstance(value, str) and value.strip() else None


def sibling_maps(map_path, root=None):
    """Every committed map of the same corpus, this one included.

    The neighbours are the point. `srd-52-conditions` and `srd-52-combat` are two slices of one
    corpus, and the eight references #223 found in `method.md` were to the *other* slice's
    entries -- this corpus's vocabulary, handed to a mapper reading this corpus. A staging that
    took its vocabulary from the map under mapping alone would have passed the run that failed.

    The default root is the directory holding the trials (`examples/`, two levels above a map at
    `examples/<trial>/corpus-map.json`), searched with the two globs validate.sh uses.
    """
    map_path = os.path.abspath(map_path)
    document = _read_json(map_path, "map")
    corpus = corpus_of(document)
    if corpus is None:
        raise Refused(f"{map_path}: the map declares no corpus, so nothing says which other maps "
                      f"read the same one")
    if root is None:
        root = os.path.dirname(os.path.dirname(map_path))
    found = {map_path: document}
    for trial in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        directory = os.path.join(root, trial)
        if not os.path.isdir(directory):
            continue
        for where in (directory, *(os.path.join(directory, sub) for sub in sorted(os.listdir(directory)))):
            if not os.path.isdir(where):
                continue
            for name in sorted(os.listdir(where)):
                if not (name.startswith("corpus-map") and name.endswith(".json")):
                    continue
                candidate = os.path.join(where, name)
                if candidate in found:
                    continue
                try:
                    other = _read_json(candidate, "map")
                except Refused:
                    continue
                if corpus_of(other) == corpus:
                    found[candidate] = other
    return corpus, found


def vocabulary(corpus, maps):
    """(term -> class) for everything the corpus's maps name.

    An id with a hyphen, and the corpus id itself, are coinages: `certain`. A one-word id, an
    entry's `name` and a word of the corpus id are words a document has its own uses for:
    `possible`, which is a question and not a verdict.
    """
    terms = {}

    def add(term, weight):
        term = term.strip()
        if len(term) < 3:
            return
        key = term.lower()
        if terms.get(key) != CERTAIN:
            terms[key] = weight

    add(corpus, CERTAIN)
    for word in re.split(r"[^A-Za-z0-9]+", corpus):
        if word.isalpha():
            add(word, POSSIBLE)
    for document in maps.values():
        for entry in entries_of(document):
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("id")
            if isinstance(identifier, str) and identifier.strip():
                add(identifier, CERTAIN if "-" in identifier else POSSIBLE)
            name = entry.get("name")
            if isinstance(name, str) and name.strip():
                add(name, POSSIBLE)
    return terms


def _term_pattern(term):
    """A term, bounded by anything that is not a letter or a digit.

    The boundary is deliberately not `\\b` and not "not a word character or a hyphen". Both let a
    compound hide a term, which is the one failure that matters here: the first run of this over
    the `srd-52-conditions` staging reported clean while `srd-52-combat`,
    `srd-5.2.1-pdftotext-24.02.0-page-marked` and `SRD_CC_v5.2.1.pdf` were still in the
    documents, because a hyphen and an underscore each ended the term for the boundary and not
    for a reader. A scan that reports clean over a leak is worse than no scan.

    Whitespace inside a term matches any run of whitespace, because markdown wraps its lines.
    """
    parts = [re.escape(p) for p in re.split(r"\s+", term.strip()) if p]
    return re.compile(r"(?<![A-Za-z0-9])" + r"\s+".join(parts) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def scan(text, terms):
    """Every occurrence of a term in the vocabulary: [(term, class, line), ...]."""
    hits = []
    for term, weight in sorted(terms.items()):
        for match in _term_pattern(term).finditer(text):
            hits.append((term, weight, text.count("\n", 0, match.start()) + 1))
    return sorted(hits, key=lambda hit: (hit[2], hit[0]))


# ---------------------------------------------------------------- staging

def _whitespace_insensitive(find):
    parts = [re.escape(p) for p in re.split(r"\s+", find.strip()) if p]
    return re.compile(r"\s+".join(parts))


def apply_edits(texts, edits):
    """Each declared edit, in order, matching its document exactly once.

    Exactly once is the whole discipline: an edit that matches twice removed one example and
    left another, and an edit that matches nothing is an example that moved and a redaction that
    silently did not happen.
    """
    applied, problems = [], []
    for position, edit in enumerate(edits):
        text = texts[edit["document"]]
        pattern = _whitespace_insensitive(edit["find"])
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            problems.append(f"edit {position} ({edit['document']}: {edit['why']}) matched "
                            f"{len(matches)} time(s); an edit matches exactly once")
            continue
        line = text.count("\n", 0, matches[0].start()) + 1
        replacement = edit.get("replace", "")
        texts[edit["document"]] = text[:matches[0].start()] + replacement + text[matches[0].end():]
        applied.append({"document": edit["document"], "why": edit["why"], "line": line,
                        "deletes": replacement == ""})
    return applied, problems


def flatten_links(texts):
    """A markdown link to a file the mapper does not have becomes its own text.

    The mapper is given these documents and the corpus extract, and nothing else: a link to a
    decision record, an issue or a trial directory is an offer it cannot take up. The target is
    also prose -- `0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md`
    says a good deal -- so flattening removes text the scan would otherwise have to judge.
    """
    kept = set(texts)
    counts = {}

    def plain(match):
        text, target = match.group(1), match.group(2)
        if target.split("#")[0] in kept or target.startswith("#"):
            return match.group(0)
        counts[target.split("#")[0]] = counts.get(target.split("#")[0], 0) + 1
        return text

    for name in texts:
        texts[name] = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", plain, texts[name])
    return counts


def stage(spec_path, out_dir, root=None):
    """Produce the bundle. Returns (record, problems, unresolved).

    `problems` are failures -- an edit that did not match once, a `certain` leak left in a
    staged document. `unresolved` are the `possible` occurrences nobody has ruled on, which are
    NOT VERIFIED rather than either.
    """
    spec_path = os.path.abspath(spec_path)
    spec_dir = os.path.dirname(spec_path)
    spec = load_spec(spec_path)
    map_path = os.path.join(spec_dir, spec["map"])
    corpus, maps = sibling_maps(map_path, root)
    for extra in spec.get("alsoMapped") or []:
        path = os.path.abspath(os.path.join(spec_dir, extra))
        if path not in maps:
            maps[path] = _read_json(path, "map")
    terms = vocabulary(corpus, maps)

    sources, texts = {}, {}
    for relative in spec["documents"]:
        path = os.path.join(spec_dir, relative)
        name = os.path.basename(relative)
        texts[name] = _read_text(path, "document")
        sources[name] = {"path": relative, "sha256": sha256_file(path)}

    applied, problems = apply_edits(texts, spec.get("edits") or [])
    links = flatten_links(texts) if spec.get("flattenLinks", True) else {}

    acknowledged = {(a["document"], a["term"].lower()): a["reason"]
                    for a in spec.get("acknowledged") or []}
    counted, residue, unresolved = {}, [], []
    for name in sorted(texts):
        for term, weight, line in scan(texts[name], terms):
            item = {"document": name, "term": term, "class": weight, "line": line}
            if weight == CERTAIN:
                residue.append(item)
                problems.append(f"{name}:{line}: {term!r} is an id the corpus's maps coin; a "
                                f"staged document that names it is not blind")
            elif (name, term) in acknowledged:
                counted[(name, term)] = counted.get((name, term), 0) + 1
            else:
                unresolved.append(item)
    problems.extend(f"{document}: {term!r} is acknowledged and does not occur"
                    for (document, term) in sorted(acknowledged) if (document, term) not in counted)

    record = {
        "recordVersion": RECORD_VERSION,
        "about": "What a blind second mapping was given, by digest (docs/method.md, #223). "
                 "`mapper stage --verify` re-hashes every file named here and re-runs the scan "
                 "over the staged documents; scripts/validate.sh runs it on every record.",
        "corpus": corpus,
        "spec": {"path": os.path.relpath(spec_path, out_dir), "sha256": sha256_file(spec_path)},
        "vocabularyFrom": [
            {"path": os.path.relpath(path, out_dir), "sha256": sha256_file(path),
             "entries": len(entries_of(document))}
            for path, document in sorted(maps.items())],
        "terms": {CERTAIN: sorted(t for t, w in terms.items() if w == CERTAIN),
                  POSSIBLE: sorted(t for t, w in terms.items() if w == POSSIBLE)},
        "documents": [
            {"name": name,
             "source": sources[name]["path"],
             "sourceSha256": sources[name]["sha256"],
             "sha256": sha256_bytes(texts[name].encode("utf-8")),
             "edits": sum(1 for edit in applied if edit["document"] == name)}
            for name in sorted(texts)],
        "record": {"path": LOG_FILENAME},
        "acknowledged": [
            {"document": document, "term": term, "occurrences": counted.get((document, term), 0),
             "reason": acknowledged[(document, term)]}
            for (document, term) in sorted(acknowledged)],
        "residue": {CERTAIN: len(residue), POSSIBLE: len(unresolved),
                    "acknowledged": sum(counted.values())},
        "limits": list(LIMITS),
    }

    os.makedirs(out_dir, exist_ok=True)
    for name, text in texts.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            handle.write(text)
    log = write_log(os.path.join(out_dir, LOG_FILENAME), record, applied, links, residue, unresolved)
    record["record"]["sha256"] = log
    with open(os.path.join(out_dir, RECORD_FILENAME), "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return record, problems, unresolved


def write_log(path, record, applied, links, residue, unresolved):
    """The record of what was removed, in the shape trial 7's REDACTIONS.md had."""
    lines = ["# Redactions", "",
             f"What was removed from the documents a blind second mapping of `{record['corpus']}` "
             f"is given, and why (docs/method.md, *Before the map is used*). Written by "
             f"`python3 tools/mapper stage`; the digests are in "
             f"[{RECORD_FILENAME}]({RECORD_FILENAME}).", "",
             "## What was staged", ""]
    for document in record["documents"]:
        lines.append(f"- `{document['name']}` from `{document['source']}` "
                     f"({document['sourceSha256'][:12]}…) -> `{document['sha256'][:12]}…`, "
                     f"{document['edits']} edit(s)")
    lines += ["", "## The vocabulary the scan used", "",
              "Every map of this corpus, the neighbouring slices included: a sibling slice's "
              "entry id is this corpus's vocabulary.", ""]
    for source in record["vocabularyFrom"]:
        lines.append(f"- `{source['path']}` ({source['entries']} entries)")
    lines += ["",
              f"{len(record['terms'][CERTAIN])} term(s) an occurrence of which fails a staging "
              f"(a hyphenated entry id, or the corpus id), "
              f"{len(record['terms'][POSSIBLE])} that raise a question (a one-word id, an entry "
              f"name, a word of the corpus id).",
              "", "## Content edits", ""]
    if applied:
        for edit in applied:
            lines.append(f"- `{edit['document']}` L{edit['line']}: {edit['why']}"
                         + (" (deleted)" if edit["deletes"] else ""))
    else:
        lines.append("None declared.")
    lines += ["", "## Links made plain text", "",
              "A markdown link to anything but a staged document became its link text: the mapper "
              "has none of those files, and a target is prose too.", ""]
    for target, count in sorted(links.items()):
        lines.append(f"- {target} ({count})")
    if not links:
        lines.append("None.")
    lines += ["", "## Named and left in", ""]
    if record["acknowledged"]:
        lines.append("Each of these is a word the document uses for its own reasons. The staging "
                     "says so, by document and term, and counts the occurrences, so one more is "
                     "a change:")
        lines.append("")
        for ack in record["acknowledged"]:
            lines.append(f"- `{ack['document']}` — `{ack['term']}` ×{ack['occurrences']}: "
                         f"{ack['reason']}")
    else:
        lines.append("Nothing.")
    if residue or unresolved:
        lines += ["", "## Left over — this staging is not blind", ""]
        for item in residue + unresolved:
            lines.append(f"- {item['class']}: `{item['document']}` L{item['line']} — "
                         f"`{item['term']}`")
    lines += ["", "## What this did not check", ""]
    for limit in LIMITS:
        lines.append(f"- {limit}")
    lines.append("")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return sha256_file(path)


# ---------------------------------------------------------------- verifying

def verify(record_path):
    """Hold a committed record to the files beside it. Returns (problems, notes, checked)."""
    record_path = os.path.abspath(record_path)
    base = os.path.dirname(record_path)
    record = _read_json(record_path, "staging record")
    if not isinstance(record, dict) or record.get("recordVersion") != RECORD_VERSION:
        raise Refused(f"{record_path}: recordVersion is "
                      f"{record.get('recordVersion') if isinstance(record, dict) else None!r}; "
                      f"this mapper verifies version {RECORD_VERSION}")
    problems, notes, checked = [], [], 0

    for named in [record.get("spec"), record.get("record")] + list(record.get("documents") or []):
        if not isinstance(named, dict):
            problems.append("a file this record names is not an object")
            continue
        relative = named.get("path") or named.get("name")
        expected = named.get("sha256")
        if not relative or not expected:
            problems.append(f"{relative!r} is recorded without a sha256")
            continue
        path = os.path.join(base, relative)
        if not os.path.isfile(path):
            problems.append(f"{relative}: recorded, and not here")
            continue
        got = sha256_file(path)
        checked += 1
        if got != expected:
            problems.append(f"{relative}: sha256 {got}, recorded {expected} -- the staged input "
                            f"is not the one this record covers")

    # The digests say the bytes did not move. The scan says the bytes were redacted, which is
    # the claim a blind run actually rests on, and is not a thing a digest can assert.
    terms = {term: CERTAIN for term in (record.get("terms") or {}).get(CERTAIN) or []}
    terms.update({term: POSSIBLE for term in (record.get("terms") or {}).get(POSSIBLE) or []
                  if term not in terms})
    if not terms:
        problems.append("this record carries no vocabulary, so re-scanning it would examine "
                        "nothing")
    acknowledged = {(a.get("document"), str(a.get("term", "")).lower()): a
                    for a in record.get("acknowledged") or [] if isinstance(a, dict)}
    counts = {}
    scanned = 0
    for document in record.get("documents") or []:
        path = os.path.join(base, document.get("name", ""))
        if not os.path.isfile(path):
            continue
        scanned += 1
        for term, weight, line in scan(_read_text(path, "staged document"), terms):
            key = (document["name"], term)
            if weight == CERTAIN:
                problems.append(f"{document['name']}:{line}: {term!r} is an id the corpus's maps "
                                f"coin; this staged document is not redacted")
            elif key in acknowledged:
                counts[key] = counts.get(key, 0) + 1
            else:
                problems.append(f"{document['name']}:{line}: {term!r} is named and neither "
                                f"redacted nor acknowledged")
    for key, ack in sorted(acknowledged.items()):
        if counts.get(key, 0) != ack.get("occurrences"):
            problems.append(f"{key[0]}: {key[1]!r} occurs {counts.get(key, 0)} time(s), "
                            f"acknowledged for {ack.get('occurrences')!r}")
    if scanned == 0:
        problems.append("no staged document was scanned -- this record proves nothing")

    for source in record.get("vocabularyFrom") or []:
        path = os.path.join(base, source.get("path", ""))
        if os.path.isfile(path) and sha256_file(path) != source.get("sha256"):
            notes.append(f"{source['path']} has changed since this staging; the vocabulary "
                         f"recorded here is the one the run was scanned against")
    return problems, notes, checked + scanned
