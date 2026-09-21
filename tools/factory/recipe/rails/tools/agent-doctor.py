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
    required, pinned to the app that posts them, and set on this repository rather than above it.
    `--local` skips them, for an offline machine; the output then says the remote half was not
    examined, because a green report that skipped the half that matters is the failure this
    repository has twice found in its own tools.
  * One row spans both: **what merged work left behind**. `tools/dispatch-agent.sh --cleanup` has
    always existed and nothing ran it, so a worktree and a branch from a pull request that merged
    days ago sit there, and the rails look exactly as active as they would if nothing had been
    left. It reads the local worktrees and branches and asks GitHub which pull requests merged, so
    with `--local`, or with `gh` refusing, it is NOT CHECKED -- never OK.

The remote half asks the same questions `factory rails --check` asks, from inside the engine and
without the factory. Where the answers would differ, the factory's is authoritative: it is the
thing that writes them -- so the questions are not asked twice in two places. Which ruleset is the
factory's, and what a required check has to be pinned to, are read from the same vendored
`scripts/factory/` the rail bytes and the policy are judged by. Before that they were restated
here, and this report said a check was OK while `factory rails --check` said WRONG about the same
ruleset at the same moment (#231).

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
GUARDED_TOOLS = "Bash|Edit|Write|NotebookEdit"
OK, MISSING, WRONG, UNKNOWN = "OK", "MISSING", "WRONG", "NOT EXAMINED"
# The leftovers row's own third state. `NOT EXAMINED` is what this report says about a half it
# chose not to look at; this is a question it asked and could not get an answer to, and the two
# read differently to somebody deciding whether the report is worth anything.
NOT_CHECKED = "NOT CHECKED"
LEFTOVERS = "Leftovers from merged work"
SWEEP = "tools/dispatch-agent.sh --sweep"
# The newest this many merged pull requests, the same cap the sweep reads them under: a leftover is
# recent by definition, and a cap that misses an older one under-reports rather than over-reports.
MERGED_LIMIT = "500"
# The ruleset's name and the three checks it requires are the factory's, and are read from the
# vendored `scripts/factory/` rather than written down again here. `verdict-requeue` is
# deliberately not among them: it runs on the default branch's commit, where a required check
# governs nothing.


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


def git(*args):
    """`git` in this checkout, as (stdout, None) or (None, why)."""
    try:
        done = subprocess.run(["git", "-C", str(ROOT), *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        return None, str(error)
    if done.returncode != 0:
        return None, (done.stderr.strip() or done.stdout.strip() or f"git {args[0]} failed")
    return done.stdout, None


def merged_heads():
    """{head branch: {head commits}} for this repository's merged pull requests, or (None, why)."""
    rows, why = gh("pr", "list", "--state", "merged", "--limit", MERGED_LIMIT,
                   "--json", "headRefName,headRefOid")
    if why:
        return None, why
    heads = {}
    for item in rows or []:
        heads.setdefault(item.get("headRefName"), set()).add(item.get("headRefOid"))
    return heads, None


def worktrees(listing):
    """git's worktree porcelain as dicts, the primary checkout first."""
    found, current = [], {}
    for line in (listing or "").splitlines() + [""]:
        if not line:
            if current:
                found.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value if value else True
    return found


def leftover_rows(local):
    """What merged work left behind: a worktree or a branch whose pull request merged at EXACTLY
    its tip, which is what `tools/dispatch-agent.sh --sweep` removes.

    The rule is rules-factory's own `tools/repo-hygiene.py`, restated because an engine does not
    receive that file. It is deliberately the strict one: a worktree dispatched and not yet
    committed in sits at `main`'s tip, so "its commits are in main" reports every agent who has
    not started as finished, and a report that cries wolf is a report nobody reads.

    This reads. It removes nothing, as nothing in this file does -- and it says NOT CHECKED rather
    than OK wherever it could not ask, because a leftover nobody looked for and a repository with
    none look identical from here.
    """
    if local:
        return ([row(LEFTOVERS, NOT_CHECKED, "--local: merged pull requests were not read, so a worktree or "
                                             "branch left behind by merged work is not reported")],
                [f"what merged work left behind was not examined (--local); `{SWEEP}` is what removes it"])
    heads, why = merged_heads()
    if heads is None:
        return ([row(LEFTOVERS, NOT_CHECKED, f"merged pull requests could not be read ({why})")],
                [f"what merged work left behind was not examined ({why}); a worktree and a branch from a pull "
                 f"request that merged days ago look exactly like a clean repository from here"])
    listing, why = git("worktree", "list", "--porcelain")
    refs, ref_why = git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads")
    if listing is None or refs is None:
        unreadable = why or ref_why
        return ([row(LEFTOVERS, NOT_CHECKED, f"this checkout could not be read ({unreadable})")],
                [f"what merged work left behind was not examined ({unreadable})"])

    trees = worktrees(listing)
    found = []
    for tree in trees[1:]:
        branch = (tree.get("branch") or "").removeprefix("refs/heads/")
        if branch and tree.get("HEAD") in heads.get(branch, set()):
            found.append(f"{tree['worktree']} (worktree)")
    # A branch a worktree has checked out goes with that worktree, and the primary checkout's own
    # branch is in this set too, which is how the default branch is spared without being named.
    checked_out = {(tree.get("branch") or "").removeprefix("refs/heads/") for tree in trees}
    for line in refs.splitlines():
        name, _, sha = line.partition(" ")
        if name not in checked_out and sha in heads.get(name, set()):
            found.append(f"{name} (branch)")

    if not found:
        return [row(LEFTOVERS, OK, "no worktree or branch is left over from merged work")], []
    shown = ", ".join(found[:3]) + (", ..." if len(found) > 3 else "")
    return ([row(LEFTOVERS, WRONG, f"{len(found)} left over: {shown}")],
            [f"{len(found)} worktree(s) or branch(es) are left over from work whose pull request merged; "
             f"`{SWEEP}` removes exactly those, and every dispatch runs it"])


def pages(generate, *args):
    """An array endpoint of GitHub's, read as the pages it actually comes in: (items, None), or
    (None, why).

    `gh api --paginate` prints each page as its own JSON array, so two pages are `[...][...]` --
    not one document. Read as one, a repository with more labels than a page holds reported none
    of them (#237). `--slurp` prints the pages as one array of arrays, and the factory's own
    `flatten_pages` puts them back together for this and for `factory rails --check` alike.
    """
    document, why = gh(*args, *generate.PAGES)
    if why:
        return None, why
    return generate.flatten_pages(document if document is not None else [])


def factory():
    """The factory's generator as `produce` vendored it into this engine, or (None, why)."""
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        import generate  # noqa: E402  (the factory's generator and its ownership table, vendored by produce)
    except ImportError as error:
        return None, f"scripts/factory/generate.py cannot be imported ({error}); `factory produce` writes it"
    return generate, None


def local_rows(generate, error):
    rows, problems = [], []

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


def remote_rows(repo, generate, unavailable):
    rows, problems = [], []
    if generate is None:
        # What GitHub enforces is judged by the factory's rules, from the copy `produce` vendored
        # here, so that this and `factory rails --check` cannot disagree about the same ruleset.
        # Without them there is no second reading to fall back on: there is the reading that is
        # already in this repository twice, and saying so.
        rows.append(row("GitHub", UNKNOWN, unavailable))
        problems.append(f"the remote half was not examined: {unavailable}. The ruleset and the pins are judged by "
                        f"the factory's own rules, and they could not be read")
        return rows, problems

    repository, error = gh("api", f"repos/{repo}")
    if repository is None:
        rows.append(row("GitHub", UNKNOWN, f"cannot read {repo}: {error}"))
        problems.append(f"the remote half was not examined ({error}); a report that skipped it proves nothing "
                        f"about what GitHub enforces")
        return rows, problems

    labels_document, _ = pages(generate, "api", f"repos/{repo}/labels")
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

    # Every ruleset that can govern the branch, an organization's included -- `includes_parents`
    # is GitHub's default and is asked for here so the intent is on the page rather than in the
    # API's defaults. The factory's ruleset is the one at this repository's own level: an
    # organization ruleset carrying its name is not the factory's, `factory rails --apply` cannot
    # write it, and reading it as the factory's reports rails this repository does not have.
    ruleset = generate.RULESET
    rulesets, _ = pages(generate, "api", f"repos/{repo}/rulesets?includes_parents=true")
    ours, shadows = generate.factory_ruleset(rulesets or [])
    detail, _ = gh("api", f"repos/{repo}/rulesets/{ours['id']}") if ours else (None, None)
    active = bool(detail and detail.get("enforcement") == "active")
    rows.append(row(f"Ruleset on {repository.get('default_branch')}", OK if active else
                    (WRONG if detail else MISSING),
                    ruleset if active else (f"{ruleset} is {detail.get('enforcement')}" if detail else
                                            f"no ruleset named {ruleset} at this repository's own level")))
    if not active:
        problems.append(f"no active {ruleset} of this repository's own: the default branch has no rails, whatever "
                        f"files this engine holds")
    for shadow in shadows:
        problems.append(f"{generate.ruleset_origin(shadow)} carries the factory's ruleset name above this "
                        f"repository; it is not the factory's, `factory rails --apply` cannot write it, and the "
                        f"factory's own must be at the repository's level")

    # A required check is a context name plus the app that may post it. A name on its own is
    # satisfied by a commit status anyone with write access can post, so the id of the app the
    # three workflows run as is read from the host and each pin is compared with it (#186, #231).
    app_document, app_error = gh("api", f"apps/{generate.CHECKS_APP}")
    app = (app_document or {}).get("id")
    pins = generate.required_check_pins(detail)
    for context in generate.REQUIRED_CHECKS:
        state, note = generate.required_check_state(pins, context, app if isinstance(app, int) else None)
        rows.append(row(f"Required check: {context}", state, note))
        if state == generate.MISSING:
            problems.append(f"{context} is not a required check: a workflow that exists is not one that is required")
        elif state == generate.WRONG:
            problems.append(f"{context} is required but {note}")
        elif state == generate.NOT_VERIFIED:
            problems.append(f"{context} is required, but {note} (`gh api apps/{generate.CHECKS_APP}`: {app_error})")

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

    # One import of the vendored factory for both halves: the rail bytes, the policy, and what the
    # rails on GitHub are judged by all come from it.
    generate, unavailable = factory()
    rows, problems = local_rows(generate, unavailable)
    # Neither half: it reads this checkout and asks GitHub what merged. It is here, between them,
    # because it needs both, and it needs no vendored factory to answer.
    leftovers, leftover_problems = leftover_rows(args.local)
    rows.extend(leftovers)
    problems.extend(leftover_problems)
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
            remote, remote_problems = remote_rows(repo, generate, unavailable)
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
