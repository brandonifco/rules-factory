#!/usr/bin/env python3
"""The gate refuses a mutation nobody ran (#239).

`scripts/map-overlay.py merge` -- the recipe at tools/factory/recipe/map-overlay.py, which every
`factory produce` vendors into an engine -- took any non-empty string as a test's `mutation`. So
`"mutation": "PENDING"` passed an engine's gate, and AGENTS.md's "a test whose named mutation was
never observed to fail is a test nobody has watched fail" rested on a string nothing read.

What is asserted here, without a .NET SDK and without the factory:

  * every placeholder in the defined set is refused, and refused however it is cased, spaced or
    punctuated, and the empty-after-punctuation case with it;
  * the floor refuses what is too short to be a sentence, and the refusal names the entry, the
    test, the reason, what a mutation is and `tools/re-produce.sh`;
  * the real mutations of faa-part-107 and tax-121-principal-residence pass -- the shortest of
    each, by words and by characters, verbatim, because those are the ones a floor could refuse;
  * an entry whose status is not `implemented` is untouched by the rule, whatever it records;
  * `merge` and `check` both refuse, at the command line, with exit 1.

Run: python3 -m unittest discover -s tools/tests
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
FACTORY = os.path.join(TOOLS, "factory")
RECIPE = os.path.join(FACTORY, "recipe", "map-overlay.py")

sys.path.insert(0, FACTORY)  # the recipe imports its vendored copy of rulings.py by that name
_spec = importlib.util.spec_from_file_location("map_overlay_recipe", RECIPE)
overlay_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(overlay_tool)

PACKAGE = {"corpus": "widget", "entries": [
    {"id": "speed-limit", "status": "mapped"},
    {"id": "altitude-limit", "status": "mapped"},
]}

# Verbatim from /home/brandon/faa-part-107 and /home/brandon/tax-121-principal-residence: the
# shortest mutation each engine records, by words and by characters. If a floor ever refuses one
# of these it is refusing honest work, which is the failure this rule must not have.
FAA_SHORTEST = (
    "Handlers.SpeedLimit defaulted a missing statement to none held (`request.Waiver ?? "
    "WaiverStatement.NoneHeld(Speed.Regulation, \"the engine\")` for `Demand(request.Waiver, "
    "...)`); this test went red.")
REAL = {
    "faa-part-107, shortest by words and by characters (20 words, 196 characters)": FAA_SHORTEST,
    "tax-121-principal-residence, shortest by words (24 words, 168 characters)":
        "Handlers.ResidenceMayInclude defaulted a missing date to the effective date "
        "(`request.SaleOrExchangeDate ?? Applicability.ApplicableFrom` for "
        "`request.SaleOrExchangeDate`), so `Registry.Resolve(\"residence-may-include\", "
        "RuleRequest.Empty)` resolved the list; this test went red.",
    "tax-121-principal-residence, shortest by characters (27 words, 159 characters)":
        "IsEstablishedByDays held only at exactly the threshold (`days == Days` for `days >= "
        "Days`); this test went red and every other test of this entry stayed green.",
}

# The set the rule names, each written the way somebody actually types it.
PLACEHOLDERS = [
    "PENDING", "pending", "Pending.", "  PENDING  ", "pending!",
    "TBD", "tbd.", "TBD:", "TODO", "todo", "ToDo...", "TODO!",
    "none", "NONE", "None.", "n/a", "N/A", "N/A.", "na", "NA",
    "scratch", "Scratch.", "placeholder", "PLACEHOLDER", "Placeholder.",
    "xxx", "XXX", "XXX.", "unknown", "Unknown", "UNKNOWN.",
    "later", "Later.", "fixme", "FIXME", "wip", "WIP",
    "-", "?", "??", "...", "--", ".", "  -  ", "*", "()",
    "TODO TBD", "pending / tbd", "none, n/a",
]

# Refused by the floor, not by the set: nothing here is a placeholder word, and none of it is a
# sentence saying what was changed and what the test did.
TOO_SHORT = ["m", "m1", "x", "changed", "return null", "inverted it", "broke it", "a b", "1 2 3 4"]


def overlay(mutation, status="implemented", entry="speed-limit"):
    return {entry: {"status": status,
                    "implementedIn": {"ruleset": "widget", "version": 1},
                    "tests": [{"test": "SpeedTests.The_limit_is_87_knots", "mutation": mutation}]}}


def problems(document):
    merged, found = overlay_tool.merge(PACKAGE, document)
    return found


class TestThePlaceholderSetIsRefused(unittest.TestCase):
    def test_every_placeholder_form_is_refused_however_it_is_cased_or_punctuated(self):
        for mutation in PLACEHOLDERS:
            with self.subTest(mutation):
                found = problems(overlay(mutation))
                self.assertEqual(len(found), 1, f"{mutation!r} was accepted: {found}")
                self.assertIn("is a placeholder, not a mutation", found[0])

    def test_a_mutation_made_only_of_placeholder_words_is_refused(self):
        self.assertIn("is a placeholder", problems(overlay("todo -- pending, tbd"))[0])

    def test_a_placeholder_word_inside_a_real_mutation_is_not_refused(self):
        self.assertEqual(problems(overlay(
            "Handlers.SpeedLimit answered none where the map says pending review is unknown to "
            "it; this test went red.")), [])


class TestTheFloorRefusesWhatIsNotASentence(unittest.TestCase):
    def test_what_is_too_short_is_refused_and_told_how_short(self):
        for mutation in TOO_SHORT:
            with self.subTest(mutation):
                found = problems(overlay(mutation))
                self.assertEqual(len(found), 1, f"{mutation!r} was accepted: {found}")
                self.assertIn("is too short to be a mutation", found[0])
                self.assertIn(f"at least {overlay_tool.MINIMUM_WORDS} words and "
                              f"{overlay_tool.MINIMUM_CHARACTERS} characters", found[0])

    def test_the_floor_is_an_order_of_magnitude_below_the_shortest_real_mutation(self):
        """The threshold is a floor, not a bar. Stated as a test so lifting it is a deliberate act."""
        shortest = min(REAL.values(), key=lambda m: len(m.split()))
        self.assertLessEqual(overlay_tool.MINIMUM_WORDS * 5, len(shortest.split()))
        self.assertLessEqual(overlay_tool.MINIMUM_CHARACTERS * 10, len(min(REAL.values(), key=len)))

    def test_a_three_word_mutation_that_says_something_is_accepted(self):
        self.assertEqual(problems(overlay("inverted the comparison")), [])

    def test_a_missing_or_non_string_mutation_is_refused_too(self):
        for mutation, expected in ((None, "records no mutation"), (17, "records a int")):
            with self.subTest(repr(mutation)):
                document = overlay("unused")
                if mutation is None:
                    document["speed-limit"]["tests"][0].pop("mutation")
                else:
                    document["speed-limit"]["tests"][0]["mutation"] = mutation
                self.assertIn(expected, problems(document)[0])


    def test_every_test_of_an_entry_is_read_not_only_the_first(self):
        document = overlay(FAA_SHORTEST)
        document["speed-limit"]["tests"].append(
            {"test": "SpeedTests.The_limit_declines_as_one_figure", "mutation": "TBD"})
        found = problems(document)
        self.assertEqual(len(found), 1, found)
        self.assertIn("'SpeedTests.The_limit_declines_as_one_figure'", found[0])


class TestTheRealMutationsStillPass(unittest.TestCase):
    def test_the_shortest_real_mutation_of_each_engine_is_accepted(self):
        for label, mutation in REAL.items():
            with self.subTest(label):
                self.assertEqual(problems(overlay(mutation)), [])


class TestAnEntryThatIsNotImplementedIsUnaffected(unittest.TestCase):
    def test_a_mapped_entry_recording_a_placeholder_merges(self):
        for status in ("mapped", "declined", "deferred"):
            with self.subTest(status):
                self.assertEqual(problems(overlay("PENDING", status=status)), [])

    def test_the_same_overlay_fails_the_moment_the_entry_is_implemented(self):
        self.assertEqual(problems(overlay("PENDING", status="mapped")), [])
        self.assertEqual(len(problems(overlay("PENDING", status="implemented"))), 1)

    def test_one_placeholder_among_implemented_entries_is_named_alone(self):
        document = overlay(FAA_SHORTEST)
        document.update(overlay("PENDING", entry="altitude-limit"))
        found = problems(document)
        self.assertEqual(len(found), 1, found)
        self.assertIn("'altitude-limit'", found[0])


class TestTheRefusalSaysWhatToDo(unittest.TestCase):
    def setUp(self):
        self.message = problems(overlay("PENDING"))[0]

    def test_it_names_the_entry_the_test_and_the_string(self):
        self.assertIn("'speed-limit'", self.message)
        self.assertIn("'SpeedTests.The_limit_is_87_knots'", self.message)
        self.assertIn("'PENDING'", self.message)

    def test_it_says_what_a_mutation_is(self):
        self.assertIn("the edit you made to this engine that turned that test red", self.message)

    def test_it_names_re_produce_and_says_the_check_is_a_floor_not_a_grader(self):
        self.assertIn("`tools/re-produce.sh`", self.message)
        self.assertIn("floor against an unfilled placeholder, not a judgement", self.message)


class TestTheCommandLineRefuses(unittest.TestCase):
    """The gate runs the file, not the function: both subcommands, exit 1, message on stderr.

    Laid out the way `factory produce` lays an engine out -- scripts/map-overlay.py with
    scripts/factory/rulings.py beside it -- in a temporary directory that is removed after.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="map-overlay-mutation-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        scripts = os.path.join(self.tmp, "scripts")
        os.makedirs(os.path.join(scripts, "factory"))
        self.tool = os.path.join(scripts, "map-overlay.py")
        shutil.copy(RECIPE, self.tool)
        shutil.copy(os.path.join(FACTORY, "rulings.py"), os.path.join(scripts, "factory", "rulings.py"))
        self.package_map = os.path.join(self.tmp, "package-map.json")
        self.overlay = os.path.join(self.tmp, "corpus-map.overlay.json")
        self.out = os.path.join(self.tmp, "corpus-map.json")
        with open(self.package_map, "w", encoding="utf-8") as handle:
            json.dump(PACKAGE, handle)

    def run_tool(self, mutation, *argv):
        with open(self.overlay, "w", encoding="utf-8") as handle:
            json.dump(overlay(mutation), handle)
        result = subprocess.run([sys.executable, self.tool, *argv, "--package-map", self.package_map,
                                 "--overlay", self.overlay],
                                capture_output=True, text=True,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        return result.returncode, result.stdout + result.stderr

    def test_merge_exits_one_and_writes_no_map(self):
        code, output = self.run_tool("PENDING", "merge", "--out", self.out)
        self.assertEqual(code, 1, output)
        self.assertIn("is a placeholder, not a mutation", output)
        self.assertFalse(os.path.exists(self.out), "a refused merge wrote a map anyway")

    def test_check_exits_one(self):
        code, output = self.run_tool("TBD", "check")
        self.assertEqual(code, 1, output)
        self.assertIn("is a placeholder, not a mutation", output)

    def test_a_real_mutation_merges(self):
        code, output = self.run_tool(next(iter(REAL.values())), "merge", "--out", self.out)
        self.assertEqual(code, 0, output)
        self.assertTrue(os.path.exists(self.out))


if __name__ == "__main__":
    unittest.main()
