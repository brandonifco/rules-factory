#!/usr/bin/env python3
"""Every file `factory produce` writes is generated, managed or engine-owned (#72, decision 0018).

Asserted: every file in a produced engine, fresh and re-run, matches exactly one row of
tools/factory/ownership.py's table, and every row matches a produced file; the table agrees with
the ADR's table, with what generate.py writes per class and with the gate recipe gate.py vendors;
each managed recipe's bytes are the hash its version records, so a recipe cannot change without a
new version. And the behaviour: a bumped managed recipe updates an unedited managed file on
re-run and records the new version; a hand-edited managed file is refused, naming it, with the
engine byte-identical afterwards, bumped recipe or not; `--adopt` keeps the edit, is recorded in
provenance.json, and is remembered by later runs; `--reset` puts the recipe back; engine-owned
files are never touched by a re-run, even when every managed recipe moves.

Run: python3 -m unittest discover -s tools/tests
"""
import contextlib
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
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")
ADR = os.path.join(REPO, "docs", "decisions", "0018-every-file-the-factory-writes-has-one-owner.md")

_spec = importlib.util.spec_from_file_location("factory_main_ownership", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
generate = factory.generate
gate = factory.gate
provenance = factory.provenance
ownership = generate.ownership

PART107 = os.path.join(REPO, "examples", "faa-part-107")
PART107_XML = os.path.join(PART107, "part107.xml")
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
NAME = "FaaPart107"
MANAGED = ("Directory.Build.props", "NuGet.config", "global.json",
           # The agent rails (decision 0029).
           "AGENTS.md", "CLAUDE.md", "docs/agent-team.md", ".claude/agents/engine-dev.md",
           ".claude/agents/repo-steward.md", ".claude/agents/rules-conformance.md",
           ".claude/hooks/primary-checkout-guard.py", ".claude/settings.json",
           "tools/dispatch-agent.sh", "tools/new-issue.sh", "tools/entry-packet.py",
           "tools/review-packet.py")
ENGINE_OWNED = ("Directory.Packages.props", f"{NAME}.slnx", f"src/{NAME}/{NAME}.csproj",
                f"tests/{NAME}.Tests/{NAME}.Tests.csproj", "corpus-map.overlay.json",
                ".github/agent-policy.json")
LOCKS = (f"src/{NAME}/packages.lock.json", f"tests/{NAME}.Tests/packages.lock.json")


def pack(map_dir, out):
    subprocess.run([sys.executable, PACK, map_dir, "--out", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
    return os.path.join(out, name)


def tree(root):
    files = {}
    for directory, _, names in os.walk(root):
        for name in names:
            path = os.path.join(directory, name)
            with open(path, "rb") as handle:
                files[os.path.relpath(path, root).replace(os.sep, "/")] = (handle.read(), os.stat(path).st_mode)
    return files


@contextlib.contextmanager
def bumped(*paths):
    """The managed recipes for `paths` moved to a new version: new bytes, a new row version, and its hash."""
    real_files, real_table = generate.managed_files, ownership.TABLE
    versions = {row.pattern: row.recipe + 1 for row in real_table if row.pattern in paths}
    table = tuple(row._replace(recipe=versions[row.pattern]) if row.pattern in versions else row for row in real_table)

    def files():
        out = real_files()
        for path in paths:
            out[path] = out[path] + ("\n" if path == "global.json" else f"<!-- recipe {versions[path]} -->\n")
        return out

    history = {path: dict(digests) for path, digests in ownership.RECIPE_SHA256.items()}
    with mock.patch.object(ownership, "TABLE", table), mock.patch.object(generate, "managed_files", files):
        for path, text in files().items():
            if path in versions:
                history[path][versions[path]] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with mock.patch.object(ownership, "RECIPE_SHA256", history):
            yield versions


class OwnershipCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        cls.part107 = pack(PART107, os.path.join(cls.shared, "part107"))
        cls.hoyle = pack(HOYLE, os.path.join(cls.shared, "hoyle"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = os.path.join(self.tmp, "engine")

    def produce(self, *extra, out=None, package=None, corpus=PART107_XML, name=NAME):
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(["produce", "--package", package or self.part107, "--corpus", corpus, "--name", name,
                                 "--out", out or self.out, "--allow-dirty", "--no-verify", *extra])
        return code, buffer.getvalue()

    def produced(self, *extra, **kwargs):
        code, output = self.produce(*extra, **kwargs)
        self.assertEqual(code, 0, output)
        return output

    def refused(self, *extra):
        before = tree(self.out)
        code, output = self.produce(*extra)
        self.assertEqual(code, 1, output)
        self.assertIn("REFUSED", output)
        self.assertEqual(before, tree(self.out), "a refusal leaves the engine byte-identical")
        return output

    def read(self, relative):
        with open(os.path.join(self.out, *relative.split("/")), encoding="utf-8") as handle:
            return handle.read()

    def append(self, relative, text):
        with open(os.path.join(self.out, *relative.split("/")), "a", encoding="utf-8") as handle:
            handle.write(text)

    def record(self):
        return json.loads(self.read("provenance.json"))


class TestTheTable(OwnershipCase):
    def assert_every_file_has_one_class(self, out, name):
        classes = {}
        for relative in tree(out):
            found = ownership.matching(relative, name)
            self.assertEqual(len(found), 1, f"{relative} matches {[r.pattern for r in found]}")
            classes[relative] = found[0].cls
        return classes

    def test_every_file_a_produced_engine_holds_is_in_exactly_one_class(self):
        self.produced()
        classes = self.assert_every_file_has_one_class(self.out, NAME)
        self.produced()
        self.assertEqual(classes, self.assert_every_file_has_one_class(self.out, NAME), "a re-run agrees")
        self.assertEqual(sorted(p for p, c in classes.items() if c == ownership.MANAGED), sorted(MANAGED))
        self.assertEqual(sorted(p for p, c in classes.items() if c == ownership.ENGINE_OWNED), sorted(ENGINE_OWNED))
        # What a verified produce also commits: the lock files its restore writes (verify.py; this
        # test runs no dotnet, so they are written here the way restore would leave them).
        for relative in LOCKS:
            self.append(relative, '{"version": 2}\n')
        self.produced()
        for relative in LOCKS:
            self.assertEqual(self.read(relative), '{"version": 2}\n', "a re-run never touches a lock file")
        classes = self.assert_every_file_has_one_class(self.out, NAME)
        self.assertEqual(sorted(p for p, c in classes.items() if c == ownership.ENGINE_OWNED),
                         sorted(ENGINE_OWNED + LOCKS))
        record = self.record()
        self.assertEqual({e["path"] for e in record["engineOwned"]}, set(ENGINE_OWNED + LOCKS))
        self.assertEqual({b["path"] for b in record["buildInputs"]}, set(ENGINE_OWNED + LOCKS))
        for row in ownership.rows(NAME):
            self.assertTrue(any(ownership.matching(p, NAME) == [row] for p in classes), f"row {row.pattern} matches nothing")

    def test_another_engine_too(self):
        out = os.path.join(self.tmp, "hoyle")
        self.produced(out=out, package=self.hoyle, corpus=os.path.join(HOYLE, "hoyle.txt"), name="HoyleBackgammon")
        self.assert_every_file_has_one_class(out, "HoyleBackgammon")

    def test_provenance_records_every_file_in_its_class_once(self):
        self.produced()
        record = self.record()
        generated = {g["path"] for g in record["generated"]}
        managed = {m["path"] for m in record["managed"]}
        owned = {e["path"] for e in record["engineOwned"]}
        inputs = {b["path"] for b in record["buildInputs"]}
        self.assertEqual(managed, set(MANAGED))
        self.assertEqual(owned, set(ENGINE_OWNED))
        self.assertEqual(generated | managed | owned | {"provenance.json"}, set(tree(self.out)))
        self.assertFalse(generated & managed or generated & owned or managed & owned)
        self.assertEqual(inputs, owned, "engine-owned files are hashed in buildInputs, managed ones are not")
        for item in record["managed"]:
            self.assertEqual(item["recipeVersion"], ownership.classify(item["path"], NAME).recipe)

    def test_an_unclassified_output_is_refused(self):
        real = gate.files

        def with_stray(name):
            return {**real(name), "scripts/stray.txt": (b"x", False)}

        with mock.patch.object(gate, "files", with_stray):
            code, output = self.produce()
        self.assertEqual(code, 1, output)
        self.assertIn("scripts/stray.txt, which the ownership table", output)
        self.assertFalse(os.path.exists(self.out))

    def test_the_adr_table_is_this_table(self):
        with open(ADR, encoding="utf-8") as handle:
            text = handle.read()
        documented = re.findall(r"^\| `([^`]+)` \| (generated|managed|engine-owned) \| (\d+|) \|", text, re.M)
        self.assertEqual([(p, c, str(v) if v else "") for p, c, v, _ in ownership.TABLE],
                         [(p, c, v) for p, c, v in documented])

    def test_generate_and_the_gate_write_each_class_from_the_table(self):
        model = types.SimpleNamespace(name=NAME, header="", package_id="P", version="1")
        self.assertEqual(set(generate.managed_files()), {r.pattern for r in ownership.rows(NAME) if r.cls == ownership.MANAGED})
        self.assertEqual(set(generate.engine_owned(model)) | set(LOCKS),  # the lock files are restore's (verify.py)
                         {r.pattern for r in ownership.rows(NAME) if r.cls == ownership.ENGINE_OWNED})
        # The gate regenerates exactly the generated `*.g.*` files, and vendors what it needs as generated files.
        for relative in list(gate.FILES) + [f"src/{NAME}/Generated/X.g.cs", f"tests/{NAME}.Tests/Generated/X.g.cs",
                                            generate.PACKAGES_PROPS]:
            self.assertEqual(ownership.classify(relative, NAME).cls, ownership.GENERATED, relative)

    def test_each_managed_recipe_is_the_bytes_its_version_records(self):
        for path, text in generate.managed_files().items():
            row = ownership.classify(path, NAME)
            self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), ownership.RECIPE_SHA256[path][row.recipe],
                             f"{path} changed without a new recipe version and hash in tools/factory/ownership.py")
            self.assertEqual(max(ownership.RECIPE_SHA256[path]), row.recipe)


class TestManaged(OwnershipCase):
    def test_a_bumped_recipe_updates_an_unedited_managed_file(self):
        self.produced()
        with bumped("Directory.Build.props", "global.json") as versions:
            output = self.produced()
            self.assertIn(f"updated managed Directory.Build.props from recipe 2 to {versions['Directory.Build.props']}", output)
            self.assertTrue(self.read("Directory.Build.props").endswith(f"<!-- recipe {versions['Directory.Build.props']} -->\n"))
            self.assertTrue(self.read("global.json").endswith("}\n\n"))
            recorded = {m["path"]: m["recipeVersion"] for m in self.record()["managed"]}
            self.assertEqual(recorded["Directory.Build.props"], versions["Directory.Build.props"])
            self.assertEqual(recorded["global.json"], versions["global.json"])
            before = tree(self.out)
            self.produced()
            self.assertEqual(before, tree(self.out), "a second run on the bumped recipe changes nothing")

    def test_an_engine_scaffolded_before_ownership_is_migrated_without_a_flag(self):
        """Version 1 is the write-once scaffold's bytes from before #72; such an engine is unedited."""
        self.produced()
        current = generate.managed_files()
        legacy = {
            "NuGet.config": re.sub(r"<!-- Restore.*?-->", "<!-- Restore talks to nuget.org and nothing else; "
                                   "packages.lock.json pins every content hash. -->", current["NuGet.config"], flags=re.S),
            "Directory.Build.props": re.sub(r"<!-- Zero-warning.*?-->", "<!-- Produced by rules-factory tools/factory. "
                                            "Zero-warning, deterministic builds. -->", current["Directory.Build.props"],
                                            flags=re.S),
        }
        for path, text in legacy.items():
            self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), ownership.RECIPE_SHA256[path][1], path)
            with open(os.path.join(self.out, path), "w", encoding="utf-8") as handle:
                handle.write(text)
        output = self.produced()
        for path in legacy:
            self.assertIn(f"updated managed {path} from recipe 1 to 2", output)
            self.assertEqual(self.read(path), current[path])

    def test_a_hand_edited_managed_file_is_refused(self):
        self.produced()
        self.append("Directory.Build.props", "<!-- mine -->\n")
        output = self.refused()
        self.assertIn("Directory.Build.props is a managed file edited by hand", output)
        self.assertIn("--adopt", output)
        with bumped("Directory.Build.props"):
            output = self.refused()
        self.assertIn("Directory.Build.props is a managed file edited by hand", output)

    def test_adopt_keeps_the_edit_and_is_remembered(self):
        self.produced()
        self.append("NuGet.config", "<!-- mine -->\n")
        self.produced("--adopt", "NuGet.config")
        self.assertTrue(self.read("NuGet.config").endswith("<!-- mine -->\n"))
        record = self.record()
        self.assertIn({"path": "NuGet.config", "adopted": True}, record["engineOwned"])
        self.assertNotIn("NuGet.config", [m["path"] for m in record["managed"]])
        self.assertIn("NuGet.config", [b["path"] for b in record["buildInputs"]])
        with bumped("NuGet.config"):
            self.produced()
        self.assertTrue(self.read("NuGet.config").endswith("<!-- mine -->\n"), "an adopted file is never touched")
        self.assertIn({"path": "NuGet.config", "adopted": True}, self.record()["engineOwned"])

    def test_reset_puts_the_recipe_back(self):
        self.produced()
        self.append("global.json", "\n")
        self.produced("--adopt", "global.json")
        self.produced("--reset", "global.json")
        self.assertEqual(self.read("global.json"), generate.managed_files()["global.json"])
        self.assertIn("global.json", [m["path"] for m in self.record()["managed"]])
        self.assertNotIn("global.json", [e["path"] for e in self.record()["engineOwned"]])

    def test_a_flag_must_name_a_managed_file(self):
        self.produced()
        self.assertIn("--adopt and --reset name managed files only", self.refused("--adopt", "Directory.Packages.props"))
        self.assertIn("given to both --adopt and --reset", self.refused("--adopt", "global.json", "--reset", "global.json"))


class TestEngineOwned(OwnershipCase):
    def test_never_touched_again_whatever_the_recipes_do(self):
        self.produced()
        for relative in ENGINE_OWNED:
            if relative != "corpus-map.overlay.json":
                self.append(relative, "<!-- the engine's -->\n")
        with bumped(*MANAGED):
            self.produced()
        for relative in ENGINE_OWNED:
            if relative != "corpus-map.overlay.json":
                self.assertTrue(self.read(relative).endswith("<!-- the engine's -->\n"), relative)
        self.assertEqual(self.read("corpus-map.overlay.json"), "{}\n")


if __name__ == "__main__":
    unittest.main()
