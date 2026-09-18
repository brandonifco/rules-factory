"""The mapper's command line.

Two commands today, and both are about the protocol, because the protocol is the part of the
method that is mechanical: `protocol` says whether a corpus's protocol is one this mapper can
act on, and `pointers` performs the interrogation the protocol obliges and reports what it
found. Producing a map is still done by hand (docs/method.md); what this makes checkable is that
the walk was the walk this corpus requires.

Four exit codes, the factory's four (README, *What the factory exits with*), because a caller
that reads only `$?` must be able to tell what happened:

  0  every declaration held, and something was actually examined
  1  a declaration is wrong, or an interrogation that was declared detected nothing at all
  2  a usage error
  3  NOT VERIFIED: the interrogation ran and found what it cannot judge -- a pointer the map
     does not declare. Whether each one is owed is 0026's question, decided by reading the
     corpus, and this tool does not decide it. Not a pass, not a failure, and never silent.
"""
import argparse
import json
import os
import sys

from mapcontract.entry import entries_of

from mapper import corpus as corpus_step
from mapper import inventory as inventory_step
from mapper import pointers as pointers_step
from mapper import protocol as protocol_step

NOT_VERIFIED = 3


def _read(path, what):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise protocol_step.Refused(f"cannot read {what} {path}: {error}")


def _find_manifest(map_path):
    """The manifest beside the map, when there is exactly one candidate -- the same rule
    check-map.py uses, so a map does not need two conventions for where its manifest is."""
    directory = os.path.dirname(os.path.abspath(map_path)) or "."
    candidates = sorted(os.path.join(directory, name) for name in os.listdir(directory)
                        if name.startswith("corpus-manifest") and name.endswith(".json"))
    return candidates[0] if len(candidates) == 1 else None


def _inputs(args):
    document = _read(args.map_path, "map")
    path = args.protocol or protocol_step.path_beside(args.map_path)
    if not os.path.exists(path):
        raise protocol_step.Refused(
            f"no {protocol_step.PROTOCOL_FILENAME} beside {args.map_path}; a map with no protocol "
            f"is one that cannot say how its corpus was read (0032)")
    return document, path, protocol_step.load(path)


def command_protocol(args):
    document, path, protocol = _inputs(args)
    manifest_path = args.manifest or _find_manifest(args.map_path)
    manifest = _read(manifest_path, "manifest") if manifest_path else None
    problems = protocol_step.check(protocol, document, manifest)
    print(f"{path} (corpus {protocol.get('corpus')!r}, {len(entries_of(document))} entries in "
          f"{os.path.basename(args.map_path)}"
          + (f", manifest {os.path.basename(manifest_path)}" if manifest_path else ", no manifest")
          + ")")
    for line in problems:
        print(f"  X  {line}")
    if problems:
        print(f"\n{len(problems)} problem(s) in the protocol")
        return 1

    here, elsewhere = [], []
    for mechanism in protocol_step.mechanisms_of(protocol):
        name = mechanism.get("mechanism")
        (here if name in protocol_step.DETECTED_HERE else elsewhere).append(name)
    print(f"  units: {', '.join(protocol.get('units'))}")
    print(f"  pointers detected by `mapper pointers`: {', '.join(here) or 'none'}")
    for name in elsewhere:
        print(f"  pointers detected elsewhere: {name} -- "
              f"{protocol_step.DETECTED_ELSEWHERE[name]}")
    # Said out loud on every run, so a protocol cannot read as though its sweeps had run.
    print(f"  sweeps declared: {', '.join(protocol.get('requiredSweeps'))} "
          f"-- NOT RUN: no sweep is implemented (#250)")
    print(f"  adapter reach: "
          + ", ".join(f"{k}={v}" for k, v in sorted(protocol.get('adapterReach').items())))
    return 0


def command_pointers(args):
    document, path, protocol = _inputs(args)
    declared = protocol_step.mechanisms_of(protocol, "defined-term-use")
    print(f"{args.map_path} ({len(entries_of(document))} entries, protocol "
          f"{os.path.basename(path)})")
    if not declared:
        # Not a silent skip: a corpus that does not point this way says so, and the run says
        # which detector would have been used and was not.
        print("  this corpus declares no defined-term-use mechanism; nothing here detects the "
              "ways it does point")
        for mechanism in protocol_step.mechanisms_of(protocol):
            name = mechanism.get("mechanism")
            print(f"  {name}: {protocol_step.DETECTED_ELSEWHERE.get(name, 'detected here')}")
        return 0

    lines, detected, undeclared = pointers_step.report(protocol, document)
    for line in lines:
        print(line)
    if not detected:
        print("\nthis protocol declares defined-term-use and nothing fired; either the mechanism "
              "is wrong for this corpus or the map's evidence spans do not reach its pointers. "
              "A silent zero is not a pass (0026)", file=sys.stderr)
        return 1
    if undeclared:
        print(f"\nNOT VERIFIED: {len(undeclared)} naming(s) of a defined term that the entry "
              f"declares no crossReference for. Whether each is owed is decided by reading the "
              f"corpus (0026), not here")
        return NOT_VERIFIED
    print(f"\n{detected} naming(s), every one declared")
    return 0


def command_inventory(args):
    """What the extent claims, against what the walk reached (#255).

    The corpus comes from the manifest and not from the command line: the manifest is already
    the one place that says which adapter read this corpus and where the committed copy is, and
    a map inventoried against a corpus its manifest does not name would be measured against
    bytes nothing pinned.
    """
    document = _read(args.map_path, "map")
    manifest_path = args.manifest or _find_manifest(args.map_path)
    if manifest_path is None:
        raise protocol_step.Refused(
            f"no corpus manifest beside {args.map_path}; the manifest is what says which adapter "
            f"read this corpus and where the pinned bytes are")
    manifest = _read(manifest_path, "manifest")
    source = document.get("corpus")
    adapter = corpus_step.open_corpus(manifest, source,
                                      os.path.dirname(os.path.abspath(manifest_path)))
    extent = document.get("extent")
    if not isinstance(extent, dict):
        raise protocol_step.Refused(
            f"{args.map_path} declares no `extent`, so it claims no coverage and there is "
            f"nothing to inventory (0009)")
    units = adapter.units(extent)
    rejected = inventory_step.load_rejections(inventory_step.path_beside(args.map_path), source)
    taken = inventory_step.take(units, document, rejected)
    for line in inventory_step.lines(taken, os.path.basename(args.map_path), source, adapter.name,
                                     extent, show_all=args.list):
        print(line)

    if not units:
        print("\nthe extent enumerated no unit at all; an inventory of nothing accounts for "
              "nothing and is not a pass", file=sys.stderr)
        return 1
    if not taken.located:
        print("\nno entry's quoted evidence was found in the enumerated units, so every unit is "
              "unaccounted by default. Either the map's evidence is not quotation or the "
              "enumeration is of the wrong bytes; a silent zero is not a pass", file=sys.stderr)
        return 1
    if taken.problems:
        print(f"\n{len(taken.problems)} problem(s) with the recorded rejections")
        return 1
    if taken.unaccounted:
        print(f"\nNOT VERIFIED: {len(taken.unaccounted)} of {len(units)} unit(s) inside the "
              f"declared extent are reached by no entry's quote and recorded as examined by "
              f"nothing. Whether each owed an entry is decided by reading the corpus, not here")
        return NOT_VERIFIED
    print(f"\nall {len(units)} unit(s) of the declared extent are reached by a quote or recorded "
          f"as examined")
    return 0


COMMANDS = {"protocol": command_protocol, "pointers": command_pointers,
            "inventory": command_inventory}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mapper", description="The mapper subsystem (0032).")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("protocol", "check the mapping protocol governing a map"),
                            ("pointers", "detect the pointers the protocol says this corpus makes"),
                            ("inventory", "enumerate the extent's units and report what the walk "
                                          "reached")):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("map_path", help="the corpus map the protocol governs")
        if name != "inventory":
            sub.add_argument("--protocol", help=f"the protocol; "
                                                f"{protocol_step.PROTOCOL_FILENAME} beside the "
                                                f"map by default")
        if name in ("protocol", "inventory"):
            sub.add_argument("--manifest", help="corpus manifest; found beside the map when "
                                                "unambiguous")
        if name == "inventory":
            sub.add_argument("--list", action="store_true",
                             help="print every unaccounted unit, not the first ten")
    args = parser.parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except protocol_step.Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
