"""M5 of #3: the backlog -- one issue per entry the engine still has to build.

**The backlog is a projection, not a file in the engine (#243).** `produce` used to commit
`backlog/NNN-<entry-id>.md` and `backlog/README.md`. Nothing read them: `create` files GitHub
issues, `tools/dispatch-agent.sh` dispatches from issues and `tools/entry-packet.py` assembles an
assignment from the map. They were 19 of the 27 files in a one-entry pull request, and because
every item states its position out of the total, finishing any entry renumbered and rewrote nearly
all of them, so two entry branches collided on twenty files neither was about. So:

  * `produce` writes no `backlog/` and **removes one an earlier produce committed**: the pattern
    is retired in ownership.py (`RETIRED`, `remove_retired`) and the deletion is committed with the
    rest of the run or not at all (transaction.py);
  * `create` renders the items in memory, from the same two inputs `produce` used -- the map
    package `provenance.json` records, merged with the engine's `overlay/<entry id>.json` files
    (`engine_backlog`) -- and synchronises GitHub issues with them;
  * `factory backlog --render` prints the same rendering, as one Markdown document on stdout, or
    writes the files to a directory given with `--to`, which is never inside the engine unless the
    engine ignores it.

The rendering itself is unchanged, and so is every issue body: what moved is where it is kept.

docs/method.md, "Phase 5 -- Generate the backlog": each entry becomes one issue carrying its
scope, its source (the locator verbatim and the `evidence` it resolves to), its dependencies
(which order it), its reachability (`enabledBy` / `suspendedBy`, which order nothing), its
cross-references, its acceptance criteria and its required evidence (from `note`). The backlog is ordered by the
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

**Cross-references.** Every item has a "Cross-references" section listing the entry's
`crossReferences` in map order, each as its `cites` (JSON-quoted, so its bytes are exact) and how it
resolves: `resolvedBy`, linked to that entry's item or saying why it has none, or `unmapped` with
its reason, also JSON-quoted. An entry with none (a derived entry always) says `none`. So a
pointer that moves from `unmapped` to `resolvedBy`, or to another entry, changes the issue body and
`backlog --create` updates it, even when nothing else about the entry changed.

**Links.** An item names another item (in its dependencies, reachability and cross-references) as a
link to that item's file, `[`<entry-id>`](NNN-<entry-id>.md)`, which resolves in a rendering on disk
and not inside a GitHub issue. So `create` rewrites each such link in the body it sends as `#<n>`, the
issue of the item it names, when that item has one (`link_issues`); a link to an item with no issue
yet stays a file link. The rendering is never rewritten. Issues are matched by their marker, never by
file or issue number, so the two numberings need not agree: in a repository with an issue made
before its backlog, item file 025 is issue #26, and nothing depends on that.

**Identity.** Under the title, every item carries `<!-- rules-factory-entry: <entry-id> -->`
and `<!-- rules-factory-engine: <Name>; map: <package id> -->`. The entry id is the one thing
about an item the map never changes, so it is what ties a file to its issue: a title or a body
can change under it. The second marker says which engine and map made the issue, for a reader;
lookup does not use it, since an engine's issues live in that engine's repository.

**Quoted text carries the attribution its licence requires (decision 0023).** When the manifest
`licence` of the corpus is `<licence>. Attribution required: <statement>` (`attribution`; the SRD's),
`produce` puts `attribution` in the context, and every item, and the index, carries a "Corpus licence"
section: which corpus the quotations are from, its licence, a pointer to `LICENCE.txt` in the map
package, and the statement verbatim. A licence that mentions attribution or CC-BY in any other shape
is refused rather than rendered without it. A corpus whose licence requires no attribution (the
public-domain ones) renders nothing extra, so its backlog is byte-identical to before. `create`
reads the map package provenance.json records -- which is also what it renders from -- and refuses,
before any call to `gh`, a body without the statement (`check_bodies`).

Deterministic, standard library only. `create` synchronises the rendering with GitHub issues
through `gh` -- see its docstring.
"""
import hashlib
import json
import os
import re
import subprocess

import agentrails
import compose
import semantics
import intake
import overlay as overlay_step

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


def _cross_references(entry, files, by_id):
    """The entry's `crossReferences`, one line each in map order; `- none` without any."""
    references = [item for item in entry.get("crossReferences") or [] if isinstance(item, dict)]
    if not references:
        return "- none\n"
    lines = []
    for item in references:
        head = f"- `cites` {json.dumps(item.get('cites'), ensure_ascii=False)}"
        if "resolvedBy" in item:
            lines.append(f"{head} -- `resolvedBy` " + _relation([item["resolvedBy"]], files, by_id)[2:])
        else:
            lines.append(f"{head} -- `unmapped`: {json.dumps(item.get('unmapped'), ensure_ascii=False)}\n")
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
    out.append(f"A hand-written handler implements `Handlers.{semantics.pascal(eid)}`, the partial method "
               "`Generated/Contracts.g.cs` declares for this entry, with exactly its signature: once the entry "
               "is `implemented`, a missing or mis-typed handler does not build (#76).")
    out.append(f"`{overlay_step.path_for(eid)}` sets `status: implemented`, with `implementedIn` "
               "and `tests`: every test named with its recorded `mutation` -- the change to the engine "
               "that turned that test red.")
    out.append("After `factory produce` regenerates with that overlay, the generated correspondence tests "
               "stay green (`dotnet test`).")
    return "".join(f"- [ ] {line}\n" for line in out)


READY, BLOCKED = "ready", "blocked"
STATE_MARKER = "<!-- rules-factory-state:"


def state_of(entry, files):
    """`blocked` while an entry this one depends on is itself still to build, else `ready`.

    `files` is every entry that has a backlog item -- which is exactly the set of entries not yet
    built (items(), above). So a dependency with an item is a dependency that is not there yet,
    and an item that waits on one cannot be worked however ready its own text looks. Reachability
    (`enabledBy`, `suspendedBy`) orders nothing and is not consulted: it says where a rule applies,
    not what must exist first (decision 0029).

    This is the only state the factory decides. `needs-decision` is a person's judgement about a
    question the corpus does not settle, and `create` never overwrites it.
    """
    return BLOCKED if any(other in files for other in entry.get("dependsOn") or []) else READY


def markers(entry, context, files=()):
    """The HTML comments that identify an item's issue; invisible when GitHub renders it.

    The state marker is here, in the body, rather than computed again at sync time: the file then
    says what the factory decided, a reader sees it in the repository, and `backlog --create` reads
    it rather than re-deriving it from a graph it would have to be handed separately.
    """
    return (f"<!-- rules-factory-entry: {entry['id']} -->\n"
            f"<!-- rules-factory-engine: {context['name']}; map: {context['package']} -->\n"
            f"{STATE_MARKER} {state_of(entry, files)} -->\n")


def item_markdown(position, total, file_name, entry, files, by_id, context):
    eid = entry["id"]
    parts = [f"# {title(entry)}\n\n", markers(entry, context, files), "\n",
             f"Backlog item {position} of {total} for {context['name']}, from {context['package']} "
             f"{context['version']}. Generated by `factory produce` from the map merged with "
             "`overlay/<entry id>.json`; change those, not this file.\n\n",
             attribution_markdown(context),
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
    parts.append("## Cross-references\n\n`crossReferences` -- each pointer the evidence makes, and the entry "
                 "or the recorded reason it resolves to:\n\n"
                 + _cross_references(entry, files, by_id) + "\n")
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
             "derived entries are items. Rendered from the map package and this engine's "
             "`overlay/<entry id>.json` by `factory backlog`; not a file in the engine.\n\n"]
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


def document(rendered):
    """One Markdown document holding the whole rendering, index first, for stdout."""
    order = ["README.md"] + sorted(n for n in rendered if n != "README.md")
    return "\n\n---\n\n".join(rendered[name].rstrip("\n") + "\n" for name in order if name in rendered)


def stale_names(directory, rendered):
    """Names of an earlier rendering in `directory` that this one no longer has.

    The set `write_rendered` removes, computed where the ignore gate can also see it: a deletion in
    the engine is as much a change to the engine as a write, and `999-old.md` may be tracked even
    where every file about to be written is ignored. So the gate is asked about these too, and a
    directory that cannot be cleaned is refused rather than half-cleaned.
    """
    if not os.path.isdir(directory) or os.path.islink(directory):
        return []
    return sorted(name for name in os.listdir(directory)
                  if (ITEM_FILE.match(name) or name == "README.md") and name not in rendered)


def refuse_unignored(engine_dir, directory, names):
    """Refuse a `--render --to` inside `engine_dir` that the engine does not ignore (#243).

    A rendering is derived from the overlay, and committing it beside the overlay is the state
    #243 removed: it renumbers on every entry built, so two entry branches collide on files
    neither is about. A path outside the engine is the caller's business and is not checked.
    Inside it, three things are refused:

      * **the engine root itself**, outright and without asking git. `--to <engine>` would write
        `README.md` over the engine's own, and the root is never ignored by anything;
      * **a file the engine does not ignore**, which is asked of git for **every file the run would
        touch** (`names`: the rendering, and the stale items `write_rendered` would delete), not for
        the directory that will hold them. A deletion is held to the standard a write is: nothing
        here removes a file the engine tracks. An ignored directory can
        hold a tracked child -- `git check-ignore` answers for the path it is given, and a
        negation (`!backlog/README.md`) or an already-tracked file makes the directory's answer and
        the file's differ. Checking the directory alone was the first version of this and was wrong;
      * **a path that passes through a symlink**, because the answer git gives is about the name and
        the write follows the link.

    git is asked rather than `.gitignore` parsed: the rules are the engine's, may be spelled in any
    of the places git reads, and the factory emits no `.gitignore` of its own. A tree git cannot
    answer for is refused, not admitted.
    """
    engine = os.path.realpath(os.path.abspath(engine_dir))
    # Both spellings are asked, and the name is preferred. A path that *names* somewhere in the
    # engine is inside it even when a link on the way out resolves elsewhere -- that is the case
    # this refuses -- and a path that resolves into the engine from outside is inside it too.
    lexical, resolved = os.path.abspath(directory), os.path.realpath(os.path.abspath(directory))
    inside = [p for p in (lexical, resolved) if os.path.commonpath([engine, p]) == engine]
    if not inside:
        return
    if engine in (lexical, resolved):
        raise BacklogError(f"--to {directory} is the engine root: rendering there would write the backlog's "
                           f"README.md over the engine's own, and nothing ignores the root. Render to a "
                           f"directory of its own, outside the engine or one the engine ignores")
    relative = os.path.relpath(inside[0], engine)
    advice = (f"render to a path outside the engine, or add {relative}/ to the engine's .gitignore. The "
              f"backlog is derived from the overlay, and a committed copy of it is what #243 "
              f"removed")
    link = _symlink_between(engine, lexical)
    if link is not None:
        raise BacklogError(f"--to {directory} is inside the engine and passes through the symlink {link}, so "
                           f"what git says about the name is not what the write would reach; {advice}")
    wanted = sorted(f"{relative}/{name}" for name in names)
    try:
        done = subprocess.run(["git", "-C", engine, "check-ignore", "--stdin"], input="\n".join(wanted),
                              capture_output=True, text=True, timeout=GH_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BacklogError(f"--to {directory} is inside the engine, and git cannot say whether the engine "
                           f"ignores it ({error}); {advice}")
    if done.returncode not in (0, 1):
        raise BacklogError(f"--to {directory} is inside the engine, and `git check-ignore` failed "
                           f"({done.stderr.strip() or 'no output'}); {advice}")
    unignored = [path for path in wanted if path not in set(done.stdout.split("\n"))]
    if unignored:
        raise BacklogError(f"--to {directory} is inside the engine and the engine does not ignore "
                           f"{len(unignored)} of the {len(wanted)} file(s) it would write "
                           f"({', '.join(unignored[:3])}{'...' if len(unignored) > 3 else ''}); {advice}")


def _symlink_between(root, target):
    """The first component of `target` under `root` that is a symlink, or None. `root` itself is not one."""
    parts = os.path.relpath(os.path.abspath(target), root).split(os.sep)
    for depth in range(1, len(parts) + 1):
        if os.path.islink(os.path.join(root, *parts[:depth])):
            return "/".join(parts[:depth])
    return None


def write_rendered(rendered, directory):
    """Write the rendering as files under `directory`, replacing an earlier one; the paths written.

    For `factory backlog --render --to`. The directory is the caller's: it is created when absent,
    and an earlier rendering in it (`README.md`, `NNN-*.md`) is replaced, so a re-render leaves no
    item the backlog no longer has. Nothing else in it is touched.

    **Nothing is written through a symlink.** `open(path, "wb")` opens its destination by name and
    follows a link, so a `README.md -> ../../README.md` planted in the output directory would put
    the backlog's index over the engine's -- and `--to` is allowed to point at a directory the
    engine ignores, where planting one costs nothing. Each file is opened `O_NOFOLLOW`, which fails
    on a link rather than writing past it, and the run is refused naming the path. A platform whose
    `os` has no `O_NOFOLLOW` is refused outright: the flag defaulting to 0 would put the
    link-following write back silently, on the one platform nobody here is testing on.

    `O_NOFOLLOW` covers the **final component**. A parent directory swapped for a link between
    `refuse_unignored`'s check and the write is not caught, and catching it would take
    descriptor-relative I/O the standard library does not offer portably -- the same limit
    transaction.py records for `--out`.
    """
    if not hasattr(os, "O_NOFOLLOW"):
        raise BacklogError("this platform's os has no O_NOFOLLOW, so a rendering cannot be written without "
                           "the risk of following a symlink out of the directory it was told to write to. "
                           "Render to stdout (`factory backlog --render` with no --to) instead")
    os.makedirs(directory, exist_ok=True)
    for name in stale_names(directory, rendered):
        # Held to the gate the writes are (refuse_unignored), and it removes the link, never what
        # it points at.
        os.remove(os.path.join(directory, name))
    nofollow = os.O_NOFOLLOW
    for name in sorted(rendered):
        path = os.path.join(directory, name)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | nofollow, 0o644)
        except OSError as error:
            raise BacklogError(f"cannot write {path}: {error}. A rendering is never written through a "
                               f"symlink; remove it, or render somewhere else")
        with open(fd, "wb") as handle:
            handle.write(rendered[name].encode("utf-8"))
    return [os.path.join(directory, name) for name in sorted(rendered)]


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


def state_of_body(body):
    """The state the factory computed for this item, from its marker, or None on an older item."""
    for line in (body or "").splitlines():
        if line.startswith(STATE_MARKER):
            return line[len(STATE_MARKER):].split("-->")[0].strip() or None
    return None


def entry_of(body):
    """The entry id a body's leading marker names, or None."""
    found = ENTRY_MARKER.match(body)
    return found.group(1) if found else None


ITEM_LINK = re.compile(r"\[`([^`\n]+)`\]\((\d{3,}-[^()\s]+\.md)\)")
ISSUE_URL = re.compile(r"/issues/(\d+)\s*\Z")


def link_issues(body, files, numbers):
    """`body` with each link to an item file (`_relation`'s `[`id`](NNN-id.md)`) as `#<n>`.

    `files` maps each backlog file name to its entry id, `numbers` each entry id to its issue number.
    A link whose file is not an item of that entry, or whose entry has no issue, is left as it is."""
    def replace(found):
        eid = files.get(found.group(2))
        if eid != found.group(1) or eid not in numbers:
            return found.group(0)
        return f"#{numbers[eid]}"
    return ITEM_LINK.sub(replace, body)


def _read_items(rendered):
    """[(item name, entry id, title, body)] from the rendering, refusing one without a marker."""
    out, seen = [], {}
    for name in sorted(n for n in rendered if ITEM_FILE.match(n)):
        first, _, body = rendered[name].partition("\n")
        if not first.startswith("# "):
            raise BacklogError(f"{name} does not begin with a `# ` title line")
        eid = entry_of(body)
        if eid is None:
            raise BacklogError(f"{name} does not carry a rules-factory-entry marker under its title, so it "
                               "cannot be matched to an issue")
        if eid in seen:
            raise BacklogError(f"{seen[eid]} and {name} are both entry {eid!r}")
        seen[eid] = name
        out.append((name, eid, first[2:], body.lstrip("\n")))
    return out


POLICY = os.path.join(".github", "agent-policy.json")


def label_policy(engine_dir):
    """The engine's label vocabulary (decision 0029), or None when it has no policy file.

    The strings are the engine's, not the factory's: an engine that renames `state:ready` renames
    it here and nowhere else. An engine produced before the rails have no policy at all, and its
    issues are synchronised without labels rather than with the factory's guesses.

    What makes a vocabulary usable is `agentrails.policy_labels`, the same function `rails.py` reads
    it through (#188): the rule that the five are distinct is stated once, where the file is
    written, rather than twice here and there.
    """
    path = os.path.join(engine_dir, POLICY)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise BacklogError(f"{POLICY} cannot be read ({error}); it is where the label vocabulary lives")
    try:
        return agentrails.policy_labels(document, POLICY)
    except agentrails.PolicyError as error:
        raise BacklogError(str(error))


def label_plan(state, existing, labels):
    """(labels to add, labels to remove) for one issue. The two rules 0029 states, and nothing else.

    * **`needs-decision` is never overwritten.** It says a person judged that the corpus does not
      settle something, which is not a fact the factory can recompute from a dependency graph.
      While it is there, the state is left exactly as it is.
    * **Risk is never lowered.** An issue promoted to independent review stays there; the factory
      adds `normal` only to an issue carrying no risk label at all, because an issue with none
      cannot be dispatched or gated.
    """
    states = {labels["ready"], labels["blocked"], labels["needsDecision"]}
    risks = {labels["normalRisk"], labels["independentRisk"]}
    add, remove = [], []
    if labels["needsDecision"] not in existing:
        wanted = labels[state]
        if wanted not in existing:
            add.append(wanted)
        remove.extend(sorted((existing & states) - {wanted}))
    if not (existing & risks):
        add.append(labels["normalRisk"])
    return add, remove


def _issues(repo, gh):
    listed = _gh(["issue", "list", "--repo", repo, "--state", "all", "--limit", str(LIST_LIMIT),
                  "--json", "number,title,body,labels"], gh)
    try:
        issues = [{"number": int(i["number"]), "title": i["title"], "body": i.get("body") or "",
                   "labels": {label["name"] for label in i.get("labels") or []}}
                  for i in json.loads(listed or "[]")]
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise BacklogError(f"cannot read `gh issue list` output: {error}")
    if len(issues) >= LIST_LIMIT:
        raise BacklogError(f"{repo} has at least {LIST_LIMIT} issues, the most `gh issue list` is asked "
                           "for; an issue beyond them would be created again")
    return issues


def _recorded_packages(record, package, why):
    """[(package id, parts, the manifest corpus its map cites)] for every map provenance.json records.

    Read from `package` (a .nupkg path or Id@Version) or else Id@Version from provenance.json, taken
    from a file or the NuGet global packages folder and never downloaded, and refused unless its map
    and manifest are the ones provenance hashed.

    **An engine composed of several map packages is read from all of them** (rules-factory 0067).
    A backlog is the whole engine's work, so rendering it from one constituent would list a third
    of it and say nothing about the rest. An explicit `--package` still names one, for the caller
    who has the file and wants it used; it then stands for the package whose recorded digests it
    matches, and a file matching none is refused by the digest check below as it always was.
    """
    maps = [m for m in record.get("maps") or [] if isinstance(m, dict)]
    if not maps:
        raise BacklogError(f"provenance.json names no map package, so {why} cannot be read")
    return [_one_recorded_package(source, package if len(maps) == 1 else None, why) for source in maps]


def _one_recorded_package(source, package, why):
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
    return str(source.get("packageId")), parts, corpus


def engine_backlog(engine_dir, package=None):
    """(rendered, credit) for `engine_dir`: its backlog, rendered now, from the inputs it was produced from.

    Since #243 no engine holds a `backlog/`, so the rendering is made here rather than read. The two
    inputs are exactly the ones `produce` merged: the map package `provenance.json` records
    (`_recorded_package`, which refuses any package whose map and manifest are not the bytes the
    record hashed) and the engine's own `overlay/` (#247), merged under decision 0015 by
    the factory's own `semantics.merge`. So what `create` files, and what `--render` prints, is the
    backlog of the engine as it stands -- and an overlay edit shows up in it with no produce at all,
    which is the point of not committing a rendering of the overlay beside the overlay.

    `credit` is the attribution the corpus's licence requires (decision 0023), or None.
    """
    path = os.path.join(engine_dir, "provenance.json")
    if not os.path.isfile(path):
        raise BacklogError(f"{path} is not here, so nothing says which map package this engine was produced "
                           f"from and the backlog cannot be rendered; run `factory produce` first")
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError) as error:
        raise BacklogError(f"cannot read {path}, so the map package and the corpus's terms are unknown: {error}")
    if not isinstance(record, dict):
        raise BacklogError(f"{path} is not a JSON object, so the map package and the corpus's terms are unknown")
    name = ((record.get("engine") or {}).get("name") if isinstance(record.get("engine"), dict) else None)
    if not isinstance(name, str) or not name:
        raise BacklogError(f"{path} records no engine.name, so the backlog's items cannot say which engine "
                           f"they are for; run `factory produce` again")
    read = _recorded_packages(record, package,
                              "the backlog is rendered from the map packages the record names (0023)")
    documents = []
    for package_id, parts, corpus in read:
        try:
            documents.append((package_id, json.loads(parts["map"][1].decode("utf-8")), corpus))
        except (ValueError, AttributeError) as error:
            raise BacklogError(f"the map inside {package_id} is not readable JSON: {error}")
    try:
        document_map = compose.union([(package_id, document) for package_id, document, _ in documents])
    except compose.Refused as error:
        raise BacklogError(f"the map packages this engine was produced from do not compose, so there is "
                           f"no backlog to render: {error}")
    try:
        overlay = overlay_step.load(engine_dir, document_map)
    except overlay_step.OverlayError as error:
        raise BacklogError(str(error))
    try:
        merged = semantics.merge(document_map, overlay, root=engine_dir)
    except semantics.GenerationError as error:
        raise BacklogError(f"the map and {overlay_step.DIRECTORY}/ do not merge, so there is no backlog to "
                           f"render: {error}")
    maps = [m for m in record.get("maps") or [] if isinstance(m, dict)]
    context = {"name": name, "package": ", ".join(str(m.get("packageId")) for m in maps),
               "version": ", ".join(str(m.get("version")) for m in maps)}
    # One statement for the whole rendering, because every item quotes the same corpus: 0067's
    # compatibility rule refuses a composition whose packages do not read one corpus under one
    # content hash. What it does not refuse is two manifests describing that corpus's licence
    # differently, and rendering one of them over every item would put a statement on quotations
    # the other package's terms govern. So the statements are compared and a difference is
    # refused rather than resolved here (decision 0023).
    credits = []
    for package_id, _, corpus in documents:
        credit = attribution(corpus)
        if credit is not None and credit not in credits:
            credits.append(credit)
    if len(credits) > 1:
        raise BacklogError(f"the {len(documents)} map packages this engine is composed of state "
                           f"{len(credits)} different corpus attributions "
                           f"({'; '.join(str(c.get('sourceId')) for c in credits)}); every item of one "
                           f"backlog would carry one of them over quotations the other governs, so the "
                           f"backlog is refused rather than rendered under either (decision 0023)")
    credit = credits[0] if credits else None
    if credit:
        context["attribution"] = credit
    return render(merged.get("entries") or [], context), credit


def check_bodies(credit, files):
    """Before anything is sent to GitHub, what the corpus's terms demand of every body.

    Decision 0023: when the manifest `licence` of the corpus the map cites requires attribution
    (`credit`, from `engine_backlog`), every body must carry its statement verbatim, since a body
    quotes the corpus. Whether a body needs one is the map package's to say, not the body's, which
    is why `credit` comes from the package the record names and not from the text at hand. A
    rendering that dropped it -- an attribution section that stopped being emitted, a context
    assembled without it -- is refused here rather than posted. Returns log lines."""
    if not credit:
        return []
    missing = [name for name, _, _, body in files if credit["statement"] not in body]
    if missing:
        raise BacklogError(f"{credit['sourceId']}'s licence ({credit['terms']}) requires attribution (0023), and "
                           f"{len(missing)} issue body(ies) do not carry its statement verbatim: "
                           f"{'; '.join(missing)}. Nothing was sent to GitHub")
    return [f"--- backlog: {len(files)} bodies carry the attribution {credit['sourceId']}'s licence "
            f"({credit['terms']}) requires (0023)"]


def create(repo, engine_dir, log, gh="gh", package=None):
    """Synchronise the repository's issues with the engine's backlog, in build order.

    The backlog is rendered here, from the map package and the overlay (`engine_backlog`); since
    #243 the engine holds no copy of it, and the issues are the working copy.

    Every issue, open or closed, is read once, and each item is matched to an issue by the
    rules-factory-entry marker that begins both -- never by title, which a rename changes. Per item the outcome
    is `created` (no issue carries the marker), `updated` (one does, and its title or body
    differs from the item: `gh issue edit`) or `unchanged`. An issue with no marker whose title
    is exactly the item's title was made before markers existed; it is `adopted` -- edited to
    carry the marker -- rather than duplicated. So a second run in a row writes nothing.

    Bodies are compared and sent with their item links as issue references (`link_issues`). An issue's
    number is known only once it exists, so the issues to create are created first, in build order,
    each linking the items that already have issues; then, in build order, every other issue whose
    title or body differs is edited, and a created issue that links an item created after it is
    edited to link it too (`linked`, counted with `created`).

    Then the labels (decision 0029), from the engine's own `.github/agent-policy.json`: the state
    the item's marker carries -- `blocked` while something it depends on is itself still to build,
    `ready` otherwise -- and `normal` risk on an issue that carries no risk label. Two things are
    never done here: an issue a person moved to `needs-decision` keeps that state, and an issue
    promoted to independent review is never lowered. Both are judgements the factory has no basis
    to revise, and a sync that quietly undid them would teach everyone to stop making them. An
    engine with no policy file is synchronised without labels, and the run says so.

    Everything is decided before the first write. The same entry marker on two issues, or two
    unmarked issues with an adoptable title, is a refusal naming them: which one is the item
    is not the factory's to guess. An issue whose entry is no longer in the backlog (built,
    ruled out, or gone from the map) is reported and left alone; closing it is a person's
    decision.

    Returns ({outcome: count}, [numbers of issues not in the backlog]).
    """
    rendered, credit = engine_backlog(engine_dir, package)
    files = _read_items(rendered)
    if not files:
        raise BacklogError(f"{engine_dir} has no backlog items -- every entry of its map is built, ruled out "
                           f"or not this corpus's to supply, so there is nothing to create")
    for line in check_bodies(credit, files):
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
            issue, action = found[0], "matched"
        else:
            legacy = unmarked.get(issue_title) or []
            if len(legacy) > 1:
                raise BacklogError(f"{name}: no issue carries its marker, and several have its title: "
                                   + ", ".join(f"#{i['number']}" for i in legacy))
            issue = legacy[0] if legacy else None
            action = "adopted" if issue else "created"
        plan.append((action, issue, eid, issue_title, body))
    item_files = {name: eid for name, eid, _, _ in files}
    numbers = {eid: issue["number"] for _, issue, eid, _, _ in plan if issue is not None}

    counts = {"created": 0, "updated": 0, "adopted": 0, "unchanged": 0}
    sent = {}
    for action, _, eid, issue_title, body in plan:
        if action != "created":
            continue
        sent[eid] = link_issues(body, item_files, numbers)
        made = _gh(["issue", "create", "--repo", repo, "--title", issue_title, "--body-file", "-"], gh,
                   stdin=sent[eid])
        number = ISSUE_URL.search(made.strip())
        if not number:
            raise BacklogError(f"`gh issue create` made {issue_title!r} but printed no issue URL ({made.strip()!r}), "
                               f"so the issues linking it cannot name it; run `factory backlog --create` again")
        numbers[eid] = int(number.group(1))
        print(f"created   {issue_title}", file=log)
        counts["created"] += 1
    for action, issue, eid, issue_title, body in plan:
        body = link_issues(body, item_files, numbers)
        if action == "created":
            if _normal(sent[eid]) != _normal(body):
                _gh(["issue", "edit", str(numbers[eid]), "--repo", repo, "--title", issue_title,
                     "--body-file", "-"], gh, stdin=body)
                print(f"linked    #{numbers[eid]} {issue_title}", file=log)
            continue
        if action == "matched":
            same = issue["title"] == issue_title and _normal(issue["body"]) == _normal(body)
            action = "unchanged" if same else "updated"
        if action in ("updated", "adopted"):
            _gh(["issue", "edit", str(issue["number"]), "--repo", repo, "--title", issue_title,
                 "--body-file", "-"], gh, stdin=body)
            print(f"{action:<9} #{issue['number']} {issue_title}", file=log)
        else:
            print(f"unchanged #{issue['number']} {issue_title}", file=log)
        counts[action] += 1

    labels = label_policy(engine_dir)
    if labels is None:
        print("--- backlog: no .github/agent-policy.json, so no state or risk labels were applied "
              "(an engine produced before the rails); `factory produce` writes one", file=log)
    else:
        existing_labels = {issue["number"]: issue.get("labels", set()) for issue in issues}
        refused = []
        labelled = 0
        for action, issue, eid, issue_title, body in plan:
            number = numbers[eid]
            state = state_of_body(body) or READY
            add, remove = label_plan(state, existing_labels.get(number, set()), labels)
            if not add and not remove:
                continue
            command = ["issue", "edit", str(number), "--repo", repo]
            for label in add:
                command += ["--add-label", label]
            for label in remove:
                command += ["--remove-label", label]
            try:
                _gh(command, gh)
            except BacklogError as error:
                refused.append(f"#{number}: {', '.join(add + remove)} ({error})")
                continue
            labelled += 1
            print(f"labelled  #{number} {'+' + ' +'.join(add) if add else ''}"
                  f"{' -' + ' -'.join(remove) if remove else ''}", file=log)
        print(f"--- backlog: {labelled} issue(s) relabelled", file=log)
        if refused:
            raise BacklogError("these labels could not be applied, so the issues are not dispatchable:\n  "
                               + "\n  ".join(refused)
                               + "\nThe labels have to exist in the repository first: `factory rails --apply`.")

    current = {eid for _, eid, _, _ in files}
    orphans = sorted((i for eid, found in by_marker.items() if eid not in current for i in found),
                     key=lambda i: i["number"])
    for issue in orphans:
        print(f"not in backlog #{issue['number']} {issue['title']} -- left as it is", file=log)
    print(f"--- backlog: {counts['created']} created, {counts['updated']} updated, "
          f"{counts['adopted']} adopted, {counts['unchanged']} unchanged, "
          f"{len(orphans)} not in the backlog", file=log)
    return counts, [i["number"] for i in orphans]
