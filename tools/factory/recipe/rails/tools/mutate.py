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

`count` on an edit says how many occurrences of `old` are expected; the default is 1. Edits apply
in the order they are named, each to the text the earlier ones left, so a spec may edit one file
several times.

**What it matches.** Plain substring search on the text of a file exactly as it is on disk: decoded
as UTF-8 with no newline translation. A CR LF line ending is therefore two characters, so an `old`
that spans a line ending must name the file's own ending (CR LF in a CR LF file), and an `old` of LF
alone also matches the LF inside a CR LF. There is no line-ending special case.

**What it refuses**, before anything is written:

- An empty `old`: it names no site.
- An `old` string that does not occur exactly `count` times -- counted in the text the spec's
  earlier edits left, not in the file as it was read: a mutation applied to the wrong site, or to
  nothing, proves nothing and the run would still print a colour.
- An `old` whose occurrences overlap one another (`aa` in `aaa`): the site is ambiguous.
- An `old` any occurrence of which overlaps text an earlier edit of the same spec wrote, for the
  same reason: it edits the mutation, not the code.
- Replacement text that cannot be written as UTF-8, so a bad `new` never leaves a file half
  written.
- A spec whose edits cancel out, so that every file it names would be written with the bytes it
  already holds: the test would run against the unmutated source, and a red result would be
  certified as an observed mutation.
- The primary checkout, for the reason the rails block writes there at all.

Two names for one file (a hard link) are one file, and are edited as one; each name the spec
gave is restored. If a write fails anyway, or is interrupted, every file already written is put back
before the failure is raised. Anything it cannot restore, it says loudly.

**Restoring is not best-effort.** The original bytes are held in memory and written back in a
`finally`, byte for byte, then read again and compared. An interrupted run leaves no mutated file:
an interrupt (^C) in the middle of applying or restoring finishes putting every file back before it
is raised again, and SIGTERM, and SIGHUP where the platform has it (a closed terminal sends it in
the middle of a long test run), are turned into the same interrupt from just before the first write
until the last file is back. (SIGKILL cannot be caught, and nothing here pretends otherwise.) An
interrupt is reported as having left the source as it was only after every file the spec names has
been read again and found byte for byte what it was before the run; otherwise the files that differ
are listed, and the exit is 1. The one thing worse than no mutation evidence is a source tree quietly carrying a mutation.

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
import signal
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


class NotRestored(Refused):
    """A file was mutated and could not be put back. Unlike the rest, this stops the whole run."""


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
        if edit["old"] == "":
            raise Refused(f"{where} edit {index} has an empty `old`, which names no site")
        if edit["old"] == edit["new"]:
            raise Refused(f"{where} edit {index} replaces a string with itself, which mutates nothing")
        count = edit.get("count", 1)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise Refused(f"{where} edit {index} has a `count` that is not a positive integer")
    return spec


def apply(spec, where):
    """Apply every edit of one spec, or none of them. Returns [(path, original bytes)] to restore.

    Edits are applied in the order the spec names them, each to what the earlier ones left: the
    occurrences of `old` are counted in that text, not in the file as it was read. A file the spec
    edits twice is read once, and the pair returned for it holds the bytes from before any edit.
    Files are told apart by what they are (device and inode), not by the name a spec gave them, so
    two names for one file are one file, planned and written once. The pairs returned hold one entry
    for every distinct path the spec named, aliases sharing the same original bytes, because the run
    may replace one name with another inode and restoring "the file" would then miss the other name.

    An edit is refused when its `old` does not occur exactly `count` times in that text, when two
    occurrences of it overlap one another (the site is ambiguous), and when any occurrence of it
    overlaps text an earlier edit of the same spec wrote: that is an edit to the mutation, not to
    the code the test is about, and no one reading the source could have written it. Every check,
    for every edit, and the encoding of every file, is made before the first byte is written, so a
    spec whose later edit is refused does not leave an earlier one applied. So is the last check: a
    spec whose planned text equals the original bytes of every file it names (`a` to `ab`, then `bc`
    to `c`, in `abbc`) changes nothing, and is refused.

    If a write fails after all that, or is interrupted (any BaseException, a ^C or a SIGTERM that
    main() turned into one), every file already written is put back from its original bytes before
    the failure is raised, so neither leaves a half-applied spec.
    """
    texts = {}      # file identity -> the text so far, after the earlier edits of this spec
    paths = {}      # file identity -> every distinct path the spec named it by, in order
    originals = {}  # file identity -> the bytes before any edit, in the order the files first appear
    written = {}    # file identity -> [(start, end, index of the edit that wrote it)] in its text
    for index, edit in enumerate(spec["edits"]):
        path = (ROOT / edit["file"]).resolve()
        if not _within(path, ROOT):
            raise Refused(f"{where} edit {index} names {edit['file']}, which is outside this engine")
        try:
            status = path.stat()
            identity = (status.st_dev, status.st_ino)
            if identity not in texts:
                raw = path.read_bytes()
                # Decoded and matched exactly as it is on disk: no newline translation, so CR LF is
                # two characters, and an `old` holding LF alone matches the LF inside it.
                texts[identity] = raw.decode("utf-8")
                originals[identity], paths[identity], written[identity] = raw, [], []
            if path not in paths[identity]:
                paths[identity].append(path)
        except (OSError, ValueError) as error:
            raise Refused(f"{where} edit {index} cannot read {edit['file']}: {error}")
        text, spans = texts[identity], written[identity]
        expected = edit.get("count", 1)
        # Overlap allowed: `aa` occurs twice in `aaa`, and a search that skips past a match would
        # report one.
        hits = [(m.start(), m.start() + len(edit["old"]))
                for m in re.finditer("(?=" + re.escape(edit["old"]) + ")", text)]
        for (_, earlier_end), (later_start, _) in zip(hits, hits[1:]):
            if later_start < earlier_end:
                raise Refused(f"{where} edit {index}: occurrences of {_excerpt(edit['old'])} in "
                              f"{edit['file']} overlap one another, so the site is ambiguous. Name "
                              f"more of the text around it.")
        if len(hits) != expected:
            after = f" as edit(s) {', '.join(str(n) for n in sorted({s[2] for s in spans}))} leave it" if spans else ""
            raise Refused(f"{where} edit {index}: {_excerpt(edit['old'])} occurs {len(hits)} time(s) in "
                          f"{edit['file']}{after}, expected {expected}. A mutation applied to the wrong "
                          f"site, or to nothing, proves nothing about the test.")
        for start, end in hits:
            for first, last, by in spans:
                if first < end and start < last:
                    raise Refused(f"{where} edit {index}: {_excerpt(edit['old'])} in {edit['file']} overlaps "
                                  f"text edit {by} wrote. An edit to another edit's output is not an edit "
                                  f"to the code the test is about; name the final text in one edit.")
        # Every hit and every earlier span is a position in the text as it stands before this edit,
        # and a span moves by the change in length of the hits that end at or before it: no hit
        # overlaps a span (checked above), so each is wholly before it or wholly after it.
        delta = len(edit["new"]) - len(edit["old"])
        moved = []
        for first, last, by in spans:
            shift = delta * sum(1 for _, end in hits if end <= first)
            moved.append((first + shift, last + shift, by))
        pieces, cursor = [], 0
        for number, (start, end) in enumerate(hits):
            pieces += [text[cursor:start], edit["new"]]
            cursor = end
            where_it_lands = start + delta * number
            moved.append((where_it_lands, where_it_lands + len(edit["new"]), index))
        pieces.append(text[cursor:])
        texts[identity], written[identity] = "".join(pieces), moved

    # Encoded before anything is written, so text that cannot be (a lone surrogate in `new`) is a
    # refusal and not a file truncated half way through its write.
    planned = []
    for identity, mutated in texts.items():
        try:
            planned.append((paths[identity], originals[identity], mutated.encode("utf-8")))
        except ValueError as error:
            raise Refused(f"{where}: the edited text of {paths[identity][0].relative_to(ROOT)} cannot be "
                          f"written as UTF-8 ({error}); nothing was written")
    if all(mutated == original for _, original, mutated in planned):
        raise Refused(f"{where}: the edits cancel out; the test would run against the unmutated source, "
                      f"and a red result would be certified as an observed mutation of source that did "
                      f"not change")

    done = []       # (path, original bytes) for every name of every file written whole
    current = []    # the same for the file being written now
    culprit = None
    try:
        for names, original, mutated in planned:
            current = [(name, original) for name in names]
            culprit = names[0]
            culprit.write_bytes(mutated)    # one inode, however many names: the first writes them all
            done += current
            current = []
    except BaseException as error:
        # The file that failed is put back too if the failed write changed it (a write can truncate
        # and then fail), and left alone if it did not: it may be unwritable. Whatever interrupted
        # the writes, ^C included, the files already written go back before it is raised again.
        touched = done + (current if current and _bytes_of(current[0][0]) != current[0][1] else [])
        failed = restore(touched)
        reason = error if isinstance(error, OSError) else type(error).__name__
        writing = f"writing {culprit.relative_to(ROOT)}" if culprit else "writing"
        if failed:
            raise NotRestored(
                f"{where}: {writing} failed ({reason}), and these files were "
                f"mutated and could not be restored -- fix them before anything else:\n  "
                + "\n  ".join(str(p) for p in failed)) from error
        if isinstance(error, OSError):
            raise Refused(f"{where}: {writing} failed ({reason}); the files "
                          f"already written were put back and nothing is left mutated") from error
        raise
    return [(name, original) for names, original, _ in planned for name in names]


def restore(pairs):
    """Put every file back, byte for byte, and prove it went back. Returns the paths that did not.

    One file's failure does not stop the rest. An OSError marks that file failed. Anything else (a
    ^C, a SIGTERM that main() turned into KeyboardInterrupt) is not swallowed: the file it hit is
    tried once more, every remaining file is restored, and then the first such exception is raised.
    """
    failed, interrupt = [], None
    for path, original in pairs:
        try:
            if not _put_back(path, original):
                failed.append(path)
        except BaseException as error:
            interrupt = interrupt or error
            try:
                if not _put_back(path, original):
                    failed.append(path)
            except BaseException:
                failed.append(path)
    if interrupt is not None:
        raise interrupt
    return failed


def _put_back(path, original):
    """True when `path` holds `original` after writing it and reading it back."""
    try:
        path.write_bytes(original)
        return path.read_bytes() == original
    except OSError:
        return False


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


def _bytes_of(path):
    try:
        return path.read_bytes()
    except OSError:
        return None


def _within(path, root):
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _excerpt(text, width=70):
    one_line = " ".join(text.split())
    return repr(one_line if len(one_line) <= width else one_line[:width] + "...")


def _named_originals(spec):
    """[(path, bytes)] for every file the spec names, as it is on disk now, before anything is written."""
    pairs, seen = [], set()
    for edit in spec["edits"]:
        path = (ROOT / edit["file"]).resolve()
        if path in seen or not _within(path, ROOT):
            continue
        seen.add(path)
        original = _bytes_of(path)
        if original is not None:
            pairs.append((path, original))
    return pairs


def _terminated(signum, frame):
    """SIGTERM or SIGHUP while a file is mutated is an interrupt like ^C, so the `finally` clauses run."""
    raise KeyboardInterrupt(f"terminated by signal {signum}")


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

        # From just before the first write until the last file is back, SIGTERM and SIGHUP are an
        # interrupt: a terminated process runs no `finally`, and would leave the source mutated.
        # `apply` puts back what it wrote if it is interrupted, and `restore` finishes every file
        # before it raises.
        named = []
        previous = {}
        for signum in (signal.SIGTERM, getattr(signal, "SIGHUP", None)):
            if signum is not None:
                previous[signum] = signal.signal(signum, _terminated)
        try:
            try:
                named = _named_originals(spec)
                restore_pairs = apply(spec, f"spec {number}")
            except NotRestored as error:
                print(f"REFUSED: {error}", file=sys.stderr)
                return 1
            except Refused as error:
                print(f"[{number}/{len(specs)}] {label}\n    REFUSED: {error}", file=sys.stderr, flush=True)
                results.append((label, "REFUSED", str(error)))
                continue
            try:
                outcome, line = run_test(solution, test, args.configuration)
            finally:
                try:
                    failed = restore(restore_pairs)
                except BaseException:
                    failed = [path for path, original in restore_pairs if _bytes_of(path) != original]
                    if not failed:
                        raise
                if failed:
                    print("REFUSED: these files were mutated and could not be restored -- fix them "
                          "before anything else:\n  " + "\n  ".join(str(p) for p in failed), file=sys.stderr)
                    return 1
        except KeyboardInterrupt as error:
            # The claim is made only after looking: each named file against the bytes it had.
            failed = [path for path, original in named if _bytes_of(path) != original]
            if failed:
                print(f"INTERRUPTED: {error or 'interrupted'}\nREFUSED: these files were mutated and "
                      f"could not be restored -- fix them before anything else:\n  "
                      + "\n  ".join(str(p) for p in failed), file=sys.stderr)
                return 1
            print(f"INTERRUPTED: {error or 'interrupted'}; every file the mutation touched was put "
                  f"back.", file=sys.stderr)
            return 1
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
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
