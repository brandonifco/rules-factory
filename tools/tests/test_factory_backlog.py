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
import zipfile
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
            # `--no-verify` ends NOT VERIFIED (3), never 0 (tools/factory/__main__.py).
            assert code == factory.NOT_VERIFIED, log

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
        self.assertEqual(len(self.items("hoyle")), 29)
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

    def test_cross_references_are_carried_in_map_order(self):
        for key in CASES:
            by_id = {e["id"]: e for e in self.maps[key]["entries"]}
            files = {n.split("-", 1)[1][:-3]: n for n in self.items(key)}
            carried = 0
            for name, data in self.items(key).items():
                entry = by_id[name.split("-", 1)[1][:-3]]
                text = data.decode("utf-8")
                with self.subTest(f"{key}/{name}"):
                    section = text.split("## Cross-references\n\n", 1)[1].split("\n## ", 1)[0]
                    lines = [line for line in section.splitlines() if line.startswith("- ")]
                    references = entry.get("crossReferences") or []
                    if not references:
                        self.assertEqual(lines, ["- none"])
                        continue
                    self.assertEqual(len(lines), len(references))
                    for line, item in zip(lines, references):
                        head = f"- `cites` {json.dumps(item['cites'], ensure_ascii=False)} -- "
                        if "resolvedBy" in item:
                            target = item["resolvedBy"]
                            link = (f"[`{target}`]({files[target]})" if target in files
                                    else f"`{target}` -- no backlog item (")
                            self.assertTrue(line.startswith(head + "`resolvedBy` " + link), line)
                        else:
                            self.assertEqual(line, head + f"`unmapped`: {json.dumps(item['unmapped'], ensure_ascii=False)}")
                        carried += 1
            with self.subTest(key):
                self.assertGreater(carried, 0, f"no {key} item carries a cross-reference; the check examined nothing")
        (twilight,) = [b for n, b in self.items("part107").items() if n.endswith("-civil-twilight-operation.md")]
        self.assertRegex(twilight.decode(), r'- `cites` "paragraph \(b\) of this section" -- `resolvedBy` '
                                            r'\[`anti-collision-lighting`\]\(\d{3}-anti-collision-lighting\.md\)\n')

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
        self.assertEqual(code, factory.NOT_VERIFIED, log)
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
    assert args[args.index("--json") + 1] == "number,title,body,labels"
    print(json.dumps([dict(i, labels=[{{"name": n}} for n in i.get("labels", [])])
                      for i in issues[:int(args[args.index("--limit") + 1])]]))
elif args[:2] == ["issue", "create"]:
    assert args[args.index("--body-file") + 1] == "-"
    number = max([i["number"] for i in issues] + [0]) + 1
    issues.append({{"number": number, "title": args[args.index("--title") + 1], "body": sys.stdin.read()}})
    save()
    print("https://github.com/example/engine/issues/%d" % number)
elif args[:2] == ["issue", "edit"]:
    (issue,) = [i for i in issues if i["number"] == int(args[2])]
    if "--body-file" in args:
        assert args[args.index("--body-file") + 1] == "-"
        issue["title"] = args[args.index("--title") + 1]
        issue["body"] = sys.stdin.read()
    labels = set(issue.get("labels", []))
    for i, a in enumerate(args):
        if a == "--add-label":
            if os.environ.get("GH_STUB_MISSING_LABELS"):
                sys.exit("could not add label: '%s' not found" % args[i + 1])
            labels.add(args[i + 1])
        elif a == "--remove-label":
            labels.discard(args[i + 1])
    issue["labels"] = sorted(labels)
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


class TestCrossReferencesRendered(unittest.TestCase):
    """The Cross-references section, rendered alone: deterministic and exact."""

    CITES = "except as provided in paragraph (d) of this section"
    REASON = "Paragraph (d) of this section is outside the slice mapped here."

    def listed(self):
        listed = entries()
        listed[1]["crossReferences"] = [{"cites": self.CITES, "resolvedBy": "first"},
                                        {"cites": 'as in "Fig. 1"', "unmapped": self.REASON}]
        return listed

    def test_rendering_is_deterministic_and_exact(self):
        first = backlog.render(self.listed(), CONTEXT)
        self.assertEqual(first, backlog.render(self.listed(), CONTEXT))
        self.assertIn("## Cross-references\n\n`crossReferences` -- each pointer the evidence makes, and the entry or "
                      "the recorded reason it resolves to:\n\n"
                      f'- `cites` "{self.CITES}" -- `resolvedBy` [`first`](001-first.md)\n'
                      f'- `cites` "as in \\"Fig. 1\\"" -- `unmapped`: "{self.REASON}"\n\n## Acceptance criteria',
                      first["002-second.md"])
        self.assertIn("## Cross-references\n\n`crossReferences` -- each pointer the evidence makes, and the entry or "
                      "the recorded reason it resolves to:\n\n- none\n\n", first["001-first.md"])


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
        self.assertIn("built before this item:\n\n- #1\n", self.issues()[1]["body"])
        self.assertNotIn(".md)", self.issues()[1]["body"])
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
        self.assertNotIn("- #1\n", self.issues()[1]["body"])
        self.assertEqual(self.issues()[1]["body"], self.body("002-second.md"))
        self.assertIn("0 created, 1 updated, 0 adopted, 1 unchanged", log)

    def test_a_cross_reference_resolved_where_it_was_unmapped_updates_the_body(self):
        """FaaPart107 4.0.0's "paragraph (b)": only the resolution moves, and the issue must show it."""
        before = entries()
        before[1]["crossReferences"] = [{"cites": "as in paragraph (b)", "unmapped": "Nothing maps (b) yet."}]
        self.emit(before)
        self.create()
        self.writes()
        self.assertIn('- `cites` "as in paragraph (b)" -- `unmapped`: "Nothing maps (b) yet."\n',
                      self.issues()[1]["body"])
        after = entries()
        after[1]["crossReferences"] = [{"cites": "as in paragraph (b)", "resolvedBy": "first"}]
        self.emit(after)
        code, log = self.create()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.writes(), [["issue", "edit", "2"]])
        self.assertIn('- `cites` "as in paragraph (b)" -- `resolvedBy` #1\n', self.issues()[1]["body"])
        self.assertNotIn("unmapped", self.issues()[1]["body"])
        self.assertIn("0 created, 1 updated, 0 adopted, 1 unchanged", log)

    def test_item_links_become_issue_references_in_bodies_and_stay_file_links_in_files(self):
        """Matched by marker, not number: an unrelated issue #1 makes item 001 issue #2, and links say so."""
        linked = entries()
        linked[0]["crossReferences"] = [{"cites": "as in the second", "resolvedBy": "second"}]
        self.emit(linked)
        files = {name: self.body(name) for name in ("001-first.md", "002-second.md")}
        self.seed([(1, "unrelated", "text")])
        code, log = self.create()
        self.assertEqual(code, 0, log)
        # first is created before second has a number, so it is edited once second has one.
        self.assertEqual(self.writes(), [["issue", "create"], ["issue", "create"], ["issue", "edit", "2"]])
        self.assertIn("linked    #2 first: First", log)
        self.assertIn("2 created, 0 updated, 0 adopted, 0 unchanged", log)
        first, second = self.issues()[1:]
        self.assertEqual((first["number"], second["number"]), (2, 3))
        self.assertIn('- `cites` "as in the second" -- `resolvedBy` #3\n', first["body"])
        self.assertIn("built before this item:\n\n- #2\n", second["body"])
        self.assertNotIn(".md)", first["body"] + second["body"])
        self.assertEqual(first["body"], files["001-first.md"].replace("[`second`](002-second.md)", "#3"))
        self.assertEqual({name: self.body(name) for name in files}, files)
        self.assertIn("[`second`](002-second.md)", files["001-first.md"])
        code, log = self.create()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.writes(), [])
        self.assertIn("0 created, 0 updated, 0 adopted, 2 unchanged", log)

    def test_a_link_to_an_item_without_an_issue_stays_a_file_link(self):
        body = self.body("002-second.md")
        self.assertEqual(backlog.link_issues(body, {"001-first.md": "first"}, {}), body)
        self.assertEqual(backlog.link_issues(body, {"001-first.md": "other"}, {"first": 5, "other": 6}), body)
        self.assertIn("- #5\n", backlog.link_issues(body, {"001-first.md": "first"}, {"first": 5}))

    def test_line_endings_and_trailing_space_github_adds_are_not_a_change(self):
        first, second = self.body("001-first.md"), self.body("002-second.md")
        second = second.replace("[`first`](001-first.md)", "#7")
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
        # Issues to create are created first: the others' bodies link them by number.
        self.assertEqual(self.writes(), [["issue", "create"], ["issue", "edit", "4"]])
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

    def test_without_provenance_a_body_carrying_an_attribution_is_refused(self):
        item = os.path.join(self.engine, "backlog", "001-first.md")
        with open(item, "a", encoding="utf-8") as handle:
            handle.write("\n" + backlog.ATTRIBUTION_HEADING + "\nSomeone's statement.\n")
        code, log = self.create()
        self.assertEqual(code, 1, log)
        self.assertIn("attributes a corpus's text (0023)", log)
        self.assertEqual(self.writes(), [])


SRD = os.path.join(REPO, "examples", "srd-52-combat")
with open(os.path.join(SRD, "corpus-manifest.json"), encoding="utf-8") as _handle:
    SRD_LICENCE = json.load(_handle)["corpora"][0]["licence"]
# The statement as the SRD's Legal Information page words it, restated here rather than parsed from the
# manifest, so a parser that kept the wrong part of the licence cannot pass.
SRD_STATEMENT = ("This work includes material from the System Reference Document 5.2.1 (“SRD 5.2.1”) by Wizards of "
                 "the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the "
                 "Creative Commons Attribution 4.0 International License, available at "
                 "https://creativecommons.org/licenses/by/4.0/legalcode.")


class TestAttribution(unittest.TestCase):
    """Decision 0023: a backlog quoting an attribution-requiring corpus (the SRD, CC-BY-4.0) carries the
    attribution in every item and every issue body; a public-domain corpus's backlog carries nothing extra."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.nupkg = {}
        for key, directory, corpus, name in (("srd", SRD, "srd-5.2.1.txt", "Srd52Combat"),
                                             ("hoyle", os.path.join(REPO, "examples", "hoyle-backgammon"), "hoyle.txt",
                                              "HoyleBackgammon")):
            out = os.path.join(cls.tmp, "pkg-" + key)
            subprocess.run([sys.executable, PACK, directory, "--out", out], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (nupkg,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
            cls.nupkg[key] = (os.path.join(out, nupkg), os.path.join(directory, corpus), name)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def setUp(self):
        self.work = tempfile.mkdtemp(dir=self.tmp)
        self.state = os.path.join(self.work, "issues.json")
        gh = os.path.join(self.work, "gh")
        with open(gh, "w", encoding="utf-8") as handle:
            handle.write(STUB.format(python=sys.executable))
        os.chmod(gh, 0o755)
        for key, value in (("GH_STUB_STATE", self.state), ("FACTORY_GH", gh),
                           ("NUGET_PACKAGES", os.path.join(self.work, "empty-nuget"))):
            self.addCleanup(os.environ.__setitem__, key, os.environ[key]) if key in os.environ else \
                self.addCleanup(os.environ.pop, key, None)
            os.environ[key] = value

    def produce(self, key):
        nupkg, corpus, name = self.nupkg[key]
        engine = os.path.join(self.work, "engine-" + key)
        code, log = run(["produce", "--package", nupkg, "--corpus", corpus, "--name", name, "--out", engine,
                         "--allow-dirty", "--no-verify"])
        # `--no-verify` ends NOT VERIFIED (3), never 0 (tools/factory/__main__.py).
        self.assertEqual(code, factory.NOT_VERIFIED, log)
        return engine

    def create(self, engine, *extra):
        return run(["backlog", "--create", "--repo", "example/engine", "--dir", engine, *extra])

    def calls(self):
        path = self.state + ".calls"
        return open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []

    def test_the_manifest_licence_is_read_for_its_statement(self):
        credit = backlog.attribution({"sourceId": "srd-5.2.1", "licence": SRD_LICENCE})
        self.assertEqual(credit, {"sourceId": "srd-5.2.1", "terms": "CC-BY-4.0", "statement": SRD_STATEMENT})
        for licence in ("public-domain-us-government",
                        "public-domain-underlying-work; Project Gutenberg trademark terms apply to the edition"):
            self.assertIsNone(backlog.attribution({"sourceId": "s", "licence": licence}))
        for licence in ("CC-BY-4.0", "CC-BY-SA-4.0; credit the authors", "attribution: see the colophon", "", None):
            with self.subTest(licence=licence), self.assertRaises(backlog.BacklogError):
                backlog.attribution({"sourceId": "s", "licence": licence})

    def test_every_srd_item_and_the_index_carry_the_statement_verbatim(self):
        engine = self.produce("srd")
        files = backlog_files(engine)
        self.assertGreater(len(files), 2)
        for name, data in files.items():
            text = data.decode("utf-8")
            self.assertEqual(text.count(SRD_STATEMENT), 1, name)
            self.assertIn(backlog.ATTRIBUTION_HEADING, text, name)
            self.assertIn("CC-BY-4.0", text, name)
            self.assertIn("`LICENCE.txt` inside RulesFactory.Maps.Srd52Combat 2.0.0", text, name)
        with zipfile.ZipFile(self.nupkg["srd"][0]) as archive:
            self.assertIn("LICENCE.txt", archive.namelist(), "the pointer names a file the package carries")

    def test_a_public_domain_backlog_carries_no_attribution(self):
        engine = self.produce("hoyle")
        for name, data in backlog_files(engine).items():
            self.assertNotIn(backlog.ATTRIBUTION_HEADING, data.decode("utf-8"), name)
        code, log = self.create(engine, "--package", self.nupkg["hoyle"][0])
        self.assertEqual(code, 0, log)
        self.assertNotIn("(0023)", log)

    def test_create_posts_bodies_that_carry_the_statement(self):
        engine = self.produce("srd")
        code, log = self.create(engine, "--package", self.nupkg["srd"][0])
        self.assertEqual(code, 0, log)
        self.assertIn("bodies carry the attribution srd-5.2.1's licence (CC-BY-4.0) requires (0023)", log)
        with open(self.state, encoding="utf-8") as handle:
            issues = json.load(handle)
        self.assertEqual(len(issues), len(backlog_files(engine)) - 1)
        for issue in issues:
            self.assertIn(SRD_STATEMENT, issue["body"], issue["title"])

    def test_create_refuses_a_body_without_the_statement_before_any_call(self):
        engine = self.produce("srd")
        item = sorted(n for n in os.listdir(os.path.join(engine, "backlog")) if n != "README.md")[1]
        path = os.path.join(engine, "backlog", item)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace(SRD_STATEMENT, "(attribution removed)"))
        code, log = self.create(engine, "--package", self.nupkg["srd"][0])
        self.assertEqual(code, 1, log)
        self.assertIn(f"do not carry its statement verbatim: {item}", log)
        self.assertEqual(self.calls(), [], "gh was never called")

    def test_create_refuses_when_the_package_that_says_whether_attribution_is_needed_is_absent(self):
        engine = self.produce("srd")
        code, log = self.create(engine)  # NUGET_PACKAGES is an empty folder, and nothing is downloaded
        self.assertEqual(code, 1, log)
        self.assertIn("not a local file or in the NuGet global packages folder", log)
        self.assertEqual(self.calls(), [])

    def test_create_refuses_a_package_other_than_the_one_provenance_records(self):
        engine = self.produce("srd")
        code, log = self.create(engine, "--package", self.nupkg["hoyle"][0])
        self.assertEqual(code, 1, log)
        self.assertIn("is not the map provenance.json records", log)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()


class TestLabels(CreateCase):
    """One state label and one risk label per issue (#154, decision 0029)."""

    def policy(self, **overrides):
        os.makedirs(os.path.join(self.engine, ".github"), exist_ok=True)
        # The labels the factory ships in the policy it writes, so this reads the defaults from
        # the one place they are decided rather than restating them (#188).
        labels = dict(json.loads(factory.generate.agent_policy())["labels"], **overrides)
        with open(os.path.join(self.engine, ".github", "agent-policy.json"), "w", encoding="utf-8") as handle:
            json.dump({"schemaVersion": 1, "labels": labels}, handle, indent=2)

    def labels(self):
        return {issue["number"]: set(issue.get("labels", [])) for issue in self.issues()}

    def set_labels(self, number, names):
        issues = self.issues()
        (issue,) = [i for i in issues if i["number"] == number]
        issue["labels"] = sorted(names)
        with open(self.state, "w", encoding="utf-8") as handle:
            json.dump(issues, handle)

    def test_a_dependency_still_to_build_blocks_its_dependant(self):
        self.policy()
        code, output = self.create()
        self.assertEqual(code, 0, output)
        # `first` depends on nothing; `second` depends on `first`, which has an item of its own,
        # so it is not built yet.
        self.assertEqual(self.labels(), {1: {"state:ready", "risk:normal"},
                                         2: {"state:blocked", "risk:normal"}})

    def test_a_dependency_that_is_built_makes_its_dependant_ready(self):
        self.policy()
        self.assertEqual(self.create()[0], 0)
        # `first` is implemented, so it leaves the backlog, and nothing `second` waits on remains.
        built = entries()
        built[0]["status"] = "implemented"
        built[0]["implementedIn"] = "Rules/First.cs"
        built[0]["tests"] = [{"name": "First_Resolves", "mutation": "return null"}]
        self.emit(built)
        code, output = self.create()
        self.assertEqual(code, 0, output)
        self.assertIn("state:ready", self.labels()[2])
        self.assertNotIn("state:blocked", self.labels()[2])

    def test_needs_decision_survives_a_sync(self):
        self.policy()
        self.assertEqual(self.create()[0], 0)
        # A person judged that this one asks a question the corpus does not settle.
        self.set_labels(2, ["state:needs-decision", "risk:normal"])
        code, output = self.create()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.labels()[2], {"state:needs-decision", "risk:normal"},
                         "a sync re-imposed a state a person had overridden")

    def test_risk_is_never_lowered(self):
        self.policy()
        self.assertEqual(self.create()[0], 0)
        self.set_labels(1, ["state:ready", "risk:independent-review"])
        self.assertEqual(self.create()[0], 0)
        self.assertEqual(self.labels()[1], {"state:ready", "risk:independent-review"})

    def test_a_state_that_no_longer_applies_is_removed(self):
        self.policy()
        self.assertEqual(self.create()[0], 0)
        self.set_labels(1, ["state:blocked", "risk:normal"])
        self.assertEqual(self.create()[0], 0)
        self.assertEqual(self.labels()[1], {"state:ready", "risk:normal"},
                         "an issue cannot carry two state labels")

    def test_the_label_strings_are_the_engine_s(self):
        self.policy(ready="ready-to-work", normalRisk="risk/ordinary")
        code, output = self.create()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.labels()[1], {"ready-to-work", "risk/ordinary"})

    def test_an_engine_with_no_policy_is_synchronised_without_labels(self):
        code, output = self.create()
        self.assertEqual(code, 0, output)
        self.assertIn("no .github/agent-policy.json", output)
        self.assertEqual(self.labels(), {1: set(), 2: set()})

    def test_a_policy_missing_a_label_is_refused(self):
        os.makedirs(os.path.join(self.engine, ".github"), exist_ok=True)
        with open(os.path.join(self.engine, ".github", "agent-policy.json"), "w", encoding="utf-8") as handle:
            json.dump({"schemaVersion": 1, "labels": {"ready": "state:ready"}}, handle)
        code, output = self.create()
        self.assertEqual(code, 1, output)
        self.assertIn("names no blocked", output)

    def test_a_policy_whose_labels_collide_is_refused(self):
        # `label_plan` computes a state set and a risk set from the five strings, so two keys that
        # share one make an issue ready and blocked at once, or strip its risk label when its state
        # moves. Refused before any issue is written, by the same check `rails --check` reads the
        # policy through (#188).
        for overrides, expected in (({"blocked": "state:ready"}, "ready and blocked are both 'state:ready'"),
                                    ({"independentRisk": "state:blocked"},
                                     "blocked and independentRisk are both 'state:blocked'")):
            self.policy(**overrides)
            code, output = self.create()
            self.assertEqual(code, 1, output)
            self.assertIn(expected, output)
            self.assertIn("lose its risk label when its state changed", output)

    def test_a_label_that_does_not_exist_in_the_repository_is_reported(self):
        self.policy()
        os.environ["GH_STUB_MISSING_LABELS"] = "1"
        self.addCleanup(os.environ.pop, "GH_STUB_MISSING_LABELS", None)
        code, output = self.create()
        self.assertEqual(code, 1, output)
        self.assertIn("not dispatchable", output)
        self.assertIn("factory rails --apply", output)

    def test_a_second_run_relabels_nothing(self):
        self.policy()
        self.assertEqual(self.create()[0], 0)
        self.writes()
        code, output = self.create()
        self.assertEqual(code, 0, output)
        self.assertIn("0 issue(s) relabelled", output)
        self.assertEqual(self.writes(), [], "a second run in a row writes nothing")

    def test_the_state_is_in_the_item_file_a_reader_can_see(self):
        self.policy()
        self.assertEqual(self.create()[0], 0)
        self.assertIn("<!-- rules-factory-state: blocked -->", self.body("002-second.md"))
        self.assertIn("<!-- rules-factory-state: ready -->", self.body("001-first.md"))
