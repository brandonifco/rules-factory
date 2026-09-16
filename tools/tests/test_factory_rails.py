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
gate = factory.gate
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
            if relative == ".github/pull_request_template.md":
                # A form, not a document: its text is copied into every pull request body, where a
                # repository-relative link would render as a broken one. It names paths in prose
                # instead, and the engine gate checks those paths exist.
                continue
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


class TestBytecodeStaysOutOfTheCheckout(unittest.TestCase):
    """#194: a script run as `__main__` writes no bytecode of its own, but the vendored
    scripts/factory modules it imports do -- into scripts/factory/__pycache__, a path no ownership
    row covers. The checkout that ran the script then reports it as untracked, and
    tools/dispatch-agent.sh refuses to open a worktree for the next issue. scripts/validate.sh and
    `factory verify` export PYTHONDONTWRITEBYTECODE, but an agent's shell exports nothing.

    What is asserted is where the flag sits, not that it appears: the loader reads it when the
    import happens, so a flag set after the path insert prevents exactly nothing."""

    SUPPRESSION = "sys.dont_write_bytecode = True"

    def emitted_python(self):
        """Every .py the factory writes into an engine and something runs as a command. The
        vendored scripts/factory modules are left out: they are the imported side, and a flag in
        them would be read too late to stop their own bytecode."""
        out = {relative: text for relative, text in generate.managed_files().items() if relative.endswith(".py")}
        for relative, (data, _) in gate.files(NAME).items():
            if relative.endswith(".py") and not relative.startswith("scripts/factory/"):
                out[relative] = data.decode("utf-8")
        return out

    def test_every_emitted_script_that_imports_the_vendored_factory_suppresses_bytecode(self):
        importers = {}
        for relative, text in self.emitted_python().items():
            lines = text.splitlines()
            reaches = next((i for i, line in enumerate(lines)
                            if "sys.path.insert" in line and "factory" in line), None)
            if reaches is None:
                continue
            importers[relative] = reaches
            # Column 0, so the flag is module level: map-overlay.py imports while it loads, and for
            # the two that import inside a function the line order below only means something if
            # the flag is not itself nested in some function that may never run.
            flag = next((i for i, line in enumerate(lines) if line == self.SUPPRESSION), None)
            self.assertIsNotNone(flag, f"{relative} puts scripts/factory on the path and leaves its "
                                       f"bytecode in the engine (#194)")
            self.assertLess(flag, reaches,
                            f"{relative} sets dont_write_bytecode at line {flag + 1}, after line "
                            f"{reaches + 1} reaches for scripts/factory; there it prevents nothing")
        # Named, so that an emitted script that starts importing the factory fails here rather than
        # being skipped by a check that examined whatever it happened to find.
        self.assertEqual(sorted(importers),
                         ["scripts/engine-gate.py", "scripts/map-overlay.py", "tools/entry-packet.py"])


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
        # `--no-verify` ends NOT VERIFIED (3), never 0: the engine was written but never built
        # or tested (tools/factory/__main__.py).
        self.assertEqual(code, factory.NOT_VERIFIED, output)
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


GOOD_PR_BODY = """## Linked issue

Closes #27

## Exact behavioural claim

Above 400 feet AGL outside a structure's 400-foot radius, `AltitudeLimit` now declines
`RequiresInterpretation` citing § 107.51(b) instead of answering 400.

## Scope, and what this deliberately does not do

Only the altitude limit. The speed limit's unit gap is untouched (#31).

## Map and rules conformance

- entry id(s): altitude-limit
- map package and version: RulesFactory.Maps.FaaPart107 4.0.0
- source locator(s): § 107.51(b)
- owner's rulings used, if any: none

## Tests and evidence

```
$ ./scripts/validate.sh full
==> [7] Build + test (Release, CI=true)
ok   test Release
validate.sh full: PASS
```

Mutations observed: `AltitudeLimit_DeclinesAboveTheCeiling` fails with the mutation "return the
ceiling instead of declining" (observed).

## Determinism

Nothing here reads the machine: no time, no locale, no ordering.

## Decisions and trade-offs

Declining rather than answering 400, because the corpus does not settle the radius case.

## Known limitations and unresolved behaviour

The structure-radius case still declines.

## Agent provenance

- implemented by: engine-dev
- structurally reviewed by: repo-steward
- semantically reviewed by: rules-conformance
- independently reviewed by: not required

## Unrelated changes

None
"""


class TestPrPolicy(RailsInAGitEngine):
    """`tools/pr-policy.py`: the contract, checked mechanically (#153)."""

    def pull_request(self, body=GOOD_PR_BODY, labels=("state:ready", "risk:normal"), files=None):
        self.fixture({
            "pr": {"5": {"number": 5, "title": "Implement the altitude limit", "body": body,
                         "files": files if files is not None else [{"path": "corpus-map.overlay.json"},
                                                                   {"path": f"src/{NAME}/Rules/AltitudeLimit.cs"}]}},
            "issue": {"27": {"number": 27, "state": "OPEN",
                             "labels": [{"name": name} for name in labels]}},
        })

    def policy_check(self):
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "pr-policy.py"), "5"],
                              cwd=self.out, capture_output=True, text=True, env=self.environment())

    def test_a_filled_pull_request_passes(self):
        self.produced()
        self.pull_request()
        done = self.policy_check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("satisfies the contract", done.stdout)
        self.assertIn("What this does not say", done.stdout, "it says what it did not check")

    def test_the_template_is_what_it_checks_against(self):
        # The template and the checker are emitted together, so a section renamed in one and not
        # the other would make every pull request fail. This is that pairing, asserted.
        self.produced()
        template = self.read(".github/pull_request_template.md")
        for name, _ in [("Linked issue", 0)]:
            self.assertIn(f"## {name}", template)
        headings = {line[3:].strip() for line in template.splitlines() if line.startswith("## ")}
        with open(os.path.join(self.out, "tools", "pr-policy.py"), encoding="utf-8") as handle:
            checker = handle.read()
        for heading in headings:
            self.assertIn(f'("{heading}"', checker, f"the template has `## {heading}` and pr-policy.py does not")

    def test_no_closes_is_a_finding(self):
        self.produced()
        self.pull_request(body=GOOD_PR_BODY.replace("Closes #27", "Related to #27"))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("no `Closes #<n>`", done.stdout)

    def test_two_closes_is_a_finding(self):
        self.produced()
        self.pull_request(body=GOOD_PR_BODY.replace("Closes #27", "Closes #27\nCloses #28"))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("closes 2 issues", done.stdout)

    def test_a_missing_section_is_named(self):
        self.produced()
        self.pull_request(body=GOOD_PR_BODY.split("## Determinism")[0])
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("## Determinism` is missing", done.stdout)
        self.assertIn("## Agent provenance` is missing", done.stdout)

    def test_a_claim_is_not_evidence(self):
        self.produced()
        body = GOOD_PR_BODY.replace("""```
$ ./scripts/validate.sh full
==> [7] Build + test (Release, CI=true)
ok   test Release
validate.sh full: PASS
```

Mutations observed: `AltitudeLimit_DeclinesAboveTheCeiling` fails with the mutation "return the
ceiling instead of declining" (observed).""", "Tests pass.")
        self.pull_request(body=body)
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("no command and no output", done.stdout)
        self.assertIn("names no mutation", done.stdout)

    def test_semantic_work_must_name_its_entry_and_locator(self):
        self.produced()
        conformance = GOOD_PR_BODY.split("## Map and rules conformance")[1].split("## Tests")[0]
        self.pull_request(body=GOOD_PR_BODY.replace(conformance, "\n\nN/A\n\n"))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("touches the semantic surface", done.stdout)

    def test_a_change_off_the_semantic_surface_need_not_name_an_entry(self):
        self.produced()
        conformance = GOOD_PR_BODY.split("## Map and rules conformance")[1].split("## Tests")[0]
        self.pull_request(body=GOOD_PR_BODY.replace(conformance, "\n\nN/A\n\n"),
                          files=[{"path": "README.md"}])
        done = self.policy_check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_provenance_must_say_who_reviewed(self):
        self.produced()
        self.pull_request(body=GOOD_PR_BODY.replace("- semantically reviewed by: rules-conformance",
                                                    "- semantically reviewed by:"))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("semantically reviewed", done.stdout)

    def test_the_issue_needs_exactly_one_risk_label(self):
        self.produced()
        self.pull_request(labels=("state:ready",))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("0 risk labels", done.stdout)

    def test_an_issue_awaiting_a_decision_cannot_be_closed_by_a_pull_request(self):
        self.produced()
        self.pull_request(labels=("state:needs-decision", "risk:normal"))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("cannot answer it for itself", done.stdout)


class TestVerdicts(RailsInAGitEngine):
    """`tools/record-verdict.py` and `tools/conformance-gate.py` (#153)."""

    def setUp(self):
        super().setUp()
        self.statuses = os.path.join(self.tmp, "statuses.json")

    def gh_with_statuses(self):
        """The stand-in, extended to answer `gh api` for commit statuses and to accept POSTs."""
        with open(self.gh, "w", encoding="utf-8") as handle:
            handle.write(GH_STUB.replace('fixture = json.load', '''
if argv_api := [a for a in sys.argv[1:] if a.startswith("repos/")]:
    pass
''' + 'fixture = json.load'))
        # Simpler: a purpose-built stub for the status API.
        with open(self.gh, "w", encoding="utf-8") as handle:
            handle.write(GH_STATUS_STUB)
        os.chmod(self.gh, 0o755)

    def record(self, *args):
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "record-verdict.py"), *args],
                              cwd=self.out, capture_output=True, text=True,
                              env={**self.environment(), "GH_STATUSES": self.statuses})

    def gate(self):
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "conformance-gate.py"), "5"],
                              cwd=self.out, capture_output=True, text=True,
                              env={**self.environment(), "GH_STATUSES": self.statuses})

    def scenario(self, head="a" * 40, labels=("state:ready", "risk:normal"), files=None):
        self.gh_with_statuses()
        self.fixture({
            "pr": {"5": {"number": 5, "headRefOid": head, "state": "OPEN",
                         "files": files if files is not None else [{"path": f"src/{NAME}/Rules/AltitudeLimit.cs"}],
                         "closingIssuesReferences": [{"number": 27}]}},
            "issue": {"27": {"number": 27, "labels": [{"name": name} for name in labels]}},
            "repo": {"nameWithOwner": "owner/engine"},
        })
        with open(self.statuses, "w", encoding="utf-8") as handle:
            json.dump({}, handle)

    def test_a_verdict_is_recorded_at_the_head_commit(self):
        self.produced()
        self.scenario()
        done = self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass")
        self.assertEqual(done.returncode, 0, done.stderr)
        recorded = json.load(open(self.statuses, encoding="utf-8"))
        self.assertEqual(recorded["a" * 40]["rules-verdict/semantic"], "success")

    def test_an_unconfigured_reviewer_is_refused_and_says_what_is_configured(self):
        self.produced()
        self.scenario()
        done = self.record("--pr", "5", "--reviewer", "a-friend", "--verdict", "pass")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not a reviewer this engine configures", done.stderr)
        self.assertIn("Known: semantic", done.stderr)
        self.assertIn("edit to .github/agent-policy.json", done.stderr)

    def test_the_gate_requires_a_semantic_verdict_for_semantic_work(self):
        self.produced()
        self.scenario()
        done = self.gate()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("rules-verdict/semantic is not recorded as a success", done.stdout)
        self.assertEqual(self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass").returncode, 0)
        done = self.gate()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_verdict_at_one_commit_does_not_satisfy_the_gate_at_another(self):
        self.produced()
        self.scenario(head="a" * 40)
        self.assertEqual(self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass").returncode, 0)
        self.assertEqual(self.gate().returncode, 0)
        # One more commit on the pull request: the verdict is on the bytes nobody is merging now.
        self.scenario(head="b" * 40)
        recorded = {"a" * 40: {"rules-verdict/semantic": "success"}}
        with open(self.statuses, "w", encoding="utf-8") as handle:
            json.dump(recorded, handle)
        done = self.gate()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("verdict on an earlier commit is a verdict on bytes nobody is merging", done.stdout)

    def test_a_recorded_failure_blocks_and_another_context_does_not_clear_it(self):
        self.produced()
        self.scenario(labels=("state:ready", "risk:independent-review"))
        self.assertEqual(self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass").returncode, 0)
        done = self.record("--pr", "5", "--reviewer", "codex", "--verdict", "fail", "--note", "row 7 is wrong")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("blocks the merge outright", done.stdout)
        self.assertEqual(self.record("--pr", "5", "--reviewer", "gemini", "--verdict", "pass").returncode, 0)
        done = self.gate()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("recorded as a failure", done.stdout)
        self.assertIn("does not clear it", done.stdout)

    def test_an_independent_risk_issue_needs_a_second_verdict(self):
        self.produced()
        self.scenario(labels=("state:ready", "risk:independent-review"))
        self.assertEqual(self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass").returncode, 0)
        done = self.gate()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("must also be recorded as a success", done.stdout)
        self.assertIn("rules-verdict/codex or rules-verdict/gemini", done.stdout)
        self.assertEqual(self.record("--pr", "5", "--reviewer", "codex", "--verdict", "pass").returncode, 0)
        self.assertEqual(self.gate().returncode, 0)

    def test_a_change_off_the_semantic_surface_needs_no_verdict(self):
        self.produced()
        self.scenario(files=[{"path": "README.md"}])
        done = self.gate()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("no rules verdict required", done.stdout)

    def test_the_chain_is_the_policy_s(self):
        self.produced()
        path = os.path.join(self.out, ".github", "agent-policy.json")
        settings = json.load(open(path, encoding="utf-8"))
        settings["review"]["independentFallback"] = [{"id": "acme", "context": "rules-verdict/acme"}]
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
        self.scenario(labels=("risk:independent-review",))
        self.assertEqual(self.record("--pr", "5", "--reviewer", "codex", "--verdict", "pass").returncode, 1,
                         "a provider the policy dropped is no longer a reviewer")
        self.assertEqual(self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass").returncode, 0)
        self.assertEqual(self.record("--pr", "5", "--reviewer", "acme", "--verdict", "pass").returncode, 0)
        self.assertEqual(self.gate().returncode, 0)


GH_STATUS_STUB = '''#!/usr/bin/env python3
"""A stand-in for `gh` that also keeps commit statuses in a JSON file."""
import json, os, sys

fixture = json.load(open(os.environ["GH_FIXTURE"], encoding="utf-8"))
store = os.environ["GH_STATUSES"]
argv = sys.argv[1:]

def statuses():
    try:
        return json.load(open(store, encoding="utf-8"))
    except Exception:
        return {}

if argv[0] == "api":
    endpoint = argv[1]
    if "-X" in argv and argv[argv.index("-X") + 1] == "POST":
        sha = endpoint.split("/statuses/")[1]
        fields = dict(argv[i + 1].split("=", 1) for i, a in enumerate(argv) if a == "-f")
        recorded = statuses()
        recorded.setdefault(sha, {})[fields["context"]] = fields["state"]
        json.dump(recorded, open(store, "w", encoding="utf-8"))
        print("{}")
    else:
        sha = endpoint.split("/commits/")[1].split("/status")[0]
        found = statuses().get(sha, {})
        print(json.dumps({"statuses": [{"context": c, "state": s} for c, s in found.items()]}))
    raise SystemExit(0)

if argv[0] == "repo":
    print(json.dumps(fixture["repo"]))
    raise SystemExit(0)

kind = argv[0]
number = argv[2] if len(argv) > 2 else ""
record = (fixture.get(kind) or {}).get(number)
if record is None:
    sys.stderr.write(f"no such {kind} {number}\\n")
    sys.exit(1)
fields = argv[argv.index("--json") + 1].split(",") if "--json" in argv else []
print(json.dumps({f: record.get(f) for f in fields}))
'''


FACTORY_STUB = '''#!/usr/bin/env python3
"""A stand-in for the factory's CLI. It records the version of itself that ran, and its arguments,
where the run can be seen afterwards."""
import json, sys

argv = sys.argv[1:]
out = argv[argv.index("--out") + 1]
with open(out + "/re-produced-by.json", "w", encoding="utf-8") as handle:
    json.dump({"version": "@VERSION@", "argv": argv}, handle)
print("stub factory @VERSION@ produced into " + out)
'''


class TestReProduce(RailsInAGitEngine):
    """`tools/re-produce.sh`: the one command an overlay edit is finished with (#192).

    The factory is a stand-in here, in a git repository of its own with two commits: the one the
    engine's record names, and a later `main`. Which of the two runs is the whole point -- checking
    out `main` would re-emit the gate, the rails and the vendored generator from a factory nobody
    asked for, into an implementation pull request.
    """

    def factory_repo(self):
        """A repository whose recorded commit and whose `main` are different factories."""
        repo = os.path.join(self.tmp, "factory-stub")
        os.makedirs(os.path.join(repo, "tools", "factory"))
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "t@example.invalid")
        git(repo, "config", "user.name", "t")
        commits = {}
        for version in ("recorded", "main"):
            with open(os.path.join(repo, "tools", "factory", "__main__.py"), "w", encoding="utf-8") as handle:
                handle.write(FACTORY_STUB.replace("@VERSION@", version))
            git(repo, "add", ".")
            git(repo, "commit", "-qm", version)
            commits[version] = git(repo, "rev-parse", "HEAD")
        return repo, commits

    def commit_engine_as_is(self):
        """`commit_engine`, without producing again: the record is already pointed at the stub."""
        git(self.out, "init", "-q", "-b", "main")
        git(self.out, "config", "user.email", "t@example.invalid")
        git(self.out, "config", "user.name", "t")
        git(self.out, "add", ".")
        git(self.out, "commit", "-qm", "the produced engine")

    def record_commit(self, commit):
        """Point the engine's record at `commit`, as a produce from that factory would have."""
        path = os.path.join(self.out, "provenance.json")
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        record["factory"]["commit"] = commit
        record["factory"]["dirty"] = False
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record, indent=2, ensure_ascii=False) + "\n")

    def re_produce(self, *args, repo=None, **extra):
        environment = self.environment(**extra)
        if repo is not None:
            environment["RULES_ENGINE_FACTORY_REPO"] = repo
        return subprocess.run(["bash", os.path.join(self.out, "tools", "re-produce.sh"), *args],
                              cwd=self.out, capture_output=True, text=True, env=environment)

    def test_it_re_produces_from_the_commit_the_record_names_and_never_main(self):
        self.produced()
        repo, commits = self.factory_repo()
        self.record_commit(commits["recorded"])
        self.commit_engine_as_is()
        done = self.re_produce(repo=repo)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        with open(os.path.join(self.out, "re-produced-by.json"), encoding="utf-8") as handle:
            ran = json.load(handle)
        self.assertEqual(ran["version"], "recorded",
                         "the clone took the factory's main, not the commit provenance.json names")
        self.assertEqual(ran["argv"][0], "produce")
        self.assertIn("--package", ran["argv"])
        self.assertEqual(ran["argv"][ran["argv"].index("--name") + 1], NAME)
        self.assertEqual(ran["argv"][ran["argv"].index("--out") + 1], self.out)
        self.assertTrue(ran["argv"][ran["argv"].index("--corpus") + 1].endswith("/corpus/part107.xml"),
                        ran["argv"])

    def test_dry_run_prints_the_produce_it_would_run_and_does_nothing(self):
        self.produced()
        repo, commits = self.factory_repo()
        self.record_commit(commits["recorded"])
        done = self.re_produce("--dry-run", repo=repo)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(commits["recorded"], done.stdout)
        self.assertRegex(done.stdout, r"produce\s+\S*python3 \S+/tools/factory produce --package \S+@\S+ "
                                      r"--corpus \S+ --name " + NAME + r" --out \S+")
        self.assertIn("nothing was cloned, produced or committed", done.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.out, "re-produced-by.json")))

    def test_extra_arguments_reach_produce(self):
        self.produced()
        repo, commits = self.factory_repo()
        self.record_commit(commits["recorded"])
        self.commit_engine_as_is()
        done = self.re_produce("--no-verify", repo=repo)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        with open(os.path.join(self.out, "re-produced-by.json"), encoding="utf-8") as handle:
            self.assertIn("--no-verify", json.load(handle)["argv"])

    def test_it_makes_no_commit(self):
        self.produced()
        repo, commits = self.factory_repo()
        self.record_commit(commits["recorded"])
        self.commit_engine_as_is()
        head = git(self.out, "rev-parse", "HEAD")
        done = self.re_produce(repo=repo)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(git(self.out, "rev-parse", "HEAD"), head, "re-produce.sh committed")
        self.assertIn("re-produced-by.json", git(self.out, "status", "--porcelain"))
        self.assertIn("No commit was made", done.stdout)

    def test_an_uncommitted_change_to_the_recorded_factory_commit_is_refused(self):
        """The one thing that must not be in doubt: which factory is about to rewrite this engine.

        A dirty tree is otherwise the normal case -- this is run *after* an overlay edit and a
        regeneration -- so only the field the script obeys is compared with the committed record.
        """
        self.produced()
        repo, commits = self.factory_repo()
        self.record_commit(commits["recorded"])
        self.commit_engine_as_is()
        self.record_commit(commits["main"])  # a hand edit redirecting the clone
        done = self.re_produce(repo=repo)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("names factory.commit", done.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.out, "re-produced-by.json")))
        # and an edit that leaves that field alone does not stop it: the overlay is expected to move
        with open(os.path.join(self.out, "corpus-map.overlay.json"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        self.record_commit(commits["recorded"])
        self.assertEqual(self.re_produce(repo=repo).returncode, 0)


class TestTheEngineGateChecksItsOwnRails(TestAProducedEngine):
    """`scripts/engine-gate.py rails`: the rails held to their own word (#153, 0029 §8 and §9)."""

    def rails(self):
        return subprocess.run([sys.executable, os.path.join(self.out, "scripts", "engine-gate.py"), "rails"],
                              cwd=self.out, capture_output=True, text=True)

    def test_a_freshly_produced_engine_passes(self):
        self.produced()
        done = self.rails()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("the rails hold", done.stdout)

    def test_a_reviewer_charter_that_can_write_fails(self):
        self.produced()
        path = os.path.join(self.out, ".claude", "agents", "rules-conformance.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace("tools: Read, Grep, Glob", "tools: Read, Grep, Glob, Bash"))
        done = self.rails()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("grants bash", done.stderr.lower())

    def test_a_reviewer_charter_with_no_tool_list_fails(self):
        self.produced()
        path = os.path.join(self.out, ".claude", "agents", "repo-steward.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace("tools: Read, Grep, Glob\n", ""))
        done = self.rails()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("inherits every tool", done.stderr)

    def test_a_rail_citing_a_document_the_engine_does_not_have_fails(self):
        self.produced()
        with open(os.path.join(self.out, "AGENTS.md"), "a", encoding="utf-8") as handle:
            handle.write("\nSee [the runbook](docs/runbook-that-was-deleted.md).\n")
        done = self.rails()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("docs/runbook-that-was-deleted.md", done.stderr)

    def test_a_rail_naming_a_command_the_engine_does_not_have_fails(self):
        # The predecessor's failure exactly: enforcement shipped beside documents and tools it
        # cited and did not have, several inside runtime error messages.
        self.produced()
        with open(os.path.join(self.out, "AGENTS.md"), "a", encoding="utf-8") as handle:
            handle.write("\nRun `tools/reconcile-the-map.py` before opening a pull request.\n")
        done = self.rails()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("tools/reconcile-the-map.py", done.stderr)
        self.assertIn("does not have", done.stderr)

    def test_a_policy_without_an_independent_chain_fails(self):
        self.produced()
        path = os.path.join(self.out, ".github", "agent-policy.json")
        policy = json.load(open(path, encoding="utf-8"))
        policy["review"]["independentFallback"] = []
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(policy, handle, indent=2)
        done = self.rails()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("can never be merged", done.stderr)

    def test_a_policy_link_without_its_own_context_fails(self):
        self.produced()
        path = os.path.join(self.out, ".github", "agent-policy.json")
        policy = json.load(open(path, encoding="utf-8"))
        policy["review"]["independentFallback"] = [{"id": "acme"}]
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(policy, handle, indent=2)
        done = self.rails()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("cannot be told", done.stderr)

    def test_an_unreadable_policy_fails(self):
        self.produced()
        with open(os.path.join(self.out, ".github", "agent-policy.json"), "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        done = self.rails()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("cannot read their own configuration", done.stderr)

    def test_the_gate_runs_it(self):
        self.produced()
        self.assertIn('"${GATE[@]}" rails', self.read("scripts/validate.sh"))


RAILS_GH_STUB = '''#!/usr/bin/env python3
"""A stand-in for `gh` holding one repository's labels, rulesets and settings in a JSON file."""
import json, os, sys

store = os.environ["GH_REPO_STATE"]
state = json.load(open(store, encoding="utf-8"))
argv = sys.argv[1:]


def save():
    json.dump(state, open(store, "w", encoding="utf-8"))


def fields():
    out = {}
    for i, a in enumerate(argv):
        if a in ("-f", "-F"):
            key, value = argv[i + 1].split("=", 1)
            out[key] = {"true": True, "false": False}.get(value, value)
    return out


if argv[0] == "repo" and argv[1] == "view":
    print(json.dumps({"nameWithOwner": state["repo"]}))
    raise SystemExit(0)

assert argv[0] == "api", argv
endpoint = argv[1]
method = argv[argv.index("-X") + 1] if "-X" in argv else "GET"
path = endpoint.split("/")

if endpoint == f"repos/{state['repo']}":
    if method == "PATCH":
        state["settings"].update(fields())
        save()
    print(json.dumps({"default_branch": state["branch"], **state["settings"]}))
elif endpoint.startswith(f"repos/{state['repo']}/labels"):
    if method == "POST":
        state["labels"].append(fields()["name"])
        save()
        print("{}")
    else:
        print(json.dumps([{"name": n} for n in state["labels"]]))
elif endpoint.startswith(f"repos/{state['repo']}/rulesets"):
    rest = endpoint.split("/rulesets")[1].strip("/")
    if method == "POST":
        payload = json.load(sys.stdin)
        payload["id"] = len(state["rulesets"]) + 1
        state["rulesets"].append(payload)
        save()
        print(json.dumps(payload))
    elif method == "PUT":
        payload = json.load(sys.stdin)
        payload["id"] = int(rest)
        state["rulesets"] = [payload if r["id"] == payload["id"] else r for r in state["rulesets"]]
        save()
        print(json.dumps(payload))
    elif rest:
        (found,) = [r for r in state["rulesets"] if r["id"] == int(rest)]
        print(json.dumps(found))
    else:
        print(json.dumps([{"id": r["id"], "name": r["name"]} for r in state["rulesets"]]))
else:
    sys.exit(f"unexpected gh api call: {endpoint}")
'''


class TestFactoryRails(TestAProducedEngine):
    """`factory rails --check` and `--apply` (#155, decision 0029 §10)."""

    REPO = "owner/engine"

    def setUp(self):
        super().setUp()
        self.state_path = os.path.join(self.tmp, "repo.json")
        self.gh = os.path.join(self.tmp, "gh-repo.py")
        with open(self.gh, "w", encoding="utf-8") as handle:
            handle.write(RAILS_GH_STUB)
        os.chmod(self.gh, 0o755)
        self.repo_state(labels=[], rulesets=[],
                        settings={"allow_merge_commit": True, "allow_squash_merge": True,
                                  "allow_rebase_merge": True})

    def repo_state(self, **overrides):
        document = {"repo": self.REPO, "branch": "main", **overrides}
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)

    def read_state(self):
        with open(self.state_path, encoding="utf-8") as handle:
            return json.load(handle)

    def rails(self, *args):
        buffer = io.StringIO()
        environment = dict(os.environ, FACTORY_GH=self.gh, GH_REPO_STATE=self.state_path)
        old = dict(os.environ)
        os.environ.update(environment)
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                code = factory.main(["rails", "--repo", self.REPO, "--dir", self.out, *args])
        finally:
            os.environ.clear()
            os.environ.update(old)
        return code, buffer.getvalue()

    def test_check_on_a_bare_repository_says_what_is_missing_and_changes_nothing(self):
        self.produced()
        before = self.read_state()
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("Agent files", output)
        self.assertIn("OK", output)
        self.assertIn("MISSING", output)
        self.assertIn("a workflow that exists is not a workflow that is required", output)
        self.assertEqual(self.read_state(), before, "--check changed the repository")

    def test_check_names_the_configured_chain(self):
        self.produced()
        code, output = self.rails("--check")
        self.assertIn("Review chain", output)
        self.assertIn("codex -> gemini -> in-house-independent", output)

    def test_apply_creates_the_labels_the_ruleset_and_the_merge_policy(self):
        self.produced()
        code, output = self.rails("--apply")
        self.assertEqual(code, 0, output)
        state = self.read_state()
        self.assertEqual(sorted(state["labels"]),
                         ["risk:independent-review", "risk:normal", "state:blocked",
                          "state:needs-decision", "state:ready"])
        (ruleset,) = state["rulesets"]
        self.assertEqual(ruleset["name"], "rules-factory-agent-rails")
        self.assertEqual(ruleset["enforcement"], "active")
        self.assertEqual(ruleset["bypass_actors"], [])
        rules = {rule["type"]: rule.get("parameters", {}) for rule in ruleset["rules"]}
        self.assertEqual({check["context"] for check in rules["required_status_checks"]["required_status_checks"]},
                         {"validate", "pr-policy", "conformance-gate"})
        self.assertTrue(rules["required_status_checks"]["strict_required_status_checks_policy"])
        self.assertTrue(rules["pull_request"]["required_review_thread_resolution"])
        self.assertEqual(rules["pull_request"]["allowed_merge_methods"], ["merge"])
        self.assertIn("deletion", rules)
        self.assertIn("non_fast_forward", rules)
        self.assertEqual(state["settings"], {"allow_merge_commit": True, "allow_squash_merge": False,
                                             "allow_rebase_merge": False})
        self.assertIn("The rails are in place on GitHub, not merely present", output)

    def test_apply_twice_changes_nothing_the_second_time(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        first = self.read_state()
        code, output = self.rails("--apply")
        self.assertEqual(code, 0, output)
        self.assertIn("nothing to do: the rails are already in place", output)
        self.assertEqual(self.read_state(), first)

    def test_apply_leaves_another_ruleset_byte_identical(self):
        self.produced()
        theirs = {"id": 99, "name": "someone-elses-ruleset", "target": "branch", "enforcement": "active",
                  "rules": [{"type": "required_signatures"}]}
        self.repo_state(labels=[], rulesets=[theirs],
                        settings={"allow_merge_commit": True, "allow_squash_merge": True,
                                  "allow_rebase_merge": True})
        self.assertEqual(self.rails("--apply")[0], 0)
        state = self.read_state()
        self.assertIn(theirs, state["rulesets"], "the factory edited a ruleset it does not own")
        self.assertEqual(len(state["rulesets"]), 2)

    def test_a_ruleset_that_is_only_evaluated_is_not_in_place(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        state = self.read_state()
        state["rulesets"][0]["enforcement"] = "evaluate"
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("is not active", output)

    def test_a_dropped_required_check_is_reported_and_put_back(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        state = self.read_state()
        for rule in state["rulesets"][0]["rules"]:
            if rule["type"] == "required_status_checks":
                rule["parameters"]["required_status_checks"] = [{"context": "validate"}]
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("conformance-gate is not a required check", output)
        self.assertEqual(self.rails("--apply")[0], 0)

    def test_a_bypass_actor_is_reported(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        state = self.read_state()
        state["rulesets"][0]["bypass_actors"] = [{"actor_id": 5, "actor_type": "RepositoryRole"}]
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("may bypass", output)

    def test_squash_merging_is_reported(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        state = self.read_state()
        state["settings"]["allow_squash_merge"] = True
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("squash or rebase merging is still on", output)
        self.assertIn("the repository still allows squash or rebase merging", output)

    def test_an_engine_with_no_policy_is_refused(self):
        self.produced()
        os.remove(os.path.join(self.out, ".github", "agent-policy.json"))
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("rails REFUSED", output)

    def test_a_repo_that_is_not_owner_name_is_refused(self):
        self.produced()
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["rails", "--repo", "engine", "--dir", self.out, "--check"])
        self.assertEqual(code, 1, buffer.getvalue())
        self.assertIn("is not owner/name", buffer.getvalue())


class TestTheDoctor(TestAProducedEngine):
    """`tools/agent-doctor.py`: active, or merely present? (#155)"""

    def doctor(self, *args, **environment):
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "agent-doctor.py"), *args],
                              cwd=self.out, capture_output=True, text=True,
                              env={**os.environ, **environment})

    def test_local_says_the_remote_half_was_not_examined(self):
        self.produced()
        done = self.doctor("--local")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("NOT EXAMINED", done.stdout)
        self.assertIn("says nothing about what GitHub enforces", done.stdout)
        self.assertIn("Rail files ", done.stdout)
        self.assertIn("Guard wired to the tools", done.stdout)

    def test_a_guard_nothing_invokes_is_reported(self):
        self.produced()
        path = os.path.join(self.out, ".claude", "settings.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"hooks": {}}, handle)
        done = self.doctor("--local")
        self.assertIn("not wired into .claude/settings.json", done.stdout)

    def test_a_missing_rail_is_reported(self):
        self.produced()
        os.remove(os.path.join(self.out, "tools", "record-verdict.py"))
        done = self.doctor("--local")
        self.assertIn("are not in this engine", done.stdout)
