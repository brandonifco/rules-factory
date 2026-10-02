#!/usr/bin/env python3
"""Whether this pull request has the review verdicts it needs, at the commit being merged.

    tools/conformance-gate.py <pr-number>

Emitted by rules-factory as a managed file (decision 0029), and run by
`.github/workflows/conformance-gate.yml` as a required check.

**What it asks.** For the pull request's current head commit:

  1. does the change owe a semantic review? That is decided by its **review class**, computed from
     the diff by the factory's one `scripts/factory/reviewclass.py` (rules-factory 0076): a change
     that touches the semantic surface (`review.semanticPaths`) is a `semantic-implementation`, or
     a `semantic-ruling` when it is a decision that changes how rules are read, unless the diff
     provably is none of that and the pull request claims so -- a new decision record that
     overrules nothing, a regeneration with the maps and corpora unmoved, a document. Then the
     semantic verdict must be recorded, and successful, at that commit.
  2. is the linked issue classified as needing independent review? Then one of the configured
     independent contexts must also be recorded, and successful, at that commit.
  3. is any configured context recorded as a failure at that commit? Then this blocks, whatever
     else is green.

**Why it refuses a truncated file list (#193).** The answer to 1 is derived from the changed paths
and nothing else, which is also what makes it right for a `factory produce` update: a map version
bump rewrites `RulesFactory.Packages.g.props`, the generated code under `src/` and `tests/` and both
lock files, so it is semantic four times over and no author has to say so. But `gh pr view --json
files` returns at most 100 files with no error, and a regeneration writes hundreds. So the count is
asked for with the list, and a short list is undecidable rather than a change that looked small.

**Why the head commit, and not "the pull request".** A verdict is formed on bytes somebody read.
A commit after it means nobody has read the bytes being merged. Because the status lives on the
commit rather than on the pull request, that invalidation is automatic: nothing has to notice.

**Why a recorded failure blocks outright.** The independent chain exists to catch the plausible,
fluent, wrong implementation -- the failure a second reviewer from the same family reproduces
rather than catches. A chain that could be walked until one link agrees would produce exactly the
outcome it exists to prevent, at more expense. So the chain advances only when a provider was
unavailable, and a fail anywhere in it stands until the code, the map or an owner's ruling changes.

A changed path arrives from GitHub relative to the **repository**, and the semantic surface is
written in the engine's own paths. For an engine embedded under a repository root (rules-factory
decision 0069) those are not the same string, and the engine's record says what the difference is
(`repository.enginePath`).

**Where it stays as strict as it was.** The class is the diff's, never the pull request's: a
pull request can claim an exemption the diff shows, or ask for more review, and cannot lower what
the diff computes. A diff that touches the semantic surface and says nothing is an implementation,
exactly as it was; and anything the classifier cannot prove inert -- a file it cannot read, a
record it cannot compare, a module it cannot load -- is an implementation, or an undecidable gate,
which fails.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`).
"""
import argparse
import base64
import binascii
import json
import os
import pathlib
import subprocess
import sys

# The class is decided by the engine's vendored scripts/factory/reviewclass.py, and an imported
# module leaves its bytecode beside it: a path no ownership row covers, so the checkout goes dirty (#194).
sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"


class Undecidable(Exception):
    """The gate cannot tell. It says so and fails: silence is not a pass."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT, timeout=120)
    if done.returncode != 0:
        raise Undecidable(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


# GitHub's REST statuses, spelled as `gh pr view --json files` spells a `changeType`, so a path read
# either way compares the same.
_CHANGE_TYPES = {"added": "ADDED", "removed": "DELETED", "modified": "MODIFIED", "renamed": "RENAMED",
                 "copied": "COPIED", "changed": "CHANGED"}


def listed_files(pull, number):
    """Every changed file of the pull request, as `{"path", "changeType"}` (#562).

    `gh pr view --json files` stops at 100 files without a word, and `changedFiles` says how many
    there are. Where the two disagree, the list is read again from the REST endpoint, which pages
    to 3,000 files; what that returns is still held to `changedFiles` by the caller, so a list
    GitHub will not give whole is refused as it always was, and never judged in part.
    """
    files = [{"path": f["path"], "changeType": f.get("changeType") or ""} for f in pull.get("files") or []]
    count = pull.get("changedFiles")
    if not isinstance(count, int) or len(files) == count:
        return files
    listing = gh("api", f"repos/{{owner}}/{{repo}}/pulls/{number}/files?per_page=100", "--paginate",
                 "--jq", '.[] | [.filename, .status] | @tsv')
    whole = []
    for line in listing.splitlines():
        path, _, status = line.partition("\t")
        if path:
            whole.append({"path": path, "changeType": _CHANGE_TYPES.get(status, status.upper())})
    return whole


def engine_path():
    """This engine's path under its repository root, or "" when the engine **is** that root.

    Read from `provenance.json` (`repository.enginePath`, provenanceFormat 9, rules-factory decision
    0069) and "" for a record that cannot be read or predates it -- which is what every engine that
    is its own repository root has always been. GitHub reports a changed path relative to the
    repository, and for an engine embedded under one that is not the path the semantic surface is
    written in: `engine/src/Rules/X.cs` matches none of `src/**`, so **nothing would ever be
    semantic** and this gate would require no verdict of exactly the work it exists to hold.
    """
    try:
        record = json.loads((ROOT / "provenance.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    section = record.get("repository") if isinstance(record, dict) else None
    return str((section or {}).get("enginePath") or "") if isinstance(section, dict) else ""


def engine_relative(path, prefix):
    """`path`, as GitHub reports it, in the engine's own terms -- or None when it is not the engine's.

    None is a file of the repository the engine is embedded in: its README, its own workflows. Those
    are not on this engine's semantic surface, and a verdict about this engine cannot be about them.
    """
    if not prefix:
        return path
    return path[len(prefix) + 1:] if path.startswith(prefix + "/") else None


def factory_module(name):
    """One of the engine's vendored `scripts/factory` modules, or Undecidable: a gate that cannot load
    what decides the class has no honest answer, and says so rather than falling back to a weaker one."""
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        return __import__(name)
    except ImportError as error:
        raise Undecidable(f"scripts/factory/{name}.py is not importable ({error}); run `factory produce` again")
    finally:
        sys.path.pop(0)


def engine_name():
    try:
        record = json.loads((ROOT / "provenance.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    name = (record.get("engine") or {}).get("name") if isinstance(record, dict) else None
    return name if isinstance(name, str) and name else None


def base_bytes(base_oid, path):
    """The bytes of `path` (as GitHub spells it) at the commit the pull request is based on, or None."""
    try:
        return base64.b64decode(gh("api", f"repos/{{owner}}/{{repo}}/contents/{path}?ref={base_oid}",
                                   "--jq", ".content"))
    except (Undecidable, ValueError, binascii.Error):
        return None


def review_class(changed, patterns, prefix, body, base_oid):
    """`(result, effective class, problems, hints, declared)` for the diff, in the engine's own terms.

    `changed` is `{path as GitHub reports it: change type}`. The head's bytes are read from this
    checkout and the base's from the API, only for the files the class needs them for. Where the
    engine's own ownership table cannot be loaded nothing is the factory's, so nothing is exempt.
    """
    reviewclass = factory_module("reviewclass")
    inside = {}
    for path, change in changed.items():
        relative = engine_relative(path, prefix)
        if relative is not None:
            inside[relative] = change
    name = engine_name()
    try:
        ownership = factory_module("ownership")
        fclass = reviewclass.factory_class(ownership, name) if name else (lambda _path: None)
    except Undecidable:
        fclass = lambda _path: None  # noqa: E731

    def read(path, side):
        if side == "head":
            try:
                return (ROOT / path).read_bytes()
            except OSError:
                return None
        return base_bytes(base_oid, f"{prefix}/{path}" if prefix else path) if base_oid else None

    result = reviewclass.classify(inside, patterns, read=read, fclass=fclass)
    declared = reviewclass.declared_class(body)
    effective, problems, hints = reviewclass.judge(result, declared)
    return result, effective, problems, hints, declared, reviewclass


def statuses(repository, sha):
    """context -> state, the most recent status per context at `sha`."""
    document = json.loads(gh("api", f"repos/{repository}/commits/{sha}/status", "--paginate"))
    found = {}
    for status in document.get("statuses") or []:
        found.setdefault(status["context"], status["state"])
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(prog="conformance-gate.py", description=__doc__.split("\n")[0])
    parser.add_argument("pr", type=int)
    args = parser.parse_args(argv)

    try:
        with open(ROOT / POLICY, encoding="utf-8") as handle:
            review = (json.load(handle).get("review") or {})
        semantic_context = review.get("semanticContext")
        chain = review.get("independentFallback") or []
        if not semantic_context:
            raise Undecidable(f"{POLICY} sets no review.semanticContext")

        pull = json.loads(gh("pr", "view", str(args.pr), "--json",
                             "number,headRefOid,baseRefOid,body,files,changedFiles,closingIssuesReferences"))
        sha = pull.get("headRefOid")
        if not sha:
            raise Undecidable(f"PR #{args.pr} has no head commit")
        changed = [f["path"] for f in listed_files(pull, args.pr)]
        # `gh pr view --json files` caps at 100 files, silently: no error, no warning, and
        # `changedFiles` says how many there really are; `listed_files` reads the rest from the
        # REST endpoint (#562), and what is still short is refused here. Which verdicts this change needs is decided
        # from these paths alone, so on a partial list the answer "nothing on the semantic surface"
        # can be produced by files nobody listed -- and a map version bump, which regenerates
        # hundreds of files, is exactly the change that reaches the cap. An undecidable gate fails.
        count = pull.get("changedFiles")
        if isinstance(count, int) and len(changed) != count:
            raise Undecidable(f"GitHub listed {len(changed)} of PR #{args.pr}'s {count} changed files, so the file "
                              f"list is truncated. The semantic surface cannot be decided from a partial list, and "
                              f"a gate that decides on half the files is the failure this check exists to prevent")
        # Which verdicts this change needs is its review class's to say (0076). The surface is still
        # the policy's: it decides which paths *can* be semantic, and the class decides which of
        # those the diff proves are not.
        changes = {f["path"]: f["changeType"] for f in listed_files(pull, args.pr)}
        result, effective, problems_of_class, hints, declared, reviewclass = review_class(
            changes, review.get("semanticPaths") or [], engine_path(), pull.get("body") or "",
            pull.get("baseRefOid"))
        touched = list(result["semanticFiles"]) if effective in reviewclass.SEMANTIC else []

        issues = pull.get("closingIssuesReferences") or []
        if len(issues) != 1:
            raise Undecidable(f"PR #{args.pr} closes {len(issues)} issues; exactly one is required "
                              f"(pr-policy.py says the same, and says it first)")
        issue = json.loads(gh("issue", "view", str(issues[0]["number"]), "--json", "number,labels"))
        names = {label["name"] for label in issue.get("labels") or []}

        with open(ROOT / POLICY, encoding="utf-8") as handle:
            labels = json.load(handle).get("labels") or {}
        independent_required = labels.get("independentRisk") in names

        repository = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
        recorded = statuses(repository, sha)
    except (Undecidable, OSError, ValueError, KeyError) as error:
        print(f"conformance-gate: cannot decide PR #{args.pr} -- {error}", file=sys.stderr)
        print("An undecidable gate fails. A check that cannot examine what it is for is not a pass.", file=sys.stderr)
        return 2

    print(f"conformance-gate: PR #{args.pr}, head {sha[:12]}")
    print(f"  semantic surface: {len(touched)} changed file(s)" + (f" ({', '.join(touched[:4])})" if touched else ""))
    for line in reviewclass.describe(result, effective, declared):
        print(f"  {line}")
    for line in hints + problems_of_class:
        print(f"  note: {line}")
    print(f"  recorded at this commit: {', '.join(f'{c}={s}' for c, s in sorted(recorded.items())) or 'nothing'}")

    problems = []
    configured = [semantic_context] + [link.get("context") for link in chain]
    for context in configured:
        if recorded.get(context) in ("failure", "error"):
            problems.append(f"{context} is recorded as a failure at {sha[:12]}. A recorded failure blocks outright: "
                            f"fix the code, fix the map, or get an owner's ruling. Recording a pass at another "
                            f"context does not clear it.")

    if touched and recorded.get(semantic_context) != "success":
        problems.append(f"{semantic_context} is not recorded as a success at {sha[:12]}, and this change is a "
                        f"`{effective}`, which owes a semantic verdict. Review the head commit and record the verdict "
                        f"(`tools/review-packet.py {args.pr}`, then `tools/record-verdict.py --pr "
                        f"{args.pr} --reviewer semantic --verdict pass --packet <its .review.json>`). "
                        f"A verdict on an earlier commit is a verdict on bytes nobody is merging.")

    if independent_required:
        passed = [link.get("context") for link in chain if recorded.get(link.get("context")) == "success"]
        if not passed:
            names = " or ".join(link.get("context", "?") for link in chain)
            problems.append(f"issue #{issue['number']} is {labels.get('independentRisk')}, so one of {names} must "
                            f"also be recorded as a success at {sha[:12]}. The chain is tried in order, and it "
                            f"advances only when a provider is unavailable.")
        else:
            print(f"  independent verdict: {passed[0]}")

    if problems:
        print(f"\nconformance-gate: BLOCKED ({len(problems)}):")
        for problem in problems:
            print(f"  X  {problem}")
        return 1
    if not touched:
        print(f"  a `{effective}` change owes no rules verdict: structural and provenance validation are "
              f"pr-policy's, and this gate asks for nothing more")
    print("\nconformance-gate: the verdicts this change needs are recorded at the commit being merged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
