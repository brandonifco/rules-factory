#!/usr/bin/env python3
"""Agent lifecycle guard: a completed subagent is replaced, never resumed (policy version 1).

POLICY
  1. One agent, one attempt (AGENTS.md section 4). A subagent that has returned its final result
     is finished. A message to it is refused, and the orchestrator dispatches a fresh agent with a
     concise brief assembled from committed state (`tools/repair-packet.py <pr> --finding ...` in
     an engine; `handoff` below anywhere). A message to an agent that is still running is a
     legitimate continuation of its assignment and goes through.
  2. Inside one assignment a subagent has a context budget. At CHECKPOINT_TOKENS it is told once
     to commit, keep to its assignment, and return a handoff brief if the remaining work is
     separable. At HARD_TOKENS it may only commit and return: every tool is refused except a git
     command and this file's `handoff`.
  3. A handoff is a brief from committed repository state, never a transcript. `handoff` refuses a
     worktree with uncommitted work, because that work would not survive the handoff.

WHY THESE NUMBERS (measurement, rules-factory issue #676; Claude Code transcripts under
~/.claude/projects, rules ecosystem projects, 2026-10-15): 502 subagents, 96 of them resumed after
their final result, 169 times; 29.2% of every token they processed (2.27B of 7.77B) was spent in
post-resume turns and 20.8% (1.61B) was a resumed agent re-reading the context of its earlier
assignment. First-assignment peak context: p50 157k, p75 211k, p90 284k, p95 348k tokens.
CHECKPOINT_TOKENS is the p75 (rounded down) and HARD_TOKENS the p95 (rounded up). `measure`
recomputes all of this from the same record, so the claim can be checked rather than believed.

THE BOUNDARY, VERIFIED IN CLAUDE CODE 2.1.287
  * Every hook gets session_id, transcript_path, cwd, permission_mode, agent_type; `agent_id`
    only when the hook fires inside a subagent.
  * PostToolUse of the Agent tool carries the new agent's `agentId` (and `tool_input.name`);
    SubagentStop carries `agent_id` when a subagent returns its final result.
  * SendMessage's target `to` is resolved by the runtime to a RUNNING task ("Message queued for
    delivery ... at its next tool round") or to a stopped or evicted one, which it RESUMES
    ("Resuming agent X", `resumedAgentId`). PreToolUse sees the target before that resolution.
  * A subagent's transcript is <transcript_path minus .jsonl>/subagents/agent-<agent_id>.jsonl;
    each assistant line has message.usage, and the context of a turn is input_tokens +
    cache_read_input_tokens + cache_creation_input_tokens.

WHAT IT ENFORCES
  * PreToolUse SendMessage to a target the session's ledger shows as completed: denied. To an
    id-shaped target ("a" + 16 hex) the ledger never saw launched: denied, because this cannot
    show it is running (fail closed). To a launched, not completed agent: allowed. To "main":
    allowed.
  * PostToolUse SendMessage whose result says the runtime resumed an agent: recorded as a
    violation, and the model is told to stop that agent and dispatch a fresh one. Detection after
    the fact, for the case the PreToolUse check could not see.
  * Context budget, in subagents only (see POLICY 2).

WHAT IT CANNOT SEE
  * A name target the ledger does not know (a teammate, another session, an agent launched before
    this guard was wired) is allowed; only the PostToolUse backstop catches a resume through it,
    after it has happened.
  * Hooks the user disables (`disableAllHooks`), user-level settings, the main session's own
    context, and any harness other than Claude Code: another harness's calls that resume a finished
    agent or send it input are unverified here and covered by nothing in this file.
  * The context budget reads the subagent's transcript tail. A transcript that is missing,
    unreadable, or in a layout this file does not recognise gives NO budget verdict: the guard
    cannot tell, so it neither warns nor stops. It never crashes the hook over it.
  * A hard-bound Bash command is judged by its tokens, not run in a shell: this is accident
    prevention for an agent that has been told to stop, not security.
  * An internal error is reported on stderr and lets the call through. A guard that blocks every
    tool because of its own bug is worse than a missing one, and `check-settings`, the rail-bytes
    check and the tests are what notice a guard that is not what it should be.

THE LEDGER: one append-only JSONL file per session, in $RULES_AGENT_LEDGER_DIR, else
${XDG_STATE_HOME:-~/.local/state}/rules-agent-lifecycle/, named by the sanitised session_id.
It is never inside a repository: it is the machine's record of what happened in a session, not a
build input. Records: launched, stopped, checkpoint, denied, violation.

USAGE
  agent-lifecycle-guard.py                          hook mode: one JSON event on stdin
  agent-lifecycle-guard.py handoff [--base REF]     brief from committed state (default origin/main)
  agent-lifecycle-guard.py check-settings PATH      0 iff PATH wires this guard (REQUIRED_HOOKS)
  agent-lifecycle-guard.py measure [--projects-dir DIR] [--match REGEX] [--ledger-dir DIR]

Hook answers: a PreToolUse refusal is `permissionDecision: deny` on stdout, exit 0. A PostToolUse
correction is `decision: block`; a note is `additionalContext`. Malformed stdin is exit 2 with a
message on stderr: this guard cannot tell what it was asked, so it does not guess.

Standard library only; emitted to engines as `.claude/hooks/agent-lifecycle-guard.py`.
"""
from __future__ import annotations

import argparse
import bisect
import datetime
import json
import math
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

POLICY_VERSION = 1
GUARD_NAME = "agent-lifecycle-guard.py"

# The measured peaks of a first assignment (issue #676, 502 agents): p75 211k, p95 348k.
CHECKPOINT_TOKENS = 210_000
HARD_TOKENS = 350_000

AGENT_ID = re.compile(r"^a[0-9a-f]{16}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
AGENT_TOOLS = ("Agent", "Task")

# Where this guard must be wired, defined once: `check-settings` reports against it, and
# tools/agent-doctor.py runs `check-settings` rather than restating it. (event, scope, why);
# scope is a tool name the matcher must cover, ALL_TOOLS, or None (the event has no matcher).
ALL_TOOLS = "*"
REQUIRED_HOOKS = (
    ("PreToolUse", "SendMessage", "refuse a message to a completed agent"),
    ("PreToolUse", ALL_TOOLS, "enforce the context hard bound in every tool"),
    ("PostToolUse", ALL_TOOLS, "record launches, detect a resume, issue the checkpoint note"),
    ("SubagentStop", None, "record that an agent completed"),
)
# Tool names a matcher is probed with to decide whether it covers "all tools".
PROBE_TOOLS = ("Bash", "Read", "Edit", "Write", "Glob", "Grep", "Agent", "SendMessage",
               "NotebookEdit", "WebFetch", "TodoWrite", "mcp__server__tool")

TAIL_START = 256 * 1024
TAIL_MAX = 16 * 1024 * 1024
BRIEF_COMMITS = 40
BRIEF_FILES = 80


# --------------------------------------------------------------------------- the ledger


def ledger_dir() -> Path:
    override = os.environ.get("RULES_AGENT_LEDGER_DIR")
    if override:
        return Path(override)
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return Path(state) / "rules-agent-lifecycle"


def ledger_file(session_id: object) -> Path:
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id if isinstance(session_id, str) else "")[:128]
    if not name.strip("."):
        name = "unknown-session"
    return ledger_dir() / f"{name}.jsonl"


def ledger_append(session_id: object, record: dict) -> bool:
    """Append one record; False when the ledger cannot be written (the hook goes on without it)."""
    try:
        path = ledger_file(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(descriptor, line)
        finally:
            os.close(descriptor)
        return True
    except OSError:
        return False


def ledger_records(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    records = []
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


class Ledger:
    """What one session's ledger says about its agents."""

    def __init__(self, records: list[dict]):
        self.launched: dict[str, str | None] = {}   # agent id -> name
        self.names: dict[str, str] = {}              # name -> id of the latest agent that bore it
        self.stopped: set[str] = set()
        self.checkpointed: set[str] = set()
        for record in records:
            agent = record.get("agent_id")
            if not isinstance(agent, str) or not agent:
                continue
            event = record.get("event")
            if event == "launched":
                name = record.get("name") if isinstance(record.get("name"), str) and record.get("name") else None
                self.launched[agent] = name
                if name:
                    self.names[name] = agent
            elif event == "stopped":
                self.stopped.add(agent)
            elif event == "checkpoint":
                self.checkpointed.add(agent)

    def knows(self, agent: str) -> bool:
        # A foreground agent's SubagentStop fires before the Agent tool returns its id, so a stop
        # on record proves the agent existed even when its launch has not been recorded yet.
        return agent in self.launched or agent in self.stopped


def record(payload: dict, event: str, **fields) -> None:
    ledger_append(payload.get("session_id"), {"event": event, **fields})


# --------------------------------------------------------------------------- hook answers


def deny(event: str, reason: str) -> int:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    return 0


def block(reason: str) -> int:
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def note(event: str, text: str) -> int:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))
    return 0


# --------------------------------------------------------------------------- reading results


def find_key(value: object, key: str, depth: int = 0) -> str | None:
    """The first string under `key` anywhere in a tool result: a dict, JSON text, or a list of text blocks."""
    if depth > 6:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in "{[":
            try:
                return find_key(json.loads(stripped), key, depth + 1)
            except ValueError:
                return None
        return None
    if isinstance(value, dict):
        found = value.get(key)
        if isinstance(found, str) and found:
            return found
        for inner in value.values():
            found = find_key(inner, key, depth + 1)
            if found:
                return found
    elif isinstance(value, list):
        for inner in value:
            found = find_key(inner, key, depth + 1)
            if found:
                return found
    return None


RESUMING = re.compile(r"^\s*Resuming agent\s+(\S+)")


def resumed_agent(value: object, depth: int = 0) -> str | None:
    """The agent a SendMessage result says the runtime resumed, or None."""
    if depth > 6:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in "{[":
            try:
                return resumed_agent(json.loads(stripped), depth + 1)
            except ValueError:
                pass
        match = RESUMING.match(value)
        return match.group(1).rstrip(".,;:") if match else None
    if isinstance(value, dict):
        direct = value.get("resumedAgentId")
        if isinstance(direct, str) and direct:
            return direct
        for inner in value.values():
            found = resumed_agent(inner, depth + 1)
            if found:
                return found
    elif isinstance(value, list):
        for inner in value:
            found = resumed_agent(inner, depth + 1)
            if found:
                return found
    return None


# --------------------------------------------------------------------------- context budget


def subagent_transcript(payload: dict) -> Path | None:
    agent = payload.get("agent_id")
    if not isinstance(agent, str) or not SAFE_ID.match(agent):
        return None
    candidates = []
    own = payload.get("agent_transcript_path")
    if isinstance(own, str) and own:
        candidates.append(Path(own))
    main = payload.get("transcript_path")
    if isinstance(main, str) and main:
        main_path = Path(main)
        if main_path.name == f"agent-{agent}.jsonl":
            candidates.append(main_path)
        candidates.append(main_path.with_suffix("") / "subagents" / f"agent-{agent}.jsonl")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def turn_context(line: object) -> int | None:
    """input + cache read + cache creation of an assistant line, or None for anything else."""
    if not isinstance(line, dict) or line.get("type") != "assistant":
        return None
    message = line.get("message")
    usage = message.get("usage") if isinstance(message, dict) else None
    if not isinstance(usage, dict):
        return None
    total = 0
    for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        count = usage.get(key)
        if isinstance(count, int) and not isinstance(count, bool) and count > 0:
            total += count
    return total or None


def latest_context(path: Path) -> int | None:
    """The context of the subagent's latest turn, from the tail of its transcript; None if unknown."""
    try:
        size = path.stat().st_size
        window = TAIL_START
        while True:
            start = max(0, size - window)
            with open(path, "rb") as handle:
                handle.seek(start)
                data = handle.read()
            lines = data.split(b"\n")
            if start > 0:
                lines = lines[1:]  # the first line of a tail is usually cut in two
            for raw in reversed(lines):
                if b'"usage"' not in raw:
                    continue
                try:
                    found = turn_context(json.loads(raw))
                except ValueError:
                    continue
                if found is not None:
                    return found
            if start == 0 or window >= TAIL_MAX:
                return None
            window *= 4
    except OSError:
        return None


def subagent_context(payload: dict) -> int | None:
    agent = payload.get("agent_id")
    if not isinstance(agent, str) or not agent:
        return None
    path = subagent_transcript(payload)
    return latest_context(path) if path else None


def allowed_at_hard_bound(tool: str, tool_input: dict) -> bool:
    """Past the hard bound only a git command, or this file's `handoff`, may run (POLICY 2).

    The command is tokenised the way a shell would (quotes respected, so a commit message may hold
    anything) and split on `&&`, `;` and newlines. Every piece must be `git ...`, `cd ...`, or
    `python3 <path>/agent-lifecycle-guard.py handoff ...`. A pipe, redirect, subshell or background
    job outside quotes refuses the whole command.
    """
    if tool != "Bash":
        return False
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
        lexer.whitespace_split = True
        lexer.whitespace = " \t\r"
        tokens = list(lexer)
    except ValueError:
        return False
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token.strip("();<>|&\n") == "" and token != "":
            if token.replace("\n", "").replace(" ", "") not in ("", "&&", ";"):
                return False
            segments.append([])
        else:
            segments[-1].append(token)
    segments = [segment for segment in segments if segment]
    if not segments:
        return False
    for segment in segments:
        if segment[0] in ("git", "cd"):
            continue
        if segment[0] in ("python3", "python") and len(segment) >= 3 \
                and os.path.basename(segment[1]) == GUARD_NAME and segment[2] == "handoff":
            continue
        return False
    return True


# --------------------------------------------------------------------------- hook events


def pre_tool_use(payload: dict) -> int:
    tool = payload.get("tool_name") if isinstance(payload.get("tool_name"), str) else ""
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    agent = payload.get("agent_id") if isinstance(payload.get("agent_id"), str) else ""

    if agent:
        context = subagent_context(payload)
        if context is not None and context >= HARD_TOKENS and not allowed_at_hard_bound(tool, tool_input):
            record(payload, "denied", reason="context-hard-bound", agent_id=agent, tool=tool, tokens=context)
            return deny("PreToolUse", (
                f"Context budget: this agent is at {context:,} tokens, past the hard bound of "
                f"{HARD_TOKENS:,}. Only a git command or the guard's `handoff` may run now. Commit "
                f"what is done (`git add` and `git commit`), run `python3 {GUARD_NAME} handoff` from "
                f"the worktree, and return the brief it prints as your final message. A fresh agent "
                f"continues from the repository; do not keep working in this one."))

    if tool == "SendMessage":
        return send_message(payload, tool_input)
    return 0


def send_message(payload: dict, tool_input: dict) -> int:
    target = tool_input.get("to")
    if not isinstance(target, str) or not target.strip():
        target = tool_input.get("recipient")
    if not isinstance(target, str) or not target.strip():
        return 0
    target = target.strip()
    if target == "main":
        return 0
    session = payload.get("session_id")
    ledger = Ledger(ledger_records(ledger_file(session)))
    by_id = bool(AGENT_ID.match(target))
    agent = target if by_id else ledger.names.get(target)
    if agent is None:
        return 0  # a teammate, a session, or an agent this ledger never saw: the backstop covers it
    if agent in ledger.stopped:
        record(payload, "denied", reason="completed-agent", agent_id=agent, target=target)
        return deny("PreToolUse", (
            f"{target} has completed its assignment and is single-use (AGENTS.md section 4: one agent, "
            f"one attempt). Sending to it would resume it, carrying its whole earlier context into "
            f"every turn. Dispatch a fresh agent with a concise brief from committed state: in an "
            f"engine `tools/repair-packet.py <pr> --finding ...`, anywhere `python3 {GUARD_NAME} "
            f"handoff` from the worktree. Do not paste the old agent's transcript into the brief."))
    if by_id and not ledger.knows(agent):
        record(payload, "denied", reason="unknown-agent-id", agent_id=agent, target=target)
        return deny("PreToolUse", (
            f"{target} was not launched in this session as far as the lifecycle ledger can show, so "
            f"this cannot show it is still running, and a message to a completed agent resumes it. "
            f"Message a running agent by the name it was launched with, or dispatch a fresh agent "
            f"with a concise brief from committed state."))
    return 0


def post_tool_use(payload: dict) -> int:
    tool = payload.get("tool_name") if isinstance(payload.get("tool_name"), str) else ""
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    response = payload.get("tool_response")

    if tool in AGENT_TOOLS:
        agent = find_key(response, "agentId")
        if agent:
            name = tool_input.get("name")
            record(payload, "launched", agent_id=agent, name=name if isinstance(name, str) and name else None)
        return 0

    if tool == "SendMessage":
        resumed = resumed_agent(response)
        if resumed:
            record(payload, "violation", reason="completed-agent-resumed", agent_id=resumed)
            return block(
                f"The runtime resumed agent {resumed}, which had completed: it is now running again "
                f"with its whole earlier context, which is the cost AGENTS.md section 4 exists to avoid. "
                f"Stop it (TaskStop), and dispatch a fresh agent with a concise brief from committed "
                f"state (in an engine `tools/repair-packet.py <pr> --finding ...`, anywhere `python3 "
                f"{GUARD_NAME} handoff`). Do not message completed agents.")

    agent = payload.get("agent_id")
    if isinstance(agent, str) and agent:
        context = subagent_context(payload)
        if context is not None and context >= CHECKPOINT_TOKENS and agent not in \
                Ledger(ledger_records(ledger_file(payload.get("session_id")))).checkpointed:
            record(payload, "checkpoint", agent_id=agent, tokens=context)
            return note("PostToolUse", (
                f"Context checkpoint: this agent is at {context:,} tokens, past {CHECKPOINT_TOKENS:,}, where "
                f"three in four first assignments have finished. Commit what is done now. Keep to your "
                f"assignment and do not widen it. If the remaining work is separable, return with a handoff "
                f"brief (`python3 {GUARD_NAME} handoff`) so a fresh agent continues from the repository. "
                f"At {HARD_TOKENS:,} only git commands and `handoff` will run."))
    return 0


def subagent_stop(payload: dict) -> int:
    agent = payload.get("agent_id")
    if isinstance(agent, str) and agent:
        record(payload, "stopped", agent_id=agent)
    return 0


def hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        print(f"{GUARD_NAME}: stdin is not a JSON object, so this guard cannot tell what it was asked "
              f"and refuses (a guard that guesses is not one).", file=sys.stderr)
        return 2
    event = payload.get("hook_event_name")
    if not isinstance(event, str):
        event = ("SubagentStop" if "agent_transcript_path" in payload or "last_assistant_message" in payload
                 else "PostToolUse" if "tool_response" in payload
                 else "PreToolUse" if "tool_name" in payload else "")
    handler = {"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use, "SubagentStop": subagent_stop}.get(event)
    if handler is None:
        return 0
    try:
        return handler(payload)
    except Exception as error:  # noqa: BLE001 -- see "WHAT IT CANNOT SEE": an internal error fails open, loudly
        print(f"{GUARD_NAME}: internal error ({type(error).__name__}: {error}); the call goes through.",
              file=sys.stderr)
        return 0


# --------------------------------------------------------------------------- handoff


def git(*args: str) -> tuple[int, str]:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return 127, str(error)
    return done.returncode, done.stdout.rstrip("\n") if done.returncode == 0 else (done.stderr or done.stdout).strip()


def bounded(lines: list[str], limit: int, what: str) -> list[str]:
    if len(lines) <= limit:
        return lines
    return lines[:limit] + [f"... and {len(lines) - limit} more {what}"]


def cmd_handoff(args: argparse.Namespace) -> int:
    code, top = git("rev-parse", "--show-toplevel")
    if code != 0:
        print(f"handoff: not inside a git worktree ({top})", file=sys.stderr)
        return 1
    code, dirty = git("status", "--porcelain")
    if code != 0:
        print(f"handoff: git status failed: {dirty}", file=sys.stderr)
        return 1
    if dirty.strip():
        shown = bounded(dirty.splitlines(), 20, "paths")
        print("handoff refused: the worktree has uncommitted work, and a handoff is a brief from committed "
              "state only, so this would not survive it. Commit it (or remove what is not yours), then run "
              "handoff again.\n" + "\n".join(f"  {line}" for line in shown), file=sys.stderr)
        return 1
    _, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    _, head = git("log", "-1", "--format=%H %s", "HEAD")
    out = [f"handoff brief (policy version {POLICY_VERSION}), from committed state in {top}",
           f"branch: {branch}", f"head: {head}"]
    base = args.base
    code, base_sha = git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if code != 0:
        out.append(f"base: {base} (not found here, so the commit list and file list are omitted)")
    else:
        out.append(f"base: {base} ({base_sha[:12]})")
        _, log = git("log", "--oneline", f"{base}..HEAD")
        entries = log.splitlines()
        out.append(f"commits on the branch since the base ({len(entries)}):")
        out.extend(f"  {line}" for line in bounded(entries, BRIEF_COMMITS, "commits") or ["  (none)"])
        _, names = git("diff", "--name-status", f"{base}...HEAD")
        files = names.splitlines()
        out.append(f"files changed since the base ({len(files)}):")
        out.extend(f"  {line}" for line in bounded(files, BRIEF_FILES, "files") or ["  (none)"])
    code, counts = git("rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    if code == 0 and len(counts.split()) == 2:
        behind, ahead = counts.split()
        _, upstream = git("rev-parse", "--abbrev-ref", "@{upstream}")
        out.append(f"upstream: {upstream}, {ahead} ahead, {behind} behind")
    else:
        out.append("upstream: none configured (the branch has not been pushed)")
    out.append("The next agent reads the repository, not a transcript: the code, the tests, the issue and the "
               "pull request are the state; nothing the previous agent remembered is carried over.")
    print("\n".join(out))
    return 0


# --------------------------------------------------------------------------- check-settings


def matcher_covers(matcher: object, tool: str) -> bool:
    if matcher is None or matcher in ("", "*"):
        return True
    if not isinstance(matcher, str):
        return False
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return False


def covers(matcher: object, scope: str | None) -> bool:
    if scope is None:
        return True
    if scope == ALL_TOOLS:
        return all(matcher_covers(matcher, tool) for tool in PROBE_TOOLS)
    return matcher_covers(matcher, scope)


def describe(event: str, scope: str | None) -> str:
    if scope is None:
        return event
    return f"{event} for all tools (matcher \"*\")" if scope == ALL_TOOLS else f"{event} for {scope}"


def settings_problems(settings: object) -> list[str]:
    """One line per registration `REQUIRED_HOOKS` asks for that `settings` does not carry."""
    if not isinstance(settings, dict):
        return ["the settings are not a JSON object"]
    problems = []
    if settings.get("disableAllHooks") is True:
        problems.append("`disableAllHooks` is true, so no hook runs, this guard included")
    hooks = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}
    for event, scope, why in REQUIRED_HOOKS:
        found = False
        entries = hooks.get(event) if isinstance(hooks.get(event), list) else []
        for entry in entries:
            if not isinstance(entry, dict) or not covers(entry.get("matcher"), scope):
                continue
            for hook_ in entry.get("hooks") if isinstance(entry.get("hooks"), list) else []:
                if isinstance(hook_, dict) and hook_.get("type", "command") == "command" \
                        and GUARD_NAME in str(hook_.get("command", "")):
                    found = True
        if not found:
            problems.append(f"missing: {describe(event, scope)} does not run {GUARD_NAME} (needed to {why})")
    return problems


def cmd_check_settings(args: argparse.Namespace) -> int:
    try:
        settings = json.loads(Path(args.path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"{args.path}: cannot be read as JSON settings ({error})", file=sys.stderr)
        return 1
    problems = settings_problems(settings)
    if problems:
        print(f"{args.path} does not wire {GUARD_NAME}:\n" + "\n".join(f"  {line}" for line in problems))
        return 1
    print(f"{args.path} wires {GUARD_NAME}: " + "; ".join(describe(e, s) for e, s, _ in REQUIRED_HOOKS))
    return 0


# --------------------------------------------------------------------------- measure


def percentile(values: list[int], percent: int) -> int:
    """Nearest rank: the smallest value with at least `percent` of the sample at or below it."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percent / 100 * len(ordered)) - 1)]


def parse_time(text: object) -> datetime.datetime | None:
    if not isinstance(text, str):
        return None
    try:
        value = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)


def read_jsonl(path: Path, needles: tuple[bytes, ...]):
    """Parsed lines of `path` that contain any of `needles`, in file order. Streaming; bad lines skipped."""
    try:
        with open(path, "rb") as handle:
            for raw in handle:
                if any(needle in raw for needle in needles):
                    try:
                        parsed = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(parsed, dict):
                        yield parsed
    except OSError:
        return


def transcript_turns(path: Path) -> list[tuple[datetime.datetime | None, int, int]]:
    """(time, context, tokens processed) per turn of one agent, a message id counted once (its last line)."""
    order: list[str] = []
    turns: dict[str, tuple[datetime.datetime | None, int, int]] = {}
    for index, line in enumerate(read_jsonl(path, (b'"usage"',))):
        context = turn_context(line)
        if context is None:
            continue
        message = line["message"]
        usage = message["usage"]
        output = usage.get("output_tokens")
        output = output if isinstance(output, int) and not isinstance(output, bool) and output > 0 else 0
        key = message.get("id") if isinstance(message.get("id"), str) and message.get("id") else f"#{index}"
        stamp = parse_time(line.get("timestamp"))
        if key in turns:
            stamp = turns[key][0] or stamp  # the turn began at its first line
        else:
            order.append(key)
        turns[key] = (stamp, context, context + output)
    return [turns[key] for key in order]


def resume_events(path: Path) -> list[tuple[str, str]]:
    """(timestamp text, resumed agent id) for each toolUseResult.resumedAgentId in a transcript."""
    found = []
    for line in read_jsonl(path, (b"resumedAgentId",)):
        result = line.get("toolUseResult")
        agent = result.get("resumedAgentId") if isinstance(result, dict) else None
        if isinstance(agent, str) and agent:
            found.append((str(line.get("timestamp") or ""), agent))
    return found


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "n/a"


def cmd_measure(args: argparse.Namespace) -> int:
    root = Path(args.projects_dir) if args.projects_dir else Path(os.path.expanduser("~")) / ".claude" / "projects"
    if not root.is_dir():
        print(f"measure: no projects directory at {root}", file=sys.stderr)
        return 1
    try:
        pattern = re.compile(args.match) if args.match else None
    except re.error as error:
        print(f"measure: --match is not a regular expression ({error})", file=sys.stderr)
        return 2
    projects = [p for p in sorted(root.iterdir()) if p.is_dir() and (pattern is None or pattern.search(p.name))]
    if not projects:
        print(f"measure: no project under {root} matches {args.match!r}", file=sys.stderr)
        return 1

    events: dict[str, set[tuple[str, str]]] = {}
    agents: dict[str, Path] = {}
    for project in projects:
        for main in sorted(project.glob("*.jsonl")):
            for stamp, agent in resume_events(main):
                events.setdefault(agent, set()).add((stamp, agent))
            for transcript in sorted((project / main.stem / "subagents").glob("agent-*.jsonl")):
                agent_id = transcript.stem[len("agent-"):]
                agents[f"{project.name}/{main.stem}/{agent_id}"] = transcript
                for stamp, agent in resume_events(transcript):
                    events.setdefault(agent, set()).add((stamp, agent))

    total = post_tokens = post_turns = reread = 0
    peaks: list[int] = []
    resumed_agents = set()
    for key in sorted(agents):
        agent_id = key.rsplit("/", 1)[1]
        turns = transcript_turns(agents[key])
        total += sum(tokens for _, _, tokens in turns)
        when = sorted(t for t in (parse_time(stamp) for stamp, _ in events.get(agent_id, ())) if t)
        if when:
            resumed_agents.add(key)
        if not turns:
            continue
        segment, previous = [], None
        for stamp, _, _ in turns:
            previous = stamp or previous
            segment.append(bisect.bisect_left(when, previous) if previous else 0)
        first_context = turns[0][1]
        peaks.append(max([context for (_, context, _), s in zip(turns, segment) if s == 0] or [first_context]))
        for index, ((_, context, tokens), s) in enumerate(zip(turns, segment)):
            if s == 0:
                continue
            post_tokens += tokens
            post_turns += 1
            before = [turns[i][1] for i in range(index) if segment[i] < s]
            reread += max(0, min(context, before[-1] if before else 0) - first_context)

    known = {key.rsplit("/", 1)[1] for key in agents}
    all_events = sorted((stamp, agent) for agent, stamps in events.items() for stamp, _ in stamps)
    counted = [(stamp, agent) for stamp, agent in all_events if agent in known]

    print("rules-agent-lifecycle measure (tokens are input + cache read + cache creation + output per turn)")
    print(f"projects dir: {root}")
    print(f"projects matched: {len(projects)}")
    print(f"agents: {len(agents)}")
    print(f"resumed agents: {len(resumed_agents)}")
    print(f"resume events: {len(counted)}")
    print(f"resume events without a transcript: {len(all_events) - len(counted)}")
    print(f"tokens in all agent turns: {total}")
    print(f"post-resume turns: {post_turns}")
    print(f"tokens in post-resume turns: {post_tokens} ({pct(post_tokens, total)} of all)")
    print(f"re-read tokens beyond the first turn: {reread} ({pct(reread, total)} of all) -- an ESTIMATE of what "
          f"a fresh agent would not have carried: per post-resume turn, max(0, min(context, context at the end "
          f"of the previous segment) - context of the agent's first turn)")
    if peaks:
        print(f"first-assignment peak context over {len(peaks)} agents (nearest rank): "
              + " ".join(f"p{p} {percentile(peaks, p)}" for p in (50, 75, 90, 95)))
    else:
        print("first-assignment peak context: no agent turns found")

    directory = Path(args.ledger_dir) if args.ledger_dir else ledger_dir()
    files = sorted(directory.glob("*.jsonl")) if directory.is_dir() else []
    if not files:
        print(f"guard ledger: none at {directory}")
    else:
        records = [r for f in files for r in ledger_records(f)]
        reasons: dict[str, int] = {}
        for r in records:
            if r.get("event") == "denied":
                reasons[str(r.get("reason"))] = reasons.get(str(r.get("reason")), 0) + 1
        print(f"guard ledger: {directory} ({len(files)} sessions)")
        print(f"guard denials: {sum(reasons.values())}"
              + (" (" + ", ".join(f"{k}: {v}" for k, v in sorted(reasons.items())) + ")" if reasons else ""))
        print(f"guard violations (a completed agent was resumed anyway): "
              f"{sum(1 for r in records if r.get('event') == 'violation')}")
        print(f"checkpoint notes issued: {sum(1 for r in records if r.get('event') == 'checkpoint')}")
    if counted:
        print("resume events (time, agent):")
        for stamp, agent in counted:
            print(f"  {stamp or 'untimed'} {agent}")
    return 0


# --------------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=GUARD_NAME, description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    handoff = sub.add_parser("handoff", help="a brief from committed state, for the next agent")
    handoff.add_argument("--base", default="origin/main", help="the ref the branch is measured against")
    check = sub.add_parser("check-settings", help="exit 0 iff the settings file wires this guard")
    check.add_argument("path")
    measure = sub.add_parser("measure", help="telemetry from Claude Code transcripts and the guard ledger")
    measure.add_argument("--projects-dir", default=None, help="default ~/.claude/projects")
    measure.add_argument("--match", default=None, help="regex over project directory names")
    measure.add_argument("--ledger-dir", default=None, help="default: the ledger directory this guard writes")
    return parser


def main(argv: list[str]) -> int:
    if not argv:
        return hook()
    args = build_parser().parse_args(argv)
    return {"handoff": cmd_handoff, "check-settings": cmd_check_settings, "measure": cmd_measure}[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
