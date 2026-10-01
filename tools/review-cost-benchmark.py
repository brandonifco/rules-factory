#!/usr/bin/env python3
"""How much a reviewer is handed across a repair chain, under the old model and under 0071's (#532).

    python3 tools/review-cost-benchmark.py [--rounds N] [--slice N] [--map examples/<map>/corpus-map.json ...]

**What it measures, and what it does not.** No token count: none is reliably available outside a
live session, and an invented one would be the kind of claim this repository refuses. It measures
what a reviewer is *handed* -- bytes, entries, implementation bytes, corpus evidence bytes -- which
is what a reviewer's context is made of, and it measures it deterministically, so two runs print
the same table and a later factory can be compared with this one.

**The engine.** Each map is a real one from `examples/`. Every entry of the slice is implemented the
way the generator's convention has it: one handler per file, every handler a member of one partial
class, resolving the entries it depends on (`dependsOn`, `enabledBy`, `suspendedBy`) through their
generated request types, and a third of them calling a helper another file of the same partial
class declares; each entry has one test file, resolving through the registry. That is the coupling
the map itself declares, written the way a produced engine writes it.

**The chain.** A full review at the first head fails with two findings. Each repair edits the file
of the entry a finding named; a round that is not the last fails again on a dependent of the
repaired entry (the interaction a repair most often breaks); the last passes.

  * the **old model** hands the reviewer a complete packet at every head: every entry of the slice,
    every implementation file of the slice, the whole base-to-head diff, the corpus evidence.
  * the **new model** hands a complete packet at the first head, a delta packet at each repair head
    (`reviewscope.render_delta_packet`, with the entry packets it names), and one complete packet at
    the end for the final acceptance review.

The complete packet is modelled with the same parts in both columns, so the comparison is of how
often it is handed over, not of how it is written. The delta packet is the real renderer's output.

Standard library only. Exit 0; `--check` exits 1 unless the new model hands over less, reviews the
whole slice at the end, and reuses evidence -- which is what its test holds it to.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_MAPS = ("examples/faa-part-107/corpus-map.json", "examples/hazmat-172-table/corpus-map.json",
                "examples/srd-52-combat/corpus-map.json")


_MODEL = []


def model():
    """The factory's review-evidence model, loaded once: the benchmark measures the code engines run."""
    if not _MODEL:
        spec = importlib.util.spec_from_file_location("reviewscope_benchmark",
                                                      os.path.join(HERE, "factory", "reviewscope.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODEL.append(module)
    return _MODEL[0]


def pascal(entry_id):
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[^A-Za-z0-9]+", entry_id) if part) or "Entry"


class Engine:
    """A deterministic engine over one map's first `size` entries."""

    def __init__(self, document, size):
        self.document = document
        entries = [e for e in document["entries"] if isinstance(e, dict) and e.get("id")]
        self.slice = [e["id"] for e in entries[:size]]
        self.entries = {}
        for entry in entries:
            implemented = entry["id"] in self.slice
            self.entries[entry["id"]] = {"entry": entry, "overlay": {
                "status": "implemented", "implementedIn": f"Handlers/{pascal(entry['id'])}.cs",
                "tests": [{"test": f"{pascal(entry['id'])}_Holds", "mutation": f"invert {entry['id']}"}]}
                if implemented else None}
        self.files = {"src/Engine/Handlers/Shared.cs": self.primitive(),
                      "src/Engine/Engine.csproj": b"<Project />\n"}
        for entry_id in self.slice:
            self.files[f"src/Engine/Handlers/{pascal(entry_id)}.cs"] = self.rule(entry_id)
            self.files[f"tests/Engine.Tests/{pascal(entry_id)}Tests.cs"] = self.test(entry_id)
        self.frame = {k: v for k, v in document.items() if k != "entries"}

    @staticmethod
    def primitive(revision=0):
        """A helper the handlers share, declared in the same partial class as they are."""
        return (f"namespace Engine;\n\ninternal static partial class Handlers\n{{\n"
                f"    private static bool Within(int value, int low, int high) => value >= low + {revision} && value <= high;\n"
                f"}}\n").encode()

    def uses(self, entry_id):
        entry = self.entries[entry_id]["entry"]
        return [d for d in (entry.get("dependsOn") or []) + (entry.get("enabledBy") or [])
                + (entry.get("suspendedBy") or []) if d in self.slice]

    def rule(self, entry_id, revision=0):
        """One entry's handler, as the generator's convention writes it: a member of the one partial
        class every handler shares, resolving what it depends on through their request types."""
        entry = self.entries[entry_id]["entry"]
        member = pascal(entry_id)
        calls = "".join(f"        if (!{pascal(d)}(new {pascal(d)}Request(request.Value)).IsAllowed) "
                        f"return Resolution<bool>.Unresolved(\"{d}\");\n" for d in self.uses(entry_id))
        if self.slice.index(entry_id) % 3 == 0:
            calls += "        if (!Within(request.Value, 0, 400)) return Resolution<bool>.Refused(\"bound\");\n"
        body = (f"// {entry.get('name', entry_id)} -- {json.dumps((entry.get('locator') or {}).get('citation'))}\n"
                f"namespace Engine;\n\ninternal static partial class Handlers\n{{\n"
                f"    internal static partial Resolution<bool> {member}({member}Request request)\n    {{\n"
                f"        if (request is null) return Resolution<bool>.Refused(\"null request\");\n{calls}"
                f"        return request.Value >= {revision} ? Resolution<bool>.Allowed : "
                f"Resolution<bool>.Refused(\"{entry_id}\");\n    }}\n}}\n")
        return body.encode()

    def test(self, entry_id):
        name = pascal(entry_id)
        return (f"namespace Engine.Tests;\n\npublic class {name}Tests\n{{\n    [Fact]\n    public void {name}_Holds() =>\n"
                f"        Assert.True(Registry.Resolve(new {name}Request(1)).IsAllowed);\n}}\n").encode()

    def repair(self, entry_id, revision):
        path = f"src/Engine/Handlers/{pascal(entry_id)}.cs"
        before = self.files[path]
        self.files[path] = after = self.rule(entry_id, revision)
        return path, before, after

    def snapshot(self, m):
        return m.Snapshot(entries=self.entries, slice=self.slice, files=self.files,
                          maps=[{"packageId": "Map", "version": "1", "sha256": "0" * 64, "frame": self.frame}],
                          corpora={str(self.document.get("corpus")): "0" * 64}, charter="c" * 64,
                          policy_review="p" * 64, factory="f" * 40)


def entry_packet(merged):
    """A proxy for `tools/entry-packet.py`'s output: the entry and its overlay row, as the map has them."""
    return json.dumps(merged, indent=2, sort_keys=True, ensure_ascii=False)


def evidence_bytes(engine, entries):
    return sum(len(str(engine.entries[e]["entry"].get("evidence") or "").encode()) for e in entries)


def full_packet(engine):
    """What a complete semantic packet hands a reviewer: every entry, every file of the slice's
    implementation (the whole base-to-head diff adds each of them), and the corpus evidence."""
    entries = [entry_packet(engine.entries[e]) for e in engine.slice]
    implementation = [data for path, data in sorted(engine.files.items()) if path.endswith(".cs")]
    text = "\n".join(entries)
    return {"bytes": len(text.encode()) + sum(len(d) for d in implementation),
            "entries": len(engine.slice), "implementationBytes": sum(len(d) for d in implementation),
            "corpusBytes": evidence_bytes(engine, engine.slice)}


def delta_packet(m, engine, prior, current, result, changes, head):
    review_entries = [c[len("entry:"):] for c in result["review"] if c.startswith("entry:")]
    closure = sorted({u[len("file:"):] for c in result["review"] if c in current["claims"]
                      for u in current["claims"][c] if u.startswith("file:")})
    diff = "\n".join(f"--- a/{path}\n+++ b/{path}\n-{before.decode()}\n+{after.decode()}" for path, before, after in changes
                     if path in closure)
    packets = [entry_packet(engine.entries[e]) for e in review_entries]
    text = m.render_delta_packet(
        prior=prior, prior_digest=m.attestation_digest(prior), head=head, base="0" * 40, current=current,
        impact_record=result, entry_packets=[(e, f"entry-{e}.md", m.sha256(p.encode())) for e, p in
                                             zip(review_entries, packets)],
        diff=f"```diff\n{diff}\n```" if diff else "", closure_files={p: current["units"][f"file:{p}"] for p in closure},
        locators={e: engine.entries[e]["entry"].get("locator") for e in review_entries},
        tests={e: (engine.entries[e]["overlay"] or {}).get("tests") or [] for e in review_entries})
    measured = m.measure(text, packets)
    return {"bytes": measured["bytes"], "entries": len(review_entries),
            "implementationBytes": len(diff.encode()), "corpusBytes": evidence_bytes(engine, review_entries)}


def attest(m, current, head, kind, result, parent=None, impact=None, blocking=()):
    return m.build_attestation(project={"engine": "Engine"}, reviewed_commit=head, base_commit="0" * 40,
                               review_type=kind, reviewer={"id": "semantic"}, charter={}, packet={}, maps=[],
                               corpora=[], current=current, result=result, blocking=blocking, parent=parent,
                               impact_record=impact or {})


def dependents(engine, entry_id):
    return [e for e in engine.slice if e != entry_id and entry_id in m_closure(engine, e)]


def m_closure(engine, entry_id):
    return model().entry_closure(engine.entries, entry_id)


def run(path, rounds, size, where="local"):
    m = model()
    with open(os.path.join(REPO, path), encoding="utf-8") as handle:
        document = json.load(handle)
    engine = Engine(document, size)
    heads = [f"{n:040x}" for n in range(1, rounds + 3)]
    state = m.state(engine.snapshot(m))
    # Where the findings land. `local`: the two entries of the slice fewest others rest on -- the
    # ordinary defect, in one rule's own reading. `hub`: the two most rested on -- a shared rule a
    # misreading of which reaches everything above it, which is the worst case for a bounded review
    # and is reported beside the ordinary one rather than instead of it.
    ranked = sorted(engine.slice, key=lambda e: (len(dependents(engine, e)) * (1 if where == "local" else -1),
                                                   engine.slice.index(e)))
    targets = ranked[:2]
    blocking = [{"claim": f"entry:{e}", "summary": f"{e} misreads its bound", "category": "exact-min-max"}
                for e in targets]
    old = [full_packet(engine)]
    new = [dict(full_packet(engine), kind="full")]
    prior = attest(m, state, heads[0], "full", "FAIL", impact=m.impact(None, state), blocking=blocking)
    reused = 0
    for number in range(1, rounds + 1):
        changes = [engine.repair(finding["claim"][len("entry:"):], number) for finding in blocking]
        head = heads[number]
        current = m.state(engine.snapshot(m))
        result = m.impact(prior, current)
        old.append(full_packet(engine))
        if result["mode"] == "full":
            new.append(dict(full_packet(engine), kind="full", reasons=[r["code"] for r in result["reasons"]]))
            kind = "full"
        else:
            new.append(dict(delta_packet(m, engine, prior, current, result, changes, head), kind="delta"))
            kind = "delta"
        reused += len(result["retained"])
        last = number == rounds
        repaired = [f["claim"][len("entry:"):] for f in blocking]
        following = [e for r in repaired for e in dependents(engine, r) if f"entry:{e}" in result["review"]]
        blocking = [] if last else [{"claim": f"entry:{(following or repaired)[0]}",
                                     "summary": "a dependent still reads the old bound", "category": "exact-min-max"}]
        prior = attest(m, current, head, kind, "PASS" if last else "FAIL", parent=prior,
                       impact=result if kind == "delta" else dict(result), blocking=blocking)
    # The final acceptance review follows a delta PASS. A full review that passed already read the
    # whole slice at the head being merged, and is its own acceptance.
    if prior["reviewType"] == "delta":
        final = attest(m, m.state(engine.snapshot(m)), heads[rounds], "final", "PASS", parent=prior,
                       impact={"reasons": []})
        new.append(dict(full_packet(engine), kind="final"))
    else:
        final = prior
    problems = m.validate_attestation(final)
    return {"map": path, "where": where, "entries": len(engine.slice), "rounds": rounds, "old": old, "new": new,
            "reused": reused, "finalCoversSlice": sorted(final["reviewed"]["entries"]) == sorted(engine.slice),
            "finalProblems": problems,
            "fullReasons": sorted({code for r in new for code in r.get("reasons") or []})}


def totals(rows):
    return {key: sum(r[key] for r in rows) for key in ("bytes", "entries", "implementationBytes", "corpusBytes")}


def full_bytes(result):
    return result["old"][0]["bytes"]


def table(results):
    lines = ["| map | findings | repairs | model | packets | comprehensive | bytes presented | entries presented "
             "| implementation bytes | corpus bytes | claims reused | full-review reasons |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for result in results:
        old, new = totals(result["old"]), totals(result["new"])
        comprehensive = sum(1 for r in result["new"] if r["kind"] in ("full", "final"))
        name = result["map"].split("/")[1]
        lines.append(f"| {name} | {result['where']} | {result['rounds']} | old | {len(result['old'])} | "
                     f"{len(result['old'])} | {old['bytes']:,} | {old['entries']} | {old['implementationBytes']:,} | "
                     f"{old['corpusBytes']:,} | 0 | — |")
        lines.append(f"| {name} | {result['where']} | {result['rounds']} | new | {len(result['new'])} | "
                     f"{comprehensive} | {new['bytes']:,} ({new['bytes'] / old['bytes']:.0%}) | {new['entries']} | "
                     f"{new['implementationBytes']:,} | {new['corpusBytes']:,} | {result['reused']} | "
                     f"{', '.join(result['fullReasons']) or '—'} |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="review-cost-benchmark.py", description=__doc__.split("\n")[0])
    parser.add_argument("--map", action="append", default=[])
    parser.add_argument("--rounds", type=int, action="append", default=[])
    parser.add_argument("--slice", type=int, default=24, help="entries of the map the pull request claims")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    results = [run(path, rounds, args.slice, where) for path in (args.map or DEFAULT_MAPS)
               for where in ("local", "hub") for rounds in (args.rounds or (2, 7))]
    print(f"slice of {args.slice} entries per map; old = a complete packet at every head, new = 0071's chain\n")
    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(table(results))
    if args.check:
        # Never more than the old model hands over, beyond the one final review a delta chain adds;
        # less on every chain whose repairs could be bounded; and a whole-slice acceptance at the end.
        failures = [f"{r['map']} ({r['where']}, {r['rounds']})" for r in results
                    if not r["finalCoversSlice"] or r["finalProblems"]
                    or totals(r["new"])["bytes"] > totals(r["old"])["bytes"] + full_bytes(r)
                    or (r["where"] == "local" and r["rounds"] > 2 and totals(r["new"])["bytes"] >= totals(r["old"])["bytes"])]
        if failures:
            print(f"review-cost-benchmark: FAILED for {', '.join(failures)}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
