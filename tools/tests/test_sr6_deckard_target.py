#!/usr/bin/env python3
"""examples/sr6-deckard/check-target.py, proved able to refuse.

The committed TARGET.json is checked here only for internal consistency (--self-check): comparing
it with deckard needs a clone and the network, which CI does not have, so that run belongs to the
equivalence step. Every comparison the checker makes is instead exercised against a synthetic
deckard-shaped git repository built here, with a fake dotnet that writes TRX files: a TARGET the
fixture agrees with passes, and each pin, changed on its own, is refused.

Run: python3 -m unittest discover -s tools/tests
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXAMPLE = ROOT / "examples" / "sr6-deckard"
TOOL = EXAMPLE / "check-target.py"

_spec = importlib.util.spec_from_file_location("check_target", TOOL)
check_target = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_target)


def run_main(*argv, env=None):
    out = io.StringIO()
    old = dict(os.environ)
    try:
        if env:
            os.environ.update(env)
        with redirect_stdout(out), redirect_stderr(out):
            code = check_target.main([str(a) for a in argv])
    finally:
        os.environ.clear()
        os.environ.update(old)
    return code, out.getvalue()


TESTS_CS = textwrap.dedent("""\
    using Xunit;

    namespace Demo.Tests.Things;

    public sealed class ThingTests
    {
        [Fact]
        public void A_fact_holds()
        {
            Assert.True(true);
        }

        [Theory]
        [InlineData(1)]
        [InlineData(2)]
        public void A_theory_holds(int value)
        {
            Assert.True(value > 0);
        }
    }
    """)

ARCH_CS = textwrap.dedent("""\
    namespace Demo.Tests;

    public sealed class ArchitectureTests
    {
        [Fact]
        public void Layers_hold() { }
    }
    """)

SOURCE_CS = "\n".join(f"// line {n}" for n in range(1, 11)) + "\n"

VALIDATE_SH = textwrap.dedent("""\
    #!/usr/bin/env bash
    check_pin() {
      step "SDK pin"
    }
    step "Format"
    """)

REPO_CHECKS = textwrap.dedent("""\
    CHECKS = {
        "layering": check_layering,
        "text-hygiene": check_text_hygiene,
    }
    """)

FAKE_DOTNET = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys, uuid
    from pathlib import Path
    spec = json.loads(os.environ["FAKE_TRX_SPEC"])
    args = sys.argv[1:]
    results = Path(args[args.index("--results-directory") + 1])
    results.mkdir(parents=True, exist_ok=True)
    for n, (project, cases) in enumerate(spec.items()):
        defs, res = [], []
        for cls, method, outcome in cases:
            tid = str(uuid.uuid4())
            defs.append(f'<UnitTest name="{cls}.{method}" id="{tid}"><TestMethod codeBase="/x/{project}/bin/Release/net10.0/{project}.dll" className="{cls}" name="{method}"/></UnitTest>')
            res.append(f'<UnitTestResult testId="{tid}" testName="{cls}.{method}" outcome="{outcome}"/>')
        ns = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"
        (results / f"run{n}.trx").write_text(f'<TestRun xmlns="{ns}"><Results>{"".join(res)}</Results><TestDefinitions>{"".join(defs)}</TestDefinitions></TestRun>')
    sys.exit(int(os.environ.get("FAKE_DOTNET_EXIT", "0")))
    """)

PASSING = {
    "Demo.Tests": [
        ["Demo.Tests.ArchitectureTests", "Layers_hold", "Passed"],
        ["Demo.Tests.Things.ThingTests", "A_fact_holds", "Passed"],
        ["Demo.Tests.Things.ThingTests", "A_theory_holds", "Passed"],
        ["Demo.Tests.Things.ThingTests", "A_theory_holds", "Passed"],
    ]
}


def sha(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class Fixture(unittest.TestCase):
    """A deckard-shaped repository at one commit, and a TARGET written by hand to agree with it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / "deckard"
        self.files = {
            "Demo.slnx": "<Solution />\n",
            "tests/Demo.Tests/Demo.Tests.csproj": "<Project />\n",
            "tests/Demo.Tests/ArchitectureTests.cs": ARCH_CS,
            "tests/Demo.Tests/Things/ThingTests.cs": TESTS_CS,
            "tests/Demo.Testing/Helper.cs": "namespace Demo.Testing;\n",
            "src/Demo/Thing.cs": SOURCE_CS,
            "scripts/validate.sh": VALIDATE_SH,
            "tools/repo-checks.py": REPO_CHECKS,
            ".github/workflows/ci.yml": "name: ci\n",
            ".claude/hooks/guard.py": "# guard\n",
            **{f"docs/decisions/000{n}-record-{n}.md": f"# Record {n}\n" for n in range(1, 8)},
            "docs/decisions/0008-later.md": "# Later\n",
        }
        for path, text in self.files.items():
            self.write(path, text)
        self.git("init", "-q")
        self.commit = self.commit_all("fixture")

        self.dotnet = base / "fake-dotnet"
        self.dotnet.write_text(FAKE_DOTNET)
        self.dotnet.chmod(self.dotnet.stat().st_mode | stat.S_IEXEC)
        self.env = {"DOTNET": str(self.dotnet), "FAKE_TRX_SPEC": json.dumps(PASSING)}

        self.target = self.make_target()

    def tearDown(self):
        self.tmp.cleanup()

    # -- helpers
    def write(self, path, text):
        full = self.repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(text)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def commit_all(self, message):
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def lines(self, path, start, end):
        return sha("\n".join(self.files[path].split("\n")[start - 1:end]))

    def make_target(self):
        methods = [
            "Demo.Tests.ArchitectureTests.Layers_hold",
            "Demo.Tests.Things.ThingTests.A_fact_holds",
            "Demo.Tests.Things.ThingTests.A_theory_holds",
        ]

        def gate(gid, path, line, cls="repository-process", **extra):
            return {"id": gid, "locator": {"path": path, "lines": str(line),
                                           "sha256": self.lines(path, line, line)},
                    "class": cls, "note": "fixture", **extra}

        return {
            "targetVersion": 1,
            "deckard": {"repository": "fixture", "commit": self.commit,
                        "testsTree": self.git("rev-parse", f"{self.commit}:tests")},
            "tests": {
                "methodCount": 3, "caseCount": 4,
                "projects": {"Demo.Tests": {"methodCount": 3, "caseCount": 4, "methods": methods}},
                "categories": {
                    "architecture": {"classes": ["Demo.Tests.ArchitectureTests"], "methodCount": 1, "runVerbatim": True},
                    "test-double": {"classes": [], "methodCount": 0, "runVerbatim": True},
                    "prng-and-dice": {"classes": [], "methodCount": 0, "runVerbatim": True},
                    "replay-identity": {"classes": [], "methodCount": 0, "runVerbatim": True},
                    "sr6-rules": {"classes": ["Demo.Tests.Things.ThingTests"], "methodCount": 2, "runVerbatim": True},
                },
            },
            "decisionRecords": [
                {"path": f"docs/decisions/000{n}-record-{n}.md", "sha256": sha(f"# Record {n}\n")} for n in range(1, 8)
            ],
            "codeCommentDecisions": [{
                "id": "a-decision", "summary": "fixture",
                "locators": [{"path": "src/Demo/Thing.cs", "lines": "3-5", "sha256": self.lines("src/Demo/Thing.cs", 3, 5)}],
                "pinnedBy": ["Demo.Tests.Things.ThingTests.A_fact_holds"],
            }],
            "gates": [
                gate("validate.sh/SDK pin", "scripts/validate.sh", 3, "divergent", approvedBy="D6"),
                gate("validate.sh/Format", "scripts/validate.sh", 5, "equivalent"),
                gate("repo-checks/layering", "tools/repo-checks.py", 2, "carried-as-test"),
                gate("repo-checks/text-hygiene", "tools/repo-checks.py", 3, "carried-as-test"),
                gate("workflow/ci.yml", ".github/workflows/ci.yml", 1),
                gate("hook/guard.py", ".claude/hooks/guard.py", 1),
            ],
            "ownerDecisions": {"D6": {"date": "2026-09-15", "decision": "fixture"}},
        }

    def check(self, target=None, *flags, env=None):
        path = Path(self.tmp.name) / "TARGET.json"
        path.write_text(json.dumps(target if target is not None else self.target))
        return run_main(self.repo, "--target", path, *flags, env={**self.env, **(env or {})})

    def assertRefused(self, target=None, *flags, expect=None, env=None):
        code, out = self.check(target, *flags, env=env)
        self.assertEqual(code, 1, out)
        if expect:
            self.assertIn(expect, out)
        return out


class AgreeingTarget(Fixture):
    def test_a_target_the_fixture_agrees_with_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("ok   Demo.Tests: cases", out)
        self.assertIn("check-target: PASS against", out)

    def test_skip_tests_is_not_verified_never_ok(self):
        code, out = self.check(None, "--skip-tests")
        self.assertEqual(code, 3, out)
        self.assertIn("NOT VERIFIED", out)

    def test_the_working_tree_is_never_read(self):
        # A method added in the working tree and in a later commit changes nothing at the pinned commit.
        self.write("tests/Demo.Tests/Things/ThingTests.cs",
                   TESTS_CS.replace("    [Fact]\n", "    [Fact]\n    public void Added() { }\n\n    [Fact]\n", 1))
        self.write("docs/decisions/0001-record-1.md", "# Edited\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.commit_all("later")
        code, out = self.check()
        self.assertEqual(code, 0, out)


class PinsRefuse(Fixture):
    def mutated(self, fn):
        target = copy.deepcopy(self.target)
        fn(target)
        return target

    def test_a_commit_the_clone_lacks(self):
        self.assertRefused(self.mutated(lambda t: t["deckard"].update(commit="1" * 40)))

    def test_a_different_tests_tree(self):
        self.assertRefused(self.mutated(lambda t: t["deckard"].update(testsTree="2" * 40)),
                           expect="FAIL git tree hash of <commit>:tests")

    def test_a_method_missing_from_target(self):
        out = self.assertRefused(self.mutated(lambda t: (
            t["tests"]["projects"]["Demo.Tests"]["methods"].pop(),
            t["tests"]["projects"]["Demo.Tests"].update(methodCount=2),
            t["tests"].update(methodCount=2),
            t["tests"]["categories"]["sr6-rules"].update(methodCount=1))))
        self.assertIn("FAIL Demo.Tests: test methods", out)

    def test_a_method_added_at_a_new_commit(self):
        self.write("tests/Demo.Tests/Things/ThingTests.cs",
                   TESTS_CS.replace("    [Fact]\n", "    [Fact]\n    public void Added() { }\n\n    [Fact]\n", 1))
        commit = self.commit_all("add a test")
        target = self.mutated(lambda t: t["deckard"].update(commit=commit, testsTree=self.git("rev-parse", f"{commit}:tests")))
        self.assertRefused(target, expect="FAIL Demo.Tests: test methods")

    def test_an_edited_decision_record(self):
        self.assertRefused(self.mutated(lambda t: t["decisionRecords"][3].update(sha256="3" * 64)),
                           expect="FAIL sha256 docs/decisions/0004-record-4.md")

    def test_a_code_comment_locator_that_moved(self):
        self.assertRefused(self.mutated(lambda t: t["codeCommentDecisions"][0]["locators"][0].update(lines="4-6")),
                           expect="FAIL decision a-decision")

    def test_a_locator_outside_the_file(self):
        self.assertRefused(self.mutated(lambda t: t["codeCommentDecisions"][0]["locators"][0].update(lines="9-40")),
                           expect="outside the file")

    def test_an_unclassified_gate(self):
        out = self.assertRefused(self.mutated(lambda t: t["gates"].pop(1)))
        self.assertIn("every gate deckard declares has a row", out)
        self.assertIn("validate.sh/Format", out)

    def test_a_gate_locator_on_the_wrong_line(self):
        def move(t):
            t["gates"][1]["locator"].update(lines="4", sha256=self.lines("scripts/validate.sh", 4, 4))
        self.assertRefused(self.mutated(move), expect="FAIL gate validate.sh/Format: locator")

    def test_a_failing_case(self):
        failing = copy.deepcopy(PASSING)
        failing["Demo.Tests"][1][2] = "Failed"
        self.assertRefused(None, env={"FAKE_TRX_SPEC": json.dumps(failing)}, expect="FAIL Demo.Tests: every case passed")

    def test_a_case_count_that_differs(self):
        fewer = copy.deepcopy(PASSING)
        fewer["Demo.Tests"].pop()
        self.assertRefused(None, env={"FAKE_TRX_SPEC": json.dumps(fewer)}, expect="FAIL Demo.Tests: cases")

    def test_methods_that_ran_must_equal_methods_in_source(self):
        renamed = copy.deepcopy(PASSING)
        renamed["Demo.Tests"][1][1] = "Something_else"
        self.assertRefused(None, env={"FAKE_TRX_SPEC": json.dumps(renamed)},
                           expect="FAIL Demo.Tests: methods that ran equal methods in source")

    def test_dotnet_test_that_fails_to_run(self):
        self.assertRefused(None, env={"FAKE_DOTNET_EXIT": "1"}, expect="test cases could not be re-derived")

    def test_an_attribute_not_followed_by_a_test_method(self):
        self.write("tests/Demo.Tests/Things/ThingTests.cs", TESTS_CS.replace("public void A_fact_holds()", "private void A_fact_holds()"))
        commit = self.commit_all("helper")
        target = self.mutated(lambda t: t["deckard"].update(commit=commit, testsTree=self.git("rev-parse", f"{commit}:tests")))
        self.assertRefused(target, expect="not followed by a public void/Task method")

    def test_an_unapproved_divergent_gate_is_pending_unless_approval_is_required(self):
        target = self.mutated(lambda t: t["gates"][1].update({"class": "divergent", "approvedBy": None}))
        code, out = self.check(target)
        self.assertEqual(code, 0, out)
        self.assertIn("PENDING divergent gate validate.sh/Format", out)
        self.assertRefused(target, "--require-approved", expect="not approved")


class SelfCheck(Fixture):
    def self_check(self, target):
        path = Path(self.tmp.name) / "TARGET.json"
        path.write_text(json.dumps(target))
        return run_main("--self-check", "--target", path)

    def refuse(self, fn, expect):
        target = copy.deepcopy(self.target)
        fn(target)
        code, out = self.self_check(target)
        self.assertEqual(code, 1, out)
        self.assertIn(expect, out)

    def test_the_fixture_target_is_consistent(self):
        code, out = self.self_check(self.target)
        self.assertEqual(code, 0, out)

    def test_counts_must_equal_the_lists(self):
        self.refuse(lambda t: t["tests"].update(caseCount=5), "FAIL tests.caseCount")
        self.refuse(lambda t: t["tests"]["projects"]["Demo.Tests"].update(methodCount=4), "methodCount equals its list")

    def test_every_method_needs_a_category(self):
        self.refuse(lambda t: t["tests"]["categories"]["architecture"].update(classes=[]),
                    "every method's class is in a category")

    def test_no_category_may_be_superseded(self):
        self.refuse(lambda t: t["tests"]["categories"]["replay-identity"].update(runVerbatim=False), "none superseded")

    def test_a_gate_class_outside_the_vocabulary(self):
        self.refuse(lambda t: t["gates"][1].update({"class": "fine"}), "is not one of")

    def test_approval_must_name_a_recorded_owner_decision(self):
        self.refuse(lambda t: t["gates"][0].update(approvedBy="D9"), "must name a recorded owner decision")
        self.refuse(lambda t: t["gates"][1].update(approvedBy="D6"), "must name a recorded owner decision")

    def test_a_pinning_test_that_is_not_pinned(self):
        self.refuse(lambda t: t["codeCommentDecisions"][0].update(pinnedBy=["Demo.Tests.Nope.Nope"]),
                    "every pinning test is a pinned method")

    def test_free_text_cannot_carry_a_quotation(self):
        self.refuse(lambda t: t["gates"][1].update(note='the book says "roll them all"'), "quotes nothing")
        self.refuse(lambda t: t["gates"][1].update(note="x" * 401), "quotes nothing")

    def test_the_comparison_refuses_an_inconsistent_target(self):
        target = copy.deepcopy(self.target)
        target["tests"]["caseCount"] = 99
        code, out = self.check(target)
        self.assertEqual(code, 1, out)
        self.assertIn("refusing to compare", out)


class CommittedTarget(unittest.TestCase):
    """The frozen target itself, as far as it can be checked without deckard."""

    def setUp(self):
        self.target = json.loads((EXAMPLE / "TARGET.json").read_text(encoding="utf-8"))

    def test_it_is_internally_consistent(self):
        code, out = run_main("--self-check")
        self.assertEqual(code, 0, out)

    def test_it_freezes_the_commit_and_counts_the_plan_names(self):
        self.assertEqual(self.target["deckard"]["commit"], "9825f249d2566312f987bb5fcc04bfa2d2ee84ca")
        tests = self.target["tests"]
        self.assertEqual((tests["methodCount"], tests["caseCount"]), (110, 324))
        self.assertEqual({p: (s["methodCount"], s["caseCount"]) for p, s in tests["projects"].items()},
                         {"Deckard.Core.Tests": (64, 256), "Deckard.Rules.Tests": (45, 67), "Deckard.Data.Tests": (1, 1)})
        self.assertEqual({c: s["methodCount"] for c, s in tests["categories"].items()},
                         {"architecture": 3, "test-double": 5, "prng-and-dice": 30, "replay-identity": 28, "sr6-rules": 44})

    def test_only_the_sdk_pin_is_an_approved_divergence(self):
        approved = {g["id"]: g["approvedBy"] for g in self.target["gates"] if g.get("approvedBy")}
        self.assertEqual(approved, {"validate.sh/SDK pin": "D6"})

    def test_it_names_the_six_implicit_decisions_the_plan_lists(self):
        ids = {d["id"] for d in self.target["codeCommentDecisions"]}
        self.assertLessEqual({"threshold-zero-is-valid", "net-hits-zero-on-failure", "negative-inputs-throw",
                              "actor-draws-before-defender", "exactly-half-ones-is-not-a-glitch",
                              "glitch-independent-of-success"}, ids)


if __name__ == "__main__":
    unittest.main()
