"""What can be said about a produced engine right now, from what it already records (#585).

  python3 tools/factory status --engine <engine dir> [--json] [--package <nupkg path | Id@Version>]
  python3 tools/factory status --engine <engine dir> --verify [--json] [--package ...]

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
  * without `--verify` the report says verification was **not run by this invocation**.

**`--verify` delegates (#586).** It runs `factory verify` itself, by its own command line in this
process -- the same parser, stages, refusals and exit codes -- and reports that it ran now, which
authority ran, the exit code and the verifier's last line. The exit code of `status --verify` is
the verifier's. Nothing here knows what `verify` checks, so a new rule there changes what this
reports with no edit here. `verify` restores and may write lock files: `--verify` is not the
read-only mode, and the read-only part of the report is computed before it runs.

**Read-only by default.** No restore, no build, no gate, no network, and nothing written in the
engine or its repository: the git fact is asked with `--no-optional-locks`, so even git's index
refresh is not written. That is the whole claim. Under `python3 tools/factory ...` CPython may
compile the entry point to bytecode in the factory's own checkout, and `provenance.
discard_entry_point_bytecode` deletes it (#373): that is every factory command's, and not a write
to the engine. Standard library only.
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


def _git(engine_dir, *args):
    """(exit code, stdout, stderr) of a read-only git command in the engine, or None when git cannot run."""
    try:
        done = subprocess.run(["git", "--no-optional-locks", "-C", engine_dir, *args],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.returncode, done.stdout, done.stderr.strip()


def working_tree(engine_dir):
    """Whether git sees uncommitted changes under the engine: a git fact, asked without writing.

    Clean is said only of an engine git tracks. An engine git has never been told about -- one the
    repository ignores, or one never committed -- shows no changes and has no commit to be clean
    against, so it is unknown.
    """
    tracked = _git(engine_dir, "ls-files", "--", ".")
    if tracked is None:
        return trace_step.unknown("git could not be run, so nothing says whether the tree has moved since a commit")
    if tracked[0] != 0:
        return trace_step.unknown(f"git could not read the engine's repository ({tracked[2] or 'no message'}), so "
                                  f"nothing says whether the tree has moved since a commit")
    if not tracked[1].strip():
        return trace_step.unknown("git tracks no file under the engine (it is ignored, or never committed), so there "
                                  "is no commit for the tree to be clean against")
    done = _git(engine_dir, "status", "--porcelain=v1", "--untracked-files=normal", "--", ".")
    if done is None or done[0] != 0:
        return trace_step.unknown(f"git could not report the working tree ({(done or (0, '', ''))[2] or 'no message'})")
    changed = [line for line in done[1].split("\n") if line.strip()]
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


def ran(exit_code, output, engine_dir):
    """What `factory verify` said when `--verify` ran it: that it ran now, who, its exit code, its last line."""
    lines = [line for line in output.split("\n") if line.strip()]
    return {"ranNow": True, "authority": f"factory verify --engine {engine_dir}", "exitCode": exit_code,
            "lastLine": lines[-1] if lines else None,
            "says": "the verifier's own result, unchanged; its exit code is this command's exit code. Everything "
                    "else on this page was read before it ran, and verify may have written lock files since"}


def refused(why):
    """The report when the engine's records could not be read, and `--verify` asks the verifier anyway."""
    return {"statusFormat": FORMAT, "refused": why, "verification": {"ranNow": False, "says": NOT_RUN}}


def text(status):
    if "refused" in status:
        check = status["verification"]
        return (f"status        REFUSED: {status['refused']}\n"
                f"verification  ran now by {check['authority']}: exit {check['exitCode']}; it said: "
                f"{check['lastLine']}\n") if check["ranNow"] else f"status        REFUSED: {status['refused']}\n"
    return _page(status)


def _page(status):
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
        out.append(f"corpus        {value(corpus.get('sourceId'))} contentHash {value(corpus.get('contentHash'))} "
                   f"asOf {value(corpus.get('asOf'))}")
    out.append(f"entries       {done['entries']}: " + ", ".join(f"{n} {s}" for s, n in done["byStatus"].items()))
    out.append(f"named tests   {done['namedTests']}, {done['mutationsRecorded']} with a recorded mutation")
    out.append("evidence      " + ", ".join(f"{n} {c}" for c, n in done["evidence"].items()))
    out.append("trace gaps    " + (", ".join(f"{n} {r}" for r, n in done["gaps"].items()) or "none"))
    provenance = status["provenance"]
    factory = provenance["factory"]
    out.append(f"provenance    format {value(provenance['format'])}; factory {value(factory['version'])} at "
               f"{value(factory['commit'])}, dirty {value(factory['dirty'])}")
    out.append(f"at produce    provenance records verification.verified = {value(provenance['verification']['verified'])}, "
               f"ran {value(provenance['verification']['ran'])} -- {provenance['verification']['scope']}")
    tree = status["currentTree"]
    if tree["evidence"] == "unknown":
        out.append(f"working tree  {value(tree)}")
    else:
        moved = tree["value"]
        out.append("working tree  " + ("clean" if moved["clean"] else f"{moved['changedPaths']} changed path(s)")
                   + " [git] -- not a verification")
    check = status["verification"]
    if check["ranNow"]:
        out.append(f"verification  ran now by {check['authority']}: exit {check['exitCode']}; it said: "
                   f"{check['lastLine']}")
    else:
        out.append(f"verification  {check['says']}")
    for gap in status["gaps"]:
        out.append(f"gap           {gap['relationship']}: {gap['why']}")
    return "\n".join(out) + "\n"
