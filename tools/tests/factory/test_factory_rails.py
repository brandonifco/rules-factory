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


def one_map(document):
    """The single map of a review identity's `reviewContext.maps`.

    The identity names every map the engine was produced from (#460), and every engine in these
    tests is produced from one; a test that reached for `maps[0]` would keep passing if the list
    ever held two, which is the state the list exists to make visible.
    """
    (only,) = document["reviewContext"]["maps"]
    return only


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

    def test_the_two_reviewer_charters_are_tiered_and_the_cheap_one_is_the_cheaper(self):
        """The steward's description has said "Cheap" since the rails were generalised from
        `deckard`, and the line that made it true there was dropped on the way (0029's amendment).
        In the first measured run of this team the structural review cost 2% more than the
        semantic review it exists to run before.

        Same family as the read-only assertion above: a charter that claims something the rails do
        not carry out is worse than one that claims nothing, because it is believed. The tier
        itself is `docs/agent-team.md`'s, stated without naming a model; this asserts only that
        the Claude adapter answers it, and answers it the right way round.
        """
        steward = frontmatter(self.emitted[".claude/agents/repo-steward.md"])
        semantic = frontmatter(self.emitted[".claude/agents/rules-conformance.md"])
        for relative, header in ((".claude/agents/repo-steward.md", steward),
                                 (".claude/agents/rules-conformance.md", semantic)):
            self.assertIn("model", header,
                          f"{relative} names no model, so it inherits whatever dispatched it and the "
                          f"tiering docs/agent-team.md describes is a description rather than a dispatch")
        self.assertNotEqual(steward["model"], semantic["model"],
                            "both reviewers run on one tier, which is the defect 0029's amendment records: "
                            "the cheap review then costs what the expensive one costs")

    def test_the_team_document_states_the_tiering_without_naming_a_model(self):
        """0029's amendment: the requirement is the contract's and vendor-neutral, the model name
        is the vendor adapter's. A model named in the managed team document would be the
        hard-coded provider chain that record rejects."""
        team = self.emitted["docs/agent-team.md"]
        self.assertIn("cheaper tier", team)
        self.assertIn("deepest tier", team)
        for vendor in ("sonnet", "opus", "haiku", "claude-", "gpt-", "gemini"):
            self.assertNotIn(vendor, team.lower(), f"docs/agent-team.md names {vendor}, a vendor's model")

    def test_a_managed_rail_names_neither_the_engine_nor_its_map(self):
        # The constraint ownership.py's managed class puts on a recipe, checked on the rails rather
        # than assumed: fixed bytes per version is what a hand edit is detected against.
        for relative, text in self.rails.items():
            for forbidden in (NAME, "FaaPart107", "HoyleBackgammon", "RulesFactory.Maps"):
                self.assertNotIn(forbidden, text, f"{relative} names an engine or a map")

    def section_four(self):
        """AGENTS.md section 4, as one line: what it says, not how it happens to be wrapped."""
        section = self.emitted["AGENTS.md"].split("## 4. ")[1].split("\n## ")[0]
        return " ".join(section.split())

    def test_the_contract_says_to_delete_only_what_was_created_and_by_exact_path(self):
        """The engine's AGENTS.md §4 carries the rule and the incident that bought it (#236).

        rules-factory's own §4 has said this since #235: on 2026-09-17 an agent tidying up ran
        `rm -rf <scratchpad>/*` in a directory shared by every agent of that session, took two
        worktrees and uncommitted work that were not its own, and the work was rebuilt. An engine
        dispatches concurrent agents the same way and had no such sentence. The date is asserted
        because a rule with its reason removed is a rule the next agent argues with.
        """
        section = self.section_four()
        for needed in ("Delete only what you created", "by its exact path", "never by wildcard",
                       "2026-09-17", "tools/dispatch-agent.sh --sweep"):
            self.assertIn(needed, section, f"AGENTS.md section 4 does not say {needed!r}")

    def test_the_contract_names_the_documentation_the_pull_request_must_account_for(self):
        # The contract and tools/pr-policy.py are emitted together; a section the checker requires
        # and the contract does not mention is a rule an agent meets by accident (#236).
        section = self.section_four()
        self.assertIn("a line for every living document this engine owns", section)
        self.assertIn("`## Documentation` line per document", section)
        self.assertIn("tools/pr-policy.py --docs-skeleton", section)

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

    def test_the_rails_are_a_minority_of_the_engine_they_govern(self):
        """The measurement 0052 rests on, held to the threshold 0052 says would reopen it.

        0052 decided the rails stay copied into every engine rather than being externalised,
        and the reason was their size: 204 KB of a 1378 KB engine when it was written. It names
        the trade as different if the rails ever pass half an engine's bytes. That is a number
        that drifts silently, so it is asserted here rather than left in a document.
        """
        self.produced()
        managed = 0
        for relative in ownership.RECIPE_SHA256:
            path = os.path.join(self.out, *relative.split("/"))
            if os.path.isfile(path):
                managed += os.path.getsize(path)
        engine = 0
        for directory, subdirs, files in os.walk(self.out):
            subdirs[:] = [d for d in subdirs if d != ".git"]
            engine += sum(os.path.getsize(os.path.join(directory, name)) for name in files)
        self.assertGreater(managed, 0, "no managed file was found in the produced engine")
        share = managed / engine
        self.assertLess(share, 0.5,
                        f"the rails are {share:.0%} of this engine ({managed} of {engine} bytes); "
                        f"0052 says that reopens whether they should be externalised")

    def test_every_rail_a_produced_engine_carries_is_hashed_in_its_provenance(self):
        """0052's first property: an engine can prove its rails are the recipe's bytes offline.

        provenance.json's `managed` section is what makes that possible, and it is the section a
        rails distribution would have replaced with one package digest.
        """
        self.produced()
        record = json.loads(self.read("provenance.json"))
        hashed = {entry["path"] for entry in record["managed"]}
        for relative in agentrails.rails_files():
            with self.subTest(rail=relative):
                self.assertIn(relative, hashed)
                entry = next(e for e in record["managed"] if e["path"] == relative)
                digest = hashlib.sha256(
                    open(os.path.join(self.out, *relative.split("/")), "rb").read()).hexdigest()
                self.assertEqual(digest, entry["sha256"])
                self.assertIn(entry["recipeVersion"], ownership.RECIPE_SHA256[relative])

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


class TestTheEntryPacketOfAComposedEngine(unittest.TestCase):
    """`tools/entry-packet.py` against an engine produced from several map packages (#460, 0067).

    The composition is `srd-52-combat` + `srd-52-conditions`: two maps of one corpus, where combat
    declines `prone-condition` because its slice stopped short and the conditions glossary holds
    that passage in scope. So one fixture exercises all three things a composed packet has to get
    right -- an entry of either package, the package an id names, and a supersession -- and it
    exercises them on published maps rather than on a fixture invented to make them true.

    `--no-verify`, so no SDK and no build: everything asserted here is computed from the map
    packages and the overlay, which is the whole of what a packet is.
    """

    COMPOSED = ("srd-52-combat", "srd-52-conditions")
    ENGINE = "Srd52"

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        out = os.path.join(cls.shared, "packages")
        cls.packages, cls.package_maps = [], []
        for slug in cls.COMPOSED:
            directory = os.path.join(REPO, "examples", slug)
            subprocess.run([sys.executable, PACK, directory, "--out", out], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cls.package_maps.append(os.path.join(directory, "corpus-map.json"))
        cls.packages = sorted(os.path.join(out, n) for n in os.listdir(out) if n.endswith(".nupkg"))
        cls.corpus = os.path.join(REPO, "examples", "srd-52-combat", "srd-5.2.1.txt")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = os.path.join(self.tmp, "engine")
        argv = []
        for package in self.packages:
            argv += ["--package", package]
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["produce", *argv, "--corpus", self.corpus, "--name", self.ENGINE,
                                 "--out", self.out, "--allow-dirty", "--no-verify"])
        self.assertEqual(code, factory.NOT_VERIFIED, buffer.getvalue())
        with open(os.path.join(self.out, "provenance.json"), encoding="utf-8") as handle:
            self.record = json.load(handle)

    def packet(self, entry, *extra, maps=None):
        argv = [sys.executable, os.path.join(self.out, "tools", "entry-packet.py"), entry]
        for package_map in (self.package_maps if maps is None else maps):
            argv += ["--package-map", package_map]
        return subprocess.run(argv + list(extra), capture_output=True, text=True, cwd=self.out)

    def rendered(self, entry, **kwargs):
        done = self.packet(entry, "--stdout", **kwargs)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_the_record_names_both_packages_and_the_supersession_they_make(self):
        """The fixture's own claim, asserted rather than assumed: everything below rests on this
        engine being composed of two packages with one supersession between them."""
        self.assertEqual([m["packageId"] for m in self.record["maps"]],
                         ["RulesFactory.Maps.Srd52Combat", "RulesFactory.Maps.Srd52Conditions"])
        self.assertEqual(self.record["supersedes"],
                         [{"entry": "Srd52Combat.prone-condition", "by": "Srd52Conditions.prone"}])

    def test_a_packet_names_the_package_its_own_entry_came_from(self):
        """Which map an entry is from is not a detail: it is the bytes the implementer works to and
        the version a defect is reported against. Each of these entries is a different package's,
        and each packet says its own -- not the first, and not all of them."""
        combat = self.rendered("Srd52Combat.opportunity-attack")
        self.assertIn("map `RulesFactory.Maps.Srd52Combat` 2.0.0", combat)
        self.assertNotIn("map `RulesFactory.Maps.Srd52Conditions`", combat)
        conditions = self.rendered("Srd52Conditions.blinded")
        self.assertIn("map `RulesFactory.Maps.Srd52Conditions` 1.0.0", conditions)
        self.assertNotIn("map `RulesFactory.Maps.Srd52Combat`", conditions)

    def test_a_packet_names_the_id_the_published_map_has_for_the_entry(self):
        """The prefix is this engine's, not the map's. An upstream defect reported as
        `Srd52Conditions.blinded` names an entry that map does not have, so the packet says both
        ids and which is which."""
        text = self.rendered("Srd52Conditions.blinded")
        self.assertIn("published as `blinded`", text)
        self.assertIn("the entry is `blinded` there", text)

    def test_an_entry_of_the_other_package_reads_exactly_as_one_of_this_package_s(self):
        """The model is the whole composition, not the entry's own package. So an entry another
        map holds is named with what it is, not reported as absent -- which is what a model built
        from one constituent would do, and it would do it silently."""
        text = self.rendered("Srd52Combat.prone-condition")
        self.assertIn("Srd52Conditions.prone", text)
        self.assertNotIn("not an entry of this map", text)

    def test_a_superseded_entry_says_so_rather_than_being_handed_out_as_work(self):
        """The one thing a composition changes about an entry's assignment. `prone-condition` is
        combat's declined stub for a passage the glossary holds in scope; the composition answers
        the rule there, so there is nothing to implement here and the packet says so instead of
        rendering a handler to write."""
        text = self.rendered("Srd52Combat.prone-condition")
        self.assertIn("superseded in this composition", text)
        self.assertIn("Srd52Conditions.prone", text)
        self.assertNotIn("superseded in this composition", self.rendered("Srd52Conditions.blinded"))

    def test_an_id_whose_prefix_names_no_package_is_refused_and_the_packages_are_listed(self):
        """The one case where choosing would be silently wrong, and the case the blanket refusal
        on a composed engine used to stand in for. An unqualified id is this case too: in a
        composition it names no entry, and the packages are what a caller needs to see."""
        for entry in ("Srd52Fictional.prone", "prone"):
            done = self.packet(entry)
            self.assertEqual(done.returncode, 1, done.stdout)
            self.assertIn("Srd52Combat", done.stderr)
            self.assertIn("Srd52Conditions", done.stderr)

    def test_a_restored_map_is_matched_to_its_package_by_digest_not_by_the_order_given(self):
        """MSBuild returns the restored maps in its own order, so a pairing by position would be
        right on the machine it was written on and wrong on the next one. The digest is what says
        which file is which package's, so the same packet comes out of either order."""
        forward = self.rendered("Srd52Conditions.blinded")
        reversed_order = self.rendered("Srd52Conditions.blinded", maps=list(reversed(self.package_maps)))
        self.assertEqual(forward, reversed_order)

    def test_a_map_this_engine_was_not_produced_from_is_refused_and_named(self):
        """A composed engine must not be the way an unchecked map reaches a packet. A file that
        hashes to nothing the record holds is refused, and so is a composition missing one of its
        packages -- half a composition is a different map, not a smaller one."""
        stranger = os.path.join(self.tmp, "stranger.json")
        shutil.copyfile(os.path.join(PART107, "corpus-map.json"), stranger)
        done = self.packet("Srd52Conditions.blinded", maps=[self.package_maps[0], stranger])
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("Srd52Conditions", done.stderr)
        short = self.packet("Srd52Conditions.blinded", maps=[self.package_maps[0]])
        self.assertEqual(short.returncode, 1, short.stdout)
        self.assertIn("Srd52Conditions", short.stderr)


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
                               "--package-id", record["maps"][0]["packageId"],
                               "--package-version", record["maps"][0]["version"], "--name", NAME],
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
if kind == "pr" and len(argv) > 1 and argv[1] == "list":
    # `gh pr list --state merged --limit N --json headRefName,headRefOid`: the merged pull
    # requests tools/dispatch-agent.sh --sweep judges worktrees and branches by (#236). An
    # absent key answers "none have merged", which is an answer and not an absence: every
    # fixture that says nothing about pull requests is a repository where none has merged.
    # GH_PR_LIST_FAILS is the other case: `gh` is there and the answer is not, which a caller
    # must not read as "none have merged".
    if os.environ.get("GH_PR_LIST_FAILS"):
        sys.stderr.write("could not read pull requests: HTTP 403\\n")
        sys.exit(1)
    print(json.dumps(fixture.get("merged") or []))
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


class MergedWorkInAnEngine(RailsInAGitEngine):
    """A produced engine with one issue worktree, and a `gh` that can be told what has merged.

    Shared by the two rails that read that state: the sweep, which removes what merged work left
    behind, and the doctor, which reports it (#236).
    """

    TITLE = "Widen the altitude limit"
    BRANCH = "issue-27-widen-the-altitude-limit"

    def state(self, merged=(), issues=((27, TITLE),)):
        self.fixture({
            "issue": {str(number): {"title": title, "state": "OPEN",
                                    "labels": [{"name": "state:ready"}, {"name": "risk:normal"}]}
                      for number, title in issues},
            "merged": [{"headRefName": branch, "headRefOid": head} for branch, head in merged],
        })

    def worktree(self, branch=BRANCH):
        return os.path.join(self.worktrees, branch)

    def commit_in(self, path):
        with open(os.path.join(path, "note.txt"), "w", encoding="utf-8") as handle:
            handle.write("the work of this issue\n")
        git(path, "add", "note.txt")
        git(path, "commit", "-qm", "the work of this issue")
        return git(path, "rev-parse", "HEAD")

    def dispatched(self, number=27):
        """A worktree for `number`, as an agent would have it: dispatched, and committed in."""
        self.commit_engine()
        self.state()
        self.assertEqual(self.dispatch(str(number)).returncode, 0)
        return self.worktree(), self.commit_in(self.worktree())

    def branches(self):
        return git(self.out, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()


class TestTheSweep(MergedWorkInAnEngine):
    """`tools/dispatch-agent.sh --sweep`: what merged work left behind, removed at exactly its tip
    and never otherwise (#236).

    The rule is rules-factory's own `tools/repo-hygiene.py`, which is not vendored into an engine:
    a worktree or a branch is finished when a pull request merged at **exactly** its tip, and
    nothing weaker counts. A fresh worktree sits on a branch whose tip is `main`'s, so "its commits
    are in main" would sweep an agent that has not committed yet; a worktree that has committed
    since its pull request merged is somebody working in it now.

    Every assertion here names the message and not only the exit code (#283). A sweep that could
    not read GitHub, a sweep that found nothing, and a sweep that found something and refused to
    touch it all remove nothing, and a report that cannot tell them apart is the failure this
    exists for.
    """

    def sweep(self, **extra):
        return self.dispatch("--sweep", **extra)

    def test_a_worktree_whose_pull_request_merged_at_its_tip_is_swept_with_its_branch(self):
        path, head = self.dispatched()
        self.state(merged=((self.BRANCH, head),))
        done = self.sweep()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"swept    {path} ({self.BRANCH}, its pull request merged at this tip)", done.stdout)
        self.assertIn(f"swept    branch {self.BRANCH} (its pull request merged at this tip)", done.stdout)
        self.assertIn("sweep: removed 1 worktree(s) and 1 branch(es)", done.stdout)
        self.assertFalse(os.path.isdir(path), done.stdout)
        self.assertEqual(self.branches(), ["main"], done.stdout)

    def test_a_worktree_committed_to_since_its_pull_request_merged_is_not_swept(self):
        # The merged pull request is at the commit before the one in the worktree now: somebody is
        # working in it. "Its commits are in main" is true of that branch and is not the rule.
        path, head = self.dispatched()
        merged_at = git(path, "rev-parse", "HEAD~1")
        self.state(merged=((self.BRANCH, merged_at),))
        done = self.sweep()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("sweep: nothing to remove", done.stdout)
        self.assertIn("1 worktree(s) and 2 branch(es) examined", done.stdout)  # main, and the issue's
        self.assertNotIn("swept", done.stdout)
        self.assertTrue(os.path.isdir(path), done.stdout)
        self.assertIn(self.BRANCH, self.branches())

    def test_a_fresh_worktree_with_no_merged_pull_request_is_not_swept(self):
        # Its tip is main's tip, so every weaker rule -- "in main", "merged into main" -- removes
        # the worktree of an agent that has not committed yet.
        self.commit_engine()
        self.state()
        self.assertEqual(self.dispatch("27").returncode, 0)
        path = self.worktree()
        self.assertEqual(git(path, "rev-parse", "HEAD"), git(self.out, "rev-parse", "main"))
        done = self.sweep()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("sweep: nothing to remove", done.stdout)
        self.assertTrue(os.path.isdir(path), done.stdout)

    def test_a_finished_worktree_with_uncommitted_work_is_kept_and_named(self):
        path, head = self.dispatched()
        self.state(merged=((self.BRANCH, head),))
        with open(os.path.join(path, "half-done.txt"), "w", encoding="utf-8") as handle:
            handle.write("not committed\n")
        done = self.sweep()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn(f"kept     {path} ({self.BRANCH}): it has uncommitted or untracked files; "
                      f"look at them before removing it", done.stdout)
        self.assertNotIn("swept", done.stdout)
        self.assertTrue(os.path.isdir(path), done.stdout)
        self.assertIn(self.BRANCH, self.branches(), "the branch of a kept worktree was deleted under it")

    def test_a_branch_with_no_worktree_whose_pull_request_merged_at_its_tip_is_swept(self):
        path, head = self.dispatched()
        # --cleanup takes the worktree and leaves the branch: `git branch -d` judges it unmerged
        # against the local main, which the merged pull request has not moved.
        self.assertEqual(self.dispatch("--cleanup", "27").returncode, 0)
        self.assertIn(self.BRANCH, self.branches())
        self.state(merged=((self.BRANCH, head),))
        done = self.sweep()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"swept    branch {self.BRANCH} (its pull request merged at this tip)", done.stdout)
        self.assertEqual(self.branches(), ["main"], done.stdout)

    def test_the_sweep_says_not_checked_when_github_cannot_be_read_and_removes_nothing(self):
        # The failure this separates from the others: "nothing merged" and "I could not ask" both
        # end with an empty worktree root untouched, and only one of them is a clean repository.
        path, head = self.dispatched()
        self.state(merged=((self.BRANCH, head),))
        done = self.sweep(RULES_ENGINE_GH=os.path.join(self.tmp, "no-such-gh"))
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertIn("NOT CHECKED  merged pull requests could not be read", done.stdout)
        self.assertIn("Nothing was swept, and a worktree or branch left behind by merged work is "
                      "not reported by this run", done.stdout)
        self.assertNotIn("sweep: nothing to remove", done.stdout)
        self.assertTrue(os.path.isdir(path), done.stdout)

    def test_a_dispatch_sweeps_before_it_creates_the_next_worktree(self):
        # The acceptance criterion: nobody has to remember. #27's worktree and branch are gone
        # because #31 was dispatched, and #31's worktree is there.
        path, head = self.dispatched()
        self.state(merged=((self.BRANCH, head),),
                   issues=((27, self.TITLE), (31, "Correct the weight table")))
        done = self.dispatch("31")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"swept    {path} ({self.BRANCH}, its pull request merged at this tip)", done.stdout)
        self.assertFalse(os.path.isdir(path), done.stdout)
        self.assertTrue(os.path.isdir(self.worktree("issue-31-correct-the-weight-table")), done.stdout)
        self.assertEqual(sorted(self.branches()), ["issue-31-correct-the-weight-table", "main"], done.stdout)

    def test_a_dispatch_whose_sweep_cannot_read_github_still_opens_the_worktree(self):
        # An offline agent gets a worktree, told what was not checked. The sweep is hygiene, and
        # hygiene that blocks the work would be turned off.
        self.commit_engine()
        self.state()
        done = self.dispatch("27", RULES_ENGINE_GH=self.gh, GH_PR_LIST_FAILS="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("NOT CHECKED  merged pull requests could not be read", done.stdout)
        self.assertTrue(os.path.isdir(self.worktree()), done.stdout)


class TestTheDoctorsLeftoversRow(MergedWorkInAnEngine):
    """`tools/agent-doctor.py` reports what merged work left behind, and never calls it OK when it
    could not ask (#236).

    The doctor's failure is "I thought the rails were active", and a leftover worktree is the rail
    that stopped: `--cleanup` exists and nothing runs it. The row changes nothing -- the doctor
    never does -- and names the command that would.
    """

    ROW = "Leftovers from merged work"

    def doctor(self, *args, **extra):
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "agent-doctor.py"), *args],
                              cwd=self.out, capture_output=True, text=True, env=self.environment(**extra))

    def row(self, output):
        lines = [line for line in output.splitlines() if line.startswith(self.ROW + " ")]
        self.assertEqual(len(lines), 1, f"expected one `{self.ROW}` row:\n{output}")
        return lines[0]

    def test_a_worktree_left_by_merged_work_is_named(self):
        path, head = self.dispatched()
        self.state(merged=((self.BRANCH, head),))
        done = self.doctor()
        line = self.row(done.stdout)
        self.assertIn("WRONG", line)
        self.assertIn(f"1 left over: {path} (worktree)", line)
        self.assertNotIn("(branch)", line, "the branch of a leftover worktree is counted twice")
        self.assertIn("tools/dispatch-agent.sh --sweep", done.stdout)
        self.assertTrue(os.path.isdir(path), "the doctor removed something; it reports and never acts")

    def test_a_branch_left_by_merged_work_with_no_worktree_is_named(self):
        path, head = self.dispatched()
        self.assertEqual(self.dispatch("--cleanup", "27").returncode, 0)
        self.state(merged=((self.BRANCH, head),))
        line = self.row(self.doctor().stdout)
        self.assertIn("WRONG", line)
        self.assertIn(f"1 left over: {self.BRANCH} (branch)", line)

    def test_a_worktree_still_being_worked_in_is_not_a_leftover(self):
        path, head = self.dispatched()
        self.state()
        line = self.row(self.doctor().stdout)
        self.assertIn("OK", line)
        self.assertIn("no worktree or branch is left over from merged work", line)

    def test_the_row_says_not_checked_when_github_cannot_be_read(self):
        path, head = self.dispatched()
        self.state(merged=((self.BRANCH, head),))
        line = self.row(self.doctor(GH_PR_LIST_FAILS="1").stdout)
        self.assertIn("NOT CHECKED", line)
        self.assertNotIn(" OK ", line)
        self.assertIn("HTTP 403", line)

    def test_local_says_not_checked_rather_than_ok(self):
        path, head = self.dispatched()
        self.state(merged=((self.BRANCH, head),))
        done = self.doctor("--local")
        line = self.row(done.stdout)
        self.assertIn("NOT CHECKED", line)
        self.assertNotIn(" OK ", line)
        self.assertIn("--local", line)


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

    def test_packet_context_comes_from_the_pr_head_not_the_caller_checkout(self):
        # #334: the old packet put head B in its heading while reading policy, provenance and
        # entry context from checkout A. The review then named bytes it had not actually shown.
        self.commit_engine()
        head = self.change()
        policy_path = os.path.join(self.out, ".github", "agent-policy.json")
        policy = json.load(open(policy_path, encoding="utf-8"))
        policy["review"]["semanticContext"] = "rules-verdict/head-b"
        with open(policy_path, "w", encoding="utf-8") as handle:
            json.dump(policy, handle, indent=2)
            handle.write("\n")
        git(self.out, "add", ".github/agent-policy.json")
        git(self.out, "commit", "-qm", "change the review context on the pull request")
        head = git(self.out, "rev-parse", "HEAD")
        self.pull_request(head)

        # The object for B exists, but the process is deliberately launched from A.
        git(self.out, "checkout", "-q", "main")
        out = os.path.join(self.tmp, "head-bound-packet")
        done = self.packet("--out", out)
        self.assertEqual(done.returncode, 0, done.stderr)

        review_path = os.path.join(out, f"pr-5-{head[:12]}.md")
        entry_path = os.path.join(out, "entry-altitude-limit.md")
        manifest_path = os.path.join(out, f"pr-5-{head[:12]}.review.json")
        self.assertTrue(os.path.isfile(manifest_path), "the human packet has no machine-readable identity")
        review = open(review_path, encoding="utf-8").read()
        entry = open(entry_path, encoding="utf-8").read()
        self.assertIn("rules-verdict/head-b", review,
                      "the packet named B but read review policy from checkout A")
        self.assertIn('"status": "implemented"', entry,
                      "the entry packet named B but was generated from checkout A's overlay")

        manifest = json.load(open(manifest_path, encoding="utf-8"))
        self.assertEqual(manifest["reviewedCommit"], head)
        self.assertEqual(manifest["reviewPacket"]["sha256"],
                         hashlib.sha256(open(review_path, "rb").read()).hexdigest())
        self.assertEqual(manifest["entryPackets"][0]["sha256"],
                         hashlib.sha256(open(entry_path, "rb").read()).hexdigest())

    def test_the_reviewed_snapshot_is_removed_on_success_and_refusal(self):
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        before = git(self.out, "worktree", "list", "--porcelain")
        done = self.packet("--stdout")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(git(self.out, "worktree", "list", "--porcelain"), before,
                         "successful packet assembly left its reviewed snapshot attached")

        policy_path = os.path.join(self.out, ".github", "agent-policy.json")
        with open(policy_path, "w", encoding="utf-8") as handle:
            handle.write("{ not valid json\n")
        git(self.out, "add", ".github/agent-policy.json")
        git(self.out, "commit", "-qm", "break the policy at the reviewed head")
        broken = git(self.out, "rev-parse", "HEAD")
        self.pull_request(broken)
        before = git(self.out, "worktree", "list", "--porcelain")
        done = self.packet("--stdout")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("cannot be read at reviewed commit", done.stderr)
        self.assertEqual(git(self.out, "worktree", "list", "--porcelain"), before,
                         "refused packet assembly left its reviewed snapshot attached")

    def test_a_real_packet_for_a_cannot_record_pass_after_the_pr_moves_to_b(self):
        # #334 end to end: the actual packet producer binds A; after the PR moves, the actual
        # recorder consumes that identity and refuses rather than posting a success to B.
        self.commit_engine()
        reviewed = self.change()
        self.pull_request(reviewed)
        out = os.path.join(self.tmp, "review-then-move")
        done = self.packet("--out", out)
        self.assertEqual(done.returncode, 0, done.stderr)
        identity = os.path.join(out, f"pr-5-{reviewed[:12]}.review.json")
        self.assertTrue(os.path.isfile(identity))

        with open(os.path.join(self.out, "README.md"), "a", encoding="utf-8") as handle:
            handle.write("\nadvance after review\n")
        git(self.out, "add", "README.md")
        git(self.out, "commit", "-qm", "advance after review")
        advanced = git(self.out, "rev-parse", "HEAD")

        with open(self.gh, "w", encoding="utf-8") as handle:
            handle.write(GH_STATUS_STUB)
        os.chmod(self.gh, 0o755)
        statuses = os.path.join(self.tmp, "review-then-move-statuses.json")
        with open(statuses, "w", encoding="utf-8") as handle:
            json.dump({}, handle)
        self.fixture({
            "pr": {"5": {"number": 5, "headRefOid": advanced, "state": "OPEN"}},
            "repo": {"nameWithOwner": "owner/engine"},
        })
        recorded = subprocess.run(
            [sys.executable, os.path.join(self.out, "tools", "record-verdict.py"),
             "--pr", "5", "--packet", identity, "--reviewer", "semantic", "--verdict", "pass"],
            cwd=self.out, capture_output=True, text=True,
            env={**self.environment(), "GH_STATUSES": statuses})
        self.assertEqual(recorded.returncode, 1, recorded.stdout + recorded.stderr)
        self.assertIn(reviewed[:12], recorded.stderr)
        self.assertIn(advanced[:12], recorded.stderr)
        self.assertEqual(json.load(open(statuses, encoding="utf-8")), {},
                         "the real stale packet posted a status after the PR moved")

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
        self.assertEqual(written[2], os.path.join(out, f"pr-5-{head[:12]}.review.json"))
        with open(written[0], encoding="utf-8") as handle:
            body = handle.read()
        digest = hashlib.sha256(open(written[1], "rb").read()).hexdigest()
        self.assertIn(digest, body, "the entry packet's digest, so two reviewers can prove they read the same entry")
        identity = json.load(open(written[2], encoding="utf-8"))
        self.assertEqual(identity["reviewedCommit"], head)
        self.assertEqual(identity["baseCommit"], git(self.out, "rev-parse", "main"))
        self.assertEqual(identity["reviewPacket"]["sha256"],
                         hashlib.sha256(open(written[0], "rb").read()).hexdigest())
        self.assertEqual(identity["reviewContext"]["policy"]["path"], ".github/agent-policy.json")
        self.assertEqual(identity["reviewContext"]["provenance"]["path"], "provenance.json")
        self.assertEqual([m["packageId"] for m in identity["reviewContext"]["maps"]],
                         ["RulesFactory.Maps.FaaPart107"])

    def test_a_packet_inside_the_repository_is_refused(self):
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        done = self.packet("--out", os.path.join(self.out, "packets"))
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("never written inside the repository", done.stderr)

    # --- the entry evidence is the map the reviewed commit declares (#356) ---------------------

    def altered_map(self, marker="THE REVIEWER IS READING BYTES NOBODY COMMITTED"):
        """A corpus-map.json the reviewed commit never declared: one entry's evidence rewritten."""
        directory = os.path.join(self.tmp, "altered")
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(PART107, "corpus-map.json"), encoding="utf-8") as handle:
            document = json.load(handle)
        for entry in document["entries"]:
            if entry.get("id") == "altitude-limit":
                entry["evidence"] = marker
        target = os.path.join(directory, "corpus-map.json")
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        return target, marker

    def test_a_package_map_the_reviewed_commit_did_not_declare_is_refused(self):
        """#356: the entry packets are the one input a semantic reviewer reads before the diff.

        `--package-map` is a caller-supplied host path handed straight to the reviewed tree's
        entry-packet.py, so the *overlay* came from the reviewed commit and the *map* came from
        wherever the caller pointed -- while section 3 says both are "the reviewed commit's own
        map/overlay bytes".
        """
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        altered, marker = self.altered_map()
        done = self.packet("--stdout", "--package-map", altered)
        self.assertEqual(done.returncode, 1, done.stdout)
        # The message, not merely the verdict: several rules of this tool refuse with exit 1, and a
        # test that asserts only the code is satisfied by the wrong one firing (#283).
        self.assertIn("is not the map", done.stderr)
        self.assertNotIn(marker, done.stdout, "a refused packet still handed over the altered evidence")

    def test_the_refusal_names_both_digests(self):
        """A refusal that does not say which two things disagree cannot be acted on."""
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        altered, _ = self.altered_map()
        with open(altered, "rb") as handle:
            supplied = hashlib.sha256(handle.read()).hexdigest()
        declared = json.loads(self.read("provenance.json"))["maps"][0]
        (expected,) = [f["sha256"] for f in declared["files"] if f["role"] == "map"]
        done = self.packet("--stdout", "--package-map", altered)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn(supplied[:12], done.stderr)
        self.assertIn(expected[:12], done.stderr)

    def test_the_declared_map_is_accepted_and_its_digest_recorded(self):
        """The honest path still works, and the manifest says which bytes it was built from."""
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        done = self.packet("--out", os.path.join(self.tmp, "packets"))
        self.assertEqual(done.returncode, 0, done.stderr)
        (manifest_path,) = [l for l in done.stdout.split() if l.endswith(".review.json")]
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        with open(os.path.join(PART107, "corpus-map.json"), "rb") as handle:
            supplied = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(one_map(manifest)["readSha256"], supplied,
                         "the manifest records the map bytes the entry packets were built from")

    # --- the bytes hashed are the bytes read, and a refusal writes nothing (#371) --------------

    def substituted_when_the_subprocess_starts(self, path, payload):
        """Rewrite `path` with `payload`'s bytes exactly when `entry-packet.py` starts.

        #371's defect is two opens of one pathname: `map_read_from` hashes the file, and the
        `entry-packet.py` subprocess opens the same name again. Rewriting a regular file from
        another thread between the two is a race a test cannot win reliably, so the substitution
        is put where it can only land between them -- `sitecustomize`, which the subprocess's own
        interpreter imports at startup, after the hash and before the map is read. The guard on
        `argv[0]` keeps it off `review-packet.py` itself, which runs with the same PYTHONPATH.

        Returns the environment addition that arms it.
        """
        directory = os.path.join(self.tmp, "substitute")
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "sitecustomize.py"), "w", encoding="utf-8") as handle:
            handle.write("import sys\n"
                         "if sys.argv and sys.argv[0].endswith('entry-packet.py'):\n"
                         f"    with open({payload!r}, 'rb') as source, open({path!r}, 'wb') as target:\n"
                         "        target.write(source.read())\n")
        return {"PYTHONPATH": directory}

    def test_the_entry_packet_is_built_from_the_bytes_that_were_hashed(self):
        """#371: it hashed one map and opened another.

        The first open is the digest check and sees the map the reviewed commit declares, so the
        check passes; the second open, by the subprocess, sees an altered map. That is #356's
        substitution moved from "never checked" to "checked, then not used".
        """
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        altered, marker = self.altered_map()
        supplied = os.path.join(self.tmp, "supplied-corpus-map.json")
        shutil.copyfile(os.path.join(PART107, "corpus-map.json"), supplied)
        with open(supplied, "rb") as handle:
            declared = handle.read()
        armed = self.substituted_when_the_subprocess_starts(supplied, altered)

        out = os.path.join(self.tmp, "substituted-packets")
        done = subprocess.run([sys.executable, os.path.join(self.out, "tools", "review-packet.py"), "5",
                               "--base", "main", "--package-map", supplied, "--out", out],
                              cwd=self.out, capture_output=True, text=True, env=self.environment(**armed))
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(supplied, "rb") as handle:
            self.assertNotEqual(handle.read(), declared,
                                "the substitution never happened, so this test proves nothing")
        with open(os.path.join(out, "entry-altitude-limit.md"), encoding="utf-8") as handle:
            entry = handle.read()
        self.assertNotIn(marker, entry,
                         "the digest was checked on one read of --package-map and the entry packet "
                         "was built from another")
        with open(os.path.join(out, f"pr-5-{head[:12]}.review.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual(one_map(manifest)["readSha256"],
                         hashlib.sha256(declared).hexdigest(),
                         "the manifest records a digest of bytes the entry packet was not built from")

    def test_a_refused_packet_writes_nothing_and_creates_no_directory(self):
        """#371: `main()` made the output directory before `build()` could refuse."""
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        altered, _ = self.altered_map()
        out = os.path.join(self.tmp, "never-written")
        done = self.packet("--out", out, "--package-map", altered)
        self.assertEqual(done.returncode, 1, done.stdout)
        # The message, not merely the code: this tool refuses in many ways and a test that asserts
        # only exit 1 is satisfied by the wrong refusal (#283).
        self.assertIn("is not the map", done.stderr)
        self.assertFalse(os.path.exists(out), "a refusal left an empty packet directory behind")

    def test_a_refusal_under_stdout_creates_no_directory_either(self):
        """A `--stdout` run writes no packet at all, so a refused one has even less to leave."""
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        altered, _ = self.altered_map()
        out = os.path.join(self.tmp, "never-written-stdout")
        done = self.packet("--stdout", "--out", out, "--package-map", altered)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("is not the map", done.stderr)
        self.assertFalse(os.path.exists(out), "a refused --stdout run created a packet directory")

    # --- a verdict rests on entry evidence that was produced and bound (#372) ------------------

    def unbound(self, *extra):
        """`review-packet.py` with no `--package-map`: the map is whatever MSBuild resolves."""
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "review-packet.py"), "5",
                               "--base", "main", *extra],
                              cwd=self.out, capture_output=True, text=True, env=self.environment())

    def test_an_unbound_packet_that_names_an_entry_is_refused_rather_than_written(self):
        """#372: nothing acted on `readSha256: null`, so a pass could stand for unbound evidence.

        The reviewed snapshot is a freshly created detached worktree with no restore, so the
        MSBuild question cannot be answered in it and the entry packet is not built either. The
        packet is refused rather than written as an identity a verdict can be recorded from.
        """
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        out = os.path.join(self.tmp, "unbound-packets")
        done = self.unbound("--out", out)
        self.assertEqual(done.returncode, 1, done.stdout)
        # The specific refusal, not exit 1 (#283).
        self.assertIn("--package-map", done.stderr)
        self.assertIn("cannot carry a verdict", done.stderr)
        self.assertFalse(os.path.exists(out), "a refused packet left a directory behind")

    def test_an_unbound_packet_can_still_be_read_on_stdout(self):
        """Inspection is not recording: `--stdout` writes no identity, so it stays available."""
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        done = self.unbound("--stdout")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("NOT VERIFIED", done.stdout, "the packet still says the map was not bound")

    def test_a_named_entry_with_no_packet_is_refused_rather_than_written(self):
        """The other way entry evidence goes missing: the packet could not be built at all.

        An identity written anyway names a verdict formed without the one artifact the semantic
        reviewer is told to read first, and nothing in the record says so.
        """
        self.commit_engine()
        head = self.change()
        self.pull_request(head, body="## Linked Issue\nCloses #27\n<!-- rules-factory-entry: no-such-entry -->")
        out = os.path.join(self.tmp, "missing-entry-packets")
        done = self.packet("--out", out)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("no-such-entry", done.stderr)
        self.assertIn("cannot carry a verdict", done.stderr)
        self.assertFalse(os.path.exists(out), "a refused packet left a directory behind")

    def recorder(self, identity, statuses):
        """The real recorder, against the status-keeping stand-in."""
        with open(self.gh, "w", encoding="utf-8") as handle:
            handle.write(GH_STATUS_STUB)
        os.chmod(self.gh, 0o755)
        return subprocess.run(
            [sys.executable, os.path.join(self.out, "tools", "record-verdict.py"),
             "--pr", "5", "--packet", identity, "--reviewer", "semantic", "--verdict", "pass"],
            cwd=self.out, capture_output=True, text=True,
            env={**self.environment(), "GH_STATUSES": statuses})

    def real_identity(self, head, name):
        """A real packet from the real producer, and the path of its identity file."""
        out = os.path.join(self.tmp, name)
        done = self.packet("--out", out)
        self.assertEqual(done.returncode, 0, done.stderr)
        return os.path.join(out, f"pr-5-{head[:12]}.review.json")

    def test_a_verdict_is_refused_when_the_entry_evidence_was_never_bound(self):
        """#372 end to end: the identity #357 wrote for the unbound path, given to the recorder.

        `readSha256: null` beside entry packets is exactly what `review-packet.py` wrote before
        this change, and the recorder accepted it and posted a passing status.
        """
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        identity = self.real_identity(head, "unbound-identity")
        with open(identity, encoding="utf-8") as handle:
            document = json.load(handle)
        self.assertTrue(document["entryPackets"], "this test needs a packet that names entry evidence")
        one_map(document)["readSha256"] = None
        document["reviewContext"]["mapsReadFrom"] = "MSBuild inside the reviewed tree -- NOT VERIFIED"
        with open(identity, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)

        self.fixture({"pr": {"5": {"number": 5, "headRefOid": head, "state": "OPEN"}},
                      "repo": {"nameWithOwner": "owner/engine"}})
        statuses = os.path.join(self.tmp, "unbound-statuses.json")
        with open(statuses, "w", encoding="utf-8") as handle:
            json.dump({}, handle)
        done = self.recorder(identity, statuses)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        # The specific refusal (#283): the recorder refuses for a dozen other reasons too.
        self.assertIn("entry evidence", done.stderr)
        self.assertIn("readSha256", done.stderr)
        with open(statuses, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {}, "a verdict was posted on unbound entry evidence")

    def test_one_unbound_map_among_several_refuses_the_whole_verdict(self):
        """A composed engine is several maps and the entry packets are built from the composition
        (#460, 0067), so bytes nobody held to the record reach the reviewer through one of them
        exactly as they would through a single map. The check is therefore per package, and this
        is the shape a loop that stopped at the first map -- or checked only the first -- would
        pass: the first is bound, the second is not.
        """
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        identity = self.real_identity(head, "one-unbound-identity")
        with open(identity, encoding="utf-8") as handle:
            document = json.load(handle)
        self.assertTrue(document["entryPackets"], "this test needs a packet that names entry evidence")
        bound = one_map(document)
        document["reviewContext"]["maps"] = [
            bound,
            {**bound, "packageId": "RulesFactory.Maps.Second", "readSha256": None},
        ]
        with open(identity, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)

        self.fixture({"pr": {"5": {"number": 5, "headRefOid": head, "state": "OPEN"}},
                      "repo": {"nameWithOwner": "owner/engine"}})
        statuses = os.path.join(self.tmp, "one-unbound-statuses.json")
        with open(statuses, "w", encoding="utf-8") as handle:
            json.dump({}, handle)
        done = self.recorder(identity, statuses)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("RulesFactory.Maps.Second", done.stderr)
        self.assertIn("readSha256", done.stderr)
        with open(statuses, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {}, "a verdict was posted with one map unbound")

    def test_a_verdict_is_refused_when_the_map_read_is_not_the_map_declared(self):
        """The recorder checks the relationship itself rather than trusting the producer's word."""
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        identity = self.real_identity(head, "mismatched-identity")
        with open(identity, encoding="utf-8") as handle:
            document = json.load(handle)
        one_map(document)["readSha256"] = "0" * 64
        with open(identity, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)

        self.fixture({"pr": {"5": {"number": 5, "headRefOid": head, "state": "OPEN"}},
                      "repo": {"nameWithOwner": "owner/engine"}})
        statuses = os.path.join(self.tmp, "mismatched-statuses.json")
        with open(statuses, "w", encoding="utf-8") as handle:
            json.dump({}, handle)
        done = self.recorder(identity, statuses)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("is not the map the reviewed commit declares", done.stderr)
        with open(statuses, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {}, "a verdict was posted on a map that was never declared")

    def test_a_bound_packet_still_records_a_verdict(self):
        """The honest path end to end: the real producer's identity records a pass."""
        self.commit_engine()
        head = self.change()
        self.pull_request(head)
        identity = self.real_identity(head, "bound-identity")
        self.fixture({"pr": {"5": {"number": 5, "headRefOid": head, "state": "OPEN"}},
                      "repo": {"nameWithOwner": "owner/engine"}})
        statuses = os.path.join(self.tmp, "bound-statuses.json")
        with open(statuses, "w", encoding="utf-8") as handle:
            json.dump({}, handle)
        done = self.recorder(identity, statuses)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        with open(statuses, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)[head]["rules-verdict/semantic"], "success")


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

## Documentation

None: this engine has no documents of its own, and nothing here changes one.

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
        self.document("README.md")
        conformance = GOOD_PR_BODY.split("## Map and rules conformance")[1].split("## Tests")[0]
        # The README is off the semantic surface and is a document, so it is accounted for under
        # `## Documentation` and names no entry (#236).
        body = self.listing("- [x] `README.md` — updated: the engine's own overview").replace(
            conformance, "\n\nN/A\n\n")
        self.pull_request(body=body, files=[{"path": "README.md"}])
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

    # --- #236: every pull request accounts for this engine's own documents ---------------------
    #
    # The living-document set is the engine's, not rules-factory's: a document is living when the
    # engine owns it. Everything the factory writes -- AGENTS.md, CLAUDE.md, docs/agent-team.md,
    # the charters, this very template -- is refused a hand edit by `produce`, so asking an engine's
    # pull request to account for one would be asking it to account for a file it may not touch.
    # An **adopted** rail is the engine's from then on, and is living; a numbered decision record is
    # frozen, as in rules-factory. A document the diff changes is listed as `updated` whoever owns
    # it, so a `factory produce` update still says what it did to AGENTS.md.

    def document(self, relative, text="# a document of this engine's own\n"):
        path = os.path.join(self.out, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def listing(self, *lines):
        """GOOD_PR_BODY with its `## Documentation` answer replaced by `lines`."""
        return GOOD_PR_BODY.replace(
            "None: this engine has no documents of its own, and nothing here changes one.",
            "\n".join(lines))

    def test_a_living_document_of_the_engine_left_out_is_a_finding(self):
        self.produced()
        self.document("README.md")
        self.pull_request()
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("`README.md` is a living document of this engine and is not listed", done.stdout)

    def test_a_rail_the_factory_writes_is_not_a_living_document_of_the_engine(self):
        # AGENTS.md, CLAUDE.md and the charters are in every produced engine and in no diff here.
        self.produced()
        self.pull_request()
        done = self.policy_check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("AGENTS.md", done.stdout)
        self.assertIn("0 living document(s)", done.stdout)

    def test_a_document_the_diff_changes_must_be_listed_as_updated(self):
        self.produced()
        self.document("README.md")
        self.pull_request(body=self.listing("- [x] `README.md` — checked, no change: the status table"),
                          files=[{"path": "README.md"}])
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("`README.md` is changed by this pull request but listed as checked, no change",
                      done.stdout)

    def test_a_rail_the_diff_changes_must_be_listed_though_it_is_not_living(self):
        # A `factory produce` update moves AGENTS.md. It is not the engine's document and it is in
        # the diff, so it is accounted for as `updated` like any other changed file.
        self.produced()
        self.pull_request(files=[{"path": "AGENTS.md"}])
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("`AGENTS.md` is changed by this pull request and is not listed", done.stdout)

    def test_an_adopted_rail_is_a_living_document_of_the_engine(self):
        # `--adopt` makes a managed file the engine's own from then on (0018), and a document the
        # engine owns is one an engine change can make untrue.
        self.produced()
        with open(os.path.join(self.out, "AGENTS.md"), "a", encoding="utf-8") as handle:
            handle.write("\n## Our own section\n")
        self.produced("--adopt", "AGENTS.md")
        self.pull_request()
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("`AGENTS.md` is a living document of this engine and is not listed", done.stdout)

    def test_a_decision_record_is_frozen_and_the_rest_of_docs_is_not(self):
        self.produced()
        self.document("docs/decisions/0001-we-decline-rather-than-guess.md")
        self.document("docs/how-we-read-the-corpus.md")
        self.pull_request()
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("`docs/how-we-read-the-corpus.md` is a living document", done.stdout)
        self.assertNotIn("0001-we-decline-rather-than-guess", done.stdout)

    def test_a_line_that_is_not_ticked_or_carries_no_note_is_a_finding(self):
        self.produced()
        self.document("README.md")
        self.document("docs/how-we-read-the-corpus.md")
        self.pull_request(body=self.listing(
            "- [ ] `README.md` — checked, no change: the status table",
            "- [x] `docs/how-we-read-the-corpus.md` — checked, no change:"))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("`README.md` is not ticked", done.stdout)
        self.assertIn("`docs/how-we-read-the-corpus.md` has no note after `checked, no change:`",
                      done.stdout)

    def test_a_listed_path_that_is_neither_living_nor_changed_is_a_typo(self):
        self.produced()
        self.pull_request(body=self.listing("- [x] `READNE.md` — checked, no change: the status table"))
        done = self.policy_check()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("`READNE.md` is neither a living document of this engine nor changed here",
                      done.stdout)

    def test_the_skeleton_lists_the_engines_own_documents_and_no_rail(self):
        self.produced()
        self.document("README.md")
        self.document("docs/how-we-read-the-corpus.md")
        self.document("docs/decisions/0001-we-decline-rather-than-guess.md")
        done = subprocess.run([sys.executable, os.path.join(self.out, "tools", "pr-policy.py"),
                               "--docs-skeleton"], cwd=self.out, capture_output=True, text=True,
                              env=self.environment())
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("## Documentation", done.stdout)
        self.assertIn("- [ ] `README.md` — checked, no change:", done.stdout)
        self.assertIn("- [ ] `docs/how-we-read-the-corpus.md` — checked, no change:", done.stdout)
        self.assertNotIn("AGENTS.md", done.stdout)
        self.assertNotIn("0001-we-decline-rather-than-guess", done.stdout)

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

    def produce_body(self, section=None, evidence=PRODUCE_EVIDENCE, conformance=None, files=()):
        """GOOD_PR_BODY turned into the factory update it would be: the produce section added, the
        entry and locator dropped, and the produce evidence in place of the mutation."""
        record = self.record()
        body = GOOD_PR_BODY
        if section is None:
            section = PRODUCE_SECTION.format(factory=record["factory"]["version"],
                                             map=f"{record['maps'][0]['packageId']} {record['maps'][0]['version']}",
                                             kernel=record["kernel"]["version"], version=record["maps"][0]["version"])
        body = body.replace("## Exact behavioural claim", f"{section}\n## Exact behavioural claim")
        body = body.replace("""- entry id(s): altitude-limit
- map package and version: RulesFactory.Maps.FaaPart107 4.0.0
- source locator(s): § 107.51(b)
- owner's rulings used, if any: none""",
                            conformance if conformance is not None else
                            f"- map package and version: {record['maps'][0]['packageId']} "
                                f"{record['maps'][0]['version']}")
        # Split at `## Documentation`, which now sits between the evidence and the determinism:
        # replacing as far as `## Determinism` would delete a required section from this fixture.
        old_evidence = GOOD_PR_BODY.split("## Tests and evidence")[1].split("## Documentation")[0]
        if evidence is not None:
            body = body.replace(old_evidence, f"\n\n{evidence}\n")
        # Every `*.md` a produce moves is listed as `updated`. This is the case #236 keeps rather
        # than waives: the rails are documents, and a produce is the one thing that changes them.
        moved = sorted(item["path"] for item in files if item["path"].endswith(".md"))
        if moved:
            body = body.replace(
                "None: this engine has no documents of its own, and nothing here changes one.",
                "\n".join(f"- [x] `{path}` — updated: the recipe this produce brought" for path in moved))
        return body

    def produce_request(self, body=None, **extra):
        self.commit_engine()
        files = extra.pop("files", None) or self.produced_files()
        self.pull_request(body=self.produce_body(files=files) if body is None else body,
                          files=files, **extra)

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
        files = self.retired_files()
        self.pull_request(body=self.produce_body(files=files), files=files, base_record=self.retired_base())
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
                                         map=f"{record['maps'][0]['packageId']} 99.0.0",
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

    def review_identity(self, pr="5"):
        """A format-1 review identity for the fixture's current PR head.

        Most verdict tests are about status/gate semantics rather than packet assembly, so they use
        this tiny mechanically self-consistent packet. TestTheReviewPacket proves the real producer.
        """
        fixture = json.load(open(self.fixture_path, encoding="utf-8"))
        head = fixture["pr"][str(pr)]["headRefOid"]
        directory = os.path.join(self.tmp, "record-packets")
        os.makedirs(directory, exist_ok=True)

        human = os.path.join(directory, f"pr-{pr}-{head[:12]}.md")
        with open(human, "w", encoding="utf-8") as handle:
            handle.write(f"# Review packet\n\nHead commit `{head}`.\n")

        policy_path = os.path.join(self.out, ".github", "agent-policy.json")
        provenance_path = os.path.join(self.out, "provenance.json")
        policy_bytes = open(policy_path, "rb").read()
        provenance_bytes = open(provenance_path, "rb").read()
        policy = json.loads(policy_bytes)
        provenance = json.loads(provenance_bytes)

        identity = {
            "reviewPacketFormat": 1,
            "pullRequest": int(pr),
            "reviewedCommit": head,
            "baseCommit": "0" * 40,
            "reviewPacket": {
                "path": os.path.basename(human),
                "sha256": hashlib.sha256(open(human, "rb").read()).hexdigest(),
            },
            "reviewContext": {
                "policy": {
                    "path": ".github/agent-policy.json",
                    "sha256": hashlib.sha256(policy_bytes).hexdigest(),
                    "semanticContext": policy["review"]["semanticContext"],
                    "independentFallback": policy["review"]["independentFallback"],
                },
                "provenance": {
                    "path": "provenance.json",
                    "sha256": hashlib.sha256(provenance_bytes).hexdigest(),
                },
                "maps": [
                    {
                        "packageId": package["packageId"],
                        "version": package["version"],
                        "nupkgSha256": package.get("nupkgSha256", ""),
                    }
                    for package in provenance["maps"]
                ],
            },
            "entryPackets": [],
        }
        path = os.path.join(directory, f"pr-{pr}-{head[:12]}.review.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(identity, handle, indent=2)
            handle.write("\n")
        return path

    def record(self, *args):
        args = list(args)
        if "--packet" not in args:
            pr = args[args.index("--pr") + 1]
            args += ["--packet", self.review_identity(pr)]
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

    def test_a_packet_for_an_earlier_head_cannot_pass_a_newer_head(self):
        # #334: a reviewer forms a verdict on A, the pull request advances to B, and the recorder
        # must consume A's packet identity rather than silently selecting B because it is current.
        self.commit_engine()
        git(self.out, "checkout", "-qb", "issue-27")
        with open(os.path.join(self.out, "README.md"), "a", encoding="utf-8") as handle:
            handle.write("\nreviewed A\n")
        git(self.out, "add", "README.md")
        git(self.out, "commit", "-qm", "reviewed state A")
        reviewed = git(self.out, "rev-parse", "HEAD")

        self.scenario(head=reviewed, files=[{"path": "README.md"}])
        packet_dir = os.path.join(self.tmp, "verdict-packet")
        os.makedirs(packet_dir)
        packet_path = os.path.join(packet_dir, f"pr-5-{reviewed[:12]}.md")
        with open(packet_path, "w", encoding="utf-8") as handle:
            handle.write(f"# Review packet\n\nHead commit `{reviewed}`.\n")
        policy_path = os.path.join(self.out, ".github", "agent-policy.json")
        provenance_path = os.path.join(self.out, "provenance.json")
        manifest_path = os.path.join(packet_dir, f"pr-5-{reviewed[:12]}.review.json")
        policy_bytes = open(policy_path, "rb").read()
        provenance_bytes = open(provenance_path, "rb").read()
        policy = json.loads(policy_bytes)
        provenance = json.loads(provenance_bytes)
        manifest = {
            "reviewPacketFormat": 1,
            "pullRequest": 5,
            "reviewedCommit": reviewed,
            "baseCommit": git(self.out, "rev-parse", "main"),
            "reviewPacket": {"path": os.path.basename(packet_path),
                             "sha256": hashlib.sha256(open(packet_path, "rb").read()).hexdigest()},
            "reviewContext": {
                "policy": {
                    "path": ".github/agent-policy.json",
                    "sha256": hashlib.sha256(policy_bytes).hexdigest(),
                    "semanticContext": policy["review"]["semanticContext"],
                    "independentFallback": policy["review"]["independentFallback"],
                },
                "provenance": {
                    "path": "provenance.json",
                    "sha256": hashlib.sha256(provenance_bytes).hexdigest(),
                },
                "maps": [
                    {
                        "packageId": package["packageId"],
                        "version": package["version"],
                        "nupkgSha256": package.get("nupkgSha256", ""),
                    }
                    for package in provenance["maps"]
                ],
            },
            "entryPackets": [],
        }
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
            handle.write("\n")

        with open(os.path.join(self.out, "README.md"), "a", encoding="utf-8") as handle:
            handle.write("advanced B\n")
        git(self.out, "add", "README.md")
        git(self.out, "commit", "-qm", "advance to state B")
        advanced = git(self.out, "rev-parse", "HEAD")
        self.scenario(head=advanced, files=[{"path": "README.md"}])

        done = self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass",
                           "--packet", manifest_path)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn(reviewed[:12], done.stderr)
        self.assertIn(advanced[:12], done.stderr)
        self.assertEqual(json.load(open(self.statuses, encoding="utf-8")), {},
                         "a stale review posted a status to the newer head")

    def test_sha_is_only_an_assertion_and_cannot_select_another_commit(self):
        self.produced()
        self.scenario(head="a" * 40)
        identity = self.review_identity()
        done = self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass",
                           "--packet", identity, "--sha", "b" * 40)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("--sha says", done.stderr)
        self.assertIn("reviewed packet says", done.stderr)
        self.assertEqual(json.load(open(self.statuses, encoding="utf-8")), {})

    def test_a_tampered_human_packet_cannot_record_a_verdict(self):
        self.produced()
        self.scenario()
        identity = self.review_identity()
        document = json.load(open(identity, encoding="utf-8"))
        human = os.path.join(os.path.dirname(identity), document["reviewPacket"]["path"])
        with open(human, "a", encoding="utf-8") as handle:
            handle.write("changed after review\n")
        done = self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass",
                           "--packet", identity)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("review packet digest does not match", done.stderr)
        self.assertEqual(json.load(open(self.statuses, encoding="utf-8")), {})

    def test_a_tampered_entry_packet_cannot_record_a_verdict(self):
        self.produced()
        self.scenario()
        identity = self.review_identity()
        directory = os.path.dirname(identity)
        entry_path = os.path.join(directory, "entry-altitude-limit.md")
        with open(entry_path, "w", encoding="utf-8") as handle:
            handle.write("# Entry packet: altitude-limit\n")
        document = json.load(open(identity, encoding="utf-8"))
        document["entryPackets"] = [{
            "entryId": "altitude-limit",
            "path": os.path.basename(entry_path),
            "sha256": hashlib.sha256(open(entry_path, "rb").read()).hexdigest(),
        }]
        with open(identity, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)
            handle.write("\n")
        with open(entry_path, "a", encoding="utf-8") as handle:
            handle.write("changed after review\n")

        done = self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass",
                           "--packet", identity)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("entry packet 'altitude-limit' digest does not match", done.stderr)
        self.assertEqual(json.load(open(self.statuses, encoding="utf-8")), {})

    def test_the_verdict_context_is_the_reviewed_packet_s_not_the_caller_checkout_s(self):
        self.produced()
        self.scenario()
        identity = self.review_identity()

        path = os.path.join(self.out, ".github", "agent-policy.json")
        policy = json.load(open(path, encoding="utf-8"))
        policy["review"]["semanticContext"] = "rules-verdict/later-policy"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(policy, handle, indent=2)
            handle.write("\n")

        done = self.record("--pr", "5", "--reviewer", "semantic", "--verdict", "pass",
                           "--packet", identity)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        recorded = json.load(open(self.statuses, encoding="utf-8"))
        self.assertIn("rules-verdict/semantic", recorded["a" * 40])
        self.assertNotIn("rules-verdict/later-policy", recorded["a" * 40])

    def test_recording_without_a_packet_identity_is_explicitly_refused(self):
        self.produced()
        self.scenario()
        done = subprocess.run(
            [sys.executable, os.path.join(self.out, "tools", "record-verdict.py"),
             "--pr", "5", "--reviewer", "semantic", "--verdict", "pass"],
            cwd=self.out, capture_output=True, text=True,
            env={**self.environment(), "GH_STATUSES": self.statuses})
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("review packet identity is required", done.stderr)
        self.assertIn("Legacy verdict statuses remain readable", done.stderr)
        self.assertEqual(json.load(open(self.statuses, encoding="utf-8")), {})

    def test_an_unconfigured_reviewer_is_refused_and_says_what_is_configured(self):
        # The reviewer set is the reviewed packet's, not the engine's current policy, which is the
        # whole of #334: a verdict is about the bytes somebody read. So the refusal names the
        # packet and tells the caller to regenerate and re-review rather than to edit the policy
        # -- editing it would make an old review answer a question it was never asked. This
        # asserted the pre-#334 wording, and both halves of that wording are now wrong.
        self.produced()
        self.scenario()
        done = self.record("--pr", "5", "--reviewer", "a-friend", "--verdict", "pass")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not a reviewer configured by the reviewed packet", done.stderr)
        self.assertIn("Known: semantic", done.stderr)
        self.assertIn("regenerate and re-review the packet", done.stderr)
        self.assertNotIn("edit to .github/agent-policy.json", done.stderr)

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

    def requeue_issue(self, number="27", label="risk:independent-review", action="labeled"):
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "requeue-gate.py")],
                              cwd=self.out, capture_output=True, text=True,
                              env={**self.environment(), "GH_STATUSES": self.statuses, "GH_RERUNS": self.reruns,
                                   "ISSUE_NUMBER": number, "ISSUE_LABEL": label, "ISSUE_ACTION": action})

    def issue_scenario(self, pulls=None, runs=({"id": 991, "run_number": 7, "status": "completed"},)):
        """Open pull requests, each closing issue 27, and the gate runs GitHub holds at their heads."""
        pulls = pulls or {"5": {"number": 5, "headRefOid": HEAD, "state": "OPEN",
                                "closingIssuesReferences": [{"number": 27}]}}
        self.gh_with_statuses()
        self.fixture({
            "pr": pulls,
            "repo": {"nameWithOwner": "owner/engine"},
            "runs": {p["headRefOid"]: list(runs) for p in pulls.values()},
            "rerunFails": False,
        })
        with open(self.statuses, "w", encoding="utf-8") as handle:
            json.dump({}, handle)

    def test_raising_risk_on_the_linked_issue_re_requests_the_gate(self):
        """#230: the gate reads the *issue's* labels and runs on *pull request* events, so this
        was a green required check that no longer reflected the issue's risk -- and the pull
        request could merge without the independent verdict it now needed."""
        self.produced()
        self.issue_scenario()
        done = self.requeue_issue()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.recorded_reruns(), ["991"])
        self.assertIn("#5", done.stdout)

    def test_lowering_risk_re_requests_it_the_same_way(self):
        """Unlabelling is the same event and the same consequence: the gate is asked again, and
        finds the independent verdict no longer required."""
        self.produced()
        self.issue_scenario()
        done = self.requeue_issue(action="unlabeled")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.recorded_reruns(), ["991"])

    def test_a_label_the_gate_does_not_read_re_runs_nothing(self):
        """The filter is the argument, not a precaution on top of it: only the label the engine's
        own policy calls independent risk changes what the gate would answer."""
        self.produced()
        self.issue_scenario()
        done = self.requeue_issue(label="documentation")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual([], self.recorded_reruns())
        self.assertIn("not the risk label", done.stdout)

    def test_an_issue_no_open_pull_request_closes_is_not_a_failure(self):
        """Risk is set when an issue is triaged, usually before anything is opened against it."""
        self.produced()
        self.issue_scenario(pulls={"5": {"number": 5, "headRefOid": HEAD, "state": "OPEN",
                                         "closingIssuesReferences": [{"number": 99}]}})
        done = self.requeue_issue()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual([], self.recorded_reruns())
        self.assertIn("no open pull request closes #27", done.stdout)

    def test_every_open_pull_request_closing_the_issue_is_re_requested(self):
        """Per pull request, not per commit: two pull requests closing one issue head different
        commits, and each has its own gate run."""
        other = "b" * 40
        self.produced()
        self.issue_scenario(pulls={
            "5": {"number": 5, "headRefOid": HEAD, "state": "OPEN",
                  "closingIssuesReferences": [{"number": 27}]},
            "6": {"number": 6, "headRefOid": other, "state": "OPEN",
                  "closingIssuesReferences": [{"number": 27}]},
        })
        done = self.requeue_issue()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(2, len(self.recorded_reruns()), self.recorded_reruns())

    def test_an_issue_number_that_is_not_one_is_refused(self):
        self.produced()
        self.issue_scenario()
        done = self.requeue_issue(number="not-a-number")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not an issue number", done.stderr)

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
        self.assertIn("\n  issues:\n    types: [labeled, unlabeled]\n", text,
                      "the risk label changes outside the pull request and nothing re-ran the gate (#230)")
        body = text.split("jobs:\n", 1)[1]
        jobs = [line.strip().rstrip(":") for line in body.splitlines()
                if line.startswith("  ") and not line.startswith("   ") and line.strip().endswith(":")]
        self.assertEqual(jobs, ["verdict-requeue"],
                         "two check runs of one name are ambiguous; this one lands on the default branch's head")
        # #191's lesson, kept where it applies. A *job* condition is what skipped every status
        # run, and the job still has none: it runs on both events, whichever arrives. The two
        # *steps* are conditional because the workflow now has two events and each step reads a
        # payload the other event does not carry -- and the conditions are asserted exhaustive
        # over the triggers, so neither event can arrive and find nothing to do.
        job = body.split("steps:\n", 1)[0]
        self.assertNotIn("if:", job,
                         "a job condition on this workflow is how #191 skipped every run")
        conditions = re.findall(r"^\s+if: github\.event_name == '(\w+)'$", body, re.M)
        self.assertEqual(sorted(conditions), ["issues", "status"],
                         "each trigger needs exactly one step, or an event arrives and does nothing")
        self.assertIn("format('sha-{0}', github.event.sha)", text)
        self.assertIn("format('issue-{0}', github.event.issue.number)", text,
                      "an issues event carries no commit, so the issue number keys the group")
        self.assertNotIn("github.sha }}", text,
                         "github.sha is the same value for every verdict, and cancel-in-progress is on")
        # The payload is text somebody else wrote: it reaches the script as values, never as script.
        for variable in ("VERDICT_SHA", "VERDICT_CONTEXT", "VERDICT_STATE",
                         "ISSUE_NUMBER", "ISSUE_LABEL", "ISSUE_ACTION"):
            self.assertIn(f"{variable}: ${{{{ github.event.", text)
        self.assertEqual(2, text.count("run: python3 tools/requeue-gate.py\n"),
                         "one invocation per event")

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


class TestAConflictedRecordNamesItsOneCommand(AFactoryToReProduceFrom, RailsInAGitEngine):
    """#252: two entry branches merge, `provenance.json` conflicts, and the refusal says what to do.

    Since the overlay became a directory (#247) an entry's evidence is its own file, so two entry
    branches cut from the same produced commit write no common overlay path. `provenance.json` is
    what is left: it hashes everything, so both branches rewrite the same lines of it and a merge
    leaves markers there and nowhere else. `merged()` asserts exactly that, because it is the
    premise the rest of this rests on -- and because two entries close together in the map also
    conflict in the generated C#, which is a different merge about a different thing.

    A file holding conflict markers is not JSON, and both the gate and `tools/re-produce.sh` read
    the record as JSON, so the one command that recomputes every hash in it could not run until
    somebody had already picked a side -- and neither message named that step. There is nothing
    there to pick: a re-produce overwrites the whole record, so both sides are discarded whichever
    is kept. An operator who has not seen it before opens the file, finds three conflicting
    SHA-256 hunks and has no way to tell which is right, which is the state #242's criterion
    exists to prevent.

    **#283, and why the exit codes here are not the assertion.** Both tools refused a conflicted
    record before this change as well, with the wrong message: `assertEqual(returncode, 1)` passes
    before and after and proves nothing at all. What is asserted is the sentence -- that the
    refusal calls it a merge conflict, says either side is equally good, and names
    `tools/re-produce.sh --resolve-record` -- that the old parse error is gone, that the refusal
    resolved nothing by itself, and that the command it names does the job when it is run.
    """

    #: Two entries from opposite ends of the map, so the record is the only file that conflicts.
    ENTRIES = ("speed-limit", "waivable-regulations")
    IMPLEMENTED = {"status": "implemented", "implementedIn": "Rules/Entry.cs",
                   "tests": [{"name": "Entry_Declines",
                              "mutation": "return the limit instead of declining"}]}

    def setUp(self):
        super().setUp()
        self.produced()
        self.factory, commits = self.factory_repo()
        self.recorded = commits["recorded"]
        self.record_commit(self.recorded)
        self.commit_engine_as_is()

    def entry_branch(self, entry_id):
        """One entry branch cut from the produced commit: its evidence, and a real re-produce."""
        git(self.out, "checkout", "-q", "main")
        git(self.out, "checkout", "-q", "-b", entry_id)
        write_overlay(self.out, {entry_id: self.IMPLEMENTED})
        self.produced()
        # Back to the stand-in factory, so --resolve-record's re-produce below needs no network.
        self.record_commit(self.recorded)
        git(self.out, "add", "-A")
        git(self.out, "commit", "-qm", f"implement {entry_id}")

    def merged(self, first, second):
        """`second` merged into `first`, both cut from the same produced commit."""
        for entry_id in self.ENTRIES:
            self.entry_branch(entry_id)
        git(self.out, "checkout", "-q", first)
        done = subprocess.run(["git", "merge", "--no-edit", second], cwd=self.out,
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 1, f"the merge did not conflict:\n{done.stdout}{done.stderr}")
        unmerged = sorted({line.split("\t", 1)[1] for line in git(self.out, "ls-files", "-u").splitlines()})
        self.assertEqual(unmerged, ["provenance.json"],
                         "#252's premise: the record is the one file two entry branches conflict in")

    def gate(self, *args):
        return subprocess.run([sys.executable, os.path.join(self.out, "scripts", "engine-gate.py"), *args],
                              cwd=self.out, capture_output=True, text=True)

    def refusals(self):
        """What each tool says about the conflicted record, and what the record looked like after."""
        gate = self.gate("provenance")
        reproduce = self.re_produce("--dry-run", repo=self.factory)
        for done in (gate, reproduce):
            # Collapsed, because one of these two is a shell script wrapping its own refusal.
            said = " ".join((done.stdout + done.stderr).split())
            # 1 before this change too, on the parse error: the sentence is the assertion (#283).
            self.assertEqual(done.returncode, 1, said)
            self.assertIn("provenance.json is in a merge conflict", said)
            self.assertIn("either side is equally good", said)
            self.assertIn("tools/re-produce.sh --resolve-record", said)
            self.assertNotIn("is not readable JSON", said,
                             "the old refusal answered with a column number in a file nobody should read")
            self.assertNotIn("cannot be read (", said)
        # Neither of them resolved anybody's merge on the way past.
        self.assertIn("UU provenance.json", git(self.out, "status", "--porcelain"))
        return gate, reproduce

    def test_the_refusal_names_the_one_command_and_that_command_finishes_it(self):
        self.merged(*self.ENTRIES)
        self.refusals()

        done = self.re_produce("--resolve-record", repo=self.factory)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("is in a merge conflict", done.stderr)
        self.assertIn("ours, the branch you are on", done.stderr,
                      "it does not say which side it took")
        with open(os.path.join(self.out, "provenance.json"), encoding="utf-8") as handle:
            json.load(handle)  # readable again, which is the whole of the recovery
        self.assertEqual(git(self.out, "ls-files", "-u"), "", "the record is still unmerged in the index")
        with open(os.path.join(self.out, "re-produced-by.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["version"], "recorded", "the re-produce did not run")

    def test_the_other_merge_order_is_told_the_same_thing(self):
        """Either side is equally good, so which branch was merged into which cannot matter."""
        self.merged(*reversed(self.ENTRIES))
        self.refusals()

    def test_a_record_that_is_broken_rather_than_conflicted_keeps_its_own_message(self):
        """The discriminator: a conflict is somebody's merge, broken JSON is somebody's edit.

        Calling every unreadable record a merge conflict would name `--resolve-record` at an
        operator who has no sides to choose between, so all three markers are required.
        """
        with open(os.path.join(self.out, "provenance.json"), "w", encoding="utf-8") as handle:
            handle.write('{"provenanceFormat": 4,\n')
        said = "".join(part for done in (self.gate("provenance"), self.re_produce("--dry-run", repo=self.factory))
                       for part in (done.stdout, done.stderr))
        self.assertIn("provenance.json is not readable JSON", said)
        self.assertIn("provenance.json cannot be read (", said)
        self.assertNotIn("merge conflict", said)
        self.assertNotIn("--resolve-record", said)


COMMAND = re.compile(r"^(?:\./)?(?:tools|scripts)/[A-Za-z0-9_.\-]+\.(?:py|sh)$")
# What a rail's placeholder stands for here, so the command that runs is the one the rail spells.
# An unknown placeholder fails the test rather than skipping the command it is in: a rail that
# grows a new one is a command nobody has run.
PLACEHOLDERS = {"<n>": "1", "<issue number>": "1", "<entry id>": "speed-limit", "<entry-id>": "speed-limit",
                "<pr>": "1", "<pr number>": "1", "<id>": "semantic", "{args.pr}": "1",
                '"..."': "Title", "pass|fail": "pass",
                # `--package-map <path>`: the map this engine was produced from, which is what an
                # engine's own restore would put there.
                "<path>": os.path.join(PART107, "corpus-map.json"),
                # No such file: record-verdict.py then refuses because the manifest cannot be
                # read -- a refusal about what it was asked, not how it was called (#386).
                "<packet.review.json>": "pr-1-abcdef123456.review.json"}
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

    def test_no_rail_names_a_record_verdict_call_the_recorder_refuses(self):
        """#386: a rail told an agent to run a command refused since #334.

        The test above asks whether a command is refused **for how it was spelled** -- argparse's
        own vocabulary -- and this one is not: `record-verdict.py` parses it happily and then
        refuses because no `--packet` names what was reviewed (0053 section 3). So that test
        cannot see this, correctly, and this is the narrow rule instead: a rail that spells out a
        `record-verdict.py` invocation spells out one that works.

        Mutation: drop `--packet` from either the reviewer's charter or the sentence
        `conformance-gate.py` prints when a semantic verdict is missing. Both went red.
        """
        offenders = []
        for relative, text in sorted(agentrails.rails_files().items()):
            # Over the whole file, not line by line: an invocation is a logical unit and a rail
            # may wrap one across source lines -- `conformance-gate.py` builds its sentence from
            # two adjacent f-string literals, and a per-line scan reads the half without --packet.
            flat = " ".join(text.split())
            for part in flat.split("record-verdict.py")[1:]:
                # An invocation, not a mention: the tool named with arguments after it.
                call = part.split("`")[0]
                if "--" in call and "--packet" not in call:
                    offenders.append(f"{relative}: record-verdict.py{call.strip()[:100]}")
        self.assertEqual(offenders, [],
                         "a rail spells out a record-verdict.py call with no --packet, which the "
                         "recorder refuses before it does anything (#386):\n" + "\n".join(offenders))

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


def array(items):
    """An array endpoint, printed the way `gh api` prints one (#237).

    `--paginate` walks the pages and prints each as its own JSON array, so two pages leave
    `[...][...]` on stdout -- two documents, which `json.loads` will not read. `--slurp` prints
    the pages as one array of arrays instead. Without `--paginate` only the first page comes back,
    as GitHub answers. `state["perPage"]` is the page size, so a fixture can hold a second page
    without thirty labels in it.
    """
    size = int(state.get("perPage", 30))
    pages = [items[at:at + size] for at in range(0, len(items), size)] or [[]]
    if "--paginate" not in argv:
        print(json.dumps(pages[0]))
    elif "--slurp" in argv:
        print(json.dumps(pages))
    else:
        for page in pages:
            print(json.dumps(page))


if argv[0] == "repo" and argv[1] == "view":
    print(json.dumps({"nameWithOwner": state["repo"]}))
    raise SystemExit(0)

if argv[0] == "pr" and argv[1] == "list":
    # The doctor's leftovers row (#236). This fixture is about what GitHub enforces, not about
    # what has merged, so the answer is "nothing has" -- which is an answer, and keeps the row
    # OK rather than NOT CHECKED for every ruleset test below.
    print(json.dumps(state.get("mergedPulls") or []))
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
        array([{"name": n} for n in state["labels"]])
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
    array(rules)
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
        # An organization's rulesets come back beside the repository's own unless the caller says
        # otherwise: `includes_parents` defaults to true on GitHub, so a caller that picks a
        # ruleset by name alone picks an organization's without knowing it (#231, #234).
        parents = [] if "includes_parents=false" in query else state.get("orgRulesets", [])
        array([{"id": r["id"], "name": r["name"], "source_type": r.get("source_type", "Repository"),
                "source": r.get("source", state["repo"])} for r in state["rulesets"] + parents])
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

    def verdict(self, output, name):
        """The state word of one row, whichever of the two tools printed it: each pads its own
        rows to its own width, and what has to agree is the word, not the layout."""
        return self.row(output, name)[len(name):].strip(" .").split("  -- ")[0].strip()

    def doctor(self, *args):
        """The engine's own `tools/agent-doctor.py`, reading the same fake repository."""
        done = subprocess.run([sys.executable, os.path.join(self.out, "tools", "agent-doctor.py"), *args],
                              cwd=self.out, capture_output=True, text=True,
                              env={**os.environ, "RULES_ENGINE_GH": self.gh, "GH_REPO_STATE": self.state_path})
        return done.returncode, done.stdout + done.stderr

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

    # --- #237: a paginated read is pages, not one document ------------------------------------

    FILLERS = ["bug", "chore", "documentation", "duplicate"]

    def test_labels_on_a_later_page_are_not_missing(self):
        # `gh api --paginate` prints each page as its own array, so `[...][...]` reached
        # `json.loads`, failed, and `default=[]` turned the failure into "the repository has no
        # labels": every required label was reported MISSING on a repository that had them all.
        # The row and the reason are asserted, not the exit code alone (#283) -- the exit code was
        # already right, for the wrong reason.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.with_state(perPage=4, labels=self.FILLERS + self.read_state()["labels"])
        code, output = self.rails("--check")
        self.assertEqual(code, 0, output)
        self.assertIn("OK", self.row(output, "Required labels"))
        self.assertNotIn("the repository has no", output)

    def test_apply_does_not_re_create_a_label_on_a_later_page(self):
        # The other half of the same defect: `--apply` read "no labels" and posted the five it
        # would have created, over labels that were already there.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.with_state(perPage=4, labels=self.FILLERS + self.read_state()["labels"])
        before = self.read_state()["labels"]
        code, output = self.rails("--apply")
        self.assertEqual(code, 0, output)
        self.assertNotIn("created label", output)
        self.assertEqual(self.read_state()["labels"], before, "--apply created a label that existed")

    def test_a_ruleset_on_a_later_page_is_found(self):
        # The same read shape, added for the rulesets in #234: there a parse failure reported
        # MISSING rather than OK, and was still wrong about a repository whose rails are in place.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.with_state(perPage=1, orgRulesets=[self.ORG_SIGNING])
        code, output = self.rails("--check")
        self.assertEqual(code, 0, output)
        self.assertIn("OK", self.row(output, "Ruleset on main"))
        self.assertNotIn("no ruleset named rules-factory-agent-rails", output)

    def test_the_rules_in_force_on_a_later_page_are_verified(self):
        # And the third: the rules GitHub enforces on the branch are an array endpoint too, and
        # the factory's ruleset alone puts four rules in it. NOT VERIFIED is the honest word for a
        # read that failed -- this one did not fail.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.with_state(perPage=1, orgRulesets=[self.ORG_SIGNING])
        code, output = self.rails("--check")
        self.assertEqual(code, 0, output)
        line = self.row(output, "Rules in force on main")
        self.assertIn("OK", line)
        self.assertNotIn("NOT VERIFIED", line)
        self.assertIn("org-signed-commits (organization owner): required_signatures", line)

    def test_the_doctor_reads_every_page_of_the_labels_too(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.with_state(perPage=4, labels=self.FILLERS + self.read_state()["labels"])
        code, output = self.doctor()
        # The row and the problem list, not the exit code: since #195 the doctor also reports the
        # machine -- the pinned SDK, a restore, `gh` -- and a machine without the pinned SDK is a
        # problem like any other, so the exit code here would be a fact about the runner rather
        # than about the labels page this test is for.
        self.assertIn("OK", self.row(output, "Labels"))
        self.assertNotIn("the repository has no", output)
        self.assertNotIn("labels", "\n".join(line for line in output.splitlines() if line.startswith("  X  ")))

    # --- #231: the doctor judges a check by its pin, and the ruleset by its level --------------

    def unpin(self, ruleset):
        for rule in ruleset["rules"]:
            if rule["type"] == "required_status_checks":
                rule["parameters"]["required_status_checks"] = [
                    {"context": context} for context in factory.rails_step.REQUIRED_CHECKS]

    def another_app(self, ruleset):
        for rule in ruleset["rules"]:
            if rule["type"] == "required_status_checks":
                for check in rule["parameters"]["required_status_checks"]:
                    check["integration_id"] = self.APP + 1

    def test_the_doctor_says_an_unpinned_required_check_is_not_in_place(self):
        # The doctor reduced each required check to its context name, so a check anyone with
        # status-write access could satisfy read OK in the engine's own report while
        # `factory rails --check` called it WRONG (#231, #186). The row and the problem line are
        # asserted, not the exit code: the doctor exits 1 for any problem at all, and did so here
        # while saying this check was fine.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.edit_ruleset(self.unpin)
        code, output = self.doctor()
        self.assertEqual(code, 1, output)
        self.assertIn("WRONG", self.row(output, "Required check: conformance-gate"))
        self.assertIn("conformance-gate is required but not pinned to the github-actions app", output)

    def test_the_doctor_says_a_check_pinned_to_another_app_is_not_in_place(self):
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        self.edit_ruleset(self.another_app)
        code, output = self.doctor()
        self.assertEqual(code, 1, output)
        self.assertIn("WRONG", self.row(output, "Required check: validate"))
        self.assertIn(f"integration {self.APP + 1!r}, not {self.APP!r}", output)

    def test_a_pin_neither_tool_can_judge_is_not_ok_in_either(self):
        # Without the app's id the pin cannot be judged, and a row that could not judge it may not
        # say OK (#211). It is not WRONG either: nothing was found wrong, nothing was verified.
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        state = self.read_state()
        del state["app"]
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        code, output = self.doctor()
        self.assertEqual(code, 1, output)
        self.assertIn("NOT VERIFIED", self.row(output, "Required check: validate"))
        self.assertIn("would not say which app github-actions is", output)
        self.assertIn("NOT VERIFIED", self.row(self.rails("--check")[1], "Required check: validate"))

    def test_an_organization_ruleset_with_the_factory_s_name_is_not_the_factory_s_to_the_doctor(self):
        # GitHub's ruleset list includes an organization's, so a doctor that found the factory's
        # by name alone reported rails the repository does not have and `--apply` cannot write
        # (#234 fixed the same defect in `factory rails --check`).
        self.produced()
        payload = factory.rails_step.ruleset_payload("main", self.APP)
        self.with_state(rulesets=[], orgRulesets=[{**payload, "id": 902, "source_type": "Organization",
                                                   "source": "owner"}])
        code, output = self.doctor()
        self.assertEqual(code, 1, output)
        self.assertIn("MISSING", self.row(output, "Ruleset on main"))
        self.assertIn("rules-factory-agent-rails (organization owner)", output)

    def test_the_doctor_and_the_factory_agree_about_every_required_check(self):
        # The acceptance of #231: one rule, imported by both, rather than a copy in each. Every
        # fixture is a ruleset an admin can leave behind with the UI.
        fixtures = {
            "as the factory applies it": lambda ruleset: None,
            "an unpinned check": self.unpin,
            "a check pinned to another app": self.another_app,
            "a dropped check": lambda ruleset: ruleset["rules"].__setitem__(
                slice(None), [rule for rule in ruleset["rules"] if rule["type"] != "required_status_checks"]),
        }
        self.produced()
        self.assertEqual(self.rails("--apply")[0], 0)
        applied = json.dumps(self.read_state()["rulesets"])
        for name, change in fixtures.items():
            with self.subTest(name):
                self.with_state(rulesets=json.loads(applied))
                self.edit_ruleset(change)
                doctor = self.doctor()[1]
                checked = self.rails("--check")[1]
                for context in factory.rails_step.REQUIRED_CHECKS:
                    row = f"Required check: {context}"
                    self.assertEqual(self.verdict(doctor, row), self.verdict(checked, row),
                                     f"{row}: the doctor says {self.verdict(doctor, row)!r} and the factory "
                                     f"{self.verdict(checked, row)!r}")

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

    def test_the_machine_is_reported_before_the_rails(self):
        """#195: every rail can be in place on a machine that cannot run the gate.

        What each row *says* depends on the machine, and is not what this asserts. What it asserts
        is that all three are asked, and asked before the rails: a report that every rail is in
        place, made on a machine that cannot run the gate, is the failure #195 is about.
        """
        self.produced()
        done = self.doctor("--local")
        printed = done.stdout.splitlines()
        self.assertTrue(printed[0].startswith("SDK pinned by global.json"), done.stdout)
        self.assertIn("Restore ", done.stdout)
        self.assertIn("gh reads the packet's fields", done.stdout)
        self.assertLess(printed.index(next(line for line in printed if line.startswith("Restore "))),
                        printed.index(next(line for line in printed if line.startswith("Rail files "))),
                        done.stdout)

    def test_a_gh_without_the_packets_field_is_reported(self):
        """#195: the review packet and the conformance gate ask `gh` for a field an older `gh`
        refuses, and the failure surfaced as an unreadable error in the middle of a review."""
        self.produced()
        old = os.path.join(self.out, "old-gh.sh")
        with open(old, "w", encoding="utf-8") as handle:
            handle.write('#!/bin/sh\necho \'Unknown JSON field: "closingIssuesReferences"\' >&2\nexit 1\n')
        os.chmod(old, 0o755)
        done = self.doctor("--local", RULES_ENGINE_GH=old)
        self.assertIn("gh reads the packet's fields", done.stdout)
        self.assertIn("has no --json closingIssuesReferences", done.stdout)
        self.assertIn("$RULES_ENGINE_GH", done.stdout)


# Stand-in for `dotnet test`: prints the next scripted result, and records what the source looked
# like while it ran. That second part is the whole point -- it is how a test can prove the mutation
# was actually in place for the run, rather than trusting the tool's own account of itself.
DOTNET_MUTATION_STUB = '''#!/usr/bin/env python3
import json, os, pathlib, sys
sys.dont_write_bytecode = True

plan = json.loads(pathlib.Path(os.environ["DOTNET_PLAN"]).read_text())
state = pathlib.Path(os.environ["DOTNET_CALLS"])
calls = json.loads(state.read_text()) if state.exists() else []
step = plan[min(len(calls), len(plan) - 1)]
watched = pathlib.Path(os.environ["DOTNET_WATCH"])
calls.append({"argv": sys.argv[1:], "watched": watched.read_text() if watched.exists() else None})
state.write_text(json.dumps(calls))
print(step["say"])
sys.exit(step.get("code", 0))
'''

PROBE = "probe.txt"
ORIGINAL = "alpha\nbeta\ngamma\n"


class TestTheMutationRunner(RailsInAGitEngine):
    """`tools/mutate.py`: the recorded mutation, run (#454).

    Every test here asserts on the file on disk afterwards as well as the exit code. A runner that
    reports the right colour and leaves the tree mutated is worse than no runner, because the next
    thing anybody does is commit.
    """

    def setUp(self):
        super().setUp()
        self.plan_path = os.path.join(self.tmp, "plan.json")
        self.calls_path = os.path.join(self.tmp, "calls.json")
        self.bin = os.path.join(self.tmp, "mutate-bin")
        os.makedirs(self.bin, exist_ok=True)
        stub = os.path.join(self.bin, "dotnet")
        with open(stub, "w", encoding="utf-8") as handle:
            handle.write(DOTNET_MUTATION_STUB)
        os.chmod(stub, 0o755)

    def engine_with_a_probe(self, text=ORIGINAL):
        self.commit_engine()
        return self.put(text)

    def put(self, text):
        path = os.path.join(self.out, PROBE)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def plan(self, *steps):
        with open(self.plan_path, "w", encoding="utf-8") as handle:
            json.dump(list(steps) or [{"say": "Passed!  - Failed:     0, Passed:     1"}], handle)

    def calls(self):
        if not os.path.isfile(self.calls_path):
            return []
        with open(self.calls_path, encoding="utf-8") as handle:
            return json.load(handle)

    def mutate(self, spec, *flags, hatch=True):
        environment = {**os.environ, "PATH": self.bin + os.pathsep + os.environ["PATH"],
                       "DOTNET_PLAN": self.plan_path, "DOTNET_CALLS": self.calls_path,
                       "DOTNET_WATCH": os.path.join(self.out, PROBE)}
        if hatch:
            environment["RULES_ENGINE_ALLOW_PRIMARY_MUTATION"] = "1"
        return subprocess.run([sys.executable, os.path.join(self.out, "tools", "mutate.py"), "-", *flags],
                              input=json.dumps(spec), cwd=self.out, capture_output=True, text=True,
                              env=environment)

    @staticmethod
    def spec(old="beta", new="BETA", count=None, test="ProbeTests.Beta_is_beta", extra_edits=()):
        edit = {"file": PROBE, "old": old, "new": new}
        if count is not None:
            edit["count"] = count
        return {"test": test, "edits": [edit, *extra_edits]}

    def on_disk(self):
        with open(os.path.join(self.out, PROBE), encoding="utf-8") as handle:
            return handle.read()

    # -- the mutation is really applied, and really put back -------------------------------------

    def test_the_source_is_mutated_for_the_run_and_restored_after_it(self):
        self.engine_with_a_probe()
        self.plan({"say": "Passed!  - Failed:     0, Passed:     1"},
                  {"say": "Failed!  - Failed:     1, Passed:     0", "code": 1})
        done = self.mutate(self.spec())
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("RED", done.stdout)
        calls = self.calls()
        self.assertEqual(len(calls), 2, "the baseline run and the mutated run")
        self.assertEqual(calls[0]["watched"], ORIGINAL, "the baseline ran against the unmutated source")
        self.assertEqual(calls[1]["watched"], "alpha\nBETA\ngamma\n", "the mutation was in place")
        self.assertEqual(self.on_disk(), ORIGINAL, "the source was restored")

    def test_only_the_named_test_is_run(self):
        self.engine_with_a_probe()
        self.plan({"say": "Passed!  - Failed:     0, Passed:     1"},
                  {"say": "Failed!  - Failed:     1, Passed:     0", "code": 1})
        self.mutate(self.spec(test="ProbeTests.One"))
        for call in self.calls():
            self.assertIn("--filter", call["argv"])
            self.assertIn("FullyQualifiedName~ProbeTests.One", call["argv"])

    def test_the_source_is_restored_even_when_the_run_blows_up(self):
        """The `finally`, proved by taking `dotnet` away after the mutation is already written."""
        probe = self.engine_with_a_probe()
        environment = {**os.environ, "PATH": self.tmp, "RULES_ENGINE_ALLOW_PRIMARY_MUTATION": "1"}
        done = subprocess.run([sys.executable, os.path.join(self.out, "tools", "mutate.py"), "-", "--no-baseline"],
                              input=json.dumps(self.spec()), cwd=self.out, capture_output=True, text=True,
                              env=environment)
        self.assertNotEqual(done.returncode, 0)
        with open(probe, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), ORIGINAL, "a run that died left the source mutated")

    # -- what it refuses -------------------------------------------------------------------------

    def test_an_ambiguous_old_string_is_refused_and_nothing_is_written(self):
        self.engine_with_a_probe("beta\nbeta\n")
        self.plan()
        done = self.mutate(self.spec())
        self.assertEqual(done.returncode, 1)
        self.assertIn("occurs 2 time(s)", done.stdout + done.stderr)
        self.assertEqual(self.on_disk(), "beta\nbeta\n", "a refused mutation wrote something")

    def test_an_old_string_that_is_not_there_is_refused(self):
        self.engine_with_a_probe()
        self.plan()
        done = self.mutate(self.spec(old="delta"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("occurs 0 time(s)", done.stdout + done.stderr)

    def test_a_spec_whose_second_edit_is_ambiguous_applies_neither(self):
        """Every edit is checked before the first byte is written, so a spec is all or nothing."""
        self.engine_with_a_probe()
        self.plan()
        done = self.mutate(self.spec(extra_edits=({"file": PROBE, "old": "a", "new": "A"},)))
        self.assertEqual(done.returncode, 1)
        self.assertEqual(self.on_disk(), ORIGINAL, "the first edit of a refused spec stayed applied")

    def test_an_edit_outside_the_engine_is_refused(self):
        self.engine_with_a_probe()
        self.plan()
        done = self.mutate({"test": "T.X", "edits": [{"file": "../escape.txt", "old": "a", "new": "b"}]})
        self.assertEqual(done.returncode, 1)
        self.assertIn("outside this engine", done.stdout + done.stderr)

    def test_a_replacement_that_changes_nothing_is_refused(self):
        self.engine_with_a_probe()
        self.plan()
        done = self.mutate(self.spec(new="beta"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("replaces a string with itself", done.stdout + done.stderr)

    def test_the_primary_checkout_is_refused_and_the_hatch_is_the_policy_s(self):
        self.engine_with_a_probe()
        self.plan()
        done = self.mutate(self.spec(), hatch=False)
        self.assertEqual(done.returncode, 1)
        self.assertIn("primary checkout", done.stdout + done.stderr)
        with open(os.path.join(self.out, ".github", "agent-policy.json"), encoding="utf-8") as handle:
            named = json.load(handle)["worktrees"]["primaryMutationEscapeHatch"]
        self.assertIn(named, done.stdout + done.stderr,
                      "the refusal names a variable other than the one the policy configures")
        self.assertEqual(self.calls(), [], "it reached dotnet from the primary checkout")

    # -- the failure the prose cannot name ---------------------------------------------------------

    def test_a_mutation_that_leaves_its_test_green_is_reported_and_exits_non_zero(self):
        self.engine_with_a_probe()
        self.plan({"say": "Passed!  - Failed:     0, Passed:     1"})
        done = self.mutate(self.spec())
        self.assertEqual(done.returncode, 1)
        self.assertIn("GREEN", done.stdout)
        self.assertIn("test nobody has watched fail", done.stdout)
        self.assertEqual(self.on_disk(), ORIGINAL)

    def test_a_mutation_that_does_not_compile_is_not_a_red_test(self):
        self.engine_with_a_probe()
        self.plan({"say": "Passed!  - Failed:     0, Passed:     1"},
                  {"say": "Rules.cs(9,5): error CS1002: ; expected", "code": 1})
        done = self.mutate(self.spec())
        self.assertEqual(done.returncode, 1)
        self.assertIn("DID NOT COMPILE", done.stdout)

    def test_a_filter_that_matches_no_test_is_not_a_red_test(self):
        self.engine_with_a_probe()
        self.plan({"say": "Passed!  - Failed:     0, Passed:     1"},
                  {"say": "Passed!  - Failed:     0, Passed:     0"})
        done = self.mutate(self.spec())
        self.assertEqual(done.returncode, 1)
        self.assertIn("NO TEST MATCHED", done.stdout)

    def test_a_test_that_was_already_red_is_not_evidence_and_is_not_mutated(self):
        """A baseline that is not green means the mutation would prove nothing, so it is not run."""
        self.engine_with_a_probe()
        self.plan({"say": "Failed!  - Failed:     1, Passed:     0", "code": 1})
        done = self.mutate(self.spec())
        self.assertEqual(done.returncode, 1)
        self.assertIn("BASELINE RED", done.stdout)
        self.assertEqual(len(self.calls()), 1, "it mutated a test that was already red")
        self.assertEqual(self.on_disk(), ORIGINAL)

    def test_no_baseline_skips_the_unmutated_run(self):
        self.engine_with_a_probe()
        self.plan({"say": "Failed!  - Failed:     1, Passed:     0", "code": 1})
        done = self.mutate(self.spec(), "--no-baseline")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.calls()), 1, "the baseline ran despite --no-baseline")

    # -- several mutations in one run, which is the point of it ------------------------------------

    def test_several_specs_run_in_one_invocation_and_the_summary_counts_them(self):
        self.engine_with_a_probe()
        self.plan({"say": "Passed!  - Failed:     0, Passed:     1"},
                  {"say": "Failed!  - Failed:     1, Passed:     0", "code": 1},
                  {"say": "Passed!  - Failed:     0, Passed:     1"})
        done = self.mutate([self.spec(test="ProbeTests.One"), self.spec(old="gamma", new="GAMMA",
                                                                       test="ProbeTests.Two")])
        self.assertIn("2 mutation(s): 1 red, 1 not red", done.stdout)
        self.assertEqual(done.returncode, 1)
        self.assertEqual(self.on_disk(), ORIGINAL)

    def test_a_spec_with_no_test_is_refused(self):
        self.engine_with_a_probe()
        self.plan()
        done = self.mutate({"edits": [{"file": PROBE, "old": "beta", "new": "BETA"}]})
        self.assertEqual(done.returncode, 1)
        self.assertIn("names no `test`", done.stdout + done.stderr)
