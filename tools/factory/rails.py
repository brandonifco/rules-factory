"""The rails on GitHub: are they there, and are they required? (#155, decision 0029)

`produce` writes files. Files are not enforcement: a workflow that exists is not a workflow that
is required, a label the rails read is not a label the repository has, and a branch anyone can
push to has no gate at all. Closing that gap means changing a repository's settings, which
`produce` must never do quietly -- producing files into a directory and altering who may write to
a repository are different acts with different blast radii.

So it is a command of its own, in two modes:

  * `factory rails --repo owner/name --dir <engine> --check` reads and changes nothing. It reports
    each row in plain English: the agent files, the policy, the labels, the ruleset, each required
    check, the merge method, and the review chain the engine has configured.
  * `--apply` creates what is missing.

**The factory owns one ruleset and never edits another.** GitHub's ruleset update replaces the
whole `rules` array, so writing into a ruleset somebody else authored would silently drop rules
the factory never saw. Rulesets are evaluated together, so a separate one named
`rules-factory-agent-rails` composes with whatever else the repository has -- and the repository's
own protections stay the repository's.

**Merge commits only.** A review verdict is pinned to the pull request's head commit (0029 §7). A
squash merge manufactures a commit that no reviewer ever read; a merge commit keeps the reviewed
commit in the history as a parent. So `--apply` turns squash and rebase merging off, and `--check`
reports it -- the one repository setting outside the ruleset that the verdict mechanism depends on.

**Idempotent.** `--apply` twice in a row changes nothing the second time, and says so.

Standard library only, plus `gh` (or `$FACTORY_GH`).
"""
import json
import os
import re
import subprocess

import generate

RULESET = "rules-factory-agent-rails"
# `verdict-requeue` is deliberately not among them (#191). It runs on the `status` event, so its
# run belongs to the default branch's commit rather than to any pull request, and a required check
# on that commit is a condition on something that has already merged.
REQUIRED_CHECKS = ("validate", "pr-policy", "conformance-gate")
POLICY = ".github/agent-policy.json"
LABEL_COLOURS = {
    # Colour is the one thing here with no consequence, so it is picked once and never argued
    # about: states in blue-greys, risk in amber and red.
    "ready": ("1d76db", "Ready to dispatch: nothing it depends on is still to build"),
    "blocked": ("5a6069", "Something this depends on is not built yet"),
    "needsDecision": ("8a63d2", "Waiting on an owner's ruling; an agent may not answer it"),
    "normalRisk": ("fbca04", "Ordinary risk: the semantic verdict is enough"),
    "independentRisk": ("d93f0b", "Needs a second, independent verdict before it can merge"),
}
OK, MISSING, WRONG = "OK", "MISSING", "WRONG"


class RailsError(Exception):
    """Something the command cannot do. Nothing is changed."""


def _gh(args, gh, method=None, fields=(), check=True):
    command = [gh, *args]
    if method:
        command += ["-X", method]
    for name, value in fields:
        command += ["-f", f"{name}={value}"]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
    if done.returncode != 0 and check:
        raise RailsError(f"`{' '.join(command)}` failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.returncode, done.stdout


def _json(args, gh, default=None):
    code, out = _gh(args, gh, check=default is None)
    if code != 0:
        return default
    try:
        return json.loads(out or "null")
    except ValueError as error:
        raise RailsError(f"`gh {' '.join(args)}` did not return JSON ({error})")


def labels_of(engine_dir):
    """The engine's label vocabulary, from the policy it owns."""
    path = os.path.join(engine_dir, POLICY)
    if not os.path.isfile(path):
        raise RailsError(f"{path} does not exist; run `factory produce` first -- the rails read every label, "
                         f"context and provider from it")
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise RailsError(f"{path} cannot be read ({error})")
    labels = document.get("labels") or {}
    missing = [key for key in LABEL_COLOURS if not labels.get(key)]
    if missing:
        raise RailsError(f"{path} names no {', '.join(sorted(missing))} label")
    return document, labels


def agent_files(engine_dir):
    """Every managed rail the factory emits, and whether the engine has it."""
    return {relative: os.path.isfile(os.path.join(engine_dir, *relative.split("/")))
            for relative in sorted(generate.RAILS)}


def ruleset_payload(branch):
    """The one ruleset the factory owns. Enforcement, not decoration.

    A pull request is required, its threads must be resolved, the branch cannot be deleted or
    force-pushed, and the three checks are required and strict (a pull request must be up to date
    with the branch it merges into, so the checks ran against what will exist afterwards). No
    bypass actor: a rail with an exemption for its author is a rail nobody else can rely on.
    """
    return {
        "name": RULESET,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request",
             "parameters": {"required_approving_review_count": 0,
                            "dismiss_stale_reviews_on_push": False,
                            "require_code_owner_review": False,
                            "require_last_push_approval": False,
                            "required_review_thread_resolution": True,
                            "allowed_merge_methods": ["merge"]}},
            {"type": "required_status_checks",
             "parameters": {"strict_required_status_checks_policy": True,
                            "do_not_enforce_on_create": False,
                            "required_status_checks": [{"context": context} for context in REQUIRED_CHECKS]}},
        ],
    }
    # `branch` is not interpolated: the condition names ~DEFAULT_BRANCH, so the ruleset follows a
    # repository that renames its default branch. It is a parameter only so a caller must have
    # looked it up, and so --check can say which branch this will govern.


def survey(repo, engine_dir, gh):
    """What the repository and the engine have, as rows. Reads only."""
    document, labels = labels_of(engine_dir)
    repository = _json(["api", f"repos/{repo}"], gh)
    branch = repository.get("default_branch") or "main"
    existing_labels = {item["name"] for item in _json(["api", f"repos/{repo}/labels", "--paginate"], gh, default=[])}
    rulesets = _json(["api", f"repos/{repo}/rulesets"], gh, default=[]) or []
    ours = next((item for item in rulesets if item.get("name") == RULESET), None)
    detail = _json(["api", f"repos/{repo}/rulesets/{ours['id']}"], gh) if ours else None

    required = set()
    pull_request = None
    if detail:
        for rule in detail.get("rules") or []:
            if rule.get("type") == "required_status_checks":
                required = {check.get("context")
                            for check in (rule.get("parameters") or {}).get("required_status_checks") or []}
            if rule.get("type") == "pull_request":
                pull_request = rule.get("parameters") or {}

    return {
        "branch": branch,
        "files": agent_files(engine_dir),
        "policy": document,
        "labels": labels,
        "missingLabels": [labels[key] for key in sorted(LABEL_COLOURS) if labels[key] not in existing_labels],
        "ruleset": detail,
        "rulesetEnforced": bool(detail and detail.get("enforcement") == "active"),
        "bypass": (detail or {}).get("bypass_actors") or [],
        "requiredChecks": required,
        "pullRequest": pull_request,
        "mergeOnly": (repository.get("allow_merge_commit") is True
                      and repository.get("allow_squash_merge") is False
                      and repository.get("allow_rebase_merge") is False),
        "chain": [link.get("id") for link in ((document.get("review") or {}).get("independentFallback") or [])],
        "semanticContext": (document.get("review") or {}).get("semanticContext"),
    }


def _row(name, state, note=""):
    dots = "." * max(3, 28 - len(name))
    return f"{name} {dots} {state}" + (f"  -- {note}" if note else "")


def report(state):
    """`--check`'s output: one row per thing that is either true of the repository or not."""
    lines = []
    missing_files = [path for path, present in state["files"].items() if not present]
    lines.append(_row("Agent files", OK if not missing_files else MISSING,
                      "" if not missing_files else f"{len(missing_files)} not in the engine: "
                                                   f"{', '.join(missing_files[:3])}"))
    lines.append(_row("Policy", OK, f"{POLICY}, schemaVersion {state['policy'].get('schemaVersion')}"))
    lines.append(_row("Required labels", OK if not state["missingLabels"] else MISSING,
                      "" if not state["missingLabels"] else ", ".join(state["missingLabels"])))
    lines.append(_row(f"Ruleset on {state['branch']}",
                      OK if state["rulesetEnforced"] else (WRONG if state["ruleset"] else MISSING),
                      RULESET if state["rulesetEnforced"] else
                      (f"{RULESET} exists but is not active" if state["ruleset"] else
                       f"no ruleset named {RULESET}")))
    for context in REQUIRED_CHECKS:
        lines.append(_row(f"Required check: {context}",
                          OK if context in state["requiredChecks"] else MISSING,
                          "" if context in state["requiredChecks"] else "the workflow may exist; it is not required"))
    pull_request = state["pullRequest"]
    lines.append(_row("Pull request required", OK if pull_request else MISSING))
    if pull_request is not None:
        lines.append(_row("Threads resolved", OK if pull_request.get("required_review_thread_resolution") else MISSING))
        methods = pull_request.get("allowed_merge_methods") or []
        lines.append(_row("Merge commits only (ruleset)", OK if methods == ["merge"] else WRONG,
                          "" if methods == ["merge"] else f"allows {', '.join(methods) or 'anything'}; a squash "
                                                          f"merge makes a commit no reviewer read"))
    lines.append(_row("Merge commits only (repo)", OK if state["mergeOnly"] else WRONG,
                      "" if state["mergeOnly"] else "squash or rebase merging is still on"))
    lines.append(_row("No bypass actor", OK if not state["bypass"] else WRONG,
                      "" if not state["bypass"] else f"{len(state['bypass'])} actor(s) may bypass the rails"))
    chain = " -> ".join(state["chain"]) or "none configured"
    lines.append(_row("Review chain", OK if state["chain"] else WRONG, f"{state['semanticContext']}, then {chain}"))
    return lines


def problems(state):
    """The rows that are not OK, as reasons. `--check` exits 1 when there are any."""
    found = []
    missing_files = [path for path, present in state["files"].items() if not present]
    if missing_files:
        found.append(f"the engine is missing {len(missing_files)} rail(s) ({', '.join(missing_files[:3])}...); "
                     f"run `factory produce`")
    if state["missingLabels"]:
        found.append(f"the repository has no {', '.join(state['missingLabels'])} label, so the issues that need "
                     f"them cannot be labelled or dispatched")
    if not state["rulesetEnforced"]:
        found.append(f"no active ruleset named {RULESET}: the branch has no rails, whatever files it holds")
    for context in sorted(set(REQUIRED_CHECKS) - state["requiredChecks"]):
        found.append(f"{context} is not a required check: a workflow that exists is not a workflow that is required")
    if state["pullRequest"] is None:
        found.append("a pull request is not required on the default branch")
    elif (state["pullRequest"].get("allowed_merge_methods") or []) != ["merge"]:
        found.append("the ruleset allows a merge method other than a merge commit; a verdict is pinned to the head "
                     "commit, and a squash merge manufactures a commit nobody reviewed")
    if not state["mergeOnly"]:
        found.append("the repository still allows squash or rebase merging, for the same reason")
    if state["bypass"]:
        found.append(f"{len(state['bypass'])} actor(s) may bypass the ruleset; a rail with an exemption for its "
                     f"author is a rail nobody else can rely on")
    if not state["chain"]:
        found.append(f"{POLICY} configures no independent reviewer, so an issue that needs one can never merge")
    return found


def apply(repo, engine_dir, gh, log):
    """Create what is missing, and nothing else. Returns the number of changes made."""
    state = survey(repo, engine_dir, gh)
    changed = 0

    for key, (colour, description) in sorted(LABEL_COLOURS.items()):
        name = state["labels"][key]
        if name not in state["missingLabels"]:
            continue
        _gh(["api", f"repos/{repo}/labels"], gh, method="POST",
            fields=(("name", name), ("color", colour), ("description", description)))
        print(f"created label {name}", file=log)
        changed += 1

    payload = ruleset_payload(state["branch"])
    existing = state["ruleset"]
    if existing is None:
        # The ruleset goes in as one JSON document on stdin: its rules are nested, and `-f` pairs
        # cannot express them.
        done = subprocess.run([gh, "api", f"repos/{repo}/rulesets", "-X", "POST", "--input", "-"],
                              input=json.dumps(payload), text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=120)
        if done.returncode != 0:
            raise RailsError(f"could not create the ruleset: {done.stderr.strip() or done.stdout.strip()}")
        print(f"created ruleset {RULESET} on {state['branch']}", file=log)
        changed += 1
    elif not matches(existing, payload):
        done = subprocess.run([gh, "api", f"repos/{repo}/rulesets/{existing['id']}", "-X", "PUT", "--input", "-"],
                              input=json.dumps(payload), text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=120)
        if done.returncode != 0:
            raise RailsError(f"could not update the ruleset: {done.stderr.strip() or done.stdout.strip()}")
        print(f"updated ruleset {RULESET} (it is the factory's own; no other ruleset was read or written)", file=log)
        changed += 1

    if not state["mergeOnly"]:
        done = subprocess.run([gh, "api", f"repos/{repo}", "-X", "PATCH",
                               "-F", "allow_merge_commit=true", "-F", "allow_squash_merge=false",
                               "-F", "allow_rebase_merge=false"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        if done.returncode != 0:
            raise RailsError(f"could not restrict the merge methods: {done.stderr.strip() or done.stdout.strip()}")
        print("merge commits only: squash and rebase merging turned off, so the reviewed commit stays in the "
              "history", file=log)
        changed += 1

    return changed


def matches(existing, payload):
    """Whether the factory's ruleset already says what this version of the factory would write.

    Compared on what the rails depend on -- enforcement, conditions, and each rule's type and
    parameters -- rather than on the whole document, which carries ids, timestamps and links that
    say nothing about what is enforced. An equal ruleset is left alone, which is what makes
    `--apply` idempotent.
    """
    if existing.get("enforcement") != payload["enforcement"]:
        return False
    if (existing.get("conditions") or {}).get("ref_name", {}).get("include") != \
            payload["conditions"]["ref_name"]["include"]:
        return False
    if existing.get("bypass_actors"):
        return False
    wanted = {rule["type"]: rule.get("parameters", {}) for rule in payload["rules"]}
    found = {rule.get("type"): rule.get("parameters") or {} for rule in existing.get("rules") or []}
    if set(wanted) - set(found):
        return False
    for kind, parameters in wanted.items():
        for key, value in parameters.items():
            if key == "required_status_checks":
                contexts = {check.get("context") for check in found[kind].get(key) or []}
                if {check["context"] for check in value} - contexts:
                    return False
            elif found[kind].get(key) != value:
                return False
    return True


def run(repo, engine_dir, gh, log, do_apply):
    if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", repo):
        raise RailsError(f"--repo {repo!r} is not owner/name")
    if do_apply:
        changed = apply(repo, engine_dir, gh, log)
        if not changed:
            print("nothing to do: the rails are already in place", file=log)
        print("", file=log)

    state = survey(repo, engine_dir, gh)
    for line in report(state):
        print(line, file=log)
    found = problems(state)
    if found:
        print("", file=log)
        for problem in found:
            print(f"  X  {problem}", file=log)
        print("\n`factory rails --repo <owner/name> --dir <engine> --apply` creates the labels and the factory's "
              "own ruleset. It never reads or writes another ruleset.", file=log)
        return 1
    print("\nThe rails are in place on GitHub, not merely present in the repository.", file=log)
    return 0
