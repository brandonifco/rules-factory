#!/usr/bin/env python3
"""The agent rails a produced engine ships with (#151, decision 0029).

Asserted here, about the bytes the factory emits rather than about a GitHub repository:

  * every link in an emitted rail resolves **in an engine**, which is the one place they can be
    judged -- `AGENTS.md` sits at an engine's root, not in `tools/factory/recipe/rails/`, so
    scripts/validate.sh's repository-wide link check skips that directory and this replaces it.
    The predecessor shipped 61 references to files that did not exist, several inside runtime
    error messages, and a rail that cites a document the factory does not emit is that failure;
  * no vendor name appears in any emitted rail. The one place a provider is named is
    `.github/agent-policy.json`, which the engine owns (0029 §3);
  * a reviewer charter grants read tools only. The predecessor's own check caught a charter
    claiming read-only while granting `Bash` (0029 §8). The engine-side check is #153's; this is
    the factory's, so a charter cannot be emitted that way in the first place;
  * a managed rail names neither the engine nor its map. A managed recipe's bytes are fixed per
    version (ownership.py), which is what hand-edit detection compares against, so a rail that
    varied per engine would have no history to detect against (0029 §5);
  * the policy is engine-owned in behaviour and not only in the table: a produce writes it once,
    a later produce with an edited copy leaves the edit alone, and provenance records it;
  * the guard reads the policy for its variable names, falls back to the defaults when the policy
    is unreadable rather than failing open or closed by accident, and actually blocks a write in
    the primary checkout while allowing one in a worktree.

Run: python3 -m pytest tools/tests/test_factory_rails.py
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")
PART107 = os.path.join(REPO, "examples", "faa-part-107")
PART107_XML = os.path.join(PART107, "part107.xml")
NAME = "FaaPart107"
GUARD = os.path.join(FACTORY, "recipe", "rails", "hooks", "primary-checkout-guard.py")

_spec = importlib.util.spec_from_file_location("factory_main_rails", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
generate = factory.generate
ownership = generate.ownership

LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")
# Every provider the default chain names, plus the repository these rails were adapted from and its
# subject matter. A rail that needs one of these is misclassified: the choice belongs in the policy.
#
# "Claude" is deliberately not on this list. The Claude adapter's own files, the directory they live
# in and the two places AGENTS.md says what a Claude agent or a non-Claude agent should do are the
# adapter existing, not a provider being chosen -- and 0029 puts the review chain, which is the
# thing that must be replaceable, in the policy alone.
VENDORS = ("codex", "gemini", "openai", "deckard", "shadowrun")
MUTATING_TOOLS = {"bash", "edit", "write", "notebookedit", "multiedit", "task", "webfetch"}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True).stdout.strip()


def frontmatter(text):
    """The `---`-delimited YAML header of a charter, as a flat dict of strings."""
    if not text.startswith("---\n"):
        return {}
    body = text.split("---\n", 2)[1]
    out = {}
    for line in body.splitlines():
        if ": " in line and not line.startswith(" "):
            key, value = line.split(": ", 1)
            out[key.strip()] = value.strip()
    return out


class TestTheEmittedRails(unittest.TestCase):
    """The recipe bytes, judged without producing an engine."""

    def setUp(self):
        self.rails = generate.rails_files()
        self.emitted = {**generate.managed_files(), ".github/agent-policy.json": generate.agent_policy()}

    def test_every_rail_is_a_managed_row_of_the_table(self):
        managed = {row.pattern for row in ownership.managed_rows("")}
        self.assertTrue(set(self.rails) <= managed, sorted(set(self.rails) - managed))

    def test_every_link_in_a_rail_resolves_in_an_engine(self):
        # The engine an emitted rail lives in: every path the factory writes for a named engine,
        # plus the directories those paths imply.
        model = type("M", (), {"name": NAME, "rulings": (), "entries": ()})()
        layout = set(self.emitted) | {"scripts/validate.sh", "provenance.json", "corpus-map.overlay.json",
                                      "docs/decisions", "corpus", "backlog"}
        for row in ownership.rows(NAME):
            layout.add(row.pattern.replace("*", "x"))
        layout |= {os.path.dirname(p) for p in list(layout) if os.path.dirname(p)}
        del model

        # Every markdown rail, and every one of them examined: a rail that links to nothing is how
        # this check would quietly stop proving anything as the documents change.
        examined = {}
        for relative, text in self.emitted.items():
            if not relative.endswith(".md"):
                continue
            examined[relative] = 0
            for target in LINK.findall(text):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                examined[relative] += 1
                resolved = os.path.normpath(os.path.join(os.path.dirname(relative), target))
                self.assertIn(resolved, layout, f"{relative} -> {target} resolves to nothing an engine holds")
        self.assertEqual(set(examined), {p for p in self.emitted if p.endswith(".md")})
        for relative, count in examined.items():
            self.assertGreater(count, 0, f"{relative} links to nothing in the engine, so it proved nothing here")

    def test_no_emitted_rail_names_a_vendor(self):
        for relative, text in self.emitted.items():
            if relative == ".github/agent-policy.json":
                continue
            for vendor in VENDORS:
                self.assertNotIn(vendor, text.lower(),
                                 f"{relative} names {vendor!r}; a provider belongs in .github/agent-policy.json")

    def test_the_policy_names_the_default_chain(self):
        policy = json.loads(generate.agent_policy())
        self.assertEqual(policy["schemaVersion"], 1)
        self.assertEqual([link["id"] for link in policy["review"]["independentFallback"]],
                         ["codex", "gemini", "in-house-independent"])
        for link in policy["review"]["independentFallback"]:
            self.assertTrue(link["context"].startswith("rules-verdict/"), link)
        self.assertEqual(set(policy["labels"]), {"ready", "blocked", "needsDecision", "normalRisk", "independentRisk"})
        self.assertEqual(policy["worktrees"], {"rootEnvironmentVariable": "RULES_ENGINE_WORKTREE_ROOT",
                                               "primaryMutationEscapeHatch": "RULES_ENGINE_ALLOW_PRIMARY_MUTATION"})

    def test_a_reviewer_charter_grants_read_tools_only(self):
        reviewers = [".claude/agents/repo-steward.md", ".claude/agents/rules-conformance.md"]
        for relative in reviewers:
            header = frontmatter(self.emitted[relative])
            self.assertIn("tools", header, f"{relative} grants no explicit tool list, so it inherits everything")
            granted = {tool.strip().lower() for tool in header["tools"].split(",")}
            self.assertEqual(granted & MUTATING_TOOLS, set(), f"{relative} grants a mutation-capable tool")
            self.assertTrue(granted <= {"read", "grep", "glob"}, granted)

    def test_a_managed_rail_names_neither_the_engine_nor_its_map(self):
        # The constraint ownership.py's managed class puts on a recipe, checked on the rails rather
        # than assumed: fixed bytes per version is what a hand edit is detected against.
        for relative, text in self.rails.items():
            for forbidden in (NAME, "FaaPart107", "HoyleBackgammon", "RulesFactory.Maps"):
                self.assertNotIn(forbidden, text, f"{relative} names an engine or a map")

    def test_the_settings_run_the_guard_without_an_executable_bit(self):
        # `produce` writes with the default mode, so a hook invoked by path alone would not run.
        settings = json.loads(self.emitted[".claude/settings.json"])
        (entry,) = settings["hooks"]["PreToolUse"]
        self.assertEqual(entry["matcher"], "Bash|Edit|Write|NotebookEdit")
        (hook,) = entry["hooks"]
        self.assertTrue(hook["command"].startswith("python3 "), hook["command"])
        self.assertIn(".claude/hooks/primary-checkout-guard.py", hook["command"])


class TestAProducedEngine(unittest.TestCase):
    """The rails as `factory produce` puts them in place."""

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        out = os.path.join(cls.shared, "package")
        subprocess.run([sys.executable, PACK, PART107, "--out", out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (package,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
        cls.package = os.path.join(out, package)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = os.path.join(self.tmp, "engine")

    def produce(self, *extra):
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["produce", "--package", self.package, "--corpus", PART107_XML, "--name", NAME,
                                 "--out", self.out, "--allow-dirty", "--no-verify", *extra])
        return code, buffer.getvalue()

    def produced(self, *extra):
        code, output = self.produce(*extra)
        self.assertEqual(code, 0, output)
        return output

    def read(self, relative):
        with open(os.path.join(self.out, *relative.split("/")), encoding="utf-8") as handle:
            return handle.read()

    def test_a_produced_engine_holds_every_rail(self):
        self.produced()
        for relative in list(generate.rails_files()) + [".github/agent-policy.json"]:
            self.assertTrue(os.path.isfile(os.path.join(self.out, *relative.split("/"))), relative)
        self.assertIn("is the governing contract for this repository", self.read("CLAUDE.md"))

    def test_the_policy_is_written_once_and_never_again(self):
        self.produced()
        edited = json.loads(self.read(".github/agent-policy.json"))
        edited["review"]["independentFallback"] = [{"id": "in-house-independent",
                                                    "context": "rules-verdict/in-house-independent"}]
        edited["labels"]["ready"] = "ready-to-work"
        path = os.path.join(self.out, ".github", "agent-policy.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(edited, handle, indent=2)
        self.produced()
        self.assertEqual(json.loads(self.read(".github/agent-policy.json")), edited,
                         "a produce rewrote a file the engine owns")

    def test_the_policy_is_recorded_as_an_engine_owned_build_input(self):
        self.produced()
        record = json.loads(self.read("provenance.json"))
        self.assertIn(".github/agent-policy.json", {e["path"] for e in record["engineOwned"]})
        self.assertIn(".github/agent-policy.json", {b["path"] for b in record["buildInputs"]})

    def test_a_hand_edited_rail_is_refused_by_name_and_adoption_settles_it(self):
        self.produced()
        path = os.path.join(self.out, "AGENTS.md")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n## Our own section\n")
        code, output = self.produce()
        self.assertEqual(code, 1, output)
        self.assertIn("AGENTS.md", output)
        self.assertIn("--adopt", output)
        self.assertTrue(self.read("AGENTS.md").endswith("## Our own section\n"), "the edit survived the refusal")

        output = self.produced("--adopt", "AGENTS.md")
        self.assertIn("adopted AGENTS.md", output)
        self.assertTrue(self.read("AGENTS.md").endswith("## Our own section\n"))
        record = json.loads(self.read("provenance.json"))
        self.assertTrue(any(e["path"] == "AGENTS.md" and e["adopted"] for e in record["engineOwned"]))

        output = self.produced("--reset", "AGENTS.md")
        self.assertEqual(self.read("AGENTS.md"), generate.rails_files()["AGENTS.md"])


class TestTheGuard(unittest.TestCase):
    """The guard's own behaviour, as the hook runs it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.primary = os.path.join(self.tmp, "engine")
        os.makedirs(self.primary)
        git(self.primary, "init", "-q", "-b", "main")
        git(self.primary, "config", "user.email", "t@example.invalid")
        git(self.primary, "config", "user.name", "t")
        with open(os.path.join(self.primary, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("engine\n")
        git(self.primary, "add", "README.md")
        git(self.primary, "commit", "-qm", "first")

    def policy(self, document):
        os.makedirs(os.path.join(self.primary, ".github"), exist_ok=True)
        with open(os.path.join(self.primary, ".github", "agent-policy.json"), "w", encoding="utf-8") as handle:
            handle.write(document)

    def run_guard(self, payload, environment=None, project_dir=None):
        done = subprocess.run([sys.executable, GUARD], input=json.dumps(payload), text=True,
                              capture_output=True,
                              env={**os.environ, "CLAUDE_PROJECT_DIR": project_dir or self.primary,
                                   **(environment or {})})
        return done.returncode, done.stderr

    def bash(self, command, cwd=None, **kwargs):
        return self.run_guard({"tool_name": "Bash", "tool_input": {"command": command},
                               "cwd": cwd or self.primary}, **kwargs)

    def test_a_commit_in_the_primary_checkout_is_blocked(self):
        code, stderr = self.bash("git commit -m 'x'")
        self.assertEqual(code, 2, stderr)
        self.assertIn("commit in the primary checkout", stderr)
        self.assertIn("RULES_ENGINE_ALLOW_PRIMARY_MUTATION", stderr)

    def test_a_write_into_the_primary_checkout_is_blocked(self):
        code, stderr = self.run_guard({"tool_name": "Write", "cwd": self.primary,
                                       "tool_input": {"file_path": os.path.join(self.primary, "src", "A.cs")}})
        self.assertEqual(code, 2, stderr)
        self.assertIn("AGENTS.md section 4", stderr)

    def test_a_worktree_is_not_the_primary_checkout(self):
        worktree = os.path.join(self.tmp, "worktrees", "issue-1")
        git(self.primary, "worktree", "add", "-q", "-b", "issue-1", worktree)
        code, stderr = self.bash("git commit -m 'x'", cwd=worktree)
        self.assertEqual(code, 0, stderr)
        code, stderr = self.run_guard({"tool_name": "Write", "cwd": worktree,
                                       "tool_input": {"file_path": os.path.join(worktree, "src", "A.cs")}})
        self.assertEqual(code, 0, stderr)

    def test_bulk_staging_is_blocked_in_a_worktree_too(self):
        worktree = os.path.join(self.tmp, "worktrees", "issue-2")
        git(self.primary, "worktree", "add", "-q", "-b", "issue-2", worktree)
        code, stderr = self.bash("git add -A", cwd=worktree)
        self.assertEqual(code, 2, stderr)
        self.assertIn("bulk", stderr)

    def test_the_escape_hatch_allows_it(self):
        code, stderr = self.bash("git commit -m 'x'", environment={"RULES_ENGINE_ALLOW_PRIMARY_MUTATION": "1"})
        self.assertEqual(code, 0, stderr)

    def test_the_escape_hatch_is_the_policy_s_to_rename(self):
        self.policy(json.dumps({"schemaVersion": 1,
                                "worktrees": {"rootEnvironmentVariable": "ACME_WORKTREES",
                                              "primaryMutationEscapeHatch": "ACME_ALLOW"}}))
        code, stderr = self.bash("git commit -m 'x'")
        self.assertEqual(code, 2, stderr)
        self.assertIn("ACME_ALLOW", stderr)
        code, stderr = self.bash("git commit -m 'x'", environment={"ACME_ALLOW": "1"})
        self.assertEqual(code, 0, stderr)
        code, stderr = self.bash("git commit -m 'x'", environment={"RULES_ENGINE_ALLOW_PRIMARY_MUTATION": "1"})
        self.assertEqual(code, 2, msg=f"the default still worked after the policy renamed it: {stderr}")

    def test_an_unreadable_policy_falls_back_to_the_defaults(self):
        self.policy("{ not json at all")
        code, stderr = self.bash("git commit -m 'x'")
        self.assertEqual(code, 2, stderr)
        self.assertIn("RULES_ENGINE_ALLOW_PRIMARY_MUTATION", stderr)
        code, stderr = self.bash("git commit -m 'x'", environment={"RULES_ENGINE_ALLOW_PRIMARY_MUTATION": "1"})
        self.assertEqual(code, 0, stderr)

    def test_a_quoted_angle_bracket_is_not_a_redirect(self):
        # The message this project's own commits carry. A guard that blocks it teaches agents to
        # route around the guard, which is worse than not having one.
        worktree = os.path.join(self.tmp, "worktrees", "issue-3")
        git(self.primary, "worktree", "add", "-q", "-b", "issue-3", worktree)
        code, stderr = self.bash("git commit -m 'x\n\nCo-Authored-By: A <noreply@example.invalid>'", cwd=worktree)
        self.assertEqual(code, 0, stderr)


if __name__ == "__main__":
    unittest.main()


class TestTheEntryPacket(TestAProducedEngine):
    """`tools/entry-packet.py` against a produced engine and the map it was produced from (#152)."""

    PACKAGE_MAP = os.path.join(PART107, "corpus-map.json")

    def packet(self, entry, *extra, out=None):
        done = subprocess.run([sys.executable, os.path.join(self.out, "tools", "entry-packet.py"), entry,
                               "--package-map", self.PACKAGE_MAP, *extra],
                              capture_output=True, text=True, cwd=self.out)
        return done

    def rendered(self, entry):
        done = self.packet(entry, "--stdout")
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_the_packet_is_the_map_s_own_bytes(self):
        self.produced()
        text = self.rendered("speed-limit")
        source = json.load(open(self.PACKAGE_MAP, encoding="utf-8"))
        entry = next(e for e in source["entries"] if e["id"] == "speed-limit")
        # The evidence verbatim, the citation, and the unresolved question: quoted, never summarised.
        self.assertIn(entry["evidence"], text)
        self.assertIn("§ 107.51(a)", text)
        self.assertIn(entry["ambiguity"]["question"], text)
        self.assertIn("RulesFactory.Maps.FaaPart107", text)
        # Reachability and cross-references are named with what they point at, not bare ids.
        self.assertIn("suspendedBy", text)
        self.assertIn("waivable-regulations", text)

    def test_the_packet_declares_the_handler_the_build_declares(self):
        self.produced()
        text = self.rendered("speed-limit")
        signature = next(line for line in text.splitlines()
                         if "SpeedLimit(" in line and "partial" in line)
        contracts = self.read(f"src/{NAME}/Generated/Contracts.g.cs")
        self.assertIn(signature.strip(), contracts,
                      "the packet's handler signature is not the one Contracts.g.cs declares")

    def test_an_unknown_entry_is_refused_with_what_the_map_does_have(self):
        self.produced()
        done = self.packet("speed", "--stdout")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("REFUSED", done.stderr)
        self.assertIn("speed-limit", done.stderr, "a near miss says what the map does have")

    def test_a_packet_is_never_written_inside_the_repository(self):
        self.produced()
        done = self.packet("speed-limit", "--out", os.path.join(self.out, "packets"))
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("never written inside the repository", done.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.out, "packets")))

    def test_the_packet_is_written_where_the_variable_says(self):
        self.produced()
        root = os.path.join(self.tmp, "packets")
        done = self.packet("altitude-limit", "--out", root)
        self.assertEqual(done.returncode, 0, done.stderr)
        written = done.stdout.strip()
        self.assertEqual(written, os.path.join(root, "entry-altitude-limit.md"))
        with open(written, encoding="utf-8") as handle:
            self.assertIn("# Entry packet: `altitude-limit`", handle.read())


GH_STUB = '''#!/usr/bin/env python3
"""A stand-in for `gh`, answering from a JSON fixture. Only the shapes the rails ask for."""
import json, os, sys

fixture = json.load(open(os.environ["GH_FIXTURE"], encoding="utf-8"))
argv = sys.argv[1:]
kind = argv[0] if argv else ""
number = argv[2] if len(argv) > 2 else ""
record = (fixture.get(kind) or {}).get(number)
if record is None:
    sys.stderr.write(f"no such {kind} {number}\\n")
    sys.exit(1)
fields = argv[argv.index("--json") + 1].split(",") if "--json" in argv else []
answer = {f: record.get(f) for f in fields}
if "--jq" in argv:
    expression = argv[argv.index("--jq") + 1]
    if expression == ".title":
        print(record.get("title", ""))
    elif expression == ".state":
        print(record.get("state", ""))
    elif "labels" in expression:
        print(",".join(label["name"] for label in record.get("labels") or []))
    else:
        sys.stderr.write(f"unsupported --jq {expression}\\n")
        sys.exit(2)
else:
    print(json.dumps(answer))
'''


class RailsInAGitEngine(TestAProducedEngine):
    """A produced engine that is also a git repository, with a stand-in for `gh`."""

    def setUp(self):
        super().setUp()
        self.worktrees = os.path.join(self.tmp, "worktrees")
        self.gh = os.path.join(self.tmp, "gh-stub.py")
        with open(self.gh, "w", encoding="utf-8") as handle:
            handle.write(GH_STUB)
        os.chmod(self.gh, 0o755)
        self.fixture_path = os.path.join(self.tmp, "gh.json")

    def fixture(self, document):
        with open(self.fixture_path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)

    def commit_engine(self):
        self.produced()
        git(self.out, "init", "-q", "-b", "main")
        git(self.out, "config", "user.email", "t@example.invalid")
        git(self.out, "config", "user.name", "t")
        git(self.out, "add", ".")
        git(self.out, "commit", "-qm", "the produced engine")

    def environment(self, **extra):
        return {**os.environ, "RULES_ENGINE_GH": self.gh, "GH_FIXTURE": self.fixture_path,
                "RULES_ENGINE_WORKTREE_ROOT": self.worktrees, **extra}

    def dispatch(self, *args, **extra):
        return subprocess.run(["bash", os.path.join(self.out, "tools", "dispatch-agent.sh"), *args],
                              cwd=self.out, capture_output=True, text=True, env=self.environment(**extra))


class TestTheDispatcher(RailsInAGitEngine):
    """`tools/dispatch-agent.sh`: what it refuses, and what it leaves behind when it does not (#152)."""

    def issue(self, number, labels=("state:ready", "risk:normal"), state="OPEN", title="Widen the altitude limit"):
        self.fixture({"issue": {str(number): {"title": title, "state": state,
                                              "labels": [{"name": name} for name in labels]}}})

    def test_a_ready_issue_gets_a_worktree_outside_the_repository(self):
        self.commit_engine()
        self.issue(27)
        done = self.dispatch("27")
        self.assertEqual(done.returncode, 0, done.stderr)
        path = os.path.join(self.worktrees, "issue-27-widen-the-altitude-limit")
        self.assertTrue(os.path.isdir(path), done.stdout)
        self.assertIn("tools/entry-packet.py", done.stdout, "it says where the assignment comes from")
        # The primary checkout is untouched: still on main, still clean.
        self.assertEqual(git(self.out, "rev-parse", "--abbrev-ref", "HEAD"), "main")
        self.assertEqual(git(self.out, "status", "--porcelain"), "")

    def test_an_issue_awaiting_a_decision_is_not_dispatched(self):
        self.commit_engine()
        self.issue(27, labels=("state:needs-decision", "risk:normal"))
        done = self.dispatch("27")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("may not resolve the open question itself", done.stderr)
        self.assertFalse(os.path.isdir(self.worktrees) and os.listdir(self.worktrees))

    def test_a_blocked_issue_is_not_dispatched(self):
        self.commit_engine()
        self.issue(27, labels=("state:blocked",))
        done = self.dispatch("27")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not built yet", done.stderr)

    def test_a_closed_issue_is_not_dispatched(self):
        self.commit_engine()
        self.issue(27, state="CLOSED")
        done = self.dispatch("27")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("is CLOSED", done.stderr)

    def test_the_labels_are_the_policy_s(self):
        # An engine that renames its labels gets the rename honoured, with no change to the script.
        self.commit_engine()
        path = os.path.join(self.out, ".github", "agent-policy.json")
        policy = json.load(open(path, encoding="utf-8"))
        policy["labels"]["needsDecision"] = "awaiting-brandon"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(policy, handle, indent=2)
        git(self.out, "commit", "-qam", "rename a label")  # the dirty-checkout guard fires first otherwise
        self.issue(27, labels=("awaiting-brandon",))
        done = self.dispatch("27")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("awaiting-brandon", done.stderr)

    def test_a_dirty_primary_checkout_is_not_dispatched_from(self):
        self.commit_engine()
        self.issue(27)
        with open(os.path.join(self.out, "README-notes.md"), "w", encoding="utf-8") as handle:
            handle.write("half-finished\n")
        done = self.dispatch("27")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("uncommitted changes", done.stderr)

    def test_a_second_dispatch_of_the_same_issue_is_refused(self):
        self.commit_engine()
        self.issue(27)
        self.assertEqual(self.dispatch("27").returncode, 0)
        done = self.dispatch("27")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("already exists", done.stderr)
        self.assertIn("--cleanup 27", done.stderr)

    def test_a_worktree_root_inside_the_repository_is_refused(self):
        self.commit_engine()
        self.issue(27)
        done = self.dispatch("27", RULES_ENGINE_WORKTREE_ROOT=os.path.join(self.out, "worktrees"))
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("resolves inside the repository", done.stderr)

    def test_a_non_numeric_issue_is_refused(self):
        self.commit_engine()
        done = self.dispatch("altitude-limit")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("must be numeric", done.stderr)

    def test_cleanup_removes_the_worktree_and_the_merged_branch(self):
        self.commit_engine()
        self.issue(27)
        self.assertEqual(self.dispatch("27").returncode, 0)
        done = self.dispatch("--cleanup", "27")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(os.path.isdir(os.path.join(self.worktrees, "issue-27-widen-the-altitude-limit")))


class TestNewIssue(RailsInAGitEngine):
    """`tools/new-issue.sh`: one state label, one risk label, and the shape (#152)."""

    def new_issue(self, *args):
        return subprocess.run(["bash", os.path.join(self.out, "tools", "new-issue.sh"), *args],
                              cwd=self.out, capture_output=True, text=True, env=self.environment())

    def test_it_files_at_the_ready_state_and_normal_risk(self):
        self.produced()
        done = self.new_issue("--title", "Widen the altitude limit", "--dry-run")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("labels: state:ready,risk:normal", done.stdout)
        self.assertIn("## Acceptance criteria", done.stdout)
        self.assertIn("names the mutation that makes it fail", done.stdout)

    def test_independent_risk_is_asked_for_explicitly(self):
        self.produced()
        done = self.new_issue("--title", "x", "--risk", "independent", "--dry-run")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("risk:independent-review", done.stdout)

    def test_an_entry_gets_the_marker_that_ties_it_to_the_map(self):
        self.produced()
        done = self.new_issue("--title", "x", "--entry", "altitude-limit", "--dry-run")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("<!-- rules-factory-entry: altitude-limit -->", done.stdout)

    def test_the_labels_are_the_policy_s(self):
        self.produced()
        path = os.path.join(self.out, ".github", "agent-policy.json")
        policy = json.load(open(path, encoding="utf-8"))
        policy["labels"]["ready"] = "ready-to-work"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(policy, handle, indent=2)
        done = self.new_issue("--title", "x", "--dry-run")
        self.assertIn("labels: ready-to-work,risk:normal", done.stdout)

    def test_an_unknown_risk_is_refused(self):
        self.produced()
        done = self.new_issue("--title", "x", "--risk", "catastrophic", "--dry-run")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("--risk is normal or independent", done.stderr)


class TestTheReviewPacket(RailsInAGitEngine):
    """`tools/review-packet.py`: the reviewer's context, assembled once and in reading order (#152)."""

    def change(self):
        """A branch that touches the semantic surface, as an implementation would."""
        git(self.out, "checkout", "-qb", "issue-27")
        overlay = os.path.join(self.out, "corpus-map.overlay.json")
        with open(overlay, "w", encoding="utf-8") as handle:
            json.dump({"altitude-limit": {"status": "implemented", "implementedIn": "Rules/AltitudeLimit.cs",
                                          "tests": [{"name": "AltitudeLimit_DeclinesAboveTheCeiling",
                                                     "mutation": "return the ceiling instead of declining"}]}},
                      handle, indent=2)
        os.makedirs(os.path.join(self.out, "src", NAME, "Rules"), exist_ok=True)
        with open(os.path.join(self.out, "src", NAME, "Rules", "AltitudeLimit.cs"), "w", encoding="utf-8") as handle:
            handle.write("// the altitude limit\n")
        git(self.out, "add", "-A")
        git(self.out, "commit", "-qm", "implement the altitude limit")
        return git(self.out, "rev-parse", "HEAD")

    def pull_request(self, head, *, labels=("state:ready", "risk:normal"), issues=1, body="## Linked Issue\nCloses #27"):
        self.fixture({
            "pr": {"5": {"number": 5, "title": "Implement the altitude limit", "body": body,
                         "headRefOid": head, "headRefName": "issue-27", "baseRefName": "main",
                         "files": [{"path": "corpus-map.overlay.json"},
                                   {"path": f"src/{NAME}/Rules/AltitudeLimit.cs"},
                                   {"path": "README.md"}],
                         "closingIssuesReferences": [{"number": 27}][:issues]}},
            "issue": {"27": {"number": 27, "title": "Widen the altitude limit", "state": "OPEN",
                             "body": "<!-- rules-factory-entry: altitude-limit -->\n## Acceptance criteria\n- [ ] it declines",
                             "labels": [{"name": name} for name in labels]}},
        })

    def packet(self, *extra):
        # --package-map because the test has no restored package: in an engine it asks MSBuild, as the
        # gate does. Everything else about the packet is the same either way.
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "review-packet.py"), "5",
                               "--base", "main", "--package-map", os.path.join(PART107, "corpus-map.json"), *extra],
                              cwd=self.out, capture_output=True, text=True, env=self.environment())

    def rendered(self, *extra):
        done = self.packet("--stdout", *extra)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_the_entry_comes_before_the_diff(self):
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        text = self.rendered()
        self.assertLess(text.index("## 3. The entries, as the map has them"), text.index("## 7. The diff"),
                        "a semantic reviewer reads the entry first, so the packet puts it first")
        self.assertIn("altitude-limit", text)
        self.assertIn(head, text, "the head commit every verdict is recorded against")

    def test_it_carries_the_issue_the_claim_the_overlay_and_what_must_be_green(self):
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        text = self.rendered()
        self.assertIn("Widen the altitude limit", text)
        self.assertIn("Closes #27", text)
        self.assertIn("AltitudeLimit_DeclinesAboveTheCeiling", text, "the overlay's before and after")
        self.assertIn("return the ceiling instead of declining", text, "the mutation evidence")
        self.assertIn("./scripts/validate.sh full", text)
        self.assertIn("rules-verdict/semantic", text)
        self.assertIn("← semantic surface", text, "which changed files are on the semantic surface")

    def test_an_independent_risk_issue_says_one_verdict_is_not_enough(self):
        self.commit_engine()
        head = self.change()
        self.pull_request(head, labels=("state:ready", "risk:independent-review"))
        text = self.rendered()
        self.assertIn("A semantic verdict alone does not satisfy the gate", text)
        self.assertIn("rules-verdict/codex → rules-verdict/gemini", text, "the chain, read from the policy")

    def test_the_chain_is_the_policy_s_to_replace(self):
        self.commit_engine()
        path = os.path.join(self.out, ".github", "agent-policy.json")
        policy = json.load(open(path, encoding="utf-8"))
        policy["review"]["independentFallback"] = [{"id": "acme", "context": "rules-verdict/acme"}]
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(policy, handle, indent=2)
        git(self.out, "commit", "-qam", "one provider, ours")
        head = self.change()
        self.pull_request(head, labels=("risk:independent-review",))
        text = self.rendered()
        self.assertIn("rules-verdict/acme", text)
        self.assertNotIn("codex", text, "no script names a provider; the policy does")

    def test_a_pull_request_closing_no_single_issue_is_refused(self):
        self.commit_engine()
        head = self.change()
        self.pull_request(head, issues=0)
        done = self.packet("--stdout")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("closes 0 issues", done.stderr)

    def test_the_packet_is_written_outside_the_repository_with_the_entry_packets(self):
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        out = os.path.join(self.tmp, "packets")
        done = self.packet("--out", out)
        self.assertEqual(done.returncode, 0, done.stderr)
        written = done.stdout.split()
        self.assertEqual(written[0], os.path.join(out, f"pr-5-{head[:12]}.md"))
        self.assertEqual(written[1], os.path.join(out, "entry-altitude-limit.md"))
        with open(written[0], encoding="utf-8") as handle:
            body = handle.read()
        digest = hashlib.sha256(open(written[1], "rb").read()).hexdigest()
        self.assertIn(digest, body, "the entry packet's digest, so two reviewers can prove they read the same entry")

    def test_a_packet_inside_the_repository_is_refused(self):
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        done = self.packet("--out", os.path.join(self.out, "packets"))
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("never written inside the repository", done.stderr)
