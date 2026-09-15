#!/usr/bin/env python3
"""The licensed-copy exception (#105, decision 0022) admits one named operator locally, and nothing else.

Every test uses the synthetic corpus in licensed_fixture.py: invented text, never a real licensed
one. `gh` is a fake (`$FACTORY_GH`, as for `backlog --create`) that prints the login it is told to,
or fails; `dotnet` and the engine's gate are test_factory_verify.py's fakes.

Asserted:

  * identity -- the allowlisted login passes; another login, `gh` failing, `gh` missing, and CI
    (`CI` or `GITHUB_ACTIONS`) each refuse, CI before `gh` is even asked;
  * pack-map.py -- with the flag and brandonifco, a local-copy map packs, the locator checker reads
    the file `envVar` names, and the package has the same parts as any other, marked in its nuspec;
    without the flag the old refusal fires unchanged; a non-allowlisted login, `gh` failing, CI,
    `--tag` and an unset `envVar` refuse and write nothing; a committed-copy map packs to the same
    bytes with the flag as without;
  * publish-map.yml -- its two guard steps, extracted from the workflow and run: a local-copy map is
    refused and a committed-copy one passes; a marked package is refused and an unmarked one
    passes; and each guard sits before the step it protects;
  * the factory -- `produce` (with verify), `verify` and `provenance` pass under the exception,
    say `verified locally under the licensed-copy exception by brandonifco`, record
    `licensedCopyException`, and write no corpus bytes into the engine; each refuses without the
    flag, for a non-allowlisted login, when `gh` fails and in CI; recompute names the field when a
    different operator re-produces, and an engine holding corpus/ files is refused;
  * no quotation leaves the machine -- no file of the local-copy engine carries any `evidence`,
    `note` or `ambiguity.question` string of the map (backlog items carry the withheld notice and the
    locator instead); `backlog --create` posts bodies carrying none of them, and refuses before any
    `gh` call a body that does, one without the notice, or when the map cannot be found; a
    committed-copy engine (hoyle-backgammon) is byte-identical with the flag and without, and still
    quotes its evidence;
  * pack-map.py hashes the local copy first, so a wrong edition does not pack;
  * an owner's ruling on the licensed corpus (0027 as amended 2026-09-15) is produced, verified and
    recomputed with its span named by offsets and hash: no engine file carries a word of the
    question, and the engine's own merge step accepts it given the package manifest and refuses it
    without; a span quoting the question is refused before anything is written, and so is an answer
    carrying fifteen words of the map.

pack-map.py runs in-process here, so the fixture's derivation can be added to intake's for it.

Run: python3 -m unittest discover -s tools/tests
"""
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
WORKFLOW = os.path.join(REPO, ".github", "workflows", "publish-map.yml")

sys.path.insert(0, HERE)
import licensed_fixture as fixture  # noqa: E402
from test_factory_verify import FAKE_DOTNET, FAKE_GATE  # noqa: E402
from test_factory_backlog import STUB as ISSUE_STUB  # noqa: E402
from test_factory_rulings import (EVIDENCE, OPPOSING_PART, OWN_PART, licensed_example,  # noqa: E402
                                  write_record)

_spec = importlib.util.spec_from_file_location("factory_main_licensed", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
licensed_copy = factory.licensed_copy
intake = factory.intake_step
verify_step = factory.verify_step
backlog = factory.backlog_step

_pack_spec = importlib.util.spec_from_file_location("pack_map_licensed", PACK)
pack_map = importlib.util.module_from_spec(_pack_spec)
_pack_spec.loader.exec_module(pack_map)

OPERATOR = "brandonifco"
ATTESTATION = f"verified locally under the licensed-copy exception by {OPERATOR}"
OLD_REFUSAL = f"NOT VERIFIED -- {fixture.SOURCE_ID} is 'local-copy', not `committed-copy`"


def clean_environ():
    """os.environ without the CI markers a GitHub runner sets, which would refuse every allowed case."""
    return {k: v for k, v in os.environ.items() if k not in ("CI", "GITHUB_ACTIONS")}


def pack_in_process(argv, env):
    """pack-map.py's main in this process, so the fixture's derivation can be added to intake's for it."""
    buffer = io.StringIO()
    with mock.patch.dict(os.environ, env, clear=True), fixture.derivation(intake), \
            redirect_stdout(buffer), redirect_stderr(buffer):
        code = pack_map.main(list(argv))
    return code, buffer.getvalue()


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.map_dir, self.corpus = fixture.write(os.path.join(self.tmp, "fixture"))
        self.gh = fixture.fake_gh(self.tmp)
        self.gh_log = os.path.join(self.tmp, "gh.log")

    def env(self, login=OPERATOR, **extra):
        env = {**clean_environ(), "FACTORY_GH": self.gh, "FAKE_GH_LOG": self.gh_log, "FAKE_GH_LOGIN": login,
               fixture.ENV_VAR: self.corpus}
        env.pop("FAKE_GH_FAIL", None)
        env.update(extra)
        return {k: v for k, v in env.items() if v is not None}

    def gh_calls(self):
        if not os.path.exists(self.gh_log):
            return []
        with open(self.gh_log, encoding="utf-8") as handle:
            return handle.read().splitlines()


class TestIdentity(Case):
    def test_the_allowlisted_login_is_the_operator(self):
        self.assertEqual(licensed_copy.authorise(env=self.env()), OPERATOR)
        self.assertEqual(self.gh_calls(), ["api user --jq .login"], "the identity is gh's, asked once")

    def test_the_committed_allowlist_holds_brandonifco_only(self):
        self.assertEqual(licensed_copy.operators(), [OPERATOR])

    def test_another_login_is_refused(self):
        with self.assertRaisesRegex(licensed_copy.Refused, "authenticated as someone-else, who is not in"):
            licensed_copy.authorise(env=self.env(login="someone-else"))

    def test_gh_failing_is_refused(self):
        with self.assertRaisesRegex(licensed_copy.Refused, "gh auth login"):
            licensed_copy.authorise(env=self.env(FAKE_GH_FAIL="1"))

    def test_gh_missing_is_refused(self):
        with self.assertRaisesRegex(licensed_copy.Refused, "cannot run"):
            licensed_copy.authorise(env=self.env(FACTORY_GH=os.path.join(self.tmp, "nowhere", "gh")))

    def test_ci_is_refused_before_gh_is_asked(self):
        for marker in ({"CI": "true"}, {"GITHUB_ACTIONS": "true"}, {"CI": "1"}):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(licensed_copy.Refused, "refused in CI"):
                    licensed_copy.authorise(env=self.env(**marker))
        self.assertEqual(self.gh_calls(), [])

    def test_git_config_is_not_an_identity(self):
        env = self.env(FAKE_GH_FAIL="1", GIT_AUTHOR_NAME=OPERATOR, GIT_COMMITTER_NAME=OPERATOR,
                       GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="user.name", GIT_CONFIG_VALUE_0=OPERATOR)
        with self.assertRaises(licensed_copy.Refused):
            licensed_copy.authorise(env=env)


class TestPackMap(Case):
    def pack(self, *extra, env=None, map_dir=None, out=None):
        out = out or os.path.join(self.tmp, "out")
        code, output = pack_in_process([map_dir or self.map_dir, "--out", out, *extra],
                                       env if env is not None else self.env())
        return code, output, out

    def packages(self, out):
        return sorted(os.listdir(out)) if os.path.isdir(out) else []

    def test_the_operator_packs_a_local_copy_map_marked_unpublishable(self):
        code, output, out = self.pack(licensed_copy.FLAG)
        self.assertEqual(code, 0, output)
        self.assertIn("the local copy at $" + fixture.ENV_VAR, output)
        self.assertIn(f"the local copy at ${fixture.ENV_VAR} hashes to the manifest's contentHash", output)
        self.assertIn(self.corpus, output, "the locator checker read the file envVar names")
        self.assertIn(f"{ATTESTATION}: NOT PUBLISHABLE", output)
        (name,) = self.packages(out)
        with zipfile.ZipFile(os.path.join(out, name)) as archive:
            names = archive.namelist()
            nuspec = archive.read(f"{fixture.PACKAGE_ID}.nuspec").decode("utf-8")
            contents = b"".join(archive.read(n) for n in names)
        self.assertEqual([n for n in names if "core-properties" not in n], [
            "_rels/.rels", f"{fixture.PACKAGE_ID}.nuspec", "map/corpus-map.json", "map/corpus-manifest.json",
            "tools/check-map.py", f"build/{fixture.PACKAGE_ID}.props", "LICENCE.txt", "[Content_Types].xml"])
        self.assertRegex(nuspec, r"<tags>[^<]*\blicensed-copy-exception</tags>")
        self.assertIn(f"NOT PUBLISHABLE: built locally under the licensed-copy exception by {OPERATOR}", nuspec)
        self.assertNotIn(fixture.corpus_bytes(), contents, "the package carries no corpus")

    def test_without_the_flag_the_refusal_is_unchanged(self):
        code, output, out = self.pack()
        self.assertEqual(code, 1, output)
        self.assertIn(f"pack-map: REFUSED -- {OLD_REFUSAL}, so no publish job can read the corpus to check a "
                      f"citation. No package was written.", output)
        self.assertEqual(self.packages(out), [])
        self.assertEqual(self.gh_calls(), [], "no identity is asked for without the flag")

    def assert_refused(self, expected, *extra, env=None):
        code, output, out = self.pack(*extra, env=env)
        self.assertEqual(code, 1, output)
        self.assertIn(expected, output)
        self.assertEqual(self.packages(out), [])

    def test_a_login_not_on_the_allowlist_is_refused(self):
        self.assert_refused("authenticated as someone-else", licensed_copy.FLAG, env=self.env(login="someone-else"))

    def test_gh_failing_is_refused(self):
        self.assert_refused("gh auth login", licensed_copy.FLAG, env=self.env(FAKE_GH_FAIL="1"))

    def test_the_flag_is_refused_in_ci(self):
        self.assert_refused("refused in CI", licensed_copy.FLAG, env=self.env(CI="true"))
        self.assert_refused("refused in CI", licensed_copy.FLAG, env=self.env(GITHUB_ACTIONS="true"))

    def test_the_flag_is_refused_on_the_publish_path(self):
        self.assert_refused("--tag is the publish path", licensed_copy.FLAG, "--tag",
                            f"map/{fixture.MAP_NAME}/v{fixture.VERSION}")

    def test_a_wrong_edition_of_the_local_copy_is_refused(self):
        with open(self.corpus, "ab") as handle:
            handle.write(b"\n{3}\nA later printing adds this page.\n")
        self.assert_refused(f"is not {fixture.SOURCE_ID} at the manifest's baseline", licensed_copy.FLAG)

    def test_an_unset_env_var_is_not_verified(self):
        self.assert_refused(f"${fixture.ENV_VAR} is not set", licensed_copy.FLAG, env=self.env(**{fixture.ENV_VAR: None}))

    def test_a_committed_copy_map_packs_the_same_bytes_with_the_flag(self):
        code, output, plain = self.pack(map_dir=HOYLE, out=os.path.join(self.tmp, "plain"))
        self.assertEqual(code, 0, output)
        code, output, flagged = self.pack(licensed_copy.FLAG, map_dir=HOYLE, out=os.path.join(self.tmp, "flagged"))
        self.assertEqual(code, 0, output)
        self.assertNotIn("licensed-copy exception", output, "the exception was not used, so nothing says it was")
        (name,) = self.packages(plain)
        with open(os.path.join(plain, name), "rb") as a, open(os.path.join(flagged, name), "rb") as b:
            self.assertEqual(a.read(), b.read())


def workflow_step(name):
    """(job, env, run script) of the publish-map.yml step called `name`, read from the file as written."""
    with open(WORKFLOW, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    job = None
    for index, line in enumerate(lines):
        match = re.match(r"^  ([a-z-]+):\s*$", line)
        if match:
            job = match.group(1)
        if line.strip() == f"- name: {name}":
            indent = len(line) - len(line.lstrip())
            body = []
            for later in lines[index + 1:]:
                if later.strip() and len(later) - len(later.lstrip()) <= indent:
                    break
                body.append(later)
            text = "\n".join(body)
            run = re.search(r"^(\s*)run: \|\n((?:\1  .*\n?|\s*\n)+)", text + "\n", re.M)
            env = dict(re.findall(r"^\s+([A-Z_]+): (.*)$", text.split("run:")[0], re.M))
            return job, env, textwrap.dedent(run.group(2))
    raise AssertionError(f"publish-map.yml has no step {name!r}")


def step_order(job):
    with open(WORKFLOW, encoding="utf-8") as handle:
        text = handle.read()
    section = text.split(f"\n  {job}:\n", 1)[1]
    section = re.split(r"\n  [a-z-]+:\n", section, 1)[0]
    return re.findall(r"^\s+- name: (.*)$", section, re.M)


class TestPublishWorkflow(Case):
    LOCAL = "Refuse a local-copy map"
    MARKED = "Refuse a package built under the licensed-copy exception"

    def run_step(self, name, cwd, **env):
        _, _, script = workflow_step(name)
        done = subprocess.run(["bash", "-e", "-c", script], cwd=cwd, env={**clean_environ(), **env},
                              capture_output=True, text=True)
        return done.returncode, done.stdout + done.stderr

    def test_the_gate_refuses_a_local_copy_map_and_passes_a_committed_copy_one(self):
        job, env, _ = workflow_step(self.LOCAL)
        self.assertEqual(job, "gate")
        self.assertEqual(env, {"MAP": "${{ steps.tag.outputs.map }}"})
        repo = os.path.join(self.tmp, "checkout")
        shutil.copytree(self.map_dir, os.path.join(repo, "examples", fixture.MAP_NAME))
        shutil.copytree(HOYLE, os.path.join(repo, "examples", "hoyle-backgammon"),
                        ignore=shutil.ignore_patterns("produced-engine", "blind-mapping"))
        code, output = self.run_step(self.LOCAL, repo, MAP=fixture.MAP_NAME)
        self.assertEqual(code, 1, output)
        self.assertIn("never published", output)
        code, output = self.run_step(self.LOCAL, repo, MAP="hoyle-backgammon")
        self.assertEqual(code, 0, output)

    def test_the_publish_job_refuses_a_marked_package_and_passes_an_unmarked_one(self):
        job, _, _ = workflow_step(self.MARKED)
        self.assertEqual(job, "publish")
        env = self.env()
        marked = os.path.join(self.tmp, "marked")
        code, output = pack_in_process([self.map_dir, "--out", os.path.join(marked, "artifacts"),
                                        licensed_copy.FLAG], env)
        self.assertEqual(code, 0, output)
        code, output = self.run_step(self.MARKED, marked)
        self.assertEqual(code, 1, output)
        self.assertIn("built under the licensed-copy exception", output)
        plain = os.path.join(self.tmp, "plain")
        subprocess.run([sys.executable, PACK, HOYLE, "--out", os.path.join(plain, "artifacts")], check=True,
                       capture_output=True)
        code, output = self.run_step(self.MARKED, plain)
        self.assertEqual(code, 0, output)
        os.makedirs(os.path.join(self.tmp, "empty", "artifacts"))
        code, output = self.run_step(self.MARKED, os.path.join(self.tmp, "empty"))
        self.assertEqual(code, 1, "no package examined is not a pass")

    def test_each_guard_runs_before_what_it_protects(self):
        gate = step_order("gate")
        self.assertLess(gate.index(self.LOCAL), gate.index("Gate and pack"))
        publish = step_order("publish")
        self.assertLess(publish.index("Re-pack, and require the bytes the gate checked"), publish.index(self.MARKED))
        self.assertLess(publish.index(self.MARKED), publish.index("Exchange the OIDC token for a short-lived API key"))
        self.assertLess(publish.index(self.MARKED), publish.index("Push to nuget.org"))

    def test_the_workflow_never_passes_the_flag_and_its_pack_command_refuses_it_in_ci(self):
        with open(WORKFLOW, encoding="utf-8") as handle:
            self.assertNotRegex(handle.read(), r"pack-map\.py[^\n]*--licensed-copy-exception")
        _, _, script = workflow_step("Gate and pack")
        self.assertIn("--tag", script)
        # The gate job's pack, as a runner would run it with the flag appended.
        code = subprocess.run([sys.executable, PACK, self.map_dir, "--out", os.path.join(self.tmp, "ci"),
                               licensed_copy.FLAG], env=self.env(CI="true", GITHUB_ACTIONS="true"),
                              capture_output=True).returncode
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "ci")))


def run(argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = factory.main(argv)
    return code, buffer.getvalue()


class FactoryCase(Case):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        map_dir, cls.shared_corpus = fixture.write(os.path.join(cls.shared, "fixture"))
        gh = fixture.fake_gh(cls.shared)
        env = {**clean_environ(), "FACTORY_GH": gh, "FAKE_GH_LOG": os.path.join(cls.shared, "gh.log"),
               "FAKE_GH_LOGIN": OPERATOR, fixture.ENV_VAR: cls.shared_corpus}
        out = os.path.join(cls.shared, "package")
        code, output = pack_in_process([map_dir, "--out", out, licensed_copy.FLAG], env)
        assert code == 0, output
        (name,) = os.listdir(out)
        cls.nupkg = os.path.join(out, name)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        super().setUp()
        bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(bin_dir)
        fake = os.path.join(bin_dir, "dotnet")
        with open(fake, "w", encoding="utf-8") as handle:
            handle.write(FAKE_DOTNET)
        os.chmod(fake, 0o755)
        self.fake_gate = os.path.join(self.tmp, "fake-gate.py")
        with open(self.fake_gate, "w", encoding="utf-8") as handle:
            handle.write(FAKE_GATE)
        self.gate_env = []
        real_run = verify_step._run

        def run_with_fake_gate(stage, argv, cwd, log, env=None):
            if stage != "gate":
                return real_run(stage, argv, cwd, log, env)
            self.gate_env.append(env)
            return real_run(stage, [sys.executable, self.fake_gate], cwd, log, env)

        for patcher in (mock.patch.object(verify_step, "_run", run_with_fake_gate), fixture.derivation(intake)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dotnet = {"FACTORY_DOTNET": fake, "FAKE_DOTNET_LOG": os.path.join(self.tmp, "dotnet.log")}
        self.engine = os.path.join(self.tmp, "engine")

    def factory(self, *argv, login=OPERATOR, **extra):
        with mock.patch.dict(os.environ, {**self.env(login=login, **self.dotnet), **extra}, clear=True):
            return run(list(argv))

    def produce(self, *extra, **env):
        return self.factory("produce", "--package", self.nupkg, "--corpus", self.corpus, "--name", fixture.ENGINE,
                            "--out", self.engine, "--allow-dirty", *extra, **env)

    def produced(self):
        code, output = self.produce(licensed_copy.FLAG)
        self.assertEqual(code, 0, output)
        return output

    def record(self):
        with open(os.path.join(self.engine, "provenance.json"), encoding="utf-8") as handle:
            return json.load(handle)


class TestFactory(FactoryCase):
    def test_produce_verifies_and_records_the_exception_without_committing_the_corpus(self):
        output = self.produced()
        self.assertIn("ok   gate: scripts/validate.sh full passed", output)
        self.assertEqual(output.strip().splitlines()[-1], f"produced {fixture.ENGINE} in {self.engine}, {ATTESTATION}")
        self.assertNotRegex(output, r"(?m), verified$")
        self.assertEqual(self.record()["licensedCopyException"], {"operator": OPERATOR, "corpus": fixture.SOURCE_ID})
        self.assertEqual(os.environ.get(fixture.ENV_VAR), None, "the test did not leak its environment")
        (gate_env,) = self.gate_env
        self.assertEqual(gate_env[fixture.ENV_VAR], self.corpus, "the engine's gate reads the local copy from envVar")

        corpus = fixture.corpus_bytes()
        self.assertFalse(os.path.exists(os.path.join(self.engine, "corpus")))
        for directory, _, names in os.walk(self.engine):
            for name in names:
                with open(os.path.join(directory, name), "rb") as handle:
                    self.assertNotIn(corpus, handle.read(), os.path.join(directory, name))
        self.assertFalse(any(g["path"].startswith("corpus/") for g in self.record()["generated"]))

    def test_no_engine_file_carries_the_corpus_text_the_map_quotes(self):
        self.produced()
        strings = backlog.quoted_strings(fixture.map_document())
        self.assertEqual(len(strings), 6, "two distinct evidence spans, three notes over 12 characters, one question")
        self.assertTrue(any("another pawn occupies" in s for s in strings))
        examined = 0
        for directory, _, names in os.walk(self.engine):
            for name in names:
                path = os.path.join(directory, name)
                with open(path, "rb") as handle:
                    flat = " ".join(handle.read().decode("utf-8", "replace").split())
                examined += 1
                for text in strings:
                    self.assertNotIn(text, flat, path)
        self.assertGreater(examined, 20)
        with open(os.path.join(self.engine, "backlog", "003-occupied-square.md"), encoding="utf-8") as handle:
            item = handle.read()
        self.assertEqual(item.count(backlog.WITHHELD), 3, "evidence, the ambiguity question and the note")
        self.assertIn("Skirmish / p. 2", item, "the locator is kept")
        self.assertIn("- kind: `operation`", item, "structural fields are kept")
        self.assertIn("Fate: `unresolved`; unresolvedReason: `RequiresInterpretation`", item)

    def test_a_committed_copy_engine_is_unchanged_and_still_quotes(self):
        hoyle_pack = os.path.join(self.tmp, "hoyle-package")
        subprocess.run([sys.executable, PACK, HOYLE, "--out", hoyle_pack], check=True, capture_output=True)
        (name,) = os.listdir(hoyle_pack)
        trees = []
        for label, extra in (("plain", ()), ("flagged", (licensed_copy.FLAG,))):
            out = os.path.join(self.tmp, label)
            code, output = self.factory("produce", "--package", os.path.join(hoyle_pack, name), "--corpus",
                                        os.path.join(HOYLE, "hoyle.txt"), "--name", "HoyleBackgammon", "--out", out,
                                        "--allow-dirty", "--no-verify", *extra)
            self.assertEqual(code, 0, output)
            tree = {}
            for directory, _, names in os.walk(out):
                for file_name in names:
                    path = os.path.join(directory, file_name)
                    with open(path, "rb") as handle:
                        tree[os.path.relpath(path, out)] = handle.read()
            trees.append(tree)
        self.assertEqual(trees[0], trees[1], "the exception changes nothing for a committed-copy corpus")
        with open(os.path.join(HOYLE, "corpus-map.json"), encoding="utf-8") as handle:
            evidence = json.load(handle)["entries"][0]["evidence"]
        backlog_text = b"".join(v for k, v in trees[0].items() if k.startswith("backlog")).decode("utf-8")
        self.assertIn(evidence, backlog_text)
        self.assertNotIn(backlog.WITHHELD, backlog_text)
        self.assertIn("corpus/hoyle.txt", trees[0])

    def backlog_create(self, *extra):
        state = os.path.join(self.tmp, "issues.json")
        stub = os.path.join(self.tmp, "issue-gh")
        with open(stub, "w", encoding="utf-8") as handle:
            handle.write(ISSUE_STUB.format(python=sys.executable))
        os.chmod(stub, 0o755)
        code, output = self.factory("backlog", "--create", "--repo", "example/engine", "--dir", self.engine, *extra,
                                    FACTORY_GH=stub, GH_STUB_STATE=state,
                                    NUGET_PACKAGES=os.path.join(self.tmp, "empty-nuget"))
        issues = []
        if os.path.exists(state):
            with open(state, encoding="utf-8") as handle:
                issues = json.load(handle)
        calls = []
        if os.path.exists(state + ".calls"):
            with open(state + ".calls", encoding="utf-8") as handle:
                calls = [json.loads(line) for line in handle]
        return code, output, issues, calls

    def test_backlog_create_posts_locator_only_bodies(self):
        self.produced()
        code, output, issues, _ = self.backlog_create("--package", self.nupkg)
        self.assertEqual(code, 0, output)
        self.assertIn("bodies carry no text from the corpus (6 quoted strings of the map compared)", output)
        self.assertEqual(len(issues), 3)
        strings = backlog.quoted_strings(fixture.map_document())
        for issue in issues:
            flat = " ".join((issue["title"] + " " + issue["body"]).split())
            for text in strings:
                self.assertNotIn(text, flat)
            self.assertIn(backlog.WITHHELD, issue["body"])
            self.assertIn("Skirmish / p.", issue["body"])

    def test_backlog_create_refuses_a_body_carrying_corpus_text_before_any_call(self):
        self.produced()
        item = os.path.join(self.engine, "backlog", "002-one-pawn-per-turn.md")
        with open(item, "a", encoding="utf-8") as handle:
            handle.write("\nA captain moves one pawn per turn,\nand never onto a square another pawn occupies.\n")
        code, output, issues, calls = self.backlog_create("--package", self.nupkg)
        self.assertEqual(code, 1, output)
        self.assertIn("002-one-pawn-per-turn.md (it contains text the map quotes", output)
        self.assertEqual((issues, calls), ([], []), "gh was never called")

    def test_backlog_create_refuses_a_body_without_the_withheld_notice(self):
        self.produced()
        item = os.path.join(self.engine, "backlog", "001-captain-count.md")
        with open(item, encoding="utf-8") as handle:
            text = handle.read()
        with open(item, "w", encoding="utf-8") as handle:
            handle.write(text.replace(backlog.WITHHELD, "(nothing)\n"))
        code, output, _, calls = self.backlog_create("--package", self.nupkg)
        self.assertEqual(code, 1, output)
        self.assertIn("001-captain-count.md (it does not carry the withheld notice", output)
        self.assertEqual(calls, [])

    def test_backlog_create_refuses_when_the_map_cannot_be_found(self):
        self.produced()
        code, output, _, calls = self.backlog_create()
        self.assertEqual(code, 1, output)
        self.assertIn("not a local file or in the NuGet global packages folder", output)
        self.assertEqual(calls, [])

    def test_verify_and_provenance_pass_under_the_exception_and_say_so(self):
        self.produced()
        code, output = self.factory("verify", "--engine", self.engine, "--package", self.nupkg, licensed_copy.FLAG)
        self.assertEqual(code, 0, output)
        self.assertEqual(output.strip().splitlines()[-1], f"verify {self.engine}: PASS, {ATTESTATION}")
        code, output = self.factory("provenance", "--engine", self.engine, "--package", self.nupkg, licensed_copy.FLAG)
        self.assertEqual(code, 0, output)
        self.assertEqual(output.strip(), f"provenance of {self.engine}: every field matches, {ATTESTATION}")

    def test_without_the_flag_every_command_refuses_as_today(self):
        code, output = self.produce()
        self.assertEqual(code, 1, output)
        self.assertIn(OLD_REFUSAL, output)
        self.assertFalse(os.path.exists(self.engine))
        self.assertEqual(self.gh_calls(), [])
        self.produced()
        code, output = self.factory("provenance", "--engine", self.engine, "--package", self.nupkg)
        self.assertEqual(code, 1, output)
        self.assertIn(f"produce refused to re-produce the engine, so nothing else was compared: {OLD_REFUSAL}", output)
        code, output = self.factory("verify", "--engine", self.engine, "--package", self.nupkg)
        self.assertEqual(code, 1, output)
        self.assertIn("verify FAILED at stage provenance", output)

    def test_a_login_not_on_the_allowlist_is_refused_everywhere(self):
        code, output = self.produce(licensed_copy.FLAG, login="someone-else")
        self.assertEqual(code, 1, output)
        self.assertIn("authenticated as someone-else, who is not in", output)
        self.assertFalse(os.path.exists(self.engine))
        self.produced()
        for command in ("verify", "provenance"):
            with self.subTest(command=command):
                code, output = self.factory(command, "--engine", self.engine, "--package", self.nupkg,
                                            licensed_copy.FLAG, login="someone-else")
                self.assertEqual(code, 1, output)
                self.assertIn("who is not in licensed-copy-operators.json", output)

    def test_gh_failing_or_ci_is_refused(self):
        for extra, expected in (({"FAKE_GH_FAIL": "1"}, "gh auth login"), ({"CI": "true"}, "refused in CI"),
                                ({"GITHUB_ACTIONS": "true"}, "refused in CI")):
            with self.subTest(env=extra):
                code, output = self.produce(licensed_copy.FLAG, **extra)
                self.assertEqual(code, 1, output)
                self.assertIn(expected, output)
                self.assertFalse(os.path.exists(self.engine))

    def test_recompute_compares_the_operator(self):
        self.produced()
        allowlist = os.path.join(self.tmp, "operators.json")
        with open(allowlist, "w", encoding="utf-8") as handle:
            json.dump({"operators": [OPERATOR, "second-operator"]}, handle)
        with mock.patch.object(licensed_copy, "ALLOWLIST", allowlist):
            code, output = self.factory("provenance", "--engine", self.engine, "--package", self.nupkg,
                                        licensed_copy.FLAG, login="second-operator")
        self.assertEqual(code, 1, output)
        self.assertIn('MISMATCH licensedCopyException.operator: recorded "brandonifco", recomputed "second-operator"',
                      output)

    def test_a_record_without_the_field_is_a_mismatch(self):
        self.produced()
        record = self.record()
        del record["licensedCopyException"]
        with open(os.path.join(self.engine, "provenance.json"), "wb") as handle:
            handle.write(factory.provenance.serialize(record))
        code, output = self.factory("provenance", "--engine", self.engine, "--package", self.nupkg, licensed_copy.FLAG)
        self.assertEqual(code, 1, output)
        self.assertIn("MISMATCH generated: names 0 corpus/ files", output)

    def test_an_engine_holding_corpus_files_is_refused(self):
        self.produced()
        os.makedirs(os.path.join(self.engine, "corpus"))
        shutil.copy(self.corpus, os.path.join(self.engine, "corpus", "synthetic.txt"))
        code, output = self.produce(licensed_copy.FLAG)
        self.assertEqual(code, 1, output)
        self.assertIn("corpus bytes of a licensed corpus are never committed", output)

    def test_a_changed_local_copy_is_refused(self):
        self.produced()
        changed = os.path.join(self.tmp, "changed.txt")
        with open(changed, "wb") as handle:
            handle.write(fixture.corpus_bytes() + b"\nA new errata line.\n")
        code, output = self.factory("provenance", "--engine", self.engine, "--package", self.nupkg,
                                    licensed_copy.FLAG, **{fixture.ENV_VAR: changed})
        self.assertEqual(code, 1, output)
        self.assertIn(f"is not {fixture.SOURCE_ID} at the map's baseline", output)


class TestRulings(FactoryCase):
    """0027 as amended: a ruling on a licensed corpus names its part of the question without its words."""

    def with_overlay(self, overlay):
        os.makedirs(self.engine, exist_ok=True)
        write_record(self.engine)
        with open(os.path.join(self.engine, "corpus-map.overlay.json"), "w", encoding="utf-8") as handle:
            json.dump(overlay, handle, indent=2)

    def test_a_ruling_is_produced_and_verified_and_no_engine_file_carries_the_question(self):
        overlay = licensed_example()
        self.with_overlay(overlay)
        output = self.produced()
        self.assertIn("--- owner's ruling occupied-square/own-pawn on occupied-square, not the corpus", output)
        span = overlay["occupied-square"]["rulings"][0]["span"]
        (ruling,) = self.record()["rulings"]
        self.assertEqual(set(ruling), {"id", "entry", "span", "answer", "ruledBy", "ruledOn", "record", "recordSha256"})
        self.assertEqual(ruling["span"], span)
        with open(os.path.join(self.engine, "src", fixture.ENGINE, "Generated", "Rulings.g.cs"), encoding="utf-8") as handle:
            generated = handle.read()
        self.assertIn(f'"sha256:{span["sha256"]} [{span["start"]}, {span["end"]})",', generated)
        self.assertIn("named without its words", generated)
        for directory, _, names in os.walk(self.engine):
            for name in names:
                path = os.path.join(directory, name)
                with open(path, "rb") as handle:
                    flat = " ".join(handle.read().decode("utf-8", "replace").split())
                for part in (OWN_PART, OPPOSING_PART, "another pawn occupies"):
                    self.assertNotIn(part, flat, path)

        code, output = self.factory("provenance", "--engine", self.engine, "--package", self.nupkg, licensed_copy.FLAG)
        self.assertEqual(code, 0, output)
        with zipfile.ZipFile(self.nupkg) as archive:
            for part in ("corpus-map.json", "corpus-manifest.json"):
                with open(os.path.join(self.tmp, part), "wb") as handle:
                    handle.write(archive.read(f"map/{part}"))
        merge = [sys.executable, os.path.join(self.engine, "scripts", "map-overlay.py"), "merge",
                 "--package-map", os.path.join(self.tmp, "corpus-map.json"),
                 "--overlay", os.path.join(self.engine, "corpus-map.overlay.json"), "--out", os.path.join(self.tmp, "m.json")]
        done = subprocess.run(merge + ["--package-manifest", os.path.join(self.tmp, "corpus-manifest.json")],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        done = subprocess.run(merge, capture_output=True, text=True)
        self.assertEqual(done.returncode, 1, "without the manifest the posture is unknown, and a ruling is refused")
        self.assertIn("verification posture was not given", done.stderr)

    def test_a_quoted_span_or_a_quoting_answer_is_refused_before_anything_is_written(self):
        quoted = licensed_example()
        quoted["occupied-square"]["rulings"][0]["span"] = OWN_PART
        quoting = licensed_example()
        quoting["occupied-square"]["rulings"][0]["answer"] = EVIDENCE
        for overlay, expected in ((quoted, "`span` quotes the question"), (quoting, "`answer` carries 15 or more")):
            with self.subTest(expected):
                shutil.rmtree(self.engine, True)
                self.with_overlay(overlay)
                code, output = self.produce(licensed_copy.FLAG)
                self.assertEqual(code, 1, output)
                self.assertIn(expected, output)
                self.assertFalse(os.path.exists(os.path.join(self.engine, "provenance.json")))


if __name__ == "__main__":
    unittest.main()
