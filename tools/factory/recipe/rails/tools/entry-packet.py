#!/usr/bin/env python3
"""The bounded assignment for one map entry: everything an agent needs, and nothing else.

    tools/entry-packet.py <entry-id> [--out DIR] [--package-map PATH] [--stdout]

Emitted by rules-factory as a managed file (decision 0029). `AGENTS.md` is the contract this
serves; read that first.

**Why a packet rather than "read the repository".** An agent that starts by searching a corpus and
a map for what a rule means re-does the mapping, badly, every time -- and its reading, not the
published map, ends up in the engine. The map is the interface (rules-factory decision 0001), so
the assignment is one entry of it, assembled mechanically: the entry as published and merged with
this engine's overlay file for it, its citation and the evidence verbatim, what it depends on and what those
entries are, what enables or suspends it, where its cross-references land, the owner's rulings
that apply to it, the handler the generated code declares once the entry is `implemented` -- the
one the work has to produce, not the one on disk while it is still `mapped` -- and the obligations
the gate will hold the work to.

**What this deliberately does not do.** It does not read the corpus, quote more of it than the map
quotes, summarise, paraphrase or rank anything. Every line below is the map's own bytes or a fact
computed from them, so a packet cannot introduce a reading of its own -- which is the failure it
exists to prevent, not a limitation of the implementation.

Where the packet and the corpus appear to disagree, that is an upstream map defect: report it
(`AGENTS.md`), and do not make the engine disagree with the published map.

**Ephemeral.** A packet is written outside the repository and never committed: it is derived from
the map, so committing it would create a second copy of the interface that can go stale. The
default location is `$RULES_ENGINE_PACKET_ROOT` or a directory beside the system temporary one;
a `--out` inside the repository is refused.

The map itself is a NuGet package this engine references and never copies (decision 0015), so the
merge needs the restored package. `--package-map` names it; without one, this asks MSBuild where
the restore put it, exactly as `scripts/validate.sh` does -- which needs the SDK and a restore.

**A composed engine** (rules-factory 0067) is produced from several map packages, and a packet is
built from the one its entry came from. The entry id says which: identity in a composition is
`(package, entry id)` -- `Srd52Combat.round-down` -- so the prefix names the package, and the
header names that package at its own version. The model is built over the whole composition,
because that is what the engine implements: an entry of another package is read here exactly as
one of this package's is, and an entry another map supersedes says so instead of being handed out
as work. `--package-map` is repeated once per package, or MSBuild is asked for all of them; each
is matched to the package `provenance.json` records **by digest**, never by order or by path.

Standard library only, plus the factory's own generator vendored under `scripts/factory/`, so the
entry, the handler signature and the packet cannot drift from what the build actually generates.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import types

# model_for() imports the vendored scripts/factory modules, and an imported module leaves its
# bytecode behind: scripts/factory/__pycache__/, a path no ownership row covers, so the checkout
# that ran this goes dirty and tools/dispatch-agent.sh refuses to open a worktree for the next
# issue (#194). scripts/validate.sh and `factory verify` export PYTHONDONTWRITEBYTECODE for the
# same reason, but nothing exports it in the shell an agent runs this from. The loader reads this
# flag when the import happens, so it belongs here and not beside the import it disarms.
sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
OVERLAY = "overlay"
PROVENANCE = "provenance.json"
PACKET_ROOT_VARIABLE = "RULES_ENGINE_PACKET_ROOT"


class Refused(Exception):
    """Something the packet cannot honestly assemble. Nothing is written."""


def read_json(path, what):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise Refused(f"{what} is missing: {path}")
    except (OSError, ValueError) as error:
        raise Refused(f"{what} cannot be read ({path}): {error}")


def vendored(module):
    """A module of the factory's own generator, from `scripts/factory/` where produce vendored it.

    The packet computes with the factory's code rather than a copy of its rules, so that the
    entry, the handler signature and the composed ids cannot drift from what the build emits.
    """
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        return __import__(module)
    except ImportError as error:
        raise Refused(f"scripts/factory is not importable ({error}); run `factory produce` again")


def engine():
    """(name, the map packages, what each supersedes, randomness) from the engine's provenance.

    Every map the engine was produced from, in the order the record names them -- which is package
    id order, because a record of a composition is a function of its inputs and not of the order
    they were given in (rules-factory 0067). One map is the ordinary case and is a list of one.
    """
    record = read_json(ROOT / PROVENANCE, "provenance.json")
    maps = [m for m in record.get("maps") or [] if isinstance(m, dict)]
    superseded = {str(s.get("entry")): str(s.get("by"))
                  for s in record.get("supersedes") or [] if isinstance(s, dict)}
    try:
        name = record["engine"]["name"]
        for package in maps:
            package["packageId"], package["version"]
    except (KeyError, TypeError):
        raise Refused(f"{PROVENANCE} does not name this engine and its map; run `factory produce` again")
    if not maps:
        raise Refused(f"{PROVENANCE} does not name this engine and its map; run `factory produce` again")
    return name, maps, superseded, record.get("randomness")


def map_of(entry_id, maps):
    """The map package `entry_id` came from, and the id it has inside that package.

    This is the question the tool used to refuse, and the entry id answers it. Identity in a
    composition is `(package, entry id)` -- `Srd52Combat.round-down`, the package id's last
    segment, the separator, the map's own id (rules-factory 0067) -- so the prefix names the
    package and nothing has to be guessed, authored or inferred from a file path. `compose` is the
    factory's own module for it, vendored under `scripts/factory/`, so the separator and the slug
    rule cannot drift from the ones the engine was produced with.

    **A single-package engine is not namespaced**, so its ids carry no prefix and every entry is
    that one map's. A prefix naming no package of a composition is refused with the packages
    listed: that is the one case where choosing would be silently wrong, and it is what the
    blanket refusal on a composed engine used to stand in for.
    """
    if len(maps) == 1:
        return maps[0], entry_id
    compose = vendored("compose")
    by_slug = {compose.slug(package["packageId"]): package for package in maps}
    prefix, separator, rest = str(entry_id).partition(compose.SEPARATOR)
    if separator and prefix in by_slug:
        return by_slug[prefix], rest
    raise Refused(f"this engine is composed of {len(maps)} map packages, so an entry id names the "
                  f"package it came from ({compose.SEPARATOR.join((next(iter(by_slug)), 'some-entry'))}), "
                  f"and {entry_id!r} names none of them: "
                  f"{', '.join(sorted(by_slug))}")


def paired(paths, maps):
    """[(map package, its restored map's path)], matched by digest and never by order.

    A composed engine restores one map file per package and MSBuild hands them back in its own
    order, so something has to say which file is which package's. The digest does:
    `provenance.json` records `files[role="map"].sha256` for every package, and a file that hashes
    to it *is* that package's map. Pairing by the order MSBuild happened to return, or by picking
    the package id out of the restore path, would be a guess that reads plausibly when it is wrong
    -- and the failure it would cause is a packet built from another map's bytes, which is exactly
    what this tool exists to prevent.

    So the pairing is the check. Every package must be matched, every path must match one, and a
    path that matches nothing is named rather than dropped.
    """
    recorded = {}
    for package in maps:
        declared = [part.get("sha256") for part in package.get("files") or []
                    if isinstance(part, dict) and part.get("role") == "map"]
        if len(declared) != 1 or not declared[0]:
            raise Refused(f"{PROVENANCE} does not record the digest of {package['packageId']}'s map "
                          f"(`maps[].files[role=\"map\"]`), so the bytes a packet is built from "
                          f"cannot be checked against it")
        recorded[declared[0]] = package
    found, unknown = {}, []
    for path in paths:
        try:
            digest = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
        except OSError as error:
            raise Refused(f"--package-map {path} cannot be read ({error})")
        if digest in recorded:
            found[digest] = path
        else:
            unknown.append(path)
    missing = [package["packageId"] for digest, package in recorded.items() if digest not in found]
    if missing:
        raise Refused(f"no restored map hashes to what {PROVENANCE} records for "
                      f"{', '.join(missing)}; the engine was produced from "
                      f"{len(maps)} package(s) and {len(paths)} map file(s) were read"
                      + (f", of which {len(unknown)} match no package this engine records "
                         f"({', '.join(unknown[:3])})" if unknown else "")
                      + ". Restore the packages this engine declares, or pass one --package-map "
                        "per package.")
    if unknown:
        raise Refused(f"{len(unknown)} map file(s) match no package {PROVENANCE} records "
                      f"({', '.join(unknown[:3])}); a packet is built from the maps the engine "
                      f"was produced from and nothing else")
    return [(package, found[digest]) for digest, package in recorded.items()]


def package_maps_from_msbuild(name):
    """Where the restore put each map package's map, asked of MSBuild rather than guessed.

    The same question `scripts/validate.sh` asks, and for the same reason: the global packages
    folder is NuGet's business, and an engine that guesses at it is wrong on someone's machine.

    A composed engine references one map package per constituent, so MSBuild answers with several
    `RulesFactoryMap` items and their order is its own business. `paired` matches each to the
    package `provenance.json` records by digest, so nothing here depends on that order.
    """
    project = ROOT / "src" / name / f"{name}.csproj"
    if not project.is_file():
        raise Refused(f"no project at {project}; pass --package-map")
    try:
        frameworks = (ROOT / "Directory.Build.props").read_text(encoding="utf-8")
        framework = frameworks.split("<TargetFrameworks>")[1].split("<")[0].split(";")[0]
    except (OSError, IndexError):
        raise Refused("cannot read the target framework from Directory.Build.props; pass --package-map")
    try:
        done = subprocess.run(["dotnet", "msbuild", str(project), "-getItem:RulesFactoryMap",
                               f"-p:TargetFramework={framework}"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as error:
        raise Refused(f"cannot ask MSBuild where the map package is ({error}). Pass --package-map, or "
                      f"restore first: dotnet restore")
    if done.returncode != 0:
        raise Refused(f"MSBuild could not answer where the map package is. Restore first "
                      f"(`dotnet restore`), or pass --package-map.\n{done.stderr.strip()}")
    try:
        items = json.loads(done.stdout)["Items"]["RulesFactoryMap"]
        paths = [item["FullPath"] for item in items]
    except (ValueError, KeyError, TypeError):
        raise Refused("MSBuild returned no readable RulesFactoryMap items; restore first, or pass --package-map")
    if not paths:
        raise Refused("MSBuild returned no RulesFactoryMap item; restore first, or pass --package-map")
    return paths


def model_for(pairs, name, superseded, randomness):
    """The factory's own model of merge(the composed map, overlay), from the generator this engine vendors.

    `pairs` is every map package and its restored map, so the model is built over the **whole**
    composition and not over one constituent of it. That is what makes the entry findable at all:
    a composed engine's overlay files, generated members and registry ids are the namespaced ones
    (`Srd52Combat.round-down`), and a model built from one package would not hold them.

    The composition is `compose.union`, the same call `engine-gate.py regenerate` makes over the
    restored packages, in the same package-id order -- so what a packet computes is what the gate
    regenerates rather than a second, parallel idea of what these packages mean together. One
    package composes to itself, ids and all.
    """
    generate = vendored("generate")          # the factory's generator, vendored by produce
    overlay_step = vendored("overlay")       # one file per entry under overlay/, #247
    rulings = vendored("rulings")            # the owner's rulings the overlay holds, decision 0027
    compose = vendored("compose")            # several packages as one, decision 0067
    try:
        package = compose.union([(record["packageId"], read_json(path, "the map package's map"))
                                 for record, path in pairs])
    except compose.Refused as error:
        raise Refused(f"the maps this engine was produced from do not compose: {error}")
    try:
        overlay = overlay_step.load(str(ROOT), package)
    except overlay_step.OverlayError as error:
        raise Refused(str(error))
    try:
        merged = generate.merge(package, overlay, root=str(ROOT))
        model = generate.Model(types.SimpleNamespace(
            packages=[types.SimpleNamespace(package_id=record["packageId"], version=record["version"])
                      for record, _ in pairs],
            superseded=superseded, randomness=randomness),
                               merged, name, rulings.collect(overlay))
    except generate.GenerationError as error:
        raise Refused(f"the map and this engine's overlay do not merge: {error}")
    return generate, model, overlay


def block(value):
    """A JSON value as a fenced block: the map's bytes, not a rendering of them."""
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"


def fence(text):
    """A string the corpus wrote, in a fence, exactly as the map holds it.

    Not `block`: JSON-quoting the corpus's own sentence escapes its quotation marks and turns the
    wording an implementer has to read into something they have to decode first. The map's backlog
    items render evidence this way for the same reason. The fence is opened with as many backticks
    as it takes to contain what is inside it.
    """
    ticks = "`" * max(3, max((len(run) for run in re.findall(r"`+", text)), default=0) + 1)
    return f"{ticks}text\n{text}\n{ticks}"


def entry_line(model, entry_id):
    """`<id> -- <name> (<status>)` for an entry of the map, or a note that the map has no such entry."""
    item = model.by_id.get(entry_id)
    if item is None:
        return f"`{entry_id}` — **not an entry of this map**"
    entry = item["entry"]
    return f"`{entry_id}` — {entry.get('name', '(unnamed)')} (status: {entry.get('status', 'unstated')})"


def locators(generate, model, item):
    """Every located entry this one rests on, as (entry id, locator), in the model's own order.

    A derived entry (decision 0012) cites nothing of its own: its sources' citations are its
    citation, and they entail the fact together, so all of them are here rather than the first.
    """
    del generate
    out = []
    for member in item["locators"]:
        located = next(i for i in model.entries if i["member"] == member)
        out.append((located["entry"]["id"], model.locator_of(member)))
    return out


def as_implemented(generate, model, item):
    """This entry as the generator will see it once the overlay says `implemented` (#204).

    §7 describes the work, and the work changes the declaration: `status` decides both the
    correspondence row (`first_row`) and, through it, whether the handler is the required partial
    or the optional hook. So the status is moved and the generator is asked again, rather than the
    packet restating either rule -- the packet's whole claim is that it computes from the map with
    the factory's own generator, and a second copy of that rule here would be the first line of it
    that could drift from what the build emits.
    """
    entry = {**item["entry"], "status": "implemented"}
    entries = {entry_id: other["entry"] for entry_id, other in model.by_id.items()}
    entries[entry["id"]] = entry
    return {**item, "entry": entry, "row": generate.first_row(entry, entries)}


def handler(generate, model, item):
    """The handler this entry will declare once it is implemented -- not the one declared today.

    While the entry is `mapped`, `Contracts.g.cs` declares the optional hook, and the regeneration
    that follows marking it `implemented` replaces that with the required partial. Rendering the
    file as it stands hands the implementer a signature that is right about the present and wrong
    about the assignment, which costs one rewrite of the handler file (#204).

    Returns the signature, what obliges it, and whether it is not what the file holds today -- an
    entry that stays on the optional hook when implemented (correspondence row 8) has the same
    declaration before and after, and saying otherwise would be the same defect the other way up.
    """
    c = generate.contract(model, as_implemented(generate, model, item))
    replaces = c["required"] != generate.contract(model, item)["required"]
    if c["required"]:
        return (f"internal static partial Resolution<{c['output']}> {item['member']}({c['request_cs']} request);",
                "required: the build does not complete without it", replaces)
    return (f"static partial void {item['member']}({c['request_cs']} request, ref Resolution<{c['output']}>? resolution);",
            "optional even then: its correspondence row answers by default, and this hook overrides that "
            "answer or leaves it", replaces)


def packet(generate, model, overlay, item, identity):
    """The packet for one entry, naming the map **that entry** came from.

    A composed engine holds several maps, and which one an entry is from is not a detail: it is
    which published bytes the implementer is working to, which version a defect is reported
    against, and which corpus licence the work carries. The entry id says it (`map_of`), so the
    header names that package and then says what it is composed with, rather than naming one of
    several and leaving a reader to find out which.
    """
    name, source, local_id, maps, superseded = identity
    entry = item["entry"]
    entry_id = entry["id"]
    composed = [m for m in maps if m["packageId"] != source["packageId"]]
    lines = [f"# Entry packet: `{entry_id}`\n",
             f"**{entry.get('name', '(unnamed)')}** — engine `{name}`, map `{source['packageId']}` "
             f"{source['version']}",
             f"(`sha256:{source.get('nupkgSha256', '')[:16]}…`). Assembled by `tools/entry-packet.py` from the merge of that",
             "package and this engine's overlay. Every line below is the map's own bytes or a fact computed",
             "from them: nothing here is a reading of the corpus, and neither is your implementation.\n"]
    if composed:
        lines.append(f"This engine is **composed** of {len(maps)} map packages (rules-factory 0067), and this "
                     f"entry is `{source['packageId']}`'s — its id says so. It is merged here with "
                     + ", ".join(f"`{m['packageId']}` {m['version']}" for m in composed)
                     + ", so what an entry of another package says is in section 4 exactly as an entry of this "
                       "one would be. A defect in **this** entry is reported against "
                       f"`{source['packageId']}` {source['version']} and no other, where it is "
                       f"published as `{local_id}` — the composition's prefix is this engine's, not the "
                       "map's, so an upstream report names the id without it (section 9).\n")
    if entry_id in superseded:
        lines.append(f"> **This entry is superseded in this composition**, by "
                     f"{entry_line(model, superseded[entry_id])}. The map that holds this one declined the "
                     "passage because its slice stopped short, and another map of this composition holds it in "
                     "scope; the composition answers the rule there. There is no implementation to write here, "
                     "and writing one would be a second reading of a passage this engine already answers "
                     "(rules-factory 0067). If you were assigned this entry, say so on the issue.\n")
    lines += ["## 1. The entry, as the engine sees it\n",
              block(entry), ""]

    lines.append("## 2. Where it comes from\n")
    cited = locators(generate, model, item)
    if not cited:
        lines.append("This entry cites nothing: the map records no locator for it, and it derives from nothing.\n")
    for cited_id, locator in cited:
        held = " (its own passage)" if cited_id == entry_id else f" (through `derivedFrom`, from `{cited_id}`)"
        lines.append(f"**Locator**{held}:\n\n{block(locator)}\n")
    evidence = entry.get("evidence")
    if evidence is not None:
        lines.append("**Evidence, verbatim as the map quotes it.** This is the corpus's wording, and the only "
                     "wording you may rely on:\n")
        lines.append(fence(str(evidence)) + "\n")
    else:
        lines.append("The map quotes no evidence for this entry. That is a fact about the entry, not a gap for "
                     "you to fill from the corpus.\n")

    ambiguity = entry.get("ambiguity")
    if isinstance(ambiguity, dict):
        lines.append("**The question the map records as unsettled** — `fate` "
                     f"`{ambiguity.get('fate')}`"
                     + (f", `unresolvedReason` `{ambiguity['unresolvedReason']}`"
                        if ambiguity.get("unresolvedReason") else "") + ":\n")
        lines.append(fence(str(ambiguity.get("question", ""))) + "\n")
        lines.append("An entry whose question is unresolved is implemented as a decline that names why and cites "
                     "where. Answering it is not yours to do (`AGENTS.md`).\n")

    lines.append("## 3. What this engine records about it\n")
    row = overlay.get(entry_id)
    lines.append(f"This entry's overlay file (`{OVERLAY}/{entry_id}.json`, the three fields the engine owns "
                 f"under decision 0015; one file per entry, so it is yours alone to write):\n")
    lines.append(block(row) if row is not None else f"This entry has no overlay file yet. Writing "
                                                    f"`{OVERLAY}/{entry_id}.json` is part of the work: `status`, "
                                                    f"`implementedIn` and `tests`.")
    lines.append(f"\nCorrespondence row: {item['row'] if item['row'] else 'none (not plainly computable)'}\n")

    lines.append("## 4. Dependencies and reachability\n")
    depends = entry.get("dependsOn") or []
    lines.append("**`dependsOn`** — these order the work; an entry is built after what it depends on:\n"
                 if depends else "**`dependsOn`**: none.\n")
    for other in depends:
        lines.append(f"- {entry_line(model, other)}")
    for field, meaning in (("enabledBy", "this entry applies only where these hold"),
                           ("suspendedBy", "these suspend it")):
        values = entry.get(field) or []
        lines.append(f"\n**`{field}`** — {meaning}; reachability orders nothing:\n"
                     if values else f"\n**`{field}`**: none.\n")
        for other in values:
            lines.append(f"- {entry_line(model, other)}")

    lines.append("\n## 5. Cross-references\n")
    references = entry.get("crossReferences") or []
    if not references:
        lines.append("None. (A derived entry never has any.)\n")
    for reference in references:
        cites = json.dumps(reference.get("cites", ""), ensure_ascii=False)
        if reference.get("resolvedBy"):
            lines.append(f"- {cites} → resolved by {entry_line(model, reference['resolvedBy'])}")
        else:
            reason = json.dumps(reference.get("reason", ""), ensure_ascii=False)
            lines.append(f"- {cites} → **unmapped**: {reason}")

    lines.append("\n## 6. The owner's rulings that apply\n")
    applicable = [ruling for ruling in model.rulings if ruling.get("entry") == entry_id]
    if not applicable:
        lines.append("None. Where the corpus does not settle this entry, the engine declines; it does not "
                     "decide (decision 0027, and `AGENTS.md`).\n")
    for ruling in applicable:
        lines.append(block(ruling) + "\n")

    signature, obligation, replaces = handler(generate, model, item)
    lines.append("## 7. The handler you implement\n")
    lines.append(f"What `src/{name}/Generated/Contracts.g.cs` declares for this entry once it is `implemented` — "
                 f"{obligation}:\n")
    lines.append(f"```csharp\n{signature}\n```\n")
    if replaces:
        lines.append(f"That file holds a different declaration **today**: this entry is `{entry.get('status')}`, so "
                     "the generator has emitted the optional hook, and the re-produce that follows marking it "
                     "`implemented` replaces that with the signature above. Write the signature above; do not copy "
                     "the one currently in the file.\n")
    lines.append(f"The request type is `{generate.contract(model, item)['request']}` in "
                 f"`src/{name}/Generated/Requests.g.cs`. It is partial: declare the entry's inputs as `init` "
                 f"properties in a file of your own. Do not edit anything under `Generated/`.\n")

    lines.append("## 8. What the gate will ask of you\n")
    lines.append(f"- Every test you write is named in this entry's `tests`, in `{OVERLAY}/{entry_id}.json`, with the mutation that "
                 "makes it fail — and you must have watched it fail. A test nobody has watched fail is not yet a "
                 "test.\n"
                 "- The whole gate, not a narrower command: `./scripts/validate.sh full`.\n"
                 "- The implementation cites this entry and its locator, and a decline names why and where.\n"
                 "- Nothing under `Generated/`, `corpus/` or `provenance.json` is edited by hand.\n"
                 "- The change closes exactly the one issue it names, and nothing else.\n")
    lines.append("## 9. If the map is wrong\n")
    lines.append("Stop. Report an upstream map defect on the issue — the entry id, the locator, what the map says "
                 "and what the corpus says — and do not implement around it. A map is corrected by a new, checked, "
                 "published map version, and this engine is then re-produced from it (`AGENTS.md`).\n")
    if composed:
        lines.append(f"The map to report it against is `{source['packageId']}` {source['version']}, and the entry "
                     f"is `{local_id}` there. `{entry_id}` is what **this** engine calls it, because an id is "
                     "qualified by the package that enumerated it once several are composed; a report naming the "
                     "composed id names an entry that map does not have.\n")
    return "\n".join(lines)


def destination(out, entry_id):
    if out is None:
        root = os.environ.get(PACKET_ROOT_VARIABLE) or os.path.join(tempfile.gettempdir(), "rules-engine-packets")
        out = os.path.join(root, ROOT.name)
    resolved = pathlib.Path(out).expanduser().resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise Refused(f"a packet is never written inside the repository ({resolved}). It is derived from the map, "
                      f"and a committed copy of the interface goes stale. Use --out elsewhere, or "
                      f"${PACKET_ROOT_VARIABLE}.")
    return resolved / f"entry-{entry_id}.md"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="entry-packet.py", description=__doc__.split("\n")[0])
    parser.add_argument("entry", help="the map entry id to assemble a packet for")
    parser.add_argument("--out", help=f"directory to write into (default: ${PACKET_ROOT_VARIABLE}, "
                                      f"else a directory beside the system temporary one)")
    parser.add_argument("--package-map", action="append", default=[], metavar="PATH",
                        help="the restored map package's corpus-map.json (default: ask MSBuild); "
                             "repeat once per package for a composed engine")
    parser.add_argument("--stdout", action="store_true", help="write the packet to stdout and no file")
    args = parser.parse_args(argv)

    try:
        name, maps, superseded, randomness = engine()
        pairs = paired(args.package_map or package_maps_from_msbuild(name), maps)
        source, local_id = map_of(args.entry, maps)
        generate, model, overlay = model_for(pairs, name, superseded, randomness)
        item = model.by_id.get(args.entry)
        if item is None:
            near = [entry_id for entry_id in model.by_id if args.entry.lower() in entry_id.lower()]
            raise Refused(f"the map has no entry {args.entry!r}"
                          + (f". Did you mean: {', '.join(sorted(near)[:5])}?" if near else
                             f" (the map has {len(model.by_id)} entries)"))
        text = packet(generate, model, overlay, item, (name, source, local_id, maps, superseded))
        if args.stdout:
            sys.stdout.write(text)
            return 0
        target = destination(args.out, args.entry)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    except Refused as error:
        print(f"entry-packet: REFUSED -- {error}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
