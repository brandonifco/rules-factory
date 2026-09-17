#!/usr/bin/env python3
"""Are this engine's rails actually active, or do they only exist?

    tools/agent-doctor.py [--local]

Emitted by rules-factory as a managed file (decision 0029).

**The failure this exists for is "I thought the rails were active".** Every rail in this repository
is a file, and a file is easy to have and easy to believe in. A hook that is present but not
wired into any settings, a workflow that runs but is not required, a label the scripts read and
the repository does not have, a ruleset that was created and then set to "evaluate" rather than
"active" -- each of those looks exactly like a working rail from inside the repository, and stops
anything only when somebody checks.

So this asks the questions whose answers are not visible in a file listing, and prints one row per
answer. It changes nothing, ever.

  * **Local** rows come from this checkout: the rails are byte for byte what the factory's recipe
    wrote, the hook is wired to the tools it guards, the policy is one the rails can record verdicts
    under, and the gate runs the rails check. The rail bytes and the policy are judged by the
    factory's own rules, from the copy `produce` vendored under `scripts/factory/`, so this and
    `factory rails --check` cannot disagree about the same file.
  * **Remote** rows come from GitHub: the labels, the ruleset, and whether the three checks are
    required rather than merely present. `--local` skips them, for an offline machine; the output
    then says the remote half was not examined, because a green report that skipped the half that
    matters is the failure this repository has twice found in its own tools.

The remote half asks the same questions `factory rails --check` asks, from inside the engine and
without the factory. Where the answers would differ, the factory's is authoritative: it is the
thing that writes them.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`) for the remote rows.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

# The rail bytes and the policy are judged by the engine's vendored scripts/factory modules, and an
# imported module leaves its bytecode behind: scripts/factory/__pycache__/, a path no ownership row
# covers, so the checkout that ran this goes dirty and tools/dispatch-agent.sh refuses to open a
# worktree for the next issue. The loader reads this flag when the import happens, so it belongs
# here and not beside the import it disarms.
sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
RULESET = "rules-factory-agent-rails"
# `verdict-requeue` is deliberately absent: it runs on the default branch's commit, where a
# required check governs nothing.
REQUIRED_CHECKS = ("validate", "pr-policy", "conformance-gate")
GUARDED_TOOLS = "Bash|Edit|Write|NotebookEdit"
OK, MISSING, WRONG, UNKNOWN = "OK", "MISSING", "WRONG", "NOT EXAMINED"


def row(name, state, note=""):
    dots = "." * max(3, 34 - len(name))
    return f"{name} {dots} {state}" + (f"  -- {note}" if note else "")


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    try:
        done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        return None, str(error)
    if done.returncode != 0:
        return None, (done.stderr.strip() or done.stdout.strip())
    try:
        return json.loads(done.stdout or "null"), None
    except ValueError as error:
        return None, str(error)


def factory():
    """The factory's generator as `produce` vendored it into this engine, or (None, why)."""
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        import generate  # noqa: E402  (the factory's generator and its ownership table, vendored by produce)
    except ImportError as error:
        return None, f"scripts/factory/generate.py cannot be imported ({error}); `factory produce` writes it"
    return generate, None


def local_rows():
    rows, problems = [], []
    generate, error = factory()

    # A file of the right name is not the rail the factory wrote: a truncated gate reads exactly
    # like a working one in a listing. So the bytes are compared with every version of the recipe,
    # the same judgement `produce` refuses a hand edit by.
    if generate is None:
        rows.append(row("Rail files", UNKNOWN, error))
        problems.append(f"the rail files were not examined: {error}")
    else:
        ownership = generate.ownership
        states = ownership.managed_states(str(ROOT), generate.RAILS)
        wrong = [(path, kind) for path, (kind, _) in sorted(states.items())
                 if kind not in (ownership.CURRENT, ownership.ADOPTED)]
        adopted = [path for path, (kind, _) in sorted(states.items()) if kind == ownership.ADOPTED]
        if not wrong:
            rows.append(row("Rail files", OK, "byte for byte as the recipe writes them"
                                              + (f"; adopted by this engine: {', '.join(adopted)}" if adopted else "")))
        else:
            absent_only = all(kind == ownership.ABSENT for _, kind in wrong)
            rows.append(row("Rail files", MISSING if absent_only else WRONG,
                            f"{len(wrong)} not as the recipe writes them: "
                            + ", ".join(f"{path} ({kind})" for path, kind in wrong[:3])))
        for kind, advice in ((ownership.ABSENT, "`factory produce` writes them"),
                             (ownership.EARLIER, "`factory produce` migrates them to the current recipe"),
                             (ownership.EDITED, "`factory produce` refuses them until `--adopt` or `--reset` "
                                                "settles each")):
            paths = [path for path, found in wrong if found == kind]
            if paths:
                problems.append(f"{len(paths)} rail(s) in this engine are {kind} ({', '.join(paths[:3])}"
                                f"{', ...' if len(paths) > 3 else ''}); {advice}")

    # A guard nothing invokes is a guard that stops nothing, and reads exactly like one that works.
    settings_path = ROOT / ".claude" / "settings.json"
    wired = False
    if settings_path.is_file():
        try:
            hooks = json.loads(settings_path.read_text(encoding="utf-8")).get("hooks") or {}
            for entry in hooks.get("PreToolUse") or []:
                command = " ".join(hook.get("command", "") for hook in entry.get("hooks") or [])
                if "primary-checkout-guard.py" in command and entry.get("matcher") == GUARDED_TOOLS:
                    wired = True
        except ValueError:
            pass
    rows.append(row("Guard wired to the tools", OK if wired else WRONG,
                    "" if wired else f"the hook exists, but no PreToolUse entry runs it for {GUARDED_TOOLS}"))
    if not wired:
        problems.append("the primary-checkout guard is not wired into .claude/settings.json, so nothing invokes it")

    chain = []
    policy_path = ROOT / POLICY
    if policy_path.is_file():
        try:
            document = json.loads(policy_path.read_text(encoding="utf-8"))
            review = (document.get("review") if isinstance(document, dict) else None) or {}
            chain = [str(link.get("id")) if isinstance(link, dict) else repr(link)
                     for link in review.get("independentFallback") or []]
            # The factory's rule, not a second copy of it: `factory rails --check` and
            # scripts/engine-gate.py rails judge the policy by the same function.
            if generate is None:
                rows.append(row("Policy", UNKNOWN, error))
                problems.append(f"{POLICY} was not judged: {error}")
            else:
                found = generate.policy_problems(document, POLICY)
                chain_found = generate.review_problems(document, POLICY)
                rows.append(row("Policy", OK if not found else WRONG,
                                f"schemaVersion {document.get('schemaVersion')}" if not found else found[0]))
                rows.append(row("Review chain", OK if not chain_found else WRONG,
                                f"{review.get('semanticContext')}, then {' -> '.join(chain) or 'nothing'}"))
                problems.extend(found)
        except ValueError as error:
            rows.append(row("Policy", WRONG, f"not JSON: {error}"))
            problems.append(f"{POLICY} does not parse, and every rail reads it")
    else:
        rows.append(row("Policy", MISSING, POLICY))
        problems.append(f"{POLICY} is missing, and every rail reads its labels, contexts and chain from it")

    gate = ROOT / "scripts" / "validate.sh"
    runs_rails = gate.is_file() and "rails" in gate.read_text(encoding="utf-8")
    rows.append(row("Gate checks the rails", OK if runs_rails else WRONG,
                    "" if runs_rails else "scripts/validate.sh does not run `engine-gate.py rails`"))
    if not runs_rails:
        problems.append("the gate does not check the rails, so a reviewer charter that can write would pass it")
    # The gate's workflow is the gate's recipe rather than a rail, so the bytes above do not cover it;
    # without it the `validate` check the ruleset requires has nothing to post it.
    if not (ROOT / ".github" / "workflows" / "validate.yml").is_file():
        rows.append(row("Gate workflow", MISSING, ".github/workflows/validate.yml"))
        problems.append(".github/workflows/validate.yml is missing, so nothing posts the required validate check")
    return rows, problems


def remote_rows(repo):
    rows, problems = [], []
    repository, error = gh("api", f"repos/{repo}")
    if repository is None:
        rows.append(row("GitHub", UNKNOWN, f"cannot read {repo}: {error}"))
        problems.append(f"the remote half was not examined ({error}); a report that skipped it proves nothing "
                        f"about what GitHub enforces")
        return rows, problems

    labels_document, _ = gh("api", f"repos/{repo}/labels", "--paginate")
    have = {item["name"] for item in labels_document or []}
    policy_path = ROOT / POLICY
    wanted = []
    if policy_path.is_file():
        try:
            wanted = sorted((json.loads(policy_path.read_text(encoding="utf-8")).get("labels") or {}).values())
        except ValueError:
            wanted = []
    absent = [name for name in wanted if name not in have]
    rows.append(row("Labels", OK if wanted and not absent else (MISSING if wanted else UNKNOWN),
                    "" if not absent else ", ".join(absent)))
    if absent:
        problems.append(f"the repository has no {', '.join(absent)} label, so an issue that needs one cannot be "
                        f"labelled or dispatched")

    rulesets, _ = gh("api", f"repos/{repo}/rulesets")
    ours = next((item for item in rulesets or [] if item.get("name") == RULESET), None)
    detail, _ = gh("api", f"repos/{repo}/rulesets/{ours['id']}") if ours else (None, None)
    active = bool(detail and detail.get("enforcement") == "active")
    rows.append(row(f"Ruleset on {repository.get('default_branch')}", OK if active else
                    (WRONG if detail else MISSING),
                    RULESET if active else (f"{RULESET} is {detail.get('enforcement')}" if detail else
                                            f"no ruleset named {RULESET}")))
    if not active:
        problems.append(f"no active {RULESET}: the default branch has no rails, whatever files this engine holds")

    required = set()
    for rule in (detail or {}).get("rules") or []:
        if rule.get("type") == "required_status_checks":
            required = {check.get("context")
                        for check in (rule.get("parameters") or {}).get("required_status_checks") or []}
    for context in REQUIRED_CHECKS:
        present = context in required
        rows.append(row(f"Required check: {context}", OK if present else MISSING,
                        "" if present else "the workflow may run; it is not required"))
        if not present:
            problems.append(f"{context} is not a required check: a workflow that exists is not one that is required")

    merge_only = (repository.get("allow_merge_commit") is True
                  and repository.get("allow_squash_merge") is False
                  and repository.get("allow_rebase_merge") is False)
    rows.append(row("Merge commits only", OK if merge_only else WRONG,
                    "" if merge_only else "squash or rebase merging is on, and a squash merge makes a commit no "
                                          "reviewer read"))
    if not merge_only:
        problems.append("squash or rebase merging is on; a verdict is pinned to the head commit, which a squash "
                        "merge discards")
    return rows, problems


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agent-doctor.py", description=__doc__.split("\n")[0])
    parser.add_argument("--local", action="store_true", help="check this checkout only, and say GitHub was not examined")
    parser.add_argument("--repo", help="owner/name (default: whatever `gh` says this checkout's remote is)")
    args = parser.parse_args(argv)

    rows, problems = local_rows()
    if args.local:
        rows.append(row("GitHub", UNKNOWN, "--local: the labels, the ruleset and the required checks were not read"))
        problems.append("the remote half was not examined (--local), so this says nothing about what GitHub "
                        "enforces")
    else:
        repo = args.repo
        if not repo:
            document, error = gh("repo", "view", "--json", "nameWithOwner")
            repo = (document or {}).get("nameWithOwner")
            if not repo:
                rows.append(row("GitHub", UNKNOWN, f"cannot tell which repository this is: {error}"))
                problems.append("the remote half was not examined; pass --repo owner/name")
        if repo:
            remote, remote_problems = remote_rows(repo)
            rows.extend(remote)
            problems.extend(remote_problems)

    for line in rows:
        print(line)
    if problems:
        print()
        for problem in problems:
            print(f"  X  {problem}")
        print("\nThe factory puts the remote half in place: "
              "`factory rails --repo <owner/name> --dir <this engine> --apply`.")
        return 1
    print("\nThe rails are active, not merely present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
