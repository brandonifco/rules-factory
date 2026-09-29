#!/usr/bin/env python3
"""The review-evidence model decides what a reviewer is allowed not to reread, so it is attacked (#532).

Each mutation below is a plausible defect in `tools/factory/reviewscope.py` that would let a
review skip something it owes: a changed entry called unaffected, a dependent dropped from the
closure, a stale or forged attestation accepted, a changed charter accepted, a delta PASS that
skipped a claim, a delta posted as the merge gate's verdict, a changed head treated as a reason, a
legacy verdict reused. Each is applied to a copy of the module, the scenarios of
`test_review_scope.py` are run against the copy, and the mutation must make at least one of them
fail. A mutation every scenario survives is a rail nobody has watched fail, and this test says so
by name.

The measurement is printed as a table, so a run of this file is the evidence 0071 cites:

    python3 -m pytest tools/tests/factory/test_review_scope_mutations.py -q -s
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.join(os.path.dirname(os.path.dirname(HERE)), "factory")
SOURCE = os.path.join(FACTORY, "reviewscope.py")

sys.path.insert(0, HERE)
import test_review_scope as scenarios  # noqa: E402

#: (name, [(old, new)]) -- each `old` must occur exactly once in the module, or the mutation is
#: refused before it is run: a mutation applied to nothing proves nothing.
MUTATIONS = (
    ("a changed entry is marked unaffected",
     [("for unit in sorted(recorded) if after.get(unit) != recorded[unit]]",
       "for unit in sorted(recorded) if after.get(unit) != recorded[unit] and not unit.startswith(\"entry:\")]")]),
    ("a changed implementation file is marked unaffected",
     [("for unit in sorted(recorded) if after.get(unit) != recorded[unit]]",
       "for unit in sorted(recorded) if after.get(unit) != recorded[unit] and not unit.startswith(\"file:\")]")]),
    ("a map dependent is omitted from the closure",
     [('for field in ("dependsOn", "enabledBy", "suspendedBy"):', 'for field in ("enabledBy", "suspendedBy"):')]),
    ("a caller of a shared primitive is omitted from the closure",
     [("for other in declares.get(name, ()) if other != path})",
       "for other in declares.get(name, ()) if other != path and not other.endswith(\"Dice.cs\")})")]),
    ("a member of a partial class declared in another file is not a dependency",
     [("            | set(EXTENSION_METHOD.findall(text)) | members | implemented_names(text))",
       "            | set(EXTENSION_METHOD.findall(text)) | implemented_names(text))")]),
    ("an entry reached through generated code is not a dependency",
     [("                        todo.extend(r for r in references.get(path, ()) if r not in seen)",
       "                        pass")]),
    ("a partial class's shared name links every file that declares it",
     [("    shared = {name for name, paths in partial_in.items() if len(paths) > 1}", "    shared = set()")]),
    ("a grown dependency set is not an invalidation",
     [('why += [f"dependency-added: {unit}" for unit in current["claims"][claim] if unit not in recorded]',
       "why += []")]),
    ("the wrong previous head is accepted",
     [('if document.get("reviewedCommit") != reviewed_commit:', "if False:")]),
    ("the wrong map digest is accepted",
     [("if named != declared:", "if False:")]),
    ("an edited attestation is accepted",
     [("if recorded_digest != digest:", "if False:")]),
    ("the wrong corpus digest is accepted",
     [("if unit in cited_corpora:", "if False:")]),
    ("a materially changed charter is accepted",
     [('("charter", "charter-changed"),\n', "")]),
    ("a delta PASS need not review every invalidated claim",
     [('review = sorted(set(invalidated) & set(current["claims"]) | set(new) | set(changes))',
       "review = sorted(set(new) | set(changes))"),
      ('            if claim in statuses and statuses[claim] != "reviewed":',
       "            if False:")]),
    ("a claim the prior review failed is not reviewed again",
     [("    for claim in carried:\n        if claim in retained:", "    for claim in []:\n        if claim in retained:")]),
    ("a delta PASS satisfies the merge gate, bypassing the final review",
     [('if document.get("reviewType") in COMPREHENSIVE:\n        return semantic_context, "success"',
       'if True:\n        return semantic_context, "success"')]),
    ("a final review may retain evidence instead of rereading the slice",
     [("if kind in COMPREHENSIVE and retained:", "if kind == \"full\" and retained:")]),
    ("a changed head alone is treated as a reason for a full review",
     [('    mode = "delta" if review or invalidated else "none"', '    mode = "delta" if review or invalidated else "full"')]),
    ("the head changing is accepted as a full-review reason",
     [("        if code in NOT_A_REASON:\n", "        if False:\n"),
      ('    "no-prior-attestation":', '    "head-changed": "the head changed",\n    "no-prior-attestation":')]),
    ("legacy evidence with no scope is reused",
     [('if evidence.get("scope") != "scoped" or not isinstance(evidence.get("units"), dict):', "if False:"),
      ('    before = evidence["units"]', '    before = evidence.get("units") or {}')]),
    ("a retained claim may carry fingerprints its parent never recorded",
     [('        elif before.get("dependencies") != claim.get("dependencies"):', "        elif False:")]),
    ("a self-review made before the repair is accepted",
     [('if record.get("claimSha256") != digest:', "if False:")]),
    ("a carried verdict does not require an unchanged semantic state",
     [('            and impact_record.get("mode") == "none" and not impact_record.get("invalidated"))', "            )")]),
    ("another reviewer's pass is carried as this one's",
     [('            and (document.get("reviewer") or {}).get("id") == reviewer\n', "")]),
    ("an invariant's statement is not part of what was reviewed",
     [('        needed.add(f"invariant-statement:{invariant[\'id\']}")\n', "")]),
    ("a dependency dropped from a claim is not an invalidation",
     [("        why += [f\"dependency-dropped: {unit}\" for unit in sorted(recorded)\n"
       "                if unit not in current[\"claims\"][claim] and after.get(unit) == recorded[unit]]\n", "")]),
    ("a removed claim leaves the evidence standing whole",
     [('    mode = "delta" if review or invalidated else "none"', '    mode = "delta" if review else "none"'),
      (' and not impact_record.get("invalidated"))', ")")]),
    ("a final review may follow a FAIL",
     [('    elif kind == "final" and (parent.get("reviewType") != "delta" or parent.get("result") != "PASS"):',
       "    elif False:")]),
    ("a call through an interface does not reach its implementations",
     [("            | set(EXTENSION_METHOD.findall(text)) | members | implemented_names(text))",
       "            | set(EXTENSION_METHOD.findall(text)) | members)")]),
    ("a finding on a change is not reviewed again",
     [('                                     and f"file:{f[\'claim\'][len(\'change:\'):]}" in after})',
       '                                     and False})')]),
)


def mutated(edits, directory):
    with open(SOURCE, encoding="utf-8") as handle:
        text = handle.read()
    for old, new in edits:
        count = text.count(old)
        if count != 1:
            raise AssertionError(f"mutation site occurs {count} times, not once: {old!r}")
        text = text.replace(old, new)
    path = os.path.join(directory, "reviewscope_mutant.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return scenarios.load(path, name=f"reviewscope_mutant_{abs(hash(text))}")


def run_scenarios(module):
    """The scenario suite against `module`: (tests run, tests failed or errored)."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in dir(scenarios):
        case = getattr(scenarios, name)
        if isinstance(case, type) and issubclass(case, scenarios.Scenario) and case is not scenarios.Scenario:
            bound = type(f"Mutant{name}", (case,), {"module": module})
            suite.addTests(loader.loadTestsFromTestCase(bound))
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


class TestEveryMutationIsKilled(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="reviewscope-mutants-")
        self.addCleanup(shutil.rmtree, self.directory, True)

    def test_the_unmutated_module_passes_every_scenario(self):
        ran, failed = run_scenarios(scenarios.load(SOURCE, name="reviewscope_unmutated"))
        self.assertGreater(ran, 30)
        self.assertEqual(failed, 0, "a mutation is measured against a suite that is green without it")

    def test_every_mutation_makes_a_scenario_fail(self):
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
        self.assertEqual(survivors, [], "these mutations left every scenario green:\n  " + "\n  ".join(survivors))


if __name__ == "__main__":
    unittest.main()
