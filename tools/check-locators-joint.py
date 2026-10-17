#!/usr/bin/env python3
"""Check the citations of a map that cites corpora read by different adapters (#681).

Each grammar's locator checker reads one grammar, and refuses an entry citing a corpus it does not
read: `examples/faa-part-107/check-locators-section.py` holds a quote to the eCFR section tree,
`examples/frcp-6-12-81/check-locators-uslm.py` to USLM identifiers. A map may still cite both -- a
statute and the regulation made under it, one joint extent across them (0042) -- and until this
existed nothing could check it, so nothing could pack it.

This does not merge the grammars. It divides the map, and runs each grammar's own checker on its
share, unchanged:

  * **Entries** go to the corpus their `locator.sourceId` names. An entry naming none, or naming a
    corpus the manifest does not declare, is refused: with two grammars there is no default corpus.
  * **The extent's sections** go to the corpus that holds them, by that corpus's adapter
    (`portion_of`, the division `mapper inventory` already walks by, #660 and #674). A section no
    cited corpus holds, or two hold, is refused, exactly as the inventory refuses it.
  * **`extent.unreachable`** items go to the corpus their `sourceId` names; one naming no cited
    corpus is refused. Every other key of `extent` is kept on every share.

Each adapter's share is written to a private temporary directory as a map of its own and checked by
`LOCATOR_CHECKERS[adapter]` (the table `tools/pack-map.py` holds) against that adapter's corpora,
each named `<sourceId>=<path>`. An adapter whose checker reads one corpus per run is given one
share per corpus. The run passes only when every entry was in a share and every share passed.

What it does not buy: anything a single grammar's checker does not. A quote is held to its own
corpus's tree and nothing checks one corpus against the other; the division is mechanical, by
`sourceId` and by what each corpus prints.

Usage: check-locators-joint.py <corpus-map.json> --manifest <corpus-manifest.json>
The corpora are read at each manifest row's `committedPath`, relative to the manifest.
Exit 0 if every share passed, 1 if one did not or the map could not be divided, 2 on a usage error.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, TOOLS)
from mapper import corpus as corpus_step  # noqa: E402  (each adapter's portion_of: the inventory's own division)
from mapper.protocol import Refused  # noqa: E402


def _pack_map():
    spec = importlib.util.spec_from_file_location("pack_map", os.path.join(TOOLS, "pack-map.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shares(document, manifest, manifest_dir):
    """[(adapter, [sourceId, ...], share map)]: the map divided by grammar. Raises Refused."""
    corpora = {c.get("sourceId"): c for c in manifest.get("corpora") or [] if isinstance(c, dict)}
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise Refused("the map has no entries")
    by_source = {}
    for position, entry in enumerate(entries):
        source = ((entry.get("locator") if isinstance(entry, dict) else None) or {}).get("sourceId")
        label = entry.get("id") if isinstance(entry, dict) and isinstance(entry.get("id"), str) else f"entries[{position}]"
        if not isinstance(source, str) or not source:
            raise Refused(f"{label} names no locator.sourceId; a map citing several grammars has no default corpus")
        if source not in corpora:
            raise Refused(f"{label} cites {source!r}, which the manifest does not declare")
        by_source.setdefault(source, []).append(entry)
    cited = sorted(by_source)

    extent = document.get("extent")
    if not isinstance(extent, dict) or extent.get("unit") != "section-designation" \
            or not isinstance(extent.get("sections"), list):
        raise Refused("the extent is not a `section-designation` list of sections, so it cannot be divided "
                      "between the corpora by what each one prints")
    claimed, mine_of = {}, {}
    for source in cited:
        portion, mine = corpus_step.open_corpus(manifest, source, manifest_dir).portion_of(extent)
        if mine is None:
            raise Refused(f"the {corpora[source].get('adapter')!r} adapter of {source} makes no claim about "
                          f"which extent sections it holds, so the extent cannot be divided")
        mine_of[source] = (portion, mine)
        for item in mine:
            claimed.setdefault(item, []).append(source)
    listed = [item for item in extent["sections"] if isinstance(item, str)]
    orphan = [item for item in listed if item not in claimed]
    if orphan or len(listed) != len(extent["sections"]):
        raise Refused(f"the extent names {', '.join(orphan) or 'a non-string item'}, which no corpus this map "
                      f"cites contains")
    twice = sorted(item for item, holders in claimed.items() if len(holders) > 1)
    if twice:
        raise Refused(f"the extent names {', '.join(twice)}, which more than one corpus this map cites contains")
    unreachable = extent.get("unreachable")
    if unreachable is not None:
        if not isinstance(unreachable, list):
            raise Refused("extent.unreachable is not a list")
        for item in unreachable:
            if not isinstance(item, dict) or item.get("sourceId") not in by_source:
                raise Refused(f"an extent.unreachable item names {item.get('sourceId') if isinstance(item, dict) else item!r}, "
                              f"which is not a corpus this map's entries cite")

    checkers = _pack_map()
    groups = {}
    for source in cited:
        adapter = corpora[source].get("adapter")
        if adapter not in checkers.LOCATOR_CHECKERS:
            raise Refused(f"no locator checker for adapter {adapter!r} ({source}); known: "
                          f"{', '.join(sorted(checkers.LOCATOR_CHECKERS))}")
        if adapter in checkers.MULTI_CORPUS_ADAPTERS:
            groups.setdefault((adapter, None), []).append(source)
        else:
            groups[(adapter, source)] = [source]
    out = []
    for (adapter, _), sources in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[1])):
        held = set().union(*(mine_of[s][1] for s in sources))
        share_extent = dict(extent, sections=[item for item in listed if item in held])
        tables = [t for s in sources for t in mine_of[s][0].get("tables", [])] if "tables" in extent else None
        if tables is not None:
            share_extent["tables"] = tables
        if unreachable is not None:
            share_extent["unreachable"] = [item for item in unreachable if item["sourceId"] in sources]
        share = dict(document, entries=[e for s in sources for e in by_source[s]], extent=share_extent)
        out.append((adapter, sources, share))
    assert sum(len(share["entries"]) for _, _, share in out) == len(entries)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("map_path")
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    try:
        document = json.load(open(args.map_path, encoding="utf-8"))
        manifest = json.load(open(args.manifest, encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"check-locators-joint: cannot read the inputs: {error}", file=sys.stderr)
        return 2
    here = os.path.dirname(os.path.abspath(args.manifest))
    corpora = {c.get("sourceId"): c for c in manifest.get("corpora") or [] if isinstance(c, dict)}
    try:
        divided = shares(document, manifest, here)
    except Refused as error:
        print(f"NOT VERIFIED -- {error}")
        return 1
    checkers = _pack_map()
    failed = []
    with tempfile.TemporaryDirectory(prefix="rules-factory-joint-") as stage:
        for number, (adapter, sources, share) in enumerate(divided, 1):
            path = os.path.join(stage, f"share-{number}", "corpus-map.json")
            os.makedirs(os.path.dirname(path))
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(share, handle, indent=2, ensure_ascii=False)
            checker = checkers.LOCATOR_CHECKERS[adapter]
            named = [f"{s}={os.path.normpath(os.path.join(here, str(corpora[s].get('committedPath'))))}" for s in sources]
            print(f"--- share {number}: {adapter}, {', '.join(sources)}: {len(share['entries'])} entries, "
                  f"{len(share['extent']['sections'])} extent section(s); {os.path.relpath(checker, os.path.dirname(TOOLS))}",
                  flush=True)
            done = subprocess.run([sys.executable, checker, path, *named], stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True)
            print(done.stdout, end="" if done.stdout.endswith("\n") else "\n", flush=True)
            if done.returncode != 0:
                failed.append(f"share {number} ({adapter}) exited {done.returncode}")
    total = sum(len(share["entries"]) for _, _, share in divided)
    if failed:
        print(f"FAILED -- {'; '.join(failed)}")
        return 1
    print(f"ok -- {total} entries in {len(divided)} share(s), each checked by its own grammar's checker")
    return 0


if __name__ == "__main__":
    sys.exit(main())
