#!/usr/bin/env python3
"""The review-cost benchmark 0071 cites, held to what it shows (#532).

`tools/review-cost-benchmark.py` replays a repair chain over three real maps under the old model --
a complete packet at every head -- and under 0071's: one full review, a delta per repair, and one
final acceptance review when the chain ended on a delta. These tests hold the measured claims:

  * a chain of ordinary, local repairs hands the reviewer well under half of what the old model did,
    with two comprehensive reviews instead of one per head;
  * a repair of a rule everything rests on is not made cheaper by pretending it is local: it is
    reviewed in full, for a stated reason, and costs at most one extra comprehensive review;
  * every chain ends with the whole slice accepted, and the numbers are the same on every run.

Mutations, each watched failing `test_a_hub_repair_is_reviewed_in_full_for_a_stated_reason`: make
`impact()` retain a claim whose units moved (`if why:` -> `if False:` in tools/factory/reviewscope.py),
and the hub chain turns into cheap deltas that never name a reason; make `repair-too-broad` never fire
(`if not reasons and total >= ...` -> `if False:`), and the same. Every other mutation of the model is
measured by tools/tests/factory/test_review_scope_mutations.py.

Run: python3 -m pytest tools/tests/test_review_cost_benchmark.py
"""
import contextlib
import importlib.util
import io
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "review-cost-benchmark.py")

_spec = importlib.util.spec_from_file_location("review_cost_benchmark", TOOL)
benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(benchmark)


class TestTheBenchmark(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.results = {(r["map"].split("/")[1], r["where"], r["rounds"]): r
                       for path in benchmark.DEFAULT_MAPS for where in ("local", "hub") for rounds in (2, 7)
                       for r in [benchmark.run(path, rounds, 24, where)]}

    def ratio(self, key):
        result = self.results[key]
        return benchmark.totals(result["new"])["bytes"] / benchmark.totals(result["old"])["bytes"]

    def test_local_repairs_present_well_under_half_after_seven_rounds(self):
        for name in ("faa-part-107", "hazmat-172-table", "srd-52-combat"):
            result = self.results[(name, "local", 7)]
            self.assertLess(self.ratio((name, "local", 7)), 0.5, name)
            self.assertEqual(sum(1 for r in result["new"] if r["kind"] in ("full", "final")), 2, name)
            deltas = [r for r in result["new"] if r["kind"] == "delta"]
            self.assertEqual(len(deltas), 7, name)
            self.assertTrue(all(r["entries"] >= 1 and r["implementationBytes"] > 0 for r in deltas),
                            f"{name}: every delta presents the repaired entry and its diff")
            self.assertGreater(result["reused"], 100, name)

    def test_a_hub_repair_is_reviewed_in_full_for_a_stated_reason(self):
        result = self.results[("faa-part-107", "hub", 7)]
        self.assertEqual(result["fullReasons"], ["repair-too-broad"])
        self.assertEqual(self.ratio(("faa-part-107", "hub", 7)), 1.0,
                         "no cheaper than the old model, because nothing could be bounded -- and no dearer")
        for key, result in self.results.items():
            extra = benchmark.totals(result["new"])["bytes"] - benchmark.totals(result["old"])["bytes"]
            self.assertLessEqual(extra, benchmark.full_bytes(result), f"{key}: at most one extra complete review")

    def test_every_chain_ends_with_the_whole_slice_accepted(self):
        for key, result in self.results.items():
            self.assertTrue(result["finalCoversSlice"], key)
            self.assertEqual(result["finalProblems"], [], key)

    def test_the_numbers_are_the_same_on_every_run(self):
        first, second = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(first):
            self.assertEqual(benchmark.main(["--check"]), 0)
        with contextlib.redirect_stdout(second):
            benchmark.main(["--check"])
        self.assertEqual(first.getvalue(), second.getvalue())


if __name__ == "__main__":
    unittest.main()
