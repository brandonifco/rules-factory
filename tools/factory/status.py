"""What can be said about a produced engine right now, from what it already records (#585).

  python3 tools/factory status --engine <engine dir> [--json] [--package <nupkg path | Id@Version>]

A reporter, not a judge. Every number and every fact here comes from the trace (trace.py) of the
same engine, or from `provenance.json` through the trace's reader, so there is no second reader of
the overlay, the map or the record to disagree with the first. What `status` adds is a short page:
the engine, its inputs, how much of it is implemented and named-tested, how many gaps the trace
found, what provenance recorded about the produce that wrote it, and whether the working tree has
moved since a commit.

**No verdict.** There is no "overall", no score and no severity. The factory already has an
authority for whether an engine is acceptable -- `factory verify`, which runs provenance, restore
and the engine's own gate -- and a summary that issued a second verdict would be a second authority
that can disagree with it. So:

  * provenance's `verification` is reported as what it is: a recorded fact about **the produce that
    wrote the record**. It says nothing about the tree as it stands, and the report says so;
  * a clean working tree is reported as a git fact and never as "verified";
  * the report says verification was **not run by this invocation**.

**Read-only.** No restore, no build, no gate, no network, nothing written: the git
fact is asked with `--no-optional-locks`, so even git's index refresh is not written. Standard
library only.
"""
import os
import subprocess

import trace as trace_step

FORMAT = 1
NOT_RUN = ("not run by this invocation: nothing here says whether the current tree passes; "
           "`factory verify` is the authority")
HISTORICAL = ("a recorded fact about the produce that wrote provenance.json, not about the tree as it stands; "
              "only `factory verify` answers for the current tree")


def counted(trace, basis="counted from the trace of this engine (factory trace)"):
    """The implementation section: counts over the trace's own entries, and the trace's own summary."""
    by_status = {}
    tests = mutations = 0
    for entry in trace["entries"]:
        status = entry["status"]["value"]
        by_status[str(status)] = by_status.get(str(status), 0) + 1
        for test in entry["tests"]:
            tests += 1
            mutations += test["mutation"]["evidence"] == "recorded"
    return {"basis": basis, "entries": len(trace["entries"]), "byStatus": dict(sorted(by_status.items())),
            "namedTests": tests, "mutationsRecorded": mutations,
            "evidence": trace["summary"]["evidence"], "gaps": trace["summary"]["gaps"]}


def working_tree(engine_dir):
    """Whether git sees uncommitted changes under the engine: a git fact, asked without writing."""
    try:
        done = subprocess.run(["git", "--no-optional-locks", "-C", engine_dir, "status", "--porcelain=v1",
                               "--untracked-files=normal", "--", "."],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        return trace_step.unknown(f"git could not be asked about the working tree ({error})")
    if done.returncode != 0:
        return trace_step.unknown("the engine directory is in no git work tree, so nothing says whether it has "
                                  "moved since a commit")
    changed = [line for line in done.stdout.split("\n") if line.strip()]
    value = {"clean": not changed, "changedPaths": len(changed)}
    return trace_step.derived(value, "git --no-optional-locks status --porcelain -- <engine>; a clean tree is a git "
                                     "fact and is not a verification")


def build(engine_dir, package=None):
    """The status of the engine at `engine_dir`, read-only, as plain data."""
    trace = trace_step.build(engine_dir, package)
    record = trace_step.read_record(engine_dir)
    gaps = []
    verification = record.get("verification")
    recorded = {
        "verified": trace_step.held(verification, "verified", "provenance.json verification.verified",
                                    "provenance", gaps),
        "ran": trace_step.held(verification, "ran", "provenance.json verification.ran", "provenance", gaps),
        "scope": HISTORICAL,
    }
    factory = record.get("factory")
    return {
        "statusFormat": FORMAT,
        "engine": {"name": trace["engine"]["name"], "distribution": trace["engine"]["distribution"],
                   "kernel": trace["engine"]["kernel"], "topology": trace["topology"]},
        "inputs": {
            "maps": [{"packageId": m["packageId"], "version": m["version"]} for m in trace["maps"]],
            "corpora": [{k: c[k] for k in ("sourceId", "contentHash", "asOf") if k in c} for c in trace["corpora"]],
        },
        "implementation": counted(trace),
        "provenance": {
            "format": trace["engine"]["provenanceFormat"],
            "factory": {"version": trace["engine"]["factory"]["version"],
                        "commit": trace["engine"]["factory"]["commit"],
                        "dirty": trace_step.held(factory, "dirty", "provenance.json factory.dirty", "provenance",
                                                 gaps)},
            "verification": recorded,
        },
        "currentTree": working_tree(engine_dir),
        "verification": {"ranNow": False, "says": NOT_RUN},
        "gaps": gaps,
    }


def text(status):
    """The human page: the same data, in lines."""
    def value(node):
        if not isinstance(node, dict) or "evidence" not in node:
            return str(node)
        if node["evidence"] == "unknown":
            return f"UNKNOWN ({node['why']})"
        shown = node["value"]
        return f"{shown}  [{node['evidence']}]"

    engine, inputs, done = status["engine"], status["inputs"], status["implementation"]
    topology = engine["topology"]
    out = [f"engine        {value(engine['name'])}",
           f"distribution  {value(engine['distribution'])}",
           f"kernel        {value(engine['kernel']['packageId'])} {value(engine['kernel']['version'])}",
           f"topology      recorded enginePath {value(topology['recordedEnginePath'])}; observed "
           f"{value(topology['observedEnginePath'])}; agree: {topology['agrees']}"]
    for package in inputs["maps"]:
        out.append(f"map           {value(package['packageId'])} {value(package['version'])}")
    for corpus in inputs["corpora"]:
        out.append(f"corpus        {value(corpus.get('sourceId'))} contentHash {value(corpus.get('contentHash'))}")
    out.append(f"entries       {done['entries']}: " + ", ".join(f"{n} {s}" for s, n in done["byStatus"].items()))
    out.append(f"named tests   {done['namedTests']}, {done['mutationsRecorded']} with a recorded mutation")
    out.append("evidence      " + ", ".join(f"{n} {c}" for c, n in done["evidence"].items()))
    out.append("trace gaps    " + (", ".join(f"{n} {r}" for r, n in done["gaps"].items()) or "none"))
    provenance = status["provenance"]
    out.append(f"provenance    format {value(provenance['format'])}; factory {value(provenance['factory']['version'])}")
    out.append(f"produced as   verified {value(provenance['verification']['verified'])} -- "
               f"{provenance['verification']['scope']}")
    tree = status["currentTree"]
    if tree["evidence"] == "unknown":
        out.append(f"working tree  {value(tree)}")
    else:
        moved = tree["value"]
        out.append("working tree  " + ("clean" if moved["clean"] else f"{moved['changedPaths']} changed path(s)")
                   + " [git] -- not a verification")
    out.append(f"verification  {status['verification']['says']}")
    for gap in status["gaps"]:
        out.append(f"gap           {gap['subject']} {gap['relationship']}: {gap['why']}")
    return "\n".join(out) + "\n"
