"""M5 of #3: the backlog -- one issue file per entry the engine still has to build.

docs/method.md, "Phase 5 -- Generate the backlog": each entry becomes one issue carrying its
scope, its source (the locator verbatim and the `evidence` it resolves to), its dependencies
(which order it), its reachability (`enabledBy` / `suspendedBy`, which order nothing), its
acceptance criteria and its required evidence (from `note`). The backlog is ordered by the
dependency graph, not by the corpus's page order.

**Which entries become items.** Read from the map merged with the engine's overlay:

  * `scope: in` -- an entry ruled out is a recorded verdict the engine already answers with
    `OutsideCurrentScope` (method.md, "In scope or out"); there is nothing to build;
  * `status: mapped` or `blocked` -- read, not built (corpus-map.md, `status`; correspondence
    row 2). `implemented` is built; `declined` is a recorded refusal;
  * no `definedElsewhere` and no `beyondAdapter` -- the corpus does not supply the fact to this
    engine (method.md, Phase 3, "Unsupplied by the corpus, or only to us?"), and the engine
    answers `MissingRulesData` until another source does. No issue can be closed from this
    corpus;
  * `derivedFrom` entries are items. A derived fact is one "the engine must give" (method.md,
    Phase 2, and 0012); it has no locator of its own, so its item's source is its sources'
    locators and evidence, verbatim.

**Order.** Topological over `dependsOn` on the whole map, ties broken by map order, then
filtered to items -- so an item follows every item it depends on even through an entry that is
not itself an item. File names are `NNN-<entry-id>.md`, NNN zero-padded (at least three
digits). The title is `<entry-id>: <name>`, which does not move when the order does -- but it
does move when the entry is renamed, so nothing keys on it.

**Identity.** Under the title, every item carries `<!-- rules-factory-entry: <entry-id> -->`
and `<!-- rules-factory-engine: <Name>; map: <package id> -->`. The entry id is the one thing
about an item the map never changes, so it is what ties a file to its issue: a title or a body
can change under it. The second marker says which engine and map made the issue, for a reader;
lookup does not use it, since an engine's issues live in that engine's repository.

**A licensed `local-copy` corpus quotes nothing (decision 0022).** When the context says the corpus
is `local-copy` (`localCopy`, set by `produce` from the manifest), an item carries the entry's id,
name, structural fields and locator citation, and never the corpus's words: `evidence`, the entry's
`note` and `ambiguity.question` (both may quote the corpus, and nothing measures how closely) are
each replaced by WITHHELD, which points at the citation in the operator's licensed copy.
`create` on an engine whose provenance.json records `licensedCopyException` refuses before any
write unless every body carries that replacement and none contains any of those strings from the
map package the provenance names (`quoted_strings`). A committed-copy corpus renders exactly as before.

**Quoted text carries the attribution its licence requires (decision 0023).** When the manifest
`licence` of the corpus is `<licence>. Attribution required: <statement>` (`attribution`; the SRD's),
`produce` puts `attribution` in the context, and every item, and the index, carries a "Corpus licence"
section: which corpus the quotations are from, its licence, a pointer to `LICENCE.txt` in the map
package, and the statement verbatim. A licence that mentions attribution or CC-BY in any other shape
is refused rather than rendered without it. A corpus whose licence requires no attribution (the
public-domain ones) renders nothing extra, so its backlog is byte-identical to before. `create`
reads the map package provenance.json records and refuses, before any call to `gh`, a body without
the statement (`check_bodies`). A local-copy corpus's items quote nothing, so carry no attribution.

Deterministic, standard library only. `emit` rewrites `backlog/` in full on every `produce`.
`create` synchronises the files with GitHub issues through `gh` -- see its docstring.
"""
import hashlib
import json
import os
import re
import subprocess

import generate
import intake

DIRECTORY = "backlog"
ITEM_FILE = re.compile(r"^\d{3,}-.+\.md$")
BUILDABLE = ("mapped", "blocked")
# Seconds one `gh` call may take. A hung call (an auth prompt, a stalled network) is a
# failure to report, not something to wait on forever (0016: every child process is bounded).
GH_TIMEOUT = 120
# Only as the first line of a body: a marker quoted further down (in evidence, or pasted into a
# comment on the issue) is text, not identity.
ENTRY_MARKER = re.compile(r"\A\s*<!-- rules-factory-entry: (\S+) -->[ \t]*\r?\n")
# `gh issue list` pages internally up to --limit; a result that reaches the limit may be cut
# short, and a missing issue would be created twice, so reaching it is a refusal.
LIST_LIMIT = 10000


class BacklogError(Exception):
    """The backlog cannot be written or created as asked."""


# --- selection and order -------------------------------------------------------------------


def disposition(entry):
    """None when the entry is a backlog item; otherwise why it is not."""
    if entry.get("scope") != "in":
        return "scope: out -- the engine answers OutsideCurrentScope"
    if "definedElsewhere" in entry:
        return "definedElsewhere -- the corpus does not supply the fact"
    if "beyondAdapter" in entry:
        return "beyondAdapter -- the fact is beyond this corpus's adapter"
    if entry.get("status") not in BUILDABLE:
        return f"status: {entry.get('status')}"
    return None


def order(entries):
    """Entries in dependsOn topological order, ties broken by map order. Refuses a cycle."""
    index = {e["id"]: i for i, e in enumerate(entries)}
    waiting = {}
    blocking = {e["id"]: [] for e in entries}
    for entry in entries:
        deps = [d for d in dict.fromkeys(entry.get("dependsOn") or [])]
        for dep in deps:
            if dep not in index:
                raise BacklogError(f"{entry['id']} dependsOn {dep!r}, which is not an entry in the map")
            blocking[dep].append(entry["id"])
        waiting[entry["id"]] = len(deps)
    ready = sorted(i for i, e in enumerate(entries) if waiting[e["id"]] == 0)
    result = []
    while ready:
        i = ready.pop(0)
        result.append(entries[i])
        for later in blocking[entries[i]["id"]]:
            waiting[later] -= 1
            if waiting[later] == 0:
                ready.append(index[later])
        ready.sort()
    if len(result) != len(entries):
        stuck = sorted((e["id"] for e in entries if waiting[e["id"]] > 0), key=index.get)
        raise BacklogError(f"dependsOn has a cycle among {stuck}")
    return result


def items(entries):
    """(file name, entry) for each backlog item, in backlog order."""
    chosen = [e for e in order(entries) if disposition(e) is None]
    width = max(3, len(str(len(chosen))))
    return [(f"{n:0{width}d}-{e['id']}.md", e) for n, e in enumerate(chosen, 1)]


# --- markdown ------------------------------------------------------------------------------


def fence(text):
    """A code fence holding `text` byte-for-byte: longer than any backtick run inside it."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    marker = "`" * max(3, longest + 1)
    return f"{marker}text\n{text}\n{marker}\n"


def title(entry):
    return f"{entry['id']}: {' '.join(str(entry.get('name') or entry['id']).split())}"


# Decision 0023: a corpus whose terms require attribution says so in its manifest `licence`, as
# `<licence>. Attribution required: <statement>` (the SRD's is the first). The statement is copied into
# every item verbatim; a licence that names attribution (or any CC-BY licence) in any other shape is
# refused, since the statement it needs cannot be found in it and must not be guessed.
ATTRIBUTION_REQUIRED = re.compile(r"\A(?P<terms>.*?)[\s.;:]*\bAttribution required:\s*(?P<statement>\S.*?)\s*\Z", re.S)
NAMES_ATTRIBUTION = re.compile(r"\bCC-BY\b|attribution", re.I)
ATTRIBUTION_HEADING = "## Corpus licence\n"


def attribution(corpus):
    """{sourceId, terms, statement} when the manifest corpus's `licence` requires attribution, else None.

    Refuses a corpus with no `licence` (whether its quotations need attribution is then unknown), and
    a licence that mentions attribution or CC-BY without an `Attribution required: <statement>`."""
    source_id = corpus.get("sourceId") if isinstance(corpus, dict) else None
    licence = corpus.get("licence") if isinstance(corpus, dict) else None
    if not isinstance(licence, str) or not licence.strip():
        raise BacklogError(f"the manifest gives {source_id!r} no `licence`, so whether the backlog's quotations of it "
                           f"must carry an attribution is unknown (decision 0023)")
    found = ATTRIBUTION_REQUIRED.match(licence)
    if found:
        return {"sourceId": source_id, "terms": found["terms"].strip() or licence.strip(),
                "statement": found["statement"]}
    if NAMES_ATTRIBUTION.search(licence):
        raise BacklogError(f"{source_id}'s manifest `licence` ({licence!r}) mentions attribution or a CC-BY licence but "
                           f"does not state it as `<licence>. Attribution required: <statement>`, so the backlog "
                           f"cannot carry the attribution its quotations need (decision 0023)")
    return None


def attribution_markdown(context):
    """The attribution section every item and the index carry for an attribution-requiring corpus; else ''."""
    credit = context.get("attribution")
    if not credit:
        return ""
    return (f"{ATTRIBUTION_HEADING}\n"
            f"Text quoted here from corpus `{credit['sourceId']}` (its evidence, and any note or question that "
            f"quotes it) is under the corpus's licence, {credit['terms']}, not this repository's. The full terms, "
            f"and what was changed, are in `LICENCE.txt` inside {context['package']} {context['version']} "
            "(rules-factory decision 0023). The attribution the licence requires, verbatim:\n\n"
            f"{credit['statement']}\n\n")


WITHHELD = ("*Withheld: the corpus is a licensed `local-copy` corpus, so no text quoted from it or "
            "paraphrased from it is written here (rules-factory decision 0022). Read the passage at the "
            "citation in your licensed copy.*\n")


def _source(entry, withhold=False):
    locator = entry["locator"]
    head = (f"Locator, `sourceId` {json.dumps(locator.get('sourceId'), ensure_ascii=False)}; citation:\n\n"
            f"{fence(locator['citation'])}\n")
    if withhold:
        return head + f"Evidence:\n\n{WITHHELD}"
    return head + f"Evidence, verbatim:\n\n{fence(entry['evidence'])}"


def _relation(ids, files, by_id):
    if not ids:
        return "- none\n"
    lines = []
    for other in ids:
        if other in files:
            lines.append(f"- [`{other}`]({files[other]})\n")
        else:
            why = disposition(by_id[other]) if other in by_id else "not an entry in the map"
            lines.append(f"- `{other}` -- no backlog item ({why or 'status: ' + str(by_id[other].get('status'))})\n")
    return "".join(lines)


def _criteria(entry, by_id):
    eid = entry["id"]
    out = []
    kind = entry.get("kind")
    if kind == "value":
        out.append("The engine states this value as the evidence prints it -- every figure and unit, "
                   "and where the corpus prints a finite table, the whole table.")
    elif kind == "assertion":
        out.append("The engine demands this fact of the caller rather than deciding it; "
                   "what the caller states is what the engine evaluates.")
    else:
        out.append("The engine performs the operation the evidence states, observable through its public API, "
                   "on each situation the required evidence names.")
    if entry.get("derivedFrom"):
        out.append("The tests show the fact as it follows from "
                   + ", ".join(f"`{s}`" for s in entry["derivedFrom"])
                   + "; it is not carried inside a source entry's handler.")
    enablers = entry.get("enabledBy") or []
    if enablers:
        named = " or ".join(f"`{gate}`" for gate in enablers)
        out.append(f"Every test of the rule sets up a state in which {named} holds, and a test shows the "
                   "rule does not apply where none of them holds.")
    for gate in entry.get("suspendedBy") or []:
        out.append(f"A test shows the rule does not apply while `{gate}` holds.")
    ambiguity = entry.get("ambiguity")
    if isinstance(ambiguity, dict):
        if ambiguity.get("fate") == "unresolved":
            reason = ambiguity.get("unresolvedReason") or "RequiresInterpretation"
            out.append(f"Where the answer turns on the question above, the engine declines with `{reason}` "
                       "citing this entry's locator; it does not choose a reading.")
        elif ambiguity.get("fate") == "decision":
            out.append(f"The engine follows the recorded decision `{ambiguity.get('decision')}`, "
                       "and a test goes red under the reading it rejected.")
    out.append(f"A hand-written handler implements `Handlers.{generate.pascal(eid)}`, the partial method "
               "`Generated/Contracts.g.cs` declares for this entry, with exactly its signature: once the entry "
               "is `implemented`, a missing or mis-typed handler does not build (#76).")
    out.append(f"`corpus-map.overlay.json` sets `{eid}` to `status: implemented`, with `implementedIn` "
               "and `tests`: every test named with its recorded `mutation` -- the change to the engine "
               "that turned that test red.")
    out.append("After `factory produce` regenerates with that overlay, the generated correspondence tests "
               "stay green (`dotnet test`).")
    return "".join(f"- [ ] {line}\n" for line in out)


def markers(entry, context):
    """The HTML comments that identify an item's issue; invisible when GitHub renders it."""
    return (f"<!-- rules-factory-entry: {entry['id']} -->\n"
            f"<!-- rules-factory-engine: {context['name']}; map: {context['package']} -->\n")


def item_markdown(position, total, file_name, entry, files, by_id, context):
    eid = entry["id"]
    withhold = bool(context.get("localCopy"))
    parts = [f"# {title(entry)}\n\n", markers(entry, context), "\n",
             f"Backlog item {position} of {total} for {context['name']}, from {context['package']} "
             f"{context['version']}. Generated by `factory produce` from the map merged with "
             "`corpus-map.overlay.json`; change those, not this file.\n\n",
             attribution_markdown(context),
             "## Entry\n\n",
             f"- id: `{eid}`\n- kind: `{entry.get('kind')}`\n- clarity: `{entry.get('clarity')}`\n"
             f"- status: `{entry.get('status')}`\n\n",
             "## Source\n\n"]
    if entry.get("derivedFrom"):
        parts.append("Derived (0012): no sentence states this fact, so it has no locator of its own. "
                     "Its sources' citations are its citation.\n\n")
        for source in entry["derivedFrom"]:
            parts.append(f"### From `{source}`\n\n{_source(by_id[source], withhold)}\n")
    else:
        parts.append(_source(entry, withhold) + "\n")
    ambiguity = entry.get("ambiguity")
    if isinstance(ambiguity, dict):
        parts.append(f"## Ambiguity\n\nFate: `{ambiguity.get('fate')}`")
        for key in ("unresolvedReason", "decision", "conflict"):
            if key in ambiguity:
                parts.append(f"; {key}: `{ambiguity[key]}`")
        parts.append(f".\n\n{WITHHELD if withhold else fence(str(ambiguity.get('question', '')))}\n")
    parts.append("## Dependencies\n\n`dependsOn` -- built before this item:\n\n"
                 + _relation(entry.get("dependsOn") or [], files, by_id) + "\n")
    parts.append("## Reachability\n\n`enabledBy` -- what the tests must set up:\n\n"
                 + _relation(entry.get("enabledBy") or [], files, by_id)
                 + "\n`suspendedBy` -- what the tests must show does not happen:\n\n"
                 + _relation(entry.get("suspendedBy") or [], files, by_id) + "\n")
    parts.append("## Acceptance criteria\n\n" + _criteria(entry, by_id) + "\n")
    if withhold:
        parts.append("## Required evidence\n\nThe entry's `note`:\n\n" + WITHHELD)
    else:
        parts.append("## Required evidence\n\nFrom the entry's `note`:\n\n" + fence(str(entry.get("note", ""))))
    return "".join(parts)


def render(entries, context):
    """{relative path under backlog/: text} for the merged entries."""
    listed = items(entries)
    files = {e["id"]: name for name, e in listed}
    by_id = {e["id"]: e for e in entries}
    out = {}
    index = [f"# Backlog for {context['name']}\n\n",
             f"{len(listed)} item(s) from {context['package']} {context['version']}, in build order "
             "(dependsOn, ties by map order). An entry is an item when it is `scope: in`, "
             "`status: mapped` or `blocked`, and neither `definedElsewhere` nor `beyondAdapter`; "
             "derived entries are items. Generated by `factory produce`.\n\n"]
    for position, (name, entry) in enumerate(listed, 1):
        out[name] = item_markdown(position, len(listed), name, entry, files, by_id, context)
        index.append(f"{position}. [{title(entry)}]({name})\n")
    skipped = [e for e in entries if disposition(e) is not None]
    if skipped:
        index.append("\nNot in the backlog:\n\n")
        index.extend(f"- `{e['id']}` -- {disposition(e)}\n" for e in skipped)
    if context.get("attribution"):
        index.append("\n" + attribution_markdown(context).rstrip("\n") + "\n")
    out["README.md"] = "".join(index)
    return out


def emit(entries, context, out):
    """Rewrite `<out>/backlog/` from the merged entries; returns the relative paths written."""
    directory = os.path.join(out, DIRECTORY)
    rendered = render(entries, context)
    os.makedirs(directory, exist_ok=True)
    for name in sorted(os.listdir(directory)):
        if (ITEM_FILE.match(name) or name == "README.md") and name not in rendered:
            os.remove(os.path.join(directory, name))
    for name in sorted(rendered):
        with open(os.path.join(directory, name), "wb") as handle:
            handle.write(rendered[name].encode("utf-8"))
    return [f"{DIRECTORY}/{name}" for name in rendered]


# --- GitHub issues -------------------------------------------------------------------------


def _gh(args, gh, stdin=None):
    try:
        done = subprocess.run([gh] + args, input=stdin, capture_output=True, text=True, timeout=GH_TIMEOUT)
    except OSError as error:
        raise BacklogError(f"cannot run {gh}: {error}")
    except subprocess.TimeoutExpired:
        raise BacklogError(f"`gh {' '.join(args[:2])}` did not finish in {GH_TIMEOUT} seconds")
    if done.returncode != 0:
        raise BacklogError(f"`gh {' '.join(args[:2])}` failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def _normal(text):
    """A body as compared: GitHub may hand back CRLF line ends and trims the ends of a body."""
    return text.replace("\r\n", "\n").strip()


def entry_of(body):
    """The entry id a body's leading marker names, or None."""
    found = ENTRY_MARKER.match(body)
    return found.group(1) if found else None


def _read_items(directory, names):
    """[(file name, entry id, title, body)] from the backlog files, refusing one without a marker."""
    out, seen = [], {}
    for name in names:
        with open(os.path.join(directory, name), encoding="utf-8") as handle:
            first, _, body = handle.read().partition("\n")
        if not first.startswith("# "):
            raise BacklogError(f"{name} does not begin with a `# ` title line")
        eid = entry_of(body)
        if eid is None:
            raise BacklogError(f"{name} does not carry a rules-factory-entry marker under its title; "
                               "run `factory produce` again")
        if eid in seen:
            raise BacklogError(f"{seen[eid]} and {name} are both entry {eid!r}")
        seen[eid] = name
        out.append((name, eid, first[2:], body.lstrip("\n")))
    return out


def _issues(repo, gh):
    listed = _gh(["issue", "list", "--repo", repo, "--state", "all", "--limit", str(LIST_LIMIT),
                  "--json", "number,title,body"], gh)
    try:
        issues = [{"number": int(i["number"]), "title": i["title"], "body": i.get("body") or ""}
                  for i in json.loads(listed or "[]")]
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise BacklogError(f"cannot read `gh issue list` output: {error}")
    if len(issues) >= LIST_LIMIT:
        raise BacklogError(f"{repo} has at least {LIST_LIMIT} issues, the most `gh issue list` is asked "
                           "for; an issue beyond them would be created again")
    return issues


# Shorter normalised strings are not compared: a two-word evidence span would match ordinary prose.
QUOTE_MINIMUM = 12


def _normalised(text):
    return " ".join(str(text).split())


def quoted_strings(document):
    """Every string in the map that holds or may paraphrase corpus text: evidence, note, ambiguity.question."""
    found = set()
    for entry in document.get("entries") or [] if isinstance(document, dict) else []:
        if not isinstance(entry, dict):
            continue
        ambiguity = entry.get("ambiguity") if isinstance(entry.get("ambiguity"), dict) else {}
        for text in (entry.get("evidence"), entry.get("note"), ambiguity.get("question")):
            if isinstance(text, str) and len(_normalised(text)) >= QUOTE_MINIMUM:
                found.add(_normalised(text))
    return sorted(found)


def _recorded_package(record, package, why):
    """(package parts, the manifest corpus the map cites) for the map package provenance.json records.

    Read from `package` (a .nupkg path or Id@Version) or else Id@Version from provenance.json, taken
    from a file or the NuGet global packages folder and never downloaded (a local-copy map is never
    published), and refused unless its map and manifest are the ones provenance hashed."""
    source = record.get("map") or {}
    spec = package or f"{source.get('packageId')}@{source.get('version')}"
    if os.path.isfile(spec):
        nupkg = spec
    else:
        match = intake.PACKAGE_REF.match(spec)
        lower = (match["id"].lower(), match["version"].lower()) if match else None
        nupkg = (os.path.join(intake._global_packages_folder(), lower[0], lower[1], f"{lower[0]}.{lower[1]}.nupkg")
                 if lower else "")
        if not os.path.isfile(nupkg):
            raise BacklogError(f"{why}, and its map package {spec} is not a local file or in the NuGet global "
                               f"packages folder, so the issue bodies cannot be checked; pass --package")
    try:
        _, _, parts = intake.read_package(nupkg)
    except (intake.Refused, intake.Usage) as error:
        raise BacklogError(f"cannot read the map package {nupkg}: {error}")
    recorded = {f.get("role"): f.get("sha256") for f in source.get("files") or [] if isinstance(f, dict)}
    for role in ("map", "manifest"):
        if hashlib.sha256(parts[role][1]).hexdigest() != recorded.get(role):
            raise BacklogError(f"{nupkg}'s {role} is not the {role} provenance.json records, so it cannot say what "
                               f"the issue bodies must or must not carry")
    try:
        document = json.loads(parts["map"][1].decode("utf-8"))
        manifest = json.loads(parts["manifest"][1].decode("utf-8"))
        cited = document.get("corpus")
        (corpus,) = [c for c in manifest.get("corpora") or [] if isinstance(c, dict) and c.get("sourceId") == cited]
    except (ValueError, AttributeError) as error:
        raise BacklogError(f"cannot read which corpus {nupkg}'s map cites from its manifest: {error}")
    return parts, corpus


def check_bodies(engine_dir, files, package=None):
    """Before anything is sent to GitHub, what the corpus's terms demand of every body.

    Decision 0023: when the manifest `licence` of the corpus the map cites requires attribution
    (`attribution`), every body must carry its statement verbatim, since a body quotes the corpus.
    Decision 0022: for an engine whose provenance.json records `licensedCopyException`, every body must
    carry WITHHELD and contain none of `quoted_strings` (and quotes nothing, so needs no attribution).

    Both read the map package provenance.json records (`_recorded_package`), so for any engine with a
    provenance.json that package must be at hand: whether a body needs an attribution is the package's
    to say, not the body's. Without provenance.json nothing says which corpus the backlog is of; a body
    carrying either notice is then refused, and any other is not checked. Returns log lines."""
    path = os.path.join(engine_dir, "provenance.json")
    if not os.path.exists(path):
        if any(WITHHELD.strip() in body for _, _, _, body in files):
            raise BacklogError(f"the backlog withholds a licensed corpus's text (0022) and {path} is missing, so "
                               f"what it must not quote cannot be checked; run `factory produce` again")
        if any(ATTRIBUTION_HEADING in body for _, _, _, body in files):
            raise BacklogError(f"the backlog attributes a corpus's text (0023) and {path} is missing, so the "
                               f"attribution its licence requires cannot be checked; run `factory produce` again")
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError) as error:
        raise BacklogError(f"cannot read {engine_dir}/provenance.json, so the corpus's terms are unknown: {error}")
    if not isinstance(record, dict):
        raise BacklogError(f"{engine_dir}/provenance.json is not a JSON object, so the corpus's terms are unknown")
    if "licensedCopyException" not in record:
        _, corpus = _recorded_package(record, package,
                                      "whether the corpus's licence requires attribution is its map package's to say (0023)")
        credit = attribution(corpus)
        if not credit:
            return []
        missing = [name for name, _, _, body in files if credit["statement"] not in body]
        if missing:
            raise BacklogError(f"{credit['sourceId']}'s licence ({credit['terms']}) requires attribution (0023), and "
                               f"{len(missing)} issue body(ies) do not carry its statement verbatim: "
                               f"{'; '.join(missing)}. Run `factory produce` again. Nothing was sent to GitHub")
        return [f"--- backlog: {len(files)} bodies carry the attribution {credit['sourceId']}'s licence "
                f"({credit['terms']}) requires (0023)"]
    parts, _ = _recorded_package(record, package,
                                 "the engine was produced from a licensed local-copy corpus (0022)")
    strings = quoted_strings(json.loads(parts["map"][1].decode("utf-8")))
    leaking = []
    for name, _, _, body in files:
        flat = _normalised(body)
        if WITHHELD.strip() not in body:
            leaking.append(f"{name} (it does not carry the withheld notice; run `factory produce` again)")
        elif any(text in flat for text in strings):
            leaking.append(f"{name} (it contains text the map quotes or paraphrases from the corpus)")
    if leaking:
        raise BacklogError("the engine was produced from a licensed local-copy corpus (0022), and no issue may "
                           "carry its text: " + "; ".join(leaking) + ". Nothing was sent to GitHub")
    return [f"--- backlog: licensed local-copy corpus (0022): {len(files)} bodies carry no text from the "
            f"corpus ({len(strings)} quoted strings of the map compared)"]


def create(repo, engine_dir, log, gh="gh", package=None):
    """Synchronise the repository's issues with the backlog files, in build order.

    Every issue, open or closed, is read once, and each file is matched to an issue by the
    rules-factory-entry marker that begins both -- never by title, which a rename changes. Per file the outcome
    is `created` (no issue carries the marker), `updated` (one does, and its title or body
    differs from the file: `gh issue edit`) or `unchanged`. An issue with no marker whose title
    is exactly the file's title was made before markers existed; it is `adopted` -- edited to
    carry the marker -- rather than duplicated. So a second run in a row writes nothing.

    Everything is decided before the first write. The same entry marker on two issues, or two
    unmarked issues with an adoptable title, is a refusal naming them: which one is the item
    is not the factory's to guess. An issue whose entry is no longer in the backlog (built,
    ruled out, or gone from the map) is reported and left alone; closing it is a person's
    decision.

    Returns ({outcome: count}, [numbers of issues not in the backlog]).
    """
    directory = os.path.join(engine_dir, DIRECTORY)
    if not os.path.isdir(directory):
        raise BacklogError(f"{directory} does not exist; run `factory produce` first")
    names = sorted(n for n in os.listdir(directory) if ITEM_FILE.match(n))
    if not names:
        raise BacklogError(f"{directory} has no backlog items -- nothing to create")
    files = _read_items(directory, names)
    for line in check_bodies(engine_dir, files, package):
        print(line, file=log)
    issues = _issues(repo, gh)

    by_marker, unmarked = {}, {}
    for issue in issues:
        eid = entry_of(issue["body"])
        if eid:
            by_marker.setdefault(eid, []).append(issue)
        else:
            unmarked.setdefault(issue["title"], []).append(issue)
    conflicts = [f"{eid} on " + ", ".join(f"#{i['number']}" for i in found)
                 for eid, found in sorted(by_marker.items()) if len(found) > 1]
    if conflicts:
        raise BacklogError("the same rules-factory-entry marker is on more than one issue: "
                           + "; ".join(conflicts))

    plan = []
    for name, eid, issue_title, body in files:
        found = by_marker.get(eid)
        if found:
            issue = found[0]
            same = issue["title"] == issue_title and _normal(issue["body"]) == _normal(body)
            action = "unchanged" if same else "updated"
        else:
            legacy = unmarked.get(issue_title) or []
            if len(legacy) > 1:
                raise BacklogError(f"{name}: no issue carries its marker, and several have its title: "
                                   + ", ".join(f"#{i['number']}" for i in legacy))
            issue = legacy[0] if legacy else None
            action = "adopted" if issue else "created"
        plan.append((action, issue, issue_title, body))

    counts = {"created": 0, "updated": 0, "adopted": 0, "unchanged": 0}
    for action, issue, issue_title, body in plan:
        if action == "created":
            _gh(["issue", "create", "--repo", repo, "--title", issue_title, "--body-file", "-"], gh, stdin=body)
            print(f"created   {issue_title}", file=log)
        elif action in ("updated", "adopted"):
            _gh(["issue", "edit", str(issue["number"]), "--repo", repo, "--title", issue_title,
                 "--body-file", "-"], gh, stdin=body)
            print(f"{action:<9} #{issue['number']} {issue_title}", file=log)
        else:
            print(f"unchanged #{issue['number']} {issue_title}", file=log)
        counts[action] += 1

    current = {eid for _, eid, _, _ in files}
    orphans = sorted((i for eid, found in by_marker.items() if eid not in current for i in found),
                     key=lambda i: i["number"])
    for issue in orphans:
        print(f"not in backlog #{issue['number']} {issue['title']} -- left as it is", file=log)
    print(f"--- backlog: {counts['created']} created, {counts['updated']} updated, "
          f"{counts['adopted']} adopted, {counts['unchanged']} unchanged, "
          f"{len(orphans)} not in the backlog", file=log)
    return counts, [i["number"] for i in orphans]
