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

Deterministic, standard library only. `emit` rewrites `backlog/` in full on every `produce`.
`create` synchronises the files with GitHub issues through `gh` -- see its docstring.
"""
import json
import os
import re
import subprocess

import generate

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


def _source(entry):
    locator = entry["locator"]
    return (f"Locator, `sourceId` {json.dumps(locator.get('sourceId'), ensure_ascii=False)}; citation:\n\n"
            f"{fence(locator['citation'])}\n"
            f"Evidence, verbatim:\n\n{fence(entry['evidence'])}")


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
    parts = [f"# {title(entry)}\n\n", markers(entry, context), "\n",
             f"Backlog item {position} of {total} for {context['name']}, from {context['package']} "
             f"{context['version']}. Generated by `factory produce` from the map merged with "
             "`corpus-map.overlay.json`; change those, not this file.\n\n",
             "## Entry\n\n",
             f"- id: `{eid}`\n- kind: `{entry.get('kind')}`\n- clarity: `{entry.get('clarity')}`\n"
             f"- status: `{entry.get('status')}`\n\n",
             "## Source\n\n"]
    if entry.get("derivedFrom"):
        parts.append("Derived (0012): no sentence states this fact, so it has no locator of its own. "
                     "Its sources' citations are its citation.\n\n")
        for source in entry["derivedFrom"]:
            parts.append(f"### From `{source}`\n\n{_source(by_id[source])}\n")
    else:
        parts.append(_source(entry) + "\n")
    ambiguity = entry.get("ambiguity")
    if isinstance(ambiguity, dict):
        parts.append(f"## Ambiguity\n\nFate: `{ambiguity.get('fate')}`")
        for key in ("unresolvedReason", "decision", "conflict"):
            if key in ambiguity:
                parts.append(f"; {key}: `{ambiguity[key]}`")
        parts.append(f".\n\n{fence(str(ambiguity.get('question', '')))}\n")
    parts.append("## Dependencies\n\n`dependsOn` -- built before this item:\n\n"
                 + _relation(entry.get("dependsOn") or [], files, by_id) + "\n")
    parts.append("## Reachability\n\n`enabledBy` -- what the tests must set up:\n\n"
                 + _relation(entry.get("enabledBy") or [], files, by_id)
                 + "\n`suspendedBy` -- what the tests must show does not happen:\n\n"
                 + _relation(entry.get("suspendedBy") or [], files, by_id) + "\n")
    parts.append("## Acceptance criteria\n\n" + _criteria(entry, by_id) + "\n")
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


def create(repo, engine_dir, log, gh="gh"):
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
