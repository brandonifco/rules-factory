#!/usr/bin/env python3
"""The gate refuses a mutation nobody ran (#239).

`scripts/map-overlay.py merge` -- the recipe at tools/factory/recipe/map-overlay.py, which every
`factory produce` vendors into an engine -- took any non-empty string as a test's `mutation`. So
`"mutation": "PENDING"` passed an engine's gate, and AGENTS.md's "a test whose named mutation was
never observed to fail is a test nobody has watched fail" rested on a string nothing read.

What is asserted here, without a .NET SDK and without the factory:

  * every placeholder in the defined set is refused, and refused however it is cased, spaced or
    punctuated, and the empty-after-punctuation case with it;
  * and however it is spelled in Unicode: curly quotes, zero-width spaces, fullwidth forms,
    combining marks, and a Latin `O` written as a Cyrillic `О`;
  * the floor refuses what is too short to be a sentence -- each half of it independently, at its
    exact boundary -- and the refusal names the entry, the test, the reason, what a mutation is
    and `tools/re-produce.sh`;
  * **an implemented entry whose `tests` come from the package map is checked too**, because the
    rule reads the merge and not the overlay;
  * the real mutations of faa-part-107 and tax-121-principal-residence pass -- the shortest of
    each, by words and by characters, verbatim, because those are the ones a floor could refuse;
  * an entry whose status is not `implemented` is untouched by the rule, whatever it records;
  * `merge` and `check` both refuse, at the command line, with exit 1.

Run: python3 -m unittest discover -s tools/tests -t tools
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
TOOLS = os.path.dirname(os.path.dirname(HERE))
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

ZWSP = "\u200b"          # a format character (Cf) that hides inside a word and pads a length
CURLY = "\u201c{}\u201d"  # left and right double quotation marks (Pi, Pf)
FULLWIDTH_TODO = "\uff34\uff2f\uff24\uff2f"
CYRILLIC_TODO = "T\u041eDO"      # a Cyrillic capital O where the Latin O belongs
COMBINING_TODO = "T\u00d3DO"     # O with an acute accent

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
# sentence saying what was changed and what the test did. Each half of the floor has cases that
# only it refuses, so removing either half turns a test red.
TOO_SHORT = {
    # below both halves
    "m": "1 word, 1 character",
    "m1": "1 word, 2 characters",
    "changed": "1 word, 7 characters",
    "a b": "2 words, 3 characters",
    # below the word floor only: over twelve characters, under three words
    "comparison inverted": "2 words, 19 characters",
    "Registry.Resolve short-circuited": "2 words, 32 characters",
    # below the character floor only: three or more distinct words, under twelve characters
    "abc def ghi": "3 words, 11 characters",
    "1 2 3 4": "4 words, 7 characters",
    f"1 2 3{ZWSP * 7}": "4 characters of padding do not count",
    # exactly one under each boundary
    "abc def gh": "3 words, 10 characters",
}

# The exact boundary, and one character and one word above it: these pass, and a floor raised by
# one refuses them.
AT_THE_FLOOR = {
    "abc def ghij": "exactly 3 words and exactly 12 characters",
    "abcd efgh ijkl": "3 words, 14 characters",
    "one two three four": "4 words, 18 characters",
    # #241 review A: the floor counts words with repeats, so honest evidence about a variable
    # named `increment` is not refused for saying the word twice.
    "Increment `increment`; fails.": "3 words, 2 of them the same, 28 characters",
    "Registry.Resolve now resolves Registry.Resolve": "a repeated identifier in a real sentence",
}

# Two or more words, all the same word. This is where distinctness lives, and it is what refuses a
# repeated placeholder spelled in a script the set does not contain.
ONE_WORD_REPEATED = {
    "reversed reversed reversed reversed": "a plain repeat",
    " ".join([CYRILLIC_TODO] * 3): "a Cyrillic homoglyph, repeated -- refused here, not read as "
                                   "the word, because no confusable mapping is done",
    f"resolved{ZWSP} resolved{ZWSP} resolved": "zero-widths do not make three words of one",
}

# The reviewer's Unicode cases (#241 review): every one of these passed before normalisation. The
# expected reason matters as much as the refusal -- "is a placeholder" means normalisation read the
# word, where "too short" would mean only the floor caught it.
PLACEHOLDER = "is a placeholder, not a mutation"
TOO_SHORT_REASON = "is too short to be a mutation"
REPEATED = "is one word repeated, not a mutation"
UNICODE_PLACEHOLDERS = {
    " ".join([CURLY.format("TODO")] * 3): (PLACEHOLDER, "curly quotes around each word"),
    " ".join([f"TODO{ZWSP}"] * 3): (PLACEHOLDER, "a zero-width space inside each word"),
    " ".join([FULLWIDTH_TODO] * 3): (PLACEHOLDER, "fullwidth letters"),
    " ".join([COMBINING_TODO] * 3): (PLACEHOLDER, "a combining acute accent"),
    " ".join([CYRILLIC_TODO] * 3): (REPEATED,
                                    "a Cyrillic homoglyph: refused as one word repeated, not read "
                                    "as the word, because no confusable mapping is done"),
    CURLY.format("pending"): (PLACEHOLDER, "one curly-quoted placeholder"),
    f"TB{ZWSP}D": (PLACEHOLDER, "a zero-width space inside a placeholder"),
    FULLWIDTH_TODO: (PLACEHOLDER, "one fullwidth placeholder"),
    COMBINING_TODO: (PLACEHOLDER, "one accented placeholder"),
}


def overlay(mutation, status="implemented", entry="speed-limit"):
    return {entry: {"status": status,
                    "implementedIn": {"ruleset": "widget", "version": 1},
                    "tests": [{"test": "SpeedTests.The_limit_is_87_knots", "mutation": mutation}]}}


def problems(document, package=None):
    merged, found = overlay_tool.merge(package or PACKAGE, document)
    return found


def package_with(entry_id, item):
    """The package map, with `item`'s fields already on one of its entries: evidence upstream owns."""
    return {"corpus": "widget",
            "entries": [dict(e, **item) if e["id"] == entry_id else e for e in PACKAGE["entries"]]}


class TestThePlaceholderSetIsRefused(unittest.TestCase):
    def test_every_placeholder_form_is_refused_however_it_is_cased_or_punctuated(self):
        for mutation in PLACEHOLDERS:
            with self.subTest(mutation):
                found = problems(overlay(mutation))
                self.assertEqual(len(found), 1, f"{mutation!r} was accepted: {found}")
                self.assertIn("is a placeholder, not a mutation", found[0])

    def test_a_mutation_made_only_of_placeholder_words_is_refused(self):
        self.assertIn("is a placeholder", problems(overlay("todo -- pending, tbd"))[0])

    def test_a_placeholder_spelled_in_unicode_is_refused_for_the_right_reason(self):
        for mutation, (reason, why) in UNICODE_PLACEHOLDERS.items():
            with self.subTest(why):
                found = problems(overlay(mutation))
                self.assertEqual(len(found), 1, f"{mutation!r} ({why}) was accepted: {found}")
                self.assertIn(reason, found[0], f"{mutation!r} ({why}) was refused, but not as {reason!r}")

    def test_no_confusable_mapping_is_claimed(self):
        """A homoglyph is never read as the word it imitates. Repeating one spelling is refused
        whatever script it is in; mixing spellings to evade is not something this floor stops, and
        saying so here keeps the claim and the rule the same size (#241 review B)."""
        self.assertIn(REPEATED, overlay_tool.placeholder_problem(" ".join([CYRILLIC_TODO] * 3)))
        self.assertIsNone(overlay_tool.placeholder_problem(f"{CYRILLIC_TODO} and two more words"))
        mixed = f"TODO {CYRILLIC_TODO} TOD\u041e"
        self.assertIsNone(overlay_tool.placeholder_problem(mixed),
                          "three spellings of TODO pass, and the documentation says so")

    def test_a_placeholder_word_inside_a_real_mutation_is_not_refused(self):
        self.assertEqual(problems(overlay(
            "Handlers.SpeedLimit answered none where the map says pending review is unknown to "
            "it; this test went red.")), [])


class TestTheFloorRefusesWhatIsNotASentence(unittest.TestCase):
    def test_what_is_too_short_is_refused_and_told_how_short(self):
        for mutation, why in TOO_SHORT.items():
            with self.subTest(why):
                found = problems(overlay(mutation))
                self.assertEqual(len(found), 1, f"{mutation!r} ({why}) was accepted: {found}")
                self.assertIn("is too short to be a mutation", found[0])
                self.assertIn(f"at least {overlay_tool.MINIMUM_WORDS} words and "
                              f"{overlay_tool.MINIMUM_CHARACTERS} characters", found[0])

    def test_one_word_repeated_is_refused(self):
        for mutation, why in ONE_WORD_REPEATED.items():
            with self.subTest(why):
                found = problems(overlay(mutation))
                self.assertEqual(len(found), 1, f"{mutation!r} ({why}) was accepted: {found}")
                self.assertIn(REPEATED, found[0])

    def test_a_word_repeated_in_a_real_sentence_is_not_refused(self):
        """#241 review A: the counter-example. Incrementing a variable named `increment`."""
        self.assertEqual(problems(overlay("Increment `increment`; fails.")), [])

    def test_the_exact_boundary_passes(self):
        for mutation, why in AT_THE_FLOOR.items():
            with self.subTest(why):
                self.assertEqual(problems(overlay(mutation)), [], f"{mutation!r} ({why}) was refused")

    def test_the_floor_is_an_order_of_magnitude_below_the_shortest_real_mutation(self):
        """The threshold is a floor, not a bar. Stated as a test so lifting it is a deliberate act."""
        shortest = min(REAL.values(), key=lambda m: len(m.split()))
        self.assertLessEqual(overlay_tool.MINIMUM_WORDS * 5, len(shortest.split()))
        self.assertLessEqual(overlay_tool.MINIMUM_CHARACTERS * 10, len(min(REAL.values(), key=len)))

    def test_a_three_word_mutation_that_says_something_is_accepted(self):
        self.assertEqual(problems(overlay("inverted the comparison")), [])

    def test_a_missing_or_non_string_mutation_is_refused_too(self):
        for mutation, expected in ((None, "records no mutation at all"), (17, "records a int, which is not a mutation")):
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


class TestTheRuleReadsTheMergeNotTheOverlay(unittest.TestCase):
    """#241's review, blocking finding 1: `merge()` checked `overlay.items()`, so an implemented
    entry whose `status` and `tests` came from the **package map** was never looked at, and
    `"mutation": "PENDING"` survived into the merged map untouched."""

    IMPLEMENTED_UPSTREAM = {"status": "implemented",
                            "implementedIn": {"ruleset": "widget", "version": 1},
                            "tests": [{"test": "SpeedTests.The_limit_is_87_knots",
                                       "mutation": "PENDING"}]}

    def test_a_placeholder_in_the_package_map_is_refused_with_an_empty_overlay(self):
        found = problems({}, package=package_with("speed-limit", self.IMPLEMENTED_UPSTREAM))
        self.assertEqual(len(found), 1, found)
        self.assertIn("'speed-limit'", found[0])
        self.assertIn("is a placeholder", found[0])

    def test_the_refusal_says_the_evidence_is_upstream_and_not_this_engine_s(self):
        found = problems({}, package=package_with("speed-limit", self.IMPLEMENTED_UPSTREAM))
        self.assertIn("come from the map package, not this engine's overlay", found[0])
        self.assertIn("no re-produce here will change it", found[0])
        self.assertNotIn("Make the edit, watch the test fail, undo it, record it in "
                         "`overlay/speed-limit.json`", found[0])

    def test_the_same_placeholder_from_the_overlay_names_the_overlay(self):
        message = problems(overlay("PENDING"))[0]
        self.assertIn("record it in `overlay/speed-limit.json`, and re-produce", message)
        self.assertNotIn("come from the map package", message)

    def test_a_real_mutation_in_the_package_map_merges(self):
        upstream = dict(self.IMPLEMENTED_UPSTREAM,
                        tests=[{"test": "SpeedTests.The_limit_is_87_knots", "mutation": FAA_SHORTEST}])
        self.assertEqual(problems({}, package=package_with("speed-limit", upstream)), [])

    def test_an_overlay_that_overrides_upstream_tests_is_judged_on_the_overlay_s(self):
        """The overlay owns `tests` where it sets them (rule 3), so the merged entry is what counts."""
        package = package_with("speed-limit", self.IMPLEMENTED_UPSTREAM)
        self.assertEqual(problems(overlay(FAA_SHORTEST), package=package), [])
        self.assertEqual(len(problems(overlay("TBD"), package=package)), 1)


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
        self.assertIn("it cannot tell whether the edit was made or the test went red", self.message)


class TestTheCommandLineRefuses(unittest.TestCase):
    """The gate runs the file, not the function: both subcommands, exit 1, message on stderr.

    Laid out the way `factory produce` lays an engine out -- scripts/map-overlay.py with
    scripts/factory/rulings.py, overlay.py and compose.py beside it -- in a temporary directory
    that is removed after.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="map-overlay-mutation-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        scripts = os.path.join(self.tmp, "scripts")
        os.makedirs(os.path.join(scripts, "factory"))
        self.tool = os.path.join(scripts, "map-overlay.py")
        shutil.copy(RECIPE, self.tool)
        shutil.copy(os.path.join(FACTORY, "rulings.py"), os.path.join(scripts, "factory", "rulings.py"))
        shutil.copy(os.path.join(FACTORY, "overlay.py"), os.path.join(scripts, "factory", "overlay.py"))
        # Composing the restored packages before the overlay is applied is the recipe's, so the
        # module is beside it in a produced engine too (rules-factory 0067).
        shutil.copy(os.path.join(FACTORY, "compose.py"), os.path.join(scripts, "factory", "compose.py"))
        self.package_map = os.path.join(self.tmp, "package-map.json")
        self.overlay = os.path.join(self.tmp, "overlay")
        self.out = os.path.join(self.tmp, "corpus-map.json")
        with open(self.package_map, "w", encoding="utf-8") as handle:
            json.dump(PACKAGE, handle)

    def run_tool(self, mutation, *argv):
        os.makedirs(self.overlay, exist_ok=True)
        for entry_id, item in overlay(mutation).items():
            with open(os.path.join(self.overlay, f"{entry_id}.json"), "w", encoding="utf-8") as handle:
                json.dump(item, handle)
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
