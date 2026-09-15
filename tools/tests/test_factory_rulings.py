#!/usr/bin/env python3
"""Owner's rulings (decision 0027): an engine's answer to part of an unresolved question, held in its
overlay, checked by the factory, and never merged into the map.

What is asserted here, without a .NET SDK:

  * `rulings.problems` refuses each thing 0027 refuses, one test per refusal, against the real
    hoyle-backgammon map and its `bearing-off-eligible` question; and passes the worked example;
  * `factory produce` refuses an overlay that breaks 0027 before anything is written, and on the
    worked example generates `Rulings.g.cs`, records the rulings in provenance.json and says in its
    output which answers are the owner's; withdrawing the last ruling removes the generated file;
  * the gate: `map-overlay.py merge` refuses the same overlays, passes the worked example without
    carrying `rulings` or `declines` into the merged map, and prints the rulings; `engine-gate.py
    regenerate` passes; an engine with no rulings generates exactly what it did before;
  * provenance: an edited decision record is a mismatch until the engine is produced again.

That `Rulings.g.cs` compiles, warning-free, beside an engine's own use of it, is
scripts/validate-engine.sh's to show, on the SDK the kernel pins.

Run: python3 -m unittest discover -s tools/tests
"""
import copy
import importlib.util
import io
import json
import os
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
HOYLE = os.path.join(REPO, "examples", "hoyle-backgammon")
HOYLE_TXT = os.path.join(HOYLE, "hoyle.txt")
NAME = "HoyleBackgammon"
RULINGS_CS = f"src/{NAME}/Generated/Rulings.g.cs"
RECORD = "docs/decisions/0009-owner-rulings-are-ruleset-version-five.md"

sys.path.insert(0, FACTORY)
import rulings  # noqa: E402

_spec = importlib.util.spec_from_file_location("factory_main_rulings", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)

with open(os.path.join(HOYLE, "corpus-map.json"), encoding="utf-8") as _handle:
    MAP = json.load(_handle)

QUESTION = next(e for e in MAP["entries"] if e["id"] == "bearing-off-eligible")["ambiguity"]["question"]
# The question's two parts, as an engine divides it: everything before "Nor does it say", and the rest.
FIRST_PART = QUESTION[:QUESTION.index("Nor does it say")].strip()
SECOND_PART = QUESTION[QUESTION.index("Nor does it say"):]
RULED_TEST = "MustPlayWholeThrowEntryPointTests.A_number_left_after_the_last_man_comes_home_bears_off_naming_the_owners_ruling"
DECLINE_TEST = "BearingOffEligibilityTests.A_man_re_entered_after_bearing_off_began_is_the_case_the_corpus_does_not_settle"


def worked_example():
    """The overlay item `bearing-off-eligible` carries once Brandon's ruling of 2026-09-15 moves into it."""
    return {"bearing-off-eligible": {
        "status": "implemented",
        "implementedIn": {"ruleset": "hoyle-1909-backgammon", "version": 5},
        "tests": [
            {"test": "BearingOffEligibilityTests.Fourteen_home_and_one_out_does_not", "mutation": "m1"},
            {"test": DECLINE_TEST, "mutation": "m2"},
            {"test": RULED_TEST, "mutation": "m3"},
        ],
        "rulings": [{
            "id": "bearing-off-eligible/2",
            "span": SECOND_PART,
            "answer": "Yes: once a player's first number brings his last man home, the number left bears off.",
            "ruledBy": "Brandon",
            "ruledOn": "2026-09-15",
            "record": RECORD,
            "tests": [RULED_TEST],
        }],
        "declines": [{"span": FIRST_PART, "tests": [DECLINE_TEST]}],
    }}


def write_record(root, relative=RECORD, text="# 0009\n\nBrandon ruled.\n"):
    path = os.path.join(root, *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def pack(map_dir, out):
    subprocess.run([sys.executable, PACK, map_dir, "--out", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (name,) = [n for n in os.listdir(out) if n.endswith(".nupkg")]
    return os.path.join(out, name)


class TestTheWorkedExampleIsInTheMap(unittest.TestCase):
    def test_both_spans_are_in_the_current_question_once(self):
        self.assertTrue(FIRST_PART.startswith("The stage begins 'when either player"))
        self.assertTrue(FIRST_PART.endswith("must first bring every man home again."))
        self.assertTrue(SECOND_PART.startswith("Nor does it say when within a throw the stage begins."))
        self.assertTrue(SECOND_PART.endswith("so it does not decide the case."))
        self.assertEqual(QUESTION.count(SECOND_PART), 1)
        self.assertEqual(QUESTION.count(FIRST_PART), 1)


class TestProblems(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        write_record(self.root)

    def check(self, overlay, root="engine", package=None):
        return rulings.problems(package or MAP, overlay, self.root if root == "engine" else root)

    def refused(self, change, *expected):
        overlay = worked_example()
        change(overlay["bearing-off-eligible"])
        found = self.check(overlay)
        self.assertTrue(found, "the overlay was accepted")
        text = "\n".join(found)
        for fragment in expected:
            self.assertIn(fragment, text)
        return found

    def ruling(self, item):
        return item["rulings"][0]

    def test_the_worked_example_passes(self):
        self.assertEqual(self.check(worked_example()), [])

    def test_an_overlay_without_rulings_is_not_examined(self):
        self.assertEqual(self.check({"player-count": {"status": "mapped"}, "x": "not an object"}), [])

    def test_a_ruling_on_an_entry_that_is_not_unresolved(self):
        overlay = worked_example()
        item = overlay.pop("bearing-off-eligible")
        overlay["legal-destination"] = item  # fate: decision
        self.assertIn("fate: decision", "\n".join(self.check(overlay)))
        overlay = {"player-count": item}  # clear: no ambiguity at all
        self.assertIn("records no ambiguity", "\n".join(self.check(overlay)))

    def test_a_ruling_on_an_entry_the_map_moved_to_decision(self):
        package = copy.deepcopy(MAP)
        entry = next(e for e in package["entries"] if e["id"] == "bearing-off-eligible")
        entry["ambiguity"] = {"question": entry["ambiguity"]["question"], "fate": "decision",
                              "decision": "docs/decisions/0099-x.md"}
        self.assertIn("withdraws the ruling", "\n".join(self.check(worked_example(), package=package)))

    def test_a_ruling_on_an_entry_that_is_not_implemented(self):
        self.refused(lambda item: item.update(status="mapped"), "must be `implemented`")

    def test_a_span_not_in_the_current_question(self):
        self.refused(lambda item: self.ruling(item).update(span="Nor does it say when the stage ends."),
                     "is not in the entry's current `ambiguity.question`")

    def test_a_question_the_map_rewrote(self):
        package = copy.deepcopy(MAP)
        entry = next(e for e in package["entries"] if e["id"] == "bearing-off-eligible")
        entry["ambiguity"]["question"] = entry["ambiguity"]["question"].replace("within a throw", "during a throw")
        found = "\n".join(self.check(worked_example(), package=package))
        self.assertIn("bearing-off-eligible: ruling 'bearing-off-eligible/2': span", found)
        self.assertIn("If the map rewrote the question", found)

    def test_a_span_that_occurs_twice(self):
        self.refused(lambda item: self.ruling(item).update(span="the text does not say whether"), "occurs 2 times")

    def test_overlapping_spans(self):
        self.refused(lambda item: item["declines"][0].update(span="Nor does it say when within a throw"),
                     "quote overlapping spans")

    def test_two_rulings_on_one_part(self):
        def twice(item):
            second = dict(self.ruling(item), id="bearing-off-eligible/again", span="the number left is played")
            item["rulings"].append(second)
        self.refused(twice, "quote overlapping spans")

    def test_each_missing_field(self):
        for field in rulings.RULING_FIELDS:
            with self.subTest(field=field):
                self.refused(lambda item: self.ruling(item).pop(field), f"lacks {field}")

    def test_a_field_a_ruling_does_not_have(self):
        self.refused(lambda item: self.ruling(item).update(questionPart=2), "carries questionPart")

    def test_blank_fields(self):
        for field in ("id", "answer", "ruledBy", "record"):
            with self.subTest(field=field):
                self.refused(lambda item: self.ruling(item).update({field: "  "}), f"`{field}` is blank")

    def test_an_id_that_does_not_name_its_entry(self):
        self.refused(lambda item: self.ruling(item).update(id="must-play-whole-throw/2"),
                     "the id must be `bearing-off-eligible/<slug>`")
        self.refused(lambda item: self.ruling(item).update(id="bearing-off-eligible/Part 2"),
                     "the id must be `bearing-off-eligible/<slug>`")

    def test_an_id_used_twice(self):
        overlay = worked_example()
        overlay["must-play-whole-throw"] = copy.deepcopy(overlay["bearing-off-eligible"])
        overlay["must-play-whole-throw"]["rulings"] = []  # empty is refused on its own
        self.assertIn("non-empty list", "\n".join(self.check(overlay)))
        item = worked_example()["bearing-off-eligible"]
        item["rulings"].append(dict(item["rulings"][0], span=FIRST_PART))
        item["declines"] = []
        self.assertIn("the id is used twice", "\n".join(self.check({"bearing-off-eligible": item})))

    def test_an_answer_that_is_not_brief(self):
        self.refused(lambda item: self.ruling(item).update(answer="Yes.\nBecause."), "stated briefly")
        self.refused(lambda item: self.ruling(item).update(answer="y" * (rulings.ANSWER_LIMIT + 1)), "stated briefly")

    def test_a_ruled_on_that_is_not_a_date(self):
        for value in ("15 September 2026", "2026-9-15", "2026-02-30", 20260915):
            with self.subTest(value=value):
                self.refused(lambda item: self.ruling(item).update(ruledOn=value), "not a YYYY-MM-DD date")

    def test_tests_absent_from_the_overlay_tests(self):
        self.refused(lambda item: self.ruling(item).update(tests=["Nobody.Wrote_this"]),
                     "'Nobody.Wrote_this', which is not among the overlay item's `tests`")
        self.refused(lambda item: self.ruling(item).update(tests=[]), "names no tests")
        self.refused(lambda item: item["declines"][0].update(tests=["Nobody.Wrote_this"]),
                     "decline 1 names test 'Nobody.Wrote_this'")

    def test_a_record_that_does_not_exist(self):
        self.refused(lambda item: self.ruling(item).update(record="docs/decisions/0010-missing.md"),
                     "is not a file in the engine")

    def test_a_record_outside_the_engine(self):
        for record in ("../elsewhere.md", "/etc/hosts", "docs\\decisions\\x.md", "./docs/x.md"):
            with self.subTest(record=record):
                self.refused(lambda item: self.ruling(item).update(record=record), f"record {record!r}")

    def test_the_record_is_not_looked_for_without_a_root(self):
        overlay = worked_example()
        overlay["bearing-off-eligible"]["rulings"][0]["record"] = "docs/decisions/0010-missing.md"
        self.assertEqual(rulings.problems(MAP, overlay, None), [])

    def test_rulings_without_declines(self):
        self.refused(lambda item: item.pop("declines"), "names rulings and no `declines`")

    def test_fully_ruled_is_declared_with_an_empty_declines(self):
        overlay = worked_example()
        item = overlay["bearing-off-eligible"]
        item["rulings"].append(dict(item["rulings"][0], id="bearing-off-eligible/1", span=FIRST_PART,
                                    answer="He goes on bearing off.", tests=[DECLINE_TEST]))
        item["declines"] = []
        self.assertEqual(self.check(overlay), [])
        self.assertIn("bearing-off-eligible: declared fully ruled", "\n".join(rulings.describe(overlay)))

    def test_declines_empty_without_a_ruling(self):
        def nothing_ruled(item):
            item.pop("rulings")
            item["declines"] = []
        self.refused(nothing_ruled, "names no ruling")

    def test_a_malformed_decline(self):
        self.refused(lambda item: item["declines"][0].update(reason="x"), "must carry exactly span, tests")
        self.refused(lambda item: item["declines"][0].pop("span"), "it lacks span")
        self.refused(lambda item: item.update(declines={"span": FIRST_PART}), "`declines` must be a list")

    def test_a_part_of_the_question_neither_ruled_nor_declined(self):
        self.refused(lambda item: item["declines"][0].update(span=FIRST_PART.split(". ")[0]),
                     "of the question unquoted", "If one of his men is hit")
        self.refused(lambda item: item.update(declines=[]), "of the question unquoted", "The stage begins")

    def test_a_part_the_map_added_to_the_question(self):
        package = copy.deepcopy(MAP)
        entry = next(e for e in package["entries"] if e["id"] == "bearing-off-eligible")
        entry["ambiguity"]["question"] += " Nor does it say whether a man borne off may return."
        found = "\n".join(self.check(worked_example(), package=package))
        self.assertIn("'Nor does it say whether a man borne off may return.' of the question unquoted", found)

    def test_declines_alone_are_checked_the_same_way(self):
        overlay = worked_example()
        overlay["bearing-off-eligible"].pop("rulings")
        self.assertIn("of the question unquoted", "\n".join(self.check(overlay)))
        overlay["bearing-off-eligible"]["declines"].append({"span": SECOND_PART, "tests": [RULED_TEST]})
        self.assertEqual(self.check(overlay), [])
        overlay["bearing-off-eligible"]["declines"][0]["span"] = "not in the question"
        self.assertIn("is not in the entry's current", "\n".join(self.check(overlay)))

    def test_collect_and_describe(self):
        overlay = worked_example()
        (collected,) = rulings.collect(overlay)
        self.assertEqual(collected["entry"], "bearing-off-eligible")
        self.assertEqual(collected["id"], "bearing-off-eligible/2")
        (line,) = rulings.describe(overlay)
        self.assertIn("owner's ruling bearing-off-eligible/2 on bearing-off-eligible, not the corpus", line)
        self.assertIn("ruled by Brandon on 2026-09-15", line)


class ProducedCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        cls.nupkg = pack(HOYLE, os.path.join(cls.shared, "feed"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = os.path.join(self.tmp, "engine")

    def run_factory(self, *argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = factory.main(list(argv))
        return code, buffer.getvalue()

    def produce(self):
        return self.run_factory("produce", "--package", self.nupkg, "--corpus", HOYLE_TXT, "--name", NAME,
                                "--out", self.out, "--allow-dirty", "--no-verify")

    def with_overlay(self, overlay, record=True):
        os.makedirs(self.out, exist_ok=True)
        if record:
            write_record(self.out)
        with open(os.path.join(self.out, "corpus-map.overlay.json"), "w", encoding="utf-8") as handle:
            json.dump(overlay, handle, indent=2)

    def read(self, relative):
        with open(os.path.join(self.out, *relative.split("/")), encoding="utf-8") as handle:
            return handle.read()

    def script(self, name, *args):
        done = subprocess.run([sys.executable, os.path.join(self.out, "scripts", name), *args], cwd=self.out,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return done.returncode, done.stdout


class TestProduce(ProducedCase):
    def test_the_worked_example_generates_the_registry_and_records_the_rulings(self):
        self.with_overlay(worked_example())
        code, output = self.produce()
        self.assertEqual(code, 0, output)
        self.assertIn("--- owner's ruling bearing-off-eligible/2 on bearing-off-eligible, not the corpus", output)
        generated = self.read(RULINGS_CS)
        self.assertIn("public sealed partial record OwnerRuling(string Id, string EntryId, string Span, string Answer, "
                      "string RuledBy, DateOnly RuledOn, string Record);", generated)
        self.assertIn("public static partial class OwnerRulings", generated)
        self.assertIn("public static OwnerRuling BearingOffEligible2 { get; } = new(\n"
                      "        \"bearing-off-eligible/2\",\n        \"bearing-off-eligible\",\n", generated)
        self.assertIn("new DateOnly(2026, 9, 15)", generated)
        self.assertIn("public static ImmutableArray<OwnerRuling> All { get; } = [BearingOffEligible2];", generated)
        self.assertNotIn("\\n", generated.split("namespace")[1].split("OwnerRulings")[0])
        with open(os.path.join(self.out, "provenance.json"), encoding="utf-8") as handle:
            record = json.load(handle)
        (ruling,) = record["rulings"]
        self.assertEqual((ruling["id"], ruling["entry"], ruling["ruledBy"], ruling["ruledOn"], ruling["record"]),
                         ("bearing-off-eligible/2", "bearing-off-eligible", "Brandon", "2026-09-15", RECORD))
        self.assertEqual(len(ruling["recordSha256"]), 64)
        self.assertIn(RULINGS_CS, {g["path"] for g in record["generated"]})
        self.assertNotIn("rulings", self.read(f"src/{NAME}/Generated/MapEntries.g.cs"))

    def test_an_engine_without_rulings_generates_no_registry_and_records_none(self):
        code, output = self.produce()
        self.assertEqual(code, 0, output)
        self.assertFalse(os.path.exists(os.path.join(self.out, *RULINGS_CS.split("/"))))
        with open(os.path.join(self.out, "provenance.json"), encoding="utf-8") as handle:
            self.assertNotIn("rulings", json.load(handle))

    def test_withdrawing_the_last_ruling_removes_the_registry(self):
        self.with_overlay(worked_example())
        self.assertEqual(self.produce()[0], 0)
        overlay = worked_example()
        overlay["bearing-off-eligible"].pop("rulings")
        overlay["bearing-off-eligible"]["declines"].append({"span": SECOND_PART, "tests": [RULED_TEST]})
        self.with_overlay(overlay)
        code, output = self.produce()
        self.assertEqual(code, 0, output)
        self.assertFalse(os.path.exists(os.path.join(self.out, *RULINGS_CS.split("/"))))
        code, output = self.script("engine-gate.py", "regenerate", *self.package_args())
        self.assertEqual(code, 0, output)

    def test_a_broken_ruling_is_refused_before_anything_is_written(self):
        overlay = worked_example()
        overlay["bearing-off-eligible"]["rulings"][0]["span"] = "not in the question"
        self.with_overlay(overlay)
        code, output = self.produce()
        self.assertEqual(code, 1, output)
        self.assertIn("breaks decision 0027", output)
        self.assertFalse(os.path.exists(os.path.join(self.out, "provenance.json")))

    def test_a_missing_record_is_refused(self):
        self.with_overlay(worked_example(), record=False)
        code, output = self.produce()
        self.assertEqual(code, 1, output)
        self.assertIn("is not a file in the engine", output)

    def test_an_edited_record_is_a_provenance_mismatch_until_produced_again(self):
        self.with_overlay(worked_example())
        self.assertEqual(self.produce()[0], 0)
        write_record(self.out, text="# 0009\n\nBrandon ruled, and the record changed.\n")
        code, output = self.run_factory("provenance", "--engine", self.out, "--package", self.nupkg)
        self.assertEqual(code, 1, output)
        self.assertIn("MISMATCH rulings:", output)
        self.assertEqual(self.produce()[0], 0)
        code, output = self.run_factory("provenance", "--engine", self.out, "--package", self.nupkg)
        self.assertEqual(code, 0, output)

    def package_args(self):
        import zipfile
        package_map = os.path.join(self.tmp, "package-map.json")
        package_manifest = os.path.join(self.tmp, "package-manifest.json")
        with zipfile.ZipFile(self.nupkg) as archive:
            with open(package_map, "wb") as handle:
                handle.write(archive.read("map/corpus-map.json"))
            with open(package_manifest, "wb") as handle:
                handle.write(archive.read("map/corpus-manifest.json"))
        version = json.load(open(os.path.join(HOYLE, "map-package.json"), encoding="utf-8"))["version"]
        return ("--package-map", package_map, "--package-manifest", package_manifest,
                "--package-id", "RulesFactory.Maps.HoyleBackgammon", "--package-version", version, "--name", NAME)


class TestGate(ProducedCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.produce()[0], 0)
        self.package_map = os.path.join(self.tmp, "package-map.json")
        self.merged = os.path.join(self.tmp, "merged.json")
        with open(self.package_map, "w", encoding="utf-8") as handle:
            json.dump(MAP, handle)

    def merge(self):
        return self.script("map-overlay.py", "merge", "--package-map", self.package_map,
                           "--overlay", os.path.join(self.out, "corpus-map.overlay.json"), "--out", self.merged)

    def test_the_worked_example_merges_without_its_rulings_and_is_reported(self):
        self.with_overlay(worked_example())
        code, output = self.merge()
        self.assertEqual(code, 0, output)
        self.assertIn("owner's ruling bearing-off-eligible/2 on bearing-off-eligible, not the corpus", output)
        with open(self.merged, encoding="utf-8") as handle:
            entry = next(e for e in json.load(handle)["entries"] if e["id"] == "bearing-off-eligible")
        self.assertNotIn("rulings", entry)
        self.assertNotIn("declines", entry)
        self.assertEqual(entry["status"], "implemented")
        self.assertEqual(entry["ambiguity"]["fate"], "unresolved", "the map still says the corpus does not settle it")

    def test_the_merge_refuses_what_produce_refuses(self):
        cases = {
            "not unresolved": lambda o: o.update({"player-count": o.pop("bearing-off-eligible")}),
            "span": lambda o: o["bearing-off-eligible"]["rulings"][0].update(span="nowhere"),
            "missing field": lambda o: o["bearing-off-eligible"]["rulings"][0].pop("ruledBy"),
            "test": lambda o: o["bearing-off-eligible"]["rulings"][0].update(tests=["No.Such"]),
            "record": lambda o: o["bearing-off-eligible"]["rulings"][0].update(record="docs/none.md"),
        }
        for label, change in cases.items():
            with self.subTest(label):
                overlay = worked_example()
                change(overlay)
                self.with_overlay(overlay)
                code, output = self.merge()
                self.assertEqual(code, 1, output)
                self.assertIn("owner's rulings (rules-factory decision 0027)", output)

    def test_regeneration_passes_with_rulings_and_fails_on_a_hand_edited_registry(self):
        self.with_overlay(worked_example())
        self.assertEqual(self.produce()[0], 0)
        args = TestProduce.package_args(self)
        code, output = self.script("engine-gate.py", "regenerate", *args)
        self.assertEqual(code, 0, output)
        path = os.path.join(self.out, *RULINGS_CS.split("/"))
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace('"Brandon"', '"the corpus"'))
        code, output = self.script("engine-gate.py", "regenerate", *args)
        self.assertEqual(code, 1, output)
        self.assertIn(f"{RULINGS_CS} differs from a fresh regeneration", output)


if __name__ == "__main__":
    unittest.main()
