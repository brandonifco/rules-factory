#!/usr/bin/env python3
"""The agent lifecycle guard (#676, decision 0083): a completed subagent is replaced, not resumed.

The guard is a hook, so every test runs it the way Claude Code does: as a subprocess, one JSON
event on stdin, the answer on stdout. The payloads have the shapes verified in Claude Code 2.1.287
(see the guard's docstring). Every test uses its own temporary directory for the ledger and the
transcripts, and removes it.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import shutil
import unittest

sys.dont_write_bytecode = True

TOOLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
GUARD = os.path.join(FACTORY, "recipe", "rails", "hooks", "agent-lifecycle-guard.py")
RAILS_SETTINGS = os.path.join(FACTORY, "recipe", "rails", "settings.json")
OWN_SETTINGS = os.path.join(REPO, ".claude", "settings.json")

sys.path.insert(0, FACTORY)
import ownership  # noqa: E402

CHECKPOINT = 210_000
HARD = 350_000
SESSION = "11111111-2222-3333-4444-555555555555"
WORKER = "a0123456789abcdef"      # "a" + 16 hex, as the runtime issues them
OTHER = "afedcba9876543210"
STRANGER = "a1111111111111111"


def run_guard(*args, stdin=None, cwd=None, **environment):
    env = {key: value for key, value in os.environ.items()
           if key not in ("RULES_AGENT_LEDGER_DIR", "XDG_STATE_HOME")}
    env.update(environment)
    return subprocess.run([sys.executable, GUARD, *args], input=stdin, capture_output=True, text=True,
                          cwd=cwd, env=env, check=False)


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lifecycle-guard-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.ledger = os.path.join(self.tmp, "ledger")

    # -- events -------------------------------------------------------------------------------

    def event(self, name, **fields):
        return {"session_id": SESSION, "cwd": self.tmp, "permission_mode": "default",
                "hook_event_name": name, **fields}

    def hook(self, payload):
        """(exit code, parsed stdout or None, stderr) of one hook invocation."""
        done = run_guard(stdin=json.dumps(payload), RULES_AGENT_LEDGER_DIR=self.ledger)
        out = json.loads(done.stdout) if done.stdout.strip() else None
        return done.returncode, out, done.stderr

    def launched(self, agent_id, name=None, response=None):
        fields = {"tool_name": "Agent", "tool_input": {"description": "d", "prompt": "p", **({"name": name} if name else {})},
                  "tool_response": response or {"agentId": agent_id, "status": "async_launched"}}
        self.assertEqual(self.hook(self.event("PostToolUse", **fields))[:2], (0, None))

    def stopped(self, agent_id):
        payload = self.event("SubagentStop", agent_id=agent_id, agent_type="general-purpose",
                             agent_transcript_path="/nonexistent/agent.jsonl", last_assistant_message="done")
        self.assertEqual(self.hook(payload)[:2], (0, None))

    def send(self, to, **extra):
        return self.hook(self.event("PreToolUse", tool_name="SendMessage", tool_use_id="toolu_1",
                                    tool_input={"to": to, "message": "fix the finding", **extra}))

    def assertDenied(self, result, *needles):
        code, out, _ = result
        self.assertEqual(code, 0)
        self.assertIsNotNone(out, "the guard let it through")
        decision = out["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        for needle in needles:
            self.assertIn(needle, decision["permissionDecisionReason"])

    def assertAllowed(self, result):
        self.assertEqual(result[:2], (0, None), result)

    def ledger_records(self):
        names = os.listdir(self.ledger)
        self.assertEqual(len(names), 1, names)
        with open(os.path.join(self.ledger, names[0]), encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    # -- transcripts --------------------------------------------------------------------------

    def transcript(self, agent_id, contexts, padding=0):
        """A main transcript path and, beside it, the subagent's transcript with one turn per context."""
        project = os.path.join(self.tmp, "projects", "-work-rules-x")
        main = os.path.join(project, f"{SESSION}.jsonl")
        sub = os.path.join(project, SESSION, "subagents", f"agent-{agent_id}.jsonl")
        os.makedirs(os.path.dirname(sub), exist_ok=True)
        open(main, "a", encoding="utf-8").close()
        with open(sub, "w", encoding="utf-8") as handle:
            for index, context in enumerate(contexts):
                handle.write(json.dumps(assistant_line(f"msg_{index}", context, 7)) + "\n")
                if padding:
                    handle.write(json.dumps({"type": "user", "message": {"content": "x" * padding}}) + "\n")
        return main

    def in_subagent(self, name, agent_id, contexts, tool, tool_input, padding=0, **extra):
        return self.event(name, agent_id=agent_id, agent_type="general-purpose",
                          transcript_path=self.transcript(agent_id, contexts, padding),
                          tool_name=tool, tool_input=tool_input, tool_use_id="toolu_2", **extra)


def assistant_line(message_id, context, output, stamp="2026-10-15T10:00:00.000Z"):
    # Spread the context over the three fields the runtime reports, as a real turn is.
    return {"type": "assistant", "timestamp": stamp,
            "message": {"id": message_id, "role": "assistant",
                        "usage": {"input_tokens": 3, "cache_read_input_tokens": context - 3 - 1000,
                                  "cache_creation_input_tokens": 1000, "output_tokens": output}}}


class TestACompletedAgentIsNotMessaged(GuardCase):
    def test_a_completed_agent_is_refused_by_name_and_by_id(self):
        self.launched(WORKER, name="implementer")
        self.stopped(WORKER)
        self.assertDenied(self.send("implementer"), "completed its assignment", "single-use", "repair-packet.py")
        self.assertDenied(self.send(WORKER), "completed its assignment")

    def test_the_refusal_is_recorded_for_the_telemetry(self):
        self.launched(WORKER, name="implementer")
        self.stopped(WORKER)
        self.send("implementer")
        denied = [r for r in self.ledger_records() if r["event"] == "denied"]
        self.assertEqual([(r["reason"], r["agent_id"]) for r in denied], [("completed-agent", WORKER)])

    def test_a_foreground_agent_that_stopped_before_its_id_was_returned_is_still_completed(self):
        # SubagentStop fires while the Agent tool is still running; its PostToolUse comes after.
        self.stopped(WORKER)
        self.launched(WORKER, name="reviewer", response={"agentId": WORKER, "status": "completed"})
        self.assertDenied(self.send("reviewer"), "completed its assignment")

    def test_a_running_agents_continuation_is_allowed_by_name_and_by_id(self):
        self.launched(WORKER, name="implementer")
        self.assertAllowed(self.send("implementer"))
        self.assertAllowed(self.send(WORKER))

    def test_a_running_agent_is_not_confused_with_a_completed_one(self):
        self.launched(WORKER, name="implementer")
        self.launched(OTHER, name="reviewer")
        self.stopped(OTHER)
        self.assertAllowed(self.send("implementer"))
        self.assertDenied(self.send("reviewer"), "completed")

    def test_a_name_reused_for_a_fresh_agent_reaches_the_fresh_one(self):
        self.launched(WORKER, name="implementer")
        self.stopped(WORKER)
        self.launched(OTHER, name="implementer")
        self.assertAllowed(self.send("implementer"))

    def test_main_is_always_allowed(self):
        self.launched(WORKER, name="implementer")
        self.stopped(WORKER)
        self.assertAllowed(self.send("main"))

    def test_an_id_never_launched_is_refused_because_it_cannot_be_shown_running(self):
        self.assertDenied(self.send(STRANGER), "not launched in this session", "cannot show it is still running")

    def test_a_name_the_ledger_never_saw_is_allowed(self):
        self.assertAllowed(self.send("some-teammate"))

    def test_the_target_falls_back_to_recipient(self):
        self.launched(WORKER, name="implementer")
        self.stopped(WORKER)
        payload = self.event("PreToolUse", tool_name="SendMessage",
                             tool_input={"recipient": "implementer", "message": "m"})
        self.assertDenied(self.hook(payload), "completed")

    def test_a_tool_other_than_sendmessage_is_not_judged(self):
        self.launched(WORKER, name="implementer")
        self.stopped(WORKER)
        payload = self.event("PreToolUse", tool_name="Bash", tool_input={"command": "echo implementer"})
        self.assertAllowed(self.hook(payload))

    def test_sessions_do_not_share_a_ledger(self):
        self.launched(WORKER, name="implementer")
        self.stopped(WORKER)
        other = self.event("PreToolUse", tool_name="SendMessage", tool_input={"to": "implementer", "message": "m"})
        other["session_id"] = "another-session"
        self.assertAllowed(self.hook(other))

    def test_the_ledger_is_written_where_it_is_told_and_by_default_under_xdg_state(self):
        self.launched(WORKER, name="implementer")
        self.assertEqual([r["event"] for r in self.ledger_records()], ["launched"])
        state = os.path.join(self.tmp, "state")
        launch = self.event("PostToolUse", tool_name="Agent", tool_input={"name": "n"},
                            tool_response={"agentId": WORKER})
        done = run_guard(stdin=json.dumps(launch), XDG_STATE_HOME=state)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(os.listdir(os.path.join(state, "rules-agent-lifecycle")), [f"{SESSION}.jsonl"])

    def test_a_hostile_session_id_cannot_leave_the_ledger_directory(self):
        launch = self.event("PostToolUse", tool_name="Agent", tool_input={}, tool_response={"agentId": WORKER})
        launch["session_id"] = "../../escape"
        self.assertEqual(self.hook(launch)[:2], (0, None))
        self.assertEqual(os.listdir(self.tmp).count("escape.jsonl"), 0)
        (name,) = os.listdir(self.ledger)
        self.assertNotIn("/", name)

    def test_malformed_stdin_fails_closed(self):
        for stdin in ("", "not json", "[1, 2]", "null"):
            with self.subTest(stdin=stdin):
                done = run_guard(stdin=stdin, RULES_AGENT_LEDGER_DIR=self.ledger)
                self.assertEqual(done.returncode, 2, done.stdout)
                self.assertIn("refuses", done.stderr)


class TestAResumeTheRuntimeReportsIsCaught(GuardCase):
    def resumed(self, response):
        return self.hook(self.event("PostToolUse", tool_name="SendMessage", tool_use_id="toolu_3",
                                    tool_input={"to": "implementer", "message": "m"}, tool_response=response))

    def assertBlocked(self, result):
        code, out, _ = result
        self.assertEqual(code, 0)
        self.assertEqual(out["decision"], "block")
        self.assertIn(WORKER, out["reason"])
        self.assertIn("TaskStop", out["reason"])
        self.assertIn("fresh agent", out["reason"])

    def test_resumedagentid_in_the_result_is_a_violation(self):
        self.assertBlocked(self.resumed({"success": True, "message": f"Resuming agent {WORKER}",
                                         "resumedAgentId": WORKER}))
        (violation,) = [r for r in self.ledger_records() if r["event"] == "violation"]
        self.assertEqual((violation["reason"], violation["agent_id"]), ("completed-agent-resumed", WORKER))

    def test_the_result_as_json_text_or_as_text_blocks_is_read_the_same(self):
        as_dict = {"success": True, "message": f"Resuming agent {WORKER}", "resumedAgentId": WORKER}
        for response in (json.dumps(as_dict), [{"type": "text", "text": json.dumps(as_dict)}],
                         [{"type": "text", "text": f"Resuming agent {WORKER}"}], f"Resuming agent {WORKER}"):
            with self.subTest(response=response):
                self.assertBlocked(self.resumed(response))

    def test_a_queued_message_is_silent(self):
        for response in ({"success": True, "message": "Message queued for delivery to implementer at its next tool round."},
                         "Message queued for delivery to implementer at its next tool round.",
                         [{"type": "text", "text": "Message queued for delivery to main"}]):
            with self.subTest(response=response):
                self.assertAllowed(self.resumed(response))
        self.assertFalse(os.path.exists(self.ledger), "a queued message must leave no violation behind")


class TestTheContextBudget(GuardCase):
    def post(self, agent_id, context, **extra):
        return self.hook(self.in_subagent("PostToolUse", agent_id, [1_000, context], "Bash",
                                          {"command": "ls"}, tool_response={"stdout": ""}, **extra))

    def test_the_checkpoint_note_fires_once_at_the_checkpoint_and_not_below(self):
        self.assertAllowed(self.post(WORKER, CHECKPOINT - 1))
        code, out, _ = self.post(WORKER, CHECKPOINT)
        self.assertEqual(code, 0)
        note = out["hookSpecificOutput"]
        self.assertEqual(note["hookEventName"], "PostToolUse")
        for needle in (f"{CHECKPOINT:,}", "Commit what is done", "do not widen", "handoff", f"{HARD:,}"):
            self.assertIn(needle, note["additionalContext"])
        self.assertAllowed(self.post(WORKER, CHECKPOINT + 5_000))   # once per agent
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"].count("Context checkpoint"), 1)
        code, again, _ = self.post(OTHER, CHECKPOINT + 5_000)       # another agent has its own
        self.assertIn("additionalContext", again["hookSpecificOutput"])

    def test_no_budget_applies_outside_a_subagent(self):
        payload = self.event("PostToolUse", tool_name="Bash", tool_input={"command": "ls"}, tool_response={},
                             transcript_path=self.transcript(WORKER, [HARD + 1]))
        self.assertAllowed(self.hook(payload))
        pre = self.event("PreToolUse", tool_name="Read", tool_input={"file_path": "/x"},
                         transcript_path=self.transcript(WORKER, [HARD + 1]))
        self.assertAllowed(self.hook(pre))

    def test_the_hard_bound_denies_every_tool_but_git_and_handoff(self):
        def at_hard(tool, tool_input, context=HARD):
            return self.hook(self.in_subagent("PreToolUse", WORKER, [1_000, context], tool, tool_input))

        for tool, tool_input in (("Read", {"file_path": "/x"}), ("Edit", {"file_path": "/x", "old_string": "a",
                                                                          "new_string": "b"}),
                                 ("Write", {"file_path": "/x", "content": "c"}), ("Grep", {"pattern": "p"}),
                                 ("SendMessage", {"to": "main", "message": "m"}),
                                 ("Bash", {"command": "make test"}), ("Bash", {"command": "git log | head"}),
                                 ("Bash", {"command": "git status\nrm -rf ."}), ("Bash", {"command": "git log > out"}),
                                 ("Bash", {"command": "git status && rm -r x"}),
                                 # The word after an operator is itself a git command: only the
                                 # operator tells these from two allowed commands.
                                 ("Bash", {"command": "git log | git commit -m x"}),
                                 ("Bash", {"command": "git log > git"}), ("Bash", {"command": "git log || git gc"}),
                                 ("Bash", {"command": "git status & git gc"})):
            with self.subTest(tool=tool, tool_input=tool_input):
                self.assertDenied(at_hard(tool, tool_input), f"{HARD:,}", "git command", "handoff")
        for command in ('git commit -m "Fix it | not > that"',
                        'cd /work/tree && git add -A && git commit -m "m"',
                        'git commit -m "$(cat <<\'EOF\'\nsubject\n\nCo-Authored-By: A <a@example.invalid>\nEOF\n)"',
                        'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/agent-lifecycle-guard.py" handoff',
                        "python3 tools/factory/recipe/rails/hooks/agent-lifecycle-guard.py handoff --base origin/main"):
            with self.subTest(command=command):
                self.assertAllowed(at_hard("Bash", {"command": command}))
        # Just below the bound nothing is refused.
        self.assertAllowed(at_hard("Read", {"file_path": "/x"}, context=HARD - 1))

    def test_the_denial_is_recorded(self):
        self.hook(self.in_subagent("PreToolUse", WORKER, [HARD], "Read", {"file_path": "/x"}))
        (denied,) = [r for r in self.ledger_records() if r["event"] == "denied"]
        self.assertEqual((denied["reason"], denied["agent_id"], denied["tool"], denied["tokens"]),
                         ("context-hard-bound", WORKER, "Read", HARD))

    def test_the_context_is_input_plus_cache_read_plus_cache_creation_of_the_latest_turn(self):
        # An earlier, larger turn does not count: the latest is the context the next turn pays for.
        payload = self.in_subagent("PreToolUse", WORKER, [HARD + 50_000, HARD - 1], "Read", {"file_path": "/x"})
        self.assertAllowed(self.hook(payload))

    def test_the_latest_turn_is_found_past_a_large_tail_of_other_lines(self):
        payload = self.in_subagent("PreToolUse", WORKER, [HARD], "Read", {"file_path": "/x"}, padding=400_000)
        self.assertDenied(self.hook(payload), f"{HARD:,}")

    def test_without_a_readable_transcript_there_is_no_verdict_and_no_crash(self):
        gone = self.event("PreToolUse", agent_id=WORKER, tool_name="Read", tool_input={"file_path": "/x"},
                          transcript_path=os.path.join(self.tmp, "nowhere", f"{SESSION}.jsonl"))
        self.assertAllowed(self.hook(gone))
        unreadable = self.in_subagent("PreToolUse", WORKER, [HARD], "Read", {"file_path": "/x"})
        sub = os.path.join(os.path.dirname(unreadable["transcript_path"]), SESSION, "subagents",
                           f"agent-{WORKER}.jsonl")
        with open(sub, "w", encoding="utf-8") as handle:
            handle.write("{not json\n\x00\x01\n")
        self.assertAllowed(self.hook(unreadable))
        unsafe = self.event("PreToolUse", agent_id="../../etc", tool_name="Read", tool_input={},
                            transcript_path=unreadable["transcript_path"])
        self.assertAllowed(self.hook(unsafe))


def git(cwd, *args):
    done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "commit.gpgsign=false", *args], cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})
    assert done.returncode == 0, (args, done.stdout, done.stderr)
    return done.stdout.strip()


class TestHandoff(GuardCase):
    def repository(self):
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(repo)
        git(repo, "init", "-q", "-b", "main")
        with open(os.path.join(repo, "base.txt"), "w", encoding="utf-8") as handle:
            handle.write("base\n")
        git(repo, "add", "base.txt")
        git(repo, "commit", "-q", "-m", "The base")
        git(repo, "checkout", "-q", "-b", "the-feature-works")
        with open(os.path.join(repo, "feature.txt"), "w", encoding="utf-8") as handle:
            handle.write("feature\n")
        git(repo, "add", "feature.txt")
        git(repo, "commit", "-q", "-m", "Add the feature that the next agent continues")
        return repo

    def test_a_dirty_worktree_is_refused_because_that_work_would_not_survive(self):
        repo = self.repository()
        with open(os.path.join(repo, "half-done.txt"), "w", encoding="utf-8") as handle:
            handle.write("not committed\n")
        done = run_guard("handoff", "--base", "main", cwd=repo)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(done.stdout, "")
        self.assertIn("uncommitted work", done.stderr)
        self.assertIn("half-done.txt", done.stderr)

    def test_a_modified_tracked_file_is_refused_too(self):
        repo = self.repository()
        with open(os.path.join(repo, "feature.txt"), "a", encoding="utf-8") as handle:
            handle.write("more\n")
        self.assertEqual(run_guard("handoff", "--base", "main", cwd=repo).returncode, 1)

    def test_the_brief_from_a_committed_worktree_names_the_head_and_what_was_committed(self):
        repo = self.repository()
        head = git(repo, "rev-parse", "HEAD")
        done = run_guard("handoff", "--base", "main", cwd=repo)
        self.assertEqual(done.returncode, 0, done.stderr)
        brief = done.stdout
        self.assertIn("branch: the-feature-works", brief)
        self.assertIn(f"head: {head} Add the feature that the next agent continues", brief)
        self.assertIn("base: main", brief)
        self.assertIn("Add the feature that the next agent continues", brief.split("commits on the branch")[1])
        self.assertIn("A\tfeature.txt", brief)
        self.assertNotIn("base.txt", brief.split("files changed")[1])
        self.assertIn("upstream: none configured", brief)
        self.assertIn("reads the repository, not a transcript", brief)

    def test_the_brief_is_bounded(self):
        repo = self.repository()
        for index in range(45):
            for suffix in "ab":
                with open(os.path.join(repo, f"f{index}{suffix}.txt"), "w", encoding="utf-8") as handle:
                    handle.write("x\n")
            git(repo, "add", ".")
            git(repo, "commit", "-q", "-m", f"Commit number {index}")
        brief = run_guard("handoff", "--base", "main", cwd=repo).stdout
        # 46 commits against a bound of 40, and 91 files against a bound of 80.
        self.assertIn("commits on the branch since the base (46):", brief)
        self.assertIn("and 6 more commits", brief)
        self.assertIn("files changed since the base (91):", brief)
        self.assertIn("and 11 more files", brief)
        self.assertLess(len(brief.splitlines()), 150)

    def test_outside_a_repository_it_refuses(self):
        done = run_guard("handoff", cwd=self.tmp)
        self.assertEqual(done.returncode, 1)
        self.assertIn("not inside a git worktree", done.stderr)


class TestCheckSettings(GuardCase):
    def check(self, settings):
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(settings, handle)
        return run_guard("check-settings", path)

    def load(self, path):
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def test_the_rails_settings_and_this_repositorys_own_wire_the_guard(self):
        for path in (RAILS_SETTINGS, OWN_SETTINGS):
            with self.subTest(path=path):
                done = run_guard("check-settings", path)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertIn("SubagentStop", done.stdout)

    def test_this_repositorys_own_settings_run_the_one_file_the_rails_emit(self):
        commands = [hook["command"] for entries in self.load(OWN_SETTINGS)["hooks"].values()
                    for entry in entries for hook in entry["hooks"]]
        self.assertIn('python3 "$CLAUDE_PROJECT_DIR/tools/factory/recipe/rails/hooks/agent-lifecycle-guard.py"', commands)
        self.assertTrue(any("repo-hygiene.py --fix" in command for command in commands), "the SessionStart hook stays")
        self.assertTrue(os.path.isfile(GUARD))

    def test_without_the_subagentstop_entry_it_fails_and_says_so(self):
        settings = self.load(RAILS_SETTINGS)
        del settings["hooks"]["SubagentStop"]
        done = self.check(settings)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("SubagentStop", done.stdout)
        self.assertNotIn("PostToolUse", done.stdout)

    def test_the_previous_rails_settings_fail_naming_every_missing_registration(self):
        previous = {"$schema": "https://json.schemastore.org/claude-code-settings.json",
                    "hooks": {"PreToolUse": [{"matcher": "Bash|Edit|Write|NotebookEdit", "hooks": [
                        {"type": "command",
                         "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/primary-checkout-guard.py"'}]}]}}
        # This is the bytes recipe 1 of .claude/settings.json wrote, not a paraphrase of them.
        self.assertEqual(hashlib.sha256((json.dumps(previous, indent=2) + "\n").encode()).hexdigest(),
                         ownership.RECIPE_SHA256[".claude/settings.json"][1])
        done = self.check(previous)
        self.assertEqual(done.returncode, 1)
        for event in ("PreToolUse for SendMessage", "PreToolUse for all tools", "PostToolUse for all tools",
                      "SubagentStop"):
            self.assertIn(event, done.stdout)

    def test_a_matcher_that_covers_only_some_tools_is_not_all_tools(self):
        settings = self.load(RAILS_SETTINGS)
        settings["hooks"]["PostToolUse"][0]["matcher"] = "Agent|SendMessage"
        done = self.check(settings)
        self.assertEqual(done.returncode, 1)
        self.assertIn("PostToolUse for all tools", done.stdout)
        settings["hooks"]["PostToolUse"][0]["matcher"] = ".*"
        self.assertEqual(self.check(settings).returncode, 0)

    def test_a_sendmessage_only_pretooluse_does_not_satisfy_the_every_tool_bound(self):
        settings = self.load(RAILS_SETTINGS)
        settings["hooks"]["PreToolUse"][1]["matcher"] = "SendMessage"
        done = self.check(settings)
        self.assertEqual(done.returncode, 1)
        self.assertIn("PreToolUse for all tools", done.stdout)
        self.assertNotIn("PreToolUse for SendMessage", done.stdout)

    def test_disabling_all_hooks_or_pointing_at_another_script_fails(self):
        settings = self.load(RAILS_SETTINGS)
        settings["disableAllHooks"] = True
        done = self.check(settings)
        self.assertEqual(done.returncode, 1)
        self.assertIn("disableAllHooks", done.stdout)
        other = self.load(RAILS_SETTINGS)
        for entries in other["hooks"].values():
            for entry in entries:
                for hook in entry["hooks"]:
                    hook["command"] = hook["command"].replace("agent-lifecycle-guard", "something-else")
        self.assertEqual(self.check(other).returncode, 1)

    def test_a_file_that_is_not_json_or_is_absent_fails(self):
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{nope")
        self.assertEqual(run_guard("check-settings", path).returncode, 1)
        self.assertEqual(run_guard("check-settings", os.path.join(self.tmp, "absent.json")).returncode, 1)


class TestMeasure(GuardCase):
    """One session, two subagents: A is resumed once, B never is. The figures are worked by hand."""

    def line(self, message_id, context, output, stamp):
        return assistant_line(message_id, context, output, stamp)

    def write(self, path, lines):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            for line in lines:
                handle.write(json.dumps(line) + "\n")

    def build(self):
        root = os.path.join(self.tmp, "projects")
        project = os.path.join(root, "-work-rules-engine")
        agents = os.path.join(project, SESSION, "subagents")
        resume = {"type": "user", "timestamp": "2026-10-15T10:00:10.000Z",
                  "toolUseResult": {"success": True, "message": f"Resuming agent {WORKER}", "resumedAgentId": WORKER}}
        self.write(os.path.join(project, f"{SESSION}.jsonl"), [
            {"type": "user", "timestamp": "2026-10-15T09:59:00.000Z", "toolUseResult": {"agentId": WORKER}},
            resume])
        # A: first assignment 100k then 300k (peak), resumed at 10:00:10, then 320k and 340k.
        first = self.line("m1", 100_000, 5, "2026-10-15T10:00:00.000Z")
        partial = self.line("m2", 290_000, 1, "2026-10-15T10:00:05.000Z")      # same message id, earlier line
        second = self.line("m2", 300_000, 10, "2026-10-15T10:00:06.000Z")
        self.write(os.path.join(agents, f"agent-{WORKER}.jsonl"), [
            first, partial, second,
            self.line("m3", 320_000, 20, "2026-10-15T10:00:20.000Z"),
            self.line("m4", 340_000, 10, "2026-10-15T10:00:30.000Z")])
        self.write(os.path.join(agents, f"agent-{OTHER}.jsonl"), [
            self.line("n1", 200_000, 7, "2026-10-15T10:01:00.000Z"),
            self.line("n2", 250_000, 3, "2026-10-15T10:01:05.000Z")])
        # A project outside --match carries an agent that must not be counted.
        self.write(os.path.join(root, "-work-unrelated", "s", "subagents", "agent-a9999999999999999.jsonl"),
                   [self.line("z1", 999_999, 1, "2026-10-15T11:00:00.000Z")])
        with open(os.path.join(root, "-work-unrelated", "s.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("")
        return root

    def ledger_with_history(self):
        os.makedirs(self.ledger)
        records = [{"event": "denied", "reason": "completed-agent", "agent_id": WORKER},
                   {"event": "denied", "reason": "completed-agent", "agent_id": OTHER},
                   {"event": "denied", "reason": "context-hard-bound", "agent_id": OTHER},
                   {"event": "violation", "reason": "completed-agent-resumed", "agent_id": WORKER},
                   {"event": "checkpoint", "agent_id": WORKER}, {"event": "launched", "agent_id": WORKER}]
        with open(os.path.join(self.ledger, "s.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("".join(json.dumps(r) + "\n" for r in records))

    def measure(self, root, *extra):
        return run_guard("measure", "--projects-dir", root, "--ledger-dir", self.ledger, *extra)

    def test_the_report_has_the_exact_counts_and_the_reread_estimate(self):
        root = self.build()
        self.ledger_with_history()
        done = self.measure(root, "--match", "rules")
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        wanted = {
            "projects matched: 1",
            "agents: 2",
            "resumed agents: 1",
            "resume events: 1",
            "resume events without a transcript: 0",
            # A: 100,005 + 300,010 + 320,020 + 340,010 ; B: 200,007 + 250,003
            "tokens in all agent turns: 1510055",
            "post-resume turns: 2",
            "tokens in post-resume turns: 660030 (43.7% of all)",
        }
        for line in wanted:
            self.assertIn(line, lines)
        # max(0, min(320k, 300k) - 100k) + max(0, min(340k, 300k) - 100k) = 200k + 200k
        (reread,) = [line for line in lines if line.startswith("re-read tokens beyond the first turn:")]
        self.assertTrue(reread.startswith("re-read tokens beyond the first turn: 400000 (26.5% of all)"), reread)
        self.assertIn("ESTIMATE of what a fresh agent would not have carried", reread)
        self.assertIn("first-assignment peak context over 2 agents (nearest rank): p50 250000 p75 300000 "
                      "p90 300000 p95 300000", lines)
        self.assertIn("  2026-10-15T10:00:10.000Z " + WORKER, lines)
        self.assertIn("guard denials: 3 (completed-agent: 2, context-hard-bound: 1)", lines)
        self.assertIn("guard violations (a completed agent was resumed anyway): 1", lines)
        self.assertIn("checkpoint notes issued: 1", lines)

    def test_a_message_id_is_counted_once_and_a_project_outside_the_match_not_at_all(self):
        root = self.build()
        everything = self.measure(root).stdout.splitlines()
        self.assertIn("agents: 3", everything)
        self.assertIn("projects matched: 2", everything)
        matched = self.measure(root, "--match", "rules").stdout.splitlines()
        self.assertIn("agents: 2", matched)

    def test_the_report_is_deterministic(self):
        root = self.build()
        self.ledger_with_history()
        self.assertEqual(self.measure(root).stdout, self.measure(root).stdout)

    def test_no_ledger_is_said_rather_than_reported_as_zero(self):
        root = self.build()
        self.assertIn("guard ledger: none at", self.measure(root).stdout)

    def test_a_missing_projects_directory_or_an_unmatched_pattern_fails(self):
        root = self.build()
        self.assertEqual(self.measure(os.path.join(self.tmp, "absent")).returncode, 1)
        done = self.measure(root, "--match", "no-such-project")
        self.assertEqual(done.returncode, 1)
        self.assertIn("matches", done.stderr)


if __name__ == "__main__":
    unittest.main()
