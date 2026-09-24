#!/usr/bin/env python3
"""A recorded mutation, run: edit, watch the named test, put the source back.

    tools/mutate.py <spec.json>... | -        one or more mutation specs, or stdin
    tools/mutate.py --no-baseline <spec>...   skip the unmutated run of each test
    tools/mutate.py -c Release <spec>...      a configuration other than Debug

Emitted by rules-factory as a managed file (decision 0029). `AGENTS.md` §7 is the rule this
serves; read that first.

**Why this exists.** `AGENTS.md` requires every test to record the mutation that makes it fail,
and says plainly what the placeholder floor cannot do: "it cannot tell whether the edit was made,
whether the test went red, or whether you copied the sentence from another entry. That is still
your word, and the point of writing it down is that a reviewer can re-run it." A reviewer cannot
re-run a sentence. A spec is the same claim in a form that runs, so the implementer's evidence and
the reviewer's check are one artefact instead of two readings of one paragraph.

It also names the failure the prose cannot: a mutation that leaves its test **green**. That is a
test nobody has watched fail, which is the whole thing the overlay's mutation record exists to
prevent, and until this it had no way to be reported.

**What a spec is.** One JSON object, or a list of them. Each names the test and the edits that
should turn it red:

    {"test": "WeatherTests.Neither_minimum_met_resolves_not_met",
     "edits": [{"file": "src/Engine/Rules/Weather.cs",
                "old": "!finding.BelowMet && !finding.HorizontalMet",
                "new": "finding.BelowMet && finding.HorizontalMet"}]}

`count` on an edit says how many occurrences of `old` are expected; the default is 1.

**What it refuses.** An `old` string that does not occur exactly `count` times, before anything is
written -- a mutation applied to the wrong site, or to nothing, proves nothing and the run would
still print a colour. The primary checkout, for the reason the rails block writes there at all.
Anything it cannot restore, loudly.

**Restoring is not best-effort.** The original bytes are held in memory and written back in a
`finally`, then read again and compared. An interrupted run leaves no mutated file, because the
one thing worse than no mutation evidence is a source tree quietly carrying a mutation.

**A mutation that does not compile is not a red test.** It is reported as its own outcome and
counts as a failure of the run: the test was never asked the question.

**Exit code.** 0 when every mutation turned its test red, and 1 otherwise -- green, did not
compile, no test matched, or refused. One non-zero for "the evidence AGENTS.md asks for was not
produced", because that is the only distinction a caller acts on; which of them it was is in the
output, loudly. Exit 2 stays argparse's, for a command called wrongly.

Writes nothing into the checkout (`AGENTS.md` §4), and standard library only -- it does not import
the vendored factory, so it leaves no bytecode behind either.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVENANCE = "provenance.json"
POLICY = ".github/agent-policy.json"
DEFAULT_ESCAPE_HATCH = "RULES_ENGINE_ALLOW_PRIMARY_MUTATION"

# What the run can conclude about one mutation. Only RED is the evidence AGENTS.md asks for.
RED = "RED"
GREEN = "GREEN"
NO_BUILD = "DID NOT COMPILE"
NO_TEST = "NO TEST MATCHED"


class Refused(Exception):
    """Something the run cannot honestly do. Nothing is left mutated."""


def read_json(path, what):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise Refused(f"{what} is missing: {path}")
    except (OSError, ValueError) as error:
        raise Refused(f"{what} cannot be read ({path}): {error}")


def escape_hatch():
    """The variable that lets a write into the primary checkout through, from the engine's policy.

    The name is configuration (`.github/agent-policy.json`), so the hook, the contract and this
    cannot each block on a different variable. An unreadable policy falls back to the default,
    exactly as `.claude/hooks/primary-checkout-guard.py` does: a guard that fails open on its own
    configuration is one an engine can disarm by corrupting a file.
    """
    try:
        document = read_json(ROOT / POLICY, POLICY)
        name = (document.get("worktrees") or {}).get("primaryMutationEscapeHatch")
        return name or DEFAULT_ESCAPE_HATCH
    except Refused:
        return DEFAULT_ESCAPE_HATCH


def in_primary_checkout():
    """True in the primary checkout, False in a worktree, False where git cannot say."""
    def ask(flag):
        result = subprocess.run(["git", "rev-parse", flag], cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return str((ROOT / result.stdout.strip()).resolve())

    common, own = ask("--git-common-dir"), ask("--git-dir")
    if common is None or own is None:
        return False
    return common == own


def engine_name():
    """The engine's own name, from its provenance -- never this file's bytes.

    A managed recipe is one fixed sequence of bytes for a recipe version (ownership.py), so it may
    not name the engine it is shipped into. `tools/entry-packet.py` and `tools/re-produce.sh` read
    the record for the same reason.
    """
    record = read_json(ROOT / PROVENANCE, PROVENANCE)
    name = (record.get("engine") or {}).get("name")
    if not name:
        raise Refused(f"{PROVENANCE} does not name this engine; run `factory produce` again")
    return name


def solution_for(name):
    path = ROOT / f"{name}.slnx"
    if not path.is_file():
        raise Refused(f"{PROVENANCE} names the engine {name}, and {name}.slnx is not here; "
                      f"run this from a produced engine")
    return path


def load_specs(sources):
    """Every spec named on the command line, in order, each checked for the shape it must have."""
    specs = []
    for source in sources:
        if source == "-":
            try:
                document = json.loads(sys.stdin.read())
            except ValueError as error:
                raise Refused(f"the spec on stdin is not JSON: {error}")
            where = "stdin"
        else:
            document = read_json(source, f"the spec {source}")
            where = source
        for index, spec in enumerate(document if isinstance(document, list) else [document]):
            specs.append(checked(spec, f"{where}[{index}]" if isinstance(document, list) else where))
    if not specs:
        raise Refused("no mutation spec was given; name one or more spec files, or `-` for stdin")
    return specs


def checked(spec, where):
    if not isinstance(spec, dict):
        raise Refused(f"{where} is not a JSON object")
    test = spec.get("test")
    if not isinstance(test, str) or not test.strip():
        raise Refused(f"{where} names no `test`; a mutation with no test to turn red proves nothing")
    edits = spec.get("edits")
    if not isinstance(edits, list) or not edits:
        raise Refused(f"{where} names no `edits`")
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            raise Refused(f"{where} edit {index} is not a JSON object")
        for key in ("file", "old", "new"):
            if not isinstance(edit.get(key), str):
                raise Refused(f"{where} edit {index} has no `{key}`")
        if edit["old"] == edit["new"]:
            raise Refused(f"{where} edit {index} replaces a string with itself, which mutates nothing")
        count = edit.get("count", 1)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise Refused(f"{where} edit {index} has a `count` that is not a positive integer")
    return spec


def apply(spec, where):
    """Apply every edit of one spec, or none of them. Returns [(path, original bytes)] to restore.

    The occurrence count is checked for **every** edit before the first byte is written, so a spec
    whose second edit is ambiguous does not leave the first one applied.
    """
    planned = []
    for index, edit in enumerate(spec["edits"]):
        path = (ROOT / edit["file"]).resolve()
        if not _within(path, ROOT):
            raise Refused(f"{where} edit {index} names {edit['file']}, which is outside this engine")
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, ValueError) as error:
            raise Refused(f"{where} edit {index} cannot read {edit['file']}: {error}")
        expected = edit.get("count", 1)
        found = original.count(edit["old"])
        if found != expected:
            raise Refused(f"{where} edit {index}: {_excerpt(edit['old'])} occurs {found} time(s) in "
                          f"{edit['file']}, expected {expected}. A mutation applied to the wrong site, "
                          f"or to nothing, proves nothing about the test.")
        planned.append((path, original, original.replace(edit["old"], edit["new"])))

    restore = [(path, original) for path, original, _ in planned]
    for path, _, mutated in planned:
        path.write_text(mutated, encoding="utf-8")
    return restore


def restore(pairs):
    """Put every file back and prove it went back. Returns the paths that did not."""
    failed = []
    for path, original in pairs:
        try:
            path.write_text(original, encoding="utf-8")
            if path.read_text(encoding="utf-8") != original:
                failed.append(path)
        except OSError:
            failed.append(path)
    return failed


def run_test(solution, test, configuration):
    """`dotnet test` filtered to one test. Returns (outcome, the line that says so)."""
    result = subprocess.run(
        ["dotnet", "test", str(solution.name), "-c", configuration, "--nologo",
         "--filter", f"FullyQualifiedName~{test}"],
        cwd=ROOT, capture_output=True, text=True)
    out = f"{result.stdout}\n{result.stderr}"
    lines = out.splitlines()

    compile_error = next((line.strip() for line in lines if "error CS" in line or "error MSB" in line), None)
    if compile_error:
        return NO_BUILD, compile_error
    failed = next((line.strip() for line in lines if line.startswith("Failed!")), None)
    if failed:
        return RED, failed
    passed = next((line.strip() for line in lines if line.startswith("Passed!")), None)
    if passed:
        if re.search(r"\bPassed:\s*0\b", passed) or "No test matches" in out:
            return NO_TEST, passed
        return GREEN, passed
    if "No test matches" in out or "no test is available" in out.lower():
        return NO_TEST, "no test matched the filter"
    return NO_TEST, (lines[-1].strip() if lines else f"dotnet test exited {result.returncode} and said nothing")


def _within(path, root):
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _excerpt(text, width=70):
    one_line = " ".join(text.split())
    return repr(one_line if len(one_line) <= width else one_line[:width] + "...")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run each recorded mutation and report whether it turns its test red.")
    parser.add_argument("specs", nargs="*", metavar="SPEC",
                        help="mutation spec files, or `-` to read one from stdin")
    parser.add_argument("-c", "--configuration", default="Debug",
                        help="build configuration for the test runs (default: Debug)")
    parser.add_argument("--no-baseline", action="store_true",
                        help="do not run each test unmutated first; a test already red proves nothing, "
                             "and the baseline is what rules that out")
    args = parser.parse_args(argv)

    try:
        if in_primary_checkout() and os.environ.get(escape_hatch()) != "1":
            raise Refused("this is the primary checkout, and this edits source files. Work in a worktree "
                          f"(`tools/dispatch-agent.sh <n>`, or AGENTS.md §4), or set {escape_hatch()}=1.")
        solution = solution_for(engine_name())
        specs = load_specs(args.specs or ["-"])
    except Refused as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 1

    results = []
    baselines = {}
    for number, spec in enumerate(specs, start=1):
        label = spec.get("name") or spec["test"]
        test = spec["test"]

        if not args.no_baseline and test not in baselines:
            outcome, line = run_test(solution, test, args.configuration)
            baselines[test] = outcome
            if outcome != GREEN:
                print(f"[{number}/{len(specs)}] {label}\n"
                      f"    BASELINE {outcome}: {line}", flush=True)
        if baselines.get(test, GREEN) != GREEN:
            results.append((label, f"BASELINE {baselines[test]}", "the test was not green before the mutation"))
            continue

        restore_pairs = []
        try:
            restore_pairs = apply(spec, f"spec {number}")
        except Refused as error:
            print(f"[{number}/{len(specs)}] {label}\n    REFUSED: {error}", file=sys.stderr, flush=True)
            results.append((label, "REFUSED", str(error)))
            continue
        try:
            outcome, line = run_test(solution, test, args.configuration)
        finally:
            failed = restore(restore_pairs)
            if failed:
                print("REFUSED: these files were mutated and could not be restored -- fix them before "
                      "anything else:\n  " + "\n  ".join(str(p) for p in failed), file=sys.stderr)
                return 1
        results.append((label, outcome, line))
        print(f"[{number}/{len(specs)}] {label}\n    {outcome}: {line}", flush=True)

    print()
    red = sum(1 for _, outcome, _ in results if outcome == RED)
    print(f"{len(results)} mutation(s): {red} red, {len(results) - red} not red")
    for label, outcome, line in results:
        if outcome != RED:
            print(f"  {outcome}  {label}")
    if red != len(results):
        print("\nA mutation that does not turn its test red is a test nobody has watched fail "
              "(AGENTS.md §7). Fix the test, or record a mutation that does.")
    return 0 if red == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
