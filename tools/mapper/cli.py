"""The mapper's command line.

What is here is the part of the method that is mechanical. `protocol` says whether a corpus's
protocol is one this mapper can act on, `pointers` performs the interrogation the protocol
obliges and reports what it found, `inventory` enumerates the units inside the declared extent
and reports which of them the walk reached (#255), and `stage` produces the inputs a blind
second mapping is given -- the documents with every worked example drawn from the corpus under
mapping removed -- and, with `--verify`, holds a committed run to the digests of what it was
given (#223). Producing a map is still done by hand (docs/method.md); what this makes checkable
is that the walk was the walk this corpus requires, how much of the extent it covered, and that
a second walk was blind.

Four exit codes, the factory's four (README, *What the factory exits with*), because a caller
that reads only `$?` must be able to tell what happened:

  0  every declaration held, and something was actually examined
  1  a declaration is wrong, or an interrogation that was declared detected nothing at all
  2  a usage error
  3  NOT VERIFIED: the run found what it cannot judge -- a pointer the map does not declare, or
     a unit inside the declared extent that no entry's quote reaches and no rejection accounts
     for. Whether each one is owed is 0026's question, decided by reading the corpus, and this
     tool does not decide it. Not a pass, not a failure, and never silent.
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
from mapper import staging as staging_step

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


def command_stage(args):
    """Stage the inputs a blind second mapping is given, or hold a staged run to them (#223).

    Two directions over one record, because they are one claim: `stage` writes the redacted
    documents and the digests of what it wrote, and `--verify` re-hashes those files and re-runs
    the scan over them. The second is what `scripts/validate.sh` runs on every committed record,
    so a run whose inputs were not the redacted ones is visibly not a blind run.
    """
    if args.verify:
        problems, notes, checked = staging_step.verify(args.spec)
        print(f"{args.spec}")
        for note in notes:
            print(f"  --  {note}")
        for problem in problems:
            print(f"  X  {problem}")
        if problems:
            print(f"\n{len(problems)} problem(s): this is not a record of a blind staging")
            return 1
        if checked == 0:
            print("nothing was hashed or scanned -- this record proved nothing", file=sys.stderr)
            return 1
        print(f"  ok  {checked} file(s) hashed and re-scanned against the vocabulary recorded")
        return 0

    out = args.out or os.path.dirname(os.path.abspath(args.spec))
    record, problems, unresolved = staging_step.stage(args.spec, out, args.corpus_root)
    print(f"{args.spec} -> {out} (corpus {record['corpus']!r}, "
          f"{len(record['vocabularyFrom'])} map(s) of it)")
    for document in record["documents"]:
        print(f"  {document['name']}: {document['edits']} edit(s), sha256 {document['sha256']}")
    for ack in record["acknowledged"]:
        print(f"  named and left in: {ack['document']} {ack['term']!r} x{ack['occurrences']}")
    for problem in problems:
        print(f"  X  {problem}")
    # Printed whatever the verdict is: a run with a leak in it still has to be told what else it
    # will have to rule on, or the next run finds them one at a time.
    for item in unresolved:
        print(f"  ?  {item['document']}:{item['line']}: {item['term']!r} is named by this "
              f"corpus's maps and is a word a document uses for its own reasons")
    print("  what this did not look for:")
    for limit in staging_step.LIMITS:
        print(f"    - {limit}")
    if problems:
        print(f"\n{len(problems)} problem(s): these documents are not staged")
        return 1
    if unresolved:
        print(f"\nNOT VERIFIED: {len(unresolved)} occurrence(s) this cannot decide. Each is either "
              f"an example to edit away or an acknowledgement to declare, with a reason")
        return NOT_VERIFIED
    print(f"\nstaged: nothing the corpus's maps coin is left in, "
          f"{record['residue']['acknowledged']} occurrence(s) named and left in on purpose")
    return 0


COMMANDS = {"protocol": command_protocol, "pointers": command_pointers,
            "inventory": command_inventory, "stage": command_stage}


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
    # `stage` takes a staging spec and not a map: the map is one of the things the spec names
    # (#223). Its own parser rather than another arm of the loop above, because it shares no
    # argument with the three that read a map.
    stage = subparsers.add_parser("stage", help="stage the inputs a blind second mapping is given")
    stage.add_argument("spec", help=f"the staging spec, or with --verify a "
                                    f"{staging_step.RECORD_FILENAME} to check")
    stage.add_argument("--out", help="where the bundle is written; beside the spec by default")
    stage.add_argument("--corpus-root", help="where the corpus's other maps are looked for; two "
                                             "levels above the map by default")
    stage.add_argument("--verify", action="store_true",
                       help="check a committed record against the files beside it")
    args = parser.parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except protocol_step.Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
