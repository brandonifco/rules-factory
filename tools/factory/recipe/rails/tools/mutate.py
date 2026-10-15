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

**What the verdict is about.** Exactly the test the spec names, and nothing else the run printed.
The solution is built first, and a build that exits non-zero is the end of it. Then the tests run
with a TRX logger writing to a temporary directory that is removed afterwards, and the verdict is
read from the results of the named test in the TRX files of every test project: RED when one of
that test's own results is `Failed`, GREEN when it ran and every one of its results is `Passed`.
`test` is a fully qualified test name (`Ns.Class.Method`) or the name without its namespace
(`Class.Method`); a name that spells a namespace is that namespace's, and is not found in a longer
one. A closed generic class (`Probe<System.Int32>.One`) and a nested one (`Outer+Inner.One`) are
named whole. The result line names the test it resolved to and its assembly. Test results are
read as the xUnit the factory pins reports them, a theory under its method name; a framework that
names a row `Rows(1)` is not read, and finds nothing. Two projects are two assemblies even when
their files share a name; one project built for several target frameworks is one. The unmutated
run fixes which test is being watched, and a mutated run that finds a different one (or none) is
not judged: it is reported as a different test, or as no test, and is not red. The `--filter` only narrows
what runs, and its operators are escaped. Other tests the filter happens to select (`Probe.OneMore`
for `Probe.One`) run, and nothing they do decides anything. A test project the filter matches
nothing in is silent, not a verdict. A `test` that names more than one test (the same
`Class.Method` in two namespaces, or the same name in two assemblies) is reported as such and is
not red. The rows of one theory are
one test: any `Failed` row is red.

**A mutation that does not compile is not a red test.** It is reported as its own outcome and
counts as a failure of the run: the test was never asked the question. It is classified from the
build's exit status, and the diagnostic quoted is the build's own first `error XXX####` line,
whatever its class (`CS`, `MSB`, `NETSDK`, ...). Test output is never searched for one.

**Exit code.** 0 when every mutation turned its test red, and 1 otherwise -- green, did not
compile, no test matched, more than one did, or refused. One non-zero for "the evidence AGENTS.md asks for was not
produced", because that is the only distinction a caller acts on; which of them it was is in the
output, loudly. A temporary results directory the run could not remove is said when it happens and
at the end, and fails the run too: a run that leaves its own litter did not finish. Exit 2 stays
argparse's, for a command called wrongly.

**The temporary results directory** of a test run is made and removed with SIGTERM, SIGHUP and
SIGINT held (`signal.pthread_sigmask`), except while `dotnet test` itself runs: a signal that
falls in between waits, and fires once the directory is owned by the `try` that removes it, or once
it is gone. So the run never removes a directory it did not make, and never leaves its own. Where
the platform cannot hold signals (Windows) nothing is held, and a signal in those two short gaps
can still orphan the directory; one that is left is said, and fails the run.

Writes nothing into the checkout (`AGENTS.md` §4), and standard library only -- it does not import
the vendored factory, so it leaves no bytecode behind either.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVENANCE = "provenance.json"
POLICY = ".github/agent-policy.json"
DEFAULT_ESCAPE_HATCH = "RULES_ENGINE_ALLOW_PRIMARY_MUTATION"

# What the run can conclude about one mutation. Only RED is the evidence AGENTS.md asks for.
RED = "RED"
GREEN = "GREEN"
NO_BUILD = "DID NOT COMPILE"
NO_TEST = "NO TEST MATCHED"
MANY_TESTS = "MORE THAN ONE TEST MATCHED"
OTHER_TEST = "A DIFFERENT TEST MATCHED"

TRX_NS = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}

NOT_REMOVED = []    # results directories a run could not remove, said at the end and in the exit status


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


def run_test(solution, test, configuration, expected=None):
    """Build, run the filter, and judge the one test. Returns (outcome, the line that says so, the test).

    The third item is the one test (its name and its assembly) the results held, or None. `expected`
    is the one an earlier run found: a run that finds a different one is not judged, because an edit
    can remove the test that was watched and add another of the same name.
    """
    built = subprocess.run(["dotnet", "build", str(solution.name), "-c", configuration, "--nologo"],
                           cwd=ROOT, capture_output=True, text=True)
    if built.returncode != 0:
        return NO_BUILD, _diagnostic(f"{built.stdout}\n{built.stderr}", f"dotnet build exited {built.returncode}"), None

    # A signal is deferred (see `_defer`) from before the directory is made until it is removed,
    # except while `dotnet test` itself runs: one that falls anywhere else waits, and fires once
    # the directory is owned by this `try`, or once it is gone. The run therefore never removes a
    # directory it did not make (`mkdtemp` chooses the name and makes it), and never leaves its own.
    held = _defer()
    try:
        results = None
        try:
            results = tempfile.mkdtemp(prefix="mutate-")
            try:
                _undefer(held)
                ran = subprocess.run(
                    ["dotnet", "test", str(solution.name), "-c", configuration, "--nologo", "--no-build",
                     "--filter", f"FullyQualifiedName~{_escaped(test)}",
                     "--logger", "trx", "--results-directory", results],
                    cwd=ROOT, capture_output=True, text=True)
            finally:
                _defer()
            outcomes, problems = _results_of(test, results)
        finally:
            if results is not None:
                _remove(results)
    finally:
        _undefer(held)
    if problems:
        return NO_TEST, problems[0], None
    if len(outcomes) > 1:
        return MANY_TESTS, f"{_excerpt(test)} names {len(outcomes)} tests: {', '.join(sorted(_shown(label) for label in outcomes))}", None
    if not outcomes:
        lines = [line.strip() for line in f"{ran.stdout}\n{ran.stderr}".splitlines()
                 if line.strip() and not line.startswith("Results File:")]
        return NO_TEST, (f"no test named {_excerpt(test)} produced a result"
                         + (f"; dotnet test exited {ran.returncode}: {lines[-1]}" if ran.returncode and lines else "")), None
    (name, seen), = outcomes.items()
    if expected is not None and name != expected:
        return OTHER_TEST, f"the unmutated run found {_shown(expected)}, and this one found {_shown(name)}", name
    said = f"{_shown(name)}: " + ", ".join(f"{outcome} {count}" for outcome, count in sorted(seen.items()))
    if "Failed" in seen:
        return RED, said, name
    if set(seen) == {"Passed"}:
        return GREEN, said, name
    return NO_TEST, f"{said}; it did not run to a result of its own", name


def _escaped(test):
    """`test` as a VSTest filter value: its operators are text, so it cannot widen what is selected."""
    return re.sub(r"([\\()&|=!~])", r"\\\1", test)


def _diagnostic(output, fallback):
    """The build's first diagnostic of any class (`error CS1002`, `error NETSDK1045`), else its last line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    found = next((line for line in lines if re.search(r"\berror\s+[A-Za-z]+\d+\b", line)), None)
    return found or (lines[-1] if lines else fallback)


def _results_of(test, results):
    """({the test that matched: {outcome: results}}, problems), from the TRX files of this run.

    Only the files the logger wrote into `results` itself are read: VSTest copies a test's own
    attachments beneath it, and one of those may be any TRX at all. A result belongs to the test
    when `test` is the test's fully qualified name (the TRX's class and method), or `Class.Method`,
    the same without the namespace. A name that spells a namespace is therefore that namespace's:
    `Ns.Class.Method` is not `Other.Ns.Class.Method`. Both forms are cut from the one string
    `className.name`, because the logger may have moved part of the class name into `name` (see
    `_class_and_method`); `Probe<System.Int32>.One` and `Outer+Inner.One` are names.

    A test is told apart by its assembly as well, because the same name in two projects is two
    tests: the assembly is its output path, lower-cased, with `/` for `\\` and without the
    target-framework directory under `bin/<Configuration>/`, so two projects of one file name are
    two and one project built for several frameworks is one. The rows of one theory share both and
    are one test. A parameterised name (`Rows(1)`, which is how NUnit and MSTest name a row) is not
    the method's name and matches nothing: the xUnit the factory pins reports a theory under its
    method. So does a `DisplayName`: the TRX names the result by it, and keeps the declaring class
    and method in `TestMethod`, which is all a spec is read against.

    A project the filter matched nothing in writes a TRX with no results, which is no evidence either
    way; a TRX that cannot be read is reported, because it may have held the answer.
    """
    outcomes, problems = {}, []
    for path in sorted(found for found in pathlib.Path(results).glob("*.trx") if found.is_file()):
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as error:
            problems.append(f"{path.name} cannot be read ({error}), so it shows no test running")
            continue
        units = list(root.iterfind(".//t:UnitTest", TRX_NS))
        assemblies = {unit.get("id"): _assembly(unit.get("storage") or "") for unit in units}
        methods = {unit.get("id"): (method.get("className") or "", method.get("name") or "")
                   for unit in units for method in unit.iterfind("t:TestMethod", TRX_NS)}
        for result in root.iterfind(".//t:UnitTestResult", TRX_NS):
            if result.find("t:InnerResults", TRX_NS) is not None:
                continue    # a parent the writer made over the rows beneath it
            klass, method = methods.get(result.get("testId"), ("", ""))
            full = f"{klass}.{method}"
            if method and test in (full, _class_and_method(full)):
                assembly = assemblies.get(result.get("testId"))
                label = full + (f" ({assembly})" if assembly else "")
                seen = outcomes.setdefault(label, {})
                seen[result.get("outcome")] = seen.get(result.get("outcome"), 0) + 1
    return outcomes, problems


def _class_and_method(full):
    """The last two names of a fully qualified test name, `Class.Method`, split at dots outside brackets.

    The TrxLogger splits `className` and `name` at the display name when that is a dotted suffix of
    the full name, so `Other.Ns.RealTests.Declared` with `DisplayName = "RealTests.Declared"` is
    written as class `Other.Ns` and name `RealTests.Declared`. Only the whole string is the test's
    name; every form is derived from it, and a namespace is never read from `className` alone.
    A `+` is part of a name (`Outer+Inner`), and so are the dots inside `<>`, `[]` and `()`.
    """
    depth, names, start = 0, [], 0
    for index, character in enumerate(full):
        if character in "<[(":
            depth += 1
        elif character in ">])":
            depth -= 1
        elif depth == 0 and character == ".":
            names.append(full[start:index])
            start = index + 1
    names.append(full[start:])
    return ".".join(names[-2:])


def _defer():
    """Hold SIGTERM, SIGHUP and SIGINT until `_undefer`, and return the mask to give back (None if unavailable).

    A held signal is not lost: it is delivered when the mask is restored, so the interrupt it
    becomes (see `_terminated`) is raised where the caller can act on it. Where the platform cannot
    hold signals (`signal.pthread_sigmask` is missing, as on Windows) nothing is held, and a signal
    can fall in the narrow gaps this exists to close: between a directory being made and its
    removal being armed, and between the removal being entered and finishing.
    """
    block = getattr(signal, "pthread_sigmask", None)
    if block is None:
        return None
    held = {signal.SIGTERM, signal.SIGINT, getattr(signal, "SIGHUP", signal.SIGTERM)}
    return block(signal.SIG_BLOCK, held)


def _undefer(previous):
    """Give back the mask `_defer` returned, which delivers any signal held since."""
    block = getattr(signal, "pthread_sigmask", None)
    if block is not None and previous is not None:
        block(signal.SIG_SETMASK, previous)


def _remove(directory):
    """Remove `directory`, finishing the removal even if a signal turned into an interrupt inside it.

    The interrupt is raised again once the directory is gone: it is the caller's to act on, and
    leaving the directory behind is not. A directory that is still there afterwards (a file another
    process holds) is said now and again at the end, and the run exits non-zero for it.
    """
    interrupt = None
    while True:
        try:
            shutil.rmtree(directory, ignore_errors=True)
            break
        except BaseException as error:
            interrupt = interrupt or error
    if os.path.exists(directory):
        NOT_REMOVED.append(directory)
        print(f"NOT REMOVED: {directory} could not be removed; delete it by hand.", file=sys.stderr, flush=True)
    if interrupt is not None:
        raise interrupt


def _shown(label):
    """`label` with the assembly path shortened to the engine's root when it is under it, else whole."""
    name, separator, assembly = label.partition(" (")
    root = ROOT.as_posix().lower().rstrip("/") + "/"
    if separator and assembly.startswith(root):
        assembly = assembly[len(root):]
    return name + separator + assembly


def _assembly(storage):
    """The project an output path belongs to: its output path without the framework's directory.

    That is the one directly under `bin/<Configuration>/`, and no other: a directory above the
    project that looks like a framework (`tests/net8.0/`) is part of which project it is, and a
    runtime directory beneath the framework's (`linux-x64`) stays as it is. The path is absolute, so
    a project outside the engine is not the one inside it with the same tail; `_shown` shortens it
    for the eye and nothing else.
    """
    parts = [part for part in re.split(r"[\\/]", storage.lower()) if part]
    target = re.compile(r"net(coreapp|standard)?\d+(\.\d+)*(-[a-z0-9.]+)?")
    directories = parts[:-1]
    framework = next((index + 2 for index in reversed(range(len(directories)))
                      if directories[index] == "bin" and index + 2 < len(directories)
                      and target.fullmatch(directories[index + 2])), None)
    kept = [part for index, part in enumerate(directories) if index != framework] + parts[-1:]
    return ("/" if storage[:1] and storage[:1] in "/\\" else "") + "/".join(kept)


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
    baselines = {}      # test -> the outcome of its unmutated run
    resolved = {}       # test -> the one test (name and assembly) that run found
    for number, spec in enumerate(specs, start=1):
        label = spec.get("name") or spec["test"]
        test = spec["test"]

        # From before the first thing that makes a temporary directory until the last file is back,
        # SIGTERM and SIGHUP are an interrupt: a terminated process runs no `finally`, and would
        # leave the results directory of a run behind, or, after the first write, the source
        # mutated. `apply` puts back what it wrote if it is interrupted, and `restore` finishes
        # every file before it raises.
        named = []
        previous = {}
        for signum in (signal.SIGTERM, getattr(signal, "SIGHUP", None)):
            if signum is not None:
                previous[signum] = signal.signal(signum, _terminated)
        try:
            if not args.no_baseline and test not in baselines:
                outcome, line, found = run_test(solution, test, args.configuration)
                baselines[test], resolved[test] = outcome, found
                if outcome != GREEN:
                    print(f"[{number}/{len(specs)}] {label}\n"
                          f"    BASELINE {outcome}: {line}", flush=True)
            if baselines.get(test, GREEN) != GREEN:
                results.append((label, f"BASELINE {baselines[test]}", "the test was not green before the mutation"))
                continue
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
                # Judged against the test the unmutated run found, not against whatever the name
                # resolves to now: an edit can add a test of the same name and remove the first.
                outcome, line, _ = run_test(solution, test, args.configuration, expected=resolved.get(test))
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
            print(f"INTERRUPTED: {error or 'interrupted'}; "
                  + ("every file the mutation touched was put back." if named else "nothing had been mutated."),
                  file=sys.stderr)
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
    if NOT_REMOVED:
        print("\nNOT REMOVED, and the run fails for it:\n  " + "\n  ".join(NOT_REMOVED))
    return 0 if red == len(results) and not NOT_REMOVED else 1


if __name__ == "__main__":
    sys.exit(main())
