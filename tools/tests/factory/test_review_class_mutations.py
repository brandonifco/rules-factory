#!/usr/bin/env python3
"""The review class decides what a reviewer is allowed not to be asked for, so it is attacked (0076, #595).

Each mutation below is a plausible defect in `tools/factory/reviewclass.py` that would let a change
skip a review it owes: a decision record that overrules another passed as a record, an edited
ruling passed as a typo, a claim that lowers what the diff computes, an exemption nobody claimed,
a corpus counted as the factory's, a regeneration that moved the map called inert, a hand-edited
generated file believed, a code change called a comment. Each is applied to a copy of the module,
the unit tests of `test_review_class.py` are run against the copy, and the mutation must make at
least one of them fail. A mutation every test survives is a rail nobody has watched fail, and this
test says so by name.

The measurement is printed as a table, so a run of this file is the evidence 0076 cites:

    python3 -m pytest -p no:cacheprovider tools/tests/factory/test_review_class_mutations.py -q -s
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.join(os.path.dirname(os.path.dirname(HERE)), "factory")
SOURCE = os.path.join(FACTORY, "reviewclass.py")

sys.path.insert(0, HERE)
sys.path.insert(0, FACTORY)
import test_review_class as scenarios  # noqa: E402

#: (name, [(old, new)]) -- each `old` must occur exactly once in the module, or the mutation is
#: refused before it is run: a mutation applied to nothing proves nothing.
MUTATIONS = (
    ("a decision record is not told from a document",
     [("    if DECISION_RECORD.match(path):\n        return decision_record(", "    if False:\n        return decision_record(")]),
    ("a record that says it supersedes another is a new record like any other",
     [("        found = SUPERSESSION.search(new)\n", "        found = None\n")]),
    ("a record that says how it can be overruled is a ruling",
     [('SUPERSESSION = re.compile(r"(?im)^[ \\t>*_-]*(?:supersedes|', 'SUPERSESSION = re.compile(r"(?im)(?:overrule|overturned|supersedes|'),
      ('r"retracts|withdraws)\\b[*_]*[ \\t]*:")', 'r"retracts|withdraws)\\b")')]),
    ("an edited decision record is a typo",
     [("    if _normal(old) == _normal(new):", "    if True:")]),
    ("a deleted decision record is only a record",
     [('        return SEMANTIC_RULING, "a decision record deleted: a ruling withdrawn"',
       '        return DECISION_RECORD_ONLY, "a decision record deleted: a ruling withdrawn"')]),
    ("an unreadable decision record is an addition that overrules nothing",
     [('        return SEMANTIC_RULING, "a decision record that cannot be read at the head"',
       '        return DECISION_RECORD_ONLY, "a decision record that cannot be read at the head"')]),
    ("a decision record need not be numbered",
     [('DECISION_RECORD = re.compile(r"\\Adocs/decisions/\\d{4}-[^/]+\\.md\\Z")',
       'DECISION_RECORD = re.compile(r"\\Adocs/decisions/.+\\Z")')]),
    ("an exemption nobody claimed is granted anyway",
     [('    if declared is None:\n        hints.append(', '    if declared is None:\n        return computed, problems, hints\n    if False:\n        hints.append(')]),
    ("a claim lowers a class the diff computed",
     [("        elif declared is not None and declared != computed and declared not in SEMANTIC:\n            problems.append(",
       "        elif declared is not None and declared != computed and declared not in SEMANTIC:\n            effective = declared\n            problems.append(")]),
    ("any claim is the right claim for an exemption",
     [("    if declared == computed:\n        return computed, problems, hints", "    if True:\n        return computed, problems, hints")]),
    ("an unknown class is a claim",
     [("    if declared is not None and declared not in CLASSES:", "    if False:")]),
    ("a ruling beside an implementation is a ruling",
     [("    if SEMANTIC_IMPLEMENTATION in classes:\n        computed = SEMANTIC_IMPLEMENTATION\n    elif SEMANTIC_RULING in classes:",
       "    if SEMANTIC_RULING in classes:\n        computed = SEMANTIC_RULING\n    elif SEMANTIC_IMPLEMENTATION in classes:\n        computed = SEMANTIC_IMPLEMENTATION\n    elif SEMANTIC_RULING in classes:")]),
    ("a path that cannot be classified is documentation",
     [('paths[path] = (SEMANTIC_IMPLEMENTATION, f"cannot be classified ({error})")',
       'paths[path] = (DOCUMENTATION, f"cannot be classified ({error})")')]),
    ("the reviewer of an unclaimed exemption is handed nothing",
     [('    return list(result["onSurface"]) if effective in SEMANTIC else []',
       '    return list(result["semanticFiles"])')]),
    ("the corpus is a file the factory writes",
     [('    return not path.startswith("corpus/") and fclass(path) in ("generated", "managed", "lock")',
       '    return fclass(path) in ("generated", "managed", "lock")')]),
    ("a path the table cannot place is the factory's",
     [('    return not path.startswith("corpus/") and fclass(path) in ("generated", "managed", "lock")',
       '    return not path.startswith("corpus/") and fclass(path) in ("generated", "managed", "lock", None)')]),
    ("a retired path is a file the factory writes",
     [('                return "retired"', '                return "generated"')]),
    ("a hand-written file beside a regeneration does not void it",
     [("    if foreign:\n        return False,", "    if False:\n        return False,")]),
    ("a regeneration need not move provenance.json",
     [('    if "provenance.json" not in changed:\n        return False,', '    if False:\n        return False,')]),
    ("a moved map, corpus or randomness does not void a regeneration",
     [("    if _identity(before) != _identity(after):", "    if False:")]),
    ("a dirty factory does not void a regeneration",
     [('    if (after.get("factory") or {}).get("dirty") is not False:', "    if False:")]),
    ("a hand-edited generated file is believed",
     [('        if data is None or recorded.get(path) != hashlib.sha256(data).hexdigest():', "        if False:")]),
    ("a lock file may move without its pins",
     [('    if any(fclass(p) == "lock" for p in changed) and "RulesFactory.Packages.g.props" not in changed:',
       "    if False:")]),
    ("every C# change is a comment change",
     [("    return a is not None and a == b", "    return True")]),
    ("a comment is deleted rather than being a separator",
     [('            buffer.append(" ")\n            i = end + 2', "            i = end + 2")]),
    ("an unterminated literal is compared as far as it goes",
     [("            if end >= n:\n                return None\n            flush()", "            if False:\n                return None\n            flush()")]),
    ("whitespace inside a literal is not code",
     [('            out.append("\\x00" + text[i:end] + "\\x01")\n            i = end\n        elif c == "\'":',
       '            out.append("\\x00" + re.sub(r"\\s+", " ", text[i:end]) + "\\x01")\n            i = end\n        elif c == "\'":')]),
    ("the template's own comment is a declaration",
     [('    text = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)', '    text = body or ""')]),
)


def mutated(edits, directory):
    with open(SOURCE, encoding="utf-8") as handle:
        text = handle.read()
    for old, new in edits:
        count = text.count(old)
        if count != 1:
            raise AssertionError(f"mutation site occurs {count} times, not once: {old!r}")
        text = text.replace(old, new)
    path = os.path.join(directory, "reviewclass_mutant.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    spec = importlib.util.spec_from_file_location(f"reviewclass_mutant_{abs(hash(text))}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_scenarios(module):
    """The unit tests against `module`: (tests run, tests failed or errored)."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in dir(scenarios):
        case = getattr(scenarios, name)
        if isinstance(case, type) and issubclass(case, unittest.TestCase):
            suite.addTests(loader.loadTestsFromTestCase(case))
    with mock.patch.object(scenarios, "rc", module):
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


class TestEveryMutationIsKilled(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="reviewclass-mutants-")
        self.addCleanup(shutil.rmtree, self.directory, True)

    def test_the_unmutated_module_passes_every_test(self):
        ran, failed = run_scenarios(mutated([], self.directory))
        self.assertGreater(ran, 60)
        self.assertEqual(failed, 0, "a mutation is measured against a suite that is green without it")

    def test_every_mutation_makes_a_test_fail(self):
        rows, survivors = [], []
        for name, edits in MUTATIONS:
            ran, failed = run_scenarios(mutated(edits, self.directory))
            rows.append((name, ran, failed))
            if not failed:
                survivors.append(name)
        width = max(len(name) for name, _, _ in rows)
        report = [f"{'mutation'.ljust(width)}  run  failed  verdict"]
        report += [f"{name.ljust(width)}  {ran:3}  {failed:6}  {'killed' if failed else 'SURVIVED'}"
                   for name, ran, failed in rows]
        report.append(f"{len(rows) - len(survivors)} of {len(rows)} mutations killed")
        print("\n" + "\n".join(report))
        self.assertEqual(survivors, [], "these mutations left every test green:\n  " + "\n  ".join(survivors))


if __name__ == "__main__":
    unittest.main()
