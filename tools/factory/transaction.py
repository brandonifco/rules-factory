"""`produce` is transactional (#67): a refusal leaves `--out` as it was.

The transaction is over files in `--out`, never over git. `produce` writes an engine's files and
makes no git commit: what it wrote is left in the engine's working tree for whoever ran it to
review and commit (`git_note()` says so, on every run whose `--out` is a git checkout).

Every step of `produce` -- generation, the gate recipe, backlog, provenance -- writes into a
staging copy of the engine, never into `--out`. Only when every step has passed is the result
put in place. A refusal before that point removes the staging copy, so `--out` is byte-identical to
how it started and "Nothing was produced." is true; a fresh `--out` is not created.

Staging. A working directory is made beside `--out` (in its parent, or the nearest ancestor that
exists when the parent does not), so it is on the same filesystem and `os.replace` into `--out`
is atomic. It holds `engine/`, the staging copy, and `backup/`. The copy is of `--out` minus
`bin`, `obj`, `.git` and `.vs` at any depth (provenance.COPY_IGNORE, what `recompute` skips):
no step reads or writes those, and they are the large ones. They are skipped when computing the
mutation set too, so they are never touched. Symlinks are followed when copying (a dangling one
is not copied, and not counted as removed), so no step can write through a link to outside the
staging copy.

Symlinks in `--out` itself (#184). Git stores symlinks, so a pull request to an engine can turn a
directory the factory writes into a link to anywhere. `os.replace` and `os.remove` on
`--out/backlog/x.md` resolve a symlinked `backlog`, so committing through it would write and
delete outside `--out`. Before anything is written, every path in the mutation set is checked:
if the file itself, or any directory between it and `--out`, is a symlink, the run is refused,
naming the link, and nothing is written. A symlink on a path the commit does not touch is left
alone. A link swapped in between that check and the write is not caught; that would take
descriptor-relative I/O the standard library does not offer portably.

The mutation set. Right after the copy, each staged file's size, executable bit and SHA-256 is
noted. After the steps, a file is added when it is new, changed when its bytes or executable bit
differ from what was copied, and removed when it was copied and is gone. The executable bit is the
only part of a mode git tracks, and the only part compared: the gate recipe writes 0644 and 0755,
and a clone made under umask 002 has 0664 and 0775, so comparing whole modes counted files git
sees as unchanged as changed. A file whose other mode bits alone differ is left as it is in
`--out`. Removal has one producer: a pattern the factory has retired (ownership.RETIRED --
`backlog/*.md`, since #243) is deleted from the staging copy by every `produce`, which is how an
engine produced before the retirement is migrated, transactionally. Nothing else deletes anything.
Comparing against the snapshot rather than against `--out` at commit time means a
file someone edits in `--out` while `produce` runs is not reverted; and before committing, every
path in the set is checked against `--out` again (a changed or removed file still as it was
copied, an added one still absent), and the run is refused, with nothing written, if not.

What a verified commit is held to (#335). The mutation set is what the run writes, and for a
`--no-verify` run it is the whole of what the commit claims: nothing was built, so nothing else
is asserted, and a file someone edits in `--out` meanwhile is kept and the run goes on. A
verified run claims more. `verify` (verify.py) builds and tests the staging copy *as a whole*,
so the proof is over every input of it -- the `.cs` files the gate compiled, the projects and
props it read, the overlay, the lock files, the scripts it ran -- and every one of those the run
did not itself write is still the snapshot's bytes. Checking only the mutation set let an engine
whose source moved in `--out` after the copy be committed over and reported as verified, though
what was then on disk had never been built anywhere: the generated files from the staged tree,
beside a source file the gate never saw. So `commit(verified=True)` compares `--out` against the
snapshot for every input before anything is written (`drift`), and refuses, naming each path and
whether it was changed, added or removed. Preserving the edit is right and the refusal preserves
it -- nothing is written, so the engine keeps it -- but the answer is to run `produce` again and
verify the engine with it, not to call a tree verified that no build ever saw. What is compared
is every file under `--out` except the directories a build and the gate write rather than read
(`OUTPUT` -- `artifacts` and `TestResults` -- and `SKIP`, which is not copied at all), so a TRX
file or an assembly landing in `--out` while the gate runs refuses nothing.

The commit, for a fresh `--out`: its missing parents are created and the staging copy is renamed
into place, one atomic rename. For an existing `--out`:

  1. every file to change or remove is copied to `backup/`;
  2. the journal, `--out/.factory-produce-journal.json`, is written atomically and fsynced. It
     names `--out`, the working directory, and the added, changed and removed paths and the
     directories to create. Its existence means the backups are complete;
  3. directories are created, each added or changed file is `os.replace`d into place, each
     removed file is deleted;
  4. the journal is deleted, then any directory the removals emptied (`_prune_emptied`: after the
     journal, because an empty directory can lose nothing and a rollback has nothing to restore
     into it), then the working directory.

A failure in step 3 (an exception, KeyboardInterrupt included) is rolled back at once: added
files and created directories are removed, changed and removed files are restored from
`backup/`. Rollback is idempotent, so it is safe to repeat. If the process dies instead, the
journal stays, and the next `produce` into that `--out` rolls it back before anything else,
says so, and then runs as usual. Rolling back rather than refusing: the backups make it exact,
and a refusal would leave the engine half-committed until someone repaired it by hand. A journal
that cannot be read, names a different directory (a copy of an engine taken mid-commit, as
`recompute` makes), or whose rollback fails, is refused, naming the journal and the backups.

A journal is also a file in the engine's checkout, so it can arrive in a commit rather than from a
dead run (#183). Rollback deletes and overwrites the paths it names, so nothing in it is taken on
trust: before any rollback, every path must be relative and normalised (no absolute prefix, no
empty, `.` or `..` component) and must not pass through a symlink under `--out`; the working
directory must exist as a real directory; and every changed or removed path must have a regular
file in its `backup/`, which is itself a real directory; and the `restoring` file the rollback
copies through must not be a symlink or anything but a regular file (#228). A journal failing any of
these is refused, and nothing is deleted or restored. The copy into `restoring` is also made
without following a link at either end, so one planted after the check fails the copy instead of
being written through.

Not handled: a working directory left behind by a process killed before step 2 is not removed
by a later run (it cannot tell a dead run from a concurrent one); it is a hidden
`.<name>.factory-produce-*` beside `--out`, holds nothing `--out` needs, and can be deleted.
Writes are not fsynced beyond the journal, as before.

Standard library only.
"""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile

import intake as intake_step

JOURNAL = ".factory-produce-journal.json"
JOURNAL_FORMAT = 1
SKIP = frozenset({"bin", "obj", ".git", ".vs"})
#: Directories a verified commit does not hold `--out` to (#335), on top of SKIP, which is not
#: copied at all. The build and the gate write these and no build reads one, so their bytes are
#: not an input to what verify proved: `artifacts` is the SDK's output path and `TestResults` the
#: TRX files `dotnet test` writes -- the same two names verify.py already prunes as not-inputs.
#: Everything else under `--out` is an input: a `.cs` the gate compiles, a project or props it
#: reads, the overlay, a lock file, a script the gate runs. Named by what they are rather than
#: listed by what a build reads, so a file an engine adds is covered without anyone remembering it.
OUTPUT = frozenset({"artifacts", "TestResults"})


class CommitError(Exception):
    """Committing to `--out` failed after it began. `rolled_back` says whether `--out` is as it was."""

    def __init__(self, message, rolled_back):
        super().__init__(message)
        self.rolled_back = rolled_back


def _files(root):
    """Relative POSIX path -> absolute path of every regular file under `root`, SKIP pruned."""
    found = {}
    for directory, dirs, names in os.walk(root, followlinks=True):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in names:
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                found[os.path.relpath(path, root).replace(os.sep, "/")] = path
    return found


def _signature(path):
    info = os.stat(path)
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return info.st_size, bool(info.st_mode & stat.S_IXUSR), digest.hexdigest()


def _is_input(relative):
    """Whether `relative` is a source or build input of what verify proved, rather than output (#335)."""
    return not any(part in OUTPUT for part in relative.split("/")[:-1])


def _native(root, relative):
    return os.path.join(root, *relative.split("/"))


def _safe_relative(relative):
    """Whether `relative` is a normalised relative POSIX path that cannot leave the root it is joined to."""
    return (isinstance(relative, str) and relative and "\0" not in relative and not relative.startswith("/")
            and all(part not in ("", ".", "..") for part in relative.split("/")))


def _symlink_on(root, relative):
    """The first of `relative`'s own path or its parent directories, under `root`, that is a symlink; else None."""
    parts = relative.split("/")
    for depth in range(1, len(parts) + 1):
        prefix = "/".join(parts[:depth])
        if os.path.islink(_native(root, prefix)):
            return prefix
    return None


def _existing_ancestor(path):
    while not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return path


# --- rollback --------------------------------------------------------------------------------


def _copy_without_following(source, destination):
    """`shutil.copy2(source, destination)`, except that neither end is followed through a symlink (#228).

    `copy2` opens its destination by name, so a link planted there is written through to wherever it
    points. A regular file left there by a run that died mid-restore is removed without following
    anything; then the destination is created exclusively and without following, so a link that
    appears after the removal makes the copy fail rather than land outside `--out`.
    """
    if os.path.islink(destination):
        raise OSError(f"{destination} is a symlink, and a restore is never written through one")
    if os.path.lexists(destination):
        os.unlink(destination)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    with open(source, "rb", opener=lambda path, flags: os.open(path, flags | nofollow)) as reader:
        mode = stat.S_IMODE(os.fstat(reader.fileno()).st_mode)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o600)
        with open(fd, "wb") as writer:
            shutil.copyfileobj(reader, writer)
    shutil.copystat(source, destination, follow_symlinks=False)
    os.chmod(destination, mode)


def _rollback(journal):
    out, work = journal["out"], journal["work"]
    backup = os.path.join(work, "backup")
    for relative in journal["added"]:
        target = _native(out, relative)
        if os.path.lexists(target):
            os.remove(target)
    restoring = os.path.join(work, "restoring")
    for relative in journal["changed"] + journal["removed"]:
        _copy_without_following(_native(backup, relative), restoring)
        os.replace(restoring, _native(out, relative))
    for relative in reversed(journal["directories"]):
        try:
            os.rmdir(_native(out, relative))
        except FileNotFoundError:
            pass
        except OSError:
            if os.listdir(_native(out, relative)):
                continue  # something not this commit's is in it; it was not ours to remove
            raise


def _journal_problem(journal, out):
    """Why the journal's paths cannot be rolled back safely (#183), or None. Checked before anything is touched."""
    root = journal["out"]
    work = journal["work"]
    if os.path.islink(work) or not os.path.isdir(work):
        return f"its working directory {work} does not exist"
    backup = os.path.join(work, "backup")
    # Rollback copies out of `backup/` into `restoring` and moves that into --out, so neither may be a
    # link: a planted `restoring` pointing outside --out is written through, and a linked `backup/`
    # makes every "backed-up file" whatever it points at (#228).
    if os.path.islink(backup) or (os.path.lexists(backup) and not os.path.isdir(backup)):
        return f"its backup directory {backup} is not a real directory"
    restoring = os.path.join(work, "restoring")
    if os.path.islink(restoring) or (os.path.lexists(restoring) and not os.path.isfile(restoring)):
        return f"{restoring} is not a regular file, and a restore is never written through one"
    for key in ("added", "changed", "removed", "directories"):
        for relative in journal[key]:
            if not _safe_relative(relative):
                return f"its {key!r} list names {relative!r}, which is not a relative path inside the engine"
            link = _symlink_on(root, relative)
            if link is not None:
                return f"its {key!r} path {relative!r} passes through the symlink {link}"
    for relative in journal["changed"] + journal["removed"]:
        saved = _native(backup, relative)
        if _symlink_on(backup, relative) is not None or not os.path.isfile(saved):
            return f"{relative!r} has no backed-up file under {backup}"
    return None


def recover(out, log=None):
    """Roll back a commit to `out` that a dead run left journaled; refuse when that cannot be done."""
    path = os.path.join(out, JOURNAL)
    if not os.path.lexists(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            journal = json.load(handle)
        if journal.get("format") != JOURNAL_FORMAT:
            raise ValueError(f"format {journal.get('format')!r}, not {JOURNAL_FORMAT}")
        for key in ("added", "changed", "removed", "directories"):
            if not isinstance(journal.get(key), list):
                raise ValueError(f"no list {key!r}")
    except (OSError, ValueError) as error:
        raise intake_step.Refused(f"{path} records an interrupted commit to this engine, and cannot be read "
                                  f"({error}); restore the engine from version control and delete the journal")
    if journal.get("out") != os.path.realpath(out):
        raise intake_step.Refused(f"{path} records an interrupted commit to {journal.get('out')}, not to this "
                                  f"directory (a copy taken mid-commit?); roll the original back by running "
                                  f"produce there, or restore this copy and delete the journal")
    # Rollback deletes the working directory, so it must be one a run made beside this --out.
    work = journal.get("work")
    if not isinstance(work, str) or os.path.dirname(work) != _existing_ancestor(os.path.dirname(journal["out"])) \
            or not os.path.basename(work).startswith(f".{os.path.basename(journal['out'])}.factory-produce-"):
        raise intake_step.Refused(f"{path} records an interrupted commit to this engine, but names {work!r} as "
                                  f"its working directory, which is not one produce makes; restore the engine "
                                  f"from version control and delete the journal")
    unsafe = _journal_problem(journal, out)
    if unsafe:
        raise intake_step.Refused(f"{path} records an interrupted commit to this engine, but {unsafe}, so it is not "
                                  f"one produce wrote and nothing in it was rolled back; restore the engine from "
                                  f"version control and delete the journal")
    try:
        _rollback(journal)
    except OSError as error:
        raise intake_step.Refused(f"{path} records an interrupted commit to this engine, and rolling it back "
                                  f"failed ({error}); the files it changed or removed are backed up under "
                                  f"{os.path.join(journal['work'], 'backup')}: restore them by hand, remove the "
                                  f"files it added, then delete the journal")
    os.remove(path)
    shutil.rmtree(journal["work"], ignore_errors=True)
    if log is not None:
        print(f"rolled back an interrupted commit recorded in {path}: {len(journal['added'])} added file(s) "
              f"removed, {len(journal['changed']) + len(journal['removed'])} restored", file=log)


# --- the stage -------------------------------------------------------------------------------


class Stage:
    """A staging copy of `out` that every step writes into, put in place in `out` by `commit()`.

    Leaving the `with` block without a successful commit discards the copy and leaves `out` alone.
    """

    def __init__(self, out, log=None):
        self.out = os.path.realpath(os.path.abspath(out))
        self.log = log
        self.work = None
        self.committed = False

    def __enter__(self):
        if os.path.lexists(self.out) and not os.path.isdir(self.out):
            raise intake_step.Refused(f"--out {self.out} exists and is not a directory")
        self.fresh = not os.path.isdir(self.out)
        if not self.fresh:
            recover(self.out, self.log)
        parent = _existing_ancestor(os.path.dirname(self.out))
        try:
            self.work = tempfile.mkdtemp(prefix=f".{os.path.basename(self.out)}.factory-produce-", dir=parent)
        except OSError as error:
            raise intake_step.Refused(f"cannot make a staging directory in {parent} beside --out: {error}")
        self.root = os.path.join(self.work, "engine")
        try:
            if self.fresh:
                os.mkdir(self.root)
            else:
                shutil.copytree(self.out, self.root, ignore=lambda _, names: [n for n in names if n in SKIP],
                                ignore_dangling_symlinks=True)
            self.snapshot = {relative: _signature(path) for relative, path in _files(self.root).items()}
        except BaseException:
            self._discard()
            raise
        return self

    def __exit__(self, *exc):
        self._discard()
        return False

    def _discard(self):
        if self.work is not None and not os.path.lexists(os.path.join(self.out, JOURNAL)):
            shutil.rmtree(self.work, ignore_errors=True)
            self.work = None

    def testing(self):
        """Note the staging copy's inputs as the proof is about to be made over them (#370)."""
        self.tested = {relative: _signature(path) for relative, path in _files(self.root).items()
                       if _is_input(relative)}

    def plan(self):
        """(added, changed, removed): relative paths, each sorted."""
        after = _files(self.root)
        added = sorted(p for p in after if p not in self.snapshot)
        changed = sorted(p for p in after if p in self.snapshot and _signature(after[p]) != self.snapshot[p])
        removed = sorted(p for p in self.snapshot if p not in after)
        return added, changed, removed

    def drift(self):
        """Every source or build input where `out` no longer holds the bytes the staging copy was made from.

        `(path, reason)` pairs, sorted by path: what the engine was verified from is the staging
        copy, and every input of it that this run did not write is the snapshot's bytes -- so
        `out` still holding the snapshot, input for input, is what makes the committed tree the
        verified one (#335). Build output is not compared (`OUTPUT`), and neither is anything
        under SKIP, which was never copied.
        """
        expected = {p: signature for p, signature in self.snapshot.items() if _is_input(p)}
        present = {p: path for p, path in _files(self.out).items() if _is_input(p)}
        moved = []
        for relative in sorted(set(expected) | set(present)):
            if relative not in present:
                moved.append((relative, "removed"))
            elif relative not in expected:
                moved.append((relative, "added"))
            elif _signature(present[relative]) != expected[relative]:
                moved.append((relative, "changed"))
        return moved

    def commit(self, verified=False):
        """Put the staged engine in place of `out`; returns (added, changed, removed).

        `verified` says this run proved the staged engine by building and testing it (verify.py).
        A verified commit is held to every input of that proof, not only to the paths it writes:
        see `drift` and `_commit_existing` (#335).
        """
        added, changed, removed = self.plan()
        if self.fresh:
            self._commit_fresh()
        else:
            self._commit_existing(added, changed, removed, verified)
        self.committed = True
        if self.log is not None:
            # "wrote", not "committed": this puts files in place in --out and makes no git commit
            # (git_note() below says so where --out is a git checkout).
            print(f"wrote to {self.out}: {len(added)} added, {len(changed)} changed, {len(removed)} removed",
                  file=self.log)
        return added, changed, removed

    def _commit_fresh(self):
        if os.path.lexists(self.out):
            raise intake_step.Refused(f"--out {self.out} was created by something else while produce ran")
        created = []
        try:
            missing = os.path.dirname(self.out)
            while not os.path.isdir(missing):
                created.append(missing)
                missing = os.path.dirname(missing)
            for directory in reversed(created):
                os.mkdir(directory)
            os.rename(self.root, self.out)
        except BaseException as error:
            try:
                for directory in created:
                    if os.path.isdir(directory):
                        os.rmdir(directory)
            except OSError as second:
                raise CommitError(f"moving the staged engine to {self.out} failed ({error}), and removing the "
                                  f"directories made for it failed too ({second})", rolled_back=False)
            raise CommitError(f"moving the staged engine to {self.out} failed ({error})", rolled_back=True)

    def _commit_existing(self, added, changed, removed, verified=False):
        linked = sorted({f"{p} (through {link})" for p in added + changed + removed
                         for link in [_symlink_on(self.out, p)] if link is not None})
        if linked:
            raise intake_step.Refused(f"--out has a symlink where produce would write or remove ({', '.join(linked)}); "
                                      f"writing through it would change files outside --out, so nothing was "
                                      f"written. Replace the link with a real file or directory and run produce "
                                      f"again")
        if verified:
            # #335. The staged engine was built and tested as a whole, so the proof is over every
            # input of it, not over the paths this run happens to write. Committing the writes over
            # an --out whose other inputs have moved would leave a tree nothing ever built, reported
            # as verified. Refused before a byte is written, so the concurrent edit stands: it is
            # the engine's, and the answer is to build and test the engine with it, not to lose it.
            drifted = self.drift()
            if drifted:
                raise intake_step.Refused(
                    f"--out changed after the engine was verified "
                    f"({', '.join(f'{path} ({reason})' for path, reason in drifted)}); the engine that was "
                    f"built and tested was made from --out as it stood when produce started, so committing "
                    f"over it would report an engine as verified that was never built. Nothing was written "
                    f"and the change in --out is untouched; run produce again to verify the engine with it")
        moved = [p for p in added if os.path.lexists(_native(self.out, p))]
        moved += [p for p in changed + removed
                  if not os.path.isfile(_native(self.out, p)) or _signature(_native(self.out, p)) != self.snapshot[p]]
        if moved:
            raise intake_step.Refused(f"--out changed while produce ran ({', '.join(sorted(moved))}), so the staged "
                                      f"result is not committed over it; run produce again")
        if not (added or changed or removed):
            return
        backup = os.path.join(self.work, "backup")
        for relative in changed + removed:
            target = _native(backup, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(_native(self.out, relative), target)
        directories = []
        for relative in added:
            parts = relative.split("/")[:-1]
            for depth in range(1, len(parts) + 1):
                directory = "/".join(parts[:depth])
                if directory not in directories and not os.path.isdir(_native(self.out, directory)):
                    directories.append(directory)
        journal = {"format": JOURNAL_FORMAT, "out": self.out, "work": self.work,
                   "added": added, "changed": changed, "removed": removed, "directories": directories}
        journal_path = os.path.join(self.out, JOURNAL)
        pending = os.path.join(self.work, "journal")
        with open(pending, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(journal, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, journal_path)
        try:
            for directory in directories:
                os.mkdir(_native(self.out, directory))
            for relative in added + changed:
                os.replace(_native(self.root, relative), _native(self.out, relative))
            for relative in removed:
                os.remove(_native(self.out, relative))
        except BaseException as error:
            try:
                _rollback(journal)
                os.remove(journal_path)
            except BaseException as second:
                raise CommitError(f"writing to {self.out} failed ({error!r}), and rolling back failed too "
                                  f"({second!r}); the journal {journal_path} names every path, and the files "
                                  f"it changed or removed are backed up under {backup}. The next produce into "
                                  f"{self.out} retries the rollback", rolled_back=False)
            raise CommitError(f"writing to {self.out} failed ({error!r}) and was rolled back", rolled_back=True)
        os.remove(journal_path)
        self._prune_emptied(removed)

    def _prune_emptied(self, removed):
        """Remove directories this commit emptied, deepest first. After the journal, deliberately.

        Removals can take the last file out of a directory -- `backlog/` when a produce migrates an
        engine past #243. git does not track a directory, so an empty one left behind is invisible
        in a diff and present on disk, which is the worst of both. It is done after the journal is
        deleted because the transaction is over by then and there is nothing left to roll back:
        every directory removed here is empty, so removing it can lose nothing, and a rollback that
        had to recreate directories would need them in the journal for no gain. An `OSError` --
        something arrived in the directory between the check and the call, or it is not ours to
        remove -- leaves the directory alone and is not a failed commit.
        """
        directories = {os.path.dirname(relative) for relative in removed} - {""}
        for relative in sorted(directories, key=lambda p: p.count("/"), reverse=True):
            target = _native(self.out, relative)
            try:
                if os.path.isdir(target) and not os.path.islink(target) and not os.listdir(target):
                    os.rmdir(target)
            except OSError:
                pass


# --- what git was not told -------------------------------------------------------------------


def git_note(out, log=None):
    """Say that the files just written to `out` are uncommitted, when `out` is a git checkout.

    `produce` never runs git in the engine: it writes files, and whoever ran it reviews and commits
    them. The line reporting what was written used to say "committed to <engine>", which read as a
    git commit that had not happened. Returns the note, or None when `out` is not in a git work tree, git
    cannot be run, or the work tree is clean.
    """
    out = os.path.realpath(os.path.abspath(out))
    try:
        done = subprocess.run(["git", "-C", out, "status", "--porcelain"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None  # not a git work tree: nothing to say about commits
    changes = [line for line in done.stdout.splitlines() if line.strip()]
    if not changes:
        return None
    note = (f"git: produce writes files and makes no commit -- {out} has {len(changes)} uncommitted "
            f"change(s); review them (git -C {out} status) and commit")
    if log is not None:
        print(note, file=log)
    return note
