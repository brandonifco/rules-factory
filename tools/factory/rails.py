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

**A ruleset carrying the factory's name is compared in full (#185).** Its target, its enforcement,
its conditions -- exclusions included, and a condition the factory does not model is a mismatch,
not something to skip -- its bypass actors, and every rule's parameters. `--check` says OK only
about the ruleset `--apply` would write, because a ruleset that keeps the name while excluding the
default branch protects nothing, and a doctor that reads half the document is how that goes unseen.

**Merge commits only.** A review verdict is pinned to the pull request's head commit (0029 §7). A
squash merge manufactures a commit that no reviewer ever read; a merge commit keeps the reviewed
commit in the history as a parent. So `--apply` turns squash and rebase merging off, and `--check`
reports it -- the one repository setting outside the ruleset that the verdict mechanism depends on.

**A required check is pinned to the app that posts it (#186).** A required status check matches by
context name, and anyone with status-write access on the repository can post a commit status under
any name -- so an unpinned `conformance-gate` is satisfied by a collaborator typing the words. The
three checks are GitHub Actions workflows this factory emits, so each is pinned by `integration_id`
to the GitHub Actions app on the host the repository lives on, and a status from anywhere else no
longer counts. **The verdict contexts cannot be pinned this way**, because a verdict is a commit
status posted by whoever ran `tools/record-verdict.py` and `integration_id` pins to an app, not to
a person: that limit is stated in 0029 §7 and in the emitted `AGENTS.md`, where the rails are
decided, rather than left for a reader to infer.

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
# The app that posts them. All three are workflows in the engine, so the app is GitHub Actions --
# but its id is per host (github.com and each Enterprise Server have their own), so it is looked
# up through the same `gh` and never written down here.
CHECKS_APP = "github-actions"
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
    try:
        # The same check `backlog.py` reads the policy through, stated once where the file is
        # written (#188): five labels, none empty, no two the same.
        labels = generate.policy_labels(document, path)
    except generate.PolicyError as error:
        raise RailsError(str(error))
    return document, labels


def agent_files(engine_dir):
    """Every managed rail the factory emits, and whether the engine has it."""
    return {relative: os.path.isfile(os.path.join(engine_dir, *relative.split("/")))
            for relative in sorted(generate.RAILS)}


def checks_app(gh):
    """The id of the app that posts the three required checks, or None if it cannot be read.

    `integration_id` in a required status check is what makes the check mean "this app said so"
    rather than "something said so under that name" (#186). The id differs per host, so it is
    read from the host rather than hard-coded; GitHub Enterprise Server installs the same app
    under the same slug with an id of its own.
    """
    document = _json(["api", f"apps/{CHECKS_APP}"], gh, default={}) or {}
    identifier = document.get("id")
    return identifier if isinstance(identifier, int) else None


def ruleset_payload(branch, app):
    """The one ruleset the factory owns. Enforcement, not decoration.

    A pull request is required, its threads must be resolved, the branch cannot be deleted or
    force-pushed, and the three checks are required, strict (a pull request must be up to date
    with the branch it merges into, so the checks ran against what will exist afterwards) and
    pinned to `app`, the GitHub Actions app that runs the emitted workflows. No bypass actor: a
    rail with an exemption for its author is a rail nobody else can rely on.
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
                            "required_status_checks": [{"context": context, "integration_id": app}
                                                       for context in REQUIRED_CHECKS]}},
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

    app = checks_app(gh)
    required = {}
    pull_request = None
    if detail:
        for rule in detail.get("rules") or []:
            if rule.get("type") == "required_status_checks":
                required = {check.get("context"): check.get("integration_id")
                            for check in (rule.get("parameters") or {}).get("required_status_checks") or []}
            if rule.get("type") == "pull_request":
                pull_request = rule.get("parameters") or {}

    return {
        "branch": branch,
        "checksApp": app,
        "files": agent_files(engine_dir),
        "policy": document,
        "labels": labels,
        "missingLabels": [labels[key] for key in sorted(LABEL_COLOURS) if labels[key] not in existing_labels],
        "ruleset": detail,
        "rulesetEnforced": bool(detail and detail.get("enforcement") == "active"),
        # Every way the ruleset carrying the factory's name is not the ruleset the factory writes
        # (#185). Empty when there is no such ruleset: what is missing is then the ruleset itself.
        "rulesetDiffers": differences(detail, ruleset_payload(branch, app)) if detail else [],
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
    differs = state["rulesetDiffers"]
    lines.append(_row(f"Ruleset on {state['branch']}",
                      OK if state["rulesetEnforced"] and not differs else (WRONG if state["ruleset"] else MISSING),
                      RULESET if state["rulesetEnforced"] and not differs else
                      (f"{RULESET} exists but {differs[0] if differs else 'is not active'}" if state["ruleset"] else
                       f"no ruleset named {RULESET}")))
    app = state["checksApp"]
    for context in REQUIRED_CHECKS:
        pin = state["requiredChecks"].get(context)
        lines.append(_row(f"Required check: {context}",
                          OK if pin is not None and pin == app else
                          (WRONG if context in state["requiredChecks"] else MISSING),
                          "" if pin is not None and pin == app else
                          ("the workflow may exist; it is not required" if context not in state["requiredChecks"]
                           else f"required, but not pinned to the {CHECKS_APP} app: a commit status under that "
                                f"name satisfies it, whoever posted it")))
    # Not a pass or a fail but a standing fact, reported where the rails are read: a verdict is a
    # commit status posted by a person's token, and `integration_id` pins an app, not a person, so
    # the verdict contexts cannot be pinned at all while they stay commit statuses (0029 §7, #186).
    lines.append(_row("Verdict gate", OK,
                      "recorded at the head SHA and unpinnable: an integrity check against mistakes and ordering, "
                      "not an authentication of who reviewed (0029 §7)"))
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

    def note(reason):
        # A ruleset difference and a missing required check are the same sentence read two ways --
        # once per row and once for the ruleset as a whole -- so a reason is said once.
        if reason not in found:
            found.append(reason)

    missing_files = [path for path, present in state["files"].items() if not present]
    if missing_files:
        note(f"the engine is missing {len(missing_files)} rail(s) ({', '.join(missing_files[:3])}...); "
             f"run `factory produce`")
    if state["missingLabels"]:
        note(f"the repository has no {', '.join(state['missingLabels'])} label, so the issues that need "
             f"them cannot be labelled or dispatched")
    if state["checksApp"] is None:
        note(f"the {CHECKS_APP} app's id could not be read from this host, so a required check cannot be pinned to "
             f"the app that posts it, and a commit status under its name would satisfy it")
    if state["ruleset"] is None:
        note(f"no active ruleset named {RULESET}: the branch has no rails, whatever files it holds")
        for context in REQUIRED_CHECKS:
            note(f"{context} is not a required check: a workflow that exists is not a workflow that is required")
        note("a pull request is not required on the default branch")
    else:
        # A ruleset that exists is judged by one comparison against what `--apply` would write, so
        # no row of it can pass while the field beside it is wrong (#185).
        for reason in state["rulesetDiffers"]:
            note(reason)
    if not state["mergeOnly"]:
        note("the repository still allows squash or rebase merging: a verdict is pinned to the head commit, and a "
             "squash merge manufactures a commit nobody reviewed")
    if not state["chain"]:
        note(f"{POLICY} configures no independent reviewer, so an issue that needs one can never merge")
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

    if state["checksApp"] is None:
        # Writing the ruleset without the pin would be the quiet half-measure #186 is about: the
        # checks would look required and would be satisfiable by anyone who can post a status.
        raise RailsError(f"the {CHECKS_APP} app's id could not be read from this host (`gh api apps/{CHECKS_APP}`), "
                         f"and a required check that is not pinned to the app that posts it is satisfied by a "
                         f"commit status anyone with write access can post; nothing was changed")
    payload = ruleset_payload(state["branch"], state["checksApp"])
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
    elif differences(existing, payload):
        done = subprocess.run([gh, "api", f"repos/{repo}/rulesets/{existing['id']}", "-X", "PUT", "--input", "-"],
                              input=json.dumps(payload), text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=120)
        if done.returncode != 0:
            raise RailsError(f"could not update the ruleset: {done.stderr.strip() or done.stdout.strip()}")
        print(f"updated ruleset {RULESET} (it is the factory's own; no other ruleset was read or written):", file=log)
        for reason in differences(existing, payload):
            print(f"  it was not what the factory writes: {reason}", file=log)
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
    """Whether the ruleset on GitHub is the one this version of the factory would write.

    An equal ruleset is left alone, which is what makes `--apply` idempotent.
    """
    return not differences(existing, payload)


def differences(existing, payload):
    """Every way the ruleset carrying the factory's name is not the ruleset the factory writes.

    Each item is a reason `--check` can print. The comparison is of what decides enforcement --
    the target, the enforcement, the conditions, the bypass actors, and every rule's type and the
    parameters the factory sets -- and not of the whole document, which carries ids, timestamps
    and links that say nothing about what is enforced.

    **What it used to skip is what it exists for now (#185).** It compared `enforcement`,
    `conditions.ref_name.include`, the bypass actors and the rule parameters, and ignored `target`
    and `conditions.ref_name.exclude`. So a ruleset named `rules-factory-agent-rails` that excluded
    `~DEFAULT_BRANCH`, or targeted tags, was reported as enforced and left alone by `--apply`: the
    default branch had no rails and the doctor said OK.

    **An unknown condition is a mismatch, not something to ignore.** A condition this factory does
    not model may narrow the ruleset in a way it cannot reason about -- which is the shape of the
    defect above, one field further on. `--apply` rewrites the ruleset it owns, so the cost of
    calling a narrowing the factory does not understand a mismatch is one rewrite; the cost of
    ignoring it is a green check over an ungoverned branch.
    """
    out = []
    if (existing.get("target") or "branch") != payload["target"]:
        out.append(f"it targets {existing.get('target') or 'branch'!r}, not {payload['target']!r}, so it governs "
                   f"nothing the rails are about")
    if existing.get("enforcement") != payload["enforcement"]:
        out.append(f"it is not active: its enforcement is {existing.get('enforcement')!r}, so the branch has no "
                   f"rails, whatever files it holds")

    conditions = existing.get("conditions") or {}
    unknown = sorted(set(conditions) - set(payload["conditions"]))
    if unknown:
        out.append(f"it carries {', '.join(unknown)} condition(s) the factory did not write, which may narrow it "
                   f"in a way the factory cannot reason about")
    reference = conditions.get("ref_name") or {}
    wanted_reference = payload["conditions"]["ref_name"]
    if (reference.get("include") or []) != wanted_reference["include"]:
        out.append(f"it applies to {', '.join(reference.get('include') or []) or 'no branch'}, not to "
                   f"{', '.join(wanted_reference['include'])}")
    if (reference.get("exclude") or []) != wanted_reference["exclude"]:
        out.append(f"it excludes {', '.join(reference.get('exclude') or [])}, and an exclusion the factory did not "
                   f"write takes the branch it names out of the rails while the ruleset still exists")
    if existing.get("bypass_actors"):
        out.append(f"{len(existing['bypass_actors'])} actor(s) may bypass the ruleset; a rail with an exemption "
                   f"for its author is a rail nobody else can rely on")

    wanted = {rule["type"]: rule.get("parameters") or {} for rule in payload["rules"]}
    found = {rule.get("type"): rule.get("parameters") or {} for rule in existing.get("rules") or []}
    for kind in sorted(set(found) - set(wanted)):
        out.append(f"it carries a {kind} rule the factory did not write")
    for kind in sorted(wanted):
        if kind not in found:
            if kind == "pull_request":
                out.append("a pull request is not required on the default branch")
            else:
                out.append(f"it has no {kind} rule")
            continue
        out.extend(_parameters(kind, wanted[kind], found[kind]))
    return out


def _parameters(kind, wanted, found):
    """How one rule's parameters differ from the ones the factory sets.

    Only the parameters the factory writes are compared: GitHub returns others, and a field this
    factory never set is not a difference between two factory rulesets. The checks are compared as
    (context, app) pairs, because a required check that is not pinned to the app that posts it is
    satisfied by any account with status-write access (#186).
    """
    out = []
    for key in sorted(wanted):
        value, mine = found.get(key), wanted[key]
        if key == "required_status_checks":
            pinned = {check.get("context"): check.get("integration_id") for check in value or []}
            for check in mine:
                context, app = check["context"], check.get("integration_id")
                if context not in pinned:
                    out.append(f"{context} is not a required check: a workflow that exists is not a workflow that "
                               f"is required")
                elif pinned[context] != app:
                    out.append(f"{context} is required but not pinned to the {CHECKS_APP} app (integration "
                               f"{pinned[context]!r}, not {app!r}): a commit status under that name satisfies it, "
                               f"whoever posted it")
            for context in sorted(set(pinned) - {check["context"] for check in mine}):
                out.append(f"{context} is a required check the factory did not write")
        elif key == "allowed_merge_methods" and value != mine:
            out.append("the ruleset allows a merge method other than a merge commit; a verdict is pinned to the "
                       "head commit, and a squash merge manufactures a commit nobody reviewed")
        elif value != mine:
            out.append(f"its {kind} rule sets {key} to {value!r}, not {mine!r}")
    return out


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
