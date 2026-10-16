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
  * PostToolUse of the Agent tool carries the new agent's `agentId` (and `tool_input.name`) and a
    `tool_response.status`: `async_launched` for a background agent, `completed` when a foreground
    agent returned its final result.
  * The MAIN session transcript (`transcript_path`, the same file inside a subagent) records a task
    notification when an agent stops, as a `queue-operation` record with `"operation": "enqueue"`
    whose `content` is a string that STARTS with `<task-notification>` and holds `<task-id>AGENT_ID
    </task-id>` and `<status>STATUS</status>`. The runtime may also append the same text inside a
    tool_result (when an agent reads it back), which is not a notification; a subagent's message to
    the main session is enqueued wrapped as `<agent-message from="...">`, so it cannot start with
    `<task-notification>`; a user prompt can (the user is trusted). The transcript also holds the Agent
    `tool_use` (`input.name`) and its tool_result (`toolUseResult.agentId`), which is how a name is
    resolved when the ledger never saw it.
  * SubagentStop is NOT evidence of completion: another stop hook can veto it (the agent then keeps
    running), so this guard neither registers for it nor handles it.
  * SendMessage's target `to` is resolved by the runtime to a RUNNING task ("Message queued for
    delivery ... at its next tool round") or to a stopped or evicted one, which it RESUMES
    ("Resuming agent X", `resumedAgentId`). PreToolUse sees the target before that resolution.
  * A subagent's transcript is <transcript_path minus .jsonl>/subagents/agent-<agent_id>.jsonl;
    each assistant line has message.usage, and the context of a turn is input_tokens +
    cache_read_input_tokens + cache_creation_input_tokens.

WHAT IT ENFORCES
  * PreToolUse SendMessage to a target with definitive evidence of completion: denied. The evidence
    is (a) a PostToolUse of Agent whose tool_response status is `completed` (a foreground agent
    returned), recorded in the ledger, or (b) a task notification for it, read ONLY from a main
    transcript `queue-operation` enqueue record whose content starts with `<task-notification>` (task
    id and status from that leading block alone), with any status but `running`. A notification
    quoted anywhere else (a tool_result that read a file or a log, an `<agent-message>`, any other
    record, any string past the leading block) is not evidence. A name is resolved to every id the ledger and the main
    transcript launched under it, and two names are equal under `normal_name` (NFKC, control and format characters dropped, `str.lower()`, whitespace runs to `-`,
    trimmed, applied to both sides: the runtime's own equivalence). A name that resolves to more than one launched
    agent is denied when ANY of them has completed (fail safe: the runtime picks one of them). To an id-shaped target ("a" + 16 hex) neither the ledger nor the transcript saw
    launched: denied, because this cannot show it is running (fail closed). To a launched agent with
    no completion evidence (running): allowed. To "main": allowed.
  * PostToolUse SendMessage whose result says the runtime resumed an agent: recorded as a
    violation, and the model is told to stop that agent and dispatch a fresh one. Detection after
    the fact, for the case the PreToolUse check could not see. Claude Code 2.1.287 reports a resume
    five ways (a result that is a dict, JSON text, or a list of text blocks): the key `resumedAgentId`
    or `inlineHandback`, or a message that STARTS `Resuming agent ` or `Resumed agent`, or one that does not
    start `Message queued` and contains the runtime's fixed phrases `" was resumed but`, `" was not running;
    resumed it as an in-process teammate` or ` is already waking; message queued for its next tool round`.
    The display name, which may hold spaces and quotes, is never pattern-matched. A message starting
    `Message queued` (X running, or main) is none of them, whatever its recipient's name says, unless the
    result carries `resumedAgentId` or `inlineHandback`.
  * Context budget, in subagents only (see POLICY 2).

WHAT IT CANNOT SEE
  * A name target neither the ledger nor the main transcript resolves (a teammate, another session,
    an agent launched before this guard was wired, one launched inside a subagent before the
    ledger saw it) is allowed; only the PostToolUse backstop catches a resume through it, after it
    has happened.
  * An agent that stopped without a result the hooks or the transcript show (a notification the
    runtime did not write, a transcript that is missing or unreadable) looks running, so a message to
    it is allowed. The evidence is definitive when present and silent when absent.
  * Hooks the user disables (`disableAllHooks`), user-level settings, the main session's own
    context, and any harness other than Claude Code: another harness's calls that resume a finished
    agent or send it input are unverified here and covered by nothing in this file.
  * The context budget reads the subagent's transcript tail. A transcript that is missing,
    unreadable, or in a layout this file does not recognise gives NO budget verdict: the guard
    cannot tell, so it neither warns nor stops. It never crashes the hook over it.
  * A hard-bound Bash command is not parsed by any shell model: the whole command string must
    FULLMATCH a strict regular grammar (`HARD_BOUND_GIT`, `HARD_BOUND_HANDOFF`), and anything else is
    refused. Tokens are SAFE words, `[A-Za-z0-9_./:@+=,-]+` (no `::`, so no `ext::` transport); a word
    that starts with `-` must be one of the subcommand's allowlisted options (`GIT_OPTIONS`). The
    forms are `git [-C <dir>] <subcommand> <options and words>`, with the subcommand one of add,
    commit, status, diff, log, show, push, rev-parse and `branch --show-current`, and
    `python3 <path> handoff [--base <ref>]`, where <path> resolved against the hook's `cwd` is the
    running guard's own file (real path). A commit message is the one quoted thing: `-m "..."` with
    no `$`, backtick, backslash, `!`, double quote or newline in it. Every other character anywhere
    (dollar, a quote other than a commit message's, `; & | < > # ( ) { } * ? ~`, backslash, `!`,
    backtick, newline) refuses the command, so `cd`, `&&`, redirects, `$(...)`, `$'...'`, a comment, a heredoc and an alias `-c` are all refused. By design a
    commit message written as a heredoc or with `$(...)` is refused past the bound: it is the price of
    not judging a shell's parse. A guard path outside the SAFE characters cannot be run past the
    bound either. What a permitted git command runs of the repository's own configuration (a commit
    hook, a configured external diff driver) is not judged: accident prevention, not security.
  * An internal error is reported on stderr and lets the call through. A guard that blocks every
    tool because of its own bug is worse than a missing one, and `check-settings`, the rail-bytes
    check and the tests are what notice a guard that is not what it should be.

THE LEDGER: one append-only JSONL file per session, in $RULES_AGENT_LEDGER_DIR, else
${XDG_STATE_HOME:-~/.local/state}/rules-agent-lifecycle/, named by the sanitised session_id.
It is never inside a repository: it is the machine's record of what happened in a session, not a
build input. A location is used only when it is an absolute path and neither it nor any directory
above it (symbolic links followed) holds a `.git`. A $RULES_AGENT_LEDGER_DIR that fails this is
REFUSED with a message on stderr, before anything is created, and the default location is used
instead; a relative $XDG_STATE_HOME is ignored as the XDG specification says. If the default fails
too (HOME is itself a work tree), there is no ledger: nothing is written and nothing is read, and
the PreToolUse SendMessage check fails closed as it does for any id it never saw launched, because
with no ledger it cannot show an id is running. The ledger FILE is opened with O_NOFOLLOW and a ledger
file that is a symbolic link is refused (nothing written, nothing read), because a link in an
otherwise outside directory would carry the append into a repository. Records: launched, stopped
(foreground result), checkpoint, denied, violation.

USAGE
  agent-lifecycle-guard.py                          hook mode: one JSON event on stdin
  agent-lifecycle-guard.py handoff [--base REF]     brief from committed state (default origin/main)
  agent-lifecycle-guard.py check-settings PATH [--guard-path REL]
                                                    0 iff PATH wires this guard (REQUIRED_HOOKS): every
                                                    group and entry under EVERY event is typed (a group
                                                    has only `matcher`, a string, and `hooks`, a non-empty
                                                    list of `command` hooks with a string `command`, a
                                                    positive `timeout`, boolean `async`/`asyncRewake`/
                                                    `once`, string `if`), each invalid item named by its
                                                    path; this guard's own registration has only `type`,
                                                    `command` and `timeout`, and that
                                                    command is exactly `python3 "$CLAUDE_PROJECT_DIR/REL"`
                                                    (REL default .claude/hooks/agent-lifecycle-guard.py)
  agent-lifecycle-guard.py measure [--projects-dir DIR] [--match REGEX] [--ledger-dir DIR] [--events]
                                                    summary; --events adds one line per resume

Hook answers: a PreToolUse refusal is `permissionDecision: deny` on stdout, exit 0. A PostToolUse
correction is `decision: block`; a note is `additionalContext`. Malformed stdin is exit 2 with a
message on stderr: this guard cannot tell what it was asked, so it does not guess. That includes
stdin the JSON parser cannot take at all (nested too deeply, not UTF-8: the bytes are decoded strictly before
the JSON, so an invalid byte inside a string is refused as well).

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
import unicodedata
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
# scope is a tool name the matcher must cover or ALL_TOOLS. There is no SubagentStop entry: another
# stop hook can veto that event, so receiving it is not evidence that an agent completed.
ALL_TOOLS = "*"
REQUIRED_HOOKS = (
    ("PreToolUse", "SendMessage", "refuse a message to a completed agent"),
    ("PreToolUse", ALL_TOOLS, "enforce the context hard bound in every tool"),
    ("PostToolUse", ALL_TOOLS, "record launches and completions, detect a resume, issue the checkpoint note"),
)
# The matchers that mean every tool, whatever tools exist: absent (None here: an explicit null is not a
# string, and `registration_defects` refuses it), empty, `*`. A matcher that lists tools covers those
# and nothing else, however long the list, so it is not on this list.
UNRESTRICTED_MATCHERS = (None, "", "*")
# Where the guard sits in an engine; this repository's own settings name another path (--guard-path).
DEFAULT_GUARD_PATH = ".claude/hooks/agent-lifecycle-guard.py"
# Hook keys that run a command in the background, where a decision cannot be enforced.
BACKGROUND_KEYS = ("async", "asyncRewake")

# Past the hard bound the only commands that run are the ones this grammar accepts, as a whole string
# and with no shell model behind it (see WHAT IT CANNOT SEE). A word is SAFE when made only of these
# characters; a word that starts with `-` is accepted only as one of the subcommand's options below.
# `::` is left out of a plain word so that no `ext::` or `fd::` transport can be named.
_WS = r"[ \t]+"
_PLAIN = r"(?!-)(?:[A-Za-z0-9_./@+=,-]|:(?!:))+"
_MESSAGE = r'"[^"$`\\!\n]*"'
# subcommand -> options it may carry (regular expression alternatives), whether a plain word may follow.
GIT_OPTIONS = {
    "add": (r"-A|--all|-u|--", True),
    "commit": (r"-a|--all|-m" + _WS + _MESSAGE, True),
    "status": (r"-s|--short|--porcelain|-b", True),
    "diff": (r"--stat|--name-status|--cached|--staged", True),
    "log": (r"--oneline|--stat|-n|-[0-9]+", True),
    "show": (r"--stat|--name-status", True),
    "push": (r"-u|--set-upstream", True),
    "rev-parse": (r"--abbrev-ref|--show-toplevel", True),
    "branch": (r"--show-current", False),   # listing only: a plain word would create a branch
}


def _git_subcommand(name: str) -> str:
    options, words = GIT_OPTIONS[name]
    return rf"{re.escape(name)}(?:{_WS}(?:{options}{'|' + _PLAIN if words else ''}))*"


HARD_BOUND_GIT = re.compile(
    rf"[ \t]*git(?:{_WS}-C{_WS}{_PLAIN})?{_WS}(?:" + "|".join(_git_subcommand(n) for n in GIT_OPTIONS)
    + r")[ \t]*", re.ASCII)
HARD_BOUND_HANDOFF = re.compile(
    rf"[ \t]*python3{_WS}({_PLAIN}){_WS}handoff(?:{_WS}--base{_WS}{_PLAIN})?[ \t]*", re.ASCII)

TAIL_START = 256 * 1024
TAIL_MAX = 16 * 1024 * 1024
BRIEF_COMMITS = 40
BRIEF_FILES = 80


# --------------------------------------------------------------------------- the ledger


def inside_work_tree(path: Path) -> bool:
    """True when `path`, or a directory above it once symbolic links are followed, holds a `.git`."""
    try:
        resolved = Path(os.path.realpath(path))
    except (OSError, ValueError):
        return True  # cannot tell where it is, so it is not shown to be outside
    return any((directory / ".git").exists() for directory in (resolved, *resolved.parents))


def usable_ledger_dir(path: Path) -> bool:
    return path.is_absolute() and not inside_work_tree(path)


def ledger_dir() -> Path | None:
    """Where the ledger lives, or None when no location is usable (see THE LEDGER)."""
    override = os.environ.get("RULES_AGENT_LEDGER_DIR")
    if override:
        if usable_ledger_dir(Path(override)):
            return Path(override)
        print(f"{GUARD_NAME}: RULES_AGENT_LEDGER_DIR={override!r} is relative or inside a git work tree, "
              f"so it is refused and the default location is used; the ledger is never inside a repository.",
              file=sys.stderr)
    state = os.environ.get("XDG_STATE_HOME")
    if not state or not os.path.isabs(state):
        state = os.path.join(os.path.expanduser("~"), ".local", "state")
    default = Path(state) / "rules-agent-lifecycle"
    if usable_ledger_dir(default):
        return default
    print(f"{GUARD_NAME}: no usable ledger location ({default} is relative or inside a git work tree), so "
          f"nothing is recorded.", file=sys.stderr)
    return None


def ledger_file(session_id: object) -> Path | None:
    directory = ledger_dir()
    if directory is None:
        return None
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id if isinstance(session_id, str) else "")[:128]
    if not name.strip("."):
        name = "unknown-session"
    path = directory / f"{name}.jsonl"
    if os.path.islink(path):
        # The directory was checked, the file in it was not: a link would carry the append into a
        # repository. A linked ledger file is no ledger.
        print(f"{GUARD_NAME}: the ledger file {path} is a symbolic link, so it is refused and nothing is "
              f"recorded or read.", file=sys.stderr)
        return None
    return path


def ledger_append(session_id: object, record: dict) -> bool:
    """Append one record; False when the ledger cannot be written (the hook goes on without it)."""
    try:
        path = ledger_file(session_id)
        if path is None:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            os.write(descriptor, line)
        finally:
            os.close(descriptor)
        return True
    except OSError:
        return False


# What the runtime's `\s` matches (JavaScript), the only whitespace its resolver turns into `-`.
_RUNTIME_SPACE = "\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_RUNTIME_SPACES = re.compile(f"[{_RUNTIME_SPACE}]+")
_RUNTIME_SPACE_CHAR = re.compile(f"[{_RUNTIME_SPACE}]")


def _without_invisible(text: str) -> str:
    """`text` without its control (Cc) and format (Cf) characters, except those the runtime reads as whitespace."""
    return "".join(char for char in text
                   if unicodedata.category(char) not in ("Cc", "Cf") or _RUNTIME_SPACE_CHAR.match(char))


def normal_name(name: str) -> str:
    """The one form in which two agent names are compared, on both sides, wherever a name is matched.

    NFKC, control and format characters dropped (Unicode categories Cc and Cf, except the few the runtime
    reads as whitespace), `str.lower()`, every run of whitespace turned into one `-`, trimmed. The runtime resolves
    a SendMessage target to an agent under its own normalisation (read in Claude Code 2.1.287: NFKC; remove
    Cc and Cf characters unless `\\s` matches them; trim; lower case; whitespace runs to `-`), so `WORKER`,
    ` worker `, a full-width `ｗｏｒｋｅｒ`, `worker` followed by a zero-width space, and `review agent` for
    `review-agent` all reach the agent launched under the plain name. It is the runtime's equivalence, not a wider one:
    `casefold()` would merge names the runtime keeps apart (`worker-ß`, `worker-ss`), and a completed agent
    would hide behind a running one. A name that still resolves to several launched agents is judged by
    `send_message`, which denies when any of them has completed.
    """
    text = _without_invisible(unicodedata.normalize("NFKC", name)).lower()
    return "-".join(part for part in _RUNTIME_SPACES.split(text) if part)


UNDECODABLE = object()


def decode_json(data: str | bytes):
    """The one place this guard decodes JSON: the value, or UNDECODABLE when anything at all goes wrong.

    ValueError is not the only way a decoder fails: 10,000 nested arrays raise RecursionError, a huge
    number MemoryError, a bad type TypeError. Every such failure means the same thing, that this item is
    not a record. Callers skip the item and go on to the rest, because one poisoned line or text block
    must not discard definitive evidence beside it (a resume, a completed agent). Stdin the hook cannot
    decode is the exception to going on: `hook` refuses it (exit 2).
    """
    try:
        return json.loads(data)
    except Exception:  # noqa: BLE001 -- see above: every failure is one answer
        return UNDECODABLE


def ledger_records(path: Path | None) -> list[dict]:
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    records = []
    for line in text.splitlines():
        record = decode_json(line)
        if isinstance(record, dict):
            records.append(record)
    return records


class Ledger:
    """What one session's ledger says about its agents."""

    def __init__(self, records: list[dict]):
        self.launched: dict[str, str | None] = {}   # agent id -> name
        self.names: dict[str, list[str]] = {}        # normal_name(name) -> ids of every agent that bore it
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
                    ids = self.names.setdefault(normal_name(name), [])
                    if agent not in ids:
                        ids.append(agent)
            elif event == "stopped":
                self.stopped.add(agent)
            elif event == "checkpoint":
                self.checkpointed.add(agent)

    def knows(self, agent: str) -> bool:
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
            decoded = decode_json(stripped)
            return None if decoded is UNDECODABLE else find_key(decoded, key, depth + 1)
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
RESUMED = re.compile(r"^\s*Resumed agent(?:\s+(\S+))?")
QUEUED = re.compile(r"^\s*Message queued")
# The runtime's own fixed wording around the caller's display name, which is never matched.
RESUME_PHRASES = (
    '" was resumed but',
    '" was not running; resumed it as an in-process teammate',
    " is already waking; message queued for its next tool round",
)
NAME_EDGES = ".,;:\"'"


def resume_in_text(text: str) -> str | None:
    """"" when a runtime message says it resumed an agent, the agent's id or name when it names one, else None.

    Claude Code 2.1.287 words a resume five ways. Two START with fixed words: `Resuming agent X` and
    `Resumed agent` (alone, or `Resumed agent X. Result: ...`). Three put the caller's display name, which
    may hold spaces and quotes, before or between fixed phrases: `Agent "X" was resumed but ...` (it failed
    while running), `Teammate "X" was not running; resumed it as an in-process teammate ...`, and
    `X is already waking; message queued for its next tool round` (another caller resumed it). So the display
    name is never pattern-matched: a message that does not start with `Message queued` is a resume when it
    contains one of those fixed phrases or starts with one of the first two. A message that starts
    `Message queued` reports a delivery to a running agent or to main, and the recipient's name, which is
    the caller's text, may hold any of the phrases (a running agent named `worker was resumed but still
    running`): it is no resume.
    """
    if QUEUED.match(text):
        return None
    match = RESUMING.match(text)
    if match:
        return match.group(1).strip(NAME_EDGES)
    match = RESUMED.match(text)
    if match:
        return (match.group(1) or "").strip(NAME_EDGES)
    if any(phrase in text for phrase in RESUME_PHRASES):
        return ""
    return None


def resumed_agent(value: object, depth: int = 0) -> str | None:
    """The agent a SendMessage result says the runtime resumed, or None if it reports no resume.

    The result is a dict, JSON text, or a list of text blocks. A resume is `resumedAgentId`, an
    `inlineHandback` key, or a message in one of the forms of `resume_in_text`. The answer is the agent's
    id or name, or "" when the result says it resumed one without naming it (test with `is not None`).
    """
    if depth > 6:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in "{[":
            decoded = decode_json(stripped)
            if decoded is not UNDECODABLE:
                return resumed_agent(decoded, depth + 1)
        return resume_in_text(value)
    if isinstance(value, dict):
        direct = value.get("resumedAgentId")
        if isinstance(direct, str) and direct:
            return direct
        if "inlineHandback" in value:
            message = value.get("message")
            named = resume_in_text(message) if isinstance(message, str) else None
            return named or ""
        for inner in value.values():
            found = resumed_agent(inner, depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for inner in value:
            found = resumed_agent(inner, depth + 1)
            if found is not None:
                return found
    return None


# --------------------------------------------------------------------------- completion evidence


def guard_command() -> str:
    """How to run this file's `handoff`: the real path of the running guard, quoted for a shell."""
    return f"python3 {shlex.quote(os.path.realpath(__file__))} handoff"


def main_transcript(payload: dict) -> Path | None:
    """The session's MAIN transcript. Inside a subagent the hook still gets that one; a subagent's own
    file (<session>/subagents/agent-<id>.jsonl) is mapped back to it, should a runtime hand that over."""
    raw = payload.get("transcript_path")
    if not isinstance(raw, str) or not raw:
        return None
    path = Path(raw)
    if path.parent.name == "subagents" and path.parent.parent.name:
        path = path.parent.parent.with_name(path.parent.parent.name + ".jsonl")
    return path


def transcript_lines(path: Path, needles: tuple[bytes, ...]):
    """(raw, parsed) for each line of `path` holding any of `needles` that parses as a JSON object.
    Streaming: a long transcript is never held in memory, and a line that lacks every needle is not parsed."""
    try:
        with open(path, "rb") as handle:
            for raw in handle:
                if not any(needle in raw for needle in needles):
                    continue
                parsed = decode_json(raw)
                if isinstance(parsed, dict):
                    yield raw, parsed
    except (OSError, ValueError):
        return


TASK_NOTIFICATION = "<task-notification>"
_NOTIFIED_ID = re.compile(r"<task-id>\s*([^<\s]+)\s*</task-id>")
_NOTIFIED_STATUS = re.compile(r"<status>\s*([A-Za-z_-]+)\s*</status>")


def enqueued_notification(parsed: dict) -> tuple[str, str] | None:
    """(task id, status) of a genuine task notification record, else None.

    Genuine means one thing: a `queue-operation` record with `operation` `enqueue` whose `content` is a
    string STARTING with `<task-notification>`. The id and the status are read from that leading block,
    up to its first `</task-notification>`, and from nowhere else: a notification quoted in a
    tool_result, in an `<agent-message>` or past the block is text someone wrote, not the runtime.
    """
    if parsed.get("type") != "queue-operation" or parsed.get("operation") != "enqueue":
        return None
    content = parsed.get("content")
    if not isinstance(content, str) or not content.startswith(TASK_NOTIFICATION):
        return None
    block = content.split("</task-notification>", 1)[0]
    task, status = _NOTIFIED_ID.search(block), _NOTIFIED_STATUS.search(block)
    return (task.group(1), status.group(1) if status else "") if task else None


def transcript_agent_state(path: Path, agent: str) -> tuple[bool, bool]:
    """(seen, completed) for `agent` in the main transcript.

    Seen: an Agent tool result carried this agent id, or a genuine task notification named it.
    Completed: a genuine task notification (`enqueued_notification`) for it whose status is not
    `running`, or a foreground Agent result that says the agent completed.
    """
    seen = completed = False
    for _, parsed in transcript_lines(path, (agent.encode("utf-8"),)):
        result = parsed.get("toolUseResult")
        if isinstance(result, dict) and result.get("agentId") == agent:
            seen = True
            if result.get("status") == "completed":
                completed = True
        found = enqueued_notification(parsed)
        if found is not None and found[0] == agent:
            seen = True
            if found[1] and found[1] != "running":
                completed = True
    return seen, completed


def transcript_agents_for_name(path: Path, name: str) -> list[str]:
    """The ids of every agent launched with `name`: an Agent tool_use whose input.name is `name` under
    `normal_name`, and the agentId on the toolUseResult of the tool_result that answered it.

    The name cannot be a byte needle, because the launch may spell it any way `normal_name` folds, so the
    lines parsed are the launches (the tool's own name) and the results that carry an agent id."""
    wanted = normal_name(name)
    needles = tuple(json.dumps(tool).encode("utf-8") for tool in AGENT_TOOLS) + (b'"agentId"',)
    launches: list[str] = []
    answers: dict[str, str] = {}
    for raw, parsed in transcript_lines(path, needles):
        message = parsed.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") in AGENT_TOOLS:
                given = block.get("input")
                if (isinstance(given, dict) and isinstance(given.get("name"), str)
                        and normal_name(given["name"]) == wanted and isinstance(block.get("id"), str)):
                    launches.append(block["id"])
            elif block.get("type") == "tool_result" and isinstance(block.get("tool_use_id"), str):
                result = parsed.get("toolUseResult")
                agent = result.get("agentId") if isinstance(result, dict) else None
                if isinstance(agent, str) and SAFE_ID.match(agent):
                    answers[block["tool_use_id"]] = agent
    found: list[str] = []
    for launch in launches:
        if launch in answers and answers[launch] not in found:
            found.append(answers[launch])
    return found


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
                decoded = decode_json(raw)
                found = None if decoded is UNDECODABLE else turn_context(decoded)
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


def runs_this_guard(match: re.Match, cwd: object) -> bool:
    """`python3 <path> handoff [--base REF]` where <path>, from the hook's cwd, is this very file."""
    word = match.group(1)
    if not os.path.isabs(word):
        if not isinstance(cwd, str) or not os.path.isabs(cwd):
            return False
        word = os.path.join(os.path.realpath(cwd), word)
    return os.path.realpath(word) == os.path.realpath(__file__)


def allowed_at_hard_bound(tool: str, tool_input: dict, cwd: object = None) -> bool:
    """Past the hard bound only a bounded git command, or this file's `handoff`, may run (POLICY 2).

    The command string must fullmatch HARD_BOUND_GIT or HARD_BOUND_HANDOFF: no tokenising, no quote
    state, no shell model. The script of a handoff is identified by its real path, resolved against the
    hook's `cwd`, not by its name.
    """
    if tool != "Bash":
        return False
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return False
    if HARD_BOUND_GIT.fullmatch(command):
        return True
    handoff = HARD_BOUND_HANDOFF.fullmatch(command)
    return bool(handoff) and runs_this_guard(handoff, cwd)


# --------------------------------------------------------------------------- hook events


def pre_tool_use(payload: dict) -> int:
    tool = payload.get("tool_name") if isinstance(payload.get("tool_name"), str) else ""
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    agent = payload.get("agent_id") if isinstance(payload.get("agent_id"), str) else ""

    if agent:
        context = subagent_context(payload)
        if context is not None and context >= HARD_TOKENS \
                and not allowed_at_hard_bound(tool, tool_input, payload.get("cwd")):
            record(payload, "denied", reason="context-hard-bound", agent_id=agent, tool=tool, tokens=context)
            return deny("PreToolUse", (
                f"Context budget: this agent is at {context:,} tokens, past the hard bound of "
                f"{HARD_TOKENS:,}. Only one plain command at a time may run now, with no shell syntax: a git "
                f"command (add, commit, status, diff, log, show, push, rev-parse, branch --show-current; "
                f"`-C <dir>` is the one global option; a commit message is a double-quoted `-m \"...\"` "
                f"without `$`, a backtick, a backslash, `!` or a newline, so no heredoc) or the guard's "
                f"`handoff`. Commit what is done (`git add` and `git commit`), run `{guard_command()}` "
                f"from the worktree, and return the brief it prints as your final message. A fresh agent "
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
    transcript = main_transcript(payload)
    target_name = normal_name(target)
    by_id = bool(AGENT_ID.match(target_name))  # a spelling that folds to an id is treated as one: fails safe
    agents: list[str] = [target_name] if by_id else list(ledger.names.get(target_name, []))
    if transcript is not None and not by_id:  # launched in a way the ledger did not see, or under the same name
        agents += [found for found in transcript_agents_for_name(transcript, target) if found not in agents]
    if not agents:
        return 0  # a teammate, a session, or an agent this ledger never saw: the backstop covers it
    # Completed only on definitive evidence: a foreground Agent result that said so, or a task
    # notification in the main transcript. A SubagentStop event is not evidence: another stop hook can veto it.
    # A name that several launched agents bear is denied when ANY of them completed: the runtime picks one.
    seen = False
    agent = agents[0]
    completed = False
    for candidate in agents:
        candidate_seen, candidate_completed = ledger.knows(candidate), candidate in ledger.stopped
        if transcript is not None and not candidate_completed:
            in_transcript, candidate_completed = transcript_agent_state(transcript, candidate)
            candidate_seen = candidate_seen or in_transcript
        seen = seen or candidate_seen
        if candidate_completed:
            completed, agent = True, candidate
            break
    if completed:
        record(payload, "denied", reason="completed-agent", agent_id=agent, target=target)
        return deny("PreToolUse", (
            f"{target} has completed its assignment and is single-use (AGENTS.md section 4: one agent, "
            f"one attempt). Sending to it would resume it, carrying its whole earlier context into "
            f"every turn. Dispatch a fresh agent with a concise brief from committed state: in an "
            f"engine `tools/repair-packet.py <pr> --finding ...`, anywhere `{guard_command()}` "
            f"from the worktree. Do not paste the old agent's transcript into the brief."))
    if by_id and not seen:
        record(payload, "denied", reason="unknown-agent-id", agent_id=agent, target=target)
        return deny("PreToolUse", (
            f"{target} was not launched in this session as far as the lifecycle ledger and the session "
            f"transcript can show, so this cannot show it is still running, and a message to a completed "
            f"agent resumes it. Message a running agent by the name it was launched with, or dispatch a "
            f"fresh agent with a concise brief from committed state."))
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
            if find_key(response, "status") == "completed":
                # A foreground agent returned its final result: the one completion a hook sees for certain.
                record(payload, "stopped", agent_id=agent, source="agent-result")
        # No return: inside a subagent the launch is also a tool result the budget applies to.

    if tool == "SendMessage":
        resumed = resumed_agent(response)
        if resumed is not None:
            if not resumed:  # the result reports a resume without naming it: say who it was sent to
                target = tool_input.get("to") if isinstance(tool_input.get("to"), str) else tool_input.get("recipient")
                resumed = target.strip() if isinstance(target, str) and target.strip() else "(unnamed)"
            record(payload, "violation", reason="completed-agent-resumed", agent_id=resumed)
            return block(
                f"The runtime resumed agent {resumed}, which had completed: it is now running again "
                f"with its whole earlier context, which is the cost AGENTS.md section 4 exists to avoid. "
                f"Stop it (TaskStop), and dispatch a fresh agent with a concise brief from committed "
                f"state (in an engine `tools/repair-packet.py <pr> --finding ...`, anywhere `{guard_command()}`). "
                f"Do not message completed agents.")

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
                f"brief (`{guard_command()}`) so a fresh agent continues from the repository. "
                f"At {HARD_TOKENS:,} only git commands and `handoff` will run."))
    return 0


def hook() -> int:
    try:
        # Bytes, decoded strictly: the text layer of stdin may keep an invalid byte as a surrogate escape
        # (UTF-8 mode, the C locale), which JSON accepts inside a string, so `agent_id: "\xff"` would pass.
        payload = decode_json(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 -- a read error or bytes that are not text: the same refusal
        payload = UNDECODABLE
    if not isinstance(payload, dict):
        print(f"{GUARD_NAME}: stdin is not a JSON object, so this guard cannot tell what it was asked "
              f"and refuses (a guard that guesses is not one).", file=sys.stderr)
        return 2
    event = payload.get("hook_event_name")
    if not isinstance(event, str):
        event = ("PostToolUse" if "tool_response" in payload
                 else "PreToolUse" if "tool_name" in payload else "")
    # SubagentStop is deliberately not handled: another stop hook can veto it, so it proves nothing.
    handler = {"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use}.get(event)
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
    if matcher in UNRESTRICTED_MATCHERS:
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
        # Every tool, including ones this file cannot name (any MCP tool): only a matcher that
        # restricts nothing covers that, so a list of tool names does not, however long.
        return matcher in UNRESTRICTED_MATCHERS
    return matcher_covers(matcher, scope)


def expected_command(guard_path: str) -> str:
    """The one command a registration may carry: double quotes kept, so `$CLAUDE_PROJECT_DIR` expands."""
    return f'python3 "$CLAUDE_PROJECT_DIR/{guard_path}"'


def describe(event: str, scope: str | None) -> str:
    if scope is None:
        return event
    return f"{event} for all tools (matcher \"*\")" if scope == ALL_TOOLS else f"{event} for {scope}"


GROUP_KEYS = ("matcher", "hooks")
HOOK_KEYS = ("type", "command", "timeout")


def unsupported_keys(group: dict, hook_: dict) -> list[str]:
    """Keys of THIS GUARD'S registration that change what Claude Code does with it, naming where each sits.

    A hook group carries a matcher and its hooks, a lifecycle hook a type, a command and a timeout, and
    nothing more. Verified in Claude Code 2.1.287: `args` makes the whole command string the executable
    name, with no shell expansion, so the guard never runs; `if` skips the hook for other tools; `once`
    removes it after one run; `async` and `asyncRewake` run it in the background; `shell` changes what
    interprets it. None of them can be told apart from a working registration by the command alone.
    """
    found = [f"{key!r} on the hook group" for key in group if key not in GROUP_KEYS]
    found += [f"{key!r} on the hook" for key in hook_ if key not in HOOK_KEYS]
    return found


def own_defects(path: str, hook_: dict) -> list[str]:
    """What is wrong with the types of THIS GUARD'S hook entry: it is a command hook, its timeout (if any)
    a positive number. Its other keys are `unsupported_keys`'."""
    defects = []
    if hook_.get("type") != "command":
        defects.append(f"{path}: 'type' is {hook_.get('type')!r}, not 'command'")
    if "timeout" in hook_:
        timeout = hook_["timeout"]
        # The runtime's settings schema takes a positive number; a bool is not one, nan and inf are not usable.
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or timeout <= 0):
            defects.append(f"{path}: 'timeout' is {timeout!r}, not a positive number")
    return defects


def registration_defects(event: str, value: object) -> list[str]:
    """What is wrong with the structure that hosts everything registered under `hooks.<event>`, one line each.

    Verified in Claude Code 2.1.287: the settings schema reads the event's value as a list of groups, a
    group as an object with an optional string `matcher` and a `hooks` list, and `hooks` as a non-empty
    list of objects, each with a string `type`. A value of another type (an explicit `matcher: null` is
    one; absent is not) fails validation, and the loader drops or rejects the registration, and one
    unloadable entry can take its event's other registrations with it, so a command that looks right beside
    it never runs. That hosting structure is judged here for every group and entry under every event, this
    guard's or not. Nothing else about a neighbour is: its type may be any (`command`, `prompt`, `agent`,
    ...), and its other fields are the runtime's settings schema, the vendor's and different in each release,
    which this file does not re-implement. A neighbour that schema rejects is NOT detected (decision 0083).
    """
    where = f"hooks.{event}"
    if not isinstance(value, list):
        return [f"{where} is {type(value).__name__}, not a list of hook groups"]
    defects = []
    for index, group in enumerate(value):
        path = f"{where}[{index}]"
        if not isinstance(group, dict):
            defects.append(f"{path} is {type(group).__name__}, not an object")
            continue
        if "matcher" in group and not isinstance(group["matcher"], str):
            defects.append(f"{path}.matcher is {group['matcher']!r}, not a string (leave it out to match every tool)")
        entries = group.get("hooks")
        if not isinstance(entries, list) or not entries:
            defects.append(f"{path}.hooks is {entries!r}, not a non-empty list of objects")
            continue
        for position, entry in enumerate(entries):
            entry_path = f"{path}.hooks[{position}]"
            if not isinstance(entry, dict):
                defects.append(f"{entry_path} is {type(entry).__name__}, not an object")
            elif not isinstance(entry.get("type"), str):
                defects.append(f"{entry_path}: 'type' is {entry.get('type')!r}, not a string")
    return defects


def guard_refusals(hooks: dict, event: str, command: str) -> list[str]:
    """What is wrong with each registration under `hooks.<event>` that runs this guard (its command is
    `command`), whatever its matcher covers: keys that change how Claude Code runs it, and a type or timeout
    the runtime's schema refuses."""
    refused: list[str] = []
    entries = hooks.get(event) if isinstance(hooks.get(event), list) else []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        for position, hook_ in enumerate(entry.get("hooks") if isinstance(entry.get("hooks"), list) else []):
            if isinstance(hook_, dict) and hook_.get("command") == command:
                refused.extend(unsupported_keys(entry, hook_)
                               + own_defects(f"hooks.{event}[{index}].hooks[{position}]", hook_))
    return refused


def settings_problems(settings: object, guard_path: str = DEFAULT_GUARD_PATH) -> list[str]:
    """One line per registration `REQUIRED_HOOKS` asks for that `settings` does not carry.

    First the structure that hosts every hook under every event is checked (`registration_defects`), this
    guard's or not, and every invalid item is named with its path. An event with a defect is not wired:
    Claude Code may drop or reject its registrations. Then a registration counts when its matcher covers
    the scope, its command is exactly `expected_command(guard_path)` (compared as the string it is: parsing
    it would discard the quotes that decide whether the variable expands), it is a `command` hook with a
    positive timeout if it has one, and nothing else about THIS GUARD'S entry changes how Claude Code runs
    it: the hook group has only `matcher` and `hooks`, the hook only `type`, `command` and `timeout`. Any
    other key on it (`args`, `if`, `once`, `async`, `shell`, ...) leaves it not wired and is named. A
    background hook is among them: Claude Code does not wait for its decisions. A neighbouring hook is not
    judged beyond its hosting structure: it may be of any type and carry any key.
    """
    if not isinstance(settings, dict):
        return ["the settings are not a JSON object"]
    command = expected_command(guard_path)
    problems = []
    if settings.get("disableAllHooks") is True:
        problems.append("`disableAllHooks` is true, so no hook runs, this guard included")
    hooks = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}
    required_events = {event for event, _, _ in REQUIRED_HOOKS}
    unloadable: set[str] = set()
    for event, value in hooks.items():
        defects = registration_defects(str(event), value)
        if defects:
            unloadable.add(event)
            effect = f", so {GUARD_NAME} may not run" if event in required_events else ""
            problems.append(f"not wired: {event} has registrations Claude Code may drop or reject{effect}: "
                            f"{'; '.join(defects)} (a group has an optional string matcher and a non-empty "
                            f"list of hook objects, each with a string type)")
    for event, scope, why in REQUIRED_HOOKS:
        if event in unloadable:
            continue
        # Every registration that runs this guard must be valid: one invalid registration of it means not wired,
        # whatever else is registered, and wherever its matcher points.
        found = False
        refused = guard_refusals(hooks, event, command)
        entries = hooks.get(event) if isinstance(hooks.get(event), list) else []
        for entry in entries:
            if not isinstance(entry, dict) or not covers(entry.get("matcher"), scope):
                continue
            for hook_ in entry.get("hooks") if isinstance(entry.get("hooks"), list) else []:
                if isinstance(hook_, dict) and hook_.get("command") == command and not (
                        unsupported_keys(entry, hook_) or own_defects("", hook_)):
                    found = True
        if found and not refused:
            continue
        if refused:
            background = [key for key in BACKGROUND_KEYS if any(f"'{key}'" in item for item in refused)]
            tail = ("it runs in the background, so its decisions are not enforced; it must run in the "
                    "foreground" if background else
                    "a key or type Claude Code reads changes how it runs, so it may not enforce")
            problems.append(f"not wired: {describe(event, scope)} runs {GUARD_NAME} with {'; '.join(refused)}: "
                            f"{tail} (a group has only {', '.join(GROUP_KEYS)}; a hook only "
                            f"{', '.join(HOOK_KEYS)} with type 'command'), needed to {why}")
        else:
            problems.append(f"missing: {describe(event, scope)} does not run {GUARD_NAME} as exactly "
                            f"`{command}`, needed to {why}")
    for event in hooks:
        if event in required_events or event in unloadable:
            continue
        refused = guard_refusals(hooks, event, command)
        if refused:
            problems.append(f"not wired: {event} runs {GUARD_NAME} with {'; '.join(refused)}: every registration "
                            f"of the guard must be valid (a group has only {', '.join(GROUP_KEYS)}; a hook only "
                            f"{', '.join(HOOK_KEYS)} with type 'command')")
    return problems


def cmd_check_settings(args: argparse.Namespace) -> int:
    try:
        text = Path(args.path).read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"{args.path}: cannot be read ({error})", file=sys.stderr)
        return 1
    settings = decode_json(text)
    if settings is UNDECODABLE:
        print(f"{args.path}: cannot be read as JSON settings", file=sys.stderr)
        return 1
    problems = settings_problems(settings, args.guard_path)
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
    """Parsed lines of `path` that contain any of `needles`, in file order. Streaming; a line that cannot be decoded for any reason is skipped."""
    try:
        with open(path, "rb") as handle:
            for raw in handle:
                if any(needle in raw for needle in needles):
                    parsed = decode_json(raw)
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
    files = sorted(directory.glob("*.jsonl")) if directory is not None and directory.is_dir() else []
    if not files:
        print(f"guard ledger: none at {directory if directory is not None else 'any usable location'}")
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
    if counted and not args.events:
        print(f"(--events lists the {len(counted)} resume events, one line each)")
    if counted and args.events:
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
    check.add_argument("--guard-path", default=DEFAULT_GUARD_PATH,
                       help="where the guard sits under $CLAUDE_PROJECT_DIR (default: the engine's)")
    measure = sub.add_parser("measure", help="telemetry from Claude Code transcripts and the guard ledger")
    measure.add_argument("--projects-dir", default=None, help="default ~/.claude/projects")
    measure.add_argument("--match", default=None, help="regex over project directory names")
    measure.add_argument("--ledger-dir", default=None, help="default: the ledger directory this guard writes")
    measure.add_argument("--events", action="store_true", help="also list every resume event (one line each)")
    return parser


def main(argv: list[str]) -> int:
    if not argv:
        return hook()
    args = build_parser().parse_args(argv)
    return {"handoff": cmd_handoff, "check-settings": cmd_check_settings, "measure": cmd_measure}[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
