"""`produce` is transactional (#67): a refusal leaves `--out` as it was.

Every step of `produce` -- generation, the gate recipe, backlog, provenance -- writes into a
staging copy of the engine, never into `--out`. Only when every step has passed is the result
committed. A refusal before that point removes the staging copy, so `--out` is byte-identical to
how it started and "Nothing was produced." is true; a fresh `--out` is not created.

Staging. A working directory is made beside `--out` (in its parent, or the nearest ancestor that
exists when the parent does not), so it is on the same filesystem and `os.replace` into `--out`
is atomic. It holds `engine/`, the staging copy, and `backup/`. The copy is of `--out` minus
`bin`, `obj`, `.git` and `.vs` at any depth (provenance.COPY_IGNORE, what `recompute` skips):
no step reads or writes those, and they are the large ones. They are skipped when computing the
mutation set too, so they are never touched. Symlinks are followed when copying (a dangling one
is not copied, and not counted as removed), so no step can write through a link to outside the
staging copy.

The mutation set. Right after the copy, each staged file's size, executable bit and SHA-256 is
noted. After the steps, a file is added when it is new, changed when its bytes or executable bit
differ from what was copied, and removed when it was copied and is gone. The executable bit is the
only part of a mode git tracks, and the only part compared: the gate recipe writes 0644 and 0755,
and a clone made under umask 002 has 0664 and 0775, so comparing whole modes counted files git
sees as unchanged as changed. A file whose other mode bits alone differ is left as it is in
`--out`. Removal is not a concept invented here:
backlog.py deletes item files that are no longer in the backlog, and nothing else deletes
anything. Comparing against the snapshot rather than against `--out` at commit time means a
file someone edits in `--out` while `produce` runs is not reverted; and before committing, every
path in the set is checked against `--out` again (a changed or removed file still as it was
copied, an added one still absent), and the run is refused, with nothing written, if not.

The commit, for a fresh `--out`: its missing parents are created and the staging copy is renamed
into place, one atomic rename. For an existing `--out`:

  1. every file to change or remove is copied to `backup/`;
  2. the journal, `--out/.factory-produce-journal.json`, is written atomically and fsynced. It
     names `--out`, the working directory, and the added, changed and removed paths and the
     directories to create. Its existence means the backups are complete;
  3. directories are created, each added or changed file is `os.replace`d into place, each
     removed file is deleted;
  4. the journal is deleted, then the working directory.

A failure in step 3 (an exception, KeyboardInterrupt included) is rolled back at once: added
files and created directories are removed, changed and removed files are restored from
`backup/`. Rollback is idempotent, so it is safe to repeat. If the process dies instead, the
journal stays, and the next `produce` into that `--out` rolls it back before anything else,
says so, and then runs as usual. Rolling back rather than refusing: the backups make it exact,
and a refusal would leave the engine half-committed until someone repaired it by hand. A journal
that cannot be read, names a different directory (a copy of an engine taken mid-commit, as
`recompute` makes), or whose rollback fails, is refused, naming the journal and the backups.

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
import tempfile

import intake as intake_step

JOURNAL = ".factory-produce-journal.json"
JOURNAL_FORMAT = 1
SKIP = frozenset({"bin", "obj", ".git", ".vs"})


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


def _native(root, relative):
    return os.path.join(root, *relative.split("/"))


def _existing_ancestor(path):
    while not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return path


# --- rollback --------------------------------------------------------------------------------


def _rollback(journal):
    out, work = journal["out"], journal["work"]
    backup = os.path.join(work, "backup")
    for relative in journal["added"]:
        target = _native(out, relative)
        if os.path.lexists(target):
            os.remove(target)
    restoring = os.path.join(work, "restoring")
    for relative in journal["changed"] + journal["removed"]:
        shutil.copy2(_native(backup, relative), restoring)
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
    """A staging copy of `out` that every step writes into, committed to `out` by `commit()`.

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

    def plan(self):
        """(added, changed, removed): relative paths, each sorted."""
        after = _files(self.root)
        added = sorted(p for p in after if p not in self.snapshot)
        changed = sorted(p for p in after if p in self.snapshot and _signature(after[p]) != self.snapshot[p])
        removed = sorted(p for p in self.snapshot if p not in after)
        return added, changed, removed

    def commit(self):
        """Put the staged engine in place of `out`; returns (added, changed, removed)."""
        added, changed, removed = self.plan()
        if self.fresh:
            self._commit_fresh()
        else:
            self._commit_existing(added, changed, removed)
        self.committed = True
        if self.log is not None:
            print(f"committed to {self.out}: {len(added)} added, {len(changed)} changed, {len(removed)} removed",
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

    def _commit_existing(self, added, changed, removed):
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
                raise CommitError(f"committing to {self.out} failed ({error!r}), and rolling back failed too "
                                  f"({second!r}); the journal {journal_path} names every path, and the files "
                                  f"it changed or removed are backed up under {backup}. The next produce into "
                                  f"{self.out} retries the rollback", rolled_back=False)
            raise CommitError(f"committing to {self.out} failed ({error!r}) and was rolled back", rolled_back=True)
        os.remove(journal_path)
