"""What a produced engine's records say about each of its rules, and what they do not say (#576).

  python3 tools/factory trace --engine <engine dir> --json [--package <nupkg path | Id@Version>]

An engine already holds every fact this reports. `provenance.json` names the map packages, the
corpora, the kernel and where the engine sits in its repository. The map package gives each entry
its locator. `overlay/<entry id>.json` gives each entry its status, the tests it names and the
mutation each test was watched catching. What nothing showed was how those records join up per
entry, and which of the joins no record makes. That is all this module does. It adds no fact and
writes nothing: the trace is a reading of artifacts that already have owners, computed again on
every run, so a changed overlay or a re-produced engine is reflected the next time it is asked.

**Every relationship carries its evidence class**, because a reader who cannot tell a recorded
fact from a guess will act on the guess:

  * `recorded` -- an existing artifact states it. `basis` names the artifact and the field.
  * `derived` -- it follows from recorded facts through a reader the factory already has, with no
    choice made by heuristic. `basis` names the reader.
  * `inferred` -- deterministic analysis suggests it, and nothing records it. `mechanism` names
    the analysis.
  * `unknown` -- nothing establishes it. `why` says what was tried and why it failed, and the same
    relationship is listed under `gaps`. Unknown is never promoted to inferred, and inferred is
    never promoted to recorded.

**Entry -> handler is derived; handler -> file is inferred (#582).** The generator binds every
entry to a handler on the generated `Handlers` class (contracts.py): an implemented entry off
correspondence row 8 gets a *required* partial method the engine does not build without (CS8795),
and every other entry an optional hook. So `handler` is derived through the generator's own model
and contract (`semantics.Model`, `semantics.contract`), and the rule is stated nowhere here. Which
file writes that handler is recorded nowhere -- the overlay's `implementedIn` is `{ruleset,
version}` in every engine the factory has produced, which ruleset the entry was implemented
against, not where -- so the files are found by the review model's own lexical analysis
(reviewscope.py): the hand-written file whose partial `Handlers` writes the handler, and the files
that name the entry's member, its request type or its id. That is evidence of where to look, not a
binding, and it is labelled inferred. Whether the current tree builds is not the trace's to say.

**A locator is not resolved to corpus text.** Which component resolves a citation to the exact
bytes it names is not settled, and a trace that resolved it would settle it by accident. So the
locator is reported as the map records it, the corpus it names is matched against provenance's
corpora, and the segment is `unknown`.

**The trace is as private as the engine.** It never emits a map entry's `evidence`, which is the
quotation itself. But entry names, locators and mutations are the map's and the engine's own words,
and those words quote the corpus: in a licensed engine, half the mutations carry a run of ten words
or more straight from it. So the trace reports the engine's recorded `distribution` (`engine.distribution`), and a
trace of a private engine goes only where the engine's own files may go (0068). Hashing those fields
would make the trace safe to publish and useless to read. The rule is the one the backlog already
follows: `factory backlog --create` refuses to file a private engine's items anywhere public.

**Readers, not parsers.** The map packages are read by `backlog.recorded_packages`, which refuses
a package whose map and manifest are not the bytes provenance hashed; several are composed by
`compose.union`; the overlay is read by `overlay.load` and merged by `semantics.merge`, so a
trace sees exactly the merge the engine's gate and generator see. The topology is
`repository.from_record` against `repository.git_root`. Where the supplied directory and the
recorded `enginePath` disagree, both are reported and the disagreement is a gap: nothing is
corrected.

Deterministic for the same bytes: entries in map order, tests in overlay order, files in byte
order of path, no clock, no absolute path. Paths are engine-relative; `topology` says where the
engine sits under its repository root. Standard library only.
"""
import json
import os
import re
import types

import backlog as backlog_step
import compose
import overlay as overlay_step
import provenance
import repository as repository_step
import reviewscope
import semantics

FORMAT = 1
CLASSES = ("recorded", "derived", "inferred", "unknown")

#: The generated class every entry's handler is a partial method of (contracts.py). A hand-written
#: file that declares a member of it is where that entry's handler is written.
HANDLERS = "Handlers"

SEGMENT_WHY = ("the trace reports a locator as the map records it and does not resolve it to corpus text: "
               "which component resolves a citation to the bytes it names is not settled, and the trace "
               "does not settle it")


class TraceError(Exception):
    """The directory cannot be traced: it is not a produced engine, or its inputs cannot be read.

    A refusal, not a gap. A gap is a relationship an engine's records do not establish; this is a
    record that is not there to be read, which no trace of it could be truthful about.
    """


def recorded(value, basis):
    return {"value": value, "evidence": "recorded", "basis": basis}


def derived(value, basis):
    return {"value": value, "evidence": "derived", "basis": basis}


def inferred(value, mechanism):
    return {"value": value, "evidence": "inferred", "mechanism": mechanism}


def unknown(why):
    return {"value": None, "evidence": "unknown", "why": why}


def _gap(subject, relationship, why):
    return {"subject": subject, "relationship": relationship, "why": why}


def read_record(engine_dir):
    """The engine's provenance.json as an object, or a refusal naming what is wrong with it."""
    path = os.path.join(engine_dir, provenance.FILE_NAME)
    if not os.path.isfile(path):
        raise TraceError(f"{engine_dir} has no {provenance.FILE_NAME}, so it is not a directory `factory "
                         f"produce` wrote and nothing records what it was built from; pass the engine "
                         f"directory itself, which for an embedded engine is below its repository root")
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError) as error:
        raise TraceError(f"cannot read {provenance.FILE_NAME}: {error}")
    if not isinstance(record, dict):
        raise TraceError(f"{provenance.FILE_NAME} is not a JSON object")
    return record


def topology(engine_dir, record, gaps):
    """Where the record says the engine is, where git says it is, and whether they agree."""
    section = record.get("repository")
    if isinstance(section, dict) and "enginePath" in section:
        said = recorded(repository_step.from_record(record).engine_path, "provenance.json repository.enginePath")
    elif isinstance(section, dict):
        said = unknown("provenance.json has a repository section with no enginePath, so nothing says where the "
                       "engine sits under its repository root")
        gaps.append(_gap("engine", "engine -> recorded enginePath", said["why"]))
    else:
        said = derived(None, "provenance.json has no repository section (a record before format 9); "
                             "repository.from_record reads that as an engine that is its own repository root")
    top = repository_step.git_root(engine_dir)
    if top is None:
        seen = unknown("the engine directory is in no git work tree, so nothing says where its repository root is")
        gaps.append(_gap("engine", "engine -> repository root", seen["why"]))
        agrees = None
    else:
        seen = derived(repository_step.under(top, engine_dir) or None,
                       "git rev-parse --show-toplevel (repository.git_root), relative to the engine directory")
        agrees = None if said["evidence"] == "unknown" else seen["value"] == said["value"]
        if agrees is False:
            gaps.append(_gap("engine", "engine -> repository root",
                             f"provenance.json records enginePath {said['value']!r} and the directory traced is at "
                             f"{seen['value']!r} under its repository root; the trace reports both and corrects "
                             f"neither"))
    return {"recordedEnginePath": said, "observedEnginePath": seen, "agrees": agrees}


def engine_facts(record, gaps):
    def field(path):
        value = record
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value is not None:
            return recorded(value, f"provenance.json {path}")
        fact = unknown(f"provenance.json records no {path}")
        gaps.append(_gap("engine", f"engine -> {path}", fact["why"]))
        return fact
    return {"name": field("engine.name"), "distribution": field("distribution"),
            "provenanceFormat": field("provenanceFormat"),
            "kernel": {"packageId": field("kernel.packageId"), "version": field("kernel.version")},
            "factory": {"version": field("factory.version"), "commit": field("factory.commit")}}


def read_maps(record, package):
    """[(package id, map document, manifest document)] for every map the record names."""
    try:
        read = backlog_step.recorded_packages(record, package, "the map an engine's entries are traced from",
                                              consequence="the entries cannot be traced")
    except backlog_step.BacklogError as error:
        raise TraceError(str(error))
    found = []
    for package_id, parts, _ in read:
        try:
            found.append((package_id, json.loads(parts["map"][1].decode("utf-8")),
                          json.loads(parts["manifest"][1].decode("utf-8"))))
        except (ValueError, UnicodeDecodeError) as error:
            raise TraceError(f"the map package {package_id} does not hold readable JSON: {error}")
    return found


def held(document, key, basis, subject, gaps):
    """`document[key]` as recorded, or unknown and a gap when the record does not hold it."""
    if isinstance(document, dict) and document.get(key) is not None:
        return recorded(document[key], basis)
    fact = unknown(f"{basis} is not recorded")
    gaps.append(_gap(subject, f"{subject} -> {key}", fact["why"]))
    return fact


def maps_section(record, documents, gaps):
    """Each map package: its identity as provenance records it, and the corpora its manifest pins."""
    sources = [m for m in record.get("maps") or [] if isinstance(m, dict)]
    out = []
    for position, (source, (package_id, document, manifest)) in enumerate(zip(sources, documents)):
        at = f"provenance.json maps[{position}]"
        subject = f"map:{package_id}"
        cites = [c.get("sourceId") for c in manifest.get("corpora") or [] if isinstance(c, dict)]
        files = held(source, "files", f"{at}.files", subject, gaps)
        if files["evidence"] == "recorded":
            files["value"] = [{k: f.get(k) for k in ("role", "path", "sha256")}
                              for f in files["value"] if isinstance(f, dict)]
        out.append({
            "packageId": recorded(package_id, f"{at}.packageId"),
            "version": held(source, "version", f"{at}.version", subject, gaps),
            "nupkgSha256": held(source, "nupkgSha256", f"{at}.nupkgSha256", subject, gaps),
            "files": files,
            "principalCorpus": recorded(document.get("corpus"), f"{package_id} map/corpus-map.json corpus"),
            "corpora": recorded(cites, f"{package_id} map/corpus-manifest.json corpora[].sourceId"),
        })
    return out


def corpora_section(record):
    out = []
    for position, corpus in enumerate(c for c in record.get("corpora") or [] if isinstance(c, dict)):
        at = f"provenance.json corpora[{position}]"
        out.append({key: recorded(corpus.get(key), f"{at}.{key}")
                    for key in ("sourceId", "contentHash", "hashDerivation", "asOf", "path", "principal")
                    if key in corpus})
    return out


def compose_maps(documents):
    """The engine's map as the factory composed it, and which package each entry id came from."""
    pairs = [(package_id, document) for package_id, document, _ in documents]
    try:
        document = compose.union(pairs)
    except compose.Refused as error:
        raise TraceError(f"the map packages this engine records do not compose: {error}")
    origin = {}
    for package_id, one in pairs:
        named = one if len(pairs) == 1 else compose.namespaced(one, package_id)
        held_ids = [e.get("id") if isinstance(e, dict) else None for e in one.get("entries") or []]
        for entry, own in zip(named.get("entries") or [], held_ids):
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                origin[entry["id"]] = (package_id, own)
    return document, origin


def implementation_files(engine_dir, gaps):
    """{engine-relative path: bytes} of the hand-written C# under src/, build output pruned.

    A file that cannot be read is a gap, not a refusal: every other inference still stands, and
    the gap says which file it could not see.
    """
    root = os.path.join(engine_dir, "src")
    found = {}
    for directory, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in provenance.SKIP_DIRS)
        for name in names:
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, engine_dir).replace(os.sep, "/")
            if reviewscope.classify(relative) == "implementation" and os.path.isfile(path):
                try:
                    with open(path, "rb") as handle:
                        found[relative] = handle.read()
                except OSError as error:
                    gaps.append(_gap("engine", "engine -> implementation files",
                                     f"{relative} could not be read ({error.strerror}), so no entry's "
                                     f"implementation was inferred from it"))
    return dict(sorted(found.items(), key=lambda item: item[0].encode("utf-8")))


#: The two handler shapes the generator declares (contracts.py), as the hand-written half writes them:
#: `partial Resolution<TOutput> {Member}(` for an implemented entry, `partial void {Member}(` for the
#: optional hook every other entry gets. Matched on the text with its literals and comments blanked.
HANDLER_SIGNATURE = re.compile(r"\bpartial\s+(?:Resolution\s*<[^(){};]*>|void)\s+@?([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def handler_files(files):
    """{member name: sorted paths} of the files that write an entry's generated handler.

    A file qualifies when `reviewscope.partial_members` finds it declaring the partial `Handlers`,
    and the member is one it declares with the generator's own handler signature. Both, because
    `partial_members` answers for the file and not for one type in it: an engine's handler file
    also extends the entry's partial request type with the inputs it reads (#93), and a member of
    that type is not a handler.
    """
    found = {}
    for path, data in files.items():
        text = data.decode("utf-8", "replace")
        types, members = reviewscope.partial_members(text)
        if HANDLERS not in types:
            continue
        for member in sorted(members & set(HANDLER_SIGNATURE.findall(reviewscope.blank_literals(text)))):
            found.setdefault(member, []).append(path)
    return found


HANDLER_MECHANISM = (f"reviewscope.partial_members and the generated handler signature (contracts.py): a "
                     f"hand-written file under src/ that declares the partial {HANDLERS} and writes "
                     f"`partial Resolution<...> <Member>(` or `partial void <Member>(` for the entry's member "
                     f"(the member semantics.Model gives the entry)")
REFERENCE_MECHANISM = ("reviewscope.entry_references: a hand-written file under src/ that names the entry's "
                       "member, its request type, or its id as a string literal")


def implementation(entry_id, member, handlers, references):
    candidates = [inferred({"path": path, "symbol": f"{HANDLERS}.{member}"}, HANDLER_MECHANISM)
                  for path in handlers.get(member, [])]
    declaring = {c["value"]["path"] for c in candidates}
    candidates += [inferred({"path": path, "symbol": None}, REFERENCE_MECHANISM)
                   for path, reached in references.items() if entry_id in reached and path not in declaring]
    return candidates


def generator_model(record, merged, documents):
    """The generator's own model of the merged map, for the two facts the trace takes from it.

    `semantics.Model` reads six attributes of an intake, duck-typed. The trace has no intake --
    it reads a produced engine, not a package being produced -- so it hands in the package ids and
    versions provenance recorded and nothing else; the members and correspondence rows the model
    computes depend on the merged map alone.
    """
    sources = [m for m in record.get("maps") or [] if isinstance(m, dict)]
    packages = [types.SimpleNamespace(package_id=package_id, version=str(source.get("version")))
                for (package_id, _, _), source in zip(documents, sources)]
    name = (record.get("engine") or {}).get("name") if isinstance(record.get("engine"), dict) else None
    try:
        return semantics.Model(types.SimpleNamespace(packages=packages, superseded={}, randomness=None), merged,
                               str(name or "Engine"))
    except (semantics.GenerationError, KeyError, TypeError) as error:
        raise TraceError(f"the generator cannot model this engine's merged map, so no handler can be derived: {error}")


HANDLER_BASIS = ("semantics.contract over semantics.Model: the generated Handlers class declares this member for "
                 "the entry (contracts.py); required means the entry is implemented and off correspondence row 8, "
                 "so the engine does not build without it, and otherwise it is an optional hook")


def entry_trace(entry, origin, item, corpora, handlers, references, single, gaps, generated):
    entry_id = entry["id"]
    package_id, own_id = origin.get(entry_id, (None, entry_id))
    in_map = f"{package_id} map/corpus-map.json entries[{own_id!r}]"
    overlay_path = overlay_step.path_for(entry_id)
    subject = f"entry:{entry_id}"
    out = {
        "id": (recorded(entry_id, f"{in_map}.id") if single else
               derived(entry_id, "compose.union: the map's entry id qualified by its package (0067)")),
        "package": (recorded(package_id, "provenance.json maps[0].packageId, the one map package, whose "
                                         "map/corpus-map.json holds the entry") if single else
                    derived(package_id, f"compose.namespaced: provenance.json maps[].packageId of the package whose "
                                        f"map holds the entry as {own_id!r}")),
        "name": recorded(entry.get("name"), f"{in_map}.name"),
    }
    locator = entry.get("locator") if isinstance(entry.get("locator"), dict) else None
    if locator is None:
        out["locator"] = unknown("the map entry has no locator")
        gaps.append(_gap(subject, "entry -> locator", out["locator"]["why"]))
    else:
        out["locator"] = recorded(locator, f"{in_map}.locator")
    source = (locator or {}).get("sourceId")
    if source in corpora:
        out["corpus"] = derived(source, "the locator's sourceId is a sourceId provenance.json corpora[] records")
    else:
        why = (f"the locator names corpus {source!r}, which provenance.json corpora[] does not record" if source
               else "the locator names no corpus")
        out["corpus"] = unknown(why)
        gaps.append(_gap(subject, "locator -> corpus", why))
    out["segment"] = unknown(SEGMENT_WHY)
    gaps.append(_gap(subject, "locator -> corpus segment", SEGMENT_WHY))

    if item is not None:
        out["status"] = recorded(entry.get("status"), f"{overlay_path} status")
        if "implementedIn" in item:
            out["implementedIn"] = recorded(item.get("implementedIn"), f"{overlay_path} implementedIn")
        tests_at = f"{overlay_path} tests"
    else:
        out["status"] = recorded(entry.get("status"), f"{in_map}.status; the engine has no {overlay_path}")
        tests_at = f"{in_map}.tests"
    tests = []
    rows = entry.get("tests") if entry.get("tests") is not None else []
    listed = isinstance(rows, list)
    if not listed:
        gaps.append(_gap(subject, "entry -> test", f"{tests_at} is not a list, so it names no test anybody can run"))
        rows = []
    for position, test in enumerate(rows):
        test = test if isinstance(test, dict) else {}
        at = f"{tests_at}[{position}]"
        name = test.get("test")
        mutation = test.get("mutation")
        row = {"name": recorded(name, f"{at}.test") if isinstance(name, str) and name.strip()
               else unknown(f"{at} names no test")}
        if isinstance(mutation, str) and mutation.strip():
            row["mutation"] = recorded(mutation, f"{at}.mutation")
        else:
            row["mutation"] = unknown(f"{at} records no mutation the test was watched catching")
            gaps.append(_gap(subject, "test -> mutation", row["mutation"]["why"]))
        if row["name"]["evidence"] == "unknown":
            gaps.append(_gap(subject, "entry -> test", row["name"]["why"]))
        tests.append(row)
    out["tests"] = tests
    if entry.get("status") == "implemented" and listed and not tests:
        gaps.append(_gap(subject, "entry -> test", "the entry is implemented and names no test"))

    contract = semantics.contract(generated["model"], generated["item"])
    member = generated["item"]["member"]
    out["handler"] = derived({"symbol": f"{HANDLERS}.{member}", "required": contract["required"]}, HANDLER_BASIS)
    candidates = implementation(entry_id, member, handlers, references)
    if candidates:
        out["implementation"] = candidates
    else:
        why = (f"no hand-written file under src/ writes {HANDLERS}.{member} or names the entry, and no artifact "
               f"records which file implements it")
        out["implementation"] = [unknown(why)]
        gaps.append(_gap(subject, "entry -> implementation", why))
    return out


def count(node, tally):
    """Every fact under `node`, by evidence class."""
    if isinstance(node, dict):
        if node.get("evidence") in CLASSES and "value" in node:
            tally[node["evidence"]] += 1
            return
        for value in node.values():
            count(value, tally)
    elif isinstance(node, list):
        for value in node:
            count(value, tally)


def build(engine_dir, package=None):
    """The trace of the engine at `engine_dir`, as plain data: what `--json` prints."""
    record = read_record(engine_dir)
    gaps = []
    documents = read_maps(record, package)
    document, origin = compose_maps(documents)
    try:
        items = overlay_step.load(engine_dir, document)
        merged = semantics.merge(document, items, root=engine_dir)
    except (overlay_step.OverlayError, semantics.GenerationError) as error:
        raise TraceError(f"the map and {overlay_step.DIRECTORY}/ do not merge, so there is no engine map to trace "
                         f"(the engine's own gate refuses this too): {error}")
    files = implementation_files(engine_dir, gaps)
    entries = [e for e in merged.get("entries") or [] if isinstance(e, dict) and isinstance(e.get("id"), str)]
    model = generator_model(record, merged, documents)
    generated = {item["entry"]["id"]: {"model": model, "item": item} for item in model.entries}
    references = reviewscope.entry_references(files, {e["id"]: generated[e["id"]]["item"]["member"] for e in entries})
    handlers = handler_files(files)
    corpora = {c.get("sourceId") for c in record.get("corpora") or [] if isinstance(c, dict)}
    trace = {
        "traceFormat": FORMAT,
        "engine": engine_facts(record, gaps),
        "topology": topology(engine_dir, record, gaps),
        "maps": maps_section(record, documents, gaps),
        "corpora": corpora_section(record),
        "entries": [entry_trace(e, origin, items.get(e["id"]), corpora, handlers, references,
                                len(documents) == 1, gaps, generated[e["id"]]) for e in entries],
    }
    tally = dict.fromkeys(CLASSES, 0)
    count(trace, tally)
    by_relationship = {}
    for gap in gaps:
        by_relationship[gap["relationship"]] = by_relationship.get(gap["relationship"], 0) + 1
    trace["summary"] = {"entries": len(entries), "evidence": tally,
                        "gaps": dict(sorted(by_relationship.items()))}
    trace["gaps"] = gaps
    return trace


def refuse_inside(engine_dir, path):
    """Refuse a report written inside the engine: a committed rendering is truth that goes stale.

    The trace is recomputed from the engine's records every time it is asked for. A copy of it
    beside those records would be a second statement of them that no produce updates -- the state
    #243 removed for the backlog. Outside the engine, the path is the caller's business.
    """
    engine = os.path.realpath(os.path.abspath(engine_dir))
    for spelling in (os.path.abspath(path), os.path.realpath(os.path.abspath(path))):
        if os.path.commonpath([engine, spelling]) == engine:
            raise TraceError(f"--html {path} is inside the engine at {engine_dir}: a report committed beside the "
                             f"records it is computed from goes stale at the next overlay edit. Write it outside "
                             f"the engine")


def dumps(trace):
    """The trace's bytes as `--json` prints them: the same bytes for the same engine, every time."""
    return json.dumps(trace, indent=2, ensure_ascii=False) + "\n"
