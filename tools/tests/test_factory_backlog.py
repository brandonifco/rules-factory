#!/usr/bin/env python3
"""`factory produce` writes the backlog (#3, M5), and `factory backlog --create` files it.

Asserted: one `backlog/NNN-<id>.md` per in-scope, unbuilt entry that is neither
`definedElsewhere` nor `beyondAdapter` (derived entries included), for Part 107 and backgammon;
every file comes after every file for its `dependsOn`; its locator citation and evidence are the
map's bytes; links resolve; two runs give identical bytes and a stale item is removed; a cycle
is refused. `--create` against a stubbed `gh` (`FACTORY_GH`) finds issues by the entry marker
under each item's title: it creates each issue once, updates it when the entry is renamed or
its dependencies change, writes nothing on a second run, adopts a legacy title-only issue,
refuses a duplicate marker before any write, and reports without touching an issue whose entry
left the backlog. No real repository is touched.

Run: python3 -m unittest discover -s tools/tests
"""
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
FACTORY = os.path.join(TOOLS, "factory")
PACK = os.path.join(TOOLS, "pack-map.py")

_spec = importlib.util.spec_from_file_location("factory_main_backlog", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
backlog = factory.backlog_step

CASES = {
    "part107": ("faa-part-107", "part107.xml", "FaaPart107"),
    "hoyle": ("hoyle-backgammon", "hoyle.txt", "HoyleBackgammon"),
}
FENCE = re.compile(rb"^(`{3,})text\n(.*?)\n\1$", re.S | re.M)


def run(argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = factory.main(argv)
    return code, buffer.getvalue()


def backlog_files(engine):
    directory = os.path.join(engine, "backlog")
    out = {}
    for name in sorted(os.listdir(directory)):
        with open(os.path.join(directory, name), "rb") as handle:
            out[name] = handle.read()
    return out


def qualifies(entry):
    """The rule, restated independently of backlog.disposition."""
    return (entry["scope"] == "in" and entry["status"] in ("mapped", "blocked")
            and "definedElsewhere" not in entry and "beyondAdapter" not in entry)


class BacklogCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.packages, cls.maps, cls.engines = {}, {}, {}
        for key, (example, corpus, name) in CASES.items():
            directory = os.path.join(REPO, "examples", example)
            out = os.path.join(cls.tmp, "pkg-" + key)
            subprocess.run([sys.executable, PACK, directory, "--out", out], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (nupkg,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
            cls.packages[key] = (os.path.join(out, nupkg), os.path.join(directory, corpus), name)
            with open(os.path.join(directory, "corpus-map.json"), encoding="utf-8") as handle:
                cls.maps[key] = json.load(handle)
            cls.engines[key] = os.path.join(cls.tmp, "engine-" + key)
            code, log = cls.produce(key, cls.engines[key])
            assert code == 0, log

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    @classmethod
    def produce(cls, key, out):
        nupkg, corpus, name = cls.packages[key]
        return run(["produce", "--package", nupkg, "--corpus", corpus, "--name", name, "--out", out,
                    # this checkout's own git state is not under test here (test_factory_provenance.py)
                    "--allow-dirty",
                    "--no-verify"])  # no .NET SDK assumed; test_factory_verify.py covers verify

    def items(self, key):
        return {n: b for n, b in backlog_files(self.engines[key]).items() if n != "README.md"}

    def test_one_file_per_qualifying_entry(self):
        for key in CASES:
            with self.subTest(key):
                expected = {e["id"] for e in self.maps[key]["entries"] if qualifies(e)}
                names = self.items(key)
                ids = {re.match(r"^\d{3}-(.+)\.md$", n).group(1) for n in names}
                self.assertEqual(ids, expected)
                self.assertEqual(sorted(names), [f"{i:03d}-{n.split('-', 1)[1]}" for i, n in
                                                 enumerate(sorted(names), 1)])
        self.assertEqual(len(self.items("part107")), 39)
        self.assertEqual(len(self.items("hoyle")), 28)
        self.assertIn("hit-pays-single-stake", "".join(self.items("hoyle")))

    def test_each_file_follows_its_dependencies(self):
        for key in CASES:
            with self.subTest(key):
                position = {n.split("-", 1)[1][:-3]: n for n in self.items(key)}
                for entry in self.maps[key]["entries"]:
                    if entry["id"] not in position:
                        continue
                    for dep in entry["dependsOn"]:
                        if dep in position:
                            self.assertLess(position[dep], position[entry["id"]], f"{entry['id']} before {dep}")

    def test_locator_and_evidence_are_the_maps_bytes(self):
        for key in CASES:
            by_id = {e["id"]: e for e in self.maps[key]["entries"]}
            for name, data in self.items(key).items():
                entry = by_id[name.split("-", 1)[1][:-3]]
                with self.subTest(f"{key}/{name}"):
                    blocks = [m.group(2) for m in FENCE.finditer(data)]
                    sources = [by_id[s] for s in entry.get("derivedFrom") or [entry["id"]]]
                    for i, source in enumerate(sources):
                        self.assertEqual(blocks[2 * i], source["locator"]["citation"].encode("utf-8"))
                        self.assertEqual(blocks[2 * i + 1], source["evidence"].encode("utf-8"))
                    self.assertEqual(blocks[-1], entry["note"].encode("utf-8"))
                    self.assertIn(f'`Handlers.{factory.generate.pascal(entry["id"])}`'.encode(), data)
                    self.assertIn(b"mutation", data)
                    self.assertTrue(data.startswith(f"# {entry['id']}: ".encode()))

    def test_ambiguity_and_gates_are_carried(self):
        items = self.items("hoyle")
        (bearing,) = [b for n, b in items.items() if n.endswith("-bearing-off-highest.md")]
        self.assertRegex(bearing.decode(), r"enabledBy.*\n\n- \[`bearing-off-eligible`\]\(\d{3}-bearing-off-eligible\.md\)")
        (entry,) = [b for n, b in items.items() if n.endswith("-legal-destination.md")]
        self.assertIn(b"docs/decisions/0006-", entry)
        (inner,) = [b for n, b in items.items() if n.endswith("-bearing-off-move-or-remove.md")]
        self.assertIn(b"## Reachability", inner)

    def test_links_resolve_and_readme_lists_order(self):
        for key in CASES:
            with self.subTest(key):
                files = backlog_files(self.engines[key])
                for name, data in files.items():
                    for target in re.findall(rb"\]\(([^)]+\.md)\)", data):
                        self.assertIn(target.decode(), files, f"{name} links {target}")
                listed = re.findall(r"^\d+\. \[.*\]\((\d{3}-.+\.md)\)$", files["README.md"].decode(), re.M)
                self.assertEqual(listed, sorted(self.items(key)))

    def test_deterministic_and_stale_items_removed(self):
        other = os.path.join(self.tmp, "again")
        stale = os.path.join(other, "backlog", "999-gone.md")
        os.makedirs(os.path.dirname(stale))
        with open(stale, "w", encoding="utf-8") as handle:
            handle.write("# gone\n")
        code, log = self.produce("part107", other)
        self.assertEqual(code, 0, log)
        self.assertEqual(backlog_files(other), backlog_files(self.engines["part107"]))
        self.assertNotIn(self.tmp.encode(), b"".join(backlog_files(other).values()))

    def test_a_dependency_cycle_is_refused(self):
        entries = [{"id": "a", "dependsOn": ["b"]}, {"id": "b", "dependsOn": ["a"]}]
        with self.assertRaisesRegex(backlog.BacklogError, "cycle"):
            backlog.order(entries)

    def test_ties_break_by_map_order(self):
        entries = [{"id": "c", "dependsOn": ["b"]}, {"id": "a", "dependsOn": []}, {"id": "b", "dependsOn": []}]
        self.assertEqual([e["id"] for e in backlog.order(entries)], ["a", "b", "c"])


STUB = r'''#!{python}
import json, os, sys
state = os.environ["GH_STUB_STATE"]
issues = json.load(open(state)) if os.path.exists(state) else []
args = sys.argv[1:]
with open(state + ".calls", "a") as log:
    log.write(json.dumps(args) + "\n")
def save():
    json.dump(issues, open(state, "w"))
if args[:2] == ["issue", "list"]:
    assert args[args.index("--repo") + 1] == "example/engine"
    assert args[args.index("--state") + 1] == "all"
    assert args[args.index("--json") + 1] == "number,title,body"
    print(json.dumps(issues[:int(args[args.index("--limit") + 1])]))
elif args[:2] == ["issue", "create"]:
    assert args[args.index("--body-file") + 1] == "-"
    number = max([i["number"] for i in issues] + [0]) + 1
    issues.append({{"number": number, "title": args[args.index("--title") + 1], "body": sys.stdin.read()}})
    save()
    print("https://github.com/example/engine/issues/%d" % number)
elif args[:2] == ["issue", "edit"]:
    assert args[args.index("--body-file") + 1] == "-"
    (issue,) = [i for i in issues if i["number"] == int(args[2])]
    issue["title"] = args[args.index("--title") + 1]
    issue["body"] = sys.stdin.read()
    save()
    print("https://github.com/example/engine/issues/%d" % issue["number"])
else:
    sys.exit("unexpected gh call: %r" % args)
'''

CONTEXT = {"name": "Engine", "package": "Pkg", "version": "1.0.0"}


def entries():
    return [
        {"id": "first", "name": "First", "kind": "value", "scope": "in", "clarity": "clear",
         "dependsOn": [], "status": "mapped", "locator": {"sourceId": "s", "citation": "p. 1"},
         "evidence": "One.", "note": "n"},
        {"id": "second", "name": "Second", "kind": "operation", "scope": "in", "clarity": "clear",
         "dependsOn": ["first"], "status": "mapped", "locator": {"sourceId": "s", "citation": "p. 2"},
         "evidence": "Two.", "note": "n"},
    ]


class CreateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.engine = os.path.join(self.tmp, "engine")
        self.emit(entries())
        self.state = os.path.join(self.tmp, "issues.json")
        self.gh = os.path.join(self.tmp, "gh")
        with open(self.gh, "w", encoding="utf-8") as handle:
            handle.write(STUB.format(python=sys.executable))
        os.chmod(self.gh, os.stat(self.gh).st_mode | stat.S_IEXEC)
        os.environ["GH_STUB_STATE"] = self.state
        os.environ["FACTORY_GH"] = self.gh
        self.addCleanup(os.environ.pop, "GH_STUB_STATE", None)
        self.addCleanup(os.environ.pop, "FACTORY_GH", None)

    def emit(self, listed):
        backlog.emit(listed, CONTEXT, self.engine)

    def create(self):
        return run(["backlog", "--create", "--repo", "example/engine", "--dir", self.engine])

    def issues(self):
        with open(self.state, encoding="utf-8") as handle:
            return json.load(handle)

    def seed(self, issues):
        with open(self.state, "w", encoding="utf-8") as handle:
            json.dump([{"number": n, "title": t, "body": b} for n, t, b in issues], handle)

    def writes(self):
        """The create and edit calls the stub has seen, then forgets them."""
        calls = self.state + ".calls"
        if not os.path.exists(calls):
            return []
        with open(calls, encoding="utf-8") as handle:
            seen = [json.loads(line) for line in handle]
        os.remove(calls)
        return [c[:2] + c[2:3] * (c[1] == "edit") for c in seen if c[:2] != ["issue", "list"]]

    def body(self, name):
        with open(os.path.join(self.engine, "backlog", name), encoding="utf-8") as handle:
            return handle.read().partition("\n")[2].lstrip("\n")

    def test_every_item_carries_its_markers_under_the_title(self):
        body = self.body("002-second.md")
        self.assertTrue(body.startswith("<!-- rules-factory-entry: second -->\n"
                                        "<!-- rules-factory-engine: Engine; map: Pkg -->\n"), body)
        self.assertEqual(backlog.entry_of(body), "second")
        self.assertIsNone(backlog.entry_of("quoted:\n<!-- rules-factory-entry: second -->\n"))

    def test_creates_in_order_then_a_second_run_writes_nothing(self):
        code, log = self.create()
        self.assertEqual(code, 0, log)
        self.assertEqual([i["title"] for i in self.issues()], ["first: First", "second: Second"])
        self.assertIn("(001-first.md)", self.issues()[1]["body"])
        self.assertFalse(self.issues()[0]["body"].startswith("# "))
        self.assertEqual(self.writes(), [["issue", "create"], ["issue", "create"]])
        code, log = self.create()
        self.assertEqual(code, 0, log)
        self.assertIn("0 created, 0 updated, 0 adopted, 2 unchanged, 0 not in the backlog", log)
        self.assertEqual(self.writes(), [])
        self.assertEqual(len(self.issues()), 2)

    def test_renaming_an_entry_updates_its_issue_and_creates_none(self):
        self.create()
        self.writes()
        renamed = entries()
        renamed[0]["name"] = "The First"
        self.emit(renamed)
        code, log = self.create()
        self.assertEqual(code, 0, log)
        self.assertEqual([i["title"] for i in self.issues()], ["first: The First", "second: Second"])
        self.assertEqual(self.writes(), [["issue", "edit", "1"]])
        self.assertIn("updated   #1 first: The First", log)
        self.assertEqual(self.create()[0], 0)
        self.assertEqual(self.writes(), [])

    def test_changing_dependencies_updates_the_body(self):
        self.create()
        self.writes()
        changed = entries()
        changed[1]["dependsOn"] = []
        self.emit(changed)
        code, log = self.create()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.writes(), [["issue", "edit", "2"]])
        self.assertNotIn("(001-first.md)", self.issues()[1]["body"])
        self.assertEqual(self.issues()[1]["body"], self.body("002-second.md"))
        self.assertIn("0 created, 1 updated, 0 adopted, 1 unchanged", log)

    def test_line_endings_and_trailing_space_github_adds_are_not_a_change(self):
        first, second = self.body("001-first.md"), self.body("002-second.md")
        self.seed([(7, "first: First", first.replace("\n", "\r\n").rstrip()), (8, "second: Second", second)])
        code, log = self.create()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.writes(), [])

    def test_a_duplicate_marker_refuses_before_any_write(self):
        first = self.body("001-first.md")
        self.seed([(3, "first: First", first), (5, "copy", first)])
        code, log = self.create()
        self.assertEqual(code, 1, log)
        self.assertIn("first on #3, #5", log)
        self.assertEqual(self.writes(), [])
        self.assertEqual(len(self.issues()), 2)

    def test_a_legacy_title_only_issue_is_adopted(self):
        self.seed([(4, "first: First", "made by hand"), (9, "unrelated", "text")])
        code, log = self.create()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.writes(), [["issue", "edit", "4"], ["issue", "create"]])
        self.assertEqual([(i["number"], i["title"]) for i in self.issues()],
                         [(4, "first: First"), (9, "unrelated"), (10, "second: Second")])
        self.assertEqual(backlog.entry_of(self.issues()[0]["body"]), "first")
        self.assertIn("0 updated, 1 adopted", log)
        self.assertEqual(self.create()[0], 0)
        self.assertEqual(self.writes(), [])

    def test_two_legacy_issues_with_the_title_refuse(self):
        self.seed([(1, "second: Second", "a"), (2, "second: Second", "b")])
        code, log = self.create()
        self.assertEqual(code, 1, log)
        self.assertIn("#1, #2", log)
        self.assertEqual(self.writes(), [])

    def test_an_issue_whose_entry_left_the_backlog_is_reported_and_left_alone(self):
        self.create()
        self.writes()
        self.emit(entries()[:1])
        code, log = self.create()
        self.assertEqual(code, 0, log)
        self.assertIn("not in backlog #2 second: Second -- left as it is", log)
        self.assertIn("1 not in the backlog", log)
        # "item 1 of 2" became "item 1 of 1"; the issue that left is not written.
        self.assertEqual(self.writes(), [["issue", "edit", "1"]])
        self.assertEqual([i["title"] for i in self.issues()], ["first: First", "second: Second"])

    def test_a_listing_that_reaches_the_limit_refuses(self):
        self.addCleanup(setattr, backlog, "LIST_LIMIT", backlog.LIST_LIMIT)
        backlog.LIST_LIMIT = 2
        self.seed([(1, "a", ""), (2, "b", ""), (3, "c", "")])
        code, log = self.create()
        self.assertEqual(code, 1, log)
        self.assertIn("at least 2 issues", log)
        self.assertEqual(self.writes(), [])

    def test_a_failing_gh_is_a_refusal(self):
        os.environ["FACTORY_GH"] = os.path.join(self.tmp, "no-such-gh")
        code, log = self.create()
        self.assertEqual(code, 1, log)

    def test_a_missing_backlog_and_a_bad_repo(self):
        code, _ = run(["backlog", "--create", "--repo", "example/engine", "--dir", os.path.join(self.tmp, "none")])
        self.assertEqual(code, 1)
        code, _ = run(["backlog", "--create", "--repo", "not a repo", "--dir", self.engine])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(self.state))


if __name__ == "__main__":
    unittest.main()
