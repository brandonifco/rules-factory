"""Where a produced engine sits in its repository, and the automation the repository root owns
(#501, decision 0069).

GitHub runs a workflow file only when it is in `.github/workflows/` **at the root of the
repository**. An engine that is its own repository root therefore carries its four workflows and
they run, which is what every engine produced before this module was. An engine produced into a
subdirectory of a larger repository -- `host/engine/` beside a corpus, packaging and archive
material -- carried the same four files where GitHub never looks: the gate, the pull request
policy, the conformance gate and the verdict requeue were all dark, while `provenance.json`
recorded them as generated and `tools/agent-doctor.py` reported them present. Nothing said that
not one of them could ever run.

So where the engine sits is a fact about the run, decided here before anything is written:

  * **standalone** -- `--out` is the repository root (or is in no repository at all). The four
    workflows are the engine's own files, at the paths they have always had, byte for byte as
    before. `enginePath` is null in `provenance.json`.
  * **embedded** -- `--out` lies under the repository root named by `--repo-root`. The same four
    recipes are rendered for the engine's path beneath that root and written **there**; the engine
    is written with no `.github/workflows/` at all. A copy under the engine is not kept as a
    template: an inert file that reads as an active rail is the whole harm.

One rendering, from the same recipes. `recipes()` reads exactly the bytes `gate.py` and
`agentrails.py` would have written into the engine, and `render()` adds what the repository root
needs and nothing else: a job-level `defaults.run.working-directory`, so every `run:` step
executes in the engine, a note saying who wrote the file and why it is here, and -- in the gate
workflow alone -- the step that holds these bytes to the record (`engine-gate.py repository`).
There is no second copy of any gate to drift from the first.

`assure_active()` is the invariant, as code: a run that writes a workflow file at all writes one
where GitHub will run it. It is called after emission, over every path the run wrote, and refuses
rather than reports.

Standard library only. Not vendored into an engine: an engine reads its own topology from
`provenance.json` (`repository`), which is where `scripts/engine-gate.py repository`,
`tools/pr-policy.py` and `tools/agent-doctor.py` all read it.
"""
import collections
import hashlib
import os
import posixpath
import subprocess

import agentrails
import gate
import intake as intake_step

#: The four workflows that belong to a repository, in the order they are reported. The published
#: path each has when the engine is the repository root -- and, under an embedded engine's
#: repository root, the path it has there: the same file, in the one place GitHub reads.
WORKFLOWS = (".github/workflows/validate.yml",
             ".github/workflows/pr-policy.yml",
             ".github/workflows/conformance-gate.yml",
             ".github/workflows/verdict-requeue.yml")

#: The pull request template. GitHub reads one only from the repository root (or `docs/`, or the
#: root itself), so an embedded engine's copy is as unread as its workflows were: every pull request
#: opened against the repository arrives with an empty body, and `tools/pr-policy.py` -- the check
#: that reads that body -- fails every one of them for sections nobody was shown.
TEMPLATE = ".github/pull_request_template.md"

#: Everything a repository root holds for an embedded engine, in the order it is reported.
FILES = WORKFLOWS + (TEMPLATE,)

#: The directory GitHub reads workflows from. Everything about this module follows from the fact
#: that it is read at the repository root and nowhere else.
WORKFLOW_DIR = ".github/workflows"

TEMPLATE_NOTE = """<!--
Rendered by rules-factory for the engine at `{path}/` (decision 0069). GitHub reads a pull request
template only from the repository root, so this repository's root carries the engine's pull request
contract: **every path named below is relative to `{path}/`**, which is where the commands are run.

Factory-managed and generated: rewritten by every `factory produce`, and a hand edit here is
overwritten. Change the recipe in the factory, not this file.
-->

"""

#: The last line of the checkout step, identical in all four recipes: where a step the repository
#: root adds is inserted, after the tree is on disk and before anything reads it.
AFTER_CHECKOUT = "          persist-credentials: false\n"

NOTE = """# Rendered by rules-factory for the engine at `{path}/` (decision 0069). GitHub runs a workflow
# only from `.github/workflows/` at the **root** of a repository, so an engine embedded under one
# does not own its rails: this repository's root does, and every `run:` step below executes in
# `{path}/`. The engine carries no `.github/workflows/` of its own -- a copy there would be inert,
# and reading as an active rail is the harm this exists to prevent.
#
# Factory-managed and generated: rewritten by every `factory produce`, and a hand edit here is
# overwritten and fails `{path}/scripts/engine-gate.py repository`. Change the recipe in the
# factory, not this file. A workflow this repository owns itself is any other file in this
# directory; the factory writes {count} paths under `.github/` and touches nothing else.
"""

#: The step the gate workflow gains at a repository root: the bytes in this directory are the ones
#: the engine's record says the factory wrote. It runs in the engine (the job's working directory)
#: and is given the repository root, which on a runner is the checkout.
RECORD_STEP = """      - name: The repository's workflows are the bytes the engine's record names
        run: python3 scripts/engine-gate.py repository --root "$GITHUB_WORKSPACE"

"""


class RepositoryError(intake_step.Refused):
    """A topology that cannot be acted on, or a recipe this module cannot render.

    A refusal, like every other in `produce`: nothing is written, and the run says why. It is
    raised before the staging copy exists wherever it can be, so "Nothing was produced." is true
    of the engine **and** of the repository root.
    """


class Topology(collections.namedtuple("Topology", "root engine_path")):
    """Where the engine is. `root` is the repository root; `engine_path` its path under it, or None.

    None, not "" or ".": the standalone case is the absence of a path, and every reader of
    `provenance.json` sees the same absence.
    """

    @property
    def embedded(self):
        return self.engine_path is not None

    @property
    def depth(self):
        """How many directories up from the engine the repository root is. 0 when standalone."""
        return 0 if not self.embedded else len(self.engine_path.split("/"))

    def record(self, automation=()):
        """The `repository` section of provenance.json: where the engine is, and what the root holds."""
        return {"enginePath": self.engine_path,
                "automation": [{"path": path, "sha256": digest} for path, digest in automation]}


def _real(path):
    return os.path.realpath(os.path.abspath(path))


def _existing(path):
    """`path` or the nearest ancestor of it that exists: what git can be asked about."""
    path = _real(path)
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent
    return path


def git_root(path):
    """The top level of the git work tree `path` is in, or None. Read, never written.

    The one fact that decides whether a produce is about to write inert workflows, and it is
    asked of git rather than declared, because the engine's own location is not a matter of
    opinion. A `--out` that does not exist yet is asked about through its nearest existing
    ancestor: produce creates it inside whatever repository that is.
    """
    where = _existing(path)
    if where is None:
        return None
    try:
        done = subprocess.run(["git", "-C", where, "rev-parse", "--show-toplevel"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    top = done.stdout.strip()
    return _real(top) if top else None


def under(root, out):
    """`out`'s path relative to `root` as POSIX, or None when `out` is not under `root`."""
    root, out = _real(root), _real(out)
    if root == out:
        return ""
    relative = os.path.relpath(out, root).replace(os.sep, "/")
    if relative == ".." or relative.startswith("../") or posixpath.isabs(relative):
        return None
    return relative


def decide(out, repo_root=None):
    """The topology of this run, or a refusal. Called before anything is written.

    With no `--repo-root`, git is asked where `--out` is. `--out` that is a repository root, or is
    in no repository, is standalone and produces exactly what it always did. `--out` **under** a
    repository root is refused: the four workflows would be written where GitHub cannot run them,
    and the factory does not write a rail it knows is dark. The refusal names both answers --
    `--repo-root <top level>` for an engine embedded in that repository, `--repo-root <out>` for an
    engine that is deliberately its own repository root inside another checkout (a trial, a scratch
    copy) and wants the workflows it has always had.
    """
    out = _real(out)
    if repo_root is None:
        top = git_root(out)
        if top is None or top == out:
            return Topology(out, None)
        raise RepositoryError(
            f"--out {out} is not the root of its repository: git reports the root as {top}. GitHub runs a "
            f"workflow only from .github/workflows/ at the repository root, so the four workflows produce "
            f"writes -- the gate, the pull request policy, the conformance gate and the verdict requeue -- "
            f"would be written under the engine, where nothing would ever run them, and the engine would "
            f"carry rails that are dark while its record called them generated (decision 0069). Say which "
            f"this is: --repo-root {top} writes them at that repository's root, rendered to run in "
            f"{under(top, out)}/; --repo-root {out} declares this engine its own repository root and writes "
            f"them where it always did")
    root = _real(repo_root)
    if os.path.lexists(root) and not os.path.isdir(root):
        raise RepositoryError(f"--repo-root {root} exists and is not a directory")
    relative = under(root, out)
    if relative is None:
        raise RepositoryError(f"--repo-root {root} does not contain --out {out}; the repository root is an "
                              f"ancestor of the engine, or the engine itself")
    if not relative:
        # `--repo-root` equal to `--out`: the engine is declared its own repository root, which is
        # what a trial or a scratch copy inside another checkout is. git is not asked to contradict
        # it -- the declaration is exactly for the case where git's answer is not the one wanted --
        # and the engine keeps the workflows it has always had.
        return Topology(root, None)
    top = git_root(root)
    if top is not None and top != root:
        raise RepositoryError(
            f"--repo-root {root} is not a repository root: git reports the root of the repository it is in as "
            f"{top}. Workflows written at {root}/{WORKFLOW_DIR} would not be run by GitHub either, which is "
            f"the whole of what this declaration is for (decision 0069)")
    return Topology(root, relative)


def from_record(record):
    """The topology a `provenance.json` records, for a reader that has the record and not the run."""
    section = (record or {}).get("repository")
    if not isinstance(section, dict):
        # A record written before format 9 says nothing about the topology, and an engine produced
        # by that factory was written as a repository root, which is what it was assumed to be.
        return Topology("", None)
    path = section.get("enginePath")
    return Topology("", str(path) if path else None)


def recipes(name):
    """The recipes as the engine would have received them: published path -> text.

    Read from `gate.py` and `agentrails.py`, so the repository root and a standalone engine are
    rendered from one sequence of bytes and there is no second copy of any workflow to drift.
    """
    found = {}
    for relative, (data, _executable) in gate.files(name).items():
        if relative in WORKFLOWS:
            found[relative] = data.decode("utf-8")
    for relative, text in agentrails.rails_files().items():
        if relative in FILES:
            found[relative] = text
    missing = [w for w in FILES if w not in found]
    if missing:
        raise RepositoryError(f"the factory no longer writes {', '.join(missing)}; repository.WORKFLOWS names a "
                              f"file no recipe produces")
    return found


def render(text, engine_path, where=""):
    """`text` as the repository root's copy of it: the note, the working directory, the record step.

    Three additions and no other change, each refused rather than guessed at when the recipe does
    not have the shape they are inserted into -- a recipe that grows a second job, or loses its
    checkout, is a change to what a repository root should run, and this cannot know what.
    """
    if not engine_path:
        return text
    if where == TEMPLATE:
        return TEMPLATE_NOTE.format(path=engine_path) + text
    head, separator, rest = text.partition("\n")
    if not separator or not head.startswith("name:"):
        raise RepositoryError(f"{where or 'the recipe'} does not begin with a `name:` line; "
                              f"the repository root's note is inserted after it")
    runs_on = [line for line in text.split("\n") if line.startswith("    runs-on:")]
    if len(runs_on) != 1:
        raise RepositoryError(f"{where or 'the recipe'} has {len(runs_on)} jobs (`    runs-on:` lines); the "
                              f"working directory is set on the one job each repository workflow has")
    defaults = f"    defaults:\n      run:\n        working-directory: {engine_path}\n"
    body = rest.lstrip("\n").replace(runs_on[0] + "\n", defaults + runs_on[0] + "\n", 1)
    if where == WORKFLOWS[0]:
        if body.count(AFTER_CHECKOUT) != 1:
            raise RepositoryError(f"{where} does not check out the repository exactly once; the step that holds "
                                 f"this directory to the engine's record is inserted after the checkout")
        body = body.replace(AFTER_CHECKOUT, AFTER_CHECKOUT + "\n" + RECORD_STEP.rstrip("\n") + "\n", 1)
    return f"{head}\n\n{NOTE.format(path=engine_path, count=len(FILES))}#\n{body}"


def files(name, topology):
    """What the repository root holds for this engine: published path -> bytes. {} when standalone.

    Empty for a standalone engine because the engine's own `.github/` **is** the repository root's:
    the same files, written by `gate.emit` and `generate.produce` as they always were.
    """
    if not topology.embedded:
        return {}
    return {relative: render(text, topology.engine_path, relative).encode("utf-8")
            for relative, text in recipes(name).items()}


def is_workflow(relative):
    """Whether an engine-relative path is a file GitHub would read as a workflow at a root."""
    return relative.startswith(WORKFLOW_DIR + "/") and relative.endswith((".yml", ".yaml"))


def assure_active(topology, engine_paths, repository_paths):
    """Refuse a run that wrote a workflow file and none that GitHub will run (#501).

    The invariant, as code and not as care: a production mode that claims workflow integration
    and emits every workflow below an embedded engine is exactly the bug of #501, and this is
    what fails when it returns by another road -- a recipe added to `RAILS` without a thought
    for the topology, a `--repo-root` threaded through half the emission. Called after emission,
    over what the run actually wrote, so it answers for the files and not for the intent.
    """
    inert = sorted(p for p in engine_paths if is_workflow(p))
    active = sorted(p for p in repository_paths if is_workflow(p))
    if not topology.embedded:
        if active:
            raise RepositoryError(f"this run wrote {', '.join(active)} outside a standalone engine, whose own "
                                 f"{WORKFLOW_DIR} is its repository's")
        return
    if inert:
        raise RepositoryError(
            f"this run wrote {', '.join(inert)} under an engine embedded at {topology.engine_path}/, where "
            f"GitHub will never run them: a workflow file is read only from {WORKFLOW_DIR} at the repository "
            f"root (decision 0069). Nothing was written")
    if not active:
        raise RepositoryError(
            f"this run wrote no workflow at the repository root for an engine embedded at "
            f"{topology.engine_path}/, so the engine has no gate, no pull request policy and no conformance "
            f"gate anywhere GitHub can run one (decision 0069). Nothing was written")


# --- putting it in place ---------------------------------------------------------------------


#: The directory of a repository root the factory writes into. Everything it writes there is under
#: this one directory, which is what makes the transaction below small and what it stages.
ROOT_DIR = ".github"


def _recorded_hash(record, relative, *sections):
    """The sha256 a record holds for `relative` in any of `sections`, or "" when it holds none."""
    for section in sections:
        items = ((((record or {}).get("repository") or {}).get("automation")) if section == "repository"
                 else (record or {}).get(section))
        for item in items or []:
            if isinstance(item, dict) and item.get("path") == relative:
                return str(item.get("sha256") or "")
    return ""


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def digests(automation):
    """`[(path, sha256)]` for what the repository root holds, sorted: what the record names."""
    return [(path, _sha256(data)) for path, data in sorted(automation.items())]


def refuse_unowned(topology, automation, record):
    """Refuse before anything is written when a repository-level path is not the factory's to write.

    A repository root is somebody's product, not an empty lot. A file at one of these paths that
    the factory did not write -- a `validate.yml` the repository kept by hand, a pull request
    template the product wrote for itself -- is not overwritten silently: the run says which path,
    and the two ways on are to remove it, so the recipe writes it, or to keep it under a name the
    factory does not write. Bytes this run would write anyway, and bytes the last run's record
    names, are the factory's own and pass.
    """
    for relative, data in sorted(automation.items()):
        path = os.path.join(topology.root, *relative.split("/"))
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            present = handle.read()
        # The factory's own, either way: the bytes this run would write, or a path the last run's
        # record says it wrote here. A path the record names whose bytes have since moved is a hand
        # edit of a generated file, and generated means the recipe wins -- the edit is overwritten,
        # as it is anywhere else in an engine. What is protected here is a file the factory never
        # wrote, which is a different thing and the only thing this refuses over.
        if present == data or _recorded_hash(record, relative, "repository"):
            continue
        raise RepositoryError(
            f"{path} exists and is not a file this factory wrote: an engine embedded at "
            f"{topology.engine_path}/ takes its rails from the repository root, and this run would write "
            f"{relative} over bytes it cannot account for. Nothing was written. Remove that file if the "
            f"factory's copy replaces it (the recipe writes every rail, the private-distribution guardrail "
            f"included), or rename it if it is the repository's own workflow -- the factory writes these "
            f"{len(FILES)} paths and touches nothing else in {ROOT_DIR}/")


def commit(topology, automation, log=None):
    """Put the repository root's files in place, transactionally; returns (added, changed, removed).

    A transaction of its own, over `<root>/.github` alone, and it runs **after** the engine's:
    every refusal this run can make has been made by then, so the ordinary outcomes are both roots
    written or neither. What is left if the write itself fails mid-way -- a full disk, a killed
    process -- is an engine in place and a repository root rolled back by the journal, which the
    next `produce` completes; the run says so rather than reporting a success.

    Files in `<root>/.github` the factory does not write are copied and left exactly as they are:
    the mutation set is the paths this run writes, and nothing else is touched (transaction.py).
    """
    if not automation:
        return [], [], []
    import transaction  # here, not at import: only a run that writes a repository root needs it
    directory = os.path.join(topology.root, ROOT_DIR)
    with transaction.Stage(directory, log=log) as stage:
        for relative, data in sorted(automation.items()):
            inside = relative.split("/")[1:]  # without the `.github/` this stage is rooted at
            path = os.path.join(stage.root, *inside)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(data)
            os.chmod(path, 0o644)
        return stage.commit()


def remove_inert(out, name, record):
    """Delete an embedded engine's own `.github` rails: the repository root holds them now (0069).

    Returns `(removed, kept)` -- the engine-relative paths deleted, and `[(path, why)]` for every
    inert file left where it is. Called by `produce` in the staging copy, so the deletions are part
    of the one transaction and a refused run removes nothing, and called with the record the engine
    had **before** this run, which is what says who wrote each file.

    Only the factory's own bytes are deleted, by the same rule `ownership.remove_retired` deletes
    by: the record hashed the file, and the bytes on disk are still that hash. Anything else -- a
    workflow somebody added under the engine, a rail edited since the last produce -- is kept and
    named, because a file that cannot run where it is is exactly what its owner needs to be told
    about, and deleting an edit nobody has seen would be worse than leaving it.
    """
    removed, kept = [], []
    root = os.path.join(out, *ROOT_DIR.split("/"))
    if not os.path.isdir(root):
        return removed, kept
    for directory, _dirs, names in os.walk(root):
        for leaf in sorted(names):
            path = os.path.join(directory, leaf)
            relative = os.path.relpath(path, out).replace(os.sep, "/")
            if relative not in FILES:
                # Not the factory's, and still unrunnable where it is: a workflow somebody added
                # under the engine is named, so nobody reads it as a rail (#501). Anything else
                # under `.github` -- the engine-owned agent policy, which the engine's own scripts
                # read by path and GitHub never looks at -- is where it belongs and is not mentioned.
                if is_workflow(relative):
                    kept.append((relative, "GitHub reads no workflow below the repository root, and the factory "
                                           "did not write this one, so it is left where it is"))
                continue
            with open(path, "rb") as handle:
                data = handle.read()
            recorded = _recorded_hash(record, relative, "generated", "managed")
            if recorded and recorded == _sha256(data):
                os.remove(path)
                removed.append(relative)
            else:
                kept.append((relative, "the bytes are not the ones the engine's record hashed, so this is not "
                                       "the factory's to delete; GitHub will not read it here"))
    return removed, sorted(kept)
