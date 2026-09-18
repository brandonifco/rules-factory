"""The agent rails a produced engine carries (decision 0029), and the one reading of the
configuration they run on.

The rails are documents, hooks, scripts and workflows, recipes under `recipe/rails/` rather than
strings in a module; `rails_files` reads them, and `scaffold.managed_files` hands them to
ownership.py as managed files, so a hand edit in an engine is refused and never silently
overwritten. `.github/agent-policy.json` is the configuration they read, and is engine-owned: the
factory writes the default below once and never again.

The reading of that file lives here, beside the default, so what the rails demand of it cannot
drift from what the factory ships in it. `factory rails --check` (rails.py), `backlog.py`, the
engine's `scripts/engine-gate.py rails` and `tools/agent-doctor.py` all judge it through this
module and none of them states the rule itself.
"""
import json
import os

import overlay as overlay_step
import pins

# The agent rails whose recipe is a file rather than a string (decision 0029): published path ->
# template under recipe/rails/. They are documents and a hook, long enough that inlining them here
# would bury the generator, and worth reading as what they are. Read lazily, inside
# scaffold.managed_files: this module is vendored into every engine as scripts/factory/agentrails.py,
# where recipe/ does not exist and the engine's gate calls `generate.generated` alone.
RAILS = {
    "AGENTS.md": "AGENTS.md",
    "CLAUDE.md": "CLAUDE.md",
    "docs/agent-team.md": "agent-team.md",
    ".claude/agents/engine-dev.md": "agents/engine-dev.md",
    ".claude/agents/repo-steward.md": "agents/repo-steward.md",
    ".claude/agents/rules-conformance.md": "agents/rules-conformance.md",
    ".claude/hooks/primary-checkout-guard.py": "hooks/primary-checkout-guard.py",
    ".claude/settings.json": "settings.json",
    "tools/dispatch-agent.sh": "tools/dispatch-agent.sh",
    "tools/new-issue.sh": "tools/new-issue.sh",
    "tools/entry-packet.py": "tools/entry-packet.py",
    "tools/re-produce.sh": "tools/re-produce.sh",
    "tools/review-packet.py": "tools/review-packet.py",
    "tools/pr-policy.py": "tools/pr-policy.py",
    "tools/record-verdict.py": "tools/record-verdict.py",
    "tools/conformance-gate.py": "tools/conformance-gate.py",
    "tools/requeue-gate.py": "tools/requeue-gate.py",
    ".github/pull_request_template.md": "pull_request_template.md",
    ".github/workflows/pr-policy.yml": "workflows/pr-policy.yml",
    ".github/workflows/conformance-gate.yml": "workflows/conformance-gate.yml",
    ".github/workflows/verdict-requeue.yml": "workflows/verdict-requeue.yml",
    "tools/agent-doctor.py": "tools/agent-doctor.py",
    # Named `editorconfig` in the recipe: a dotfile there would be invisible in a listing of the
    # rails, and the published path is what matters.
    ".editorconfig": "editorconfig",
}


# The rails an operator runs. `produce` writes with the default mode, so a script invoked by path
# would not run; the hook is invoked through `python3` by .claude/settings.json instead and needs
# no bit, and tools/requeue-gate.py is the same case -- .github/workflows/verdict-requeue.yml runs
# it through `python3`, and nobody runs it by hand. The mode is not part of a recipe's bytes, so it
# plays no part in hand-edit detection.
EXECUTABLE = frozenset({"tools/dispatch-agent.sh", "tools/new-issue.sh", "tools/entry-packet.py",
                        "tools/review-packet.py", "tools/pr-policy.py", "tools/record-verdict.py",
                        "tools/conformance-gate.py", "tools/agent-doctor.py", "tools/re-produce.sh"})


RAILS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recipe", "rails")


def rails_files():
    """The rails recipes: published path -> text, read from recipe/rails/.

    Each is read in binary and decoded, so the bytes written are the bytes on disk: a recipe
    version means one fixed sequence of bytes (ownership.py), and a newline translated on the way
    through would silently make an engine's copy a hand edit.
    """
    out = {}
    for relative, template in RAILS.items():
        with open(os.path.join(RAILS_DIR, *template.split("/")), "rb") as handle:
            out[relative] = handle.read().decode("utf-8")
    return out


AGENT_POLICY = ".github/agent-policy.json"


# The five labels the issue state machine is written in: three states and two risks, in the order
# `agent_policy` writes them.
LABEL_KEYS = ("ready", "blocked", "needsDecision", "normalRisk", "independentRisk")


class PolicyError(ValueError):
    """An `.github/agent-policy.json` the rails cannot act on. Callers raise their own error type."""


def policy_labels(document, where=AGENT_POLICY):
    """The five label strings, or a refusal. The one place the label vocabulary is judged (#188).

    Two keys may not share a string. `backlog.label_plan` computes a state set and a risk set from
    these five, and two keys that collapse into one label make those sets lie: with `ready` equal
    to `blocked` an issue is in two states at once and neither can be removed, and with a state
    label equal to a risk label, moving the state strips the risk. Either way the issues reach
    GitHub undispatchable, and `rails --check` said OK, because each key was non-empty.

    It lives here because this module holds the default that file is written from (`agent_policy`
    below), so what the rails demand of it cannot drift from what the factory ships in it;
    `rails.py` and `backlog.py` both read it through here and neither states the rule itself.
    """
    labels = document.get("labels") or {}
    missing = [key for key in LABEL_KEYS if not labels.get(key)]
    if missing:
        raise PolicyError(f"{where} names no {', '.join(sorted(missing))} label; the rails read every label "
                          f"from it, so a missing one would silently go unapplied")
    taken = {}
    for key in LABEL_KEYS:
        taken.setdefault(labels[key], []).append(key)
    shared = sorted((name, keys) for name, keys in taken.items() if len(keys) > 1)
    if shared:
        collisions = "; ".join(f"{' and '.join(keys)} are both {name!r}" for name, keys in shared)
        raise PolicyError(f"{where} gives one label to more than one key ({collisions}); the five are a state "
                          f"machine and a risk axis, so an issue would be in two states at once, or lose its "
                          f"risk label when its state changed")
    return {key: labels[key] for key in LABEL_KEYS}


def review_problems(document, where=AGENT_POLICY):
    """Every way the policy's `review` section cannot be recorded under, as printable reasons (#211).

    A semantic context, a non-empty independent chain, and an `id` and a `context` on every link.
    `tools/record-verdict.py` records a verdict under the link's context, so a link with an `id`
    and no `context` is a reviewer that cannot record anything -- and a reader finds that out at the
    moment they try to, which is the worst time.

    There is one statement of this rule for the three things that judge the file. `factory rails
    --check` imports it from here, and the engine's `scripts/engine-gate.py rails` and
    `tools/agent-doctor.py` import the copy `produce` vendors under `scripts/factory/`. Before it,
    the gate rejected a link with no context and `rails --check` called the same file OK.
    """
    review = document.get("review") if isinstance(document, dict) else None
    review = review if isinstance(review, dict) else {}
    out = []
    if not review.get("semanticContext"):
        out.append(f"{where} sets no review.semanticContext, so no semantic verdict can be recorded")
    chain = review.get("independentFallback") or []
    if not isinstance(chain, list) or not chain:
        out.append(f"{where} configures no independent reviewer, so an issue classified as needing one can never "
                   f"be merged")
        return out
    for link in chain:
        if not (isinstance(link, dict) and link.get("id") and link.get("context")):
            out.append(f"{where}: every review.independentFallback link needs an id and a context (got {link!r}). "
                       f"A verdict recorded under a generic context cannot be told from a same-family fallback.")
    return out


def policy_problems(document, where=AGENT_POLICY):
    """Every way the policy is not one the rails can act on: its schema version, its five labels
    (`policy_labels`) and its review section (`review_problems`). Empty when the rails can read it."""
    if not isinstance(document, dict):
        return [f"{where} is not a JSON object; the rails cannot read their own configuration"]
    out = []
    if document.get("schemaVersion") != 1:
        out.append(f"{where} has schemaVersion {document.get('schemaVersion')!r}; the rails read version 1")
    try:
        policy_labels(document, where)
    except PolicyError as error:
        out.append(str(error))
    return out + review_problems(document, where)


def agent_policy():
    """The engine's rails configuration (decision 0029): every choice the rails read.

    Engine-owned, so the factory writes it once and never again: a consumer changes the review
    chain, the label vocabulary or the worktree variables by editing this file, and no emitted
    script names a provider. The chain below is the default the factory ships, which is why it is
    here and not in a script.
    """
    return json.dumps({
        "schemaVersion": 1,
        "labels": {
            "ready": "state:ready",
            "blocked": "state:blocked",
            "needsDecision": "state:needs-decision",
            "normalRisk": "risk:normal",
            "independentRisk": "risk:independent-review",
        },
        "review": {
            "semanticContext": "rules-verdict/semantic",
            "semanticPaths": ["src/**", "tests/**", f"{overlay_step.DIRECTORY}/**", pins.PACKAGES_PROPS,
                              "corpus/**", "docs/decisions/**"],
            "independentFallback": [
                {"id": "codex", "context": "rules-verdict/codex"},
                {"id": "gemini", "context": "rules-verdict/gemini"},
                {"id": "in-house-independent", "context": "rules-verdict/in-house-independent"},
            ],
        },
        "worktrees": {
            "rootEnvironmentVariable": "RULES_ENGINE_WORKTREE_ROOT",
            "primaryMutationEscapeHatch": "RULES_ENGINE_ALLOW_PRIMARY_MUTATION",
        },
    }, indent=2) + "\n"
