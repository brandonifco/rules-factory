#!/usr/bin/env python3
"""The agent rails a produced engine ships with (#151, decision 0029).

Asserted here, about the bytes the factory emits rather than about a GitHub repository:

  * every link in an emitted rail resolves **in an engine**, which is the one place they can be
    judged -- `AGENTS.md` sits at an engine's root, not in `tools/factory/recipe/rails/`, so
    scripts/validate.sh's repository-wide link check skips that directory and this replaces it.
    The predecessor shipped 61 references to files that did not exist, several inside runtime
    error messages, and a rail that cites a document the factory does not emit is that failure;
  * every command an emitted rail tells an agent to run is one it can run: run as written against
    a produced engine, none of them refuses the call itself. The charter shipped
    `scripts/engine-gate.py regenerate --write` as "how you run it", and run as written it exits 2
    asking for five arguments only a restored project can supply (#203). A rail here is read by
    agents, which take a backticked command as a command to run;
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

Run: python3 -m pytest tools/tests/factory/test_factory_rails.py
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
import unittest.mock
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
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
import agentrails  # noqa: E402
import scaffold  # noqa: E402
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


def write_overlay(engine, items):
    """Replace the engine's overlay/ with one file per entry of `items` (#247)."""
    directory = os.path.join(engine, "overlay")
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            os.remove(os.path.join(directory, name))
    os.makedirs(directory, exist_ok=True)
    for entry_id, item in items.items():
        with open(os.path.join(directory, f"{entry_id}.json"), "w", encoding="utf-8") as handle:
            json.dump(item, handle, indent=2)
            handle.write("\n")


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
        self.rails = agentrails.rails_files()
        self.emitted = {**scaffold.managed_files(), ".github/agent-policy.json": agentrails.agent_policy()}

    def test_every_rail_is_a_managed_row_of_the_table(self):
        managed = {row.pattern for row in ownership.managed_rows("")}
        self.assertTrue(set(self.rails) <= managed, sorted(set(self.rails) - managed))

    def test_every_link_in_a_rail_resolves_in_an_engine(self):
        # The engine an emitted rail lives in: every path the factory writes for a named engine,
        # plus the directories those paths imply.
        model = type("M", (), {"name": NAME, "rulings": (), "entries": ()})()
        layout = set(self.emitted) | {"scripts/validate.sh", "provenance.json", "overlay/x.json",
                                      "docs/decisions", "corpus"}
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
        policy = json.loads(agentrails.agent_policy())
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
        out = {relative: text for relative, text in scaffold.managed_files().items() if relative.endswith(".py")}
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
                         ["scripts/engine-gate.py", "scripts/map-overlay.py", "tools/agent-doctor.py",
                          "tools/entry-packet.py", "tools/pr-policy.py"])


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
        for relative in list(agentrails.rails_files()) + [".github/agent-policy.json"]:
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
        self.assertEqual(self.read("AGENTS.md"), agentrails.rails_files()["AGENTS.md"])


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

    def regenerate(self):
        """The generated C# as the gate rewrites it from the overlay as it stands."""
        record = json.loads(self.read("provenance.json"))
        done = subprocess.run([sys.executable, os.path.join(self.out, "scripts", "engine-gate.py"), "regenerate",
                               "--write", "--package-map", self.PACKAGE_MAP,
                               "--package-manifest", os.path.join(PART107, "corpus-manifest.json"),
                               "--package-id", record["map"]["packageId"],
                               "--package-version", record["map"]["version"], "--name", NAME],
                              capture_output=True, text=True, cwd=self.out)
        self.assertIn(done.returncode, (0, 1), done.stdout + done.stderr)
        return done

    def test_the_packet_declares_the_handler_the_build_declares_once_the_entry_is_implemented(self):
        """§7 is the assignment, and the assignment is the declaration the work produces (#204).

        `speed-limit` is `mapped`, so `Contracts.g.cs` holds the optional hook today and the
        required partial the moment the overlay says `implemented` -- which is the first thing the
        implementer does. A packet rendering the file as it stands is right about the present and
        wrong about the work, and costs one rewrite of the handler file. So the packet is read
        before the overlay moves and checked against the file after it has moved and been
        regenerated: the two are the same bytes or the packet is describing the wrong state.
        """
        self.produced()
        text = self.rendered("speed-limit")
        signature = next(line for line in text.splitlines()
                         if "SpeedLimit(" in line and "partial" in line).strip()

        write_overlay(self.out, {"speed-limit": {"status": "implemented", "implementedIn": "Rules/SpeedLimit.cs",
                                                "tests": [{"name": "SpeedLimit_DeclinesTheUnsettledQuestion",
                                                           "mutation": "answer it instead of declining"}]}})
        done = self.regenerate()
        contracts = self.read(f"src/{NAME}/Generated/Contracts.g.cs")
        self.assertIn(signature, contracts,
                      f"the packet's §7 signature is not the one the implemented entry declares\n{done.stdout}")
        self.assertIn("internal static partial Resolution<object> SpeedLimit(", signature,
                      "the required form is what an implemented entry off row 8 declares; the packet showed "
                      "something else, and the check above would then be comparing two wrong things")

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
import base64, json, os, sys

fixture = json.load(open(os.environ["GH_FIXTURE"], encoding="utf-8"))
argv = sys.argv[1:]
kind = argv[0] if argv else ""
if kind == "api":
    # `gh api repos/{owner}/{repo}/contents/<path>?ref=<sha> --jq .content`: a file at the base
    # commit, base64 as GitHub returns it. pr-policy.py reads the record this way and then hashes
    # each deleted retired path's bytes against it (#243).
    route, _, query = argv[1].partition("?")
    ref = query.split("ref=")[-1]
    wanted = route.split("/contents/", 1)[1] if "/contents/" in route else ""
    body = ((fixture.get("contents") or {}).get(ref) or {}).get(wanted)
    if body is None:
        sys.stderr.write(f"no {wanted} at {ref}\\n")
        sys.exit(1)
    print(base64.b64encode(body.encode("utf-8")).decode("ascii"))
    sys.exit(0)
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

    def test_the_closing_order_names_the_re_produce_before_the_gate(self):
        """The last thing dispatch prints is an order an implementer can follow to a green gate.

        Marking an entry `implemented` edits the overlay, and since #192 the gate's provenance step
        fails by design until `tools/re-produce.sh` has run, so the gate alone -- which is what
        dispatch used to close with -- is an order no entry implementation can follow (#202). The
        order is asserted rather than the two lines' presence: printing both in the wrong order is
        the defect, and the drift this holds shut.
        """
        self.commit_engine()
        self.issue(27)
        done = self.dispatch("27")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("tools/re-produce.sh", done.stdout, "dispatch does not mention the re-produce at all")
        self.assertLess(done.stdout.index("tools/re-produce.sh"), done.stdout.index("scripts/validate.sh"),
                        f"dispatch tells the implementer to run the gate before the re-produce:\n{done.stdout}")

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

    def test_a_factory_update_is_filed_at_the_ready_state_and_normal_risk(self):
        # #193: a `factory produce` update is work under the rails like any other, so it is filed
        # like any other. The flag swaps the body and promotes nothing: what moved decides the
        # risk, and that is the orchestrator's judgement (0029 section 3), not a flag's.
        self.produced()
        done = self.new_issue("--title", "Take the engine to the next map version", "--produce", "--dry-run")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("labels: state:ready,risk:normal", done.stdout)
        self.assertIn("## What moves", done.stdout)
        self.assertIn("## Produced by the factory", done.stdout)
        self.assertIn("separate issue, because it is a rules decision the factory did not make", done.stdout)
        self.assertNotIn("risk:independent-review", done.stdout)

    def test_a_factory_update_body_and_a_body_file_are_refused_together(self):
        self.produced()
        path = os.path.join(self.tmp, "body.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("## What this is\n\nmine\n")
        done = self.new_issue("--title", "x", "--produce", "--body-file", path, "--dry-run")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("both say what the body is", done.stderr)

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
        write_overlay(self.out, {"altitude-limit": {
            "status": "implemented", "implementedIn": "Rules/AltitudeLimit.cs",
            "tests": [{"name": "AltitudeLimit_DeclinesAboveTheCeiling",
                       "mutation": "return the ceiling instead of declining"}]}})
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
                         "files": [{"path": "overlay/altitude-limit.json"},
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

    #: The base commit's SHA in these fixtures, and the key its provenance.json is filed under.
    BASE = "0000000000000000000000000000000000000000"

    def pull_request(self, body=GOOD_PR_BODY, labels=("state:ready", "risk:normal"), files=None,
                     changed_files=None, base_record=None):
        files = files if files is not None else [{"path": "overlay/altitude-limit.json"},
                                                 {"path": f"src/{NAME}/Rules/AltitudeLimit.cs"}]
        self.fixture({
            # `changedFiles` is GitHub's own count, and defaults here to the length of the list:
            # a fixture where they disagree is a truncated list, which is its own test below.
            "pr": {"5": {"number": 5, "title": "Implement the altitude limit", "body": body,
                         "files": files, "baseRefOid": self.BASE,
                         "changedFiles": len(files) if changed_files is None else changed_files}},
            "issue": {"27": {"number": 27, "state": "OPEN",
                             "labels": [{"name": name} for name in labels]}},
            # `gh api .../contents/<path>?ref=<base>`: the base commit's files, read only when a
            # retired path is in the diff (#243). Absent unless a test puts them there.
            "contents": {self.BASE: base_record} if base_record is not None else {},
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

    def test_a_truncated_file_list_is_refused_rather_than_judged(self):
        # `gh pr view --json files` caps at 100 with no error (#193). Everything pr-policy.py
        # decides about the diff comes from that list, so half of it is not a smaller diff.
        self.produced()
        self.pull_request(files=[{"path": "README.md"}], changed_files=140)
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("GitHub returned 1 of this pull request's 140 changed files", done.stdout)
        self.assertIn("cannot be decided from a partial list", done.stdout)


# The `## Produced by the factory` section, filled as `factory produce --produce-report` gives it.
# The three facts are substituted from the engine's own provenance.json at the moment of the test:
# they are the claim, and a claim the tree does not bear out is refused (#193).
PRODUCE_SECTION = """## Produced by the factory

<!-- rules-factory-produce -->

- factory version: {factory}
- map package and version: {map}
- kernel version: {kernel}
- what moved: the map, 3.0.0 to {version}
"""
PRODUCE_EVIDENCE = """```
$ python3 tools/factory produce --package ... --out .
produced in ., verified
$ ./scripts/validate.sh full
validate.sh full: PASS
$ python3 tools/factory provenance --engine .
provenance of .: every field matches
```
"""


class TestAProduceUpdateIsAPullRequestLikeAnyOther(TestPrPolicy):
    """`tools/pr-policy.py` produce mode: a closed predicate, not an escape hatch (#193).

    A `factory produce` update to an engine cannot honestly name a mutation (it writes no test) or
    a single entry and locator (a map bump regenerates every entry), and until #193 the rails it
    installs could not accept the pull request that installs them. What is asserted here is the
    shape of the relaxation and, more than that, its edges: the `files` list comes from a real
    produced tree rather than from invented path strings, so the ownership predicate is exercised
    against what `produce` actually wrote, and the test that matters is the one where a single
    hand-written file is smuggled in beside them.
    """

    def record(self):
        return json.loads(self.read("provenance.json"))

    def write_record(self, record):
        with open(os.path.join(self.out, "provenance.json"), "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2)

    def commit_engine(self):
        """The produced engine, committed, with a record saying the factory was clean.

        Every engine in these tests is produced `--allow-dirty`, because the factory checkout a
        test runs in usually has uncommitted changes. A real factory update is produced from a
        clean factory and the predicate requires it, so the record is corrected here once; the test
        that is about a dirty record puts it back.
        """
        super().commit_engine()
        record = self.record()
        record["factory"]["dirty"] = False
        self.write_record(record)

    def produced_files(self, extra=(), limit=40):
        """Paths a real produce wrote into this engine, as GitHub would list them.

        Read back out of provenance.json's own `generated` and `managed` sections, so a file the
        factory stops writing (or starts writing) changes this fixture without anybody editing it.
        """
        record = self.record()
        # provenance.json is written last and so is not in its own `generated` list, but it is in
        # every real produce's diff -- and it is the file the declaration is checked against.
        paths = ["provenance.json"] + [item["path"] for item in record["generated"][:limit]]
        paths += [item["path"] for item in record["managed"][:5]]
        # `changeType` is what GitHub reports and what the produce predicate reads: a retired path
        # is the factory's when deleted and nobody's otherwise (#243). `extra` may carry its own.
        return ([{"path": path, "changeType": "MODIFIED"} for path in paths]
                + [item if isinstance(item, dict) else {"path": item, "changeType": "MODIFIED"}
                   for item in extra])

    def produce_body(self, section=None, evidence=PRODUCE_EVIDENCE, conformance=None):
        """GOOD_PR_BODY turned into the factory update it would be: the produce section added, the
        entry and locator dropped, and the produce evidence in place of the mutation."""
        record = self.record()
        body = GOOD_PR_BODY
        if section is None:
            section = PRODUCE_SECTION.format(factory=record["factory"]["version"],
                                             map=f"{record['map']['packageId']} {record['map']['version']}",
                                             kernel=record["kernel"]["version"], version=record["map"]["version"])
        body = body.replace("## Exact behavioural claim", f"{section}\n## Exact behavioural claim")
        body = body.replace("""- entry id(s): altitude-limit
- map package and version: RulesFactory.Maps.FaaPart107 4.0.0
- source locator(s): § 107.51(b)
- owner's rulings used, if any: none""",
                            conformance if conformance is not None else
                            f"- map package and version: {record['map']['packageId']} {record['map']['version']}")
        old_evidence = GOOD_PR_BODY.split("## Tests and evidence")[1].split("## Determinism")[0]
        return body.replace(old_evidence, f"\n\n{evidence}\n") if evidence is not None else body

    def produce_request(self, body=None, **extra):
        self.commit_engine()
        self.pull_request(body=self.produce_body() if body is None else body,
                          files=extra.pop("files", None) or self.produced_files(), **extra)

    def test_a_produce_update_passes(self):
        self.produce_request()
        done = self.policy_check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("claim was admitted", done.stdout)
        self.assertIn("waived no verdict", done.stdout)

    def test_it_need_not_name_a_mutation(self):
        self.produce_request()
        done = self.policy_check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("names no mutation", done.stdout)

    def test_it_need_not_name_an_entry_or_a_locator(self):
        self.produce_request()
        done = self.policy_check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("the entry id", done.stdout)
        self.assertNotIn("the locator", done.stdout)

    def test_one_hand_written_file_voids_the_claim_and_is_named(self):
        # The escape-hatch test. Everything else in this class is about a claim that holds; this is
        # the one that says the claim is a predicate over the diff and not a sentence in the body.
        smuggled = f"src/{NAME}/Rules/AltitudeLimit.cs"
        self.commit_engine()
        self.pull_request(body=self.produce_body(), files=self.produced_files(extra=[smuggled]))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn(smuggled, done.stdout)
        self.assertIn("not files a produce writes", done.stdout)
        self.assertIn("claim is void", done.stdout)
        # And, having been voided, the pull request is held to the whole contract again.
        self.assertIn("names no mutation", done.stdout)

    RETIRED_GONE = ["backlog/001-speed-limit.md", "backlog/README.md"]

    def retired_base(self, paths=None, edited=()):
        """The base commit's files: a record that hashed those retired paths, and the paths themselves.

        The bytes are here, not only the hashes, because pr-policy fetches and hashes them -- the
        same test `ownership.remove_retired` applies. `edited` names paths whose committed bytes have
        moved since the record hashed them, which is the hand-edit case the record alone misses.
        """
        record = self.record()
        listed = self.RETIRED_GONE if paths is None else paths
        contents, generated = {}, list(record["generated"])
        for path in listed:
            text = f"# committed by a produce before #243: {path}\n"
            generated.append({"path": path, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
            contents[path] = f"{text}hand-edited after the last produce\n" if path in edited else text
        record["generated"] = generated
        contents["provenance.json"] = json.dumps(record)
        return contents

    def retired_files(self, change="REMOVED"):
        return self.produced_files(extra=[{"path": path, "changeType": change} for path in self.RETIRED_GONE])

    def test_a_retired_path_the_produce_deleted_does_not_void_the_claim(self):
        """#243: the migration produce deletes the engine's committed `backlog/`.

        Those paths match no row of the ownership table -- nothing writes them any more -- so
        without `ownership.RETIRED` every migration pull request would have its produce claim voided
        by the nineteen deletions the produce itself made. Admitted only as a **deletion**, and only
        because the **base commit's record** says the factory wrote those files: the two other
        tests below are the same diff with each of those two facts taken away.
        """
        self.commit_engine()
        self.pull_request(body=self.produce_body(), files=self.retired_files(), base_record=self.retired_base())
        done = self.policy_check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("claim was admitted", done.stdout)
        self.assertNotIn("not files a produce writes", done.stdout)

    #: What the pre-#247 shared overlay held, and what `overlay/` must carry for its deletion to be
    #: the factory's. Two entries, because a split that dropped one is the failure being ruled out.
    SHARED_OVERLAY = {"altitude-limit": {"status": "blocked"},
                      "speed-limit": {"status": "implemented", "implementedIn": "Rules/SpeedLimit.cs",
                                      "tests": [{"test": "T.t", "mutation": "returned 88 for 87; it went red"}]}}

    def overlay_base(self, document=None):
        """A base commit holding `corpus-map.overlay.json`, as every engine before #247 did.

        Its hash is in `buildInputs` and not in `generated` or `managed`, because the factory never
        wrote the engine's evidence -- which is exactly why the record cannot authorise this
        deletion and the split's witness has to.
        """
        record = self.record()
        text = json.dumps(document if document is not None else self.SHARED_OVERLAY, indent=2) + "\n"
        record["buildInputs"] = list(record["buildInputs"]) + [
            {"path": "corpus-map.overlay.json", "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}]
        return {"corpus-map.overlay.json": text, "provenance.json": json.dumps(record)}

    def test_the_split_s_deletion_of_the_shared_overlay_does_not_void_the_claim(self):
        """#247: the migration produce deletes `corpus-map.overlay.json` after splitting it.

        The record cannot say the factory wrote that file, because it never did -- it is the
        engine's own evidence. What admits the deletion is `overlay.superseded_by_split`, the
        witness the remover itself uses, reading the head tree: every key the deleted file held is
        in an `overlay/<entry id>.json` beside it, so the deletion drops nothing.
        """
        self.commit_engine()
        write_overlay(self.out, self.SHARED_OVERLAY)
        files = self.produced_files(extra=[{"path": "corpus-map.overlay.json", "changeType": "REMOVED"}])
        self.pull_request(body=self.produce_body(), files=files, base_record=self.overlay_base())
        done = self.policy_check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("claim was admitted", done.stdout)
        self.assertNotIn("not files a produce writes", done.stdout)

    def test_a_shared_overlay_the_split_does_not_carry_voids_the_claim(self):
        """The witness reads the content, so a key `overlay/` lacks is evidence being dropped.

        Same diff, same pattern, same pathname; the only difference is that the files in the head
        tree do not account for one of the deleted file's entries. Admitting that would let a
        produce update carry away an entry's evidence, which is the shape #246's three review rounds
        kept coming back to: never authorise a deletion by pathname alone.
        """
        self.commit_engine()
        write_overlay(self.out, {"altitude-limit": self.SHARED_OVERLAY["altitude-limit"]})
        files = self.produced_files(extra=[{"path": "corpus-map.overlay.json", "changeType": "REMOVED"}])
        self.pull_request(body=self.produce_body(), files=files, base_record=self.overlay_base())
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not files a produce writes", done.stdout)
        self.assertIn("corpus-map.overlay.json", done.stdout)
        self.assertIn("claim is void", done.stdout)

    def test_a_retired_path_added_or_modified_voids_the_claim(self):
        """`backlog/notes.md` is hand-written and matches `backlog/*.md`. A produce deletes; it
        never adds to or edits a retired pattern, so a diff that does is somebody's decision."""
        self.commit_engine()
        for change in ("ADDED", "MODIFIED"):
            with self.subTest(change=change):
                self.pull_request(body=self.produce_body(), files=self.retired_files(change=change),
                                  base_record=self.retired_base())
                done = self.policy_check()
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn("not files a produce writes", done.stdout)
                self.assertIn("backlog/001-speed-limit.md", done.stdout)
                self.assertIn("claim is void", done.stdout)

    def test_a_retired_deletion_whose_base_bytes_were_hand_edited_voids_the_claim(self):
        """The policy draws the line the remover draws, and the record's path list is not that line.

        A file the factory generated once and somebody edited afterwards without re-producing is
        still listed in the record, under its old hash. `ownership.remove_retired` keeps such a file;
        a policy that admitted its deletion on the strength of the path alone would call somebody's
        deletion of somebody's work a produce.
        """
        self.commit_engine()
        self.pull_request(body=self.produce_body(), files=self.retired_files(),
                          base_record=self.retired_base(edited=["backlog/001-speed-limit.md"]))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not files a produce writes", done.stdout)
        self.assertIn("backlog/001-speed-limit.md", done.stdout)
        self.assertNotIn("backlog/README.md", done.stdout.split("are not files a produce writes")[1][:200],
                         "the one whose bytes are the record's is still admitted")

    def test_a_retired_deletion_the_base_record_does_not_own_voids_the_claim(self):
        """Deleting a hand-written file under a retired pattern is still a decision (#243).

        The base commit's record is what says the factory wrote a file. Without it -- the record
        never named the path, or the API call failed -- the deletion is not attributed, and a
        deletion this check cannot attribute is not admitted.
        """
        self.commit_engine()
        self.pull_request(body=self.produce_body(), files=self.retired_files(),
                          base_record=self.retired_base(paths=["backlog/999-something-else.md"]))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not files a produce writes", done.stdout)
        self.assertIn("backlog/001-speed-limit.md", done.stdout)

        self.pull_request(body=self.produce_body(), files=self.retired_files())  # no base record at all
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("the base commit's provenance.json could not be read", done.stdout)

    def test_an_overlay_edit_voids_the_claim(self):
        # The overlay is engine-owned and is the input to generation: an entry the new map forces
        # is a rules decision the factory did not make, and belongs to its own issue.
        self.commit_engine()
        self.pull_request(body=self.produce_body(), files=self.produced_files(extra=["overlay/altitude-limit.json"]))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("overlay/altitude-limit.json", done.stdout)
        self.assertIn("not files a produce writes", done.stdout)

    def test_a_declared_version_the_tree_does_not_show_is_refused(self):
        self.commit_engine()
        record = self.record()
        section = PRODUCE_SECTION.format(factory=record["factory"]["version"],
                                         map=f"{record['map']['packageId']} 99.0.0",
                                         kernel=record["kernel"]["version"], version="99.0.0")
        self.pull_request(body=self.produce_body(section=section), files=self.produced_files())
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("99.0.0", done.stdout)
        self.assertIn("provenance.json in this tree records", done.stdout)

    def test_a_dirty_factory_record_is_refused(self):
        # Every engine these tests produce is produced --allow-dirty, so the record already says
        # dirty: true; the passing cases above clear it, and this one does not. A produce nobody
        # can repeat is not an update to anything.
        self.commit_engine()
        self.pull_request(body=self.produce_body(), files=self.produced_files())
        record = self.record()
        record["factory"]["dirty"] = True
        self.write_record(record)
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("records the factory as dirty", done.stdout)

    def test_the_marker_alone_buys_nothing(self):
        # The body says every true thing a produce update says, and the diff is an ordinary
        # implementation. Both relaxations must be gone, not one of them.
        self.commit_engine()
        self.pull_request(body=self.produce_body(),
                          files=[{"path": "overlay/altitude-limit.json"}, {"path": f"src/{NAME}/Rules/AltitudeLimit.cs"}])
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("names no mutation", done.stdout)
        self.assertIn("does not name the entry id", done.stdout)
        self.assertIn("does not name the locator", done.stdout)

    def test_it_still_needs_one_closes_and_one_of_each_label(self):
        self.commit_engine()
        self.pull_request(body=self.produce_body().replace("Closes #27", "Related to #27"),
                          files=self.produced_files())
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("no `Closes #<n>`", done.stdout)

        self.pull_request(body=self.produce_body(), files=self.produced_files(), labels=("state:ready",))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("0 risk labels", done.stdout)

    def test_the_produce_evidence_is_required_in_the_mutation_s_place(self):
        # Not a discount: a produce update shows the command that wrote the bytes and the recompute
        # saying the committed record is the one a re-produce writes. Both are re-runnable.
        self.commit_engine()
        self.pull_request(body=self.produce_body(evidence="```\n$ ./scripts/validate.sh full\nPASS\n```"),
                          files=self.produced_files())
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("shows no `factory produce`", done.stdout)
        self.assertIn("shows no `factory provenance`", done.stdout)

    def test_the_emitted_template_carries_the_section_and_the_marker(self):
        # Template and checker are emitted together and are one contract: renaming the section in
        # one would make every factory update's claim silently unrecognised, which is the shape of
        # failure this pairing exists to prevent.
        self.produced()
        template = self.read(".github/pull_request_template.md")
        self.assertIn("## Produced by the factory", template)
        self.assertIn("<!-- rules-factory-produce -->", template)
        checker = self.read("tools/pr-policy.py")
        self.assertIn('("Produced by the factory"', checker)
        self.assertIn('PRODUCE_MARKER = "<!-- rules-factory-produce -->"', checker)

    def test_a_pull_request_without_the_section_is_not_asked_for_one(self):
        # The one optional heading: almost no pull request is a factory update.
        self.produced()
        self.pull_request()
        done = self.policy_check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("Produced by the factory", done.stdout)


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

    def scenario(self, head="a" * 40, labels=("state:ready", "risk:normal"), files=None, changed_files=None):
        self.gh_with_statuses()
        files = files if files is not None else [{"path": f"src/{NAME}/Rules/AltitudeLimit.cs"}]
        self.fixture({
            "pr": {"5": {"number": 5, "headRefOid": head, "state": "OPEN",
                         "files": files,
                         "changedFiles": len(files) if changed_files is None else changed_files,
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

    def test_a_truncated_file_list_is_undecidable(self):
        # #193: `gh pr view --json files` caps at 100 silently, and a regeneration writes hundreds.
        # The verdict requirement is derived from these paths, so "nothing on the semantic surface"
        # from a partial list is the answer this gate exists to never give by accident.
        self.produced()
        self.scenario(files=[{"path": "README.md"}], changed_files=140)
        done = self.gate()
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("listed 1 of PR #5's 140 changed files", done.stderr)
        self.assertIn("cannot be decided from a partial list", done.stderr)

    def test_a_produce_update_touching_the_generated_code_still_needs_the_semantic_verdict(self):
        # Produce mode lives in pr-policy.py and buys nothing here: the gate reads the changed
        # paths and nothing else, and a map bump rewrites the generated code, the pins and both
        # lock files. This is the check 0029's amendment refuses ever to let the claim waive.
        self.produced()
        self.scenario(files=[{"path": "provenance.json"},
                             {"path": "RulesFactory.Packages.g.props"},
                             {"path": f"src/{NAME}/Generated/MapEntries.g.cs"},
                             {"path": f"src/{NAME}/packages.lock.json"}])
        done = self.gate()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("rules-verdict/semantic is not recorded as a success", done.stdout)
        self.assertEqual(self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass").returncode, 0)
        done = self.gate()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

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
"""A stand-in for `gh` that also keeps commit statuses, workflow runs and re-runs in JSON files."""
import json, os, sys

fixture = json.load(open(os.environ["GH_FIXTURE"], encoding="utf-8"))
store = os.environ["GH_STATUSES"]
reruns = os.environ.get("GH_RERUNS", "")
argv = sys.argv[1:]

def statuses():
    try:
        return json.load(open(store, encoding="utf-8"))
    except Exception:
        return {}

if argv[0] == "api":
    endpoint = argv[1]
    if endpoint.endswith("/rerun"):
        # The 30-day limit, when the fixture asks for it: GitHub refuses the re-run, and nothing
        # else can produce a run at that commit.
        if fixture.get("rerunFails"):
            sys.stderr.write("HTTP 403: Unable to retry this workflow run because it was created over 30 days ago\\n")
            sys.exit(1)
        run_id = endpoint.split("/actions/runs/")[1].split("/rerun")[0]
        recorded = json.load(open(reruns, encoding="utf-8")) if os.path.exists(reruns) else []
        recorded.append(run_id)
        json.dump(recorded, open(reruns, "w", encoding="utf-8"))
        print("{}")
        raise SystemExit(0)
    if "/actions/workflows/" in endpoint:
        sha = endpoint.split("head_sha=")[1].split("&")[0]
        print(json.dumps({"workflow_runs": (fixture.get("runs") or {}).get(sha, [])}))
        raise SystemExit(0)
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

if argv[:2] == ["pr", "list"]:
    fields = argv[argv.index("--json") + 1].split(",")
    open_pulls = [p for p in (fixture.get("pr") or {}).values() if p.get("state") == "OPEN"]
    print(json.dumps([{f: p.get(f) for f in fields} for p in open_pulls]))
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


HEAD = "a" * 40
STRANGER = "c" * 40


class TestTheVerdictReRunsTheGate(TestVerdicts):
    """`tools/requeue-gate.py` and the two workflows' shape (#191).

    Recording a verdict used to leave the required `conformance-gate` check holding its earlier
    answer, because a commit status re-runs nothing and the gate's own `status` trigger was gated
    to `pull_request` events. What is asserted here is the logic that replaces it, and the emitted
    YAML's shape -- the workflow-level wiring, which only tools/validate-engine.py can run, is
    proved there.
    """

    def setUp(self):
        super().setUp()
        self.reruns = os.path.join(self.tmp, "reruns.json")

    def requeue(self, sha=HEAD, context="rules-verdict/semantic", state="success"):
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "requeue-gate.py")],
                              cwd=self.out, capture_output=True, text=True,
                              env={**self.environment(), "GH_STATUSES": self.statuses, "GH_RERUNS": self.reruns,
                                   "VERDICT_SHA": sha, "VERDICT_CONTEXT": context, "VERDICT_STATE": state})

    def requeue_scenario(self, runs=({"id": 991, "run_number": 7, "status": "completed"},), head=HEAD,
                         rerun_fails=False):
        """One open pull request at `head`, and the gate runs GitHub holds at that commit."""
        self.gh_with_statuses()
        self.fixture({
            "pr": {"5": {"number": 5, "headRefOid": head, "state": "OPEN"}},
            "repo": {"nameWithOwner": "owner/engine"},
            "runs": {head: list(runs)},
            "rerunFails": rerun_fails,
        })
        with open(self.statuses, "w", encoding="utf-8") as handle:
            json.dump({}, handle)

    def recorded_reruns(self):
        return json.load(open(self.reruns, encoding="utf-8")) if os.path.exists(self.reruns) else []

    def test_a_verdict_re_requests_the_gate_run_at_that_head(self):
        self.produced()
        self.requeue_scenario()
        done = self.requeue()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.recorded_reruns(), ["991"])
        self.assertIn("#5", done.stdout)

    def test_the_newest_run_is_the_one_re_requested(self):
        self.produced()
        self.requeue_scenario(runs=({"id": 991, "run_number": 7, "status": "completed"},
                                    {"id": 992, "run_number": 9, "status": "completed"}))
        self.assertEqual(self.requeue().returncode, 0)
        self.assertEqual(self.recorded_reruns(), ["992"])

    def test_a_status_on_a_commit_no_open_pull_request_heads_re_runs_nothing(self):
        # Acceptance criterion 2 of #191: and it is not a failure either, because a failing check
        # on such a commit is a red mark nobody can clear.
        self.produced()
        self.requeue_scenario()
        done = self.requeue(sha=STRANGER)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.recorded_reruns(), [])
        self.assertIn(f"no open pull request heads {STRANGER}", done.stdout)

    def test_a_status_that_is_not_a_verdict_is_ignored(self):
        self.produced()
        self.requeue_scenario()
        done = self.requeue(context="ci/some-other-service")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.recorded_reruns(), [])
        self.assertIn("is not a verdict context", done.stdout)

    def test_a_pending_verdict_re_runs_nothing(self):
        self.produced()
        self.requeue_scenario()
        done = self.requeue(state="pending")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.recorded_reruns(), [])

    def test_the_verdict_contexts_are_the_policy_s(self):
        self.produced()
        path = os.path.join(self.out, ".github", "agent-policy.json")
        settings = json.load(open(path, encoding="utf-8"))
        settings["review"]["independentFallback"] = [{"id": "acme", "context": "rules-verdict/acme"}]
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
        self.requeue_scenario()
        self.assertEqual(self.requeue(context="rules-verdict/codex").returncode, 0)
        self.assertEqual(self.recorded_reruns(), [], "a context the policy dropped is no longer a verdict")
        self.assertEqual(self.requeue(context="rules-verdict/acme").returncode, 0)
        self.assertEqual(self.recorded_reruns(), ["991"])

    def test_a_run_already_under_way_is_left_alone(self):
        self.produced()
        self.requeue_scenario(runs=({"id": 991, "run_number": 7, "status": "in_progress"},))
        done = self.requeue()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.recorded_reruns(), [])
        self.assertIn("without being asked", done.stdout)

    def test_no_run_to_re_request_is_a_failure_that_names_why(self):
        self.produced()
        self.requeue_scenario(runs=())
        done = self.requeue()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("no conformance-gate.yml run on the `pull_request` event", done.stderr)

    def test_a_run_too_old_to_re_request_is_a_failure_that_names_the_30_day_limit(self):
        self.produced()
        self.requeue_scenario(rerun_fails=True)
        done = self.requeue()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("30 days", done.stderr)
        self.assertIn("the branch must be pushed", done.stderr)

    def test_a_sha_that_is_not_a_commit_is_refused(self):
        self.produced()
        self.requeue_scenario()
        done = self.requeue(sha="not-a-sha")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not a 40-character commit SHA", done.stderr)

    def test_the_gate_workflow_is_asked_only_by_the_pull_request_event(self):
        self.produced()
        text = self.read(".github/workflows/conformance-gate.yml")
        triggers = text.split("\non:\n", 1)[1].split("\nconcurrency:", 1)[0]
        self.assertNotIn("status:", triggers,
                         "a status run belongs to the default branch's commit, not to the pull request")
        job = text.split("jobs:\n", 1)[1]
        self.assertNotIn("if:", job, "the job's `if:` was what skipped every status run (#191)")
        self.assertNotIn("github.sha", text, "on a status event github.sha is the default branch's head")

    def test_the_requeue_workflow_does_not_answer_to_the_required_check_s_name(self):
        self.produced()
        text = self.read(".github/workflows/verdict-requeue.yml")
        self.assertIn("\non:\n  status:\n", text)
        jobs = [line.strip().rstrip(":") for line in text.split("jobs:\n", 1)[1].splitlines()
                if line.startswith("  ") and not line.startswith("   ") and line.strip().endswith(":")]
        self.assertEqual(jobs, ["verdict-requeue"],
                         "two check runs of one name are ambiguous; this one lands on the default branch's head")
        self.assertNotIn("if:", text.split("jobs:\n", 1)[1],
                         "a job condition on the only event this workflow has is how #191 skipped every run")
        self.assertIn("group: verdict-requeue-${{ github.event.sha }}", text)
        self.assertNotIn("github.sha }}", text,
                         "github.sha is the same value for every verdict, and cancel-in-progress is on")
        # The payload is text somebody else wrote: it reaches the script as values, never as script.
        for variable in ("VERDICT_SHA", "VERDICT_CONTEXT", "VERDICT_STATE"):
            self.assertIn(f"{variable}: ${{{{ github.event.", text)
        self.assertIn("run: python3 tools/requeue-gate.py\n", text)

    def test_the_requeue_is_not_a_required_check(self):
        # The ruleset the factory applies, and the doctor's reading of it from inside an engine:
        # both leave it out, because it runs on the default branch's commit.
        self.assertNotIn("verdict-requeue", factory.rails_step.REQUIRED_CHECKS)
        self.assertIn("verdict-requeue", agentrails.rails_files()["tools/agent-doctor.py"])
        self.assertNotIn('"verdict-requeue"', agentrails.rails_files()["tools/agent-doctor.py"])


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


class AFactoryToReProduceFrom:
    """A stand-in factory in a git repository, and an engine record pointed at a commit of it.

    Shared by the two suites that run `tools/re-produce.sh` for real: #192's, which is about which
    commit it takes, and #203's, which runs every command a rail names and needs this to be one of
    the commands it can run without cloning the factory over the network.
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


class TestReProduce(AFactoryToReProduceFrom, RailsInAGitEngine):
    """`tools/re-produce.sh`: the one command an overlay edit is finished with (#192).

    The factory is a stand-in here, in a git repository of its own with two commits: the one the
    engine's record names, and a later `main`. Which of the two runs is the whole point -- checking
    out `main` would re-emit the gate, the rails and the vendored generator from a factory nobody
    asked for, into an implementation pull request.
    """

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
        write_overlay(self.out, {"altitude-limit": {"status": "blocked"}})
        self.record_commit(commits["recorded"])
        self.assertEqual(self.re_produce(repo=repo).returncode, 0)


COMMAND = re.compile(r"^(?:\./)?(?:tools|scripts)/[A-Za-z0-9_.\-]+\.(?:py|sh)$")
# What a rail's placeholder stands for here, so the command that runs is the one the rail spells.
# An unknown placeholder fails the test rather than skipping the command it is in: a rail that
# grows a new one is a command nobody has run.
PLACEHOLDERS = {"<n>": "1", "<issue number>": "1", "<entry id>": "speed-limit", "<entry-id>": "speed-limit",
                "<pr>": "1", "<pr number>": "1", "<id>": "semantic", "{args.pr}": "1",
                '"..."': "Title", "pass|fail": "pass"}
# `scripts/validate.sh` is the gate itself: running it here would restore, build and test an engine
# in every target framework from inside a unit test. scripts/validate-engine.sh runs it against a
# produced engine for real, which is where its runnability is proven.
NOT_RUN_HERE = ("scripts/validate.sh",)
# How a script refuses the way it was called, rather than what it was asked to do: argparse's own
# vocabulary, a shell rail printing its usage, and a rail that names the option it was not given.
# The last is a pattern rather than the words "is required", which a rail says about other things
# ("gh is required: work starts from an issue").
USAGE_ERROR = ("the following arguments are required", "unrecognized arguments", "invalid choice",
               "expected one argument", "error: argument")
USAGE_PATTERN = re.compile(r"(?m)^usage: |(?:^|: )-{1,2}[A-Za-z][A-Za-z-]* is required")


def refused_for_how_it_was_called(done):
    """Why the run below was a usage error, or None when the command got as far as doing something."""
    said = done.stdout + done.stderr
    marker = next((marker for marker in USAGE_ERROR if marker in said), None)
    if marker is None:
        found = USAGE_PATTERN.search(said)
        marker = found.group(0).strip() if found else None
    if marker is None and done.returncode == 2:
        marker = "it exited 2, which is how a command refuses its own arguments"
    return marker
# MSBuild's answer to `-getItem:RulesFactoryMap`, so entry-packet.py's own resolution runs here
# rather than being skipped: the restore is what this test cannot have, not the question.
DOTNET_STUB = '''#!/usr/bin/env python3
import json, sys
print(json.dumps({"Items": {"RulesFactoryMap": [{"FullPath": "@MAP@"}]}}))
'''


def rail_commands(rails):
    """Every command an emitted rail tells an agent to run: (rail, argv-as-written), deduplicated.

    Two shapes count, and the difference is not pedantry. A line in a fenced block is a command
    whether or not it carries arguments: the fence is there to be typed. An inline code span counts
    only when it carries one -- a bare `tools/pr-policy.py` in a sentence is the tool's name, and
    that the file exists is already the engine gate's rails check, while
    `scripts/engine-gate.py regenerate --write` is an instruction to run something (#203).
    """
    found = {}
    for relative, text in sorted(rails.items()):
        spans = [(span, False) for span in re.findall(r"`([^`\n]+)`", text)]
        fence = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                fence = None if fence is not None else stripped[3:].strip()
            elif fence in ("bash", "sh", ""):
                spans.append((stripped.split("#", 1)[0].strip(), True))
        for span, fenced in spans:
            words = span.split()
            if words and COMMAND.match(words[0]) and (fenced or len(words) > 1):
                found.setdefault(span, relative)
    return sorted((relative, span) for span, relative in found.items())


class TestEveryCommandARailNamesRunsAsWritten(AFactoryToReProduceFrom, RailsInAGitEngine):
    """Every command an emitted rail hands an agent, run against a produced engine (#203).

    The implementer's charter used to offer `scripts/engine-gate.py regenerate --write` as "how you
    run it", and run as written it exits 2: it needs five arguments that only a
    `dotnet msbuild -getItem:RulesFactoryMap` against a restored project can supply. Rails here are
    read by agents, which take a backticked command as a command to run, so an uninvokable one
    spends an attempt and the rails' own credibility -- and the narrower defect, fixing the one
    sentence, would leave the next one free to appear.

    What is asserted is deliberately narrow: not that each command succeeds. Most of these need a
    GitHub, a restore or a network this test does not have, and the stand-ins below answer them with
    failures. What must not happen is a command refused for how it was spelled, before it does
    anything at all. That is the whole class of defect, and the only part of it that can be checked
    without reproducing the world every rail expects.
    """

    def setUp(self):
        super().setUp()
        self.produced()
        repo, commits = self.factory_repo()
        self.factory = repo
        self.record_commit(commits["recorded"])
        self.commit_engine_as_is()
        self.fixture({"issue": {"1": {"title": "Widen the altitude limit", "state": "OPEN",
                                      "labels": [{"name": "state:ready"}, {"name": "risk:normal"}]}},
                      "pr": {"1": {"number": 1, "title": "Implement the altitude limit", "body": "Closes #1",
                                   "headRefOid": git(self.out, "rev-parse", "HEAD"), "headRefName": "issue-1",
                                   "baseRefName": "main", "files": [{"path": "overlay/altitude-limit.json"}],
                                   "closingIssuesReferences": [{"number": 1}]}}})
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        dotnet = os.path.join(self.bin, "dotnet")
        with open(dotnet, "w", encoding="utf-8") as handle:
            handle.write(DOTNET_STUB.replace("@MAP@", os.path.join(PART107, "corpus-map.json")))
        os.chmod(dotnet, 0o755)

    def spelled(self, span):
        """The rail's command as argv, with each placeholder replaced by something concrete."""
        def value(match):
            token = match.group(0)
            self.assertIn(token, PLACEHOLDERS,
                          f"{token!r} in `{span}` is a placeholder this test has no value for. Give it one: a "
                          f"command nobody can run as written is the defect this test exists for.")
            return PLACEHOLDERS[token]
        return re.sub(r"<[^>]*>|\{[^}]*\}|\"\.\.\.\"|\b\w+\|\w+\b", value, span).split()

    def test_no_rail_names_a_command_that_is_refused_for_how_it_was_spelled(self):
        commands = rail_commands(agentrails.rails_files())
        self.assertGreater(len(commands), 5, "no commands were found in the rails -- this check proved nothing")
        environment = {**self.environment(), "RULES_ENGINE_FACTORY_REPO": self.factory,
                       "RULES_ENGINE_PACKET_ROOT": os.path.join(self.tmp, "packets"),
                       "PATH": self.bin + os.pathsep + os.environ["PATH"]}
        ran = 0
        for relative, span in commands:
            if any(span.split()[0].lstrip("./").startswith(tool) for tool in NOT_RUN_HERE):
                continue
            argv = self.spelled(span)
            runner = [sys.executable] if argv[0].endswith(".py") else ["bash"]
            done = subprocess.run([*runner, os.path.join(self.out, *argv[0].lstrip("./").split("/")), *argv[1:]],
                                  cwd=self.out, capture_output=True, text=True, env=environment, timeout=300)
            ran += 1
            refusal = refused_for_how_it_was_called(done)
            self.assertIsNone(refusal, f"{relative} tells an agent to run `{span}`, and run exactly as written it "
                                       f"refuses that call ({refusal}):\n{(done.stdout + done.stderr).strip()}")
        self.assertGreater(ran, 5, "every command was skipped -- this check proved nothing")


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
endpoint, _, query = argv[1].partition("?")

# The app the three required checks are pinned to. `apps` is a host-wide endpoint, not a
# repository one: `state["app"]` absent is a host that will not say (#186).
if endpoint == "apps/github-actions":
    if "app" not in state:
        sys.exit("Not Found")
    print(json.dumps({"id": state["app"], "slug": "github-actions", "name": "GitHub Actions"}))
    raise SystemExit(0)

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
elif endpoint == f"repos/{state['repo']}/rules/branches/{state['branch']}":
    # The rules GitHub enforces on the default branch, from every active ruleset at every level
    # whose conditions reach it. `state["inForce"]` set to an error is a token that may not read them.
    if "inForce" in state:
        sys.exit(state["inForce"])
    rules = []
    for ruleset in state["rulesets"] + state.get("orgRulesets", []):
        reference = (ruleset.get("conditions") or {}).get("ref_name") or {}
        reaches = {"~DEFAULT_BRANCH", "~ALL", f"refs/heads/{state['branch']}"}
        # `state["unenforced"]` names rulesets GitHub holds and does not enforce -- a private
        # repository on a plan without rulesets keeps them, active, and enforces none of them.
        if (ruleset["id"] in state.get("unenforced", [])
                or ruleset.get("enforcement") != "active" or ruleset.get("target", "branch") != "branch"
                or not reaches & set(reference.get("include") or [])
                or reaches & set(reference.get("exclude") or [])):
            continue
        level = ruleset.get("source_type", "Repository")
        for rule in ruleset.get("rules") or []:
            rules.append({**rule, "ruleset_source_type": level, "ruleset_id": ruleset["id"],
                          "ruleset_source": ruleset.get("source", state["repo"])})
    print(json.dumps(rules))
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
        # GitHub answers this for a ruleset above the repository too, so a caller that took an
        # organization's ruleset for its own would read it here and be none the wiser.
        (found,) = [r for r in state["rulesets"] + state.get("orgRulesets", []) if r["id"] == int(rest)]
        print(json.dumps(found))
    else:
        # An organization's rulesets come back beside the repository's own only when asked for.
        parents = state.get("orgRulesets", []) if "includes_parents=true" in query else []
        print(json.dumps([{"id": r["id"], "name": r["name"], "source_type": r.get("source_type", "Repository"),
                           "source": r.get("source", state["repo"])} for r in state["rulesets"] + parents]))
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

    APP = 15368  # the GitHub Actions app on github.com; the stub answers `gh api apps/github-actions` with it

    def repo_state(self, **overrides):
        document = {"repo": self.REPO, "branch": "main", "app": self.APP, **overrides}
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

    def edit_ruleset(self, change):
        """Change the applied ruleset behind the factory's back, as an admin with the UI can."""
        state = self.read_state()
        change(state["rulesets"][0])
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        return state["rulesets"][0]

    def test_a_ruleset_that_excludes_the_default_branch_is_reported_and_rewritten(self):
        # The ruleset is still named, still active and still carries every rule -- and governs
        # nothing, because the one branch it applied to is excluded (#185).
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.edit_ruleset(lambda r: r["conditions"]["ref_name"].update({"exclude": ["~DEFAULT_BRANCH"]}))
        payload = factory.rails_step.ruleset_payload("main", self.APP)
        self.assertFalse(factory.rails_step.matches(self.read_state()["rulesets"][0], payload))
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("it excludes ~DEFAULT_BRANCH", output)
        self.assertEqual(self.rails("--apply")[0], 0)
        self.assertEqual(self.read_state()["rulesets"][0]["conditions"]["ref_name"]["exclude"], [])
        self.assertEqual(self.rails("--check")[0], 0)

    def test_a_ruleset_that_targets_tags_is_reported_and_rewritten(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.edit_ruleset(lambda r: r.update({"target": "tag"}))
        payload = factory.rails_step.ruleset_payload("main", self.APP)
        self.assertFalse(factory.rails_step.matches(self.read_state()["rulesets"][0], payload))
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("it targets 'tag'", output)
        self.assertEqual(self.rails("--apply")[0], 0)
        self.assertEqual(self.read_state()["rulesets"][0]["target"], "branch")
        self.assertEqual(self.rails("--check")[0], 0)

    def test_a_condition_the_factory_does_not_understand_is_a_mismatch(self):
        # Not because this one narrows the ruleset -- it may not -- but because the factory cannot
        # tell whether it does, and a check that passes on what it did not read is #185 again.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.edit_ruleset(lambda r: r["conditions"].update({"repository_property": {"include": []}}))
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("repository_property condition(s) the factory did not write", output)

    def test_a_required_check_is_pinned_to_the_app_that_posts_it(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        (rule,) = [r for r in self.read_state()["rulesets"][0]["rules"] if r["type"] == "required_status_checks"]
        self.assertEqual({check["integration_id"] for check in rule["parameters"]["required_status_checks"]},
                         {self.APP})

    def test_an_unpinned_required_check_is_reported_and_pinned(self):
        # What an unpinned context means: `conformance-gate` is satisfied by a commit status under
        # that name, which anyone with write access can post (#186).
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)

        def unpin(ruleset):
            for rule in ruleset["rules"]:
                if rule["type"] == "required_status_checks":
                    rule["parameters"]["required_status_checks"] = [{"context": c} for c in
                                                                    ("validate", "pr-policy", "conformance-gate")]
        self.edit_ruleset(unpin)
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("conformance-gate is required but not pinned to the github-actions app", output)
        self.assertEqual(self.rails("--apply")[0], 0)
        self.assertEqual(self.rails("--check")[0], 0)

    def test_apply_refuses_when_the_app_the_checks_come_from_cannot_be_read(self):
        self.produced()
        state = self.read_state()
        del state["app"]
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        code, output = self.rails("--apply")
        self.assertEqual(code, 1, output)
        self.assertIn("could not be read from this host", output)
        self.assertEqual(self.read_state()["rulesets"], [], "a ruleset was written without the pin")

    def test_check_says_what_the_verdict_gate_is_worth(self):
        # 0029 §7 and AGENTS.md §7 say it where the rails are decided and where they are read; the
        # doctor's own report is the third place someone meets it (#186).
        self.produced()
        code, output = self.rails("--check")
        self.assertIn("Verdict gate", output)
        self.assertIn("not an authentication of who reviewed", output)

    def test_the_verdict_gate_row_is_not_ok_and_does_not_fail_the_check(self):
        # It examines nothing, so it may not say OK (#211); and nothing `--apply` does changes it,
        # so it may not fail a repository whose rails are otherwise in place.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        code, output = self.rails("--check")
        self.assertEqual(code, 0, output)
        line = self.row(output, "Verdict gate")
        self.assertIn(" NOT AUTHENTICATED ", line)
        self.assertNotIn(" OK ", line)

    def test_a_policy_whose_labels_collide_is_refused(self):
        self.produced()
        path = os.path.join(self.out, ".github", "agent-policy.json")
        for overrides, expected in (({"blocked": "state:ready"}, "ready and blocked are both 'state:ready'"),
                                    ({"normalRisk": "state:ready"}, "ready and normalRisk are both 'state:ready'")):
            with open(path, encoding="utf-8") as handle:
                policy = json.load(handle)
            edited = dict(policy, labels=dict(json.loads(agentrails.agent_policy())["labels"], **overrides))
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(edited, handle, indent=2)
            code, output = self.rails("--check")
            self.assertEqual(code, 1, output)
            self.assertIn(expected, output)
            self.assertIn("in two states at once", output)

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

    # --- #211: a row says OK only about what it examined -------------------------------------

    def write_policy(self, change):
        path = os.path.join(self.out, ".github", "agent-policy.json")
        policy = json.loads(agentrails.agent_policy())
        change(policy)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(policy, handle, indent=2)

    def doctor_and_gate(self):
        """What the engine's own two judges of the policy say, run as an agent would run them."""
        doctor = subprocess.run([sys.executable, os.path.join(self.out, "tools", "agent-doctor.py"), "--local"],
                                cwd=self.out, capture_output=True, text=True)
        gate_run = subprocess.run([sys.executable, os.path.join(self.out, "scripts", "engine-gate.py"), "rails"],
                                  cwd=self.out, capture_output=True, text=True)
        return doctor.stdout, gate_run.returncode, gate_run.stderr

    def row(self, output, name):
        (line,) = [line for line in output.splitlines() if line.startswith(name + " ")]
        return line

    def test_a_chain_link_with_no_context_is_not_ok_and_every_judge_of_the_policy_agrees(self):
        # `tools/record-verdict.py` records under the link's context, so this reviewer can record
        # nothing; the engine gate said so and `--check` called the same file OK.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.write_policy(lambda p: p["review"]["independentFallback"].append({"id": "acme"}))
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("WRONG", self.row(output, "Policy"))
        self.assertIn("WRONG", self.row(output, "Review chain"))
        self.assertIn("{'id': 'acme'}", output)
        self.assertIn("cannot be told", output)
        doctor, gate_code, gate_errors = self.doctor_and_gate()
        self.assertIn("WRONG", self.row(doctor, "Policy"))
        self.assertIn("cannot be told", doctor)
        self.assertEqual(gate_code, 1, gate_errors)
        self.assertIn("cannot be told", gate_errors)

    def test_the_three_judges_of_the_policy_agree_on_every_fixture(self):
        # One rule, imported by all three, rather than three copies; this is what shows the
        # engine's vendored copy is the one the factory reads, fixture by fixture.
        fixtures = {
            "as the factory ships it": lambda p: None,
            "a link with no context": lambda p: p["review"]["independentFallback"].append({"id": "acme"}),
            "a link with no id": lambda p: p["review"]["independentFallback"].append({"context": "rules-verdict/x"}),
            "a link that is not an object": lambda p: p["review"]["independentFallback"].append("acme"),
            "no chain": lambda p: p["review"].update(independentFallback=[]),
            "no semantic context": lambda p: p["review"].pop("semanticContext"),
            "another schema version": lambda p: p.update(schemaVersion=2),
        }
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        for name, change in fixtures.items():
            with self.subTest(name):
                self.write_policy(change)
                expected = agentrails.policy_problems(json.loads(self.read(".github/agent-policy.json")))
                self.assertEqual(bool(expected), name != "as the factory ships it", expected)
                code, output = self.rails("--check")
                doctor, gate_code, gate_errors = self.doctor_and_gate()
                self.assertEqual("OK" in self.row(output, "Policy"), not expected, output)
                self.assertEqual("OK" in self.row(doctor, "Policy"), not expected, doctor)
                self.assertEqual(gate_code == 0, not expected, gate_errors)
                self.assertEqual(code == 0, not expected, output)
                for reason in expected:
                    self.assertIn(reason, output)
                    self.assertIn(reason, doctor)
                    self.assertIn(reason, gate_errors)

    def test_a_hand_edited_rail_is_not_ok(self):
        # A truncated gate is a file that exists; the row used to say OK about it.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        path = os.path.join(self.out, "tools", "conformance-gate.py")
        with open(path, "r+", encoding="utf-8") as handle:
            handle.truncate(200)
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("WRONG", self.row(output, "Agent files"))
        self.assertIn("tools/conformance-gate.py (edited by hand)", output)
        self.assertIn("--adopt", output)
        doctor, _, _ = self.doctor_and_gate()
        self.assertIn("WRONG", self.row(doctor, "Rail files"))
        self.assertIn("tools/conformance-gate.py (edited by hand)", doctor)

    def test_a_rail_from_an_earlier_recipe_is_named_for_produce_to_migrate(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        earlier = b"# what an earlier recipe wrote\n"
        with open(os.path.join(self.out, "tools", "requeue-gate.py"), "wb") as handle:
            handle.write(earlier)
        history = {**ownership.RECIPE_SHA256["tools/requeue-gate.py"], 0: ownership.sha256(earlier)}
        with unittest.mock.patch.dict(ownership.RECIPE_SHA256, {"tools/requeue-gate.py": history}):
            code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("tools/requeue-gate.py (earlier recipe)", output)
        self.assertIn("migrates them", output)

    def test_an_adopted_rail_is_named_and_is_the_engine_s_own(self):
        self.produced()
        with open(os.path.join(self.out, "AGENTS.md"), "a", encoding="utf-8") as handle:
            handle.write("\n## Our own section\n")
        self.produced("--adopt", "AGENTS.md")
        self.assertEqual(self.rails("--apply")[0], 0)
        code, output = self.rails("--check")
        self.assertEqual(code, 0, output)
        self.assertIn("adopted by the engine: AGENTS.md", self.row(output, "Agent files"))

    ORG_SIGNING = {"id": 901, "name": "org-signed-commits", "target": "branch", "enforcement": "active",
                   "source_type": "Organization", "source": "owner",
                   "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                   "rules": [{"type": "required_signatures"}]}

    def with_state(self, **changes):
        state = self.read_state()
        state.update(changes)
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)

    def test_an_organization_ruleset_on_the_default_branch_is_read_and_named(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.with_state(orgRulesets=[self.ORG_SIGNING])
        code, output = self.rails("--check")
        self.assertEqual(code, 0, output)
        self.assertIn("org-signed-commits (organization owner): required_signatures",
                      self.row(output, "Rules in force on main"))

    def test_rules_in_force_that_cannot_be_read_are_not_verified(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.with_state(inForce="HTTP 403: Resource not accessible by integration")
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        line = self.row(output, "Rules in force on main")
        self.assertIn("NOT VERIFIED", line)
        self.assertIn("HTTP 403", line)
        self.assertNotIn("The rails are in place", output)

    def test_an_organization_ruleset_with_the_factory_s_name_is_not_the_factory_s(self):
        # Shadowing: every rule the factory writes, under its name, one level up where `--apply`
        # cannot write it. It is not the factory's ruleset, and the repository still has none.
        self.produced()
        payload = factory.rails_step.ruleset_payload("main", self.APP)
        shadow = {**payload, "id": 902, "source_type": "Organization", "source": "owner"}
        self.with_state(orgRulesets=[shadow])
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("MISSING", self.row(output, "Ruleset on main"))
        self.assertIn("rules-factory-agent-rails (organization owner)", self.row(output, "Rules in force on main"))
        self.assertEqual(self.rails("--apply")[0], 1)
        state = self.read_state()
        (ours,) = state["rulesets"]
        self.assertEqual(ours["name"], "rules-factory-agent-rails")
        self.assertEqual(state["orgRulesets"], [shadow], "--apply wrote a ruleset above the repository")

    def test_a_ruleset_github_does_not_enforce_on_the_branch_is_not_ok(self):
        # What a private repository on a plan without rulesets looks like: the ruleset is there,
        # active and exactly the factory's, and GitHub enforces none of it.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.with_state(unenforced=[self.read_state()["rulesets"][0]["id"]])
        code, output = self.rails("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("OK", self.row(output, "Ruleset on main"))
        self.assertIn("WRONG", self.row(output, "Rules in force on main"))
        self.assertIn("GitHub does not enforce rules-factory-agent-rails's deletion", output)

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
        self.assertIn("tools/record-verdict.py (absent)", done.stdout)
