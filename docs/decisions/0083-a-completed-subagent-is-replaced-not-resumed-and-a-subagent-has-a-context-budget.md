# 0083 — A completed subagent is replaced, not resumed, and a subagent has a context budget

## Status

Accepted — 2026-10-15, on the owner's (brandonifco's) instruction of that date to implement and enforce
the single-use subagent policy. Implements
[#676](https://github.com/brandonifco/rules-factory/issues/676). Builds on the rule of
[#465](https://github.com/brandonifco/rules-factory/issues/465), "one agent, one attempt"
(`AGENTS.md` §4 of the rails, [0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md)),
and gives it a check. Adds one managed rail, `.claude/hooks/agent-lifecycle-guard.py` (recipe 1),
and changes three others, decision [0018](0018-every-file-the-factory-writes-has-one-owner.md):
`.claude/settings.json` (recipe 1 → 2), `AGENTS.md` (33 → 34) and `docs/agent-team.md` (11 → 12);
`CLAUDE.md` (1 → 2) gains a table row. Changes no engine-owned file.

## Context

`AGENTS.md` §4 says a completed agent is never resumed: a blocking review finding starts a fresh
attempt from the repository, because a resumed agent pays for its whole earlier conversation on every
turn. Nothing enforced it, and the orchestrators broke it.

**Evidence** (Claude Code transcripts under `~/.claude/projects`, rules ecosystem projects,
2026-10-15; `agent-lifecycle-guard.py measure` recomputes it from the same record):

- 502 subagents; 96 were resumed after returning their final result, 169 times in all, almost
  always to hand a review finding back to the implementer that wrote the code.
- 29.2% of every token those subagents processed (2.27B of 7.77B) was spent in post-resume turns;
  20.8% (1.61B) was a resumed agent re-reading the context of its earlier assignment, beyond what a
  fresh agent's first turn carried. (The second figure is an estimate of what a fresh agent would not
  have carried, not a measured saving.)
- First-assignment peak context: p50 157k, p75 211k, p90 284k, p95 348k tokens.

**The boundary is visible to a hook** (verified in Claude Code 2.1.287). `SendMessage` resolves its
target to a running task (result "Message queued for delivery to X at its next tool round") or to a
stopped or evicted one, which it resumes (`{"success":true,"message":"Resuming agent X",
"resumedAgentId":"a..."}`). `PreToolUse` sees `tool_name` and `tool_input` and, inside a subagent,
`agent_id`; `PostToolUse` of the `Agent` tool sees the new agent's `agentId` and a `tool_response.status`
(`async_launched`, or `completed` when a foreground agent returned its final result). The session's main
transcript (`transcript_path`, the same file inside a subagent) records a task notification when an agent
stops, and records it one way (verified in a Claude Code 2.1.287 transcript): a `queue-operation` record
with `"operation": "enqueue"` whose `content` is a string that starts with `<task-notification>` and holds
`<task-id>AGENT_ID</task-id>` and `<status>STATUS</status>`. The same text may also be appended inside a
`tool_result`, which is only text a tool returned. A subagent's message to the main session is enqueued
wrapped as `<agent-message from="...">`, so it cannot start with `<task-notification>`. The transcript
also holds the `Agent` tool_use (`input.name`) and its result (`toolUseResult.agentId`). A subagent's own transcript
records the usage of each turn. What a hook does not see is the runtime's resolution of a name:
`PreToolUse` runs before it.

**`SubagentStop` is not evidence of completion.** It can be vetoed by another stop hook
(`{"decision":"block"}`), in which case the runtime keeps the agent running. A guard that recorded
"stopped" on receiving it would later refuse a message to an agent still doing its assignment (found in
the final review of #677). The guard therefore neither registers for the event nor handles it.

## Decision

1. **A completed agent is replaced.** A `PreToolUse` guard refuses a `SendMessage` to a subagent with
   definitive evidence of completion: (a) a `PostToolUse` of `Agent` whose `tool_response.status` is
   `completed` (a foreground agent returned), recorded in the ledger, or (b) a task notification for it
   with any status but `running`, found by streaming the main transcript and parsing only the lines that
   hold the agent id, and read from one kind of record only: a `queue-operation` `enqueue` whose `content`
   is a string starting with `<task-notification>`, with the task id and the status taken from that
   leading block (up to its first `</task-notification>`) and from no other string of any record. A
   notification quoted in a `tool_result` (an agent that read a log or a file), in an `<agent-message>`, or
   past the leading block is not evidence (found in the review at 9df6565: every string of every record was
   searched). It resolves a name to every id the ledger recorded and the main transcript shows launched
   under it, comparing names under one normaliser applied to both sides wherever a name is matched (NFKC, control and format characters of Unicode categories Cc and Cf dropped except those the runtime reads as whitespace, `str.lower()`, whitespace runs turned into one `-`, trimmed): the runtime resolves a target under its own normalisation (read in Claude Code 2.1.287), so `WORKER`, ` worker `, a full-width `ｗｏｒｋｅｒ` and `worker` followed by a zero-width space reach the agent launched as `worker`, and `review agent` the one launched as `review-agent`; the normaliser is that equivalence and no wider: `casefold()` merged `worker-ß` with `worker-ss`, which the runtime keeps apart, and the running one masked the completed one. A name that still resolves to more than one launched agent is denied when any of them has completed, because the runtime picks one of them and a message to a completed one resumes it (found in the review at 5ad72d4: exact comparison let `Worker` through; in the review at 4ed9085: control and format characters, and whitespace against `-`, let a completed agent be reached; in the review at ff51852: casefold, and the latest agent under a name hiding an earlier completed one). It also reads a target as the runtime's other addresses (Claude Code 2.1.287; found in the review at f3a062c, where `worker [7cedb0]` and `wor` reached a completed `worker` unrefused): a displayed address `name [ref]` (six hex digits) resolves by the name and by the ref, which is the `pin.ref` the runtime returned for that agent in an earlier `SendMessage` result in the main transcript; and the normalised target, as a prefix, resolves to every launched agent whose normalised name it begins. The guard denies when any of them has completed. A target that is a prefix only of running agents' names is allowed, and so is a name that matches nothing launched. It treats an id (`a` and 16 hex digits) as itself, and refuses an id neither the
   ledger nor the transcript saw launched, because that cannot be shown to be running. A message to a running agent is a continuation of its assignment and goes
   through, as does one to `main`. The refusal says what to do: dispatch a fresh agent with a concise
   brief from committed state (`tools/repair-packet.py <pr> --finding ...` in an engine, the guard's
   `handoff` anywhere).
2. **A resume the guard could not prevent is detected.** A `PostToolUse` backstop reads the
   `SendMessage` result; if the runtime reports it resumed an agent, the guard records a violation and
   tells the model to stop that agent and dispatch a fresh one. It recognises every form the runtime reports a resume in (Claude Code 2.1.287), not only the one that carries `resumedAgentId`. It reads the response's `message` string and the keys `resumedAgentId` and `inlineHandback`, and nothing else: not `pin` (`{id, name, ref}`, whose `name` is the recipient's display name) or any other field (found in the review at f3a062c: `pin.name: "Resumed agent"` on a delivery to a running agent was reported as a resume). A delivery is exempt only when the whole message is `Message queued for delivery to <anything> at its next tool round.` or `Message queued for the main conversation's next turn.`; a message that ends ` is already waking; message queued for its next tool round (not delivered if the agent turns out to have been stopped).` is a resume, checked before the exemption, so a recipient named `Message queued worker` hides nothing.

**Threat model.** The guard stops an orchestrator's habit of resuming a finished agent. It is accident prevention, not a security boundary against an orchestrator that chooses agent names to imitate the runtime's own response text. A finding that needs such a crafted display name is non-blocking and documented here, not chased.
3. **Within one assignment a subagent has a context budget**, read from its own transcript. At
   `CHECKPOINT_TOKENS` = 210,000 it is told once to commit, keep to its assignment, and return a
   handoff brief if the remaining work is separable. At `HARD_TOKENS` = 350,000 every tool is refused
   except a bounded `git` command and the guard's `handoff`: it commits and returns, and a fresh agent
   continues. A Bash command is not parsed at all: the whole
   string must fullmatch a strict regular grammar, and anything else is refused. A word is made of
   `[A-Za-z0-9_./:@+=,-]` (no `::`, so no `ext::` transport) and starts with `-` only when it is one of the
   subcommand's allowlisted options. The two forms are `git [-C <dir>] <subcommand> ...` with `add` (`-A`,
   `--all`, `-u`, `--`), `commit` (`-a`, `--all`, `-m "<message>"`), `status` (`-s`, `--short`,
   `--porcelain`, `-b`), `diff` (`--stat`, `--name-status`, `--cached`, `--staged`), `log` (`--oneline`,
   `--stat`, `-n`, `-<digits>`), `show` (`--stat`, `--name-status`), `push` (`-u`, `--set-upstream`),
   `rev-parse` (`--abbrev-ref`, `--show-toplevel`) or `branch --show-current`; and
   `python3 <path> handoff [--base REF]` where `<path>`, resolved against the hook's `cwd`, has the real path
   of the running guard file. A commit message is a double-quoted string with no `$`, backtick, backslash,
   `!`, double quote or newline. Every other character anywhere refuses the command: `$ ' ; & | < > # ( ) { }
   * ? ~`, a backslash, `!`, a backtick, a newline. So there is no `cd`, no `&&`, no redirect, no comment, no
   alias or `-c`, and no `$'...'` or `$(...)`: nothing is left to a shell to read differently from the guard.
   **A commit message written as a heredoc, or with `$(...)`, is refused past the bound by design**; the agent
   writes a plain one. Two earlier designs, a tokenizer and then a quote-aware scanner, were each bypassed by
   a quoting form the reader did not model (`$'...'` in the review at 9df6565); the grammar replaces the
   reader instead of extending it.
4. **A handoff is a brief from committed repository state, never a transcript.** `handoff` prints the
   branch, the head commit and its subject, the commits and files since the base, and the upstream
   state, and refuses a worktree with uncommitted work, because that would not survive the handoff.
5. **A missing or stale guard is detected.** `factory rails --check` and `tools/agent-doctor.py`
   report the rail bytes through the existing managed-file comparison, and the doctor reports a
   `WRONG` row when `.claude/settings.json` does not wire the guard, by running the guard's own
   `check-settings`, so the required registrations are stated once (`REQUIRED_HOOKS`: `PreToolUse` for
   `SendMessage`, `PreToolUse` and `PostToolUse` for every tool). A registration counts only when its command
   is exactly `python3 "$CLAUDE_PROJECT_DIR/<REL>"` (compared as the string it is, so the double quotes that
   let the variable expand are kept; `<REL>` is `--guard-path`, by default the engine's
   `.claude/hooks/agent-lifecycle-guard.py`, and this repository's own settings use the path of the file
   the rails are emitted from), it is not a background hook (`"async": true` or `"asyncRewake": true`,
   whose decisions Claude Code does not wait for), and "all tools" only when its matcher is absent, empty
   or `*`: a list of tool names covers those tools and no other, however long. The hook group that carries it
   has only the keys `matcher` and `hooks`, and the hook only `type` (which must be `command`), `command`
   and `timeout`; any other key leaves it not wired and is named. The structure that hosts every hook is checked for every group and entry under every event in the file, this guard's or not: an event's value is a list, each group an object whose `matcher`, when present, is a string (an explicit `null`, a number or a list is not one: Claude Code 2.1.287 drops or rejects the registration) and whose `hooks` is a non-empty list of objects, each with a string `type`. One defect in that structure anywhere leaves the event not wired, and every invalid item is named with its path, because one unloadable entry can take its event's other registrations with it (found in the review at 5ad72d4). A neighbouring hook may be of any type (`command`, `prompt`, `agent`, ...) and is not validated beyond that: its other fields are the runtime's settings schema, the vendor's, which changes per release and which this checker does not re-implement (rounds 6 and 7 of the review showed that doing so does not converge; the review at 4ed9085 found a `prompt` hook reported as missing wiring). Only this guard's own entries are held to their keys and types, every one of them: one invalid registration of the guard (a `timeout` of `"bad"`, a `type` of `not-a-hook-type`, a stray key) leaves it not wired and is named, however many valid ones sit beside it (found in the review at ff51852), and a neighbour the runtime rejects is not detected (see the table). Claude Code 2.1.287 reads `args` as direct
   execution (the whole command string becomes the executable name, so the guard never runs), `if` as a
   condition that skips the hook for other tools, `once` as removal after one run, and `async`,
   `asyncRewake` and `shell` as other ways of running it; a check on the command string alone passes all of
   them (the review at 9df6565 reproduced three).
6. **State is kept outside any repository.** One append-only JSONL ledger per session in
   `$RULES_AGENT_LEDGER_DIR`, else `${XDG_STATE_HOME:-~/.local/state}/rules-agent-lifecycle/`. A
   location that is relative, or inside a git work tree (a `.git` in it or any directory above it,
   links followed), is refused before anything is created: a refused `$RULES_AGENT_LEDGER_DIR` falls
   back to the default location, and if the default is refused too there is no ledger, so nothing is
   written and the `SendMessage` check fails closed for an id it cannot show was launched. The ledger
   file is opened with `O_NOFOLLOW`, and one that is a symbolic link is refused (nothing written, nothing
   read): the directory check alone let a link in an outside directory carry the append into a repository.

**The thresholds, and why.** They are the measured peaks of a first assignment: the checkpoint is
the p75 (211k, rounded down) and the hard bound the p95 (348k, rounded up). The checkpoint is where
three in four assignments have already finished, so the note reaches only the long tail; the hard
bound is where only one in twenty assignments would still be working, so stopping there costs little
and a fresh agent is cheaper than another turn in a context that large. They are counts of tokens,
not a judgement about any one agent, and `measure` recomputes the percentiles so a later change to
them is argued from the record and not from this paragraph. The guard has a `POLICY_VERSION`.

**What the guard covers and does not.**

| | Status | Where |
|---|---|---|
| A `SendMessage` to a completed subagent is refused | **Mechanically enforced** (Claude Code), on definitive evidence only: a foreground `Agent` result of status `completed`, or a task notification enqueued in the main transcript | `PreToolUse` on `SendMessage`; tests: completed by foreground result, by an enqueued notification (any status but `running`), name resolved from the transcript, a name matched under the normaliser (`WORKER`, ` worker `, `ｗｏｒｋｅｒ` for `worker`; a running agent stays reachable under each); a notification quoted in a `tool_result`, in an `<agent-message>` enqueue, or past the leading block does not complete a running agent |
| A task notification typed as a user prompt | **Counts as evidence, trusted**: a user prompt is enqueued as a `queue-operation` and can start with `<task-notification>`; the user is trusted, and the guard cannot tell the prompt from the runtime's own record | |
| A `SubagentStop` event | **Not evidence, not registered**: another stop hook can veto it and the agent keeps running | test: a delivered `SubagentStop` leaves the agent messageable; no shipped settings register it |
| An agent that stopped without a foreground result or a notification (a notification the runtime did not write, an unreadable transcript) | **Not covered**: it looks running, so a message is allowed and the backstop catches a resume | |
| A `SendMessage` addressed as `name [ref]` or by a name prefix reaches the agent the runtime resolves it to | **Mechanically enforced**, fails safe: refused when any agent the address can reach has completed. The ref comes from a `pin` recorded in the main transcript | `PreToolUse` on `SendMessage`; tests: a completed `worker` is refused for `worker [<its pinned ref>]`, `worker [abcdef]` (by name), `anything [<its pinned ref>]` (by ref) and the prefixes `wor`, `w`, `WOR`; a prefix of running agents only, and a name matching nothing launched, are allowed |
| A ref the transcript never recorded in a `pin`, for a name that matches nothing | **Not covered**: allowed, and caught only after the fact by the backstop | |
| A display name crafted to imitate the runtime's response text | **Not covered**: the guard stops a habit, it is not a security boundary against the orchestrator naming its own agents | |
| A `SendMessage` to an id never launched in the session is refused | **Mechanically enforced**, fail closed | same; test: unknown id denied |
| A resume the runtime reports is detected and the model told to stop it | **Mechanically detected**, after the fact | `PostToolUse` on `SendMessage`, for the five forms Claude Code 2.1.287 reports a resume in (a result that is a dict, JSON text or a list of text blocks): the key `resumedAgentId` or `inlineHandback`, or a message that starts `Resuming agent ` or `Resumed agent`, or, in a message that is not one of the two whole delivery forms, contains one of the runtime's fixed phrases `" was resumed but`, `" was not running; resumed it as an in-process teammate` or ` is already waking; message queued for its next tool round`. The display name, which keeps its spaces and quotes, is never pattern-matched (found in the review at ff51852: `review agent is already waking...` was missed). Only `message`, `resumedAgentId` and `inlineHandback` are read, never `pin` or another field. The two whole-message delivery forms (`Message queued for delivery to <anything> at its next tool round.`, `Message queued for the main conversation's next turn.`) stay silent whatever the recipient's display name says, unless the result carries `resumedAgentId` or `inlineHandback`; a message ending the runtime's closing words `... is already waking; message queued for its next tool round (not delivered if the agent turns out to have been stopped).` is a violation whatever it starts with; tests: `review agent is already waking; ...`, `Message queued worker is already waking; ...`, `Agent "say "hi" now" was resumed but ...` and `Teammate "a b" was not running; resumed it as an in-process teammate ...` are violations, a delivery to `worker was resumed but still running` is silent, a delivery whose `pin.name` is `Resumed agent` is silent, and every exact delivery form is silent |
| A subagent past 350,000 tokens may only commit and return | **Mechanically enforced** in subagents | `PreToolUse` on every tool, from the subagent's transcript; tests: every bypass found in review (comment, newline, alias `-c`, `$'...'`, `--receive-pack`, `--exec`, `$(...)` in double quotes, heredoc) is refused; `git add -A`, `git commit -m "fix: x > y \| z"`, `git push -u origin branch-name`, `git status --short` and `handoff` of this very file run; a long near-miss is refused quickly |
| What a permitted git command runs of the repository's own configuration (a commit hook, a configured external diff driver) | **Not covered**: accident prevention, not security | |
| The ledger is never inside a repository | **Mechanically enforced** | a relative or in-work-tree location is refused before it is created, and a ledger file that is a symbolic link is refused; tests: ledger location, ledger file symlink |
| A launch inside a subagent is also a tool result the context budget applies to | **Mechanically enforced** | `PostToolUse` of `Agent` records the child launch and then applies the parent's checkpoint check; test: checkpoint note on an `Agent` result |
| A missing or stale guard is detected | **Mechanically detected** | `factory rails --check` and `agent-doctor.py` (bytes); `agent-doctor.py` via `check-settings` (wiring: exact command and path, foreground, every tool); tests: a valid registration beside an invalid duplicate (`timeout: "bad"`, `type: "not-a-hook-type"`) is not wired and names it; any key beyond `matcher`/`hooks` on the group and `type`/`command`/`timeout` on this guard's hook (`args`, `if`, `once`, `async`, `shell`, ...) refused and named, a `timeout` that is not a positive number (a bool, zero, negative, a string, nan) or a `type` that is not `command` on this guard's hook refused and named, another path refused, quoting kept; a `matcher` that is `null`, a number, a list or an object, `hooks` that is not a non-empty list of objects, a hook with no string `type`, and a group or event value of the wrong type, under any event, refused with its path, while a neighbouring `prompt`, `agent`, `http` or `command` hook, one with `if`/`once`, and the primary-checkout guard leave it wired |
| A new agent launched under the name of one that has completed | **Refused by that name** (fails safe): a name that resolves to several launched agents is denied when any of them has completed. Message the new agent by its id, or give each attempt its own name | |
| A neighbouring hook the runtime's schema rejects (for example a wrong-typed field) | **Not detected by `check-settings`**: the runtime's settings schema is the vendor's and changes per release; `check-settings` holds the guard's registrations and the structure that hosts them | test: a neighbour with `args: 42`, a string `timeout` or a group key nobody reads leaves the guard reported wired (the limit, pinned) |
| A handoff refuses uncommitted work | **Mechanically enforced** by the subcommand | `handoff` |
| The orchestrator does not paste a transcript into the next brief | **Advisory** | `AGENTS.md` §4; no hook sees a brief's content |
| The checkpoint note at 210,000 tokens | **Advisory** | `additionalContext`; the agent may ignore it |
| A message by a name the ledger never saw launched (a teammate, another session, an agent launched before the guard was wired) | **Not covered**: allowed, and caught only after the fact by the backstop | |
| A subagent that returns while background work of its own is still running is woken by the runtime when that work finishes, without any `SendMessage` | **Not covered**: no tool call to refuse. Observed on 2026-10-15 while building this change: the implementer of #677 woke three times after returning, re-sent its report and changed nothing. A brief tells an agent to finish or stop its background work before it returns (advisory). The orchestrator ends repeated wakes with `TaskStop` on the finished agent (done once in #677's own history) | |
| Hooks disabled by the user (`disableAllHooks`), user-level settings | **Not covered**; `check-settings` reports `disableAllHooks` in the project file only | |
| The main session's own context | **Not covered**: `agent_id` is absent there, so no budget applies | |
| A transcript that is missing or in an unrecognised layout | **No budget verdict**: the guard neither warns nor stops | |
| JSON that cannot be decoded (a transcript line, a ledger line, a text block of a tool result: corrupt, or nested past the decoder's recursion limit) | **Skipped**, by one decoding helper that treats any failure as "not a record" and goes on with the rest; tests: a 350,000-token turn followed by a 10,000-deep line still denies; a 10,000-deep text block before a genuine `resumedAgentId` block still yields the violation; a 10,000-deep ledger line after `launched` and `stopped` records still denies the completed agent | |
| Codex `resume_agent` and `send_input` | **Not covered, unverified**; Codex is used here only as one-shot `codex exec` reviewers, which are not resumed | |
| A Bash command past the hard bound is matched against a grammar, not parsed or run by any shell model | **Accident prevention, not security**: what a permitted git command runs of the repository's own configuration is not judged. A heredoc or `$(...)` commit message, `cd`, `&&` and a guard path outside the plain characters are refused by design | |
| An internal error in the guard | **Fails open**, with a message on stderr; malformed stdin, including stdin nested too deeply to parse and stdin that is not UTF-8 (the bytes are decoded strictly before the JSON, so an invalid byte inside a string is refused, not kept as a surrogate escape), fails closed (exit 2) | |

## Alternatives considered

- **Keep the rule on the orchestrator's word.** That is the state the evidence measures: 96 of 502
  agents resumed.
- **Refuse every `SendMessage` to a subagent.** It would also stop a legitimate continuation of a
  running assignment, which the runtime queues at the agent's next tool round and which costs nothing
  extra.
- **Resolve the runtime's own routing in the hook.** The hook runs before the runtime resolves the
  name and sees only the task state the ledger recorded; the ledger is the evidence it has.
- **A token limit in the harness instead of a hook.** None is exposed; the transcript is the record
  the cost claims came from, so the budget reads it.
- **Time limits.** Cost follows context, not wall clock.
- **Record "stopped" when `SubagentStop` fires.** It was the first design. A stop hook that blocks the
  event keeps the agent running, so the record is false and the guard would refuse a legitimate
  continuation; only a returned foreground result and a task notification are definitive.

## Consequences

- Every produced engine receives `.claude/hooks/agent-lifecycle-guard.py` on its next `factory
  produce`; one that edited `.claude/settings.json` by hand is refused, as for any managed file, until
  `--adopt` or `--reset` settles it. An engine that adopts the old settings is reported by the doctor
  as not wiring the guard.
- rules-factory's own sessions run the same file from `tools/factory/recipe/rails/hooks/`, with no
  copy, registered in `.claude/settings.json` beside the `SessionStart` hook.
- The ledger and the transcripts are read on every tool call inside a subagent. The transcript is read
  from its tail, a bounded window that grows only when the last turn is not in it.
- The guard is accident prevention in Claude Code sessions, in the sense of the primary-checkout
  guard: it stops the unintended resume, not a determined one.
