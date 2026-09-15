"""`factory verify` (#70): the end of the factory's contract. An engine is acceptable when this passes.

Until this existed, `produce` printed that it had produced an engine without compiling it or
running a single one of the tests it generated, so "produced" said nothing about whether the
product worked. `verify` is what "produced" now means: `produce` runs it on the staging copy
(transaction.py, #67) after provenance is written and before anything is committed, unless told
explicitly (`--no-verify`) not to. So a failed verify discards the staging copy, `--out` is
byte-identical to how it started, and only a verified engine is ever committed. What verify
writes in the staging copy is committed with the engine only where it belongs to the engine: the
packages.lock.json files a first restore writes are added files, while bin/ and obj/ are not:
`verify_staged` deletes them from the staging copy once verify has passed. transaction.py already
leaves them out of an existing engine's mutation set, but a fresh `--out` is committed by renaming
the whole staging copy, which would carry them along -- and obj/ holds absolute paths into a
staging directory that no longer exists.

Stages, in order, each named in the output; the first that fails stops the run:

  1. provenance -- `recompute` (provenance.py) re-produces the engine in a scratch copy and
     every field of provenance.json matches. This comes first because everything after it runs
     code the factory generated, the engine's gate above all: once provenance matches, that code
     is the factory's, byte for byte, and not a hand-edited copy that passes by being weakened.
  2. restore -- only for an engine with no packages.lock.json yet (every freshly produced one:
     `produce` itself runs no dotnet): `dotnet restore` with RestoreLockedMode forced off, so
     that CI=true in the environment cannot make a first restore impossible, which writes the
     lock files (the scaffold's Directory.Build.props turns them on). An engine that already has
     lock files skips this stage; the gate's locked restore holds it to them -- except in a
     `produce` whose generated pins changed (below), where this stage re-locks them.
  3. gate -- the engine's own `scripts/validate.sh full` (gate.py): SDK pin, locked restore, the
     randomness the corpus declares (0019), the 0015 merge and the packaged consumer checker, corpus posture, every `*.g.cs`
     equal to a fresh regeneration, format, and a -warnaserror build and tests in Debug and
     Release, reading the TRX files to show tests ran (zero tests fails) and that every test an
     implemented entry names exists and ran.

There is no build or test stage of verify's own. The gate builds and tests, and is the engine's
single definition of acceptable; a build and test here as well would build the solution three
times (Release here, then the gate's Debug and Release) to learn nothing the gate does not. The
only thing the gate cannot do is start from an engine without lock files, since its restore is
locked -- which is exactly what stage 2 provides, so the gate runs on every engine, fresh or not.

Lock files and provenance (#69). `buildInputs` makes no claim about lock files while the record
lists none, and holds the engine to all of them once it lists any. The restore in stage 2 writes
lock files the record written before it could not have seen. Committing them unrecorded would
pass `factory provenance` (no claim) but leave the lock files unproven until someone re-ran
produce. So `produce` passes `after_restore`, which rewrites provenance.json in the staging copy
once restore has written them and before the gate: every build the gate makes embeds the record
that lists them, the generated provenance test compares that embedded copy with the file, and
the committed engine -- exactly what the gate tested -- is held to its lock files from the start.
Standalone `verify` writes nothing but what restore writes, and so leaves an unrecorded engine's
lock files unclaimed.

Changed pins re-lock (#94). `produce` rewrites RulesFactory.Packages.g.props every run, and a map
version bump (or a new kernel pin) changes the versions it pins. Lock files resolved against the
old pins then fail the gate's locked restore, so a verified bump could never be committed. So
`produce` compares the resolved pin set of the staged props -- every `PackageVersion` Include and
Version, `pins` below -- with the one the engine had before the run (`pins_changed`), and passes
`relock=True` when they differ. If lock files exist, stage 2 then runs `dotnet restore
--force-evaluate` with locked mode off, `after_restore` records the rewritten lock files in
provenance.json, and the gate's locked restore proves them. The pin set, not the file's bytes, is
the signal: a change to the props' comments or layout moves no package, and must not turn the
gate's proof of the committed lock files into a rewrite of them. An existing engine without a
readable props counts as changed, since nothing shows its lock files were resolved against these
pins. With the pins unchanged nothing differs from before: no relock, and the gate's locked
restore holds the engine to its committed lock files.

This is the one case where `produce` rewrites files the ownership table (ownership.py, decision
0018) calls engine-owned: it is the factory's input that moved, the rewrite happens in the staging
copy and is committed only when the gate passes, and the commit lists the lock files as changed,
for the engine to review.

Standalone `verify` never re-locks. It has no earlier pin set to compare with, and it runs on the
engine in place, outside any transaction, so a relock there would silently rewrite engine-owned
files and leave them unrecorded. An engine whose pins moved outside `produce` fails the gate's
locked restore; it re-locks itself with `scripts/validate.sh lock`, reviews and commits the result,
or runs `produce` again.

`dotnet` is `$FACTORY_DOTNET` when set, else `dotnet` on PATH; a test substitutes a fake the way
`$FACTORY_GH` substitutes `gh` for `backlog --create`. The gate is a shell script that runs
`dotnet` from PATH, so when `$FACTORY_DOTNET` names a path its directory is put first on the
gate's PATH. Every child process has a timeout, and one that overruns fails its stage.

Exit codes, as for every factory command: 0 when every stage passed, 1 when a stage failed, 2 on
a usage error (the engine directory does not exist).

Standard library only.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import threading

import intake as intake_step

STAGES = ("provenance", "restore", "gate")
GATE = "scripts/validate.sh"
IGNORED = {"bin", "obj", ".git", "artifacts", "TestResults"}
BUILD_OUTPUT = frozenset({"bin", "obj"})

# Seconds. Generous: a cold restore from nuget.org and two configurations of build and test are
# slow, and a timeout is only there so a hung child fails its stage instead of hanging produce.
TIMEOUTS = {"restore": 900, "gate": 3600}


class Failed(Exception):
    """A stage failed. `stage` names it; the message says why."""

    def __init__(self, stage, message):
        super().__init__(f"{stage}: {message}")
        self.stage = stage
        self.message = message


PACKAGES_PROPS = "RulesFactory.Packages.g.props"
PACKAGE_VERSION = re.compile(r'<PackageVersion\b(?=[^>]*\bInclude="([^"]*)")(?=[^>]*\bVersion="([^"]*)")[^>]*>')


def pins(text):
    """The resolved pin set of a RulesFactory.Packages.g.props text: {package id, lower case: version}.

    Comments are dropped first, so a commented-out pin pins nothing.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return {package.lower(): version.strip() for package, version in PACKAGE_VERSION.findall(text)}


def read_pins(engine_dir):
    """`pins` of the engine's RulesFactory.Packages.g.props; None when it is absent or unreadable."""
    try:
        with open(os.path.join(engine_dir, PACKAGES_PROPS), encoding="utf-8") as handle:
            return pins(handle.read())
    except (OSError, UnicodeDecodeError):
        return None


def pins_changed(before, after):
    """Whether a produce moved the generated pins; `before` and `after` are `read_pins` results.

    No readable props before the run counts as changed (module docstring).
    """
    return before is None or before != after


def dotnet_command():
    return os.environ.get("FACTORY_DOTNET") or "dotnet"


def lock_files(engine_dir):
    found = []
    for directory, dirs, names in os.walk(engine_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED]
        if "packages.lock.json" in names:
            found.append(os.path.join(directory, "packages.lock.json"))
    return sorted(found)


def _run(stage, argv, cwd, log, env=None):
    """Run `argv`, echoing its output to `log` as it arrives; return its exit code.

    Output is streamed, not collected, so a ten-minute build is not silent for ten minutes; the
    timeout is a timer that kills the child, since reading a pipe to its end cannot also time out.
    """
    try:
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, errors="replace")
    except OSError as error:
        raise Failed(stage, f"cannot run {argv[0]}: {error}")
    expired = []

    def kill():
        expired.append(True)
        child.kill()

    timer = threading.Timer(TIMEOUTS[stage], kill)
    timer.start()
    try:
        for line in child.stdout:
            log.write(line)
        code = child.wait()
    finally:
        timer.cancel()
    if expired:
        raise Failed(stage, f"`{' '.join(argv[:2])}` did not finish in {TIMEOUTS[stage]} seconds")
    return code


def solution(engine_dir):
    found = sorted(glob.glob(os.path.join(engine_dir, "*.slnx")))
    if len(found) != 1:
        raise Failed("restore", f"expected exactly one .slnx in {engine_dir}, found {len(found)}")
    return os.path.basename(found[0])


def verify_staged(root, recompute, package=None, log=None, after_restore=None, relock=False):
    """`verify` on produce's staging copy, then delete the build output it left there.

    The staging copy never holds bin/ or obj/ before this (transaction.py does not copy them), so
    every one found afterwards is verify's own and nothing of the engine's is deleted.
    """
    verify(root, recompute, package, log, after_restore, relock)
    for directory, dirs, _ in os.walk(root):
        for name in [d for d in dirs if d in BUILD_OUTPUT]:
            shutil.rmtree(os.path.join(directory, name))
        dirs[:] = [d for d in dirs if d not in BUILD_OUTPUT]


def verify(engine_dir, recompute, package=None, log=None, after_restore=None, relock=False):
    """Run every stage on `engine_dir`, raising Failed at the first that fails.

    `recompute(engine_dir, package)` returns provenance mismatches (__main__.recompute_provenance);
    it is passed in because it re-runs produce, which lives in __main__ and calls this module.
    `after_restore()`, when given, runs after a restore that wrote the lock files and before the
    gate (produce uses it to record them in provenance.json, above). `relock` is produce's alone,
    passed when the generated pins changed: existing lock files are then re-locked, not skipped.
    """
    log = log or sys.stdout
    if not os.path.isdir(engine_dir):
        raise intake_step.Usage(f"--engine {engine_dir!r} is not a directory")
    engine_dir = os.path.abspath(engine_dir)

    def stage(name, detail=""):
        print(f"--- verify [{STAGES.index(name) + 1}/{len(STAGES)}] {name}{detail}", file=log)

    def ok(name, detail):
        print(f"ok   {name}: {detail}", file=log)

    stage("provenance")
    mismatches = recompute(engine_dir, package)
    for line in mismatches:
        print(f"MISMATCH {line}", file=log)
    if mismatches:
        raise Failed("provenance", f"{len(mismatches)} provenance field(s) do not match what re-producing gives")
    ok("provenance", "every field matches")

    dotnet = dotnet_command()
    locks = lock_files(engine_dir)
    if locks and not relock:
        stage("restore", f" -- skipped: {len(locks)} lock file(s) present; the gate's locked restore holds the "
                         f"engine to them")
    else:
        sln = solution(engine_dir)
        argv = [dotnet, "restore", sln, "-p:RestoreLockedMode=false"]
        if locks:
            stage("restore", f" -- the generated pins changed, so this restore re-locks the {len(locks)} lock "
                             f"file(s)")
            argv.append("--force-evaluate")
        else:
            stage("restore", " -- no packages.lock.json yet, so this restore writes them")
        if _run("restore", argv, engine_dir, log) != 0:
            raise Failed("restore", "dotnet restore failed")
        written = lock_files(engine_dir)
        if not written:
            raise Failed("restore", "dotnet restore wrote no packages.lock.json, so the gate's locked restore "
                                    "cannot run")
        ok("restore", f"{len(written)} lock file(s) {'re-locked' if locks else 'written'}")
        if after_restore is not None:
            after_restore()

    stage("gate", f" -- {GATE} full (locked restore, build -warnaserror and tests in Debug and Release, "
                  f"and the engine's other checks)")
    gate = os.path.join(engine_dir, *GATE.split("/"))
    if not os.path.isfile(gate):
        raise Failed("gate", f"the engine has no {GATE}")
    # The gate's Python imports scripts/factory/*.py; left to itself it writes __pycache__ into the
    # engine, which a staged verify would then commit as if it were the engine's.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if os.sep in dotnet:
        env["PATH"] = os.path.dirname(os.path.abspath(dotnet)) + os.pathsep + env.get("PATH", "")
    if _run("gate", ["bash", gate, "full"], engine_dir, log, env) != 0:
        raise Failed("gate", f"{GATE} full failed; its output above names the step")
    ok("gate", f"{GATE} full passed")
