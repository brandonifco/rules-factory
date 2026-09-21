#!/usr/bin/env python3
"""`factory produce` records provenance (#3, M4), and `factory provenance` recomputes it.

The factory under test is a copy of tools/factory committed to a scratch git repository, run
as a child process: provenance names the factory's commit and refuses a dirty tree, and this
checkout's own state (dirty while being edited, a `.pytest_cache` in CI) is not something a
test can assume. Tests that change the factory (a recipe, a tag, an untracked file) get their
own copy.

Asserted: two runs give byte-identical provenance, and so does a re-run in place; the fields
say what the inputs are; recompute passes on fresh output; changing a generated file, the
corpus copy, a recipe, or the package makes recompute fail naming the field; after a re-run with
a newer map, recompute passes, and a pin hand-edited back to the old version fails it (#66); a dirty factory
is refused, and `--allow-dirty` records it; a factory outside git is refused; a factory whose
recipe files are not the bytes of the commit it would name -- a committed file or directory
symlink under `tools/factory`, a symlinked `tools/check-map.py`, any ignored file under
`tools/factory`, bytecode there included -- is refused, naming the path (#232, #373), and the
entry point writes no bytecode of its own, so a second consecutive produce still runs.

Build inputs (#69): `buildInputs` lists the engine-owned build files by rule, never a generated
or managed file (#72: those are hashed once, in `generated` and `managed`); a fresh run and a
re-run agree on it; editing the overlay or a csproj, or adding or removing a build input, is a
`buildInputs[<path>]` mismatch and not a `generated` one; editing global.json is a
`managed[global.json]` mismatch until `--adopt global.json` records it; lock files are no claim
until a record lists one, and then every lock file is held.

The engine's gate carries a narrower check of the same record, without the factory
(`scripts/engine-gate.py provenance`, #192). One test here holds the two to the same direction: a
tree the gate fails is one recompute also fails, naming at least one of the same paths.

The embedded copy is only exercised by `dotnet test` on a produced engine, which needs the
SDK the kernel pins and network access to nuget.org; that test skips, saying why, without them.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import hashlib
import importlib.util
import json
import marshal
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")
PART107 = os.path.join(REPO, "examples", "faa-part-107")
PART107_XML = os.path.join(PART107, "part107.xml")
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
NAME = "FaaPart107"
MAP_ENTRIES = f"src/{NAME}/Generated/MapEntries.g.cs"
PACKAGES_PROPS = "RulesFactory.Packages.g.props"
MAP_ID = "RulesFactory.Maps.FaaPart107"
GIT_ENV = {"GIT_AUTHOR_NAME": "factory-test", "GIT_AUTHOR_EMAIL": "factory-test@example.invalid",
           "GIT_COMMITTER_NAME": "factory-test", "GIT_COMMITTER_EMAIL": "factory-test@example.invalid",
           "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

sys.path.insert(0, FACTORY)
import provenance  # noqa: E402
import scaffold  # noqa: E402  (the managed recipes, to name them once)

# What a `--no-verify` produce exits: NOT VERIFIED, never 0. Read from the CLI it names, so the
# two cannot drift (the factory itself is run as a child process here).
_main_spec = importlib.util.spec_from_file_location("factory_main_provenance", os.path.join(FACTORY, "__main__.py"))
_main = importlib.util.module_from_spec(_main_spec)
_main_spec.loader.exec_module(_main)
NOT_VERIFIED = _main.NOT_VERIFIED


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


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, env={**os.environ, **GIT_ENV}).stdout.strip()


def factory_repo(root):
    """tools/factory and the tools/check-map.py intake runs (0016), copied into a fresh git repository."""
    shutil.copytree(FACTORY, os.path.join(root, "tools", "factory"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(os.path.join(os.path.dirname(FACTORY), "check-map.py"), os.path.join(root, "tools", "check-map.py"))
    with open(os.path.join(root, ".gitignore"), "w", encoding="utf-8") as handle:
        handle.write("__pycache__/\n*.pyc\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "factory")
    return root


def pack(map_dir, out):
    subprocess.run([sys.executable, PACK, map_dir, "--out", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
    return os.path.join(out, name)


def pack_version(map_dir, version, root):
    """`map_dir` packed as `version`: a copy under `root` whose map-package.json says so."""
    copy = os.path.join(root, f"v{version}", os.path.basename(map_dir))
    shutil.copytree(map_dir, copy)
    settings_path = os.path.join(copy, "map-package.json")
    with open(settings_path, encoding="utf-8") as handle:
        settings = json.load(handle)
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(dict(settings, version=version), handle)
    return pack(copy, os.path.join(root, f"v{version}", "out"))


class ProvenanceCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        cls.part107 = pack(PART107, os.path.join(cls.shared, "part107"))
        cls.repo = factory_repo(os.path.join(cls.shared, "factory"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def own_repo(self):
        return factory_repo(os.path.join(self.tmp, "factory"))

    def factory(self, *args, repo=None, env=None):
        done = subprocess.run([sys.executable, os.path.join(repo or self.repo, "tools", "factory"), *args],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              env={**(os.environ if env is None else env), **GIT_ENV})
        return done.returncode, done.stdout

    def produce(self, out=None, repo=None, package=None, corpus=PART107_XML, name=NAME, extra=(), env=None):
        out = out or os.path.join(self.tmp, "engine")
        code, output = self.factory("produce", "--package", package or self.part107, "--corpus", corpus,
                                    "--name", name, "--out", out, *extra,
                                    "--no-verify",  # building is TestEmbeddedCopyBuilds's (and verify's) job
                                    repo=repo, env=env)
        return code, output, out

    def produced(self, **kwargs):
        code, output, out = self.produce(**kwargs)
        # `--no-verify` ends NOT VERIFIED (3), never 0: the engine was written but never built
        # or tested (tools/factory/__main__.py).
        self.assertEqual(code, NOT_VERIFIED, output)
        return out

    def recompute(self, out, repo=None, package=None):
        return self.factory("provenance", "--engine", out, "--package", package or self.part107, repo=repo)

    def assert_recompute_names(self, out, *fields, repo=None, package=None):
        code, output = self.recompute(out, repo=repo, package=package)
        self.assertEqual(code, 1, output)
        for field in fields:
            self.assertIn(f"MISMATCH {field}", output)
        return output

    def record(self, out):
        with open(os.path.join(out, "provenance.json"), encoding="utf-8") as handle:
            return json.load(handle)


class TestRecord(ProvenanceCase):
    def test_two_runs_are_byte_identical(self):
        first = self.produced(out=os.path.join(self.tmp, "a"))
        second = self.produced(out=os.path.join(self.tmp, "b"))
        with open(os.path.join(first, "provenance.json"), "rb") as a, open(os.path.join(second, "provenance.json"), "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_a_rerun_in_place_changes_nothing(self):
        out = self.produced()
        before = pathlib.Path(out, "provenance.json").read_bytes()
        self.produced(out=out)
        self.assertEqual(before, pathlib.Path(out, "provenance.json").read_bytes())

    def test_the_fields(self):
        out = self.produced()
        record = self.record(out)
        commit = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(record["factory"], {"version": f"0.0.0-dev+{commit[:12]}", "commit": commit, "dirty": False})
        self.assertEqual(record["engine"], {"name": NAME})
        self.assertEqual(record["map"]["packageId"], "RulesFactory.Maps.FaaPart107")
        self.assertEqual(record["map"]["version"], "4.0.0")
        self.assertEqual(record["map"]["nupkgSha256"], sha256_file(self.part107))
        with zipfile.ZipFile(self.part107) as archive:
            expected = [{"role": role, "path": path, "sha256": hashlib.sha256(archive.read(path)).hexdigest()}
                        for role, path in (("map", "map/corpus-map.json"), ("manifest", "map/corpus-manifest.json"),
                                           ("checker", "tools/check-map.py"),
                                           ("verification", "map/verification.json"))]
        self.assertEqual(record["map"]["files"], expected)
        # One entry per corpus the map cites, sorted by sourceId, the principal one flagged (0039).
        self.assertEqual(record["corpora"], [{"sourceId": "cfr-14-107",
                                              "contentHash": sha256_file(PART107_XML),
                                              "hashDerivation": "ecfr-versioner-xml", "asOf": "2026-01-01",
                                              "path": "corpus/part107.xml", "principal": True,
                                              "recomputed": True}])
        self.assertNotIn("corpus", record)
        self.assertEqual(record["kernel"], {"packageId": "RulesKernel", "version": "0.3.0"})
        self.assertEqual(record["packs"], [])
        self.assertEqual(record["randomness"], "none")

        files = record["recipes"]["files"]
        paths = [f["path"] for f in files]
        self.assertEqual(paths, sorted(paths, key=lambda p: p.encode("utf-8")))
        self.assertIn("tools/factory/generate.py", paths)
        self.assertIn("tools/factory/provenance.py", paths)
        self.assertIn("tools/check-map.py", paths)
        for item in files:
            self.assertEqual(item["sha256"], sha256_file(os.path.join(self.repo, *item["path"].split("/"))))
        lines = "".join(f"{f['sha256']}  {f['path']}\n" for f in files)
        self.assertEqual(record["recipes"]["digest"], hashlib.sha256(lines.encode("utf-8")).hexdigest())

        generated = {g["path"]: g["sha256"] for g in record["generated"]}
        self.assertEqual(list(generated), sorted(generated))
        for path in (MAP_ENTRIES, "corpus/part107.xml", "scripts/validate.sh", f"src/{NAME}/Generated/Provenance.g.cs",
                     f"tests/{NAME}.Tests/Generated/ProvenanceTests.g.cs", PACKAGES_PROPS):
            self.assertIn(path, generated)
        for path in ("provenance.json", "global.json", f"src/{NAME}/{NAME}.csproj"):
            self.assertNotIn(path, generated, "provenance.json, managed and engine-owned files are not generated")
        self.assertFalse([p for p in generated if p.startswith("backlog/")],
                         "the backlog is not produced, so it is not recorded as generated (#243)")
        for path, digest in generated.items():
            self.assertEqual(digest, sha256_file(os.path.join(out, *path.split("/"))), path)

    def test_build_inputs(self):
        out = self.produced()
        record = self.record(out)
        inputs = {b["path"]: b["sha256"] for b in record["buildInputs"]}
        self.assertEqual(list(inputs), sorted(inputs, key=lambda p: p.encode("utf-8")))
        self.assertEqual(set(inputs), {"Directory.Packages.props", f"{NAME}.slnx",
                                       f"src/{NAME}/{NAME}.csproj", f"tests/{NAME}.Tests/{NAME}.Tests.csproj",
                                       # Configuration the rails read rather than MSBuild (0029).
                                       ".github/agent-policy.json"})
        for path, digest in inputs.items():
            self.assertEqual(digest, sha256_file(os.path.join(out, *path.split("/"))), path)
        generated = {g["path"] for g in record["generated"]}
        self.assertIn(PACKAGES_PROPS, generated)
        self.assertEqual(set(inputs) & generated, set(), "a generated file is not listed again as a build input")
        managed = {m["path"]: m for m in record["managed"]}
        self.assertEqual(set(managed), set(scaffold.managed_files()))
        self.assertIn("AGENTS.md", managed)
        for path, item in managed.items():
            self.assertEqual(item["sha256"], sha256_file(os.path.join(out, *path.split("/"))), path)
            self.assertIsInstance(item["recipeVersion"], int)
        self.assertEqual(set(inputs) & set(managed), set(), "a managed file is hashed once, in managed")
        self.assertEqual({e["path"] for e in record["engineOwned"]}, set(inputs),
                         "every engine-owned file is a build input, and hashed there")
        self.assertFalse(any(e["adopted"] for e in record["engineOwned"]))
        self.assertNotIn("provenance.json", inputs)

    def test_the_rule_is_by_name_and_skips_build_output(self):
        for path in ("global.json", "sub/nuget.CONFIG", "Directory.Build.targets", "src/A/A.csproj", "A.sln",
                     "src/A/packages.lock.json", ".editorconfig", "x/My.targets",
                     # One file per entry, covered by path because its name is the entry's (#247).
                     "overlay/speed-limit.json", ".github/agent-policy.json"):
            self.assertTrue(provenance.is_build_input(path), path)
        for path in ("src/A/obj/A.csproj.nuget.g.props", "bin/x.props", ".git/x.props", "src/A/Rules/Speed.cs",
                     "scripts/validate.sh", "backlog/README.md", "corpus/part107.xml",
                     "corpus-map.overlay.json", "overlay/notes.md", "src/A/overlay/x.json"):
            self.assertFalse(provenance.is_build_input(path), path)

    def test_a_fresh_run_and_a_rerun_agree_on_build_inputs(self):
        first = self.produced(out=os.path.join(self.tmp, "a"))
        second = self.produced(out=os.path.join(self.tmp, "b"))
        self.assertEqual(self.record(first)["buildInputs"], self.record(second)["buildInputs"])
        self.produced(out=first)
        self.assertEqual(self.record(first)["buildInputs"], self.record(second)["buildInputs"])

    def test_the_version_comes_from_a_factory_tag_on_head(self):
        repo = self.own_repo()
        git(repo, "tag", "factory/v1.2.3")
        git(repo, "tag", "factory/v1.10.0")
        git(repo, "tag", "map/other/v9.0.0")
        out = self.produced(repo=repo)
        self.assertEqual(self.record(out)["factory"]["version"], "1.10.0")

    def test_the_engine_embeds_it(self):
        out = self.produced()
        csproj = pathlib.Path(out, "src", NAME, f"{NAME}.csproj").read_text(encoding="utf-8")
        self.assertIn(f'<EmbeddedResource Include="../../provenance.json" LogicalName="{NAME}.provenance.json"', csproj)
        tests = pathlib.Path(out, "tests", f"{NAME}.Tests", "Generated", "ProvenanceTests.g.cs").read_text(encoding="utf-8")
        self.assertIn("Assert.Equal(File.ReadAllBytes(EngineRootFile(\"provenance.json\")), EngineProvenance.ReadBytes())", tests)

    def test_the_recorder_sees_any_write_under_the_engine_and_nothing_else(self):
        root = os.path.join(self.tmp, "engine")
        os.makedirs(os.path.join(root, "backlog"))
        outside = os.path.join(self.tmp, "outside.txt")
        pathlib.Path(root, "kept.txt").write_text("hand-written\n", encoding="utf-8")
        with provenance.Recorder(root) as recorder:
            with open(os.path.join(root, "a.g.cs"), "w", encoding="utf-8") as handle:
                handle.write("x")
            pathlib.Path(root, "backlog", "b.md").write_text("y", encoding="utf-8")
            with open(os.path.join(root, "tmp"), "wb") as handle:
                handle.write(b"z")
            os.replace(os.path.join(root, "tmp"), os.path.join(root, "gate.sh"))
            with open(os.path.join(root, "kept.txt"), encoding="utf-8") as handle:
                handle.read()
            with open(outside, "w", encoding="utf-8") as handle:
                handle.write("elsewhere")
        self.assertEqual(recorder.paths - {"tmp"}, {"a.g.cs", "backlog/b.md", "gate.sh"})
        with open(os.path.join(root, "after.txt"), "w", encoding="utf-8") as handle:
            handle.write("not recorded")
        self.assertNotIn("after.txt", recorder.paths)


class TestVerificationIsRecorded(ProvenanceCase):
    """#222: the record says whether the produce that wrote it built and tested the engine.

    `produce --no-verify` printed it and exited 3, and `provenance.json` said nothing -- so a
    reader of a committed engine, or of the copy embedded in the assembly, could not tell a
    verified produce from an unverified one. The indirect signal (lock files in `buildInputs`)
    is inference, and it breaks the moment anyone runs `dotnet restore` by hand.
    """

    def test_an_unverified_produce_says_so_and_says_why(self):
        record = self.record(self.produced())
        self.assertEqual(record["verification"]["verified"], False)
        self.assertEqual(record["verification"]["ran"], [])
        # The message, not only the boolean: a reader with no console output needs the reason
        # (#283 -- another field being false would satisfy a verdict-only assertion).
        self.assertIn("--no-verify", record["verification"]["why"])
        self.assertIn("never built or tested", record["verification"]["why"])

    def test_a_verified_produce_names_every_step_it_ran(self):
        """No SDK is needed to assert the shape the verified path writes."""
        self.assertEqual(provenance.verification(True),
                         {"verified": True, "ran": list(provenance.VERIFICATION_STEPS)})
        self.assertIn("gate", provenance.VERIFICATION_STEPS,
                      "a reader of `verified: true` is owed what was proven, not a bare boolean")

    def test_the_two_differ_in_that_field(self):
        self.assertNotEqual(provenance.verification(True), provenance.verification(False))
        self.assertIs(provenance.verification(False)["verified"], False)

    def test_the_format_number_moved_with_the_member(self):
        self.assertGreaterEqual(provenance.FORMAT, 6,
                                "a record gained a member, so a reader can tell which records have it")
        self.assertEqual(self.record(self.produced())["provenanceFormat"], provenance.FORMAT)


class TestRecomputeDoesNotRewriteVerification(ProvenanceCase):
    """`factory provenance` reports; it must never upgrade an unverified record to a verified one."""

    def test_a_record_that_says_nothing_about_verification_is_named(self):
        out = self.produced()
        path = os.path.join(out, "provenance.json")
        record = self.record(out)
        del record["verification"]
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
        code, output = self.recompute(out)
        self.assertEqual(code, 1, output)
        self.assertIn("does not say whether the produce that wrote it", output)

    def test_a_verified_claim_is_not_silently_replaced_by_the_re_produce(self):
        """The re-produce runs unverified. If `verification` were in the diff, either every
        verified engine would look like a mismatch, or -- the tempting fix -- the recomputed
        value would win and quietly rewrite `true` to `false` and back. Neither happens."""
        out = self.produced()
        path = os.path.join(out, "provenance.json")
        record = self.record(out)
        record["verification"] = {"verified": True, "ran": list(provenance.VERIFICATION_STEPS)}
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
        code, output = self.recompute(out)
        self.assertNotIn("MISMATCH verification", output)
        # And the file on disk still says what it said: recompute writes nothing.
        self.assertEqual(self.record(out)["verification"]["verified"], True)


class TestRecompute(ProvenanceCase):
    def test_passes_on_fresh_output(self):
        out = self.produced()
        code, output = self.recompute(out)
        self.assertEqual(code, 0, output)
        self.assertIn("every field matches", output)

    def test_passes_after_hand_written_code_and_a_build(self):
        out = self.produced()
        pathlib.Path(out, "src", NAME, "Rules").mkdir(parents=True)
        pathlib.Path(out, "src", NAME, "Rules", "Speed.cs").write_text("// mine\n", encoding="utf-8")
        pathlib.Path(out, "src", NAME, "bin").mkdir()
        pathlib.Path(out, "src", NAME, "bin", "junk.dll").write_bytes(b"\0")
        pathlib.Path(out, "src", NAME, "obj").mkdir()
        pathlib.Path(out, "src", NAME, "obj", f"{NAME}.csproj.nuget.g.props").write_text("<Project />\n", encoding="utf-8")
        code, output = self.recompute(out)
        self.assertEqual(code, 0, output)

    def test_a_changed_generated_file(self):
        out = self.produced()
        with open(os.path.join(out, *MAP_ENTRIES.split("/")), "a", encoding="utf-8") as handle:
            handle.write("// hand edit\n")
        self.assert_recompute_names(out, f"generated[{MAP_ENTRIES}].sha256")

    def test_a_deleted_generated_file(self):
        out = self.produced()
        os.remove(os.path.join(out, *MAP_ENTRIES.split("/")))
        self.assert_recompute_names(out, f"generated[{MAP_ENTRIES}]")

    def test_a_changed_corpus(self):
        out = self.produced()
        path = os.path.join(out, "corpus", "part107.xml")
        data = bytearray(pathlib.Path(path).read_bytes())
        data[len(data) // 2] ^= 1
        pathlib.Path(path).write_bytes(bytes(data))
        self.assert_recompute_names(out, "corpora[cfr-14-107].contentHash",
                                    "generated[corpus/part107.xml].sha256")

    def test_a_changed_recipe(self):
        repo = self.own_repo()
        out = self.produced(repo=repo)
        with open(os.path.join(repo, "tools", "factory", "generate.py"), "a", encoding="utf-8") as handle:
            handle.write("\n# a changed recipe\n")
        git(repo, "commit", "-q", "-am", "change a recipe")
        self.assert_recompute_names(out, "recipes.files[tools/factory/generate.py].sha256", "recipes.digest",
                                    "factory.commit", repo=repo)

    def test_a_changed_checker(self):
        repo = self.own_repo()
        out = self.produced(repo=repo)
        before = self.record(out)["recipes"]
        with open(os.path.join(repo, "tools", "check-map.py"), "a", encoding="utf-8") as handle:
            handle.write("\n# a changed checker\n")
        git(repo, "commit", "-q", "-am", "change the checker")
        self.assert_recompute_names(out, "recipes.files[tools/check-map.py].sha256", "recipes.digest", repo=repo)
        after = self.record(self.produced(out=os.path.join(self.tmp, "again"), repo=repo))["recipes"]
        self.assertNotEqual(before["digest"], after["digest"])

    def test_a_changed_package(self):
        out = self.produced()
        changed = os.path.join(self.tmp, "changed.nupkg")
        with zipfile.ZipFile(self.part107) as src, zipfile.ZipFile(changed, "w", zipfile.ZIP_STORED) as dst:
            for info in src.infolist():
                dst.writestr(info, src.read(info.filename))
            dst.writestr("extra.txt", "one more byte")
        self.assert_recompute_names(out, "map.nupkgSha256", package=changed)

    def test_a_changed_overlay_without_a_rerun(self):
        out = self.produced()
        implemented = {"status": "implemented", "implementedIn": {"ruleset": "faa-part-107", "version": 1},
                       "tests": [{"test": "T.t", "mutation": "m"}]}
        write_overlay(out, {"reasonable-protection": implemented})
        self.assert_recompute_names(out, f"generated[src/{NAME}/Generated/Registry.g.cs].sha256",
                                    "buildInputs[overlay/reasonable-protection.json]")
        self.produced(out=out)
        code, output = self.recompute(out)
        self.assertEqual(code, 0, output)

    def test_a_pin_edited_back_after_a_map_upgrade(self):
        root = os.path.join(self.tmp, "versions")
        v1, v2 = pack_version(PART107, "5.0.0", root), pack_version(PART107, "7.0.0", root)
        out = self.produced(package=v1)
        self.produced(out=out, package=v2)
        self.assertEqual(self.record(out)["map"]["version"], "7.0.0")
        code, output = self.recompute(out, package=v2)
        self.assertEqual(code, 0, output)

        props = pathlib.Path(out, PACKAGES_PROPS)
        text = props.read_text(encoding="utf-8")
        pin = f'<PackageVersion Include="{MAP_ID}" Version="[7.0.0]" />'
        self.assertIn(pin, text)
        props.write_text(text.replace(pin, pin.replace("7.0.0", "5.0.0")), encoding="utf-8")
        self.assert_recompute_names(out, f"generated[{PACKAGES_PROPS}].sha256", package=v2)

    def test_a_pin_edited_back_after_a_map_downgrade(self):
        root = os.path.join(self.tmp, "versions")
        v1, v2 = pack_version(PART107, "5.0.0", root), pack_version(PART107, "7.0.0", root)
        out = self.produced(package=v2)
        self.produced(out=out, package=v1)
        code, output = self.recompute(out, package=v1)
        self.assertEqual(code, 0, output)
        props = pathlib.Path(out, PACKAGES_PROPS)
        props.write_text(props.read_text(encoding="utf-8").replace("[5.0.0]", "[7.0.0]"), encoding="utf-8")
        self.assert_recompute_names(out, f"generated[{PACKAGES_PROPS}].sha256", package=v1)

    def test_a_changed_global_json(self):
        out = self.produced()
        path = pathlib.Path(out, "global.json")
        path.write_text(path.read_text(encoding="utf-8").replace('"disable"', '"latestFeature"'), encoding="utf-8")
        output = self.assert_recompute_names(out, "managed[global.json].sha256")
        self.assertNotIn("MISMATCH generated[", output, "a managed file is not a generated mismatch")
        self.assertIn("edited by hand", output, "re-producing refuses the hand-edited managed file")
        self.produced(out=out, extra=("--adopt", "global.json"))
        self.assertIn({"path": "global.json", "adopted": True}, self.record(out)["engineOwned"])
        self.assertIn("global.json", [b["path"] for b in self.record(out)["buildInputs"]])
        code, output = self.recompute(out)
        self.assertEqual(code, 0, "re-producing with --adopt records the engine's edit: " + output)

    def test_a_changed_csproj(self):
        out = self.produced()
        with open(os.path.join(out, "tests", f"{NAME}.Tests", f"{NAME}.Tests.csproj"), "a", encoding="utf-8") as handle:
            handle.write("<!-- an engine's edit -->\n")
        output = self.assert_recompute_names(out, f"buildInputs[tests/{NAME}.Tests/{NAME}.Tests.csproj].sha256")
        self.assertNotIn("MISMATCH generated[", output)

    def test_an_added_and_a_removed_build_input(self):
        out = self.produced()
        pathlib.Path(out, "Directory.Build.targets").write_text("<Project />\n", encoding="utf-8")
        os.remove(os.path.join(out, f"{NAME}.slnx"))
        os.remove(os.path.join(out, "NuGet.config"))
        self.assert_recompute_names(out, "buildInputs[Directory.Build.targets]: not recorded",
                                    f"buildInputs[{NAME}.slnx]: recorded, recomputed nothing",
                                    "managed[NuGet.config]: recorded, missing on disk")

    def test_an_edit_that_makes_produce_refuse_is_still_named(self):
        out = self.produced()
        path = pathlib.Path(out, "Directory.Packages.props")
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("</ItemGroup>", '  <PackageVersion Include="RulesKernel" Version="9.9.9" />\n  </ItemGroup>', 1),
                        encoding="utf-8")
        output = self.assert_recompute_names(out, "buildInputs[Directory.Packages.props].sha256")
        self.assertIn("produce refused", output)

    def test_lock_files(self):
        """None recorded: no claim, so a restore does not break recompute. Once recorded, all are held."""
        out = self.produced()
        src_lock = pathlib.Path(out, "src", NAME, "packages.lock.json")
        tests_lock = pathlib.Path(out, "tests", f"{NAME}.Tests", "packages.lock.json")
        src_lock.write_text('{"version": 2}\n', encoding="utf-8")
        tests_lock.write_text('{"version": 2}\n', encoding="utf-8")
        code, output = self.recompute(out)
        self.assertEqual(code, 0, output)

        self.produced(out=out)
        recorded = [b["path"] for b in self.record(out)["buildInputs"]]
        self.assertIn(f"src/{NAME}/packages.lock.json", recorded)
        self.assertIn(f"tests/{NAME}.Tests/packages.lock.json", recorded)
        code, output = self.recompute(out)
        self.assertEqual(code, 0, output)

        src_lock.write_text('{"version": 2, "dependencies": {}}\n', encoding="utf-8")
        tests_lock.unlink()
        pathlib.Path(out, "extra").mkdir()
        pathlib.Path(out, "extra", "packages.lock.json").write_text("{}\n", encoding="utf-8")
        self.assert_recompute_names(out, f"buildInputs[src/{NAME}/packages.lock.json].sha256",
                                    f"buildInputs[tests/{NAME}.Tests/packages.lock.json]: recorded, recomputed nothing",
                                    "buildInputs[extra/packages.lock.json]: not recorded")

    def test_the_recorded_randomness_follows_the_manifest(self):
        """0019: provenance records the corpus's declaration, and recompute compares it."""
        self.assertEqual(self.record(self.produced())["randomness"], "none")
        hoyle = pack(HOYLE, os.path.join(self.tmp, "hoyle"))
        out = self.produced(package=hoyle, corpus=os.path.join(HOYLE, "hoyle.txt"), name="HoyleBackgammon",
                            out=os.path.join(self.tmp, "hoyle-engine"))
        self.assertEqual(self.record(out)["randomness"], "seeded")
        code, output = self.recompute(out, package=hoyle)
        self.assertEqual(code, 0, output)
        # The same Part 107 map, its manifest declaring `seeded`: re-producing records the new value.
        engine = self.produced()
        copy = os.path.join(self.tmp, "seeded", "faa-part-107")
        shutil.copytree(PART107, copy)
        manifest_path = os.path.join(copy, "corpus-manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["corpora"][0]["randomness"] = "seeded"
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
        seeded = pack(copy, os.path.join(self.tmp, "seeded", "out"))
        output = self.assert_recompute_names(engine, "randomness: recorded \"none\", recomputed \"seeded\"",
                                             f"generated[{PACKAGES_PROPS}]", package=seeded)
        self.assertIn("map.files[map/corpus-manifest.json].sha256", output)

    def test_the_gate_s_own_check_and_recompute_agree_in_direction(self):
        """#192: `scripts/engine-gate.py provenance` compares without the factory; this recomputes
        with it. They are not equal -- recompute re-produces, so it legitimately says more -- but a
        tree the gate fails must be one recompute also fails, naming at least one of the same paths.
        Were that not so, the cheap check in every engine's gate would be reporting something the
        factory's own recomputation does not believe.
        """
        out = self.produced()
        implemented = {"status": "implemented", "implementedIn": {"ruleset": "faa-part-107", "version": 1},
                       "tests": [{"test": "T.t", "mutation": "m"}]}
        write_overlay(out, {"reasonable-protection": implemented})
        gate = subprocess.run([sys.executable, os.path.join(out, "scripts", "engine-gate.py"), "provenance"],
                              cwd=out, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(gate.returncode, 1, gate.stdout)
        named = set(re.findall(r"(?:generated|managed|buildInputs)\[([^\]]+)\]", gate.stdout))
        self.assertTrue(named, gate.stdout)

        code, output = self.recompute(out)
        self.assertEqual(code, 1, output)
        mismatches = [line for line in output.splitlines() if "MISMATCH" in line]
        self.assertTrue(mismatches, output)
        self.assertTrue(named & set(re.findall(r"\[([^\]]+)\]", "\n".join(mismatches))),
                        f"the gate named {sorted(named)}; recompute named none of them:\n{output}")

    def test_a_hand_edited_record(self):
        out = self.produced()
        record = self.record(out)
        record["randomness"] = "seeded"
        pathlib.Path(out, "provenance.json").write_bytes(provenance.serialize(record))
        self.assert_recompute_names(out, "randomness")


class TestRefuses(ProvenanceCase):
    def test_a_dirty_factory(self):
        repo = self.own_repo()
        pathlib.Path(repo, "tools", "factory", "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
        code, output, out = self.produce(repo=repo)
        self.assertEqual(code, 1, output)
        self.assertIn("REFUSED", output)
        self.assertIn("uncommitted changes", output)
        self.assertFalse(os.path.exists(out), "nothing is produced")

        out = self.produced(repo=repo, extra=("--allow-dirty",))
        self.assertTrue(self.record(out)["factory"]["dirty"])

    def test_a_modified_tracked_file_is_dirty_too(self):
        repo = self.own_repo()
        with open(os.path.join(repo, "tools", "factory", "intake.py"), "a", encoding="utf-8") as handle:
            handle.write("\n")
        code, output, _ = self.produce(repo=repo)
        self.assertEqual(code, 1, output)
        self.assertIn("uncommitted changes", output)

    # A symlink and an ignored file are the two ways the bytes `recipes()` hashes can fail to be
    # the bytes of the commit the record names, with `git status` calling the tree clean (#232).
    # Each test below commits what it makes, or has git ignore it, so the *dirty* rule cannot
    # fire; each asserts the refusal's own words, because a test that asserted only the verdict
    # would pass on `--allow-dirty`'s rule firing instead of this one (#283). `assertNotIn` on
    # "uncommitted changes" says that in the assertion itself.

    def _outside(self, name, text="OUTSIDE = 1\n"):
        """A file outside the scratch repository, for a symlink under it to point at."""
        outside = os.path.join(self.tmp, "outside")
        os.makedirs(outside, exist_ok=True)
        path = os.path.join(outside, name)
        pathlib.Path(path).write_text(text, encoding="utf-8")
        return path

    def test_a_tracked_file_symlink_under_the_factory(self):
        repo = self.own_repo()
        link = os.path.join(repo, "tools", "factory", "generate.py")
        target = self._outside("outside.py", pathlib.Path(link).read_text(encoding="utf-8"))
        os.remove(link)
        os.symlink(target, link)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "generate.py is a symlink")
        self.assertEqual(git(repo, "status", "--porcelain"), "", "the symlink is committed; git calls the tree clean")
        code, output, out = self.produce(repo=repo)
        self.assertEqual(code, 1, output)
        self.assertIn("tools/factory/generate.py is a symlink", output)
        self.assertNotIn("uncommitted changes", output)
        self.assertFalse(os.path.exists(out), "nothing is produced")

    def test_a_tracked_directory_symlink_under_the_factory(self):
        repo = self.own_repo()
        self._outside("in_pkg.py")
        os.symlink(os.path.join(self.tmp, "outside"), os.path.join(repo, "tools", "factory", "pkg"))
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "pkg is a symlink")
        self.assertEqual(git(repo, "status", "--porcelain"), "", "the symlink is committed; git calls the tree clean")
        code, output, _ = self.produce(repo=repo)
        self.assertEqual(code, 1, output)
        self.assertIn("tools/factory/pkg is a symlink", output)
        self.assertNotIn("uncommitted changes", output)

    def test_a_symlinked_checker_beside_the_factory(self):
        repo = self.own_repo()
        checker = os.path.join(repo, "tools", "check-map.py")
        target = self._outside("outside-check-map.py", pathlib.Path(checker).read_text(encoding="utf-8"))
        os.remove(checker)
        os.symlink(target, checker)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "check-map.py is a symlink")
        self.assertEqual(git(repo, "status", "--porcelain"), "", "the symlink is committed; git calls the tree clean")
        code, output, _ = self.produce(repo=repo)
        self.assertEqual(code, 1, output)
        self.assertIn("tools/check-map.py is a symlink", output)
        self.assertNotIn("uncommitted changes", output)

    def test_an_ignored_file_under_the_factory(self):
        repo = self.own_repo()
        with open(os.path.join(repo, ".gitignore"), "a", encoding="utf-8") as handle:
            handle.write("/tools/factory/local_notes.py\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "ignore local_notes.py")
        pathlib.Path(repo, "tools", "factory", "local_notes.py").write_text("LOCAL = 1\n", encoding="utf-8")
        self.assertEqual(git(repo, "status", "--porcelain"), "", "an ignored file leaves the tree clean")
        code, output, out = self.produce(repo=repo)
        self.assertEqual(code, 1, output)
        self.assertIn("tools/factory/local_notes.py is ignored by git", output)
        self.assertNotIn("uncommitted changes", output)
        self.assertFalse(os.path.exists(out), "nothing is produced")

    # Bytecode under `tools/factory` is an ignored file like any other, and the one the factory
    # actually executes: a `.pyc` whose header carries the source's mtime and size is loaded in
    # preference to the `.py` beside it, at import, before `produce()` reaches any check (#373).
    # It used to be exempt, because a run left its own `__pycache__` behind and the next run would
    # have refused itself; the entry point now suppresses bytecode instead, so the exemption is
    # gone rather than widened.

    def plant_bytecode(self, repo, module, forge):
        """A loadable `.pyc` for `<repo>/tools/factory/<module>.py`, with that source's header.

        `forge` makes the code from the module's own source, so the import succeeds and the run
        gets as far as the check under test; a stub would fail at some later attribute instead and
        prove nothing about this rule.
        """
        source = pathlib.Path(repo, "tools", "factory", f"{module}.py")
        stat = source.stat()
        code = compile(forge(source.read_text(encoding="utf-8")), str(source), "exec")
        cache = pathlib.Path(importlib.util.cache_from_source(str(source)))
        cache.parent.mkdir(parents=True, exist_ok=True)
        with open(cache, "wb") as handle:
            handle.write(importlib.util.MAGIC_NUMBER)
            handle.write(struct.pack("<III", 0, int(stat.st_mtime) & 0xFFFFFFFF, stat.st_size & 0xFFFFFFFF))
            handle.write(marshal.dumps(code))
        return cache

    def test_planted_bytecode_under_the_factory(self):
        repo = self.own_repo()
        cache = self.plant_bytecode(repo, "generate", lambda text: text + "\nFORGED = True\n")
        # The premise, proved rather than asserted: this .pyc is what an import of the factory's
        # own directory loads. Without it the test would pass on a file Python ignores.
        # `-B`, so this probe writes no bytecode of its own. `generate` imports its siblings, and
        # their .pyc files would then sit beside the planted one -- the refusal names whichever it
        # reaches first, and the assertion below would be about a file this test did not plant.
        # It passed only because the gate's pytest exports PYTHONDONTWRITEBYTECODE, which is a
        # test held to its assertion by its caller's environment (#384, and the same shape).
        loaded = subprocess.run([sys.executable, "-B", "-c", "import generate; print(generate.FORGED)"],
                                cwd=os.path.join(repo, "tools", "factory"),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(loaded.stdout.strip(), "True", "the planted bytecode is not what Python loads")
        self.assertEqual(git(repo, "status", "--porcelain"), "", "ignored bytecode leaves the tree clean")
        code, output, out = self.produce(repo=repo)
        self.assertEqual(code, 1, output)
        # The .pyc itself, not the __pycache__/ git collapses it into, and the bytecode wording
        # rather than the plain ignored-file one: the refusal has to say which file ran (#283).
        self.assertIn(f"{os.path.relpath(cache, repo)} is bytecode git ignores", output)
        self.assertNotIn("uncommitted changes", output)
        self.assertFalse(os.path.exists(out), "nothing is produced")

    def test_planted_bytecode_for_the_entry_point_itself(self):
        """The `.pyc` the factory cannot prevent, and therefore removes: `python3 tools/factory`
        runs a directory, so CPython caches `__main__.py` before its first line sets the flag.

        What is removed is only bytecode equal to what the source compiles to now. This one is
        not, it runs (the marker it prints says so), and it is refused rather than tidied away --
        a delete here would be the old exemption with an extra step.
        """
        repo = self.own_repo()
        cache = self.plant_bytecode(repo, "__main__", lambda text: 'print("FORGED entry point")\n' + text)
        code, output, out = self.produce(repo=repo)
        self.assertIn("FORGED entry point", output, "the planted bytecode is not what Python ran")
        self.assertEqual(code, 1, output)
        self.assertIn(f"{os.path.relpath(cache, repo)} is bytecode git ignores", output)
        self.assertNotIn("uncommitted changes", output)
        self.assertFalse(os.path.exists(out), "nothing is produced")

    def test_a_stray_pyc_beside_the_factory_modules(self):
        # The other shape git reports: a `*.pyc` outside any __pycache__ matches the ignore
        # pattern by itself, and is named by itself.
        repo = self.own_repo()
        pathlib.Path(repo, "tools", "factory", "generate.pyc").write_bytes(b"\0")
        self.assertEqual(git(repo, "status", "--porcelain"), "", "ignored bytecode leaves the tree clean")
        code, output, _ = self.produce(repo=repo)
        self.assertEqual(code, 1, output)
        self.assertIn("tools/factory/generate.pyc is bytecode git ignores", output)
        self.assertNotIn("uncommitted changes", output)

    def test_a_second_consecutive_produce_in_the_same_checkout(self):
        """What the exemption existed to prevent: the factory refusing itself after one run.

        The environment is the one an agent has -- PYTHONDONTWRITEBYTECODE unset -- so what is
        proved is the entry point's own `sys.dont_write_bytecode` and not this test runner's
        inherited setting.
        """
        bare = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
        repo = self.own_repo()
        first = self.produced(repo=repo, out=os.path.join(self.tmp, "a"), env=bare)
        left = [os.path.join(base, name)
                for base, dirs, names in os.walk(os.path.join(repo, "tools"))
                for name in list(dirs) + names
                if name == "__pycache__" or name.endswith(".pyc")]
        self.assertEqual(left, [], "the factory wrote bytecode into its own checkout")
        second = self.produced(repo=repo, out=os.path.join(self.tmp, "b"), env=bare)
        self.assertEqual(pathlib.Path(first, "provenance.json").read_bytes(),
                         pathlib.Path(second, "provenance.json").read_bytes())

    def test_every_tool_that_puts_the_factory_on_the_path_suppresses_bytecode(self):
        """The repository's side of the rule test_factory_rails.py holds every emitted script to.

        A tool that imports the factory's modules leaves their bytecode in `tools/factory`, and
        the next produce refuses it -- rightly, because it is what Python runs and no commit holds
        it. scripts/validate.sh exports PYTHONDONTWRITEBYTECODE for its children, but
        scripts/validate-engine.sh does not, and an agent's shell exports nothing, so each tool
        says it for itself. What is asserted is where the flag sits: the loader reads it when the
        import happens, so a flag after the path insert prevents exactly nothing.
        """
        suppressors = {}
        for path in sorted(pathlib.Path(TOOLS).glob("*.py")) + [pathlib.Path(FACTORY, "__main__.py")]:
            lines = path.read_text(encoding="utf-8").splitlines()
            reaches = next((i for i, line in enumerate(lines)
                            if "sys.path.insert" in line and not line.lstrip().startswith("#")), None)
            if reaches is None:
                continue
            relative = str(path.relative_to(REPO))
            suppressors[relative] = reaches
            # Column 0, so the flag is module level and not nested in some function that may
            # never run: check-readme-status.py reaches for the factory inside one.
            flag = next((i for i, line in enumerate(lines)
                         if line.split("#")[0].rstrip() == "sys.dont_write_bytecode = True"), None)
            self.assertIsNotNone(flag, f"{relative} puts tools/factory on the path and leaves its bytecode "
                                       f"there, for the next produce to refuse (#373)")
            self.assertLess(flag, reaches,
                            f"{relative} sets dont_write_bytecode at line {flag + 1}, after line "
                            f"{reaches + 1} reaches for the path; there it prevents nothing")
        # Named, so a new tool that starts importing the factory fails here rather than being
        # skipped by a check that examined whatever it happened to find.
        self.assertEqual(sorted(suppressors),
                         ["tools/check-readme-status.py", "tools/factory/__main__.py", "tools/pack-map.py",
                          "tools/validate-engine.py"])

    def test_a_factory_outside_git(self):
        loose = os.path.join(self.tmp, "loose")
        shutil.copytree(FACTORY, os.path.join(loose, "tools", "factory"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        env_ceiling = {**os.environ, **GIT_ENV, "GIT_CEILING_DIRECTORIES": self.tmp}
        done = subprocess.run([sys.executable, os.path.join(loose, "tools", "factory"), "produce",
                               "--package", self.part107, "--corpus", PART107_XML, "--name", NAME,
                               "--out", os.path.join(self.tmp, "engine")],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env_ceiling)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not a git checkout", done.stdout)


class TestEmbeddedCopyBuilds(ProvenanceCase):
    """`dotnet test` on a produced engine: the generated provenance test passes on the real build."""

    def test_dotnet_test(self):
        from importlib.util import module_from_spec, spec_from_file_location
        spec = spec_from_file_location("factory_generate_pin", os.path.join(FACTORY, "generate.py"))
        pins = module_from_spec(spec)
        spec.loader.exec_module(pins)
        dotnet = shutil.which("dotnet")
        if dotnet is None:
            self.skipTest("no dotnet on PATH")
        sdks = subprocess.run([dotnet, "--list-sdks"], stdout=subprocess.PIPE, text=True).stdout
        if not any(line.split(" ")[0] == pins.SDK_VERSION for line in sdks.splitlines()):
            self.skipTest(f"the .NET SDK {pins.SDK_VERSION} the kernel pins is not installed")
        hoyle = pack(HOYLE, os.path.join(self.tmp, "hoyle"))
        out = self.produced(package=hoyle, corpus=os.path.join(HOYLE, "hoyle.txt"), name="HoyleBackgammon")
        done = subprocess.run([dotnet, "test", os.path.join(out, "HoyleBackgammon.slnx")],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(done.returncode, 0, done.stdout[-4000:])


if __name__ == "__main__":
    unittest.main()
