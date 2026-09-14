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
digits). The title is `<entry-id>: <name>`, which does not move when the order does; `create`
keys its idempotence on it.

Deterministic, standard library only. `emit` rewrites `backlog/` in full on every `produce`.
`create` turns the files into GitHub issues through `gh`, skipping titles that already exist.
"""
import json
import os
import re
import subprocess

DIRECTORY = "backlog"
ITEM_FILE = re.compile(r"^\d{3,}-.+\.md$")
BUILDABLE = ("mapped", "blocked")


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
    out.append(f"A hand-written handler carries `[Implements(\"{eid}\")]`.")
    out.append(f"`corpus-map.overlay.json` sets `{eid}` to `status: implemented`, with `implementedIn` "
               "and `tests`: every test named with its recorded `mutation` -- the change to the engine "
               "that turned that test red.")
    out.append("After `factory produce` regenerates with that overlay, the generated correspondence tests "
               "stay green (`dotnet test`).")
    return "".join(f"- [ ] {line}\n" for line in out)


def item_markdown(position, total, file_name, entry, files, by_id, context):
    eid = entry["id"]
    parts = [f"# {title(entry)}\n\n",
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
        done = subprocess.run([gh] + args, input=stdin, capture_output=True, text=True)
    except OSError as error:
        raise BacklogError(f"cannot run {gh}: {error}")
    if done.returncode != 0:
        raise BacklogError(f"`gh {' '.join(args[:2])}` failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def create(repo, engine_dir, log, gh="gh"):
    """Create one issue per backlog file in build order, skipping titles the repo already has."""
    directory = os.path.join(engine_dir, DIRECTORY)
    if not os.path.isdir(directory):
        raise BacklogError(f"{directory} does not exist; run `factory produce` first")
    names = sorted(n for n in os.listdir(directory) if ITEM_FILE.match(n))
    if not names:
        raise BacklogError(f"{directory} has no backlog items -- nothing to create")
    existing_json = _gh(["issue", "list", "--repo", repo, "--state", "all", "--limit", "10000",
                         "--json", "title"], gh)
    try:
        existing = {issue["title"] for issue in json.loads(existing_json or "[]")}
    except (ValueError, TypeError, KeyError) as error:
        raise BacklogError(f"cannot read `gh issue list` output: {error}")
    created = skipped = 0
    for name in names:
        path = os.path.join(directory, name)
        with open(path, encoding="utf-8") as handle:
            first, _, body = handle.read().partition("\n")
        if not first.startswith("# "):
            raise BacklogError(f"{name} does not begin with a `# ` title line")
        issue_title = first[2:]
        if issue_title in existing:
            print(f"exists  {issue_title}", file=log)
            skipped += 1
            continue
        _gh(["issue", "create", "--repo", repo, "--title", issue_title, "--body-file", "-"], gh,
            stdin=body.lstrip("\n"))
        existing.add(issue_title)
        print(f"created {issue_title}", file=log)
        created += 1
    print(f"--- backlog: {created} created, {skipped} already existed", file=log)
    return created, skipped
