#!/usr/bin/env python3
"""The placeholder rule is duplicated on purpose, and this is what keeps the two copies in step.

Two files decide whether a recorded `mutation` is evidence or an unfilled placeholder:

  * `tools/factory/recipe/map-overlay.py` -- the gate recipe every `factory produce` vendors into
    an engine, which refuses a placeholder in the merge the engine ships (#239);
  * `tools/mapvalidator/mutation.py` -- the checker a published map package carries and the one
    `scripts/validate.sh` runs over this repository's own maps, which refuses one *before* any
    engine merges the map (#240).

They are not one module, and cannot be. The recipe is a standard-library script that lives beside
an engine's own sources with no factory, no `mapcontract` and no `mapvalidator` on the path, so it
may import nothing of this repository's; 0032 forbids the reverse -- the map's verifier does not
import the factory's consumer code -- and `mapcontract`, which both may read, states what a field
means and judges nothing, where this judges. So the duplication is deliberate, and a deliberate
duplicate without a check on it is two rules that agree today.

What is asserted here:

  * every constant the rule reads is equal in both copies, named one by one so a diff names the
    constant that moved;
  * the five functions are the *same code*, compared as syntax trees with docstrings removed, so
    prose may differ between the two homes and behaviour may not -- and a rule added to one copy
    is a function or a branch the other does not have;
  * and, independently of the source comparison, both copies return the same verdict over one
    table of strings: the placeholder set however it is spelled, the Unicode cases, each half of
    the floor at its exact boundary, and the real mutations of both engines the factory has built.

Mutation: change MINIMUM_WORDS, or a line of `normalise`, in either copy alone. The constant test
names the constant; the tree test names the function; the table test names the string.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import ast
import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
FACTORY = os.path.join(TOOLS, "factory")
RECIPE = os.path.join(FACTORY, "recipe", "map-overlay.py")
CHECKER = os.path.join(TOOLS, "mapvalidator", "mutation.py")

sys.path.insert(0, TOOLS)   # `mapvalidator` and the `mapcontract` it reads
sys.path.insert(0, FACTORY)  # the recipe imports its vendored copy of rulings.py by that name
_spec = importlib.util.spec_from_file_location("map_overlay_recipe", RECIPE)
recipe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recipe)

from mapvalidator import mutation as checker  # noqa: E402  (after sys.path is set above)

# Every constant the rule reads, and all of them: SHARED_NAMES below is asserted to hold nothing
# else, so a constant added to one copy cannot escape this list by not being in it.
CONSTANTS = ("PLACEHOLDERS", "MINIMUM_WORDS", "MINIMUM_CHARACTERS", "INVISIBLE", "EDGE_CATEGORIES")
FUNCTIONS = ("an_edge", "strip_edges", "normalise", "words", "placeholder_problem")

ZWSP = "​"           # a format character (Cf) that hides inside a word and pads a length
CURLY = "“{}”"   # left and right double quotation marks (Pi, Pf)
FULLWIDTH_TODO = "ＴＯＤＯ"
CYRILLIC_TODO = "TОDO"   # a Cyrillic capital O where the Latin O belongs
COMBINING_TODO = "TÓDO"  # O with an acute accent

# One table, run through both copies. It is the union of what each copy's own tests cover, so a
# divergence shows up as a verdict, not only as a syntax tree.
TABLE = [
    # the set, as people type it
    "PENDING", "pending", "Pending.", "  PENDING  ", "pending!", "TBD", "tbd.", "TODO", "todo",
    "ToDo...", "none", "NONE", "n/a", "N/A.", "na", "scratch", "placeholder", "xxx", "unknown",
    "later", "fixme", "wip", "-", "?", "??", "...", "--", ".", "  -  ", "*", "()", "",
    # every distinct word a placeholder
    "TODO TBD", "pending / tbd", "none, n/a", "todo -- pending, tbd",
    # spelled in Unicode
    CURLY.format("pending"), f"TB{ZWSP}D", FULLWIDTH_TODO, COMBINING_TODO,
    " ".join([CURLY.format("TODO")] * 3), " ".join([f"TODO{ZWSP}"] * 3),
    " ".join([FULLWIDTH_TODO] * 3), " ".join([COMBINING_TODO] * 3),
    # one word repeated, including the homoglyph case no confusable mapping is done for
    "reversed reversed reversed reversed", " ".join([CYRILLIC_TODO] * 3),
    f"resolved{ZWSP} resolved{ZWSP} resolved",
    # too short, each half of the floor and each exact boundary
    "m", "m1", "changed", "a b", "comparison inverted", "Registry.Resolve short-circuited",
    "abc def ghi", "1 2 3 4", f"1 2 3{ZWSP * 7}", "abc def gh",
    # at the floor and above it
    "abc def ghij", "abcd efgh ijkl", "one two three four", "Increment `increment`; fails.",
    "Registry.Resolve now resolves Registry.Resolve", "inverted the comparison",
    # a homoglyph among real words, and three spellings of TODO: both pass, and both copies say so
    f"{CYRILLIC_TODO} and two more words", f"TODO {CYRILLIC_TODO} TODО",
    # a placeholder word inside honest evidence
    "Handlers.SpeedLimit answered none where the map says pending review is unknown to it; "
    "this test went red.",
    # verbatim from the two engines the factory has built: the shortest mutation each records
    "Handlers.SpeedLimit defaulted a missing statement to none held (`request.Waiver ?? "
    "WaiverStatement.NoneHeld(Speed.Regulation, \"the engine\")` for `Demand(request.Waiver, "
    "...)`); this test went red.",
    "IsEstablishedByDays held only at exactly the threshold (`days == Days` for `days >= "
    "Days`); this test went red and every other test of this entry stayed green.",
]


def _module(path):
    with open(path, encoding="utf-8") as handle:
        return ast.parse(handle.read(), filename=path)


def _definition(tree, name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            stripped = ast.FunctionDef(
                name=node.name, args=node.args, body=list(node.body), decorator_list=[],
                returns=None, type_comment=None, type_params=[])
            first = stripped.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                stripped.body = stripped.body[1:]
            return ast.dump(ast.fix_missing_locations(stripped))
    return None


class TestTheConstantsAreTheSame(unittest.TestCase):
    def test_each_constant_is_equal_in_both_copies(self):
        for name in CONSTANTS:
            with self.subTest(name):
                self.assertEqual(getattr(recipe, name), getattr(checker, name),
                                 f"{name} differs between tools/factory/recipe/map-overlay.py and "
                                 f"tools/mapvalidator/mutation.py; the duplication is deliberate, "
                                 f"the divergence is not")

    def test_neither_copy_has_a_constant_or_a_function_the_other_does_not(self):
        """The list above is not a sample. A sixth constant or a fourth refusal added to one copy
        and not the other is exactly the drift this file exists to catch, and it would pass every
        assertion that only walks a list of names both copies already share."""
        shared = set(CONSTANTS) | set(FUNCTIONS)
        for label, tree in (("map-overlay.py", _module(RECIPE)), ("mutation.py", _module(CHECKER))):
            names = set()
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    names.add(node.name)
                elif isinstance(node, ast.Assign):
                    names.update(t.id for t in node.targets if isinstance(t, ast.Name))
            missing = shared - names
            self.assertEqual(missing, set(), f"{label} does not define {sorted(missing)}")
        # The recipe is a whole tool and defines much else; the checker's module is the rule and
        # nothing else, so its top level is exactly the shared names.
        checker_names = {n.name for n in _module(CHECKER).body if isinstance(n, ast.FunctionDef)}
        checker_names |= {t.id for n in _module(CHECKER).body if isinstance(n, ast.Assign)
                          for t in n.targets if isinstance(t, ast.Name)}
        self.assertEqual(checker_names, shared,
                         "tools/mapvalidator/mutation.py defines something the recipe does not, "
                         "or has lost something it does; both copies must be the same rule")


class TestTheCodeIsTheSame(unittest.TestCase):
    def test_each_function_is_the_same_tree_with_its_docstring_removed(self):
        """Prose may differ -- each copy says where it is and what it is duplicated from -- and
        code may not. Comparing trees rather than bytes is what allows the first and forbids the
        second."""
        recipe_tree, checker_tree = _module(RECIPE), _module(CHECKER)
        for name in FUNCTIONS:
            with self.subTest(name):
                theirs, ours = _definition(recipe_tree, name), _definition(checker_tree, name)
                self.assertIsNotNone(theirs, f"the recipe defines no {name}()")
                self.assertIsNotNone(ours, f"mutation.py defines no {name}()")
                self.assertEqual(theirs, ours,
                                 f"{name}() is not the same code in tools/factory/recipe/"
                                 f"map-overlay.py and tools/mapvalidator/mutation.py")


class TestBothCopiesGiveTheSameVerdict(unittest.TestCase):
    """Independent of the source comparison: the rule is run, not read.

    The verdicts are compared, not merely their shape. `placeholder_problem` returns None or the
    reason, and the reason is what the two paths must agree on -- a string refused as "too short"
    by one copy and "a placeholder" by the other is two rules wearing one name.
    """

    def test_every_string_gets_the_same_verdict_from_both_copies(self):
        for text in TABLE:
            with self.subTest(repr(text)):
                self.assertEqual(recipe.placeholder_problem(text),
                                 checker.placeholder_problem(text))

    def test_the_normalisation_is_the_same(self):
        for text in TABLE:
            with self.subTest(repr(text)):
                self.assertEqual(recipe.normalise(text), checker.normalise(text))
                self.assertEqual(recipe.words(recipe.normalise(text)),
                                 checker.words(checker.normalise(text)))

    def test_the_table_exercises_all_three_refusals_and_the_passing_case(self):
        """A parity test over strings both copies accept proves nothing. This is the guard that
        the table still reaches every branch, so that a verdict comparison is a comparison."""
        reasons = [checker.placeholder_problem(t) for t in TABLE]
        for fragment in ("is a placeholder, not a mutation", "is one word repeated, not a mutation",
                         "is too short to be a mutation"):
            with self.subTest(fragment):
                self.assertTrue(any(r and fragment in r for r in reasons), fragment)
        self.assertTrue(any(r is None for r in reasons), "no string in the table is accepted")


if __name__ == "__main__":
    unittest.main()
